"""LangGraph assembly: the deterministic SDLC topology.

    START → product → planner → architect → approval ⏸(interrupt)
          → developer → validate ──fail──▶ developer (fix) | escalate
                              └─pass─▶ [reviewer ‖ qa ‖ devops] → aggregate
    aggregate ──all APPROVED──▶ readiness → END
              ──NEEDS_FIX & budget left──▶ developer (fix)
              ──budget exhausted──▶ escalate → END

The graph guarantees the *topology* (every node runs, in order, with a hard
fix-loop limit and a real human-approval pause). The LLM only does generative
work inside nodes; validation and routing are plain code.
"""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from .config import Config
from .state import PipelineState
from . import nodes as N


def build_graph(config: Config, runner: Callable[..., Any] | None = None, checkpointer=None):
    """Build and compile the pipeline graph.

    ``runner`` defaults to the real Claude Agent SDK bridge; tests inject a
    mock. A ``checkpointer`` is required for the approval interrupt and durable
    resume — :func:`runtime.checkpoint.make_checkpointer` provides one.
    """
    if runner is None:
        from .claude_runner import run_agent as runner  # lazy: avoid SDK import in tests

    g: StateGraph = StateGraph(PipelineState)

    # Nodes
    g.add_node("product", N.make_product_node(config, runner))
    g.add_node("planner", N.make_planner_node(config, runner))
    g.add_node("architect", N.make_architect_node(config, runner))
    g.add_node("approval", N.make_approval_node(config))
    g.add_node("developer", N.make_developer_node(config, runner))
    g.add_node("validate", N.make_validate_node(config))
    g.add_node("reviewer", N.make_reviewer_node(config, runner))
    g.add_node("qa", N.make_qa_node(config, runner))
    g.add_node("devops", N.make_devops_node(config, runner))
    g.add_node("aggregate", N.make_aggregate_node(config))
    g.add_node("readiness", N.make_readiness_node(config))
    g.add_node("escalate", N.make_escalate_node(config))

    # Linear planning chain
    g.add_edge(START, "product")
    g.add_edge("product", "planner")
    g.add_edge("planner", "architect")
    g.add_edge("architect", "approval")

    # Approval gate → implement or cancel
    g.add_conditional_edges(
        "approval",
        N.route_after_approval,
        {"developer": "developer", "escalate": "escalate"},
    )

    # Implement → deterministic validation gate
    g.add_edge("developer", "validate")
    g.add_conditional_edges(
        "validate",
        N.make_route_after_validate(config),
        {
            "reviewer": "reviewer",
            "qa": "qa",
            "devops": "devops",
            "developer": "developer",
            "escalate": "escalate",
        },
    )

    # Parallel review fan-in → aggregate
    g.add_edge("reviewer", "aggregate")
    g.add_edge("qa", "aggregate")
    g.add_edge("devops", "aggregate")

    # Aggregate drives the fix-loop
    g.add_conditional_edges(
        "aggregate",
        N.make_route_after_aggregate(config),
        {
            "readiness": "readiness",
            "developer": "developer",
            "escalate": "escalate",
        },
    )

    g.add_edge("readiness", END)
    g.add_edge("escalate", END)

    return g.compile(checkpointer=checkpointer)
