---
name: sdlc-deploy
description: Run devops-agent only: create or update Dockerfile, docker-compose, GitHub Actions CI/CD pipeline, and write DEPLOY.md deployment runbook. Use when you need deployment artifacts independently from the review pipeline. Invoke as: /sdlc-deploy <issue-name>
---

# SDLC Deploy

Standalone deployment artifact generation.

## Pre-flight Checks
1. `docs/{issue}/IMPLEMENTATION.md` must exist
2. Scan for existing: Dockerfile, docker-compose.yml, .github/workflows/ (Glob)

## Steps
1. Invoke `devops-agent`:
   - Create multi-stage Dockerfile (non-root user, minimal image)
   - Create/update docker-compose.yml with health checks
   - Create .github/workflows/{issue}.yml: lint → test → build → deploy stages
   - Write `docs/{issue}/DEPLOY.md`:
     - Env Vars table (name, required, description)
     - Health Check endpoints
     - Rollback Plan (exact commands)
     - CI/CD Stages description
     - Operations Runbook

## Security Rules
- ZERO hardcoded secrets — all via env vars
- Dockerfile: non-root user, multi-stage, pinned base image digest
- Secrets managed via GitHub Secrets or equivalent

## Anti-Patterns
- NEVER hardcode API keys, passwords, tokens in Dockerfile or CI config
- NEVER use `root` user in production container
- NEVER skip rollback plan

## Related Skills
- /sdlc-review — code + QA review (run before deploy)
- /sdlc-orchestrate — full pipeline
