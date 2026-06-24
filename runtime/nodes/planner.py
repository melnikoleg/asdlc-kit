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
        f"End with your JSON verdict."
    )


def make_planner_node(config: Config, runner: Runner):
    return make_generative_node("planner", "plan", _prompt, config, runner)
