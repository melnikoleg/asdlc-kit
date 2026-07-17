---
name: sdlc-orchestrate
description: Run the agentic SDLC pipeline end-to-end: codebase-agent (brownfield scan) → product-agent → planner-agent → architect-agent → [human approval gate] → developer-agent → reviewer-agent + qa-agent in parallel → fix loop (max 3x) → PRODUCTION_READINESS.md. Use when you want to build a feature from a requirement description all the way to reviewed, production-ready code. Invoke as: /sdlc-orchestrate <issue-name> "<requirement description>"
---

# SDLC Orchestrate

Full pipeline from requirement to reviewed code. You ARE the orchestrator —
delegate each phase to its agent, never do phase work yourself.

Pipeline state is derived from which artifacts exist in `docs/{issue}/`.
There is no STATE.json to maintain.

## Steps

### Step 1 — Init
1. Validate issue-name: kebab-case, 1-50 chars.
2. Create `docs/{issue}/`.

### Step 1.5 — Brownfield Scan
Invoke `codebase-agent` with the requirement text.
Output: `docs/{issue}/CODEBASE_CONTEXT.md` (stack, conventions, relevant existing
code, integration points), or a "greenfield" note if the repo has no existing code.

### Step 2 — Product
Invoke `product-agent` with the requirement text + CODEBASE_CONTEXT.md (if present).
Output: `docs/{issue}/PRD.md` with binary-testable acceptance criteria.

### Step 3 — Plan
Invoke `planner-agent` with PRD.md + CODEBASE_CONTEXT.md (if present).
Output: `docs/{issue}/PLAN.md` — phases, each with a runnable validation command.

### Step 4 — Architect
Invoke `architect-agent` with PRD.md + PLAN.md + CODEBASE_CONTEXT.md (if present).
Output: `docs/{issue}/ADR.md`, or a "no ADR needed" note if standard patterns apply.

### Step 5 — Human Approval Gate ⛔ MANDATORY STOP
Show summary:
```
📋 PLAN READY: {issue}
Phases: N | Tasks: N | ADR: YES/NO
Type "approve" to start implementation, or "cancel" to stop.
```
Wait for explicit "approve". Do NOT proceed without it.

### Step 6 — Implement
Invoke `developer-agent` with PLAN.md + ADR.md + PRD.md (AC context) + CODEBASE_CONTEXT.md (if present).
Output: `docs/{issue}/IMPLEMENTATION.md` (with REAL captured command output) + source files.

### Step 7 — Parallel Review
Launch TWO agents simultaneously:
- `reviewer-agent` → `docs/{issue}/REVIEW.md` (code quality, OWASP Top 10, ADR + AC compliance)
- `qa-agent` → `docs/{issue}/QA.md` + tests mapped to every PRD AC

Deployment artifacts are NOT generated here. Run `/sdlc-deploy {issue}` separately
when the change actually needs Docker/CI — most features do not.

### Step 8 — Fix Loop (max 3 rounds)
If any verdict is NEEDS_FIX:
  Collect all BLOCKING issues from REVIEW.md and QA.md.
  Invoke `developer-agent` in fix mode (touch only files tied to blocking issues;
  it appends a `## Fix Round N` section to IMPLEMENTATION.md — that heading count IS
  the round counter, so it survives across separate /sdlc-fix runs).
  Re-run ONLY the agents that returned NEEDS_FIX.
  Repeat until all APPROVED or 3 Fix Round headings exist.

If still failing after 3 iterations:
  Write `docs/{issue}/ESCALATION.md` with remaining blocks, STOP, ask the human to take over.

### Step 9 — Completion
When reviewer + qa are both APPROVED, write `docs/{issue}/PRODUCTION_READINESS.md`.

## Resume
Resume is implicit: re-run `/sdlc-orchestrate {issue}` (no requirement needed once
PRD.md exists). Skip any phase whose output artifact already exists; continue from
the first missing one. Run `/sdlc-status {issue}` to see what is present.

## Anti-Patterns
- NEVER skip the human approval gate at Step 5
- NEVER fabricate terminal output in IMPLEMENTATION.md
- NEVER run the fix loop more than 3 times — escalate instead
- NEVER continue if a required input artifact is missing
- NEVER do phase work yourself — always delegate to the agent

## Related Skills
- /sdlc-plan — planning only (Steps 1-5)
- /sdlc-implement — implementation only (Step 6)
- /sdlc-review — review only (Step 7)
- /sdlc-fix — targeted fix for known blocking issues
- /sdlc-deploy — optional Docker/CI/runbook generation
- /sdlc-status — show what artifacts exist for an issue
