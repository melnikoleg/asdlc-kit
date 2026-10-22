"""Reviewer node — adversarial code review → REVIEW.md (reviewer-agent).

Clean-context review: the reviewer judges the diff and the recorded validation
results, never the developer's own IMPLEMENTATION.md narrative.
"""

from __future__ import annotations

from ..config import Config
from ..state import PipelineState
from ._common import Runner, make_review_node


def _prompt(state: PipelineState, config: Config) -> str:
    issue = state["issue"]
    base = state.get("base_sha")
    how_to_diff = (
        f"Run `git diff {base}` and `git status --short` to see "
        f"exactly what changed since the pre-implementation commit"
        if base
        else "Run `git status --short` and `git diff` to see exactly what changed"
    )
    validation = "".join(
        f"\n- `{cmd}` → {'PASS' if r.get('passed') else 'FAIL'} (exit {r.get('exit_code')})"
        for cmd, r in state.get("validation", {}).items()
    )
    return (
        f"Issue: {issue}\n"
        f"Adversarially review the implementation against docs/{issue}/PRD.md and "
        f"docs/{issue}/ADR.md. {how_to_diff}. Judge only that diff and the validation "
        f"results recorded below. Do NOT read docs/{issue}/IMPLEMENTATION.md: the "
        f"developer's own account is not evidence.\n"
        f"Validation results:{validation or ' (none)'}\n"
        f"Check every PRD acceptance criterion, ADR constraints, and OWASP Top 10. "
        f"Write docs/{issue}/REVIEW.md with a Verdict line. End with your JSON verdict."
    )


def make_reviewer_node(config: Config, runner: Runner):
    return make_review_node("reviewer", _prompt, config, runner)
