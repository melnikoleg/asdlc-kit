"""Agentic loop for cheap models via OpenRouter's Anthropic-compatible endpoint.

OpenRouter exposes ``https://openrouter.ai/api/v1`` which accepts the same
message/tool-use format as the Anthropic API.  We instantiate
``anthropic.Anthropic(base_url=..., api_key=OPENROUTER_API_KEY)`` and run a
standard tool-call loop, executing each requested tool locally.

This runner is used when an agent's frontmatter contains ``provider: openrouter``.
It gives cheap coding models (DeepSeek, Qwen, Gemini Flash, etc.) the same
file-system and shell capabilities that Claude Code agents have, without going
through the Claude Agent SDK subprocess path.
"""

from __future__ import annotations

import glob as glob_module
import subprocess
from pathlib import Path
from typing import Any

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore[assignment]

from .agent_loader import AgentDef, build_system_prompt
from .claude_runner import AgentResult, extract_verdict
from .config import Config

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Patterns mirrored from .claude/hooks/block-destructive.sh
_DESTRUCTIVE_PATTERNS = [
    "rm -rf /",
    "rm -rf ~",
    "git push --force",
    "git push -f",
    "git reset --hard",
    "> /dev/sda",
    "mkfs",
    "dd if=",
]

# Anthropic tool schemas for each supported tool name.
_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "Read": {
        "name": "Read",
        "description": "Read the contents of a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file"},
                "offset": {"type": "integer", "description": "Line number to start reading from (0-based)"},
                "limit": {"type": "integer", "description": "Maximum number of lines to read"},
            },
            "required": ["file_path"],
        },
    },
    "Write": {
        "name": "Write",
        "description": "Write content to a file, creating it (and parent directories) if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["file_path", "content"],
        },
    },
    "Edit": {
        "name": "Edit",
        "description": "Replace an exact string in a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file"},
                "old_string": {"type": "string", "description": "Exact string to find"},
                "new_string": {"type": "string", "description": "Replacement string"},
            },
            "required": ["file_path", "old_string", "new_string"],
        },
    },
    "Bash": {
        "name": "Bash",
        "description": "Run a shell command and return stdout + stderr.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
            },
            "required": ["command"],
        },
    },
    "Glob": {
        "name": "Glob",
        "description": "Find files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py')"},
                "path": {"type": "string", "description": "Directory to search in (defaults to repo root)"},
            },
            "required": ["pattern"],
        },
    },
    "Grep": {
        "name": "Grep",
        "description": "Search for a regex pattern in files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "path": {"type": "string", "description": "File or directory to search"},
                "glob": {"type": "string", "description": "File glob filter (e.g. '*.py')"},
            },
            "required": ["pattern"],
        },
    },
}


def _check_destructive(command: str) -> str | None:
    """Return a reason string if the command matches a destructive pattern, else None."""
    for pat in _DESTRUCTIVE_PATTERNS:
        if pat in command:
            return f"Destructive command blocked: matched pattern '{pat}'"
    return None


def _execute_tool(name: str, inputs: dict[str, Any], cwd: Path) -> str:
    """Execute a tool call locally and return a string result."""
    if name == "Read":
        path = Path(inputs["file_path"])
        try:
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        offset = int(inputs.get("offset") or 0)
        limit = inputs.get("limit")
        lines = lines[offset:]
        if limit is not None:
            lines = lines[: int(limit)]
        # Prefix with line numbers (1-based from offset)
        numbered = "".join(
            f"{offset + i + 1}\t{line}" for i, line in enumerate(lines)
        )
        return numbered or "(empty file)"

    if name == "Write":
        path = Path(inputs["file_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(inputs["content"], encoding="utf-8")
        return f"Written {len(inputs['content'])} bytes to {path}"

    if name == "Edit":
        path = Path(inputs["file_path"])
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        old = inputs["old_string"]
        new = inputs["new_string"]
        if old not in text:
            return f"Error: old_string not found in {path}"
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        return f"Edited {path}"

    if name == "Bash":
        command = inputs["command"]
        reason = _check_destructive(command)
        if reason:
            return f"Error: {reason}"
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=120,
        )
        output = result.stdout
        if result.stderr:
            output += "\n[stderr]\n" + result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output or "(no output)"

    if name == "Glob":
        search_root = Path(inputs.get("path") or cwd)
        pattern = inputs["pattern"]
        # Make pattern relative to search_root for glob
        full_pattern = str(search_root / pattern)
        matches = glob_module.glob(full_pattern, recursive=True)
        if not matches:
            return "(no matches)"
        return "\n".join(sorted(matches))

    if name == "Grep":
        pattern = inputs["pattern"]
        path = inputs.get("path") or str(cwd)
        args = ["grep", "-rn", "--color=never", pattern, path]
        glob_filter = inputs.get("glob")
        if glob_filter:
            args = ["grep", "-rn", "--color=never", f"--include={glob_filter}", pattern, path]
        result = subprocess.run(args, capture_output=True, text=True, cwd=str(cwd))
        return result.stdout or "(no matches)"

    return f"Error: unknown tool '{name}'"


async def run_openrouter_agent(agent: AgentDef, prompt: str, config: Config) -> AgentResult:
    """Run an agent via OpenRouter using the Anthropic SDK with a custom base_url.

    Implements an agentic loop: send → handle tool_use → send results → repeat
    until the model returns a text-only stop_reason.  Retries once with a JSON
    nudge if no verdict is found, mirroring the Claude runner behaviour.
    """
    if anthropic is None:  # pragma: no cover
        raise RuntimeError(
            "anthropic package is required for OpenRouter support. "
            "Install it: pip install anthropic"
        )

    if not config.openrouter_api_key:
        raise ValueError(
            "OPENROUTER_API_KEY environment variable is not set. "
            "Required when an agent uses provider: openrouter."
        )

    client = anthropic.Anthropic(
        base_url=OPENROUTER_BASE_URL,
        api_key=config.openrouter_api_key,
    )

    system_prompt = build_system_prompt(agent, config)
    tools = [_TOOL_SCHEMAS[t] for t in agent.tools if t in _TOOL_SCHEMAS]
    model = agent.model or "deepseek/deepseek-chat"

    text = await _run_loop(client, model, system_prompt, prompt, tools, config.repo_root)
    verdict = extract_verdict(text)
    if verdict is not None:
        return verdict

    nudge = (
        prompt
        + "\n\nIMPORTANT: End your response with ONLY the JSON verdict object "
        + '{"status":"APPROVED|NEEDS_FIX|FAILED","artifacts":[],"issues":[]}'
    )
    text2 = await _run_loop(client, model, system_prompt, nudge, tools, config.repo_root)
    verdict = extract_verdict(text2)
    if verdict is not None:
        return verdict

    return AgentResult(status="FAILED", raw_text=text + "\n---retry---\n" + text2)


async def _run_loop(
    client: Any,
    model: str,
    system: str,
    user_prompt: str,
    tools: list[dict],
    cwd: Path,
) -> str:
    """Drive the tool-call loop and return the final assistant text."""
    messages: list[dict] = [{"role": "user", "content": user_prompt}]
    text_chunks: list[str] = []

    while True:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": 8192,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = client.messages.create(**kwargs)

        # Collect text from this turn.
        turn_text = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                turn_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(block)

        if turn_text:
            text_chunks.append(turn_text)

        # Append assistant message to history.
        messages.append({"role": "assistant", "content": response.content})

        if not tool_calls or response.stop_reason == "end_turn":
            break

        # Execute tools and build tool_result message.
        tool_results = []
        for call in tool_calls:
            result_text = _execute_tool(call.name, call.input, cwd)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": result_text,
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return "".join(text_chunks)
