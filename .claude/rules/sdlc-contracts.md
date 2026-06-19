# SDLC Artifact Contracts (Always Active)

## Every Agent MUST
- Read its input artifacts before starting work
- Write only its designated output artifact(s)
- Return a JSON verdict: {"status":"APPROVED|NEEDS_FIX|FAILED","artifacts":[],"issues":[]}
- Capture REAL command output — fabrication is prohibited. IMPLEMENTATION.md and
  QA.md must contain captured command-output blocks, not just section headings
  (the validate-artifact-schema hook checks for this).

## Artifact Ownership
PRD.md                    → product-agent (owner)
PLAN.md                   → planner-agent (owner)
ADR.md                    → architect-agent (owner)
IMPLEMENTATION.md + code  → developer-agent (owner)
REVIEW.md                 → reviewer-agent (owner)
QA.md + tests             → qa-agent (owner)
DEPLOY.md + infra         → devops-agent (owner, opt-in via /sdlc-deploy)
PRODUCTION_READINESS.md   → orchestrating skill (owner)

## No agent writes another agent's artifact.
## Pipeline state is derived from artifact presence — there is no STATE.json.
