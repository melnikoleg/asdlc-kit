# Executable Specifications mode

Enable with `asdlc-runtime orders "Implement order workflow" --specs` or
`/factory orders "Implement order workflow" --specs`. Disabled by default
for backwards compatibility. The server accepts `"specs": true` on `POST /pipelines`.

## Pipeline

`product -> planner -> architect -> specification -> spec_preflight -> acceptance
-> approval -> developer -> validate (PLAN, specs, E2E) -> reviewer/qa
-> held-out acceptance -> readiness`

`specification` writes public, executable contract tests **before** implementation.
`spec_preflight` rejects missing coverage or broken artifacts; human approval
pins a SHA-256 over `PRD.md`, `SPECIFICATIONS.md` and every regular file in
`docs/{issue}/specs/`. `validate` runs those pre-approved tests and loops on
ordinary failures. Modifying the contract after approval fails closed and
escalates rather than regenerating tests to match the implementation.

## Format

```markdown
## AC-1 — Paid order can be shipped
Given: OrderCreated and PaymentConfirmed
When: ShipOrder is submitted
Then: exactly one OrderShipped is produced
Spec: python -m pytest docs/orders/specs/test_ship_paid.py -q
```

The `Spec:` command must reference a real test source under the per-issue
`specs/` directory. Each PRD `AC-N` must have exactly one corresponding
section, with nonempty Given/When/Then fields and one or more unique Spec
commands. The runtime executes the commands; documentation alone never counts
as a passing spec. Use ordinary test frameworks; no YAML or Gherkin runner
dependency is required. HTTP/UI test commands run against the app started
through TEST_STRATEGY.md. Event Sourcing is optional.

## Trust boundaries

- Keep specifications readable to developer-agent: they define expected behavior.
- Held-out `ACCEPTANCE.md` remains an independent final verification layer.
- Existing held-out suite isolation is instruction-based, not a filesystem sandbox.
- Approved contract hash protects spec files from accidental or opportunistic
  edits during development. It does not protect external dependencies or
  every possible test helper; consider process isolation for adversarial agents.
- For changed requirements, start a fresh pipeline and approve new specs.

## Diagnostics

- `SPEC_TAMPERED`: the approved contract was changed or invalidated.
- `SPEC_INVALID`: tests could not be run (for example, app startup failed).
- A regular failed `Spec AC-N: ...` check goes through the normal fix-loop.
- A missing AC, missing test file or malformed spec escalates before approval.
