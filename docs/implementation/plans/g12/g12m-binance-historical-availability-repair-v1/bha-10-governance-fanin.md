---
id: G12M-BHA-10
status: READY_H3
owner: governance and main-branch single writer
produces:
  - final accepted or blocked G12M registry state
  - immutable acceptance receipt and artifact links
consumes:
  - G12M-BHA-02 H3
depends_on:
  contract: [G12M-BHA-00]
  evidence: [accepted node receipts]
  write_conflict: [acceptance-registry, g12-readme, main-branch]
fan_in: null
---

# BHA-10 Fan accepted nodes into governance

## Outcome

Integrate the accepted BHA-02 H3 decision and make the Acceptance Matrix and G12
README state unambiguous: upstream v2 evidence remains accepted and historical
causal Runtime qualification is blocked by `H3 — NO_CAUSAL_AUTHORITY`.

## Inputs

- Accepted node commits and receipts.
- Exact BHA-02 H3 blocker-decision hash.
- Protected v1/v2 fingerprints and pre-existing dirty-file fingerprints.

## Fan-in rules

- Cherry-pick only immutable accepted commits; one writer owns main.
- Resolve no user-owned dirty file without explicit ownership handoff.
- Record H3 as the permanent causal blocker and retain 2024 v2 as post-hoc-only.
- Link no prospective plan and reuse no v2 artifact as causal input.
- Remove stale Binance `nominal ready` wording.
- Keep legal, live, deployment, permanent-finality, and provider-global-completeness
  claims false or explicitly limited.

## Write set

- `docs/implementation/acceptance-matrix.md`
- `docs/implementation/plans/g12/README.md`
- Minimal links/status in the parent G12M qualification plan
- Acceptance receipts under this execution directory

No executable package or accepted source/fixture changes.

## Acceptance

- Topological commit and artifact-hash audit.
- Protected v1/v2 and user-dirty fingerprints unchanged.
- Focused/adjacent suites for every integrated executable node.
- Full architecture and repository suites when H1 executable code is integrated.
- Ruff, Markdown/Python LSP, `git diff --check`, gitleaks, link/status consistency.
- Independent final review with no blocker/high finding.
- Commit but do not push without authorization.

## Exclusions

- New implementation or research.
- Retrofitting H3 into H1.
- Live/deployment authorization.
