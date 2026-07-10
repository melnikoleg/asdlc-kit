"""Per-agent usage metrics: capture, persist, and aggregate.

Each agent run produces one metric record (which agent/skill ran, its model,
verdict, real token counts, cost and duration). Records live in pipeline state
(reducer-accumulated) and are mirrored to ``docs/{issue}/METRICS.json``. The
dashboard reads those files back and aggregates them across all pipelines.

All numbers originate from the SDK ``ResultMessage`` via
:class:`runtime.claude_runner.Usage`; a mock/usage-less run degrades to a
zero-cost record rather than fabricating figures.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .agent_loader import AGENT_FILE
from .state import now_iso

if TYPE_CHECKING:  # avoid importing the SDK bridge at module load
    from .claude_runner import Usage

METRICS_FILE = "METRICS.json"

# Numeric fields summed when aggregating a set of records.
_SUM_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_creation_tokens",
    "total_tokens",
    "cost_usd",
    "duration_ms",
    "num_turns",
)


def build_metric(node: str, status: str, usage: "Usage | None", iteration: int) -> dict[str, Any]:
    """One metric record for a single agent run."""
    from .claude_runner import Usage  # lazy: keep SDK import out of import time

    u = usage or Usage()
    total_tokens = u.input_tokens + u.output_tokens
    return {
        "node": node,
        "agent": AGENT_FILE.get(node, node),
        "model": u.model,
        "status": status,
        "iteration": iteration,
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "cache_read_tokens": u.cache_read_tokens,
        "cache_creation_tokens": u.cache_creation_tokens,
        "total_tokens": total_tokens,
        "cost_usd": round(u.cost_usd, 6),
        "duration_ms": u.duration_ms,
        "num_turns": u.num_turns,
        "timestamp": now_iso(),
    }


def write_metrics(metrics: list[dict[str, Any]], docs_dir: Path) -> Path:
    """Mirror the full metric list for one issue to METRICS.json."""
    docs_dir.mkdir(parents=True, exist_ok=True)
    target = docs_dir / METRICS_FILE
    target.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return target


def load_metrics(docs_dir: Path) -> list[dict[str, Any]]:
    """Read one issue's METRICS.json, tolerating a missing/corrupt file."""
    path = docs_dir / METRICS_FILE
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _phase_of(docs_dir: Path) -> str | None:
    state = docs_dir / "STATE.json"
    if not state.is_file():
        return None
    try:
        return json.loads(state.read_text(encoding="utf-8")).get("phase")
    except (json.JSONDecodeError, OSError):
        return None


def collect_all(docs_root: Path) -> dict[str, list[dict[str, Any]]]:
    """Map ``issue -> records`` for every pipeline under ``docs/`` with metrics."""
    out: dict[str, list[dict[str, Any]]] = {}
    if not docs_root.is_dir():
        return out
    for child in sorted(docs_root.iterdir()):
        if child.is_dir():
            records = load_metrics(child)
            if records:
                out[child.name] = records
    return out


def _zero_totals() -> dict[str, float]:
    return {f: 0 for f in _SUM_FIELDS}


def _accumulate(into: dict[str, Any], record: dict[str, Any]) -> None:
    into["runs"] = into.get("runs", 0) + 1
    for f in _SUM_FIELDS:
        into[f] = into.get(f, 0) + (record.get(f, 0) or 0)


def summarize(all_metrics: dict[str, list[dict[str, Any]]], docs_root: Path | None = None) -> dict[str, Any]:
    """Aggregate raw records into the shape the dashboard renders.

    Returns totals, a per-agent breakdown (sorted by token spend), a per-issue
    breakdown, and a flat newest-first run list.
    """
    totals: dict[str, Any] = {"runs": 0, **_zero_totals()}
    by_agent: dict[str, dict[str, Any]] = {}
    by_issue: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []

    for issue, records in all_metrics.items():
        issue_row: dict[str, Any] = {"issue": issue, "runs": 0, **_zero_totals()}
        if docs_root is not None:
            issue_row["phase"] = _phase_of(docs_root / issue)
        for rec in records:
            _accumulate(totals, rec)
            _accumulate(issue_row, rec)
            agent = rec.get("agent", rec.get("node", "unknown"))
            row = by_agent.setdefault(agent, {"agent": agent, "runs": 0, **_zero_totals()})
            _accumulate(row, rec)
            runs.append({"issue": issue, **rec})
        by_issue.append(issue_row)

    for row in list(by_agent.values()) + by_issue + [totals]:
        row["cost_usd"] = round(row.get("cost_usd", 0), 6)

    return {
        "generated_at": now_iso(),
        "totals": totals,
        "by_agent": sorted(by_agent.values(), key=lambda r: r["total_tokens"], reverse=True),
        "by_issue": sorted(by_issue, key=lambda r: r["total_tokens"], reverse=True),
        "runs": sorted(runs, key=lambda r: r.get("timestamp", ""), reverse=True),
    }
