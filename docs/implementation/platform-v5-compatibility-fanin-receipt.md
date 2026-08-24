# Platform V5 Backtest compatibility fan-in receipt

- **Status:** CANDIDATE_VALIDATED / REMOTE_PUSH_PENDING
- **Platform contract:** `integration-v5-decision-grade-proof-v1`
- **Fan-in merge:** `599f62cd95ea480fe4b809cc3f34af7e86197c8f`
- **Validated implementation candidate:** `10b0173762de8ab820a6b771a1ac983b149b4f9d`
- **Model seam ancestor:** `033344172b24847e73941bb97a06da0490527edf`
- **Durable-proof ancestor:** `cebb9b033b7eeffbbff712715fc017708ac5a247`

## Accepted compatibility result

The candidate is a real two-parent merge descendant of both accepted lines. It
preserves the durable-proof/canonical-v3 implementation and ports the accepted model
binding as one optional exact field through request identity, execution-input
reconstruction, engine context, canonical cache, and V2/V3 repository replay.

The following imports coexist:

```python
from crypto_quant_backtest import (
    AnalysisArtifactRefV2,
    BacktestCanonicalPublicationRefV2,
    VerifiedCompletedPublicationV3,
    prepare_model_bound_cash_development_backtest,
)
```

Ordinary requests and engine contexts omit `model_binding` when it is `None`; accepted
V1/V2 canonical bytes remain unchanged. Nonempty model bindings must match between the
resolved request and engine context before V2/V3 completed results can be constructed
or published. Repository replay independently reconstructs and checks the same edge.

The historical branch's `.gitleaksignore` was deliberately excluded because the
current repository configuration scans clean without it.

## Validation

```text
accepted model-bound provider suite: 9 passed
focused durable/canonical-v3 suite: 26 passed
combined compatibility/integrity/architecture suite: 66 passed
Backtest full repository: 2438 passed
Platform requested Research regressions: 3 passed
import boundaries: 138 files passed
public import smoke: passed
model-bound canonical-v3 replay/cache regression: passed
V2/V3 mismatched request/context model binding rejection: passed
LSP: clean on 8 changed production files and focused changed tests
lens: no new blocking findings; unrelated pre-existing facade/integrity findings deferred
uv lock --check: passed
git diff --check: passed
gitleaks candidate range: no leaks
candidate git status: clean
```

## Ancestry evidence

Both commands pass against the validated candidate:

```bash
git merge-base --is-ancestor \
  033344172b24847e73941bb97a06da0490527edf \
  10b0173762de8ab820a6b771a1ac983b149b4f9d

git merge-base --is-ancestor \
  cebb9b033b7eeffbbff712715fc017708ac5a247 \
  10b0173762de8ab820a6b771a1ac983b149b4f9d
```

## Preserved boundaries

- no Platform-owned type enters Backtest;
- no grade is synthesized or changed;
- no nominal ref unwrap or fallback is introduced;
- accepted durable proof, canonical-v3 and analysis-v2 checks remain fail-closed;
- model bytes, loader, training, inference framework, Live, and deployment remain out
  of scope;
- private fixed-singleton authorities remain off the public root.

## Remaining closure

Remote reachability is intentionally pending explicit push approval. After the final
governance commit is pushed, the returned `backtest_fanin_sha` should be that remotely
reachable descendant; Platform may pin it and rerun its full V5 acceptance.
