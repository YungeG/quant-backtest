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
- 策略不直接生成交易所或 Hummingbot 命令。
- 市场差异通过可组合的 `MarketProfile` 表达。
- Accounting 是回测账户状态和 PnL 的唯一权威实现。
- Bar Engine 与 Microstructure Replay Engine 共用领域契约，但不强行共用内部撮合实现。
- 历史运行与实时运行尽可能共用 Strategy、Portfolio/Risk 和 Order Planning 模块。
- 接口同时作为调用面和测试面。

## 3. 非目标

第一阶段不追求：

- 一次性完整支持所有交易所和资产类型。
- 使用一个万能引擎统一 Bar 回测和逐笔订单簿回放。
- 在回测系统内部实现策略研究、参数搜索和实验管理。
- 由回测结果自动授权 Shadow 或 Live。
- 为尚不存在的市场提前设计大量抽象。
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

### 4.2 策略输出目标，不输出交易命令

策略输出 `StrategyDecision`。组合风险模块将其转换为 `ApprovedPortfolioTarget`，订单规划模块再生成 `OrderPlan`。

```text
MarketObservation
      ↓
StrategyDecision
      ↓
ApprovedPortfolioTarget
      ↓
OrderPlan
      ↓
ExecutionReport
      ↓
PortfolioSnapshot
```

### 4.3 市场能力组合优于巨型 Market Adapter

不同市场的交易时间、价格限制、交收、融资和公司行为相互独立。系统使用多个能力模块组成 `MarketProfile`，避免一个拥有大量可选方法的浅接口。

### 4.4 确定性和 Fail-closed

在缺少必需数据、规则、Funding slot、公司行为或结算信息时，decision-grade 运行必须失败关闭。近似模型必须显式写入结果限制，不得静默降级。

### 4.5 回测不等于部署授权

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
┌──────────────┐      ┌──────────────────────┐      ┌─────────────────┐
│ Market Data  │─────▶│   Backtest System    │─────▶│ Evidence Store  │
│ Bundles      │      │                      │      │ / Registry      │
└──────────────┘      └──────────┬───────────┘      └─────────────────┘
                                │
                 ┌──────────────┼──────────────┐
                 ▼              ▼              ▼
             Strategy     Portfolio/Risk   MarketProfile
```

回测系统负责组合这些模块，但不拥有具体策略研究流程和部署审批。

## 6. 总体模块图

```text
backtest-contracts
       ▲
       │
       ├──────── market-bundles
       ├──────── market-profiles
       ├──────── accounting-ledger
       ├──────── portfolio-risk
       ├──────── order-planning
       ├──────── bar-engine
       ├──────── microstructure-engine
       ├──────── metrics
       └──────── evidence
                      ▲
                      │
                backtest-runner
```

### 6.1 依赖规则

- `backtest-contracts` 不依赖其他业务模块。
- `market-profiles` 只依赖领域契约和必要的纯计算模块。
- Strategy 不依赖 Backtest Engine。
- Strategy 不依赖具体 MarketProfile 实现。
- Accounting 不依赖 Strategy。
- Bar Engine 不依赖 Microstructure Engine，反之亦然。
- Evidence 模块只消费运行结果，不修改运行语义。
- Hummingbot 不进入回测核心依赖图。
- Platform 可以组合所有模块，其他模块不能反向依赖 Platform。

## 7. 外部接口

第一阶段建议只提供一个主要调用接口：

```python
def run_backtest(
    *,
    request: BacktestRequest,
    market_bundle: MarketBundle,
    strategy: Strategy,
    market_profile: MarketProfile,
) -> BacktestResult:
    ...
```

调用者需要理解四个概念：请求、数据包、策略和市场 Profile。时间推进、订单生命周期、结算、核算和证据生成隐藏在模块内部。

对于不同精度的引擎，可以通过请求中的 `engine_profile` 选择，也可以暴露两个明确入口：

```python
run_bar_backtest(...) -> BacktestResult
run_microstructure_replay(...) -> BacktestResult
```

禁止让调用者直接驱动内部事件队列或手工修改 Ledger。

## 8. 领域模型

### 8.1 BacktestRequest

```python
@dataclass(frozen=True)
class BacktestRequest:
    schema_version: int
    run_id: str | None
    start_time: datetime
    end_time: datetime
    initial_account: InitialAccount
    strategy_spec: StrategySpec
    risk_spec: RiskSpec
    market_profile_key: str
    engine_profile_key: str
    data_manifest_hash: str
    random_seed: int
    result_grade_requested: str
```

约束：

- `start_time < end_time`
- 所有配置可规范化序列化并计算 hash
- request 不包含密钥
- request 不使用隐式当前时间或当前目录

### 8.2 MarketBundle

```python
@dataclass(frozen=True)
class MarketBundle:
    manifest: MarketManifest
    instruments: tuple[InstrumentSpec, ...]
    events: MarketEventSource
    exchange_rules: RuleTimeline
    corporate_actions: CorporateActionSource
```

`MarketBundle` 是经过验证的历史证据包，不是任意 DataFrame 集合。

Manifest 至少记录：

- 数据源
- 生成时间
- 覆盖区间
- Symbol 和 Instrument identity
- 数据 schema version
- 文件 hash
- 缺口和限制
- Exchange rule coverage
- Funding coverage
- Corporate action coverage

### 8.3 StrategyDecision

```python
@dataclass(frozen=True)
class StrategyDecision:
    strategy_id: str
    decision_time: datetime
    observed_through: datetime
    targets: tuple[DesiredPosition, ...]
    confidence: Decimal | None
    reason: str
    evidence: Mapping[str, CanonicalValue]
```

关键约束：

```text
observed_through <= decision_time
```

策略目标使用领域 Instrument ID，不使用 Hummingbot trading pair 或券商专用字段。

### 8.4 ApprovedPortfolioTarget

```python
@dataclass(frozen=True)
class ApprovedPortfolioTarget:
    decision_id: str
    approved_at: datetime
    targets: tuple[ApprovedPosition, ...]
    gross_exposure: Decimal
    net_exposure: Decimal
    margin_requirement: Decimal
    applied_limits: tuple[AppliedLimit, ...]
    rejections: tuple[TargetRejection, ...]
```

它负责表达组合聚合和风险审批后的最终目标，而非原始策略观点。

### 8.5 OrderPlan

```python
@dataclass(frozen=True)
class OrderPlan:
    plan_id: str
    created_at: datetime
    expires_at: datetime | None
    orders: tuple[PlannedOrder, ...]
    assumptions: tuple[str, ...]
```

`PlannedOrder` 至少包括：

- Instrument ID
- Side
- Quantity
- Order type
- Limit/stop price
- Time in force
- Reduce-only
- Reason
- Parent decision/target ID

### 8.6 ExecutionReport

```python
@dataclass(frozen=True)
class ExecutionReport:
    plan_id: str
    accepted_orders: tuple[AcceptedOrder, ...]
    rejected_orders: tuple[RejectedOrder, ...]
    fills: tuple[Fill, ...]
    cancellations: tuple[Cancellation, ...]
```

### 8.7 Fill

```python
@dataclass(frozen=True)
class Fill:
    fill_id: str
    order_id: str
    instrument_id: str
    side: str
    quantity: Decimal
    price: Decimal
    fee: Money
    liquidity: str | None
    execution_time: datetime
    venue: str
```

### 8.8 PortfolioSnapshot

```python
@dataclass(frozen=True)
class PortfolioSnapshot:
    timestamp: datetime
    cash: tuple[CashBalance, ...]
    positions: tuple[Position, ...]
    realized_pnl: tuple[Money, ...]
    unrealized_pnl: tuple[Money, ...]
    fees: tuple[Money, ...]
    financing: tuple[Money, ...]
    margin: MarginSnapshot | None
    equity: tuple[Money, ...]
```

## 9. 时间模型

系统必须区分：

| 时间 | 含义 |
|---|---|
| `event_time` | 市场事件实际发生时间 |
| `available_time` | 数据对策略可见的时间 |
| `decision_time` | 策略作出决策的时间 |
| `submission_time` | 订单提交时间 |
| `execution_time` | 订单成交时间 |
| `settlement_time` | 资金或持仓完成交收的时间 |

基本因果约束：

```text
event_time <= available_time <= decision_time <= submission_time <= execution_time
```

不是所有事件都需要经历所有阶段，例如 Funding 和公司行为可以直接进入 Ledger，但必须有明确时间语义。

### 9.1 Bar 数据示例

```text
Bar close_time      = 10:00:00
available_time      = 10:00:01
strategy decision   = 10:00:02
order submission    = 10:00:03
next-bar execution  = 10:01:00
```

### 9.2 宏观数据示例

```text
统计月份            = 2026-01
官方发布日期        = 2026-02-10
available_time      = 2026-02-10 10:00
decision_time       = 2026-02-10 close
execution_time      = 2026-02-11 open
```

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
- `FundingPublished`
- `FundingApplied`
- `CorporateActionApplied`
- `SettlementOccurred`
- `ContractExpired`
- `TradingSuspended`
- `TradingResumed`

### 10.2 决策和订单事件

- `DecisionScheduled`
- `DecisionMade`
- `TargetApproved`
- `OrderPlanned`
- `OrderSubmitted`
- `OrderAccepted`
- `OrderRejected`
- `OrderPartiallyFilled`
- `OrderFilled`
- `OrderCancelled`
- `OrderExpired`

### 10.3 账户事件

- `CashChanged`
- `PositionChanged`
- `FeeCharged`
- `FinancingCharged`
- `MarginChanged`
- `EquityMarked`
- `LiquidationTriggered`

事件是否完整持久化由 trace level 决定，但内部状态转换必须遵守统一语义。

## 11. MarketProfile

```python
@dataclass(frozen=True)
class MarketProfile:
    key: str
    session_model: SessionModel
    instrument_model: InstrumentModel
    order_rule_model: OrderRuleModel
    execution_model: ExecutionModel
    settlement_model: SettlementModel
    financing_model: FinancingModel
    corporate_action_model: CorporateActionModel
```

### 11.1 SessionModel

负责：

- 时区
- 交易日历
- Session 阶段
- Decision schedule
- 开盘、午休、收盘和夜盘

### 11.2 InstrumentModel

负责：

- Equity、Spot、Perpetual、Future、Option
- Base/quote currency
- Contract multiplier
- Tick size 和 lot/step size
- Expiry
- Long/short 能力

### 11.3 OrderRuleModel

负责：

- 订单类型是否合法
- 最小数量和最小名义金额
- Price limit
- T+1 可卖数量
- Suspension
- Reduce-only
- 保证金前置检查

### 11.4 ExecutionModel

负责：

- Next-open/next-bar
- OHLC conservative fill
- 固定或比例滑点
- Spread
- Participation rate
- Partial fill
- 延迟
- L1/L2 queue 模拟

### 11.5 SettlementModel

负责：

- T+0/T+1
- 可用资金
- 可卖数量
- Futures daily settlement
- Contract expiry 和 rollover

### 11.6 FinancingModel

负责：

- Crypto funding
- Borrow fee
- Margin interest
- Futures carry
- 现金利息

### 11.7 CorporateActionModel

负责：

- 分红
- 拆股和送转
- 配股
- Symbol migration
- 合约换月

不需要公司行为的市场使用显式的 No-op 实现，而不是空值分支。

## 12. 引擎划分

### 12.1 Bar/Portfolio Engine

适用：

- 日频、小时级和分钟级中低频策略
- 趋势、轮动、Carry、Cross-sectional
- 多资产组合

第一阶段支持的 Execution Profile：

- `next_open`
- `next_bar_open`
- `bar_close`
- `ohlc_conservative`
- `fixed_slippage`
- `participation_limited`

### 12.2 Microstructure Replay Engine

适用：

- Market making
- L1/L2 replay
- Queue position
- Partial fill
- Hedge execution
- Second-level execution

它与 Bar Engine 共用：

- Instrument、Order、Fill 和 Ledger 契约
- Market manifest
- Result 和 evidence 契约
- 费用与交易规则的权威定义

它不与 Bar Engine 强行共用：

- 内部事件队列实现
- 撮合状态
- Queue 模型
- 高频性能优化

## 13. Accounting Ledger

Accounting Ledger 是账户状态的唯一权威来源。

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

Ledger 接口建议：

```python
new_state = ledger.apply(state, account_event)
snapshot = ledger.mark(state, market_marks, timestamp)
```

Ledger 的状态转换必须可用小型事件 Fixture 独立测试。

## 14. 数据完整性和结果等级

### 14.1 Development Grade

允许显式近似，例如：

- 当前交易规则快照代替历史规则
- 固定滑点
- 缺少订单簿深度

但必须记录限制。

### 14.2 Decision Grade

要求：

- 完整 Market manifest
- 所有观察满足时间因果性
- 历史交易规则覆盖
- 必需 Funding slot 完整
- 必需 Corporate action 完整
- 确定性运行
- 无 blocking integrity issue

### 14.3 失败关闭条件

- MarketBundle hash 不匹配
- Symbol/Instrument identity 冲突
- 时间倒序、重复或不允许的缺口
- 使用 `available_time > decision_time` 的数据
- 必需规则时间段缺失
- Funding slot 缺失
- 公司行为缺失
- Settlement 无法完成
- Accounting 不平衡
- 非法订单状态转换

## 15. 结果与证据契约

标准运行目录：

```text
runs/<run-id>/
├── request.json
├── environment.json
├── market-manifest.json
├── strategy-spec.json
├── decisions.jsonl
├── targets.jsonl
├── orders.jsonl
├── fills.jsonl
├── positions.jsonl
├── equity.jsonl
├── financing.jsonl
├── rejections.jsonl
├── metrics.json
├── integrity.json
└── result.json
```

### 15.1 Result 最小结构

```json
{
  "schema_version": 1,
  "run_id": "...",
  "request_hash": "...",
  "canonical_result_hash": "...",
  "result_grade": "development",
  "deployment_authorized": false,
  "metrics": {},
  "integrity": {
    "blocking": [],
    "limitations": []
  }
}
```

### 15.2 Trace Level

- `summary`：request、manifest、metrics、integrity、result
- `full_trace`：增加 decisions、orders、fills、positions、equity
- `microstructure_trace`：增加 quote/trade/queue 级诊断

Decision-grade 默认要求 `full_trace`。

## 16. 确定性和性能

### 16.1 确定性

- 所有随机行为必须使用 request seed。
- 配置和结果采用 canonical serialization。
- Decimal 字段禁止通过 JSON number 隐式转换。
- 相同 request、MarketBundle 和代码版本应产生相同 result hash。
- Engine 不读取系统当前时间决定业务行为。

### 16.2 性能分层

- 低中频优先保证语义正确和 traceability。
- Bar Engine 可对纯指标计算使用向量化，但账户和订单状态转换保持权威语义。
- Microstructure Engine 可以采用专门的数据结构和批处理优化。
- 任何 fast path 都必须通过黄金 Fixture 与权威路径做 parity。

## 17. 初始市场 Profile

### 17.1 Binance USD-M Perpetual

```yaml
market_profile: crypto.binance_usdm.v1
session_model: continuous_24x7
instrument_model: perpetual
order_rule_model: binance_historical_rules
execution_model: next_bar_with_slippage
settlement_model: realtime
financing_model: historical_funding
corporate_action_model: none
margin_model: cross_margin
liquidation_model: historical_tiers
```

关键场景：

- Funding 跨期持仓
- Long/short
- Step size 和 min notional
- Cross margin
- Intrabar liquidation audit
- Rule timeline 变化

### 17.2 A 股

```yaml
market_profile: equity.cn_a_share.v1
session_model: cn_exchange_calendar
instrument_model: cash_equity
order_rule_model: board_aware_price_limits
execution_model: next_open
settlement_model: cash_t0_position_t1
financing_model: none
corporate_action_model: cn_equity_actions
```

关键场景：

- 100 股手
- 当日买入不可卖
- 涨停买入和跌停卖出
- 停牌
- 印花税
- 分红送转和复权

这两个市场差异足够大，可用于验证 MarketProfile 接缝是否真实成立。

## 18. 测试策略

### 18.1 契约测试

- 时间因果性
- Canonical hash
- Order lifecycle
- Fill 和 Ledger 平衡
- Result schema

### 18.2 市场 Profile 黄金 Fixture

Binance Fixture：

1. 开多仓。
2. 经历一次 Funding。
3. 部分平仓。
4. 价格不利变化。
5. 验证 margin、PnL 和 equity。

A 股 Fixture：

1. T 日开盘买入。
2. T 日尝试卖出并被拒绝。
3. T+1 日涨停状态下尝试买入。
4. T+1 日卖出已有持仓。
5. 验证 lot、印花税、可卖数量和现金。

### 18.3 Parity 测试

- 从 `crypt-gemini` 抽取策略和回测场景。
- 从 `cycle-rotation-platform` 抽取 A 股 T+1 和订单规划场景。
- 比较 decisions、orders、fills、positions 和 PnL。
- 迁移阶段不只比较最终收益率。

### 18.4 性质测试

- 无成交时现金和持仓不变。
- Fee 不能增加账户权益。
- Full close 后 Position quantity 为零。
- 不允许卖出超过可卖数量。
- 缺少必需数据时 decision-grade 不得成功。

## 19. 建议代码组织

逻辑模块先于物理仓库拆分。初始可以放在一个独立仓库中：

```text
crypto-quant-backtest/
├── src/crypto_quant_backtest/
│   ├── contracts/
│   ├── runner/
│   ├── timeline/
│   ├── ledger/
│   ├── planning/
│   ├── engines/
│   │   ├── bar/
│   │   └── microstructure/
│   ├── markets/
│   │   ├── binance_usdm/
│   │   └── cn_a_share/
│   ├── metrics/
│   └── evidence/
├── tests/
│   ├── contracts/
│   ├── ledger/
│   ├── markets/
│   ├── parity/
│   └── fixtures/
└── docs/
```

如果部分契约已属于 `crypto-quant-core`，回测仓库应依赖 core，而不是复制定义。

## 20. 与现有项目的关系

### 20.1 `crypto-quant-core`

应提供：

- Instrument、Order、Fill、Money 等基础契约
- Canonical serialization
- Causality guard
- Accounting primitives
- Exchange rule primitives

需移出：

- Hummingbot DTO

需增强：

- 多 Fill Ledger
- Partial close
- 多币种现金
- Margin 和 Financing

### 20.2 `crypto-quant-platform`

应负责：

- 构建 BacktestRequest
- 选择 Strategy 和 MarketProfile
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

迁移必须保留源 commit 和 parity Fixture。

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

### 阶段 0：架构冻结

- 确认领域词汇。
- 确认模块依赖图。
- 确认 BacktestRequest/Result schema。
- 确认时间和结果等级语义。

### 阶段 1：Contracts 和 Ledger

- Money、Instrument、Order、Fill。
- 多 Fill 和 Partial close。
- Canonical hash。
- Ledger 黄金 Fixture。

### 阶段 2：Bar Engine

- 事件时间线。
- Strategy decision schedule。
- Target → OrderPlan。
- Next-open/next-bar 执行。
- Full trace result。

### 阶段 3：Binance USD-M Profile

- Historical rules。
- Funding。
- Margin。
- Liquidation audit。
- 与 `crypt-gemini` parity。

### 阶段 4：A 股 Profile

- Calendar。
- T+1。
- Lot 和 price limits。
- Tax。
- 与 `cycle-rotation-platform` parity。

### 阶段 5：Evidence 和 Registry

- Immutable run bundle。
- Result hash。
- Decision-grade validation。
- Platform integration。

### 阶段 6：Microstructure Engine

- L1/L2 events。
- Queue/fill model。
- 与 `crypt-gemini/mm_l1_replay` parity。

## 22. 待确认的架构问题

以下问题需要在实现前继续讨论：

1. `StrategyDecision` 应直接输出目标数量、目标权重，还是同时支持两者？
2. Portfolio/Risk 和 Order Planning 属于回测仓库，还是独立共享仓库？
3. Accounting Ledger 是否直接进入 `crypto-quant-core`？
4. Bar Engine 的第一批成交 Profile 需要支持到什么精度？
5. Binance 第一版是否要求完整 liquidation，还是先提供 intrabar audit？
6. A 股第一版是否包含公司行为，还是只支持已复权数据并显式声明限制？
7. 是否需要在 v1 支持多账户和多基础币种？
8. Decision-grade 的历史交易规则覆盖标准如何定义？
9. Strategy 接口采用逐事件调用还是 Decision schedule 批调用？
10. BacktestResult 中哪些 trace 是必须长期保留的权威证据？

## 23. 架构验收标准

本设计可进入稳定实施阶段的最低条件：

- Binance 永续和 A 股两个 Profile 不要求修改回测主循环。
- 同一个 Ledger 能核算两个市场的账户状态。
- Strategy 不依赖具体回测引擎和交易 Adapter。
- 历史和实时路径可以共享 StrategyDecision 和 OrderPlan 语义。
- 缺少规则、Funding 或时间证据时能够失败关闭。
- 相同输入能够产生相同 run ID/result hash。
- 可以从 source commit 和 Fixture 验证迁移前后 parity。
- Platform 只通过公开接口运行回测，不读取引擎内部状态。

---

本文件描述的是架构基线，不是最终实现细节。后续不可逆且存在真实权衡的决定，应单独记录为 ADR。
