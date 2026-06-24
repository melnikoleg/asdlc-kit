"""Pipeline state — a typed, code-owned analogue of ``docs/{issue}/STATE.json``.

Unlike the native pipeline, where the LLM updates STATE.json "by good will",
every field here is written by graph node code. The state is mirrored back to
``docs/{issue}/STATE.json`` so the native ``/sdlc-status`` skill and the Stop
hook keep working unchanged.
"""

from __future__ import annotations

import json
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
    started_at: str
    updated_at: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_state(issue: str, requirement: str) -> PipelineState:
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
