# Agentic SDLC Best Practices

## Three Pillars That Prevent Collapse
1. Spec-First: no implementation without approved PRD + PLAN + ADR
2. Evidence Required: IMPLEMENTATION.md must contain REAL command output
3. Adversarial Review: reviewer and qa-agent run independently with separate contexts

## Anti-Patterns This Kit Prevents
- Early stop without artifact (incomplete-pipeline-guard hook)
- Vague untestable ACs (product-agent rules enforce binary criteria)
- Fabricated test output (developer-agent rules)
- Infinite fix loops (max 3 iterations)
- Sensitive file exposure (validate-write-path hook)

## Model Strategy
- Opus: orchestrator, architect, reviewer (high-stakes decisions)
- Sonnet: product, planner, developer, qa, devops (high-volume execution)

## Extending
Add agent: create .claude/agents/{name}-agent.md, add to orchestrator pipeline,
add artifact to CLAUDE.md table, add schema check to validate-artifact-schema.sh hook.
