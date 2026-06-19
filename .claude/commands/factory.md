---
name: factory
description: "Alias for full SDLC pipeline. Usage: /factory <issue-name> "<description>" [--plan|--implement|--review]"
---

# /factory

Shorthand for /sdlc-orchestrate. See `.claude/skills/sdlc-orchestrate/SKILL.md` for full docs.

## Usage
- /factory <issue> "<description>"     Full pipeline
- /factory <issue>                     Resume — skips phases whose artifact already exists
- /factory <issue> --plan              Stop after planning (PRD+PLAN+ADR)
- /factory <issue> --implement         Start from implementation
- /factory <issue> --review            Start from review

## Instructions
Run the /sdlc-orchestrate flow with the given issue and description.
Resume is implicit: skip any phase whose output artifact already exists in
`docs/{issue}/` and continue from the first missing one.
