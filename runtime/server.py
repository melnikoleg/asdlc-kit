"""Optional FastAPI server exposing the pipeline as a service.

Run with::

    pip install 'asdlc-runtime[server]'
    uvicorn runtime.server:app

Endpoints:
    POST /pipelines               {"issue", "requirement"} → start, returns pause/interrupt
    POST /pipelines/{issue}/approve  {"decision": "approve"|"cancel"} → resume
    GET  /pipelines/{issue}       → current state snapshot

A single checkpointer is opened for the app's lifetime, so approvals can land
on a different request than the one that started the pipeline (durable resume).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from langgraph.types import Command
from pydantic import BaseModel

from .checkpoint import open_checkpointer
from .config import configure_providers, load_config
from .dashboard import build_dashboard_data, render_html
from .graph import build_graph
from .state import new_state

_config = load_config()
_state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with open_checkpointer(_config) as cp:
        _state["checkpointer"] = cp
        yield
    _state.clear()


app = FastAPI(title="asdlc-runtime", lifespan=lifespan)


class StartRequest(BaseModel):
    issue: str
    requirement: str
    devops: bool = False
    specs: bool = False
    provider: str | None = None
    agent_providers: dict[str, str] = {}


class ApproveRequest(BaseModel):
    decision: str = "approve"


def _thread(issue: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": issue}}


def _shape(result: dict[str, Any]) -> dict[str, Any]:
    interrupts = result.get("__interrupt__")
    if interrupts:
        return {
            "status": "awaiting_approval",
            "interrupt": [getattr(i, "value", i) for i in interrupts],
        }
    return {
        "status": result.get("phase"),
        "provider": result.get("provider"),
        "agent_providers": result.get("agent_providers", {}),
        "iteration": result.get("iteration", 0),
        "failing_agents": result.get("failing_agents", []),
        "artifacts": result.get("artifacts", []),
    }


@app.post("/pipelines")
async def start(req: StartRequest) -> dict[str, Any]:
    try:
        config = configure_providers(_config, req.provider, req.agent_providers)
        initial = new_state(req.issue, req.requirement, devops=req.devops, specs=req.specs,
                            provider=config.provider, agent_providers=config.agent_providers)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    graph = build_graph(config, checkpointer=_state["checkpointer"])
    result = await graph.ainvoke(initial, _thread(req.issue))
    return _shape(result)


async def _graph_for_saved(issue: str):
    """Rebuild routing from checkpointed choices; requests never cross-contaminate."""
    probe = build_graph(_config, checkpointer=_state["checkpointer"])
    snapshot = await probe.aget_state(_thread(issue))
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="pipeline not found")
    config = configure_providers(
        _config, snapshot.values.get("provider", "claude"),
        snapshot.values.get("agent_providers", {}), replace_overrides=True,
    )
    return build_graph(config, checkpointer=_state["checkpointer"]), snapshot


@app.post("/pipelines/{issue}/approve")
async def approve(issue: str, req: ApproveRequest) -> dict[str, Any]:
    graph, snapshot = await _graph_for_saved(issue)
    result = await graph.ainvoke(Command(resume=req.decision), _thread(issue))
    return _shape(result)


@app.get("/pipelines/{issue}")
async def status(issue: str) -> dict[str, Any]:
    graph, snapshot = await _graph_for_saved(issue)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="pipeline not found")
    return {"next": list(snapshot.next), **_shape(snapshot.values)}


@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    """Aggregated usage metrics (JSON) across all pipelines."""
    return build_dashboard_data(_config)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> str:
    """Rendered usage dashboard: agents used, tokens, cost and timing."""
    return render_html(build_dashboard_data(_config))
