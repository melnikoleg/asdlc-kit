"""Codebase node - scan an existing repo before planning (codebase-agent).

Greenfield repos skip the agent entirely: no LLM cost, no artifact.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..config import Config
from ..state import PipelineState
from ._common import Runner, base_update, make_generative_node


def is_greenfield(repo_root: Path) -> bool:
    # ponytail: heuristic - only hidden entries, docs/, top-level *.md and install.sh
    # count as empty. Misses odd layouts; switch to an explicit flag if it misfires.
    with os.scandir(repo_root) as entries:
        return all(
            e.name.startswith(".")
            or e.name == "docs"
            or e.name == "install.sh"
            or (e.is_file() and e.name.endswith(".md"))
            for e in entries
        )


def _prompt(state: PipelineState, config: Config) -> str:
    issue = state["issue"]
    return (
        f"Issue: {issue}\n"
        f"Requirement:\n{state['requirement']}\n\n"
        f"Scan the repo and write docs/{issue}/CODEBASE_CONTEXT.md: stack, "
        f"conventions, how the app is started and tested, and integration points "
        f"relevant to the requirement. End with your JSON verdict."
    )


def make_codebase_node(config: Config, runner: Runner):
    generative = make_generative_node("codebase", "codebase", _prompt, config, runner)

    async def _node(state: PipelineState):
        if is_greenfield(config.repo_root):
            return base_update(state, "codebase", config)
        return await generative(state)

    return _node
