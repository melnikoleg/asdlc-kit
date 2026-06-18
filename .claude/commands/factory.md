---
name: factory
description: "Full agentic SDLC pipeline. Usage: /factory <issue-name> "<description>" [--resume|--plan|--implement|--review]"
---

# /factory

Run the autonomous software factory pipeline.

## Usage
- /factory <issue> "<description>"   Full pipeline
- /factory <issue> --resume          Resume from STATE.json
- /factory <issue> --plan            Start from planning (needs PRD.md)
- /factory <issue> --implement       Start from implementation (needs PLAN.md)
- /factory <issue> --review          Start from review (needs IMPLEMENTATION.md)

## Instructions for Claude
1. Validate: issue = kebab-case 1-50 chars, description non-empty
2. Create docs/{issue}/ directory
3. Write initial STATE.json (phase="product")
4. Warn (don't block) on uncommitted git changes
5. For --resume: read STATE.json, continue from current phase
6. Delegate to orchestrator-agent with: issue name, description, start phase
7. At PLAN.md gate: show summary, require explicit human "approve" before implementation
8. Report each phase completion
