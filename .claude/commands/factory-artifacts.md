---
name: factory-artifacts
description: "List artifacts for an issue. Usage: /factory-artifacts <issue-name>"
---

# /factory-artifacts

## Instructions for Claude
1. Glob docs/{issue}/*.md and docs/{issue}/*.json
2. Show: filename, size, first heading line
3. Highlight missing expected artifacts:
   PRD.md, PLAN.md, ADR.md, IMPLEMENTATION.md, REVIEW.md, QA.md, DEPLOY.md, PRODUCTION_READINESS.md
4. Show completion: N/8 artifacts present
