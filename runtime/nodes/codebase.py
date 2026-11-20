"""Codebase node - scan an existing repo before planning (codebase-agent).

Greenfield repos skip the agent entirely: no LLM cost, no artifact.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..config import Config
from ..skill_cache import qualify_and_record, replay_codebase, workspace_fingerprint
from ..state import PipelineState, mirror_to_disk
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
            update = base_update(state, "codebase", config)
            if state.get("skill_cache"):
                update["skill_cache_status"] = "greenfield"
                mirror_to_disk({**state, **update}, config.docs_for(state["issue"]))
            return update
        if not state.get("skill_cache"):
            return await generative(state)

        # Observe -> qualify -> replay, with exact-request and workspace guards.
        # A cache miss always delegates to the source agent; it never implies
        # an APPROVED verdict by itself.
        fingerprint = workspace_fingerprint(config.repo_root)
        issue = state["issue"]
        if fingerprint and replay_codebase(
            config.repo_root, issue, state["requirement"], fingerprint
        ):
            update = base_update(state, "codebase", config)
            update["verdicts"] = {"codebase": "APPROVED"}
            update["artifacts"] = [f"docs/{issue}/CODEBASE_CONTEXT.md"]
            update["skill_cache_status"] = "hit"
            mirror_to_disk({**state, **update}, config.docs_for(issue))
            return update

        update = await generative(state)
        recorded = bool(
            fingerprint
            and update.get("verdicts", {}).get("codebase") == "APPROVED"
            and qualify_and_record(config.repo_root, issue, state["requirement"], fingerprint)
        )
        update["skill_cache_status"] = "recorded" if recorded else "cold"
        mirror_to_disk({**state, **update}, config.docs_for(issue))
        return update

    return _node
