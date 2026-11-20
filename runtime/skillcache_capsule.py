"""SkillCache capsule schema, dataflow verification and admission contracts.

Hybrid representation from arXiv:2611.10022: (metadata, bindings, programs,
steps, verification). Qualification-only examples are never published.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

IDENT = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
MAX_PROGRAMS = 16
MAX_STEPS = 48
MAX_SOURCE_BYTES = 196_608
MAX_CAPSULE_BYTES = 524_288


class CapsuleError(ValueError):
    """Invalid or unqualified capsule; caller must use the original skill."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ident(value: Any) -> str:
    if not isinstance(value, str) or not IDENT.fullmatch(value):
        raise CapsuleError(f"invalid capsule identifier: {str(value)[:90]}")
    return value


def _relative_source(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 160:
        raise CapsuleError("invalid program file name")
    path = Path(value)
    if path.is_absolute() or any(x in ("..", ".") for x in path.parts):
        raise CapsuleError("program file must be relative without traversal")
    if len(path.parts) > 4 or value.startswith("-") or any("\\" in x for x in path.parts):
        raise CapsuleError("invalid program file path")
    return value


def _argv(value: Any) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= 24:
        raise CapsuleError("program command/check must be nonempty argv")
    if any(not isinstance(arg, str) or not arg or len(arg) > 512
           or "\x00" in arg for arg in value):
        raise CapsuleError("invalid argv token")
    if any("{" in x or "}" in x for x in value if "{package}" not in x):
        raise CapsuleError("only {package} expansion is supported")
    if value[0] not in ("python3", "python", "node", "bash", "sh"):
        raise CapsuleError("program executable is not on the interpreter allowlist")
    return value


def validate_capsule(raw: Any, *, require_provenance: bool = False) -> dict[str, Any]:
    """Gate 1: parse, bound and check program-level dataflow before any execution."""
    if not isinstance(raw, dict):
        raise CapsuleError("capsule must be an object")
    if raw.get("schema_version") != 1 or raw.get("form") not in ("hybrid", "textual"):
        raise CapsuleError("unsupported capsule schema/form")
    for field in ("name", "role"):
        _ident(raw.get(field))
    desc = raw.get("description")
    if not isinstance(desc, str) or not desc.strip() or len(desc) > 2000:
        raise CapsuleError("capsule needs a description and applicability scope")
    bindings = raw.get("bindings")
    programs = raw.get("programs")
    steps = raw.get("steps")
    verification = raw.get("verification", [])
    if not isinstance(bindings, dict) or len(bindings) > 40:
        raise CapsuleError("invalid binding declarations")
    for key, instruction in bindings.items():
        _ident(key)
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 1500:
            raise CapsuleError("each binding needs a short live-value instruction")
    if not isinstance(programs, dict) or len(programs) > MAX_PROGRAMS:
        raise CapsuleError("invalid program declarations")
    if not isinstance(steps, list) or not steps or len(steps) > MAX_STEPS:
        raise CapsuleError("missing/too many steps")
    if not isinstance(verification, list) or len(verification) > MAX_STEPS:
        raise CapsuleError("invalid verification steps")
    if raw["form"] == "textual" and programs:
        raise CapsuleError("textual capsules cannot contain programs")
    sources_total = 0
    for name, program in programs.items():
        _ident(name)
        if not isinstance(program, dict):
            raise CapsuleError("invalid program")
        for field in ("command", "check"):
            _argv(program.get(field))
        for field in ("inputs", "outputs"):
            ids = program.get(field, [])
            if not isinstance(ids, list) or len(ids) > 24 or len(ids) != len(set(
                str(i) for i in ids
            )):
                raise CapsuleError("program bindings must be unique")
            if any(i not in bindings for i in ids):
                raise CapsuleError("program binding is undeclared")
        if set(program.get("inputs", [])) & set(program.get("outputs", [])):
            raise CapsuleError("program cannot redeclare input as output")
        if program.get("timeout_seconds", 15) not in range(1, 121):
            raise CapsuleError("invalid program timeout")
        sources = program.get("files")
        if not isinstance(sources, dict) or not sources or len(sources) > 12:
            raise CapsuleError("program must contain a bounded file package")
        for relative, source in sources.items():
            _relative_source(relative)
            if not isinstance(source, str):
                raise CapsuleError("source must be UTF-8 text")
            sources_total += len(source.encode("utf-8"))
            if sources_total > MAX_SOURCE_BYTES:
                raise CapsuleError("oversize program package")
    called: list[str] = []
    produced: set[str] = set()
    for index, step in enumerate([*steps, *verification]):
        if not isinstance(step, dict) or not isinstance(step.get("instruction"), str):
            raise CapsuleError("each step needs an instruction")
        if not step["instruction"].strip() or len(step["instruction"]) > 2000:
            raise CapsuleError("invalid instruction")
        pname = step.get("program")
        if pname is None:
            continue
        if pname not in programs or pname in called:
            raise CapsuleError("each declared program must occur exactly once")
        called.append(pname)
        program = programs[pname]
        # A binding may be externally supplied by the model. It cannot be
        # consumed before its producing program, however.
        later_outputs = {
            out for name, p in programs.items() if name not in called
            for out in p.get("outputs", [])
        }
        for value in program.get("inputs", []):
            if value in later_outputs and value not in produced:
                raise CapsuleError("a program consumes output before producer runs")
        for output in program.get("outputs", []):
            if output in produced:
                raise CapsuleError("output has more than one producer")
            produced.add(output)
    if set(called) != set(programs):
        raise CapsuleError("unused declared program")
    if require_provenance:
        for field in ("request_sha256", "workspace_sha256", "trace_sha256"):
            value = raw.get(field)
            if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
                raise CapsuleError(f"missing/invalid {field}")
    # Examples are needed only to qualify, never at warm execution.
    if "examples" in raw:
        examples = raw["examples"]
        if not isinstance(examples, dict) or set(examples) - set(bindings):
            raise CapsuleError("invalid qualification examples")
        if len(json.dumps(examples, ensure_ascii=False).encode()) > 32768:
            raise CapsuleError("qualification examples too large")
    if len(json.dumps(raw, ensure_ascii=False).encode()) > MAX_CAPSULE_BYTES:
        raise CapsuleError("oversize capsule")
    return raw


def public_capsule(candidate: dict[str, Any]) -> dict[str, Any]:
    """Strip all observed binding values and incidental trace information."""
    validate_capsule(candidate)
    return {k: v for k, v in candidate.items() if k not in ("examples", "trace", "request")}


def capsule_id(raw: dict[str, Any]) -> str:
    stable = public_capsule(raw)
    return digest(json.dumps(stable, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def input_bindings(raw: dict[str, Any]) -> set[str]:
    """Bindings not produced by any compiled program must come from the model."""
    produced = {name for p in raw["programs"].values() for name in p.get("outputs", [])}
    return {
        name for p in raw["programs"].values() for name in p.get("inputs", [])
        if name not in produced
    }
