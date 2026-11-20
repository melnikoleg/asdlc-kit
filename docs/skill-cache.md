# Execution-grounded skill capsules (experimental)

This opt-in fast path is inspired by **SkillCache** from Ni et al.,
[arXiv:2611.10022](https://arxiv.org/abs/2611.10022). The paper observes one
successful invocation, compiles repeatable operations into a capsule, qualifies
the program by replay, and falls back to the source skill when guards fail.

## What asdlc-kit implements

The first capsule is deliberately narrow: **codebase-agent report reuse**.
This is *not* a full general-purpose SkillCache implementation, nor a compiler
of arbitrary Claude/Codex tool-call trajectories. It is a guarded deterministic
program that replays one successful codebase report into another issue.

1. **Observe:** the original codebase agent must finish with APPROVED and
   create a real `docs/{issue}/CODEBASE_CONTEXT.md` file.
2. **Compile:** store a metadata-only capsule with SHA-256 checksums for the
   exact requirement, source report and source-workspace snapshot. The
   deterministic program binds a new issue-local docs path.
3. **Qualify:** execute the replay program in a temporary directory and
   byte-compare with the observed report; reject unsuccessful capsules.
4. **Warm reuse:** only when the exact requirement and scanned workspace
   (including agent instructions and rules) still match, replay the report
   without invoking codebase-agent.
5. **Deopt:** stale/missing/corrupt capsule, changed source document, changed
   agent instructions, larger-than-supported workspace, or failed replay
   automatically invokes the original codebase-agent.

Raw tool traces, arbitrary shell commands, report content and request text are
**not** stored in the capsule. Metadata is stored under
`.asdlc/skill-cache/`; the original report remains in `docs/{issue}/`.

## Usage

~~~bash
# First invocation: capture a successful codebase scan and qualify it
asdlc-runtime first-a "Review payment handling" --skill-cache --specs

# Identical request, unchanged codebase, fresh issue:
# codebase scan may be replayed; every other agent still runs normally
asdlc-runtime first-b "Review payment handling" --skill-cache --specs

# Later approval always continues the regular deterministic LangGraph
asdlc-runtime first-b --approve
~~~

You can use `--provider codex`, `--provider claude`, or hybrid routing
together with `--skill-cache`. The cache program itself is model-independent.

The server's `POST /pipelines` also accepts `"skill_cache": true`.
Check `docs/{issue}/STATE.json` (`skill_cache_status`) or the readiness report.
Statuses: `recorded`, `hit`, `cold`, `greenfield`.

## Safety and limitations

- **No gate bypass:** product, planner, specifications, approval, validation,
  reviewer/QA and held-out acceptance all execute as before.
- **Exact match:** semantically similar, differently worded requests are cache
  misses. Even a successful earlier report is invalidated by source changes.
- **No benchmarks claimed:** the paper's 74–81% warm token reductions are from
  SkillsBench on Claude Code, **not measured in asdlc-kit**. This limited
  implementation saves at most one codebase-agent invocation per warm hit.
- **No shell replay:** the capsule cannot execute generated shell scripts.
- **No content duplication in cache:** capsules contain hashes and a reference
  to the original report. Removing that report invalidates the capsule.
- **Security boundary:** stored SHA-256 hashes check accidental/stale changes;
  they are not digital signatures or a defence against a malicious process
  with write access to the entire workspace. Treat workspace access carefully.
- **Filesystem scan limits:** a large, symlinked or unreadable workspace skips
  caching and runs the original agent.

This is a useful first adapter for the paper's observe–compile–qualify–replay–
deopt lifecycle. General trace-level program fusion and model handoffs require
isolated trace collection, sandboxed execution, and explicit verification.
