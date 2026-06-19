---
name: factory
description: "Alias for full SDLC pipeline. Usage: /factory <issue-name> "<description>" [--resume|--plan|--implement|--review]"
---

# /factory

Shorthand for /sdlc-orchestrate. See `.claude/skills/sdlc-orchestrate/SKILL.md` for full docs.

## Usage
- /factory <issue> "<description>"     Full pipeline
- /factory <issue> --resume            Resume from STATE.json
- /factory <issue> --plan              Stop after planning (PRD+PLAN+ADR)
- /factory <issue> --implement         Start from implementation
- /factory <issue> --review            Start from review

## Instructions
Delegate to orchestrator-agent with issue, description, and start phase.
For --resume: read STATE.json, continue from current phase.
