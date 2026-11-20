"""Resume-safe hybrid capsule executor with model hand-backs and deoptimization.

Each call advances consecutive deterministic programs. State is persisted
atomically so an interrupted command can be retried. The executing model only
sees reports, program diagnostics, and natural-language steps on hand-back.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from .skill_cache import workspace_fingerprint
from .skillcache_capsule import CapsuleError, validate_capsule, capsule_id

MAX_RESULT_BYTES = 32768
MAX_BINDINGS_BYTES = 32768


def _validate_inputs(values: Any) -> dict[str, Any]:
    if not isinstance(values, dict) or len(values) > 40:
        raise CapsuleError("bindings must be a bounded JSON object")
    try:
        if len(json.dumps(values, ensure_ascii=False).encode()) > MAX_BINDINGS_BYTES:
            raise CapsuleError("bindings too large")
    except (TypeError, ValueError) as exc:
        raise CapsuleError("bindings must be JSON serializable") from exc
    return values


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


@contextmanager
def _session_lock(session: Path):
    session.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(session) + ".lock", timeout=0)) as lock:
        try:
            lock.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as exc:
            raise CapsuleError("session is busy or unavailable") from exc
        yield


@contextmanager
def _snapshot(workspace: Path, capsule: dict, session: Path | None = None):
    with tempfile.TemporaryDirectory(prefix="asdlc-workspace-") as base:
        dest = Path(base) / "workspace"
        fingerprint = workspace_fingerprint(
            workspace, snapshot=dest, role=capsule["role"],
            session=session.resolve() if session is not None else None,
        )
        if fingerprint is None or fingerprint != capsule["workspace_sha256"]:
            raise CapsuleError("workspace unavailable or changed since qualification")
        yield dest


def _run_bounded(args, *, cwd, env, timeout):
    with subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE) as proc:
        def read_stream(stream):
            data = stream.read(MAX_RESULT_BYTES + 1)
            if len(data) > MAX_RESULT_BYTES:
                proc.kill()
                raise CapsuleError("program output too large")
            return data

        with ThreadPoolExecutor(max_workers=2) as readers:
            stdout = readers.submit(read_stream, proc.stdout)
            stderr = readers.submit(read_stream, proc.stderr)
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError("capsule step timed out") from exc
            finally:
                if proc.poll() is None:
                    proc.kill()
            return subprocess.CompletedProcess(args, proc.returncode, stdout.result(), stderr.result())


class Executor:
    def __init__(self, capsule: dict[str, Any], root: Path, *, sandbox: str = "docker",
                 docker_image: str = "python:3.11-slim") -> None:
        self.capsule = validate_capsule(capsule, require_provenance=True)
        self.root = root.resolve()
        self.sandbox = sandbox
        self.docker_image = docker_image
        if sandbox not in ("docker", "local-test"):
            raise CapsuleError("unsupported sandbox; docker is required for production")
        if sandbox == "docker" and shutil.which("docker") is None:
            raise CapsuleError("docker unavailable; deoptimize to source skill")

    def _program(self, name: str, bindings: dict[str, Any], workspace: Path,
                 output_dir: Path, *, check_only: bool = False) -> dict[str, Any]:
        """Execute one program in an isolated container or explicit test runner."""
        program = self.capsule["programs"][name]
        with tempfile.TemporaryDirectory(prefix="asdlc-capsule-") as base:
            basepath = Path(base)
            source = basepath / "program"
            source.mkdir()
            for relative, content in program["files"].items():
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            inp = basepath / "input.json"
            # Syntax/build checks never need live program inputs.
            inputs = {} if check_only else {
                key: bindings[key] for key in program.get("inputs", [])
            }
            inp.write_text(json.dumps(inputs, ensure_ascii=False), encoding="utf-8")
            os.chmod(inp, 0o600)
            # Program checks are always run in the same sandbox as execution.
            for key in (("check",) if check_only else ("check", "command")):
                argv = [a.replace("{package}", "/capsule" if self.sandbox == "docker"
                                  else str(source)) for a in program[key]]
                timeout = program.get("timeout_seconds", 15)
                container = None
                if self.sandbox == "docker":
                    # No host secrets, mounts or network; writable output is
                    # ephemeral and all inherited capabilities are dropped.
                    args = [
                        "docker", "create", "--pull", "never", "--log-driver", "none",
                        "--network", "none", "--pids-limit", "64",
                        "--memory", "512m", "--cpus", "1", "--cap-drop", "ALL",
                        "--security-opt", "no-new-privileges", "--read-only",
                        "--user", f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else "65534:65534",
                        "--tmpfs", "/tmp:rw,nosuid,size=64m",
                        "-v", f"{source}:/capsule:rw",
                        "-v", f"{inp}:/input.json:ro",
                        "-v", f"{workspace}:/workspace:ro",
                        "-v", f"{output_dir}:/output:rw",
                        "-w", "/workspace",
                        "-e", "SKILLCACHE_INPUT=/input.json",
                        "-e", "SKILLCACHE_PACKAGE=/capsule",
                        "-e", "SKILLCACHE_WORKSPACE=/workspace",
                        "-e", "SKILLCACHE_OUTPUT=/output",
                        self.docker_image, *argv,
                    ]
                    try:
                        created = subprocess.run(args, capture_output=True, timeout=timeout)
                    except subprocess.TimeoutExpired as exc:
                        raise TimeoutError("docker create timed out") from exc
                    if created.returncode:
                        raise CapsuleError("docker create failed: " + created.stderr[-1200:].decode(errors="replace"))
                    container = created.stdout.decode("ascii").strip()
                    args = ["docker", "start", "--attach", container]
                    env = None
                else:
                    # For unit tests only; never use for untrusted compiled code.
                    args = argv
                    env = dict(os.environ)
                    env.update(SKILLCACHE_INPUT=str(inp),
                               SKILLCACHE_PACKAGE=str(source),
                               SKILLCACHE_WORKSPACE=str(workspace),
                               SKILLCACHE_OUTPUT=str(output_dir))
                try:
                    outcome = _run_bounded(
                        args, cwd=workspace if self.sandbox == "local-test" else None,
                        env=env, timeout=timeout,
                    )
                finally:
                    if container is not None:
                        # A killed attach client does not terminate the container.
                        subprocess.run(["docker", "rm", "--force", container], check=True,
                                       timeout=30, stdout=subprocess.DEVNULL)
                if outcome.returncode:
                    raise CapsuleError(
                        f"program {name} {key} failed (exit {outcome.returncode}): "
                        + outcome.stderr[-1200:].decode(errors="replace")
                    )
                if key == "command":
                    try:
                        result = json.loads(outcome.stdout)
                    except (json.JSONDecodeError, UnicodeError) as exc:
                        raise CapsuleError("program did not return JSON") from exc
                    if not isinstance(result, dict) or result.get("status") != "complete":
                        raise CapsuleError("program result status is not complete")
                    values = result.get("result")
                    if not isinstance(values, dict):
                        raise CapsuleError("program result must be a JSON object")
                    expected = set(program.get("outputs", []))
                    if not expected.issubset(values):
                        raise CapsuleError("program omitted declared outputs")
                    return values
            if check_only:
                return {}
        raise CapsuleError("program did not execute")

    def start(self, bindings: dict[str, Any], workspace: Path, session: Path) -> dict[str, Any]:
        with _session_lock(session):
            if session.exists():
                raise CapsuleError("capsule session already exists")
            with _snapshot(workspace, self.capsule, session) as dest:
                state = {
                    "capsule_id": capsule_id(self.capsule),
                    "position": 0,
                    "awaiting": None,
                    "bindings": _validate_inputs(bindings),
                    "completed": [],
                    "failed": [],
                    "finished": False,
                }
                _write_json(session, state)
                return self._advance(state, dest, session)

    def resume(self, bindings: dict[str, Any], workspace: Path, session: Path) -> dict[str, Any]:
        with _session_lock(session):
            state = json.loads(session.read_text("utf-8"))
            if state.get("capsule_id") != capsule_id(self.capsule) or state.get("finished"):
                raise CapsuleError("session has stale capsule or already completed")
            given = _validate_inputs(bindings)
            if state["awaiting"] is None and given:
                raise CapsuleError("retry interrupted steps without new bindings")
            unknown = set(given) - set(self.capsule["bindings"])
            if unknown:
                raise CapsuleError("unknown binding(s): " + ", ".join(sorted(unknown)))
            with _snapshot(workspace, self.capsule, session) as dest:
                state["bindings"].update(given)
                state["awaiting"] = None
                return self._advance(state, dest, session)

    def _advance(self, state: dict[str, Any], workspace: Path, session: Path) -> dict[str, Any]:
        steps = [*self.capsule["steps"], *self.capsule.get("verification", [])]
        output_dir = session.with_name(session.name + ".outputs")
        if "output_version" in state:
            output_dir = output_dir.with_suffix(".outputs." + uuid.UUID(state["output_version"]).hex)
        if output_dir.is_symlink():
            raise CapsuleError("staging output path cannot be symlink")
        output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._staging_dir = output_dir
        fresh_completed: list[dict[str, Any]] = []
        handback: list[dict[str, Any]] = []
        while state["position"] < len(steps):
            step = steps[state["position"]]
            name = step.get("program")
            if name is None:
                handback.append({"kind": "model", "instruction": step["instruction"]})
                state["position"] += 1
                continue
            program = self.capsule["programs"][name]
            missing = sorted(set(program.get("inputs", [])) - state["bindings"].keys())
            if handback:
                state["awaiting"] = "your_steps"
                _write_json(session, state)
                return self._report("your_steps", state, fresh_completed, handback,
                                    required=self._required_until_handoff(steps, state))
            if missing:
                state["awaiting"] = "needs_bindings"
                _write_json(session, state)
                return self._report("needs_bindings", state, fresh_completed, [],
                                    required=missing)
            # Persist before execution: crashed processes retry this step.
            _write_json(session, state)
            issue = None
            for attempt in range(2):
                version = uuid.uuid4().hex
                staging = session.with_name(session.name + ".outputs." + version)
                try:
                    shutil.copytree(output_dir, staging, symlinks=True)
                    values = self._program(name, state["bindings"], workspace, staging)
                    if any(p.is_symlink() for p in staging.rglob("*")):
                        raise CapsuleError("symlinks are not allowed in staged output")
                    state["output_version"] = version
                    output_dir = self._staging_dir = staging
                    issue = None
                    break
                except TimeoutError as exc:
                    issue = str(exc)
                    break  # one timeout is sufficient to deoptimize
                except (CapsuleError, OSError) as exc:
                    issue = str(exc)
                finally:
                    if output_dir != staging and staging.exists():
                        shutil.rmtree(staging)
            if issue is not None:
                failed = {"kind": "program_failed", "program": name,
                          "instruction": step["instruction"], "diagnostic": issue}
                state["failed"].append(failed)
                handback.append(failed)
                state["position"] += 1
                continue
            for field in program.get("outputs", []):
                state["bindings"][field] = values[field]
            event = {"program": name, "result": values}
            state["completed"].append(event)
            fresh_completed.append(event)
            state["position"] += 1
        if handback:
            state["awaiting"] = "your_steps"
            _write_json(session, state)
            return self._report("your_steps", state, fresh_completed, handback)
        state["finished"] = True
        _write_json(session, state)
        return self._report("complete", state, fresh_completed, [])

    def _required_until_handoff(self, steps: list[dict[str, Any]], state: dict[str, Any]) -> list[str]:
        needed: set[str] = set()
        produced = set(state["bindings"])
        for step in steps[state["position"]:]:
            if "program" not in step:
                break
            prog = self.capsule["programs"][step["program"]]
            needed |= set(prog.get("inputs", [])) - produced
            produced.update(prog.get("outputs", []))
        return sorted(needed)

    def _report(self, kind: str, state: dict[str, Any], completed: list[dict[str, Any]],
                handback: list[dict[str, Any]], required: list[str] | None = None) -> dict[str, Any]:
        return {
            "status": kind,
            "position": state["position"],
            "completed": completed,
            "your_steps": handback,
            "required_bindings": required or [],
            "failed_count": len(state["failed"]),
            "staging_directory": str(self._staging_dir) if hasattr(self, "_staging_dir") else None,
        }


def qualify(candidate: dict[str, Any], workspace: Path, *, sandbox: str = "docker",
            docker_image: str = "python:3.11-slim",
            examples: dict[str, Any] | None = None) -> tuple[bool, str]:
    """Gates 1–3: structure/dataflow, sandboxed program checks, sandboxed replay.

    Qualification happens in a *fresh* copied workspace, never in the live repo.
    A program requiring model steps must provide examples of all bindings.
    """
    try:
        validate_capsule(candidate)
        if candidate["form"] == "textual":
            return True, "textual procedure accepted (no executable programs)"
        if examples is None:
            examples = candidate.get("examples")
        if not isinstance(examples, dict):
            return False, "hybrid capsule missing observed binding examples"
        _validate_inputs(examples)
        if set(examples) - set(candidate["bindings"]):
            return False, "unknown qualification binding"
        with tempfile.TemporaryDirectory(prefix="asdlc-qualify-") as base:
            session = Path(base) / "session.json"
            executor = Executor(candidate, workspace, sandbox=sandbox, docker_image=docker_image)
            # Gate 2 is separate from execution: *every* program check must
            # pass before Gate 3 begins replay in this fresh workspace.
            checks = Path(base) / "checks"
            checks.mkdir()
            with _snapshot(workspace, candidate) as dest:
                for name in candidate["programs"]:
                    executor._program(name, {}, dest, checks, check_only=True)
            result = executor.start(examples, workspace, session)
            # Qualification-only examples simulate a model hand-back. The
            # executor itself, and all program/check calls, are the same as
            # during warm execution. Examples are stripped before publication.
            for _ in range(len(candidate["steps"]) + len(candidate.get("verification", [])) + 2):
                if result["status"] == "complete":
                    break
                if result["status"] not in ("needs_bindings", "your_steps"):
                    return False, "unexpected qualification hand-back: " + str(result)
                if result["failed_count"]:
                    return False, "qualification program failed: " + str(result)
                missing = result["required_bindings"]
                if not set(missing).issubset(examples):
                    return False, "model binding examples missing: " + ", ".join(missing)
                result = executor.resume(
                    {key: examples[key] for key in missing}, workspace, session
                )
            if result["status"] != "complete" or result["failed_count"]:
                return False, "qualification replay incomplete: " + str(result)
            return True, "qualified by full deterministic replay with example hand-backs"
    except (CapsuleError, OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
        return False, str(exc)
