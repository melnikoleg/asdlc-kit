---
name: refactor
description: Safe, test-backed refactoring of a file or module. Identifies code smells (duplication, long methods, deep nesting, magic numbers), proposes refactoring plan, applies changes while keeping all tests passing. Use when improving code structure without changing behavior. Invoke as: /refactor <file-or-directory>
---

# Refactor

Safe refactoring: improve structure without changing behavior.

## Refactoring Process
1. Run existing tests (baseline: they must all pass)
2. Identify code smells:
   - **Duplication** — same logic in 2+ places → extract function
   - **Long method** — > 20 lines → extract helper methods
   - **Deep nesting** — > 3 levels → early returns / extract
   - **Magic numbers** — raw values in logic → named constants
   - **God object** — class doing too many things → split by responsibility
   - **Primitive obsession** — 5 string params → value object

3. Plan refactoring (show before applying):
   ```
   Proposed changes:
   1. Extract validateEmail() from registerUser() (lines 42-58)
   2. Replace magic number 86400 with SECONDS_PER_DAY constant
   3. Split UserService into UserService + AuthService (SRP)
   ```

4. Apply changes incrementally:
   - One refactoring at a time
   - Run tests after each change
   - If tests break: revert that step and investigate

5. Final: run full test suite, verify all pass

## Rules
- NEVER change behavior during refactoring
- NEVER refactor and fix a bug in the same commit
- ALWAYS have tests before refactoring (if no tests: /test-writer first)

## Anti-Patterns
- Do NOT rename + move + extract in one step (too risky)
- Do NOT refactor code you don't understand yet
- Do NOT introduce new abstractions during refactoring (YAGNI)

## Related Skills
- /test-writer — add tests before refactoring
- /code-reviewer — review after refactoring
- /debug-agent — fix bugs separately from refactoring
