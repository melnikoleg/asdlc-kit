"""Shared helpers for graph nodes (DRY)."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol

from ..claude_runner import AgentResult
from ..config import Config
from ..state import PipelineState, Phase, mirror_to_disk, now_iso


class Runner(Protocol):
    """Callable that runs an agent node and returns its verdict.

    Matches :func:`runtime.claude_runner.run_agent`; tests substitute a mock.
    """

    def __call__(self, node: str, prompt: str, config: Config) -> Awaitable[AgentResult]:
        ...


def base_update(state: PipelineState, phase: Phase, config: Config) -> dict[str, Any]:
    """Phase transition + STATE.json mirror, returned as a partial state update."""
    update: dict[str, Any] = {"phase": phase, "updated_at": now_iso()}
    # Mirror using the post-transition view so STATE.json reflects this node.
    mirror_to_disk({**state, **update}, config.docs_for(state["issue"]))
    return update


def make_generative_node(
    node: str,
    phase: Phase,
    build_prompt: Callable[[PipelineState, Config], str],
    config: Config,
    runner: Runner,
) -> Callable[[PipelineState], Awaitable[dict[str, Any]]]:
    """Factory for an LLM-backed node that runs one agent and records its verdict."""

    async def _node(state: PipelineState) -> dict[str, Any]:
        prompt = build_prompt(state, config)
        result = await runner(node, prompt, config)
        update = base_update(state, phase, config)
        update["verdicts"] = {node: result.status}
        update["artifacts"] = result.artifacts  # reducer union-appends
        return update

    return _node


def make_review_node(
    node: str,
    build_prompt: Callable[[PipelineState, Config], str],
    config: Config,
    runner: Runner,
) -> Callable[[PipelineState], Awaitable[dict[str, Any]]]:
    """Factory for a parallel review node.

    Runs only on the first review pass (no prior verdict for this node) or when
    this node is explicitly in ``failing_agents`` (fix re-run). Otherwise it is
    a no-op returning its previous verdict — so passing agents aren't re-run.

    Does not mutate ``phase`` or mirror STATE.json: those are owned by the
    downstream ``aggregate`` node to avoid concurrent-write races during fan-out.
    """

    async def _node(state: PipelineState) -> dict[str, Any]:
        prior = state.get("verdicts", {}).get(node)
        failing = state.get("failing_agents", [])
        should_run = prior is None or node in failing
        if not should_run:
            return {"verdicts": {node: prior}}
        result = await runner(node, build_prompt(state, config), config)
        return {"verdicts": {node: result.status}, "artifacts": result.artifacts}

    return _node
