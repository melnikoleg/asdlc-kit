"""Deterministic validation gate node + routing.

Runs the PLAN.md validation commands, then the TEST_STRATEGY.md ``E2E:`` commands
against the booted app (real subprocess output). On pass →
parallel review fan-out. On fail → back to the developer in fix mode, unless
the iteration budget is exhausted, in which case → escalate.
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..state import PipelineState, now_iso, review_agents
from ..validation import all_passed, load_strategy, run_validation, run_with_app
from ._common import base_update


def make_validate_node(config: Config):
    async def _node(state: PipelineState) -> dict[str, Any]:
        issue = state["issue"]
        plan_path = config.docs_for(issue) / "PLAN.md"
        results = run_validation(plan_path, config.repo_root)
        if all_passed(results):
            # E2E runs only once the cheap checks pass, against a really-booted app.
            strategy = load_strategy(config.docs_for(issue) / "TEST_STRATEGY.md")
            if strategy.get("E2E"):
                results.update(run_with_app(strategy["E2E"], strategy, config.repo_root))
        passed = all_passed(results)

        update = base_update(state, "validate", config)
        update["validation"] = results
        if passed:
            return update

        # Validation failure is the developer's to fix; consume one iteration.
        update["iteration"] = state.get("iteration", 0) + 1
        update["failing_agents"] = ["developer"]
        update["updated_at"] = now_iso()
        return update

    return _node


def make_route_after_validate(config: Config):
    """Conditional edge: list of review nodes (parallel) | 'developer' | 'escalate'."""

    def _route(state: PipelineState):
        if all_passed(state.get("validation", {})):
            return list(review_agents(state))
        if state.get("iteration", 0) > config.max_iterations:
            return "escalate"
        return "developer"

    return _route
