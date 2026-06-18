---
name: sdlc-plan
description: Run product-agent, planner-agent, architect-agent to produce PRD+PLAN+ADR. Usage: /sdlc-plan <issue-name> "<requirement>"
---

# SDLC Plan Skill

Produce all planning artifacts before implementation.

## Steps
1. Spawn product-agent with requirement -> PRD.md
2. Spawn planner-agent -> PLAN.md
3. Spawn architect-agent -> ADR.md
4. Display PLAN.md summary, ask for human approval
5. Report: "Planning complete. Run /factory {issue} --implement to start coding"
