---
name: sdlc-orchestrate
description: Run the complete agentic SDLC pipeline end-to-end: product-agent → planner-agent → architect-agent → [human approval gate] → developer-agent → reviewer-agent + qa-agent + devops-agent in parallel → fix loop (max 3x) → PRODUCTION_READINESS.md. Use when you want to build a feature from a requirement description all the way to production-ready code and deployment artifacts with minimal human intervention. Invoke as: /sdlc-orchestrate <issue-name> "<requirement description>"
---

# SDLC Orchestrate

Full autonomous pipeline from requirements to production-ready code.

## Steps

### Step 1 — Init
1. Validate issue-name: kebab-case, 1-50 chars
2. Create `docs/{issue}/` directory
3. Write `docs/{issue}/STATE.json`: phase="product", iteration=0, failing_agents=[], artifacts=[]

### Step 2 — Product Agent
Invoke `product-agent` with the requirement text.
Output: `docs/{issue}/PRD.md` with binary-testable acceptance criteria.

### Step 3 — Planner Agent
Invoke `planner-agent` with PRD.md.
Output: `docs/{issue}/PLAN.md` with phases, tasks, and validation shell commands.

### Step 4 — Architect Agent
Invoke `architect-agent` with PRD.md + PLAN.md.
Output: `docs/{issue}/ADR.md` (or "no ADR needed").

### Step 5 — Human Approval Gate ⛔ MANDATORY STOP
Show summary:
```
📋 PLAN READY: {issue}
Phases: N | Tasks: N | Complexity: X | ADR: YES/NO
Type "approve" to start implementation, or "cancel" to stop.
```
Wait for explicit "approve". Do NOT proceed without it.

### Step 6 — Developer Agent
Update STATE.json: phase="implement".
Invoke `developer-agent` with PLAN.md + ADR.md.
Output: `docs/{issue}/IMPLEMENTATION.md` + source code files.

### Step 7 — Parallel Review
Update STATE.json: phase="review".
Launch THREE agents simultaneously:
- `reviewer-agent` → `docs/{issue}/REVIEW.md`
- `qa-agent` → `docs/{issue}/QA.md` + test files
- `devops-agent` → `docs/{issue}/DEPLOY.md` + Dockerfile + CI config

### Step 8 — Fix Loop (max 3x)
If any NEEDS_FIX:
  Collect all blocking issues from REVIEW.md and QA.md.
  Invoke `developer-agent` (fix scope only).
  Increment STATE.json iteration.
  Re-run ONLY agents that had NEEDS_FIX.
  Repeat until all APPROVED or iteration >= 3.

If iteration >= 3 and still failing:
  Write `docs/{issue}/ESCALATION.md`, STATE.json phase="escalated", STOP.

### Step 9 — Completion
Write `docs/{issue}/PRODUCTION_READINESS.md`.
Update STATE.json: phase="done".

## Anti-Patterns
- NEVER skip the human approval gate at Step 5
- NEVER fabricate terminal output in IMPLEMENTATION.md
- NEVER run fix loop more than 3 times — escalate instead
- NEVER continue if a required input artifact is missing

## Related Skills
- /sdlc-plan — planning phase only (Steps 1-5)
- /sdlc-implement — implementation only (Step 6)
- /sdlc-review — review only (Step 7)
- /sdlc-fix — targeted fix for known issues
- /sdlc-status — check pipeline state
