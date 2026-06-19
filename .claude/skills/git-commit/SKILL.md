---
name: git-commit
description: Write a Conventional Commits compliant commit message for staged changes. Analyzes git diff, groups changes by type (feat/fix/refactor/test/docs/chore), and writes a structured multi-line commit. Use before every commit. Invoke as: /git-commit
---

# Git Commit

Generate a Conventional Commits message from staged changes.

## Steps
1. Run `git diff --staged` to see what's staged
2. If nothing staged: print "Nothing staged. Run: git add <files>" and stop
3. Analyze changes and categorize:
   - `feat:` new user-facing functionality
   - `fix:` bug fix
   - `refactor:` code change without behavior change
   - `test:` adding/updating tests
   - `docs:` documentation only
   - `chore:` build, deps, tooling
   - `perf:` performance improvement
   - `ci:` CI/CD changes

4. Write commit message:
   ```
   <type>(<scope>): <short imperative description, max 72 chars>

   <body: what changed and why, not how>

   <footer: BREAKING CHANGE: ... or Closes #NNN>
   ```

5. Run: `git commit -m "<message>"`

## Rules
- Subject line: imperative mood ("add", not "added" or "adds")
- Subject line: max 72 chars
- Body: what and why, not how (code shows how)
- Breaking changes: always in footer with BREAKING CHANGE:

## Anti-Patterns
- Do NOT commit secrets, .env files, or credentials
- Do NOT stage everything blindly — check git status first
- Do NOT write vague messages like "fix stuff" or "update"

## Related Skills
- /code-reviewer — review before committing
- /sdlc-implement — implementation that produces commits
