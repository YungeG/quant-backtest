from __future__ import annotations

from decimal import Decimal

import pytest

from crypto_quant_domain import (
    Money,
    QuantizationPolicy,
    RoundingPolicy,
    Scale,
)


def test_decimal_quantization_is_versioned_and_rounding_explicit() -> None:
    half_even = QuantizationPolicy(
        version="analytics-money-v1",
        target_scale=Scale(2),
        rounding=RoundingPolicy.HALF_EVEN,
    )
    half_up = QuantizationPolicy(
        version="analytics-money-v1-half-up",
        target_scale=Scale(2),
        rounding=RoundingPolicy.HALF_UP,
    )

    assert Money.from_decimal(
        Decimal("1.225"), currency="USD", policy=half_even
    ).units == 122
    assert Money.from_decimal(
        "1.225", currency="USD", policy=half_up
    ).units == 123


def test_float_can_enter_only_through_quantization_policy() -> None:
    policy = QuantizationPolicy(
        version="analytics-float-v1",
        target_scale=Scale(4),
        rounding=RoundingPolicy.HALF_EVEN,
    )

    value = Money.from_float(0.1, currency="USD", policy=policy)

    assert value == Money(units=1000, scale=Scale(4), currency="USD")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_float_is_rejected(value: float) -> None:
    policy = QuantizationPolicy(
        version="analytics-float-v1",
        target_scale=Scale(4),
        rounding=RoundingPolicy.HALF_EVEN,
    )

    with pytest.raises(ValueError, match="finite"):
        Money.from_float(value, currency="USD", policy=policy)


def test_quantization_policy_requires_version() -> None:
    with pytest.raises(ValueError, match="version"):
        QuantizationPolicy(
            version="",
            target_scale=Scale(2),
            rounding=RoundingPolicy.HALF_EVEN,
        )
