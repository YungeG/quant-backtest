---
id: G12M-BHA-01B
status: DRAFT_READY
owner: Binance revision authority researcher
produces:
  - target-effective revision/correction limitation research note
  - retained first-party source bytes and hashes
consumes:
  - ../g12m-binance-historical-availability-repair-v1.md
depends_on:
  contract: []
  evidence: [first-party Binance USD-M materials]
  write_conflict: []
fan_in: G12M-BHA-02
---

# BHA-01B Establish revision and correction authority

## Outcome

Determine what can be claimed about the revision vintage returned for settled 2024
funding rows and whether later corrections can alter the currently observed value.

## Questions

1. Does Binance document corrections or revisions to settled funding rows?
2. Does Funding Rate History expose revision identity or only current state?
3. Can the current endpoint return a value revised after original settlement?
4. Is any permanent finality/checksum guarantee available for these rows?
5. Which limitations remain acceptable under ADR 0008 without weakening causality?

## Evidence contract

Retain exact official bytes, request scope, local receipt, SourceSnapshot, SHA-256,
effective-date basis, and quoted passages. Absence claims must be bounded to the exact
searched first-party surfaces; do not claim provider-global completeness.

## Write set

- `docs/research/g12m-binance-funding-revision-authority-v1.md`
- A dedicated `evidence/g12m-binance-funding-revision-authority-v1/` subtree

Do not edit BHA-01A evidence, shared manifests, registries, packages, or accepted v2
artifacts.

## Decision contribution

Return a closed limitation set to BHA-02. Missing permanent finality may remain an
ADR 0008 limitation. Missing identity for the exact revision visible at settlement is
a causal blocker and cannot be downgraded to a finality limitation.

## Acceptance

- Raw-byte replay reproduces all retained hashes.
- Claims are source-bounded and target-effective where asserted.
- Independent primary-source review passes.
- Secret scan passes; no credential or cookie value is retained.

## Exclusions

- Settlement-time equality, owned by BHA-01A.
- H1/H2/H3 decision, owned by BHA-02.
- Event revision IDs or implementation code.
