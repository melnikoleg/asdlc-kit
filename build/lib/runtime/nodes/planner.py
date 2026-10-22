"""Planner node — PRD.md → PLAN.md (planner-agent)."""

from __future__ import annotations

from ..config import Config
from ..state import PipelineState
from ._common import Runner, make_generative_node


def _prompt(state: PipelineState, config: Config) -> str:
    issue = state["issue"]
    return (
        f"Issue: {issue}\n"
        f"Read docs/{issue}/PRD.md and decompose it into docs/{issue}/PLAN.md. "
        f"Every phase MUST include a runnable 'Validation:' shell command. "
        f"Also write docs/{issue}/TEST_STRATEGY.md (read docs/{issue}/CODEBASE_CONTEXT.md "
        f"if present) as `Key: value` lines: Stack, Type (web-ui|http-api|cli|library), "
        f"Layers (subset of unit, integration, api-e2e, ui-e2e), Tooling, and for "
        f"web-ui/http-api a foreground `Start:` command on a fixed port in 8700-8799, a "
        f"`Healthcheck:` URL, and an `E2E:` command. Include a PLAN.md phase that "
        f"installs the e2e tooling and one that writes the e2e tests. "
        f"End with your JSON verdict."
    )


def make_planner_node(config: Config, runner: Runner):
    return make_generative_node("planner", "plan", _prompt, config, runner)
