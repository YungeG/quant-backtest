"""Framework-independent trading domain contracts."""

from .numeric import (
    ExposureFraction,
    Money,
    Price,
    Quantity,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
)

__version__ = "0.1.0"

__all__ = [
    "ExposureFraction",
    "Money",
    "Price",
    "Quantity",
    "QuantizationPolicy",
    "Rate",
    "RoundingPolicy",
    "Scale",
]
