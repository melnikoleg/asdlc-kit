---
name: architect-adr
description: Write an Architecture Decision Record (ADR) for a significant technical decision. Captures context, decision, alternatives considered with trade-offs, and consequences. Use when making non-obvious choices about data model, auth strategy, external dependencies, scaling approach, or tech stack. Invoke as: /architect-adr "<decision title>"
---

# Architect ADR

Document non-obvious architectural decisions with full context and trade-offs.

## When to Write an ADR
Write for: data model changes, auth/session strategy, external dependency selection,
caching strategy, database choice, API design pattern, scaling approach.

Skip for: standard patterns, trivial library choices, implementation details.

## ADR Structure

```markdown
# ADR-NNN: {Title}

## Status
Proposed | Accepted | Deprecated | Superseded by ADR-NNN

## Context
What problem are we solving? What constraints exist?
What is the deadline or business driver?

## Decision
What we decided. One clear sentence, then details.

## Alternatives Considered
| Option | Pros | Cons | Why Rejected |
|--------|------|------|--------------|
| Option A | ... | ... | ... |
| Option B | ... | ... | ... |
| Chosen | ... | ... | — Selected |

## Consequences
### Positive
- ...
### Negative (known trade-offs)
- ...
### Constraints for Implementation (BINDING)
- All code using this decision MUST follow these constraints
- ...

## References
- Links to docs, RFCs, prior art
```

## Rules
- Be specific about WHY alternatives were rejected (not just "worse")
- Constraints section is BINDING — developer-agent must follow them
- Reference real docs, not vague "best practices"
- Number sequentially: ADR-001, ADR-002, etc.

## Related Skills
- /sdlc-plan — planning phase that produces ADRs
- /api-design — API-specific design decisions
