---
id: MRMD-01
readiness: PASSED
gate_status: PASSED
owner: backtest-runtime preparation and observation integration
produces:
  - MultiResolutionMarketDataBindings@1
  - strict visible G12G signal-Bar verification
consumes:
  - G11B point-in-time observation causality
  - G11D named Bar windows
  - G11E DecisionSchedule and LookbackRequirement
  - canonical G12G v1 Bar Event payloads
  - one selected MarketBundleReader
  - selected Profile-owned execution and valuation inputs
depends_on:
  contract: [G11B, G11D, G11E, G12G, BT-GAP-02B, BT-GAP-02C, PERF-OBS-01]
  evidence: [accepted G12G fixtures]
  write_conflict: [execution-input bundle, acceptance registry]
fan_out: [PREP-COVERAGE-01, G12I, provider-specific multi-resolution slices]
---

# MRMD-01 Multi-resolution Market Data v1

## Status

`PASSED`. F1 core is frozen at immutable source
`85eac498b70d98dccce524f7ec30198456983dbf`; F2 one-Bundle/Profile identity,
hydration, replay, and Runtime fan-in is frozen through `PREP-COVERAGE-01` source
`8fc4fde588ef6f215576e8a3cf4de17acbdce8da`. All PASSED v1 bytes, hashes,
interfaces, and failure precedence remain immutable.

Architecture decision: `docs/adr/0002-no-global-backtest-frequency.md`.

## Delivery slices

MRMD-01 is delivered in two explicit slices. The Gate remains `READY`, not
`PASSED`, until both slices and the full acceptance contract complete.

### F1 — core bindings and visible verification

F1 owns only:

- the four off-root canonical binding values;
- binding construction and `DecisionSchedule` signal exact-cover validation;
- exact reconstruction of the selected G11B point-in-time result followed by
  strict visible G12G v1 Bar consumer verification;
- the private bounded recorder and the three F1 observations:
  `CONSTRUCT_BINDINGS`, `VALIDATE_BINDINGS`, and `VERIFY_SIGNAL_BAR`.

G11B observation lineage keys remain opaque caller-supplied authority. F1 neither
derives nor verifies a new observation-key preimage.

F2 acceptance closure is inherited from `PREP-COVERAGE-01`: slices 1–3 PASSED,
2031 full repository tests passed at final source, import boundaries passed for 117
files, and independent ordering/security/identity/repository reviews found no
blocker/high finding.

### F2 — PREP-COVERAGE integration

`PREP-COVERAGE-01` owns F2:

- one-Bundle and selected Profile execution/valuation validation;
- the remaining six observations: `LOOKUP_STREAMS`, `HYDRATE_INPUTS`,
  `VERIFY_REPLAY`, `PROJECT_POINT_IN_TIME`, `BUILD_WINDOW`, and
  `EVALUATE_LOOKBACK`;
- integration with the existing decision/execution/snapshot role-hash preimages;
- execution-input bundle v3, decode/hydration, and replay verification;
- cross-requirement atomic failure precedence.

F1 does not implement or partially scaffold any F2 responsibility.

F1 acceptance closure:

- RED: `5ef0e375c83b5ef317dab8fe28ac9d881e271bb8`;
- implementation: `c5177260e118e7dd314fb08f4d9d79e96c1f22e3`;
- hardening/final source: `85eac498b70d98dccce524f7ec30198456983dbf`;
- focused source validation: 36 passed;
- compatibility validation: 117 passed;
- full repository: 1899 passed;
- clean detached acceptance: 119 passed;
- import boundaries: 116 files passed;
- LSP/lens: clean;
- independent standards/spec/minimality re-reviews: no blocker/high findings;
- MRMD fixture: `sha256:64b41061f8ab0707fe7aa5a23f2f73039fc5730a3da53709b610b4d2dac4e18c`.

## Outcome

Unify how one run binds four independent market-data concerns without creating a
global Backtest frequency:

1. Strategy signal observations;
2. finite decision cadence;
3. execution-simulation data;
4. valuation data.

A run may use 1-minute signal Bars, explicit minute-close decisions, 5-second
execution data, and a separate valuation stream. Runtime and Strategy code never
resample.

MRMD is a resolved preparation output, not a new caller request. Preparation
consumes the existing `DecisionSchedule`, selected Profile-owned execution and
valuation inputs, and one selected Bundle manifest/Reader. No caller frequency,
default stream, selector registry, resolver factory, or provider framework is
introduced.

## Ownership

| Concern | Owner | Existing authority reused |
| --- | --- | --- |
| Signal query and minimum lookback | Strategy/Runtime | `LookbackRequirement` |
| Decision instants | Strategy/Runtime | `DecisionSchedule` |
| Bar construction and geometry | Builder | G12G `BarDefinition` and `BarBucketPlan` |
| Execution stream selection | Simulation Profile | existing execution composition |
| Valuation stream and staleness | Profile/Kernel semantics | existing mark and snapshot inputs |
| Exact run-scoped role bindings | Runtime preparation | MRMD bindings |
| Source completeness and qualification | G12I/G12L/G12M | not MRMD-01 |
| Performance observations | outer orchestration | `PERF-OBS-01` |

Runtime does not import Builder. Builder does not import Runtime or Trading Kernel.

## Existing gap

G12G Bar Events carry `bar_definition_key/version/hash`, `bucket_plan_hash`,
`aggregation_input_hash`, and source lineage. Existing G11D windows validate Event
type, stream, Instrument, capability, ordering, and causality, but do not compare
those payload identities with `BarDefinitionRef`.

MRMD adds a new opt-in verified signal path after G11B visibility selection. It
does not change G11D v1 or reinterpret legacy fixtures.

## Canonical binding values

The new module owns four frozen/slotted schema-v1 values. Constructors rebuild
nested accepted values, canonical-sort tuples, reject duplicate identities, expose
`to_canonical_dict()`, and derive non-recursive hashes.

### `SignalBarBinding`

Exact fields:

1. `requirement_hash: str`;
2. `stream_key: str`;
3. `price_purpose: PricePurpose`;
4. `aggregation_input_hash: str`.

The requirement hash must identify exactly one member of the selected
`DecisionSchedule.requirements`. Signal bindings exact-cover that tuple with no
missing, duplicate, or extra requirement.

### `ExecutionDataBinding`

Exact fields:

1. `profile_binding_key: str`;
2. `stream_key: str`.

The selected Simulation Profile owns the binding key and execution semantics.
MRMD does not add an execution Event schema or infer one from a signal stream.

### `ValuationDataBinding`

Exact fields:

1. `instrument_id: InstrumentId`;
2. `stream_key: str`.

The selected snapshot/mark inputs continue to own `PricePurpose.VALUATION` and
stale-policy identity. MRMD binds only which immutable stream supplies the mark;
it does not duplicate those existing semantic hashes.

### `MultiResolutionMarketDataBindings`

Exact fields:

1. `signal_bindings: tuple[SignalBarBinding, ...]`;
2. `execution_bindings: tuple[ExecutionDataBinding, ...]`;
3. `valuation_bindings: tuple[ValuationDataBinding, ...]`.

`bindings_hash=canonical_sha256(canonical body)`.

The value contains no Bundle ref, profile digest, schedule, snapshot hash, grade,
deployment flag, global resolution, or duplicated semantic authority. Those values
already belong to the request, selected environment, Decision inputs, Execution
inputs, Snapshot inputs, and result-grade contracts.

Explicit cross-role stream reuse is allowed when every role independently names
and validates the same stream. Implicit fallback is forbidden.

## One-Bundle invariant

This invariant is implemented and accepted in F2 by `PREP-COVERAGE-01`; F1 only
checks the exact selected `MarketStreamManifest` supplied to visible verification.
MRMD-01 v1 is one-Bundle only:

- the request, resolved environment, Timeline Reader, and hydration Reader use one
  exact `MarketBundleRef`;
- every binding `stream_key` resolves to exactly one member of that manifest;
- the resolved manifest Event type/capability must satisfy the owning schedule or
  Profile contract;
- G12G source Bundles named by Event lineage are provenance only and never a second
  Runtime Reader.

`MarketStreamManifest` values are not copied into every binding. The selected
Bundle manifest is the single stream-content authority.

## Visible signal-Bar verification

After existing G11B point-in-time selection, a visible signal Event is accepted
only when:

- it matches the existing `ObservationQuery` context;
- `event_type == "bar"`;
- `source_key == "canonical-bar-aggregation-v1"`;
- capability is exactly `price_bars@1` and equals the selected stream manifest and
  requirement;
- payload has exactly the frozen G12G v1 fields:
  `schema_version`, `bar_definition_key`, `bar_definition_version`,
  `bar_definition_hash`, `source_stream_hash`, `bucket_plan_hash`,
  `aggregation_spec_hash`, `aggregation_code_hash`, `aggregation_input_hash`,
  `bucket_hash`, `session_id`, `trading_date`, `included_spans`, `interval_start`,
  `interval_end_exclusive`, `price_purpose`, `price_scale`, `open`, `high`, `low`,
  `close`, `volume`, `observation_count`, `source_event_hashes`, and
  `selected_source_set_hash`;
- payload schema version is exact integer `1`;
- payload `aggregation_spec_hash` is
  `sha256:324439214b2cb2fa64300c470a65e322de3c3dd7056381a73672db00677dbccb`;
- payload `bar_definition_key/version/hash` equals the requirement's exact
  `BarDefinitionRef`;
- payload `price_purpose` equals the signal binding and `price_scale` is a
  non-negative exact integer;
- payload `aggregation_input_hash` equals the signal binding;
- `event.source_hash` equals that aggregation input hash;
- every hash field and source Event hash is canonical SHA-256;
- `session_id`, `trading_date`, every included span, and both interval bounds have
  exact accepted canonical field sets and primitive types; spans are nonempty,
  ordered, and disjoint; the first starts at `interval_start`, the final ends at
  `interval_end_exclusive`, and gaps between spans are allowed;
- OHLC objects have exact `{units, scale}` integer fields, use the declared scale,
  and satisfy `low <= open,close <= high`; `volume is None`;
- `observation_count` is a positive exact integer and source Event hashes are a
  nonempty canonical list.

Runtime validates the frozen consumer grammar but does not recompute aggregation,
revision selection, or Builder manifests.

G11B observation lineage keys remain opaque and are not re-derived or interpreted
by MRMD F1. Existing G11B owns revision selection and its caller-supplied keys,
G11D owns bounded windows, and G11E owns lookback eligibility and Strategy
invocation. Malformed future Events are not eagerly scanned and cannot alter
earlier decisions.

## Aggregation scope

MRMD-01 accepts only already materialized existing G12G v1 lineage:

```text
synthetic_price_point.v1 → explicit G12G Bar buckets
```

Every requested output stream is built before the run. G12G v1 does not accept Bar
input, so MRMD cannot upsample or perform Bar-to-Bar conversion. Nominal strings or
durations such as `5s < 1m` are not resolution authority; explicit bucket geometry
is.

Bar-to-Bar transformation is outside this plan and requires a separately reviewed
Builder contract if a concrete need appears.

## Identity and migration

The following integration belongs to F2 and is not implemented by F1. MRMD-01
reuses existing identity fields instead of adding another semantic root:

1. preserve `BacktestRequest@1` and `ExecutionCaseSemanticSpec@1` bytes;
2. add `backtest_execution_input_bundle@3` embedding the complete canonical MRMD
   bindings;
3. include signal bindings in the existing `decision_inputs_hash` preimage;
4. include execution bindings in the existing `execution_inputs_hash` preimage;
5. include valuation bindings in the existing `snapshot_inputs_hash` preimage;
6. require decode/hydration to reconstruct the bindings and recompute all three
   existing hashes before Timeline or Engine construction;
7. rely on the existing `execution_case_semantic_hash` path so any role change
   alters request hash and Semantic Run ID;
8. bind the same values through deterministic rebuild evidence and repository
   replay;
9. keep every legacy request/bundle/spec/result/evidence fixture byte-exact;
10. never infer legacy role bindings from stream names.

`PREP-COVERAGE-01` owns construction and structured preflight failures but cannot
change these identity preimages or introduce a second Artifact lookup.

## Failure boundary

Constructors use exact `TypeError`/`ValueError`. Preparation failure codes and
precedence belong to `PREP-COVERAGE-01`.

Within one F1 visible signal verification call, precedence is:

1. malformed consumed G12G payload;
2. BarDefinition key/version/hash mismatch;
3. aggregation-input/source-hash mismatch.

Reader/Event order breaks F1 ties. F2 owns atomic precedence across schedule
requirements and preparation checks. No partial binding set or verified window
escapes failure. Normal lookback shortfall
remains the existing successful-but-ineligible G11E result.

## Performance observation coverage

F1 exposes only:

- binding construction;
- schedule signal exact-cover validation;
- visible signal payload verification.

F2 exposes the remaining outer-orchestration observation points for Bundle/stream
lookup, point-in-time projection, named-window construction, lookback evaluation,
and execution-input hydration/replay verification. One-Bundle and Profile-owned
execution/valuation checks are also F2 preparation authority.

The mechanism, fixed schema, boundedness, privacy rules, and failure isolation are
owned only by `PERF-OBS-01`. Telemetry on/off/failure/overflow must leave all
canonical bytes, hashes, IDs, control flow, results, evidence, and analysis equal.

## RED matrix

| Slice | Required evidence |
| --- | --- |
| value contract | canonical order/hash, exact-type and constructor-bypass rejection, no global resolution |
| signal exact cover | missing/duplicate/extra schedule binding rejected |
| role separation | 1-minute signal, independent decisions, 5-second execution, and valuation binding coexist |
| explicit reuse | a shared stream is accepted only when each role explicitly binds and independently validates it |
| signal authority | wrong source/schema/spec/definition/aggregation/bucket identity rejected |
| point-in-time | malformed future Event cannot affect an earlier decision; visible malformed Event fails |
| one-Bundle | foreign manifest/Reader or missing/ambiguous stream rejected |
| identity | role-only changes alter existing decision/execution/snapshot hashes, request hash, and Semantic Run ID |
| hydration/replay | embedded binding substitution, wrong role hash, wrong Bundle, and tamper fail before Engine execution |
| compatibility | all PASSED G11B/D/E, G12G, BT-GAP-02B/C bytes/hashes unchanged |
| observability | telemetry on/off/failure/overflow produces identical canonical outputs |
| architecture | no Runtime↔Builder/Kernel violation and no Provider/Registry/Factory/DSL/resampler framework |

## Acceptance

Implementation acceptance must run focused MRMD, G11B/D/E, G12G,
execution-input-v3, request-identity, evidence-replay, architecture, and telemetry
invariance tests, followed by:

```bash
uv run --locked pytest -q
uv run --locked python tools/architecture/check_import_boundaries.py \
  --root . --policy architecture/import-boundaries.toml \
  --report build/acceptance/mrmd-01-import-boundaries.json
uv lock --check
git diff --check
```

Final acceptance requires clean detached-worktree replay and independent review
`NONE`.

## Explicit non-goals

No global frequency, caller requirement DTO, Runtime/Strategy resampling,
Bar-to-Bar compiler, pandas/DataFrame interface, forward fill, interpolation,
synthetic Bars, provider/calendar discovery, second data/profile registry,
factory/plugin/DSL, telemetry exporter, Runtime import of Builder, Builder import
of Runtime/Kernel, G12I completeness, G12L qualification, decision-grade claim,
live use, or deployment authorization.
