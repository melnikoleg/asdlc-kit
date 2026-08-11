"""Developer node — implements code (normal mode) or fixes blocking issues (fix mode).

Mode is decided by ``iteration``: iteration 0 is the first implementation pass;
any later entry (re-entered from the fix-loop) is scoped to the blocking issues
recorded by the review agents.
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..metrics import build_metric
from ..state import PipelineState
from ._common import Runner, base_update


_HELD_OUT_NOTE = (
    "Do NOT read docs/{issue}/ACCEPTANCE.md — it is a held-out acceptance suite "
    "graded independently. Implement to the PRD criteria, not to those tests."
)


def _normal_prompt(issue: str) -> str:
    return (
        f"Issue: {issue}\n"
        f"Implement docs/{issue}/PLAN.md following docs/{issue}/ADR.md constraints "
        f"and docs/{issue}/PRD.md acceptance criteria. Write code files and "
        f"docs/{issue}/IMPLEMENTATION.md. {_HELD_OUT_NOTE.format(issue=issue)} "
        f"End with your JSON verdict."
    )


def _fix_prompt(issue: str, failing: list[str]) -> str:
    sources = " and ".join(
        f"docs/{issue}/{name}.md"
        for name in ("REVIEW", "QA")
    )
    return (
        f"Issue: {issue}\n"
        f"FIX MODE. Failing agents: {', '.join(failing) or 'unknown'}.\n"
        f"Read {sources} and address ONLY the blocking issues listed there. "
        f"Do not change unrelated files. Re-run validation. "
        f"{_HELD_OUT_NOTE.format(issue=issue)} "
        f"Update docs/{issue}/IMPLEMENTATION.md. End with your JSON verdict."
    )


def make_developer_node(config: Config, runner: Runner):
    async def _node(state: PipelineState) -> dict[str, Any]:
        issue = state["issue"]
        fix_mode = state.get("iteration", 0) > 0
        if fix_mode:
            prompt = _fix_prompt(issue, state.get("failing_agents", []))
            phase = "fix"
        else:
            prompt = _normal_prompt(issue)
            phase = "implement"
        result = await runner("developer", prompt, config)
        metric = build_metric("developer", result.status, result.usage, state.get("iteration", 0))
        update = base_update(state, phase, config, metric=metric)
        update["verdicts"] = {"developer": result.status}
        update["artifacts"] = result.artifacts  # reducer union-appends
        return update

    return _node
