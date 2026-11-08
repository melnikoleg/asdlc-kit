"""Escalate node — terminal failure: write ESCALATION.md.

Reached when the fix-loop budget is exhausted or the human cancels at the
approval gate.
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..specifications import SPEC_TAMPERED, SPEC_INVALID
from ..state import PipelineState, now_iso
from ..validation import MISCONFIGURED, all_passed
from ._common import base_update


def make_escalate_node(config: Config):
    async def _node(state: PipelineState) -> dict[str, Any]:
        issue = state["issue"]
        docs = config.docs_for(issue)
        docs.mkdir(parents=True, exist_ok=True)
        cancelled = not state.get("approved", False) and state.get("iteration", 0) == 0
        acceptance = state.get("acceptance", {})
        held_out_failed = bool(acceptance) and not all_passed(acceptance)
        misconfigured = next(
            (r[MISCONFIGURED]["output"] for r in (state.get("validation", {}), acceptance) if MISCONFIGURED in r),
            None,
        )
        spec_error = state.get("spec_error")
        spec_validation = {**state.get("validation", {}), **acceptance}
        if spec_error:
            reason = f"Specification preflight or approval failed: {spec_error}"
        elif SPEC_TAMPERED in spec_validation:
            reason = f"Approved specification contract changed: {spec_validation[SPEC_TAMPERED]['output']}"
        elif SPEC_INVALID in spec_validation:
            reason = f"Specification runner misconfigured: {spec_validation[SPEC_INVALID]['output']}"
        elif cancelled:
            reason = "Human cancelled at the approval gate."
        elif misconfigured:
            reason = f"Gate misconfigured — {misconfigured}."
        elif held_out_failed:
            failed = [c for c, r in acceptance.items() if not r.get("passed")]
            reason = (
                "Held-out acceptance gate failed "
                f"({len(failed)}/{len(acceptance)} checks failing)."
            )
        else:
            reason = f"Fix-loop budget exhausted after {state.get('iteration', 0)} iteration(s)."
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
