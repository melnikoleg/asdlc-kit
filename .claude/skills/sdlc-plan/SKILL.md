---
name: sdlc-plan
description: Run the planning phase only: product-agent → planner-agent → architect-agent, producing PRD.md + PLAN.md + ADR.md. Use when you want to review and approve the plan before any code is written. Requires: issue-name and requirement description. Invoke as: /sdlc-plan <issue-name> "<requirement>"
---

# SDLC Plan

Produce all planning artifacts. Stop before implementation.

## Steps
1. Create `docs/{issue}/`, write STATE.json (phase="product")
2. Invoke `product-agent` → `docs/{issue}/PRD.md`
3. Invoke `planner-agent` → `docs/{issue}/PLAN.md`
4. Invoke `architect-agent` → `docs/{issue}/ADR.md` (or skip)
5. Show plan summary. Say: "Review the plan, then run /sdlc-implement {issue} to start coding."

## Output
- PRD.md — structured requirements with binary-testable ACs
- PLAN.md — phased plan, each phase has validation shell command
- ADR.md — architecture decisions (only if non-trivial choices exist)

## Anti-Patterns
- Do NOT start implementation in this skill
- Do NOT skip PRD — it is the contract for all downstream agents

## Related Skills
- /sdlc-orchestrate — full pipeline
- /sdlc-implement — next step after review
- /prd-writer — standalone PRD generation
