# G11I Portfolio Strategy Invocation Research

## Scope

G11I is the single offline fan-in from the frozen G11A–G11H Strategy Runtime authorities to the existing G04 validation and atomic `DecisionBatch` path. It constructs least-authority immutable callback contexts, stages every Strategy result, validates every captured Candidate, and publishes either one complete handoff or no downstream authority.

G11I does not add a second allocation, risk, sizing, execution, accounting, Runner, or evidence path.

## Primary authorities

1. `docs/architecture/backtest-system-design.md`, Strategy Runtime and DecisionBatch sections:
   - Strategies receive immutable point-in-time views rather than Bundles, account state, ambient clocks, or provider handles;
   - all Strategies assigned to one exact Decision entry share the same eligibility boundary;
   - Candidates enter the existing Trading Kernel validation and atomic collection seam before downstream economics.
2. G11A–G11H production contracts:
   - G11B supplies revision-safe observation results and causality traces;
   - G11C supplies point-in-time Universe identity;
   - G11D supplies named window evidence;
   - G11E supplies the exact full `SimulationInstant` schedule entry and Warmup eligibility;
   - G11F supplies immutable Strategy checkpoints;
   - G11G supplies named deterministic RNG checkpoints;
   - G11H supplies point-in-time model timelines and selected artifact identity.
3. G04 Trading Kernel contracts:
   - `StrategyOutputValidator` is the only Candidate decoder/validator;
   - `AtomicDecisionBatchCollector` is the only `DecisionBatch` and `LatestSleeveDecisionState` authority.
4. `crypto_quant_domain` canonical serialization:
   - invocation, handoff, checkpoint, model, decision, batch, allocation, risk, and sizing identities use the existing canonical bytes and SHA-256 rules.

## Frozen invocation seam

The public G11I surface is:

- `PortfolioStrategyRegistration`;
- `PortfolioStrategyInvocationContext`;
- `PortfolioStrategyInvocation`;
- `PortfolioStrategyInvocationFailureCode`;
- `PortfolioStrategyInvocationStatus`;
- `PortfolioStrategyInvocationOutput`;
- `invoke_portfolio_strategies(...)`.

A registration binds one expectation, one attested immutable Strategy build artifact, one executable Strategy object exposing that same artifact, point-in-time observations, Universe, windows, one prior `StrategyCheckpoint`, named RNG streams, selected model timelines, and an optional successful prior G11I output.

There is no runtime registry, dynamic loader, factory, executor, thread/process pool, cache, filesystem, network, wall clock, or global RNG manager.

## Least-authority context

Each callback receives only its immutable `PortfolioStrategyInvocationContext` and prior `StrategyState`. The context binds:

- exact expectation and shared G11E entry/eligibility hashes;
- observation result/query/trace hashes;
- Universe selection hash;
- named window result and causality hashes;
- prior Target hash, StrategyState hash, checkpoint hash, and prior successful output hash;
- exact prior checkpoint `SimulationInstant`;
- named RNG stream hashes;
- model timeline and selected artifact hashes;
- Instrument Catalog hash.

Cross-evidence must match the same exact G11E entry before any callback executes. Future observation, window, model, checkpoint, prior target, or prior decision-state evidence fails closed.

## Deterministic invocation and failure order

Registrations are sorted by `(strategy_id, sleeve_id)` before context creation or callbacks. Duplicate Sleeves fail before invocation.

The frozen order is:

1. validate input types, unique registrations, prior handoff continuity, and exact-instant causality;
2. construct every least-authority context;
3. when ineligible, return canonical `INELIGIBLE` evidence with zero callbacks, Validator calls, or Collector calls;
4. invoke every callback in canonical order and stage Candidate, state transition, and RNG transition evidence;
5. isolate callback lookup/call exceptions and malformed callback output without short-circuiting sibling callbacks;
6. run the existing `StrategyOutputValidator` for every captured Candidate;
7. give invocation/output/state/RNG failure precedence over validation failure;
8. on eligible Warmup, publish invocation/state/RNG evidence without a `DecisionBatch`;
9. on eligible Active success, call `AtomicDecisionBatchCollector.collect(...)` exactly once;
10. expose no partial authoritative handoff on callback, output, validation, or batch failure.

Attempted after-state and RNG hashes remain in failure evidence, but only successful outputs are accepted as future checkpoint/RNG handoffs.

## Full SimulationInstant compatibility

G11E permits distinct schedule entries sharing one UTC nanosecond while differing by phase or source sequence. The original G04 seam stored only `UtcInstant`, which could not safely chain those entries.

G11I therefore adopts an additive exact-instant mode:

- `StrategyDecision`, `DecisionBatch`, `LatestSleeveDecisionState`, validation context, batch failure, and collector input accept optional keyword-only `SimulationInstant` evidence;
- absent exact-instant fields preserve all legacy v1 canonical bytes, hashes, constructors, and `decision-batch-v1:` identifiers;
- exact-instant calls use separate v2 identities and reject UTC/full-instant mismatch, exact/legacy mode downgrade, and equal-or-future prior state;
- two valid same-UTC entries with strictly increasing full instants produce distinct decision/batch/state/handoff identities and may continue from the earlier state;
- ambiguous legacy same-UTC decisions cannot be carried into an exact state.

The exact instant is propagated through Portfolio Snapshot, Allocation, Risk, Mark, Sizing, and Active Target evidence only in opt-in v2 flows. Mixing exact state with UTC-only downstream evidence fails closed. Existing v1 golden files remain byte-for-byte unchanged.

## Strategy state, RNG, model, and build continuity

Genesis execution requires a caller-supplied immutable checkpoint strictly before the Decision entry and RNG counters at zero. Advanced state or RNG positions require a successful prior G11I output whose invocation hash, transition, checkpoint, streams, and optional active decision state exact-match the new registration.

Model evidence is accepted as `ModelRevisionTimeline`, not a bare artifact. G11H validates the visible lineage and terminal selection; G11I binds both timeline and selected artifact hashes without loading or executing model bytes.

The executable Strategy object must expose the exact `BuildArtifactRef(role=DECISION_SOURCE)` supplied by the registration. Artifact storage and installed-byte attestation remain external build authority; callback identity, module paths, exception text, traceback, object address, and attempt identity never enter canonical evidence.

## Canonical outputs

Per-Strategy invocation evidence binds context, Strategy artifact, validation result, attempted state transition, attempted next RNG streams, and stable failure code.

Aggregate output binds:

- status;
- exact schedule entry and eligibility identity;
- Instrument Catalog hash;
- canonically ordered invocation records;
- existing atomic batch/state/failure evidence;
- active-success-only handoff hash.

Public record constructors revalidate exact-cover relationships so callers cannot splice unrelated contexts, validations, transitions, batches, or states into a forged canonical handoff.

All G11I outputs remain development-only with `decision_grade_eligible=false` and `deployment_authorized=false` until G12 qualification.

## Required evidence

1. two-Sleeve Active success with registration-order independence and exactly one Collector call;
2. eligible Warmup state/RNG transition without batch handoff;
3. ineligible zero-callback behavior whose output still binds suppressed context evidence;
4. callback, malformed output, invalid state, invalid RNG, validation, and batch failures with deterministic precedence and no partial authority;
5. prior checkpoint/output/RNG continuity and forgery rejection;
6. G11H timeline and selected artifact binding;
7. two consecutive same-UTC full-instant Active invocations with previous-target continuity and distinct v2 identities;
8. legacy v1 hash compatibility and exact/legacy mode fail-closed tests;
9. exact-instant propagation through allocation, risk, marks, sizing, and Active Target;
10. static golden, architecture/import boundary, public export, full suite, static typing, and dependency-lock validation.

## Explicit exclusions

- Strategy discovery, dynamic loading, sandboxing arbitrary Python imports, model loading/inference infrastructure, or provider access;
- thread/process parallel execution or transactional runtime infrastructure;
- account, Ledger, Margin, Reservation, or current Portfolio state in callback contexts;
- a second Validator, DecisionBatch collector, allocation, risk, planning, execution, accounting, Runner, or evidence implementation;
- decision-grade, live, or deployment authorization;
- G11J precomputed-vs-Strategy downstream parity, which consumes the completed G11I handoff.
