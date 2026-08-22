---
id: DRP-04
owner: platform-superproject-consumer
repository: Platform superproject ../
status_authority: README.md
produces:
  - one immutable Platform consumer-v2 commit
  - exact ../backtest gitlink pin to the DRP-03 Backtest candidate
  - V1/V2 completed and analysis operation-dispatch evidence
consumes:
  - immutable DRP-03 Backtest implementation candidate commit
  - frozen Platform BT-PORT-01 v1 fixture and behavior
depends_on:
  contract: [DRP-03]
  evidence: [backtest-candidate-sha, backtest-candidate-validation]
  write_conflict: [platform-backtest-gitlink-and-consumer-contract]
---

# DRP-04 Platform consumer-v2 and exact Backtest pin

## Vertical outcome

In the Platform superproject, create one clean commit that pins the `backtest`
submodule gitlink to exactly the immutable DRP-03 Backtest implementation candidate
and adds the minimum consumer-v2 fixture/support/boundary coverage. This node writes
no Backtest source, Backtest Matrix row, or governance receipt.

The repository boundary is explicit: every path in this node is Platform-owned and is
spelled relative to the Backtest submodule checkout as `../...`.

## Exact Platform write set

Write exactly:

- `../tests/contracts/backtest-consumer-port-v2.json` — additive consumer-v2 fixture;
- `../tests/support/backtest_consumer_port.py` — exact V1/V2 dispatch in the existing
  test-only consumer model;
- `../tests/architecture/test_backtest_consumer_port.py` — preserved V1 fingerprint
  plus V2 journey/version/operation assertions; and
- `../backtest` — the superproject gitlink, set to the exact DRP-03 candidate SHA.

Do not edit `../tests/contracts/backtest-consumer-port-v1.json`; its bytes and
`sha256:5f9971573154a92aa83f6ac6edbb36024721ad5b54a35f0f14414c1e393f69fa`
remain protected. No Platform production adapter, repository, schema registry,
heuristic decoder, or Backtest semantic reimplementation is added.

## Version and operation dispatch

The additive v2 consumer contract preserves all v1 operations and dispositions while
making version dispatch explicit:

- nominal V1 completed ref → `load_completed`;
- nominal V2 completed ref → `load_completed_v3`;
- unchanged `derive` operation receives the verified result of the corresponding
  completed load; V1 produces/loads the V1 analysis ref, V2 produces the V2 analysis
  ref;
- V1 analysis ref → `load_analysis`;
- V2 analysis ref → `load_analysis_v2`;
- raw `ArtifactRef` → terminal/evaluation handling only, never canonical-v3 success;
- unknown nominal/ref/artifact schema versions → the exact DRP-00-frozen port
  type/version failure.

Dispatch uses exact nominal type and schema contracts. It never peeks through a
wrapper to infer manifest version, treats raw `canonical_publication_manifest@2` as a
completed result, sends V2 to V1 methods, or retries/downgrades after a V2 failure.
`BacktestAnalysisRuntime.derive` remains one operation; consumer-v2 adds no
`derive_v2` operation.

## Required consumer journey

With the Platform gitlink already at the exact DRP-03 SHA, consumer-v2 must test the
exact operation chain `run → load_completed_v3 → derive → load_analysis_v2`:

```text
run
→ exact BacktestCanonicalPublicationRefV2
→ load_completed_v3
→ BacktestAnalysisRuntime.derive
→ exact AnalysisArtifactRefV2
→ load_analysis_v2
```

Assertions bind the V2 completed publication ref, execution-result hash, result grade,
metric profile, V2 analysis ref, and V2 source publication. Adjacent vectors prove the
unchanged V1 route:

```text
run → BacktestCanonicalPublicationRef → load_completed
    → derive → AnalysisArtifactRef → load_analysis
```

Terminal/evaluation cases remain metric-free and cannot enter either analysis route.
Failure precedence, malformed/unknown version rejection, and no-heuristic/no-downgrade
behavior are explicit.

## Commit and acceptance

Before commit, prove:

- `git -C .. diff -- ../backtest ../tests/contracts/backtest-consumer-port-v2.json ../tests/support/backtest_consumer_port.py ../tests/architecture/test_backtest_consumer_port.py`
  is the complete Platform diff;
- `git -C .. rev-parse :backtest` equals the immutable DRP-03 candidate SHA;
- the v1 fixture hash and existing v1 consumer vectors are unchanged;
- consumer-v2 journey, exact version dispatch, operations, failure precedence, and
  architecture boundary pass;
- Platform diff-check and gitleaks pass; and
- the Platform working tree is clean after one commit.

Record the immutable Platform commit SHA plus its exact `backtest` gitlink SHA for the
typed DRP-04→DRP-05 evidence edge. Do not update the Backtest Acceptance Matrix. The
later DRP-05 governance commit is docs/status only, so Platform may remain pinned to
this exact DRP-03 code commit; there is no reason to repin to DRP-05.
