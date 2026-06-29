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
from langgraph.types import Command
from pydantic import BaseModel

from .checkpoint import open_checkpointer
from .config import load_config
from .graph import build_graph
from .state import new_state

_config = load_config()
_state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with open_checkpointer(_config) as cp:
        _state["graph"] = build_graph(_config, checkpointer=cp)
        yield
    _state.clear()


app = FastAPI(title="asdlc-runtime", lifespan=lifespan)


class StartRequest(BaseModel):
    issue: str
    requirement: str


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
        "iteration": result.get("iteration", 0),
        "failing_agents": result.get("failing_agents", []),
        "artifacts": result.get("artifacts", []),
    }


@app.post("/pipelines")
async def start(req: StartRequest) -> dict[str, Any]:
    graph = _state["graph"]
    try:
        initial = new_state(req.issue, req.requirement)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = await graph.ainvoke(initial, _thread(req.issue))
    return _shape(result)


@app.post("/pipelines/{issue}/approve")
async def approve(issue: str, req: ApproveRequest) -> dict[str, Any]:
    graph = _state["graph"]
    result = await graph.ainvoke(Command(resume=req.decision), _thread(issue))
    return _shape(result)


@app.get("/pipelines/{issue}")
async def status(issue: str) -> dict[str, Any]:
    graph = _state["graph"]
    snapshot = await graph.aget_state(_thread(issue))
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="pipeline not found")
    return {"next": list(snapshot.next), **_shape(snapshot.values)}
