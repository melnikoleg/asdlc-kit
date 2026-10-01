"""DevOps node — Dockerfile + CI + DEPLOY.md (devops-agent)."""

from __future__ import annotations

from ..config import Config
from ..state import PipelineState
from ._common import Runner, make_review_node


def _prompt(state: PipelineState, config: Config) -> str:
    issue = state["issue"]
    return (
        f"Issue: {issue}\n"
        f"Produce deployment artifacts: multi-stage non-root Dockerfile, "
        f"docker-compose, GitHub Actions CI, and docs/{issue}/DEPLOY.md runbook "
        f"with a Verdict line. Review env-var safety and health checks. "
        f"End with your JSON verdict."
    )


def make_devops_node(config: Config, runner: Runner):
    return make_review_node("devops", _prompt, config, runner)
