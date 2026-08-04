# Backtest Work Package Acceptance Matrix

状态：Draft governance contract。此文件不自动授权实现；只有状态为 `READY` 且用户明确要求开始的 Work Package 才允许进入实现。

关联文档：

- `docs/architecture/backtest-system-design.md`
- `docs/implementation/target-driven-bar-v1-plan.md`

## 1. 状态规则

```text
DRAFT  → 接口、依赖或验收字段尚未完成，禁止实现
READY  → 验收契约已经评审，可以实现
PASSED → 指定 commit 上全部验收通过并保存 Evidence
```

状态变化规则：

- `DRAFT → READY` 必须完成 Depends On、Owner Package、Public Interface、Test Command、Fixture IDs、Expected Artifact、Failure Contract、Allowed Grade 和 Evidence。
- `READY → PASSED` 必须记录 immutable commit、实际命令、测试结果和 Artifact hash。
- 代码合并后发现验收契约需要实质变化，状态退回 `DRAFT`，不能边改标准边宣布通过。
- `PASSED` 不代表后续 Gate 自动 READY。
- Decision-grade Gate 的 `PASSED` 不产生部署授权。

## 2. 每项必填模板

```yaml
id: WP-or-Gate-ID
status: DRAFT | READY | PASSED
depends_on: []
owner_package: package-or-repository-root
public_interface: interface-under-test
test_commands:
  contract: python -m pytest -q ...
  fixture: python -m pytest -q ...
  boundary: python -m pytest -q ...
fixture_ids: []
expected_artifacts: []
failure_contracts: []
allowed_grade: development | decision-candidate
evidence: []
passed_commit: null
artifact_hashes: []
```

所有 Gate 的 Boundary command 必须包含或依赖 Architecture import checks。Golden Artifact 必须是静态受控文件；测试可以生成 actual output 做比较，但不得现场重写 expected 文件。

## 3. 当前 Gate Registry

所有项目默认 `DRAFT`。`TBD before READY` 是明确阻断，不是可在实现中补充的占位符。

| ID | Status | Owner | Depends On | Readiness blocker |
| --- | --- | --- | --- | --- |
| WP-00A | PASSED | repository root | none | none |
| WP-00B | PASSED | repository root | WP-00A | none |
| WP-00C | PASSED | repository root + parity tooling | WP-00B | none |
| G00 | PASSED | repository root | WP-00A, WP-00B, WP-00C | none |
| WP-01A | PASSED | trading-domain | G00 | none |
| WP-01B | PASSED | trading-domain | WP-01A | none |
| WP-01C | PASSED | trading-domain | WP-01B | none |
| WP-01D | PASSED | trading-domain | WP-01A–WP-01C | none |
| G01 | PASSED | trading-domain | WP-01A, WP-01B, WP-01C, WP-01D | none |
| WP-02A | PASSED | trading-domain | G01 | none |
| WP-02B | PASSED | trading-domain | WP-02A | none |
| WP-02C | PASSED | trading-domain | WP-02A, WP-02B | none |
| WP-02D | PASSED | trading-domain | WP-02A, WP-02C | none |
| WP-02E | PASSED | trading-domain | WP-01D | none |
| WP-02F | READY | trading-kernel | WP-02A–WP-02D | none |
| WP-02G | DRAFT | backtest-runtime | WP-02A–WP-02D | Simulation Port contracts |
| WP-02H | DRAFT | trading-domain | WP-02A–WP-02E | Error taxonomy catalog |
| WP-03A | DRAFT | trading-kernel | G02 | Journal replay fixtures |
| WP-03B | DRAFT | trading-kernel | WP-03A | Ledger projection fixtures |
| WP-03C | DRAFT | trading-kernel | WP-02F | PricePurpose/Mark fixtures |
| WP-03D | DRAFT | trading-kernel | WP-03C | Currency graph fixtures |
| WP-03E | DRAFT | trading-kernel | WP-03B–WP-03D | Snapshot fixtures |
| WP-03F | DRAFT | trading-kernel | WP-03A–WP-03E | Cash accounting + legacy parity |
| WP-04A | DRAFT | trading-kernel | G02 | Candidate validation fixtures |
| WP-04B | DRAFT | trading-kernel | WP-04A | Atomic batch fixtures |
| WP-04C | DRAFT | trading-kernel | WP-04B, G03 | Allocation/netting fixtures |
| WP-04D | DRAFT | trading-kernel | WP-04C | Portfolio Risk fixtures |
| WP-04E | DRAFT | trading-kernel | WP-04D, WP-03C | Sizing/materialization fixtures |
| WP-05A | DRAFT | trading-kernel | G02 | Order lifecycle fixtures |
| WP-05B | DRAFT | trading-kernel | WP-05A | Reservation replay fixtures |
| WP-05C | DRAFT | trading-kernel | WP-03B, WP-05B | Settlement/availability fixtures |
| WP-05D | DRAFT | trading-kernel | G04, WP-05A–WP-05C | Rebalance fixtures |
| WP-05E | DRAFT | trading-kernel | WP-05D | Capability fixtures |
| WP-05F | DRAFT | trading-kernel | WP-05E | Translation fixtures |
| WP-05G | DRAFT | trading-kernel | WP-05F, WP-02F | Market rule fixtures |
| WP-05H | DRAFT | trading-kernel | WP-05G, WP-02F | Fee reservation fixtures |
| WP-05I | DRAFT | trading-kernel | WP-05B, WP-05H | Pre-trade Risk fixtures |
| WP-05J | DRAFT | trading-kernel | WP-02F, WP-03A | Fee assessment fixtures |
| WP-06A | DRAFT | market-data-contracts | G02 | Reader/Cursor contract commands |
| WP-06B | DRAFT | backtest-runtime | WP-01B, WP-06A | Timeline fixtures |
| WP-06C | DRAFT | backtest-runtime | G04, WP-06A–WP-06B | TargetStream fixtures |
| WP-06D | DRAFT | backtest-runtime | WP-02G, WP-03C | Slippage fixtures |
| WP-06E | DRAFT | backtest-runtime | G05, WP-06A–WP-06D | Next-open fixtures |
| WP-06F | DRAFT | backtest-runtime | WP-03E, WP-05A–WP-05C, WP-06B, WP-06E | Run-end fixtures |
| WP-06G | DRAFT | backtest-runtime | WP-06A–WP-06F | Engine harness fixtures |
| WP-06H | DRAFT | tests/support | WP-02F–WP-02G | Synthetic profile/golden artifacts |
| WP-07A | DRAFT | backtest-runtime | G06 | Resolver/semantic ID fixtures |
| WP-07B | DRAFT | backtest-runtime | WP-07A | Attempt/Outcome fixtures |
| WP-07C | DRAFT | backtest-runtime | WP-07B | Evidence atomicity fixtures |
| WP-07D | DRAFT | backtest-runtime | WP-07B–WP-07C | Execution hash fixtures |
| WP-07E | DRAFT | backtest-runtime | WP-07C–WP-07D | Integrity/grade fixtures |
| G08A | DRAFT | trading-kernel profiles/cn_a_share | G07 | Calendar fixtures |
| G08B | DRAFT | trading-kernel profiles/cn_a_share | G08A | T+1 fixtures |
| G08C | DRAFT | trading-kernel profiles/cn_a_share | G08A | Lattice/odd-lot fixtures |
| G08D | DRAFT | trading-kernel profiles/cn_a_share | G08A, G08C, WP-05G | Historical rule fixtures |
| G08E | DRAFT | trading-kernel profiles/cn_a_share | WP-05H, WP-05J | Fee/tax fixtures |
| G08F | DRAFT | trading-kernel profiles/cn_a_share | G08A, WP-06B | Announcement/entitlement fixtures |
| G08G | DRAFT | trading-kernel profiles/cn_a_share | G08F, G03 | Adjustment/payment fixtures |
| G08H | DRAFT | trading-kernel profiles/cn_a_share + parity | G08A–G08G | Composition/parity commands |
| G09A | DRAFT | trading-kernel derivatives | G03 | Position model fixtures |
| G09B | DRAFT | trading-kernel accounting | G09A, G03 | Fill/PnL fixtures |
| G09C | DRAFT | trading-kernel financing | G09A, WP-06B | Funding eligibility fixtures |
| G09D | DRAFT | trading-kernel financing/accounting | G09B–G09C | Funding settlement fixtures |
| G09E | DRAFT | trading-kernel margin | G09A | Instrument margin fixtures |
| G09F | DRAFT | trading-kernel margin | G09B, G09E, WP-05B | Cross-margin fixtures |
| G09G | DRAFT | backtest-runtime liquidation audit | G09E–G09F | SAFE/AMBIGUOUS fixtures |
| G09H | DRAFT | tests/support + profile composition | G09A–G09G | Synthetic perpetual E2E |
| G10A | DRAFT | trading-kernel profiles/binance_usdm | G09H | Instrument metadata fixtures |
| G10B | DRAFT | trading-kernel profiles/binance_usdm | G10A, WP-05G | Rule timeline fixtures |
| G10C | DRAFT | trading-kernel profiles/binance_usdm | G10A, G09E | Margin tier fixtures |
| G10D | DRAFT | trading-kernel profiles/binance_usdm | G10A, WP-03C | PricePurpose fixtures |
| G10E | DRAFT | trading-kernel profiles/binance_usdm | G09C–G09D, G10D | Funding source fixtures |
| G10F | DRAFT | trading-kernel profiles/binance_usdm | WP-05H, WP-05J, G09F | Fee/account fixtures |
| G10G | DRAFT | backtest-runtime composition | G10A–G10F | Resolved profile E2E |
| G10H | DRAFT | parity tooling | G10G, WP-00C | crypt-gemini parity |
| G11A | DRAFT | backtest-runtime observations | G07 | Capability isolation fixtures |
| G11B | DRAFT | backtest-runtime observations | G11A | Revision/causality fixtures |
| G11C | DRAFT | backtest-runtime observations | G11A–G11B | Universe fixtures |
| G11D | DRAFT | backtest-runtime observations | G11A–G11B | Bar/window fixtures |
| G11E | DRAFT | backtest-runtime strategy | G11B, G11D | Schedule/warmup fixtures |
| G11F | DRAFT | backtest-runtime strategy | G02 | State/checkpoint fixtures |
| G11G | DRAFT | backtest-runtime strategy | G11F | Random stream fixtures |
| G11H | DRAFT | backtest-runtime strategy | G11B, G11F | Model revision fixtures |
| G11I | DRAFT | backtest-runtime strategy | G11A–G11H, G04 | Invocation/batch fixtures |
| G11J | DRAFT | parity tooling | G11I, G07 | Dual-entry parity |
| G12A | DRAFT | market-bundle-builder | G00 | SourceSnapshot contract |
| G12B | DRAFT | market-bundle-builder | G12A, G02 | Normalization fixtures |
| G12C | DRAFT | market-bundle-builder | G12B | Manifest/validation fixtures |
| G12D | DRAFT | market-bundle-builder + market-data-contracts | G12C | Atomic publish/repository fixtures |
| G12E | DRAFT | market-data-contracts | G12D, WP-06A | Columnar reader fixtures |
| G12F | DRAFT | parity tooling | G12E, G07 | Reader/partition parity |
| G12G | DRAFT | market-bundle-builder | G12B–G12C | Bar aggregation fixtures |
| G12H | DRAFT | market-bundle-builder validation | G12C | Rule coverage fixtures |
| G12I | DRAFT | market-bundle-builder validation | G12C, G12G | Price/availability/revision coverage |
| G12J | DRAFT | trading-domain schema migration | real old artifact | No real source/target schema yet |
| G12K | DRAFT | market-bundle-builder validation | G12C | Universe/corporate action coverage |
| G12L-* | DRAFT | market-bundle-builder source adapter | G12A–G12K as applicable | Provider selection/spec |
| G12M-* | DRAFT | backtest-runtime qualification | market-specific G12L, G07–G10 | Per-market qualification matrix |

## 4. WP-00A Acceptance Card

```yaml
id: WP-00A
status: PASSED
depends_on: []
owner_package: repository-root
public_interface:
  - uv workspace package discovery
  - root uv.lock reproducible dependency installation
  - Python 3.13-only workspace (`>=3.13,<3.14`)
  - per-package build and import
  - root test entrypoint
test_commands:
  contract: uv run pytest -q tests/architecture/test_workspace_smoke.py
  fixture: uv run pytest -q tests/architecture/test_package_imports.py
  boundary: uv run pytest -q tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - five-package-workspace-v1
expected_artifacts:
  - tests/fixtures/architecture/five-package-workspace-v1.expected.json
  - build/acceptance/wp-00a-package-build-manifest.json
  - build/wheels/*.whl
failure_contracts:
  - missing-package-metadata
  - non-reproducible-install
  - package-import-failure
  - undeclared-editable-source
  - test-mutates-worktree
allowed_grade: development
evidence:
  - pytest-report
  - package-build-manifest
  - dependency-lock-hash
  - exact-python-patch-version
passed_commit: 77f70227fdb0edc2837b059e43fb2e1fd242778f
artifact_hashes:
  uv.lock: sha256:87fee7ebf7f6a14f158d4e3826fee358f04de8974bc63554d46decc7086e0979
  tests/fixtures/architecture/five-package-workspace-v1.expected.json: sha256:dceec5a831a68ece8ba1cd3967f44783e88c92c5c7457657414c5ec52cca8f4e
  build/acceptance/wp-00a-package-build-manifest.json: sha256:7f9e3c6dfdf56e37f5ad9bc1e0953f5688c301a48ceb23a55ec02d6109d5fd24
  build/acceptance/wp-00a-pytest.xml: sha256:e25a02561f74f75d983eaff730c41092c5d6dc1609e72815e7b663e5b1f763b1
```

### WP-00A Acceptance

第二轮拆解审阅已完成。Workspace 使用 `uv workspace + root uv.lock + setuptools.build_meta`，v1 仅支持 Python 3.13（`>=3.13,<3.14`，`.python-version = 3.13`）。目录约定为：

```text
build/acceptance/   # CI/local acceptance actual artifacts
build/coverage/     # 派生覆盖率报告
build/wheels/       # WP 验收 Wheel
tests/fixtures/     # Git 跟踪的静态 Golden
runs/               # Backtest canonical evidence
```

`build/` 全部 gitignored；CI 可以上传 `build/acceptance/`。WP-00A 的实现已冻结在 immutable commit `77f70227fdb0edc2837b059e43fb2e1fd242778f`，状态为 `PASSED`。

验证记录：

```text
uv sync --all-packages --group dev                                      PASS
uv run pytest -q tests/architecture/test_workspace_smoke.py             2 passed
uv run pytest -q tests/architecture/test_package_imports.py              1 passed
uv run pytest -q tests/architecture/test_repository_cleanliness.py       2 passed
uv run pytest                                                            5 passed
Python                                                                   3.13.5
uv.lock sha256                                                           87fee7ebf7f6a14f158d4e3826fee358f04de8974bc63554d46decc7086e0979
```

## 5. WP-00B Acceptance Card

```yaml
id: WP-00B
status: PASSED
depends_on:
  - WP-00A
owner_package: repository-root
public_interface:
  - architecture/import-boundaries.toml policy schema v1
  - tools/architecture/check_import_boundaries.py CLI
  - deterministic boundary report schema v1
  - global pytest network isolation
  - package-root-only cross-package import contract
test_commands:
  contract: uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/wp-00b-boundary-report.json
  fixture: uv run pytest -q tests/architecture/test_import_boundary_mutations.py
  boundary: uv run pytest -q tests/architecture/test_network_isolation.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - import-boundary-mutations-v1
expected_artifacts:
  - architecture/import-boundaries.toml
  - tests/fixtures/architecture/import-boundary-mutations-v1/
  - build/acceptance/wp-00b-boundary-report.json
failure_contracts:
  - unsupported-policy-schema
  - forbidden-workspace-import
  - forbidden-external-import
  - generic-kernel-concrete-profile-import
  - runtime-builder-import
  - runtime-network-import
  - undeclared-dynamic-import
  - cross-package-internal-import
  - real-network-access-attempt
  - checker-mutates-worktree
allowed_grade: development
evidence:
  - pytest-report
  - deterministic-boundary-report
  - policy-hash
passed_commit: 99db3a9f31a102c27045739645fae7cb0da5032f
artifact_hashes:
  architecture/import-boundaries.toml: sha256:d209981299381c7815e1da25be271675cbe30dd67a84ce157699ccb682e66ea9
  tests/fixtures/architecture/import-boundary-mutations-v1/cases.json: sha256:05f064ef9b161d8dc78e6eae493e05f1a8ccae3aca32ba18ee9888a093a178b2
  build/acceptance/wp-00b-boundary-report.json: sha256:ebf690868ee9dedb91b429ad2677ca11834c33d88a08400e5d806431794f08f6
  build/acceptance/wp-00b-pytest.xml: sha256:2a1f0f5ea27bb918dd369d5a93ff2c78b50c3d25852730e3f796dd04b15bfee2
```

### WP-00B Acceptance

已确认使用仓库自有的标准库 AST checker，不引入 `import-linter` 或 `pytest-socket`。Policy 和 Checker 必须满足：

1. Policy schema/version 未识别时 fail closed；
2. 普通 import、from import、字面量 dynamic import 均被检查；
3. 受保护目录中的非字面量 dynamic import 默认拒绝，allowlist 必须精确记录 caller path、target prefix 和 reason；
4. 跨 Package 只能导入目标 package root Public API；
5. Runtime 的 DNS/socket/HTTP 网络入口在 pytest 进程中全局阻断；阻断测试先确认 guard 已安装，再触发 guard，不允许执行真实网络 syscall；
6. JSON report 按 rule、source path、line、target 稳定排序，不包含 wall-clock time；
7. Checker、Fixture 和报告生成不得修改 tracked worktree。

WP-00B 的实现已冻结在 immutable commit `99db3a9f31a102c27045739645fae7cb0da5032f`，状态为 `PASSED`。

验证记录：

```text
Boundary checker contract                                             PASS (5 files)
Import mutation fixtures                                              18 passed
Network/Public API/Cleanliness boundaries                              7 passed
Full test suite                                                        28 passed
Python                                                                 3.13.5
Policy sha256                                                          d209981299381c7815e1da25be271675cbe30dd67a84ce157699ccb682e66ea9
```

## 6. WP-00C Acceptance Card

```yaml
id: WP-00C
status: PASSED
depends_on:
  - WP-00B
owner_package: repository-root-and-parity-tooling
public_interface:
  - docs/migration/source-map.yaml schema v1
  - deterministic source snapshot manifest schema v1
  - tools/migration/freeze_source_snapshot.py CLI
  - tools/migration/verify_legacy_baseline.py CLI
  - comparator contract schema v1
  - tools/migration/run_parity.py CLI
  - first-divergence parity report schema v1
test_commands:
  contract: uv run python tools/migration/verify_legacy_baseline.py --root . --source-map docs/migration/source-map.yaml --report build/acceptance/wp-00c-source-baseline-report.json
  fixture: uv run pytest -q tests/parity/test_source_snapshots.py tests/parity/test_comparator_contract.py
  boundary: uv run pytest -q tests/parity/test_parity_report_harness.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - legacy-source-snapshots-v1
  - comparator-contract-v1
  - first-divergence-parity-report-v1
expected_artifacts:
  - docs/migration/source-map.yaml
  - tests/parity/contracts/comparator-contract-v1.schema.json
  - tests/parity/fixtures/legacy-sources/*.tar.gz
  - tests/parity/fixtures/legacy-sources/*.manifest.json
  - tests/parity/fixtures/comparator-v1/
  - build/acceptance/wp-00c-source-baseline-report.json
  - build/acceptance/wp-00c-pytest.xml
failure_contracts:
  - unsupported-source-map-schema
  - undeclared-source-path
  - missing-source-member
  - duplicate-source-member
  - unsafe-archive-member
  - snapshot-hash-mismatch
  - manifest-hash-mismatch
  - unsupported-migration-mode
  - intentional-change-without-adr
  - global-epsilon-forbidden
  - unclassified-comparator-field
  - invalid-quantization-policy
  - invalid-explicit-tolerance
  - sequence-first-divergence
  - approved-change-without-reference
  - migration-evidence-mutated
allowed_grade: development
evidence:
  - source-map-hash
  - three-snapshot-hashes
  - three-manifest-hashes
  - comparator-contract-hash
  - pytest-report
  - source-baseline-report
passed_commit: e298a2ce9f2a4214bc7eb4e68dc87ef0a860b331
artifact_hashes:
  docs/migration/source-map.yaml: sha256:8a0be053f538f6277e35b0908c25398a989cd52e499c1cd911742aebfd1a8cf5
  tests/parity/contracts/comparator-contract-v1.schema.json: sha256:4e36d823efeae635b0cbff84271e691615920c0f28dc37a009acb68ecd7948ca
  tests/parity/fixtures/legacy-sources/crypto-quant-core-33ca4055b16fd966d92263248289fcd960a1cb93f52c4d8a0db00030b3e3d0d1.tar.gz: sha256:33ca4055b16fd966d92263248289fcd960a1cb93f52c4d8a0db00030b3e3d0d1
  tests/parity/fixtures/legacy-sources/crypto-quant-core-33ca4055b16fd966d92263248289fcd960a1cb93f52c4d8a0db00030b3e3d0d1.manifest.json: sha256:58fc5e0b8b96515e506e885406e37a9dde2f4f7f0c3e9435aeea6d68d5177a01
  tests/parity/fixtures/legacy-sources/cycle-rotation-platform-1fea4f5a4ec8ab12ddb25c6c5bb525f91f8bac9e887f3e5b382b641a948c91c3.tar.gz: sha256:1fea4f5a4ec8ab12ddb25c6c5bb525f91f8bac9e887f3e5b382b641a948c91c3
  tests/parity/fixtures/legacy-sources/cycle-rotation-platform-1fea4f5a4ec8ab12ddb25c6c5bb525f91f8bac9e887f3e5b382b641a948c91c3.manifest.json: sha256:5074f0b6f1130a6bc6b755e8dc9c582dbf15631ef92520b6f7a601eb763c03e2
  tests/parity/fixtures/legacy-sources/crypt-gemini-d6e6feca46b61586e890a441443738dc9e911a58428c940e86055459361eda80.tar.gz: sha256:d6e6feca46b61586e890a441443738dc9e911a58428c940e86055459361eda80
  tests/parity/fixtures/legacy-sources/crypt-gemini-d6e6feca46b61586e890a441443738dc9e911a58428c940e86055459361eda80.manifest.json: sha256:002fbec9fad3de169fd91be99078c316b2a0896fad890c3e2004518dc6e6eac4
  build/acceptance/wp-00c-source-baseline-report.json: sha256:75082323356fd9554c3bc782b33552c7f58c3992876b703cd24b9a8b50e9cfd1
  build/acceptance/wp-00c-pytest.xml: sha256:539389342c0a6e8cdc6358a47365f7b178bd27111dc4a1430ebedace46022a92
```

### WP-00C Acceptance

已冻结以下决策：

1. 来源仓库 clean/dirty 状态不影响资格；Snapshot 捕获 `include_files` 中当时的实际文件字节；
2. 首批范围为 `crypto-quant-core` 12 文件、`cycle-rotation-platform` 8 文件、`crypt-gemini` 28 文件；
3. 三个确定性归档及 Manifest 都作为 Git 跟踪的 Golden Fixture 提交；
4. Base commit、remote、worktree state 仅为 provenance，Archive SHA-256 才是 Source Snapshot identity；
5. 验证完全离线，不能依赖三个原来源仓库继续存在；
6. `PyYAML` 是本 WP 唯一新增 external seam；Comparator 和 Snapshot 算法只使用标准库；
7. Comparator 禁止 global epsilon，字段必须逐项声明比较语义；
8. `intentional_semantic_change` 和 `approved_change` 必须引用已提交 ADR。

WP-00C 的实现已冻结在 immutable commit `e298a2ce9f2a4214bc7eb4e68dc87ef0a860b331`，状态为 `PASSED`。

验证记录：

```text
Offline source baseline verifier                                      PASS (3 sources / 48 files)
Source Snapshot + Comparator fixtures                                  17 passed
Parity report + repository cleanliness                                  7 passed
Full test suite                                                        50 passed
mypy                                                                    no issues (11 files)
Python                                                                  3.13.5
Source Map sha256                                                       8a0be053f538f6277e35b0908c25398a989cd52e499c1cd911742aebfd1a8cf5
```

## 7. G00 Acceptance Card

```yaml
id: G00
status: PASSED
depends_on:
  - WP-00A
  - WP-00B
  - WP-00C
owner_package: repository-root
public_interface:
  - locked Python 3.13 workspace
  - five-package dependency boundary policy
  - offline legacy source baseline
  - root architecture and parity test entrypoint
test_commands:
  contract: uv sync --locked --all-packages --group dev
  fixture: uv run pytest -q tests/architecture tests/parity
  boundary: uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g00-import-boundary-report.json && uv run python tools/migration/verify_legacy_baseline.py --root . --source-map docs/migration/source-map.yaml --report build/acceptance/g00-source-baseline-report.json
fixture_ids:
  - five-package-workspace-v1
  - import-boundary-mutations-v1
  - legacy-source-snapshots-v1
  - comparator-contract-v1
expected_artifacts:
  - uv.lock
  - architecture/import-boundaries.toml
  - docs/migration/source-map.yaml
  - build/acceptance/g00-import-boundary-report.json
  - build/acceptance/g00-source-baseline-report.json
  - build/acceptance/g00-pytest.xml
failure_contracts:
  - unlocked-dependency-environment
  - workspace-package-missing
  - architecture-boundary-violation
  - runtime-network-access
  - legacy-source-evidence-invalid
  - comparator-harness-regression
  - test-mutates-worktree
allowed_grade: development
evidence:
  - dependency-lock-hash
  - import-policy-hash
  - source-map-hash
  - pytest-report
  - boundary-reports
passed_commit: 35913d151c68c8e9ef9e93db48c2db5711ce688a
artifact_hashes:
  uv.lock: sha256:afa595beed6c70d7a0124844d450e6b157b365ce6fa7c7fd0d2df9b70aff97c5
  architecture/import-boundaries.toml: sha256:d209981299381c7815e1da25be271675cbe30dd67a84ce157699ccb682e66ea9
  docs/migration/source-map.yaml: sha256:8a0be053f538f6277e35b0908c25398a989cd52e499c1cd911742aebfd1a8cf5
  build/acceptance/g00-import-boundary-report.json: sha256:ebf690868ee9dedb91b429ad2677ca11834c33d88a08400e5d806431794f08f6
  build/acceptance/g00-source-baseline-report.json: sha256:75082323356fd9554c3bc782b33552c7f58c3992876b703cd24b9a8b50e9cfd1
  build/acceptance/g00-pytest.xml: sha256:afbf14f6933b51db27d770156286e4769859634e29d1c1a02de86bb3c9d94a59
```

### G00 Acceptance

WP-00A、WP-00B 和 WP-00C 均已通过各自 Acceptance Card。G00 聚合验证冻结在 immutable commit `35913d151c68c8e9ef9e93db48c2db5711ce688a`，状态为 `PASSED`。

验证记录：

```text
Locked workspace sync                                                   PASS
Architecture + parity suite                                              50 passed
Import boundary report                                                   PASS
Offline source baseline                                                  PASS (3 sources / 48 files)
Python                                                                   3.13.5
```

## 8. WP-01A Acceptance Card

```yaml
id: WP-01A
status: PASSED
depends_on:
  - G00
owner_package: trading-domain
public_interface:
  - crypto_quant_domain.Scale
  - crypto_quant_domain.RoundingPolicy
  - crypto_quant_domain.QuantizationPolicy
  - crypto_quant_domain.Price
  - crypto_quant_domain.Quantity
  - crypto_quant_domain.Money
  - crypto_quant_domain.Rate
  - crypto_quant_domain.ExposureFraction
  - canonical typed scaled integer dictionaries
test_commands:
  contract: uv run pytest -q tests/domain/numeric/test_scaled_values.py
  fixture: uv run pytest -q tests/domain/numeric/test_rounding.py tests/domain/numeric/test_quantization.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - numeric-boundaries-v1
expected_artifacts:
  - tests/fixtures/domain/numeric-boundaries-v1.json
failure_contracts:
  - implicit-cross-domain-arithmetic
  - identity-mismatch
  - implicit-scale-conversion
  - rounding-policy-required
  - invalid-scale
  - non-finite-analytics-value
  - unversioned-quantization
  - floating-point-in-canonical-value
allowed_grade: development
evidence:
  - pytest-report
  - numeric-boundary-fixture-hash
  - public-api-import-report
passed_commit: d0330c211e772230bda1da59dca4f314ebe64b52
artifact_hashes:
  tests/fixtures/domain/numeric-boundaries-v1.json: sha256:f74f4f5d4870de6d5977b3b65d317b0d7e6aac5816e54df7115c0e0287e3941b
  build/acceptance/wp-01a-pytest.xml: sha256:c612dbad5a0027b38a76ae170b6e9368e91d2bd9bdd00bd731d4d9d0be3a2169
```

### WP-01A Acceptance

已冻结 v1 数值语义：

1. `Scale` 是十进制小数位数，范围 `0..18`；超出范围 fail closed；
2. 权威存储只有 Python integer `units`，拒绝 bool/float units；
3. 加减要求完全相同的领域类型、identity 和 Scale，不执行隐式对齐；
4. Scale 提升、降低、乘法、除法均必须显式传入 `RoundingPolicy`；
5. v1 Rounding 包含 toward-zero、away-from-zero、floor、ceiling、half-even 和 half-up；
6. `QuantizationPolicy` 必须包含非空 version、目标 Scale 和 RoundingPolicy；float/Decimal 只能通过该边界进入；
7. `Money` 使用 currency identity，`Quantity` 使用 instrument identity，`Price` 使用 instrument + quote currency identity；WP-02A 会将字符串 identity 收紧为正式领域 ID，但不改变 canonical 字段；
8. Canonical dictionary 只包含 type、units、scale 和相应 identity，不包含 float 或 Decimal；
9. `Price.notional(Quantity)` 和 `Money.quantity_at(Price)` 是 v1 唯一跨类型乘除入口，必须显式结果 Scale 和 RoundingPolicy。

WP-01A 的实现已冻结在 immutable commit `d0330c211e772230bda1da59dca4f314ebe64b52`，状态为 `PASSED`。

验证记录：

```text
Typed scaled value contracts                                            8 passed
Rounding + quantization fixtures                                        15 passed
Boundary tests                                                           5 passed
Full test suite                                                         73 passed
mypy                                                                     no issues (9 files)
Python                                                                   3.13.5
```

## 9. WP-01B Acceptance Card

```yaml
id: WP-01B
status: PASSED
depends_on:
  - WP-01A
owner_package: trading-domain
public_interface:
  - crypto_quant_domain.UtcInstant
  - crypto_quant_domain.LocalTimeDisambiguation
  - crypto_quant_domain.resolve_local_datetime
  - crypto_quant_domain.TradingDate
  - crypto_quant_domain.SessionId
  - crypto_quant_domain.TimelinePhase
  - crypto_quant_domain.SourceSequence
  - crypto_quant_domain.SimulationInstant
test_commands:
  contract: uv run pytest -q tests/domain/time/test_utc_instant.py tests/domain/time/test_simulation_instant.py
  fixture: uv run pytest -q tests/domain/time/test_local_time_resolution.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - time-dst-boundaries-v1
expected_artifacts:
  - tests/fixtures/domain/time-dst-boundaries-v1.json
failure_contracts:
  - naive-datetime-rejected
  - ambiguous-local-time-unresolved
  - nonexistent-local-time
  - lossy-nanosecond-conversion
  - inferred-trading-date
  - invalid-source-sequence
  - unstable-simulation-order
allowed_grade: development
evidence:
  - pytest-report
  - dst-fixture-hash
  - public-api-import-report
passed_commit: 3da5ee1fa99debe3d3c3b6e987d0468d2e8c601b
artifact_hashes:
  tests/fixtures/domain/time-dst-boundaries-v1.json: sha256:70554c97f2ae43c0e6fdae26d435a40e0ef619b97769e95d0d882a668c3ef901
  build/acceptance/wp-01b-pytest.xml: sha256:4b268f6fccddcaf75a2688381df77ca811dcacbb5a15d80fc9b6cf5a29fbd35a
```

### WP-01B Acceptance

已冻结 v1 时间语义：

1. `UtcInstant` 只存 signed integer `epoch_nanoseconds`；aware datetime 输入用整数运算转换，naive datetime 拒绝；
2. Python datetime 只有 microsecond 精度，`to_datetime()` 遇到非 1000ns 对齐值时 fail closed，不允许静默截断；
3. 本地时间解析必须提供 IANA ZoneInfo 和 `LocalTimeDisambiguation`；重复时间支持 earlier/later/reject，缺失时间始终拒绝；
4. `TradingDate` 是显式 `calendar_id + date` 值，不提供从 UTC/local date 推断的 API；
5. `SessionId` 是显式 `calendar_id + value`；
6. `TimelinePhase` 使用非负 rank 和 canonical code，不预先硬编码市场/Engine phase 集合；
7. `SourceSequence` 是 `0..2^63-1` 的整数；
8. `SimulationInstant` 总顺序为 `(epoch_nanoseconds, phase.rank, phase.code, source_sequence)`；Profile/Runtime 后续必须保证同一 registry 内 phase rank 唯一。

WP-01B 的实现已冻结在 immutable commit `3da5ee1fa99debe3d3c3b6e987d0468d2e8c601b`，状态为 `PASSED`。

验证记录：

```text
UtcInstant + SimulationInstant contracts                                 9 passed
DST resolution fixtures                                                   3 passed
Boundary tests                                                            5 passed
Full test suite                                                          85 passed
mypy                                                                      no issues (10 files)
Python                                                                    3.13.5
```

## 10. WP-01C Acceptance Card

```yaml
id: WP-01C
status: PASSED
depends_on:
  - WP-01B
owner_package: trading-domain
public_interface:
  - crypto_quant_domain.IdentityNamespace
  - crypto_quant_domain.IdentityManifest
  - crypto_quant_domain.DomainIdKind
  - crypto_quant_domain.DomainId
  - crypto_quant_domain.derive_domain_id
test_commands:
  contract: uv run pytest -q tests/domain/identity/test_domain_ids.py
  fixture: uv run pytest -q tests/domain/identity/test_identity_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - deterministic-domain-ids-v1
expected_artifacts:
  - tests/fixtures/domain/deterministic-domain-ids-v1.json
failure_contracts:
  - noncanonical-semantic-run-id
  - empty-semantic-key
  - invalid-domain-ordinal
  - invalid-domain-id
  - attempt-id-contamination
  - identity-algorithm-drift
  - identity-namespace-version-drift
allowed_grade: development
evidence:
  - pytest-report
  - identity-golden-hash
  - public-api-import-report
passed_commit: 1ff4bdccbb48af5bd651d918ee257d8eb6c3bfa8
artifact_hashes:
  tests/fixtures/domain/deterministic-domain-ids-v1.json: sha256:4691c2467d6c8d16fead46f79f5602ceae1e561ace4990ae055f306f77fe48e4
  build/acceptance/wp-01c-pytest.xml: sha256:0ea8e3580b4fecbd0ee2f2cccbb407070d6f2a90ef2b467b16492a521918cf01
```

### WP-01C Acceptance

已冻结 identity algorithm v1：

1. 输入仅包含 `IdentityNamespace`、`DomainIdKind`、Semantic Run ID、canonical semantic key bytes 和 non-negative ordinal；Attempt ID 不存在于接口中；
2. SHA-256 payload 使用固定 magic `crypto-quant-domain-id\\0`，随后依次写入 algorithm、namespace、namespace version、kind、semantic run ID 和 semantic key 的 4-byte big-endian length-prefixed UTF-8/bytes，ordinal 使用 8-byte unsigned big-endian；
3. algorithm 标识为 `sha256-length-prefixed-v1`；
4. ID 使用固定 kind prefix + 64 lowercase hex digest；
5. v1 支持 decision、order、fill、fee、settlement、journal 和 reservation kind；
6. Semantic Run ID、namespace 和 version 必须是无首尾空白的 canonical text；semantic key 必须是非空 immutable bytes；
7. Namespace/version/algorithm 进入 `IdentityManifest` 和 hash payload，任何变化必须显式改变 ID。

WP-01C 的实现已冻结在 immutable commit `1ff4bdccbb48af5bd651d918ee257d8eb6c3bfa8`，状态为 `PASSED`。

验证记录：

```text
Deterministic ID contracts                                               5 passed
Golden identity fixtures                                                 5 passed
Boundary tests                                                           5 passed
Full test suite                                                         95 passed
mypy                                                                     no issues (10 files)
Python                                                                   3.13.5
```

## 11. WP-01D Acceptance Card

```yaml
id: WP-01D
status: PASSED
depends_on:
  - WP-01A
  - WP-01B
  - WP-01C
owner_package: trading-domain
public_interface:
  - crypto_quant_domain.CanonicalizationError
  - crypto_quant_domain.CanonicalSchema
  - crypto_quant_domain.CanonicalEnvelope
  - crypto_quant_domain.canonical_bytes
  - crypto_quant_domain.canonical_sha256
test_commands:
  contract: uv run pytest -q tests/domain/canonical/test_canonical_encoding.py
  fixture: uv run pytest -q tests/domain/canonical/test_canonical_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - canonical-envelope-v1
expected_artifacts:
  - tests/fixtures/domain/canonical-envelope-v1.json
failure_contracts:
  - floating-point-canonical-value
  - decimal-canonical-value
  - datetime-canonical-value
  - non-string-mapping-key
  - non-normalized-unicode
  - unsupported-canonical-type
  - invalid-schema-identity
  - canonical-hash-drift
allowed_grade: development
evidence:
  - pytest-report
  - canonical-golden-hash
  - public-api-import-report
passed_commit: b2d5254d0190f0ba1758068c05ab7a57222d0dfe
artifact_hashes:
  tests/fixtures/domain/canonical-envelope-v1.json: sha256:b60ffff75d09be85cef3fe6b1d8293691d565583095c82510b2397d4722d5031
  build/acceptance/wp-01d-pytest.xml: sha256:e84acdb8ee1e4e3b699c6eb71aeee62637a3290dfc2086269d389c34dded7d64
```

### WP-01D Acceptance

已冻结 canonical encoding v1：

1. 输出为 UTF-8 JSON、mapping key 按 Unicode codepoint 排序、无多余空白、末尾无换行；
2. 允许 `null`、bool、integer、NFC string、list/tuple、string-key mapping，以及显式 `to_canonical_dict()` 领域对象；
3. 禁止 float、Decimal、datetime/date、bytes、set、非字符串 key、非 NFC string 和未知对象；
4. `CanonicalSchema` 使用 lowercase canonical name 和 `version >= 1` integer；
5. `CanonicalEnvelope` 固定为 `{schema: {name, version}, payload: ...}`，Schema version 必须进入 bytes/hash；
6. `canonical_sha256()` 返回 `sha256:<64 lowercase hex>`；
7. WP-01C 的 semantic key 应由 `canonical_bytes()` 产生，但 Identity 模块继续只消费 immutable bytes，避免反向耦合。

WP-01D 的实现已冻结在 immutable commit `b2d5254d0190f0ba1758068c05ab7a57222d0dfe`，状态为 `PASSED`。

验证记录：

```text
Canonical encoding contracts                                            12 passed
Golden bytes/hash fixture                                                 1 passed
Boundary tests                                                            5 passed
Full test suite                                                         108 passed
mypy                                                                     no issues (11 files)
Python                                                                   3.13.5
```

## 12. G01 Acceptance Card

```yaml
id: G01
status: PASSED
depends_on:
  - WP-01A
  - WP-01B
  - WP-01C
  - WP-01D
owner_package: trading-domain
public_interface:
  - exact typed scaled integer foundation
  - nanosecond UTC and deterministic simulation ordering
  - versioned deterministic domain identities
  - canonical bytes and SHA-256 envelopes
test_commands:
  contract: uv run pytest -q tests/domain/numeric tests/domain/time tests/domain/identity tests/domain/canonical
  fixture: uv run pytest -q tests/domain --junitxml=build/acceptance/g01-domain-pytest.xml
  boundary: uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g01-import-boundary-report.json
fixture_ids:
  - numeric-boundaries-v1
  - time-dst-boundaries-v1
  - deterministic-domain-ids-v1
  - canonical-envelope-v1
expected_artifacts:
  - tests/fixtures/domain/numeric-boundaries-v1.json
  - tests/fixtures/domain/time-dst-boundaries-v1.json
  - tests/fixtures/domain/deterministic-domain-ids-v1.json
  - tests/fixtures/domain/canonical-envelope-v1.json
  - build/acceptance/g01-domain-pytest.xml
  - build/acceptance/g01-import-boundary-report.json
failure_contracts:
  - numeric-regression
  - temporal-regression
  - identity-drift
  - canonical-hash-drift
  - trading-domain-dependency-violation
allowed_grade: development
evidence:
  - four-fixture-hashes
  - pytest-report
  - import-boundary-report
passed_commit: fb50a193956464430dc573c05a654023eaa872cc
artifact_hashes:
  tests/fixtures/domain/numeric-boundaries-v1.json: sha256:f74f4f5d4870de6d5977b3b65d317b0d7e6aac5816e54df7115c0e0287e3941b
  tests/fixtures/domain/time-dst-boundaries-v1.json: sha256:70554c97f2ae43c0e6fdae26d435a40e0ef619b97769e95d0d882a668c3ef901
  tests/fixtures/domain/deterministic-domain-ids-v1.json: sha256:4691c2467d6c8d16fead46f79f5602ceae1e561ace4990ae055f306f77fe48e4
  tests/fixtures/domain/canonical-envelope-v1.json: sha256:b60ffff75d09be85cef3fe6b1d8293691d565583095c82510b2397d4722d5031
  build/acceptance/g01-domain-pytest.xml: sha256:8670e6ed4e7ea56ca9b1700339520b90e3810577762293d5950a4c1d8c84caf7
  build/acceptance/g01-import-boundary-report.json: sha256:43a990caf66f8800daa8500d29f158cffbd5df3cc732687717c0aade4340575b
```

### G01 Acceptance

WP-01A 至 WP-01D 已分别通过。G01 聚合验证冻结在 immutable commit `fb50a193956464430dc573c05a654023eaa872cc`，状态为 `PASSED`。

验证记录：

```text
Domain foundation contracts + fixtures                                  58 passed
Trading-domain import boundary                                           PASS (13 files)
Python                                                                   3.13.5
```

## 13. WP-02A Acceptance Card

```yaml
id: WP-02A
status: PASSED
depends_on:
  - G01
owner_package: trading-domain
public_interface:
  - crypto_quant_domain.CurrencyId
  - crypto_quant_domain.VenueId
  - crypto_quant_domain.InstrumentId
  - crypto_quant_domain.InstrumentType
  - crypto_quant_domain.InstrumentDefinition
  - crypto_quant_domain.SymbolInterval
  - crypto_quant_domain.SymbolTimeline
  - crypto_quant_domain.InstrumentCatalog
test_commands:
  contract: uv run pytest -q tests/domain/instruments/test_identities.py
  fixture: uv run pytest -q tests/domain/instruments/test_symbol_timeline.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - instrument-identity-timeline-v1
expected_artifacts:
  - tests/fixtures/domain/instrument-identity-timeline-v1.json
failure_contracts:
  - invalid-currency-id
  - invalid-venue-id
  - invalid-instrument-id
  - unknown-currency-reference
  - unknown-instrument-reference
  - duplicate-instrument-definition
  - overlapping-symbol-interval
  - missing-symbol-at-instant
  - symbol-rename-changes-identity
allowed_grade: development
evidence:
  - pytest-report
  - instrument-fixture-hash
  - public-api-import-report
passed_commit: 642cf363d35293bb7c3adf69ccbe0f6801567e09
artifact_hashes:
  tests/fixtures/domain/instrument-identity-timeline-v1.json: sha256:c883d97d59e9b118ba92aada03527b35408057758756e1109609ece0600803a7
  build/acceptance/wp-02a-pytest.xml: sha256:5aa39d4e844f890862b80c3994dfe16a043007f48e8e43f9c85aaeb74fa35ebb
```

### WP-02A Acceptance

已冻结 v1 Instrument identity：

1. `CurrencyId` 使用 uppercase canonical code；`VenueId` 使用 lowercase canonical code；
2. `InstrumentId` 由 `VenueId + stable_key` 构成，stable key 不是交易 Symbol，允许字母、数字、`.`、`_`、`:`、`/`、`-`；
3. `InstrumentType` v1 支持 spot、equity、linear_perpetual、inverse_perpetual、future、option 和 fx；
4. `InstrumentDefinition` 包含 immutable identity、type、可选 base currency、quote currency 和 settlement currency；
5. `SymbolTimeline` 使用按 `effective_from` 排序的 half-open interval，同一 Instrument 不允许重叠；Symbol 改名不改变 InstrumentId；
6. `InstrumentCatalog` 是引用完整性边界，拒绝重复 Currency/Instrument、未知 Currency reference 和未知 Timeline Instrument；
7. Instrument rule、lot、tick、margin 和 fee 不属于本 WP。

WP-02A 的实现已冻结在 immutable commit `642cf363d35293bb7c3adf69ccbe0f6801567e09`，状态为 `PASSED`。

验证记录：

```text
Instrument identity/catalog contracts                                    5 passed
Symbol timeline fixtures                                                  4 passed
Boundary tests                                                            5 passed
Full test suite                                                         117 passed
mypy                                                                     no issues (12 files)
Python                                                                   3.13.5
```

## 14. WP-02B Acceptance Card

```yaml
id: WP-02B
status: PASSED
depends_on:
  - WP-02A
owner_package: trading-domain
public_interface:
  - crypto_quant_domain.StrategyDecisionPayload
  - crypto_quant_domain.StrategyDecisionCandidate
  - crypto_quant_domain.StrategySleeveId
  - crypto_quant_domain.TargetExposureFraction
  - crypto_quant_domain.TargetSnapshot
  - crypto_quant_domain.StrategyDecision
  - crypto_quant_domain.DecisionBatch
  - crypto_quant_domain.ActivePortfolioTarget
test_commands:
  contract: uv run pytest -q tests/domain/decisions/test_decision_contracts.py
  fixture: uv run pytest -q tests/domain/decisions/test_target_decision_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - target-decision-contracts-v1
expected_artifacts:
  - tests/fixtures/domain/target-decision-contracts-v1.json
  - build/acceptance/wp-02b-pytest.xml
failure_contracts:
  - unsupported-candidate-payload-value
  - candidate-enters-canonical-trace
  - invalid-strategy-sleeve-id
  - noncanonical-target-exposure-scale
  - duplicate-target-instrument
  - observed-through-after-decision
  - effective-time-before-decision
  - invalid-target-expiry
  - noncanonical-decision-evidence
  - mixed-decision-batch-time
  - duplicate-decision-batch-sleeve
  - active-target-quantity-identity-mismatch
  - duplicate-active-target-instrument
allowed_grade: development
evidence:
  - pytest-report
  - target-decision-fixture-hash
  - public-api-import-report
passed_commit: 4175549ac76884e498258fd8d8656250769771ab
artifact_hashes:
  tests/fixtures/domain/target-decision-contracts-v1.json: sha256:e871629a26cb1fca0d72dd1561a71efd36ac6878f2dd5bd2e307982bb3aca9e7
  build/acceptance/wp-02b-pytest.xml: sha256:8a47b0dc91700bb564ad31e360ff7b70851f2c1dd6b6f66e16c0575ba225ea59
  build/acceptance/wp-02b-import-boundary-report.json: sha256:e413a2d4e64e81f92a85e26ba40e3736ed2d69a65ff10d033960fd20f4a8171e
```

### WP-02B Acceptance

已冻结 v1 Target/Decision 数据契约：

1. `StrategyDecisionPayload` 是 immutable decoded-data tree；它保留重复 Target、未知 Instrument、非法时间和尚未量化的 `float`/字符串值，但拒绝 DataFrame、Broker DTO、Engine reference 和其他非数据对象；
2. `StrategyDecisionCandidate` 只包装 Payload，不提供 canonical serialization，因此不能进入权威 execution trace；
3. `StrategySleeveId` 使用 canonical non-empty text；`TargetExposureFraction` 使用 `InstrumentId + signed integer units`，v1 canonical scale 固定为 12，不在本 WP 限制经济杠杆；
4. Validated `TargetSnapshot` 是同一 Sleeve 的完整、绝对、原子替换集合；允许空集合表示全部归零，拒绝重复 Instrument，`expires_at` 必须晚于 `effective_time`；
5. Validated `StrategyDecision` 使用 `UtcInstant`，强制 `observed_through <= decision_time <= effective_time`；confidence 使用 basis=`confidence`、scale=12、范围 `[0, 1]` 的 `Rate`，evidence 必须是 immutable canonical mapping；
6. `DecisionBatch` 数据契约要求非空、同一 Decision Time、每个 Sleeve 唯一；`decision_batch_id` 由调用方提供 canonical text，稳定派生属于 WP-04B；
7. `ActivePortfolioTarget` 保存 materialization instant、source decision batch identity 和按 `InstrumentId` 绑定的 exact `Quantity`；typed InstrumentId 必须与既有 Quantity canonical string identity 一致，重复 Instrument 被拒绝；
8. 本 WP 不拥有 Candidate→Validated 校验流程、Capital Allocation、Portfolio Risk、Position Sizing 或 DecisionBatch 构建算法。

WP-02B 的实现已冻结在 immutable commit `4175549ac76884e498258fd8d8656250769771ab`，状态为 `PASSED`。

验证记录：

```text
Target/Decision contract tests                                           7 passed
Candidate/Validated golden fixtures                                      2 passed
Public API + repository cleanliness boundaries                           5 passed
Trading-domain import boundary                                           PASS (15 files)
Full test suite                                                         126 passed
mypy                                                                     no issues (13 files)
Python                                                                   3.13.5
```

## 15. WP-02C Acceptance Card

```yaml
id: WP-02C
status: PASSED
depends_on:
  - WP-02A
  - WP-02B
owner_package: trading-domain
public_interface:
  - crypto_quant_domain.OrderSide
  - crypto_quant_domain.ExecutionStyle
  - crypto_quant_domain.TimeInForce
  - crypto_quant_domain.PositionEffect
  - crypto_quant_domain.PriceConstraint
  - crypto_quant_domain.OrderIntent
  - crypto_quant_domain.Order
  - crypto_quant_domain.OrderEventType
  - crypto_quant_domain.OrderEvent
  - crypto_quant_domain.OrderStatus
  - crypto_quant_domain.OrderState
  - crypto_quant_domain.Fill
  - crypto_quant_domain.FeeBasisType
  - crypto_quant_domain.FeeAssessment
  - crypto_quant_domain.SettlementObligation
  - crypto_quant_domain.TranslationStatus
  - crypto_quant_domain.UnsupportedCapability
  - crypto_quant_domain.TranslationFieldMapping
  - crypto_quant_domain.OrderTranslationReport
test_commands:
  contract: uv run pytest -q tests/domain/execution/test_order_execution_contracts.py
  fixture: uv run pytest -q tests/domain/execution/test_order_execution_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - order-execution-contracts-v1
expected_artifacts:
  - tests/fixtures/domain/order-execution-contracts-v1.json
  - build/acceptance/wp-02c-pytest.xml
failure_contracts:
  - invalid-order-enum
  - nonpositive-order-quantity
  - order-quantity-identity-mismatch
  - order-price-constraint-identity-mismatch
  - venue-specific-order-intent-field
  - wrong-order-domain-id-kind
  - fill-event-without-fill-id
  - non-fill-event-with-fill-id
  - rejection-event-without-reason
  - order-state-quantity-identity-mismatch
  - order-state-quantity-scale-mismatch
  - order-state-total-mismatch
  - filled-state-with-remaining-quantity
  - fill-identity-mismatch
  - fill-contains-final-fee
  - fee-basis-type-mismatch
  - duplicate-fee-basis
  - fee-assessment-without-rule-identity
  - invalid-settlement-obligation-shape
  - settlement-identity-mismatch
  - translated-report-with-unsupported-capability
  - rejected-report-without-unsupported-capability
  - duplicate-translation-mapping
allowed_grade: development
evidence:
  - pytest-report
  - order-execution-fixture-hash
  - public-api-import-report
passed_commit: e2ca080c79a676ea6e2bed303cf30be9ead38d10
artifact_hashes:
  tests/fixtures/domain/order-execution-contracts-v1.json: sha256:f113a7d34dbfe196202fc7d8effb0e427517cc3dfe2ebfb75c1577b828c8b4d5
  build/acceptance/wp-02c-pytest.xml: sha256:2cafbf6fd1a4e9b1679b295d6ea7cf2cc360453d9b2b041c9c318f7846ad48db
  build/acceptance/wp-02c-import-boundary-report.json: sha256:30885625eec2e0a85ea4fec528804a443c6e92d1cb5d29541d7186a5fbece945
```

### WP-02C Acceptance

已冻结 v1 Order/Execution 数据契约：

1. `OrderIntent` 只表达 venue-neutral canonical semantics；固定字段为 Instrument、Side、Quantity、Execution Style、可选 Price Constraint、Time-in-Force、Reduce-only、Position Effect、Urgency、Reason 和 Parent identity，不提供任意 extensions/metadata；
2. v1 支持 `buy/sell`、`market/limit/stop/stop_limit`、`day/gtc/ioc/fok/gtx` 和 `auto/open/close`；style、constraint 和 profile capability 的组合合法性不属于本 WP；
3. `Order` 使用 `DomainIdKind.ORDER`，绑定单一 Execution Account、immutable Intent 和创建时 `SimulationInstant`；
4. `OrderEvent` 使用独立 canonical event ID、typed Order ID、causation ID 和 `SimulationInstant`；Fill lifecycle event 必须且只能引用 `DomainIdKind.FILL`，拒绝类 Event 必须携带 reason code；
5. `OrderState` 是 immutable projection data contract，使用 ordered/cumulative/remaining Quantity 并验证 identity、Scale 和总量；状态转换、幂等应用和 replay 推迟到 WP-05C；
6. `Fill` 保存 reference price、execution price 和 Slippage provenance，所有 Quantity/Price/Money identity 必须一致；Fill 不含 Fee 字段；
7. `FeeAssessment` 的 basis 类型为 Fill、Order 或 Session，basis 使用对应 typed `DomainId`/`SessionId`，允许一个或多个唯一 basis，且至少引用一个 Fee/Tax/Account rule identity；
8. `SettlementObligation` 使用 source Fill identity，并恰好承载 `(InstrumentId, Quantity)` 或 `(CurrencyId, Money)` 一种义务；signed units 表达收付方向，零义务被拒绝；
9. `OrderTranslationReport` 只记录 Translation 证据，不包含 Venue Request；translated report 不得包含 unsupported capability，rejected report 必须包含结构化 `UnsupportedCapability`；field mapping 保留 canonical/target field/value，重复 canonical field 被拒绝；
10. 本 WP 不实现 Capability Validator、Translator、Order Event replay、FeeAssessmentEngine、SettlementBook 或 Accounting。

WP-02C 的实现已冻结在 immutable commit `e2ca080c79a676ea6e2bed303cf30be9ead38d10`，状态为 `PASSED`。

验证记录：

```text
Order/Execution contract tests                                          8 passed
Canonical golden fixtures                                               2 passed
Public API + repository cleanliness boundaries                          5 passed
Trading-domain import boundary                                          PASS (16 files)
Full test suite                                                        136 passed
mypy                                                                    no issues (14 files)
Python                                                                  3.13.5
```

## 16. WP-02D Acceptance Card

```yaml
id: WP-02D
status: PASSED
depends_on:
  - WP-02A
  - WP-02C
owner_package: trading-domain
public_interface:
  - crypto_quant_domain.PricePurpose
  - crypto_quant_domain.AccountingEntryType
  - crypto_quant_domain.CashBalanceKey
  - crypto_quant_domain.PositionBalanceKey
  - crypto_quant_domain.BalanceChange
  - crypto_quant_domain.PositionLot
  - crypto_quant_domain.CashBalance
  - crypto_quant_domain.PositionBalance
  - crypto_quant_domain.ValuationMarkReference
  - crypto_quant_domain.AccountingJournalEntry
  - crypto_quant_domain.PortfolioSnapshot
test_commands:
  contract: uv run pytest -q tests/domain/accounting/test_accounting_contracts.py
  fixture: uv run pytest -q tests/domain/accounting/test_accounting_golden.py
  boundary: uv run pytest -q tests/domain/execution/test_order_execution_contracts.py tests/domain/execution/test_order_execution_golden.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - accounting-contracts-v1
expected_artifacts:
  - tests/fixtures/domain/accounting-contracts-v1.json
  - build/acceptance/wp-02d-pytest.xml
failure_contracts:
  - invalid-price-purpose
  - untyped-fill-price-purpose
  - wrong-journal-domain-id-kind
  - journal-source-identity-missing
  - journal-effective-time-after-recorded-time
  - duplicate-journal-source
  - balance-key-value-kind-mismatch
  - balance-identity-mismatch
  - journal-account-venue-mismatch
  - duplicate-balance-change
  - invalid-position-lot-quantity
  - position-lot-identity-mismatch
  - duplicate-position-lot-fee-currency
  - position-balance-lot-total-mismatch
  - duplicate-snapshot-balance
  - snapshot-reporting-currency-mismatch
  - future-valuation-mark
  - duplicate-valuation-mark
  - valuation-mark-set-hash-mismatch
  - invalid-content-hash
  - snapshot-in-journal-schema
allowed_grade: development
evidence:
  - pytest-report
  - accounting-contracts-fixture-hash
  - public-api-import-report
passed_commit: d11ffc9383d75971f0c69d1dd91b2e27f904e67d
artifact_hashes:
  tests/fixtures/domain/accounting-contracts-v1.json: sha256:b63ea512fd5b43043b8b82a0c2fe66cd7ebceabb8825fba52904f9497e5fad17
  build/acceptance/wp-02d-pytest.xml: sha256:904dd9c420200b3dc3b79d105b59420b53d05a1ee29cf07d812b0c669764dc9f
  build/acceptance/wp-02d-import-boundary-report.json: sha256:fae03a69508b799943297546c47f2092fbb835be13af3a2843f2cec61d2cdc97
```

### WP-02D Acceptance

已冻结 v1 Accounting 数据契约：

1. `PricePurpose` 固定为 `execution_reference`、`valuation`、`margin`、`liquidation`、`settlement` 和 `funding`；既有 `Fill.reference_price_purpose` 改为 typed enum，同时保持原 canonical string value；
2. `CashBalanceKey` 使用 Execution Account、Venue 和 typed `CurrencyId`；`PositionBalanceKey` 使用 Execution Account、Venue 和 typed `InstrumentId`，且 Instrument Venue 必须匹配；
3. `BalanceChange` 只能组合 Cash key + matching native `Money` 或 Position key + matching `Quantity`，零变化和跨 identity 变化被拒绝；
4. `AccountingJournalEntry` 使用 `DomainIdKind.JOURNAL`，保存固定 `AccountingEntryType`、effective `UtcInstant`、recorded `SimulationInstant`、一个或多个 source identity、typed balance changes 及 native-currency realized PnL/fee/financing attribution；Entry 本身 immutable，source/change 集合 canonical 排序；
5. `PositionLot` 保存 stable lot/source identity、typed Position key、signed non-zero Quantity、可选正 unit cost、allocated native fees 和 opened time；本 WP 不定义 Cash CostBasisPolicy 或 Derivative PnL 公式；
6. `CashBalance` 和 `PositionBalance` 是 immutable state values；Position lots 如果存在，必须与 Position key/Scale 一致并 exact 合计为 Position Quantity；没有 generic lots 的 Derivative projection 仍可显式使用空 tuple；
7. `PortfolioSnapshot` 保存 native Cash/Position state；Realized PnL、Unrealized PnL、Fees、Financing 和 Equity 均为单一 Reporting Currency `Money`；
8. `ValuationMarkReference` 保存 mark identity、typed Instrument、PricePurpose 和 observed time；Snapshot 拒绝未来 Mark、重复 identity/(Instrument,Purpose) 及与 references 不一致的 mark-set hash；
9. Snapshot 保存 Journal State、Valuation Staleness Report 和 Currency Valuation Graph 的 `sha256:` identity；Snapshot 不进入 `AccountingJournalEntry` 字段，不能覆盖或修改 Journal history；
10. 本 WP 不实现 Journal store/replay、Ledger mutation/projection、Accounting model、Lot selector/consumption、MarkResolver、CurrencyValuationGraph、PortfolioSnapshotProjector、Margin Snapshot 或 mutable state。

WP-02D 的实现已冻结在 immutable commit `d11ffc9383d75971f0c69d1dd91b2e27f904e67d`，状态为 `PASSED`。

验证记录：

```text
Accounting contract tests                                               8 passed
Canonical golden fixtures                                               2 passed
Execution compatibility + public API + cleanliness boundaries          15 passed
Trading-domain import boundary                                          PASS (17 files)
Full test suite                                                        146 passed
mypy                                                                    no issues (17 files)
Python                                                                  3.13.5
```

## 17. WP-02E Acceptance Card

```yaml
id: WP-02E
status: PASSED
depends_on:
  - WP-01D
owner_package: trading-domain
public_interface:
  - crypto_quant_domain.ArtifactEnvelope
  - crypto_quant_domain.ArtifactSchemaRegistration
  - crypto_quant_domain.ArtifactWriteResult
  - crypto_quant_domain.ArtifactReadResult
  - crypto_quant_domain.SchemaCatalog
  - crypto_quant_domain.ArtifactCatalogError
  - crypto_quant_domain.UnknownArtifactTypeError
  - crypto_quant_domain.UnsupportedSchemaVersionError
  - crypto_quant_domain.ArtifactIntegrityError
  - crypto_quant_domain.ArtifactDecodeError
test_commands:
  contract: uv run pytest -q tests/domain/artifacts/test_schema_catalog.py
  fixture: uv run pytest -q tests/domain/artifacts/test_artifact_envelope_golden.py
  boundary: uv run pytest -q tests/domain/canonical/test_canonical_encoding.py tests/domain/canonical/test_canonical_golden.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - artifact-envelope-catalog-v1
expected_artifacts:
  - tests/fixtures/domain/artifact-envelope-catalog-v1.json
  - build/acceptance/wp-02e-pytest.xml
failure_contracts:
  - invalid-artifact-type
  - invalid-artifact-schema-version
  - invalid-artifact-content-hash
  - artifact-content-hash-mismatch
  - duplicate-artifact-type-registration
  - unknown-artifact-type
  - unsupported-artifact-schema-version
  - writer-version-override
  - malformed-artifact-json
  - duplicate-artifact-json-key
  - noncanonical-artifact-source-bytes
  - artifact-payload-decode-failure
allowed_grade: development
evidence:
  - pytest-report
  - artifact-envelope-fixture-hash
  - public-api-import-report
passed_commit: d156b7ac33ebe7aab05506da7740045726d47df8
artifact_hashes:
  tests/fixtures/domain/artifact-envelope-catalog-v1.json: sha256:ec5138bcc003ecd59a1821f20999bfea3072493e3dfccf8cd781b4f4963b7e16
  build/acceptance/wp-02e-pytest.xml: sha256:5cb07d1c01d8af527f83be70d77de9d80ee1059c9553a11d3b71e38da3cb1f56
  build/acceptance/wp-02e-import-boundary-report.json: sha256:a6887199571593873df1cc38818cdf3caa900c5bf889cfd0d1e2d9e3fe03045d
```

### WP-02E Acceptance

已冻结 v1 Artifact Envelope 与 Schema Catalog seam：

1. `ArtifactEnvelope` 的 canonical 形状固定为 `artifact_type`、`schema_version`、`payload` 和 `content_hash`；`content_hash` 是 `{artifact_type, schema_version, payload}` canonical body 的 SHA-256，不递归覆盖自身；Payload 在 Envelope 内物化为 immutable canonical data tree；
2. `SchemaCatalog` 每个 Artifact type 只注册一个当前版本和一个 payload reader；Catalog 构造后不可增加、替换或回退版本；
3. `write_current()` 由 Catalog 选择已注册当前版本，调用方不能覆盖 schema version；输出是 canonical UTF-8 JSON bytes；
4. `read()` 只接受 canonical UTF-8 JSON，先验证 Envelope、content hash、Artifact type 和当前 schema version，再 dispatch payload reader；未知 type/version、重复 JSON key、非 canonical bytes 和 reader failure 均 fail closed；
5. `ArtifactWriteResult` 和 `ArtifactReadResult` 保存完整原始 `source_bytes` 及其独立 `source_hash`；raw bytes 不进入 canonical domain graph，不允许被重新编码后冒充原始证据；
6. 本 WP 只实现 current-version read/write，不实现 Migration、version negotiation、fallback reader、Artifact store、filesystem layout、compression、signing 或 encryption；没有发明 v0 fixture。

WP-02E 的实现已冻结在 immutable commit `d156b7ac33ebe7aab05506da7740045726d47df8`，状态为 `PASSED`。

验证记录：

```text
Artifact catalog contract tests                                         7 passed
Canonical envelope golden fixture                                       1 passed
Canonical compatibility + public API + cleanliness boundaries          18 passed
Trading-domain import boundary                                          PASS (18 files)
Full test suite                                                        154 passed
mypy                                                                    no issues (16 files)
Python                                                                  3.13.5
```

## 18. WP-02F Acceptance Card

```yaml
id: WP-02F
status: READY
depends_on:
  - WP-02A
  - WP-02B
  - WP-02C
  - WP-02D
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.ProfilePortType
  - crypto_quant_trading.ProfilePortContract
  - crypto_quant_trading.ProfileComponentRef
  - crypto_quant_trading.ProfilePortOutcome
  - crypto_quant_trading.SessionModel
  - crypto_quant_trading.InstrumentModel
  - crypto_quant_trading.OrderRuleModel
  - crypto_quant_trading.FeeAssessmentPolicy
  - crypto_quant_trading.TaxPolicy
  - crypto_quant_trading.SettlementModel
  - crypto_quant_trading.PositionAccountingModel
  - crypto_quant_trading.FinancingModel
  - crypto_quant_trading.MarginModel
  - crypto_quant_trading.LiquidationRules
  - crypto_quant_trading.CorporateActionModel
  - crypto_quant_trading.CurrencyValuationPolicy
test_commands:
  contract: uv run pytest -q tests/kernel/ports/test_profile_port_contracts.py
  fixture: uv run pytest -q tests/kernel/ports/test_profile_port_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - kernel-profile-ports-v1
expected_artifacts:
  - tests/fixtures/kernel/kernel-profile-ports-v1.json
  - build/acceptance/wp-02f-pytest.xml
failure_contracts:
  - invalid-profile-port-type
  - invalid-profile-component-key
  - invalid-profile-component-version
  - invalid-profile-component-digest
  - noncanonical-profile-port-contract
  - profile-port-result-and-failure
  - profile-port-result-and-failure-missing
  - invalid-profile-port-input-hash
  - missing-profile-port-method
  - implicit-profile-port-default
  - profile-port-vendor-dto
allowed_grade: development
evidence:
  - pytest-report
  - kernel-profile-port-fixture-hash
  - public-api-import-report
passed_commit: null
artifact_hashes: []
```

### WP-02F Readiness

已冻结以下实现边界：

1. 十二个 Market/Account semantics Port 均为 `runtime_checkable` generic Protocol；每个 Port 有独立语义方法名，不使用一个万能 `evaluate()` 或 arbitrary payload；
2. 每个 Protocol 显式绑定 `RequestT`、`ResultT`、`FailureT`，三者必须满足 immutable/canonical `ProfilePortContract`；未来具体规则 WP 必须用 Trading Domain 类型组成这些 contract，不能传入 DataFrame、Vendor DTO、Runtime State、裸 `dict[str, object]` 或 `Any`；
3. `ProfileComponentRef` 固定 `ProfilePortType`、canonical component key、正整数 version 和 `sha256:` component digest；Profile Registry、component compatibility 和 resolved profile digest 不属于本 WP；
4. `ProfilePortOutcome` 保存 component ref、canonical input hash 和 exactly-one-of result/failure；它不把 exception text、log text 或隐式 `None` 当失败协议；
5. 共享 Profile lookup/incompatibility/applicability reason code 属于 WP-02H，本 WP 只保留 typed `FailureT` seam，避免提前冻结错误 taxonomy；
6. 本 WP 只有 Protocol、identity/outcome value contracts 和 tests 内 Test Adapter；没有 concrete A-share/Binance/Synthetic Profile、registry/resolver、no-op default、simulation assumption、DataFrame、Vendor SDK、网络或可变运行状态。

WP-02F 当前状态为 `READY`，已获持续实施授权。

## 19. PASSED 记录格式

```yaml
id: WP-00A
status: PASSED
passed_commit: immutable_git_commit
executed_commands:
  - uv run pytest -q tests/architecture/test_workspace_smoke.py
  - uv run pytest -q tests/architecture/test_package_imports.py
  - uv run pytest -q tests/architecture/test_repository_cleanliness.py
artifact_hashes:
  tests/fixtures/architecture/five-package-workspace-v1.expected.json: sha256:...
  build/acceptance/wp-00a-package-build-manifest.json: sha256:...
evidence:
  test_report: build/acceptance/wp-00a-pytest.xml
  dependency_lock_hash: sha256:...
```
