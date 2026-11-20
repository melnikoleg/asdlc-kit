"""Resume-safe hybrid capsule executor with model hand-backs and deoptimization.

Each call advances consecutive deterministic programs. State is persisted
atomically so an interrupted command can be retried. The executing model only
sees reports, program diagnostics, and natural-language steps on hand-back.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

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


def _safe_session(path: Path, root: Path) -> Path:
    root = root.resolve()
    path = path.resolve()
    if not path.is_relative_to(root) or path == root:
        raise CapsuleError("session state must live under the cache root")
    return path


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
                 output_dir: Path) -> dict[str, Any]:
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
            inp.write_text(json.dumps({key: bindings[key] for key in program.get("inputs", [])},
                                      ensure_ascii=False), encoding="utf-8")
            os.chmod(inp, 0o600)
            # Program checks are always run in the same sandbox as execution.
            for key in ("check", "command"):
                argv = [a.replace("{package}", "/capsule" if self.sandbox == "docker"
                                  else str(source)) for a in program[key]]
                if self.sandbox == "docker":
                    # No host secrets, mounts or network; writable output is
                    # ephemeral and all inherited capabilities are dropped.
                    args = [
                        "docker", "run", "--rm", "--network", "none", "--pids-limit", "64",
                        "--memory", "512m", "--cpus", "1", "--cap-drop", "ALL",
                        "--security-opt", "no-new-privileges", "--read-only",
                        "--user", f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else "65534:65534",
                        "--tmpfs", "/tmp:rw,nosuid,size=64m",
                        "-v", f"{source}:/capsule:ro",
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
                    env = {"PATH": os.environ.get("PATH", "")}
                else:
                    # For unit tests only; never use for untrusted compiled code.
                    args = argv
                    env = dict(os.environ)
                    env.update(SKILLCACHE_INPUT=str(inp),
                               SKILLCACHE_PACKAGE=str(source),
                               SKILLCACHE_WORKSPACE=str(workspace),
                               SKILLCACHE_OUTPUT=str(output_dir))
                try:
                    outcome = subprocess.run(
                        args, cwd=workspace if self.sandbox == "local-test" else None,
                        env=env, capture_output=True, text=True,
                        timeout=program.get("timeout_seconds", 15),
                    )
                except subprocess.TimeoutExpired as exc:
                    raise TimeoutError("capsule step timed out") from exc
                if outcome.returncode:
                    raise CapsuleError(
                        f"program {name} {key} failed (exit {outcome.returncode}): "
                        + outcome.stderr[-1200:]
                    )
                if key == "command":
                    if len(outcome.stdout.encode("utf-8")) > MAX_RESULT_BYTES:
                        raise CapsuleError("program output too large")
                    try:
                        result = json.loads(outcome.stdout)
                    except json.JSONDecodeError as exc:
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
        raise CapsuleError("program did not execute")

    def start(self, bindings: dict[str, Any], workspace: Path, session: Path) -> dict[str, Any]:
        if session.exists():
            raise CapsuleError("capsule session already exists")
        session.parent.mkdir(parents=True, exist_ok=True)
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
        return self._advance(state, workspace, session)

    def resume(self, bindings: dict[str, Any], workspace: Path, session: Path) -> dict[str, Any]:
        state = json.loads(session.read_text("utf-8"))
        if state.get("capsule_id") != capsule_id(self.capsule) or state.get("finished"):
            raise CapsuleError("session has stale capsule or already completed")
        if state.get("awaiting") not in ("needs_bindings", "your_steps"):
            raise CapsuleError("session is not awaiting the model")
        given = _validate_inputs(bindings)
        unknown = set(given) - set(self.capsule["bindings"])
        if unknown:
            raise CapsuleError("unknown binding(s): " + ", ".join(sorted(unknown)))
        state["bindings"].update(given)
        state["awaiting"] = None
        _write_json(session, state)
        return self._advance(state, workspace, session)

    def _advance(self, state: dict[str, Any], workspace: Path, session: Path) -> dict[str, Any]:
        workspace = workspace.resolve()
        if not workspace.is_dir() or workspace.is_symlink():
            raise CapsuleError("invalid workspace")
        steps = [*self.capsule["steps"], *self.capsule.get("verification", [])]
        output_dir = session.with_name(session.name + ".outputs")
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
                try:
                    values = self._program(name, state["bindings"], workspace, output_dir)
                    issue = None
                    break
                except TimeoutError as exc:
                    issue = str(exc)
                    break  # one timeout is sufficient to deoptimize
                except (CapsuleError, OSError) as exc:
                    issue = str(exc)
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
            docker_image: str = "python:3.11-slim") -> tuple[bool, str]:
    """Gates 1–3: structure/dataflow, sandboxed program checks, sandboxed replay.

    Qualification happens in a *fresh* copied workspace, never in the live repo.
    A program requiring model steps must provide examples of all bindings.
    """
    try:
        validate_capsule(candidate)
        if candidate["form"] == "textual":
            return True, "textual procedure accepted (no executable programs)"
        examples = candidate.get("examples")
        if not isinstance(examples, dict):
            return False, "hybrid capsule missing observed binding examples"
        # Reject suspicious workspaces instead of following symlinks into secrets.
        if workspace.is_symlink() or not workspace.is_dir():
            return False, "invalid qualification workspace"
        with tempfile.TemporaryDirectory(prefix="asdlc-qualify-") as base:
            dest = Path(base) / "workspace"
            shutil.copytree(workspace, dest, ignore=shutil.ignore_patterns(
                ".git", ".asdlc", ".asdlc-venv", ".venv", "node_modules", "__pycache__",
                ".env", ".env.*", "*.pem", "*.key", "secrets.*"
            ), symlinks=True)
            if any(p.is_symlink() for p in dest.rglob("*")):
                return False, "symlinks are not allowed in qualification workspace"
            session = Path(base) / "session.json"
            executor = Executor(candidate, dest, sandbox=sandbox, docker_image=docker_image)
            result = executor.start(
                {k: v for k, v in examples.items() if k in candidate["bindings"]},
                dest, session
            )
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
                    {key: examples[key] for key in missing}, dest, session
                )
            if result["status"] != "complete" or result["failed_count"]:
                return False, "qualification replay incomplete: " + str(result)
            return True, "qualified by full deterministic replay with example hand-backs"
    except (CapsuleError, OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
        return False, str(exc)
