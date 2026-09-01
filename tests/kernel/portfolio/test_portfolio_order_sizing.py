from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    ExecutionStyle,
    InstrumentId,
    Money,
    OrderSide,
    OrderStatus,
    Price,
    Quantity,
    TimeInForce,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import (
    CancelIntent,
    CashAvailability,
    CappedPortfolioTargetV1,
    FeeReservationEstimate,
    NotionalPriceBasis,
    OrderCapabilitySet,
    OrderRuleInterval,
    OrderRuleNotionalEvidence,
    OrderRuleSnapshot,
    OrderRuleTimeline,
    PortfolioOrderSizerV1,
    PortfolioRebalanceCoordinatorV2,
    PortfolioRebalanceExecutionPolicyV1,
    PortfolioSizingCandidateV1,
    PortfolioSizingOmissionReason,
    PortfolioSizingOrderIdentityV1,
    QuantityLattice,
)

from tests.runtime.engine._fixtures import (
    ACCOUNT,
    BTC,
    CASH_KEY,
    MONEY_SCALE,
    QUANTITY_SCALE,
    admission,
    expected_order,
    sizing_inputs,
)


SOURCE_HASH = "sha256:" + "d" * 64


def _candidate(
    *,
    side: OrderSide,
    current: int,
    target: int,
    sellable: int | None = None,
    buy_coverage: int = 0,
    sell_coverage: int = 0,
    order_digit: str = "7",
    source_hash: str = SOURCE_HASH,
    instrument_id: InstrumentId = BTC,
) -> PortfolioSizingCandidateV1:
    resolved = admission()
    pretrade = resolved.pretrade_plan
    order, _ = expected_order()
    capabilities = resolved.capability_set
    market_style = next(
        value
        for value in capabilities.style_capabilities
        if value.execution_style is ExecutionStyle.MARKET
    )
    capabilities = OrderCapabilitySet.create(
        capability_set_key=capabilities.capability_set_key,
        capability_set_version=capabilities.capability_set_version,
        style_capabilities=tuple(
            replace(
                value,
                time_in_forces=(TimeInForce.DAY, TimeInForce.GTC),
            )
            if value is market_style
            else value
            for value in capabilities.style_capabilities
        ),
        supports_reduce_only=capabilities.supports_reduce_only,
        supported_position_effects=capabilities.supported_position_effects,
        declared_capability_keys=capabilities.declared_capability_keys,
    )
    lattice = sizing_inputs()[0].lattice
    timeline = pretrade.order_rule_timeline
    notional_evidence = pretrade.notional_evidence
    if instrument_id != BTC:
        lattice = QuantityLattice.create(
            instrument_id=instrument_id,
            lattice_key=f"{lattice.lattice_key}.clone",
            lattice_version=lattice.lattice_version,
            atomic_scale=lattice.atomic_scale,
            step_units=lattice.step_units,
            buy_lot_units=lattice.buy_lot_units,
            sell_lot_units=lattice.sell_lot_units,
            min_quantity_units=lattice.min_quantity_units,
            min_notional=lattice.min_notional,
            odd_lot_close_permitted=lattice.odd_lot_close_permitted,
            whole_sell_residual_permitted=lattice.whole_sell_residual_permitted,
        )
        source_snapshot = timeline.intervals[0].snapshot
        clone_price = lambda value: (
            None
            if value is None
            else Price(
                value.units,
                value.scale,
                str(instrument_id),
                value.quote_currency,
            )
        )
        snapshot = OrderRuleSnapshot.create(
            component_ref=source_snapshot.component_ref,
            instrument_id=instrument_id,
            session_id=source_snapshot.session_id,
            session_state=source_snapshot.session_state,
            quantity_lattice=lattice,
            price_scale=source_snapshot.price_scale,
            price_tick_units=source_snapshot.price_tick_units,
            lower_price_limit=clone_price(source_snapshot.lower_price_limit),
            upper_price_limit=clone_price(source_snapshot.upper_price_limit),
            permitted_sides=source_snapshot.permitted_sides,
            permitted_position_effects=source_snapshot.permitted_position_effects,
            reduce_only_required=source_snapshot.reduce_only_required,
            notional_rounding=source_snapshot.notional_rounding,
            supplemental_decisions=source_snapshot.supplemental_decisions,
            max_limit_order_quantity_units=source_snapshot.max_limit_order_quantity_units,
            max_market_order_quantity_units=source_snapshot.max_market_order_quantity_units,
        )
        interval = OrderRuleInterval.create(
            effective_from=timeline.intervals[0].effective_from,
            effective_to_exclusive=timeline.intervals[0].effective_to_exclusive,
            snapshot=snapshot,
        )
        timeline = OrderRuleTimeline.create(
            timeline_key=f"{timeline.timeline_key}.clone",
            timeline_version=timeline.timeline_version,
            instrument_id=instrument_id,
            intervals=(interval,),
        )
        price = Price(
            notional_evidence.price.units,
            notional_evidence.price.scale,
            str(instrument_id),
            notional_evidence.price.quote_currency,
        )
        notional_evidence = OrderRuleNotionalEvidence(
            basis=NotionalPriceBasis.SUPPLIED_REFERENCE,
            price=price,
            source_hash=canonical_sha256(
                {"price": price, "available_at": notional_evidence.available_at}
            ),
            available_at=notional_evidence.available_at,
        )
    identity = PortfolioSizingOrderIdentityV1.create(
        decision_ordinal=1,
        instrument_id=instrument_id,
        side=side,
        preallocated_order_id=DomainId(DomainIdKind.ORDER, "ord_" + order_digit * 64),
        source_target_hash=source_hash,
    )
    quantity = lambda units: Quantity(units, QUANTITY_SCALE, str(instrument_id))
    return PortfolioSizingCandidateV1(
        identity=identity,
        account_id=ACCOUNT,
        current_quantity=quantity(current),
        requested_target_quantity=quantity(target),
        sellable_quantity=quantity(current if sellable is None else sellable),
        retained_working_buy_coverage=quantity(buy_coverage),
        retained_working_sell_coverage=quantity(sell_coverage),
        lattice=lattice,
        capability_set=capabilities,
        translation_mapping=resolved.translation_mapping,
        order_rule_timeline=timeline,
        notional_evidence=notional_evidence,
        fee_rule_set=pretrade.fee_reservation_rule_set,
        created_at=order.created_at,
        market_rule_evaluated_at=pretrade.market_rule_evaluated_at,
        fee_estimated_at=pretrade.fee_estimated_at,
    )


def _cash(tradable: int, *, settled: int | None = None) -> CashAvailability:
    amount = lambda units: Money(units, MONEY_SCALE, "USD")
    settled = max(tradable, 100_000) if settled is None else settled
    return CashAvailability(
        CASH_KEY,
        amount(max(tradable, settled, 100_000)),
        amount(settled),
        amount(tradable),
        amount(tradable),
        amount(tradable),
    )


def _size(
    *candidates: PortfolioSizingCandidateV1,
    cash: int = 100_000,
    settled: int | None = None,
    active_cash: int = 0,
    active_fee: int = 0,
):
    return PortfolioOrderSizerV1().size(
        source_target_hash=(
            candidates[0].identity.source_target_hash if candidates else SOURCE_HASH
        ),
        candidates=tuple(candidates),
        cash_availability=_cash(cash, settled=settled),
        active_cash_reservations=Money(active_cash, MONEY_SCALE, "USD"),
        active_fee_reservations=Money(active_fee, MONEY_SCALE, "USD"),
    )


def _reasons(result) -> set[PortfolioSizingOmissionReason]:
    return {value.reason for value in result.omissions}


def test_durable_omission_reason_set_is_exact() -> None:
    assert {value.value for value in PortfolioSizingOmissionReason} == {
        "T1_UNSELLABLE",
        "ZERO_AFTER_LATTICE",
        "SETTLED_CASH_CAPPED",
        "MINIMUM_COMMISSION_CAPPED",
        "ACTIVE_ORDER_COVERAGE",
        "TARGET_SUPERSEDED",
    }


def test_t1_sell_cap_and_working_sell_coverage_are_durable() -> None:
    result = _size(
        _candidate(
            side=OrderSide.SELL,
            current=5_000,
            target=0,
            sellable=3_000,
            sell_coverage=1_000,
        )
    )

    evidence = result.sizing_evidence[0]
    assert evidence.final_quantity.units == 2_000
    assert evidence.identity.side is OrderSide.SELL
    assert PortfolioSizingOmissionReason.T1_UNSELLABLE in _reasons(result)
    assert PortfolioSizingOmissionReason.ACTIVE_ORDER_COVERAGE in _reasons(result)


def test_active_buy_coverage_reduces_new_order_quantity() -> None:
    result = _size(
        _candidate(
            side=OrderSide.BUY,
            current=0,
            target=5_000,
            buy_coverage=2_000,
        )
    )

    assert result.sizing_evidence[0].final_quantity.units == 3_000
    assert PortfolioSizingOmissionReason.ACTIVE_ORDER_COVERAGE in _reasons(result)


def test_settled_cash_cap_rounds_lots_and_keeps_preallocated_identity() -> None:
    candidate = _candidate(side=OrderSide.BUY, current=0, target=5_000)
    full_evidence = _size(candidate, cash=100_000).sizing_evidence[0]
    result = _size(candidate, cash=25_000)
    evidence = result.sizing_evidence[0]

    assert 0 < evidence.final_quantity.units < 5_000
    assert evidence.final_quantity.units % candidate.lattice.buy_lot_units == 0
    assert evidence.identity.preallocated_order_id == candidate.identity.preallocated_order_id
    assert evidence.identity.identity_hash == candidate.identity.identity_hash
    assert evidence.identity == full_evidence.identity
    assert isinstance(evidence.fee_estimate, FeeReservationEstimate)
    assert evidence.exact_fee_reservation == evidence.fee_estimate.total_fee
    approved_order = (
        evidence.fee_estimate.market_rule_approval.evaluation_input
        .executable_order_spec.source_order
    )
    assert approved_order.order_id == evidence.identity.preallocated_order_id
    assert approved_order.intent.quantity == evidence.final_quantity
    assert evidence.iteration_count > 1
    assert PortfolioSizingOmissionReason.SETTLED_CASH_CAPPED in _reasons(result)


def test_settled_cash_is_hard_cap_when_tradable_is_higher() -> None:
    candidate = _candidate(side=OrderSide.BUY, current=0, target=5_000)

    result = _size(
        candidate,
        cash=100_000,
        settled=20_000,
        active_cash=1_000,
        active_fee=500,
    )

    assert result.available_buy_budget.units == 18_500
    assert result.sizing_evidence[0].final_quantity.units < 5_000
    assert PortfolioSizingOmissionReason.SETTLED_CASH_CAPPED in _reasons(result)


def test_minimum_commission_discontinuity_recomputes_until_stable() -> None:
    candidate = _candidate(side=OrderSide.BUY, current=0, target=1_000)
    full = _size(candidate, cash=100_000).sizing_evidence[0]
    budget = full.exact_notional.units + full.exact_fee_reservation.units - 1

    result = _size(candidate, cash=budget)

    assert result.sizing_evidence[0].final_quantity.units < 1_000
    assert PortfolioSizingOmissionReason.MINIMUM_COMMISSION_CAPPED in _reasons(result)
    assert result.sizing_evidence[0].iteration_count > 1


def test_multi_buy_common_scale_recomputes_each_minimum_commission() -> None:
    second_instrument = InstrumentId(BTC.venue, "cash:eth-usd")
    first = _candidate(side=OrderSide.BUY, current=0, target=1_000)
    second = _candidate(
        side=OrderSide.BUY,
        current=0,
        target=2_000,
        order_digit="5",
        instrument_id=second_instrument,
    )
    fully_funded = _size(first, second, cash=100_000)
    full_cost = sum(
        value.exact_notional.units + value.exact_fee_reservation.units
        for value in fully_funded.sizing_evidence
    )

    result = _size(first, second, cash=full_cost - 1)

    by_instrument = {
        value.identity.instrument_id: value for value in result.sizing_evidence
    }
    assert by_instrument[BTC].final_quantity.units < first.requested_order_units
    assert (
        by_instrument[second_instrument].final_quantity.units
        < second.requested_order_units
    )
    common_scale = max(
        Fraction(by_instrument[BTC].final_quantity.units, first.requested_order_units),
        Fraction(
            by_instrument[second_instrument].final_quantity.units,
            second.requested_order_units,
        ),
    )
    assert by_instrument[BTC].final_quantity.units == (
        first.requested_order_units
        * common_scale.numerator
        // common_scale.denominator
    )
    assert by_instrument[second_instrument].final_quantity.units == (
        second.requested_order_units
        * common_scale.numerator
        // common_scale.denominator
    )
    assert all(value.iteration_count > 1 for value in result.sizing_evidence)
    assert PortfolioSizingOmissionReason.MINIMUM_COMMISSION_CAPPED in _reasons(result)


def test_expected_sell_proceeds_are_excluded_from_buy_budget() -> None:
    sell = _candidate(
        side=OrderSide.SELL,
        current=5_000,
        target=0,
        sellable=5_000,
        order_digit="8",
    )
    buy = _candidate(side=OrderSide.BUY, current=0, target=5_000)

    result = _size(sell, buy, cash=20_000)
    buy_evidence = next(
        value for value in result.sizing_evidence if value.identity.side is OrderSide.BUY
    )

    assert buy_evidence.final_quantity.units < 5_000
    assert PortfolioSizingOmissionReason.SETTLED_CASH_CAPPED in _reasons(result)
    assert result.available_buy_budget.units == 20_000 - result.exact_sell_fee_reservation.units


def test_side_tif_and_canonical_order_sequence() -> None:
    sell_result = _size(
        _candidate(
            side=OrderSide.SELL,
            current=5_000,
            target=0,
            sellable=5_000,
            order_digit="8",
        )
    )
    buy_result = _size(_candidate(side=OrderSide.BUY, current=0, target=1_000))
    capped = CappedPortfolioTargetV1(
        source_target_hash=SOURCE_HASH,
        cash_availability_hash=buy_result.cash_availability_hash,
        sizing_evidence=(
            sell_result.sizing_evidence[0],
            buy_result.sizing_evidence[0],
        ),
        omissions=(),
        available_buy_budget=buy_result.available_buy_budget,
        exact_sell_fee_reservation=sell_result.exact_sell_fee_reservation,
    )
    policy = PortfolioRebalanceExecutionPolicyV1(
        "equity.cn_a_share.portfolio.rebalance-execution.v1", 1
    )

    cancellation = CancelIntent(
        cancel_intent_id="cancel-intent-v1:sha256:" + "e" * 64,
        order_id=DomainId(DomainIdKind.ORDER, "ord_" + "6" * 64),
        instrument_id=BTC,
        reason_code="target_superseded",
        normalized_target_id="normalized-target-v1:sha256:" + "f" * 64,
    )
    plan = PortfolioRebalanceCoordinatorV2().coordinate(
        capped_target=capped,
        policy=policy,
        created_at=UtcInstant(150),
        cancellations=(cancellation,),
    )

    assert tuple(value.intent.side for value in plan.planned_orders) == (
        OrderSide.SELL,
        OrderSide.BUY,
    )
    assert plan.planned_orders[0].intent.time_in_force.value == "gtc"
    assert plan.planned_orders[1].intent.time_in_force.value == "day"
    assert tuple(value.stage_rank for value in plan.stages) == (90, 100, 110)
