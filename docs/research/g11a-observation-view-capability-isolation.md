# G11A ObservationView Capability Isolation — Frozen Seam

## Scope

G11A freezes the smallest Strategy-facing read seam: an immutable, capability-isolated `ObservationView` that accepts an explicit dataset, Instrument, semantic purpose, and exact MarketBundle capability on every query.

G11A does not invoke Strategy code, read a MarketBundle, choose a point-in-time revision, enforce a decision-time visibility cutoff, construct a Universe, build Bar windows, resample data, schedule Decisions, maintain StrategyState, expose account state, or authorize decision-grade/deployment use. G11B owns availability/revision selection and causality trace; G11C owns Universe semantics; G11D owns named Bar/window semantics; G11E–G11I own scheduling and Strategy invocation.

## Inherited authorities

G11A reuses these existing contracts without reinterpretation:

1. `InstrumentId` is the stable Instrument subject.
2. `MarketBundleCapability` is the exact key/version data capability identity.
3. `MarketEvent` is the immutable canonical observation record, including stream, event type, Instrument, event/available times, Timeline phase/sequence, revision lineage, source identity/hash, and frozen payload.
4. Canonical bytes/hash functions define deterministic identities.
5. `MarketBundleReader` remains a Runtime/Timeline read seam and is never exposed through the Strategy-facing view.

The authoritative architecture is `docs/architecture/backtest-system-design.md`, sections 7.1 and 8.2–8.3. The current Gate split is `docs/implementation/target-driven-bar-v1-plan.md`, G11A–G11D.

## Seam placement

The production module belongs in `crypto_quant_backtest.observations` because it is a Strategy-facing Runtime view over already-supplied immutable market evidence. It may import only stdlib, `crypto_quant_domain`, and `crypto_quant_market_data` contracts.

The module interface is intentionally small:

- `ObservationPurposeRef` — versioned semantic purpose identity;
- `ObservationQuery` — exact dataset/Instrument/purpose/capability selector;
- `ObservationRecord` — explicit purpose plus one immutable `MarketEvent`;
- structured query failure/result/outcome values;
- `ObservationView.view_hash` and `ObservationView.query(...)`.

The view does not expose its backing records, a `MarketBundleReader`, Bundle Ref/Manifest, Cursor, Ledger, Snapshot, filesystem path, callback, network client, process handle, clock, or mutable cache.

## Query capability model

The view receives an immutable allowlist of exact `ObservationQuery` values. An allowed query is therefore the capability grant; no second shallow grant type is needed.

Each query exact-declares:

- `dataset_key` — the canonical Market stream/dataset identity;
- `instrument_id` — one stable Instrument; G11A v1 has no global/Universe query;
- `purpose` — a versioned semantic purpose, distinct from Event type;
- `capability` — exact `MarketBundleCapability` key/version.

Authorization failure precedence is:

1. `DATASET_NOT_AUTHORIZED`;
2. `INSTRUMENT_NOT_AUTHORIZED`;
3. `PURPOSE_NOT_AUTHORIZED`;
4. `CAPABILITY_NOT_AUTHORIZED`.

This precedence is evaluated only against the allowlist, not against hidden backing records. A failure must not disclose whether unauthorized data exists.

An exact authorized query with no matching record succeeds with an empty tuple. G11A does not interpret absence as a coverage gap, no-session fact, suspension, or source outage; later Gates own those semantics.

## Record and purpose model

`ObservationRecord` wraps an existing `MarketEvent` and an explicit `ObservationPurposeRef`.

Its query context is derived without payload inspection:

- dataset from `MarketEvent.stream_key`;
- Instrument from `MarketEvent.instrument_id`;
- capability from `MarketEvent.capability`;
- purpose from the wrapper.

G11A v1 rejects Instrument-less records. G11C may add a separate typed Universe query rather than overloading `None`.

The same raw `MarketEvent` may support multiple purposes only through separate explicit records. A shared source row never creates an implicit cross-purpose fallback.

Input record order cannot change view/result identity. Duplicate `(purpose, event_id)` with exact content is one record; conflicting content fails construction. Query results use deterministic MarketEvent ordering plus stable identity tie-breakers.

## Hidden-record and cache isolation

A caller may construct a view from a broad immutable record set. During construction, the view retains only records whose exact selector is present in the allowlist. Unauthorized records:

- are not stored by the Strategy-facing view;
- do not affect `view_hash`;
- cannot appear in a result;
- cannot change an authorized result hash.

G11A v1 intentionally has no result cache. A linear scan over the retained immutable tuple is sufficient for the frozen fixture. If profiling later justifies a cache, it must be private, keyed by the exact authorized query hash, and populated only after authorization; cache behavior cannot change canonical results or visibility.

## Time and revision boundary

Although `MarketEvent` preserves event time, available time, full Timeline instant, revision ID, supersession, and source lineage, G11A does not select among revisions or accept a Decision Time.

Therefore a G11A view is not yet a complete glossary-qualified point-in-time Observation View and must not be handed to executable Strategy code. G11B must add:

- `available_time/full SimulationInstant <= decision instant` enforcement;
- latest legal revision selection without rewriting prior views;
- maximum event/available times, revision IDs, dataset hashes, and query trace;
- future-revision failures.

Keeping these rules out of G11A prevents a partial duplicate revision engine while still freezing the capability seam G11B will deepen.

## Strategy and ambient authority boundary

G11A ensures the Strategy-facing interface does not hand out Bundle, Reader, Ledger, account state, filesystem, network, process, or clock objects. It does not claim to sandbox arbitrary in-process Python code from importing ambient libraries; G11I/build qualification must constrain executable Strategy artifacts separately.

No Strategy callback, implementation object, module path, runtime address, PID, wall clock, or mutable cache enters query/view/result identity.

## Development limitations

All G11A outputs are development-only because:

- decision-time visibility and revision selection are not implemented until G11B;
- Universe and Bar/window coverage are not implemented until G11C/G11D;
- no Strategy is invoked until G11I;
- arbitrary Python ambient-authority sandboxing is not provided;
- G12 has not supplied real decision-grade MarketBundle completeness.

G11A must not alter Engine, Runner, Timeline, MarketBundleReader, TargetStream, Journal, Ledger, or Profile behavior.
