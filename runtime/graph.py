"""LangGraph assembly: the deterministic SDLC topology.

    START → product → planner → architect → acceptance → approval ⏸(interrupt)
          → developer → validate ──fail──▶ developer (fix) | escalate
                              └─pass─▶ [reviewer ‖ qa ‖ devops] → aggregate
    aggregate ──all APPROVED──▶ acceptance_gate ──pass──▶ readiness → END
                                                └─fail─▶ escalate → END
              ──NEEDS_FIX & budget left──▶ developer (fix)
              ──budget exhausted──▶ escalate → END

    ``acceptance`` authors a held-out suite the developer never reads;
    ``acceptance_gate`` grades it deterministically as an objective final check.

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
    g.add_node("acceptance", N.make_acceptance_author_node(config, runner))
    g.add_node("acceptance_gate", N.make_acceptance_gate_node(config))
    g.add_node("approval", N.make_approval_node(config))
    g.add_node("developer", N.make_developer_node(config, runner))
    g.add_node("validate", N.make_validate_node(config))
    g.add_node("reviewer", N.make_reviewer_node(config, runner))
    g.add_node("qa", N.make_qa_node(config, runner))
    g.add_node("devops", N.make_devops_node(config, runner))
    g.add_node("aggregate", N.make_aggregate_node(config))
    g.add_node("readiness", N.make_readiness_node(config))
    g.add_node("escalate", N.make_escalate_node(config))

    # Linear planning chain. The held-out acceptance suite is authored before
    # the approval gate so a human can review the objective criteria too.
    g.add_edge(START, "product")
    g.add_edge("product", "planner")
    g.add_edge("planner", "architect")
    g.add_edge("architect", "acceptance")
    g.add_edge("acceptance", "approval")

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

    # Aggregate drives the fix-loop. On all-APPROVED it goes to the held-out
    # acceptance gate (not straight to readiness).
    g.add_conditional_edges(
        "aggregate",
        N.make_route_after_aggregate(config),
        {
            "readiness": "acceptance_gate",
            "developer": "developer",
            "escalate": "escalate",
        },
    )

    # Held-out gate: pass → readiness, fail → escalate (never looped back to the
    # developer, so the suite stays held-out).
    g.add_conditional_edges(
        "acceptance_gate",
        N.make_route_after_acceptance(config),
        {"readiness": "readiness", "escalate": "escalate"},
    )

    g.add_edge("readiness", END)
    g.add_edge("escalate", END)

    return g.compile(checkpointer=checkpointer)
