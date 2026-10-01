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
from runtime.state import REVIEW_AGENTS, new_state, review_agents

ISSUE = "demo"


def mock_runner(review_fail_times=0, fan_out=2):
    """Runner that fails the whole review fan-out ``review_fail_times`` times."""
    counters = {"calls_in_round": 0}

    async def runner(node, prompt, config):
        if node in REVIEW_AGENTS:
            counters["calls_in_round"] += 1
            round_index = (counters["calls_in_round"] - 1) // fan_out
            if round_index < review_fail_times:
                return AgentResult(status="NEEDS_FIX", artifacts=[f"docs/{ISSUE}/{node}.md"])
        return AgentResult(status="APPROVED", artifacts=[f"docs/{ISSUE}/{node}.md"])

    return runner


def write_plan(config, cmd):
    docs = config.docs_for(ISSUE)
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "PLAN.md").write_text(f"## Phase 1\nValidation: {cmd}\n")


def write_strategy(config, fields: dict):
    docs = config.docs_for(ISSUE)
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "TEST_STRATEGY.md").write_text(
        "".join(f"{k}: {v}\n" for k, v in fields.items())
    )


def server_strategy(e2e):
    import socket
    import sys

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return {
        "Layers": "api-e2e",
        "Start": f"{sys.executable} -m http.server {port} --bind 127.0.0.1",
        "Healthcheck": f"http://127.0.0.1:{port}/",
        "E2E": e2e.format(port=port),
    }


def write_acceptance(config, cmd):
    docs = config.docs_for(ISSUE)
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "ACCEPTANCE.md").write_text(f"AC-1\nAcceptance: {cmd}\n")


async def drive(
    config, *, review_fail_times=0, plan_cmd="true", approve=True, acceptance_cmd=None,
    devops=False, strategy=None, runner=None,
):
    write_plan(config, plan_cmd)
    if strategy is not None:
        write_strategy(config, strategy)
    if acceptance_cmd is not None:
        write_acceptance(config, acceptance_cmd)
    thread = {"configurable": {"thread_id": f"{ISSUE}-{uuid.uuid4()}"}}
    async with open_checkpointer(config) as cp:
        graph = build_graph(
            config,
            runner=runner or mock_runner(review_fail_times, fan_out=3 if devops else 2),
            checkpointer=cp,
        )
        first = await graph.ainvoke(new_state(ISSUE, "build a thing", devops=devops), thread)
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
    assert all(final["verdicts"][a] == "APPROVED" for a in review_agents(final))
    assert "devops" not in final["verdicts"]


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
    assert set(final["failing_agents"]) == {"reviewer", "qa"}


@pytest.mark.asyncio
async def test_cancel_at_gate_escalates_without_developer(temp_config):
    out = await drive(temp_config, approve=False)
    final = out["final"]
    assert final["phase"] == "escalated"
    assert "developer" not in final.get("verdicts", {})


@pytest.mark.asyncio
async def test_heldout_pass_reaches_done(temp_config):
    out = await drive(temp_config, acceptance_cmd="true")
    final = out["final"]
    assert final["phase"] == "done"
    assert all(r["passed"] for r in final["acceptance"].values())


@pytest.mark.asyncio
async def test_heldout_failure_escalates_without_fix_loop(temp_config):
    # Review passes, but the held-out suite fails → escalate. The developer is
    # never re-run against it (iteration stays at 0), so the gate stays held-out.
    out = await drive(temp_config, acceptance_cmd="false")
    final = out["final"]
    assert final["phase"] == "escalated"
    assert final["iteration"] == 0
    assert any(not r["passed"] for r in final["acceptance"].values())


@pytest.mark.asyncio
async def test_developer_prompt_never_shows_acceptance(temp_config):
    seen_prompts = []

    async def spy_runner(node, prompt, config):
        if node == "developer":
            seen_prompts.append(prompt)
        return AgentResult(status="APPROVED", artifacts=[f"docs/{ISSUE}/{node}.md"])

    write_plan(temp_config, "true")
    write_acceptance(temp_config, "true")
    thread = {"configurable": {"thread_id": f"{ISSUE}-{uuid.uuid4()}"}}
    async with open_checkpointer(temp_config) as cp:
        graph = build_graph(temp_config, runner=spy_runner, checkpointer=cp)
        await graph.ainvoke(new_state(ISSUE, "build a thing"), thread)
        await graph.ainvoke(Command(resume="approve"), thread)

    assert seen_prompts, "developer node never ran"
    for prompt in seen_prompts:
        assert "ACCEPTANCE.md" in prompt  # the blindness instruction is present
        assert "NOT read" in prompt


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
    # One metric per agent run. Greenfield skips codebase, devops is opt-in.
    agents = {m["agent"] for m in final["metrics"]}
    assert agents == {
        "product-agent", "planner-agent", "architect-agent", "acceptance-agent",
        "developer-agent", "reviewer-agent", "qa-agent",
    }
    # And the full list is mirrored to METRICS.json.
    import json

    metrics_file = temp_config.docs_for(ISSUE) / "METRICS.json"
    assert metrics_file.is_file()
    disk = json.loads(metrics_file.read_text())
    assert len(disk) == len(final["metrics"])


@pytest.mark.asyncio
async def test_devops_runs_only_when_opted_in(temp_config):
    out = await drive(temp_config, devops=True)
    assert out["final"]["phase"] == "done"
    assert out["final"]["verdicts"]["devops"] == "APPROVED"


@pytest.mark.asyncio
async def test_greenfield_skips_codebase_agent(temp_config):
    seen = []

    async def spy(node, prompt, config):
        seen.append(node)
        return AgentResult(status="APPROVED")

    await drive(temp_config, runner=spy)
    assert "codebase" not in seen


@pytest.mark.asyncio
async def test_existing_repo_runs_codebase_agent_first(temp_config):
    (temp_config.repo_root / "app.py").write_text("print('hi')\n")
    seen = []

    async def spy(node, prompt, config):
        seen.append(node)
        return AgentResult(status="APPROVED")

    await drive(temp_config, runner=spy)
    assert seen[0] == "codebase"


@pytest.mark.asyncio
async def test_e2e_failure_loops_to_developer_then_escalates(temp_config):
    strategy = server_strategy("curl -sf http://127.0.0.1:{port}/missing-page -o /dev/null")
    out = await drive(temp_config, strategy=strategy)
    final = out["final"]
    assert final["phase"] == "escalated"
    assert final["iteration"] == temp_config.max_iterations + 1
    assert any("missing-page" in cmd and not r["passed"] for cmd, r in final["validation"].items())


@pytest.mark.asyncio
async def test_e2e_and_heldout_run_against_booted_app(temp_config):
    strategy = server_strategy("curl -sf http://127.0.0.1:{port}/ -o /dev/null")
    acc = strategy["Healthcheck"]
    out = await drive(temp_config, strategy=strategy, acceptance_cmd=f"curl -sf {acc} -o /dev/null")
    final = out["final"]
    assert final["phase"] == "done"
    assert all(r["passed"] for r in final["validation"].values())
    assert all(r["passed"] for r in final["acceptance"].values())


@pytest.mark.asyncio
async def test_prompts_carry_the_e2e_contract(temp_config):
    prompts = {}

    async def spy(node, prompt, config):
        prompts.setdefault(node, prompt)
        return AgentResult(status="APPROVED")

    await drive(temp_config, runner=spy)
    for node in ("developer", "qa", "acceptance", "planner"):
        assert "TEST_STRATEGY.md" in prompts[node], node
    assert "asdlc-e2e" in prompts["developer"] and "asdlc-e2e" in prompts["qa"]


@pytest.mark.asyncio
async def test_fix_prompt_includes_failed_command_output(temp_config):
    dev_prompts = []

    async def spy(node, prompt, config):
        if node == "developer":
            dev_prompts.append(prompt)
        return AgentResult(status="APPROVED")

    await drive(temp_config, runner=spy, plan_cmd="echo marker-xyz; false")
    fix = [p for p in dev_prompts if "FIX MODE" in p]
    assert fix and all("marker-xyz" in p for p in fix)
    assert all("REVIEW.md" not in p for p in fix)  # nothing to read yet
