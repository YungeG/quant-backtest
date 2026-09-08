from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from crypto_quant_domain import (
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    FeeBasisType,
    Fill,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    Money,
    Order,
    OrderEvent,
    OrderEventType,
    OrderSide,
    PositionEffect,
    Price,
    PricePurpose,
    Quantity,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
    SessionId,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountFeeScheduleRef,
    ExecutableOrderSpec,
    FeeReservationApplicability,
    FeeReservationBasis,
    FeeReservationChargeRule,
    FeeReservationMinimum,
    FeeReservationRuleSet,
    FeeReservationRuleSource,
    FinalFeeApplicability,
    FinalFeeCalculationBasis,
    FinalFeeChargeRule,
    FinalFeeMinimum,
    FinalFeeRuleSet,
    FinalFeeRuleSource,
    MarketRuleApproval,
    MarketRuleEvaluator,
    MarketSessionState,
    NotionalPriceBasis,
    OrderEventRecord,
    OrderEventStream,
    OrderReservationSchedule,
    OrderReservationUpdate,
    OrderRuleEvaluationInput,
    OrderRuleInterval,
    OrderRuleNotionalEvidence,
    OrderRuleSnapshot,
    OrderRuleTimeline,
    OrderTranslator,
    ProfileComponentRef,
    ProfilePortType,
    QuantityLattice,
    ReservationCommitment,
    ResourceReservationBook,
    ResourceReservationProposal,
    ResourceReservationState,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashFeeRuleQuery,
    CnAShareCashMarketFeePolicy,
    CnAShareCashStampDutyTaxPolicy,
    CnAShareFeeReservationBuffer,
    CnAShareFeeRuleSourceRef,
    CnAShareFeeTradeMechanism,
    CnAShareMarketFeeBand,
    CnAShareMarketFeeRuleBook,
    CnAShareStampDutyBand,
    CnAShareStampDutyRuleBook,
)
from tests.kernel.translation._fixtures import approval, mapping, order


CNY = CurrencyId("CNY")
FEE_SCALE = Scale(2)
QUANTITY_SCALE = Scale(0)
SHANGHAI = timezone(timedelta(hours=8))
ACCOUNT = "account:primary"
ORDER_PHASE = TimelinePhase(60, "orders")
FEE_PHASE = TimelinePhase(90, "fees")
QUANTIZATION = QuantizationPolicy(
    "cn-a-share-fee.cny-cent.half-up.v1", FEE_SCALE, RoundingPolicy.HALF_UP
)


def local_instant(day: int, hour: int = 0, *, nanoseconds: int = 0) -> UtcInstant:
    base = UtcInstant.from_datetime(
        datetime(2023, 8, day, hour, tzinfo=SHANGHAI)
    )
    return UtcInstant(base.epoch_nanoseconds + nanoseconds)


def domain_id(kind: DomainIdKind, digit: str) -> DomainId:
    return DomainId(kind, f"{kind.prefix}_{digit * 64}")


def instrument(venue: str = "xshg") -> InstrumentDefinition:
    venue_id = VenueId(venue)
    return InstrumentDefinition(
        InstrumentId(venue_id, "600000" if venue == "xshg" else "000001"),
        InstrumentType.EQUITY,
        None,
        CNY,
        CNY,
    )


def _source(key: str, digest: str) -> CnAShareFeeRuleSourceRef:
    return CnAShareFeeRuleSourceRef(key, f"sha256:{digest}")


SSE_HANDLING = _source(
    "sse.transaction-handling.2023-136",
    "09fc5f031acb829b3810e23196fa77201d9181060209cd6fe6a2fff4d76070bc",
)
SZSE_HANDLING = _source(
    "szse.transaction-handling.2023-08-18",
    "6645a32b6ab297741f22e6b8e959342bb4c9312757d0f1d99de37a0a410d12ba",
)
REGULATORY = _source(
    "ndrc.securities-business-regulatory-fee.2018-917",
    "4c8c8426c7cc797a99a86f8d8bea21fef8f1a944d1ef14857286c9784085b3c8",
)
SSE_BILATERAL = _source(
    "chinaclear.sh-market-fee-table.2025-12-31",
    "84a99e563cb8e84e264c88e3bea2df5f4ac50b1e95330417ec30e2b2566d862f",
)
SZSE_BILATERAL = _source(
    "szse.market-fee-collection.2026-08-08-snapshot",
    "fbd7df3dfa07778b1318564563d22992f19d06bde415144fef248f27674f03c7",
)
TRANSFER = _source(
    "chinaclear.stock-transfer-fee.2022-04-28",
    "68763b8fe13f7fb90f378b077033b692aafc4eca851c78c18a306b001d591a60",
)
STAMP_BASE = _source(
    "sta.12366.stamp-duty.2008-2-quotation",
    "69179c93a4861d2fad5d96d2d8e85b3346e0b70ac8213129959bcb4fa5d3f6ba",
)
STAMP_HALF = _source(
    "mof-sta.stamp-duty.2023-39",
    "970711682948365c3f79afc476df67d5f2d29f57ed239f695f1308f45acffdaf",
)


def _market_bands(
    venue: str,
    handling: CnAShareFeeRuleSourceRef,
    bilateral: CnAShareFeeRuleSourceRef,
) -> tuple[CnAShareMarketFeeBand, CnAShareMarketFeeBand]:
    def band(start: int, stop: int, rate_units: int) -> CnAShareMarketFeeBand:
        return CnAShareMarketFeeBand(
            venue_id=VenueId(venue),
            effective_from=local_instant(start),
            effective_to_exclusive=local_instant(stop),
            handling_rate=Rate(rate_units, Scale(7), "fee_fraction"),
            handling_source_refs=(handling,),
            regulatory_rate=Rate(2, Scale(5), "fee_fraction"),
            regulatory_source_refs=(REGULATORY, bilateral),
            transfer_rate=Rate(1, Scale(5), "fee_fraction"),
            transfer_source_refs=(TRANSFER,),
        )

    return band(25, 28, 487), band(28, 30, 341)


def market_rule_book() -> CnAShareMarketFeeRuleBook:
    return CnAShareMarketFeeRuleBook(
        "equity.cn_a_share.cash.market-fees.2023-08.v1",
        1,
        (
            *_market_bands("xshg", SSE_HANDLING, SSE_BILATERAL),
            *_market_bands("xshe", SZSE_HANDLING, SZSE_BILATERAL),
        ),
    )


def tax_rule_book() -> CnAShareStampDutyRuleBook:
    return CnAShareStampDutyRuleBook(
        "equity.cn_a_share.cash.stamp-duty.2023-08.v1",
        1,
        tuple(
            band
            for venue in (VenueId("xshg"), VenueId("xshe"))
            for band in (
                CnAShareStampDutyBand(
                    venue,
                    local_instant(25),
                    local_instant(28),
                    Rate(1, Scale(3), "fee_fraction"),
                    (STAMP_BASE,),
                ),
                CnAShareStampDutyBand(
                    venue,
                    local_instant(28),
                    local_instant(30),
                    Rate(5, Scale(4), "fee_fraction"),
                    (STAMP_BASE, STAMP_HALF),
                ),
            )
        ),
    )


def policies() -> tuple[CnAShareCashMarketFeePolicy, CnAShareCashStampDutyTaxPolicy]:
    return (
        CnAShareCashMarketFeePolicy(market_rule_book()),
        CnAShareCashStampDutyTaxPolicy(tax_rule_book()),
    )


def fee_query(
    side: OrderSide,
    effective_at: UtcInstant,
    *,
    venue: str = "xshg",
    mechanism: CnAShareFeeTradeMechanism = CnAShareFeeTradeMechanism.AUCTION,
) -> CnAShareCashFeeRuleQuery:
    return CnAShareCashFeeRuleQuery(
        instrument(venue), side, effective_at, mechanism
    )


def _sim_instant(value: UtcInstant, sequence: int) -> SimulationInstant:
    return SimulationInstant(value, ORDER_PHASE, SourceSequence(sequence))


def source_order(
    *, quantity_units: int, side: OrderSide, effective_at: UtcInstant
) -> Order:
    base = order()
    value = instrument()
    return replace(
        base,
        account_id=ACCOUNT,
        intent=replace(
            base.intent,
            instrument_id=value.instrument_id,
            side=side,
            quantity=Quantity(quantity_units, QUANTITY_SCALE, str(value.instrument_id)),
            reduce_only=side is OrderSide.SELL,
            position_effect=(PositionEffect.CLOSE if side is OrderSide.SELL else PositionEffect.OPEN),
        ),
        created_at=_sim_instant(UtcInstant(effective_at.epoch_nanoseconds - 100), 1),
    )


def executable_spec(subject: Order, effective_at: UtcInstant) -> ExecutableOrderSpec:
    outcome = OrderTranslator().translate(
        subject,
        approval(subject),
        mapping(),
        UtcInstant(effective_at.epoch_nanoseconds - 90),
    )
    assert outcome.executable_spec is not None
    return outcome.executable_spec


def market_rule_approval(
    *, quantity_units: int, side: OrderSide, effective_at: UtcInstant
) -> MarketRuleApproval:
    value = instrument()
    subject = source_order(
        quantity_units=quantity_units, side=side, effective_at=effective_at
    )
    spec = executable_spec(subject, effective_at)
    order_rule_ref = ProfileComponentRef(
        ProfilePortType.ORDER_RULE_MODEL,
        "equity.cn_a_share.cash.fixture-order-rules.v1",
        1,
        "sha256:" + "a" * 64,
    )
    lattice = QuantityLattice.create(
        instrument_id=value.instrument_id,
        lattice_key="equity.cn_a_share.cash.fixture-lattice.v1",
        lattice_version=1,
        atomic_scale=QUANTITY_SCALE,
        step_units=1,
        buy_lot_units=100,
        sell_lot_units=100,
        min_quantity_units=0,
        min_notional=Money(0, FEE_SCALE, str(CNY)),
        odd_lot_close_permitted=True,
        whole_sell_residual_permitted=True,
    )
    snapshot = OrderRuleSnapshot.create(
        component_ref=order_rule_ref,
        instrument_id=value.instrument_id,
        session_id=SessionId("cn-a-share.fixture", "2023-08-28.auction"),
        session_state=MarketSessionState.OPEN,
        quantity_lattice=lattice,
        price_scale=FEE_SCALE,
        price_tick_units=1,
        lower_price_limit=None,
        upper_price_limit=None,
        permitted_sides=(OrderSide.BUY, OrderSide.SELL),
        permitted_position_effects=(PositionEffect.OPEN, PositionEffect.CLOSE),
        reduce_only_required=False,
        notional_rounding=RoundingPolicy.HALF_UP,
        supplemental_decisions=(),
    )
    interval = OrderRuleInterval.create(
        effective_from=UtcInstant(effective_at.epoch_nanoseconds - 10),
        effective_to_exclusive=UtcInstant(effective_at.epoch_nanoseconds + 10),
        snapshot=snapshot,
    )
    timeline = OrderRuleTimeline.create(
        timeline_key="equity.cn_a_share.cash.fixture-order-rules.v1",
        timeline_version=1,
        instrument_id=value.instrument_id,
        intervals=(interval,),
    )
    price = Price(1_000, FEE_SCALE, str(value.instrument_id), str(CNY))
    evidence = OrderRuleNotionalEvidence(
        NotionalPriceBasis.SUPPLIED_REFERENCE,
        price,
        canonical_sha256({"price": price, "available_at": effective_at}),
        UtcInstant(effective_at.epoch_nanoseconds - 20),
    )
    outcome = MarketRuleEvaluator().evaluate(
        OrderRuleEvaluationInput(spec, effective_at, evidence), timeline
    )
    assert outcome.approval is not None
    return outcome.approval


def account_fee_schedule_ref() -> AccountFeeScheduleRef:
    schedule_key = "development.cn-a-share.cash-broker.net-commission.v1"
    payload = {
        "type": "development_cn_a_share_cash_broker_net_commission_schedule",
        "schema_version": 1,
        "schedule_key": schedule_key,
        "schedule_version": 1,
        "commission_rate": Rate(3, Scale(4), "fee_fraction"),
        "minimum_amount": Money(500, FEE_SCALE, str(CNY)),
        "assessment_scale": 2,
        "rounding": RoundingPolicy.HALF_UP.value,
        "excluded_charge_keys": (
            "exchange_handling",
            "regulatory",
            "transfer",
            "stamp_duty",
        ),
    }
    return AccountFeeScheduleRef(schedule_key, 1, canonical_sha256(payload))


def _tagged(tag: str, payload: object) -> str:
    return f"{tag}:{canonical_sha256(payload)}"


def _account_rule_id(purpose: str, basis: str) -> str:
    return _tagged(
        "cn-a-share-development-commission-rule-v1",
        {
            "account_fee_schedule_ref": account_fee_schedule_ref(),
            "purpose": purpose,
            "basis": basis,
        },
    )


def reservation_buffer(
    *,
    side: OrderSide,
    effective_at: UtcInstant,
    maximum_fill_count: int = 2,
) -> CnAShareFeeReservationBuffer:
    market, tax = policies()
    query = fee_query(side, effective_at)
    market_outcome = market.assess_fees(query)
    tax_outcome = tax.assess_taxes(query)
    assert market_outcome.result is not None and tax_outcome.result is not None
    return CnAShareFeeReservationBuffer.create(
        market_resolution=market_outcome.result,
        tax_resolution=tax_outcome.result,
        maximum_fill_count=maximum_fill_count,
    )


def reservation_rule_set(
    *, side: OrderSide, effective_at: UtcInstant, maximum_fill_count: int = 2
) -> FeeReservationRuleSet:
    market, tax = policies()
    market_outcome = market.assess_fees(fee_query(side, effective_at))
    tax_outcome = tax.assess_taxes(fee_query(side, effective_at))
    assert market_outcome.result is not None and tax_outcome.result is not None
    buffer = CnAShareFeeReservationBuffer.create(
        market_resolution=market_outcome.result,
        tax_resolution=tax_outcome.result,
        maximum_fill_count=maximum_fill_count,
    )
    account_rule_id = _account_rule_id("reservation", FeeReservationBasis.ORDER_NOTIONAL.value)
    account_rule = FeeReservationChargeRule(
        FeeReservationRuleSource.ACCOUNT_SCHEDULE,
        account_rule_id,
        FeeReservationBasis.ORDER_NOTIONAL,
        FeeReservationApplicability.APPLIES,
        Rate(3, Scale(4), "fee_fraction"),
        None,
        QUANTIZATION,
    )
    minimum = FeeReservationMinimum(
        FeeReservationRuleSource.ACCOUNT_SCHEDULE,
        _tagged(
            "cn-a-share-development-commission-minimum-v1",
            {
                "account_fee_schedule_ref": account_fee_schedule_ref(),
                "charge_rule_id": account_rule_id,
                "purpose": "reservation",
                "minimum_amount": Money(500, FEE_SCALE, str(CNY)),
            },
        ),
        (account_rule_id,),
        Money(500, FEE_SCALE, str(CNY)),
    )
    return FeeReservationRuleSet.create(
        market_fee_policy_ref=market.component_ref,
        tax_policy_ref=tax.component_ref,
        account_fee_schedule_ref=account_fee_schedule_ref(),
        reservation_currency=CNY,
        reservation_scale=FEE_SCALE,
        charge_rules=(
            *market_outcome.result.reservation_charge_rules,
            tax_outcome.result.reservation_charge_rule,
            buffer.market_charge_rule,
            buffer.tax_charge_rule,
            account_rule,
        ),
        minimums=(minimum,),
    )


def final_fill_rule_set(fill: Fill) -> FinalFeeRuleSet:
    market, tax = policies()
    market_outcome = market.assess_fees(fee_query(fill.side, fill.execution_time))
    tax_outcome = tax.assess_taxes(fee_query(fill.side, fill.execution_time))
    assert market_outcome.result is not None and tax_outcome.result is not None
    account_rule = FinalFeeChargeRule(
        FinalFeeRuleSource.ACCOUNT_SCHEDULE,
        _account_rule_id("final_fill", FeeBasisType.FILL.value),
        FeeBasisType.FILL,
        FinalFeeCalculationBasis.NOTIONAL_RATE,
        FinalFeeApplicability.NOT_APPLICABLE,
        Rate(0, Scale(0), "fee_fraction"),
        None,
        QUANTIZATION,
    )
    return FinalFeeRuleSet.create(
        market_fee_policy_ref=market.component_ref,
        tax_policy_ref=tax.component_ref,
        account_fee_schedule_ref=account_fee_schedule_ref(),
        assessment_currency=CNY,
        assessment_scale=FEE_SCALE,
        charge_rules=(
            *market_outcome.result.final_fill_charge_rules,
            tax_outcome.result.final_fill_charge_rule,
            account_rule,
        ),
        minimums=(),
    )


def final_order_rule_set(
    *, side: OrderSide, effective_at: UtcInstant
) -> FinalFeeRuleSet:
    market, tax = policies()
    market_outcome = market.assess_fees(fee_query(side, effective_at))
    tax_outcome = tax.assess_taxes(fee_query(side, effective_at))
    assert market_outcome.result is not None and tax_outcome.result is not None
    account_rule_id = _account_rule_id("final_order", FeeBasisType.ORDER.value)
    account_rule = FinalFeeChargeRule(
        FinalFeeRuleSource.ACCOUNT_SCHEDULE,
        account_rule_id,
        FeeBasisType.ORDER,
        FinalFeeCalculationBasis.NOTIONAL_RATE,
        FinalFeeApplicability.ALWAYS,
        Rate(3, Scale(4), "fee_fraction"),
        None,
        QUANTIZATION,
    )
    minimum = FinalFeeMinimum(
        FinalFeeRuleSource.ACCOUNT_SCHEDULE,
        _tagged(
            "cn-a-share-development-commission-minimum-v1",
            {
                "account_fee_schedule_ref": account_fee_schedule_ref(),
                "charge_rule_id": account_rule_id,
                "purpose": "final_order",
                "minimum_amount": Money(500, FEE_SCALE, str(CNY)),
            },
        ),
        FeeBasisType.ORDER,
        (account_rule_id,),
        Money(500, FEE_SCALE, str(CNY)),
    )
    return FinalFeeRuleSet.create(
        market_fee_policy_ref=market.component_ref,
        tax_policy_ref=tax.component_ref,
        account_fee_schedule_ref=account_fee_schedule_ref(),
        assessment_currency=CNY,
        assessment_scale=FEE_SCALE,
        charge_rules=(
            market_outcome.result.final_order_not_applicable_rule,
            tax_outcome.result.final_order_not_applicable_rule,
            account_rule,
        ),
        minimums=(minimum,),
    )


def fill(
    subject: Order,
    digit: str,
    execution_time: UtcInstant,
    *,
    quantity_units: int = 100,
) -> Fill:
    value = instrument()
    price = Price(1_000, FEE_SCALE, str(value.instrument_id), str(CNY))
    return Fill(
        domain_id(DomainIdKind.FILL, digit),
        subject.order_id,
        subject.account_id,
        value.instrument_id.venue,
        value.instrument_id,
        subject.intent.side,
        Quantity(quantity_units, QUANTITY_SCALE, str(value.instrument_id)),
        price,
        PricePurpose.EXECUTION_REFERENCE,
        price,
        Money(0, FEE_SCALE, str(CNY)),
        f"slippage:{digit}",
        "next_eligible_bar_open.v1",
        None,
        "taker",
        execution_time,
    )


def _event(
    subject: Order,
    *,
    event_type: OrderEventType,
    name: str,
    occurred_at: UtcInstant,
    sequence: int,
    causation_id: str,
    fill_value: Fill | None = None,
) -> OrderEventRecord:
    return OrderEventRecord(
        OrderEvent(
            f"event:{name}",
            subject.order_id,
            causation_id,
            event_type,
            _sim_instant(occurred_at, sequence),
            None if fill_value is None else fill_value.fill_id,
            f"evidence:{name}",
            None,
        ),
        fill_value,
    )


def partial_cancelled_stream(
    *, quantity_units: int, side: OrderSide, effective_at: UtcInstant
) -> OrderEventStream:
    subject = source_order(
        quantity_units=quantity_units, side=side, effective_at=effective_at
    )
    records = []
    causation = subject.intent.parent_id
    event_types = (
        OrderEventType.ORDER_INTENT_CREATED,
        OrderEventType.ORDER_CAPABILITY_APPROVED,
        OrderEventType.ORDER_TRANSLATED,
        OrderEventType.MARKET_RULE_APPROVED,
        OrderEventType.FEE_RESERVATION_ESTIMATED,
        OrderEventType.PRE_TRADE_RISK_APPROVED,
        OrderEventType.ORDER_SUBMITTED,
        OrderEventType.ORDER_ACCEPTED,
        OrderEventType.ORDER_ACTIVATED,
    )
    for sequence, event_type in enumerate(event_types, start=1):
        record = _event(
            subject,
            event_type=event_type,
            name=f"{sequence}-{event_type.value}",
            occurred_at=(
                subject.created_at.instant
                if sequence == 1
                else UtcInstant(effective_at.epoch_nanoseconds + sequence)
            ),
            sequence=sequence,
            causation_id=causation,
        )
        records.append(record)
        causation = record.event.event_id
    fills = (
        fill(subject, "2", UtcInstant(effective_at.epoch_nanoseconds + 10)),
        fill(subject, "3", UtcInstant(effective_at.epoch_nanoseconds + 20)),
    )
    for sequence, value in enumerate(fills, start=10):
        record = _event(
            subject,
            event_type=OrderEventType.ORDER_PARTIALLY_FILLED,
            name=f"{sequence}-partial",
            occurred_at=value.execution_time,
            sequence=sequence,
            causation_id=causation,
            fill_value=value,
        )
        records.append(record)
        causation = record.event.event_id
    requested = _event(
        subject,
        event_type=OrderEventType.ORDER_CANCEL_REQUESTED,
        name="12-cancel-requested",
        occurred_at=UtcInstant(effective_at.epoch_nanoseconds + 30),
        sequence=12,
        causation_id=causation,
    )
    cancelled = _event(
        subject,
        event_type=OrderEventType.ORDER_CANCELLED,
        name="13-cancelled",
        occurred_at=UtcInstant(effective_at.epoch_nanoseconds + 40),
        sequence=13,
        causation_id=requested.event.event_id,
    )
    return OrderEventStream.from_records(
        subject, (*records, requested, cancelled)
    )


def reservation_states(
    proposal: ResourceReservationProposal,
    stream: OrderEventStream,
) -> tuple[ResourceReservationState, ResourceReservationState, ResourceReservationState]:
    records = stream.records
    quantity = stream.order.intent.quantity
    schedule = OrderReservationSchedule(
        order_id=stream.order.order_id,
        source_proposal_hash=proposal.proposal_hash,
        updates=(
            OrderReservationUpdate(
                stream.order.order_id,
                records[7].event.event_id,
                OrderEventType.ORDER_ACCEPTED,
                quantity,
                proposal.commitment,
                canonical_sha256({"proposal": proposal.proposal_hash, "stage": "accepted"}),
            ),
            OrderReservationUpdate(
                stream.order.order_id,
                records[9].event.event_id,
                OrderEventType.ORDER_PARTIALLY_FILLED,
                Quantity(quantity.units - 100, quantity.scale, quantity.instrument_id),
                ReservationCommitment(
                    fee_reserve=(Money(1_000, FEE_SCALE, str(CNY)),)
                ),
                canonical_sha256({"proposal": proposal.proposal_hash, "stage": "partial-1"}),
            ),
            OrderReservationUpdate(
                stream.order.order_id,
                records[10].event.event_id,
                OrderEventType.ORDER_PARTIALLY_FILLED,
                Quantity(quantity.units - 200, quantity.scale, quantity.instrument_id),
                ReservationCommitment(
                    fee_reserve=(Money(900, FEE_SCALE, str(CNY)),)
                ),
                canonical_sha256({"proposal": proposal.proposal_hash, "stage": "partial-2"}),
            ),
        ),
    )
    book = ResourceReservationBook(stream.order.account_id)
    return (
        book.project((OrderEventStream.from_records(stream.order, records[:8]),), (schedule,)),
        book.project((OrderEventStream.from_records(stream.order, records[:11]),), (schedule,)),
        book.project((stream,), (schedule,)),
    )


def filled_stream(
    *,
    quantity_units: int,
    side: OrderSide,
    effective_at: UtcInstant,
    fill_quantities: tuple[int, int] = (100, 100),
) -> OrderEventStream:
    if sum(fill_quantities) != quantity_units:
        raise ValueError("fill_quantities must equal order quantity")
    subject = source_order(
        quantity_units=quantity_units, side=side, effective_at=effective_at
    )
    prefix = partial_cancelled_stream(
        quantity_units=max(quantity_units, 300), side=side, effective_at=effective_at
    ).records[:9]
    first = fill(
        subject,
        "2",
        UtcInstant(effective_at.epoch_nanoseconds + 10),
        quantity_units=fill_quantities[0],
    )
    second = fill(
        subject,
        "3",
        UtcInstant(effective_at.epoch_nanoseconds + 20),
        quantity_units=fill_quantities[1],
    )
    partial = _event(
        subject,
        event_type=OrderEventType.ORDER_PARTIALLY_FILLED,
        name="10-partial",
        occurred_at=first.execution_time,
        sequence=10,
        causation_id=prefix[-1].event.event_id,
        fill_value=first,
    )
    completed = _event(
        subject,
        event_type=OrderEventType.ORDER_FILLED,
        name="11-filled",
        occurred_at=second.execution_time,
        sequence=11,
        causation_id=partial.event.event_id,
        fill_value=second,
    )
    return OrderEventStream.from_records(subject, (*prefix, partial, completed))


def single_fill_stream(
    *, quantity_units: int, side: OrderSide, effective_at: UtcInstant
) -> OrderEventStream:
    subject = source_order(
        quantity_units=quantity_units, side=side, effective_at=effective_at
    )
    prefix = partial_cancelled_stream(
        quantity_units=max(quantity_units, 300), side=side, effective_at=effective_at
    ).records[:9]
    value = fill(
        subject,
        "2",
        UtcInstant(effective_at.epoch_nanoseconds + 10),
        quantity_units=quantity_units,
    )
    completed = _event(
        subject,
        event_type=OrderEventType.ORDER_FILLED,
        name="10-filled",
        occurred_at=value.execution_time,
        sequence=10,
        causation_id=prefix[-1].event.event_id,
        fill_value=value,
    )
    return OrderEventStream.from_records(subject, (*prefix, completed))


def unfilled_cancelled_stream(
    *, side: OrderSide, effective_at: UtcInstant
) -> OrderEventStream:
    subject = source_order(
        quantity_units=100, side=side, effective_at=effective_at
    )
    prefix = partial_cancelled_stream(
        quantity_units=300, side=side, effective_at=effective_at
    ).records[:9]
    requested = _event(
        subject,
        event_type=OrderEventType.ORDER_CANCEL_REQUESTED,
        name="10-unfilled-cancel-requested",
        occurred_at=UtcInstant(effective_at.epoch_nanoseconds + 10),
        sequence=10,
        causation_id=prefix[-1].event.event_id,
    )
    cancelled = _event(
        subject,
        event_type=OrderEventType.ORDER_CANCELLED,
        name="11-unfilled-cancelled",
        occurred_at=UtcInstant(effective_at.epoch_nanoseconds + 20),
        sequence=11,
        causation_id=requested.event.event_id,
    )
    return OrderEventStream.from_records(subject, (*prefix, requested, cancelled))


def cash_key() -> CashBalanceKey:
    value = instrument()
    return CashBalanceKey(ACCOUNT, value.instrument_id.venue, CNY)


def fee_recorded_at(value: UtcInstant, sequence: int) -> SimulationInstant:
    return SimulationInstant(value, FEE_PHASE, SourceSequence(sequence))
