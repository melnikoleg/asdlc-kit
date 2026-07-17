"""Bridge to Claude Code via the Claude Agent SDK, or the raw CLI as fallback.

Each generative graph node calls :func:`run_agent`, which launches a headless
Claude Code session configured from the agent's ``.claude/agents/*.md``
definition. We run with ``cwd = repo_root`` so guardrails (``.claude/settings.json``
hooks) stay enforced in one place rather than being duplicated in Python.

When ``config.anthropic_api_key`` is set we use the Claude Agent SDK (imported
lazily so the rest of the package works without it installed). When no key is
set, sessions run under the developer's local Claude Code subscription login;
the SDK still works there, but we instead shell out to ``claude -p`` directly
so this path has no dependency on the ``claude-agent-sdk`` pip package.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from .agent_loader import AgentDef, build_system_prompt, load_agent
from .config import Config

# Verdict statuses defined by .claude/rules/sdlc-contracts.md
VALID_STATUSES = {"APPROVED", "NEEDS_FIX", "FAILED"}


@dataclass
class Usage:
    """Real token/cost/timing usage captured from the SDK ``ResultMessage``.

    Feeds the metrics dashboard; all fields default to zero so a mock runner (or
    an SDK version that omits usage) degrades gracefully to a no-cost record.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    num_turns: int = 0
    model: str | None = None

    def merge(self, other: "Usage") -> "Usage":
        """Sum numeric usage across sessions (e.g. a run plus its retry)."""
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
            cost_usd=self.cost_usd + other.cost_usd,
            duration_ms=self.duration_ms + other.duration_ms,
            num_turns=self.num_turns + other.num_turns,
            model=self.model or other.model,
        )


@dataclass
class AgentResult:
    status: str  # APPROVED | NEEDS_FIX | FAILED
    artifacts: list[str] = field(default_factory=list)
    issues: list[Any] = field(default_factory=list)
    raw_text: str = ""
    usage: Usage | None = None

    @property
    def ok(self) -> bool:
        return self.status == "APPROVED"


def extract_verdict(text: str) -> AgentResult | None:
    """Pull the last well-formed JSON verdict object out of ``text``.

    Agents are instructed to END with a JSON verdict per the SDLC contract, so
    when several verdict-shaped objects appear we take the last valid one.
    """
    last: AgentResult | None = None
    for candidate in _json_objects(text):
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


def _json_objects(text: str):
    """Yield top-level brace-balanced JSON candidates from ``text``.

    A single forward pass that respects JSON string quoting and escapes, so a
    ``}`` inside a string value (e.g. an issue description like ``"missing }"``)
    does not prematurely close the object and drop an otherwise-valid verdict.
    """
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0:
                yield text[start : i + 1]


async def _run_session(prompt: str, agent: AgentDef, config: Config) -> tuple[str, Usage]:
    """Run one headless Claude Code session; return (assistant text, usage).

    Dispatches to the Agent SDK when an API key is configured, otherwise to a
    raw ``claude -p`` subprocess running under the local subscription login.
    """
    if config.anthropic_api_key:
        return await _run_session_sdk(prompt, agent, config)
    return await _run_session_cli(prompt, agent, config)


async def _run_session_sdk(prompt: str, agent: AgentDef, config: Config) -> tuple[str, Usage]:
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
    usage = Usage(model=agent.model)
    async for message in query(prompt=prompt, options=options):
        chunks.append(_message_text(message))
        message_usage = _usage_from_message(message)
        if message_usage is not None:
            usage = usage.merge(message_usage)
    return "".join(c for c in chunks if c), usage


async def _run_session_cli(prompt: str, agent: AgentDef, config: Config) -> tuple[str, Usage]:
    """Run one headless session via the ``claude`` CLI (no SDK/API key needed)."""
    args = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--append-system-prompt", build_system_prompt(agent, config),
        "--permission-mode", "acceptEdits",
    ]
    if agent.tools:
        args += ["--allowedTools", ",".join(agent.tools)]
    if agent.model:
        args += ["--model", agent.model]

    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(config.repo_root),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited {proc.returncode}: {stderr.decode(errors='replace')}"
        )

    payload = json.loads(stdout.decode())
    text = str(payload.get("result", ""))
    raw_usage = payload.get("usage") or {}
    usage = Usage(
        input_tokens=int(raw_usage.get("input_tokens", 0) or 0),
        output_tokens=int(raw_usage.get("output_tokens", 0) or 0),
        cache_read_tokens=int(raw_usage.get("cache_read_input_tokens", 0) or 0),
        cache_creation_tokens=int(raw_usage.get("cache_creation_input_tokens", 0) or 0),
        cost_usd=float(payload.get("total_cost_usd", 0.0) or 0.0),
        duration_ms=int(payload.get("duration_ms", 0) or 0),
        num_turns=int(payload.get("num_turns", 0) or 0),
        model=agent.model,
    )
    return text, usage


def _usage_from_message(message: Any) -> Usage | None:
    """Extract token/cost/timing from an SDK ``ResultMessage`` (best-effort)."""
    raw = getattr(message, "usage", None)
    cost = getattr(message, "total_cost_usd", None)
    duration = getattr(message, "duration_ms", None)
    turns = getattr(message, "num_turns", None)
    if raw is None and cost is None and duration is None:
        return None
    raw = raw if isinstance(raw, dict) else {}

    def _int(key: str) -> int:
        try:
            return int(raw.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0

    return Usage(
        input_tokens=_int("input_tokens"),
        output_tokens=_int("output_tokens"),
        cache_read_tokens=_int("cache_read_input_tokens"),
        cache_creation_tokens=_int("cache_creation_input_tokens"),
        cost_usd=float(cost or 0.0),
        duration_ms=int(duration or 0),
        num_turns=int(turns or 0),
    )


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

    Retries once with an explicit JSON-only nudge if no verdict is found. Token
    usage is accumulated across both attempts and attached to the result.
    """
    agent = load_agent(node, config)

    text, usage = await _run_session(prompt, agent, config)
    verdict = extract_verdict(text)
    if verdict is not None:
        verdict.usage = usage
        return verdict

    nudge = (
        prompt
        + "\n\nIMPORTANT: End your response with ONLY the JSON verdict object "
        + '{"status":"APPROVED|NEEDS_FIX|FAILED","artifacts":[],"issues":[]}'
    )
    text2, usage2 = await _run_session(nudge, agent, config)
    usage = usage.merge(usage2)
    verdict = extract_verdict(text2)
    if verdict is not None:
        verdict.usage = usage
        return verdict

    # No parseable verdict — treat as failure rather than silently passing.
    return AgentResult(
        status="FAILED", raw_text=text + "\n---retry---\n" + text2, usage=usage
    )
