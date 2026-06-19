---
name: debug-agent
description: Systematically debug a failing test, error, or unexpected behavior. Reads error output, traces root cause through the call stack, proposes minimal fix with explanation. Use when facing a bug you can't immediately locate. Invoke as: /debug-agent "<error message or symptom>"
---

# Debug Agent

Systematic root cause analysis and minimal fix.

## Steps
1. Parse the error: type, message, file, line number, stack trace
2. Read the failing file at the reported line
3. Trace backwards: what calls this? What state does it expect?
4. Check: recent git changes (git log -10 --oneline), related tests
5. Identify root cause category:
   - **Type error** — wrong data shape, missing null check
   - **Logic error** — incorrect condition, off-by-one
   - **State error** — race condition, unexpected mutation
   - **Config error** — wrong env var, missing dependency
   - **Integration error** — API contract mismatch, schema change

6. Propose MINIMAL fix (change only what's needed):
   ```
   Root cause: {explanation}
   File: {file}:{line}
   Fix: {specific code change}
   Why: {explanation}
   Risk: LOW/MEDIUM/HIGH
   ```

7. Apply fix and re-run the failing test to verify

## Rules
- Fix the root cause, not the symptom
- Minimal change: don't refactor while debugging
- Verify the fix: run the test again
- If multiple hypotheses: test cheapest one first

## Anti-Patterns
- Do NOT suppress errors with try/catch without handling
- Do NOT add print-debugging to production code
- Do NOT fix symptoms (e.g., adding null checks everywhere instead of finding why null appears)

## Related Skills
- /test-writer — add a regression test after fixing
- /code-reviewer — review the fix before committing
