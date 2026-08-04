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
|---|---|---|---|---|
| WP-00A | PASSED | repository root | none | none |
| WP-00B | READY | repository root | WP-00A | none |
| WP-00C | DRAFT | repository root + parity tooling | WP-00B | 三个来源项目 immutable identity |
| WP-01A | DRAFT | trading-domain | G00 | Numeric Interface/fixtures/commands |
| WP-01B | DRAFT | trading-domain | WP-01A | Time/DST fixtures/commands |
| WP-01C | DRAFT | trading-domain | WP-01B | ID namespace/version fixtures |
| WP-01D | DRAFT | trading-domain | WP-01A–WP-01C | Canonical golden bytes/hash |
| WP-02A | DRAFT | trading-domain | G01 | Instrument identity fixtures |
| WP-02B | DRAFT | trading-domain | WP-02A | Candidate/Validated wire fixtures |
| WP-02C | DRAFT | trading-domain | WP-02A | Order/Execution schema fixtures |
| WP-02D | DRAFT | trading-domain | WP-02A | Accounting schema fixtures |
| WP-02E | DRAFT | trading-domain | WP-01D | Envelope/Catalog fixtures |
| WP-02F | DRAFT | trading-kernel | WP-02A–WP-02D | Kernel Profile Port contracts |
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
status: READY
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
passed_commit: null
artifact_hashes: []
```

### WP-00B Readiness

已确认使用仓库自有的标准库 AST checker，不引入 `import-linter` 或 `pytest-socket`。Policy 和 Checker 必须满足：

1. Policy schema/version 未识别时 fail closed；
2. 普通 import、from import、字面量 dynamic import 均被检查；
3. 受保护目录中的非字面量 dynamic import 默认拒绝，allowlist 必须精确记录 caller path、target prefix 和 reason；
4. 跨 Package 只能导入目标 package root Public API；
5. Runtime 的 DNS/socket/HTTP 网络入口在 pytest 进程中全局阻断；阻断测试先确认 guard 已安装，再触发 guard，不允许执行真实网络 syscall；
6. JSON report 按 rule、source path、line、target 稳定排序，不包含 wall-clock time；
7. Checker、Fixture 和报告生成不得修改 tracked worktree。

WP-00B 当前状态为 `READY`，只有用户明确要求开始实现后才执行。

## 6. PASSED 记录格式

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
