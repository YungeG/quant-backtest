# G12G Canonical Bar Aggregation v1 Contract

## Decision status

G12G readiness is **frozen READY** for implementation. The Gate remains `DRAFT` in `docs/implementation/acceptance-matrix.md`; this document does not mark G12G `PASSED` or authorize implementation evidence.

Freeze G12G as one pure, offline Builder compiler from a G12C-validated synthetic price stream plus one caller-supplied finite bucket plan to canonical revisioned `bar` Events. G12G owns deterministic aggregation mechanics and lineage only. It does not derive a calendar or schedule and does not own exchange-calendar truth, provider completeness, gap classification, decision-grade qualification, or deployment authorization.

Fixture ID: `canonical-bar-aggregation-v1`.

## Reused authority and ownership

G12G reuses without modifying:

- G12B `synthetic_price_point.v1` as the only v1 source payload grammar;
- G12C `validate_market_bundle_v1`, `MarketEvent`, `MarketStreamManifest`, `MarketBundleManifest`, and `MarketBundleRef` as the canonical Event/stream/Bundle authorities;
- Domain `UtcInstant`, `SimulationInstant`, `TimelinePhase`, `SourceSequence`, `SessionId`, `TradingDate`, `Scale`, `PricePurpose`, `canonical_bytes`, and `canonical_sha256`;
- G11D `BarDefinitionRef(key, version, definition_hash)` as the Runtime-compatible identity shape, without importing Backtest Runtime.

Builder production imports remain stdlib plus the public roots of `crypto_quant_domain` and `crypto_quant_market_data`, and the sibling G12C validator. There is no Trading Kernel, Backtest Runtime, provider SDK, network, filesystem, current clock, database, subprocess, Pandas, Polars, Arrow, DataFrame, registry, callback, protocol, or plug-in authority.

## Minimal public seam

One module, `crypto_quant_bundle_builder.bar_aggregation`, and one function:

```python
aggregate_bars_v1(
    *,
    source_manifest: MarketBundleManifest,
    source_events: tuple[MarketEvent, ...],
    bucket_plan: BarBucketPlan,
    definition: BarDefinition,
    aggregation_code_hash: str,
) -> BarAggregationOutcome
```

Builder root exports only:

- `BarBucket`;
- `BarBucketPlan`;
- `BarDefinition`;
- `BarAggregationManifest`;
- `BarAggregationResult`;
- `BarAggregationFailureCode`;
- `BarAggregationFailure`;
- `BarAggregationOutcome`;
- `aggregate_bars_v1`.

There is no generic payload mapper, calendar adapter or engine, bucket generator, resampling DSL, Reader, repository, path, mutable builder object, or default/current BarDefinition.

## Explicit finite bucket plan

`BarBucketPlan` is immutable, already-resolved input. G12G does not calculate interval grids, local times, time zones, DST, holidays, TradingDate, Session ownership, included phases, or empty intervals.

```text
BarBucket v1
  session_id: SessionId
  trading_date: TradingDate
  included_spans: canonical nonempty tuple[{start: UtcInstant, end_exclusive: UtcInstant}, ...]
  interval_start: UtcInstant
  interval_end_exclusive: UtcInstant
  bucket_hash: canonical_sha256(nonrecursive body)

BarBucketPlan v1
  plan_key: canonical nonempty str
  coverage_start: UtcInstant
  coverage_end_exclusive: UtcInstant
  bar_definition_key: canonical nonempty str
  bar_definition_version: positive non-bool int
  bar_definition_hash: sha256
  buckets: tuple[BarBucket, ...]
  bucket_plan_hash: canonical_sha256(nonrecursive body)
```

The canonical plan body binds type/schema, plan key, coverage, exact BarDefinition identity, and exact caller-order bucket bodies. Invariants are:

- coverage is a nonempty half-open UTC range;
- buckets are exact caller-order values and are never derived, split, merged, truncated, or repaired by G12G;
- every bucket has one or more ordered, disjoint, nonempty half-open included spans inside plan coverage;
- `interval_start` equals the first span start and `interval_end_exclusive` equals the final span end;
- each bucket's `SessionId.calendar_id` equals its `TradingDate.calendar_id`;
- flattened spans are strictly time-ordered and non-overlapping across buckets, and buckets do not interleave;
- the bucket tuple may be empty for a coverage window with no caller-declared interval;
- no UTC date, local date, phase, Session, TradingDate, or missing interval is inferred.

A-share lunch, UTC 24×7 days, fixed or truncated intervals, and night-session TradingDate ownership are therefore exact bucket facts supplied by the caller. G12I and later provider/market Gates must prove whether the plan is complete and authoritative.

## Frozen BarDefinition

```text
BarDefinition v1
  key: canonical nonempty str
  version: positive non-bool int
  output_stream_key: canonical nonempty str
  aggregation_kind: "explicit_bucket_price_ohlc"
  source_stream_key: canonical nonempty str
  source_event_type: "synthetic_price_point.v1"
  source_capability: MarketBundleCapability
  price_purpose: PricePurpose
  price_scale: Scale
  volume_semantics: "none"
  empty_interval_policy: "omit"
  output_phase: TimelinePhase
  definition_hash: canonical_sha256(nonrecursive body)
```

Invariants are:

- `aggregation_kind` is exactly `explicit_bucket_price_ohlc`;
- source and output stream keys differ;
- v1 accepts only the frozen source Event type, exact price-only OHLC, no volume, and omission of empty intervals;
- every semantic field above is inside the nonrecursive definition body;
- any semantic change changes `definition_hash`; version changes are caller-managed but no implicit current/default definition exists;
- the supplied plan's exact key/version/hash identity must equal this definition.

The exact G11D-compatible reference is constructed externally as:

```python
BarDefinitionRef(
    key=definition.key,
    version=definition.version,
    definition_hash=definition.definition_hash,
)
```

G12G never imports or constructs the Runtime class.

## Assignment and empty semantics

A source observation is assigned by economic `event_time` using each caller-supplied half-open span's `start <= event_time < end`:

- matching exactly one bucket span assigns the observation to that bucket;
- matching no bucket span leaves the observation out of plan and emits no Bar from it;
- valid plans cannot match multiple bucket spans because their spans do not overlap;
- half-open boundaries assign an Event at one span end only to the next supplied span, if one exists;
- an instrument/bucket with no selected observation emits no Event and is counted as empty/unclassified mechanical evidence.

The candidate Instrument set is the canonical distinct non-null Instrument tuple from all source revision chains with the selected PricePurpose, including out-of-plan chains. `planned_bucket_count` counts caller-supplied buckets; `empty_bucket_instrument_count` counts candidate-Instrument × bucket pairs with no assigned selected observation. Neither count is a coverage or qualification claim, and G12G makes no claim about Instruments absent from the source stream or catalog completeness.

G12G never emits zero-price, carry-close, forward-filled, placeholder, or gap-reason Bars. G12I later classifies absence as NO_SESSION, SUSPENDED, NO_TRADES, MISSING, SOURCE_OUTAGE, or another frozen reason; G12L/M prove provider and market qualification.

## Source validation and selection

Before aggregation, G12G reruns `validate_market_bundle_v1` with the supplied manifest header and complete unchanged `source_events` tuple. Success must exactly equal `source_manifest`; G12G never sorts or repairs source input.

The definition must identify exactly one source manifest stream, and that stream must match its exact Event type and capability. The output stream key must not already exist.

Every Event in that source stream must retain the exact G12B payload shape:

```text
synthetic_record_key
price_units
price_scale
price_purpose
```

Events with another valid PricePurpose are nonselected and counted. Events with the selected purpose require a non-null Instrument, positive non-bool integer units, and the definition's exact scale. Mixed-scale input fails; G12G does not rescale.

For each selected `(InstrumentId, synthetic_record_key)` chain, Instrument, purpose, scale, economic time, and assignment state (one exact bucket hash or out of plan) are immutable. Only price units, availability evidence, revision identity, supersession, and source provenance may change.

Distinct selected observation chains for the same Instrument may not share one economic `event_time`. G12B supplies no authoritative economic tie sequence, so v1 rejects that ambiguity rather than using Event ID, physical-line `SourceSequence`, revision arrival order, or lexical record key to decide open/close.

## Exact arithmetic

Source price is the exact rational value:

```text
price_units / 10**price_scale
```

V1 requires every selected value to have the definition's exact denominator. OHLC comparison and output use integer `price_units`; time arithmetic uses integer epoch nanoseconds. There is no float, ambient `Decimal`, implicit rounding, implicit scale conversion, VWAP, average, or division in aggregation. This is the complete v1 integer/rational arithmetic contract.

Volume is exact `null`. Observation count is provenance count, never trading volume.

## Mechanical revision processing

G12G mechanically validates enough of the supplied revision set to compile point-in-time Bars; it does not claim the set is complete.

For each selected observation key, including out-of-plan keys:

1. require exactly one root with `supersedes_revision_id=None`;
2. require every child to name an existing immediate parent in the same chain;
3. reject duplicate revision identity, fork, cycle, disconnected node, or multiple terminal paths;
4. require child `timeline_instant` to be strictly later than its parent;
5. reject a correction that changes Instrument, purpose, scale, economic time, or assignment state;
6. reject cancellation/deletion semantics, which G12B v1 cannot represent.

For each instrument/bucket:

1. apply all source revisions visible by bucket close and emit no Bar before close;
2. if no selected observation is visible at close, wait until the first later source availability that produces a nonempty state, then emit the root;
3. after close, group all relevant source changes at the same UTC availability time and apply the complete group before emitting;
4. emit a new immutable Bar revision whenever the ordered selected source Event-hash tuple changes, even if OHLC is numerically unchanged;
5. retain every prior Bar Event and point `supersedes_revision_id` to the immediately previous Bar revision;
6. never supersede across a changed definition, bucket plan, aggregation spec, code hash, or source stream identity.

Grouping same-UTC changes is mandatory because all causal source phases must precede the output phase. Emitting intermediate Bar states that were never visible at the output phase is forbidden.

## Bar Event contract

Every generated Event uses:

```text
event_type = "bar"
capability = MarketBundleCapability("price_bars", 1)
stream_key = definition.output_stream_key
event_time = bucket.interval_start
phase = definition.output_phase
source_key = "canonical-bar-aggregation-v1"
source_hash = aggregation_input_hash
```

Payload:

```text
schema_version = 1
bar_definition_key
bar_definition_version
bar_definition_hash
source_stream_hash
bucket_plan_hash
aggregation_spec_hash
aggregation_code_hash
aggregation_input_hash
bucket_hash
session_id
trading_date
included_spans
interval_start
interval_end_exclusive
price_purpose
price_scale
open/high/low/close = {units, scale}
volume = null
observation_count
source_event_hashes
selected_source_set_hash
```

`included_spans` preserves disjoint Session aggregation such as lunch. `source_event_hashes` is the visible terminal revision hash for each selected observation, ordered by economic Event time. `selected_source_set_hash = canonical_sha256(source_event_hashes)`.

Open/close are first/last integer price units; high/low are exact integer extrema. The single-observation case has identical OHLC values.

Bar revision identity is exact:

```text
bar_revision_identity_hash = canonical_sha256({
  type: "bar_revision_identity",
  schema_version: 1,
  aggregation_spec_hash,
  aggregation_input_hash,
  instrument_id,
  bucket_hash,
  selected_source_set_hash
})

event_id = "bar-event-v1:" + bar_revision_identity_hash
revision_id = "bar-revision-v1:" + bar_revision_identity_hash
```

A child names the immediately previous Bar revision ID.

Availability is:

```text
available_time = max(bucket.interval_end_exclusive,
                     latest causal selected source available_time)
```

At each equal UTC instant, `definition.output_phase` must sort strictly after every causal source phase. Otherwise aggregation fails `output_causality_invalid`. Generated `SourceSequence` is a zero-based deterministic output ordinal assigned after sorting candidate outputs by availability UTC, Instrument canonical bytes, bucket order/hash, and Bar revision identity. It is not an economic tie sequence.

## Aggregation and Bundle identity

The fixed algorithm identity is `canonical_bar_aggregation@1`:

```text
aggregation_spec_hash = canonical_sha256({
  type: "bar_aggregation_spec",
  schema_version: 1,
  aggregation_id: "canonical_bar_aggregation@1"
})
```

`aggregation_code_hash` is a required caller-supplied canonical SHA-256 for the immutable Builder artifact that executed the compiler. G12G validates and binds it but does not derive, inspect, or attest it and does not import Runtime `BuildArtifactManifest`. Decision-grade rebuild evidence must later prove that external artifact binding.

```text
aggregation_input_hash = canonical_sha256({
  type: "bar_aggregation_input",
  schema_version: 1,
  source_bundle_ref,
  source_stream_manifest,
  source_stream_hash,
  definition_hash,
  bucket_plan_hash,
  aggregation_spec_hash,
  aggregation_code_hash
})
```

`source_stream_hash` is the exact hash carried by the selected G12C stream manifest. Generated Bars explicitly commit source, definition, bucket-plan, aggregation-spec, aggregation-code, bucket, and selected source Event hashes. G12G appends generated Bars to unchanged `source_events` and reruns G12C; no result exists unless that final validation succeeds and returns the exact output manifest.

The output Bundle preserves source schema version, coverage, and Instrument catalog hash. Its deterministic key is:

```text
source_manifest.bundle_key
+ ".bar-aggregation-v1."
+ aggregation_input_hash without "sha256:"
```

This makes source/definition/bucket-plan/spec/code changes produce a distinct output Bundle identity even when every planned interval is empty and no Bar stream is emitted. With Bars present, the same changes also alter Bar Event hashes and the output stream hash.

`BarAggregationManifest v1` binds:

```text
source_bundle_ref
source_stream_manifest
source_stream_hash
bar_definition
bucket_plan_key
bucket_plan_hash
aggregation_spec_hash
aggregation_code_hash
aggregation_input_hash
input_event_count
source_stream_event_count
selected_source_revision_count
assigned_source_revision_count
out_of_plan_source_revision_count
nonselected_source_event_count
candidate_instrument_count
planned_bucket_count
empty_bucket_instrument_count
output_root_count
output_revision_count
output_stream_manifest | null
output_bundle_ref
decision_grade_eligible = false
deployment_authorized = false
manifest_hash
```

`output_revision_count` is the total emitted Bar Event count; roots are its subset. Counts and refs are derived, not caller-supplied. Exact count relationships are `source_stream_event_count = selected_source_revision_count + nonselected_source_event_count`, `selected_source_revision_count = assigned_source_revision_count + out_of_plan_source_revision_count`, and `output_root_count <= output_revision_count`. Out-of-plan and empty counts are mechanical evidence only, not coverage findings. The current `MarketBundleManifest` is not modified to carry the full aggregation report. `BarAggregationManifest` remains separately content-addressed Builder evidence linked to source and output Bundle refs.

`BarAggregationResult` contains only generated Bar Events, the exact final G12C `output_manifest`, and the aggregation manifest. Callers can reconstruct the validated output tuple as `source_events + result.generated_events`.

## Atomic failures and precedence

Failure codes are exactly:

1. `invalid_input`;
2. `source_bundle_mismatch`;
3. `definition_bucket_plan_mismatch`;
4. `source_stream_mismatch`;
5. `source_coverage_unaligned`;
6. `source_event_invalid`;
7. `revision_chain_invalid`;
8. `output_causality_invalid`;
9. `output_validation_failed`.

Precedence is global in that order, then earliest original source input position where applicable. `definition_bucket_plan_mismatch` means the plan's bound definition identity differs from the supplied definition. `source_coverage_unaligned` includes unequal source/plan coverage or a supplied span outside source coverage. Ambiguous economic ties are `source_event_invalid`; no bucket assignment is valid out-of-plan evidence; final G12C rejection is `output_validation_failed`.

`BarAggregationOutcome` is XOR result/failure. Failure contains only code plus optional safe `stream_key`, zero-based original `input_position`, or `interval_hash`. No failure exposes partial Bars/manifests, source payloads, raw values, exception text, paths, host/process identity, or credentials.

## Qualification boundary and non-goals

Every G12G result is development-only:

```text
decision_grade_eligible = false
deployment_authorized = false
```

G12G explicitly does not provide:

- bucket derivation or exchange calendar, timezone, DST, holiday, Session, TradingDate, included-phase, or interval-completeness authority;
- provider acquisition, network access, schema adapter, or source completeness;
- stable provider economic tie ordering beyond fail-closed v1 constraints;
- volume, quantity, VWAP, turnover, forward fill, carry close, or synthetic empty Bars;
- arbitrary resampling, calendar DSL, callback, registry, DataFrame, Pandas/Polars/Arrow;
- multi-source/provider joins or timestamp-moving/cancellation revisions;
- bucket-plan completeness, revision-set completeness, price-purpose coverage, availability coverage, stale policy, or gap classification;
- G12D sidecars or mutation of passed Market Data schemas;
- Runtime aggregation, Strategy resampling, Trading Kernel dependency, live use, decision grade, or deployment authorization.

G12I owns coverage/classification and proves whether the supplied bucket plan, revision set, price evidence, and availability evidence are complete. G12L/G12M own real-provider and real-market qualification. Runtime remains branchless and consumes only canonical `bar` Events plus a matching G11D `BarDefinitionRef`.

## Frozen evidence required before PASSED

The `canonical-bar-aggregation-v1` golden must freeze:

- caller-supplied A-share morning/afternoon buckets with no lunch crossing;
- one caller-supplied Session bucket with disjoint lunch spans;
- explicit UTC 24×7 day and synthetic night Session buckets with next-TradingDate ownership;
- exact SessionId, TradingDate, half-open spans, boundaries, and truncated final interval;
- empty omission and mechanical out-of-plan counts;
- integer OHLC, exact scale, null volume, source hashes, and ambiguous-tie rejection;
- root state at close, pre-close correction collapse, late root, post-close correction, same-UTC grouping, retained old revisions, and exact availability/phase/sequence;
- source, definition, bucket-plan, spec/code, Event, stream, manifest, and Bundle identity sensitivity;
- changed definition to changed G11D-compatible ref, Bar stream hash, and Bundle ref;
- exact G11D consumption of `event_type="bar"` without Runtime resampling;
- every failure code, precedence, and atomicity;
- repeat canonical bytes/hashes, architecture/import report, mypy, lock check, G12B/C and G11D regressions, full suite, JUnit/artifact hashes, and immutable implementation commit.

Passing those checks is future Acceptance work. This readiness freeze alone must not change the G12G Acceptance Matrix status from `DRAFT`.
