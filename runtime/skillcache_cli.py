"""asdlc-skillcache: observe/compile/qualify/start/continue/inspect capsules.

Each invocation is short and stateful, suitable for Codex or Claude's shell
tools. Errors are explicit JSON and exit nonzero; the caller then falls back
to the original skill rather than claiming a cached result.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from .skillcache_capsule import CapsuleError, capsule_id, validate_capsule
from .skillcache_compiler import compile_observation, find_capsules
from .skillcache_executor import Executor, qualify
from .skill_cache import workspace_fingerprint
from .state import validate_issue


def _load(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 524288:
        raise CapsuleError("missing, symlinked or oversized capsule/trace")
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise CapsuleError("input must be a JSON object")
    return result


def _bindings(raw: str) -> dict[str, Any]:
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise CapsuleError("--bindings must be a JSON object")
    return result


def _session(workspace: Path, slug: str) -> Path:
    validate_issue(slug)
    return workspace / ".asdlc" / "skill-cache" / "sessions" / (slug + ".json")


async def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace).resolve()
    if args.operation == "inspect":
        capsule = _load(Path(args.capsule))
        validate_capsule(capsule, require_provenance=True)
        return {"status": "ok", "capsule_id": capsule_id(capsule),
                "name": capsule["name"], "form": capsule["form"],
                "role": capsule["role"], "bindings": capsule["bindings"],
                "steps": capsule["steps"], "verification": capsule.get("verification", [])}
    if args.operation == "lookup":
        fingerprint = workspace_fingerprint(workspace)
        if not fingerprint:
            raise CapsuleError("workspace fingerprint unavailable")
        capsules = find_capsules(workspace, args.role, args.request, fingerprint)
        return {"status": "ok", "hits": [{
            "id": capsule_id(c), "name": c["name"], "form": c["form"],
            "description": c["description"],
        } for c in capsules]}
    if args.operation == "compile":
        fingerprint = workspace_fingerprint(workspace)
        if not fingerprint:
            raise CapsuleError("workspace fingerprint unavailable")
        trace = _load(Path(args.trace))
        source = Path(args.skill).read_text(encoding="utf-8")
        path, detail = await compile_observation(
            root=workspace, role=args.role, provider=args.provider,
            request=args.request, workspace_hash=fingerprint,
            source_skill=source, trace=trace, sandbox=args.sandbox
        )
        return {"status": "complete" if path else "fallback",
                "capsule_path": str(path) if path else None, "detail": detail}
    capsule = _load(Path(args.capsule))
    executor = Executor(capsule, workspace, sandbox=args.sandbox)
    if args.operation == "qualify":
        ok, reason = qualify(capsule, workspace, sandbox=args.sandbox)
        return {"status": "qualified" if ok else "fallback", "detail": reason}
    session = _session(workspace, args.session)
    if args.operation == "start":
        return executor.start(_bindings(args.bindings), workspace, session)
    if args.operation == "continue":
        return executor.resume(_bindings(args.bindings), workspace, session)
    raise CapsuleError("unsupported operation")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="asdlc-skillcache")
    sub = parser.add_subparsers(dest="operation", required=True)
    for operation in ("inspect", "lookup", "compile", "qualify", "start", "continue"):
        cmd = sub.add_parser(operation)
        cmd.add_argument("--workspace", default=".")
        if operation in ("inspect", "qualify", "start", "continue"):
            cmd.add_argument("--capsule", required=True)
        if operation in ("lookup", "compile"):
            cmd.add_argument("--role", required=True)
            cmd.add_argument("--request", required=True)
        if operation == "compile":
            cmd.add_argument("--trace", required=True, help="sanitized observation JSON")
            cmd.add_argument("--skill", required=True, help="source skill Markdown")
            cmd.add_argument("--provider", choices=("codex", "claude"), default="codex")
        if operation in ("compile", "qualify", "start", "continue"):
            cmd.add_argument("--sandbox", choices=("docker",), default="docker")
        if operation in ("start", "continue"):
            cmd.add_argument("--session", required=True)
            cmd.add_argument("--bindings", default="{}")
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(dispatch(args))
    except (CapsuleError, OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "fallback", "error": str(exc)[:900]}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] not in ("fallback", "error") else 1


if __name__ == "__main__":
    raise SystemExit(main())
