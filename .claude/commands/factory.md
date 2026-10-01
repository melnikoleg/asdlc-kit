---
name: factory
description: "Run the SDLC pipeline via the asdlc-runtime. Usage: /factory <issue> \"<requirement>\" [--devops] | /factory <issue> --approve|--cancel|--resume"
---

# /factory

Thin wrapper over `asdlc-runtime`. The runtime owns the whole pipeline
(codebase scan, PRD, plan + test strategy, ADR, held-out acceptance suite, approval gate,
implementation, deterministic validation + e2e against the booted app, review + QA, fix loop,
held-out acceptance gate, readiness). Never do phase work yourself.

## Usage
- `/factory <issue> "<requirement>" [--devops]`  start; runs until the approval gate and pauses
- `/factory <issue> --approve`                   approve and implement
- `/factory <issue> --cancel`                    cancel at the gate
- `/factory <issue> --resume`                    continue from the last checkpoint after a crash

## Instructions
1. Run `asdlc-runtime <args>` exactly as given (Bash) and relay its output.
2. At the pause, show the user the plan summary from `docs/<issue>/` (PRD.md, PLAN.md,
   TEST_STRATEGY.md, ADR.md) and ask whether to approve. Do not approve on their behalf.
3. Planning only = start without approving.
