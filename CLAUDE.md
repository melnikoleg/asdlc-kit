# Agentic SDLC Kit

This project uses an **agent-native Software Development Lifecycle** where specialized agents own every phase.

## Quick Start

```bash
# Full pipeline (requirement → production-ready code); pauses at the approval gate
asdlc-runtime <issue-name> "<requirement description>" [--devops]
asdlc-runtime <issue-name> --approve      # or --cancel / --resume

# Inside Claude Code
/factory <issue-name> "<requirement>"
/sdlc-status
```

The runtime (`runtime/`, LangGraph + headless `claude -p`) is the only pipeline. Skills wrap it.

## Pipeline

```
Requirement → codebase-agent  → CODEBASE_CONTEXT.md (skipped on greenfield repos)
             product-agent    → PRD.md
             planner-agent    → PLAN.md + TEST_STRATEGY.md (stack, layers, Start/Healthcheck/E2E)
             architect-agent  → ADR.md
             acceptance-agent → ACCEPTANCE.md (held-out; developer never reads it)
             [human approval]
             developer-agent → IMPLEMENTATION.md + code
             validate (code)  → PLAN `Validation:` commands, then `E2E:` against the booted app
             reviewer-agent  ┐
             qa-agent        ┴── parallel (+ devops-agent with --devops) → REVIEW.md + QA.md
             [fix loop if needed, max 3x]
             held-out acceptance gate (code, against the booted app) → pass, else escalate
             PRODUCTION_READINESS.md
```

## Testing during the pipeline

`TEST_STRATEGY.md` (planner-owned) declares `Type` (web-ui | http-api | cli | library), `Layers`,
`Start`/`Healthcheck` (foreground command, port 8700-8799), and `E2E`. `runtime/validation.py`
boots the app, waits for health, runs the commands, kills the process group. Agents run e2e
through `asdlc-e2e <issue> -- <command>` so they hit the same lifecycle. UI = Playwright,
API = HTTP client, CLI = subprocess.

## Available Skills (invoke via /skill-name)

| Skill | Description |
|-------|-------------|
| `/factory` | Run the pipeline through `asdlc-runtime` |
| `/sdlc-status` | Status from `docs/*/STATE.json` |
| `/sdlc-deploy` | Optional Docker/CI/runbook generation (or `--devops`) |
| `/code-reviewer` | Adversarial code review |
| `/security-audit` | OWASP Top 10 security scan |
| `/test-writer` | Write tests for existing code |
| `/git-commit` | Conventional Commits message |
| `/ponytail [lite\|full\|ultra\|off]` | Lazy senior dev mode — minimal, necessary code only |

## Artifacts

All SDLC artifacts are stored in `docs/{issue-name}/`:
- `CODEBASE_CONTEXT.md` — existing stack/conventions/integration points (brownfield repos only)
- `PRD.md` — requirements with testable ACs
- `PLAN.md` — phased plan with validation commands
- `TEST_STRATEGY.md` — stack, test layers, how to boot the app, e2e command
- `ADR.md` — architecture decisions (binding)
- `ACCEPTANCE.md` — held-out acceptance suite (one runnable check per AC; the developer must not read it)
- `IMPLEMENTATION.md` — code changes + real validation evidence
- `REVIEW.md` — adversarial code review verdict
- `QA.md` — test results mapped to ACs
- `DEPLOY.md` — deployment runbook (only with `--devops` or /sdlc-deploy)
- `PRODUCTION_READINESS.md` — final sign-off
- `STATE.json`, `METRICS.json` — runtime state mirror and per-agent cost/tokens

## Editor & MCP Setup

See `docs/setup/mcp-configs.md` for ready-to-paste MCP server configs (Claude Desktop, Cursor, Copilot, Claude Code project-local) that add `codebase-memory-mcp` — persistent cross-session project memory for agents.

See `docs/setup/rtk.md` to install RTK — a transparent CLI proxy that compresses shell command output by 60–90% before it hits the LLM context, cutting token costs across the entire pipeline.

## Model Tiers & Economics (runtime)

Each agent runs on a model chosen by role. Planning and judgment use the **smart**
tier (product, planner, architect, reviewer → Opus by default); production uses the
cheaper **worker** tier (developer, qa, devops, acceptance → Sonnet by default).
Defaults live in each `.claude/agents/*.md` `model:` field.

The runtime lets you swap the whole mix for one run — reproduce the
"agent-swarm economics" experiment (planner=smart, workers=cheap) and compare cost.
Resolution order (most specific wins): `ASDLC_MODEL_<NODE>` → `ASDLC_MODEL_SMART` /
`ASDLC_MODEL_WORKER` → frontmatter `model:`. Example:

```bash
ASDLC_MODEL_SMART=claude-opus-4-8 ASDLC_MODEL_WORKER=claude-haiku-4-5-20251001 \
  asdlc-runtime <issue> "<requirement>"
```

Cost/token usage per agent is captured to `docs/{issue}/METRICS.json`, summarized in
the `## Model Economics` section of `PRODUCTION_READINESS.md`, and rendered by
`asdlc-dashboard`. 
## Guardrails (always active)
- Destructive shell commands blocked (rm -rf /, git push --force, git reset --hard, mkfs, dd)
- Writes to .env, *.pem, id_rsa, kubeconfig blocked
- Artifacts missing real evidence/required sections trigger warnings
