"""Bridge to Claude Code via headless ``claude -p``.

Each generative graph node calls :func:`run_agent`, which launches one
``claude -p`` session configured from the agent's ``.claude/agents/*.md``
definition. We run with ``cwd = repo_root`` so guardrails (``.claude/settings.json``
hooks) stay enforced in one place rather than being duplicated in Python.
Auth is whatever the local ``claude`` login already holds.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

from .agent_loader import AgentDef, build_system_prompt, load_agent
from .config import Config

# Verdict statuses defined by .claude/rules/sdlc-contracts.md
VALID_STATUSES = {"APPROVED", "NEEDS_FIX", "FAILED"}


@dataclass
class Usage:
    """Real token/cost/timing usage captured from ``claude -p --output-format json``.

    Feeds the metrics dashboard; all fields default to zero so a mock runner (or
    a payload that omits usage) degrades gracefully to a no-cost record.
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


def _usage_from_payload(payload: dict[str, Any], model: str | None) -> Usage:
    raw = payload.get("usage") or {}

    def _int(key: str) -> int:
        return int(raw.get(key, 0) or 0)

    return Usage(
        input_tokens=_int("input_tokens"),
        output_tokens=_int("output_tokens"),
        cache_read_tokens=_int("cache_read_input_tokens"),
        cache_creation_tokens=_int("cache_creation_input_tokens"),
        cost_usd=float(payload.get("total_cost_usd", 0.0) or 0.0),
        duration_ms=int(payload.get("duration_ms", 0) or 0),
        num_turns=int(payload.get("num_turns", 0) or 0),
        model=model,
    )


def _env_with_runtime_bin() -> dict[str, str]:
    """Put this interpreter's bin dir on PATH so agents can call ``asdlc-e2e``."""
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    return env


async def _run_session(prompt: str, agent: AgentDef, config: Config) -> tuple[str, Usage]:
    """Run one headless ``claude -p`` session; return (assistant text, usage)."""
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

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(config.repo_root),
            env=_env_with_runtime_bin(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise RuntimeError("claude CLI not found on PATH - install Claude Code") from None
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited {proc.returncode}: {stderr.decode(errors='replace')}"
        )

    try:
        payload = json.loads(stdout.decode())
    except json.JSONDecodeError:
        raise RuntimeError(
            f"claude CLI returned non-JSON output: {stdout.decode(errors='replace')[-500:]}"
        ) from None
    return str(payload.get("result", "")), _usage_from_payload(payload, agent.model)


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
