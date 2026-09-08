from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .time import UtcInstant


_CURRENCY = re.compile(r"[A-Z][A-Z0-9._-]{0,31}\Z")
_VENUE = re.compile(r"[a-z][a-z0-9_.-]{0,63}\Z")
_STABLE_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")


@dataclass(frozen=True, slots=True, order=True)
class CurrencyId:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or _CURRENCY.fullmatch(self.value) is None:
            raise ValueError("CurrencyId must be uppercase canonical code")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {"type": "currency_id", "value": self.value}

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True, order=True)
class VenueId:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or _VENUE.fullmatch(self.value) is None:
            raise ValueError("VenueId must be lowercase canonical code")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {"type": "venue_id", "value": self.value}

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True, order=True)
class InstrumentId:
    venue: VenueId
    stable_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.venue, VenueId):
            raise TypeError("venue must be VenueId")
        if (
            not isinstance(self.stable_key, str)
            or _STABLE_KEY.fullmatch(self.stable_key) is None
        ):
            raise ValueError("InstrumentId stable_key must be canonical stable text")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "instrument_id",
            "venue": self.venue.value,
            "stable_key": self.stable_key,
        }

    def __str__(self) -> str:
        return f"{self.venue.value}:{self.stable_key}"


class InstrumentType(str, Enum):
    SPOT = "spot"
    EQUITY = "equity"
    LINEAR_PERPETUAL = "linear_perpetual"
    INVERSE_PERPETUAL = "inverse_perpetual"
    FUTURE = "future"
    OPTION = "option"
    FX = "fx"


@dataclass(frozen=True, slots=True)
class InstrumentDefinition:
    instrument_id: InstrumentId
    instrument_type: InstrumentType
    base_currency: CurrencyId | None
    quote_currency: CurrencyId
    settlement_currency: CurrencyId

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.instrument_type, InstrumentType):
            raise TypeError("instrument_type must be InstrumentType")
        if self.base_currency is not None and not isinstance(
            self.base_currency, CurrencyId
        ):
            raise TypeError("base_currency must be CurrencyId or None")
        if not isinstance(self.quote_currency, CurrencyId):
            raise TypeError("quote_currency must be CurrencyId")
        if not isinstance(self.settlement_currency, CurrencyId):
            raise TypeError("settlement_currency must be CurrencyId")

    def referenced_currencies(self) -> frozenset[CurrencyId]:
        values = {self.quote_currency, self.settlement_currency}
        if self.base_currency is not None:
            values.add(self.base_currency)
        return frozenset(values)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "instrument_definition",
            "instrument_id": self.instrument_id.to_canonical_dict(),
            "instrument_type": self.instrument_type.value,
            "base_currency": (
                self.base_currency.to_canonical_dict()
                if self.base_currency is not None
                else None
            ),
            "quote_currency": self.quote_currency.to_canonical_dict(),
            "settlement_currency": self.settlement_currency.to_canonical_dict(),
        }


@dataclass(frozen=True, slots=True)
class SymbolInterval:
    symbol: str
    effective_from: UtcInstant
    effective_until: UtcInstant | None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.symbol, str)
            or not self.symbol
            or self.symbol != self.symbol.strip()
        ):
            raise ValueError("symbol must be canonical non-empty text")
        if not isinstance(self.effective_from, UtcInstant):
            raise TypeError("effective_from must be UtcInstant")
        if self.effective_until is not None and not isinstance(
            self.effective_until, UtcInstant
        ):
            raise TypeError("effective_until must be UtcInstant or None")
        if (
            self.effective_until is not None
            and self.effective_until <= self.effective_from
        ):
            raise ValueError("effective_until must be after effective_from")

    def contains(self, instant: UtcInstant) -> bool:
        return self.effective_from <= instant and (
            self.effective_until is None or instant < self.effective_until
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "effective_from": self.effective_from.to_canonical_dict(),
            "effective_until": (
                self.effective_until.to_canonical_dict()
                if self.effective_until is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class SymbolTimeline:
    instrument_id: InstrumentId
    intervals: tuple[SymbolInterval, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.intervals, tuple) or not self.intervals:
            raise ValueError("SymbolTimeline intervals must be a non-empty tuple")
        if not all(isinstance(item, SymbolInterval) for item in self.intervals):
            raise TypeError("intervals must contain SymbolInterval")
        starts = [item.effective_from for item in self.intervals]
        if starts != sorted(starts):
            raise ValueError("SymbolTimeline intervals must be sorted")
        for previous, current in zip(self.intervals, self.intervals[1:]):
            if previous.effective_until is None or (
                current.effective_from < previous.effective_until
            ):
                raise ValueError("SymbolTimeline intervals overlap")

    def symbol_at(self, instant: UtcInstant) -> str:
        if not isinstance(instant, UtcInstant):
            raise TypeError("instant must be UtcInstant")
        for interval in self.intervals:
            if interval.contains(instant):
                return interval.symbol
        raise LookupError(f"no symbol for {self.instrument_id} at instant")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "symbol_timeline",
            "instrument_id": self.instrument_id.to_canonical_dict(),
            "intervals": [item.to_canonical_dict() for item in self.intervals],
        }


@dataclass(frozen=True, slots=True)
class InstrumentCatalog:
    currencies: tuple[CurrencyId, ...]
    instruments: tuple[InstrumentDefinition, ...]
    symbol_timelines: tuple[SymbolTimeline, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.currencies, tuple):
            raise TypeError("currencies must be a tuple")
        if not isinstance(self.instruments, tuple):
            raise TypeError("instruments must be a tuple")
        if not isinstance(self.symbol_timelines, tuple):
            raise TypeError("symbol_timelines must be a tuple")
        if not all(isinstance(item, CurrencyId) for item in self.currencies):
            raise TypeError("currencies must contain CurrencyId")
        if not all(isinstance(item, InstrumentDefinition) for item in self.instruments):
            raise TypeError("instruments must contain InstrumentDefinition")
        if not all(isinstance(item, SymbolTimeline) for item in self.symbol_timelines):
            raise TypeError("symbol_timelines must contain SymbolTimeline")
        currency_set = set(self.currencies)
        if len(currency_set) != len(self.currencies):
            raise ValueError("duplicate CurrencyId in catalog")
        instrument_ids = [item.instrument_id for item in self.instruments]
        if len(set(instrument_ids)) != len(instrument_ids):
            raise ValueError("duplicate InstrumentId in catalog")
        for definition in self.instruments:
            unknown = definition.referenced_currencies() - currency_set
            if unknown:
                raise ValueError(f"unknown CurrencyId reference: {sorted(map(str, unknown))}")
        known_instruments = set(instrument_ids)
        timeline_ids = [item.instrument_id for item in self.symbol_timelines]
        if len(set(timeline_ids)) != len(timeline_ids):
            raise ValueError("duplicate SymbolTimeline InstrumentId")
        for instrument_id in timeline_ids:
            if instrument_id not in known_instruments:
                raise ValueError(f"unknown InstrumentId reference: {instrument_id}")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "instrument_catalog",
            "currencies": [
                item.to_canonical_dict() for item in sorted(self.currencies)
            ],
            "instruments": [
                item.to_canonical_dict()
                for item in sorted(
                    self.instruments, key=lambda value: value.instrument_id
                )
            ],
            "symbol_timelines": [
                item.to_canonical_dict()
                for item in sorted(
                    self.symbol_timelines, key=lambda value: value.instrument_id
                )
            ],
        }

    def instrument(self, instrument_id: InstrumentId) -> InstrumentDefinition:
        for definition in self.instruments:
            if definition.instrument_id == instrument_id:
                return definition
        raise LookupError(f"unknown InstrumentId: {instrument_id}")
