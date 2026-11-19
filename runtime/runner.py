"""Provider dispatch for LangGraph agents. The node API stays provider-neutral."""
from __future__ import annotations

from .config import Config, validate_provider


async def run_agent(node: str, prompt: str, config: Config):
    provider = validate_provider(config.agent_providers.get(node, config.provider))
    if provider == "codex":
        from .codex_runner import run_agent as codex_run
        return await codex_run(node, prompt, config)
    from .claude_runner import run_agent as claude_run
    return await claude_run(node, prompt, config)
