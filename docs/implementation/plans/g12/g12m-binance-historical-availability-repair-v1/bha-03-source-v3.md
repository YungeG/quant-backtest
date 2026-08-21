---
id: G12M-BHA-03
status: TERMINATED_H3
owner: Builder source-v3 writer
produces:
  - additive Binance funding-history source-bounded v3 report
  - exact revisioned funding MarketEvents and stream manifest
consumes:
  - G12M-BHA-02 H1 authority
  - accepted funding-history source-bounded v2 report
depends_on:
  contract: [G12M-BHA-02]
  evidence: [accepted Binance funding-history v2]
  write_conflict: []
fan_in: [G12M-BHA-05, G12M-BHA-06]
---

# BHA-03 Publish additive funding-history source v3

## Outcome

Produce new canonical v3 report/Event/stream/Bundle identities that reuse accepted v2
row normalization and replace only the independently authorized availability meaning.

## Inputs

- Exact accepted v2 observation-report bytes.
- Exact BHA-02 H1 authority bytes and frozen v3 capability/payload contract.
- Existing `MarketEvent`, manifest, validation, and publication contracts.

## Interface and invariants

The provider-specific off-root Builder function accepts the two exact canonical byte
values only and emits the exact BHA-02 capability/version and payload contract:

```text
event_time      = fundingTime
available_time  = fundingTime
phase           = market-data phase
source_sequence = retained provider row order
observed_at      = accepted v2 acquisition time
```

It binds v2 report hash, authority hash, source-row hashes, Event hashes, stream hash,
manifest, BundleRef, limitations, and direct report predecessor.

Initial v3 Events use a new `revision_id` derived from source-record and authority
hashes and `supersedes_revision_id = null`. A corrective v3 Event points only to the
direct preceding v3 revision. V2 is evidence lineage, not an Event revision parent.

## Expected write set

- One new off-root Builder source-v3 module.
- New v3-focused tests and fixtures under a dedicated provider path.
- New architecture test proving no Runtime/Kernel import and no root export.

Do not edit v2 modules/fixtures/hashes, generic MarketEvent contracts, Builder roots,
repository/catalog infrastructure, Runtime, or Kernel.

## Failure precedence

1. malformed v2 report;
2. malformed authority;
3. v2 identity/hash mismatch;
4. authority scope mismatch;
5. missing row availability;
6. availability-time inequality;
7. invalid revision/predecessor;
8. canonical output mismatch.

## Acceptance

- Exact v2 replay and immutable-byte fingerprint.
- H1 authority binding and adversarial row/scope/time tests.
- Event/stream/manifest/report golden reconstruction.
- Initial and corrective revision tests.
- Focused Builder and architecture suites, Ruff/LSP/diff/secret scan.
- Independent canonical-identity review.

## Exclusions

- Production Profile authority.
- Execution Bundle composition.
- Runtime adapter or Run.
- G12M assessment.
