"""Frozen mainland China cash-equity calendar and session semantics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
import unicodedata
from zoneinfo import ZoneInfo

from crypto_quant_domain import (
    SessionId,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading.ports import (
    ProfileComponentRef,
    ProfilePortOutcome,
    ProfilePortType,
)


_CALENDAR_BY_VENUE = {
    "xshg": "CN.XSHG",
    "xshe": "CN.XSHE",
}
_COMPONENT_KEY = "equity.cn_a_share.cash.session.v1"
_ALGORITHM_KEY = "cn-a-share-cash-session-resolution-v1"
_TIMEZONE = ZoneInfo("Asia/Shanghai")
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class CnAShareCalendarDayKind(Enum):
    TRADING = "trading"
    WEEKEND = "weekend"
    FROZEN_HOLIDAY = "frozen_holiday"


class CnAShareSessionPhase(Enum):
    PRE_OPEN = "pre_open"
    OPENING_CALL = "opening_call"
    OPENING_PAUSE = "opening_pause"
    CONTINUOUS_MORNING = "continuous_morning"
    LUNCH_BREAK = "lunch_break"
    CONTINUOUS_AFTERNOON = "continuous_afternoon"
    CLOSING_CALL = "closing_call"
    POST_CLOSE = "post_close"


class CnAShareSessionFailureCode(Enum):
    UNSUPPORTED_VENUE = "unsupported_venue"
    CALENDAR_COVERAGE_MISSING = "calendar_coverage_missing"


_PHASE_TABLE = (
    (CnAShareSessionPhase.PRE_OPEN, 0, 9 * 60 + 15, False),
    (CnAShareSessionPhase.OPENING_CALL, 9 * 60 + 15, 9 * 60 + 25, True),
    (CnAShareSessionPhase.OPENING_PAUSE, 9 * 60 + 25, 9 * 60 + 30, False),
    (CnAShareSessionPhase.CONTINUOUS_MORNING, 9 * 60 + 30, 11 * 60 + 30, True),
    (CnAShareSessionPhase.LUNCH_BREAK, 11 * 60 + 30, 13 * 60, False),
    (CnAShareSessionPhase.CONTINUOUS_AFTERNOON, 13 * 60, 14 * 60 + 57, True),
    (CnAShareSessionPhase.CLOSING_CALL, 14 * 60 + 57, 15 * 60, True),
    (CnAShareSessionPhase.POST_CLOSE, 15 * 60, 24 * 60, False),
)
_OPEN_PHASES = frozenset(
    phase for phase, _, _, is_open in _PHASE_TABLE if is_open
)


def _canonical_text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if (
        not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be nonempty canonical text")
    return value


def _date(name: str, value: object) -> date:
    if isinstance(value, datetime) or not isinstance(value, date):
        raise TypeError(f"{name} must be date")
    return value


@dataclass(frozen=True, slots=True)
class CnAShareFrozenCalendarDay:
    local_date: date
    kind: CnAShareCalendarDayKind

    def __post_init__(self) -> None:
        _date("local_date", self.local_date)
        if not isinstance(self.kind, CnAShareCalendarDayKind):
            raise TypeError("kind must be CnAShareCalendarDayKind")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_frozen_calendar_day",
            "schema_version": 1,
            "local_date": self.local_date.isoformat(),
            "kind": self.kind.value,
        }


@dataclass(frozen=True, slots=True)
class CnAShareFrozenCalendar:
    venue_id: VenueId
    calendar_id: str
    coverage_start: date
    coverage_end_exclusive: date
    days: tuple[CnAShareFrozenCalendarDay, ...]
    timezone_name: str = "Asia/Shanghai"

    def __post_init__(self) -> None:
        if not isinstance(self.venue_id, VenueId):
            raise TypeError("venue_id must be VenueId")
        _canonical_text("calendar_id", self.calendar_id)
        expected_calendar = _CALENDAR_BY_VENUE.get(self.venue_id.value)
        if expected_calendar != self.calendar_id:
            raise ValueError("unsupported calendar and venue pair")
        if self.timezone_name != "Asia/Shanghai":
            raise ValueError("timezone_name must be Asia/Shanghai")
        start = _date("coverage_start", self.coverage_start)
        end = _date("coverage_end_exclusive", self.coverage_end_exclusive)
        if start >= end:
            raise ValueError("calendar coverage must be nonempty")
        if not isinstance(self.days, tuple) or not all(
            isinstance(value, CnAShareFrozenCalendarDay) for value in self.days
        ):
            raise TypeError("days must contain CnAShareFrozenCalendarDay")
        ordered = tuple(sorted(self.days, key=lambda value: value.local_date))
        if len({value.local_date for value in ordered}) != len(ordered):
            raise ValueError("calendar days must be unique")
        expected_dates = tuple(
            start + timedelta(days=offset) for offset in range((end - start).days)
        )
        if tuple(value.local_date for value in ordered) != expected_dates:
            raise ValueError("calendar days must exact-cover the coverage interval")
        object.__setattr__(self, "days", ordered)

    @property
    def calendar_hash(self) -> str:
        return canonical_sha256(
            {
                "type": "cn_a_share_frozen_calendar",
                "schema_version": 1,
                "venue_id": self.venue_id,
                "calendar_id": self.calendar_id,
                "timezone_name": self.timezone_name,
                "coverage_start": self.coverage_start.isoformat(),
                "coverage_end_exclusive": self.coverage_end_exclusive.isoformat(),
                "canonical_sorted_days": self.days,
            }
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_frozen_calendar",
            "schema_version": 1,
            "venue_id": self.venue_id,
            "calendar_id": self.calendar_id,
            "timezone_name": self.timezone_name,
            "coverage_start": self.coverage_start.isoformat(),
            "coverage_end_exclusive": self.coverage_end_exclusive.isoformat(),
            "days": self.days,
        }


@dataclass(frozen=True, slots=True)
class CnAShareSessionQuery:
    venue_id: VenueId
    instant: UtcInstant

    def __post_init__(self) -> None:
        if not isinstance(self.venue_id, VenueId):
            raise TypeError("venue_id must be VenueId")
        if not isinstance(self.instant, UtcInstant):
            raise TypeError("instant must be UtcInstant")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_session_query",
            "schema_version": 1,
            "venue_id": self.venue_id,
            "instant": self.instant,
        }


@dataclass(frozen=True, slots=True)
class CnAShareSessionResolution:
    venue_id: VenueId
    instant: UtcInstant
    local_date: date
    day_kind: CnAShareCalendarDayKind
    session_id: SessionId | None
    trading_date: TradingDate | None
    phase: CnAShareSessionPhase | None
    phase_start: UtcInstant | None
    phase_end_exclusive: UtcInstant | None
    is_open: bool

    def __post_init__(self) -> None:
        if not isinstance(self.venue_id, VenueId):
            raise TypeError("venue_id must be VenueId")
        if not isinstance(self.instant, UtcInstant):
            raise TypeError("instant must be UtcInstant")
        _date("local_date", self.local_date)
        if not isinstance(self.day_kind, CnAShareCalendarDayKind):
            raise TypeError("day_kind must be CnAShareCalendarDayKind")
        if type(self.is_open) is not bool:
            raise TypeError("is_open must be bool")
        session_fields = (
            self.session_id,
            self.trading_date,
            self.phase,
            self.phase_start,
            self.phase_end_exclusive,
        )
        if self.day_kind is CnAShareCalendarDayKind.TRADING:
            expected_types = (
                SessionId,
                TradingDate,
                CnAShareSessionPhase,
                UtcInstant,
                UtcInstant,
            )
            if not all(
                isinstance(value, expected)
                for value, expected in zip(
                    session_fields, expected_types, strict=True
                )
            ):
                raise ValueError("trading resolution requires all session fields")
            if not isinstance(self.session_id, SessionId) or not isinstance(
                self.trading_date, TradingDate
            ):
                raise ValueError("trading resolution requires session identity")
            expected_calendar = _CALENDAR_BY_VENUE.get(self.venue_id.value)
            expected_session_value = f"{self.local_date.isoformat()}.regular"
            if (
                expected_calendar is None
                or self.session_id.calendar_id != expected_calendar
                or self.session_id.value != expected_session_value
                or self.trading_date.calendar_id != expected_calendar
                or self.trading_date.value != self.local_date
            ):
                raise ValueError("session identity does not match venue/local date")
            if self.phase_start is None or self.phase_end_exclusive is None:
                raise ValueError("trading resolution requires phase bounds")
            if self.phase is None:
                raise ValueError("trading resolution requires phase")
            if self.is_open != (self.phase in _OPEN_PHASES):
                raise ValueError("is_open does not match phase")
            phase_row = next(
                value for value in _PHASE_TABLE if value[0] is self.phase
            )
            expected_start = _boundary(self.local_date, phase_row[1])
            expected_end = _boundary(self.local_date, phase_row[2])
            if (
                self.phase_start != expected_start
                or self.phase_end_exclusive != expected_end
            ):
                raise ValueError("phase bounds do not match phase/local date")
            if not (
                self.phase_start.epoch_nanoseconds
                <= self.instant.epoch_nanoseconds
                < self.phase_end_exclusive.epoch_nanoseconds
            ):
                raise ValueError("instant must be inside resolved phase")
        elif any(value is not None for value in session_fields) or self.is_open:
            raise ValueError("known closure cannot carry session fields or be open")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_session_resolution",
            "schema_version": 1,
            "venue_id": self.venue_id,
            "instant": self.instant,
            "local_date": self.local_date.isoformat(),
            "day_kind": self.day_kind.value,
            "session_id": self.session_id,
            "trading_date": self.trading_date,
            "phase": self.phase.value if self.phase is not None else None,
            "phase_start": self.phase_start,
            "phase_end_exclusive": self.phase_end_exclusive,
            "is_open": self.is_open,
        }


@dataclass(frozen=True, slots=True)
class CnAShareSessionFailure:
    code: CnAShareSessionFailureCode
    venue_id: VenueId
    instant: UtcInstant
    calendar_id: str
    subject_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, CnAShareSessionFailureCode):
            raise TypeError("code must be CnAShareSessionFailureCode")
        if not isinstance(self.venue_id, VenueId):
            raise TypeError("venue_id must be VenueId")
        if not isinstance(self.instant, UtcInstant):
            raise TypeError("instant must be UtcInstant")
        _canonical_text("calendar_id", self.calendar_id)
        _canonical_text("subject_key", self.subject_key)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_session_failure",
            "schema_version": 1,
            "code": self.code.value,
            "venue_id": self.venue_id,
            "instant": self.instant,
            "calendar_id": self.calendar_id,
            "subject_key": self.subject_key,
        }


def _phase_table_payload() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "phase": phase.value,
            "start_minute": start,
            "end_minute_exclusive": end,
            "is_open": is_open,
        }
        for phase, start, end, is_open in _PHASE_TABLE
    )


def _local_datetime(instant: UtcInstant) -> datetime:
    seconds = instant.epoch_nanoseconds // 1_000_000_000
    return (_EPOCH + timedelta(seconds=seconds)).astimezone(_TIMEZONE)


def _boundary(local_date: date, minute: int) -> UtcInstant:
    if minute == 24 * 60:
        value = datetime.combine(
            local_date + timedelta(days=1), time.min, tzinfo=_TIMEZONE
        )
    else:
        value = datetime.combine(
            local_date,
            time(hour=minute // 60, minute=minute % 60),
            tzinfo=_TIMEZONE,
        )
    return UtcInstant.from_datetime(value)


@dataclass(frozen=True, slots=True)
class CnAShareCashSessionModel:
    calendar: CnAShareFrozenCalendar

    def __post_init__(self) -> None:
        if not isinstance(self.calendar, CnAShareFrozenCalendar):
            raise TypeError("calendar must be CnAShareFrozenCalendar")

    @property
    def component_ref(self) -> ProfileComponentRef:
        digest = canonical_sha256(
            {
                "type": "cn_a_share_cash_session_component",
                "schema_version": 1,
                "component_key": _COMPONENT_KEY,
                "component_version": 1,
                "algorithm_key": _ALGORITHM_KEY,
                "venue_id": self.calendar.venue_id,
                "calendar_id": self.calendar.calendar_id,
                "timezone_name": self.calendar.timezone_name,
                "calendar_hash": self.calendar.calendar_hash,
                "phase_table": _phase_table_payload(),
            }
        )
        return ProfileComponentRef(
            port_type=ProfilePortType.SESSION_MODEL,
            component_key=_COMPONENT_KEY,
            component_version=1,
            component_digest=digest,
        )

    def resolve_session(
        self, query: CnAShareSessionQuery, /
    ) -> ProfilePortOutcome[CnAShareSessionResolution, CnAShareSessionFailure]:
        if not isinstance(query, CnAShareSessionQuery):
            raise TypeError("query must be CnAShareSessionQuery")
        if query.venue_id != self.calendar.venue_id:
            return ProfilePortOutcome.for_failure(
                self.component_ref,
                query,
                CnAShareSessionFailure(
                    code=CnAShareSessionFailureCode.UNSUPPORTED_VENUE,
                    venue_id=query.venue_id,
                    instant=query.instant,
                    calendar_id=self.calendar.calendar_id,
                    subject_key=f"venue:{query.venue_id.value}",
                ),
            )
        query_ns = query.instant.epoch_nanoseconds
        coverage_start_ns = _boundary(
            self.calendar.coverage_start, 0
        ).epoch_nanoseconds
        coverage_end_ns = _boundary(
            self.calendar.coverage_end_exclusive, 0
        ).epoch_nanoseconds
        if not coverage_start_ns <= query_ns < coverage_end_ns:
            return ProfilePortOutcome.for_failure(
                self.component_ref,
                query,
                CnAShareSessionFailure(
                    code=CnAShareSessionFailureCode.CALENDAR_COVERAGE_MISSING,
                    venue_id=query.venue_id,
                    instant=query.instant,
                    calendar_id=self.calendar.calendar_id,
                    subject_key=f"instant:{canonical_sha256(query.instant)}",
                ),
            )
        local_date = _local_datetime(query.instant).date()
        offset = (local_date - self.calendar.coverage_start).days
        if offset < 0 or offset >= len(self.calendar.days):
            return ProfilePortOutcome.for_failure(
                self.component_ref,
                query,
                CnAShareSessionFailure(
                    code=CnAShareSessionFailureCode.CALENDAR_COVERAGE_MISSING,
                    venue_id=query.venue_id,
                    instant=query.instant,
                    calendar_id=self.calendar.calendar_id,
                    subject_key=f"date:{local_date.isoformat()}",
                ),
            )
        day = self.calendar.days[offset]
        if day.kind is not CnAShareCalendarDayKind.TRADING:
            return ProfilePortOutcome.for_result(
                self.component_ref,
                query,
                CnAShareSessionResolution(
                    venue_id=query.venue_id,
                    instant=query.instant,
                    local_date=local_date,
                    day_kind=day.kind,
                    session_id=None,
                    trading_date=None,
                    phase=None,
                    phase_start=None,
                    phase_end_exclusive=None,
                    is_open=False,
                ),
            )
        for phase, start, end, is_open in _PHASE_TABLE:
            phase_start = _boundary(local_date, start)
            phase_end = _boundary(local_date, end)
            if (
                phase_start.epoch_nanoseconds
                <= query_ns
                < phase_end.epoch_nanoseconds
            ):
                return ProfilePortOutcome.for_result(
                    self.component_ref,
                    query,
                    CnAShareSessionResolution(
                        venue_id=query.venue_id,
                        instant=query.instant,
                        local_date=local_date,
                        day_kind=day.kind,
                        session_id=SessionId(
                            self.calendar.calendar_id,
                            f"{local_date.isoformat()}.regular",
                        ),
                        trading_date=TradingDate(
                            self.calendar.calendar_id, local_date
                        ),
                        phase=phase,
                        phase_start=phase_start,
                        phase_end_exclusive=phase_end,
                        is_open=is_open,
                    ),
                )
        raise RuntimeError("phase table does not cover local trading day")
