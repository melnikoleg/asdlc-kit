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
import re
import shutil
import stat
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
    "node_modules", "dist", "build", "coverage", ".next",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
    ".idea", ".vscode",
})
# Skip only per-issue files produced by the SDLC. Source documentation such as
# docs/architecture.md and docs/design/*.md still invalidates the capsule.
GENERATED_DOC_MARKERS = frozenset({
    "STATE.json", "CODEBASE_CONTEXT.md", "PRD.md", "PLAN.md",
    "TEST_STRATEGY.md", "SPECIFICATIONS.md", "ACCEPTANCE.md",
    "IMPLEMENTATION.md", "REVIEW.md", "QA.md", "METRICS.json",
    "PRODUCTION_READINESS.md", "ESCALATION.md",
})


ROLE_INPUTS = {
    "product": ("CODEBASE_CONTEXT.md",),
    "planner": ("PRD.md", "CODEBASE_CONTEXT.md"),
    "architect": ("PRD.md", "PLAN.md", "CODEBASE_CONTEXT.md"),
    "specification": ("PRD.md", "PLAN.md", "TEST_STRATEGY.md", "ADR.md"),
    "developer": ("PRD.md", "PLAN.md", "ADR.md", "CODEBASE_CONTEXT.md", "TEST_STRATEGY.md",
                  "SPECIFICATIONS.md", "specs", "REVIEW.md", "QA.md"),
    "devops": ("PRD.md", "IMPLEMENTATION.md"),
}


# Cacheable roles never consume held-out checks or runtime state mirrors.
_excluded_names = shutil.ignore_patterns(
    *EXCLUDED_DIRS, ".env", ".env.*", "*.pem", "*.key", "secrets.*",
    ".aws", ".ssh", ".kube", ".docker", ".netrc", ".npmrc", ".pypirc",
    "id_rsa*", "id_ed25519*", "credentials", "kubeconfig", ".git-credentials",
    ".cp.sqlite*", "ACCEPTANCE.md", "STATE.json", "METRICS.json",
    "PRODUCTION_READINESS.md", "ESCALATION.md", ".sdlc-audit.log",
)


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def workspace_fingerprint(root: Path, *, snapshot: Path | None = None,
                          role: str | None = None, session: Path | None = None) -> str | None:
    """Hash the actual source bytes and skill instructions, not just git HEAD.

    Refuse overly large or symlinked workspaces rather than cache a partial
    snapshot. When requested, copy the bytes hashed plus role-visible issue inputs.
    """
    if not root.is_dir() or root.is_symlink():
        return None
    root = root.resolve()
    h = hashlib.sha256(b"asdlc-source-v1\0")
    total = 0
    count = 0
    try:
        issue_dirs: set[str] = set()

        def raise_walk_error(error: OSError) -> None:
            raise error

        for current, dirs, files in os.walk(root, onerror=raise_walk_error):
            relative = Path(current).relative_to(root)
            ignored = _excluded_names(current, dirs + files)
            if session is not None and Path(current) == session.parent:
                # Python callers can store the executor checkpoint inside the source tree.
                ignored.update(session.name + suffix for suffix in ("", ".lock", ".lock-journal", ".outputs"))
                ignored.update(d for d in dirs if re.fullmatch(
                    re.escape(session.name) + r"\.outputs\.[0-9a-f]{32}", d
                ))
            dirs[:] = sorted(set(dirs) - ignored)
            if any((Path(current) / d).is_symlink() for d in dirs):
                return None
            if relative.parts == ("docs",):
                issue_dirs = {d for d in dirs if any(
                    (Path(current) / d / marker).exists() for marker in GENERATED_DOC_MARKERS
                )}
                if snapshot is None:
                    dirs[:] = [d for d in dirs if d not in issue_dirs]
            issue_doc = (len(relative.parts) >= 2 and relative.parts[0] == "docs"
                         and relative.parts[1] in issue_dirs)
            if issue_doc and len(relative.parts) == 2 and role is not None:
                inputs = ROLE_INPUTS.get(role, ())
                dirs[:] = [d for d in dirs if d in inputs]
                files = [f for f in files if f in inputs]
            if snapshot is not None:
                (snapshot / relative).mkdir(parents=True, exist_ok=True)
            for name in sorted(set(files) - ignored):
                path = Path(current) / name
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode):
                    return None
                count += 1
                total += info.st_size
                if info.st_size > MAX_FILE_BYTES or total > MAX_BYTES or count > MAX_FILES:
                    return None
                with path.open("rb") as stream:
                    if not os.path.samestat(info, os.fstat(stream.fileno())):
                        return None
                    data = stream.read(info.st_size + 1)
                if len(data) != info.st_size:
                    return None
                if snapshot is not None:
                    dest = snapshot / relative / name
                    dest.write_bytes(data)
                    dest.chmod(0o755 if info.st_mode & 0o111 else 0o644)
                if not issue_doc:
                    rel = (relative / name).as_posix().encode("utf-8")
                    h.update(len(rel).to_bytes(4, "big"))
                    h.update(rel)
                    h.update(hashlib.sha256(data).digest())
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
    # Only a docs path can be rebound safely. A bare issue identifier in
    # the report could leak stale issue-specific guidance into the next task.
    bound = _render_report(original, issue, "__asdlc_issue_binding__")
    if issue.encode("utf-8") in bound:
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
