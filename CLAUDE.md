# Agentic SDLC Kit

This project uses an **agent-native Software Development Lifecycle** where specialized agents own every phase.

## Quick Start

```bash
# Full pipeline (requirement → production-ready code)
/factory <issue-name> "<requirement description>"

# Planning only (review before coding)
/sdlc-plan <issue-name> "<requirement>"

# Check all pipeline status
/sdlc-status
```

## Pipeline

```
Requirement → codebase-agent  → CODEBASE_CONTEXT.md (brownfield repos only)
             product-agent    → PRD.md
             planner-agent    → PLAN.md
             architect-agent  → ADR.md
             acceptance-agent → ACCEPTANCE.md (held-out; developer never reads it)
             [human approval]
             developer-agent → IMPLEMENTATION.md + code
             reviewer-agent  ┐
             qa-agent        ┴── parallel → REVIEW.md + QA.md
             [fix loop if needed, max 3x]
             held-out acceptance gate (deterministic) → pass, else escalate
             PRODUCTION_READINESS.md

             (optional) /sdlc-deploy → devops-agent → DEPLOY.md + Docker/CI
```

## Available Skills (invoke via /skill-name)

| Skill | Description |
|-------|-------------|
| `/sdlc-orchestrate` (`/factory`) | Full pipeline end-to-end |
| `/sdlc-plan` | Planning phase only (PRD + PLAN + ADR) |
| `/sdlc-implement` | Implementation from existing PLAN.md |
| `/sdlc-review` | Parallel review (reviewer + qa) |
| `/sdlc-fix` | Fix blocking review issues |
| `/sdlc-deploy` | Optional Docker/CI/runbook generation |
| `/sdlc-status` | Status, derived from artifacts present |
| `/code-reviewer` | Adversarial code review |
| `/security-audit` | OWASP Top 10 security scan |
| `/test-writer` | Write tests for existing code |
| `/git-commit` | Conventional Commits message |
| `/ponytail [lite\|full\|ultra\|off]` | Lazy senior dev mode — minimal, necessary code only |

## Artifacts

All SDLC artifacts are stored in `docs/{issue-name}/`. Pipeline status is derived
from which of these exist — there is no separate state file:
- `CODEBASE_CONTEXT.md` — existing stack/conventions/integration points (brownfield repos only)
- `PRD.md` — requirements with testable ACs
- `PLAN.md` — phased plan with validation commands
- `ADR.md` — architecture decisions (binding)
- `ACCEPTANCE.md` — held-out acceptance suite (one runnable check per AC; the developer must not read it)
- `IMPLEMENTATION.md` — code changes + real validation evidence
- `REVIEW.md` — adversarial code review verdict
- `QA.md` — test results mapped to ACs
- `DEPLOY.md` — deployment runbook (only if /sdlc-deploy was run)
- `PRODUCTION_READINESS.md` — final sign-off

## Editor & MCP Setup

See `docs/setup/mcp-configs.md` for ready-to-paste MCP server configs (Claude Desktop, Cursor, Copilot, Claude Code project-local) that add `codebase-memory-mcp` — persistent cross-session project memory for agents.

See `docs/setup/rtk.md` to install RTK — a transparent CLI proxy that compresses shell command output by 60–90% before it hits the LLM context, cutting token costs across the entire pipeline.

## Model Tiers & Economics (runtime)

Each agent runs on a model chosen by role. Planning and judgment use the **smart**
tier (product, planner, architect, reviewer → Opus by default); production uses the
cheaper **worker** tier (developer, qa, devops, acceptance → Sonnet by default).
Defaults live in each `.claude/agents/*.md` `model:` field.

The Python runtime lets you swap the whole mix for one run — reproduce the
"agent-swarm economics" experiment (planner=smart, workers=cheap) and compare cost.
Resolution order (most specific wins): `ASDLC_MODEL_<NODE>` → `ASDLC_MODEL_SMART` /
`ASDLC_MODEL_WORKER` → frontmatter `model:`. Example:

```bash
ASDLC_MODEL_SMART=claude-opus-4-8 ASDLC_MODEL_WORKER=claude-haiku-4-5-20251001 \
  asdlc-runtime <issue> "<requirement>"
```

Cost/token usage per agent is captured to `docs/{issue}/METRICS.json`, summarized in
the `## Model Economics` section of `PRODUCTION_READINESS.md`, and rendered by
`asdlc-dashboard`. (The skills-only path has no token capture; there, "configurable"
means editing the frontmatter `model:`.)

## Guardrails (always active)
- Destructive shell commands blocked (rm -rf /, git push --force, git reset --hard, mkfs, dd)
- Writes to .env, *.pem, id_rsa, kubeconfig blocked
- Artifacts missing real evidence/required sections trigger warnings
