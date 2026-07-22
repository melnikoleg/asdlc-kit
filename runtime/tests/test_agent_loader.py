"""Agent definitions in .claude/agents/*.md parse correctly."""

from __future__ import annotations

import pytest

from runtime.agent_loader import AGENT_FILE, build_system_prompt, load_agent, resolve_model
from runtime.config import load_config


@pytest.mark.parametrize("node", list(AGENT_FILE))
def test_every_agent_loads(node, real_config):
    agent = load_agent(node, real_config)
    assert agent.name
    assert agent.model, f"{node} has no model in frontmatter"
    assert agent.tools, f"{node} has no tools in frontmatter"
    assert agent.body.strip(), f"{node} has an empty body"


def test_tools_are_parsed_as_list(real_config):
    dev = load_agent("developer", real_config)
    assert "Read" in dev.tools and "Bash" in dev.tools


def test_system_prompt_includes_rules(real_config):
    prompt = build_system_prompt(load_agent("reviewer", real_config), real_config)
    # CLAUDE.md + always-active rules are appended.
    assert "Project Rules" in prompt
    assert "SDLC" in prompt


def test_unknown_agent_raises(real_config):
    with pytest.raises(FileNotFoundError):
        load_agent("nonexistent", real_config)


# --- model tiering / overrides -------------------------------------------------

_MODEL_ENV = ("ASDLC_MODEL_SMART", "ASDLC_MODEL_WORKER") + tuple(
    f"ASDLC_MODEL_{n.upper()}" for n in AGENT_FILE
)


def _clear_model_env(monkeypatch):
    monkeypatch.delenv("ASDLC_REPO_ROOT", raising=False)
    monkeypatch.delenv("CHECKPOINT_BACKEND", raising=False)
    for var in _MODEL_ENV:
        monkeypatch.delenv(var, raising=False)


def test_no_env_keeps_frontmatter_model(monkeypatch):
    _clear_model_env(monkeypatch)
    cfg = load_config()
    # planner defaults to Opus in frontmatter after the tiering change.
    assert resolve_model("planner", "claude-opus-4-8", cfg) == "claude-opus-4-8"


def test_tier_env_overrides_frontmatter(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("ASDLC_MODEL_SMART", "smart-x")
    monkeypatch.setenv("ASDLC_MODEL_WORKER", "worker-y")
    cfg = load_config()
    # planner is a "smart" node, developer a "worker" node.
    assert resolve_model("planner", "frontmatter", cfg) == "smart-x"
    assert resolve_model("developer", "frontmatter", cfg) == "worker-y"


def test_per_node_override_beats_tier(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("ASDLC_MODEL_SMART", "smart-x")
    monkeypatch.setenv("ASDLC_MODEL_PLANNER", "planner-special")
    cfg = load_config()
    assert resolve_model("planner", "frontmatter", cfg) == "planner-special"


def test_load_agent_applies_override(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("ASDLC_MODEL_DEVELOPER", "cheap-dev-model")
    cfg = load_config()
    assert load_agent("developer", cfg).model == "cheap-dev-model"
