# 跨市场回测系统架构设计

- 状态：Draft
- 版本：0.1
- 日期：2026-08-02
- 适用范围：加密货币、A 股及后续其他交易市场
- 目标项目：`crypto-quant-*` 系列项目

## 1. 背景

现有 `crypt-gemini` 同时包含市场数据、策略研究、多个回测实现、Hummingbot 适配、实盘状态和部署逻辑。随着策略、市场和执行模型增加，回测语义散落在不同研究目录中，容易出现以下问题：

- 同一策略在研究、回测和实时执行中存在多套实现。
- 手续费、Funding、滑点、持仓和盈亏核算口径不一致。
- 防未来数据依赖局部约定，缺少统一时间模型。
- Binance、A 股、期货等市场规则容易进入回测主循环形成条件分支。
- 简单 Bar 回测与 L1/L2 微观结构回放被迫共享不合适的内部模型。
- 回测结果缺少统一、可重建、可审计的证据契约。

本设计将回测系统作为整个交易系统中的独立深模块，通过较小的外部接口隐藏时间推进、市场规则、成交模拟、结算和账户核算等复杂行为。

## 2. 目标

### 2.1 功能目标

回测系统应支持：

1. 组合型中低频 Bar 回测。
2. 加密现货和永续合约。
3. A 股日频及分钟级策略。
4. 后续扩展至美股、期货、期权和其他交易场所。
5. 策略、组合风险与实时执行逻辑复用。
6. 可替换的历史市场和模拟执行 Adapter。
7. 确定性运行、完整 trace、结果 hash 和证据归档。
8. 明确区分 development、decision-grade 和 deployment authorization。

### 2.2 架构目标

- 回测主循环不包含 `if market == "crypto"` 一类市场分支。
- Portfolio Strategy 输出目标；Liquidity/Execution Strategy 输出 venue-neutral Order Intent。两者都不生成交易所或 Hummingbot 专用命令。
- 真实市场差异通过 `MarketSemanticsProfile` 表达，回测近似通过独立 `SimulationProfile` 表达。
- Accounting 是回测账户状态和 PnL 的唯一权威实现。
- Bar Engine 与 Microstructure Replay Engine 共用领域契约，但不强行共用内部撮合实现。
- 历史运行与实时运行尽可能共用 Strategy、Portfolio/Risk 和 Order Planning 模块。
- 接口同时作为调用面和测试面。

## 3. 非目标

第一阶段不追求：

- 一次性完整支持所有交易所和资产类型。
- 在一次 Backtest Run 中同时交易多个 MarketSemanticsProfile 或 Execution Account。
- 跨账户资金转移、跨币种 FX 估值和 Consolidated Portfolio。
- 使用一个万能引擎统一 Bar 回测和逐笔订单簿回放。
- 在 Backtest Runtime 内部实现策略训练、参数搜索、候选选择和实验管理。
- 由回测结果自动授权 Shadow 或 Live。
- 为尚不存在的市场提前设计大量抽象。
- 在 Bar Engine v1 中实现任意中途恢复或原地续跑。
- 把 Hummingbot 作为领域模型的一部分。

## 4. 核心原则

### 4.1 统一语义，不统一所有实现

系统统一：

- 时间语义
- 市场事件
- 策略决策
- 组合目标
- 订单
- 成交
- 账户账本
- 回测结果
- 审计证据

系统不强制统一：

- Bar 成交模型与 L2 撮合实现
- 不同市场的结算方式
- 不同资产类型的融资和公司行为

### 4.2 两类策略契约

系统承认两类具有不同输出语义的策略，避免用目标仓位强行表达做市和队列管理。

```text
Portfolio Strategies
    → Atomic DecisionBatch(StrategyDecisions) ─────┐
                                                    ├→ Strategy Sleeves
PortfolioSnapshot → CapitalAllocationPolicy        │
                  → StrategyAllocations ────────────┘
    → Portfolio Allocation / Cross-strategy Netting
    → Account-level ApprovedPortfolioTarget
    → Position Sizing
    → ActivePortfolioTarget(Decision-time Quantity)
    → RebalanceCoordinator(Current Portfolio + Working Orders)
    → OrderPlan
    → OrderIntent

Liquidity/Execution Strategy
    → OrderIntent / CancelIntent
```

`PortfolioStrategy` 使用 `TargetExposureFraction` 表达相对于 Strategy Allocation NAV 的有符号目标名义暴露。Strategy 不决定 Allocation NAV；`CapitalAllocationPolicy` 在每个决策点根据权威 `PortfolioSnapshot` 和运行配置为每个 Strategy Sleeve 产生 `StrategyAllocation`。

Portfolio Allocation 将各 Sleeve 的目标转换为名义暴露，并对同一 Instrument 的相反或重复目标进行账户级净额化。Portfolio/Risk 审批账户级目标后，Position Sizing 根据价格、合约乘数和 Lot/step size 转换为可交易数量，Order Planning 再生成账户订单意图。

`LiquidityStrategy` 或 `ExecutionStrategy` 可以表达挂单、改单和撤单意图，但不能生成 Binance、Hummingbot 或券商专用命令。

两类策略最终都必须经过统一的 Order Capability Validation、Order Translation、Market Rule Evaluation、Fee Reservation、Pre-trade Risk、Execution、Fee Assessment、Settlement 和 Accounting。Portfolio Strategy 在 Position Sizing 前还必须经过 Portfolio Risk。

### 4.3 单一权威执行与核算内核

回测系统只有一套权威执行与核算内核。完整 Portfolio Strategy 路径和预计算 Target Stream 路径只在 `StrategyDecision` 产生方式上不同，从组合风险审批开始共享相同实现。

```text
完整组合策略路径：
Market Events → PortfolioStrategy ──────┐
                                        ▼
预计算目标路径：Precomputed Target Stream
                                        │
                                        ▼
                 Atomic DecisionBatch(TargetSnapshots) ──────┐
                                                              ├→ Strategy Sleeves
PortfolioSnapshot → CapitalAllocationPolicy                   │
                  → StrategyAllocations ───────────────────────┘
                                        ↓
                         Portfolio Allocation / Netting
                                        ↓
                    Account-level ApprovedPortfolioTarget
                                        ↓
                               Position Sizing
                                        ↓
                ActivePortfolioTarget(Exact Quantity)
                                        ↓
RebalanceCoordinator(Current Portfolio + Working Orders)
                                        ↓
                                  OrderPlan
                                        ↓
                                  OrderIntent ─────┐
                                                  │
Liquidity/Execution Strategy → Order/CancelIntent ┤
                                                  ▼
                                  Order Capability Validation
                                                  ↓
                                       Order Translation
                                                  ↓
                                     Market Rule Evaluation
                                                  ↓
                              Fee/Resource Reservation Proposal
                                                  ↓
                                          Pre-trade Risk
                                                  ↓
                                             Execution
                                                  ↓
                              Fee Assessment + Settlement + Accounting
```

预计算 Target Stream 是按 `decision_time` 排序的 `StrategyDecision` 序列；每个 Decision 携带一个完整、绝对的 `TargetSnapshot`，而不是仓位变化命令、已成交仓位或收益率序列。它可以绕过策略计算，但不能绕过 Portfolio/Risk、Order Planning、Market Rules、Execution、Settlement 或 Accounting。独立的向量化收益计算器只能作为非权威分析工具。

### 4.4 市场事实与模拟假设分离

不同市场的交易时间、价格限制、交收、融资和公司行为相互独立。系统使用 `MarketSemanticsProfile` 组合真实市场语义，使用 `SimulationProfile` 组合历史执行近似，避免把事实和假设混入一个巨型 Market Adapter。

外部调用者不能为 decision-grade 运行任意拼装能力模块，只能通过版本化 key 使用 Registry 中已经注册、兼容性验证并计算 digest 的 Profile。Research 可以使用 custom profile，但结果最高只能是 development-grade，并必须保存完整 resolved component manifest。

### 4.5 分层数值语义

指标、统计、优化和展示可以使用 `float64`。Order、Fill、Fee、Funding、Cash、Position、市场规则和 Accounting Journal 等权威交易数值使用有类型的固定精度整数。

```text
real_value = units / 10**scale
```

权威领域对象使用 `Price`、`Quantity`、`Money`、`Rate` 和 `ExposureFraction` 等类型，不暴露无业务身份的裸整数。`Decimal` 只用于外部字符串解析、格式转换和参考测试，不作为权威存储模型。

所有除法、Scale 降低和市场格点量化必须指定显式 `RoundingPolicy`。Strategy/Analytics 的 float 值进入交易领域时必须通过版本化规范化边界。

### 4.6 确定性和 Fail-closed

在缺少必需数据、规则、Funding slot、公司行为或结算信息时，decision-grade 运行必须失败关闭。近似模型必须显式写入结果限制，不得静默降级。

### 4.7 回测不等于部署授权

所有回测结果默认：

```json
{
  "deployment_authorized": false
}
```

部署授权属于独立的 Promotion Gate 和人工审批流程。

## 5. 系统上下文

```text
                    ┌──────────────────┐
                    │ Research Platform │
                    └─────────┬────────┘
                              │ BacktestRequest
                              ▼
┌──────────────────┐      ┌──────────────────────┐      ┌─────────────────┐
│ Immutable Market │─────▶│   Backtest System    │─────▶│ Evidence Store  │
│ Bundle Repository│      │                      │      │ / Registry      │
└──────────────────┘      └──────────┬───────────┘      └─────────────────┘
                                │
                 ┌──────────────┼──────────────┐
                 ▼              ▼              ▼
             Strategy     Trading Kernel   Backtest Environment
```

回测系统负责在历史环境中组合这些模块，但不拥有具体策略研究流程和部署审批。Capital Allocation、Portfolio/Risk、Position Sizing、Order Planning、Pre-trade Risk 和 Accounting 属于共享 Trading Kernel，由 Backtest Runtime 和未来 Live Runtime 共同依赖。

## 6. 总体模块图

```text
trading-domain                         market-data-contracts
      ▲                                ├── bundle-manifest
      │                                ├── bundle-reader
trading-kernel                         ├── event-cursor
├── ports                              └── repository-contract
├── strategy-output-validation                    ▲
├── capital-allocation                            │
├── portfolio-aggregation              market-bundle-builder
├── portfolio-risk                    ├── source-adapters
├── position-sizing                   ├── normalization
├── rebalance-coordinator             ├── validation
├── order-planning                    └── immutable-bundle-publisher
├── order-capability-validation                   │
├── order-translation                             │
├── market-rule-evaluation                        │
├── fee-reservation-estimation                    │
├── fee-assessment                                │
├── settlement-book                               │
├── availability-projection                       ▼
├── resource-reservations             immutable-bundle-repository
├── pre-trade-risk                                ▲
├── accounting-journal-ledger                     │
├── mark-resolver                                 │
├── currency-valuation-graph                      │
├── portfolio-snapshot-projector                  │
└── profiles                                      │
    ├── binance-usdm                              │
    └── cn-a-share                                │
      ▲                                           │
      └──────────────────┬────────────────────────┘
                         │
                  backtest-runtime
                  ├── historical-timeline
                  ├── deterministic-cursor-merge
                  ├── observation-replay
                  ├── simulation
                  │   ├── ports
                  │   └── profiles
                  ├── bar-engine
                  ├── run-end-coordinator
                  ├── microstructure-engine
                  ├── evidence
                  └── analysis-runtime
                      └── versioned-metrics
```

未来 Live Runtime 只依赖 `trading-domain` 和 `trading-kernel`，不能依赖 `backtest-runtime`。

### 6.1 依赖规则

- `trading-domain` 不依赖其他业务模块，并拥有权威 Artifact Envelope、Schema Catalog 与纯 Migration contract；没有真实旧 Artifact 时不实现 speculative Migration Chain。
- `trading-kernel` 依赖 `trading-domain`，不依赖 Backtest 或 Live Adapter；拥有真实市场和账户行为 Ports，RebalanceCoordinator 在两种运行环境中共享。
- Generic Trading Kernel 只能依赖 Ports，禁止导入具体 `binance_usdm` 或 `cn_a_share` Profile；具体 Profile 实现依赖 Ports 并可由 Backtest/Live composition root 注册。
- `market-data-contracts` 依赖 `trading-domain`，拥有轻量 Bundle Manifest、Reader、EventCursor 和 Repository contract，不依赖在线 Source Adapter 或供应商 SDK。
- `market-bundle-builder` 依赖 `market-data-contracts`，通过 Source Adapter 构建并发布内容寻址 Bundle；不被 Backtest Runtime 反向调用。
- `backtest-runtime` 依赖 `trading-kernel` 和 `market-data-contracts`，只读 Bundle Repository，并提供历史 Timeline 和模拟 Execution Adapter；不得依赖 `market-bundle-builder`。
- Strategy 不依赖 Backtest Engine。
- Strategy 不依赖具体 MarketSemanticsProfile 或 SimulationProfile 实现。
- Accounting 不依赖 Strategy。
- Bar Engine 不依赖 Microstructure Engine，反之亦然。
- Evidence 模块只消费运行结果，不修改运行语义。
- Hummingbot DTO 不进入 Trading Domain、Trading Kernel 或 Backtest Runtime，只存在于具体 Live Venue Adapter。
- Platform 可以组合所有模块，其他模块不能反向依赖 Platform。

## 7. 外部接口

第一阶段提供三个面向不同决策来源的入口，三者必须进入同一个权威执行与核算内核：

```python
def run_portfolio_strategy_backtest(
    *,
    request: BacktestRequest,
    market_bundle_repository: MarketBundleRepository,
    strategy: PortfolioStrategy,
    environment_registry: BacktestEnvironmentRegistry,
) -> BacktestRunOutcome:
    ...


def run_target_backtest(
    *,
    request: BacktestRequest,
    market_bundle_repository: MarketBundleRepository,
    target_stream: TargetStream,
    environment_registry: BacktestEnvironmentRegistry,
) -> BacktestRunOutcome:
    ...


def run_liquidity_strategy_backtest(
    *,
    request: BacktestRequest,
    market_bundle_repository: MarketBundleRepository,
    strategy: LiquidityStrategy,
    environment_registry: BacktestEnvironmentRegistry,
) -> BacktestRunOutcome:
    ...
```

Runner 根据 `BacktestRequest.market_bundle_hash` 从只读 `MarketBundleRepository` 解析不可变 Bundle，并根据 `market_semantics_profile_key`、`simulation_profile_key` 和 `execution_account_profile_key` 解析 `ResolvedBacktestEnvironment`。Runner 验证三类 Profile、InitialAccountState 与 MarketBundle 的兼容性，并把三个 profile digest 和 bundle hash 纳入 request hash。调用者不能直接向 decision-grade 运行传入随意拼装的 Profile 或可变数据对象。

`run_portfolio_strategy_backtest` 在历史时间线上调用 Portfolio Strategy 产生 `StrategyDecisionCandidate`；`run_target_backtest` 从预计算 Target Stream Payload 解码出相同 Candidate。两条路径经过同一个 StrategyOutputValidator，只有 Validated `StrategyDecision` 才能从 DecisionBatch 开始进入共享 Portfolio/Risk 实现。

`run_liquidity_strategy_backtest` 驱动需要 Quote、Trade 或订单簿事件的策略，接收其 venue-neutral Order/Cancel Intent，并从 Pre-trade Risk 开始进入共享执行与核算内核。

禁止调用者直接驱动内部事件队列、直接注入 Fill 或手工修改 Ledger。

### 7.1 Strategy 调用与数据可见性

Portfolio Strategy 由显式 `DecisionSchedule` 调用：

```python
decision_candidate, new_state = strategy.decide(
    context=DecisionContext(
        decision_time=decision_time,
        observations=observation_view,
        previous_target_snapshot=previous_target_snapshot,
        schedule_context=schedule_context,
    ),
    previous_state=strategy_state,
)
```

Liquidity/Execution Strategy 由其订阅的市场事件调用：

```python
intents = strategy.on_market_event(
    event=visible_market_event,
    context=microstructure_context,
)
```

Strategy Context 采用最小权限：

- Portfolio Strategy 只能访问 ObservationView、自己的 Previous TargetSnapshot、StrategyState 和 DecisionSchedule context；禁止读取账户 Cash、NAV、Margin、其他 Sleeve 和 Working Orders。
- Liquidity Strategy 可以访问订阅 Instrument 的权威 InventoryView、WorkingOrderView 和 RecentFillView，但不能直接读取完整 Accounting Journal。
- Execution Strategy 可以访问 Parent Execution Demand、Working Orders、Fills 和 Remaining Quantity，不决定上游投资目标。

两类 Strategy 只能通过只读 `ObservationView` 访问市场数据。所有影响未来 Decision 或 OrderIntent 的业务状态必须进入可 canonical serialization 的 `StrategyState`；每次调用记录 before/after state hash。Strategy 随机性只能使用分配给该 Strategy 的命名 RandomStream。

Liquidity Strategy 的 Inventory 必须来自权威 PortfolioSnapshot，不能在 StrategyState 中维护第二套财务持仓。性能缓存可以不进入 State，但必须可从市场数据和权威 State 重建。

`ObservationView` 必须强制：

```text
observation.available_time <= current decision/simulation time
```

对于可修订数据，ObservationView 返回当前模拟时点已经可用的最新合法 Revision。后续 Revision 不得重写此前 Strategy 已观察的 DecisionContext。

Strategy 不接收原始 `MarketBundle`，不得自行读取市场数据文件、访问网络或读取系统当前时间。Strategy 只能通过 ObservationView 的 point-in-time universe query 获取可交易 Instrument，并通过命名 BarDefinition key 查询 canonical Bar Stream；不能扫描数据目录推断 Universe，也不能执行未经版本化的时间 Resample。ObservationView 内部可以使用向量化或缓存优化，但不能扩大可见数据范围。

每次 Strategy 调用必须记录：

- 调用时间和 Timeline Phase
- 查询的数据集和 Instrument
- 最大 event time
- 最大 available time
- 观察数据 revision IDs、版本/hash
- StrategyState before/after hash
- Strategy-specific RNG state hash（如适用）

这些记录构成因果性审计的一部分。

## 8. 领域模型

### 8.1 BacktestRequest

```python
@dataclass(frozen=True)
class BacktestRequest:
    schema_version: int
    experiment_id: str | None
    data_start_time: UtcInstant
    trading_start_time: UtcInstant
    trading_end_time_exclusive: UtcInstant
    execution_account_profile_key: str
    initial_account_state: InitialAccountState
    external_cash_flow_timeline_hash: str | None
    reporting_currency: str
    currency_valuation_policy_key: str
    strategy_book_spec: StrategyBookSpec
    model_artifact_refs: tuple[ModelArtifactRef, ...]
    capital_allocation_spec: CapitalAllocationSpec
    risk_spec: RiskSpec
    rebalance_policy_spec: RebalancePolicySpec
    closeout_policy: CloseoutPolicy
    market_semantics_profile_key: str
    simulation_profile_key: str
    market_bundle_hash: str
    master_random_seed: int
    build_artifact_manifest_hash: str
    stale_target_policy: StaleTargetPolicy
    result_grade_requested: str
```

约束：

- `data_start_time <= trading_start_time < trading_end_time_exclusive`
- Warmup 区间为 `[data_start_time, trading_start_time)`
- Active Trading 区间为 `[trading_start_time, trading_end_time_exclusive)`
- 所有配置可规范化序列化并计算 hash
- request 不包含密钥
- decision-grade request 必须引用不可变 `BuildArtifactManifest`
- request 不使用隐式当前时间或当前目录
- Backtest Run 只读已冻结 MarketBundle，运行期间禁止网络和可变外部数据查询
- 第一阶段一个 request 只能引用一个 MarketSemanticsProfile、一个 SimulationProfile、一个 ExecutionAccountProfile、一个 Execution Account 和一个 Reporting Currency
- 配置多个 account_id、execution_account_profile_key 或 market_semantics_profile_key 时必须在运行前失败关闭

### 8.2 MarketBundle

```python
@dataclass(frozen=True)
class MarketBundle:
    manifest: MarketManifest
    instruments: tuple[InstrumentIdentity, ...]
    instrument_reference_timeline: InstrumentReferenceSource
    universe_timeline: TradableUniverseSource
    price_streams: Mapping[PricePurpose, PriceEventSource]
    bar_streams: Mapping[BarDefinitionKey, BarEventSource]
    availability_timeline: MarketAvailabilitySource
    exchange_rules: RuleTimeline
    funding_publications: FundingPublicationSource
    funding_settlements: FundingSettlementSource
    corporate_actions: CorporateActionSource
```

`MarketBundle` 是经过验证的历史证据包，不是任意 DataFrame 集合。Backtest Runtime 通过只读 `MarketBundleReader` 和多个 `EventCursor` 流式消费，不要求一次性载入内存，也不直接暴露给 Strategy。

Price Stream 必须按用途区分：`EXECUTION_REFERENCE`、`VALUATION`、`MARGIN`、`LIQUIDATION` 和 `SETTLEMENT`。MarketSemanticsProfile 声明必需用途，MarketBundle 生成 `PriceStreamCoverageReport`。模块不得自行从任意价格列选择替代值。

可修订 Observation 记录使用双时间和 Revision identity：`event_time`、`available_time`、`revision_id`、`supersedes_revision_id`、source 和 source hash。Vendor 修订必须作为新 Revision 进入 Bundle，不能原地覆盖旧版本。

所有预期数据缺口必须由 `MarketAvailabilitySource` 分类为 `NO_SESSION`、`SUSPENDED`、`NO_TRADES`、`MISSING` 或 `SOURCE_OUTAGE`。Execution 禁止使用 forward-filled 或合成 Bar 成交。ObservationView 必须向 Strategy 暴露 availability status。

Execution、Market Rules 和 Accounting 使用的 Price/Quantity 必须能够无损解析为 typed scaled integer；ObservationView 可以为指标计算提供 float64 数组。复权观察序列必须根据 point-in-time Corporate Action Timeline 派生。

Manifest 至少记录：

- 数据源
- 生成时间
- 覆盖区间
- 稳定 Instrument identity、时点 Symbol 和 listing/delisting coverage
- Point-in-time Universe membership coverage
- 数据 schema version
- 文件 hash
- 缺口和限制
- Exchange rule coverage 和 `RuleCoverageReport` hash
- Funding publication、settlement slot、eligibility instant 和 funding mark coverage
- Corporate action coverage
- 各 PricePurpose 的 stream identity、覆盖区间和 hash
- Market availability/gap classification coverage
- Revision-aware data coverage 和 revision provenance
- BarDefinition、BarAggregationManifest 和 canonical Bar stream hash
- Source Snapshot 和 normalization provenance

### 8.3 MarketBundle Builder

MarketBundle 构建是独立于 Backtest Run 的数据流程：

```text
Raw Source Adapters
        ↓
Content-addressed Source Snapshots
        ↓
Normalization
        ↓
MarketBundle Builder
        ↓
Validation Reports
        ↓
Immutable MarketBundle Repository
```

Binance API、Vendor、CSV、Parquet 和 DuckDB 只存在于 Source Adapter/Builder 层。Normalizer 映射到统一 Instrument Identity、Timeline、Price Stream、Rule Timeline、Revision、Universe 和 Corporate Action schema。`BarDefinition` 明确 duration、Session scope、anchor、included phases、price source、volume semantics、empty interval policy 和 Calendar；日线按 TradingDate/Session 聚合，不按 UTC date 猜测。数据刷新或 BarDefinition 变化产生新的 Bundle hash，不得修改旧 Bundle。

MarketBundle 声明 capabilities；ResolvedBacktestEnvironment 在运行前验证 SimulationProfile 所需 capability。Backtest Runtime 运行期间不得访问网络、调用供应商 API 或读取未冻结的可变数据源。

Reader Contract：

- `MarketBundleReader` 打开内容寻址 Bundle。
- 每类 Event Stream 提供按规范排序的 `EventCursor`。
- Timeline 对 Cursor 按 `(epoch_nanoseconds, phase, source_sequence)` 做确定性 merge。
- ObservationView 可请求有界历史窗口并返回向量化数组。
- Parquet、Arrow、memory map、Pandas 和 in-memory Fixture 都是 Reader Adapter 或内部优化。
- 存储格式、分区和 batch size 不能改变领域事件顺序。
- Cursor position 可进入未来 EngineCheckpoint。

### 8.4 StrategyState 与 StrategyDecision

`StrategyState` 是 Strategy 所有影响未来行为的显式业务状态。它必须可序列化、可恢复并具有稳定 hash。随机行为使用 BacktestRequest seed 派生的 Strategy-specific RNG state。文件、网络、系统时钟和不可重建缓存不能成为隐藏业务状态。

Backtest Runtime 不训练模型、不搜索参数、不选择最佳候选。普通 Strategy 使用 immutable StrategySpec；训练型 Strategy 使用内容寻址 `ModelArtifact`，记录 model hash、training data hash、training interval、training code hash、feature schema hash 和 available time。

ModelArtifact 只有在 `available_time <= decision_time` 时可用。Walk-forward 通过 point-in-time `ModelRevisionTimeline` 切换 Artifact；每次切换进入 Strategy State 和 Decision trace。每个参数组合形成独立 Semantic Run，由外部 Research/Experiment 层比较和选择。

Portfolio Strategy 和预计算 TargetStream 都先产生不受信任的 `StrategyDecisionCandidate`。Candidate 可以保留重复 Instrument、未知 Instrument、非法时间或尚未量化数值，以便 Validator 生成完整失败证据；它不是权威执行对象，也不进入 canonical execution trace。

```python
@dataclass(frozen=True)
class StrategyDecisionCandidate:
    payload: StrategyDecisionPayload
```

`StrategyOutputValidator` 将 Candidate 转换为 Validated `StrategyDecision` 或结构化 `ValidationFailure`。只有 Validated StrategyDecision 才是 Portfolio Strategy 的权威输出契约；它不用于表达做市挂单和撤单。

```python
@dataclass(frozen=True)
class StrategyDecision:
    strategy_id: str
    decision_time: UtcInstant
    observed_through: UtcInstant
    target_snapshot: TargetSnapshot
    confidence: ConfidenceScore | None
    reason: str
    evidence: Mapping[str, CanonicalValue]


@dataclass(frozen=True)
class TargetSnapshot:
    sleeve_id: str
    effective_time: UtcInstant
    expires_at: UtcInstant | None
    targets: tuple[TargetExposureFraction, ...]
```

Validated StrategyDecision 的关键约束：

```text
observed_through <= decision_time
```

策略目标使用领域 Instrument ID，不使用 Hummingbot trading pair 或券商专用字段。

`TargetExposureFraction` 是有类型的固定精度整数，定义为：

```text
有符号目标名义暴露 / Strategy Allocation NAV
real_value = units / 10**scale
```

其 canonical scale 由 Trading Domain schema version 固定，不由单个 Strategy 任意选择。v1 固定为 12 位小数（`real_value = units / 10**12`），足以 exact 表达现有 round-12 Strategy weight；经济杠杆范围由 Portfolio Risk 而不是数据契约限制。

第一阶段它是 Portfolio Strategy 唯一允许的目标单位：

- `+0.5`：目标多头名义暴露为分配 NAV 的 50%
- `-0.8`：目标空头名义暴露为分配 NAV 的 80%
- `+2.0`：目标多头名义暴露为分配 NAV 的 200%
- `0`：目标空仓

Strategy 不直接输出 Instrument 数量、交易金额、Allocation NAV 或订单。原始信号、排名和指标属于 Strategy 内部语义。Capital Allocation、Portfolio Allocation、Position Sizing 和 MarketSemanticsProfile 负责将目标比例转换为符合市场规则的可交易数量。

`TargetSnapshot` 使用完整、绝对、原子替换语义：

- 数值表示最终目标暴露，不表示对旧目标的增量。
- 新快照整体替换同一 Sleeve 的旧快照。
- 旧快照中存在而新快照省略的 Instrument 目标归零。
- 不支持隐式继承旧值的稀疏 Patch。
- `effective_time` 不得早于 `decision_time`。
- 到达 `expires_at` 后，由请求中显式配置的 `StaleTargetPolicy` 决定 `hold_last`、`flatten` 或 `halt_new_orders`。
- Decision-grade 运行不允许使用隐藏的过期默认策略。

### 8.5 DecisionBatch

同一 `DecisionBatchInstant` 调度的 Portfolio Strategies 独立读取各自最小权限 Context。每个 StrategyDecisionCandidate 先经过 Trading Kernel 的 `StrategyOutputValidator`；全部得到 Validated StrategyDecision 后才原子收集到 `DecisionBatch`，之后执行 Capital Allocation、Portfolio Netting、Risk 和 Active Target materialization。

Strategy 注册顺序不得改变结果；同 Batch Strategy 互相不可见。不同 Decision Instant 的 Strategy 保留其他 Sleeve 最近有效的 ActivePortfolioTarget。整个 Batch 完成前禁止生成 OrderPlan。

每个 Batch 使用稳定 `decision_batch_id`。Validator 只返回 `Validated StrategyDecision | ValidationFailure`，不知道 Candidate 来自 Runtime Strategy 还是预计算输入，也不返回 Run Outcome。

Backtest Runtime 根据 `InputOrigin` 映射失败：Runtime Strategy 的未处理错误或 Contract/Causality violation 产生 FAILED；预计算 TargetStream 的 decode/validation failure 产生 BLOCKED。两者都不允许使用部分成功 DecisionBatch。无法解码的原始 Payload 在输入 Adapter 层产生 `InputDecodeFailure`。

Contract violation 包括未知或未上市 Instrument、重复 Target、observed-through 越过 Decision Time、非法 effective time、Schema 错误和 float-to-fixed quantization 失败。合法但超出风险预算的 economic target 不属于 Contract violation，应交给 Portfolio Risk approve、clamp 或 reject。非法 Candidate 不进入 canonical execution trace，但 payload hash 和 Validation Report 必须进入失败证据。

Validator 的可信输入使用 `StrategyOutputValidationContext` 固定 expected Strategy/Sleeve identity、authoritative Decision Time、InstrumentCatalog 和已在该时点解析完成的 Universe。Validator 不自行查询或推断 Universe。Candidate v1 目标数值仅允许 integer、`Decimal` 或 canonical decimal string exact 转换到 scale 12；bool/float、非有限值和需要 rounding 的值均 fail closed。ValidationFailure 只保存稳定 type-tagged payload evidence hash 和规范排序 Issue，不获得 Candidate 的 canonical execution authority。

### 8.6 StrategyAllocation

```python
@dataclass(frozen=True)
class StrategyAllocation:
    strategy_id: str
    sleeve_id: StrategySleeveId
    valuation_time: UtcInstant
    valuation_currency: CurrencyId
    allocation_nav: Money
    policy_ref: CapitalAllocationPolicyRef
    source_portfolio_snapshot_hash: str
```

`CapitalAllocationPolicy` 在每个决策点为每个 Strategy Sleeve 生成 `StrategyAllocation`。第一阶段至少支持：

- `fixed_initial_allocation`：以运行开始时的固定资本为基准，不随盈亏复利。
- `current_equity_fraction`：以当前权威 Portfolio Equity 的配置比例为基准，随盈亏复利。

Allocation Policy、比例和估值货币必须进入规范化请求和 request hash，不允许由 Strategy 隐式决定。WP-04C 的 Allocator 消费带有完整 Policy/Snapshot provenance 的 supplied `StrategyAllocation`；具体 Policy 执行由组合层显式完成，Kernel 不提供隐式默认 Allocation。

### 8.7 StrategySleeve

`StrategySleeve` 是一个 Portfolio Strategy 在共享执行账户中的逻辑资本和目标边界。多个 Sleeve 可以对同一 Instrument 产生不同目标，但不能直接维护相互独立的真实现金或交易所持仓。

Portfolio Allocation 必须：

1. 将每个 Sleeve 的 Target Exposure Fraction 转换为目标名义暴露。
2. 按 Instrument 聚合所有 Sleeve。
3. 在账户级净额化相反目标。
4. 将净目标交给 Portfolio/Risk。

第一条纵向切片可以只配置一个 Sleeve，但领域契约和聚合器必须允许多个 Sleeve。

### 8.8 ApprovedPortfolioTarget

```python
@dataclass(frozen=True)
class ApprovedPortfolioTarget:
    decision_id: str
    approved_at: UtcInstant
    targets: tuple[ApprovedPosition, ...]
    gross_exposure: Money
    net_exposure: Money
    margin_requirement: Money
    applied_limits: tuple[AppliedLimit, ...]
    rejections: tuple[TargetRejection, ...]
```

它负责表达组合聚合和 Portfolio Risk 审批后的最大允许目标，而非原始策略观点。Portfolio Risk 可以 approve、clamp 或 reject Target，但每次变换必须记录原目标、应用规则和最终目标。

v1 的 Target-level absolute-notional limit 可以向零 clamp 或 reject 为显式零目标；aggregate gross/absolute-net limit 只做 approve 或 reject whole target set。v1 不做 proportional aggregate clamp，因为该行为必须额外冻结 Instrument 优先级、离散 rounding 和 residual 分配语义。Risk Policy 必须覆盖每个输入 Instrument 并绑定 valuation Currency/Scale；coverage 或 context 错误属于 Contract Failure，合法 economic target 的 clamp/reject 则是成功的 Risk Assessment。`ApprovedPortfolioTarget` 保留原始 `NetInstrumentTarget` 的 Sleeve attribution；Risk 不创建 Quantity、Venue Order 或 Margin 值。

### 8.9 NormalizedPortfolioTarget

Position Sizing 使用 supplied Decision-Instant Mark 和时点有效、版本化的 `QuantityLattice`，将已审批目标名义暴露转换为市场可交易的定点整数数量。Sizer 不查询 MarkResolver、Market Profile 或 Reader；Composition Root 必须把已解析的 Mark/Lattice 作为 immutable input 提供。

规则：

- v1 `PositionSizingPolicy` 必须显式声明 key/version/config hash、Sizing PricePurpose、`RoundingPolicy.TOWARD_ZERO` 和 `ResidualPositionPolicy`；不允许隐式默认 Policy。
- Notional/Price 先直接量化到 Lattice atomic Scale，再按 signed target 对应的 buy/sell lot（未声明时为 step）向零量化。普通规格化禁止绝对名义暴露超过已审批暴露；显式 `hold_dust` 可以保留无法合法关闭的既有 odd-lot，但必须记录该 approved-target 偏差，不能伪装成已达到目标。
- Mark resolved instant 必须等于 Approved Target instant，Price 必须为正，Price quote Currency 必须等于 approved Notional Currency；本边界不发明 FX path 或 stablecoin peg。
- 每个 Instrument 同时提供当前 exact Quantity。正常目标按 buy/sell lattice 物化；完整平仓若遇到 odd lot，只能按 Lattice 的显式 full-close capability 和 Residual Policy 处理。
- 反向持仓的 exact Active Target 可以被物化，但后续 Order Planner 必须拆为 close/open 两阶段，禁止一个含糊净订单隐式穿越零点。
- 无法交易的残余仓位由显式 `ResidualPositionPolicy` 处理：`hold_dust`、`close_if_permitted` 或 `fail`。任一 Instrument 失败时不产生部分账户级 Active Target。
- Normalized target、current/raw/final Quantity、量化差异、Mark/Lattice identity、RoundingPolicy 和 Residual decision 都属于权威证据。

```python
@dataclass(frozen=True)
class QuantityLattice:
    instrument_id: InstrumentId
    lattice_key: str
    lattice_version: int
    config_hash: str
    atomic_scale: Scale
    step_units: int
    buy_lot_units: int | None
    sell_lot_units: int | None
    min_quantity_units: int
    min_notional: Money
    odd_lot_close_permitted: bool
```

Order Planner 只消费已经物化的 exact `ActivePortfolioTarget` Quantity，不得再次执行数量舍入。Contract multiplier 或非 quote-currency sizing 必须由后续显式 Instrument/Profile Gate 扩展，不能在 v1 内隐式猜测。

### 8.10 ActivePortfolioTarget

`TargetExposureFraction` 只在 StrategyDecision 生效时，使用该 Decision Instant 的 Strategy Allocation NAV、Price、Risk 和 QuantityLattice 原子物化为精确 `ActivePortfolioTarget` Quantity。

持续有效的是 ActivePortfolioTarget Quantity，而不是动态 Exposure Fraction。Price、NAV 或 External Cash Flow 变化本身不会重新计算旧目标。只有新 StrategyDecision、明确 Capital Reallocation event 或 Target expiry policy 可以产生新的 ActivePortfolioTarget。

需要恒定权重的 Strategy 必须通过 DecisionSchedule 发布新 TargetSnapshot。未来若增加连续动态目标，必须使用显式 `DynamicTargetPolicy`，不能改变 v1 默认语义。

### 8.11 RebalanceCoordinator

`TargetSnapshot` 是策略决策证据；其物化后的 `ActivePortfolioTarget` 才是 RebalanceCoordinator 持续逼近的目标状态。Target Validity、OrderPlan Validity 和 Venue Order Time-in-Force 是三种独立生命周期。

`RebalanceCoordinator` 根据以下状态持续生成 OrderPlan、CancelIntent 或 PlanningOmission：

- 当前 ActivePortfolioTarget 及其来源 TargetSnapshot
- 当前 PortfolioSnapshot
- Working Orders 及其剩余数量
- Session 和 Market Rule 状态
- 版本化 RebalancePolicy

重新规划触发器至少包括：

- 新 TargetSnapshot
- Fill 或 Partial Fill
- Order reject、cancel 或 expire
- Session open
- Rule Timeline change
- Target expiration
- Account state change

新 TargetSnapshot 原子替换旧目标，并取消与新目标冲突的 Working Orders。Planner 必须将 Working Order 剩余数量计入预期仓位，禁止对相同未完成目标重复下单。

OrderPlan 必须引用生成时的 Target Snapshot、Portfolio Snapshot 和 Working Order set hash；任一前提变化后旧 Plan 进入 `superseded`，不能继续产生新订单。Plan superseded 不会让已提交订单静默消失，必须通过 CancelIntent 处理。

Venue Order 使用明确 Time-in-Force，例如 DAY、GTC、IOC、FOK 或 GTX/Post-only。合法 TIF 由 MarketSemanticsProfile 和 ExecutionAccountProfile 判断，具体历史行为由 SimulationProfile 模拟。Order expiry 不清除 Target，RebalanceCoordinator 可以根据 RebalancePolicy 在后续触发点继续逼近仍然有效的目标。

### 8.12 OrderPlan

```python
@dataclass(frozen=True)
class OrderPlan:
    plan_id: str
    created_at: UtcInstant
    based_on_target_snapshot_id: str
    based_on_portfolio_snapshot_id: str
    based_on_working_order_set_hash: str
    valid_until: UtcInstant | None
    orders: tuple[PlannedOrder, ...]
    assumptions: tuple[str, ...]
```

`PlannedOrder` 产生 canonical `OrderIntent`，至少包括：

- Instrument ID
- Side
- Quantity
- Execution style
- Price constraint
- Venue Time in Force
- Reduce-only
- Position effect
- Urgency
- Reason
- Parent decision/target ID

v1 canonical values 为 `OrderSide = buy | sell`、`ExecutionStyle = market | limit | stop | stop_limit`、`TimeInForce = day | gtc | ioc | fok | gtx`、`PositionEffect = auto | open | close`。`PriceConstraint` 只承载可选 typed limit/trigger price；Style 与 Constraint 的合法组合由 Capability/Market Rule 判断。

Canonical OrderIntent 不包含任意 extensions/metadata、trading pair、Hummingbot `PositionAction`、券商 Board 或其他 Venue DTO 字段。OrderTranslator 将其解析为 `ExecutableOrderSpec` 并生成 OrderTranslationReport；ExecutableOrderSpec 可以包含已解析的 Profile capability 和账户约束，但仍不是 Hummingbot 或券商 DTO。

### 8.13 OrderEventStream 与 ExecutionReport

`OrderEventStream` 是订单生命周期的权威证据，`OrderState` 是可重建投影。它不意味着整个回测引擎采用 Event Sourcing。

具体 OrderIntent 的门控顺序固定为：

```text
Canonical OrderIntent
→ Order Capability Validation
→ Order Translation + OrderTranslationReport
→ ExecutableOrderSpec
→ Market Rule Evaluation
→ Fee Reservation Estimate
→ Resource Reservation Proposal
→ Pre-trade Risk
→ Submission
→ Reservation Activation on accepted/active order
```

OrderCapabilityValidator 只判断 canonical 语义是否受支持；OrderTranslator 不得静默降级语义；MarketRuleEvaluator 只产生 MarketRuleDecision；FeeReservationEstimator 产生最坏费用承诺但不写 Journal。Pre-trade Risk 只 approve/reject，不能修改 Quantity、Price、TIF 或 Order Type。

`MarketRuleEvaluator` 只消费 supplied immutable `OrderRuleTimeline`。Timeline 按 Evaluation Instant 从半开有效区间中解析且必须恰好命中一个 `OrderRuleInterval`；缺失或重叠产生 `DataIntegrityFailure`，禁止回退最后规则或当前交易所规则。Snapshot 绑定 `ORDER_RULE_MODEL` Component identity、Instrument、Session、`QuantityLattice`、Price tick/limits、permissions 和显式 supplemental rule decisions。Evaluator 只验证，不能再次舍入或修改 Price/Quantity。Minimum Notional 使用显式 `OrderRuleNotionalEvidence`：constraint basis 必须 exact 引用 Intent Price，supplied reference basis 必须携带 source hash；Generic Kernel 不自行选择市场价、FX path 或 stablecoin peg。具体 A 股/Binance 规则只由后续 Profile Adapter 构造 Snapshot/Timeline，Generic Evaluator 不含市场条件分支。

Portfolio Risk 位于上游目标层，可以显式 approve、clamp 或 reject。Pre-trade Risk 位于具体订单层，只能 approve 或 reject，不得修改 Price、Quantity 或 TIF。它使用当前 Availability、现有 Resource Reservations、Fee 的 worst-case `ResourceReservationProposal` 以及 supplied immutable 完整 `ReservationCommitment` requirement 进行判断。完整 requirement 由 Market/Account Profile 组合提供并绑定 source Order、Market Rule 和 Fee Proposal identity；Generic PreTradeRisk 不自行猜测 Spot、Margin 或 Derivative 的资源公式。Cash、Sellable Quantity、Margin、Fee Reserve、Order Capacity 和 Exposure Capacity 必须分类比较；Fee Reserve 使用 Tradable Cash 还是 Available Margin 由显式版本化 Account Risk Policy 声明。若拒绝后允许重试，由 RebalanceCoordinator 根据显式 RebalancePolicy 重新规划。

```text
OrderIntentCreated
OrderCapabilityApproved / OrderCapabilityRejected
OrderTranslated
MarketRuleApproved / MarketRuleRejected
FeeReservationEstimated
PreTradeRiskApproved / PreTradeRiskRejected
OrderSubmitted
OrderAccepted / OrderRejected
OrderActivated
OrderPartiallyFilled
OrderFilled
OrderCancelRequested
OrderCancelled
OrderExpired
```

每个 Order Event 必须具有稳定 Event ID、Order ID、Causation ID 和 Simulation Instant，并支持幂等应用。模拟领域 ID 根据 semantic run ID、因果父 ID、稳定 ordinal 和必要 Simulation Instant 确定性派生；不同 Attempt 产生相同领域 ID。第一阶段订单修改使用 cancel-and-replace，不支持隐式原地修改。

失败必须区分：

- `PlanningOmission`：没有生成订单，例如落入 Deadband。
- `PreTradeRiskRejection`：未通过账户风险检查，订单未提交。
- `MarketRuleRejection`：数量、价格、Session 或权限不合法。
- `ExecutionRejection`：模拟或真实执行场所拒绝。
- `DataIntegrityFailure`：数据不足或不一致，阻断整个 decision-grade Run。

```python
@dataclass(frozen=True)
class ExecutionReport:
    plan_id: str
    final_order_states: tuple[OrderState, ...]
    fills: tuple[Fill, ...]
    lifecycle_event_hash: str
```

### 8.14 ResourceReservationBook

Working Order 尚未成交的现金、保守 Fee Reservation Estimate、可卖数量、初始保证金、借贷能力和订单/暴露额度承诺由独立 `ResourceReservationBook` 管理，不写入 Accounting Journal。

Reservation 生命周期由 Order Event 驱动：

```text
OrderAccepted/Activated → reserve
PartialFill             → reduce reservation
Cancel/Reject/Expire    → release
Fill                    → convert to Accounting Journal facts
```

Reservation 必须引用 Order ID，并可从 Order Event Stream 重建。MarketSemanticsProfile 和 ExecutionAccountProfile 共同定义具体 Reservation 计算规则。终态订单不得继续占用资源，重复 Event 不得重复冻结。

Generic `ResourceReservationBook` 只投影 supplied immutable reservation evidence，不实现上述规则计算。每个 Order 的 `OrderReservationSchedule` 必须指定恰好一个 Accepted 或 Activated Event 作为 activation point，并为每个后续 Partial Fill 提供与 exact remaining Quantity 对齐的 replacement commitment。Cash、Sellable Quantity、Margin、Fee Reserve、Order Capacity 和 Exposure Capacity 分类别保留；Partial Fill 更新不得增加任何既有维度或引入新维度，固定承诺可以保持不变。Cancel、Reject、Expire 或 Final Fill 无条件释放全部剩余 commitment。Book 只能在同一 Execution Account 内聚合 typed totals，不把 Reservation 写入 Journal、SettlementBook 或 AvailabilityProjection。

### 8.15 SettlementBook 与 AvailabilityProjection

Fill 发生后立即记录经济风险和 PnL，但资产或现金是否可卖、可交易或可提现由 Settlement 状态决定。

`SettlementBook` 保存可从 Fill 和 Settlement Event 重建的待结算义务：

```python
@dataclass(frozen=True)
class SettlementObligation:
    settlement_obligation_id: DomainId  # SETTLEMENT
    source_fill_id: DomainId             # FILL
    trade_time: UtcInstant
    settlement_time: UtcInstant
    instrument_id: InstrumentId | None
    quantity: Quantity | None
    currency_id: CurrencyId | None
    amount: Money | None
```

恰好一个 `(instrument_id, quantity)` 或 `(currency_id, amount)` pair 必须存在；signed units 表达收付方向，零义务非法。

`AvailabilityProjection` 根据 Accounting Ledger、SettlementBook、ResourceReservationBook 和 Market Settlement Rules 计算：

- Total Position
- Sellable Quantity
- Settled Cash
- Tradable Cash
- Withdrawable Cash
- Available Margin

Settlement 到达时产生明确 `SettlementApplied` Event 和对应 Journal/Availability 状态转换。Pre-trade Risk 使用 Available Resources，而不是只查看总 Cash 或 Position。Settlement Obligation 与 Working Order Reservation 是不同概念。

### 8.16 Fill

`Price`、`Quantity`、`Money`、`Rate` 和 `ExposureFraction` 使用 typed scaled integer 表示。Canonical serialization 必须包含 `units`、`scale` 以及 Instrument/Currency identity。

```python
@dataclass(frozen=True)
class Fill:
    fill_id: DomainId   # FILL
    order_id: DomainId  # ORDER
    account_id: str
    venue_id: VenueId
    instrument_id: InstrumentId
    side: OrderSide
    quantity: Quantity
    reference_price: Price
    reference_price_purpose: PricePurpose
    price: Price
    slippage_amount: Money
    slippage_decision_id: str
    slippage_model_key: str
    slippage_calibration_id: str | None
    liquidity: str | None
    execution_time: UtcInstant
```

### 8.17 FeeAssessment

Fill 是成交事实，不直接拥有唯一最终 Fee。`FeeAssessment` 独立表达按 Fill、Order 或 Session 计算的费用：

```python
@dataclass(frozen=True)
class FeeAssessment:
    fee_assessment_id: DomainId  # FEE
    basis_type: FeeBasisType
    basis_ids: tuple[DomainId | SessionId, ...]
    market_fee_rule_id: str | None
    account_fee_schedule_id: str | None
    tax_rule_id: str | None
    amount: Money
    assessment_time: UtcInstant
```

Per-fill maker/taker fee、per-order minimum commission、sell-only tax 和 order cancel 后的最终费用都由独立 `FeeAssessmentEngine` 根据相应 Fee/Tax/Account Policy 生成 FeeAssessment，再生成幂等 `FeeCharged` Journal Entry。Fee 的 Scale 和 RoundingPolicy 必须由对应规则明确规定。

FeeReservationEstimate 是下单前最坏费用承诺，只影响 Reservation 和 Available Resources；它不是 FeeAssessment 或 Accounting Journal。最终 Fee 可以低于预留，终态订单必须释放差额。

FeeAssessment 通过 basis IDs 引用 Fill/Order，而不是事后修改 immutable Fill。Cash Instrument Lot 的 fee allocation 可以在 FeeAssessment 完成后通过明确 Journal Entry 更新成本基础。

### 8.18 AccountingJournal

`AccountingJournal` 是执行账户现金、持仓、费用、外部资金流和已实现 PnL 的唯一财务权威。它由不可变且具有稳定 ID 的经济事实组成，例如：

- `CapitalDeposited`
- `CapitalWithdrawn`
- `FillBooked`
- `FeeCharged`
- `FundingApplied`
- `BorrowFeeCharged`
- `SettlementApplied`
- `CorporateActionEntitlementBooked`
- `CorporateActionPositionAdjusted`
- `CorporateActionCashPaid`
- `LiquidationApplied`

每条 Journal Entry 必须记录事件来源，例如 `fill_id`、`fee_assessment_id`、Funding slot、Settlement ID 或 Corporate Action ID，并支持按稳定 ID 幂等应用。Market Event trace、Strategy trace 和 Accounting Journal 是不同证据流，不得混为一个无类型事件文件。

### 8.19 PortfolioSnapshot

```python
@dataclass(frozen=True)
class PortfolioSnapshot:
    account_id: str
    timestamp: UtcInstant
    reporting_currency: CurrencyId
    cash: tuple[CashBalance, ...]               # native currency balances
    positions: tuple[PositionBalance, ...]      # native instrument quantities/lots
    realized_pnl: Money                         # reporting currency
    unrealized_pnl: Money                       # reporting currency
    fees: Money                                 # reporting currency
    financing: Money                            # reporting currency
    equity: Money                               # reporting currency
    valuation_marks: tuple[ValuationMarkReference, ...]
    journal_state_hash: str
    valuation_mark_set_hash: str
    valuation_staleness_report_hash: str
    currency_valuation_graph_hash: str
```

## 9. 时间模型

所有权威时间使用：

```python
@dataclass(frozen=True)
class UtcInstant:
    epoch_nanoseconds: int
```

Event ordering 只使用 UtcInstant。Exchange local time 仅用于 Source parsing、Session rule 和展示；禁止 naive datetime 进入权威领域对象。

`TradingDate` 和 `SessionId` 由 SessionModel 根据 Exchange time zone、Calendar 和夜盘归属规则计算，不能用 UTC date 或本地自然日猜测。Source timestamp、解析时区和 DST resolution 必须进入 provenance。

系统必须区分：

| 时间 | 含义 |
| --- | --- |
| `event_time` | 市场事件实际发生时间 |
| `available_time` | 数据对策略可见的时间 |
| `decision_time` | 策略作出决策的时间 |
| `submission_time` | 订单提交时间 |
| `execution_time` | 订单成交时间 |
| `settlement_time` | 资金或持仓完成交收的 UtcInstant |
| `trading_date` | SessionModel 赋予事件的交易日期标签，不参与 Instant 排序 |
| `session_id` | 事件所属交易 Session 的稳定身份 |

基本因果约束：

```text
event_time <= available_time <= decision_time <= submission_time <= execution_time
```

不是所有事件都需要经历所有阶段，例如 Funding 和公司行为可以直接进入 Ledger，但必须有明确时间语义。

所有事件使用以下总排序键：

```text
(epoch_nanoseconds, phase, source_sequence)
```

只按 UtcInstant 排序不构成确定性回测。

### 9.1 Warmup 与 Active Trading 区间

Warmup 区间 `[data_start_time, trading_start_time)`：

- Timeline 和 ObservationView 正常推进。
- Strategy 可以构建初始 StrategyState。
- Microstructure Engine 可以建立 Market/Order Book 状态。
- 禁止产生 OrderIntent、Fill 和 Accounting Journal Entry。
- 不计算策略收益和绩效。
- `InitialAccountState` 定义为 trading start 时点的账户状态，不受 Warmup economic event 修改。
- Warmup 结束时生成 Strategy State checkpoint。

StrategySpec 必须声明 `LookbackRequirement`。MarketBundle validator 生成 `LookbackCoverageReport`；数据不足时 decision-grade 失败关闭。

Active Trading 使用半开区间 `[trading_start_time, trading_end_time_exclusive)`，避免结束边界事件是否包含的歧义。

独立 `RunEndCoordinator` 在 Timeline 到达 `trading_end_time_exclusive` 时停止新 Strategy Decision，拒绝边界及之后的业务事件，终止 Working Orders，应用 CloseoutPolicy，识别未完成 Settlement/Funding/Fee basis，并请求 Final PortfolioSnapshot。

默认 `CloseoutPolicy` 为 `mark_to_market`：到达结束边界时保留 Position，使用边界前最后一个合法 Valuation Mark 生成 Final PortfolioSnapshot，分别报告 Realized 和 Unrealized PnL。Working Orders 进入 `OrderTerminatedByRunEnd`，不产生 Fill。边界时点及之后的 Funding、Settlement 和 Corporate Action 不计入结果。

如果研究要求最终平仓，必须显式配置 CloseoutPolicy，并在结束边界前预留执行窗口，使平仓经过正常 Capability、Translation、Market Rules、Fee Reservation、Risk、Slippage、Execution、Fee Assessment 和 Accounting Journal。禁止在最后收盘价隐式强平。

RunEndCoordinator 必须生成 `RunEndReport`，至少记录 terminated order IDs、open positions、pending settlements、pending fee assessments、last valuation mark IDs 和 closeout status。

### 9.2 Bar 数据示例

```text
Bar close_time      = 10:00:00
available_time      = 10:00:01
strategy decision   = 10:00:02
order submission    = 10:00:03
next-bar execution  = 10:01:00
```

### 9.3 宏观数据示例

```text
统计月份            = 2026-01
官方发布日期        = 2026-02-10
available_time      = 2026-02-10 10:00
decision_time       = 2026-02-10 close
execution_time      = 2026-02-11 open
```

### 9.4 同时间戳阶段协议

Timeline Engine 拥有统一阶段协议，MarketSemanticsProfile 只能声明市场特有事件的合法阶段，不能重新实现完整事件循环。

```text
1. BOUNDARY_PRE
   Session、规则切换和公司行为等边界前事件

2. MARKET_UPDATE
   Bar、Quote 和 Trade 更新市场状态

3. MATCH_RESTING
   使用当前市场事件撮合此前已经有效的订单

4. ACCOUNT_EVENT
   Funding、结算和其他计划账户事件

5. OBSERVATION_RELEASE
   available_time 已到的数据对 Strategy 可见

6. DECISION
   Strategy 产生 StrategyDecision 或 Order/Cancel Intent

7. PLAN_AND_SUBMIT
   Allocation、Risk、Position Sizing、Planning 和订单激活

8. MATCH_IMMEDIATE
   仅在 ExecutionModel 明确允许时撮合新订单

9. MARK_AND_SNAPSHOT
   Mark-to-market 并生成 PortfolioSnapshot
```

具体 Funding、公司行为或结算位于撮合前还是撮合后，由 MarketSemanticsProfile 根据真实市场规则声明。SimulationProfile 中的 ExecutionModel 决定新订单从哪个阶段开始具备模拟成交资格。

同一 UtcInstant 和 phase 内使用稳定的 `source_sequence`；它必须来自可重建的数据顺序或明确生成规则，不能依赖容器遍历顺序。Full trace 必须记录 epoch nanoseconds、phase 和 source sequence。无法证明同时间顺序时，decision-grade 运行失败关闭。

## 10. 事件模型

### 10.1 市场事件

- `SessionOpened`
- `SessionClosed`
- `AuctionStarted`
- `AuctionEnded`
- `BarOpened`
- `BarClosed`
- `QuoteUpdated`
- `TradePrinted`
- `FundingRatePublished`
- `FundingSettlementOccurred`
- `CorporateActionAnnounced`
- `CorporateActionEntitlementCaptured`
- `CorporateActionPositionAdjustmentApplied`
- `CorporateActionCashDistributionPaid`
- `SettlementOccurred`
- `ContractExpired`
- `RuleTimelineChanged`
- `InstrumentListed`
- `InstrumentDelisted`
- `InstrumentRenamed`
- `UniverseMembershipChanged`
- `TradingSuspended`
- `TradingResumed`

### 10.2 决策和订单事件

- `DecisionScheduled`
- `DecisionMade`
- `StrategyOutputValidated`
- `StrategyOutputValidationFailed`
- `DecisionBatchCompleted`
- `TargetApproved`
- `OrderPlanned`
- `OrderPlanSuperseded`
- `OrderIntentCreated`
- `MarketRuleValidated`
- `MarketRuleRejected`
- `PreTradeRiskApproved`
- `PreTradeRiskRejected`
- `OrderSubmitted`
- `OrderAccepted`
- `OrderRejected`
- `OrderActivated`
- `LiquidityBlockedAtLimit`
- `OrderPartiallyFilled`
- `OrderFilled`
- `OrderCancelRequested`
- `OrderCancelled`
- `OrderExpired`
- `OrderTerminatedByRunEnd`

### 10.3 账户事件

- `CapitalDeposited`
- `CapitalWithdrawn`
- `CapitalTransferred`
- `CashChanged`
- `PositionChanged`
- `FeeAssessed`
- `FeeCharged`
- `FinancingCharged`
- `MarginChanged`
- `EquityMarked`
- `LiquidationTriggered`
- `PostTradeRiskBreach`
- `IntegrityFinding`

事件是否完整持久化由 trace level 决定，但内部状态转换必须遵守统一语义。

## 11. 市场语义与模拟 Profile

### 11.1 ResolvedMarketSemanticsProfile

Trading Kernel 拥有真实市场与账户行为 Ports，包括 SessionModel、InstrumentModel、OrderRuleModel、FeeAssessmentPolicy、TaxPolicy、SettlementModel、PositionAccountingModel、FinancingModel、MarginModel、LiquidationRules、CorporateActionModel 和 CurrencyValuationPolicy。

`MarketSemanticsProfile` 是这些 Ports 的具体组合，是回测与实时共同使用的版本化市场事实集合。它必须声明 Execution Reference、Valuation、Margin、Liquidation 和 Settlement 各用途所需的 Price Stream，以及每类 Stream 的期望覆盖、合法 gap reason 和 `StaleMarkPolicy`；不适用的用途必须显式声明为 `not_applicable`。

```python
@dataclass(frozen=True)
class ResolvedMarketSemanticsProfile:
    profile_key: str
    profile_version: int
    profile_digest: str
    session_model: SessionModel
    instrument_model: InstrumentModel
    order_rule_model: OrderRuleModel
    position_accounting_model: PositionAccountingModel
    settlement_model: SettlementModel
    financing_model: FinancingModel
    margin_rules: MarginRules
    liquidation_rules: LiquidationRules
    corporate_action_model: CorporateActionModel
    market_fee_rules: MarketFeeRules
    tax_rules: TaxRules
    component_manifest: tuple[ProfileComponentRef, ...]
```

它描述市场是什么，不包含 Bar Fill、Slippage、Latency、Queue 或其他回测近似。

### 11.2 ResolvedSimulationProfile

Backtest Runtime 拥有模拟行为 Ports，包括 ExecutionModel、SlippageModel、LatencyModel、LiquidityModel、LiquidationAuditModel 和 CloseoutPolicy。

`SimulationProfile` 仅由 Backtest Runtime 使用，描述如何近似历史执行。Decision-grade SlippageModel 必须具有版本、校准证据和可机器验证的适用范围，禁止隐式零滑点。

```python
@dataclass(frozen=True)
class ResolvedSimulationProfile:
    profile_key: str
    profile_version: int
    profile_digest: str
    engine_kind: str
    execution_model: ExecutionModel
    slippage_model: SlippageModel
    slippage_calibration: CalibrationEvidence
    slippage_applicability: ApplicabilityEnvelope
    latency_model: LatencyModel
    liquidity_model: LiquidityModel
    intrabar_ambiguity_policy: IntrabarAmbiguityPolicy
    liquidation_audit_model: LiquidationAuditModel
    closeout_policy: CloseoutPolicy
    component_manifest: tuple[ProfileComponentRef, ...]
    random_stream_requirements: tuple[RandomStreamRequirement, ...]
```

Stochastic SimulationProfile 必须显式声明，并使用从 master seed、semantic component key、Instrument ID 和 purpose 派生的命名独立 RandomStream。禁止共享全局 RNG。

### 11.3 ResolvedExecutionAccountProfile

`ExecutionAccountProfile` 是回测与实时共同使用的版本化账户行为和合同集合，与期初经济状态分离。

```python
@dataclass(frozen=True)
class ResolvedExecutionAccountProfile:
    profile_key: str
    profile_version: int
    profile_digest: str
    venue_id: str
    account_type: str
    margin_mode: str
    leverage_policy: LeveragePolicy
    account_fee_schedule: AccountFeeSchedule
    cost_basis_policy: CostBasisPolicy
    permissions: AccountPermissions
    borrow_policy: BorrowPolicy | None
    component_manifest: tuple[ProfileComponentRef, ...]
```

`InitialAccountState` 只保存期初现金、Position Lots、待结算项目和必要成本基础，不保存账户行为规则。

### 11.4 ResolvedBacktestEnvironment

```python
@dataclass(frozen=True)
class ResolvedBacktestEnvironment:
    market_semantics: ResolvedMarketSemanticsProfile
    simulation: ResolvedSimulationProfile
    execution_account: ResolvedExecutionAccountProfile
    market_bundle_hash: str
    currency_valuation_policy: CurrencyValuationPolicy
    compatibility_report: EnvironmentCompatibilityReport
```

Backtest Runtime composition root 中的 `ProfileResolver` 根据 BacktestRequest、Profile Registries 和 MarketBundle capabilities 构造 ResolvedBacktestEnvironment。Resolver 只负责组合与兼容性验证，不实现市场规则、Fee、Accounting 或 Slippage。

Registry 必须验证至少以下兼容性：

- Instrument 类型与 PositionAccountingModel
- Instrument 类型与 Margin/LiquidationRules
- SettlementModel 与 SessionModel
- OrderRuleModel 与 Venue/Instrument
- FinancingModel、MarketFeeRules、TaxRules 和 AccountFeeSchedule 的结算币种
- ExecutionAccountProfile 的 Venue、账户类型、权限和 Margin mode 与 MarketSemanticsProfile 兼容
- SimulationProfile 的 Engine kind 与 Strategy family
- Execution/Slippage/Liquidity Model 要求的数据能力是否由 MarketBundle 提供
- MarketBundle 是否完整覆盖 MarketSemanticsProfile 声明的 PricePurpose
- LiquidationAuditModel 是否能消费 MarketSemanticsProfile 的 LiquidationRules
- CurrencyValuationPolicy 能否为全部非 Reporting Currency balance 解析唯一 Price Stream path
- SlippageModel 是否具有校准证据，且本次订单与市场状态位于 applicability envelope 内

任何会改变结果语义的组件版本、配置或代码身份变化都必须产生新的 digest。Decision-grade 只允许已注册且兼容性验证通过的三类 Profile；custom profile 必须降级为 development-grade。

G06 Fixture 使用的 `synthetic.cash.development.v1` 只存在于 TestProfileRegistry 或显式 `allow_development_profiles=True` 路径，默认 Production Profile Registry 不得注册。使用 Synthetic Profile 的 Evidence 必须记录 `synthetic_market_profile` limitation，且永远不能产生 decision-grade。真实 A 股/Binance Profile 不得继承 Synthetic Profile，只能实现相同 Ports。

FeeReservationEstimator 和 FeeAssessmentEngine 共同消费 MarketFeeRules、TaxRules 和 ExecutionAccountProfile 的 AccountFeeSchedule。前者产生非财务最坏承诺，后者产生最终权威 FeeAssessment。每个 Fee Journal Entry 必须记录所使用的市场规则、税费规则和账户 Profile identity。

### 11.5 SessionModel

负责时区、交易日历、Session 阶段、Decision schedule、开盘、午休、收盘和夜盘。

### 11.6 InstrumentModel

负责 Equity、Spot、Perpetual、Future、Option、base/quote currency、contract multiplier、tick size、lot/step size、expiry 和 long/short 能力。

Instrument 使用跨 Symbol 变化稳定的 `instrument_id`。Symbol、listing、delisting、分类和 Universe membership 是 point-in-time 属性；上市前 Instrument 不可观察，退市 Instrument 不得从历史 Bundle 删除。Delisting Position 必须由 SettlementModel 或 CorporateActionModel 明确处理。

### 11.7 OrderRuleModel

MarketSemanticsProfile 必须通过 `required_rule_dimensions()` 声明会影响结果的历史规则维度。MarketBundle 使用这些要求生成 `RuleCoverageReport`。

每条历史规则至少记录：

```text
instrument_id
effective_from
effective_until
source
source_hash
```

Decision-grade 要求每个必需维度在回测有效区间内无缺口、无重叠，并且任一模拟时点只能解析到唯一有效规则。禁止缺失时回退到当前规则或估算值。

OrderRuleModel 负责 `OrderCapabilitySet`、合法 Execution style、Price constraint、Time-in-Force、时点有效 `QuantityLattice`、最小数量、最小名义金额、Price limit、T+1 可卖数量、Suspension、Reduce-only、odd-lot close 和保证金前置规则。

### 11.8 ExecutionModel

属于 SimulationProfile，负责 Next-open/next-bar、OHLC path、Spread、Participation、Partial Fill、延迟生效和 L1/L2 Queue 等模拟行为。真实交易规则不能放入此模型。

Simulation Execution Adapter 和未来 Live Venue Adapter 都消费 canonical OrderIntent，并产生 `OrderTranslationReport`。Report 记录 Intent 语义、目标能力、映射结果和任何拒绝原因。Adapter 禁止静默把 Post-only、Reduce-only、TIF 或其他约束降级为不同语义；无法精确映射时必须 reject 或 BLOCKED。

### 11.9 PositionAccountingModel

负责将 Fill 和其他 Position 经济事实翻译为不可变 Accounting Journal Entry。不同 Instrument 使用不同实现，例如 `CashInstrumentAccounting`、`LinearDerivativeAccounting`、`InverseDerivativeAccounting` 和 `FuturesSettlementAccounting`。它理解合约乘数、PnL 公式和结算币种，但不能直接修改 Ledger State。

Cash Instrument Accounting 保留不可变 `AcquisitionLot`：lot ID、source fill ID、quantity、unit cost、allocated fees 和 acquisition time。卖出时由 ExecutionAccountProfile 的版本化 `CostBasisPolicy` 选择 FIFO、LIFO、Weighted Average 或 Specific Identification，并在 Journal Entry 中记录被消耗 Lot ID。不能为了平均成本投影丢弃原始 Fill/Lot provenance。

Derivative Entry Price 和 PnL 由具体 PositionAccountingModel 定义，不强行套用 Cash Instrument Lot 模型。

### 11.10 SettlementModel

负责 T+0/T+1、Settlement Obligation、可交易/可提现资金、可卖数量、Futures daily settlement、Contract expiry 和 rollover。T+1 等规则必须通过 SettlementBook 和 AvailabilityProjection 实现，不能只作为 Strategy 条件判断。

### 11.11 FinancingModel

负责 Crypto funding、Borrow fee、Margin interest、Futures carry 和现金利息。

Funding 使用两个不同事件：

- `FundingRatePublished` 是 Strategy 可观察的市场事件，具有 event time、available time 和目标 funding time。
- `FundingSettlement` 是账户经济事件，具有稳定 `funding_slot_id`、settlement instant、eligibility instant、applied rate、Funding Mark 和 settlement currency。

Funding Payment 使用 eligibility instant 的合格 Position 计算，并由 FinancingModel 生成唯一 `FundingApplied` Accounting Journal Entry。Applied Rate 不得在 available time 前暴露给 Strategy，不允许按 Bar 隐式均摊 Funding。

### 11.12 MarginRules 与 LiquidationRules

属于 MarketSemanticsProfile，表达真实 Initial Margin、Maintenance Margin、保证金层级和强平条件，不包含 Bar 数据下的近似判断。

### 11.13 LiquidationAuditModel

属于 SimulationProfile，决定如何根据当前数据粒度检查真实 LiquidationRules。

Bar Engine v1：

- Long 使用历史 Liquidation Mark Bar low 作为最不利价格检查。
- Short 使用历史 Liquidation Mark Bar high 作为最不利价格检查。
- 最不利价格下仍满足 Maintenance Margin 时结果为 `SAFE`。
- 可能跌破 Maintenance Margin 时结果为 `AMBIGUOUS_BREACH`。
- `AMBIGUOUS_BREACH` 使 decision-grade 运行失败关闭。
- Development-grade 可以显式选择近似强平模型，但必须记录模型和限制。

精确 Liquidation 需要足够粒度的历史 Liquidation Mark Price 或 Microstructure 数据。Trade Price OHLC 不得静默替代 Mark Price OHLC。

### 11.14 CorporateActionModel

负责现金分红、拆股和送转、除权除息生效时间、配股、Symbol migration 和合约换月。

公司行为使用生命周期事件：

- `CorporateActionAnnounced`：在 available time 后对 Strategy 可见。
- `EntitlementCaptured`：在 Record/Eligibility Instant 锁定历史合格 Position quantity。
- `PositionAdjustmentApplied`：在 Effective Instant 调整 Position Lot quantity 和 unit cost。
- `CashDistributionPaid`：在 Payment Instant 产生 Cash Journal Entry。

每个生命周期共享稳定 `corporate_action_id`。当前 Position 不能替代历史 Entitlement。拆股/送转默认保持总 Cost Basis 不变；Tax/withholding 由 Market Tax Rules 和 ExecutionAccountProfile 共同决定。

Execution、Market Rules 和 Accounting 必须使用原始可交易价格。拆股、送转和分红通过明确生命周期经济事实生成 Accounting Journal Entry，调整 Position quantity、cost basis 或 cash。

Strategy 可以通过 ObservationView 请求 point-in-time adjusted series，但调整只能使用在当前模拟时点已经公布或生效的公司行为。Vendor 预先生成的全历史复权序列不能直接作为 decision-grade 执行证据。

第一阶段 A 股至少支持现金分红、拆股/送转和除权除息生效时间。遇到尚未支持但会影响持仓或价格连续性的公司行为时，decision-grade 必须失败关闭。无公司行为的市场使用显式 No-op 实现，而不是空值分支。

## 12. 引擎划分

### 12.1 Bar/Portfolio Engine

Bar Engine 是无 Run Outcome 的确定性执行 Harness：

```text
ResolvedExecutionCase
        ↓
Bar Engine
        ↓
EngineExecutionResult
├── ExecutionTrace
├── Final Ledger State
├── Final PortfolioSnapshot
├── target_stream_digest
└── EngineTermination
```

Engine 不拥有 BacktestRequest resolution、Semantic Run ID、Attempt ID、FAILED/BLOCKED/CANCELLED 映射或 Canonical Evidence publication。它返回结构化 InputValidationFailure、EngineFailure 或 EngineCancellation。Backtest Runtime composition root 在 Engine 外部完成 Profile resolution 和 ExecutionCase 构建；Auditable Runner 负责 Run identity、Outcome mapping、Evidence、Integrity 和 atomic finalize。

适用：

- 日频、小时级和分钟级中低频策略
- 趋势、轮动、Carry、Cross-sectional
- 多资产组合

第一阶段唯一允许产生 decision-grade 结果的 Bar Execution Profile 是：

```text
next_eligible_bar_open.v1
```

ExecutionModel 只决定成交资格、ExecutionReferencePrice 和 full/partial/no-fill，不计算 Slippage 数值。独立 SlippageModel 根据 Side、Quantity、Reference Price 和允许的市场状态产生 `SlippageDecision`；每个 Decision 记录 model/calibration identity 和 applicability result。

规则：

- 只服务于 Portfolio Strategy 的再平衡订单。
- 决策产生的订单禁止在信号所属同一 Bar 成交。
- 订单最早在下一根满足 Session、交易状态、数据 availability 和 Order Rules 的真实 Bar open 成交。
- ExecutionModel 使用该 open 作为 reference price；SimulationProfile 中的版本化确定性 SlippageModel 独立计算 execution price，Fee 由 FeeAssessmentEngine 计算。
- 通过规则和资金检查后默认 full fill。
- 停牌、价格限制、数据终止或无合格 Bar 时，根据明确 TIF 产生 keep-active、liquidity-blocked 或 expire；流动性阻断不等同于 MarketRuleRejection。
- 不使用未来 Bar close、high 或 low 决定开盘成交价格。
- 不使用 forward-filled、合成或 gap placeholder Bar 成交。
- A 股方向敏感价格限制：Buy 在 upper-limit open、Sell 在 lower-limit open 时产生 `LiquidityBlockedAtLimit`；反方向可以继续评估。
- 不使用全天 Volume 推断涨跌停 Queue 成交；日频模型不在盘中打开价格限制后补成交。
- Bar 内 Stop、Limit、Queue、Partial Fill 和精确 Liquidation 不属于该 Profile 的能力。

后续可以增加 Limit、Stop、OHLC path 或 participation model，但在获得独立验证前只能产生 development-grade 结果。Liquidity Strategy 和做市不能使用 Bar Engine。

### 12.2 Microstructure Replay Engine

适用：

- Market making
- L1/L2 replay
- Queue position
- Partial fill
- Hedge execution
- Second-level execution

它接收 `LiquidityStrategy` 或 `ExecutionStrategy` 产生的 venue-neutral Order/Cancel Intent。

它与 Bar Engine 共用：

- Instrument、Order Intent、Order、Fill 和 Ledger 契约
- Market manifest
- Result、evidence 和派生 analysis 契约
- 费用与交易规则的权威定义

它不与 Bar Engine 强行共用：

- 内部事件队列实现
- 撮合状态
- Queue 模型
- 高频性能优化

Microstructure Engine 出现真实性能需求后可以增加版本化 `EngineCheckpoint`，内容至少包括 Timeline cursor、StrategyState、OrderState、ReservationBook、SettlementBook、Accounting state/journal hash、Market/Order Book state、RandomStream counters 和 Artifact offsets/hashes。

Checkpoint 只能在安全 Timeline Phase 边界创建。恢复必须创建新的 child Attempt，保留 parent Attempt 和 checkpoint identity；恢复结果必须与从头运行产生相同 execution result hash。旧 Attempt 不允许原地修改。

## 13. Accounting Ledger

`AccountingJournal` 是共享执行账户现金、持仓、费用和已实现 PnL 的唯一财务权威来源。`PortfolioSnapshot` 是 Journal 状态加当前 Market Marks 计算出的派生投影，可以缓存，但必须能够重建，不能覆盖或修改历史 Journal。

```text
Fill / Funding / Settlement / Corporate Action
                         ↓
       Instrument-specific Accounting Models
                         ↓
          Immutable Accounting Journal
                         ↓
              Generic Accounting Ledger
                         +
PricePurpose Streams → MarkResolver
                         ↓
             Native Currency Valuations
                         ↓
              CurrencyValuationGraph
                         ↓
             Reporting Currency Values
                         ↓
            PortfolioSnapshotProjector
                         ↓
                PortfolioSnapshot
```

Generic Ledger 不包含 `if instrument_type` 分支，不读取 MarketSemanticsProfile、ExecutionAccountProfile 或 Risk Policy。它只保证 Journal Entry schema、稳定 Entry ID 幂等、已注册 Account/Balance Key、Debit/Credit 或等价财务不变量以及确定性 replay。

Immutable Journal 使用 `(recorded_at, journal_entry_id.value)` 作为唯一稳定顺序。单次 append batch 可以无序输入，但在发布 cursor 后不得向既有 prefix 插入更早 Entry；否则历史 cursor 和 projection identity 将失去含义。相同 Entry ID 与相同 canonical content 是 no-op，相同 ID 与不同 content 是冲突。Replay cursor 同时携带已消费 Entry 数量和 prefix hash-chain identity，所有 replay range 使用半开区间并校验 position/hash，不能只信任整数 offset。空 Journal 从固定 genesis hash 开始，每个 prefix identity 只由前一 prefix hash 与当前 Entry canonical hash 推导。Journal Store/Replay 本身不计算 Cash、Position 或 PnL，也不拥有外部 mutable persistence。

`PositionAccountingModel`、`FinancingModel`、`SettlementModel` 和 `CorporateActionModel` 负责把市场特有经济事实翻译为 Journal Entry，但不能直接修改 Ledger State。是否允许负现金、Short Position、Margin exposure 或某项账户权限由 ExecutionAccountProfile、PreTradeRisk、MarginModel 和 AvailabilityProjection 决定，不由 Ledger 决定。

实际 Fill 即使暴露风险或权限违规也必须如实入账；系统随后产生 `PostTradeRiskBreach` 或 `IntegrityFinding`。禁止为了维持“合法状态”而丢弃已发生 Fill 或拒绝 Accounting。

Strategy Sleeve 级 PnL attribution 属于分析结果，第一阶段不作为独立财务账本。未实现 PnL 不写入 Journal，由当前 Position 和 Mark 派生。

第一阶段一个 Backtest Run 只允许一个 Execution Account 和一个 Reporting Currency。Journal Entry 仍必须保留 `account_id`、`venue_id` 和原生 `currency`，不能依赖“系统永远只有一个账户或币种”的隐式假设。

External Cash Flow 使用 `CapitalDeposited`、`CapitalWithdrawn` 和 `CapitalTransferred` 等明确事件，改变 Cash 和 Equity，但不计入 Trading PnL。每个事件具有稳定 ID、时间、原生币种、金额、来源和审批 provenance。第一阶段默认 timeline 为空，且不支持跨 Execution Account transfer。Strategy 不得在事件可用前观察未来资金流。资金流只影响后续 CapitalAllocationPolicy 计算，不自动重算已有 ActivePortfolioTarget。

`MarkResolver` 按 PricePurpose 和 UtcInstant 选择唯一合法 Mark，执行 StaleMarkPolicy，并禁止用 Execution Price 隐式替代 Valuation Price。缺失、歧义或过期 Mark 返回结构化失败。

`CurrencyValuationGraph` 把原生 Currency Balance 转换为 Reporting Currency。每条转换边引用 point-in-time Price Stream；存在多条路径时由版本化 `CurrencyValuationPolicy` 选择。Stablecoin 不默认 1:1，除非 Profile 明确提供版本化 Peg Valuation Policy。缺少路径或路径不唯一时 decision-grade 失败关闭。

`PortfolioSnapshotProjector` 只消费 Ledger State、Resolved Marks 和 Reporting Currency Valuations；它不查询数据源、不选择价格、不决定换算路径。

第一批 Binance USD-M 和 A 股 Profile 可以分别限制为主要单结算币种 USDT 和 CNY。多账户、跨 Venue 资金和 Consolidated Portfolio 留作后续独立扩展。

必须支持：

- 多币种现金
- 多 Instrument Position
- 多次 Fill
- 加仓、减仓和反向
- Partial close
- Realized/unrealized PnL
- Fee
- Funding/financing
- Contract multiplier
- Settlement
- Margin
- Liquidation
- Corporate action

禁止引擎和策略各自计算另一套 PnL。

接口组合建议：

```python
new_state = ledger.apply_entry(state, journal_entry)
rebuilt_state = ledger.replay(journal_entries)
resolved_marks = mark_resolver.resolve(price_view, price_purposes, utc_instant)
valuations = currency_valuation_graph.value(new_state, resolved_marks, reporting_currency)
snapshot = snapshot_projector.project(new_state, resolved_marks, valuations, utc_instant)
```

`apply_entry` 必须按稳定 Entry ID 幂等；重复应用同一经济事实不能产生重复现金、仓位或费用。Ledger 的状态转换和 Journal replay 必须使用小型事件 Fixture 独立测试。

这不意味着整个回测引擎采用 Event Sourcing。订单簿、指标缓存和其他引擎内部状态可以使用专门实现，只要求财务状态可从 Accounting Journal 重建。

## 14. 数据完整性和结果等级

### 14.1 Development Grade

允许显式近似，例如：

- 当前交易规则快照代替历史规则
- 固定滑点
- 使用 OHLC 假想路径处理 Stop/Limit
- 使用 Bar volume 近似 Partial Fill
- 使用无校准证据的 SlippageModel
- 缺少订单簿深度

但必须记录限制。

### 14.2 Decision Grade

要求：

- 完整 Market manifest
- 已生成并通过 `PriceStreamCoverageReport`、`MarketAvailabilityReport` 和 `UniverseCoverageReport`
- 所有非 Reporting Currency 余额具有唯一、完整的 Currency Valuation path
- 所有观察满足时间因果性和 point-in-time revision 规则
- MarketSemanticsProfile 声明的结果相关历史规则在有效区间内无缺口、无重叠且具有来源证据
- 已生成并通过 `RuleCoverageReport`
- SlippageModel 具有版本、校准证据，且所有 Fill 均位于适用范围
- 必需 Funding publication、settlement slot、eligibility instant 和 Funding Mark 完整
- 必需 Corporate action announcement、record/eligibility、effective 和 payment lifecycle 完整
- 确定性运行
- 无 blocking integrity issue

### 14.3 失败关闭条件

- MarketBundle hash 不匹配
- Backtest Run 访问网络、供应商 API 或未冻结可变数据源
- MarketSemanticsProfile、SimulationProfile 或 ExecutionAccountProfile 未注册、组件不兼容或 digest 不匹配
- 权威 Artifact 缺少 Schema version、Migration chain 不可用或旧 Artifact 被原地改写
- Canonical OrderIntent 不受 OrderCapabilitySet 支持或 Adapter 发生静默语义降级
- InitialAccountState 与 ExecutionAccountProfile 不兼容
- SlippageModel 缺少校准证据、使用隐式零滑点或订单超出 applicability envelope
- ExecutionModel 自行计算 Slippage、SlippageDecision identity 缺失或读取未来 Bar 字段
- Fill 直接承载唯一最终 Fee、FeeAssessment 重复/遗漏或 minimum commission 被按 Fill 重复收取
- Symbol/Instrument identity 冲突、未来上市 Instrument 提前可见或退市 Instrument 从历史 Universe 消失
- Strategy 绕过 ObservationView 构造 Universe，或 StaticUniverseSpec 冒充无幸存者偏差全市场结果
- Strategy 执行未经版本化 Resample、Bar 跨 Session 聚合或 BarDefinition/aggregation hash 缺失
- 时间倒序、重复或未分类/不允许的数据缺口
- 权威对象使用 naive/local datetime、DST 解析不明确或 TradingDate 由 UTC date 猜测
- 同一时间戳的 phase 或 source sequence 未定义
- 使用 `available_time > decision_time` 的数据
- Strategy 使用 Decision Time 之后才可见的 Revision，或 Vendor correction 原地覆盖旧数据
- Strategy/Simulation 使用全局 RNG、未注册 RandomStream 或 RandomStream derivation 无法重建
- Backtest Runtime 内训练/调参/候选选择，或 Strategy 使用 available time 晚于 Decision Time 的 ModelArtifact
- Strategy 绕过 ObservationView 读取外部市场数据或非确定性时钟
- Portfolio Strategy 读取账户 Cash/NAV/Margin、其他 Sleeve 或 Working Orders，或 Strategy Family 越权访问 Context capability
- Decision-grade 使用 editable install、不可确定源码、缺失依赖锁或 Build Artifact hash 不匹配
- Warmup 期间产生 OrderIntent、Fill、Accounting Journal Entry 或绩效结果
- Run end 使用隐式最后收盘价强平、缺少合法 Final Valuation Mark 或结束边界后的经济事件被计入结果
- Strategy LookbackRequirement 未满足或交易结束边界不是 exclusive
- 影响未来行为的 Strategy 状态无法序列化、恢复或 hash，或 Liquidity Strategy 维护第二套 Inventory
- 必需规则时间段缺失、重叠、来源不明或解析结果不唯一
- 历史规则缺失时回退当前规则或估算值
- Instrument 缺少明确的 PositionAccountingModel、MarginModel 或结算语义
- Bar LiquidationAudit 返回 `AMBIGUOUS_BREACH`
- 必需 PricePurpose 缺失、覆盖不足或模块使用错误用途的价格
- Execution 使用 forward-filled/合成 Bar，或 Valuation 使用未经 StaleMarkPolicy 批准的旧 Mark
- `MISSING`/`SOURCE_OUTAGE` 未阻断 decision-grade，或 gap reason 与 Session/Suspension 证据冲突
- 非 Reporting Currency 余额缺少估值路径、存在未决多路径或使用隐式 Stablecoin 1:1
- Decision-grade 中使用 PriceFallbackPolicy
- Funding publication、settlement slot、eligibility instant、Funding Mark 或 cutoff Position 证据缺失
- Funding slot 重复入账或 Applied Rate 在 available time 前暴露给 Strategy
- 公司行为 announcement、record/eligibility、effective 或 payment 证据缺失，类型不受支持，或使用当前 Position 替代历史 Entitlement
- 使用事后复权价格作为执行证据
- Settlement 无法完成、Obligation 重复/遗漏或 AvailabilityProjection 与 Settlement Rules 不一致
- Accounting 不平衡
- Accounting Journal 出现重复来源、非幂等 Entry 或无法重建 Snapshot
- Cash Instrument Lot provenance 丢失、CostBasisPolicy 未配置或 Journal 消耗不存在/重复的 Lot
- External Cash Flow 被计入 Trading PnL、缺少 provenance 或在事件发生前影响 Capital Allocation
- 非法订单状态转换、重复非幂等 Order Event 或无法从 Order Event Stream 重建 OrderState
- Decision-grade Bar 运行发生 same-bar fill 或使用未来 high/low/close/volume 决定开盘成交
- A 股在 upper-limit open 买入或 lower-limit open 卖出仍成交，或把流动性阻断误记为规则拒绝
- 数量舍入扩大已审批风险、Residual Policy 未配置或 Order Planner 再次隐式舍入
- RebalanceCoordinator 忽略 Working Order、重复规划未完成数量或新目标未取消冲突订单
- 同一 Decision Instant 按 Strategy 注册顺序逐个下单、暴露其他 Strategy 输出或使用部分完成 DecisionBatch
- Runtime Strategy 产生 Contract/Causality violation 却继续运行，或把正常 Portfolio Risk rejection 误判为 Contract failure
- Pre-trade Risk 修改订单，或 Capability Validation、Translation、Market Rule Evaluation、Fee/Resource Reservation、Pre-trade Risk 和 Submission 顺序颠倒
- Resource Reservation 重复冻结、释放不完整、终态订单仍占用资源或可用资源变成非法负值
- Target、OrderPlan 和 Venue Order 生命周期混用，或 superseded Plan 继续产生订单

上述可预期完整性和适用性条件产生 `BLOCKED`。未处理异常、实现不变量被破坏或 Artifact 持久化失败产生 `FAILED`，不得混用。

## 15. 结果、Outcome 与证据契约

`RunOutcome` 与 `ResultGrade` 是两个独立维度。

```text
PENDING → RUNNING → COMPLETED
                  ↘ BLOCKED
                  ↘ FAILED
                  ↘ CANCELLED
```

- `COMPLETED`：完整运行结束，才允许产生正式 BacktestResult，grade 可以是 development 或 decision。
- `BLOCKED`：预期内的数据完整性、因果性、模型适用性或市场歧义阻断，产生 BlockedRunReport。
- `FAILED`：系统缺陷、未处理异常、不变量实现错误或 Artifact 写入失败，产生 FailureReport。
- `CANCELLED`：由操作者或资源管理系统终止。

Partial metrics 只能标记为 diagnostic-only。Platform 不得把 BLOCKED、FAILED 或 CANCELLED 当成零收益或普通 Completed 样本。所有 Outcome 的 `deployment_authorized` 固定为 false。

Decision-grade 永久保存权威决策、执行、财务和完整性轨迹；大型 MarketBundle 不在每个 Run 中复制，而是通过不可变内容 hash 引用。

相同语义输入产生相同 `semantic_run_id`；每次实际执行产生独立 `attempt_id`。Completed canonical evidence 通过 staging 原子 finalize，此后不可修改。

标准运行目录：

```text
runs/<semantic-run-id>/
├── .publication.lock                  # operational exclusive lock；不进入 canonical hash
├── canonical/                         # 仅 atomic、immutable COMPLETED publication
│   ├── canonical-attempt-ref.json
│   ├── integrity.json
│   ├── result.json
│   └── publication-manifest.json
├── integrity-evaluations/
│   └── <evaluation-id>/               # post-integrity BLOCKED/FAILED immutable record
│       ├── integrity.json
│       ├── evaluation-outcome.json
│       └── publication-manifest.json
└── attempts/
    └── <attempt-id>/                   # independently atomic、immutable Attempt evidence
```

只有 `COMPLETED` 可以创建 `canonical/`。Integrity 的预期 blocking 产生独立 `BLOCKED` evaluation，execution-hash mismatch 产生独立 `FAILED` evaluation；二者都不得写 `result.json` 或占用 canonical destination。Evaluation 目录与 canonical 目录分别通过同一文件系统内 staging→rename 原子发布。

每个 Attempt 目录包含：

```text
<attempt-id>/
├── request.json
├── environment.json
├── build-artifact-manifest.json
├── schema-migration-manifests/
├── market-bundle-ref.json
├── bar-aggregation-manifest.json
├── corporate-action-lifecycle-events.jsonl
├── resolved-market-semantics-profile.json
├── resolved-simulation-profile.json
├── resolved-execution-account-profile.json
├── initial-account-state.json
├── external-cash-flow-events.jsonl
├── environment-compatibility-report.json
├── slippage-applicability-report.json
├── strategy-book-spec.json
├── model-artifact-manifest.json
├── model-revision-timeline.jsonl
├── random-stream-manifest.json
├── id-derivation-manifest.json
├── checkpoint-manifest.json             # future microstructure child attempt only
├── parity-report.json                    # migration/verification attempts
├── allocation-risk-execution-specs.json
├── observation-causality-audit.jsonl
├── revision-provenance-report.json
├── universe-coverage-report.json
├── strategy-state-checkpoints.jsonl
├── lookback-coverage-report.json
├── rule-coverage-report.json
├── price-stream-coverage-report.json
├── market-availability-report.json
├── valuation-staleness-report.json
├── currency-valuation-report.json
├── decision-candidate-payload-refs.jsonl
├── decisions.jsonl
├── strategy-output-validation.jsonl
├── decision-batches.jsonl
├── target-snapshots.jsonl
├── strategy-allocations.jsonl
├── portfolio-netting.jsonl
├── portfolio-risk-decisions.jsonl
├── normalized-targets.jsonl
├── active-portfolio-targets.jsonl
├── market-rule-decisions.jsonl
├── pre-trade-risk-decisions.jsonl
├── residual-decisions.jsonl
├── rebalance-decisions.jsonl
├── order-plans.jsonl
├── order-translation-reports.jsonl
├── order-events.jsonl
├── liquidity-block-events.jsonl
├── slippage-decisions.jsonl
├── reservation-events.jsonl
├── settlement-obligations.jsonl
├── availability-checkpoints.jsonl
├── fills.jsonl
├── fee-assessments.jsonl
├── accounting-journal.jsonl
├── position-lots.jsonl
├── portfolio-checkpoints.jsonl
├── funding-events.jsonl
├── financing.jsonl
├── liquidation-audit.jsonl
├── final-portfolio-snapshot.json        # future full-trace expansion; G07 v1 is inside Engine result envelope
├── run-end-report.json                  # future full-trace expansion; G07 v1 is inside Engine result envelope
├── blocked-run-report.json              # BLOCKED only
├── failure-report.json                  # FAILED only
├── cancellation-report.json             # CANCELLED only
└── evidence-manifest.json
```

`integrity.json`、`result.json`、`canonical-attempt-ref.json`、evaluation outcome 和 publication manifest 只属于 run-level publication，不得追加到 WP-07C 已 atomic-finalize 的 Attempt 目录。上表中的细粒度 full-trace 文件是后续 Evidence schema 扩展目标；G07 v1 Attempt exact coverage 以 WP-07C ArtifactEnvelope 集合为准。

派生分析独立存放，不修改 immutable canonical evidence：

```text
analyses/<semantic-run-id>/<metric-profile-digest>/
├── metric-profile.json
├── metrics.json
├── analysis-evidence.json
└── analysis-artifact-hash.json
```

MarketBundle 必须在 Retention Policy 下保持可取回。如果引用的数据包已经丢失，即使运行目录仍存在，该运行也不再是 Rebuildable。G07 v1 的 caller-supplied `DeterministicRebuildEvidence` 必须 canonically 绑定 Request、Resolved Environment、BuildArtifactManifest、MarketBundle manifest/retention proof、TargetStream digest、ExecutionCase identity manifest、Execution trace hash/level 和 execution result hash；`CanonicalAttemptRef` 绑定该 evidence hash，不能只保存布尔 `rebuildable=true`。

### 15.1 Completed Result 最小结构

```json
{
  "schema_version": 1,
  "semantic_run_id": "...",
  "attempt_id": "...",
  "outcome": "COMPLETED",
  "request_hash": "...",
  "execution_result_hash": "...",
  "evidence_manifest_hash": "...",
  "result_grade": "development",
  "deployment_authorized": false,
  "integrity": {
    "blocking": [],
    "limitations": []
  }
}
```

只有 Auditable Runner 可以发布 BacktestRunOutcome。EngineExecutionResult 不是 Completed Result；Evidence atomic finalize 和 Integrity validation 成功前不得发布 `COMPLETED`。

### 15.2 Canonical publication hash DAG

```text
finalized Attempt evidence + AttemptExecutionHash + DeterministicRebuildEvidence
                              ↓
                 canonical-attempt-ref.json
                              ↓ ref hash
integrity closed-attempt-set + canonical ref + retention/rebuild checks
                              ↓
                       integrity.json
                              ↓ integrity hash
                         result.json
                              ↓
                 publication-manifest.json
```

- `canonical-attempt-ref.json` 不引用 Integrity、Result 或 Publication Manifest；它绑定 canonical Attempt identity/ordinal、Attempt Evidence Manifest hash、AttemptExecutionHash artifact/content hash、execution result hash、Bundle/Trace/Rebuild evidence 和 final ExecutionCase identity。
- `integrity.json` 绑定 closed Attempt set hash、全部 eligible Attempt 的 evidence/execution hash tuple、canonical Attempt ref hash、blocking/limitation 和 grade inputs；不引用 Result 或 Publication Manifest。
- `result.json` 绑定 canonical Attempt ref hash、Integrity hash、request/execution identity、Outcome/grade 和 `deployment_authorized=false`；不引用 Publication Manifest。
- `publication-manifest.json` exact-cover 同目录其他权威文件及其 schema/content hash，是 DAG root；任何子文件都不得反向引用 manifest hash。
- BLOCKED/FAILED integrity evaluation 使用独立 DAG：closed Attempt set → Integrity → EvaluationOutcome → evaluation PublicationManifest；它没有 `canonical-attempt-ref.json` 或 `result.json`。

### 15.3 Semantic Run、Attempt 与领域 ID

```text
semantic_run_id = hash(
    normalized request including ID-free ExecutionCaseSemanticSpec hash
    + MarketBundle hash
    + all profile digests
    + BuildArtifactManifest hash
)
```

- 相同语义输入必须得到相同 semantic run ID。
- 每次实际执行使用不同 attempt ID，Attempt 之间不得覆盖。
- Bar Engine v1 的 FAILED/CANCELLED Attempt 不支持 in-place resume；Auditable Runner 重试时创建新 Attempt 并从初始 ResolvedExecutionCase 运行。
- G07 v1 的 `COMPLETED` closure 至少需要两个 finalized `READY_FOR_INTEGRITY` Attempt。Publisher 在获取 run-level exclusive lock 后 exact-cover 当时全部 eligible Attempt；execution result hash 必须完全一致，canonical Attempt 固定选择最小 ordinal。
- `canonical/` 原子发布后 Semantic Run 永久关闭：Evidence Writer 拒绝新 Attempt，Runner 只能返回 cache hit；同一 Semantic Run 的 post-publication parity/revocation 不在 v1 内，不能绕过 closure 继续写入。
- closure 前发现 execution hash mismatch 产生独立 durable `FAILED` integrity evaluation，不得选择 winner。少于两个 eligible Attempt 或其他预期 Integrity deficit 产生独立 durable `BLOCKED` evaluation。
- v1 filesystem threat model 固定为 trusted cooperative single-writer：受控本地同一文件系统、同一个 run-level exclusive lock 和 staging→rename。锁不得按 wall clock 自动回收；shared/adversarial filesystem、NFS/object-store rename 语义、symlink 攻击和恶意并发写者明确不支持，不能用于 decision-grade publication。
- `ExecutionCaseSemanticSpec` 必须在领域 ID 派生前冻结，且不得包含 Order、OrderEvent、Fill、FeeAssessment、SettlementObligation、JournalEntry 等派生 ID 或 final ExecutionCase hash。它必须 exact-cover 所有行为相关的 typed execution input，包括 Slippage calibration/configuration，而不能只绑定省略参数的端口描述。
- Spec 同时冻结 role-aware `identity_plan`：每个 Case role 显式绑定 identity type、Domain kind、semantic key 和 ordinal。Factory 只能按 role 请求身份，不能由 builder 在派生时重新选择 key/ordinal；Plan 任一变化都会先改变 Semantic Run ID。
- Composition root 先由 ID-free Spec 生成 Semantic Run ID，再用 semantic run namespace、role-aware identity plan 和稳定 ordinal 确定性派生领域 ID，最后构造完整 `ResolvedExecutionCase`。Final case hash 独立进入 Attempt/Engine evidence，不回流到 Semantic Run ID preimage。
- `ResolvedExecutionCase` 同时保存完整 Semantic Spec、其 hash 和 Identity Manifest。Composer 与 Runner 都从最终 Case 重新计算 ID-free Spec，校验 Request/Spec/Case、Order parent→NormalizedTarget 关系、Manifest derivation plan 和 Case role exact coverage 后，才允许 Engine 执行。
- Order、OrderEvent、Fill、FeeAssessment、SettlementObligation 和 JournalEntry 等模拟领域 ID 使用 semantic run namespace、causation 和稳定 ordinal 确定性派生。
- Attempt ID 是独立操作身份，不进入模拟领域 ID。
- Live Adapter 同时保存内部 canonical ID 和 Venue ID。
- ID algorithm 和 namespace version 进入 Schema/Build identity。

### 15.4 Schema 演进

每个权威 Artifact 都有独立 `schema_version`。第一阶段先实现 Artifact Envelope v1、Schema Catalog、当前版本 Writer/Reader dispatch 和 unknown-version fail-closed。只有出现真实 immutable 旧 Artifact 和明确 source/target Schema 后，Reader 才增加显式、纯、单向的 migration chain；禁止为了框架测试发明虚构旧版本。

```text
original artifact v1 + original hash
             ↓ explicit migration
canonical view v3 + migration manifest
```

原始 Artifact 和 Evidence Manifest 永远保留，不允许原地升级。首个真实 Migration 必须记录 source/target schema、migration chain 和 migration code hash。Legacy 对象如果不是旧 Artifact Schema，应通过 Legacy Adapter、Comparator Contract 和 ParityReport 迁移，不能伪装成 Schema Migration。

Schema Migration 只能处理结构表达变化。如果 Instrument、Accounting、Order 或其他经济语义发生变化，必须建立新领域类型、Profile 或语义版本，不能通过 migration 静默重新解释旧证据。Parity 工具可以把不同版本显式迁移到共同 Canonical View 后比较。

### 15.5 权威 Hash

- `request_hash`：覆盖全部规范化语义输入及其引用 identity。
- `execution_result_hash`：覆盖影响交易和财务结果的规范化 Decision、Allocation、Risk、Order、Fill、Journal 和最终 Snapshot 轨迹。
- `evidence_manifest_hash`：覆盖本次运行所有权威证据 artifact 的路径、角色、schema version 和内容 hash。

图表、展示格式和可重建 Metrics 的变化不应改变 `execution_result_hash`。

### 15.6 派生 Metrics

Metrics 不属于 Backtest Engine 的权威状态，而是以下输入的版本化派生分析：

```text
Accounting Journal
+ MarketBundle
+ Valuation Marks
+ MetricProfile
        ↓
Derived Metrics
```

`MetricProfile` 必须声明 valuation schedule、return method、annualization basis、risk-free source、cash-flow treatment、drawdown sampling、reporting currency 和 benchmark。每份分析具有独立 `metric_profile_digest` 和 `analysis_artifact_hash`。

同一个 execution result 可以派生多个 MetricProfile 结果。Promotion Gate 必须指定接受的 MetricProfile；跨市场比较前必须验证 Profile 兼容性。派生分析不能回写或改变 immutable canonical run evidence。

### 15.7 Trace Level

- `summary`：仅允许 completed development-grade，保存请求、引用、最终结果和限制。
- `full_trace`：保存权威决策、执行、Journal、Checkpoint 和完整性证据。
- `microstructure_trace`：在 full trace 上增加必要的 Queue 和撮合诊断；原始 Quote/Trade 仍优先引用 MarketBundle。

Decision-grade 必须使用 `full_trace` 或 `microstructure_trace`。

PortfolioSnapshot checkpoint 至少在决策后、成交后、结算后和运行结束生成。Final Snapshot 必须区分 Realized/Unrealized PnL，并记录未平仓 Position、Margin exposure、结束前最后合法 Valuation Mark identity 和被 Run End 终止的 Working Orders。其他时点 Snapshot 可以由 Journal 与 MarketBundle 重建，不要求永久保存。

## 16. 确定性和性能

### 16.1 确定性

Decision-grade 使用不可变 `BuildArtifactManifest` 定义实际执行代码身份。Manifest 至少记录 Strategy、Trading Domain、Trading Kernel、Backtest Runtime 和 Profile component 的 Artifact hash，依赖 lock hash，Python/NumPy 等结果相关运行库版本，以及可选 container image digest。Git commit 只作为 provenance，不是唯一代码身份。

主机名、绝对路径和运行时间等不影响语义的 Attempt 信息不进入 semantic run ID。Dirty source 只有在打包成不可变内容寻址 Artifact 后才能被准确记录；正式 decision-grade 禁止无法确定内容的 editable install。

- 所有随机行为必须使用 master seed 派生的命名独立 RandomStream。
- RandomStream 使用版本化 counter-based RNG 或等价可定位算法，记录 algorithm、version、stream key 和 seed derivation。
- 新增其他组件的随机调用不得改变现有 Stream 结果。
- 一个 master seed 表示一个模拟场景；多 Seed 稳健性由外部 Experiment/Promotion 层创建多个 Semantic Run。
- 配置和结果采用 canonical serialization。
- Typed scaled integer 必须显式序列化 `units`、`scale` 和领域 identity，禁止转成 JSON 浮点数。
- `Decimal` 仅允许用于字符串解析、外部格式转换和参考测试。
- Analytics float64 进入 StrategyDecision 时必须经过版本化 QuantizationPolicy。
- 相同 request、MarketBundle、market semantics digest、simulation digest、execution account digest 和代码版本应产生相同 execution result hash。
- Order、Fill、Fee、Settlement 和 Journal ID 必须按因果链与稳定 ordinal 确定性生成。
- 同一 semantic run 的 Completed attempts 必须产生相同 execution result hash。
- 权威交易计算不得依赖平台相关的二进制浮点舍入结果。
- 同 UtcInstant 事件必须按 `(epoch_nanoseconds, phase, source_sequence)` 稳定排序。
- MarketBundle 分区、Reader batch size 和存储 Adapter 变化不得改变事件顺序或 execution result hash。
- Engine 不读取系统当前时间决定业务行为。

### 16.2 性能分层

- 低中频优先保证语义正确和 traceability。
- Runtime 使用流式 EventCursor 和有界 Observation cache，不假设 MarketBundle 可以完全载入内存。
- Metrics 由独立 analysis runtime 从 Journal、MarketBundle 和 MetricProfile 派生。
- Bar Engine 可对纯指标计算使用向量化，但账户和订单状态转换保持权威语义。
- Microstructure Engine 可以采用专门的数据结构和批处理优化。
- 任何 fast path 都必须通过黄金 Fixture 与权威路径做 parity。

## 17. 初始市场 Profile

### 17.1 Binance USD-M Perpetual

```yaml
market_semantics_profile: crypto.binance_usdm.v1
semantics:
  session_model: continuous_24x7
  instrument_model: linear_perpetual
  order_rule_model: binance_historical_rules
  position_accounting_model: linear_derivative
  settlement_model: realtime
  financing_model: historical_funding
  market_fee_rules: binance_usdm_fee_structure
  tax_rules: none
  margin_rules: exchange_margin_tiers
  liquidation_rules: binance_usdm_tiered
  corporate_action_model: none
  price_streams:
    execution_reference: raw_trade_bar
    valuation: historical_mark_price
    margin: historical_mark_price
    liquidation: historical_mark_price
    settlement: exchange_settlement_mark

simulation_profile: bar.next_eligible_open.conservative.v1
simulation:
  engine_kind: bar
  execution_model: next_eligible_bar_open.v1
  slippage_model: deterministic_bps.v1
  latency_model: next_bar_eligibility.v1
  liquidity_model: full_fill_after_rules.v1
  liquidation_audit_model: conservative_intrabar_audit.v1

execution_account_profile: binance.usdm.vip0.cross.v1
account:
  account_type: derivatives
  margin_mode: cross
  leverage_policy: configured_per_instrument
  account_fee_schedule: vip0_timeline
  cost_basis_policy: not_applicable
  permissions:
    long: true
    short: true
```

关键场景：

- Funding 跨期持仓
- Long/short
- Step size 和 min notional
- Cross margin
- Intrabar LiquidationAudit：SAFE 或 AMBIGUOUS_BREACH
- Rule timeline 变化

### 17.2 A 股

```yaml
market_semantics_profile: equity.cn_a_share.v1
semantics:
  session_model: cn_exchange_calendar
  instrument_model: cash_equity
  order_rule_model: board_aware_price_limits
  position_accounting_model: cash_instrument
  settlement_model: cash_t0_position_t1
  financing_model: none
  market_fee_rules: exchange_mandatory_fees
  tax_rules: historical_stamp_duty
  margin_rules: cash_only
  liquidation_rules: none
  corporate_action_model: cn_equity_actions.v1
  price_streams:
    execution_reference: raw_tradable_open
    valuation: raw_tradable_close
    margin: not_applicable
    liquidation: not_applicable
    settlement: raw_settlement_price
  strategy_adjustment: point_in_time_optional

simulation_profile: bar.next_eligible_open.conservative.v1
simulation:
  engine_kind: bar
  execution_model: next_eligible_bar_open.v1
  slippage_model: deterministic_bps.v1
  latency_model: next_bar_eligibility.v1
  liquidity_model: full_fill_after_rules.v1
  liquidation_audit_model: none

execution_account_profile: cn_broker.cash.standard.v1
account:
  account_type: cash_equity
  margin_mode: none
  account_fee_schedule: broker_commission_with_minimum
  cost_basis_policy: configured_cash_instrument_policy
  permissions:
    long: true
    short: false
```

关键场景：

- 100 股手
- 当日买入不可卖
- 涨停买入和跌停卖出
- 停牌
- 印花税
- 现金分红、拆股/送转和 point-in-time 复权

这两个市场差异足够大，可用于验证 MarketSemanticsProfile 接缝以及同一 SimulationProfile 的跨市场复用是否真实成立。

## 18. 测试策略

### 18.1 契约测试

- UtcInstant canonical serialization、DST 重复/缺失本地时间、夜盘 TradingDate 和 point-in-time Revision selection
- Point-in-time Universe、listing/delisting、Symbol rename 和 survivorship-bias fixture
- RuleTimeline 无缺口、无重叠和唯一解析
- PricePurpose 隔离与 PriceStreamCoverageReport
- Gap classification、禁止 forward-fill execution 和 StaleMarkPolicy max-age
- CurrencyValuationGraph 唯一路径、Stablecoin 非隐式 peg 和 PortfolioSnapshot 换算
- StrategyState canonical round-trip、checkpoint restore 和命名 RandomStream replay
- Random Stream independence：新增无关随机调用不改变其他组件结果
- Immutable StrategySpec/ModelArtifact、training cutoff 和 walk-forward ModelRevisionTimeline
- Portfolio/Liquidity/Execution Strategy Context capability isolation
- StrategyOutputValidator：runtime violation→FAILED、precomputed input violation→BLOCKED、economic limit→Portfolio Risk
- Warmup 禁止交易副作用、LookbackCoverageReport 和半开区间边界
- 默认 Mark-to-market 结束、Working Order termination 和显式 CloseoutPolicy
- Run Outcome 状态机以及 BLOCKED/FAILED/CANCELLED 不产生 Completed Result
- Semantic run ID 稳定性、attempt 隔离、cache hit、并发 dedup 和 canonical atomic finalize
- Deterministic domain ID derivation、重复经济内容不碰撞和跨 Attempt ID parity
- Bar retry 从头重跑；未来 EngineCheckpoint child attempt 与 full replay parity
- BuildArtifactManifest 内容寻址、editable install 阻断和 Artifact hash 验证
- Schema Registry、单向 Migration、原始 hash 保持和跨版本 Canonical View parity
- 分层 ParityContract、无全局 epsilon 和 first-divergence report
- G01–G03 模块级 source provenance/parity，不把基础语义比较推迟到端到端阶段
- MarketBundle Builder source snapshot/normalization provenance 与 Runtime offline enforcement
- In-memory/Parquet 不同 Reader Adapter 和 batch size 的事件顺序/result parity
- BarDefinition Session anchor、夜盘 TradingDate、午休和 empty interval aggregation fixture
- 同一 execution result 派生多个 MetricProfile 且不改变 canonical evidence
- Profile required rule dimensions 与 MarketBundle coverage 匹配
- Synthetic Profile 默认 Production Registry lookup 失败、显式 development opt-in 和固定 limitation
- Canonical hash
- Canonical OrderIntent capability validation、Translation Report 和禁止静默降级
- Order Event Stream 幂等应用、合法状态转换和 OrderState replay
- PlanningOmission、PreTradeRiskRejection、MarketRuleRejection、ExecutionRejection 和 DataIntegrityFailure 分类
- Portfolio Risk clamp trace，以及 Pre-trade Risk 只能 approve/reject 的不变量
- Reservation Book 从 Order Event replay、partial fill 缩减和终态零泄漏
- SettlementBook replay、T+1 sellable quantity、tradable/withdrawable cash 和 AvailabilityProjection
- Fill reference price、SlippageDecision amount 和成交价一致
- ExecutionModel 与 SlippageModel 职责隔离、ApplicabilityEnvelope 和显式 zero-slippage limitation
- Per-fill/per-order FeeAssessment、minimum commission、tax 和 FeeCharged 幂等
- Slippage applicability envelope 边界和越界失败
- Fill 和 Accounting Journal 平衡
- 已发生但违反账户权限/风险的 Fill 仍完整入账，并产生 PostTradeRiskBreach/IntegrityFinding
- FIFO/LIFO/Weighted Average/Specific Identification Lot consumption fixture
- Funding publication causality、eligibility Position、slot 幂等和 Journal booking
- External Cash Flow 与 PnL 分离、Capital Allocation 更新和 MetricProfile cash-flow treatment
- Corporate Action historical entitlement、position adjustment、payment 和 tax lifecycle
- Journal 幂等应用和 Snapshot replay
- Result schema

### 18.2 多策略聚合 Fixture

至少验证：

1. 同一 Decision Instant 的 Strategy 注册顺序变化不改变 DecisionBatch、净目标和订单。
2. 两个 Sleeve 对同一 Instrument 提出相反目标。
3. Portfolio Allocation 根据各自 Strategy Allocation NAV 转换名义暴露。
4. 相反暴露在下单前净额化。
5. Account Ledger 只记录账户级订单、成交和持仓。
6. Sleeve attribution 不改变账户权益。

### 18.3 市场 Profile 黄金 Fixture

Binance Fixture：

1. 开多仓。
2. 观察 FundingRatePublished，并在 eligibility instant 保持仓位后经历 FundingSettlement。
3. 部分平仓。
4. 价格不利变化但最不利 extreme 下仍为 `SAFE`。
5. 构造可能触发强平的 Bar 并验证 `AMBIGUOUS_BREACH` 阻断 decision-grade。
6. 验证 margin、PnL 和 equity。

A 股 Fixture：

1. T 日开盘买入。
2. T 日尝试卖出并被拒绝。
3. T+1 日 upper-limit open 尝试买入，验证 `LiquidityBlockedAtLimit` 且不使用全天 Volume 补成交。
4. 应用 Announcement、Entitlement、Ex/Effective 和 Payment 完整现金分红及拆股/送转生命周期。
5. 验证 Execution 仍使用原始价格，Strategy 可按 point-in-time 观察复权序列。
6. T+1 日卖出已有持仓。
7. 验证 lot、印花税、可卖数量、数量调整和现金。

### 18.4 Parity 测试

采用分层 `ParityContract`：

- 新架构内部的 TargetSnapshot、Normalized Target、OrderIntent、Order Event、Fill Price/Quantity、FeeAssessment、Accounting Journal 和 Final PortfolioSnapshot 在规范化后要求 exact parity。
- 旧系统迁移为每个字段显式选择 `exact`、`quantized-equal`、`ordered-sequence-equal`、`explicit-tolerance` 或 `known-intentional-change` Comparator，禁止全局 epsilon。
- Metrics 只在明确 MetricProfile 下比较，并区分 Execution、Accounting 和 MetricProfile 差异。

`ParityReport` 必须记录 first divergence、affected domain、expected/actual、comparator、source provenance 和 intentional change reference。

具体迁移：

- 从 `crypt-gemini` 抽取策略和回测场景。
- 从 `cycle-rotation-platform` 抽取 A 股 T+1 和订单规划场景。
- 比较 decisions、normalized targets、orders、fills、fees、journal、positions 和 PnL。
- 不只比较最终收益率。

### 18.5 性质测试

- 无成交时现金和持仓不变。
- Fee 不能增加账户权益。
- Full close 后 Position quantity 为零。
- TargetSnapshot 重放不会累加为增量仓位。
- Price/NAV/External Cash Flow 变化不会隐式重算 ActivePortfolioTarget Quantity。
- Next eligible bar open 模型不会发生 same-bar fill。
- A 股价格限制开盘阻断具有方向敏感性并触发后续 Rebalance。
- 成交价不依赖成交时点之后的 Bar 字段。
- 新 TargetSnapshot 省略的旧目标被归零。
- 不允许卖出超过可卖数量。
- 缺少必需数据时 decision-grade 不得成功。

## 19. 建议代码组织

逻辑模块先于物理仓库拆分。第一阶段在当前 `backtest/` 仓库中建立五个可独立打包和测试的 Python package：

```text
backtest/
├── packages/
│   ├── trading-domain/
│   │   ├── pyproject.toml
│   │   └── src/crypto_quant_domain/
│   ├── trading-kernel/
│   │   ├── pyproject.toml
│   │   └── src/crypto_quant_trading/
│   │       ├── ports/
│   │       │   ├── market_semantics.py
│   │       │   ├── accounting.py
│   │       │   ├── settlement.py
│   │       │   └── risk.py
│   │       ├── allocation/
│   │       ├── risk/
│   │       ├── planning/
│   │       ├── accounting/
│   │       ├── profiles/
│   │       │   ├── binance_usdm/
│   │       │   └── cn_a_share/
│   │       └── execution_account_profiles/
│   ├── market-data-contracts/
│   │   ├── pyproject.toml
│   │   └── src/crypto_quant_market_data/
│   │       ├── manifests/
│   │       ├── readers/
│   │       ├── cursors/
│   │       └── repository/
│   ├── market-bundle-builder/
│   │   ├── pyproject.toml
│   │   └── src/crypto_quant_bundle_builder/
│   │       ├── source_adapters/
│   │       ├── normalization/
│   │       ├── validation/
│   │       └── publishing/
│   └── backtest-runtime/
│       ├── pyproject.toml
│       └── src/crypto_quant_backtest/
│           ├── runner/
│           ├── timeline/
│           ├── observations/
│           ├── engines/
│           │   ├── bar/
│           │   └── microstructure/
│           ├── simulation/
│           │   ├── ports.py
│           │   └── profiles/
│           │       ├── bar/
│           │       └── microstructure/
│           ├── evidence/
│           └── analysis/
├── tests/
│   ├── support/
│   │   └── synthetic_market/
│   │       ├── profile.py
│   │       ├── bundle_factory.py
│   │       ├── target_factory.py
│   │       └── expected_evidence.py
│   ├── domain/
│   ├── trading_kernel/
│   ├── market_data/
│   ├── bundle_builder/
│   ├── backtest_runtime/
│   ├── markets/
│   ├── parity/
│   └── fixtures/
└── docs/
```

固定依赖方向：

```text
crypto_quant_domain ← crypto_quant_trading ← crypto_quant_backtest
crypto_quant_domain ← crypto_quant_market_data ← crypto_quant_backtest
crypto_quant_market_data ← crypto_quant_bundle_builder
```

`crypto_quant_backtest` 只依赖 `crypto_quant_market_data` 的只读 Bundle Repository contract，不依赖 `crypto_quant_bundle_builder` 或在线 Source Adapter。

五个 package 稳定后再决定是否拆为独立 Git 仓库。Live Runtime 只能依赖 Trading Domain 和 Trading Kernel。现有 `crypto-quant-core` 中可复用的契约必须通过 provenance 和 parity 迁移，不能复制后形成双权威实现。

## 20. 与现有项目的关系

### 20.1 `crypto-quant-core`

现有项目作为契约和核算语义的迁移来源，而不是与新 Trading Domain/Kernel 并存的第二套权威实现。

候选迁移内容：

- Instrument、Order、Fill、Money 等基础契约
- Canonical serialization
- Causality guard
- Accounting primitives
- Exchange rule primitives

迁移后需要补齐：

- 不可变 Accounting Journal 和幂等 Entry
- Journal replay 与派生 PortfolioSnapshot
- Instrument-specific PositionAccountingModel
- Linear/Inverse derivative 核算语义
- 多 Fill 和 Partial close
- 多币种现金
- Margin 和 Financing

Hummingbot DTO 不进入 Trading Domain。迁移完成后应选择单一权威 package，并删除或弃用旧定义。

### 20.2 `crypto-quant-platform`

应负责：

- 构建 BacktestRequest
- 选择 Strategy、MarketSemanticsProfile、SimulationProfile 和 ExecutionAccountProfile
- 调用回测系统
- 注册运行证据
- 执行 Promotion Gate

不应继续扩展自己的简化回测实现。

### 20.3 `crypt-gemini`

作为迁移来源：

- `research/hummingbot_audited/`
- `research/blend_v2/`
- `research/mm_l1_replay/`
- Binance historical rule evidence
- Funding 和因果性实现

迁移必须保留 base commit、源文件 hash、Migration Mode、Comparator contract 和 parity Fixture。迁移来源仓库是否 dirty 不构成资格条件；所有来源都按声明范围冻结内容寻址 Source Snapshot。范围内使用 Snapshot 时的实际文件字节，可以包含 modified/untracked 文件；范围外 dirty 内容不进入 Snapshot。Base commit 和 clean/dirty 状态只作为 provenance，aggregate snapshot hash 是唯一权威来源身份。

基础数值、契约和 Accounting 的 Parity 必须在对应 G01–G03 Work Package 中完成模块级验证，不能等待市场 Profile 或端到端 G12。G12 只承担真实 MarketBundle、完整策略和端到端 Parity。

### 20.4 `cycle-rotation-platform`

作为 A 股语义来源：

- T+1 和 next-open 执行
- Lot size
- Position planning
- Risk gate
- Traceable backtest run bundle
- Promotion registry

借鉴其证据治理方式，但不复制 `operations` 和 Strategy 之间的反向依赖。

## 21. 实施阶段

本节只保留高层路线。可独立合并的 Work Package、依赖 Gate、失败边界和逐项验收标准见：

- `docs/implementation/target-driven-bar-v1-plan.md`
- `docs/implementation/acceptance-matrix.md`

实现不得把本节任一“阶段”作为单一大任务；必须按详细计划中的 WP/Gate 交付。只有 Acceptance Matrix 状态为 `READY` 的 Work Package 才允许实现；`PASSED` 必须记录 immutable commit、实际验收命令和 Artifact hash。

### 阶段 0：架构冻结

- 确认领域词汇。
- 建立 Legacy Migration Source Map，冻结 `crypto-quant-core`、`crypt-gemini` 和 `cycle-rotation-platform` 的 immutable source identity。
- 建立 Comparator Contracts 和模块级 ParityReport Harness。
- 确认模块依赖图。
- 确认 BacktestRequest/Result schema。
- 确认 Warmup、半开交易区间、时间和结果等级语义。

### 阶段 1：Foundation（G00–G03）

- 建立五个独立 package 和依赖护栏。
- 冻结 Legacy source identity 与模块级 Parity Harness。
- 实现 Typed Scaled Integer、UtcInstant、确定性 ID 和 Canonical Envelope。
- 建立 Candidate/Validated Domain contracts 与 Profile Ports。
- 实现 Journal/Ledger、MarkResolver、CurrencyValuationGraph、PortfolioSnapshotProjector 和 Cash Accounting。

### 阶段 2：Target-to-Order Kernel（G04–G05）

- StrategyOutputValidator 与 Atomic DecisionBatch。
- Capital Allocation、Portfolio Risk、Position Sizing 和 ActivePortfolioTarget。
- RebalanceCoordinator、Order lifecycle、Settlement、Availability 和 Reservation。
- Capability、Translation、Market Rules、Fee Reservation、Pre-trade Risk 和 Fee Assessment。

### 阶段 3：Synthetic Bar Engine 与 Auditable Runner（G06–G07）

- In-memory MarketBundle Reader、确定性 Timeline 和 Precomputed TargetStream。
- 独立 SlippageModel 与 `next_eligible_bar_open.v1`。
- 无 Run Outcome 的 Engine Harness 和 RunEndCoordinator。
- Semantic Run、Attempt、Outcome mapping、Canonical Evidence、Integrity 和 atomic finalize。

### 阶段 4：市场语义分支（G08、G09）

- G08A–G08H：A 股 Calendar、T+1、Lot/Price Limit、Fee/Tax、Corporate Action 和 `cycle-rotation-platform` parity。
- G09A–G09H：通用 Linear Perpetual Position、Funding、Margin 和 LiquidationAudit。
- 两个分支都不得修改 Generic Kernel、Runner 或 Bar Engine 主循环。

### 阶段 5：Binance USD-M Profile（G10）

- Instrument identity、Historical rules、Margin tiers 和 PricePurpose streams。
- Funding source、Fee/Account Profile 和 ResolvedEnvironment composition。
- 与固定 `crypt-gemini` Source Snapshot 做分层 parity。

### 阶段 6：Portfolio Strategy Runtime（G11）

- ObservationView、Revision、Universe、Bar Window、DecisionSchedule 和 Warmup。
- StrategyState、Named RandomStream、ModelArtifact 和 Walk-forward。
- Strategy Candidate → Validated Decision → Atomic DecisionBatch。
- 与预计算 TargetStream 路径做下游 exact parity。

### 阶段 7：真实 MarketBundle 与逐市场资格（G12）

- SourceSnapshot、Normalization、Validation、Publishing 和 Columnar Reader。
- Bar aggregation 与 Rule/Price/Availability/Revision/Universe/Corporate Action coverage。
- 每个供应商 Source Adapter 独立 Gate。
- A 股和 Binance 分别评估 decision-grade，且始终 `deployment_authorized=false`。

### 阶段 8：Microstructure Engine

- Liquidity/Execution Strategy 契约。
- Venue-neutral Order/Cancel Intent。
- L1/L2 events。
- Pre-trade Risk。
- Queue/fill model。
- 真实需要后增加版本化 EngineCheckpoint 和 child-attempt resume。
- 与 `crypt-gemini/mm_l1_replay` parity。

## 22. 待确认的架构问题

通过架构拷问继续逐项确认；已确认的决定立即从本节移除并写入对应正文和领域词汇表。

## 23. 架构验收标准

本设计可进入稳定实施阶段的最低条件：

- Binance 永续和 A 股两个 Profile 可以分别运行且不要求修改回测主循环。
- 第一阶段明确拒绝单次运行配置多个 MarketSemanticsProfile、ExecutionAccountProfile 或 Execution Account。
- 同一个 Ledger 能核算两个市场的账户状态。
- Strategy 不依赖具体回测引擎和交易 Adapter。
- 历史和实时路径可以共享 StrategyDecision 和 OrderPlan 语义。
- 缺少规则、Funding 或时间证据时能够失败关闭。
- 相同输入能够产生相同 run ID/result hash。
- 可以从 source provenance 和 Fixture 生成分层 ParityReport，并定位 first divergence。
- Platform 只通过公开接口运行回测，不读取引擎内部状态。

---

本文件描述的是架构基线，不是最终实现细节。后续不可逆且存在真实权衡的决定，应单独记录为 ADR。
