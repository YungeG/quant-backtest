---
id: G12M-BHA-00
status: DRAFT_READY
owner: governance single writer
produces:
  - ADR 0009 historical-provider-availability vocabulary
  - explicit upstream-evidence versus causal-qualification status
consumes:
  - ../g12m-binance-historical-availability-repair-v1.md
  - ../../../../adr/0008-source-bounded-decision-grade.md
depends_on:
  contract: []
  evidence: []
  write_conflict: [acceptance-registry]
fan_in: G12M-BHA-02
---

# BHA-00 Freeze historical-availability governance

## Outcome

Freeze the four-time vocabulary and fail-closed authority rule without changing any
accepted artifact or creating a reusable availability framework.

## Inputs

- Parent repair plan.
- ADR 0008.
- Current Acceptance Matrix, G12 README, and `CONTEXT.md`.

## Write set

- `docs/adr/0009-historical-provider-availability-is-distinct-from-local-acquisition.md`
- `CONTEXT.md`
- Minimal status corrections in `docs/implementation/acceptance-matrix.md` and
  `docs/implementation/plans/g12/README.md`

No package, fixture, evidence, or accepted plan file.

## Invariants

- Event, Provider Availability, Acquisition, and Assessment Time are distinct.
- Unknown provider availability remains fail-closed and post-hoc-only.
- Dataset-specific authority is allowed; a global policy/DSL is not.
- ADR 0008 finality limitations remain unchanged.
- Binance v2 `available_time=2026 receipt` is not reinterpreted.
- Governance never mints or upgrades `ResultGrade`.

## Acceptance

- Independent governance review with no blocker/high finding.
- `git diff --check` and Markdown LSP clean for the write set.
- Protected v1/v2 byte/hash fingerprint unchanged.
- `gitleaks detect --no-banner --redact --source .`

## Exclusions

- Binance authority research.
- Availability authority code.
- Source v3, Profile, Bundle, Runtime, Run, or G12M implementation.
- Final PASSED/BLOCKED registry fan-in, owned by BHA-10.

## Dependencies

| Type | Node/artifact | Why |
| --- | --- | --- |
| Contract | Parent repair plan | Supplies frozen terminology and stop conditions |
| Write conflict | BHA-10 registry files | Same files, but topologically serialized |
