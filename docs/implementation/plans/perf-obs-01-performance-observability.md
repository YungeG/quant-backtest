---
id: PERF-OBS-01
readiness: READY
gate_status: READY
owner: backtest-runtime MRMD/PREP orchestration
produces:
  - private bounded MRMD/PREP performance recorder
consumes:
  - new MRMD/PREP outer orchestration operations
depends_on:
  contract: [G00]
  evidence: []
  write_conflict: [MRMD-01, PREP-COVERAGE-01]
fan_out: [MRMD-01, PREP-COVERAGE-01]
---

# PERF-OBS-01 MRMD/PREP Performance Observability v1

## Status

`READY`; F1 recorder core is `PASSED` at immutable source
`85eac498b70d98dccce524f7ec30198456983dbf`. The full Gate remains READY until
`PREP-COVERAGE-01` adds the remaining six operations at their authoritative seams.

Architecture decision:
`docs/adr/0003-performance-observations-are-non-authoritative.md`.

## Delivery slices

PERF-OBS-01 follows the MRMD delivery split while retaining one fixed Runtime-v1
taxonomy:

- F1 implements `CONSTRUCT_BINDINGS`, `VALIDATE_BINDINGS`, and
  `VERIFY_SIGNAL_BAR` only.
- `PREP-COVERAGE-01` F2 implements `LOOKUP_STREAMS`, `HYDRATE_INPUTS`,
  `VERIFY_REPLAY`, `PROJECT_POINT_IN_TIME`, `BUILD_WINDOW`, and
  `EVALUATE_LOOKBACK` when their authoritative seams are implemented.

The recorder accepts exact `PerformanceOperation` and `PerformanceOutcome` enum
values. F1 contains no generic observing callback/decorator graph; each of its
three new operations executes authority directly and then best-effort records
already-known aggregate measurements.

F1 acceptance closure:

- RED: `5ef0e375c83b5ef317dab8fe28ac9d881e271bb8`;
- implementation: `c5177260e118e7dd314fb08f4d9d79e96c1f22e3`;
- hardening/final source: `85eac498b70d98dccce524f7ec30198456983dbf`;
- focused source validation: 36 passed;
- full repository: 1899 passed;
- clean detached acceptance: 119 passed;
- import boundaries: 116 files passed;
- LSP/lens: clean;
- independent standards/spec/minimality re-reviews: no blocker/high findings;
- observation fixture: `sha256:1e61c04fabc6735ea0a8cce6ed257c1dd02012bbbd2167d9e4f82716d8777d13`.

## Outcome

Add enough bounded observation points to optimize the new MRMD/PREP path later,
without changing any authoritative behavior or creating a telemetry platform.

V1 observes only the new Runtime multi-resolution binding, preparation, hydration,
and visible-window orchestration. Existing Builder, Reader, Strategy, Engine,
repository, and analysis implementations remain unchanged. They receive local
observation plans only when a concrete future implementation touches their outer
seam.

## Runtime-private mechanism

Add one off-root production module:

`crypto_quant_backtest.performance_observations`

It owns exactly:

- `PerformanceOperation` enum;
- `PerformanceOutcome` enum;
- `_PerformanceObservation` frozen/slotted internal value;
- `BoundedPerformanceRecorder` concrete recorder.

Only `BoundedPerformanceRecorder` and the fixed `PerformanceOperation` /
`PerformanceOutcome` enums may be imported by the new MRMD/PREP Runtime
orchestration modules; nothing is exported from `crypto_quant_backtest` root.

The recorder:

- is caller-owned and optional (`None` means disabled);
- performs no I/O, logging, serialization, locking, threading, background work,
  retry, export, or global registration;
- stores one aggregate cell per valid `(operation, outcome)` pair;
- uses saturating exact integers capped at `2**63 - 1`;
- exposes a sorted in-memory snapshot for diagnostics/tests only;
- has no capacity/drop mechanism because the fixed taxonomy is naturally bounded
  to nineteen cells.

## Fixed taxonomy

`PerformanceOutcome` is exactly:

- `SUCCEEDED`;
- `FAILED`;
- `INELIGIBLE`.

`PerformanceOperation` is exactly:

1. `CONSTRUCT_BINDINGS`;
2. `VALIDATE_BINDINGS`;
3. `LOOKUP_STREAMS`;
4. `HYDRATE_INPUTS`;
5. `VERIFY_REPLAY`;
6. `PROJECT_POINT_IN_TIME`;
7. `VERIFY_SIGNAL_BAR`;
8. `BUILD_WINDOW`;
9. `EVALUATE_LOOKBACK`.

All operations allow `SUCCEEDED` and `FAILED`. Only `EVALUATE_LOOKBACK` permits
`INELIGIBLE`. Unknown combinations are invalid.

## Aggregate cell

`_PerformanceObservation` exact fields:

1. `operation: PerformanceOperation`;
2. `outcome: PerformanceOutcome`;
3. `call_count: int`;
4. `total_duration_ns: int`;
5. `input_count: int`;
6. `output_count: int`.

All numeric fields are exact non-`bool` integers in `[0, 2**63 - 1]`.

Input/output meanings are fixed:

| Operation | `input_count` | `output_count` |
| --- | --- | --- |
| `CONSTRUCT_BINDINGS` | caller role candidates | constructed bindings |
| `VALIDATE_BINDINGS` | bindings checked | valid bindings |
| `LOOKUP_STREAMS` | stream keys requested | exact manifest streams found |
| `HYDRATE_INPUTS` | embedded bindings decoded | hydrated bindings |
| `VERIFY_REPLAY` | replay bindings checked | verified replay bindings |
| `PROJECT_POINT_IN_TIME` | candidate Events | visible selected Events |
| `VERIFY_SIGNAL_BAR` | visible Bar Events | verified Bar Events |
| `BUILD_WINDOW` | eligible visible Events | returned window Events |
| `EVALUATE_LOOKBACK` | available Bar count | required Bar count satisfied, `0` or `1` |

One authoritative operation call emits at most one aggregate update. Event loops
contribute only counts; they never emit per-Event observations.

The observation value intentionally has no canonical/artifact serializer and is
never an accepted canonical input.

## Observation sequence and failure isolation

With recorder `None`, the authoritative operation runs with no clock reads,
counter extraction, observation construction, or recorder calls.

With a recorder:

1. best-effort read `perf_counter_ns()` before the operation;
2. run the authoritative operation exactly once;
3. preserve its returned value, structured failure, or raised `BaseException`;
4. best-effort read the end clock, calculate elapsed duration, and extract aggregate
   counts from the already-produced value/failure;
5. best-effort update the recorder once;
6. return the original value/failure or re-raise the original `BaseException`
   unchanged.

Every observation-side step—including both clock reads, subtraction, count
extraction, value construction, saturation, and recorder update—is isolated. An
observation failure is discarded and cannot mask, replace, suppress, delay, retry,
or reclassify authority.

Recorder state is never read by authoritative logic.

## Data restriction

The fixed schema has no named field or dynamic label for identifiers, hashes,
payloads, prices, paths, timestamps, or error text. Trusted owner wrappers may
populate only the documented aggregate counts.

Do not derive counts from secret or user text and encode them into numeric fields.
This is a recording-policy and code-review invariant; arbitrary integers cannot
provide information-theoretic privacy by themselves.

Forbidden observation sources include:

- run/attempt/Domain/Instrument/Event/revision/Strategy/model/profile/account/
  provider/venue/symbol/currency/user identities;
- hashes, digests, Bundle/stream/dataset/cache/source keys;
- prices, quantities, Money, Rate, PnL, balances, positions, orders, or fills;
- payloads, canonical bytes, URLs, paths, files, hostnames, credentials;
- exception classes/messages/tracebacks;
- wall-clock or Simulation timestamps.

## Canonical exclusion

Recorder presence, observations, durations, snapshots, and failures are absent
from every request, environment, semantic hash, Run ID, execution-input bundle,
case, Strategy context/state, Engine trace/result, evidence artifact, repository,
cache identity, retention proof, and analysis value.

Enabled, disabled, saturating, always-failing-recorder, failing-clock, and
failing-counter-extraction paths must produce identical authoritative values,
failures, exceptions, bytes, and hashes. Instrumentation code remains included in
the Build Artifact Manifest.

## Frozen-signature policy

No observation argument is added to a PASSED function, method, Protocol, value, or
constructor. PERF-OBS-01 instruments only the new MRMD/PREP orchestration created
under MRMD-01 and PREP-COVERAGE-01.

No generic decorator, observing Reader/Engine/Repository adapter, or cross-package
recorder is introduced in v1.

## RED matrix

| Test | Required evidence |
| --- | --- |
| value contract | exact enum/value types, valid outcome pairs, sorted snapshot |
| aggregation | repeated updates aggregate and every integer saturates |
| fixed bound | all valid pairs produce exactly nineteen maximum cells |
| aggregate-only | 1 versus 10,000 Events produces one update/cell with different counts |
| disabled fast path | `None` performs no clock or observation work |
| on/off invariance | MRMD bindings, role hashes, request, Run ID, input bundle, case, result, evidence, and replay are byte-identical |
| recorder failure | always-raising recorder preserves exact value/failure/`BaseException` |
| instrumentation failure | failing start/end clock and count extraction preserve authority |
| canonical exclusion | canonical encode/hash of observation/snapshot is rejected and no canonical fixture contains observation fields |
| signature compatibility | every touched PASSED callable retains exact `inspect.signature` |
| source boundary | recorder module imports only stdlib; no logging/I/O/threading/SDK/exporter/registry source path |
| architecture | no Runtime↔Builder violation, root export, Protocol, callback graph, or global singleton |
| legacy compatibility | all PASSED golden bytes/hashes remain unchanged |

The authoritative readiness card is in
`docs/implementation/acceptance-matrix.md`.

## Explicit non-goals

No existing-module instrumentation, optimization, sampling, profiler payload,
per-Event trace, logging, OpenTelemetry/Prometheus/StatsD, exporter, dashboard,
persistence, database, file/network I/O, background queue, lock, thread, global
registry, generic observer Protocol, callback graph, cross-package telemetry API,
canonical evidence, decision-grade claim, live use, or deployment authorization.
