# G11J Precomputed-vs-Strategy Parity Research

## Decision status

G11J remains `DRAFT` in `docs/implementation/acceptance-matrix.md`. Its smallest valid v1 seam is repository-root parity tooling over a test-owned dual-entry fixture. No Engine, Runner, Timeline, TargetStream, Trading Kernel, or package export change is required.

The fixture normalizes both entry mechanisms at the first source-neutral economic value they already share: the complete ordered validated `TargetSnapshot` tuple. It then binds both legs to independently composed equal `ResolvedExecutionCase` values and exact-compares the existing Engine and G07 authorities. The CLI report is equality evidence for the supplied projections, not authentication of their origin.

## Primary authorities

- `packages/backtest-runtime/src/crypto_quant_backtest/strategy_runtime.py:696-900` invokes G11I Strategies, uses the existing `StrategyOutputValidator`, and calls the existing `AtomicDecisionBatchCollector` once on Active success.
- `packages/backtest-runtime/src/crypto_quant_backtest/target_stream.py:482-569` decodes precomputed Candidates, uses the same Validator and Collector, and publishes the existing target-stream injection.
- `packages/trading-kernel/src/crypto_quant_trading/validation.py:177-257` constructs the validated `StrategyDecision` and its `TargetSnapshot`; confidence, reason, and Decision evidence remain part of the validated Decision and are not stripped or rewritten.
- `packages/backtest-runtime/src/crypto_quant_backtest/engine.py:1406-1504` defines the authoritative Engine result fields.
- `packages/backtest-runtime/src/crypto_quant_backtest/execution_hash.py:48-126` defines the attempt-independent `CanonicalExecutionSummary` and G07 execution-result hash.
- `tools/migration/legacy_migration/parity.py:145-404` owns Comparator Contract v1 validation, exact/sequence comparison, complete field classification, and first-divergence reporting.

## Frozen normalization seam

The source-neutral Candidate is the existing synthetic cash `target_payload()` from `tests/runtime/engine/_fixtures.py`. It contains fixed confidence, reason, and model-revision evidence; it does not derive Decision evidence from a G11I invocation `context_hash`.

The two entries are:

1. **Precomputed:** the existing `PrecomputedTargetStreamAdapter` validates the target event and collects its atomic batch.
2. **Strategy:** one minimal offline Strategy returns the same Candidate through `invoke_portfolio_strategies(...)`, with an empty observation/window/RNG/model set, one static synthetic Universe, and one genesis checkpoint.

Both validated Decisions therefore contain exactly equal `TargetSnapshot` values. Their source `DecisionBatch` identities intentionally differ today:

- precomputed collection uses legacy `decision-batch-v1` because the target schedule validation context has no full `SimulationInstant`;
- G11I collection uses `decision-batch-v2` and binds the full schedule instant.

G11J treats those source batch IDs/hashes as entry evidence, not as downstream economics. It does not hide or rewrite them inside the compared projection. Tests record them in an explicit sidecar and prove that they differ while the validated TargetSnapshots match exactly.

Layer 00 also freezes the complete source-neutral validated Decisions: strategy ID, UTC decision and observation times, TargetSnapshot, confidence, reason, and Decision evidence must all match. Normalization changes only the precomputed Decision's absent transport-level `decision_instant` to the shared target event full instant; the Strategy Decision already carries that same instant. This prevents equal target weights from masking confidence, reason, or evidence drift.

After snapshot normalization, both legs bind the same exact decision instant, Semantic Run ID, execution-case hash, target event, and independently composed equal `ResolvedExecutionCase`. The existing Engine then forms its normal precomputed target-stream batch and executes one branchless downstream path for each leg.

## Exact parity layers

Comparator rules are lexically sorted and use only `exact` or type-sensitive exact `sequence` comparison:

```text
00_NORMALIZED_ENTRY
01_DECISION_BATCH
02_ALLOCATION
03_PORTFOLIO_RISK
04_NORMALIZED_ACTIVE_TARGET
05_ORDER_PLAN_INTENT
06_ORDER_EVENT
07_FILL
08_SLIPPAGE
09_FEE
10_FINANCIAL_ARTIFACT
11_JOURNAL
12_LEDGER
13_FINAL_SNAPSHOT
14_RUN_END
15_TRACE
16_EXECUTION_RESULT_HASH
```

The layers exact-cover every authoritative `EngineExecutionResult` field except top-level target-stream transport provenance, which is excluded before comparison. Layer 16 contains the Engine result hash, G07 execution-result hash, Trace hash, Journal hash, Ledger state hash, final Snapshot hash, and Run End report hash.

Numeric prefixes freeze first-divergence order. A later Trace or aggregate hash difference cannot hide an earlier Allocation, Risk, order, fill, fee, or accounting difference. Sequence mismatches report the first zero-based item index. There is no tolerance, quantization, epsilon, `approved_change`, ignore rule, or not-comparable row.

## Entry and attempt evidence outside economic layers

Only explicit source/operational evidence stays outside the projection:

- precomputed TargetStream digest, schedule hash, source event IDs/hashes, and injection hash;
- Strategy schedule/eligibility, artifact, checkpoint, context, invocation, state-transition, output, and handoff hashes;
- the differing source v1/v2 DecisionBatch IDs and hashes;
- G07 Attempt IDs, Evidence Manifest hashes, and evidence directories.

G07 still executes and publishes two real attempts of the normalized semantic case. The existing Runner requires `InputOrigin` to match the resolved request's Strategy family, so both post-normalization attempts retain the case's existing precomputed input origin; G11J does not add a Runner origin branch. Attempt and Evidence identities are distinct, while Semantic Run ID, execution-case hash, domain identities, and bound execution-result hash are equal. Existing G07 canonical publication selects one canonical Result only after the equal execution hashes pass integrity evaluation.

## Tool and failure contract

`tools/parity/precomputed_strategy.py` is a thin wrapper over `legacy_migration.parity.run_comparison(...)` with fixed `migration_mode="copy_with_parity"`. Its CLI accepts only:

```text
--root --contract --expected --actual --report
```

The tool imports only stdlib plus the existing comparator. Test support owns Runtime, Kernel, Engine, and G07 projection generation.

Failure precedence is:

1. unsafe paths: `status=blocked`, `verdict=BLOCKED`, exit `2`;
2. malformed, unclassified, or otherwise invalid contract/projection: `status=invalid-contract`, `verdict=BLOCKED`, exit `2`;
3. first differing numbered layer: `status=completed`, `verdict=MISMATCH`, exit `1`;
4. all exact layers equal: `status=completed`, `verdict=MATCH`, exit `0`.

Qualification remains `decision_grade_eligible=false` and `deployment_authorized=false`.

A copied-fixture-root golden regression proves that report content does not depend on the repository checkout path. The architecture boundary also freezes the contract, requires direct reuse of the existing comparator helpers, and rejects G11J production modules or public exports.

## Assurance boundary

The CLI does not regenerate the projections, consume `sidecar.json`, or authenticate that `expected.json` came from precomputed entry and `actual.json` came from Strategy entry. Two identical substituted or malicious files that satisfy the frozen shape can therefore produce `MATCH`. The separate dual-entry fixture-generation test executes both entry mechanisms and checks their generated projections and sidecar against the checked-in fixtures; that test is the implementation link to those entry paths, not a provenance guarantee supplied by the comparator report itself.

## Explicit exclusions

- no production exact-instant TargetStream migration in G11J v1;
- no Engine/Runner/Timeline/TargetStream branch for Strategy entry;
- no second Validator, batch collector, comparator, projection framework, or economic implementation;
- no comparison of raw Strategy invocation evidence against TargetStream transport evidence;
- no use of tolerance or approved semantic-change masking;
- no cryptographic or adversarial provenance claim for supplied projection files;
- no decision-grade, live, or deployment authorization claim.
