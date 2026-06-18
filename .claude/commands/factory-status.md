---
name: factory-status
description: "Check SDLC pipeline status. Usage: /factory-status [issue-name]"
---

# /factory-status

## Instructions for Claude
1. Glob docs/*/STATE.json
2. Parse: issue, phase, iteration, failing_agents, updated_at
3. Display as table
4. If issue-name provided: show full STATE.json + STATUS.md
5. Flag: phase not "done" or "escalated" for >24h
