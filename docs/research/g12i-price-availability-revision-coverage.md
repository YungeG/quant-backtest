# G12I Price, Availability, and Revision Coverage Readiness Analysis

## Decision status

G12I remains **DRAFT / BLOCKED**. G12C and G12G are PASSED, but the Builder lacks frozen canonical input declarations for price-purpose requirements, stale-policy evidence, availability classifications, and generalized revision-closure claims.

This note records the missing authority. It does not authorize implementation, provider completeness, decision-grade use, Runtime qualification, or deployment.

## Verified existing authority

- G12C binds Bundle coverage, stream capabilities, Event ordering, revision envelopes, and source identities.
- G12G binds mechanical Bar bucket/out-of-plan counts, source Event hashes, exact availability, and immutable Bar revisions.
- `PricePurpose` is Domain authority.
- `StaleMarkPolicy` is Trading Kernel authority with key/version/purpose/max-age/forward-fill fields and `policy_hash`.
- Builder may not import Trading Kernel production code.
- No existing Builder schema declares required purposes per market/profile, maps a Bundle stream to one purpose over an Instrument/time scope, classifies every availability gap, or attests that a supplied revision set is closed.

G12I therefore cannot claim exact G03 policy reuse, invent gap reasons from empty Bars, or generalize source-specific revision payloads without a preceding projection contract.

## Missing prerequisite contracts

Implementation requires immutable Builder-consumable declarations for:

### Price-purpose requirement declaration

- target Bundle/profile/Instrument scope;
- required `PricePurpose` tuple;
- exact stream/capability/schema identity per purpose;
- finite half-open coverage spans;
- a canonical stale-policy projection containing policy key/version/purpose/max-age/forward-fill and authoritative Kernel policy hash;
- test-only exact parity to `StaleMarkPolicy.to_canonical_dict()`.

### Availability closure declaration

- exact target interval and Instrument/purpose scope;
- caller-justified non-overlapping spans using frozen reasons;
- source key/hash and explicit empty coverage;
- links to relevant G12G bucket hashes/mechanical findings;
- declaration hash and authority provenance.

G12G mechanical emptiness must never manufacture `NO_SESSION`, `SUSPENDED`, `NO_TRADES`, `MISSING`, or `SOURCE_OUTAGE` by itself.

### Revision closure declaration

- exact logical lineage keys and in-scope Event hashes;
- declared terminal revision hashes;
- source key/hash and explicit empty closure;
- causal visibility limit;
- declaration hash and immutable source authority.

Event absence or one internally valid chain does not prove that no omitted correction exists.

## Provisional downstream outcome

After the declarations are frozen, G12I may produce atomically:

- `PriceStreamCoverageReport`;
- `MarketAvailabilityReport`;
- `RevisionProvenanceReport`;
- one combined coverage manifest; or
- one structured failure.

Reports must bind exact G12C/G12G refs and declaration hashes, remain development-only, and never mutate source artifacts.

The public seam, canonical bodies, and failure precedence remain provisional until the declaration contracts exist.

## Evidence needed to become READY

- real immutable fixtures for all three declaration types;
- test-only stale-policy projection parity to G03;
- explicit required-purpose ownership by a profile/build artifact;
- exact availability reason vocabulary and closure authority;
- revision terminal-set/closure evidence, including explicit empty scope;
- no-forward-fill tests for execution/liquidation purposes;
- cross-purpose fallback rejection;
- missing/duplicate purpose, unclassified/overlapping availability, broken/omitted revision closure, future visibility, precedence, atomicity, and repeat hashes;
- Builder-only import boundary.

## Non-goals

- No calendar/session derivation or gap-reason invention.
- No Bar generation, interpolation, carry close, placeholder data, or forward-filled execution evidence.
- No provider API, real-source completeness claim, or provider schema mapping; G12L owns those.
- No Runtime/Kernel production import, Engine branch, market qualification, live use, or deployment authorization; G12M owns final qualification.
