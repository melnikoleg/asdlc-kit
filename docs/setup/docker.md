# Running the pipeline in a clean container

The `runtime/` LangGraph orchestrator can run the whole SDLC pipeline
autonomously inside a single, disposable container. This is the right way to
run it unattended: the `developer` and `qa` nodes execute LLM-generated code,
so a throwaway container is your isolation boundary.

The image is **self-contained** — it carries Python + the runtime, Node.js +
the Claude Code CLI (the Claude Agent SDK launches it headless), `git`, and a
Python/Node toolchain so generated projects can actually be validated.

## What you need

- Docker with Compose v2
- An `ANTHROPIC_API_KEY` (service-account key — the headless/automated path)

The API key is **injected at runtime**, never baked into the image.

## Autonomous run (default)

Start → auto-approve the gate → code → review → readiness → exit.

```bash
export ANTHROPIC_API_KEY=sk-ant-...

ASDLC_ISSUE=todo-api \
ASDLC_REQUIREMENT="Build a TODO REST API with CRUD endpoints" \
  docker compose up --build
```

Artifacts land in `./docs/todo-api/` on the host (`PRD.md`, `PLAN.md`,
`ADR.md`, `IMPLEMENTATION.md`, `REVIEW.md`, `QA.md`,
`PRODUCTION_READINESS.md`). The container exits `0` when the pipeline reaches
`done`, non-zero if it escalated.

To keep the human approval gate, set `ASDLC_AUTO_APPROVE=0`; the run pauses,
and you approve with:

```bash
docker compose exec asdlc python -m runtime.cli todo-api --approve
```

## Server mode (HTTP API)

```bash
ASDLC_MODE=server docker compose up --build
# POST /pipelines                 {"issue","requirement"}  → start (pauses at gate)
# POST /pipelines/{issue}/approve {"decision":"approve"}    → resume
# GET  /pipelines/{issue}                                   → state snapshot
```

(Add a `ports:` mapping to `docker-compose.yml` to reach it from the host.)

## Manual mode

`ASDLC_MODE=manual` keeps the container idle so you can drive it step by step:

```bash
docker compose run --rm asdlc python -m runtime.cli demo "Build X"
docker compose exec asdlc python -m runtime.cli demo --approve
```

## Durable state (Postgres)

SQLite (default) lives in the `asdlc-state` volume — fine for single runs.
For durable, concurrent-safe state use the optional Postgres profile:

```bash
CHECKPOINT_BACKEND=postgres \
DB_URL=postgresql://asdlc:asdlc@postgres:5432/asdlc \
ASDLC_ISSUE=todo-api ASDLC_REQUIREMENT="Build a TODO REST API" \
  docker compose --profile postgres up --build
```

No code changes — only the checkpointer backend differs.

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required.** Headless agent auth. |
| `ASDLC_MODE` | `autonomous` | `autonomous` \| `server` \| `manual`. |
| `ASDLC_ISSUE` | — | Kebab-case issue name (required in autonomous mode). |
| `ASDLC_REQUIREMENT` | — | Requirement text (required in autonomous mode). |
| `ASDLC_AUTO_APPROVE` | `1` | `0` pauses at the approval gate. |
| `ASDLC_MAX_ITERATIONS` | `3` | Fix-loop budget before escalation. |
| `CHECKPOINT_BACKEND` | `sqlite` | `sqlite` or `postgres`. |
| `DB_URL` | — | Required when backend is `postgres`. |

## Notes & gotchas

- **Toolchains.** The image ships Python + Node. If your pipeline targets Go,
  Rust, etc., add it to `docker/Dockerfile` (stage 2) so `qa`/`developer`
  validation commands can run.
- **Bind-mount permissions (Linux).** The container runs as UID 1000. If your
  host `./docs` isn't writable by UID 1000, uncomment the `user:` line in
  `docker-compose.yml`.
- **Guardrails stay on.** The Agent SDK runs with `cwd` at the repo root and
  loads `.claude/settings.json`, so the destructive-command and secret-write
  hooks are enforced inside the container too.
