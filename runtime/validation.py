"""Deterministic validation: parse PLAN.md validation commands and run them.

This is the heart of the determinism win. In the native pipeline the developer
agent is *asked* to run validation and paste output — fabrication is possible.
Here the graph itself runs each ``Validation:`` command via subprocess and
records the real exit code and output as a fact in state.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

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

_INLINE_RE = re.compile(r"^\s*[-*]?\s*(?:Validation|Acceptance):\s*(.+?)\s*$", re.MULTILINE)


def parse_validation_commands(plan_text: str) -> list[str]:
    """Extract runnable commands from PLAN.md / ACCEPTANCE.md.

    Supports inline ``Validation: <cmd>`` (PLAN.md) and ``Acceptance: <cmd>``
    (the held-out ACCEPTANCE.md), optionally wrapped in backticks. Returns
    commands in document order, de-duplicated.
    """
    commands: list[str] = []
    for match in _INLINE_RE.finditer(plan_text):
        cmd = match.group(1).strip().strip("`").strip()
        if cmd and cmd not in commands:
            commands.append(cmd)
    return commands


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
