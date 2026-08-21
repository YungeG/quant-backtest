---
id: G12M-BHA-02
status: DECIDED_H3
owner: Builder authority single writer
produces:
  - one H3 NO_CAUSAL_AUTHORITY decision
consumes:
  - G12M-BHA-00
  - G12M-BHA-01A
  - G12M-BHA-01B
depends_on:
  contract: [G12M-BHA-00]
  evidence: [G12M-BHA-01A, G12M-BHA-01B]
  write_conflict: []
fan_in: G12M-BHA-10
---

# BHA-02 Decide and freeze provider availability authority

## Outcome

The sole decision is **`H3 — NO_CAUSAL_AUTHORITY`**. Publish only the blocker
decision, terminate BHA-03 through BHA-09 as `TERMINATED_H3`, and route only to
BHA-10. Emit no availability authority, module, placeholder, tests, or executable
code.

## Frozen inputs

- Accepted BHA-00 governance tip
  `d9ec8631385247249fcd91bd814c1342948c53b5`.
- Accepted BHA-01A settlement research tip
  `7a808d3b7b7a58a354212e0da0fc67c3dcefd85c`.
- Accepted BHA-01B revision research tip
  `366575914cd4066ad6cfa593b8df219df7021c54`.
- Exact accepted v2 observation report identity.

## H3 basis

- ADR 0009 requires the earliest defensible Provider Availability Time for the exact
  event revision. A prospective REST receipt proves local receipt and may bound
  participant usability, but cannot prove that earliest time exactly equals
  `fundingTime`.
- `MarketEvent` requires causal availability and G10E fixes publication/settlement at
  the exact `fundingTime`; neither a later receipt nor an at-or-before receipt proves
  the required exact equality.
- Funding Rate History provides no revision/as-of selector or complete correction
  lineage. Polling observes samples and cannot prove that every settlement-visible
  revision was retained.

The proposed prospective capture route is rejected, not planned. It cannot close the
exact publication-time or revision-lineage requirements.

## Write set

- One provider-specific H3 decision report.
- One canonical H3 decision JSON and regenerated SHA-256 manifest.
- This BHA-02 subplan and the execution DAG status update.

No authority/module/code, source v3, Profile input, Bundle, adapter, Run, assessment,
grade, prospective plan, accepted v1/v2 artifact/package change, Acceptance Matrix
change, or G12 README change.

## Acceptance

- Canonical JSON parses and round-trips unchanged.
- Decision/report/subplan/DAG links and hashes agree.
- BHA-03 through BHA-09 are `TERMINATED_H3`; BHA-10 is the only Ready route.
- Protected v1/v2 bytes, package bytes, Acceptance Matrix, and G12 README are
  unchanged from `4352919`.
- Markdown/LSP, `git diff --check`, link checks, gitleaks, and independent diff review
  are clean.
