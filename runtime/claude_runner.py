"""Bridge to Claude Code via the Claude Agent SDK.

Each generative graph node calls :func:`run_agent`, which launches a headless
Claude Code session configured from the agent's ``.claude/agents/*.md``
definition. We run with ``cwd = repo_root`` so the SDK picks up the project's
``.claude/settings.json`` hooks — guardrails stay enforced in one place rather
than being duplicated in Python.

The SDK is imported lazily so the rest of the package (state, validation,
graph wiring, tests with a mock runner) works without the SDK installed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .agent_loader import AgentDef, build_system_prompt, load_agent
from .config import Config

# Verdict statuses defined by .claude/rules/sdlc-contracts.md
VALID_STATUSES = {"APPROVED", "NEEDS_FIX", "FAILED"}


@dataclass
class AgentResult:
    status: str  # APPROVED | NEEDS_FIX | FAILED
    artifacts: list[str] = field(default_factory=list)
    issues: list[Any] = field(default_factory=list)
    raw_text: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "APPROVED"


def extract_verdict(text: str) -> AgentResult | None:
    """Pull the last well-formed JSON verdict object out of ``text``.

    Agents are instructed to END with a JSON verdict per the SDLC contract, so
    when several verdict-shaped objects appear we take the last valid one.
    """
    last: AgentResult | None = None
    for candidate in _balanced_objects(text):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        status = str(data.get("status", "")).upper()
        if status in VALID_STATUSES:
            last = AgentResult(
                status=status,
                artifacts=list(data.get("artifacts", []) or []),
                issues=list(data.get("issues", []) or []),
                raw_text=text,
            )
    return last


def _balanced_objects(text: str):
    """Yield substrings of ``text`` that are brace-balanced JSON candidates."""
    starts = [i for i, c in enumerate(text) if c == "{"]
    for start in starts:
        depth = 0
        for end in range(start, len(text)):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    yield text[start : end + 1]
                    break


async def _collect_text(prompt: str, agent: AgentDef, config: Config) -> str:
    """Run one headless Claude Code session and return all assistant text."""
    from claude_agent_sdk import ClaudeAgentOptions, query  # lazy import

    options = ClaudeAgentOptions(
        system_prompt=build_system_prompt(agent, config),
        allowed_tools=list(agent.tools),
        permission_mode="acceptEdits",
        cwd=str(config.repo_root),
        model=agent.model,
        # Load the project's settings (hooks) so guardrails stay active.
        setting_sources=["project"],
    )

    chunks: list[str] = []
    async for message in query(prompt=prompt, options=options):
        chunks.append(_message_text(message))
    return "".join(c for c in chunks if c)


def _message_text(message: Any) -> str:
    """Best-effort text extraction across SDK message types/versions."""
    # ResultMessage exposes a final `.result` string.
    result = getattr(message, "result", None)
    if isinstance(result, str):
        return result
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for block in content:
            block_text = getattr(block, "text", None)
            if isinstance(block_text, str):
                out.append(block_text)
        return "".join(out)
    return ""


async def run_agent(node: str, prompt: str, config: Config) -> AgentResult:
    """Load the agent for ``node`` and run it, returning its parsed verdict.

    Retries once with an explicit JSON-only nudge if no verdict is found.
    """
    agent = load_agent(node, config)

    text = await _collect_text(prompt, agent, config)
    verdict = extract_verdict(text)
    if verdict is not None:
        return verdict

    nudge = (
        prompt
        + "\n\nIMPORTANT: End your response with ONLY the JSON verdict object "
        + '{"status":"APPROVED|NEEDS_FIX|FAILED","artifacts":[],"issues":[]}'
    )
    text2 = await _collect_text(nudge, agent, config)
    verdict = extract_verdict(text2)
    if verdict is not None:
        return verdict

    # No parseable verdict — treat as failure rather than silently passing.
    return AgentResult(status="FAILED", raw_text=text + "\n---retry---\n" + text2)
