# SDLC Artifact Contracts (Always Active)

## Every Agent MUST
- Read its input artifacts before starting work
- Write only its designated output artifact(s)
- Return a JSON verdict: {"status":"APPROVED|NEEDS_FIX|FAILED","artifacts":[],"issues":[]}
- Capture REAL command output — fabrication is prohibited. IMPLEMENTATION.md and
  QA.md must contain captured command-output blocks, not just section headings
  (the validate-artifact-schema hook checks for this).

## Artifact Ownership
CODEBASE_CONTEXT.md       → codebase-agent (owner, brownfield repos only)
PRD.md                    → product-agent (owner)
PLAN.md                   → planner-agent (owner)
TEST_STRATEGY.md         → planner-agent (owner; Start/Healthcheck/E2E drive the e2e gate)
ADR.md                    → architect-agent (owner)
ACCEPTANCE.md             → acceptance-agent (owner, held-out; developer must NOT read it)
IMPLEMENTATION.md + code  → developer-agent (owner)
REVIEW.md                 → reviewer-agent (owner)
QA.md + tests             → qa-agent (owner)
DEPLOY.md + infra         → devops-agent (owner, opt-in via /sdlc-deploy)
PRODUCTION_READINESS.md   → runtime readiness node (owner)

## No agent writes another agent's artifact.
## Pipeline state lives in the runtime (LangGraph checkpoint); docs/{issue}/STATE.json is a mirror.
