"""Noninteractive Codex CLI adapter with Claude-compatible AgentResult.

Uses codex exec --json, explicitly providing the existing agent role instructions
as prompt content. Codex CLI does not enforce Claude Code hooks/tool allowlists.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from .agent_loader import AgentDef, build_system_prompt, load_agent
from .claude_runner import AgentResult, Usage, extract_verdict
from .config import Config


def _is_git_workspace(path: Path) -> bool:
    return any((p / ".git").exists() for p in (path, *path.parents))


def build_codex_command(agent: AgentDef, config: Config) -> list[str]:
    # A read-only role cannot modify files; developers and other writers need
    # workspace-write. Bash may write temporary files/tests, so it also opts in.
    writable = bool(set(agent.tools) & {"Write", "Edit", "Bash"})
    sandbox = "workspace-write" if writable else "read-only"
    args = ["codex", "exec", "--json", "--sandbox", sandbox, "--ephemeral"]
    if agent.model:
        args.extend(["--model", agent.model])
    if not _is_git_workspace(config.repo_root):
        args.append("--skip-git-repo-check")
    args.append("-")  # pass prompt via stdin (not a shell command)
    return args


def parse_codex_events(output: str, model: str | None) -> tuple[str, Usage]:
    """Extract the final agent message and real usage from Codex JSONL."""
    message = ""
    usage = Usage(model=model)
    errors: list[str] = []
    completed = False
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if event_type == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                message = str(item.get("text") or "")
        elif event_type == "turn.completed":
            completed = True
            counts = event.get("usage") or {}
            if isinstance(counts, dict):
                usage.input_tokens += int(counts.get("input_tokens") or 0)
                usage.output_tokens += int(counts.get("output_tokens") or 0)
                usage.cache_read_tokens += int(counts.get("cached_input_tokens") or 0)
            usage.num_turns += 1
        elif event_type in {"turn.failed", "error"}:
            raw = event.get("error") or event.get("message") or "Codex turn failed"
            errors.append(str(raw)[-1000:])
    if errors:
        raise RuntimeError("codex CLI reported error: " + "; ".join(errors[-2:]))
    if not completed:
        raise RuntimeError("codex CLI returned no completed turn")
    if not message:
        raise RuntimeError("codex CLI returned no final agent message")
    # Codex JSONL provides token counts but not a verified monetary price.
    return message, usage


async def _run_session(prompt: str, agent: AgentDef, config: Config) -> tuple[str, Usage]:
    instructions = build_system_prompt(agent, config)
    full_prompt = (
        instructions + "\n\n## Current task\n" + prompt
        + "\n\nFinish with a JSON object containing status, artifacts and issues. "
          "Use APPROVED, NEEDS_FIX or FAILED as the status."
    )
    args = build_codex_command(agent, config)
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(config.repo_root),
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise RuntimeError("codex CLI not found on PATH - install/authenticate Codex") from None

    stdout, stderr = await process.communicate(input=full_prompt.encode("utf-8"))
    if process.returncode != 0:
        raise RuntimeError(
            f"codex CLI exited {process.returncode}: "
            + stderr.decode("utf-8", "replace")[-1500:]
        )
    return parse_codex_events(stdout.decode("utf-8", "replace"), agent.model)


async def run_agent(node: str, prompt: str, config: Config) -> AgentResult:
    agent = load_agent(node, config)
    first_text, first_usage = await _run_session(prompt, agent, config)
    first = extract_verdict(first_text)
    if first is not None:
        first.usage = first_usage
        return first
    retry_text, retry_usage = await _run_session(
        prompt + '\n\nIMPORTANT: Finish with ONLY a valid JSON verdict: '
        + '{"status":"APPROVED|NEEDS_FIX|FAILED","artifacts":[],"issues":[]}',
        agent, config,
    )
    usage = first_usage.merge(retry_usage)
    result = extract_verdict(retry_text)
    if result is None:
        return AgentResult(
            status="FAILED",
            raw_text=first_text + "\n---retry---\n" + retry_text,
            usage=usage,
        )
    result.usage = usage
    return result
