from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import (
    ExecutionStyle,
    InstrumentId,
    PositionEffect,
    Scale,
    TimeInForce,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading import MarketSessionState, PriceConstraintShape
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmDeferredRuleKey,
    BinanceUsdmInstrumentModel,
    BinanceUsdmOrderAdmissionMode,
    BinanceUsdmOrderRuleFailureCode,
    BinanceUsdmOrderRuleModel,
    BinanceUsdmOrderRuleQuery,
    BinanceUsdmOrderRuleSourceRef,
)
from tests.profiles.binance_usdm._fixtures import (
    query as instrument_query,
    revision,
)
from tests.profiles.binance_usdm._order_rule_fixtures import (
    DELIST_AT,
    ONBOARD_AT,
    RENAME_AT,
    REQUIRED_FILTERS,
    SESSION_ID,
    band,
    complete_bands,
    order_rule_query,
    rule_book,
)


def _failure_code(query: BinanceUsdmOrderRuleQuery):
    outcome = BinanceUsdmOrderRuleModel().resolve_order_rules(query)
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.failure_hash == canonical_sha256(outcome.failure)
    return outcome.failure.code


def test_resolves_point_in_time_limit_market_rules_and_capabilities() -> None:
    first, second = complete_bands()
    model = BinanceUsdmOrderRuleModel()

    outcome = model.resolve_order_rules(order_rule_query(second, first))

    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert result.active_band == second
    assert result.visible_bands == (first, second)
    assert result.price_scale == Scale(2)
    assert result.quantity_scale == Scale(3)
    assert result.limit_quantity_lattice.step_units == 1
    assert result.market_quantity_lattice.step_units == 5
    assert result.active_snapshot.quantity_lattice == result.limit_quantity_lattice
    assert (
        result.active_snapshot.market_quantity_lattice
        == result.market_quantity_lattice
    )
    assert result.active_snapshot.max_limit_order_quantity_units == 100_000
    assert result.active_snapshot.max_market_order_quantity_units == 50_000
    assert result.active_snapshot.config_payload()["schema_version"] == 3
    assert len(result.rule_timeline.intervals) == 2
    assert result.rule_timeline.active_intervals(RENAME_AT)[0].snapshot == (
        result.active_snapshot
    )
    styles = {
        value.execution_style: value for value in result.order_capabilities.style_capabilities
    }
    assert list(styles[ExecutionStyle.LIMIT].price_constraint_shapes) == [
        PriceConstraintShape.LIMIT
    ]
    assert list(styles[ExecutionStyle.LIMIT].time_in_forces) == [
        TimeInForce.FOK,
        TimeInForce.GTC,
        TimeInForce.GTX,
        TimeInForce.IOC,
    ]
    assert styles[ExecutionStyle.MARKET].price_constraint_shapes == (
        PriceConstraintShape.NONE,
    )
    assert styles[ExecutionStyle.MARKET].time_in_forces == (TimeInForce.IOC,)
    assert result.deferred_rule_keys == ()
    assert result.decision_grade_eligible
    assert result.resolution_hash == canonical_sha256(result)


def test_admission_modes_map_without_account_or_current_rule_fallback() -> None:
    first, normal = complete_bands()
    _, reduce_only = complete_bands(
        second_admission=BinanceUsdmOrderAdmissionMode.REDUCE_ONLY
    )
    _, closed = complete_bands(
        second_admission=BinanceUsdmOrderAdmissionMode.CLOSED
    )
    model = BinanceUsdmOrderRuleModel()

    normal_result = model.resolve_order_rules(order_rule_query(first, normal)).result
    reduce_result = model.resolve_order_rules(
        order_rule_query(first, reduce_only)
    ).result
    closed_result = model.resolve_order_rules(order_rule_query(first, closed)).result
    halted_closed = model.resolve_order_rules(
        order_rule_query(first, closed, metadata_status="TRADING_HALT")
    ).result

    assert normal_result is not None
    assert normal_result.active_snapshot.session_state is MarketSessionState.OPEN
    assert list(normal_result.active_snapshot.permitted_position_effects) == [
        PositionEffect.AUTO,
        PositionEffect.CLOSE,
        PositionEffect.OPEN,
    ]
    assert not normal_result.active_snapshot.reduce_only_required
    assert reduce_result is not None
    assert reduce_result.active_snapshot.session_state is MarketSessionState.OPEN
    assert reduce_result.active_snapshot.permitted_position_effects == (
        PositionEffect.CLOSE,
    )
    assert reduce_result.active_snapshot.reduce_only_required
    assert closed_result is not None
    assert closed_result.active_snapshot.session_state is MarketSessionState.SUSPENDED
    assert closed_result.active_snapshot.permitted_sides == ()
    assert halted_closed is not None
    assert halted_closed.active_band.admission_mode is BinanceUsdmOrderAdmissionMode.CLOSED


def test_deferred_rules_are_preserved_and_force_development_grade() -> None:
    first, second = complete_bands(
        second_deferred=(
            BinanceUsdmDeferredRuleKey.PERCENT_PRICE.value,
            BinanceUsdmDeferredRuleKey.TRIGGER_PROTECT.value,
        )
    )

    outcome = BinanceUsdmOrderRuleModel().resolve_order_rules(
        order_rule_query(first, second)
    )

    assert outcome.result is not None
    assert list(outcome.result.deferred_rule_keys) == [
        BinanceUsdmDeferredRuleKey.PERCENT_PRICE,
        BinanceUsdmDeferredRuleKey.TRIGGER_PROTECT,
    ]
    assert not outcome.result.decision_grade_eligible

    historical = replace(
        first,
        deferred_rule_keys=(BinanceUsdmDeferredRuleKey.MAX_NUM_ORDERS.value,),
    )
    full_visible = BinanceUsdmOrderRuleModel().resolve_order_rules(
        order_rule_query(historical, second)
    ).result
    assert full_visible is not None
    assert full_visible.active_deferred_rule_keys == (
        BinanceUsdmDeferredRuleKey.PERCENT_PRICE,
        BinanceUsdmDeferredRuleKey.TRIGGER_PROTECT,
    )
    assert list(full_visible.deferred_rule_keys) == [
        BinanceUsdmDeferredRuleKey.MAX_NUM_ORDERS,
        BinanceUsdmDeferredRuleKey.PERCENT_PRICE,
        BinanceUsdmDeferredRuleKey.TRIGGER_PROTECT,
    ]
    assert not full_visible.decision_grade_eligible


def test_captured_at_never_falls_back_to_a_current_rule_band() -> None:
    late = UtcInstant(RENAME_AT.epoch_nanoseconds + 100)
    first, second = complete_bands(second_available_at=late)
    before = order_rule_query(first, second)
    after = order_rule_query(
        first,
        second,
        captured_at=UtcInstant(late.epoch_nanoseconds + 1),
    )
    model = BinanceUsdmOrderRuleModel()

    unavailable = model.resolve_order_rules(before)
    available = model.resolve_order_rules(after)

    assert unavailable.failure is not None
    assert unavailable.failure.code is (
        BinanceUsdmOrderRuleFailureCode.MISSING_RULE_INTERVAL
    )
    assert available.result is not None
    assert available.result.active_band == second


@pytest.mark.parametrize(
    ("query_value", "expected"),
    (
        (
            order_rule_query(),
            BinanceUsdmOrderRuleFailureCode.MISSING_RULE_BANDS,
        ),
        (
            replace(
                order_rule_query(*complete_bands()),
                evaluated_at=UtcInstant(RENAME_AT.epoch_nanoseconds + 11),
            ),
            BinanceUsdmOrderRuleFailureCode.INSTRUMENT_METADATA_MISMATCH,
        ),
        (
            order_rule_query(
                *(
                    replace(
                        value,
                        available_at=UtcInstant(DELIST_AT.epoch_nanoseconds + 10),
                    )
                    for value in complete_bands()
                )
            ),
            BinanceUsdmOrderRuleFailureCode.RULE_NOT_AVAILABLE,
        ),
        (
            order_rule_query(
                band(
                    effective_to_exclusive=UtcInstant(
                        RENAME_AT.epoch_nanoseconds - 1
                    )
                ),
                complete_bands()[1],
            ),
            BinanceUsdmOrderRuleFailureCode.MISSING_RULE_INTERVAL,
        ),
        (
            order_rule_query(
                band(
                    effective_to_exclusive=UtcInstant(
                        RENAME_AT.epoch_nanoseconds + 1
                    )
                ),
                complete_bands()[1],
            ),
            BinanceUsdmOrderRuleFailureCode.OVERLAPPING_RULE_INTERVALS,
        ),
        (
            order_rule_query(
                *complete_bands()[:-1],
                replace(
                    complete_bands()[1],
                    filter_keys=tuple(
                        value for value in REQUIRED_FILTERS if value != "MIN_NOTIONAL"
                    ),
                ),
            ),
            BinanceUsdmOrderRuleFailureCode.MISSING_REQUIRED_FILTER,
        ),
        (
            order_rule_query(
                complete_bands()[0],
                replace(
                    complete_bands()[1],
                    filter_keys=(*REQUIRED_FILTERS, "MAGIC_FILTER"),
                ),
            ),
            BinanceUsdmOrderRuleFailureCode.UNSUPPORTED_FILTER,
        ),
        (
            order_rule_query(
                complete_bands()[0],
                replace(complete_bands()[1], tick_size="1e-3"),
            ),
            BinanceUsdmOrderRuleFailureCode.INVALID_DECIMAL_FIELD,
        ),
        (
            order_rule_query(
                complete_bands()[0],
                replace(complete_bands()[1], min_notional="5.000001"),
            ),
            BinanceUsdmOrderRuleFailureCode.INVALID_DECIMAL_FIELD,
        ),
        (
            order_rule_query(
                complete_bands()[0],
                replace(complete_bands()[1], min_price="0.015", tick_size="0.01"),
            ),
            BinanceUsdmOrderRuleFailureCode.INVALID_FILTER_GEOMETRY,
        ),
        (
            order_rule_query(
                complete_bands()[0],
                replace(complete_bands()[1], time_in_forces=("GTC", "RPI")),
            ),
            BinanceUsdmOrderRuleFailureCode.UNSUPPORTED_ORDER_CAPABILITY,
        ),
        (
            order_rule_query(
                complete_bands()[0],
                replace(
                    complete_bands()[1],
                    admission_mode=BinanceUsdmOrderAdmissionMode.REDUCE_ONLY,
                    supports_reduce_only=False,
                ),
            ),
            BinanceUsdmOrderRuleFailureCode.UNSUPPORTED_ORDER_CAPABILITY,
        ),
        (
            order_rule_query(*complete_bands(), metadata_status="TRADING_HALT"),
            BinanceUsdmOrderRuleFailureCode.ADMISSION_STATUS_CONFLICT,
        ),
        (
            order_rule_query(
                complete_bands()[0],
                replace(
                    complete_bands()[1],
                    source_ref=BinanceUsdmOrderRuleSourceRef(
                        source_key=complete_bands()[0].source_ref.source_key,
                        source_hash="sha256:" + "f" * 64,
                    ),
                ),
            ),
            BinanceUsdmOrderRuleFailureCode.METADATA_CONFLICT,
        ),
    ),
)
def test_failure_precedence_is_structured(query_value, expected) -> None:
    assert _failure_code(query_value) is expected


def test_constructor_revalidation_rejects_forged_resolution_and_failure() -> None:
    first, second = complete_bands()
    model = BinanceUsdmOrderRuleModel()
    success = model.resolve_order_rules(order_rule_query(first, second))
    assert success.result is not None
    failure = model.resolve_order_rules(order_rule_query())
    assert failure.failure is not None

    with pytest.raises(ValueError, match="embedded query"):
        replace(success.result, active_band=first)
    with pytest.raises(ValueError, match="embedded query"):
        replace(success.result, decision_grade_eligible=False)
    with pytest.raises(ValueError, match="embedded query"):
        replace(failure.failure, message="forged")


def test_rule_band_input_order_is_canonical_and_identity_is_not_guessed() -> None:
    first, second = complete_bands()
    forward = order_rule_query(first, second)
    reverse = order_rule_query(second, first)
    model = BinanceUsdmOrderRuleModel()

    assert forward == reverse
    assert forward.query_hash == reverse.query_hash
    assert model.resolve_order_rules(forward) == model.resolve_order_rules(reverse)

    other_instrument = InstrumentId(VenueId("binance_usdm"), "other-perpetual")
    mismatched = replace(second, instrument_id=other_instrument)
    outcome = model.resolve_order_rules(order_rule_query(first, mismatched))
    assert outcome.failure is not None
    assert outcome.failure.code is BinanceUsdmOrderRuleFailureCode.METADATA_CONFLICT


def test_query_rejects_forged_g10a_resolution() -> None:
    metadata = BinanceUsdmInstrumentModel().resolve_instrument(
        instrument_query(revision())
    ).result
    assert metadata is not None
    with pytest.raises(ValueError):
        replace(metadata, active_symbol="FORGED")
    assert SESSION_ID.calendar_id == "binance_usdm"
    assert ONBOARD_AT < RENAME_AT < DELIST_AT
