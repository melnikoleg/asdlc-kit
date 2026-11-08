"""Executable business specifications: contract lint, immutability, and execution.

Specs live in docs/<issue>/SPECIFICATIONS.md.  Each ``## AC-N`` section
contains Given:, When:, Then:, and one or more ``Spec:`` shell commands.
Tests themselves live under docs/<issue>/specs/ and are authored BEFORE
implementation. Existing test runners (pytest, jest, etc.) execute them.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .validation import load_strategy, run_with_app

_AC = re.compile(r"\bAC-\d+\b")
_HEADING = re.compile(r"^##\s+(AC-\d+)\b", re.MULTILINE)
_FIELD = re.compile(r"^\s*(Given|When|Then|Spec):[ \t]*(.+?)\s*$", re.MULTILINE)
SPEC_TAMPERED = "SPEC_TAMPERED"
SPEC_INVALID = "SPEC_INVALID"


@dataclass(frozen=True)
class Scenario:
    ac_id: str
    given: str
    when: str
    then: str
    commands: tuple[str, ...]


class SpecificationError(ValueError):
    pass


def _files(docs: Path) -> list[Path]:
    prd = docs / "PRD.md"
    spec = docs / "SPECIFICATIONS.md"
    root = docs / "specs"
    if not prd.is_file() or not spec.is_file():
        raise SpecificationError("PRD.md and SPECIFICATIONS.md are required")
    if not root.is_dir() or root.is_symlink():
        raise SpecificationError("specs/ must contain the executable test sources")
    # Compiled/test-runner output is not part of the approved source contract.
    ignored_dirs = {"__pycache__", ".pytest_cache", "node_modules", ".cache", ".mypy_cache"}
    test_files = []
    for p in root.rglob("*"):
        if p.is_symlink():
            raise SpecificationError(f"symlinks are not allowed in specs/: {p}")
        if p.is_file() and not set(p.relative_to(root).parts).intersection(ignored_dirs) \
                and p.suffix not in {".pyc", ".pyo"}:
            test_files.append(p)
    test_files.sort()
    if not test_files:
        raise SpecificationError("specs/ is empty")
    for p in (prd, spec, *test_files):
        if p.is_symlink() or any(parent.is_symlink() for parent in p.parents if parent != docs.parent):
            raise SpecificationError(f"symlinks are not allowed in the specification contract: {p}")
    return [prd, spec, *test_files]


def load_specifications(docs: Path) -> list[Scenario]:
    """Fail closed on missing/mismatched ACs, placeholders and missing tests."""
    files = _files(docs)
    prd_text, spec_text = (p.read_text(encoding="utf-8") for p in files[:2])
    criteria = set(_AC.findall(prd_text))
    if not criteria:
        raise SpecificationError("PRD.md must contain explicit AC-1, AC-2, ... identifiers")
    matches = list(_HEADING.finditer(spec_text))
    if not matches:
        raise SpecificationError("SPECIFICATIONS.md must have ## AC-N headings")
    seen: set[str] = set()
    result: list[Scenario] = []
    commands_seen: set[str] = set()
    prefix = f"docs/{docs.name}/specs/"
    for i, heading in enumerate(matches):
        ac_id = heading.group(1)
        if ac_id in seen:
            raise SpecificationError(f"duplicate section: {ac_id}")
        seen.add(ac_id)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(spec_text)
        section = spec_text[heading.end():end]
        fields: dict[str, list[str]] = {}
        for key, value in _FIELD.findall(section):
            fields.setdefault(key, []).append(value.strip().strip('`').strip())
        if any(not fields.get(k) or not all(fields[k]) for k in ("Given", "When", "Then", "Spec")):
            raise SpecificationError(f"{ac_id}: Given, When, Then and Spec are mandatory")
        for k in ("Given", "When", "Then"):
            if len(fields[k]) != 1:
                raise SpecificationError(f"{ac_id}: expected exactly one {k} line")
        for command in fields["Spec"]:
            if prefix not in command or command in commands_seen:
                raise SpecificationError(f"{ac_id}: Spec command must uniquely target {prefix}")
            if any(op in command for op in (";", "&&", "||", "|", "`", "$(")):
                raise SpecificationError(f"{ac_id}: Spec command must be a single test-runner invocation")
            commands_seen.add(command)
            # At least one source file must actually be named in the command.
            if not any(str(p.as_posix()).endswith(command_fragment) for p in files[2:]
                       for command_fragment in command.split() if command_fragment.startswith(prefix)):
                raise SpecificationError(f"{ac_id}: Spec command does not reference an existing spec file")
        result.append(Scenario(ac_id, fields["Given"][0], fields["When"][0],
                               fields["Then"][0], tuple(fields["Spec"])))
    if criteria != seen:
        missing = sorted(criteria - seen)
        extra = sorted(seen - criteria)
        raise SpecificationError(f"AC coverage mismatch: missing={missing}, extra={extra}")
    return result


def contract_sha256(docs: Path) -> str:
    """Bind the approved PRD, spec document and executable test bytes."""
    paths = _files(docs)
    digest = hashlib.sha256()
    for path in paths:
        rel = path.relative_to(docs).as_posix()
        payload = path.read_bytes()
        digest.update(rel.encode("utf-8") + b"\0" + str(len(payload)).encode() + b"\0")
        digest.update(payload)
    return digest.hexdigest()


def preflight(docs: Path) -> tuple[str | None, str | None]:
    try:
        load_specifications(docs)
        return contract_sha256(docs), None
    except (SpecificationError, OSError, UnicodeError) as exc:
        return None, str(exc)


def run_specifications(docs: Path, repo_root: Path, approved_sha: str | None) -> dict[str, dict[str, Any]]:
    """Only execute unchanged, approved specs; no vacuous success."""
    current, error = preflight(docs)
    if error or not approved_sha or current != approved_sha:
        return {
            SPEC_TAMPERED: {
                "command": SPEC_TAMPERED,
                "exit_code": -1,
                "output": error or "specification contract changed after human approval",
                "passed": False,
            }
        }
    scenarios = load_specifications(docs)
    commands = [cmd for spec in scenarios for cmd in spec.commands]
    strategy = load_strategy(docs / "TEST_STRATEGY.md")
    raw = run_with_app(commands, strategy, repo_root)
    if set(raw) != set(commands):
        # Start/healthcheck failure is reported as a single failed record.
        return {
            SPEC_INVALID: {
                "command": SPEC_INVALID, "exit_code": -1,
                "output": "; ".join(str(r.get("output", "")) for r in raw.values()),
                "passed": False,
            }
        }
    return {f"Spec {spec.ac_id}: {cmd}": raw[cmd]
            for spec in scenarios for cmd in spec.commands}
