---
id: G12M-BHA-06
status: DRAFT_WAITING
owner: Runtime-to-Kernel adapter writer
produces:
  - provider-specific MarketEvent-to-G10E adapter
  - deterministic source-to-accounting lineage crosswalk contract
consumes:
  - G12M-BHA-03
  - G12M-BHA-04
  - existing G10E funding source contracts
depends_on:
  contract: [G12M-BHA-03, G12M-BHA-04, G10E]
  evidence: []
  write_conflict: []
fan_in: [G12M-BHA-07, G12M-BHA-08, G12M-BHA-09]
---

# BHA-06 Adapt v3 Events into the existing funding path

## Outcome

Add one pure provider-specific Runtime-to-Kernel conversion that preserves the exact
v3 Event lineage while reusing the existing G10E funding resolver and record types.

## Inputs

- Exact BHA-03 v3 `MarketEvent` contract and payload.
- BHA-04 funding capability/version.
- Existing `BinanceUsdmFundingRateRecord` and `BinanceUsdmFundingSourceRef`.

## Interface and invariants

A single function accepts an exact v3 Event plus the frozen BHA-03 source-stream
identity and returns the existing funding record type. BHA-07, not this adapter,
later proves that stream's membership in the BHA-05 execution Bundle:

```text
record.funding_time                       = event.event_time
record.archive_available_at              = event.timeline_instant
record.event_id                          = event.event_id
record.revision_id                       = event.revision_id
record.source_ref.source_hash            = event.event_hash
record.source_ref.supersedes_revision_id = event.supersedes_revision_id
```

Require exact provider, dataset, event type, capability/version, instrument, funding
purpose, market-data phase, source sequence, decimal strings/units/scales, source-row
hash, and BHA-03 stream identity. The Event must be visible at the settlement instant
before the funding eligibility phase.

Current G10E rejects non-null source predecessors. This adapter therefore accepts only
initial v3 Events with `supersedes_revision_id = null`; it rejects rather than erases a
correction predecessor. Corrective v3 Events remain source evidence and require a
separate additive/versioned G10E correction plan before execution qualification.

Freeze a reconstructable crosswalk:

```text
v3 Event ID/hash
→ funding record/event/source-ref hash
→ selected existing funding resolution
→ settlement/accounting evidence identity
```

Do not add a resolver, registry, mapping-based adapter, fallback timestamp, nearby
mark, or synthetic publication.

## Expected write set

- One new off-root Runtime adapter module.
- Focused adapter/crosswalk tests and golden fixture.
- One architecture test for Runtime→Builder and Kernel→Runtime prohibition.

No Builder files, shared Profile registration, existing G10E implementation, Runtime
root export, engine orchestration, or canonical Run fixture.

## Failure precedence

1. wrong exact input type;
2. provider/dataset/capability mismatch;
3. instrument/funding-purpose mismatch;
4. invalid phase/time/sequence;
5. invalid payload decimal/scale;
6. source-row/Event hash mismatch;
7. unsupported non-null source predecessor;
8. invalid revision identity;
9. crosswalk reconstruction mismatch.

## Acceptance

- Golden Event→record→crosswalk reconstruction.
- Equality and phase-order tests at the funding instant.
- Malformed/tampered payload and identity adversarial cases.
- Existing G10E resolution remains unchanged; non-null source predecessor fails
  closed and adjacent tests pass.
- Architecture, Ruff/LSP/diff, and secret scan clean.
- Independent causality review.

## Exclusions

- Bundle construction.
- Shared Runtime registration/orchestration.
- Run, Integrity, accounting journey, or G12M assessment.
