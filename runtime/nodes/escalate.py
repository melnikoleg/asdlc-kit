"""Escalate node — terminal failure: write ESCALATION.md.

Reached when the fix-loop budget is exhausted or the human cancels at the
approval gate.
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..state import PipelineState, now_iso
from ._common import base_update


def make_escalate_node(config: Config):
    async def _node(state: PipelineState) -> dict[str, Any]:
        issue = state["issue"]
        docs = config.docs_for(issue)
        docs.mkdir(parents=True, exist_ok=True)
        cancelled = not state.get("approved", False) and state.get("iteration", 0) == 0
        reason = (
            "Human cancelled at the approval gate."
            if cancelled
            else f"Fix-loop budget exhausted after {state.get('iteration', 0)} iteration(s)."
        )
        lines = [
            f"# Escalation — {issue}",
            "",
            f"- Generated: {now_iso()}",
            f"- Reason: {reason}",
            f"- Failing agents: {', '.join(state.get('failing_agents', [])) or 'none'}",
            "",
            "## Last Verdicts",
            *[f"- {a}: {s}" for a, s in sorted(state.get("verdicts", {}).items())],
            "",
            "Verdict: NEEDS_FIX",
            "",
        ]
        (docs / "ESCALATION.md").write_text("\n".join(lines), encoding="utf-8")

        update = base_update(state, "escalated", config)
        update["artifacts"] = [f"docs/{issue}/ESCALATION.md"]
        return update

    return _node
