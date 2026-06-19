---
name: docker-setup
description: Create or improve Dockerfile and docker-compose.yml for a project. Multi-stage build, non-root user, health checks, proper signal handling, minimal image. Auto-detects tech stack (Node/Python/Go/.NET/Java). Invoke as: /docker-setup
---

# Docker Setup

Production-quality Dockerfile and docker-compose for any stack.

## Steps
1. Detect tech stack: scan package.json, pyproject.toml, go.mod, *.csproj, pom.xml
2. Generate multi-stage Dockerfile:
   - Stage 1 (builder): full deps, compile/build
   - Stage 2 (runner): minimal base, copy artifacts only
3. Security requirements (mandatory):
   - Non-root user: `RUN adduser -D appuser && USER appuser`
   - Pinned base image: `node:20.18-alpine3.20` not `node:latest`
   - No secrets in image: use ARG for build-time, ENV for runtime
   - `.dockerignore` to exclude node_modules, .env, .git
4. Health check: `HEALTHCHECK --interval=30s --timeout=3s CMD wget -q http://localhost:PORT/health || exit 1`
5. Signal handling: use `ENTRYPOINT ["node"]` not shell form
6. docker-compose.yml with:
   - Named volumes for persistent data
   - Health check dependencies (`depends_on: condition: service_healthy`)
   - Environment variables via `.env` file reference

## Output
- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`
- Print: "Build: docker compose up --build"

## Anti-Patterns
- NEVER use `latest` tag in production Dockerfiles
- NEVER run as root
- NEVER copy .env or secrets into image
- NEVER use shell form for ENTRYPOINT (misses signals)

## Related Skills
- /ci-setup — CI/CD pipeline
- /sdlc-deploy — full deployment pipeline
