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

## 44. PASSED 记录格式

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
