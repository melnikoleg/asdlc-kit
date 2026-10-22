"""Shared helpers for graph nodes (DRY)."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol

from ..claude_runner import AgentResult
from ..config import Config
from ..metrics import build_metric, write_metrics
from ..state import PipelineState, Phase, mirror_to_disk, now_iso


class Runner(Protocol):
    """Callable that runs an agent node and returns its verdict.

    Matches :func:`runtime.claude_runner.run_agent`; tests substitute a mock.
    """

    def __call__(self, node: str, prompt: str, config: Config) -> Awaitable[AgentResult]:
        ...


def base_update(
    state: PipelineState,
    phase: Phase,
    config: Config,
    metric: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Phase transition + STATE.json/METRICS.json mirror, as a partial update.

    ``metric`` (if given) is this node's usage record: it is returned as a
    reducer delta AND folded into the on-disk metrics mirror. The mirror uses
    ``state``'s already-merged metric list plus this delta, so it stays complete
    without the review fan-out racing on the file (review nodes don't mirror).
    """
    update: dict[str, Any] = {"phase": phase, "updated_at": now_iso()}
    if metric is not None:
        update["metrics"] = [metric]
    docs = config.docs_for(state["issue"])
    # Mirror using the post-transition view so STATE.json reflects this node.
    mirror_to_disk({**state, **update}, docs)
    all_metrics = list(state.get("metrics", [])) + ([metric] if metric else [])
    if all_metrics:
        write_metrics(all_metrics, docs)
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
        metric = build_metric(node, result.status, result.usage, state.get("iteration", 0))
        update = base_update(state, phase, config, metric=metric)
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
        metric = build_metric(node, result.status, result.usage, state.get("iteration", 0))
        return {
            "verdicts": {node: result.status},
            "artifacts": result.artifacts,
            "metrics": [metric],
        }

    return _node
