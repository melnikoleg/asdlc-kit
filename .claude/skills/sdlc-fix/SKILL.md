---
name: sdlc-fix
description: Fix blocking issues from REVIEW.md or QA.md. Reads blocking issues, invokes developer-agent with scoped fix context, then re-runs only the failing review agents. Use after /sdlc-review returns NEEDS_FIX. Invoke as: /sdlc-fix <issue-name>
---

# SDLC Fix

Targeted fix loop for blocking review issues.

## Pre-flight Checks
1. Read `docs/{issue}/REVIEW.md` — collect BLOCKING items only (not non-blocking)
2. Read `docs/{issue}/QA.md` — collect failing ACs
3. Count prior fix rounds from `docs/{issue}/ESCALATION.md` history / prior IMPLEMENTATION.md
   fix entries — if 3 rounds already done: write ESCALATION.md, STOP, tell user to fix manually

## Steps
1. Build fix scope document listing ONLY:
   - Blocking issues from REVIEW.md (file:line, problem, required fix)
   - Failing ACs from QA.md (AC-N, test failure, required fix)

2. Invoke `developer-agent` with:
   - PLAN.md (reference)
   - ADR.md (binding constraints — cannot violate)
   - Fix scope document
   - Instruction: "Modify ONLY files related to these blocking issues"

3. After developer completes:
   - Re-run ONLY agents whose verdict was NEEDS_FIX (not agents that were APPROVED)
   - If now all APPROVED: write PRODUCTION_READINESS.md
   - If still NEEDS_FIX: report remaining issues, print which fix round this was

## Escalation Trigger
```
⚠️ ESCALATION: 3 fix iterations exhausted
Issue: {issue}
Remaining blocks: N
Write docs/{issue}/ESCALATION.md and stop.
Human review required.
```

## Anti-Patterns
- NEVER re-run agents that already returned APPROVED
- NEVER allow changes to files unrelated to blocking issues
- NEVER run more than 3 total iterations — escalate instead

## Related Skills
- /sdlc-review — get blocking issues
- /sdlc-status — see what artifacts exist
