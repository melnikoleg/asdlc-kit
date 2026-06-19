---
name: factory-status
description: "Check SDLC pipeline status. Usage: /factory-status [issue-name]"
---

# /factory-status

Shorthand for /sdlc-status. See `.claude/skills/sdlc-status/SKILL.md`.

## Instructions
Glob docs/*/STATE.json, parse each, display table with phase/iteration/flags.
If issue-name given: show detail view with artifact completeness.
