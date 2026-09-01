from __future__ import annotations

from dataclasses import replace

from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    ExecutionStyle,
    Money,
    OrderSide,
    OrderStatus,
    Quantity,
    TimeInForce,
    UtcInstant,
)
from crypto_quant_trading import (
    CancelIntent,
    CashAvailability,
    CappedPortfolioTargetV1,
    FeeReservationEstimate,
    OrderCapabilitySet,
    PortfolioOrderSizerV1,
    PortfolioRebalanceCoordinatorV2,
    PortfolioRebalanceExecutionPolicyV1,
    PortfolioSizingCandidateV1,
    PortfolioSizingOmissionReason,
    PortfolioSizingOrderIdentityV1,
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
    identity = PortfolioSizingOrderIdentityV1.create(
        decision_ordinal=1,
        instrument_id=BTC,
        side=side,
        preallocated_order_id=DomainId(DomainIdKind.ORDER, "ord_" + order_digit * 64),
        source_target_hash=SOURCE_HASH,
    )
    quantity = lambda units: Quantity(units, QUANTITY_SCALE, str(BTC))
    return PortfolioSizingCandidateV1(
        identity=identity,
        account_id=ACCOUNT,
        current_quantity=quantity(current),
        requested_target_quantity=quantity(target),
        sellable_quantity=quantity(current if sellable is None else sellable),
        retained_working_buy_coverage=quantity(buy_coverage),
        retained_working_sell_coverage=quantity(sell_coverage),
        lattice=sizing_inputs()[0].lattice,
        capability_set=capabilities,
        translation_mapping=resolved.translation_mapping,
        order_rule_timeline=pretrade.order_rule_timeline,
        notional_evidence=pretrade.notional_evidence,
        fee_rule_set=pretrade.fee_reservation_rule_set,
        created_at=order.created_at,
        market_rule_evaluated_at=pretrade.market_rule_evaluated_at,
        fee_estimated_at=pretrade.fee_estimated_at,
    )


def _cash(tradable: int) -> CashAvailability:
    amount = lambda units: Money(units, MONEY_SCALE, "USD")
    return CashAvailability(
        CASH_KEY,
        amount(max(tradable, 100_000)),
        amount(max(tradable, 100_000)),
        amount(tradable),
        amount(tradable),
        amount(tradable),
    )


def _size(*candidates: PortfolioSizingCandidateV1, cash: int = 100_000):
    return PortfolioOrderSizerV1().size(
        source_target_hash=SOURCE_HASH,
        candidates=tuple(candidates),
        cash_availability=_cash(cash),
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
    assert evidence.iteration_count > 1
    assert PortfolioSizingOmissionReason.SETTLED_CASH_CAPPED in _reasons(result)


def test_minimum_commission_discontinuity_recomputes_until_stable() -> None:
    candidate = _candidate(side=OrderSide.BUY, current=0, target=1_000)
    full = _size(candidate, cash=100_000).sizing_evidence[0]
    budget = full.exact_notional.units + full.exact_fee_reservation.units - 1

    result = _size(candidate, cash=budget)

    assert result.sizing_evidence[0].final_quantity.units < 1_000
    assert PortfolioSizingOmissionReason.MINIMUM_COMMISSION_CAPPED in _reasons(result)
    assert result.sizing_evidence[0].iteration_count > 1


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
