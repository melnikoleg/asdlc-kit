"""Graph node factories.

Every node is built by a ``make_*_node(config, runner)`` factory so the graph
can inject configuration and — in tests — a mock runner instead of the real
Claude Agent SDK bridge. Routing functions for conditional edges are likewise
built by ``make_route_*`` factories (they close over config for the iteration
budget).
"""

from .acceptance import (
    make_acceptance_author_node,
    make_acceptance_gate_node,
    make_route_after_acceptance,
)
from .aggregate import make_aggregate_node, make_route_after_aggregate
from .approval import make_approval_node, route_after_approval
from .architect import make_architect_node
from .developer import make_developer_node
from .devops import make_devops_node
from .escalate import make_escalate_node
from .planner import make_planner_node
from .product import make_product_node
from .qa import make_qa_node
from .readiness import make_readiness_node
from .review import make_reviewer_node
from .validate import make_route_after_validate, make_validate_node

__all__ = [
    "make_product_node",
    "make_planner_node",
    "make_architect_node",
    "make_acceptance_author_node",
    "make_acceptance_gate_node",
    "make_route_after_acceptance",
    "make_approval_node",
    "route_after_approval",
    "make_developer_node",
    "make_validate_node",
    "make_route_after_validate",
    "make_reviewer_node",
    "make_qa_node",
    "make_devops_node",
    "make_aggregate_node",
    "make_route_after_aggregate",
    "make_readiness_node",
    "make_escalate_node",
]
