# SkillCache: trace-grounded compilation, qualification and warm execution

Paper: [Ni et al., *How Much Skill Orchestration Can LLM Agents Compile Away?*
(arXiv:2611.10022)](https://arxiv.org/abs/2611.10022).

This experimental subsystem implements the paper's observe–compile–qualify–
execute/deoptimize lifecycle **inside asdlc-kit**, with both Claude and Codex.
It extends the initial narrow `codebase-agent` report cache and adds a generic
capsule engine for arbitrary skills. It is not the authors' original code and
is **not benchmark-equivalent** to their research prototype.

## Subsystems

| Stage | Implementation |
|---|---|
| Observe | Opt-in Codex `exec --json` and Claude `stream-json` tool events; sanitized, bounded observations |
| Compile | Separate read-only Codex/Claude compiler in a fresh directory |
| Bindings | Named live inputs, model decisions, and outputs from prior programs |
| Programs | Language-agnostic source packages, argv, syntax/build checks, JSON result contract |
| Steps | Interleave deterministic programs with natural-language judgments |
| Qualification | Schema/dataflow -> program checks -> sandboxed replay from observed bindings |
| Repair | Up to 3 hybrid candidates, then textual capsule, then uncached skill |
| Storage | Example-free, content-addressed capsules with source trace/request/workspace SHA-256 |
| Replay | `asdlc-skillcache start` / `continue` persist session position and bindings |
| Deoptimization | Twice-failed program or one timeout -> `program_failed` handback to the model |
| Guards | Request, role and workspace/instructions fingerprint; missing evidence -> cold execution |

The compiler does **not** use human acceptance tests, verification answers or
other unavailable evaluation data. The runner still executes the normal SDLC
human approval, specs, validation, reviewer/QA and held-out acceptance gates.

## Prerequisites

- Python 3.10+, asdlc-runtime installed.
- Codex CLI or Claude Code CLI, authenticated.
- **Docker** for executing untrusted compiled programs. Docker must already
  have the required image locally (default `python:3.11-slim`). The executor
  disables networking, runs with dropped capabilities, and mounts the
  workspace read-only. Outputs go to a session-specific staging directory.
- No Docker: the original model/skill continues; no untrusted local program
  execution takes place. The original narrow report-only cache still works.

`local-test` in the Python API exists only for trusted unit test fixtures.
The production CLI does **not** expose this unsafe runner.

## Normal pipeline use

~~~bash
# Full opt-in mode: capture real tool events and compile after completed runs
asdlc-runtime orders "Implement order workflow" --specs --skill-cache

# Works with either provider
asdlc-runtime orders "Implement order workflow" --provider claude --skill-cache
asdlc-runtime orders "Implement order workflow" --provider codex --skill-cache

# Optional similar-task transfer: the model decides applicability
asdlc-runtime orders-v2 "Review order edge cases" --provider codex \
  --skill-cache --skill-cache-match role

# Continue with saved flags/providers
asdlc-runtime orders --approve
~~~

The kit still uses the original agent to make/verdict its decisions. A warm
matching capsule is supplied as a machine-executable optional fast path in the
agent's prompt. Matching defaults to an exact request; `--skill-cache-match role`
may offer a capsule for a different request of the same agent role in the same
unchanged workspace, but **never** automatically declares it applicable. The executing agent judges applicability and can invoke the
executor using its ordinary shell tool. Missing Docker, mismatched request,
unavailable bindings and failed programs return control to the original agent.

Automatic trace compilation currently targets codebase, product, planner,
architect, developer, specification and devops roles. Independent
acceptance/reviewer/QA agents are intentionally excluded from this optimization.
Codebase report reuse remains a separate safe direct fast path.

Observations live under `.asdlc/skill-cache/observations/`; compiled capsules
under `.asdlc/skill-cache/compiled/`; short-lived execution sessions under
`.asdlc/skill-cache/sessions/`. Avoid publishing these directories to Git.

## Manual compilation and replay

You may also compile any completed invocation independently of LangGraph.

~~~bash
# A provider-neutral JSON observation (see examples below) and a SKILL.md file
asdlc-skillcache compile --role codebase --request "Inspect module" \
  --trace observed.json --skill .claude/agents/codebase-agent.md \
  --provider codex --workspace .

asdlc-skillcache lookup --role codebase --request "Inspect module" --workspace .
asdlc-skillcache inspect --capsule .asdlc/skill-cache/compiled/<hash>.json

asdlc-skillcache qualify --capsule .asdlc/skill-cache/compiled/<hash>.json \
  --workspace . --examples /path/to/observed-bindings.json

# A new session, with initial known bindings
asdlc-skillcache start --capsule .asdlc/skill-cache/compiled/<hash>.json \
  --session trial-1 --bindings '{"value": 5}' --workspace .

# If executor reports needs_bindings/your_steps:
asdlc-skillcache continue --capsule .asdlc/skill-cache/compiled/<hash>.json \
  --session trial-1 --bindings '{"decision": "approved"}' --workspace .
~~~

The `start` and `continue` commands return exactly one machine-readable JSON
report with `status`:

- `needs_bindings`: supply the named live values in `required_bindings`.
- `your_steps`: do the listed natural-language steps (or recover the single
  failed program); supply requested bindings, then continue.
- `complete`: all programs and verification steps completed.
- `fallback`: unusable capsule or sandbox; run the original source skill.

Programs execute as direct argv (never interpolated shell command strings).
Each reads `SKILLCACHE_INPUT` and emits one JSON object:

~~~json
{"status": "complete", "result": {"output_binding": 42}}
~~~

Programs can write generated files under `SKILLCACHE_OUTPUT`. The resulting
`staging_directory` is included in executor reports; the agent must inspect
and explicitly promote validated artifacts to the intended destination. The
runtime never silently overwrites production files from an LLM-generated
capsule. Syntax/build checks execute inside the same sandbox.

## Qualification and security

A capsule is admitted only after schema/dataflow checks, program build checks,
and an end-to-end replay in a **fresh copied workspace** with qualification-only
observed bindings. Those observed values are removed before publication.
Programs are retried once on ordinary failure; a timeout deoptimizes
immediately. Program failures return only their diagnostics and instruction
to the model so that later steps may remain compiled.

The trace parser redacts known credential formats and ignores dangerous
command patterns. This is **best effort**, not proof that a trace contains no
secrets. Do not enable capture on untrusted repositories or environments with
sensitive data. The compiler is separate and read-only but still receives the
selected role instructions and redacted evidence. Treat all compiled sources
as untrusted; Docker network isolation and filesystem controls are mandatory.

Qualification and replay mount a filtered, read-only copy of the workspace.
Each start and continuation verifies the source fingerprint. The copy excludes
held-out acceptance, runtime state, checkpoints and known private filenames.
Exact pipeline matches also include hashes of the role’s public input artifacts.
For a published hybrid capsule, pass observed bindings as a separate JSON object
to `qualify --examples` (for example, `{"value": 5}`). Store this fixture
outside the source workspace. To retry an interrupted program, run `continue`
with empty bindings. Each attempt starts from the last committed staging output.
The agent must explicitly promote generated files to the live workspace.
The codebase-report cache has additional exact-match constraints.

This version does **not** claim the paper's 74–81% token savings. Compile/replay
latency and the quality of model-generated capsules need to be measured on
representative real workspaces. Tests use trusted synthetic programs; a live
authenticated Claude+Codex benchmark is still required.

## Initial report-only cache

The original `codebase-agent` capsule remains supported. It records a
successful `CODEBASE_CONTEXT.md`, qualifies a deterministic copy, and
replays only with the same request and repository fingerprint. Its status is
visible in `docs/{issue}/STATE.json` and the readiness report. In contrast,
general hybrid capsules run through the model/executor interface above.

## Further reading

The original paper's design and validation protocol are in Sections 4–6;
Appendix B gives the compiler prompts and representative hybrid capsules.
