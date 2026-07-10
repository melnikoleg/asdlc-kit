"""Verdict extraction and the run_agent retry path."""

from __future__ import annotations

import pytest

from runtime import claude_runner
from runtime.claude_runner import AgentResult, Usage, extract_verdict, run_agent


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


def test_brace_inside_string_does_not_truncate_verdict():
    # A '}' inside a string value must not prematurely close the object.
    text = '{"status":"NEEDS_FIX","issues":["unbalanced } brace in message"]}'
    v = extract_verdict(text)
    assert v is not None and v.status == "NEEDS_FIX"
    assert v.issues == ["unbalanced } brace in message"]


def test_escaped_quote_inside_string_is_handled():
    text = r'{"status":"FAILED","issues":["he said \"oops}\" loudly"]}'
    v = extract_verdict(text)
    assert v is not None and v.status == "FAILED"


@pytest.mark.asyncio
async def test_run_agent_retries_then_succeeds(real_config, monkeypatch):
    calls = {"n": 0}

    async def fake_session(prompt, agent, config):
        calls["n"] += 1
        if calls["n"] == 1:
            return "no json at all", Usage(input_tokens=10, output_tokens=5, cost_usd=0.01)
        return '{"status":"APPROVED","artifacts":[]}', Usage(input_tokens=20, output_tokens=7, cost_usd=0.02)

    monkeypatch.setattr(claude_runner, "_run_session", fake_session)
    result = await run_agent("product", "do it", real_config)
    assert result.status == "APPROVED"
    assert calls["n"] == 2  # one retry
    # Usage is summed across the failed attempt and the retry.
    assert result.usage.input_tokens == 30
    assert result.usage.output_tokens == 12
    assert result.usage.cost_usd == pytest.approx(0.03)


@pytest.mark.asyncio
async def test_run_agent_fails_when_no_verdict(real_config, monkeypatch):
    async def fake_session(prompt, agent, config):
        return "still no verdict", Usage(input_tokens=3)

    monkeypatch.setattr(claude_runner, "_run_session", fake_session)
    result = await run_agent("product", "do it", real_config)
    assert result.status == "FAILED"
    assert result.usage.input_tokens == 6  # both attempts counted


def test_usage_from_result_message():
    class FakeResult:
        usage = {
            "input_tokens": 100,
            "output_tokens": 40,
            "cache_read_input_tokens": 12,
        }
        total_cost_usd = 0.0123
        duration_ms = 4200
        num_turns = 3

    u = claude_runner._usage_from_message(FakeResult())
    assert u.input_tokens == 100 and u.output_tokens == 40
    assert u.cache_read_tokens == 12
    assert u.cost_usd == pytest.approx(0.0123)
    assert u.duration_ms == 4200 and u.num_turns == 3


def test_usage_from_message_ignores_plain_text_blocks():
    class TextOnly:
        content = "hello"

    assert claude_runner._usage_from_message(TextOnly()) is None
