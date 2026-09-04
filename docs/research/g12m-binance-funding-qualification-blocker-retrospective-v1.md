# G12M Binance Funding History 资格阻塞复盘 v1

- 状态：已确认
- 日期：2026-08-21
- 范围：Binance USD-M Funding History source-bounded v2 → G12M Runtime qualification
- 关联 blocker plan：[`g12m-binance-usdm-funding-history-qualification-v1.md`](../implementation/plans/g12/g12m-binance-usdm-funding-history-qualification-v1.md)

## 结论

Binance Funding History source-bounded v2 是有效且已接受的**事后来源证据**，但目前不能用于声明某个 Binance Run 满足 `SOURCE_BOUNDED_DECISION_GRADE`。

真正阻塞不是 provider checksum、future finality 或 correction completeness；ADR 0008 已允许将这些记录为 limitation。真正阻塞是：

1. 当前单流 evidence Bundle 不具备生产 Binance Profile 所需的完整 capabilities，不能作为 execution Bundle 完成 resolution；
2. 三条 Funding Event 没有被证明在合法历史 Run 窗口内可用，因此当前 evidence model 必须 fail closed；
3. 当前生产 Binance Profile 仍是 Development-only；
4. 没有已接受的 Binance decision-grade canonical Result；
5. 没有证明三条 Event 被 Runtime 消费并得到确定性 accounting disposition 的 trace。

这是一次**资格规划和验收顺序失误**，不是底层双时间模型失误。`event_time` / `available_time` 分离和 Runtime fail-closed 规则正确地阻止了错误 qualification。当前结论是“历史可用性未被证明”，不是“Binance 数据已被证明在 2024 年不可用”。

## 背景

已接受的 source-bounded v2 保存并验证了：

- 精确 REST request/response bytes；
- acquisition receipt；
- deterministic SourceSnapshot；
- 三条 rate + funding-time mark source rows；
- 精确 decimal scale-8 normalization；
- 三条 `MarketEvent`；
- G12C stream/manifest 和 `MarketBundleRef`；
- append-only correction 边界；
- provider finality、completeness、live 和 deployment 非声明。

关键身份：

- implementation：`024e5f209a94bb358946f5c468630108981f0329`
- response：`sha256:e9f73f9c845c28abb31037d8230df2d6f13d5d368c43436e891fcc757372c338`
- receipt：`sha256:a92989478047de7d744744aedeaf365f7d16240b536c1ccece749abe3b4efa36`
- Snapshot：`sha256:a45d9acdcfb4d42d1c70af44969f6a5151fb260c4c3040943b3d961c1073aa3f`
- Bundle-ref manifest：`sha256:352aa6a20c9c04dc998d07e6935f6bb635fb52459a361648262565d5773423fb`
- report：`sha256:29e639615c1e5f5fa05ffdff9bc77a630d56838c7b0e70230177922bdbffc37b`
- canonical report file：`sha256:850cf2b5b2f3caffd7afc1cb4f364e6224c4022417ae46bb01a406600e971951`

这些身份仍然有效，不需要撤销或修改。

## 遇到的现象

三条 Funding Event 的业务时间分别为：

- `2024-01-01T00:00:00Z`
- `2024-01-01T08:00:00Z`
- `2024-01-01T16:00:00Z`

Bundle 覆盖范围为：

```text
[2024-01-01T00:00:00Z, 2024-01-02T00:00:00Z)
```

但三条 Event 的 `available_time` 都来自真实本地 receipt：

```text
1787304863983843230 epoch nanoseconds  # 2026 local observation
```

当前 accepted Bundle 是一个 funding-evidence 单流 Bundle，只提供 `binance_usdm.funding-publications@2`。生产 Binance Profile 还要求 `account.financial-event@1`、`bar_open@1`、`binance_usdm.price-purpose-streams@1`，precomputed strategy 还要求 `precomputed_target_stream@1`。因此当前生产 Run 首先会在 capability compatibility 阶段失败，不能仅凭该 `MarketBundleRef` 完成 resolution。

availability 仍是独立的后续 blocker。即使未来构造了包含相同 Funding Event 的兼容 joined Bundle，只要历史 Run 的结束时间仍位于当前 2024 coverage 内，Runtime timeline 就会在下列条件成立时停止发射：

```text
event.available_time >= request.timeline_window.end_exclusive
```

当前 accepted Event 满足：

```text
2026 local receipt available_time > 2024 historical Run end
```

所以，在当前已接受的 evidence model 中，这三条 Event 没有被证明可以在 2024 Run 内发射，必须按不可见处理。它们是否在真实 Binance 系统中更早可用仍是未知，而不是已证明为否。

## 根本原因

### 1. 混淆了“后来观察到”和“当时可获得”

当前证据能够证明：

> 在 2026 年抓取时，Binance 返回了这三条精确的 2024 年 Funding History 记录。

它不能证明：

> 在 2024 年每条记录被 Run 使用之前，相同 rate + mark 内容已经发布并可获得。

`fundingTime` 是业务生效时间，不自动等于可验证的历史发布时间。把 `available_time` 人工改成 `fundingTime` 会制造无来源支持的历史可用性，形成 lookahead。

### 2. 混淆了 evidence Bundle 与 execution Bundle

G12C publication 能够为一个精确来源切片生成合法的 Bundle，不表示该 Bundle 已包含生产 Run 所需的全部市场角色。当前 funding-history Bundle 的职责是保存和发布三条 funding evidence；它缺少生产 Binance Profile 所需的 bar、price-purpose、financial-event 和 target-stream capabilities。

因此当前 `MarketBundleRef` 是有效 evidence identity，但不是可直接执行的 production Run input。未来需要一个保持 source lineage 的兼容 joined Bundle，而不是让 Profile 忽略缺失 capabilities。

### 3. 错把 BundleRef 相等当成 Event 消费证明

`request.market_bundle_ref == accepted_report.bundle_ref` 只能证明 Run 声明绑定了该 Bundle。

它不能证明：

- Event 通过了 timeline availability gate；
- Event 被写入 canonical `TIMELINE_EVENT` trace；
- accounting 为 Event 产生了确定性 disposition，并在存在相关持仓时实际应用了 rate 和 mark。

因此 BundleRef 是必要条件，但不是充分条件。

### 4. G12M 前置 Grade 权威不存在

ADR 0008 要求 G12M 只能资格评估一个已经满足以下条件的完成结果：

```text
RequestedResultGrade.DECISION_GRADE
ResultGrade.DECISION_GRADE
```

当前生产 Binance Market、Simulation 和 Execution-account registrations 均保持：

```text
RequestedResultGrade.DEVELOPMENT
decision_grade_eligible = false
```

Binance funding-source resolution 不拥有 `RequestedResultGrade` 字段，但同样固定为：

```text
decision_grade_eligible = false
```

G12M 无权升级这些值。通过测试代码 `dataclasses.replace` 或手工构造对象制造 decision-grade Result 属于自证，不能成为生产 authority。

### 5. 缺少可接受的 Run 与消费链

目前不存在一个为该 source case 接受并冻结的 Binance decision-grade canonical Result，因而无法绑定：

- persisted canonical publication identity；
- semantic run、request 和 Integrity context/report；
- Bundle、Build、Profile、Environment；
- execution result；
- 三条 Funding Event 的 timeline trace；
- 每条 Event 的确定性 accounting disposition；有相关持仓时还需 settlement/journal evidence。

公开可构造的 `FinalizedCanonicalResultV2` 只能证明对象内部一致，不能替代已持久化、独立验证并接受的真实 Run。

## 我们的设计失误

失误发生在资格规划与验收顺序：

```text
source evidence accepted
→ provider-specific nominal reconstruction ready
→ 误以为可以直接进入 successful G12M qualification
```

正确顺序应当是：

```text
source evidence accepted
→ evidence Bundle 与 execution Bundle 职责分离
→ compatible joined Bundle 满足生产 capabilities
→ causal availability 可证明且 Event 可实际发射
→ production Profile 已具备 decision-grade authority
→ accepted canonical Result 存在
→ trace 证明 Event 被消费并有确定性 accounting disposition
→ G12M qualification
```

D4 复审验证了 bytes、hash、Snapshot、Event、manifest、nonclaims 和 correction 边界，但没有先把 evidence flow 贯穿到 production capability resolution、Runtime timeline 与生产 Profile grade。这是审查范围的缺口。

## 正确工作的设计

以下设计不应修改：

1. `event_time` 与 `available_time` 分离；
2. Runtime 对未被证明在使用前可用的数据 fail-closed；
3. Bundle coverage 限制 request timeline；
4. G12M 不 mint、upgrade 或 downgrade `ResultGrade`；
5. ADR 0008 仍把 observed-after-use 和 lookahead 视为真实 blocker；
6. correction 保持 append-only，不覆盖旧 source、assessment 或 Run。

这些规则正是发现问题并阻止错误 qualification 的防线。

## 已实施的处理

1. Funding History source-bounded v2 保持 `PASSED`，用途限定为精确 post-hoc source corroboration。
2. 没有实现会错误返回成功的 Runtime assessor。
3. 没有创建 synthetic decision-grade golden Result。
4. 已冻结 blocker plan：
   - 文件：`docs/implementation/plans/g12/g12m-binance-usdm-funding-history-qualification-v1.md`
   - commit：`04322d84b17aa238691c72d4d289621003d5e63b`
   - file SHA-256：`9d1491f3c05ea085aeb9948956c7b5c4dda3aac5e07df1808c371dc817ea7f85`
5. G12M market qualification 任务保持未完成，并新增 causal Binance authority blocker。
6. Acceptance Matrix、G12 README 和 G12M governance plan 尚未同步引用 blocker plan；在完成同步前，权威 registry 中的 Binance `nominal ready` 只能解释为 upstream nominal reconstruction ready，不能解释为 successful Runtime qualification ready。

## 解决方案

### 当前方案

将状态明确区分为：

```text
Upstream Builder evidence reconstruction: ACCEPTED
Post-hoc corroboration: READY
Runtime independent reconstruction: NOT IMPLEMENTED
Production execution Bundle compatibility: BLOCKED
Runtime source-bounded qualification: BLOCKED
Live/deployment: FALSE
Governance registry synchronization: PENDING
```

不得通过以下方式绕过：

- 把 assessment 时间设到 2026 年以后；
- 把 `available_time` 无证据回填为 `fundingTime`；
- 只比较 BundleRef 或 hash；
- 使用 monthly rate-only archive 或附近 mark-price stream 替代 exact rate+mark；
- 在测试中制造 decision-grade Profile/Result。

### 解除阻塞所需条件

未来只有在以下条件全部独立接受后，才能重新冻结 G12M successful interface：

1. **因果可用性证据**：证明每条 Funding Event 的数据在 Runtime 实际使用时间之前已可获得；不能从 event time 推断。
2. **兼容 Bundle**：一个 immutable Bundle 同时包含 exact funding Events 和生产 Binance Profile 所需的其他 capabilities，coverage 允许事件实际发射。
3. **生产 decision-grade Profile**：以 additive/versioned 方式建立可接受的 Binance decision-grade Market、Simulation 和 Execution-account registrations，不修改现有 Development artifacts。
4. **接受的 canonical Result**：真实持久化并独立验证的 decision-grade completed publication，冻结完整 Run 身份。
5. **消费证明**：canonical trace 包含所需 Event ID/hash，并为每条 Event 记录确定性 accounting disposition；存在相关持仓时验证 settlement/journal，零持仓时验证明确的 not-applicable/zero-exposure 结果，不能要求制造财务变动。
6. **Runtime source seam**：Runtime 能在不 import Builder、不做 I/O、不信任 generic mapping/boolean/naked hash 的前提下重建 exact evidence。
7. **版本化 correction**：新 source 使用新 qualification/schema version，绑定直接 predecessor report；存在旧 assessment 时才绑定直接 superseded assessment。

## 防止再次发生

未来 provider slice 进入 G12M 前必须增加以下 readiness gate：

- execution Bundle 在进入 availability 检查前已满足生产 Profile 的全部 capabilities；
- `max(required_event.available_time) < run.end_exclusive` 只是最低窗口检查；最终必须用 provider evidence 证明 availability 不晚于因果相关的 strategy/settlement decision time，并由 canonical trace 证明实际发射时间；
- Profile registrations 已具备所请求 grade 的生产 authority；
- 已存在 accepted persisted canonical Result，而不是测试构造对象；
- BundleRef、timeline trace 和 accounting disposition 三者同时绑定；
- development Result 只能得到 canonical non-qualified assessment，不能升级；
- provider finality limitations 与 causal blockers 分开记录。

## 最终判定

本次问题不是数据抓取失败，也不是 canonicalization 或 Runtime 时间模型错误。

准确判定是：

> 我们正确建立了一个诚实的晚观察 source artifact，但过早把“可重建来源证据”解释成“完整 execution Bundle 和可用于因果 decision-grade Run qualification”。当前证据只是不足以证明 2024 历史可用性，并不证明真实 Binance 数据当时不可用；Runtime 和 ADR 的 fail-closed 规则阻止了该未知被错误投影为成功资格。
