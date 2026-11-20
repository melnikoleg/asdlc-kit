"""Per-async-task trace buffer, preventing parallel LangGraph agents mixing logs."""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from .skillcache_trace import codex_trace, claude_trace

BUFFER: ContextVar[list[dict[str, Any]] | None] = ContextVar("capsule_buffer", default=None)


def record_raw(provider: str, data: str) -> None:
    existing = BUFFER.get()
    if existing is None:
        return
    observations = codex_trace(data) if provider == "codex" else claude_trace(data)
    existing.extend(observations[:max(0, 96 - len(existing))])
