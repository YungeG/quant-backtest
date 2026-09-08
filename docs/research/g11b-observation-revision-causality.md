# G11B Point-in-time Observation Revision Selection and Causality — Frozen Seam

## Scope

G11B deepens the G11A Strategy-facing observation seam with one caller-supplied `SimulationInstant`, full availability-order filtering, latest legal revision selection, and a canonical per-query causality trace.

G11B does not read a MarketBundle, invoke Strategy code, choose a Universe, build Bar windows, classify data gaps, resample data, schedule Decisions, maintain StrategyState, aggregate invocation traces, or authorize decision-grade/deployment use. G11C owns Universe semantics; G11D owns Bar/window semantics; G11E–G11I own scheduling and invocation; G12 owns real Bundle completeness and revision coverage.

## Inherited authorities

G11B reuses without reinterpretation:

1. G11A `ObservationPurposeRef`, `ObservationQuery`, `ObservationRecord`, and exact Dataset → Instrument → Purpose → Capability authorization precedence.
2. `MarketEvent` as the immutable versioned market record, including event/available time, Timeline phase/source sequence, Event ID, Revision ID, superseded Revision ID, source identity/hash, and frozen payload.
3. `SimulationInstant` as the total ordering position `(UtcInstant, TimelinePhase, SourceSequence)`.
4. Canonical bytes/hash functions as the only identity encoding.

The authoritative architecture is `docs/architecture/backtest-system-design.md`, especially the Strategy Runtime and MarketBundle revision sections. G11A's frozen seam is `docs/research/g11a-observation-view-capability-isolation.md`.

## Existing contract gap

`MarketEvent.event_id` is unique for each immutable event version in a Bundle. It cannot identify one logical observation across several versions. `revision_id` is source-revision provenance and may legitimately repeat across many independent observations; G11A's static bars both use `rev-1`.

Therefore G11B must not group corrections by Event ID, Revision ID alone, event time, payload shape, tuple position, or source hash. It requires a caller-supplied canonical `observation_key` that identifies one logical observation lineage within an exact `ObservationQuery`.

A `RevisionedObservationRecord` contains:

- one nonempty canonical `observation_key`;
- one existing G11A `ObservationRecord`.

Its version identity is `(ObservationQuery, observation_key, MarketEvent.revision_id)`. Event ID remains the immutable version-record identity. Revision ID remains provider/source revision provenance. Observation key is the stable logical fact identity across corrections.

G11B v1 does not infer observation keys from payload fields. Source adapters/builders must supply them. Deletion/tombstone semantics remain unsupported unless a later typed record contract freezes them explicitly.

## Point-in-time view seam

The production seam remains `crypto_quant_backtest.observations`. G11A public types and canonical bytes remain unchanged.

G11B adds a separate `PointInTimeObservationView` rather than making G11A's unsafe no-time `ObservationView.query(...)` appear point-in-time complete. Its constructor accepts only:

- exact allowed `ObservationQuery` values;
- caller-supplied immutable `RevisionedObservationRecord` values;
- one exact `decision_instant: SimulationInstant`.

The Strategy-facing public surface remains only:

- `view_hash`;
- `query(ObservationQuery)`.

The view does not expose its decision instant, allowlist, backing revisions, superseded payloads, Bundle/Reader, Timeline, clock, Ledger, account state, cache, callbacks, or runtime objects.

## Authorization and visibility order

Construction applies rules in this order:

1. discard records whose exact query selector is not authorized;
2. discard records whose `MarketEvent.timeline_instant` is after the supplied decision instant;
3. canonicalize exact duplicates and retain visible authorized revision evidence.

This order is required for noninterference:

- unauthorized records cannot affect the point-in-time view hash or any outcome;
- future records, future corrections, and conflicts that are not yet available cannot affect an earlier view hash or result;
- adding a later vendor correction to the same immutable archive cannot rewrite a previously observed DecisionContext.

Visibility uses full `SimulationInstant` ordering, not only UTC nanoseconds. An event at the same UTC time but a later Timeline phase or Source Sequence is future data for that decision.

A forged result containing an event whose timeline instant is after the decision instant fails construction. Normal queries do not fail merely because the backing archive contains future records; those records are invisible.

## Revision-chain rules

Revision selection is performed independently for each exact `(ObservationQuery, observation_key)` lineage after authorization and visibility filtering.

A legal visible lineage has:

1. one root revision whose `supersedes_revision_id` is `None`;
2. unique Revision IDs within that observation lineage;
3. every non-root revision naming an existing visible parent Revision ID in the same lineage;
4. no fork, cycle, or disconnected second root;
5. stable query context, event type, and event time across the lineage;
6. a strictly increasing `MarketEvent.timeline_instant` from parent to child.

The selected version is the unique terminal revision in the visible legal chain. Before a correction becomes available, its predecessor remains selected. At or after the correction's exact Simulation Instant, the correction becomes selected. Old versions remain immutable audit evidence and are never overwritten.

Independent observation keys may reuse the same source Revision ID. Multiple independent observations may share an event time. Neither is ambiguity.

## Query failures and precedence

G11A authorization failures remain the first four failures and are returned without inspecting revision evidence:

1. `DATASET_NOT_AUTHORIZED`;
2. `INSTRUMENT_NOT_AUTHORIZED`;
3. `PURPOSE_NOT_AUTHORIZED`;
4. `CAPABILITY_NOT_AUTHORIZED`.

For an authorized query, G11B causality failure precedence is:

1. `REVISION_ID_CONFLICT` — same observation key/revision identity has conflicting canonical content;
2. `REVISION_PARENT_MISSING` — a visible non-root revision names no visible parent in its lineage;
3. `REVISION_CHAIN_CONFLICT` — fork, cycle, zero/multiple roots, disconnected chain, or multiple terminals;
4. `REVISION_CONTEXT_MISMATCH` — query context, event type, or event time changes inside a lineage;
5. `REVISION_AVAILABILITY_REGRESSION` — child availability Simulation Instant is not strictly after its parent.

Multiple defects return only the first code. Failure evidence carries sorted observation keys, Revision IDs, and candidate record hashes, never hidden unauthorized/future payloads.

An exact authorized query with no visible record succeeds with an empty result and an empty causality trace. G11B does not reinterpret empty as coverage success/failure, no session, suspension, no trades, or source outage.

## Causality trace

Every successful point-in-time query returns selected `MarketEvent` values plus one canonical `ObservationCausalityTrace` containing:

- point-in-time view hash;
- exact query and decision instant;
- sorted hashes of all visible authorized candidate revision records for that query;
- a revision-set hash derived from those candidate hashes;
- selected observation keys, Event hashes, Revision IDs, and source hashes aligned to result order;
- selected dataset hash derived from the exact query, observation keys, and selected Event canonical values;
- maximum selected event time, or `None` for an empty result;
- maximum selected available `SimulationInstant`, or `None` for an empty result;
- selected event count and trace hash.

The result constructor exact-validates that events match the query, are not future, use canonical order, and agree with all selected trace fields, maxima, and the selected dataset hash. The trace's visible candidate hashes prove which revision set was eligible without exposing superseded payloads to Strategy code.

G11I may later aggregate multiple query traces with StrategyState/RNG/Model evidence into a Decision invocation audit. G11B does not create that aggregate or a DecisionBatch.

## Canonical ordering and identity

Selected events use existing G11A deterministic ordering: `MarketEvent.ordering_key`, Event ID, Revision ID, and stable record/hash tie-breaks. Input order, Mapping order, and exact duplicate inputs cannot change view, result, trace, failure, or outcome identity.

`PointInTimeObservationView.view_hash` binds only:

- schema/model identity;
- exact decision instant;
- canonical allowlist;
- visible authorized revision records.

It does not bind unauthorized records, future records, wall clock, filesystem root, PID, runtime address, Attempt ID, Strategy implementation, or mutable cache.

## Purity and ownership exclusions

The module remains pure in-memory and may import only stdlib plus public `crypto_quant_domain` and `crypto_quant_market_data` contracts. It must not import or read:

- MarketBundle Reader/Manifest/Cursor or Builder;
- Engine, Runner, Timeline, TargetStream, Profile, Journal, Ledger, Snapshot, or account state;
- filesystem, network, database, process, environment, wall clock, provider SDK, or dynamic import;
- Strategy callback, implementation object, module path, or runtime address.

G11B v1 has no cache. A later private cache requires measured need and must be populated only after authorization/visibility filtering with exact query+decision identity; it cannot change canonical output.

## Development limitations

All G11B outputs remain development-only because:

- Universe/listing/membership semantics are not frozen until G11C;
- Bar/window/lookback and gap coverage are not frozen until G11D;
- Strategy scheduling/invocation and aggregate causality audit are not frozen until G11E–G11I;
- G12 has not proved real MarketBundle revision completeness;
- no live or deployment qualification exists.

G11B must not alter G11A canonical artifacts or Engine/Runner behavior.
