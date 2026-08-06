from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from crypto_quant_domain import UtcInstant, VenueId
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCalendarDayKind,
    CnAShareFrozenCalendar,
    CnAShareFrozenCalendarDay,
    CnAShareSessionQuery,
)


_TIMEZONE = ZoneInfo("Asia/Shanghai")


def frozen_calendar(venue: str = "xshg") -> CnAShareFrozenCalendar:
    calendar_id = {"xshg": "CN.XSHG", "xshe": "CN.XSHE"}[venue]
    days = []
    for day in range(8, 20):
        local_date = date(2024, 2, day)
        if day in {8, 19}:
            kind = CnAShareCalendarDayKind.TRADING
        elif day == 18:
            kind = CnAShareCalendarDayKind.WEEKEND
        else:
            kind = CnAShareCalendarDayKind.FROZEN_HOLIDAY
        days.append(CnAShareFrozenCalendarDay(local_date, kind))
    return CnAShareFrozenCalendar(
        venue_id=VenueId(venue),
        calendar_id=calendar_id,
        coverage_start=date(2024, 2, 8),
        coverage_end_exclusive=date(2024, 2, 20),
        days=tuple(reversed(days)),
    )


def local_query(
    local_date: date,
    hour: int,
    minute: int,
    *,
    venue: str = "xshg",
) -> CnAShareSessionQuery:
    return CnAShareSessionQuery(
        venue_id=VenueId(venue),
        instant=UtcInstant.from_datetime(
            datetime(
                local_date.year,
                local_date.month,
                local_date.day,
                hour,
                minute,
                tzinfo=_TIMEZONE,
            )
        ),
    )
