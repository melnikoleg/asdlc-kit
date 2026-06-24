"""Verdict extraction and the run_agent retry path."""

from __future__ import annotations

import pytest

from runtime import claude_runner
from runtime.claude_runner import AgentResult, extract_verdict, run_agent


def test_extracts_trailing_verdict():
    text = 'Here is my review.\n{"status":"APPROVED","artifacts":["a.md"],"issues":[]}\n'
    v = extract_verdict(text)
    assert v.status == "APPROVED"
    assert v.artifacts == ["a.md"]
    assert v.ok


def test_picks_last_valid_object():
    text = '{"status":"NEEDS_FIX"} then later {"status":"APPROVED","artifacts":[]}'
    assert extract_verdict(text).status == "APPROVED"


def test_ignores_non_verdict_json():
    text = '{"foo":"bar"} no verdict here'
    assert extract_verdict(text) is None


def test_handles_nested_braces():
    text = 'log {"a":{"b":1}}\n{"status":"FAILED","issues":[{"x":1}]}'
    assert extract_verdict(text).status == "FAILED"


@pytest.mark.asyncio
async def test_run_agent_retries_then_succeeds(real_config, monkeypatch):
    calls = {"n": 0}

    async def fake_collect(prompt, agent, config):
        calls["n"] += 1
        if calls["n"] == 1:
            return "no json at all"
        return '{"status":"APPROVED","artifacts":[]}'

    monkeypatch.setattr(claude_runner, "_collect_text", fake_collect)
    result = await run_agent("product", "do it", real_config)
    assert result.status == "APPROVED"
    assert calls["n"] == 2  # one retry


@pytest.mark.asyncio
async def test_run_agent_fails_when_no_verdict(real_config, monkeypatch):
    async def fake_collect(prompt, agent, config):
        return "still no verdict"

    monkeypatch.setattr(claude_runner, "_collect_text", fake_collect)
    result = await run_agent("product", "do it", real_config)
    assert result.status == "FAILED"
