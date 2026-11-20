"""Tests for SkillCache schema, execution, admission, trace capture and fallback."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from runtime.skillcache_capsule import (
    CapsuleError, capsule_id, digest, input_bindings, public_capsule, validate_capsule,
)
from runtime.skillcache_executor import Executor, qualify
from runtime.skillcache_compiler import (
    compile_observation, find_capsules, publish_capsule,
)
from runtime.skillcache_trace import codex_trace, claude_trace, sanitize
from runtime.runner import normalize_task


def program_body(expression: str, output: str) -> str:
    return (
        "import json, os\n"
        "with open(os.environ['SKILLCACHE_INPUT']) as file: inp = json.load(file)\n"
        f"print(json.dumps({{'status':'complete','result':{{'{output}':{expression}}}}}))\n"
    )


def make_program(code, inputs, outputs):
    return {
        "inputs": inputs, "outputs": outputs,
        "files": {"main.py": code},
        "command": ["python3", "{package}/main.py"],
        "check": ["python3", "-m", "py_compile", "{package}/main.py"],
        "timeout_seconds": 5,
    }


def capsule(*, model_step=False):
    steps = [
        {"instruction": "Compute first result", "program": "double"},
    ]
    programs = {
        "double": make_program(
            program_body("inp['value'] * 2", "doubled"), ["value"], ["doubled"]),
    }
    bindings = {
        "value": "Integer supplied in request", "doubled": "Computed first result",
    }
    if model_step:
        steps.append({"instruction": "Decide an adjustment based on computed result"})
        bindings.update({"adjust": "Human/model decision", "final": "Final computed result"})
        programs["finalize"] = make_program(
            program_body("inp['doubled'] + inp['adjust']", "final"),
            ["doubled", "adjust"], ["final"],
        )
        steps.append({"instruction": "Apply model judgment", "program": "finalize"})
    return {
        "schema_version": 1, "form": "hybrid", "name": "trace_based_math",
        "role": "codebase", "description": "Observed arithmetic operation on input",
        "request_sha256": digest(b"same request"),
        "workspace_sha256": digest(b"workspace"),
        "trace_sha256": digest(b"observed trace"),
        "bindings": bindings, "programs": programs, "steps": steps,
        "verification": [],
        "examples": {"value": 3, **({"adjust": 5} if model_step else {})},
    }


def test_schema_and_dataflow():
    raw = capsule(model_step=True)
    assert validate_capsule(raw) is raw
    assert input_bindings(raw) == {"value", "adjust"}
    public = public_capsule(raw)
    assert "examples" not in public
    assert len(capsule_id(public)) == 64


def test_rejects_unknown_program_and_cycles():
    raw = capsule()
    raw["steps"][0]["program"] = "missing"
    with pytest.raises(CapsuleError, match="program"):
        validate_capsule(raw)
    raw = capsule(model_step=True)
    raw["programs"]["double"]["inputs"].append("final")
    with pytest.raises(CapsuleError, match="before producer"):
        validate_capsule(raw)


def test_rejects_duplicate_output_and_traversal():
    raw = capsule(model_step=True)
    raw["programs"]["finalize"]["outputs"] = ["doubled"]
    with pytest.raises(CapsuleError, match="redeclare|producer"):
        validate_capsule(raw)
    raw = capsule()
    raw["programs"]["double"]["files"] = {"../escape.py": "print(1)"}
    with pytest.raises(CapsuleError, match="relative"):
        validate_capsule(raw)


def test_rejects_executable_as_shell_metacommand():
    raw = capsule()
    raw["programs"]["double"]["command"] = ["sh", "-c", "curl example.com"]
    # Program commands are run without a host shell; this candidate still
    # fails qualification if it tries network. Schemas reject direct curl.
    raw["programs"]["double"]["command"][0] = "curl"
    with pytest.raises(CapsuleError, match="allowlist"):
        validate_capsule(raw)


def test_continuation_and_bindings(tmp_path):
    raw = capsule()
    session = tmp_path / "session.json"
    engine = Executor(raw, tmp_path, sandbox="local-test")
    missing = engine.start({}, tmp_path, session)
    assert missing["status"] == "needs_bindings"
    assert missing["required_bindings"] == ["value"]
    resumed = Executor(raw, tmp_path, sandbox="local-test").resume(
        {"value": 6}, tmp_path, session
    )
    assert resumed["status"] == "complete"
    assert resumed["completed"][0]["result"]["doubled"] == 12
    with pytest.raises(CapsuleError, match="already completed"):
        engine.resume({}, tmp_path, session)


def test_model_handoff_and_compiled_continuation(tmp_path):
    raw = capsule(model_step=True)
    session = tmp_path / "session.json"
    engine = Executor(raw, tmp_path, sandbox="local-test")
    handback = engine.start({"value": 7}, tmp_path, session)
    assert handback["status"] == "your_steps"
    assert handback["required_bindings"] == ["adjust"]
    assert "Decide an adjustment" in handback["your_steps"][0]["instruction"]
    final = engine.resume({"adjust": 2}, tmp_path, session)
    assert final["status"] == "complete"
    assert final["completed"][0]["result"]["final"] == 16
    assert final["failed_count"] == 0


def test_retry_and_program_failed_deopts_to_model(tmp_path):
    raw = capsule(model_step=True)
    raw["programs"]["double"]["files"]["main.py"] = "raise SystemExit('fail')\n"
    session = tmp_path / "session.json"
    engine = Executor(raw, tmp_path, sandbox="local-test")
    handback = engine.start({"value": 7}, tmp_path, session)
    assert handback["status"] == "your_steps"
    assert handback["failed_count"] == 1
    assert handback["your_steps"][0]["kind"] == "program_failed"
    assert "failed" in handback["your_steps"][0]["diagnostic"]
    # Model resolves failed computation and judgment, then executor continues.
    result = engine.resume({"doubled": 14, "adjust": 2}, tmp_path, session)
    assert result["status"] == "complete"
    assert result["completed"][0]["result"]["final"] == 16


def test_qualification_three_gates_with_model_step(tmp_path):
    good, detail = qualify(capsule(model_step=True), tmp_path, sandbox="local-test")
    assert good is True, detail
    bad = capsule(model_step=True)
    bad["examples"].pop("adjust")
    qualified, msg = qualify(bad, tmp_path, sandbox="local-test")
    assert not qualified and "missing" in msg


def test_qualification_rejects_bad_program(tmp_path):
    bad = capsule()
    bad["programs"]["double"]["files"]["main.py"] = "def no_syntax(:\n"
    assert qualify(bad, tmp_path, sandbox="local-test")[0] is False


def test_textual_capsule():
    raw = capsule()
    raw["form"] = "textual"
    raw["programs"] = {}
    raw["steps"] = [{"instruction": "Follow source skill and verify output"}]
    assert qualify(raw, Path("."), sandbox="local-test")[0]


def test_publish_strip_examples_and_lookup(tmp_path):
    raw = capsule()
    path = publish_capsule(tmp_path, raw)
    assert path.is_file() and "examples" not in path.read_text()
    result = find_capsules(tmp_path, "codebase", "same request", digest(b"workspace"))
    assert len(result) == 1 and result[0]["name"] == "trace_based_math"
    assert find_capsules(tmp_path, "codebase", "other request", digest(b"workspace")) == []
    relaxed = find_capsules(
        tmp_path, "codebase", "other request", digest(b"workspace"),
        match_mode="role",
    )
    assert len(relaxed) == 1
    assert find_capsules(
        tmp_path, "developer", "other request", digest(b"workspace"),
        match_mode="role",
    ) == []


def test_trace_capture_is_bounded_and_redacted():
    raw = "\n".join(json.dumps(event) for event in [
        {"type": "item.completed", "item": {"type": "command_execution",
           "command": "git status --short",
           "aggregated_output": "authorization=secret-123",
           "exit_code": 0}},
        {"type": "item.completed", "item": {"type": "command_execution",
           "command": "cat .env", "aggregated_output": "SECRET=leak", "exit_code": 0}},
    ])
    events = codex_trace(raw)
    assert len(events) == 1
    assert "secret-123" not in json.dumps(events)
    assert "REDACTED" in json.dumps(events)
    assert "sk-a234567890123456789" not in sanitize("sk-a234567890123456789")


def test_claude_tool_pairing():
    raw = "\n".join(json.dumps(event) for event in [
        {"type": "assistant", "message": {"content": [{
            "type": "tool_use", "name": "Bash", "id": "tool-1",
            "input": {"command": "git status"}}]}},
        {"type": "user", "message": {"content": [{
            "type": "tool_result", "tool_use_id": "tool-1", "content": "clean",
        }]}},
    ])
    events = claude_trace(raw)
    assert len(events) == 1
    assert events[0]["output"] == "clean"
    assert events[0]["kind"] == "bash"


def test_prompt_key_lifts_issue_only():
    src = "Issue: first-issue\nRead docs/first-issue/PRD.md and build API"
    dst = "Issue: other-issue\nRead docs/other-issue/PRD.md and build API"
    assert normalize_task(src) == normalize_task(dst)
    assert normalize_task(src) != normalize_task(src.replace("build API", "build CLI"))


@pytest.mark.asyncio
async def test_trace_grounded_compiler_retries_and_publishes(tmp_path, monkeypatch):
    from runtime import skillcache_compiler
    generated = capsule()
    calls = []

    async def fake_provider(provider, prompt):
        calls.append(prompt)
        return json.dumps(generated)

    monkeypatch.setattr(skillcache_compiler, "_invoke_provider", fake_provider)
    trace = {"successful": True, "events": [{"kind": "terminal",
        "command": "python3 -c 'print(1)'", "output": "1", "exit_code": 0}]}
    path, detail = await compile_observation(
        root=tmp_path, role="codebase", provider="codex",
        request="same request", workspace_hash=digest(b"workspace"),
        source_skill="# Sample skill", trace=trace, sandbox="local-test"
    )
    assert path is not None, detail
    obj = json.loads(path.read_text())
    assert "examples" not in obj and obj["form"] == "hybrid"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_compiler_cold_fallback_with_no_evidence(tmp_path, monkeypatch):
    from runtime import skillcache_compiler
    called = []
    async def fake_provider(*args):
        called.append(1)
        return "{}"
    monkeypatch.setattr(skillcache_compiler, "_invoke_provider", fake_provider)
    path, reason = await compile_observation(
        root=tmp_path, role="codebase", provider="codex",
        request="task", workspace_hash=digest(b"workspace"),
        source_skill="skill", trace={"successful": False, "events": []},
        sandbox="local-test"
    )
    assert path is None
    assert not called


def test_docker_is_required_by_default(tmp_path, monkeypatch):
    from runtime import skillcache_executor
    monkeypatch.setattr(skillcache_executor.shutil, "which", lambda cmd: None)
    with pytest.raises(CapsuleError, match="docker unavailable"):
        Executor(capsule(), tmp_path)
