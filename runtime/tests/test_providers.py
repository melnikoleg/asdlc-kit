
"""Multi-provider routing, persistence, and Codex CLI JSONL integration."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from runtime.agent_loader import load_agent
from runtime.claude_runner import AgentResult, Usage
from runtime.codex_runner import build_codex_command, parse_codex_events
from runtime.config import (
    configure_providers, load_config, parse_agent_provider_args, required_providers,
)
from runtime.runner import run_agent
from runtime.state import new_state, mirror_to_disk


def test_default_is_claude(monkeypatch):
    monkeypatch.delenv("ASDLC_PROVIDER", raising=False)
    monkeypatch.delenv("ASDLC_PROVIDER_DEVELOPER", raising=False)
    cfg = load_config()
    assert cfg.provider == "claude"
    assert "claude" in required_providers(cfg)


def test_codex_only_does_not_need_claude(real_config):
    cfg = configure_providers(real_config, "codex", {}, replace_overrides=True)
    assert required_providers(cfg) == {"codex"}
    agent = load_agent("product", cfg)
    assert agent.model is None or "codex" in agent.model.lower() or agent.model == cfg.codex_model
    assert "--model" not in build_codex_command(agent, replace(cfg, codex_model=None,
                                                           codex_model_smart=None,
                                                           codex_model_overrides={}))


def test_hybrid_and_role_parsing(real_config):
    overrides = parse_agent_provider_args(["developer=codex", "reviewer=claude"])
    cfg = configure_providers(real_config, "claude", overrides, replace_overrides=True)
    assert cfg.agent_providers == overrides
    assert required_providers(cfg) == {"claude", "codex"}
    assert "codex" not in required_providers(cfg, devops=False) - {"claude", "codex"}


@pytest.mark.parametrize("value", ["nope", "", "CLAUDE", "openai"])
def test_reject_invalid_provider(real_config, value):
    with pytest.raises(ValueError, match="provider"):
        configure_providers(real_config, value)


def test_reject_unknown_node(real_config):
    with pytest.raises(ValueError, match="unknown agent"):
        configure_providers(real_config, agent_providers={"stranger": "codex"})


def test_reject_malformed_override():
    with pytest.raises(ValueError):
        parse_agent_provider_args(["developer-codex"])


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("ASDLC_PROVIDER", "codex")
    monkeypatch.setenv("ASDLC_PROVIDER_REVIEWER", "claude")
    monkeypatch.setenv("ASDLC_CODEX_MODEL", "my-codex")
    cfg = load_config()
    assert cfg.provider == "codex"
    assert cfg.agent_providers["reviewer"] == "claude"
    assert load_agent("developer", cfg).model == "my-codex"
    assert load_agent("reviewer", cfg).model != "my-codex"


def test_choices_persist_in_state(tmp_path):
    state = new_state("orders", "build an order API", provider="codex",
                      agent_providers={"reviewer": "claude"})
    assert state["provider"] == "codex"
    assert state["agent_providers"] == {"reviewer": "claude"}
    snapshot = json.loads(mirror_to_disk(state, tmp_path).read_text())
    assert snapshot["provider"] == "codex"


def test_codex_events_and_usage():
    payload = "\n".join(json.dumps(e) for e in [
        {"type": "thread.started", "thread_id": "sample"},
        {"type": "item.completed", "item": {"type": "command_execution", "command": "ls"}},
        {"type": "item.completed", "item": {
            "type": "agent_message",
            "text": '{"status":"APPROVED","artifacts":["PLAN.md"],"issues":[]}',
        }},
        {"type": "turn.completed", "usage": {
            "input_tokens": 120, "cached_input_tokens": 80, "output_tokens": 30,
        }},
    ])
    text, usage = parse_codex_events(payload, "codex-model")
    assert '"APPROVED"' in text
    assert usage.provider == "codex"
    assert usage.input_tokens == 120 and usage.output_tokens == 30
    assert usage.cache_read_tokens == 80 and usage.num_turns == 1
    assert usage.cost_usd == 0


def test_codex_error_fails_closed():
    with pytest.raises(RuntimeError, match="reported error"):
        parse_codex_events(json.dumps({"type": "turn.failed", "error": "oops"}), None)
    with pytest.raises(RuntimeError, match="no completed turn"):
        parse_codex_events(json.dumps({"type": "item.completed",
                                       "item": {"type": "agent_message", "text": "hi"}}), None)


@pytest.mark.asyncio
async def test_provider_dispatch(real_config, monkeypatch):
    from runtime import claude_runner, codex_runner

    called = []
    async def fake_claude(node, prompt, config):
        called.append("claude")
        return AgentResult(status="APPROVED", usage=Usage(provider="claude"))
    async def fake_codex(node, prompt, config):
        called.append("codex")
        return AgentResult(status="APPROVED", usage=Usage(provider="codex"))

    monkeypatch.setattr(claude_runner, "run_agent", fake_claude)
    monkeypatch.setattr(codex_runner, "run_agent", fake_codex)
    cfg = configure_providers(real_config, "codex", {"reviewer": "claude"},
                              replace_overrides=True)
    assert (await run_agent("developer", "do it", cfg)).usage.provider == "codex"
    assert (await run_agent("reviewer", "review", cfg)).usage.provider == "claude"
    assert called == ["codex", "claude"]


@pytest.mark.asyncio
async def test_codex_subprocess_receives_role_instructions(real_config, monkeypatch):
    from runtime import codex_runner

    captured = {}
    class FakeProcess:
        returncode = 0
        async def communicate(self, input):
            captured["prompt"] = input.decode("utf-8")
            result = [
                {"type": "item.completed", "item": {
                    "type": "agent_message", "text": '{"status":"APPROVED","artifacts":[]}'
                }},
                {"type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 2}},
            ]
            return "\n".join(json.dumps(x) for x in result).encode("utf-8"), b""

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        return FakeProcess()

    monkeypatch.setattr(codex_runner.asyncio, "create_subprocess_exec", fake_exec)
    cfg = configure_providers(real_config, "codex", {}, replace_overrides=True)
    result = await codex_runner.run_agent("product", "Make a PRD", cfg)
    assert result.ok
    assert result.usage.provider == "codex"
    assert captured["args"][:3] == ("codex", "exec", "--json")
    assert "Product Agent" in captured["prompt"]
    assert "Make a PRD" in captured["prompt"]
    assert "--sandbox" in captured["args"]
