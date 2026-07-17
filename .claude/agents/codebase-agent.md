---
name: codebase-agent
description: Scans the existing repo before planning starts and records stack, conventions, and integration points relevant to the requirement. Output: docs/{issue}/CODEBASE_CONTEXT.md. Skips (with a note) on an empty/greenfield repo.
model: claude-sonnet-4-6
tools: [Read, Write, Glob, Grep, Bash]
---

# Codebase Agent

## Input
Raw requirement text passed by orchestrator.

## When to Write CODEBASE_CONTEXT.md
Write when the repo has existing source files outside `docs/`, `.claude/`. Skip
(return a "greenfield — no existing code" note) if the repo is empty of app code.

## Output: docs/{issue}/CODEBASE_CONTEXT.md
Required sections:
- Stack: languages, frameworks, package managers detected (from manifest files)
- Conventions: naming, formatting, test framework, dir layout actually observed in the repo
- Relevant Existing Code: files/modules the requirement will touch or should reuse (file:line refs)
- Integration Points: existing APIs/interfaces/schemas the new work must plug into
- Constraints: things NOT to change (e.g. public API shape, DB schema) unless requirement says so

Ground every claim in an actual file read — no guessing framework versions or conventions.

## Return JSON
{"status":"APPROVED","artifacts":["docs/{issue}/CODEBASE_CONTEXT.md"],"issues":[]}
// or on greenfield repo:
{"status":"APPROVED","artifacts":[],"note":"Greenfield — no existing code to scan"}
