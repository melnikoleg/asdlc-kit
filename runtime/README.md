# asdlc-runtime — LangGraph orchestrator for the Agentic SDLC Kit

A deterministic, server-grade orchestration layer for the SDLC pipeline. It runs
the **same** Claude Code agents defined in `.claude/agents/*.md` (via the Claude
Agent SDK), but wires them into a LangGraph state machine so the *topology* is
guaranteed by code rather than by the model's good will.

## Why this exists

The native Claude Code pipeline (`/factory`, `/sdlc-orchestrate`) is ideal for
interactive use. For an **autonomous service** its LLM-driven orchestration is
best-effort: the model can skip the approval gate, not actually run validation,
declare `APPROVED` without checking, or mis-count the fix-loop.

This package moves the deterministic parts **out of the LLM and into graph code**:

| Concern | Native (LLM-driven) | Here (code-enforced) |
|---|---|---|
| Approval gate | Text "MANDATORY STOP" | `interrupt()` — physically blocks |
| Fix-loop limit | Counter the model updates | Real counter in a conditional edge |
| Validation | Agent *asked* to run commands | Graph runs them via `subprocess`, records real output |
| State | Derived from artifact presence | Typed state written by node code, mirrored to `STATE.json` for the dashboard |
| Resume after crash | `--resume` re-reads JSON | Durable checkpointer (SQLite/Postgres) |

The LLM still does all generative work; the agents, rules and hooks in `.claude/`
remain the single source of truth — this package loads them, it does not fork them.

## Topology

```
START → product → planner → architect → acceptance → approval ⏸(interrupt)
      → developer → validate ──fail──▶ developer (fix) | escalate
                          └─pass─▶ [reviewer ‖ qa ‖ devops] → aggregate
aggregate ──all APPROVED──▶ acceptance_gate ──pass──▶ readiness → END
                                            └─fail─▶ escalate → END
          ──NEEDS_FIX & budget left──▶ developer (fix)
          ──budget exhausted──▶ escalate → END

acceptance authors a held-out suite the developer never reads; acceptance_gate
grades it deterministically as an objective final check.
```

## Install

```bash
cd runtime
pip install -e .            # core (SQLite checkpointer)
pip install -e '.[postgres]'  # production Postgres checkpointer
pip install -e '.[server]'    # FastAPI server
pip install -e '.[dev]'       # tests
```

## Configuration (env)

| Var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Use for server/automated runs** (service-account path). If unset, falls back to local Claude Code subscription credentials — only appropriate for dev. |
| `CHECKPOINT_BACKEND` | `sqlite` | `sqlite` (dev) or `postgres` (prod). |
| `DB_URL` | — | Required when backend is `postgres`. |
| `ASDLC_SQLITE_PATH` | `.asdlc/checkpoints.sqlite` | SQLite checkpoint file. |
| `ASDLC_MAX_ITERATIONS` | `3` | Fix-loop budget before escalation. |
| `ASDLC_REPO_ROOT` | auto-detected | Repo containing `.claude/`. |
| `ASDLC_MODEL_SMART` | — | Override the model for the **smart** tier (product, planner, architect, reviewer). |
| `ASDLC_MODEL_WORKER` | — | Override the model for the **worker** tier (developer, qa, devops, acceptance). |
| `ASDLC_MODEL_<NODE>` | — | Override one agent (e.g. `ASDLC_MODEL_DEVELOPER`). Beats the tier override. |

Model resolution (most specific wins): `ASDLC_MODEL_<NODE>` → tier
(`ASDLC_MODEL_SMART`/`ASDLC_MODEL_WORKER`) → each agent's frontmatter `model:`.
Swap a whole mix for one run, then compare cost in `docs/{issue}/METRICS.json` /
the `## Model Economics` section of `PRODUCTION_READINESS.md`.

## Usage — CLI

```bash
# Start (runs up to the approval gate, then pauses)
ANTHROPIC_API_KEY=… python -m runtime.cli demo-feature "Build a TODO REST API"

# Approve / cancel the paused pipeline
python -m runtime.cli demo-feature --approve
python -m runtime.cli demo-feature --cancel

# Resume from the last checkpoint after a crash
python -m runtime.cli demo-feature --resume
```

The thread id is the issue name, so approve/resume work across separate processes.

## Usage — HTTP server

```bash
uvicorn runtime.server:app
# POST /pipelines                {"issue","requirement"}     → start (pauses at gate)
# POST /pipelines/{issue}/approve {"decision":"approve"}     → resume
# GET  /pipelines/{issue}                                     → state snapshot
# GET  /metrics                                               → usage metrics (JSON)
# GET  /dashboard                                             → usage dashboard (HTML)
```

## Usage dashboard — which skills ran, tokens, cost & timing

Every agent run records a real metric — the agent (skill) invoked, its model,
verdict, token counts, cost and duration, all captured from the SDK
`ResultMessage` (no estimates). Records accumulate in pipeline state and are
mirrored to `docs/{issue}/METRICS.json` as the graph runs.

Render a self-contained, theme-aware HTML dashboard aggregating every pipeline:

```bash
python -m runtime.dashboard              # writes ./dashboard.html
python -m runtime.dashboard --print      # HTML to stdout
asdlc-dashboard -o report.html           # installed console script
```

Or serve it live from the running server at `GET /dashboard` (and the raw
aggregate at `GET /metrics`). The dashboard shows total token/cost/time KPIs, a
per-agent token-spend breakdown, per-pipeline totals, and a recent-runs log.

## Tests

```bash
python -m pytest runtime/tests -o asyncio_mode=auto
```

`test_graph_flow.py` runs the whole graph with a **mock runner** (no LLM calls)
and asserts the determinism guarantees: the interrupt blocks before `developer`,
the fix-loop is hard-capped, passing review agents aren't re-run, and terminal
states (`done` / `escalated`) are reached deterministically.

## dev → prod checkpointer

Development uses SQLite (zero setup). For production set
`CHECKPOINT_BACKEND=postgres` and `DB_URL=postgresql://…` — **no code change**,
the graph wiring is identical. Postgres gives durable, concurrent-safe state for
multiple pipelines and horizontal scaling.
