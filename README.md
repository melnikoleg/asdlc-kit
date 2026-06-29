# Agentic SDLC Kit (slim)

**One-command install** for an agent-native Software Development Lifecycle in Claude Code.

11 skills · 7 agents · 3 hooks · 3 rules · 1 command

## Install

```bash
# Current project
bash install.sh

# All projects (global ~/.claude)
bash install.sh --global

# Specific project
bash install.sh --project=/path/to/project
```

## What You Get

### SDLC Skills (7)
| Skill | What it does |
|-------|-------------|
| `/sdlc-orchestrate` | Full pipeline: PRD → plan → code → review |
| `/sdlc-plan` | Planning phase only (PRD + PLAN + ADR) |
| `/sdlc-implement` | Implementation from existing PLAN.md |
| `/sdlc-review` | Parallel review: reviewer + qa |
| `/sdlc-fix` | Fix blocking review issues |
| `/sdlc-deploy` | Optional: Dockerfile + CI/CD + deployment runbook |
| `/sdlc-status` | Status derived from artifacts present |

### Engineering Skills (4)
`/code-reviewer` `/security-audit` `/test-writer` `/git-commit`

### Agents (7)
product · planner · architect · developer · reviewer · qa · devops (opt-in)

### Hooks (3)
- Block destructive bash commands (single source of truth)
- Block writes to .env / secrets
- Validate artifact schemas (requires real evidence blocks)

## Usage

```bash
# Build a REST API from scratch
/factory auth-api "Build JWT authentication API with register, login, refresh endpoints"

# Check what's running
/sdlc-status

# Planning only (review before coding)
/sdlc-plan user-profile "User profile CRUD with avatar upload"

# After you approve the plan
/sdlc-implement user-profile

# Run review
/sdlc-review user-profile
```

## Run the pipeline in a container

Run the full pipeline autonomously on a clean, disposable environment:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
ASDLC_ISSUE=todo-api ASDLC_REQUIREMENT="Build a TODO REST API" \
  docker compose up --build
```

Artifacts land in `./docs/<issue>/`. See `docs/setup/docker.md` for server
mode, manual mode, and the optional Postgres state backend.

## Requirements
- Claude Code (claude.ai/code)
- Python 3 (for settings merge, usually pre-installed)

## License
MIT
