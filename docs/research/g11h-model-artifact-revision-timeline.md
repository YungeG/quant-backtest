# G11H Model Artifact and Revision Timeline Research

## Scope

G11H needs a pure runtime value seam for selecting an already-built immutable model artifact at one exact Decision `SimulationInstant`. It must preserve model/training provenance, reject malformed visible revision chains, ignore future/unrelated evidence, and expose only the selected artifact reference—not train, load, rank, or execute a model.

## Primary authorities

1. [`docs/architecture/backtest-system-design.md`](../architecture/backtest-system-design.md), sections **8.4**, **16.8**, **17.4**, and **20.2**:
   - Runtime does not train models, search parameters, or select best candidates;
   - a model artifact records model hash, training-data hash, training interval, training-code hash, feature-schema hash, and available time;
   - an artifact is usable only when available by the Decision time;
   - Walk-forward switches through a point-in-time revision timeline and the selected artifact identity enters StrategyState and Decision evidence.
2. [`packages/backtest-runtime/src/crypto_quant_backtest/observations.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/observations.py), G11B point-in-time view:
   - authorization/scope filtering precedes visibility and revision inspection;
   - full `SimulationInstant` ordering prevents same-UTC later-phase lookahead;
   - future conflicts must not rewrite a prior view;
   - visible revisions require one legal chain and select its unique terminal.
3. [`packages/backtest-runtime/src/crypto_quant_backtest/strategy_state.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/strategy_state.py), G11F:
   - StrategyState can carry the selected model artifact identity as explicit future-behavior state;
   - G11H must not mutate StrategyState itself; G11I later binds selection and state transition evidence.
4. [`packages/backtest-runtime/src/crypto_quant_backtest/resolution.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/resolution.py), `BuildArtifactRef`:
   - runtime artifact references use immutable content/source hashes rather than module paths or mutable installation objects;
   - G11H model artifacts should remain references, not loaded implementations.
5. [`packages/trading-domain/src/crypto_quant_domain/canonical.py`](../../packages/trading-domain/src/crypto_quant_domain/canonical.py):
   - exact provenance values can use repository canonical serialization and `sha256:<hex>` content identities without a second serializer.

## Frozen vocabulary

### ModelArtifactRef

One immutable reference to one already-produced model revision:

- canonical nonempty `model_key` identifying one logical model interface/lineage;
- `model_hash` for exact model content;
- `training_data_hash` for exact training input evidence;
- `training_start` and `training_end` as UTC economic training interval, with start strictly before end;
- `training_code_hash` for exact training implementation/source evidence;
- `feature_schema_hash` for exact Strategy/model feature interface;
- `available_at: SimulationInstant` for first legal runtime visibility;
- canonical `revision_id` and optional `supersedes_revision_id`;
- derived `artifact_ref_hash`.

`training_end` must not be after `available_at.instant`. Equal UTC is allowed only because the full availability phase/sequence can occur after training completion.

The reference contains no model bytes, path, loader, callable, framework object, endpoint, registry handle, score, rank, or mutable status.

### ModelRevisionTimeline

One immutable point-in-time timeline for one exact `model_key` and one exact `decision_instant`.

Constructor order:

1. discard artifact refs for other model keys;
2. discard refs with `available_at > decision_instant` using full `SimulationInstant` order;
3. collapse exact duplicate refs;
4. validate the visible revision chain;
5. freeze canonical visible evidence and derive `timeline_hash`.

Public behavior is only `timeline_hash` and argument-free `select() -> ModelArtifactRef | None`.

## Revision rules

Visible identity is `(model_key, revision_id)`.

For one point-in-time timeline:

- same revision identity with different canonical content fails;
- one root has no parent;
- every child names an existing visible parent;
- no fork, cycle, disconnected second root, or multiple terminal;
- child `available_at` is strictly later than parent in full `SimulationInstant` order;
- `feature_schema_hash` is stable across the lineage. A schema change is a new model key or a later explicit migration contract, not a silent revision;
- training data/window, training code, and model content may change and are recorded per revision;
- the unique terminal is selected;
- no visible refs is a successful `None` selection.

Future child/conflict evidence is removed before validation, so the visible predecessor remains selectable and prior timeline/selection identity is unchanged.

## Canonical identity

`ModelArtifactRef` canonical body binds every field above. `artifact_ref_hash` is derived and non-recursive.

`ModelRevisionTimeline` canonical body binds:

- type/schema version;
- exact model key;
- exact Decision `SimulationInstant`;
- canonical visible artifact refs in stable revision-chain order.

`timeline_hash` is derived. Other model keys, future refs, and exact duplicate input order do not affect it.

## Switch evidence boundary

G11H only selects a reference. It does not mutate StrategyState or create a Decision trace. G11I later compares the previous model artifact identity in StrategyState with the selected `artifact_ref_hash`, records a StrategyState transition when it changes, and binds that identity into invocation evidence.

This keeps three authorities separate:

- G11H: point-in-time model artifact selection;
- G11F: Strategy-owned business state;
- G11I: Strategy invocation and before/after evidence.

## Required tests

1. before/at same-UTC later-sequence availability selects predecessor then correction;
2. future conflicting revision and unrelated model refs do not alter prior timeline/hash/selection;
3. exact duplicates collapse and input order is irrelevant;
4. revision-ID conflict, missing parent, fork/cycle/multiple root, availability regression, and feature-schema change fail closed;
5. training interval and availability constraints fail closed;
6. visible terminal selection and empty success are deterministic;
7. canonical hashes bind all provenance fields;
8. public boundary exposes no model implementation, path, loader, callback, registry, network, filesystem, clock, Engine, or training dependency.

## Explicit exclusions

- runtime training, fitting, fine-tuning, feature computation, parameter search, candidate scoring/ranking, best-model selection, or experiment comparison;
- model deserialization/loading, framework SDKs, inference callbacks, remote endpoints, filesystem/object-store access;
- StrategyState mutation, Decision production, Observation query, schedule/warmup, RNG, financial state, or EngineCheckpoint;
- Bundle completeness and historical artifact acquisition/retention, which remain external/G12 concerns;
- decision-grade, live, or deployment authorization.

## Minimal implementation seam

Add one production module, `crypto_quant_backtest.model_revisions`, and root exports for only:

- `ModelArtifactRef`;
- `ModelRevisionTimeline`.

Use stdlib immutable collections plus public `crypto_quant_domain` identity/time/canonical contracts. No new dependency or registry is needed.
