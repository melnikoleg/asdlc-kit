---
name: sdlc-review
description: Run reviewer-agent, qa-agent, devops-agent in parallel on current implementation. Usage: /sdlc-review <issue-name>
---

# SDLC Review Skill

Trigger parallel expert review after implementation.

## Steps
1. Verify docs/{issue}/IMPLEMENTATION.md exists
2. Spawn three parallel Agent() calls: reviewer-agent, qa-agent, devops-agent
3. Collect verdicts
4. If any NEEDS_FIX: summarize blocking issues by agent
5. If all APPROVED: write PRODUCTION_READINESS.md
