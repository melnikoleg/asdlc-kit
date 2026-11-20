"""Provider-neutral, opt-in observation capture for one completed skill invocation.

Capture only bounded sanitized command/tool evidence. Raw credential-bearing
provider logs are never written to disk. Redaction is best-effort, not a
confidentiality guarantee; enable only in trusted project workspaces.
"""
from __future__ import annotations

import json
import re
from typing import Any

MAX_EVENTS = 96
MAX_TRACE_BYTES = 128 * 1024
MAX_TEXT = 1536

SECRET_PATTERNS = (
    re.compile(r"(?i)(?:sk-[a-zA-Z0-9_-]{15,}|gh[pousr]_[a-zA-Z0-9_-]{15,}|"
               r"AKIA[0-9A-Z]{16})"),
    re.compile(r"(?i)\b(authorization|api[_-]?key|password|secret|token|"
               r"private[_-]?key)\b\s*[:=]\s*[^\s,;]+"),
)
PRIVATE_COMMAND = re.compile(
    r"(?i)(?:\bprintenv\b|\benv\b|\bsecret\b|\bpassword\b|"
    r"\b\.env\b|\bssh\b|\bid_rsa\b|\bcredential\b|"
    r"\btoken\b|\bcurl\b|\bwget\b|\brm\b|\bsudo\b)"
)


def sanitize(text: Any) -> str:
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False, default=str)
    for regex in SECRET_PATTERNS:
        text = regex.sub("[REDACTED]", text)
    return text[:MAX_TEXT]


def _append(events: list[dict[str, Any]], operation: dict[str, Any]) -> None:
    if len(events) >= MAX_EVENTS:
        return
    if len(json.dumps(events, ensure_ascii=False).encode()) > MAX_TRACE_BYTES - 2048:
        return
    command = operation.get("command") or ""
    if PRIVATE_COMMAND.search(command):
        return
    events.append(operation)


def codex_trace(raw: str) -> list[dict[str, Any]]:
    """Extract completed terminal calls from codex exec --json JSONL."""
    events: list[dict[str, Any]] = []
    for line in raw.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict) or item.get("type") != "item.completed":
            continue
        body = item.get("item") or {}
        if not isinstance(body, dict):
            continue
        if body.get("type") == "command_execution":
            command = body.get("command")
            if not isinstance(command, str):
                continue
            _append(events, {
                "kind": "terminal",
                "command": sanitize(command),
                "exit_code": body.get("exit_code"),
                "output": sanitize(body.get("aggregated_output", "")),
            })
        elif body.get("type") == "file_change":
            # Record only a summary of file changes. The compiler must not
            # silently turn an unobserved edit into a deterministic program.
            changes = body.get("changes") or []
            _append(events, {
                "kind": "file_change",
                "summary": sanitize([str(c.get("path", "")) for c in changes
                                     if isinstance(c, dict)][:12]),
            })
    return events


def claude_trace(raw: str) -> list[dict[str, Any]]:
    """Pair Claude stream-json tool_use IDs and tool_result observations."""
    events: list[dict[str, Any]] = []
    pending: dict[str, dict[str, Any]] = {}
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        msg = event.get("message") or {}
        if not isinstance(msg, dict):
            continue
        content = msg.get("content") or []
        if not isinstance(content, list):
            continue
        if event.get("type") == "assistant":
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "tool_use":
                    continue
                tool = str(item.get("name") or "")
                if tool not in ("Bash", "Read", "Glob", "Grep"):
                    continue
                args = item.get("input") or {}
                if not isinstance(args, dict):
                    continue
                command = args.get("command") if tool == "Bash" else (
                    args.get("file_path") or args.get("path") or args.get("pattern") or ""
                )
                if not isinstance(command, str) or PRIVATE_COMMAND.search(command):
                    continue
                ident = str(item.get("id") or "")
                if ident:
                    pending[ident] = {"kind": tool.lower(), "command": sanitize(command)}
        elif event.get("type") == "user":
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "tool_result":
                    continue
                ident = str(item.get("tool_use_id") or "")
                pending_result = pending.pop(ident, None)
                if pending_result is None:
                    continue
                content_value = item.get("content") or ""
                if isinstance(content_value, list):
                    content_value = " ".join(str(c.get("text", "")) for c in content_value
                                             if isinstance(c, dict))
                pending_result["output"] = sanitize(content_value)
                pending_result["failed"] = bool(item.get("is_error", False))
                _append(events, pending_result)
    return events


def observation(role: str, provider: str, raw: str, *, successful: bool) -> dict[str, Any]:
    from datetime import datetime, timezone

    return {
        "schema_version": 1,
        "role": role,
        "provider": provider,
        "successful": bool(successful),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "events": codex_trace(raw) if provider == "codex" else claude_trace(raw),
    }
