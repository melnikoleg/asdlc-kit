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
Requirement → product-agent  → PRD.md
             planner-agent   → PLAN.md
             architect-agent → ADR.md
             [human approval]
             developer-agent → IMPLEMENTATION.md + code
             reviewer-agent  ┐
             qa-agent        ┴── parallel → REVIEW.md + QA.md
             [fix loop if needed, max 3x]
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

## Artifacts

All SDLC artifacts are stored in `docs/{issue-name}/`. Pipeline status is derived
from which of these exist — there is no separate state file:
- `PRD.md` — requirements with testable ACs
- `PLAN.md` — phased plan with validation commands
- `ADR.md` — architecture decisions (binding)
- `IMPLEMENTATION.md` — code changes + real validation evidence
- `REVIEW.md` — adversarial code review verdict
- `QA.md` — test results mapped to ACs
- `DEPLOY.md` — deployment runbook (only if /sdlc-deploy was run)
- `PRODUCTION_READINESS.md` — final sign-off

## Guardrails (always active)
- Destructive shell commands blocked (rm -rf /, git push --force, git reset --hard, mkfs, dd)
- Writes to .env, *.pem, id_rsa, kubeconfig blocked
- Artifacts missing real evidence/required sections trigger warnings
