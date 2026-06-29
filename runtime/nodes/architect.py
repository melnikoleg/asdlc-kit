"""Architect node — PRD.md + PLAN.md → ADR.md or skip (architect-agent)."""

from __future__ import annotations

from ..config import Config
from ..state import PipelineState
from ._common import Runner, make_generative_node


def _prompt(state: PipelineState, config: Config) -> str:
    issue = state["issue"]
    return (
        f"Issue: {issue}\n"
        f"Read docs/{issue}/PRD.md and docs/{issue}/PLAN.md. If the design has "
        f"non-trivial decisions, write docs/{issue}/ADR.md (BINDING constraints "
        f"for the developer). Otherwise state that no ADR is needed. "
        f"End with your JSON verdict."
    )


def make_architect_node(config: Config, runner: Runner):
    return make_generative_node("architect", "architect", _prompt, config, runner)
