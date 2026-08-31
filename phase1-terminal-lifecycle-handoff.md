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

## Residual risks / deferred work

- Phase 5 still owns the dedicated V2 execution case and V7 materialization/codec. Phase 1 uses the approved additive V2 cycle/bar values under the existing in-memory case carrier.
- A future case builder/provider must pre-resolve the exact no-fill decision hash used by terminal plans.
- Atomic cancel/replace and replacement causation remain deliberately unimplemented until Phase 4.
- Independent reviewer approval remains required by the acceptance gate.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Only additive terminal/cancellation plans, V2 cycle/bar carriers, engine lifecycle mutation/resource refresh, exports, and focused tests were added. Forbidden provider, V7, profile, capping, snapshot-refresh, supersession, legacy canonical bodies, and cash_development_provider.py work was not changed."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Focused tests passed, the clean-tree preservation gate passed 125 tests, exact fixture SHA-256 values are recorded, changed files and commands are listed, and the implementation is committed without push."
    }
  ],
  "changedFiles": [
    "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    "packages/backtest-runtime/src/crypto_quant_backtest/__init__.py",
    "tests/runtime/engine/test_order_terminal_lifecycle_v2.py",
    "phase1-terminal-lifecycle-handoff.md"
  ],
  "testsAddedOrUpdated": [
    "tests/runtime/engine/test_order_terminal_lifecycle_v2.py"
  ],
  "commandsRun": [
    {
      "command": "uv run pytest -q tests/runtime/providers/test_cash_development_provider.py tests/runtime/providers/test_model_bound_cash_development_provider.py tests/runtime/target_stream tests/runtime/profiles/cn_a_share tests/architecture/test_cn_a_share_fixed_singleton_no_trade_profile_boundary.py tests/architecture/test_cn_a_share_fixed_singleton_no_trade_profile_v2_boundary.py tests/runtime/engine/test_g08h_cn_a_share_golden.py tests/kernel/rebalance/test_rebalance_coordinator.py tests/kernel/rebalance/test_rebalance_coordinator_golden.py",
      "result": "passed",
      "summary": "Baseline before edits: 122 passed in 22.23s."
    },
    {
      "command": "uv run pytest -q tests/runtime/engine/test_order_terminal_lifecycle_v2.py tests/runtime/engine/test_engine_harness.py tests/kernel/rebalance/test_rebalance_coordinator_golden.py",
      "result": "passed",
      "summary": "13 passed in 2.16s."
    },
    {
      "command": "uv run pytest -q tests/runtime/engine",
      "result": "passed",
      "summary": "49 passed in 33.27s."
    },
    {
      "command": "uv run pytest -q tests/runtime/providers/test_cash_development_provider.py tests/runtime/providers/test_model_bound_cash_development_provider.py tests/runtime/target_stream tests/runtime/profiles/cn_a_share tests/architecture/test_cn_a_share_fixed_singleton_no_trade_profile_boundary.py tests/architecture/test_cn_a_share_fixed_singleton_no_trade_profile_v2_boundary.py tests/runtime/engine/test_g08h_cn_a_share_golden.py tests/kernel/rebalance/test_rebalance_coordinator.py tests/kernel/rebalance/test_rebalance_coordinator_golden.py tests/runtime/engine/test_order_terminal_lifecycle_v2.py",
      "result": "passed",
      "summary": "Clean-tree preservation gate: 125 passed in 21.99s."
    },
    {
      "command": "git diff --check",
      "result": "passed",
      "summary": "No whitespace errors."
    },
    {
      "command": "uv run ruff check packages/backtest-runtime/src/crypto_quant_backtest/engine.py packages/backtest-runtime/src/crypto_quant_backtest/__init__.py tests/runtime/engine/test_order_terminal_lifecycle_v2.py",
      "result": "failed",
      "summary": "ruff is not installed in the environment; no lint process was spawned."
    }
  ],
  "validationOutput": [
    "Baseline: 122 passed in 22.23s.",
    "Focused/legacy sentinel: 13 passed in 2.16s.",
    "Runtime engine suite: 49 passed in 33.27s.",
    "Clean-tree preservation gate: 125 passed in 21.99s.",
    "git diff --check passed.",
    "No diff in packages/backtest-runtime/src/crypto_quant_backtest/cash_development_provider.py."
  ],
  "residualRisks": [
    "ruff was unavailable, so lint validation was not run.",
    "Independent reviewer approval is still required.",
    "Dedicated V2 case/V7 codec, snapshot refresh, capping, profile/provider, and atomic supersession remain deferred by scope."
  ],
  "noStagedFiles": true,
  "diffSummary": "Add identity-bound DAY expiry and target cancellation plans, additive V2 cycle/bar carriers, deterministic terminal event mutation and resource refresh traces, public exports, and three focused engine lifecycle tests; preserve legacy canonical paths.",
  "reviewFindings": [
    "no implementation blockers found in focused self-review",
    "review gate pending independent reviewer"
  ],
  "manualNotes": "Implementation commit created locally with no push. The handoff is committed separately as the required run artifact."
}
```
