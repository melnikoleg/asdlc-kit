# Multi-provider agent execution

This kit supports both Claude Code and Codex CLI without changing LangGraph
nodes, approval gates, test runner, or the existing executable specifications
workflow. Every agent role reads the existing .claude/agents/*.md definition;
both providers receive the same role instructions and shared project rules.

## Requirements

Install and authenticate at least one CLI on PATH, depending on the roles used:

- Claude Code CLI: `claude` (legacy, explicitly selected).
- Codex CLI: `codex`; login with `codex login` or configure API-key auth.

The installer creates project-level AGENTS.md for Codex if it does not
already exist. It never overwrites a project's existing AGENTS.md.

## Common commands

~~~bash
# 1) Codex Code Mode pipeline (default)
asdlc-runtime auth-api "Build auth API" --specs

# 2) Explicit Codex-only; Claude need not be installed
asdlc-runtime auth-api "Build auth API" --provider codex --specs

# 3) Hybrid: Codex default with Claude review
asdlc-runtime auth-api "Build auth API" --specs \
  --agent-provider reviewer=claude

# 4) Hybrid: Claude default with Codex developer
asdlc-runtime auth-api "Build auth API" --provider claude --specs \
  --agent-provider developer=codex

# 5) Human approves after reviewing PRD, PLAN and SPECIFICATIONS
asdlc-runtime auth-api --approve

# Resume after process interruption
asdlc-runtime auth-api --resume
~~~

Provider selection is checkpointed at initial start and restored from the
stored LangGraph state on approve/resume. To change provider routing, start
another issue; don't switch providers halfway through an approved pipeline.

Available agent roles: codebase, product, planner, architect, specification,
acceptance, developer, reviewer, qa, devops. Only active roles require CLIs.

## Environment configuration

~~~bash
ASDLC_PROVIDER=codex  # default; optional override
ASDLC_PROVIDER_REVIEWER=claude
ASDLC_CODEX_MODEL=gpt-6
ASDLC_CODEX_MODEL_SMART=gpt-6
ASDLC_CODEX_MODEL_WORKER=gpt-6
ASDLC_CODEX_MODEL_DEVELOPER=gpt-6
~~~

Codex model settings are separate from Claude model settings (ASDLC_MODEL_*).
If no Codex model override is set, the Codex CLI uses its own default model.
Environment values for models are resolved when agents execute, while **provider
choices** are persisted in the checkpoint.

## HTTP API

Start a pipeline with:

~~~json
{
  "issue": "auth-api",
  "requirement": "Build auth API",
  "specs": true,
  "provider": "codex",
  "agent_providers": {"reviewer": "claude"}
}
~~~

Send this to POST /pipelines. POST /pipelines/{issue}/approve and the status
endpoint restore provider routing independently of concurrent HTTP requests.

## Operational and security notes

- The explicitly selected Claude runner still uses headless `claude -p`.
- The default Codex runner enables Code Mode / Code Mode Only when supported.
  For incompatible builds use `ASDLC_CODE_MODE=0`. See [Code Mode setup](setup/codex-code-mode.md).
- The Codex adapter uses `codex exec --json --sandbox workspace-write` for
  modifying agents and read-only mode for read-only roles. It passes the
  complete role prompt through stdin and parses JSONL final messages and usage.
- Codex cannot enforce Claude Code's hooks, allowlisted tools or .claude
  permissions. Runtime's own deterministic test gates and contract hash still
  work, but those do **not** replace sandboxing or filesystem access controls.
- The previous held-out acceptance suite is still only instruction-hidden
  within the common workspace; use separate isolated workspaces to enforce
  strict secrecy from an untrusted development agent.
- Codex JSONL usage contains token counts, but no authoritative dollar cost.
  The Model Economics report excludes Codex spend from the USD total.
- The Codex CLI may need dependencies installed beforehand because the
  workspace-write sandbox typically limits network access.
- The same role instructions were authored originally for Claude Code; while
  they are supplied to Codex, behavior can vary. Run a small --specs smoke test
  before relying on a production pipeline.
