---
name: sdlc-status
description: Show SDLC pipeline status for all active issues or a specific one. Displays phase, iteration, failing agents, artifact completeness, and time since last update. Use to check what is in progress, paused, escalated, or done. Invoke as: /sdlc-status [issue-name]
---

# SDLC Status

Pipeline status dashboard.

## Steps

### Without issue-name (show all)
1. Glob `docs/*/STATE.json`
2. Parse each: issue, phase, iteration, failing_agents, updated_at
3. Print table:
   ```
   Issue              Phase          Iter  Failing     Updated
   ────────────────────────────────────────────────────────────
   auth-api           implement      0     —           2026-06-18 19:30
   user-profile       done           1     —           2026-06-17 14:20
   payments           escalated      3     reviewer    2026-06-16 09:10
   ```
4. Flags: 🔴 escalated | 🟡 paused >24h | ✅ done

### With issue-name (detail view)
1. Print full STATE.json (pretty)
2. List artifacts present vs expected:
   ```
   ✅ PRD.md       ✅ PLAN.md      ✅ ADR.md
   ✅ IMPLEMENTATION.md           🔴 REVIEW.md (missing)
   🔴 QA.md (missing)             🔴 DEPLOY.md (missing)
   ```
3. Show resume command: `/sdlc-orchestrate {issue} --resume`

## Anti-Patterns
- Do NOT modify any files in this skill — read-only
- Do NOT start or resume pipelines — just report status

## Related Skills
- /sdlc-orchestrate — start or resume pipeline
- /sdlc-fix — fix blocking issues
