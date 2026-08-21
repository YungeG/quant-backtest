---
id: G12M-BHA-08
status: DRAFT_WAITING
owner: canonical Run single writer
produces:
  - one persisted decision-grade Binance Run
  - exact trace, crosswalk, and accounting disposition evidence
consumes:
  - G12M-BHA-05
  - G12M-BHA-07
depends_on:
  contract: [G12M-BHA-05, G12M-BHA-07]
  evidence: [accepted BHA-03 v3 and BHA-06 crosswalk]
  write_conflict: [canonical-runtime-fixtures]
fan_in: G12M-BHA-09
---

# BHA-08 Produce and verify the canonical Run

## Outcome

Persist one exact Run whose decision-grade Result consumes the accepted v3 funding
Events from the accepted execution Bundle and preserves deterministic accounting
proof.

## Inputs

- Accepted BHA-05 Bundle and all component stream bytes.
- Accepted BHA-07 production registration/integration.
- Exact v3 report, authority, adapter crosswalk, Build/Profile/Environment identities,
  and strategy target stream.

## Run contract

Freeze request and semantic Run identity, Bundle/Build/Profile/Environment identities,
requested/result grade, Integrity context/report, execution result, completed
publication, timeline trace, adapter crosswalk, and accounting trace/journal.

The trace must contain every required initial v3 Event ID/hash at the exact
funding/availability instant. The crosswalk must prove that the same Event reached the
selected funding resolution. A selected Event with a non-null source predecessor
blocks the canonical Run; it is never flattened into an initial revision.

Run two journeys:

1. a relevant position spans at least one funding event and produces exact settlement
   and journal identities;
2. zero exposure produces explicit `NOT_APPLICABLE`/zero-exposure disposition without
   pretending the Event was unconsumed.

## Expected write set

- Dedicated Runtime integration journey tests.
- New immutable canonical Run/publication/trace/accounting fixtures.
- Minimal off-root test support only when existing fixtures cannot express the case.

No source, authority, Bundle, Profile registration, adapter implementation, or generic
Runtime policy changes.

## Acceptance

- Persisted canonical reconstruction and replay parity.
- Integrity verification and exact requested/result grade.
- Event trace and adapter crosswalk identity checks.
- Position and zero-position accounting disposition tests.
- Tampered Run/Bundle/Profile/trace/journal and corrected-source execution cases fail
  closed.
- Focused and adjacent suites, full architecture suite, full repository suite,
  Ruff/LSP/diff/secret scan.
- Independent Runtime/accounting review.

## Exclusions

- G12M assessment logic.
- Registry fan-in or live/deployment claims.
