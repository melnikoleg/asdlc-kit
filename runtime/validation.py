"""Deterministic validation: parse PLAN.md validation commands and run them.

This is the heart of the determinism win. In the native pipeline the developer
agent is *asked* to run validation and paste output — fabrication is possible.
Here the graph itself runs each ``Validation:`` command via subprocess and
records the real exit code and output as a fact in state.
"""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

# Mirror of .claude/hooks/block-destructive.sh — even though commands come from
# our own PLAN.md, we never run obviously destructive ones. Keep this list in
# sync with that hook so graph-run validation is no weaker than interactive use.
_DENY_PATTERNS = (
    "rm -rf /",
    "rm -rf ~",
    "git push --force",
    "git push -f",
    "git reset --hard",
    "> /dev/sda",
    "mkfs",
    "dd if=",
)

_FIELD_RE = re.compile(
    r"^\s*[-*]?\s*(Validation|Acceptance|E2E|Start|Healthcheck|Stop):[ \t]*(.*?)[ \t]*$",
    re.MULTILINE,
)


def parse_fields(text: str) -> dict[str, list[str]]:
    """Extract ``Key: value`` lines (PLAN/ACCEPTANCE/TEST_STRATEGY) by key.

    Values may be wrapped in backticks; each key keeps document order,
    de-duplicated. Empty values are dropped.
    """
    fields: dict[str, list[str]] = {}
    for match in _FIELD_RE.finditer(text):
        value = match.group(2).strip().strip("`").strip()
        if value and value not in fields.setdefault(match.group(1), []):
            fields[match.group(1)].append(value)
    return fields


def parse_validation_commands(plan_text: str) -> list[str]:
    """Runnable commands from PLAN.md (``Validation:``) / ACCEPTANCE.md (``Acceptance:``)."""
    fields = parse_fields(plan_text)
    commands: list[str] = []
    for cmd in fields.get("Validation", []) + fields.get("Acceptance", []):
        if cmd not in commands:
            commands.append(cmd)
    return commands


def load_strategy(path: Path) -> dict[str, list[str]]:
    """Parse TEST_STRATEGY.md; ``{}`` if the planner did not write one."""
    return parse_fields(path.read_text(encoding="utf-8")) if path.is_file() else {}


def is_destructive(command: str) -> bool:
    return any(pat in command for pat in _DENY_PATTERNS)


def _as_text(stream: Any) -> str:
    """Coerce a captured stream (str, bytes, or None) to text."""
    if stream is None:
        return ""
    if isinstance(stream, bytes):
        return stream.decode("utf-8", "replace")
    return str(stream)


def run_command(command: str, cwd: Path, timeout: int = 600) -> dict[str, Any]:
    """Run one shell command, capturing real output. Never raises on non-zero exit."""
    if is_destructive(command):
        return {
            "command": command,
            "exit_code": -1,
            "output": "BLOCKED: destructive command refused by validation guardrail",
            "passed": False,
        }
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return {
            "command": command,
            "exit_code": proc.returncode,
            "output": output[-8000:],  # cap stored output
            "passed": proc.returncode == 0,
        }
    except subprocess.TimeoutExpired as exc:
        # Surface whatever the command printed before it was killed — a hung
        # validation is far easier to diagnose with its partial output. The
        # captured streams on TimeoutExpired can be bytes even with text=True.
        partial = _as_text(exc.stdout) + _as_text(exc.stderr)
        return {
            "command": command,
            "exit_code": -1,
            "output": f"TIMEOUT after {timeout}s\n{partial[-4000:]}".rstrip(),
            "passed": False,
        }
    except OSError as exc:
        # e.g. command too long, or the shell itself cannot be spawned.
        return {
            "command": command,
            "exit_code": -1,
            "output": f"ERROR: could not run command: {exc}",
            "passed": False,
        }


def run_validation(plan_path: Path, cwd: Path, timeout: int = 600) -> dict[str, dict[str, Any]]:
    """Parse PLAN.md and run every validation command. Keyed by command string."""
    if not plan_path.is_file():
        return {}
    commands = parse_validation_commands(plan_path.read_text(encoding="utf-8"))
    return {cmd: run_command(cmd, cwd, timeout) for cmd in commands}


def all_passed(results: dict[str, dict[str, Any]]) -> bool:
    """True if there are results and all passed. Empty results => no gate => True."""
    if not results:
        return True
    return all(r.get("passed") for r in results.values())


class AppStartError(RuntimeError):
    """The app declared by TEST_STRATEGY.md did not come up healthy."""


def _healthy(check: str, cwd: Path) -> bool:
    if check.startswith(("http://", "https://")):
        try:
            with urllib.request.urlopen(check, timeout=3) as resp:  # noqa: S310 - local healthcheck
                return 200 <= resp.status < 400
        except OSError:
            return False
    return run_command(check, cwd, timeout=30)["passed"]


def _kill_group(proc: subprocess.Popen) -> None:
    for sig, wait in ((signal.SIGTERM, 10), (signal.SIGKILL, 5)):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue


@contextmanager
def running_app(
    strategy: dict[str, list[str]], cwd: Path, start_timeout: int = 90
) -> Iterator[None]:
    """Boot the app (``Start``), wait for ``Healthcheck``, tear it down after.

    No ``Start`` declared (cli/library) -> no-op. Refuses to start when the
    healthcheck already answers, so a stale server is never mistaken for ours.
    """
    start = (strategy.get("Start") or [None])[0]
    if not start:
        yield
        return
    check = (strategy.get("Healthcheck") or [None])[0]
    stop = (strategy.get("Stop") or [None])[0]
    for cmd in (start, stop):
        if cmd and is_destructive(cmd):
            raise AppStartError(f"BLOCKED: destructive command refused: {cmd}")
    if check and _healthy(check, cwd):
        raise AppStartError(f"healthcheck {check} already answers before Start - stale server or port in use")

    with tempfile.TemporaryFile() as log:
        proc = subprocess.Popen(
            start, shell=True, cwd=str(cwd), stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )

        def tail() -> str:
            log.seek(0)
            return log.read().decode("utf-8", "replace")[-4000:]

        try:
            deadline = time.monotonic() + start_timeout
            while check:
                if proc.poll() is not None:
                    raise AppStartError(f"app exited early (code {proc.returncode}):\n{tail()}")
                if _healthy(check, cwd):
                    break
                if time.monotonic() > deadline:
                    raise AppStartError(f"app not healthy after {start_timeout}s:\n{tail()}")
                time.sleep(0.5)
            yield
        finally:
            if stop:
                run_command(stop, cwd, timeout=30)
            _kill_group(proc)


def run_with_app(
    commands: list[str],
    strategy: dict[str, list[str]],
    cwd: Path,
    timeout: int = 600,
    start_timeout: int = 90,
) -> dict[str, dict[str, Any]]:
    """Run ``commands`` while the declared app is up. Keyed by command string."""
    try:
        with running_app(strategy, cwd, start_timeout):
            return {cmd: run_command(cmd, cwd, timeout) for cmd in commands}
    except AppStartError as exc:
        key = (strategy.get("Start") or ["app start"])[0]
        return {key: {"command": key, "exit_code": -1, "output": str(exc), "passed": False}}


def main(argv: list[str] | None = None) -> int:
    """``asdlc-e2e <issue> -- <cmd...>``: run one command against the booted app."""
    from .config import load_config
    from .state import validate_issue

    parser = argparse.ArgumentParser(prog="asdlc-e2e", description=main.__doc__)
    parser.add_argument("issue")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = " ".join(args.command[1:] if args.command[:1] == ["--"] else args.command)
    if not command:
        parser.error("a command is required after --")

    config = load_config()
    strategy = load_strategy(config.docs_for(validate_issue(args.issue)) / "TEST_STRATEGY.md")
    result = next(iter(run_with_app([command], strategy, config.repo_root).values()))
    print(result["output"])
    return result["exit_code"] if result["exit_code"] > 0 else (0 if result["passed"] else 1)


if __name__ == "__main__":
    sys.exit(main())
