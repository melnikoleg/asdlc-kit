# ASDLC Kit — Codex instructions

This project uses an agent-native SDLC orchestrator. For full SDLC tasks, use
the installed `asdlc-runtime` CLI instead of manually improvising its phases.

- Start: `asdlc-runtime issue "Requirement" --provider codex --specs`
- Hybrid example: `asdlc-runtime issue "Requirement" --agent-provider developer=codex`
- After the planning phase, read the generated PRD.md, PLAN.md and (when enabled)
  SPECIFICATIONS.md, then ask the human for explicit approval.
- Only after the human approves, run `asdlc-runtime issue --approve`.
- Resume interrupted runs using `asdlc-runtime issue --resume`.
- Do not edit approved specification tests to make an implementation pass.
- Do not inspect held-out ACCEPTANCE.md while acting as developer.

The pipeline is the authority for approval gates, validation and acceptance.
Claude Code hooks are not executed by Codex; follow project security policy and
use the Codex workspace sandbox. Never bypass sandbox protections to fix tests.
