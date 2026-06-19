# Code Quality Rules (Always Active)

- KISS: simplest solution that meets requirements
- YAGNI: do not add functionality not in PRD
- DRY: extract shared logic into functions/modules
- Every public function needs at least one test
- Tests must be isolated: no shared state between tests
- Tests must be deterministic: no random sleeps or time-dependent assertions
- Code must pass all PLAN.md validation commands before review
