"""Tests for the OpenRouter agentic runner."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from runtime.agent_loader import AgentDef
from runtime.config import Config
from runtime.openrouter_runner import (
    _check_destructive,
    _execute_tool,
    run_openrouter_agent,
)


# ---------------------------------------------------------------------------
# Guardrail tests
# ---------------------------------------------------------------------------

def test_check_destructive_blocks_rm():
    assert _check_destructive("rm -rf /home") is not None


def test_check_destructive_blocks_force_push():
    assert _check_destructive("git push --force origin main") is not None


def test_check_destructive_allows_safe():
    assert _check_destructive("pytest runtime/tests/") is None
    assert _check_destructive("git status") is None


# ---------------------------------------------------------------------------
# Tool executor tests
# ---------------------------------------------------------------------------

def test_execute_read(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("line1\nline2\nline3\n")
    result = _execute_tool("Read", {"file_path": str(f)}, tmp_path)
    assert "line1" in result
    assert "line2" in result


def test_execute_read_with_offset_limit(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("a\nb\nc\nd\n")
    result = _execute_tool("Read", {"file_path": str(f), "offset": 1, "limit": 2}, tmp_path)
    assert "b" in result
    assert "c" in result
    assert "d" not in result


def test_execute_read_missing_file(tmp_path):
    result = _execute_tool("Read", {"file_path": str(tmp_path / "nope.txt")}, tmp_path)
    assert "not found" in result


def test_execute_write(tmp_path):
    dest = tmp_path / "sub" / "out.txt"
    result = _execute_tool("Write", {"file_path": str(dest), "content": "hello"}, tmp_path)
    assert dest.read_text() == "hello"
    assert "Written" in result


def test_execute_edit(tmp_path):
    f = tmp_path / "edit_me.txt"
    f.write_text("foo bar baz")
    result = _execute_tool(
        "Edit",
        {"file_path": str(f), "old_string": "bar", "new_string": "QUX"},
        tmp_path,
    )
    assert f.read_text() == "foo QUX baz"
    assert "Edited" in result


def test_execute_edit_not_found_string(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("hello")
    result = _execute_tool(
        "Edit",
        {"file_path": str(f), "old_string": "MISSING", "new_string": "x"},
        tmp_path,
    )
    assert "not found" in result


def test_execute_bash_safe(tmp_path):
    result = _execute_tool("Bash", {"command": "echo hello"}, tmp_path)
    assert "hello" in result


def test_execute_bash_blocked():
    result = _execute_tool("Bash", {"command": "rm -rf /"}, Path("/"))
    assert "Destructive" in result or "blocked" in result.lower()


def test_execute_glob(tmp_path):
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.py").write_text("x")
    (tmp_path / "c.txt").write_text("x")
    result = _execute_tool("Glob", {"pattern": "*.py"}, tmp_path)
    assert "a.py" in result
    assert "b.py" in result
    assert "c.txt" not in result


def test_execute_grep(tmp_path):
    f = tmp_path / "code.py"
    f.write_text("def foo():\n    pass\n")
    result = _execute_tool("Grep", {"pattern": "def foo", "path": str(tmp_path)}, tmp_path)
    assert "def foo" in result


def test_execute_unknown_tool(tmp_path):
    result = _execute_tool("WebSearch", {"query": "x"}, tmp_path)
    assert "unknown tool" in result


# ---------------------------------------------------------------------------
# run_openrouter_agent tests (mocked anthropic client)
# ---------------------------------------------------------------------------

def _make_agent(tools=("Read", "Write"), model="deepseek/deepseek-chat"):
    return AgentDef(
        name="test-agent",
        model=model,
        provider="openrouter",
        tools=tuple(tools),
        body="You are a test agent. Return a JSON verdict.",
    )


def _make_config(tmp_path):
    return Config(
        repo_root=tmp_path,
        anthropic_api_key=None,
        openrouter_api_key="sk-or-test",
        checkpoint_backend="sqlite",
        db_url=None,
        sqlite_path=tmp_path / "cp.sqlite",
        max_iterations=3,
    )


def _mock_response(text: str, stop_reason: str = "end_turn"):
    """Build a minimal mock anthropic response."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.stop_reason = stop_reason
    return resp


@pytest.mark.asyncio
async def test_run_openrouter_returns_approved(tmp_path):
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    agent = _make_agent()
    config = _make_config(tmp_path)

    verdict_text = '{"status":"APPROVED","artifacts":["docs/x/PRD.md"],"issues":[]}'

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response(
        f"Here is my work.\n{verdict_text}"
    )

    with patch("runtime.openrouter_runner.anthropic") as mock_anthropic:
        mock_anthropic.Anthropic.return_value = mock_client
        result = await run_openrouter_agent(agent, "Build a TODO API", config)

    assert result.status == "APPROVED"
    assert "docs/x/PRD.md" in result.artifacts


@pytest.mark.asyncio
async def test_run_openrouter_retries_then_approved(tmp_path):
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    agent = _make_agent()
    config = _make_config(tmp_path)

    verdict_text = '{"status":"NEEDS_FIX","artifacts":[],"issues":["missing section"]}'
    call_count = {"n": 0}

    def side_effect(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _mock_response("no verdict here at all")
        return _mock_response(verdict_text)

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = side_effect

    with patch("runtime.openrouter_runner.anthropic") as mock_anthropic:
        mock_anthropic.Anthropic.return_value = mock_client
        result = await run_openrouter_agent(agent, "do something", config)

    assert result.status == "NEEDS_FIX"
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_run_openrouter_fails_when_no_verdict(tmp_path):
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    agent = _make_agent()
    config = _make_config(tmp_path)

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response("nothing useful")

    with patch("runtime.openrouter_runner.anthropic") as mock_anthropic:
        mock_anthropic.Anthropic.return_value = mock_client
        result = await run_openrouter_agent(agent, "do something", config)

    assert result.status == "FAILED"


@pytest.mark.asyncio
async def test_run_openrouter_missing_api_key(tmp_path):
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    agent = _make_agent()
    config = Config(
        repo_root=tmp_path,
        anthropic_api_key=None,
        openrouter_api_key=None,  # missing
        checkpoint_backend="sqlite",
        db_url=None,
        sqlite_path=tmp_path / "cp.sqlite",
        max_iterations=3,
    )

    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        await run_openrouter_agent(agent, "do something", config)


@pytest.mark.asyncio
async def test_run_openrouter_tool_call_loop(tmp_path):
    """Model calls Read tool, gets result, then returns verdict."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    target = tmp_path / "data.txt"
    target.write_text("important content")

    agent = _make_agent(tools=("Read",))
    config = _make_config(tmp_path)

    verdict_text = '{"status":"APPROVED","artifacts":[],"issues":[]}'

    # First response: tool_use block asking to Read the file
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.id = "tu_1"
    tool_use_block.name = "Read"
    tool_use_block.input = {"file_path": str(target)}

    first_resp = MagicMock()
    first_resp.content = [tool_use_block]
    first_resp.stop_reason = "tool_use"

    # Second response: final text with verdict
    second_resp = _mock_response(f"Done. {verdict_text}")

    call_count = {"n": 0}

    def side_effect(**kwargs):
        call_count["n"] += 1
        return first_resp if call_count["n"] == 1 else second_resp

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = side_effect

    with patch("runtime.openrouter_runner.anthropic") as mock_anthropic:
        mock_anthropic.Anthropic.return_value = mock_client
        result = await run_openrouter_agent(agent, "read the file", config)

    assert result.status == "APPROVED"
    assert call_count["n"] == 2
