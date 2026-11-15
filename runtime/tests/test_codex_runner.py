"""Codex JSONL parsing and the default headless Code Mode runner."""

import json

import pytest

from runtime.codex_runner import _codex_model, parse_codex_events, run_agent
from runtime import codex_runner


def test_codex_jsonl_collects_latest_message_and_turn_usage():
    events = [
        {"type": "item.completed", "item": {"type": "agent_message", "text": "draft"}},
        {"type": "turn.completed", "usage": {
            "input_tokens": 10, "output_tokens": 3, "cached_input_tokens": 2,
        }},
        {"type": "item.completed", "item": {"type": "agent_message", "text":
            '{"status":"APPROVED","artifacts":["PLAN.md"],"issues":[]}' }},
        {"type": "turn.completed", "usage": {"input_tokens": 5, "output_tokens": 2}},
    ]
    text, usage = parse_codex_events(
        "\n".join(json.dumps(e) for e in events), model="codex-test"
    )
    assert '"APPROVED"' in text
    assert usage.input_tokens == 15
    assert usage.output_tokens == 5
    assert usage.cache_read_tokens == 2
    assert usage.num_turns == 2


def test_codex_jsonl_fails_closed():
    with pytest.raises(RuntimeError, match="no final agent message"):
        parse_codex_events('{"type":"turn.completed"}')
    with pytest.raises(RuntimeError, match="reported an error"):
        parse_codex_events(
            '{"type":"item.completed","item":{"type":"agent_message","text":"fine"}}\n'
            '{"type":"turn.failed","message":"tool failed"}'
        )


def test_codex_does_not_use_claude_frontmatter_models(real_config):
    assert _codex_model("product", real_config) is None


@pytest.mark.asyncio
async def test_codex_runner_uses_code_mode_and_parses_verdict(real_config, monkeypatch):
    calls = {}

    class FakeProc:
        returncode = 0

        async def communicate(self, supplied):
            calls["prompt"] = supplied.decode()
            return (
                b'{"type":"item.completed","item":{"type":"agent_message",'
                b'"text":"{\\"status\\":\\"APPROVED\\",\\"artifacts\\":[],\\"issues\\":[]}"}}\n'
                b'{"type":"turn.completed","usage":{"input_tokens":9,"output_tokens":3}}\n',
                b"",
            )

    async def fake_subprocess(*args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr(codex_runner.asyncio, "create_subprocess_exec", fake_subprocess)
    verdict = await run_agent("product", "make a plan", real_config)
    assert verdict.ok
    assert verdict.usage.input_tokens == 9
    assert verdict.usage.num_turns == 1
    assert calls["args"][:3] == ("codex", "exec", "--json")
    assert "features.code_mode=true" in calls["args"]
    assert "features.code_mode_only=true" in calls["args"]
    assert "claude-" not in " ".join(calls["args"])
    assert "make a plan" in calls["prompt"]


@pytest.mark.asyncio
async def test_codex_runner_compatible_mode_without_code_mode(
    real_config, monkeypatch,
):
    from dataclasses import replace

    cfg = replace(real_config, code_mode=False)
    calls = {}

    class FakeProc:
        returncode = 0

        async def communicate(self, supplied):
            return (
                b'{"type":"item.completed","item":{"type":"agent_message",'
                b'"text":"{\\"status\\":\\"APPROVED\\"}"}}\n',
                b"",
            )

    async def fake_subprocess(*args, **kwargs):
        calls["args"] = args
        return FakeProc()

    monkeypatch.setattr(codex_runner.asyncio, "create_subprocess_exec", fake_subprocess)
    assert (await run_agent("qa", "review", cfg)).ok
    assert "features.code_mode=false" in calls["args"]
    assert "features.code_mode_only=false" in calls["args"]


@pytest.mark.asyncio
async def test_codex_runner_missing_binary_is_clear(real_config, monkeypatch):
    async def fake_subprocess(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(codex_runner.asyncio, "create_subprocess_exec", fake_subprocess)
    with pytest.raises(RuntimeError, match="codex CLI not found"):
        await run_agent("product", "do it", real_config)
