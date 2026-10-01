"""LangGraph orchestrator for the Agentic SDLC Kit.

Adds a deterministic orchestration layer (topology, gates, loop limits,
durable checkpoints) on top of the native Claude Code agents in ``.claude/``.
The agents, rules and hooks remain the single source of truth — this package
loads and runs them, it does not re-implement their prompts.
"""

__version__ = "0.1.0"
