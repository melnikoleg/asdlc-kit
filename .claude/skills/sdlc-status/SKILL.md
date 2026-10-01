---
name: sdlc-status
description: Show SDLC pipeline status for all issues or a specific one, read from the runtime's docs/{issue}/STATE.json mirror. Read-only. Invoke as: /sdlc-status [issue-name]
---

# SDLC Status

The runtime mirrors each pipeline's state to `docs/{issue}/STATE.json`
(`phase`, `iteration`, `failing_agents`, `artifacts`, `updated_at`).

## Steps

### Without issue-name
1. Glob `docs/*/STATE.json` and read each.
2. Print a table: Issue | Phase | Iteration | Failing | Next step.
   Next step by phase: `awaiting_approval` → `/factory <issue> --approve`;
   `escalated` → read `docs/<issue>/ESCALATION.md`; `done` → —;
   anything else → `/factory <issue> --resume` if it looks stalled.
3. Flags: 🔴 escalated | ✅ done | 🟡 in progress

### With issue-name
1. Read `docs/<issue>/STATE.json` and list which of PRD, PLAN, TEST_STRATEGY, ADR, ACCEPTANCE,
   IMPLEMENTATION, REVIEW, QA, PRODUCTION_READINESS exist.
2. Show `METRICS.json` totals (cost, tokens) if present.

## Anti-Patterns
- Do NOT modify any files, start, or resume pipelines — just report.
