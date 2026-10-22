# Agentic SDLC Kit (slim)

**One-command install** for an agent-native Software Development Lifecycle in Claude Code.

7 skills · 9 agents · 3 hooks · 4 rules · 1 command

One pipeline, implemented once: [`runtime/`](runtime/README.md) is a LangGraph state machine that runs the agents in `.claude/agents/` through headless `claude -p`. Skills and `/factory` are thin wrappers around it.

## Install

```bash
# Current project (also creates .asdlc-venv with asdlc-runtime and asdlc-e2e)
bash install.sh

# All projects (global ~/.claude, no runtime)
bash install.sh --global

# Specific project
bash install.sh --project=/path/to/project
```

## Pipeline

```
codebase-agent (brownfield only) → product → planner (PLAN.md + TEST_STRATEGY.md) → architect
  → acceptance (held-out suite) → [human approval]
  → developer → validate: PLAN `Validation:` commands, then `E2E:` against the booted app
  → reviewer ‖ qa (‖ devops with --devops) → fix loop (max 3)
  → held-out acceptance gate, run against the booted app → PRODUCTION_READINESS.md
```

The planner detects the stack and writes `TEST_STRATEGY.md` (type, test layers, how to start the app, healthcheck, e2e command). The runtime boots the app, waits for health, runs the tests, and tears it down, for both the e2e gate and the held-out acceptance gate. UI apps get Playwright, APIs get HTTP-client tests, CLIs get subprocess tests.

## Usage

```bash
asdlc-runtime auth-api "Build JWT authentication API"   # runs to the approval gate
asdlc-runtime auth-api --approve                        # implement, test, review
asdlc-runtime auth-api --resume                         # continue after a crash
asdlc-runtime auth-api "..." --devops                   # also Docker/CI artifacts
```

Inside Claude Code: `/factory <issue> "<requirement>"`, `/factory <issue> --approve`, `/sdlc-status`.

## Skills
`/factory` `/sdlc-status` `/sdlc-deploy` `/code-reviewer` `/security-audit` `/test-writer` `/git-commit` `/ponytail`

## Agents (9)
codebase · product · planner · architect · acceptance · developer · reviewer · qa · devops (opt-in)

## Hooks (3)
- Block destructive bash commands (single source of truth)
- Block writes to .env / secrets
- Validate artifact schemas (requires real evidence blocks)

## Requirements
- Claude Code (`claude` on PATH, logged in)
- Python 3.10+ (runtime and settings merge)
- For UI e2e: Node + Playwright (installed by the plan)

## License
MIT
