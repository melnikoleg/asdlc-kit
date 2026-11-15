# Codex Code Mode — primary execution backend

This kit uses the experimental Codex JavaScript Code Mode by default for all
LangGraph agent nodes. Its project settings live in `.codex/config.toml`,
and `runtime/codex_runner.py` forces the same Code Mode flags for headless
`codex exec` sessions, including workspaces where project config is untrusted.

## Prerequisites

1. Install a Codex CLI build supporting the `code_mode` and
   `code_mode_only` flags. Authenticate using the standard `codex` login.
2. The standalone `codex-code-mode-host` must be installed and functional;
   this is an experimental capability and not all public builds include it.
3. Python 3.10+ and this kit's Python runtime dependencies.

Check the local build:

```bash
codex --version
codex features list
command -v codex-code-mode-host
python -m pytest runtime/tests
```

Start the default Codex pipeline:

```bash
asdlc-runtime auth-api "Build an authentication API"
asdlc-runtime auth-api --approve
```

Inside a trusted Codex project, launching `codex` normally also uses the
project default Code Mode. Codex only loads project configuration for trusted
workspaces. The headless runtime passes explicit flags independently.

## Compatibility switches

If the binary does not support Code Mode or its host is missing, run Codex
without Code Mode until a compatible version is installed:

```bash
ASDLC_CODE_MODE=0 asdlc-runtime auth-api "Build an authentication API"
```

To retain the original Claude backend:

```bash
ASDLC_AGENT_BACKEND=claude asdlc-runtime auth-api "Build an authentication API"
```

To disable experimental Code Mode in an interactive Codex session, override
the project config explicitly:

```bash
codex -c features.code_mode=false -c features.code_mode_only=false
```

Codex uses its default model unless a model override is explicitly set through
`ASDLC_MODEL_<NODE>`, `ASDLC_MODEL_SMART` or `ASDLC_MODEL_WORKER`. The
Claude models in agent Markdown frontmatter are intentionally not passed to
Codex.

## Safety and correctness

- Code Mode batches tool calls; it does not remove model reasoning or make all
  operations concurrent. Parallelize independent reads, not dependent writes.
- The runtime still enforces approval interrupts, test/validation commands,
  held-out acceptance checks and a finite fix loop.
- `codex exec` runs within the `workspace-write` sandbox with non-interactive
  approval policy. No dangerous full-access flags are used.
- `.claude/hooks/` are Claude-specific. They do **not** enforce shell or file
  restrictions on Codex. Deploy a compatible Codex sandbox/host policy and
  check changes before approval.
- Codex JSONL reports input/output tokens, but generally does not supply a
  monetary cost figure; cost remains 0 (unknown) in the existing dashboard
  rather than being estimated.
- Experimental features may not run on the currently installed Codex build.
  The runtime reports failure instead of silently switching agents.

Reference: https://github.com/openai/codex
