from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from crypto_quant_domain import (
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
    canonical_sha256,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/domain/order-execution-contracts-v1.json"


def load_fixture() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))


def domain_id(kind: DomainIdKind, digit: str) -> DomainId:
    return DomainId(kind, f"{kind.prefix}_{digit * 64}")


def instrument() -> InstrumentId:
    return InstrumentId(VenueId("binance_usdm"), "linear_perpetual:btc-usdt")


def quantity(units: int) -> Quantity:
    return Quantity(units, Scale(8), str(instrument()))


def price(units: int) -> Price:
    return Price(units, Scale(2), str(instrument()), "USDT")


def simulation_instant(nanoseconds: int, sequence: int) -> SimulationInstant:
    return SimulationInstant(
        UtcInstant(nanoseconds), TimelinePhase(30, "order"), SourceSequence(sequence)
    )


def build_order() -> Order:
    return Order(
        order_id=domain_id(DomainIdKind.ORDER, "1"),
        account_id="account:primary",
        intent=OrderIntent(
            instrument_id=instrument(),
            side=OrderSide.BUY,
            quantity=quantity(125_000_000),
            execution_style=ExecutionStyle.LIMIT,
            price_constraint=PriceConstraint(limit_price=price(6_250_000)),
            time_in_force=TimeInForce.GTX,
            reduce_only=False,
            position_effect=PositionEffect.OPEN,
            urgency="normal",
            reason="scheduled rebalance",
            parent_id="target:batch-100",
        ),
        created_at=simulation_instant(100, 1),
    )


def build_fill(fill_id: DomainId, quantity_units: int, time: int) -> Fill:
    return Fill(
        fill_id=fill_id,
        order_id=build_order().order_id,
        account_id="account:primary",
        venue_id=VenueId("binance_usdm"),
        instrument_id=instrument(),
        side=OrderSide.BUY,
        quantity=quantity(quantity_units),
        reference_price=price(6_250_000),
        reference_price_purpose="execution_reference",
        price=price(6_251_000),
        slippage_amount=Money(500_000, Scale(2), "USDT"),
        slippage_decision_id=f"slippage:{fill_id.value[-1]}",
        slippage_model_key="slippage.zero-or-fixed.v1",
        slippage_calibration_id=None,
        liquidity="taker",
        execution_time=UtcInstant(time),
    )


def build_objects() -> dict[str, object]:
    order = build_order()
    first_fill = build_fill(domain_id(DomainIdKind.FILL, "2"), 50_000_000, 120)
    second_fill = build_fill(domain_id(DomainIdKind.FILL, "5"), 75_000_000, 130)
    mapping_style = TranslationFieldMapping(
        canonical_field="execution_style",
        canonical_value="limit",
        target_field="type",
        target_value="LIMIT",
    )
    mapping_tif = TranslationFieldMapping(
        canonical_field="time_in_force",
        canonical_value="gtx",
        target_field="timeInForce",
        target_value="GTX",
    )
    unsupported_style = UnsupportedCapability(
        capability="execution_style",
        requested_value="stop_limit",
        reason_code="style_not_supported",
    )
    unsupported_tif = UnsupportedCapability(
        capability="time_in_force",
        requested_value="gtx",
        reason_code="post_only_not_supported",
    )

    return {
        "order": order,
        "fill_event": OrderEvent(
            event_id="event:partial-1",
            order_id=order.order_id,
            causation_id="event:accepted-1",
            event_type=OrderEventType.ORDER_PARTIALLY_FILLED,
            occurred_at=simulation_instant(120, 2),
            fill_id=first_fill.fill_id,
        ),
        "partial_order_state": OrderState(
            order_id=order.order_id,
            status=OrderStatus.PARTIALLY_FILLED,
            ordered_quantity=quantity(125_000_000),
            cumulative_filled_quantity=quantity(50_000_000),
            remaining_quantity=quantity(75_000_000),
            last_event_id="event:partial-1",
            updated_at=simulation_instant(120, 2),
        ),
        "fill": first_fill,
        "multi_fill_fee_assessment": FeeAssessment(
            fee_assessment_id=domain_id(DomainIdKind.FEE, "3"),
            basis_type=FeeBasisType.FILL,
            basis_ids=(second_fill.fill_id, first_fill.fill_id),
            market_fee_rule_id="fee-rule:binance-usdm-v1",
            account_fee_schedule_id=None,
            tax_rule_id=None,
            amount=Money(312_550, Scale(2), "USDT"),
            assessment_time=UtcInstant(131),
        ),
        "instrument_settlement": SettlementObligation(
            settlement_obligation_id=domain_id(DomainIdKind.SETTLEMENT, "4"),
            source_fill_id=first_fill.fill_id,
            trade_time=UtcInstant(120),
            settlement_time=UtcInstant(120),
            instrument_id=instrument(),
            quantity=quantity(50_000_000),
            currency_id=None,
            amount=None,
        ),
        "translated_report": OrderTranslationReport(
            report_id="translation:order-1",
            order_id=order.order_id,
            translator_key="binance-usdm.v1",
            translator_version="1",
            target_profile_id="execution-account:binance-usdm-v1",
            status=TranslationStatus.TRANSLATED,
            unsupported_capabilities=(),
            field_mappings=(mapping_tif, mapping_style),
            translation_time=UtcInstant(105),
        ),
        "rejected_report": OrderTranslationReport(
            report_id="translation:order-2",
            order_id=order.order_id,
            translator_key="cash-equity.v1",
            translator_version="1",
            target_profile_id="execution-account:cash-equity-v1",
            status=TranslationStatus.REJECTED,
            unsupported_capabilities=(unsupported_tif, unsupported_style),
            field_mappings=(),
            translation_time=UtcInstant(105),
        ),
    }


def test_order_execution_objects_match_golden_hashes() -> None:
    expected = load_fixture()["expected_sha256"]
    actual = {name: canonical_sha256(value) for name, value in build_objects().items()}
    assert actual == expected


def test_set_like_translation_and_fee_inputs_have_order_independent_hashes() -> None:
    objects = build_objects()
    fee = cast(FeeAssessment, objects["multi_fill_fee_assessment"])
    translated = cast(OrderTranslationReport, objects["translated_report"])
    rejected = cast(OrderTranslationReport, objects["rejected_report"])

    reversed_fee = FeeAssessment(
        fee.fee_assessment_id,
        fee.basis_type,
        tuple(reversed(fee.basis_ids)),
        fee.market_fee_rule_id,
        fee.account_fee_schedule_id,
        fee.tax_rule_id,
        fee.amount,
        fee.assessment_time,
    )
    reversed_translated = OrderTranslationReport(
        translated.report_id,
        translated.order_id,
        translated.translator_key,
        translated.translator_version,
        translated.target_profile_id,
        translated.status,
        translated.unsupported_capabilities,
        tuple(reversed(translated.field_mappings)),
        translated.translation_time,
    )
    reversed_rejected = OrderTranslationReport(
        rejected.report_id,
        rejected.order_id,
        rejected.translator_key,
        rejected.translator_version,
        rejected.target_profile_id,
        rejected.status,
        tuple(reversed(rejected.unsupported_capabilities)),
        rejected.field_mappings,
        rejected.translation_time,
    )

    assert canonical_sha256(reversed_fee) == canonical_sha256(fee)
    assert canonical_sha256(reversed_translated) == canonical_sha256(translated)
    assert canonical_sha256(reversed_rejected) == canonical_sha256(rejected)
