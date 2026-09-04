from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_MAX_SOURCE_SEQUENCE = 2**63 - 1
_PHASE_CODE = re.compile(r"[a-z][a-z0-9_.-]*\Z")


def require_canonical_text(name: str, value: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise ValueError(f"{name} must be canonical non-empty text")


@dataclass(frozen=True, slots=True, order=True)
class UtcInstant:
    epoch_nanoseconds: int

    def __post_init__(self) -> None:
        if isinstance(self.epoch_nanoseconds, bool) or not isinstance(
            self.epoch_nanoseconds, int
        ):
            raise TypeError("epoch_nanoseconds must be an integer")

    @classmethod
    def from_datetime(cls, value: datetime) -> UtcInstant:
        if not isinstance(value, datetime):
            raise TypeError("value must be a datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("naive datetime is not an authoritative instant")
        utc = value.astimezone(timezone.utc)
        delta = utc - _EPOCH
        seconds = delta.days * 86400 + delta.seconds
        return cls(seconds * 1_000_000_000 + utc.microsecond * 1000)

    def to_datetime(self) -> datetime:
        if self.epoch_nanoseconds % 1000 != 0:
            raise ValueError("epoch nanoseconds are not exactly representable at microsecond precision")
        return _EPOCH + timedelta(microseconds=self.epoch_nanoseconds // 1000)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "utc_instant",
            "epoch_nanoseconds": self.epoch_nanoseconds,
        }


class LocalTimeDisambiguation(str, Enum):
    EARLIER = "earlier"
    LATER = "later"
    REJECT = "reject"


def resolve_local_datetime(
    value: datetime,
    zone: ZoneInfo,
    disambiguation: LocalTimeDisambiguation,
) -> UtcInstant:
    if not isinstance(value, datetime):
        raise TypeError("value must be a datetime")
    if value.tzinfo is not None:
        raise ValueError("local resolver requires a naive local datetime")
    if not isinstance(zone, ZoneInfo):
        raise TypeError("zone must be ZoneInfo")
    if not isinstance(disambiguation, LocalTimeDisambiguation):
        raise TypeError("disambiguation must be LocalTimeDisambiguation")

    candidates: dict[int, UtcInstant] = {}
    for fold in (0, 1):
        aware = value.replace(tzinfo=zone, fold=fold)
        utc = aware.astimezone(timezone.utc)
        round_trip = utc.astimezone(zone)
        if (
            round_trip.replace(tzinfo=None) == value
            and round_trip.fold == fold
        ):
            instant = UtcInstant.from_datetime(utc)
            candidates[instant.epoch_nanoseconds] = instant

    ordered = [candidates[key] for key in sorted(candidates)]
    if not ordered:
        raise ValueError("nonexistent local time")
    if len(ordered) == 1:
        return ordered[0]
    if disambiguation is LocalTimeDisambiguation.REJECT:
        raise ValueError("ambiguous local time requires earlier/later policy")
    return ordered[0] if disambiguation is LocalTimeDisambiguation.EARLIER else ordered[-1]


@dataclass(frozen=True, slots=True)
class TradingDate:
    calendar_id: str
    value: date

    def __post_init__(self) -> None:
        require_canonical_text("calendar_id", self.calendar_id)
        if isinstance(self.value, datetime) or not isinstance(self.value, date):
            raise TypeError("TradingDate value must be a date")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "trading_date",
            "calendar_id": self.calendar_id,
            "date": self.value.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class SessionId:
    calendar_id: str
    value: str

    def __post_init__(self) -> None:
        require_canonical_text("calendar_id", self.calendar_id)
        require_canonical_text("SessionId value", self.value)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "session_id",
            "calendar_id": self.calendar_id,
            "value": self.value,
        }


@dataclass(frozen=True, slots=True, order=True)
class TimelinePhase:
    rank: int
    code: str

    def __post_init__(self) -> None:
        if isinstance(self.rank, bool) or not isinstance(self.rank, int):
            raise TypeError("TimelinePhase rank must be an integer")
        if self.rank < 0:
            raise ValueError("TimelinePhase rank must be non-negative")
        if not isinstance(self.code, str) or _PHASE_CODE.fullmatch(self.code) is None:
            raise ValueError("TimelinePhase code must be canonical lowercase text")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {"type": "timeline_phase", "rank": self.rank, "code": self.code}


@dataclass(frozen=True, slots=True, order=True)
class SourceSequence:
    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError("SourceSequence value must be an integer")
        if not 0 <= self.value <= _MAX_SOURCE_SEQUENCE:
            raise ValueError("SourceSequence must be between 0 and 2^63-1")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {"type": "source_sequence", "value": self.value}


@dataclass(frozen=True, slots=True, order=True)
class SimulationInstant:
    instant: UtcInstant
    phase: TimelinePhase
    source_sequence: SourceSequence

    def __post_init__(self) -> None:
        if not isinstance(self.instant, UtcInstant):
            raise TypeError("instant must be UtcInstant")
        if not isinstance(self.phase, TimelinePhase):
            raise TypeError("phase must be TimelinePhase")
        if not isinstance(self.source_sequence, SourceSequence):
            raise TypeError("source_sequence must be SourceSequence")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "simulation_instant",
            "instant": self.instant.to_canonical_dict(),
            "phase": self.phase.to_canonical_dict(),
            "source_sequence": self.source_sequence.to_canonical_dict(),
        }
