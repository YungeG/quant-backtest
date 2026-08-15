# G12K Universe and Corporate Action Coverage Readiness Analysis

## Decision status

G12K remains **DRAFT / BLOCKED**. G12C validates generic Event integrity, G11C evaluates supplied Universe revisions, and G08F evaluates supplied corporate-action evidence, but no Builder-normalized listing, membership, or corporate-action Event schemas and no closure declarations exist.

This note records the blocker. It does not authorize fabricated schemas, completeness claims, Runtime qualification, decision-grade use, or deployment.

## Verified existing authority

- G12C carries an opaque `instrument_catalog_hash`; it does not carry or verify an `InstrumentCatalog` body.
- G11C owns point-in-time listing/membership selection from supplied revisions but explicitly does not prove completeness or survivorship safety.
- G08F owns A-share corporate-action lifecycle/economic checks over supplied announcements and registered-position evidence but does not prove a closed provider action inventory.
- The repository has no production G12B schemas named `instrument_listing_revision.v1`, `universe_membership_revision.v1`, or `corporate_action_announcement.v1`.
- Builder may not import Backtest Runtime or Trading Kernel production code.

Therefore G12K cannot implement against those proposed Event names, infer catalog contents from a hash, or treat absence as complete coverage.

## Missing prerequisite contracts

### Catalog body binding

A canonical immutable `InstrumentCatalog` artifact whose hash exact-matches the G12C manifest, including catalog schema/version and source authority.

### Normalized lifecycle and membership schemas

G12B-owned Event contracts for listing lifecycle and Universe membership revisions, including:

- stable logical keys;
- Instrument and Universe identity;
- finite effective interval semantics;
- full revision/supersession/source identity;
- listing reference and point-in-time causality;
- exact capabilities and stream classification.

### Normalized corporate-action schema

A G12B-owned Event contract that preserves action ID, Instrument, lifecycle status, revision identity, source evidence, supported semantics key, and required lifecycle terms while leaving entitlement/accounting economics to G08F/G08G.

### Explicit closure declarations

Universe and action declarations must bind target interval/context, exact in-scope Event hashes, terminal revision hashes, source key/hash, explicit empty scope, and declaration hash. G12L later qualifies whether the declared closure matches reality.

## Provisional downstream outcome

Once prerequisites exist, G12K may atomically produce:

- `UniverseCoverageReport`;
- `CorporateActionCoverageReport`; or
- one structured failure.

The reports should bind the G12C Bundle ref, exact catalog/declaration identities, relevant and terminal Event hashes, canonical Instrument/action sets, explicit empty scope, `survivorship_bias_safe=false`, and false qualification flags.

Public names, canonical bodies, failure codes, and precedence remain provisional until normalized schemas and closure declarations are frozen.

## Evidence needed to become READY

- real immutable catalog artifact exact-bound to a G12C manifest;
- normalized G12B listing, membership, and corporate-action schemas with static fixtures;
- explicit Universe and action closure declarations, including zero-member/zero-action cases;
- test-only mapping parity to G11C and G08F authorities;
- listing containment and membership/listing causality;
- corrected revisions, cancellation/terminal closure, unsupported semantics, and required lifecycle terms;
- revision conflict/parent/context/availability failures, precedence, atomicity, repeat hashes, and Builder-only imports.

## Qualification boundary and non-goals

G12K will prove only mechanical consistency against declared closure. It will not select a Universe, infer lifecycle dates, certify survivorship safety, map provider identifiers, calculate entitlements, validate tax/rates, mutate accounting, or prove real-source completeness.

G12L owns provider/source closure authority. G12M owns market/profile qualification. A-share qualification also remains blocked by G08H closed revision/scope qualification and G08G replayable corporate-action effects.
