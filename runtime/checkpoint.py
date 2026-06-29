"""Checkpointer factory: SQLite for dev, Postgres for production.

Switching backend is an env change (``CHECKPOINT_BACKEND``), not a code change
— the graph wiring is identical. The checkpointer is what makes the approval
``interrupt()`` and durable resume work.

Pipeline nodes are async (they call the Claude Agent SDK), so the graph runs
async and needs an async-capable saver. Both backends are exposed as async
context managers via :func:`open_checkpointer`::

    async with open_checkpointer(config) as cp:
        graph = build_graph(config, checkpointer=cp)
        ...
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from .config import Config


@asynccontextmanager
async def open_checkpointer(config: Config) -> AsyncIterator[object]:
    if config.checkpoint_backend == "postgres":
        async with _postgres(config) as cp:
            yield cp
    else:
        async with _sqlite(config) as cp:
            yield cp


@asynccontextmanager
async def _sqlite(config: Config) -> AsyncIterator[object]:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(config.sqlite_path)) as saver:
        await saver.setup()
        yield saver


@asynccontextmanager
async def _postgres(config: Config) -> AsyncIterator[object]:
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Postgres backend requires the 'postgres' extra: "
            "pip install 'asdlc-runtime[postgres]'"
        ) from exc

    assert config.db_url  # validated in load_config()
    async with AsyncPostgresSaver.from_conn_string(config.db_url) as saver:
        await saver.setup()
        yield saver
