from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any, ClassVar, Self

from .quantization import QuantizationPolicy
from .rounding import RoundingPolicy, round_ratio
from .scales import Scale


def require_identity(name: str, value: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise ValueError(f"{name} identity must be non-empty canonical text")


def rescale_from_places(
    units: int,
    source_places: int,
    target_scale: Scale,
    rounding: RoundingPolicy,
) -> int:
    if not isinstance(rounding, RoundingPolicy):
        raise TypeError("rounding must be a RoundingPolicy")
    difference = target_scale.places - source_places
    if difference >= 0:
        return units * 10**difference
    return round_ratio(units, 10 ** (-difference), rounding)


def product_units(
    left_units: int,
    left_scale: Scale,
    right_units: int,
    right_scale: Scale,
    result_scale: Scale,
    rounding: RoundingPolicy,
) -> int:
    source_places = left_scale.places + right_scale.places
    return rescale_from_places(
        left_units * right_units, source_places, result_scale, rounding
    )


def quotient_units(
    numerator_units: int,
    numerator_scale: Scale,
    denominator_units: int,
    denominator_scale: Scale,
    result_scale: Scale,
    rounding: RoundingPolicy,
) -> int:
    if denominator_units == 0:
        raise ZeroDivisionError("division by zero")
    numerator = numerator_units * 10 ** (
        denominator_scale.places + result_scale.places
    )
    denominator = denominator_units * 10**numerator_scale.places
    return round_ratio(numerator, denominator, rounding)


@dataclass(frozen=True, slots=True)
class _ScaledValue:
    units: int
    scale: Scale

    DOMAIN_TYPE: ClassVar[str] = "scaled_value"

    def __post_init__(self) -> None:
        if isinstance(self.units, bool) or not isinstance(self.units, int):
            raise TypeError("units must be an integer")
        if not isinstance(self.scale, Scale):
            raise TypeError("scale must be a Scale")

    def _identity(self) -> tuple[str, ...]:
        return ()

    def _canonical_identity(self) -> dict[str, str]:
        return {}

    def _assert_compatible(self, other: object) -> _ScaledValue:
        if type(self) is not type(other):
            raise TypeError("scaled arithmetic requires the same domain type")
        assert isinstance(other, _ScaledValue)
        if self._identity() != other._identity():
            raise ValueError("scaled arithmetic identity mismatch")
        if self.scale != other.scale:
            raise ValueError("scaled arithmetic scale mismatch")
        return other

    def __add__(self, other: object) -> Self:
        compatible = self._assert_compatible(other)
        return replace(self, units=self.units + compatible.units)

    def __sub__(self, other: object) -> Self:
        compatible = self._assert_compatible(other)
        return replace(self, units=self.units - compatible.units)

    def __neg__(self) -> Self:
        return replace(self, units=-self.units)

    def rescale(self, target_scale: Scale, rounding: RoundingPolicy) -> Self:
        if not isinstance(target_scale, Scale):
            raise TypeError("target_scale must be a Scale")
        return replace(
            self,
            units=rescale_from_places(
                self.units, self.scale.places, target_scale, rounding
            ),
            scale=target_scale,
        )

    def multiply_by_rate(
        self,
        rate: Rate,
        *,
        result_scale: Scale,
        rounding: RoundingPolicy,
    ) -> Self:
        if not isinstance(rate, Rate):
            raise TypeError("rate must be a Rate")
        return replace(
            self,
            units=product_units(
                self.units,
                self.scale,
                rate.units,
                rate.scale,
                result_scale,
                rounding,
            ),
            scale=result_scale,
        )

    def divide_by_rate(
        self,
        rate: Rate,
        *,
        result_scale: Scale,
        rounding: RoundingPolicy,
    ) -> Self:
        if not isinstance(rate, Rate):
            raise TypeError("rate must be a Rate")
        return replace(
            self,
            units=quotient_units(
                self.units,
                self.scale,
                rate.units,
                rate.scale,
                result_scale,
                rounding,
            ),
            scale=result_scale,
        )

    @classmethod
    def from_decimal(
        cls,
        value: Decimal | str,
        *,
        policy: QuantizationPolicy,
        **identity: str,
    ) -> Self:
        if not isinstance(policy, QuantizationPolicy):
            raise TypeError("policy must be a QuantizationPolicy")
        return cls(
            units=policy.quantize_decimal(value),
            scale=policy.target_scale,
            **identity,
        )

    @classmethod
    def from_float(
        cls,
        value: float,
        *,
        policy: QuantizationPolicy,
        **identity: str,
    ) -> Self:
        if not isinstance(policy, QuantizationPolicy):
            raise TypeError("policy must be a QuantizationPolicy")
        return cls(
            units=policy.quantize_float(value),
            scale=policy.target_scale,
            **identity,
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": self.DOMAIN_TYPE,
            "units": self.units,
            "scale": self.scale.places,
            **self._canonical_identity(),
        }


@dataclass(frozen=True, slots=True)
class Money(_ScaledValue):
    currency: str

    DOMAIN_TYPE: ClassVar[str] = "money"

    def __post_init__(self) -> None:
        _ScaledValue.__post_init__(self)
        require_identity("currency", self.currency)

    def _identity(self) -> tuple[str, ...]:
        return (self.currency,)

    def _canonical_identity(self) -> dict[str, str]:
        return {"currency": self.currency}

    def quantity_at(
        self,
        price: Price,
        *,
        result_scale: Scale,
        rounding: RoundingPolicy,
    ) -> Quantity:
        if not isinstance(price, Price):
            raise TypeError("price must be a Price")
        if self.currency != price.quote_currency:
            raise ValueError("Money currency must match Price quote currency")
        return Quantity(
            units=quotient_units(
                self.units,
                self.scale,
                price.units,
                price.scale,
                result_scale,
                rounding,
            ),
            scale=result_scale,
            instrument_id=price.instrument_id,
        )


@dataclass(frozen=True, slots=True)
class Quantity(_ScaledValue):
    instrument_id: str

    DOMAIN_TYPE: ClassVar[str] = "quantity"

    def __post_init__(self) -> None:
        _ScaledValue.__post_init__(self)
        require_identity("instrument", self.instrument_id)

    def _identity(self) -> tuple[str, ...]:
        return (self.instrument_id,)

    def _canonical_identity(self) -> dict[str, str]:
        return {"instrument_id": self.instrument_id}


@dataclass(frozen=True, slots=True)
class Price(_ScaledValue):
    instrument_id: str
    quote_currency: str

    DOMAIN_TYPE: ClassVar[str] = "price"

    def __post_init__(self) -> None:
        _ScaledValue.__post_init__(self)
        require_identity("instrument", self.instrument_id)
        require_identity("quote currency", self.quote_currency)

    def _identity(self) -> tuple[str, ...]:
        return (self.instrument_id, self.quote_currency)

    def _canonical_identity(self) -> dict[str, str]:
        return {
            "instrument_id": self.instrument_id,
            "quote_currency": self.quote_currency,
        }

    def notional(
        self,
        quantity: Quantity,
        *,
        result_scale: Scale,
        rounding: RoundingPolicy,
    ) -> Money:
        if not isinstance(quantity, Quantity):
            raise TypeError("quantity must be a Quantity")
        if self.instrument_id != quantity.instrument_id:
            raise ValueError("Price and Quantity instrument identity mismatch")
        return Money(
            units=product_units(
                self.units,
                self.scale,
                quantity.units,
                quantity.scale,
                result_scale,
                rounding,
            ),
            scale=result_scale,
            currency=self.quote_currency,
        )


@dataclass(frozen=True, slots=True)
class Rate(_ScaledValue):
    basis: str = "fraction"

    DOMAIN_TYPE: ClassVar[str] = "rate"

    def __post_init__(self) -> None:
        _ScaledValue.__post_init__(self)
        require_identity("rate basis", self.basis)

    def _identity(self) -> tuple[str, ...]:
        return (self.basis,)

    def _canonical_identity(self) -> dict[str, str]:
        return {"basis": self.basis}


@dataclass(frozen=True, slots=True)
class ExposureFraction(_ScaledValue):
    DOMAIN_TYPE: ClassVar[str] = "exposure_fraction"
