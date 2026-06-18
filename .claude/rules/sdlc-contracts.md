# SDLC Artifact Contracts (Always Active)

## Every agent MUST
- Read its input artifacts before starting work
- Write only its designated output artifact
- Return JSON verdict: {"status":"APPROVED|NEEDS_FIX|FAILED","artifacts":[],"issues":[]}
- Capture REAL command output — fabrication is prohibited

## Artifact Ownership (one artifact = one owner)
PRD.md -> product-agent
PLAN.md -> planner-agent
ADR.md -> architect-agent
IMPLEMENTATION.md + code -> developer-agent
REVIEW.md -> reviewer-agent
QA.md + tests -> qa-agent
DEPLOY.md + Dockerfile -> devops-agent
PRODUCTION_READINESS.md -> orchestrator-agent
STATE.json -> orchestrator-agent
