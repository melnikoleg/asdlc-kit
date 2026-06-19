---
name: sdlc-review
description: Run parallel adversarial review: reviewer-agent + qa-agent + devops-agent simultaneously on a completed implementation. Returns aggregated APPROVED or NEEDS_FIX verdict with specific blocking issues. Use after /sdlc-implement. Invoke as: /sdlc-review <issue-name>
---

# SDLC Review

Parallel review by three independent specialist agents.

## Pre-flight Checks
1. `docs/{issue}/IMPLEMENTATION.md` must exist
2. `docs/{issue}/PRD.md` must exist

## Steps
1. Update STATE.json: phase="review"
2. Launch THREE agents IN PARALLEL (not sequentially):
   - `reviewer-agent` → checks: code quality, security (OWASP Top 10), ADR compliance, PRD AC verification
   - `qa-agent` → writes and runs tests mapped to every PRD AC
   - `devops-agent` → creates/validates Dockerfile, CI pipeline, DEPLOY.md

3. Collect verdicts from all three.

4. Aggregate and display:
   - All APPROVED → write PRODUCTION_READINESS.md, print ✅ summary
   - Any NEEDS_FIX → group blocking issues by agent:
     ```
     🔴 REVIEWER (N blocking): file:line — problem — required fix
     🔴 QA (N blocking): AC-X — test failure — fix
     🔴 DEVOPS (N blocking): issue — fix
     ```
     Print: "Run /sdlc-fix {issue} to address these N blocking issues"

## Output
- `docs/{issue}/REVIEW.md`
- `docs/{issue}/QA.md` + test files
- `docs/{issue}/DEPLOY.md` + deployment artifacts
- `docs/{issue}/PRODUCTION_READINESS.md` (if all APPROVED)

## Anti-Patterns
- NEVER run the three agents sequentially — must be parallel
- NEVER block on style issues — only security, broken ACs, ADR violations
- NEVER skip QA — test coverage is mandatory

## Related Skills
- /sdlc-implement — run before review
- /sdlc-fix — fix blocking issues
- /sdlc-qa — QA only
