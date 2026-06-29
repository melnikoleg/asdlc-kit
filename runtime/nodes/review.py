"""Reviewer node — adversarial code review → REVIEW.md (reviewer-agent)."""

from __future__ import annotations

from ..config import Config
from ..state import PipelineState
from ._common import Runner, make_review_node


def _prompt(state: PipelineState, config: Config) -> str:
    issue = state["issue"]
    return (
        f"Issue: {issue}\n"
        f"Adversarially review the implementation. Read docs/{issue}/PRD.md, "
        f"docs/{issue}/ADR.md, docs/{issue}/IMPLEMENTATION.md and the changed "
        f"source files. Check every PRD acceptance criterion, ADR constraints, "
        f"and OWASP Top 10. Write docs/{issue}/REVIEW.md with a Verdict line. "
        f"End with your JSON verdict."
    )


def make_reviewer_node(config: Config, runner: Runner):
    return make_review_node("reviewer", _prompt, config, runner)
