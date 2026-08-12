# G11D Named Bar Window Research

## Scope

G11D needs a typed Strategy-facing query that returns a bounded lookback of already-aggregated canonical Bar observations visible at one exact Decision `SimulationInstant`. It must bind an explicit versioned BarDefinition identity, preserve G11B revision causality, reject wrong-stream/post-decision data, and report whether the requested count was satisfied without performing resampling or claiming G12 gap completeness.

## Primary authorities

1. [`docs/architecture/backtest-system-design.md`](../architecture/backtest-system-design.md), sections **4.6**, **8.2**, **16.8**, and **20.2**:
   - Strategy queries a named canonical Bar Stream and cannot perform unversioned resampling;
   - BarDefinition owns duration, Session scope, anchor, included phases, price source, volume semantics, empty interval policy, and Calendar;
   - changing BarDefinition produces new Bundle/stream identity;
   - daily/session Bars are not inferred from UTC-date grouping.
2. [`packages/backtest-runtime/src/crypto_quant_backtest/observations.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/observations.py), G11A/B:
   - exact Dataset/Instrument/Purpose/Capability authorization and full `SimulationInstant` visibility already exist;
   - latest legal revision selection and causality trace are frozen;
   - G11D should compose the returned point-in-time result, not rerun raw revision logic.
3. [`packages/backtest-runtime/src/crypto_quant_backtest/execution.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/execution.py):
   - execution-specific `BarOpenObservation` parses a narrow payload for fills and must not become the general Strategy Bar/window contract;
   - G11D should preserve exact `MarketEvent` values instead of coupling to execution semantics.
4. [`packages/trading-domain/src/crypto_quant_domain/canonical.py`](../../packages/trading-domain/src/crypto_quant_domain/canonical.py):
   - explicit BarDefinition/query/result values and hashes can reuse repository canonical serialization.

## Missing prerequisite and minimal freeze

No production BarDefinition contract currently exists. G11D therefore owns the smallest identity reference needed to address a pre-aggregated stream; it does not implement aggregation.

### BarDefinitionRef

One immutable versioned identity:

- canonical nonempty `key`;
- positive integer `version`;
- exact `definition_hash` supplied by the Builder/Bundle evidence.

The hash commits to the full external BarDefinition (duration/session/anchor/phases/price/volume/empty policy/calendar), while G11D intentionally does not duplicate or interpret those fields. A changed definition requires a changed hash and/or version.

### NamedBarWindowQuery

One immutable query:

- exact G11B `ObservationQuery` selecting one Dataset/Instrument/Purpose/Capability;
- exact `BarDefinitionRef`;
- exact `decision_instant: SimulationInstant` equal to the backing point-in-time view instant by result evidence;
- positive bounded `lookback_count`;
- optional `end_at_or_before: UtcInstant`, which must not exceed `decision_instant.instant`.

The query does not request duration, resampling, timezone, Calendar, arbitrary predicate, or dataframe operations.

### NamedBarWindowResult

One immutable successful result:

- Query;
- canonical ordered suffix of selected `MarketEvent` bars;
- backing `ObservationCausalityTrace`;
- `available_count` from the backing selected result;
- `requested_count`;
- `coverage_complete = available_count >= requested_count`;
- `shortfall_count = max(requested_count - available_count, 0)`;
- max Event and availability times from the returned window;
- result hash;
- `decision_grade_eligible=false` and `deployment_authorized=false`.

Partial lookback is a successful explicit result, not an exception. G11D can truthfully report count shortfall but cannot classify why bars are absent. G12 owns NO_SESSION/SUSPENDED/NO_TRADES/MISSING/SOURCE_OUTAGE and full Bar aggregation coverage.

### NamedBarWindowView

Constructed from exact `NamedBarWindowQuery` and one successful G11B `PointInTimeObservationQueryResult`. Construction validates:

- Query selector and decision instant match backing result;
- every event is the requested stream/instrument/capability and already visible;
- Event type is exact caller-frozen Bar event type `bar`;
- every event `event_time <= end_at_or_before` when supplied;
- no duplicate/noncanonical event ordering;
- G11B trace/result integrity remains valid.

Public behavior is only `view_hash` and argument-free `window() -> NamedBarWindowResult`.

The returned window is the final `lookback_count` events after optional end cutoff, retaining G11A/B canonical event ordering. G11D does not sort by payload timestamps, parse OHLCV, derive intervals, forward-fill, or aggregate.

## BarDefinition binding

G11B ObservationQuery does not contain BarDefinition. G11D binds `BarDefinitionRef` in its Query/result/view hashes. The caller/Bundle builder must supply a dataset/capability whose stream is already the exact definition. G11D cannot prove that the underlying payload was correctly aggregated; G12 BarAggregationManifest and coverage own that proof.

## Failure boundary

Constructor failures are exact context/integrity failures:

- invalid BarDefinition key/version/hash;
- nonpositive/bool lookback;
- end cutoff after Decision instant;
- backing query/decision mismatch;
- non-Bar event type, future/post-cutoff event, wrong context, duplicate/noncanonical events, or forged trace.

Authorized empty or short windows are successful results. An unauthorized G11B query remains a G11B failure and cannot construct G11D; G11D does not duplicate the authorization failure union.

## Explicit exclusions

- raw MarketBundle/Reader/Cursor access, file/network/database/process/environment/wall clock;
- resampling, aggregation, timezone/session/TradingDate calculation, empty interval synthesis, forward fill, indicator computation, vectorized dataframe API;
- Universe selection, scheduling/warmup, Strategy invocation, Target/Decision production, financial state, RNG, Model, or EngineCheckpoint;
- Bar completeness/gap reason/quality/decision-grade/deployment claims.

## Minimal implementation seam

Add `crypto_quant_backtest.observation_windows` and root exports for:

- `BarDefinitionRef`;
- `NamedBarWindowQuery`;
- `NamedBarWindowResult`;
- `NamedBarWindowView`.

Reuse G11B public result/trace values. No new dependency is needed.

## Readiness fixture shape

One finite fixture should freeze:

- five already-aggregated Bar revisions, visible cutoff, canonical suffix lookback 3;
- optional end cutoff and exact boundary inclusion;
- full and partial coverage including empty success;
- same stream with changed BarDefinition hash/version changes identity;
- input/repeat parity inherited from G11B;
- wrong query/decision/event type/post-cutoff/forged trace failures;
- result events, count/shortfall/maxima, trace and all hashes/flags.
