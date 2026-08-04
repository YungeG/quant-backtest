from __future__ import annotations

from enum import Enum


class RoundingPolicy(str, Enum):
    TOWARD_ZERO = "toward_zero"
    AWAY_FROM_ZERO = "away_from_zero"
    FLOOR = "floor"
    CEILING = "ceiling"
    HALF_EVEN = "half_even"
    HALF_UP = "half_up"


def round_ratio(
    numerator: int, denominator: int, rounding: RoundingPolicy
) -> int:
    """Round an exact integer ratio without passing through float or Decimal."""

    if not isinstance(rounding, RoundingPolicy):
        raise TypeError("rounding must be a RoundingPolicy")
    if denominator == 0:
        raise ZeroDivisionError("division by zero")
    if denominator < 0:
        numerator = -numerator
        denominator = -denominator

    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), denominator)
    truncated = sign * quotient
    if remainder == 0:
        return truncated
    if rounding is RoundingPolicy.TOWARD_ZERO:
        return truncated
    if rounding is RoundingPolicy.AWAY_FROM_ZERO:
        return sign * (quotient + 1)
    if rounding is RoundingPolicy.FLOOR:
        return truncated - 1 if sign < 0 else truncated
    if rounding is RoundingPolicy.CEILING:
        return truncated + 1 if sign > 0 else truncated

    doubled = remainder * 2
    if doubled < denominator:
        rounded_magnitude = quotient
    elif doubled > denominator:
        rounded_magnitude = quotient + 1
    elif rounding is RoundingPolicy.HALF_EVEN:
        rounded_magnitude = quotient if quotient % 2 == 0 else quotient + 1
    elif rounding is RoundingPolicy.HALF_UP:
        rounded_magnitude = quotient + 1
    else:  # pragma: no cover - enum exhaustiveness guard
        raise AssertionError(f"Unhandled rounding policy: {rounding}")
    return sign * rounded_magnitude
