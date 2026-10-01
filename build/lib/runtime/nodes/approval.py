"""Human approval gate — a real, durable pause via LangGraph ``interrupt()``.

Unlike the native "MANDATORY STOP" instruction (which the LLM can skip), this
physically halts the graph. Execution resumes only when the caller sends
``Command(resume="approve")`` (CLI ``--approve`` or the server approve route).
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..state import PipelineState
from ._common import base_update


def make_approval_node(config: Config):
    async def _node(state: PipelineState) -> dict[str, Any]:
        from langgraph.types import interrupt  # lazy import

        issue = state["issue"]
        verdicts = state.get("verdicts", {})
        adr = (config.docs_for(issue) / "ADR.md").is_file()
        decision = interrupt(
            {
                "issue": issue,
                "message": "PLAN READY — type 'approve' to implement or 'cancel' to stop.",
                "adr": adr,
                "verdicts": verdicts,
            }
        )
        approved = str(decision).strip().lower() == "approve"
        update = base_update(state, "implement" if approved else "escalated", config)
        update["approved"] = approved
        return update

    return _node


def route_after_approval(state: PipelineState) -> str:
    return "developer" if state.get("approved") else "escalate"
