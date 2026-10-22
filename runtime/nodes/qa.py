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
        f"docs/{issue}/PRD.md. Read docs/{issue}/TEST_STRATEGY.md and cover each "
        f"declared layer (Playwright for ui-e2e, an HTTP client for api-e2e, subprocess "
        f"for cli, unit otherwise). Run e2e tests with "
        f"`asdlc-e2e {issue} -- <command>` so the app is booted for them. "
        f"Capture real test output. Write docs/{issue}/QA.md "
        f"with an AC coverage map and a Verdict line. End with your JSON verdict."
    )


def make_qa_node(config: Config, runner: Runner):
    return make_review_node("qa", _prompt, config, runner)
