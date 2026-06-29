"""Agent definitions in .claude/agents/*.md parse correctly."""

from __future__ import annotations

import pytest

from runtime.agent_loader import AGENT_FILE, build_system_prompt, load_agent


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
