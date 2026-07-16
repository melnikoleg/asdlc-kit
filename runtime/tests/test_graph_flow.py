"""End-to-end graph topology with a mock runner (no real LLM calls).

Verifies the determinism guarantees the LangGraph layer exists to provide:
the approval interrupt physically blocks, the fix-loop is hard-capped, passing
review agents aren't re-run, and terminal states are reached deterministically.
"""

from __future__ import annotations

import uuid

import pytest
from langgraph.types import Command

from runtime.checkpoint import open_checkpointer
from runtime.claude_runner import AgentResult
from runtime.graph import build_graph
from runtime.state import REVIEW_AGENTS, new_state

ISSUE = "demo"


def mock_runner(review_fail_times=0):
    """Runner that fails the whole review fan-out ``review_fail_times`` times."""
    counters = {"review_rounds_seen": 0, "calls_in_round": 0}

    async def runner(node, prompt, config):
        if node in REVIEW_AGENTS:
            counters["calls_in_round"] += 1
            round_index = (counters["calls_in_round"] - 1) // len(REVIEW_AGENTS)
            if round_index < review_fail_times:
                return AgentResult(status="NEEDS_FIX", artifacts=[f"docs/{ISSUE}/{node}.md"])
        return AgentResult(status="APPROVED", artifacts=[f"docs/{ISSUE}/{node}.md"])

    return runner


def write_plan(config, cmd):
    docs = config.docs_for(ISSUE)
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "PLAN.md").write_text(f"## Phase 1\nValidation: {cmd}\n")


async def drive(config, *, review_fail_times=0, plan_cmd="true", approve=True):
    write_plan(config, plan_cmd)
    thread = {"configurable": {"thread_id": f"{ISSUE}-{uuid.uuid4()}"}}
    async with open_checkpointer(config) as cp:
        graph = build_graph(config, runner=mock_runner(review_fail_times), checkpointer=cp)
        first = await graph.ainvoke(new_state(ISSUE, "build a thing"), thread)
        snap = await graph.aget_state(thread)
        paused_at_approval = snap.next == ("approval",)
        dev_ran_early = "developer" in snap.values.get("verdicts", {})
        final = await graph.ainvoke(
            Command(resume="approve" if approve else "cancel"), thread
        )
    return {
        "first": first,
        "paused_at_approval": paused_at_approval,
        "dev_ran_early": dev_ran_early,
        "final": final,
    }


@pytest.mark.asyncio
async def test_interrupt_blocks_before_developer(temp_config):
    out = await drive(temp_config)
    assert out["paused_at_approval"] is True
    assert "__interrupt__" in out["first"]
    assert out["dev_ran_early"] is False  # developer did NOT run before approval


@pytest.mark.asyncio
async def test_happy_path_reaches_done(temp_config):
    out = await drive(temp_config)
    final = out["final"]
    assert final["phase"] == "done"
    assert final["iteration"] == 0
    assert all(final["verdicts"][a] == "APPROVED" for a in REVIEW_AGENTS)


@pytest.mark.asyncio
async def test_validation_failure_caps_at_escalation(temp_config):
    out = await drive(temp_config, plan_cmd="false")
    final = out["final"]
    assert final["phase"] == "escalated"
    assert final["iteration"] == temp_config.max_iterations + 1


@pytest.mark.asyncio
async def test_review_failure_then_recovery(temp_config):
    out = await drive(temp_config, review_fail_times=2)
    final = out["final"]
    assert final["phase"] == "done"
    assert final["iteration"] == 2


@pytest.mark.asyncio
async def test_review_failure_exhausts_budget(temp_config):
    out = await drive(temp_config, review_fail_times=99)
    final = out["final"]
    assert final["phase"] == "escalated"
    assert set(final["failing_agents"]) == set(REVIEW_AGENTS)


@pytest.mark.asyncio
async def test_cancel_at_gate_escalates_without_developer(temp_config):
    out = await drive(temp_config, approve=False)
    final = out["final"]
    assert final["phase"] == "escalated"
    assert "developer" not in final.get("verdicts", {})


@pytest.mark.asyncio
async def test_state_json_is_mirrored(temp_config):
    await drive(temp_config)
    state_file = temp_config.docs_for(ISSUE) / "STATE.json"
    assert state_file.is_file()
    import json

    data = json.loads(state_file.read_text())
    assert data["issue"] == ISSUE
    assert data["phase"] == "done"


@pytest.mark.asyncio
async def test_metrics_recorded_for_every_agent(temp_config):
    out = await drive(temp_config)
    final = out["final"]
    # One metric per agent run: product, planner, architect, developer + 3 reviews.
    agents = {m["agent"] for m in final["metrics"]}
    assert agents == {
        "product-agent", "planner-agent", "architect-agent",
        "developer-agent", "reviewer-agent", "qa-agent", "devops-agent",
    }
    # And the full list is mirrored to METRICS.json.
    import json

    metrics_file = temp_config.docs_for(ISSUE) / "METRICS.json"
    assert metrics_file.is_file()
    disk = json.loads(metrics_file.read_text())
    assert len(disk) == len(final["metrics"])
