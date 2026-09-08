---
id: G12M-BHA-01A
status: DRAFT_READY
owner: Binance settlement authority researcher
produces:
  - target-effective funding settlement and availability research note
  - retained first-party source bytes and hashes
consumes:
  - ../g12m-binance-historical-availability-repair-v1.md
depends_on:
  contract: []
  evidence: [first-party Binance USD-M materials]
  write_conflict: []
fan_in: G12M-BHA-02
---

# BHA-01A Establish settlement-time authority

## Outcome

Determine whether first-party Binance semantics effective for the three 2024 rows
prove the exact rate and settlement mark usable at the funding settlement instant.

## Questions

1. What does `fundingTime` mean for USD-M Funding Rate History?
2. When is the final rate fixed and applied?
3. Is the returned `markPrice` the exact settlement mark?
4. Is the exact rate+mark revision available at, before, or only after settlement?
5. Are the semantics target-effective for the 2024 period rather than current-only?

## Evidence contract

Retain exact official response/document bytes, URL/request scope, local receipt,
SourceSnapshot, SHA-256, effective-date basis, and quoted passages. Record negative
searches and access limitations. Secondary sources may locate material but cannot
supply authority.

## Write set

- `docs/research/g12m-binance-funding-settlement-availability-authority-v1.md`
- A dedicated `evidence/g12m-binance-funding-settlement-availability-v1/` subtree

Do not edit shared manifests, governance registries, packages, or accepted evidence.

## Decision contribution

Return one evidence-backed input to BHA-02:

- `HISTORICAL_EQUALITY_SUPPORTED` only if exact target-effective authority proves
  `provider_available_time == funding_time` for rate and mark;
- `PROSPECTIVE_ONLY` when only future capture can establish the instant;
- `UNKNOWN` otherwise.

## Acceptance

- Raw-byte replay reproduces every retained hash.
- Research note distinguishes documented fact, inference, and limitation.
- Independent primary-source review passes.
- Secret scan passes; no credential or cookie value is retained.

## Exclusions

- Correction/revision closure, owned by BHA-01B.
- H1/H2/H3 decision, owned by BHA-02.
- Any code or synthetic availability timestamp.
