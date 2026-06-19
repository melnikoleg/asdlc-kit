# Agentic SDLC Kit v2

**One-command install** for a complete agent-native Software Development Lifecycle in Claude Code.

19 skills · 8 agents · 5 hooks · 3 rules · 2 commands

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

### SDLC Skills (8)
| Skill | What it does |
|-------|-------------|
| `/sdlc-orchestrate` | Full pipeline: PRD → plan → code → review → deploy |
| `/sdlc-plan` | Planning phase only (PRD + PLAN + ADR) |
| `/sdlc-implement` | Implementation from existing PLAN.md |
| `/sdlc-review` | Parallel review: reviewer + qa + devops |
| `/sdlc-qa` | Tests mapped to PRD acceptance criteria |
| `/sdlc-deploy` | Dockerfile + CI/CD + deployment runbook |
| `/sdlc-status` | Pipeline status dashboard |
| `/sdlc-fix` | Fix blocking review issues |

### Engineering Skills (11)
`/code-reviewer` `/security-audit` `/test-writer` `/architect-adr`
`/git-commit` `/prd-writer` `/api-design` `/docker-setup`
`/ci-setup` `/debug-agent` `/refactor` `/dependency-audit`

### Agents (8)
orchestrator · product · planner · architect · developer · reviewer · qa · devops

### Hooks (5)
- Block destructive bash commands
- Block writes to .env / secrets
- Validate artifact schemas
- Remind about paused pipelines
- Audit log for subagent events

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

## Requirements
- Claude Code (claude.ai/code)
- Python 3 (for settings merge, usually pre-installed)

## License
MIT
