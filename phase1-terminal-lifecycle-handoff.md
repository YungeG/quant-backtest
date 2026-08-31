# Phase 0–1 terminal lifecycle handoff

Implemented baseline preservation and additive engine terminal lifecycle only.

## Scope delivered

- Added identity-bound `ResolvedOrderTerminalPlanV1` and `ResolvedOrderCancellationPlanV1`.
- Added additive `ResolvedPortfolioBarExecutionV2` and `ResolvedPortfolioDecisionCycleV2` carriers without changing legacy canonical bodies.
- DAY exhausted no-fill decisions append `ORDER_EXPIRED`, replace the order stream, refresh resources, and trace the terminal stream plus reservation/availability state.
- Target-driven cancellations append `ORDER_CANCEL_REQUESTED` then `ORDER_CANCELLED` at the same UTC decision time with strictly increasing phases, refresh resources, and preserve financial state.
- Legacy cycles still reject cancellation intents unless the additive V2 cancellation plans exact-cover them.
- No supersession transaction, snapshot refresh, sizing/capping, portfolio profile, V7 codec, provider, or cash-development provider changes were made.

## Changed files

- `packages/backtest-runtime/src/crypto_quant_backtest/engine.py`
- `packages/backtest-runtime/src/crypto_quant_backtest/__init__.py`
- `tests/runtime/engine/test_order_terminal_lifecycle_v2.py`
- `phase1-terminal-lifecycle-handoff.md`

## Focused tests

`tests/runtime/engine/test_order_terminal_lifecycle_v2.py` covers:

1. DAY no-fill expiry becomes `EXPIRED`, releases its active reservation, leaves cash and positions unchanged, and emits terminal/resource traces.
2. GTC no-fill remains accepted/working and reserved.
3. Target cancellation emits `ORDER_CANCEL_REQUESTED` then `ORDER_CANCELLED` at phases 90/91, releases its reservation, and leaves cash and positions unchanged.

## Baseline and preservation evidence

Baseline before edits:

```text
122 passed in 22.23s
```

Focused plus legacy engine/rebalance validation:

```text
13 passed in 2.16s
49 passed in 33.27s
```

Preservation gate after the implementation commit, with a clean worktree:

```text
125 passed in 21.99s
```

The same preservation selection was also run before committing while the tree was dirty. Its two fixed-singleton architecture write-set tests failed only because those tests intentionally reject any unrelated dirty paths; all other 123 tests passed. The clean-tree preservation rerun above passed all 125 tests.

`ruff` was unavailable in the environment (`Failed to spawn: ruff`). `git diff --check` passed, and all edited Python was imported/executed by the focused and preservation suites.

## Frozen fixture SHA-256 values

```text
09578ac47f997bc4bf55119d31e97dbcad3eb71e90d93a5ef7c8e6669bd66be2  tests/fixtures/runtime/bt-gap02b-execution-input-bundle-v1.json
c082042640382dde2dad61f758058ab93c3ba741ed19df0256d7989a157eced1  tests/fixtures/runtime/bt-gap02c-execution-closure-v2.json
ac17536771914f599b3ea58f936049208f29b3f707815456e5b763d0762e5179  tests/fixtures/runtime/bt-gap02b-execution-input-bundle-v3.json
58d2dab674acace62c2a8cf92393c01385b76cf92dec33c0c4f014bb4c0a012c  tests/fixtures/runtime/execution-input-bundle-v4/equity.json
63a1df61db13093af30e64820f382d7abe33315f0d28fe5a87ab2a9eb26b0759  tests/fixtures/runtime/engine/g12m-tushare-market-engine-journey-v1.json
9cbe91becf64053fdb44cb884a8cfd621e020e8ce54e4f5f6f76411f275e3c79  tests/fixtures/runtime/bt-gap04-publication-ref-v1.json
1f88bb2b3260bfc80bb375e2d877ae18d5e049c80e0682f5ecbc0d137cbbd980  tests/fixtures/runtime/precomputed-target-stream-injection-v1.json
b463238c2aa830f1de0386a825e47fc523fe21f2dca7d0374e5e7cbf23c1c7c1  tests/fixtures/kernel/rebalance-coordination-v1.json
08358c1c0d2144fb23c1b1c8862fa6c879bd285533e5fa415e5cc0273013e905  tests/fixtures/runtime/engine/cn-a-share-resolved-profile-development-journey-v1.json
```

## Independent-review blocker repair

The two blockers from `phase1-independent-review.md` were repaired without starting Phase 2:

- Cancellation plans now require authoritative phases `90/order_cancel_requested` and `91/order_cancelled`, with one shared source sequence.
- The engine derives canonical instrument order from cancellation intents and requires one-based source sequences in that order.
- All phase-90 request streams/events are prebuilt first, followed by all phase-91 completion streams/events.
- Every source stream, reason, target hash, decision time, sequence, event transition, causation, final reservation projection, settlement projection, and availability projection is preflighted before state or trace mutation.
- Commit occurs only after complete preflight: all request streams/traces, then all cancelled streams/traces, then the precomputed resource state.
- Added a two-instrument ordering test and a later-invalid-plan test that proves stream, trace, reservation, settlement, and availability state remain unchanged.

Repair validation:

```text
Focused lifecycle: 5 passed in 1.17s
Runtime engine: 51 passed in 33.96s
Clean-tree preservation: 127 passed in 23.02s
```

## Residual risks / deferred work

- Phase 5 still owns the dedicated V2 execution case and V7 materialization/codec. Phase 1 uses the approved additive V2 cycle/bar values under the existing in-memory case carrier.
- A future case builder/provider must pre-resolve the exact no-fill decision hash used by terminal plans.
- Atomic cancel/replace and replacement causation remain deliberately unimplemented until Phase 4.
- Independent reviewer re-approval remains required by the acceptance gate.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Repaired only canonical multi-instrument cancellation ordering and transactional preflight/commit. No Phase 2, provider, codec, profile, sizing, snapshot, supersession, legacy canonical, or cash_development_provider.py work was added."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Five focused lifecycle tests, 51 runtime-engine tests, and the 127-test clean-tree preservation gate passed; the new tests directly prove canonical two-order event ordering and zero mutation after a later invalid plan."
    }
  ],
  "changedFiles": [
    "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    "tests/runtime/engine/test_order_terminal_lifecycle_v2.py",
    "phase1-terminal-lifecycle-handoff.md"
  ],
  "testsAddedOrUpdated": [
    "tests/runtime/engine/test_order_terminal_lifecycle_v2.py"
  ],
  "commandsRun": [
    {
      "command": "uv run pytest -q tests/runtime/engine/test_order_terminal_lifecycle_v2.py",
      "result": "passed",
      "summary": "5 passed in 1.17s."
    },
    {
      "command": "uv run pytest -q tests/runtime/engine",
      "result": "passed",
      "summary": "51 passed in 33.96s."
    },
    {
      "command": "uv run pytest -q tests/runtime/providers/test_cash_development_provider.py tests/runtime/providers/test_model_bound_cash_development_provider.py tests/runtime/target_stream tests/runtime/profiles/cn_a_share tests/architecture/test_cn_a_share_fixed_singleton_no_trade_profile_boundary.py tests/architecture/test_cn_a_share_fixed_singleton_no_trade_profile_v2_boundary.py tests/runtime/engine/test_g08h_cn_a_share_golden.py tests/kernel/rebalance/test_rebalance_coordinator.py tests/kernel/rebalance/test_rebalance_coordinator_golden.py tests/runtime/engine/test_order_terminal_lifecycle_v2.py",
      "result": "passed",
      "summary": "Clean-tree preservation gate: 127 passed in 23.02s."
    },
    {
      "command": "git diff --check",
      "result": "passed",
      "summary": "No whitespace errors."
    }
  ],
  "validationOutput": [
    "Two-instrument trace order is request(BTC), request(ETH), cancelled(BTC), cancelled(ETH), resource refresh, with phases 90/90/91/91 and source sequences 1/2/1/2.",
    "A later invalid cancellation plan leaves all order stream hashes, trace entries, reservation hash, availability hash, and settlement hash unchanged.",
    "Existing DAY expiry, GTC persistence, and single-order cancellation tests remain passing.",
    "Runtime engine suite: 51 passed in 33.96s.",
    "Clean-tree preservation gate: 127 passed in 23.02s.",
    "No diff in packages/backtest-runtime/src/crypto_quant_backtest/cash_development_provider.py."
  ],
  "residualRisks": [
    "Independent reviewer re-approval is still required.",
    "Dedicated V2 case/V7 codec, snapshot refresh, capping, profile/provider, and atomic supersession remain deferred by scope."
  ],
  "noStagedFiles": true,
  "diffSummary": "Enforce authoritative cancellation phases and canonical instrument source sequences; preflight all multi-order stream/event/resource transitions before committing phase-90 requests, phase-91 completions, and refreshed resources; add two focused regression tests.",
  "reviewFindings": [
    "repaired blocker: canonical cancellation ordering across instruments",
    "repaired blocker: no partial mutation when a later cancellation plan fails",
    "review gate pending independent re-review"
  ],
  "manualNotes": "Fix committed locally with no push. phase1-independent-review.md remains an unmodified reviewer-provided artifact."
}
```
