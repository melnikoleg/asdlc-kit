"""Held-out acceptance gate — author up-front, grade at the end.

The article's lesson: measure quality with a suite the implementer never sees.
Here a single writer (acceptance-agent) authors ``ACCEPTANCE.md`` during planning,
the developer is told not to read it, and a deterministic subprocess grades it
right before sign-off. Because the suite is never fed back into a developer fix
prompt, it stays an independent objective measure rather than a target to tune
to — a held-out failure escalates to a human instead of looping.

Race-free: one writer for ACCEPTANCE.md, and the grader is plain code, not an
agent writing its own file.
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..metrics import build_metric
from ..state import PipelineState
from ..validation import all_passed, run_validation
from ._common import Runner, base_update

ACCEPTANCE_FILE = "ACCEPTANCE.md"


def _author_prompt(issue: str) -> str:
    return (
        f"Issue: {issue}\n"
        f"Author a HELD-OUT acceptance suite for the criteria in "
        f"docs/{issue}/PRD.md. For each acceptance criterion, write ONE runnable "
        f"shell check as a line `Acceptance: <command>` in "
        f"docs/{issue}/{ACCEPTANCE_FILE} (exit 0 = the criterion holds). "
        f"This suite is graded automatically and the developer must NOT see it: "
        f"do not place these commands in PLAN.md, IMPLEMENTATION.md, or any code. "
        f"End with your JSON verdict."
    )


def make_acceptance_author_node(config: Config, runner: Runner):
    """Generative node: write the held-out suite before implementation."""

    async def _node(state: PipelineState) -> dict[str, Any]:
        issue = state["issue"]
        result = await runner("acceptance", _author_prompt(issue), config)
        metric = build_metric("acceptance", result.status, result.usage, state.get("iteration", 0))
        # Still the planning phase; does NOT set a verdict (would pollute the
        # review fan-out routing for the qa/reviewer nodes).
        update = base_update(state, "acceptance", config, metric=metric)
        update["artifacts"] = result.artifacts
        return update

    return _node


def make_acceptance_gate_node(config: Config):
    """Deterministic node: run the held-out suite once review has approved."""

    async def _node(state: PipelineState) -> dict[str, Any]:
        acc_path = config.docs_for(state["issue"]) / ACCEPTANCE_FILE
        results = run_validation(acc_path, config.repo_root)
        update = base_update(state, "review", config)
        update["acceptance"] = results
        return update

    return _node


def make_route_after_acceptance(config: Config):
    """Conditional edge: 'readiness' if the held-out suite passes, else 'escalate'."""

    def _route(state: PipelineState) -> str:
        return "readiness" if all_passed(state.get("acceptance", {})) else "escalate"

    return _route
