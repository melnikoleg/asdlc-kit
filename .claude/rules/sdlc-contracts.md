# SDLC Artifact Contracts (Always Active)

## Every Agent MUST
- Read its input artifacts before starting work
- Write only its designated output artifact(s)
- Return a JSON verdict: {"status":"APPROVED|NEEDS_FIX|FAILED","artifacts":[],"issues":[]}
- Capture REAL command output — fabrication is prohibited and immediately detectable

## Artifact Ownership
PRD.md                    → product-agent (owner)
PLAN.md                   → planner-agent (owner)
ADR.md                    → architect-agent (owner)
IMPLEMENTATION.md + code  → developer-agent (owner)
REVIEW.md                 → reviewer-agent (owner)
QA.md + tests             → qa-agent (owner)
DEPLOY.md + infra         → devops-agent (owner)
PRODUCTION_READINESS.md   → orchestrator-agent (owner)
STATE.json                → orchestrator-agent (owner)

## No agent writes another agent's artifact.

## Ensemble review exception (only when /sdlc-ensemble-review is used)
REVIEW.run{n}.md          → reviewer-agent instance n (intermediate)
REVIEW.md                 → ensemble-aggregator (consolidated, replaces single-reviewer ownership)
The consolidated REVIEW.md still satisfies the standard REVIEW.md contract.
