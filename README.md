# Agentic SDLC Kit for Claude Code

**One-command install for a production-grade, agent-driven SDLC in Claude Code.**

Implements the full [ASDLC.io](https://asdlc.io) methodology as a working Claude Code plugin:
8 specialized agents, 3 slash commands, 5 lifecycle hooks, 2 skills, 2 rule files.

## Install

```bash
# Clone and install into current project
git clone https://github.com/melnikoleg/asdlc-kit/

bash asdlc-kit/install.sh

# Install globally (available in all projects)
bash asdlc-kit/install.sh --global

# Install into specific project
bash asdlc-kit/install.sh --project /path/to/your/project
```

That's it. Open Claude Code in your project and run `/factory`.

## Quick Start

```bash
# Full pipeline: requirements → architecture → code → tests → deploy
/factory my-feature "Build a REST API for user authentication with JWT"

# Resume after interruption
/factory my-feature --resume

# Check all pipeline statuses
/factory-status

# See artifacts for a specific issue
/factory-artifacts my-feature
```

## What Gets Installed

| Component | Count | Purpose |
|---|---|---|
| Agents | 8 | Orchestrator, Product, Planner, Architect, Developer, Reviewer, QA, DevOps |
| Commands | 3 | /factory, /factory-status, /factory-artifacts |
| Hooks | 5 | Block destructive ops, validate paths, schema checks, pipeline guard, audit log |
| Skills | 2 | /sdlc-plan (planning only), /sdlc-review (parallel review only) |
| Rules | 2 | Artifact contracts, security rules |

## Pipeline Flow

```
/factory <issue> "<description>"
       |
       ├─ product-agent ────────────────► PRD.md
       ├─ planner-agent ────────────────► PLAN.md
       ├─ architect-agent ──────────────► ADR.md
       ├─ [HUMAN APPROVAL GATE] ─────────────────
       ├─ developer-agent ──────────────► IMPLEMENTATION.md + code
       ├─ reviewer-agent ─┐
       ├─ qa-agent ────────┼─ parallel ─► REVIEW.md, QA.md, DEPLOY.md
       ├─ devops-agent ───┘
       ├─ [FIX LOOP if NEEDS_FIX, max 3 iterations]
       └─ orchestrator ─────────────────► PRODUCTION_READINESS.md
```

## Artifact Contracts

Every agent **must** return:
```json
{"status": "APPROVED|NEEDS_FIX|FAILED", "artifacts": ["path/to/file"], "issues": []}
```

Artifacts live in `docs/{issue-name}/`:
`PRD.md` · `PLAN.md` · `ADR.md` · `IMPLEMENTATION.md` · `REVIEW.md` · `QA.md` · `DEPLOY.md` · `PRODUCTION_READINESS.md` · `STATE.json`

## Guardrails (always active)

- ❌ No writes to `.env`, `*.pem`, `id_rsa`, credentials files
- ❌ No `git push`, `rm -rf /`, `git reset --hard`
- ✅ Bash scoped to test/build/inspect commands only
- ✅ Schema validation on every artifact write
- ✅ Incomplete pipeline warning on Stop event

## Sources & Credits

This kit is assembled from:
- **ASDLC.io** methodology — spec-first, deterministic protocols, verification architecture
- **DenizOkcu/claude-code-ai-development-workflow** — SDLC agent patterns, STATE.json design, parallel review
- **rohitg00/awesome-claude-code-toolkit** — hook patterns, settings.json structure
- **VoltAgent/awesome-claude-code-subagents** — agent tool assignment strategy
- **Anthropic Claude Code docs** — hooks reference, subagents, skills, slash commands

## License

MIT
