---
id: G12M-BHA-05
status: TERMINATED_H3
owner: Builder execution-Bundle writer
produces:
  - one immutable complete execution Bundle
  - exact funding-stream membership proof
consumes:
  - G12M-BHA-03
  - G12M-BHA-04
depends_on:
  contract: [G12M-BHA-03, G12M-BHA-04]
  evidence: [accepted component streams]
  write_conflict: []
fan_in: [G12M-BHA-07, G12M-BHA-08, G12M-BHA-09]
---

# BHA-05 Build the complete execution Bundle

## Outcome

Publish one immutable Bundle that satisfies the exact BHA-04 production capability
contract and proves exact membership of the accepted BHA-03 funding stream.

## Inputs

- Accepted v3 report, Event stream, stream manifest, and BundleRef.
- Accepted BHA-04 capability keys/versions.
- Exact `account.financial-event`, `bar_open`, Binance price-purpose, target-stream,
  and other required component streams.

## Interface and invariants

Use the existing `MarketBundleManifest`, validators, and repository publication path.
The source-evidence and execution BundleRefs may differ.

The execution manifest funding entry must match BHA-03 on stream key, capability and
version, count, stream content hash, and replayed ordered Event hashes. Coverage must
include all Event/Availability Times at settlement and satisfy the request window.

No cross-Bundle read, resampling, forward fill, synthetic Bar, nearby mark, role
fallback, or second inclusion-proof/catalog framework.

## Expected write set

- One provider-specific Bundle composition module or fixture builder off the public
  Builder root.
- Dedicated execution-Bundle fixtures and focused tests.
- Existing generic manifest/repository code only if a proven defect blocks the exact
  contract; otherwise it remains unchanged.

No Runtime/Profile registration, adapter, accepted source v3, or canonical Run files.

## Failure precedence

1. malformed component stream;
2. missing required capability;
3. duplicate/incompatible capability;
4. funding stream identity/count/hash mismatch;
5. coverage mismatch;
6. cross-Bundle or role fallback attempt;
7. manifest/BundleRef reconstruction mismatch.

## Acceptance

- Required-capability resolution against BHA-04.
- Exact funding membership and tamper tests.
- One-Bundle/no-resampling/no-network architecture tests.
- Atomic publication and deterministic replay.
- Golden manifest/BundleRef bytes and hashes.
- Focused Builder/market-data tests, Ruff/LSP/diff/secret scan.
- Independent Bundle-contract review.

## Exclusions

- Profile registration.
- Runtime Event conversion.
- Run execution, Integrity, accounting, or G12M assessment.
