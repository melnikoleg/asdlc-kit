---
name: prd-writer
description: Write a structured Product Requirements Document (PRD) from a rough feature description. Produces a PRD with binary-testable acceptance criteria, user stories, success metrics, and out-of-scope items. Use when formalizing requirements before planning. Invoke as: /prd-writer "<feature description>"
---

# PRD Writer

Convert rough requirements into a structured PRD with testable acceptance criteria.

## Output: docs/{feature-slug}/PRD.md

### Required Sections

**Problem Statement**
- What user problem are we solving?
- Who is affected? (persona)
- What is the current workaround?

**User Stories**
```
As a {persona}, I want to {action} so that {outcome}
```
3-5 stories covering the main flows.

**Acceptance Criteria**
Each AC must be binary (PASS/FAIL, not "should feel good"):
```
AC-1: Given [context], when [action], then [exact measurable outcome]
AC-2: Given [context], when [action], then [exact measurable outcome]
```
Examples of GOOD ACs:
- "POST /users returns 201 with {id, email} when valid email and password >= 8 chars"
- "Login rate-limited to 5 attempts per 15 minutes per IP"

Examples of BAD ACs (vague, unverifiable):
- "The API should be fast" → REJECT
- "Users should be happy" → REJECT

**Out of Scope**
Explicit list of what is NOT included in this version.

**Constraints & Assumptions**
Mark assumptions as [ASSUMPTION: ...] so they can be validated.

**Success Metrics**
Measurable KPIs: adoption rate, error rate, latency percentile.

## Rules
- No vague language: "fast" → "p95 < 200ms", "secure" → specific OWASP controls
- Every AC is automatable as a test
- [ASSUMPTION: ...] tags surface ambiguity explicitly

## Related Skills
- /sdlc-plan — uses PRD.md as input
- /architect-adr — architectural decisions after PRD
