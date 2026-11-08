"""Optional specification authoring and deterministic preflight."""
from __future__ import annotations

from typing import Any

from ..config import Config
from ..metrics import build_metric
from ..specifications import preflight
from ..state import PipelineState
from ._common import Runner, base_update


def make_specification_node(config: Config, runner: Runner):
    async def _node(state: PipelineState) -> dict[str, Any]:
        if not state.get("specs"):
            return {}
        issue = state["issue"]
        prompt = (
            f"Issue: {issue}. Before implementation, create executable, developer-visible "
            f"business specifications: docs/{issue}/SPECIFICATIONS.md and test files in "
            f"docs/{issue}/specs/. Read PRD.md, PLAN.md, TEST_STRATEGY.md, ADR.md if present. "
            f"Every PRD AC-N needs a `## AC-N` section with one-line Given:, When:, "
            f"Then: and unique `Spec: <command>` lines referring to a real test file in "
            f"docs/{issue}/specs/. Tests MUST contain meaningful assertions against the "
            f"observable behavior; use the existing stack's test framework. Do not "
            f"change implementation code. Tests are allowed to fail before implementation. "
            f"Do NOT edit held-out ACCEPTANCE.md. End with your JSON verdict."
        )
        result = await runner("specification", prompt, config)
        metric = build_metric("specification", result.status, result.usage, state.get("iteration", 0))
        update = base_update(state, "specification", config, metric=metric)
        update["artifacts"] = result.artifacts
        if result.status != "APPROVED":
            update["spec_error"] = f"specification-agent returned {result.status}"
        return update
    return _node


def make_spec_preflight_node(config: Config):
    async def _node(state: PipelineState) -> dict[str, Any]:
        if not state.get("specs"):
            return {}
        digest, error = preflight(config.docs_for(state["issue"]))
        error = state.get("spec_error") or error
        if error:
            digest = None
        update = base_update(state, "spec_preflight", config)
        update["spec_hash"] = digest
        update["spec_error"] = error
        return update
    return _node


def route_after_spec_preflight(state: PipelineState) -> str:
    return "escalate" if state.get("specs") and state.get("spec_error") else "acceptance"
