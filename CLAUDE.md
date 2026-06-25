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
Requirement → product-agent → PRD.md
             planner-agent  → PLAN.md
             architect-agent → ADR.md
             [human approval]
             developer-agent → IMPLEMENTATION.md + code
             reviewer-agent  ┐
             qa-agent        ├── parallel → REVIEW.md + QA.md + DEPLOY.md
             devops-agent    ┘
             [fix loop if needed, max 3x]
             PRODUCTION_READINESS.md
```

## Available Skills (invoke via /skill-name)

| Skill | Description |
|-------|-------------|
| `/sdlc-orchestrate` | Full pipeline end-to-end |
| `/sdlc-plan` | Planning phase only |
| `/sdlc-implement` | Implementation from existing PLAN.md |
| `/sdlc-review` | Parallel review (reviewer + qa + devops) |
| `/sdlc-ensemble-review` | Kaggle-style ensemble review: k reviewers → majority-vote verdict + frequency-weighted issues |
| `/sdlc-qa` | QA and tests only |
| `/sdlc-deploy` | Deployment artifacts only |
| `/sdlc-status` | Pipeline status dashboard |
| `/sdlc-fix` | Fix blocking review issues |
| `/code-reviewer` | Adversarial code review |
| `/security-audit` | OWASP Top 10 security scan |
| `/test-writer` | Write tests for existing code |
| `/prd-writer` | Write structured PRD |
| `/architect-adr` | Write Architecture Decision Record |
| `/api-design` | Design REST API with OpenAPI spec |
| `/docker-setup` | Dockerfile + docker-compose |
| `/ci-setup` | GitHub Actions CI/CD |
| `/debug-agent` | Systematic bug root cause analysis |
| `/refactor` | Safe test-backed refactoring |
| `/dependency-audit` | CVE scan for dependencies |
| `/git-commit` | Conventional Commits message |

## Artifacts

All SDLC artifacts are stored in `docs/{issue-name}/`:
- `STATE.json` — pipeline state machine
- `PRD.md` — requirements with testable ACs
- `PLAN.md` — phased plan with validation commands
- `ADR.md` — architecture decisions (binding)
- `IMPLEMENTATION.md` — code changes + validation evidence
- `REVIEW.md` — adversarial code review verdict
- `QA.md` — test results mapped to ACs
- `DEPLOY.md` — deployment runbook
- `PRODUCTION_READINESS.md` — final sign-off

## Guardrails (always active)
- Destructive shell commands blocked (rm -rf /, git push --force)
- Writes to .env, *.pem, id_rsa, kubeconfig blocked
- Missing required sections in artifacts trigger warnings
- Paused pipelines announced on session stop
