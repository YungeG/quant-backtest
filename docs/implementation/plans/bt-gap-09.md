---
id: BT-GAP-09
status_source: ../acceptance-matrix.md
owner: backtest-runtime public provider preparation
produces:
  - installable cash.precomputed_target.development.v1 provider
  - BacktestRequestRef
  - PreparedBacktestExecution
  - prepare_cash_development_backtest
consumes:
  - immutable BacktestRequest@1
  - additive backtest_execution_input_bundle@2
  - BT-GAP-02/02A/02B/02C/07/08
fan_in:
  - Platform P00-BTA-01
  - Platform P00-SEAM-01
---

# BT-GAP-09 Installable Development Cash Provider and Platform Preparation

## Status

`BLOCKED_OWNER_DECISION` until the Backtest owner approves
`cash.precomputed_target.development.v1` as a new installable, development-only
product. A registration wrapper alone cannot close P00 because the current installed
packages contain no production producer of an executable v2 execution plan.

## First-principles authority chain

The required independent flow is:

```text
opaque Platform context
→ public BacktestRequest
→ Backtest validation/persistence and BacktestRequestRef
→ concrete provider external facts
→ Backtest-owned executable case
→ canonical v2 execution-input envelope
→ BacktestRuntime execution and evidence
→ Platform governance admission
```

Every arrow requires one installed authority. The missing arrow is not merely request
registration; it is `concrete provider external facts → executable case`. The accepted
v2 materializer and decoder begin after that transition and therefore cannot produce
it.

Independence means:

1. Platform constructs only the public request and passes opaque context; it derives
   no Backtest identity, execution plan, metric, terminal, or evidence hash.
2. Backtest imports no Platform type and preserves the opaque context exactly.
3. Foundation stores and structurally reads canonical bytes but implements no
   Backtest semantic decoder or verifier.
4. Provider inputs contain external economic/provider facts, never a disguised
   `ResolvedBacktestRequest`, `ResolvedExecutionCase`, decision cycle, identity plan,
   or ledger plan.
5. A clean-installed Backtest distribution can prepare, run, derive, and verify the
   development case without Platform or `tests/support`.
6. Real-market, decision-grade, deployment, and governance qualification remain
   separate receipts.

## Reproduced blockers

1. `materialize_execution_input_bundle_v2()` requires an already-resolved request and
   execution case.
2. Every current producer of decision cycles, bar executions, financial state,
   dispatch plans, and snapshots is under `tests/support` or test fixtures.
3. Binance and China A-share production profile modules freeze registrations and
   component identities but do not produce a complete executable case.
4. The public facade selects the production default cash dispatcher. The Binance and
   China A-share dispatchers used by executable tests are test-only.
5. No `BacktestRequestRef` or public request registration/persistence operation exists.
6. `BacktestRuntime.run()` does not currently expose its accepted cancellation input,
   so a real public `CANCELLED` vector cannot be driven through the facade.

Therefore the smaller proposal—accepting an opaque prebuilt v2 envelope and returning
a transport—would improve ergonomics while knowingly leaving `P00-BTA-01` blocked.
It must not be accepted as Platform closure.

## Proposed minimum product

Freeze one concrete provider:

```text
cash.precomputed_target.development.v1
```

It supports only:

- one cash account and reporting currency;
- one spot instrument;
- precomputed target events supplied by the accepted MarketBundle reader;
- next-eligible-bar-open, full-fill execution;
- the production `DefaultCashFinancialDispatcher`;
- mark-to-market closeout;
- development result grade only;
- no fees, settlement events, derivatives, corporate actions, provider-market claims,
  decision-grade eligibility, deployment authority, or live behavior.

This is the minimum honest producer because the required cash engine and dispatcher
already exist in production. Choosing Binance or China A-share would additionally
require a production financial dispatcher and a materially larger authority freeze.

The product is reasonable only as a permanent standalone reference/conformance
provider for development-grade integration. It is not a temporary fixture promoted
into production and cannot be cited as Binance, China A-share, G12L/G12M, real-market,
or deployment evidence. If the owner requires the first P00 receipt itself to prove a
real market, this proposal must be rejected and replaced by a larger concrete
Binance/China A-share provider gate.

## Decision rule

Approve the cash product when the immediate objective is the accepted P00
**development-grade integration seam**. Reject it when the immediate objective is
**real-market qualification**. Current Platform Integration v1 expects the former:
one adverse development result, one Fill, verified terminal/evidence behavior, and no
positive deployment claim. The recommended decision is therefore approval, subject
to the independent-input constraints above.

## Proposed public seam

After the provider input contract is approved and frozen, add only:

```python
BacktestRequestRef
CashDevelopmentProviderInputs
PreparedBacktestExecution

prepare_cash_development_backtest(
    *,
    request: BacktestRequest,
    provider_inputs: CashDevelopmentProviderInputs,
    artifact_reader: ArtifactEnvelopeReader,
    artifact_publisher: ArtifactEnvelopePublisher,
    market_reader: MarketBundleReader,
    publication_root: Path,
) -> PreparedBacktestExecution
```

```text
BacktestRequestRef@1 = {
  type: "backtest_request_ref",
  artifact_ref: ArtifactRef[backtest_request@1],
}

PreparedBacktestExecution@1 = {
  type: "prepared_backtest_execution",
  schema_version: 1,
  request_ref: BacktestRequestRef,
  semantic_run_id: sha256,
  execution_request: BacktestExecutionRequest@2,
  runtime: BacktestRuntime,
}
```

The operation internally owns profile registration, request resolution, concrete
cash-case production, identity sealing, v2 materialization, request/bundle
publication, returned-ref verification, and facade composition. It exposes no
resolved request, execution case, plan, registry, dispatcher, builder, callback,
path convention, or Platform type.

The exact `CashDevelopmentProviderInputs` fields are intentionally not frozen before
the owner approves this product. The subsequent authority-freeze commit must prove
that every field is a caller-owned economic/provider input rather than a disguised
resolved plan or fixture-case selector.

## Terminal contract to freeze

The implementation must use legitimate semantics rather than `fixture_case` flags:

- `BLOCKED`: public request/profile resolution failure before Attempt creation;
- `FAILED`: a valid cash execution reaches an accepted engine failure, initially an
  order-capability rejection derived from provider capability inputs;
- `CANCELLED`: additive optional `EngineCancellationRequest` propagation through
  `BacktestRuntime.run(..., cancellation=...)` and both retry attempts;
- provider, storage, malformed input, tamper, and binding failures remain exceptions
  before Attempt creation and outside the terminal union.

## Failure precedence

Provider preparation must freeze and test:

1. exact public argument types;
2. request/provider-input semantic validation;
3. market/build/target/spec binding;
4. profile resolution;
5. concrete execution-case composition and identity sealing;
6. v2 materialization and canonical decode verification;
7. request publication and returned-ref verification;
8. execution-input publication and returned-ref verification;
9. runtime construction.

No partial `PreparedBacktestExecution` is returned. Immutable orphan CAS objects may
remain after a later publication failure; no transaction, cleanup protocol, or
second repository is introduced.

## Acceptance gate split

The work is recorded as three separately accepted responsibilities even if it remains
under one BT-GAP-09 plan:

```text
A. provider authority freeze and concrete cash producer
→ B. request registration/preparation plus executable facade
→ C. Platform P00-BTA-01 and P00-SEAM-01 binding
```

A cannot be replaced by a prebuilt-envelope wrapper. B cannot claim provider closure
without A. C remains Platform-owned and cannot be claimed by Backtest tests.

## Execution phases

### Phase 1 — provider authority decision and freeze

1. Approve or reject `cash.precomputed_target.development.v1`.
2. Freeze exact provider input fields and one-instrument/one-fill ceiling.
3. Freeze completed, blocked, failed, and cancelled semantic vectors.
4. Freeze request/build/market/target/spec identity sources.
5. Record unchanged v1/v2 fixture hashes.

### Phase 2 — RED tests

1. Public preparation signature exposes no resolved/plan/builder type.
2. Clean-installed public roots produce a v2 transport without importing `tests`.
3. Returned request ref binds the exact persisted `backtest_request@1`.
4. Completed execution and analysis produce `-0.1`, one Fill, development grade.
5. Same request/context replays to identical request, semantic-run, retry, cache,
   publication, and analysis identities.
6. Legitimate BLOCKED, FAILED, and CANCELLED paths publish durable terminal evidence.
7. Preparation faults create no Attempt or terminal evidence.
8. Architecture guards reject Platform/Foundation implementation imports,
   `tests/support`, adapters, Protocols, factories, callbacks, second catalogs,
   registries, and repositories.

### Phase 3 — provider and preparation implementation

Expected production write set:

- `packages/backtest-runtime/src/crypto_quant_backtest/cash_development_provider.py`
- `packages/backtest-runtime/src/crypto_quant_backtest/request_registration.py`
- additive exports in `packages/backtest-runtime/src/crypto_quant_backtest/__init__.py`
- narrowly scoped cancellation propagation in `facade.py`

Do not move or import test fixture builders. Reuse existing production engine,
composer, materializer, dispatcher, identity factory, publisher, and reader.

### Phase 4 — Backtest acceptance

Run focused provider/facade/boundary tests, all inherited BT-GAP tests, fixture-hash
checks, full repository, import boundaries, lock/diff/LSP/lens/secret checks,
independent review, and clean-install validation. Record a new clean lowercase
40-character accepted SHA.

### Phase 5 — Platform fan-in

Platform pins that exact SHA, adds
`tests/integration/test_backtest_public_binding.py`, binds Foundation structural
reader/publisher through public roots only, runs unchanged BT-PORT vectors, and
records `P00-BTA-01` then `P00-SEAM-01`. Backtest does not create Platform admission,
Research, Validation, Promotion, or fan-in receipts.

## Rejected alternatives

- **Registration/preparation wrapper only:** still lacks an installed producer.
- **Generic execution-plan public type:** transfers prohibited resolved construction
  to callers and creates a second plan product.
- **Promote test-support Binance/China A-share builders:** copies fixture economics
  and test-only dispatchers into production.
- **Implement Binance/China A-share first:** requires a new production dispatcher and
  is larger than the cash development path.

## Immutable exclusions

No accepted v1 bytes/API changes; no provider adapter framework; no second simulator,
registry, repository, SchemaCatalog, verifier, cache, database, queue, deployment, or
Platform import. The provider is explicitly development-only and cannot qualify real
market, decision-grade, or deployment claims.
