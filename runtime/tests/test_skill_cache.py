"""Regression tests for opt-in execution-grounded codebase capsules."""
from __future__ import annotations

import json

import pytest

from runtime.claude_runner import AgentResult
from runtime.nodes.codebase import make_codebase_node
from runtime.skill_cache import (
    qualify_and_record, replay_codebase, workspace_fingerprint,
)
from runtime.state import new_state


REPORT = (
    "# Codebase Context\n"
    "Stack: Python 3.11\n"
    "Tests: pytest\n"
    "Conventions: small functional services\n"
    "Relevant implementation: docs/first-issue/CODEBASE_CONTEXT.md\n"
)


def _project(tmp_path):
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    (tmp_path / ".claude" / "agents" / "codebase-agent.md").write_text(
        "Codebase scanner v1"
    )
    (tmp_path / "app.py").write_text("print('hello')\n")
    return tmp_path


def _record(root, *, requirement="Implement payment tracking", issue="first-issue"):
    fingerprint = workspace_fingerprint(root)
    assert fingerprint is not None
    report = root / "docs" / issue / "CODEBASE_CONTEXT.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(REPORT)
    assert qualify_and_record(root, issue, requirement, fingerprint)
    return fingerprint


def test_fingerprint_ignores_generated_docs_and_cache(tmp_path):
    root = _project(tmp_path)
    before = workspace_fingerprint(root)
    (root / "docs" / "task").mkdir(parents=True)
    (root / "docs" / "task" / "PRD.md").write_text("generated")
    (root / ".asdlc" / "skill-cache").mkdir(parents=True)
    (root / ".asdlc" / "skill-cache" / "entry.json").write_text("{}")
    assert workspace_fingerprint(root) == before
    (root / "app.py").write_text("print('changed')\n")
    assert workspace_fingerprint(root) != before


def test_qualifies_and_replays_with_issue_binding(tmp_path):
    root = _project(tmp_path)
    _record(root)
    assert replay_codebase(
        root, "second-issue", "Implement payment tracking", workspace_fingerprint(root)
    )
    copied = (root / "docs" / "second-issue" / "CODEBASE_CONTEXT.md").read_text()
    assert "docs/second-issue/CODEBASE_CONTEXT.md" in copied
    assert "first-issue/CODEBASE_CONTEXT" not in copied
    capsules = list((root / ".asdlc" / "skill-cache").glob("*.json"))
    assert len(capsules) == 1
    # Capsules contain provenance hashes only; source report stays in docs.
    capsule = json.loads(capsules[0].read_text())
    assert capsule["program"] == "copy-codebase-report-with-issue-binding"
    assert capsule["qualified"] is True
    assert "Stack: Python" not in capsules[0].read_text()


def test_miss_without_observed_success(tmp_path):
    root = _project(tmp_path)
    fingerprint = workspace_fingerprint(root)
    assert not qualify_and_record(root, "first-issue", "task", fingerprint)
    assert not replay_codebase(root, "other-issue", "task", fingerprint)


def test_rejects_request_and_workspace_drift(tmp_path):
    root = _project(tmp_path)
    fingerprint = _record(root)
    assert not replay_codebase(root, "other-issue", "a different request", fingerprint)
    (root / "app.py").write_text("print('new')\n")
    assert not replay_codebase(root, "other-issue", "Implement payment tracking", fingerprint)


def test_rejects_agent_instruction_drift(tmp_path):
    root = _project(tmp_path)
    fingerprint = _record(root)
    (root / ".claude" / "agents" / "codebase-agent.md").write_text("Codebase scanner v2")
    assert not replay_codebase(root, "other-issue", "Implement payment tracking", fingerprint)


def test_rejects_modified_source_artifact(tmp_path):
    root = _project(tmp_path)
    fingerprint = _record(root)
    (root / "docs" / "first-issue" / "CODEBASE_CONTEXT.md").write_text(REPORT + "tampered")
    assert not replay_codebase(root, "other-issue", "Implement payment tracking", fingerprint)


def test_rejects_corrupt_capsule_and_preserves_target(tmp_path):
    root = _project(tmp_path)
    fingerprint = _record(root)
    capsule_path = next((root / ".asdlc" / "skill-cache").glob("*.json"))
    capsule_path.write_text("{broken")
    target = root / "docs" / "second-issue" / "CODEBASE_CONTEXT.md"
    target.parent.mkdir(parents=True)
    target.write_text("Important original content")
    assert not replay_codebase(root, "second-issue", "Implement payment tracking", fingerprint)
    assert target.read_text() == "Important original content"


def test_replay_rejects_symlink_source(tmp_path):
    root = _project(tmp_path)
    fingerprint = _record(root)
    source = root / "docs" / "first-issue" / "CODEBASE_CONTEXT.md"
    original = source.parent / "original.md"
    source.rename(original)
    try:
        source.symlink_to(original)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    assert not replay_codebase(root, "another-issue", "Implement payment tracking", fingerprint)


@pytest.mark.asyncio
async def test_codebase_node_cold_then_warm_then_fallback(temp_config):
    root = temp_config.repo_root
    (root / "app.py").write_text("print('hello')\n")
    calls = []

    async def runner(node, prompt, config):
        calls.append(node)
        issue = prompt.split("Issue: ", 1)[1].splitlines()[0]
        report = config.docs_for(issue) / "CODEBASE_CONTEXT.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(REPORT)
        return AgentResult(status="APPROVED", artifacts=[f"docs/{issue}/CODEBASE_CONTEXT.md"])

    node = make_codebase_node(temp_config, runner)
    first = await node(new_state("first-issue", "Implement payment tracking", skill_cache=True))
    assert first["skill_cache_status"] == "recorded"
    assert calls == ["codebase"]

    second = await node(new_state("second-issue", "Implement payment tracking", skill_cache=True))
    assert second["skill_cache_status"] == "hit"
    assert second["verdicts"]["codebase"] == "APPROVED"
    assert calls == ["codebase"]

    # Code changed: guard misses, so the original model/skill is called.
    (root / "app.py").write_text("print('different')\n")
    third = await node(new_state("third-issue", "Implement payment tracking", skill_cache=True))
    assert third["skill_cache_status"] == "recorded"
    assert calls == ["codebase", "codebase"]


@pytest.mark.asyncio
async def test_cache_is_opt_in(temp_config):
    root = temp_config.repo_root
    (root / "app.py").write_text("pass\n")
    calls = []

    async def runner(node, prompt, config):
        calls.append(node)
        return AgentResult(status="APPROVED")

    node = make_codebase_node(temp_config, runner)
    assert "skill_cache_status" not in await node(new_state("first-issue", "task"))
    assert "skill_cache_status" not in await node(new_state("second-issue", "task"))
    assert calls == ["codebase", "codebase"]


@pytest.mark.asyncio
async def test_failed_agent_never_compiles_capsule(temp_config):
    root = temp_config.repo_root
    (root / "app.py").write_text("pass\n")

    async def runner(node, prompt, config):
        target = config.docs_for("first-issue") / "CODEBASE_CONTEXT.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(REPORT)
        return AgentResult(status="FAILED")

    result = await make_codebase_node(temp_config, runner)(
        new_state("first-issue", "task", skill_cache=True)
    )
    assert result["skill_cache_status"] == "cold"
    assert not list((root / ".asdlc" / "skill-cache").glob("*.json"))
