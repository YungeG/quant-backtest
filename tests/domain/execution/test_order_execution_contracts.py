from __future__ import annotations

from dataclasses import fields, replace
from typing import Any, cast

import pytest

from crypto_quant_domain import (
    CurrencyId,
    DomainId,
    DomainIdKind,
    ExecutionStyle,
    FeeAssessment,
    FeeBasisType,
    Fill,
    InstrumentId,
    Money,
    Order,
    OrderEvent,
    OrderEventType,
    OrderIntent,
    OrderSide,
    OrderState,
    OrderStatus,
    OrderTranslationReport,
    PositionEffect,
    Price,
    PriceConstraint,
    Quantity,
    Scale,
    SessionId,
    SettlementObligation,
    SimulationInstant,
    SourceSequence,
    TimeInForce,
    TimelinePhase,
    TranslationFieldMapping,
    TranslationStatus,
    UnsupportedCapability,
    UtcInstant,
    VenueId,
)


def domain_id(kind: DomainIdKind, digit: str) -> DomainId:
    return DomainId(kind, f"{kind.prefix}_{digit * 64}")


def instrument() -> InstrumentId:
    return InstrumentId(VenueId("binance_usdm"), "linear_perpetual:btc-usdt")


def quantity(units: int = 125_000_000, places: int = 8) -> Quantity:
    return Quantity(units, Scale(places), str(instrument()))


def price(units: int = 6_250_000, places: int = 2) -> Price:
    return Price(units, Scale(places), str(instrument()), "USDT")


def simulation_instant(nanoseconds: int = 100, sequence: int = 1) -> SimulationInstant:
    return SimulationInstant(
        UtcInstant(nanoseconds), TimelinePhase(30, "order"), SourceSequence(sequence)
    )


def intent() -> OrderIntent:
    return OrderIntent(
        instrument_id=instrument(),
        side=OrderSide.BUY,
        quantity=quantity(),
        execution_style=ExecutionStyle.LIMIT,
        price_constraint=PriceConstraint(limit_price=price()),
        time_in_force=TimeInForce.GTX,
        reduce_only=False,
        position_effect=PositionEffect.OPEN,
        urgency="normal",
        reason="scheduled rebalance",
        parent_id="target:batch-100",
    )


def order() -> Order:
    return Order(
        order_id=domain_id(DomainIdKind.ORDER, "1"),
        account_id="account:primary",
        intent=intent(),
        created_at=simulation_instant(),
    )


def fill() -> Fill:
    return Fill(
        fill_id=domain_id(DomainIdKind.FILL, "2"),
        order_id=order().order_id,
        account_id="account:primary",
        venue_id=VenueId("binance_usdm"),
        instrument_id=instrument(),
        side=OrderSide.BUY,
        quantity=quantity(50_000_000),
        reference_price=price(6_250_000),
        reference_price_purpose="execution_reference",
        price=price(6_251_000),
        slippage_amount=Money(500_000, Scale(2), "USDT"),
        slippage_decision_id="slippage:decision-1",
        slippage_model_key="slippage.zero-or-fixed.v1",
        slippage_calibration_id=None,
        liquidity="taker",
        execution_time=UtcInstant(120),
    )


def test_order_intent_is_typed_venue_neutral_and_has_no_extension_escape_hatch() -> None:
    value = intent()
    assert value.quantity.instrument_id == str(value.instrument_id)
    assert value.price_constraint is not None
    assert set(field.name for field in fields(OrderIntent)).isdisjoint(
        {"symbol", "trading_pair", "board", "position_action", "extensions", "metadata"}
    )

    with pytest.raises(TypeError):
        cast(Any, OrderIntent)(
            instrument_id=value.instrument_id,
            side=value.side,
            quantity=value.quantity,
            execution_style=value.execution_style,
            price_constraint=value.price_constraint,
            time_in_force=value.time_in_force,
            reduce_only=value.reduce_only,
            position_effect=value.position_effect,
            urgency=value.urgency,
            reason=value.reason,
            parent_id=value.parent_id,
            symbol="BTCUSDT",
        )
    with pytest.raises(TypeError, match="OrderSide"):
        replace(value, side=cast(Any, "buy"))
    with pytest.raises(ValueError, match="positive"):
        replace(value, quantity=quantity(0))
    with pytest.raises(ValueError, match="Quantity instrument"):
        replace(value, quantity=Quantity(1, Scale(8), "other:instrument"))
    with pytest.raises(ValueError, match="PriceConstraint instrument"):
        replace(
            value,
            price_constraint=PriceConstraint(
                limit_price=Price(1, Scale(2), "other:instrument", "USDT")
            ),
        )


def test_order_binds_order_identity_account_intent_and_creation_instant() -> None:
    value = order()
    assert value.order_id.kind is DomainIdKind.ORDER
    assert value.intent is not None

    with pytest.raises(ValueError, match="ORDER"):
        replace(value, order_id=domain_id(DomainIdKind.FILL, "2"))
    with pytest.raises(ValueError, match="account_id"):
        replace(value, account_id=" account:primary ")


def test_order_event_requires_lifecycle_specific_evidence() -> None:
    partial = OrderEvent(
        event_id="event:partial-1",
        order_id=order().order_id,
        causation_id="event:accepted-1",
        event_type=OrderEventType.ORDER_PARTIALLY_FILLED,
        occurred_at=simulation_instant(120, 2),
        fill_id=fill().fill_id,
    )
    assert partial.fill_id == fill().fill_id

    with pytest.raises(ValueError, match="fill_id"):
        replace(partial, fill_id=None)
    with pytest.raises(ValueError, match="only Fill events"):
        replace(partial, event_type=OrderEventType.ORDER_ACCEPTED)
    with pytest.raises(ValueError, match="reason_code"):
        OrderEvent(
            event_id="event:risk-rejected-1",
            order_id=order().order_id,
            causation_id="event:risk-1",
            event_type=OrderEventType.PRE_TRADE_RISK_REJECTED,
            occurred_at=simulation_instant(110, 2),
        )


def test_order_state_enforces_quantity_projection_invariants() -> None:
    value = OrderState(
        order_id=order().order_id,
        status=OrderStatus.PARTIALLY_FILLED,
        ordered_quantity=quantity(125_000_000),
        cumulative_filled_quantity=quantity(50_000_000),
        remaining_quantity=quantity(75_000_000),
        last_event_id="event:partial-1",
        updated_at=simulation_instant(120, 2),
    )
    assert (
        value.cumulative_filled_quantity.units + value.remaining_quantity.units
        == 125_000_000
    )

    with pytest.raises(ValueError, match="identity"):
        replace(value, remaining_quantity=Quantity(75_000_000, Scale(8), "other"))
    with pytest.raises(ValueError, match="scale"):
        replace(value, remaining_quantity=quantity(750_000, 6))
    with pytest.raises(ValueError, match="positive"):
        replace(
            value,
            ordered_quantity=quantity(0),
            cumulative_filled_quantity=quantity(0),
            remaining_quantity=quantity(0),
        )
    with pytest.raises(ValueError, match="sum"):
        replace(value, remaining_quantity=quantity(74_000_000))
    with pytest.raises(ValueError, match="FILLED"):
        replace(value, status=OrderStatus.FILLED)


def test_fill_preserves_execution_provenance_without_final_fee() -> None:
    value = fill()
    assert "fee" not in {field.name for field in fields(Fill)}
    assert value.price.quote_currency == value.slippage_amount.currency

    with pytest.raises(ValueError, match="FILL"):
        replace(value, fill_id=domain_id(DomainIdKind.ORDER, "1"))
    with pytest.raises(ValueError, match="instrument identity"):
        replace(value, quantity=Quantity(1, Scale(8), "other"))
    with pytest.raises(ValueError, match="quote currency"):
        replace(value, slippage_amount=Money(1, Scale(2), "USD"))
    with pytest.raises(ValueError, match="positive"):
        replace(value, price=price(0))


def test_fee_assessment_uses_typed_unique_basis_and_rule_provenance() -> None:
    assessment = FeeAssessment(
        fee_assessment_id=domain_id(DomainIdKind.FEE, "3"),
        basis_type=FeeBasisType.FILL,
        basis_ids=(fill().fill_id,),
        market_fee_rule_id="fee-rule:binance-usdm-v1",
        account_fee_schedule_id=None,
        tax_rule_id=None,
        amount=Money(125_020, Scale(2), "USDT"),
        assessment_time=UtcInstant(121),
    )
    assert len(assessment.basis_ids) == 1
    assert assessment.basis_ids[0] == fill().fill_id

    with pytest.raises(ValueError, match="basis type"):
        replace(
            assessment,
            basis_type=FeeBasisType.SESSION,
            basis_ids=(fill().fill_id,),
        )
    with pytest.raises(ValueError, match="duplicate"):
        replace(assessment, basis_ids=(fill().fill_id, fill().fill_id))
    with pytest.raises(ValueError, match="rule identity"):
        replace(assessment, market_fee_rule_id=None)

    session_fee = replace(
        assessment,
        basis_type=FeeBasisType.SESSION,
        basis_ids=(SessionId("xshg", "2026-08-03"),),
    )
    assert session_fee.basis_type is FeeBasisType.SESSION


def test_settlement_obligation_has_exactly_one_typed_nonzero_leg() -> None:
    obligation = SettlementObligation(
        settlement_obligation_id=domain_id(DomainIdKind.SETTLEMENT, "4"),
        source_fill_id=fill().fill_id,
        trade_time=UtcInstant(120),
        settlement_time=UtcInstant(120),
        instrument_id=instrument(),
        quantity=quantity(50_000_000),
        currency_id=None,
        amount=None,
    )
    assert obligation.quantity is not None

    cash_obligation = SettlementObligation(
        settlement_obligation_id=domain_id(DomainIdKind.SETTLEMENT, "5"),
        source_fill_id=fill().fill_id,
        trade_time=UtcInstant(120),
        settlement_time=UtcInstant(120),
        instrument_id=None,
        quantity=None,
        currency_id=CurrencyId("USDT"),
        amount=Money(-312_550_000, Scale(2), "USDT"),
    )
    assert cash_obligation.amount is not None

    with pytest.raises(ValueError, match="exactly one"):
        replace(
            obligation,
            currency_id=CurrencyId("USDT"),
            amount=Money(-312_550_000, Scale(2), "USDT"),
        )
    with pytest.raises(ValueError, match="identity mismatch"):
        replace(obligation, quantity=Quantity(1, Scale(8), "other"))
    with pytest.raises(ValueError, match="identity mismatch"):
        replace(cash_obligation, amount=Money(-1, Scale(2), "USD"))
    with pytest.raises(ValueError, match="non-zero"):
        replace(obligation, quantity=quantity(0))
    with pytest.raises(ValueError, match="settlement_time"):
        replace(obligation, settlement_time=UtcInstant(119))


def test_translation_report_cannot_hide_unsupported_semantics() -> None:
    mapping = TranslationFieldMapping(
        canonical_field="time_in_force",
        canonical_value="gtx",
        target_field="timeInForce",
        target_value="GTX",
    )
    translated = OrderTranslationReport(
        report_id="translation:order-1",
        order_id=order().order_id,
        translator_key="binance-usdm.v1",
        translator_version="1",
        target_profile_id="execution-account:binance-usdm-v1",
        status=TranslationStatus.TRANSLATED,
        unsupported_capabilities=(),
        field_mappings=(mapping,),
        translation_time=UtcInstant(105),
    )
    assert len(translated.field_mappings) == 1
    assert translated.field_mappings[0] == mapping

    unsupported = UnsupportedCapability(
        capability="time_in_force",
        requested_value="gtx",
        reason_code="post_only_not_supported",
    )
    with pytest.raises(ValueError, match="translated"):
        replace(translated, unsupported_capabilities=(unsupported,))
    with pytest.raises(ValueError, match="rejected"):
        replace(
            translated,
            status=TranslationStatus.REJECTED,
            field_mappings=(),
        )
    with pytest.raises(ValueError, match="duplicate canonical field"):
        replace(translated, field_mappings=(mapping, mapping))
