# RTK — Token Compression for AI Coding

RTK is a transparent CLI proxy that compresses command output before it reaches the LLM context. It intercepts commands like `git status`, `pytest`, `ls`, and 100+ others, stripping noise and deduplicating output. Typical savings: 60–90% fewer tokens per tool call.

**Why it matters for asdlc-kit:** agents in the pipeline run many shell commands (validation, tests, git ops). RTK shrinks every one of those outputs, reducing cost and keeping context windows free for actual reasoning.

## Install

```bash
# macOS
brew install rtk

# Linux / macOS (curl)
curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
```

## Activate for Claude Code

```bash
rtk init -g
```

Then restart Claude Code. RTK installs a shell hook that rewrites commands transparently — you don't need to prefix anything with `rtk` manually.

## What gets changed

- Binary placed in your PATH (`~/.local/bin/rtk` or Homebrew prefix)
- Shell hook added to your rc file (`~/.bashrc` / `~/.zshrc`)
- Config written to `~/.config/rtk/`

Nothing is added to this repository — RTK is a machine-level tool, not a per-project one.

## Verify it's working

```bash
rtk git status   # should show compressed output
rtk --version
```

## Reference

- Repo: https://github.com/rtk-ai/rtk
- Supports: Claude Code, Cursor, Copilot, Gemini CLI, and 10+ others
- Overhead: <10ms per command
