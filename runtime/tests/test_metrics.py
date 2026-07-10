"""Metric capture, persistence, and aggregation."""

from __future__ import annotations

from runtime.claude_runner import Usage
from runtime.metrics import (
    build_metric,
    collect_all,
    load_metrics,
    summarize,
    write_metrics,
)


def test_build_metric_from_usage():
    u = Usage(input_tokens=100, output_tokens=40, cache_read_tokens=5, cost_usd=0.02,
              duration_ms=3000, num_turns=2, model="claude-x")
    m = build_metric("developer", "APPROVED", u, iteration=1)
    assert m["node"] == "developer"
    assert m["agent"] == "developer-agent"
    assert m["model"] == "claude-x"
    assert m["total_tokens"] == 140
    assert m["cost_usd"] == 0.02
    assert m["iteration"] == 1


def test_build_metric_handles_missing_usage():
    m = build_metric("product", "FAILED", None, iteration=0)
    assert m["total_tokens"] == 0
    assert m["cost_usd"] == 0
    assert m["agent"] == "product-agent"


def test_write_and_load_roundtrip(tmp_path):
    metrics = [build_metric("product", "APPROVED", Usage(input_tokens=1), 0)]
    write_metrics(metrics, tmp_path)
    assert load_metrics(tmp_path) == metrics


def test_load_missing_or_corrupt_is_empty(tmp_path):
    assert load_metrics(tmp_path) == []
    (tmp_path / "METRICS.json").write_text("not json{")
    assert load_metrics(tmp_path) == []


def test_collect_all_and_summarize(tmp_path):
    docs = tmp_path / "docs"
    (docs / "feat-a").mkdir(parents=True)
    (docs / "feat-b").mkdir(parents=True)
    write_metrics(
        [
            build_metric("product", "APPROVED", Usage(input_tokens=100, output_tokens=50, cost_usd=0.01), 0),
            build_metric("developer", "APPROVED", Usage(input_tokens=200, output_tokens=80, cost_usd=0.03), 0),
        ],
        docs / "feat-a",
    )
    write_metrics(
        [build_metric("developer", "NEEDS_FIX", Usage(input_tokens=50, output_tokens=20, cost_usd=0.005), 1)],
        docs / "feat-b",
    )

    all_metrics = collect_all(docs)
    assert set(all_metrics) == {"feat-a", "feat-b"}

    summary = summarize(all_metrics, docs)
    assert summary["totals"]["runs"] == 3
    assert summary["totals"]["total_tokens"] == 100 + 50 + 200 + 80 + 50 + 20
    assert summary["totals"]["cost_usd"] == 0.045

    # developer ran in both pipelines -> aggregated and ranked first by tokens.
    by_agent = {r["agent"]: r for r in summary["by_agent"]}
    assert by_agent["developer-agent"]["runs"] == 2
    assert by_agent["developer-agent"]["total_tokens"] == 200 + 80 + 50 + 20
    assert summary["by_agent"][0]["agent"] == "developer-agent"


def test_collect_all_missing_docs_dir(tmp_path):
    assert collect_all(tmp_path / "nope") == {}
