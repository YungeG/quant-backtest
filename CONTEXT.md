# Domain Glossary

## 交易领域契约（Trading Domain Contract）

由回测和实时运行共同使用的市场无关领域类型及不变量，例如 Instrument、Order、Fill 和 Money。

## 有类型定点整数（Typed Scaled Integer）

以整数 units 和十进制 scale 精确表示交易数值，并携带 Price、Quantity、Money、Rate 或 Exposure 等领域身份的值。它是权威交易和核算数值表示。
_Avoid_: Exact float, naked scaled integer

## 规范任意精度整数（Canonical Arbitrary-Precision Integer）

Trading Domain 接受的 signed integer 不受 Python 十进制字符串位数限制。Canonical JSON 使用确定性十进制编码，不修改 process-global digit limit；普通整数既有 bytes/hash 保持不变。

## 量化策略（Quantization Policy）

将分析浮点值或高精度中间结果转换为目标定点 Scale 或市场格点的显式规则。

## 舍入策略（Rounding Policy）

在除法、Scale 降低或格点转换时明确选择结果方向的规则，不允许使用隐藏默认值。

## 交易内核（Trading Kernel）

由回测和实时运行共同依赖的资本分配、组合风险、仓位规格化、订单规划、交易前风险和账户核算模块。它不依赖历史或实时 Adapter。

## 回测运行时（Backtest Runtime）

使用历史时间线、观察回放和模拟执行 Adapter 驱动交易内核的运行环境。

## 回测运行（Backtest Run）

由固定语义输入标识的可重复模拟，包含独立预热区间和半开交易区间。一次语义运行可以有多个实际执行尝试。

## 语义运行标识（Semantic Run ID）

由规范化请求、不可变数据引用、Profile 摘要和 Strategy/代码身份计算的内容标识。相同语义输入必须产生相同标识。

## 执行案例语义规格（Execution Case Semantic Spec）

在领域 ID 派生前冻结的 ID-free typed composition input。它 exact-cover Timeline、Target、Decision、Execution、Financial、Snapshot、RunEnd、完整行为配置和 Identity Plan；其 hash 进入 Semantic Run ID，final ExecutionCase hash 不回流。
_Avoid_: final-case preimage, placeholder semantic hash

## 身份计划（Identity Plan）

按 ExecutionCase role 冻结 identity type、Domain kind、semantic key 和 ordinal 的 ID-free 派生计划。Identity Factory 只能按 role 执行该计划，builder 不能在派生阶段替换 key 或 ordinal。

## 身份清单（Identity Manifest）

记录一个最终 ExecutionCase 中每个 role 实际派生的身份值及其 Identity Plan 输入的不可变证据。Composer 和 Runner 必须验证其 Semantic Run、derivation plan 和 Case role exact coverage。

## 执行尝试（Execution Attempt）

对一个语义运行进行的一次实际计算，具有独立 Attempt ID 和 Outcome，不得覆盖其他尝试的证据。Bar Engine v1 的重试从初始状态创建新尝试；canonical publication 封闭 Semantic Run 后不得再创建同 Run Attempt。

## 引擎检查点（Engine Checkpoint）

在安全时间线阶段边界保存的版本化完整模拟恢复状态。未来 Microstructure 恢复必须从检查点创建新的 Child Attempt。

## 权威运行证据（Canonical Run Evidence）

一个已完成语义运行通过原子 finalize 发布的不可变权威证据集合。只有 COMPLETED 可以创建 `canonical/`；post-integrity BLOCKED/FAILED 使用独立 immutable Integrity Evaluation。

## 可审计开发级运行（Auditable Development Run）

G07 冻结的首条完整回测运行：同一 Synthetic Semantic Run 必须实际执行至少两个独立 Attempt，保持全部 Domain ID、ExecutionCase 和 execution result hash 一致，分别原子发布 Evidence，再经 Integrity 发布 development-grade `COMPLETED`；Mismatch 只能发布 durable `FAILED` Evaluation。它始终 `deployment_authorized=false`。

## 权威结果缓存命中（Canonical Result Cache Hit）

Auditable Runner 在 run-level lock 内验证已发布只读 `canonical/` Artifact、Manifest exact coverage 和 Result hash chain 后返回的 `COMPLETED` 复用结果。它不创建新 Attempt、不写 Evidence，也不重跑 Engine；缺少 publication root 时 Runner fail closed。

## 封闭 Attempt 集（Closed Attempt Set）

Publisher 在 run-level exclusive lock 下 exact-cover 的全部 finalized `READY_FOR_INTEGRITY` Attempt。G07 v1 的 COMPLETED 至少需要两个 execution hash 一致的 Attempt，canonical Attempt 固定选择最小 ordinal；canonical 发布后同一 Semantic Run 不再接受新 Attempt。

## 完整性评估记录（Integrity Evaluation Record）

对一个 Closed Attempt Set 产生的 immutable post-integrity BLOCKED 或 FAILED 记录。它原子发布在 `integrity-evaluations/`，不包含 `result.json`，不能冒充 Completed canonical result。

## 确定性重建证据（Deterministic Rebuild Evidence）

Canonically 绑定 Request、Resolved Environment、Build、MarketBundle manifest/retention proof、Target digest、ExecutionCase identity、Trace hash/level 和 execution result hash 的 caller-supplied 证据。CanonicalAttemptRef 必须绑定其 hash。

## Canonical Publication Manifest

Canonical 或 Integrity Evaluation 目录的无环 hash DAG root，exact-cover 同目录其他权威文件的路径、schema 和 content hash。子文件不得反向引用 Manifest hash。

## 构建产物清单（Build Artifact Manifest）

标识 Strategy、共享交易模块、回测运行时、Profile 组件和结果相关依赖实际执行内容摘要的不可变清单。Git commit 仅是其来源信息之一。

## Schema 版本（Schema Version）

标识一个权威 Artifact 结构契约版本的显式整数。结构版本不能用来隐藏经济语义变化。

## Schema 迁移（Schema Migration）

将不可变旧 Artifact 通过可审计纯函数转换为新结构视图的单向过程。原始 Artifact 和摘要保持不变。

## Migration Manifest

记录一次 Schema 迁移的源版本、目标版本、迁移链和迁移代码身份的证据。

## 预热区间（Warmup Interval）

交易开始前用于构建 Strategy State 和市场模拟状态的数据区间。预热期间禁止产生订单、成交、会计流水和绩效。

## 活跃交易区间（Active Trading Interval）

允许产生交易和绩效的半开时间区间 `[trading_start, trading_end_exclusive)`。

## 冻结交易日历（Frozen Trading Calendar）

在显式有限覆盖区间内逐日声明交易日、周末和已知节假日的 immutable Calendar。相同内容必须产生相同摘要；覆盖区间外不能按工作日规则外推。

## 已知无 Session（Known No-Session）

Frozen Trading Calendar 明确声明的周末或休市日。它是成功解析出的市场关闭事实，不等同于 Calendar 数据缺失。

## Calendar 覆盖缺失（Calendar Coverage Missing）

查询日期不在 Frozen Trading Calendar 覆盖内，或覆盖内缺少唯一日期记录。它必须 fail closed，不能被解释为周末、节假日或普通交易日。

## 市场 Session 阶段（Market Session Phase）

交易场所在一个 TradingDate 内具有市场语义的半开时间段，例如集合竞价、连续竞价、暂停、午休和收盘后。它不同于 Engine 事件排序使用的 `TimelinePhase`。

## A 股现金竞价 Session Model（A-Share Cash Auction Session Model）

G08A 冻结的 XSHG/XSHE development-grade `SessionModel`：使用 caller-injected finite Calendar 和 `Asia/Shanghai` local date，解析开盘集合竞价、暂停、上午/下午连续竞价、午休、收盘集合竞价与收盘后阶段。已知周末/节假日是成功的 no-session；覆盖缺失必须结构化失败。

## 结束策略（Closeout Policy）

规定运行结束前是否通过正常交易链平仓，或在结束边界保留仓位并按市值估值的显式规则。

## 按市值结束（Mark-to-market Closeout）

在运行结束时不产生隐式平仓成交，保留未平仓 Position，并使用最后合法估值价格生成最终组合快照的默认结束策略。

## 运行结束报告（Run End Report）

记录运行结束时被终止订单、未平仓 Position、待结算义务、待评估费用、最终估值价格身份和 Closeout 状态的证据。

## 回看要求（Lookback Requirement）

Strategy 为形成首个合法决策所声明的最小历史数据范围和数据能力要求。

## 回看覆盖报告（Lookback Coverage Report）

证明市场数据包在交易开始前满足 Strategy 回看要求的验证结果。

## 来源快照（Source Snapshot）

从供应商、交易所、数据库、文件系统或迁移来源仓库取得，并以内容摘要冻结的原始输入证据。来源仓库是否 dirty 不影响资格；Snapshot 按声明范围捕获当时的实际文件字节，范围内 modified/untracked 文件可以被纳入，范围外文件一律忽略。Base commit 和 clean/dirty 状态只属于 provenance，Snapshot aggregate hash 才是权威身份。它先于规范化、迁移比较或 MarketBundle 构建。

## 市场数据包构建器（Market Bundle Builder）

将来源快照规范化、验证并发布为内容寻址 MarketBundle 的独立数据流程。它不在 Backtest Run 中执行。

## 市场数据包仓库（Market Bundle Repository）

按不可变内容摘要存取已验证 MarketBundle 的仓库。Backtest Runtime 只读此仓库。

## 市场数据包读取器（Market Bundle Reader）

以存储格式无关方式打开不可变 MarketBundle，并提供规范 Event Cursor 和有界 Observation 查询的只读接口。

## 事件游标（Event Cursor）

按规范事件总顺序流式读取一个 MarketBundle Event Stream 的位置化接口。

## 市场数据包（Market Bundle）

经过完整性验证并带有 Manifest 的历史市场证据集合。它可以包含行情、Funding、交易规则、公司行为、交易日历和 point-in-time Universe，但不等同于任意 DataFrame 或文件目录。

## Instrument 身份（Instrument Identity）

跨 Symbol 改名、合约迁移和历史引用保持稳定的交易标的身份。Symbol 是可随时间变化的属性，不是权威身份。

## Binance USDⓈ-M 稳定标的谱系（Binance USDⓈ-M Stable Instrument Lineage）

G10A caller显式提供、由冻结source evidence支持的稳定provider lineage key。它与`VenueId("binance_usdm")`共同确定`InstrumentId`，不能从current symbol、pair、base/quote拼接、去后缀或rebranding名称猜测。没有显式same-lineage evidence时old/new contract保持不同Instrument。

## Binance USDⓈ-M Instrument Metadata Revision

对一条USDⓈ-M `exchangeInfo` metadata状态的immutable、bi-temporal source revision，保存effective/available instant、revision/supersedes identity、source key/hash、symbol/pair、contract type/status、onboard/delivery和currency context。G10A只解析`captured_at`已可见的closed revision chain，不查询current API。

## Binance USDⓈ-M Open-ended Delivery Sentinel

Official perpetual `exchangeInfo` example中的`deliveryDate=4133404800000` epoch milliseconds。G10A只把该精确值解释为没有finite delisting boundary；其他finite delivery revision形成exclusive delisting boundary，不能把sentinel当作真实2100年退市时间。

## Binance USDⓈ-M Linear Contract Metadata

G10A冻结的base quantity、quote price、margin/settlement currency与exact `1 base quantity per contract` multiplier。它不包含tick/step/scale；G10B提供historical rules后，G10G才组合G09A `LinearPerpetualContract`。

## 可交易 Universe（Tradable Universe）

在一个模拟时点已经上市、当时已知并满足 UniverseSpec 的 Instrument 集合。

## 静态 Universe（Static Universe）

由研究者预先固定的 Instrument 集合，不声称代表历史全市场或消除幸存者偏差。

## Universe 覆盖报告（Universe Coverage Report）

证明 Instrument 上市、退市、改名和成员变化在回测区间内具有 point-in-time 证据的验证结果。

## 市场语义 Profile（Market Semantics Profile）

描述真实市场 Session、Instrument、订单规则、核算、交收、融资、保证金和公司行为的版本化事实集合。它由回测与实时运行共享，不包含模拟成交假设。
_Avoid_: Market Profile

## 模拟 Profile（Simulation Profile）

描述回测如何近似历史成交、滑点、延迟、流动性和数据粒度歧义的版本化假设集合。它不表示真实市场规则。

## 财务分派器（Financial Dispatcher）

由已解析Profile composition注入Generic Bar Engine的账户经济编排接口。Engine只向它提交canonical Fill Accounting Plan、Scheduled Account Event和immutable Financial State View，并接收append-only Journal Entries、typed Financial Artifacts或Final PortfolioSnapshot；Engine不得按Cash、Derivative、Provider或operation key解释经济语义。
_Avoid_: derivative engine branch, profile callback in case identity

## 财务分派计划（Financial Dispatch Plan）

ResolvedExecutionCase中的versioned immutable composition authority，exact保存Dispatcher Spec、per-Fill opaque accounting payload、ordered Scheduled Account Events、Final Snapshot authority和expected artifact roles。Implementation object、runtime address、Attempt ID和wall clock不进入Plan或Semantic Spec。

## 计划账户事件（Scheduled Account Event）

把一个已存在Timeline Event exact绑定到Profile-owned账户操作payload的resolved plan。它携带stable Event ID、完整SimulationInstant、versioned operation key、component refs、availability和expected artifact roles；Engine只负责唯一、按时dispatch，不解释Funding、Margin或Liquidation含义。

## 财务分派产物（Financial Dispatch Artifact）

Engine Result中由Financial Dispatch Plan exact覆盖的canonical typed evidence。它绑定source Timeline Event、component/request/result identity和完整payload，用于独立重建Journal、Derivative Position、MarginProjection、LiquidationAudit或Final Snapshot；裸hash不能替代重建authority。

## Synthetic Linear Perpetual Development Profile

G09H tests/support中的显式opt-in Profile composition，用同一Generic Financial Dispatcher seam组合G09A–G09G并冻结Long/Short、partial close、Funding、Margin、Liquidation与Snapshot Journey。它始终记录`synthetic_market_profile` limitation，`decision_grade_eligible=false`且`deployment_authorized=false`。G09H已由实现提交`e0f2bc767dc87513d562becd9907262628b788e6`通过冻结验收。

## Binance USDⓈ-M Instrument Model

G10A已实现并通过冻结验收的纯离线Profile Adapter：caller-supplied frozen `exchangeInfo` revisions → stable Instrument、point-in-time Symbol timeline、listing/delisting interval和Linear currency/multiplier metadata。它只解析`captured_at`已可见的closed revision chain，保留source provenance并structured fail closed；implementation commit为`613c319b2dbba9962d4867dcfb3d1b19067d16cf`。它不扩展到G10B rules、G12 acquisition、live或deployment。

## Binance USDⓈ-M Order Rule Model

G10B已实现并通过冻结验收的纯离线Profile Adapter：caller-supplied finite historical RuleBook → style-specific Quantity lattices、Price tick/bounds、MIN_NOTIONAL、Admission Mode、generic Rule Timeline与Capability evidence。它只使用`captured_at`已可见且finite exact-cover的Band，保留raw decimal/source/deferred authority并structured fail closed；implementation commit为`11072289a9dda708a185ae2edcbf5fcdf0c7bd55`。它不查询current exchange info，也不拥有Mark、account、translation、execution或deployment。

## Binance USDⓈ-M Historical Margin Tier Model

G10C已实现并通过冻结验收的纯离线Profile Adapter：caller-supplied archived Contract Info bracket-update Bands → generic Historical Margin Rule Book。它保留raw `bs/bnf/bnc/mmr/cf/mi/ma`和source lineage，使用upper-inclusive bracket、finite terminal cap与point-in-time availability；current authenticated bracket、`notionalCoef`和account-adjusted tier不能补历史。Implementation commit为`50fa838f901385498ce18d65a897d4eb1dc31337`。G12拥有archive completeness，G10F拥有selected account leverage。

## Binance USDⓈ-M Margin Tier Band

对一个stable Instrument在half-open economic interval内生效的immutable bracket-update evidence，保存`available_at`、source provenance和完整raw bracket set。其notional bracket本身使用upper-inclusive provider convention；time interval仍为half-open。

## Binance USDⓈ-M Account-adjusted Notional Coefficient

Authenticated UM bracket evidence中的`notionalCoef`。G10C v1不解释或乘算该account-scoped字段，任何携带它的normalized tier source都structured reject；只有G10F/G12未来冻结Account identity、历史effective/available time与变换语义后才可扩展。

## Binance USDⓈ-M Order Rule Band

对一个stable Instrument在half-open economic interval内生效的历史下单规则证据，保存可用时间、source provenance、raw PRICE_FILTER/LOT_SIZE/MARKET_LOT_SIZE/MIN_NOTIONAL、provider capability和admission mode。它是新Order admission authority，不反向修改旧Order已保存的rule decision。

## Style-specific Quantity Lattice

同一Instrument按Execution Style选择的数量格点。Limit/Stop-Limit使用primary lattice，Market/Stop使用market lattice；两者共享atomic Scale与MIN_NOTIONAL authority，但minimum、maximum和step可以不同。

## Binance USDⓈ-M Order Admission Mode

Symbol-time规则状态：`normal`允许普通开平仓，`reduce_only`只允许显式CLOSE且要求reduce-only，`closed`禁止新admission。它不同于Account的one-way/hedge mode，也不同于Order最终Fill结果。

## Deferred Provider Rule

已在冻结source中出现、但当前Gate缺少所需Mark、account state、translation或execution semantics而不能安全判定的provider rule。它必须保留identity和owner；存在未解析Deferred Rule时不得声明decision-grade eligibility。

## 已解析回测环境（Resolved Backtest Environment）

由已解析市场语义 Profile、模拟 Profile 和市场数据包引用组成，并通过兼容性验证的不可变运行环境。

## Profile 摘要（Profile Digest）

标识一个已解析 Profile 全部组件版本、配置和结果相关代码身份的规范化摘要。

## 规则时间线（Rule Timeline）

按生效区间记录 Instrument 交易、费用、保证金和结算规则的历史证据序列。

## 必需规则维度（Required Rule Dimension）

一个市场语义 Profile 声明会影响其回测结果、因此必须具有完整历史覆盖的规则类别。

## 规则覆盖报告（Rule Coverage Report）

证明市场数据包满足市场语义 Profile 必需规则维度，并且有效区间无缺口、无重叠且来源明确的验证结果。

## 市场事件（Market Event）

影响策略观察、交易可行性或账户状态的已发生事实，例如 Bar 完成、报价变化、Funding、停牌、结算或公司行为。

## 市场可用状态（Market Availability Status）

说明预期市场数据在某时段为何存在或缺失的权威分类，包括非交易时段、停牌、无成交、数据缺失和数据源故障。

## 数据缺口（Data Gap）

Price 或 Market Event Stream 在预期覆盖区间中的缺失，并具有明确的市场可用状态和来源证据。

## A 股历史订单规则簿（A-Share Historical Order Rule Book）

按 Venue、Board 和半开 TradingDate 区间冻结 daily price limit、tick、Execution-style 单笔数量上限与 QuantityLattice 的 caller-injected immutable evidence。缺口或重叠必须 fail closed，禁止回退 current rule。

## 权威订单规则仓位证据（Authoritative Order-Rule Position Evidence）

为 residual/odd SELL 准入在同一 evaluated-at exact 绑定 PortfolioSnapshot、AvailabilityState、ResourceReservationState、active Working Orders、total/sellable Quantity 和 resolved lattice hash 的 canonical hash chain。Sizing、Target 或 `PositionEffect.CLOSE` 不能替代它。

## 涨跌停流动性阻断（Liquidity Blocked at Limit）

`next_eligible_bar_open.v1` 在 contemporaneous bar open 等于 upper limit 的 BUY 或等于 lower limit 的 SELL 上使用的 conservative no-fill eligibility。它不使用全天 Volume，也不声称具备真实 Queue 模拟能力。

## 陈旧估值策略（Stale Mark Policy）

规定在停牌或无成交等允许原因下，估值价格可以沿用的最大年龄和 Price Purpose。它不能授权使用旧价格模拟成交。

## 市场可用性报告（Market Availability Report）

证明全部预期数据缺口已经分类并符合 MarketSemanticsProfile 规则的验证结果。

## 价格用途（Price Purpose）

价格在交易系统中的明确用途，包括成交参考、组合估值、保证金、强平和结算。不同用途的价格流不能隐式互换。

## 价格流（Price Stream）

针对一个价格用途、按模拟时点排序并具有稳定来源身份的历史价格事件序列。

## Bar 定义（Bar Definition）

规定 Bar duration、Session scope、anchor、包含阶段、价格来源、成交量语义和空区间策略的版本化聚合契约。

## Bar 聚合清单（Bar Aggregation Manifest）

记录一个 canonical Bar Stream 的 Bar Definition、源数据摘要、聚合代码身份和输出摘要的证据。

## 原始可交易价格（Raw Tradable Price）

市场在当时实际报价或成交的未事后复权价格，是成交参考和交易规则的价格依据，不自动等同于估值或强平价格。

## 价格流覆盖报告（Price Stream Coverage Report）

证明市场数据包满足市场语义 Profile 所声明价格用途及时间区间的验证结果。

## 价格回退策略（Price Fallback Policy）

当必需价格流缺失时使用其他用途价格近似的显式开发级规则。Decision-grade 禁止使用。

## 时点复权观察（Point-in-time Adjusted Observation）

仅使用当前模拟时点已经公布或生效的公司行为派生的策略观察价格。它不是订单成交或账户核算价格。

## 公司行为时间线（Corporate Action Timeline）

按公布、资格、有效和支付时点记录分红、拆股、送转及其他公司行为完整生命周期的历史证据序列。Announcement 是 available time 驱动的市场观察；Record、Adjustment 和 Payment 是独立账户 lifecycle facts，不能把未来日期伪装成提前可用的 Market Event。

## 公司行为登记持仓快照（Corporate Action Registered Position Snapshot）

在 Record/Eligibility boundary 由权威登记来源冻结的账户持仓证据，携带 account、instrument、record instant、available time 和 source hash。它不同于后续当前 Portfolio、Ledger balance、sellable quantity、Order 或 Fill。

## 公司行为资格（Corporate Action Entitlement）

在 Record 或 Eligibility Instant 根据历史 registered-position snapshot 锁定的公司行为权利，并同时记录 evidence captured-at。当前持仓不能替代或重算；零登记持仓仍可产生 canonical zero entitlement。

## 公司行为生效触发（Corporate Action Effective Trigger）

独立证明送股、转增、拆分或其他 Position adjustment 何时生效/上市的账户 lifecycle evidence。Announcement 中的未来日期不等于已经发生的 Adjustment。

## 公司行为支付触发（Corporate Action Payment Trigger）

独立证明现金分配到达 Payment lifecycle boundary 的账户证据。Entitlement 本身不能自动推导 Payment，延迟或暂停必须显式表达。

## Funding 费率发布（Funding Rate Publication）

市场在完整可用时点向 Strategy 暴露某个目标 Funding UTC 的费率观察事件；该可用时点可在同一 UTC 的较晚 phase。它本身不改变账户现金。

## Funding 结算（Funding Settlement）

在明确结算时点按 Eligibility Instant 的合格仓位、Applied Rate 和 Funding Mark 产生账户经济影响的事件。G09D v1 的 effective time 是目标 Funding UTC，recorded-at 是账户结算证据完整可用的 `SimulationInstant`。

## Funding Application Key

由 Execution Account 与 Funding Slot 唯一决定的一次账户级 Funding 应用身份。Rate、Mark、Money、Currency、Scale、revision、source 和 Request hash不进入该语义 key；同一 Namespace/Semantic Run使用它分别派生SETTLEMENT/JOURNAL ID。

## 精确线性 Funding Cash Flow（Exact Linear Funding Cash Flow）

由signed eligibility Quantity、contract multiplier、Funding Mark和signed Applied Rate形成的约分有理数账户现金：`-(quantity × multiplier × mark × rate)`。它只在每个Funding Application的Money boundary调用一次显式QuantizationPolicy。

## Funding Mark

仅用于Funding payment notional的`PricePurpose.FUNDING`价格证据，必须绑定target Funding UTC、Instrument、settlement Currency、Price Scale、完整StaleMarkPolicy和既有Mark Resolver的authoritative UTC availability。G09D不附加caller伪造的phase/sequence；Settlement、Valuation、Margin、Liquidation或execution价格不能静默替代。

## Funding Slot ID

只由 Instrument 与目标 Funding UTC 派生、唯一标识一次 Funding 时隙的稳定身份。Account、Rate、revision、source 和 Position 不进入 Slot identity。

## Funding 发布修订链（Funding Publication Revision Chain）

同一 Funding Slot 的 caller-supplied、按完整 availability 顺序闭合的线性 MarketEvent revision chain。每个 revision 只能紧邻 supersede 前一项，final item 唯一决定 published Rate 或 cancellation；它本身不创建账户义务。

## Funding 资格持仓快照（Funding Eligibility Position Snapshot）

绑定 G09B authoritative Journal、最大 `recorded_at < eligibility_instant` cursor/prefix 与重放后 `LinearPositionState` 的历史资格证据。Snapshot available 后的 current close、flip 或其他 Position 不能替代 cutoff State。

## Instrument Margin Exposure Quantity

Caller要求评估Initial/Maintenance Margin的单Instrument signed Quantity。其绝对值决定margin notional；它不声明自己来自当前Position、Order、Working Order或Target，来源组合由后续Gate拥有。

## Historical Margin Rule Book

按半开生效时间区间保存Instrument Margin Tier历史事实的immutable RuleBook。查询时必须命中唯一historical interval；缺口、重叠或用当前tier回填历史都必须fail closed。每个Rule Interval显式或按backward-compatible default声明notional Tier Boundary Convention。

## Margin Tier Boundary Convention

声明共享notional boundary归属哪一Tier的provider-neutral规则。G09E既有schema-v1保持lower-inclusive/upper-exclusive；G10C Binance规则使用zero-degenerate first Tier以及positive notional lower-exclusive/upper-inclusive。Boundary选择发生在notional量化之前，不能用epsilon或Scale shift伪造。

## Margin Tier

按exact settlement-currency notional floor/cap定义maximum leverage、maintenance margin rate和maintenance deduction的历史规则层级。Terminal cap可以unbounded或finite；超过finite terminal cap必须structured fail closed，不能映射为unbounded。

## Initial Margin Requirement

单Instrument exposure notional按caller提供的historical selected leverage计算出的最低初始抵押要求。它不是账户Available Margin，也不证明订单可接受。

## Maintenance Margin Requirement

单Instrument exposure按historical Margin Tier计算出的最低持续抵押要求。它不包含账户Equity聚合、跨Instrument净额或Liquidation结论。

## Maintenance Margin Deduction

Margin Tier中从`notional × maintenance margin rate`扣除的非负累计固定额，用于表达连续的分层Maintenance Margin曲线；它不是Fee、Funding或Cash movement。

## Derivative Wallet Balance

单Execution Account、单Venue、单settlement Currency在权威Ledger State中的Cash balance。Realized PnL、Fee与Funding已经通过Journal进入该Cash；账户Equity计算不得再次把这些attribution重复相加。

## Derivative Unrealized PnL

由G09A authoritative signed Position、exact average-entry basis、contract multiplier与`PricePurpose.VALUATION` Mark形成的未结算盈亏。它在单Instrument Money boundary量化后进入Account Margin Projection，不写入Generic Ledger。

## Account Margin Projection

同一Execution Account与Venue下，把Derivative Wallet Balance、逐Instrument Unrealized PnL、G09E Initial/Maintenance requirements和Working Order Margin Reservation聚合成immutable账户视图。v1不执行跨Venue、跨Currency或跨Account collateral netting。

## Available Margin

Account Margin Projection中的`Equity - Position Initial Margin - Working Order Margin Reservation`。它可以为负，负值是账户状态而不是Projection失败，也不等同于Liquidation结论。

## Working Order Margin Reservation

ResourceReservationState中active Orders的`ReservationCommitment.margin`聚合。它只减少Available Margin，不减少Equity，也不进入Generic Ledger balance。

## Liquidation Mark Bar

只由`PricePurpose.LIQUIDATION` Mark stream形成、带完整source/revision/availability的closed Bar extreme evidence。Long审计使用low，Short审计使用high；Trade、Execution、Valuation或Margin OHLC不能替代。

## Conservative Liquidation Audit

以bar开始时保持到bar结束的authoritative Account Margin Projection为基础，对每个Position同时应用方向最不利的Liquidation Mark extreme，重新计算multiplier-aware Unrealized PnL与Maintenance Margin。最不利状态仍满足Maintenance时为`SAFE`；否则因bar内路径未知而为`AMBIGUOUS_BREACH`，不伪造精确强平时点。

## 资格时点（Eligibility Instant）

决定某个 Position 是否参与 Funding、分红或其他离散经济事件的规范模拟时点。

## UTC 时点（UtcInstant）

以 Unix epoch nanoseconds 表示的权威绝对时点，是事件排序和领域序列化的唯一时间表示。

## 交易日期（Trading Date）

由市场 Session 日历赋予事件的交易业务日期标签，不等同于 UTC date 或普通本地自然日。

## Session 身份（Session ID）

标识一个市场交易 Session 及其阶段边界的稳定身份。

## 事件时间（Event Time）

市场事件在市场中实际发生的 UtcInstant。

## 可用时间（Available Time）

市场事件、数据版本或修订最早可以被策略合法观察的时间。

## 数据修订（Data Revision）

供应方对已有可修订记录发布的新版本，具有独立 Revision ID、可用时间和被取代版本引用。修订不能原地覆盖旧版本。

## 时点版本选择（Point-in-time Revision Selection）

在一个决策时点，从所有可用时间不晚于该时点的数据修订中选择最新合法版本的规则。

## 决策时间（Decision Time）

策略基于当时可用信息形成决策的时间。

## 执行时间（Execution Time）

订单实际成交并产生 Fill 的时间。

## 时间线阶段（Timeline Phase）

回测引擎在同一时间戳内处理边界、市场更新、撮合、账户事件、决策和快照的规范顺序。

## 来源序号（Source Sequence）

同一时间戳和时间线阶段内，用于稳定重建事件顺序的确定性序号。

## 模拟时点（Simulation Instant）

由 UtcInstant、时间线阶段和来源序号组成的事件总排序位置。

## 观察视图（Observation View）

Strategy 在当前模拟时点可查询的只读市场信息边界，只包含已经到达可用时间的数据。Strategy 不直接访问市场数据包。

## 决策计划（Decision Schedule）

规定组合策略在哪些模拟时点被调用以产生策略决策的显式时间安排。

## 决策上下文（Decision Context）

组合策略在一个决策点可见的观察视图、前一目标快照和决策计划信息。它不包含账户现金、净值、保证金、其他分舱或工作订单。

## Inventory View

Liquidity Strategy 对其订阅 Instrument 权威账户仓位的只读最小权限视图。

## Working Order View

Liquidity 或 Execution Strategy 对其授权范围内工作订单及剩余数量的只读视图。

## Recent Fill View

Liquidity 或 Execution Strategy 对其授权订单近期成交的只读视图。

## 策略状态（Strategy State）

包含一个 Strategy 所有影响未来决策或订单意图的可序列化业务状态。它不包含可重建性能缓存或独立财务持仓。

## 策略状态检查点（Strategy State Checkpoint）

在确定模拟时点保存的 Strategy State canonical identity，用于恢复后验证后续行为一致。

## 模型产物（Model Artifact）

由固定训练数据、训练区间、特征 Schema 和训练代码产生，并具有内容摘要和可用时间的不可变模型。

## 模型修订时间线（Model Revision Timeline）

按可用时间记录 Strategy 在 Walk-forward 过程中可以使用的 Model Artifact 版本序列。

## 命名随机流（Named Random Stream）

由主 Seed、组件身份、Instrument 和用途确定性派生的独立随机序列。一个组件的随机调用不能改变其他随机流。

## 随机流清单（Random Stream Manifest）

记录一次运行全部随机流的算法、版本、Stream Key 和 Seed 派生方式的证据。

## 组合策略（Portfolio Strategy）

由决策计划调用、通过目标暴露表达市场观点的策略。它不负责生成具体交易场所命令。

## 流动性策略（Liquidity Strategy）

通过挂单、改单和撤单意图获取点差、提供流动性或管理订单簿暴露的策略。它不等同于具体交易场所 Adapter。

## 执行策略（Execution Strategy）

将既定交易需求按时间、价格和流动性约束拆分为订单意图的策略。它不决定上游投资观点。

## 策略决策候选（Strategy Decision Candidate）

由组合策略或预计算输入产生、尚未通过领域校验的候选输出。它可以保留重复目标、未知 Instrument、非法时间或未量化值，不是权威执行对象。

## 策略决策（Strategy Decision）

候选通过策略输出校验后形成的权威组合策略决策，包含决策时间、已观察时间和目标。策略决策不是已审批组合目标、订单或部署授权。

## 策略输出校验（Strategy Output Validation）

在候选决策进入批次前验证其 Schema、Instrument、时间因果性、唯一性和数值规范化的领域入口。它返回权威策略决策或结构化校验失败，不负责 Run Outcome 映射或判断正常经济目标是否超过风险预算。

## 输入来源（Input Origin）

说明候选决策来自运行时 Strategy 还是预计算输入的 Runtime 属性，用于把同一种校验失败映射为 FAILED 或 BLOCKED。

## 策略契约违规（Strategy Contract Violation）

Strategy 输出违反领域 Schema、时间因果性、Instrument identity 或量化规则的缺陷。Runtime Strategy 违规导致 FAILED，预计算输入违规导致 BLOCKED。

## 决策批次（Decision Batch）

在同一决策时点校验并独立收集全部已调度组合策略决策后形成的原子集合。组合分配、净额化和下单只能在整个批次完成后开始。

## 目标快照（Target Snapshot）

一个策略分舱在指定生效时间的完整、绝对目标暴露集合。新快照原子替换旧快照，省略的旧目标归零。
_Avoid_: Target patch, position delta

## 目标流（Target Stream）

按决策时间排序、每项携带目标快照的策略决策序列，可以由历史时间线中的策略产生，也可以作为预计算输入提供。目标流不是增量仓位命令、已成交仓位或收益率序列。

## 目标有效期（Target Validity）

由生效时间、过期时间和过期目标策略共同定义的策略目标生命周期。订单过期不会使目标失效。

## 过期目标策略（Stale Target Policy）

目标快照过期后决定继续保持目标、转为空仓目标或停止新订单的显式规则。

## 订单意图（Order Intent）

尚未经过市场规则、资源和交易前风险校验的 canonical venue-neutral 下单请求。它表达执行方式、价格约束、有效方式和仓位效果，但不包含 Binance、Hummingbot 或券商专用命令。

## 订单能力集合（Order Capability Set）

一个市场语义 Profile 和执行账户 Profile 共同支持的 canonical Execution Style、价格约束、有效方式和仓位效果集合。

## 可执行订单规格（Executable Order Spec）

Canonical OrderIntent 通过能力校验和翻译后形成的已解析订单规格。它可以携带已解析 Profile 和账户约束，但仍不是 Hummingbot 或券商 DTO。

## Venue 订单请求（Venue Order Request）

具体 Simulation 或 Live Venue Adapter 根据 Executable Order Spec 生成的场所专用请求。

## 订单翻译报告（Order Translation Report）

记录 canonical OrderIntent 到 Executable Order Spec 的能力检查、字段映射和拒绝原因的审计证据。

## 订单事件流（Order Event Stream）

记录一个订单从意图、风险、提交、激活到成交、撤销或过期的不可变生命周期事件序列，是订单状态的权威证据。

## 订单状态（Order State）

从订单事件流重建的当前生命周期投影，不是独立权威记录。

## 因果标识（Causation ID）

标识一个领域事件由哪个 Decision、Plan、Intent 或前序事件直接引起的稳定引用。

## 确定性领域标识（Deterministic Domain ID）

由语义运行命名空间、因果父标识和稳定序号派生的模拟领域身份。相同语义运行的不同执行尝试产生相同领域标识。

## 撤单意图（Cancel Intent）

尚未经过校验的 venue-neutral 撤销活动订单请求。

## 市场规则评估（Market Rule Evaluation）

在交易前风险之前根据时点有效规则判断可执行订单规格的数量、价格、有效方式、Session、权限和最小名义金额是否合法的权威决策。

## 费用预留估算（Fee Reservation Estimate）

下单前根据订单及市场、税费和账户规则计算的保守费用承诺。它只影响资源预留和可用资源，不是最终费用评估或会计流水。

## 交易前风险（Pre-trade Risk）

在合法订单进入执行场所前判断其最坏成交后账户状态是否满足现金、保证金、工作订单、暴露和安全限制的最终门控。它只能批准或拒绝，不能修改订单。

## 规划省略（Planning Omission）

订单规划明确决定无需生成订单的结果，例如目标变化落入 Deadband。它不是订单拒绝。

## 交易前风险拒绝（Pre-trade Risk Rejection）

订单意图因账户或风险限制未获批准，因此从未提交执行场所的结果。

## 市场规则拒绝（Market Rule Rejection）

订单意图因数量、价格、Session、权限或其他市场规则不合法而未被提交或接受的结果。

## 执行拒绝（Execution Rejection）

已经提交的订单被模拟或真实执行场所拒绝的结果。

## 权威执行内核（Authoritative Execution Kernel）

统一执行交易前风险、市场规则、成交、交收和账户核算的状态转换。组合策略、预计算目标和流动性策略路径最终必须进入此内核。

## 资本分配策略（Capital Allocation Policy）

在每个决策点根据权威组合快照和运行配置确定策略分配净值的规则。它不属于组合策略内部逻辑。

## 策略分配（Strategy Allocation）

资本分配策略在特定估值时间为一个组合策略确定的可用净值及其估值货币。

## 策略分配净值（Strategy Allocation NAV）

策略分配中的净值金额，是目标暴露比例的估值基准，不等同于整个账户净值。

## 目标暴露比例（Target Exposure Fraction）

某 Instrument 的有符号目标名义暴露除以策略分配净值，并以 Trading Domain 规定 Scale 的定点整数表示。它不是绝对数量、交易金额、裸信号或订单。

## 执行账户 Profile（Execution Account Profile）

描述一个执行账户的费用合同、权限、保证金模式、杠杆和借贷规则的版本化行为集合。它不包含期初现金和持仓。

## 期初账户状态（Initial Account State）

一次运行开始时执行账户的现金、持仓、待结算项目和必要成本基础。它不定义账户行为规则。

## 执行账户（Execution Account）

一次回测运行中接受订单、持有真实模拟现金和仓位并承担结算与保证金责任的账户。第一阶段每次运行只允许一个执行账户 Profile 和执行账户。

## 报告货币（Reporting Currency）

一次回测运行用于汇总账户权益和绩效的唯一估值货币。它不改变现金或费用事件的原生币种。

## 货币估值图（Currency Valuation Graph）

使用 point-in-time Price Stream 将执行账户原生币种余额转换为报告货币的有向转换图。

## 货币估值策略（Currency Valuation Policy）

在存在多条货币转换路径时选择唯一权威路径，并规定 Peg 等特殊估值假设的版本化规则。

## Peg 估值策略（Peg Valuation Policy）

明确声明某种 Stablecoin 在规定适用范围内如何相对另一货币估值的版本化假设。不存在该策略时禁止隐式按 1:1 处理。

## 策略分舱（Strategy Sleeve）

一个组合策略在共享执行账户中的逻辑资本和目标边界。它不拥有独立的真实现金或交易所持仓。
_Avoid_: Strategy account, virtual account

## 组合分配（Portfolio Allocation）

将多个策略分舱的目标暴露和分配净值聚合并净额化为账户级目标名义暴露的权威决策。

## 净额化（Netting）

在订单规划前，将同一 Instrument 上来自不同策略分舱的相反或重复暴露合并为单一账户目标。

## 组合风险（Portfolio Risk）

在账户目标层审批、限制或拒绝 Gross/Net exposure、集中度、杠杆、分舱和保证金预算的规则集合。它可以显式变换目标。

## 已审批组合目标（Approved Portfolio Target）

组合风险处理后的账户级权威目标持仓集合，记录原目标、应用限制、最终目标和被拒绝项目。

## 数量格点（Quantity Lattice）

一个 Instrument 在特定时点允许的原子 Scale、Step、买卖 Lot、最小数量、最小名义金额和 odd-lot 规则集合。若订单数量规则依赖当前持仓或可卖余额，Lattice 必须显式声明该状态依赖，不能把它伪装成静态目标数量倍数。

## 卖出余股成分（Sell Residual Component）

在权威可卖余额 `H` 下，相对于正常卖出 Lot `L` 的严格小于 `L` 的余数 `H mod L`。完整余股可以单独或与正常 Lot 合并在一次订单申报中；它不表示任意小于 `L` 的卖出数量都合法，也不保证一次成交完成。

## 仓位可达数量（Reachable Position Quantity）

从当前 Position 以单一交易方向调整，在合法可达集合中选择不扩大 raw target 绝对暴露且距离 raw target 最近的 Quantity。减仓时允许越过 raw target 继续向零，但禁止先背离目标、穿越零点或通过反向多腿扩大可达集合。它不自动等于从零开始的静态 Lot 整数倍。

## 仓位相对可达性过期（Position-relative Reachability Stale）

一个 Normalized Target 的合法可达性绑定 Sizing 时的当前仓位和 Lattice；若仓位随后变化且原订单 remainder 不再由同一 Target lineage exact-cover，Coordinator 必须停止重新规划并要求重新 Sizing，不能把新出现的 odd delta 当作合法 successor order。Signed legacy/cross-zero path 不使用该状态。

## 规格化残差（Sizing Residual）

Position Sizing 中 raw target Quantity 与 final target Quantity 的差。它不同于当前持仓的 Sell Residual Component，两者不能都简称为“余股”。

## 仓位规格化（Position Sizing）

根据已审批目标名义暴露、市场价格、合约乘数和数量格点确定不扩大已审批风险的可交易目标数量。
_Avoid_: Strategy sizing

## 规格化组合目标（Normalized Portfolio Target）

已审批组合目标在决策时点经过数量格点、舍入和残余策略处理后形成的账户级可交易目标数量集合。

## 活跃组合目标（Active Portfolio Target）

由策略目标比例在决策时点原子物化的精确目标数量，是再平衡协调器持续逼近的权威目标。后续价格或净值变化不会隐式重算它。

## 残余仓位策略（Residual Position Policy）

当市场数量或最小名义规则使目标无法完全实现时，明确选择保留 Dust、在允许时清仓或使运行失败的规则。

## 先平后开（Close Before Open）

目标方向反转时先关闭当前方向并确认归零，再建立相反方向仓位的订单规划语义。

## 工作订单（Working Order）

已经进入订单生命周期但尚未达到终态、其剩余数量仍可能改变账户持仓并占用资源的订单。

## 结算义务（Settlement Obligation）

由成交产生、将在版本化账户语义所声明的结算时点完成的资产或现金交付要求。它具有稳定身份并引用来源 Fill；该账户层时点不自动等同于中央结算参与人批次、法律权属登记或银行服务时点。

## 结算簿（Settlement Book）

保存并推进未完成结算义务的可重建状态，不等同于会计流水或订单资源预留。

## 可用性投影（Availability Projection）

根据账户账本、结算簿、资源预留簿和市场规则计算总持仓、可卖数量、已结算现金、可交易现金、可提现现金和可用保证金的派生状态。

## 可用性成熟时点（Availability Maturation Instant）

一个已入账经济权益或账户交付义务完成、因而开始计入特定可用资源维度的明确时点。它不自动等同于中央交收批次、法律权属登记或银行服务时点，必须由版本化市场/账户语义显式声明。

## A 股 T+1 可卖（A-share T+1 Sellability）

普通人民币 A 股在 T 日买入后立即形成经济持仓，但 T 日不可卖；只有下一已声明交易日才进入可卖数量。下一交易日必须来自权威 Calendar，不得用自然日或工作日猜测。

## A 股现金账户交付约定（A-share Cash-account Delivery Convention）

G08B development-grade Profile 中，买入负现金和卖出负持仓在 Fill 时完成交付；买入正持仓在下一 Frozen TradingDate 本地 00:00 成熟，卖出正现金在本地 16:00 成熟。后两者是版本化客户账户约定，不冒充逐 Fill 中央净额交收、法律权属登记或所有券商统一提现承诺。

## 卖出资金可交易/可提现分离（Sale Proceeds Tradability/Withdrawability）

卖出所得在现金账户中的再投资能力与向外提现能力是两个独立可用性维度；不同 Market/Account Profile 必须分别声明其成熟条件，不能把“可用”自动解释为“可取”。

## 资源预留簿（Resource Reservation Book）

根据工作订单维护现金、可卖数量、初始保证金、借贷能力和额度承诺的可重建非财务状态。预留不是会计流水或结算义务。

## 可用资源（Available Resources）

可用性投影扣除已有订单预留后，仍可供新订单承诺的现金、数量、保证金和权限额度。

## 再平衡协调器（Rebalance Coordinator）

根据持续有效的目标快照、当前组合、工作订单和市场状态，反复决定下单、撤单或省略规划以逼近目标的共享交易内核模块。

## 再平衡策略（Rebalance Policy）

规定再平衡协调器在拒单、过期、Session 变化和其他触发器后何时重试、等待或停止的版本化规则。

## 订单计划有效期（Order Plan Validity）

由计划所依据的目标、组合快照、工作订单集合和截止时间共同定义的计划生命周期。任一前提变化会使计划被取代。

## 计划取代（Plan Supersession）

目标、组合或工作订单前提变化后，旧订单计划不再允许产生新订单的状态。它不会自动撤销已经提交的订单。

## 订单有效方式（Time in Force）

交易场所规定订单在 Session、时间或成交条件下保持活动或终止的生命周期规则，例如 DAY、GTC、IOC、FOK 和 GTX。

## 订单计划（Order Plan）

再平衡协调器根据当前账户状态、工作订单、规格化目标和市场规则生成的一组计划订单及其执行约束。

## 计划订单（Planned Order）

尚未提交给模拟或真实执行场所的订单意图。

## 成交（Fill）

订单在特定时间、价格和数量上实际执行的不可变事实。成交本身不承载唯一最终费用。

## 费用评估（Fee Assessment）

根据一个或多个 Fill、Order 或 Session 及其市场、税费和账户规则计算出的不可变费用事实。

## 费用入账（Fee Charged）

将费用评估转化为账户现金和损益影响的会计流水项。

## 仓位核算模型（Position Accounting Model）

将特定 Instrument 的成交和仓位经济事实翻译为会计流水项的规则。它不能直接修改账户账本状态。

## 线性永续合约（Linear Perpetual Contract）

以结算币计价、盈亏与价格变化和合约乘数线性相关、没有固定到期日的衍生 Instrument。合约乘数明确表示每份合约对应的基础资产数量。

## 精确平均入场基础（Exact Average Entry Basis）

线性净持仓未平仓部分的正有理数平均入场价格。它以约分后的整数分子和正分母表达，不是舍入后的固定小数价格，也不是现金类取得批次。

## 线性仓位投影（Linear Position Projection）

按 caller 给定顺序从成交序列确定性重建单向净 Long、Short 或 Flat 状态及 OPEN、ADD、REDUCE、CLOSE、FLIP 转换的不可变证据。它不是会计流水、账户账本或保证金投影。

## 仓位翻转（Position Flip）

单个反向成交完全关闭原方向后仍有剩余数量并立即建立相反方向净持仓的转换。新方向的入场基础只来自该 crossing Fill，不继承已关闭方向的基础。

## 精确线性已实现盈亏（Exact Linear Realized PnL）

由线性仓位转换的旧方向符号、关闭数量、合约乘数、退出价格与转换前精确平均入场基础计算出的约分有理数结算币金额。它在进入 caller-supplied Money QuantizationPolicy 前不进行舍入。

## 线性衍生品会计流水项（Linear Derivative Journal Entry）

继承通用 AccountingJournalEntry 并把完整线性仓位转换、会计请求、量化策略和精确已实现盈亏直接纳入同一不可变流水身份的 specialized Entry。Generic Ledger 只读取其通用经济字段，不按衍生品类型分支。

## 线性衍生品账本投影（Linear Derivative Ledger Projection）

按 Accounting Journal 已发布顺序从 specialized Entries 重建精确平均入场仓位状态，并与 Generic Ledger 的 signed Position Quantity 核对的不可变投影。它是 Journal 的确定性视图，不是第二财务权威。

## 取得批次（Acquisition Lot）

现金类 Instrument 由一次买入成交取得的不可变数量、单位成本、费用和时间来源记录。

## 成本基础策略（Cost Basis Policy）

执行账户 Profile 在卖出现金类 Instrument 时选择和消耗取得批次的版本化规则，例如 FIFO、LIFO、加权平均或特定识别。

## 保证金模型（Margin Model）

根据 Instrument、仓位和账户状态计算初始保证金、维持保证金和可用保证金的市场规则。

## 强平模型（Liquidation Model）

根据保证金状态、市场价格和数据粒度判断强平风险的规则。模型不能声称超过输入数据所能证明的精度。

## 强平审计（Liquidation Audit）

使用 Bar 最不利价格判断仓位明确安全或可能发生盘中强平的保守检查。可能强平但过程不可确定时称为模糊突破。

## 模糊突破（Ambiguous Breach）

Bar 数据显示盘中可能跌破维持保证金要求，但不足以重建强平时刻和成交过程的状态。它会阻断 decision-grade 运行。

## 外部资金流（External Cash Flow）

由充值、提现或获批准资本调拨引起的账户现金变化。它改变 Equity 和资本分配基准，但不是 Trading PnL。

## 会计流水（Accounting Journal）

由成交、费用、融资、外部资金流、结算和公司行为产生的不可变经济事实序列，是执行账户现金、持仓和已实现盈亏的唯一财务权威。已经发生的经济事实不能因违反风险或账户权限而被丢弃。

## 交易后风险违规（Post-trade Risk Breach）

已发生并完成核算的成交导致账户违反权限、现金、保证金或风险限制的明确事实。它不撤销成交或会计流水。

## 完整性发现（Integrity Finding）

运行过程中发现的数据、状态或契约问题记录，可以是阻断问题或限制说明，不得通过修改既有经济事实消除。

## 会计流水项（Accounting Journal Entry）

会计流水中的单个不可变经济事实，具有稳定身份和来源引用，可以被幂等应用。

## 账户账本（Accounting Ledger）

将会计流水投影为现金、持仓、费用和已实现盈亏状态的权威状态转换模型。策略分舱归因不是独立财务账本。

## 组合快照（Portfolio Snapshot）

账户账本状态与指定时点市场估值结合产生的可重建账户投影，不是独立财务权威。

## Bar Engine

基于 K 线推进组合型中低频回测的模拟模块。第一阶段只有下一可交易 Bar 开盘模型可以产生 decision-grade 结果。

## 下一可交易 Bar 开盘（Next Eligible Bar Open）

订单在决策所属 Bar 之后，首个满足交易 Session、Instrument 状态、方向性流动性和订单规则的真实 Bar 开盘时获得成交资格的模型。它禁止 same-bar fill。

## 价格限制流动性阻断（Liquidity Blocked at Limit）

A 股 Buy 在 upper-limit open 或 Sell 在 lower-limit open 时，由保守 Bar 模型产生的无成交状态。它不是订单规则拒绝，也不根据全天 Volume 推断排队成交。

## 参考价格（Reference Price）

模拟成交在应用滑点前使用的可观察市场价格，例如下一可交易 Bar 的原始开盘价。

## 滑点模型（Slippage Model）

根据参考价格、订单和市场状态计算模拟成交价格偏移的版本化假设。它不决定订单成交资格，也不是市场事实。

## 滑点决策（Slippage Decision）

滑点模型针对一个成交候选产生的不可变结果，记录参考价格、偏移、执行价格、模型、校准证据和适用范围判断。

## 适用范围（Applicability Envelope）

模型经过校准并允许用于 decision-grade 结果的 Instrument、订单规模、参与率、波动率和市场状态边界。

## 校准证据（Calibration Evidence）

说明一个模拟模型参数如何从具有稳定身份的数据和方法得到的可审计证据。

## 市场费用规则（Market Fee Rules）

交易场所对所有适用账户规定的公共费用结构，不包含账户专属费率等级或券商合同。

## 账户费用计划（Account Fee Schedule）

执行账户 Profile 规定的费率等级、返佣、券商佣金和最低佣金合同。

## A 股历史税费规则簿（A-share Historical Fee and Tax Rule Book）

按 Venue 与半开有效时点区间冻结证券交易经手费、监管费、过户费和卖方印花税的 caller-injected immutable evidence。缺口或重叠必须 fail closed；不能从当前网页、最近区间或账户佣金反推历史市场税费。

## 每 Fill 市场税费 / 每 Order 账户佣金（Per-Fill Market Charges / Per-Order Account Commission）

市场费用和印花税按每个不可变 Fill 及其执行时点规则最终评估；券商佣金按终态 Order 的实际 Fill 聚合并只应用一次账户最低佣金。下单前 Fee Reservation 仍按完整获批订单保守估算，不是上述任一最终费用事实。

## 费用预留舍入缓冲（Fee Reservation Rounding Buffer）

当最终费用逐 Fill、逐 component 舍入而预留按聚合订单名义金额估算时，基于 caller-supplied 最大 Fill 数 N 增加的 canonical 非财务缓冲。A 股 G08E 对每个适用 component 预留 `floor(N/2)` 个 CNY cent；实际 Fill 数超过 N 必须 fail closed，不能继续声称预留是保守上界。

## Microstructure Replay Engine

基于 Quote、Trade 或订单簿事件模拟撮合、队列、部分成交和高频执行的回放模块。

## 运行结果状态（Run Outcome）

一次回测执行的终态，区分完整完成、完整性阻断、系统失败和主动取消。它不等同于结果等级。

## 阻断运行（Blocked Run）

因预期内的数据、因果性、规则、模型适用性或市场歧义问题而失败关闭的运行。它保留诊断证据，但不产生正式回测结果。

## 失败运行（Failed Run）

因系统缺陷、未处理异常、不变量实现错误或证据持久化失败而终止的运行。它不是市场或数据结论。

## 请求摘要（Request Hash）

标识一次回测全部规范化语义输入和不可变输入引用的内容摘要。

## 执行结果摘要（Execution Result Hash）

标识影响交易与财务结果的规范化决策、分配、风险、订单、成交、会计流水和最终组合状态的内容摘要。

## 证据清单（Evidence Manifest）

列出一次运行全部权威证据的角色、Schema、位置和内容摘要的不可变清单。

## 可重建（Rebuildable）

一次运行的全部语义输入、引用数据和代码身份仍可取得，因此能够重新产生并比较权威结果。

## 指标 Profile（Metric Profile）

规定估值计划、收益计算、年化基准、无风险利率、现金流处理、回撤采样、报告货币和 Benchmark 的版本化分析口径。

## 分析产物摘要（Analysis Artifact Hash）

标识一个执行结果在特定指标 Profile 下派生的规范化 Metrics 和分析证据的内容摘要。

## 结果等级（Result Grade）

回测结果可用于何种决策的证据等级。Development Grade 允许显式近似；Decision Grade 要求规定的数据、规则和完整性证据。

## 完整性阻断项（Blocking Integrity Issue）

使一次运行不能被视为成功结果的数据、时间、规则、核算或状态错误。

## 限制（Limitation）

不会使运行失败，但降低结果真实性或适用范围的显式近似和已知缺口。

## 部署授权（Deployment Authorization）

允许系统进入 Shadow 或 Live 的独立审批结果。回测成功本身不产生部署授权。

## Parity Contract

规定同一输入下新旧实现各领域字段使用 exact、quantized-equal、ordered-sequence-equal、显式容差或已批准语义变化进行比较的契约。禁止全局 epsilon。

## Parity Report

记录 Parity 比较的首个分歧、受影响领域、期望与实际值、Comparator、来源和已批准变化引用的证据。
