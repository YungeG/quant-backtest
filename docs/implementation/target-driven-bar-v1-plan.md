# Target-driven Bar v1：模块化实施与验收计划

状态：Draft；用于拆分工作，不代表已经授权开始实现。

关联设计：`docs/architecture/backtest-system-design.md`

计划拆分、依赖 DAG、受控并行与风险分级验证规则：`docs/implementation/plans/README.md`。本文件暂作为已完成历史和未迁移计划的聚合索引；后续优先迁移活跃 G11/G12 sections，不重写已冻结历史。

## 1. 目标

将 Target-driven Bar v1 拆成可以独立开发、测试、评审和回滚的小模块，避免把“完整回测系统”作为一个任务交付。

每个 Work Package 必须：

- 只拥有一个清晰职责；
- 暴露小而稳定的公开接口；
- 不通过跨模块内部状态读取完成工作；
- 具有独立验收命令和黄金 Fixture；
- 在前置 Gate 未通过前不进入后续实现；
- 不授权真实下单、资金操作、网络数据读取或自动部署。

## 2. 物理 Package 与依赖

第一阶段保持一个 Git 仓库、五个 Python package：

```text
packages/trading-domain          # 领域值、事件、Schema、规范化身份
packages/trading-kernel          # 分配、风险、规划、订单、结算、核算
packages/market-data-contracts   # Bundle Manifest、Reader、Cursor、Repository contract
packages/market-bundle-builder   # Source→Normalize→Validate→发布不可变 Bundle
packages/backtest-runtime        # 历史 Timeline、模拟执行、Runner、Evidence
```

允许依赖：

```text
trading-domain ← trading-kernel ← backtest-runtime
      ↑                                │
      └── market-data-contracts ←──────┘
                  ↑
        market-bundle-builder
```

`market-data-contracts` 必须保持轻量，不安装供应商 SDK 或在线构建依赖。Backtest Runtime 只依赖其只读接口；MarketBundle Builder 是独立写侧工具。

禁止依赖：

- `trading-domain` 依赖其他四个 package；
- `trading-kernel` 依赖 Backtest Runtime、Pandas、供应商 SDK 或 Hummingbot；
- `market-data-contracts` 依赖 Trading Kernel、Backtest Runtime、在线 Source Adapter 或供应商 SDK；
- `market-bundle-builder` 依赖 Trading Kernel 或 Backtest Runtime；
- `backtest-runtime` 依赖 `market-bundle-builder`、在线 Source Adapter 或供应商 SDK；
- Strategy 或 Profile 读取 Ledger、Runner、Engine 的私有状态；
- `crypto-quant-platform` 成为交易或核算实现的所有者。

## 3. 通用 Definition of Done

可执行验收状态、命令、Fixture 和 Evidence 的权威索引见：

- `docs/implementation/acceptance-matrix.md`

只有 Acceptance Matrix 中状态为 `READY` 的 Work Package 才允许进入实现；`DRAFT` 禁止实现，`PASSED` 必须记录 immutable commit、实际命令和 Artifact hash。

每个 Work Package 合并前必须满足：

1. 公共 API 和不变量有文档或类型说明。
2. 正常路径、边界路径和失败路径均有测试。
3. 权威数值不经过 JSON float。
4. 权威时间不接受 naive/local datetime。
5. 测试不访问网络、系统当前业务时间或可变外部数据。
6. 同一输入重复执行产生相同 canonical bytes/hash。
7. 错误不得通过 `None`、空集合或日志静默吞掉。
8. 新 Artifact 有 `schema_version` 和 canonical serialization Fixture。
9. 新模块没有违反依赖图的 import。
10. 尚未实现的能力显式 reject/block，不能假装支持。
11. 迁移自现有实现的行为具有固定 source commit/file hash、Migration Mode、Comparator Contract 和模块级 ParityReport。

每个 Gate 使用三类验收：

- **Contract**：公开输入、输出和失败语义正确；
- **Fixture**：黄金场景结果正确；
- **Boundary**：依赖、确定性和 fail-closed 约束正确。

## 4. Gate 总览

```text
G00 仓库与依赖护栏
 ↓
G01 精确值、时间、身份和 Canonical 基础
 ↓
G02 领域契约、Profile Ports 与 Schema
 ↓
G03 Journal/Ledger 最小财务内核
 ↓
G04 Strategy Target 校验、批次和组合物化
 ↓
G05 Order 生命周期、预留、结算和再平衡
 ↓
G06 Deterministic Bar Engine Harness
 ↓
G07 Auditable Runner、Canonical Evidence 与重复运行确定性
 ├── G08A–G08H A 股 Cash Profile
 └── G09A–G09H Linear Perpetual Accounting
          ↓
        G10A–G10H Binance USD-M Profile
 ↓
G11A–G11J Strategy Runtime
 ↓
G12A–G12M 真实 MarketBundle 与逐市场 Decision-grade Qualification
```

G06 是第一条可执行 Engine 纵向切片，但不产生正式 Run Outcome；G07 才是第一条可审计 development-grade Run。G08 和 G10 分别证明市场差异不会污染主循环。G00–G07 完成前不并行开发真实市场 Adapter。

---

## 5. G00：仓库与依赖护栏

### WP-00A Workspace skeleton

工具基线：`uv workspace + root uv.lock + setuptools.build_meta + Python 3.13 only`。所有 package 使用 `requires-python = ">=3.13,<3.14"`，根目录使用 `.python-version = 3.13`。开发环境可以使用 workspace install；decision-grade BuildArtifact 必须来自独立构建的 immutable Wheel，不能来自 editable source，并记录精确 Python patch version。

拥有：

- 根级 `[tool.uv.workspace]` 和统一 `uv.lock`；
- 五个 package 的 `pyproject.toml`、`src/`、`tests/`，每个 package 使用 `setuptools.build_meta`；
- 根级测试和静态检查入口；
- 固定 Python 版本范围与 dependency groups；
- package wheel build/import smoke test；
- 根级产物目录约定：`build/acceptance/`、`build/coverage/`、`build/wheels/` 全部忽略提交，静态 Golden 保存在 `tests/fixtures/`，Run Evidence 保存在 `runs/`。

不拥有：任何交易逻辑。

验收：

- 五个 package 可以分别 build 和 import；
- `uv sync --all-packages --group dev` 可以从 lock 创建完整开发环境；
- `uv run pytest` 可以从仓库根运行测试；
- `uv build --package <package-name> --out-dir build/wheels` 可以分别构建五个 package；
- CI 可以上传 `build/acceptance/`，但临时 actual output 不提交 Git；
- CI 不依赖开发者机器上的 editable source；
- `git status` 在测试后保持干净。

### WP-00B Dependency boundary checks

工具基线：仓库自有、仅依赖 Python 标准库的 AST checker；不引入 `import-linter` 或网络测试插件。

拥有：

```text
architecture/import-boundaries.toml
                         # versioned policy、package ownership、允许依赖、禁用前缀和 dynamic import allowlist
tools/architecture/check_import_boundaries.py
                         # fail-closed AST checker 和 deterministic JSON report
tests/conftest.py        # 全局 DNS/socket/HTTP 底层网络阻断
tests/architecture/test_import_boundary_mutations.py
tests/architecture/test_network_isolation.py
tests/architecture/test_public_api_imports.py
tests/fixtures/architecture/import-boundary-mutations-v1/
```

Policy 要求：

- checker 无外部依赖，不 import 任何 Workspace Package；
- Policy schema/version 不识别时失败；
- 静态 `import`、`from ... import ...` 和可识别的 `importlib.import_module`/`__import__` 均进入检查；
- 受保护目录中的非字面量 dynamic import 默认拒绝，只能通过包含 caller path、target prefix 和 reason 的精确 allowlist 放行；
- 跨 Package import 只能指向目标 package root Public API，不允许依赖其内部模块；
- Report 按 rule、source path、line、import target 稳定排序，且不包含 wall-clock time。

验收命令：

```text
uv run python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report build/acceptance/wp-00b-boundary-report.json
uv run pytest -q tests/architecture/test_import_boundary_mutations.py
uv run pytest -q tests/architecture/test_network_isolation.py tests/architecture/test_public_api_imports.py tests/architecture/test_repository_cleanliness.py
```

验收：

- 人为加入 `trading-domain -> backtest-runtime` import 时测试失败；
- 人为加入 `trading-kernel -> pandas/hummingbot/vendor SDK` import 时测试失败；
- 人为加入 Generic Kernel module → concrete `profiles/binance_usdm` 或 `profiles/cn_a_share` import 时测试失败；
- 人为加入 `market-data-contracts -> vendor SDK` 或 `backtest-runtime -> market-bundle-builder` import 时测试失败；
- Runtime 的在线网络调用在测试中被阻断，测试不得为了证明阻断而先执行真实网络 syscall；
- package public API 不要求调用方导入内部目录；
- 非字面量 dynamic import 未在精确 allowlist 中登记时失败；
- Checker 和网络阻断测试不修改 tracked worktree。

### WP-00C Legacy Baseline and Migration Harness

工具基线：`PyYAML` 是本 WP 唯一新增 external seam，只用于读取受控 `source-map.yaml`；Snapshot、Comparator 和 ParityReport 使用标准库 `tarfile`、`gzip`、`hashlib`、`decimal` 和 JSON。

拥有：冻结迁移来源身份、Migration Source Map、Comparator Contract 目录和模块级 ParityReport Harness。

产物：

```text
docs/migration/source-map.yaml
                         # Source Map schema v1、显式 include_files、provenance 和 migration units
tools/migration/freeze_source_snapshot.py
                         # 从声明文件列表捕获实际 worktree bytes，生成 deterministic tar.gz + manifest
tools/migration/verify_legacy_baseline.py
                         # 完全离线验证 Source Map、archive、manifest 和 aggregate identity
tools/migration/run_parity.py
                         # Comparator Contract v1 和 first-divergence ParityReport CLI
tests/parity/contracts/comparator-contract-v1.schema.json
tests/parity/fixtures/legacy-sources/
tests/parity/fixtures/comparator-v1/
tests/parity/test_source_snapshots.py
tests/parity/test_comparator_contract.py
tests/parity/test_parity_report_harness.py
```

首批 Snapshot scope：

- `crypto-quant-core`：12 个核心源码、测试及 package metadata 文件；base commit `348b9e56b99c8ee2999aa8cdfcf91a18ecce9019`；
- `cycle-rotation-platform`：8 个架构、Strategy contract 和交易语义文件；base commit `91cd8e182b736a07319e0f504e64572b32ea7dea`；
- `crypt-gemini`：28 个 `hummingbot_audited`、`blend_v2/execution.py` 和 `mm_l1_replay` 文件；base commit `ba36e8a2b9ca1b1a949cf71cc93e175c9ef5e014`。

Snapshot archive 规则：成员按路径排序，mtime/uid/gid 固定为零，owner/group 为空，只保留 regular file bytes 和 executable bit；禁止 symlink、absolute path、`..`、重复成员及 scope 外文件。Archive SHA-256 是 Snapshot ID，Manifest 另含逐文件 SHA-256、size、mode 和 canonical content-tree hash。

允许 Migration Mode：

- `copy_with_parity`
- `reimplement_with_reference`
- `new_capability`
- `intentional_semantic_change`

验收：

- 三个来源仓库都按显式 include scope 生成内容寻址 Source Snapshot、逐文件 SHA-256 Manifest 和 aggregate hash；
- 来源仓库是否 dirty 不构成阻断；范围内读取 Snapshot 时的实际文件字节并纳入 modified/untracked 文件，范围外 dirty 内容一律忽略；
- Base commit、remote 和 clean/dirty 状态只记录为 provenance，不能替代 aggregate snapshot hash；
- Snapshot 归档和 Manifest 作为受控 Golden Fixture 提交，后续验证不依赖原来源仓库仍然存在；
- `intentional_semantic_change` 必须引用 ADR；
- Comparator 按字段声明 `exact`、`quantized`、`sequence`、`explicit_tolerance` 或 `approved_change`，禁止全局 epsilon；
- `quantized` 必须声明 Decimal quantum 和 rounding；`explicit_tolerance` 必须逐字段声明 absolute/relative tolerance；
- 所有未分类字段、重复规则、非法 tolerance、sequence 首个差异和 approved change 缺失引用均 fail closed；
- ParityReport 固定记录 contract hash、expected/actual hash、first divergence、Migration Mode 和 verdict；
- 来源后续变化不能改写旧 Migration Evidence；验证命令不读取原来源仓库。

验收命令：

```text
uv run python tools/migration/verify_legacy_baseline.py --root . --source-map docs/migration/source-map.yaml --report build/acceptance/wp-00c-source-baseline-report.json
uv run pytest -q tests/parity/test_source_snapshots.py tests/parity/test_comparator_contract.py
uv run pytest -q tests/parity/test_parity_report_harness.py tests/architecture/test_repository_cleanliness.py
```

### Gate G00

只有 Workspace smoke test、dependency checks 和 Legacy Baseline Harness 全部通过，才能实现领域类型。

---

## 6. G01：精确基础设施

### WP-01A Typed Scaled Integer

模块建议：

```text
crypto_quant_domain.numeric
├── scales
├── price
├── quantity
├── money
├── rate
├── exposure
├── rounding
└── quantization
```

拥有：Price、Quantity、Money、Rate、ExposureFraction、Scale、RoundingPolicy 和 QuantizationPolicy。v1 Scale 是 `0..18` 的十进制小数位数；identity 暂以非空 canonical string 表达，WP-02A 收紧为正式领域 ID 时不得改变序列化字段。跨类型运算只开放 `Price.notional(Quantity)` 和 `Money.quantity_at(Price)`。

不拥有：Instrument rule、Position sizing 或 Accounting。

验收：

- 不同领域类型不能隐式相加；
- 不同 Currency/Instrument identity 不能隐式相加；
- Scale 提升、降低、乘除均要求显式 RoundingPolicy；
- Analytics float 只能通过版本化 QuantizationPolicy 进入权威类型；
- canonical JSON 输出 `units`、`scale`、领域 identity，不输出浮点；
- 边界 Fixture 覆盖正负值、零、向零舍入、半单位和超大整数。

### WP-01B UtcInstant 与 SimulationInstant

拥有：UtcInstant、TradingDate、SessionId、TimelinePhase、SourceSequence 和 SimulationInstant 排序。`TimelinePhase` v1 是 `rank + canonical code` 值对象，不在 Domain 中提前固化市场阶段枚举；`SimulationInstant` 使用 `(epoch_nanoseconds, phase.rank, phase.code, source_sequence)` 总顺序。

验收：

- naive datetime 输入被拒绝；
- DST 重复本地时间必须由显式解析规则消歧；
- 夜盘 TradingDate 不由 UTC date 推断；
- 相同 UtcInstant 使用 phase、source_sequence 稳定排序；
- epoch nanoseconds canonical round-trip 完全相同。

### WP-01C Deterministic identity

拥有：Semantic namespace 下 Decision、Order、Fill、Fee、Settlement、Journal 和 Reservation 领域 ID 的确定性派生算法。v1 使用 `sha256-length-prefixed-v1`：固定 magic、versioned namespace、kind、Semantic Run ID、canonical semantic key bytes 和 unsigned ordinal 均进入无歧义 length-prefixed payload；Attempt ID 不属于接口。

验收：

- 不同 Attempt 对同一 Semantic Run 产生相同领域 ID；
- 两个经济字段完全相同但 ordinal 不同的 Fill 不碰撞；
- Attempt ID 不进入领域 ID；
- algorithm/version 变化会改变 identity manifest，而不是静默改变结果。

### WP-01D Canonical serialization/hash

拥有：canonical encoder、hash envelope、schema/version metadata；不拥有具体 Run evidence。v1 使用 UTF-8、sorted-key、compact JSON，只允许 null/bool/integer/NFC string/array/string-key mapping 和显式 canonical domain object；float、Decimal、datetime、bytes、set 与未知对象 fail closed。

验收：

- Mapping 插入顺序不影响 canonical bytes；
- 禁止 NaN、Infinity、naive datetime 和 JSON float 进入权威 Artifact；
- Golden bytes/hash Fixture 固定；
- 不同 Schema version 不会产生未标识的相同 envelope。

### Gate G01

通过 exact numeric、time ordering、ID 和 canonical hash 四组黄金 Fixture。任何迁移自 `crypto-quant-core` 的行为同时生成模块级 ParityReport。此 Gate 不包含 Instrument、Order 或 Ledger。

---

## 7. G02：领域契约与 Schema

### WP-02A Instrument 与 Currency identity

拥有：InstrumentId、VenueId、CurrencyId、InstrumentDefinition、SymbolTimeline、InstrumentCatalog 和基础 Instrument type discriminator。InstrumentId 使用 Venue + stable key，Symbol 仅存在于 half-open SymbolTimeline；Catalog 拥有 Currency/Instrument 引用完整性。

验收：

- Symbol 改名不改变 InstrumentId；
- 未知 Currency/Instrument reference 被拒绝；
- InstrumentDefinition 为 immutable；
- Canonical round-trip/hash 稳定。

### WP-02B Target/Decision contracts

拥有：StrategyDecisionPayload、StrategyDecisionCandidate、Validated StrategyDecision、TargetSnapshot、TargetExposureFraction、StrategySleeveId、DecisionBatch 和 ActivePortfolioTarget 数据契约。

不拥有：校验流程、分配、风险或 sizing 行为。

验收：

- Candidate 使用 immutable decoded-data tree，可以保留重复 Instrument、未知 Instrument、非法时间和未量化值，用于结构化验证，但拒绝 DataFrame、Broker DTO、Engine reference 和其他非数据对象；
- TargetExposureFraction 使用 InstrumentId 和 signed integer units，v1 canonical scale 固定为 12；
- Validated TargetSnapshot 是完整、绝对、原子集合，允许空集合表示全部归零，不能包含重复 Instrument；
- Candidate 不是权威执行对象，不进入 canonical execution trace；
- Decision Time、Observed Through、Effective Time 使用 UtcInstant；
- 数据契约不包含 DataFrame、Broker DTO 或 Engine reference。

### WP-02C Order/Execution contracts

拥有：venue-neutral `OrderIntent`、identity-bearing `Order`、`OrderEvent`、`OrderState`、`Fill`、`FeeAssessment`、`SettlementObligation`、`OrderTranslationReport` 及其最小 canonical enum/value contracts。

不拥有：Order capability 判断、Translation 算法、Order Event replay/state transition、Market Rule、Fee 计算、Settlement 应用、Accounting mutation 或 Venue DTO。

v1 canonical semantics：

- `OrderSide = buy | sell`；
- `ExecutionStyle = market | limit | stop | stop_limit`；
- `TimeInForce = day | gtc | ioc | fok | gtx`；
- `PositionEffect = auto | open | close`；
- `PriceConstraint` 只承载 typed limit/trigger price；具体 style/constraint 组合由后续 Capability/Market Rule Gate 判断；
- `OrderIntent` 不提供 extensions/metadata 字段，Venue symbol、board、position action、client DTO 和 Adapter payload 只能出现在 Translation evidence 或 Adapter 内；
- `Order` 绑定 `DomainIdKind.ORDER`、Execution Account identity、创建时 `SimulationInstant` 和 immutable Intent；
- `OrderEvent` 具有独立 canonical event ID、typed Order ID、causation ID 和 `SimulationInstant`；Fill event 必须引用 typed Fill ID；
- `OrderState` 只是 immutable projection contract，保存 ordered/cumulative/remaining Quantity，状态转换和 replay 属于 WP-05C；
- `Fill` 使用 typed Order/Fill ID、Instrument/Venue、Quantity/Price/Money 和 UtcInstant，且不含最终 Fee；
- `FeeAssessment` 使用 `fill | order | session` typed basis，并独立引用 Fee/Tax/Account rule identity；
- `SettlementObligation` 必须恰好表达 Instrument Quantity 或 Currency Money 之一；
- `OrderTranslationReport` 明确 translated/rejected，记录 field mapping，并以 `UnsupportedCapability` 结构化表达无法精确映射的语义。

验收：

- Fill 不含唯一最终 Fee；
- FeeAssessment 可以引用一个或多个 Fill、Order 或 Session basis，basis 类型不匹配时 fail closed；
- Order Event 具有 event/order/causation identity，Fill event 缺少 Fill ID 时拒绝；
- OrderState Quantity identity、Scale 和总量不变量成立；
- Venue-specific 字段不能进入 canonical OrderIntent；
- unsupported capability 有结构化表达，rejected Translation 不得伪装为 translated；
- canonical round-trip/hash 不受 tuple 输入顺序影响的集合字段必须稳定排序。

### WP-02D Accounting contracts

拥有：`PricePurpose`、`AccountingEntryType`、`CashBalanceKey`、`PositionBalanceKey`、typed `BalanceChange`、`PositionLot`、`CashBalance`、`PositionBalance`、`ValuationMarkReference`、`AccountingJournalEntry` 和 `PortfolioSnapshot` 数据契约。

冻结语义：

- `PricePurpose` v1 固定为 `execution_reference | valuation | margin | liquidation | settlement | funding`；`Fill.reference_price_purpose` 必须升级为该 typed enum，但 canonical value 保持原字符串；
- Journal Entry 使用 `DomainIdKind.JOURNAL`、`SimulationInstant` 和非空 source identities；同一 Entry ID 的幂等 apply/replay 属于 WP-03A；
- Balance Change 只能是 `CashBalanceKey + Money` 或 `PositionBalanceKey + Quantity`，identity、account、venue 和 native currency/instrument 必须一致；
- `PositionLot` 保存 stable lot ID、Position key、source identity、signed non-zero Quantity、可选 typed unit cost、allocated native fees 和 opened time；具体 Cash CostBasisPolicy、Lot selection/consumption 和 Derivative Entry Price 算法不属于本 WP；
- `PortfolioSnapshot` 保存 native Cash/Position state，但 Realized PnL、Unrealized PnL、Fees、Financing 和 Equity 都是单一 Reporting Currency `Money`；Snapshot 引用 Journal State hash、实际 Valuation Mark identities/set hash、Staleness Report hash 和 Currency Valuation Graph hash；
- Snapshot 只是 immutable derived projection，不能进入 Journal Entry schema，也不能修改 Journal。

验收：

- Journal Entry immutable 且具有幂等 identity；
- Native Currency 保留到 Journal；
- Balance key/value、Position Lot 和 Snapshot identity 不匹配时 fail closed；
- Set-like source、balance、lot 和 mark inputs 具有顺序无关 canonical hash；
- PortfolioSnapshot 明确 realized/unrealized PnL 和 valuation mark identity；
- Future valuation mark、错误 Reporting Currency 和不一致 mark-set hash 被拒绝；
- Snapshot 不能作为修改历史 Journal 的输入。

不拥有：Journal store/replay、Ledger projection、Accounting translation、CostBasisPolicy、Lot consumption、Mark resolution、Currency valuation、Snapshot calculation、Margin Snapshot 或任何 mutable state。

### WP-02E Artifact Envelope and Schema Catalog v1

拥有：ArtifactEnvelope、artifact type/schema version catalog、当前版本 writer、canonical reader dispatch 和 source bytes/hash preservation。

不拥有：没有真实 source/target artifact 的通用 Migration Chain。

验收：

- Envelope 明确记录 artifact type、schema version、canonical payload 和 content hash；
- Writer 只写当前版本；
- Reader 对已注册当前版本稳定 dispatch；
- 未知 Artifact type 或 Schema version fail closed；
- 原始 bytes/hash 可以独立验证；
- 不为测试框架发明虚构 v0→v1 Migration。

### WP-02F Kernel Profile Ports

所属 package：`trading-kernel`。

拥有：SessionModel、InstrumentModel、OrderRuleModel、FeeAssessmentPolicy、TaxPolicy、SettlementModel、PositionAccountingModel、FinancingModel、MarginModel、LiquidationRules、CorporateActionModel 和 CurrencyValuationPolicy Interface。

不拥有：具体 A 股/Binance 实现、Profile Registry、Backtest Simulation 假设。

v1 Port seam 使用三参数 generic Protocol：`RequestT`、`ResultT` 和 `FailureT`。三者都必须实现 immutable canonical `ProfilePortContract`，并由具体规则 WP 使用 Trading Domain 类型组成；禁止 `Any`、裸 `object` payload、任意 metadata/extensions 或 Vendor DTO 作为语义逃生口。每次调用返回 exactly-one-of result/failure 的 `ProfilePortOutcome`，同时记录 `ProfileComponentRef` 和 canonical input hash。共享稳定 reason code 延后由 WP-02H 统一，WP-02F 不提前发明错误 taxonomy。

验收：

- Generic Kernel 只依赖 Ports，不导入具体市场 Profile；
- Ports 使用 Trading Domain 类型，不暴露 DataFrame、Vendor DTO 或 Runtime State；
- 每个 Interface 使用独立语义方法名并声明 typed Request、Result、Failure 和确定性要求；
- `ProfileComponentRef` 固定 component key、正版本、Port type 和 `sha256:` digest；
- `ProfilePortOutcome` 拒绝 result/failure 同时存在或同时缺失，并保存 canonical input hash；
- Test Adapter 可独立验证调用方，不成为生产默认实现；
- 本 WP 不实现具体规则请求/结果、共享 reason code、Profile composition/registry/resolution、no-op component 或任何市场/模拟行为。

### WP-02G Simulation Profile Ports

所属 package：`backtest-runtime`。

拥有：ExecutionModel、SlippageModel、LatencyModel、LiquidityModel、LiquidationAuditModel 和 CloseoutPolicy Interface。

不拥有：真实市场规则、Fee、Accounting、Settlement 或 Live 行为。

验收：

- Simulation Port 与 Market Semantics Port 类型上分离，使用独立 `SimulationPortType`、`SimulationComponentRef`、`SimulationPortSpec` 和 `SimulationPortOutcome`；
- 六个模型均为 `runtime_checkable` generic Protocol，并分别使用 `simulate_execution()`、`decide_slippage()`、`resolve_latency()`、`evaluate_liquidity()`、`audit_liquidation()` 和 `resolve_closeout()`；
- 每个模型必须通过 `SimulationPortSpec` 暴露 versioned component identity、显式 `SimulationCapabilityRequirement` 集合和 typed canonical applicability contract；空 capability 集合必须显式存在，不能通过缺失属性表示；
- 每次调用返回保存 canonical input hash 的 exactly-one result/failure outcome；不得返回裸值、`None`、日志文本或抛出预期业务失败；
- Live Runtime 不需要安装或导入这些 Ports；`trading-domain`、`trading-kernel` 和未来 Live composition 不能反向依赖 `backtest-runtime`；
- 未配置模型不能使用隐式零值、零滑点、无限流动性、零延迟、自动 closeout 或 no-op 降级；
- 本 WP 不实现 CalibrationEvidence 内容、具体 Applicability 条件、RandomStream、Profile composition/registry/resolver、next-open execution 或任何 concrete/synthetic model。

### WP-02H Profile Component Error Taxonomy

拥有：`ProfileComponentFailureCode` 和 `ProfileComponentFailure`，覆盖 Profile lookup、component incompatibility、capability missing、applicability violation 和 unsupported semantics 的稳定 reason code。

v1 canonical reason code 固定为：

- `profile_lookup_failed`；
- `component_incompatible`；
- `capability_missing`；
- `applicability_violation`；
- `unsupported_semantics`。

`ProfileComponentFailure` 只保存 typed reason code 和 non-empty NFC `subject_key`。Subject 标识失败主体，不承载日志、异常文本、任意 metadata 或 Vendor DTO。

不拥有：Run Outcome 映射、Resolver/Registry、compatibility/capability/applicability 算法、具体 Profile 行为、异常层或日志呈现。

验收：

- Kernel、Runtime 和 Resolver 可以共享结构化 reason code，不依赖日志文本判断；
- 新错误不能通过 `None`、通用 `ValueError`、exception text 或 log matching 静默表达；
- Reason code 与 failure value 的 canonical serialization 稳定；
- Error taxonomy 不引用具体市场或供应商 DTO；
- 新增或重定义 reason code 必须通过显式 schema/version 变更。

### Gate G02

所有核心对象可 canonical round-trip；Kernel/Simulation Profile Ports 和结构化错误契约已建立；Domain package 仍不依赖 Runtime、Pandas、Hummingbot 或市场 Profile。Generic Kernel 不导入具体市场 Profile。

---

## 8. G03：Journal/Ledger 最小财务内核

### WP-03A Immutable Journal store/replay

拥有：Journal append validation、稳定顺序、幂等 apply、hash-chain identity 和 replay cursor。

冻结语义：

- `AccountingJournal` 是 immutable append-only value；append 返回新 Journal，不修改旧实例，也不拥有外部持久化；
- entry 顺序固定为 `recorded_at` 后接 `journal_entry_id.value`。单次 batch 先按该 key 排序；已发布 cursor 之后禁止插入更早 entry；
- 相同 Entry ID 与相同 canonical content 是幂等 no-op；相同 ID 与不同 canonical content 是冲突；
- `JournalReplayCursor` 由已消费 entry 数量和该 prefix 的 hash-chain identity 组成。Cursor 必须同时匹配 position 和 prefix hash，不能只按整数 offset 信任；
- replay 使用半开区间 `[start_cursor, stop_cursor)`，返回 immutable entry slice 和经验证的 start/end cursor；
- 空 Journal 有固定 genesis hash；每个后续 prefix hash 只由前一 prefix hash 和当前 entry canonical hash 推导；
- 本 WP 可以用无经济语义的测试 reducer 证明任意 cursor replay parity，但不实现 Ledger State projection。

验收：

- 相同 Entry ID 与相同内容重复应用不改变 Journal identity；
- 相同 Entry ID 与不同内容导致结构化冲突；
- reverse/batch 输入产生相同稳定 Journal 顺序和 hash；
- replay 到任意稳定位置并继续 replay 产生与从 genesis replay 相同的 entry sequence/reducer state；
- 篡改 position/prefix hash、反向 range 或已发布 cursor 前的 late insert fail closed；
- Journal 顺序不依赖 Mapping/set 遍历。

不拥有：Generic Ledger economic projection、Accounting translation、Market/Profile 读取、Mark resolution、Valuation、Settlement mutation、mutable external persistence 或 EngineCheckpoint。

### WP-03B Generic Ledger projection

拥有：Cash、Position、Realized PnL、Fee 和 Financing 的 immutable `LedgerState` 投影；不包含市场类型 `if/elif`，不读取 MarketSemanticsProfile、ExecutionAccountProfile 或 Risk Policy。

冻结语义：

- `LedgerSchema` 显式注册每个 `CashBalanceKey` / `PositionBalanceKey` 及其唯一 `Scale`；注册顺序不影响 schema hash；
- v1 的 Debit/Credit 等价财务不变量定义为 closed registered dimensions：每个 BalanceChange 和 attribution 必须落在已注册的 account/venue/currency/instrument key，且 identity 与 Scale 精确匹配；Ledger 禁止隐式 rescale、跨 key 抵消或未知维度创建。跨资产经济配平证明由产生 Entry 的 PositionAccountingModel 在 WP-03F 负责；
- `GenericLedger.project()` 只消费经 `AccountingJournal.replay()` 验证的 prefix；`resume()` 同时验证 schema hash、cursor/prefix hash 和已有 state 的 genesis replay parity，不能信任伪造 checkpoint；
- Cash key 始终保留显式零余额；零 Position 从 state 中移除，非零 Position 使用 `PositionBalance(lots=())`，Lot/cost-basis projection 留给 WP-03F；
- Realized PnL、Fee 和 Financing 按注册 Cash key 的原生币种与 Scale 独立累计；未实现 PnL 不进入 Ledger State；
- State canonical identity 包含 schema hash、Journal cursor、Cash/Position 和三类 attribution，Mapping/注册/Entry 输入顺序不能影响 state hash；
- 对同一 Journal prefix 重复 project/resume 是幂等 no-op；负现金、Short Position 和已发生风险暴露是合法 truthful state。

验收：

- 初始资本、买入、费用、卖出、实现损益可通过 Journal replay 重建；
- Ledger 不读取市场价格计算未实现损益；
- genesis→end 与 genesis→cursor→resume 产生 exact 相同 State hash；
- 未注册 Account/Balance Key、Scale/identity 不匹配、伪造 cursor 或伪造 resume state 明确失败；
- 负现金、Short Position 或 Margin breach 不由 Ledger 拒绝，已发生 Fill 必须如实入账；
- 经济权限违规、具体 Fill-to-Journal 配平、Lot 和 CostBasisPolicy 不在本 WP 实现。

### WP-03C MarkResolver

拥有：根据 PricePurpose、UtcInstant、Price Stream 和 StaleMarkPolicy 解析唯一合法 Resolved Mark。

不拥有：币种换算、Snapshot 计算、Execution Price fallback 或数据源查询。

验收：

- Execution、Valuation、Margin、Liquidation 和 Settlement PricePurpose 不可隐式互换；
- 缺失、歧义或超过 max-age 的 Mark 返回结构化失败；
- forward-filled execution price 不能成为 Valuation fallback，除非显式 Policy 允许对应用途；
- Resolved Mark 记录 source event/revision identity 和 UtcInstant。

### WP-03D CurrencyValuationGraph

拥有：从调用方提供的 immutable、ResolvedMark-backed 有向 Edge 中解析 Native Currency → Reporting Currency 的唯一 point-in-time 路径及 provenance evidence。

不拥有：Ledger mutation、Mark 选择、Money 换算/舍入、市场特定 Graph 构建或隐式 Stablecoin peg。

验收：

- 每条有向 Edge 引用完整 Resolved Mark 和 PricePurpose，不从 Instrument symbol 猜测 Currency relation，也不自动生成 inverse Edge；
- Graph 中所有 Edge 属于同一 UtcInstant 和 PricePurpose，Edge 输入顺序不影响 graph/path identity；
- 唯一路径直接解析；多路径只能由显式版本化 CurrencyValuationPolicy 的 typed outcome 唯一选择；
- 缺失路径、未提供 Policy 的非唯一路径、Policy failure 或未知 path selection 均 fail closed；
- Stablecoin 只有未来 Profile 显式提供版本化、Mark-backed Edge 时才能按 1:1，本 WP 不发明 Peg；
- Synthetic 单币种 Fixture 也返回显式 zero-edge Reporting Currency identity path。

### WP-03E PortfolioSnapshotProjector

拥有：Ledger State + Resolved Marks + supplied Reporting Currency Valuations → PortfolioSnapshot 的纯确定性投影。

冻结语义：

- `PortfolioValueRef` 用 typed Cash/Position balance key 区分 Cash、Position market value、Realized PnL、Unrealized PnL、Fee 和 Financing；每个 ledger fact 必须有且仅有一个对应 valuation，禁止按金额或容器顺序猜测来源；
- `ReportingCurrencyValuation` 保存 native `Money`、reporting-currency `Money`、`CurrencyValuationResolution`、Graph hash 和稳定 source identity。Projector 验证币种、时点、PricePurpose、path source/target 和统一 graph identity，但不重新选择路径或发明汇率；
- Position market value 必须由对应 `ResolvedMark`、Ledger Quantity 和显式 `QuantizationPolicy` 精确重算。Unrealized PnL 作为 supplied native valuation fact 输入；Lot/Cost Basis 计算属于 WP-03F；
- supplied Marks 必须精确覆盖 Position marks 和所有 CurrencyValuationPath edge marks；future、额外或缺失 Mark 均失败关闭。Snapshot 记录每个 Mark identity，并从 mark age/policy evidence 生成稳定 staleness report hash；
- v1 只允许一个 account、一个 reporting currency 和一个 reporting `Scale`。Equity 由 converted Cash + converted Position market value 得到；Realized/Unrealized/Fee/Financing 分别汇总，Fee 和 Financing 的符号按 Journal truth 原样保留；
- 同一 Ledger state、Marks 和 Valuations 的输入顺序不影响 Snapshot canonical identity；删除 Snapshot 后可以从相同 immutable inputs exact 重建。

不拥有：数据读取、MarkResolver、换算路径/Policy 调用、Currency conversion 发明、Journal/Ledger mutation、Lot/Cost Basis 计算、Margin Snapshot、instrument-specific accounting 或 Run Outcome mapping。

验收：

- realized 与 unrealized PnL 分离，且 reporting currency/scale 精确一致；
- Mark identity、PricePurpose、UtcInstant、staleness 和 Currency Graph identity 被记录；
- Equity、Cash 和 Position market value 使用同一 Reporting Currency valuation context；Margin exposure 留给独立 Margin Snapshot；
- 缺失/重复/额外 valuation、Mark mismatch、graph/path/time/purpose mismatch、Position notional mismatch 或多 account 均返回结构化失败；
- Snapshot 可删除并由 Journal-derived Ledger State、Marks 和 supplied Valuations exact 重建。

### WP-03F Cash Instrument Accounting model（最小）

拥有：Cash Instrument Fill 到 Journal Entry 的纯翻译、独立 FeeAssessment 到 FeeCharged Journal Entry 的纯翻译，以及显式版本化 FIFO CostBasisPolicy/Lot selector。

冻结语义：

- `CashInstrumentAccounting` 只消费调用方提供的 immutable Fill、FeeAssessment、typed balance keys、当前 PositionLot、显式 QuantizationPolicy、CostBasisPolicy、Journal ID 和 recorded SimulationInstant；它不读取 Profile、Market、Journal、Ledger 或外部状态；
- v1 CostBasisMethod 只实现显式 `fifo`，没有隐式默认。Policy 缺失返回结构化 block；FIFO 顺序固定为 `opened_at` 后接 `lot_id`；
- Buy 产生负 quote Cash、正 Position 和一个以 source Fill 为 provenance 的 immutable acquisition Lot；Sell 产生正 quote Cash、负 Position，按 FIFO 消耗现有 Long Lot，并记录每个 consumed Lot/source Fill；
- Sell 数量超过可用 Long Lot 是非法反向路径并 fail closed；Cash accounting v1 不通过负 Lot 偷渡 Short；
- Gross realized PnL 只等于 Sell proceeds 减被消耗 Lot 的 price cost basis。Fee 不嵌入 Fill，也不重复折入 gross realized PnL；FeeCharged 通过 Cash 变化和独立 `fees` attribution 只计一次，`net_pnl = gross_realized_pnl - fees + financing`；
- Fill-based Buy Fee 可以明确分配到对应 acquisition Lot 的 `allocated_fees` provenance；后续 partial/full Lot consumption 按 Policy rounding 精确拆分并保持总额守恒，但该分配不改变 Journal 中独立 Fee attribution；
- FeeCharged Entry 引用 FeeAssessment ID、basis ID 和全部非空 rule identity。v1 只资格化单一 Fill basis 的非零同币种费用；Order/Session 聚合费用留给 WP-05J；
- Journal Entry 和 Lot Result 均为 immutable output；本组件不能直接修改 Journal、Ledger 或 Lot store。

验收：

- 买入、加仓、部分卖出、全部卖出和反向非法路径有 Fixture；
- FeeAssessment 独立入账并正确影响 Cash、Fee attribution、Lot fee provenance 和 net PnL，且不双计；
- Lot consumption 可追踪到 source Fill，输入 Lot 顺序不改变 FIFO result/canonical identity；
- 未声明 CostBasisPolicy、key/scale/identity 不匹配、unsupported fee basis 或 Buy Fee 找不到 acquisition Lot 时结构化阻断；
- 固定 crypto-quant-core `accounting.py` source snapshot 通过 Comparator Contract 证明 closed-trade gross/fee/funding/net exact parity。

不拥有：Derivative accounting、Market/Profile 读取、Settlement mutation、Tax/Funding/Corporate Action、mutable Lot store、Runtime orchestration、implicit Policy/default 或 Order/Session aggregate fee allocation。

### Gate G03

Cash/Accounting 迁移必须在本 Gate 立即对固定来源 Fixture 生成模块级 ParityReport，不等待 G10/G12。

黄金财务 Fixture：Deposit → Buy → Fee → Mark Resolution → Currency Valuation → Partial Sell → Fee → Final Snapshot。删除 Snapshot 后必须通过 Journal、Resolved Marks 和 CurrencyValuationGraph 得到 exact 相同结果。

Gate 冻结验收：

- 只组合 WP-03A–WP-03F 已通过的公开接口，不新增旁路财务状态或测试专用生产 API；
- Journal replay 的最终 Cash、Position、gross realized PnL 和 Fee attribution 与 CashInstrumentAccounting outputs 一致；
- MarkResolver 只消费 supplied Valuation observation，CurrencyValuationGraph 使用显式 Reporting Currency identity path；
- PortfolioSnapshot Equity 等于 converted Cash + Position market value；gross realized、unrealized 和 fees 分离，Fixture 的 net economics 只减一次 Fee；
- 删除 Snapshot 后，以同一 Journal-derived LedgerState、ResolvedMark、Valuation path evidence 和 supplied valuations exact 重建相同 canonical Snapshot/hash；
- `core-accounting` ParityReport 必须为 `MATCH`，且 Aggregate Gate 同时重跑 WP-03A–WP-03F fixtures、import boundary、mypy 和完整 test suite。

---

## 9. G04：Target 校验、批次和组合物化

### WP-04A StrategyOutputValidator

拥有：从 StrategyDecisionCandidate 到 `ValidationResult[StrategyDecision, ValidationFailure]` 的 Schema、Instrument、Universe、时间因果性、唯一性和 Quantization 边界校验。

不拥有：输入来源判断、Run Outcome 映射、DecisionBatch 部分降级、Portfolio Risk。

验收：

- Validator 对相同 Candidate 产生相同 Validated Decision 或 ValidationFailure；
- Validator 不接收 InputOrigin，也不返回 FAILED/BLOCKED；
- 未知/未上市 Instrument、未来 observed-through、重复 Target 和无法量化均产生结构化 Failure，不被静默删除；
- 只有 Validated StrategyDecision 可以进入 DecisionBatch；
- 正常经济风险超限不在此模块处理。

v1 Candidate Schema 固定为：

- 顶层字段：`schema_version/strategy_id/sleeve_id/decision_time/observed_through/effective_time/expires_at/targets/confidence/reason/evidence`，缺失或未知字段 fail closed；
- Target 字段：`instrument_id: {venue, stable_key}` 与 `value`；value 仅接受 integer、`Decimal` 或 canonical decimal string，exact 转为 scale-12 units；
- bool/float、NaN/Infinity、超过 12 位且不能 exact 量化的数值禁止隐式 rounding；
- Validator 接收可信 `StrategyOutputValidationContext`：expected Strategy/Sleeve、authoritative Decision Time、InstrumentCatalog 和该时点已解析 Universe；它不读取 InputOrigin、不推断 Universe；
- ValidationFailure 保存稳定 Candidate payload evidence hash 和规范排序 Issue；Candidate/Failure 均不进入 canonical execution trace。

### WP-04B Atomic DecisionBatch

拥有：同一 Decision Instant 的 Validated StrategyDecision 原子收集、稳定 batch identity，以及跨不同 Decision Instant 的 latest-per-Sleeve Decision State 更新。

冻结边界：

- Caller 先提供规范化的 expected `(strategy_id, sleeve_id)` 集合，再一次性提交已经独立完成的 `StrategyValidationResult`；Collector 不接收 Strategy callback、Context 或逐个可见的 staged Batch；
- 每个 expected Sleeve 必须有且只有一个 Submission；missing、duplicate、unexpected、ValidationFailure、Strategy/Sleeve identity mismatch 或 Decision Time mismatch 均返回规范化 Failure，且 `batch=None/state=None`；
- `decision_batch_id` 由 versioned canonical identity payload（Decision Instant + canonical-sorted Validated Decisions）确定性派生，不使用注册顺序、Mapping 顺序、Attempt ID 或 wall-clock time；
- `LatestSleeveDecisionState` 只保存每个 Sleeve 最近一次 Validated Decision。新 Batch 原子替换本 Batch 中的 Sleeve，并保留不同 Instant 未调度 Sleeve 的最近 Decision；Target expiry/stale policy 不在 Collector 内解释；
- 同一 Instant 不允许通过多次 Collector 调用拼接部分 Batch；已有非空 State 的 `as_of` 必须早于新 Batch Decision Instant。

验收：

- Strategy 注册顺序和 Submission 顺序变化不改变 batch ID、batch hash 或 latest-Sleeve state hash；
- Candidate validation 有任一 Failure，或 expected/submission completeness 不成立时，不产生部分 Batch 或部分 State；
- Collector API 只消费已完成 Result，Strategy 互相看不到同 Batch 输出；
- 不同 Instant 原子更新被调度 Sleeve，并保留其他 Sleeve 最近 Validated Decision；
- 不实现 Allocation、Netting、Risk、Sizing、Order Planning、Strategy invocation、InputOrigin 或 Run Outcome mapping。

### WP-04C Capital allocation 与 Sleeve netting

拥有：显式版本化 Allocation Policy evidence、每个 Strategy Sleeve 的 supplied Allocation NAV、精确 Target Notional 转换和账户级净额化。

冻结边界：

- Allocator 只消费 `LatestSleeveDecisionState`、同一 valuation instant 的权威 `PortfolioSnapshot`、显式 `CapitalAllocationPolicyRef`、每个 active Sleeve 恰好一个 `StrategyAllocation` 和显式 target-notional Scale；它不调用 Policy callback，也不发明默认 Allocation；
- `StrategyAllocation` 必须绑定 Strategy/Sleeve、valuation time/currency、source Snapshot hash 和非负 Allocation NAV；总 Allocation NAV 不能超过 Snapshot Equity，违反约束返回结构化 Decision 且不产生部分结果；
- Target Exposure Fraction 到 native Target Notional 使用整数精确换算到调用方声明的 Scale；需要 rounding 的输入 fail closed，rounding 只允许在 WP-04E Position Sizing 的显式边界发生；
- 每个 Instrument 保留完整 Sleeve attribution，并在账户级求和；完全相反的 Sleeve target 产生显式零净目标而不丢失 attribution；
- 输入、Mapping、Strategy 注册和 Allocation tuple 顺序不影响 allocation identity、net target 或 evidence hash；
- 不实现 Price/Quantity conversion、Portfolio Risk、ActivePortfolioTarget、Order、Ledger mutation、Strategy invocation 或 allocation policy execution。

验收：

- 两个 Sleeve 对同一 Instrument 的相反目标在下单前净额化；
- Sleeve attribution 不改变账户权益；
- Allocation 总量不满足约束时有显式 Decision；
- Mapping/注册顺序不影响净目标。

### WP-04D Portfolio Risk

拥有：Target-level approve、clamp、reject；不拥有 Order 修改。

冻结边界：

- `PortfolioRiskEvaluator` 只消费 immutable `PortfolioAllocation` 和显式 `PortfolioRiskPolicy`；Policy 绑定版本化 identity/config hash、valuation Currency/Scale、每个 Instrument 恰好一个 target absolute-notional limit，以及显式 gross/absolute-net aggregate limits；没有默认 Policy、回调或未覆盖 Instrument；
- Target limit 对超限结果显式选择 `clamp` 或 `reject`：clamp 只向零截断到 limit，reject 物化为显式零 approved target；未超限产生 approve Decision；
- v1 aggregate gross/absolute-net limit 只允许 approve 或 reject whole target set，不实现会隐式分配 Instrument 优先级或 rounding 的 proportional clamp；aggregate reject 将全部最终 approved targets 显式置零；
- 每个 Decision 记录 scope、action、before、after、limit、reason、Policy identity；`ApprovedPortfolioTarget` 保存原 `NetInstrumentTarget`（含 Sleeve attribution）及最终 approved notional；
- `gross_exposure = Σ abs(approved target)`，`net_exposure = Σ approved target`，均使用 Allocation valuation Currency/Scale；输入与 Policy rule 顺序不影响 identity/hash；
- Policy coverage/context/identity/scale 错误是 Contract Failure；合法经济 target 的 clamp/reject 是成功的 Risk Assessment，不映射为 Candidate ValidationFailure 或 Run Outcome；
- 不实现 Price/Quantity sizing、Margin requirement、Market/Profile read、ActivePortfolioTarget、Order、Pre-trade Risk、Ledger mutation 或 Runtime orchestration。

验收：

- 每次 clamp 记录 before/after/reason/policy identity；
- Risk 不能产生 Venue Order；
- Risk reject 不等同于 Contract violation；
- gross/net limit 的经济拒绝可重建且 input/rule 顺序无关；
- 未声明或 coverage 不完整的 Policy 不使用隐式默认值。

### WP-04E Position sizing 与 ActivePortfolioTarget

拥有：approved Notional + supplied Decision-Instant Mark → versioned `QuantityLattice` → exact Quantity → `ActivePortfolioTarget`。

冻结边界：

- `PositionSizer` 只消费 immutable `ApprovedPortfolioTarget`、权威 `source_decision_batch_id`、显式 `PositionSizingPolicy`，以及每个 approved Instrument 恰好一个 supplied `InstrumentSizingInput`；它不调用 MarkResolver、Profile、Reader 或 Policy callback，也不提供默认 Policy/Lattice；
- `InstrumentSizingInput` 绑定 Instrument、同一 `approved_at` 的 supplied `ResolvedMark`、当前 exact Quantity 和版本化 `QuantityLattice`。Mark 必须为正，PricePurpose 必须等于 Policy 声明的 sizing purpose，Price quote Currency 必须等于 approved Notional Currency；跨币种换算不能隐式发生；
- v1 `PositionSizingPolicy.rounding` 只允许 `toward_zero`。Notional/Price 使用整数除法直接量化到 Lattice atomic Scale，再按 signed target 对应的 buy/sell lot（缺省时为 step）向零量化；普通量化禁止物化后绝对名义暴露超过 approved Notional。唯一例外是显式 `hold_dust` 保留无法合法关闭的既有 odd-lot Position，且 before/after/residual 必须完整记录；
- `QuantityLattice` 显式记录 key/version/config hash、atomic Scale、step、buy/sell lot、minimum Quantity、minimum Notional 和 odd-lot full-close capability；所有 lot/minimum 必须与 Instrument/Scale/Currency 一致，且不存在隐式当前规则 fallback；
- 量化差异、minimum Quantity、minimum Notional、toward-zero、odd-lot full-close 和 residual action 均形成 canonical `PositionSizingDecision`。`ResidualPositionPolicy` 必须显式选择 `hold_dust`、`close_if_permitted` 或 `fail`；无法按声明规则形成完整账户级目标时原子失败，不返回部分 Active Target；
- `NormalizedPortfolioTarget` 保留 source Batch、Approved Target/Policy、Mark、Lattice、当前 Quantity、raw/final Quantity 和 residual provenance；`ActivePortfolioTarget` 只保存已物化的 exact Quantity，后续 Price/NAV/Cash Flow 变化不能重新解释旧对象；
- input/Lattice 顺序不影响 normalized/active identity。Order Planner 只消费 exact Active Quantity，不得执行第二次数量舍入；
- 本 WP 不读取市场数据/Profile，不执行 Risk、Order Planning、Ledger mutation、contract-multiplier sizing、跨币种转换或 Runtime orchestration。

验收：

- 使用 Decision Instant 的 Allocation NAV/approved Notional 和 supplied Price；
- Price/NAV 后续变化不重算旧 Active Target；
- toward-zero、buy/sell lot、minimum Quantity/Notional、odd-lot close 和 residual 结果有明确 Decision；
- 缺少/重复/额外 Sizing Input、context mismatch、隐式 Policy 或 residual=`fail` 均不产生部分 Active Target；
- Order Planner 不执行第二次数量舍入。

### Gate G04

输入两个 Sleeve 的 TargetSnapshot，稳定地产生一个 Account-level ActivePortfolioTarget；改变 Strategy 注册顺序、Mapping 顺序或后续 Mark 不得改变已物化 Quantity。

---

## 10. G05：订单、预留、结算和再平衡

### WP-05A Order Event Stream/State projection

拥有：Order immutable event stream、合法状态机和 cancel-replace。

验收：

- Created→Submitted→Accepted→Filled/Cancelled/Expired/Rejected 转换合法；
- 非法终态回退被拒绝；
- Event replay 重建相同 OrderState；
- 不支持隐式原地修改。

### WP-05B ResourceReservationBook

拥有：Working Order 的 Cash、Sellable Quantity、Margin、Fee Reserve、Order Capacity 和 Exposure Capacity 承诺投影。

本 WP 的 Book 不计算 Reservation。调用方必须提供与 Order Event 对齐的 immutable `OrderReservationSchedule`：一个明确的 Accepted/Activated activation update，以及每个 Partial Fill 后的 exact remaining commitment。不同资源类别不做隐式比例缩放、币种转换或相互净额化。

验收：

- 显式 Accepted/Activated activation update 增加预留但不会重复冻结；
- 每个 Partial Fill 必须提供与 exact remaining Quantity 对齐、各资源维度不增加的 replacement commitment；
- Cancel/expire/reject/fill 终态释放该 Order 的全部预留，零泄漏；
- Book 保留逐 Order commitment 和 account-level typed totals，输入/Stream/Schedule 顺序不改变 state hash；
- 重复 identical Event replay 幂等；冲突 Event 继续由 OrderEventStream fail closed；
- prefix resume 必须先重建并验证 prior state，再得到与 full replay exact 相同的最终 state hash；
- Reservation 不是 Journal、Settlement 或 Availability，也不读取 Profile，不自行计算 commitment。

### WP-05C SettlementBook/AvailabilityProjection

拥有：Settlement Obligation 生命周期和 total/sellable/tradable/withdrawable 投影。

验收：

- Fill 后经济 Position 立即反映；
- 未结算 Position/Cash 的可用性按规则限制；
- SettlementApplied 幂等；
- Settlement 与 Reservation 不混用；
- Pre-trade check 消费 Available Resources，不只看总余额。

### WP-05D RebalanceCoordinator

拥有：`NormalizedPortfolioTarget`、显式 `TargetValidity`、当前 `PortfolioSnapshot`、非终态 `OrderEventStream`、`ResourceReservationState`、`AvailabilityState` 和版本化 `RebalancePolicy` → immutable `OrderPlan` / `CancelIntent` / `PlanningOmission`。

冻结语义：

- Coordinator 只消费 supplied immutable state；Reservation/Availability 仅用于 account/context evidence，不在本 WP 重新计算资源或执行 Pre-trade Risk；
- Working Order coverage 使用其 exact remaining Quantity 和 side。相同 evidence + 尚有效 prior Plan 返回同一 Plan；已有 Working coverage 不重复规划；
- 对每个 Instrument 计算 `target - current - retained working coverage`。Partial Fill 后 remaining working Quantity 继续覆盖目标；终态 Order 不得作为 Working Order 输入；
- 新 Target 下，方向相反或会超过当前阶段目标的 Working Order 是 conflict。Coordinator 先生成 CancelIntent；该 Instrument 在取消完成前不得同时生成 replacement PlannedOrder；
- 当前 Position 与 Target 异号时，当前阶段只允许精确减仓到零。Opening opposite exposure 必须等待 close Fill 已反映到新的 PortfolioSnapshot 后重新规划；
- `TargetValidity`、`OrderPlan.valid_until` 和 Planned `OrderIntent.time_in_force` 分别保存并独立校验；Order expiry/Plan supersession 不删除仍有效 Target；
- Plan 必须绑定 Target hash、PortfolioSnapshot hash、Working Order set hash、Reservation State hash、Availability State hash、Policy hash 和创建时点；任一前提变化使 prior Plan superseded；
- 所有 Instrument、Working Order 和 input 顺序变化不得改变 Plan/Decision identity。Order Planner 只使用已物化 exact Quantity，不再次舍入。

验收：

- 重复 tick 不重复规划已被 prior Plan 或 Working Order 覆盖的数量；
- Partial Fill 后只保留/规划 exact remaining delta；
- 新目标替换时先取消冲突订单，取消完成前没有 replacement；
- close-before-open 对 Long→Short 和 Short→Long 生效；
- target validity、plan supersession 和 venue TIF 独立；
- account/time/hash/quantity Scale、duplicate/terminal Working Order 或 prior Plan context mismatch 结构化失败。

不拥有：Capability/Translation/MarketRule/Fee Reservation/Pre-trade Risk、Execution Simulation、Fee/Accounting、Ledger/Reservation/Settlement mutation、Profile/Market data 读取或 Runtime orchestration。

### WP-05E OrderCapabilityValidator

拥有：Canonical `OrderIntent` 与显式版本化 `OrderCapabilitySet` 的兼容性判断。

冻结语义：

- Capability Set 使用 key/version/config hash，并按每个 `ExecutionStyle` 显式声明允许的 `PriceConstraintShape` 与 `TimeInForce`；不能使用跨 Style 全局并集猜测组合支持性；
- Capability Set 必须显式声明 execution style、price constraint、TIF、reduce-only 和 position effect 五个 capability key。缺失或未知 key 均 fail closed；
- `None`、limit-only、trigger-only、limit+trigger 是不同 Price Constraint shape；Validator 只判断 exact 支持性；
- Approval/Rejection 保存未修改的 source Intent、Capability Set、各自 canonical hash 和稳定 Decision ID；set-like 输入顺序不影响 identity；
- 所有不兼容维度汇总为 canonical-sorted `UnsupportedCapability` evidence，不返回部分 Approval。

不拥有：订单翻译、ExecutableOrderSpec、市场规则、费用预留、账户风险、Price/Quantity rounding、Profile resolution、Venue DTO、订单修改、提交或 Runtime orchestration。

验收：

- unsupported execution style、style-specific price constraint、style-specific TIF、reduce-only 或 position effect 产生结构化 `CapabilityRejection`；
- Validator 不修改 Intent；
- 相同 Intent/CapabilitySet 产生相同 Decision；
- 禁止 missing/unknown capability 隐式降级。

### WP-05F OrderTranslator

拥有：Canonical OrderIntent → ExecutableOrderSpec 和 OrderTranslationReport。

不拥有：MarketRule、PreTradeRisk、Venue execution 或 Accounting。

验收：

- 每个 canonical 字段具有明确映射或拒绝原因；
- 禁止 Market→Limit、Post-only/TIF/reduce-only 等静默降级；
- ExecutableOrderSpec 不是 Hummingbot 或券商 DTO；
- TranslationReport 可通过 source Intent 和 Profile identity 重建。

### WP-05G MarketRuleEvaluator

拥有：从 supplied immutable `OrderRuleTimeline` 在 Evaluation Instant 唯一解析时点有效 `OrderRuleInterval`，并对未修改的 `ExecutableOrderSpec` 执行 tick、step/side-specific lot、min quantity/notional、price limit、Session、permission 和显式 supplemental `OrderRuleModel` decision 检查。

冻结语义：

- Timeline 使用 key/version/config hash；Interval 使用半开有效区间并保存 Snapshot/Interval identity。输入顺序不改变 Timeline 或 Decision identity；
- Snapshot 绑定 `ORDER_RULE_MODEL` Component、Instrument、Session、`QuantityLattice`、Price Scale/Tick、可选 Price Limits、Side/PositionEffect/reduce-only permission 和 supplemental decisions；Generic Evaluator 不包含具体市场分支；
- Evaluation Instant 早于 Translation Time、缺失 Interval、重叠 Interval 或 evidence/context mismatch 产生结构化 `MarketRuleDataIntegrityFailure`；禁止回退当前规则；
- Evaluator 只验证，不执行 Price/Quantity rounding 或 Order mutation；
- Minimum Notional 使用显式 `OrderRuleNotionalEvidence`，其 basis 必须是 exact Intent limit/trigger Price 或带 source hash 的 supplied reference Price；Notional rounding 由 Snapshot 显式声明；
- 合法但不满足规则的订单产生 canonical-sorted `MarketRuleRejection`，Data Integrity 与 Market Rule rejection 保持不同分类。

不拥有：具体 A 股/Binance/Vendor rule Adapter、Profile Resolver、Portfolio Risk、账户资源判断、Fee Reservation、Submission、Fill、Fee/Accounting、数据读取或 Runtime orchestration。

验收：

- 只产生 `MarketRuleApproval`、结构化 `MarketRuleRejection` 或 `MarketRuleDataIntegrityFailure`；
- Rule Timeline identity、effective interval、Snapshot/Component identity 和 Notional evidence 进入 Decision；
- 缺失/重叠规则产生 DataIntegrityFailure，不使用当前规则回退；
- tick/step/minimum/price-limit/Session/permission/supplemental rejection 完整分类且不修改订单；
- A 股/Binance 具体规则通过后续 Profile Adapter 提供，不写入 Generic Evaluator 分支。

### WP-05H FeeReservationEstimator

拥有：下单前基于已通过 `MarketRuleApproval` 的 Order 和显式 immutable 市场/税费/账户规则，计算最坏 `FeeReservationEstimate` 与仅包含 Fee reserve 的 `ResourceReservationProposal`。

冻结语义：

- Rule Set 显式绑定 `FEE_ASSESSMENT_POLICY`、`TAX_POLICY` 和版本化 `AccountFeeScheduleRef`；Market Fee、Tax、Account Schedule 三类来源都必须具有明确 rule，显式 `not_applicable` 可以表示不收费，缺失不能默认为零；
- v1 只解释 `order_notional` 和 `flat_per_order` basis。未知 basis 或 `unknown` applicability 结构化失败，不调用 Profile callback 或自行推断；
- 所有收费使用同一显式 reservation Currency/Scale。Notional rate 采用 Typed Scaled Integer 与 rule 自带 `QuantizationPolicy`，禁止 float、隐式 rescale、FX 或 Stablecoin 假设；
- `FeeReservationMinimum` 显式声明覆盖的 charge rule IDs。只有至少一个 scoped charge 明确适用时，Estimator 才对 scope subtotal 添加一次 minimum adjustment；API 不接受 possible Fill count；
- Estimate 保存 source Approval、Rule Set、逐 rule line、minimum adjustment、总 Fee、估算时点和全部 identity/hash；Proposal 只填充 `ReservationCommitment.fee_reserve`，不生成其他资源承诺；
- 输入顺序不改变 Rule Set/Estimate/Proposal/Failure identity；任一 failure 都不产生部分权威输出。

不拥有：最终 FeeAssessment、FeeCharged/Journal、per-fill/order/session 最终聚合、具体市场 Fee/Tax schedule、Profile Resolver、Pre-trade Risk、Submission、Execution、Accounting 或 Runtime orchestration。

验收：

- Estimate 只影响 Reservation Proposal 和 Available Resources；
- per-order minimum fee 不被按潜在 Fill 次数重复预留；
- 未知 fee basis、未知 applicability、缺失 source coverage 或 context/hash mismatch 产生结构化失败；
- 订单终态由 ResourceReservation lifecycle 释放 Proposal，释放差额不构成 Accounting；
- Market/Tax/Account rules 与 input 顺序变化具有 canonical identity parity。

### WP-05I PreTradeRisk

拥有：使用 unchanged approved `ExecutableOrderSpec`、`MarketRuleApproval`、Fee 的 worst-case `ResourceReservationProposal`、supplied immutable 完整 `ReservationCommitment` requirement、当前 `ResourceReservationState`、`AvailabilityState` 和显式版本化 `AccountRiskPolicy` 进行 approve/reject。完整 requirement 是后续 Market/Account Profile 组合产生的输入证据；Generic PreTradeRisk 只验证其来源绑定并比较资源，不自行推导 Spot/Margin/Derivative 公式。

不拥有：修改 Quantity、Price、TIF、Order Type 或上游 Target。

验收：

- 只能返回 Approval 或 PreTradeRiskRejection；合法经济不足不是 Contract/Data Failure；
- `AccountRiskPolicy` 显式声明 Account/Venue、Order permissions、Fee Reserve 使用 Tradable Cash 或 Available Margin、Order Capacity 上限和逐 Currency Exposure Capacity 上限；不存在 implicit default；
- 完整 requirement 的 Fee Reserve 必须 exact 等于 WP-05H Proposal，Cash、Sellable Quantity、Margin、Fee、Order Capacity 和 Exposure Capacity 保持分类比较，禁止跨维度或跨 Currency netting；
- Cash requirement 使用 `tradable`，Sellable Quantity 使用 `sellable`，Margin 使用 `available_margin`；Fee Reserve 按 Policy 指定维度比较。当前 Availability 必须 exact 引用当前 Reservation State hash；
- 决策记录 Order、MarketRule、Fee Proposal、完整 requirement、Availability/Reservation State hash 和 Policy identity；
- 相同状态和订单产生相同 Decision，输入 tuple 顺序不改变 identity；
- MarketRule、PreTradeRisk 和 Execution rejection 分类不同；
- Context/hash mismatch、缺失资源维度、Currency/Scale mismatch 或未覆盖 Exposure limit 产生结构化 Contract Failure，不得降级为经济拒绝。

### WP-05J FeeAssessmentEngine

拥有：根据 Fill、Completed Order 或 Session basis 以及 MarketFeeRules、TaxRules、AccountFeeSchedule 产生最终 FeeAssessment。

不拥有：费用预留、Cash mutation 或 Journal replay。

验收：

- 支持 per-fill、per-order 和 per-session basis；
- minimum commission、sell-only tax 和 maker/taker fee 有独立 Fixture；
- FeeAssessment 幂等，重复 basis 不重复收费；
- FeeCharged Journal Entry 引用 FeeAssessment ID 和全部规则 identity。

### Gate G05

从 ActivePortfolioTarget 到 Accepted OrderState 的纯 Kernel Fixture 全部通过；Capability、Translation、MarketRule、Fee Reservation 和 PreTradeRisk 的失败分类互不混淆。独立 Synthetic Fill Fixture 可以产生幂等 FeeAssessment；不需要 Timeline 或 Bar Engine。

---

## 11. G06：Deterministic Bar Engine Harness

G06 只实现可重复的执行 Harness。它不拥有 BacktestRequest resolution、Semantic Run ID、Attempt ID、Run Outcome 或 Canonical Evidence publication。

### WP-06A MarketBundle read contracts + InMemory adapter

所属 package：`market-data-contracts`。

拥有：MarketBundleRef、Manifest、Reader、EventCursor 和 InMemory Fixture adapter。`market-bundle-builder` 只在后续实现写侧 Adapter，不是 Runtime 依赖。

验收：

- Reader 只读内容寻址 Bundle；
- Cursor 输出规范排序事件；
- batch size 变化不改变顺序；
- Runtime 不接触 Source Adapter；
- Bundle capability 缺失时返回结构化 `InputValidationFailure`，不映射为 BLOCKED。

### WP-06B Deterministic Timeline

拥有：多个 Cursor 的 `(epoch_nanoseconds, phase, source_sequence)` merge。

验收：

- 同时间多流排序有黄金 Fixture；
- 缺失/重复 source sequence fail closed；
- 不读取 wall clock；
- Warmup 和 `[start, end_exclusive)` 边界正确。

### WP-06C Precomputed TargetStream adapter

拥有：不可变 TargetStream 的读取、Validation 和 DecisionBatch 注入。

冻结边界：

- Target Stream v1 是 canonical `MarketEvent` 序列，capability 为 `precomputed_target_stream@1`、event type 为 `strategy_decision_candidate`；每个事件 Payload 使用精确 Envelope `schema_version + candidate`，Envelope decode 与 Candidate contract validation 分层；
- `PrecomputedTargetStream` 对完整事件序列计算稳定 `target_stream_digest`，供后续 ExecutionCase Builder 引用，但本 WP 不生成 Semantic Run ID；
- 一个 `TargetStreamDecisionSchedule` 显式绑定同一 Decision Time 的 Expected Strategy/Sleeve、源 Event ID 和可信 Validation Context；Adapter 不从不受信任 Payload 推断 Universe 或可信路由；
- Adapter 先保存 InputDecodeFailure 或 Candidate ValidationFailure，再把全部成功结果交给同一个 `AtomicDecisionBatchCollector`；任一失败均不产生部分 Batch；
- Warmup Event 仍经过 decode/validation，但成功后只产生显式 suppression evidence，不修改 Sleeve State、不产生 DecisionBatch 或任何下游交易权威对象。

验收：

- 只能绕过 Strategy 计算，不能绕过 Risk/Planning/Execution/Accounting；
- malformed stream 在 Adapter 层产生 InputDecodeFailure，Candidate validation failure 保持为结构化 ValidationFailure；
- ExecutionCase Builder 计算稳定 `target_stream_digest`，但不生成 Semantic Run ID；
- Warmup 期间 Target 不产生交易副作用。

### WP-06D Deterministic Slippage Model

拥有：ExecutionReferencePrice + Side/Quantity/允许市场状态 → SlippageDecision。

不拥有：订单成交资格、Bar 选择、Fill 数量、Fee 或 MarketRule。

首个实现：`deterministic_bps.v1`。

验收：

- BPS、Scale 和 RoundingPolicy 显式；
- Buy/Sell 偏移方向正确；
- 不读取未来 high/low/close/volume；
- SlippageDecision 记录 reference price、amount、execution price、model/calibration identity 和 applicability result；
- 超出 ApplicabilityEnvelope 返回 SlippageApplicabilityViolation；
- 禁止隐式零滑点；`zero_slippage.development.v1` 必须显式配置并产生 development limitation。

### WP-06E `next_eligible_bar_open.v1`

拥有：Portfolio Rebalance Order 的下一合格真实 Bar open 成交资格、ExecutionReferencePrice 和 full/no-fill 决定。

不拥有：Slippage 数值、Fee、Accounting 或 Bar 内 Queue/Partial Fill 推断。

冻结边界：

- Bar Engine 消费独立 `bar_open@1` Event；payload 只暴露 `schema_version`、`bar_kind` 和 Open Price，ExecutionModel 接口不接收 high/low/close/volume；
- Model 按 Timeline 逐 Bar、bounded、无状态调用，不接收未来 Bar 序列；
- 合格 Bar 必须携带同 Order/Instrument/Instant 的 MarketRuleApproval、PreTradeRiskApproval 和 versioned BarLiquidityEvidence；Rule interval 必须覆盖 Open，Session 必须 OPEN；
- `NextBarOpenApplicability` 显式完整映射全部 TIF 在 eligibility-window 结束时的 keep/expire，不提供默认；
- 第一根合格真实 Bar 只产生 full remaining Quantity 和 ExecutionReferencePrice；Fill ID 由调用方提供，且只有匹配的独立成功 SlippageDecision 才能进入 FullFillBuilder。

验收：

- 禁止 same-bar 或 pre-activation fill；
- 不使用未来 high/low/close/volume；
- gap placeholder、forward-filled Bar 不成交；
- 规则/资金/流动性通过后按 Profile full fill；
- no eligible bar 按显式 TIF mapping keep/expire；
- ExecutionModel 输出 reference price 后必须调用独立 SlippageModel 才能构造 Fill。

### WP-06F RunEndCoordinator

拥有：结束边界门控、Working Order termination、CloseoutPolicy 执行、pending obligation 收集和 RunEndReport。

不拥有：隐式 Fill、最终价格选择、Accounting mutation、Run Outcome 或 Evidence finalize。

验收：

- `trading_end_exclusive` 及之后不产生新 Strategy Decision 或业务事件应用；
- 默认 mark-to-market 保留 Position，不产生隐式平仓 Fill；
- Working Orders 产生 `OrderTerminatedByRunEnd` 并释放 Reservation；
- 显式 liquidate-before-end 必须在边界前经过完整订单与核算链；
- RunEndReport 记录 terminated orders、open positions、pending settlements、pending fee assessments、last valuation mark IDs 和 closeout status；
- 无法在边界前完成显式 Closeout 时返回结构化 EngineTermination，不自行映射 Run Outcome。

### WP-06G Engine orchestration harness

依赖：WP-06A–WP-06F。

拥有：`ResolvedExecutionCase`、Timeline loop、RunEndCoordinator integration、EngineExecutionResult、EngineTermination 和 final snapshot 调用。

不拥有：BacktestRequest、Semantic Run ID、Attempt、Run Outcome、Evidence 或 retry policy。

验收：

- 相同 ResolvedExecutionCase 产生相同 ExecutionTrace、Final Ledger State、Final PortfolioSnapshot 和 RunEndReport；
- InputValidationFailure、EngineFailure 和 EngineCancellation 保持结构化，不映射为 BLOCKED/FAILED/CANCELLED；
- Runtime 不能访问网络或 wall clock；
- Engine Harness 不创建 Result 或 Evidence 目录。

### WP-06H Synthetic Development Profile

所属位置：`tests/support/synthetic_market/`；不是默认 Production Profile Registry 的成员。

拥有：`synthetic.cash.development.v1`、固定离线 Bundle/Target factories 和静态 Golden Artifact。

不拥有：Generic Kernel 特殊分支、真实市场规则或 decision-grade 资格。

验收：

- 实现正式 Kernel/Simulation Ports，不绕过 Interface；
- 只能通过 TestProfileRegistry 或显式 `allow_development_profiles=True` 加载；
- Production Profile Registry 默认 lookup 失败；
- 使用该 Profile 的 G07 Evidence 自动记录 `synthetic_market_profile` limitation，永远不能标记 decision-grade；
- A 股/Binance Profile 不继承 Synthetic Profile；
- Golden Artifact 为静态文件，不能由被测实现现场生成。

### Gate G06：Engine Cash Happy Path

使用 development-only synthetic cash profile：

```text
Deposit
→ Target 50%
→ next real bar open Buy
→ FeeAssessment
→ Journal
→ Mark-to-market Final Snapshot
```

必须满足：

- 没有 same-bar fill；
- Fill reference price、SlippageDecision 和 execution price 可核对；
- 全链路可由 ID 追踪；
- Journal、Resolved Marks 和 CurrencyValuationGraph replay 等于 Final Snapshot；
- RunEndReport 与 Working Order、Open Position 和 pending obligation 状态一致；
- 第二次执行的 ExecutionTrace、Ledger State 和 Final Snapshot 完全相同；
- 不产生 Semantic Run ID、Attempt ID 或 COMPLETED Result；
- Synthetic Profile 只能通过测试或显式 development opt-in 加载；
- 此 Gate 不声称 development-grade Run、A 股或 Binance decision-grade。

---

## 12. G07：Auditable Runner、Canonical Evidence 与确定性运行

### WP-07A BacktestRequest/Profile resolution

拥有：Backtest Runtime composition root 中的 ProfileResolver、component registry lookup、MarketBundle capability compatibility、BuildArtifactManifest、request normalization 和 Semantic Run ID。Resolver 只组合和验证组件，不实现市场规则、Fee、Accounting 或 Slippage。

验收：

- ProfileResolver 取得 G06 ExecutionCase Builder 的 target stream digest，并与其他语义输入共同生成 Semantic Run ID；
- 相同语义输入和 Profile component digests 得到相同 Semantic Run ID；
- Generic Kernel 不感知 Registry，具体市场 Profile 通过 composition root 注入；
- MarketBundle capability 与 Profile requirements 不兼容时在执行前产生结构化阻断；
- code/profile/bundle 变化改变 ID；
- hostname、绝对路径、attempt start time 不进入 ID；
- editable/dirty code 没有 immutable artifact identity 时只能 development-grade 或 BLOCKED。

### WP-07A-R1 Pre-ID ExecutionCase Semantic Identity

修正 Semantic Run、领域 ID 和 final ExecutionCase hash 的循环依赖。Composition root 先冻结不含派生领域 ID 的 `ExecutionCaseSemanticSpec`，其 hash 进入 Semantic Run ID；再使用 Semantic Run namespace 派生 Order/Fill/Fee/Journal 等 ID，最后构造完整 `ResolvedExecutionCase`。

验收：

- Semantic Run ID preimage 只包含 ID-free Spec，不包含 final Case hash 或派生领域 ID；
- Spec exact-cover 全部行为相关 typed inputs，并冻结 role → identity type/Domain kind/semantic key/ordinal 的 identity plan；Factory 只能按 role 派生，builder 不能替换 key 或 ordinal；
- Composer 与 Runner 都从最终 Case 重算 ID-free Spec，校验 Request/Spec/Case、Slippage 完整配置、Order parent→NormalizedTarget 关系、Manifest derivation plan 和 role exact coverage；
- G07 使用 production `derive_domain_id()`，两个 Attempt 的领域 ID 和 final case hash 完全一致；
- Spec、identity plan 或行为配置改变会改变 Semantic Run ID；Attempt/hostname/path/time 不进入；
- 身份修正不得改变 Engine 的经济行为。

### WP-07B Auditable runner 与 Outcome mapping

拥有：Attempt identity、G06 Engine 调用、InputOrigin-aware failure mapping、Run Outcome state machine 和 retry-from-start policy。

v1 `InputOrigin` 只区分 `precomputed_target_stream` 与 `runtime_strategy`，并必须与 Request 的 Strategy Family 一致。Attempt 使用同一 Semantic Run 下显式递增的 ordinal 生成独立 `attempt_<sha256>` identity；Retry 创建直接 child Attempt 并从同一个初始 immutable ExecutionCase 重跑，不恢复旧 Attempt 的任何部分状态。

验收：

- Runtime Strategy Candidate failure → FAILED；预计算 Payload decode/validation failure → BLOCKED；Engine cancellation → CANCELLED；
- 所有 EngineFailureCode 由显式穷尽 mapping table 分类，禁止 default/fallthrough；
- ready-to-finalize/BLOCKED/FAILED/CANCELLED 四个 Runner 分支互斥；
- Bar retry 创建新 Attempt 并从初始状态执行；
- Runner 逐字保存且不修改 EngineExecutionResult 的经济轨迹；
- 成功 Engine result 只产生 `ReadyToFinalizeAttempt`，Evidence atomic finalize 成功前不得发布 COMPLETED Result；
- 本 WP 不实现 Evidence writer、canonical execution result hash、Integrity 或 ResultGrade。

### WP-07C Evidence writer

拥有：Attempt staging 目录、Canonical Artifact writer、content hash、EvidenceManifest exact coverage 和 atomic finalize。

v1 固定目录为 `runs/<semantic_run_id>/attempts/.staging/<attempt_id>/` → `runs/<semantic_run_id>/attempts/<attempt_id>/`。Writer 对 WP-07B 四个分支都发布 Attempt evidence；成功 Engine 分支在本 WP 只能标记 `READY_FOR_INTEGRITY`，不能产生 `COMPLETED`、`result.json`、Integrity 或 ResultGrade。

验收：

- 每个 Artifact 使用当前版本 `ArtifactEnvelope` 的 canonical UTF-8 bytes，记录 envelope content hash、exact source hash、schema version、role、relative path 和 byte count；
- Common evidence 固定包含 Request、Resolved Environment、BuildArtifactManifest、MarketBundleRef、Compatibility Report 和原始 `AttemptExecutionRecord`；四个分支分别增加 EngineExecutionResult、Blocked、Failure 或 Cancellation report；
- EvidenceManifest 覆盖 staging 中除自身外的全部权威文件；未列出文件、缺失文件、hash/schema/path/role 不一致均 fail closed；
- Manifest 最后写入并 read-back 验证，随后通过同一 filesystem 的 directory rename 原子 finalize；final destination 已存在时禁止覆盖；
- 未完成 staging 不可冒充 canonical Attempt；finalize 后 Writer 拒绝重写并把文件设为只读；
- 大型 MarketBundle 只写 `MarketBundleRef` immutable hash reference，不复制 Bundle events/partitions；
- ready-to-finalize 只发布 `READY_FOR_INTEGRITY` evidence；BLOCKED/FAILED/CANCELLED 保持原 Outcome，不转换成 COMPLETED；
- 任何 staging、Artifact、Manifest、rename 或 read-back 失败返回结构化 `EvidenceWriteFailure(outcome=FAILED)`，不得留下 final Attempt 或发布 Result；
- 本 WP 不生成 WP-07D execution result summary/hash，不执行 WP-07E Integrity/grade，不创建 canonical Attempt ref，不重跑 Engine，也不实现 cache/dedup/network/外部数据库。

### WP-07D Execution result hash

拥有：`EngineExecutionResult` 的规范执行摘要、Attempt Evidence 绑定和同一 Semantic Run 的执行一致性检查。

验收：

- `CanonicalExecutionSummary` exact-cover `ExecutionTrace`、DecisionBatch、Allocation、Portfolio Risk approvals/decisions、Normalized/Active Target、Order Plan/Event、Fill、Slippage、FeeAssessment、Accounting Journal、Final Ledger/Snapshot 和 RunEnd；
- summary/hash 不包含 Attempt ID、Evidence path/Manifest hash、日志、图表、Metrics 或展示字段；
- `AttemptExecutionHash` 只允许绑定 `READY_FOR_INTEGRITY` Evidence，验证 Attempt/Semantic Run 和 `engine-execution-result.json` envelope content hash，但其 `execution_result_hash` 只来自 canonical summary；
- 任一权威交易或财务事实变化必须改变 execution result hash；图表、日志格式、派生 Metrics、Attempt identity 或 Evidence relative directory 变化不得改变 hash；
- 同一 Semantic Run 的多个 ready/completed-candidate Attempt 必须产生同一 execution result hash；不同 hash 返回 canonical `ExecutionHashMismatch`，不得按 Attempt 顺序或时间静默选择；
- 本 WP 不实现 Integrity/ResultGrade、发布 COMPLETED、canonical Attempt ref、cache/dedup、Metrics、network 或 deployment authorization。

### WP-07E Integrity report 与 Canonical Result publication

拥有：stable blocking issue/limitation taxonomy、result grade、deployment authorization 固定为 false，以及 Evidence finalize 之后的 Canonical Result 原子发布。

验收：

- Publisher 获取 trusted local filesystem 上的 run-level exclusive lock，并 exact-cover 当时全部 finalized `READY_FOR_INTEGRITY` Attempt；`COMPLETED` 至少需要两个 execution hash 一致的 Attempt，canonical Attempt 固定选择最小 ordinal；
- Integrity 只绑定 closed Attempt set、WP-07D execution hash/check、Resolved Environment 和 caller-supplied canonical `DeterministicRebuildEvidence`；不得重跑 Engine；
- `deployment_authorized` 永远为 false；
- Development Profile、Build/Environment、summary trace、Bundle retention 和 deterministic rebuild limitation 不得隐藏；
- Decision grade 要求 immutable Build、decision-grade Profile、可取回 Bundle、full/microstructure trace、same-run execution hash 一致且无 blocking issue；Summary trace 永远不能 decision-grade；
- execution hash mismatch 在 `integrity-evaluations/<evaluation_id>/` 原子发布 durable `FAILED`；少于两个 eligible Attempt 或其他预期 blocking 原子发布 durable `BLOCKED`。二者都不创建 `canonical/` 或 `result.json`；
- 只有 closed Attempt set + 一致 execution hash + 无 blocking Integrity 才能产生 COMPLETED Result。Canonical DAG 固定为 AttemptRef → Integrity → Result → PublicationManifest，manifest exact-cover 同目录其他三个文件；
- Canonical publication 在独立 staging 中写 `canonical-attempt-ref.json`、`integrity.json`、`result.json`、`publication-manifest.json`，read-back 后原子 rename 到 `runs/<semantic_run_id>/canonical/`；不得修改 Attempt evidence；
- final canonical 目录和 evaluation 目录只读且不可覆盖。Canonical 发布后 Semantic Run 封闭，Evidence Writer 拒绝新 Attempt；Auditable Runner 必须绑定 publication root，并在锁内验证 existing canonical Artifact/Manifest/hash chain 后返回 cache hit，不能创建 Attempt、返回 FAILED 或重跑 Engine；post-publication same-run parity 不在 v1；
- v1 只支持 trusted cooperative single-writer、受控本地同一文件系统和同一排他锁；不支持 shared/adversarial filesystem、NFS/object-store rename 语义或基于 wall clock 的 stale-lock 自动回收。任何失败不得留下可见 Completed Result。

### Gate G07

同一 Synthetic Run 执行两个 Attempt：Attempt ID 不同，Semantic Run ID、领域 ID 和 execution result hash 相同；Evidence Manifest 各自完整且互不覆盖。任何 Attempt 只有在 Integrity validation 和 Evidence atomic finalize 成功后才能发布 COMPLETED Result。

G07 完成后才算拥有“可审计 development-grade 回测运行器”。

---

## 13. G08A–G08H：A 股 Cash Profile

每个子 Gate 独立合并、验收和停止；全部使用 Synthetic/Frozen Fixture，不依赖 G12 真实 MarketBundle。

### Gate G08A Calendar and Session

拥有：`xshg`/`xshe` 标准现金股票竞价市场的有限 Frozen Calendar、`Asia/Shanghai` 本地时区转换、Session phase、Known Closure 和 TradingDate 归属 Adapter。每个 concrete `CnAShareCashSessionModel` 只绑定一个 Venue Calendar，并实现已有 `SessionModel.resolve_session()` seam；不构造 partial `MarketSemanticsProfileRegistration`。

不拥有：T+1、价格限制、费用、公司行为、DecisionSchedule、Timeline/MarketEvent 生成、Registry composition、运行时网络/provider 读取或 G12 MarketBundle。

v1 official-source-backed phase table 使用半开区间工程约定：

```text
[00:00, 09:15)  pre_open             CLOSED
[09:15, 09:25)  opening_call         OPEN
[09:25, 09:30)  opening_pause        CLOSED
[09:30, 11:30)  continuous_morning   OPEN
[11:30, 13:00)  lunch_break          CLOSED
[13:00, 14:57)  continuous_afternoon OPEN
[14:57, 15:00)  closing_call         OPEN
[15:00, 24:00)  post_close           CLOSED
```

上海与深圳 2023 修订交易规则均给出相同现金股票竞价时段；区间端点的半开表达、pause/lunch/pre/post 名称是系统解释约定。2024 春节 Frozen Fixture 固定 2024-02-09 至 2024-02-17 休市、2024-02-18 周末休市、2024-02-19 恢复交易。

验收：

- 开盘集合竞价、开盘暂停、上午连续竞价、午休、下午连续竞价、收盘集合竞价和收盘后边界正确；
- 周末和已声明 Frozen Holiday 是成功的 known no-session resolution；未知日期或 coverage 外查询是结构化 failure，禁止把缺失数据解释成休市；
- TradingDate 由 `Asia/Shanghai` local date 和 Frozen Calendar 显式赋值，不由 UTC date 猜测；
- `SessionId(calendar_id, YYYY-MM-DD.regular)` 在同一交易日全部 phase 内稳定，相同 Calendar input 与不同构造顺序产生相同 Calendar/component digest；
- `VenueId("xshg")` 使用 `calendar_id="CN.XSHG"`，`VenueId("xshe")` 使用 `calendar_id="CN.XSHE"`；BSE、基金、债券、盘后固定价格、港股通和特殊临时 Session 不在 v1 scope；
- concrete profile 只从 `crypto_quant_trading.profiles.cn_a_share` 导出，generic Kernel 不依赖它；
- Fixture 和 Model 只允许 development-grade，不声称 current-live 或 decision-grade calendar。

### Gate G08B T+1 Settlement and Availability

依赖：G08A。

拥有：普通人民币 A 股现金账户的 concrete `SettlementModel`；其 `availability_rules()` materialize 既有 generic `MarketSettlementRules` value，并与 generic `SettlementBook`/`AvailabilityProjection` 形成组合证据。准确语义是：成交经济事实在 T 日立即入账；T 日买入的普通 A 股在下一交易日才可卖；T 日卖出所得可继续用于证券买入，但按 v1 保守账户约定在下一交易日资金可用性成熟后才可提现。禁止把它简称为法律意义上的“Cash T+0 settlement”。

v1 将 `SettlementObligation.settlement_time` 保持为账户交付义务的完成时点，并在该现金账户 Adapter 中令完成时点同时成为相应资源的 availability-maturation instant：负 Cash/Position delivery leg 在 Fill time 完成；正 Position receivable 在下一交易日 `00:00 Asia/Shanghai` 完成，以支持开盘前规划；正 Cash receivable 在下一交易日 `16:00 Asia/Shanghai` 完成。后者只是参考中国结算最晚参与人资金交收边界的保守 development-grade 客户账户约定，不是逐 Fill 中央交收或所有券商提现承诺。两个时点均进入 component digest。

验收：

- T 日买入立即增加 Ledger total Position，但 positive Position receivable 在下一 Frozen TradingDate 的 00:00 前从 Sellable Quantity 扣除；禁止使用 calendar-day 或 weekday `+1`；
- T 日卖出立即增加 Ledger total Cash。Positive Cash receivable 在 pending 时计入 Tradable Cash、不计入 Settled/Withdrawable Cash，并在下一 Frozen TradingDate 的 16:00 `SettlementApplied` 后成熟；
- Buy negative Cash leg 与 Sell negative Position leg 在 Fill time 成熟，不能因 generic Projection 只扣 positive receivable 而永久留在 pending；SettlementApplied 不重复写 Ledger；
- concrete Adapter 从 supplied `FILL_BOOKED` Accounting Entry 取得 exact signed Cash/Position effects，不独立重算 Notional 或舍入；Entry 必须 exact 绑定 Fill/Order source、effective time、Account/Venue 和空 Fee/Financing。Bare Entry 的 Journal inclusion 不是五类型 seam 可证明的事实，G08B fixture/G08H 必须把该 Entry hash、authoritative Journal/Ledger prefix 和 Settlement Recorded evidence 显式绑定；
- Fixed rules 为 `pending_receivable_tradable=true`、`pending_receivable_withdrawable=false`、`pending_receivable_margin_eligible=false`、`pending_receivable_sellable=false`；Cash/Fee Reservation 与 Sellable Reservation 继续由独立 `ResourceReservationBook` evidence 扣减。Generic `available_margin` 输出不构成 Margin 授权，G08H cash-account policy 必须禁止使用；
- Settlement Obligation、Settlement Event 与 Working Order Reservation 保持不同身份/状态流；Adapter 不生成 Event。Fixture 对同一 UTC instant 的 Recorded/Immediate-Applied 使用显式递增 `SimulationInstant` phase/source sequence，禁止依赖 Event ID lexical ordering；full replay、prefix resume 和输入顺序变化产生相同 Book/Availability hash；
- XSHG/XSHE 共享算法和经济语义，但 Calendar/component digest 独立；Fixture 使用 2024 春节 02-08 → 02-19 跨休市结算，并在 Calendar coverage 无法证明下一交易日时 fail closed；
- Adapter 只验证 Contract 可观察的 Venue、broad Equity type、Instrument identity 和 CNY currency。普通 A 股/Stock Connect/cash-account classification 是 G08H caller precondition，G08B 不得声称已验证；
- 不修改 generic Settlement/Availability seam，不生成 Runtime Event ID，不实现 Fees/Tax、Margin、Stock Connect、B 股/基金/债券、Broker transfer cut-off、Registry 或 Runtime orchestration。

### Gate G08C Quantity Lattice and Odd Lot

依赖：G08A、WP-04E、WP-05D、WP-05G。

拥有：concrete A-share `InstrumentModel` Adapter、position-relative `QuantityLattice` capability、100 股买入手数、完整 Sell Residual Component、odd-lot close 和 generic ResidualPositionPolicy integration。

验收：

- 普通 A 股竞价买入 order delta 按 100 股手向目标方向 toward-zero；卖出 normal delta 为 100 股整数倍，当前完整 `H mod 100` 余股可以单独或与 normal lot 合并一次申报，不能拆分；
- G08C 使用 current Position-relative reachable target，不把 order-side lot 误写成 absolute target multiple；existing schema-v1 lattice bytes/hash 保持兼容；
- XSHG/XSHE concrete Adapter 只验证 Venue、broad EQUITY 和 CNY，可观察不到的普通 A 股/STAR/ETF/Stock Connect/cash-account classification 保持 caller/G08H precondition；
- Sizing Decision 区分 Sizing Residual 与 Sell Residual Component，`close_if_permitted`、`hold_dust`、`fail` 结果可审计，任一失败原子拒绝账户级 target；
- Frozen fixture 覆盖 flat buy、odd holding buy、normal sell、完整余股单独/合并、one-share residual、full close、arbitrary odd negative control、unequal buy/sell-lot generic control、input-order parity 和 one-share boundaries；
- RebalanceCoordinator 逐字消费 exact normalized Quantity，证明 `SELL 99`、`SELL 1` 等合法 delta 不被第二次舍入；position-relative target 在 partial fill 后失去 working coverage时必须 stale-omit 并要求重新 sizing，不能从旧 target 生成新的 odd order；effective-lattice change evidence 留给 G08D/H；
- Order admission 对 authoritative sellable balance 的验证仍属于 G08D；G08C 不声称 arbitrary odd sell 已通过 MarketRuleEvaluator。

### Gate G08D Historical Order Rules and Price Limits

依赖：G08A、G08C、WP-05G。

拥有：caller-injected finite `CnAShareOrderRuleBook`、Board-aware historical `OrderRuleTimeline`、explicit Suspension、方向敏感 bar-open Price Limit decision，以及 residual-sell admission 所需的 canonical authoritative position evidence seam。G08D 为 `OrderRuleEvaluationInput` 和 `OrderRuleSnapshot` 冻结向后兼容的版本化扩展；legacy evidence/cap 为空时 schema-v1 bytes/hash 不变。

v1 只批准 standard seasoned XSHG Main/STAR、XSHE Main/ChiNext cash auction。Board、listing/risk classification、previous close 和 trade status 都是 supplied point-in-time evidence，禁止从 symbol、缺 Bar、零 Volume 或 current rule 推断。Risk-warning累计买入和无涨跌幅股票价格笼子/临停因 seam 不完整而 fail closed，不做部分实现。

冻结历史事实至少包括：ChiNext standard seasoned 在 2020-08-24 从 10% 切换到 20%；2023-04-10 后 XSHG/XSHE Main 为 10%；STAR 为 20%；Main/STAR/ChiNext Limit/Market 单笔上限分别为 1,000,000/1,000,000、100,000/50,000、300,000/150,000。Limit 使用 previous close、CNY 0.01 tick 和 HALF_UP integer rounding。

Authoritative odd-sell evidence exact 绑定 evaluated-at PortfolioSnapshot、AvailabilityState、ResourceReservationState、ACTIVE/PARTIALLY_FILLED Working Orders、total/sellable Quantity 和 resolved lattice hash。缺失/链不一致是 DataIntegrityFailure；证据有效但拆分 residual、重复预留或超 sellable 是 MarketRuleRejection。STAR “至少 200 股”使用 step 1 + minimum 200，不得误建模为 200 股整数倍。

验收：

- upper-limit open Buy 与 lower-limit open Sell 产生 `liquidity_blocked_at_limit`，反方向继续；
- conservative input 不含全天 Volume，不从日内后续成交补 Queue fill；
- Suspension、known NoTrade 和 DataMissing 分类不同；
- 历史 Rule 缺失/重叠时 fail closed，不回退 current rule；
- execution-style 单笔上限、HALF_UP tick rounding、ChiNext transition 与 ordinary/STAR quantity semantics exact；
- H=299 的 SELL99/199/299 仅在 evaluated-at evidence 支持时获批，arbitrary odd、超 sellable 和 active residual reservation fail closed；
- G08C ordinary Main lattice hash exact 复用，schema-v1 compatibility golden 保持。

### Gate G08E Commission and Tax

依赖：WP-05H、WP-05J。

拥有：caller-injected finite A-share market-fee/stamp-duty RuleBooks、structural `FeeAssessmentPolicy`/`TaxPolicy` Adapter，以及与其严格分离的 caller-supplied AccountFeeSchedule fixture。Generic `FeeReservationEstimator`、`FeeAssessmentEngine`、`FeeChargedJournalTranslator` 和 Journal/Ledger 不新增 A 股分支。

v1 只批准 XSHG/XSHE standard domestic CNY cash-auction A-share fixture，并冻结窄历史窗口：2023-08-25 使用交易经手费 0.0487‰、卖方印花税 1‰；自 2023-08-28 使用交易经手费 0.0341‰、卖方印花税 0.5‰。两个区间都显式包含双边证券业务监管费 0.02‰ 与交易过户费 0.01‰。Block trade 与窗口外日期在本 Adapter 内 fail closed；B 股、基金、Stock Connect、Margin 和真实券商合同不由 Query 表达，必须由 G08H/Profile composition 作为 caller precondition 阻断，G08E 不得声称支持或自行推断。

Broker commission 不属于 MarketSemantics。Golden 使用 caller-supplied synthetic development net-commission schedule：双边 0.3‰、每个有 Fill 的 terminal Order 最低 CNY 5.00，并明确不代表任何真实券商或“佣金已包含规费”的统一做法。

最终 market fee/stamp duty 按 `FeeBasisType.FILL` 和 Fill execution time 解析/量化；最终 broker commission 按 terminal `FeeBasisType.ORDER` 聚合实际 Fills，minimum 只应用一次。Reservation 按获批完整订单 notional 估算，并必须组合 caller-supplied `maximum_fill_count` 的 canonical rounding buffer：每个 applicable final component 额外预留 `floor(N/2)` 个 CNY cent；实际 Fill 数超过 N 时 fail closed。Reservation 不能复用为最终 Assessment。

验收：

- per-order minimum commission 不按 Fill 重复收取，无 Fill cancel 不收费；
- 多 Fill、部分成交和取消后按实际 Fill 产生 per-Fill market/tax 与单一 per-Order commission；
- `maximum_fill_count=2` 时，10,000 CNY 获批订单只成交两个 1,000 CNY Fill 后取消，Reservation CNY 10.68、final CNY 6.12、terminal Reservation 清零并释放相对最终费用 CNY 4.56；
- BUY 的印花税是 `NOT_APPLICABLE`，SELL 才应用；
- 每个 component 使用 CNY Scale 2、explicit `HALF_UP`；独立 CNY 2,000 fully-filled/two-Fill sentinel 冻结未缓冲 aggregate CNY 6.13、bounded reservation CNY 6.17 与 per-Fill final CNY 6.12；
- Tax/Fee component、active band、charge rule、RuleSet、basis 和 AccountFeeSchedule identity 进入 Assessment result 与 `FeeCharged` Journal source IDs；
- exact 2023-08-28 local boundary 选新规则；RuleBook 缺失/重叠时 fail closed，不回退 current/nearest rule；
- concrete Adapter 不读取 network/filesystem/provider/process/database/wall clock，不拥有账户佣金或 deployment authorization。

### Gate G08F Corporate Action Observation and Entitlement

依赖：G08A、WP-06A Market Event、WP-06B Deterministic Timeline。

拥有：final implementation Announcement event/available time、Record/Eligibility Instant、authoritative historical registered-position snapshot 和 immutable gross Entitlement capture；不拥有 Strategy-facing ObservationView、Journal mutation、Adjustment、Payment 或 Tax。

验收：

- Announcement 保持普通 `MarketEvent` causality：未来 Record/Ex/Payment/Listing 只在 payload，available boundary 使用完整 `SimulationInstant(available_time, phase, source_sequence)`，边界前不能由 Timeline 返回；Strategy-facing 集成由 G11B 验证；
- Record eligibility 使用 local 15:00 session-close 的 explicit development ordering convention；registered-position snapshot 可以稍后可用，但必须 exact 绑定 Record instant、account、instrument 和 source hash；
- Entitlement 只使用历史 `R`-close registered quantity，后续当前 Portfolio/Ledger/Order/Fill/Bar 不能替代或重算；
- XSHE 支持 strictly positive final cash/bonus/capitalization terms，XSHG v1 仅支持 cash；XSHG share-listing provenance 未消歧前 bonus/capitalization 以 `UNSUPPORTED_VENUE_ACTION_COMBINATION` fail closed。Cash 要求 Payment date，XSHE bonus/capitalization 要求 Listing date，share Rate basis 固定 `shares_per_share`；frozen v1 的 declared Ex/Payment/Listing 必须等于 Record 后首个 known G08A TradingDate；invalid lifecycle order/rate basis、fractional share、sub-cent cash、negative input、supplied revision/cancellation、late Announcement、缺少 Announcement/Register/Calendar/Rule coverage 均 fail closed；complete closed announcement/register revision-set 与 Query 不可观察的 security/account/distribution scope 由 G08H/Profile composition 阻断；
- zero registered quantity 产生 canonical zero entitlement；G08F 不产生任何 Journal/Ledger/Lot/Settlement/Availability mutation。

### Gate G08G Corporate Action Adjustment and Payment

依赖：G08F、G03 Accounting；当前状态 `DRAFT`。

拥有：Ex/Effective position adjustment、Payment cash、withholding/tax Journal translation。

READY 前阻断：

- Generic Journal/Ledger 必须拥有 replayable Position Lot create/replace/close effects，Runtime mutable lot side-state 不能作为权威；
- `PositionLot` 必须拥有 exact authoritative total Cost Basis，不能只靠 fixed-scale unit cost 声称任意 ratio 守恒；
- 新股 sellability、支付现金 tradable/withdrawable availability、fractional delivered quantity、gross/deferred tax 和 delayed/suspended lifecycle evidence必须冻结；
- Fill accounting 与 Corporate Action 必须共享 Lot-effect contract并通过 full/prefix/resume replay；多 Lot 的 entitlement allocation 必须有 authoritative per-Lot evidence，或 v1 exact 限制为单一 eligible Lot；
- Corporate Action tax disposition 至少区分 NOT_APPLICABLE/APPLIED/DEFERRED_UNSUPPORTED；G08G owns disposition，G08H/Runtime 对 deferred unsupported 后续 taxable transfer fail closed。

最终验收仍包括：

- 送股/转增调整 Lot quantity，并从 exact total Cost Basis 派生 unit cost；
- 除显式规则另有规定外总 Cost Basis 保持；
- Payment trigger 前不得产生 Cash Journal Entry；
- adjustment/payment 幂等并可 Journal replay；
- 缺少 Effective/Payment/Listing 或 availability evidence 时 fail closed；
- raw tradable prices 不被 ex-reference metadata 改写。

### Gate G08H A-share Profile Composition and Parity

依赖：G08A–G08G。

拥有：`equity.cn_a_share.v1` component composition、完整黄金 Fixture、announcement/register complete closed revision-set validation、跨 Query identity-history validation、不可由 G08F Query 表达的 security/account/distribution scope qualification，以及 `cycle-rotation-platform` ParityReport。

验收：

- Profile composition exact 证明没有遗漏 later announcement cancellation/revision 或 register correction，并对跨 Query stable ID conflicting reuse fail closed；
- Profile composition 在调用 G08F 前阻断 ordinary-vs-preferred、cash-auction mechanism、B/H、Stock Connect、margin/short、lending/repo、pledge/freeze、restricted/pre-IPO、differential distribution 和 issuer self-distribution 等 Query 不可观察上下文；
- Timeline、Runner、Generic Ledger 和 Bar Engine 不新增 A 股条件分支；
- ProfileResolver 对全部 component/capability 兼容性验证通过；
- 完整 Fixture 覆盖 T+1、100 股手、价格限制、费用、税和公司行为；
- 与固定 `cycle-rotation-platform` source 使用分层 ParityContract；
- ParityReport 定位 first divergence；
- 任何未支持且影响结果的公司行为产生结构化阻断。

---

## 14. G09A–G09H：Linear Perpetual Accounting

每个子 Gate 使用 Synthetic Linear Perpetual Fixture，不包含 Binance symbol、fee 或 historical rule Adapter。

### Gate G09A Linear Derivative Position Model

拥有：Linear Perpetual long/short Position quantity、average entry basis、contract multiplier 和 flip state transition。

不拥有：账户 Margin、Funding、Fee 或 Liquidation。

验收：

- Long/Short 开仓、加仓、减仓和 Flip 状态正确；
- Quantity/Price/Multiplier Scale 运算精确；
- Position state 可从 Fill sequence 确定性重建；
- Generic Ledger 不增加 Instrument type 条件分支。

冻结实现 seam：G09A 只新增 pure `crypto_quant_trading.derivatives` deep module，唯一行为 interface 为 `LinearPositionProjector.project(LinearPositionProjectionRequest)`；不新增 Port、Adapter、Profile 或 Runtime integration。Request 使用 caller-ordered immutable Fill tuple，从 Flat state 原子投影完整 sequence；signed Quantity 正/负/零分别表达 Long/Short/Flat，同 execution time 由 tuple order 决定且 Projector 不排序。

Average entry 使用 GCD-reduced exact rational `ExactAverageEntryBasis(numerator, denominator)`，禁止 float、Decimal 或固定 Scale rounding。OPEN 使用 Fill Price；ADD 按同 Scale raw Quantity 加权；REDUCE 保持 prior basis；CLOSE 清空 basis；FLIP 的新方向只使用 crossing Fill Price。Contract multiplier 是 positive `Rate`，basis exact 为 `base_quantity_per_contract`，进入 Contract/State identity但在 weighted average 中代数消去。G09A 不计算 PnL；G09B 再冻结 `sign(before.quantity.units) × closed_quantity × multiplier × (exit price - prior basis)` 到 Money 的量化边界。

G09A Result/Failure 嵌入完整 Request 并使用 canonical schema v1/hash；Transition constructor 重算 kind、closed Quantity 和 after State，Projection 重放全部 Transition。Duplicate Fill、time regression、context/Scale mismatch 按 Acceptance Matrix first-failure precedence 原子 fail closed，不返回 partial prefix。Cash PositionLot、Generic Ledger、SnapshotProjector、Engine 和 Runner 不感知 derivative type。

### Gate G09B Fill-to-Journal and PnL

依赖：G09A、G03 Accounting。

拥有：Linear Derivative Fill → Position/Realized PnL Journal translation。

验收：

- Partial close 和 full close realized PnL 正确；
- Unrealized PnL 只由 SnapshotProjector + Mark 派生；
- Fee 保持独立 FeeAssessment/Journal Entry；
- Journal replay 与 direct projection exact parity。

冻结实现 seam：G09B 只新增 `crypto_quant_trading.derivative_accounting`。`LinearDerivativeAccounting.translate_position_fact()` 每次消费一个完整 G09A Transition、settlement Cash registration、QuantizationPolicy 与 Journal context，产生一条 frozen `LinearDerivativeJournalEntry`。该类型继承 `AccountingJournalEntry`：既有 `AccountingJournal` 直接保存完整 derivative evidence并继续拥有排序/哈希/幂等/冲突语义；Generic Ledger只读取继承的通用经济字段，不增加 derivative branch。

Realized PnL先形成 GCD-reduced signed exact rational。对 before sign `s`、closed raw Quantity `C`/factor `Q`、multiplier `m/M`、exit Price `p/P` 与 before basis `N/D`，公式 exact 为 `s*C*m*(p*D-N*P)/(Q*M*P*D)`；OPEN/ADD 为 `0/1`，FLIP 只结算旧方向 closed portion。Money只在每个 Transition 末端通过 caller-supplied QuantizationPolicy 和 public `round_ratio` 量化一次。Perpetual principal notional不改变 Cash；只有非零 quantized realized PnL 同时进入 Cash BalanceChange与 gross realized attribution，Fee/Funding/Unrealized PnL保持独立。

`LinearDerivativeLedgerProjector` 从 immutable Journal 的 specialized Entries按 published order重建 target exact State；caller必须使同一 target 的 `(recorded_at, journal_entry_id.value)` 按 G09A Transition lineage严格递增，Projector不排序或修复错误 booking context。Replay先拒绝 Journal-wide specialized duplicate Fill，再拒绝普通 Entry 改写 target Position和 transition lineage mismatch；随后调用 branchless Generic Ledger验证 signed Position Quantity 和 state hash。Replay Projection保存 exact PnL aggregate与逐 Transition 已量化 Money aggregate，后者禁止重新 aggregate-quantize。Runtime dispatch/Profile composition继续由 G09H拥有。

### Gate G09C Funding Publication and Eligibility

依赖：G09A、G09B、WP-06A MarketEvent 与 WP-06B Timeline contracts。

拥有：Funding publication available time、stable Funding Slot ID、closed publication revision chain 和 Eligibility Position capture。

验收：

- Strategy 不能在完整 `SimulationInstant` publication available boundary 前观察费率；
- Eligibility Instant exact 使用 `TimelinePhase(100, "funding_eligibility")/SourceSequence(0)`，锁定同一 authoritative Journal 的最大 `recorded_at < eligibility` prefix，不使用后续 current Position；
- Slot ID 只绑定 Instrument 与 target funding UTC，重复/修订 publication 对同一 Slot只产生一个 immutable eligibility observation，不创建 obligation；
- root/correction/cancellation chain、missing publication/position、late/unavailable evidence按 frozen precedence fail closed。

冻结实现 seam：G09C 只新增 pure `crypto_quant_trading.funding`。Caller/G09H/G10E把普通 MarketEvent映射为 `LinearFundingRatePublicationCandidate`；production Kernel不导入 MarketBundle或Runtime。`LinearFundingEligibilityResolver.resolve()`消费 Slot、Contract、Position key、完整 publication chain、Eligibility Instant、historical Position Snapshot和 captured-at，返回 dedicated `LinearFundingEligibilityOutcome`；它不使用 Profile Port identity，也不实现 FinancingModel accounting。

Historical Position Snapshot 嵌入 G09B availability projection、同一 Journal 的 eligibility cursor与 cutoff `LinearPositionState`。Snapshot constructor按完整 SimulationInstant找到 Journal最大 `< eligibility` prefix，验证 cursor/prefix hash，并以 G09B projector重放该 prefix；availability projection可包含 eligibility后的 close/flip，但不得替代已冻结 cutoff State。G09C只返回 Rate publication + historical State eligibility evidence；Applied Rate、Funding Mark、cash direction、Journal/Ledger mutation仍由 G09D拥有。

### Gate G09D Funding Settlement and Accounting

依赖：G09B、G09C。

拥有：Applied Rate、Funding Mark、cash direction、account/Slot application identity 和 Funding Journal translation。

验收：

- Long/Short/Flat在正、负、零Rate下现金方向正确，exact Funding amount只在Money boundary量化一次；
- Funding Mark exact 使用 `PricePurpose.FUNDING`，完整 StaleMarkPolicy、resolution identity与Mark Resolver authoritative UTC availability进入证据，不允许caller伪造full phase或使用其他Price Purpose fallback；
- 同一Account/Funding Slot使用同一canonical SETTLEMENT/JOURNAL ID幂等结算，changed evidence触发native Journal conflict；alternate ID重复/冲突由full-Journal projector fail closed；
- Journal Entry引用publication、eligibility、historical Position、applied Rate、mark/policy、settlement source、quantization和application identity，Generic Ledger保持branchless。

冻结实现 seam：G09D只新增 pure `crypto_quant_trading.funding_accounting` 并结构化实现既有 `FinancingModel`。Application Key exact为`(account_id, funding_slot_id)`；caller提供Identity Namespace与Semantic Run，module以Application Key value、ordinal 0分别重新派生SETTLEMENT/JOURNAL ID。Translator不读取prior Journal、不append/mutate authority；existing Journal负责same-ID no-op/conflict，独立Funding Journal Projector负责完整Journal中的alternate-ID duplicate/conflict与ordinary/non-exact funding Entry拒绝。

G09D v1 Applied Rate必须exact等于G09C final published Rate，basis为`funding_fraction_of_notional`。对signed eligibility Quantity `q/Q`、positive multiplier `m/M`、positive Funding Mark `p/P`、signed Rate `r/R`，账户Cash exact为`-(q*m*p*r)/(Q*M*P*R)`，GCD约分后仅调用一次`round_ratio`映射到caller-supplied settlement Cash Scale。Positive Rate时Long支付、Short收取；negative反向；Flat、zero Rate和rounded zero仍发布唯一specialized `FUNDING_APPLIED` evidence Entry。

Funding Mark必须在target Funding UTC以`PricePurpose.FUNDING`解析，Instrument、settlement Currency、Price Scale、Stale Policy与`ResolvedMark.available_at` UTC均exact匹配；G09D不增加caller-supplied mark phase/sequence。Settlement `effective_time` exact为Slot target UTC，`recorded_at` exact为account settlement evidence `applied_at`，且Eligibility captured-at与Mark available UTC必须不晚于该booking boundary。Generic Ledger只消费Entry继承的Cash/financing字段，不增加Funding分支。G09D不拥有provider mapping、Mark query/fallback、SettlementBook、Margin/Liquidation、Runtime dispatch或deployment authorization。

### Gate G09E Instrument Margin Requirement

依赖：G09A。

拥有：Historical leverage/margin tier 下单 Instrument initial/maintenance requirement。

不拥有：账户级 Equity 聚合、Available Margin 或 Liquidation 决策。

验收：

- Tier boundary、notional 和 leverage 计算精确；
- Historical tier identity 进入结果；
- 缺失/重叠 tier fail closed；
- 不回退到当前交易所 tier。

冻结实现 seam：G09E只新增pure `crypto_quant_trading.margin`并结构化实现既有`MarginModel`。Request exact消费Position key、完整G09A Contract、caller-supplied signed Margin Exposure Quantity、evaluated-at、optional historical leverage evidence、optional historical Margin Rule Book、optional Margin Mark evidence、settlement Cash registration和requirement QuantizationPolicy；optional只用于structured missing-evidence failure。它不读取current Position/Ledger/Portfolio/Order/Working Order，也不创建Reservation或账户Projection。

Historical leverage evidence绑定Account、Instrument、selected leverage、半开effective interval、完整`SimulationInstant` available-at与source key/hash。Rule Book绑定Instrument、settlement Currency、authoritative tier Scale和caller-injected historical intervals；每个interval保存半开effective range、full availability、source identity和ordered Tiers。查询必须命中唯一effective interval且evidence已available；历史缺口即使存在later/current interval也fail closed，重叠不按版本、顺序或最新来源猜测。

Margin Tier以exact Money floor与optional cap保存maximum leverage、maintenance margin rate和nonnegative maintenance deduction。G09E原始schema-v1区间保持lower-inclusive/upper-exclusive并从zero连续覆盖到unbounded；G10C只可增加backward-compatible provider-neutral boundary convention，使Binance upper-inclusive bracket与finite terminal cap可被exact表达，既有canonical bytes/hash与选择结果不得变化。Tier集合必须按floor严格递增并连续；order mismatch、gap、overlap、finite coverage overflow、Currency/Scale/Basis mismatch分别按frozen precedence失败。Provider `ma`/`initialLeverage`、maintenance ratio与`cf`/`cum`等字段只能由G10C Adapter显式映射为generic maximum leverage/rate/deduction；G09E不识别provider字段或symbol。

对signed Quantity `q/Q`、positive multiplier `m/M`和positive `PricePurpose.MARGIN` Mark `p/P`，exact notional为`abs(q)*m*p/(Q*M*P)`。Selected leverage `l/L`下Initial exact为`notional*L/l`；Maintenance exact为`notional*rate-deduction`。Tier选择使用未量化notional；selected leverage不得超过tier maximum；negative Maintenance fail closed。Initial/Maintenance各自只调用一次public `round_ratio(exact*target_scale.factor, denominator, CEILING)`，禁止float/Decimal、pre-quantization、FX或隐式rescale。

Result保存component、完整Request/hash、resolved historical Interval/Tier、exact notional、exact Initial/Maintenance及quantized Money。G09E不聚合Equity、Unrealized PnL、Fee/Funding、跨Instrument requirement或Working Order reservation，不写Journal/Ledger，也不决定Available Margin/Liquidation；G09F/G09G拥有这些后续语义。

### Gate G09F Single Execution Account Margin Projection

依赖：G09B、G09E、ReservationBook。

拥有：单 Execution Account、单Venue、单settlement Currency的Derivative Wallet Balance、Unrealized PnL、Equity、聚合Initial/Maintenance Margin、Available Margin和Working Order Margin Reservation。

验收：

- 多Instrument Position、Unrealized PnL与G09E requirements exact coverage并正确聚合；
- Ledger Cash、Realized PnL、Fee/Funding attribution和ResourceReservationState通过immutable authority输入；
- Working Order Margin Reservation只降低Available Margin，不降低Equity；
- 不实现多Currency、多账户或跨Venue collateral netting。

冻结实现 seam：G09F只新增pure `crypto_quant_trading.account_margin`与必要root exports，不新增Port/Profile/Adapter/Package或依赖。Request exact保存Account、Venue、evaluated-at、optional Ledger evidence、G09A Position tuple、VALUATION Mark evidence tuple、G09E Result tuple、optional Reservation evidence、settlement Cash registration和Unrealized PnL quantization。Optional只用于structured missing-evidence failures；Projection不查询Journal、Runtime、provider current account或working Orders。

Ledger evidence保存完整`LedgerState`、`projected_through: SimulationInstant`、`available_at: SimulationInstant`与source key/hash；两者不得晚于evaluated-at，projected-through必须exact等于evaluated-at，Ledger Schema仅允许同Account/Venue authority。Wallet Balance、Realized PnL、Fee与Funding分别使用Ledger settlement Cash key的cash/attribution values；后3项已进入Wallet Cash，只用于audit，Equity不得重复相加。

每个non-flat G09A Position必须exact匹配一个G09E Result和一个VALUATION Mark/Policy；Result exposure等于Position quantity且evaluated-at相同。若entry basis为`a/A`、Mark为`p/P`、signed Quantity为`q/Q`、multiplier为`m/M`，Unrealized exact为`q*m*(p*A-a*P)/(Q*M*P*A)`，GCD约分后每Instrument只调用一次HALF_EVEN映射到settlement Scale。Flat Position不得携带Requirement或Mark；不得使用generic PortfolioSnapshot的spot-style Position market value替代该multiplier-aware derivative formula。

Reservation evidence保存完整`ResourceReservationState`、projected-through/full availability和source identity。Working Order Margin exact只聚合`state.totals.margin`中matching settlement Currency/Scale；任何其他Margin Currency/Scale fail closed，其他commitment dimensions不进入Projection。`Equity = Wallet Balance + Σ Unrealized PnL`；`Available Margin = Equity - Σ Initial Margin - Working Order Margin Reservation`；聚合Maintenance Margin独立保存。Negative Equity或Available Margin是可审计Projection状态，G09G才决定conservative Liquidation。

### Gate G09G Conservative Liquidation Audit

依赖：G09E、G09F。

拥有：Bar粒度下single Account/Venue/Currency的`SAFE`或`AMBIGUOUS_BREACH` conservative classification，以及decision-grade ambiguity fail-closed。

不拥有：伪造精确liquidation time/price、queue、partial liquidation、bankruptcy fill、ADL或provider closeout。

验收：

- Long-low/Short-high adverse extremes下重新计算Unrealized PnL与Maintenance requirement；
- 最不利Bar extremes同时发生仍满足要求时为SAFE；
- 可能突破但Bar内路径未知时为AMBIGUOUS_BREACH；
- decision-grade遇到ambiguity structured fail closed，development-grade保留完整limitation/audit evidence。

冻结实现 seam：G09G只新增pure `crypto_quant_backtest.liquidation_audit`与runtime root exports，结构化实现既有`LiquidationAuditModel`；不得修改Generic Engine/Runner/Timeline、Ledger、G09E/G09F、Resolution或Integrity。Request exact保存optional Account Window Evidence、ordered optional Liquidation Mark Bars、audit-at与existing `RequestedResultGrade`；optional只用于structured missing-evidence failures。

Account Window Evidence嵌入完整G09F Projection、half-open bar start/end、full available-at和source key/hash，证明Projection authority在整个bar interval内无Journal、Fill、Funding、Fee或Reservation mutation。Projection evaluated-at exact等于bar start；window end/availability不晚于audit-at。G09G不读取current Engine/Ledger/Reservation state，也不允许caller用bar结束后的Projection回填历史。

每个non-flat Position必须exact有一个`PricePurpose.LIQUIDATION` closed Mark Bar。Evidence保存Instrument、half-open interval、positive low/high Price、closed-at、完整`available_at: SimulationInstant`、stream/event/revision/source identity；所有Bars interval相同且exact等于Account Window，`low <= high`，Instrument/Currency/Scale匹配Contract。Trade、Execution、Valuation、Margin、Settlement或Funding Bar不得替代。

Long选择low，Short选择high。以G09F Wallet为不变量，按adverse Price重新计算每Position exact/quantized Unrealized PnL；再使用对应G09E Result的resolved historical Interval/Tiers和未量化adverse notional重新选择Tier，按G09E formula/CEILING重算adverse Maintenance。`adverse_equity = wallet + Σ adverse_unrealized`，`adverse_maintenance = Σ adverse_maintenance`。若前者大于等于后者则SAFE，否则AMBIGUOUS_BREACH；Working Order reservation与Available Margin不进入Liquidation threshold。

Development-grade返回两种classification并记录每Position direction/extreme/Tier/exact+Money adverse values、Account totals、limitation和`decision_grade_eligible`。Decision-grade SAFE可返回Result；Decision-grade AMBIGUOUS必须返回`AMBIGUOUS_BREACH_NOT_DECISION_GRADE` Failure，不生成精确trigger或closeout side effect。

### Gate G09H Generic Linear Perpetual Composition

依赖：G09A–G09G。

拥有：Synthetic Linear Perpetual Profile composition、profile-neutral Financial Dispatcher injection、canonical financial artifacts和完整黄金 Fixture。

不拥有：Binance/provider Adapter、真实账户/费用/tier/wallet/margin-mode语义、精确Liquidation、live/deployment或decision-grade qualification。

验收：

- Generic Runner、Timeline、Ledger、Composer和Bar Engine不新增Cash/Linear/Binance derivative条件分支；
- Cash与Linear至少两个实现通过同一Dispatcher interface，Case保存canonical Dispatcher Plan而不保存callback/implementation object；
- 完整Fixture覆盖Long OPEN、partial REDUCE、FLIP to Short、Funding、Long/Short Margin与Long-low/Short-high LiquidationAudit；
- Journal、Generic Ledger、G09B exact Position、G09F MarginProjection和Final PortfolioSnapshot可从immutable authority独立重建；
- Scheduled Account Event exact绑定Timeline Event/availability，Engine只dispatch opaque payload并验证complete artifacts；
- Financial artifacts、Semantic Spec、Identity Manifest、Trace、Journal、Margin、Snapshot和Result在repeat Attempt、batch size与input order间hash parity；
- Profile显式opt-in并标记synthetic/development、`decision_grade_eligible=false`、`deployment_authorized=false`；
- 不包含Binance symbol、fee、rule、wallet、tier或provider Adapter。

冻结实现seam：`ResolvedExecutionCase`新增versioned Financial Dispatch Plan，exact保存Dispatcher Spec、per-Fill opaque accounting payload、ordered Scheduled Account Events、Final Snapshot authority与expected artifact roles。`ResolvedBarExecution`的accounting plan变为profile-neutral，公共字段绑定expected Fill、Position Accounting component、Journal/recorded-at和Fee authority；Engine不得读取payload concrete fields。

`DeterministicBarEngine`执行时必须拥有匹配Case Spec的Financial Dispatcher；无参数构造只创建immutable default Cash dispatcher以保持既有调用兼容，显式`None`/invalid dispatcher拒绝，且不存在inline accounting bypass。Engine只调用`book_fill`、`dispatch_scheduled_event`和`project_final_snapshot`，继续拥有Journal append、Generic Ledger replay、Reservation/Settlement refresh、Trace与Run End；Dispatcher只返回append-only Entries、replacement Cash lot state、ordered typed artifacts或Final Snapshot。Cash dispatcher迁移现有G06/G07行为；Synthetic Linear dispatcher只存在tests/support并组合G09A–G09G。

Synthetic chronology使用single Account/Venue/Currency/Contract：三次deterministic Fill形成Long OPEN → partial REDUCE → FLIP Short；Funding在Long之后、partial close之前，使用G09C historical eligibility和G09D specialized Entry；Long与Short各有G09E/G09F audit，且分别用closed LIQUIDATION Mark Bar执行G09G。Linear Fill不交换principal notional，Fee独立走existing generic path。

状态：PASSED；实现提交`e0f2bc767dc87513d562becd9907262628b788e6`，79项冻结G09H验收、977项完整suite、72文件import boundary与71源文件mypy均通过。

`EngineExecutionResult.financial_artifacts` exact保存role、source Timeline Event/instant、component/request/result identity和完整typed payload，Plan expected roles exact覆盖。Final Snapshot从Final Ledger、Final G09F、VALUATION Mark references与versioned derivative Snapshot Plan构造，realized/fees/financing来自Ledger attribution，unrealized/equity exact等于G09F；禁止generic spot `quantity × mark`估值替代。

---

## 15. G10A–G10H：Binance USD-M Profile

全部子 Gate 使用冻结规则、行情和来源 Fixture；真实 Bundle Builder 属于 G12。

### Gate G10A Instrument Identity and Contract Metadata

状态：PASSED；implementation commit `613c319b2dbba9962d4867dcfb3d1b19067d16cf`已通过Acceptance Matrix G10A frozen validation。

拥有：纯离线`crypto_quant_trading.profiles.binance_usdm.instrument_metadata` Adapter；caller-supplied frozen USDⓈ-M `exchangeInfo` revision evidence → stable Instrument ID、Symbol timeline、linear contract metadata与listing/delisting lifecycle。

不拥有：HTTP/provider client、MarketBundle Builder、current API fallback、tick/step/min-notional、margin tier、price stream、funding、fee/account mode、Liquidation execution、live/deployment或decision-grade provider completeness。

验收：

- Stable lineage key由caller显式提供并进入canonical identity；不得从current `symbol`、`pair`、base/quote拼接、去后缀或rebranding名称猜测Instrument identity；
- 完整Revision exact保存effective/available instant、revision/supersedes identity与source key/hash；`captured_at`只选择已可见closed chain，missing/fork/cycle/late/conflict fail closed；
- Symbol变化更新同一`SymbolTimeline`但不改变Instrument ID；没有显式lineage evidence时old/new contract必须保持不同Instrument；
- 仅支持USDⓈ-M `contractType=PERPETUAL`、base quantity、quote price和quote=margin/settlement currency的Linear scope；COIN-M、delivery futures、quanto或currency conflict structured reject；
- USDⓈ-M不提供COIN-M `contractSize`，Adapter冻结multiplier为exact `1 base quantity per contract`；G10A不从precision字段猜scale；
- `onboardDate`形成listing lower bound；official perpetual sentinel `deliveryDate=4133404800000`映射open-ended，finite visible revision关闭delisting boundary；
- 上市前、finite delivery之后或没有唯一visible metadata时structured failure；退市不删除历史Instrument、Symbol或source evidence；
- `TRADING`才标记普通tradable；其他known Contract status保留为non-tradable provider evidence，reduce-only/no-new-position语义留给G10B；
- `pricePrecision`/`quantityPrecision`不得替代G10B `PRICE_FILTER.tickSize`/`LOT_SIZE.stepSize`；
- Constructor重算revision chain、source hash、InstrumentDefinition、SymbolTimeline、listing interval、contract metadata与result/failure identity；公开对象immutable/canonical/idempotent；
- static Fixture覆盖open-ended BTCUSDT-like perpetual、finite delist revision、symbol lineage、onboard correction visibility、pre-listing/post-delisting、unsupported contract type/status/currency与forgery；
- Production module无filesystem/network/process/database/cloud SDK或wall clock；source acquisition和historical retention由G12拥有。

Primary source note：`docs/research/binance-usdm-instrument-metadata-primary-sources.md`。

G10A纯离线Adapter、source revision/captured-at、stable lineage、Symbol timeline、listing/delisting、Linear currency/multiplier、structured failure、forgery和purity boundaries已由implementation commit `613c319b2dbba9962d4867dcfb3d1b19067d16cf`冻结通过。

### Gate G10B Historical Order Rules

状态：PASSED；implementation commit `11072289a9dda708a185ae2edcbf5fcdf0c7bd55`已通过Acceptance Matrix G10B frozen validation。

依赖：G10A、G05G。

拥有：纯离线`crypto_quant_trading.profiles.binance_usdm.order_rules` Adapter；caller-supplied finite historical Band/RuleBook → style-specific Quantity lattice、Price tick/bounds、MIN_NOTIONAL、admission mode、generic OrderRuleTimeline与OrderCapabilitySet。

不拥有：provider client/JSON parser、current-rule fallback、PERCENT_PRICE mark resolution、open/algo-order account counts、account-mode permission、wire translation、marketTakeBound execution、triggerProtect、fill simulation、Runtime/Bundle Builder、live/deployment。

验收：

- RuleBook exact绑定G10A stable Instrument、finite coverage、half-open Bands、`available_at`、source key/hash；canonical排序后只使用`captured_at`已可见Band；gap、overlap、late-only、source conflict fail closed；
- Band保存raw canonical decimal strings，不用float、global Decimal context、`pricePrecision`或`quantityPrecision`；decimal grammar/scale/overflow、zero step/tick、incompatible min/max和offset geometry structured reject；
- `PRICE_FILTER`映射exact Price Scale、tick、optional min/max；`LOT_SIZE`与`MARKET_LOT_SIZE`分别映射Limit/Market min/max/step，不得合并；
- Generic `OrderRuleSnapshot`增加optional `market_quantity_lattice` schema-v3 extension；字段缺失时既有schema-v1/v2 bytes/hash不变；LIMIT/STOP_LIMIT与MARKET/STOP按style选择对应lattice/cap/notional/position evidence；
- 两条quantity lattice共享Instrument、atomic Scale、quote currency和MIN_NOTIONAL authority；G10B输出price/quantity scales供G10G组合G09A contract；
- `MIN_NOTIONAL`按exact `price × quantity`评估；Market/Stop必须由后续G10D/G10G提供MARK_PRICE purpose evidence，不得使用Trade/Bar Close/Valuation/current fallback；
- Provider order types/TIF source集合完整进入identity；v1 generic capability至少资格化LIMIT与MARKET、Limit GTC/IOC/FOK/GTX intersection及reduce-only support；unknown values fail closed，GTD/RPI/trailing/close-all等显式defer；
- Admission mode exact为NORMAL/REDUCE_ONLY/CLOSED；REDUCE_ONLY只允许CLOSE且要求`reduce_only=true`，CLOSED和G10A non-tradable status不得产生普通admission；Hedge/One-way compatibility留给G10F；
- `PERCENT_PRICE`、MAX_NUM_ORDERS、MAX_NUM_ALGO_ORDERS、marketTakeBound、triggerProtect和advanced order capability必须进入known deferred keys；未解析时`decision_grade_eligible=false`，unknown/omitted key不允许静默成功；
- Tick transition前已获批Order保留原MarketRuleDecision和interval hash；新Band只约束transition后新admission，temporary suspension需显式source evidence；
- Constructor重算RuleBook/Query/Resolution/Failure、generic Snapshot/Timeline/Capability identities，伪造active Band、lattice、scale、cap、admission、deferred keys或source coverage拒绝；
- static Fixture覆盖independent Limit/Market geometry、MIN_NOTIONAL、tick transition、one-minute suspension、reduce-only window、gap/overlap/late evidence、unknown capability/deferred key、forgery与legacy snapshot/evaluator hash compatibility；
- Production module无filesystem/network/process/database/cloud SDK/wall clock，不修改Generic Engine/Runner增加Binance branch。

Primary source note：`docs/research/binance-usdm-order-rules-primary-sources.md`。

G10B generic schema-v3 style lattice extension、historical source Band/RuleBook、decimal/filter geometry、Admission Mode、Capability/Deferred evidence、failure precedence、golden与purity boundaries已由implementation commit `11072289a9dda708a185ae2edcbf5fcdf0c7bd55`冻结通过。

### Gate G10C Historical Margin and Leverage Tiers

状态：PASSED；implementation commit `50fa838f901385498ce18d65a897d4eb1dc31337`已通过Acceptance Matrix G10C frozen validation。

依赖：G10A、G09E。

拥有：Binance historical margin/leverage tier Adapter，以及G09E backward-compatible finite-cap/upper-inclusive generic extension。

验收：

- 只消费caller-supplied immutable archived Contract Info bracket-update Bands、G10A Resolution与time inputs；不发HTTP、不读file/database/wall clock、不调用authenticated current bracket endpoint；
- raw `bs/bnf/bnc/mmr/cf/mi/ma` canonical decimal/source evidence全部进入identity；`bnf/bnc`映射exact settlement Money，`ma`映射maximum leverage，`mmr`映射maintenance rate，`cf`映射maintenance deduction；
- `mi`只保留为provider leverage-range evidence，不成为minimum selected account leverage；selected leverage仍由G10F提供`LinearMarginLeverageEvidence`；
- Generic `LinearMarginRuleInterval`增加backward-compatible boundary convention：既有lower-inclusive/upper-exclusive schema-v1 bytes/hash不变；Binance使用zero-degenerate first tier及lower-exclusive/upper-inclusive positive-notional bracket；
- Binance final `bnc`保持finite terminal cap；exact shared cap归前一tier，超过terminal cap返回structured outside-tier-coverage failure，不改成unbounded、不fallback；
- RuleBook绑定stable G10A Instrument、finite coverage、half-open economic Bands、`available_at`、revision/source lineage；只使用`captured_at`已可见Band，gap、overlap、late-only、source conflict或current/latest回填历史fail closed；
- decimal grammar、Scale、positive integral bracket/leverage、strict bracket order、contiguous floors/caps、nonnegative rate/deduction及Currency/Basis exact验证，不使用float或ambient Decimal context；
- authenticated/account-adjusted source或任何`notionalCoef` structured reject；G10C v1不解释、乘算或跨Account共享该字段；
- Resolution输出完整generic historical `LinearMarginRuleBook`和provider source evidence，但不创建account leverage、Margin Result、Mark、Wallet、Liquidation或Runtime composition；
- static Fixture覆盖upper-inclusive shared boundary、finite terminal cap/overflow、tier update before/at/after、late evidence、gap/overlap、malformed decimal、`cf`、`mi/ma`、notionalCoef rejection、forgery、input-order parity与legacy G09E hash compatibility；
- Production module无filesystem/network/process/database/cloud SDK/wall clock，不修改Generic Engine/Runner增加Binance branch；仅development-grade，G12 archive completeness前不得decision-grade。

Primary source note：`docs/research/binance-usdm-margin-tiers-primary-sources.md`。

G10C generic schema-v2 boundary convention、finite terminal coverage、historical source Band/RuleBook、exact bracket mapping、failure precedence、golden与purity boundaries已由implementation commit `50fa838f901385498ce18d65a897d4eb1dc31337`冻结通过。

### Gate G10D Price Purpose Streams

依赖：G10A、MarkResolver。

拥有：纯离线`crypto_quant_trading.profiles.binance_usdm.price_streams` Adapter；caller-supplied immutable USDⓈ-M aggregate-trade与closed mark-price-kline evidence → purpose-specific generic `MarkObservation`、resolved point Mark及provider liquidation Mark Bar。Settlement mapping由本Gate显式fail closed；Funding Mark source仍由G10E拥有。

不拥有：provider client/JSON/CSV/ZIP parser、current endpoint fallback、archive completeness、Bar Builder、Fill/Order Book simulation、Funding Slot、final settlement price acquisition、Runtime/Profile composition、live/deployment。

验收：

- Accepted mapping exact为aggregate-trade `p@T`→`EXECUTION_REFERENCE`；closed mark-price-kline close→分别独立的`VALUATION`与`MARGIN` point streams；同一closed mark-price-kline close及low/high→`LIQUIDATION` point/bar evidence。共享raw row不共享PricePurpose identity，Trade/contract-kline close/index/estimated-settlement不得替代Mark；
- Contract kline open不得按bucket start冒充已知execution reference；G10D v1只用aggregate trade作为execution-reference source。Book ticker保留outside scope，不冒充trade或fill；
- Provider trade time、bar open/close time、interval end-exclusive、closed-at、available-at与captured-at分离。Aggregate trade `available_at >= T`；final Mark Bar `closed_at.instant = close_time + 1ms`且`available_at >= closed_at`；只靠same-UTC phase/sequence表达的late availability因generic point Mark无法无损表示而structured fail closed；
- Point selection exact委托既有provider-neutral `MarkResolver`与purpose-specific `StaleMarkPolicy`；availability、ambiguity、forward-fill与maximum age不在Binance Adapter复制实现。Liquidation OHLC coverage独立验证且不得point forward-fill；
- `P` estimated settlement price、index price `i`、moving-average mark `ap`、ordinary mark/contract close均不能创建`SETTLEMENT` Mark。G10D v1 settlement query返回structured unsupported failure，直到first-party immutable final-settlement-price source另行冻结；
- Funding Rate History关联mark属于G10E；G10D不得从nearby mark kline或Mark Price Stream制造`FUNDING` Mark；
- Historical Price Book按每个purpose保存finite half-open coverage、source kind/key/hash、event/revision lineage与raw canonical decimal/timestamp evidence；visible evidence只允许`available_at <= captured_at`，gap、overlap、duplicate visible natural ID、cross-Instrument、late-only或current/latest fallback fail closed；
- Decimal只用canonical ordinary string与integer arithmetic；raw trailing zeros进入source identity，mapped Price使用smallest exact required Scale，不用float、ambient Decimal context或precision hint；
- Model digest exact包含固定purpose→source mapping、schema与limitations；任何mapping变化都改变G10D model digest，并由G10G纳入最终Profile digest。G10D不新增会迫使现有Market Profile exact-cover的generic `ProfilePortType`；
- Resolution固定`decision_grade_eligible=false`，直到G12证明source archive initial state、all files/checksums/revisions及gap classification coverage；
- static Fixture覆盖execution/valuation/margin/liquidation mapping、same raw Mark row的purpose separation、before/at/after availability、staleness、duplicate same-time ambiguity、liquidation interval coverage、contract-kline-open lookahead rejection、settlement/funding/index/estimated-settlement rejection、malformed decimal/timing/source conflict、forgery与input-order parity；
- Production module无filesystem/network/process/database/cloud SDK/wall clock，不修改Generic MarkResolver、Engine、Runner、Ledger、Snapshot、Margin或Liquidation Audit增加Binance branch。

Primary source note：`docs/research/binance-usdm-price-purpose-streams-primary-sources.md`。

G10D fixed purpose mapping、point-in-time availability、generic MarkResolver delegation、Liquidation OHLC coverage、unsupported Settlement/G10E-owned Funding、model digest、golden与purity boundaries已由implementation commit `790469d80ddcf3797f03c96c975b77d75a3d49a5`冻结通过。

### Gate G10E Funding Source Semantics

依赖：G09C、G09D、G10D。

拥有：Binance Funding publication time、settlement time、applied rate、associated mark 和 Slot ID Adapter。

验收：

- Production只消费caller-supplied immutable G10A Resolution、完整G09A Contract、G09D Application Key、finite Historical Funding Book、target Funding UTC与capture instant；不得调用REST/WebSocket、解析provider文件、读取filesystem/wall clock或用current endpoint补历史；
- accepted v1 source exact为USDⓈ-M Funding Rate History `GET /fapi/v1/fundingRate` row；`fundingTime`是Slot/effective UTC，`fundingRate`是直接applied fraction，`markPrice`是该funding-fee charge关联Mark；
- `FundingSlotId`只由stable Instrument与exact `fundingTime`派生，不假设8h cadence、不从`fundingIntervalHours`或邻近row推断missing slot；
- 只接受exact一个visible immutable `Regular` row。`Special` additional funding、missing/unknown rate type、same-slot duplicate、superseding revision或conflicting bytes structured fail closed，不sum/net或改写G09C Slot identity；
- Mark Price Stream `r/T`、REST `lastFundingRate/nextFundingTime`、Funding Info cap/floor/interval、interest/premium formula不得替代或重算historical final rate；
- same row的associated `markPrice`唯一映射`PricePurpose.FUNDING`；nearby G10D Mark Kline、ordinary mark update、index、moving-average mark、estimated settlement、trade或last price均不得fallback；
- Funding Mark使用frozen zero-age、zero-max-age、no-forward-fill StaleMarkPolicy，并通过generic MarkResolver；raw Mark必须positive且exact representable at supplied G09A Contract price Scale，不round、不pre-quantize；
- provider只给millisecond UTC；simulation convention冻结为target UTC `TimelinePhase(110,"funding_settlement")/SourceSequence(0)`，位于G09C eligibility phase 100之后。Publication availability与G09D `applied_at`使用该instant，archive captured-at独立保存；
- exact raw decimal保留trailing zeros/source identity；Rate允许signed/zero ordinary decimal，Mark只允许positive ordinary decimal；mapping只用string/integer arithmetic，不用float、ambient Decimal或precision hint；
- Resolution直接产生derived Slot、G09C final-rate Publication Candidate、G09D Funding Mark Evidence与绑定caller Application Key的Settlement Evidence；不拥有Position snapshot、Eligibility resolution、cash-flow calculation、Journal append或Ledger mutation；
- Query/G10A effective/capture、Contract Instrument/Currency/Scale、Application Key account/Slot、Coverage、source event/revision与natural slot identity必须exact匹配；tuple order不得选winner；
- model digest exact包含accepted source、Regular-only policy、fixed phase/sequence、rate basis、associated-mark-only policy、revision policy、decimal/scale rules与limitations，G10G必须纳入final Profile digest；
- static Fixture覆盖positive/negative/zero Rate、exact associated Mark、dynamic/non-8h target times、before/at/after archive capture、missing rate/mark/type、Special、duplicate/conflict/supersession、coverage gap/overlap、current/predicted source rejection、inexact Mark Scale、forgery与input-order parity；
- G12证明funding archive initial state、all files/checksums/revisions与slot-gap classification前，Resolution固定`decision_grade_eligible=false`；
- Production module无filesystem/network/process/database/cloud SDK/wall clock，不修改G09C、G09D、MarkResolver、Journal、Ledger、Engine、Runner或Timeline增加Binance branch。

Primary source note：`docs/research/binance-usdm-funding-source-semantics-primary-sources.md`。

G10E Funding Rate History Regular-only source、stable Slot、fixed post-eligibility settlement instant、direct Rate、same-row Funding Mark、G09C/G09D evidence、failure precedence、golden与purity boundaries已由implementation commit `195265b1ed830e62b91882ff315b115e7ac80597`冻结通过。

### Gate G10F Fee and Account Profile

依赖：G05H、G05J、G09F、G10A。

拥有：historical account-specific maker/taker fee timeline、cross/single-asset/one-way account mode、selected leverage evidence和USDT Reporting Currency约束。

验收：

- Production只消费caller-supplied immutable G10A Resolution、Account ID、finite Historical Account Profile Book、evaluated/captured instant与requested Reporting Currency；不得调用authenticated current API、解析provider payload、读取filesystem/wall clock或用current Account/Symbol/Commission response补历史；
- 一个Profile Band exact保存account/symbol/commission/feeBurn四类first-party snapshot的独立source/revision lineage、finite half-open effective interval与full available-at；Book必须canonical-sort并exact-cover请求窗口；
- account-specific per-symbol `makerCommissionRate`/`takerCommissionRate`是Fee authority；`feeTier`只保留raw evidence，不从VIP公开表、announcement、tradeGroup或neighboring symbol推导rate；
- accepted v1 account exact为`canTrade=true`、standard UM scope、One-way (`dualSidePosition=false`)、Single-Asset (`multiAssetsMargin=false`)、`CROSSED`、`isAutoAddMargin=false`、`feeBurn=false`；Hedge、Multi-Assets、isolated、auto-add、Portfolio Margin或BNB fee discount structured fail closed；
- selected positive integral leverage direct映射G09E `LinearMarginLeverageEvidence` basis `notional_per_initial_margin`，effective/available interval来自Band；不得使用G10C `ma/mi/initialLeverage`、current Symbol Config、`maxNotionalValue`或neighboring symbol替代selected leverage；
- Commission Rate允许non-negative ordinary decimal与zero。Negative maker rebate/LP program不clip为zero、不写negative fee，v1 structured unsupported；raw trailing zeros进入source identity；
- Fee currency、G10A quote/settlement Currency和requested Reporting Currency必须exact `USDT`；固定Fee Scale 8，不为USDC/BUSD/BNB建立隐式peg、FX或stablecoin conversion；
- `AccountFeeScheduleRef` digest绑定Account/Instrument、maker/taker、feeTier、feeBurn、mode、source revisions、Currency/Scale与quantization；Reservation与Final Rule Set exact共享该Ref；
- Fee Reservation Rule Set显式包含market-fee/tax `ORDER_NOTIONAL+NOT_APPLICABLE+zero rate`及account-schedule `ORDER_NOTIONAL+APPLIES` rule，account rate exact为`max(maker,taker)`且USDT Scale 8 `CEILING`；zero-rate N/A形式保持generic Estimator可执行，不得按可能Fill数重复预留；
- Final Fee Rule Set显式包含market-fee/tax `FILL+NOTIONAL_RATE+NOT_APPLICABLE+zero rate`及separate account-schedule maker-only/taker-only per-Fill notional rules，USDT Scale 8 `TOWARD_ZERO`。Zero-rate N/A形式保持generic Engine可执行；Fill liquidity role与actual price×quantity仍由generic FeeAssessmentEngine拥有；
- final fee rounding是development convention，G10H必须与archived Account Trade List `commission/commissionAsset/maker`逐Fill parity后才能升级；G10F不把actual historical commission amount作为未来synthetic Fill fee；
- Resolution保存active Band、selected leverage、Leverage Evidence、AccountFeeScheduleRef、Reservation/Final Rule Sets、normalized mode、Reporting/Fee Currency、`FeeReserveFundingSource.AVAILABLE_MARGIN`、limitations与`decision_grade_eligible=false`；
- G10F不创建完整`AccountRiskPolicy`：order capacity/exposure limits、G10B deferred counts、G09F available margin与capability intersection由G10G组合；不映射Wallet/Ledger state；
- failure precedence、constructor/hash forgery、source conflict、input-order parity、before/at/after update、fee/leverage/mode transitions、all unsupported modes与negative rebate均由static source/golden冻结；
- G12证明account initial state、all config/commission/leverage/feeBurn revisions与coverage前固定development-grade；Production module不修改generic Fee Estimator/Engine、Margin、Account Margin、PreTradeRisk、Journal、Ledger、Engine、Runner或Timeline增加Binance branch。

Primary source note：`docs/research/binance-usdm-fee-account-profile-primary-sources.md`。

G10F Historical Account Profile Book、normalized mode、selected Leverage Evidence、shared Account Fee Schedule、Reservation/Final Rule Sets、18项failure precedence、static golden与purity boundaries已由implementation commit `07cc15823ec3790b0491220f248a64c334e3a81b`冻结通过。

### Gate G10G Binance Profile Composition

依赖：G10A–G10F、G09H。

拥有：`crypto.binance_usdm.v1`、`binance.usdm.standard-cross.v1`和`bar.next_eligible_open.conservative.v1`的development-only ResolvedEnvironment composition、single-instrument `AccountRiskPolicy`、Financial Dispatcher Spec与完整Binance Journey Fixture。

验收：

- Production composition只消费caller-supplied immutable G10A–G10F successful Resolutions、finite Timeline Window、composition instant与matching historical Account Capacity Evidence；不重新查询provider/current state、不构建MarketBundle、不修改G10 source facts；
- G10A Instrument/multiplier与G10B exact price/quantity Scales组成G09A Contract；不得使用precision hints、display decimals或Mark decimals；
- Required Price Purpose exact为Execution Reference、Valuation、Margin、Liquidation各一个G10D Resolution；Funding只来自G10E，Settlement unsupported，Purpose之间不fallback；
- G10B active deferred set只允许MAX_NUM_ORDERS/MAX_NUM_ALGO_ORDERS且必须由matching Account Capacity Evidence完成；Result同时保存source deferred与composed resolved keys。其他deferred rule structured unsupported；generic单order-cap exact保守取两个provider limits的minimum，不扩大Binance split limits；
- Exposure cap exact取G10F selected-leverage `maxNotionalValue`与G10C finite terminal tier coverage的USDT minimum；G09F current exposure/Available Margin和Reservation继续作为generic PreTradeRisk runtime state，不进入static Policy；
- `AccountRiskPolicy`从G10B allowed sides/effects/reduce-only、G10F `AVAILABLE_MARGIN` fee source、order/exposure caps组成；NORMAL与REDUCE_ONLY exact区分，CLOSED不产生executable Profile；
- Market Profile exact-cover全部Profile ports；Simulation exact-cover全部Simulation ports。No Tax/Corporate Action/automatic Settlement与single-USDT valuation均使用explicit versioned component，不用`None`；
- Profile digest exact绑定all G10 model/resolution hashes、Contract、Risk Policy、Price/Funding coverage、component manifests、simulation conventions、Dispatcher Spec和limitations；任一输入变化必须改变identity；
- ProfileResolver对matching Bundle/Build/Request成功；wrong Venue/Account/Currency/capability/build/profile/grade沿generic compatibility checks失败。Market capabilities至少包含bar-open、account financial-event、Binance price-purpose streams与funding publications；
- Financial Dispatcher Spec固定`crypto.binance_usdm.linear-financial-dispatch.v1`。Engine Case只保存Spec/plans/payloads，不保存implementation object、callback、module path、runtime address、Attempt ID或wall clock；
- Test-support Binance dispatcher通过同一G09H branchless seam产生Long OPEN→partial REDUCE→FLIP Short、G10E Funding、G10F maker/taker Fee、G10C/G10F Margin、G10D Long-low/Short-high Liquidation Audit与Final Snapshot；
- Final Journal→Generic Ledger、specialized Journal→G09B Position、Ledger+provider evidence→G09F Projection、Ledger+Projection→Snapshot四条重建路径与Engine exact parity；
- Binance Fixture与A股/Synthetic Fixture共享ProfileResolver、Runner、OrderEventStream、Reservation/Settlement、Journal、Ledger、Timeline、Engine和Composer接口；Generic modules不得增加Binance import/name branch；
- Production module纯offline且不import Engine/Runner/MarketBundle Reader；test dispatcher不读取network/filesystem/provider current state。G12 archive completeness与G10H Account Trade/matching-engine/liquidation parity前固定development-only、`decision_grade_eligible=false`、`deployment_authorized=false`。

G10G pure composition authority、three profile registrations、conservative AccountRiskPolicy、FinancialDispatcherSpec、development Journey、Runner repeatability与static goldens已由implementation commit `12286dbf6b7289fcb2f6069c46fc648d8f5a5be0`冻结通过。

Primary source and composition convention note：`docs/research/binance-usdm-profile-composition-primary-sources.md`。

### Gate G10H Binance USDⓈ-M Layered Parity

依赖：G10G、WP-00C。

拥有：固定`crypt-gemini` Source Snapshot、caller-supplied canonical Binance account-record projection、existing Comparator Contract v1调用、13-layer coverage与first-divergence composite Parity Report。G10H是pure offline parity tooling，不是第二套exchange simulator或provider acquisition gate。

验收：

- Legacy identity exact固定archive SHA-256 `d6e6feca46b61586e890a441443738dc9e911a58428c940e86055459361eda80`与content-tree SHA-256 `704dee87020ad119e417fbec3831875f8203787ba06206f625a07e2414a068bb`；Dirty workspace provenance不作为identity，tool也不执行archive code；
- comparison pairs固定`LEGACY_TO_G10G`、`BINANCE_TO_G10G`。Layer order固定Source Identity、Decision、Order Intent、Order Event、Fill、Fee、Position/PnL、Funding、Journal/Ledger、Margin/Snapshot、Liquidation Audit、Liquidation Execution、Final Result；后续aggregate match不能掩盖较早divergence；
- 每个pair exact-cover全部layers，每层显式`COMPARABLE`或具体`NOT_COMPARABLE_*` reason。Missing legacy scope、missing provider evidence或G12 archive completeness未证明时不能伪装成Match、zero、tolerance或silent omission；
- 只复用WP-00C Comparator Contract v1。Exact、sequence、quantized、explicit tolerance和approved change全部path-local；global epsilon与unclassified field继续禁止；
- Intentional semantic change只引用committed `docs/adr/0001-g10h-legacy-binance-parity-boundary.md`。Legacy long-only/next-open/fixed-cost shortcuts与G10G open-reduce-flip/provider semantics的差异必须可见，不能为追求Match重写；
- Binance Account Trade按Account+Instrument+Trade ID保存per-Fill price/quantity/maker/commission/realized PnL；Income History只作linked cash-flow cross-check，不能double-book；Order/User Data event、economic、capture与availability times保持分离；`ACCOUNT_UPDATE.bc`不能冒充含PnL/commission的总cash delta；
- User Force Orders区分Liquidation与ADL。Conservative bar-extreme Audit只能比较detection/classification，不能冒充actual trigger/fill/bankruptcy/insurance execution；public liquidation stream不作complete user archive；
- CLI在completed `MISMATCH`或`APPROVED_CHANGE`仍生成canonical report并exit 0；invalid/blocked非零。Passing gate证明报告真实可重复，不要求经济Verdict为Match；
- Static provider fixture仅为pseudonymous first-party-schema example，并显式archive completeness未证明。G12前全部report固定`decision_grade_eligible=false`、`deployment_authorized=false`；
- Tool只import stdlib与existing parity helpers，不import Engine/Runner/concrete Profile/provider SDK/network/secrets/database/process。G10G projection由tests/support预先生成fixture，Parity runtime不执行Backtest。

Primary-source and parity boundary：`docs/research/binance-usdm-parity-primary-sources.md`。

G10H layered parity tooling、strict plan/source/coverage validation、two pair reports、root-independent static golden与first-divergence aggregate已由implementation commit `468c91ad3fdbad221c959182f8751300f20a2424`冻结通过。Frozen composite verdict为`APPROVED_CHANGE`：Legacy→G10G有11项ADR-backed approved changes，provider-record→G10G有8项exact matches；archive coverage仍不完整，全部资格标志保持false。

---

## 16. G11A–G11J：Portfolio Strategy Runtime

G11 active plan authority、dependency DAG、Ready queue与per-Gate links已迁移到：

- `docs/implementation/plans/g11/README.md`

G11A–G11J均已冻结通过；G11I implementation commit为`43735440ca5c60e2b3ae9c536c4a77411db317d0`，G11J implementation commit为`7387c0b667d6af29d82fd0e0a046d45a3387956d`。其详细contract与证据由Acceptance Matrix、G11 research authority和拆分后的Gate plan拥有；本聚合文件不再复制per-Gate prose。

---

## 17. G12A–G12M：真实 MarketBundle 与 Decision-grade Qualification

Builder 是允许访问网络/供应商文件的独立写侧工具；Backtest Runtime 在全部 G12 Gate 中仍保持离线只读。

### Gate G12A SourceSnapshot Contract

Detailed plan：[`docs/implementation/plans/g12/g12a.md`](plans/g12/g12a.md)。

Acceptance and status authority：[`docs/implementation/acceptance-matrix.md`](acceptance-matrix.md)。

### Gate G12B Canonical Normalization

依赖：G12A、`trading-domain`、`market-data-contracts`。

拥有：SourceSnapshot → canonical Instrument/UtcInstant/PricePurpose/Revision/Rule/CorporateAction records。

验收：

- Normalizer 不读取 Trading Kernel 私有状态；
- Source record 与 canonical record provenance 可双向追踪；
- 时区、Scale、Instrument mapping 和 revision rules 显式；
- normalization code/config identity 进入 manifest。

### Gate G12C Bundle Validation and Manifest

依赖：G12B。

拥有：Schema、capability、partition、event count/hash 和 provenance validation。

验收：

- Validation 完成前不能发布 Bundle；
- Manifest 覆盖全部 partition 和 stream hashes；
- 重复、倒序和无法分类记录 fail closed；
- Bundle capability 与实际内容一致。

### Gate G12D Atomic Publishing and Repository

依赖：G12C、`market-data-contracts` repository contract。

拥有：content-addressed path、atomic publish、immutability、retention 和 concurrent deduplication。

验收：

- 旧 Bundle 永不原地覆盖；
- 相同内容并发发布只形成一个 canonical identity；
- publish failure 不留下可读取的半成品；
- Retention Policy 可以验证 Rebuildability。

### Gate G12E Local Persisted Reader

依赖：G12D、G06A Reader contract。

拥有：对 G12D manifest-bound canonical stream payload 的完整本地验证，以及 bounded batch Reader Adapter。

验收：

- 不暴露 DataFrame 给 Strategy；
- Cursor 支持规范事件顺序和有界读取；
- Runtime 不加载 Source Adapter；
- corrupted publication/stream/hash mismatch fail closed；
- Parquet/Arrow 与 memory-map representation 延后到独立 hashed representation contract。

### Gate G12F Reader and Partition Parity

依赖：G12E、G07 Auditable Runner。

验收：

- InMemory vs Local persisted Reader event sequence exact parity；
- logical stream partition、Reader batch size 和 Timeline batch size 不改变 execution result hash；
- first divergence 可定位到 stream/logical partition/event；
- 性能优化不改变 canonical ordering；
- future Parquet/Arrow physical partition parity 必须先有 separately hashed representation manifest。

### Gate G12G Bar Aggregation

依赖：G12B、G12C。

拥有：BarDefinition、Session anchor、TradingDate、included phases、empty interval policy 和 BarAggregationManifest。

验收：

- A 股午休、Crypto UTC day 和未来夜盘规则按 Session 聚合；
- Strategy 不需要自行 Resample；
- source/definition/code/output hashes 完整；
- BarDefinition 变化产生新 Bundle identity。

### Gate G12H Rule Coverage

依赖：G12C、MarketSemanticsProfile required dimensions。

拥有：RuleCoverageReport。

验收：

- 每个 required dimension 有完整有效区间；
- 无缺口、无重叠且唯一解析；
- source identity 完整；
- 缺失时在 Engine 启动前产生结构化阻断。

### Gate G12I Price, Availability and Revision Coverage

依赖：G12C、G12G。

拥有：PriceStreamCoverageReport、MarketAvailabilityReport 和 RevisionProvenanceReport。

验收：

- 每个 PricePurpose 独立覆盖；
- Gap 分类为 non-session/suspension/no-trade/data-missing/source-failure；
- StaleMarkPolicy max-age 可验证；
- Execution 禁止 forward-fill；
- Vendor correction 保留旧 Revision。

### Gate G12J First Real Schema Migration

只在存在真实 immutable 旧 Artifact 时实施。

拥有：明确 source/target Schema 之间的纯单向 Migration、Migration Manifest 和 migration code identity。

验收：

- 不构造虚假旧版本；
- 原始 Artifact 和 source hash 永远保留；
- Migration 只改变结构表达，不重新解释经济语义；
- Canonical View 可重复生成且记录完整 migration chain；
- 若不存在真实旧版本，本 Gate 保持未启动。

### Gate G12K Universe and Corporate Action Coverage

依赖：G12C。

拥有：UniverseCoverageReport 和 CorporateAction lifecycle coverage。

验收：

- Listing/delisting/membership point-in-time 完整；
- Announcement/Record/Effective/Payment 证据完整；
- StaticUniverse 明确标记；
- unsupported action 对受影响运行 fail closed。

### Gate G12L Market Source Adapter Slice

每个真实供应商或来源独立一个子 Gate，例如：

```text
G12L-BINANCE-001
G12L-CN-EQUITY-001
```

验收：

- 一个 PR 只包含一个 Source Adapter；
- Source-specific mapping 只存在 Builder；
- SourceSnapshot、Normalization、Coverage 和 Reader Fixture 完整；
- Provider schema change 有明确失败和版本策略；
- 两个供应商不得合并为一个 Adapter Gate。

### Gate G12M Per-market Decision-grade Qualification

每个市场/Profile 独立执行，不共享通过状态。

验收：

- immutable real MarketBundle；
- required rule/price/availability/revision/universe/corporate-action coverage 完整；
- immutable BuildArtifactManifest；
- full trace evidence；
- Simulation/Profile applicability 未越界；
- parity/integrity blocking issue 为空；
- Bundle 在 Retention Policy 下可取回和重建；
- Decision-grade 结果仍保持 `deployment_authorized=false`。

---

## 18. 每个 PR 的大小约束

为避免重新形成“大任务”，建议：

- 一个 PR 只完成一个 WP，最多包含同一接口下不可分割的两个小 WP；
- 一个 PR 最多引入一个新的 external seam；内部实现可以有私有 seam，但不得同时扩张多个 caller-facing Interface；
- 一个 PR 不同时新增领域契约、Runtime orchestration 和市场 Profile；
- 新市场能力先有 failing Fixture，再实现 Profile component；
- 任何临时分支必须通过显式 development-only Profile 标识，不能成为默认；
- 不为后续 Gate 提前加入未测试抽象；
- 一个 Gate 通过后创建 Git tag 或不可变基线 commit，后续 parity 以其为固定点。

## 19. 第一轮建议执行顺序

以下是路线，不是一次性授权的任务批次：

```text
G00: WP-00A → WP-00B → WP-00C → review
G01: WP-01A → WP-01B → WP-01C → WP-01D → review
G02: WP-02A → WP-02B → WP-02C → WP-02D → WP-02E → WP-02F → WP-02G → WP-02H → review
G03: WP-03A → WP-03B → WP-03C → WP-03D → WP-03E → WP-03F → review
```

G00 与 G01 已通过验收；Workspace、Dependency Boundary、Legacy Baseline、Typed Scaled Integer、权威时间、确定性 ID 和 Canonical Hash 均已有不可变实现基线。用户已授权按 Gate 顺序持续推进；Agent 可以在每个 WP 的 Acceptance Card 达到 `READY` 后直接实施、验收和提交，不再逐项等待确认。任何测试、Parity、Boundary 或 Evidence 失败仍必须先停止并修复；外部供应商、真实数据或不可逆市场语义未被现有文档决定时必须明确阻断，不能自行猜测。

到 G03 再做一次 Foundation Release Review：

- 类型是否足够稳定；
- Ledger 是否真正可 replay；
- package 边界是否保持；
- `crypto-quant-core` 哪些内容可以通过 parity 迁移。

评审通过后才进入 Target、Order 和 Runtime。这样不会在基础数值或 Accounting 尚未稳定时堆叠完整回测系统。

## 20. 完成定义

“Target-driven Bar v1 完成”不是某个命令能运行，而是至少通过 G00–G10：

- G00–G07：通用、可审计的 development-grade Bar Runtime；
- G08A–G08H：A 股 Profile；
- G09A–G09H、G10A–G10H：Binance USD-M Profile；
- G11A–G11J：Strategy Runtime，可独立后置；
- G12A–G12M：真实数据和逐市场 decision-grade 资格，可独立后置。

因此可以分别发布：

1. `domain-ledger-foundation`（G00–G03）
2. `target-to-order-kernel`（G04–G05）
3. `synthetic-bar-runtime`（G06–G07）
4. `cn-a-share-profile`（G08A–G08H）
5. `binance-usdm-profile`（G09A–G09H、G10A–G10H）
6. `portfolio-strategy-runtime`（G11A–G11J）
7. `real-bundle-decision-grade`（G12A–G12M，逐市场发布）

每个发布点都有独立价值、明确边界和停止条件。
