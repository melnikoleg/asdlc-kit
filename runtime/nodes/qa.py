"""QA node — tests mapped to ACs → QA.md (qa-agent)."""

from __future__ import annotations

from ..config import Config
from ..state import PipelineState
from ._common import Runner, make_review_node


def _prompt(state: PipelineState, config: Config) -> str:
    issue = state["issue"]
    return (
        f"Issue: {issue}\n"
        f"Write and run tests for every acceptance criterion in "
        f"docs/{issue}/PRD.md. Capture real test output. Write docs/{issue}/QA.md "
        f"with an AC coverage map and a Verdict line. End with your JSON verdict."
    )


def make_qa_node(config: Config, runner: Runner):
    return make_review_node("qa", _prompt, config, runner)
