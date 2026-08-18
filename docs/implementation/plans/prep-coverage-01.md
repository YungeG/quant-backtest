---
id: PREP-COVERAGE-01
readiness: READY
gate_status: READY
owner: backtest-runtime preparation/preflight
produces:
  - one-Bundle MRMD preparation and replay closure
  - backtest_execution_input_bundle@3
  - MRMD-01/PERF-OBS-01 F2 integration
consumes:
  - MRMD-01 F1 bindings and visible-Bar verifier
  - PERF-OBS-01 F1 recorder
  - G11B/G11D/G11E observation, window, and eligibility contracts
  - G12E MarketBundleReader
  - BT-GAP-02B/02C execution-input and composition contracts
depends_on:
  contract: [MRMD-01, PERF-OBS-01, G11B, G11D, G11E, G12E, BT-GAP-02B, BT-GAP-02C]
  evidence: [MRMD F1 accepted fixtures, frozen v1/v2 execution-input fixtures]
  write_conflict: [execution_inputs.py, composition.py, facade.py, runner.py, acceptance-matrix.md]
fan_in: [MRMD-01, PERF-OBS-01]
---

# PREP-COVERAGE-01 Runtime Multi-resolution Preparation v1

## Status

`READY`. The F2 contract, Acceptance Matrix readiness card, and independent
architecture/oracle/security reviews are complete. Implementation is authorized
only as the three test-first delivery slices below.

## Outcome

Before cache acceptance, Timeline opening, case sealing, Attempt creation, or Engine
execution, prove atomically that:

- one exact MarketBundle ref/manifest/Reader supplies every market-data role;
- signal bindings and opaque G11B lineage replay the DecisionSchedule;
- execution and valuation data are explicitly bound to the resolved case/Profile;
- G11E eligibility exact-controls which case decision cycles may exist;
- signal, execution, and valuation changes enter their existing semantic hash roles;
- execution-input bundle v3 can be decoded and replayed from one Artifact read;
- no partial preparation, window, eligibility, Timeline, case, Attempt, cache hit,
  or evidence escapes a structural failure.

A normal lookback shortfall is accepted G11E `INELIGIBLE`, not a preparation
failure, and cannot coexist with an executable active decision cycle.

## Placement and ownership

Add one off-root deep module:

`crypto_quant_backtest.multi_resolution_preparation`

It may import Domain, Market Data, Runtime engine value types, MRMD F1, PERF F1,
and G11B/D/E values. It must not import Builder, Trading Kernel, concrete Profiles,
facade, runner, repository, or a second catalog.

| Existing module | F2 responsibility |
| --- | --- |
| `multi_resolution_market_data.py` | unchanged F1 values/verifier |
| `performance_observations.py` | unchanged recorder/taxonomy |
| new preparation module | pure one-Bundle/role/lineage/window/cycle closure |
| `composition.py` | private v3 role-preimage and compose helpers |
| `execution_inputs.py` | sole catalog; v3 materialize/decode/hydrate |
| `facade.py` | private v3 read-once → resolve-once → hydrate continuation |
| `runner.py` | private v3 contract continuation sharing the existing execute body |
| `resolution.py` | unchanged sole Profile registry/resolver |
| `cash_development_provider.py` | remains v2; its marks are not one-Bundle MRMD evidence |

No public/root signature, `ResolvedExecutionCase` field, request field, Profile
registration, or legacy behavior changes are authorized.

## Canonical preparation values

### `SignalObservationLineageBinding`

Exact fields:

1. `requirement_hash: str`;
2. `event_id: str`;
3. `event_hash: str`;
4. `observation_key: str`.

The observation key is opaque caller-owned G11B authority; F2 never derives it.
Rows reference Reader Events but copy no Event bytes. Rows are canonical-ordered by
requirement hash, Event ID/hash, and observation key. Duplicate
`(requirement_hash, event_id)` or inconsistent Event hashes fail.

### `MultiResolutionMarketDataPreparation`

Exact fields:

1. `decision_schedule: DecisionSchedule`;
2. `bindings: MultiResolutionMarketDataBindings`;
3. `signal_lineages: tuple[SignalObservationLineageBinding, ...]`.

Derived identities:

- `decision_schedule_hash`;
- `signal_lineage_hash`;
- `preparation_hash` over the complete canonical body.

It contains no Bundle ref, manifest copy, Event payload, Reader, Profile registry,
performance observation, path, callback, cache, or second Artifact ref.

## Process-local case authority

Preflight cannot consume `ResolvedExecutionCase` because that value requires an
already-open Timeline. Instead add one noncanonical exact Runtime view:

```text
MarketDataCaseAuthority = {
  decision_cycles: tuple[ResolvedDecisionCycle, ...],
  bar_executions: tuple[ResolvedBarExecution, ...],
  execution_model: NextEligibleBarOpenModel,
  snapshot_plan: SnapshotProjectionPlan,
  target_stream: PrecomputedTargetStream,
}
```

The decoded `_ExecutionCasePlan` creates this view before Timeline construction.
It has no canonical serializer/hash and is not persisted independently.

## Process-local preflight interface

```text
prepare_multi_resolution_market_data_v1(
  *,
  expected_bundle_ref: MarketBundleRef,
  reader: MarketBundleReader,
  schedule: DecisionSchedule,
  signal_binding_candidates: tuple[SignalBarBinding, ...],
  execution_binding_candidates: tuple[ExecutionDataBinding, ...],
  valuation_binding_candidates: tuple[ValuationDataBinding, ...],
  signal_lineages: tuple[SignalObservationLineageBinding, ...],
  case_authority: MarketDataCaseAuthority,
  resolved_request: ResolvedBacktestRequest,
  recorder: BoundedPerformanceRecorder | None = None,
) -> MarketDataPreparationOutcome
```

Reader validation is structural through `MarketBundleReader`; exact-type checks
apply to canonical value objects.

Success contains one process-local noncanonical prepared value with:

- `preparation: MultiResolutionMarketDataPreparation`;
- schedule-entry-ordered `eligibilities: tuple[WarmupEligibility, ...]`;
- retained immutable `verified_reader: InMemoryMarketBundleReader` built from the
  captured exact ref/manifest/Event tuples.

### Failure and outcome schema

`MarketDataPreparationFailure` exact fields:

1. `code: MarketDataPreparationFailureCode`;
2. `role_position: int | None`;
3. `schedule_entry_position: int | None`;
4. `requirement_position: int | None`;
5. `event_position: int | None`.

It exposes `failure_hash`. It contains no paths, payloads, stream keys, IDs,
provider text, exceptions, or arbitrary subjects.

`MarketDataPreparationOutcome` is exactly-one `prepared | failure`; failure returns
no partial bindings/windows/eligibilities.

Schema-3 decode/hydration uses a separate private
`ExecutionInputsHydrationFailureV3` with the same four optional positional integers
plus one closed v3 failure enum. It has no free-form `message`. The v3 facade exposes
only the stable enum value (for example,
`execution input hydration failed: prepared_market_data_replay_mismatch`) and never
formats `str(error)`. V1/v2 retain their existing failure value and behavior.

## Reader and one-Bundle integrity

Require:

```text
reader.bundle_ref
== MarketBundleRef.from_manifest(reader.manifest)
== expected_bundle_ref
== resolved_request selected Bundle ref
```

For every manifest stream (including target/timeline and all role streams):

1. resolve exactly one matching `MarketStreamManifest`;
2. open a cursor and rebuild its exact ref/manifest/position/batch values;
3. read until exhausted, requiring every non-exhausted read to return at least one
   Event, every successor cursor to retain the same ref and manifest, advance
   strictly by the returned Event count, and never exceed manifest count;
4. reconstruct every MarketEvent authority;
5. require total Event count equals the manifest count;
6. require `canonical_sha256(tuple(events)) == stream_manifest.content_hash`;
7. if resume is used, require the resumed cursor retains ref/manifest/position and
   only changes the approved batch size;
8. construct an existing `InMemoryMarketBundleReader` from the captured exact ref,
   manifest, and complete reconstructed stream tuples; use this retained immutable
   Reader for all preparation, Timeline, hydration, and execution consumption.

The original structural Reader is not used after capture. Reader mutation, cursor
substitution, zero-progress reads, and post-preflight content substitution therefore
fail closed.

## Signal lineage scope and replay

For each signal requirement, lineage rows exact-cover all Reader Events that:

- belong to the bound signal stream;
- match the requirement Instrument, capability, and Bar event context;
- have `available_time` in
  `[schedule.window.data_start, schedule.window.end_exclusive)`.

Events outside that interval are excluded. If an in-window revision requires a
supersession parent outside the interval, preparation fails
`SIGNAL_LINEAGE_MISMATCH`; pre-window ancestors are never fed into G11B. One Event may be
referenced by multiple requirements, but its Event ID must map to one consistent
Event hash. No observation-key derivation is permitted.

Per schedule entry, normal G11B visibility still uses the full
`SimulationInstant <= decision_instant`; F1 payload verification runs only after
visibility selection, so malformed future Bars cannot alter earlier decisions.

The schedule matrix is processed entry-order then requirement-order:

1. rebuild `RevisionedObservationRecord`s from Reader Events and opaque lineage;
2. run `PointInTimeObservationView.query()`;
3. run F1 `verify_visible_signal_bars()`;
4. build exact `NamedBarWindowQuery` and `NamedBarWindowView.window()`;
5. after all windows for the entry succeed, run `DecisionSchedule.eligibility()`.

## Eligibility-to-case-cycle enforcement

G11E is execution authority, not replay-only audit. Map existing identities:

```text
(entry.decision_instant.instant, entry.segment)
↔
(cycle.schedule.decision_time, cycle.schedule.segment)
```

Rules:

- every `strategy_invocation_eligible=true` entry maps to exactly one cycle;
- every ineligible entry maps to no cycle;
- every case cycle maps to exactly one eligible entry;
- a mapped warmup cycle has empty allocations and admissions;
- an active cycle additionally requires `trading_side_effects_authorized=true`;
- same-UTC/distinct-phase entries that cannot map uniquely fail closed;
- retained target Event IDs exact-cover all mapped cycle schedule entries, including
  warmup, and no others;
- each cycle's target batch is validated through the existing
  `PrecomputedTargetStreamAdapter` contract using that cycle's schedule and segment,
  preserving accepted multi-sleeve Event capability/type/payload/time/source-sequence
  behavior;
- every target Event has `event_time == available_time ==
  cycle.schedule.decision_time`, and its full timeline instant is at or after the
  matched G11E decision instant and strictly before the next DecisionSchedule entry
  when one exists; distinct Events retain unique ordering keys/source sequences;
- ineligible entries cannot coexist with cycles, targets, allocations, admissions,
  orders, or other side effects.

No new mapping DTO is persisted; schedule/eligibility and the existing decoded case
cycles are already in the v3 decision preimage.

## Execution role validation

Authoritative success requires the exact resolved request.

- selected Simulation Profile `EXECUTION_MODEL` component ref equals the decoded
  execution model component ref;
- each `ExecutionDataBinding.profile_binding_key` equals that component key;
- the bound stream manifest satisfies the execution model's required capability;
- v1 requires exactly the execution bindings modeled by that concrete model and
  rejects extras;
- every `ResolvedBarExecution.event_id` resolves in an explicitly bound execution
  stream;
- the exact Reader Event ID/hash/context matches
  `BarLiquidityEvidence.market_event_id/market_event_hash`, execution evaluated
  time, revision/time context, and existing execution market-state evidence.

F2 does not interpret execution prices or duplicate slippage/liquidity economics.

## Valuation role validation

F2 v1 admits only canonical G12G `price_bars@1` valuation Bars for one-Bundle source
identity replay. For every `SnapshotProjectionPlan.resolved_mark`:

- one `ValuationDataBinding` exact-matches Instrument and stream;
- the Reader Event is a strict valid G12G Bar with
  `price_purpose == VALUATION`;
- source Event ID, revision, stream, and Instrument match the mark;
- Event time equals the Bar `interval_start`;
- mark availability equals Event availability;
- exact `available_at_instant`, when present, equals Event timeline instant.

`ResolvedMark` and its selected Profile remain the authority for mark price,
observed/resolved time, stale policy, and economic projection. F2 does not derive a
mark from Bar close or require mark observed time to equal Event time/end. Economic
price reconstruction needs a separately reviewed Profile-owned projection contract.
Provider-specific or non-Bar valuation Events likewise need a later concrete
version. The current cash development provider remains v2.

A repeated stream key across roles is valid only when every role explicitly binds
and independently validates it; no fallback exists.

## Identity integration

Keep `BacktestRequest@1` and `ExecutionCaseSemanticSpec@1` shapes unchanged. For v3
only, recompute existing semantic bodies with domain-separated role preimages:

```text
decision_inputs_hash = sha256({
  type: "execution_case_decision_inputs_mrmd_v1",
  base: existing decision semantic body,
  decision_schedule,
  signal_bindings,
  signal_lineages,
})

execution_inputs_hash = sha256({
  type: "execution_case_execution_inputs_mrmd_v1",
  base: existing execution semantic body,
  execution_bindings,
})

snapshot_inputs_hash = sha256({
  type: "execution_case_snapshot_inputs_mrmd_v1",
  base: existing snapshot semantic body,
  valuation_bindings,
})
```

Use full role values, not aggregate `bindings_hash` or prior role hashes. A role-only
change first alters only its assigned role hash, then propagates through spec hash →
`BacktestRequest.execution_case_semantic_hash` → request hash → Semantic Run ID and
case/attempt identities.

Do not add a semantic adjunct to `ResolvedExecutionCase`. Private v3 compose and
Runner continuations receive the retained preparation in memory. Legacy public
composer/runner methods remain unchanged.

## Execution-input bundle v3

Add one registration to the existing private execution-input catalog:

```text
backtest_execution_input_bundle@3 =
  exact v2 field set
  + market_data_preparation: MultiResolutionMarketDataPreparation@1
```

No second Bundle ref, manifest, Reader, Event bytes, Profile registry, performance
data, cache, path, or Artifact ref is added. `BacktestExecutionRequest` keeps its
three fields and accepts schema 3 only with the matching v3 ref.

V3 materialize/decode functions remain private. V1/v2 bytes, signatures, catalogs,
and branches remain unchanged.

## V3 ordering and shared execution body

For schema 3 only:

1. read and decode the execution-input Artifact once;
2. perform existing request/build/Reader/ref/required-stream/target-stream/
   target-digest checks from the retained decoded value;
3. resolve Profiles once using the captured immutable manifest;
4. run full preparation, eligibility-cycle closure, and three role-hash replay;
5. open Timeline from the retained immutable verified Reader and compose the sealed
   case;
6. run a private v3 contract continuation that recomputes the same semantic spec
   before cache lookup/return, Attempt evidence, or Engine;
7. delegate v2 and v3 after contract verification to one shared internal
   execute/cache/Engine body;
8. retry uses the same retained preparation and shared internal path.

V1/v2 facade/hydration/composition/runner behavior and precedence remain exact.
No partial value, cache hit, Attempt, or evidence is accepted before v3 replay.

## Failure precedence

Exact-type constructor failures remain `TypeError`/`ValueError`.

For valid preflight input, first-applicable order is:

1. `BUNDLE_READER_MISMATCH`;
2. `SIGNAL_BINDING_MISMATCH`;
3. `STREAM_MANIFEST_MISMATCH`;
4. `EXECUTION_PROFILE_BINDING_MISMATCH`;
5. `VALUATION_PROFILE_BINDING_MISMATCH`;
6. `SIGNAL_LINEAGE_MISMATCH`;
7. `POINT_IN_TIME_FAILURE`;
8. `SIGNAL_BAR_FAILURE`;
9. `WINDOW_CONSTRUCTION_FAILURE`;
10. `DECISION_CYCLE_ELIGIBILITY_MISMATCH`.

Evaluate each stage over its complete matrix before selecting one failure. Total tie
order is stage number, role order `SIGNAL → EXECUTION → VALUATION`, role binding
canonical position, schedule entry position, requirement position, lineage/Event
position, then F1's local malformed → definition → aggregation-lineage order.

V3 hydration preserves every v1/v2 transport/read/decode/request/build/target
failure first, then adds:

1. `PREPARED_MARKET_DATA_BINDING_MISMATCH`;
2. `PREPARED_MARKET_DATA_REPLAY_MISMATCH`;
3. existing `EXECUTION_CASE_SEMANTIC_HASH_MISMATCH`.

All occur before cache acceptance, Timeline, Attempt, or Engine.

V3 failure conversion uses stable enums and positional integers only. It never
returns `str(error)`, exception type/text, paths, URIs, provider messages,
credentials, payloads, or arbitrary subjects. Secret-sentinel tests are required.

## PERF-OBS F2

Instrument only the six direct new seams:

| Operation | Authoritative seam |
| --- | --- |
| `LOOKUP_STREAMS` | one-manifest role-stream lookup |
| `HYDRATE_INPUTS` | v3 decode/reconstruction |
| `VERIFY_REPLAY` | Reader/role-hash/spec replay |
| `PROJECT_POINT_IN_TIME` | one G11B query |
| `BUILD_WINDOW` | one verified G11D window |
| `EVALUATE_LOOKBACK` | one G11E eligibility |

Use F1's concrete best-effort primitive. Recorder `None` performs no clock work;
clock/count/recorder/saturation failure cannot alter authority or control flow.

## Delivery slices

1. **RED + pure preflight:** values, Reader integrity, one-Bundle/role checks,
   lineage replay, atomic G11B/F1/G11D/G11E/cycle closure, six PERF operations.
2. **V3 identity closure:** role preimages, sole catalog v3,
   materialize/decode/hydrate, role-only identity proofs, legacy byte/signature locks.
3. **Runtime fan-in:** one-read/one-resolve facade, pre-cache/pre-Timeline replay,
   shared Runner execution/retry body, repository evidence, full acceptance.

## RED matrix

| Area | Required proof |
| --- | --- |
| values | exact fields/order/hash, duplicate/conflict and constructor-bypass rejection |
| Reader | ref/manifest/cursor substitution, zero progress, position/count/content-hash mismatch, immutable retained-reader parity |
| lineage | exact bounded revision-chain cover, omitted/forged/conflicting row, no key derivation |
| signal | missing/extra/wrong binding; future malformed Bar noninterference; F1 precedence |
| execution | component/capability/Event ID/hash/context mismatch and no fallback |
| valuation | strict G12G valuation Bar source ID/revision/stream/Instrument/availability mismatch and no fallback; no price projection inference |
| reuse | same stream succeeds only when every role explicitly binds and validates it |
| eligibility | eligible warmup maps one side-effect-free cycle/target; active cycles require trading authorization; ineligible entries map none; target timeline mismatch fails |
| atomicity | simultaneous failures select total positional winner and return no partial output |
| identity | role-only changes alter only assigned role hash then request/run identity |
| v3 | exact fields, one catalog, round-trip, tamper/replay rejection before cache/Timeline/Engine |
| facade/runner | one Artifact read, one Profile resolution, shared execute/retry body, same preparation |
| PERF | six operations off/on/failing/saturating invariance and aggregate counts |
| secrecy | provider/path/token/exception sentinels absent from every v3 failure |
| compatibility | all v1/v2 request/spec/transport/bundle/provider/facade/runner/evidence bytes and signatures unchanged |
| architecture | no Builder/Kernel import, adjunct, second ref/catalog/registry/framework/resampler/callback/root export |

## Readiness card

The authoritative readiness card is in
`docs/implementation/acceptance-matrix.md`.

## Explicit non-goals

No global frequency, Runtime resampling, Bar synthesis, Builder import, Profile
stream registry, second Artifact/ref/catalog/Reader/repository/cache, generic
provider/adapter/factory/Protocol/DSL, copied Event/manifest payloads, semantic
adjunct, public composer/runner signature change, legacy auto-upgrade, cash-provider
v3 migration, persisted performance data, G12I/G12L/G12M qualification,
decision grade, live use, or deployment authorization.
