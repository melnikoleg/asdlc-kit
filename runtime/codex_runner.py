"""Codex CLI bridge: headless Code Mode is the default SDLC agent backend.

Runs one isolated `codex exec` per LangGraph node. The graph remains responsible
for approvals, deterministic validation, held-out tests and routing.
"""

from __future__ import annotations

import asyncio
import json
import time

from .agent_loader import NODE_TIER, build_system_prompt, load_agent
from .claude_runner import AgentResult, Usage, _env_with_runtime_bin, extract_verdict
from .config import Config


def _codex_model(node: str, config: Config) -> str | None:
    """Use only explicit Codex-compatible overrides, not Claude frontmatter."""
    if node in config.model_overrides:
        return config.model_overrides[node]
    tier = NODE_TIER.get(node)
    if tier == "smart":
        return config.model_smart
    if tier == "worker":
        return config.model_worker
    return None


def parse_codex_events(output: str, model: str | None = None) -> tuple[str, Usage]:
    """Extract the last agent message and accumulated usage from Codex JSONL."""
    final_text: str | None = None
    usage = Usage(model=model)
    failure: str | None = None

    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue  # CLI may include non-JSON warning lines in older builds
        if not isinstance(event, dict):
            continue

        kind = event.get("type")
        if kind == "item.completed":
            item = event.get("item") or {}
            if isinstance(item, dict) and item.get("type") == "agent_message":
                message = item.get("text")
                if isinstance(message, str):
                    final_text = message
        elif kind == "turn.completed":
            info = event.get("usage") or {}
            if not isinstance(info, dict):
                info = {}
            usage = usage.merge(
                Usage(
                    input_tokens=int(info.get("input_tokens") or 0),
                    output_tokens=int(info.get("output_tokens") or 0),
                    cache_read_tokens=int(info.get("cached_input_tokens") or 0),
                    num_turns=1,
                    model=model,
                )
            )
        elif kind in ("turn.failed", "error"):
            failure = str(event.get("message") or event.get("error") or kind)

    if failure:
        raise RuntimeError(f"codex CLI reported an error: {failure}")
    if final_text is None:
        raise RuntimeError("codex CLI returned no final agent message")
    return final_text, usage


async def _run_session(
    node: str, prompt: str, config: Config,
) -> tuple[str, Usage]:
    agent = load_agent(node, config)
    model = _codex_model(node, config)
    mode = "true" if config.code_mode else "false"

    args = [
        "codex", "exec", "--json",
        "--sandbox", "workspace-write",
        "-c", "approval_policy=never",
        "-c", f"features.code_mode={mode}",
        "-c", f"features.code_mode_only={mode}",
        "-",
    ]
    if model:
        args[2:2] = ["--model", model]

    full_prompt = (
        build_system_prompt(agent, config)
        + "\n\n# Execution context\n"
        + "You are running as the "
        + node
        + " agent in the deterministic asdlc-runtime pipeline.\n"
        + "Follow the SDLC artifact ownership rules. "
        + "End with the required machine-readable JSON verdict.\n\n"
        + "# Task\n"
        + prompt
    )

    started = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(config.repo_root),
            env=_env_with_runtime_bin(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise RuntimeError("codex CLI not found on PATH — install OpenAI Codex") from None

    stdout, stderr = await proc.communicate(full_prompt.encode("utf-8"))
    if proc.returncode != 0:
        details = stderr.decode(errors="replace")[-1600:]
        raise RuntimeError(
            f"codex CLI exited {proc.returncode}: {details}. "
            "If Code Mode is unavailable, set ASDLC_CODE_MODE=0; "
            "to use Claude instead, set ASDLC_AGENT_BACKEND=claude."
        )

    text, usage = parse_codex_events(stdout.decode(errors="replace"), model)
    usage.duration_ms = int((time.monotonic() - started) * 1000)
    return text, usage


async def run_agent(node: str, prompt: str, config: Config) -> AgentResult:
    """Execute a Codex node; retry once when no valid SDLC verdict is returned."""
    text, usage = await _run_session(node, prompt, config)
    verdict = extract_verdict(text)
    if verdict is not None:
        verdict.usage = usage
        return verdict

    nudge = (
        prompt
        + "\n\nIMPORTANT: End your response with ONLY the JSON verdict object "
        + '{"status":"APPROVED|NEEDS_FIX|FAILED","artifacts":[],"issues":[]}'
    )
    second_text, second_usage = await _run_session(node, nudge, config)
    usage = usage.merge(second_usage)
    verdict = extract_verdict(second_text)
    if verdict is not None:
        verdict.usage = usage
        return verdict
    return AgentResult(
        status="FAILED",
        raw_text=text + "\n---retry---\n" + second_text,
        usage=usage,
    )
