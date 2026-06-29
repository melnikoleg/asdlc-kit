# syntax=docker/dockerfile:1
#
# Self-contained image that runs the Agentic SDLC pipeline on a clean,
# disposable environment. It carries everything the pipeline needs to run
# autonomously, end to end:
#   - Python 3.12 + the runtime/ LangGraph orchestrator and its deps
#   - Node.js + the Claude Code CLI (the Claude Agent SDK spawns it headless)
#   - git + a Python/Node toolchain so the developer/qa nodes can actually
#     run the generated project's validation commands and tests
#
# ANTHROPIC_API_KEY is injected at runtime — never baked into the image.

############################
# Stage 1 — build the Python venv (deps only; no secrets, no Node)
############################
FROM python:3.12-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

RUN python -m venv "$VIRTUAL_ENV"

WORKDIR /build
# Only the packaging metadata is needed to resolve dependencies, so this
# layer caches across source-only changes.
COPY runtime/pyproject.toml runtime/README.md ./runtime/
COPY runtime/__init__.py ./runtime/__init__.py
RUN pip install "./runtime[server,postgres]"

############################
# Stage 2 — runtime image
############################
FROM python:3.12-slim-bookworm AS runtime

ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NODE_MAJOR=20 \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# git: the pipeline operates on a repo. bash: the .claude/ hooks are bash.
# Node.js: required by the Claude Code CLI that the Agent SDK launches.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git bash ca-certificates curl gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get purge -y gnupg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Python deps built in stage 1.
COPY --from=builder /opt/venv /opt/venv

# Non-root user (UID 1000 matches the common host UID for bind-mounted docs/).
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app
# The whole repo: config.py finds the repo root by walking up for .claude/,
# so agents, rules, hooks and the runtime package must all be present together.
COPY --chown=appuser:appuser . /app
# Checkpoint dir, owned by appuser so a named volume inherits writable perms.
RUN mkdir -p /app/.asdlc && chown -R appuser:appuser /app/.asdlc \
    && chmod +x /app/.claude/hooks/*.sh /app/docker/entrypoint.sh

USER appuser

# acceptEdits + headless: surface what the pipeline is doing.
ENV ASDLC_MODE=autonomous \
    ASDLC_AUTO_APPROVE=1 \
    CHECKPOINT_BACKEND=sqlite \
    ASDLC_SQLITE_PATH=/app/.asdlc/checkpoints.sqlite

ENTRYPOINT ["/app/docker/entrypoint.sh"]
