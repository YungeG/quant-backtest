# G12I Price, Availability, and Revision Coverage Readiness Analysis

## Decision status

G12I remains **DRAFT / BLOCKED**. The Builder now owns immutable declaration value contracts and test-only G03 stale-policy parity, but no real profile/build authority, provider/calendar classification, or terminal-set closure has been supplied.

This note does not authorize the final analyzer, provider completeness, decision-grade use, Runtime qualification, or deployment.

## Frozen prerequisite seam

`crypto_quant_bundle_builder.coverage_declarations` now exports:

- `BuilderStaleMarkPolicy` — exact Kernel-independent projection of G03 `StaleMarkPolicy`;
- `PricePurposeRequirement` — one Instrument/purpose/stream/time requirement bound to the projection and source identity;
- `MarketAvailabilityReason` — the closed caller-declared reason vocabulary;
- `AvailabilitySpan` and `AvailabilityClosureDeclaration` — exact half-open caller declarations linked to a G12G manifest hash;
- `RevisionTerminalLineage` and `RevisionClosureDeclaration` — exact caller-declared terminal hashes and causal visibility limit.

All declaration records are frozen/slotted schema-v1 values with constructor validation, canonical hashes, explicit empty-scope semantics, and fixed development-only qualification. The Builder production module imports only Domain and Market Data public contracts. Trading Kernel appears only in parity tests.

The stale-policy projection intentionally preserves the G03 canonical body byte-for-byte, so its schema-v1 identity is class authority rather than an added canonical field. `policy_hash` is always recomputed as `canonical_sha256(projection)` and exact-matches the authoritative Kernel value for equal inputs.

`PricePurposeRequirement` rejects cross-purpose policy binding and rejects forward fill for `EXECUTION_REFERENCE` and `LIQUIDATION`. It is passive data, not a resolver, evaluator, fallback engine, or state machine.

## What remains blocked

The checked-in fixture proves only deterministic contract shape. It is not real market authority.

G12I still requires:

1. immutable profile/build ownership declaring the complete required purpose set and exact Bundle scopes;
2. real provider/calendar-backed availability declarations classifying every required scope, including justified empty scope;
3. real terminal-set closure declarations proving that no in-scope lineage or later visible correction was omitted;
4. exact binding of those declarations to the target G12C/G12G artifacts.

G12G mechanical empty-bucket counts must not manufacture `NO_SESSION`, `SUSPENDED`, `NO_TRADES`, `MISSING`, or `SOURCE_OUTAGE`. A locally valid revision chain must not be treated as proof of provider terminal-set completeness.

## Provisional downstream outcome

Only after real declaration evidence is frozen may G12I add, atomically:

- `PriceStreamCoverageReport`;
- `MarketAvailabilityReport`;
- `RevisionProvenanceReport`;
- one combined coverage manifest; or
- one structured failure.

None of those reports is implemented by this prerequisite slice.

## Non-goals

- No calendar/session derivation or gap-reason invention.
- No Bar generation, interpolation, carry close, placeholder data, or forward-filled execution/liquidation evidence.
- No provider adapter, API, filesystem/network/wall-clock read, cache, registry, DSL, resolver, or rule engine.
- No Runtime/Kernel production import, Engine branch, market qualification, live use, or deployment authorization.
