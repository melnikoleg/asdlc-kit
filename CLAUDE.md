# Agentic SDLC — Project Configuration

## Quick Start
```bash
/factory my-feature "Build a REST API for user auth with JWT"
/factory my-feature --resume
/factory-status
```

## Architecture: 3-Tier Pipeline
```
Tier 1: /factory command     — parse, validate, init STATE.json
            |
Tier 2: orchestrator-agent   — coordinate phases, STATE.json, delegate via Agent()
            |
Tier 3: Specialist agents    — isolated 200K context, strict artifact contracts
```

## Agent Roles
| Agent              | Model  | Output Artifact              |
|--------------------|--------|------------------------------|
| orchestrator-agent | Opus   | STATE.json, PRODUCTION_READINESS.md |
| product-agent      | Sonnet | PRD.md                       |
| planner-agent      | Sonnet | PLAN.md                      |
| architect-agent    | Opus   | ADR.md                       |
| developer-agent    | Sonnet | IMPLEMENTATION.md + code     |
| reviewer-agent     | Opus   | REVIEW.md                    |
| qa-agent           | Sonnet | QA.md + test files           |
| devops-agent       | Sonnet | DEPLOY.md + Dockerfile + CI  |

## Artifact Contracts (STRICT)
- Every agent reads inputs before working
- Every agent writes only its designated artifact
- Every agent returns JSON verdict: {"status":"APPROVED|NEEDS_FIX","artifacts":[],"issues":[]}
- REAL command output required — fabrication prohibited

## Human Gates
- PAUSE after architect-agent → human approves PLAN.md before implementation
- ESCALATION.md written after 3 failed fix iterations → human must intervene

## Guardrails
- No writes to .env, *.pem, id_rsa, credentials
- No git push, no rm -rf on critical paths
- Bash scoped to test/build/inspect only
- All secrets via environment variables
