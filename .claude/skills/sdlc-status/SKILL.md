---
name: sdlc-status
description: Show SDLC pipeline status for all issues or a specific one, derived from which artifacts exist in docs/{issue}/. Read-only. Invoke as: /sdlc-status [issue-name]
---

# SDLC Status

Status is derived from artifact presence — there is no STATE.json to read.

## Phase Derivation
For an issue, the current phase is the first missing artifact in this order:
```
PRD.md            → product
PLAN.md           → plan
ADR.md (optional) → architect   (a "no ADR needed" note also counts as present)
IMPLEMENTATION.md → implement
REVIEW.md + QA.md → review
PRODUCTION_READINESS.md → done
ESCALATION.md present → escalated
```

## Steps

### Without issue-name (show all)
1. Glob `docs/*/` directories.
2. For each, derive phase from artifacts present (rules above).
3. Print a table:
   ```
   Issue              Phase          Next step
   ─────────────────────────────────────────────────────────
   auth-api           implement      /sdlc-implement auth-api
   user-profile       done           —
   payments           escalated      see docs/payments/ESCALATION.md
   ```
4. Flags: 🔴 escalated | ✅ done | 🟡 in progress

### With issue-name (detail view)
1. List artifacts present vs expected:
   ```
   ✅ PRD.md       ✅ PLAN.md      ✅ ADR.md
   ✅ IMPLEMENTATION.md           🔴 REVIEW.md (missing)
   🔴 QA.md (missing)
   ```
2. Show the next command to run (`/sdlc-orchestrate {issue}` resumes from the gap).

## Anti-Patterns
- Do NOT modify any files — read-only
- Do NOT start or resume pipelines — just report status

## Related Skills
- /sdlc-orchestrate — start or resume pipeline
- /sdlc-fix — fix blocking issues
