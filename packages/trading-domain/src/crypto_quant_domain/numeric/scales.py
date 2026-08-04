from __future__ import annotations

from dataclasses import dataclass


MAX_SCALE_PLACES = 18


@dataclass(frozen=True, slots=True)
class Scale:
    """A decimal fixed-point scale expressed as fractional places."""

    places: int

    def __post_init__(self) -> None:
        if isinstance(self.places, bool) or not isinstance(self.places, int):
            raise TypeError("Scale places must be an integer")
        if not 0 <= self.places <= MAX_SCALE_PLACES:
            raise ValueError(f"Scale places must be between 0 and {MAX_SCALE_PLACES}")

    @property
    def factor(self) -> int:
        return 10**self.places

    def __int__(self) -> int:
        return self.places
