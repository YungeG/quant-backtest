# G12M Tushare fixed-singleton prerequisite authority v1

## Decision

**H2 — `PREREQUISITE_INCOMPLETE`.** Current HEAD does not contain either required independently accepted prerequisite:

1. no separately and independently accepted generic decision-grade durable rebuild/retention proof prerequisite provides a durable canonical proof body, exact versioned schema, independent pre-Integrity verification/recomputation against immutable execution evidence, and repository replay of the same body/hash while preserving existing v1 APIs and bytes; and
2. no separately and independently accepted exact applicable production China A-share component/Profile/Build authority exists. The current Profile registrations and current-selected rule authorities are DEVELOPMENT-only and false for decision-grade/Profile qualification.

Either absence requires H2. Both are present at current HEAD. This decision terminates BHA-02 through BHA-04 and routes only to BHA-05 blocked governance.

The canonical decision is [decision.json](../../evidence/g12m-tushare-fixed-singleton-prerequisite-authority-v1/decision.json), with semantic decision hash `sha256:a7a6fff66a34f20031178d82fd7da424799ecbc2b3e2c887bdd149e98cc826bb` and file SHA-256 `sha256:cce8099f25ede30dc8d3a8736a70da34f5f004fbe7b87c20a21ee0433035f134`.

## Contract binding

Execution DAG commit: `0e2715f4f87bea1a68baf5657dc41a89eaecd156`.

| Contract file | SHA-256 |
| --- | --- |
| [Parent plan](../implementation/plans/g12/g12m-tushare-fixed-singleton-qualification-v1.md) | `sha256:f818835febdcdff604b60b4ddf8eda99eeb0254f7fc773cda2ed5e539d3fd7e0` |
| [Execution DAG](../implementation/plans/g12/g12m-tushare-fixed-singleton-qualification-v1/README.md) | `sha256:766dc42d8bad54c7ee57f43fb19ffa43ca065a6c84f18dc3adb64fdd02c64f43` |
| [BHA-00 contract freeze](../implementation/plans/g12/g12m-tushare-fixed-singleton-qualification-v1/bha-00-contract-freeze.md) | `sha256:cc09251c37b5f6b85773f400776d13f655f027b349d9db041a51bef24adde900` |
| [BHA-01 gate](../implementation/plans/g12/g12m-tushare-fixed-singleton-qualification-v1/bha-01-profile-resolution-build-authority-gate.md) | `sha256:ac5cea5e6645c73bdd92fcd9de0fc807d324290ba438a1268cad8088a52b275d` |
| [ADR 0008](../adr/0008-source-bounded-decision-grade.md) | `sha256:a213f151393d23e264eaf90de5d6ac7a556548de84c420a3cb5a5bb703f3c3a8` |

The bound case is exactly singleton `xshe:000001`, no dynamic selector, zero target, zero initial/final exposure, and no trade activity.

## Accepted upstream evidence identities

Accepted G12I and G12K remain provider evidence only. They do not establish Profile or Build eligibility and do not assign result grade.

### G12I

- implementation commit: `4389877b8879fc9bb1a6d6544c4079a7d29312ab`;
- [implementation module](../../packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_daily_source_bounded_v2.py): `sha256:808f23ba7e2b0dd08fe08fcfa625489c3ca0d35a5ecbbcfa5e42e5d218d84e3a`;
- [acceptance plan](../implementation/plans/g12/g12i-tushare-cn-a-share-daily-source-bounded-v2.md): `sha256:81297973849f1dc7d759d918d16486e80bcbd52c0d75a7a04e697ff400c13685`;
- report: `sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029`;
- [canonical report file](../../tests/fixtures/market_data/providers/tushare/cn-a-share-daily-source-bounded-v2/observation-report.expected.json): `sha256:9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6`;
- relevant flags are false: provider qualification, historical listing status, corporate-action qualification, decision-grade eligibility, and deployment authorization.

### G12K

- implementation commit: `28a4d7234f5101e67bfa64f1eded92b81bfcf73d`;
- [implementation module](../../packages/market-bundle-builder/src/crypto_quant_bundle_builder/g12k_tushare_fixed_instrument_source_bounded_v1.py): `sha256:4fe7aea59608fbe7dcf9953b29b97a0bf644e3efe6ef069790c851aa64403546`;
- [acceptance plan](../implementation/plans/g12/g12k-tushare-fixed-instrument-source-bounded-v1.md): `sha256:79402fe89df8bffc23be4ff2772bbba14510f6a6133de8fe48acca1b0656c5d8`;
- report: `sha256:5a49065d87286a9673893337328ddbbab9a19cd3addf178bf96033b9b1babfd7`;
- [canonical report file](../../tests/fixtures/market_data/providers/tushare/g12k-fixed-instrument-source-bounded-v1/observation-report.expected.json): `sha256:a386f4281374d1449c0b5ba4371b9e9d2de5b236bc8fc5b5cdd8de5e43c65956`;
- relevant authority, closure, listing, continuity, lifecycle, Profile, decision-grade, live, and deployment flags are false.

## Current HEAD facts

| File | SHA-256 | Exact line facts |
| --- | --- | --- |
| [cn_a_share_profile.py](../../packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_profile.py) | `sha256:f5ec4c572b6bb84fe94997051b9d382be6e3a0a9e227b1fea56a193113114a3c` | Lines 887-900 register Market, Simulation, and Account as `DEVELOPMENT` with final `False`; lines 923-940 exact-reconstruct `decision_grade_eligible`, `profile_qualified`, and `deployment_authorized` as false. |
| [facade.py](../../packages/backtest-runtime/src/crypto_quant_backtest/facade.py) | `sha256:df38483bb7b752d2b13a814e48ddf09a32735c83f2a5baed3892ee84384ac436` | Lines 870-895 construct `DeterministicRebuildEvidence` with both proof hashes `None`. |
| [integrity.py](../../packages/backtest-runtime/src/crypto_quant_backtest/integrity.py) | `sha256:bcb7030666367a9600077d50d6abf132cc12e0f11cdd7a3c23d8f2a6306872c5` | Lines 240-305 define optional proof hashes without a proof body/schema; lines 591-619 preserve Profile/Build grade firewalls; lines 629-654 check only whether proof hashes are non-null. |
| [resolution.py](../../packages/backtest-runtime/src/crypto_quant_backtest/resolution.py) | `sha256:b984e1e0a816154dc85e2c399156ea539a64834bac695129efba5f6843036d44` | Lines 95-279 define generic immutable Build capability; lines 1206-1239 check Bundle capabilities/Profile artifact digest binding; lines 1268-1314 require exact eligible Profiles and Build for decision-grade compatibility. |
| [local_market_bundle_reader.py](../../packages/market-data-contracts/src/crypto_quant_market_data/local_market_bundle_reader.py) | `sha256:bbca532a90789590b882fc3e9a259cce0bfbcb8c37bef6b97ee946f3e0b7a57a` | Lines 394-445 verify an immutable G12D Bundle tree/manifest; lines 447-533 verify its schema-1 publication and retention-proof linkage. This is a specific G12D retention artifact, not the missing generic execution rebuild/retention prerequisite. |
| [evidence_repository.py](../../packages/backtest-runtime/src/crypto_quant_backtest/evidence_repository.py) | `sha256:617347b75b03c9717448e11dfa5a1d6c23503db1840b8c84c2fd28fa9d860e7d` | Lines 407-459 validate canonical-attempt hash fields, including an optional retention hash and deterministic-rebuild-evidence hash, but do not replay/recompute a durable proof body. |
| [integrity test fixtures](../../tests/runtime/integrity/_fixtures.py) | `sha256:e1e086821590f999d23f4ce38ca370d01ab8b6b5c828b81beb251f826baf2fcb` | Lines 65-117 mutate generic test registrations to decision grade; lines 229-258 produce opaque hashes from `{"bundle":"retained"}` and `{"rebuild":"verified"}`. |
| [integrity tests](../../tests/runtime/integrity/test_integrity_report.py) | `sha256:0fb9e874c2263c19a807fc678e3dbbe0cd506e0d721328ba8587f24bdb1b1a11` | Lines 169-210 pass those opaque hashes and expect decision-grade success. |
| [integrity golden fixture](../../tests/fixtures/runtime/integrity-canonical-result-publication-v1.json) | `sha256:e2c160f990f52ea1e67ff81934411a9e32dac92ae7bb55feb52c1b67ae866586` | Lines 66-72, 580, and 652-658 contain null or opaque sample proof hashes, not a canonical durable proof body. |
| [current-selected G12H plan](../implementation/plans/g12/g12h-current-selected-development-v1.md) | `sha256:8055a662a61a60f301072c3bbc25c0139be031a8ff979fd6f77fda05f7211742` | Lines 20-42 and 88 identify the accepted lane as development-only; lines 126-136 freeze `decision_grade_eligible=false`. |
| [current-selected rule projector](../../packages/market-bundle-builder/src/crypto_quant_bundle_builder/cn_a_share_current_selected_rule_bundle.py) | `sha256:2315606653d5513bc3613f5230385fc2f12aa5f387d863145fa6ce1cc0a54eb7` | Lines 23-29 and 48-96 use explicit current-selected-development capability/event/source identities and preserve the declaration qualification mapping. |

## Negative searches

All commands ran at HEAD `0e2715f4f87bea1a68baf5657dc41a89eaecd156`.

1. Durable proof body/schema or verifier symbols:

   ```bash
   git grep -n -E 'class [A-Za-z0-9_]*(Durable|Deterministic)(Rebuild|Retention)[A-Za-z0-9_]*(Proof|Verifier)|def [A-Za-z0-9_]*(verify|recompute)[A-Za-z0-9_]*(rebuild|retention)[A-Za-z0-9_]*proof|deterministic_rebuild_proof_(body|schema)|pre_integrity_(proof_)?verif' -- packages tools tests evidence docs/research
   ```

   Exit `1`; no matches.

2. Repository replay/recomputation of a rebuild/retention proof:

   ```bash
   git grep -n -E '(repository|Repository).*(replay|recompute|verify).*(rebuild|retention).*proof|(rebuild|retention).*proof.*(repository|Repository).*(replay|recompute|verify)' -- packages tools tests evidence docs/research
   ```

   Exit `1`; no matches.

3. Candidate tracked durable/rebuild/retention proof schema/verifier/replay filenames:

   ```bash
   git ls-files | grep -Ei '((durable|rebuild|retention).*(proof|schema|verif|replay))|((proof|schema|verif|replay).*(durable|rebuild|retention))'
   ```

   Exit `1`; no matches.

4. Existing proof-hash surface:

   ```bash
   git grep -n -E 'market_bundle_retention_proof_hash|deterministic_rebuild_proof_hash' -- packages tests
   ```

   Exactly 36 matches occur in six files: `evidence_repository.py`, `facade.py`, `integrity.py`, the Integrity golden fixture, `_fixtures.py`, and `test_integrity_report.py`. Inspection found only hash fields, parsing, nulls, presence checks, and opaque test hashes—not the required accepted durable body/schema/verifier/repository replay.

5. Exact A-share decision-grade production authority symbols:

   ```bash
   git grep -n -E 'cn_a_share.*(DECISION_GRADE|decision_grade_eligible=True|decision_grade_eligible=true)|(DECISION_GRADE|decision_grade_eligible=True|decision_grade_eligible=true).*cn_a_share' -- packages tools evidence docs/research
   ```

   Exit `1`; no matches.

6. Accepted/PASSED A-share Profile/Build decision-grade authority in research/evidence:

   ```bash
   git grep -n -i -E '(accepted|passed).*(china a-share|cn_a_share|a-share).*(profile|build).*(authority|decision-grade)|(accepted|passed).*(profile|build).*(authority|decision-grade).*(china a-share|cn_a_share|a-share)' -- docs/research evidence
   ```

   Exit `1`; no matches.

## Capability is not accepted authority

Generic types can represent immutable Build artifacts and decision-grade registrations, and tests can replace fixture values with `DECISION_GRADE`, `decision_grade_eligible=True`, and opaque proof hashes. Those facts demonstrate capability only. They do not identify a separately reviewed and independently accepted production A-share component/Profile/Build decision, and they do not supply the required durable proof prerequisite.

Likewise, `LocalMarketBundleReader` verifies the existing G12D Bundle retention artifact. That does not provide the missing execution-wide canonical proof body, versioned schema, independent pre-Integrity recomputation, or repository replay contract required by BHA-01 H1.

## Strict closure disposition

Missing strict G12H successor, official closure, or legal closure remains unknown and is recorded only as an ADR-0008 limitation/nonclaim. It is **not** an H2 cause because no exact selected production component exists whose controllable contract makes that closure fact applicable.

## Route and non-emissions

- BHA-02: `TERMINATED_H2`;
- BHA-03: `TERMINATED_H2`;
- BHA-04: `TERMINATED_H2`;
- next route: BHA-05 blocked governance only.

This BHA-01 result emits no authority module, production Profile registration, Build, Bundle, resolved environment, Run, Integrity result, assessment, qualification, or grade. It contains no secrets or environment values. `supersedes_decision_hash` is null.

## Protected history baseline

The research decision records these pre-write deterministic tree digests for replay after the write:

- G12I implementation plus 54 fixture files: `sha256:8afede23aaa2d96ee87aa26cea73a3e12fb86cd65fafcd2157b212766d143df2`;
- G12K implementation plus three fixture files: `sha256:7958e2764c9f746cf2b6a98397e5443d70931fc1f94438250d660a1626984faa`;
- 171 tracked Binance-related files: `sha256:040276f7eceefa107815156fe79a75bf5e45ed433dbdde71d1dd6f41ab1f1eeb`.

No accepted G12I, G12K, or Binance byte is in the BHA-01 write set.
