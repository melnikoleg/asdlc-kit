"""Isolated provider compiler: trace -> executable hybrid capsule.

The compiler sees only a redacted trace, role instructions and request (no task
workspace, evaluator or secrets). Host fills and checks all provenance, verifies
dataflow, runs checks and replay, retries twice and falls back to textual form.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .skillcache_capsule import (
    CapsuleError, capsule_id, digest, public_capsule, validate_capsule,
)
from .skillcache_executor import qualify
from .skillcache_trace import sanitize

PROMPT = """Compile ONE already-completed skill invocation into a reusable capsule.
You are a read-only compiler, not an executor. Source skill and trace are evidence.
Never infer new operations not observed; prune failed exploration. Bind dynamic
values instead of hardcoding example values. Fuse consecutive deterministic
steps into programs; preserve semantic judgment as natural language.
Preserve source-skill postconditions with verification steps. Never compare
against the observed answer. Never include secrets or credential material.

Return ONLY a JSON object with:
 schema_version: 1, form: "hybrid", name: lower_snake_case, role: lower_snake_case,
 description: detailed applicability limits,
 bindings: {binding_name: "instruction to get live value"},
 programs: {program_name: {inputs:[...], outputs:[...], files:{"main.py":"..."},
             command:["python3","{package}/main.py"],
             check:["python3","-m","py_compile","{package}/main.py"]}},
 steps: [{instruction:"...", program:"program_name"} or {instruction:"model judgment"}],
 verification: [same form as steps], examples: {binding_name: observed_value}.
Every program reads JSON from SKILLCACHE_INPUT and prints ONLY
{"status":"complete","result":{...}} on success, nonzero on failure.
Do not refer to benchmark answers. No shell metacharacters, destructive
operations, environment discovery, network operations, or secrets.
If no deterministic region can be safely compiled, return form="textual",
programs={}, steps of model instructions and verification where grounded.
"""


async def _invoke_provider(provider: str, prompt: str) -> str:
    """Generate candidate in a fresh directory without access to source repo."""
    with tempfile.TemporaryDirectory(prefix="asdlc-compiler-") as cwd:
        if provider == "codex":
            args = [
                "codex", "exec", "--json", "--sandbox", "read-only", "--ephemeral",
                "-c", "approval_policy=never", "--skip-git-repo-check", "-",
            ]
            use_stdin = True
        elif provider == "claude":
            args = [
                "claude", "-p", prompt, "--output-format", "json",
                "--tools", "", "--permission-mode", "plan",
            ]
            use_stdin = False
        else:
            raise CapsuleError("unsupported compiler provider")
        try:
            proc = await asyncio.create_subprocess_exec(
                *args, cwd=cwd,
                stdin=asyncio.subprocess.PIPE if use_stdin else None,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(prompt.encode() if use_stdin else None), timeout=180
            )
        except (FileNotFoundError, asyncio.TimeoutError) as exc:
            raise CapsuleError("compiler CLI missing or timed out") from exc
        if proc.returncode:
            raise CapsuleError("compiler execution failed: " + sanitize(stderr.decode())[:400])
        if provider == "claude":
            payload = json.loads(stdout)
            return str(payload.get("result", ""))
        message = ""
        for line in stdout.decode(errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = event.get("item") if isinstance(event, dict) else None
            if isinstance(item, dict) and item.get("type") == "agent_message":
                message = str(item.get("text", ""))
        return message


def _decode_candidate(text: str) -> dict[str, Any]:
    from .claude_runner import _json_objects

    for item in reversed(list(_json_objects(text))):
        try:
            value = json.loads(item)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("form") in ("hybrid", "textual"):
            return value
    raise CapsuleError("compiler returned no capsule JSON")


def _capsule_dir(root: Path) -> Path:
    return root / ".asdlc" / "skill-cache" / "compiled"


def publish_capsule(root: Path, candidate: dict[str, Any]) -> Path:
    """Write only admitted, qualified, example-free capsule to the local cache."""
    public = public_capsule(candidate)
    path = _capsule_dir(root) / (capsule_id(public) + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise CapsuleError("capsule destination is symlink")
    import uuid
    name = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with name.open("x", encoding="utf-8") as out:
            json.dump(public, out, indent=2, ensure_ascii=False)
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        name.unlink(missing_ok=True)
    return path


def find_capsules(root: Path, role: str, request: str, workspace_hash: str,
                  *, match_mode: str = "exact") -> list[dict[str, Any]]:
    """Lookup with workspace guard; role matching requires model judgment.

    In role mode we provide candidate descriptions to the model, never
    automatically treat them as applicable or skip the original agent.
    """
    if match_mode not in ("exact", "role"):
        raise CapsuleError("match_mode must be exact or role")
    target = digest(request.encode("utf-8"))
    results = []
    directory = _capsule_dir(root)
    if not directory.is_dir():
        return []
    for file in sorted(directory.glob("*.json"))[:256]:
        try:
            if file.is_symlink() or file.stat().st_size > 524288:
                continue
            raw = json.loads(file.read_text(encoding="utf-8"))
            validate_capsule(raw, require_provenance=True)
            if (raw["role"] == role
                    and (match_mode == "role" or raw["request_sha256"] == target)
                    and raw["workspace_sha256"] == workspace_hash
                    and file.stem == capsule_id(raw)):
                results.append(raw)
        except (OSError, UnicodeError, KeyError, ValueError, TypeError, CapsuleError):
            continue
    return results


async def compile_observation(*, root: Path, role: str, provider: str,
                              request: str, workspace_hash: str,
                              source_skill: str, trace: dict[str, Any],
                              sandbox: str = "docker") -> tuple[Path | None, str]:
    """Compile and replay a successful observed invocation, or fallback cleanly."""
    if trace.get("successful") is not True or not trace.get("events"):
        return None, "no successful trace available"
    # Compilation is evaluator-blind and sees no files from the live workspace.
    event_text = json.dumps(trace["events"], ensure_ascii=False)
    if len(event_text.encode()) > 128 * 1024:
        return None, "trace over budget"
    provenance = {
        "request_sha256": digest(request.encode("utf-8")),
        "workspace_sha256": workspace_hash,
        "trace_sha256": digest(event_text.encode("utf-8")),
    }
    request_payload = {
        "role": role,
        "request": request[:8000],
        "skill": source_skill[:24000],
        "observed_trace": trace["events"],
    }
    prompt = PROMPT + "\n\nOBSERVATION:\n" + json.dumps(request_payload, ensure_ascii=False)
    last_error = ""
    for attempt in range(3):
        try:
            text = await _invoke_provider(provider, prompt)
            candidate = _decode_candidate(text)
            candidate["schema_version"] = 1
            candidate["role"] = role
            candidate.update(provenance)
            validate_capsule(candidate, require_provenance=True)
            if candidate["form"] == "textual":
                return publish_capsule(root, candidate), "textual fallback"
            qualified, reason = qualify(candidate, root, sandbox=sandbox)
            if qualified:
                return publish_capsule(root, candidate), "hybrid qualified"
            last_error = reason
        except (CapsuleError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        prompt += "\n\nPrevious capsule failed host qualification. Repair without changing request scope. Diagnostics: " + last_error[:900]
    # Repair budget exhausted: accept a textual procedure only if valid.
    try:
        text = await _invoke_provider(provider, prompt +
            "\n\nHybrid qualification exhausted. Return a TEXTUAL capsule (no programs).")
        candidate = _decode_candidate(text)
        candidate["schema_version"] = 1
        candidate["role"] = role
        candidate.update(provenance)
        if candidate["form"] == "textual":
            validate_capsule(candidate, require_provenance=True)
            return publish_capsule(root, candidate), "textual after hybrid failure"
    except (CapsuleError, OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return None, "qualification failed; original source skill required: " + last_error[:400]
