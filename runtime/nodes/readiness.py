"""Readiness node — terminal success: write PRODUCTION_READINESS.md."""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..state import PipelineState, now_iso
from ._common import base_update


def make_readiness_node(config: Config):
    async def _node(state: PipelineState) -> dict[str, Any]:
        issue = state["issue"]
        docs = config.docs_for(issue)
        docs.mkdir(parents=True, exist_ok=True)
        verdicts = state.get("verdicts", {})
        lines = [
            f"# Production Readiness — {issue}",
            "",
            f"- Generated: {now_iso()}",
            f"- Fix iterations: {state.get('iteration', 0)}",
            "",
            "## Verdicts",
            *[f"- {agent}: {status}" for agent, status in sorted(verdicts.items())],
            "",
            "## Validation Evidence",
            *_validation_lines(state),
            "",
            "## Artifacts",
            *[f"- {a}" for a in state.get("artifacts", [])],
            "",
            "Verdict: APPROVED",
            "",
        ]
        (docs / "PRODUCTION_READINESS.md").write_text("\n".join(lines), encoding="utf-8")

        update = base_update(state, "done", config)
        update["artifacts"] = [f"docs/{issue}/PRODUCTION_READINESS.md"]
        return update

    return _node


def _validation_lines(state: PipelineState) -> list[str]:
    out: list[str] = []
    for cmd, res in state.get("validation", {}).items():
        mark = "PASS" if res.get("passed") else "FAIL"
        out.append(f"- `{cmd}` → {mark} (exit {res.get('exit_code')})")
    return out or ["- (no validation commands found in PLAN.md)"]
