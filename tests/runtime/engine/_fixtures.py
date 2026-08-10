from __future__ import annotations

from dataclasses import dataclass, replace

from crypto_quant_backtest import (
    BAR_OPEN_CAPABILITY,
    BAR_OPEN_EVENT_TYPE,
    TARGET_STREAM_CAPABILITY,
    TARGET_STREAM_EVENT_TYPE,
    BarLiquidityEvidence,
    CashFillAccountingPlan,
    DeterministicBarEngine,
    FeeAccountingDispatchPlan,
    FillAccountingDispatchPlan,
    FinancialDispatchPlan,
    DeterministicBpsSlippageModel,
    DeterministicTimeline,
    MarkToMarketCloseoutPolicy,
    NextEligibleBarOpenModel,
    NoEligibleBarAction,
    OrderEventPlan,
    PositionLotBook,
    PrecomputedTargetStream,
    ResolvedBarExecution,
    ResolvedDecisionCycle,
    ExecutionCaseComposer,
    ExecutionCaseIdentityFactory,
    ExecutionCaseIdentityRule,
    ExecutionCaseSemanticSpec,
    ResolvedExecutionCase,
    ResolvedFinancialState,
    ResolvedOrderAdmission,
    ResolvedPreTradePlan,
    SimulationComponentRef,
    SimulationPortType,
    SlippageApplicabilityEnvelope,
    SlippageCalibrationRef,
    SlippageMarketState,
    SnapshotProjectionPlan,
    TargetStreamDecisionSchedule,
    TargetStreamScheduleEntry,
    TimelineEvent,
    TimelineSegment,
    TimelineWindow,
    default_cash_financial_dispatcher_spec,
)
from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    IdentityNamespace,
    ExecutionStyle,
    FeeBasisType,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    Money,
    Order,
    OrderEventType,
    OrderSide,
    PortfolioSnapshot,
    PositionBalanceKey,
    PositionEffect,
    Price,
    PricePurpose,
    QuantizationPolicy,
    Quantity,
    Rate,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    SourceSequence,
    StrategyDecisionPayload,
    StrategyDecisionCandidate,
    StrategySleeveId,
    TimelinePhase,
    TimeInForce,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_market_data import (
    InMemoryMarketBundleReader,
    InputValidationFailure,
    MarketEvent,
)
from crypto_quant_trading import (
    AccountingJournal,
    AccountRiskPolicy,
    AvailabilityProjection,
    CapitalAllocationPolicyRef,
    CashAvailabilityRule,
    CashReservationUse,
    CostBasisMethod,
    CostBasisPolicy,
    CurrencyValuationGraph,
    ExposureCapacityLimit,
    FeeReserveFundingSource,
    FinalFeeApplicability,
    FinalFeeRuleSource,
    FeeReservationEstimator,
    GenericLedger,
    InstrumentSizingInput,
    LedgerBalanceRegistration,
    LedgerSchema,
    MarketRuleEvaluator,
    MarketSettlementRules,
    OrderCapabilityValidator,
    OrderRuleEvaluationInput,
    OrderRuleNotionalEvidence,
    PortfolioAllocator,
    PortfolioRiskAction,
    PortfolioRiskEvaluator,
    PortfolioRiskLimit,
    PortfolioRiskPolicy,
    PortfolioRiskScope,
    PositionAvailabilityRule,
    PositionSizer,
    PositionSizingPolicy,
    PreTradeResourceRequirement,
    ProfileComponentRef,
    ProfilePortType,
    ReportingCurrencyValuation,
    ReservationCommitment,
    RebalanceCoordinator,
    RebalancePolicy,
    ResidualPositionPolicy,
    ResolvedMark,
    ResourceReservationBook,
    SettlementBook,
    StrategyAllocation,
    StrategyOutputValidationContext,
    TargetValidity,
    PortfolioValueKind,
    PortfolioValueRef,
)
from tests.kernel.capabilities._fixtures import capability_set
from tests.kernel.fee_reservations._fixtures import rule_set as fee_reservation_rules
from tests.kernel.fees._fixtures import all_rules, rule_set as final_fee_rules
from tests.kernel.market_rules._fixtures import (
    interval as market_rule_interval,
    reference_notional_evidence,
    timeline as market_rule_timeline,
)
from tests.kernel.translation._fixtures import mapping as translation_mapping


ACCOUNT = "account:primary"
VENUE = VenueId("synthetic")
USD = CurrencyId("USD")
BTC = InstrumentId(VENUE, "cash:btc-usd")
CASH_KEY = CashBalanceKey(ACCOUNT, VENUE, USD)
POSITION_KEY = PositionBalanceKey(ACCOUNT, VENUE, BTC)
MONEY_SCALE = Scale(2)
QUANTITY_SCALE = Scale(3)
TARGET_TIME = UtcInstant(100)
BAR_TIME = UtcInstant(200)
END_TIME = UtcInstant(300)
TARGET_PHASE = TimelinePhase(30, "strategy_decision")
BAR_PHASE = TimelinePhase(60, "bar_open")
ORDER_PHASE = TimelinePhase(80, "order_admission")
ACCOUNTING_PHASE = TimelinePhase(90, "accounting")
SLEEVE = StrategySleeveId("trend.primary")
STRATEGY_ID = "trend-v1"
TARGET_EVENT_ID = "engine-target-100"
WARMUP_TARGET_EVENT_ID = "engine-target-warmup-50"
BAR_EVENT_ID = "engine-bar-open-200"
ORDER_ID = DomainId(DomainIdKind.ORDER, "ord_" + "1" * 64)
FILL_ID = DomainId(DomainIdKind.FILL, "fil_" + "2" * 64)
FILL_JOURNAL_ID = DomainId(DomainIdKind.JOURNAL, "jnl_" + "3" * 64)
FEE_ID = DomainId(DomainIdKind.FEE, "fee_" + "4" * 64)
FEE_JOURNAL_ID = DomainId(DomainIdKind.JOURNAL, "jnl_" + "5" * 64)


@dataclass(frozen=True, slots=True)
class EngineDomainIds:
    deposit_journal_id: DomainId
    order_id: DomainId
    fill_id: DomainId
    fill_journal_id: DomainId
    fee_assessment_id: DomainId
    fee_journal_id: DomainId


@dataclass(frozen=True, slots=True)
class EngineEventIds:
    admission_event_ids: tuple[str, ...]
    fill_event_id: str


LEGACY_DOMAIN_IDS = EngineDomainIds(
    deposit_journal_id=DomainId(DomainIdKind.JOURNAL, "jnl_" + "0" * 64),
    order_id=ORDER_ID,
    fill_id=FILL_ID,
    fill_journal_id=FILL_JOURNAL_ID,
    fee_assessment_id=FEE_ID,
    fee_journal_id=FEE_JOURNAL_ID,
)
# Compatibility identity for component fixtures accepted before WP-07A-R1.
# G07 uses an explicit ID-free ExecutionCaseSemanticSpec instead.
LEGACY_EXECUTION_CASE_SEMANTIC_HASH = (
    "sha256:b445b42147b77bd0b5d1d267a5f178d13f45f32d41cdc636eddc463ef0036690"
)
LEGACY_EVENT_IDS = EngineEventIds(
    admission_event_ids=tuple(
        f"engine-order:{index}:{event_type.value}"
        for index, event_type in enumerate(
            (
                OrderEventType.ORDER_INTENT_CREATED,
                OrderEventType.ORDER_CAPABILITY_APPROVED,
                OrderEventType.ORDER_TRANSLATED,
                OrderEventType.MARKET_RULE_APPROVED,
                OrderEventType.FEE_RESERVATION_ESTIMATED,
                OrderEventType.PRE_TRADE_RISK_APPROVED,
                OrderEventType.ORDER_SUBMITTED,
                OrderEventType.ORDER_ACCEPTED,
            )
        )
    ),
    fill_event_id="engine-order:fill",
)


def sim(
    nanoseconds: int,
    phase: TimelinePhase,
    sequence: int,
) -> SimulationInstant:
    return SimulationInstant(UtcInstant(nanoseconds), phase, SourceSequence(sequence))


def catalog() -> InstrumentCatalog:
    btc = CurrencyId("BTC")
    return InstrumentCatalog(
        currencies=(btc, USD),
        instruments=(
            InstrumentDefinition(BTC, InstrumentType.SPOT, btc, USD, USD),
        ),
        symbol_timelines=(),
    )


def target_payload(*, decision_time: int = 100) -> dict[str, object]:
    return {
        "schema_version": 1,
        "strategy_id": STRATEGY_ID,
        "sleeve_id": SLEEVE.value,
        "decision_time": decision_time,
        "observed_through": decision_time - 1,
        "effective_time": decision_time,
        "expires_at": 250,
        "targets": [
            {
                "instrument_id": {
                    "venue": VENUE.value,
                    "stable_key": BTC.stable_key,
                },
                "value": "0.5",
            }
        ],
        "confidence": "1",
        "reason": "engine fixture scheduled rebalance",
        "evidence": {"model_revision": "sha256:model-engine-v1"},
    }


def target_event() -> MarketEvent:
    return MarketEvent(
        event_id=TARGET_EVENT_ID,
        stream_key="targets",
        event_type=TARGET_STREAM_EVENT_TYPE,
        capability=TARGET_STREAM_CAPABILITY,
        instrument_id=None,
        event_time=TARGET_TIME,
        available_time=TARGET_TIME,
        phase=TARGET_PHASE,
        source_sequence=SourceSequence(1),
        revision_id="rev-1",
        supersedes_revision_id=None,
        source_key="fixture.engine.targets.v1",
        source_hash="sha256:" + "11" * 32,
        payload={"schema_version": 1, "candidate": target_payload()},
    )


def warmup_target_event() -> MarketEvent:
    decision_time = UtcInstant(50)
    return MarketEvent(
        event_id=WARMUP_TARGET_EVENT_ID,
        stream_key="targets",
        event_type=TARGET_STREAM_EVENT_TYPE,
        capability=TARGET_STREAM_CAPABILITY,
        instrument_id=None,
        event_time=decision_time,
        available_time=decision_time,
        phase=TARGET_PHASE,
        source_sequence=SourceSequence(0),
        revision_id="rev-1",
        supersedes_revision_id=None,
        source_key="fixture.engine.targets.v1",
        source_hash="sha256:" + "10" * 32,
        payload={
            "schema_version": 1,
            "candidate": target_payload(decision_time=50),
        },
    )


def bar_event() -> MarketEvent:
    return MarketEvent(
        event_id=BAR_EVENT_ID,
        stream_key="bars.open",
        event_type=BAR_OPEN_EVENT_TYPE,
        capability=BAR_OPEN_CAPABILITY,
        instrument_id=BTC,
        event_time=BAR_TIME,
        available_time=BAR_TIME,
        phase=BAR_PHASE,
        source_sequence=SourceSequence(2),
        revision_id="rev-1",
        supersedes_revision_id=None,
        source_key="fixture.engine.bar-open.v1",
        source_hash="sha256:" + "22" * 32,
        payload={
            "schema_version": 1,
            "bar_kind": "real",
            "open_price": {
                "units": 10_500,
                "scale": 2,
                "quote_currency": "USD",
            },
        },
    )


def reader(*, include_warmup: bool = False) -> InMemoryMarketBundleReader:
    target_events = (
        (warmup_target_event(), target_event())
        if include_warmup
        else (target_event(),)
    )
    return InMemoryMarketBundleReader.build(
        bundle_key="fixture.engine.bundle.v1",
        schema_version=1,
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(400),
        instrument_catalog_hash=canonical_sha256(catalog()),
        capabilities=(TARGET_STREAM_CAPABILITY, BAR_OPEN_CAPABILITY),
        streams={
            "targets": target_events,
            "bars.open": (bar_event(),),
        },
    )


def timeline(*, include_warmup: bool = False) -> DeterministicTimeline:
    opened = DeterministicTimeline.open(
        reader=reader(include_warmup=include_warmup),
        stream_keys=("bars.open", "targets"),
        window=TimelineWindow(UtcInstant(0), UtcInstant(90), END_TIME),
    )
    if not isinstance(opened, DeterministicTimeline):
        raise AssertionError(f"timeline fixture failed: {opened!r}")
    return opened


def deposit_entry(
    journal_entry_id: DomainId = LEGACY_DOMAIN_IDS.deposit_journal_id,
) -> AccountingJournalEntry:
    return AccountingJournalEntry(
        journal_entry_id=journal_entry_id,
        entry_type=AccountingEntryType.CAPITAL_DEPOSITED,
        account_id=ACCOUNT,
        venue_id=VENUE,
        effective_time=UtcInstant(0),
        recorded_at=sim(1, ACCOUNTING_PHASE, 1),
        source_ids=("capital:engine-fixture",),
        balance_changes=(BalanceChange(CASH_KEY, Money(100_000, MONEY_SCALE, "USD")),),
        realized_pnl=(),
        fees=(),
        financing=(),
    )


def ledger_schema() -> LedgerSchema:
    return LedgerSchema(
        (
            LedgerBalanceRegistration(CASH_KEY, MONEY_SCALE),
            LedgerBalanceRegistration(POSITION_KEY, QUANTITY_SCALE),
        )
    )


def initial_journal(
    journal_entry_id: DomainId = LEGACY_DOMAIN_IDS.deposit_journal_id,
) -> AccountingJournal:
    return AccountingJournal.from_entries((deposit_entry(journal_entry_id),))


def empty_settlement_rules() -> MarketSettlementRules:
    return MarketSettlementRules.create(
        policy_key="settlement.engine-fixture.v1",
        policy_version=1,
        account_id=ACCOUNT,
        cash_rules=(
            CashAvailabilityRule(
                key=CASH_KEY,
                pending_receivable_tradable=False,
                pending_receivable_withdrawable=False,
                pending_receivable_margin_eligible=False,
                tradable_reservation_uses=(
                    CashReservationUse.CASH,
                    CashReservationUse.FEE_RESERVE,
                ),
                withdrawable_reservation_uses=(
                    CashReservationUse.CASH,
                    CashReservationUse.FEE_RESERVE,
                ),
                available_margin_reservation_uses=(CashReservationUse.MARGIN,),
            ),
        ),
        position_rules=(
            PositionAvailabilityRule(
                key=POSITION_KEY,
                pending_receivable_sellable=False,
            ),
        ),
    )


def initial_snapshot(
    journal_entry_id: DomainId = LEGACY_DOMAIN_IDS.deposit_journal_id,
) -> PortfolioSnapshot:
    ledger = GenericLedger(ledger_schema()).project(initial_journal(journal_entry_id))
    zero = Money(0, MONEY_SCALE, "USD")
    graph = CurrencyValuationGraph(
        valuation_at=TARGET_TIME,
        price_purpose=PricePurpose.VALUATION,
        edges=(),
    )
    return PortfolioSnapshot(
        account_id=ACCOUNT,
        timestamp=TARGET_TIME,
        reporting_currency=USD,
        cash=ledger.cash_balances,
        positions=ledger.position_balances,
        realized_pnl=zero,
        unrealized_pnl=zero,
        fees=zero,
        financing=zero,
        equity=Money(100_000, MONEY_SCALE, "USD"),
        valuation_marks=(),
        journal_state_hash=ledger.state_hash,
        valuation_mark_set_hash=canonical_sha256(()),
        valuation_staleness_report_hash=canonical_sha256(()),
        currency_valuation_graph_hash=graph.graph_hash,
    )


def target_schedule() -> TargetStreamDecisionSchedule:
    from crypto_quant_trading import DecisionBatchExpectation

    expectation = DecisionBatchExpectation(STRATEGY_ID, SLEEVE)
    context = StrategyOutputValidationContext(
        expected_strategy_id=STRATEGY_ID,
        expected_sleeve_id=SLEEVE,
        decision_time=TARGET_TIME,
        instrument_catalog=catalog(),
        universe=(BTC,),
    )
    return TargetStreamDecisionSchedule(
        decision_time=TARGET_TIME,
        segment=TimelineSegment.ACTIVE_TRADING,
        entries=(
            TargetStreamScheduleEntry(
                event_id=TARGET_EVENT_ID,
                expectation=expectation,
                validation_context=context,
            ),
        ),
    )


def warmup_schedule() -> TargetStreamDecisionSchedule:
    from crypto_quant_trading import DecisionBatchExpectation

    decision_time = UtcInstant(50)
    expectation = DecisionBatchExpectation(STRATEGY_ID, SLEEVE)
    return TargetStreamDecisionSchedule(
        decision_time=decision_time,
        segment=TimelineSegment.WARMUP,
        entries=(
            TargetStreamScheduleEntry(
                event_id=WARMUP_TARGET_EVENT_ID,
                expectation=expectation,
                validation_context=StrategyOutputValidationContext(
                    expected_strategy_id=STRATEGY_ID,
                    expected_sleeve_id=SLEEVE,
                    decision_time=decision_time,
                    instrument_catalog=catalog(),
                    universe=(BTC,),
                ),
            ),
        ),
    )


def allocation_policy_ref() -> CapitalAllocationPolicyRef:
    return CapitalAllocationPolicyRef(
        policy_key="capital.engine-fixture.v1",
        policy_version=1,
        config_hash="sha256:" + "31" * 32,
    )


def allocations(
    journal_entry_id: DomainId = LEGACY_DOMAIN_IDS.deposit_journal_id,
) -> tuple[StrategyAllocation, ...]:
    snapshot = initial_snapshot(journal_entry_id)
    return (
        StrategyAllocation(
            strategy_id=STRATEGY_ID,
            sleeve_id=SLEEVE,
            valuation_time=TARGET_TIME,
            valuation_currency=USD,
            allocation_nav=Money(100_000, MONEY_SCALE, "USD"),
            policy_ref=allocation_policy_ref(),
            source_portfolio_snapshot_hash=canonical_sha256(snapshot),
        ),
    )


def risk_policy() -> PortfolioRiskPolicy:
    return PortfolioRiskPolicy.create(
        policy_key="risk.engine-fixture.v1",
        policy_version=1,
        valuation_currency=USD,
        notional_scale=MONEY_SCALE,
        limits=(
            PortfolioRiskLimit(
                limit_id="target.btc.absolute.v1",
                scope=PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL,
                maximum=Money(100_000, MONEY_SCALE, "USD"),
                breach_action=PortfolioRiskAction.REJECT,
                instrument_id=BTC,
            ),
            PortfolioRiskLimit(
                limit_id="aggregate.gross.v1",
                scope=PortfolioRiskScope.GROSS_EXPOSURE,
                maximum=Money(100_000, MONEY_SCALE, "USD"),
                breach_action=PortfolioRiskAction.REJECT,
                instrument_id=None,
            ),
            PortfolioRiskLimit(
                limit_id="aggregate.net.v1",
                scope=PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE,
                maximum=Money(100_000, MONEY_SCALE, "USD"),
                breach_action=PortfolioRiskAction.REJECT,
                instrument_id=None,
            ),
        ),
    )


def valuation_mark(*, price_units: int = 10_000, resolved_at: UtcInstant = TARGET_TIME) -> ResolvedMark:
    return ResolvedMark(
        instrument_id=BTC,
        quote_currency_id=USD,
        price_purpose=PricePurpose.VALUATION,
        price=Price(price_units, MONEY_SCALE, str(BTC), "USD"),
        observed_at=UtcInstant(resolved_at.epoch_nanoseconds - 10),
        available_at=UtcInstant(resolved_at.epoch_nanoseconds - 5),
        resolved_at=resolved_at,
        age_nanoseconds=10,
        stream_id="bars.valuation",
        source_event_id=f"valuation:{resolved_at.epoch_nanoseconds}",
        revision_id="rev-1",
        stale_policy_key="valuation.engine-fixture.v1",
        stale_policy_version=1,
        stale_policy_hash="sha256:" + "32" * 32,
    )


def quantity_lattice():
    from crypto_quant_trading import QuantityLattice

    return QuantityLattice.create(
        instrument_id=BTC,
        lattice_key="lattice.engine-fixture.v1",
        lattice_version=1,
        atomic_scale=QUANTITY_SCALE,
        step_units=1,
        buy_lot_units=1,
        sell_lot_units=1,
        min_quantity_units=1,
        min_notional=Money(100, MONEY_SCALE, "USD"),
        odd_lot_close_permitted=False,
    )


def sizing_policy() -> PositionSizingPolicy:
    return PositionSizingPolicy.create(
        policy_key="sizing.engine-fixture.v1",
        policy_version=1,
        price_purpose=PricePurpose.VALUATION,
        rounding=RoundingPolicy.TOWARD_ZERO,
        residual_policy=ResidualPositionPolicy.FAIL,
    )


def sizing_inputs() -> tuple[InstrumentSizingInput, ...]:
    return (
        InstrumentSizingInput(
            instrument_id=BTC,
            mark=valuation_mark(),
            current_quantity=Quantity(0, QUANTITY_SCALE, str(BTC)),
            lattice=quantity_lattice(),
        ),
    )


def rebalance_policy() -> RebalancePolicy:
    return RebalancePolicy.create(
        policy_key="rebalance.engine-fixture.v1",
        policy_version=1,
        execution_style=ExecutionStyle.MARKET,
        time_in_force=TimeInForce.DAY,
        urgency="normal",
        plan_valid_for_nanoseconds=100,
    )


def _empty_resources(
    journal_entry_id: DomainId = LEGACY_DOMAIN_IDS.deposit_journal_id,
):
    state = ResourceReservationBook(ACCOUNT).project((), ())
    settlement = SettlementBook(ACCOUNT).project()
    availability = AvailabilityProjection().project(
        GenericLedger(ledger_schema()).project(initial_journal(journal_entry_id)),
        settlement,
        state,
        empty_settlement_rules(),
    )
    return state, availability


def expected_order(
    order_id: DomainId = LEGACY_DOMAIN_IDS.order_id,
    deposit_journal_id: DomainId = LEGACY_DOMAIN_IDS.deposit_journal_id,
) -> tuple[Order, TargetValidity]:
    from crypto_quant_backtest import PrecomputedTargetStreamAdapter

    stream = PrecomputedTargetStream("targets", (target_event(),))
    injected = PrecomputedTargetStreamAdapter().inject(
        stream=stream,
        timeline_events=(TimelineEvent(TimelineSegment.ACTIVE_TRADING, target_event()),),
        schedule=target_schedule(),
    )
    assert injected.injection is not None
    allocated = PortfolioAllocator().allocate(
        sleeve_state=injected.injection.state,
        portfolio_snapshot=initial_snapshot(deposit_journal_id),
        allocations=allocations(deposit_journal_id),
        target_notional_scale=MONEY_SCALE,
    )
    assert allocated.allocation is not None
    approved = PortfolioRiskEvaluator().evaluate(
        allocation=allocated.allocation,
        policy=risk_policy(),
    )
    assert approved.approved_target is not None
    sized = PositionSizer().materialize(
        approved_target=approved.approved_target,
        source_decision_batch_id=injected.injection.batch.decision_batch_id,
        policy=sizing_policy(),
        inputs=sizing_inputs(),
    )
    assert sized.normalized_target is not None
    validity = TargetValidity(
        normalized_target_id=sized.normalized_target.normalized_target_id,
        normalized_target_hash=sized.normalized_target.normalized_target_hash,
        valid_from=TARGET_TIME,
        valid_until=UtcInstant(250),
    )
    reservations, availability = _empty_resources(deposit_journal_id)
    planned = RebalanceCoordinator().coordinate(
        target=sized.normalized_target,
        target_validity=validity,
        portfolio_snapshot=initial_snapshot(deposit_journal_id),
        working_orders=(),
        reservations=reservations,
        availability=availability,
        policy=rebalance_policy(),
        as_of=UtcInstant(105),
    )
    assert planned.decision is not None
    assert len(planned.decision.plan.planned_orders) == 1
    return (
        Order(
            order_id=order_id,
            account_id=ACCOUNT,
            intent=planned.decision.plan.planned_orders[0].intent,
            created_at=sim(110, ORDER_PHASE, 1),
        ),
        validity,
    )


def order_rule_timeline():
    return market_rule_timeline(
        intervals=(market_rule_interval(start=0, stop=300),)
    )


def account_risk_policy() -> AccountRiskPolicy:
    return AccountRiskPolicy.create(
        policy_key="account-risk.engine-fixture.v1",
        policy_version=1,
        account_id=ACCOUNT,
        venue_id=VENUE,
        allowed_sides=(OrderSide.BUY, OrderSide.SELL),
        allowed_position_effects=(
            PositionEffect.AUTO,
            PositionEffect.OPEN,
            PositionEffect.CLOSE,
        ),
        allowed_reduce_only_values=(False, True),
        fee_reserve_funding_source=FeeReserveFundingSource.TRADABLE_CASH,
        order_capacity_limit=10,
        exposure_capacity_limits=(
            ExposureCapacityLimit(Money(200_000, MONEY_SCALE, "USD")),
        ),
    )


def resource_commitment(
    order: Order,
    *,
    price_units: int,
    evaluated_at: int,
) -> ReservationCommitment:
    capability = OrderCapabilityValidator().validate(order.intent, capability_set())
    assert capability.approval is not None
    from crypto_quant_trading import OrderTranslator

    translated = OrderTranslator().translate(
        order,
        capability.approval,
        translation_mapping(),
        UtcInstant(111),
    )
    assert translated.executable_spec is not None
    market = MarketRuleEvaluator().evaluate(
        OrderRuleEvaluationInput(
            executable_order_spec=translated.executable_spec,
            evaluated_at=UtcInstant(evaluated_at),
            notional_evidence=reference_notional_evidence(
                price_units=price_units,
                available_at=evaluated_at,
            ),
        ),
        order_rule_timeline(),
    )
    assert market.approval is not None
    fees = FeeReservationEstimator().estimate(
        market.approval,
        fee_reservation_rules(),
        UtcInstant(evaluated_at + 1),
    )
    assert fees.proposal is not None
    notional = market.approval.calculated_notional
    return ReservationCommitment(
        cash=(notional,),
        fee_reserve=fees.proposal.commitment.fee_reserve,
        order_capacity_units=1,
        exposure_capacity=(notional,),
    )


def pretrade_plan(
    order: Order,
    *,
    price_units: int,
    market_time: int,
    same_instant: bool = False,
) -> ResolvedPreTradePlan:
    fee_time = market_time if same_instant else market_time + 1
    risk_time = market_time if same_instant else market_time + 2
    return ResolvedPreTradePlan(
        order_rule_timeline=order_rule_timeline(),
        notional_evidence=reference_notional_evidence(
            price_units=price_units,
            available_at=market_time,
        ),
        market_rule_evaluated_at=UtcInstant(market_time),
        fee_reservation_rule_set=fee_reservation_rules(),
        fee_estimated_at=UtcInstant(fee_time),
        resource_commitment=resource_commitment(
            order,
            price_units=price_units,
            evaluated_at=market_time,
        ),
        requirement_source_key="resource.engine-fixture.v1",
        requirement_source_version=1,
        requirement_source_hash="sha256:" + "33" * 32,
        account_risk_policy=account_risk_policy(),
        pretrade_evaluated_at=UtcInstant(risk_time),
    )


def admission(
    *,
    reject_capability: bool = False,
    domain_ids: EngineDomainIds = LEGACY_DOMAIN_IDS,
    event_ids: EngineEventIds = LEGACY_EVENT_IDS,
) -> ResolvedOrderAdmission:
    order, _ = expected_order(
        domain_ids.order_id,
        domain_ids.deposit_journal_id,
    )
    plans = tuple(
        OrderEventPlan(
            event_type=event_type,
            event_id=event_ids.admission_event_ids[index],
            occurred_at=sim(110 + index, ORDER_PHASE, index + 1),
            external_evidence_id=(
                f"external:{event_type.value}"
                if event_type
                in {OrderEventType.ORDER_SUBMITTED, OrderEventType.ORDER_ACCEPTED}
                else None
            ),
        )
        for index, event_type in enumerate(
            (
                OrderEventType.ORDER_INTENT_CREATED,
                OrderEventType.ORDER_CAPABILITY_APPROVED,
                OrderEventType.ORDER_TRANSLATED,
                OrderEventType.MARKET_RULE_APPROVED,
                OrderEventType.FEE_RESERVATION_ESTIMATED,
                OrderEventType.PRE_TRADE_RISK_APPROVED,
                OrderEventType.ORDER_SUBMITTED,
                OrderEventType.ORDER_ACCEPTED,
            )
        )
    )
    return ResolvedOrderAdmission(
        order=order,
        capability_set=(capability_set(styles=()) if reject_capability else capability_set()),
        translation_mapping=translation_mapping(),
        translation_time=UtcInstant(112),
        pretrade_plan=pretrade_plan(order, price_units=10_000, market_time=113),
        event_plan=plans,
    )


def decision_cycle(
    *,
    reject_capability: bool = False,
    domain_ids: EngineDomainIds = LEGACY_DOMAIN_IDS,
    event_ids: EngineEventIds = LEGACY_EVENT_IDS,
) -> ResolvedDecisionCycle:
    _, validity = expected_order(
        domain_ids.order_id,
        domain_ids.deposit_journal_id,
    )
    return ResolvedDecisionCycle(
        schedule=target_schedule(),
        allocations=allocations(domain_ids.deposit_journal_id),
        target_notional_scale=MONEY_SCALE,
        risk_policy=risk_policy(),
        sizing_policy=sizing_policy(),
        sizing_inputs=sizing_inputs(),
        target_validity=validity,
        rebalance_policy=rebalance_policy(),
        planning_at=UtcInstant(105),
        admissions=(
            admission(
                reject_capability=reject_capability,
                domain_ids=domain_ids,
                event_ids=event_ids,
            ),
        ),
    )


def warmup_cycle(
    domain_ids: EngineDomainIds = LEGACY_DOMAIN_IDS,
    event_ids: EngineEventIds = LEGACY_EVENT_IDS,
) -> ResolvedDecisionCycle:
    active = decision_cycle(domain_ids=domain_ids, event_ids=event_ids)
    return replace(
        active,
        schedule=warmup_schedule(),
        allocations=(),
        planning_at=UtcInstant(50),
        admissions=(),
    )


def slippage_model() -> DeterministicBpsSlippageModel:
    return DeterministicBpsSlippageModel(
        component_ref=SimulationComponentRef(
            port_type=SimulationPortType.SLIPPAGE_MODEL,
            component_key="deterministic_bps.v1",
            component_version=1,
            component_digest="sha256:" + "41" * 32,
        ),
        calibration_ref=SlippageCalibrationRef(
            calibration_key="calibration.engine-fixture.v1",
            calibration_version=1,
            calibration_digest="sha256:" + "42" * 32,
        ),
        applicability_envelope=SlippageApplicabilityEnvelope.create(
            envelope_key="slippage.engine-fixture.v1",
            envelope_version=1,
            instrument_id=BTC,
            valid_from=UtcInstant(190),
            valid_to_exclusive=UtcInstant(210),
            maximum_quantity=Quantity(5_000, QUANTITY_SCALE, str(BTC)),
            allowed_market_state_keys=("normal",),
        ),
        basis_points_units=10,
        basis_points_scale=Scale(0),
        rounding=RoundingPolicy.HALF_UP,
        limitations=(),
    )


def final_fee_rule_set():
    rules = tuple(
        replace(rule, applicability=FinalFeeApplicability.ALWAYS)
        if (
            rule.basis_type is FeeBasisType.FILL
            and rule.source is FinalFeeRuleSource.MARKET_FEE
        )
        else rule
        for rule in all_rules()
    )
    return final_fee_rules(rules=rules, minimums=())


@dataclass(frozen=True, slots=True)
class CashAccountingSemanticPayload:
    cash_key: CashBalanceKey
    position_key: PositionBalanceKey
    cost_basis_policy: CostBasisPolicy
    notional_quantization: QuantizationPolicy

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cash_accounting_semantic_payload",
            "cash_key": self.cash_key,
            "position_key": self.position_key,
            "cost_basis_policy": self.cost_basis_policy,
            "notional_quantization": self.notional_quantization,
        }


def cash_accounting_plan(
    domain_ids: EngineDomainIds = LEGACY_DOMAIN_IDS,
) -> FillAccountingDispatchPlan:
    payload = CashFillAccountingPlan(
        cash_key=CASH_KEY,
        position_key=POSITION_KEY,
        cost_basis_policy=CostBasisPolicy(
            policy_key="cost-basis.engine-fixture.v1",
            policy_version=1,
            method=CostBasisMethod.FIFO,
            fee_allocation_rounding=RoundingPolicy.HALF_EVEN,
        ),
        notional_quantization=QuantizationPolicy(
            version="notional.engine-fixture.v1",
            target_scale=MONEY_SCALE,
            rounding=RoundingPolicy.HALF_EVEN,
        ),
        fill_journal_entry_id=domain_ids.fill_journal_id,
        fill_recorded_at=sim(210, ACCOUNTING_PHASE, 1),
        final_fee_rule_set=final_fee_rule_set(),
        fee_assessment_id=domain_ids.fee_assessment_id,
        fee_assessment_time=UtcInstant(211),
        fee_journal_entry_id=domain_ids.fee_journal_id,
        fee_recorded_at=sim(212, ACCOUNTING_PHASE, 3),
    )
    spec = default_cash_financial_dispatcher_spec()
    return FillAccountingDispatchPlan(
        source_event_id=BAR_EVENT_ID,
        expected_fill_id=domain_ids.fill_id,
        position_accounting_component=spec.position_accounting_component,
        position_payload=payload,
        semantic_payload=CashAccountingSemanticPayload(
            payload.cash_key,
            payload.position_key,
            payload.cost_basis_policy,
            payload.notional_quantization,
        ),
        fill_journal_entry_id=domain_ids.fill_journal_id,
        fill_recorded_at=payload.fill_recorded_at,
        fee_plan=FeeAccountingDispatchPlan(
            payload.cash_key,
            payload.final_fee_rule_set,
            payload.fee_assessment_id,
            payload.fee_assessment_time,
            payload.fee_journal_entry_id,
            payload.fee_recorded_at,
        ),
        expected_artifact_roles=("position_accounting",),
    )


def bar_execution(
    domain_ids: EngineDomainIds = LEGACY_DOMAIN_IDS,
    event_ids: EngineEventIds = LEGACY_EVENT_IDS,
) -> ResolvedBarExecution:
    order, _ = expected_order(domain_ids.order_id)
    event = bar_event()
    return ResolvedBarExecution(
        event_id=BAR_EVENT_ID,
        order_id=domain_ids.order_id,
        pretrade_plan=pretrade_plan(
            order, price_units=10_500, market_time=200, same_instant=True
        ),
        liquidity_evidence=BarLiquidityEvidence.create(
            evidence_key="liquidity.engine-fixture.v1",
            evidence_version=1,
            market_event=event,
            evaluated_at=BAR_TIME,
            approved=True,
            reason_code=None,
            source_hash="sha256:" + "43" * 32,
        ),
        market_state=SlippageMarketState(
            state_key="normal",
            observed_at=BAR_TIME,
            available_at=BAR_TIME,
            source_event_id=BAR_EVENT_ID,
            revision_id="rev-1",
            evidence_hash=event.event_hash,
        ),
        slippage_model=slippage_model(),
        fill_id=domain_ids.fill_id,
        fill_event_id=event_ids.fill_event_id,
        fill_event_at=sim(200, TimelinePhase(70, "fill"), 1),
        accounting_plan=cash_accounting_plan(domain_ids),
    )


def final_valuation_mark() -> ResolvedMark:
    return valuation_mark(price_units=11_000, resolved_at=END_TIME)


def snapshot_plan() -> SnapshotProjectionPlan:
    mark = final_valuation_mark()
    graph = CurrencyValuationGraph(
        valuation_at=END_TIME,
        price_purpose=PricePurpose.VALUATION,
        edges=(),
    )
    resolution = graph.resolve(USD, USD).resolution
    assert resolution is not None
    quantization = QuantizationPolicy(
        version="position-value.engine-fixture.v1",
        target_scale=MONEY_SCALE,
        rounding=RoundingPolicy.HALF_EVEN,
    )
    return SnapshotProjectionPlan(
        resolved_marks=(mark,),
        valuations=(
            ReportingCurrencyValuation(
                PortfolioValueRef(PortfolioValueKind.CASH, CASH_KEY),
                Money(47_392, MONEY_SCALE, "USD"),
                Money(47_392, MONEY_SCALE, "USD"),
                resolution,
                graph.graph_hash,
            ),
            ReportingCurrencyValuation(
                PortfolioValueRef(PortfolioValueKind.POSITION_MARKET_VALUE, POSITION_KEY),
                Money(55_000, MONEY_SCALE, "USD"),
                Money(55_000, MONEY_SCALE, "USD"),
                resolution,
                graph.graph_hash,
                quantization,
            ),
            ReportingCurrencyValuation(
                PortfolioValueRef(PortfolioValueKind.UNREALIZED_PNL, POSITION_KEY),
                Money(2_445, MONEY_SCALE, "USD"),
                Money(2_445, MONEY_SCALE, "USD"),
                resolution,
                graph.graph_hash,
            ),
            ReportingCurrencyValuation(
                PortfolioValueRef(PortfolioValueKind.FEES, CASH_KEY),
                Money(53, MONEY_SCALE, "USD"),
                Money(53, MONEY_SCALE, "USD"),
                resolution,
                graph.graph_hash,
            ),
        ),
        reporting_currency=USD,
        reporting_scale=MONEY_SCALE,
        timestamp=END_TIME,
        currency_valuation_graph_hash=graph.graph_hash,
    )


def execution_model() -> NextEligibleBarOpenModel:
    return NextEligibleBarOpenModel.create(
        actions=tuple(
            (tif, action)
            for tif, action in (
                (TimeInForce.DAY, NoEligibleBarAction.EXPIRE),
                (TimeInForce.GTC, NoEligibleBarAction.KEEP_ACTIVE),
                (TimeInForce.IOC, NoEligibleBarAction.EXPIRE),
                (TimeInForce.FOK, NoEligibleBarAction.EXPIRE),
                (TimeInForce.GTX, NoEligibleBarAction.KEEP_ACTIVE),
            )
        )
    )


def financial_state(
    domain_ids: EngineDomainIds = LEGACY_DOMAIN_IDS,
) -> ResolvedFinancialState:
    return ResolvedFinancialState(
        journal=initial_journal(domain_ids.deposit_journal_id),
        ledger_schema=ledger_schema(),
        initial_snapshot=initial_snapshot(domain_ids.deposit_journal_id),
        lot_books=(PositionLotBook(POSITION_KEY),),
        order_streams=(),
        order_admissions=(),
        reservation_schedules=(),
        settlement_book=SettlementBook(ACCOUNT),
        settlement_rules=empty_settlement_rules(),
    )


def financial_dispatch_plan() -> FinancialDispatchPlan:
    return FinancialDispatchPlan(
        default_cash_financial_dispatcher_spec(),
        (),
        snapshot_plan(),
        ("final_snapshot", "position_accounting"),
    )


def execution_case(
    *,
    batch_size: int = 1,
    reject_capability: bool = False,
    include_warmup: bool = False,
    semantic_spec_hash: str = LEGACY_EXECUTION_CASE_SEMANTIC_HASH,
    domain_ids: EngineDomainIds = LEGACY_DOMAIN_IDS,
    event_ids: EngineEventIds = LEGACY_EVENT_IDS,
) -> ResolvedExecutionCase:
    target_events = (
        (warmup_target_event(), target_event())
        if include_warmup
        else (target_event(),)
    )
    cycles = (
        (
            warmup_cycle(domain_ids, event_ids),
            decision_cycle(
                reject_capability=reject_capability,
                domain_ids=domain_ids,
                event_ids=event_ids,
            ),
        )
        if include_warmup
        else (
            decision_cycle(
                reject_capability=reject_capability,
                domain_ids=domain_ids,
                event_ids=event_ids,
            ),
        )
    )
    return ResolvedExecutionCase(
        case_key="engine.cash.fixture.v1",
        case_version=1,
        semantic_spec_hash=semantic_spec_hash,
        timeline=timeline(include_warmup=include_warmup),
        timeline_batch_size=batch_size,
        target_stream=PrecomputedTargetStream("targets", target_events),
        decision_cycles=cycles,
        bar_executions=(bar_execution(domain_ids, event_ids),),
        financial_state=financial_state(domain_ids),
        financial_dispatch_plan=financial_dispatch_plan(),
        execution_model=execution_model(),
        snapshot_plan=snapshot_plan(),
        closeout_policy=MarkToMarketCloseoutPolicy(),
    )


@dataclass(frozen=True, slots=True)
class SyntheticExecutionCaseBuilder:
    reject_capability: bool = False
    include_warmup: bool = False
    batch_size: int = 1

    def identity_plan(self) -> tuple[ExecutionCaseIdentityRule, ...]:
        cycle_index = 1 if self.include_warmup else 0
        return (
            ExecutionCaseIdentityRule(
                "journal.initial.0", "engine.cash.deposit", 0, DomainIdKind.JOURNAL
            ),
            ExecutionCaseIdentityRule(
                f"order.{cycle_index}.0", "engine.cash.order", 0, DomainIdKind.ORDER
            ),
            ExecutionCaseIdentityRule(
                "fill.0", "engine.cash.fill", 0, DomainIdKind.FILL
            ),
            ExecutionCaseIdentityRule(
                "journal.fill.0",
                "engine.cash.fill-journal",
                0,
                DomainIdKind.JOURNAL,
            ),
            ExecutionCaseIdentityRule(
                "fee.0", "engine.cash.fee", 0, DomainIdKind.FEE
            ),
            ExecutionCaseIdentityRule(
                "journal.fee.0",
                "engine.cash.fee-journal",
                0,
                DomainIdKind.JOURNAL,
            ),
            *(
                ExecutionCaseIdentityRule(
                    f"order-event.{cycle_index}.0.{index}",
                    f"engine.cash.order-event.{event_type.value}",
                    index,
                )
                for index, event_type in enumerate(
                    _REQUIRED_ADMISSION_EVENTS_FOR_FIXTURE
                )
            ),
            ExecutionCaseIdentityRule(
                "order-event.fill.0", "engine.cash.order-event.fill", 0
            ),
        )

    def semantic_spec(self) -> ExecutionCaseSemanticSpec:
        template = execution_case(
            batch_size=self.batch_size,
            reject_capability=self.reject_capability,
            include_warmup=self.include_warmup,
        )
        return ExecutionCaseComposer.semantic_spec_from_case(
            template,
            spec_key="synthetic.cash.execution-case.v1",
            spec_version=1,
            identity_namespace=IdentityNamespace("backtest", "1"),
            identity_plan=self.identity_plan(),
        )

    def build(
        self,
        identities: ExecutionCaseIdentityFactory,
        semantic_spec_hash: str,
    ) -> ResolvedExecutionCase:
        domain_ids = EngineDomainIds(
            deposit_journal_id=identities.domain_id("journal.initial.0"),
            order_id=identities.domain_id(
                f"order.{1 if self.include_warmup else 0}.0"
            ),
            fill_id=identities.domain_id("fill.0"),
            fill_journal_id=identities.domain_id("journal.fill.0"),
            fee_assessment_id=identities.domain_id("fee.0"),
            fee_journal_id=identities.domain_id("journal.fee.0"),
        )
        admission_event_ids = tuple(
            identities.event_id(
                f"order-event.{1 if self.include_warmup else 0}.0.{index}"
            )
            for index, event_type in enumerate(_REQUIRED_ADMISSION_EVENTS_FOR_FIXTURE)
        )
        event_ids = EngineEventIds(
            admission_event_ids=admission_event_ids,
            fill_event_id=identities.event_id("order-event.fill.0"),
        )
        return execution_case(
            batch_size=self.batch_size,
            reject_capability=self.reject_capability,
            include_warmup=self.include_warmup,
            semantic_spec_hash=semantic_spec_hash,
            domain_ids=domain_ids,
            event_ids=event_ids,
        )


_REQUIRED_ADMISSION_EVENTS_FOR_FIXTURE = (
    OrderEventType.ORDER_INTENT_CREATED,
    OrderEventType.ORDER_CAPABILITY_APPROVED,
    OrderEventType.ORDER_TRANSLATED,
    OrderEventType.MARKET_RULE_APPROVED,
    OrderEventType.FEE_RESERVATION_ESTIMATED,
    OrderEventType.PRE_TRADE_RISK_APPROVED,
    OrderEventType.ORDER_SUBMITTED,
    OrderEventType.ORDER_ACCEPTED,
)


def input_validation_failure() -> InputValidationFailure:
    failure = reader().validate_requirements(required_streams=("missing",))
    if not isinstance(failure, InputValidationFailure):
        raise AssertionError("missing stream fixture did not fail")
    return failure


def run_result(*, batch_size: int = 1):
    outcome = DeterministicBarEngine().run(execution_case(batch_size=batch_size))
    if outcome.result is None:
        raise AssertionError(f"engine fixture failed: {outcome!r}")
    return outcome.result
