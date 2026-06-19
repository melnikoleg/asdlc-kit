---
name: sdlc-qa
description: Run QA agent only: write tests mapped to every PRD acceptance criterion, execute them, produce QA.md with real test output and coverage map. Use when you need targeted test generation without full review. Invoke as: /sdlc-qa <issue-name>
---

# SDLC QA

Standalone test generation and execution mapped to acceptance criteria.

## Pre-flight Checks
1. `docs/{issue}/PRD.md` must exist (source of ACs)
2. `docs/{issue}/IMPLEMENTATION.md` must exist
3. Glob existing test directory to understand current coverage

## Steps
1. Invoke `qa-agent`:
   - Read all ACs from PRD.md
   - For each AC: write at least one automated test (TDD: write first, then run)
   - Detect existing test framework (pytest/jest/vitest/go test/other)
   - Run all tests, capture REAL terminal output
   - Write `docs/{issue}/QA.md` with:
     - Coverage Map: AC | Test Name | Status | Actual Output
     - New Tests Written: File | Test | Maps to AC
     - Test Run Evidence: command + real output
     - Verdict: APPROVED or NEEDS_FIX

## Success Criteria
- Every PRD AC has at least one passing automated test
- QA.md contains actual (not fabricated) test output
- Verdict is APPROVED

## Anti-Patterns
- NEVER write tests for framework internals — test business behavior only
- NEVER accept "tests pass" without showing actual output
- NEVER skip failing ACs — they are blocking issues

## Related Skills
- /sdlc-review — full parallel review including QA
- /test-writer — general test generation without AC mapping
