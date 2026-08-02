# Domain Glossary

## 回测运行（Backtest Run）

一次由固定请求、固定市场证据、固定策略版本和固定代码环境驱动的可重复模拟。运行产生唯一的结果与证据集合。

## 市场数据包（Market Bundle）

经过完整性验证并带有 Manifest 的历史市场证据集合。它可以包含行情、Funding、交易规则、公司行为和交易日历，但不等同于任意 DataFrame 或文件目录。

## 市场 Profile（Market Profile）

描述一个市场交易语义的能力组合，包括交易 Session、Instrument、订单规则、成交、交收、融资和公司行为。它不是某个交易所客户端。

## 市场事件（Market Event）

影响策略观察、交易可行性或账户状态的已发生事实，例如 Bar 完成、报价变化、Funding、停牌、结算或公司行为。

## 事件时间（Event Time）

市场事件在市场中实际发生的时间。

## 可用时间（Available Time）

市场事件或数据最早可以被策略合法观察的时间。

## 决策时间（Decision Time）

策略基于当时可用信息形成决策的时间。

## 执行时间（Execution Time）

订单实际成交并产生 Fill 的时间。

## 策略决策（Strategy Decision）

策略对期望风险或持仓的表达，包含决策时间、已观察时间和目标。策略决策不是订单，也不是部署授权。

## 期望持仓（Desired Position）

策略希望持有的 Instrument 风险或数量，在组合聚合和风险审批前不具备执行权威性。

## 已审批组合目标（Approved Portfolio Target）

组合和风险规则处理后的权威目标持仓集合，记录被应用的限制和被拒绝的目标。

## 订单计划（Order Plan）

根据当前账户状态、已审批组合目标和市场规则生成的一组计划订单及其执行约束。

## 计划订单（Planned Order）

尚未提交给模拟或真实执行场所的订单意图。

## 成交（Fill）

订单在特定时间、价格和数量上实际执行的不可变事实。

## 账户账本（Accounting Ledger）

根据成交、费用、融资、结算和公司行为维护现金、持仓、盈亏、保证金和权益的权威状态转换模型。

## 组合快照（Portfolio Snapshot）

账户账本在指定时间的现金、持仓、盈亏、费用、保证金和权益状态。

## Bar Engine

基于 K 线或其他离散聚合行情推进组合型中低频回测的权威模拟模块。

## Microstructure Replay Engine

基于 Quote、Trade 或订单簿事件模拟撮合、队列、部分成交和高频执行的回放模块。

## 结果等级（Result Grade）

回测结果可用于何种决策的证据等级。Development Grade 允许显式近似；Decision Grade 要求规定的数据、规则和完整性证据。

## 完整性阻断项（Blocking Integrity Issue）

使一次运行不能被视为成功结果的数据、时间、规则、核算或状态错误。

## 限制（Limitation）

不会使运行失败，但降低结果真实性或适用范围的显式近似和已知缺口。

## 部署授权（Deployment Authorization）

允许系统进入 Shadow 或 Live 的独立审批结果。回测成功本身不产生部署授权。

## Parity

新旧实现对同一输入产生相同领域结果的兼容性。Parity 应比较决策、订单、成交、持仓和核算，而不只比较最终收益率。
