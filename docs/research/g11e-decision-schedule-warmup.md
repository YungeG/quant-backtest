# G11E Decision Schedule and Warmup Research

## Scope

G11E needs one immutable, provider-neutral schedule authority that classifies exact Decision `SimulationInstant` values into Warmup or Active Trading, preserves total ordering, enforces half-open run boundaries, and decides whether a caller-supplied set of G11D named Bar windows satisfies explicit lookback requirements before Strategy invocation.

It does not generate exchange-local sessions, read the Timeline, invoke Strategy code, or authorize trading side effects.

## Primary authorities

1. [`docs/architecture/backtest-system-design.md`](../architecture/backtest-system-design.md), sections **7.1**, **8.1**, **9.1**, and **9.4**:
   - Portfolio Strategy is invoked only by an explicit DecisionSchedule;
   - run boundaries are `data_start <= trading_start < trading_end_exclusive`;
   - Warmup is `[data_start, trading_start)` and Active Trading is `[trading_start, trading_end_exclusive)`;
   - Warmup may build Strategy state but cannot produce OrderIntent, Fill, Accounting Journal Entry, or performance;
   - StrategySpec declares LookbackRequirement and insufficient lookback fails closed for decision grade;
   - deterministic event identity and visibility use full `(UtcInstant, TimelinePhase, SourceSequence)`, not UTC alone.
2. [`packages/backtest-runtime/src/crypto_quant_backtest/timeline.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/timeline.py):
   - `TimelineWindow` already freezes the three half-open Utc boundaries;
   - `TimelineSegment` already names `WARMUP` and `ACTIVE_TRADING`;
   - G11E should reuse both rather than create a second interval or segment model;
   - `DeterministicTimeline` remains the MarketEvent merge/reader authority and must not be coupled to Strategy scheduling.
3. [`packages/backtest-runtime/src/crypto_quant_backtest/observation_windows.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/observation_windows.py), G11D:
   - a `NamedBarWindowResult` binds one exact Decision SimulationInstant, BarDefinition identity, Observation selector, requested/available counts, canonical Event suffix, and G11B causality trace;
   - G11E should consume those immutable results as lookback evidence and must not resample, fetch, or reinterpret Bar payloads.
4. [`packages/backtest-runtime/src/crypto_quant_backtest/target_stream.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/target_stream.py):
   - the existing `TargetStreamDecisionSchedule` is an adapter-specific precomputed Target Stream contract keyed by UTC decision time and expected Strategy/Sleeve event entries;
   - its Warmup suppression records validated target-source suppression, not general Strategy invocation eligibility;
   - G11E therefore requires a separate generic schedule seam and must not mutate or replace the Target Stream contract.

## Minimal frozen contract

### LookbackRequirement

One immutable required named window identity:

- `requirement_key`: canonical nonempty identity used for deterministic ordering and diagnostics;
- exact G11D `BarDefinitionRef`;
- exact G11A `ObservationQuery` selector;
- positive non-bool `minimum_count`, maximum 10000.

The requirement does not contain duration, arbitrary resampling, gap reason, callback, dataframe, or Strategy code. Duplicate requirement keys or duplicate `(ObservationQuery, BarDefinitionRef)` identities are invalid.

### DecisionScheduleEntry

One immutable planned invocation instant:

- exact `decision_instant: SimulationInstant`;
- exact `segment: TimelineSegment`.

The instant must be inside the schedule `TimelineWindow` by UTC boundary and the declared segment must equal the boundary-derived segment:

- `data_start <= instant.instant < trading_start` => Warmup;
- `trading_start <= instant.instant < end_exclusive` => Active Trading.

The end boundary and later are excluded. Entries are strictly increasing and unique by full SimulationInstant. Multiple entries at the same UTC time are legal only when phase/source-sequence make the full instant distinct; their canonical order is the full SimulationInstant order. The schedule does not collapse them by UTC.

### DecisionSchedule

One immutable finite schedule:

- canonical nonempty schedule key and positive version;
- exact `TimelineWindow`;
- ordered nonempty `DecisionScheduleEntry` tuple;
- ordered `LookbackRequirement` tuple, which may be empty;
- canonical schedule hash.

Construction canonicalizes requirements by identity but requires entries already in exact increasing execution order; silently reordering caller schedule input would hide an invalid trigger source. A changed window, instant, phase, source sequence, segment, requirement, or BarDefinition changes schedule identity.

G11E consumes already-resolved caller-supplied instants. Exchange local time, Calendar, Session, DST, TradingDate, recurring cron/rule expansion, and MarketEvent generation remain outside this seam. SessionModel/Calendar or a later composition layer creates the finite entries before construction.

### WarmupEligibility

One immutable evaluation for one schedule entry:

- schedule hash and exact entry;
- canonical provided G11D window evidence matched by requirement identity;
- required, available, and shortfall counts per requirement;
- overall `lookback_satisfied`;
- `strategy_invocation_eligible`;
- `trading_side_effects_authorized`;
- development-only / deployment false flags;
- canonical eligibility hash.

Eligibility rules:

- Every required window must be supplied exactly once.
- Each window Query Decision Instant must equal the entry instant.
- Its ObservationQuery and BarDefinitionRef must exactly match its LookbackRequirement.
- `available_count >= minimum_count` satisfies that requirement. The G11D query's own requested count may be greater, equal, or smaller; G11E evaluates the frozen requirement count from available evidence and does not trust a caller-provided Boolean alone.
- Extra unrelated window evidence is rejected rather than ignored.
- Empty requirements are satisfied without window evidence.
- `strategy_invocation_eligible = lookback_satisfied` for both Warmup and Active entries. This permits deterministic Warmup state construction only after its requirements are present.
- `trading_side_effects_authorized = lookback_satisfied and segment is ACTIVE_TRADING`.
- Warmup can therefore be invocation-eligible while never authorizing OrderIntent, Fill, Journal, performance, Target activation, or account mutation.
- Insufficient lookback is an explicit successful ineligible result, not an exception and not a G12 gap-reason classification.

### DecisionSchedule evaluator seam

The smallest public behavior is:

- `schedule_hash`;
- `eligibility(entry, windows) -> WarmupEligibility`.

The entry must be an exact member of the schedule. The evaluator has no callbacks, hidden state, clock, Timeline reader, Strategy registry, or side effects. Same input yields the same result/hash.

## Atomic same-instant boundary

G11E schedules invocation windows; G11I owns Strategy identity, registration-order independence, Context creation, state/RNG/model authorities, invocation, and atomic DecisionBatch fan-in.

For G11E, “atomic same-instant invocation window” means only that every exact schedule entry is one immutable eligibility boundary. All Strategy invocations assigned by G11I to that exact full SimulationInstant must use the same entry, same schedule hash, and separately validated lookback evidence before any downstream planning. G11E does not create one entry per Strategy and does not expose partial Strategy outputs.

Two entries sharing UTC but differing in phase or source sequence are different ordered invocation windows, not one atomic batch.

## Failure boundary

Construction/evaluation fails closed for:

- invalid schedule/requirement identity or bool/nonpositive versions/counts;
- invalid TimelineWindow;
- empty, duplicate, unsorted, or out-of-window entries;
- declared segment inconsistent with half-open boundaries;
- duplicate requirement key or selector/BarDefinition identity;
- evaluating an entry not in the schedule;
- duplicate, missing, extra, wrong-definition, wrong-selector, or wrong-Decision window evidence;
- forged derived eligibility fields/hashes.

Insufficient count is not a constructor failure. It returns explicit `lookback_satisfied=false`, `strategy_invocation_eligible=false`, and `trading_side_effects_authorized=false`.

## Explicit exclusions

- Calendar/Session/TradingDate/DST or recurring-rule expansion;
- Timeline/Reader/Bundle/file/network/database/process/environment/wall clock access;
- Bar aggregation/resampling/gap classification/completeness qualification;
- Universe construction;
- Strategy Context, invocation, Strategy State transition/checkpoint, RNG draw, Model selection, Target/Decision/Batch, Order/Fill/Journal/performance;
- live or deployment authorization.

## Minimal implementation seam

Add `crypto_quant_backtest.decision_schedule` and root exports for:

- `LookbackRequirement`;
- `DecisionScheduleEntry`;
- `DecisionSchedule`;
- `LookbackCoverage`;
- `WarmupEligibility`.

Reuse `TimelineWindow`, `TimelineSegment`, `SimulationInstant`, `ObservationQuery`, `BarDefinitionRef`, and `NamedBarWindowResult`. No dependency, scheduler framework, cron parser, registry, callback, or cache is needed.

## Readiness fixture shape

One finite static fixture should freeze:

- a window `[0, 100)` Warmup and `[100, 300)` Active;
- Warmup at UTC 50, Active boundary at UTC 100, two same-UTC full instants with distinct phase/sequence, and the last legal Active instant before 300;
- explicit exclusion of UTC 300;
- one requirement satisfied, short, and missing;
- empty requirement success;
- Warmup invocation eligibility with trading side effects false;
- Active eligibility with trading side effects true only when lookback is satisfied;
- changed phase/source sequence/window/requirement changes identity;
- wrong entry/window context, extra/duplicate evidence, unsorted entries, boundary segment mismatch, and forged eligibility failures;
- schedule, entry, coverage, eligibility, and fixture hashes plus repeat parity.
