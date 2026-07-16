"""Pipeline state — a typed, code-owned analogue of ``docs/{issue}/STATE.json``.

Unlike the native pipeline, where the LLM updates STATE.json "by good will",
every field here is written by graph node code. The state is mirrored back to
``docs/{issue}/STATE.json`` so the native ``/sdlc-status`` skill and the Stop
hook keep working unchanged.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

Phase = Literal[
    "product",
    "plan",
    "architect",
    "awaiting_approval",
    "implement",
    "validate",
    "review",
    "fix",
    "done",
    "escalated",
]

# Agents that run in the parallel review fan-out.
REVIEW_AGENTS = ("reviewer", "qa", "devops")

# An issue name becomes both the durable thread id and a path segment
# (``docs/{issue}/``). Restricting it to a kebab/snake slug keeps it from
# escaping the docs directory (path traversal) or colliding across pipelines.
_ISSUE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")


def validate_issue(issue: str) -> str:
    """Return ``issue`` if it is a safe slug, else raise ``ValueError``.

    This is a trust boundary: the issue arrives from the CLI/HTTP caller and is
    used unescaped as a filesystem path segment, so it must never contain path
    separators, ``..``, or whitespace.
    """
    if not isinstance(issue, str) or not _ISSUE_RE.match(issue) or ".." in issue:
        raise ValueError(
            "issue must be a slug matching [a-z0-9._-] (1-100 chars), "
            f"with no path separators or '..'; got {issue!r}"
        )
    return issue


def _merge_dict(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Reducer: shallow-merge dict updates from concurrent (fan-out) nodes."""
    merged = dict(left)
    merged.update(right)
    return merged


def _append_unique(left: list[str], right: list[str]) -> list[str]:
    """Reducer: union-append, preserving order. Safe for concurrent fan-out writes."""
    merged = list(left)
    for item in right:
        if item not in merged:
            merged.append(item)
    return merged


def _concat(left: list[Any], right: list[Any]) -> list[Any]:
    """Reducer: append all (duplicates kept). Each agent run is its own metric,
    so re-runs across fix iterations accumulate rather than de-duplicating."""
    return list(left) + list(right)


class PipelineState(TypedDict, total=False):
    issue: str
    requirement: str
    phase: Phase
    iteration: int
    approved: bool
    failing_agents: list[str]
    artifacts: Annotated[list[str], _append_unique]
    # verdicts and validation are written concurrently by fan-out nodes,
    # so they use a merge reducer to avoid clobbering each other.
    verdicts: Annotated[dict[str, str], _merge_dict]
    validation: Annotated[dict[str, dict[str, Any]], _merge_dict]
    # One record per agent run (token/cost/timing), accumulated across the
    # pipeline and fix-loop; mirrored to docs/{issue}/METRICS.json for the dashboard.
    metrics: Annotated[list[dict[str, Any]], _concat]
    started_at: str
    updated_at: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_state(issue: str, requirement: str) -> PipelineState:
    issue = validate_issue(issue)
    if not requirement or not requirement.strip():
        raise ValueError("requirement must be a non-empty string")
    ts = now_iso()
    return PipelineState(
        issue=issue,
        requirement=requirement,
        phase="product",
        iteration=0,
        approved=False,
        failing_agents=[],
        artifacts=[],
        verdicts={},
        validation={},
        metrics=[],
        started_at=ts,
        updated_at=ts,
    )


# Fields mirrored into STATE.json (must stay compatible with the native schema
# in .claude/sdlc/templates/STATE_TEMPLATE.json).
_STATE_JSON_FIELDS = (
    "issue",
    "phase",
    "iteration",
    "failing_agents",
    "artifacts",
    "started_at",
    "updated_at",
)


def mirror_to_disk(state: PipelineState, docs_dir: Path) -> Path:
    """Write the native-compatible STATE.json for an issue."""
    docs_dir.mkdir(parents=True, exist_ok=True)
    payload = {k: state.get(k) for k in _STATE_JSON_FIELDS}
    payload["updated_at"] = now_iso()
    target = docs_dir / "STATE.json"
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target
