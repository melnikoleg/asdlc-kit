"""Dashboard aggregation and HTML rendering."""

from __future__ import annotations

from runtime.claude_runner import Usage
from runtime.dashboard import build_dashboard_data, render_html
from runtime.metrics import build_metric, summarize, write_metrics


def _seed(config):
    docs = config.docs_for("demo-feature")
    write_metrics(
        [
            build_metric("product", "APPROVED", Usage(input_tokens=1200, output_tokens=300, cost_usd=0.02), 0),
            build_metric("developer", "APPROVED", Usage(input_tokens=5000, output_tokens=1500, cost_usd=0.11), 0),
        ],
        docs,
    )


def test_build_dashboard_data_reads_disk(temp_config):
    _seed(temp_config)
    data = build_dashboard_data(temp_config)
    assert data["totals"]["runs"] == 2
    assert data["totals"]["total_tokens"] == 1200 + 300 + 5000 + 1500
    assert data["by_agent"][0]["agent"] == "developer-agent"  # biggest spender first


def test_render_html_contains_real_numbers(temp_config):
    _seed(temp_config)
    html = render_html(build_dashboard_data(temp_config))
    assert "<!doctype html>" in html
    assert "Usage Dashboard" in html
    assert "developer-agent" in html
    assert "8,000" in html  # grand total tokens, thousands-separated
    assert "prefers-color-scheme" in html  # theme-aware


def test_render_html_empty_state():
    html = render_html(summarize({}))
    assert "No metrics yet" in html
    assert "<!doctype html>" in html


def test_render_html_escapes_untrusted_fields():
    # Agent/verdict text is rendered into HTML; ensure it is escaped.
    data = summarize({"x": [{"agent": "<script>", "status": "<b>", "total_tokens": 1,
                             "cost_usd": 0, "duration_ms": 0, "input_tokens": 0,
                             "output_tokens": 0, "cache_read_tokens": 0, "timestamp": ""}]})
    html = render_html(data)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
