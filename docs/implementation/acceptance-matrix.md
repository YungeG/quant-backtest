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
| WP-02F | PASSED | trading-kernel | WP-02A–WP-02D | none |
| WP-02G | PASSED | backtest-runtime | WP-02A–WP-02D, WP-02F | none |
| WP-02H | PASSED | trading-domain | WP-02A–WP-02G | none |
| G02 | PASSED | trading-domain + trading-kernel + backtest-runtime | WP-02A–WP-02H | none |
| WP-03A | PASSED | trading-kernel | G02 | none |
| WP-03B | PASSED | trading-kernel | WP-03A | none |
| WP-03C | PASSED | trading-kernel | WP-02F | none |
| WP-03D | PASSED | trading-kernel | WP-03C | none |
| WP-03E | PASSED | trading-kernel | WP-03B–WP-03D | none |
| WP-03F | PASSED | trading-kernel | WP-03A–WP-03E | none |
| G03 | PASSED | trading-kernel + parity | WP-03A–WP-03F | none |
| WP-04A | PASSED | trading-kernel | G02 | none |
| WP-04B | PASSED | trading-kernel | WP-04A | none |
| WP-04C | PASSED | trading-kernel | WP-04B, G03 | none |
| WP-04D | PASSED | trading-kernel | WP-04C | none |
| WP-04E | PASSED | trading-kernel | WP-04D, WP-03C | none |
| G04 | PASSED | trading-kernel | WP-04A–WP-04E | none |
| WP-05A | PASSED | trading-kernel | G02 | none |
| WP-05B | PASSED | trading-kernel | WP-05A | none |
| WP-05C | PASSED | trading-kernel | WP-03B, WP-05B | none |
| WP-05D | PASSED | trading-kernel | G04, WP-05A–WP-05C | none |
| WP-05E | PASSED | trading-kernel | WP-05D | none |
| WP-05F | PASSED | trading-kernel | WP-05E | none |
| WP-05G | PASSED | trading-kernel | WP-05F, WP-02F | none |
| WP-05H | PASSED | trading-kernel | WP-05G, WP-02F | none |
| WP-05I | PASSED | trading-kernel | WP-05B, WP-05H | none |
| WP-05J | PASSED | trading-kernel | WP-02F, WP-03A | none |
| G05 | PASSED | trading-kernel | G04, WP-05A–WP-05J | none |
| WP-06A | PASSED | market-data-contracts | G02 | none |
| WP-06B | PASSED | backtest-runtime | WP-01B, WP-06A | none |
| WP-06C | PASSED | backtest-runtime | G04, WP-06A–WP-06B | none |
| WP-06D | PASSED | backtest-runtime | WP-02G, WP-03C | none |
| WP-06E | PASSED | backtest-runtime | G05, WP-06A–WP-06D | none |
| WP-06F | PASSED | backtest-runtime | WP-03E, WP-05A–WP-05C, WP-06B, WP-06E | none |
| WP-06G | PASSED | backtest-runtime | WP-06A–WP-06F | none |
| WP-06H | PASSED | tests/support | WP-02F–WP-02G | none |
| G06 | PASSED | tests/support + backtest-runtime integration | WP-06A–WP-06H, G03–G05 | none |
| WP-07A | PASSED | backtest-runtime | G06 | none |
| WP-07A-R1 | PASSED | backtest-runtime | WP-07A, G06 | none |
| WP-07B | PASSED | backtest-runtime | WP-07A | none |
| WP-07C | PASSED | backtest-runtime | WP-07B | none |
| WP-07D | PASSED | backtest-runtime | WP-07B–WP-07C | none |
| WP-07E | PASSED | backtest-runtime | WP-07A-R1, WP-07C–WP-07D | none |
| G07 | PASSED | backtest-runtime integration | WP-07A-R1, WP-07A–WP-07E | none |
| G08A | PASSED | trading-kernel profiles/cn_a_share | G07 | none |
| G08B | PASSED | trading-kernel profiles/cn_a_share | G08A | none |
| G08C | PASSED | trading-kernel profiles/cn_a_share | G08A, WP-04E, WP-05D, WP-05G | none |
| G08D | PASSED | trading-kernel profiles/cn_a_share | G08A, G08C, WP-05G | none |
| G08E | PASSED | trading-kernel profiles/cn_a_share | WP-05H, WP-05J | none |
| G08F | READY | trading-kernel profiles/cn_a_share | G08A, WP-06A, WP-06B | none |
| G08G | DRAFT | trading-domain + trading-kernel + backtest-runtime | G08F, G03 | Journal-replayable Lot effects, exact total Cost Basis, availability/tax/fractional-share fixtures |
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
status: PASSED
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
passed_commit: 878a70d88722e3c88ae3547d5eb463d374cbb99b
artifact_hashes:
  tests/fixtures/kernel/kernel-profile-ports-v1.json: sha256:36f5ec3428083bd4eefddeeee5bfdac50cfe353d89197c7654375630bd4a4904
  build/acceptance/wp-02f-pytest.xml: sha256:40bceeb8c6680afe19bbf14fd0e981f7bf820713116c00e3788cd5fb53244273
  build/acceptance/wp-02f-import-boundary-report.json: sha256:8f17d0760d246b7c1d5f29327209afa6930ae3134be210ac3f6d8f44457a0a5c
```

### WP-02F Acceptance

已冻结以下实现边界：

1. 十二个 Market/Account semantics Port 均为 `runtime_checkable` generic Protocol；每个 Port 有独立语义方法名，不使用一个万能 `evaluate()` 或 arbitrary payload；
2. 每个 Protocol 显式绑定 `RequestT`、`ResultT`、`FailureT`，三者必须满足 immutable/canonical `ProfilePortContract`；未来具体规则 WP 必须用 Trading Domain 类型组成这些 contract，不能传入 DataFrame、Vendor DTO、Runtime State、裸 `dict[str, object]` 或 `Any`；
3. `ProfileComponentRef` 固定 `ProfilePortType`、canonical component key、正整数 version 和 `sha256:` component digest；Profile Registry、component compatibility 和 resolved profile digest 不属于本 WP；
4. `ProfilePortOutcome` 保存 component ref、canonical input hash 和 exactly-one-of result/failure；它不把 exception text、log text 或隐式 `None` 当失败协议；
5. 共享 Profile lookup/incompatibility/applicability reason code 属于 WP-02H，本 WP 只保留 typed `FailureT` seam，避免提前冻结错误 taxonomy；
6. 本 WP 只有 Protocol、identity/outcome value contracts 和 tests 内 Test Adapter；没有 concrete A-share/Binance/Synthetic Profile、registry/resolver、no-op default、simulation assumption、DataFrame、Vendor SDK、网络或可变运行状态；
7. `trading-domain` 与 `trading-kernel` 均发布 PEP 561 `py.typed` marker，使跨 package Protocol 类型检查不依赖 `ignore_missing_imports`。

WP-02F 的实现已冻结在 immutable commit `878a70d88722e3c88ae3547d5eb463d374cbb99b`，状态为 `PASSED`。

验证记录：

```text
Kernel Profile Port contract tests                                     11 passed
Canonical golden fixture                                                1 passed
Public API + repository cleanliness boundaries                         5 passed
Trading-kernel import boundary                                          PASS (19 files)
Full test suite                                                        166 passed
mypy                                                                    no issues (18 files)
Primary LSP                                                             clean
pi-lens full scoped scan                                                no findings
Python                                                                  3.13.5
```

## 19. WP-02G Acceptance Card

```yaml
id: WP-02G
status: PASSED
depends_on:
  - WP-02A
  - WP-02B
  - WP-02C
  - WP-02D
  - WP-02F
owner_package: backtest-runtime
public_interface:
  - crypto_quant_backtest.SimulationPortType
  - crypto_quant_backtest.SimulationPortContract
  - crypto_quant_backtest.SimulationComponentRef
  - crypto_quant_backtest.SimulationCapabilityRequirement
  - crypto_quant_backtest.SimulationPortSpec
  - crypto_quant_backtest.SimulationPortOutcome
  - crypto_quant_backtest.ExecutionModel
  - crypto_quant_backtest.SlippageModel
  - crypto_quant_backtest.LatencyModel
  - crypto_quant_backtest.LiquidityModel
  - crypto_quant_backtest.LiquidationAuditModel
  - crypto_quant_backtest.CloseoutPolicy
test_commands:
  contract: uv run pytest -q tests/runtime/ports/test_simulation_port_contracts.py
  fixture: uv run pytest -q tests/runtime/ports/test_simulation_port_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - simulation-profile-ports-v1
expected_artifacts:
  - tests/fixtures/runtime/simulation-profile-ports-v1.json
  - build/acceptance/wp-02g-pytest.xml
failure_contracts:
  - invalid-simulation-port-type
  - invalid-simulation-component-key
  - invalid-simulation-component-version
  - invalid-simulation-component-digest
  - invalid-simulation-capability-key
  - invalid-simulation-capability-version
  - duplicate-simulation-capability
  - noncanonical-simulation-applicability
  - simulation-result-and-failure
  - simulation-result-and-failure-missing
  - invalid-simulation-input-hash
  - missing-simulation-port-method
  - market-port-identity-reused-for-simulation
  - implicit-zero-or-noop-simulation-default
  - live-runtime-depends-on-backtest-runtime
allowed_grade: development
evidence:
  - pytest-report
  - simulation-profile-port-fixture-hash
  - public-api-import-report
passed_commit: 4d06d91079c68fdd281cae3a43f31cc77af9d4ff
artifact_hashes:
  tests/fixtures/runtime/simulation-profile-ports-v1.json: sha256:18b95808f7b71e59cbe1d5f53a0b7e7b31177fed2a37f6b396ff6cab61173f5c
  build/acceptance/wp-02g-pytest.xml: sha256:f4ffd560997786b646eef9b8504f79e396df376b1370dca542619a6fa9879d6b
  build/acceptance/wp-02g-import-boundary-report.json: sha256:5fac8c61736931791c9d8e552034ef09d526549b7641c50530247bf686394e0d
```

### WP-02G Readiness

已冻结以下边界：

1. Simulation Ports 由 `backtest-runtime` 独占，使用独立于 `ProfilePortType/ProfileComponentRef/ProfilePortOutcome` 的 identity、spec 和 outcome contracts；Market/Account semantics 仍只属于 `trading-kernel`；
2. 六个 Port 是 `runtime_checkable` generic Protocol，每个有独立语义方法名和 typed Request/Result/Failure；这些值必须满足 immutable canonical `SimulationPortContract`，不能使用 DataFrame、Vendor DTO、Runtime mutable state、裸 `dict` 或 `Any`；
3. `SimulationPortSpec` 固定 component ref、canonical applicability contract 及 canonical-sorted unique capability requirements；它显式允许空 requirements，但没有缺失属性或隐式 default；
4. `SimulationPortOutcome` 保存 component identity、canonical input hash 和 exactly-one-of result/failure；预期不适用、能力不足或无法模拟必须走 typed failure seam，具体共享 reason code 在 WP-02H 冻结；
5. 本 WP 不冻结 CalibrationEvidence payload、具体 applicability 条件、RandomStream derivation、ResolvedSimulationProfile、registry/resolver、next-open/slippage 数值、bar liquidation 或 closeout 行为；这些属于后续独立 Gate；
6. 没有 concrete/no-op/zero-slippage/unlimited-liquidity/zero-latency/automatic-closeout model。Test Adapter 只验证调用 seam，不进入任何 Production Registry；
7. `backtest-runtime` 发布 PEP 561 `py.typed`；`trading-domain` 和 `trading-kernel` 不能反向导入它，未来 Live Runtime 也不依赖它。

WP-02G 的实现已冻结在 immutable commit `4d06d91079c68fdd281cae3a43f31cc77af9d4ff`，状态为 `PASSED`。

验证记录：

```text
Simulation Profile Port contract tests                                 17 passed
Canonical golden fixture                                                1 passed
Public API + repository cleanliness boundaries                         5 passed
Acceptance test report                                                 23 passed
Backtest-runtime import boundary                                        PASS (20 files)
Full test suite                                                        184 passed
mypy                                                                    no issues (4 files)
Primary LSP                                                             clean
pi-lens scoped review                                                   no blocking findings; 2 intentional type-separation duplication warnings deferred
uv lock --check                                                         PASS
Python                                                                  3.13.5
```

## 20. WP-02H Acceptance Card

```yaml
id: WP-02H
status: PASSED
depends_on:
  - WP-02A
  - WP-02B
  - WP-02C
  - WP-02D
  - WP-02E
  - WP-02F
  - WP-02G
owner_package: trading-domain
public_interface:
  - crypto_quant_domain.ProfileComponentFailureCode
  - crypto_quant_domain.ProfileComponentFailure
test_commands:
  contract: uv run pytest -q tests/domain/profile_errors/test_profile_component_failures.py
  fixture: uv run pytest -q tests/domain/profile_errors/test_profile_component_error_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - profile-component-errors-v1
expected_artifacts:
  - tests/fixtures/domain/profile-component-errors-v1.json
  - build/acceptance/wp-02h-pytest.xml
failure_contracts:
  - invalid-profile-component-failure-code
  - invalid-profile-component-failure-subject
  - noncanonical-profile-component-failure-subject
  - freeform-profile-error-message
  - profile-failure-exception-text-protocol
  - market-or-vendor-specific-profile-error
allowed_grade: development
evidence:
  - pytest-report
  - profile-component-error-fixture-hash
  - public-api-import-report
passed_commit: 620d52031e900e5c4516a80588b324a2d7c6146d
artifact_hashes:
  tests/fixtures/domain/profile-component-errors-v1.json: sha256:e90995c6ee0aabcca576780547d588f85ef6b6be8d7d5663e560d5c0892fe20a
  build/acceptance/wp-02h-pytest.xml: sha256:4216e1ef79b42f0dde467a9edef94ebdfe17feea43fc8c414a3bdf1f0cc27cb5
  build/acceptance/wp-02h-import-boundary-report.json: sha256:d785d2fe7b2331272e1f686196a32f47f5924ef65e880d77c4c2b5b9b08237bb
```

### WP-02H Acceptance

已冻结以下边界：

1. `ProfileComponentFailureCode` 只包含五个跨 Kernel、Runtime 和未来 Resolver 共用的稳定 canonical code：`profile_lookup_failed`、`component_incompatible`、`capability_missing`、`applicability_violation` 和 `unsupported_semantics`；
2. `ProfileComponentFailure` 是 immutable canonical value，只包含 typed reason code 和 non-empty NFC `subject_key`。`subject_key` 标识失败主体，不承载日志、异常消息、Vendor DTO、任意 metadata 或用户显示文本；
3. Kernel `ProfilePortOutcome.failure` 与 Runtime `SimulationPortOutcome.failure` 可以使用该值作为具体 `FailureT`，无需由 Trading Domain 反向依赖两个 Port package；
4. 预期业务失败必须显式返回 `ProfileComponentFailure` 或未来更具体的 typed failure，不能以 `None`、通用 `ValueError`、exception text 或 log matching 作为跨模块协议；
5. 本 WP 不实现 Profile Registry/Resolver、component compatibility 算法、capability/applicability 检查、Run Outcome 映射、异常层、日志呈现或具体市场/供应商错误；
6. 新增更细 reason code 属于显式 schema/version 变更，不能静默复用现有 code 改变语义。

WP-02H 的实现已冻结在 immutable commit `620d52031e900e5c4516a80588b324a2d7c6146d`，状态为 `PASSED`。

验证记录：

```text
Profile component failure contract tests                               12 passed
Canonical golden fixture                                                1 passed
Public API + repository cleanliness boundaries                         5 passed
Trading-domain import boundary                                          PASS (21 files)
Full test suite                                                        197 passed
mypy                                                                    no issues (17 files)
Primary LSP                                                             clean
pi-lens scoped review                                                   no findings
uv lock --check                                                         PASS
Python                                                                  3.13.5
```

## 21. G02 Acceptance Card

```yaml
id: G02
status: PASSED
depends_on:
  - WP-02A
  - WP-02B
  - WP-02C
  - WP-02D
  - WP-02E
  - WP-02F
  - WP-02G
  - WP-02H
owner_package: trading-domain + trading-kernel + backtest-runtime
public_interface:
  - canonical Instrument, Target, Decision, Order, Execution, Accounting and Artifact contracts
  - generic Market/Account Profile Ports
  - type-separated Simulation Profile Ports
  - shared profile component failure taxonomy
test_commands:
  contract: uv run pytest -q tests/domain/instruments tests/domain/decisions tests/domain/execution tests/domain/accounting tests/domain/artifacts tests/domain/profile_errors tests/kernel/ports tests/runtime/ports
  fixture: uv run pytest -q tests/domain/instruments tests/domain/decisions tests/domain/execution tests/domain/accounting tests/domain/artifacts tests/domain/profile_errors tests/kernel/ports tests/runtime/ports --junitxml=build/acceptance/g02-contracts-pytest.xml
  boundary: uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g02-import-boundary-report.json
fixture_ids:
  - instrument-identity-timeline-v1
  - target-decision-contracts-v1
  - order-execution-contracts-v1
  - accounting-contracts-v1
  - artifact-envelope-catalog-v1
  - kernel-profile-ports-v1
  - simulation-profile-ports-v1
  - profile-component-errors-v1
expected_artifacts:
  - tests/fixtures/domain/instrument-identity-timeline-v1.json
  - tests/fixtures/domain/target-decision-contracts-v1.json
  - tests/fixtures/domain/order-execution-contracts-v1.json
  - tests/fixtures/domain/accounting-contracts-v1.json
  - tests/fixtures/domain/artifact-envelope-catalog-v1.json
  - tests/fixtures/kernel/kernel-profile-ports-v1.json
  - tests/fixtures/runtime/simulation-profile-ports-v1.json
  - tests/fixtures/domain/profile-component-errors-v1.json
  - build/acceptance/g02-contracts-pytest.xml
  - build/acceptance/g02-import-boundary-report.json
failure_contracts:
  - g02-domain-contract-regression
  - g02-canonical-hash-drift
  - g02-profile-port-contract-regression
  - g02-market-simulation-port-conflation
  - g02-unstructured-profile-failure
  - g02-domain-runtime-reverse-dependency
  - g02-generic-kernel-concrete-profile-import
  - g02-external-framework-or-vendor-dto-leakage
  - g02-implicit-profile-or-simulation-default
allowed_grade: development
evidence:
  - eight-fixture-hashes
  - pytest-report
  - import-boundary-report
  - static-type-report
passed_commit: 0df9b63d0198742a097920441b506905a312818e
artifact_hashes:
  tests/fixtures/domain/instrument-identity-timeline-v1.json: sha256:c883d97d59e9b118ba92aada03527b35408057758756e1109609ece0600803a7
  tests/fixtures/domain/target-decision-contracts-v1.json: sha256:e871629a26cb1fca0d72dd1561a71efd36ac6878f2dd5bd2e307982bb3aca9e7
  tests/fixtures/domain/order-execution-contracts-v1.json: sha256:f113a7d34dbfe196202fc7d8effb0e427517cc3dfe2ebfb75c1577b828c8b4d5
  tests/fixtures/domain/accounting-contracts-v1.json: sha256:b63ea512fd5b43043b8b82a0c2fe66cd7ebceabb8825fba52904f9497e5fad17
  tests/fixtures/domain/artifact-envelope-catalog-v1.json: sha256:ec5138bcc003ecd59a1821f20999bfea3072493e3dfccf8cd781b4f4963b7e16
  tests/fixtures/kernel/kernel-profile-ports-v1.json: sha256:36f5ec3428083bd4eefddeeee5bfdac50cfe353d89197c7654375630bd4a4904
  tests/fixtures/runtime/simulation-profile-ports-v1.json: sha256:18b95808f7b71e59cbe1d5f53a0b7e7b31177fed2a37f6b396ff6cab61173f5c
  tests/fixtures/domain/profile-component-errors-v1.json: sha256:e90995c6ee0aabcca576780547d588f85ef6b6be8d7d5663e560d5c0892fe20a
  build/acceptance/g02-contracts-pytest.xml: sha256:00575ca52113a950568792783cbd443d3fcdcfca636866143e9291219ca86a42
  build/acceptance/g02-import-boundary-report.json: sha256:d785d2fe7b2331272e1f686196a32f47f5924ef65e880d77c4c2b5b9b08237bb
```

### G02 Acceptance

WP-02A 至 WP-02H 已分别通过。G02 聚合 Gate 只验证已冻结契约的组合完整性、canonical 稳定性和 package 方向，不新增领域对象、Profile 实现、Resolver、Runtime 行为或市场语义。通过条件：

1. 八组 WP fixture 和 contract test 在同一 Python 3.13 workspace 中共同通过；
2. 所有已发布 Domain 对象继续支持稳定 canonical serialization/hash；Candidate 和 raw Artifact source bytes 等明确非 canonical 对象保持在各自审计边界；
3. `trading-domain` 不依赖 Kernel/Runtime/Pandas/Hummingbot/Vendor SDK，Generic Kernel 不导入具体市场 Profile，Runtime 不反向污染 Domain/Kernel；
4. Market/Account Profile Ports、Simulation Ports 和 shared failure taxonomy 保持类型分离但可结构化组合；
5. 未配置组件不存在 no-op、零滑点、无限流动性、零延迟或其他隐式默认。

G02 聚合验收冻结在 immutable acceptance commit `0df9b63d0198742a097920441b506905a312818e`，状态为 `PASSED`。

验证记录：

```text
G02 domain/kernel/runtime contracts and fixtures                       89 passed
Workspace import boundary                                               PASS (21 files)
Full test suite                                                        197 passed
mypy                                                                    no issues (19 files)
uv lock --check                                                         PASS
Python                                                                  3.13.5
```

## 22. WP-03A Acceptance Card

```yaml
id: WP-03A
status: PASSED
depends_on:
  - G02
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.AccountingJournal
  - crypto_quant_trading.JournalReplayCursor
  - crypto_quant_trading.JournalReplay
  - crypto_quant_trading.JournalError
  - crypto_quant_trading.JournalEntryConflictError
  - crypto_quant_trading.JournalOrderingError
  - crypto_quant_trading.JournalCursorError
test_commands:
  contract: uv run pytest -q tests/kernel/journal/test_immutable_journal.py
  fixture: uv run pytest -q tests/kernel/journal/test_journal_replay_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - immutable-journal-replay-v1
expected_artifacts:
  - tests/fixtures/kernel/immutable-journal-replay-v1.json
  - build/acceptance/wp-03a-pytest.xml
  - build/acceptance/wp-03a-import-boundary-report.json
failure_contracts:
  - non-journal-entry-append
  - conflicting-journal-entry-identity
  - late-journal-entry-insertion
  - invalid-replay-cursor-position
  - mismatched-replay-prefix-hash
  - reversed-replay-range
  - mutable-journal-update
  - journal-economic-projection-leakage
  - journal-profile-or-market-dependency
allowed_grade: development
evidence:
  - pytest-report
  - immutable-journal-replay-fixture-hash
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: c0c95cf822cd23751f0e77e37eab8739dc51757f
artifact_hashes:
  tests/fixtures/kernel/immutable-journal-replay-v1.json: sha256:107f291470008c1de90133ecadc08839367a086368cbaf9a992c4475dd7a81b8
  build/acceptance/wp-03a-pytest.xml: sha256:1538ea54d33ca451b919fd32a3f7a3b3d14756bfdf4c2584799ebbb2d0032216
  build/acceptance/wp-03a-import-boundary-report.json: sha256:092a85810d8de5a8fc4805b518760ffbf3499931ee502496d5206cc9eb4121c1
```

### WP-03A Acceptance

已冻结以下边界：

1. `AccountingJournal` 是 immutable、in-memory、append-only value。它只拥有 Entry validation/order/deduplication/hash/replay，不拥有 Cash、Position、PnL 或外部持久化；
2. Entry order 固定为 `(recorded_at, journal_entry_id.value)`。无序 batch 在 append 前稳定排序；已发布 Journal prefix 之后的 late insert 被拒绝，不能静默重写旧 cursor；
3. 相同 `journal_entry_id` + 相同 canonical hash 是 idempotent no-op；相同 ID + 不同 canonical hash 抛出结构化 `JournalEntryConflictError`；
4. 空 Journal 使用固定 genesis hash，后续 prefix 通过前一 prefix hash 与 Entry canonical hash 形成确定性 hash chain；
5. `JournalReplayCursor` 包含 position 和 prefix hash。`replay()` 使用半开区间 `[start, stop)`，同时验证两个字段，并返回 immutable `JournalReplay`；
6. Golden fixture 使用无经济语义 reducer 验证 genesis→cursor→end 与 genesis→end parity，不提前实现 WP-03B Ledger projection；
7. 本 WP 不实现 Accounting translation、市场/Profile 读取、Mark/Valuation、Settlement mutation、mutable store、EngineCheckpoint 或 Run Outcome。

WP-03A 的实现已冻结在 immutable commit `c0c95cf822cd23751f0e77e37eab8739dc51757f`，状态为 `PASSED`。

验证记录：

```text
Immutable Journal contract tests                                       7 passed
Canonical replay golden fixture                                        1 passed
Public API + repository cleanliness boundaries                         5 passed
Acceptance test report                                                13 passed
Trading-kernel import boundary                                         PASS (22 files)
Full test suite                                                        205 passed
mypy                                                                    no issues (7 files)
Primary LSP                                                             clean
pi-lens scoped review                                                   no findings
uv lock --check                                                         PASS
Python                                                                  3.13.5
```

## 23. WP-03B Acceptance Card

```yaml
id: WP-03B
status: PASSED
depends_on:
  - WP-03A
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.LedgerBalanceRegistration
  - crypto_quant_trading.LedgerSchema
  - crypto_quant_trading.LedgerState
  - crypto_quant_trading.GenericLedger
  - crypto_quant_trading.LedgerError
  - crypto_quant_trading.UnregisteredBalanceKeyError
  - crypto_quant_trading.LedgerFinancialInvariantError
  - crypto_quant_trading.LedgerStateMismatchError
test_commands:
  contract: uv run pytest -q tests/kernel/ledger/test_generic_ledger.py
  fixture: uv run pytest -q tests/kernel/ledger/test_generic_ledger_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - generic-ledger-projection-v1
expected_artifacts:
  - tests/fixtures/kernel/generic-ledger-projection-v1.json
  - build/acceptance/wp-03b-pytest.xml
  - build/acceptance/wp-03b-import-boundary-report.json
failure_contracts:
  - invalid-ledger-schema
  - duplicate-ledger-balance-registration
  - unregistered-balance-key
  - unregistered-attribution-currency
  - balance-identity-or-scale-mismatch
  - forged-ledger-cursor
  - forged-ledger-resume-state
  - ledger-market-or-profile-dependency
  - ledger-unrealized-pnl-leakage
  - ledger-economic-policy-rejection
allowed_grade: development
evidence:
  - pytest-report
  - generic-ledger-golden-fixture-hash
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 0f5f2bf3416594b527603e4dc836a5a230ff9340
artifact_hashes:
  tests/fixtures/kernel/generic-ledger-projection-v1.json: sha256:e1f728f2117348331c8866f0ee44fdb38d47e41402f01a09fc7c529694c8f338
  build/acceptance/wp-03b-pytest.xml: sha256:dbe05eb39014c9a2cb8592a26bdb627e6606f9d9c4d3c1629cf1c173029e4255
  build/acceptance/wp-03b-import-boundary-report.json: sha256:326fd0a94f53ebe76ac8005b7eee36137dc39806426234d5f6e94ac3df131e74
```

### WP-03B Acceptance

已冻结以下边界：

1. `LedgerSchema` 显式注册 typed Cash/Position balance key 与唯一 Scale；注册顺序 canonical 化，未知 key 或未知 attribution currency fail closed；
2. v1 的 generic financial invariant 是 closed registered dimensions 与 exact identity/scale arithmetic。Ledger 不做跨资产估值配平；具体 PositionAccountingModel 的经济配平、Lot 和 Cost Basis 留给 WP-03F；
3. `LedgerState` 是 immutable projection，保存 schema hash、经验证 Journal cursor、Cash/Position 及 realized PnL/fee/financing 原生币种累计，并提供确定性 state hash；
4. `project()` 从 genesis replay；`resume()` 重新验证 prefix state parity 后继续，伪造 cursor 或 state 不能被信任；
5. Cash 注册 key 保留显式零值；零 Position 被移除；负 Cash 和 Short Position 是 truthful state，不由 Ledger 拒绝；
6. Ledger 不读取价格/Profile/Risk，不计算 unrealized PnL，不修改 Journal，不实现 Accounting translation、Lot/Cost Basis、Mark 或 Valuation。

WP-03B 的实现已冻结在 immutable commit `0f5f2bf3416594b527603e4dc836a5a230ff9340`，状态为 `PASSED`。

验证记录：

```text
Generic Ledger contract tests                                          8 passed
Canonical projection golden fixture                                    1 passed
Public API + repository cleanliness boundaries                         5 passed
Acceptance test report                                                 14 passed
Trading-kernel import boundary                                         PASS (23 files)
Full test suite                                                         214 passed
mypy                                                                    no issues (7 files)
Primary LSP                                                             clean
pi-lens scoped review                                                   no findings
uv lock --check                                                         PASS
Python                                                                  3.13.5
```

## 24. WP-03C Acceptance Card

```yaml
id: WP-03C
status: PASSED
depends_on:
  - WP-02F
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.MarkObservation
  - crypto_quant_trading.StaleMarkPolicy
  - crypto_quant_trading.ResolvedMark
  - crypto_quant_trading.MarkResolutionFailureCode
  - crypto_quant_trading.MarkResolutionFailure
  - crypto_quant_trading.MarkResolutionOutcome
  - crypto_quant_trading.MarkResolver
test_commands:
  contract: uv run pytest -q tests/kernel/marks/test_mark_resolver.py
  fixture: uv run pytest -q tests/kernel/marks/test_mark_resolver_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - deterministic-mark-resolution-v1
expected_artifacts:
  - tests/fixtures/kernel/deterministic-mark-resolution-v1.json
  - build/acceptance/wp-03c-pytest.xml
  - build/acceptance/wp-03c-import-boundary-report.json
failure_contracts:
  - missing-mark-at-requested-time
  - unavailable-price-purpose
  - ambiguous-latest-mark
  - stale-mark-max-age
  - forward-fill-policy-violation
  - future-observation-or-revision-selection
  - price-instrument-or-currency-identity-mismatch
  - implicit-cross-purpose-fallback
  - mark-data-source-query
  - mark-currency-conversion-or-snapshot-leakage
allowed_grade: development
evidence:
  - pytest-report
  - deterministic-mark-resolution-fixture-hash
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 1e465930838738804ef1c09b9b3198361fb005ff
artifact_hashes:
  tests/fixtures/kernel/deterministic-mark-resolution-v1.json: sha256:bbdda823a1d75e0ac08f38872faf3f73a31f5c5f34dac3db2c699f8352026ea4
  build/acceptance/wp-03c-pytest.xml: sha256:e96b80711ad21c8949bf8efd2d41a180e950992b15351e89b3736568198af15a
  build/acceptance/wp-03c-import-boundary-report.json: sha256:c4f3489717fa193c3ef70ce4bd2745f180fd0d731abd2beb0a91eb3ee1722e1f
```

### WP-03C Acceptance

已冻结以下边界：

1. `MarkObservation` 是调用方提供的 immutable Price Stream fact，包含 typed Instrument/Currency/PricePurpose/Price、`observed_at`、`available_at`、stream/source-event/revision identity；Resolver 不查询 Reader、Bundle、网络或文件；
2. `StaleMarkPolicy` 绑定单一 `PricePurpose`，以整数纳秒声明 `max_age` 和是否允许同用途 forward-fill，并具有稳定 key/version/hash；它不能授权跨用途 fallback；
3. Resolver 只考虑 `observed_at <= requested_at` 且 `available_at <= requested_at` 的同 Instrument、同 Purpose observations。输入顺序不影响结果，未来 event/revision 不可见；
4. 最新合法 event time 必须唯一；同一最新 event time 存在多个合法 revision 时返回 `ambiguous_mark`，Revision winner selection 不在本 WP 猜测；
5. 无 Instrument fact 返回 `missing_mark`；存在 Instrument fact 但未提供所需 Purpose 返回 `price_purpose_unavailable`；无 point-in-time 合法 observation 返回 `missing_mark`；max-age 或 forward-fill 约束不满足返回 `stale_mark`；
6. `ResolvedMark` 保留 source stream/event/revision identity、event/available/requested time、typed PricePurpose/Price、age、Policy identity，并由这些 canonical facts 产生稳定 mark identity；
7. 本 WP 不实现数据读取、market-specific stream mapping、revision timeline selection、Execution Price fallback、币种换算、PortfolioSnapshot、Profile Resolver 或 Run Outcome mapping。

WP-03C 的实现已冻结在 immutable commit `1e465930838738804ef1c09b9b3198361fb005ff`，状态为 `PASSED`。

验证记录：

```text
MarkResolver contract tests                                             7 passed
Deterministic mark-resolution golden fixture                            1 passed
Public API + repository cleanliness boundaries                         5 passed
Acceptance test report                                                 13 passed
Trading-kernel import boundary                                         PASS (24 files)
Full test suite                                                         222 passed
mypy                                                                    no issues (7 files)
Primary LSP                                                             clean
pi-lens scoped review                                                   no findings
uv lock --check                                                         PASS
Python                                                                  3.13.5
```

## 25. WP-03D Acceptance Card

```yaml
id: WP-03D
status: PASSED
depends_on:
  - WP-03C
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.CurrencyValuationEdge
  - crypto_quant_trading.CurrencyValuationGraph
  - crypto_quant_trading.CurrencyValuationPath
  - crypto_quant_trading.CurrencyValuationPathRequest
  - crypto_quant_trading.CurrencyValuationPathSelection
  - crypto_quant_trading.CurrencyValuationResolution
  - crypto_quant_trading.CurrencyValuationFailureCode
  - crypto_quant_trading.CurrencyValuationFailure
  - crypto_quant_trading.CurrencyValuationOutcome
test_commands:
  contract: uv run pytest -q tests/kernel/valuation/test_currency_valuation_graph.py
  fixture: uv run pytest -q tests/kernel/valuation/test_currency_valuation_graph_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - currency-valuation-graph-v1
expected_artifacts:
  - tests/fixtures/kernel/currency-valuation-graph-v1.json
  - build/acceptance/wp-03d-pytest.xml
  - build/acceptance/wp-03d-import-boundary-report.json
failure_contracts:
  - valuation-edge-currency-or-purpose-mismatch
  - valuation-edge-not-point-in-time
  - duplicate-valuation-edge
  - missing-valuation-path
  - non-unique-valuation-path-without-policy
  - valuation-policy-rejected
  - valuation-policy-wrong-port-or-input-hash
  - valuation-policy-selected-unknown-path
  - implicit-stablecoin-peg
  - graph-mark-resolution-or-data-query
  - graph-money-conversion-or-snapshot-leakage
allowed_grade: development
evidence:
  - pytest-report
  - currency-valuation-graph-fixture-hash
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 885189644dab25a4156410aa9d17839044f19d38
artifact_hashes:
  tests/fixtures/kernel/currency-valuation-graph-v1.json: sha256:8480953669aa0244a8916d7ba45fae3b821af596231dc2c472682b71d0d28fc0
  build/acceptance/wp-03d-pytest.xml: sha256:e8a32c8d6616beb1b0ba514e4b5d01c6ddf5b9270f53ad466ff6babe4a632fc0
  build/acceptance/wp-03d-import-boundary-report.json: sha256:5733bbd7ba24b5718da4b68025ae0c7723c6f4af8c71674da95b38ce986225f1
```

### WP-03D Acceptance

已冻结以下边界：

1. `CurrencyValuationEdge` 是调用方提供的 immutable 有向边：一个 source `CurrencyId` 通过一个 `ResolvedMark` 指向该 Mark 的 quote `CurrencyId`；它保存完整 Mark/PricePurpose/source-event/revision provenance，不从 Instrument symbol 猜测币种关系；
2. `CurrencyValuationGraph` 只包含同一 `UtcInstant`、同一 `PricePurpose` 的 supplied edges；Graph 不查询 MarkResolver、Reader、Bundle、网络或文件，也不自行生成逆向 Edge；
3. Graph 只枚举无重复 Currency 的简单有向路径。输入 Edge 顺序不影响 graph/path identity；重复 Edge identity fail closed；
4. source 等于 reporting currency 时必须返回显式 zero-edge identity path；不同 Currency 之间没有 Edge 时返回 `missing_path`，因此 Stablecoin 不存在隐式 1:1 peg；
5. 唯一路径可直接解析；存在多个 candidate paths 时只能由显式版本化 `CurrencyValuationPolicy` 的 typed `ProfilePortOutcome` 选择，未提供 Policy 时返回 `non_unique_path`；
6. Graph 验证 Policy component type、request hash 和 selected path hash；Policy failure 或伪造/未知选择均结构化失败，不按输入顺序猜测；
7. 本 WP 只产出 point-in-time path/provenance evidence，不计算 `Money`、不决定数值舍入、不构建市场特定 FX/Stablecoin Edge、不选择 Mark、不修改 Ledger，也不计算 `PortfolioSnapshot`。

WP-03D 的实现已冻结在 immutable commit `885189644dab25a4156410aa9d17839044f19d38`，状态为 `PASSED`。

验证记录：

```text
CurrencyValuationGraph contract tests                                  8 passed
Currency valuation golden fixture                                      1 passed
Public API + repository cleanliness boundaries                         5 passed
Acceptance test report                                                14 passed
Trading-kernel import boundary                                         PASS (25 files)
Full test suite                                                       231 passed
mypy                                                                   no issues (8 files)
Primary LSP                                                            clean
pi-lens scoped review                                                  no findings
uv lock --check                                                        PASS
Python                                                                 3.13.5
```

## 26. WP-03E Acceptance Card

```yaml
id: WP-03E
status: PASSED
depends_on:
  - WP-03B
  - WP-03C
  - WP-03D
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.PortfolioValueKind
  - crypto_quant_trading.PortfolioValueRef
  - crypto_quant_trading.ReportingCurrencyValuation
  - crypto_quant_trading.SnapshotProjectionFailureCode
  - crypto_quant_trading.SnapshotProjectionFailure
  - crypto_quant_trading.SnapshotProjectionOutcome
  - crypto_quant_trading.PortfolioSnapshotProjector
test_commands:
  contract: uv run pytest -q tests/kernel/snapshots/test_portfolio_snapshot_projector.py
  fixture: uv run pytest -q tests/kernel/snapshots/test_portfolio_snapshot_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - portfolio-snapshot-projection-v1
expected_artifacts:
  - tests/fixtures/kernel/portfolio-snapshot-projection-v1.json
  - build/acceptance/wp-03e-pytest.xml
  - build/acceptance/wp-03e-import-boundary-report.json
failure_contracts:
  - multiple-execution-accounts
  - missing-duplicate-or-unexpected-valuation
  - native-ledger-value-mismatch
  - reporting-currency-or-scale-mismatch
  - valuation-path-source-target-mismatch
  - valuation-time-or-price-purpose-mismatch
  - currency-valuation-graph-mismatch
  - missing-extra-or-future-mark
  - position-mark-or-notional-mismatch
  - implicit-currency-path-selection-or-rate-invention
  - snapshot-data-query-or-ledger-mutation
  - lot-cost-basis-margin-or-accounting-leakage
allowed_grade: development
evidence:
  - pytest-report
  - portfolio-snapshot-projection-fixture-hash
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 230bec2b166639595198a31fa5f6cba4fc158fe0
artifact_hashes:
  tests/fixtures/kernel/portfolio-snapshot-projection-v1.json: sha256:39712c45f722761829718c52694bbf4e341b5e273a3d70a303bf25f7b1bd1d41
  build/acceptance/wp-03e-pytest.xml: sha256:120a3e294c16ca4b18ddcc5f0f65e92e14a923708be5c428ee15e63e43588fb2
  build/acceptance/wp-03e-import-boundary-report.json: sha256:99cb806a96b60753379bb04b9a7ac6ef67d7f3428e6307bfc5ce12c8c24d4954
```

### WP-03E Acceptance

已冻结以下边界：

1. Projector 是纯函数式组件，只消费 immutable `LedgerState`、supplied `ResolvedMark` 和 supplied `ReportingCurrencyValuation`；不查询 MarkResolver、Graph、Reader、Bundle、网络或文件；
2. `PortfolioValueRef` 用 typed balance key 标识 Cash、Position market value、Realized PnL、Unrealized PnL、Fee 和 Financing。每个 expected ref 必须有且仅有一个 valuation，不能按金额、Mapping 或输入顺序匹配；
3. 每个 `ReportingCurrencyValuation` 保存 native/reporting `Money`、已解析 `CurrencyValuationResolution`、统一 graph hash 和显式 Position notional quantization（仅 Position market value）。Projector 验证 path、currency、time、purpose 和 identity，但不重新选择 path 或发明 FX rate；
4. Position market value 必须由 Ledger Quantity × 对应 Valuation `ResolvedMark` 按显式 QuantizationPolicy exact 重算；Unrealized PnL 是 supplied native fact，Lot/Cost Basis 计算留给 WP-03F；
5. supplied mark set 必须精确等于 Position marks 与所有 valuation path edge marks 的并集。Future、缺失或额外 Mark fail closed；mark-set 和 staleness report identity 从完整 Mark provenance 确定性生成；
6. v1 只允许一个 account、一个 reporting currency 和一个 reporting Scale。Equity = converted Cash + converted Position market value；Realized/Unrealized/Fee/Financing 独立汇总且保留原始符号；
7. Snapshot 保留 Ledger state hash、mark-set hash、staleness report hash 和 currency graph hash；相同 inputs 的任意输入顺序产生 exact 相同 canonical Snapshot；
8. 本 WP 不实现 data read、Mark/path resolution、隐式 Stablecoin peg、Journal/Ledger mutation、Lot/Cost Basis、Margin Snapshot、instrument-specific accounting 或 Run Outcome mapping。

WP-03E 的实现已冻结在 immutable commit `230bec2b166639595198a31fa5f6cba4fc158fe0`，状态为 `PASSED`。

验证记录：

```text
PortfolioSnapshotProjector contract tests                              7 passed
Portfolio snapshot golden fixture                                      1 passed
Public API + repository cleanliness boundaries                         5 passed
Acceptance test report                                                13 passed
Trading-kernel import boundary                                         PASS (26 files)
Full test suite                                                       239 passed
mypy                                                                   no issues (26 files)
Primary LSP                                                            clean
pi-lens scoped review                                                  no findings
uv lock --check                                                        PASS
Python                                                                 3.13.5
```

## 27. WP-03F Acceptance Card

```yaml
id: WP-03F
status: PASSED
depends_on:
  - WP-03A
  - WP-03B
  - WP-03C
  - WP-03D
  - WP-03E
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.CostBasisMethod
  - crypto_quant_trading.CostBasisPolicy
  - crypto_quant_trading.LotConsumption
  - crypto_quant_trading.CashFillAccountingResult
  - crypto_quant_trading.FeeChargeAccountingResult
  - crypto_quant_trading.CashAccountingFailureCode
  - crypto_quant_trading.CashAccountingFailure
  - crypto_quant_trading.CashFillAccountingOutcome
  - crypto_quant_trading.FeeChargeAccountingOutcome
  - crypto_quant_trading.CashInstrumentAccounting
test_commands:
  contract: uv run pytest -q tests/kernel/accounting/test_cash_instrument_accounting.py
  fixture: uv run pytest -q tests/kernel/accounting/test_cash_instrument_accounting_golden.py
  parity: uv run pytest -q tests/parity/test_core_accounting_parity.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - cash-instrument-accounting-v1
  - core-accounting-wp03f-v1
expected_artifacts:
  - tests/fixtures/kernel/cash-instrument-accounting-v1.json
  - tests/parity/contracts/core-accounting-wp03f-v1.json
  - tests/parity/fixtures/core-accounting-wp03f-v1.expected.json
  - build/acceptance/wp-03f-core-accounting-parity.json
  - build/acceptance/wp-03f-pytest.xml
  - build/acceptance/wp-03f-import-boundary-report.json
failure_contracts:
  - missing-or-unsupported-cost-basis-policy
  - cash-position-fill-identity-or-scale-mismatch
  - malformed-or-duplicate-open-lot-state
  - insufficient-long-lot-quantity
  - implicit-short-or-reverse-crossing
  - unsupported-fee-basis-or-missing-related-fill
  - fee-currency-or-rule-provenance-mismatch
  - buy-fee-missing-acquisition-lot
  - fee-double-counted-in-gross-realized-pnl
  - mutable-journal-ledger-or-lot-store-side-effect
  - market-profile-settlement-tax-funding-or-derivative-leakage
  - missing-module-level-legacy-parity
allowed_grade: development
evidence:
  - pytest-report
  - cash-accounting-golden-fixture-hash
  - core-accounting-comparator-contract-hash
  - core-accounting-parity-report
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: c68c470c1cf33a4140c6055e88f5d6b292cbf22f
artifact_hashes:
  tests/fixtures/kernel/cash-instrument-accounting-v1.json: sha256:9285111fcaa429c60d6cd789f6ad7955c99351ffc520675a1890792996496c3e
  tests/parity/contracts/core-accounting-wp03f-v1.json: sha256:83bcceefe77b30176a009693e1b216d18119b29f9816bf683c7e60fa1322b0f5
  tests/parity/fixtures/core-accounting-wp03f-v1.expected.json: sha256:fc3e0a4e52d052264bcb5be77bb4e91bc137a322280d18d26e5713d533f135a8
  build/acceptance/wp-03f-core-accounting-parity.json: sha256:c44c622511a9e461c62eb255e99fb5d242fee5b37416ed51e1faaa86cc0af063
  build/acceptance/wp-03f-pytest.xml: sha256:08dbe34767bdb0479ba393baac0b702b70d8cadd7e257aafaa607562dc0e30e6
  build/acceptance/wp-03f-import-boundary-report.json: sha256:233ed74067f3321f4508811ce729fca60e2dab1132396ec9e8a38879e675c9ae
```

### WP-03F Acceptance

已冻结以下边界：

1. `CashInstrumentAccounting` 是纯翻译组件，只消费 supplied immutable facts/keys/lots/policies/IDs/time；不读取 Profile、Market、Journal、Ledger 或外部状态；
2. v1 唯一资格化方法是显式版本化 FIFO；没有默认 CostBasisPolicy。FIFO order 固定为 `opened_at` 后接 `lot_id`，输入 tuple 顺序不能改变结果；
3. Buy 建立 source-Fill acquisition Lot；Sell 只消费现有正 Long Lots。部分/全部卖出保留 Lot/source Fill provenance；超过可用数量不能形成隐式 Short；
4. Gross realized PnL 是 price-only proceeds 减 price cost basis。FeeAssessment 独立生成 FeeCharged Cash/fee attribution，因此 net economics 中 Fee 只出现一次；
5. 单 Fill Buy Fee 可分配到 acquisition Lot 的 allocated-fee provenance。Partial consumption 按 Policy rounding 拆分且守恒，但不重复改变 gross realized PnL；
6. v1 Fee translation 只资格化单一 Fill basis、非零、同 quote currency assessment，并在 source IDs 中记录 FeeAssessment、basis 和全部 rule identity；
7. `core-accounting` migration unit 已激活 `copy_with_parity` Comparator。Legacy expected 必须由冻结 archive 内真实 `accounting.py` 行为复核，新实现通过 exact closed-trade gross/fee/funding/net comparison；
8. 本 WP 不实现 Derivative、Settlement、Tax/Funding/Corporate Action、mutable Lot store、Runtime orchestration、Profile lookup 或 Order/Session aggregate fee allocation。

WP-03F 的实现已冻结在 immutable commit `c68c470c1cf33a4140c6055e88f5d6b292cbf22f`，状态为 `PASSED`。

验证记录：

```text
Cash accounting contract tests                                         8 passed
Cash accounting canonical golden fixture                               1 passed
Frozen crypto-quant-core accounting parity                             1 passed / MATCH
Public API + repository cleanliness boundaries                         5 passed
Acceptance test report                                                15 passed
Trading-kernel import boundary                                         PASS (27 files)
Legacy source baseline                                                 PASS (3 sources)
Full test suite                                                       249 passed
mypy                                                                   no issues (7 files)
Primary LSP                                                            clean
pi-lens scoped review                                                  no findings
uv lock --check                                                        PASS
Python                                                                 3.13.5
```

## 28. G03 Foundation Financial Kernel Acceptance Card

```yaml
id: G03
status: PASSED
depends_on:
  - WP-03A
  - WP-03B
  - WP-03C
  - WP-03D
  - WP-03E
  - WP-03F
owner_package: trading-kernel + parity
public_interface:
  - AccountingJournal -> GenericLedger replay
  - CashInstrumentAccounting Fill/Fee translation
  - MarkResolver valuation resolution
  - CurrencyValuationGraph reporting-currency path evidence
  - PortfolioSnapshotProjector rebuild
  - core-accounting Comparator Contract
test_commands:
  contract: uv run pytest -q tests/kernel/integration/test_foundation_financial_journey.py
  fixture: uv run pytest -q tests/kernel/journal/test_journal_replay_golden.py tests/kernel/ledger/test_generic_ledger_golden.py tests/kernel/marks/test_mark_resolver_golden.py tests/kernel/valuation/test_currency_valuation_graph_golden.py tests/kernel/snapshots/test_portfolio_snapshot_golden.py tests/kernel/accounting/test_cash_instrument_accounting_golden.py
  parity: uv run pytest -q tests/parity/test_core_accounting_parity.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - foundation-financial-journey-v1
  - immutable-journal-replay-v1
  - generic-ledger-projection-v1
  - deterministic-mark-resolution-v1
  - currency-valuation-graph-v1
  - portfolio-snapshot-projection-v1
  - cash-instrument-accounting-v1
  - core-accounting-wp03f-v1
expected_artifacts:
  - tests/fixtures/kernel/foundation-financial-journey-v1.json
  - build/acceptance/g03-pytest.xml
  - build/acceptance/g03-import-boundary-report.json
  - build/acceptance/wp-03f-core-accounting-parity.json
failure_contracts:
  - journal-ledger-cash-position-or-attribution-divergence
  - fee-counted-more-or-less-than-once
  - missing-or-wrong-purpose-valuation-mark
  - implicit-or-nonidentity-reporting-currency-path
  - snapshot-equity-or-pnl-component-divergence
  - snapshot-delete-rebuild-hash-mismatch
  - module-level-legacy-parity-not-match
  - aggregate-import-boundary-or-static-type-regression
  - test-only-financial-state-or-production-api
allowed_grade: development
evidence:
  - pytest-report
  - foundation-financial-journey-fixture-hash
  - core-accounting-parity-report
  - public-api-import-report
  - import-boundary-report
  - static-type-report
  - full-regression-report
passed_commit: 055a33a9d287859dcf77dbb47bd49a01c2dd6a01
artifact_hashes:
  tests/fixtures/kernel/foundation-financial-journey-v1.json: sha256:a4ea9c56939a10aa09326a019999ddfd6d2b4737fdae1ad1095505ad2765cc90
  build/acceptance/g03-pytest.xml: sha256:2e0edc2c656388ab1bbba82e78cdad97e2fd44a3b0bd435304eed62e636d04d7
  build/acceptance/g03-import-boundary-report.json: sha256:233ed74067f3321f4508811ce729fca60e2dab1132396ec9e8a38879e675c9ae
  build/acceptance/wp-03f-core-accounting-parity.json: sha256:c44c622511a9e461c62eb255e99fb5d242fee5b37416ed51e1faaa86cc0af063
```

### G03 Acceptance

已冻结以下 aggregate seam：

1. Gate 只组合 WP-03A–WP-03F 的公开 API，不新增旁路财务状态；
2. 固定旅程为 Deposit → Buy → Buy Fee → Valuation Mark/identity Currency path → Partial Sell → Sell Fee → Final Snapshot；
3. 最终 Journal-derived Ledger 必须精确得到 Cash、Position、gross realized PnL 和独立 Fee attribution；Fee 在 net economics 中只减一次；
4. Snapshot 使用 supplied ResolvedMark 和显式 Reporting Currency identity path，Equity = Cash + Position market value，realized/unrealized/fees 分开；
5. 删除 Snapshot 后，以相同 immutable evidence exact 重建相同 canonical Snapshot/hash；
6. `core-accounting` frozen-source Comparator 必须为 `MATCH`，并同时重跑全部 G03 component golden fixtures、Boundary、mypy 和完整 suite。

G03 的 aggregate verification 已冻结在 immutable commit `055a33a9d287859dcf77dbb47bd49a01c2dd6a01`，状态为 `PASSED`。

验证记录：

```text
Foundation financial journey contract                                  1 passed
WP-03A–WP-03F canonical golden fixtures                                 6 passed
Frozen crypto-quant-core accounting parity                             1 passed / MATCH
Public API + repository cleanliness boundaries                         5 passed
Aggregate acceptance test report                                      13 passed
Trading-kernel import boundary                                         PASS (27 files)
Full test suite                                                       250 passed
mypy                                                                   no issues (28 files)
Primary LSP                                                            clean
pi-lens aggregate review                                               no blocking findings
Intentional Kernel/Runtime nominal-port duplication                    2 deferred
uv lock --check                                                        PASS
Python                                                                 3.13.5
```

## 29. WP-04A Acceptance Card

```yaml
id: WP-04A
status: PASSED
depends_on:
  - G02
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.StrategyOutputValidationContext
  - crypto_quant_trading.StrategyValidationIssueCode
  - crypto_quant_trading.StrategyValidationIssue
  - crypto_quant_trading.StrategyValidationFailure
  - crypto_quant_trading.StrategyValidationResult
  - crypto_quant_trading.StrategyOutputValidator
test_commands:
  contract: uv run pytest -q tests/kernel/validation/test_strategy_output_validator.py
  fixture: uv run pytest -q tests/kernel/validation/test_strategy_output_validator_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - strategy-output-validation-v1
expected_artifacts:
  - tests/fixtures/kernel/strategy-output-validation-v1.json
  - build/acceptance/wp-04a-pytest.xml
  - build/acceptance/wp-04a-import-boundary-report.json
failure_contracts:
  - missing-or-unexpected-candidate-schema-field
  - invalid-field-type-or-canonical-text
  - strategy-or-sleeve-identity-mismatch
  - candidate-decision-time-mismatch
  - observed-through-after-decision-time
  - effective-time-before-decision-time
  - expiry-not-after-effective-time
  - unknown-instrument
  - instrument-outside-point-in-time-universe
  - duplicate-target-instrument
  - float-or-inexact-fixed-scale-quantization
  - invalid-confidence-scale-or-range
  - noncanonical-reason-or-evidence
  - invalid-candidate-entering-canonical-execution-trace
  - input-origin-or-run-outcome-mapping-leakage
allowed_grade: development
evidence:
  - pytest-report
  - strategy-output-validation-golden-fixture-hash
  - candidate-payload-evidence-hash
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: e92d7c561306c1d5bcfd9b1c19d038f68246468e
artifact_hashes:
  tests/fixtures/kernel/strategy-output-validation-v1.json: sha256:eaf7831685f6acab217dc6f6a8619cdda8477c679f4aeae01c37fb0db08b782c
  build/acceptance/wp-04a-pytest.xml: sha256:31663deef5005e8ca15d75ed8a9a771b1784a0731f9bb027c14c25cd1da6c144
  build/acceptance/wp-04a-import-boundary-report.json: sha256:81ad7a6bccc347c5910b1aff63a099df5957d5713ac56d201753f38718767ac4
```

### WP-04A Acceptance

已冻结以下边界：

1. `StrategyOutputValidationContext` 是 Validator 的可信调用上下文，只包含 expected Strategy/Sleeve identity、authoritative Decision Time、`InstrumentCatalog` 和该时点已解析的 point-in-time Universe；Validator 不推断 Universe 或上市状态；
2. Candidate v1 顶层 Schema 固定为 `schema_version/strategy_id/sleeve_id/decision_time/observed_through/effective_time/expires_at/targets/confidence/reason/evidence`。未知或缺失字段产生结构化 Issue，不被忽略；
3. 每个 Target 固定使用 `instrument_id: {venue, stable_key}` 与 `value`。`value` 仅接受 integer、`Decimal` 或 canonical decimal string，并 exact 转换为 scale-12 units；bool/float、NaN/Infinity 和超过 12 位不可精确量化的值 fail closed，禁止隐式 rounding；
4. Confidence 使用相同 exact decimal-to-scale-12 边界并额外限制 `[0, 1]`；Target 的经济杠杆范围不属于 Validator；
5. Unknown Instrument、Universe 外 Instrument、重复 Target、identity/time causality、reason/evidence canonical failure 均作为稳定排序的 `StrategyValidationIssue` 返回；不静默删除 Target，不产生部分 Decision；
6. `StrategyValidationFailure` 保存稳定 type-tagged Candidate payload evidence hash；原始 `StrategyDecisionCandidate` 由调用者作为失败证据保留，但 Candidate/Failure 都不能进入 canonical execution trace；
7. Validator 既不接收 `InputOrigin`，也不映射 FAILED/BLOCKED，不实现 DecisionBatch、Allocation/Netting、Risk、Sizing、Order Planning、Strategy invocation 或 Runtime orchestration。
8. Decimal-to-scale conversion 使用 Decimal tuple 的精确整数运算，不依赖进程 Decimal Context；高精度 Candidate 不得被静默 rounding。

WP-04A 的实现已冻结在 immutable commit `e92d7c561306c1d5bcfd9b1c19d038f68246468e`，状态为 `PASSED`。

验证记录：

```text
Strategy output validator contract tests                              18 passed
Strategy output validation canonical golden fixture                    2 passed
Public API + repository cleanliness boundaries                         5 passed
Acceptance test report                                                25 passed
Trading-kernel import boundary                                         PASS (28 files)
Full test suite                                                       270 passed
mypy                                                                   no issues (6 files)
Primary LSP                                                            clean
pi-lens scoped review                                                  no findings
uv lock --check                                                        PASS
Python                                                                 3.13.5
```

## 30. WP-04B Acceptance Card

```yaml
id: WP-04B
status: PASSED
depends_on:
  - WP-04A
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.DecisionBatchExpectation
  - crypto_quant_trading.DecisionBatchSubmission
  - crypto_quant_trading.DecisionBatchIssueCode
  - crypto_quant_trading.DecisionBatchIssue
  - crypto_quant_trading.DecisionBatchFailure
  - crypto_quant_trading.LatestSleeveDecisionState
  - crypto_quant_trading.AtomicDecisionBatchResult
  - crypto_quant_trading.AtomicDecisionBatchCollector
test_commands:
  contract: uv run pytest -q tests/kernel/decisions/test_atomic_decision_batch.py
  fixture: uv run pytest -q tests/kernel/decisions/test_atomic_decision_batch_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - atomic-decision-batch-v1
expected_artifacts:
  - tests/fixtures/kernel/atomic-decision-batch-v1.json
  - build/acceptance/wp-04b-pytest.xml
  - build/acceptance/wp-04b-import-boundary-report.json
failure_contracts:
  - empty-or-duplicate-expected-sleeve
  - missing-duplicate-or-unexpected-submission
  - submitted-validation-failure
  - strategy-or-sleeve-identity-mismatch
  - decision-time-mismatch
  - prior-state-from-same-or-future-instant
  - partial-batch-or-partial-state-on-failure
  - registration-or-submission-order-dependent-identity
  - strategy-callback-or-same-batch-output-visibility
  - attempt-id-wall-clock-or-runtime-origin-in-identity
  - allocation-netting-risk-sizing-or-order-planning-leakage
allowed_grade: development
evidence:
  - pytest-report
  - atomic-decision-batch-golden-fixture-hash
  - deterministic-batch-and-state-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 4ac6ed0a23229755e6eaa5b8949828e4dde13982
artifact_hashes:
  tests/fixtures/kernel/atomic-decision-batch-v1.json: sha256:e24e0e52e6a8b4c62b6105e4c09251f4abeac22e0902df60e491f0623009c6a0
  build/acceptance/wp-04b-pytest.xml: sha256:51053d890b4d10aabe6df6a0d3ccea1a0db6a771d4132f83e0b181f1e52174c3
  build/acceptance/wp-04b-import-boundary-report.json: sha256:681980b2645e7194998a6aba208ec577ab8bda647a4d9f71741fd1b1be00c681
```

### WP-04B Acceptance

已冻结以下边界：

1. `DecisionBatchExpectation` 规范化 expected Strategy/Sleeve membership；每个 Sleeve 唯一且 expected 集合非空；
2. `DecisionBatchSubmission` 只包裹 caller 已独立完成的 `StrategyValidationResult`。Collector 不接收 Strategy callback、Observation Context 或逐个可见的 staged Batch，因此不提供 same-Batch output visibility seam；
3. 每个 expected Sleeve 必须有且只有一个 Submission。Missing、duplicate、unexpected、ValidationFailure、Strategy/Sleeve identity mismatch 或 Decision Time mismatch 统一形成稳定排序的 `DecisionBatchIssue`；任一 Issue 时 Result 必须同时 `batch=None`、`state=None`；
4. `decision_batch_id` 由 versioned canonical identity payload（authoritative Decision Time + canonical-sorted Validated Decisions）确定性派生。注册顺序、Submission 顺序、Mapping 顺序、Attempt ID 和 wall-clock time 不参与 identity；
5. `LatestSleeveDecisionState` 保存每个 Sleeve 最近一次 Validated Decision。成功 Batch 原子替换本 Batch Sleeve 并保留不同 Instant 未调度 Sleeve；它不解释 Target expiry、StaleTargetPolicy 或经济有效性；
6. 为禁止同一 Instant 被多次拼成部分 Batch，非空 prior State 的 `as_of` 必须严格早于新 Batch Decision Time；
7. 本 WP 不实现 Candidate validation、Allocation/Netting、Risk、Sizing、ActivePortfolioTarget、Order Planning、Strategy invocation、InputOrigin 或 Run Outcome mapping。

WP-04B 的实现已冻结在 immutable commit `4ac6ed0a23229755e6eaa5b8949828e4dde13982`，状态为 `PASSED`。

验证记录：

```text
Atomic DecisionBatch contract tests                                    8 passed
Atomic DecisionBatch canonical golden fixture                          2 passed
Public API + repository cleanliness boundaries                         5 passed
Acceptance test report                                                15 passed
Trading-kernel import boundary                                         PASS (29 files)
Full test suite                                                       280 passed
mypy                                                                   no issues (14 files)
Primary LSP                                                            clean
pi-lens scoped review                                                  no findings
uv lock --check                                                        PASS
Python                                                                 3.13.5
```

## 31. WP-04C Acceptance Card

```yaml
id: WP-04C
status: PASSED
depends_on:
  - WP-04B
  - G03
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.CapitalAllocationPolicyRef
  - crypto_quant_trading.StrategyAllocation
  - crypto_quant_trading.SleeveTargetNotional
  - crypto_quant_trading.NetInstrumentTarget
  - crypto_quant_trading.PortfolioAllocation
  - crypto_quant_trading.AllocationConstraintCode
  - crypto_quant_trading.AllocationConstraintDecision
  - crypto_quant_trading.CapitalAllocationFailure
  - crypto_quant_trading.PortfolioAllocationOutcome
  - crypto_quant_trading.PortfolioAllocator
test_commands:
  contract: uv run pytest -q tests/kernel/allocation/test_portfolio_allocator.py
  fixture: uv run pytest -q tests/kernel/allocation/test_portfolio_allocator_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - capital-allocation-netting-v1
expected_artifacts:
  - tests/fixtures/kernel/capital-allocation-netting-v1.json
  - build/acceptance/wp-04c-pytest.xml
  - build/acceptance/wp-04c-import-boundary-report.json
failure_contracts:
  - empty-or-unbound-latest-sleeve-state
  - missing-duplicate-or-unexpected-sleeve-allocation
  - strategy-or-sleeve-allocation-identity-mismatch
  - allocation-valuation-time-currency-scale-or-snapshot-mismatch
  - negative-allocation-nav
  - total-allocation-nav-exceeds-portfolio-equity
  - target-not-yet-effective-or-expired
  - target-notional-inexact-at-declared-scale
  - partial-allocation-result-on-constraint-failure
  - lost-sleeve-attribution-or-zero-net-target
  - registration-mapping-or-input-order-dependent-result
  - allocation-policy-callback-or-default-policy
  - price-quantity-risk-active-target-order-or-ledger-leakage
allowed_grade: development
evidence:
  - pytest-report
  - capital-allocation-netting-golden-fixture-hash
  - deterministic-allocation-and-net-target-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: d899198c9762268cd39de602d2baa2b31b433465
artifact_hashes:
  tests/fixtures/kernel/capital-allocation-netting-v1.json: sha256:277c9955cdcf0f30f80d13c3c01f345636e0ae94c677267dfbc43742bde8a542
  build/acceptance/wp-04c-pytest.xml: sha256:b768b49f65c78020ce1919905db50bcc5a635d35377a2a6cccb4cf5ebb1ae5ba
  build/acceptance/wp-04c-import-boundary-report.json: sha256:fc7e436e626b9c53148e480d3fc6a41314ae9352abbfea2c0cf2f52ad78911e7
```

### WP-04C Acceptance

已冻结以下边界：

1. `PortfolioAllocator` 只消费 immutable `LatestSleeveDecisionState`、同一 valuation instant 的权威 `PortfolioSnapshot`、显式版本化 `CapitalAllocationPolicyRef`、每个 active Sleeve 恰好一个 supplied `StrategyAllocation` 和显式 target-notional Scale；没有 Policy callback 或默认 Policy；
2. `StrategyAllocation` 绑定 expected Strategy/Sleeve、valuation time/currency、非负 Allocation NAV 与 source Snapshot hash。缺失、重复、unexpected、identity/time/currency/scale/hash 不一致均返回稳定排序的 `AllocationConstraintDecision`，不能产生部分 Portfolio Allocation；
3. 全部 Allocation NAV 使用 Snapshot reporting Currency/Scale，总量不能超过 Snapshot Equity；负 Equity 不允许隐式正 Allocation，违反约束返回显式 failure；
4. `TargetExposureFraction × Allocation NAV` 使用整数运算 exact 转换到调用方声明的 target-notional Scale；不能整除时 fail closed，不在本 WP rounding；
5. 每个 Instrument 的 account-level target 保存 canonical-sorted Sleeve attribution。相反目标完全抵消时仍保留显式零 `NetInstrumentTarget`，Sleeve attribution 不建立虚拟 Cash、Ledger 或 Equity；
6. State、Allocation tuple、Target 和 Mapping 顺序不影响 allocation identity、result hash 或 net target；
7. 本 WP 不执行 Allocation Policy、读取 Price/Market/Profile，不实现 Quantity sizing、Portfolio Risk、ActivePortfolioTarget、Order Planning、Strategy invocation 或 Ledger mutation。

WP-04C 的实现已冻结在 immutable commit `d899198c9762268cd39de602d2baa2b31b433465`，状态为 `PASSED`。

验证记录：

```text
Portfolio Allocator contract tests                                    8 passed
Capital allocation/netting canonical golden fixture                   2 passed
Public API + repository cleanliness boundaries                        5 passed
Acceptance test report                                               15 passed
Trading-kernel import boundary                                        PASS (30 files)
Full test suite                                                       290 passed
mypy                                                                  no issues (15 files)
Primary LSP                                                           clean
pi-lens scoped review                                                 no findings
uv lock --check                                                       PASS
Python                                                                3.13.5
```

## 32. WP-04D Portfolio Risk Acceptance Card

```yaml
id: WP-04D
status: PASSED
depends_on:
  - WP-04C
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.PortfolioRiskAction
  - crypto_quant_trading.PortfolioRiskScope
  - crypto_quant_trading.PortfolioRiskPolicyRef
  - crypto_quant_trading.PortfolioRiskLimit
  - crypto_quant_trading.PortfolioRiskPolicy
  - crypto_quant_trading.PortfolioRiskReasonCode
  - crypto_quant_trading.PortfolioRiskDecision
  - crypto_quant_trading.ApprovedInstrumentTarget
  - crypto_quant_trading.ApprovedPortfolioTarget
  - crypto_quant_trading.PortfolioRiskContractIssueCode
  - crypto_quant_trading.PortfolioRiskContractIssue
  - crypto_quant_trading.PortfolioRiskContractFailure
  - crypto_quant_trading.PortfolioRiskOutcome
  - crypto_quant_trading.PortfolioRiskEvaluator
test_commands:
  contract: uv run pytest -q tests/kernel/risk/test_portfolio_risk.py
  fixture: uv run pytest -q tests/kernel/risk/test_portfolio_risk_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - portfolio-risk-decisions-v1
expected_artifacts:
  - tests/fixtures/kernel/portfolio-risk-decisions-v1.json
  - build/acceptance/wp-04d-pytest.xml
  - build/acceptance/wp-04d-import-boundary-report.json
failure_contracts:
  - missing-or-implicit-risk-policy
  - policy-identity-config-hash-mismatch
  - policy-valuation-currency-or-scale-mismatch
  - missing-duplicate-or-unexpected-instrument-limit
  - invalid-negative-or-mismatched-limit
  - unsupported-aggregate-clamp
  - target-decision-without-before-after-limit-reason-policy-evidence
  - target-clamp-away-from-zero-or-beyond-limit
  - target-reject-with-nonzero-approved-notional
  - aggregate-gross-or-absolute-net-reject-with-nonzero-final-target
  - economic-reject-misclassified-as-contract-failure
  - lost-sleeve-attribution
  - input-or-policy-rule-order-dependent-result
  - price-quantity-margin-profile-order-or-ledger-leakage
allowed_grade: development
evidence:
  - pytest-report
  - portfolio-risk-canonical-golden-fixture-hash
  - deterministic-approved-target-and-risk-decision-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: a44a636a4d9299bd3a2872508c28790aac5a2178
artifact_hashes:
  tests/fixtures/kernel/portfolio-risk-decisions-v1.json: sha256:08b293a76b662b6a187294b38fdb08dfc26f8f034ba6fed74d73e27395bc6a7f
  build/acceptance/wp-04d-pytest.xml: sha256:30882ecede4dc3530bce872eb4347f5d2ab483e34f2ec218bf0bab5260c5382a
  build/acceptance/wp-04d-import-boundary-report.json: sha256:f1ba308e67848b7fd2805d4a2a781ef843ba6d17a53e15f3d75698b5c6c89593
```

### WP-04D Acceptance

冻结以下边界：

1. `PortfolioRiskEvaluator` 只消费 immutable `PortfolioAllocation` 与显式 `PortfolioRiskPolicy`，不调用 Policy callback，也不提供默认 Policy；
2. Policy 使用版本化 key/version/config hash，并绑定 Allocation valuation Currency/Scale；每个输入 Instrument 必须恰好有一个 target absolute-notional limit，同时显式声明 gross 与 absolute-net aggregate limit；
3. Target limit 未超限时 approve；超限时按规则向零 clamp 到 limit，或 reject 为显式零 approved target；每次 Decision 必须保存 scope/action/before/after/limit/reason/Policy identity；
4. v1 aggregate gross/absolute-net rule 只允许 approve/reject，不支持 proportional clamp；任一 aggregate reject 将 whole target set 显式置零，避免隐式 Instrument 优先级、rounding 或 residual 分配；
5. `ApprovedInstrumentTarget` 保留原 `NetInstrumentTarget` 及完整 Sleeve attribution；Risk 不创建新的虚拟 Sleeve、Cash、Position、Quantity 或 Order；
6. `gross_exposure` 精确等于最终 target absolute-notional 总和，`net_exposure` 精确等于最终 signed target 总和；结果 identity 与 input/rule 顺序无关；
7. Policy coverage/context/schema 错误进入 `PortfolioRiskContractFailure`；合法 economic target 的 clamp/reject 进入成功 `ApprovedPortfolioTarget`，不能伪装为 Strategy Contract violation 或 Run Outcome；
8. 本 WP 不读取 Price/Market/Profile，不实现 Position sizing、Margin requirement、ActivePortfolioTarget、Order、Pre-trade Risk、Ledger mutation 或 Runtime orchestration。

WP-04D 的实现已冻结在 immutable commit `a44a636a4d9299bd3a2872508c28790aac5a2178`，状态为 `PASSED`。

验证记录：

```text
Portfolio Risk contract tests                                         8 passed
Portfolio Risk canonical golden fixture                               2 passed
Public API + repository cleanliness boundaries                        5 passed
Acceptance test report                                                15 passed
Trading-kernel import boundary                                        PASS (31 files)
Full test suite                                                       300 passed
mypy                                                                  no issues (6 files)
Primary LSP                                                           clean
pi-lens scoped review                                                 no blocking findings; 2 local nominal/helper duplicate warnings deferred
uv lock --check                                                       PASS
Python                                                                3.13.5
```

## 33. WP-04E Position Sizing and Active Target Acceptance Card

```yaml
id: WP-04E
status: PASSED
depends_on:
  - WP-04D
  - WP-03C
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.ResidualPositionPolicy
  - crypto_quant_trading.PositionSizingAction
  - crypto_quant_trading.PositionSizingReasonCode
  - crypto_quant_trading.PositionSizingFailureCode
  - crypto_quant_trading.PositionSizingPolicy
  - crypto_quant_trading.QuantityLattice
  - crypto_quant_trading.InstrumentSizingInput
  - crypto_quant_trading.PositionSizingDecision
  - crypto_quant_trading.NormalizedInstrumentTarget
  - crypto_quant_trading.NormalizedPortfolioTarget
  - crypto_quant_trading.PositionSizingFailure
  - crypto_quant_trading.PositionSizingOutcome
  - crypto_quant_trading.PositionSizer
test_commands:
  contract: uv run pytest -q tests/kernel/sizing/test_position_sizing.py
  fixture: uv run pytest -q tests/kernel/sizing/test_position_sizing_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - position-sizing-active-target-v1
expected_artifacts:
  - tests/fixtures/kernel/position-sizing-active-target-v1.json
  - build/acceptance/wp-04e-pytest.xml
  - build/acceptance/wp-04e-import-boundary-report.json
failure_contracts:
  - missing-or-implicit-position-sizing-policy
  - policy-identity-config-hash-mismatch
  - unsupported-non-toward-zero-rounding
  - missing-duplicate-or-unexpected-instrument-sizing-input
  - approved-target-mark-lattice-current-quantity-context-mismatch
  - sizing-mark-not-at-approved-instant-wrong-price-purpose-or-nonpositive-price
  - approved-notional-price-currency-mismatch-or-implicit-fx
  - invalid-lattice-step-lot-minimum-or-config-hash
  - normalized-absolute-notional-exceeds-approved-notional-without-explicit-hold-dust
  - minimum-quantity-or-minimum-notional-without-explicit-decision
  - odd-lot-full-close-without-explicit-capability-and-residual-policy
  - residual-fail-returns-partial-active-target
  - missing-mark-lattice-current-raw-final-or-residual-provenance
  - input-or-lattice-order-dependent-result
  - later-price-nav-or-cash-flow-recomputes-materialized-quantity
  - mark-resolver-profile-reader-risk-order-ledger-or-runtime-leakage
allowed_grade: development
evidence:
  - pytest-report
  - position-sizing-canonical-golden-fixture-hash
  - deterministic-normalized-and-active-target-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: ab99e3ac0990052a5f2c3d1b3ecac7503ae56001
artifact_hashes:
  tests/fixtures/kernel/position-sizing-active-target-v1.json: sha256:d425532da4269b74ce6139a886246bf4b173b8ce59c9c5a38adc36425667897a
  build/acceptance/wp-04e-pytest.xml: sha256:993ef392e923c19d43e426d7a51bdd925fd4969e040c4c18e81d8e2a5fde30ef
  build/acceptance/wp-04e-import-boundary-report.json: sha256:b97c4aec16f8e96314d4886266e8b2ce60600396bb151776ee734596d8742ff4
```

### WP-04E Acceptance

冻结以下边界：

1. Sizer 只消费 immutable Approved Target、权威 source DecisionBatch identity、显式版本化 PositionSizingPolicy，以及每个 Instrument 恰好一个 supplied Mark/Current Quantity/QuantityLattice input；没有默认 Policy/Lattice，也不执行 callback；
2. v1 只允许 `RoundingPolicy.TOWARD_ZERO`；Notional/Price 和 buy/sell lot 量化均使用整数运算，普通量化不能使规范化目标的绝对名义暴露超过已审批值；显式 `hold_dust` 是唯一允许保留既有超目标 odd-lot 的例外，并必须记录 before/after/residual；
3. supplied `ResolvedMark.resolved_at` 必须等于 `ApprovedPortfolioTarget.approved_at`，Mark purpose 必须等于 Policy sizing purpose，Price quote Currency 必须等于 approved Notional Currency；本 WP 不执行 FX；
4. Lattice 绑定 Instrument、key/version/config hash、atomic Scale、step、可选 buy/sell lot、minimum Quantity/Notional 与 odd-lot full-close capability；缺失或不一致 fail closed；
5. toward-zero、lot、minimum、odd-lot 和 residual 处理都形成 canonical Decision。Residual Policy 显式为 `hold_dust | close_if_permitted | fail`；任一 Instrument 无法物化时整个账户级结果失败；
6. `NormalizedPortfolioTarget` 保留 Approved Target、Batch、Mark、Lattice、current/raw/final/residual 与 Policy provenance；domain `ActivePortfolioTarget` 保存 materialized exact Quantity，后续 Mark/NAV/Cash Flow 不能改写它；
7. 不实现 contract multiplier、跨币种换算、Mark/Profile/Data 查询、Risk、Order Planning、Ledger mutation 或 Runtime orchestration；Order Planner 不得第二次 rounding。

WP-04E 的实现已冻结在 immutable commit `ab99e3ac0990052a5f2c3d1b3ecac7503ae56001`，状态为 `PASSED`。

验证记录：

```text
Position Sizing contract tests                                      8 passed
Position Sizing canonical golden fixture                            2 passed
Public API + repository cleanliness boundaries                     5 passed
Acceptance test report                                             15 passed
Trading-kernel import boundary                                     PASS (32 files)
Full test suite                                                    310 passed
mypy                                                               no issues (5 files)
Primary/auxiliary LSP                                              clean
pi-lens scoped review                                              no findings
uv lock --check                                                    PASS
Python                                                             3.13.5
```

## 34. G04 Target Materialization Aggregate Acceptance Card

```yaml
id: G04
status: PASSED
depends_on:
  - WP-04A
  - WP-04B
  - WP-04C
  - WP-04D
  - WP-04E
owner_package: trading-kernel
public_interface:
  - no-new-production-interface
  - existing Validator/Batch/Allocation/Risk/Sizing public seams only
test_commands:
  journey: uv run pytest -q tests/kernel/integration/test_target_materialization_journey.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - target-materialization-journey-v1
expected_artifacts:
  - tests/fixtures/kernel/target-materialization-journey-v1.json
  - build/acceptance/g04-pytest.xml
  - build/acceptance/g04-import-boundary-report.json
failure_contracts:
  - candidate-validation-failure-produces-partial-batch-or-target
  - missing-duplicate-or-unexpected-sleeve-produces-partial-target
  - allocation-or-risk-failure-bypassed-by-sizing
  - sleeve-targets-not-netted-before-risk-and-sizing
  - strategy-registration-candidate-mapping-submission-allocation-rule-or-sizing-input-order-dependent-result
  - approved-notional-to-quantity-materialization-loses-batch-sleeve-policy-mark-or-lattice-provenance
  - later-mark-nav-or-external-cash-flow-mutates-existing-active-target
  - order-created-before-complete-account-level-active-target
allowed_grade: development
evidence:
  - pytest-report
  - target-materialization-journey-golden-fixture-hash
  - exact-active-target-and-stage-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 51789b8d9b355460d051338a37aa94d0f3065324
artifact_hashes:
  tests/fixtures/kernel/target-materialization-journey-v1.json: sha256:91d7c57f828dc06539426726b5a1a7c7ebb5fc81dfd3d802c1b1b58974d222ae
  build/acceptance/g04-pytest.xml: sha256:37f9673d39fd4a953458240b9c74369f25088094900443304bacb71688fb1f18
  build/acceptance/g04-import-boundary-report.json: sha256:b97c4aec16f8e96314d4886266e8b2ce60600396bb151776ee734596d8742ff4
```

### G04 Acceptance

冻结 aggregate journey：

1. 两个独立 Sleeve Candidate 分别通过 `StrategyOutputValidator`，在同一 Decision Instant 原子形成一个 `DecisionBatch` 和 `LatestSleeveDecisionState`；
2. supplied Strategy Allocations 将两个 Sleeve Target 转为 native Notional，并在账户级按 Instrument 净额化；Portfolio Risk 在净额化后产生 Approved Target；
3. Position Sizer 使用同一 Decision Instant 的 supplied Mark/Lattice 将 Approved Notional 一次性物化为一个 account-level exact `ActivePortfolioTarget`；
4. Strategy 注册、Candidate Mapping、Submission、Allocation、Risk rule 和 Sizing Input 顺序变化不改变各阶段 canonical hash、Active Quantity 或最终 aggregate fixture；
5. 任一 Validator/Batch/Allocation/Risk/Sizing failure 都不能产生部分 Active Target，也不能提前创建 Order；
6. 后续 Mark/NAV/External Cash Flow 只能成为未来新 Decision/Reallocation 的输入，不能修改已经物化的 immutable Active Target；
7. 本 Gate 不新增生产 API，也不实现 Rebalance/Order/Execution/Runtime。

G04 aggregate journey 已冻结在 immutable commit `51789b8d9b355460d051338a37aa94d0f3065324`，状态为 `PASSED`。

验证记录：

```text
Two-Sleeve target materialization journey                            4 passed
Public API + repository cleanliness boundaries                       5 passed
Acceptance test report                                               9 passed
Trading-kernel import boundary                                       PASS (32 files)
Full test suite                                                     314 passed
mypy                                                                no issues (14 files)
Primary LSP                                                         clean
pi-lens scoped review                                               no findings
uv lock --check                                                     PASS
Python                                                              3.13.5
```

## 35. WP-05A Order Event Stream/State Projection Acceptance Card

```yaml
id: WP-05A
status: PASSED
depends_on:
  - G02
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.OrderEventRecord
  - crypto_quant_trading.OrderEventStream
  - crypto_quant_trading.CancelReplaceCausation
  - crypto_quant_trading.OrderEventStreamError
  - crypto_quant_trading.OrderEventConflictError
  - crypto_quant_trading.OrderEventOrderingError
  - crypto_quant_trading.OrderTransitionError
  - crypto_quant_trading.OrderFillError
test_commands:
  contract: uv run pytest -q tests/kernel/orders/test_order_event_stream.py
  fixture: uv run pytest -q tests/kernel/orders/test_order_event_stream_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - order-event-state-replay-v1
expected_artifacts:
  - tests/fixtures/kernel/order-event-state-replay-v1.json
  - build/acceptance/wp-05a-pytest.xml
  - build/acceptance/wp-05a-import-boundary-report.json
failure_contracts:
  - first-event-is-not-order-intent-created
  - event-order-id-or-created-context-mismatch
  - invalid-gate-or-lifecycle-transition
  - terminal-state-regression
  - late-event-insertion-before-published-prefix
  - identical-event-id-with-conflicting-content
  - duplicate-fill-identity
  - missing-extra-or-mismatched-fill-fact
  - fill-quantity-identity-scale-or-side-mismatch
  - cumulative-fill-exceeds-order-quantity
  - partial-fill-completes-order-or-final-fill-leaves-remainder
  - unknown-or-forward-causation
  - in-place-order-modification
  - invalid-cancel-replace-causation
  - input-order-dependent-replay
allowed_grade: development
evidence:
  - pytest-report
  - order-event-state-replay-golden-fixture-hash
  - deterministic-stream-and-state-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 47f9d279ae3eec6b099862ea15e6a9b5b232d4c6
artifact_hashes:
  tests/fixtures/kernel/order-event-state-replay-v1.json: sha256:59ccdb91e6ffd6fd23a40ceb230eab36f8cca13b737738c692f924558ea0a247
  build/acceptance/wp-05a-pytest.xml: sha256:f74d0e59306957495208d3764406f0eee6d7b2fa5735732f9cace2ade38d5760
  build/acceptance/wp-05a-import-boundary-report.json: sha256:60f733f85fa55eadb0a1013f49b321bfd6589a1917704fed1100d431ba563cb6
```

### WP-05A Acceptance

冻结以下边界：

1. `OrderEventStream` 是单一 `Order` 的 immutable authoritative lifecycle evidence；每个 `OrderEventRecord` 恰好包含一个 Event，并且 Fill Event 恰好携带与 `fill_id` 一致的 immutable `Fill` fact，非 Fill Event 不得携带 Fill；
2. Stream stable order 为 `(occurred_at, event_id)`。相同 Event ID + 相同 record canonical hash 是幂等 no-op；相同 ID + 不同内容结构化冲突；已发布 prefix 之前的 late insertion 被拒绝；
3. 第一条 Event 必须是与 `Order.created_at`/`Order.order_id` 对齐的 `OrderIntentCreated`；其 `causation_id` 是可审计的外部 root cause，而 `OrderIntent.parent_id` 继续保留 source Decision/Target identity，两者不得被隐式等同。门控顺序固定为 Capability → Translation → Market Rule → Fee Reservation → Pre-trade Risk → Submission；拒绝事件进入终态且不能回退；
4. Submission 后支持 Submitted → Accepted → Active，以及 Accepted/Active → PartiallyFilled → Filled；CancelRequested 可来自 Working 状态，Cancellation/Expiry/Fill race 必须通过显式 Event 记录，终态之后不得追加新事实；
5. Fill context 必须与 Order 的 ID、Account、Instrument、Side、Quantity identity/Scale 一致，Fill execution time 必须等于 Event instant；Partial Fill 必须保留正 remaining Quantity，Final Fill 必须 exact 清零，不允许 overfill；
6. `OrderState` 只能由完整 Stream replay 得到。无序初始输入 canonical 排序后必须得到相同 Stream/State hash；prefix `state_at()` 与完整 replay 的同一 prefix exact parity；
7. 每条后续 Event 的 `causation_id` 必须引用同一 Stream 中已经发生的 Event。`CancelReplaceCausation` 只接受已显式 CancelRequested→Cancelled 的旧 Order，以及首个 Created Event 由旧 Cancelled Event 直接导致的新 Order；不支持原地修改；
8. 本 WP 不实现 Reservation、Settlement/Availability、Rebalance、Capability/Translation/MarketRule/PreTradeRisk 行为、Execution simulation、Fee/Accounting、Ledger mutation 或 Runtime orchestration。

WP-05A 的实现已冻结在 immutable commit `47f9d279ae3eec6b099862ea15e6a9b5b232d4c6`，状态为 `PASSED`。

验证记录：

```text
Order Event Stream contract tests                                  8 passed
Order Event replay canonical golden fixture                        1 passed
Public API + repository cleanliness boundaries                     5 passed
Acceptance test report                                            14 passed
Trading-kernel import boundary                                     PASS (33 files)
Full test suite                                                   323 passed
mypy                                                               no issues (5 files)
Primary LSP                                                        clean
pi-lens scoped review                                              no findings
uv lock --check                                                    PASS
Python                                                             3.13.5
```

## 36. WP-05B ResourceReservationBook Acceptance Card

```yaml
id: WP-05B
status: PASSED
depends_on:
  - WP-05A
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.ReservationCommitment
  - crypto_quant_trading.OrderReservationUpdate
  - crypto_quant_trading.OrderReservationSchedule
  - crypto_quant_trading.ActiveOrderReservation
  - crypto_quant_trading.OrderReservationCursor
  - crypto_quant_trading.ResourceReservationState
  - crypto_quant_trading.ResourceReservationBook
  - crypto_quant_trading.ResourceReservationError
  - crypto_quant_trading.ReservationEvidenceError
  - crypto_quant_trading.ReservationStateMismatchError
test_commands:
  contract: uv run pytest -q tests/kernel/reservations/test_resource_reservation_book.py
  fixture: uv run pytest -q tests/kernel/reservations/test_resource_reservation_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - resource-reservation-replay-v1
expected_artifacts:
  - tests/fixtures/kernel/resource-reservation-replay-v1.json
  - build/acceptance/wp-05b-pytest.xml
  - build/acceptance/wp-05b-import-boundary-report.json
failure_contracts:
  - empty-or-negative-resource-entry
  - duplicate-resource-dimension
  - account-order-or-quantity-context-mismatch
  - missing-duplicate-or-extra-order-schedule
  - missing-or-multiple-activation-update
  - activation-update-not-bound-to-accepted-or-activated-event
  - missing-duplicate-or-extra-partial-fill-update
  - update-remaining-quantity-mismatch
  - partial-update-increases-or-introduces-resource-dimension
  - update-source-evidence-hash-invalid
  - terminal-order-reservation-leak
  - reservation-evidence-used-as-journal-settlement-or-availability
  - forged-prefix-cursor-or-prior-state
  - input-order-dependent-reservation-state
allowed_grade: development
evidence:
  - pytest-report
  - resource-reservation-replay-golden-fixture-hash
  - deterministic-prefix-resume-and-state-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: e3db8e565b82b43e516cea2294e5f35a98280ef9
artifact_hashes:
  tests/fixtures/kernel/resource-reservation-replay-v1.json: sha256:6b0c92b211c6d7501c1848df6d5d88181b1d722fff7a1df938bfceeee068e56a
  build/acceptance/wp-05b-pytest.xml: sha256:dfad7f3863c842c98b3a91ba16d2c29d28794682f04193efa03e6d75e7d41f44
  build/acceptance/wp-05b-import-boundary-report.json: sha256:a5c565f3897dfab03f3784086a97bdeeb760c0e2c1eceba5357c0d64402860e7
```

### WP-05B Acceptance

冻结以下边界：

1. `ReservationCommitment` 分别保存 positive Cash、Sellable Quantity、Margin、Fee Reserve、Order Capacity 和 Exposure Capacity；零值通过省略表达，类别之间不隐式净额化、换算或共享 identity；
2. `OrderReservationSchedule` 是调用方提供的 immutable evidence，不是 Book 计算结果。它绑定一个 Order、一个 canonical source proposal hash、恰好一个 `OrderAccepted` 或 `OrderActivated` activation update，以及该 Order 每个 Partial Fill 的 exact replacement update；
3. 每个 update 的 remaining Quantity 必须与对应 Event replay 后的 `OrderState.remaining_quantity` exact identity/Scale/units 一致。Partial update 不得增加已有资源单位或引入新资源维度；固定 Order Capacity/Fee 类承诺可以保持不变；
4. Activation 只发生一次。后续 Accepted/Activated Event 不重复冻结；Cancel、Reject、Expire 或 Final Fill 进入终态时无条件释放该 Order 全部 remaining commitment；
5. `ResourceReservationBook` 只接受同一显式 Execution Account 的 `OrderEventStream`，保留逐 Order active reservation，并产生按 Currency/Instrument 分类的 account-level exact totals。Stream、Schedule 和资源 tuple 输入顺序不改变 canonical state hash；
6. 相同 Event 由 `OrderEventStream` 幂等去重，因此重复 replay 不重复冻结。Book 的 prefix resume 必须从 supplied Stream prefix 独立重建 prior state 并验证 cursor/state hash；伪造或陈旧 state fail closed；
7. Reservation 不进入 Accounting Journal，不表示 Settlement Obligation 或 Availability，不读取 Market/Account Profile，也不自行推导 worst-case commitment。具体 proposal 由后续 Market Rule、Fee Reservation 和 Account semantics 组合提供；
8. 本 WP 不实现 Settlement/Availability、Rebalance、Capability/Translation/MarketRule/PreTradeRisk 行为、Fee Assessment、Accounting、Ledger mutation 或 Runtime orchestration。

WP-05B 的实现已冻结在 immutable commit `e3db8e565b82b43e516cea2294e5f35a98280ef9`，状态为 `PASSED`。

验证记录：

```text
Resource Reservation contract tests                               10 passed
Resource Reservation canonical golden fixture                      1 passed
Public API + repository cleanliness boundaries                     5 passed
Acceptance test report                                            16 passed
Trading-kernel import boundary                                     PASS (34 files)
Full test suite                                                   334 passed
mypy                                                               no issues (5 files)
Primary LSP                                                        clean
pi-lens scoped review                                              no findings
uv lock --check                                                    PASS
Python                                                             3.13.5
```

## 37. WP-05C SettlementBook/AvailabilityProjection Acceptance Card

```yaml
id: WP-05C
status: PASSED
depends_on:
  - WP-03B
  - WP-05B
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.SettlementEventType
  - crypto_quant_trading.AccountSettlementObligation
  - crypto_quant_trading.SettlementEvent
  - crypto_quant_trading.SettlementBookCursor
  - crypto_quant_trading.SettlementBookState
  - crypto_quant_trading.SettlementBook
  - crypto_quant_trading.CashReservationUse
  - crypto_quant_trading.CashAvailabilityRule
  - crypto_quant_trading.PositionAvailabilityRule
  - crypto_quant_trading.MarketSettlementRules
  - crypto_quant_trading.CashAvailability
  - crypto_quant_trading.PositionAvailability
  - crypto_quant_trading.AvailabilityState
  - crypto_quant_trading.AvailabilityProjection
  - crypto_quant_trading.SettlementBookError
  - crypto_quant_trading.SettlementEventConflictError
  - crypto_quant_trading.SettlementLifecycleError
  - crypto_quant_trading.SettlementStateMismatchError
  - crypto_quant_trading.AvailabilityProjectionError
  - crypto_quant_trading.AvailabilityEvidenceError
test_commands:
  contract: uv run pytest -q tests/kernel/settlement/test_settlement_availability.py
  fixture: uv run pytest -q tests/kernel/settlement/test_settlement_availability_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - settlement-availability-replay-v1
expected_artifacts:
  - tests/fixtures/kernel/settlement-availability-replay-v1.json
  - build/acceptance/wp-05c-pytest.xml
  - build/acceptance/wp-05c-import-boundary-report.json
failure_contracts:
  - obligation-account-venue-or-balance-key-mismatch
  - missing-or-invalid-recorded-event
  - settlement-applied-before-contractual-settlement-time
  - duplicate-settlement-application
  - identical-event-id-with-conflicting-content
  - late-event-insertion-before-published-prefix
  - unknown-or-forward-settlement-causation
  - forged-prefix-cursor-or-prior-state
  - input-order-dependent-settlement-state
  - ledger-settlement-reservation-account-mismatch
  - missing-duplicate-or-extra-balance-rule
  - pending-obligation-balance-key-unregistered
  - reservation-currency-without-unique-cash-rule-owner
  - availability-identity-or-scale-mismatch
  - implicit-market-rule-default
allowed_grade: development
evidence:
  - pytest-report
  - settlement-availability-replay-golden-fixture-hash
  - deterministic-prefix-resume-and-state-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 46a8b3cb05ce35220a08f53b31388f1f3878bf37
artifact_hashes:
  tests/fixtures/kernel/settlement-availability-replay-v1.json: sha256:37ec8f992013d3380871458105bb822df9d82d8eec4467314675f8bd4a024e31
  build/acceptance/wp-05c-pytest.xml: sha256:83cd0ce30268bde0347797e915af85ab5efd97a8e556c7477773f95b5cf9d673
  build/acceptance/wp-05c-import-boundary-report.json: sha256:5844fa0a0b55fd56d1b509209b8f75e92642e7a2b3586066bc1182f3fd3c7154
```

### WP-05C Acceptance

冻结以下边界：

1. `AccountSettlementObligation` 只把既有 immutable `SettlementObligation` 显式绑定到一个 `CashBalanceKey` 或 `PositionBalanceKey`；该 wrapper 补足 Account/Venue projection context，不改变 Domain obligation，也不计算义务；
2. 每个 Obligation 必须先有发生于 `trade_time` 的 `SettlementObligationRecorded` Event，随后至多有一个发生于或晚于 `settlement_time` 的 `SettlementApplied` Event。Event 使用稳定 ID、Obligation ID、Causation ID 和 `SimulationInstant`；Applied 必须直接因果引用 Recorded；
3. `SettlementBook` 是 immutable append/replay value。Event stable order 为 `(occurred_at, event_id)`；identical Event 重放幂等，相同 Event ID 不同内容、第二个 Applied Event、已发布 prefix 前 late insertion、未知/前向 causation 均 fail closed；
4. `SettlementBookState` 明确分离 pending 和 applied Obligation，并保存可验证 prefix cursor/hash。`resume()` 必须独立重建并验证 prior prefix，full replay 与 prefix resume 得到 exact 相同 state hash；
5. Fill 的经济 Cash/Position 已经进入 `LedgerState`。Availability 只对仍 pending 的 positive receivable leg 限制可用性；negative delivery leg 不二次扣减已经立即反映在 Ledger 的经济余额；
6. `MarketSettlementRules` 是调用方提供的 immutable、版本化规则证据，并对 Ledger 中每个 Cash/Position balance key exact 覆盖。Cash rule 分别声明 pending receivable 是否可 tradable/withdrawable/margin-eligible，以及 Cash/Margin/Fee Reserve 哪些类别扣减各可用维度；Position rule 显式声明 pending receivable 是否 sellable；禁止 implicit stablecoin、T+0、T+1 或 no-op default；
7. `AvailabilityProjection` 产生 Total Position、Sellable Quantity、Total Cash、Settled Cash、Tradable Cash、Withdrawable Cash 和 Available Margin。Sellable Quantity 还扣除同 Instrument 的 Reservation；Cash Reservation 必须由规则显式且唯一映射到一个相同 Currency 的 Cash key，类别之间不隐式净额化或换算；
8. Projection 必须保留 Ledger state hash、Settlement state hash、Reservation state hash 和 Market Settlement Rules hash。输入顺序、full replay/rebuild 不改变 Availability state hash；Pre-trade Risk 后续只消费该 typed Available Resources；
9. 本 WP 不实现市场特定 T+1/Crypto 规则、Profile 读取、SettlementModel 义务计算、Accounting translation、Journal 写入、Order Planning、Pre-trade Risk 行为、mutable persistence 或 Runtime orchestration。

WP-05C 的实现已冻结在 immutable commit `46a8b3cb05ce35220a08f53b31388f1f3878bf37`，状态为 `PASSED`。

验证记录：

```text
Settlement/Availability contract tests                             9 passed
Settlement/Availability canonical golden fixture                  1 passed
Public API + repository cleanliness boundaries                    5 passed
Acceptance test report                                           15 passed
Trading-kernel import boundary                                    PASS (35 files)
Full test suite                                                  344 passed
mypy                                                              no issues (20 files)
Primary LSP                                                       clean
pi-lens full scoped review                                        no findings
uv lock --check                                                   PASS
Python                                                            3.13.5
```

## 38. WP-05D RebalanceCoordinator Acceptance Card

```yaml
id: WP-05D
status: PASSED
depends_on:
  - G04
  - WP-05A
  - WP-05B
  - WP-05C
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.RebalancePolicy
  - crypto_quant_trading.TargetValidity
  - crypto_quant_trading.PlannedOrder
  - crypto_quant_trading.CancelIntent
  - crypto_quant_trading.PlanningOmissionCode
  - crypto_quant_trading.PlanningOmission
  - crypto_quant_trading.OrderPlan
  - crypto_quant_trading.RebalanceDecision
  - crypto_quant_trading.RebalanceFailureCode
  - crypto_quant_trading.RebalanceFailure
  - crypto_quant_trading.RebalanceOutcome
  - crypto_quant_trading.RebalanceCoordinator
test_commands:
  contract: uv run pytest -q tests/kernel/rebalance/test_rebalance_coordinator.py
  fixture: uv run pytest -q tests/kernel/rebalance/test_rebalance_coordinator_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - rebalance-coordination-v1
expected_artifacts:
  - tests/fixtures/kernel/rebalance-coordination-v1.json
  - build/acceptance/wp-05d-pytest.xml
  - build/acceptance/wp-05d-import-boundary-report.json
failure_contracts:
  - missing-rebalance-policy
  - target-validity-identity-or-time-mismatch
  - target-snapshot-reservation-or-availability-context-mismatch
  - duplicate-or-terminal-working-order
  - working-order-instrument-or-quantity-scale-mismatch
  - reservation-or-availability-evidence-hash-mismatch
  - stale-or-forged-prior-plan-context
  - duplicate-working-coverage-on-repeated-tick
  - replacement-created-before-conflicting-cancel-completes
  - sign-reversal-opens-before-current-position-closes
  - input-order-dependent-plan-identity
allowed_grade: development
evidence:
  - pytest-report
  - rebalance-coordination-golden-fixture-hash
  - deterministic-plan-and-decision-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: aa998012fffc0c92925f285a636144735f1b2692
artifact_hashes:
  tests/fixtures/kernel/rebalance-coordination-v1.json: sha256:b463238c2aa830f1de0386a825e47fc523fe21f2dca7d0374e5e7cbf23c1c7c1
  build/acceptance/wp-05d-pytest.xml: sha256:03d09ea183aba05e6374074d5923faffc51ab815ee4df85109e90f4310d9b52c
  build/acceptance/wp-05d-import-boundary-report.json: sha256:10eed38c7e6476142efcfe038a92afb85d5a96fb45886459b7201621a3c91bb8
```

### WP-05D Acceptance

冻结以下边界：

1. `RebalanceCoordinator` 只消费 immutable `NormalizedPortfolioTarget`、显式 `TargetValidity`、当前 `PortfolioSnapshot`、非终态 `OrderEventStream`、`ResourceReservationState`、`AvailabilityState` 和显式版本化 `RebalancePolicy`；它不读取 Profile、Market Data、Journal 或外部状态；
2. `TargetValidity` 绑定唯一 normalized Target，并独立保存 `valid_from`/`valid_until`。`OrderPlan.valid_until` 由 RebalancePolicy 决定，Planned `OrderIntent.time_in_force` 也是独立证据；三者不得互相替代；
3. Working Order coverage 使用 `OrderState.remaining_quantity` 和 Order side。相同 evidence 且 prior Plan 仍有效时返回相同 Plan；已有 Planned/Working coverage 不得在重复 tick 中产生重复新 Quantity；
4. 每个 Instrument 使用 exact `target - current - retained working coverage`。Partial Fill 的 remaining Quantity 继续覆盖目标；Order terminal 后由新的 Position Snapshot 决定 exact remainder。Coordinator 不执行 Quantity rounding；
5. 新 Target 下方向相反或超过当前阶段 delta 的 Working Order 必须产生 canonical `CancelIntent`。同一 Instrument 在 conflict cancellation 完成前不得同时产生 replacement PlannedOrder；
6. Long→Short 或 Short→Long 必须 close-before-open：当前阶段至多规划到零。只有 close Fill 已反映到新的 PortfolioSnapshot 后，后续 tick 才能规划 opposite opening Quantity；
7. Plan identity 绑定 Target、PortfolioSnapshot、Working Order set、Reservation、Availability、Policy 和 planning time。任一前提变化使 prior Plan 显式 superseded；Plan supersession 不让已提交 Order 消失，也不删除仍有效 Target；
8. `RebalancePolicy` 显式提供 execution style、Venue TIF、urgency 和 Plan validity；没有默认 Policy。OrderIntent 的 reduce-only/position-effect 由 current→target 阶段显式记录，后续 Capability/Translation/MarketRule 才判断支持性；
9. Target/Position/Working Order/Reservation/Availability 的 account、Instrument、Quantity Scale、time/hash context 必须一致。重复 Order、终态 Order 作为 Working 输入、伪造 prior Plan 或 evidence mismatch 返回结构化 `RebalanceFailure`，不产生部分 Plan；
10. 本 WP 不实现 Capability Validation、Translation、Market Rules、Fee Reservation、Pre-trade Risk、Execution Simulation、Fee/Accounting、Ledger/Reservation/Settlement mutation、Profile/Market data 读取或 Runtime orchestration。

WP-05D 的实现已冻结在 immutable commit `aa998012fffc0c92925f285a636144735f1b2692`，状态为 `PASSED`。

验证记录：

```text
Rebalance Coordinator contract tests                              8 passed
Rebalance Coordinator canonical golden fixture                    1 passed
Public API + repository cleanliness boundaries                    5 passed
Acceptance test report                                           14 passed
Trading-kernel import boundary                                    PASS (36 files)
Full test suite                                                  353 passed
mypy                                                              no issues (6 files)
Primary LSP                                                       clean
pi-lens full scoped review                                        no blocking findings
uv lock --check                                                   PASS
Python                                                            3.13.5
```

三个小型 contract-local validation duplicate warnings 已在本 session defer；当前不抽取共享 abstraction，以免在 Rebalance/Allocation/Mark Policy 尚未稳定时扩大耦合。

## 39. WP-05E OrderCapabilityValidator Acceptance Card

```yaml
id: WP-05E
status: PASSED
depends_on:
  - WP-05D
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.OrderCapabilityKey
  - crypto_quant_trading.PriceConstraintShape
  - crypto_quant_trading.OrderStyleCapability
  - crypto_quant_trading.OrderCapabilitySet
  - crypto_quant_trading.OrderCapabilityApproval
  - crypto_quant_trading.CapabilityRejection
  - crypto_quant_trading.OrderCapabilityDecision
  - crypto_quant_trading.OrderCapabilityValidator
test_commands:
  contract: uv run pytest -q tests/kernel/capabilities/test_order_capability_validator.py
  fixture: uv run pytest -q tests/kernel/capabilities/test_order_capability_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - order-capability-validation-v1
expected_artifacts:
  - tests/fixtures/kernel/order-capability-validation-v1.json
  - build/acceptance/wp-05e-pytest.xml
  - build/acceptance/wp-05e-import-boundary-report.json
failure_contracts:
  - missing-declared-capability-dimension
  - unknown-declared-capability-key
  - unsupported-execution-style
  - unsupported-price-constraint-shape
  - unsupported-time-in-force-for-style
  - unsupported-reduce-only
  - unsupported-position-effect
  - duplicate-style-capability-or-config-hash-mismatch
  - intent-or-capability-input-order-dependent-decision
  - intent-mutation-or-silent-semantic-downgrade
  - translation-market-rule-account-risk-rounding-profile-or-runtime-leakage
allowed_grade: development
evidence:
  - pytest-report
  - order-capability-canonical-golden-fixture-hash
  - deterministic-intent-capability-and-decision-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 7230fbd75ed73c42ea663b9e500ff8d8f4b32b02
artifact_hashes:
  tests/fixtures/kernel/order-capability-validation-v1.json: sha256:78e15472aa2469f675d302ee1a89883ed2d75852c1be7c111c6d750038b08a22
  build/acceptance/wp-05e-pytest.xml: sha256:95a59c78f42984946ae11b0492276cd2ed3eca19976c5e2164d5d764c583782b
  build/acceptance/wp-05e-import-boundary-report.json: sha256:57f48c3ec8e5dab13ec3fe2651a3b34b1701dd7d9b4c3e2f00e8482cd9316ee8
```

### WP-05E Acceptance

冻结以下边界：

1. `OrderCapabilityValidator` 只消费 immutable canonical `OrderIntent` 与显式版本化 `OrderCapabilitySet`；Capability Set 使用 key/version/config hash，Validator 没有默认 Set、Profile Resolver 或 callback；
2. `OrderCapabilitySet` 以 `OrderStyleCapability` 显式声明每个 `ExecutionStyle` 允许的 `PriceConstraintShape` 与 `TimeInForce`，并独立声明 reduce-only 和 `PositionEffect` 支持；Validator 不把跨字段组合退化为全局 capability 并集；
3. Capability Set 必须通过 canonical `declared_capability_keys` 显式覆盖 execution style、price constraint、TIF、reduce-only 和 position effect 五个维度。缺失或未知 key 均返回结构化 rejection，禁止忽略未知维度；
4. `None`、limit-only、trigger-only 和 limit+trigger 映射为不同 `PriceConstraintShape`。Validator 只判断 exact shape 支持，不调整 Price、Quantity 或 Constraint；
5. unsupported execution style、style-specific Price Constraint、style-specific TIF、requested reduce-only 或 position effect 汇总为 canonical-sorted `UnsupportedCapability` evidence；任一问题都不产生 Approval；
6. Approval/Rejection 均保存原始 Intent、Capability Set、各自 canonical hash 和稳定 Decision ID；输入 tuple 顺序变化不改变 Capability Set 或 Decision identity；
7. Validator 返回的新对象不得修改或替换 Intent 字段，不允许 Market→Limit、TIF、reduce-only、position-effect 或其他语义降级；
8. 本 WP 不实现 Order Translation、ExecutableOrderSpec、Market Rules、Fee Reservation、Pre-trade Risk、quantity/price rounding、Profile resolution、Venue DTO、Submission 或 Runtime orchestration。

WP-05E 的实现已冻结在 immutable commit `7230fbd75ed73c42ea663b9e500ff8d8f4b32b02`，状态为 `PASSED`。

验证记录：

```text
Order Capability Validator contract tests                          9 passed
Order Capability canonical golden fixture                          1 passed
Public API + repository cleanliness boundaries                     5 passed
Acceptance test report                                            15 passed
Trading-kernel import boundary                                     PASS (37 files)
Full test suite                                                   363 passed
mypy                                                               no issues (22 files)
Primary LSP                                                        clean
pi-lens scoped review                                              no findings after 2 signature-shape false positives
uv lock --check                                                    PASS
Python                                                             3.13.5
```

## 40. WP-05F OrderTranslator Acceptance Card

```yaml
id: WP-05F
status: PASSED
depends_on:
  - WP-05E
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.OrderTranslationFieldRule
  - crypto_quant_trading.OrderTranslationMapping
  - crypto_quant_trading.ExecutableOrderSpec
  - crypto_quant_trading.OrderTranslationResult
  - crypto_quant_trading.OrderTranslationError
  - crypto_quant_trading.OrderTranslationEvidenceError
  - crypto_quant_trading.OrderTranslator
test_commands:
  contract: uv run pytest -q tests/kernel/translation/test_order_translator.py
  fixture: uv run pytest -q tests/kernel/translation/test_order_translator_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - order-translation-v1
expected_artifacts:
  - tests/fixtures/kernel/order-translation-v1.json
  - build/acceptance/wp-05f-pytest.xml
  - build/acceptance/wp-05f-import-boundary-report.json
failure_contracts:
  - capability-approval-intent-mismatch
  - translation-before-order-creation
  - forged-translation-config-hash
  - missing-canonical-field-mapping
  - unknown-canonical-field-mapping
  - duplicate-canonical-or-target-field-mapping
  - source-intent-field-mutation-or-silent-semantic-downgrade
  - executable-spec-venue-dto-or-arbitrary-extension
  - market-rule-rounding-risk-submission-or-runtime-leakage
allowed_grade: development
evidence:
  - pytest-report
  - order-translation-canonical-golden-fixture-hash
  - deterministic-spec-report-mapping-and-result-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 053d2490303d539935e4ef22ae2fac77eb099060
artifact_hashes:
  tests/fixtures/kernel/order-translation-v1.json: sha256:94a4aee0c3d593ac812debb87f47884ba004aec0dc2b98970e595b0e41b903b5
  build/acceptance/wp-05f-pytest.xml: sha256:450ff7d6e7a7b83fe7fea46e917fcce59333ffc852838145389fc4b5fda15073
  build/acceptance/wp-05f-import-boundary-report.json: sha256:04f58c902d15add4154acd7e085f85e878edad75a843f28fab2f4f1d2e0b0992
```

### WP-05F Acceptance

冻结以下边界：

1. `OrderTranslator` 只消费 immutable `Order`、同一 source `OrderIntent` 的 `OrderCapabilityApproval`、显式版本化 `OrderTranslationMapping` 和权威 `translation_time`；没有默认 Mapping、Profile Resolver、callback 或外部状态读取；
2. canonical Intent 字段集合固定为 `instrument_id`、`side`、`quantity`、`execution_style`、`price_constraint`、`time_in_force`、`reduce_only`、`position_effect`、`urgency`、`reason`、`parent_id`。Mapping 必须为每个字段提供唯一 target field；missing/unknown 字段产生结构化 rejected `OrderTranslationReport`，不产生部分 `ExecutableOrderSpec`；
3. `OrderTranslationFieldRule` 只重命名 target field。`ExecutableOrderSpec` 继续保存原始 typed canonical 语义；它不允许 value rewrite，因此不能把 Market→Limit、TIF、reduce-only、position-effect、Price 或 Quantity 静默降级；
4. `OrderTranslationMapping` 使用 canonical key、正整数 version、target Profile identity、canonical-sorted field rules 和 config hash；规则输入顺序不改变 Mapping、Spec、Report 或 Result identity；
5. translated Report 为全部字段生成 `TranslationFieldMapping`，canonical/target value 都来自同一个原始 typed field 的 canonical bytes；rejected Report 保留所有可解析 mapping，并使用 canonical-sorted `UnsupportedCapability` 记录每个 missing/unknown 字段；
6. `ExecutableOrderSpec` 是 venue-neutral resolved execution contract：保存 source Order/Intent、Capability approval、Translator/Profile identity、完整 field mappings 和 translation time，不包含 Hummingbot/Broker/Vendor DTO、任意 extensions/metadata 或提交命令；
7. source Intent、Capability Decision 和 Mapping/config hashes 全部进入 Spec/Result identity；Capability approval Intent mismatch、伪造 config hash 或早于 Order creation 的 translation time fail closed；
8. 本 WP 不实现 MarketRule、Price/Quantity rounding、Fee Reservation、Pre-trade Risk、Venue submission、Execution Simulation、Accounting 或 Runtime orchestration。

WP-05F 的实现已冻结在 immutable commit `053d2490303d539935e4ef22ae2fac77eb099060`，状态为 `PASSED`。

验证记录：

```text
Order Translator contract tests                                      8 passed
Order Translation canonical golden fixture                           1 passed
Public API + repository cleanliness boundaries                        5 passed
Acceptance test report                                                14 passed
Trading-kernel import boundary                                        PASS (38 files)
Full test suite                                                       372 passed
mypy                                                                   no issues (38 files)
Primary LSP                                                            clean
pi-lens scoped review                                                  no findings after one local helper duplicate defer
uv lock --check                                                        PASS
Python                                                                 3.13.5
```

一个小型 module-local canonical text validation helper 与 Rebalance 模块形状相同，已在本 session defer；当前不抽取跨模块共享 abstraction，以免为了 11 行验证代码扩大不稳定 contract 之间的耦合。

## 41. WP-05G MarketRuleEvaluator Acceptance Card

```yaml
id: WP-05G
status: PASSED
depends_on:
  - WP-05F
  - WP-02F
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.MarketSessionState
  - crypto_quant_trading.NotionalPriceBasis
  - crypto_quant_trading.OrderRuleNotionalEvidence
  - crypto_quant_trading.SupplementalOrderRuleDecision
  - crypto_quant_trading.OrderRuleSnapshot
  - crypto_quant_trading.OrderRuleInterval
  - crypto_quant_trading.OrderRuleTimeline
  - crypto_quant_trading.OrderRuleEvaluationInput
  - crypto_quant_trading.MarketRuleIssueCode
  - crypto_quant_trading.MarketRuleIssue
  - crypto_quant_trading.MarketRuleApproval
  - crypto_quant_trading.MarketRuleRejection
  - crypto_quant_trading.MarketRuleDataIntegrityCode
  - crypto_quant_trading.MarketRuleDataIntegrityFailure
  - crypto_quant_trading.MarketRuleDecision
  - crypto_quant_trading.MarketRuleEvaluator
test_commands:
  contract: uv run pytest -q tests/kernel/market_rules/test_market_rule_evaluator.py
  fixture: uv run pytest -q tests/kernel/market_rules/test_market_rule_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - point-in-time-market-rule-evaluation-v1
expected_artifacts:
  - tests/fixtures/kernel/point-in-time-market-rule-evaluation-v1.json
  - build/acceptance/wp-05g-pytest.xml
  - build/acceptance/wp-05g-import-boundary-report.json
failure_contracts:
  - missing-effective-rule-interval
  - overlapping-effective-rule-intervals
  - current-rule-fallback
  - forged-rule-snapshot-or-timeline-hash
  - executable-spec-or-instrument-context-mismatch
  - evaluation-before-translation
  - quantity-scale-step-or-minimum-violation
  - missing-or-invalid-notional-price-evidence
  - minimum-notional-violation
  - price-scale-tick-or-limit-violation
  - closed-session-or-order-permission-violation
  - rejected-supplemental-order-rule-decision
  - order-rule-input-order-dependent-decision
  - order-mutation-or-rule-rounding
  - concrete-market-profile-fee-risk-execution-accounting-or-runtime-leakage
allowed_grade: development
evidence:
  - pytest-report
  - point-in-time-market-rule-canonical-golden-fixture-hash
  - deterministic-timeline-snapshot-interval-and-decision-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 63bbec453a8d3ed36a63731f452eac6018abb7b5
artifact_hashes:
  tests/fixtures/kernel/point-in-time-market-rule-evaluation-v1.json: sha256:3f6a72aa3f61a17dede39d4cd0e0c330074467a6291ef5bc75d177ec82df1f80
  build/acceptance/wp-05g-pytest.xml: sha256:a19ea985c11655c79ac76cc6536ab540b35be370ce9f533dc7a62da7d6689597
  build/acceptance/wp-05g-import-boundary-report.json: sha256:26e822f14f2bf2a7124831c838808fbb9e17e04864362c8e99ccf6ffccf377eb
```

### WP-05G Acceptance

冻结以下边界：

1. `MarketRuleEvaluator` 只消费 immutable `ExecutableOrderSpec`、显式 `OrderRuleTimeline` 和 `OrderRuleEvaluationInput`；不调用 `OrderRuleModel`、Profile Resolver、Reader、网络或当前规则服务；
2. `OrderRuleTimeline` 使用 key/version/config hash，并保存同一 Instrument 的 `OrderRuleInterval`。每个 Interval 使用半开 `[effective_from, effective_to_exclusive)`，保存 `OrderRuleSnapshot`、Interval identity 和有效区间；输入顺序不改变 Timeline identity；
3. `OrderRuleSnapshot` 绑定 `ProfileComponentRef(port_type=ORDER_RULE_MODEL)`、Instrument、Session 状态、`QuantityLattice`、Price Scale/Tick、可选 Price Limits、允许 Side/PositionEffect、reduce-only requirement 和 canonical supplemental rule decisions；Generic Evaluator 不包含 A 股、Binance 或 Vendor 分支；
4. Evaluation Instant 必须不早于 Translation Time。恰好一个有效 Interval 才能继续；零个产生 `missing_rule_interval`，多个产生 `overlapping_rule_intervals` 的 `MarketRuleDataIntegrityFailure`。禁止回退到 Timeline 最后一个或“当前”规则；
5. Evaluator 只验证，不修改或舍入 Order：Quantity Scale、Side-specific lot/step、minimum Quantity、Price Scale/Tick、Price Limit、Session 和 Permission 任一违规都产生 canonical-sorted `MarketRuleIssue`；
6. Minimum Notional 使用显式 `OrderRuleNotionalEvidence`。Basis 必须说明来自 limit constraint、trigger constraint 或 supplied reference；constraint basis 必须 exact 等于 source Intent Price，reference basis 必须携带 source hash。Evaluator 按 Snapshot 显式 Notional rounding 计算，不自行选价、FX 或 stablecoin peg；
7. `SupplementalOrderRuleDecision` 是 `OrderRuleModel` 已显式给出的 typed pass/reject evidence；Evaluator 只聚合 rejected decision，不解释 Vendor 字段或未知 metadata；
8. Approval/Rejection/DataIntegrityFailure 是互斥结果。Approval/Rejection 保存未修改 Spec、Timeline、resolved Interval/Snapshot、Notional evidence 和各自 hashes；Data Integrity 与合法 Market Rule rejection 分类不同；
9. 本 WP 不实现具体 A-share/Binance rules、Profile resolution、Price/Quantity rounding、Fee Reservation、Pre-trade Risk、Submission、Execution、Accounting、数据读取或 Runtime orchestration。

WP-05G 的实现已冻结在 immutable commit `63bbec453a8d3ed36a63731f452eac6018abb7b5`，状态为 `PASSED`。

验证记录：

```text
Market Rule Evaluator contract tests                              9 passed
Point-in-time Market Rule canonical golden fixture                1 passed
Public API + repository cleanliness boundaries                    5 passed
Acceptance test report                                           15 passed
Trading-kernel import boundary                                    PASS (39 files)
Full test suite                                                  382 passed
mypy                                                              no issues (24 files)
Primary LSP                                                       clean
pi-lens scoped review                                             no findings after explicit duplicate dispositions
uv lock --check                                                   PASS
Python                                                            3.13.5
```

四个 jscpd findings 属于 canonical payload/factory 显式字段列表与 typed signature 的结构性 false positive；两个小型 module-local validation helper 与既有 Kernel 模块形状相同，已在本 session defer，避免在独立 contract 稳定前引入共享内部抽象。

## 42. WP-05H FeeReservationEstimator Acceptance Card

```yaml
id: WP-05H
status: PASSED
depends_on:
  - WP-05G
  - WP-02F
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.FeeReservationRuleSource
  - crypto_quant_trading.FeeReservationBasis
  - crypto_quant_trading.FeeReservationApplicability
  - crypto_quant_trading.AccountFeeScheduleRef
  - crypto_quant_trading.FeeReservationChargeRule
  - crypto_quant_trading.FeeReservationMinimum
  - crypto_quant_trading.FeeReservationRuleSet
  - crypto_quant_trading.FeeReservationLine
  - crypto_quant_trading.FeeReservationEstimate
  - crypto_quant_trading.ResourceReservationProposal
  - crypto_quant_trading.FeeReservationFailureCode
  - crypto_quant_trading.FeeReservationFailure
  - crypto_quant_trading.FeeReservationOutcome
  - crypto_quant_trading.FeeReservationEstimator
test_commands:
  contract: uv run pytest -q tests/kernel/fee_reservations/test_fee_reservation_estimator.py
  fixture: uv run pytest -q tests/kernel/fee_reservations/test_fee_reservation_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - worst-case-fee-reservation-v1
expected_artifacts:
  - tests/fixtures/kernel/worst-case-fee-reservation-v1.json
  - build/acceptance/wp-05h-pytest.xml
  - build/acceptance/wp-05h-import-boundary-report.json
failure_contracts:
  - non-approved-market-rule-input
  - fee-estimation-before-market-rule-evaluation
  - forged-market-tax-or-account-fee-component-identity
  - missing-explicit-market-tax-or-account-rule-source
  - unknown-fee-reservation-basis
  - unknown-fee-applicability
  - fee-rule-currency-scale-or-quantization-mismatch
  - duplicate-fee-rule-or-minimum-identity
  - invalid-minimum-rule-scope
  - per-order-minimum-multiplied-by-possible-fills
  - fee-estimate-or-proposal-input-order-dependent-identity
  - fee-reservation-final-assessment-journal-profile-resolution-risk-execution-or-runtime-leakage
allowed_grade: development
evidence:
  - pytest-report
  - worst-case-fee-reservation-canonical-golden-fixture-hash
  - deterministic-rule-set-estimate-proposal-and-failure-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 0ea60de5cb646e5c4e407f4e16de8aebca0d4967
artifact_hashes:
  tests/fixtures/kernel/worst-case-fee-reservation-v1.json: sha256:65c1b8991d5cb83099dca99c077faa28713e6a86efa0829b6fb425dea7571c6a
  build/acceptance/wp-05h-pytest.xml: sha256:30932ab129bede780de41af77a347e8565a231c2826eb1912a50e4bd12e9ea31
  build/acceptance/wp-05h-import-boundary-report.json: sha256:2a6fa0a28e27e20d4e118059fd6f6e88ebf0c9cf915410f8f843d9824754a8af
```

### WP-05H Acceptance

冻结以下边界：

1. `FeeReservationEstimator` 只消费已通过 `MarketRuleApproval` 的未修改 Order、权威估算时点和显式 immutable `FeeReservationRuleSet`；不调用 Fee/Tax Profile Port、Profile Resolver、Reader、网络或账户服务；
2. Rule Set 显式绑定 `FEE_ASSESSMENT_POLICY`、`TAX_POLICY` 和版本化 `AccountFeeScheduleRef`，并要求 Market Fee、Tax 和 Account Schedule 三类来源均有明确 rule（可以显式 `not_applicable`，不能因缺失而默认为零）；
3. v1 `FeeReservationBasis` 只支持 `order_notional` 与 `flat_per_order`。未知 basis 和 `unknown` applicability 返回结构化 failure，不猜测金额；
4. 所有 charge 使用同一显式 reservation Currency/Scale。Notional rate 通过整数算术和 rule 自带 `QuantizationPolicy` 计算；不允许 float、隐式 rescale、FX 或 Stablecoin 假设；
5. `FeeReservationMinimum` 显式列出覆盖的 charge rule IDs。只有至少一个 scoped charge 明确适用时，Estimator 才先计算 scope subtotal，再只添加一次 `max(minimum - subtotal, 0)` adjustment；Estimate 不接受 possible-fill-count，因此 minimum 不可能按潜在 Fill 次数重复预留；
6. `FeeReservationEstimate` 保存 source Approval、Rule Set、逐 rule line、minimum adjustment、总最坏 Fee、估算时点及全部 identity/hash。`ResourceReservationProposal` 只把总 Fee 写入 `ReservationCommitment.fee_reserve`，不创建 Cash/Margin/Sellable/Capacity 承诺；
7. Rule、minimum 和输入 tuple 顺序不改变 Rule Set、Estimate、Proposal 或 Failure identity；任一结构化 failure 都不产生部分 Estimate/Proposal；
8. 订单终态的 release 由 `ResourceReservationBook` lifecycle 使用 Proposal commitment 完成；差额释放不是 FeeAssessment、Cash 变化或 Journal Entry；
9. 本 WP 不实现最终 `FeeAssessment`、FeeCharged Journal、per-fill/order/session 聚合、具体市场 Fee/Tax schedule、Profile resolution、Pre-trade Risk、Submission、Execution、Accounting 或 Runtime orchestration。

WP-05H 的实现已冻结在 immutable commit `0ea60de5cb646e5c4e407f4e16de8aebca0d4967`，状态为 `PASSED`。

验证记录：

```text
Fee Reservation Estimator contract tests                         10 passed
Worst-case Fee Reservation canonical golden fixture               1 passed
Public API + repository cleanliness boundaries                    5 passed
Acceptance test report                                           16 passed
Trading-kernel import boundary                                    PASS (40 files)
Full test suite                                                  393 passed
mypy                                                              no issues (25 files)
Primary LSP                                                       clean
pi-lens scoped review                                             no unresolved findings; 1 local helper duplicate deferred
uv lock --check                                                   PASS
Python                                                            3.13.5
```

一个 module-local canonical text/hash validation helper 与 `reservations.py` 形状相同，已在本 session defer；当前不为两个仍在演进的 Reservation contract 引入共享内部抽象。

## 43. WP-05I PreTradeRisk Acceptance Card

```yaml
id: WP-05I
status: PASSED
depends_on:
  - WP-05B
  - WP-05H
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.FeeReserveFundingSource
  - crypto_quant_trading.ExposureCapacityLimit
  - crypto_quant_trading.AccountRiskPolicy
  - crypto_quant_trading.PreTradeResourceRequirement
  - crypto_quant_trading.PreTradeRiskEvaluationInput
  - crypto_quant_trading.PreTradeRiskReasonCode
  - crypto_quant_trading.PreTradeRiskCheck
  - crypto_quant_trading.PreTradeRiskApproval
  - crypto_quant_trading.PreTradeRiskRejection
  - crypto_quant_trading.PreTradeRiskContractIssueCode
  - crypto_quant_trading.PreTradeRiskContractIssue
  - crypto_quant_trading.PreTradeRiskContractFailure
  - crypto_quant_trading.PreTradeRiskOutcome
  - crypto_quant_trading.PreTradeRiskEvaluator
test_commands:
  contract: uv run pytest -q tests/kernel/pretrade_risk/test_pretrade_risk.py
  fixture: uv run pytest -q tests/kernel/pretrade_risk/test_pretrade_risk_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - exact-pretrade-risk-decision-v1
expected_artifacts:
  - tests/fixtures/kernel/exact-pretrade-risk-decision-v1.json
  - build/acceptance/wp-05i-pytest.xml
  - build/acceptance/wp-05i-import-boundary-report.json
failure_contracts:
  - non-approved-market-rule-or-mismatched-fee-proposal
  - pretrade-evaluation-before-fee-estimation
  - forged-account-risk-policy-or-resource-requirement
  - account-venue-order-or-source-evidence-context-mismatch
  - stale-reservation-hash-in-availability-state
  - fee-reserve-not-exactly-included-in-resource-requirement
  - missing-cash-position-margin-or-capacity-dimension
  - resource-currency-instrument-or-scale-mismatch
  - missing-exposure-capacity-policy-coverage
  - account-order-permission-economic-rejection
  - insufficient-tradable-cash-sellable-quantity-or-available-margin
  - order-or-exposure-capacity-exceeded
  - valid-economic-rejection-misclassified-as-contract-failure
  - pretrade-clamp-order-mutation-or-replanning
  - market-rule-execution-profile-resolution-submission-accounting-or-runtime-leakage
allowed_grade: development
evidence:
  - pytest-report
  - exact-pretrade-risk-canonical-golden-fixture-hash
  - deterministic-policy-requirement-input-check-decision-and-failure-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: a3c29dd1eeaf476bcbe333398977b5c2b755ee29
artifact_hashes:
  tests/fixtures/kernel/exact-pretrade-risk-decision-v1.json: sha256:2699652fc4a85f2bd8594f86a34df8cce8f1576bc341e2e7aaf5a72dbac34870
  build/acceptance/wp-05i-pytest.xml: sha256:88df1a8618275f1207b7ec6d5244b1b6b73c8b3f7953d6de5164f449a4f6c930
  build/acceptance/wp-05i-import-boundary-report.json: sha256:49b95a5395124f8c37a2b9fecb404e95dfd75b38f2ec7b89819d568a6b505936
```

### WP-05I Acceptance

冻结以下边界：

1. `PreTradeRiskEvaluator` 只消费 immutable `MarketRuleApproval`、匹配的 WP-05H `ResourceReservationProposal`、supplied `PreTradeResourceRequirement`、当前 `ResourceReservationState`、当前 `AvailabilityState`、显式版本化 `AccountRiskPolicy` 和 authoritative Evaluation Instant；不调用 Profile/Rule/Reader/账户服务；
2. `PreTradeResourceRequirement` 保存 source Order、Market Rule decision/hash、Fee Proposal/hash、完整 `ReservationCommitment` 和版本化 source evidence。Requirement 的 `fee_reserve` 必须 exact 等于 Fee Proposal；Generic Evaluator 不推导 Spot/Margin/Derivative resource formula；
3. `AccountRiskPolicy` 绑定 Account/Venue、允许 Side/PositionEffect/reduce-only 值、Fee Reserve 使用 `tradable_cash` 或 `available_margin`、Order Capacity 上限和逐 Currency/Scale Exposure Capacity 上限。所有配置进入 config hash，不存在 no-op/default policy；
4. Availability 必须 exact 引用 supplied Reservation State hash。Cash commitment 与使用 Tradable Cash 的 Fee Reserve 按 Currency/Scale 合并比较 `CashAvailability.tradable`；Margin 与使用 Available Margin 的 Fee Reserve 合并比较 `available_margin`；Sellable Quantity 按 Instrument/Scale 比较 `PositionAvailability.sellable`；禁止跨 Currency、Instrument 或资源类别 netting；
5. Order Capacity 使用 current reservation units + proposed units 与 Policy 上限比较；Exposure Capacity 按 Currency/Scale 使用 current + proposed 与显式 Policy limit 比较。缺少 limit/resource dimension 或 identity/scale mismatch 是 Contract Failure，不是经济拒绝；
6. 合法且完整的输入只产生 Approval 或 `PreTradeRiskRejection`。账户权限、资源不足和容量超限是 canonical Economic checks/rejection；它们不变成 Validation/MarketRule/DataIntegrity/Execution rejection；
7. Approval/Rejection 保存 unchanged source Order/Executable Spec、Market Rule、Fee Proposal、完整 requirement、Reservation/Availability hashes、Policy identity 和全部 checks。相同输入及 tuple 顺序变化产生相同 Decision identity；
8. 任一 Contract/Data Failure 都不产生部分 Approval/Rejection；Evaluator 不能 clamp、修改 Order、回到 Rebalance 或生成替代订单；
9. 本 WP 不实现 Portfolio Risk、Capability/Translation/MarketRule/Fee estimation、Profile resolution、Submission、Execution、Accounting、Ledger mutation 或 Runtime Outcome mapping。

WP-05I 的实现已冻结在 immutable commit `a3c29dd1eeaf476bcbe333398977b5c2b755ee29`，状态为 `PASSED`。

验证记录：

```text
PreTrade Risk contract tests                                      10 passed
Exact PreTrade Risk canonical golden fixture                       1 passed
Public API + repository cleanliness boundaries                     5 passed
Acceptance test report                                            16 passed
Trading-kernel import boundary                                    PASS (41 files)
Full test suite                                                  404 passed
mypy                                                              no issues (26 files)
Primary LSP                                                       clean
pi-lens scoped review                                             no unresolved findings after 4 structural false-positive dispositions; 1 local helper duplicate deferred
uv lock --check                                                   PASS
Python                                                            3.13.5
```

四个 jscpd findings 属于 frozen policy config/factory 显式字段列表与 nominal Approval/Rejection 类型的结构性 false positive；一个 module-local canonical validation helper 与既有 Kernel 模块形状相同，已在本 session defer，避免在 Order Gate contracts 稳定前引入共享内部抽象。

## 44. WP-05J FeeAssessmentEngine Acceptance Card

```yaml
id: WP-05J
status: PASSED
depends_on:
  - WP-02F
  - WP-03A
owner_package: trading-kernel
public_interface:
  - crypto_quant_trading.FinalFeeRuleSource
  - crypto_quant_trading.FinalFeeCalculationBasis
  - crypto_quant_trading.FinalFeeApplicability
  - crypto_quant_trading.FinalFeeChargeRule
  - crypto_quant_trading.FinalFeeMinimum
  - crypto_quant_trading.FinalFeeRuleSet
  - crypto_quant_trading.FeeBasisClosureRef
  - crypto_quant_trading.FeeAssessmentBasisEvidence
  - crypto_quant_trading.FinalFeeLine
  - crypto_quant_trading.FinalFeeMinimumAdjustment
  - crypto_quant_trading.FinalFeeAssessmentResult
  - crypto_quant_trading.FinalFeeAssessmentFailureCode
  - crypto_quant_trading.FinalFeeAssessmentFailure
  - crypto_quant_trading.FinalFeeAssessmentOutcome
  - crypto_quant_trading.FeeAssessmentEngine
  - crypto_quant_trading.FeeChargedJournalFailureCode
  - crypto_quant_trading.FeeChargedJournalFailure
  - crypto_quant_trading.FeeChargedJournalResult
  - crypto_quant_trading.FeeChargedJournalOutcome
  - crypto_quant_trading.FeeChargedJournalTranslator
test_commands:
  contract: uv run pytest -q tests/kernel/fees/test_fee_assessment_engine.py
  fixture: uv run pytest -q tests/kernel/fees/test_fee_assessment_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - final-fee-assessment-v1
expected_artifacts:
  - tests/fixtures/kernel/final-fee-assessment-v1.json
  - build/acceptance/wp-05j-pytest.xml
  - build/acceptance/wp-05j-import-boundary-report.json
failure_contracts:
  - missing-explicit-market-tax-or-account-final-fee-rule-source
  - unknown-final-fee-calculation-basis-or-applicability
  - rule-basis-currency-scale-or-quantization-mismatch
  - incomplete-fill-order-or-session-basis
  - ambiguous-order-session-membership-or-conflicting-fill-identity
  - nonterminal-order-used-as-completed-order-basis
  - maker-taker-applicability-with-missing-or-unknown-liquidity-role
  - duplicate-basis-double-charge
  - minimum-commission-applied-more-than-once-per-aggregate-basis
  - sell-only-tax-applied-to-buy-fill
  - forged-rule-set-closure-basis-result-or-journal-identity
  - fee-reservation-estimate-reused-as-final-assessment
  - fee-assessment-fill-order-journal-or-ledger-mutation
  - concrete-market-profile-resolution-submission-execution-or-runtime-leakage
allowed_grade: development
evidence:
  - pytest-report
  - final-fee-assessment-canonical-golden-fixture-hash
  - deterministic-basis-rule-line-minimum-assessment-journal-and-failure-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 41b7811236a6d2f0d53d6a4a76d9271a37f7e4fa
artifact_hashes:
  tests/fixtures/kernel/final-fee-assessment-v1.json: sha256:22281cf7aa4b9fdfe67c1ff347fc2771cb97bc817b7d859d8c0c2916fd370533
  build/acceptance/wp-05j-pytest.xml: sha256:36952381f8c674805009eb047789041549d9a4f6d972984d6c49c72de35e82a4
  build/acceptance/wp-05j-import-boundary-report.json: sha256:66f6e9463491891465ae8150ee2a6088bbc0aadb27e833d49e30a65520045c13
```

### WP-05J Acceptance

冻结以下边界：

1. `FeeAssessmentEngine` 只消费 immutable `FeeAssessmentBasisEvidence`、显式版本化 `FinalFeeRuleSet`、caller-supplied deterministic Fee ID 和 authoritative Assessment Instant；不调用 Fee/Tax Profile Port、Profile Resolver、Reader、网络、Order submission 或账户服务；
2. Basis Evidence 精确表达 Fill、Completed Order 或 Closed Session：Fill basis 绑定单一 Fill；Order basis 绑定单一 terminal `OrderEventStream` 并从其权威 Fill records 重建；Session basis 绑定同一 Account/Venue 的 terminal Order streams 和显式版本化 `FeeBasisClosureRef`。不完整 basis 返回结构化 failure；
3. 相同 Fill/Order stream 的重复证据按 canonical hash 幂等折叠，不重复收费；同一 Fill/Order ID 的冲突内容、重复 Session membership 或不唯一 basis 返回 `ambiguous_basis`，不得猜测；
4. `FinalFeeRuleSet` 显式绑定 `FEE_ASSESSMENT_POLICY`、`TAX_POLICY` 和 `AccountFeeScheduleRef`。每个被评估 basis 必须由 Market Fee、Tax 和 Account 三类 source 显式覆盖，`not_applicable` 是合法显式规则，缺失不能默认为零；
5. v1 calculation basis 只支持 `notional_rate` 与 `flat_per_basis`；applicability 只支持 always、maker_only、taker_only、sell_only、not_applicable。Maker/Taker 使用 immutable Fill liquidity role；缺失或未知 role 在相关 rule 下 fail closed。Sell-only Tax 只选择 Sell Fill；
6. Notional 使用 Fill execution Price × Quantity 和 rule 自带 `QuantizationPolicy`，再按 Rate 以 Typed Scaled Integer 计算。所有 charge/minimum 使用 Rule Set 的单一 Currency/Scale；禁止 float、隐式 rescale、FX、stablecoin peg 或复用最坏 FeeReservationEstimate；
7. `FinalFeeMinimum` 只允许 Order/Session aggregate basis，显式列出 scoped rule IDs，并在该 basis 的 subtotal 上只添加一次 `max(minimum - subtotal, 0)`。取消/部分成交后的 terminal Order 使用实际 Fill 集，而不是预留 Notional；
8. `FinalFeeAssessmentResult` 保存 Basis、Rule Set、逐 rule line、minimum adjustment、全部 rule/component identity 和最终 `FeeAssessment`。重复相同 authoritative 输入产生相同 Assessment/Result hash；任一 failure 不产生部分 Assessment；
9. `FeeChargedJournalTranslator` 只把正的最终 Assessment 翻译为一个 `FeeCharged` `AccountingJournalEntry`，引用 Assessment ID、全部 basis/rule/minimum/component identity，并记录单一 Cash debit 与 Fee attribution。重复相同 Assessment/Journal ID 产生相同 Entry，实际幂等 apply 由 immutable Journal 的相同 ID/hash 规则保证；
10. 本 WP 不修改 Fill/Order/OrderEventStream/Journal/Ledger，不实现 Fee Reservation、Lot allocation、具体市场 Fee/Tax schedule、Profile resolution、Submission、Execution 或 Runtime orchestration。

WP-05J 的实现已冻结在 immutable commit `41b7811236a6d2f0d53d6a4a76d9271a37f7e4fa`，状态为 `PASSED`。

验证记录：

```text
Final Fee Assessment contract tests                              13 passed
Final Fee Assessment canonical golden fixture                     1 passed
Public API + repository cleanliness boundaries                    5 passed
Acceptance test report                                           19 passed
Trading-kernel import boundary                                    PASS (42 files)
Full test suite                                                  418 passed
mypy                                                              no issues (27 files)
Primary LSP                                                       clean
pi-lens scoped review                                             no unresolved findings after 6 structural false-positive dispositions; 1 local Journal-construction duplicate deferred
uv lock --check                                                   PASS
Python                                                            3.13.5
```

Reservation and final Fee contracts intentionally remain nominally separate so a worst-case reservation can never become Accounting authority. Six jscpd findings on their parallel version/hash/canonical shapes were marked structural false positives. One small explicit FeeCharged Journal construction duplicate remains session-deferred until aggregate G05 confirms the final composition seam.

## 45. G05 Target-to-Accepted-Order Aggregate Acceptance Card

```yaml
id: G05
status: PASSED
depends_on:
  - G04
  - WP-05A
  - WP-05B
  - WP-05C
  - WP-05D
  - WP-05E
  - WP-05F
  - WP-05G
  - WP-05H
  - WP-05I
  - WP-05J
owner_package: trading-kernel
public_interface:
  - no-new-production-api
  - tests.kernel.integration.test_order_acceptance_journey
  - tests/fixtures/kernel/target-to-accepted-order-journey-v1.json
test_commands:
  journey: uv run pytest -q tests/kernel/integration/test_order_acceptance_journey.py
  component_fixtures: uv run pytest -q tests/kernel/rebalance/test_rebalance_coordinator_golden.py tests/kernel/capabilities/test_order_capability_golden.py tests/kernel/translation/test_order_translator_golden.py tests/kernel/market_rules/test_market_rule_golden.py tests/kernel/fee_reservations/test_fee_reservation_golden.py tests/kernel/pretrade_risk/test_pretrade_risk_golden.py tests/kernel/orders/test_order_event_stream_golden.py tests/kernel/fees/test_fee_assessment_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - target-to-accepted-order-journey-v1
expected_artifacts:
  - tests/fixtures/kernel/target-to-accepted-order-journey-v1.json
  - build/acceptance/g05-pytest.xml
  - build/acceptance/g05-import-boundary-report.json
failure_contracts:
  - active-target-quantity-rounded-again-by-order-path
  - duplicate-working-order-created-on-repeated-evidence
  - capability-rejection-misclassified-as-translation-market-rule-risk-or-execution
  - translation-rejection-misclassified-as-capability-market-rule-risk-or-execution
  - market-rule-rejection-or-data-integrity-misclassified-as-capability-translation-risk-or-execution
  - fee-reservation-failure-reused-as-final-fee-or-misclassified
  - pretrade-economic-rejection-misclassified-as-contract-or-upstream-failure
  - rejected-stage-still-produces-submission-or-accepted-order-state
  - accepted-order-state-bypasses-required-gate-event-order
  - synthetic-fill-mutated-to-carry-final-fee
  - duplicate-final-fee-basis-double-charged-in-journal
  - timeline-bar-engine-runtime-profile-resolver-or-network-leakage
allowed_grade: development
evidence:
  - pytest-report
  - target-to-accepted-order-canonical-golden-fixture-hash
  - deterministic-plan-order-gate-state-fee-and-journal-hashes
  - distinct-stage-failure-type-report
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 37c46de51e3582ca0db0d44c904d0033be8f826a
artifact_hashes:
  tests/fixtures/kernel/target-to-accepted-order-journey-v1.json: sha256:671400b757fd26ed0b938dcb0343d239188a1ce4e6004f83158faf64ddc83c00
  build/acceptance/g05-pytest.xml: sha256:3cacfe1ea911f488c639604ff9fea9d98b4c9b88841f18a9357330c8038d409c
  build/acceptance/g05-import-boundary-report.json: sha256:66f6e9463491891465ae8150ee2a6088bbc0aadb27e833d49e30a65520045c13
```

### G05 Acceptance

冻结以下 aggregate 边界：

1. Fixture 从 G04 已物化的 `NormalizedPortfolioTarget/ActivePortfolioTarget` 开始，经 `RebalanceCoordinator` 产生 exact `PlannedOrder`；Order path 必须逐字保留已物化 Quantity，不执行第二次 rounding/sizing/risk；
2. 每个 Order 依次通过 Capability、Translation、MarketRule、Fee Reservation、PreTradeRisk，再以对应 immutable decision/evidence 创建 Order Events。`OrderEventStream` 必须按 Gate 顺序到达 `ACCEPTED`；任一 rejected/failure stage 都不能产生 Submission 或 Accepted state；
3. 相同 Target/Snapshot/Working/Reservation/Availability/Policy evidence 的 repeated tick 返回同一 Plan，不产生重复 working coverage；
4. Capability rejection、Translation rejection、MarketRule rejection、MarketRule DataIntegrityFailure、Fee Reservation failure、PreTrade economic rejection 与 Contract Failure 保持 nominal 类型和 canonical reason code 隔离，不映射为 Execution/Run Outcome；
5. FeeReservationEstimate 只进入 Reservation proposal。独立 supplied Synthetic Fill 保持 immutable 且无最终 fee 字段，随后由 WP-05J 产生 deterministic `FeeAssessment` 和 `FeeCharged` Journal Entry；相同 basis/IDs 重放由 Assessment identity + immutable Journal ID/hash 幂等；
6. Journey Golden 记录 Active Target、Plan、Order、全部 Gate decision、Accepted OrderState、independent Fill、FeeAssessment 和 FeeCharged Journal 的稳定 ID/hash；输入 tuple/mapping/registration 顺序不改变权威结果；
7. 本 Gate 不需要 Market Timeline、Bar/Execution Engine、Profile Resolver、具体市场规则、数据/网络读取、Ledger replay、Runtime Outcome、Semantic Run 或 Evidence publication，也不新增 Production API。

G05 aggregate journey 已冻结在 immutable commit `37c46de51e3582ca0db0d44c904d0033be8f826a`，状态为 `PASSED`。

验证记录：

```text
Target-to-Accepted-Order aggregate journey                         3 passed
G05 component canonical golden fixtures                            8 passed
Public API + repository cleanliness boundaries                     5 passed
Acceptance test report                                            16 passed
Trading-kernel import boundary                                     PASS (42 files)
Full test suite                                                   421 passed
mypy                                                               no issues (24 files)
Primary LSP                                                        clean
pi-lens scoped review                                              no findings
uv lock --check                                                    PASS
Python                                                             3.13.5
```

## 46. WP-06A Acceptance Card

```yaml
id: WP-06A
status: PASSED
depends_on:
  - G02
owner_package: market-data-contracts
public_interface:
  - crypto_quant_market_data.MarketBundleCapability
  - crypto_quant_market_data.MarketStreamManifest
  - crypto_quant_market_data.MarketBundleManifest
  - crypto_quant_market_data.MarketBundleRef
  - crypto_quant_market_data.MarketEvent
  - crypto_quant_market_data.InputValidationIssueCode
  - crypto_quant_market_data.InputValidationIssue
  - crypto_quant_market_data.InputValidationFailure
  - crypto_quant_market_data.MarketBundleReader
  - crypto_quant_market_data.EventCursor
  - crypto_quant_market_data.InMemoryMarketBundleReader
  - crypto_quant_market_data.MarketBundleError
  - crypto_quant_market_data.MarketBundleIntegrityError
  - crypto_quant_market_data.MarketBundleStreamError
test_commands:
  contract: uv run pytest -q tests/market_data/bundles/test_market_bundle_reader.py
  fixture: uv run pytest -q tests/market_data/bundles/test_market_bundle_reader_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - in-memory-market-bundle-reader-v1
expected_artifacts:
  - tests/fixtures/market_data/in-memory-market-bundle-reader-v1.json
  - build/acceptance/wp-06a-pytest.xml
  - build/acceptance/wp-06a-import-boundary-report.json
failure_contracts:
  - malformed-market-event-envelope
  - noncanonical-market-event-payload
  - invalid-event-availability-causality
  - duplicate-stream-ordering-key
  - manifest-stream-set-mismatch
  - stream-content-hash-mismatch
  - bundle-reference-hash-mismatch
  - missing-required-bundle-capability
  - unknown-market-stream
  - invalid-cursor-batch-size
  - cursor-position-out-of-range
  - cursor-cross-bundle-or-stream-resume
  - reader-source-adapter-or-network-leakage
allowed_grade: development
evidence:
  - pytest-report
  - in-memory-market-bundle-reader-fixture-hash
  - deterministic-page-size-parity-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 15555539d6be77532d6958184750e5718585d4e1
artifact_hashes:
  tests/fixtures/market_data/in-memory-market-bundle-reader-v1.json: sha256:8af4e06b83e9764a49102b2c865076707688e37fea6ef059efd9c4d5f965df50
  build/acceptance/wp-06a-pytest.xml: sha256:a1de74f8bd79a49c8535a189d9b73a9cfc7d810110ff199f72ff7a9f264b9cb1
  build/acceptance/wp-06a-import-boundary-report.json: sha256:20598ca6ff1d4b0f701e6ffa37b34cfd0e36f7b031ab1bd11a4a14896c0583f5
```

### WP-06A Acceptance

冻结以下实现边界：

1. `MarketBundleManifest` 是当前读取侧最小不可变 Manifest：声明 Bundle key/schema、半开覆盖区间、Instrument Catalog hash、canonical capability 集和逐 Stream 的 event count/content hash；`MarketBundleRef` 以 Manifest canonical hash 作为内容地址，不包含文件路径、供应商连接或可变 repository 状态；
2. `MarketBundleCapability` 与 Stream key 都是 canonical NFC text。Capability 只声明读取方可验证的语义能力；本 WP 不定义真实市场 coverage report，也不推断 Profile requirements；
3. `MarketEvent` 是 immutable typed envelope，保存 deterministic Market Event ID、Stream/Event type、可选 typed Instrument、event time、available time、Timeline phase/source sequence、revision/source identity/hash 和 canonical payload。Timeline ordering 使用 `(available_time.epoch_nanoseconds, phase.rank, phase.code, source_sequence.value)`；同一 Stream 的 ordering key 必须唯一，`available_time < event_time` fail closed；
4. `MarketBundleReader` 是只读 Protocol。`EventCursor` 只保存 immutable Bundle/Stream/position/batch-size token，不携带完整事件集合；Reader 以 Cursor 返回有界 batch 和新 Cursor。不同正 batch size 拼接后必须得到相同 event ID/hash 序列，Cursor/Reader 不读取 wall clock；
5. `InMemoryMarketBundleReader` 只用于 Fixture/development：构造时验证 Ref→Manifest hash、Manifest→Stream set/count/content hash、Event stream identity 和 ordering-key uniqueness。输入 Mapping/tuple 顺序不得改变 Bundle、Manifest、Cursor 或 event sequence identity；
6. 缺少 required capability 或请求未知 Stream 返回 canonical structured `InputValidationFailure`，不在本层映射为 `BLOCKED`。Malformed envelope、hash mismatch、重复 ordering key、非法 Cursor position/cross-stream resume 作为 fail-closed typed reader/integrity error；
7. Runtime 后续只能依赖 `market-data-contracts` 的这些读取接口，不得依赖 `market-bundle-builder`、Source Adapter、Pandas/Parquet/Vendor SDK 或网络。Parquet/columnar Adapter、Builder/Repository publish、Timeline merge、ObservationView、TargetStream、Bar Execution、Run Outcome 和 Evidence publication 不属于本 WP。

WP-06A 的实现已冻结在 immutable commit `15555539d6be77532d6958184750e5718585d4e1`，状态为 `PASSED`。

验证记录：

```text
MarketBundle Reader contract tests                                  6 passed
InMemory Reader canonical golden fixture                            1 passed
Public API + repository cleanliness boundaries                      5 passed
Acceptance test report                                             12 passed
Market-data-contracts import boundary                               PASS (43 files)
Full test suite                                                    428 passed
mypy                                                                no issues (6 files)
Primary LSP                                                         clean
pi-lens scoped review                                               no unresolved findings; Protocol ellipsis warnings marked false-positive
uv lock --check                                                     PASS
Python                                                              3.13.5
```

## 47. WP-06B Acceptance Card

```yaml
id: WP-06B
status: PASSED
depends_on:
  - WP-01B
  - WP-06A
owner_package: backtest-runtime
public_interface:
  - crypto_quant_backtest.TimelineSegment
  - crypto_quant_backtest.TimelineWindow
  - crypto_quant_backtest.TimelineEvent
  - crypto_quant_backtest.TimelineStreamCursor
  - crypto_quant_backtest.TimelineCursor
  - crypto_quant_backtest.TimelineBatch
  - crypto_quant_backtest.TimelineFailureCode
  - crypto_quant_backtest.TimelineFailure
  - crypto_quant_backtest.TimelineReadOutcome
  - crypto_quant_backtest.DeterministicTimeline
  - crypto_quant_backtest.TimelineError
  - crypto_quant_backtest.TimelineCursorError
test_commands:
  contract: uv run pytest -q tests/runtime/timeline/test_deterministic_timeline.py
  fixture: uv run pytest -q tests/runtime/timeline/test_deterministic_timeline_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - deterministic-multi-stream-timeline-v1
expected_artifacts:
  - tests/fixtures/runtime/deterministic-multi-stream-timeline-v1.json
  - build/acceptance/wp-06b-pytest.xml
  - build/acceptance/wp-06b-import-boundary-report.json
failure_contracts:
  - invalid-timeline-window
  - duplicate-or-empty-stream-selection
  - missing-market-stream
  - cursor-bundle-or-window-mismatch
  - cursor-source-position-mismatch
  - malformed-market-event-from-reader
  - missing-typed-source-sequence
  - duplicate-global-timeline-ordering-key
  - per-stream-or-global-order-regression
  - event-after-end-boundary-consumed
  - timeline-wall-clock-read
allowed_grade: development
evidence:
  - pytest-report
  - deterministic-timeline-fixture-hash
  - output-batch-size-parity-hashes
  - source-cursor-continuation-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 88e787fe5cc1f01d4e37e5c55cd1454f468cb477
artifact_hashes:
  tests/fixtures/runtime/deterministic-multi-stream-timeline-v1.json: sha256:c5a82a91a9a864d1e324610358758ac4e032d071f7ab88200db34c050809acc0
  build/acceptance/wp-06b-pytest.xml: sha256:474461cce3ea7d4e82b41864ab2de8d3cd15d1d7d47b88ce29ca3ce8ae646e59
  build/acceptance/wp-06b-import-boundary-report.json: sha256:4ab5263799b6345deb35626b08893cefec2a76eff1e9352fb00417723b3e78f4
```

### WP-06B Acceptance

冻结以下实现边界：

1. `DeterministicTimeline` 只消费一个只读 `MarketBundleReader` 和显式、唯一、非空的 Stream key 集；它不导入 Builder/Source Adapter，不读取文件、网络或 wall clock；
2. `TimelineWindow` 明确 `data_start <= trading_start < end_exclusive`。按 Event 的 `available_time` 划分：`[data_start, trading_start)` 为 Warmup，`[trading_start, end_exclusive)` 为 Active Trading；早于 data_start 的 Event 只推进源 Cursor，不输出，等于或晚于 end_exclusive 的 Event 不得被消费；
3. Timeline 对各 Stream 的当前头 Event 按 `(available_time.epoch_nanoseconds, phase.rank, phase.code, source_sequence.value)` merge。同一完整 ordering key 在任意两个 Stream/事件中重复，或后续 key 不严格递增，均返回结构化 `TimelineFailure`，不使用 Stream 注册顺序或容器顺序解歧；
4. “缺失 source sequence” 指 Reader 违反 typed `MarketEvent` contract、返回没有合法 `SourceSequence` 的事件；合法 sequence 数值不要求连续，避免把供应商过滤、分区或预留编号误判为数据缺口；
5. `TimelineCursor` 保存 Bundle/Window identity、逐 Stream 的精确 `EventCursor` position、已消费的最后 ordering key 和累计输出数。Timeline 将底层 Cursor 固定为单 Event 有界头部读取，输出 batch size 的变化不得改变完整事件 ID/hash/segment 序列；Reader 自身 page-size parity 已由 WP-06A 独立证明；
6. `TimelineBatch` 保存带 Warmup/Active segment 的 immutable `TimelineEvent`、下一 Cursor 和 window-complete 标志。Window 完成时 Cursor 停在第一个 end-exclusive 外 Event 之前，可用于后续确定性 continuation；
7. 缺失 Stream 继续使用 WP-06A `InputValidationFailure` 作为构造失败证据；读取期间的 malformed Event、ordering ambiguity/regression 和 Cursor 篡改使用 Timeline 自有 typed fail-closed failure/error，不映射 Run Outcome；
8. 本 WP 不实现 ObservationView、TargetStream、Strategy invocation、Slippage/Execution、Profile Resolver、Semantic Run/Attempt、Run Outcome、EngineCheckpoint 或 Evidence publication。

WP-06B 的实现已冻结在 immutable commit `88e787fe5cc1f01d4e37e5c55cd1454f468cb477`，状态为 `PASSED`。

验证记录：

```text
Deterministic Timeline contract tests                              10 passed
Canonical multi-stream golden fixture                               1 passed
Public API + repository cleanliness boundaries                      5 passed
Acceptance test report                                             16 passed
Backtest-runtime import boundary                                    PASS (44 files)
Full test suite                                                    439 passed
mypy                                                                no issues (6 files)
Primary LSP                                                         clean
pi-lens scoped review                                               no unresolved findings
uv lock --check                                                     PASS
Python                                                              3.13.5
```

## 48. WP-06C Precomputed TargetStream Acceptance Card

```yaml
id: WP-06C
status: PASSED
depends_on:
  - G04
  - WP-06A
  - WP-06B
owner_package: backtest-runtime
public_interface:
  - crypto_quant_backtest.TARGET_STREAM_CAPABILITY
  - crypto_quant_backtest.TARGET_STREAM_EVENT_TYPE
  - crypto_quant_backtest.PrecomputedTargetStream
  - crypto_quant_backtest.TargetStreamScheduleEntry
  - crypto_quant_backtest.TargetStreamDecisionSchedule
  - crypto_quant_backtest.InputDecodeIssueCode
  - crypto_quant_backtest.InputDecodeIssue
  - crypto_quant_backtest.InputDecodeFailure
  - crypto_quant_backtest.TargetCandidateValidationFailure
  - crypto_quant_backtest.TargetStreamWarmupSuppression
  - crypto_quant_backtest.TargetStreamBatchInjection
  - crypto_quant_backtest.TargetStreamInjectionOutcome
  - crypto_quant_backtest.PrecomputedTargetStreamAdapter
test_commands:
  contract: uv run pytest -q tests/runtime/target_stream/test_precomputed_target_stream.py
  fixture: uv run pytest -q tests/runtime/target_stream/test_precomputed_target_stream_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - precomputed-target-stream-injection-v1
expected_artifacts:
  - tests/fixtures/runtime/precomputed-target-stream-injection-v1.json
  - build/acceptance/wp-06c-pytest.xml
  - build/acceptance/wp-06c-import-boundary-report.json
failure_contracts:
  - unsupported-target-stream-capability-or-event-type
  - malformed-target-stream-envelope
  - duplicate-or-unknown-envelope-field
  - unsupported-target-stream-schema-version
  - schedule-event-or-context-mismatch
  - missing-or-duplicate-scheduled-event
  - candidate-validation-failure-preserved
  - atomic-decision-batch-failure-preserved
  - mixed-warmup-active-decision-group
  - warmup-produced-authoritative-batch-or-state
allowed_grade: development
evidence:
  - pytest-report
  - precomputed-target-stream-fixture-hash
  - target-stream-digest-order-parity
  - candidate-validation-failure-evidence
  - warmup-suppression-evidence
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 1ff4e74f2021579563560bfa7a4e8c821636400e
artifact_hashes:
  tests/fixtures/runtime/precomputed-target-stream-injection-v1.json: sha256:1f88bb2b3260bfc80bb375e2d877ae18d5e049c80e0682f5ecbc0d137cbbd980
  build/acceptance/wp-06c-pytest.xml: sha256:f58fd9401089d34be4bd32f83824ea6a1e138b62a62702cbbc1e98b6b70c0ba5
  build/acceptance/wp-06c-import-boundary-report.json: sha256:06ee1b9241ba00ec8818e22e0c1cf0af902532364a7249bac0662e0fbeb584e7
```

### WP-06C Acceptance

冻结以下实现边界：

1. `PrecomputedTargetStream` 只接收 immutable `MarketEvent`。事件必须使用 `precomputed_target_stream@1` capability、`strategy_decision_candidate` event type、空 Instrument identity、`event_time == available_time`，并按 canonical Market Event ordering 严格排序；构造时可接受任意输入顺序，但 canonical Stream 和 `target_stream_digest` 不得受输入顺序影响；
2. Target Event Payload v1 的 Adapter Envelope 精确为 `schema_version` 和 `candidate`。Envelope 字段、版本或 Candidate container 无法解码时产生 canonical `InputDecodeFailure`；已成功解码的 Candidate 内部 schema、identity、time、Universe、Target、confidence 等错误必须由既有 `StrategyOutputValidator` 返回并原样保存在 `TargetCandidateValidationFailure`，不得降格成 decode failure；
3. `TargetStreamDecisionSchedule` 显式绑定同一 `UtcInstant` 的 expected Strategy/Sleeve、源 Event ID 和可信 `StrategyOutputValidationContext`。Context 必须与 expectation/Decision Time 一致；Adapter 不从不受信任 Candidate Payload 推断可信 Strategy 路由、InstrumentCatalog 或 Universe；
4. 每个 Schedule Entry 恰好对应一个同 Decision Time 的 Timeline Event。缺失 Event 由同一个 `AtomicDecisionBatchCollector` 产生 missing submission failure；重复/额外 Event、源 hash 不一致、错误 Timeline instant 或 mixed Warmup/Active segment 在 Adapter 层 fail closed；
5. 所有 Candidate 先独立 decode/validate；只有全部 Validation 通过后才一次性交给既有 `AtomicDecisionBatchCollector`。任一 decode、validation 或 batch failure 都不产生部分 `DecisionBatch`、`LatestSleeveDecisionState` 或下游对象；
6. Active Event 成功后只返回 `TargetStreamBatchInjection`，其中保存完整 Stream digest、源 Event identities/hashes、Batch/State identity。它仅替代 Strategy computation；Allocation、Risk、Sizing、Planning、Execution、Settlement 和 Accounting 仍必须使用 G04/G05 之后的共享权威路径；
7. Warmup Event 仍执行 Envelope decode 和 Candidate validation，使 malformed immutable input 不被隐藏；全部成功后只返回 `TargetStreamWarmupSuppression`。Warmup 不调用 Batch Collector、不修改 prior Sleeve State，也不产生 DecisionBatch 或任何交易副作用；
8. 本 WP 不实现 Strategy invocation、ObservationView、ExecutionCase Builder、Semantic Run/Attempt、InputOrigin→Run Outcome mapping、Profile Resolver、Bar execution、Evidence publication 或任何 Builder/Source Adapter/network read。

WP-06C 的实现已冻结在 immutable commit `1ff4e74f2021579563560bfa7a4e8c821636400e`，状态为 `PASSED`。

验证记录：

```text
Precomputed TargetStream contract tests                              8 passed
Canonical TargetStream golden fixture                                1 passed
Public API + repository cleanliness boundaries                       5 passed
Acceptance test report                                              14 passed
Backtest-runtime import boundary                                     PASS (45 files)
Full test suite                                                     448 passed
mypy                                                                 no issues (7 files)
Primary LSP                                                          clean
pi-lens scoped review                                                no unresolved findings
uv lock --check                                                      PASS
Python                                                               3.13.5
```

## 49. WP-06D Deterministic Slippage Model Acceptance Card

```yaml
id: WP-06D
status: PASSED
depends_on:
  - WP-02G
  - WP-03C
owner_package: backtest-runtime
public_interface:
  - crypto_quant_backtest.SlippageModelKind
  - crypto_quant_backtest.SlippageLimitation
  - crypto_quant_backtest.SlippageApplicabilityDimension
  - crypto_quant_backtest.SlippageCalibrationRef
  - crypto_quant_backtest.SlippageApplicabilityEnvelope
  - crypto_quant_backtest.SlippageMarketState
  - crypto_quant_backtest.ExecutionReferencePrice
  - crypto_quant_backtest.SlippageRequest
  - crypto_quant_backtest.SlippageApplicabilityResult
  - crypto_quant_backtest.SlippageDecision
  - crypto_quant_backtest.SlippageApplicabilityViolation
  - crypto_quant_backtest.DeterministicBpsSlippageModel
  - crypto_quant_backtest.SimulationPortOutcome
  - crypto_quant_backtest.SlippageModel
test_commands:
  contract: uv run pytest -q tests/runtime/slippage/test_deterministic_slippage.py
  fixture: uv run pytest -q tests/runtime/slippage/test_deterministic_slippage_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - deterministic-bps-slippage-v1
expected_artifacts:
  - tests/fixtures/runtime/deterministic-bps-slippage-v1.json
  - build/acceptance/wp-06d-pytest.xml
  - build/acceptance/wp-06d-import-boundary-report.json
failure_contracts:
  - non-execution-reference-price-purpose
  - request-instrument-or-quantity-mismatch
  - future-market-state-evidence
  - applicability-instrument-violation
  - applicability-time-window-violation
  - applicability-quantity-violation
  - applicability-market-state-violation
  - invalid-component-calibration-or-envelope-identity
  - implicit-zero-slippage-configuration
  - missing-zero-slippage-development-limitation
  - nonpositive-computed-execution-price
allowed_grade: development
evidence:
  - pytest-report
  - deterministic-slippage-fixture-hash
  - buy-sell-direction-evidence
  - integer-bps-rounding-evidence
  - applicability-violation-evidence
  - explicit-zero-slippage-development-limitation
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 5f140bf495e21cb1ec86682e2c937002f8a79684
artifact_hashes:
  tests/fixtures/runtime/deterministic-bps-slippage-v1.json: sha256:09c1e6f7be45f1b156d6ae1f9f9e3efe5e23bc00dfc2a6ff08c460b78ef2d8b5
  build/acceptance/wp-06d-pytest.xml: sha256:f64c24ab7699b7b9d5c36cd80051e83e44841b994e76eebd324b77c0c72f7093
  build/acceptance/wp-06d-import-boundary-report.json: sha256:af3d930c5040c414a663681fa24e61cef37598c290bd83a8d96802543ca973ab
```

### WP-06D Acceptance

冻结以下实现边界：

1. `ExecutionReferencePrice` 必须包装一个 `PricePurpose.EXECUTION_REFERENCE` 的既有 `ResolvedMark`；Slippage Model 不选择 Bar、不解析价格流、不调用 `MarkResolver`，也不接受 high/low/close/volume 字段；
2. `SlippageRequest` 只包含 Execution Reference、`OrderSide`、正 `Quantity` 和 supplied immutable `SlippageMarketState`。Quantity Instrument 必须与 Reference Instrument 一致，市场状态证据的 `available_at` 不得晚于 Reference 的 `resolved_at`；
3. `SlippageApplicabilityEnvelope` 是显式版本化且内容寻址的单 Instrument 半开时间窗口，声明最大 Quantity 和 canonical allowed market-state keys。Model 必须逐项验证 Instrument、Time、Quantity 和 Market State；任一越界返回结构化 `SlippageApplicabilityViolation`，不得猜测或 fallback；
4. `deterministic_bps.v1` 显式声明非负 BPS units、BPS `Scale` 和 `RoundingPolicy`。Slippage amount 只使用 Python integer ratio arithmetic；Buy 为正偏移，Sell 为负偏移，且 `execution_price == reference_price + signed_amount`；
5. `SlippageDecision` 保存原始 Request、signed amount、execution price、Simulation component identity、Calibration identity、Applicability result、BPS/Scale/Rounding 配置和 limitation。Decision identity 不含 wall clock、Attempt ID 或输入对象顺序；
6. `deterministic_bps.v1` 禁止配置零 BPS。零滑点只能通过精确 key `zero_slippage.development.v1` 和零 BPS 显式配置，并必须携带 canonical `zero_slippage_development_only` limitation；该结果只能是 development-grade；
7. `DeterministicBpsSlippageModel` 实现既有 `SlippageModel` Protocol，其 `SimulationPortSpec` 使用同一 component 和 Applicability Envelope，其结果使用既有 `SimulationPortOutcome`；不存在隐式默认 Model、Calibration 或 Envelope；
8. 本 WP 不决定成交资格、Bar 选择、Fill Quantity、Fee、MarketRule、Liquidity、Latency、concrete Profile resolution、Run Outcome 或 Runtime orchestration。

WP-06D 的实现已冻结在 immutable commit `5f140bf495e21cb1ec86682e2c937002f8a79684`，状态为 `PASSED`。

验证记录：

```text
Deterministic Slippage contract tests                              8 passed
Canonical Slippage golden fixture                                  1 passed
Public API + repository cleanliness boundaries                     5 passed
Acceptance test report                                             14 passed
Backtest-runtime import boundary                                   PASS (46 files)
Full test suite                                                    457 passed
mypy                                                                no issues (8 files)
Primary LSP                                                         clean
pi-lens scoped review                                               no unresolved findings
uv lock --check                                                     PASS
Python                                                              3.13.5
```

## 50. WP-06E `next_eligible_bar_open.v1` Acceptance Card

```yaml
id: WP-06E
status: PASSED
depends_on:
  - G05
  - WP-06A
  - WP-06B
  - WP-06C
  - WP-06D
owner_package: backtest-runtime
public_interface:
  - crypto_quant_backtest.BAR_OPEN_CAPABILITY
  - crypto_quant_backtest.BAR_OPEN_EVENT_TYPE
  - crypto_quant_backtest.BarOpenKind
  - crypto_quant_backtest.BarIneligibilityReason
  - crypto_quant_backtest.NoEligibleBarAction
  - crypto_quant_backtest.BarOpenObservation
  - crypto_quant_backtest.BarLiquidityEvidence
  - crypto_quant_backtest.BarOpenCandidate
  - crypto_quant_backtest.NextBarOpenApplicability
  - crypto_quant_backtest.NextBarOpenRequest
  - crypto_quant_backtest.NextBarOpenDecision
  - crypto_quant_backtest.NextBarOpenFailureCode
  - crypto_quant_backtest.NextBarOpenFailure
  - crypto_quant_backtest.NextEligibleBarOpenModel
  - crypto_quant_backtest.FullFillConstructionFailureCode
  - crypto_quant_backtest.FullFillConstructionFailure
  - crypto_quant_backtest.FullFillResult
  - crypto_quant_backtest.FullFillBuilder
  - crypto_quant_backtest.ExecutionModel
  - crypto_quant_backtest.SimulationPortOutcome
test_commands:
  contract: uv run pytest -q tests/runtime/execution/test_next_eligible_bar_open.py
  fixture: uv run pytest -q tests/runtime/execution/test_next_eligible_bar_open_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - next-eligible-bar-open-v1
expected_artifacts:
  - tests/fixtures/runtime/next-eligible-bar-open-v1.json
  - build/acceptance/wp-06e-pytest.xml
  - build/acceptance/wp-06e-import-boundary-report.json
failure_contracts:
  - malformed-or-wrong-capability-bar-open-event
  - non-real-gap-placeholder-or-forward-filled-bar-is-ineligible
  - same-bar-or-pre-activation-fill-attempt
  - order-stream-not-accepted-active-or-already-partially-filled
  - candidate-order-instrument-or-time-context-mismatch
  - missing-or-mismatched-session-market-rule-or-funding-approval
  - stale-or-out-of-interval-market-rule-approval
  - missing-or-forged-liquidity-evidence
  - future-market-state-evidence
  - no-eligible-bar-without-explicit-tif-action
  - fill-created-before-successful-independent-slippage-decision
  - slippage-request-or-decision-mismatch
  - non-full-fill-quantity
  - input-order-or-wall-clock-dependent-decision
allowed_grade: development
evidence:
  - pytest-report
  - next-eligible-bar-open-golden-fixture-hash
  - same-bar-and-future-field-isolation-evidence
  - real-vs-placeholder-bar-eligibility-evidence
  - explicit-tif-keep-expire-evidence
  - independent-slippage-before-fill-evidence
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 71c8fb1db3472549f43afc4b9ac79ce2c58923f9
artifact_hashes:
  tests/fixtures/runtime/next-eligible-bar-open-v1.json: sha256:f05ef9e5762878c4d51d1b6ea43b6c2094258c95142683e4a045315bdc66d3bd
  build/acceptance/wp-06e-pytest.xml: sha256:cba3e8569eb95b47460966bb931ec9cf7f07bc556e8e100c80d34dfacadf617f
  build/acceptance/wp-06e-import-boundary-report.json: sha256:0bacbc5e615f8647c54eb0e9e3af2419a0d35d397be16b199e5f17c781e182c3
```

### WP-06E Acceptance

冻结以下实现边界：

1. `BarOpenObservation` 只从 capability `bar_open@1`、event type `bar_open` 的 immutable `MarketEvent` 解码 `schema_version`、`bar_kind` 和 Open Price。合格 Open 必须在 `event_time == available_time` 时可见；接口不包含 high/low/close/volume，因此 Execution Model 无法读取未来 Bar 字段；
2. `BarOpenKind.REAL` 才可能成交。`GAP_PLACEHOLDER` 和 `FORWARD_FILLED` 产生显式 ineligibility evidence，不能贡献 Execution Reference Price；
3. Model 是逐 Bar、bounded、无状态的。调用方按 Deterministic Timeline 顺序重复调用，直至第一根合格 Bar 或显式 TIF eligibility window 结束；Request 不接收未来 Bar 序列，不使用 wall clock；
4. Order 必须已有 authoritative `OrderEventStream` 且处于 `ACCEPTED`/`ACTIVE`、尚无 Fill。Candidate Bar Open 必须严格晚于当前 Order State instant，禁止 same-bar/pre-activation Fill；
5. 合格 Candidate 必须携带同一 Order、同一 Instrument、同一 Bar instant 的 `MarketRuleApproval` 和 `PreTradeRiskApproval`。Rule interval 必须覆盖 Bar instant，Session 必须 OPEN，PreTrade approval 必须引用同一 MarketRule approval；二者分别作为 Market Rule 与资金/账户资源批准证据；
6. 流动性/方向限制由 supplied immutable versioned `BarLiquidityEvidence` 显式给出。Blocked 只产生 no-fill/liquidity evidence，不伪装为 MarketRuleRejection；本 WP 不实现 A 股或其他具体市场判断；
7. `NextBarOpenApplicability` 显式完整映射全部 `TimeInForce` 到 eligibility-window 结束时的 `KEEP_ACTIVE` 或 `EXPIRE`，没有默认。非合格 Bar 在窗口尚未结束时只保持 Working；窗口结束后严格采用该映射；
8. 第一根合格真实 Bar 只生成 full remaining Quantity、由 Open 构造的 `ExecutionReferencePrice` 和 deterministic eligibility decision，不直接生成 Fill。`FullFillBuilder` 只有在获得与 Reference/Side/Quantity/Market State 精确匹配的独立成功 `SlippageDecision` 后才能构造 immutable full Fill；Slippage failure/mismatch 不得生成 Fill；
9. Open Reference 通过 exact source Event/Revision identity 构造 `PricePurpose.EXECUTION_REFERENCE` Mark。Fill 保存 Reference、Slippage decision/model/calibration 和执行 Bar instant；Fill ID 由调用方提供，本 WP 不生成 Semantic Run ID；
10. 本 WP 不实现 Partial Fill/Queue/Participation、Fee/Accounting、concrete Market Profile/Resolver、Run Outcome、Evidence publication 或完整 Engine orchestration。

WP-06E 的实现已冻结在 immutable commit `71c8fb1db3472549f43afc4b9ac79ce2c58923f9`，状态为 `PASSED`。

验证记录：

```text
Next Eligible Bar Open contract tests                              9 passed
Canonical next-open golden fixture                                 1 passed
Public API + repository cleanliness boundaries                     5 passed
Acceptance test report                                            15 passed
Backtest-runtime import boundary                                   PASS (47 files)
Full test suite                                                   467 passed
mypy                                                               no issues (9 files)
Primary LSP                                                        clean
pi-lens scoped review                                              no unresolved findings
uv lock --check                                                    PASS
Python                                                             3.13.5
```

## 51. WP-06F RunEndCoordinator Acceptance Card

```yaml
id: WP-06F
status: PASSED
depends_on:
  - WP-03E
  - WP-05A
  - WP-05B
  - WP-05C
  - WP-06B
  - WP-06E
owner_package: backtest-runtime
public_interface:
  - crypto_quant_backtest.RunEndEvidence
  - crypto_quant_backtest.RunEndCloseoutMode
  - crypto_quant_backtest.RunEndCloseoutStatus
  - crypto_quant_backtest.RunEndCloseoutRequest
  - crypto_quant_backtest.RunEndCloseoutDecision
  - crypto_quant_backtest.RunEndCloseoutFailure
  - crypto_quant_backtest.MarkToMarketCloseoutPolicy
  - crypto_quant_backtest.OrderTerminatedByRunEnd
  - crypto_quant_backtest.RunEndReservationRelease
  - crypto_quant_backtest.PendingFeeAssessmentRef
  - crypto_quant_backtest.RunEndReport
  - crypto_quant_backtest.EngineTerminationCode
  - crypto_quant_backtest.EngineTermination
  - crypto_quant_backtest.RunEndOutcome
  - crypto_quant_backtest.RunEndCoordinator
  - existing crypto_quant_backtest.CloseoutPolicy port
  - existing Timeline/Order/Reservation/Settlement/Snapshot contracts
  - canonical run-end report schema v1
  - deterministic run-end golden fixture v1
test_commands:
  contract: uv run pytest -q tests/runtime/run_end/test_run_end_coordinator.py
  fixture: uv run pytest -q tests/runtime/run_end/test_run_end_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
fixture_ids:
  - deterministic-run-end-report-v1
expected_artifacts:
  - tests/fixtures/runtime/deterministic-run-end-report-v1.json
  - build/acceptance/wp-06f-pytest.xml
  - build/acceptance/wp-06f-import-boundary-report.json
failure_contracts:
  - incomplete-or-mismatched-timeline-boundary-evidence
  - business-event-at-or-after-end-exclusive
  - final-snapshot-account-time-or-mark-context-mismatch
  - duplicate-or-conflicting-order-stream-evidence
  - nonterminal-order-without-authoritative-state
  - reservation-without-matching-working-order
  - closeout-component-or-request-hash-mismatch
  - closeout-policy-structured-failure
  - mark-to-market-decision-that-mutates-or-closes-position
  - liquidate-before-end-with-open-position-working-order-or-reservation
  - liquidation-completion-without-full-chain-evidence
  - future-pending-settlement-or-fee-evidence
  - implicit-fill-or-final-price-selection
  - input-order-or-wall-clock-dependent-report
allowed_grade: development
evidence:
  - pytest-report
  - run-end-report-golden-fixture-hash
  - end-exclusive-gating-evidence
  - working-order-termination-and-reservation-release-evidence
  - explicit-closeout-policy-outcome-evidence
  - mark-to-market-no-implicit-fill-evidence
  - liquidate-before-end-incomplete-engine-termination-evidence
  - pending-settlement-fee-and-last-mark-evidence
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 976fca04d259302a4073404ef14184de673ecc9e
artifact_hashes:
  tests/fixtures/runtime/deterministic-run-end-report-v1.json: sha256:eb2c1a8ea615247ec2ff513504adc4eacc8ffc2440464db25f148e53d4bfa4f3
  build/acceptance/wp-06f-pytest.xml: sha256:ba6e1f7128dce451832c426abadd34c9cdeb60d007d78000d56383dd8c979348
  build/acceptance/wp-06f-import-boundary-report.json: sha256:cdf9ee259f92f48f706c56c8f9f83dcf4d2e188afc54c186d5aa6a991c4dd9fd
```

### WP-06F Acceptance

冻结以下实现边界：

1. Coordinator 只接受已完成的 `TimelineCursor`，其 Window hash 必须匹配且 `end_exclusive` 是唯一 Run End boundary；所有 Order 业务事件和估值 Mark 必须严格早于该边界；
2. `RunEndEvidence` 只组合 immutable Final `PortfolioSnapshot`、Order streams、`ResourceReservationState`、`SettlementBookState` 和尚未处理的 Fee basis evidence，不读取 Journal/Ledger/Data/Profile/网络或 wall clock；
3. 所有非终态 Order 在 Run End 产生独立 `OrderTerminatedByRunEnd` evidence；存在的 active Reservation 产生精确 `RunEndReservationRelease` evidence。二者不伪造 OrderEvent、Fill、Journal Entry 或可被 replay 的 ReservationBook state；
4. Coordinator 通过现有 `CloseoutPolicy` port 执行显式 Policy。Outcome 必须使用 `CLOSEOUT_POLICY` component、匹配 Request hash，且 result/failure 均为 canonical typed evidence；
5. `MarkToMarketCloseoutPolicy` 是显式提供的 `mark_to_market.v1` component；它保留 Final Snapshot 中的非零 Position，不创建 Fill、不选择价格、不修改 Snapshot；Coordinator 不隐式实例化任何 Policy；
6. `LIQUIDATE_BEFORE_END` 只有在边界前已通过完整订单/成交/Fee/Accounting 链，且 Final Snapshot 无 open Position、无 Working Order、无 active Reservation、无 pending Fee assessment，并提供非空 completion evidence hashes 时才为 completed；否则返回结构化 `EngineTermination`；
7. `RunEndReport` 记录 terminated Orders、released Reservations、open Positions、pending Settlement obligations、pending Fee assessment references、last valuation Mark IDs、Closeout component/outcome/status 和所有输入 state hashes；输入顺序不得影响 Report ID/hash；
8. 本 WP 不拥有最终价格选择、Accounting/Journal/Ledger/Settlement/Reservation mutation、Run Outcome、Semantic Run/Attempt、Evidence finalize 或完整 Engine orchestration。

WP-06F 的实现已冻结在 immutable commit `976fca04d259302a4073404ef14184de673ecc9e`，状态为 `PASSED`。

验证记录：

```text
Run End Coordinator contract tests                                  6 passed
Canonical Run End golden fixture                                    1 passed
Public API + repository cleanliness boundaries                     5 passed
Acceptance test report                                            12 passed
Backtest-runtime import boundary                                   PASS (48 files)
Full test suite                                                   474 passed
mypy                                                               no issues (10 files)
Primary LSP                                                        clean
pi-lens scoped review                                              no unresolved findings
uv lock --check                                                    PASS
Python                                                             3.13.5
```

## 52. WP-06G Engine orchestration harness Acceptance Card

```yaml
id: WP-06G
status: PASSED
depends_on:
  - WP-06A
  - WP-06B
  - WP-06C
  - WP-06D
  - WP-06E
  - WP-06F
owner_package: backtest-runtime
public_interface:
  - crypto_quant_backtest.ResolvedExecutionCase
  - crypto_quant_backtest.ResolvedDecisionCycle
  - crypto_quant_backtest.ResolvedOrderAdmission
  - crypto_quant_backtest.ResolvedPreTradePlan
  - crypto_quant_backtest.OrderEventPlan
  - crypto_quant_backtest.ResolvedBarExecution
  - crypto_quant_backtest.CashFillAccountingPlan
  - crypto_quant_backtest.ResolvedFinancialState
  - crypto_quant_backtest.PositionLotBook
  - crypto_quant_backtest.SnapshotProjectionPlan
  - crypto_quant_backtest.EngineStage
  - crypto_quant_backtest.ExecutionTraceEntry
  - crypto_quant_backtest.ExecutionTrace
  - crypto_quant_backtest.EngineExecutionResult
  - crypto_quant_backtest.EngineFailureCode
  - crypto_quant_backtest.EngineFailure
  - crypto_quant_backtest.EngineCancellationRequest
  - crypto_quant_backtest.EngineCancellation
  - crypto_quant_backtest.EngineExecutionOutcome
  - crypto_quant_backtest.DeterministicBarEngine
  - deterministic Timeline + TargetStream + G04/G05 + execution/accounting + RunEnd composition
  - exact repeat-run trace/Ledger/Snapshot/RunEnd hash parity
test_commands:
  contract: uv run pytest -q tests/runtime/engine/test_engine_harness.py
  fixture: uv run pytest -q tests/runtime/engine/test_engine_harness_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/wp-06g-import-boundary-report.json
fixture_ids:
  - deterministic-engine-orchestration-v1
expected_artifacts:
  - tests/fixtures/runtime/deterministic-engine-orchestration-v1.json
  - build/acceptance/wp-06g-pytest.xml
  - build/acceptance/wp-06g-import-boundary-report.json
failure_contracts:
  - unresolved-or-noncanonical-execution-case
  - target-stream-input-decode-or-validation-failure-collapsed
  - warmup-target-causes-trading-side-effect
  - allocation-risk-sizing-or-planning-failure-hidden
  - capability-translation-market-rule-fee-or-pretrade-failure-hidden
  - supplied-order-does-not-match-planned-intent
  - same-bar-or-pre-activation-fill
  - slippage-or-fill-evidence-mismatch
  - fill-fee-or-accounting-failure-hidden
  - journal-ledger-reservation-or-availability-state-mismatch
  - final-snapshot-projection-input-mismatch
  - run-end-termination-hidden
  - timeline-or-case-order-dependent-trace
  - repeat-run-hash-drift
  - wall-clock-network-or-filesystem-output
  - engine-creates-semantic-run-attempt-outcome-or-evidence
allowed_grade: development
evidence:
  - pytest-report
  - engine-orchestration-golden-fixture-hash
  - resolved-execution-case-hash
  - target-stream-digest
  - execution-trace-hash
  - final-journal-and-ledger-state-hashes
  - final-portfolio-snapshot-hash
  - run-end-report-hash
  - structured-input-failure-engine-failure-cancellation-evidence
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 06bbaa36fc2143c241f125c18dd44880a3de6ab1
artifact_hashes:
  tests/fixtures/runtime/deterministic-engine-orchestration-v1.json: sha256:cb766f3a4f2dddc76cf9cb91cf003caddab6155c724d05670df362fdcda654bf
  build/acceptance/wp-06g-pytest.xml: sha256:6d55d3ab8820f4126824fb4a305ae4c251a31eccb454ec3b69819469bc14895a
  build/acceptance/wp-06g-import-boundary-report.json: sha256:84e7a5ee390aada767ce3c8e2d6eaa4e4d24296c455f698c2d9ece95b419eb9d
```

### WP-06G Acceptance

冻结以下实现边界：

1. `ResolvedExecutionCase` 是已经完成 Profile/规则/模型选择后的单账户、单 Reporting Currency、cash-instrument Bar Engine 输入；它只组合 immutable Bundle/Timeline、TargetStream schedules、G04/G05 policy/evidence plans、显式领域 ID、初始财务状态、最终估值输入和 Run End Policy，不执行 Registry lookup、BacktestRequest normalization 或 Semantic Run ID 生成；
2. Engine 按 Timeline canonical order bounded 读取。Warmup Target 只能产生 suppression trace；Active Target 必须通过现有 `PrecomputedTargetStreamAdapter → Allocation → Portfolio Risk → Position Sizing → Rebalance → Capability → Translation → MarketRule → Fee Reservation → PreTradeRisk → Accepted OrderState`，任一阶段失败都产生结构化 `EngineFailure` 且不得保留部分权威 Batch/Order；
3. Case Builder 必须提供与 Rebalance Planned Intent 完全一致的 immutable `Order`、Admission evidence 和 Pre-trade resource commitment；Engine 不推断市场/账户资源公式、不更改 Quantity、不降级订单语义；
4. 每个 Bar Event 逐个调用现有 `next_eligible_bar_open.v1`。只有匹配的 MarketRule/PreTrade approval、独立 Slippage outcome 和 FullFillBuilder 成功后才生成 Fill；禁止 same-bar、未来 Bar 字段、隐式 Slippage 或部分成交；
5. Fill 通过 CashInstrumentAccounting 产生 FillBooked Journal Entry；最终 Fee 由 FeeAssessmentEngine 从实际 Fill basis 独立计算并由 FeeChargedJournalTranslator 入账。Reservation、Journal、Ledger、Availability 和 open-lot state 按 immutable replay 重建，不使用隐藏 mutable external state；
6. Final `PortfolioSnapshot` 仍由现有 Projector 消费 Case Builder 提供的 Resolved Marks/Reporting Currency Valuations；Engine 不调用 MarkResolver/Graph policy、不发明 FX、成本或缺失估值；
7. Timeline 完成后必须调用 RunEndCoordinator。RunEnd termination 不被转成 Run Outcome；成功 Result 保存完整 Trace、Decision/Allocation/Risk/Target/Order/Fill/Fee/Journal、Final Ledger、Final Snapshot 和 RunEndReport；
8. `ExecutionTrace` 使用稳定 sequence、stage、Simulation Instant、subject identity 和 canonical evidence hash；同一 Case 在不同 Timeline batch size 或输入 tuple order 下产生完全相同 Trace、Journal、Ledger、Snapshot 和 RunEnd hashes；
9. `InputValidationFailure`、`EngineFailure` 和显式 deterministic `EngineCancellation` 是 nominally distinct branches。Engine 不映射 BLOCKED/FAILED/CANCELLED，不重试，不读取 wall clock/网络，不创建 Result/Evidence 目录；
10. 本 WP 不拥有 Synthetic Profile Registry、Semantic Run/Attempt、Run Outcome、Evidence publication/integrity、真实市场 Profile、partial fill/queue 或 derivatives accounting。

WP-06G 的实现已冻结在 immutable commit `06bbaa36fc2143c241f125c18dd44880a3de6ab1`，状态为 `PASSED`。

验证记录：

```text
Engine orchestration contract tests                                 8 passed
Canonical Engine golden fixture                                     1 passed
Public API + repository cleanliness boundaries                      5 passed
Acceptance test report                                             14 passed
Backtest-runtime import boundary                                    PASS (49 files)
Full test suite                                                    483 passed
mypy                                                                no issues (11 files)
Primary LSP                                                         clean
pi-lens scoped review                                               no unresolved findings
uv lock --check                                                     PASS
Python                                                              3.13.5
```

## 53. WP-06H Synthetic Development Profile Acceptance Card

```yaml
id: WP-06H
status: PASSED
depends_on:
  - WP-02F
  - WP-02G
owner_package: tests/support
public_interface:
  - tests.support.synthetic_market.SYNTHETIC_PROFILE_KEY
  - tests.support.synthetic_market.SYNTHETIC_PROFILE_LIMITATION
  - tests.support.synthetic_market.SyntheticCashDevelopmentProfile
  - tests.support.synthetic_market.SyntheticMarketSemanticsProfile
  - tests.support.synthetic_market.SyntheticSimulationProfile
  - tests.support.synthetic_market.SyntheticExecutionAccountProfile
  - tests.support.synthetic_market.TestProfileRegistry
  - tests.support.synthetic_market.build_synthetic_bundle
  - tests.support.synthetic_market.build_synthetic_target_stream
  - tests.support.synthetic_market.build_synthetic_execution_case
  - formal structural implementations of all Kernel Profile Ports
  - formal structural implementations of all Simulation Profile Ports
  - explicit development-profile opt-in and default lookup rejection
  - static offline synthetic Profile and factory identity
  - no production registry membership or Generic Kernel/Runtime special branch
test_commands:
  contract: uv run pytest -q tests/support/synthetic_market/test_synthetic_cash_profile.py
  fixture: uv run pytest -q tests/support/synthetic_market/test_synthetic_cash_profile_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/wp-06h-import-boundary-report.json
fixture_ids:
  - synthetic-cash-development-profile-v1
expected_artifacts:
  - tests/fixtures/support/synthetic-cash-development-profile-v1.json
  - build/acceptance/wp-06h-pytest.xml
  - build/acceptance/wp-06h-import-boundary-report.json
failure_contracts:
  - synthetic-profile-loads-without-explicit-development-opt-in
  - production-default-registry-resolves-synthetic-profile
  - profile-key-version-or-digest-is-not-stable
  - kernel-or-simulation-port-missing-or-not-structurally-conformant
  - profile-component-manifest-incomplete-duplicate-or-mismatched
  - fixed-bundle-or-target-factory-reads-network-wall-clock-or-mutable-source
  - synthetic-profile-bypasses-generic-kernel-or-runtime-interface
  - synthetic-profile-claims-real-market-or-decision-grade-semantics
  - synthetic-profile-omits-synthetic-market-profile-limitation
  - static-golden-is-generated-or-rewritten-by-test
allowed_grade: development
evidence:
  - pytest-report
  - static-synthetic-profile-golden-hash
  - profile-and-component-digests
  - kernel-port-structural-conformance-report
  - simulation-port-structural-conformance-report
  - explicit-opt-in-and-production-default-rejection-evidence
  - fixed-offline-bundle-and-target-digests
  - synthetic-market-profile-limitation
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: dc3d2f40a054cb3bed6ded35ede1cdbe5f097caf
artifact_hashes:
  tests/fixtures/support/synthetic-cash-development-profile-v1.json: sha256:85454b76b1706e11ef3a55f92dd2e3ca5972acf500074d6efffdc573a0fa8729
  build/acceptance/wp-06h-pytest.xml: sha256:6894b7f5c34dc750d00addbe1135c0c4446d1cbb793dcd328555f78c2c5454c4
  build/acceptance/wp-06h-import-boundary-report.json: sha256:84e7a5ee390aada767ce3c8e2d6eaa4e4d24296c455f698c2d9ece95b419eb9d
```

### WP-06H Acceptance

冻结以下实现边界：

1. `synthetic.cash.development.v1` 只允许位于 `tests/support/synthetic_market/`，通过 `TestProfileRegistry(allow_development_profiles=True)` 显式加载；默认 Registry 不包含该 key，lookup 必须返回结构化拒绝，不能自动 opt-in；
2. Profile 是 Market Semantics、Simulation 和 Execution Account 三个 test-only resolved plane 的不可变组合。Market plane 必须 exact-cover WP-02F 的十二个 Kernel Ports；Simulation plane 必须 exact-cover WP-02G 的六个 Simulation Ports；组件 key/version/digest 和 manifest 必须稳定、唯一且 canonical；
3. WP-06E 的 `NextEligibleBarOpenModel`、WP-06D 的 `DeterministicBpsSlippageModel` 和 WP-06F 的 `MarkToMarketCloseoutPolicy` 作为正式 Simulation Port 实现注入。其余 development-only Port 必须返回 typed deterministic outcome，不得通过 `None`、隐式 no-op 或 Runtime 特判表达；
4. 固定 Bundle、TargetStream 和 ExecutionCase factories 只能组合 committed immutable test facts，不访问网络、文件数据源、wall clock 或环境变量。ExecutionCase 仍通过现有 Generic Engine contracts；不得在 Kernel/Runtime 添加 `if synthetic` 分支；
5. Profile 必须携带 `synthetic_market_profile` limitation，grade 固定为 development，`decision_grade_eligible=false`、`deployment_authorized=false`；它不模拟真实 A 股、Binance、交易所账户或部署权限；
6. 默认生产路径 lookup 失败是测试契约，不要求在本 WP 引入生产 `ProfileResolver`；正式 Resolver 属于 WP-07A；
7. Golden Artifact 是手工审阅并提交的静态文件。测试只生成 ignored actual output 做比较，禁止写回 expected；
8. 本 WP 不拥有 Semantic Run ID、Attempt、Run Outcome、Evidence writer/finalize、真实市场 Profile、供应商数据、Runtime 网络行为或任何真实订单能力。

WP-06H 的实现已冻结在 immutable commit `dc3d2f40a054cb3bed6ded35ede1cdbe5f097caf`，状态为 `PASSED`。

验证记录：

```text
Synthetic profile contract tests                                  7 passed
Canonical synthetic profile golden fixture                        1 passed
Public API + repository cleanliness boundaries                    5 passed
Acceptance test report                                           13 passed
Import boundary                                                   PASS (49 files)
Full test suite                                                  491 passed
mypy                                                              no issues (3 files)
Primary LSP                                                       clean
pi-lens scoped review                                             no unresolved findings
uv lock --check                                                   PASS
Python                                                            3.13.5
```

## 54. G06 Engine Cash Happy Path Acceptance Card

```yaml
id: G06
status: PASSED
depends_on:
  - G03
  - G04
  - G05
  - WP-06A
  - WP-06B
  - WP-06C
  - WP-06D
  - WP-06E
  - WP-06F
  - WP-06G
  - WP-06H
owner_package: tests/support + backtest-runtime integration
public_interface:
  - tests.support.synthetic_market.build_synthetic_execution_case
  - crypto_quant_backtest.DeterministicBarEngine.run
  - development-only Deposit -> Target 50% -> next real Bar open -> Slippage -> Fill -> FeeAssessment -> Journal/Ledger -> Final Snapshot -> RunEnd journey
  - exact repeat-run ExecutionTrace/Ledger/Snapshot/RunEnd parity
  - explicit synthetic_market_profile limitation and development-only qualification
  - no Semantic Run ID, Attempt ID, Run Outcome, COMPLETED Result, decision-grade claim, or deployment authorization
test_commands:
  contract: uv run pytest -q tests/runtime/engine/test_g06_synthetic_cash_journey.py
  fixture: uv run pytest -q tests/runtime/engine/test_g06_synthetic_cash_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g06-import-boundary-report.json
fixture_ids:
  - g06-synthetic-cash-happy-path-v1
expected_artifacts:
  - tests/fixtures/runtime/g06-synthetic-cash-happy-path-v1.json
  - build/acceptance/g06-pytest.xml
  - build/acceptance/g06-import-boundary-report.json
failure_contracts:
  - synthetic-profile-not-loaded-through-explicit-development-opt-in
  - synthetic-profile-limitation-or-grade-evidence-missing
  - same-bar-or-non-real-bar-fill
  - fill-reference-slippage-or-execution-price-lineage-mismatch
  - target-order-fill-fee-journal-id-chain-broken
  - journal-ledger-mark-or-currency-valuation-rebuild-does-not-match-final-snapshot
  - run-end-report-inconsistent-with-working-order-position-or-pending-state
  - repeat-run-trace-ledger-snapshot-or-run-end-hash-drift
  - timeline-batch-size-changes-economic-or-trace-result
  - engine-result-contains-semantic-run-id-attempt-id-run-outcome-or-completed-result
  - synthetic-gate-claims-decision-grade-real-market-or-deployment-authorization
  - test-generates-or-rewrites-static-golden
allowed_grade: development
evidence:
  - pytest-report
  - static-g06-golden-hash
  - synthetic-profile-and-component-digests
  - synthetic-market-profile-limitation
  - execution-case-and-target-stream-digests
  - execution-trace-hash
  - fill-reference-slippage-execution-lineage
  - journal-and-ledger-state-hashes
  - final-portfolio-snapshot-hash
  - run-end-report-hash
  - repeat-run-and-batch-size-parity
  - no-semantic-run-attempt-outcome-evidence
  - deployment-authorized-false-evidence
  - import-boundary-report
  - static-type-report
passed_commit: 0e481d4f9e06f073446749149756f38ea0054739
artifact_hashes:
  tests/fixtures/runtime/g06-synthetic-cash-happy-path-v1.json: sha256:47d5654547b826cebd9c1b86214128999f02982c796c1c79ba635a08bd092ab9
  build/acceptance/g06-pytest.xml: sha256:7ffccc47f4ddab90ec5ad2905914fd57ca5a500c852ca54e1d43632818707e95
  build/acceptance/g06-import-boundary-report.json: sha256:84e7a5ee390aada767ce3c8e2d6eaa4e4d24296c455f698c2d9ece95b419eb9d
```

### G06 Acceptance

冻结以下 Aggregate 边界：

1. G06 只从 `TestProfileRegistry(allow_development_profiles=True)` 取得 `synthetic.cash.development.v1`，再由 WP-06H 固定 factory 构造 `ResolvedExecutionCase`；不允许直接拼装未注册 Profile 或在 Engine 中添加 Synthetic 分支；
2. Journey 必须实际通过 WP-06G Engine Harness：Deposit → 50% Target → G04 materialization → G05 admission → 下一真实 eligible Bar Open → independent Slippage → Fill → final FeeAssessment/FeeCharged → immutable Journal/Ledger → supplied Mark/Valuation → Final Snapshot → mark-to-market RunEnd；
3. Fill 的 Reference Price、signed Slippage amount 和 Execution Price 必须逐项核对；Target/Order/Fill/Fee/Journal IDs 与 trace evidence 保持完整链路；禁止 same-bar、gap placeholder、forward-fill 或未来 Bar 字段；
4. Final Snapshot 必须与 immutable Journal/Ledger、Resolved Mark、CurrencyValuationGraph evidence 一致；RunEndReport 必须与 Working Orders、Open Positions、Reservation、pending Settlement/Fee 状态一致；
5. 相同 Case 重复执行及 Timeline batch size 变化必须产生相同 case/trace/Ledger/Snapshot/RunEnd hashes；
6. G06 仍是无 Run Outcome 的 Engine Gate。Result 对象和 canonical evidence 中不得出现 Semantic Run ID、Attempt ID、COMPLETED/BLOCKED/FAILED/CANCELLED；这些属于 G07；
7. Gate Evidence 必须显式记录 `synthetic_market_profile`、`grade=development`、`decision_grade_eligible=false` 和 `deployment_authorized=false`。G06 不声称真实 A 股、Binance 或 decision-grade；
8. Golden Artifact 是静态 committed 文件，测试不能现场重写 expected。

G06 的实现已冻结在 immutable commit `0e481d4f9e06f073446749149756f38ea0054739`，状态为 `PASSED`。

验证记录：

```text
Synthetic cash Engine journey contract tests                       5 passed
Canonical G06 static golden fixture                                1 passed
Public API + repository cleanliness boundaries                    5 passed
Acceptance test report                                           11 passed
Import boundary                                                   PASS (49 files)
Full test suite                                                  497 passed
mypy                                                              no issues (5 files)
Primary LSP                                                       clean
pi-lens scoped review                                             no unresolved findings
uv lock --check                                                   PASS
Python                                                            3.13.5
```

## 55. WP-07A BacktestRequest/Profile Resolution Acceptance Card

```yaml
id: WP-07A
status: PASSED
depends_on:
  - G06
owner_package: backtest-runtime
public_interface:
  - crypto_quant_backtest.BacktestRequest
  - crypto_quant_backtest.RequestedResultGrade
  - crypto_quant_backtest.StrategyFamily
  - crypto_quant_backtest.BuildArtifactRole
  - crypto_quant_backtest.ArtifactInstallMode
  - crypto_quant_backtest.SourceTreeState
  - crypto_quant_backtest.BuildArtifactRef
  - crypto_quant_backtest.RuntimeLibraryRef
  - crypto_quant_backtest.BuildProvenance
  - crypto_quant_backtest.BuildArtifactManifest
  - crypto_quant_backtest.MarketSemanticsProfileRegistration
  - crypto_quant_backtest.SimulationProfileRegistration
  - crypto_quant_backtest.ExecutionAccountProfileRegistration
  - crypto_quant_backtest.BacktestProfileRegistry
  - crypto_quant_backtest.EnvironmentCompatibilityCheckCode
  - crypto_quant_backtest.EnvironmentCompatibilityCheck
  - crypto_quant_backtest.EnvironmentCompatibilityReport
  - crypto_quant_backtest.ResolvedBacktestEnvironment
  - crypto_quant_backtest.NormalizedBacktestRequest
  - crypto_quant_backtest.BacktestResolutionFailureCode
  - crypto_quant_backtest.BacktestResolutionFailure
  - crypto_quant_backtest.ResolvedBacktestRequest
  - crypto_quant_backtest.BacktestResolutionOutcome
  - crypto_quant_backtest.ProfileResolver
  - deterministic semantic_run_id schema v1
  - static BacktestRequest/Profile resolution golden fixture v1
test_commands:
  contract: uv run pytest -q tests/runtime/resolution/test_backtest_resolution.py
  fixture: uv run pytest -q tests/runtime/resolution/test_backtest_resolution_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/wp-07a-import-boundary-report.json
fixture_ids:
  - backtest-request-profile-resolution-v1
expected_artifacts:
  - tests/fixtures/runtime/backtest-request-profile-resolution-v1.json
  - build/acceptance/wp-07a-pytest.xml
  - build/acceptance/wp-07a-import-boundary-report.json
failure_contracts:
  - invalid-or-noncanonical-backtest-request
  - profile-plane-not-found-or-duplicate-registry-key
  - profile-registration-digest-or-component-manifest-mismatch
  - market-bundle-reference-or-coverage-mismatch
  - market-bundle-capability-missing
  - market-account-venue-or-account-context-incompatible
  - simulation-engine-or-strategy-family-incompatible
  - reporting-currency-not-supported
  - build-manifest-reference-or-profile-artifact-mismatch
  - decision-grade-request-with-development-profile
  - decision-grade-request-with-editable-or-unidentified-build-artifact
  - semantic-run-id-omits-target-stream-bundle-profile-or-build-identity
  - semantic-run-id-includes-hostname-absolute-path-build-time-or-attempt-time
  - resolver-reads-network-wall-clock-or-executes-engine
allowed_grade: development
evidence:
  - pytest-report
  - static-request-resolution-golden-hash
  - normalized-request-hash
  - target-stream-digest
  - market-bundle-manifest-hash-and-capability-report
  - three-profile-and-component-digests
  - build-artifact-manifest-identity-hash
  - development-profile-and-editable-build-limitations
  - semantic-run-id-repeat-and-change-sensitivity
  - operational-provenance-exclusion-parity
  - production-empty-registry-and-test-registry-lookup-evidence
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 04da782b84703094b5351bebe51e0d7e46afb53b
artifact_hashes:
  tests/fixtures/runtime/backtest-request-profile-resolution-v1.json: sha256:7f8f16a87e6dccfe94cbe2e0e13f1855407e436399a687f715c02e070b76e221
  build/acceptance/wp-07a-pytest.xml: sha256:6b08d1ba7e2151602e2c1fdf2f932f9b41e1e3a7a620e827491665fe192e23e9
  build/acceptance/wp-07a-import-boundary-report.json: sha256:1f1181038ee8b518c6dec3156b0dab8ace218a9dcb3ef5d5771160b8856c0925
```

### WP-07A Acceptance

冻结以下实现边界：

1. `BacktestRequest` 是 TargetStream Bar v1 的单账户、单 Reporting Currency composition-root 请求；它显式引用 Timeline 半开区间、三个 Profile key、MarketBundleRef、target-stream digest、execution-case semantic input hash、master seed、BuildArtifactManifest identity 和 requested grade；不接受 hostname、绝对路径、Attempt time 或任意 metadata escape hatch；
2. `BacktestProfileRegistry` 是不可变、精确 key lookup 的 composition-root Registry。默认空 Registry 代表 Production 不注册 Synthetic Profile；测试可显式注册 development Profile。Generic Trading Kernel 不导入或感知 Registry；
3. Market、Simulation 和 Execution Account 三个 Registration 分别验证 Profile digest、完整且唯一的 Kernel/Simulation component manifest、Venue/Account/Engine/Strategy family/Reporting Currency 约束和 required MarketBundle capabilities；Resolver 只组合、验证和报告，不调用任何市场规则、Fee、Accounting、Slippage 或 Engine；
4. `BuildArtifactManifest` 以内容身份记录 Decision Source、Trading Domain、Trading Kernel、Market Data Contracts、Backtest Runtime 和三个 Profile plane，以及 dependency lock、Python/结果相关运行库和可选 container digest。Git commit/hostname/source root/build time 只属于 provenance，不进入 Manifest identity 或 Semantic Run ID；
5. Development request 可以显式携带 development Profile、editable 或缺失 immutable content identity 的 BuildArtifact，但必须在 Compatibility Report 中保留 limitation。Decision-grade request 对 development Profile、editable install、缺失 content identity 或不匹配 Profile artifact identity 结构化失败关闭；
6. Resolver 必须验证 Bundle ref/hash、时间覆盖、required capabilities、Market/Account Venue、Account ID、Simulation engine/Strategy family、Reporting Currency、Profile grade 和 Build identity；任何 incompatibility 在 Engine 运行前返回结构化 `BacktestResolutionFailure`，本 WP 不映射 BLOCKED；
7. `semantic_run_id` 使用 versioned canonical schema，由 normalized request、MarketBundle identity、三个 Profile digest、BuildArtifactManifest identity 和 target-stream digest 共同确定。code/profile/bundle/target/request semantic input 变化必须改变 ID；Registry 顺序和 Build provenance 的 hostname/绝对路径/git commit/build time 变化不得改变 ID；
8. Resolved output 保存 immutable Environment、Compatibility Report、Normalized Request、Build Manifest identity 和 Semantic Run ID，但不创建 Attempt、不执行 Engine、不映射 Run Outcome、不写 Evidence、不重试且始终不授予部署权限。

WP-07A 的实现已冻结在 immutable commit `04da782b84703094b5351bebe51e0d7e46afb53b`，状态为 `PASSED`。

验证记录：

```text
BacktestRequest/Profile resolution contract tests                    6 passed
Canonical request-resolution golden fixture                          1 passed
Public API + repository cleanliness boundaries                       5 passed
Acceptance test report                                               12 passed
Backtest-runtime import boundary                                      PASS (50 files)
Full test suite                                                       504 passed
mypy                                                                   no issues (12 files)
Primary LSP                                                            clean
pi-lens scoped review                                                  no unresolved findings
uv lock --check                                                        PASS
Python                                                                 3.13.5
```

## 56. WP-07B Auditable Runner and Outcome Mapping Acceptance Card

```yaml
id: WP-07B
status: PASSED
depends_on:
  - WP-07A
owner_package: backtest-runtime
public_interface:
  - crypto_quant_backtest.InputOrigin
  - crypto_quant_backtest.BacktestRunOutcome
  - crypto_quant_backtest.AttemptExecutionStatus
  - crypto_quant_backtest.AttemptIdentity
  - crypto_quant_backtest.AttemptIssueSource
  - crypto_quant_backtest.AttemptIssue
  - crypto_quant_backtest.BlockedAttemptReport
  - crypto_quant_backtest.FailedAttemptReport
  - crypto_quant_backtest.CancelledAttemptReport
  - crypto_quant_backtest.ReadyToFinalizeAttempt
  - crypto_quant_backtest.AttemptExecutionRecord
  - crypto_quant_backtest.AuditableBacktestRunner
  - deterministic retry-from-start policy v1
  - static auditable-runner outcome-mapping golden fixture v1
test_commands:
  contract: uv run pytest -q tests/runtime/runner/test_auditable_runner.py
  fixture: uv run pytest -q tests/runtime/runner/test_auditable_runner_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/wp-07b-import-boundary-report.json
fixture_ids:
  - auditable-runner-outcome-mapping-v1
expected_artifacts:
  - tests/fixtures/runtime/auditable-runner-outcome-mapping-v1.json
  - build/acceptance/wp-07b-pytest.xml
  - build/acceptance/wp-07b-import-boundary-report.json
failure_contracts:
  - attempt-identity-semantic-run-or-parent-mismatch
  - resolved-request-execution-case-or-target-digest-mismatch
  - request-strategy-family-and-input-origin-mismatch
  - precomputed-target-decode-or-validation-mapped-to-failed
  - runtime-strategy-candidate-failure-mapped-to-blocked
  - engine-cancellation-not-mapped-to-cancelled
  - blocked-failed-cancelled-or-ready-to-finalize-branches-overlap
  - completed-outcome-published-before-evidence-atomic-finalize
  - retry-reuses-or-mutates-prior-attempt
  - retry-resumes-partial-engine-state-instead-of-running-initial-case
  - runner-mutates-engine-result-trace-ledger-snapshot-or-run-end
  - engine-failure-code-not-exactly-covered-by-outcome-mapping
  - unhandled-engine-exception-text-used-as-canonical-protocol
  - attempt-id-enters-semantic-run-or-simulated-domain-identity
  - evidence-writer-result-hash-integrity-grade-network-or-deployment-leakage
allowed_grade: development
evidence:
  - pytest-report
  - static-outcome-mapping-golden-hash
  - deterministic-attempt-and-parent-identity-hashes
  - exact-engine-failure-classification-coverage
  - input-origin-target-failure-mapping-evidence
  - retry-attempt-isolation-and-from-start-engine-call-evidence
  - engine-result-object-and-economic-hash-preservation
  - ready-to-finalize-has-no-completed-outcome-evidence
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: c16499ba9afc83f189d61241bba4d31a013d9e6d
artifact_hashes:
  tests/fixtures/runtime/auditable-runner-outcome-mapping-v1.json: sha256:3dfea82a2469753e2fff0d132805aeff9e425e7c69074ee7ffe285141d442542
  build/acceptance/wp-07b-pytest.xml: sha256:7c086cba09a70285a092a85368385278a78ee664429b077d5c844951c2310d97
  build/acceptance/wp-07b-import-boundary-report.json: sha256:388901cda9ecd44fb747f95324e3c6737eb2c87d940e41e0274846a180fbd5b0
```

### WP-07B Acceptance

冻结以下实现边界：

1. `AttemptIdentity` 绑定一个已解析的 `semantic_run_id`、正整数 Attempt ordinal、确定性 `attempt_<sha256>` identity 和可选 parent Attempt。Retry 必须使用更大的 ordinal、新 Attempt ID、同一 Semantic Run，并记录直接 parent；Attempt identity 不进入 Engine case、模拟领域 ID 或经济结果；
2. `InputOrigin` v1 只区分 `precomputed_target_stream` 与 `runtime_strategy`。Precomputed Request 必须使用前者；Portfolio/Liquidity Strategy Request 必须使用后者，调用者不能伪造 origin 以改变 Outcome；
3. Runner 只接受 PASSED WP-07A `ResolvedBacktestRequest`、完全匹配的初始 `ResolvedExecutionCase`、Attempt 和可选 deterministic Engine cancellation request。Request 的 execution-case semantic hash、target-stream digest 和 Semantic Run 必须逐字匹配；Runner 不解析 Profile、不修改 Case；
4. Engine `InputValidationFailure` 固定映射 `BLOCKED`。`TARGET_INPUT_DECODE`、`TARGET_VALIDATION` 和 `DECISION_BATCH` 对 Precomputed origin 映射 `BLOCKED`，对 Runtime Strategy origin 映射 `FAILED`；Engine cancellation 固定映射 `CANCELLED`；
5. 其他 `EngineFailureCode` 必须由显式、穷尽、可测试的 mapping table 分类，禁止 default/fallthrough：预期数据、市场适用性、规则歧义和模型阻断映射 `BLOCKED`；Case/Contract 不一致、Accounting/Journal/构造不变量和未处理实现异常映射 `FAILED`；
6. Runner 捕获的未处理 Engine exception 只以异常类型和版本化类型 hash 进入 `FailedAttemptReport`，异常 message/stack/log 不成为 canonical protocol；
7. 成功 Engine result 只能产生 `ReadyToFinalizeAttempt`。该对象逐字保存原 `EngineExecutionResult`，不规范化或重算 WP-07D execution result hash，不得暴露 `COMPLETED`；WP-07C Evidence atomic finalize 与后续 Integrity 成功前不存在 published Completed result；
8. `AttemptExecutionRecord` 在 ready-to-finalize、blocked、failed、cancelled 四个分支中严格互斥。`BacktestRunOutcome.COMPLETED` 仅作为后续发布状态机值存在，本 WP 的 Runner 不产生它；
9. `retry_from_start` 必须重新调用同一个初始 immutable Case，创建 child Attempt，并且不得复用前一 Attempt 的 Timeline Cursor、Journal、Ledger、Reservation、Snapshot 或其他 partial state；前一 Attempt/Report 不可修改；
10. 本 WP 不实现 Evidence 目录/writer/atomic finalize、canonical execution-result summary/hash、Integrity/ResultGrade、cache/concurrency dedup、retry scheduling、network、wall clock或 deployment authorization。

WP-07B 的实现已冻结在 immutable commit `c16499ba9afc83f189d61241bba4d31a013d9e6d`，状态为 `PASSED`。

验证记录：

```text
Auditable Runner contract tests                                      6 passed
Canonical outcome-mapping golden fixture                             1 passed
Public API + repository cleanliness boundaries                       5 passed
Acceptance test report                                               12 passed
Backtest-runtime import boundary                                     PASS (51 files)
Full test suite                                                      511 passed
mypy                                                                  no issues (13 files)
Primary LSP                                                           clean
pi-lens scoped review                                                 no unresolved findings; 1 small runtime-local helper duplicate deferred
uv lock --check                                                       PASS
Python                                                                3.13.5
```

## 57. WP-07C Evidence Writer Acceptance Card

```yaml
id: WP-07C
status: PASSED
depends_on:
  - WP-07B
owner_package: backtest-runtime
public_interface:
  - crypto_quant_backtest.EvidenceArtifactRole
  - crypto_quant_backtest.EvidenceArtifactEntry
  - crypto_quant_backtest.EvidenceManifest
  - crypto_quant_backtest.EvidencePublicationStatus
  - crypto_quant_backtest.FinalizedAttemptEvidence
  - crypto_quant_backtest.EvidenceWriteFailureCode
  - crypto_quant_backtest.EvidenceWriteFailure
  - crypto_quant_backtest.EvidencePublicationOutcome
  - crypto_quant_backtest.AttemptEvidenceWriter
  - canonical attempt staging and atomic-finalize layout v1
  - static atomic Attempt evidence golden fixture v1
test_commands:
  contract: uv run pytest -q tests/runtime/evidence/test_evidence_writer.py
  fixture: uv run pytest -q tests/runtime/evidence/test_evidence_writer_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/wp-07c-import-boundary-report.json
fixture_ids:
  - atomic-attempt-evidence-publication-v1
expected_artifacts:
  - tests/fixtures/runtime/atomic-attempt-evidence-publication-v1.json
  - build/acceptance/wp-07c-pytest.xml
  - build/acceptance/wp-07c-import-boundary-report.json
failure_contracts:
  - attempt-staging-or-final-path-escapes-canonical-run-layout
  - existing-final-attempt-is-overwritten-or-mutated
  - unfinished-staging-is-visible-as-final-attempt
  - artifact-is-not-current-version-canonical-envelope-bytes
  - evidence-manifest-omits-or-misstates-authoritative-file
  - unlisted-authoritative-file-exists-at-finalize
  - artifact-content-source-schema-role-path-or-byte-count-mismatch
  - market-bundle-content-is-copied-instead-of-hash-referenced
  - ready-attempt-publishes-completed-result-before-integrity
  - blocked-failed-or-cancelled-attempt-loses-original-outcome
  - writer-failure-leaves-final-attempt-or-publishes-result
  - writer-failure-uses-exception-message-path-or-stack-as-canonical-protocol
  - execution-summary-hash-integrity-grade-or-canonical-attempt-ref-implemented-early
  - evidence-writer-reruns-engine-or-accesses-network-external-database-or-wall-clock
allowed_grade: development
evidence:
  - pytest-report
  - static-evidence-publication-golden-hash
  - common-and-branch-artifact-coverage-report
  - canonical-envelope-content-and-source-hashes
  - manifest-exact-coverage-and-readback-evidence
  - staging-to-final-atomic-rename-and-immutability-evidence
  - market-bundle-reference-only-evidence
  - all-four-runner-branch-publication-status-evidence
  - writer-failure-failed-outcome-and-no-final-publication-evidence
  - no-completed-result-execution-summary-integrity-or-grade-evidence
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 174e11fcb14cd72e4045de8fc548e968cdc270e3
artifact_hashes:
  tests/fixtures/runtime/atomic-attempt-evidence-publication-v1.json: sha256:5810950d35c91759fb9e2184cda4869403d12680de90e03717dd05333b0ce804
  build/acceptance/wp-07c-pytest.xml: sha256:976757432b069828cf1f5d4139557f4bd9cbeca35e76683e0c58958b65a414e4
  build/acceptance/wp-07c-import-boundary-report.json: sha256:2633b569d2bdbad32d94d5ad18fd4acb254d301b5fe77c55510597d4c476fe91
```

### WP-07C Acceptance

冻结以下实现边界：

1. `AttemptEvidenceWriter` 只接受 WP-07B 的 immutable `AttemptExecutionRecord` 和 caller-supplied local evidence root。规范相对目录固定为 `runs/<semantic_run_id>/attempts/.staging/<attempt_id>/`，成功后原子 rename 到 `runs/<semantic_run_id>/attempts/<attempt_id>/`；绝对 root 是操作配置，不进入 canonical identity；
2. 每个证据文件通过 WP-02E `SchemaCatalog.write_current()` 生成当前版本 `ArtifactEnvelope` canonical bytes。Common 文件固定为 `request.json`、`environment.json`、`build-artifact-manifest.json`、`market-bundle-ref.json`、`environment-compatibility-report.json` 和 `attempt-execution-record.json`；分支文件分别是 `engine-execution-result.json`、`blocked-run-report.json`、`failure-report.json` 或 `cancellation-report.json`；
3. `EvidenceArtifactEntry` 记录 canonical relative path、Artifact role/type/schema version、envelope content hash、exact source SHA-256 和 byte count。`EvidenceManifest` canonical-sort entries，覆盖 staging 中除 `evidence-manifest.json` 自身外的全部权威文件；文件缺失、额外文件、内容、hash、schema、role、path 或大小不一致均 fail closed；
4. Writer 最后写入 `evidence-manifest.json`，read-back 全部 Artifact 和 Manifest，验证 exact coverage 后才执行同一 filesystem 的 atomic directory rename。final Attempt 已存在或 stale staging 已存在时拒绝覆盖；成功 Artifact 设为只读，重复 publish 不得改变任何 bytes；
5. `market-bundle-ref.json` 只保存 WP-06A immutable `MarketBundleRef`；Writer API 不接受或复制 Bundle events、stream partitions 或 Builder/source data；
6. Ready 分支发布状态固定为 `READY_FOR_INTEGRITY`，保留 exact `EngineExecutionResult`，但不创建 `result.json`、`BacktestRunOutcome.COMPLETED`、canonical Attempt ref、execution result summary/hash、Integrity 或 ResultGrade。BLOCKED/FAILED/CANCELLED 分支保持 Runner 的原始 terminal Outcome；
7. 任一 staging 创建、Artifact 写入、Manifest 写入、read-back、permission 或 rename 失败返回 canonical `EvidenceWriteFailure`，Outcome 固定 FAILED，只记录稳定 failure code、Attempt identity、相对 artifact subject 和异常类型 identity；异常 message、stack、hostname 和绝对 path 不进入 protocol。失败不得留下 final Attempt；
8. 本 WP 不重跑 Engine、不修改 Runner/Engine economic objects、不做 cache/concurrent dedup、不访问 network 或 mutable external database，并保持 `deployment_authorized=false`。

WP-07C 的实现已冻结在 immutable commit `174e11fcb14cd72e4045de8fc548e968cdc270e3`，状态为 `PASSED`。

验证记录：

```text
Evidence writer contract tests                                      6 passed
Canonical atomic publication golden fixture                         1 passed
Public API + repository cleanliness boundaries                      5 passed
Acceptance test report                                             12 passed
Backtest-runtime import boundary                                    PASS (52 files)
Full test suite                                                    518 passed
mypy                                                                no issues (4 files)
Primary LSP                                                         clean
pi-lens scoped/full review                                          no unresolved findings; 2 small G07-local helper duplicates deferred
uv lock --check                                                     PASS
Python                                                              3.13.5
```

## 58. WP-07D Execution Result Hash Acceptance Card

```yaml
id: WP-07D
status: PASSED
depends_on:
  - WP-07B
  - WP-07C
owner_package: backtest-runtime
public_interface:
  - crypto_quant_backtest.CanonicalExecutionSummary
  - crypto_quant_backtest.AttemptExecutionHash
  - crypto_quant_backtest.ExecutionHashAttemptRef
  - crypto_quant_backtest.ExecutionHashConsistency
  - crypto_quant_backtest.ExecutionHashMismatch
  - crypto_quant_backtest.ExecutionHashCheck
  - crypto_quant_backtest.ExecutionHashEvidenceErrorCode
  - crypto_quant_backtest.ExecutionHashEvidenceError
  - crypto_quant_backtest.ExecutionResultHasher
  - canonical authoritative execution-result hash schema v1
  - static execution-result hash golden fixture v1
test_commands:
  contract: uv run pytest -q tests/runtime/execution_hash/test_execution_result_hash.py
  fixture: uv run pytest -q tests/runtime/execution_hash/test_execution_result_hash_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/wp-07d-import-boundary-report.json
fixture_ids:
  - canonical-execution-result-hash-v1
expected_artifacts:
  - tests/fixtures/runtime/canonical-execution-result-hash-v1.json
  - build/acceptance/wp-07d-pytest.xml
  - build/acceptance/wp-07d-import-boundary-report.json
failure_contracts:
  - execution-summary-omits-authoritative-decision-allocation-risk-target-order-fill-slippage-fee-journal-ledger-snapshot-or-run-end-fact
  - execution-summary-includes-attempt-id-evidence-path-manifest-log-chart-metric-or-presentation-field
  - attempt-execution-hash-binds-non-ready-evidence
  - attempt-ready-record-and-finalized-evidence-identity-mismatch
  - engine-result-artifact-missing-wrong-role-type-schema-or-content-hash
  - execution-result-hash-changes-with-attempt-or-evidence-directory
  - authoritative-execution-or-financial-change-does-not-change-hash
  - same-semantic-run-execution-hash-mismatch-is-silently-selected
  - consistency-check-depends-on-attempt-input-order
  - execution-hash-check-publishes-completed-integrity-grade-or-deployment-authorization
  - execution-hash-layer-reads-network-wall-clock-or-derived-metrics
allowed_grade: development
evidence:
  - pytest-report
  - static-execution-hash-golden-hash
  - canonical-summary-coverage-and-exclusion-report
  - authoritative-mutation-sensitivity-evidence
  - attempt-and-evidence-path-independence-evidence
  - engine-result-artifact-envelope-binding-evidence
  - same-semantic-run-consistency-and-mismatch-evidence
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: a12821ebb38f9c5a69b2a64a566b7b35b6172268
artifact_hashes:
  tests/fixtures/runtime/canonical-execution-result-hash-v1.json: sha256:1fbcbb7950042f49985c45b1e54d523edd1ae425f07349777cbd103c79e40d14
  build/acceptance/wp-07d-pytest.xml: sha256:7f0533edba958c8e500d52b3c9f87cf154a4f1399b2972abb4e517d50ff74da6
  build/acceptance/wp-07d-import-boundary-report.json: sha256:e90779a66ff3ddf5728d538df19db62d9a43ff3b746e201dbb2176c5946a2180
```

### WP-07D Acceptance

冻结以下实现边界：

1. `CanonicalExecutionSummary` 必须逐项保存 `ExecutionTrace`、DecisionBatch、Capital Allocation、Portfolio Risk Approval/Decision、Normalized/Active Target、Order Plan/Event Stream、Fill、SlippageDecision、FeeAssessment、Accounting Journal、Final Ledger State、Final PortfolioSnapshot 和 RunEndReport；不以日志、图表、Metrics 或 presentation artifact 替代权威对象；
2. `execution_result_hash` 只由该 canonical summary 产生，不包含 Attempt ID、Semantic Run ID、Evidence relative directory/Manifest hash、日志、图表、派生 Metrics、wall clock 或 hostname。Attempt 绑定对象可以保存这些操作身份，但不能把它们混入 execution hash；
3. `ExecutionResultHasher.bind()` 只接受 WP-07B ready branch 与 WP-07C `READY_FOR_INTEGRITY` finalized evidence，要求 Attempt/Semantic Run 完全匹配，并验证 Manifest 中唯一 `engine-execution-result.json` entry 的 role/type/schema/content hash 与原始 `EngineExecutionResult` 一致；
4. `AttemptExecutionHash` 保存原始 immutable Engine Result、canonical summary、execution hash、Attempt 和 Evidence Manifest identity；构造时独立重算 summary/hash，防止 caller 伪造；
5. 同一 Semantic Run 的 Attempt refs canonical-sort。全部 hash 相同产生 `ExecutionHashConsistency`；存在多个 hash 产生 canonical `ExecutionHashMismatch`，不得按 Attempt ordinal、输入顺序、完成时间或路径选择 winner；
6. 任一权威 Decision、Allocation、Risk、Target、Order/Event、Fill、Slippage、Fee、Journal、Ledger、Snapshot、RunEnd 或 Trace 变化必须改变 hash；仅 Attempt 或 Evidence path/Manifest 变化不得改变 hash；
7. 本 WP 不实现 Integrity/ResultGrade、发布 `COMPLETED`、canonical Attempt ref、cache/dedup、Metrics、network、wall clock 或 deployment authorization。

WP-07D 的实现已冻结在 immutable commit `a12821ebb38f9c5a69b2a64a566b7b35b6172268`，状态为 `PASSED`。

验证记录：

```text
Execution result hash contract tests                                6 passed
Canonical execution hash golden fixture                             1 passed
Public API + repository cleanliness boundaries                      5 passed
Acceptance test report                                             12 passed
Backtest-runtime import boundary                                    PASS (53 files)
Full test suite                                                    525 passed
mypy                                                                no issues (4 files)
Primary LSP                                                         clean
pi-lens scoped/full review                                          no unresolved findings
uv lock --check                                                     PASS
Python                                                              3.13.5
```

## 59. WP-07A-R1 Pre-ID ExecutionCase Semantic Identity Acceptance Card

```yaml
id: WP-07A-R1
status: PASSED
depends_on:
  - WP-07A
  - G06
owner_package: backtest-runtime
public_interface:
  - crypto_quant_backtest.ExecutionCaseSemanticSpec
  - crypto_quant_backtest.ExecutionCaseIdentityRule
  - crypto_quant_backtest.ExecutionCaseIdentityBinding
  - crypto_quant_backtest.ExecutionCaseIdentityManifest
  - crypto_quant_backtest.ExecutionCaseIdentityFactory
  - crypto_quant_backtest.ExecutionCaseComposer
  - crypto_quant_backtest.ResolvedExecutionCase.semantic_spec
  - crypto_quant_backtest.ResolvedExecutionCase.semantic_spec_hash
  - crypto_quant_backtest.ResolvedExecutionCase.identity_manifest
  - BacktestRequest.execution_case_semantic_hash is the ID-free ExecutionCaseSemanticSpec hash
  - deterministic two-phase composition: semantic spec -> Semantic Run ID -> domain IDs -> ResolvedExecutionCase
  - static pre-ID case identity golden fixture v1
test_commands:
  contract: uv run pytest -q tests/runtime/resolution/test_execution_case_identity.py
  fixture: uv run pytest -q tests/runtime/resolution/test_execution_case_identity_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/wp-07a-r1-import-boundary-report.json
fixture_ids:
  - pre-id-execution-case-identity-v1
expected_artifacts:
  - tests/fixtures/runtime/pre-id-execution-case-identity-v1.json
  - build/acceptance/wp-07a-r1-pytest.xml
  - build/acceptance/wp-07a-r1-import-boundary-report.json
failure_contracts:
  - semantic-run-id-preimage-includes-final-execution-case-or-derived-domain-id
  - execution-case-semantic-spec-contains-attempt-wall-clock-hostname-or-absolute-path
  - runner-compares-request-semantic-spec-hash-to-final-case-hash
  - order-fill-fee-or-journal-id-is-not-derived-from-semantic-run-namespace
  - distinct-attempts-change-domain-id-or-final-execution-case-hash
  - semantic-spec-change-does-not-change-semantic-run-id
  - final-case-change-is-not-preserved-by-final-case-hash-and-evidence
  - compatibility-shim-becomes-default-auditable-g07-path
  - identity-correction-changes-engine-economic-result
  - behavior-affecting-execution-configuration-omitted-from-semantic-spec
  - order-parent-substitution-reaches-engine
  - identity-role-key-or-ordinal-substitution
  - identity-plan-missing-extra-duplicate-or-not-exact-covered
allowed_grade: development
evidence:
  - pytest-report
  - static-pre-id-identity-golden-hash
  - id-free-spec-and-semantic-run-preimage-evidence
  - semantic-run-domain-id-final-case-two-phase-lineage
  - production-derive-domain-id-evidence
  - two-attempt-domain-and-final-case-hash-parity
  - semantic-spec-change-sensitivity
  - unchanged-economic-execution-result-evidence
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: defe0785222910279120dbfa43e7b06e299b2c23
artifact_hashes:
  tests/fixtures/runtime/pre-id-execution-case-identity-v1.json: sha256:a252bace904d5a35cc504983b716a7e0710d51ca650ccf22665a76ef5f6a4aa8
  build/acceptance/wp-07a-r1-pytest.xml: sha256:9eb204f1966aac623e9ec3030cbc3d2fe75edd5eb9a3ce880486362da99ebb39
  build/acceptance/wp-07a-r1-import-boundary-report.json: sha256:928857fbb845ae3c7094edd4bac17c6610680de5e2b537cd2c566b881d00f599
```

### WP-07A-R1 Acceptance

冻结以下修正：

1. `ExecutionCaseSemanticSpec` 是不包含 Order、OrderEvent、Fill、FeeAssessment、SettlementObligation、Journal Entry 等派生领域 ID 的 immutable composition input；其 hash 进入 `BacktestRequest.execution_case_semantic_hash` 和 Semantic Run ID preimage；
2. composition root 必须先由 Request、Bundle、Profile、Build、Target 和 `ExecutionCaseSemanticSpec` 生成 Semantic Run ID，再用 WP-01C `derive_domain_id()` 生成领域 ID，最后构造 `ResolvedExecutionCase`；
3. `ExecutionCaseComposer` 是唯一 auditable two-phase composition entry point：它验证 Resolved Request/Spec、创建绑定 Semantic Run/IdentityNamespace/identity plan 的 `ExecutionCaseIdentityFactory`、调用 caller-supplied pure Case builder、exact-cover builder 发出的 Domain/Event identities，并冻结 `ExecutionCaseIdentityManifest`；Factory 只允许按 role 请求身份，builder 不能在派生时替换 semantic key、kind 或 ordinal；测试不得复制该算法冒充 production composition；
4. `ResolvedExecutionCase` 保存完整 `semantic_spec`、`semantic_spec_hash` 和 `identity_manifest`。Auditable final `case_hash` 必须覆盖后两者；Composer 与 Runner 都从最终 Case 重算 Spec，并比较 Request spec hash、Manifest Semantic Run、Manifest derivation plan 和 Case role exact identity coverage。Final case hash 进入 Attempt/Engine evidence，但不回流到 Semantic Run ID；
5. `ExecutionCaseSemanticSpec` 必须由构造最终 Case 的同一组 ID-free typed inputs产生；至少绑定 Timeline、TargetStream、Decision、Execution、Financial、Snapshot、RunEnd、IdentityNamespace 和 role-aware identity plan。所有行为相关模拟配置（包括完整 Slippage calibration/BPS/scale/rounding/limitations）都必须进入 Spec；Spec target digest 与 Request/Case 必须一致，OrderIntent parent 必须引用同一 cycle 的 normalized target，禁止可重贴的 placeholder digest 或 parent；
6. 同一 Semantic Spec 的独立重新 composition 以及不同 Attempt 必须拥有相同 Semantic Run ID、领域 ID 和 final case hash。Spec 语义变化必须改变 Semantic Run ID；Attempt、wall clock、hostname、绝对路径不得进入；
7. G07 路径必须通过 production `ExecutionCaseComposer`/`derive_domain_id()` 生成 Deposit/Fill/Fee Journal、Order、Fill、FeeAssessment 和模拟 OrderEvent identities。现有早期 Component Fixture 可保留显式 compatibility identity，但不得作为 G07 Auditable path；
8. Compatibility path 必须显式命名；G07-facing Resolver/Runner fixtures 默认使用 derived identity。Cross-run relabel、wrong target digest、execution-policy/slippage/parent substitution、identity role/key/ordinal swap、missing Manifest、stateful builder 和 non-exact identity plan 必须在 Engine 调用前失败；
9. 本修正不改变交易经济行为、Execution result、Profile、Bundle、Engine orchestration 或 Run Outcome；ID scrub 后完整 Engine result 必须与 compatibility baseline 一致，只打破身份循环并补充可审计 lineage。

WP-07A-R1 的实现已冻结在 immutable commit `defe0785222910279120dbfa43e7b06e299b2c23`，状态为 `PASSED`。

验证记录：

```text
Pre-ID identity contract tests                                      19 passed
Static pre-ID identity golden fixture                                1 passed
Public API + repository cleanliness boundaries                      5 passed
Full test suite                                                    545 passed
Backtest-runtime import boundary                                    PASS (54 files)
mypy                                                                no issues (20 files)
Primary LSP + pi-lens                                               clean
Multi-agent blocker reviews                                         prior findings resolved
uv lock --check                                                     PASS
Python                                                              3.13.5
```

## 60. WP-07E Integrity and Canonical Result Publication Acceptance Card

```yaml
id: WP-07E
status: PASSED
depends_on:
  - WP-07A-R1
  - WP-07C
  - WP-07D
owner_package: backtest-runtime
public_interface:
  - crypto_quant_backtest.CanonicalResultCacheHit
  - crypto_quant_backtest.IntegrityIssueSeverity
  - crypto_quant_backtest.IntegrityIssueCode
  - crypto_quant_backtest.IntegrityTraceLevel
  - crypto_quant_backtest.ResultGrade
  - crypto_quant_backtest.IntegrityIssue
  - crypto_quant_backtest.DeterministicRebuildEvidence
  - crypto_quant_backtest.AttemptConsistencySet
  - crypto_quant_backtest.IntegrityEvaluationContext
  - crypto_quant_backtest.IntegrityReport
  - crypto_quant_backtest.IntegrityEvaluationRecord
  - crypto_quant_backtest.FinalizedIntegrityEvaluation
  - crypto_quant_backtest.IntegrityEvaluator
  - crypto_quant_backtest.CanonicalAttemptRef
  - crypto_quant_backtest.CanonicalPublicationManifest
  - crypto_quant_backtest.CompletedBacktestResult
  - crypto_quant_backtest.FinalizedCanonicalResult
  - crypto_quant_backtest.CanonicalPublicationFailureCode
  - crypto_quant_backtest.CanonicalPublicationFailure
  - crypto_quant_backtest.CanonicalPublicationOutcome
  - crypto_quant_backtest.CanonicalResultPublisher
  - canonical integrity/report/result schemas v1
  - static integrity and canonical publication golden fixture v1
test_commands:
  contract: uv run pytest -q tests/runtime/integrity/test_integrity_report.py
  fixture: uv run pytest -q tests/runtime/integrity/test_integrity_report_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/wp-07e-import-boundary-report.json
fixture_ids:
  - integrity-canonical-result-publication-v1
expected_artifacts:
  - tests/fixtures/runtime/integrity-canonical-result-publication-v1.json
  - build/acceptance/wp-07e-pytest.xml
  - build/acceptance/wp-07e-import-boundary-report.json
failure_contracts:
  - integrity-context-attempt-evidence-or-execution-hash-identity-mismatch
  - execution-hash-mismatch-does-not-create-blocking-integrity-issue
  - development-profile-build-or-environment-limitation-is-hidden
  - summary-trace-market-bundle-retention-or-deterministic-rebuild-deficit-is-hidden
  - decision-grade-published-with-development-profile-editable-build-summary-trace-unrebuildable-bundle-or-blocking-issue
  - integrity-report-or-result-authorizes-deployment
  - canonical-result-published-before-attempt-evidence-atomic-finalize
  - blocked-failed-or-cancelled-attempt-is-converted-to-completed
  - canonical-publication-overwrites-existing-result-or-mutates-attempt-evidence
  - canonical-result-attempt-ref-integrity-or-source-hash-mismatch
  - fewer-than-two-eligible-attempts-publishes-completed
  - eligible-attempt-set-is-not-exact-covered-under-publication-lock
  - canonical-attempt-is-not-lowest-ordinal
  - post-integrity-blocked-or-failed-outcome-has-no-durable-evaluation-record
  - blocked-or-failed-evaluation-creates-canonical-directory-or-result-json
  - canonical-attempt-ref-integrity-result-or-publication-manifest-forms-hash-cycle
  - trace-bundle-retention-or-rebuild-evidence-is-not-bound-by-canonical-attempt-ref
  - post-publication-attempt-is-accepted-for-closed-semantic-run
  - auditable-runner-executes-without-publication-root
  - closed-run-cache-hit-is-unvalidated-or-reruns-engine
  - shared-adversarial-or-cross-filesystem-publication-is-treated-as-supported-v1
  - stale-lock-is-broken-using-wall-clock-time
  - canonical-publication-failure-leaves-visible-final-result
  - execution-hash-mismatch-is-published-as-completed-or-silently-selects-an-attempt
  - publisher-accesses-network-wall-clock-cache-external-database-or-reruns-engine
allowed_grade: development
evidence:
  - pytest-report
  - static-integrity-publication-golden-hash
  - blocking-versus-limitation-classification-evidence
  - development-and-decision-grade-rule-evidence
  - full-trace-and-summary-trace-grade-evidence
  - finalized-attempt-and-execution-hash-binding-evidence
  - execution-hash-mismatch-failed-evaluation-evidence
  - insufficient-attempt-blocked-evaluation-evidence
  - closed-attempt-set-exact-coverage-and-lowest-ordinal-selection
  - atomic-integrity-evaluation-and-canonical-directory-evidence
  - canonical-publication-hash-dag-and-manifest-exact-coverage
  - deterministic-rebuild-bundle-retention-and-trace-binding-evidence
  - trusted-single-writer-filesystem-and-run-closure-evidence
  - completed-result-and-canonical-attempt-reference-hashes
  - deployment-authorized-false-evidence
  - public-api-import-report
  - import-boundary-report
  - static-type-report
passed_commit: 0aa059145f79bf49432b14f3ad9c415880db591a
artifact_hashes:
  tests/fixtures/runtime/integrity-canonical-result-publication-v1.json: sha256:58954ba13e3d9ae211d70a47ce7b4fb921119dd5b96600433209964bcbfcf4ef
  build/acceptance/wp-07e-pytest.xml: sha256:878c35b7c433f40f4e454a4c9d38c120b3ef3c342de03a658a52d05dcd7b101e
  build/acceptance/wp-07e-import-boundary-report.json: sha256:31e5356f0766adb358334ffa4520d58fa71f8e210246d6624b3f1ada2d3e04a3
```

### WP-07E Acceptance

冻结以下实现边界：

1. Publisher 在 caller-supplied root 获取 run-level exclusive lock 后，构造 `AttemptConsistencySet` exact-cover 当时全部 finalized `READY_FOR_INTEGRITY` Attempt。`COMPLETED` 至少需要两个 eligible Attempt；全部 execution result hash 必须一致，canonical Attempt 固定选择最小 ordinal；
2. `IntegrityEvaluator` 只接受 closed Attempt set、WP-07D `AttemptExecutionHash`、Resolved Request/Environment 和 caller-supplied canonical `DeterministicRebuildEvidence`；不重跑 Engine、不修改经济对象。Rebuild evidence exact 绑定 Request、Environment、Build、Bundle manifest/retention proof、Target digest、ExecutionCase identity、Trace hash/level 和 execution result hash；
3. `IntegrityIssue` 只使用稳定 code、blocking/limitation severity 和 canonical subject keys。Synthetic/development Profile、editable/unidentified Build、Environment limitation、summary trace、MarketBundle retention 和 deterministic rebuild 缺失不得隐藏；
4. Development request 可以在没有 blocking issue 时得到 `ResultGrade.DEVELOPMENT`，但必须完整保留 limitation。Decision grade 只允许 immutable Build、decision-grade Profile、兼容 Environment、可取回 Bundle、`full_trace`/`microstructure_trace`、同一 Semantic Run 确定性一致且无 blocking issue；summary trace 永远不能 decision-grade；
5. WP-07D `ExecutionHashMismatch` 必须成为 blocking issue，并原子发布到 `runs/<semantic_run_id>/integrity-evaluations/<evaluation_id>/` 的 durable `FAILED` evaluation；少于两个 eligible Attempt 或其他预期完整性 blocking 原子发布 durable `BLOCKED` evaluation。Evaluation 目录只含 `integrity.json`、`evaluation-outcome.json` 和 exact-cover `publication-manifest.json`，不得创建 `canonical/`、`result.json` 或 canonical Attempt ref；
6. `CompletedBacktestResult` 只有在 closed Attempt set、Execution hash 一致、Integrity 无 blocking issue 后才能构造；Outcome 固定 `COMPLETED`，`deployment_authorized=false`。Canonical hash DAG 固定为 `canonical-attempt-ref.json` → `integrity.json` → `result.json` → `publication-manifest.json`；Manifest exact-cover 其他三个文件，任何子文件不得反向引用 Manifest；
7. Canonical publication 使用同一 local filesystem 的独立 staging，read-back 验证后原子 rename 为 `runs/<semantic_run_id>/canonical/`；不得修改只读 Attempt evidence。Canonical/evaluation 目录 finalize 后只读且禁止覆盖；任一写入、验证、permission 或 rename 失败不得留下 final destination，并返回结构化 FAILED publication；
8. `canonical/` 发布后 Semantic Run 永久关闭。WP-07C Evidence Writer 使用同一 run-level lock 并拒绝新 Attempt；Auditable Runner 执行必须绑定 publication root，缺失时 fail closed；已有 `canonical/` 时验证只读目录、Artifact envelope、Manifest exact coverage 和 Result hash chain 后返回 `CanonicalResultCacheHit`，不得创建 Attempt、重跑 Engine 或把 cache hit 映射成 FAILED。Post-publication same-run parity/revocation 不在 v1；
9. Filesystem threat model 固定为 trusted cooperative single-writer：受控本地同一文件系统、排他 lockfile、staging→rename；锁不得按 wall clock 自动回收。Shared/adversarial filesystem、NFS/object-store rename 语义、symlink attack 和 malicious concurrent writer 明确不支持；
10. 本 WP 不实现 cache eviction、promotion、Metrics、network、wall clock、外部数据库、真实交易或任何 deployment authorization。

上述 durable evaluation、双 Attempt closure、lowest-ordinal selection、无环 DAG、Rebuild/Trace/Bundle binding、validated cache hit 和 trusted single-writer filesystem 语义已由 production implementation 与 fault-injection coverage 固化。

WP-07E 的实现已冻结在 immutable commit `0aa059145f79bf49432b14f3ad9c415880db591a`，状态为 `PASSED`。

验证记录：

```text
Integrity and canonical publication contract tests                  46 passed
Static integrity/publication golden fixture                          1 passed
WP-07E acceptance JUnit report                                      47 passed
Public API + repository cleanliness boundaries                      5 passed
Full test suite                                                    596 passed
Backtest-runtime import boundary                                    PASS (56 files)
mypy                                                                no issues (32 files)
Primary LSP + pi-lens                                               clean
Multi-agent blocker reviews                                         no unresolved P0/P1
uv lock --check                                                     PASS
Python                                                              3.13.5
```

## 61. G07 Auditable Development Run Acceptance Card

```yaml
id: G07
status: PASSED
depends_on:
  - WP-07A-R1
  - WP-07A
  - WP-07B
  - WP-07C
  - WP-07D
  - WP-07E
owner_package: backtest-runtime integration
public_interface:
  - two-attempt synthetic Semantic Run through Resolver/Runner/Evidence/ExecutionHash/Integrity/Canonical publication
  - exact Semantic Run/domain/execution hash parity with distinct Attempt and Evidence identities
  - deterministic mismatch-to-FAILED path
  - canonical COMPLETED development Result only after atomic Attempt Evidence and Integrity
  - static G07 auditable run golden fixture v1
test_commands:
  contract: uv run pytest -q tests/runtime/integration/test_g07_auditable_run.py
  fixture: uv run pytest -q tests/runtime/integration/test_g07_auditable_run_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g07-import-boundary-report.json
fixture_ids:
  - g07-auditable-synthetic-run-v1
expected_artifacts:
  - tests/fixtures/runtime/g07-auditable-synthetic-run-v1.json
  - build/acceptance/g07-pytest.xml
  - build/acceptance/g07-import-boundary-report.json
failure_contracts:
  - attempts-share-attempt-id-or-overwrite-evidence
  - same-semantic-run-attempts-change-domain-id-or-execution-result-hash
  - evidence-manifests-are-incomplete-identical-or-path-overlapping
  - completed-result-exists-before-attempt-evidence-and-integrity
  - synthetic-development-limitation-or-deployment-false-evidence-is-hidden
  - execution-hash-mismatch-selects-winner-or-publishes-completed
  - canonical-attempt-ref-result-integrity-or-evidence-binding-mismatch
  - engine-runner-evidence-or-integrity-object-is-mutated-during-publication
allowed_grade: development
evidence:
  - pytest-report
  - static-g07-golden-hash
  - two-attempt-semantic-domain-and-execution-hash-parity
  - distinct-attempt-and-evidence-manifest-identities
  - atomic-attempt-evidence-before-completed-publication
  - development-integrity-limitations-and-result-grade
  - deterministic-mismatch-failed-publication
  - canonical-result-and-attempt-reference-hashes
  - deployment-authorized-false-evidence
  - import-boundary-report
  - static-type-report
passed_commit: 63eff046fb847d10c5d91a8c45953217e865cd98
artifact_hashes:
  tests/fixtures/runtime/g07-auditable-synthetic-run-v1.json: sha256:550141a1a2795320a65b272bd54684d5a2948554fb0eb282b48413d1cdd7e3ec
  build/acceptance/g07-pytest.xml: sha256:bc1d4d394632d04fd8a0c28d8981dfcfbbbe28c5ec38dec40bf472f4c9d5f307
  build/acceptance/g07-import-boundary-report.json: sha256:31e5356f0766adb358334ffa4520d58fa71f8e210246d6624b3f1ada2d3e04a3
```

### G07 Acceptance

冻结以下 aggregate integration 证据：

1. 同一 Synthetic Semantic Run 通过 production `ProfileResolver`、`ExecutionCaseComposer` 和 `AuditableBacktestRunner` 执行两个独立 Attempt；recording delegate 证明 `DeterministicBarEngine` 对同一 immutable `ResolvedExecutionCase` 实际调用两次，不允许复制或重贴第一次结果冒充 retry；
2. 两个 Attempt 的 Attempt ID、Evidence Manifest hash 和 final relative directory 各自独立且不覆盖；Evidence Writer 对两个只读目录分别通过 exact-coverage 验证，全部 Artifact path 集合互不相交；
3. 两个 Attempt 的 Semantic Run ID、final ExecutionCase hash、Order/Fill/Fee/Journal Domain ID 全集和 canonical execution result hash 完全一致。Attempt/Evidence identity 不进入权威经济结果 hash；
4. Canonical publication 前不存在 `canonical/`。Publisher 只在两个 finalized `READY_FOR_INTEGRITY` Evidence 和一致 execution hash 后发布 development-grade `COMPLETED`；canonical Attempt 固定为 ordinal 1，Result、Integrity、AttemptRef 与 Publication Manifest hash DAG exact-cover；
5. Synthetic/development Profile、Environment、summary trace、Bundle retention 和 deterministic rebuild limitation 全部保留，`deployment_authorized=false`；发布前后 ExecutionCase、Resolved Request、AttemptConsistencySet、Engine result 和 Attempt Evidence bytes 不变；
6. Canonical publication 封闭 Semantic Run 后，Runner 验证 canonical Artifact/hash chain 并返回 cache hit，Engine 调用数为零，完整 run tree 前后逐字节一致，且不产生第三 Attempt 目录；
7. 人为改变第二次 production Runner outcome 的权威 Trace 后，两个 execution result hash 不同；Publisher 确定性原子发布 durable `FAILED` Integrity Evaluation，不选择 winner、不创建 `canonical/` 或 Completed Result，也不修改 Attempt Evidence；
8. Static golden 同时冻结 completed 与 mismatch 路径的 Semantic/Domain/Attempt/Evidence/Execution/Integrity/Result identity，以及 canonical/evaluation 目录全部源文件 byte hash。

G07 的 aggregate integration 已冻结在 immutable commit `63eff046fb847d10c5d91a8c45953217e865cd98`，状态为 `PASSED`。G00–G07 至此形成通用、可审计的 development-grade Bar Runtime 基线。

验证记录：

```text
G07 auditable run contract tests                                  3 passed
Static G07 auditable run golden fixture                           1 passed
G07 acceptance JUnit report                                      4 passed
Public API + repository cleanliness boundaries                   5 passed
Full test suite                                                 600 passed
Backtest-runtime import boundary                                 PASS (56 files)
mypy                                                             no issues (18 files)
Primary LSP + pi-lens                                            clean
Multi-agent blocker reviews                                      no unresolved P0/P1
uv lock --check                                                  PASS
Python                                                           3.13.5
```

## 62. G08A A-Share Calendar and Session Acceptance Card

```yaml
id: G08A
status: PASSED
depends_on:
  - G07
owner_package: trading-kernel profiles/cn_a_share
public_interface:
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCalendarDayKind
  - crypto_quant_trading.profiles.cn_a_share.CnAShareSessionPhase
  - crypto_quant_trading.profiles.cn_a_share.CnAShareSessionFailureCode
  - crypto_quant_trading.profiles.cn_a_share.CnAShareFrozenCalendarDay
  - crypto_quant_trading.profiles.cn_a_share.CnAShareFrozenCalendar
  - crypto_quant_trading.profiles.cn_a_share.CnAShareSessionQuery
  - crypto_quant_trading.profiles.cn_a_share.CnAShareSessionResolution
  - crypto_quant_trading.profiles.cn_a_share.CnAShareSessionFailure
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCashSessionModel
  - structural implementation of crypto_quant_trading.SessionModel
  - static A-share frozen calendar/session golden fixture v1
test_commands:
  contract: uv run pytest -q tests/kernel/profiles/cn_a_share/test_calendar_session.py
  fixture: uv run pytest -q tests/kernel/profiles/cn_a_share/test_calendar_session_golden.py
  boundary: uv run pytest -q tests/architecture/test_import_boundary_mutations.py tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g08a-import-boundary-report.json
fixture_ids:
  - cn-a-share-calendar-session-v1
expected_artifacts:
  - tests/fixtures/kernel/profiles/cn_a_share/calendar-session-v1.json
  - build/acceptance/g08a-pytest.xml
  - build/acceptance/g08a-import-boundary-report.json
failure_contracts:
  - partial-market-profile-or-placeholder-component-created
  - unsupported-cn-cash-venue-or-calendar-identity
  - invalid-noncanonical-or-duplicate-calendar-day
  - calendar-coverage-gap-or-out-of-range-query-is-extrapolated
  - known-weekend-or-holiday-is-treated-as-coverage-failure
  - missing-calendar-data-is-treated-as-known-market-closure
  - weekend-or-frozen-holiday-produces-session
  - phase-overlap-gap-or-non-half-open-boundary
  - opening-call-opening-pause-lunch-or-closing-call-boundary-drift
  - trading-date-is-derived-from-utc-date
  - session-id-changes-with-phase-input-order-attempt-or-semantic-run
  - calendar-or-component-digest-is-circular-or-order-dependent
  - concrete-profile-is-root-reexported-or-imported-by-generic-kernel
  - decision-schedule-timeline-market-event-t1-rule-fee-tax-or-corporate-action-leak
  - runtime-network-wall-clock-provider-filesystem-or-market-bundle-read
  - development-fixture-claims-current-live-or-decision-grade-calendar
allowed_grade: development
evidence:
  - pytest-report
  - static-calendar-session-golden-hash
  - official-rule-and-holiday-source-reference-table
  - xshg-xshe-calendar-and-component-digests
  - exact-half-open-phase-boundary-table
  - known-closure-versus-coverage-missing-evidence
  - local-trading-date-versus-utc-date-evidence
  - stable-session-id-repeat-resolution-and-input-order-evidence
  - profile-port-outcome-result-and-failure-evidence
  - network-market-bundle-and-generic-kernel-import-absence
  - import-boundary-report
  - static-type-report
passed_commit: cafd55d80b4e686dc6ad779f1bd03d2f6092b119
artifact_hashes:
  tests/fixtures/kernel/profiles/cn_a_share/calendar-session-v1.json: sha256:ef2ed7296ca9da16791ca7839583b93f151b1425734f53b02dd6e8556c0dd26d
  build/acceptance/g08a-pytest.xml: sha256:aa79fb78a0df3597a7b548db8d107c6d282ce7f76c0c51ebb41951cab499b18d
  build/acceptance/g08a-import-boundary-report.json: sha256:265205da492c1e2bc5cf838dc11c6f90c060c2827574e7f895e897a864fcc53c
```

### G08A Acceptance

冻结以下实现边界：

1. G08A 只新增一个 concrete `SessionModel` Adapter，位置固定在 `crypto_quant_trading.profiles.cn_a_share`；不修改 generic `SessionModel` seam、不 root re-export concrete profile、不创建 partial `MarketSemanticsProfileRegistration`。完整 Profile composition 属于 G08H；
2. v1 scope 仅含 `VenueId("xshg")`/`calendar_id="CN.XSHG"` 和 `VenueId("xshe")`/`calendar_id="CN.XSHE"` 的标准现金股票竞价 Session。BSE、基金、债券、港股通、盘后固定价格和临时特殊 Session 均不在 scope；
3. 全部 public value 使用 `schema_version=1` canonical form，并冻结为以下字段和值；实现不得在 READY 后自行发明字段、枚举或 optional 语义：

```text
CnAShareCalendarDayKind
  trading | weekend | frozen_holiday

CnAShareSessionPhase
  pre_open | opening_call | opening_pause | continuous_morning |
  lunch_break | continuous_afternoon | closing_call | post_close

CnAShareSessionFailureCode
  unsupported_venue | calendar_coverage_missing

CnAShareFrozenCalendarDay
  local_date: date
  kind: CnAShareCalendarDayKind

CnAShareFrozenCalendar
  venue_id: VenueId
  calendar_id: str
  timezone_name: str = "Asia/Shanghai"
  coverage_start: date
  coverage_end_exclusive: date
  days: tuple[CnAShareFrozenCalendarDay, ...]
  calendar_hash: derived property

CnAShareSessionQuery
  venue_id: VenueId
  instant: UtcInstant

CnAShareSessionResolution
  venue_id: VenueId
  instant: UtcInstant
  local_date: date
  day_kind: CnAShareCalendarDayKind
  session_id: SessionId | None
  trading_date: TradingDate | None
  phase: CnAShareSessionPhase | None
  phase_start: UtcInstant | None
  phase_end_exclusive: UtcInstant | None
  is_open: bool

CnAShareSessionFailure
  code: CnAShareSessionFailureCode
  venue_id: VenueId
  instant: UtcInstant
  calendar_id: str
  subject_key: str

CnAShareCashSessionModel
  component_ref: ProfileComponentRef
  resolve_session(query) -> ProfilePortOutcome[CnAShareSessionResolution, CnAShareSessionFailure]
```

1. Trading-day resolution 必须同时具有 non-null SessionId、TradingDate、phase 和 phase bounds，`day_kind=trading`。Known weekend/holiday resolution 必须保留 venue/instant/local_date/day_kind，其他五个 Session fields 全为 null 且 `is_open=false`。Failure branch 不得携带 result；result branch 不得携带 failure；
2. Calendar 是 caller-injected、finite、immutable、逐日 exact-cover 的 `CnAShareFrozenCalendar`，统一使用 `Asia/Shanghai`。输入顺序 canonical 化，重复日期、coverage gap、错误 timezone 和 calendar/venue pair 在构造时拒绝；unsupported query venue 返回 `unsupported_venue`，coverage 外或缺失日期返回 `calendar_coverage_missing`；
3. Market phase 使用独立 `CnAShareSessionPhase`，禁止复用 Engine ordering 的 `TimelinePhase`。系统半开区间固定为：`pre_open [00:00,09:15)`、`opening_call [09:15,09:25)`、`opening_pause [09:25,09:30)`、`continuous_morning [09:30,11:30)`、`lunch_break [11:30,13:00)`、`continuous_afternoon [13:00,14:57)`、`closing_call [14:57,15:00)`、`post_close [15:00,24:00)`；
4. `opening_call`、两个 continuous phase 和 `closing_call` 为 OPEN；pre/opening pause/lunch/post-close 为 CLOSED。Known weekend/holiday 返回成功的 no-session resolution；unsupported venue 或 coverage missing 返回结构化 failure。缺失数据绝不能伪装成市场关闭；
5. TradingDate 必须由 `Asia/Shanghai` local date 和 Calendar row 显式解析。Fixture 必须包含 local date 已进入次日而 UTC date 仍为前一日的 pre-open 查询，证明禁止 UTC-date inference；
6. `SessionId` 固定使用现有 explicit identity：`SessionId(calendar_id, "YYYY-MM-DD.regular")`。同一 Venue/TradingDate 的全部 phase 共用一个 Session ID；它不包含 Attempt、Semantic Run、query instant 或 phase；
7. Calendar hash preimage 固定为 `{type="cn_a_share_frozen_calendar", schema_version=1, venue_id, calendar_id, timezone_name, coverage_start, coverage_end_exclusive, canonical_sorted_days}`，排除自身 hash。`ProfileComponentRef` 固定为 `port_type=session_model`、`component_key="equity.cn_a_share.cash.session.v1"`、`component_version=1`；component digest preimage 固定为 `{type="cn_a_share_cash_session_component", schema_version=1, component_key, component_version, algorithm_key="cn-a-share-cash-session-resolution-v1", venue_id, calendar_id, timezone_name, calendar_hash, phase_table}`。因此 XSHG/XSHE digest 必须不同，且任何 identity、Calendar 或 phase 变化都会改变 digest；
8. Frozen Fixture 对两个 Venue exact-cover `[2024-02-08, 2024-02-20)`：2024-02-08 与 2024-02-19 为 trading，2024-02-09 至 2024-02-17 为 official frozen holiday closure，2024-02-18 为 weekend closure。2024-02-20 查询必须 coverage failure；
9. Official fact references 固定为 SSE/SZSE 2023 revised trading rules中的现金股票竞价时段，以及 SSE 上证公告〔2023〕47号、SZSE 深证会〔2023〕409号/2024 春节通知中的休市安排。Exchange facts 只提供 clock ranges；半开端点与 pause/lunch/pre/post phase 名称是本系统显式解释，不冒充交易所原文；
10. G08A 不拥有 DecisionSchedule、Warmup、Timeline/MarketEvent、T+1、Quantity Lattice、Price Limit、Fee/Tax、Corporate Action、Registry、Resolver 或 Runtime orchestration；不得访问 network、wall clock、provider SDK、filesystem source repository、MarketBundle Builder 或 G12 runtime data。Contract test 必须用 AST 扫描 concrete profile source，拒绝 `open`、`os`、`pathlib`、`socket`、`urllib`、`http.client`、已知 network SDK，以及 `datetime.now/utcnow`、`date.today`、`time.time/time_ns`；
11. Frozen Fixture 和 Model 仅允许 development-grade，不声明 current-live 或 decision-grade calendar。Legacy `cycle-rotation-platform` 没有可用 Calendar/Session oracle，G08H 不得对 G08A 语义声称 legacy parity。

Official primary references：

- SSE《上海证券交易所交易规则（2023年修订）》Rule 2.4.2/3.3.1：`https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/10824490/files/dcbe58edb194451d93f19b1f7dd8fb4c.docx`；
- SZSE《深圳证券交易所交易规则（2023年修订）》Rule 2.3.2/3.3.1：`https://docs.static.szse.cn/www/lawrules/rule/repeal/rules/W020230217564423808793.pdf`；
- SSE 2024 休市通知（上证公告〔2023〕47号）：`https://www.sse.com.cn/disclosure/announcement/general/c/c_20231226_5733939.shtml`；
- SZSE 2024 休市通知（深证会〔2023〕409号）：`https://www.szse.cn/disclosure/notice/t20231226_605108.html`；
- SZSE 2024 春节休市通知：`https://www.szse.cn/disclosure/notice/general/t20240201_605828.html`；
- IANA `Asia/Shanghai` mapping：`https://data.iana.org/time-zones/tzdb/zone1970.tab`。

上述接口、范围、phase、closure/coverage、identity、digest、provenance 和 ownership 语义已由实现与固定 Golden 固化。

G08A 的实现边界如下：

1. `CnAShareFrozenCalendar` 对 caller-supplied 日期行排序后 exact-cover 有限区间，拒绝重复、缺口、错误 timezone 和错误 Venue/Calendar identity；Calendar hash 使用独立 `canonical_sorted_days` preimage，不把自身 hash 纳入；
2. XSHG/XSHE frozen fixture 精确覆盖 `[2024-02-08, 2024-02-20)`，Calendar hash 与 Session component digest 由硬编码 spec literal 独立校验。Golden 保存两个 Venue 的完整日期行、组件身份和全部解析证据；
3. `CnAShareCashSessionModel` 结构化实现 generic `SessionModel`，返回 exactly-one `ProfilePortOutcome`。交易日 Resolution 强制 SessionId、TradingDate、phase、canonical bounds 和 open state 彼此一致；Known holiday/weekend 成功返回 no-session closure；
4. Phase resolution 使用 `Asia/Shanghai` local date 和整数 nanosecond half-open comparison。Fixture 证明本地 2024-02-19 pre-open 对应 UTC 2024-02-18，且每个 phase start 和边界前一 nanosecond 均按冻结表解析；
5. Query 先以整数 epoch nanoseconds 对 Calendar UTC coverage 做 fail-closed range check，再执行 datetime/timezone conversion。任意大小的正负 `UtcInstant` 和 `datetime.max` 均返回 `calendar_coverage_missing`，不会泄漏 OverflowError；bounded subject key 与 canonical input hash 保持可审计；
6. 为保持 Trading Domain 已接受的无界 signed-integer 契约，canonical encoder 增加无 process-global 设置的 base-1e9 decimal fallback；正常整数的既有 canonical bytes/hash 不变，正负 5001 位整数具有确定 canonical JSON 表达；
7. Concrete profile 只从 `crypto_quant_trading.profiles.cn_a_share` 导出，generic root 不 re-export，generic Kernel 不反向依赖。AST contract 递归扫描 concrete package，拒绝 filesystem、network SDK 和 wall-clock 入口；
8. 实现不创建 partial Market Profile，不接入 Runtime/Registry/MarketBundle，不包含 G08B–G08H 的 T+1、Lattice、Price Limit、Fee/Tax、Corporate Action 或部署资格语义；结果只允许 development-grade。

G08A 已冻结在 immutable commit `cafd55d80b4e686dc6ad779f1bd03d2f6092b119`，状态为 `PASSED`。

验证记录：

```text
G08A calendar/session contract tests                              25 passed
Static A-share calendar/session golden fixture                     1 passed
G08A acceptance JUnit report                                      26 passed
Architecture and isolation boundaries                             25 passed
Full test suite                                                  627 passed
Trading-kernel import boundary                                    PASS (59 files)
mypy                                                               no issues (8 files)
Primary LSP + pi-lens                                              clean
Multi-agent blocker reviews                                        no unresolved P0/P1
uv lock --check                                                    PASS
Python                                                             3.13.5
```

## 63. G08B T+1 Settlement and Availability Acceptance Card

```yaml
id: G08B
status: PASSED
depends_on:
  - G08A
  - WP-01C
  - WP-02C
  - WP-03F
  - WP-05B
  - WP-05C
owner_package: trading-kernel profiles/cn_a_share
public_interface:
  - crypto_quant_trading.profiles.cn_a_share.CnAShareSettlementFailureCode
  - crypto_quant_trading.profiles.cn_a_share.CnAShareSettlementQuery
  - crypto_quant_trading.profiles.cn_a_share.CnAShareSettlementResolution
  - crypto_quant_trading.profiles.cn_a_share.CnAShareSettlementFailure
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCashSettlementModel
  - CnAShareCashSettlementModel.component_ref
  - CnAShareCashSettlementModel.resolve_settlement
  - CnAShareCashSettlementModel.availability_rules
  - canonical A-share settlement/availability schemas v1
  - static A-share settlement/availability golden fixture v1
test_commands:
  contract: uv run pytest -q tests/kernel/profiles/cn_a_share/test_settlement_availability.py
  fixture: uv run pytest -q tests/kernel/profiles/cn_a_share/test_settlement_availability_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py tests/kernel/ports/test_profile_port_contracts.py tests/kernel/settlement/test_settlement_availability.py tests/kernel/profiles/cn_a_share/test_calendar_session.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g08b-import-boundary-report.json
fixture_ids:
  - cn-a-share-settlement-availability-v1
expected_artifacts:
  - tests/fixtures/kernel/profiles/cn_a_share/settlement-availability-v1.json
  - build/acceptance/g08b-pytest.xml
  - build/acceptance/g08b-import-boundary-report.json
failure_contracts:
  - ordinary-a-share-buy-is-sellable-on-trade-date
  - next-trading-date-is-inferred-by-calendar-day-or-weekday-arithmetic
  - calendar-coverage-missing-is-treated-as-a-known-closure-or-next-date
  - sale-cash-receivable-is-withdrawable-before-maturation
  - sale-cash-receivable-is-not-tradable-on-trade-date
  - negative-delivery-leg-remains-pending-after-fill-time
  - settlement-applied-rebooks-ledger-economics
  - settlement-model-recomputes-notional-or-rounding-instead-of-binding-fill-accounting
  - accounting-entry-fill-account-venue-instrument-currency-or-sign-mismatch-is-accepted
  - settlement-domain-id-kind-duplicate-or-source-fill-mismatch-is-accepted
  - working-order-reservation-is-merged-with-settlement-obligation
  - pending-position-or-cash-receivable-policy-is-caller-configurable
  - xshg-and-xshe-component-identity-collide
  - profile-component-digest-omits-calendar-timing-or-availability-policy
  - profile-adapter-mutates-settlement-book-ledger-reservation-or-runtime-state
  - profile-adapter-reads-network-wall-clock-provider-or-filesystem-source
  - observable-non-equity-or-non-cny-context-is-treated-as-supported
  - g08h-caller-precondition-is-claimed-as-g08b-validated
allowed_grade: development
evidence:
  - pytest-report
  - static-settlement-availability-golden-hash
  - official-t-plus-one-and-holiday-source-references
  - official-fact-versus-system-convention-classification
  - fill-accounting-to-obligation-exact-binding
  - authoritative-journal-ledger-prefix-and-settlement-source-binding
  - buy-position-t-plus-one-sellability-evidence
  - sale-cash-t-zero-tradability-and-t-plus-one-withdrawability-evidence
  - next-frozen-trading-date-and-boundary-nanosecond-evidence
  - immediate-negative-delivery-and-deferred-positive-receivable-evidence
  - settlement-book-full-replay-and-prefix-resume-parity
  - settlement-versus-reservation-state-and-hash-isolation
  - fixed-market-settlement-rules-and-availability-state-hashes
  - xshg-xshe-economic-parity-and-component-identity-separation
  - profile-port-outcome-result-and-failure-evidence
  - network-market-bundle-runtime-and-generic-kernel-import-absence
  - import-boundary-report
  - static-type-report
passed_commit: dc941e960c26db298da9f600d7d747725ee26402
artifact_hashes:
  tests/fixtures/kernel/profiles/cn_a_share/settlement-availability-v1.json: sha256:4b66c6ed6594c05de8723f11b69839507ba5991b8b913b6fe32f61d6960ba800
  build/acceptance/g08b-pytest.xml: sha256:48658fa8b66f5209231c9a71c0705b82ff0fb62fb170f0405e21a99b912cb80e
  build/acceptance/g08b-import-boundary-report.json: sha256:a4c47ac240df0219ac8d7a6e2e2f024e25b13657132c23bbf0a64467a21c39f7
```

### G08B Acceptance

以下语义、接口、Fixture、failure 和 purity contract 已冻结并实现：

1. G08B 只在 `crypto_quant_trading.profiles.cn_a_share` 增加一个 concrete Settlement Adapter；不修改 generic `SettlementModel`、`SettlementBook`、`MarketSettlementRules` 或 `AvailabilityProjection` seam，不 root re-export concrete 类型，不创建 partial `MarketSemanticsProfileRegistration`。完整 Profile composition 仍属于 G08H；
2. v1 scope 仅含 `VenueId("xshg")`/`CN.XSHG` 与 `VenueId("xshe")`/`CN.XSHE` 的普通人民币 A 股现金账户。Adapter 可从 Query 直接验证的范围只有 Venue、broad `InstrumentType.EQUITY`、Instrument identity 和 CNY quote/settlement currency；普通 A 股而非 ETF/REIT/Stock Connect、现金而非融资账户等不可由当前 Contract 观察的区分，必须作为 caller/G08H precondition，G08B 不得声称已验证。BSE、B 股、基金、债券、跨境、融资融券、卖空、质押/冻结、参与人违约和 Broker/Bank transfer cut-off 均不在 scope；
3. 官方事实与系统约定必须分开：SSE/SZSE 规则证明普通 A 股 T 日买入不得 T 日卖出；中国结算规则、DVP 生效公告与 2024 春节公告证明下一交易日和 2024-02-08 → 2024-02-19 参与人层资金交收关系。Sale proceeds 的 retail tradable/withdrawable bucket 和 exact intraday instant 是账户/Profile 约定，不得冒充逐 Fill 中央净额交收或所有券商的法定统一时点；
4. G08B 保持 `SettlementObligation.settlement_time` 的通用含义：它是版本化客户账户中该 Cash/Position 交付义务完成的时点；在本 Adapter 中，账户交付完成同时使该资源 Availability 成熟。Buy negative Cash leg 与 Sell negative Position leg 在 Fill execution time 完成；Buy positive Position receivable 在下一 Frozen TradingDate `00:00 Asia/Shanghai` 完成；Sell positive Cash receivable 在下一 Frozen TradingDate `16:00 Asia/Shanghai` 完成。本 Adapter 不模拟中央参与人净额交收、法定权属登记或银行服务时点；
5. `00:00` Position convention 使 pre-open Planning/Reservation 可看到 T+1 可卖数量；`16:00` Cash convention 只是参考中国结算最晚参与人资金交收边界的保守 development-grade 客户账户约定。两个 convention、immediate-negative-leg policy、G08A Session component identity 和 fixed availability policy 全部进入 component digest；任一改变必须改变 digest；
6. Public canonical schema v1 固定如下，READY 后实现不得新增字段、枚举或 optional 解释：

```text
CnAShareSettlementFailureCode
  unsupported_venue | unsupported_instrument | unsupported_currency |
  trade_time_not_open | calendar_coverage_missing |
  accounting_effect_mismatch | settlement_identity_mismatch

CnAShareSettlementQuery
  fill: Fill
  instrument: InstrumentDefinition
  fill_accounting_entry: AccountingJournalEntry
  cash_obligation_id: DomainId
  position_obligation_id: DomainId

CnAShareSettlementResolution
  venue_id: VenueId
  fill_id: DomainId
  trade_date: TradingDate
  next_trading_date: TradingDate
  position_availability_time: UtcInstant
  cash_withdrawal_time: UtcInstant
  fill_accounting_entry_hash: str
  obligations: tuple[AccountSettlementObligation, ...]

CnAShareSettlementFailure
  code: CnAShareSettlementFailureCode
  fill_id: DomainId
  venue_id: VenueId
  calendar_id: str
  subject_key: str

CnAShareCashSettlementModel
  calendar: CnAShareFrozenCalendar
  component_ref: ProfileComponentRef
  resolve_settlement(query) -> ProfilePortOutcome[CnAShareSettlementResolution, CnAShareSettlementFailure]
  availability_rules(schema: LedgerSchema) -> MarketSettlementRules
```

Canonical serialization exact 为：

```text
Query.to_canonical_dict()
  {type:"cn_a_share_settlement_query", schema_version:1,
   fill, instrument, fill_accounting_entry,
   cash_obligation_id, position_obligation_id}

Resolution.to_canonical_dict()
  {type:"cn_a_share_settlement_resolution", schema_version:1,
   venue_id, fill_id, trade_date, next_trading_date,
   position_availability_time, cash_withdrawal_time,
   fill_accounting_entry_hash, obligations}

Failure.to_canonical_dict()
  {type:"cn_a_share_settlement_failure", schema_version:1,
   code:<enum value>, fill_id, venue_id, calendar_id, subject_key}
```

`fill_accounting_entry_hash` 必须等于 `canonical_sha256(query.fill_accounting_entry)`；`ProfilePortOutcome.input_hash` 继续由 generic port 对完整 Query canonical bytes 计算。所有 tuple 保持上述字段语义，Domain value 使用其现有 canonical encoding。

1. Query constructor 只验证字段类型，不把错误 Domain kind 变成 construction exception。`resolve_settlement()` 的 deterministic failure precedence 固定为：`unsupported_venue` → `unsupported_instrument` → `unsupported_currency` → `settlement_identity_mismatch` → `accounting_effect_mismatch` → `calendar_coverage_missing` → `trade_time_not_open`。两个 obligation ID 必须是 caller-generated、彼此不同的 `DomainIdKind.SETTLEMENT`；Adapter 不在缺少 Semantic Run namespace 时发明领域 ID；
2. Predicate-to-code mapping exact 为：`fill.venue_id != model.calendar.venue_id` → unsupported venue；`instrument.instrument_id != fill.instrument_id`、`instrument.instrument_id.venue != fill.venue_id` 或 `instrument.instrument_type != EQUITY` → unsupported instrument；Instrument quote/settlement currency 或 Fill price quote currency 任一不是 CNY → unsupported currency；ID kind 不是 SETTLEMENT 或两个 ID 相同 → settlement identity mismatch；Accounting predicate 任一失败 → accounting effect mismatch；Session failure/无下一 trading row → calendar coverage missing；Session 成功但非 trading/open phase → trade time not open。多缺陷只返回 precedence 中第一个；
3. Failure `subject_key` 固定为稳定 identity：unsupported venue 使用 `fill.venue_id.value`；unsupported instrument/currency、identity mismatch、trade-time failure 和 coverage failure 使用 `fill.fill_id.value`；accounting mismatch 使用 `fill_accounting_entry.journal_entry_id.value`。Failure 不保存 free-form message。Result obligations 顺序固定为 Cash leg、Position leg；
4. `fill_accounting_entry` 是 Adapter 唯一消费的 Fill economic evidence；Adapter 只验证其结构与 Query exact binding，不能仅凭 bare Entry 证明它已进入 authoritative Journal。Caller/G08H 必须保证并在组合证据中验证该 Entry 已包含于所消费 LedgerState 对应的 Journal prefix。Entry 本身必须满足：`entry_type=FILL_BOOKED`、`effective_time == fill.execution_time`、`recorded_at.instant >= fill.execution_time`、account/venue exact 匹配、`source_ids` 是 `{fill.fill_id.value, fill.order_id.value}` 的 exact two-element set（输入顺序无语义）、`fees=()`、`financing=()`，并 exact 含一个 matching `CashBalanceKey/Money` 与一个 matching `PositionBalanceKey/Quantity` change。Position effect 必须保留 Fill Quantity 的 Instrument identity/Scale，且 BUY 等于 `+fill.quantity`、SELL 等于 `-fill.quantity`；Cash effect currency 必须 CNY 且 BUY 为负、SELL 为正。Adapter 直接使用 signed values，禁止用 Fill price×quantity 重算 Notional、Scale 或 rounding；
5. Fill 必须与 supplied `InstrumentDefinition` exact 匹配，且可观察检查仅允许 `InstrumentType.EQUITY`、CNY quote/settlement currency、matching XSHG/XSHE Venue。Fixture 声明普通人民币 A 股是 caller precondition；Stock Connect、margin account、ETF/REIT 等当前 Contract 不可观察的上下文不得产生“已验证”证据；
6. TradingDate 必须通过 G08A concrete SessionModel 在 Fill instant 解析，且 Fill 必须处于 OPEN phase。下一 TradingDate 只能扫描同一 injected Frozen Calendar 中后续 `trading` row；2024-02-09–17 holiday 和 02-18 weekend 必须跳过。Coverage 无法证明下一 TradingDate 时返回 `calendar_coverage_missing`，禁止 extrapolation；
7. `availability_rules(schema)` 不是 ProfilePortOutcome：非 `LedgerSchema` 输入抛 `TypeError`；多 Account、其他 Venue、非 CNY Cash 或缺少 Cash/Position registration 抛既有 `AvailabilityEvidenceError`。它 materialize fixed `MarketSettlementRules(policy_key="equity.cn_a_share.cash.availability.v1", policy_version=1)`，规则严格为：Cash pending receivable tradable=true、withdrawable=false、margin-eligible=false；Tradable/Withdrawable reservation uses 均为 `(cash, fee_reserve)`；Available-margin reservation uses 为空；Position pending receivable sellable=false。Margin Reservation 因没有 owner 而 fail closed；
8. Availability 仍由 generic `AvailabilityProjection` 计算。Ledger total 在 Fill 时立即反映经济 Cash/Position；Projection 只对 pending positive receivable 限制可用性，negative delivery 不二次扣减。Cash-account `available_margin` 维度在本 Gate 只是 generic projection 输出，不授权 Margin；Fixture 固定 cash maturation 前为 CNY 9,000、之后为 CNY 10,200，G08H 的 Account/Risk Policy 必须禁止使用该维度；
9. Frozen fixture 对 XSHG/XSHE 使用 G08A `[2024-02-08, 2024-02-20)` Calendar：初始 CNY 10,000.00、200 settled shares；T 日 BUY 100 @ 10.00、SELL existing 100 @ 12.00，无 Fee/Tax；另有 CNY 200 Cash、CNY 10 Fee Reserve 和 20 shares Sellable Reservation。两次 Fill 后 total Cash=10,200、settled Cash=9,000、tradable Cash=9,990、withdrawable Cash=8,790、available margin=9,000、total Position=200、sellable=80；
10. 在 2024-02-19 00:00 前一 nanosecond，Buy Position 仍 pending；边界应用后 sellable=180。Cash receivable 在 2024-02-19 16:00 前一 nanosecond 仍 pending；边界应用后 settled Cash=10,200、tradable Cash=9,990、withdrawable Cash=9,990、available margin=10,200。Tradable Cash 在 Cash maturation 时不得二次增加；
11. Adapter 不生成 `SettlementEvent`。Fixture 的 caller-owned lifecycle 固定使用 Accounting `SimulationInstant(fill_time, TimelinePhase(50, "accounting"), SourceSequence(1))`，ObligationRecorded 使用 phase `(60, "settlement_recorded")`，同 UTC instant 的 immediate SettlementApplied 使用更晚 phase `(61, "settlement_applied")`；同 phase 的事件使用递增 SourceSequence。不得依赖 `event_id` lexical order 建立因果；early Applied 必须触发 generic lifecycle failure；
12. Fixture 必须先把两个 exact `FILL_BOOKED` Entry append 到 authoritative `AccountingJournal`，由同一完整 Journal cursor/prefix 投影 `LedgerState`，再解析 Settlement；每个 ObligationRecorded Event 的 `source_evidence_hash` 必须等于对应 `canonical_sha256(CnAShareSettlementResolution)`，从而间接绑定 resolution 内的 accounting-entry hash。Accounting phase 必须早于 Settlement Recorded/Applied phase，Availability 只能消费引用该完整 Journal prefix 的 LedgerState。该 Journal-inclusion/order 约束是 G08B fixture 与 G08H caller precondition，不由五类型 SettlementModel seam 单独证明；
13. Fixture 还必须证明四条 obligation 的 recorded/immediate/deferred lifecycle、full replay 与 cursor/resume parity、输入顺序不影响 Book/Rules/Availability hash、Reservation 变化不改变 Settlement state/hash，以及 Settlement obligation 与 Reservation identity/path 永不混用。`SettlementApplied` 只推进 Book/Availability，不创建 Journal Entry；Profile Adapter 不拥有 Event ID、Simulation phase、mutable Book/Ledger/Reservation state 或 Runtime scheduling；
14. XSHG/XSHE 共享 normalized signed amounts、maturation schedule 和 availability arithmetic；因为 Venue/Instrument/Balance identities 不同，SettlementBook、Rules 和 Availability hashes 预期不同。Calendar/session/settlement component digest 必须不同；
15. Component 固定为 `port_type=settlement_model`、`component_key="equity.cn_a_share.cash.settlement.v1"`、`component_version=1`。Digest preimage exact 为 `{type="cn_a_share_cash_settlement_component", schema_version=1, component_key, component_version, algorithm_key="cn-a-share-cash-settlement-availability-v1", session_component_ref=<完整 G08A ProfileComponentRef>, applicability_key="ordinary-rmb-a-share-cny-cash-v1", leg_timing={negative_delivery:"fill-execution-time", positive_position:"next-trading-date-local-00:00", positive_cash:"next-trading-date-local-16:00"}, availability_policy={policy_key:"equity.cn_a_share.cash.availability.v1", policy_version:1, cash={pending_receivable_tradable:true, pending_receivable_withdrawable:false, pending_receivable_margin_eligible:false, tradable_reservation_uses:["cash","fee_reserve"], withdrawable_reservation_uses:["cash","fee_reserve"], available_margin_reservation_uses:[]}, position={pending_receivable_sellable:false}}}`；
16. Concrete package purity test 必须使用 exact import allowlist `{__future__, dataclasses, datetime, enum, typing, unicodedata, zoneinfo, crypto_quant_domain, crypto_quant_trading.ledger, crypto_quant_trading.ports, crypto_quant_trading.settlement}` 加同 package relative `{calendar, settlement}`，其他 import 一律失败。AST scanner 必须解析 `import`/`from import` alias 到 qualified call，并用 mutation cases覆盖 direct/aliased `open`、`builtins`、`io`、`tempfile`、`pathlib`、`os`、`sqlite3`、`subprocess`、`importlib.resources`、`socket`、`http.client`、`urllib`、`requests`、`httpx`、`aiohttp`、`websockets`、`fsspec`、`boto3`、`botocore`、`time`，以及 direct/aliased `datetime.now/utcnow/today`、`date.today`、`time.time/time_ns`。禁止 MarketBundle/Runtime；
17. Fixture 和 Adapter 仅允许 development-grade。Settlement Domain IDs 由 caller/Runtime identity plan 生成；`SettlementEvent.event_id` 是 caller-owned canonical string。Official source URL/document number 只属于 provenance/Acceptance，不进入 result-affecting component digest；G08B 不实现 Fees/Tax、Quantity Lattice、Price Limit、Corporate Action、Registry、Resolver、Runtime scheduling、真实交易或 deployment authorization。

Official primary references：

- SSE《上海证券交易所交易规则（2023年修订）》Rules 3.1.4–3.1.5：`https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/10824490/files/dcbe58edb194451d93f19b1f7dd8fb4c.docx`；
- SZSE《深圳证券交易所交易规则（2023年修订）》Rules 3.1.4–3.1.5：`https://docs.static.szse.cn/www/lawrules/rule/repeal/rules/W020230217564423808793.pdf`；
- 中国结算《证券结算规则》Articles 10–22、45–46：`https://www.chinaclear.cn/zdjs/editor_file/20220620141248275.pdf`；
- 中国结算货银对付改革 2022-12-26 全面实施公告：`https://www.chinaclear.cn/zdjs/gszb/202303/25835600a00f4909a61e16daf4158a62.shtml`；
- 中国结算 2024 春节期间证券资金清算交收安排：`https://www.chinaclear.cn/zdjs/gszb/202402/55414758160a4efdacfb89d6f4a82518.shtml`；
- 证监会《证券登记结算管理办法》Articles 45、50–55：`https://www.csrc.gov.cn/csrc/c101953/c2801304/content.shtml`；
- CSRC JR/T 0300—2023 separate available/withdrawable balance terminology：`https://www.csrc.gov.cn/csrc/c101954/c7445425/content.shtml`。

SSE/SZSE 投教材料中存在当日可用/次日可取的产品示例，但不作为普通 A 股规范依据；G08B 的 retail Tradable/Withdrawable 行为明确属于版本化现金账户系统约定。

G08B 的实现边界如下：

1. `CnAShareCashSettlementModel` 在 concrete profile package 中结构化实现 `SettlementModel`，只接受 XSHG/XSHE、broad EQUITY 和 CNY 可观察上下文；Query constructor 保持 type-only，Model 按冻结 precedence 返回 exactly-one `ProfilePortOutcome`；
2. Adapter 对 `FILL_BOOKED` Entry 做 account、venue、source exact set、Cash/Position cardinality、identity、currency、Scale、signed effect、fee/financing 和 timing 完整绑定；BUY/SELL off-notional sentinel 证明 Cash obligation 逐字使用 Journal Money，禁止从 Fill 重算 Notional；
3. 下一 TradingDate 只扫描 caller-injected G08A Frozen Calendar。Negative delivery 在 Fill instant 完成，positive Position 在下一交易日本地 00:00 成熟，positive Cash 在本地 16:00 成熟；公开 Resolution constructor 同时拒绝非 CNY、同号 legs、重复 ID、跨 Account/Venue、trade-date 和 boundary 矛盾；
4. `availability_rules()` 只 materialize 固定 cash-account policy；pending cash 可交易但不可提现/不可用于 margin，pending position 不可卖，Cash/Fee reservation ownership 与 Margin fail-closed 均由 generic `AvailabilityProjection` 验证；
5. Fixture 严格按 authoritative Journal → full-prefix Ledger → Settlement Resolution → Recorded/Applied events → SettlementBook → Availability 顺序构造。Recorded event source hash 绑定 Resolution；Accounting/Recorded/Applied 使用 phase 50/60/61 和递增 SourceSequence，reverse-lexical Journal/Event IDs 证明不依赖 ID 排序；
6. Frozen journey 证明四条 obligation 的 immediate/deferred lifecycle、`boundary-1ns`/boundary 状态、full replay/resume、Book/Rules/Availability input-order parity、Reservation isolation 和 SettlementApplied 不重复记账；
7. XSHG/XSHE normalized signed economics相同，但 Calendar/Session/Settlement component、SettlementBook、Rules 与 Availability identities 不同。Golden 保存 development-only qualification、caller preconditions、系统 maturity conventions、全部关键对象与 hash；
8. Concrete package 未 root re-export，不修改 generic seams；alias-aware AST mutation contract 拒绝 filesystem、network/provider/process/database/cloud SDK 和 wall clock，并保持 Runtime/MarketBundle/G08C–G08H 语义隔离。

G08B 已冻结在 immutable commit `dc941e960c26db298da9f600d7d747725ee26402`，状态为 `PASSED`。

验证记录：

```text
G08B settlement/availability contract tests                         52 passed
Static A-share settlement/availability golden fixture                1 passed
G08B acceptance JUnit report                                        53 passed
Public API, generic port/settlement and calendar boundaries          50 passed
Full test suite                                                     680 passed
Trading-kernel import boundary                                      PASS (60 files)
mypy                                                                 no issues (8 files)
Primary LSP + pi-lens                                                clean
Multi-agent blocker reviews                                          no unresolved P0/P1
uv lock --check                                                      PASS
Python                                                               3.13.5
```

## 64. G08C Quantity Lattice and Odd Lot Acceptance Card

```yaml
id: G08C
status: PASSED
depends_on:
  - G08A
  - WP-04E
  - WP-05D
  - WP-05G
owner_package: trading-kernel profiles/cn_a_share
public_interface:
  - crypto_quant_trading.profiles.cn_a_share.CnAShareQuantityLatticeFailureCode
  - crypto_quant_trading.profiles.cn_a_share.CnAShareQuantityLatticeQuery
  - crypto_quant_trading.profiles.cn_a_share.CnAShareQuantityLatticeResolution
  - crypto_quant_trading.profiles.cn_a_share.CnAShareQuantityLatticeFailure
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCashQuantityLatticeModel
  - CnAShareCashQuantityLatticeModel.component_ref
  - CnAShareCashQuantityLatticeModel.resolve_instrument
  - structural implementation of crypto_quant_trading.InstrumentModel
  - crypto_quant_trading.QuantityLattice.whole_sell_residual_permitted
  - crypto_quant_trading.PositionSizingAction.SELL_RESIDUAL_COMPONENT
  - crypto_quant_trading.PositionSizingReasonCode.SELL_RESIDUAL_COMPONENT_PERMITTED
  - crypto_quant_trading.PlanningOmissionCode.POSITION_RELATIVE_REACHABILITY_STALE
  - position-relative QuantityLattice schema v2 with schema-v1 hash compatibility
  - static A-share quantity-lattice/odd-lot golden fixture v1
test_commands:
  contract: uv run pytest -q tests/kernel/profiles/cn_a_share/test_quantity_lattice.py
  fixture: uv run pytest -q tests/kernel/profiles/cn_a_share/test_quantity_lattice_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py tests/kernel/ports/test_profile_port_contracts.py tests/kernel/sizing/test_position_sizing.py tests/kernel/sizing/test_position_sizing_golden.py tests/kernel/rebalance/test_rebalance_coordinator.py tests/kernel/market_rules/test_market_rule_evaluator.py tests/kernel/profiles/cn_a_share/test_calendar_session.py tests/kernel/profiles/cn_a_share/test_settlement_availability.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g08c-import-boundary-report.json
fixture_ids:
  - cn-a-share-quantity-lattice-odd-lot-v1
expected_artifacts:
  - tests/fixtures/kernel/profiles/cn_a_share/quantity-lattice-odd-lot-v1.json
  - build/acceptance/g08c-pytest.xml
  - build/acceptance/g08c-import-boundary-report.json
failure_contracts:
  - unsupported-venue-instrument-or-currency-is-accepted
  - ordinary-a-share-or-board-classification-is-claimed-from-unobservable-fields
  - buy-order-lot-is-applied-to-absolute-target-instead-of-buy-delta
  - sell-order-lot-is-modeled-as-arbitrary-one-share-sells
  - legal-whole-residual-sale-is-rejected-by-sizing
  - current-residual-is-split-across-orders
  - exact-reachable-target-is-rounded-away
  - normalized-target-exceeds-approved-notional-without-explicit-hold-dust
  - residual-fail-returns-partial-normalized-or-active-target
  - quantity-lattice-schema-v1-bytes-or-hash-changes-when-new-capability-is-false
  - xshg-and-xshe-component-or-lattice-identities-collide
  - component-digest-contains-source-url-clock-build-attempt-or-profile-parent
  - rebalance-coordinator-rounds-or-resizes-normalized-quantity
  - partial-fill-cancel-replans-position-relative-target-with-stale-reachability
  - odd-sell-is-claimed-end-to-end-approved-without-authoritative-balance-evidence
  - broker-auto-rounding-splitting-retry-or-fill-behavior-is-claimed-as-exchange-rule
  - concrete-profile-reads-network-filesystem-provider-process-database-or-wall-clock
  - concrete-profile-is-root-reexported-or-imported-by-generic-kernel
  - g08d-history-price-limit-session-settlement-fee-tax-or-runtime-semantics-leak
allowed_grade: development
evidence:
  - pytest-report
  - static-quantity-lattice-odd-lot-golden-hash
  - official-rule-notice-and-example-reference-table
  - official-fact-versus-system-sizing-convention-classification
  - xshg-xshe-component-config-lattice-policy-mark-decision-target-and-plan-hashes
  - flat-buy-odd-holding-buy-and-position-relative-sell-arithmetic
  - whole-residual-alone-combined-and-full-close-evidence
  - arbitrary-odd-sell-negative-control
  - unequal-buy-sell-lot-side-selection-control
  - residual-policy-atomic-failure-and-input-order-parity
  - downstream-no-second-rounding-order-plan-evidence
  - current-market-rule-odd-sell-limitation-regression
  - profile-port-outcome-result-and-failure-evidence
  - network-market-bundle-runtime-and-generic-kernel-import-absence
  - import-boundary-report
  - static-type-report
passed_commit: d20e2d252cec1efc566c8bbfee48d52948dc88a3
artifact_hashes:
  tests/fixtures/kernel/profiles/cn_a_share/quantity-lattice-odd-lot-v1.json: sha256:7b6a4e76260955735ea62a81c897dfb11eecc0af89b571143bbfcea244cecd1c
  build/acceptance/g08c-pytest.xml: sha256:dcc042a2d805a7375001493352b43d2d39f88a020dbe949dc9f14f4d7f5dc732
  build/acceptance/g08c-import-boundary-report.json: sha256:cc096b1b0a027ed924a524020d986f5aedafaa91228c360e1b9ae7a4bc042e7f
```

### G08C Acceptance

以下接口、规则分类、Fixture、identity、lifecycle 和 purity contract 在 readiness 阶段已通过最终只读审阅；G08C implementation 逐项保持这些冻结语义：

1. G08C 只增加一个 concrete public seam：`CnAShareCashQuantityLatticeModel`，位置固定在 `crypto_quant_trading.profiles.cn_a_share`，结构化实现既有 `InstrumentModel.resolve_instrument()`。不得增加新的 generic port、partial `MarketSemanticsProfileRegistration` 或 root re-export；`OrderRuleModel` 与历史规则仍属于 G08D。本 Card 同时冻结 `QuantityLattice`、`PositionSizer`、`RebalanceCoordinator` 的 market-neutral backward-compatible extension，但 generic implementation 不得 import、引用或 branch on `cn_a_share` identity；
2. Model 由 `venue_id: VenueId` 和 `notional_scale: Scale` 构造，只允许 `xshg`/`xshe`。Query 只携带 supplied `InstrumentDefinition`；Result 只携带该 Instrument 的 generic static v1 `QuantityLattice` template。`ResidualPositionPolicy`、Sizing `PricePurpose` 和 approved/current/mark evidence 继续由 caller 通过 generic `PositionSizingPolicy`/`InstrumentSizingInput` 提供。未来 G08D/G08H 组合时，Sizing lattice 必须来自 Approved Target instant 的唯一 `OrderRuleSnapshot.quantity_lattice` 或与 template 具有相同 lattice hash，不匹配 fail closed；InstrumentModel result 不是第二个 runtime lattice authority；
3. v1 applicability 仅为 XSHG/XSHE 普通人民币 A 股标准现金竞价。Concrete Model 可观察并验证的只有 matching Venue、broad `InstrumentType.EQUITY`、CNY quote/settlement currency。普通 A 股而非 STAR/ChiNext/ETF/REIT/B 股/Stock Connect、标准竞价而非 after-hours、现金账户、long-only 权限，以及 Fixture 中 current holding 等于 authoritative sellable balance、无 working order/Reservation，全部是 caller/G08H precondition，不得声称由 G08C seam 验证；single-order maximum、board/product-specific quantity cap 与 historical parameter 由 G08D/G08H 拥有；
4. 官方事实固定为：买入申报数量是 100 股或其整数倍；正常卖出数量是 100 股整数倍；若交易所文本所称持有余额 `H` 的完整余股 `r=H mod 100` 位于 `1..99`，该完整 `r` 可单独一次申报或与 100 股整数倍合并一次申报，不得拆分。`H=299` 因此允许 `SELL 99/100/199/200/299`，不允许 `SELL 1/101/198/298`。交易所文本不定义应用系统的 authoritative sellable balance；Fixture 把 current Position 映射为该余额且声明无 Working Order/Reservation，属于 system precondition。“一次性申报”是一张 exchange order，不是 guaranteed one-fill，也不定义 cancel/re-entry；
5. Exchange 文本约束 order quantity，不规定 target-position rounding、最大可达 target 选择、ResidualPositionPolicy、自动卖出全部、自动拆单、retry 或 broker UI。G08C 的“只朝 raw target 单向调整，并选择不超过 raw target 的最大 reachable final Quantity”是 explicit internal toward-zero convention，不冒充交易所事实；
6. Public canonical schema v1 固定为：

```text
CnAShareQuantityLatticeFailureCode
  unsupported_venue | unsupported_instrument | unsupported_currency

CnAShareQuantityLatticeQuery
  instrument: InstrumentDefinition

CnAShareQuantityLatticeResolution
  venue_id: VenueId
  instrument_id: InstrumentId
  quantity_lattice: QuantityLattice

CnAShareQuantityLatticeFailure
  code: CnAShareQuantityLatticeFailureCode
  venue_id: VenueId
  instrument_id: InstrumentId
  subject_key: str

CnAShareCashQuantityLatticeModel
  venue_id: VenueId
  notional_scale: Scale
  component_ref: ProfileComponentRef
  resolve_instrument(query) -> ProfilePortOutcome[CnAShareQuantityLatticeResolution, CnAShareQuantityLatticeFailure]
```

Canonical serialization exact 为：

```text
Query.to_canonical_dict()
  {type:"cn_a_share_quantity_lattice_query", schema_version:1, instrument}
Resolution.to_canonical_dict()
  {type:"cn_a_share_quantity_lattice_resolution", schema_version:1,
   venue_id, instrument_id, quantity_lattice}
Failure.to_canonical_dict()
  {type:"cn_a_share_quantity_lattice_failure", schema_version:1,
   code:<enum value>, venue_id, instrument_id, subject_key}
```

1. Enum value exact 为 `UNSUPPORTED_VENUE="unsupported_venue"`、`UNSUPPORTED_INSTRUMENT="unsupported_instrument"`、`UNSUPPORTED_CURRENCY="unsupported_currency"`。`resolve_instrument()` failure precedence 固定为该顺序；Predicate exact 为 query Instrument venue 不等于 model venue、Instrument type 不是 EQUITY、quote 或 settlement currency 任一不是 CNY。每个 Failure 保存 query `instrument_id` 与 query `venue_id`；subject exact 为 venue failure 的 `venue:<query venue value>`，其他为 `instrument:<str(query instrument_id)>`。Outcome 的 `component_ref` 标识 configured model；多缺陷只返回第一项。Query constructor 只做 type validation；Model constructor 对 unsupported configured Venue 或错误 Scale type 直接拒绝；
2. G08C 对 generic `QuantityLattice` 在现有 `config_hash` 之后增加唯一 dataclass default 字段 `whole_sell_residual_permitted: bool = False`；`QuantityLattice.create(..., whole_sell_residual_permitted: bool = False)` 把它置于 keyword-only 参数末尾。Schema 选择只取决于该字段：false 时 canonical schema、bytes、`config_hash` 和 `lattice_hash` 与既有 schema v1 完全相同且 payload 不出现新字段；true 时 config/value payload 使用 schema v2。true 要求 non-null `sell_lot_units`、`odd_lot_close_permitted=true`、`min_quantity_units=0`、`min_notional.units=0`，否则 construction fail；
3. Concrete lattice exact 为 `lattice_key="equity.cn_a_share.cash.quantity-lattice.v1"`、version 1、`atomic_scale=Scale(0)`、step 1、buy lot 100、sell lot 100、minimum quantity 0、minimum notional `Money(0, model.notional_scale, "CNY")`、odd-lot full close true、whole sell residual true。Scale 0/step 1 是整股 canonical encoding；本 Gate 不发明额外 minimum；
4. 对 capability=true 且 Fixture applicability 内 `H>=0,R>=0` 的 lattice，令 `B=buy_lot_units or step_units`、`S=sell_lot_units`、`r=H mod S`。Branch order 固定为 `H==R` no-op → `R==0` close → `R>H` increase → `0<R<H` decrease。Increase 使用 `F=H+floor((R-H)/B)*B`；decrease reachable candidate 包含 `r+floor((R-r)/S)*S`（当 `R>=r`）与 `floor(R/S)*S`，取不超过 `R` 的最大值。算法只使用整数运算，不先反向交易。`H<0` 或 `R<0` 保持 legacy static-lattice path 不变，Concrete G08C/G08H long-cash applicability 排除这些状态；
5. Enum value exact 为 `SELL_RESIDUAL_COMPONENT="sell_residual_component"` 与 `SELL_RESIDUAL_COMPONENT_PERMITTED="sell_residual_component_permitted"`。Increase delta 必须是 B 的整数倍；decrease delta `Q=H-F` 必须满足 `Q mod S=0`，或在 `r>0` 时满足 `Q mod S=r` 并完整消费余股。`applied_lot_units` no-op 使用 step、buy 使用 B、所有 sell/close 使用 S。Base action 在 `F==R` 时为 EXACT/EXACT_LATTICE，否则为 ROUNDED_TOWARD_ZERO + QUANTITY_STEP + delta-side BUY_LOT/SELL_LOT；non-zero final 使用余股分支时追加新的 action/reason；off-lot `F=0` 只追加 existing ODD_LOT_CLOSE pair。`residual_quantity=R-F` 是 Sizing Residual；
6. Existing `QuantityLattice` schema-v1 golden bytes/hash 必须硬编码回归不变，且 capability=false + odd-lot-close=true 仍不得出现 v2 字段。Mutation controls exact-cover：capability=false legacy `B=S=100,H55,R251→F200`；capability=true `B100,S10,H55,R251→F155,BUY100` 与 sub-lot buy `H55,R56→F55,no order`；`H500,R451→F450,SELL50`；`H55,R49→F45,SELL10`；`H55,R50→F50,SELL5+residual action`；nonzero no-op `H55,R55→F55` 使用 step；`R==r` control `H55,R5→F5,SELL50` 且不带 residual action。Capability=true 分别用两个独立 construction tests 拒绝 `min_quantity_units>0,min_notional=0` 与 `min_quantity_units=0,min_notional.units>0`，并另拒绝 missing sell lot、disabled odd close；legacy exact controls 固定 `H=-55,R=-251,B100,S10→F=-250`、`H=-251,R=-55→F=-50`、`H55,R=-251→F=-250`、`H=-55,R251→F200`，证明 negative/cross-zero 路径逐字不变；
7. Fixture policy 固定 key `equity.cn_a_share.cash.position-sizing.v1`、version 1、PricePurpose VALUATION、TOWARD_ZERO。Success 使用 `CLOSE_IF_PERMITTED`；另有 `FAIL` 和 `HOLD_DUST` controls，policy hash 必须反映选择，任一 failure 不返回 partial normalized/active target；
8. Frozen XSHG `xshg:600000` 使用 CNY 10.00 Mark，XSHE `xshe:000001` 使用 CNY 20.00 Mark，Quantity Scale 0、Money/Price Scale 2。至少 exact-cover：`H0,R0→F0` no-op；`H0,R251→F200,BUY200`；`H55,R251→F155,BUY100`；`H500,R451→F400,SELL100`；`H299,R200→F200,SELL99`；`H299,R100→F100,SELL199`；`H299,R199→F199,SELL100`；`H299,R298→F200,SELL99` 而非 SELL1；`H299,R198→F100,SELL199`；`H299,R98→F0,SELL299`；`H101,R100→F100,SELL1`；`H200,R199→F100,SELL100`；`H200,R0→F0,SELL200`；`H55,R0→F0,SELL55`，并冻结各自 applied lot/action/reason；
9. `FAIL` control 必须证明 legal `H299,R200` 因 raw==final 成功，`H299,R298→F200,residual+98` 则原子失败；另以 `H500,R401→F400,residual+1` 捕获普通 unreachable failure。Buy policy controls 固定 `H55,R251` 在 `CLOSE_IF_PERMITTED`/`HOLD_DUST` 下都得到 F155 但 policy/decision identity 不同，在 `FAIL` 下因 Sizing Residual 96 原子失败；任一 failure 不返回 partial normalized/active target。Forward/reversed Instrument inputs 与 approved targets 产生相同 normalized/active identity；
10. Concrete Model 还须对每个 Venue 接受第二个 opaque Instrument stable key，并接受 `xshg:000001` 与 `xshe:600000` controls，证明既不使用 symbol allowlist 也不从代码推断 Venue/Board；Query/Resolution/Lattice Instrument identity exact 绑定，cross-wired Venue fail closed。XSHG/XSHE scalar economics一致，但 component digest、per-Instrument config/lattice hashes不同；
11. Component 固定 `port_type=instrument_model`、key `equity.cn_a_share.cash.quantity-lattice.v1`、version 1。Digest preimage exact 为 `{type:"cn_a_share_cash_quantity_lattice_component", schema_version:1, component_key, component_version, algorithm_key:"cn-a-share-cash-position-relative-lattice-v1", venue_id, applicability_key:"ordinary-rmb-a-share-cny-cash-v1", notional_scale:model.notional_scale.places, lattice_policy:{atomic_scale:0, step_units:1, buy_lot_units:100, sell_lot_units:100, min_quantity_units:0, min_notional_units:0, odd_lot_close_permitted:true, whole_sell_residual_permitted:true}}`；source URL、clock、build、Attempt、Semantic Run、registry order 和 parent profile digest 不进入；
12. RebalanceCoordinator 必须逐字消费 normalized target，不进行第二次数量舍入。Fixture 至少冻结 BUY 200、BUY 100、SELL 99、SELL 199、SELL 1、SELL 55 的 exact target/current/delta、PositionEffect、reduce-only 和 OrderPlan hash。Position-relative target 绑定 sizing current Quantity 与 lattice hash；G08C static fixture 不模拟 effective-lattice change，该检查属于 G08D/H。Lifecycle matrix exact 为：baseline 未变且 order 消失可正常重发；active/partially-filled compatible remainder exact-cover 时 `ALREADY_COVERED`；cancel-requested 时 `CANCELLATION_PENDING`；target expired 时 `TARGET_EXPIRED`；full fill 已到 target 时 `ALREADY_COVERED` 而非 stale；current 已变化、remainder 已从 working set 消失且未到 target 时一律 `POSITION_RELATIVE_REACHABILITY_STALE="position_relative_reachability_stale"`，即使重算 delta 看似合法。Sell killer 固定 `H299,R199→SELL100` 只成交 1 股并取消剩余后，在 `H298` 不得重发 `SELL99`；Buy killer 固定 `H55,R251→F155,BUY100` 只成交 1 股并取消剩余后，在 `H56` 不得重发 `BUY99`；
13. G08C 不修改 MarketRuleEvaluator 来接受 odd sells。Regression 必须在同一 schema-v2 lattice 下证明普通 `SELL100` CLOSE/reduce-only 获批且无 issue，同时 planner 产生的 `SELL99/199/1/55` 因 quantity-step evidence 被拒绝；缺少 authoritative holding/sellable evidence 记录为 G08D blocker，不得把 Sizing/Planner preservation 宣称为 end-to-end order admission approval；
14. Concrete package purity沿用并强化 G08B alias-aware AST scanner。Per-file allowlist 固定：G08C 新 module 只允许 stdlib `__future__|dataclasses|enum|typing|unicodedata`、`crypto_quant_domain`、`crypto_quant_trading.ports`、`crypto_quant_trading.sizing`；calendar/settlement modules 继续使用各自 G08B allowlist；package `__init__` 只允许 relative exports。Package-wide scanner 拒绝 filesystem、network/provider/process/database/cloud SDK、MarketBundle、Runtime 和 wall-clock direct/aliased access，并额外拒绝 bare `__import__(...)`、assigned alias `loader=__import__; loader(...)`、`builtins.__import__`、aliased builtins import、`importlib.import_module` direct/alias、nonliteral dynamic import、`__builtins__["__import__"]` 和 `getattr(__builtins__, "__import__")`；mutation 至少覆盖动态加载 `time` 与 `urllib.request`。Concrete symbols只从 `profiles.cn_a_share` export，generic root不得 re-export/import；
15. 本 Gate 不拥有历史 effective interval、board/STAR/ChiNext rule、single-order cap、price limit、suspension、T+1、Fee/Tax、Corporate Action、Registry/Resolver、Runtime、MarketBundle source、short/margin 或 deployment authorization。Official source provenance 记录在 `docs/research/cn-a-share-quantity-lattice-primary-sources.md`，不进入 result-affecting digest。

G08C readiness 已由 primary-source research、parallel architecture/mutation/source reviews 和最终 cross-validation 冻结；无未解决 P0/P1 blocker。相关既有回归 115 passed，import boundary PASS（60 files），`uv lock --check` PASS，Python 3.13.5。

### G08C Implementation Acceptance

冻结以下实现边界：

1. `QuantityLattice.whole_sell_residual_permitted=false` 完整保留 schema-v1 canonical bytes、config hash 和 lattice hash；true 才发布 schema v2，并 fail closed 要求显式 Sell Lot、Odd Close 能力和零 Minimum Quantity/Notional；
2. Concrete `CnAShareCashQuantityLatticeModel` 仅位于 `profiles.cn_a_share`，结构化实现既有 `InstrumentModel`。XSHG/XSHE、EQUITY 和双 CNY predicate、failure precedence、subject key、固定 component digest preimage 与完整 A 股 cash template 均由 public value invariants 约束；Generic root 无 concrete re-export/import；
3. PositionSizer 对非负 long-cash applicability 使用 position-relative integer arithmetic。Buy 只按 delta 应用 Buy Lot；Sell 只允许 normal Sell Lot 或一次完整消费 holding residual；negative/cross-zero 与 capability=false 路径保持 legacy quantity、action、reason 和 identity；
4. Frozen matrix exact-cover flat/odd-holding Buy、normal Sell、完整余股单独/合并、invalid odd target、one-share residual、regular/full odd close、unequal Buy/Sell Lot、sub-lot Buy no-op 和 legacy signed controls。`applied_lot_units`、Action、Reason、Sizing Residual 与 final Quantity 全部静态冻结；
5. `FAIL` 对 unreachable residual 原子失败，不返回 partial target；`HOLD_DUST` 与 `CLOSE_IF_PERMITTED` 在可达 Quantity 相同但 policy/decision/normalized identity 不同；forward/reversed target/input 保持同一 canonical identity；
6. RebalanceCoordinator 逐字消费 normalized Quantity，不二次舍入。BUY 200/100 与 SELL 99/199/1/55 的 OrderIntent、PositionEffect、reduce-only、delta 和 plan hash 固定。Position-relative baseline 改变且 remainder 不再由同一 target lineage exact-cover 时返回 `POSITION_RELATIVE_REACHABILITY_STALE`，不得重发 SELL/BUY 99；unchanged、reached、active/partial exact coverage、cancel-pending、expired 和 signed legacy progression 保持各自原语义；
7. MarketRuleEvaluator 不凭 Sizing evidence 放宽 Order admission：SELL100 继续获批，SELL99/199/1/55 继续以 quantity-step 拒绝，直到 G08D 提供权威 holding/sellable evidence；
8. Concrete package purity 使用 per-file import allowlist 与 conservative fail-closed AST scanner，覆盖 bare/assigned/builtins/importlib/`__builtins__`/nonliteral dynamic imports、alias rebinding、annotation、walrus、unpacking、relative depth、filesystem/network/process/provider/database/cloud/clock。Workspace boundary checker同步绑定 assigned/rebound dynamic-import alias，防止 Runtime→Builder 绕过；
9. Static CNY golden 冻结 XSHG 10.00、XSHE 20.00 的 component/lattice/policy/mark/decision/normalized/active/order-plan identities、全部 arithmetic cases、Residual policy outcomes、development-only qualification、caller preconditions 和 G08D/G08H limitations；
10. 本 Gate 未声称 historical effective rule、board/STAR/ChiNext classification、single-order cap、odd-sell end-to-end admission、T+1/Fee/Tax/Runtime 或 deployment authorization。

G08C 的实现已冻结在 immutable commit `d20e2d252cec1efc566c8bbfee48d52948dc88a3`，状态为 `PASSED`。

验证记录：

```text
G08C quantity-lattice contract tests                              70 passed
Static quantity-lattice/odd-lot golden fixture                     1 passed
G08C acceptance JUnit report                                      71 passed
Frozen boundary command                                          142 passed
Full test suite                                                   783 passed
Trading-kernel import boundary                                    PASS (61 files)
mypy                                                               no issues (11 files)
Primary LSP + pi-lens                                              clean
Multi-agent blocker reviews                                       no unresolved P0/P1
uv lock --check                                                    PASS
Python                                                             3.13.5
```

## 65. G08D Historical Order Rules and Price Limits Acceptance Card

```yaml
id: G08D
status: PASSED
depends_on:
  - G08A
  - G08C
  - WP-05G
owner_package: trading-kernel profiles/cn_a_share
public_interface:
  - crypto_quant_trading.OrderRulePositionEvidence
  - backward-compatible crypto_quant_trading.OrderRuleEvaluationInput.position_evidence
  - backward-compatible OrderRuleSnapshot execution-style quantity caps
  - crypto_quant_trading.MarketSessionState.SUSPENDED
  - crypto_quant_trading.MarketRuleIssueCode.MAXIMUM_QUANTITY
  - crypto_quant_trading.MarketRuleIssueCode.INSTRUMENT_SUSPENDED
  - crypto_quant_trading.MarketRuleIssueCode.SELL_RESIDUAL_NOT_PERMITTED
  - crypto_quant_trading.MarketRuleIssueCode.SELLABLE_QUANTITY
  - crypto_quant_trading.MarketRuleDataIntegrityCode.MISSING_POSITION_EVIDENCE
  - crypto_quant_trading.MarketRuleDataIntegrityCode.INVALID_POSITION_EVIDENCE
  - crypto_quant_trading.profiles.cn_a_share.CnAShareBoard
  - crypto_quant_trading.profiles.cn_a_share.CnAShareInstrumentRuleContext
  - crypto_quant_trading.profiles.cn_a_share.CnAShareOrderRuleBook
  - crypto_quant_trading.profiles.cn_a_share.CnAShareOrderRuleQuery
  - crypto_quant_trading.profiles.cn_a_share.CnAShareOrderRuleResolution
  - crypto_quant_trading.profiles.cn_a_share.CnAShareOrderRuleFailure
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCashOrderRuleModel
  - crypto_quant_trading.profiles.cn_a_share.CnAShareBarLimitLiquidityEvaluator
  - structural implementation of crypto_quant_trading.OrderRuleModel
  - static A-share historical-order-rule golden fixture v1
test_commands:
  contract: uv run pytest -q tests/kernel/profiles/cn_a_share/test_order_rules.py tests/kernel/market_rules/test_market_rule_position_evidence.py
  fixture: uv run pytest -q tests/kernel/profiles/cn_a_share/test_order_rules_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py tests/kernel/ports/test_profile_port_contracts.py tests/kernel/market_rules/test_market_rule_evaluator.py tests/kernel/profiles/cn_a_share/test_calendar_session.py tests/kernel/profiles/cn_a_share/test_quantity_lattice.py tests/kernel/profiles/cn_a_share/test_settlement_availability.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g08d-import-boundary-report.json
fixture_ids:
  - cn-a-share-historical-order-rules-v1
expected_artifacts:
  - tests/fixtures/kernel/profiles/cn_a_share/historical-order-rules-v1.json
  - build/acceptance/g08d-pytest.xml
  - build/acceptance/g08d-import-boundary-report.json
failure_contracts:
  - board-or-risk-class-is-inferred-from-symbol-text
  - current-rule-fallback-fills-a-historical-gap
  - overlapping-rule-intervals-are-resolved-by-order
  - known-no-session-is-classified-as-suspension-or-data-missing
  - absent-bar-or-zero-volume-is-classified-as-suspension
  - missing-status-or-previous-close-evidence-is-treated-as-no-trade
  - price-limit-rounding-uses-float-or-bankers-rounding
  - no-limit-listing-phase-is-approved-without-price-cage-semantics
  - execution-style-single-order-cap-is-not-enforced
  - intraday-or-investor-cumulative-cap-is-misrepresented-as-single-order-cap
  - upper-limit-open-buy-or-lower-limit-open-sell-is-filled-from-full-day-volume
  - opposite-direction-limit-open-order-is-blocked
  - odd-sell-is-approved-from-close-effect-target-or-sizing-evidence-alone
  - odd-sell-position-evidence-is-missing-stale-cross-account-or-cross-instrument
  - portfolio-availability-reservation-or-working-order-hashes-do-not-chain
  - residual-component-is-split-or-already-reserved-by-an-active-order
  - odd-sell-exceeds-authoritative-sellable-quantity
  - ordinary-main-board-lattice-diverges-from-g08c
  - order-rule-evaluation-schema-v1-bytes-change-when-position-evidence-is-absent
  - order-rule-snapshot-schema-v1-bytes-change-when-quantity-caps-are-absent
  - concrete-profile-reads-network-filesystem-provider-process-database-or-wall-clock
  - generic-kernel-imports-or-branches-on-cn-a-share-identity
  - fee-tax-corporate-action-runtime-queue-or-deployment-semantics-leak
allowed_grade: development
evidence:
  - pytest-report
  - static-historical-order-rule-golden-hash
  - official-rule-source-note-and-source-document-hashes
  - rule-book-component-and-interval-hashes
  - chi-next-2020-transition-evidence
  - xshg-main-star-xshe-main-chinext-board-cap-evidence
  - price-limit-integer-rounding-and-one-tick-floor-controls
  - suspension-no-trade-data-missing-classification
  - directional-bar-open-limit-liquidity-decisions
  - authoritative-position-reservation-working-order-hash-chain
  - residual-sell-positive-and-killer-controls
  - schema-v1-compatibility-goldens
  - import-boundary-report
  - static-type-report
passed_commit: 9e514025d0973b7bd6ec7c89e03ee172d00fb52a
artifact_hashes:
  tests/fixtures/kernel/profiles/cn_a_share/historical-order-rules-v1.json: sha256:af74733a438d35a6d58712ee8f66f371af87f53dbb2f39692d22eaf5231d817d
  build/acceptance/g08d-pytest.xml: sha256:f81a5d18016de77b6d3127414fb9aa7688635d11c6d5ce53ab5b1f606a0523cd
  build/acceptance/g08d-import-boundary-report.json: sha256:53d3a3342ed9c2a478c585999a031e414dc0ee34e201beb0c17a89c42f90fa39
```

### G08D Acceptance

1. G08D 增加一个 concrete `CnAShareCashOrderRuleModel`，位置固定在 `crypto_quant_trading.profiles.cn_a_share`，结构化实现既有 `OrderRuleModel.resolve_order_rules()`；不得新增 generic port、partial profile registration 或 generic `cn_a_share` branch。一个同 package pure `CnAShareBarLimitLiquidityEvaluator` 只把已解析 Snapshot 与 bar-open observation 转成结构化 conservative decision，不进入 generic root；
2. v1 classification 由 caller-supplied `CnAShareInstrumentRuleContext` 提供，至少 exact 包含 `board=main|star|chinext`、`risk_class=standard`、`listing_phase=seasoned`、context source key/hash。Model 不从 Instrument ID、symbol prefix 或 Venue 猜 Board。Risk-warning、退市整理、IPO 前五交易日、重新上市首日和退市整理首日虽记录于官方来源，但 v1 因缺少累计买入/无涨跌幅价格笼子与临停完整语义而结构化 `unsupported_classification`，不得部分批准；
3. `CnAShareOrderRuleBook` 是 caller-injected finite immutable rule evidence。每个 Band exact 记录 board、Venue、half-open local TradingDate interval、daily-limit `Rate`、price tick、Limit/Market 单笔上限、QuantityLattice template、source key/hash。RuleBook canonical order 后计算 `rule_book_hash`；component digest exact 绑定其 hash。Official URL、下载时间和本地路径只属于 provenance，不进入 result-affecting digest；
4. Frozen historical bands 至少包括：XSHG Main `[2023-04-10, fixture_end)` 10%、1,000,000/1,000,000；XSHG STAR `[2019-07-22, fixture_end)` 20%、100,000/50,000、minimum 200、step 1；XSHE Main `[2023-04-10, fixture_end)` 10%、1,000,000/1,000,000；XSHE ChiNext standard seasoned 在 `[fixture_start, 2020-08-24)` 为 10%、1,000,000/1,000,000，自 `2020-08-24` 为 20%、300,000/150,000。Fixture 不伪造未验证的早期 Risk/IPO interval；
5. Ordinary Main Board Snapshot 的 QuantityLattice 必须逐字等于相同 Instrument 的 G08C template/lattice hash。ChiNext 使用 100-share buy/sell lot、whole-residual capability 和 board-specific lattice key；STAR 使用 step 1、minimum 200、odd full-close capability，不把“至少 200 股”错误建模为 200 的整数倍；
6. Query exact 携带 InstrumentDefinition、G08A `CnAShareSessionResolution`、InstrumentRuleContext、optional TradeStatusEvidence、optional PreviousCloseEvidence 和 `evaluated_at`。Query constructor 只做 type validation，缺失 Evidence 必须到 Model 内形成 canonical failure，不能用 construction exception 隐藏；
7. Known G08A weekend/holiday no-session 是 successful `CnAShareOrderRuleResolution(kind="no_trade", timeline=None)`；TradingDate 内 closed phase 仍可产生唯一 Snapshot，`session_state=closed`；OPEN phase + explicit suspended status 产生 `session_state=suspended`。Session coverage failure、缺少 status/previous-close 或证据 identity/time mismatch 是 failure/data missing，三类不得互换；
8. Model failure precedence exact 为：`unsupported_venue` → `unsupported_instrument` → `unsupported_currency` → `unsupported_board` → `unsupported_classification` → `session_evidence_mismatch` → known no-session result → `missing_rule_interval` → `overlapping_rule_intervals` → `missing_trade_status_evidence` → `invalid_trade_status_evidence` → `missing_previous_close_evidence` → `invalid_previous_close_evidence`。多缺陷只返回第一项；禁止使用 interval insertion order 或 current rule fallback；
9. Previous-close evidence 必须 exact 匹配 Instrument/CNY/Scale，`available_at <= evaluated_at`，并绑定 reference TradingDate 与 source hash。Trade-status evidence 必须 exact 匹配 Instrument/Session/effective interval/source hash。Model 不读取 Bar presence、Volume、provider API、filesystem、network 或 wall clock；
10. Daily limit 只用 typed integer arithmetic：`raw = previous_close × (1 ± ratio)`，按 `RoundingPolicy.HALF_UP` 取至 CNY 0.01 tick；limit 与 previous close 的差绝对值低于一 tick 时使用 previous close ± one tick，lower 低于 one tick 时取 one tick。禁止 float、HALF_EVEN 或隐藏 Decimal context。Snapshot lower/upper、ratio/tick、Band hash 和 previous-close evidence hash 全部进入 golden；
11. Generic `OrderRuleSnapshot` 在现有字段之后增加 optional `max_limit_order_quantity_units` 与 `max_market_order_quantity_units`，默认 `None`。两者都为 `None` 时 config canonical schema v1 bytes/config/snapshot hashes完全不变且 payload 不出现新字段；任一存在时 schema v2，正整数且是 lattice step 的整数倍。Evaluator 对 LIMIT/STOP_LIMIT 使用 limit cap，对 MARKET/STOP 使用 market cap，超过时返回 `MAXIMUM_QUANTITY`；
12. `MarketSessionState.SUSPENDED="suspended"` 与 `MarketRuleIssueCode.INSTRUMENT_SUSPENDED="instrument_suspended"` 是 market-neutral extension。CLOSED 继续只产生 `SESSION_CLOSED`；SUSPENDED 只产生 `INSTRUMENT_SUSPENDED`，不能双报或静默映射；
13. `OrderRulePositionEvidence` canonical v1 exact 包含 `account_id, evaluated_at, instrument_id, portfolio_snapshot, working_orders, working_order_set_hash, reservations, availability, total_quantity, sellable_quantity, quantity_lattice_hash`。Working Orders 只允许 ACTIVE/PARTIALLY_FILLED streams、按 Order ID canonical order，全部 Event time 不晚于 evaluated_at；其 set hash 使用 G08C Rebalance 已冻结的 order-id/stream/state/remaining preimage；
14. Position evidence invariants exact 为：Portfolio timestamp/evaluated_at 相等；Account/Instrument/Scale 全部匹配；Portfolio matching Position quantity 等于 explicit total；Availability matching Position total/sellable 等于 explicit values；`0 <= sellable <= total`；Availability ledger hash 等于 Portfolio journal hash；Availability reservation hash 等于 supplied Reservation state hash；每个 active Working Order 与 ActiveReservation/cursor exact one-to-one，remaining Quantity 与 stream state相等；lattice hash 等于 resolved Snapshot lattice hash；
15. Generic `OrderRuleEvaluationInput` 在现有字段后增加 `position_evidence: OrderRulePositionEvidence | None = None`。None 时 canonical schema v1 bytes/input hash完全不变且不出现字段；non-None 时 schema v2。Regular lot BUY/SELL 的 legacy evaluation 不要求 Position evidence；只有需要 residual/odd-close exception 的 SELL 才进入该证据路径；
16. 对 `whole_sell_residual_permitted=true` 的 non-multiple SELL，令 authoritative total `H`、sell lot `L`、`r=H mod L`、order `Q`。批准 exact 要求 `r>0`、`Q mod L == r`、`Q <= sellable`、PositionEffect=CLOSE、reduce-only=true，并且不存在已消费/保留该 residual 的 active odd SELL。`Q` 可为完整 `r` 或 `r+kL`；拆分 residual、arbitrary odd、超 sellable 或 active odd reservation 分别产生 stable issue；
17. 对 STAR 的 `odd_lot_close_permitted=true` 且 whole-residual capability=false，只有 `H < min_quantity`、`Q == H == sellable` 的 full close 可以豁免 minimum；`H>=200` 的订单遵守 step 1 和 minimum 200。不得把 STAR 规则套为 200-share multiple；
18. Missing position evidence 在 odd path 产生 `MISSING_POSITION_EVIDENCE` DataIntegrityFailure；cross-account/instrument/time/hash/lattice、Portfolio/Availability/Reservation/WorkingOrder chain mismatch 产生 `INVALID_POSITION_EVIDENCE`。证据有效但数量不合法是 MarketRuleRejection，不得把业务拒绝伪装成数据缺失；
19. Frozen ordinary controls 对 H=299、sellable=299 至少证明 SELL99/199/299 获批，SELL1/55/101/198/298 拒绝；sellable=98 时 SELL99 拒绝；已有 active SELL199 residual reservation 时第二张 odd SELL 拒绝；regular SELL100 在无 Position evidence 时继续获批。G08C planner 的 SELL99/199/1/55 中只有与当时 authoritative H/sellable exact 匹配的申请可通过；
20. `CnAShareBarLimitLiquidityEvaluator` input 不包含全天 Volume。Decision precedence exact 为 `data_missing` → `no_trade` → `suspended` → side-sensitive price-limit check → `continue`。Available bar open 等于 upper limit且 Side=BUY 返回 `liquidity_blocked_at_limit`；等于 lower limit且 Side=SELL 同样 blocked；反方向继续。它不声称 Queue 一定无成交，只冻结 `next_eligible_bar_open.v1` 的 conservative no-fill eligibility；
21. Limit liquidity decision exact 绑定 side、bar-open Price、Snapshot hash、observation state 和 decision code。Price identity/currency/scale mismatch 是 data missing/failure；无 daily limit、盘中重新打开、L1/L2 Queue、Limit/Stop/OHLC path、partial fill 与全天 Volume inference 不属于本 Gate；
22. Public canonical Query/Resolution/Failure、RuleBook/Band/Evidence、position evidence 与 liquidity decision 均须有 explicit `schema_version=1`、construction invariants、canonical tuple order 和 content hash。ProfilePortOutcome request/result/failure exact 绑定；Model component key 固定 `equity.cn_a_share.cash.order-rules.v1`、version 1、algorithm key `cn-a-share-historical-order-rules-v1`；
23. Concrete package purity沿用 G08C fail-closed scanner。新 module allowlist 仅包含必要 stdlib、`crypto_quant_domain`、generic `crypto_quant_trading.market_rules|orders|ports|reservations|settlement|sizing` 和 same-package `calendar|quantity_lattice`；拒绝 filesystem、network/provider/process/database/cloud、dynamic import、MarketBundle、Runtime 和 wall clock。Generic kernel 不得 import concrete profile；
24. Static golden 至少冻结 XSHG Main 2024、XSHG STAR 2024、XSHE Main 2024、ChiNext 2020-08-21/2020-08-24 transition、closed/suspended/no-trade/data-missing、rounding sentinels、Limit/Market quantity caps、direction-sensitive limit-open decisions、ordinary/STAR odd-sale evidence、all component/rule/band/timeline/snapshot/evaluation/decision hashes和 development-only limitations；
25. G08D 不拥有 Fee/Tax、Corporate Action、Broker commission、MarketBundle Builder/source adapter、Runtime Engine integration、Queue/Volume Fill、Risk-warning累计买入、无涨跌幅股票价格笼子/临停、Stock Connect、margin/short、Profile composition、真实交易或 deployment authorization。G08H 只可组合已冻结能力，不能补写历史事实。

Official primary references and fact/system classification are frozen in `docs/research/cn-a-share-order-rules-primary-sources.md`。若官方来源证明某条冻结事实错误，必须先把 G08D 退回 DRAFT 并以独立 docs commit 修订。

### G08D Implementation Acceptance

1. `OrderRuleSnapshot` execution-style caps 与 `OrderRuleEvaluationInput.position_evidence` 使用 optional schema-v2 extension；legacy snapshot/evaluation schema-v1 canonical bytes 与固定 hash 保持不变。LIMIT/STOP_LIMIT 和 MARKET/STOP 分别使用对应 cap；
2. `OrderRulePositionEvidence` exact 校验 order Account、evaluated-at、Portfolio/Availability/Reservation/WorkingOrder chain、duplicate Order ID、target Working Order Scale、total/sellable 与 current lattice。Odd residual SELL 缺证据为 DataIntegrityFailure；split、超 sellable 与 active residual reservation 为 stable rejection；
3. Concrete RuleBook/Model 冻结 Main/STAR/ChiNext historical bands、ChiNext 2020-08-24 transition、CNY tick HALF_UP rounding、one-tick floor、single-order caps、G08C Main lattice parity、STAR step-one/minimum-200 和 gap/overlap fail-closed；
4. Known no-session、closed phase、explicit suspension 与 missing status/previous-close 分离。Trade-status effective interval exact 收窄 published OrderRuleInterval，禁止 phase-wide extrapolation；closed phase precedence 高于 supplied suspended status；
5. Limit liquidity Adapter 无 Volume input，按 data-missing → no-trade → suspended → side-sensitive limit check → continue 决策。Corrupt supplied Price 不能被 no-trade/suspended 掩盖；upper-limit BUY/lower-limit SELL blocked，反方向 continue；
6. Concrete package purity allowlist、generic/concrete import boundary、public package exports、source provenance、static golden 和 development-only limitation 均冻结；未增加 Runtime/Builder/network/filesystem/wall-clock 或 deployment authorization。

G08D implementation 已冻结在 immutable commit `9e514025d0973b7bd6ec7c89e03ee172d00fb52a`，状态为 `PASSED`。

验证记录：

```text
G08D contract + static golden JUnit                              18 passed
Frozen public/boundary regression command                       212 passed
Full test suite                                                  801 passed
Trading-kernel import boundary                                   PASS (62 files)
mypy                                                               no issues (3 source files)
Primary LSP + pi-lens                                             clean
Read-only blocker reviews                              all reported P1 fixed
uv lock --check                                                    PASS
Python                                                             3.13.5
```

## 66. G08E Commission and Tax Acceptance Card

```yaml
id: G08E
status: PASSED
depends_on:
  - WP-05H
  - WP-05J
owner_package: trading-kernel profiles/cn_a_share
public_interface:
  - crypto_quant_trading.profiles.cn_a_share.CnAShareFeeTradeMechanism
  - crypto_quant_trading.profiles.cn_a_share.CnAShareFeeRuleSourceRef
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCashFeeRuleQuery
  - crypto_quant_trading.profiles.cn_a_share.CnAShareMarketFeeBand
  - crypto_quant_trading.profiles.cn_a_share.CnAShareMarketFeeRuleBook
  - crypto_quant_trading.profiles.cn_a_share.CnAShareStampDutyBand
  - crypto_quant_trading.profiles.cn_a_share.CnAShareStampDutyRuleBook
  - crypto_quant_trading.profiles.cn_a_share.CnAShareMarketFeeRuleResolution
  - crypto_quant_trading.profiles.cn_a_share.CnAShareStampDutyRuleResolution
  - crypto_quant_trading.profiles.cn_a_share.CnAShareFeeRuleFailureCode
  - crypto_quant_trading.profiles.cn_a_share.CnAShareFeeRuleFailure
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCashMarketFeePolicy
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCashStampDutyTaxPolicy
  - crypto_quant_trading.profiles.cn_a_share.CnAShareFeeReservationBuffer
  - structural implementation of crypto_quant_trading.FeeAssessmentPolicy
  - structural implementation of crypto_quant_trading.TaxPolicy
  - static A-share commission-tax golden fixture v1
test_commands:
  contract: uv run pytest -q tests/kernel/profiles/cn_a_share/test_commission_tax.py
  fixture: uv run pytest -q tests/kernel/profiles/cn_a_share/test_commission_tax_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py tests/kernel/ports/test_profile_port_contracts.py tests/kernel/fee_reservations/test_fee_reservation_estimator.py tests/kernel/fees/test_fee_assessment_engine.py tests/kernel/journal/test_immutable_journal.py tests/kernel/profiles/cn_a_share/test_settlement_availability.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g08e-import-boundary-report.json
fixture_ids:
  - cn-a-share-commission-tax-v1
expected_artifacts:
  - tests/fixtures/kernel/profiles/cn_a_share/commission-tax-v1.json
  - build/acceptance/g08e-pytest.xml
  - build/acceptance/g08e-import-boundary-report.json
failure_contracts:
  - market-or-tax-policy-owns-or-infers-broker-commission
  - account-schedule-is-presented-as-an-exchange-wide-fact
  - current-or-nearest-rule-fallback-fills-a-historical-gap
  - overlapping-rule-intervals-are-resolved-by-container-order
  - unsupported-block-trade-uses-auction-fee-rates
  - unsupported-venue-instrument-or-currency-is-partially-assessed
  - buy-order-stamp-duty-is-applied-or-hidden-as-applied-zero-tax
  - fill-after-a-rule-transition-uses-order-acceptance-time-market-or-tax-rate
  - per-fill-market-or-tax-charge-is-rounded-only-after-cross-fill-aggregation
  - final-order-commission-uses-original-notional-instead-of-actual-fills
  - per-order-minimum-commission-is-repeated-per-fill
  - no-fill-cancel-is-charged-the-minimum-commission
  - reservation-estimate-is-reused-or-journaled-as-final-fee
  - reservation-rounding-buffer-is-missing-underbounded-or-not-bound-to-fill-count
  - actual-fill-count-exceeds-the-reservation-bound-without-failing-closed
  - partial-cancel-reservation-difference-is-not-released
  - fee-arithmetic-uses-float-decimal-context-or-half-even-rounding
  - market-tax-account-band-rule-set-or-basis-identity-is-missing-from-result-or-journal
  - duplicate-final-assessment-or-journal-entry-is-not-idempotently-detected
  - concrete-profile-reads-network-filesystem-provider-process-database-or-wall-clock
  - generic-kernel-imports-or-branches-on-cn-a-share-identity
  - block-trade-b-share-fund-stock-connect-margin-corporate-action-or-deployment-semantics-leak
allowed_grade: development
evidence:
  - pytest-report
  - static-commission-tax-golden-hash
  - official-primary-source-note-and-source-document-hashes
  - market-fee-and-stamp-duty-rule-book-component-band-and-resolution-hashes
  - exact-2023-08-28-asia-shanghai-transition-evidence
  - xshg-xshe-market-fee-parity-and-distinct-source-evidence
  - buy-sell-tax-applicability-evidence
  - reservation-versus-final-partial-cancel-evidence
  - bounded-per-fill-rounding-buffer-and-coverage-evidence
  - per-fill-versus-per-order-rounding-and-minimum-evidence
  - assessment-result-and-journal-rule-identity-chain
  - account-schedule-ownership-and-development-limitation
  - import-boundary-report
  - static-type-report
passed_commit: aa7f38d62524ddd1941d4c7c948eb22317b9bda7
artifact_hashes:
  tests/fixtures/kernel/profiles/cn_a_share/commission-tax-v1.json: sha256:3ef26743bc9cebfe546f77812c6773cbdf3353e0337d03ed512d5f1c396f702b
  build/acceptance/g08e-pytest.xml: sha256:2dd347fafbf97cc6d328a633e4da997e43e6539ba6f3bb012431b685fe064413
  build/acceptance/g08e-import-boundary-report.json: sha256:4935811e0ec0564410ccca6d0b5d289cc03ebaed26279d958a3e963f3ac06cdc
```

### G08E Acceptance

1. G08E 增加同一 concrete `commission_tax` module 下的 `CnAShareCashMarketFeePolicy` 与 `CnAShareCashStampDutyTaxPolicy`，分别结构化实现既有 `FeeAssessmentPolicy.assess_fees()` 与 `TaxPolicy.assess_taxes()`；不得新增 generic port、修改 generic Fee/Tax/Journal arithmetic、创建 partial profile registration 或在 generic root 中增加 `cn_a_share` branch；
2. 两个 Policy 共用 `CnAShareCashFeeRuleQuery`。Query exact 携带 `InstrumentDefinition`、`OrderSide`、`effective_at: UtcInstant` 和 `CnAShareFeeTradeMechanism`；constructor 只做 type validation。v1 Model 支持 `AUCTION`，显式 `BLOCK` 返回 structured unsupported failure，不能静默使用 auction rate；
3. 支持范围 exact 为 XSHG/XSHE、`InstrumentType.EQUITY`、quote/settlement currency 都为 CNY 的 standard domestic cash-auction A-share fixture。Board 不影响本 Gate 冻结费率，但 Model 不能从 symbol prefix 猜 Instrument type、Currency 或交易机制。Stock Connect、Margin/Short、B 股、基金、债券和 after-hours classification 不在 Query 中表达，属于 G08H/Profile composition 的 caller precondition；G08E 不得据此声称支持或自行推断这些上下文；
4. `CnAShareFeeRuleSourceRef` exact 保存 immutable `source_key/source_hash`，hash 必须使用 canonical `sha256:<64 lowercase hex>`；每个 charge component 绑定 canonical non-empty source-ref tuple，以便复合事实保留全部来源。`CnAShareMarketFeeRuleBook` 与 `CnAShareStampDutyRuleBook` 是 caller-injected finite canonical evidence，分别按 Venue 与 half-open `UtcInstant` interval 保存 Band；Band/RuleBook 输入 canonical sort 后计算 content hash，component digest exact 绑定 RuleBook hash、algorithm key、CNY Scale 2 和 `HALF_UP` quantization；
5. Market-fee Band exact 包含三条独立 `fee_fraction`：exchange transaction handling fee、CSRC securities-business regulatory fee、ChinaClear transaction transfer fee。Handling 绑定 venue-specific 2023 notice；regulatory 对 XSHG 绑定 NDRC rate + ChinaClear Shanghai bilateral table，对 XSHE 绑定 NDRC rate + SZSE bilateral collection page；transfer 绑定 ChinaClear 2022 notice。不得在进入 typed rules 前把三者相加为一个匿名 blended rate；Tax Band exact 只有 sell-side securities transaction stamp duty，New Band 同时绑定 2008 baseline 与 2023 halving；
6. Frozen fixture interval 使用 Asia/Shanghai local midnight 对应的 canonical UTC half-open instant：old `[2023-08-25T00:00+08:00, 2023-08-28T00:00+08:00)`，new `[2023-08-28T00:00+08:00, 2023-08-30T00:00+08:00)`。窗口外即 missing coverage，不得把 post-2023 Band 开成无界 current rule；
7. Old Band 对 XSHG/XSHE exact 冻结 handling `0.0487‰` 双边、regulatory `0.02‰` 双边、transfer `0.01‰` 双边、stamp duty `1‰` seller-only；New Band exact 冻结 handling `0.0341‰` 双边、regulatory `0.02‰` 双边、transfer `0.01‰` 双边、stamp duty `0.5‰` seller-only；禁止把 `‰` 误作 `%`；
8. Model failure precedence exact 为 `unsupported_venue` → `unsupported_instrument` → `unsupported_currency` → `unsupported_trade_mechanism` → `missing_rule_interval` → `overlapping_rule_intervals`。多缺陷只返回第一项；gap、overlap 和 unsupported input 都通过 canonical `ProfilePortOutcome.failure` 返回，不读取 current fee page 或 nearest interval；
9. Market resolution exact 产生三条 reservation `ORDER_NOTIONAL/APPLIES` rules、三条 final `FILL/ALWAYS` rules 和一条 final `ORDER/NOT_APPLICABLE` source-coverage rule。Tax resolution exact 对 SELL 产生 reservation `ORDER_NOTIONAL/APPLIES`，对 BUY 产生 `NOT_APPLICABLE`；final Fill rule 始终为 `SELL_ONLY`，final Order rule 为 `NOT_APPLICABLE`；
10. 每条 applicable market/tax rule 使用其自身 `QuantizationPolicy(target_scale=Scale(2), rounding=HALF_UP)`。Final market/tax 只以单个 Fill 为 `FeeAssessmentBasisEvidence.for_fill()` 评估，先对每个 component 每 Fill 量化，再求 Assessment total；禁止跨 Fill 先聚合 market/tax notional 后只舍入一次；
11. Market/tax Policy 不产生 `ACCOUNT_SCHEDULE` rule、minimum 或 `AccountFeeScheduleRef`。Golden 的 caller-supplied development AccountFeeSchedule 独立冻结 `schedule_key=development.cn-a-share.cash-broker.net-commission.v1`、version 1、net broker commission `0.3‰` 双边、terminal Order minimum CNY 5.00，并明确排除 separately modeled market charges/tax；schedule digest preimage exact 为 `{type=development_cn_a_share_cash_broker_net_commission_schedule, schema_version=1, schedule_key, schedule_version=1, commission_rate, minimum_amount, assessment_scale=2, rounding=half_up, excluded_charge_keys=(exchange_handling, regulatory, transfer, stamp_duty)}`。它无真实 broker/provider provenance且始终 development-only；
12. Reservation RuleSet 由 caller 把 active market resolution、active tax resolution、`CnAShareFeeReservationBuffer` rules 和 account schedule rules 显式组合。Buffer exact 绑定同 Query 的 Market/Tax resolution hashes 与 caller-supplied positive `maximum_fill_count`；令 `u=floor(maximum_fill_count/2)` CNY cent，则 market `FLAT_PER_ORDER` buffer 为 `3u` cents，SELL tax buffer 为 `u` cents，BUY tax buffer 为 `NOT_APPLICABLE`。该上界覆盖至多 N 个 Fill 对每 component 独立 HALF_UP 相对 aggregate HALF_UP 的最大正舍入差；实际 Fill 数超过 bound 必须在 canonical publication 前 fail closed；
13. Reservation exact 使用 MarketRuleApproval 的完整获批订单 notional，account minimum 只作用于 commission rule 一次，rounding buffer 不进入 broker minimum scope。Estimate/Proposal 只进入 Resource Reservation，不产生 FeeAssessment、Journal Entry、Ledger fee 或已实现 PnL；Final Fill RuleSet 只包含 active execution-time market rules、tax `SELL_ONLY` rule 和 account `FILL/NOT_APPLICABLE` coverage rule。每个 Fill 必须以其 execution time 重新解析 active Band；Order acceptance time、first Fill rule 或 terminal time 都不能替代后续 Fill 的 rule resolution；
14. Final Order RuleSet 只包含 market/tax `ORDER/NOT_APPLICABLE` coverage rules、account commission `ORDER/ALWAYS` rule 和 `FinalFeeMinimum(basis_type=ORDER)`。只有 terminal Order 可评估；commission notional 是 canonical actual Fill set 的总额，minimum 只应用一次；没有 Fill 的 cancelled Order 产生 zero final assessment，不调用 `FeeChargedJournalTranslator`；
15. Frozen partial-cancel sentinel 使用 `maximum_fill_count=2`：获批 SELL notional CNY 10,000.00，New Band aggregate charges/account minimum CNY 10.64，加 market/tax rounding buffer CNY 0.04 后 reservation CNY 10.68；实际只有两个各 CNY 1,000.00 Fill 后取消。每 Fill market+tax 为 CNY 0.56，两个 Fill 合计 CNY 1.12；Order commission raw CNY 0.60、minimum adjustment CNY 4.40、final commission CNY 5.00；final total CNY 6.12，Reservation terminal state 清零且相对最终费用释放 CNY 4.56；
16. 独立 rounding sentinel 使用获批/最终 notional 都为 CNY 2,000.00、`maximum_fill_count=2` 和两个各 CNY 1,000.00 Fill：未加 buffer 的 aggregate Reservation 为 CNY 6.13，加入 CNY 0.04 buffer 后为 CNY 6.17；final 每 Fill handling 各 CNY 0.03、final total CNY 6.12。Buffer 后 reservation 必须不低于 bound 内任一合法 Fill partition 的 final market/tax/account total；
17. Frozen side/boundary controls 使用 `maximum_fill_count=2` 至少证明：Old Band SELL CNY 10,000.00 reservation CNY 15.83、final single-fill CNY 15.79；New Band SELL reservation CNY 10.68；New Band BUY reservation CNY 5.67、final single-fill CNY 5.64 且没有 applied tax line；exact `2023-08-28T00:00+08:00` 解析 New Band，前一纳秒解析 Old Band；
18. 保持既有 identity split：`FinalFeeAssessmentResult.rule_identity_ids` exact 包含 market/tax component identities、active RuleSet hash、active charge/minimum IDs 和 basis hash；`FeeChargedJournalTranslator` 再把 FeeAssessment ID 与 Fill/Order basis IDs 加入 Journal source IDs。`FeeAssessment.market_fee_rule_id/tax_rule_id/account_fee_schedule_id` 继续保存三类 component/schedule identity，不把账户 schedule 冒充 market/tax identity；
19. 每个 positive Fill/Order Assessment 产生独立 stable Fee Domain ID 和独立 `FeeCharged` Journal Entry。相同 Assessment/Journal identity 的重复应用沿用既有 fail-closed/idempotent Journal contract；不得合并两个 Fill 和一个 Order Assessment 为一条失去 basis provenance 的费用事实；
20. Query、SourceRef、Band、RuleBook、Resolution、`CnAShareFeeReservationBuffer` 和 Failure 均须有 explicit `schema_version=1`、construction invariants、canonical tuple order 和 content hash；`ProfilePortOutcome` 沿用既有无 schema-version 字段的 frozen generic canonical contract，只 exact 绑定 component ref、input hash 与 exactly-one result/failure。Market component key 固定 `equity.cn_a_share.cash.market-fees.v1`、algorithm key 固定 `cn-a-share-historical-market-fees-v1`；Tax component key 固定 `equity.cn_a_share.cash.stamp-duty.v1`、algorithm key 固定 `cn-a-share-historical-stamp-duty-v1`；各 version 1；
21. Component digest preimage exact 为 `{type, schema_version=1, component_key, component_version=1, algorithm_key, rule_book_hash, assessment_scale=2, rounding=half_up}`；Market `type=cn_a_share_cash_market_fee_component`，Tax `type=cn_a_share_cash_stamp_duty_component`，并使用第 20 条各自 key/algorithm。每个 generated market/tax charge-rule ID 使用 canonical tagged hash，tag 分别固定 `cn-a-share-market-fee-rule-v1`/`cn-a-share-stamp-duty-rule-v1`，preimage exact 包含 `{component_key, band_hash, source_refs, charge_key, purpose, basis_type}`；Resolution hash 再绑定 active band hash、生成的完整 rules 和 Query identities，禁止 rule-ID↔resolution-hash 循环。Reservation buffer rule tags 固定 `cn-a-share-market-fee-rounding-buffer-v1` 与 `cn-a-share-tax-rounding-buffer-v1`，preimage 绑定 `{market_resolution_hash, tax_resolution_hash, maximum_fill_count, component_count, buffer_formula, side}`。Account fixture 的 commission/minimum IDs 不使用 market/tax Band preimage：tags 固定 `cn-a-share-development-commission-rule-v1` 与 `cn-a-share-development-commission-minimum-v1`，preimage 分别绑定 `{account_fee_schedule_ref, purpose, basis}` 与 `{account_fee_schedule_ref, charge_rule_id, purpose, minimum_amount}`；
22. Concrete package purity沿用 G08D fail-closed scanner。新 module allowlist 仅包含必要 stdlib、`crypto_quant_domain`、generic `crypto_quant_trading.fee_reservations|fees|orders|ports`；拒绝 filesystem、network/provider/process/database/cloud、dynamic import、MarketBundle、Runtime 和 wall clock。Official URL、下载时间和本地路径只在 research provenance 中，运行时不存在 source fetch；
23. Static golden 至少冻结 exact source-key/hash pairs、XSHG/XSHE old/new Bands、exact transition、BUY/SELL applicability、gap/overlap/unsupported-mechanism failures、RuleBook/component/rule/resolution/RuleSet hashes、`maximum_fill_count=2` buffer identity/amount/coverage、CNY integer rounding、partial/no-fill cancel、Reservation/final split、per-Fill/per-Order assessments、minimum adjustment、Reservation terminal release、Journal source IDs 和 development-only limitations；
24. G08E 不拥有真实 broker schedule/provider statement parity、Block Trade discount、B 股/基金/债券/Stock Connect、VAT、返佣、Margin/Short financing、Corporate Action tax、cost-basis fee allocation、Runtime orchestration、Profile composition、网络 source adapter、真实交易或 deployment authorization。G08H 只能组合本 Gate 冻结能力，不能补写历史费率或账户合同。

Official primary references、fact/account ownership 和 system-convention classification 冻结在 `docs/research/cn-a-share-commission-tax-primary-sources.md`。若官方来源证明任一费率、方向或生效边界错误，必须先把 G08E 退回 DRAFT 并以独立 docs commit 修订；READY 前不得实现，PASSED 时 implementation commit 与 acceptance-record commit 继续分离。

### G08E Implementation Acceptance

1. Concrete finite Market Fee/Stamp Duty RuleBooks 按 XSHG/XSHE 与窄历史 UTC interval fail closed 解析，冻结 2023-08-28 handling/stamp-duty transition、双边 regulatory/transfer fee、SELL-only tax 和 BLOCK/gap/overlap precedence；
2. Query、Failure 与两类 Resolution 保存并重新验证完整 canonical Query；active Band、生成 rules、RuleBook/component/resolution identities 和 canonical order 均防止 same-venue Instrument、mechanism、source、reorder 或 forged-hash 替换；
3. `CnAShareFeeReservationBuffer` 绑定同 Query Market/Tax resolution、`maximum_fill_count` 与公式。N=2 时冻结 market CNY 0.03、SELL tax CNY 0.01 buffer；`require_covers_fills()` 对第三个 Fill fail closed；
4. Frozen reservation controls exact 为 Old SELL CNY 15.83、New SELL CNY 10.68、New BUY CNY 5.67、two-Fill CNY 6.17；final controls exact 为 Old SELL CNY 15.79、New BUY CNY 5.64、partial/two-Fill CNY 6.12；adversarial 200+400 split 证明 unbuffered CNY 8.38 < final CNY 8.39，而 buffered CNY 8.42 覆盖；
5. Partial-cancel state exact 冻结 accepted CNY 10.68、partial CNY 9.00、terminal empty 和相对 final CNY 6.12 的释放 CNY 4.56；no-fill cancel final zero，minimum commission 仅在有 Fill 的 terminal Order 应用一次；
6. Per-Fill market/tax、per-Order synthetic account commission、minimum adjustment、FeeAssessment identity、Journal source IDs 与 duplicate Journal append idempotency 均复用 generic Kernel，无 `cn_a_share` branch、runtime source read 或 deployment authorization；
7. Public export、profile purity allowlist、63-file Import Boundary、static golden、full mypy/LSP/pi-lens 和只读 targeted blocker recheck 均通过。

G08E implementation 已冻结在 immutable commit `aa7f38d62524ddd1941d4c7c948eb22317b9bda7`，状态为 `PASSED`。

验证记录：

```text
G08E contract + static golden                                    16 passed
Frozen public/boundary regression command                       120 passed
Full test suite                                                  817 passed
Trading-kernel import boundary                                   PASS (63 files)
mypy                                                              no issues (63 source files)
Primary LSP + pi-lens                                             clean
Read-only blocker recheck                                          NONE
uv lock --check                                                    PASS
Python                                                             3.13.5
```

## 67. G08F Corporate Action Observation and Entitlement Acceptance Card

```yaml
id: G08F
status: READY
depends_on:
  - G08A
  - WP-06A
  - WP-06B
owner_package: trading-kernel profiles/cn_a_share
public_interface:
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCorporateActionAnnouncementStatus
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCorporateActionSourceRef
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCorporateActionAnnouncementCandidate
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCorporateActionEntitlementBand
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCorporateActionEntitlementRuleBook
  - crypto_quant_trading.profiles.cn_a_share.CnAShareRegisteredPositionSnapshot
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCorporateActionEntitlementQuery
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCorporateActionEntitlement
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCorporateActionFailureCode
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCorporateActionFailure
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCorporateActionEntitlementModel
  - structural implementation of crypto_quant_trading.CorporateActionModel
  - static A-share corporate-action entitlement golden fixture v1
test_commands:
  contract: uv run pytest -q tests/kernel/profiles/cn_a_share/test_corporate_action_entitlement.py
  fixture: uv run pytest -q tests/kernel/profiles/cn_a_share/test_corporate_action_entitlement_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py tests/kernel/ports/test_profile_port_contracts.py tests/market_data/bundles/test_market_bundle_reader.py tests/runtime/timeline/test_deterministic_timeline.py tests/kernel/profiles/cn_a_share/test_settlement_availability.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g08f-import-boundary-report.json
fixture_ids:
  - cn-a-share-corporate-action-entitlement-v1
expected_artifacts:
  - tests/fixtures/kernel/profiles/cn_a_share/corporate-action-entitlement-v1.json
  - build/acceptance/g08f-pytest.xml
  - build/acceptance/g08f-import-boundary-report.json
failure_contracts:
  - plan-only-cancelled-revised-incomplete-or-component-empty-announcement-is-accepted
  - future-lifecycle-date-is-modeled-as-a-premature-market-event
  - announcement-is-visible-before-available-time
  - announcement-available-time-precedes-event-time
  - current-position-ledger-order-fill-or-bar-substitutes-for-r-close-register
  - registered-position-snapshot-is-available-before-eligibility-or-after-capture
  - account-instrument-record-date-or-venue-evidence-mismatch
  - record-date-calendar-is-missing-closed-or-not-post-close
  - current-or-nearest-corporate-action-rule-fills-a-gap
  - overlapping-rule-intervals-are-selected-by-container-order
  - invalid-lifecycle-order-share-rate-basis-or-venue-action-combination-is-accepted
  - negative-fractional-share-or-sub-cent-entitlement-is-locally-rounded
  - late-after-record-announcement-backdates-entitlement
  - later-current-position-recalculates-captured-entitlement
  - entitlement-capture-mutates-journal-ledger-lots-settlement-or-availability
  - market-event-or-register-source-identity-is-missing-from-result
  - concrete-profile-reads-network-filesystem-provider-process-database-or-wall-clock
  - generic-kernel-imports-or-branches-on-cn-a-share-identity
  - profile-composition-claims-unobservable-account-or-distribution-scope-is-qualified
allowed_grade: development
evidence:
  - pytest-report
  - static-corporate-action-entitlement-golden-hash
  - official-primary-source-note-and-source-document-hashes
  - announcement-market-event-causality-and-timeline-parity
  - finite-rule-book-band-component-and-resolution-hashes
  - historical-registered-position-snapshot-hash
  - eligibility-versus-capture-instant-evidence
  - later-position-non-substitution-evidence
  - zero-entitlement-evidence
  - no-accounting-mutation-evidence
  - import-boundary-report
  - static-type-report
```

### G08F Acceptance

1. G08F 只在 `crypto_quant_trading.profiles.cn_a_share.corporate_actions` 增加 concrete Entitlement Model，并结构化实现既有 `CorporateActionModel.apply_corporate_action()`；不得新增 generic port、修改 `MarketEvent` 的 causality contract、创建 partial Profile registration 或在 generic Kernel/Timeline/Ledger 中增加 `cn_a_share` branch；
2. Announcement 是普通 immutable `MarketEvent`。`event_time` 表示公告发布事件，`available_time` 表示首次合法/数据可用时点，未来 Record/Ex/Payment/Listing 日期只作为 payload term；合法 invariant 为 `available_time >= event_time`，且 `available_time < event_time` 必须 fail closed。G08F Candidate 保存 Event 的完整 `timeline_instant = SimulationInstant(available_time, phase, source_sequence)`，visibility/capture 比较使用完整总序而不只比较 UTC instant。Golden 必须通过既有 `InMemoryMarketBundleReader` 与 `DeterministicTimeline` 证明 available boundary 前不可见、边界时可见、不同 reader/timeline batch size 与输入顺序产生相同 Event ID/hash 序列；
3. Trading-kernel concrete Model 不导入 `crypto_quant_market_data` 或 `crypto_quant_backtest`，也不直接消费 `MarketEvent`。Caller/G08H 将已验证 Event payload 映射为 `CnAShareCorporateActionAnnouncementCandidate`；G08F golden exact 绑定 Candidate hash 与 source MarketEvent ID/hash，但跨 Package handoff和 complete closed revision-set validation 属于 G08H/Profile composition。G08F 只验证 supplied Candidate 自身的 revision identity，并拒绝 non-null supersession reference；
4. `CnAShareCorporateActionAnnouncementStatus` enum values exact 为 `FINAL_IMPLEMENTATION`、`PLAN_ONLY`、`CANCELLED`。`CnAShareCorporateActionAnnouncementCandidate` exact 保存 caller-owned canonical non-empty NFC `corporate_action_id`、`InstrumentDefinition`、status、announcement event/source/revision identity、`event_time: UtcInstant`、`announcement_available_at: SimulationInstant`、Record/Ex terms、conditional Payment/Listing terms、可选 CNY cash-per-share、bonus-share Rate 与 capitalization-share Rate。Cash component 要求 Payment date；bonus/capitalization component 要求 Listing date；所有 final Action 要求 Ex date。Bonus/Capitalization Rate 的 basis exact 固定 `shares_per_share`。Frozen v1 的 declared Ex date、适用的 Payment date 和适用的 Listing date 必须等于 G08A finite Calendar 中 Record 后首个 known TradingDate；不得因字段缺失自行推导日期。Constructor 只做 typed/canonical validation；只有 `FINAL_IMPLEMENTATION`、component-required lifecycle terms、合法 lifecycle order/rate basis、每个 supplied distribution component strictly positive、至少一个 component present、`supersedes_revision_id=None` 的 Candidate 可成为 authority；plan-only、cancelled 或 supplied revision chain 在 v1 structured fail closed；
5. Model 可直接验证的 supported scope exact 为 XSHG/XSHE、`InstrumentType.EQUITY`、quote/settlement CNY。XSHE 支持 final cash/bonus/capitalization terms；XSHG v1 只支持 cash distribution，因 reviewed current Shanghai guide 的 share-listing schedule provenance 未完全消歧，任何 XSHG bonus/capitalization component 返回 `UNSUPPORTED_VENUE_ACTION_COMBINATION`，不得套用 XSHE 或推断 R+1。InstrumentDefinition/Candidate 无法表达 ordinary-vs-preferred、cash-auction mechanism、B/H classification、Stock Connect、margin/short、lending/repo、pledge/freeze、restricted/pre-IPO shares、differential distribution、issuer self-distribution、rights issue、merger、capital reduction、reverse split 或 generic split classification；这些全部属于 G08H/Profile composition caller precondition；
6. `CnAShareCorporateActionSourceRef` 使用 canonical NFC trimmed `source_key` 与 `sha256:<64 lowercase hex>`。XSHG Band exact 绑定 SSE 2026 Trading Rules、SSE Distribution Guide Document 5、SSE Announcement Format 36 和 ChinaClear Shanghai Issuer Guide；XSHE Band exact 绑定 SZSE 2026 Trading Rules、SZSE Announcement Format 7 和 ChinaClear Shenzhen Issuer Guide。source key/hash pairs 必须与 `docs/research/cn-a-share-corporate-actions-primary-sources.md` 一致；
7. `CnAShareCorporateActionEntitlementRuleBook` 是 caller-injected finite canonical evidence，按 Venue 与 Record eligibility UTC instant 保存 half-open Band。Frozen coverage exact 为 `[2026-07-06T00:00:00+08:00, 2026-07-31T00:00:00+08:00)`；successful resolution 的唯一 selected Band 必须 exact 使用这两个 bounds，singleton extended/shifted Band 也按 `MISSING_RULE_INTERVAL` fail closed。窗口外、gap 或 overlap 不使用 current/nearest rule 或 container order；
8. Record/Eligibility Instant exact 为公告 Record TradingDate 的 XSHG/XSHE local 15:00 session-close boundary，使用 `TimelinePhase(rank=100, code=corporate_action_record)` 与 `SourceSequence(0)`。Model 必须通过 caller-injected G08A finite Calendar/Session Model 证明该日是同 Venue known Trading Day 且边界进入 `POST_CLOSE`。这是 engine ordering convention，不声称 ChinaClear 在 15:00 完成登记；
9. `CnAShareRegisteredPositionSnapshot` 是唯一 entitlement quantity authority，exact 保存 caller-owned canonical snapshot ID、register series/revision identity、`supersedes_revision_id`、account、`PositionBalanceKey`、Record/Eligibility Instant、available `SimulationInstant`、non-negative Scale-0 registered Quantity、source key/hash 与 snapshot hash。Snapshot 可以在 eligibility 后才可用，但不能在 eligibility 前声称 register complete，也不能晚于 Query `captured_at`；G08F 拒绝 supplied non-null supersession reference，complete closed register-revision-set validation 属于 G08H/Profile composition。Portfolio/Ledger current Position、Availability、Order、Fill、Target 或 Bar 不能替代 Snapshot；
10. `CnAShareCorporateActionEntitlementQuery` exact 保存 Instrument、account、optional Candidate、optional registered snapshot 和 `captured_at: SimulationInstant`。缺 Announcement 或 Snapshot 必须返回 structured failure；`position_key.account_id == snapshot.account_id == query.account_id`；Candidate、Snapshot 与 Query 的 Venue/Instrument/Record instant 必须 exact 一致。Announcement、Snapshot 与 capture 的 availability 比较使用完整 `SimulationInstant` total order；`captured_at` 不得早于 Announcement availability、eligibility 或 Snapshot availability；Announcement available after eligibility is `LATE_ANNOUNCEMENT`，不得 backdate；
11. Entitlement exact 保存 component/band/Candidate/source Event/snapshot identities、account/position key、eligibility instant、captured-at、registered quantity、gross cash、bonus quantity 和 capitalization quantity。后续当前 Position、Ledger 或 Snapshot 不得重算同一 result；相同 canonical input/hash 返回相同 result。G08F 只验证单个 Query 内的 ID/hash consistency；`corporate_action_id` uniqueness scope 为 `(venue_id, instrument_id, corporate_action_id)`；`snapshot_id` scope 为 `(account_id, position_key, snapshot_id)`；register revision scope 为 `(account_id, position_key, register_series_id, revision_id)`。跨 Query conflicting reuse 或 omitted later revision 统一由 G08H/Profile-composition identity-history validation fail closed；
12. Cash entitlement只支持 strictly positive supplied CNY Scale 2 component 与 exact arithmetic；share ratios 使用 basis exact 为 `shares_per_share` 的 strictly positive typed `Rate`，并只接受 exact integer Scale-0 delivered quantity sentinel；registered quantity 允许 zero 但禁止 negative。任何 unsupported Rate basis、negative term/quantity、sub-cent cash 或 fractional share result 均 structured fail closed，不得发明 floor、half-up、pro-rata、cash-in-lieu 或 ChinaClear population/random allocation；
13. Zero registered quantity 产生 canonical zero-entitlement result，而不是缺失 evidence。Frozen XSHE control 必须证明 Account A Record quantity `700` 产生 gross CNY `70.00`、bonus `70`、capitalization `140`；Account B Record quantity `0` 在 Ex date 后买入 `500` 仍保持 zero entitlement；
14. Frozen XSHG cash-only control 必须证明 Record quantity `1,000` 产生 gross CNY `200.00`，之后当前持仓变为 zero 也不改变 entitlement；
15. G08F 只捕获 gross entitlement，不产生 `CORPORATE_ACTION_ENTITLEMENT_BOOKED`、Position adjustment、Cash payment、Tax/withholding、Journal Entry、Ledger/Lot/Settlement/Availability mutation。G08G 才能在其独立 READY/PASSED contract 下翻译 account lifecycle；
16. Candidate、SourceRef、Band、RuleBook、Registered Snapshot、Query、Entitlement 和 Failure 均使用 explicit `schema_version=1`、canonical tuple order 与 content hash。`type` literal exact 为 SourceRef `cn_a_share_corporate_action_source_ref`、Band `cn_a_share_corporate_action_entitlement_band`、RuleBook `cn_a_share_corporate_action_entitlement_rule_book`、Candidate `cn_a_share_corporate_action_announcement_candidate`、Snapshot `cn_a_share_registered_position_snapshot`、Query `cn_a_share_corporate_action_entitlement_query`、Entitlement `cn_a_share_corporate_action_entitlement`、Failure `cn_a_share_corporate_action_failure`。Canonical preimage exact 分别为：SourceRef `{type,schema_version,source_key,source_hash}`；Band `{type,schema_version,venue_id,effective_start,effective_end,source_refs}`；RuleBook `{type,schema_version,bands}`；Candidate `{type,schema_version,corporate_action_id,instrument,status,event_id,event_hash,event_time,announcement_available_at,revision_id,supersedes_revision_id,record_date,ex_date,payment_date,listing_date,cash_per_share,bonus_rate,capitalization_rate,source_refs}`；Snapshot `{type,schema_version,snapshot_id,register_series_id,revision_id,supersedes_revision_id,account_id,position_key,eligibility_instant,available_at,registered_quantity,source_ref}`；Query `{type,schema_version,instrument,account_id,announcement,snapshot,captured_at}`；Entitlement `{type,schema_version,component_ref,query,active_band,band_hash,query_hash,candidate_hash,event_id,event_hash,snapshot_hash,account_id,position_key,eligibility_instant,captured_at,registered_quantity,gross_cash,bonus_quantity,capitalization_quantity}`；Failure `{type,schema_version,component_ref,query,query_hash,code,subject_ids}`。Entitlement constructor 必须从 embedded Query/active Band 重算并验证 Query/Band/Candidate/Event/Snapshot/account/position/instant/numeric identities；Failure constructor 必须从 embedded Query 重算 query hash 与 frozen subject IDs。每个 Failure 的 ordered `subject_ids` exact 固定为 `(code.value, candidate.corporate_action_id or "missing-corporate-action", snapshot.snapshot_id or "missing-register-snapshot", query.account_id, str(query.instrument.instrument_id))`。`ProfilePortOutcome.input_hash` exact 为 Query hash；Failure 和 Result 都绑定同一 component ref 与完整 Query identities；
17. `CnAShareCorporateActionFailureCode` enum 与 first-failure precedence exact 为：`MISSING_ANNOUNCEMENT` → `UNSUPPORTED_VENUE` → `UNSUPPORTED_INSTRUMENT` → `UNSUPPORTED_CURRENCY` → `UNSUPPORTED_ANNOUNCEMENT_STATUS` → `UNSUPPORTED_ANNOUNCEMENT_REVISION` → `INVALID_ANNOUNCEMENT_CAUSALITY` → `MISSING_DISTRIBUTION_COMPONENT` → `MISSING_LIFECYCLE_TERM` → `INVALID_LIFECYCLE_ORDER` → `UNSUPPORTED_DISTRIBUTION_RATE_BASIS` → `UNSUPPORTED_VENUE_ACTION_COMBINATION` → `NON_POSITIVE_DISTRIBUTION_TERM` → `ANNOUNCEMENT_NOT_AVAILABLE` → `LATE_ANNOUNCEMENT` → `MISSING_RULE_INTERVAL` → `OVERLAPPING_RULE_INTERVALS` → `INVALID_RECORD_SESSION` → `MISSING_REGISTERED_POSITION` → `UNSUPPORTED_REGISTER_REVISION` → `ACCOUNT_MISMATCH` → `INSTRUMENT_MISMATCH` → `RECORD_INSTANT_MISMATCH` → `INVALID_REGISTER_CAUSALITY` → `REGISTER_NOT_AVAILABLE` → `NEGATIVE_REGISTERED_QUANTITY` → `UNSUPPORTED_CASH_PRECISION` → `UNSUPPORTED_FRACTIONAL_SHARE`。多缺陷只返回第一项；Constructor type/canonical errors 不冒充 business failure；
18. Component key 固定 `equity.cn_a_share.corporate-action-entitlement.v1`、version 1、algorithm key 固定 `cn-a-share-record-register-entitlement-v1`。Component digest exact 绑定 RuleBook hash、G08A Session component digest、record phase convention、supported numeric policies 与 development-only grade；
19. Concrete purity沿用 G08D/G08E scanner，只允许必要 stdlib、`crypto_quant_domain`、generic `crypto_quant_trading.ports` 与 sibling G08A calendar contract；拒绝 filesystem、network/provider/process/database/cloud、dynamic import、MarketBundle/Runtime import 和 wall clock。Official URL、本地下载和 retrieval time 只属于 research provenance；
20. Static golden 至少冻结 exact official source refs、finite Bands、component/rulebook/band hashes、enum values/failure precedence、embedded Query/active-Band identity validation、Announcement Candidate/Event identity、available boundary、Record phase、next-known-TradingDate lifecycle validation、`shares_per_share` basis、XSHG share-distribution rejection、registered snapshot revision identity、XSHE 700/0 与 XSHG cash-only 1000 controls、exact-window/gap/overlap、missing/revised/cancelled/late/mismatched/negative/fractional/sub-cent failures、later-position non-substitution、Timeline page/batch parity 和 no-mutation evidence；
21. G08F 始终 development-grade、`deployment_authorized=false`，不拥有 Strategy-facing ObservationView、G11 point-in-time adjusted series、MarketBundle Builder/source adapter、Runtime scheduling、Corporate Action payment/adjustment/tax、real account register provider parity、真实交易或部署授权。

Official source facts、canonical source identities、fixture dates、system conventions 和 G08G blockers 冻结在 `docs/research/cn-a-share-corporate-actions-primary-sources.md`。若官方来源证明 Record eligibility、supported action classification 或 source identity 错误，必须先把 G08F 退回 DRAFT 并以独立 docs commit 修订；READY 前不得实现，PASSED 时 implementation commit 与 acceptance-record commit 继续分离。

## 68. G08G Corporate Action Adjustment and Payment Readiness Blockers

G08G 保持 `DRAFT`。在以下 blockers 全部冻结前不得实现：

1. Immutable Accounting Journal 与 Generic Ledger 必须拥有 typed Position Lot create/replace/close effects；当前 Generic Ledger 明确拒绝 Position lots，Runtime mutable `lot_books` 不是权威 replay source；
2. `PositionLot` 必须增加可精确守恒的 authoritative total Cost Basis；仅有 fixed-scale `unit_cost` 无法对 3-for-2 等 repeating ratio 保证总 Cost Basis exact 不变；
3. Cash Fill accounting 与 Corporate Action adjustment 必须共用同一 replayable Lot-effect contract，并证明 full replay、prefix/resume、duplicate idempotency 与 conflict rejection；Account-level entitlement 即使为整数也可能在多个 Lot 间产生 fractional allocation，因此 READY 前必须冻结 authoritative per-Lot allocation evidence，或将 v1 收窄为 exactly-one eligible Lot 并对多 Lot fail closed；
4. 新增股份的 sellability/settlement 与支付现金的 tradable/withdrawable/margin availability 必须显式冻结，不能因 Ledger balance 变化而隐式全部可用；
5. Fractional share 必须有 authoritative delivered-quantity evidence；Shanghai sub-cent cash、延迟/暂停支付和 self-distribution 需要独立 facts；
6. G08E 明确不拥有 Corporate Action tax。G08G 仍拥有 Corporate Action tax disposition/translation，但 READY 前必须冻结 typed disposition（至少区分 `NOT_APPLICABLE`、`APPLIED`、`DEFERRED_UNSUPPORTED`）及 owner：G08G 产生 account-tax disposition，G08H/Runtime composition 对 `DEFERRED_UNSUPPORTED` 后续 taxable transfer fail closed。若不冻结该 guard，G08G v1 必须收窄为有明确 `NOT_APPLICABLE` 证据的 gross payment，并排除普通个人 deferred-tax case；
7. Ex/Effective/Payment/Listing trigger identity 与 revised/suspended lifecycle evidence必须独立于 Entitlement。Entitlement 不得自动推导支付或调整；
8. Raw tradable prices 保持不变。Ex reference price 只能进入 Market Rule/reference metadata，不能 retroactively rewrite OHLC、Fill 或 accounting price；
9. 完整成功 Fixture、精确验收命令、public interface、failure precedence、canonical identity chain 和 artifact list 仍未冻结。

## 69. PASSED 记录格式

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
