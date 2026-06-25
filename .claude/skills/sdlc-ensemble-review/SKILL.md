---
name: sdlc-ensemble-review
description: Kaggle-style ensemble of the review phase. Runs reviewer-agent k times in parallel (optionally across different models for decorrelation), each writing its own REVIEW.run{n}.md, then invokes ensemble-aggregator to majority-vote the verdict and frequency-weight blocking issues into a single REVIEW.md. Use instead of /sdlc-review when review quality matters more than cost. Invoke as: /sdlc-ensemble-review <issue-name> [k]
---

# SDLC Ensemble Review

Variance-reduction for the review phase. A single reviewer run has high variance
(missed cases, occasional hallucinated blockers). Running k independent reviewers
and aggregating gives the Kaggle ensemble effect: decorrelated errors cancel,
consensus findings rise, outliers are demoted.

## Arguments
- `<issue-name>` — required.
- `[k]` — number of base reviewer runs. Default 3. Use odd k to avoid ties.

## Pre-flight Checks
1. `docs/{issue}/IMPLEMENTATION.md` must exist.
2. `docs/{issue}/PRD.md` must exist.

## Steps
1. Update STATE.json: phase="review", add `ensemble: {"k": k, "strategy": "majority"}`.
2. **Base layer — launch k `reviewer-agent` instances IN PARALLEL** (all in one
   message so they run concurrently). For run n = 1..k, instruct the instance to
   write its artifact to `docs/{issue}/REVIEW.run{n}.md` (NOT to REVIEW.md).
   - For decorrelation, vary the base models across runs when available
     (e.g. run1=opus, run2=sonnet, run3=haiku). Diversity is what makes the
     ensemble beat any single reviewer — identical runs only reduce sampling noise.
3. Wait for all k runs to finish. Each produced a `REVIEW.run{n}.md`.
4. **Stacking layer — invoke `ensemble-aggregator`.** It reads all
   `REVIEW.run*.md`, majority-votes the verdict, dedups + frequency-weights
   blocking issues, and writes the consolidated `docs/{issue}/REVIEW.md`.
5. Display:
   - APPROVED → "✅ Ensemble APPROVED — {a}/{k} runs agreed".
   - NEEDS_FIX → list CONSENSUS blocking issues with their `agreement` (M/k),
     then: "Run /sdlc-fix {issue} to address these N consensus issues".
6. (Optional) delete `REVIEW.run*.md` once REVIEW.md is written, or keep them as
   an audit trail of the jury.

## Artifact Ownership (ensemble mode override)
- `REVIEW.run{n}.md` — intermediate, owned by reviewer-agent instance n.
- `REVIEW.md` — owned by ensemble-aggregator in this mode (the consolidated output).
This is the only place where REVIEW.md is written by the aggregator instead of a
single reviewer; the consolidated file still satisfies the standard REVIEW.md
contract (Verdict line + Blocking Issues), so /sdlc-fix and the schema hook work unchanged.

## When to use this vs /sdlc-review
- Use ensemble when: high-risk change, security-sensitive code, low confidence,
  or a flaky single-reviewer verdict you want to stabilize.
- Use plain /sdlc-review when: cost/latency matter and the change is low-risk.
  (k=1 ensemble == /sdlc-review.)

## Anti-Patterns
- NEVER run the k reviewers sequentially — they MUST be parallel.
- NEVER let a MINORITY (sub-majority) finding block the merge.
- NEVER have a base reviewer write REVIEW.md directly — only run files.
- NEVER use even k without expecting tie-break-to-NEEDS_FIX behavior.

## Related Skills
- /sdlc-review — single-reviewer (cheaper) version.
- /sdlc-fix — fix consensus blocking issues.
- /sdlc-orchestrate — full pipeline (can call ensemble review at the review step).
