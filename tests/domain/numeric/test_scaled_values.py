from __future__ import annotations

import json

import pytest

from crypto_quant_domain import (
    ExposureFraction,
    Money,
    Price,
    Quantity,
    Rate,
    RoundingPolicy,
    Scale,
)


def test_same_type_identity_and_scale_can_add() -> None:
    left = Money(units=125, scale=Scale(2), currency="USD")
    right = Money(units=-25, scale=Scale(2), currency="USD")

    assert left + right == Money(units=100, scale=Scale(2), currency="USD")


def test_cross_domain_identity_and_scale_arithmetic_is_rejected() -> None:
    money = Money(units=100, scale=Scale(2), currency="USD")

    with pytest.raises(TypeError, match="domain type"):
        _ = money + Quantity(units=100, scale=Scale(2), instrument_id="BTC-USDT")  # type: ignore[operator]
    with pytest.raises(ValueError, match="identity"):
        _ = money + Money(units=100, scale=Scale(2), currency="CNY")
    with pytest.raises(ValueError, match="scale"):
        _ = money + Money(units=1000, scale=Scale(3), currency="USD")


def test_price_and_quantity_materialize_quote_currency_notional() -> None:
    price = Price(
        units=12345,
        scale=Scale(2),
        instrument_id="BTC-USDT",
        quote_currency="USDT",
    )
    quantity = Quantity(
        units=200000000,
        scale=Scale(8),
        instrument_id="BTC-USDT",
    )

    notional = price.notional(
        quantity,
        result_scale=Scale(2),
        rounding=RoundingPolicy.HALF_EVEN,
    )

    assert notional == Money(units=24690, scale=Scale(2), currency="USDT")
    assert notional.quantity_at(
        price,
        result_scale=Scale(8),
        rounding=RoundingPolicy.HALF_EVEN,
    ) == quantity


def test_product_supports_two_max_scale_operands_without_intermediate_scale() -> None:
    price = Price(
        units=10**18,
        scale=Scale(18),
        instrument_id="TOKEN-USD",
        quote_currency="USD",
    )
    quantity = Quantity(
        units=10**18,
        scale=Scale(18),
        instrument_id="TOKEN-USD",
    )

    assert price.notional(
        quantity,
        result_scale=Scale(18),
        rounding=RoundingPolicy.HALF_EVEN,
    ) == Money(units=10**18, scale=Scale(18), currency="USD")


def test_cross_type_multiplication_rejects_instrument_or_currency_mismatch() -> None:
    price = Price(
        units=100,
        scale=Scale(2),
        instrument_id="BTC-USDT",
        quote_currency="USDT",
    )
    other_quantity = Quantity(
        units=1, scale=Scale(0), instrument_id="ETH-USDT"
    )

    with pytest.raises(ValueError, match="instrument"):
        price.notional(
            other_quantity,
            result_scale=Scale(2),
            rounding=RoundingPolicy.TOWARD_ZERO,
        )
    with pytest.raises(ValueError, match="currency"):
        Money(units=100, scale=Scale(2), currency="USD").quantity_at(
            price,
            result_scale=Scale(8),
            rounding=RoundingPolicy.TOWARD_ZERO,
        )


def test_rate_application_and_division_require_explicit_result_scale() -> None:
    money = Money(units=10000, scale=Scale(2), currency="USD")
    rate = Rate(units=125, scale=Scale(3), basis="fraction")

    changed = money.multiply_by_rate(
        rate,
        result_scale=Scale(2),
        rounding=RoundingPolicy.HALF_EVEN,
    )

    assert changed == Money(units=1250, scale=Scale(2), currency="USD")
    assert changed.divide_by_rate(
        rate,
        result_scale=Scale(2),
        rounding=RoundingPolicy.HALF_EVEN,
    ) == money


def test_canonical_values_are_typed_and_contain_no_float() -> None:
    values = [
        Money(units=123, scale=Scale(2), currency="USD"),
        Quantity(units=-5, scale=Scale(0), instrument_id="600000.XSHG"),
        Price(
            units=1001,
            scale=Scale(2),
            instrument_id="600000.XSHG",
            quote_currency="CNY",
        ),
        Rate(units=15, scale=Scale(4), basis="fraction"),
        ExposureFraction(units=-2500, scale=Scale(4)),
    ]

    encoded = json.dumps([value.to_canonical_dict() for value in values])

    assert ".0" not in encoded
    assert all(isinstance(value.units, int) for value in values)
    assert values[0].to_canonical_dict() == {
        "type": "money",
        "units": 123,
        "scale": 2,
        "currency": "USD",
    }


def test_units_scale_and_identity_validate_fail_closed() -> None:
    with pytest.raises(TypeError, match="integer"):
        Money(units=1.0, scale=Scale(2), currency="USD")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="integer"):
        Money(units=True, scale=Scale(2), currency="USD")
    with pytest.raises(ValueError, match="Scale"):
        Scale(19)
    with pytest.raises(ValueError, match="identity"):
        Quantity(units=1, scale=Scale(0), instrument_id="")
