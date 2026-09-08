# G11F Strategy State and Checkpoint Research

## Scope

G11F needs one provider-neutral, offline seam for Strategy-owned business state. It must make every value that can affect a later Strategy decision explicit, immutable, canonical, hashable, and checkpointable without becoming an Engine checkpoint, financial account projection, random stream, model registry, schedule, or Strategy invocation framework.

## Primary authorities

1. [`docs/architecture/backtest-system-design.md`](../architecture/backtest-system-design.md), sections **4.6**, **8.4**, **11.2**, **16.8**, and **20.2**:
   - Strategy may read ObservationView, its previous TargetSnapshot, StrategyState, and schedule context, but not account Cash, NAV, Margin, other Sleeves, or Working Orders;
   - all business state affecting future decisions must enter canonical StrategyState and each invocation must record before/after hashes;
   - files, network, system clock, and non-rebuildable caches cannot be hidden business state;
   - warmup may produce a StrategyState checkpoint;
   - EngineCheckpoint is a later, broader child-Attempt recovery mechanism and is not G11F.
2. [`packages/trading-domain/src/crypto_quant_domain/canonical.py`](../../packages/trading-domain/src/crypto_quant_domain/canonical.py):
   - canonical values permit `None`, booleans, integers, NFC strings, string-keyed mappings, and ordered lists/tuples;
   - floats, `Decimal`, date/time objects, bytes, sets, cycles, and unsupported runtime objects fail closed;
   - mapping keys are sorted for canonical bytes and hashes.
3. [`packages/trading-domain/src/crypto_quant_domain/decisions.py`](../../packages/trading-domain/src/crypto_quant_domain/decisions.py):
   - existing Strategy-facing payloads deep-freeze mappings and sequences before publication;
   - `StrategySleeveId` is the existing canonical Strategy identity;
   - caller-supplied mappings are validated through Domain canonical serialization.
4. [`packages/trading-domain/src/crypto_quant_domain/artifacts.py`](../../packages/trading-domain/src/crypto_quant_domain/artifacts.py):
   - canonical JSON payloads can be normalized through canonical bytes and then frozen into mapping proxies and tuples;
   - content hashes are derived, never trusted caller inputs.
5. [`packages/trading-kernel/src/crypto_quant_trading/ledger.py`](../../packages/trading-kernel/src/crypto_quant_trading/ledger.py), `GenericLedger.resume()`:
   - replay-derived state can validate a checkpoint against its authoritative event prefix;
   - StrategyState has no G11F event log authority, so G11F must not imitate Ledger replay or claim Engine recovery parity. Its checkpoint is the explicit authoritative Strategy state value itself.
6. [`docs/implementation/acceptance-matrix.md`](../implementation/acceptance-matrix.md), G02:
   - canonical Domain contracts and package direction are already frozen and PASSED;
   - G11F should reuse those public contracts rather than introduce a second serializer or identity system.

## Frozen vocabulary

### StrategyState

One immutable Strategy-owned business-state value:

- `strategy_id: StrategySleeveId`;
- `schema: CanonicalSchema`;
- `values: Mapping[str, CanonicalJsonValue]`;
- derived `state_hash`.

`values` uses only the canonical JSON subset: `None`, bool, int, NFC string, string-keyed mapping, and ordered list/tuple. Every mapping level is frozen in sorted-key order and every sequence becomes a tuple. This matters beyond hash stability: Strategy code must not observe different mapping iteration order for equal state hashes.

State schema identity is explicit and enters the hash. G11F v1 performs no schema migration. A transition must keep the same Strategy and schema; a later migration contract can add explicit migration evidence if required.

### StrategyStateTransition

One immutable before/after evidence value:

- caller-supplied canonical `transition_key`;
- deterministic `occurred_at: SimulationInstant`;
- exact before and after `StrategyState` values;
- derived before/after state hashes and transition hash.

The canonical transition artifact records Strategy identity, schema, deterministic instant, and before/after hashes. It does not invoke Strategy code or interpret the state fields.

### StrategyCheckpoint

One immutable checkpoint value:

- caller-supplied canonical `checkpoint_key`;
- deterministic `captured_at: SimulationInstant`;
- exact `StrategyState`;
- derived checkpoint hash.

The checkpoint embeds the full canonical state and its hash. `restore()` returns that immutable state. The checkpoint hash is identity; there is no caller-supplied digest to trust and no mutable store, path, Attempt, process address, or wall-clock capture.

## Required behavior

1. Deep-freeze caller mappings and sequences immediately; later mutation of caller containers cannot change state bytes or behavior.
2. Sort mapping keys recursively before exposure so equal hashes imply equal observable mapping order.
3. Reject non-string or empty/trim-variant mapping keys, noncanonical Unicode, floats, decimal/date/time/bytes/set/callable/file/socket/runtime objects, and cycles.
4. Bind state identity to exact Strategy identity, schema name/version, and canonical values.
5. Bind transitions to exact Strategy/schema, full `SimulationInstant`, and exact before/after hashes; reject cross-Strategy or implicit schema-change transitions.
6. Bind checkpoints to exact Strategy state and full deterministic capture instant; reordering equivalent input mappings must not change state/checkpoint hashes.
7. Demonstrate continuation parity with an external pure test step: uninterrupted `S0 → S1 → S2` equals `S0 → S1 → checkpoint → restore(S1) → S2`.
8. Keep G11A/B artifacts and Engine/Runner/Timeline/TargetStream unchanged.

## Explicit exclusions

- Cash, NAV, Margin, Position, Working Orders, Ledger, Journal, Reservation, Settlement, or Inventory authority;
- RandomStream algorithm/counters or replay, owned by G11G;
- model artifact lookup/revision switching, owned by G11H;
- DecisionSchedule/Warmup semantics, owned by G11E;
- Strategy callback execution, Observation aggregation, DecisionBatch, or invocation audit, owned by G11I;
- filesystem/network/database/process/environment/wall-clock access;
- mutable cache, plugin registry, serializer registry, migration framework, external persistence, or EngineCheckpoint/child-Attempt recovery.

A rebuildable performance cache stays outside StrategyState. If its content can affect future decisions, it is business state and must instead be represented canonically.

## Minimal implementation seam

Add one production module, `crypto_quant_backtest.strategy_state`, and root exports for:

- `StrategyState`;
- `StrategyStateTransition`;
- `StrategyCheckpoint`.

Use only stdlib immutable-container support plus public `crypto_quant_domain` canonical, identity, and time contracts. No new dependency is needed.

## Readiness test shape

One contract file, one static golden, and one architecture boundary should freeze:

- nested deep immutability and canonical mapping-order parity;
- allowed/rejected state values and cycles;
- schema/Strategy isolation;
- before/after transition hashes;
- full-`SimulationInstant` checkpoint identity;
- continuation-after-restore parity;
- constructor/`dataclasses.replace` forgery controls;
- public imports and absence of filesystem/network/callback/Engine branches.
