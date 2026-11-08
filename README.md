# Agentic SDLC Kit (slim)

**One-command install** for an agent-native Software Development Lifecycle with Claude Code and/or Codex CLI.

7 skills · 10 agents · 3 hooks · 4 rules · 1 command

One pipeline, implemented once: [`runtime/`](runtime/README.md) is a LangGraph state machine that runs role definitions in `.claude/agents/` through either headless `claude -p` or `codex exec`. Skills and `/factory` are thin Claude Code wrappers around the same runtime.

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
  → specification (--specs only; executable business contracts) → acceptance (held-out suite)
  → [human approval]
  → developer → validate: PLAN `Validation:` commands, then approved `Spec:` checks (--specs),
    then `E2E:` against the booted app
  → reviewer ‖ qa (‖ devops with --devops) → fix loop (max 3)
  → held-out acceptance gate, run against the booted app → PRODUCTION_READINESS.md
```

The planner detects the stack and writes `TEST_STRATEGY.md` (type, test layers, how to start the app, healthcheck, e2e command). The runtime boots the app, waits for health, runs the tests, and tears it down, for both the e2e gate and the held-out acceptance gate. UI apps get Playwright, APIs get HTTP-client tests, CLIs get subprocess tests.

## Executable specifications (opt-in)

Run `asdlc-runtime orders "Implement order workflow" --specs` to generate public
Given/When/Then contracts and runnable tests **before** implementation. A
preflight validates complete AC coverage; human approval pins the PRD, spec
file and test sources by SHA-256. Runtime executes these frozen tests during
validation and rejects contract modifications. The independent held-out final
gate remains. See [Specifications mode](docs/specifications-mode.md).

## Providers: Claude, Codex or mixed

The default is **Claude**, so existing commands keep working. For Codex-only
runs, only the Codex CLI needs to be installed and authenticated.

~~~bash
# All generative agents run on Codex, including executable specifications
asdlc-runtime orders "Implement order API" --provider codex --specs

# Hybrid: Claude default, Codex writes code, Claude reviews it
asdlc-runtime orders "Implement order API" --specs \
  --agent-provider developer=codex

# Resume/approve reuse provider choices saved in the LangGraph checkpoint
asdlc-runtime orders --approve
~~~

Choose defaults with ASDLC_PROVIDER=codex, and per-role settings via
ASDLC_PROVIDER_DEVELOPER=codex. Codex models can be set independently using
ASDLC_CODEX_MODEL, ASDLC_CODEX_MODEL_SMART, ASDLC_CODEX_MODEL_WORKER,
or ASDLC_CODEX_MODEL_DEVELOPER. Claude model overrides remain unchanged.
See [Provider setup](docs/providers.md) for the CLI/API and safety details.

## Usage

~~~bash
asdlc-runtime auth-api "Build JWT authentication API"   # runs to the approval gate
asdlc-runtime auth-api --approve                        # implement, test, review
asdlc-runtime auth-api --resume                         # continue after a crash
asdlc-runtime auth-api "..." --devops                   # also Docker/CI artifacts
```

Inside Claude Code: `/factory <issue> "<requirement>"`, `/factory <issue> --approve`, `/sdlc-status`.

## Skills
`/factory` `/sdlc-status` `/sdlc-deploy` `/code-reviewer` `/security-audit` `/test-writer` `/git-commit` `/ponytail`

## Agents (10)
codebase · product · planner · architect · specification (opt-in) · acceptance · developer · reviewer · qa · devops (opt-in)

## Hooks (3)
- Block destructive bash commands (single source of truth)
- Block writes to .env / secrets
- Validate artifact schemas (requires real evidence blocks)

## Requirements
- One or both authenticated CLIs: Claude Code (`claude`) or Codex (`codex`), depending on provider routing
- Python 3.10+ (runtime and settings merge)
- For UI e2e: Node + Playwright (installed by the plan)

## License
MIT
