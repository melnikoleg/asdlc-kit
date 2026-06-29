---
name: test-writer
description: Write comprehensive tests for existing code: unit tests, integration tests, edge cases, error paths. Auto-detects test framework (pytest/jest/vitest/go test/rspec). Follows TDD: write test, verify it fails, implement or verify existing code makes it pass. Use when you need test coverage for untested code. Invoke as: /test-writer <file-or-directory>
---

# Test Writer

Comprehensive test generation for existing code.

## Steps
1. Read target file(s) and understand the API surface
2. Detect test framework: check package.json (jest/vitest/mocha), pyproject.toml (pytest), go.mod, Gemfile
3. Scan existing tests to avoid duplication
4. Write tests covering:
   - Happy path for every public function/method
   - Edge cases: empty input, null/undefined, max values, special chars
   - Error paths: invalid input, network failures, permission denied
   - Boundary conditions: off-by-one, empty collections, single items

## Test Quality Rules
- Each test has one clear assertion
- Test names describe behavior: `test_login_with_invalid_password_returns_401`
- No dependencies between tests (each test is isolated)
- Mock external services (DB, HTTP, filesystem)
- Tests run in < 1 second each (unit tests)

## Output
- Test file(s) in appropriate location (auto-detected convention)
- Print: "N tests written, run with: {detected command}"

## Anti-Patterns
- Do NOT write tests that test framework/library internals
- Do NOT write tests with external network calls (mock them)
- Do NOT write tests that depend on test execution order
- Do NOT write tests that check implementation details (test behavior, not code)

## Related Skills
- /sdlc-review — runs qa-agent with tests mapped to PRD acceptance criteria
- /code-reviewer — review before writing more tests
