"""Small, grounded replay capsules for repeated codebase-agent scans.

Inspired by SkillCache (arXiv:2611.10022). Not a general LLM tool-trace
compiler: only the completed codebase-agent's verified report is replayed as a
guarded, parameterized file-copy program. Semantic work and SDLC gates stay live.

The cache is opt-in and stores metadata only. No raw prompts, secrets, raw
tool traces or copies of project reports are written into the capsule.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from .state import validate_issue

VERSION = 1
KIND = "codebase-report"
MAX_FILES = 5000
MAX_BYTES = 64 * 1024 * 1024
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_REPORT_BYTES = 256 * 1024
EXCLUDED_DIRS = frozenset({
    ".git", ".asdlc", ".asdlc-venv", ".venv", "venv",
    "node_modules", "docs", "dist", "build", "coverage", ".next",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
    ".idea", ".vscode",
})


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def workspace_fingerprint(root: Path) -> str | None:
    """Hash the actual source bytes and skill instructions, not just git HEAD.

    Refuse overly large or symlinked workspaces rather than cache a partial
    snapshot. Ignore generated docs, checkpoints, virtualenvs and test caches.
    """
    root = root.resolve()
    h = hashlib.sha256(b"asdlc-source-v1\0")
    total = 0
    count = 0
    try:
        for current, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
            if any((Path(current) / d).is_symlink() for d in dirs):
                return None
            for name in sorted(files):
                path = Path(current) / name
                if path.is_symlink():
                    return None
                # Temporary checkpoint files may be in the repo root in tests.
                if name == ".cp.sqlite" or name.startswith(".cp.sqlite-"):
                    continue
                if not path.is_file():
                    continue
                size = path.stat().st_size
                total += size
                count += 1
                if size > MAX_FILE_BYTES or total > MAX_BYTES or count > MAX_FILES:
                    return None
                rel = path.relative_to(root).as_posix().encode("utf-8")
                h.update(len(rel).to_bytes(4, "big"))
                h.update(rel)
                h.update(hashlib.sha256(path.read_bytes()).digest())
    except (OSError, UnicodeError, ValueError):
        return None
    return h.hexdigest()


def _key(requirement: str, fingerprint: str) -> str:
    return _hash_bytes(
        b"codebase-capsule-v1\0" + requirement.encode("utf-8") +
        b"\0" + fingerprint.encode("ascii")
    )


def _capsule_path(root: Path, requirement: str, fingerprint: str) -> Path:
    return root / ".asdlc" / "skill-cache" / (_key(requirement, fingerprint) + ".json")


def _report(root: Path, issue: str) -> Path:
    validate_issue(issue)
    return root / "docs" / issue / "CODEBASE_CONTEXT.md"


def _read_report(path: Path) -> bytes | None:
    if path.is_symlink() or path.parent.is_symlink() or path.parent.parent.is_symlink():
        return None
    try:
        if not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
            return None
        data = path.read_bytes()
        if len(data) < 32 or not data.strip():
            return None
        data.decode("utf-8")  # reject non-text / corrupted reports
        return data
    except (OSError, UnicodeError):
        return None


def _render_report(observed: bytes, source_issue: str, new_issue: str) -> bytes:
    """Lift only the issue-local docs path into a live binding."""
    old = f"docs/{source_issue}/".encode("utf-8")
    new = f"docs/{new_issue}/".encode("utf-8")
    return observed.replace(old, new)


def qualify_and_record(root: Path, issue: str, requirement: str, fingerprint: str) -> bool:
    """Compile an actual successful report and qualify the copy-program replay.

    Caller must verify the agent returned APPROVED and its workspace stayed
    unchanged. A failed qualification never creates a capsule.
    """
    if workspace_fingerprint(root) != fingerprint:
        return False
    original = _read_report(_report(root, issue))
    if original is None:
        return False
    # Program check + replay qualification: run the exact replay program in a
    # fresh temporary directory, then byte-compare its observed output.
    try:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "CODEBASE_CONTEXT.md"
            out.write_bytes(_render_report(original, issue, issue))
            if _read_report(out) != original:
                return False
        capsule: dict[str, Any] = {
            "version": VERSION,
            "kind": KIND,
            "key": _key(requirement, fingerprint),
            "request_sha256": _hash_bytes(requirement.encode("utf-8")),
            "workspace_sha256": fingerprint,
            "source_issue": validate_issue(issue),
            "report_sha256": _hash_bytes(original),
            "program": "copy-codebase-report-with-issue-binding",
            "qualified": True,
        }
        dest = _capsule_path(root, requirement, fingerprint)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            tmp.write_text(json.dumps(capsule, indent=2) + "\n", encoding="utf-8")
            os.chmod(tmp, 0o600)
            os.replace(tmp, dest)
        finally:
            tmp.unlink(missing_ok=True)
        return True
    except (OSError, ValueError):
        return False


def replay_codebase(root: Path, issue: str, requirement: str, fingerprint: str) -> bool:
    """Use the qualified fast path, or return False for cold-model fallback.

    Never executes cached shell commands and never bypasses the human or
    acceptance gates. A cache miss/error cannot become an APPROVED verdict.
    """
    try:
        dest = _report(root, issue)
        if dest.exists() or dest.is_symlink():
            return False
        capsule_path = _capsule_path(root, requirement, fingerprint)
        if capsule_path.is_symlink() or not capsule_path.is_file():
            return False
        if capsule_path.stat().st_size > 4096:
            return False
        capsule = json.loads(capsule_path.read_text(encoding="utf-8"))
        if not isinstance(capsule, dict) or not capsule.get("qualified"):
            return False
        if (
            capsule.get("version") != VERSION
            or capsule.get("kind") != KIND
            or capsule.get("key") != _key(requirement, fingerprint)
            or capsule.get("request_sha256") != _hash_bytes(requirement.encode("utf-8"))
            or capsule.get("workspace_sha256") != fingerprint
            or capsule.get("program") != "copy-codebase-report-with-issue-binding"
            or workspace_fingerprint(root) != fingerprint
        ):
            return False
        source_issue = validate_issue(capsule["source_issue"])
        original = _read_report(_report(root, source_issue))
        if original is None or _hash_bytes(original) != capsule.get("report_sha256"):
            return False
        rendered = _render_report(original, source_issue, issue)
        if len(rendered) > MAX_REPORT_BYTES or not rendered.strip():
            return False
        if dest.parent.is_symlink() or dest.parent.parent.is_symlink():
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation: do not overwrite an artifact created concurrently.
        with dest.open("xb") as stream:
            stream.write(rendered)
        if _read_report(dest) != rendered:
            dest.unlink(missing_ok=True)
            return False
        return True
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return False
