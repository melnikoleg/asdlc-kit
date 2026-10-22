"""Product node — requirement → PRD.md (product-agent)."""

from __future__ import annotations

from ..config import Config
from ..state import PipelineState
from ._common import Runner, make_generative_node


def _prompt(state: PipelineState, config: Config) -> str:
    issue = state["issue"]
    return (
        f"Issue: {issue}\n"
        f"Requirement:\n{state['requirement']}\n\n"
        f"Write docs/{issue}/PRD.md with binary-testable acceptance criteria, "
        f"following your agent definition and the project rules. "
        f"End with your JSON verdict."
    )


def make_product_node(config: Config, runner: Runner):
    return make_generative_node("product", "product", _prompt, config, runner)
