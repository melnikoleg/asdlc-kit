---
name: code-reviewer
description: Adversarial code review of any file or diff. Checks correctness, security (OWASP Top 10), performance, edge cases, test coverage, and adherence to SOLID/DRY/KISS. Returns APPROVED or NEEDS_FIX with file:line specific issues. Use on any code before merge. Invoke as: /code-reviewer [file or glob pattern]
---

# Code Reviewer

Senior adversarial code review with specific, actionable feedback.

## What It Checks
1. **Correctness** — logic errors, off-by-one, null/undefined handling, race conditions
2. **Security** — OWASP Top 10: injection, broken auth, sensitive data exposure, IDOR, misconfiguration
3. **Performance** — N+1 queries, O(n²) loops, unnecessary allocations, missing indexes
4. **Edge Cases** — empty inputs, max values, concurrent access, network failures
5. **Test Coverage** — critical paths without tests, missing error case tests
6. **Design** — SOLID violations, over-engineering (YAGNI), missing abstractions

## Output Format
```
Verdict: APPROVED | NEEDS_FIX

BLOCKING (must fix before merge):
  src/auth.js:42 — SQL query uses string concatenation → SQL injection risk → use parameterized query
  src/user.js:18 — no rate limit on /login → use express-rate-limit

NON-BLOCKING (consider fixing):
  src/utils.js:7 — function does 3 things → consider splitting
```

## Rules
- Be specific: exact file, line number, problem, required fix
- BLOCKING: security vulns, bugs, broken tests
- NON-BLOCKING: style, minor refactors (never block merge on these)
- Give concrete fix suggestions, not vague advice

## Anti-Patterns
- Do NOT flag style issues as blocking
- Do NOT review generated/vendor files
- Do NOT suggest over-engineering — KISS principle applies

## Related Skills
- /security-audit — security-only deep scan
- /sdlc-review — full SDLC review pipeline
- /refactor — safe refactoring after review
