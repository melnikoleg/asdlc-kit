---
name: sdlc-plan
description: Run the planning phase only: codebase-agent (brownfield scan) → product-agent → planner-agent → architect-agent, producing CODEBASE_CONTEXT.md + PRD.md + PLAN.md + ADR.md. Use when you want to review and approve the plan before any code is written. Requires: issue-name and requirement description. Invoke as: /sdlc-plan <issue-name> "<requirement>"
---

# SDLC Plan

Produce all planning artifacts. Stop before implementation.

## Steps
1. Create `docs/{issue}/`
2. Invoke `codebase-agent` → `docs/{issue}/CODEBASE_CONTEXT.md` (or "greenfield" note)
3. Invoke `product-agent` (+ CODEBASE_CONTEXT.md if present) → `docs/{issue}/PRD.md`
4. Invoke `planner-agent` (+ CODEBASE_CONTEXT.md if present) → `docs/{issue}/PLAN.md`
5. Invoke `architect-agent` (+ CODEBASE_CONTEXT.md if present) → `docs/{issue}/ADR.md` (or skip)
6. Invoke `acceptance-agent` (PRD.md) → `docs/{issue}/ACCEPTANCE.md` — a held-out
   acceptance suite (one `Acceptance: <cmd>` per AC) authored BEFORE any code.
   The developer must never read it; it is graded independently after review.
7. Show plan summary. Say: "Review the plan, then run /sdlc-implement {issue} to start coding."

## Output
- CODEBASE_CONTEXT.md — existing stack/conventions/integration points (brownfield repos only)
- PRD.md — structured requirements with binary-testable ACs
- PLAN.md — phased plan, each phase has validation shell command
- ADR.md — architecture decisions (only if non-trivial choices exist)
- ACCEPTANCE.md — held-out acceptance suite (one runnable check per AC)

## Anti-Patterns
- Do NOT start implementation in this skill
- Do NOT skip PRD — it is the contract for all downstream agents

## Related Skills
- /sdlc-orchestrate — full pipeline
- /sdlc-implement — next step after review
