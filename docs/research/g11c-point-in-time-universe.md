# G11C Point-in-time Universe Research

## Scope

G11C needs one offline Strategy-facing value seam that resolves an explicitly named Universe at one exact `SimulationInstant`. It must distinguish economic listing/membership time from evidence availability, preserve stable `InstrumentId`, support membership entry/exit and corrections without lookahead, and label fixed caller-supplied universes truthfully.

## Primary authorities

1. [`docs/architecture/backtest-system-design.md`](../architecture/backtest-system-design.md), sections **4.6**, **8.2**, **11**, **16.8**, and **20.2**:
   - Strategy obtains tradable Instruments only through a point-in-time Universe query and may not scan data directories;
   - Symbol, listing, delisting, and Universe membership are point-in-time properties of stable Instrument identity;
   - pre-listing Instruments cannot be visible and delisted Instruments remain in historical evidence;
   - a labelled StaticUniverse must not claim survivorship-bias-free market coverage.
2. [`packages/backtest-runtime/src/crypto_quant_backtest/observations.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/observations.py), G11B:
   - scope filtering precedes full-`SimulationInstant` visibility and revision validation;
   - future/unrelated conflict evidence cannot change a prior view;
   - one logical lineage needs a caller-supplied stable key, one legal visible revision chain, and terminal selection.
3. [`packages/trading-domain/src/crypto_quant_domain/instruments.py`](../../packages/trading-domain/src/crypto_quant_domain/instruments.py):
   - `InstrumentId` is the stable canonical identity and is sortable;
   - symbol history and Instrument definitions remain separate from membership selection.
4. [`packages/trading-kernel/src/crypto_quant_trading/validation.py`](../../packages/trading-kernel/src/crypto_quant_trading/validation.py), `StrategyOutputValidationContext`:
   - downstream validation consumes a pre-resolved, unique, sorted `tuple[InstrumentId, ...]` and does not infer Universe membership itself.
5. [`packages/trading-domain/src/crypto_quant_domain/canonical.py`](../../packages/trading-domain/src/crypto_quant_domain/canonical.py):
   - Universe evidence and result identity can reuse exact canonical serialization and repository SHA-256 hashes.

## Frozen vocabulary

### UniverseKind

Two exact v1 kinds:

- `POINT_IN_TIME`: membership is supplied as historical effective/availability evidence;
- `STATIC`: a fixed caller-supplied set, explicitly labelled and never described as survivorship-bias-safe market coverage.

A single Universe key cannot mix kinds.

### UniverseMembershipRevision

One immutable revision of one logical membership interval:

- canonical nonempty `universe_key`;
- canonical nonempty caller-supplied `membership_key`, stable across corrections;
- exact `kind: UniverseKind`;
- stable `instrument_id: InstrumentId`;
- economic listing interval `[listed_at, delisted_at)` where delisted may be open-ended;
- economic membership interval `[member_from, member_until)` where member-until may be open-ended;
- `available_at: SimulationInstant`, the first instant the revision is knowable;
- canonical `revision_id` and optional `supersedes_revision_id`;
- exact `source_hash`;
- derived revision hash.

The membership interval must overlap and be contained by the listing interval. Delisting closes membership eligibility but does not delete historical identity/evidence.

Multiple non-overlapping membership keys may represent entry, exit, and later re-entry for the same Instrument. G11C does not infer an interval from Bar presence, Symbol, current listings, or missing records.

### UniverseQuery

One immutable exact query:

- canonical `universe_key`;
- exact `kind`;
- exact `decision_instant: SimulationInstant`.

Economic membership is evaluated at `decision_instant.instant`; knowledge visibility uses the full `decision_instant` total order.

### UniverseSelection

One immutable successful result:

- exact Query;
- sorted unique active `InstrumentId` tuple;
- selected membership revision hashes used for active membership;
- all visible candidate revision hashes for causality;
- maximum selected evidence availability instant;
- derived selection hash;
- exact limitations:
  - `point_in_time=True` only for `POINT_IN_TIME`;
  - `static_universe=True` only for `STATIC`;
  - `survivorship_bias_safe=False` for both in G11C because G12 has not proven completeness;
  - `decision_grade_eligible=False` and `deployment_authorized=False`.

An exact query with no active membership succeeds with an empty Instrument tuple. G11C does not reinterpret empty as no session, suspension, missing source, or complete market absence.

### PointInTimeUniverseView

One immutable view constructed from:

- exact `UniverseQuery`;
- caller-supplied `UniverseMembershipRevision` iterable.

Public behavior is only `view_hash` and argument-free `select() -> UniverseSelection`.

## Construction and failure order

1. discard records for other Universe keys or kinds;
2. discard records with `available_at > decision_instant` using full `SimulationInstant` ordering;
3. collapse exact duplicate canonical revisions;
4. validate visible revision identities/chains independently by `membership_key`;
5. select each legal lineage terminal;
6. validate selected interval consistency;
7. choose selected terminals whose membership and listing intervals contain `decision_instant.instant`;
8. unique-sort active Instruments and freeze result evidence.

Visible failure precedence:

1. same `(membership_key, revision_id)` with conflicting content;
2. missing visible parent;
3. fork/cycle/multiple root/disconnected chain;
4. lineage context mismatch (`universe_key`, kind, Instrument, membership key changes);
5. child availability not strictly later than parent;
6. invalid/cross-listing membership interval;
7. overlapping selected membership intervals for the same Instrument in one Universe.

Future or unrelated malformed evidence is filtered before these checks and cannot affect prior identity.

## Static Universe boundary

Static evidence still requires explicit membership/listing intervals and availability; it is not directory discovery or “all Instruments in the final dataset.” A fixed membership set may be useful for a controlled experiment, but the result remains labelled `static_universe=True` and `survivorship_bias_safe=False`.

G11C does not compare a Static Universe with historical exchange listings or upgrade its grade. G12 Universe coverage is required for completeness/survivorship claims.

## Canonical identity

The view hash binds the exact Query and all visible in-scope revision evidence after canonical deduplication. Other Universe/kind records, future records, future conflicts, and input order do not enter prior identity.

The selection hash binds the Query, sorted active Instrument IDs, selected active revision hashes, all visible candidate hashes, maximum selected availability, and fixed limitation flags.

## Explicit exclusions

- Instrument discovery, Symbol parsing, directory/file scanning, current exchange APIs, provider fallback, or Bundle acquisition;
- Universe completeness, gap classification, source outage, or survivorship certification, owned by G12;
- Bar/window access, resampling, scheduling, warmup, Strategy invocation, Target/Decision production, financial state, RNG, model selection, or EngineCheckpoint;
- mutable registries/caches, database/filesystem/network/process/environment/wall-clock access;
- decision-grade, live, or deployment authorization.

## Minimal implementation seam

Add one production module, `crypto_quant_backtest.universe`, with root exports for:

- `UniverseKind`;
- `UniverseMembershipRevision`;
- `UniverseQuery`;
- `UniverseSelection`;
- `PointInTimeUniverseView`.

No new dependency is required.

## Readiness fixture shape

One finite fixture should cover:

- Instrument A membership entry and later correction visible at same UTC/later source sequence;
- Instrument B exit and re-entry using separate membership keys;
- pre-listing and at/after-delisting exclusion without deleting history;
- POINT_IN_TIME and labelled STATIC results;
- future/unrelated malformed evidence noninterference;
- all visible revision/interval failures and precedence;
- empty success, input order/exact duplicate parity, stable sorted Instrument output, hashes, maxima, flags, and forgery controls.
