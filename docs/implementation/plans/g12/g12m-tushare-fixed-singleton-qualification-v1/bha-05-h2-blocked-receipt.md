# BHA-05 H2 blocked receipt

## Accepted route

- source plan commit: `0e2715f4f87bea1a68baf5657dc41a89eaecd156`;
- accepted BHA-01 main commit: `a786d9772f3732678851476ac9c51e3f10abb69b`;
- BHA-01 decision: `H2 / PREREQUISITE_INCOMPLETE`;
- semantic decision: `sha256:a7a6fff66a34f20031178d82fd7da424799ecbc2b3e2c887bdd149e98cc826bb`;
- canonical decision file: `sha256:cce8099f25ede30dc8d3a8736a70da34f5f004fbe7b87c20a21ee0433035f134`;
- research report: `sha256:60a74445d4d6691e8cf138830b464f8b927a164e9f330c9ba00329fcbb0ee611`;
- manifest file: `sha256:5499838a552cfab5d27715b97e0a4d19bb0f6117a734d9c140364c7e0e9f3d1c`.

Canonical replay from the accepted BHA-01 tip removes only the embedded
`decision_hash`, serializes with sorted keys and compact separators, and reproduces
semantic decision `sha256:a7a6fff66a34f20031178d82fd7da424799ecbc2b3e2c887bdd149e98cc826bb`.
The accepted decision bytes reproduce the decision-file hash, and both manifest
entries reproduce the accepted research and decision hashes.

## Final registry state

| Registry item | Final state |
| --- | --- |
| Tushare BHA-01 | `DECIDED_H2` / accepted prerequisite-incomplete |
| Tushare BHA-02 | `TERMINATED_H2` / no outputs |
| Tushare BHA-03 | `TERMINATED_H2` / no outputs |
| Tushare BHA-04 | `TERMINATED_H2` / no outputs |
| Tushare BHA-05 | `ACCEPTED_H2` |
| Tushare execution DAG | `BLOCKED_H2` |
| H2 receipt | this file only |
| H1 receipt | absent |
| Binance | accepted H3 status and identities unchanged |

Accepted G12I/G12K remain provider evidence only. They do not authorize a Profile,
Build, Resolution outcome, Integrity grade, Run, assessment, or G12M qualification.
Tushare qualification is blocked by two controllable prerequisites:

1. no independently accepted generic durable rebuild/retention proof seam; and
2. no independently accepted applicable production China A-share component/Profile/
   Build authority.

Missing strict G12H successor, official closure, or legal closure remains an ADR-0008
limitation/nonclaim. It is not an H2 cause.

## Terminated nodes and no-output proof

BHA-02, BHA-03, and BHA-04 produced no package, test, fixture, Bundle, Profile
registration, Build, resolved environment, Run, publication, Integrity result,
assessment, qualification, or grade. Every route-specific planned output path is
absent. The two pre-existing shared BHA-03 paths,
`packages/backtest-runtime/src/crypto_quant_backtest/evidence_repository.py` and
`tests/runtime/analysis/test_analysis_derivation_boundary.py`, are byte-identical to
the source-plan commit. No H1 receipt exists.

## Protected-byte fingerprints

The BHA-01 baseline and BHA-05 replay match exactly:

| Protected set | Tracked files | Before | After |
| --- | ---: | --- | --- |
| G12I implementation plus accepted fixture tree | 55 | `sha256:8afede23aaa2d96ee87aa26cea73a3e12fb86cd65fafcd2157b212766d143df2` | `sha256:8afede23aaa2d96ee87aa26cea73a3e12fb86cd65fafcd2157b212766d143df2` |
| G12K implementation plus accepted fixture tree | 4 | `sha256:7958e2764c9f746cf2b6a98397e5443d70931fc1f94438250d660a1626984faa` | `sha256:7958e2764c9f746cf2b6a98397e5443d70931fc1f94438250d660a1626984faa` |
| `en_US.UTF-8`-sorted tracked Binance-related paths | 171 | `sha256:040276f7eceefa107815156fe79a75bf5e45ed433dbdde71d1dd6f41ab1f1eeb` | `sha256:040276f7eceefa107815156fe79a75bf5e45ed433dbdde71d1dd6f41ab1f1eeb` |

The fingerprints are `sha256sum` records over the protected path lists, followed by
SHA-256 of that record stream. The Binance path list uses the baseline
`en_US.UTF-8` collation.

## Validation

All commands passed from accepted BHA-01 tip plus this governance write:

```bash
python /tmp/g12m_bha05_validate_decision.py
git diff --quiet 0e2715f4f87bea1a68baf5657dc41a89eaecd156 -- packages/backtest-runtime/src/crypto_quant_backtest/evidence_repository.py tests/runtime/analysis/test_analysis_derivation_boundary.py
python /tmp/g12m_bha05_validate_outputs.py
python /tmp/g12m_bha05_validate_status_links.py
python /tmp/g12m_bha05_protected_fingerprints.py
git diff --check
git diff --name-only a786d9772f3732678851476ac9c51e3f10abb69b --
git diff --no-ext-diff a786d9772f3732678851476ac9c51e3f10abb69b..HEAD | gitleaks detect --pipe --redact --no-banner
uv run --locked pytest -q tests/architecture/test_repository_cleanliness.py tests/architecture/test_public_api_imports.py
```

The decision validator reconstructs the accepted source tip in a temporary directory,
checks commit ancestry, canonical JSON bytes, semantic/file/report/manifest hashes,
and exact manifest replay. The output validator checks all BHA-02/BHA-03/BHA-04
route-specific paths are absent and exactly the H2 receipt exists. The status/link
validator checks all 11 governed authority documents plus this receipt: local Markdown
links, required final statuses, BHA-00's labelled historical state, the authorized
parent-plan and BHA-00 entries in both BHA-05 exact write-set declarations, absence
of stale readiness/route language, the exact docs-only amended diff, and no H1
output/receipt.
The fingerprint validator checks the three exact protected sets and counts above.

## Residual limitations and next actions

This route remains fixed-singleton, source-bounded, historical, zero-target,
zero-exposure, no-trade, non-live, and non-deployment. It makes no general A-share
listing, universe, survivorship, corporate-action closure, provider finality or
completeness, strict legal closure, legal certification, nonzero execution, live-use,
or Binance qualification claim.

Next actions are outside this terminated route:

1. independently design, review, and accept the generic durable rebuild/retention
   proof prerequisite; and
2. independently establish and accept applicable production China A-share
   component/Profile/Build authority.

Only after both immutable acceptance identities exist may a new qualification route
bind them and reconsider code work.
