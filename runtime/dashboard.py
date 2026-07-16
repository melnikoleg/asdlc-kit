"""Usage dashboard: which agents ran, how many tokens, cost, and timing.

Reads every ``docs/{issue}/METRICS.json`` (written by the graph as it runs),
aggregates them, and renders a single self-contained, theme-aware HTML page —
no external assets, so it opens anywhere and the FastAPI server can return it
verbatim.

    python -m runtime.dashboard                 # writes ./dashboard.html
    python -m runtime.dashboard -o out.html     # custom path
    python -m runtime.dashboard --print         # HTML to stdout

Colours follow the validated categorical palette (each agent owns a fixed hue,
never cycled), per the data-viz method.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path
from typing import Any

from .config import Config, load_config
from .metrics import collect_all, summarize

# Fixed categorical slot per agent (identity colour, never reordered). (light, dark)
_AGENT_COLORS: dict[str, tuple[str, str]] = {
    "product-agent": ("#2a78d6", "#3987e5"),    # blue
    "planner-agent": ("#1baf7a", "#199e70"),    # aqua
    "architect-agent": ("#eda100", "#c98500"),  # yellow
    "developer-agent": ("#008300", "#008300"),  # green
    "reviewer-agent": ("#4a3aa7", "#9085e9"),   # violet
    "qa-agent": ("#e34948", "#e66767"),         # red
    "devops-agent": ("#e87ba4", "#d55181"),     # magenta
}
_DEFAULT_COLOR = ("#898781", "#898781")  # muted, for unknown agents

# Verdict → status role (icon + label + colour; never colour alone).
_STATUS = {
    "APPROVED": ("●", "good", "#0ca30c"),
    "NEEDS_FIX": ("▲", "warning", "#d98500"),
    "FAILED": ("✕", "critical", "#d03b3b"),
}


def build_dashboard_data(config: Config) -> dict[str, Any]:
    """Aggregated metrics for every pipeline under ``docs/``."""
    return summarize(collect_all(config.docs_dir), config.docs_dir)


# ── formatting ───────────────────────────────────────────────────────────────

def _int(n: Any) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "0"


def _cost(n: Any) -> str:
    try:
        return f"${float(n):,.4f}"
    except (TypeError, ValueError):
        return "$0.0000"


def _dur(ms: Any) -> str:
    try:
        s = float(ms) / 1000.0
    except (TypeError, ValueError):
        return "0s"
    if s >= 60:
        return f"{int(s // 60)}m {int(s % 60)}s"
    return f"{s:.1f}s"


def _esc(s: Any) -> str:
    return html.escape(str(s if s is not None else ""))


def _agent_color_var(agent: str) -> str:
    light, dark = _AGENT_COLORS.get(agent, _DEFAULT_COLOR)
    return f"--c-light:{light};--c-dark:{dark}"


def _status_chip(status: str) -> str:
    icon, role, _ = _STATUS.get(str(status).upper(), ("○", "muted", "#898781"))
    return f'<span class="chip chip-{role}">{icon} {_esc(status)}</span>'


# ── rendering ────────────────────────────────────────────────────────────────

def _stat_tiles(totals: dict[str, Any], pipelines: int) -> str:
    tiles = [
        ("Total tokens", _int(totals.get("total_tokens"))),
        ("Cost", _cost(totals.get("cost_usd"))),
        ("Agent runs", _int(totals.get("runs"))),
        ("Total time", _dur(totals.get("duration_ms"))),
        ("Pipelines", _int(pipelines)),
    ]
    cells = "".join(
        f'<div class="tile"><div class="tile-label">{_esc(label)}</div>'
        f'<div class="tile-value">{value}</div></div>'
        for label, value in tiles
    )
    return f'<section class="tiles">{cells}</section>'


def _agent_bars(by_agent: list[dict[str, Any]]) -> str:
    if not by_agent:
        return ""
    top = max((r["total_tokens"] for r in by_agent), default=0) or 1
    rows = []
    for r in by_agent:
        pct = max(2.0, r["total_tokens"] / top * 100)
        tip = (
            f'{r["runs"]} run(s) · {_int(r["input_tokens"])} in / '
            f'{_int(r["output_tokens"])} out · {_cost(r["cost_usd"])}'
        )
        rows.append(
            f'<div class="bar-row" style="{_agent_color_var(r["agent"])}" title="{_esc(tip)}">'
            f'<div class="bar-name"><span class="swatch"></span>{_esc(r["agent"])}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%"></div></div>'
            f'<div class="bar-value">{_int(r["total_tokens"])}</div>'
            f"</div>"
        )
    return (
        '<section class="card"><h2>Tokens by agent</h2>'
        f'<div class="bars">{"".join(rows)}</div></section>'
    )


def _agent_table(by_agent: list[dict[str, Any]]) -> str:
    head = (
        "<tr><th>Agent</th><th class=n>Runs</th><th class=n>Input</th>"
        "<th class=n>Output</th><th class=n>Total tokens</th>"
        "<th class=n>Cache read</th><th class=n>Cost</th><th class=n>Time</th></tr>"
    )
    body = "".join(
        f'<tr><td><span class="swatch" style="{_agent_color_var(r["agent"])}"></span>'
        f'{_esc(r["agent"])}</td>'
        f'<td class=n>{_int(r["runs"])}</td><td class=n>{_int(r["input_tokens"])}</td>'
        f'<td class=n>{_int(r["output_tokens"])}</td>'
        f'<td class=n><b>{_int(r["total_tokens"])}</b></td>'
        f'<td class=n>{_int(r["cache_read_tokens"])}</td>'
        f'<td class=n>{_cost(r["cost_usd"])}</td><td class=n>{_dur(r["duration_ms"])}</td></tr>'
        for r in by_agent
    )
    return f'<section class="card"><h2>By agent</h2><table>{head}{body}</table></section>'


def _issue_table(by_issue: list[dict[str, Any]]) -> str:
    rows = []
    for r in by_issue:
        phase = r.get("phase")
        phase_html = f'<span class="chip chip-muted">{_esc(phase)}</span>' if phase else "—"
        rows.append(
            f'<tr><td>{_esc(r["issue"])}</td><td>{phase_html}</td>'
            f'<td class=n>{_int(r["runs"])}</td>'
            f'<td class=n>{_int(r["total_tokens"])}</td>'
            f'<td class=n>{_cost(r["cost_usd"])}</td><td class=n>{_dur(r["duration_ms"])}</td></tr>'
        )
    head = (
        "<tr><th>Pipeline</th><th>Phase</th><th class=n>Runs</th>"
        "<th class=n>Total tokens</th><th class=n>Cost</th><th class=n>Time</th></tr>"
    )
    return f'<section class="card"><h2>By pipeline</h2><table>{head}{"".join(rows)}</table></section>'


def _recent_runs(runs: list[dict[str, Any]], limit: int = 25) -> str:
    rows = "".join(
        f'<tr><td class="mono">{_esc(r.get("timestamp", ""))}</td>'
        f'<td>{_esc(r.get("issue"))}</td><td>{_esc(r.get("agent"))}</td>'
        f'<td>{_status_chip(r.get("status", ""))}</td>'
        f'<td class=n>{_int(r.get("total_tokens"))}</td>'
        f'<td class=n>{_cost(r.get("cost_usd"))}</td>'
        f'<td class=n>{_dur(r.get("duration_ms"))}</td></tr>'
        for r in runs[:limit]
    )
    head = (
        "<tr><th>Time (UTC)</th><th>Pipeline</th><th>Agent</th><th>Verdict</th>"
        "<th class=n>Tokens</th><th class=n>Cost</th><th class=n>Time</th></tr>"
    )
    return f'<section class="card"><h2>Recent runs</h2><table>{head}{rows}</table></section>'


def render_html(data: dict[str, Any]) -> str:
    totals = data.get("totals", {})
    by_agent = data.get("by_agent", [])
    by_issue = data.get("by_issue", [])
    runs = data.get("runs", [])
    generated = data.get("generated_at", "")

    if not runs:
        body = (
            '<section class="card empty"><h2>No metrics yet</h2>'
            "<p>Run a pipeline (<code>python -m runtime.cli &lt;issue&gt; "
            '"&lt;requirement&gt;"</code>) and this dashboard will fill with real '
            "token, cost and timing data captured from each agent run.</p></section>"
        )
    else:
        body = (
            _stat_tiles(totals, len(by_issue))
            + _agent_bars(by_agent)
            + _agent_table(by_agent)
            + _issue_table(by_issue)
            + _recent_runs(runs)
        )

    return _PAGE.replace("__GENERATED__", _esc(generated)).replace("__BODY__", body)


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agentic SDLC — Usage Dashboard</title>
<style>
:root{
  --plane:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --ring:rgba(11,11,11,0.10); --track:#eeede8;
}
@media (prefers-color-scheme: dark){
  :root{ --plane:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --ring:rgba(255,255,255,0.10); --track:#242422; }
}
:root[data-theme=light]{ --plane:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e;
  --grid:#e1e0d9; --ring:rgba(11,11,11,0.10); --track:#eeede8; }
:root[data-theme=dark]{ --plane:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink2:#c3c2b7;
  --grid:#2c2c2a; --ring:rgba(255,255,255,0.10); --track:#242422; }
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.45;
  padding:32px 20px 64px}
.wrap{max-width:1040px;margin:0 auto}
header{margin-bottom:24px}
h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--muted);font-size:13px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:20px}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:16px}
.tile-label{color:var(--ink2);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.tile-value{font-size:26px;font-weight:650;margin-top:6px}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:12px;
  padding:18px 18px 8px;margin-bottom:20px;overflow-x:auto}
.card h2{font-size:14px;margin:0 0 14px;color:var(--ink2);font-weight:600}
.card.empty{padding:22px}.card.empty p{color:var(--ink2);font-size:14px;max-width:60ch}
code{background:var(--track);padding:1px 6px;border-radius:5px;font-size:12px}
.bars{display:flex;flex-direction:column;gap:8px;padding-bottom:8px}
.bar-row{display:grid;grid-template-columns:160px 1fr 84px;align-items:center;gap:12px}
.bar-name{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--ink2);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar-track{background:var(--track);border-radius:5px;height:14px}
.bar-fill{height:14px;border-radius:5px;background:var(--c-light);min-width:4px}
.bar-value{text-align:right;font-size:13px;font-variant-numeric:tabular-nums}
.swatch{display:inline-block;width:10px;height:10px;border-radius:3px;
  background:var(--c-light);flex:0 0 auto}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--grid);white-space:nowrap}
th{color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.03em}
td .swatch{margin-right:7px}
.n{text-align:right;font-variant-numeric:tabular-nums}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;color:var(--ink2)}
.chip{display:inline-block;font-size:11px;padding:2px 8px;border-radius:999px;
  border:1px solid var(--ring);font-weight:600}
.chip-good{color:#0ca30c}.chip-warning{color:#d98500}.chip-critical{color:#d03b3b}
.chip-muted{color:var(--ink2)}
@media (prefers-color-scheme: dark){
  .bar-fill,.swatch{background:var(--c-dark)}
  .chip-good{color:#0ca30c}.chip-warning{color:#fab219}.chip-critical{color:#e66767}
}
:root[data-theme=dark] .bar-fill,:root[data-theme=dark] .swatch{background:var(--c-dark)}
</style>
</head>
<body>
<div class="wrap">
<header>
<h1>Agentic SDLC — Usage Dashboard</h1>
<div class="sub">Skills used, token spend, cost &amp; timing across all pipelines · generated __GENERATED__</div>
</header>
__BODY__
</div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="runtime.dashboard", description=__doc__)
    parser.add_argument("-o", "--output", default="dashboard.html", help="output HTML path")
    parser.add_argument("--print", action="store_true", dest="to_stdout", help="write HTML to stdout")
    args = parser.parse_args(argv)

    data = build_dashboard_data(load_config())
    html_out = render_html(data)

    if args.to_stdout:
        sys.stdout.write(html_out)
        return 0

    out = Path(args.output)
    out.write_text(html_out, encoding="utf-8")
    runs = len(data.get("runs", []))
    print(f"wrote {out}  ({runs} agent run(s) across {len(data.get('by_issue', []))} pipeline(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
