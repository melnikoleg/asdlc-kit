# Agentic SDLC Best Practices

## Three Pillars That Prevent Collapse
1. Spec-First: no implementation without approved PRD + PLAN + ADR
2. Evidence Required: IMPLEMENTATION.md must contain REAL command output
3. Adversarial Review: reviewer and qa-agent run independently with separate contexts

## Anti-Patterns This Kit Prevents
- Vague untestable ACs (product-agent rules enforce binary criteria)
- Fabricated evidence (validate-artifact-schema hook requires real output blocks)
- Infinite fix loops (max 3 fix rounds, then escalate)
- Sensitive file exposure (block-secret-writes hook)
- Destructive shell commands (block-destructive hook)

## Model Strategy
- Opus 4.8: architect, reviewer (high-stakes decisions)
- Sonnet 4.6: product, planner, developer, qa, devops (high-volume execution)

## Extending
Add agent: create .claude/agents/{name}-agent.md, wire it into the relevant skill,
add its artifact to the CLAUDE.md table, add a schema check to validate-artifact-schema.sh.

## Deliberately Kept Simple
- No STATE.json state machine — status is derived from which artifacts exist.
- DevOps (Docker/CI) is opt-in via /sdlc-deploy, not run on every feature.
- One source of truth per guardrail (hooks), not duplicated in permissions.
