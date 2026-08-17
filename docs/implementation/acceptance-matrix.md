# Backtest Work Package Acceptance Matrix

状态：Draft governance contract。此文件不自动授权实现；只有状态为 `READY` 且用户明确要求开始的 Work Package 才允许进入实现。

关联文档：

- `docs/architecture/backtest-system-design.md`
- `docs/implementation/target-driven-bar-v1-plan.md`
- `docs/implementation/plans/README.md`

本文件在计划拆分迁移期间仍是唯一 Gate 状态来源。子计划不得维护第二份独立状态；迁移规则见上述 plans README。

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
| G08F | PASSED | trading-kernel profiles/cn_a_share | G08A, WP-06A, WP-06B | none |
| G08G | PASSED | trading-kernel profiles/cn_a_share | G08F, G03 | none |
| G08H | PASSED | backtest-runtime composition + tests/support + parity tooling | G08A–G08G, G09H, WP-00C | none |
| G09A | PASSED | trading-kernel derivatives | G03 | none |
| G09B | PASSED | trading-kernel derivative accounting | G09A, G03 | none |
| G09C | PASSED | trading-kernel funding eligibility | G09A, G09B, WP-06A, WP-06B | none |
| G09D | PASSED | trading-kernel financing/accounting | G09B–G09C | none |
| G09E | PASSED — immutable commit `e1e4c810b67f8f911b33ef8d7302f33933fc1e32` | trading-kernel margin requirement | G09A | none |
| G09F | PASSED — immutable commit `107b41aafee00195ec0ae0031800a1409e016264` | trading-kernel account margin projection | G09B, G09E, WP-05B | none |
| G09G | PASSED — immutable commit `1a8428530133a7c9173dd9afc800d7dd5e8d304e` | backtest-runtime liquidation audit | G09E–G09F | none |
| G09H | PASSED — immutable commit `e0f2bc767dc87513d562becd9907262628b788e6` | tests/support + profile composition | G09A–G09G | none |
| G10A | PASSED — immutable commit `613c319b2dbba9962d4867dcfb3d1b19067d16cf` | trading-kernel profiles/binance_usdm | G09H | none |
| G10B | PASSED — immutable commit `11072289a9dda708a185ae2edcbf5fcdf0c7bd55` | trading-kernel profiles/binance_usdm | G10A, WP-05G | none |
| G10C | PASSED — immutable commit `50fa838f901385498ce18d65a897d4eb1dc31337` | trading-kernel margin requirement + profiles/binance_usdm | G10A, G09E | none |
| G10D | PASSED — immutable commit `790469d80ddcf3797f03c96c975b77d75a3d49a5` | trading-kernel profiles/binance_usdm | G10A, WP-03C | none |
| G10E | PASSED — immutable commit `195265b1ed830e62b91882ff315b115e7ac80597` | trading-kernel profiles/binance_usdm | G09C–G09D, G10D | Funding source fixtures |
| G10F | PASSED | trading-kernel profiles/binance_usdm | WP-05H, WP-05J, G09F, G10A | Fee/account fixtures |
| G10G | PASSED — immutable commit `12286dbf6b7289fcb2f6069c46fc648d8f5a5be0` | backtest-runtime composition | G10A–G10F | Resolved profile E2E |
| G10H | PASSED — immutable commit `468c91ad3fdbad221c959182f8751300f20a2424` | parity tooling | G10G, WP-00C | none |
| G11A | PASSED — immutable commit `72fe31f5b10d785340b11ca0fd3d0fec8c1c4a34` | backtest-runtime observations | G07, WP-06A | none |
| G11B | PASSED | backtest-runtime observations | G11A | none |
| G11C | PASSED | backtest-runtime observations | G11A–G11B | Universe fixtures |
| G11D | PASSED | backtest-runtime observations | G11A–G11B | Bar/window fixtures |
| G11E | PASSED | backtest-runtime strategy | G11B, G11D | Schedule/warmup fixtures |
| G11F | PASSED | backtest-runtime strategy | G02 | State/checkpoint fixtures |
| G11G | PASSED | backtest-runtime strategy | G11F | Random stream fixtures |
| G11H | PASSED | backtest-runtime strategy | G11B, G11F | Model revision fixtures |
| G11I | PASSED | backtest-runtime strategy | G11A–G11H, G04 | Invocation/batch fixtures |
| G11J | PASSED | parity tooling | G11I, G07 | Dual-entry parity |
| G12A | PASSED | market-bundle-builder | G00 | SourceSnapshot contract |
| G12-ACQ-TOOLS-V1 | PASSED — immutable commit `6f0bd99a93a349924996eb26708fbb0ac6fecf17` | Backtest tools/acquisition | G12A | none |
| G12B | PASSED | market-bundle-builder | G12A, G02 | Normalization fixtures |
| G12C | PASSED | market-bundle-builder | G12B | Manifest/validation fixtures |
| G12D | PASSED | market-bundle-builder + market-data-contracts | G12C | none |
| G12E | PASSED | market-data-contracts | G12D, WP-06A | none |
| G12F | PASSED | parity tooling | G12E, G07 | none |
| G12G | PASSED | market-bundle-builder | G12B–G12C | Bar aggregation fixtures |
| G12H | DRAFT | market-bundle-builder validation | G12C | Rule coverage fixtures |
| G12I | DRAFT | market-bundle-builder validation | G12C, G12G | Real profile-purpose, provider/calendar availability, and terminal-set closure evidence |
| G12J | DRAFT | trading-domain schema migration | real old artifact | No real source/target schema yet |
| G12K | DRAFT | market-bundle-builder validation | G12C | Universe/corporate action coverage |
| G12L-* | DRAFT | market-bundle-builder source adapter | G12A–G12K as applicable | Concrete provider/dataset/version, real raw fixtures, mapping and closure evidence |
| G12L-BINANCE-USDM-MARK-PRICE-KLINES-V1 | PASSED — immutable commit `47d59e40081555ab9b555c3e632070a517509436` | market-bundle-builder Binance USD-M source slice | G10D, G12A–G12D | none |
| G12L-BINANCE-USDM-AGGTRADES-V1 | PASSED — immutable commit `981429b4f0ff5fa219ccc8bc991458072b025bf8` | market-bundle-builder Binance USD-M source slice | G10D, G12A–G12D | none |
| G12L-BINANCE-USDM-FUNDING-RATE-V1 | PASSED — immutable commit `ebd91f746c4a065ca06dba89d847e7d41ab06331` | market-bundle-builder Binance USD-M source slice | G10E, G12A–G12D | none |
| G12L-BINANCE-USDM-FUNDING-HISTORY-V1 | DRAFT / BLOCKED | market-bundle-builder Binance USD-M source slice | G10E, G12A | Immutable provider revision/correction closure |
| G12L-TUSHARE-CN-A-SHARE-DAILY-LISTING-V1 | DRAFT / BLOCKED | market-bundle-builder China A-share source slice | G12A, G12-ACQ-TOOLS-V1 | Session-time, decimal/unit mapping, provider revision and listing-history authority |
| G12M-* | DRAFT | backtest-runtime qualification | market-specific G12L, G07–G10 | Per-market qualification matrix |
| BT-GAP-01 | PASSED — immutable commit `f2440f9658fbe2ae1cf0016a78c44e4230995394` | trading-domain | WP-02E, Platform BT-PORT-01 | none |
| BT-GAP-02 | PASSED — immutable commit `39863c58ace1d996f3e814835836ec46e2aa3794` | backtest-runtime facade | BT-GAP-01, G07, BT-GAP-02A, BT-GAP-04 | none |
| BT-GAP-02A | PASSED | backtest-runtime composition | G07, G08H, G10G, BT-GAP-02B, BT-GAP-02C | none |
| BT-GAP-02B | PASSED — immutable commit `9f321780bb2e831bac521722c04af82adbd8e40e` | backtest-runtime execution inputs | BT-GAP-01, G03, G07, G11I, G12E, BT-GAP-07, PLAT-REC-03 | none |
| BT-GAP-02C | PASSED | backtest-runtime execution closure | BT-GAP-02B, G07, G08H, G10G, G12E | none |
| BT-GAP-03 | PASSED — immutable commit `dfcd49508854abcb41702b7dbd9acee535608515` | backtest-runtime verified repository | BT-GAP-02, BT-GAP-05, BT-GAP-06, BT-GAP-07 | none |
| BT-GAP-04 | PASSED — immutable commit `c3257643d6911bd3b63efac0899aa04d47397b05` | backtest-runtime | BT-GAP-01, G07, Platform BT-PORT-01 | none |
| BT-GAP-05 | PASSED — immutable commit `39863c58ace1d996f3e814835836ec46e2aa3794` | backtest-runtime analysis runtime | BT-GAP-01, BT-GAP-04, BT-GAP-06, G07 | none |
| BT-GAP-06 | PASSED | backtest-runtime analysis schema | BT-GAP-01, BT-GAP-04, G07 | none |
| BT-GAP-07 | PASSED — immutable commit `029ac43f6d781567cd0742594ca82c181ead0a6d` | backtest-runtime structural read port | BT-GAP-01, WP-02E | none |
| BT-GAP-08 | PASSED — accepted package revision `9e5937895d7559b8537a4595d73b6aabc94f6f13` | Backtest package closure | BT-GAP-02, BT-GAP-03, BT-GAP-05, BT-GAP-06 | none |

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
status: PASSED
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
passed_commit: bdeaf9da8a69926473ff5f66ed7bc5ecb05d5bcb
artifact_hashes:
  tests/fixtures/kernel/profiles/cn_a_share/corporate-action-entitlement-v1.json: sha256:dd489fc4488414f1a3d1d493ea7781952bad707d0c4df839ec8645466c33b011
  build/acceptance/g08f-pytest.xml: sha256:c834845a0f1eb3fefdb78b4fef91403ef2b15323978167dadd4658df21022379
  build/acceptance/g08f-import-boundary-report.json: sha256:a27d45b0fc0c107aee4e8899b5dccf1d3ae345f712fa4363faf24b7731d89695
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
16. Candidate、SourceRef、Band、RuleBook、Registered Snapshot、Query、Entitlement 和 Failure 均使用 explicit `schema_version=1`、canonical tuple order 与 content hash。`type` literal exact 为 SourceRef `cn_a_share_corporate_action_source_ref`、Band `cn_a_share_corporate_action_entitlement_band`、RuleBook `cn_a_share_corporate_action_entitlement_rule_book`、Candidate `cn_a_share_corporate_action_announcement_candidate`、Snapshot `cn_a_share_registered_position_snapshot`、Query `cn_a_share_corporate_action_entitlement_query`、Entitlement `cn_a_share_corporate_action_entitlement`、Failure `cn_a_share_corporate_action_failure`。Canonical preimage exact 分别为：SourceRef `{type,schema_version,source_key,source_hash}`；Band `{type,schema_version,venue_id,effective_start,effective_end,source_refs}`；RuleBook `{type,schema_version,bands}`；Candidate `{type,schema_version,corporate_action_id,instrument,status,event_id,event_hash,event_time,announcement_available_at,revision_id,supersedes_revision_id,record_date,ex_date,payment_date,listing_date,cash_per_share,bonus_rate,capitalization_rate,source_refs}`；Snapshot `{type,schema_version,snapshot_id,register_series_id,revision_id,supersedes_revision_id,account_id,position_key,eligibility_instant,available_at,registered_quantity,source_ref}`；Query `{type,schema_version,instrument,account_id,announcement,snapshot,captured_at}`；Entitlement `{type,schema_version,component_ref,rule_book,calendar,query,active_band,band_hash,query_hash,candidate_hash,event_id,event_hash,snapshot_hash,account_id,position_key,eligibility_instant,captured_at,registered_quantity,gross_cash,bonus_quantity,capitalization_quantity}`；Failure `{type,schema_version,component_ref,rule_book,calendar,query,query_hash,code,subject_ids}`。Entitlement constructor 必须从 embedded RuleBook/G08A Calendar 重建 component ref、唯一 active Band、Record session 与 next-known-TradingDate，再从 embedded Query 重算并验证 Candidate/Event/Snapshot/account/position/instant/numeric identities；Failure constructor 必须从 embedded RuleBook/Calendar 重建 component ref，并从 Query 重算 query hash 与 frozen subject IDs。每个 Failure 的 ordered `subject_ids` exact 固定为 `(code.value, candidate.corporate_action_id or "missing-corporate-action", snapshot.snapshot_id or "missing-register-snapshot", query.account_id, str(query.instrument.instrument_id))`。`ProfilePortOutcome.input_hash` exact 为 Query hash；Failure 和 Result 都绑定同一 component ref 与完整 Query identities；
17. `CnAShareCorporateActionFailureCode` enum 与 first-failure precedence exact 为：`MISSING_ANNOUNCEMENT` → `UNSUPPORTED_VENUE` → `UNSUPPORTED_INSTRUMENT` → `UNSUPPORTED_CURRENCY` → `UNSUPPORTED_ANNOUNCEMENT_STATUS` → `UNSUPPORTED_ANNOUNCEMENT_REVISION` → `INVALID_ANNOUNCEMENT_CAUSALITY` → `MISSING_DISTRIBUTION_COMPONENT` → `MISSING_LIFECYCLE_TERM` → `INVALID_LIFECYCLE_ORDER` → `UNSUPPORTED_DISTRIBUTION_RATE_BASIS` → `UNSUPPORTED_VENUE_ACTION_COMBINATION` → `NON_POSITIVE_DISTRIBUTION_TERM` → `ANNOUNCEMENT_NOT_AVAILABLE` → `LATE_ANNOUNCEMENT` → `MISSING_RULE_INTERVAL` → `OVERLAPPING_RULE_INTERVALS` → `INVALID_RECORD_SESSION` → `MISSING_REGISTERED_POSITION` → `UNSUPPORTED_REGISTER_REVISION` → `ACCOUNT_MISMATCH` → `INSTRUMENT_MISMATCH` → `RECORD_INSTANT_MISMATCH` → `INVALID_REGISTER_CAUSALITY` → `REGISTER_NOT_AVAILABLE` → `NEGATIVE_REGISTERED_QUANTITY` → `UNSUPPORTED_CASH_PRECISION` → `UNSUPPORTED_FRACTIONAL_SHARE`。多缺陷只返回第一项；Constructor type/canonical errors 不冒充 business failure；
18. Component key 固定 `equity.cn_a_share.corporate-action-entitlement.v1`、version 1、algorithm key 固定 `cn-a-share-record-register-entitlement-v1`。Component digest exact 绑定 RuleBook hash、G08A Session component digest、record phase convention、supported numeric policies 与 development-only grade；
19. Concrete purity沿用 G08D/G08E scanner，只允许必要 stdlib、`crypto_quant_domain`、generic `crypto_quant_trading.ports` 与 sibling G08A calendar contract；拒绝 filesystem、network/provider/process/database/cloud、dynamic import、MarketBundle/Runtime import 和 wall clock。Official URL、本地下载和 retrieval time 只属于 research provenance；
20. Static golden 至少冻结 exact official source refs、finite Bands、component/rulebook/band hashes、enum values/failure precedence、embedded RuleBook/Calendar/Query/active-Band identity validation、Announcement Candidate/Event identity、available boundary、Record phase、next-known-TradingDate lifecycle validation、`shares_per_share` basis、XSHG share-distribution rejection、registered snapshot revision identity、XSHE 700/0 与 XSHG cash-only 1000 controls、exact-window/gap/overlap、missing/revised/cancelled/late/mismatched/negative/fractional/sub-cent failures、later-position non-substitution、Reader page-size 与 Timeline batch/input-order parity、pre-availability invisibility和 no-mutation evidence；
21. G08F 始终 development-grade、`deployment_authorized=false`，不拥有 Strategy-facing ObservationView、G11 point-in-time adjusted series、MarketBundle Builder/source adapter、Runtime scheduling、Corporate Action payment/adjustment/tax、real account register provider parity、真实交易或部署授权。

Official source facts、canonical source identities、fixture dates、system conventions 和 G08G blockers 冻结在 `docs/research/cn-a-share-corporate-actions-primary-sources.md`。若官方来源证明 Record eligibility、supported action classification 或 source identity 错误，必须先把 G08F 退回 DRAFT 并以独立 docs commit 修订；READY 前不得实现，PASSED 时 implementation commit 与 acceptance-record commit 继续分离。

### G08F Implementation Acceptance

1. Concrete `corporate_actions` module 结构化实现既有 `CorporateActionModel`，权威输入仅为完整 Announcement Candidate、G08A finite Calendar/Session、finite RuleBook 与历史 Registered Position Snapshot；generic Port、MarketEvent、Timeline、Journal、Ledger、Lot、Settlement 和 Availability 均未加入 A 股分支；
2. Announcement 可见性使用完整 `SimulationInstant`，Candidate exact 绑定真实 source `MarketEvent` ID/hash；Reader page size、Timeline batch size、输入顺序、同 UTC phase/sequence ordering 与 availability boundary 均由 frozen controls 证明确定；
3. Result/Failure 嵌入 RuleBook、G08A Calendar 与完整 Query，重建 component ref、唯一 exact-window Band、Record post-close session、next-known TradingDate、Candidate/Event/Snapshot/account/position/numeric identities 和 frozen Failure subject IDs；
4. XSHG v1 cash-only、XSHE cash/bonus/capitalization、`shares_per_share`、strictly-positive terms、CNY Scale 2、Scale-0 exact shares、zero entitlement、late/revised/cancelled/missing/mismatched/negative/sub-cent/fractional controls及 first-failure precedence 全部 fail closed；
5. XSHE Record quantity 700 exact 产生 gross CNY 70.00、bonus 70、capitalization 140；zero-register/later-current-500 保持 zero；XSHG Record quantity 1,000 exact 产生 gross CNY 200.00；
6. Recursive purity scanner 覆盖 nested mutable values/constructors、module/class suites、named expressions、decorator-time mutation、attribute/subscript mutation 与 mutating methods；no-mutation golden 证明输入、RuleBook、Calendar、Model 与 module state 均不变；
7. Public exports、official source tuples、64-file Import Boundary、64-source mypy、LSP/pi-lens、static golden、full regression、`uv lock --check` 和只读 blocker recheck 均通过。

G08F implementation 已冻结在 immutable commit `bdeaf9da8a69926473ff5f66ed7bc5ecb05d5bcb`，状态为 `PASSED`。

验证记录：

```text
G08F contract                                                     12 passed
G08F static golden                                                 1 passed
Frozen public/boundary regression command                        120 passed
Full test suite                                                   844 passed
Trading-kernel import boundary                                    PASS (64 files)
mypy                                                               no issues (64 source files)
Primary LSP + pi-lens                                              clean
Read-only blocker recheck                                           NONE
uv lock --check                                                     PASS
Python                                                              3.13.5
```

## 68. G08G Corporate Action Adjustment and Payment Acceptance Card

```yaml
id: G08G
status: PASSED
depends_on:
  - G08F
  - G03
owner_package: trading-kernel profiles/cn_a_share
public_interface:
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCorporateActionTaxDisposition
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCorporateActionDeliveryStatus
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCashPaymentEvidence
  - crypto_quant_trading.profiles.cn_a_share.CnAShareShareDeliveryEvidence
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCashPaymentRequest
  - crypto_quant_trading.profiles.cn_a_share.CnAShareShareDeliveryRequest
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCorporateActionTranslationFailureCode
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCorporateActionTranslationFailure
  - crypto_quant_trading.profiles.cn_a_share.CnAShareCashPaymentOutcome
  - crypto_quant_trading.profiles.cn_a_share.CnAShareShareDeliveryOutcome
  - crypto_quant_trading.profiles.cn_a_share.translate_corporate_action_cash_payment
  - crypto_quant_trading.profiles.cn_a_share.translate_corporate_action_share_delivery
test_commands:
  contract: uv run pytest -q tests/kernel/profiles/cn_a_share/test_corporate_action_accounting.py
  fixture: uv run pytest -q tests/kernel/profiles/cn_a_share/test_corporate_action_accounting_golden.py tests/kernel/integration/test_corporate_action_journal_replay.py
  boundary: uv run pytest -q tests/architecture/test_g08g_corporate_action_accounting_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g08g-f3-import-boundary-report.json
  foundation: uv run pytest -q tests/domain/accounting tests/kernel/accounting tests/kernel/journal tests/kernel/ledger tests/runtime/engine/test_g08g_runtime_lot_authority.py
fixture_ids:
  - cn-a-share-corporate-action-accounting-v1
  - cn-a-share-corporate-action-journal-replay-v1
expected_artifacts:
  - tests/fixtures/kernel/profiles/cn_a_share/corporate-action-accounting-v1.json
  - tests/fixtures/kernel/integration/corporate-action-journal-replay-v1.json
  - build/acceptance/g08g-f3-pytest.xml
  - build/acceptance/g08g-f3-mypy.txt
  - build/acceptance/g08g-f3-import-boundary-report.json
failure_contracts:
  - malformed-types-or-noncanonical-text-are-constructor-errors-not-business-failures
  - semantic-context-mismatch-is-accepted-or-partially-translated
  - entitlement-evidence-corporate-action-event-or-hash-mismatch-is-accepted
  - absent-or-zero-payable-leg-or-unsupported-venue-action-scope-is-translated
  - suspended-or-cancelled-delivery-status-is-translated
  - applied-or-deferred-tax-disposition-is-translated
  - nonzero-withholding-or-gross-net-cash-mismatch-is-translated
  - cash-is-not-explicitly-tradable-withdrawable-and-margin-eligible
  - delivered-shares-are-not-explicitly-sellable
  - trigger-is-inferred-or-early-or-unavailable-evidence-is-translated
  - delivered-cash-or-separate-share-values-differ-from-entitlement
  - fractional-share-evidence-is-rounded-or-cash-in-lieu-is-invented
  - zero-or-multiple-eligible-lots-are-allocated-or-selected
  - current-lot-quantity-is-required-to-equal-record-registered-quantity
  - lot-context-or-authoritative-total-cost-basis-mismatch-is-accepted
  - total-cost-basis-changes-or-unit-cost-is-derived-without-supplied-quantization
  - failure-precedence-differs-or-partial-journal-lot-output-is-returned
  - outcome-allows-both-present-or-both-absent-result-and-failure
  - duplicate-journal-id-conflicting-replay-or-stale-before-state-is-reclassified-as-translation-failure
  - raw-price-settlement-availability-provider-runtime-or-revision-scope-is-mutated
  - real-market-profile-decision-grade-or-deployment-qualification-is-claimed
allowed_grade: development
evidence:
  - pytest-report
  - static-corporate-action-accounting-golden-hash
  - static-corporate-action-journal-replay-golden-hash
  - unchanged-g08f-entitlement-hash-evidence
  - unchanged-raw-price-evidence
  - exact-failure-precedence-and-no-partial-output-evidence
  - strict-xor-reconstruction-evidence
  - exact-total-cost-basis-conservation-and-unit-cost-quantization-evidence
  - full-prefix-resume-journal-ledger-replay-evidence
  - duplicate-idempotency-conflict-and-stale-before-state-rejection-evidence
  - synthetic-development-profile-qualified-false-evidence
  - decision-grade-eligible-false-evidence
  - deployment-authorized-false-evidence
  - import-boundary-report
  - static-type-report
passed_commit: 547e16f2d7a9331f9207abfca7ea7c0593fc84fc
artifact_hashes:
  tests/fixtures/kernel/profiles/cn_a_share/corporate-action-accounting-v1.json: sha256:dfed0880cae559b5c4c0f54c3cd461e0e6008af7eda09a1c57254a2db73747c3
  tests/fixtures/kernel/integration/corporate-action-journal-replay-v1.json: sha256:63de3b4dc8f5a674d1d759ac09d868ca505e2dfbdc9707a9a348a939c342faeb
  build/acceptance/g08g-f3-pytest.xml: sha256:1a05c2dd911d41616cc61af59d74ba5799a6cfa20996299c77667a5dac15ff9a
  build/acceptance/g08g-f3-mypy.txt: sha256:787fb5f4281ca29d54908fb6f304c60aaf529c36739cf0420d75b382addef0b7
  build/acceptance/g08g-f3-import-boundary-report.json: sha256:7dc4808c8fedcdee236cf64089ecfaa60ad2e3e5ed01acf133b07156ae593a3f
```

### G08G Acceptance

1. G08G adds exactly one concrete module, `crypto_quant_trading.profiles.cn_a_share.corporate_action_accounting`, owned by `trading-kernel profiles/cn_a_share`. It is exported only from `crypto_quant_trading.profiles.cn_a_share`, not top-level `crypto_quant_trading`. It may reuse G08F Corporate Action values and existing Domain Journal/Lot/Money/Quantization authorities; it must not add a stateless service class, Protocol, registry, new `ProfilePortType`, `ProfilePortOutcome`, generic effect engine, Runtime dispatcher, provider adapter, filesystem/network/process/database access, dynamic import, or wall-clock read;
2. The public seam is exact: one `CnAShareCorporateActionTaxDisposition`, one `CnAShareCorporateActionDeliveryStatus`, separate typed cash-payment and share-delivery evidence/requests, one shared translation failure code/value, two strict XOR outcomes, and two module-level pure translator functions. No separate success-result wrapper is introduced because the existing `AccountingJournalEntry` is the complete success value;
3. `CnAShareCorporateActionTaxDisposition` values are exactly `not_applicable`, `applied`, `deferred_unsupported`. `CnAShareCorporateActionDeliveryStatus` values are exactly `confirmed`, `suspended`, `cancelled`; v1 success accepts only `confirmed`. G08G records disposition but does not calculate withholding or deferred tax. `APPLIED`, `DEFERRED_UNSUPPORTED`, and any nonzero withholding fail closed;
4. Both evidence types are immutable/slotted and exact-bind canonical `evidence_id`, one G08F `CnAShareCorporateActionSourceRef`, G08F `entitlement_hash`, `corporate_action_id`, announcement `event_id`/`event_hash`, delivery status, exact `trigger_at: SimulationInstant`, and evidence `available_at: SimulationInstant`. Cash evidence additionally binds gross cash, withholding, net cash, disposition, and explicit `tradable`, `withdrawable`, `margin_eligible`; share evidence binds separate delivered bonus/capitalization quantities, withholding, disposition, and explicit `sellable`. Payment trigger exact 为 declared Payment `TradingDate` 的 Asia/Shanghai 09:30、`TimelinePhase(110, "corporate_action_payment")`、`SourceSequence(0)`；Listing trigger exact 为 declared Listing `TradingDate` 的 Asia/Shanghai 09:30、`TimelinePhase(120, "corporate_action_listing")`、`SourceSequence(0)`。这些是 deterministic Engine ordering boundaries，不声称外部 clearing timestamp；v1 success exact 要求 `available_at == trigger_at`;
5. Constructors reject only malformed types, invalid existing Domain-value invariants, or noncanonical text. Supported-scope, entitlement/evidence identity, status, tax, withholding, availability, trigger, invocation, delivered-value, Lot, exact-basis, and quantization mismatches remain structured translator outcomes. G08G never infers provider facts, payment revisions, suspension history, event time, delivered value, availability, or tax from dates/current state;
6. Cash request exact stores entitlement, evidence, existing `CashBalanceKey`, existing `DomainId` whose kind is `DomainIdKind.JOURNAL`, and `recorded_at`. Share request exact stores entitlement, evidence, caller-ordered `open_lots: tuple[PositionLot, ...]`, existing `QuantizationPolicy`, existing Journal-kind `DomainId`, and `recorded_at`. A non-Journal ID kind is `CONTEXT_MISMATCH`; requests do not create another ID or Lot authority;
7. Cash success requires a strictly positive G08F payable cash leg; exact account/Venue/Instrument/corporate-action/entitlement/event identities; confirmed status; `NOT_APPLICABLE`; CNY Scale-2 zero withholding; `net_cash == gross_cash`; all three immediate availability flags true; the exact frozen Payment trigger; `available_at == trigger_at`; and `recorded_at >= trigger_at` under full `SimulationInstant` total order. Missing/zero cash leg is unsupported scope; sub-cent, negative, withheld, net/gross mismatch, inferred, early, late/early evidence, suspended, or unavailable cases fail closed;
8. Cash success returns one existing `AccountingJournalEntry` with `CORPORATE_ACTION_CASH_PAID`, effective time `evidence.trigger_at.instant`, exactly one positive cash `BalanceChange` for `net_cash`, empty Lot changes/realized PnL/fees/financing, and no Settlement or availability mutation. It returns no partial Journal tuple;
9. Share success is limited to a strictly positive XSHE bonus/capitalization leg. XSHG share delivery and all non-XSHE share actions are unsupported scope. Success requires confirmed status, `NOT_APPLICABLE`, CNY Scale-2 zero withholding, `sellable=True`, the exact frozen Listing trigger, `available_at == trigger_at`, `recorded_at >= trigger_at` under full `SimulationInstant` total order, separate delivered bonus and capitalization quantities exact-equal to G08F entitlement, whole Scale-0 quantities, and positive summed delivery. G08G does not invent fractional allocation, rounding, cash-in-lieu, delayed listing, or Shanghai listing semantics;
10. Share request must contain exactly one eligible current `PositionLot`; zero and multiple candidates return `ELIGIBLE_LOT_CARDINALITY_MISMATCH`. The Lot exact-matches entitlement account/Venue/Instrument position identity and has positive current quantity, but current Lot quantity is not required to equal G08F `registered_quantity`: post-Record sales do not alter captured entitlement. Multi-Lot allocation and Lot selection heuristics are forbidden;
11. The eligible Lot must have non-null positive `unit_cost` and strictly positive authoritative CNY Scale-2 `total_cost_basis: Money` with exact position/currency identity. The replacement preserves Lot ID, source ID, position key, opened time, allocated fees, and exact total cost basis; its quantity is current quantity plus delivered bonus/capitalization. Only non-authoritative `unit_cost` is rederived from conserved total basis/new quantity using the caller-supplied existing `QuantizationPolicy`; the policy target scale must equal the prior unit-cost scale and the quantized result must remain positive. Missing/zero basis, incompatible currency/scale/policy, or unverifiable derivation fails closed;
12. Share success returns one existing `AccountingJournalEntry` with `CORPORATE_ACTION_POSITION_ADJUSTED`, effective time `evidence.trigger_at.instant`, one position `BalanceChange` equal to delivered bonus plus capitalization, and exactly one `PositionLotChange(before=old_lot, after=adjusted_lot)`. Realized PnL, fees, financing, Settlement, and availability effects are empty. The outcome does not return `open_lots`; `AccountingJournal` append and `GenericLedger` replay are authoritative;
13. Failure enum declaration and first-applicable guard order are exact: `CONTEXT_MISMATCH` → `ENTITLEMENT_EVIDENCE_MISMATCH` → `UNSUPPORTED_ACTION_SCOPE` → `UNSUPPORTED_DELIVERY_STATUS` → `UNSUPPORTED_TAX_DISPOSITION` → `NONZERO_WITHHOLDING` → `UNSUPPORTED_AVAILABILITY` → `TRIGGER_MISMATCH` → `EVIDENCE_NOT_AVAILABLE` → `UNSUPPORTED_FRACTIONAL_SHARE` → `DELIVERED_VALUE_MISMATCH` → `EARLY_INVOCATION` → `ELIGIBLE_LOT_CARDINALITY_MISMATCH` → `LOT_STATE_MISMATCH` → `EXACT_COST_BASIS_MISMATCH` → `UNIT_COST_QUANTIZATION_MISMATCH`. `EVIDENCE_NOT_AVAILABLE` exact-covers `available_at != trigger_at`; `DELIVERED_VALUE_MISMATCH` exact-covers cash gross/net versus G08F entitlement after the earlier withholding guard and share bonus/capitalization mismatch after the earlier fractional guard, so intrinsic evidence attribution is stable across early/on-time retries. `ELIGIBLE_LOT_CARDINALITY_MISMATCH` checks absolute `len(open_lots) != 1` without filtering; only identity/state defects of the single Lot reach `LOT_STATE_MISMATCH`. Multi-defect requests return only the first failure and no Journal/Lot prefix;
14. Duplicate Journal IDs, duplicate idempotency, conflicting Journal replay, and stale/mismatched Lot before-state are not G08G translation failures. The translator deterministically reconstructs the same entry from the same request; existing `AccountingJournal` and `GenericLedger` remain authoritative and reject append/replay conflicts atomically;
15. Cash/share outcomes embed the complete request and exactly one of `journal_entry` or shared failure. Constructors reject both-present and both-absent states; they re-evaluate the first failure or exact-reconstruct the Journal from the request, preventing forged success/failure/outcome hashes;
16. Every new value uses `schema_version=1`, explicit type literal, canonical tuple order, and hash. Type literals are `cn_a_share_cash_payment_evidence`, `cn_a_share_share_delivery_evidence`, `cn_a_share_cash_payment_request`, `cn_a_share_share_delivery_request`, `cn_a_share_corporate_action_translation_failure`, `cn_a_share_cash_payment_outcome`, and `cn_a_share_share_delivery_outcome`. Public hashes are `evidence_hash`, `request_hash`, `failure_hash`, and `outcome_hash` as applicable;
17. Failure `subject_ids` exact order is `(code, leg, corporate_action_id, entitlement_hash, evidence_id, evidence_hash, account_id, instrument_id, journal_entry_id)`, where leg is `cash_payment` or `share_delivery`. Journal `source_ids` exact order is corporate-action ID, entitlement hash, announcement event ID, announcement event hash, evidence ID, evidence hash;
18. Static fixtures are exactly `tests/fixtures/kernel/profiles/cn_a_share/corporate-action-accounting-v1.json` with ID `cn-a-share-corporate-action-accounting-v1` and `tests/fixtures/kernel/integration/corporate-action-journal-replay-v1.json` with ID `cn-a-share-corporate-action-journal-replay-v1`. They freeze CA-XSHE-001 CNY 70 payment/210-share delivery against one current 500-share exact-basis Lot, proving current quantity need not equal the frozen 700-share Record entitlement; CA-XSHG-001 CNY 200 payment; Journal IDs with repeated 6/7/8 payloads; every failure; multi-defect precedence; XOR rejection; full/prefix/resume replay; existing Journal/Ledger duplicate/conflict rejection; unchanged G08F entitlement hash; and unchanged raw prices. Golden hashes are generated/frozen in the RED fixture commit, not invented in implementation;
19. All artifacts remain synthetic development evidence and exact-record `grade=development`, `decision_grade_eligible=false`, `profile_qualified=false`, and `deployment_authorized=false`. G08G does not qualify a provider, real security/account/distribution scope, revision completeness, real market/profile, trading decision, or deployment;
20. G08H retains provider/payment/revision-set scope, cross-query stable-ID conflict validation, real-market composition qualification, MarketBundle mapping, Runtime wiring, and parity. G08G does not mutate raw OHLC/Fill/accounting prices, infer ex-reference prices, recompute G08F entitlement, add a Corporate Action Settlement fork, or claim profile completeness.

### G08G Implementation Acceptance

1. F1/F2/F3 share one `PositionLotChange`/`GenericLedger` authority; policy-v2 Fill/Fee and Corporate Action share delivery all replay through the same Journal/Ledger path, while policy-v1 fixtures remain exact;
2. The concrete profile-only module implements the frozen twelve-name seam, exact evidence/request/failure/outcome schemas, strict XOR reconstruction, all sixteen first-failure guards, and no provider/Runtime/generic-framework side path;
3. XSHE CNY 70 payment and current-500/Record-700 share delivery conserve CNY 7,500.00 total basis and derive only rounded display unit cost; XSHG CNY 200 payment succeeds while unsupported share scope fails closed;
4. Full/prefix/resume replay, duplicate idempotency, Journal conflicts, stale Lot before-state, source identity collision, exact subject IDs, canonical hashes, raw-price non-mutation, and false qualification flags are frozen by static tests;
5. Final verification passed `92` focused acceptance tests and `1519` full repository tests; mypy 2.3.0 and import boundaries are clean across 95 source files; LSP/pi-lens, `uv lock --check`, `git diff --check`, and three independent final reviews are dry.

G08G implementation is frozen at immutable commit `547e16f2d7a9331f9207abfca7ea7c0593fc84fc` and status is `PASSED`. G08H remains responsible for provider/revision closure, real-market composition, Runtime wiring, parity, and qualification.

Validation record:

```text
G08G focused acceptance                                         92 passed
Full repository                                               1519 passed
mypy 2.3.0                                             95 source files clean
Import boundaries                                         95 files passed
Primary LSP + pi-lens                                             clean
Independent final reviews                                           NONE
uv lock --check                                                     PASS
git diff --check                                                    PASS
```

Exact acceptance commands:

```bash
uv run pytest -q \
  tests/kernel/profiles/cn_a_share/test_corporate_action_accounting.py \
  tests/kernel/profiles/cn_a_share/test_corporate_action_accounting_golden.py \
  tests/kernel/integration/test_corporate_action_journal_replay.py
```

```bash
uv run pytest -q \
  tests/domain/accounting \
  tests/kernel/accounting \
  tests/kernel/journal \
  tests/kernel/ledger \
  tests/runtime/engine/test_g08g_runtime_lot_authority.py
```

```bash
uv run pytest -q \
  tests/architecture/test_g08g_corporate_action_accounting_boundary.py \
  tests/architecture/test_public_api_imports.py \
  tests/architecture/test_network_isolation.py \
  tests/architecture/test_repository_cleanliness.py

uv run python tools/architecture/check_import_boundaries.py \
  --root . \
  --policy architecture/import-boundaries.toml \
  --report build/acceptance/g08g-f3-import-boundary-report.json
```

## 68A. G08H A-share Profile Composition and Parity Acceptance Card

```yaml
id: G08H
status: PASSED
depends_on:
  - G08A
  - G08B
  - G08C
  - G08D
  - G08E
  - G08F
  - G08G
  - G09H
  - WP-00C
owner_package: backtest-runtime composition + tests/support + parity tooling
public_interface:
  - crypto_quant_backtest.CnAShareInstrumentScopeDeclaration
  - crypto_quant_backtest.CnAShareAccountScopeDeclaration
  - crypto_quant_backtest.CnAShareAnnouncementRevisionSetDeclaration
  - crypto_quant_backtest.CnAShareRegisterRevisionSetDeclaration
  - crypto_quant_backtest.CnAShareIdentityHistoryDeclaration
  - crypto_quant_backtest.CnAShareProfileCompositionRequest
  - crypto_quant_backtest.CnAShareMarketSemanticsProfile
  - crypto_quant_backtest.CnAShareSimulationProfile
  - crypto_quant_backtest.CnAShareExecutionAccountProfile
  - crypto_quant_backtest.CnAShareResolvedProfile
  - crypto_quant_backtest.CnAShareProfileCompositionFailureCode
  - crypto_quant_backtest.CnAShareProfileCompositionFailure
  - crypto_quant_backtest.CnAShareProfileCompositionOutcome
  - crypto_quant_backtest.CnAShareProfileComposer
  - tests.support.cn_a_share.CnAShareDevelopmentFinancialDispatcher
  - tests.support.cn_a_share.CnAShareDevelopmentJourneyResult
  - tests.support.cn_a_share.build_cn_a_share_resolved_request
  - tests.support.cn_a_share.build_cn_a_share_execution_case
  - tests.support.cn_a_share.run_cn_a_share_development_journey
  - tools.parity.cn_a_share.CnAShareParityError
  - tools.parity.cn_a_share.run_plan
  - tools.parity.cn_a_share.blocked_report
  - tools/parity/run_cn_a_share_parity.py
test_commands:
  contract: uv run pytest -q tests/runtime/profiles/cn_a_share/test_profile_composition.py tests/runtime/profiles/cn_a_share/test_profile_composition_adversarial.py tests/support/cn_a_share/test_cn_a_share_profile.py
  fixture: uv run pytest -q tests/runtime/profiles/cn_a_share/test_profile_composition_golden.py tests/runtime/engine/test_g08h_cn_a_share_golden.py
  journey: uv run pytest -q tests/runtime/engine/test_g08h_cn_a_share_journey.py
  parity: uv run pytest -q tests/parity/test_cn_a_share_parity.py tests/parity/test_cn_a_share_parity_golden.py
  boundary: uv run pytest -q tests/architecture/test_g08h_cn_a_share_composition_boundary.py tests/architecture/test_g08h_parity_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  acceptance: uv run pytest -q tests/runtime/profiles/cn_a_share tests/support/cn_a_share tests/runtime/engine/test_g08h_cn_a_share_journey.py tests/runtime/engine/test_g08h_cn_a_share_golden.py tests/parity/test_cn_a_share_parity.py tests/parity/test_cn_a_share_parity_golden.py tests/architecture/test_g08h_cn_a_share_composition_boundary.py tests/architecture/test_g08h_parity_boundary.py tests/kernel/profiles/cn_a_share tests/kernel/integration/test_corporate_action_journal_replay.py tests/runtime/engine/test_g08g_runtime_lot_authority.py tests/runtime/engine/test_g09h_synthetic_linear_perpetual_journey.py --junitxml=build/acceptance/g08h-pytest.xml
fixture_ids:
  - cn-a-share-resolved-profile-composition-v1
  - cn-a-share-resolved-profile-development-journey-v1
  - cn-a-share-g08h-parity-plan-v1
  - cn-a-share-g08h-cycle-rotation-projection-v1
  - cn-a-share-g08h-runtime-projection-v1
  - cn-a-share-g08h-parity-report-v1
  - cn-a-share-g08h-legacy-to-g08h-v1
expected_artifacts:
  - docs/research/g08h-profile-composition-parity.md
  - docs/implementation/plans/g08/g08h.md
  - tests/fixtures/runtime/profiles/cn-a-share-resolved-profile-composition-v1.json
  - tests/fixtures/runtime/engine/cn-a-share-resolved-profile-development-journey-v1.json
  - tests/parity/contracts/cn-a-share-g08h-legacy-to-g08h-v1.json
  - tests/parity/fixtures/cn-a-share-g08h-v1/plan.json
  - tests/parity/fixtures/cn-a-share-g08h-v1/legacy.expected.json
  - tests/parity/fixtures/cn-a-share-g08h-v1/g08h.actual.json
  - tests/parity/fixtures/cn-a-share-g08h-v1/report.expected.json
  - build/acceptance/g08h-pytest.xml
  - build/acceptance/g08h-parity-report.json
  - build/acceptance/g08h-import-boundary-report.json
  - build/acceptance/g08h-mypy.txt
failure_contracts:
  - missing-instrument-scope-is-accepted-or-inferred
  - missing-account-scope-is-accepted-or-inferred
  - missing-announcement-revision-set-is-accepted
  - missing-register-revision-set-is-accepted
  - missing-identity-history-is-accepted
  - unsupported-instrument-scope-is-composed
  - unsupported-account-scope-or-available-margin-authority-is-composed
  - inherited-account-venue-instrument-currency-or-rule-context-mismatch-is-composed
  - revision-chain-gap-branch-terminal-or-cancellation-mismatch-is-composed
  - cross-query-stable-id-conflict-is-composed
  - timeline-coverage-gap-is-filled-from-neighbor-or-current-state
  - evidence-available-after-composition-is-used
  - applied-or-deferred-tax-disposition-produces-effects
  - xshg-share-delivery-is-composed
  - component-manifest-spec-registration-or-profile-identity-conflict-is-accepted
  - result-failure-outcome-or-declaration-hash-is-forgeable
  - generic-runtime-adds-cn-a-share-import-name-or-operation-branch
  - legacy-missing-authority-is-claimed-as-match
allowed_grade: development
evidence:
  - exact-public-schema-field-type-and-canonical-hash-tests
  - fifteen-code-first-failure-reachability-and-multi-defect-precedence
  - strict-xor-and-constructor-reconstruction-forgery-rejection
  - exact-twelve-market-and-six-simulation-component-manifests
  - inherited-g08a-through-g08g-static-fixture-hashes
  - profile-specific-dispatcher-spec-and-operation-key-identity
  - phase-110-payment-and-phase-120-listing-journey
  - exact-cash-share-basis-and-full-prefix-resume-replay-evidence
  - source-grounded-comparable-legacy-budgeting-and-order-intent-projections
  - explicit-not-comparable-legacy-scope-coverage
  - deterministic-first-divergence-and-source-identity-tamper-rejection
  - import-boundary-report
  - static-type-report
  - pytest-report
passed_commit: e954be6bc1d46a3d3f399a3c3cf874a917894570
artifact_hashes:
  tests/fixtures/runtime/profiles/cn-a-share-resolved-profile-composition-v1.json: sha256:aa032668a5207b61b6c8815894e0087f1c1e734d41e9707c7d32111b6c1cd79f
  tests/fixtures/runtime/engine/cn-a-share-resolved-profile-development-journey-v1.json: sha256:08358c1c0d2144fb23c1b1c8862fa6c879bd285533e5fa415e5cc0273013e905
  tests/parity/contracts/cn-a-share-g08h-legacy-to-g08h-v1.json: sha256:6d310d9ce7bcf3e5eb1b88704c7030d63a42aa5d2faa67c18324ebd4ca8b423b
  tests/parity/fixtures/cn-a-share-g08h-v1/plan.json: sha256:7600c6416d18e35fe5f9cb3174a6fe9768d752fd740440fba2430f4ef293d1b8
  tests/parity/fixtures/cn-a-share-g08h-v1/legacy.expected.json: sha256:e6b267b42f5983187a0807c3514beae80e0676ea2987dd4dea2c6c816f680b2a
  tests/parity/fixtures/cn-a-share-g08h-v1/g08h.actual.json: sha256:6a565b912671b88fe0c9ab70b24705aa5259fdb99fd644d19bac7ac3178a7174
  tests/parity/fixtures/cn-a-share-g08h-v1/report.expected.json: sha256:d12734232e96a78f8397a795b9151f3c2c597df338fd45d44eeeaf20990e08da
  build/acceptance/g08h-pytest.xml: sha256:f3d39b1ccf74c5d7f47202508b538ef22f6e6b56b7e3726a3b7aff65aa981b74
  build/acceptance/g08h-parity-report.json: sha256:a6f230cb5da84156cd5d114180e2a202c2b0fad169a813a1da7174018ebfdd01
  build/acceptance/g08h-import-boundary-report.json: sha256:466a494a456919fb6e0200e49ba4bb93d2bc0538f4cbca0d43a55e04b99a8df5
  build/acceptance/g08h-mypy.txt: sha256:a46f4f6204d5dbfb5bd53dd8594c13848e25384e360264df053a1e64ce013501
```

### G08H Acceptance

1. G08H adds exactly one pure production module, `crypto_quant_backtest.cn_a_share_profile`, and root-exports the fourteen frozen production names above. It reuses G08A–G08G and G09H; it must not add a second Registry, Resolver, Engine, dispatcher framework, accounting authority, Protocol, generic port, provider Adapter, cache or Runtime market branch;
2. The five immutable declarations and their exact fields/types are frozen by contract tests and the composition fixture. Every `declaration_hash` is a derived property over a canonical body that excludes itself. Constructors reject malformed exact types/text/hash/intervals; supported scope, closure, identity, coverage and availability remain structured business failures;
3. Instrument success requires explicit ordinary domestic XSHG/XSHE CNY Equity cash-auction evidence plus existing G08D board/risk/listing context, with B/H, fund/bond, Stock Connect, lending/repo, pledge/freeze, restricted/pre-IPO, differential distribution and issuer self-distribution flags false. No symbol/current/provider inference is permitted;
4. Account success requires explicit cash domestic access, no margin/short, no Stock Connect and no generic available-margin authorization. One profile covers one Venue and one declared Account scope;
5. Announcement/register declarations bind caller-order nonempty immediate-parent linear revision chains, terminal IDs, coverage, availability and source snapshot/manifest hashes. G08H validates the supplied set/chain only; G12L/G12M retain external omission/completeness and real-market qualification;
6. Cross-query identity history uses canonical scoped identity/payload-hash tuples. Conflicting reuse of corporate-action, register-snapshot or register-revision identity fails atomically;
7. Composition Request exact-binds the five optional declarations, G08A Calendar, G08D/G08E/G08F rule books, canonical Entitlement/G08G request tuples, Timeline window and composition instant. Optional declarations exist only for structured missing-authority outcomes; all inherited authorities use exact types;
8. The fifteen failure codes and first-failure order are exact as frozen in the composition fixture. Failure embeds the full Request and reconstructs the first failure with `subject_ids=(code.value, request.request_hash)`. Outcome is strict XOR. Resolved Profile, Failure and Outcome reject forged `dataclasses.replace` values;
9. G08G tax success remains `NOT_APPLICABLE`-only; `APPLIED` and `DEFERRED_UNSUPPORTED` fail before Journal/Lot effects. XSHG bonus/capitalization remains unsupported. No deferred-tax Lot state machine or Shenzhen-to-Shanghai Listing inference is added;
10. Market and Simulation profiles exact-cover all existing 12/6 port enums. Existing G08 and default-cash component refs are reused. The two explicit static manifest components and all fixed digests are frozen in the composition fixture;
11. Dispatcher spec key is `equity.cn_a_share.cash-financial-dispatch.v1`, not the generic cash key. Its config hash binds profile/request/manifests/operation keys/G08G requests/limitations while reusing default cash accounting refs and snapshot projection authority;
12. Profile keys, capabilities, AccountRiskPolicy, limitations, registrations and Registry are exact. Every result is development-only with `decision_grade_eligible=false`, `profile_qualified=false`, and `deployment_authorized=false`;
13. Test-support exports one concrete dispatcher, one Journey result and three builders/runners. Payment and Listing operation keys are exact at phases 110/120; generic Engine/Runner/Timeline/Journal/Ledger/Composer contain no A-share import, name or operation branch;
14. The scheduled-event Journey freezes the existing XSHE CNY 70 payment, 210-share delivery, current 500→710 Lot transition and exact CNY 7,500.00 total-basis conservation. Full and prefix/resume Journal/Ledger/Lot replay are identical and the final Snapshot binds the final Journal state. Inherited G08A–G08F suites remain the component behavior authority;
15. Legacy comparison is grounded in the immutable archive and a CNY 100,000/0.95/10.00/100-share synthetic case. Only case input, decision budgeting and order intent are comparable. The other seven layers are `NOT_COMPARABLE_LEGACY_SCOPE`; pair verdict is `MATCH`, aggregate verdict is `NOT_COMPARABLE_LEGACY_SCOPE`, and Calendar/Session is the first uncovered layer;
16. Parity tooling validates immutable source/projection/contract hashes, complete coverage, rule/coverage separation and deterministic first divergence. It does not execute the archive, import Runtime/profile code, invent an oracle or claim missing authority as equality;
17. Static fixture bytes, inherited PASSED fixture hashes and exact RED failures are frozen. Production, test-support and parity implementations remain absent at READY; implementation may make tests green but may not rewrite the contract or fixtures;
18. Real provider acquisition, archive completeness, live security/account scope, decision grade, profile qualification and deployment authorization remain G12L/G12M responsibilities.

### G08H Implementation Acceptance

1. The pure production composer, fourteen root exports, five immutable declarations, exact 12/6 manifests, development registrations and profile-specific dispatcher identity are implemented at immutable commit `e954be6bc1d46a3d3f399a3c3cf874a917894570`;
2. Additive adversarial tests reject fabricated embedded revision chains, unsupported risk-warning/new-listing contexts, absent profile-Venue fee/tax authority, cross-history identity conflicts, duplicate manifest authorities, bool/int equality forgery and duck-typed Outcome branches;
3. The test-support Journey emits the frozen phase-110 Payment and phase-120 Listing artifacts and appends the exact G08G share-ID-7/cash-ID-8 immutable Journal batch in canonical `(recorded_at, journal_entry_id)` order. It preserves CNY 70, 500→710 shares, CNY 7,500 total basis, full/prefix/resume replay and final Snapshot binding without an Engine/Journal/Ledger market branch;
4. The isolated parity tool reuses the WP-00C comparator, validates root-contained paths and immutable hashes, exact-covers all ten layers, reports comparable `MATCH`, aggregate `NOT_COMPARABLE_LEGACY_SCOPE`, Calendar/Session first uncovered, deterministic first divergence and canonical report hash `sha256:d72471cc2ee87d2e414c04d92be9d7de94f1cf2fbe83aa422b27f610a79b7874`;
5. Final verification passed `304` G08H acceptance tests and `1568` full repository tests. Mypy is clean for the production module and isolated test-support/parity surfaces; import boundaries pass across `96` files; LSP/pi-lens, `uv lock --check`, `git diff --check`, static fixture byte hashes and two final independent dry reviews are clean.

G08H implementation is frozen at immutable commit `e954be6bc1d46a3d3f399a3c3cf874a917894570` and status is `PASSED`. Real provider acquisition, archive completeness, live security/account scope, decision grade, profile qualification and deployment authorization remain G12L/G12M responsibilities.

Validation record:

```text
G08H focused acceptance                                        304 passed
Full repository                                               1568 passed
Mypy                                              4 changed surfaces clean
Import boundaries                                         96 files passed
Parity aggregate verdict                    NOT_COMPARABLE_LEGACY_SCOPE
Primary LSP + pi-lens                                             clean
Independent final reviews                                           NONE
uv lock --check                                                     PASS
git diff --check                                                    PASS
```

Research and plan: `docs/research/g08h-profile-composition-parity.md`, `docs/implementation/plans/g08/g08h.md`.

## 69. G09A Linear Derivative Position Model Acceptance Card

```yaml
id: G09A
status: PASSED
depends_on:
  - G03
owner_package: trading-kernel derivatives
public_interface:
  - crypto_quant_trading.LinearPositionTransitionKind
  - crypto_quant_trading.LinearPerpetualContract
  - crypto_quant_trading.ExactAverageEntryBasis
  - crypto_quant_trading.LinearPositionState
  - crypto_quant_trading.LinearPositionProjectionRequest
  - crypto_quant_trading.LinearPositionTransition
  - crypto_quant_trading.LinearPositionProjection
  - crypto_quant_trading.LinearPositionProjectionFailureCode
  - crypto_quant_trading.LinearPositionProjectionFailure
  - crypto_quant_trading.LinearPositionProjectionOutcome
  - crypto_quant_trading.LinearPositionProjector
  - static synthetic linear-position golden fixture v1
test_commands:
  contract: uv run pytest -q tests/kernel/derivatives/test_linear_positions.py
  fixture: uv run pytest -q tests/kernel/derivatives/test_linear_positions_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py tests/architecture/test_derivative_boundary.py tests/kernel/ledger/test_generic_ledger.py tests/kernel/snapshots/test_portfolio_snapshot_projector.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g09a-import-boundary-report.json
fixture_ids:
  - synthetic-linear-position-v1
expected_artifacts:
  - tests/fixtures/kernel/derivatives/linear-position-v1.json
  - build/acceptance/g09a-pytest.xml
  - build/acceptance/g09a-import-boundary-report.json
failure_contracts:
  - current-state-or-average-price-is-read-from-ledger-lots-or-runtime-mutable-state
  - fill-order-is-sorted-or-equal-time-order-is-discarded
  - duplicate-fill-id-or-execution-time-regression-is-accepted
  - account-venue-instrument-quantity-price-or-currency-context-is-partially-projected
  - quantity-or-price-is-implicitly-rescaled
  - weighted-average-entry-is-rounded-or-stored-as-float-decimal
  - partial-reduce-reprices-the-surviving-position
  - close-retains-an-entry-basis
  - flip-blends-the-closed-side-entry-basis-into-the-new-side
  - contract-multiplier-is-omitted-from-state-identity
  - failure-returns-a-partial-transition-prefix
  - generic-ledger-snapshot-engine-or-runtime-branches-on-derivative-instrument-type
  - g09a-books-realized-pnl-fee-funding-margin-or-liquidation
allowed_grade: development
evidence:
  - pytest-report
  - static-linear-position-golden-hash
  - exact-rational-average-entry-evidence
  - long-short-open-add-reduce-close-flip-evidence
  - deterministic-fill-prefix-and-ordering-evidence
  - multiplier-and-scale-identity-evidence
  - atomic-failure-precedence-evidence
  - no-ledger-runtime-mutation-evidence
  - import-boundary-report
  - static-type-report
passed_commit: 190efba252b5353267cdc336698d93fd3b3b524c
artifact_hashes:
  tests/fixtures/kernel/derivatives/linear-position-v1.json: sha256:98106e5acc8cb1ed11ef1d46e364cdb06c1156a1d01ade99fb45cfb48aaafe60
  build/acceptance/g09a-pytest.xml: sha256:0b8a29671a05886519bc310f3ac757a0463d35131cf4460a6cfdfd018c3ef658
  build/acceptance/g09a-import-boundary-report.json: sha256:13c7981d9d9faec783922a863239bf7b4242dc87a959053420db04a83072e79e
```

### G09A Acceptance

1. G09A 只在 `crypto_quant_trading.derivatives` 增加 pure in-process deep module，并从 `crypto_quant_trading` root 公开 frozen interface；不得新增 generic Port、Adapter、Package、Profile registration、依赖或在 Generic Ledger、PortfolioSnapshotProjector、Engine、Runner、Timeline 中增加 `InstrumentType.LINEAR_PERPETUAL` branch；
2. `LinearPerpetualContract` exact 保存 `InstrumentDefinition`、authoritative Quantity Scale、authoritative Price Scale 与 positive typed `Rate` contract multiplier。Instrument 必须为 `LINEAR_PERPETUAL`、base currency 非空且 quote currency exact 等于 settlement currency；multiplier basis exact 为 `base_quantity_per_contract`。Constructor 只接受 explicit evidence，不从 symbol、Venue 或 provider metadata 推断；
3. G09A v1 是单 Execution Account、单 Instrument 的 one-way net Position。Signed `Quantity` 的正值表示 Long、负值表示 Short、零表示 Flat；不新增 Long/Short enum，不表达 hedge-mode 双腿、reduce-only、`PositionEffect`、isolated/cross margin 或多账户净额；
4. `ExactAverageEntryBasis` 保存 Instrument ID、quote Currency、strictly-positive GCD-reduced integer numerator 与 positive denominator，经济含义 exact 为 quote Price `numerator / denominator`。禁止 float、Decimal、quantization、rounding 或固定小数截断；unreduced、零/负 denominator、non-positive numerator 或 identity mismatch 在 constructor fail closed；
5. `LinearPositionState` exact 保存 `PositionBalanceKey`、完整 Contract、signed Quantity 与 optional exact basis。Invariant exact 为 `quantity.units == 0 iff average_entry_basis is None`；non-flat 必须有 basis。Position key/Contract/Quantity/Basis 的 account、Venue、Instrument、Currency 和 Scale identity 必须一致。G09A 不复用 cash `PositionLot` 或 Generic Ledger balance 作为平均入场权威；
6. `LinearPositionProjectionRequest` exact 保存 Position key、Contract 与 caller-ordered immutable Fill tuple。Empty tuple 合法并产生 canonical Flat state；tuple order 是业务语义，Projector 不排序。Execution time 必须 non-decreasing；相同 execution time 合法并由 tuple order 决定，完整 Fill bytes 进入 Request/Transition/Projection identity；
7. 每个 Fill 的 signed delta exact 为 BUY `+fill.quantity.units`、SELL `-fill.quantity.units`。令 prior units `q0`、delta `d`、after `q1=q0+d`，transition precedence exact 为：`q0==0 -> OPEN`；`sign(q0)==sign(d) -> ADD`；`abs(d)<abs(q0) -> REDUCE`；`abs(d)==abs(q0) -> CLOSE`；`abs(d)>abs(q0) -> FLIP`；
8. `closed_quantity` 对 OPEN/ADD exact 为 zero positive-direction sentinel Quantity，对 REDUCE/CLOSE/FLIP exact 为 `min(abs(q0), abs(d))`，Scale 与 Instrument identity 不变。After signed Quantity exact 为 `q1`；REDUCE 保留 prior basis，CLOSE 设 basis None，FLIP 的新方向 basis exact 等于 crossing Fill Price，不把已关闭方向 basis 混入新方向；
9. OPEN basis exact 为 reduced `fill.price.units / 10^price_scale.places`。ADD 使用 Quantity raw units 作为同 Scale 权重；若 prior basis 为 `N/D`、Fill Price units 为 `p`、Price scale factor 为 `S=10^places`、同向 prior/fill raw quantities 为 `a/b`，new basis exact 为 reduced `(N*a*S + p*b*D) / (D*(a+b)*S)`。固定 Contract multiplier 在 weighted average 中代数消去，但必须保留在 Contract/State identity，供 G09B 使用 `sign(before.quantity.units) × closed_quantity × multiplier × (exit price - prior basis)`；
10. `LinearPositionProjector.project(request)` 是唯一行为 interface，一次从 Flat state投影完整 Fill sequence并返回 exactly-one Projection/Failure；不额外公开 `apply_fill()`、`replay()` 或 mutable accumulator。每个 Transition 保存 kind、完整 Fill、before/after State 与 closed Quantity；Projection 保存完整 Request、request hash、ordered Transitions 与 final State；
11. Failure enum values exact 为 `position_context_mismatch`、`duplicate_fill_id`、`non_monotonic_execution_time`、`fill_context_mismatch`、`quantity_scale_mismatch`、`price_context_mismatch`、`price_scale_mismatch`，first-failure precedence exact 为：Request-level `POSITION_CONTEXT_MISMATCH` → 对每个最早 failing Fill 依次 `DUPLICATE_FILL_ID` → `NON_MONOTONIC_EXECUTION_TIME` → `FILL_CONTEXT_MISMATCH` → `QUANTITY_SCALE_MISMATCH` → `PRICE_CONTEXT_MISMATCH` → `PRICE_SCALE_MISMATCH`。Duplicate exact 归因于最早的 repeated occurrence，不归因于首次出现；同一 Fill 多缺陷只返回该顺序第一项。任何 business failure 原子返回且不暴露 partial Projection/Transition prefix。Malformed constructor type/canonical errors 不冒充 business failure；
12. Position context exact 要求 Position key Venue/Instrument 与 Contract Instrument 一致。Fill context exact 要求 account/Venue/Instrument 与 Position key 一致；Quantity Instrument/Scale、execution Price Instrument/quote Currency/Scale 与 Contract 一致。Fill `reference_price`、slippage、liquidity 和 Order metadata 保留在 identity，但不参与 G09A entry basis；
13. Duplicate Fill ID 在同一 Request 内 fail closed；execution-time regression fail closed；跨 Request Journal idempotency/conflict detection属于 G09B。相同 Request bytes 必须返回相同 hashes；相同最终经济状态但不同 Fill order/metadata 允许 state hash相同。Request/Projection hash 必须随完整 Request identity 改变；某一 Transition hash 只在该 Transition 自身 `{kind,fill,before,after,closed_quantity}` canonical preimage 改变时改变，later Fill metadata 不 retroactively 改写 earlier Transition identity；
14. Transition、Projection constructor 必须从 embedded Request/Fill/before State 重算 transition kind、closed Quantity、after State 与 final State，拒绝 forged prefix/final result。Failure 保存完整 Request、request hash、code、zero-based fill index 与 conditional Fill ID：Request-level Position mismatch exact 使用 `(fill_index=None, fill_id=None)`；Fill-level Failure exact 指向 offending Fill；Failure constructor 必须从 embedded Request 重算完整 first failure，而不只验证 index/ID shape。Outcome 保存 request hash并只允许 exactly-one result/failure；
15. Transition kind enum values exact 为 `open`、`add`、`reduce`、`close`、`flip`。所有 public values 使用 `schema_version=1` 与 canonical tuple order。Canonical `type` exact 为 Contract `linear_perpetual_contract`、Basis `exact_average_entry_basis`、State `linear_position_state`、Request `linear_position_projection_request`、Transition `linear_position_transition`、Projection `linear_position_projection`、Failure `linear_position_projection_failure`、Outcome `linear_position_projection_outcome`。Canonical preimage exact 分别为：Contract `{type,schema_version,instrument,quantity_scale,price_scale,contract_multiplier}`，其中 `quantity_scale`/`price_scale` exact 编码为各自 `Scale.places` integer；Basis `{type,schema_version,instrument_id,quote_currency,numerator,denominator}`；State `{type,schema_version,position_key,contract,quantity,average_entry_basis}`；Request `{type,schema_version,position_key,contract,fills}`；Transition `{type,schema_version,kind,fill,before,after,closed_quantity}`；Projection `{type,schema_version,request,request_hash,transitions,final_state}`；Failure `{type,schema_version,request,request_hash,code,fill_index,fill_id}`；Outcome `{type,schema_version,request_hash,result,failure}`；
16. `contract_hash`、`basis_hash`、`state_hash`、`request_hash`、`transition_hash`、`projection_hash`、`failure_hash` 与 `outcome_hash` exact 使用 `canonical_sha256(value)`。Scale canonical 继续沿用 Domain `Scale` contract，不新增替代 schema。Constructor/Projector 不 mutate Request、Fill、Contract 或 State，也不创建 mutable module state；
17. Static synthetic golden exact 使用非 unit multiplier `Rate(125, Scale(3), "base_quantity_per_contract")`、Quantity Scale 3、Price Scale 2，至少冻结：Long/Short OPEN、ADD、REDUCE、CLOSE、FLIP；Long `1.000 @ 100.00` 加 `2.000 @ 100.50` 后 basis `301/3`；partial reduce保持 `301/3`；crossing Fill 后新 side basis等于 Fill；empty projection；prefix parity；equal-time permutation identity；cross-zero permutation economics；multiplier/Scale mutation；request-level failure null attribution、earliest repeated duplicate attribution、全部 failure precedence/atomicity、constructor rejection、canonical bytes/hash 与 no-mutation controls。`test_derivative_boundary.py` 必须 AST/source 扫描 Generic Ledger、SnapshotProjector、Engine、Runner 和 Timeline，拒绝 `InstrumentType.LINEAR_PERPETUAL` 或 `linear_perpetual` branch/reference；
18. G09A 不拥有 Accounting Journal、PositionAccountingModel、Ledger replay、realized/unrealized PnL、Money quantization、Fee、Funding、Margin、Liquidation、Settlement、Mark、Runtime orchestration、Binance metadata/provider quantity interpretation、真实交易或 deployment authorization。G09B 必须独立冻结 exact rational PnL-to-Money boundary 和 Journal evidence；G09E 必须独立冻结 multiplier-aware notional/margin semantics。

### G09A Implementation Acceptance

1. Pure `crypto_quant_trading.derivatives` deep module 与 root exports 实现 frozen interface；未新增 Port、Adapter、Package、Profile、依赖或 Generic Ledger/Snapshot/Engine/Runner/Timeline derivative branch；
2. Linear perpetual Contract、exact reduced rational Basis、signed one-way State、caller-ordered Request、OPEN/ADD/REDUCE/CLOSE/FLIP Transition、Projection、Failure 与 Outcome 均使用 frozen schema v1 与 canonical hashes；
3. Long/Short open/add/reduce/close/flip、long-to-short/short-to-long crossing、closed Quantity、empty/prefix/equal-time/cross-zero semantics全部确定；Long 1@100 + 2@100.50 exact basis 为 `301/3`；
4. Duplicate occurrence、time regression、account/Venue/Instrument/Quantity/Price/Currency/Scale mismatch 按 frozen first-failure precedence 原子 fail closed，不返回 partial transition prefix；Result/Failure constructors 从 embedded Request 重算；
5. Exact-type closure 拒绝 tuple、Domain ID、Venue、Instrument、numeric/time/metadata 等 subclass forgery；Projector/constructors不排序、不 round、不使用 float/Decimal，也不 mutate 输入或 module state；
6. `test_derivative_boundary.py` 与 purity controls 拒绝 generic derivative branch、filesystem/network/process/dynamic import、mutable module/class/decorator state及 computed-string/alias/wildcard bypass；
7. Public export、65-file Import Boundary、65-source mypy、LSP/pi-lens、static golden、full regression、`uv lock --check` 与只读 blocker recheck 均通过。

G09A implementation 已冻结在 immutable commit `190efba252b5353267cdc336698d93fd3b3b524c`，状态为 `PASSED`。

验证记录：

```text
G09A contract                                                       7 passed
G09A static golden                                                  1 passed
Frozen public/boundary regression command                          44 passed
Full test suite                                                    874 passed
Trading-kernel import boundary                                     PASS (65 files)
mypy                                                                no issues (65 source files)
Primary LSP + pi-lens                                               clean
Read-only blocker recheck                                            NONE
uv lock --check                                                      PASS
Python                                                               3.13.5
```

## 70. G09B Linear Derivative Fill-to-Journal and Realized PnL Acceptance Card

```yaml
id: G09B
status: PASSED
depends_on:
  - G09A
  - G03
owner_package: trading-kernel derivative accounting
public_interface:
  - crypto_quant_domain.round_ratio
  - crypto_quant_trading.ExactLinearRealizedPnl
  - crypto_quant_trading.LinearDerivativeAccountingRequest
  - crypto_quant_trading.LinearDerivativeJournalEntry
  - crypto_quant_trading.LinearDerivativeAccountingResult
  - crypto_quant_trading.LinearDerivativeAccountingFailureCode
  - crypto_quant_trading.LinearDerivativeAccountingFailure
  - crypto_quant_trading.LinearDerivativeAccounting
  - crypto_quant_trading.LinearDerivativeLedgerReplayRequest
  - crypto_quant_trading.LinearDerivativeLedgerProjection
  - crypto_quant_trading.LinearDerivativeLedgerReplayFailureCode
  - crypto_quant_trading.LinearDerivativeLedgerReplayFailure
  - crypto_quant_trading.LinearDerivativeLedgerReplayOutcome
  - crypto_quant_trading.LinearDerivativeLedgerProjector
  - structural implementation of crypto_quant_trading.PositionAccountingModel
  - static synthetic linear-derivative-accounting golden fixture v1
test_commands:
  contract: uv run pytest -q tests/kernel/derivatives/test_linear_derivative_accounting.py
  fixture: uv run pytest -q tests/kernel/derivatives/test_linear_derivative_accounting_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py tests/architecture/test_derivative_boundary.py tests/kernel/journal/test_immutable_journal.py tests/kernel/ledger/test_generic_ledger.py tests/kernel/derivatives/test_linear_positions.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g09b-import-boundary-report.json
fixture_ids:
  - synthetic-linear-derivative-accounting-v1
expected_artifacts:
  - tests/fixtures/kernel/derivatives/linear-derivative-accounting-v1.json
  - build/acceptance/g09b-pytest.xml
  - build/acceptance/g09b-import-boundary-report.json
failure_contracts:
  - average-entry-or-realized-pnl-is-rounded-before-the-money-boundary
  - pnl-uses-after-state-basis-or-closes-the-flip-remainder
  - position-principal-notional-is-booked-as-cash
  - zero-or-rounded-zero-pnl-creates-a-zero-balance-change
  - fee-funding-or-unrealized-pnl-is-folded-into-the-fill-entry
  - settlement-account-venue-currency-or-scale-context-is-partially-translated
  - recorded-at-precedes-fill-execution-time
  - transition-or-quantization-identity-is-missing-from-journal-authority
  - journal-entry-subclass-does-not-revalidate-inherited-economic-effects
  - replay-sorts-or-trusts-evidence-outside-journal-order
  - ordinary-entry-changes-the-target-derivative-position
  - duplicate-fill-or-transition-lineage-mismatch-is-replayed
  - replayed-derivative-state-disagrees-with-generic-ledger-position-quantity
  - whole-key-realized-pnl-is-used-for-mixed-instrument-target-parity
  - generic-ledger-snapshot-engine-or-runtime-branches-on-linear-perpetual
  - accounting-books-fee-funding-margin-liquidation-or-unrealized-pnl
allowed_grade: development
evidence:
  - pytest-report
  - static-linear-derivative-accounting-golden-hash
  - exact-rational-to-money-quantization-evidence
  - transition-journal-component-and-request-hashes
  - specialized-journal-entry-inheritance-and-generic-ledger-evidence
  - long-short-reduce-close-flip-realized-pnl-evidence
  - per-transition-rounding-and-rounded-zero-evidence
  - journal-idempotency-conflict-and-prefix-replay-evidence
  - direct-position-versus-journal-replay-parity
  - mixed-journal-target-attribution-evidence
  - no-fee-funding-unrealized-or-runtime-mutation-evidence
  - import-boundary-report
  - static-type-report
passed_commit: 8896fc3acba1644e17a780bd64f151989d670bec
artifact_hashes:
  tests/fixtures/kernel/derivatives/linear-derivative-accounting-v1.json: sha256:3d507ce1387155dba88f0a4cccbc4a2572d2856112238c414d94c1c1ff946283
  build/acceptance/g09b-pytest.xml: sha256:984e892e0c90147407bc8556641074c374e6185746929c109788d051db85f037
  build/acceptance/g09b-import-boundary-report.json: sha256:7d6cecac1c5b1a22056300f323e04e4db6349bca3fd9307e77a44d63698fb1e3
```

### G09B Acceptance

1. G09B 只新增 pure `crypto_quant_trading.derivative_accounting` deep module、必要 root exports，并把既有 `crypto_quant_domain.numeric.rounding.round_ratio` 作为 `crypto_quant_domain.round_ratio` 公开复用；不得新增 Port、Adapter、Profile、Package、依赖，或修改 `AccountingJournal`、`GenericLedger`、`LedgerState`、`PortfolioSnapshotProjector`、Engine、Runner、Timeline 的 derivative branch；
2. `LinearDerivativeAccounting.translate_position_fact(request)` 是 G09B 唯一 Fill translation interface，并结构化实现既有 `PositionAccountingModel`。Request exact 保存一个已验证 G09A `LinearPositionTransition`、settlement `LedgerBalanceRegistration`、caller-supplied `QuantizationPolicy`、caller-supplied Journal Domain ID 与 `recorded_at: SimulationInstant`；不读取 current Ledger、Lot、Runtime state、Mark、Margin 或 provider metadata；
3. `ExactLinearRealizedPnl` exact 保存 settlement Currency、GCD-reduced signed integer numerator 与 positive denominator。OPEN/ADD exact 为 `0/1`。对 REDUCE/CLOSE/FLIP，令 prior sign `s=sign(before.quantity.units)`、closed raw Quantity `C`、Quantity factor `Q=10^quantity_scale.places`、multiplier units/factor `m/M`、exit Price units/factor `p/P`、prior basis `N/D`，则 exact PnL 为 `s*C*m*(p*D-N*P)/(Q*M*P*D)`；只使用 before basis，FLIP 只关闭 `abs(before.quantity.units)`，不计算 remainder 的 PnL；
4. Money boundary 只在每个 Transition 的最终一步调用 `round_ratio(exact_numerator * target_scale.factor, exact_denominator, rounding)` 一次。不得先量化 basis、price difference、multiplier、notional 或 closed leg；Python integer 无人工 overflow ceiling。`QuantizationPolicy.target_scale` 必须等于 settlement Cash registration Scale，Money Currency exact 为 Contract settlement Currency；所有既有 `RoundingPolicy` 值均由 caller 明示，Profile/G09H 再冻结 deployment policy；
5. `LinearDerivativeJournalEntry` 是 frozen `AccountingJournalEntry` subclass，使 immutable Accounting Journal 直接保存完整 Transition/Policy/Request evidence，而 Generic Ledger 只消费 inherited base economic fields，无 instrument branch。Subclass exact 额外保存 component ref、完整 Request、request hash 与 exact PnL，并在 constructor 中调用且重验 base invariants与全部 derivative fields；canonical preimage 不能只保存 hash-only external evidence；
6. 每个 Transition exact 产生一条 `FILL_BOOKED` Entry。Position `BalanceChange` exact 为 `after.quantity-before.quantity`。Perpetual principal/notional 不改变 Cash；只有 quantized realized PnL 非零时，Cash `BalanceChange` 与 `realized_pnl` tuple 各保存同一 Money。Exact PnL 为零或 quantized units 为零时省略 Cash change与 realized attribution；`fees=()`、`financing=()` 恒为空，Fee、Funding、Unrealized PnL 由后续独立 Gate/Entry 拥有；
7. Journal inherited fields exact 为 request Journal ID、`FILL_BOOKED`、Fill account/Venue/execution time、request recorded-at，以及 source IDs `{Fill ID, Order ID, Transition hash, Request hash}`。Source tuple 和 canonical Journal Entry hash必须绑定完整 G09A Transition、component、quantization与 settlement evidence；同一 target 的合法 G09A Transition sequence 还要求 caller-supplied `(recorded_at, journal_entry_id.value)` 按 Transition lineage严格递增。Journal append 的排序、同 ID 同 hash 幂等、同 ID 异 hash conflict 和 prefix publication规则继续完全由既有 `AccountingJournal` 拥有；misordered contexts不得被 translator重排，并在 Journal append 或 derivative replay lineage检查 fail closed；
8. Translation business failure enum values exact 为 `settlement_context_mismatch`、`quantization_scale_mismatch`、`recorded_before_execution`，precedence exact 按该顺序。Settlement context 要求 registration key 为同 account/Venue/settlement Currency 的 `CashBalanceKey`；quantization target Scale exact 等于 registration Scale；recorded-at instant 不早于 Fill execution time。Malformed exact types/canonical values继续 constructor fail closed，不冒充 business failure；Failure 嵌入完整 Request并重算首个 failure。Failure ordered `subject_ids` exact 为 `(code.value, str(fill.fill_id), journal_entry_id.value, fill.account_id, str(position_key.instrument_id), str(contract.instrument.settlement_currency))`；
9. Translation Result exact 保存 component ref、完整 Request、request hash 与 specialized Journal Entry；constructor 从 Request 重算 exact PnL、Money与完整 inherited/subclass Entry，拒绝 forged cash、position、PnL、source、transition、policy或 recorded evidence。`ProfilePortOutcome.input_hash` exact 为 Request hash并只允许 exactly-one Result/Failure；
10. `LinearDerivativeLedgerProjector.project(request)` 是独立 replay interface。Replay Request exact 保存完整 `AccountingJournal`、`LedgerSchema`、target Position key、Contract 与 settlement Cash key。Projector 只对已经按 G09A lineage发布的合法 target prefixes承诺 direct parity；它不重排 Journal，也不修复 caller-supplied booking context。Projector按 Journal published order重建 target exact State与 per-transition realized PnL，然后使用 branchless `GenericLedger(LedgerSchema).project(Journal)` 验证同一 prefix 的 signed Position Quantity exact parity；不要求 mixed Journal 中整个 Cash key 的 realized PnL 等于单一 target；
11. Journal authority exact 由 Journal 中持久化的 `LinearDerivativeJournalEntry` subclass提供。Projector先扫描全 Journal 的所有 specialized Entries，任一 Fill ID 重复都 fail closed，并归因于 Journal order中最早 repeated occurrence，即使两项属于不同 target。随后对 target Position，任何普通 `AccountingJournalEntry` Position change fail closed；target specialized Entry 必须匹配 request component/Contract/Position/Cash context，且 `transition.before` 等于当前 replay State。Unrelated Cash、Fee、Funding、other Instrument或 other Position Entries可共存且保持 generic replay；
12. Replay Failure enum values exact 为 `replay_context_mismatch`、`unsupported_target_position_entry`、`entry_context_mismatch`、`duplicate_fill_id`、`transition_lineage_mismatch`、`ledger_position_mismatch`。Total precedence exact 为：Request-level context → Journal-wide specialized duplicate Fill earliest repeated occurrence → 按 Journal 最早 target-affecting Entry逐项 unsupported → context → lineage → branchless Generic Ledger projection及其原生 schema/financial exceptions → final Position parity。AccountingJournal construction/order exceptions在 Projector调用前已成立并保持原类型；Generic Ledger exceptions在 derivative target-entry checks后、final parity前保持原类型，不包装为 derivative Failure；
13. Replay Projection exact 保存完整 Replay Request、request hash、Journal terminal cursor、target `LinearPositionState`、target exact realized PnL aggregate、per-transition quantized realized `Money` aggregate、target Journal Entry ID tuple与 Generic Ledger state hash。Exact aggregate使用有理数加法后 GCD-reduce；Money aggregate只加每条已量化结果，不重新量化 aggregate。Empty Journal产生 Flat、`0/1`与 zero Money；constructor重放并验证全部字段；
14. Direct/Journal parity exact 为：caller 为同一 G09A Transition prefix提供 lineage-preserving严格递增 booking keys，经 translation、Journal append 与 replay 后，Position State exact 等于该 prefix direct `LinearPositionProjection.final_state`，Generic Ledger signed Position Quantity一致，每条 Cash/PnL effect与 translation一致。Static golden必须验证全部合法 prefix、misordered booking-key fail-closed、Journal candidate input permutation归一化后的 published order、idempotent duplicate append、conflict append、mixed Journal和 ordinary target Position mutation；
15. Component key exact 为 `instrument.linear-perpetual.accounting.v1`、version 1、algorithm key exact 为 `linear-perpetual-transition-accounting-v1`。Component digest exact 为 `canonical_sha256({type="linear_derivative_accounting_component",schema_version=1,component_key,component_version=1,algorithm_key,exact_pnl_formula="sign(before_quantity_units)*closed_quantity_units*multiplier_units*(exit_price_units*basis_denominator-basis_numerator*price_scale_factor)/(quantity_scale_factor*multiplier_scale_factor*price_scale_factor*basis_denominator)",money_boundary="round_ratio(exact_numerator*target_scale_factor,exact_denominator,rounding)",quantization_scope="per_transition",journal_entry_type="linear_derivative_journal_entry",position_effect="after_minus_before",cash_effect="nonzero_quantized_realized_pnl_only",excluded_effects=("principal_notional","fees","funding","unrealized_pnl"),allowed_grade="development"})`；tuple order与所有 literal exact 固定；
16. 所有新增 public values 使用 `schema_version=1`、exact types、canonical tuple order与 `canonical_sha256` hashes。Canonical `type` exact 为 Exact PnL `exact_linear_realized_pnl`、Request `linear_derivative_accounting_request`、Journal subclass `linear_derivative_journal_entry`、Result `linear_derivative_accounting_result`、Failure `linear_derivative_accounting_failure`、Replay Request `linear_derivative_ledger_replay_request`、Replay Projection `linear_derivative_ledger_projection`、Replay Failure `linear_derivative_ledger_replay_failure`、Replay Outcome `linear_derivative_ledger_replay_outcome`；
17. Canonical preimage exact 分别为：Exact PnL `{type,schema_version,currency,numerator,denominator}`；Request `{type,schema_version,transition,settlement_cash_registration,pnl_quantization,journal_entry_id,recorded_at}`；Journal subclass `{type,schema_version,component_ref,request,request_hash,exact_realized_pnl,journal_entry}`，其中 `journal_entry` exact 为 inherited `AccountingJournalEntry.to_canonical_dict()`；Result `{type,schema_version,component_ref,request,request_hash,journal_entry}`；Failure `{type,schema_version,component_ref,request,request_hash,code,subject_ids}`；Replay Request `{type,schema_version,journal,ledger_schema,position_key,contract,settlement_cash_key}`；Replay Projection `{type,schema_version,request,request_hash,cursor,position_state,exact_realized_pnl,realized_pnl,journal_entry_ids,ledger_state_hash}`；Replay Failure `{type,schema_version,request,request_hash,code,journal_entry_id,fill_id}`；Replay Outcome `{type,schema_version,request_hash,result,failure}`。Replay Failure attribution exact 为：`REPLAY_CONTEXT_MISMATCH` 与 `LEDGER_POSITION_MISMATCH` 使用 `(journal_entry_id=None,fill_id=None)`；`UNSUPPORTED_TARGET_POSITION_ENTRY` 使用 offending Journal ID 与 `fill_id=None`；`ENTRY_CONTEXT_MISMATCH`、`DUPLICATE_FILL_ID`、`TRANSITION_LINEAGE_MISMATCH` 使用 offending specialized Journal ID 与其 Fill ID；
18. Static golden沿用 G09A non-unit multiplier `0.125`、Quantity Scale 3、Price Scale 2，并使用 settlement Scale 2。至少冻结 Long/Short REDUCE/CLOSE/FLIP gain/loss、OPEN/ADD zero、FLIP only-old-side、prior basis `301/3`、positive/negative HALF_EVEN/HALF_UP ties `±0.005/±0.015`、rounded-zero、省略 zero change、per-transition-versus-aggregate sentinel、大整数、每个 replay prefix、mixed Journal、failure precedence、constructor/hash forgery、Journal idempotency/conflict与 no-mutation；
19. Purity沿用 G09A scanner：只允许 stdlib、`crypto_quant_domain`、G09A derivatives、generic Journal/Ledger/Ports imports；拒绝 filesystem、network/provider/process/database/cloud、dynamic import、mutable module/class/decorator state与 wall clock。`test_derivative_boundary.py` 继续拒绝 Generic Ledger、SnapshotProjector、Engine、Runner、Timeline 的 `LINEAR_PERPETUAL` branch/reference；
20. G09B 不拥有 Unrealized PnL/Mark/Snapshot valuation、Fee、Funding、Margin、Liquidation、Settlement availability、Runtime dispatch、Profile composition、Binance metadata/provider parity、真实交易或 deployment authorization。G09D拥有 Funding accounting，G09F拥有 account MarginProjection，G09H才注入 Runtime composition。

G09B 的公式、Journal subclass seam、system conventions与非拥有范围冻结在本 Acceptance Card 和 architecture/plan；无外部 provider选择。若后续 Profile 需要不同 realized-PnL settlement/rounding policy，必须由 caller-injected QuantizationPolicy/Profile identity显式区分，不能修改历史 G09B Result。

### G09B Implementation Acceptance

1. Pure `derivative_accounting` deep module 与 public `round_ratio` export 实现 frozen G09B interface；AccountingJournal、GenericLedger、Snapshot、Engine、Runner、Timeline 与 Ports 均未加入 derivative branch；
2. Exact signed rational PnL 使用 before basis、closed quantity、non-unit multiplier与 Fill exit price一次计算，Money 只在每 Transition 最终 boundary 通过 caller QuantizationPolicy量化；OPEN/ADD、zero与rounded-zero不产生 Cash/PnL zero effects；
3. Frozen specialized `LinearDerivativeJournalEntry` 继承并重验完整 base economics，保存 component/Request/exact PnL authority；Journal order/hash/idempotency/conflict与 Generic Ledger branchless projection继续复用既有实现；
4. Replay 先验证 request context、全 Journal exact specialized Fill uniqueness与 unauthorized subclass，再按 Journal order检查 ordinary target mutation、entry context与 G09A lineage，随后保留 Generic Ledger原生异常并验证 signed Position parity；
5. Replay Projection冻结每个 prefix direct-state parity、exact rational aggregate、per-transition quantized Money aggregate、terminal cursor、target Journal IDs与 Ledger state hash；mixed cash/other entries不污染 target attribution；
6. Static golden冻结 long/short REDUCE/CLOSE/FLIP gain/loss、prior basis `301/3`、正负 rounding ties、rounded zero、per-transition-vs-aggregate、large integers、全部 prefixes、booking permutation/misorder、idempotency/conflict、mixed/native precedence、failure/forgery与真实 no-mutation controls；
7. Public exports、66-file Import Boundary、66-source mypy、LSP/pi-lens、static golden、full regression、`uv lock --check` 与只读 blocker verdict均通过。

G09B implementation 已冻结在 immutable commit `8896fc3acba1644e17a780bd64f151989d670bec`，状态为 `PASSED`。

验证记录：

```text
G09B contract                                                      12 passed
G09B static golden                                                  1 passed
Frozen public/boundary regression command                          51 passed
Full test suite                                                    887 passed
Trading-kernel import boundary                                     PASS (66 files)
mypy                                                                no issues (66 source files)
Primary LSP + pi-lens                                               clean
Read-only blocker recheck                                            NONE
uv lock --check                                                      PASS
Python                                                               3.13.5
```

## 71. G09C Funding Publication and Eligibility Acceptance Card

```yaml
id: G09C
status: PASSED
depends_on:
  - G09A
  - G09B
  - WP-06A
  - WP-06B
owner_package: trading-kernel funding eligibility
public_interface:
  - crypto_quant_trading.LinearFundingEligibilityComponentRef
  - crypto_quant_trading.FundingSlotId
  - crypto_quant_trading.LinearFundingPublicationStatus
  - crypto_quant_trading.LinearFundingRatePublicationCandidate
  - crypto_quant_trading.LinearFundingEligibilityPositionSnapshot
  - crypto_quant_trading.LinearFundingEligibilityRequest
  - crypto_quant_trading.LinearFundingEligibility
  - crypto_quant_trading.LinearFundingEligibilityFailureCode
  - crypto_quant_trading.LinearFundingEligibilityFailure
  - crypto_quant_trading.LinearFundingEligibilityOutcome
  - crypto_quant_trading.LinearFundingEligibilityResolver
  - static synthetic linear-funding-eligibility golden fixture v1
test_commands:
  contract: uv run pytest -q tests/kernel/derivatives/test_linear_funding_eligibility.py
  fixture: uv run pytest -q tests/kernel/derivatives/test_linear_funding_eligibility_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py tests/architecture/test_derivative_boundary.py tests/market_data/bundles/test_market_bundle_reader.py tests/runtime/timeline/test_deterministic_timeline.py tests/kernel/derivatives/test_linear_positions.py tests/kernel/derivatives/test_linear_derivative_accounting.py tests/kernel/journal/test_immutable_journal.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g09c-import-boundary-report.json
fixture_ids:
  - synthetic-linear-funding-eligibility-v1
expected_artifacts:
  - tests/fixtures/kernel/derivatives/linear-funding-eligibility-v1.json
  - build/acceptance/g09c-pytest.xml
  - build/acceptance/g09c-import-boundary-report.json
failure_contracts:
  - funding-rate-is-visible-before-full-publication-availability
  - slot-id-depends-on-account-rate-revision-or-source
  - publication-revision-chain-is-branched-gapped-reordered-or-duplicated
  - publication-after-target-funding-utc-is-backdated
  - cancelled-final-publication-creates-eligibility
  - eligibility-uses-current-position-after-the-cutoff
  - same-utc-later-phase-journal-entry-enters-the-cutoff-prefix
  - shortened-or-forged-journal-prefix-is-accepted
  - availability-projection-or-cutoff-state-is-not-authoritative-g09b-replay
  - missing-publication-or-position-evidence-produces-partial-success
  - publication-or-position-revision-conflict-is-silently-selected
  - result-creates-funding-obligation-cash-journal-ledger-or-margin-effect
  - market-event-timeline-journal-or-ledger-is-mutated
  - generic-ledger-snapshot-engine-runner-or-timeline-branches-on-funding
  - profile-or-provider-specific-schedule-finality-mark-or-accounting-leaks-into-g09c
allowed_grade: development
evidence:
  - pytest-report
  - static-linear-funding-eligibility-golden-hash
  - market-event-publication-id-and-hash-binding
  - full-simulation-instant-visibility-and-timeline-parity
  - stable-funding-slot-identity-evidence
  - closed-publication-revision-chain-evidence
  - g09b-journal-prefix-cutoff-and-replay-evidence
  - long-short-flat-historical-position-capture
  - later-position-non-substitution-evidence
  - deterministic-idempotent-slot-observation
  - no-accounting-obligation-or-runtime-mutation-evidence
  - import-boundary-report
  - static-type-report
passed_commit: a5b90fbeac829953873f4ce4774eba7ab2d6ce11
artifact_hashes:
  tests/fixtures/kernel/derivatives/linear-funding-eligibility-v1.json: sha256:cb2dcf1060f9eff7dc681766975118ffe9ca2e18bc343b4cb38e0d10ecf7cfe5
  build/acceptance/g09c-pytest.xml: sha256:380c1f0989062dc687fbf9c4ecda086a9ac3f62c3ceb4e6a99eba83bd7777c11
  build/acceptance/g09c-import-boundary-report.json: sha256:26d838737f9915a57c563ed18cc3601af19649352e708caa87ca105d42f49e3d
```

### G09C Acceptance

1. G09C 只新增 pure `crypto_quant_trading.funding` deep module与必要 root exports；不得新增 Port、Adapter、Profile、Package、依赖，或修改 MarketEvent、Timeline、AccountingJournal、GenericLedger、SnapshotProjector、Engine、Runner。`LinearFundingEligibilityResolver.resolve(request)` 是唯一行为 interface，返回 dedicated `LinearFundingEligibilityOutcome`，不使用 `ProfilePortOutcome`、不占用 `FINANCING_MODEL` port identity且不结构化实现 `FinancingModel`；G09D 才实现 Funding settlement/accounting；
2. `FundingSlotId` exact 保存 `InstrumentId`、`target_funding_time: UtcInstant` 与稳定 value。Value exact 为 `funding-slot-v1:` 加 `canonical_sha256({type="funding_slot_semantic_key",schema_version=1,instrument_id,target_funding_time})` 去掉 `sha256:` 前缀。Slot identity 只绑定 Instrument 与目标 Funding UTC，不绑定 account、rate、revision、Event/source、availability、eligibility phase、Position或 capture；constructor/classmethod 必须重算并拒绝 forged value；
3. `LinearFundingPublicationStatus` enum values exact 为 `FINAL_RATE` 与 `CANCELLED`。`LinearFundingRatePublicationCandidate` 保存 Slot、status、optional published Rate、source MarketEvent ID/hash、event time、完整 `publication_available_at=SimulationInstant(available_time,phase,source_sequence)`、revision/supersession和 source key/hash。`FINAL_RATE` 必须有 Rate，`CANCELLED` 必须没有 Rate；Rate 可正、负或零，basis exact 为 `funding_fraction_of_notional`，G09C不量化、不应用且不声称 provider最终性；
4. Publication 是普通 immutable `MarketEvent` handoff evidence。Candidate 只接受 caller已映射的 Event fields，production module 不导入 market-data/runtime。Event time与available UTC均不得晚于 Slot target funding UTC；同一目标 UTC的 publication可在 eligibility phase之前或之后变得可用，但 Strategy/caller在完整 `publication_available_at` 前不能观察 Rate。Golden通过实际 `MarketEvent`、`InMemoryMarketBundleReader` 与 `DeterministicTimeline`冻结 Event ID/hash、同 UTC phase/sequence visibility、reader page size、timeline batch size和输入顺序 parity；
5. Request 的 `publications` 是 caller-supplied exact tuple与 supplied closed linear revision chain，按 `(publication_available_at,event_id,revision_id)` 已排序。Chain exact 要求同一 Slot、Event ID唯一、revision ID唯一、第一项 `supersedes_revision_id=None`，后续每项 exact supersede紧邻前一 revision，完整 `publication_available_at` 严格递增且无 branch/gap/reorder/duplicate；相同 availability instant不得依靠 Event ID tie-break绕过 WP-06A/WP-06B ordering identity。Resolver选最后一项；final `CANCELLED` 返回 structured cancellation failure。Cross-Request omitted later revision、same identity conflicting reuse与 provider correction/finality history由 G09H/G10E fail closed，但单 Request 内完整 chain由 G09C验证；
6. `LinearFundingEligibilityRequest` exact 保存 Slot、Position key、完整 G09A Contract、Eligibility Instant、Publication tuple、optional Position Snapshot与 captured-at。Position key必须匹配 Contract；Eligibility UTC exact 等于 Slot target funding time，并使用 frozen `TimelinePhase(rank=100,code=funding_eligibility)` 与 `SourceSequence(0)`；`captured_at >= eligibility_instant`。该 phase是 deterministic engine ordering convention，不声称任何 provider在此 phase完成结算；
7. `LinearFundingEligibilityPositionSnapshot` 是唯一 historical eligibility Position authority。它保存 snapshot/eligibility-series/revision identity、optional supersession、Slot、Eligibility Instant、available-at、`eligibility_cursor: JournalReplayCursor`、完整 G09B `availability_projection: LinearDerivativeLedgerProjection` 与 cutoff `position_state: LinearPositionState`。Snapshot constructor必须验证 exact types和 hashes，并从 availability projection嵌入的同一 authoritative Journal重建 cutoff prefix；不得接受裸 State、current Ledger Position、PortfolioSnapshot、Fill tuple或 opaque source hash替代；
8. Eligibility cutoff exact 为 availability Journal 中所有 `entry.recorded_at < eligibility_instant` 的最大 prefix，比较完整 `SimulationInstant`。同 UTC较早 phase/sequence进入，exact eligibility或更晚 phase/sequence排除。`eligibility_cursor` 必须等于 availability Journal在该最大位置的 cursor/hash；constructor用该 prefix构造 immutable AccountingJournal并调用 G09B `LinearDerivativeLedgerProjector`，重算结果必须等于 snapshot `position_state`。Availability projection必须在 Snapshot内部匹配同 Position/Contract/Cash authority；Journal entries相对 available-at的时间因果由 Resolver而非 constructor判断；
9. Resolver要求 Snapshot `available_at >= eligibility_instant`、availability Journal全部 entries `recorded_at <= available_at`且 Snapshot不得晚于 Request captured-at；不满足时按 frozen business failure返回。Snapshot只声明 caller提供的 authoritative Journal在 available-at时的完整 prefix；跨 Snapshot identity-history与外部 Journal completeness由 G09H composition拥有。Root与superseding snapshot revision均可表达，但 G09C v1只接受 supplied `supersedes_revision_id=None`；后续 current close/flip/position、availability projection terminal State或额外 Journal entries不得替代或重算已冻结 cutoff State。Flat State是成功 evidence，不等于 missing；
10. Result exact 保存 dedicated component ref、完整 Request/request hash、Slot、selected Publication hash/Event/revision identities、Snapshot hash、historical Position State/state hash、published Rate、eligibility instant与 captured-at。Result constructor从 embedded Request执行完整 first-failure evaluation并要求结果为 `None`，随后重算 selected final Publication、cutoff replay与全部 identities；相同 canonical Request产生相同 Result/Outcome hash。G09C只产生一个 immutable Slot/account eligibility observation，不创建 Funding obligation、Journal Entry、Cash/Ledger effect、Fee、Funding payment、Margin或Settlement mutation；
11. Business Failure enum values与 first-failure precedence exact 为：`MISSING_PUBLICATION` → `SLOT_CONTEXT_MISMATCH` → `POSITION_CONTEXT_MISMATCH` → `INVALID_ELIGIBILITY_INSTANT` → `PUBLICATION_SLOT_MISMATCH` → `UNSUPPORTED_RATE_BASIS` → `INVALID_PUBLICATION_REVISION_SET` → `INVALID_PUBLICATION_CAUSALITY` → `LATE_PUBLICATION` → `PUBLICATION_NOT_AVAILABLE` → `FUNDING_SLOT_CANCELLED` → `MISSING_ELIGIBILITY_POSITION` → `UNSUPPORTED_POSITION_REVISION` → `SNAPSHOT_SLOT_MISMATCH` → `SNAPSHOT_POSITION_CONTEXT_MISMATCH` → `ELIGIBILITY_INSTANT_MISMATCH` → `INVALID_POSITION_CAPTURE_CAUSALITY` → `POSITION_SNAPSHOT_NOT_AVAILABLE`。Exact predicates分别为：(1) publications empty；(2) Request Slot Instrument不等于 Contract Instrument；(3) Request Position key Venue/Instrument不等于 Contract；(4) Request eligibility UTC/phase/sequence不等于 Slot target UTC与 frozen boundary，或 captured-at早于 eligibility；(5) 任一 Publication Slot不等于 Request Slot；(6) 任一 `FINAL_RATE` published Rate basis不等于 `funding_fraction_of_notional`；(7) publications非 strict canonical order、Event/revision重复、root supersedes非空、任一 successor未紧邻 supersede前一 revision，或完整 availability不严格递增；(8) 任一 publication available UTC早于 event time；(9) 任一 event time或available UTC晚于 Slot target funding UTC；(10) 任一 supplied publication完整 availability晚于 Request captured-at；(11) selected final status为 `CANCELLED`；(12) Position Snapshot缺失；(13) Snapshot `supersedes_revision_id`非空；(14) Snapshot Slot不等于 Request Slot；(15) Snapshot cutoff State或availability projection的Position/Contract/Cash authority不等于 Request context；(16) Snapshot eligibility instant不等于 Request eligibility；(17) Snapshot available-at早于 eligibility，或availability Journal任一 Entry recorded-at晚于 Snapshot available-at；(18) Snapshot available-at晚于 Request captured-at。多缺陷只返回第一项。Candidate/Snapshot/Request constructors只验证 exact type、canonical/hash/status-rate shape与 Snapshot内部 cursor/prefix/G09B replay完整性，不验证上述跨对象 business规则；全部 18 项必须可构造并由 Resolver structured fail closed；
12. Failure ordered `subject_ids` exact 为 `(code.value, slot_id.value, selected_or_last_event_id or "missing-funding-publication", snapshot_id or "missing-eligibility-position", position_key.account_id, str(contract.instrument.instrument_id))`。Failure嵌入完整 Request并重算首个 failure；`LinearFundingEligibilityOutcome` exact 保存 dedicated component ref、Request hash与 exactly-one Result/Failure，并重验 component/request identities；
13. Dedicated `LinearFundingEligibilityComponentRef` 不含 port type；component key exact 为 `instrument.linear-perpetual.funding-eligibility.v1`、version 1、algorithm key exact 为 `linear-funding-publication-eligibility-v1`。Component digest preimage exact 为 `{type="linear_funding_eligibility_component",schema_version=1,component_key,component_version=1,algorithm_key,slot_key="instrument_id+target_funding_time",rate_basis="funding_fraction_of_notional",eligibility_phase=TimelinePhase(100,"funding_eligibility"),eligibility_sequence=SourceSequence(0),eligibility_cutoff="journal.recorded_at<eligibility_instant",publication_revision_policy="closed_linear_chain",position_revision_policy="supplied_root_only",allowed_grade="development"}`；ComponentRef canonical preimage exact 为 `{type="linear_funding_eligibility_component_ref",schema_version=1,component_key,component_version,component_digest}`；
14. 所有新增 public values使用 `schema_version=1`、exact types、canonical tuple order与 `canonical_sha256` hashes。Canonical type/preimage exact 为：Slot `funding_slot_id {type,schema_version,instrument_id,target_funding_time,value}`；Publication `linear_funding_rate_publication_candidate {type,schema_version,slot_id,status,published_rate,event_id,event_hash,event_time,publication_available_at,revision_id,supersedes_revision_id,source_key,source_hash}`；Snapshot `linear_funding_eligibility_position_snapshot {type,schema_version,snapshot_id,eligibility_series_id,revision_id,supersedes_revision_id,slot_id,eligibility_instant,available_at,eligibility_cursor,availability_projection,position_state}`；Request `linear_funding_eligibility_request {type,schema_version,slot_id,position_key,contract,eligibility_instant,publications,position_snapshot,captured_at}`；Result `linear_funding_eligibility {type,schema_version,component_ref,request,request_hash,slot_id,publication_hash,event_id,event_hash,publication_revision_id,snapshot_hash,position_state,state_hash,published_rate,eligibility_instant,captured_at}`；Failure `linear_funding_eligibility_failure {type,schema_version,component_ref,request,request_hash,code,subject_ids}`；Outcome `linear_funding_eligibility_outcome {type,schema_version,component_ref,request_hash,result,failure}`；
15. Publication hash、snapshot hash、request hash、eligibility hash与failure hash exact 为 `canonical_sha256(value)`。Publication Candidate event/source hashes使用 canonical `sha256:<64 lowercase hex>`；Slot/Event/revision/source tuple顺序固定。Snapshot hash绑定完整 availability projection和 cutoff State，因此 Journal extension、cursor、late current Position或 G09B replay identity变化都会显式改变新 Snapshot identity，而不会 retroactively改变历史 Result；
16. Static golden沿用 G09A/G09B synthetic Contract，至少冻结：positive/negative/zero Rates；Slot derivation/sensitivity及对 account/rate/revision/source/capture的不变性；actual MarketEvent-to-Candidate ID/hash；same-UTC pre-availability invisibility与 boundary visibility；Reader/Timeline parity；root/corrected/cancelled chains；branch/gap/reorder/duplicate revision failures；Long/Short/Flat cutoff States；same-UTC earlier/later Journal phases；每个 prefix cursor/hash；later close/flip/current State non-substitution；all 18 failures与 multi-defect precedence；constructor/result/failure/slot/cursor/hash forgery；same Request idempotency及 no Journal/Ledger/Timeline/module mutation；
17. Purity沿用 derivative scanner：production只允许 stdlib、`crypto_quant_domain`、G09A derivatives、G09B derivative-accounting、generic Journal/Ports imports；拒绝 filesystem、network/provider/process/database/cloud、dynamic import、MarketBundle/Runtime import、mutable module/class/decorator state与 wall clock。`test_derivative_boundary.py` 继续拒绝 Generic Ledger、SnapshotProjector、Engine、Runner、Timeline 的 funding/linear derivative branch或 reference；
18. G09C 不拥有 Strategy ObservationView、provider stream/schedule、estimated/final rate mapping、Applied Rate选择、Funding Mark、settlement Currency/Scale、cash direction、obligation、Funding Journal、Ledger mutation、Fee、Margin、Liquidation、Runtime dispatch、Binance parity、真实交易或 deployment authorization。G09D拥有 settlement/accounting；G09H拥有 closed cross-Query identity-history与 composition completeness；G10E拥有 Binance publication/finality/correction/source Adapter。

G09C 的 Slot、revision chain、historical cutoff与 system ordering convention已冻结，无外部 provider选择。若 provider证据要求不同 publication finality或 eligibility boundary，必须由 G10E mapping或先将 G09C退回 DRAFT修订，不能静默改写历史 Result。

### G09C Implementation Acceptance

1. Pure `funding` deep module与 root exports实现 dedicated funding eligibility seam；未新增/占用 Financing Port、Profile、Adapter、Package、依赖或 Generic Ledger/Snapshot/Engine/Runner/Timeline funding branch；
2. Stable Slot只绑定 Instrument与target funding UTC；signed/zero final Rate、cancelled status、actual MarketEvent ID/hash/full availability、strict closed revision chain与same-UTC phase visibility均按 frozen contract fail closed；
3. Historical Position Snapshot嵌入完整 G09B availability projection与最大 `recorded_at < eligibility_instant` Journal prefix；constructor和Resolver均重新执行full/cutoff replay与canonical hash检查，later close/flip/current State不能替代历史 cutoff；
4. Resolver按 frozen 18-code precedence处理publication/slot/position/eligibility/revision/causality/visibility/cancellation/snapshot context与capture failures；Result/Failure/Outcome重算完整 Request、component、Slot、publication、snapshot与State identities；
5. Static golden冻结positive/negative/zero Rates、Slot sensitivity/invariance、MarketEvent reader/timeline parity、root/corrected/cancelled与invalid chains、Long/Short/Flat及same-UTC cutoff、每个prefix cursor/hash、全部18 failures、forgery/idempotency与no Journal/Ledger/Timeline/module mutation；
6. Enhanced derivative boundary scanner拒绝broad funding literals/identifiers、computed/dynamic imports、custom mutable module singleton与generic funding/derivative references，同时只允许frozen immutable module constructors；
7. Public exports、67-file Import Boundary、67-source mypy、LSP/pi-lens、static golden、full regression、`uv lock --check`与只读 blocker verdict均通过。

G09C implementation 已冻结在 immutable commit `a5b90fbeac829953873f4ce4774eba7ab2d6ce11`，状态为 `PASSED`。

验证记录：

```text
G09C contract                                                       4 passed
G09C static golden                                                  1 passed
Frozen public/boundary regression command                          77 passed
Full test suite                                                    898 passed
Trading-kernel import boundary                                     PASS (67 files)
mypy                                                                no issues (67 source files)
Primary LSP + pi-lens                                               clean
Read-only blocker recheck                                            NONE
uv lock --check                                                      PASS
Python                                                               3.13.5
```

## 72. G09D Funding Settlement and Accounting Acceptance Card

```yaml
id: G09D
status: PASSED
depends_on:
  - G09B
  - G09C
owner_package: trading-kernel financing/accounting
public_interface:
  - crypto_quant_trading.LinearFundingApplicationKey
  - crypto_quant_trading.LinearFundingApplicationIdentity
  - crypto_quant_trading.LinearFundingMarkEvidence
  - crypto_quant_trading.LinearFundingSettlementEvidence
  - crypto_quant_trading.ExactLinearFundingCashFlow
  - crypto_quant_trading.LinearFundingSettlementRequest
  - crypto_quant_trading.LinearFundingJournalEntry
  - crypto_quant_trading.LinearFundingSettlementResult
  - crypto_quant_trading.LinearFundingSettlementFailureCode
  - crypto_quant_trading.LinearFundingSettlementFailure
  - crypto_quant_trading.LinearFundingAccounting
  - crypto_quant_trading.LinearFundingJournalReplayRequest
  - crypto_quant_trading.LinearFundingJournalProjection
  - crypto_quant_trading.LinearFundingJournalReplayFailureCode
  - crypto_quant_trading.LinearFundingJournalReplayFailure
  - crypto_quant_trading.LinearFundingJournalReplayOutcome
  - crypto_quant_trading.LinearFundingJournalProjector
  - static synthetic linear-funding-accounting golden fixture v1
test_commands:
  contract: uv run pytest -q tests/kernel/derivatives/test_linear_funding_accounting.py
  fixture: uv run pytest -q tests/kernel/derivatives/test_linear_funding_accounting_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py tests/architecture/test_derivative_boundary.py tests/domain/accounting/test_accounting_contracts.py tests/kernel/derivatives/test_linear_positions.py tests/kernel/derivatives/test_linear_derivative_accounting.py tests/kernel/derivatives/test_linear_funding_eligibility.py tests/kernel/marks/test_mark_resolver.py tests/kernel/journal/test_immutable_journal.py tests/kernel/ledger/test_generic_ledger.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g09d-import-boundary-report.json
fixture_ids:
  - synthetic-linear-funding-accounting-v1
expected_artifacts:
  - tests/fixtures/kernel/derivatives/linear-funding-accounting-v1.json
  - build/acceptance/g09d-pytest.xml
  - build/acceptance/g09d-import-boundary-report.json
failure_contracts:
  - applied-rate-differs-from-g09c-final-published-rate
  - funding-payment-uses-current-position-or-average-entry-basis
  - funding-mark-uses-non-funding-purpose-fallback-or-post-slot-observation
  - funding-mark-policy-context-scale-or-availability-is-invalid
  - funding-cash-is-pre-rounded-or-rounded-more-than-once
  - long-short-positive-negative-or-zero-rate-cash-direction-is-wrong
  - settlement-cash-currency-account-venue-or-scale-mismatch
  - funding-application-id-depends-on-rate-mark-amount-or-request-hash
  - same-account-slot-is-applied-twice-under-different-journal-identity
  - changed-evidence-for-the-same-account-slot-is-silently-rebooked
  - ordinary-or-subclassed-funding-journal-entry-bypasses-specialized-replay
  - zero-funding-application-loses-journal-identity
  - generic-ledger-adds-a-funding-or-derivative-branch
  - settlement-publication-eligibility-mark-journal-or-ledger-authority-is-mutated
  - provider-runtime-margin-liquidation-or-deployment-semantics-leak-into-g09d
allowed_grade: development
evidence:
  - pytest-report
  - static-linear-funding-accounting-golden-hash
  - exact-rational-funding-cash-flow-and-single-quantization-evidence
  - long-short-flat-positive-negative-zero-rate-direction-evidence
  - funding-purpose-mark-and-stale-policy-identity-evidence
  - deterministic-account-slot-settlement-and-journal-id-evidence
  - same-id-journal-idempotency-and-conflict-evidence
  - alternate-id-full-journal-duplicate-and-conflict-audit
  - publication-eligibility-rate-mark-and-settlement-source-lineage
  - branchless-generic-ledger-cash-financing-and-position-parity
  - zero-and-rounded-zero-funding-entry-evidence
  - import-boundary-report
  - static-type-report
passed_commit: 913e3ac81cc68a454f32a3f48b6444ac4604bb0e
artifact_hashes:
  tests/fixtures/kernel/derivatives/linear-funding-accounting-v1.json: sha256:047dc67b5c3a8191057d8c14166596a66c4b282ebe08b1cd9e9141c868a6bea9
  build/acceptance/g09d-pytest.xml: sha256:f263714ea4a93bb7c8c4f9fb0edc4ceda6a180563e255c54f4055bfb58b92397
  build/acceptance/g09d-import-boundary-report.json: sha256:b6fb0460ddc08a04f9c2117a02a4cddec9802774c92b9ecc34f137d7e32b93c1
```

### G09D Acceptance

1. G09D 只新增 pure `crypto_quant_trading.funding_accounting` deep module、必要 root exports，以及通用 `AccountingJournalEntry` 对 `FUNDING_APPLIED` zero-effect evidence 的最小允许项；不得新增 Port、Profile、Adapter、Package、依赖，或修改 Generic Ledger、SnapshotProjector、Engine、Runner、Timeline。`LinearFundingAccounting.assess_financing(request)` 结构化实现既有 `FinancingModel`，exact 消费 `LinearFundingSettlementRequest` 并返回 `ProfilePortOutcome[LinearFundingSettlementResult, LinearFundingSettlementFailure]`；它只翻译 Entry，不 append/mutate Journal；
2. `LinearFundingApplicationKey` exact 保存 account ID、G09C `FundingSlotId` 与稳定 value。Value exact 为 `funding-application-v1:` 加 `canonical_sha256({type="linear_funding_application_semantic_key",schema_version=1,account_id,funding_slot_id})` 去掉 `sha256:` 前缀；constructor/classmethod 重算并拒绝 forged value。语义唯一性 exact 为 `(account_id, funding_slot_id)`，Rate、Mark、Money、Currency、Scale、timing、revision、source、Request/Entry/Journal hash均不进入 key；
3. `LinearFundingApplicationIdentity` exact 保存 Application Key、`IdentityNamespace`、Semantic Run ID、`settlement_id: DomainIdKind.SETTLEMENT` 与 `journal_entry_id: DomainIdKind.JOURNAL`。两个 ID 都使用既有 `derive_domain_id()`、同一 Namespace/Run、`semantic_key=application_key.value.encode("utf-8")` 与 ordinal `0`，仅 kind 不同；constructor必须重新派生并拒绝 caller提供的非规范 ID，不允许由 Entry 或 Journal hash反向派生。Identity canonical payload不直接传入不可序列化对象，而把Namespace exact编码为 `{value: identity_namespace.value, version: identity_namespace.version, algorithm: identity_namespace.algorithm}`；
4. `LinearFundingSettlementEvidence` 是账户经济事件证据，exact 保存 Application Key、`effective_time=slot.target_funding_time`、`applied_at: SimulationInstant`、Applied Rate、event ID/hash、revision/supersession、source key/hash。Applied Rate必须 exact 等于 G09C Eligibility 的 final `published_rate`，包括 units、Scale 与 basis；v1 basis exact 为 `funding_fraction_of_notional`。Settlement evidence不拥有 provider Rate转换或 finality选择；这些仍由 G09C/G10E caller mapping完成；
5. `LinearFundingMarkEvidence` exact 只保存完整 `ResolvedMark` 与用于该 resolution 的完整 `StaleMarkPolicy`；不增加caller可伪造的full-phase availability字段。Resolved Mark与Policy purpose都必须 exact 为 `PricePurpose.FUNDING`；Instrument、quote/settlement Currency和Price Scale必须匹配 Contract；Price units必须 strictly positive；`resolved_at` exact 等于 Slot target funding UTC；authoritative mark availability exact 使用既有 Mark Resolver冻结的 `ResolvedMark.available_at: UtcInstant`，并要求不晚于 Settlement `applied_at.instant`。Policy key/version/hash、`age_nanoseconds == resolved_at - observed_at`、age/max-age与 forward-fill allowance必须重新验证；禁止用 `SETTLEMENT`、`VALUATION`、`MARGIN`、`LIQUIDATION`、execution/trade/bar price fallback；
6. `LinearFundingSettlementRequest` exact 保存 optional Eligibility、optional Settlement Evidence、optional Funding Mark Evidence、Application Identity、Position key、完整 G09A Contract、settlement Cash `LedgerBalanceRegistration` 与 payment `QuantizationPolicy`。Optional evidence只为构造 structured missing-evidence failures；Result/Entry必须嵌入无 business failure的完整 Request。Application Key account/Slot、Position key、Eligibility、Contract、Settlement Evidence、Mark与Cash registration必须全部 context-equal；尤其 `request.contract == eligibility.request.contract == eligibility.position_state.contract` 使用完整 `LinearPerpetualContract` exact equality，不能只比较 Instrument；
7. Funding exact cash flow只使用 G09C historical cutoff `position_state.quantity`，不读 current Ledger/Portfolio/Fill、availability projection terminal State或 average-entry basis。若 signed Quantity 为 `q/Q`、positive contract multiplier为 `m/M`、positive Funding Mark为 `p/P`、signed Applied Rate为 `r/R`，账户 settlement-currency cash exact 为 `F = -(q*m*p*r)/(Q*M*P*R)`。`ExactLinearFundingCashFlow` 保存 Currency、GCD-reduced signed numerator与positive denominator；zero canonical 为 `0/1`；
8. Money boundary每个 Application Key只调用 public `round_ratio(exact.numerator * target_scale.factor, exact.denominator, rounding)` 一次。Quantity、Multiplier、Mark、Rate、Notional和中间 Funding amount不得预先量化、float/Decimal转换或 aggregate 后统一舍入。Positive Rate时 Long支付/Short收取，Negative Rate反向，Flat或zero Rate exact 为零；rounded zero仍是已应用的 Funding经济事实；
9. Settlement Cash registration必须是 exact account/Venue/Contract settlement Currency的 `CashBalanceKey`，Registration Scale必须等于 Quantization target Scale；Money Currency/Scale由该 authority唯一决定，不进行 FX、stablecoin peg、隐式 rescale或从 Mark自行选择 Currency。`applied_at` 是唯一 booking/recording boundary：必须不早于 Eligibility captured-at，且`ResolvedMark.available_at <= applied_at.instant`；Journal `effective_time=slot.target_funding_time`、`recorded_at=applied_at`；
10. Result exact 保存 component ref、完整 Request/request hash、Application Key、Exact Cash Flow、quantized payment Money和 frozen `LinearFundingJournalEntry`。Entry继承 `AccountingJournalEntry`，entry type exact 为 `FUNDING_APPLIED`，ID来自 Application Identity，account/Venue/effective/recorded exact 按上述规则；nonzero payment同时产生同额 Cash `BalanceChange` 与单一 `financing` attribution，`realized_pnl=fees=()` 且无 Position effect；exact zero或rounded zero保留 specialized Entry但全部经济 tuple为空；
11. 通用 `AccountingJournalEntry` 的 empty-effect allowlist只从既有 `CORPORATE_ACTION_ENTITLEMENT_BOOKED`扩展到 `FUNDING_APPLIED`，不改变其他 Entry type。普通或任意 subclass `FUNDING_APPLIED` 即使可被构造，也不能成为 G09D authoritative funding entry；`LinearFundingJournalProjector` 必须在调用 Generic Ledger前按 `type(entry) is LinearFundingJournalEntry` fail closed。Generic Ledger继续只读取 inherited `balance_changes/financing`，zero Entry只推进 Journal/Ledger cursor，不改变 balance或attribution；
12. Specialized Entry嵌入 component、完整 Request/request hash、Application Key、Settlement ID、Eligibility、publication、historical State、Applied Rate、Funding Mark/Policy、Settlement source、Quantization、Exact Cash Flow与Money。Canonical `source_ids` exact 为 `tuple(sorted(set((application_key.value, settlement_id.value, slot_id.value, eligibility.eligibility_hash, eligibility.publication_hash, eligibility.event_id, eligibility.event_hash, eligibility.publication_revision_id, eligibility.snapshot_hash, eligibility.state_hash, resolved_mark.mark_id, stale_policy.policy_hash, settlement.event_id, settlement.event_hash, settlement.revision_id, settlement.source_key, settlement.source_hash, request_hash))))`；不得增加 Journal ID、Entry hash、application-body hash或Ledger hash。Constructor重算该 exact tuple及全部 inherited/specialized fields；
13. 同一 Namespace/Run/account/Slot的 retry产生同 SETTLEMENT/JOURNAL IDs与同 Entry；既有 `AccountingJournal.append()` 对 same-ID identical Entry是 no-op，对 same-ID changed Rate/Mark/evidence/amount是 native `JournalEntryConflictError`。Translator不接收 prior Journal、不自行查询“是否已结算”并不吞掉 native conflict；different accounts可独立结算同一 Slot；
14. `LinearFundingJournalProjector.project(LinearFundingJournalReplayRequest)` 对完整 immutable Journal做两阶段审计：先按 published order拒绝所有 ordinary或non-exact specialized `FUNDING_APPLIED`；再按 Application Key检查 exact specialized Entries。不同 IDs但 normalized application-body hash相同返回 `DUPLICATE_FUNDING_APPLICATION`，body不同返回 `CONFLICTING_FUNDING_APPLICATION`。Normalized body preimage exact 为 `{type="linear_funding_application_body",schema_version=1,application_key,eligibility,settlement_evidence,funding_mark_evidence,position_key,contract,settlement_cash_registration,payment_quantization,exact_cash_flow,payment}`：它排除整个 nested `application_identity`（Namespace、Semantic Run、SETTLEMENT/JOURNAL IDs）、Request/request hash、base Journal ID/source IDs及所有由这些G09D identity字段派生的hash，但保留G09C Eligibility、publication、historical State、Mark/Policy和Settlement source authority。只有唯一性通过后才调用 branchless `GenericLedger.project()`；Projection保存 Journal cursor、Application Keys、Journal IDs与完整 Ledger State，不把 mixed Journal的generic financing aggregate误称为 funding-only aggregate；
15. Settlement business failure enum与 first-failure precedence exact 为：`MISSING_ELIGIBILITY` → `MISSING_SETTLEMENT_EVIDENCE` → `MISSING_FUNDING_MARK` → `SLOT_CONTEXT_MISMATCH` → `POSITION_CONTEXT_MISMATCH` → `UNSUPPORTED_RATE_BASIS` → `APPLIED_RATE_MISMATCH` → `INVALID_SETTLEMENT_EFFECTIVE_TIME` → `SETTLEMENT_EVIDENCE_NOT_AVAILABLE` → `FUNDING_MARK_PURPOSE_MISMATCH` → `FUNDING_MARK_CONTEXT_MISMATCH` → `FUNDING_MARK_INSTANT_MISMATCH` → `FUNDING_MARK_SCALE_MISMATCH` → `NON_POSITIVE_FUNDING_MARK` → `FUNDING_MARK_POLICY_MISMATCH` → `FUNDING_MARK_NOT_AVAILABLE` → `SETTLEMENT_CASH_CONTEXT_MISMATCH` → `QUANTIZATION_SCALE_MISMATCH`。Enum wire values exact 分别为 `missing_eligibility`、`missing_settlement_evidence`、`missing_funding_mark`、`slot_context_mismatch`、`position_context_mismatch`、`unsupported_rate_basis`、`applied_rate_mismatch`、`invalid_settlement_effective_time`、`settlement_evidence_not_available`、`funding_mark_purpose_mismatch`、`funding_mark_context_mismatch`、`funding_mark_instant_mismatch`、`funding_mark_scale_mismatch`、`non_positive_funding_mark`、`funding_mark_policy_mismatch`、`funding_mark_not_available`、`settlement_cash_context_mismatch`、`quantization_scale_mismatch`。多缺陷只返回第一项；
16. Exact failure predicates分别覆盖：(1–3) optional evidence缺失；(4) Request/Application/Eligibility/Settlement各自Slot、Slot Instrument或Contract Instrument任一不一致；(5) account/Venue/Instrument Position authority不一致，或 `request.contract != eligibility.request.contract`，或 `request.contract != eligibility.position_state.contract` 的任一完整Contract/InstrumentDefinition/multiplier/Scale lineage差异；(6) Eligibility published Rate basis或Settlement applied Rate basis任一非 frozen basis；(7) Applied Rate不等于Eligibility published Rate；(8) Settlement effective UTC不等于Slot target；(9) `applied_at < eligibility.captured_at`；(10) Mark或Policy purpose非FUNDING；(11) Mark Instrument/quote Currency不等于Contract；(12) Mark `resolved_at`非target；(13) Price Scale不等于Contract price Scale；(14) Price units非正；(15) Policy key/version/hash、ResolvedMark `age_nanoseconds` equality、age/max-age或forward-fill不匹配；(16) `ResolvedMark.available_at > applied_at.instant`；(17) Cash key非exact account/Venue/settlement Currency或不是Cash key；(18) Quantization target Scale不等于Registration Scale。Candidate value自身的exact type、canonical text/hash、positive denominator、Domain ID derivation和source shape错误是constructor `TypeError`/`ValueError`，不是business failure；
17. Settlement Failure嵌入 component、完整 Request/request hash、code与 ordered `subject_ids=(code.value, application_key.value, settlement_id.value, journal_entry_id.value, eligibility_hash or "missing-funding-eligibility", mark_id or "missing-funding-mark", settlement_event_id or "missing-funding-settlement")` 并重算first failure。`ProfilePortOutcome` component/input hash必须与Request及exactly-one Result/Failure匹配。Journal replay Failure独立使用 `UNAUTHORIZED_FUNDING_ENTRY` → `DUPLICATE_FUNDING_APPLICATION`/`CONFLICTING_FUNDING_APPLICATION` precedence，wire values exact 为 `unauthorized_funding_entry`、`duplicate_funding_application`、`conflicting_funding_application`；unauthorized exact subject IDs为 `(code.value, str(published_index), journal_entry_id.value, entry_type.value)`，duplicate/conflict exact subject IDs为 `(code.value, application_key.value, first_journal_entry_id.value, second_journal_entry_id.value)`，总是选择published order首个offending Entry/第二次Application occurrence；
18. Component ref exact 使用 `ProfilePortType.FINANCING_MODEL`、key `instrument.linear-perpetual.funding-accounting.v1`、version 1。Digest preimage exact 为 `{type="linear_funding_accounting_component",schema_version=1,component_key,component_version=1,algorithm_key="linear-funding-settlement-accounting-v1",application_key="account_id+funding_slot_id",settlement_id_kind="settlement",journal_id_kind="journal",identity_ordinal=0,rate_basis="funding_fraction_of_notional",mark_purpose="funding",formula="-(signed_quantity*multiplier*mark*rate)",quantization="one_round_ratio_per_application",effective_time="slot.target_funding_time",recorded_at="settlement.applied_at",allowed_grade="development"}`；
19. 所有新增 public values使用 `schema_version=1`、exact types、canonical tuple order与 `canonical_sha256`。Canonical preimages exact 为：Application Key `{type="linear_funding_application_key",schema_version,account_id,slot_id,value}`；Identity `{type="linear_funding_application_identity",schema_version,application_key,identity_namespace={value,version,algorithm},semantic_run_id,settlement_id,journal_entry_id}`；Mark Evidence `{type="linear_funding_mark_evidence",schema_version,resolved_mark,stale_policy}`；Settlement Evidence `{type="linear_funding_settlement_evidence",schema_version,application_key,effective_time,applied_at,applied_rate,event_id,event_hash,revision_id,supersedes_revision_id,source_key,source_hash}`；Exact Cash `{type="exact_linear_funding_cash_flow",schema_version,currency_id,numerator,denominator}`；Request `{type="linear_funding_settlement_request",schema_version,eligibility,settlement_evidence,funding_mark_evidence,application_identity,position_key,contract,settlement_cash_registration,payment_quantization}`；Result `{type="linear_funding_settlement_result",schema_version,component_ref,request,request_hash,application_key,exact_cash_flow,payment,journal_entry}`；Failure `{type="linear_funding_settlement_failure",schema_version,component_ref,request,request_hash,code,subject_ids}`；Entry `{type="linear_funding_journal_entry",schema_version,component_ref,request,request_hash,application_key,settlement_id,exact_cash_flow,payment,application_body_hash,journal_entry}`，其中`journal_entry`是base `AccountingJournalEntry.to_canonical_dict()`；Replay Request `{type="linear_funding_journal_replay_request",schema_version,journal,ledger_schema}`；Projection `{type="linear_funding_journal_projection",schema_version,component_ref,request,request_hash,journal_cursor,application_keys,journal_entry_ids,ledger_state}`，Application/Journal tuple均按published order；Replay Failure `{type="linear_funding_journal_replay_failure",schema_version,component_ref,request,request_hash,code,subject_ids}`；Replay Outcome `{type="linear_funding_journal_replay_outcome",schema_version,component_ref,request_hash,projection,failure}`且exactly one Projection/Failure；所有constructor重算对应body/hash、first failure与embedded authority；
20. Static golden沿用 G09A–G09C synthetic Contract，至少冻结：Long/Short/Flat × positive/negative/zero Rate；multiplier `0.125`、Funding Mark `100.00 USDT`、Quantity Scale 3、settlement Scale 2，Rate `±0.0008` 对一张 Long exact 产生 `∓0.01 USDT`；`±0.005/±0.015/±0.025` 的 HALF_EVEN/HALF_UP tie controls；adversarial no-pre-quantization；later close/flip/current State non-substitution；每个18-code failure至少一个case，并为独立predicate分别增加Request/Application/Eligibility/Settlement每个Slot authority、完整Contract InstrumentDefinition/multiplier/quantity-price Scale lineage、Position account/Venue/Instrument、Eligibility published Rate basis与Settlement applied Rate basis、Settlement effective/applied-at exact/full boundary、Mark purpose/Instrument/Currency/resolved-at/available-at UTC/Price Scale/positivity/`age_nanoseconds`、Policy key/version/hash/max-age/forward-fill、Cash key type/account/Venue/Currency和Quantization Scale controls；multi-defect precedence；same-ID no-op/conflict、只改变G09D Namespace/Run的normalized alternate-ID duplicate、改变Rate/Mark/Policy/source/registration/quantization任一body字段的conflict、different-account independence；flat/zero-rate/rounded-zero specialized Entry；Generic Ledger cash/financing parity与Position unchanged；constructor/hash/ID forgery、ordinary/subclass funding Entry rejection、canonical golden stability和input/module authority不变；
21. Purity沿用并扩展 derivative scanner：`tests/architecture/test_derivative_boundary.py` 必须显式扫描新 `funding_accounting.py`，允许它导入 frozen `funding`、`marks`、G09A/G09B与generic Journal/Ledger/Ports seams，同时拒绝 filesystem、network/provider/process/database/cloud、dynamic import、MarketBundle/Runtime import、mutable module/class/decorator state与wall clock；该 scanner继续拒绝 Generic Ledger、SnapshotProjector、Engine、Runner、Timeline 的 funding/linear derivative branch或reference。`tests/domain/accounting/test_accounting_contracts.py` 必须增加 focused assertion：generic zero-effect allowlist相对既有合同只增加 `FUNDING_APPLIED`，其他 Entry type仍拒绝empty effect；G09D replay tests再证明ordinary/subclass funding Entry不可成为authoritative specialized replay；
22. G09D 不拥有 publication selection/finality、provider Rate transformation/schedule/correction/source mapping、Mark stream resolution/query/fallback、Journal append/mutation、Runtime dispatch、cross-Query history completeness、SettlementBook obligation、Fee、average-entry basis、Unrealized PnL、Margin、Liquidation、Binance semantics、真实交易、result grade或deployment authorization。G09H拥有composition completeness与Runtime injection；G10E拥有provider publication/finality/source mapping。

G09D 的 applied Rate、Funding Mark、exact cash、settlement Currency/Scale、Application/Journal identity与full-Journal duplicate/conflict语义已冻结，无需选择外部 provider。若 provider实际需要不同 Rate transformation、Funding Mark stream或settlement availability mapping，必须由 G10E caller Adapter明确转换，或先将 G09D退回 DRAFT；不得在 FinancingModel 内新增 provider分支。

### G09D Implementation Acceptance

1. Pure `funding_accounting` deep module、root exports和generic zero-effect allowlist最小扩展已实现；未新增Port、Profile、Adapter、Package、依赖或Generic Ledger/Snapshot/Engine/Runner/Timeline funding branch；
2. Account/Slot Application Key、Namespace/Semantic Run SETTLEMENT/JOURNAL身份、完整Eligibility/Settlement/Mark/Policy lineage和canonical hashes均由constructor重新派生并fail closed；
3. Signed historical eligibility Quantity、multiplier、Funding Mark与Applied Rate形成GCD-reduced exact cash，且每个Application仅在Money boundary调用一次`round_ratio`；Long/Short/Flat、正负零Rate、tie和rounded-zero均由static golden冻结；
4. Settlement translator按frozen 18-code precedence返回`ProfilePortOutcome`，成功时只生成specialized `FUNDING_APPLIED` Entry；same-ID retry/conflict继续由immutable Journal原生处理；
5. Full-Journal projector先拒绝ordinary/subclass funding Entry，再按normalized Application body审计alternate-ID duplicate/conflict，最后调用branchless Generic Ledger并保存完整Ledger State；
6. Static golden、constructor/identity forgery、source IDs、economic authority conflict controls、zero Entry、cash/financing parity、boundary purity、public exports和input authority不变性均通过；
7. 68-file Import Boundary、68-source mypy、LSP/scoped pi-lens、full regression与`uv lock --check`全部通过。

G09D implementation 已冻结在 immutable commit `913e3ac81cc68a454f32a3f48b6444ac4604bb0e`，状态为 `PASSED`。

验证记录：

```text
G09D contract                                                      24 passed
G09D static golden                                                  1 passed
Frozen public/boundary regression command                         89 passed
Combined G09D acceptance report                                  114 passed
Full test suite                                                   924 passed
Trading-kernel import boundary                                     PASS (68 files)
mypy                                                                 no issues (68 source files)
Primary LSP + scoped pi-lens                                        clean
uv lock --check                                                     PASS
Python                                                               3.13.5
```

## 73. G09E Instrument Margin Requirement Acceptance Card

```yaml
id: G09E
status: PASSED
depends_on:
  - G09A
owner_package: trading-kernel margin requirement
public_interface:
  - crypto_quant_trading.LinearMarginLeverageEvidence
  - crypto_quant_trading.LinearMarginTier
  - crypto_quant_trading.LinearMarginRuleInterval
  - crypto_quant_trading.LinearMarginRuleBook
  - crypto_quant_trading.LinearMarginMarkEvidence
  - crypto_quant_trading.ExactLinearMarginAmount
  - crypto_quant_trading.LinearInstrumentMarginRequest
  - crypto_quant_trading.LinearInstrumentMarginResult
  - crypto_quant_trading.LinearInstrumentMarginFailureCode
  - crypto_quant_trading.LinearInstrumentMarginFailure
  - crypto_quant_trading.LinearInstrumentMarginModel
  - static synthetic linear-margin-requirement golden fixture v1
test_commands:
  contract: uv run pytest -q tests/kernel/derivatives/test_linear_margin_requirement.py
  fixture: uv run pytest -q tests/kernel/derivatives/test_linear_margin_requirement_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py tests/architecture/test_derivative_boundary.py tests/kernel/derivatives/test_linear_positions.py tests/kernel/derivatives/test_linear_derivative_accounting.py tests/kernel/derivatives/test_linear_funding_eligibility.py tests/kernel/derivatives/test_linear_funding_accounting.py tests/kernel/marks/test_mark_resolver.py tests/kernel/reservations/test_resource_reservation_book.py tests/kernel/pretrade_risk/test_pretrade_risk.py tests/kernel/ledger/test_generic_ledger.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g09e-import-boundary-report.json
fixture_ids:
  - synthetic-linear-margin-requirement-v1
expected_artifacts:
  - tests/fixtures/kernel/derivatives/linear-margin-requirement-v1.json
  - build/acceptance/g09e-pytest.xml
  - build/acceptance/g09e-import-boundary-report.json
failure_contracts:
  - current-position-order-working-order-or-target-is-used-as-implicit-margin-exposure
  - current-account-leverage-or-current-exchange-tier-backfills-a-historical-gap
  - historical-leverage-or-rule-evidence-is-used-before-full-availability
  - rule-interval-or-notional-tier-gap-overlap-or-order-is-guessed
  - contract-multiplier-is-omitted-from-margin-notional
  - signed-short-quantity-produces-negative-notional
  - margin-mark-uses-non-margin-purpose-wrong-context-or-post-evaluation-observation
  - notional-is-quantized-before-tier-selection
  - selected-leverage-exceeds-the-resolved-tier-maximum
  - maintenance-rate-or-deduction-produces-a-negative-requirement
  - initial-or-maintenance-margin-is-rounded-down-or-rounded-more-than-once
  - settlement-cash-account-venue-currency-or-scale-is-inferred-or-rescaled
  - result-aggregates-equity-unrealized-pnl-fee-funding-or-working-order-reservation
  - result-mutates-journal-ledger-portfolio-rulebook-mark-or-leverage-authority
  - provider-symbol-tier-api-current-config-or-liquidation-semantics-leak-into-g09e
allowed_grade: development
evidence:
  - pytest-report
  - static-linear-margin-requirement-golden-hash
  - historical-leverage-and-rule-interval-identity-evidence
  - exact-multiplier-aware-notional-evidence
  - lower-inclusive-upper-exclusive-tier-boundary-evidence
  - tier-order-gap-overlap-and-current-fallback-rejection
  - exact-initial-and-maintenance-requirement-evidence
  - maintenance-rate-and-deduction-evidence
  - margin-purpose-mark-and-stale-policy-evidence
  - conservative-ceiling-quantization-evidence
  - long-short-flat-and-scale-adversarial-controls
  - no-account-aggregation-reservation-liquidation-or-runtime-mutation
  - import-boundary-report
  - static-type-report
passed_commit: e1e4c810b67f8f911b33ef8d7302f33933fc1e32
artifact_hashes:
  tests/fixtures/kernel/derivatives/linear-margin-requirement-v1.json: sha256:4065e57d1eea682e75da5d5ea00ca8e694b1cd0294020a28c31e2738e0f80718
  build/acceptance/g09e-pytest.xml: sha256:c8a0b2ce2376abd72213223ad994d035f3e0493547d7306bbd1ab232ccfd8527
  build/acceptance/g09e-import-boundary-report.json: sha256:c030a815511d9e501c7c4c467bbe828c48bb71ff1e497c7cfe9ec8b994e414e2
```

### G09E Acceptance

1. G09E只新增pure `crypto_quant_trading.margin` deep module与必要root exports；不得新增Port、Profile、Adapter、Package、依赖，或修改Generic Ledger、SnapshotProjector、ReservationBook、PreTradeRiskEvaluator、Engine、Runner、Timeline。`LinearInstrumentMarginModel.evaluate_margin(request)`结构化实现既有`MarginModel`，exact消费`LinearInstrumentMarginRequest`并返回`ProfilePortOutcome[LinearInstrumentMarginResult, LinearInstrumentMarginFailure]`；它不读取或mutate Journal/Ledger/Portfolio/Reservation authority；
2. `LinearInstrumentMarginRequest` exact保存Position key、完整G09A Contract、caller-supplied signed `exposure_quantity: Quantity`、`evaluated_at: SimulationInstant`、optional `LinearMarginLeverageEvidence`、optional `LinearMarginRuleBook`、optional `LinearMarginMarkEvidence`、settlement Cash `LedgerBalanceRegistration`与`requirement_quantization: QuantizationPolicy`。Exposure Quantity只声明本次单Instrument requirement评估对象；G09E不从current Position、Order、Working Order、Target、Fill或average-entry basis推导它；
3. `LinearMarginLeverageEvidence` exact保存account ID、Instrument ID、selected leverage、半开`effective_from/effective_to_exclusive`、完整`available_at: SimulationInstant`与source key/hash。Selected leverage basis frozen为`notional_per_initial_margin`。Evidence必须context匹配Request，在`evaluated_at.instant`有效且完整available-at不晚于evaluated-at；later/current account leverage不能回填历史；
4. `LinearMarginTier` exact保存stable `tier_id`、settlement-currency `notional_floor: Money`、optional `notional_cap: Money`、`maximum_leverage: Rate`、`maintenance_margin_rate: Rate`与nonnegative `maintenance_margin_deduction: Money`。Tier区间exact为lower-inclusive/upper-exclusive；maximum leverage basis为`notional_per_initial_margin`，maintenance basis为`maintenance_margin_fraction_of_notional`。Deduction是从`notional × maintenance rate`减去的固定累计额，不是Fee、Funding或Cash movement；
5. `LinearMarginRuleInterval` exact保存stable interval ID、半开effective UTC interval、完整`available_at: SimulationInstant`、caller-ordered Tier tuple与source key/hash。`LinearMarginRuleBook` exact保存rule-book key/version、Instrument、settlement Currency、authoritative tier Scale、按`(effective_from,effective_to_exclusive-or-unbounded,interval_id)`排序的historical Interval tuple与config hash。RuleBook constructor只验证exact types/canonical/hash shape、规范化Interval顺序并保留可结构化评估的gap/overlap/tier defects；Model在Request时间解析；
6. Historical Rule resolution exact使用`evaluated_at.instant`查找effective Interval：zero active返回`MISSING_HISTORICAL_RULE`，multiple active返回`OVERLAPPING_HISTORICAL_RULES`，unique Interval的full availability晚于evaluated-at返回`HISTORICAL_RULE_NOT_AVAILABLE`。禁止选择最近过去、最近未来、tuple最后一项、最高version或caller当前API Tier作为fallback；
7. Resolved Interval的Tier tuple必须按notional floor严格递增，第一项floor exact为zero，相邻`previous.cap == next.floor`，最后一项cap为None。Tuple order错误、首尾/相邻缺口和相邻重叠分别返回`TIER_ORDER_MISMATCH`、`TIER_GAP`、`TIER_OVERLAP`；所有floor/cap/deduction Currency与Scale必须匹配RuleBook，Rate basis必须匹配frozen basis。只有完整Tier集合通过后才按未量化exact notional选择唯一Tier；
8. `LinearMarginMarkEvidence` exact只保存完整`ResolvedMark`与完整`StaleMarkPolicy`。Mark与Policy purpose必须为`PricePurpose.MARGIN`；Instrument、quote/settlement Currency、Price Scale匹配Contract；Price strictly positive；`resolved_at == evaluated_at.instant`；authoritative`ResolvedMark.available_at <= evaluated_at.instant`。Policy key/version/hash、age equality、max-age与forward-fill allowance全部重新验证；Valuation、Funding、Settlement、Liquidation、execution/trade/bar price不得替代；
9. 若signed exposure Quantity为`q/Q`、positive contract multiplier为`m/M`、positive Margin Mark为`p/P`，exact settlement-currency notional为`N=abs(q)*m*p/(Q*M*P)`。`ExactLinearMarginAmount`保存Currency、GCD-reduced signed numerator与positive denominator；notional与成功requirements均nonnegative，zero canonical为`0/1`；禁止float、Decimal、Money pre-quantization或从average-entry basis推导notional；
10. Selected leverage为`l/L`时Initial Margin exact为`I=N*L/l`。Resolved Tier maximum leverage为`u/U`，必须以cross-multiplication验证`l/L <= u/U`；超过返回`LEVERAGE_EXCEEDS_TIER_MAXIMUM`，不得clamp到maximum或选择其他Tier；
11. Resolved Tier maintenance rate为`r/R`、deduction Money为`c/C`时Maintenance Margin exact为`M=N*r/R-c/C`，以共同denominator GCD约分。若exact结果为负返回`NEGATIVE_MAINTENANCE_REQUIREMENT`；不得隐式clamp为zero。Provider `cum`或等价字段只能由后续Adapter显式映射为maintenance deduction；
12. Tier选择前不得quantize notional。Initial和Maintenance各自在自己的Money boundary恰好调用一次public `round_ratio(exact.numerator * target_scale.factor, exact.denominator, RoundingPolicy.CEILING)`；`requirement_quantization.rounding`非CEILING返回`UNSAFE_MARGIN_ROUNDING`。Quantity、multiplier、Mark、leverage、rate、deduction与中间值不得提前round、aggregate或隐式rescale；
13. Settlement Cash registration必须是exact account/Venue/Contract settlement Currency的`CashBalanceKey`，Registration Scale等于Quantization target Scale。Initial/Maintenance Money Currency与Scale仅由该authority决定；不执行FX、stablecoin peg、cross-collateral haircut或从Mark/Rule阈值自行选择Scale；
14. Result exact保存component ref、完整Request/request hash、resolved historical Interval/Tier、exact Notional、exact Initial/Maintenance与quantized Initial/Maintenance Money。Result不返回Equity、Available Margin、Margin Ratio、Unrealized PnL、Fee、Funding、Reservation、Liquidation status或Journal/Ledger effect；G09F才聚合单Execution Account，G09G才评估Liquidation；
15. Business failure enum与first-failure precedence exact为：`MISSING_LEVERAGE_EVIDENCE` → `MISSING_MARGIN_RULE_BOOK` → `MISSING_MARGIN_MARK` → `POSITION_CONTEXT_MISMATCH` → `LEVERAGE_CONTEXT_MISMATCH` → `UNSUPPORTED_LEVERAGE_BASIS` → `NON_POSITIVE_LEVERAGE` → `LEVERAGE_NOT_EFFECTIVE` → `LEVERAGE_NOT_AVAILABLE` → `RULE_BOOK_CONTEXT_MISMATCH` → `MISSING_HISTORICAL_RULE` → `OVERLAPPING_HISTORICAL_RULES` → `HISTORICAL_RULE_NOT_AVAILABLE` → `TIER_ORDER_MISMATCH` → `TIER_CONTEXT_MISMATCH` → `TIER_GAP` → `TIER_OVERLAP` → `UNSUPPORTED_TIER_BASIS` → `MARGIN_MARK_PURPOSE_MISMATCH` → `MARGIN_MARK_CONTEXT_MISMATCH` → `MARGIN_MARK_INSTANT_MISMATCH` → `MARGIN_MARK_SCALE_MISMATCH` → `NON_POSITIVE_MARGIN_MARK` → `MARGIN_MARK_POLICY_MISMATCH` → `MARGIN_MARK_NOT_AVAILABLE` → `LEVERAGE_EXCEEDS_TIER_MAXIMUM` → `NEGATIVE_MAINTENANCE_REQUIREMENT` → `SETTLEMENT_CASH_CONTEXT_MISMATCH` → `QUANTIZATION_SCALE_MISMATCH` → `UNSAFE_MARGIN_ROUNDING`；wire values为对应lower-snake-case；多缺陷只返回第一项；
16. Exact failure predicates分别为：(1–3) optional evidence缺失；(4) Position key/Quantity/Contract的account、Venue、Instrument或Quantity Scale不一致；(5) leverage account/Instrument context不一致；(6–7) selected leverage basis错误或units非正；(8) evaluated UTC不在leverage半开effective interval；(9) leverage full available-at晚于evaluated-at；(10) RuleBook Instrument/settlement Currency/tier Scale不匹配Contract；(11–13) historical active Interval zero/multiple/未available；(14) Tier floor tuple非严格递增；(15) Tier floor/cap/deduction Currency或Scale不匹配RuleBook；(16) first floor非zero、final cap非None或相邻cap小于next floor；(17) 相邻cap大于next floor；(18) maximum leverage或maintenance Rate basis错误；(19–25) Margin Mark purpose/context/instant/Scale/positivity/Policy/availability错误；(26) selected leverage大于resolved maximum；(27) maintenance exact为负；(28) Cash key非exact account/Venue/settlement Currency或不是Cash key；(29) Quantization target Scale不等于Registration Scale；(30) rounding非CEILING。Candidate exact type、canonical text/hash、interval nonempty、nonnegative Tier thresholds/rates/deduction、positive denominator等shape错误是constructor`TypeError`/`ValueError`，不是business failure；
17. Failure exact保存component、完整Request/request hash、code与ordered `subject_ids=(code.value, position_key.account_id, str(contract.instrument.instrument_id), leverage.source_key or "missing-margin-leverage", rule_book.rule_book_key or "missing-margin-rule-book", interval.interval_id or "missing-margin-rule-interval", tier.tier_id or "missing-margin-tier", mark.mark_id or "missing-margin-mark")`并从Request重算first failure与resolved subjects；`ProfilePortOutcome` component/input hash与exactly-one Result/Failure必须匹配；
18. Component ref exact使用`ProfilePortType.MARGIN_MODEL`、key `instrument.linear-perpetual.margin-requirement.v1`、version 1。Digest preimage exact为`{type="linear_margin_requirement_component",schema_version=1,component_key,component_version=1,algorithm_key="linear-instrument-margin-requirement-v1",exposure="caller-supplied-signed-quantity",notional="abs(quantity)*multiplier*margin_mark",tier_interval="lower-inclusive-upper-exclusive",rule_resolution="exact-one-historical-interval",initial_margin="notional/selected_leverage",maintenance_margin="notional*maintenance_rate-maintenance_deduction",quantization="independent-ceiling-boundaries",allowed_grade="development"}`；
19. Canonical preimages exact为：Leverage Evidence `{type="linear_margin_leverage_evidence",schema_version,account_id,instrument_id,selected_leverage,effective_from,effective_to_exclusive,available_at,source_key,source_hash}`；Tier `{type="linear_margin_tier",schema_version,tier_id,notional_floor,notional_cap,maximum_leverage,maintenance_margin_rate,maintenance_margin_deduction}`；Interval `{type="linear_margin_rule_interval",schema_version,interval_id,effective_from,effective_to_exclusive,available_at,tiers,source_key,source_hash}`；RuleBook config `{type="linear_margin_rule_book_config",schema_version,rule_book_key,rule_book_version,instrument_id,settlement_currency_id,tier_scale,intervals}`，`config_hash=canonical_sha256(config)`；RuleBook `{type="linear_margin_rule_book",schema_version,rule_book_key,rule_book_version,instrument_id,settlement_currency_id,tier_scale,intervals,config_hash}`；Mark Evidence `{type="linear_margin_mark_evidence",schema_version,resolved_mark,stale_policy}`；Exact Amount `{type="exact_linear_margin_amount",schema_version,currency_id,numerator,denominator}`；Request `{type="linear_instrument_margin_request",schema_version,position_key,contract,exposure_quantity,evaluated_at,leverage_evidence,rule_book,margin_mark_evidence,settlement_cash_registration,requirement_quantization}`；Result `{type="linear_instrument_margin_result",schema_version,component_ref,request,request_hash,resolved_interval,resolved_tier,exact_notional,exact_initial_margin,exact_maintenance_margin,initial_margin,maintenance_margin}`；Failure `{type="linear_instrument_margin_failure",schema_version,component_ref,request,request_hash,code,subject_ids}`；其余hash exact为`canonical_sha256(value)`；
20. Static golden沿用G09A synthetic Contract：multiplier `0.125`、Quantity Scale 3、Margin Mark `100.00 USDT`、settlement Scale 2、selected leverage `10`。至少冻结Long/Short相同absolute notional、Flat zero、`1.000` contracts notional `12.5`、tier boundary `4.000` contracts exact notional `50`、below/at/above boundary、maximum leverage equality/exceed、maintenance rate/deduction连续控制、CEILING sub-cent、large integer/no-pre-quantization、historical interval boundary/full availability、past gap with later/current interval rejection、interval overlap、tier order/gap/overlap、全部30 failures与multi-defect precedence、constructor/hash/config forgery、same Request idempotency、input/module authority不变；
21. Purity扩展derivative scanner显式扫描`margin.py`，只允许stdlib、`crypto_quant_domain`、frozen G09A derivatives、marks、generic Ledger registration与Ports imports；拒绝filesystem、network/provider/process/database/cloud、dynamic import、MarketBundle/Runtime/Profile import、mutable module/class/decorator state与wall clock。Generic Ledger、SnapshotProjector、ReservationBook、PreTradeRiskEvaluator、Engine、Runner、Timeline不得出现`LinearMargin`/`LinearInstrumentMargin`/`ExactLinearMargin` branch或reference；既有generic `margin` Money字段不因此被禁止；
22. G09E不拥有account Equity、Available Margin、Margin Ratio、Derivative Unrealized PnL、Fee/Funding aggregate、Working Order Reservation、cross-Instrument/cross-Venue/cross-account collateral、isolated/cross mode、Liquidation、bankruptcy、provider tier query/current config、Runtime dispatch、真实交易、result grade或deployment authorization。G09F拥有单Execution Account aggregate，G09G拥有conservative Liquidation audit；G10C/G10F拥有provider tier/leverage source mapping。若provider需要不同notional basis、maintenance formula或availability语义，必须由Adapter明确映射或先把G09E退回DRAFT，不能在Model加入provider分支。

G09E的single-Instrument exposure、historical leverage/rule resolution、multiplier-aware exact notional、tier boundary、Initial/Maintenance公式、maintenance deduction与CEILING Money boundary已冻结。无需选择具体provider即可实现synthetic development-grade seam；G10C/G10F只能映射source facts，不能改写这些generic economics。

### G09E Implementation Acceptance

1. Pure `margin` deep module与root exports已实现；未新增Port、Profile、Adapter、Package、依赖，也未修改Generic Ledger、SnapshotProjector、ReservationBook、PreTradeRiskEvaluator或Runtime；
2. Caller-supplied signed exposure、historical leverage evidence、historical RuleBook Interval/Tier与MARGIN Mark/Policy均以exact immutable authority消费；past gap不使用later/current rule fallback；
3. Multiplier-aware absolute exact notional、lower-inclusive/upper-exclusive Tier选择、selected/maximum leverage cross-multiplication、Initial与Maintenance deduction公式均使用GCD-reduced rational arithmetic；
4. Initial与Maintenance各自只在Money boundary使用CEILING quantization；Long/Short、Flat、below/at/above Tier boundary与sub-cent controls由static golden冻结；
5. Frozen 30-code first-failure precedence、ordered subjects、RuleBook config identity、Result/Failure/Exact constructor forgery rejection与current fallback rejection全部通过；
6. Derivative boundary scanner显式覆盖`margin.py`并继续拒绝Generic Ledger、SnapshotProjector、Engine、Runner、Timeline derivative-margin branch；
7. 69-file Import Boundary、69-source mypy、Primary LSP、scoped pi-lens blocking diagnostics、full regression与`uv lock --check`全部通过。

G09E implementation 已冻结在 immutable commit `e1e4c810b67f8f911b33ef8d7302f33933fc1e32`，状态为 `PASSED`。

验证记录：

```text
G09E contract                                                      12 passed
G09E static golden                                                  1 passed
Frozen public/boundary regression command                         117 passed
Combined G09E acceptance report                                  130 passed
Full test suite                                                   937 passed
Trading-kernel import boundary                                     PASS (69 files)
mypy                                                                 no issues (69 source files)
Primary LSP + scoped pi-lens                                        no blocking issues
uv lock --check                                                     PASS
Python                                                               3.13.5
```

## 74. G09F Single Execution Account Margin Projection Acceptance Card

```yaml
id: G09F
status: PASSED
depends_on:
  - G09B
  - G09E
  - WP-05B
owner_package: trading-kernel account margin projection
public_interface:
  - crypto_quant_trading.LinearMarginLedgerEvidence
  - crypto_quant_trading.LinearMarginReservationEvidence
  - crypto_quant_trading.LinearPositionValuationEvidence
  - crypto_quant_trading.ExactLinearUnrealizedPnl
  - crypto_quant_trading.LinearPositionUnrealizedPnl
  - crypto_quant_trading.LinearAccountMarginProjectionRequest
  - crypto_quant_trading.LinearAccountMarginProjection
  - crypto_quant_trading.LinearAccountMarginProjectionFailureCode
  - crypto_quant_trading.LinearAccountMarginProjectionFailure
  - crypto_quant_trading.LinearAccountMarginProjectionOutcome
  - crypto_quant_trading.LinearAccountMarginProjector
  - static synthetic linear-account-margin-projection golden fixture v1
test_commands:
  contract: uv run pytest -q tests/kernel/derivatives/test_linear_account_margin_projection.py
  fixture: uv run pytest -q tests/kernel/derivatives/test_linear_account_margin_projection_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py tests/architecture/test_derivative_boundary.py tests/kernel/derivatives/test_linear_derivative_accounting.py tests/kernel/derivatives/test_linear_funding_accounting.py tests/kernel/derivatives/test_linear_margin_requirement.py tests/kernel/reservations/test_resource_reservation_book.py tests/kernel/ledger/test_generic_ledger.py tests/kernel/snapshots/test_portfolio_snapshot_projector.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g09f-import-boundary-report.json
fixture_ids:
  - synthetic-linear-account-margin-projection-v1
expected_artifacts:
  - tests/fixtures/kernel/derivatives/linear-account-margin-projection-v1.json
  - build/acceptance/g09f-pytest.xml
  - build/acceptance/g09f-import-boundary-report.json
failure_contracts:
  - ledger-or-reservation-current-state-is-read-implicitly
  - ledger-or-reservation-evidence-is-used-before-full-availability
  - multiple-accounts-venues-or-settlement-currencies-are-netted
  - derivative-unrealized-pnl-omits-contract-multiplier-or-signed-direction
  - generic-portfolio-snapshot-spot-market-value-substitutes-derivative-pnl
  - realized-pnl-fee-or-funding-is-double-counted-on-top-of-wallet-cash
  - non-valuation-mark-or-post-evaluation-observation-is-used
  - position-margin-or-valuation-coverage-gap-duplicate-or-extra-is-guessed
  - g09e-exposure-does-not-equal-authoritative-position
  - initial-maintenance-or-unrealized-values-are-rescaled-or-rounded-twice
  - working-order-margin-uses-non-margin-reservation-dimensions
  - working-order-margin-reservation-reduces-equity
  - negative-equity-or-available-margin-is-clamped-or-treated-as-projection-failure
  - margin-or-unrealized-pnl-is-written-into-generic-ledger-or-portfolio-snapshot
  - provider-wallet-cross-margin-liquidation-or-runtime-semantics-leak-into-g09f
allowed_grade: development
evidence:
  - pytest-report
  - static-linear-account-margin-projection-golden-hash
  - ledger-wallet-and-attribution-authority-evidence
  - exact-multiplier-aware-unrealized-pnl-evidence
  - position-margin-valuation-exact-coverage-evidence
  - single-account-venue-currency-context-evidence
  - wallet-plus-unrealized-equity-evidence
  - initial-maintenance-and-working-order-margin-aggregation-evidence
  - available-margin-and-negative-state-evidence
  - no-attribution-double-counting-evidence
  - immutable-ledger-reservation-and-input-authority-evidence
  - import-boundary-report
  - static-type-report
passed_commit: 107b41aafee00195ec0ae0031800a1409e016264
artifact_hashes:
  tests/fixtures/kernel/derivatives/linear-account-margin-projection-v1.json: sha256:3a18e0feb8ba49efdf7629b117d87a2266d1e493e1c8bedf1866e6eca42753be
  build/acceptance/g09f-pytest.xml: sha256:915482e5567cd16a862a4a46c9ef4c8e6b198ad56368d0f1e47d89fab7242393
  build/acceptance/g09f-import-boundary-report.json: sha256:4fd8a69189fa8d7228becdd1318ea3c210589da2381199e673b302b45c432570
```

### G09F Acceptance

1. G09F只新增pure `crypto_quant_trading.account_margin` deep module与必要root exports；不得新增Port、Profile、Adapter、Package、依赖，或修改Generic Ledger、PortfolioSnapshotProjector、ReservationBook、PreTradeRiskEvaluator、Engine、Runner、Timeline。`LinearAccountMarginProjector.project(request)`只读取embedded immutable authority并返回`LinearAccountMarginProjectionOutcome`；不查询或mutate Journal/Ledger/Reservation/Runtime；
2. v1 exact限定单Execution Account、单Venue、单settlement Currency/Scale。Request保存account ID、Venue ID、`evaluated_at: SimulationInstant`、optional Ledger Evidence、ordered Position Valuation Evidence tuple、ordered G09E Margin Result tuple、optional Reservation Evidence、settlement Cash `LedgerBalanceRegistration`和Unrealized PnL `QuantizationPolicy`。Optional只用于structured missing-evidence failures；跨Account、跨Venue、跨Currency collateral或FX不是v1 fallback；
3. `LinearMarginLedgerEvidence`保存完整`LedgerState`、`projected_through: SimulationInstant`、`available_at: SimulationInstant`与source key/hash。Projected-through必须exact等于Request evaluated-at，available-at不得晚于evaluated-at；Ledger Schema全部Registration必须属于同Account/Venue，Cash/Position registrations及balances不得被caller current state替代；
4. Settlement Cash registration必须是exact Request account/Venue/settlement Currency的`CashBalanceKey`，且exact存在于Ledger Schema。Derivative Wallet Balance exact取`ledger_state.cash_amount(key)`；Realized PnL、Fee、Funding audit exact分别取同key的`realized_pnl_amount`、`fee_amount`、`financing_amount`。这些attributions已通过Journal进入Wallet Cash，Equity公式不得再次相加；
5. `LinearMarginReservationEvidence`保存完整`ResourceReservationState`、projected-through/full available-at与source key/hash。State account必须匹配Request，projected-through exact等于evaluated-at，available-at不晚于evaluated-at；active Orders、cursors和totals继续由既有ReservationBook authority验证，G09F不重建working Orders；
6. Working Order Margin Reservation只聚合`reservation_state.totals.margin`。每项必须匹配settlement Currency与Cash registration Scale；`cash`、`fee_reserve`、`sellable_quantities`、`order_capacity_units`、`exposure_capacity`不得进入该aggregate。Reservation只减少Available Margin，不减少Wallet Balance或Equity；
7. `LinearPositionValuationEvidence` exact保存non-flat G09A `LinearPositionState`、完整`ResolvedMark`与完整`StaleMarkPolicy`。State account/Venue/Instrument/Contract必须匹配Request与Ledger Position balance；Ledger quantity必须exact等于State quantity。Flat State不得作为valuation evidence输入，也不得携带G09E Result；
8. VALUATION Mark与Policy purpose必须为`PricePurpose.VALUATION`；Instrument、quote/settlement Currency与Price Scale匹配Contract；Price strictly positive；`resolved_at == evaluated_at.instant`；`ResolvedMark.available_at <= evaluated_at.instant`。Policy key/version/hash、age equality、max-age与forward-fill全部重验；MARGIN、FUNDING、LIQUIDATION、SETTLEMENT或execution price不能替代；
9. 每个non-flat Position exact有且只有一个matching G09E Result和一个Valuation Evidence，不允许duplicate、missing或extra。Matching Result必须成功、Request Position key/Contract/evaluated-at与G09F相同，`exposure_quantity == position_state.quantity`，Initial/Maintenance Currency/Scale匹配settlement Cash authority；G09F不得重新选择leverage/Tier或重算G09E requirement；
10. 若signed Position为`q/Q`、positive multiplier为`m/M`、Valuation Mark为`p/P`、exact average entry为`a/A`，Unrealized PnL exact为`U=q*m*(p*A-a*P)/(Q*M*P*A)`。`ExactLinearUnrealizedPnl`保存settlement Currency、GCD-reduced signed numerator与positive denominator，zero canonical为`0/1`；Long price rise为正、Short price rise为负；禁止float、Decimal、generic spot Position market value或average-entry Money rounding；
11. 每个Instrument Unrealized PnL只调用一次`round_ratio(exact.numerator * target_scale.factor, exact.denominator, RoundingPolicy.HALF_EVEN)`映射到Money。Quantization target Scale必须等于settlement Cash registration Scale，rounding非HALF_EVEN返回`UNSAFE_UNREALIZED_PNL_ROUNDING`；不得先round Mark、entry、multiplier或aggregate后统一round；
12. Projection exact保存component、完整Request/hash、Wallet Balance、Realized PnL、Fees、Funding、ordered per-Position exact/quantized Unrealized PnL、total Unrealized、Equity、total Initial Margin、total Maintenance Margin、Working Order Margin Reservation与Available Margin。所有Money使用唯一settlement Currency/Scale；ordered tuples按Position key canonical order；
13. Aggregate formulas exact为：`total_unrealized = Σ instrument_unrealized_money`；`equity = wallet_balance + total_unrealized`；`total_initial_margin = Σ g09e.initial_margin`；`total_maintenance_margin = Σ g09e.maintenance_margin`；`working_order_margin_reservation = Σ reservation_state.totals.margin`；`available_margin = equity - total_initial_margin - working_order_margin_reservation`。Negative Equity或Available Margin保留signed Money，不clamp、不返回business failure、不自行产生Liquidation；
14. Business failure first precedence exact为：`MISSING_LEDGER_EVIDENCE` → `MISSING_RESERVATION_EVIDENCE` → `ACCOUNT_CONTEXT_MISMATCH` → `LEDGER_PROJECTION_INSTANT_MISMATCH` → `LEDGER_NOT_AVAILABLE` → `RESERVATION_PROJECTION_INSTANT_MISMATCH` → `RESERVATION_NOT_AVAILABLE` → `SETTLEMENT_CASH_CONTEXT_MISMATCH` → `DUPLICATE_POSITION` → `POSITION_CONTEXT_MISMATCH` → `DUPLICATE_MARGIN_RESULT` → `MARGIN_COVERAGE_MISMATCH` → `MARGIN_CONTEXT_MISMATCH` → `VALUATION_COVERAGE_MISMATCH` → `VALUATION_MARK_PURPOSE_MISMATCH` → `VALUATION_MARK_CONTEXT_MISMATCH` → `VALUATION_MARK_INSTANT_MISMATCH` → `VALUATION_MARK_SCALE_MISMATCH` → `NON_POSITIVE_VALUATION_MARK` → `VALUATION_MARK_POLICY_MISMATCH` → `VALUATION_MARK_NOT_AVAILABLE` → `QUANTIZATION_SCALE_MISMATCH` → `UNSAFE_UNREALIZED_PNL_ROUNDING` → `RESERVATION_CONTEXT_MISMATCH` → `RESERVATION_MARGIN_CONTEXT_MISMATCH`；wire values为对应lower-snake-case，多缺陷只返回第一项；
15. Exact predicates分别覆盖：(1–2) optional evidence缺失；(3) Ledger Schema/keys含其他Account/Venue/Cash Currency authority；(4–7) Ledger/Reservation projected-through或full availability错误；(8) Cash key/type/schema/Scale错误；(9–10) Position duplicate、flat、Contract/Quantity/Ledger mismatch；(11–13) G09E Result duplicate、coverage或Position/Contract/time/exposure/Currency/Scale mismatch；(14) Valuation coverage mismatch；(15–21) Mark/Policy错误；(22–23) Quantization错误；(24–25) Reservation account/state或margin Currency/Scale错误。Candidate exact type、canonical text/hash、positive denominator与existing nested authority shape错误是constructor exception；
16. Failure保存component、完整Request/request hash、code与exact `subject_ids=(code.value,request.account_id,str(request.venue_id),canonical_sha256(request.settlement_cash_registration),ledger_state_hash or "missing-margin-ledger",reservation_state_hash or "missing-margin-reservation")`；constructor重算first failure。Outcome保存component/request hash与exactly-one Projection/Failure并重验identity。Component ref使用`ProfilePortType.MARGIN_MODEL`、key `account.linear-perpetual.margin-projection.v1`、version 1；digest preimage exact为`{type="linear_account_margin_projection_component",schema_version=1,component_key,component_version=1,scope="single-account-single-venue-single-settlement-currency",wallet_balance="ledger-settlement-cash",unrealized_pnl="signed-quantity*multiplier*(valuation-mark-average-entry)",equity="wallet-balance+instrument-unrealized-pnl",position_margin="g09e-results",working_order_margin="reservation-state-totals-margin",available_margin="equity-position-initial-margin-working-order-margin",pnl_quantization="half-even-per-instrument",allowed_grade="development"}`；
17. 所有新增public values使用`schema_version=1`、exact types、canonical tuple order与`canonical_sha256`。Canonical preimages exact为：Ledger Evidence `{type="linear_margin_ledger_evidence",schema_version,ledger_state,projected_through,available_at,source_key,source_hash}`；Reservation Evidence `{type="linear_margin_reservation_evidence",schema_version,reservation_state,projected_through,available_at,source_key,source_hash}`；Position Valuation `{type="linear_position_valuation_evidence",schema_version,position_state,resolved_mark,stale_policy}`；Exact PnL `{type="exact_linear_unrealized_pnl",schema_version,currency_id,numerator,denominator}`；per-Position PnL `{type="linear_position_unrealized_pnl",schema_version,valuation_evidence,valuation_evidence_hash,exact_unrealized_pnl,unrealized_pnl}`；Request `{type="linear_account_margin_projection_request",schema_version,account_id,venue_id,evaluated_at,ledger_evidence,position_valuations,margin_results,reservation_evidence,settlement_cash_registration,unrealized_pnl_quantization}`；Projection `{type="linear_account_margin_projection",schema_version,component_ref,request,request_hash,wallet_balance,realized_pnl,fees,funding,position_unrealized_pnl,total_unrealized_pnl,equity,total_initial_margin,total_maintenance_margin,working_order_margin_reservation,available_margin}`；Failure `{type="linear_account_margin_projection_failure",schema_version,component_ref,request,request_hash,code,subject_ids}`；Outcome `{type="linear_account_margin_projection_outcome",schema_version,component_ref,request_hash,projection,failure}`。Constructor拒绝forged aggregate、hash、coverage与component；
18. Static golden沿用G09A–G09E synthetic linear perpetual fixtures，至少冻结：Long/Short price up/down、Flat omission、multiplier `0.125`、exact average entry与VALUATION Mark；multi-Instrument same account aggregation；Wallet Cash含Realized/Fee/Funding attribution但Equity不double count；G09E Initial/Maintenance totals；zero/nonzero/multiple Working Order margin reservations；positive/zero/negative Available Margin；HALF_EVEN ties、large integer/no-pre-quantization；full availability边界；全部25 failures与multi-defect precedence；constructor/hash/aggregate forgery、same Request idempotency和input/module authority不变；
19. Purity scanner显式扫描`account_margin.py`，只允许stdlib、domain、G09A/G09E、marks、generic Ledger/Reservation/Ports imports；拒绝filesystem、network/provider/process/database/cloud、dynamic import、PortfolioSnapshot/Runtime/Profile import、mutable module/class/decorator state与wall clock。Generic Ledger、PortfolioSnapshotProjector、ReservationBook、PreTradeRiskEvaluator、Engine、Runner、Timeline不得增加Linear Account Margin branch/reference；
20. G09F不拥有provider wallet balance mapping、cross/isolated mode、multi-asset collateral、FX/stablecoin peg、haircut、Margin Ratio、Liquidation/Bankruptcy price、ADL、order acceptance、reservation creation、Journal replay composition、PortfolioSnapshot replacement、Runtime dispatch、真实交易、result grade或deployment authorization。G09G拥有conservative Liquidation audit，G09H拥有injected reconstruction/composition，G10F拥有provider account mapping。

G09F authoritative Wallet、Unrealized formula、G09E coverage、Reservation margin、Equity与Available Margin semantics已冻结，可在不选择provider的情况下实现synthetic development-grade seam。

### G09F Implementation Acceptance

1. Pure `account_margin` deep module与root exports已实现；未新增Port、Profile、Adapter、Package、依赖，也未修改Generic Ledger、PortfolioSnapshotProjector、ReservationBook、PreTradeRiskEvaluator或Runtime；
2. Full-availability Ledger/Reservation evidence、single Account/Venue/Currency context与settlement Cash authority均fail closed，Wallet/Realized/Fee/Funding exact取既有Ledger State且不double count attribution；
3. G09A signed Position、multiplier、exact average entry与VALUATION Mark形成GCD-reduced exact Unrealized PnL，并在每Instrument Money boundaryHALF_EVEN量化一次；Long/Short方向与large integer-safe arithmetic通过；
4. Non-flat Position、Ledger quantity、G09E Result与VALUATION Evidence使用exact coverage；multi-Instrument同账户aggregate、duplicate/missing/extra/context mismatch均fail closed；
5. Equity、Initial/Maintenance totals、Working Order Margin Reservation与Available Margin按frozen公式聚合；Reservation其他dimensions不进入aggregate，negative Available Margin保留为Projection状态；
6. Frozen 25-code precedence、ordered subjects、component/canonical identity、Projection/per-Position/Exact constructor forgery、same Request idempotency与input authority不变全部通过；
7. Boundary scanner显式覆盖`account_margin.py`并继续拒绝Ledger、SnapshotProjector、ReservationBook、PreTradeRiskEvaluator与Runtime account-margin branch；
8. 70-file Import Boundary、70-source mypy、Primary LSP、scoped pi-lens blocking diagnostics、full regression与`uv lock --check`全部通过。

G09F implementation 已冻结在 immutable commit `107b41aafee00195ec0ae0031800a1409e016264`，状态为 `PASSED`。

验证记录：

```text
G09F contract                                                       9 passed
G09F static golden                                                  1 passed
Frozen public/boundary regression command                         109 passed
Combined G09F acceptance report                                  119 passed
Full test suite                                                   948 passed
Trading-kernel import boundary                                     PASS (70 files)
mypy                                                                 no issues (70 source files)
Primary LSP + scoped pi-lens                                        no blocking issues
uv lock --check                                                     PASS
Python                                                               3.13.5
```

## 75. G09G Conservative Liquidation Audit Acceptance Card

```yaml
id: G09G
status: PASSED
depends_on:
  - G09E
  - G09F
owner_package: backtest-runtime liquidation audit
public_interface:
  - crypto_quant_backtest.LinearLiquidationAccountWindowEvidence
  - crypto_quant_backtest.LinearLiquidationMarkBarEvidence
  - crypto_quant_backtest.LinearLiquidationAuditClassification
  - crypto_quant_backtest.LinearLiquidationPositionAudit
  - crypto_quant_backtest.LinearLiquidationAuditRequest
  - crypto_quant_backtest.LinearLiquidationAuditResult
  - crypto_quant_backtest.LinearLiquidationAuditFailureCode
  - crypto_quant_backtest.LinearLiquidationAuditFailure
  - crypto_quant_backtest.ConservativeLinearLiquidationAuditModel
  - static synthetic conservative-linear-liquidation-audit golden fixture v1
test_commands:
  contract: uv run pytest -q tests/runtime/liquidation/test_conservative_linear_liquidation_audit.py
  fixture: uv run pytest -q tests/runtime/liquidation/test_conservative_linear_liquidation_audit_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py tests/architecture/test_derivative_boundary.py tests/architecture/test_liquidation_audit_boundary.py tests/runtime/ports/test_simulation_port_contracts.py tests/kernel/derivatives/test_linear_margin_requirement.py tests/kernel/derivatives/test_linear_account_margin_projection.py tests/runtime/engine/test_engine_harness.py tests/runtime/runner/test_auditable_runner.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g09g-import-boundary-report.json
fixture_ids:
  - synthetic-conservative-linear-liquidation-audit-v1
expected_artifacts:
  - tests/fixtures/runtime/liquidation/conservative-linear-liquidation-audit-v1.json
  - build/acceptance/g09g-pytest.xml
  - build/acceptance/g09g-import-boundary-report.json
failure_contracts:
  - current-engine-ledger-reservation-or-position-state-is-read-implicitly
  - account-window-does-not-cover-the-whole-audited-bar
  - liquidation-bar-gap-duplicate-extra-future-or-unclosed-evidence-is-guessed
  - trade-execution-valuation-margin-settlement-or-funding-bar-substitutes-liquidation-mark
  - long-does-not-use-low-or-short-does-not-use-high
  - contract-multiplier-or-exact-average-entry-is-omitted-from-adverse-pnl
  - current-maintenance-margin-is-reused-at-the-adverse-short-high
  - adverse-notional-is-quantized-before-tier-selection
  - adverse-unrealized-or-maintenance-is-rounded-with-the-wrong-policy
  - working-order-reservation-or-available-margin-is-used-as-liquidation-threshold
  - ambiguous-bar-path-is-labelled-as-an-exact-liquidation
  - decision-grade-ambiguous-breach-is-returned-as-a-success
  - liquidation-trigger-fill-partial-close-bankruptcy-adl-or-journal-side-effect-is-created
  - provider-symbol-wallet-mode-or-closeout-semantics-leak-into-g09g
allowed_grade: development
evidence:
  - pytest-report
  - static-conservative-liquidation-audit-golden-hash
  - account-window-full-interval-authority-evidence
  - liquidation-mark-bar-purpose-source-and-availability-evidence
  - long-low-short-high-adverse-extreme-evidence
  - exact-adverse-unrealized-pnl-evidence
  - adverse-notional-tier-and-maintenance-recalculation-evidence
  - safe-and-ambiguous-account-total-evidence
  - decision-grade-ambiguity-fail-closed-evidence
  - no-trigger-time-closeout-or-account-mutation-evidence
  - import-boundary-report
  - static-type-report
passed_commit: 1a8428530133a7c9173dd9afc800d7dd5e8d304e
artifact_hashes:
  tests/fixtures/runtime/liquidation/conservative-linear-liquidation-audit-v1.json: sha256:4942cd57de4b80430fd8640ef6d5e768dce7c5d377d4e8c58b057fa0a4ddcf91
  build/acceptance/g09g-pytest.xml: sha256:6a401907cc94c2061e2547c547cefa2df59fab560153e5082068eeec8bc758df
  build/acceptance/g09g-import-boundary-report.json: sha256:bcc88ff37de79f9c27fe4a419fc59e3fc3033bf14ea618301710a784a660160e
```

### G09G Acceptance

1. G09G只新增pure `crypto_quant_backtest.liquidation_audit` deep module与runtime root exports，结构化实现既有`LiquidationAuditModel.audit_liquidation(request)`并返回`SimulationPortOutcome[LinearLiquidationAuditResult,LinearLiquidationAuditFailure]`；不得新增Port/Profile/Adapter/Package/依赖，或修改Engine、Runner、Timeline、Resolution、Integrity、Generic Ledger、G09E/G09F；
2. `LinearLiquidationAuditRequest` exact保存optional Account Window Evidence、optional ordered Liquidation Mark Bar tuple、`audit_at: SimulationInstant`与既有`RequestedResultGrade`。Optional只用于structured missing-evidence failures；Model不接收Engine/current Ledger/current Reservation/current Position或future Bar stream；
3. `LinearLiquidationAccountWindowEvidence` exact保存完整G09F Projection、half-open `interval_start/interval_end_exclusive`、完整`available_at: SimulationInstant`与source key/hash。Interval必须nonempty，Projection Request evaluated-at exact等于interval start；evidence声明该Projection的Ledger/Position/Margin/Reservation authority在整个interval无mutation，且interval end不晚于evidence available-at UTC；audit-at不得早于available-at；
4. `LinearLiquidationMarkBarEvidence` exact保存stable bar ID、Instrument、Price purpose、同一half-open interval、low/high Price、`closed_at: SimulationInstant`、`available_at: SimulationInstant`、stream/event/revision/supersession/source key/hash。Constructor只验证exact types、canonical text/hash与nonempty interval，并保留purpose、nonpositive/reversed extremes、timing和Contract context defects供Request structured business validation；
5. 每个G09F non-flat Position exact有且只有一个matching Bar，不允许duplicate、missing或extra。所有Bars interval必须exact等于Account Window，`closed_at.instant >= interval_end_exclusive`、closed-at不晚于available-at、available-at不晚于audit-at；不同interval、future/unclosed evidence不按最近Bar、tuple最后项或current stream fallback；Flat account允许empty Bar tuple并返回SAFE；
6. Bar purpose必须LIQUIDATION；Instrument、settlement/quote Currency和Price Scale匹配Position Contract。Trade、Execution Reference、Valuation、Margin、Settlement、Funding或generic OHLC不得替代。Long (`quantity.units > 0`) adverse Price exact为low；Short (`< 0`) exact为high；
7. 每Position adverse Unrealized复用G09F exact formula：若Quantity `q/Q`、multiplier `m/M`、adverse Price `p/P`、average entry `a/A`，则`U=q*m*(p*A-a*P)/(Q*M*P*A)`，GCD约分后按G09F `unrealized_pnl_quantization`在每Instrument调用一次HALF_EVEN。不得从current valuation PnL做delta rounding、使用float/Decimal或忽略multiplier；
8. 每Position adverse Maintenance使用matching G09E Result内resolved historical Interval/Tier tuple和Request Quantization authority。先以adverse exact notional `N=abs(q)*m*p/(Q*M*P)`重新选择lower-inclusive/upper-exclusive Tier，再按`N*maintenance_rate-maintenance_deduction`计算GCD-reduced exact amount并CEILING一次。不得复用G09F current Maintenance，尤其Short-high必须允许notional跨Tier；negative adverse Maintenance是authority inconsistency并structured fail closed；
9. `LinearLiquidationPositionAudit` exact嵌入G09F `LinearPositionValuationEvidence`、matching G09E Result与Bar，并保存Position key、direction、adverse Price、resolved adverse Tier、exact/quantized adverse Unrealized与Maintenance。Tuple按Position key canonical order；constructor从embedded Position/Bar/G09E authority重算全部字段，Result再验证它们exact覆盖Account Projection；
10. Account adverse totals exact为：Wallet Balance继续使用G09F Projection wallet；`adverse_unrealized = Σ per-position adverse unrealized Money`；`adverse_equity = wallet + adverse_unrealized`；`adverse_maintenance = Σ per-position adverse maintenance Money`。Working Order Margin Reservation、Initial Margin、Available Margin、Fee/Funding attribution不得加减Liquidation threshold；
11. `LinearLiquidationAuditClassification` wire values exact为`safe`与`ambiguous_breach`。若`adverse_equity.units >= adverse_maintenance.units`则SAFE，否则AMBIGUOUS_BREACH；equality为SAFE。Classification只证明在同时方向最不利extremes下是否仍安全，不证明extremes同时发生或bar内path/time；
12. Development-grade SAFE/AMBIGUOUS均返回Result；Result保存component、完整Request/hash、classification、ordered Position audits、Wallet、adverse totals、`decision_grade_eligible=(classification is SAFE)`与exact limitation `bar-extremes-do-not-identify-intrabar-path-or-liquidation-time`。Decision-grade SAFE返回Result；Decision-grade AMBIGUOUS返回`AMBIGUOUS_BREACH_NOT_DECISION_GRADE` Failure；
13. Business failure first precedence exact为：`MISSING_ACCOUNT_WINDOW` → `MISSING_LIQUIDATION_BARS` → `PROJECTION_CONTEXT_MISMATCH` → `ACCOUNT_WINDOW_INTERVAL_MISMATCH` → `ACCOUNT_WINDOW_NOT_AVAILABLE` → `DUPLICATE_LIQUIDATION_BAR` → `LIQUIDATION_BAR_COVERAGE_MISMATCH` → `LIQUIDATION_BAR_INTERVAL_MISMATCH` → `LIQUIDATION_BAR_NOT_CLOSED` → `LIQUIDATION_BAR_NOT_AVAILABLE` → `LIQUIDATION_BAR_PURPOSE_MISMATCH` → `LIQUIDATION_BAR_CONTEXT_MISMATCH` → `LIQUIDATION_BAR_SCALE_MISMATCH` → `INVALID_LIQUIDATION_BAR_EXTREMES` → `NEGATIVE_ADVERSE_MAINTENANCE` → `AMBIGUOUS_BREACH_NOT_DECISION_GRADE`；wire values对应lower-snake-case，多缺陷只返回第一项；
14. Exact predicates分别覆盖：(1) Window缺失；(2) non-flat Projection下Bars缺失，Flat+empty成功；(3) G09F component/request/result/context/hash不闭合；(4–5) Window start/end/evaluated-at或full availability错误；(6–7) Bar duplicate/coverage；(8–10) interval/closed/full availability错误；(11–14) purpose/Instrument/Currency/Scale/positivity/low-high错误；(15) adverse Maintenance exact负；(16) requested Decision Grade且classification ambiguous。Candidate exact type、canonical text/hash、interval nonempty与nested authority shape错误是constructor exception；
15. Failure exact保存component、完整Request/input hash、code与`subject_ids=(code.value,account_projection_hash or "missing-account-window",str(request.audit_at.instant.epoch_nanoseconds),requested_grade.value)`并重算first failure。Result/Failure满足`SimulationPortContract`；`SimulationPortOutcome` component/input hash/exactly-one value必须匹配；
16. Component ref exact使用`SimulationPortType.LIQUIDATION_AUDIT_MODEL`、key `conservative.linear-perpetual.liquidation-audit.v1`、version 1。Digest preimage exact为`{type="conservative_linear_liquidation_audit_component",schema_version=1,component_key,component_version=1,account_scope="g09f-single-account-projection",bar_purpose="liquidation",long_extreme="low",short_extreme="high",unrealized="g09f-formula-half-even",maintenance="g09e-adverse-notional-tier-ceiling",classification="safe-or-ambiguous-breach",decision_grade="ambiguous-fails-closed",limitation="bar-extremes-do-not-identify-intrabar-path-or-liquidation-time",allowed_grade="development"}`；
17. Canonical preimages exact为：Window `{type="linear_liquidation_account_window_evidence",schema_version,account_projection,interval_start,interval_end_exclusive,available_at,source_key,source_hash}`；Bar `{type="linear_liquidation_mark_bar_evidence",schema_version,bar_id,instrument_id,price_purpose,interval_start,interval_end_exclusive,low,high,closed_at,available_at,stream_id,event_id,revision_id,supersedes_revision_id,source_key,source_hash}`；Position Audit `{type="linear_liquidation_position_audit",schema_version,position_valuation,margin_result,position_key,direction,bar,adverse_price,resolved_tier,exact_adverse_unrealized,adverse_unrealized,exact_adverse_maintenance,adverse_maintenance}`；Request `{type="linear_liquidation_audit_request",schema_version,account_window,liquidation_bars,audit_at,requested_grade}`；Result `{type="linear_liquidation_audit_result",schema_version,component_ref,request,input_hash,classification,position_audits,wallet_balance,adverse_unrealized,adverse_equity,adverse_maintenance,decision_grade_eligible,limitation}`；Failure `{type="linear_liquidation_audit_failure",schema_version,component_ref,request,input_hash,code,subject_ids}`；所有constructor重算identity、first failure、position/audit totals与classification；
18. Static golden沿用G09A–G09F fixtures，至少冻结：Long low safe/breach、Short high safe/breach、equality SAFE、mixed Long/Short simultaneous extremes、adverse notional同Tier与跨Tier、multiplier/average-entry/no-pre-quantization、HALF_EVEN Unrealized与CEILING Maintenance ties、Flat empty Bars、full availability/closed boundary、全部16 failures与multi-defect precedence、development ambiguous Result、decision-grade ambiguous Failure、constructor/hash/aggregate forgery、same Request idempotency和input/module authority不变；
19. Purity scanner显式扫描`liquidation_audit.py`，只允许stdlib、domain、market-data contracts identity types、G09E/G09F、runtime Ports/RequestedResultGrade imports；拒绝filesystem、network/provider/process/database/cloud、dynamic import、Engine/Runner/Timeline/Integrity/Profile import、mutable module/class/decorator state与wall clock。Engine、Runner、Timeline、Ledger、G09E/G09F不得新增Liquidation branch/reference；
20. G09G不创建Liquidation Trigger/Fill/Order/Journal、精确trigger time/price、partial liquidation、bankruptcy、insurance fund、ADL、closeout、provider leverage/wallet/mode mapping、Runtime dispatch、真实交易、result authorization或deployment authorization。G09H拥有injected composition/audit artifact routing，G10F拥有provider semantics，未来tick/microstructure model才可提供更精确path evidence。

G09G Account Window、Liquidation Mark Bar、adverse PnL/Maintenance与SAFE/AMBIGUOUS/decision-grade routing已冻结，可实现synthetic development-grade conservative audit。

### G09G Implementation Acceptance

1. Pure `liquidation_audit` runtime deep module与root exports已实现，结构化满足既有`LiquidationAuditModel`/`SimulationPortOutcome`；未新增Port、Profile、Adapter、Package、依赖或修改Engine、Runner、Timeline、Resolution、Integrity、Ledger、G09E/G09F；
2. G09F Account Window full-interval authority与LIQUIDATION Mark closed Bar purpose/context/coverage/availability全部fail closed；current state、其他Price purpose与最近/current Bar不作fallback；
3. Long-low、Short-high、mixed Long/Short simultaneous extremes、multiplier-aware exact adverse Unrealized与HALF_EVEN Money boundary均通过；
4. Adverse exact notional在未量化状态重新选择G09E historical Tier并按Maintenance rate/deduction与CEILING重算；Short-high跨Tier和negative adverse Maintenance均有独立控制；
5. Wallet、adverse Unrealized/Equity/Maintenance totals与equality SAFE按frozen公式分类；Working Order Reservation、Available Margin与attributions不进入threshold；
6. Development SAFE/AMBIGUOUS均保存完整Position audit与limitation；Decision-grade AMBIGUOUS structured fail closed，不生成trigger time/price、Fill、Journal、partial close、bankruptcy或ADL；
7. Frozen 16-code precedence、ordered subjects、component/canonical identity、Result/Position/Failure forgery、same Request idempotency与input authority不变全部通过；
8. Dedicated purity scanner覆盖`liquidation_audit.py`并拒绝Engine、Runner、Timeline、Ledger、G09E/G09F liquidation branch；71-file Import Boundary、71-source mypy、Primary LSP、scoped pi-lens blocking diagnostics、full regression与`uv lock --check`全部通过。

G09G implementation 已冻结在 immutable commit `1a8428530133a7c9173dd9afc800d7dd5e8d304e`，状态为 `PASSED`。

验证记录：

```text
G09G contract                                                      10 passed
G09G static golden                                                  1 passed
Frozen public/boundary regression command                          90 passed
Combined G09G acceptance report                                  101 passed
Full test suite                                                   961 passed
Workspace import boundary                                          PASS (71 files)
mypy                                                                 no issues (71 source files)
Primary LSP + scoped pi-lens                                        no blocking issues
uv lock --check                                                     PASS
Python                                                               3.13.5
```

## 76. G09H Generic Linear Perpetual Composition Acceptance Card

```yaml
id: G09H
status: PASSED
depends_on:
  - G09A
  - G09B
  - G09C
  - G09D
  - G09E
  - G09F
  - G09G
owner_package: tests/support + backtest-runtime profile composition
public_interface:
  - crypto_quant_backtest.FinancialDispatcherSpec
  - crypto_quant_backtest.FeeAccountingDispatchPlan
  - crypto_quant_backtest.FillAccountingDispatchPlan
  - crypto_quant_backtest.ScheduledAccountEvent
  - crypto_quant_backtest.FinancialDispatchPlan
  - crypto_quant_backtest.FinancialDispatchArtifact
  - crypto_quant_backtest.FinancialDispatchResult
  - crypto_quant_backtest.FinancialDispatchFailureCode
  - crypto_quant_backtest.FinancialDispatchFailure
  - crypto_quant_backtest.FinancialDispatchOutcome
  - crypto_quant_backtest.FinancialEventDispatcher
  - existing crypto_quant_backtest.ResolvedExecutionCase canonical financial dispatch plan extension
  - existing crypto_quant_backtest.ResolvedBarExecution profile-neutral fill accounting dispatch extension
  - existing crypto_quant_backtest.DeterministicBarEngine injected financial dispatcher seam
  - existing crypto_quant_backtest.EngineFailureCode.FINANCIAL_DISPATCH_FAILURE
  - existing crypto_quant_backtest.EngineExecutionResult canonical financial artifacts extension
  - existing crypto_quant_backtest.ExecutionCaseComposer semantic identity coverage
  - existing crypto_quant_backtest.AuditableBacktestRunner unchanged execution interface
  - tests.support.synthetic_market.SyntheticLinearPerpetualDevelopmentProfile
  - tests.support.synthetic_market.build_synthetic_linear_perpetual_execution_case
  - tests.support.synthetic_market.build_synthetic_linear_perpetual_resolved_request
  - static synthetic linear-perpetual development journey golden fixture v1
test_commands:
  contract: uv run pytest -q tests/runtime/engine/test_financial_dispatch_contracts.py tests/support/synthetic_market/test_synthetic_linear_perpetual_profile.py tests/runtime/engine/test_g09h_synthetic_linear_perpetual_journey.py
  fixture: uv run pytest -q tests/runtime/engine/test_g09h_synthetic_linear_perpetual_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py tests/architecture/test_derivative_boundary.py tests/architecture/test_liquidation_audit_boundary.py tests/architecture/test_g09h_composition_boundary.py tests/runtime/engine/test_engine_harness.py tests/runtime/engine/test_g06_synthetic_cash_journey.py tests/runtime/runner/test_auditable_runner.py tests/runtime/resolution/test_backtest_resolution.py && uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g09h-import-boundary-report.json
fixture_ids:
  - synthetic-linear-perpetual-development-journey-v1
expected_artifacts:
  - tests/fixtures/runtime/engine/synthetic-linear-perpetual-development-journey-v1.json
  - build/acceptance/g09h-pytest.xml
  - build/acceptance/g09h-import-boundary-report.json
failure_contracts:
  - financial-dispatcher-is-missing-or-does-not-match-the-canonical-case-plan
  - dispatcher-implementation-object-or-runtime-address-enters-case-or-semantic-identity
  - cash-versus-linear-derivative-branch-is-added-to-engine-runner-ledger-or-composer
  - fill-accounting-plan-does-not-exact-match-the-produced-fill-or-profile-component
  - derivative-fill-exchanges-principal-notional-or-uses-cash-lot-accounting
  - scheduled-account-event-is-missing-duplicated-reordered-or-dispatched-before-availability
  - funding-uses-current-position-or-non-funding-mark-instead-of-eligibility-evidence
  - margin-or-liquidation-reads-current-engine-state-without-a-frozen-authority-window
  - dispatcher-journal-output-is-not-append-only-replayable-or-generic-ledger-compatible
  - financial-artifact-is-partial-unordered-unbound-to-source-event-or-not-canonical
  - final-margin-projection-cannot-be-rebuilt-from-final-journal-and-frozen-inputs
  - final-portfolio-snapshot-cannot-be-rebuilt-from-final-ledger-margin-and-mark-authority
  - liquidation-audit-artifact-is-omitted-or-creates-closeout-side-effects
  - execution-case-semantic-spec-omits-dispatcher-plan-events-or-snapshot-authority
  - retry-batch-size-or-input-registration-order-changes-economic-or-artifact-hashes
  - synthetic-profile-loads-without-explicit-development-opt-in
  - synthetic-profile-accepts-decision-grade-or-authorizes-deployment
  - binance-symbol-fee-rule-wallet-mode-tier-adapter-or-provider-semantics-leak-into-g09h
allowed_grade: development
evidence:
  - pytest-report
  - static-synthetic-linear-perpetual-journey-golden-hash
  - resolved-profile-and-financial-dispatcher-spec-hashes
  - open-reduce-flip-position-transition-evidence
  - funding-eligibility-settlement-and-specialized-journal-evidence
  - generic-ledger-and-linear-derivative-replay-parity-evidence
  - current-and-final-margin-projection-reconstruction-evidence
  - long-low-and-short-high-liquidation-audit-artifacts
  - final-portfolio-snapshot-reconstruction-evidence
  - execution-case-semantic-spec-and-identity-manifest-coverage
  - auditable-runner-development-only-evidence
  - no-derivative-branch-boundary-report
  - import-boundary-report
  - static-type-report
passed_commit: e0f2bc767dc87513d562becd9907262628b788e6
artifact_hashes:
  - tests/fixtures/runtime/engine/synthetic-linear-perpetual-development-journey-v1.json: sha256:162af5d5e236def3333d2bc5e3485f52c24a763405f58c004204e5ee143d271c
  - build/acceptance/g09h-pytest.xml: sha256:3d1d53a620726b3cbbe239fc58b68fe2ea74035b901def834a25c84316aba185
  - build/acceptance/g09h-import-boundary-report.json: sha256:9d36601649bcc115d18a47f56362257f058b142d4bac608279231e9ee32641b5
```

### G09H Acceptance

1. G09H只拥有Synthetic Linear Perpetual development Profile、profile-neutral Runtime financial dispatch composition与完整Journey Fixture；不新增Binance/provider Adapter、真实fee/tier/wallet/margin-mode语义、live/deployment权限或decision-grade声明；
2. Generic `DeterministicBarEngine`只新增单一injected financial dispatcher seam。Engine按canonical Plan调用`book_fill`、`dispatch_scheduled_event`与`project_final_snapshot`，不得导入、`isinstance`、match或按名称判断G09A–G09G、Linear Perpetual、Cash Instrument、Binance、Funding、Margin或Liquidation concrete types；`AuditableBacktestRunner`、Timeline、Generic Ledger同样不得新增derivative条件分支；
3. 既有Cash journey必须通过同一dispatcher interface迁移，不保留`None`分支或绕过dispatcher的inline accounting path。无参数Engine constructor可构造immutable default Cash dispatcher以保持既有调用兼容；Synthetic Linear必须显式注入。至少两个实现证明该seam不是单实现包装；显式传入`None`/invalid dispatcher、dispatcher spec与Case Plan不匹配或dispatcher方法缺失均在执行前fail closed；
4. `ResolvedExecutionCase` exact携带immutable canonical `FinancialDispatchPlan`；Plan只包含versioned dispatcher spec、ordered scheduled Account Events、final Snapshot authority与expected artifact roles，不包含implementation object、callback、module path、memory address、Attempt ID或wall clock。Per-Fill Plan继续由对应`ResolvedBarExecution`保存。Case canonical hash和ExecutionCaseSemanticSpec financial/snapshot inputs exact覆盖Dispatcher Plan和全部Fill Plans；
5. Canonical v1 preimages exact为：Dispatcher Spec `{type="financial_dispatcher_spec",schema_version=1,dispatcher_key,dispatcher_version,config_hash,position_accounting_component,financing_component,margin_component,liquidation_audit_component,snapshot_projection_key,snapshot_projection_version}`；Fee Plan `{type="fee_accounting_dispatch_plan",schema_version=1,cash_key,final_fee_rule_set,fee_assessment_id,fee_assessment_time,fee_journal_entry_id,fee_recorded_at}`；Fill Plan `{type="fill_accounting_dispatch_plan",schema_version=1,source_event_id,expected_fill_id,position_accounting_component,position_payload,fill_journal_entry_id,fill_recorded_at,fee_plan,expected_artifact_roles}`；Scheduled Event `{type="scheduled_account_event",schema_version=1,event_id,event_at,operation_key,component_keys,payload,expected_artifact_roles}`；Financial Plan `{type="financial_dispatch_plan",schema_version=1,dispatcher_spec,scheduled_account_events,final_snapshot_payload,expected_artifact_roles}`；Artifact `{type="financial_dispatch_artifact",schema_version=1,role,source_event_id,occurred_at,component_key,component_version,component_digest,input_hash,result_hash,payload}`；Result `{type="financial_dispatch_result",schema_version=1,dispatcher_spec,source_event_id,journal_entries,position_lot_books,artifacts,snapshot}`；Failure `{type="financial_dispatch_failure",schema_version=1,dispatcher_spec,source_event_id,input_hash,code,subject_ids}`；Outcome `{type="financial_dispatch_outcome",schema_version=1,dispatcher_spec,input_hash,result,failure}`。Tuple按`(occurred_at,source_event_id,role)`canonical排序；payload必须满足canonical contract且constructor重算全部hash；
6. `ResolvedBarExecution`只保存profile-neutral `FillAccountingDispatchPlan`。共同字段exact绑定source Bar Event、expected Fill ID、Position Accounting component ref、Journal ID/recorded-at与Fee accounting authority；payload可由Cash或Linear dispatcher解释，但Engine不得读取concrete payload字段。实际Fill identity/hash/context不匹配时不得产生Journal或partial artifact；
7. Scheduled Account Event由stable Event ID、完整`SimulationInstant`、versioned operation key、component refs、canonical payload与expected artifact roles组成，并由Timeline Event exact触发。缺失、duplicate、extra、已处理重放、event instant/context mismatch、available-at晚于dispatch或运行结束仍未处理均structured fail closed；Engine不根据operation key做经济分支，只把事件和immutable state view交给injected dispatcher；
8. `FinancialEventDispatcher` exact提供immutable `spec`及`book_fill(plan,fill,state_view)`、`dispatch_scheduled_event(event,state_view)`、`project_final_snapshot(plan,state_view)`。它只接收immutable Plan与当前Journal、Generic Ledger State、ResourceReservationState、已有canonical financial artifacts及必要Cash lot state；统一返回`FinancialDispatchOutcome`。Result可返回append-only Journal Entries、replacement Cash lot state、ordered canonical artifacts或Final PortfolioSnapshot；Fill/Event调用snapshot必须None，Snapshot调用journal entries必须empty。Outcome必须exactly one Result/Failure并绑定Spec/input hash；Failure codes first precedence exact为`DISPATCHER_SPEC_MISMATCH` → `FILL_PLAN_MISMATCH` → `EVENT_PLAN_MISMATCH` → `PROFILE_COMPONENT_FAILURE` → `JOURNAL_APPEND_FAILURE` → `ARTIFACT_COVERAGE_MISMATCH` → `SNAPSHOT_PROJECTION_FAILURE`。任一Failure或Result shape/append/coverage mismatch由Engine统一映射`EngineFailureCode.FINANCIAL_DISPATCH_FAILURE`并保留dispatcher failure hash，不发布partial Result；Engine负责Journal append与Generic Ledger重放；dispatcher不得mutate Engine state、读取filesystem/network/provider/current profile registry或调用wall clock；
9. Cash dispatcher必须保持G06/G07现有`CashInstrumentAccounting`、Fee、Lot、Ledger、Snapshot和result hash语义；Linear dispatcher对Fill exact调用G09A projector产生OPEN/ADD/REDUCE/CLOSE/FLIP Transition，再调用G09B translator生成specialized Journal Entry。Linear Fill不得交换principal notional、不得创建Cash acquisition lot；Fee仍沿既有generic fee assessment/journal path独立记账；
10. Fixture chronology冻结为single Account/Venue/settlement Currency、single Linear Perpetual Contract、三次deterministic full Fill形成Long OPEN → partial REDUCE → FLIP to Short。每次Transition、G09B Entry、Generic Ledger signed Position和`LinearDerivativeLedgerProjector` exact state/hash必须一致；
11. Funding Event发生在Long position之后和partial close之前。Linear dispatcher使用G09C supplied closed publication revision chain、historical eligibility Journal prefix/Snapshot和FUNDING Mark解析唯一Eligibility，再调用G09D FinancingModel产生唯一Funding specialized Entry；不得读取current/final Position、使用Valuation/Margin/Liquidation/Execution price或按Bar均摊；
12. Margin audit events至少覆盖Long与final Short。每次由当前immutable Journal/Generic Ledger重建G09B Position authority，使用同Instant的VALUATION Mark、MARGIN Mark、historical leverage/rule book和Reservation authority调用G09E/G09F；Working Order Margin只降低Available Margin。Final G09F Projection必须能仅凭Final Journal、frozen marks/rules/reservations与Plan重建并取得exact同一projection hash；
13. Liquidation audit events分别覆盖Long-low与Short-high closed LIQUIDATION Mark Bar，且Account Window证明对应full bar interval无Journal/Reservation mutation。Dispatcher调用G09G并保存SAFE或development AMBIGUOUS完整artifact；不得产生trigger time/price、Order、Fill、Journal、partial close、bankruptcy、ADL或run-end closeout side effect；
14. `EngineExecutionResult.financial_artifacts`是canonical ordered tuple。每个artifact exact保存role、source Timeline Event ID/instant、component ref、request/input hash、result/failure hash与完整typed payload；Plan expected roles必须exact覆盖，禁止missing/duplicate/extra、partial success、tuple order-dependent identity或只保存裸hash而丢失重建authority；
15. Final PortfolioSnapshot由dispatcher在Timeline完成后从Final Generic Ledger、Final G09F Projection、VALUATION Mark references与versioned derivative Snapshot Plan构造；Cash/Position balances和Journal state hash exact等于Final Ledger，realized/fees/financing来自Ledger attribution，unrealized/equity exact等于G09F。Generic spot-style `quantity × mark` projector不得用于Linear derivative equity；
16. Reconstruction tests必须独立完成：(a) Final Journal → Generic Ledger；(b) Final Journal specialized entries → G09B exact Position State；(c) Ledger + Position + frozen marks/rules/reservations → Final G09F Projection；(d) Ledger + Final G09F + Snapshot authority → Final PortfolioSnapshot。四者各自hash与Engine Result exact一致，禁止从Engine mutable side-state抄回；
17. Synthetic Profile key exact为`synthetic.linear-perpetual.development.v1`，必须通过`TestProfileRegistry(allow_development_profiles=True)`显式加载；Market、Simulation、Execution Account registrations及dispatcher spec均固定`grade=development`、`decision_grade_eligible=false`、`deployment_authorized=false`并至少记录`synthetic_market_profile`与`bar-extremes-do-not-identify-intrabar-path-or-liquidation-time` limitations；默认Registry lookup与decision-grade Request必须在Engine执行前structured拒绝；
18. `ExecutionCaseComposer`必须把dispatcher spec、Fill payloads、scheduled Account Events、final Snapshot authority和expected artifact roles纳入ID-free Semantic Spec；Identity Plan exact覆盖新增Funding Settlement/Journal等Domain identities，artifact roles由Financial Dispatch Plan identity覆盖。相同semantic input、不同registration order、Timeline batch size和至少两次独立Attempt产生相同Semantic Run、Case、Manifest、Trace、Journal、Ledger、Margin、Snapshot、artifact与Result hashes；
19. Static golden至少冻结Profile/registration/dispatcher digests、Case semantic hash、identity manifest、三Fill/Transition、partial close realized PnL、Funding eligibility/application、all Journal Entry types、Generic Ledger、G09B final State、Long/Short G09E/G09F、Long-low/Short-high G09G、Final Snapshot、financial artifact roles/hashes、Run End、development limitations与repeat parity；
20. Boundary scanner显式拒绝Engine、Runner、Timeline、Generic Ledger、ExecutionCaseComposer中的`LinearDerivative*`、`LinearPerpetual*`、`Funding*`、`Margin*`、`Liquidation*` imports/name branches；仅tests/support synthetic linear dispatcher可导入G09A–G09G concrete modules。Production runtime不能导入tests/support；test profile不能使用filesystem/network/process/database/cloud/provider SDK或新增dependency；
21. G09H不拥有historical provider completeness、Binance symbol/contract/order/fee/tier/funding/wallet/margin-mode mapping、真实Liquidation、multi-currency collateral、cross/isolated semantics、ADL、live trading、deployment authorization或parity。G10A–G10F拥有provider adapters，G10G才拥有resolved Binance E2E，G10H拥有parity。

G09H branchless dispatcher、event chronology、artifact routing、reconstruction、identity、development-only与boundary contracts已冻结，可实现Synthetic Linear Perpetual E2E；冻结后不得以test-only callback绕过Generic Engine/Runner canonical composition。

Readiness baseline：

```text
G09A–G09G + Engine/Runner/Resolution/Profile focused baseline      141 passed
Full test suite                                                     961 passed
Workspace import boundary                                           PASS (71 files)
mypy                                                                  no issues (71 source files)
Primary/scoped document diagnostics                                  no blocking issues
uv lock --check                                                      PASS
Python                                                                3.13.5
```

PASSED validation：

```text
G09H contract + fixture + frozen boundary command                    79 passed
Full test suite                                                     977 passed
Workspace import boundary                                           PASS (72 files)
mypy                                                                  no issues (71 source files)
Primary LSP + scoped pi-lens                                          no blocking errors
uv lock --check                                                       PASS
Python                                                                3.13.5
```

## 77. G10A Binance USDⓈ-M Instrument Identity and Contract Metadata Acceptance Card

```yaml
id: G10A
status: PASSED
depends_on:
  - WP-02A
owner_package: trading-kernel profile adapter
public_interface:
  - crypto_quant_trading.profiles.binance_usdm.BINANCE_USDM_OPEN_ENDED_DELIVERY_AT
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmContractStatus
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmInstrumentMetadataSourceRef
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmInstrumentMetadataRevision
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmInstrumentMetadataQuery
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmListingInterval
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmLinearContractMetadata
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmInstrumentMetadataResolution
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmInstrumentMetadataFailureCode
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmInstrumentMetadataFailure
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmInstrumentMetadataOutcome
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmInstrumentModel
test_commands:
  contract: uv run pytest -q tests/profiles/binance_usdm/test_instrument_metadata.py
  fixture: uv run pytest -q tests/profiles/binance_usdm/test_instrument_metadata_golden.py
  boundary: uv run pytest -q tests/architecture/test_binance_usdm_profile_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  regression: uv run pytest -q tests/domain/instruments/test_identities.py tests/domain/instruments/test_symbol_timeline.py tests/kernel/derivatives/test_linear_positions.py
  acceptance: uv run pytest -q tests/profiles/binance_usdm/test_instrument_metadata.py tests/profiles/binance_usdm/test_instrument_metadata_golden.py tests/architecture/test_binance_usdm_profile_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py tests/domain/instruments/test_identities.py tests/domain/instruments/test_symbol_timeline.py tests/kernel/derivatives/test_linear_positions.py --junitxml=build/acceptance/g10a-pytest.xml
fixture_ids:
  - binance-usdm-exchange-info-revisions-v1
  - binance-usdm-instrument-metadata-v1
expected_artifacts:
  - docs/research/binance-usdm-instrument-metadata-primary-sources.md
  - tests/fixtures/profiles/binance-usdm-exchange-info-revisions-v1.json
  - tests/fixtures/profiles/binance-usdm-instrument-metadata-v1.json
  - build/acceptance/g10a-pytest.xml
  - build/acceptance/g10a-import-boundary-report.json
failure_contracts:
  - missing-revision-set
  - invalid-forked-cyclic-or-noncanonical-revision-chain
  - revision-not-visible-by-captured-at
  - stable-lineage-key-or-revision-identity-mismatch
  - unsupported-contract-type
  - unsupported-or-unknown-contract-status
  - base-quote-margin-currency-context-mismatch
  - invalid-onboard-delivery-or-open-ended-sentinel
  - query-before-listing-or-at-after-finite-delivery
  - overlapping-gapped-or-conflicting-symbol-timeline
  - conflicting-provider-metadata
  - current-symbol-pair-or-currency-derived-identity
  - precision-used-as-tick-step-or-contract-scale
  - source-query-filesystem-network-wall-clock-or-runtime-leakage
allowed_grade: development
evidence:
  - readiness-contract-tests
  - static-source-and-golden-fixture-hashes
  - public-api-import-report
  - import-boundary-report
  - static-type-report
  - dependency-lock-report
passed_commit: 613c319b2dbba9962d4867dcfb3d1b19067d16cf
artifact_hashes:
  tests/fixtures/profiles/binance-usdm-exchange-info-revisions-v1.json: sha256:99030c1dfc9bd0105ce44614494b71753abd6756bf36731b6fa2de8f2bfbdb70
  tests/fixtures/profiles/binance-usdm-instrument-metadata-v1.json: sha256:107b5b57bc0f102552bc986f6363280302d6e3f2ff4fb2e472b380469729c0b6
  build/acceptance/g10a-pytest.xml: sha256:6605797277e79e3716d86bc5c549fad7925bf0ceaa021f30aeb54b328d23afb3
  build/acceptance/g10a-import-boundary-report.json: sha256:078e5ff9eedb95818d2c270a0b630280054eab665f2879944e90267bf6b30e13
```

### G10A Acceptance

冻结边界：

1. G10A是纯离线`crypto_quant_trading.profiles.binance_usdm` Instrument Model，只消费caller-supplied immutable revisions。Production code不得创建provider client、发HTTP、读filesystem/database、读取wall clock或fallback到current API；G12拥有acquisition、parsing、retention和MarketBundle construction；
2. `BinanceUsdmInstrumentMetadataRevision` exact保存`revision_id`、`supersedes_revision_id`、stable lineage key、`symbol`、`pair`、`contract_type`、`status`、`onboard_at`、`delivery_at`、base/quote/margin asset、`effective_from`、`available_at`及source key/hash。Revision hash覆盖全部字段；source key/hash不是可选display metadata；
3. Query exact绑定stable lineage key、economic `effective_at`、knowledge `captured_at`及按`effective_from`/`available_at`/`revision_id`规范排序的revision hashes。Resolver只使用`available_at <= captured_at`的唯一closed linear chain；missing、late-only、fork、cycle、duplicate ID、broken supersedes或输入顺序依赖fail closed；
4. Stable `InstrumentId`只由`VenueId("binance_usdm")`和caller-supplied lineage key确定。禁止从current `symbol`、`pair`、base/quote拼接、去后缀或rebranding关系猜identity。Revision lineage key与Query不一致structured reject；
5. 显式same-lineage Symbol变化形成half-open `SymbolTimeline`且Instrument ID不变；没有显式same-lineage evidence时相似pair、asset或rebranding contract必须产生不同Instrument。Current symbol不能反向覆盖历史interval；
6. v1只资格化`contract_type="PERPETUAL"`的USDⓈ-M Linear subset。Result的`InstrumentDefinition`必须为`InstrumentType.LINEAR_PERPETUAL`，base currency来自`baseAsset`，quote来自`quoteAsset`，settlement来自`marginAsset`，且quote=margin；delivery/quarterly、COIN-M/inverse、quanto或currency conflict structured reject；
7. `BinanceUsdmLinearContractMetadata`只冻结currency context和exact `Rate(1, Scale(0), "base_quantity_per_contract")` multiplier。G10A不得从`pricePrecision`/`quantityPrecision`、decimal display或current filters猜quantity/price scale；G10B拥有historical tick/step/notional，G10G组合G09A `LinearPerpetualContract`；
8. `onboard_at`是listing lower bound。`BINANCE_USDM_OPEN_ENDED_DELIVERY_AT`精确等于official perpetual sentinel `4133404800000` epoch milliseconds，并映射`delisted_at=None`；任何其他finite `delivery_at`形成exclusive delisting boundary。Invalid order、mixed sentinel interpretation或revision conflict fail closed；
9. `effective_at < listed_at`或`effective_at >= finite delisted_at`返回`NOT_LISTED_AT_QUERY_INSTANT` failure，不返回synthetic symbol或current fallback。Delisting不删除Instrument ID、historical `SymbolTimeline`、Revision或source provenance；
10. `BinanceUsdmContractStatus` exact冻结：`PENDING_TRADING`、`TRADING`、`PRE_DELIVERING`、`DELIVERING`、`DELIVERED`、`PRE_SETTLE`、`SETTLING`、`CLOSE`、`TRADING_HALT`、`TRADING_CANCEL_ONLY`。仅active revision的`TRADING`产生`tradable=true`；其他known状态保留为`tradable=false` evidence。G10A不推断reduce-only/no-new-position窗口，G10B拥有该规则；unknown raw status structured reject；
11. Resolver产出`ProfileComponentRef(ProfilePortType.INSTRUMENT_MODEL, "crypto.binance_usdm.instrument_metadata.v1")`、stable `InstrumentDefinition`、full visible `SymbolTimeline`、`BinanceUsdmListingInterval`、linear metadata、active symbol/pair/status/tradability及exact source/revision provenance；相同logical inputs任意tuple顺序必须得到相同canonical outcome；
12. `BinanceUsdmInstrumentMetadataFailureCode` precedence固定为：`MISSING_REVISION_SET`、`INVALID_REVISION_SET`、`REVISION_NOT_AVAILABLE`、`STABLE_IDENTITY_MISMATCH`、`UNSUPPORTED_CONTRACT_TYPE`、`UNSUPPORTED_CONTRACT_STATUS`、`INVALID_CURRENCY_CONTEXT`、`INVALID_LISTING_INTERVAL`、`NOT_LISTED_AT_QUERY_INSTANT`、`SYMBOL_TIMELINE_CONFLICT`、`METADATA_CONFLICT`；
13. Constructor必须重算source/revision/query/result/failure identity，并重验证InstrumentDefinition、SymbolTimeline、listing interval、multiplier、active revision与source exact coverage。`dataclasses.replace`伪造hash、active symbol/status、Instrument ID、timeline、boundary、multiplier、source或failure code/message必须被拒绝；
14. Source fixture固定覆盖：BTCUSDT-like open-ended perpetual、finite-delisting revision、explicit same-lineage symbol change、missing-lineage old/new split、corrected onboard metadata only after`available_at`、known non-trading status、pre-listing、post-delisting及unsupported type/status/currency。Golden固定完整success/failure canonical dictionaries和hash；
15. Public values immutable、canonical、input-order independent且idempotent。Production module禁止callbacks、implementation objects、runtime addresses、Attempt IDs、wall-clock identity、generic Engine/Runner分支、fees/funding/margin/liquidation/account-mode或deployment authorization语义。

G10A已由immutable implementation commit `613c319b2dbba9962d4867dcfb3d1b19067d16cf`实现并通过冻结验收，状态为`PASSED`。

Primary-source contract：`docs/research/binance-usdm-instrument-metadata-primary-sources.md`。

Readiness baseline：

```text
G09H frozen acceptance command                                      79 passed
Full test suite                                                     977 passed
Workspace import boundary                                           PASS (72 files)
mypy                                                                  no issues (71 source files)
Primary LSP                                                          clean
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
G09H frozen acceptance command                                      79 passed
Full test suite                                                     977 passed
Workspace import boundary                                           PASS (72 files)
mypy 2.3.0                                                           no issues (72 source files)
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

PASSED validation：

```text
G10A frozen acceptance command                                      45 passed
Full test suite                                                    1001 passed
Workspace import boundary                                           PASS (74 files)
mypy 2.3.0                                                           no issues (74 source files)
Primary LSP + scoped pi-lens                                         no issues
uv lock --check                                                      PASS
Python                                                                3.13.5
```

## 78. G10B Binance USDⓈ-M Historical Order Rules Acceptance Card

```yaml
id: G10B
status: PASSED
depends_on:
  - G10A
  - WP-05G
owner_package: trading-kernel + trading-kernel profile adapter
public_interface:
  - backward-compatible crypto_quant_trading.OrderRuleSnapshot.market_quantity_lattice
  - backward-compatible crypto_quant_trading.MarketRuleEvaluator style-specific quantity lattice selection
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmOrderAdmissionMode
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmDeferredRuleKey
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmOrderRuleSourceRef
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmOrderRuleBand
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmOrderRuleBook
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmOrderRuleQuery
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmOrderRuleResolution
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmOrderRuleFailureCode
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmOrderRuleFailure
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmOrderRuleOutcome
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmOrderRuleModel
test_commands:
  contract: uv run pytest -q tests/profiles/binance_usdm/test_order_rules.py tests/kernel/market_rules/test_market_rule_style_lattices.py
  fixture: uv run pytest -q tests/profiles/binance_usdm/test_order_rules_golden.py
  boundary: uv run pytest -q tests/architecture/test_binance_usdm_profile_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  regression: uv run pytest -q tests/profiles/binance_usdm/test_instrument_metadata.py tests/kernel/market_rules/test_market_rule_evaluator.py tests/kernel/market_rules/test_market_rule_position_evidence.py tests/kernel/capabilities/test_order_capability_validator.py
  acceptance: uv run pytest -q tests/profiles/binance_usdm/test_order_rules.py tests/profiles/binance_usdm/test_order_rules_golden.py tests/kernel/market_rules/test_market_rule_style_lattices.py tests/architecture/test_binance_usdm_profile_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py tests/profiles/binance_usdm/test_instrument_metadata.py tests/kernel/market_rules/test_market_rule_evaluator.py tests/kernel/market_rules/test_market_rule_position_evidence.py tests/kernel/capabilities/test_order_capability_validator.py --junitxml=build/acceptance/g10b-pytest.xml
fixture_ids:
  - binance-usdm-historical-order-rule-source-v1
  - binance-usdm-historical-order-rules-v1
expected_artifacts:
  - docs/research/binance-usdm-order-rules-primary-sources.md
  - tests/fixtures/profiles/binance-usdm-historical-order-rule-source-v1.json
  - tests/fixtures/profiles/binance-usdm-historical-order-rules-v1.json
  - build/acceptance/g10b-pytest.xml
  - build/acceptance/g10b-import-boundary-report.json
failure_contracts:
  - missing-rule-bands
  - instrument-metadata-query-or-rule-book-mismatch
  - no-rule-evidence-visible-by-captured-at
  - missing-rule-interval-or-incomplete-declared-coverage
  - overlapping-rule-intervals-or-input-order-selection
  - missing-price-lot-market-lot-or-min-notional-filter
  - unknown-or-undeclared-provider-filter
  - noncanonical-negative-exponent-overflow-or-inexact-decimal
  - disabled-tick-step-offset-or-incompatible-filter-geometry
  - missing-limit-market-or-unknown-order-tif-capability
  - g10a-tradability-and-admission-mode-conflict
  - unresolved-provider-rule-is-omitted-or-marked-decision-grade
  - current-rule-fallback-rewrites-historical-or-working-order-identity
  - limit-and-market-quantity-lattices-are-collapsed
  - market-notional-uses-trade-bar-close-or-wrong-price-purpose
  - source-query-filesystem-network-wall-clock-runtime-or-account-leakage
allowed_grade: development
evidence:
  - readiness-contract-tests
  - official-source-note
  - static-source-and-golden-fixture-hashes
  - legacy-schema-and-hash-compatibility-golden
  - public-api-import-report
  - import-boundary-report
  - static-type-report
  - dependency-lock-report
passed_commit: 11072289a9dda708a185ae2edcbf5fcdf0c7bd55
artifact_hashes:
  tests/fixtures/profiles/binance-usdm-historical-order-rule-source-v1.json: sha256:d95ecf2c821e73433bf1929d9378aad2efbd57b6c421ef47db2ab7d1ea69376b
  tests/fixtures/profiles/binance-usdm-historical-order-rules-v1.json: sha256:dfdc28535e1a1388cb92318bfb725ebbe96027c674b0122be0c3bdd5e7db3911
  build/acceptance/g10b-pytest.xml: sha256:631818b35a930dd568985bd489ace86272367c8f1337220a00ce620d28afd122
  build/acceptance/g10b-import-boundary-report.json: sha256:1bb4275a40d165e1b6b1baf97c9f62bd3da3024ca852e0b304d6c47b19243b1c
```

### G10B Acceptance

冻结边界：

1. G10B是纯离线`crypto_quant_trading.profiles.binance_usdm.order_rules` Adapter，结构化实现既有`OrderRuleModel.resolve_order_rules()`；只消费caller-supplied immutable G10A Resolution、RuleBook、Session和time inputs。Production code不得创建provider client、发HTTP、解析JSON/file、读filesystem/database/wall clock或fallback到current `/fapi/v1/exchangeInfo`；G12拥有acquisition/parsing/retention；
2. `BinanceUsdmOrderRuleBand` exact保存`band_id`、Instrument ID、half-open`effective_from/effective_to_exclusive`、`available_at`、raw canonical decimal strings：`min_price/max_price/tick_size`、Limit `min_qty/max_qty/step_size`、Market `min_qty/max_qty/step_size`、`min_notional`，以及provider `order_types`、`time_in_forces`、Admission Mode、deferred rule keys和source key/hash；全部字段进入Band hash；
3. `BinanceUsdmOrderRuleBook` exact保存key/version、Instrument、finite`coverage_from/coverage_to_exclusive`与canonical-sorted Bands。Query绑定G10A Resolution、Session ID、`evaluated_at`、`captured_at`和RuleBook hash；G10A economic instant必须等于evaluated-at，G10A captured-at不得晚于Query captured-at，Instrument/settlement currency必须exact匹配；
4. Resolver只使用`available_at <= captured_at`的Band。Failure precedence exact为：`MISSING_RULE_BANDS`、`INSTRUMENT_METADATA_MISMATCH`、`RULE_NOT_AVAILABLE`、`MISSING_RULE_INTERVAL`、`OVERLAPPING_RULE_INTERVALS`、`MISSING_REQUIRED_FILTER`、`UNSUPPORTED_FILTER`、`INVALID_DECIMAL_FIELD`、`INVALID_FILTER_GEOMETRY`、`UNSUPPORTED_ORDER_CAPABILITY`、`ADMISSION_STATUS_CONFLICT`、`METADATA_CONFLICT`；多缺陷只返回第一项；
5. Visible Bands必须从RuleBook coverage start到end exact形成连续half-open coverage；首尾缺失、内部gap、overlap、duplicate Band ID、cross-Instrument Band或按tuple顺序选winner均fail closed。Query instant必须命中唯一Band；不得nearest/current fallback；
6. Provider decimal grammar exact限定non-negative ordinary decimal string，不允许sign、exponent、NaN/Infinity、leading plus、whitespace、Unicode alternative或超过18 fractional places。Mapping只用string/integer arithmetic；raw string（含provider trailing zeros）保留在Band identity，behavior使用smallest exact common Scale；禁止float、ambient Decimal context、`pricePrecision`与`quantityPrecision`；
7. `PRICE_FILTER` tick必须positive。Zero `minPrice`/`maxPrice`分别映射disabled bound；nonzero bounds必须positive且lower<=upper。Generic evaluator使用zero-origin tick，因此enabled min必须exact位于tick lattice；需要unrepresented offset、zero tick、scale overflow或bound incompatibility返回`INVALID_FILTER_GEOMETRY`，不得round；
8. `LOT_SIZE`和`MARKET_LOT_SIZE`各自要求positive min/max/step、min<=max且min exact位于step lattice。两者映射独立Limit/Market `QuantityLattice`与max cap，不得copy、fallback或取交集。两条lattice必须同Instrument、同exact atomic Scale、同quote-currency MIN_NOTIONAL authority；raw filter差异进入hash；
9. Generic `OrderRuleSnapshot`在现有字段后增加optional `market_quantity_lattice: QuantityLattice | None = None`。None时现有无cap schema-v1与有cap schema-v2 canonical bytes/config/snapshot hashes完全不变且payload不出现字段；non-None时schema-v3并exact保存该lattice；
10. Generic Evaluator对`LIMIT`/`STOP_LIMIT`使用primary lattice及limit cap，对`MARKET`/`STOP`使用market lattice（缺失时保持legacy primary fallback）及market cap。Quantity Scale/Step/Minimum/Maximum、position-exception lattice hash、notional currency/scale和calculated notional均绑定selected lattice；Market cap按market step验证，Limit cap按primary step验证；
11. `MIN_NOTIONAL`必须positive，exact转换到`price_scale + quantity_scale`（总Scale<=18）的quote-currency Money；Limit/Stop-Limit使用对应constraint price evidence；Market/Stop要求caller-supplied `NotionalPriceBasis.SUPPLIED_REFERENCE`且其Price Purpose由G10D/G10G证明为historical MARK_PRICE。G10B不查询Mark，不允许Trade/Bar Close/Valuation/Liquidation/current price替代；
12. Source `order_types`和`time_in_forces` canonical-sort并进入Band identity。v1要求source至少声明`LIMIT`和`MARKET`；Limit generic capability exact为`PriceConstraintShape.LIMIT`及source与`GTC/IOC/FOK/GTX`的intersection且不得为空；Market capability exact为`PriceConstraintShape.NONE`与`TimeInForce.IOC`，表达immediate non-resting semantic而非要求wire发送TIF。Unknown provider values structured reject；STOP/TAKE_PROFIT/TRAILING、GTD/RPI、close-all、price-match与STP不是静默capability；
13. `BinanceUsdmDeferredRuleKey` exact冻结：`PERCENT_PRICE`、`MAX_NUM_ORDERS`、`MAX_NUM_ALGO_ORDERS`、`MARKET_TAKE_BOUND`、`TRIGGER_PROTECT`、`ADVANCED_ORDER_CAPABILITIES`。Normalized source必须声明所有存在但本Gate未解析的known rules；unknown key返回`UNSUPPORTED_FILTER`；Resolution exact保留active及full visible deferred set；
14. Resolution只有在deferred set为空时可`decision_grade_eligible=true`。任何deferred key被遗漏、结果伪造为空或非空仍标decision-grade必须constructor拒绝。G10D拥有PERCENT_PRICE/trigger Mark evidence，G10F拥有account working-order counts与mode，G10G拥有最终coverage intersection；G10B本身只允许development；
15. `BinanceUsdmOrderAdmissionMode` exact为`NORMAL`、`REDUCE_ONLY`、`CLOSED`。NORMAL Snapshot允许BUY/SELL与AUTO/OPEN/CLOSE且不要求reduce-only；REDUCE_ONLY只允许CLOSE并`reduce_only_required=true`；CLOSED使用`MarketSessionState.SUSPENDED`且不产生普通approval。G10A active metadata非tradable时active Band必须CLOSED，否则`ADMISSION_STATUS_CONFLICT`；TRADING可由explicit source进入REDUCE_ONLY/CLOSED；
16. Provider支持`reduceOnly`不等于任意Account可发送该wire field。Capability Set记录symbol-level support；Hedge/One-way、positionSide、closePosition、existing-order conflict与account restriction由G10F/intersection拥有，G10B不得授权或查询account；
17. Resolution exact包含Component Ref `ProfileComponentRef(ORDER_RULE_MODEL,"crypto.binance_usdm.order-rules.v1")`、visible Bands、active Band、full generic OrderRuleTimeline、active Snapshot、Limit/Market lattices、price/quantity scales、active OrderCapabilitySet、deferred keys、decision-grade flag和source coverage。相同logical inputs任意tuple顺序得到相同canonical outcome；
18. 每个Band形成exact matching `OrderRuleInterval`，interval identity/hash与Band/source绑定。Tick change只影响boundary后新admission；transition前已接受Order保留原MarketRuleDecision、resolved interval与rule hash，Generic Engine/Runner不得按current timeline重新解释Working Order。Official temporary suspension只有显式CLOSED Band/G10A status evidence时生效，不能从tick change猜测；
19. Constructor必须重算Band/RuleBook/Query/Resolution/Failure、Component、generic Snapshot/Interval/Timeline/Capability identities，并重验证active Band、style lattices、scale/cap、admission mode、deferred set和source exact coverage。`dataclasses.replace`伪造任一authority必须拒绝；
20. Static source/golden至少覆盖：distinct Limit/Market max与step、exact trailing-zero decimal normalization、MIN_NOTIONAL、tick transition before/at/after、one-minute CLOSED suspension、TRADING+REDUCE_ONLY delist window、captured-at late Band、coverage gap/overlap、missing filter、invalid decimal/offset geometry、unknown order/TIF/deferred key、G10A mismatch、source conflict、forgery、input-order parity与all hashes；
21. Generic compatibility golden固定：(a) no market lattice/no caps schema-v1 bytes/hash；(b) no market lattice/with caps schema-v2 bytes/hash；(c) market lattice schema-v3；(d) legacy Evaluator decisions unchanged；(e) style-specific killer证明same Quantity在Limit lattice通过但Market lattice因step/min/max拒绝，及反向case；
22. Concrete purity scanner allowlist只允许stdlib、`crypto_quant_domain`、generic `market_rules|capabilities|ports|sizing`和same-package G10A types；拒绝filesystem/network/provider/process/database/cloud、dynamic import、MarketBundle、Runtime和wall clock。Generic Kernel不得import/branch on Binance；Production Runtime不得importconcrete profile；不新增dependency；
23. G10B不拥有PERCENT_PRICE final decision、Mark streams、open/algo order count、Account/Hedge mode、GTD/RPI/trailing/close-all/STP/price-match wire semantics、marketTakeBound Fill、fees、funding、margin、liquidation、Bundle Builder、Profile composition、live、deployment或parity。任何后续Gate必须消费G10B canonical evidence，不能重抓current rules补洞。

G10B已由immutable implementation commit `11072289a9dda708a185ae2edcbf5fcdf0c7bd55`实现并通过冻结验收，状态为`PASSED`。

Primary-source contract：`docs/research/binance-usdm-order-rules-primary-sources.md`。

Readiness baseline：

```text
G10A frozen acceptance command                                      45 passed
Full test suite                                                    1001 passed
Workspace import boundary                                           PASS (74 files)
mypy 2.3.0                                                           no issues (74 source files)
Primary LSP + scoped pi-lens                                         no issues
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
G10A frozen acceptance command                                      45 passed
Full test suite                                                    1001 passed
Workspace import boundary                                           PASS (74 files)
mypy 2.3.0                                                           no issues (74 source files)
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

PASSED validation：

```text
G10B frozen acceptance command                                      80 passed
Full test suite                                                    1027 passed
Workspace import boundary                                           PASS (75 files)
mypy 2.3.0                                                           no issues (75 source files)
Primary LSP + scoped pi-lens                                         no errors
uv lock --check                                                      PASS
Python                                                                3.13.5
```

## 79. G10C Binance USDⓈ-M Historical Margin and Leverage Tiers Acceptance Card

```yaml
id: G10C
status: PASSED
depends_on:
  - G10A
  - G09E
owner_package: trading-kernel margin requirement + trading-kernel profile adapter
public_interface:
  - backward-compatible crypto_quant_trading.LinearMarginTierBoundaryConvention
  - backward-compatible crypto_quant_trading.LinearMarginRuleInterval.tier_boundary_convention
  - backward-compatible crypto_quant_trading.LinearInstrumentMarginFailureCode.NOTIONAL_OUTSIDE_TIER_COVERAGE
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmMarginTierScope
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmMarginTierSourceRef
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmMarginTierBracket
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmMarginTierBand
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmMarginTierRuleBook
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmMarginTierQuery
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmMarginTierResolution
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmMarginTierFailureCode
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmMarginTierFailure
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmMarginTierOutcome
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmMarginTierModel
test_commands:
  contract: uv run pytest -q tests/profiles/binance_usdm/test_margin_tiers.py tests/kernel/derivatives/test_linear_margin_tier_boundaries.py
  fixture: uv run pytest -q tests/profiles/binance_usdm/test_margin_tiers_golden.py
  boundary: uv run pytest -q tests/architecture/test_binance_usdm_profile_boundary.py tests/architecture/test_derivative_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  regression: uv run pytest -q tests/profiles/binance_usdm/test_instrument_metadata.py tests/kernel/derivatives/test_linear_margin_requirement.py tests/kernel/derivatives/test_linear_margin_requirement_golden.py tests/kernel/derivatives/test_linear_account_margin_projection.py tests/runtime/liquidation/test_conservative_linear_liquidation_audit.py
  acceptance: uv run pytest -q tests/profiles/binance_usdm/test_margin_tiers.py tests/profiles/binance_usdm/test_margin_tiers_golden.py tests/kernel/derivatives/test_linear_margin_tier_boundaries.py tests/architecture/test_binance_usdm_profile_boundary.py tests/architecture/test_derivative_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py tests/profiles/binance_usdm/test_instrument_metadata.py tests/kernel/derivatives/test_linear_margin_requirement.py tests/kernel/derivatives/test_linear_margin_requirement_golden.py tests/kernel/derivatives/test_linear_account_margin_projection.py tests/runtime/liquidation/test_conservative_linear_liquidation_audit.py --junitxml=build/acceptance/g10c-pytest.xml
fixture_ids:
  - binance-usdm-contract-info-margin-tier-source-v1
  - binance-usdm-historical-margin-tiers-v1
expected_artifacts:
  - docs/research/binance-usdm-margin-tiers-primary-sources.md
  - tests/fixtures/profiles/binance-usdm-contract-info-margin-tier-source-v1.json
  - tests/fixtures/profiles/binance-usdm-historical-margin-tiers-v1.json
  - build/acceptance/g10c-pytest.xml
  - build/acceptance/g10c-import-boundary-report.json
failure_contracts:
  - missing-margin-tier-bands
  - instrument-metadata-query-or-tier-rule-book-mismatch
  - no-tier-evidence-visible-by-captured-at
  - missing-tier-interval-or-incomplete-declared-coverage
  - overlapping-tier-intervals-or-input-order-selection
  - account-adjusted-tier-or-notional-coef-is-accepted
  - noncanonical-negative-exponent-overflow-or-inexact-decimal
  - bracket-id-floor-cap-leverage-rate-or-deduction-geometry-is-guessed
  - shared-cap-equality-is-assigned-to-the-next-binance-tier
  - finite-terminal-cap-is-rewritten-as-unbounded
  - notional-above-terminal-cap-asserts-clamps-or-falls-back
  - provider-mi-is-enforced-as-selected-account-minimum-leverage
  - provider-ma-or-initial-leverage-is-used-as-selected-account-leverage
  - current-authenticated-bracket-backfills-history
  - source-query-filesystem-network-wall-clock-runtime-or-account-leakage
allowed_grade: development
evidence:
  - readiness-contract-tests
  - official-source-note
  - static-source-and-golden-fixture-hashes
  - legacy-g09e-schema-bytes-hash-and-behavior-compatibility-golden
  - upper-inclusive-boundary-and-finite-terminal-cap-evidence
  - public-api-import-report
  - import-boundary-report
  - static-type-report
  - dependency-lock-report
passed_commit: 50fa838f901385498ce18d65a897d4eb1dc31337
artifact_hashes:
  tests/fixtures/profiles/binance-usdm-contract-info-margin-tier-source-v1.json: sha256:b4c6d311d7784a6d09f8f6801aa94a61cbf80476d5b770d8612bd32358c7aee2
  tests/fixtures/profiles/binance-usdm-historical-margin-tiers-v1.json: sha256:04adb8c46c87f82d4a2a988570d66baa79d3063c74fd3c5e51e7ec6f95f625b0
  build/acceptance/g10c-pytest.xml: sha256:dc53052029659e77be00db09137e9b26cad865cf528074bb46440a08bf3ab78a
  build/acceptance/g10c-import-boundary-report.json: sha256:0d9f6c984f231e0517b02fe1980148d5acbedb8d1142ff38b39db175d2dcc4d4
```

### G10C Acceptance

冻结边界：

1. G10C是纯离线`crypto_quant_trading.profiles.binance_usdm.margin_tiers` Adapter，并拥有最小backward-compatible G09E generic extension。Production code只消费caller-supplied immutable G10A Resolution、Margin Tier RuleBook与time inputs；不得创建provider client、发HTTP、解析JSON/file、读filesystem/database/wall clock、调用authenticated current leverage-bracket endpoint或读取Account/Position/Wallet；G12拥有acquisition/parsing/retention，G10F拥有account leverage/mode；
2. `BinanceUsdmMarginTierBracket` exact保存raw canonical strings `bracket_id`/`bs`、`notional_floor`/`bnf`、`notional_cap`/`bnc`、`maintenance_margin_rate`/`mmr`、`maintenance_margin_deduction`/`cf`、`minimum_leverage_range`/`mi`与`maximum_leverage`/`ma`。Raw provider trailing zeros及全部字段进入Bracket hash；不得只保存mapped generic值；
3. `BinanceUsdmMarginTierBand` exact保存Band ID、Instrument ID、half-open`effective_from/effective_to_exclusive`、完整`available_at: SimulationInstant`、`BinanceUsdmMarginTierScope`、optional raw `notional_coef`、caller-ordered Bracket tuple及source key/hash。`BinanceUsdmMarginTierScope` exact为`DEFAULT_SYMBOL`和`ACCOUNT_ADJUSTED`；v1只有Contract Info `DEFAULT_SYMBOL`可成功解析；
4. `BinanceUsdmMarginTierRuleBook` exact保存key/version、stable G10A Instrument、settlement Currency、finite`coverage_from/coverage_to_exclusive`与canonical-sorted Bands。Query绑定G10A Resolution、economic `evaluated_at`、knowledge `captured_at`和RuleBook hash；G10A effective-at必须等于Query evaluated-at，G10A captured-at不得晚于Query captured-at，Instrument/settlement Currency必须exact匹配；
5. Resolver只使用`available_at <= captured_at`的Band。Provider failure precedence exact为：`MISSING_TIER_BANDS`、`INSTRUMENT_METADATA_MISMATCH`、`TIER_NOT_AVAILABLE`、`MISSING_TIER_INTERVAL`、`OVERLAPPING_TIER_INTERVALS`、`ACCOUNT_ADJUSTED_TIER_UNSUPPORTED`、`INVALID_DECIMAL_FIELD`、`INVALID_BRACKET_GEOMETRY`、`UNSUPPORTED_MARGIN_SEMANTICS`、`METADATA_CONFLICT`；多缺陷只返回第一项；
6. Visible Bands必须从RuleBook coverage start到end exact形成连续half-open time coverage；首尾缺失、内部gap、overlap、duplicate Band ID、cross-Instrument Band或按tuple顺序选winner均fail closed。Query instant必须命中唯一Band；不得nearest/current/latest fallback；
7. Provider decimal grammar exact限定non-negative ordinary decimal string，不允许sign、exponent、NaN/Infinity、leading plus、whitespace、Unicode alternative或超过18 fractional places。Mapping只用string/integer arithmetic；raw string保留identity，behavior使用smallest exact Scale；禁止float、ambient Decimal context、`pricePrecision`与`quantityPrecision`；
8. Bracket ID、`mi`与`ma`必须是positive integral exact values；Bracket ID按数值strict递增且第一项为1；`0 <= floor < cap`，第一floor exact为zero，相邻`previous.cap == next.floor`，`mi <= ma`，maximum leverage不得随notional上升而增加，rate/deduction nonnegative，Currency/Scale/Basis必须一致。Order、gap、overlap、duplicate、zero/negative cap、fractional leverage或unsupported geometry返回`INVALID_BRACKET_GEOMETRY`，不得sort后掩盖source defect；
9. Generic增加`LinearMarginTierBoundaryConvention` exact值`LOWER_INCLUSIVE_UPPER_EXCLUSIVE`与`LOWER_EXCLUSIVE_UPPER_INCLUSIVE`。`LinearMarginRuleInterval.tier_boundary_convention`的existing/default convention不出现在legacy schema-v1 canonical payload，既有Interval/RuleBook/Request/Result bytes、hash和lower-inclusive选择完全不变；non-default Binance convention使用schema-v2并进入identity；
10. Binance notional Tier exact使用zero-degenerate first Tier及positive-notional lower-exclusive/upper-inclusive选择：notional zero选择第一Tier；shared cap equality选择前一Tier；above cap选择后一Tier；不得加epsilon、移动floor/cap、按Money Scale加一或提前quantize notional；
11. Binance final `bnc` exact映射finite terminal `notional_cap`，不得改成`None`。Generic G09E允许valid finite terminal coverage；exact notional高于terminal cap返回新增`NOTIONAL_OUTSIDE_TIER_COVERAGE`，其precedence在Margin Mark验证与exact notional计算后、`LEVERAGE_EXCEEDS_TIER_MAXIMUM`前。No matching Tier不得AssertionError、clamp、选择final Tier或current rule fallback；
12. Mapping exact为：`bnf`→settlement-currency `notional_floor`、`bnc`→finite `notional_cap`、`ma`→`maximum_leverage` basis `notional_per_initial_margin`、`mmr`→`maintenance_margin_rate` basis `maintenance_margin_fraction_of_notional`、`cf`→nonnegative `maintenance_margin_deduction`。Official formula `notional × rate - Maintenance Amount`保持G09E；source `cf`原值优先，不从rounded rates重算；
13. `mi`只保留为provider显示的leverage-range evidence和source identity，不映射minimum selected leverage，不拒绝低于`mi`的caller account leverage。`ma`/authenticated `initialLeverage`只表示Tier maximum，也不得创建`LinearMarginLeverageEvidence`；selected account leverage及其effective/available source由G10F拥有；
14. `ACCOUNT_ADJUSTED` Band、任何non-null `notional_coef`或authenticated USER_DATA bracket source返回`ACCOUNT_ADJUSTED_TIER_UNSUPPORTED`。G10C v1不解释、乘算、归一化或跨Account共享`notionalCoef`；即使数值为1也不能把current account response冒充public historical Contract Info revision；
15. Current `/fapi/v1/leverageBracket`或Portfolio Margin UM bracket response不提供G10C historical authority。Contract Info archived event/Band必须携带explicit effective/available/source lineage；status-only event无`bks`不能创建Tier revision；announcement表可验证boundary/change但缺少`cf`时不能单独形成v1 normalized Band；
16. Resolution exact包含Component Ref `ProfileComponentRef(MARGIN_MODEL,"crypto.binance_usdm.margin-tiers.v1")`、visible Bands、active Band、完整generic `LinearMarginRuleBook`、active generic Interval/Tiers、boundary convention、finite terminal cap、source coverage与`decision_grade_eligible=false`。相同logical inputs任意tuple顺序得到相同canonical outcome；Adapter不调用`LinearInstrumentMarginModel.evaluate_margin()`；
17. Generic Component仍为provider-neutral且不识别Binance。Existing G09E component digest和legacy interval payload保持不变；non-default boundary convention与finite-cap selection只由generic fields驱动。Generic Margin Model、G09F、G09G、Engine、Runner不得import/branch on Binance profile types；
18. Constructor必须重算Bracket/Band/RuleBook/Query/Resolution/Failure、generic Interval/Tier/RuleBook identities，并重验证active Band、visible coverage、boundary convention、finite cap、mapped rate/leverage/deduction、raw source exact coverage与decision-grade flag。`dataclasses.replace`伪造任一authority必须拒绝；
19. Static source/golden至少覆盖：two historical Contract Info updates、before/at/after update、shared cap below/at/above、zero notional、finite final cap equality/overflow、`cf` deduction、`mi < selected leverage < ma`及selected leverage below `mi`仍合法、selected leverage above `ma`失败、late-only Band、coverage gap/overlap、Bracket order/gap/overlap、malformed decimal/fractional leverage、account-adjusted/non-null notionalCoef、status-only source、G10A mismatch、source conflict、forgery、input-order parity与all hashes；
20. Generic compatibility golden固定：(a) legacy lower-inclusive/unbounded schema-v1 Interval/RuleBook/Request/Result bytes与hash；(b) existing exact shared boundary仍选后一Tier；(c) Binance schema-v2 shared boundary选前一Tier；(d) finite final cap equality成功且overflow structured fail；(e)既有G09E、G09F、G09G synthetic outputs不变；
21. Concrete purity scanner allowlist只允许stdlib、`crypto_quant_domain`、generic `margin|ports`和same-package G10A types；拒绝filesystem/network/provider client/process/database/cloud、dynamic import、MarketBundle、Runtime、account module和wall clock。Generic `margin.py`不得import concrete profile；Production Runtime不得import concrete profile；不新增dependency；
22. G10C不拥有selected account leverage、cross/isolated/multi-asset/portfolio margin、Wallet/Equity/Available Margin、working-order margin、Mark stream、fee、funding、Liquidation execution、Bundle Builder、Profile composition、live、deployment或parity。G12完成initial state与全update archive coverage proof前，Resolution固定development-grade且`decision_grade_eligible=false`。

G10C已由immutable implementation commit `50fa838f901385498ce18d65a897d4eb1dc31337`实现并通过冻结验收，状态为`PASSED`。

Primary-source contract：`docs/research/binance-usdm-margin-tiers-primary-sources.md`。

Readiness baseline：

```text
G10B frozen acceptance command                                      80 passed
Full test suite                                                    1027 passed
Workspace import boundary                                           PASS (75 files)
mypy 2.3.0                                                           no issues (75 source files)
Primary LSP + scoped pi-lens                                         no blocking errors
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
G10B frozen acceptance command                                      80 passed
Full test suite                                                    1027 passed
Workspace import boundary                                           PASS (75 files)
mypy 2.3.0                                                           no issues (75 source files)
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

PASSED validation：

```text
G10C frozen acceptance command                                     113 passed
Full test suite                                                    1052 passed
Workspace import boundary                                           PASS (76 files)
mypy 2.3.0                                                           no issues (76 source files)
Primary LSP                                                          no diagnostics
Scoped pi-lens                                                       no blocking errors; duplicate-code warnings only
uv lock --check                                                      PASS
Python                                                                3.13.5
```

## 80. G10D Binance USDⓈ-M Historical Price-Purpose Streams Acceptance Card

```yaml
id: G10D
status: PASSED
depends_on:
  - G10A
  - WP-03C
owner_package: trading-kernel profiles/binance_usdm
public_interface:
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmPriceSourceKind
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmPriceSourceRef
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmAggregateTradePrice
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmMarkPriceKline
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmPriceStreamCoverage
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmHistoricalPriceBook
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmPricePurposeQuery
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmLiquidationMarkBar
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmPricePurposeResolution
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmPriceStreamFailureCode
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmPriceStreamFailure
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmPriceStreamOutcome
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmPriceStreamModel
test_commands:
  contract: uv run pytest -q tests/profiles/binance_usdm/test_price_streams.py
  fixture: uv run pytest -q tests/profiles/binance_usdm/test_price_streams_golden.py
  boundary: uv run pytest -q tests/architecture/test_binance_usdm_profile_boundary.py tests/architecture/test_derivative_boundary.py tests/architecture/test_liquidation_audit_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  regression: uv run pytest -q tests/kernel/marks/test_mark_resolver.py tests/kernel/marks/test_mark_resolver_golden.py tests/runtime/execution/test_next_eligible_bar_open.py tests/runtime/liquidation/test_conservative_linear_liquidation_audit.py tests/profiles/binance_usdm/test_instrument_metadata.py tests/profiles/binance_usdm/test_order_rules.py
  acceptance: uv run pytest -q tests/profiles/binance_usdm/test_price_streams.py tests/profiles/binance_usdm/test_price_streams_golden.py tests/kernel/marks/test_mark_resolver.py tests/kernel/marks/test_mark_resolver_golden.py tests/runtime/execution/test_next_eligible_bar_open.py tests/runtime/liquidation/test_conservative_linear_liquidation_audit.py tests/architecture/test_binance_usdm_profile_boundary.py tests/architecture/test_derivative_boundary.py tests/architecture/test_liquidation_audit_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py tests/profiles/binance_usdm/test_instrument_metadata.py tests/profiles/binance_usdm/test_order_rules.py --junitxml=build/acceptance/g10d-pytest.xml
fixture_ids:
  - binance-usdm-historical-price-source-v1
  - binance-usdm-price-purpose-streams-v1
expected_artifacts:
  - docs/research/binance-usdm-price-purpose-streams-primary-sources.md
  - tests/fixtures/profiles/binance-usdm-historical-price-source-v1.json
  - tests/fixtures/profiles/binance-usdm-price-purpose-streams-v1.json
  - build/acceptance/g10d-pytest.xml
  - build/acceptance/g10d-import-boundary-report.json
failure_contracts:
  - missing-price-source-records
  - instrument-metadata-query-or-price-book-mismatch
  - unsupported-settlement-or-g10e-owned-funding-purpose
  - no-price-evidence-visible-by-captured-at
  - missing-or-overlapping-purpose-coverage
  - cross-instrument-duplicate-or-conflicting-source-event
  - malformed-noncanonical-overflow-or-inexact-decimal
  - aggregate-trade-or-mark-bar-timing-is-causal-invalid
  - same-utc-phase-only-late-availability-is-erased
  - contract-kline-open-is-exposed-at-bucket-start
  - trade-contract-close-index-moving-average-or-estimated-settlement-substitutes-mark-purpose
  - liquidation-point-forward-fill-substitutes-missing-ohlc
  - generic-mark-resolution-failure-is-hidden-or-reinterpreted
  - current-api-current-archive-or-nearest-row-backfills-history
  - purpose-source-mapping-change-does-not-change-model-digest
  - source-query-filesystem-network-wall-clock-runtime-or-engine-leakage
allowed_grade: development
evidence:
  - readiness-contract-tests
  - official-source-note
  - static-source-and-golden-fixture-hashes
  - purpose-specific-mark-resolver-and-liquidation-coverage-evidence
  - execution-reference-no-lookahead-evidence
  - public-api-import-report
  - import-boundary-report
  - static-type-report
  - dependency-lock-report
passed_commit: 790469d80ddcf3797f03c96c975b77d75a3d49a5
artifact_hashes:
  tests/fixtures/profiles/binance-usdm-historical-price-source-v1.json: sha256:5bd588c594fd159d74502ba9529bb399dc3ea24aa2a058ef3361560fbb1e0c50
  tests/fixtures/profiles/binance-usdm-price-purpose-streams-v1.json: sha256:4e1b5b1e778010868a63d12169e6704878ac7ae0b32dcc38e9ad53663462f3a1
  build/acceptance/g10d-pytest.xml: sha256:702190b6bc6d5bd0f28c11a56a0185ff2c306d15a3ebbba4f25d750ebea527c6
  build/acceptance/g10d-import-boundary-report.json: sha256:d09df94ee77151437c86394284c3a94b920f3043159f0ab579dee0ef51a2bb17
```

### G10D Acceptance

冻结边界：

1. G10D是纯离线`crypto_quant_trading.profiles.binance_usdm.price_streams` Adapter。Production code只消费caller-supplied immutable G10A Resolution、finite Historical Price Book、Query和time inputs；不得创建provider client、发HTTP/WebSocket、解析JSON/CSV/ZIP、读filesystem/database/wall clock或fallback到current REST/WebSocket/public-data directory；G12拥有acquisition/parsing/checksum/retention与complete gap proof；
2. `BinanceUsdmPriceSourceKind` exact只接受`AGGREGATE_TRADE`与`MARK_PRICE_KLINE`。Source Ref exact保存source key、SHA-256 content hash、revision ID、optional superseded revision、archive path/key和captured provenance；不得把book ticker、ordinary contract kline、index-price kline、premium-index kline、current premiumIndex response或Funding History伪装成accepted source kind；
3. `BinanceUsdmAggregateTradePrice` exact保存stable Instrument、aggregate trade ID、raw canonical price/quantity、first/last trade IDs、provider trade time、caller-supplied available-at、buyer-maker flag、source event/revision lineage与Source Ref。Aggregate IDs与trade-ID range必须nonnegative、first<=last、natural event ID在同visible revision set唯一；
4. `BinanceUsdmMarkPriceKline` exact保存stable Instrument、interval key、raw open-time/close-time毫秒、raw canonical OHLC strings、caller-supplied exact `closed_at: SimulationInstant`、`available_at: SimulationInstant`、closed-final flag、source event/revision lineage与Source Ref。只接受closed-final row；open<=high、low<=close/open<=high、low<=high及positive prices exact验证；
5. Provider Mark Kline interval exact为`[open_time, close_time + 1ms)`；`closed_at.instant`必须等于end-exclusive且`available_at >= closed_at`。Aggregate trade `available_at.instant >= trade_time`。任何future availability、close-before-end、non-final row或时钟字段冲突返回`INVALID_SOURCE_TIMING`，不得修正、round或取max；
6. `BinanceUsdmPriceStreamCoverage`按stable Instrument与一个exact PricePurpose保存finite half-open economic coverage、accepted Source Kind、stream key/version和source lineage。Historical Price Book必须exact-cover请求支持的purpose streams且canonical-sort；首尾缺失、内部gap、overlap、duplicate purpose-band ID、cross-Instrument或按tuple order选winner均fail closed；
7. Fixed mapping exact为：aggregate-trade `price@trade_time`→`EXECUTION_REFERENCE`；closed Mark Kline close→独立`VALUATION` observation；同一close→独立`MARGIN` observation；同一close→独立`LIQUIDATION` observation，且low/high→`BinanceUsdmLiquidationMarkBar`。每个output具有purpose-specific stream ID；同一raw source row可授权多个显式mapping，但不能生成一个无Purpose共享Mark；
8. Contract kline open不得在bucket start生成Execution Reference。G10D v1不用ordinary kline或book ticker替代aggregate trade，也不把aggregate trade声明为Fill、bar-open、best bid/ask或order-book execution。G10G若组合execution行为必须另外消费source event/availability evidence；
9. Mark Price Stream/REST字段`p`、`ap`、`i`、`P`、`r`、`T`保持不同authority。Accepted v1 Mark Kline只代表historical mark-price OHLC；index price、moving-average mark、estimated settlement price、funding rate/time或ordinary trade/contract close不得映射为Valuation/Margin/Liquidation Mark；
10. Query exact绑定G10A Resolution、Historical Price Book hash、PricePurpose、economic `requested_at: UtcInstant`、knowledge `captured_at: SimulationInstant`、point-purpose StaleMarkPolicy及仅LIQUIDATION允许的optional finite interval。G10A query effective-at必须exact等于requested-at，G10A listing interval必须覆盖requested-at及optional liquidation interval，G10A captured-at不得晚于Query captured-at.instant，Instrument/quote-settlement Currency必须exact匹配；
11. Visible source只允许`available_at <= captured_at`。Point observations保留provider observed-at与caller availability UTC；Adapter把canonical visible tuple交给既有provider-neutral `MarkResolver`，不复制或修改其instrument/purpose/availability/ambiguity/forward-fill/max-age precedence；generic failure保存为nested authority并映射固定provider failure；
12. 若source availability比economic fact晚但只由same UTC nanosecond的`SimulationInstant.phase`或`source_sequence`表达，current `MarkObservation.available_at: UtcInstant`无法无损表示。G10D必须返回`UNREPRESENTABLE_AVAILABILITY_ORDER`，不得丢弃phase/sequence后产生age zero或提前可见Mark；
13. Liquidation query要求exact finite interval并返回连续closed Mark Bars；每个Bar保存PricePurpose.LIQUIDATION、low/high、closed/available SimulationInstant、stream/event/revision/source identity。Bar gap、overlap、extra/cross-Instrument、future available或非exact interval coverage fail closed；point StaleMarkPolicy/forward-fill不能补Liquidation OHLC；
14. `PricePurpose.SETTLEMENT`在G10D v1返回`UNSUPPORTED_PRICE_PURPOSE`。Mark Price字段`P`只被官方定义为estimated settlement price且仅最后一小时有用；index-price kline、mark close、trade price、deliveryDate或delist time均不能创建final Settlement Mark；
15. `PricePurpose.FUNDING`在G10D返回`PRICE_PURPOSE_OWNED_BY_G10E`。Funding Rate History的associated mark、publication/finality、Funding Slot ID和target settlement UTC由G10E冻结；G10D不得从nearby Mark Kline或ordinary Mark update合成Funding Mark；
16. Provider failure precedence exact为：`INSTRUMENT_METADATA_MISMATCH`、`UNSUPPORTED_PRICE_PURPOSE`、`PRICE_PURPOSE_OWNED_BY_G10E`、`MISSING_SOURCE_RECORDS`、`SOURCE_NOT_AVAILABLE`、`MISSING_PURPOSE_COVERAGE`、`OVERLAPPING_PURPOSE_COVERAGE`、`INVALID_DECIMAL_FIELD`、`INVALID_SOURCE_TIMING`、`UNREPRESENTABLE_AVAILABILITY_ORDER`、`SOURCE_IDENTITY_CONFLICT`、`MARK_RESOLUTION_FAILED`、`METADATA_CONFLICT`；多缺陷只返回第一项；
17. Decimal grammar exact限定positive ordinary decimal string，不允许sign、exponent、NaN/Infinity、leading plus、whitespace、Unicode alternative、zero/negative value或超过18 fractional places。Mapping只用string/integer arithmetic；raw trailing zeros保留source identity，point与OHLC使用smallest exact required common Scale；禁止float、ambient Decimal context及`pricePrecision`；
18. Resolution exact包含model key/version/digest、Query/Book identity、visible source records、normalized purpose observations、optional resolved Mark、Liquidation Bars、source coverage、limitations与`decision_grade_eligible=false`。Model digest exact包含schema、fixed purpose-source mapping、unsupported Settlement、G10E-owned Funding、timing/decimal rules与limitations；mapping变化必须改变digest，并由G10G纳入final Profile digest；
19. G10D不新增generic `ProfilePortType`，避免让既有Market Profile/Runner exact-cover一个尚未成为runtime behavioral port的source-normalization component。G10G以G10D model digest和resolution hashes组合Profile identity；Generic Kernel/Runtime仍不识别Binance concrete type；
20. Constructor必须重算Source Ref、source rows、Coverage、Book、Query、Resolution、Failure、Outcome、MarkObservation和Liquidation Bar identities，并重验证visible set、purpose separation、mapped Scale/time/source exact coverage及decision-grade flag。`dataclasses.replace`伪造任一authority必须拒绝；
21. 相同logical inputs任意tuple顺序产生相同canonical outcome。Natural event/revision conflict、同observed-at多visible point导致generic ambiguity、same event ID changed bytes、supersedes chain断裂或source hash冲突不得按输入顺序选winner；
22. Static source/golden至少覆盖：two aggregate trades、two closed 1m Mark Bars、all accepted purpose mappings、same Mark row的three separate purpose identities、before/at/after available-at、stale/no-forward-fill、same-time ambiguity、liquidation exact/gap/overlap、contract-kline-open lookahead killer、settlement/funding/index/estimated-settlement/book-ticker rejection、malformed decimal/timing、cross-Instrument/source conflict、forgery、input-order parity与all hashes；
23. Generic compatibility golden固定既有`MarkObservation`、`StaleMarkPolicy`、`ResolvedMark`、`MarkResolver`与G09G `LinearLiquidationMarkBarEvidence` schema/bytes/hash/behavior不变。G10D只生成accepted generic/provider evidence，不修改generic classes或failure precedence；
24. Concrete purity scanner allowlist只允许stdlib、`crypto_quant_domain`、generic `marks`和same-package G10A types；拒绝filesystem/network/provider/process/database/cloud、dynamic import、MarketBundle、Runtime、Engine、Runner、account/margin/funding implementation和wall clock。Production Runtime不得import concrete profile；不新增dependency；
25. G10D不拥有archive completeness、raw parser、Bar aggregation、Execution Fill/Slippage/Liquidity、PERCENT_PRICE final admission、Funding source/Slot、final Settlement price acquisition、Account/Wallet、Margin calculation、Liquidation execution、Bundle Builder、Profile composition、live、deployment或parity。G12完成archive initial state、all revisions/checksums与purpose-specific gap proof前，Resolution固定development-grade。

G10D已由immutable implementation commit `790469d80ddcf3797f03c96c975b77d75a3d49a5`实现并通过冻结验收，状态为`PASSED`。

Primary-source contract：`docs/research/binance-usdm-price-purpose-streams-primary-sources.md`。

Readiness baseline：

```text
G10C frozen acceptance command                                     113 passed
Full test suite                                                    1052 passed
Workspace import boundary                                           PASS (76 files)
mypy 2.3.0                                                           no issues (76 source files)
Primary LSP + scoped pi-lens                                         no blocking errors
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
G10C frozen acceptance command                                     113 passed
Full test suite                                                    1052 passed
Workspace import boundary                                           PASS (76 files)
mypy 2.3.0                                                           no issues (76 source files)
Primary LSP + scoped pi-lens                                         no blocking errors
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

PASSED validation：

```text
G10D frozen acceptance command                                     117 passed
Full test suite                                                    1063 passed
Workspace import boundary                                           PASS (77 files)
mypy 2.3.0                                                           no issues (77 source files)
Primary LSP                                                          no diagnostics
Scoped pi-lens                                                       no blocking errors; duplicate-code warnings only
uv lock --check                                                      PASS
Python                                                                3.13.5
```

## 81. G10E Binance USDⓈ-M Funding Source Semantics Acceptance Card

```yaml
id: G10E
status: PASSED
depends_on:
  - G09C
  - G09D
  - G10D
owner_package: trading-kernel profiles/binance_usdm
public_interface:
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmFundingSourceRef
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmFundingRateRecord
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmFundingCoverage
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmHistoricalFundingBook
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmFundingSourceQuery
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmFundingSourceResolution
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmFundingSourceFailureCode
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmFundingSourceFailure
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmFundingSourceOutcome
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmFundingSourceModel
test_commands:
  contract: uv run pytest -q tests/profiles/binance_usdm/test_funding_sources.py
  fixture: uv run pytest -q tests/profiles/binance_usdm/test_funding_sources_golden.py
  boundary: uv run pytest -q tests/architecture/test_binance_usdm_profile_boundary.py tests/architecture/test_derivative_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  regression: uv run pytest -q tests/kernel/derivatives/test_linear_funding_eligibility.py tests/kernel/derivatives/test_linear_funding_eligibility_golden.py tests/kernel/derivatives/test_linear_funding_accounting.py tests/kernel/derivatives/test_linear_funding_accounting_golden.py tests/kernel/marks/test_mark_resolver.py tests/kernel/marks/test_mark_resolver_golden.py tests/profiles/binance_usdm/test_instrument_metadata.py tests/profiles/binance_usdm/test_price_streams.py
  acceptance: uv run pytest -q tests/profiles/binance_usdm/test_funding_sources.py tests/profiles/binance_usdm/test_funding_sources_golden.py tests/kernel/derivatives/test_linear_funding_eligibility.py tests/kernel/derivatives/test_linear_funding_eligibility_golden.py tests/kernel/derivatives/test_linear_funding_accounting.py tests/kernel/derivatives/test_linear_funding_accounting_golden.py tests/kernel/marks/test_mark_resolver.py tests/kernel/marks/test_mark_resolver_golden.py tests/profiles/binance_usdm/test_instrument_metadata.py tests/profiles/binance_usdm/test_price_streams.py tests/architecture/test_binance_usdm_profile_boundary.py tests/architecture/test_derivative_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g10e-pytest.xml
fixture_ids:
  - binance-usdm-historical-funding-source-v1
  - binance-usdm-funding-source-semantics-v1
expected_artifacts:
  - docs/research/binance-usdm-funding-source-semantics-primary-sources.md
  - tests/fixtures/profiles/binance-usdm-historical-funding-source-v1.json
  - tests/fixtures/profiles/binance-usdm-funding-source-semantics-v1.json
  - build/acceptance/g10e-pytest.xml
  - build/acceptance/g10e-import-boundary-report.json
failure_contracts:
  - instrument-metadata-contract-or-application-key-context-mismatch
  - missing-funding-source-row-rate-mark-or-rate-type
  - source-row-not-visible-by-captured-at
  - missing-or-overlapping-funding-coverage
  - special-additional-or-unknown-funding-rate-type
  - duplicate-conflicting-or-superseding-same-slot-source
  - malformed-overflow-or-inexact-rate-or-mark-decimal
  - source-funding-time-or-archive-causality-invalid
  - current-predicted-neighboring-or-recomputed-rate-substitutes-history
  - nearby-mark-index-trade-or-estimated-settlement-substitutes-associated-mark
  - funding-mark-cannot-exactly-use-contract-price-scale
  - fixed-publication-or-settlement-phase-is-changed
  - funding-mark-resolution-does-not-use-frozen-zero-age-policy
  - model-digest-omits-source-mapping-revision-or-timing-policy
  - source-query-filesystem-network-wall-clock-runtime-or-engine-leakage
allowed_grade: development
evidence:
  - readiness-contract-tests
  - official-source-note
  - static-source-and-golden-fixture-hashes
  - slot-publication-associated-mark-and-settlement-evidence
  - g09c-g09d-generic-mark-compatibility-evidence
  - public-api-import-report
  - import-boundary-report
  - static-type-report
  - dependency-lock-report
passed_commit: 195265b1ed830e62b91882ff315b115e7ac80597
artifact_hashes:
  tests/fixtures/profiles/binance-usdm-historical-funding-source-v1.json: sha256:db70f5bded639e56373a1bfa7fe3a16350f712f18a2f9a8bc9dbae091d756b76
  tests/fixtures/profiles/binance-usdm-funding-source-semantics-v1.json: sha256:9e1fdf8b190d8cc952c3e6017d326029ba4c0dec9d2b95745a0e759084e5f457
  build/acceptance/g10e-pytest.xml: sha256:fad8b12b60ed87bdff4c6f4080f0d2ffd38a435ebf42e6273147f7cb54801af1
  build/acceptance/g10e-import-boundary-report.json: sha256:d9c1ea3790e4ab529930768c6984b0f552a12832dd119b9c6276925d5d5b7156
```

### G10E Acceptance

冻结边界：

1. G10E是纯离线`crypto_quant_trading.profiles.binance_usdm.funding_sources` Adapter。Production code只消费caller-supplied immutable G10A Instrument Resolution、完整G09A `LinearPerpetualContract`、G09D `LinearFundingApplicationKey`、finite Historical Funding Book、target Funding UTC与capture instant；不得创建provider client、发HTTP/WebSocket、解析JSON/CSV/ZIP、读取filesystem/database/wall clock或fallback到current REST/WebSocket/Data Vision directory。G12拥有acquisition/parsing/checksum/retention与complete slot-gap proof；
2. `BinanceUsdmFundingSourceRef` exact保存source key、SHA-256 content hash、revision ID、optional superseded revision、archive key/path与captured provenance。Source kind固定为USDⓈ-M Funding Rate History；Mark Price Stream、premiumIndex、Funding Info、Account Update、Income History、G10D Mark Kline或third-party funding feed不得伪装成accepted source；
3. `BinanceUsdmFundingRateRecord` exact保存stable Instrument、raw `funding_time_milliseconds`、optional raw `funding_rate`、optional raw `mark_price`、optional raw `rate_type`、caller-supplied `archive_available_at: SimulationInstant`、source event ID/revision lineage与Source Ref。Optional字段只为structured missing-evidence failure；constructor仍验证exact types、nonnegative millisecond、canonical source identity与hash；
4. `BinanceUsdmFundingCoverage`按stable Instrument保存finite half-open UTC coverage、stream key/version与source lineage。`BinanceUsdmHistoricalFundingBook` exact保存一个Instrument、canonical-sorted Coverages和Records；首尾缺失、内部gap、overlap、duplicate coverage ID、cross-Instrument或按tuple input order选winner均fail closed；
5. `BinanceUsdmFundingSourceQuery` exact绑定G10A Resolution、完整G09A Contract、G09D Application Key、Historical Funding Book、`target_funding_time: UtcInstant`与`captured_at: SimulationInstant`。G10A query effective-at必须等于target，listing interval必须覆盖target，G10A captured-at不得晚于Query captured-at.instant；Contract Instrument/Currencies/multiplier lineage、Application Key Slot Instrument与derived target Slot、Book Instrument必须exact匹配；
6. Slot mapping exact为`FundingSlotId.derive(stable InstrumentId,target_funding_time)`，其中target必须exact等于accepted row `fundingTime`。Slot identity不得包含symbol、rate、mark、rate type、interval、account、revision、source或capture；不得假设8h/4h/1h cadence，不得从Funding Info `fundingIntervalHours`或neighboring rows推断missing target；
7. V1只接受target上exact一个visible immutable `rateType="Regular"` root row。Missing rate type返回structured failure；`Special` additional funding与unknown type均unsupported。任何visible `Special` row都不能被忽略，即使同时存在Regular；不得sum、net、merge或为Special复用同一G09C Slot/Application identity。任一record/source `supersedes_revision_id`非空、same-slot duplicate或same natural event/revision changed bytes均fail closed；
8. Provider `fundingTime`只提供millisecond UTC，不提供repository phase。System ordering convention exact冻结为`SimulationInstant(target_funding_time,TimelinePhase(110,"funding_settlement"),SourceSequence(0))`。它同时成为G09C Publication `publication_available_at`和G09D Settlement `applied_at`，位于G09C frozen eligibility phase rank 100之后；这不声称provider matching-engine内部phase。Archive availability/capture独立保存且不得早于target settlement instant；
9. Accepted raw `fundingRate`直接映射exact `Rate(...,basis="funding_fraction_of_notional")`，允许negative、zero、positive，不做percentage conversion、interval annualization、cap/floor、interest/premium formula、sign inversion或recalculation。Mark Price Stream `r/T`、REST `lastFundingRate/nextFundingTime`、Funding Info、current API或neighboring row不能成为historical final publication；
10. Accepted raw `markPrice`只映射same row、same target的`PricePurpose.FUNDING` `MarkObservation`。Frozen StaleMarkPolicy key/version/digest使用zero max age与`allow_forward_fill=false`；Adapter调用generic `MarkResolver`并保存完整`ResolvedMark`/Policy为G09D `LinearFundingMarkEvidence`。Nearby G10D Mark Kline、ordinary mark update、index、moving-average mark、estimated settlement、contract trade/last price不得fallback；
11. Funding Mark必须strictly positive且raw decimal必须在supplied G09A Contract `price_scale` exact representable；Adapter不得round、truncate或修改Contract Scale。Mark observed/resolved UTC exact为target，economic age exact为0；generic Mark availability只表达UTC，full phase causality由nested source record、fixed settlement instant与Query captured-at共同重验；
12. Resolution exact包含model key/version/digest、完整Query/Book与selected source row、derived Slot、G09C `LinearFundingRatePublicationCandidate(FINAL_RATE)`、Funding `MarkObservation`/`LinearFundingMarkEvidence`、绑定caller Application Key的G09D `LinearFundingSettlementEvidence`、coverage、limitations与`decision_grade_eligible=false`。Publication/Settlement event/hash/revision/source identity必须来自same selected row；Applied Rate必须exact等于Publication Rate；
13. Visible source只允许`archive_available_at <= query.captured_at`。Target band存在但没有visible exact row返回not-available，不得选择前一/后一Slot。V1接受一个root immutable source revision；later supersession不能伪装成original-target publication revision，也不能由current API retroactively rewrite frozen output；
14. Provider failure precedence exact为：`INSTRUMENT_METADATA_MISMATCH` → `CONTRACT_CONTEXT_MISMATCH` → `APPLICATION_KEY_MISMATCH` → `MISSING_FUNDING_SOURCE_RECORDS` → `SOURCE_NOT_AVAILABLE` → `MISSING_FUNDING_COVERAGE` → `OVERLAPPING_FUNDING_COVERAGE` → `MISSING_RATE_TYPE` → `UNSUPPORTED_RATE_TYPE` → `MISSING_FUNDING_RATE` → `MISSING_FUNDING_MARK` → `INVALID_DECIMAL_FIELD` → `INVALID_SOURCE_TIMING` → `UNSUPPORTED_SOURCE_REVISION` → `SOURCE_IDENTITY_CONFLICT` → `MARK_SCALE_MISMATCH`；多缺陷只返回第一项。Frozen single-row/zero-age/no-forward-fill construction使generic Mark resolution没有独立business ambiguity/staleness branch；unexpected generic failure是implementation invariant error，不伪装成provider failure；
15. Exact predicates分别覆盖G10A query/resolution/Book/target mismatch；Contract Instrument/base/quote/settlement/multiplier/quantity-price Scale lineage mismatch；Application Key Slot/account shape mismatch；no rows、late-only rows、coverage gap/overlap；missing/unsupported type/rate/mark；noncanonical signed Rate或positive Mark；fundingTime非target、archive before economic target、nonfixed derived phase；supersession/duplicate/conflict；Mark不能在Contract Scale exact表示。Constructor output与recomputed authority不一致直接拒绝为`TypeError`/`ValueError`，不是business failure；
16. Decimal grammar exact为ASCII ordinary decimal string。Rate允许optional leading `-`与canonical zero，Mark禁止sign且必须positive；两者禁止leading plus、whitespace、exponent、NaN/Infinity、Unicode alternative、empty integer/fraction或超过18 fractional places。Mapping只用string/integer arithmetic；raw trailing zeros进入source identity；禁止float、ambient Decimal context、`pricePrecision`与pre-quantization；
17. Model digest preimage exact包含schema、accepted endpoint/source kind、Regular-only policy、Special unsupported policy、Slot key、fixed phase/sequence、rate basis/direct mapping、associated-mark-only mapping、frozen stale policy、root-only revision policy、coverage/visibility、decimal/scale rules、development grade与limitations。G10E不新增generic `ProfilePortType`；G10G按model digest与Resolution hashes组合final Profile identity；
18. 所有新增public values使用`schema_version=1`、exact types、canonical tuple order与`canonical_sha256` hashes。Constructor必须重算Source Ref、Record、Coverage、Book、Query、Resolution、Failure、Outcome、Slot、Publication、MarkObservation/ResolvedMark/Policy/MarkEvidence与Settlement Evidence identities，并拒绝`dataclasses.replace`伪造任一authority；
19. 相同logical inputs任意tuple order产生相同canonical Outcome。Natural key exact为stable Instrument + fundingTime + rateType；same event ID/revision/source hash changed bytes、duplicate target Regular、Regular+Special、supersession或coverage overlap不得按输入顺序选winner；
20. Static source/golden至少覆盖：positive/negative/zero Regular Rate；non-8h target times；exact Slot sensitivity/invariance；same row Publication/Mark/Settlement identity；before/at/after archive capture；missing source/rate/mark/type；Special与unknown type；duplicate/conflict/supersession；coverage exact/gap/overlap；current/predicted/Funding Info/nearby Mark rejection；Mark Scale exact/inexact；generic Mark zero-age/no-forward-fill；all 16 failures、multi-defect precedence、forgery、idempotency、input-order parity与all hashes；
21. Generic compatibility golden固定G09C `FundingSlotId`/Publication/Resolver、G09D Mark/Settlement Evidence/Accounting、generic MarkResolver schema/bytes/hash/behavior不变。G10E只生成accepted generic evidence，不修改G09C、G09D、MarkResolver、Journal、Ledger、Engine、Runner或Timeline增加Binance branch；
22. Concrete purity scanner allowlist只允许stdlib、`crypto_quant_domain`、generic `marks`、G09A/G09C/G09D frozen types和same-package G10A types；拒绝filesystem/network/provider SDK/process/database/cloud、dynamic import、MarketBundle、Runtime、Engine、Runner、mutable module/class/decorator state与wall clock。Production Runtime不得import concrete profile；不新增dependency；
23. G10E不拥有Funding archive acquisition/parser/checksum/completeness、historical funding formula/cap/interval reconstruction、Position Snapshot/Eligibility resolution、account user-data/Income parity、cash-flow formula、Money quantization、Journal append、Ledger mutation、Fee、Margin、Liquidation、Bundle Builder、Profile composition、live、deployment或parity。G12完成funding archive initial state、all revisions/checksums与slot-gap proof前，Resolution固定development-grade。

G10E已由immutable implementation commit `195265b1ed830e62b91882ff315b115e7ac80597`实现并通过冻结验收，状态为`PASSED`。

Primary-source contract：`docs/research/binance-usdm-funding-source-semantics-primary-sources.md`。

Readiness baseline：

```text
G10D frozen acceptance command                                     117 passed
Full test suite                                                    1063 passed
Workspace import boundary                                           PASS (77 files)
mypy 2.3.0                                                           no issues (77 source files)
Primary LSP + scoped pi-lens                                         no blocking errors
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
G10D frozen acceptance command                                     117 passed
Full test suite                                                    1063 passed
Workspace import boundary                                           PASS (77 files)
mypy 2.3.0                                                           no issues (77 source files)
Primary LSP + scoped pi-lens                                         no blocking errors
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

PASSED validation：

```text
G10E frozen acceptance command                                     112 passed
Full test suite                                                    1072 passed
Workspace import boundary                                           PASS (78 files)
mypy 2.3.0                                                           no issues (78 source files)
Primary LSP + scoped pi-lens                                         no diagnostics
uv lock --check                                                      PASS
Python                                                                3.13.5
```

## 82. G10F Binance USDⓈ-M Fee and Account Profile Acceptance Card

```yaml
id: G10F
status: PASSED
depends_on:
  - WP-05H
  - WP-05J
  - G09F
  - G10A
owner_package: trading-kernel profiles/binance_usdm
public_interface:
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmAccountSourceKind
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmAccountProfileSourceRef
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmAccountProfileScope
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmAccountProfileBand
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmHistoricalAccountProfileBook
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmAccountProfileQuery
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmAccountProfileResolution
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmAccountProfileFailureCode
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmAccountProfileFailure
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmAccountProfileOutcome
  - crypto_quant_trading.profiles.binance_usdm.BinanceUsdmAccountProfileModel
test_commands:
  contract: uv run pytest -q tests/profiles/binance_usdm/test_account_profile.py
  fixture: uv run pytest -q tests/profiles/binance_usdm/test_account_profile_golden.py
  boundary: uv run pytest -q tests/architecture/test_binance_usdm_profile_boundary.py tests/architecture/test_derivative_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  regression: uv run pytest -q tests/kernel/fee_reservations/test_fee_reservation_estimator.py tests/kernel/fees/test_fee_assessment_engine.py tests/kernel/derivatives/test_linear_margin_requirement.py tests/kernel/derivatives/test_linear_account_margin_projection.py tests/kernel/pretrade_risk/test_pretrade_risk.py tests/profiles/binance_usdm/test_instrument_metadata.py tests/profiles/binance_usdm/test_margin_tiers.py
  acceptance: uv run pytest -q tests/profiles/binance_usdm/test_account_profile.py tests/profiles/binance_usdm/test_account_profile_golden.py tests/kernel/fee_reservations/test_fee_reservation_estimator.py tests/kernel/fees/test_fee_assessment_engine.py tests/kernel/derivatives/test_linear_margin_requirement.py tests/kernel/derivatives/test_linear_account_margin_projection.py tests/kernel/pretrade_risk/test_pretrade_risk.py tests/profiles/binance_usdm/test_instrument_metadata.py tests/profiles/binance_usdm/test_margin_tiers.py tests/architecture/test_binance_usdm_profile_boundary.py tests/architecture/test_derivative_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g10f-pytest.xml
fixture_ids:
  - binance-usdm-historical-account-profile-source-v1
  - binance-usdm-fee-account-profile-v1
expected_artifacts:
  - docs/research/binance-usdm-fee-account-profile-primary-sources.md
  - tests/fixtures/profiles/binance-usdm-historical-account-profile-source-v1.json
  - tests/fixtures/profiles/binance-usdm-fee-account-profile-v1.json
  - build/acceptance/g10f-pytest.xml
  - build/acceptance/g10f-import-boundary-report.json
failure_contracts:
  - missing-late-gapped-or-overlapping-account-profile-band
  - instrument-account-or-source-context-mismatch
  - account-trading-disabled
  - portfolio-margin-hedge-multi-asset-isolated-or-auto-add-mode
  - bnb-fee-discount-requires-unmodeled-discount-asset-and-fx
  - reporting-fee-or-settlement-currency-is-not-exact-usdt
  - malformed-commission-max-notional-or-leverage-field
  - zero-or-nonintegral-selected-leverage
  - negative-maker-rebate-or-taker-commission
  - current-account-response-vip-table-or-neighboring-symbol-backfills-history
  - commission-fee-tier-source-or-quantization-change-does-not-change-schedule
  - reservation-and-final-rule-sets-do-not-share-account-schedule-ref
  - tuple-order-source-revision-or-natural-band-conflict-selects-winner
  - complete-account-risk-policy-is-fabricated-without-capacity-and-state
  - source-query-filesystem-network-wall-clock-runtime-or-engine-leakage
allowed_grade: development
evidence:
  - readiness-contract-tests
  - official-source-note
  - static-source-and-golden-fixture-hashes
  - selected-leverage-fee-rule-and-account-mode-evidence
  - generic-fee-margin-and-pretrade-compatibility-evidence
  - public-api-import-report
  - import-boundary-report
  - static-type-report
  - dependency-lock-report
passed_commit: 07cc15823ec3790b0491220f248a64c334e3a81b
artifact_hashes:
  tests/fixtures/profiles/binance-usdm-historical-account-profile-source-v1.json: sha256:919e5e1c2e09b45986d38fa9a741293432ae6daf7af83b5904ad0afd80d555d0
  tests/fixtures/profiles/binance-usdm-fee-account-profile-v1.json: sha256:f82592ee7c56a016fa9637c9592f2e3d493a8c5f2f7fb4f34e03cd2077f4980d
  build/acceptance/g10f-pytest.xml: sha256:0f8146cb52987ba22ace28249b504a841af140a4330b70cfaa46cd2432a6d346
  build/acceptance/g10f-import-boundary-report.json: sha256:a0c85d591d5035e2cbac3b3392bd72caf4fa0b65188e5754f45417a2488daa43
```

### G10F Acceptance

冻结边界：

1. G10F是纯离线`crypto_quant_trading.profiles.binance_usdm.account_profile` Adapter。Production code只消费caller-supplied immutable G10A Instrument Resolution、Account ID、finite Historical Account Profile Book、evaluated/captured instant与requested Reporting Currency；不得创建provider client、发authenticated request、解析JSON/file、读filesystem/database/wall clock或fallback到current Account Config/Symbol Config/Commission Rate/feeBurn/Position response。G12拥有acquisition/encrypted retention/checksum/initial state/all revisions与coverage proof；
2. `BinanceUsdmAccountSourceKind` exact为`ACCOUNT_CONFIG`、`SYMBOL_CONFIG`、`COMMISSION_RATE`与`FEE_BURN`。`BinanceUsdmAccountProfileSourceRef` exact保存kind、source key、SHA-256 content hash、revision ID、optional superseded revision与archive/evidence key；Band必须exact包含四个不同kind各一个Ref，不能用VIP public table、announcement、Account Trade、G10C bracket、other symbol或third-party fee feed伪装；
3. `BinanceUsdmAccountProfileScope` exact为`STANDARD_UM`与`PORTFOLIO_MARGIN_UM`。V1只有STANDARD_UM可成功；Portfolio Margin response即使字段相似也structured unsupported，不能作为standard cross account；
4. `BinanceUsdmAccountProfileBand` exact保存Band ID、Account ID、stable Instrument ID、finite half-open effective interval、full `available_at: SimulationInstant`、scope、raw `fee_tier`、`can_trade`、`dual_side_position`、`multi_assets_margin`、raw `trade_group_id`、raw `margin_type`、`is_auto_add_margin`、raw selected `leverage`、raw `max_notional_value`、raw maker/taker commission、`fee_burn`与four Source Refs。Raw provider fields、trailing zeros与source tuple进入Band hash；
5. `BinanceUsdmHistoricalAccountProfileBook` exact保存Book key/version、Account、Instrument、finite coverage与canonical-sorted Bands。Visible Bands必须从coverage start到end形成连续half-open coverage；首尾缺失、internal gap/overlap、duplicate Band ID、cross-account/instrument或按tuple order选winner均fail closed；
6. `BinanceUsdmAccountProfileQuery` exact绑定G10A Resolution、Account ID、Book、economic `evaluated_at: UtcInstant`、knowledge `captured_at: SimulationInstant`与requested `reporting_currency_id`。G10A query effective-at必须等于evaluated-at，listing覆盖evaluated-at，G10A captured-at不得晚于Query captured-at.instant；Book/Account/Instrument必须exact匹配；
7. Resolver只使用`band.available_at <= captured_at`的evidence，并要求evaluated-at命中exact一个visible Band。Later/current Band不能补past gap；same effective Band later revision只有在caller-supplied point-in-time capture内可见，branch/gap/duplicate/conflicting revision不得按input order选择；
8. Accepted account mode exact为`can_trade=true`、scope STANDARD_UM、`dual_side_position=false`、`multi_assets_margin=false`、`margin_type="CROSSED"`、`is_auto_add_margin=false`、`fee_burn=false`。Trading disabled、Portfolio Margin、Hedge、Multi-Assets、isolated/unknown margin type、auto-add或BNB fee discount各自structured fail closed；
9. G10A quote Currency、settlement Currency、Fee Currency与requested Reporting Currency必须exact为`CurrencyId("USDT")`。Fee Scale exact为8。不得用USDC/BUSD/BNB、stablecoin label、peg、FX或Multi-Assets asset index满足USDT约束；
10. Raw selected leverage必须positive integral ASCII ordinary decimal with zero fractional part and范围`1..125`；exact映射`LinearMarginLeverageEvidence.selected_leverage=Rate(value,Scale(0),"notional_per_initial_margin")`，effective interval/available/source来自active Band及SYMBOL_CONFIG Ref。G10C `ma/mi/initialLeverage`、`maxNotionalValue`、current leverage response或neighboring symbol不得替代；
11. Raw `max_notional_value`只作为non-negative ordinary decimal source evidence进入identity；不映射G10C Tier cap、不改变selected leverage、不在G10F计算Margin。G10C active Tier maximum仍由G09E在evaluated-at验证；
12. maker/taker commission grammar exact为non-negative ASCII ordinary decimal、最多18 fractional places，允许zero。Mapping直接使用account-specific per-symbol rates，不按feeTier/VIP table/promotion重新计算。任一negative rate或market-maker rebate structured `NEGATIVE_COMMISSION_UNSUPPORTED`，不得clip、转Financing或伪装not-applicable；
13. `AccountFeeScheduleRef` key/version/digest exact绑定Account、Instrument、active Band、maker/taker raw+mapped Rate、feeTier、feeBurn、mode、four source refs、USDT Scale 8、reservation/final quantization与limitations。Reservation/Final Rule Sets必须exact共享同一Ref；Band/source/rate/mode/quantization任一变化必须改变digest；
14. Fee Reservation Rule Set exact使用fixed `ProfileComponentRef(FEE_ASSESSMENT_POLICY,"crypto.binance_usdm.market-fee-not-applicable.v1")`与`ProfileComponentRef(TAX_POLICY,"crypto.binance_usdm.tax-not-applicable.v1")`，并explicit exact-cover三个`FeeReservationRuleSource`：Market Fee ORDER_NOTIONAL+NOT_APPLICABLE+zero `fee_fraction` Rate、Tax ORDER_NOTIONAL+NOT_APPLICABLE+zero `fee_fraction` Rate、Account Schedule ORDER_NOTIONAL+APPLIES。Account rate为`max(maker,taker)` basis `fee_fraction`，Quantization为USDT Scale 8 CEILING，无minimum。Generic `FeeReservationEstimator`会对所有rules先拒绝UNKNOWN basis，即使rule已NOT_APPLICABLE，因此N/A coverage rule必须使用可执行zero-rate representation；
15. Final Fee Rule Set exact共享上述component refs/Account Schedule Ref，全部basis type为FILL：Market Fee NOTIONAL_RATE+NOT_APPLICABLE+zero `fee_fraction` Rate、Tax NOTIONAL_RATE+NOT_APPLICABLE+zero `fee_fraction` Rate、Account Schedule maker NOTIONAL_RATE+MAKER_ONLY与taker NOTIONAL_RATE+TAKER_ONLY；Quantization为USDT Scale 8 TOWARD_ZERO，无minimum。Generic `FeeAssessmentEngine`会对所有rules先拒绝UNKNOWN calculation basis，即使rule已NOT_APPLICABLE，因此N/A coverage rule必须使用可执行zero-rate representation；Engine按actual Fill `liquidity`与price×quantity逐Fill应用，不按Order style猜maker/taker；
16. Account Trade List `commission/commissionAsset/maker`是G10H parity evidence，不是G10F rule source或synthetic Fill future amount。Final rounding在first-party universal rounding rule缺失时固定development convention；G10H未逐Fill parity前`decision_grade_eligible=false`；
17. Resolution exact包含model key/version/digest、完整Query/Book、visible/active Bands、normalized account mode、selected Leverage Evidence、AccountFeeScheduleRef、Reservation Rule Set、Final Rule Set、Fee/Reporting Currency和Scale、`FeeReserveFundingSource.AVAILABLE_MARGIN`、limitations与`decision_grade_eligible=false`。G10F不调用Estimator、FeeAssessmentEngine、Margin Model或Account Margin Projector；
18. G10F不创建完整`AccountRiskPolicy`。Order capacity需要G10B active MAX_NUM_ORDERS/ALGO rules与current Working Orders，Exposure capacity需要G09F/G10C/portfolio policy，Availability需要Journal/Reservation state；G10G才组合allowed sides/effects/reduce-only、capacity与source coverage；
19. Provider failure precedence exact为：`MISSING_PROFILE_BANDS` → `INSTRUMENT_METADATA_MISMATCH` → `ACCOUNT_CONTEXT_MISMATCH` → `PROFILE_NOT_AVAILABLE` → `MISSING_PROFILE_INTERVAL` → `OVERLAPPING_PROFILE_INTERVALS` → `ACCOUNT_TRADING_DISABLED` → `PORTFOLIO_MARGIN_UNSUPPORTED` → `HEDGE_MODE_UNSUPPORTED` → `MULTI_ASSET_MODE_UNSUPPORTED` → `ISOLATED_MARGIN_UNSUPPORTED` → `AUTO_ADD_MARGIN_UNSUPPORTED` → `BNB_FEE_DISCOUNT_UNSUPPORTED` → `REPORTING_CURRENCY_MISMATCH` → `INVALID_DECIMAL_FIELD` → `INVALID_LEVERAGE` → `NEGATIVE_COMMISSION_UNSUPPORTED` → `SOURCE_IDENTITY_CONFLICT`；多缺陷只返回第一项；
20. Exact predicates分别覆盖no Bands；G10A/Book/Instrument/evaluated/capture mismatch；Account mismatch；late-only Band；coverage gap/overlap；disabled/unsupported modes；non-USDT Currency；malformed commission/maxNotional；zero/nonintegral/out-of-range leverage；negative rate；four source kind missing/duplicate、source revision branch/gap、same natural Band/event changed bytes或duplicate identity。Constructor forged output直接`TypeError`/`ValueError`；
21. Decimal mapping只用string/integer arithmetic；raw trailing zeros保留identity；禁止float、ambient Decimal context、current fee table、implicit percent conversion或precision hint。Commission Rate basis exact `fee_fraction`；Leverage basis exact `notional_per_initial_margin`；
22. Model digest exact包含schema、supported account/margin/asset/position/feeBurn scope、source-kind exact coverage、leverage mapping、maker/taker authority、reservation max-rate/CEILING、final per-fill/TOWARD_ZERO、USDT Scale 8、negative-rebate policy、AccountRiskPolicy non-ownership、development limitations与grade。G10F不新增generic `ProfilePortType`；G10G纳入final Profile digest；
23. 所有新增public values使用`schema_version=1`、exact types、canonical tuple order与`canonical_sha256` hashes。Constructor必须重算Source Ref、Band、Book、Query、Resolution、Failure、Outcome、Leverage Evidence、AccountFeeScheduleRef、component refs与两Rule Sets，并拒绝`dataclasses.replace`伪造任一authority；
24. Static source/golden至少覆盖：maker<taker、maker>taker、zero fee；selected leverage before/at/after update及1/125边界；fee-rate and feeTier transitions；before/at/after available-at；coverage exact/gap/overlap；disabled trading；Portfolio/Hedge/Multi-Assets/isolated/auto-add/feeBurn；USDT mismatch；malformed/negative commission、maxNotional和leverage；source kind/revision/conflict；Reservation max rate与CEILING；Final maker/taker/TOWARD_ZERO per-Fill；shared Schedule Ref；all 18 failures、multi-defect precedence、forgery、idempotency、input-order parity与all hashes；
25. Generic compatibility golden固定AccountFeeScheduleRef、FeeReservationRuleSet/Estimator、FinalFeeRuleSet/FeeAssessmentEngine、LinearMarginLeverageEvidence/G09E、G09F与PreTradeRisk schemas/hashes/behavior不变。G10F只生成accepted generic evidence，不修改generic modules或failure precedence；
26. Concrete purity scanner allowlist只允许stdlib、`crypto_quant_domain`、generic `fee_reservations|fees|margin|ports|pretrade_risk`和same-package G10A types；拒绝filesystem/network/provider SDK/process/database/cloud、dynamic import、MarketBundle、Runtime、Engine、Runner、mutable module/class/decorator state与wall clock。Production Runtime不得import concrete profile；不新增dependency；
27. G10F不拥有account source acquisition/secrets/storage/completeness、Wallet/Ledger initial state、actual commission parity、VIP qualification、BNB conversion、negative rebate accounting、multi-currency collateral/FX/haircut、isolated wallet、Position reconstruction、Margin calculation、working-order count、Order/Exposure capacity、AccountRiskPolicy completion、Fee evaluation/Journal、Bundle Builder、Profile composition、live、deployment或parity。G12与G10H完成前固定development-grade。

Primary-source contract：`docs/research/binance-usdm-fee-account-profile-primary-sources.md`。

Readiness baseline：

```text
G10E frozen acceptance command                                     112 passed
Full test suite                                                    1072 passed
Workspace import boundary                                           PASS (78 files)
mypy 2.3.0                                                           no issues (78 source files)
Primary LSP + scoped pi-lens                                         no blocking errors
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
G10E frozen acceptance command                                     112 passed
Full test suite                                                    1072 passed
Workspace import boundary                                           PASS (78 files)
mypy 2.3.0                                                           no issues (78 source files)
Primary LSP + scoped pi-lens                                         no blocking errors
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

### G10F Implementation Acceptance

1. Caller-supplied finite Account Profile Book按economic/knowledge time解析exact visible Band；coverage gap/overlap、late-only、cross Account/Instrument、duplicate Band ID与source revision branch/gap/conflict均按冻结precedence fail closed；
2. Standard UM、tradable、One-way、Single-Asset、CROSSED、no-auto-add、feeBurn-off、USDT-only成功；Portfolio Margin、Hedge、Multi-Assets、isolated/unknown、auto-add、BNB discount与negative commission structured fail closed；
3. Selected integral leverage映射existing `LinearMarginLeverageEvidence`；maker/taker direct映射共享`AccountFeeScheduleRef`的Reservation/Final Rule Sets。Reservation使用`max(maker,taker)`、Scale 8 CEILING；Final使用actual Fill maker/taker、Scale 8 TOWARD_ZERO；
4. Market Fee/Tax N/A coverage rules使用generic Estimator/Engine可执行的zero-rate basis；generic Fee Reservation、Fee Assessment、Margin、Account Margin与PreTradeRisk modules未修改且regression通过；
5. Public exports、exact import allowlist、79-file Import Boundary、static source/golden、full mypy/LSP/pi-lens与dependency lock checks通过；Adapter不读取network/filesystem/wall clock且未增加Runtime/provider branch；
6. Account Trade List parity、historical archive completeness、full `AccountRiskPolicy`、multi-asset/isolated/BNB/negative rebate与deployment继续由G10H/G10G/G12拥有，Resolution固定`decision_grade_eligible=false`。

G10F implementation已冻结在immutable commit `07cc15823ec3790b0491220f248a64c334e3a81b`，状态为`PASSED`。

验证记录：

```text
G10F frozen acceptance command                                     140 passed
G10F contract + golden + boundary                                   16 passed
Full test suite                                                    1085 passed
Workspace import boundary                                           PASS (79 files)
mypy 2.3.0                                                           no issues (79 source files)
Primary LSP + scoped pi-lens                                         no blocking errors
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

## 83. G10G Binance USDⓈ-M Resolved Profile Composition Acceptance Card

```yaml
id: G10G
status: PASSED
depends_on:
  - G09H
  - G10A
  - G10B
  - G10C
  - G10D
  - G10E
  - G10F
owner_package: backtest-runtime composition + tests/support
public_interface:
  - crypto_quant_backtest.BinanceUsdmAccountCapacityEvidence
  - crypto_quant_backtest.BinanceUsdmProfileCompositionRequest
  - crypto_quant_backtest.BinanceUsdmMarketSemanticsProfile
  - crypto_quant_backtest.BinanceUsdmSimulationProfile
  - crypto_quant_backtest.BinanceUsdmExecutionAccountProfile
  - crypto_quant_backtest.BinanceUsdmResolvedProfile
  - crypto_quant_backtest.BinanceUsdmProfileCompositionFailureCode
  - crypto_quant_backtest.BinanceUsdmProfileCompositionFailure
  - crypto_quant_backtest.BinanceUsdmProfileCompositionOutcome
  - crypto_quant_backtest.BinanceUsdmProfileComposer
  - tests.support.binance_usdm.BinanceUsdmDevelopmentFinancialDispatcher
  - tests.support.binance_usdm.build_binance_usdm_resolved_request
  - tests.support.binance_usdm.build_binance_usdm_execution_case
  - static Binance USDⓈ-M resolved-profile development journey golden fixture v1
test_commands:
  contract: uv run pytest -q tests/runtime/profiles/binance_usdm/test_profile_composition.py tests/support/binance_usdm/test_binance_usdm_profile.py
  fixture: uv run pytest -q tests/runtime/engine/test_g10g_binance_usdm_golden.py
  journey: uv run pytest -q tests/runtime/engine/test_g10g_binance_usdm_journey.py tests/runtime/runner/test_g10g_binance_usdm_runner.py
  boundary: uv run pytest -q tests/architecture/test_binance_usdm_profile_boundary.py tests/architecture/test_g10g_binance_composition_boundary.py tests/architecture/test_g09h_composition_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py tests/runtime/resolution/test_backtest_resolution.py tests/runtime/runner/test_auditable_runner.py
  acceptance: uv run pytest -q tests/runtime/profiles/binance_usdm/test_profile_composition.py tests/support/binance_usdm/test_binance_usdm_profile.py tests/runtime/engine/test_g10g_binance_usdm_journey.py tests/runtime/engine/test_g10g_binance_usdm_golden.py tests/runtime/runner/test_g10g_binance_usdm_runner.py tests/runtime/resolution/test_backtest_resolution.py tests/runtime/engine/test_g09h_synthetic_linear_perpetual_journey.py tests/kernel/pretrade_risk/test_pretrade_risk.py tests/profiles/binance_usdm/test_instrument_metadata.py tests/profiles/binance_usdm/test_order_rules.py tests/profiles/binance_usdm/test_margin_tiers.py tests/profiles/binance_usdm/test_price_streams.py tests/profiles/binance_usdm/test_funding_sources.py tests/profiles/binance_usdm/test_account_profile.py tests/architecture/test_binance_usdm_profile_boundary.py tests/architecture/test_g10g_binance_composition_boundary.py tests/architecture/test_g09h_composition_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g10g-pytest.xml
fixture_ids:
  - binance-usdm-resolved-profile-development-journey-v1
expected_artifacts:
  - docs/research/binance-usdm-profile-composition-primary-sources.md
  - tests/fixtures/runtime/engine/binance-usdm-resolved-profile-development-journey-v1.json
  - build/acceptance/g10g-pytest.xml
  - build/acceptance/g10g-import-boundary-report.json
failure_contracts:
  - required-g10a-through-g10f-authority-is-missing
  - provider-resolution-instrument-account-time-or-coverage-context-mismatch
  - current-or-neighboring-provider-state-fills-composition-gap
  - required-price-purpose-is-missing-duplicated-or-substituted
  - funding-source-is-missing-outside-window-or-not-the-g10e-authority
  - active-deferred-order-rule-is-silently-erased
  - closed-admission-is-composed-as-executable
  - order-capacity-evidence-does-not-match-active-g10b-source
  - separate-binance-order-counters-are-expanded-into-a-larger-generic-limit
  - account-max-notional-or-g10c-terminal-coverage-is-malformed-or-bypassed
  - complete-account-risk-policy-omits-source-capacity-or-fee-funding-dimension
  - linear-contract-uses-precision-hints-instead-of-g10b-scales
  - profile-component-manifest-is-partial-duplicated-or-forged
  - profile-digest-omits-provider-resolution-risk-simulation-or-limitation-identity
  - profile-resolver-accepts-wrong-venue-account-currency-capability-or-grade
  - engine-runner-ledger-timeline-or-composer-adds-a-binance-branch
  - dispatcher-object-callback-module-path-or-runtime-address-enters-case-identity
  - development-profile-claims-decision-grade-live-or-deployment-authorization
allowed_grade: development
evidence:
  - readiness-contract-tests
  - inherited-official-primary-source-notes
  - composed-contract-account-risk-component-and-registration-hashes
  - exact-price-purpose-and-funding-coverage-evidence
  - resolved-environment-and-build-artifact-identity
  - full-funding-margin-fee-liquidation-journey-and-reconstruction
  - static-golden-hash
  - import-boundary-report
  - static-type-report
  - dependency-lock-report
passed_commit: 12286dbf6b7289fcb2f6069c46fc648d8f5a5be0
artifact_hashes:
  tests/fixtures/runtime/profiles/binance-usdm-resolved-profile-composition-v1.json: sha256:e9e329b4cd2dfd990a8eec8460767b6b05fffcc126e876a2cdf86f15a6d06bd9
  tests/fixtures/runtime/engine/binance-usdm-resolved-profile-development-journey-v1.json: sha256:179e63dc6d56b52ee3bd9bd0751ef0480bbdfb3bd344ca1de60b393d9e4efb16
  build/acceptance/g10g-pytest.xml: sha256:6b866349c9ca875ceefae8db1668376c8a88869581c4ce9b7d034c1d2ddc3ede
  build/acceptance/g10g-import-boundary-report.json: sha256:78b4760264f9ffdf1fb5cb206c847e98165f9593c5ea5eaba6859843b8e44499
```

### G10G Acceptance

1. G10G只拥有pure production composition authority、development-only Binance test dispatcher/Journey与现有profile-neutral Runtime seam的组合；不得修改G10A–G10F source facts、调用provider/current API、解析JSON/file、读取filesystem/database/wall clock、构建MarketBundle、证明archive completeness、授权live/deployment或执行G10H parity；
2. Production seam固定为单一`crypto_quant_backtest.binance_usdm_profile` module及root exports。它只消费caller-supplied immutable G10A Instrument Resolution、G10B Order Rule Resolution、G10C Margin Tier Resolution、G10D Price Purpose Resolutions、G10E Funding Source Resolutions、G10F Account Profile Resolution、Account Capacity Evidence、finite Timeline Window与composition `SimulationInstant`；不得重新运行provider Model或读取Runtime current state；
3. `BinanceUsdmAccountCapacityEvidence` exact保存evidence key/version、Account、stable Instrument、finite half-open effective interval、full available-at、positive raw `max_num_orders`/`max_num_algo_orders`、active G10B source key/hash与revision ID。Constructor exact types/canonical identity；它不是Working Order count或current account query；
4. Generic `AccountRiskPolicy`只有一个order-capacity dimension。V1 exact使用`min(max_num_orders,max_num_algo_orders)`作为conservative development convention；不得取max、相加、忽略algo cap或声称与Binance split counters parity。Working Order count仍由generic PreTradeRisk input提供；
5. Exposure capacity exact把G10F active Band raw `max_notional_value`按ordinary string/integer arithmetic映射USDT Scale 8 Money，并与G10C `finite_terminal_notional_cap`取minimum。两者必须positive、same USDT/Scale且覆盖run window；不得把account value替代G10C tier selection，也不得从`ma/mi/initialLeverage`、current position、wallet或stablecoin peg构造cap；
6. Composed `AccountRiskPolicy` exact使用G10F Account/Venue、G10B active Snapshot allowed sides/effects/reduce-only semantics、G10F `FeeReserveFundingSource.AVAILABLE_MARGIN`、第4条order cap与第5条single-USDT exposure cap。NORMAL可按active capability允许ordinary/reduce-only；REDUCE_ONLY只允许CLOSE与`reduce_only=true`；CLOSED composition structured fail；
7. `BinanceUsdmProfileCompositionRequest` exact保存optional六类provider authorities、canonical Price Resolution tuple、Funding Resolution tuple、optional Capacity Evidence、finite `TimelineWindow`与`composed_at`。Optional只用于structured missing-authority failures；constructor不隐藏业务缺失；tuple按purpose/target/source identity canonical sort；
8. G10A Instrument/listing、G10B active Band、G10C active Band、G10F active Band与Capacity interval必须exact覆盖完整run window；各query economic Instrument/Account/time、capture/availability与composition instant必须相容。Later/current resolution不能补历史窗口，单点active Band不能越过transition外推；
9. Generic G09A `LinearPerpetualContract`只由G10A Instrument/`base_quantity_per_contract` multiplier与G10B exact `quantity_scale`/`price_scale`构造。`pricePrecision`、`quantityPrecision`、mark decimals、display hints或G10D Price不得进入Scale；
10. Required Price Purpose set exact为`EXECUTION_REFERENCE`、`VALUATION`、`MARGIN`、`LIQUIDATION`各一个successful G10D Resolution。Purpose、Instrument、coverage、requested/available time或source identity缺失/duplicate/mismatch fail closed；不得在Purpose之间fallback。`FUNDING`只由G10E提供，`SETTLEMENT`固定unsupported；
11. Funding tuple至少包含Journey内每个scheduled Slot唯一successful G10E Resolution，且Instrument、Account/Application Key、Slot target、coverage、publication/mark/settlement identity和availability exact匹配。G10G不得重算rate、cadence、mark或cash flow；
12. Active G10B deferred set只允许`MAX_NUM_ORDERS`与`MAX_NUM_ALGO_ORDERS`，且两者必须同时存在并由matching Capacity Evidence完成；Result显式保存source deferred keys与composed resolved keys，绝不改写G10B Resolution identity。`PERCENT_PRICE`、`MARKET_TAKE_BOUND`、`TRIGGER_PROTECT`与advanced capabilities v1 structured unsupported，不能被G10D marks、Capacity Evidence或generic policy silently erased；
13. Market Profile key exact为`crypto.binance_usdm.v1`、version 1；Simulation key exact为`bar.next_eligible_open.conservative.v1`、version 1；Execution Account key exact为`binance.usdm.standard-cross.v1`、version 1。旧planning label `binance.usdm.vip0.cross.v1`不得使用，因为feeTier不是rate authority；
14. `BinanceUsdmMarketSemanticsProfile` exact-cover全部现有`ProfilePortType`且不新增generic port。Manifest包含：UTC-continuous development Session、G10A Instrument、G10B Order Rules、G10F account-fee composition、explicit no Tax、no delivery Settlement、G09A/G09B Position Accounting、G10E+G09D Financing、G10C+G09E+G09F Margin、G10D+G09G conservative Liquidation Rules、no Corporate Action与single-USDT identity Valuation；
15. Reused G10A/G10B component refs必须exact等于source Model refs；composed Fee/Margin/Liquidation refs的digest必须绑定对应G10 resolution hashes、generic G09 component refs、contract/risk identity、Price Purpose coverage与limitations。No-op components也必须versioned/digested，不能用`None`、empty string或synthetic identity；
16. `BinanceUsdmSimulationProfile` exact-cover全部`SimulationPortType`：`NextEligibleBarOpenModel`、fixed deterministic zero-bps Slippage、zero-latency development component、conservative bar-open Liquidity、G09G conservative Liquidation Audit与Mark-to-Market Closeout。上述均为repository convention，不声称Binance matching-engine、queue、latency或liquidation parity；
17. Market required capabilities exact至少包含`bar_open@1`、`account.financial-event@1`、`binance_usdm.price-purpose-streams@1`与`binance_usdm.funding-publications@1`；Simulation required capability为`bar_open@1`。ProfileResolver继续自动要求precomputed Target capability；缺少/低版本capability structured incompatibility；
18. `BinanceUsdmExecutionAccountProfile` exact保存Account、Venue `binance_usdm`、account type `linear_perpetual`、margin mode `cross_single_asset_one_way`、USDT-only reporting、G10F Account Schedule、AccountRiskPolicy与provider resolution manifest；profile digest任一输入变化必须变化；
19. Market、Simulation、Execution Account implementations structural满足existing registration protocols。Composer exact产生三个registrations与`BacktestProfileRegistry`；Registration header/digest/component manifest必须与implementation重算一致。ProfileResolver在matching Bundle/Build/Request下成功，wrong Venue/Account/Currency/engine/capability/build/profile key或decision-grade request沿既有generic checks fail；
20. Overall `BinanceUsdmResolvedProfile` exact包含model key/version/digest、完整Request、provider resolution hash manifest、Linear Contract、AccountRiskPolicy、three profile implementations/registrations、Registry、FinancialDispatcherSpec、required capabilities、limitations、`decision_grade_eligible=false`与`deployment_authorized=false`。Constructor重算全部derived fields并拒绝`dataclasses.replace`伪造；
21. Financial Dispatcher key exact为`crypto.binance_usdm.linear-financial-dispatch.v1`。Spec config hash绑定overall Profile、Contract、Risk Policy、provider Resolution manifest、Market/Simulation component manifests与limitations；position/financing/margin/liquidation refs exact对应Profile。Case/semantic identity仍只保存Spec/plans/payloads，不保存implementation object/callback/module path/runtime address/Attempt ID/wall clock；
22. Provider composition failure precedence exact为：`MISSING_INSTRUMENT_METADATA` → `MISSING_ORDER_RULES` → `MISSING_MARGIN_TIERS` → `MISSING_ACCOUNT_PROFILE` → `MISSING_ACCOUNT_CAPACITY` → `MISSING_PRICE_PURPOSE` → `MISSING_FUNDING_SOURCE` → `INSTRUMENT_CONTEXT_MISMATCH` → `ACCOUNT_CONTEXT_MISMATCH` → `TIMELINE_COVERAGE_MISMATCH` → `EVIDENCE_NOT_AVAILABLE` → `ORDER_ADMISSION_CLOSED` → `DEFERRED_ORDER_RULE_UNSUPPORTED` → `ORDER_CAPACITY_SOURCE_MISMATCH` → `ORDER_CAPACITY_UNREPRESENTABLE` → `EXPOSURE_CAPACITY_INVALID` → `PRICE_PURPOSE_COVERAGE_MISMATCH` → `FUNDING_CONTEXT_MISMATCH` → `COMPONENT_IDENTITY_CONFLICT`；多缺陷只返回第一项；
23. Test-support `BinanceUsdmDevelopmentFinancialDispatcher`可导入G09A–G09G generic implementations和G10 normalized evidence，但不得读取provider/network/filesystem/current Registry。它实现existing `FinancialEventDispatcher`，Engine/Runner/Timeline/Journal/Ledger/Composer不新增Binance imports、`isinstance`、name match或operation branch；
24. Frozen Journey使用single Binance Account/Instrument/USDT、One-way cross mode、normal order admission、three deterministic full Fills形成Long OPEN→partial REDUCE→FLIP Short，并包含Long期间一个G10E Funding Event、Long-low和Short-high G10D Liquidation bars、G10C/G10F Margin inputs、G10F maker/taker Fees与final Snapshot。全部走G09H canonical plans/events/artifacts；
25. Reconstruction exact重复G09H四路径：Final Journal→Generic Ledger；specialized Journal→G09B Position；Ledger+Position+G10C/G10D/G10F/Reservations→G09F Projection；Ledger+Projection+VALUATION authority→PortfolioSnapshot。Funding、Fee、Margin、Liquidation artifacts保存完整provider resolution/result identities，不能只保存裸hash或从Engine mutable side-state抄回；
26. Profile/Resolution/Failure/Outcome/Capacity Evidence全部explicit `schema_version=1`、canonical tuple order/content hashes。Static golden至少冻结all G10 resolution/model hashes、capacity/risk/contract/component/profile/registration/registry/dispatcher/resolved-environment identities、failure precedence、wrong-grade/capability controls、three-Fill/Funding/Fee/Margin/Liquidation/Journal/Ledger/Snapshot/artifact/repeat parity；
27. Production purity allowlist仅允许stdlib、`crypto_quant_domain`、`crypto_quant_market_data` contracts、generic `crypto_quant_trading` seams、G10A–G10F public values与same-package Runtime resolution/financial-dispatch/simulation refs；拒绝filesystem/network/provider SDK/process/database/cloud/dynamic import/MarketBundle Reader/Engine/Runner/mutable global state/wall clock。G10G不拥有archive completeness、matching-engine parity、Account Trade parity、real liquidation/ADL/bankruptcy/insurance fund、multi-assets/isolated/Hedge/BNB/negative rebate/Portfolio Margin、live或deployment；全部output固定development-grade。

Primary-source and system-convention boundary：`docs/research/binance-usdm-profile-composition-primary-sources.md`。

Readiness baseline：

```text
G10F frozen acceptance command                                     140 passed
Full test suite                                                    1085 passed
Workspace import boundary                                           PASS (79 files)
mypy 2.3.0                                                           no issues (79 source files)
Primary LSP + scoped pi-lens                                         no blocking errors
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
G10F frozen acceptance command                                     140 passed
Full test suite                                                    1085 passed
Workspace import boundary                                           PASS (79 files)
mypy 2.3.0                                                           no issues (79 source files)
Primary LSP + scoped pi-lens                                         no blocking errors
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Acceptance validation：

```text
G10G frozen acceptance command                                     131 passed
Full test suite                                                    1101 passed
Workspace import boundary                                           PASS (80 files)
mypy 2.3.0                                                           no issues (80 source files)
Primary LSP + scoped pi-lens                                         no blocking errors
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Implementation commit：`12286dbf6b7289fcb2f6069c46fc648d8f5a5be0`。

## 84. G10H Binance USDⓈ-M Layered Parity Acceptance Card

```yaml
id: G10H
status: PASSED
depends_on:
  - G10G
  - WP-00C
owner_package: parity tooling
public_interface:
  - tools/parity/binance_usdm.py
  - tools/parity/run_binance_usdm_parity.py
  - binance-usdm-g10h-parity-plan-v1
  - binance-usdm-g10h-parity-report-v1
test_commands:
  readiness: uv run pytest -q tests/runtime/profiles/binance_usdm/test_profile_composition.py tests/support/binance_usdm/test_binance_usdm_profile.py tests/runtime/engine/test_g10g_binance_usdm_journey.py tests/runtime/engine/test_g10g_binance_usdm_golden.py tests/runtime/runner/test_g10g_binance_usdm_runner.py tests/runtime/resolution/test_backtest_resolution.py tests/runtime/engine/test_g09h_synthetic_linear_perpetual_journey.py tests/kernel/pretrade_risk/test_pretrade_risk.py tests/profiles/binance_usdm/test_instrument_metadata.py tests/profiles/binance_usdm/test_order_rules.py tests/profiles/binance_usdm/test_margin_tiers.py tests/profiles/binance_usdm/test_price_streams.py tests/profiles/binance_usdm/test_funding_sources.py tests/profiles/binance_usdm/test_account_profile.py tests/architecture/test_binance_usdm_profile_boundary.py tests/architecture/test_g10g_binance_composition_boundary.py tests/architecture/test_g09h_composition_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  contract: uv run pytest -q tests/parity/test_binance_usdm_parity.py
  fixture: uv run pytest -q tests/parity/test_binance_usdm_parity_golden.py
  boundary: uv run pytest -q tests/parity/test_comparator_contract.py tests/parity/test_source_snapshots.py tests/architecture/test_g10h_parity_boundary.py tests/architecture/test_repository_cleanliness.py
  acceptance: uv run pytest -q tests/parity/test_binance_usdm_parity.py tests/parity/test_binance_usdm_parity_golden.py tests/parity/test_comparator_contract.py tests/parity/test_source_snapshots.py tests/runtime/engine/test_g10g_binance_usdm_journey.py tests/runtime/engine/test_g10g_binance_usdm_golden.py tests/runtime/runner/test_g10g_binance_usdm_runner.py tests/architecture/test_g10h_parity_boundary.py tests/architecture/test_g10g_binance_composition_boundary.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g10h-pytest.xml
fixture_ids:
  - binance-usdm-g10h-parity-plan-v1
  - binance-usdm-g10h-legacy-projection-v1
  - binance-usdm-g10h-g10g-projection-v1
  - binance-usdm-g10h-provider-record-projection-v1
  - binance-usdm-g10h-parity-report-v1
expected_artifacts:
  - docs/research/binance-usdm-parity-primary-sources.md
  - docs/adr/0001-g10h-legacy-binance-parity-boundary.md
  - tests/parity/contracts/binance-usdm-g10h-legacy-to-g10g-v1.json
  - tests/parity/contracts/binance-usdm-g10h-provider-to-g10g-v1.json
  - tests/parity/fixtures/binance-usdm-g10h-v1/plan.json
  - tests/parity/fixtures/binance-usdm-g10h-v1/legacy.expected.json
  - tests/parity/fixtures/binance-usdm-g10h-v1/g10g.actual.json
  - tests/parity/fixtures/binance-usdm-g10h-v1/provider.expected.json
  - tests/parity/fixtures/binance-usdm-g10h-v1/report.expected.json
  - build/acceptance/g10h-parity-report.json
  - build/acceptance/g10h-pytest.xml
  - build/acceptance/g10h-import-boundary-report.json
failure_contracts:
  - frozen-crypt-gemini-snapshot-or-content-tree-identity-mismatch
  - unsafe-missing-duplicate-or-unexpected-parity-plan-path
  - source-role-pair-case-or-projection-identity-mismatch
  - parity-layer-order-is-missing-duplicated-or-reordered
  - pair-layer-coverage-is-missing-duplicated-or-silently-omitted
  - not-comparable-layer-is-treated-as-match-or-tolerance
  - comparable-layer-lacks-an-exact-path-local-rule
  - global-epsilon-or-unclassified-comparator-field
  - approved-change-lacks-intentional-mode-or-committed-adr
  - provider-trade-order-income-or-force-order-identity-is-collapsed
  - account-trade-and-income-history-are-double-booked
  - event-transaction-economic-capture-or-availability-time-is-substituted
  - account-update-balance-change-is-treated-as-total-fill-cash-delta
  - liquidation-and-adl-or-audit-and-execution-are-conflated
  - later-aggregate-match-hides-an-earlier-layer-divergence
  - comparator-mismatch-is-treated-as-tooling-failure-or-silently-passes-match
  - static-schema-example-claims-provider-history-completeness
  - parity-report-claims-decision-grade-live-or-deployment-authorization
  - parity-tool-imports-runtime-engine-provider-network-or-secret-state
allowed_grade: development
evidence:
  - frozen-crypt-gemini-source-snapshot-and-content-tree-hashes
  - official-account-trade-income-user-data-and-force-order-source-note
  - path-local-comparator-contract-hashes
  - explicit-layer-coverage-and-not-comparable-reasons
  - legacy-to-g10g-and-provider-record-to-g10g-comparison-reports
  - first-divergence-report-and-static-golden-hash
  - adr-backed-approved-change-evidence
  - import-boundary-report
  - static-type-report
  - dependency-lock-report
passed_commit: 468c91ad3fdbad221c959182f8751300f20a2424
artifact_hashes:
  tests/parity/contracts/binance-usdm-g10h-legacy-to-g10g-v1.json: sha256:6fed59076275ae9608c1f32976fe8a6c613976971713f53dc534184ec1da2dfb
  tests/parity/contracts/binance-usdm-g10h-provider-to-g10g-v1.json: sha256:5b54d27ce0c7abb3035f13a4acd60d3d8ea60f4d6100577940258f23cd3e9cd5
  tests/parity/fixtures/binance-usdm-g10h-v1/plan.json: sha256:24ae05535c68dc930e78d41da2bfd7c1596be5227cbee0b9d3dd79f953eb02c9
  tests/parity/fixtures/binance-usdm-g10h-v1/legacy.expected.json: sha256:c0e2eae246cafa2dfd9440470503ae6a364afbb62ce82ebd50a3d51b53dee65e
  tests/parity/fixtures/binance-usdm-g10h-v1/g10g.actual.json: sha256:6f35b75ccace175ca0c9dba0e6462bcc31a14b9a1332bc29ee0b5bc44870c0f3
  tests/parity/fixtures/binance-usdm-g10h-v1/provider.expected.json: sha256:e10437121a562180f6535e9043370a1a150ac29453843e384b10868683b0f291
  tests/parity/fixtures/binance-usdm-g10h-v1/report.expected.json: sha256:1c18dfd593dee26389453cc25c0e0fc0b6d1e0988bcd581c4048590b15f70335
  build/acceptance/g10h-parity-report.json: sha256:1c18dfd593dee26389453cc25c0e0fc0b6d1e0988bcd581c4048590b15f70335
  build/acceptance/g10h-pytest.xml: sha256:610c980c966b7a4501e319418984d7ecef8694c2eba1a88616db241a919c6f30
  build/acceptance/g10h-import-boundary-report.json: sha256:78b4760264f9ffdf1fb5cb206c847e98165f9593c5ea5eaba6859843b8e44499
```

### G10H Acceptance

1. G10H只拥有pure offline parity orchestration、canonical JSON validation、existing Comparator Contract v1调用与first-divergence aggregation；不得修改G10G经济语义、Generic Engine/Runner/Journal/Ledger/Profile、调用provider、读取secrets、执行legacy archive code、获取当前状态、补历史缺口或授权live/deployment；
2. Legacy source identity exact固定为Source ID `crypt-gemini`、Snapshot/archive SHA-256 `d6e6feca46b61586e890a441443738dc9e911a58428c940e86055459361eda80`、content-tree SHA-256 `704dee87020ad119e417fbec3831875f8203787ba06206f625a07e2414a068bb`与base commit `ba36e8a2b9ca1b1a949cf71cc93e175c9ef5e014`。Frozen dirty-worktree provenance不能替代archive/content identity；
3. Tool只消费caller-supplied immutable canonical projections和plan。Source roles exact为`LEGACY_CRYPT_GEMINI`、`G10G_DEVELOPMENT_RUN`、`BINANCE_ACCOUNT_RECORDS`；comparison pairs exact为`LEGACY_TO_G10G`后接`BINANCE_TO_G10G`，同role重复、缺失或case/source identity冲突fail closed；
4. Layer order exact为`SOURCE_IDENTITY`、`DECISION`、`ORDER_INTENT`、`ORDER_EVENT`、`FILL`、`FEE`、`POSITION_PNL`、`FUNDING`、`JOURNAL_LEDGER`、`MARGIN_SNAPSHOT`、`LIQUIDATION_AUDIT`、`LIQUIDATION_EXECUTION`、`FINAL_RESULT`。First divergence按pair order、layer order、Comparator rule/path order选择；晚期aggregate match不能覆盖早期mismatch；
5. 每个pair必须exact-cover全部13 layers，每层有且仅有一个coverage row。Coverage status exact为`COMPARABLE`、`NOT_COMPARABLE_LEGACY_SCOPE`、`NOT_COMPARABLE_PROVIDER_EVIDENCE`或`NOT_COMPARABLE_ARCHIVE_COMPLETENESS`，并保存非空reason与sorted immutable evidence refs；
6. 只有`COMPARABLE` layer进入Comparator。Not-comparable layer不得被省略、伪装为`MATCH`、zero/empty value、quantization或tolerance；有comparison rule的not-comparable layer和无rule的comparable layer均fail closed；
7. Existing `tools.migration.legacy_migration.parity` Comparator Contract v1保持唯一比较引擎。G10H不复制或扩展exact/sequence/quantized/explicit-tolerance/approved-change算法；全部input leaves必须被unique sorted non-overlapping path rule分类，global epsilon继续禁止；
8. `exact`用于identity、typed integer/string和canonical structure；`sequence`用于ordered records并报告首个不同index；`quantized`必须声明positive decimal quantum与rounding；`explicit_tolerance`必须逐path声明absolute/relative值。Tolerance不能用于source identity、provider IDs、event order、currency、side、position side、maker flag、reason/type或coverage；
9. `approved_change`只允许`intentional_semantic_change` mode并引用已提交`docs/adr/0001-g10h-legacy-binance-parity-boundary.md`。已批准v1 differences仅限legacy long-only vs open/reduce/flip、next-open full-fill vs matching-engine、fixed fee/slippage vs observed maker/taker fill economics、legacy normalized accounting/funding/margin shortcuts、conservative liquidation audit vs actual liquidation/ADL execution及operational vs canonical identity；
10. Legacy projection只冻结snapshot内真实可复核的Decision/action、OrderTrace、next-open full Fill、fixed fee/slippage、funding ledger、long Position/PnL和result reconciliation。它不得合成snapshot中不存在的partial fill、Short/flip、maker/taker、Binance order/trade IDs、account margin、force order、ADL或matching-engine truth；
11. Binance account-record projection的per-Fill identity exact为Account+Instrument/Symbol+Trade ID，并保留Order ID、side、position side、price、quantity、quote quantity、maker、commission、commission asset、realized PnL和trade time。Order ID不能折叠multiple fills，current commission rule不能重算或替代observed commission；
12. Income History保留income type、tranId、amount、asset、symbol和economic time，作为Funding/Commission/Realized PnL cash-flow cross-check；它不替代Account Trade fill authority。Linked Account Trade与Income rows只比较/reconcile一次，不能形成双重Journal effect；`INSURANCE_CLEAR`不得并入ordinary realized PnL；
13. `ORDER_TRADE_UPDATE`的event generation `E`、transaction/matching-engine `T`、order/trade time与capture/availability time保持分离；`ACCOUNT_UPDATE`只作为balance/position state observation。其`bc`不含PnL/commission，不能作为Fill总cash delta或替代Account Trade/Income fields；
14. User Force Orders exact区分`LIQUIDATION`与`ADL`并保留Order/client-order identity、status、price/average price、original/executed quantity、cumulative quote和times。Public liquidation stream不是完整user archive；G09G/G10G conservative bar-extreme audit只可比较detection window/classification，不可声称actual trigger/fill/bankruptcy/insurance parity；
15. Parity plan `schema_version=1` exact保存plan ID、three source refs、two pair refs、13-layer order、coverage rows、Comparator contract/expected/actual repo-relative paths、migration modes、expected pair verdicts、`decision_grade_eligible=false`和`deployment_authorized=false`。所有path必须normalized repo-relative、存在、不可absolute/`..`/symlink escape；
16. Pair verdict沿existing Comparator为`MATCH`、`MISMATCH`或`APPROVED_CHANGE`。Composite report另保存coverage completeness；若无comparable layer则pair为`NOT_COMPARABLE`。Composite `comparison_verdict` precedence exact为`MISMATCH`→`APPROVED_CHANGE`→`NOT_COMPARABLE`→`MATCH`，但完整per-layer coverage不能被single verdict替代；
17. Tooling completion与economic verdict分离：completed `MISMATCH`或`APPROVED_CHANGE`必须生成canonical report并以CLI exit 0结束；invalid plan/contract/source/coverage或blocked comparator非零。Optional `--require-match`只在所有pair `MATCH`且coverage complete时exit 0，否则非零；Acceptance不用该flag；
18. Composite report exact保存schema/version、plan/contract/projection hashes、source manifest、pair reports、all coverage rows、comparison counts、first divergence、limitations、`decision_grade_eligible=false`、`deployment_authorized=false`与non-recursive report hash。相同bytes在不同filesystem root重复运行必须exact相同；wall clock、absolute path、PID、hostname、Attempt ID或runtime address不得进入report；
19. Frozen provider fixture只可使用pseudonymous/static first-party-schema example records来验证field preservation、linking与first divergence。它必须显式`NOT_COMPARABLE_ARCHIVE_COMPLETENESS`，不能声称真实account history、all pages、initial state或provider completeness；G12 artifacts缺失时G10H永远不能升级decision-grade eligibility；
20. Failure precedence exact为：`INVALID_PLAN`→`UNSAFE_PATH`→`SOURCE_SNAPSHOT_MISMATCH`→`SOURCE_ROLE_MISMATCH`→`PAIR_IDENTITY_MISMATCH`→`LAYER_ORDER_MISMATCH`→`COVERAGE_MISMATCH`→`NOT_COMPARABLE_RULE_CONFLICT`→`COMPARABLE_RULE_MISSING`→`PROVIDER_IDENTITY_CONFLICT`→`COMPARATOR_BLOCKED`→`EXPECTED_VERDICT_MISMATCH`。多缺陷只报告第一项；
21. Production package purity保持不变。Parity tool可import stdlib及existing `tools.migration.legacy_migration.parity/snapshots`，但不得import `crypto_quant_backtest` Engine/Runner、concrete Profile implementation、provider SDK、network/filesystem acquisition、database/cloud/process/dynamic import或mutable global state；G10G projection由tests/support提前产生canonical fixture，tool不在运行时执行Backtest；
22. G10H通过只证明frozen source/projection/coverage/contracts/report的可重复性与first-divergence truth。所有output固定development、`decision_grade_eligible=false`、`deployment_authorized=false`；matching-engine、queue/partial-fill realism、historical archive completeness、real liquidation/ADL/bankruptcy/insurance fund与live仍明确unsupported。

Primary-source and parity boundary：`docs/research/binance-usdm-parity-primary-sources.md`。

Readiness baseline：

```text
G10G frozen acceptance command                                     131 passed
Full test suite                                                    1101 passed
Workspace import boundary                                           PASS (80 files)
mypy 2.3.0                                                           no issues (80 source files)
Primary LSP + scoped pi-lens                                         no blocking errors
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
G10G frozen acceptance command                                     131 passed
Full test suite                                                    1101 passed
Workspace import boundary                                           PASS (80 files)
mypy 2.3.0                                                           no issues (80 source files)
Primary LSP                                                          no diagnostics (6 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no new findings; 8 pre-existing Protocol ellipsis warnings
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Acceptance validation：

```text
G10H frozen acceptance command                                      33 passed
Composite parity report                                    APPROVED_CHANGE
Legacy → G10G                                           APPROVED_CHANGE (11)
Provider record → G10G                                             MATCH (8)
Coverage complete                                                    false
First divergence                                      LEGACY_TO_G10G / DECISION
Full test suite                                                    1108 passed
Workspace import boundary                                           PASS (80 files)
mypy 2.3.0                                                           no issues (82 source files)
Primary LSP                                                          clean (5 files)
pi-lens scoped review                                                no blocking errors; 3 non-blocking quality warnings
Static golden/root independence                                      PASS
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Implementation commit：`468c91ad3fdbad221c959182f8751300f20a2424`。

## 85. G11A ObservationView Capability Isolation Acceptance Card

```yaml
id: G11A
status: PASSED
depends_on:
  - G07
  - WP-06A
owner_package: backtest-runtime observations
public_interface:
  - crypto_quant_backtest.ObservationPurposeRef
  - crypto_quant_backtest.ObservationQuery
  - crypto_quant_backtest.ObservationRecord
  - crypto_quant_backtest.ObservationQueryFailureCode
  - crypto_quant_backtest.ObservationQueryFailure
  - crypto_quant_backtest.ObservationQueryResult
  - crypto_quant_backtest.ObservationQueryOutcome
  - crypto_quant_backtest.ObservationView
test_commands:
  readiness: uv run pytest -q tests/parity/test_binance_usdm_parity.py tests/parity/test_binance_usdm_parity_golden.py tests/parity/test_comparator_contract.py tests/parity/test_source_snapshots.py tests/runtime/engine/test_g10g_binance_usdm_journey.py tests/runtime/engine/test_g10g_binance_usdm_golden.py tests/runtime/runner/test_g10g_binance_usdm_runner.py tests/architecture/test_g10h_parity_boundary.py tests/architecture/test_g10g_binance_composition_boundary.py tests/architecture/test_repository_cleanliness.py
  contract: uv run pytest -q tests/runtime/observations/test_observation_view.py
  fixture: uv run pytest -q tests/runtime/observations/test_observation_view_golden.py
  boundary: uv run pytest -q tests/architecture/test_g11a_observation_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  acceptance: uv run pytest -q tests/runtime/observations/test_observation_view.py tests/runtime/observations/test_observation_view_golden.py tests/market_data/bundles/test_market_bundle_reader.py tests/market_data/bundles/test_market_bundle_reader_golden.py tests/runtime/timeline/test_deterministic_timeline.py tests/architecture/test_g11a_observation_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g11a-pytest.xml
fixture_ids:
  - observation-view-capability-isolation-v1
expected_artifacts:
  - docs/research/g11a-observation-view-capability-isolation.md
  - tests/fixtures/runtime/observations/observation-view-capability-isolation-v1.json
  - build/acceptance/g11a-pytest.xml
  - build/acceptance/g11a-import-boundary-report.json
failure_contracts:
  - dataset-is-not-authorized
  - instrument-is-not-authorized-for-dataset
  - purpose-is-not-authorized-for-dataset-and-instrument
  - exact-market-bundle-capability-is-not-authorized
  - unauthorized-backing-record-is-returned-or-affects-view-result-identity
  - shared-source-event-implicitly-substitutes-an-ungranted-purpose
  - duplicate-authorized-record-identity-conflicts
  - input-order-changes-view-or-result-identity
  - authorized-empty-result-is-misclassified-as-coverage-failure
  - bundle-reader-manifest-cursor-ledger-account-or-clock-is-exposed
  - callback-implementation-module-path-runtime-address-or-wall-clock-enters-identity
  - g11a-performs-unfrozen-revision-universe-window-resample-or-schedule-semantics
  - development-view-claims-point-in-time-decision-grade-or-deployment-authorization
allowed_grade: development
evidence:
  - readiness-contract-tests
  - exact-query-capability-and-failure-precedence-tests
  - hidden-record-noninterference-and-cross-purpose-isolation-tests
  - deterministic-static-golden-hash
  - public-api-import-report
  - import-boundary-report
  - static-type-report
  - dependency-lock-report
passed_commit: 72fe31f5b10d785340b11ca0fd3d0fec8c1c4a34
artifact_hashes:
  tests/fixtures/runtime/observations/observation-view-capability-isolation-v1.json: sha256:7bcea67e6c5eb9fd023411e30b5980c007c4722a3835b5808d9c9b43c50c9978
  build/acceptance/g11a-pytest.xml: sha256:c27e60ee276e53691bc251e9ce48690ba15b4c6e254b4019431c5656d61cdacb
  build/acceptance/g11a-import-boundary-report.json: sha256:638223017e9fcec58200226a92610dc39dd20a59d443e4a733f2ecf919aef6cd
```

### G11A Acceptance

1. G11A只拥有single production module `crypto_quant_backtest.observations`及root exports。它是pure in-memory Strategy-facing read seam，只消费caller-supplied immutable query allowlist与`MarketEvent` records；不得读取MarketBundle/Reader/Manifest/Cursor、filesystem、network、database、process、environment、wall clock、Ledger、Snapshot、Account或Strategy implementation；
2. `ObservationPurposeRef` exact保存canonical nonempty key与positive integral version。Purpose是独立semantic identity，不等于Event type、stream key、PricePurpose fallback或payload field；canonical dict/hash固定schema version 1；
3. `ObservationQuery` exact声明nonempty `dataset_key`、stable `InstrumentId`、`ObservationPurposeRef`与exact `MarketBundleCapability` key/version。Query不包含callback、predicate、arbitrary callable、Reader、path、current time、Decision Time、Attempt ID或runtime address；query hash由完整selector确定；
4. `ObservationRecord`只包装一个existing immutable `MarketEvent`与一个explicit Purpose。Record dataset exact来自`event.stream_key`，Instrument exact来自non-None `event.instrument_id`，capability exact来自`event.capability`；G11A不解析payload来猜dataset/Instrument/purpose/capability，也不接受Instrument-less global record；
5. `ObservationView` constructor接收iterable allowed queries与records，立即冻结、canonical sort并只保留exact selector出现在allowlist中的records。Public interface exact只有`view_hash`与`query(query)`；不得返回或暴露backing records/allowlist、Reader、Bundle Ref/Manifest、Cursor或mutable cache；
6. Unauthorized backing records在construction时被discard：不能进入view state、不能影响`view_hash`、不能出现在authorized result，也不能改变authorized result/outcome hash。Adding/reordering any unauthorized record must produce exact same view/query result bytes；
7. G11A v1不实现result cache。Authorized query对retained immutable tuple做deterministic linear scan；未来cache只有在profiling需要时才可private加入，且必须在authorization后按exact query hash读取/写入，不能改变visibility、ordering、canonical bytes或hash；
8. Authorization只检查allowlist，且failure precedence exact为`DATASET_NOT_AUTHORIZED` → `INSTRUMENT_NOT_AUTHORIZED` → `PURPOSE_NOT_AUTHORIZED` → `CAPABILITY_NOT_AUTHORIZED`。Failure不能根据hidden record existence改变code或message；多缺陷只返回第一项；
9. Exact authorized query即使没有matching records也成功返回empty tuple。G11A不得把empty解释为No Session、Suspended、No Trades、Missing、Source Outage、window coverage failure或revision gap；G11C/G11D/G12拥有这些语义；
10. Matching result只包含dataset、Instrument、Purpose和capability四项全部exact相等的records。Capability key相同/version不同不fallback；相邻dataset、same Instrument/different purpose、same purpose/different Instrument均不可替代；
11. 同一`MarketEvent`只有通过separate explicit `ObservationRecord`才能服务多个Purpose，且每个Purpose必须有separate authorized query。Shared source row、payload shape或Event type不能自动授权cross-purpose reuse；
12. Record canonical identity exact为Purpose identity+Event ID；authorized duplicate identity with exact canonical content collapses为一个record，same identity/different content constructor fail closed。Unauthorized conflicting duplicates被discard且不能影响view identity；
13. Retained result order固定为MarketEvent `ordering_key`后接Event ID、Revision ID与record hash稳定tie-break。Allowed-query/record input order、Mapping order或duplicate exact inputs不能改变view/result/outcome hash；
14. `ObservationQueryResult` exact保存view hash、Query与ordered `MarketEvent` tuple；`ObservationQueryFailure` exact保存view hash、Query与failure code；`ObservationQueryOutcome`必须result xor failure，并保存canonical outcome hash。Constructor重算derived hashes并拒绝forged result/failure context；
15. Strategy-facing result可以看到matching Event payload与既有event/available/revision/source provenance，但看不到其他records或container internals。No `to_canonical_dict()`/manifest accessor on `ObservationView` may serialize hidden state to Strategy；only result/failure values are canonical artifacts；
16. G11A不接收Decision/Simulation Instant，不执行`available_time <= decision_time`、latest revision selection、supersession resolution或causality trace。它因此不能单独满足完整point-in-time Observation View；G11B必须在Strategy invocation前补齐这些规则；
17. G11A不拥有Universe membership/listing/delisting/StaticUniverse（G11C）、BarDefinition/window/lookback/resample（G11D）、DecisionSchedule/Warmup（G11E）、StrategyState/RNG/Model（G11F–H）、Strategy invocation/DecisionBatch（G11I）或downstream parity（G11J）。Engine/Runner/Timeline/TargetStream/Journal/Ledger/Profile保持不变；
18. Python ambient-library sandbox不属于G11A。Frozen guarantee是Strategy-facing interface不给出filesystem/network/process/clock对象，且production module/static fixture无这些imports/handles；arbitrary Strategy artifact qualification留给G11I/build gates，不能由G11A虚假声明；
19. Static golden至少冻结：two Instruments、two datasets、two purposes、two capability versions；all four authorization failures及precedence；authorized empty；same-event explicit multi-purpose；hidden unauthorized record addition/order noninterference；authorized exact duplicate collapse/conflict；record/query input-order parity；view/query/result/failure/outcome hashes；public interface non-exposure与forgery controls；
20. Production import allowlist仅stdlib、`crypto_quant_domain`与`crypto_quant_market_data` public contracts。Module不得import Builder、Trading Kernel、Engine/Runner/Timeline/TargetStream、provider SDK、network/filesystem/process/database/cloud/dynamic import。G11A outputs固定development-only，且不拥有`decision_grade_eligible`或`deployment_authorized`升级权。

Frozen seam note：`docs/research/g11a-observation-view-capability-isolation.md`。

Readiness baseline：

```text
G10H frozen acceptance command                                      33 passed
Full test suite                                                    1108 passed
Workspace import boundary                                           PASS (80 files)
mypy 2.3.0                                                           no issues (82 source files)
Primary LSP                                                          clean
pi-lens scoped review                                                no blocking errors
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
G10H frozen acceptance command                                      33 passed
Full test suite                                                    1108 passed
Workspace import boundary                                           PASS (80 files)
mypy 2.3.0                                                           no issues (82 source files)
Primary LSP                                                          no diagnostics (5 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no new findings; 8 pre-existing Protocol ellipsis warnings
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Acceptance validation：

```text
G11A frozen acceptance command                                      34 passed
ObservationView public-seam tests                                   12 passed
Full test suite                                                    1120 passed
Workspace import boundary                                           PASS (81 files)
mypy 2.3.0                                                           no issues (83 source files)
Primary LSP                                                          clean (6 files)
pi-lens scoped review                                                no findings across 6 changed files
Static golden/input-order/hidden-record controls                     PASS
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Implementation commit：`72fe31f5b10d785340b11ca0fd3d0fec8c1c4a34`。

## 86. G11B Point-in-time Revision Selection and Causality Acceptance Card

```yaml
id: G11B
status: PASSED
depends_on:
  - G11A
owner_package: backtest-runtime observations
public_interface:
  - crypto_quant_backtest.RevisionedObservationRecord
  - crypto_quant_backtest.ObservationCausalityFailureCode
  - crypto_quant_backtest.ObservationCausalityFailure
  - crypto_quant_backtest.ObservationCausalityTrace
  - crypto_quant_backtest.PointInTimeObservationQueryResult
  - crypto_quant_backtest.PointInTimeObservationQueryOutcome
  - crypto_quant_backtest.PointInTimeObservationView
test_commands:
  readiness: uv run pytest -q tests/runtime/observations/test_observation_view.py tests/runtime/observations/test_observation_view_golden.py tests/market_data/bundles/test_market_bundle_reader.py tests/market_data/bundles/test_market_bundle_reader_golden.py tests/runtime/timeline/test_deterministic_timeline.py tests/architecture/test_g11a_observation_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  contract: uv run pytest -q tests/runtime/observations/test_point_in_time_observation_view.py
  fixture: uv run pytest -q tests/runtime/observations/test_point_in_time_observation_view_golden.py
  boundary: uv run pytest -q tests/architecture/test_g11b_observation_causality_boundary.py tests/architecture/test_g11a_observation_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  acceptance: uv run pytest -q tests/runtime/observations/test_point_in_time_observation_view.py tests/runtime/observations/test_point_in_time_observation_view_golden.py tests/runtime/observations/test_observation_view.py tests/runtime/observations/test_observation_view_golden.py tests/market_data/bundles/test_market_bundle_reader.py tests/market_data/bundles/test_market_bundle_reader_golden.py tests/runtime/timeline/test_deterministic_timeline.py tests/architecture/test_g11b_observation_causality_boundary.py tests/architecture/test_g11a_observation_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g11b-pytest.xml
fixture_ids:
  - observation-revision-causality-v1
expected_artifacts:
  - docs/research/g11b-observation-revision-causality.md
  - tests/fixtures/runtime/observations/observation-revision-causality-v1.json
  - build/acceptance/g11b-pytest.xml
  - build/acceptance/g11b-import-boundary-report.json
failure_contracts:
  - unauthorized-query-inspects-or-leaks-revision-evidence
  - utc-only-cutoff-exposes-a-later-same-time-phase-or-sequence
  - future-record-or-conflict-affects-a-prior-view-or-result-identity
  - event-id-revision-id-time-payload-or-input-position-is-used-as-observation-lineage
  - same-observation-revision-identity-has-conflicting-content
  - visible-revision-parent-is-missing
  - visible-revision-chain-forks-cycles-has-multiple-roots-or-terminals
  - revision-chain-query-event-type-or-event-time-context-changes
  - child-revision-availability-does-not-strictly-follow-parent
  - latest-visible-terminal-revision-is-not-selected
  - source-revision-id-reuse-across-independent-observations-is-rejected
  - selected-result-contains-future-wrong-context-duplicate-or-noncanonical-event
  - causality-trace-maxima-revision-source-or-dataset-hash-does-not-match-result
  - empty-authorized-result-is-misclassified-as-coverage-failure
  - input-order-exact-duplicate-hidden-or-future-record-changes-canonical-output
  - g11a-canonical-artifact-or-authorization-precedence-regresses
  - backing-revisions-decision-instant-reader-timeline-ledger-account-or-cache-is-exposed
  - g11b-performs-universe-window-gap-resample-schedule-strategy-or-bundle-semantics
  - point-in-time-view-claims-decision-grade-live-or-deployment-authorization
allowed_grade: development
evidence:
  - readiness-contract-tests
  - full-simulation-instant-visibility-tests
  - future-and-unauthorized-noninterference-tests
  - revision-lineage-selection-and-failure-precedence-tests
  - causality-trace-maxima-revision-source-and-dataset-hashes
  - deterministic-static-golden-hash
  - g11a-backward-compatibility-report
  - public-api-import-report
  - import-boundary-report
  - static-type-report
  - dependency-lock-report
passed_commit: c40de40a8e9117b95f3155ac2ebd5d3b4c7a95c8
artifact_hashes:
  tests/fixtures/runtime/observations/observation-revision-causality-v1.json: sha256:f5642321dcc1d61b485d17d32dddd6ed0eb2155ea23946edf663a4b0ddce18de
  build/acceptance/g11b-pytest.xml: sha256:4b977cf6708e8bd670ad1bafb1cfac33495cc22e9bdfa52aec1afe39f4a010c9
  build/acceptance/g11b-import-boundary-report.json: sha256:638223017e9fcec58200226a92610dc39dd20a59d443e4a733f2ecf919aef6cd
```

### G11B Acceptance

1. G11B只deepens existing single production module `crypto_quant_backtest.observations`与root exports，保持pure in-memory Strategy-facing read seam且只消费caller-supplied immutable values；G11A public classes、constructor behavior、canonical bytes/hashes、authorization outcomes与static golden必须exact unchanged；
2. `RevisionedObservationRecord` exact保存canonical nonempty `observation_key`与one exact G11A `ObservationRecord`。Observation key是在one exact Query内跨修订稳定的logical fact identity；Event ID仍是immutable version-record identity，Revision ID仍是source/provider revision provenance。G11B不得从Event ID、Revision ID、event time、payload、source hash或input order猜observation key；
3. `PointInTimeObservationView` constructor exact只接收`allowed_queries`、`RevisionedObservationRecord` iterable和one `decision_instant: SimulationInstant`。Public interface exact只有`view_hash`与`query(ObservationQuery)`；不得暴露decision instant、allowlist、backing/superseded revisions、Bundle/Reader/Manifest/Cursor、Timeline、clock、Ledger/Snapshot/Account、cache或runtime object；
4. Construction processing order exact为：先按G11A exact query allowlist discard unauthorized records；再discard `record.event.timeline_instant > decision_instant`的future records；最后canonical deduplicate/freeze visible authorized revision records。Unauthorized或future conflict不能阻断、更改或泄露past view/result；
5. Visibility必须使用full `SimulationInstant` total order `(UtcInstant, TimelinePhase, SourceSequence)`。只比较`available_time` UTC或`event_time`不合格；same UTC但later phase/source sequence对当前Decision仍是future；
6. `PointInTimeObservationView.view_hash` exact绑定schema/model identity、decision instant、canonical allowlist与visible authorized revision records。Adding/reordering unauthorized records、future records或future exact/conflicting revisions必须产生相同past view/result/trace/outcome bytes和hash；later correction不得retroactively rewrite earlier DecisionContext；
7. Revision version identity exact为`(ObservationQuery, observation_key, MarketEvent.revision_id)`。Exact duplicate canonical records collapse；same identity/different record content produces`REVISION_ID_CONFLICT`。Independent observation keys允许复用同一个source Revision ID，不能被误判为冲突；
8. Revision selection independent按exact `(ObservationQuery, observation_key)` lineage执行。每个visible legal lineage exact有one root (`supersedes_revision_id=None`)、unique revision IDs、每个child引用same lineage existing visible parent、no fork/cycle/disconnected second root、one terminal；
9. Lineage内Query selector、Event type与Event Time必须exact stable。Instrument/dataset/purpose/capability fallback或correction改变economic fact time产生`REVISION_CONTEXT_MISMATCH`；G11B不解析payload决定lineage/context；
10. Child `MarketEvent.timeline_instant`必须strictly greater than parent。Same UTC可由later phase/sequence形成合法later revision；equal/earlier full instant产生`REVISION_AVAILABILITY_REGRESSION`。Available predecessor不能因future child存在而停止被选择；
11. 成功selection exact返回每个visible legal lineage的unique terminal revision。Before correction availability返回predecessor；at/after exact correction Simulation Instant返回correction。Superseded versions保持immutable trace evidence但不向Strategy暴露payload；
12. G11A authorization failure precedence exact保持`DATASET_NOT_AUTHORIZED`→`INSTRUMENT_NOT_AUTHORIZED`→`PURPOSE_NOT_AUTHORIZED`→`CAPABILITY_NOT_AUTHORIZED`，且在检查revision evidence前返回existing `ObservationQueryFailure`。Unauthorized query不能因hidden/future/malformed lineage改变failure code/hash或泄露candidate identity；
13. Authorized query causality failure precedence exact为`REVISION_ID_CONFLICT`→`REVISION_PARENT_MISSING`→`REVISION_CHAIN_CONFLICT`→`REVISION_CONTEXT_MISMATCH`→`REVISION_AVAILABILITY_REGRESSION`。`ObservationCausalityFailure` exact保存point-in-time view hash、Query、decision instant、code及sorted observation keys/revision IDs/candidate record hashes；多缺陷只返回第一项；
14. Exact authorized query没有visible record时成功返回empty events与empty causality trace。G11B不得把empty解释为No Session、Suspended、No Trades、Missing、Source Outage、Universe exclusion、window/lookback gap或decision-grade coverage；
15. `ObservationCausalityTrace` exact保存view hash、Query、decision instant、sorted all-visible candidate record hashes、由其派生的revision-set hash、selected observation keys/Event hashes/Revision IDs/source hashes、selected dataset hash、max event time、max available `SimulationInstant`、event count与trace hash；
16. Candidate record hashes只覆盖该authorized Query在decision instant可见的revision evidence；不得包含其他Query、unauthorized或future records。Selected tuple fields与returned Event canonical order逐项align；dataset hash exact由Query、selected observation keys和selected Event canonical values派生，不从Manifest/current file或payload shortcut读取；
17. `PointInTimeObservationQueryResult` exact保存view hash、Query、decision instant、canonical selected `MarketEvent` tuple与matching trace。Constructor验证event context、unique Event IDs、canonical order、`timeline_instant <= decision_instant`、trace selected fields/maxima/count/dataset hash；`dataclasses.replace`伪造future/wrong trace/result context fail closed；
18. `PointInTimeObservationQueryOutcome`必须result xor failure；failure union exact只允许existing `ObservationQueryFailure`或G11B `ObservationCausalityFailure`。Outcome/result/failure/trace全部schema version 1并使用non-recursive canonical hashes；
19. Selected event order沿G11A convention固定为MarketEvent `ordering_key`后接Event ID、Revision ID与stable record/hash tie-break。Allowed-query/record/lineage input order、Mapping order和exact duplicates不能改变view/result/trace/failure/outcome identity；
20. Static golden至少冻结：two observation keys sharing source Revision ID；v1→v2 correction before/at exact same-UTC later phase cutoff；independent unchanged record；unauthorized and future conflicting revisions noninterference；all four authorization failures；all five causality failures and precedence；empty success；trace candidate/selected hashes、revision/source IDs、dataset hash、maxima；input-order/repeat parity与forgery controls；
21. G11B v1不实现cache。Query可对visible immutable tuple做deterministic linear grouping/selection；未来private cache only after measured need，按exact view/query identity工作且不能扩大visibility、改变failure precedence或canonical output；
22. G11B不拥有MarketBundle read/acquisition、revision completeness/gap validation（G12）、Universe/listing/membership（G11C）、BarDefinition/window/lookback/resample（G11D）、DecisionSchedule/Warmup（G11E）、StrategyState/RNG/Model（G11F–H）、Strategy invocation/aggregate audit/DecisionBatch（G11I）或parity（G11J）。Engine/Runner/Timeline/TargetStream/Journal/Ledger/Profile保持不变；
23. Production import allowlist仍仅stdlib、`crypto_quant_domain`与`crypto_quant_market_data` public contracts。Module不得import Builder、Trading Kernel、Engine/Runner/Timeline/TargetStream、provider SDK、filesystem/network/process/database/cloud/environment/dynamic import/wall clock。All outputs固定development-only，G12 completeness与later invocation qualification前不得声明decision-grade/live/deployment authorization。

Frozen seam note：`docs/research/g11b-observation-revision-causality.md`。

Readiness baseline：

```text
G11A frozen acceptance command                                      34 passed
ObservationView public-seam tests                                   12 passed
Full test suite                                                    1120 passed
Workspace import boundary                                           PASS (81 files)
mypy 2.3.0                                                           no issues (83 source files)
Primary LSP                                                          clean
pi-lens scoped review                                                no blocking errors
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
G11A frozen acceptance command                                      34 passed
Full test suite                                                    1120 passed
Workspace import boundary                                           PASS (81 files)
mypy 2.3.0                                                           no issues (83 source files)
Primary LSP                                                          no diagnostics (5 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no new findings; 8 pre-existing Protocol ellipsis warnings
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Acceptance validation：

```text
G11B frozen acceptance command                                      51 passed
Point-in-time observation contract/golden/boundary                  17 passed
Full test suite                                                    1137 passed
Workspace import boundary                                           PASS (81 files)
mypy 2.3.0                                                           no issues (81 package source files)
Primary LSP                                                          clean (6 files)
pi-lens scoped review                                                no findings across 6 changed files
Static golden/revision/failure/forgery controls                      PASS
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Implementation commit：`c40de40a8e9117b95f3155ac2ebd5d3b4c7a95c8`。

## 87. G11F Strategy State and Checkpoint Acceptance Card

```yaml
id: G11F
status: PASSED
depends_on:
  - G02
owner_package: backtest-runtime strategy
public_interface:
  - crypto_quant_backtest.StrategyState
  - crypto_quant_backtest.StrategyStateTransition
  - crypto_quant_backtest.StrategyCheckpoint
test_commands:
  readiness: uv run pytest -q tests/domain/canonical tests/domain/decisions tests/domain/artifacts tests/domain/time tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  contract: uv run pytest -q tests/runtime/strategy_state/test_strategy_state.py
  fixture: uv run pytest -q tests/runtime/strategy_state/test_strategy_state_golden.py
  boundary: uv run pytest -q tests/architecture/test_g11f_strategy_state_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  acceptance: uv run pytest -q tests/runtime/strategy_state/test_strategy_state.py tests/runtime/strategy_state/test_strategy_state_golden.py tests/domain/canonical tests/domain/decisions tests/domain/time tests/architecture/test_g11f_strategy_state_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g11f-pytest.xml
fixture_ids:
  - strategy-state-checkpoint-v1
expected_artifacts:
  - docs/research/g11f-strategy-state-checkpoint.md
  - tests/fixtures/runtime/strategy-state/strategy-state-checkpoint-v1.json
  - build/acceptance/g11f-pytest.xml
  - build/acceptance/g11f-import-boundary-report.json
failure_contracts:
  - strategy-state-accepts-noncanonical-or-hidden-runtime-value
  - caller-container-mutation-changes-frozen-state
  - equal-state-hash-exposes-different-mapping-iteration-order
  - strategy-or-state-schema-is-implicit-or-omitted-from-identity
  - transition-crosses-strategy-or-schema-without-explicit-migration
  - transition-before-or-after-hash-does-not-match-state
  - checkpoint-uses-utc-only-or-wall-clock-capture-identity
  - checkpoint-hash-does-not-bind-full-canonical-state
  - restore-returns-mutable-or-different-state
  - continuation-after-restore-diverges-from-uninterrupted-continuation
  - financial-account-inventory-rng-model-or-engine-state-becomes-g11f-authority
  - filesystem-network-process-database-cache-or-callback-enters-state-seam
  - g11f-mutates-engine-runner-timeline-target-stream-or-domain-contracts
  - g11f-claims-engine-checkpoint-decision-grade-live-or-deployment-authority
allowed_grade: development
evidence:
  - canonical-json-state-contract-tests
  - deep-immutability-and-input-order-parity-tests
  - before-after-transition-hash-tests
  - full-simulation-instant-checkpoint-tests
  - continuation-after-restore-static-golden
  - constructor-forgery-controls
  - public-api-import-report
  - import-boundary-report
  - static-type-report
  - dependency-lock-report
passed_commit: af2897e11fedf3c0807e0f60435be9e700269c03
artifact_hashes:
  tests/fixtures/runtime/strategy-state/strategy-state-checkpoint-v1.json: sha256:11154be924005081b65dd4d0433e3dcde9c4e4ad94e6e3bb9310a151a18d1911
  build/acceptance/g11f-pytest.xml: sha256:5053b7560b0e95883074f2c6bc99597dd22964890bb947a6131d9c573bcc5089
  build/acceptance/g11f-import-boundary-report.json: sha256:d8c1dd51b7b852547a9df0e73804729b614219742ecd9d598a2633771e4f4835
```

### G11F Acceptance

1. G11F只新增one production module `crypto_quant_backtest.strategy_state`与root exports，保持pure in-memory、provider-neutral、Strategy-owned value seam。它只消费caller-supplied immutable/canonical Domain values，不读取Observation、Bundle、Profile、filesystem、network、database、process、environment、wall clock、Ledger、Account、Engine或Strategy callback；
2. `StrategyState` exact保存`strategy_id: StrategySleeveId`、`state_schema: CanonicalSchema`与`values: Mapping[str, CanonicalJsonValue]`。State没有Attempt ID、runtime address、module path、implementation object、callback、path、current time或mutable store handle；
3. `CanonicalJsonValue` v1 exact只允许`None`、bool、int、NFC str、string-keyed Mapping及ordered list/tuple递归组合。float、Decimal、date/datetime、bytes、set/frozenset、callable、file/socket/process/database/client object、arbitrary `to_canonical_dict()` object、cycle及unsupported runtime value全部fail closed；
4. Every Mapping key必须canonical nonempty trimmed NFC string。Constructor立即deep-freeze：Mapping变只读mapping、list/tuple变tuple，并在每一层按key排序后暴露。Caller后续mutate原始容器不能改变State；相同canonical values必须具有相同mapping iteration order、canonical bytes与hash；
5. `StrategyState` canonical body exact为`{type="strategy_state",schema_version=1,strategy_id,state_schema,values}`，其中identity values分别使用existing Domain canonical dict。`state_hash=canonical_sha256(body)`且`to_canonical_dict()`只追加non-recursive `state_hash`；schema name/version与Strategy identity必须进入hash；
6. State schema升级/迁移不属于G11F v1。不同schema name/version产生不同State identity；G11F不提供fallback、default schema、migration registry、plugin、serializer registry或current-version lookup；
7. `StrategyStateTransition` exact保存canonical nonempty `transition_key`、`occurred_at: SimulationInstant`及exact before/after `StrategyState`。Before/after必须属于same Strategy与same exact state schema；cross-Strategy或implicit schema migration fail closed；
8. Transition canonical body exact为`{type="strategy_state_transition",schema_version=1,transition_key,occurred_at,strategy_id,state_schema,before_state_hash,after_state_hash}`。Before/after hashes只能从embedded State派生，不能由caller伪造；`transition_hash`由该body派生且non-recursive；
9. Transition不调用Strategy、不解释fields、不判断change是否经济合理，也不拥有Observation、Target、Decision、Schedule、RNG或Model semantics。No-op transition允许且仍由transition key/instant/identities形成deterministic evidence；
10. `StrategyCheckpoint` exact保存canonical nonempty `checkpoint_key`、`captured_at: SimulationInstant`及one exact `StrategyState`。Capture instant使用full `(UtcInstant,TimelinePhase,SourceSequence)` total order；不得降级为UTC-only、event time、wall-clock time或Attempt time；
11. Checkpoint canonical body exact为`{type="strategy_checkpoint",schema_version=1,checkpoint_key,captured_at,state}`，其中state使用包含state hash的canonical dict。`checkpoint_hash=canonical_sha256(body)`且无caller-supplied digest。相同canonical input/order产生exact same hash；phase/sequence、state/schema或key改变必须改变identity；
12. `StrategyCheckpoint.restore()`无参数并返回checkpoint内exact immutable `StrategyState`。不得访问外部store、Reader、file、network、clock、Journal/Event log或cache，不得构造新的默认State或静默升级schema；
13. Continuation golden exact证明external pure step的`S0→S1→S2`与`S0→S1→checkpoint→restore(S1)→S2`产生same final State canonical bytes/hash。该fixture只验证Strategy business-state continuation，不声称Order/Journal/Ledger/Runner execution parity；
14. Constructor与`dataclasses.replace`必须重新验证nested canonical values、Strategy/schema alignment与exact derived hashes。Unsupported values、mutated/wrong identity transition、forged checkpoint/state context均fail closed；derived hash properties不接受caller input；
15. StrategyState可以保存Strategy自身影响未来决策的业务字段与later G11H explicit model-revision identity，但不得成为Cash、NAV、Margin、Position、Working Order、Ledger、Journal、Reservation、Settlement或Liquidity Inventory的第二权威来源；这些财务值仍来自PortfolioSnapshot/Kernel authorities；
16. RandomStream algorithm/counter/checkpoint由G11G单独拥有，不嵌入G11F generic checkpoint identity。DecisionSchedule/Warmup由G11E拥有，Model lookup/revision switching由G11H拥有，Strategy invocation/aggregate audit/DecisionBatch由G11I拥有；
17. Rebuildable performance cache留在State外；若某cache内容会影响未来Decision，它就是business state，必须作为canonical values显式进入State。G11F v1不实现mutable cache、memoization、global registry或external persistence；
18. Public API boundary、import architecture与static source tests必须证明production module只依赖stdlib immutable/JSON support与`crypto_quant_domain` public contracts；Engine、Runner、Timeline、TargetStream、Observation、Trading Kernel及provider modules保持无G11F branch；
19. Static golden至少冻结nested Mapping/list deep freeze、input/mapping-order parity、schema/Strategy isolation、unsupported/cyclic value failures、before/after transition hashes、same-UTC different phase/sequence checkpoint identity、restore parity、continuation parity、repeat parity及forgery controls；
20. G11F outputs固定development-only。它不创建EngineCheckpoint、child Attempt、resume cursor、artifact publication、decision-grade eligibility、live trading或deployment authorization。

Frozen seam note：`docs/research/g11f-strategy-state-checkpoint.md`。

Readiness baseline：

```text
G02 canonical/decision/artifact/time readiness command               48 passed
Workspace import boundary                                           PASS (81 files)
mypy 2.3.0                                                           no issues (81 package source files)
Primary LSP                                                          no diagnostics (2 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no findings across 3 planning/research files
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
Frozen readiness command                                             48 passed
Workspace import boundary                                           PASS (81 files)
mypy 2.3.0                                                           no issues (81 package source files)
Primary LSP                                                          no diagnostics (2 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no findings across 3 planning/research files
Research note hash                                                   sha256:d4f859cc767d8a8c89b78c94e3236e3abf080be99108777fbd8b88408c7ac4a5
Import boundary report hash                                          sha256:638223017e9fcec58200226a92610dc39dd20a59d443e4a733f2ecf919aef6cd
Dependency lock hash                                                 sha256:afa595beed6c70d7a0124844d450e6b157b365ce6fa7c7fd0d2df9b70aff97c5
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Contract freeze commit：`fdf22c2fa64a97f8c3be1b4c9ea080c575b53845`。

Acceptance validation：

```text
G11F frozen acceptance command                                      61 passed
StrategyState contract/golden/boundary                              21 passed
Full test suite                                                    1158 passed
Workspace import boundary                                           PASS (82 files)
mypy 2.3.0                                                           no issues (82 package source files)
Primary LSP                                                          clean (6 files)
pi-lens scoped review                                                no findings across 6 changed files
Static golden/deep-freeze/restore/forgery controls                   PASS
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Implementation commit：`af2897e11fedf3c0807e0f60435be9e700269c03`。

## 88. G11G Named Random Streams Acceptance Card

```yaml
id: G11G
status: PASSED
depends_on:
  - G11F
owner_package: backtest-runtime strategy
public_interface:
  - crypto_quant_backtest.NamedRandomStream
test_commands:
  readiness: uv run pytest -q tests/runtime/strategy_state/test_strategy_state.py tests/runtime/strategy_state/test_strategy_state_golden.py tests/domain/canonical tests/architecture/test_g11f_strategy_state_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  contract: uv run pytest -q tests/runtime/random_streams/test_named_random_stream.py
  fixture: uv run pytest -q tests/runtime/random_streams/test_named_random_stream_golden.py
  boundary: uv run pytest -q tests/architecture/test_g11g_random_stream_boundary.py tests/architecture/test_g11f_strategy_state_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  acceptance: uv run pytest -q tests/runtime/random_streams/test_named_random_stream.py tests/runtime/random_streams/test_named_random_stream_golden.py tests/runtime/strategy_state/test_strategy_state.py tests/runtime/strategy_state/test_strategy_state_golden.py tests/domain/canonical tests/architecture/test_g11g_random_stream_boundary.py tests/architecture/test_g11f_strategy_state_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g11g-pytest.xml
fixture_ids:
  - named-random-stream-isolation-v1
expected_artifacts:
  - docs/research/g11g-named-random-streams.md
  - tests/fixtures/runtime/random-streams/named-random-stream-isolation-v1.json
  - build/acceptance/g11g-pytest.xml
  - build/acceptance/g11g-import-boundary-report.json
failure_contracts:
  - global-or-process-rng-state-affects-draws
  - ambient-entropy-time-attempt-or-runtime-address-enters-stream
  - seed-strategy-key-algorithm-version-or-counter-is-missing-from-identity
  - unrelated-strategy-or-stream-draw-advances-this-stream
  - saved-counter-does-not-replay-the-same-suffix
  - draw-mutates-the-current-stream
  - draw-preimage-or-u64-byte-order-is-implicit
  - bool-negative-or-noninteger-seed-or-counter-is-accepted
  - empty-padded-or-noncanonical-stream-key-is-accepted
  - unsupported-algorithm-or-version-silently-falls-back
  - rng-counter-is-hidden-inside-strategy-business-state
  - random-stream-claims-unfrozen-distribution-statistical-or-security-guarantees
  - numpy-provider-sdk-filesystem-network-or-callback-enters-g11g
  - g11g-mutates-engine-runner-timeline-observation-or-financial-kernel
allowed_grade: development
evidence:
  - exact-sha256-counter-preimage-tests
  - immutable-draw-and-counter-replay-tests
  - seed-strategy-key-counter-isolation-tests
  - unrelated-stream-noninterference-tests
  - deterministic-static-golden-hash
  - constructor-forgery-controls
  - public-api-import-report
  - import-boundary-report
  - static-type-report
  - dependency-lock-report
passed_commit: 91571d219b432348f5fc04e63d72ce54d3ff024b
artifact_hashes:
  tests/fixtures/runtime/random-streams/named-random-stream-isolation-v1.json: sha256:7d9c4b8b1d7a65f8fbd2a0c25b343dd6bdd257282bfd08c1fe6982a0dcf04aee
  build/acceptance/g11g-pytest.xml: sha256:ad68f0d0869b00b78a3a51a170f22c50d35a2ebe48b9705185b3289cebc95ce0
  build/acceptance/g11g-import-boundary-report.json: sha256:a5779a7e94bce8f6222149655a41462d5272ba56f9c2ceb07cbc72b96005e3c3
```

### G11G Acceptance

1. G11G只新增one production module `crypto_quant_backtest.random_streams`与root export `NamedRandomStream`。它是pure immutable、provider-neutral、offline deterministic simulation value，不读取global RNG、OS entropy、wall clock、filesystem、network、database、process、environment、Attempt或runtime address；
2. `NamedRandomStream` exact保存`master_random_seed: int`、`strategy_id: StrategySleeveId`、canonical nonempty `stream_key: str`、`algorithm: str`、`algorithm_version: int`与nonnegative `counter: int`。bool不属于integer seed/counter；
3. G11G v1 algorithm exact只允许`algorithm="sha256-counter"`与`algorithm_version=1`。Constructor不得fallback、alias、lookup current version、load plugin或接受未冻结algorithm；future algorithm必须通过new frozen version/type演进；
4. Stream key必须nonempty、trimmed、NFC canonical text。Master seed exact沿用BacktestRequest nonnegative integer contract，不自行截断、salt、读取entropy或使用process hash randomization；
5. Stream canonical body exact为`{type="named_random_stream",schema_version=1,algorithm,algorithm_version,master_random_seed,strategy_id,stream_key,counter}`。`stream_hash=canonical_sha256(body)`且`to_canonical_dict()`只追加non-recursive stream hash；任一identity field变化必须改变canonical identity；
6. Counter命名the next draw。`draw_u64()`无参数，不能mutate current stream，并返回exact `(value: int,next_stream: NamedRandomStream)`；`0 <= value < 2**64`且`next_stream.counter == self.counter + 1`，其他identity fields exact unchanged；
7. Draw preimage exact为`{type="named_random_stream_draw",schema_version=1,algorithm,algorithm_version,master_random_seed,strategy_id,stream_key,counter}`，其中counter使用draw前current value。不得加入wall clock、draw order outside this stream、Attempt、thread/process、object identity或hidden nonce；
8. Draw algorithm exact为`hashlib.sha256(canonical_bytes(preimage)).digest()`，value exact取digest前8 bytes并按unsigned big-endian解释。不得使用Python `hash()`、`random`、`secrets`、NumPy、provider SDK或platform-dependent available algorithm alias；
9. Same exact stream fields/counter必须跨construction/input order产生same draw、next stream canonical bytes/hash与suffix。Reconstruct saved counter后next draw及continuation必须与uninterrupted stream exact一致；
10. Strategy isolation exact由StrategySleeveId进入stream/draw preimage保证；stream-purpose isolation exact由stream key进入preimage保证。Different seed、Strategy、key或counter必须产生separate identity；fixture冻结代表样本差异但不把hash collision impossibility当业务证明；
11. Draw unrelated Strategy/key stream不能advance或改变original immutable stream、its hash、next draw或suffix。G11G不维护mutable registry/pool/global counter/singleton/cache；
12. `NamedRandomStream` current value本身是G11G counter checkpoint。G11F `StrategyCheckpoint`与G11G stream保持separate immutable authorities；G11I later可绑定两者hash。G11F generic values不吸收hidden RNG counter，G11G也不吸收Strategy business fields；
13. Constructor与`dataclasses.replace`必须重新验证seed/key/algorithm/version/counter。Derived stream hash不接受caller input；invalid identity fail closed且不能silent normalize为another stream；
14. SHA-256在此仅是frozen deterministic bit derivation primitive。G11G不声明cryptographic unpredictability、security token/key generation、gambling suitability、independent statistical distribution certification或Monte Carlo convergence；
15. G11G v1不提供`draw_below`、float、normal/lognormal、shuffle、choice、distribution registry或sampling policy。Exact unbiased bounded/distribution semantics需要later separate frozen Gate；raw u64是当前最小independently useful seam；
16. Parameter search、calibration、model selection、Walk-forward、experiment scheduling、Strategy invocation、Observation access、Target/Decision production、financial accounting与EngineCheckpoint均不属于G11G；
17. Production imports exact只允许stdlib `hashlib`/dataclass support及`crypto_quant_domain` public canonical/identity contracts。Engine、Runner、Timeline、Observation、TargetStream、StrategyState production modules与Trading Kernel不得获得G11G branch；
18. Static golden至少冻结first draws、counter progression、saved-counter replay、same-stream repeat parity、different seed/Strategy/key/counter separation、unrelated-stream noninterference、canonical stream/draw hashes与constructor/forgery controls；
19. G11G outputs固定development-only，不创建decision-grade eligibility、live randomness、deployment authorization、external artifact publication或child Attempt recovery。

Frozen seam note：`docs/research/g11g-named-random-streams.md`。

Readiness baseline：

```text
G11F strategy-state readiness command                               40 passed
Workspace import boundary                                           PASS (82 files)
mypy 2.3.0                                                           no issues (82 package source files)
Primary LSP                                                          no diagnostics (2 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no findings across 3 planning/research files
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
Frozen readiness command                                             40 passed
Workspace import boundary                                           PASS (82 files)
mypy 2.3.0                                                           no issues (82 package source files)
Primary LSP                                                          no diagnostics (2 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no findings across 3 planning/research files
Research note hash                                                   sha256:72559ee8005a509b18744b02a009460e39d19172e1924bfc2299d96eaffbcdfe
Import boundary report hash                                          sha256:d8c1dd51b7b852547a9df0e73804729b614219742ecd9d598a2633771e4f4835
Dependency lock hash                                                 sha256:afa595beed6c70d7a0124844d450e6b157b365ce6fa7c7fd0d2df9b70aff97c5
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Contract freeze commit：`b4d3d3622c41b567429939868d5e868860b4a67b`。

Acceptance validation：

```text
G11G frozen acceptance command                                      61 passed
NamedRandomStream contract/golden/boundary                          21 passed
Full test suite                                                    1179 passed
Workspace import boundary                                           PASS (83 files)
mypy 2.3.0                                                           no issues (83 package source files)
Primary LSP                                                          clean (6 files)
pi-lens scoped review                                                no findings across 6 changed files
Static golden/replay/isolation/forgery controls                      PASS
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Implementation commit：`91571d219b432348f5fc04e63d72ce54d3ff024b`。

## 89. G11H Model Artifact and Revision Timeline Acceptance Card

```yaml
id: G11H
status: PASSED
depends_on:
  - G11B
  - G11F
owner_package: backtest-runtime strategy
public_interface:
  - crypto_quant_backtest.ModelArtifactRef
  - crypto_quant_backtest.ModelRevisionTimeline
test_commands:
  readiness: uv run pytest -q tests/runtime/observations/test_point_in_time_observation_view.py tests/runtime/observations/test_point_in_time_observation_view_golden.py tests/runtime/strategy_state/test_strategy_state.py tests/runtime/strategy_state/test_strategy_state_golden.py tests/domain/canonical tests/architecture/test_g11b_observation_causality_boundary.py tests/architecture/test_g11f_strategy_state_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  contract: uv run pytest -q tests/runtime/model_revisions/test_model_revision_timeline.py
  fixture: uv run pytest -q tests/runtime/model_revisions/test_model_revision_timeline_golden.py
  boundary: uv run pytest -q tests/architecture/test_g11h_model_revision_boundary.py tests/architecture/test_g11b_observation_causality_boundary.py tests/architecture/test_g11f_strategy_state_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  acceptance: uv run pytest -q tests/runtime/model_revisions/test_model_revision_timeline.py tests/runtime/model_revisions/test_model_revision_timeline_golden.py tests/runtime/observations/test_point_in_time_observation_view.py tests/runtime/strategy_state/test_strategy_state.py tests/domain/canonical tests/architecture/test_g11h_model_revision_boundary.py tests/architecture/test_g11b_observation_causality_boundary.py tests/architecture/test_g11f_strategy_state_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g11h-pytest.xml
fixture_ids:
  - walk-forward-model-revision-v1
expected_artifacts:
  - docs/research/g11h-model-artifact-revision-timeline.md
  - tests/fixtures/runtime/model-revisions/walk-forward-model-revision-v1.json
  - build/acceptance/g11h-pytest.xml
  - build/acceptance/g11h-import-boundary-report.json
failure_contracts:
  - model-reference-omits-content-training-code-data-window-or-feature-schema-identity
  - model-bytes-path-loader-callback-framework-or-endpoint-enters-runtime-reference
  - training-window-is-empty-reversed-or-ends-after-artifact-availability
  - utc-only-cutoff-exposes-same-time-later-phase-or-sequence-artifact
  - future-or-unrelated-model-evidence-changes-prior-timeline-or-selection
  - same-model-revision-identity-has-conflicting-content
  - visible-model-revision-parent-is-missing
  - visible-model-revision-chain-forks-cycles-or-has-multiple-roots-or-terminals
  - feature-schema-changes-silently-inside-one-model-lineage
  - child-model-revision-availability-does-not-strictly-follow-parent
  - selected-model-is-not-the-latest-visible-terminal
  - empty-visible-timeline-is-treated-as-training-or-coverage-failure
  - input-order-or-exact-duplicate-changes-canonical-output
  - g11h-trains-ranks-loads-executes-or-mutates-strategy-state
  - g11h-claims-model-quality-decision-grade-live-or-deployment-authorization
allowed_grade: development
evidence:
  - immutable-model-provenance-contract-tests
  - full-simulation-instant-visibility-tests
  - revision-chain-selection-and-failure-precedence-tests
  - future-and-unrelated-model-noninterference-tests
  - walk-forward-switch-static-golden-hash
  - constructor-forgery-controls
  - public-api-import-report
  - import-boundary-report
  - static-type-report
  - dependency-lock-report
passed_commit: 07a29546bb7defff701b143c575b3d2df8ab2a83
artifact_hashes:
  tests/fixtures/runtime/model-revisions/walk-forward-model-revision-v1.json: sha256:ed883c62653e17e1ba2e678c6f2683ea9b1db6467b564b94df093725e00a2807
  build/acceptance/g11h-pytest.xml: sha256:4aff1c6785f85c47c954b747473f8f620efad8c07ec6faf70a6a7704335ca88c
  build/acceptance/g11h-import-boundary-report.json: sha256:ee364716383abba613329216495a156c590217bfc8090fb4a2aed4fba516386f
```

### G11H Acceptance

1. G11H只新增one production module `crypto_quant_backtest.model_revisions`与root exports `ModelArtifactRef`、`ModelRevisionTimeline`。它是pure immutable、provider-neutral、offline point-in-time reference seam，不训练、加载、执行、评分或选择候选模型；
2. `ModelArtifactRef` exact保存canonical nonempty `model_key`、`model_hash`、`training_data_hash`、`training_start: UtcInstant`、`training_end: UtcInstant`、`training_code_hash`、`feature_schema_hash`、`available_at: SimulationInstant`、canonical `revision_id`与optional `supersedes_revision_id`；
3. 四个hash field exact必须为`sha256:<64 lowercase hex>`。Reference不保存model bytes、weights、path、URI、loader、callable、module/class、framework object、endpoint、registry handle、score/rank、mutable status、Attempt或wall-clock identity；
4. Training interval必须`training_start < training_end`且`training_end <= available_at.instant`。Training interval是economic provenance，artifact visibility使用full SimulationInstant；G11H不猜timezone、capture delay或training completion；
5. `ModelArtifactRef` canonical body exact为`{type="model_artifact_ref",schema_version=1,model_key,model_hash,training_data_hash,training_start,training_end,training_code_hash,feature_schema_hash,available_at,revision_id,supersedes_revision_id}`。`artifact_ref_hash=canonical_sha256(body)`且canonical dict只追加non-recursive hash；
6. `ModelRevisionTimeline` constructor exact只接收canonical `model_key`、`decision_instant: SimulationInstant`与`ModelArtifactRef` iterable。Public behavior exact只有`timeline_hash`与argument-free `select() -> ModelArtifactRef | None`；不得暴露backing/future revisions、mutable registry或loader；
7. Construction processing order exact为：discard refs with other model key；discard `available_at > decision_instant` future refs using full total order；collapse exact duplicate canonical refs；validate/freeze visible revision chain；derive timeline hash。Future/unrelated malformed chain evidence不能阻断或改变prior timeline/selection；
8. Visible revision identity exact为`(model_key,revision_id)`。Exact duplicate refs collapse；same identity/different canonical content fail closed。Input order不得改变visible chain、timeline hash或selection；
9. Visible legal lineage exact有one root、unique revision IDs、every child naming same-lineage visible parent、no fork/cycle/disconnected second root/multiple terminal。Failure precedence exact为revision-ID conflict→missing parent→chain conflict→feature-schema mismatch→availability regression；
10. `feature_schema_hash`必须在one model lineage内exact stable。Feature interface change需要new model key或later explicit migration contract；不得silent fallback。Training data/window、training code和model content允许逐revision变化且全部保留identity；
11. Child `available_at`必须strictly greater than parent in full SimulationInstant order。Same UTC later phase/sequence可合法；equal/earlier full instant fail closed。Future child存在时visible predecessor仍是terminal；
12. `select()`成功返回visible legal chain unique terminal exact object；没有visible ref成功返回None。Empty不等于Missing Bundle、training failure、model quality failure、Universe exclusion或deployment blocker；
13. Timeline canonical body exact为`{type="model_revision_timeline",schema_version=1,model_key,decision_instant,visible_artifacts}`，visible refs按root→terminal chain order且使用full canonical dict。`timeline_hash=canonical_sha256(body)`且non-recursive；
14. Adding/reordering other model refs、future refs、future conflicts或exact duplicates必须产生same prior timeline hash与selection canonical bytes/hash。Later model revision不得retroactively rewrite earlier DecisionContext；
15. Model key、Decision full instant、any visible provenance/hash/window/revision/availability field变化必须改变timeline identity。Selected Artifact identity可由G11I写入StrategyState/Decision evidence，但G11H本身不得mutate StrategyState或produce Decision；
16. Constructor与`dataclasses.replace`必须重新验证hashes、training interval、availability、revision text与supersession identity。Timeline rejects malformed visible chains deterministically；derived hashes不接受caller input；
17. Runtime training、fine-tuning、feature computation、parameter search、candidate ranking/best-model selection、experiment comparison、model deserialization/inference callback与remote/file/object-store acquisition全部outside G11H；
18. Production imports exact只允许stdlib immutable collection support与`crypto_quant_domain` public canonical/time contracts。Observation implementation may inform semantics but G11H module不得import Engine、Runner、Timeline runtime object、StrategyState implementation、Trading Kernel、ML framework或provider SDK；
19. Static golden至少冻结before/at same-UTC correction、future conflict/unrelated model noninterference、v1→v2 terminal selection、empty success、all visible chain failures、feature-schema failure、full provenance/timeline hashes、input/repeat parity及forgery controls；
20. G11H outputs固定development-only，不声明model quality、decision-grade eligibility、live inference或deployment authorization。Historical artifact acquisition/completeness/retention remains external/G12 authority。

Frozen seam note：`docs/research/g11h-model-artifact-revision-timeline.md`。

Readiness baseline：

```text
G11B/G11F observation-state readiness command                        57 passed
Workspace import boundary                                           PASS (83 files)
mypy 2.3.0                                                           no issues (83 package source files)
Primary LSP                                                          no diagnostics (2 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no findings across 3 planning/research files
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
Frozen readiness command                                             57 passed
Workspace import boundary                                           PASS (83 files)
mypy 2.3.0                                                           no issues (83 package source files)
Primary LSP                                                          no diagnostics (2 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no findings across 3 planning/research files
Research note hash                                                   sha256:74ddec0726cd236a7fbb0b94676462379f1f68bf9d6c9d73ad6106a87fa0737b
Import boundary report hash                                          sha256:a5779a7e94bce8f6222149655a41462d5272ba56f9c2ceb07cbc72b96005e3c3
Dependency lock hash                                                 sha256:afa595beed6c70d7a0124844d450e6b157b365ce6fa7c7fd0d2df9b70aff97c5
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Contract freeze commit：`c845875326f79fb7feb00fbdd8e466171ba66ea6`。

Acceptance validation：

```text
G11H frozen acceptance command                                      80 passed
Model revision contract/golden/boundary                             25 passed
Full test suite                                                    1204 passed
Workspace import boundary                                           PASS (84 files)
mypy 2.3.0                                                           no issues (84 package source files)
Primary LSP                                                          clean (6 files)
pi-lens scoped review                                                no findings across 6 changed files
Static golden/point-in-time/chain/forgery controls                   PASS
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Implementation commit：`07a29546bb7defff701b143c575b3d2df8ab2a83`。

## 90. G11C Point-in-time Universe Acceptance Card

```yaml
id: G11C
status: PASSED
depends_on:
  - G11A
  - G11B
owner_package: backtest-runtime observations
public_interface:
  - crypto_quant_backtest.UniverseKind
  - crypto_quant_backtest.UniverseMembershipRevision
  - crypto_quant_backtest.UniverseQuery
  - crypto_quant_backtest.UniverseSelection
  - crypto_quant_backtest.PointInTimeUniverseView
test_commands:
  readiness: uv run pytest -q tests/runtime/observations/test_point_in_time_observation_view.py tests/runtime/observations/test_point_in_time_observation_view_golden.py tests/domain/instruments tests/domain/time tests/kernel/validation/test_strategy_output_validator.py tests/architecture/test_g11b_observation_causality_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  contract: uv run pytest -q tests/runtime/universe/test_point_in_time_universe.py
  fixture: uv run pytest -q tests/runtime/universe/test_point_in_time_universe_golden.py
  boundary: uv run pytest -q tests/architecture/test_g11c_universe_boundary.py tests/architecture/test_g11b_observation_causality_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  acceptance: uv run pytest -q tests/runtime/universe/test_point_in_time_universe.py tests/runtime/universe/test_point_in_time_universe_golden.py tests/runtime/observations/test_point_in_time_observation_view.py tests/domain/instruments tests/domain/time tests/kernel/validation/test_strategy_output_validator.py tests/architecture/test_g11c_universe_boundary.py tests/architecture/test_g11b_observation_causality_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g11c-pytest.xml
fixture_ids:
  - point-in-time-universe-membership-v1
expected_artifacts:
  - docs/research/g11c-point-in-time-universe.md
  - tests/fixtures/runtime/universe/point-in-time-universe-membership-v1.json
  - build/acceptance/g11c-pytest.xml
  - build/acceptance/g11c-import-boundary-report.json
failure_contracts:
  - universe-is-inferred-from-files-symbols-bars-or-current-api
  - point-in-time-and-static-evidence-is-mixed-for-one-query
  - utc-only-cutoff-exposes-same-time-later-phase-or-sequence-membership
  - future-or-unrelated-universe-conflict-changes-prior-view-or-selection
  - same-membership-revision-identity-has-conflicting-content
  - visible-membership-parent-is-missing
  - visible-membership-chain-forks-cycles-or-has-multiple-roots-or-terminals
  - membership-lineage-changes-universe-kind-instrument-or-membership-key
  - child-membership-availability-does-not-strictly-follow-parent
  - membership-or-listing-interval-is-empty-reversed-or-inconsistent
  - active-membership-overlaps-for-one-instrument
  - pre-listing-or-at-after-delisting-instrument-is-returned
  - selected-instruments-or-evidence-hashes-are-not-canonical-and-unique
  - empty-universe-is-misclassified-as-session-gap-or-completeness-failure
  - static-universe-claims-survivorship-bias-free-market-coverage
  - g11c-claims-decision-grade-live-or-deployment-authorization
allowed_grade: development
evidence:
  - full-simulation-instant-membership-tests
  - listing-delisting-entry-exit-and-reentry-tests
  - revision-chain-selection-and-failure-precedence-tests
  - future-and-unrelated-universe-noninterference-tests
  - labelled-static-universe-tests
  - deterministic-static-golden-hash
  - constructor-forgery-controls
  - public-api-import-report
  - import-boundary-report
  - static-type-report
  - dependency-lock-report
passed_commit: d3fe684181ddd5a7335da0e68485849eb41a22f2
artifact_hashes:
  tests/fixtures/runtime/universe/point-in-time-universe-membership-v1.json: sha256:46848a7f577d540ee7e5f5118e45646590034f5888cd540902535b746a03c9da
  build/acceptance/g11c-pytest.xml: sha256:227b0db7763a70cce11350f1b64a25bcc2dadf0ba5a7db25e73981c624159450
  build/acceptance/g11c-import-boundary-report.json: sha256:f94d2195306e7cb62bdffd4356fe92a3ce4c714cc81a01cf630e7978ea875097
```

### G11C Acceptance

1. G11C只新增one production module `crypto_quant_backtest.universe`与root exports，保持pure immutable、provider-neutral、offline Strategy-facing Universe value seam。它只消费caller-supplied exact evidence，不扫描directory/file、读取Bundle/Reader/network/current API或从Symbol/Bar推断Universe；
2. `UniverseKind` v1 exact只有`POINT_IN_TIME`与`STATIC`。One `UniverseQuery`/Universe key不能mix kinds；Static evidence必须显式label，不能fallback为Point-in-time或冒充historical exchange coverage；
3. `UniverseMembershipRevision` exact保存canonical nonempty `universe_key`与caller-supplied stable `membership_key`、exact kind、`InstrumentId`、listing interval、membership interval、`available_at: SimulationInstant`、canonical Revision ID/optional superseded ID、source hash；
4. Listing interval exact为`[listed_at,delisted_at)`，membership interval exact为`[member_from,member_until)`；optional ends为open-ended。Each interval必须nonempty，membership interval必须完全contained by listing interval。Delisting closes active membership but does not erase historical revision/Instrument identity；
5. `membership_key`是one logical membership interval across corrections，不从Instrument、times、Revision ID、payload/order猜测。Same Instrument exit/re-entry使用separate nonoverlapping membership keys；
6. Revision canonical body exact为`{type="universe_membership_revision",schema_version=1,universe_key,membership_key,kind,instrument_id,listed_at,delisted_at,member_from,member_until,available_at,revision_id,supersedes_revision_id,source_hash}`；`revision_hash=canonical_sha256(body)`且non-recursive；
7. `UniverseQuery` exact保存canonical `universe_key`、kind与`decision_instant: SimulationInstant`；query hash绑定full instant。Economic interval membership按`decision_instant.instant`判定，knowledge visibility按full SimulationInstant total order；
8. `PointInTimeUniverseView` constructor exact只接收Query和Revision iterable。Public behavior exact只有`view_hash`与argument-free `select() -> UniverseSelection`；不得暴露backing/future revisions、mutable registry/cache、Reader或clock；
9. Construction order exact为discard other Universe key/kind→discard future availability→canonical exact dedup→validate each membership-key visible chain→select terminal→validate selected interval consistency→select active members。Future/unrelated malformed evidence不能阻断或改变prior view/selection；
10. Visible identity exact为`(membership_key,revision_id)`。Exact duplicate collapse；same identity/different content fail closed。Each lineage exact one root、existing same-lineage parents、no fork/cycle/disconnected second root/multiple terminal；
11. Lineage exact保持Universe key、kind、Instrument与membership key。Child full availability必须strictly greater than parent。Failure precedence exact为revision identity conflict→missing parent→chain conflict→lineage context mismatch→availability regression→interval invalid→active overlap；
12. Terminal revisions independently selected per membership key。At Decision UTC instant only intervals containing that instant are active；pre-listing、at/after finite delisting、before membership start及at/after membership end必须excluded；
13. Active selected membership intervals for same Instrument/Universe cannot overlap.Exit/re-entry via nonoverlapping keys is legal；simultaneously active duplicate Instrument evidence fail closed instead of silently deduplicating semantic conflict；
14. `UniverseSelection` exact保存Query、sorted unique active Instrument tuple、selected active revision hashes、all visible candidate revision hashes、max selected availability instant、fixed limitation flags与selection hash；tuple fields/hashes必须canonical sorted and unique；
15. Selection flags exact为：`point_in_time = kind is POINT_IN_TIME`、`static_universe = kind is STATIC`、`survivorship_bias_safe=false`、`decision_grade_eligible=false`、`deployment_authorized=false`。Constructor/replace不得forge flags or maxima；
16. Exact query没有active Instrument成功返回empty tuple、empty selected revision hashes与None max selected availability。G11C不得解释为No Session、Suspended、No Trades、Missing、Source Outage、complete market absence或coverage success/failure；
17. View canonical body exact绑定Query与all visible in-scope revisions after dedup；selection canonical body绑定Query、active Instruments/selected hashes/all visible hashes/max availability/flags。Input order、exact duplicates、future/unrelated records不能改变prior identity；
18. Static Universe仍必须提供explicit listing/membership intervals与availability evidence。它只表示caller-declared fixed experiment set；G11C不得检查current directory/final dataset组成或声明survivorship-safe、all-market或decision-grade；
19. G11C不拥有Universe completeness/source gap/retention（G12）、Bar/window/resample（G11D）、schedule/warmup（G11E）、Strategy invocation（G11I）、Target validation mutation、financial state、RNG、Model或EngineCheckpoint；
20. Production imports exact只允许stdlib immutable support与`crypto_quant_domain` public identity/time/canonical contracts。Engine、Runner、Timeline runtime object、Observation implementation、Trading Kernel/provider modules保持无G11C branch；
21. Static golden至少冻结entry/correction same-UTC cutoff、exit/re-entry、pre-listing/delisting、POINT_IN_TIME/STATIC flags、future/unrelated noninterference、all chain/interval failures、empty success、input/repeat parity、sorted output、hash/maxima与forgery controls；
22. G11C outputs固定development-only。G12 coverage完成且later invocation qualification前不得声明survivorship-safe、decision-grade、live或deployment authorization。

Frozen seam note：`docs/research/g11c-point-in-time-universe.md`。

Readiness baseline：

```text
G11B observation and Domain universe readiness command               61 passed
Workspace import boundary                                           PASS (84 files)
mypy 2.3.0                                                           no issues (84 package source files)
Primary LSP                                                          no diagnostics (2 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no findings across 3 planning/research files
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
Frozen readiness command                                             61 passed
Workspace import boundary                                           PASS (84 files)
mypy 2.3.0                                                           no issues (84 package source files)
Primary LSP                                                          no diagnostics (2 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no findings across 3 planning/research files
Research note hash                                                   sha256:57590a6439ce3410de0729396da542f00c24cc9e195e1ffddbfb656d16f35b4d
Import boundary report hash                                          sha256:ee364716383abba613329216495a156c590217bfc8090fb4a2aed4fba516386f
Dependency lock hash                                                 sha256:afa595beed6c70d7a0124844d450e6b157b365ce6fa7c7fd0d2df9b70aff97c5
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Contract freeze commit：`a723209730be2365f70ed96809ed43a51b9512a0`。

Acceptance validation：

```text
G11C frozen acceptance command                                      74 passed
Universe contract/golden/boundary                                   14 passed
Full test suite                                                    1218 passed
Workspace import boundary                                           PASS (85 files)
mypy 2.3.0                                                           no issues (85 package source files)
Primary LSP                                                          clean (6 files)
pi-lens scoped review                                                no findings across 6 changed files
Static golden/membership/listing/static/forgery controls             PASS
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Implementation commit：`d3fe684181ddd5a7335da0e68485849eb41a22f2`。

## 91. G11D Named Bar Window Acceptance Card

```yaml
id: G11D
status: PASSED
passed_commit: 49969689f0792481a6fb626c090a7ac7049aaaf9
depends_on:
  - G11A
  - G11B
owner_package: backtest-runtime observations
public_interface:
  - crypto_quant_backtest.BarDefinitionRef
  - crypto_quant_backtest.NamedBarWindowQuery
  - crypto_quant_backtest.NamedBarWindowResult
  - crypto_quant_backtest.NamedBarWindowView
test_commands:
  readiness: uv run pytest -q tests/runtime/observations/test_point_in_time_observation_view.py tests/runtime/observations/test_point_in_time_observation_view_golden.py tests/domain/canonical tests/domain/time tests/architecture/test_g11b_observation_causality_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  contract: uv run pytest -q tests/runtime/observation_windows/test_named_bar_window.py
  fixture: uv run pytest -q tests/runtime/observation_windows/test_named_bar_window_golden.py
  boundary: uv run pytest -q tests/architecture/test_g11d_observation_window_boundary.py tests/architecture/test_g11b_observation_causality_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  acceptance: uv run pytest -q tests/runtime/observation_windows/test_named_bar_window.py tests/runtime/observation_windows/test_named_bar_window_golden.py tests/runtime/observations/test_point_in_time_observation_view.py tests/runtime/observations/test_point_in_time_observation_view_golden.py tests/domain/canonical tests/domain/time tests/architecture/test_g11d_observation_window_boundary.py tests/architecture/test_g11b_observation_causality_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g11d-pytest.xml
fixture_ids:
  - named-bar-window-coverage-v1
expected_artifacts:
  - docs/research/g11d-named-bar-window.md
  - tests/fixtures/runtime/observation-windows/named-bar-window-coverage-v1.json
  - build/acceptance/g11d-pytest.xml
  - build/acceptance/g11d-import-boundary-report.json
failure_contracts:
  - bar-definition-key-version-or-hash-is-invalid-or-implicit
  - lookback-is-bool-zero-negative-or-unbounded
  - window-end-is-after-decision-instant
  - backing-g11b-query-or-decision-instant-does-not-match
  - non-bar-wrong-context-future-post-cutoff-duplicate-or-noncanonical-event-is-returned
  - backing-causality-trace-is-forged-or-does-not-match-events
  - returned-window-is-not-the-canonical-bounded-suffix
  - short-or-empty-window-is-misclassified-as-gap-reason-or-exception
  - g11d-resamples-aggregates-forward-fills-or-parses-payload-semantics
  - g11d-claims-bar-completeness-decision-grade-live-or-deployment-authorization
allowed_grade: development
evidence:
  - explicit-bar-definition-identity-tests
  - full-simulation-instant-backing-result-tests
  - bounded-lookback-and-end-cutoff-tests
  - full-partial-and-empty-coverage-tests
  - causality-trace-and-maxima-tests
  - deterministic-static-golden-hash
  - constructor-forgery-controls
  - public-api-import-report
  - import-boundary-report
  - static-type-report
  - dependency-lock-report
```

### G11D Acceptance

1. G11D只新增one production module `crypto_quant_backtest.observation_windows`与root exports，保持pure immutable、provider-neutral、offline Strategy-facing bounded Bar window seam。它只组合caller-supplied successful G11B result，不读取Bundle/Reader/file/network/database/process/environment/wall clock；
2. `BarDefinitionRef` exact保存canonical nonempty key、positive non-bool integer version与exact sha256 definition hash。Hash由Builder/Bundle evidence承诺duration/session/anchor/phases/price/volume/empty-policy/calendar完整定义；G11D不复制或解释这些字段；
3. `BarDefinitionRef` canonical body exact为`{type="bar_definition_ref",schema_version=1,key,version,definition_hash}`；`bar_definition_ref_hash=canonical_sha256(body)`且non-recursive。Definition变化必须改变version和/或hash；无implicit current/default definition；
4. `NamedBarWindowQuery` exact保存one G11B `ObservationQuery`、BarDefinitionRef、`decision_instant: SimulationInstant`、positive bounded `lookback_count`与optional `end_at_or_before: UtcInstant`。bool/zero/negative lookback fail closed；v1 maximum exact为10000；
5. Optional end cutoff必须`<= decision_instant.instant`。Query不接受duration、timezone、Calendar、resample rule、predicate、callback、dataframe、Reader或path；query hash绑定all exact fields；
6. `NamedBarWindowView` constructor exact接收Named Query与one successful `PointInTimeObservationQueryResult`。Public behavior exact只有`view_hash`与argument-free `window() -> NamedBarWindowResult`；
7. Backing Result query与Decision Instant必须exact匹配Named Query，trace context/result fields必须继续通过G11B constructor invariants。G11D不得接受G11B failure、re-authorize Query或inspect hidden/superseded payload；
8. Backing events必须all exact Event type `bar`、matching Dataset/Instrument/Capability、`timeline_instant <= decision_instant`、unique IDs且G11A/B canonical order。If end cutoff supplied only events with `event_time <= cutoff` are eligible；post-cutoff event不得进入returned window；
9. Window exact为eligible events canonical tuple的final `lookback_count` suffix；不得reverse、payload-sort、deduplicate semantic bars、parse OHLCV、forward-fill、synthesize empty Bars或aggregate/resample；
10. `NamedBarWindowResult` exact保存Query、returned Event tuple、backing causality trace、`available_count`（eligible count before truncation）、requested count、coverage complete、shortfall count、window max event/available times、flags与result hash；
11. `coverage_complete` exact等于`available_count >= requested_count`，`shortfall_count=max(requested_count-available_count,0)`。Returned count exact为`min(available_count,requested_count)`；constructor/replace重算all relationships；
12. Short or empty authorized lookback成功返回explicit partial result。G11D不得分类为NO_SESSION、SUSPENDED、NO_TRADES、MISSING、SOURCE_OUTAGE、Bundle gap或Bar aggregation defect；G12 owns reasons/completeness；
13. Result maxima exact从returned window计算；empty window maxima为None。Backing trace remains full authorized Query causality evidence and may cover more events than returned suffix；result hash binds both trace and returned window；
14. View canonical body exact为`{type="named_bar_window_view",schema_version=1,query,backing_result}`，view hash绑定BarDefinition identity、Decision、lookback/cutoff与full G11B result. Input parity inherited from G11B；
15. Result canonical body exact为`{type="named_bar_window_result",schema_version=1,query,events,causality_trace,available_count,requested_count,coverage_complete,shortfall_count,max_event_time,max_available_instant,decision_grade_eligible,deployment_authorized}`；
16. `decision_grade_eligible=false`与`deployment_authorized=false`固定。G11D不能因count complete声明BarDefinition aggregation correct、gap complete或decision-grade；G12 BarAggregationManifest/coverage required；
17. Constructor与`dataclasses.replace`必须拒绝wrong Query/instant/context/type/order/count/maxima/flags或forged trace/result。Derived hashes不接受caller input；
18. G11D不拥有Universe（G11C）、schedule/warmup（G11E）、Strategy invocation（G11I）、indicator library、arbitrary resampling、financial state、RNG、Model或EngineCheckpoint；
19. Production imports exact只允许stdlib immutable support、`crypto_quant_domain`/`crypto_quant_market_data` public values与G11B public observation contracts。Engine、Runner、Timeline runtime object、Trading Kernel/provider SDK保持无G11D branch；
20. Static golden至少冻结five visible Bars、lookback 3 suffix、end cutoff boundary、full/partial/empty results、BarDefinition identity change、wrong context/type/cutoff/forged trace failures、counts/maxima/trace/hashes/flags与repeat parity；
21. G11D outputs固定development-only，不声明Bar completeness、decision-grade、live或deployment authorization。

Frozen seam note：`docs/research/g11d-named-bar-window.md`。

Readiness baseline：

```text
G11B observation and canonical readiness command                     48 passed
Workspace import boundary                                           PASS (85 files)
mypy 2.3.0                                                           no issues (85 package source files)
Primary LSP                                                          no diagnostics (2 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no findings across 3 planning/research files
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
Frozen readiness command                                             48 passed
Workspace import boundary                                           PASS (85 files)
mypy 2.3.0                                                           no issues (85 package source files)
Primary LSP                                                          no diagnostics (2 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no findings across 3 planning/research files
Research note hash                                                   sha256:4dc2f5ad23e2c6f63573171a1a832fcfe41d0616931b05952bd4def2fea0ce88
Import boundary report hash                                          sha256:f94d2195306e7cb62bdffd4356fe92a3ce4c714cc81a01cf630e7978ea875097
Dependency lock hash                                                 sha256:afa595beed6c70d7a0124844d450e6b157b365ce6fa7c7fd0d2df9b70aff97c5
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Contract freeze commit：`48d7b8f55ae7754328c89603f33e649c14911486`。

Implementation validation：

```text
Frozen acceptance command                                            61 passed
Focused G11D contract/golden/boundary                                13 passed
Full repository suite                                                1231 passed
Workspace import boundary                                           PASS (86 files)
mypy 2.3.0                                                           no issues (86 package source files)
Primary LSP                                                          no diagnostics across 6 changed Python files
pi-lens edited-file review                                           no findings across 6 files
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Artifact hashes：

```text
named-bar-window-coverage-v1.json                                    sha256:7cda8b555fb3072f3f5f629fef10c111996ab39a99f0d8e113ac981b4c60a40d
g11d-pytest.xml                                                      sha256:2a7b98e3493f0648e8f3d777097acaf376772e1a220b2ad4cc2605bf989e108c
g11d-import-boundary-report.json                                     sha256:dd1e52459f0cf25f229d3746eb9e2c18418737f19161ffd347fb233db71494fb
uv.lock                                                              sha256:afa595beed6c70d7a0124844d450e6b157b365ce6fa7c7fd0d2df9b70aff97c5
```

Implementation commit：`49969689f0792481a6fb626c090a7ac7049aaaf9`。

## 92. G11E Decision Schedule and Warmup Acceptance Card

```yaml
id: G11E
status: PASSED
passed_commit: 0e602a91ef02518533340b2bb1c6ca44a741f6f6
depends_on:
  - G11B
  - G11D
owner_package: backtest-runtime strategy
public_interface:
  - crypto_quant_backtest.LookbackRequirement
  - crypto_quant_backtest.DecisionScheduleEntry
  - crypto_quant_backtest.DecisionSchedule
  - crypto_quant_backtest.LookbackCoverage
  - crypto_quant_backtest.WarmupEligibility
test_commands:
  readiness: uv run pytest -q tests/runtime/observation_windows/test_named_bar_window.py tests/runtime/observation_windows/test_named_bar_window_golden.py tests/runtime/timeline/test_deterministic_timeline.py tests/domain/time tests/architecture/test_g11d_observation_window_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  contract: uv run pytest -q tests/runtime/decision_schedule/test_decision_schedule.py
  fixture: uv run pytest -q tests/runtime/decision_schedule/test_decision_schedule_golden.py
  boundary: uv run pytest -q tests/architecture/test_g11e_decision_schedule_boundary.py tests/architecture/test_g11d_observation_window_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  acceptance: uv run pytest -q tests/runtime/decision_schedule/test_decision_schedule.py tests/runtime/decision_schedule/test_decision_schedule_golden.py tests/runtime/observation_windows/test_named_bar_window.py tests/runtime/observation_windows/test_named_bar_window_golden.py tests/runtime/timeline/test_deterministic_timeline.py tests/domain/time tests/architecture/test_g11e_decision_schedule_boundary.py tests/architecture/test_g11d_observation_window_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g11e-pytest.xml
fixture_ids:
  - decision-schedule-warmup-eligibility-v1
expected_artifacts:
  - docs/research/g11e-decision-schedule-warmup.md
  - tests/fixtures/runtime/decision-schedule/decision-schedule-warmup-eligibility-v1.json
  - build/acceptance/g11e-pytest.xml
  - build/acceptance/g11e-import-boundary-report.json
failure_contracts:
  - schedule-or-requirement-identity-is-invalid-or-implicit
  - lookback-minimum-is-bool-zero-negative-or-unbounded
  - schedule-entry-is-empty-duplicate-unsorted-or-outside-half-open-window
  - declared-segment-does-not-match-window-boundaries
  - duplicate-requirement-key-or-selector-definition-identity
  - evaluated-entry-is-not-an-exact-schedule-member
  - window-evidence-is-missing-duplicate-extra-or-wrong-context
  - insufficient-lookback-is-misclassified-as-exception-or-gap-reason
  - warmup-authorizes-order-fill-journal-performance-or-account-side-effects
  - schedule-collapses-or-reorders-full-simulation-instants-by-utc-only
  - g11e-expands-calendar-session-cron-or-reads-timeline-bundle-clock
  - g11e-claims-decision-grade-live-or-deployment-authorization
allowed_grade: development
evidence:
  - half-open-warmup-active-boundary-tests
  - full-simulation-instant-ordering-tests
  - lookback-requirement-and-window-binding-tests
  - satisfied-short-missing-and-empty-coverage-tests
  - warmup-side-effect-suppression-tests
  - deterministic-static-golden-hash
  - constructor-forgery-controls
  - public-api-import-report
  - import-boundary-report
  - static-type-report
  - dependency-lock-report
```

### G11E Acceptance

1. G11E只新增one production module `crypto_quant_backtest.decision_schedule`与root exports，保持pure immutable、provider-neutral、offline schedule/eligibility seam；
2. G11E exact复用`TimelineWindow`与`TimelineSegment`，不得新增second run-boundary/segment model。Window必须继续满足`data_start <= trading_start < end_exclusive`；
3. `LookbackRequirement` exact保存canonical nonempty `requirement_key`、G11A `ObservationQuery`、G11D `BarDefinitionRef`与positive non-bool `minimum_count`；v1 maximum exact为10000；
4. Requirement canonical body exact为`{type="lookback_requirement",schema_version=1,requirement_key,observation_query,bar_definition,minimum_count}`；requirement hash non-recursive绑定all fields；
5. `DecisionScheduleEntry` exact保存`decision_instant: SimulationInstant`与`segment: TimelineSegment`。UTC位于`[data_start,trading_start)`必须Warmup，位于`[trading_start,end_exclusive)`必须Active Trading；end boundary及以后不得进入schedule；
6. Entry canonical body exact为`{type="decision_schedule_entry",schema_version=1,decision_instant,segment}`；entry hash绑定full Instant phase/source sequence，不能UTC-only；
7. `DecisionSchedule` exact保存canonical nonempty key、positive non-bool version、one TimelineWindow、nonempty Entry tuple与Requirement tuple。Public behavior exact只有`key`/`version`/`window`/`entries`/`requirements` values、`schedule_hash`和`eligibility(entry, windows)`；
8. Entries必须caller-supplied exact strict increasing full SimulationInstant order且unique；constructor不得silent sort。Same UTC different phase/source sequence是distinct ordered invocation windows；duplicate full Instant fail closed；
9. Requirements按`(requirement_key, observation_query.query_hash, bar_definition_ref_hash)`canonical排序。Duplicate requirement key或duplicate `(ObservationQuery, BarDefinitionRef)` identity fail closed；empty requirements合法；
10. Schedule canonical body exact为`{type="decision_schedule",schema_version=1,key,version,window,entries,requirements}`；changed boundary/Instant phase or sequence/segment/requirement/BarDefinition must change schedule hash；
11. `eligibility`只接受schedule exact member Entry与tuple of G11D `NamedBarWindowResult`；无callback、registry、hidden state或runtime clock；same inputs repeat parity；
12. Every requirement必须匹配exactly one Window result by ObservationQuery and BarDefinitionRef；Window Query Decision Instant必须exact等于Entry Decision Instant。Missing、duplicate、extra、wrong selector、wrong definition或wrong instant evidence fail closed；
13. `LookbackCoverage` exact保存requirement、window result hash、required count、available count、shortfall count与satisfied。`satisfied = available_count >= minimum_count`；`shortfall=max(minimum_count-available_count,0)`；derived relations constructor/replace重算；
14. G11E使用G11D `available_count`评估frozen minimum，不依赖G11D `coverage_complete`或requested_count等于minimum。不得parse Bar payload、resample、forward-fill或分类absence reason；
15. `WarmupEligibility` exact保存schedule hash、Entry、ordered coverage tuple、`lookback_satisfied`、`strategy_invocation_eligible`、`trading_side_effects_authorized`、grade/deployment flags与eligibility hash；
16. Overall lookback satisfied exact为all coverage satisfied；empty requirements为true。Insufficient/missing count中的insufficient是successful explicit ineligible result，不是exception、G12 gap reason或Bar completeness claim；
17. `strategy_invocation_eligible = lookback_satisfied` for both Warmup and Active，允许Warmup在requirements满足后构建StrategyState；实际Context/invocation/state transition由G11I/G11F拥有；
18. `trading_side_effects_authorized = lookback_satisfied and segment == ACTIVE_TRADING`。Warmup固定false，不得产生或授权OrderIntent、Target activation、Fill、Journal、account mutation或performance；
19. `WarmupEligibility` canonical body exact为`{type="warmup_eligibility",schema_version=1,schedule_hash,entry,coverage,lookback_satisfied,strategy_invocation_eligible,trading_side_effects_authorized,decision_grade_eligible,deployment_authorized}`；
20. `decision_grade_eligible=false`与`deployment_authorized=false`固定。G11E只提供development eligibility evidence；G12 completeness与later qualification required；
21. Constructor与`dataclasses.replace`必须拒绝wrong hash/entry/coverage counts/order/derived booleans/flags或forged context；derived hashes不接受caller input；
22. G11E consumes already-resolved finite Decision Instants；不拥有Calendar/Session/TradingDate/DST/cron/recurrence expansion、Timeline/Reader/Bundle/Event generation或wall clock；
23. Atomic same-instant boundary仅表示one exact full SimulationInstant Entry为shared eligibility boundary。G11I owns Strategy identities、registration-order independence、parallel isolation、invocation与DecisionBatch；G11E不生成per-Strategy entries或partial outputs；
24. Existing adapter-specific `TargetStreamDecisionSchedule`与Warmup suppression保持不变；G11E不替换其UTC target injection contract；Engine/Runner/Timeline/TargetStream/Kernel/provider SDK保持无G11E branch；
25. Production imports exact只允许stdlib immutable support、`crypto_quant_domain` public canonical/time values与G11D/Timeline public runtime contracts；无新增dependency/cache/framework；
26. Static golden至少冻结Warmup 50、Active boundary 100、same UTC distinct full Instants、last legal Active instant、end 300 exclusion、satisfied/short/missing/empty requirements、Warmup invocation true + side effects false、Active side effects only when satisfied、identity changes、wrong/extra/duplicate evidence、unsorted/segment/forgery failures与repeat parity；
27. G11E outputs固定development-only，不声明Lookback completeness原因、decision-grade、live或deployment authorization。

Frozen seam note：`docs/research/g11e-decision-schedule-warmup.md`。

Readiness baseline：

```text
G11D window/timeline readiness command                              40 passed
Workspace import boundary                                           PASS (86 files)
mypy 2.3.0                                                           no issues (86 package source files)
Primary LSP                                                          no diagnostics (2 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no warning findings across 3 planning/research files
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
Frozen readiness command                                             40 passed
Workspace import boundary                                           PASS (86 files)
mypy 2.3.0                                                           no issues (86 package source files)
Primary LSP                                                          no diagnostics (2 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no warning findings across 3 planning/research files
Research note hash                                                   sha256:ee58fa1c4206049af7f095a961bc4018a0d1d61ce9781d86ea053d4de976ad62
Import boundary report hash                                          sha256:dd1e52459f0cf25f229d3746eb9e2c18418737f19161ffd347fb233db71494fb
Dependency lock hash                                                 sha256:afa595beed6c70d7a0124844d450e6b157b365ce6fa7c7fd0d2df9b70aff97c5
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Contract freeze commit：`d432ba39ac00801077e96447abaf7cf46504c7fa`。

Implementation validation：

```text
Frozen acceptance command                                            52 passed
Focused G11E contract/golden/boundary                                12 passed
Full repository suite                                                1243 passed
Workspace import boundary                                           PASS (87 files)
mypy 2.3.0                                                           no issues (87 package source files)
Primary LSP                                                          no diagnostics across 6 changed Python files
pi-lens edited-file review                                           no findings across 6 files
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Artifact hashes：

```text
decision-schedule-warmup-eligibility-v1.json                         sha256:cafcf80aa438a730d747d6b7c6cbe3b5ad5b4dc8d2ce25ef49e5c0b7c1010372
g11e-pytest.xml                                                      sha256:26da77ab6d3bfd494932f3c805f56c9d50be55cabb31505ad4794fc43338e1b0
g11e-import-boundary-report.json                                     sha256:72f8fdc85a57f5a326f67a61dcb2c89d292089fdaceaaadc1bd1d3bc8e9090f1
uv.lock                                                              sha256:afa595beed6c70d7a0124844d450e6b157b365ce6fa7c7fd0d2df9b70aff97c5
```

Implementation commit：`0e602a91ef02518533340b2bb1c6ca44a741f6f6`。

## 93. G12A SourceSnapshot Acceptance Card

```yaml
id: G12A
status: PASSED
passed_commit: 36d8146864ad3fead31593878ad247fbd5f5f463
depends_on:
  - G00
owner_package: market-bundle-builder
public_interface:
  - crypto_quant_bundle_builder.RawSourceMember
  - crypto_quant_bundle_builder.SourceSnapshotProvenance
  - crypto_quant_bundle_builder.SourceSnapshotMember
  - crypto_quant_bundle_builder.SourceSnapshot
  - crypto_quant_bundle_builder.SourceSnapshotFailureCode
  - crypto_quant_bundle_builder.SourceSnapshotFailure
  - crypto_quant_bundle_builder.SourceSnapshotOutcome
  - crypto_quant_bundle_builder.freeze_source_snapshot
  - crypto_quant_bundle_builder.verify_source_snapshot
  - crypto_quant_bundle_builder.SourceSnapshot.member_bytes
test_commands:
  readiness: uv run pytest -q tests/architecture tests/parity
  contract: uv run pytest -q tests/bundle_builder/source_snapshots/test_source_snapshot.py
  fixture: uv run pytest -q tests/bundle_builder/source_snapshots/test_source_snapshot_golden.py
  boundary: uv run pytest -q tests/architecture/test_g12a_source_snapshot_boundary.py tests/architecture/test_import_boundary_mutations.py tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py
  acceptance: uv run pytest -q tests/bundle_builder/source_snapshots/test_source_snapshot.py tests/bundle_builder/source_snapshots/test_source_snapshot_golden.py tests/architecture/test_g12a_source_snapshot_boundary.py tests/architecture/test_import_boundary_mutations.py tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py tests/parity/test_source_snapshots.py --junitxml=build/acceptance/g12a-pytest.xml
fixture_ids:
  - source-snapshot-v1
expected_artifacts:
  - docs/research/g12a-source-snapshot-contract.md
  - tests/fixtures/market_data/source-snapshots/source-snapshot-v1.tar.gz
  - tests/fixtures/market_data/source-snapshots/source-snapshot-v1.expected.json
  - build/acceptance/g12a-pytest.xml
  - build/acceptance/g12a-import-boundary-report.json
failure_contracts:
  - invalid-snapshot-input
  - unsafe-member
  - duplicate-member
  - acquisition-failed
  - declared-source-hash-mismatch
  - archive-invalid
  - snapshot-id-mismatch
  - content-tree-hash-mismatch
  - provenance-hash-mismatch
allowed_grade: development
evidence:
  - g00-compatible-deterministic-archive-identity
  - content-and-provenance-hash-separation
  - one-shot-atomic-capture-tests
  - declared-source-hash-controls
  - archive-tamper-and-noncanonical-controls
  - verified-member-access-tests
  - restricted-canonical-json-parity
  - deterministic-static-golden-hash
  - scoped-import-boundary-report
  - public-api-import-report
  - static-type-report
  - dependency-lock-report
```

### G12A Acceptance

1. G12A只新增one production module `crypto_quant_bundle_builder.source_snapshots`与Builder root exports，保持pure in-memory、offline、stdlib-only source-freeze seam；不import Trading Domain/Kernel/Runtime/provider SDK；无新增dependency；
2. `RawSourceMember` exact保存`member_key`、`raw_bytes: bytes | None`、mode、caller-supplied acquisition epoch nanoseconds与optional declared sha256。`b""`是valid content，只有None表示acquisition incomplete；bytes字段`repr=False`；
3. Member key v1 exact为ASCII 1–100 bytes slash-separated logical USTAR key；每segment匹配`[A-Za-z0-9_][A-Za-z0-9._-]*`；absolute/empty/dot/dotdot/repeated or trailing slash/backslash/NUL/non-ASCII/leading-dot/overlong/PAX path fail closed；
4. Mode exact只允许`0644`或`0755`；acquisition time必须non-bool integer；all public digest exact为`sha256:<64 lowercase hex>`；declared hash若存在必须match raw bytes；
5. `SourceSnapshotProvenance` exact保存canonical lowercase `vendor_key`、`source_key`、`license_ref`与`retention_policy_ref`，每值匹配`[a-z][a-z0-9._-]*`。这些是metadata refs，不是credential/header/URL/path/legal conclusion/retention proof；
6. `freeze_source_snapshot` exact materialize caller iterable once before derivation，canonical sort by member key，并拒绝duplicate。Any invalid/unsafe/failed/mismatched later member returns failure with no partial Snapshot；
7. Content archive exact复用G00/WP-00C recipe：sorted regular USTAR members、exact key/bytes/mode、mtime/uid/gid=0、uname/gname/gzip filename empty、gzip mtime=0、compresslevel=9；
8. `snapshot_id=sha256(archive_bytes)`。Member key/mode/bytes必须改变identity；input order/acquisition time/provenance/local path/process/machine/current time不得改变identity；
9. `SourceSnapshotMember` exact保存member key、content hash、byte count、mode、acquisition epoch nanoseconds与optional declared hash；members必须sorted/unique且与archive exact-cover；
10. Content-tree preimage exact为`{type="source_snapshot_content_tree",schema_version=1,members:[{member_key,content_hash,byte_count,mode}]}`；content tree hash是audit evidence，不是second reference identity；
11. Provenance preimage exact为`{type="source_snapshot_provenance",schema_version=1,snapshot_id,vendor_key,source_key,license_ref,retention_policy_ref,members:[{member_key,acquired_at_epoch_nanoseconds,declared_sha256}]}`；provenance-only changes preserve snapshot ID and change provenance hash；
12. `SourceSnapshot.to_canonical_dict()` exact保存type/schema/snapshot ID/content-tree hash/full member evidence/provenance/provenance hash/false qualification flags且不保存archive bytes。G12A不新增manifest/ref/envelope/path/URI/CAS identity；
13. Builder private canonical encoder只接受null/bool/non-bool integer/NFC string/list/string-key mapping，使用UTF-8 compact JSON与Unicode-key sort；float/Decimal/datetime/bytes/set/non-string keys/cycles fail closed；
14. `freeze_source_snapshot`与`verify_source_snapshot` exact返回XOR `SourceSnapshotOutcome`。Success only one Snapshot；failure only one structured failure；无exception text/stack/bytes/credentials/URL/header/local path泄漏；
15. Freeze failure precedence exact为INVALID_SNAPSHOT_INPUT→UNSAFE_MEMBER→DUPLICATE_MEMBER→ACQUISITION_FAILED→DECLARED_SOURCE_HASH_MISMATCH；
16. Verify failure precedence exact为INVALID_SNAPSHOT_INPUT→ARCHIVE_INVALID→SNAPSHOT_ID_MISMATCH→CONTENT_TREE_HASH_MISMATCH→PROVENANCE_HASH_MISMATCH；constructor shape violations使用TypeError/ValueError；
17. Verification全程in-memory，reject malformed/nonregular/unsafe/duplicate/unsorted/noncanonical tar/gzip metadata，reconstruct exact canonical archive and byte-compare，再重算snapshot/member/content/provenance evidence；
18. `SourceSnapshot.member_bytes(member_key)`是G12B唯一raw-member access，必须private verify/extract、正确返回zero-byte content，并对invalid/unverified/missing request只抛fixed non-revealing error；
19. `SourceSnapshotFailure`只保存stable code与optional independently-safe member key；unsafe/unparseable input不得回显；failure identity canonical且不绑定runtime exception/message；
20. Value atomicity exact表示all supplied members形成one complete Snapshot或no Snapshot。Filesystem/object-store publish、temp files、locks、concurrent dedup、repository retrieval与retention属于G12D；
21. G12A不拥有HTTP/file/database/cloud acquisition、provider auth/pagination/retry、filesystem scan/symlink、CLI/registry/protocol/callback/cache/wall clock、normalization、Bundle validation、Reader或Runtime；
22. Scoped import policy只限制`source_snapshots.py` offline core，不全局阻止future G12L Builder adapters；Runtime→Builder prohibition保持；
23. Static golden至少冻结three synthetic members including zero-byte and executable、exact archive bytes、manifest/member/content/provenance hashes、reverse-input parity、provenance-only change、key/mode/byte sensitivity、member access、all failure codes/precedence、later-member atomicity、archive tamper/noncanonical controls、canonical vectors与false flags；
24. G12A fixture必须synthetic and secret-free。Real source admissibility/encryption/license adjudication/retention/retrievability/completeness/decision-grade/live/deployment均不在本Gate声明；
25. G12A固定development-only，`decision_grade_eligible=false`与`deployment_authorized=false`。

Frozen seam note：`docs/research/g12a-source-snapshot-contract.md`。

Readiness baseline：

```text
G00 architecture/parity prerequisites                               133 passed
Workspace import boundary                                           PASS (87 files)
mypy 2.3.0                                                           no issues (87 package source files)
Primary LSP                                                          no diagnostics (5 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no warning findings across 6 freeze files
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
Frozen readiness command                                             133 passed
Workspace import boundary                                           PASS (87 files)
mypy 2.3.0                                                           no issues (87 package source files)
Primary LSP                                                          no diagnostics (5 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no warning findings across 6 freeze files
Research note hash                                                   sha256:c27861c3b528486df2b4ff2a5ce50520df5323423b5c9286e7582ce8a4875092
Import boundary report hash                                          sha256:e9b305bf0b5e8c5f74539d02c6df9ce2c1a0b0b94d72d32d85a91590bb50d2d7
Dependency lock hash                                                 sha256:afa595beed6c70d7a0124844d450e6b157b365ce6fa7c7fd0d2df9b70aff97c5
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Contract freeze commit：`4cbca7b7f19112e7c8cf86c824f4e13d9d469cc2`。

Implementation validation：

```text
Frozen acceptance command                                            55 passed
Focused G12A contract/golden/boundary                                11 passed
Full repository suite                                                1254 passed
Workspace import boundary                                           PASS (88 files)
mypy 2.3.0                                                           no issues (88 package source files)
Primary LSP                                                          no diagnostics across 5 changed Python files
pi-lens edited-file review                                           no findings after 2 in-memory canonicalization false positives
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Artifact hashes：

```text
source-snapshot-v1.tar.gz                                            sha256:e828f1bafff2f9499c2c7c0916dd7cea1cc4eb20bf960a9ff3b93d4c4e711cd3
source-snapshot-v1.expected.json                                     sha256:86f15f62b8d3fc793580d0965b4f4ee7d7b3cb3cb43c14ea5ccb3533d8b4d8d7
g12a-pytest.xml                                                      sha256:511b0fe9f4967ab742d7ee9beaa870444edc7378e6e3cfd17b3f20229992529b
g12a-import-boundary-report.json                                     sha256:ffde2b2f133b57a885e31d430fdba9bf6e94e52a7a82f1466cc062f091351a4f
uv.lock                                                              sha256:afa595beed6c70d7a0124844d450e6b157b365ce6fa7c7fd0d2df9b70aff97c5
```

Implementation commit：`36d8146864ad3fead31593878ad247fbd5f5f463`。

## 93A. Provider Acquisition Tools v1 (PASSED)

```yaml
id: G12-ACQ-TOOLS-V1
status: PASSED
owner: Backtest tools/acquisition
depends_on: [G12A]
interfaces:
  - tools.acquisition.binance_usdm.acquire_archive
  - tools.acquisition.binance_usdm.acquire_funding_history
  - tools.acquisition.cn_a_share_tushare.acquire_daily_listing
credential_contract:
  binance_public_market_data: none
  tushare: environment-only TUSHARE_TOKEN
test_commands:
  focused: uv run --locked pytest -q tests/tools/acquisition tests/architecture/test_provider_acquisition_tools_boundary.py
remaining_blockers: []
validation:
  focused_acquisition_and_architecture: 20 passed
  full_repository: 1765 passed
  import_boundaries: 109 files passed
  lock_diff_lsp_lens_secret_scan: clean
  real_binance_network_smoke: passed
  tushare_invalid_token_redaction_smoke: passed
  independent_review: NONE
passed_commit: 6f0bd99a93a349924996eb26708fbb0ac6fecf17
```

Acceptance requires exact provider-specific request validation, bounded retries,
checksum/raw-response preservation, redacted receipts, G12A candidate snapshots,
atomic no-partial output, fixed false qualification flags, no runtime/package-root
surface change, no network tests, and no tracked credential fallback.

Implementation note: `docs/implementation/provider-acquisition-tools.md`.

## 94. G12B Synthetic JSONL v1 Normalization Acceptance Card

```yaml
id: G12B
status: PASSED
passed_commit: c57080a87e5daa48b5637ad6d9d0f84f94f707b1
depends_on:
  - G12A
  - G02
owner_package: market-bundle-builder
public_interface:
  - crypto_quant_bundle_builder.SyntheticJsonlV1Config
  - crypto_quant_bundle_builder.SyntheticJsonlV1RecordLocator
  - crypto_quant_bundle_builder.SyntheticJsonlV1SourceTrace
  - crypto_quant_bundle_builder.SyntheticJsonlV1NormalizationResult
  - crypto_quant_bundle_builder.SyntheticJsonlV1NormalizationFailureCode
  - crypto_quant_bundle_builder.SyntheticJsonlV1NormalizationFailure
  - crypto_quant_bundle_builder.SyntheticJsonlV1NormalizationOutcome
  - crypto_quant_bundle_builder.normalize_synthetic_jsonl_v1
  - crypto_quant_bundle_builder.SyntheticJsonlV1NormalizationResult.event_for_source_record
  - crypto_quant_bundle_builder.SyntheticJsonlV1NormalizationResult.trace_for_event
test_commands:
  readiness: uv run pytest -q tests/bundle_builder/source_snapshots tests/parity/test_source_snapshots.py tests/domain/canonical tests/domain/instruments tests/domain/numeric tests/domain/time tests/domain/accounting tests/market_data/bundles tests/architecture/test_workspace_smoke.py tests/architecture/test_g12a_source_snapshot_boundary.py tests/architecture/test_import_boundary_mutations.py tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py
  contract: uv run pytest -q tests/bundle_builder/normalization/test_synthetic_jsonl.py
  fixture: uv run pytest -q tests/bundle_builder/normalization/test_synthetic_jsonl_golden.py
  boundary: uv run pytest -q tests/architecture/test_g12b_synthetic_jsonl_boundary.py tests/architecture/test_g12a_source_snapshot_boundary.py tests/architecture/test_import_boundary_mutations.py tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py
  acceptance: uv run pytest -q tests/bundle_builder/normalization/test_synthetic_jsonl.py tests/bundle_builder/normalization/test_synthetic_jsonl_golden.py tests/bundle_builder/source_snapshots tests/domain/canonical tests/domain/instruments tests/domain/numeric tests/domain/time tests/domain/accounting tests/market_data/bundles tests/architecture/test_g12b_synthetic_jsonl_boundary.py tests/architecture/test_g12a_source_snapshot_boundary.py tests/architecture/test_import_boundary_mutations.py tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py tests/parity/test_source_snapshots.py --junitxml=build/acceptance/g12b-pytest.xml
fixture_ids:
  - synthetic-jsonl-v1
expected_artifacts:
  - docs/research/g12b-canonical-normalization-contract.md
  - tests/fixtures/market_data/normalization/synthetic-jsonl-v1.jsonl
  - tests/fixtures/market_data/normalization/synthetic-jsonl-v1.expected.json
  - build/acceptance/g12b-pytest.xml
  - build/acceptance/g12b-import-boundary-report.json
failure_contracts:
  - invalid-normalization-input
  - source-snapshot-invalid
  - selected-member-missing
  - member-encoding-invalid
  - jsonl-layout-invalid
  - json-invalid
  - noncanonical-json
  - record-shape-invalid
  - unsupported-record-schema
  - record-field-invalid
  - instrument-unmapped
  - price-purpose-unmapped
  - event-envelope-invalid
allowed_grade: development
evidence:
  - verified-g12a-member-only-input
  - strict-canonical-jsonl-tests
  - explicit-instrument-and-price-purpose-mapping
  - exact-utc-scale-and-revision-preservation
  - bidirectional-source-event-trace
  - physical-line-order-and-sequence-tests
  - config-and-normalizer-identity-tests
  - atomic-failure-precedence-tests
  - deterministic-static-golden-hash
  - scoped-import-boundary-report
  - public-api-import-report
  - static-type-report
  - dependency-lock-report
```

### G12B Acceptance

1. G12B只新增one production module `crypto_quant_bundle_builder.synthetic_jsonl`与eight Builder root exports，使用one synthetic-only function seam；无generic normalizer/protocol/callback/registry/parser plugin/DSL/cache/provider adapter；
2. Builder package明确直接依赖`crypto_quant_domain` public root与`crypto_quant_market_data`；无third-party dependency；不得通过Market Data re-export Domain types规避依赖；
3. `SyntheticJsonlV1Config` exact保存member key、stream key、MarketBundleCapability、TimelinePhase、Instrument alias bindings与PricePurpose alias bindings；bindings nonempty、canonical sorted、duplicate alias fail closed且input order hash-invariant；
4. Instrument alias exact匹配`[A-Z][A-Z0-9._-]{0,63}`，Purpose alias exact匹配`[a-z][a-z0-9_.-]{0,63}`；无default/implicit mapping；
5. Config canonical body exact绑定all semantic fields；`config_hash=canonical_sha256(body)`。Fixed normalizer ID exact为`synthetic_jsonl@1`，spec hash exact绑定type/schema/ID；grammar semantic change requires new version；
6. Normalizer先验证complete G12A SourceSnapshot，再从verified member evidence选择exact `config.member_key`，raw bytes只通过`member_bytes()`；不得读取archive bytes或parse gzip/tar；
7. Selected zero-byte member成功返回empty Events/traces且不声明coverage/completeness；
8. Nonempty member必须strict UTF-8、无BOM/raw CR、exact one final LF delimiter、无empty physical records；physical line number 1-based，SourceSequence exact为line_number-1；
9. JSON parser拒绝duplicate keys at any nesting、float/decimal/exponent/nonfinite tokens，不修改process-global integer limit；original line bytes必须exact等于`canonical_bytes(parsed_object)`；
10. Each line exact包含eleven keys：available/event time、instrument、price scale/units、purpose、record key、revision ID、schema version、supersedes revision ID、type；unknown/missing keys fail closed；
11. Type exact为`synthetic_price_point`且schema version exact non-bool integer 1；record/revision IDs与aliases obey frozen regex；supersedes null或different valid revision ID；
12. Times exact为non-bool integer UtcInstant且available >= event；price units positive non-bool integer；price scale exact accepted by Scale；无float/rounding/inference；
13. Event exact映射configured stream/capability/phase、mapped Instrument、event/available time、line sequence、revision fields、Snapshot provenance source key与selected member content hash；
14. Event type exact为`synthetic_price_point.v1`；payload exact为canonical primitives `synthetic_record_key`、`price_units`、`price_scale` places、`price_purpose` enum value；不构造typed Price/currency/Rule/CorporateAction；
15. Locator canonical body exact为`{type="synthetic_jsonl_line_locator",schema_version=1,member_key,line_number}`；
16. Event ID exact为`synthetic-jsonl-v1:` + canonical hash of type/schema/spec hash/config hash/snapshot ID/source key/locator；caller不能提供Event ID/sequence/hash；
17. Events/traces exact保留physical-line order；G12B不sort/deduplicate、不验证stream ordering或revision chain；G12C/G12I owns those checks；
18. Source trace exact保存snapshot ID、provenance hash、source key、member content hash、locator、Event ID/hash；member hash + locator是raw source identity，无redundant raw-line hash；
19. Result exact保存config/spec/snapshot/provenance/source/member identities、Event/trace tuples、normalization hash与false flags；trace/event positional exact-cover、contiguous locator/sequence、source evidence与hashes必须一致；
20. `event_for_source_record()`与`trace_for_event()`是deterministic linear lookup returning value or None；无stored indexes/cache；
21. Provenance-only changes with same source key preserve Event identity但change trace/result identity；source key/member content/semantic config changes affect Event/result identity；
22. Outcome XOR result/failure，all failures return no partial Event/trace tuples；failure只保存code、optional safe member key/locator/field与failure hash，不泄漏raw value/bytes/exception/path/URL/header/credential；
23. Failure precedence exact为invalid input→snapshot invalid→member missing→encoding invalid→layout invalid→lowest failing physical line；per-line exact为JSON invalid→noncanonical→shape→schema→field→Instrument unmapped→Purpose unmapped→Event envelope invalid；
24. G12B只生成existing public MarketEvent envelope与Builder-local trace；没有generic Rule/CorporateAction/Revision class claim；
25. Production imports只允许stdlib、sibling G12A、Domain public root、Market Data public root；无Domain internal/Kernel/Runtime/archive/filesystem/network/process/current-clock imports；
26. G12B不拥有G12C manifest/partition/count/capability/order/duplicate validation、G12G Bars、G12H/K economics/coverage、G12I revision selection/coverage、G12D–F publication/Reader或G12L acquisition；
27. Static golden至少冻结root+correction+second purpose、zero-byte success、exact Event/trace/config/spec/result hashes、reverse-binding parity、provenance/source/content/config sensitivity、all failure codes/precedence、atomicity、bidirectional lookup与false flags；
28. G12B outputs固定development-only，`decision_grade_eligible=false`与`deployment_authorized=false`，不声明real provider schema或source completeness。

Frozen seam note：`docs/research/g12b-canonical-normalization-contract.md`。

Readiness baseline：

```text
G12A/domain/market-data prerequisites                               133 passed
Workspace import boundary                                           PASS (88 files)
mypy 2.3.0                                                           no issues (88 package source files)
Primary LSP                                                          no diagnostics (3 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no warning findings across 5 freeze files
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Readiness validation：

```text
Frozen readiness command                                             133 passed
Workspace import boundary                                           PASS (88 files)
mypy 2.3.0                                                           no issues (88 package source files)
Primary LSP                                                          no diagnostics (3 Markdown files unconfirmed on silent clean)
pi-lens scoped review                                                no warning findings across 5 freeze files
Research note hash                                                   sha256:9ee7b15e07c0f11b8df000eeeb89ddb4043ba37f57d420fa1bb6bad0555a94d5
Import boundary report hash                                          sha256:fdee57781424acb1a79c7e013fd13b8524ce9fd5afd0b57af505461490013db5
Dependency lock hash                                                 sha256:a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Contract freeze commit：`95b5cbe`；Builder Domain dependency commit：`3bf3edfe9f77bdde3bbc74e63d246614c61e03e2`。

Implementation validation：

```text
Frozen acceptance command                                            150 passed
Focused G12B contract/golden/boundary                                22 passed
Full repository suite                                                1273 passed
Workspace import boundary                                           PASS (89 files)
mypy 2.3.0                                                           no issues (89 package source files)
Primary LSP                                                          no diagnostics across 7 changed Python files
pi-lens edited-file review                                           no findings across 7 files
Markdown + git diff checks                                           PASS
uv lock --check                                                      PASS
Python                                                                3.13.5
```

Artifact hashes：

```text
synthetic-jsonl-v1.jsonl                                             sha256:bda20f6da08ee1ad2679129f7e3f58ce3a1dae482ed8e9ce30374d70b6c0913b
synthetic-jsonl-v1.expected.json                                     sha256:d79dea48d388821a2b8e44bed5b8e53a48044909c5cfc84c405889b92f0a2390
g12b-pytest.xml                                                      sha256:7488c2e0a1e0814c5e01d4956c5db7d84d1c83a0374c7d2f759b1e00e1f89bb1
g12b-import-boundary-report.json                                     sha256:556f6dc119c0f5ab137c4816966e7a65f4f439e6d56c250d1dc30c288b4a0aa3
uv.lock                                                              sha256:a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
```

Implementation commit：`c57080a87e5daa48b5637ad6d9d0f84f94f707b1`。

## 96. G12D Atomic Local MarketBundle Repository Acceptance Card

```yaml
id: G12D
status: PASSED
passed_commit: 7df91f381a1635d3d748ff08f83504107c2a41f4
depends_on:
  - G12C
owner_package: market-bundle-builder
allowed_grade: development
public_interface:
  - crypto_quant_bundle_builder.LocalMarketBundleRepository
  - crypto_quant_bundle_builder.LocalMarketBundleRepositoryConfig
  - crypto_quant_bundle_builder.MarketBundlePublicationFailureCode
  - crypto_quant_bundle_builder.MarketBundlePublicationFailure
  - crypto_quant_bundle_builder.MarketBundlePublicationOutcome
  - crypto_quant_bundle_builder.MarketBundlePublicationResult
  - crypto_quant_bundle_builder.MarketBundleRepositoryPath
  - crypto_quant_bundle_builder.LocalMarketBundleRetentionProof
test_commands:
  readiness: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/bundle_builder/source_snapshots tests/bundle_builder/normalization tests/bundle_builder/validation tests/market_data/bundles tests/runtime/timeline tests/runtime/engine/test_g06_synthetic_cash_journey.py
  contract: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/bundle_builder/publication/test_local_market_bundle_repository.py
  fixture: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/bundle_builder/publication/test_local_market_bundle_repository_golden.py
  architecture: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/architecture/test_g12d_local_repository_boundary.py tests/architecture/test_g12c_bundle_validation_boundary.py tests/architecture/test_g12b_synthetic_jsonl_boundary.py tests/architecture/test_g12a_source_snapshot_boundary.py tests/architecture/test_import_boundary_mutations.py tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py
  acceptance: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/bundle_builder/source_snapshots tests/bundle_builder/normalization tests/bundle_builder/validation tests/bundle_builder/publication tests/market_data/bundles tests/runtime/timeline tests/runtime/engine/test_g06_synthetic_cash_journey.py tests/architecture/test_g12a_source_snapshot_boundary.py tests/architecture/test_g12b_synthetic_jsonl_boundary.py tests/architecture/test_g12c_bundle_validation_boundary.py tests/architecture/test_g12d_local_repository_boundary.py tests/architecture/test_import_boundary_mutations.py tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g12d-pytest.xml
  import_boundary: PYTHONDONTWRITEBYTECODE=1 uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g12d-import-boundary-report.json
  static_types: uvx --from mypy==2.3.0 mypy --python-version 3.13 packages/*/src
  full_suite: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q
artifacts:
  - docs/research/g12d-atomic-bundle-repository.md
  - tests/fixtures/market_data/publication/local-market-bundle-repository-v1.expected.json
  - build/acceptance/g12d-pytest.xml
  - build/acceptance/g12d-import-boundary-report.json
implementation_commit: 7df91f381a1635d3d748ff08f83504107c2a41f4
approved_on: 2026-08-13
```

Frozen contract：

- G12D adds one concrete Builder module and exactly eight root exports; the only operation is `LocalMarketBundleRepository.publish_market_bundle_v1`, with no free wrapper, generic Protocol, URI/object-store layer, Reader, Cursor, callback, registry, or plugin;
- config accepts one absolute local `Path` root; the root, hostname, PID, thread, UUID, and clock never enter identity or public evidence;
- input is an exact valid `MarketBundleManifest`, exact `Mapping[str, bytes]` covering every manifest stream and no extras, and a canonical lowercase `retention_policy_ref`; stream payload bytes are opaque and must hash exactly to the corresponding `MarketStreamManifest.content_hash`;
- authoritative identity is `MarketBundleRef.from_manifest(manifest)`; final paths use `bundles/<bundle_key>/<manifest-digest>/`, where digest is the lowercase hex portion of the manifest hash;
- deterministic final files are `manifest.json`, canonical ordered `streams/<index>.payload`, `publication.json`, and `retention-proof.json`; hidden `.locks/` and `.staging/` paths are operational state and never evidence;
- `MarketBundleRepositoryPath`, publication result, and failure expose only canonical repository-relative POSIX paths, never absolute paths or exception text;
- `LocalMarketBundleRetentionProof` proves current verified retrievability only and binds Bundle ref, retention policy ref, relative manifest/publication/stream paths, and exact source/payload hashes; it has no wall clock, expiry, future guarantee, rebuild trace/window, freshness, decision-grade, or deployment claim;
- exact failure codes and global precedence are `invalid_input` → `stream_payload_mismatch` → `lock_unavailable` → `final_destination_conflict` → `staging_prepare_failed` → `staging_write_failed` → `staging_verification_failed` → `immutability_failed` → `atomic_finalize_failed` → `unmanaged_publication_state`;
- lock granularity is exact `(bundle_key, manifest_hash)` using an exclusive cooperative lock file, with no wall-clock expiry or automatic stale-lock breaking; different identities may publish concurrently;
- under the lock, an exact verified final directory is idempotent success with `already_published=true`; any other existing final identity path is `final_destination_conflict`; an existing staging path is never adopted or overwritten;
- publish uses exclusive temporary files, flush/fsync, staged exact-cover/hash verification, read-only hardening, same-filesystem atomic rename, final-parent fsync, and complete final verification before success;
- permission bits are accidental-mutation hardening only; canonical bytes, path exact-cover, hashes, and final verification remain integrity authority;
- every pre-final failure removes staging; finalize/final-fsync failure hides and removes any final path; inability to prove that no readable partial state remains returns `unmanaged_publication_state` and requires operator attention rather than automatic retry;
- old verified final identities are never overwritten or mutated, and lock-release residue after verified success does not rewrite semantic success;
- fixture `local-market-bundle-repository-v1` freezes first publish, exact idempotence, conflicts, per-manifest contention, different-identity concurrency, phase failures/cleanup, unmanaged state, tamper detection, current retrievability proof, repeat parity, and absence of absolute-path/clock leakage;
- G12D excludes G12E Reader/columnar storage, G12F parity, provider/network/database adapters, acquisition/normalization/validation, retention guarantee, deterministic rebuild proof, coverage, decision grade, Runtime imports, and deployment authorization.

Research authority：`docs/research/g12d-atomic-bundle-repository.md`。

Readiness evidence：

```text
Frozen readiness command                                             62 passed
Workspace import boundary                                            PASS (90 files)
mypy 2.3.0                                                            no issues (90 package source files)
LSP                                                                   TOML clean; Markdown servers silent-on-clean
uv lock --check                                                       PASS
git diff --check                                                      PASS
Python                                                                 3.13.5
```

Readiness artifact hashes：

```text
g12d-atomic-bundle-repository.md                                      sha256:4fa20891348aeec107f4b7054aa94c5756e141c5278a1e869c627d5ef8a0c68e
g12d.md                                                               sha256:76bd2049212c113fab78dce94afcfb14b1f6f8f1ccaa03aa7b736696d3fa50c5
import-boundaries.toml                                                sha256:66d5d58eb8544b3d7b995921ab20845c5af75a1af6bd6255b2f5af885966713d
g12d-readiness-pytest.xml                                             sha256:9fbee8847ca1677cd447054a2ca3414c307410c9208d72e66daeffef6166886e
g12d-readiness-import-boundary-report.json                            sha256:47e95ba47a4501ba965f6758abd62aa448805bcf57b82c053fbb778f11c74976
uv.lock                                                               sha256:a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
```

Contract freeze commit：`8d9a2f9ac0cfc9fbacdf15004303438d3371f251`。

PASSED evidence：

```text
Focused G12D contract/golden/architecture                              21 passed
Frozen G12D acceptance                                                 118 passed
Workspace import boundary                                              PASS (91 files)
mypy 2.3.0                                                             no issues (91 package source files)
LSP                                                                    clean (6 changed Python files)
Full repository suite                                                  1303 passed
uv lock --check                                                        PASS
git diff --check                                                       PASS
Python                                                                  3.13.5
```

PASSED artifact hashes：

```text
local-market-bundle-repository-v1.expected.json                        sha256:6158e9745c04e2bf7592e7946801adf8eebe9cdc2f70dfc2a89601af45eafff0
g12d-pytest.xml                                                        sha256:c66f30139832ef5484c1c0fd2fe585b46698519a73c5d13a76aa97aa2030eb55
g12d-import-boundary-report.json                                       sha256:7b1236cd6380133fc076d795c84699e96dc8af1a72f9cca9ff2fab6eaac83359
g12d-atomic-bundle-repository.md                                       sha256:4fa20891348aeec107f4b7054aa94c5756e141c5278a1e869c627d5ef8a0c68e
g12d.md                                                                 sha256:76bd2049212c113fab78dce94afcfb14b1f6f8f1ccaa03aa7b736696d3fa50c5
import-boundaries.toml                                                 sha256:66d5d58eb8544b3d7b995921ab20845c5af75a1af6bd6255b2f5af885966713d
uv.lock                                                                sha256:a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
```

Implementation commit：`7df91f381a1635d3d748ff08f83504107c2a41f4`。

## 97. G12E Local Persisted MarketBundle Reader Acceptance Card

```yaml
id: G12E
status: PASSED
passed_commit: 8cfc36e77a444c47e820959328d4e480ad46fe7e
depends_on:
  - G12D
  - WP-06A
owner_package: market-data-contracts
allowed_grade: development
public_interface:
  - crypto_quant_market_data.LocalMarketBundleReader
test_commands:
  readiness: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/market_data/bundles tests/bundle_builder/publication tests/runtime/timeline tests/runtime/engine/test_g06_synthetic_cash_journey.py
  contract: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/market_data/bundles/test_local_market_bundle_reader.py
  fixture: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/market_data/bundles/test_local_market_bundle_reader_golden.py
  architecture: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/architecture/test_g12e_local_reader_boundary.py tests/architecture/test_g12d_local_repository_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py
  acceptance: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/market_data/bundles tests/bundle_builder/publication tests/runtime/timeline tests/runtime/engine/test_g06_synthetic_cash_journey.py tests/architecture/test_g12d_local_repository_boundary.py tests/architecture/test_g12e_local_reader_boundary.py tests/architecture/test_import_boundary_mutations.py tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g12e-pytest.xml
  import_boundary: PYTHONDONTWRITEBYTECODE=1 uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g12e-import-boundary-report.json
  static_types: uvx --from mypy==2.3.0 mypy --python-version 3.13 packages/*/src
  full_suite: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q
artifacts:
  - docs/research/g12e-persisted-market-bundle-reader.md
  - tests/fixtures/market_data/local-reader/local-market-bundle-reader-v1.expected.json
  - build/acceptance/g12e-pytest.xml
  - build/acceptance/g12e-import-boundary-report.json
implementation_commit: 8cfc36e77a444c47e820959328d4e480ad46fe7e
approved_on: 2026-08-13
```

Frozen contract：

- G12E adds one concrete `LocalMarketBundleReader` and one Market Data root export; it implements the existing WP-06A `MarketBundleReader` Protocol and adds no second Protocol, Cursor, wrapper function, repository abstraction, callback, registry, factory, or codec plugin;
- the only constructor seam is `LocalMarketBundleReader.open(*, repository_root: Path, bundle_ref: MarketBundleRef) -> LocalMarketBundleReader`; root must be one exact absolute local `Path`, remains operational only, and never enters Bundle identity, Cursor evidence, canonical output, or error text;
- final location is derived only from G12D identity as `bundles/<bundle_key>/<manifest-digest>/`; G12E does not accept a caller-supplied manifest path, stream path, URI, provider connection, or mutable repository handle;
- open is all-or-nothing and verifies the complete G12D publication before returning: exact root entries, no symlinks, read-only hardening, canonical Manifest/publication/retention JSON bytes, exact cross-file path/hash linkage, `MarketBundleRef.from_manifest(manifest)` parity, exact declared stream set, and every stream payload SHA-256;
- v1 stream payload representation is exactly the G12C/G12D committed `canonical_bytes(tuple(events_for_stream))`; G12E does not infer codecs, generate a sidecar, reinterpret bytes as Parquet/Arrow, or expose DataFrame/columnar objects;
- decoded values must be exact canonical MarketEvent envelopes. G12E reconstructs public Domain/Market Data value types, byte-compares canonical encoding, then reuses `InMemoryMarketBundleReader` validation for stream identity, event-ID uniqueness, coverage, declaration, count, ordering-key uniqueness, and content-hash parity;
- malformed repository state, canonical JSON, manifest/ref linkage, event envelope, path cover, writable/symlink entry, missing/extra file, count/order/hash mismatch, or tampering fails closed with `MarketBundleIntegrityError` before any Reader is returned; errors do not expose absolute paths, raw bytes, exception text, PID, hostname, or clock;
- after open, `validate_requirements`, `open_cursor`, `read_batch`, and `resume_cursor` preserve exact WP-06A behavior, typed `InputValidationFailure`, `MarketBundleStreamError`, immutable Cursor identity, exhausted-Cursor behavior, and batch-size-independent event ID/hash sequence;
- event sequence is the already-committed canonical stream order by `(available_time, phase.rank, phase.code, source_sequence)`; G12E adds no current-time, cutoff, revision-selection, resampling, coverage, or late-arrival policy;
- Reader performs no lazy partial verification and no global mutable cache. Current retrievability is checked only during open; G12E makes no future-retention, rebuild, freshness, decision-grade, or deployment claim;
- fixture `local-market-bundle-reader-v1` freezes exact G12D open, one/multiple stream reads, page sizes, exhausted/resumed/cross-Bundle/Cross-stream Cursors, requirements, all integrity failures, repeat parity, and absence of absolute-root/clock leakage;
- production imports remain provider-neutral and offline through public roots only; no Builder, Runtime, Kernel, source adapter, Pandas, Parquet, Arrow, network, database, subprocess, vendor SDK, or wall-clock dependency;
- G12E defers columnar packaging. A future Parquet/Arrow Reader requires a preceding Builder-owned, separately hashed representation manifest and publication contract; an unhashed sidecar is forbidden.

Research authority：`docs/research/g12e-persisted-market-bundle-reader.md`。

Readiness evidence：

```text
Frozen readiness command                                             32 passed
Workspace import boundary                                            PASS (91 files)
mypy 2.3.0                                                            no issues (91 package source files)
LSP                                                                   Markdown servers silent-on-clean
uv lock --check                                                       PASS
git diff --check                                                      PASS
Python                                                                 3.13.5
```

Readiness artifact hashes：

```text
g12e-persisted-market-bundle-reader.md                               sha256:1395d34f1da5f6ccd369ebf10a6c9d28a7284eb65f2089283fb1000010bcbfc8
g12e.md                                                               sha256:ff2b3a74ed758c4d31458eaa14a5854cc47ea90350d9c778ac38e54417b41ce9
import-boundaries.toml                                                sha256:66d5d58eb8544b3d7b995921ab20845c5af75a1af6bd6255b2f5af885966713d
g12e-readiness-import-boundary-report.json                           sha256:7b1236cd6380133fc076d795c84699e96dc8af1a72f9cca9ff2fab6eaac83359
uv.lock                                                               sha256:a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
```

Contract freeze commit：`e43f0f3`。

PASSED evidence：

```text
Focused G12E contract/golden/architecture                              10 passed
Frozen G12E acceptance                                                  80 passed
Workspace import boundary                                              PASS (92 files)
mypy 2.3.0                                                             no issues (92 package source files)
LSP                                                                    clean (6 changed Python files)
pi-lens edited-file review                                             no findings across 6 files
Full repository suite                                                  1313 passed
uv lock --check                                                        PASS
git diff --check                                                       PASS
Python                                                                  3.13.5
```

PASSED artifact hashes：

```text
local-market-bundle-reader-v1.expected.json                            sha256:10660fd05b88a66d3f17fb60cb63252d6916a8e3c34b0b68475fd1aad4b237ec
g12e-pytest.xml                                                        sha256:77b6f20f370ef391656692cdca86e11428e952ce55d55295e321e661402fdd72
g12e-import-boundary-report.json                                       sha256:e2ec75a4dd3761ae719f677960d27fd923012fb99dce804685d6cf90ac0a5139
import-boundaries.toml                                                 sha256:66d5d58eb8544b3d7b995921ab20845c5af75a1af6bd6255b2f5af885966713d
uv.lock                                                                sha256:a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
```

Implementation commit：`8cfc36e77a444c47e820959328d4e480ad46fe7e`。

## 98. G12C Bundle Validation and Manifest Acceptance Card

```yaml
id: G12C
status: PASSED
passed_commit: e307ffb5886fef14705c4d33d4ab9e6eda098c3f
depends_on:
  - G12B
owner_package: market-bundle-builder
allowed_grade: development
public_interface:
  - crypto_quant_bundle_builder.BundleValidationFailureCode
  - crypto_quant_bundle_builder.BundleValidationFailure
  - crypto_quant_bundle_builder.BundleValidationOutcome
  - crypto_quant_bundle_builder.validate_market_bundle_v1
test_commands:
  readiness: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/market_data/bundles tests/bundle_builder/normalization tests/runtime/timeline tests/runtime/engine/test_g06_synthetic_cash_journey.py
  contract: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/bundle_builder/validation/test_bundle_validation.py
  fixture: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/bundle_builder/validation/test_bundle_validation_golden.py
  architecture: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/architecture/test_g12c_bundle_validation_boundary.py tests/architecture/test_g12b_synthetic_jsonl_boundary.py tests/architecture/test_g12a_source_snapshot_boundary.py tests/architecture/test_import_boundary_mutations.py tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py
  acceptance: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/bundle_builder/source_snapshots tests/bundle_builder/normalization tests/bundle_builder/validation tests/market_data/bundles tests/runtime/timeline tests/runtime/engine/test_g06_synthetic_cash_journey.py tests/architecture/test_g12a_source_snapshot_boundary.py tests/architecture/test_g12b_synthetic_jsonl_boundary.py tests/architecture/test_g12c_bundle_validation_boundary.py tests/architecture/test_import_boundary_mutations.py tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g12c-pytest.xml
  import_boundary: PYTHONDONTWRITEBYTECODE=1 uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g12c-import-boundary-report.json
  static_types: uvx --from mypy==2.3.0 mypy --python-version 3.13 packages/*/src
  full_suite: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q
artifacts:
  - docs/research/g12c-bundle-validation-contract.md
  - tests/fixtures/market_data/validation/synthetic-jsonl-bundle-validation-v1.expected.json
  - build/acceptance/g12c-pytest.xml
  - build/acceptance/g12c-import-boundary-report.json
implementation_commit: null
approved_on: null
```

Frozen contract：

- G12C adds one generic, pure Builder module and exactly four root exports: `BundleValidationFailureCode`, `BundleValidationFailure`, `BundleValidationOutcome`, and `validate_market_bundle_v1`;
- the function accepts only `bundle_key`, positive `schema_version`, half-open `UtcInstant` coverage, `instrument_catalog_hash`, and an exact `tuple[MarketEvent, ...]`; it accepts no capabilities, manifests, partition IDs, paths, refs, Snapshot, normalization result, protocol, callback, registry, or plugin;
- a nonempty caller-order subsequence with one `stream_key` is the G12C logical in-memory partition; its existing `MarketStreamManifest` is the complete partition hash evidence; physical layout/chunks/files remain G12D+;
- source provenance at this Gate is exact `MarketEvent.source_key`/`source_hash`, transitively committed through Event, stream, and Bundle hashes; authenticated G12A/G12B replay provenance is excluded;
- success retains each per-stream caller subsequence unchanged, derives `MarketStreamManifest.from_events()`, derives capabilities exactly from actual stream manifests, and calls `MarketBundleManifest.build()`; `MarketBundleManifest.content_hash` and external `MarketBundleRef.from_manifest()` parity remain the only success identities;
- validation never uses `InMemoryMarketBundleReader` and never sorts to repair input;
- failure codes are exactly `invalid_input`, `duplicate_event_id`, `event_outside_coverage`, `stream_classification_mismatch`, `duplicate_stream_ordering_key`, and `stream_order_regression`;
- `BundleValidationFailure` contains only code, optional stream key, and optional zero-based original input position; its stable canonical body is `market_bundle_v1_validation_failure` schema v1 and `failure_hash = canonical_sha256(body)`;
- exact global failure precedence is invalid header/member → duplicate Bundle-wide Event ID → Event-time coverage → mixed `(event_type, capability)` inside a stream → duplicate local ordering key → local ordering regression; the earliest original input position wins within one category;
- coverage means only `coverage_start <= event.event_time < coverage_end_exclusive`; it is not completeness evidence;
- Event IDs are unique Bundle-wide; ordering keys are unique and strictly increasing only within one stream; non-contiguous SourceSequence succeeds, while equal ordering keys across streams remain WP-06B Timeline authority;
- all failure paths are atomic and return no partial manifest, stream, Event, payload, trace, path, or exception text;
- empty Events structurally succeed with empty streams/capabilities but make no coverage, retention, publication, decision-grade, or deployment claim;
- static fixture `synthetic-jsonl-bundle-validation-v1` must freeze manifest/stream/ref repeat parity, source sensitivity, structured failure precedence, atomic later failure, empty input, non-contiguous sequence, and cross-stream handoff;
- runtime/kernel may not import the Builder validator; G12C may not mutate frozen Market Data schemas or own Reader, repository, publication, global Timeline, Bars, coverage reports, provider acquisition, decision-grade, or deployment authorization.

Research authority：`docs/research/g12c-bundle-validation-contract.md`。

Readiness evidence：

```text
Frozen readiness command                                             39 passed
Workspace import boundary                                            PASS (89 files)
mypy 2.3.0                                                            no issues (89 package source files)
LSP                                                                   TOML clean; Markdown servers silent-on-clean
Auxiliary diagnostics                                                 pre-existing information-only typos outside G12C card
uv lock --check                                                       PASS
git diff --check                                                      PASS
Python                                                                 3.13.5
```

Readiness artifact hashes：

```text
g12c-bundle-validation-contract.md                                   sha256:a892c592d6a877ba3ffd65f108bbbddece47e38a7a2edc35db6e73ac0d8149b6
g12c.md                                                              sha256:d322fa27aec03883f90ca714c0efc175d48ad2af6e0f71d9a877d1a7043144e5
import-boundaries.toml                                               sha256:d15abacac6ee5b460d3f9a6ec4cbce47ac705320d7c3c80c398267dd5128b938
g12c-readiness-pytest.xml                                            sha256:00229ad7f24a0f82192c67c70ee29d6cf70452b34beaa7f8be45c540e15d5c5b
g12c-readiness-import-boundary-report.json                           sha256:9871d3b48e7162e74c90682bf773bc536a1c269aae6034ee6a4c007e7b83716f
uv.lock                                                              sha256:a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
```

Contract freeze commit：`719d9a0491e3b196248a7b9f1b57e8eb41e1c199`。

Implementation validation：

```text
Focused G12C contract/golden/architecture                               24 passed
Frozen acceptance command                                              106 passed
Full repository suite                                                  1291 passed
Workspace import boundary                                             PASS (90 files)
mypy 2.3.0                                                             no issues (90 package source files)
Primary LSP                                                            no diagnostics across 7 changed Python files
pi-lens edited-file review                                             no findings across 7 files
uv lock --check                                                        PASS
git diff --check                                                       PASS
Python                                                                  3.13.5
```

Artifact hashes：

```text
synthetic-jsonl-bundle-validation-v1.expected.json                    sha256:fe7d68cedd99461bb315310ee181e648e30159c41767005fafcc30177196ac1f
g12c-pytest.xml                                                       sha256:2e9f1597be9728ec967b41879837db0f18a52f8ef9f5b016757ff238434e227f
g12c-import-boundary-report.json                                      sha256:95bd23871a345174caa07f8b7e0c36a22aa74a607cf623ae8c76e7137b978634
uv.lock                                                               sha256:a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
```

Implementation commit：`e307ffb5886fef14705c4d33d4ab9e6eda098c3f`。

## 99. G12F Reader and Partition Parity Acceptance Card

```yaml
id: G12F
status: PASSED
passed_commit: f9e563d520d4a820bafe0a372cf17c32db70e995
depends_on:
  - G12E
  - G07
  - WP-00C
owner_package: repository-root parity tooling
allowed_grade: development
public_interface:
  - tools/parity/market_bundle_reader.py
  - tools/parity/run_market_bundle_reader_parity.py
  - market-bundle-reader-g12f-parity-report-v1
  - no production package export
test_commands:
  readiness: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/parity/test_comparator_contract.py tests/market_data/bundles tests/runtime/timeline tests/runtime/engine/test_g06_synthetic_cash_journey.py tests/runtime/integration/test_g07_auditable_run.py
  contract: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/parity/test_market_bundle_reader_parity.py
  fixture: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/parity/test_market_bundle_reader_parity_golden.py
  architecture: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/architecture/test_g12f_reader_parity_boundary.py tests/architecture/test_g12e_local_reader_boundary.py tests/architecture/test_repository_cleanliness.py
  acceptance: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/parity/test_market_bundle_reader_parity.py tests/parity/test_market_bundle_reader_parity_golden.py tests/parity/test_comparator_contract.py tests/market_data/bundles tests/runtime/timeline tests/runtime/engine/test_g06_synthetic_cash_journey.py tests/runtime/integration/test_g07_auditable_run.py tests/architecture/test_g12f_reader_parity_boundary.py tests/architecture/test_g12e_local_reader_boundary.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g12f-pytest.xml
  import_boundary: PYTHONDONTWRITEBYTECODE=1 uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g12f-import-boundary-report.json
  static_types: uvx --from mypy==2.3.0 mypy --python-version 3.13 packages/*/src
  full_suite: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q
artifacts:
  - docs/research/g12f-reader-partition-parity.md
  - tests/parity/contracts/market-bundle-reader-g12f-v1.json
  - tests/parity/fixtures/market-bundle-reader-g12f-v1/report.expected.json
  - build/acceptance/g12f-parity-report.json
  - build/acceptance/g12f-pytest.xml
  - build/acceptance/g12f-import-boundary-report.json
implementation_commit: f9e563d520d4a820bafe0a372cf17c32db70e995
approved_on: 2026-08-13
```

Frozen contract：

- G12F compares the two real adapters at the existing `MarketBundleReader` seam, `InMemoryMarketBundleReader` and `LocalMarketBundleReader`; it adds no production export, second Reader/Cursor, Runtime mode, storage abstraction, or comparator algorithm;
- v1 **logical partition** means one `MarketStreamManifest` declaration and its exact ordered canonical Event tuple. Physical Parquet/Arrow partitioning, row groups, codec choices, and memory-map modes are not represented by G12D/G12E and cannot be claimed by G12F;
- one immutable G12D Bundle ref, Manifest, and complete Event set seed both Reader projections. Absolute local root, Reader class name, Reader batch size, Timeline batch size, temporary paths, Attempt IDs, and Evidence Manifest hashes are operational or attempt evidence and do not enter economic parity identity;
- parity matrix exact-covers Reader adapters `in_memory|local_persisted`, Reader batch sizes `1|2|larger-than-stream`, Timeline batch sizes `1|2|larger-than-output`, and direct Engine plus G07 auditable Runner paths;
- every matrix cell must preserve exact Bundle/Manifest identity, per-stream Event ID/hash sequence, Timeline Event ID/hash/segment sequence, terminal Timeline Cursor evidence, execution-case hash, Engine result hash, Trace hash, Ledger state hash, Snapshot hash, Run End report hash, and G07 execution result hash;
- G07 retains distinct Attempt and Evidence identities. G12F requires their bound execution result hash to match; it never requires Attempt ID or Evidence Manifest hash equality and never weakens G07 atomic evidence/publication rules;
- Comparator Contract v1 remains the only comparison engine. G12F uses exact/sequence rules only, with no tolerance, global epsilon, `approved_change`, hidden field, or not-comparable row; a passing G12F verdict is `MATCH`;
- first divergence must expose the earliest differing comparison layer and, for stream/Timeline sequences, the stream key, zero-based Event position, and expected/actual Event ID/hash. A later aggregate result match cannot hide an earlier stream or Timeline divergence;
- malformed, missing, duplicated, reordered, unclassified, or forged Bundle/stream/Timeline/execution evidence fails closed. Report bytes are canonical, repeatable, and repository-root independent;
- parity tooling imports only stdlib and existing `legacy_migration.parity` helpers. It does not import Builder, Runtime Engine/Runner, Market Data Reader implementations, Trading Kernel, provider SDK, network, database, subprocess, secrets, dynamic imports, or wall clock; tests/support own projection generation;
- G12F proves adapter and operational batching invariance only. It does not prove source completeness, provider correctness, future retention, deterministic rebuild, columnar performance, decision-grade eligibility, live readiness, or deployment authorization; qualification flags remain false;
- a future physical partition or Parquet/Arrow parity extension requires a preceding Builder-owned, separately hashed representation manifest and atomic publication linkage. An unhashed sidecar or reopening G12C–E is forbidden.

Research authority：`docs/research/g12f-reader-partition-parity.md`。

Readiness evidence：

```text
Frozen G12F readiness command                                        41 passed
Workspace import boundary                                            PASS (92 files)
mypy 2.3.0                                                           no issues (92 package source files)
LSP                                                                  Markdown servers silent-on-clean after refresh
pi-lens current-turn review                                          no warnings
uv lock --check                                                      PASS
git diff --check                                                     PASS
Python                                                               3.13.5
```

Readiness artifact hashes：

```text
g12f-reader-partition-parity.md                                      sha256:75726edb505cd6df3252194a8421574c7d36c19aec442ce0c2afa7ddbcd5c227
g12f.md                                                              sha256:c052094f5071fc41bd3ae512f0cd1bb11af1e3a6c0ef75562d410b337cc462bd
import-boundaries.toml                                               sha256:66d5d58eb8544b3d7b995921ab20845c5af75a1af6bd6255b2f5af885966713d
g12f-readiness-pytest.xml                                            sha256:f88c61550a33277e15562361406e9c808d560abb4dc4948f90e9c748099f816e
g12f-readiness-import-boundary-report.json                           sha256:e2ec75a4dd3761ae719f677960d27fd923012fb99dce804685d6cf90ac0a5139
uv.lock                                                              sha256:a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
```

Contract freeze commit：`300d99b162dba5c4b2d1edcaddfaf2eb4aa5adf1`。

PASSED evidence：

```text
Focused G12F contract/golden/architecture                              8 passed
Frozen G12F acceptance                                                54 passed
Workspace import boundary                                            PASS (92 files)
mypy 2.3.0                                                           no issues (92 package source files)
LSP                                                                  clean (6 changed Python files)
pi-lens edited-file review                                           no findings across 6 files
Full repository suite                                                1321 passed
uv lock --check                                                      PASS
git diff --check                                                     PASS
Python                                                               3.13.5
```

PASSED artifact hashes：

```text
market-bundle-reader-g12f-v1.json                                    sha256:57e40c6a9e15720a84f815e07f7e2184a2d680faf6ab393356dd023901f9617f
expected.json                                                        sha256:46bf1d86925c736562972a8eea7a3a26c8603877bbfb091b47823c67c483094e
actual.json                                                          sha256:46bf1d86925c736562972a8eea7a3a26c8603877bbfb091b47823c67c483094e
report.expected.json                                                 sha256:60c22b847b8e5daae78681162148fed5034d3879ebee97ffda14b533295d3f1a
g12f-pytest.xml                                                      sha256:551bd140f684245eb21b661e79c22576e543d61d025ebd380058a1476da4e8d1
g12f-import-boundary-report.json                                     sha256:e2ec75a4dd3761ae719f677960d27fd923012fb99dce804685d6cf90ac0a5139
uv.lock                                                              sha256:a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
```

Implementation commit：`f9e563d520d4a820bafe0a372cf17c32db70e995`。

## 100. G11I Portfolio Strategy Invocation and Atomic DecisionBatch Acceptance Card

```yaml
id: G11I
status: PASSED
passed_commit: 43735440ca5c60e2b3ae9c536c4a77411db317d0
depends_on:
  - G11A
  - G11B
  - G11C
  - G11D
  - G11E
  - G11F
  - G11G
  - G11H
  - G04
owner_package: backtest-runtime strategy
allowed_grade: development
public_interface:
  - crypto_quant_backtest.PortfolioStrategyRegistration
  - crypto_quant_backtest.PortfolioStrategyInvocationContext
  - crypto_quant_backtest.PortfolioStrategyInvocation
  - crypto_quant_backtest.PortfolioStrategyInvocationFailureCode
  - crypto_quant_backtest.PortfolioStrategyInvocationStatus
  - crypto_quant_backtest.PortfolioStrategyInvocationOutput
  - crypto_quant_backtest.invoke_portfolio_strategies
test_commands:
  contract: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/runtime/strategy_runtime
  g04_exact_instant: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/domain/decisions tests/kernel/validation tests/kernel/decisions tests/kernel/integration/test_target_materialization_journey.py
  boundary: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/architecture/test_g11i_strategy_runtime_boundary.py tests/architecture/test_g11b_observation_causality_boundary.py tests/architecture/test_g11c_universe_boundary.py tests/architecture/test_g11d_observation_window_boundary.py tests/architecture/test_g11e_decision_schedule_boundary.py tests/architecture/test_g11f_strategy_state_boundary.py tests/architecture/test_g11g_random_stream_boundary.py tests/architecture/test_g11h_model_revision_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  acceptance: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/runtime/strategy_runtime tests/runtime/observations tests/runtime/universe tests/runtime/observation_windows tests/runtime/decision_schedule tests/runtime/strategy_state tests/runtime/random_streams tests/runtime/model_revisions tests/domain/decisions tests/kernel/validation tests/kernel/decisions tests/kernel/integration/test_target_materialization_journey.py tests/architecture/test_g11i_strategy_runtime_boundary.py tests/architecture/test_g11b_observation_causality_boundary.py tests/architecture/test_g11c_universe_boundary.py tests/architecture/test_g11d_observation_window_boundary.py tests/architecture/test_g11e_decision_schedule_boundary.py tests/architecture/test_g11f_strategy_state_boundary.py tests/architecture/test_g11g_random_stream_boundary.py tests/architecture/test_g11h_model_revision_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g11i-pytest.xml
  import_boundary: PYTHONDONTWRITEBYTECODE=1 uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g11i-import-boundary-report.json
  static_types: uvx --from mypy==2.3.0 mypy --python-version 3.13 packages/*/src
  full_suite: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q
fixture_ids:
  - portfolio-strategy-invocation-v1
  - atomic-decision-batch-simulation-instant-v2
  - target-materialization-same-utc-v2
artifacts:
  - docs/research/g11i-portfolio-strategy-invocation.md
  - tests/fixtures/runtime/portfolio-strategy-invocation-v1.json
  - tests/fixtures/kernel/atomic-decision-batch-simulation-instant-v2.json
  - tests/fixtures/kernel/target-materialization-same-utc-v2.json
  - build/acceptance/g11i-pytest.xml
  - build/acceptance/g11i-import-boundary-report.json
failure_contracts:
  - duplicate-sleeve-or-cross-evidence-mismatch-reaches-callback
  - ineligible-entry-invokes-callback-validator-or-collector
  - callback-lookup-exception-or-malformed-output-escapes-isolation
  - invalid-state-or-rng-transition-is-accepted-as-future-authority
  - validation-failure-produces-partial-batch-state-or-handoff
  - active-success-calls-atomic-collector-zero-or-multiple-times
  - registration-input-order-changes-invocation-batch-or-handoff-identity
  - executable-strategy-object-does-not-match-attested-build-artifact
  - bare-model-artifact-bypasses-g11h-timeline-selection-proof
  - detached-or-future-strategy-checkpoint-enters-context
  - advanced-rng-or-state-does-not-match-prior-successful-invocation
  - forged-public-record-splices-unrelated-context-transition-or-batch
  - same-utc-distinct-full-instants-collapse-or-cannot-continue
  - exact-and-legacy-instant-modes-mix-without-fail-closed-result
  - legacy-g04-v1-canonical-bytes-id-or-hash-changes
  - exact-instant-state-is-flattened-by-allocation-risk-mark-or-sizing
  - g11i-adds-second-validator-batch-or-downstream-economic-path
  - g11i-claims-decision-grade-live-or-deployment-authorization
evidence:
  - canonical-two-sleeve-invocation-and-registration-order-parity
  - warmup-state-rng-without-decision-batch
  - ineligible-zero-callback-context-binding
  - callback-output-state-rng-validation-and-batch-failure-precedence
  - complete-attempted-state-and-rng-audit-with-no-partial-authority
  - checkpoint-prior-output-and-model-timeline-forgery-controls
  - exact-one-validator-call-site-and-collector-call-site-boundary
  - same-utc-full-simulation-instant-v2-chain-and-downstream-journey
  - byte-identical-legacy-g04-v1-goldens
  - static-golden-public-api-import-and-import-boundary-reports
implementation_commit: 43735440ca5c60e2b3ae9c536c4a77411db317d0
approved_on: 2026-08-14
```

Frozen contract：

1. G11I只新增one offline `crypto_quant_backtest.strategy_runtime` orchestration seam与七个root exports；Generic Engine、Runner、Timeline与TargetStream不新增G11I branch；
2. `PortfolioStrategyRegistration` exact绑定one `DecisionBatchExpectation`、immutable `BuildArtifactRef(role=DECISION_SOURCE)`、executable Strategy object、G11B Observation results、G11C Universe、G11D windows、G11F checkpoint、G11G named streams、G11H model timelines及optional prior successful G11I output；
3. Executable Strategy必须暴露与registration exact相同的immutable artifact ref。Callback/module path、object address、exception text、traceback、Attempt ID与wall clock不得进入canonical identity；installed-byte attestation remains external build authority；
4. Context是least-authority immutable value，只绑定expectation、shared G11E entry/eligibility、Observation result/query/trace hashes、Universe selection、window/causality hashes、previous Target/State/checkpoint/output、RNG hashes、model timeline/selected artifact hashes与Instrument Catalog hash；不暴露Bundle、Reader、Ledger、account state、filesystem、network、process或clock；
5. Registration在任何callback前按`(strategy_id,sleeve_id)` canonical sort并拒绝duplicate Sleeve、future/mismatched Observation/Universe/window/model/checkpoint/prior state evidence。Input order不得改变callback order、invocation、batch、state、output或handoff hash；
6. `strategy_invocation_eligible=false` exact返回`INELIGIBLE`，零callback、零Validator、零Collector；但output仍绑定完整suppressed context evidence，因此State/RNG/artifact变化必须改变identity；
7. 每个callback exact接收自己的Context与prior StrategyState，返回one `StrategyDecisionCandidate`、next `StrategyState`与next named streams tuple。Lookup/call exception、malformed tuple、invalid State或invalid RNG均per-Sleeve隔离，其他callback继续执行；
8. 所有捕获Candidate必须通过existing `StrategyOutputValidator`，不得内联第二个decoder/validator。Invocation/output/state/RNG failure precedence高于validation failure；failure code稳定且不依赖exception message；
9. Eligible Warmup成功保存validated invocation、StrategyStateTransition与next RNG evidence，但不调用Collector、不生成DecisionBatch或handoff。Failed attempts保留已计算after-state/RNG audit hashes，但不得成为后续accepted checkpoint/RNG authority；
10. Eligible Active仅在所有callback/output/state/RNG/validation成功后调用existing `AtomicDecisionBatchCollector.collect(...)` exact一次。G11I不得直接构造`DecisionBatch`或`LatestSleeveDecisionState`，不得产生partial batch/state/downstream object；
11. Successful future continuation必须提供strictly earlier full-instant `StrategyCheckpoint`。Advanced State/RNG必须exact匹配prior successful G11I invocation的transition、invocation hash与next streams；Active continuation的prior decision state必须match prior output atomic state；genesis streams必须counter zero；
12. G11H evidence必须作为`ModelRevisionTimeline`进入Context并同时绑定timeline hash与selected terminal artifact hash。Bare/orphan/forked/future model ref不能绕过G11H lineage/visibility authority；G11I不加载、训练、rank或执行model bytes；
13. Public Invocation/Output constructors必须重新验证Context、eligibility、catalog、validation、transition、RNG与atomic batch exact-cover，拒绝空invocation、cross-Sleeve splicing、unrelated batch或forged success status；
14. G11E允许same UTC且phase/source sequence不同的legal full `SimulationInstant` entries。G04 additive exact-instant mode必须允许strict earlier same-UTC state继续，并使两个entry产生不同decision/batch/state/handoff identity；equal/later或ambiguous legacy same-UTC state fail closed；
15. Exact-instant支持使用optional keyword-only fields与v2 identities。字段缺失时legacy G04 v1 constructors、canonical bytes、fixture hashes与`decision-batch-v1:` ID exact保持不变；exact mode使用v2 ID且拒绝UTC/full-instant mismatch与exact→legacy downgrade；
16. Exact instant在opt-in v2路径继续绑定Portfolio Snapshot、Allocation、Risk、Resolved Mark、Sizing与Active Target。任一UTC-only downstream evidence与exact state混用必须structured fail closed，不得把phase/sequence静默压平；
17. Invocation canonical record保存Context、Strategy artifact、validation result、attempted State transition、attempted next RNG hashes与stable failure code。Aggregate output保存status、entry/eligibility、catalog、ordered invocations、existing atomic result与active-success-only handoff hash；
18. G11I始终`decision_grade_eligible=false`、`deployment_authorized=false`。G12拥有真实数据完整性与资格；G11J拥有precomputed-vs-Strategy downstream parity；
19. Production module不包含Registry、Factory、Executor、Protocol、thread/process/async runtime、dynamic import、filesystem/network/provider/model SDK、wall clock或global RNG；不新增第二套Allocation、Risk、Planning、Execution、Accounting、Runner或Evidence path；
20. Static evidence至少冻结Active two-Sleeve success、registration-order parity、Warmup、ineligible、callback/output/state/RNG/validation/batch failures、artifact/model/checkpoint/record forgery、Collector runtime call count、same-UTC v2 continuation、legacy v1 compatibility与full downstream exact-instant journey。

Research authority：`docs/research/g11i-portfolio-strategy-invocation.md`。

PASSED evidence：

```text
Focused G11I/G11A-H/G04 acceptance                              209 passed
Focused exact-instant and nearest regressions                    71 passed
Full repository suite                                          1350 passed
Workspace import boundary                                      PASS (93 files)
mypy 2.3.0                                                     no issues (93 package source files)
Primary LSP                                                    clean across 22 changed Python files
pi-lens project blocking diagnostics                           no errors across 153 scanned files
Legacy G04 v1 fixture hashes                                   byte-identical
uv lock --check                                                PASS
git diff --check                                               PASS
Python                                                          3.13.5
```

Artifact hashes：

```text
g11i-portfolio-strategy-invocation.md                           sha256:c331ad5808af2125f78907b27d6dc43874ae7a15bee1440bbd88de2e2073dbc3
portfolio-strategy-invocation-v1.json                          sha256:97ce7eae1a309436a0444d658327fd4ce1b7125d40132479db36a7ee945d9a49
atomic-decision-batch-simulation-instant-v2.json                sha256:c12342b9d0925237d3f8229b69a2a424cbfbb3345fc20cb5f7d003f871a5df63
target-materialization-same-utc-v2.json                        sha256:f551782dc9831bc77436e520f6c0f362b77932127b5d5ec9d8adf9b80860ec48
g11i-pytest.xml                                                sha256:a88ce8cd70fb5abc0daef82c84e135e0ab3e06f048b704f886581d0e6e18a356
g11i-import-boundary-report.json                               sha256:25d7011ff63aba5567f71c115a06000f33c4e653bbcc9d2096f449eddcc02673
import-boundaries.toml                                         sha256:66d5d58eb8544b3d7b995921ab20845c5af75a1af6bd6255b2f5af885966713d
uv.lock                                                        sha256:a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
```

Implementation commit：`43735440ca5c60e2b3ae9c536c4a77411db317d0`。

## 101. G11J Precomputed-vs-Strategy Downstream Parity Acceptance Card

```yaml
id: G11J
status: PASSED
passed_commit: 7387c0b667d6af29d82fd0e0a046d45a3387956d
depends_on:
  - G11I
  - G07
owner_package: repository-root parity tooling
allowed_grade: development
public_interface:
  - tools/parity/precomputed_strategy.py
  - tools/parity/run_precomputed_strategy_parity.py
  - precomputed-vs-strategy-g11j-parity-report-v1
  - no production package export
test_commands:
  contract: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/parity/test_precomputed_strategy_parity.py tests/parity/test_precomputed_strategy_parity_golden.py
  boundary: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/architecture/test_g11j_dual_entry_parity_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
  acceptance: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/parity/test_precomputed_strategy_parity.py tests/parity/test_precomputed_strategy_parity_golden.py tests/parity/test_comparator_contract.py tests/runtime/strategy_runtime tests/runtime/runner tests/runtime/execution_hash tests/runtime/integrity tests/runtime/engine tests/architecture/test_g11j_dual_entry_parity_boundary.py tests/architecture/test_g11i_strategy_runtime_boundary.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g11j-pytest.xml
  import_boundary: PYTHONDONTWRITEBYTECODE=1 uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g11j-import-boundary-report.json
  static_types: uvx --from mypy==2.3.0 mypy --python-version 3.13 packages/*/src
  full_suite: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q
fixture_ids:
  - precomputed-strategy-g11j-v1
artifacts:
  - docs/research/g11j-precomputed-strategy-parity.md
  - tests/parity/contracts/precomputed-strategy-g11j-v1.json
  - tests/parity/fixtures/precomputed-strategy-g11j-v1/expected.json
  - tests/parity/fixtures/precomputed-strategy-g11j-v1/actual.json
  - tests/parity/fixtures/precomputed-strategy-g11j-v1/sidecar.json
  - tests/parity/fixtures/precomputed-strategy-g11j-v1/report.expected.json
  - build/acceptance/g11j-pytest.xml
  - build/acceptance/g11j-import-boundary-report.json
failure_contracts:
  - precomputed-and-strategy-validated-target-snapshots-differ
  - confidence-reason-or-decision-evidence-is-normalized-away
  - source-v1-v2-batch-identities-enter-economic-comparison
  - source-batch-identity-difference-is-not-preserved-in-sidecar
  - allocation-risk-target-order-fill-fee-journal-or-result-diverges
  - later-hash-match-masks-earlier-economic-divergence
  - required-layer-is-missing-unclassified-or-reordered
  - substitute-tolerant-quantized-or-approved-change-contract-is-used
  - report-path-aliases-contract-expected-or-actual
  - contract-expected-actual-or-report-escapes-supplied-root
  - fixture-or-report-bytes-depend-on-repository-checkout-root
  - g11j-adds-production-runtime-economic-or-public-api-branch
  - comparator-report-is-claimed-as-source-provenance-authentication
  - g11j-claims-decision-grade-live-or-deployment-authorization
evidence:
  - real-precomputed-target-stream-entry
  - real-g11i-strategy-invocation-entry
  - equal-complete-normalized-validated-decisions-and-target-snapshots
  - explicit-distinct-v1-v2-source-batch-sidecar
  - independent-equal-resolved-cases-and-two-g07-attempts
  - exact-seventeen-layer-economic-projection
  - every-layer-mutation-and-missing-layer-negative-matrix
  - earliest-first-divergence-with-later-mutation
  - frozen-contract-substitution-and-policy-rejection
  - copied-root-repeatable-golden-report
  - static-architecture-and-no-public-export-boundary
implementation_commit: 7387c0b667d6af29d82fd0e0a046d45a3387956d
approved_on: 2026-08-14
```

Frozen contract：

1. G11J只新增repository-root parity tooling、test support、static contract/fixtures与architecture boundary；Engine、Runner、Timeline、TargetStream、Trading Kernel和package root exports均不新增G11J branch；
2. Dual-entry fixture分别执行existing `PrecomputedTargetStreamAdapter`与G11I `invoke_portfolio_strategies(...)`。Strategy entry继续使用existing `StrategyOutputValidator`与`AtomicDecisionBatchCollector`；G11J不新增Validator或Collector；
3. Source-neutral Candidate冻结confidence、reason、Decision evidence与TargetSnapshot。Layer 00 exact比较shared full `SimulationInstant`、complete validated Decisions和ordered TargetSnapshots，不得只比较weights或剥离Decision evidence；
4. Precomputed source batch保留legacy `decision-batch-v1` identity，Strategy source batch保留exact-instant `decision-batch-v2` identity。两者ID/hash必须不同并进入explicit sidecar；raw source batch identity不得进入source-neutral economic projection；
5. Normalization只为precomputed Decision补入shared target-event `SimulationInstant`。其余Strategy ID、decision/observation time、TargetSnapshot、confidence、reason与evidence均exact保持；
6. 两条entry分别组合equal `ResolvedExecutionCase` values并通过existing branchless Engine/G07 path执行。G07 Attempt/Evidence identities必须不同，而Semantic Run、case、domain与execution-result identities必须相等；
7. Exact parity层按numeric prefix冻结：normalized entry、DecisionBatch、Allocation、Portfolio Risk、Normalized Active Target、Order Plan/Intent、Order Event、Fill、Slippage、Fee、Financial Artifact、Journal、Ledger、final Snapshot、Run End、Trace与Execution Result hash；
8. Comparator Contract v1是唯一comparison engine。G11J wrapper固定`migration_mode=copy_with_parity`并直接复用`load_contract`、`run_comparison`与`invalid_report`；不得复制comparison algorithm；
9. Frozen contract exact包含17层及fixture/qualification/schema fields，rule path unique、sorted、non-overlapping，只允许`exact|sequence`。替代ID、缺层、额外层、tolerance、quantization、epsilon或`approved_change`全部BLOCKED；
10. Numeric layer order定义first-divergence precedence；sequence差异定位first zero-based item。任意later Trace/result hash相等不得掩盖earlier Allocation、Risk、Order、Fill、Fee或Journal差异；
11. CLI只接受`--root --contract --expected --actual --report`。Root必须是existing non-filesystem-root directory；所有evidence paths必须位于root内；report不得alias input，且以temporary replace原子写入；
12. Unsafe path返回`BLOCKED`/exit 2；malformed/unclassified/frozen-contract violation返回`invalid-contract`/exit 2；first economic difference返回`MISMATCH`/exit 1；all exact layers equal返回`MATCH`/exit 0；
13. Static generation test真实执行两条entry并将expected、actual、sidecar与checked-in fixtures exact比较。Copied-root golden证明report bytes不依赖repository checkout path；
14. CLI只证明supplied projections在frozen contract下相等，不重新生成projection、不读取sidecar，也不认证precomputed/Strategy provenance。两个identical substituted或malicious files仍可MATCH；source linkage authority属于dual-entry generation test；
15. Entry-only evidence仅包括TargetStream digest/schedule/source/injection、Strategy schedule/eligibility/artifact/checkpoint/context/invocation/state/output/handoff、source batch IDs/hashes及G07 Attempt/Evidence identities；normalization后不得排除任何economic object；
16. Qualification始终`decision_grade_eligible=false`、`deployment_authorized=false`。G11J不证明Provider correctness、market qualification、live readiness或deployment authorization。

Research authority：`docs/research/g11j-precomputed-strategy-parity.md`。

PASSED evidence：

```text
G11J parity contract/golden matrix                               67 passed
Frozen G11J/G11I/G07 acceptance                                198 passed
Full repository suite                                         1422 passed
Workspace import boundary                                      PASS (93 files)
mypy 2.3.0                                                     no issues (93 package source files)
Primary LSP                                                    clean across 7 changed Python files
pi-lens blocking diagnostics                                  no errors across 8 changed files
Derivative purity regression                                  54 passed
uv lock --check                                                PASS
git diff --check                                               PASS
Python                                                          3.13.5
```

Artifact hashes：

```text
g11j-precomputed-strategy-parity.md                            sha256:587d6fd1f279a00b1929997822746978ace5ffdb5a3e2463634731cb1e3e1e4b
precomputed-strategy-g11j-v1.json                             sha256:72356cb7be8fae03e6faa674be758f87b8a87337e5d67d6011274f6b2bfc1248
expected.json                                                  sha256:ff8ccefe1407f7f6d1aa8427706f9dcd7b22b57886b034069082663978e05811
actual.json                                                    sha256:ff8ccefe1407f7f6d1aa8427706f9dcd7b22b57886b034069082663978e05811
sidecar.json                                                   sha256:7f3390600473de53aa3e9d4dd5c27ead5c3e36a72cd0d1922fd45fd310bee1a4
report.expected.json                                           sha256:0d412cdf9144646bf4da574cd139c7ef55659a1c9402af19e397d6882d58f3dc
g11j-pytest.xml                                                sha256:b184279f58df1ec02023651b1e2ec5ad559e79a454f3191c9b207729426b3cef
g11j-import-boundary-report.json                               sha256:25d7011ff63aba5567f71c115a06000f33c4e653bbcc9d2096f449eddcc02673
import-boundaries.toml                                         sha256:66d5d58eb8544b3d7b995921ab20845c5af75a1af6bd6255b2f5af885966713d
uv.lock                                                        sha256:a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
```

Implementation commit：`7387c0b667d6af29d82fd0e0a046d45a3387956d`。

## 102. G12G Canonical Revisioned Bar Aggregation Acceptance Card

```yaml
id: G12G
status: PASSED
passed_commit: eefe4df3568776323881810a309ea09a47b379b7
depends_on:
  - G12B
  - G12C
owner_package: market-bundle-builder
allowed_grade: development
public_interface:
  - crypto_quant_bundle_builder.BarBucket
  - crypto_quant_bundle_builder.BarBucketPlan
  - crypto_quant_bundle_builder.BarDefinition
  - crypto_quant_bundle_builder.BarAggregationManifest
  - crypto_quant_bundle_builder.BarAggregationResult
  - crypto_quant_bundle_builder.BarAggregationFailureCode
  - crypto_quant_bundle_builder.BarAggregationFailure
  - crypto_quant_bundle_builder.BarAggregationOutcome
  - crypto_quant_bundle_builder.aggregate_bars_v1
test_commands:
  contract: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/bundle_builder/bar_aggregation
  g11d_integration: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/runtime/observation_windows/test_g12g_bar_window_integration.py
  boundary: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/architecture/test_g12g_bar_aggregation_boundary.py tests/architecture/test_import_boundary_mutations.py tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py
  acceptance: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q tests/bundle_builder/normalization tests/bundle_builder/validation tests/bundle_builder/bar_aggregation tests/market_data/bundles tests/runtime/observation_windows tests/architecture/test_g12b_synthetic_jsonl_boundary.py tests/architecture/test_g12c_bundle_validation_boundary.py tests/architecture/test_g12g_bar_aggregation_boundary.py tests/architecture/test_import_boundary_mutations.py tests/architecture/test_public_api_imports.py tests/architecture/test_network_isolation.py tests/architecture/test_repository_cleanliness.py --junitxml=build/acceptance/g12g-pytest.xml
  import_boundary: PYTHONDONTWRITEBYTECODE=1 uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/g12g-import-boundary-report.json
  static_types: uvx --from mypy==2.3.0 mypy --python-version 3.13 packages/*/src
  full_suite: PYTHONDONTWRITEBYTECODE=1 uv run pytest -q
fixture_ids:
  - canonical-bar-aggregation-v1
artifacts:
  - docs/research/g12g-bar-aggregation.md
  - docs/implementation/plans/g12/g12g.md
  - tests/fixtures/market_data/bar_aggregation/canonical-bar-aggregation-v1.expected.json
  - build/acceptance/g12g-pytest.xml
  - build/acceptance/g12g-import-boundary-report.json
failure_contracts:
  - invalid-input-is-accepted-or-raises
  - source-event-tuple-does-not-exactly-match-g12c-manifest
  - definition-and-bucket-plan-identities-differ
  - source-stream-contract-mismatches-or-output-stream-collides
  - source-and-plan-coverage-differ
  - selected-source-payload-purpose-scale-units-or-economic-order-is-invalid
  - source-revision-chain-is-missing-forked-cyclic-disconnected-or-context-changing
  - output-phase-cannot-follow-causal-source-evidence
  - generated-source-plus-bar-tuple-fails-final-g12c-validation
  - failure-precedence-or-earliest-input-position-is-unstable
  - partial-bars-manifest-or-result-escapes-failure
  - same-utc-full-instant-revisions-are-rejected-or-leak-intermediate-bars
  - bar-definition-plan-spec-code-or-source-change-does-not-change-identity
  - empty-or-out-of-plan-evidence-is-misclassified-as-market-coverage
  - g12g-derives-calendar-session-trading-date-or-gap-reason
  - g12g-adds-runtime-kernel-provider-network-filesystem-or-dataframe-authority
  - g12g-claims-decision-grade-live-or-deployment-authorization
evidence:
  - explicit-caller-supplied-session-trading-date-half-open-bucket-plan
  - a-share-lunch-disjoint-spans-utc-day-night-and-truncated-bucket-golden
  - exact-integer-price-only-ohlc-null-volume-and-empty-omission
  - ambiguous-economic-tie-mixed-scale-and-invalid-units-rejection
  - root-at-close-pre-close-collapse-late-root-post-close-correction
  - full-simulation-instant-same-utc-grouping-and-immediate-supersession
  - retained-bar-revisions-source-event-hashes-and-causal-availability
  - source-definition-plan-spec-code-event-stream-manifest-bundle-sensitivity
  - all-nine-failure-codes-global-precedence-and-atomicity
  - final-g12c-revalidation-and-g11d-no-resampling-consumption
  - repeat-canonical-golden-forgery-and-public-boundary-tests
implementation_commit: eefe4df3568776323881810a309ea09a47b379b7
approved_on: 2026-08-14
```

Frozen contract：

1. G12G新增one pure offline `crypto_quant_bundle_builder.bar_aggregation` module、nine Builder root exports与one `aggregate_bars_v1(...)` function；不得新增calendar engine、resampling DSL、registry、callback、Protocol、Reader或mutable builder object；
2. `BarBucketPlan`是caller-supplied finite immutable authority。G12G不推导timezone、DST、holiday、TradingDate、Session、phase、interval grid或missing interval；每个Bucket exact绑定one SessionId、one TradingDate与ordered disjoint nonempty half-open included spans；
3. `BarDefinition` exact绑定key/version、source/output streams、`synthetic_price_point.v1`、source capability、PricePurpose、Scale、price-only OHLC、`volume_semantics=none`、`empty_interval_policy=omit`与output phase。Definition hash兼容G11D `BarDefinitionRef` shape但Builder不得import Runtime；
4. Aggregation前必须以complete unchanged caller-order Event tuple重新调用existing `validate_market_bundle_v1`，并要求结果manifest exact等于supplied source manifest。不得排序、修复或内联第二套Bundle validator；
5. V1只读取exact G12B payload `{synthetic_record_key,price_units,price_scale,price_purpose}`。Selected price必须positive non-bool integer、exact scale、exact purpose与non-null Instrument；不做float、Decimal、rescale、VWAP或implicit rounding；
6. Economic assignment只使用Event `event_time`落入caller-supplied half-open spans。Distinct record keys不得共享one Instrument/economic time；无权威economic tie sequence时fail closed，不得使用Event ID、arrival order、revision order或lexical key决定open/close；
7. OHLC exact使用integer units；open/close为first/last economic time，high/low为integer extrema，volume exact为null，observation count仅是provenance count。Empty Instrument/Bucket不合成zero/carry/forward-filled/placeholder Bar；
8. 每个selected observation chain必须one root、one immediate-parent linear path，无duplicate revision、missing parent、multiple root、fork、cycle、disconnected node或multiple terminal path。Revision不得改变Instrument、record key、purpose、scale、economic time或bucket/out-of-plan assignment；
9. Source child revision按full `MarketEvent.timeline_instant` strictly later排序。同UTC且later phase/source-sequence合法；同UTC变化必须在one output causal bound内完整group后产生one Bar state，不得泄露intermediate Bar；
10. Root state使用bucket close时visible terminal revisions；pre-close changes collapse；late first availability可生成late root；post-close selected-source-set change生成immutable child，即使OHLC数值相同；old Bar保留并通过immediate `supersedes_revision_id`连接；
11. Bar available time exact为`max(bucket end, latest causal source available_time)`；equal UTC时output phase必须strictly after all causal source phases，否则`output_causality_invalid`。Generated SourceSequence只作deterministic output ordinal，不作economic tie authority；
12. 每个Bar payload绑定definition、source stream、bucket plan、aggregation spec/code/input、bucket、included spans、Session/TradingDate、OHLC、source Event hashes与selected-source-set hash。Source/definition/plan/spec/code change必须改变Bar/stream/Bundle identity；
13. G12G把generated Bars append到unchanged source Events并再次调用G12C。Final validation成功前不得返回Result；`BarAggregationManifest` separately绑定source/output refs、all lineage hashes、mechanical counts与qualification flags，不修改passed G12C/G12D schemas；
14. Failure precedence exact为`invalid_input → source_bundle_mismatch → definition_bucket_plan_mismatch → source_stream_mismatch → source_coverage_unaligned → source_event_invalid → revision_chain_invalid → output_causality_invalid → output_validation_failed`，同层按earliest original input position；Outcome exact为Result XOR Failure且failure不暴露partial authority；
15. Golden exact冻结A股午休separate/disjoint spans、UTC day、night TradingDate、truncated interval、empty/out-of-plan、integer OHLC、root/late/correction/same-UTC revisions、identity sensitivity、failure matrix与repeat bytes；G11D exact消费generated `event_type=bar`与matching definition ref，不执行Runtime resampling；
16. Out-of-plan、empty、revision set与bucket plan只构成mechanical evidence。G12I拥有coverage/gap/availability/revision completeness；G12L/M拥有Provider与market qualification。G12G始终`decision_grade_eligible=false`、`deployment_authorized=false`。

Research authority：`docs/research/g12g-bar-aggregation.md`。

PASSED evidence：

```text
Direct G12G/G11D/architecture contract                            44 passed
Frozen G12G/G12B/C/G11D acceptance                              140 passed
Full repository suite                                          1466 passed
Workspace import boundary                                      PASS (94 files)
mypy 2.3.0                                                     no issues (94 package source files)
Primary LSP                                                    clean across 11 changed Python files
pi-lens blocking diagnostics                                  no errors across 11 changed files
Independent review                                            no P0; P1 evidence gaps fixed
uv lock --check                                                PASS
git diff --check                                               PASS
Python                                                          3.13.5
```

Artifact hashes：

```text
g12g-bar-aggregation.md                                        sha256:aac7d200b05fd10d1de9cf1beba5ac8a895c0dd622310d1d5a7ddc3bc160c39d
g12g.md                                                        sha256:905f312efcc39091987a950bf448cd29f2e6d16f1dd6dc9b88a07b57543da48b
canonical-bar-aggregation-v1.expected.json                     sha256:151e1c7bdcdf9bf90a8b64a8c439bbe0ef5f483204b257e5f78313c21373a49e
g12g-pytest.xml                                                sha256:436e0cf539f1a75314283049dd13f5d82f9cd29b475d82437d1471188660fb9a
g12g-import-boundary-report.json                               sha256:7efaa8493cddc81fbf890d2bdb224770b248c49d63f24e91d11923682a363df0
import-boundaries.toml                                         sha256:1518ad6dc28c73218d4b9d1af97a2fd8c0e5913936cfff23b81e429091cb41d5
uv.lock                                                        sha256:a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
```

Implementation commit：`eefe4df3568776323881810a309ea09a47b379b7`。

## 103. G12I Declaration Prerequisite Progress (Gate remains DRAFT)

```yaml
id: G12I
status: DRAFT
depends_on:
  - G12C
  - G12G
owner_package: market-bundle-builder validation
allowed_grade: development
public_interface:
  - crypto_quant_bundle_builder.BuilderStaleMarkPolicy
  - crypto_quant_bundle_builder.PricePurposeRequirement
  - crypto_quant_bundle_builder.MarketAvailabilityReason
  - crypto_quant_bundle_builder.AvailabilitySpan
  - crypto_quant_bundle_builder.AvailabilityClosureDeclaration
  - crypto_quant_bundle_builder.RevisionTerminalLineage
  - crypto_quant_bundle_builder.RevisionClosureDeclaration
test_commands:
  contract: uv run pytest -q tests/bundle_builder/coverage_declarations/test_coverage_declarations.py
  parity: uv run pytest -q tests/parity/test_stale_policy_projection_parity.py
  boundary: uv run pytest -q tests/architecture/test_g12i_coverage_declarations_boundary.py
fixture_ids:
  - coverage-declarations-v1
expected_artifacts:
  - tests/fixtures/market_data/coverage-declarations-v1.json
failure_contracts:
  - stale-policy-projection-differs-from-g03
  - declaration-type-or-hash-forgery
  - stale-policy-purpose-mismatch
  - execution-or-liquidation-forward-fill
  - availability-overlap-gap-or-unclassified-range
  - duplicate-or-unordered-terminal-lineage
  - declaration-claims-decision-grade-or-deployment-authorization
  - builder-production-imports-kernel-runtime-or-io-authority
remaining_blockers:
  - real-profile-or-build-owned-complete-price-purpose-declarations
  - real-provider-or-calendar-backed-gap-classification
  - real-provider-backed-terminal-set-closure
  - final-report-contract-and-atomic-failure-precedence
passed_commit: null
artifact_hashes: []
```

This slice freezes passive declaration values only. The static fixture is deterministic contract evidence, not provider/calendar truth or terminal-set completeness. `PriceStreamCoverageReport`, `MarketAvailabilityReport`, and `RevisionProvenanceReport` remain unimplemented. G12I remains `DRAFT / BLOCKED`, development-only, and cannot qualify a market or authorize deployment.

## 104. G12L-* Provider Qualification Contract (Gate remains DRAFT)

```yaml
id: G12L-*
status: DRAFT
depends_on:
  - G12A
  - applicable G12B-G12K contracts
owner_package: market-bundle-builder adapters
public_interface:
  - docs-only provider-neutral qualification obligations
test_commands:
  contract: TBD by concrete provider slice before READY
  fixture: TBD by concrete provider slice before READY
  boundary: TBD by concrete provider slice before READY
fixture_ids: []
expected_artifacts:
  - docs/research/g12l-provider-adapter-contract.md
  - docs/implementation/plans/g12/g12l.md
failure_contracts:
  - CONFIGURATION_INVALID
  - PROVIDER_UNAVAILABLE
  - AUTHENTICATION_REJECTED
  - RATE_LIMIT_EXHAUSTED
  - SOURCE_SCHEMA_MISMATCH
  - NORMALIZATION_FAILED
  - DATA_GAP_DETECTED
allowed_grade: development
evidence:
  - finite-explicit-scope-obligation
  - source-authority-and-version-obligation
  - deterministic-raw-member-and-g12a-handoff-obligation
  - idempotent-retry-resume-and-atomic-failure-obligation
  - secret-redaction-and-offline-test-obligation
  - false-qualification-flags-and-immutable-hash-obligation
remaining_blockers:
  - provider-market-dataset-and-version-selection
  - provider-request-authentication-and-transport-contract
  - provider-schema-to-g12b-mapping
  - pagination-cursor-and-terminal-closure
  - revision-correction-and-archive-closure
  - availability-calendar-outage-and-gap-authority
  - sanitized-real-raw-fixtures-and-exact-artifact-hashes
  - concrete-offline-test-commands-and-provider-error-mapping
passed_commit: null
artifact_hashes: {}
```

### G12L Acceptance

1. The common G12L contract is docs-only. It adds no provider code, HTTP client,
   SDK, transport Protocol, generic adapter interface, registry, factory,
   resolver, plug-in system, retry framework, cache, credential store,
   filesystem abstraction, executable providerless schema, or network test.
2. Every concrete slice must freeze finite explicit scope, source authority and
   version, deterministic raw-byte/member identity, exact atomic G12A handoff,
   idempotent retry/resume evidence, secret redaction, offline unit tests, false
   qualification flags, and immutable artifact hashes.
3. Each concrete slice—not the common layer—owns provider request shape,
   dataset/schema mapping, pagination/cursor closure, revision/correction
   closure, availability/calendar claims, and sanitized real raw fixtures.
4. Latest/current/now fallback, open-ended polling, partial snapshots, current
   endpoint gap filling, inferred completeness, and secret-bearing evidence are
   forbidden.
5. Failure precedence is exact in the YAML order above. Multi-fault cases select
   the earliest applicable code; ties use the provider slice's frozen
   request/member order; every failure exposes no partial downstream authority.
6. The exact per-provider READY checklist is frozen in
   `docs/implementation/plans/g12/g12l.md`; research authority is
   `docs/research/g12l-provider-adapter-contract.md`.
7. G12H, G12I, G12K, and G12M remain `DRAFT / BLOCKED`. The first concrete
   G12L slice is PASSED at immutable commit `47d59e40081555ab9b555c3e632070a517509436`.
   This contract grants no decision-grade, live, or deployment authority.

## 104A. G12L Binance USDⓈ-M Daily Mark-Price-Kline v1 (PASSED)

```yaml
id: G12L-BINANCE-USDM-MARK-PRICE-KLINES-V1
status: PASSED
depends_on:
  - G10D
  - G12A
  - G12B
  - G12C
  - G12D
owner_package: market-bundle-builder Binance USD-M source slice
public_interface:
  - crypto_quant_bundle_builder.binance_usdm_mark_price_archive.BinanceUsdmMarkPriceArchiveRequest
  - crypto_quant_bundle_builder.binance_usdm_mark_price_archive.capture_binance_usdm_mark_price_archive
  - crypto_quant_bundle_builder.binance_usdm_mark_price_archive.normalize_binance_usdm_mark_price_archive
test_commands:
  contract: uv run --locked pytest -q tests/bundle_builder/providers/binance_usdm
  boundary: uv run --locked pytest -q tests/architecture/test_g12l_binance_mark_price_boundary.py
  focused: uv run --locked pytest -q tests/bundle_builder tests/architecture/test_network_isolation.py tests/architecture/test_public_api_imports.py
fixture_ids:
  - g12l-binance-usdm-mark-price-klines-v1
expected_artifacts:
  - docs/research/g12l-binance-usdm-mark-price-klines-v1.md
  - docs/implementation/plans/g12/g12l-binance-usdm-mark-price-klines-v1.md
  - tests/fixtures/market_data/providers/binance_usdm/mark-price-klines-v1/BTCUSDT-1m-2024-01-01.zip
  - tests/fixtures/market_data/providers/binance_usdm/mark-price-klines-v1/BTCUSDT-1m-2024-01-01.zip.CHECKSUM
  - tests/fixtures/market_data/providers/binance_usdm/mark-price-klines-v1/evidence.expected.json
frozen_scope:
  provider: Binance Public Data
  authority_revision: binance-public-data@5c7f3197
  market: USD-M Futures
  dataset: daily markPriceKlines
  symbol: BTCUSDT
  interval: 1m
  utc_date: 2024-01-01
  archive_rows: 1440
g12a_evidence:
  snapshot_id: sha256:df0869271a08320107381a60e9be9012d9645e076ef349c551d34aa332d2be80
  content_tree_hash: sha256:9b12fcf35779d78b2d0293692deb595d54b4506bbb9da6dde44e525a8c968b32
  provenance_hash: sha256:4dba4a7b2140ac82bc7c736f856b1fa8ea0d2ff58e8e5f7c659f4cb870aed2ca
allowed_grade: development
evidence:
  - immutable-first-party-authority-revision
  - finite-two-member-https-scope
  - sanitized-real-zip-and-checksum-bytes
  - exact-checksum-and-single-member-zip-layout
  - exact-1440-row-utc-day-sequence-closure
  - exact-g12a-snapshot-provenance-and-content-identity
  - bounded-retry-and-atomic-failure-precedence
  - conservative-g12a-acquisition-time-availability
  - purpose-separated-valuation-margin-liquidation-events
  - exact-source-row-trace-and-4320-event-identity
  - malformed-and-encrypted-zip-containment
  - exact-snapshot-provenance-and-replacement-rejection
  - finite-archive-revision-causal-limit
  - g12c-three-stream-manifest-and-g12d-publication
  - offline-repeatable-fixture-check
remaining_blockers: []
validation:
  focused_g12l: 11 passed
  full_repository: 1726 passed
  import_boundaries: 107 files passed
  lock_check: passed
  lsp_lens: clean
  independent_review: NONE
passed_commit: 47d59e40081555ab9b555c3e632070a517509436
artifact_hashes:
  archive_sha256: 660efeefdc875f052051b94c2976babd013f64c6633bf58ba030764771747b90
  checksum_sha256: ea5548dadd83fad69bbc9db3a24560b7d3f988e54299d2c6aa87e85351e05215
  csv_sha256: 71357549ea1f81632e92f1b2ee2677c173a51e8563b0d5dd26ee4f321c7eb378
  evidence_fixture_sha256: 4814ad89aeadf2aeb10a8c63f9b4ea1218d04890043f7887a98fea362f84ac3c
  provider_module_sha256: 34c8767a8d094a2f3bef0af702f17c6b9ab39a2fbe3717b34967e3458fc760b2
  request_hash: sha256:6339107fdfc8c93ce11d1c56c5d5ba5a4a05442c6e3071f2651649e4d5675f27
  capture_hash: sha256:b1b9d1bc5d85e6d97a3eb1ab6fee60a37983f378137ad979acda43193b314be9
  normalization_hash: sha256:77ac62498fc78d6ac7b10840eceb0d6b968e8c6024ba5e207ebb985dd72a3a51
  manifest_content_hash: sha256:048e1247e9346445f3764de27b123e5d90bfae9d618b3a5f7b5fa853abd1807d
  bundle_manifest_hash: sha256:9a23df29531073637259722e353685c97283be0489ec0b6e51c12e7b64cfeabd
```

### G12L Binance Mark-Price Evidence Acceptance

1. The first concrete G12L provider, dataset, authority revision, finite request,
   and real raw bytes are now selected. The common G12L contract no longer waits
   on provider selection, but this concrete Gate is not PASSED.
2. The committed Binance ZIP and adjacent checksum exact-match. The ZIP contains
   one CSV with the frozen provider header and exactly 1440 one-minute rows that
   internally exact-cover `2024-01-01` UTC. This is fixture closure, not a claim
   that Binance will never replace the archive or that no provider outage occurred.
3. The exact two-member G12A snapshot, content-tree, provenance identities and
   false qualification flags are executable and frozen without network access.
4. G10D remains the source-semantics authority. The archive CSV has economic
   close times but no provider publication timestamps, so `available_time =
   close_time + 1ms` is forbidden. The conservative v1 authority is the exact
   G12A archive member acquisition timestamp for every row. This prevents
   lookahead but cannot qualify intraday 2024 replay; G12M remains blocked.
5. The Builder provider module remains off the frozen root and imports neither
   Trading Kernel nor Runtime. It emits separate VALUATION/MARGIN point streams
   and LIQUIDATION bars with exact source-row traces, conservative late
   availability, 4320 stable event identities, and no synthetic-JSONL relabeling.
6. Capture evaluates both fixed URL outcomes before selecting the common failure
   precedence. Capture and normalization revalidate the exact two-member bytes,
   hashes, acquisition time, modes, provenance, snapshot, and checksum identity;
   malformed/encrypted/replacement evidence exposes no partial downstream authority.
7. G12C validates three exact 1440-event streams and G12D publishes their frozen
   bundle. The revision causal limit is only the accepted archive/checksum hash at
   acquisition; later Binance replacements require a new explicit slice/version.
8. G12I/G12M qualification, intraday 2024 replay, decision-grade, live, and
   deployment authority remain explicitly unclaimed.

## 104B. G12L Binance USDⓈ-M Daily Aggregate Trades v1 (PASSED)

```yaml
id: G12L-BINANCE-USDM-AGGTRADES-V1
status: PASSED
depends_on: [G10D, G12A, G12B, G12C, G12D]
owner_package: market-bundle-builder Binance USD-M source slice
public_interface:
  - crypto_quant_bundle_builder.binance_usdm_aggtrades_archive.BinanceUsdmAggregateTradesArchiveRequest
  - crypto_quant_bundle_builder.binance_usdm_aggtrades_archive.capture_binance_usdm_aggregate_trades_archive
  - crypto_quant_bundle_builder.binance_usdm_aggtrades_archive.normalize_binance_usdm_aggregate_trades_archive
test_commands:
  provider: uv run --locked pytest -q tests/bundle_builder/providers/binance_usdm tests/architecture/test_g12l_binance_aggtrades_boundary.py
fixture_ids: [g12l-binance-usdm-aggtrades-v1]
frozen_scope:
  provider: Binance Public Data
  authority_revision: binance-public-data@5c7f3197
  dataset: futures/um/daily/aggTrades
  symbol: BTCUSDT
  utc_date: 2020-01-01
  rows: 71359
  aggregate_trade_ids: 18374167..18445525
g12a_evidence:
  snapshot_id: sha256:84e362ddf3a1a7567c436160bb4bb6102324cd20474a4c2c2b0a38b388142c65
  content_tree_hash: sha256:3e51e591737b5928ce796dc555b266b7d49d48e88b1051fbb9c6aa0b957993d7
  provenance_hash: sha256:70908485e1e1baddf684248282fce1ba78dd5df4f066ccc3cf714ec892bac5d7
allowed_grade: development
remaining_blockers: []
validation:
  focused_provider_and_boundaries: 26 passed
  full_repository: 1732 passed
  import_boundaries: 108 files passed
  lock_diff_lsp_lens_secret_scan: clean
  independent_review: NONE
passed_commit: 981429b4f0ff5fa219ccc8bc991458072b025bf8
artifact_hashes:
  archive_sha256: 638e72c179e4965c2a6521bb27295930d09126433efe0cc3acd4e925ada955ac
  checksum_sha256: 54f9a3ec8d0ea0363fcd730c2eb43399fa425d2d1fd803a7261f761af78d8499
  csv_sha256: b296db90ad4f8a20cd888cb7ce4a4199409ed14ad488331fe1a6b4943e6a53c0
  evidence_fixture_sha256: 54f183ea5e4d61f0d0c80a9a1ba3f7cfe4538a429338ea711d31d4c3d24935e0
  provider_module_sha256: e00d8b058e1152aed73d2fa5198a23241550d60756245adcc9d8a0b2a1dc1079
  request_hash: sha256:71444a4b733b10f5b94508c74c5a941afc3c4ea531f1971bb71fcc0acdc64f91
  capture_hash: sha256:3a15e9f997bb9b7925037ee77a4dc6e2cc39b4ea87f56683e2611643d4ea632a
  normalization_hash: sha256:8d516a2679966c0b002e599b93559854322eaf3a17f8b61f2145aca801785c68
  manifest_content_hash: sha256:babd102967a4a40bdd1de8868916aabce54359499204eb8d267bd86d0ed3ee90
  bundle_manifest_hash: sha256:7248df115d39299343a4c31a6c6354d37ec7603a545c91b5978f4f4a7c8ac4e4
```

The committed headerless CSV has 71,359 exact seven-field rows, contiguous
aggregate-trade IDs, nondecreasing in-day transaction times, exact ZIP/checksum,
and repeatable G12A identity. The provider module emits one EXECUTION_REFERENCE
stream with availability at the later G12A acquisition instant, exact source
traces, G12C manifest, and G12D publication. G12I/G12M remain unqualified.

## 104C. G12L Binance USDⓈ-M Monthly Funding Rate v1 (PASSED)

```yaml
id: G12L-BINANCE-USDM-FUNDING-RATE-V1
status: PASSED
depends_on: [G10E, G12A, G12B, G12C, G12D]
owner_package: market-bundle-builder Binance USD-M source slice
public_interface:
  - crypto_quant_bundle_builder.binance_usdm_funding_rate_archive.BinanceUsdmFundingRateArchiveRequest
  - crypto_quant_bundle_builder.binance_usdm_funding_rate_archive.capture_binance_usdm_funding_rate_archive
  - crypto_quant_bundle_builder.binance_usdm_funding_rate_archive.normalize_binance_usdm_funding_rate_archive
test_commands:
  provider: uv run --locked pytest -q tests/bundle_builder/providers/binance_usdm tests/architecture/test_g12l_binance_funding_rate_boundary.py
fixture_ids: [g12l-binance-usdm-funding-rate-v1]
frozen_scope:
  provider: Binance Public Data
  authority_revision: binance-public-data@5c7f3197
  dataset: futures/um/monthly/fundingRate
  symbol: BTCUSDT
  utc_month: 2020-01
  rows: 93
  funding_interval_hours: 8
  maximum_slot_jitter_milliseconds: 2
g12a_evidence:
  snapshot_id: sha256:8a42a791c9471a20f734d88660b37b7e967b8eabb6007078e625b220add11ebd
  content_tree_hash: sha256:d596329bda3338709134d3b02403fb38f4cfed555a1b40910f877b15fba6196e
  provenance_hash: sha256:7abdd0a03f8e3b833595492707869700fd19c410a68cd74c1eb419759d3f6e73
allowed_grade: development
remaining_blockers: []
validation:
  focused_provider_and_boundaries: 29 passed
  full_repository: 1744 passed
  import_boundaries: 109 files passed
  lock_diff_lsp_lens_secret_scan: clean
  independent_review: NONE
passed_commit: ebd91f746c4a065ca06dba89d847e7d41ab06331
artifact_hashes:
  archive_sha256: 7f81b2f3694d13779e7e896b69d60cd61e9444d7b9f9e90df761935e1c1b76e2
  checksum_sha256: 3274779c977a6d657722bac4cc9f965bb774c5ba38aad391eb47ef183ae46120
  csv_sha256: b566eea750ede01486360de242ce63a727ebbbc81fb46fcfdf2fb68188b48835
  evidence_fixture_sha256: e2283531420b1b282b43bdbd046aba1d5e3ce6ac9438cc8c3eb909e0cdd70541
  provider_module_sha256: 2f42f796ed947dbe24f025e5e3612437c52704faaac5a12c60514685ceee0754
  request_hash: sha256:adaba188f07aab97b311e995f41d7e2b266e82baaeb5d3b416560e1fc98e29c7
  capture_hash: sha256:530184b2bafdffef4fbc7ed4e310bc4ba7567f3f44e540a3d7d29190d24d34c3
  normalization_hash: sha256:adaf13c487bb3864e3321539e70a7c4fa0f8e3ab8c4cd94cee4138537fb9d62f
  manifest_content_hash: sha256:47e75aacbe3c0dc8f877e1fbb58b8963a017bda2c1bf1b3894e32d12338295af
  bundle_manifest_hash: sha256:baa96c9993c7531715a203f610f7e0075dd2955240f020330072f925cbee4ba5
```

The committed CSV has 93 exact eight-hour slots and preserves provider 0–2ms
slot jitter plus the scientific-notation source rate. The provider emits one
rate-only funding-publication stream with exact traces and G12C/D publication.
The archive has no funding-time mark, so G10E/G12I/G12M remain unqualified.

## 104D. G12L Binance USDⓈ-M Funding History v1 (Gate remains BLOCKED)

```yaml
id: G12L-BINANCE-USDM-FUNDING-HISTORY-V1
status: DRAFT / BLOCKED
depends_on: [G10E, G12A]
owner_package: market-bundle-builder Binance USD-M source slice
public_interface:
  - none; exact source/G12A development evidence only
test_commands:
  evidence: uv run --locked pytest -q tests/bundle_builder/providers/binance_usdm/test_funding_history_response_evidence.py
fixture_ids: [g12l-binance-usdm-funding-history-v1]
frozen_scope:
  provider: Binance USD-M Funding Rate History REST
  symbol: BTCUSDT
  utc_date: 2024-01-01
  records: 3
  fields: [symbol, fundingTime, fundingRate, markPrice, rateType]
g12a_evidence:
  snapshot_id: sha256:0d4566742f51b18d66a28605c087ec3604769ab04e6fc551d71c9b32033b69a9
  content_tree_hash: sha256:a55fd58ce7f37e829b37c1a6fb94c1426a79c0b97aa0df3c6e793273506b4680
  provenance_hash: sha256:18a2286003de03ae71aa343a83b75432653ed0e1b490dcf5f3608b37896aa058
allowed_grade: development
remaining_blockers:
  - provider-checksum-or-signed-content-identity
  - immutable-publication-revision
  - correction-supersession-terminal-closure
  - historical-availability-authority
passed_commit: null
artifact_hashes:
  response_sha256: e9f73f9c845c28abb31037d8230df2d6f13d5d368c43436e891fcc757372c338
  evidence_fixture_sha256: 56ae7e1ddf9ee0fbead02b96e44a76134f60e0add2451060a824106a0810efa4
```

The exact response supplies all G10E record fields, including the funding-time
mark, and repeated fetches had identical bytes. It remains BLOCKED because the
current REST endpoint provides no immutable revision/correction terminal set or
provider checksum. No normalizer, G12C/D, G12I, G12M, or deployment claim follows.

## 104E. G12L Tushare China A-share Daily and Listing v1 (Gate remains BLOCKED)

```yaml
id: G12L-TUSHARE-CN-A-SHARE-DAILY-LISTING-V1
status: DRAFT / BLOCKED
depends_on: [G12A, G12-ACQ-TOOLS-V1]
owner_package: market-bundle-builder China A-share source slice
public_interface:
  - none; exact source/acquisition/G12A/parity evidence only
test_commands:
  evidence: uv run --locked pytest -q tests/bundle_builder/providers/tushare/test_cn_a_share_daily_listing_evidence.py
fixture_ids: [g12l-tushare-cn-a-share-daily-listing-v1]
frozen_scope:
  provider: Tushare Pro
  ts_code: 000001.SZ
  trade_date: 20240102
  daily_rows: 1
  listing_rows: 1
  acquisition_tool_commit: 6f0bd99a93a349924996eb26708fbb0ac6fecf17
g12a_evidence:
  snapshot_id: sha256:6a360b17c1a5dd7686b2496f3b04006f902ef5705a1427dc2a7dbdaeadc2458a
  content_tree_hash: sha256:44c4cd1e11dca26ddfe62fc1d2b5d4d8175da701b288876d33d1be65e06eddb5
  provenance_hash: sha256:8745af52a950d0ba35eee381b32b6adad2d2ee144325de34ad3597389f2e73fb
allowed_grade: development
remaining_blockers:
  - approved-session-date-to-event-time-authority
  - exact-source-text-decimal-unit-scale-mapping
  - provider-revision-correction-terminal-closure
  - historical-listing-status-authority
  - normalized-g12b-schema-and-failure-contract
passed_commit: null
artifact_hashes:
  daily_response_sha256: c2950a35c093b983e538f97830b7b3fcb0bba1a7dac98a17bd20f6db9296f846
  listing_response_sha256: d78fc472268deacb5af7c59c113325e2a00c5b4619c53fbbfe6fa23c96d471d2
  acquisition_receipt_sha256: 61106b7e974ff09dedf96c065070f4a097a7fe02121bfd7a81b5dacb5c4757da
  evidence_fixture_sha256: 95775b9dc7ace840f52fbb6a2291ab2b34a92318a519fb8356a67d74ab776c43
  duckdb_backup_sha256: cdc6ce41dee3fe9903d8c27ec5cc584455ad423989cd79e3eb0187c5bba8bd41
```

The exact provider responses contain no token and reproduce one candidate G12A
snapshot. Daily OHLC/change and converted volume/amount plus listing metadata
match the stable DuckDB backup. No event timestamp, historical availability,
provider revision terminality, listing lifecycle, normalizer, G12C/D, G12I/K/M,
or deployment claim follows.

## 105. BT-GAP-01 Domain ArtifactRef

```yaml
id: BT-GAP-01
status: PASSED
depends_on:
  - WP-02E
  - Platform BT-PORT-01 consumer contract
owner_package: trading-domain
public_interface:
  - crypto_quant_domain.ArtifactRef
test_commands:
  contract: uv run pytest -q tests/domain/artifacts/test_artifact_ref.py
  fixture: uv run pytest -q tests/domain/artifacts/test_artifact_ref.py tests/domain/artifacts/test_artifact_envelope_golden.py
  boundary: uv run pytest -q tests/architecture/test_public_api_imports.py
fixture_ids:
  - artifact-ref-v1
  - artifact-envelope-catalog-v1
expected_artifacts:
  - tests/fixtures/domain/artifact-ref-v1.json
  - build/acceptance/bt-gap-01-pytest.xml
failure_contracts:
  - invalid-artifact-ref-type
  - invalid-artifact-ref-schema-version
  - invalid-artifact-ref-content-hash
  - non-exact-artifact-envelope-reconstruction
  - artifact-envelope-v1-byte-regression
allowed_grade: development
evidence:
  - exact-platform-artifact-ref-wire
  - canonical-golden-fixture
  - inherited-envelope-byte-compatibility
  - public-domain-root-import
  - focused-pytest-report
contract_freeze_commit: 80d44c81645a4ea1a19bb786150e774cf0055e0f
passed_commit: f2440f9658fbe2ae1cf0016a78c44e4230995394
executed_commands:
  - uv run pytest -q --junitxml=build/acceptance/bt-gap-01-pytest.xml tests/domain/artifacts/test_artifact_ref.py tests/domain/artifacts/test_artifact_envelope_golden.py tests/domain/artifacts/test_schema_catalog.py tests/architecture/test_public_api_imports.py tests/architecture/test_import_boundary_mutations.py
  - uv run pytest -q
  - uvx --from mypy==2.3.0 mypy --python-version 3.13 packages/trading-domain/src/crypto_quant_domain/artifacts.py packages/trading-domain/src/crypto_quant_domain/__init__.py
  - MYPYPATH=packages/trading-domain/src uvx --from mypy==2.3.0 --with pytest==8.4.2 mypy --python-version 3.13 tests/domain/artifacts/test_artifact_ref.py
  - uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/bt-gap-01-import-boundary-report.json
  - uv lock --check
  - git diff --check
test_results:
  focused_and_inherited: 44 passed
  full_repository: 1581 passed
  platform_consumer_contract: 14 passed
  independent_reviews: NONE / NONE
artifact_hashes:
  tests/fixtures/domain/artifact-ref-v1.json: sha256:f1153b2b06ac0fff60ec50a0f4eca26b3e3a798cb149f185178a2deec791c75e
  tests/fixtures/domain/artifact-envelope-catalog-v1.json: sha256:ec5138bcc003ecd59a1821f20999bfea3072493e3dfccf8cd781b4f4963b7e16
  build/acceptance/bt-gap-01-pytest.xml: sha256:cc1213a24d2ca56d5bfcad9ff63698579172e4b3895c85ad5effc224f46e9060
  build/acceptance/bt-gap-01-import-boundary-report.json: sha256:55593051b06645b1ae73420cfe0d110dabb19ccd18b245e6ac17343d400e4678
  uv.lock: sha256:a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
```

### BT-GAP-01 Acceptance

1. `ArtifactRef` is the single Domain-owned immutable content coordinate. Its exact canonical wire is `{type="artifact_ref", artifact_type, schema_version, content_hash}`.
2. `artifact_type`, `schema_version`, and `content_hash` require exact built-in types; schema identity reuses `CanonicalSchema`, and the hash is exactly `sha256:<64 lowercase hex>`.
3. `ArtifactRef.from_envelope()` accepts only an exact `ArtifactEnvelope` and reconstructs all three coordinate fields. It does not decode, store, or verify external bytes.
4. The ref contains no Payload, source hash, path, timestamp, repository identity, governance status, or Platform type.
5. WP-02E `ArtifactEnvelope` and `artifact-envelope-catalog-v1` bytes/hashes remain unchanged. No migration, repository, facade, tagged Backtest ref, analysis, structural reader, registry, or BT-GAP-02+ behavior is introduced.
6. Contract freeze commit `80d44c81645a4ea1a19bb786150e774cf0055e0f` and implementation commit `f2440f9658fbe2ae1cf0016a78c44e4230995394` are immutable. Focused/inherited tests passed 44, the full repository passed 1581, the unchanged Platform consumer contract passed 14, and both independent final reviews returned `NONE`.

## 106. BT-GAP-02 Backtest Runtime Facade

```yaml
id: BT-GAP-02
status: PASSED
depends_on:
  - BT-GAP-01
  - G07
  - BT-GAP-02A production execution-case composition authority
  - BT-GAP-04 tagged publication contract
  - BT-GAP-07 structural reader
owner_package: backtest-runtime facade
public_interface:
  - crypto_quant_backtest.BacktestRuntime
  - crypto_quant_backtest.BacktestRuntime.run
  - crypto_quant_backtest.ArtifactEnvelopePublisher
composition_only_dependencies:
  - BacktestProfileRegistry
  - ArtifactEnvelopeReader
  - ArtifactEnvelopePublisher
  - MarketBundleReader
  - publication_root
private_interface:
  - request hydration, profile resolution, Attempt execution, evidence hashing, integrity evaluation, publication mirroring, and cache verification
  - manifest structural mirror safety gate
test_commands:
  focused: uv run pytest -q tests/runtime/test_bt_gap_02_facade.py tests/architecture/test_bt_gap_02_facade_boundary.py tests/runtime/ports/test_artifact_envelope_publisher_contract.py
  inherited: uv run pytest -q tests/runtime/analysis tests/runtime/execution_inputs tests/runtime/resolution tests/runtime/runner tests/runtime/evidence tests/runtime/integrity tests/runtime/publication
  full: uv run pytest -q
  boundaries: uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml
  platform_contract: uvx --python 3.13.5 --from pytest==8.4.2 pytest -q -p no:cacheprovider tests/architecture/test_backtest_consumer_port.py
  lock: uv lock --check
  diff: git diff --check
fixture_ids:
  - bt-gap02-public-facade-v1
expected_artifacts:
  - BacktestCanonicalPublicationRef for durable COMPLETED canonical publication
  - bare ArtifactRef for durable BLOCKED, FAILED, CANCELLED, or integrity-evaluation evidence
  - exact publisher-visible Attempt and canonical publication graphs
failure_contracts:
  - malformed-or-unavailable-execution-input-before-Attempt
  - provider-or-market-reader-failure-before-Attempt
  - publisher-failure-or-returned-ref-mismatch
  - local-publication-storage-or-lock-failure
  - malformed-or-path-escaping-manifest-mirror
  - cached-Attempt-evidence-or-canonical-link-mismatch
allowed_grade: development
evidence:
  - BT-GAP-02A exact sealed execution-case composition
  - G07 runner/evidence/integrity/publication authorities
  - BT-GAP-04 direct completed/terminal ref union
  - Backtest-owned composition-only registry decision
  - two blocking review rounds followed by clean Opus final review
remaining_blockers: []
implementation_commit: 39863c58ace1d996f3e814835836ec46e2aa3794
passed_commit: 39863c58ace1d996f3e814835836ec46e2aa3794
executed_commands:
  - uv run pytest -q tests/runtime/test_bt_gap_02_facade.py tests/architecture/test_bt_gap_02_facade_boundary.py tests/runtime/ports/test_artifact_envelope_publisher_contract.py tests/runtime/analysis tests/runtime/execution_inputs tests/runtime/resolution tests/runtime/runner tests/runtime/evidence tests/runtime/integrity tests/runtime/publication
  - uv run pytest -q
  - uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report /tmp/bt-gap02-main-import-boundaries.json
  - uv lock --check
  - git diff --check
  - uvx --python 3.13.5 --from pytest==8.4.2 pytest -q -p no:cacheprovider tests/architecture/test_backtest_consumer_port.py
test_results:
  focused_and_inherited: 172 passed
  full_repository: 1680 passed
  import_boundaries: 105 files passed
  platform_consumer_contract: 15 passed
  lsp: clean
  lens: clean
  independent_final_review: NONE
artifact_hashes:
  fixture_sha256: 0f3f70a457f1a54939b1ecdf6cf860671c0dfcaa20a56297540a3266141c9b91
  preserved_bt_gap02a_fixture_sha256: bfa0ddff37bb6e1c813f50da14db4abcc2fab76fa8262c522fbf5facb1b5f764
  preserved_bt_gap02b_fixture_sha256: 09578ac47f997bc4bf55119d31e97dbcad3eb71e90d93a5ef7c8e6669bd66be2
  preserved_bt_gap02c_fixture_sha256: c082042640382dde2dad61f758058ab93c3ba741ed19df0256d7989a157eced1
  preserved_bt_gap04_fixture_sha256: 9cbe91becf64053fdb44cb884a8cfd621e020e8ce54e4f5f6f76411f275e3c79
```

### BT-GAP-02 Acceptance

1. `BacktestRuntime.run(request)` is the sole Platform-facing operation. It accepts exact `BacktestExecutionRequest` by value, preserves the embedded opaque context/`experiment_id`, and returns only `BacktestCanonicalPublicationRef | ArtifactRef`. Resolved requests, execution cases, Resolver, Registry, Runner, evidence writer, hasher, publisher, and integrity values never cross the operation boundary.
2. The unique `BacktestProfileRegistry` remains the sole profile selector and is injected only by Backtest-owned composition code. Platform receives an already composed deep module. This is the minimum admissible seam because exact `ResolvedBacktestRequest` still contains live selected registrations; no default/global registry, private factory graph, bundle serialization of resolved profiles, second resolver, or runner input weakening is introduced.
3. V2 hydration first validates the public request and reconstructs one exact sealed execution case through BT-GAP-02A/02C. Profile resolution uses the same request, MarketBundle manifest, and decoded build manifest, then the second hydration binds the resolved request to the persisted semantic-run identity before Attempt creation.
4. Profile-resolution failure is published as exact `backtest_resolution_failure@1` through the shared structural `ArtifactEnvelopePublisher.put(*, envelope) -> ArtifactRef` seam and returns a bare durable BLOCKED ref. Malformed input, unavailable/tampered provider data, publisher mismatch, and local storage failures remain exceptions outside the run-result union.
5. Attempt evidence, canonical completed publications, integrity-evaluation terminals, and canonical cache hits are mirrored as their exact existing ArtifactEnvelopes into the structural publisher. Every child ref/source hash/byte count is checked against the accepted manifest before the manifest is published. A fresh publisher on cache hit receives both canonical-Attempt evidence and the canonical publication graph, so the returned completed ref remains loadable rather than becoming a partial graph.
6. The mirror safety gate rejects malformed field types, invalid hashes/refs/counts, duplicate or non-normalized paths, absolute/parent/backslash paths, missing children, and symlink escapes before publishing any child. It is not a second semantic manifest decoder; G07 writer/cache verification remains semantic authority and BT-GAP-03 remains the verified load authority.
7. COMPLETED returns the nominal `BacktestCanonicalPublicationRef`. Attempt BLOCKED/FAILED/CANCELLED evidence and blocked integrity evaluations return bare Domain `ArtifactRef`; status remains recoverable from the verified artifact graph rather than a facade wrapper. Retry/cache identity is stable and repeated publisher puts are content-addressed and idempotent.
8. Acceptance is green: 172 focused/inherited tests pass, the full repository passes 1680 tests, import boundaries pass across 105 files, Platform BT-PORT-01 passes 15 tests, LSP/lens are clean, frozen BT-GAP-02A/02B/02C/04 fixture hashes are unchanged, and the final independent Opus review reports no blocker.

## 107. BT-GAP-02A Production Execution-Case Composition Authority

```yaml
id: BT-GAP-02A
status: READY
depends_on:
  - G07
  - G08H production CnA profile composition
  - G10G production Binance USDM profile composition
  - BT-GAP-02B production execution-input hydration contract
  - BT-GAP-02C persisted execution closure v2
owner_package: backtest-runtime composition
public_interface: []
private_interface:
  - crypto_quant_backtest.composition._ExecutionCasePlan
  - crypto_quant_backtest.composition._HydratedExecutionCaseInputs
  - crypto_quant_backtest.composition._compose_execution_case
  - _HydratedExecutionInputs.execution_case
test_commands:
  contract_red: uv run pytest -q tests/runtime/execution_inputs/test_bt_gap02a_composition_contract.py
  boundary_red: uv run pytest -q tests/architecture/test_bt_gap02a_composition_boundary.py
  inherited: uv run pytest -q tests/runtime/execution_inputs/test_bt_gap02c_execution_closure_contract.py tests/architecture/test_bt_gap02c_execution_closure_boundary.py
  lock: uv lock --check
  diff: git diff --check
fixture_ids:
  - bt-gap02a-production-composition-v2
expected_artifacts:
  - one exact sealed ResolvedExecutionCase returned by v2 hydration
failure_contracts:
  - execution-closure-v2-unavailable-or-invalid
  - reconstructed-case-semantic-or-identity-mismatch
  - g12e-target-or-timeline-binding-mismatch
  - selected-profile-component-ref-mismatch
allowed_grade: development
evidence:
  - BT-GAP-02C PASSED typed persisted plan and executable Binance v2
  - accepted CnA v1 and Binance executable-v2 registration refs
  - superseded hidden simulation-implementation builder rejected
remaining_blockers: []
contract_commit: 49146424471bf6943e5966ff2c9753d5ff6cb1e9
hardening_commit: bb48c4f953e6fad42f0a17ae3f1c9a014baff048
implementation_commit: 33707f64f1a0da49fcc9239f04f39d56823f78ab
passed_commit: 33707f64f1a0da49fcc9239f04f39d56823f78ab
executed_commands:
  - uv run pytest -q tests/runtime/execution_inputs/test_bt_gap02a_composition_contract.py tests/architecture/test_bt_gap02a_composition_boundary.py tests/runtime/execution_inputs/test_bt_gap02c_execution_closure_contract.py tests/architecture/test_bt_gap02c_execution_closure_boundary.py tests/runtime/execution_inputs/test_execution_input_bundle_contract.py tests/runtime/execution_inputs/test_hydrate_execution_inputs.py tests/architecture/test_bt_gap02b_execution_input_boundary.py
  - uv run pytest -q tests/runtime/profiles/cn_a_share tests/runtime/profiles/binance_usdm tests/runtime/engine/test_g08h_cn_a_share_golden.py tests/runtime/engine/test_g08h_cn_a_share_journey.py tests/runtime/engine/test_g10g_binance_usdm_golden.py tests/runtime/runner/test_g10g_binance_usdm_runner.py tests/architecture/test_g08h_cn_a_share_composition_boundary.py tests/architecture/test_g10g_binance_composition_boundary.py
  - uv run pytest -q
  - uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report /tmp/bt-gap02a-analysis-schema-import-boundaries.json
  - uv lock --check
  - git diff --check
test_results:
  focused_and_inherited: 44 passed
  accepted_profiles: 48 passed
  full_repository: 1644 passed
  import_boundaries: 101 files passed
artifact_hashes:
  fixture_sha256: bfa0ddff37bb6e1c813f50da14db4abcc2fab76fa8262c522fbf5facb1b5f764
  preserved_bt_gap02b_fixture_sha256: 09578ac47f997bc4bf55119d31e97dbcad3eb71e90d93a5ef7c8e6669bd66be2
  preserved_bt_gap02c_fixture_sha256: c082042640382dde2dad61f758058ab93c3ba741ed19df0256d7989a157eced1
  preserved_cn_a_profile_fixture_sha256: aa032668a5207b61b6c8815894e0087f1c1e734d41e9707c7d32111b6c1cd79f
  preserved_binance_profile_fixture_sha256: e9e329b4cd2dfd990a8eec8460767b6b05fffcc126e876a2cdf86f15a6d06bd9
```

### BT-GAP-02A Readiness

1. BT-GAP-02C is the only persisted execution-plan and canonical-decoding authority. It already accepts a provider-side sealed case, stores its complete non-market typed plan, reloads target/timeline bytes through G12E, and rejects component, semantic, and identity mismatches before Attempt creation.
2. BT-GAP-02A deepens composition rather than restoring the superseded hidden builder. `_ExecutionCasePlan` moves to `composition.py`; `_HydratedExecutionCaseInputs` packages the typed plan, semantic spec, stream keys, target stream, and batch size; `_compose_execution_case` accepts only that value plus the resolved request and G12E reader.
3. Runtime composition is profile-neutral. It contains no CnA/Binance branch, second `BacktestProfileRegistry`, registration lookup, `implementation._build_execution_case`, factory, Protocol, callback graph, adapter, or `tests/support` dependency. Accepted profile ownership is already reduced to the persisted plan before runtime hydration.
4. `_compose_execution_case` reconstructs Timeline and identity authority from typed values, creates one exact `ResolvedExecutionCase`, recomputes the semantic spec, and verifies the complete identity manifest. `_hydrate_execution_inputs` returns that sealed case for the future BT-GAP-02 facade rather than exposing a second composition path.
5. CnA retains its accepted v1 simulation registration. Binance uses the additive executable v2 registration from BT-GAP-02C. The contract fixture freezes all six selected simulation refs for each profile and preserves G08H/G10G v1 fixture bytes.
6. `composition.py` receives no JSON/Mapping payload and owns no SchemaCatalog or reader. `execution_inputs.py` remains the sole v1/v2 decoder and structural-bundle hydration authority; G12E remains the sole MarketEvent source.
7. The old `3dbf171960e18f45d0f8216dfb175f864f065bdc` shape remains superseded: selected registration implementations do not gain private builders and the generic runtime never dispatches through hidden implementation state.
8. Acceptance is green: the private typed composition seam returns one exact sealed case, repeat hydration is byte/hash deterministic, 44 focused/inherited tests and 48 accepted-profile tests pass, the full repository passes 1644 tests, and import boundaries pass across 101 files.

## 107A. BT-GAP-02C Persisted Execution Closure v2

```yaml
id: BT-GAP-02C
status: PASSED
depends_on:
  - BT-GAP-02B immutable execution-input v1
  - G07 execution-case identity and sealing
  - G08H CnA profile composition
  - G10G Binance USDM profile composition
  - G12E MarketBundleReader
owner_package: backtest-runtime execution inputs + profile composition
public_interface:
  - crypto_quant_backtest.materialize_execution_input_bundle_v2
  - crypto_quant_backtest.BacktestExecutionRequest with schema_version=2
  - crypto_quant_backtest.BinanceUsdmProfileComposer.compose_executable
private_interface:
  - execution_case_plan@1 embedded value inside backtest_execution_input_bundle@2
  - one typed v2 reader registration in the existing execution-input SchemaCatalog
  - future package-private BT-GAP-02A composition seam
fixture_ids:
  - bt-gap02c-execution-closure-v2
expected_artifacts:
  - backtest_execution_input_bundle@2 ArtifactEnvelope
  - BacktestExecutionRequest@2 pass-by-value transport
  - additive Binance executable simulation profile v2
failure_contracts:
  - resolved-request-or-sealed-case-type-mismatch
  - case-does-not-bind-semantic-run-or-request
  - case-identity-manifest-is-missing-or-invalid
  - execution-plan-component-ref-mismatch
  - execution-plan-source-or-ref-tamper
  - execution-plan-decode-failure
  - g12e-timeline-or-target-mismatch
  - reconstructed-case-semantic-or-identity-mismatch
allowed_grade: development
test_commands:
  contract_red: uv run pytest -q tests/runtime/execution_inputs/test_bt_gap02c_execution_closure_contract.py
  boundary_red: uv run pytest -q tests/architecture/test_bt_gap02c_execution_closure_boundary.py
  inherited: uv run pytest -q tests/runtime/execution_inputs/test_execution_input_bundle_contract.py tests/runtime/execution_inputs/test_hydrate_execution_inputs.py tests/runtime/profiles/cn_a_share/test_profile_composition.py tests/runtime/profiles/binance_usdm/test_profile_composition.py tests/architecture/test_bt_gap02b_execution_input_boundary.py tests/architecture/test_g08h_cn_a_share_composition_boundary.py tests/architecture/test_g10g_binance_composition_boundary.py
  lock: uv lock --check
  diff: git diff --check
evidence:
  - executable-closure field and identity-cycle audit
  - G08H represented component refs match accepted v1 registration
  - G10G executable-v2 execution/slippage/closeout refs bind exact runtime components
  - exact constructor reconstruction for accepted G08H and G10G plan shapes
  - existing BacktestProfileRegistry remains the only profile selector
  - contract commit 23efa4fe32ea263aa41522edf0b2845c95f6123d
  - typed-hydration amendment 73d04563e21b046a26b8b3372eca38dfce59d0d1
  - constructor-hardening commit 05723dfa7179337ae51d9c3e249dae86a025a782
  - accepted-profile reconstruction contract 7bb7137f380f40e80105a80af146d1ed707b29ac
  - implementation commit 3c2a9bd0b3d070ae8a90c535cebb858105a63c62
remaining_blockers: []
passed_commit: 3c2a9bd0b3d070ae8a90c535cebb858105a63c62
executed_commands:
  - uv run pytest -q tests/runtime/execution_inputs/test_bt_gap02c_execution_closure_contract.py tests/architecture/test_bt_gap02c_execution_closure_boundary.py
  - uv run pytest -q tests/runtime/execution_inputs/test_execution_input_bundle_contract.py tests/runtime/execution_inputs/test_hydrate_execution_inputs.py tests/architecture/test_bt_gap02b_execution_input_boundary.py
  - uv run pytest -q
  - uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report /tmp/bt-gap02c-final-import-boundaries.json
  - uv lock --check
  - git diff --check
  - targeted pyright on changed production files
  - mypy across 100 source files
results:
  contract_and_boundary: 12 passed
  inherited_bt_gap02b: 23 passed
  g08h: 39 passed
  g10g: 13 passed
  domain_artifacts: 13 passed
  component_derivative_ledger: 127 passed
  full_repository: 1627 passed
  import_boundaries: 100 files passed
  targeted_pyright: 0 errors
  mypy: 100 source files, no issues
validation_gaps:
  - full pyright retains 8 pre-existing unrelated errors in ArtifactEnvelopeReader exports, composition.py, and capabilities.py
artifact_hashes:
  fixture_sha256: c082042640382dde2dad61f758058ab93c3ba741ed19df0256d7989a157eced1
  bundle_content_hash: sha256:887cc5e056cb46dfb785598eb36261f9bba6af269e87b42538f86234460b6252
  transport_canonical_sha256: sha256:bad2fef4a26b7ba09ddcc62fde064f4fb69865fdee8088ce3b4b94dff0117408
  preserved_bt_gap02b_fixture_sha256: 09578ac47f997bc4bf55119d31e97dbcad3eb71e90d93a5ef7c8e6669bd66be2
  preserved_cn_a_profile_fixture_sha256: aa032668a5207b61b6c8815894e0087f1c1e734d41e9707c7d32111b6c1cd79f
  preserved_binance_profile_fixture_sha256: e9e329b4cd2dfd990a8eec8460767b6b05fffcc126e876a2cdf86f15a6d06bd9
```

### BT-GAP-02C Readiness

1. Executable closure is an immutable data problem, not a second profile-selection problem. Bundle v2 persists the complete non-market preimage required to reconstruct one case: decision cycles, bar executions, resolved financial state, financial dispatch plan, execution-model spec, snapshot plan, and closeout-policy spec. The embedded `execution_case_plan@1` is a value inside the bundle; it receives no ArtifactRef, repository, cache, path, or public root type.
2. `materialize_execution_input_bundle_v2(*, resolved_request, execution_case)` accepts one exact sealed `ResolvedExecutionCase`. It verifies the request, build, semantic spec, semantic run, identity manifest, timeline, target digest, and case identities before emitting one `backtest_execution_input_bundle@2` Envelope. Provider code may construct the case while it still owns the rich resolved profile; Platform only stores the opaque Envelope.
3. Bundle v2 does not store the Timeline reader or target `MarketEvent` bytes. It stores timeline stream keys, target stream key, operational batch size, and the request-bound plan. G12E remains the sole MarketBundle/MarketEvent read authority; runtime reconstruction must reload and verify the exact target stream and timeline.
4. Semantic-run-derived Domain/Event IDs may be stored in the v2 plan. There is no content cycle: `semantic_run_id` derives from normalized `BacktestRequest`, resolved environment, and build manifest; `BacktestRequest` does not contain the execution-bundle ref. Hydration must nevertheless recompute every identity binding from `ExecutionCaseSemanticSpec.identity_plan` and reject any stored-ID mismatch before Attempt creation.
5. Initial financial state is stored as exact typed `ResolvedFinancialState` canonical data rather than a second Mapping template. The v2 reader in `execution_inputs` is the one reconstruction authority and canonical-byte-compares every rebuilt value. `composition.py` and profile modules do not implement another Domain/Kernel decoder.
6. `BacktestExecutionRequest` supports additive wire schema version 2 only when its single ref is `backtest_execution_input_bundle@2`. Its v1 constructor behavior and canonical bytes remain unchanged. The transport remains a value, not an Artifact, and has no second identity/ref/path/status/repository metadata.
7. CnA executable composition continues to use its accepted v1 simulation profile because its represented execution and closeout refs match concrete runtime components. Binance adds `bar.next_eligible_open.conservative.v2` through `BinanceUsdmProfileComposer.compose_executable`; v2 uses the exact concrete `next_eligible_bar_open.v1`, `zero_slippage.development.v1`, and `mark_to_market.v1` identities. G10G v1 remains immutable profile-composition evidence and is not mutated or reinterpreted as executable closure.
8. The existing `BacktestProfileRegistry` remains the only selector. Bundle hydration and generic runtime contain no CnA/Binance branch, profile plan registry, builder factory, hidden adapter, callback graph, or mutable profile state.
9. Implementation reconstructs accepted G08H nonempty Journal/Lot/snapshot/scheduled-event plans and G10G order/admission/reservation plus linear derivative/funding/margin plans through exact constructors. Opaque canonical wrappers remain limited to fields whose runtime contract is intentionally canonical payload; they do not impersonate typed values or bypass constructor invariants.
10. Acceptance passed with 12 focused contract/boundary tests, 23 inherited BT-GAP-02B tests, 39 G08H tests, 13 G10G tests, 13 Domain artifact tests, 127 component/derivative/ledger checks, 100-file import-boundary verification, and the full 1627-test repository suite. Frozen v1/v2 fixture hashes remain unchanged.

## 108. BT-GAP-02B Production Execution-Input Hydration Contract

```yaml
id: BT-GAP-02B
status: PASSED
depends_on:
  - BT-GAP-01
  - G03 financial state authorities
  - G07 auditable runner identity and publication
  - G11I strategy runtime and precomputed target stream
  - G12E persisted MarketBundleReader
  - BT-GAP-07 structural ArtifactEnvelope reader
  - PLAT-REC-03 additive execution-request ownership decision
owner_package: backtest-runtime execution inputs
public_interface:
  - crypto_quant_backtest.BacktestExecutionRequest
  - crypto_quant_backtest.materialize_execution_input_bundle
test_commands:
  focused: uv run pytest -q tests/runtime/execution_inputs/test_execution_input_bundle_contract.py tests/runtime/execution_inputs/test_hydrate_execution_inputs.py tests/architecture/test_bt_gap02b_execution_input_boundary.py
  full: uv run pytest -q
  boundary: uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/bt-gap02b-implementation-import-boundary-report.json
  lock: uv lock --check
  diff: git diff --check
fixture_ids:
  - bt-gap02b-execution-input-bundle-v1
expected_artifacts:
  - backtest_execution_input_bundle@1 ArtifactEnvelope
  - BacktestExecutionRequest@1 pass-by-value transport
failure_contracts:
  - malformed_execution_request
  - wrong_execution_input_bundle_ref
  - execution_input_unavailable
  - execution_input_tampered
  - execution_input_decode_failed
  - request_binding_mismatch
  - build_binding_mismatch
  - target_binding_mismatch
  - initial_state_binding_mismatch
  - execution_case_semantic_hash_mismatch
allowed_grade: development
evidence:
  - ResolvedExecutionCase field-to-owner audit
  - accepted Platform PLAT-REC-03 additive execution-input transport
  - user-approved repository-independence boundary: Platform does not construct or understand the initial-financial-state template
  - contract commit ed176cd002ac006de2a6b44120d5b57cebca1653
  - implementation commit 148c3e2e608e3ee5f3d70a82d198aefafed09e5e
  - G12E/tamper hardening commit 9f321780bb2e831bac521722c04af82adbd8e40e
remaining_blockers: []
passed_commit: 9f321780bb2e831bac521722c04af82adbd8e40e
executed_commands:
  - uv run pytest -q tests/runtime/execution_inputs/test_execution_input_bundle_contract.py tests/runtime/execution_inputs/test_hydrate_execution_inputs.py tests/architecture/test_bt_gap02b_execution_input_boundary.py
  - uv run pytest -q
  - uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/bt-gap02b-implementation-import-boundary-report.json
  - uv lock --check
  - git diff --check
test_results:
  focused: 23 passed
  full_repository: 1614 passed
  import_boundaries: 100 files passed
artifact_hashes:
  fixture_sha256: 09578ac47f997bc4bf55119d31e97dbcad3eb71e90d93a5ef7c8e6669bd66be2
  bundle_content_hash: sha256:cde469808ba86f5b55702a85c4d30111cb3408db2932db402d069d5889817c02
  transport_canonical_sha256: sha256:b28cfb5334bf0d87a5b2a5ef82b02afb5761ead717791bc08e000cba8325765d
  import_boundary_report_sha256: cc9d143d45930baa34019f3f0dac5c3b50386fbb54b35a5b594584e14e2f9ccf
```

### BT-GAP-02B Readiness

1. BT-GAP-02B produces only the pre-run, request-bound inputs consumed by BT-GAP-02A. It does not resolve profiles, build `ResolvedExecutionCase`, execute Attempts, publish evidence, or load completed/terminal/analysis artifacts.
2. `BacktestExecutionRequest@1` is a typed value passed by value. It embeds the exact immutable `BacktestRequest@1` plus one `backtest_execution_input_bundle@1` Domain `ArtifactRef`; the transport has no ArtifactEnvelope, catalog registration, content hash, second ref, path, timestamp, status, reader, or repository metadata.
3. The bundle exact-covers request hash, full `BuildArtifactManifest`, full `ExecutionCaseSemanticSpec`, sorted timeline stream keys, target stream key, operational timeline batch size, and `backtest_initial_financial_state_template@1`. The financial template exact-covers journal economics, ledger schema, snapshot economics, lots, existing orders/admissions/reservations, settlement state, and settlement rules while omitting composer-derived Domain IDs and derived journal/snapshot hashes.
4. Initial journal templates accept exact base `AccountingJournalEntry` payloads, including position-lot changes, and bind each entry through an `identity_plan` key. Specialized derivative/funding journal subtypes are rejected as v1 initial-state inputs. Backtest reconstructs identities after request/profile resolution.
5. G12E retains every MarketBundle/MarketEvent byte. The bundle carries only `target_stream_key` and `timeline_stream_keys`; Backtest reconstructs `PrecomputedTargetStream` through the G12E reader and verifies `request.target_stream_digest`. No market bytes, path convention, digest registry, provider selector, cache, or second repository is introduced.
6. The Backtest-owned public materializer accepts Backtest-owned typed values and the internal financial template, validates and writes one bundle ArtifactEnvelope, and is called by Backtest provider code—not by Platform semantic code. Platform treats the result as opaque, stores only the envelope through Foundation CAS, obtains its Domain ref, and passes the transport by value. Backtest imports no Platform type.
7. Pre-Attempt precedence is exact: malformed transport; wrong expected bundle-ref type/version; unavailable input; returned source/ref tamper; bundle decode failure; request, build, target, or initial-state binding mismatch; execution-case semantic-hash mismatch. Every failure creates no Attempt, terminal publication, analysis, or partial evidence.
8. The frozen fixture preserves existing `BacktestRequest@1` canonical bytes/hash and proves no MarketEvent copy or transport-level identity. The public materializer reproduces its exact envelope/ref/transport bytes; private hydration ignores `ArtifactReadResult.artifact`, verifies source/envelope/ref integrity, reconstructs typed build/spec values and the G12E target stream, and returns an atomic success-or-failure result.
9. Focused acceptance passed 23 tests, the full repository passed 1614 tests, 100 import-boundary files passed, `uv lock --check` and `git diff --check` passed, and independent architecture review returned `NONE`. The adversarial tamper finding was fixed before acceptance; the requested semantic-hash reordering was rejected because the frozen precedence intentionally places initial-state binding before final semantic-hash mismatch.

## 109. BT-GAP-04 Publication Reference Contract

```yaml
id: BT-GAP-04
status: PASSED
depends_on:
  - BT-GAP-01
  - G07
  - Platform BT-PORT-01 consumer fixture
owner_package: backtest-runtime
public_interface:
  - crypto_quant_backtest.BacktestCanonicalPublicationRef
  - crypto_quant_backtest.RunPublicationRef
test_commands:
  contract: uv run pytest -q tests/runtime/publication/test_publication_refs.py tests/runtime/integration/test_g07_auditable_run_golden.py
  boundary: uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/bt-gap-04-import-boundary-report.json
  source_types: MYPYPATH=packages/backtest-runtime/src:packages/trading-domain/src:packages/trading-kernel/src:packages/market-data-contracts/src:packages/market-bundle-builder/src uvx --from mypy==2.3.0 mypy --python-version 3.13 packages/backtest-runtime/src/crypto_quant_backtest/publication_refs.py
  test_types: MYPYPATH=packages/backtest-runtime/src:packages/trading-domain/src:packages/trading-kernel/src:packages/market-data-contracts/src:packages/market-bundle-builder/src uvx --from mypy==2.3.0 --with pytest==8.4.2 mypy --python-version 3.13 --ignore-missing-imports --follow-imports=silent tests/runtime/publication/test_publication_refs.py
  lock: uv lock --check
  diff: git diff --check
fixture_ids:
  - bt-gap04-publication-ref-v1
expected_artifacts:
  - tests/fixtures/runtime/bt-gap04-publication-ref-v1.json
  - build/acceptance/bt-gap-04-import-boundary-report.json
failure_contracts:
  - completed_ref_wrong_type_or_schema
  - terminal_ref_not_bare_artifact_ref
  - synthetic_run_outcome_wrapper
  - g07_canonical_byte_regression
allowed_grade: development
evidence:
  - exact Platform completed and all three terminal refs
  - direct completed-or-terminal run reference union
  - unchanged G07 finalized result and evaluation wires
contract_freeze_commit: 033af1fdc029e48c74fc3cae5eca08b4b3ef2e19
passed_commit: c3257643d6911bd3b63efac0899aa04d47397b05
executed_commands:
  - uv run pytest -q --junitxml=build/acceptance/bt-gap-04-pytest.xml tests/domain/artifacts/test_artifact_ref.py tests/runtime/publication/test_publication_refs.py tests/runtime/integration/test_g07_auditable_run_golden.py tests/architecture/test_public_api_imports.py tests/architecture/test_import_boundary_mutations.py
  - uv run pytest -q
  - cd .. && uvx --python 3.13.5 --from pytest==8.4.2 pytest -q -p no:cacheprovider tests/architecture/test_backtest_consumer_port.py
  - MYPYPATH=packages/backtest-runtime/src:packages/trading-domain/src:packages/trading-kernel/src:packages/market-data-contracts/src:packages/market-bundle-builder/src uvx --from mypy==2.3.0 mypy --python-version 3.13 packages/backtest-runtime/src/crypto_quant_backtest/publication_refs.py
  - MYPYPATH=packages/backtest-runtime/src:packages/trading-domain/src:packages/trading-kernel/src:packages/market-data-contracts/src:packages/market-bundle-builder/src uvx --from mypy==2.3.0 --with pytest==8.4.2 mypy --python-version 3.13 --ignore-missing-imports --follow-imports=silent tests/runtime/publication/test_publication_refs.py
  - uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/bt-gap-04-import-boundary-report.json
  - uv lock --check
  - git diff --check
test_results:
  focused_and_inherited: 42 passed
  full_repository: 1586 passed
  platform_consumer_contract: 14 passed
  independent_reviews: NONE / NONE
artifact_hashes:
  tests/fixtures/runtime/bt-gap04-publication-ref-v1.json: sha256:9cbe91becf64053fdb44cb884a8cfd621e020e8ce54e4f5f6f76411f275e3c79
  tests/fixtures/runtime/g07-auditable-synthetic-run-v1.json: sha256:60da78527bacf40af3586e9a783ad62ba07c4e160ec4b2c831fefb0385834c90
  build/acceptance/bt-gap-04-pytest.xml: sha256:ec4b949d0c57044a9d0e49466648834fccb6f415f60e1af7639733ce99ada617
  build/acceptance/bt-gap-04-import-boundary-report.json: sha256:576836a8f111d693e5a39dd3db936d199d4ae4681ce6dc92a6263db28b6887f5
  uv.lock: sha256:a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
```

### BT-GAP-04 Acceptance

1. The frozen Platform consumer fixture is executable authority where its prose summary conflicts: completed runs return a nominal `backtest_canonical_publication_ref`, while `BLOCKED`, `FAILED`, and `CANCELLED` return a bare Domain `artifact_ref`.
2. `BacktestCanonicalPublicationRef` wraps exactly one `ArtifactRef` constrained to `canonical_publication_manifest@1`. It adds no path, payload, timestamp, grade, metric, or repository state.
3. `RunPublicationRef` is the direct type union `BacktestCanonicalPublicationRef | ArtifactRef`. `run()` returns one ref value, not an optional-field container or synthetic outcome envelope. Provider/storage failures remain failures and are not members of this union.
4. Terminal status and durable evidence are recovered and verified by the future BT-GAP-03 repository. The run return itself carries no status wrapper, metrics, zero return, or synthetic terminal artifact.
5. Analysis refs remain BT-GAP-05/06. Facade sequencing remains BT-GAP-02, repository loads BT-GAP-03, and structural reader injection BT-GAP-07.
6. G07 canonicalized finalized structures remain unchanged and are validated against the existing G07 golden fixture.
7. Contract freeze commit `033af1fdc029e48c74fc3cae5eca08b4b3ef2e19` and implementation commit `c3257643d6911bd3b63efac0899aa04d47397b05` are immutable. Focused/inherited tests passed 42, the full repository passed 1586, Platform BT-PORT-01 passed 14, type/import checks passed, and both independent final reviews returned `NONE`.

## 110. BT-GAP-07 Artifact Envelope Reader Protocol

```yaml
id: BT-GAP-07
status: PASSED
depends_on:
  - BT-GAP-01
  - WP-02E
owner_package: backtest-runtime
public_interface:
  - crypto_quant_backtest.ArtifactEnvelopeReader
test_commands:
  contract: uv run pytest -q tests/runtime/ports/test_artifact_envelope_reader_contract.py
  boundary: uv run pytest -q tests/architecture/test_bt_gap07_artifact_reader_boundary.py
  lock: uv lock --check
  diff: git diff --check
fixture_ids: []
expected_artifacts: []
failure_contracts:
  - reader_contract_signature_drift
  - protocol_implementation_statement
  - root_export_drift
  - semantic_decoder_or_provider_leak
allowed_grade: development
evidence:
  - inherited domain WP-02E artifact fixtures
remaining_blockers: []
contract_freeze_commit: 9610e2985e41aeb7d94a74ce0c89c4424034fed3
implementation_commit: 8c7812aab63c017b52357ac826a25902412551bd
hardening_commit: 029ac43f6d781567cd0742594ca82c181ead0a6d
passed_commit: 029ac43f6d781567cd0742594ca82c181ead0a6d
executed_commands:
  - uv run pytest -q --junitxml=build/acceptance/bt-gap-07-pytest.xml tests/runtime/ports/test_artifact_envelope_reader_contract.py tests/architecture/test_bt_gap07_artifact_reader_boundary.py tests/domain/artifacts/test_artifact_ref.py tests/domain/artifacts/test_artifact_envelope_golden.py tests/domain/artifacts/test_schema_catalog.py
  - uv run pytest -q
  - cd .. && uvx --python 3.13.5 --from pytest==8.4.2 pytest -q -p no:cacheprovider tests/architecture/test_backtest_consumer_port.py
  - MYPYPATH=packages/backtest-runtime/src:packages/trading-domain/src:packages/trading-kernel/src:packages/market-data-contracts/src:packages/market-bundle-builder/src uvx --from mypy==2.3.0 mypy --python-version 3.13 packages/backtest-runtime/src/crypto_quant_backtest/artifact_envelope_reader.py packages/backtest-runtime/src/crypto_quant_backtest/ports.py packages/backtest-runtime/src/crypto_quant_backtest/__init__.py
  - uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/bt-gap-07-import-boundary-report.json
  - uv lock --check
  - git diff --check
test_results:
  focused_and_inherited: 17 passed
  full_repository: 1591 passed
  platform_consumer_contract: 14 passed
  independent_reviews: NONE after import-guard correction
artifact_hashes:
  tests/fixtures/domain/artifact-envelope-catalog-v1.json: sha256:ec5138bcc003ecd59a1821f20999bfea3072493e3dfccf8cd781b4f4963b7e16
  build/acceptance/bt-gap-07-pytest.xml: sha256:8221987a8ce1c31a25868f66c78fb6e09002521ec85e3fcfd37d559e660cdcc3
  build/acceptance/bt-gap-07-import-boundary-report.json: sha256:f9bed570a953dc581b2886d35b7041fa83378fec8f034353efd706025c96b809
  uv.lock: sha256:a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
```

### BT-GAP-07 Acceptance

1. The protocol freeze adds only the structural `ArtifactEnvelopeReader` seam (`read(*, ref: ArtifactRef) -> ArtifactReadResult`) and does not introduce a reader implementation.
2. `crypto_quant_backtest.ArtifactEnvelopeReader` is the sole Backtest public root export for this seam. Its exact Domain parameter/result types match Platform Integration v1.
3. `ArtifactReadResult.artifact` is not semantic authority at this boundary. BT-GAP-03 consumers must verify the exact ref/source bytes and decode through a Backtest-owned `SchemaCatalog`; providers remain structural.
4. AST and signature tests forbid filesystem, network, provider, repository, catalog, decoder, cache, registry, factory, adapter, callback, or Platform behavior in the port.
5. Provider conformance belongs to Platform fan-in and semantic verification belongs to BT-GAP-03. Contract commit `9610e2985e41aeb7d94a74ce0c89c4424034fed3`, implementation commit `8c7812aab63c017b52357ac826a25902412551bd`, and accepted hardening commit `029ac43f6d781567cd0742594ca82c181ead0a6d` are immutable.
6. Focused/inherited tests passed 17, the full repository passed 1591, Platform BT-PORT-01 passed 14, type/LSP/import checks passed, and the final independent re-review returned `NONE`.

## 111. BT-GAP-06 Analysis Artifact Schema

```yaml
id: BT-GAP-06
status: PASSED
depends_on:
  - BT-GAP-01
  - BT-GAP-04
  - G07 completed evidence
owner_package: backtest-runtime analysis schema
public_interface:
  - crypto_quant_backtest.AnalysisArtifactRef
  - crypto_quant_backtest.BacktestMetricProfile
  - crypto_quant_backtest.BacktestAnalysis
  - crypto_quant_backtest.VerifiedBacktestAnalysis
private_interface: []
test_commands:
  contract_red: uv run pytest -q tests/runtime/analysis/test_analysis_contract.py
  boundary_red: uv run pytest -q tests/runtime/analysis/test_analysis_boundary.py
  inherited: uv run pytest -q tests/domain/artifacts/test_artifact_ref.py tests/runtime/publication/test_publication_refs.py tests/architecture/test_public_api_imports.py
  lock: uv lock --check
  diff: git diff --check
fixture_ids:
  - bt-gap06-analysis-v1
expected_artifacts:
  - backtest_metric_profile@1 ArtifactEnvelope
  - backtest_analysis@1 ArtifactEnvelope
  - verified loaded analysis value with one AnalysisArtifactRef
failure_contracts:
  - wrong-analysis-or-metric-profile-artifact-type-or-version
  - stored-analysis-self-reference
  - source-publication-or-execution-result-link-mismatch
  - invalid-result-grade
  - noncanonical-simple-period-return
  - invalid-trade-count
  - terminal-publication-is-not-analyzable
allowed_grade: development
evidence:
  - architecture section 15.6 analysis boundary
  - Platform BT-PORT-01 complete-analysis view
  - user-confirmed missing/null, Fill-count, return, rounding, and profile authorities
remaining_blockers: []
contract_commit: 70fd2a45c3c2ed84d01d331d0a7720fdfe8589cf
implementation_commit: 61a747f7a772b3cffd0d7fe7291d98e351820047
passed_commit: 61a747f7a772b3cffd0d7fe7291d98e351820047
executed_commands:
  - uv run pytest -q tests/runtime/analysis/test_analysis_contract.py tests/runtime/analysis/test_analysis_boundary.py
  - uv run pytest -q tests/domain/artifacts/test_artifact_ref.py tests/runtime/publication/test_publication_refs.py tests/architecture/test_public_api_imports.py
  - uv run pytest -q
  - uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report /tmp/bt-gap02a-analysis-schema-import-boundaries.json
  - uv lock --check
  - git diff --check
test_results:
  focused_schema: 8 passed
  inherited: 13 passed
  full_repository: 1644 passed
  import_boundaries: 101 files passed
artifact_hashes:
  fixture_sha256: 7764e978cc530d1e518f4c4b4a714627b49b09dc2fe594eacf1633a9d8ba5ef1
  metric_profile_payload_sha256: sha256:d2448e93df20789c4f74064bfb5cf34bc116ab3f070010342a3eadc60ec2275f
  metric_profile_content_hash: sha256:bced4dbef8bbf6e1ec9821ae3b68e8c6ce2bbed953f95fe1214c8e21676dbd6a
  analysis_payload_sha256: sha256:e425e84d809f45a5306f7e374a95bec414464cc5c4cdef20141da71bf7726862
  analysis_content_hash: sha256:29279641f97e3e3b2d752642c884561fc0c65947e11e064aba5aad755e9a69c0
```

### BT-GAP-06 Readiness

1. `backtest_metric_profile@1` is the sole v1 metric-semantic authority. Profile `simple_period_return.fill_count.v1` declares run-boundary snapshots, simple period return, no annualization/risk-free/benchmark/drawdown calculation, source-result reporting currency, external-cash-flow subtraction, authoritative Fill count, and null encoding for a valid missing metric. It is a fixed v1 profile, not a generic registry or framework.
2. The return is `(ending_equity - starting_equity - net_external_cash_flow) / starting_equity`. Starting and ending equity come from the exact run-boundary `PortfolioSnapshot` values; net external cash flow is derived from authoritative Journal cash-flow evidence under the profile. A zero or otherwise unusable starting-equity denominator produces `simple_period_return: null`, never zero.
3. `trade_count` is the number of authoritative `Fill` values in the completed `EngineExecutionResult`. It is a non-negative exact integer and does not count Orders, round trips, position transitions, or Journal entries.
4. Conclusive return wire values are ordinary canonical decimal strings with at most 18 fractional digits, ROUND_HALF_EVEN, no exponent, no trailing fractional zero, and no negative zero. The profile owns this policy; Engine state and `execution_result_hash` remain unchanged.
5. The immutable `backtest_analysis@1` payload contains metric-profile ref, source canonical-publication ref, source execution-result hash, return/null, Fill count, and result grade. It does not contain `analysis_ref`, its own content hash, a path, status, timestamp, reader, repository, or Platform metadata.
6. `VerifiedBacktestAnalysis` is a loaded value, not another Artifact. BT-GAP-03 attaches the exact derived `AnalysisArtifactRef` to the verified stored payload and exposes the seven-field Platform view. The local fixture computes real Backtest content refs; BT-PORT hash literals remain test-support placeholders while artifact type/version and source/metric linkage semantics remain exact.
7. BT-GAP-06 implements only the four passive schema values and their constructor invariants. It adds no decoder, derive function, repository, reader, SchemaCatalog, MetricRegistry, MetricEngine, provider, filesystem path, or Platform import. BT-GAP-05 owns completed-only derivation and BT-GAP-03 owns verified loading.
8. Acceptance is green: all eight focused schema/boundary tests and thirteen inherited ref/publication/import tests pass; the full repository passes 1644 tests and import boundaries pass across 101 files. Frozen fixture and Platform-projection bytes remain unchanged.

## 112. BT-GAP-05 Completed-Only Analysis Runtime

```yaml
id: BT-GAP-05
status: PASSED
depends_on:
  - BT-GAP-01
  - BT-GAP-04
  - BT-GAP-06
  - G07 completed canonical evidence
owner_package: backtest-runtime analysis runtime
public_interface:
  - crypto_quant_backtest.VerifiedCompletedPublication
  - crypto_quant_backtest.BacktestAnalysisRuntime
  - crypto_quant_backtest.BacktestAnalysisRuntime.derive
  - crypto_quant_backtest.ArtifactEnvelopePublisher
private_interface:
  - crypto_quant_backtest.analysis_derivation._calculate_simple_period_return
test_commands:
  focused: uv run pytest -q tests/runtime/analysis/test_analysis_contract.py tests/runtime/analysis/test_analysis_boundary.py tests/runtime/analysis/test_analysis_derivation_contract.py tests/runtime/analysis/test_analysis_derivation_boundary.py
  inherited: uv run pytest -q tests/runtime/integrity tests/runtime/evidence tests/runtime/publication
  platform_contract: uvx --python 3.13.5 --from pytest==8.4.2 pytest -q -p no:cacheprovider tests/architecture/test_backtest_consumer_port.py
  full: uv run pytest -q
  boundaries: uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml
  lock: uv lock --check
  diff: git diff --check
fixture_ids:
  - bt-gap05-completed-analysis-v1
expected_artifacts:
  - one immutable backtest_analysis@1 ArtifactEnvelope published through exact put(envelope)
  - one AnalysisArtifactRef returned by derive
  - one verified completed loaded value shared with future BT-GAP-03
failure_contracts:
  - terminal-or-unverified-publication-is-not-analyzable
  - wrong-or-foreign-metric-profile-ref
  - metric-profile-ref-does-not-bind-v1-profile
  - publisher-failure
  - publisher-returned-ref-does-not-bind-envelope
  - unusable-starting-equity-or-currency-evidence-yields-null
allowed_grade: development
evidence:
  - authoritative run-boundary PortfolioSnapshot equity
  - authoritative Journal net external cash flow after the initial-state prefix
  - authoritative CanonicalExecutionSummary Fill count
  - immutable source publication and execution-result linkage
  - independent implementation review and clean follow-up review
remaining_blockers: []
contract_and_implementation_commit: c8de3d447ffd9fccfe507e2fbdc5c77c70aac041
publication_hardening_commit: 1cbf97c9f8ccc7b225da49379c4db08fe877e438
shared_publisher_hardening_commit: 39863c58ace1d996f3e814835836ec46e2aa3794
passed_commit: 39863c58ace1d996f3e814835836ec46e2aa3794
executed_commands:
  - uv run pytest -q tests/runtime/analysis/test_analysis_contract.py tests/runtime/analysis/test_analysis_boundary.py tests/runtime/analysis/test_analysis_derivation_contract.py tests/runtime/analysis/test_analysis_derivation_boundary.py tests/runtime/integrity tests/runtime/evidence tests/runtime/publication
  - uv run pytest -q
  - uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report /tmp/bt-gap05-main-import-boundaries.json
  - uv lock --check
  - git diff --check
  - uvx --python 3.13.5 --from pytest==8.4.2 pytest -q -p no:cacheprovider tests/architecture/test_backtest_consumer_port.py
test_results:
  focused_and_inherited: 83 passed
  full_repository: 1680 passed
  import_boundaries: 105 files passed
  platform_consumer_contract: 15 passed
  lsp: clean
  independent_followup_review: NONE
artifact_hashes:
  fixture_sha256: f988ca0d779c68a0f05e5b06caf20c68b578a6c1ff7210307816f0e4835b4f2e
  preserved_bt_gap06_fixture_sha256: 7764e978cc530d1e518f4c4b4a714627b49b09dc2fe594eacf1633a9d8ba5ef1
  metric_profile_content_hash: sha256:bced4dbef8bbf6e1ec9821ae3b68e8c6ce2bbed953f95fe1214c8e21676dbd6a
  analysis_payload_sha256: sha256:f3218fb53f78e28db07c5d5d324314cea4160fdfe6b6430065fdb36116e48430
  analysis_content_hash: sha256:0d085f4848588f2683a7d6ba81053a18e8a3bd316b1603a758fc35756c68ba1c
```

### BT-GAP-05 Acceptance

1. `VerifiedCompletedPublication` is the single upstream loaded-value contract shared by BT-GAP-05 and the future BT-GAP-03 repository. It holds the accepted finalized canonical publication and exact sealed execution case, verifies case/result/request/target/identity bindings, preserves the initial Journal prefix, and validates run-boundary account/reporting-currency context. It introduces no second status, identity, ref, repository, or evidence copy.
2. `BacktestAnalysisRuntime` is the sole derive runtime. Its public `derive(completed, metric_profile_ref)` accepts only the exact verified COMPLETED value and the exact accepted `backtest_metric_profile@1` ref. Terminal refs and unverified objects fail structurally before publication.
3. The runtime derives `simple_period_return` from starting/ending authoritative `PortfolioSnapshot.equity` and net external cash flow from authoritative post-initial-prefix Journal entries. Missing/unusable currency or denominator evidence produces `null`; conclusive values follow the BT-GAP-06 18-place ROUND_HALF_EVEN canonical-decimal policy. `trade_count` is the authoritative Fill count.
4. Derivation constructs one immutable `backtest_analysis@1` payload linked to metric profile, source canonical publication, source execution-result hash, and result grade. The shared exact structural `ArtifactEnvelopePublisher.put(*, envelope) -> ArtifactRef` port is also consumed by BT-GAP-02; it contains no implementation or provider semantics. The runtime verifies the returned exact ref and returns only `AnalysisArtifactRef`. `VerifiedBacktestAnalysis` remains exclusively the future BT-GAP-03 loaded view.
5. Repeated derivation publishes byte-identical envelopes and returns the same content-addressed ref. Publisher exceptions remain provider/storage failures; wrong returned refs fail closed. No repository, reader, SchemaCatalog, MetricRegistry, MetricEngine, cache, path convention, simulator, PnL authority, Platform import, or tests/support production import is introduced.
6. Acceptance is green: 83 focused/inherited tests passed before the shared publisher hardening; the final integrated repository passes 1680 tests, import boundaries pass across 105 files, the Platform consumer contract passes 15 tests, LSP/lens checks are clean, and the independent follow-up review reports no blocker or fix worth doing now.

## 113. BT-GAP-03 Verified Evidence Repository

```yaml
id: BT-GAP-03
status: PASSED
depends_on:
  - BT-GAP-02
  - BT-GAP-05
  - BT-GAP-06
  - BT-GAP-07
owner_package: backtest-runtime verified evidence repository
public_interface:
  - crypto_quant_backtest.BacktestEvidenceRepository
  - crypto_quant_backtest.BacktestEvidenceRepository.load_completed
  - crypto_quant_backtest.BacktestEvidenceRepository.load_terminal
  - crypto_quant_backtest.BacktestEvidenceRepository.load_analysis
  - crypto_quant_backtest.BacktestEvidenceFailureCode
  - crypto_quant_backtest.BacktestEvidenceError
  - crypto_quant_backtest.VerifiedCompletedPublicationV2
  - crypto_quant_backtest.VerifiedTerminalPublication
  - crypto_quant_backtest.TerminalStatus
  - crypto_quant_domain.ArtifactNotFoundError
  - crypto_quant_domain.ArtifactRetentionUnavailableError
failure_contracts:
  - PORT_REF_TYPE_MISMATCH
  - PORT_REF_NOT_FOUND
  - PORT_EVIDENCE_TAMPERED
  - PORT_MANIFEST_INVALID
  - PORT_RETENTION_UNAVAILABLE
  - PORT_TERMINAL_NOT_ANALYZABLE
  - PORT_ANALYSIS_LINK_MISMATCH
completed_evidence_closure_commit: f605af3769e79fe757a9d3750186351621577c47
repository_implementation_commit: dfcd49508854abcb41702b7dbd9acee535608515
passed_commit: dfcd49508854abcb41702b7dbd9acee535608515
executed_commands:
  - uv run pytest -q tests/runtime/evidence_repository/test_evidence_repository.py tests/runtime/integrity/test_completed_publication_v2.py tests/runtime/analysis/test_analysis_derivation_boundary.py
  - uv run pytest -q
  - uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report /tmp/bt-gap03-import-boundaries.json
  - uv lock --check
  - git diff --check
  - cd /tmp && /tmp/backtest-bt-gap03-repository/.venv/bin/python -m pytest -q tests/architecture/test_backtest_consumer_port.py
test_results:
  focused_final: 37 passed
  full_repository: 1715 passed
  import_boundaries: 106 files passed
  platform_consumer_contract: 15 passed
  lsp: clean
  independent_followup_review: NONE
artifact_hashes:
  completed_publication_v2_fixture_sha256: 71c3ff2bfa71ef07eb8d95e80914db35549a1ba53d5c1f1ddf447d7a6265916b
  repository_contract_fixture_sha256: e72648ac1c33812f610f988295391b0d82932ecfc26f4db9a8f3cf98e07b42e5
remaining_blockers: []
```

### BT-GAP-03 Acceptance

1. `BacktestEvidenceRepository` is the sole verified load authority for completed, terminal, and analysis evidence. It accepts only exact nominal refs, delegates structural retrieval through the frozen `ArtifactEnvelopeReader`, ignores provider-supplied hydrated artifacts, and semantically decodes only canonical `source_bytes` through one Backtest-owned multi-version `SchemaCatalog`.
2. The additive `completed_backtest_result@2` preserves the `canonical_publication_manifest@1` three-child root and all legacy v1 bytes/APIs. Its exact `EngineExecutionContext` and canonical evidence-manifest ref make starting financial state, initial Journal boundary, execution case identity, and the complete Attempt evidence graph reachable without profile resolution, hidden paths, or a second repository.
3. Completed loading verifies root and child refs, source hashes, byte counts, schema versions, normalized role/path/type layouts, canonical Attempt/integrity/result hashes, consistency and rebuild evidence, evidence-manifest and finalized-evidence identities, market-bundle and Attempt-record links, canonical execution-summary hash, engine context, Journal prefix, and run-boundary reporting-currency invariants before producing the lean exact `VerifiedCompletedPublicationV2`.
4. Terminal loading supports only resolution BLOCKED evidence, Attempt BLOCKED/FAILED/CANCELLED manifests, and integrity-evaluation manifests. It verifies all structurally reachable children before `PORT_TERMINAL_NOT_ANALYZABLE`; completed publications never acquire a synthetic terminal wrapper.
5. Analysis loading reconstructs exact `backtest_analysis@1` and the accepted metric profile, then reloads the linked completed publication and validates source publication, execution-result hash, result grade, and profile links before returning `VerifiedBacktestAnalysis`.
6. Failure precedence is frozen as ref type, root not found, tamper, manifest invalid, linked retention unavailable, terminal not analyzable, and analysis-link mismatch. Additive Domain errors distinguish not-found from retention-unavailable without changing the structural reader signature.
7. Acceptance is green: 37 final focused tests and 1715 full-repository tests pass; import boundaries pass across 106 files; the Platform consumer contract passes 15 tests; lock, diff, LSP, and lens checks are clean; the independent fix-verification review reports `NONE`.

## 114. BT-GAP-08 Clean P00 Package Revision

```yaml
id: BT-GAP-08
status: PASSED
depends_on:
  - BT-GAP-02
  - BT-GAP-03
  - BT-GAP-05
  - BT-GAP-06
accepted_package_revision: 9e5937895d7559b8537a4595d73b6aabc94f6f13
accepted_tree: clean detached worktree
clean_worktree: /tmp/backtest-bt-gap08-clean
install_command: uv sync --locked
installed_packages:
  - crypto-quant-domain==0.1.0
  - crypto-quant-market-data==0.1.0
  - crypto-quant-trading==0.1.0
  - crypto-quant-backtest==0.1.0
  - crypto-quant-bundle-builder==0.1.0
executed_commands:
  - git worktree add --detach /tmp/backtest-bt-gap08-clean 9e5937895d7559b8537a4595d73b6aabc94f6f13
  - test -z "$(git status --porcelain)"
  - uv sync --locked
  - uv run --locked python -c "import crypto_quant_domain, crypto_quant_market_data, crypto_quant_trading, crypto_quant_backtest, crypto_quant_bundle_builder"
  - uv run --locked pytest -q
  - uv run --locked python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report /tmp/bt-gap08-import-boundaries.json
  - uv lock --check
  - sha256sum uv.lock pyproject.toml packages/*/pyproject.toml
  - test -z "$(git status --porcelain)"
test_results:
  clean_install: 5 workspace packages built and installed
  public_root_imports: 5 passed
  full_repository: 1715 passed
  import_boundaries: 106 files passed
  final_worktree_status: clean
package_hashes:
  uv_lock_sha256: a07106c285b2c454d0528411c79988881b3ff87c0a84d04228d94c186e9d3d8d
  root_pyproject_sha256: d06e6db31a4050ace93efad2c73c8da532cd4990612a7bcf69bb9e945fb51c4d
  backtest_runtime_pyproject_sha256: 2d8c0ffbc581ae4e8e75f974f6f4c3d897ca7f24620a8a8955568073f1749e5b
  market_bundle_builder_pyproject_sha256: ebde64b75bf939308ae2c010d8218df9b322d6c48e5260e6202b981beca97e7a
  market_data_contracts_pyproject_sha256: 8e63e9a1ea212c3003da3a6e48776f76800d088915a100ae517251cbbe4980cb
  trading_domain_pyproject_sha256: 6552f027631013c41073f394a3ac8c16326fe56f27313bcc864074255682f734
  trading_kernel_pyproject_sha256: 68dedd449a9aeb56c9fd547d675cd3029c7a4102af13ac000645913515e5acf2
remaining_blockers: []
```

### BT-GAP-08 Acceptance

1. `9e5937895d7559b8537a4595d73b6aabc94f6f13` is the accepted lowercase 40-character Backtest package revision. It contains the accepted Domain `ArtifactRef`, Backtest facade, execution closure, structural reader, completed-only analysis, passive analysis schema, additive completed-publication v2 closure, verified evidence repository, frozen fixtures, and acceptance records through BT-GAP-03.
2. Acceptance was executed in a fresh detached worktree, not the maintainer's dirty sibling worktree. Both pre-install and post-validation `git status --porcelain` were empty; the pre-existing maintainer `.gitignore` change and untracked Platform dependency note were neither modified nor used as evidence.
3. `uv sync --locked` built and installed all five workspace packages from the accepted tree and one root lock. Public imports for Domain, Market Data, Trading, Backtest, and Bundle Builder succeeded without `PYTHONPATH`, sibling checkout imports, editable external paths, or a leaf lock.
4. The clean installed tree passes all 1715 repository tests and all 106 import-boundary files. The exact root lock and all package descriptor hashes are recorded above for Platform handoff.
5. This receipt closes only Backtest package-revision acceptance. Platform `P00-SEAM-01` still owns the real Foundation structural-reader binding, unchanged BT-PORT consumer suite, integration provider tests, Platform root lock, and fan-in receipt; it must consume this SHA without copying Backtest evidence or semantics.

## 115. PASSED 记录格式

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
