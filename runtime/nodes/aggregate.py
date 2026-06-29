"""Aggregate node — collect review verdicts, drive the fix-loop.

Owns the phase transition and STATE.json mirror after the parallel review
fan-out (the review nodes deliberately don't, to avoid concurrent writes).
The fix-loop counter lives here and in the validate node; both escalate once
the iteration budget is exceeded — a hard, code-enforced limit.
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..state import REVIEW_AGENTS, PipelineState
from ._common import base_update


def _failing(state: PipelineState) -> list[str]:
    verdicts = state.get("verdicts", {})
    return [a for a in REVIEW_AGENTS if verdicts.get(a) != "APPROVED"]


def make_aggregate_node(config: Config):
    async def _node(state: PipelineState) -> dict[str, Any]:
        failing = _failing(state)
        if not failing:
            update = base_update(state, "review", config)
            update["failing_agents"] = []
            return update

        new_iter = state.get("iteration", 0) + 1
        escalating = new_iter > config.max_iterations
        update = base_update(state, "escalated" if escalating else "fix", config)
        update["failing_agents"] = failing
        update["iteration"] = new_iter
        return update

    return _node


def make_route_after_aggregate(config: Config):
    """Conditional edge: 'readiness' | 'developer' | 'escalate'."""

    def _route(state: PipelineState) -> str:
        if not state.get("failing_agents"):
            return "readiness"
        if state.get("iteration", 0) > config.max_iterations:
            return "escalate"
        return "developer"

    return _route
