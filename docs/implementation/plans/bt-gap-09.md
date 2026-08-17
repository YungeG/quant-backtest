---
id: BT-GAP-09
status_source: ../acceptance-matrix.md
owner: backtest-runtime public provider preparation
produces:
  - installable cash.precomputed_target.development.v1 provider
  - CashDevelopmentRequestIntent
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

`PASSED` at accepted package revision
`e3c04fb612d6798aef1420b60864d4f315ed12ac` (package implementation
`a014e9389f36b6696653606c5ebcb845cabe9f24`). The installable
development-only reference provider, request registration/preparation seam,
additive no-fee authority, terminal finality, and cancellation entry point passed
clean-install, full-repository, boundary, and independent review acceptance.

## First-principles authority chain

The required independent flow is:

```text
opaque Platform context → public CashDevelopmentRequestIntent
concrete provider external facts → CashDevelopmentProviderInputs
                    ↓
Backtest-produced unsealed cash case and semantic spec
→ Backtest-derived immutable BacktestRequest@1
→ Backtest validation/persistence and BacktestRequestRef
→ identity-sealed Backtest-owned executable case
→ canonical v2 execution-input envelope
→ BacktestRuntime execution and evidence
→ Platform governance admission
```

Every arrow requires one installed authority. The missing arrow is not merely request
registration; it is `concrete provider external facts → executable case`. The accepted
v2 materializer and decoder begin after that transition and therefore cannot produce
it.

Independence means:

1. Platform constructs only the concrete provider request intent and passes opaque
   context; it derives no Backtest request hash, semantic hash, target digest, build
   binding, execution plan, metric, terminal, or evidence hash.
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

## Frozen public seam

Add only:

```python
CashDevelopmentRequestIntent
BacktestRequestRef
CashDevelopmentProviderInputs
PreparedBacktestExecution

prepare_cash_development_backtest(
    *,
    request_intent: CashDevelopmentRequestIntent,
    provider_inputs: CashDevelopmentProviderInputs,
    artifact_reader: ArtifactEnvelopeReader,
    artifact_publisher: ArtifactEnvelopePublisher,
    market_reader: MarketBundleReader,
    publication_root: Path,
) -> PreparedBacktestExecution
```

```text
CashDevelopmentRequestIntent@1 = {
  type: "cash_development_request_intent",
  schema_version: 1,
  experiment_id: canonical text | null,
  timeline_window: TimelineWindow,
  execution_account_id: canonical text,
  reporting_currency: CurrencyId,
  master_random_seed: non-negative integer,
}

BacktestRequestRef@1 = {
  type: "backtest_request_ref",
  artifact_ref: ArtifactRef[backtest_request@1],
}

```

`PreparedBacktestExecution` is an in-process immutable Python value containing
`request_ref`, `semantic_run_id`, `execution_request`, and the configured
`BacktestRuntime`. It has no canonical wire, schema version, ArtifactEnvelope, or
persistence identity because the runtime handle is process-local.

The intent deliberately omits profile keys, market-bundle ref, target digest,
execution-case semantic hash, build-manifest hash, strategy family, engine kind, and
result grade. The provider fixes or derives them and creates the exact immutable
`BacktestRequest@1` before registration. This is the additive contract correction
required because callers cannot know `execution_case_semantic_hash` before Backtest
has produced the execution case.

The operation internally owns request materialization, profile registration, request
resolution, concrete cash-case production, identity sealing, v2 materialization,
request/bundle publication, readback verification, and facade composition. Before
publication the v2 envelope must round-trip the existing package-private execution-
input `SchemaCatalog`. After publishing request and bundle, preparation exact-reads
both through the injected structural reader and verifies exact `ArtifactReadResult`,
canonical source bytes/hash, envelope equality, and ref equality before returning.
Drop, substitution, or malformed readback returns no prepared authority. It exposes no
resolved request, execution case, plan, registry, dispatcher, builder, callback,
path convention, or Platform type.

## Frozen provider-input contract

```text
CashDevelopmentProviderInputs@1 = {
  type: "cash_development_provider_inputs",
  schema_version: 1,
  build_artifact_manifest: BuildArtifactManifest,
  instrument_catalog: InstrumentCatalog,
  strategy_id: canonical text,
  sleeve_id: StrategySleeveId,
  initial_cash: Money,
  quantity_lattice: QuantityLattice,
  decision_mark: MarkObservation,
  final_mark: MarkObservation,
  order_capabilities: OrderCapabilitySet,
}
```

These nine fields are external build, market, strategy, capital, lattice, observed
price, and venue-capability facts. `build_artifact_manifest` is the caller-owned base
manifest: callers neither know nor construct this provider's profile digests. After
deriving the fixed registry, preparation deterministically adds exactly three
`PROFILE_COMPONENT` `BuildArtifactRef` values for the provider market, simulation, and
account profile keys, using profile version, WHEEL/CLEAN identity, and each derived
profile digest. Other caller artifacts, runtime libraries, lock/image identity,
build key, and provenance are preserved exactly. An exact existing provider ref is
idempotent; any caller artifact with a provider profile key and different fields fails
before publication. The final enriched manifest hash, not the base hash, binds the
immutable request and v2 bundle.

The provider owns fixed stale policies and derives
both `ResolvedMark` values at the target decision time and request end-exclusive. It
also derives every registry entry, policy, timeline,
decision cycle, order, admission, reservation, accounting plan, snapshot plan,
identity rule, semantic spec, and runtime value. None of those internal authorities
may be added to the public input later without a new version and owner review.

Validation freezes these bindings:

1. the enriched build manifest hash equals the public request commitment, contains
   the three deterministic provider profile refs, and otherwise exact-preserves the
   caller base manifest;
2. the instrument catalog hash equals the MarketBundle manifest commitment and
   contains exactly one SPOT instrument plus its currencies;
3. initial cash is positive and denominated in the request reporting currency;
4. lattice and both marks reference the sole instrument;
5. both observations use `PricePurpose.VALUATION` and quote the reporting currency;
   the decision observation has `observed_at == available_at == target decision time`
   and resolves there with `max_age_nanoseconds=0`, `allow_forward_fill=false`; the
   final observation has `observed_at < request end_exclusive` and
   `available_at <= request end_exclusive`, then resolves at end-exclusive with
   `allow_forward_fill=true` and `max_age_nanoseconds` exactly equal to
   `end_exclusive - observed_at`; this bounded close carry is provider-owned and keeps
   the accepted RunEnd rule that valuation marks must precede the boundary;
6. the public request selects the provider's fixed market, simulation, and account
   profile keys and requests development grade;
7. the target stream contains exactly one active target event for the frozen strategy
   and sleeve, exactly one positive long target for the sole instrument, and no
   warmup, revision conflict, second sleeve, or second instrument;
8. the bar stream contains exactly one eligible real bar-open event after the target
   and before end-exclusive;
9. order capabilities are preserved as provider facts so a missing MARKET capability
   produces the legitimate engine `CAPABILITY_REJECTED` / `BLOCKED` vector rather
   than a fixture selector.

## Frozen semantic ceiling

The provider owns fixed stream keys `targets` and `bars.open`, timeline batch size
one, one target decision, one order, at most one full fill, zero slippage, explicit
no-fee assessment,
no pre-existing position, no external cash flow after the initial deposit, permissive
cash market rules derived from the lattice, no settlement delay, no financing,
no margin, no liquidation, and mark-to-market final closeout. Target sizing uses the
decision mark; execution uses the bar open; final valuation uses the final mark.

A completed case must contain exactly one Fill. Inputs that would require a second
order/fill, shorting, partial fill, multiple instruments/accounts/currencies,
settlement, fees, financing, corporate actions, or a second target are rejected before
Attempt creation rather than silently approximated.

The worked P00 vector is input-derived, not hard-coded: initial equity `100000`, target
weight `0.5`, decision/fill price `100`, and final mark `80` produce ending equity
`90000`, `simple_period_return = "-0.1"`, and `trade_count = 1`.

## Additive no-fee accounting authority

Concrete market providers own versioned market, tax, and account fee rule authorities.
This provider is market-neutral and must not borrow Binance, China A-share, broker, or
exchange rates. Its `FinalFeeRuleSet` explicitly marks every Fill-basis charge as
`NOT_APPLICABLE`; `FeeAssessmentEngine` therefore produces an authoritative zero-unit
`FinalFeeAssessmentResult`.

The additive engine rule is:

1. persist/trace the exact zero assessment as fee evidence;
2. when `assessment.amount.units == 0`, perform no fee Journal mutation and do not call
   `DefaultCashFinancialDispatcher.book_fee()`;
3. retain the post-fill Ledger state and project final fees as zero;
4. positive assessments continue through the frozen existing fee accounting path
   byte-for-byte and behavior-for-behavior.

No second dispatcher, accounting engine, plan schema, fee rule engine, or provider fee
source is introduced. This also matches existing Binance G10F authority, which permits
exact zero commission rates while rejecting negative rebates.

## Frozen terminal contract

The implementation must use legitimate semantics rather than `fixture_case` flags:

- `BLOCKED`: a structurally valid provider capability set lacks MARKET execution,
  producing the accepted `CAPABILITY_REJECTED` engine mapping;
- `CANCELLED`: additive `BacktestRuntime.run_with_cancellation(request,
  cancellation)` preserves existing `run(request)` unchanged and propagates one
  `EngineCancellationRequest` to the Attempt actually executed;
- provider, storage, malformed input, tamper, and binding failures remain exceptions
  before Attempt creation and outside the terminal union.

`FAILED` is outside the real cash-provider generation scope. The production runner
maps it to allocation/risk/rebalance/plan/accounting/internal-contract failure classes;
a well-formed minimal provider must not expose a switch that fabricates one of those
defects. Platform approved the first-principles acceptance rule: the real provider
binding proves COMPLETED/BLOCKED/CANCELLED, while immutable BT-PORT and accepted
Backtest repository evidence continue to prove FAILED verification. No failure
injection field, inconsistent plan, or failure-conformance product is added.

## Failure precedence

Provider preparation must test in this order:

1. exact public argument types;
2. request-intent/provider-input semantic validation;
3. market/target observation binding and concrete case/profile derivation;
4. caller/provider profile-key conflict rejection and deterministic build-manifest
   enrichment;
5. immutable `BacktestRequest@1` materialization and profile resolution;
6. identity sealing, v2 materialization, and existing-catalog round-trip;
7. request then execution-input publication and returned-ref verification;
8. exact structural readback of both persisted envelopes;
9. runtime construction.

No partial `PreparedBacktestExecution` is returned. Immutable orphan CAS objects may
remain after a later publication/readback failure; no transaction, cleanup protocol,
or second repository is introduced.

## Terminal finality and cache order

The exact first Attempt is the only terminal Attempt for a semantic run. Before any
execution, the facade checks its deterministic Attempt directory. If a terminal
manifest exists, it exact-reads canonical local bytes, verifies the mirrored graph
through `BacktestEvidenceRepository`, and returns the same bare manifest ref without
republishing or allocating another ordinal. BLOCKED/FAILED/CANCELLED are final across
repeated calls and across `run`/`run_with_cancellation` ordering.

A completed canonical-v2 publication remains final through the existing cache. A
later cancellation request must exact-verify that cache and fail closed; it cannot
convert or return COMPLETED for a cancellation call. No terminal registry, alternate
Attempt numbering, or hidden state is introduced.

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

Completed by the owner approval and this readiness contract. Existing frozen v1/v2
fixture hashes must be captured by the RED suite before production edits.

### Phase 2 — RED tests

1. Public preparation signature exposes no resolved/plan/builder type.
2. Clean-installed public roots produce a v2 transport without importing `tests`.
3. Returned request ref binds the exact persisted `backtest_request@1`.
4. Completed execution and analysis produce `-0.1`, one Fill, development grade.
5. Same request/context replays to identical request, semantic-run, retry, cache,
   publication, and analysis identities.
6. Legitimate BLOCKED and CANCELLED paths publish durable terminal evidence; FAILED
   remains covered by immutable BT-PORT and accepted Backtest repository evidence.
7. Preparation faults create no Attempt or terminal evidence.
8. Architecture guards reject Platform/Foundation implementation imports,
   `tests/support`, adapters, Protocols, factories, callbacks, second catalogs,
   registries, and repositories.

### Phase 3 — provider and preparation implementation

Expected production write set:

- `packages/backtest-runtime/src/crypto_quant_backtest/cash_development_provider.py`
- `packages/backtest-runtime/src/crypto_quant_backtest/request_registration.py`
- additive exports in `packages/backtest-runtime/src/crypto_quant_backtest/__init__.py`
- additive `run_with_cancellation` implementation in `facade.py`, preserving `run`

Do not move or import test fixture builders. Reuse existing production engine,
composer, materializer, dispatcher, identity factory, publisher, and reader.

### Phase 4 — Backtest acceptance

Run focused provider/facade/boundary tests, all inherited BT-GAP tests, fixture-hash
checks, full repository, import boundaries, lock/diff/LSP/lens/secret checks,
independent review, and clean-install validation. Record a new clean lowercase
40-character accepted SHA.

### Phase 5 — Platform fan-in

Platform pins accepted source SHA `e3c04fb612d6798aef1420b60864d4f315ed12ac`, adds
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

## Acceptance closure

- accepted source revision: `e3c04fb612d6798aef1420b60864d4f315ed12ac`;
- package implementation revision: `a014e9389f36b6696653606c5ebcb845cabe9f24`;
- clean detached worktree: `/tmp/backtest-provider-seam-clean`;
- clean install/public roots: five workspace packages plus all BT-GAP-09 symbols;
- focused final provider/facade/engine: 43 passed;
- broad focused provider/runtime/repository/architecture: 223 passed;
- clean full repository: 1793 passed;
- import boundaries: 111 files passed;
- unchanged Platform BT-PORT: 15 passed;
- lock, diff, compile, LSP, lens, gitleaks/secret scan, and final status: clean;
- frozen BT-GAP-02/02B/02C fixture SHA-256 values unchanged;
- independent final reviews: `NONE` (`d2229a65`, `bce4c4da`, `eea3121a`).
- `BacktestEvidenceRepository.load_terminal()` acceptance publishes a real FAILED
  Attempt evidence graph through `AttemptEvidenceWriter`, reloads every reachable
  child through the structural reader, and returns exact `TerminalStatus.FAILED`.
- `BacktestAnalysisRuntime.publish_metric_profile()` publishes and returns the exact
  accepted opaque `backtest_metric_profile@1` ref; Platform constructs no metric
  profile payload.

This closes only the Backtest-owned provider/preparation dependency. Platform still
owns the real Foundation binding, `P00-BTA-01`, and `P00-SEAM-01` receipts.
