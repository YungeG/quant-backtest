from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .rounding import RoundingPolicy, round_ratio
from .scales import Scale


@dataclass(frozen=True, slots=True)
class QuantizationPolicy:
    """A versioned boundary from analytical numbers to authoritative units."""

    version: str
    target_scale: Scale
    rounding: RoundingPolicy

    def __post_init__(self) -> None:
        if (
            not isinstance(self.version, str)
            or not self.version
            or self.version != self.version.strip()
        ):
            raise ValueError("QuantizationPolicy version must be canonical non-empty text")
        if not isinstance(self.target_scale, Scale):
            raise TypeError("target_scale must be a Scale")
        if not isinstance(self.rounding, RoundingPolicy):
            raise TypeError("rounding must be a RoundingPolicy")

    def quantize_decimal(self, value: Decimal | str) -> int:
        if isinstance(value, str):
            try:
                decimal_value = Decimal(value)
            except InvalidOperation as error:
                raise ValueError("Decimal input is invalid") from error
        elif isinstance(value, Decimal):
            decimal_value = value
        else:
            raise TypeError("Decimal quantization accepts Decimal or string")
        if not decimal_value.is_finite():
            raise ValueError("Quantization input must be finite")
        numerator, denominator = decimal_value.as_integer_ratio()
        return round_ratio(
            numerator * self.target_scale.factor,
            denominator,
            self.rounding,
        )

    def quantize_float(self, value: float) -> int:
        if isinstance(value, bool) or not isinstance(value, float):
            raise TypeError("Float quantization accepts float")
        if not math.isfinite(value):
            raise ValueError("Quantization input must be finite")
        return self.quantize_decimal(Decimal(str(value)))

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "quantization_policy",
            "version": self.version,
            "target_scale": self.target_scale.places,
            "rounding": self.rounding.value,
        }
