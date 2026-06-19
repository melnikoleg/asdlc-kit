---
name: sdlc-implement
description: Run implementation phase only. Requires docs/{issue}/PRD.md and docs/{issue}/PLAN.md to already exist. Invokes developer-agent, runs all PLAN.md validation commands, captures real terminal output. Use after /sdlc-plan and human approval. Invoke as: /sdlc-implement <issue-name>
---

# SDLC Implement

Code generation phase using existing plan artifacts.

## Pre-flight Checks (abort if any fail)
1. `docs/{issue}/PLAN.md` must exist
2. `docs/{issue}/PRD.md` must exist
3. Read `docs/{issue}/ADR.md` if exists — its constraints are BINDING

## Steps
1. Update STATE.json: phase="implement"
2. Invoke `developer-agent`:
   - Input: PLAN.md + ADR.md + PRD.md (for AC context)
   - Developer runs every validation command from PLAN.md
   - Developer writes IMPLEMENTATION.md with REAL terminal output as evidence
3. Update STATE.json: phase="review", artifacts=[list all changed files]

## Success Criteria
- IMPLEMENTATION.md has all PLAN.md validation commands showing real PASS output
- All changed source files are listed in IMPLEMENTATION.md Changes table
- No hardcoded secrets in any generated code

## Anti-Patterns
- Do NOT skip without PLAN.md — it is the spec
- Do NOT accept fabricated command output
- Do NOT modify files outside the issue's scope

## Related Skills
- /sdlc-plan — create PLAN.md first
- /sdlc-review — run after implementation
