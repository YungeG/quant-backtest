# Platform V5 Backtest compatibility fan-in request

- **Status:** BLOCKER — Backtest owner action required
- **Platform contract:** `integration-v5-decision-grade-proof-v1`
- **Purpose:** publish one Backtest revision containing both accepted public capability lines
- **Platform changes requested from Backtest:** none beyond the compatibility fan-in

## Problem

Platform V5 must preserve the accepted Integration v2 model seam while consuming the accepted durable-proof/canonical-v3 seam. No known Backtest revision currently contains both.

### Accepted Integration v2 model seam

```text
033344172b24847e73941bb97a06da0490527edf
```

Required preserved public behavior includes:

- `prepare_model_bound_cash_development_backtest`;
- model-bound request and Trial composition;
- accepted Research model golden and retry behavior;
- existing Integration v2 public bytes and compatibility tests.

### Accepted durable-proof/canonical-v3 seam

```text
cebb9b033b7eeffbbff712715fc017708ac5a247
```

Required preserved public behavior includes:

- `BacktestCanonicalPublicationRefV2`;
- `AnalysisArtifactRefV2`;
- `VerifiedCompletedPublicationV3`;
- `load_completed_v3`;
- `load_analysis_v2`;
- unchanged `derive` with exact V1/V2 dispatch;
- rebuild-verification and proof-publication-manifest verification.

The two accepted revisions diverge at:

```text
cd1d7588ae451a3fa22a2b230b2cd5c3aa65973f
```

## Observed failures

Pinning Platform packages to `cebb9b0` removes the model-bound public operation:

```text
AttributeError: module 'crypto_quant_backtest' has no attribute
'prepare_model_bound_cash_development_backtest'
```

It breaks existing Research tests including:

- `test_real_model_research_golden_replays_exact_ten_task_candidate`;
- `test_transient_model_training_failure_retries_without_duplicate_reservations`;
- `test_real_research_golden_replays_without_a_second_economic_run`.

Remaining on `0333441` cannot import the new public values:

```text
AnalysisArtifactRefV2
BacktestCanonicalPublicationRefV2
VerifiedCompletedPublicationV3
```

## Required Backtest result

Publish one immutable compatibility fan-in commit, represented below as `NEW_SHA`, that descends from both accepted revisions:

```bash
git merge-base --is-ancestor \
  033344172b24847e73941bb97a06da0490527edf NEW_SHA

git merge-base --is-ancestor \
  cebb9b033b7eeffbbff712715fc017708ac5a247 NEW_SHA
```

Both commands must exit with status `0`.

The new revision must support these public imports together:

```python
from crypto_quant_backtest import (
    AnalysisArtifactRefV2,
    BacktestCanonicalPublicationRefV2,
    VerifiedCompletedPublicationV3,
    prepare_model_bound_cash_development_backtest,
)
```

## Acceptance requirements

- full Backtest suite passes;
- Integration v2 model-bound tests remain green;
- durable-proof/canonical-v3 tests remain green;
- accepted V1/V2 bytes and public behavior remain unchanged;
- no version downgrade, nominal-ref unwrap, or fallback is introduced;
- `uv lock --check` passes;
- `git diff --check` passes;
- `git status --short` is empty;
- the fan-in commit is pushed and remotely reachable, preferably from `main`.

## Return packet to Platform

```text
backtest_fanin_sha: <40 lowercase hex>
contains_model_seam: 033344172b24847e73941bb97a06da0490527edf
contains_durable_proof_seam: cebb9b033b7eeffbbff712715fc017708ac5a247
public_imports: passed
focused_tests: <commands and results>
full_tests: <command and result>
uv_lock_check: passed
git_diff_check: passed
git_status: clean
remote_branch: <branch>
```

## Non-goals

Do not add Platform-owned types to Backtest, rewrite accepted wire bytes, remove either public seam, synthesize grades, weaken proof verification, authorize Live/deployment behavior, or introduce unrelated provider/runtime scope.
