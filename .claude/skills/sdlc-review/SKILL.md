---
name: sdlc-review
description: Run parallel adversarial review: reviewer-agent + qa-agent simultaneously on a completed implementation. Returns aggregated APPROVED or NEEDS_FIX verdict with specific blocking issues. Use after /sdlc-implement. Invoke as: /sdlc-review <issue-name>
---

# SDLC Review

Parallel review by two independent specialist agents. Deployment artifacts are
out of scope here — run `/sdlc-deploy {issue}` separately if the change needs them.

## Pre-flight Checks
1. `docs/{issue}/IMPLEMENTATION.md` must exist
2. `docs/{issue}/PRD.md` must exist

## Steps
1. Launch TWO agents IN PARALLEL (not sequentially):
   - `reviewer-agent` → checks: code quality, security (OWASP Top 10), ADR compliance, PRD AC verification
   - `qa-agent` → writes and runs tests mapped to every PRD AC

2. Collect verdicts from both.

3. Aggregate and display:
   - All APPROVED → write PRODUCTION_READINESS.md, print ✅ summary
   - Any NEEDS_FIX → group blocking issues by agent:
     ```
     🔴 REVIEWER (N blocking): file:line — problem — required fix
     🔴 QA (N blocking): AC-X — test failure — fix
     ```
     Print: "Run /sdlc-fix {issue} to address these N blocking issues"

## Output
- `docs/{issue}/REVIEW.md`
- `docs/{issue}/QA.md` + test files
- `docs/{issue}/PRODUCTION_READINESS.md` (if all APPROVED)

## Anti-Patterns
- NEVER run the agents sequentially — must be parallel
- NEVER block on style issues — only security, broken ACs, ADR violations
- NEVER skip QA — test coverage is mandatory

## Related Skills
- /sdlc-implement — run before review
- /sdlc-fix — fix blocking issues
- /sdlc-deploy — optional Docker/CI/runbook generation
