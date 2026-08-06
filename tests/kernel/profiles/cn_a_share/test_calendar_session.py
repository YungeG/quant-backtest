from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone
from pathlib import Path

import crypto_quant_trading
import pytest

from crypto_quant_domain import (
    SessionId,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCalendarDayKind,
    CnAShareCashSessionModel,
    CnAShareFrozenCalendar,
    CnAShareFrozenCalendarDay,
    CnAShareSessionFailure,
    CnAShareSessionFailureCode,
    CnAShareSessionPhase,
    CnAShareSessionQuery,
    CnAShareSessionResolution,
)
from crypto_quant_trading import ProfilePortType, SessionModel
from tests.kernel.profiles.cn_a_share._fixtures import frozen_calendar, local_query


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        pytest.fail(f"cannot read source file: {error}")


def test_frozen_calendar_canonicalizes_complete_daily_coverage() -> None:
    trading = CnAShareFrozenCalendarDay(
        local_date=date(2024, 2, 8),
        kind=CnAShareCalendarDayKind.TRADING,
    )
    holiday = CnAShareFrozenCalendarDay(
        local_date=date(2024, 2, 9),
        kind=CnAShareCalendarDayKind.FROZEN_HOLIDAY,
    )

    calendar = CnAShareFrozenCalendar(
        venue_id=VenueId("xshg"),
        calendar_id="CN.XSHG",
        coverage_start=date(2024, 2, 8),
        coverage_end_exclusive=date(2024, 2, 10),
        days=(holiday, trading),
    )
    reordered = CnAShareFrozenCalendar(
        venue_id=VenueId("xshg"),
        calendar_id="CN.XSHG",
        coverage_start=date(2024, 2, 8),
        coverage_end_exclusive=date(2024, 2, 10),
        days=(trading, holiday),
    )

    expected_days = (trading, holiday)
    assert calendar.days == expected_days
    assert calendar == reordered
    expected_hash = canonical_sha256(
        {
            "type": "cn_a_share_frozen_calendar",
            "schema_version": 1,
            "venue_id": VenueId("xshg"),
            "calendar_id": "CN.XSHG",
            "timezone_name": "Asia/Shanghai",
            "coverage_start": "2024-02-08",
            "coverage_end_exclusive": "2024-02-10",
            "canonical_sorted_days": expected_days,
        }
    )
    assert calendar.calendar_hash == expected_hash
    assert calendar.to_canonical_dict()["schema_version"] == 1


def test_trading_day_resolves_local_phase_and_stable_session_id() -> None:
    calendar = CnAShareFrozenCalendar(
        venue_id=VenueId("xshg"),
        calendar_id="CN.XSHG",
        coverage_start=date(2024, 2, 19),
        coverage_end_exclusive=date(2024, 2, 20),
        days=(
            CnAShareFrozenCalendarDay(
                date(2024, 2, 19),
                CnAShareCalendarDayKind.TRADING,
            ),
        ),
    )
    model = CnAShareCashSessionModel(calendar)
    pre_open = model.resolve_session(
        CnAShareSessionQuery(
            VenueId("xshg"),
            UtcInstant.from_datetime(
                datetime(2024, 2, 18, 16, 30, tzinfo=timezone.utc)
            ),
        )
    )
    opening_call = model.resolve_session(
        CnAShareSessionQuery(
            VenueId("xshg"),
            UtcInstant.from_datetime(
                datetime(2024, 2, 19, 1, 15, tzinfo=timezone.utc)
            ),
        )
    )

    assert pre_open.failure is None
    assert opening_call.failure is None
    assert pre_open.result is not None
    assert opening_call.result is not None
    assert pre_open.result.local_date == date(2024, 2, 19)
    assert pre_open.result.trading_date == TradingDate(
        "CN.XSHG", date(2024, 2, 19)
    )
    assert pre_open.result.phase is CnAShareSessionPhase.PRE_OPEN
    assert not pre_open.result.is_open
    assert opening_call.result.phase is CnAShareSessionPhase.OPENING_CALL
    assert opening_call.result.is_open
    expected_session = SessionId("CN.XSHG", "2024-02-19.regular")
    assert pre_open.result.session_id == expected_session
    assert opening_call.result.session_id == expected_session


def test_trading_resolution_rejects_identity_that_disagrees_with_local_date() -> None:
    instant = UtcInstant.from_datetime(
        datetime(2024, 2, 19, 1, 15, tzinfo=timezone.utc)
    )

    with pytest.raises(ValueError, match="session identity"):
        CnAShareSessionResolution(
            venue_id=VenueId("xshg"),
            instant=instant,
            local_date=date(2024, 2, 19),
            day_kind=CnAShareCalendarDayKind.TRADING,
            session_id=SessionId("CN.XSHE", "2024-02-19.regular"),
            trading_date=TradingDate("CN.XSHG", date(2024, 2, 19)),
            phase=CnAShareSessionPhase.OPENING_CALL,
            phase_start=instant,
            phase_end_exclusive=UtcInstant.from_datetime(
                datetime(2024, 2, 19, 1, 25, tzinfo=timezone.utc)
            ),
            is_open=True,
        )


def test_trading_resolution_rejects_noncanonical_phase_bounds() -> None:
    instant = UtcInstant.from_datetime(
        datetime(2024, 2, 19, 1, 15, tzinfo=timezone.utc)
    )

    with pytest.raises(ValueError, match="phase bounds"):
        CnAShareSessionResolution(
            venue_id=VenueId("xshg"),
            instant=instant,
            local_date=date(2024, 2, 19),
            day_kind=CnAShareCalendarDayKind.TRADING,
            session_id=SessionId("CN.XSHG", "2024-02-19.regular"),
            trading_date=TradingDate("CN.XSHG", date(2024, 2, 19)),
            phase=CnAShareSessionPhase.OPENING_CALL,
            phase_start=instant,
            phase_end_exclusive=UtcInstant.from_datetime(
                datetime(2024, 2, 19, 1, 26, tzinfo=timezone.utc)
            ),
            is_open=True,
        )


def test_trading_resolution_rejects_open_state_that_disagrees_with_phase() -> None:
    instant = UtcInstant.from_datetime(
        datetime(2024, 2, 19, 1, 15, tzinfo=timezone.utc)
    )

    with pytest.raises(ValueError, match="is_open does not match phase"):
        CnAShareSessionResolution(
            venue_id=VenueId("xshg"),
            instant=instant,
            local_date=date(2024, 2, 19),
            day_kind=CnAShareCalendarDayKind.TRADING,
            session_id=SessionId("CN.XSHG", "2024-02-19.regular"),
            trading_date=TradingDate("CN.XSHG", date(2024, 2, 19)),
            phase=CnAShareSessionPhase.OPENING_CALL,
            phase_start=instant,
            phase_end_exclusive=UtcInstant.from_datetime(
                datetime(2024, 2, 19, 1, 25, tzinfo=timezone.utc)
            ),
            is_open=False,
        )


@pytest.mark.parametrize(
    ("hour", "minute", "phase", "is_open"),
    (
        (0, 0, CnAShareSessionPhase.PRE_OPEN, False),
        (9, 15, CnAShareSessionPhase.OPENING_CALL, True),
        (9, 25, CnAShareSessionPhase.OPENING_PAUSE, False),
        (9, 30, CnAShareSessionPhase.CONTINUOUS_MORNING, True),
        (11, 30, CnAShareSessionPhase.LUNCH_BREAK, False),
        (13, 0, CnAShareSessionPhase.CONTINUOUS_AFTERNOON, True),
        (14, 57, CnAShareSessionPhase.CLOSING_CALL, True),
        (15, 0, CnAShareSessionPhase.POST_CLOSE, False),
    ),
)
def test_phase_starts_are_exact_half_open_boundaries(
    hour: int,
    minute: int,
    phase: CnAShareSessionPhase,
    is_open: bool,
) -> None:
    query = local_query(date(2024, 2, 19), hour, minute)
    outcome = CnAShareCashSessionModel(frozen_calendar()).resolve_session(query)

    assert outcome.failure is None
    assert outcome.result is not None
    assert outcome.result.phase is phase
    assert outcome.result.phase_start == query.instant
    assert outcome.result.is_open is is_open


def test_one_nanosecond_before_phase_boundary_stays_in_prior_phase() -> None:
    opening = local_query(date(2024, 2, 19), 9, 15)
    query = CnAShareSessionQuery(
        venue_id=opening.venue_id,
        instant=UtcInstant(opening.instant.epoch_nanoseconds - 1),
    )

    outcome = CnAShareCashSessionModel(frozen_calendar()).resolve_session(query)

    assert outcome.failure is None
    assert outcome.result is not None
    assert outcome.result.phase is CnAShareSessionPhase.PRE_OPEN
    assert outcome.result.phase_end_exclusive == opening.instant


def test_known_holiday_and_weekend_are_successful_no_session_closures() -> None:
    model = CnAShareCashSessionModel(frozen_calendar())
    holiday = model.resolve_session(local_query(date(2024, 2, 10), 10, 0))
    weekend = model.resolve_session(local_query(date(2024, 2, 18), 10, 0))

    assert holiday.failure is None
    assert holiday.result is not None
    assert holiday.result.day_kind is CnAShareCalendarDayKind.FROZEN_HOLIDAY
    assert weekend.failure is None
    assert weekend.result is not None
    assert weekend.result.day_kind is CnAShareCalendarDayKind.WEEKEND
    for resolution in (holiday.result, weekend.result):
        session_fields = (
            resolution.session_id,
            resolution.trading_date,
            resolution.phase,
            resolution.phase_start,
            resolution.phase_end_exclusive,
        )
        assert all(value is None for value in session_fields)
        assert not resolution.is_open


def test_unsupported_venue_and_missing_coverage_are_distinct_failures() -> None:
    model = CnAShareCashSessionModel(frozen_calendar())
    unsupported_query = local_query(
        date(2024, 2, 19), 10, 0, venue="xbse"
    )
    coverage_query = local_query(date(2024, 2, 20), 10, 0)

    unsupported = model.resolve_session(unsupported_query)
    missing = model.resolve_session(coverage_query)

    assert unsupported.result is None
    assert unsupported.failure is not None
    assert unsupported.failure.code is CnAShareSessionFailureCode.UNSUPPORTED_VENUE
    assert unsupported.input_hash == canonical_sha256(unsupported_query)
    assert missing.result is None
    assert missing.failure is not None
    assert (
        missing.failure.code
        is CnAShareSessionFailureCode.CALENDAR_COVERAGE_MISSING
    )
    assert missing.input_hash == canonical_sha256(coverage_query)


def _two_day_calendar(
    *,
    days: tuple[CnAShareFrozenCalendarDay, ...],
    calendar_id: str = "CN.XSHG",
    timezone_name: str = "Asia/Shanghai",
) -> CnAShareFrozenCalendar:
    return CnAShareFrozenCalendar(
        venue_id=VenueId("xshg"),
        calendar_id=calendar_id,
        coverage_start=date(2024, 2, 8),
        coverage_end_exclusive=date(2024, 2, 10),
        days=days,
        timezone_name=timezone_name,
    )


@pytest.mark.parametrize(
    "instant",
    (
        UtcInstant(10**5000),
        UtcInstant(-(10**5000)),
        UtcInstant.from_datetime(datetime.max.replace(tzinfo=timezone.utc)),
    ),
)
def test_extreme_out_of_coverage_instant_is_structured_failure(
    instant: UtcInstant,
) -> None:
    query = CnAShareSessionQuery(VenueId("xshg"), instant)
    outcome = CnAShareCashSessionModel(frozen_calendar()).resolve_session(query)

    assert outcome.result is None
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is CnAShareSessionFailureCode.CALENDAR_COVERAGE_MISSING
    )
    assert outcome.input_hash == canonical_sha256(query)


def test_calendar_rejects_duplicate_gap_timezone_and_wrong_identity() -> None:
    trading = CnAShareFrozenCalendarDay(
        date(2024, 2, 8), CnAShareCalendarDayKind.TRADING
    )
    holiday = CnAShareFrozenCalendarDay(
        date(2024, 2, 9), CnAShareCalendarDayKind.FROZEN_HOLIDAY
    )
    with pytest.raises(ValueError, match="unique"):
        _two_day_calendar(days=(trading, trading))
    with pytest.raises(ValueError, match="exact-cover"):
        _two_day_calendar(days=(trading,))
    with pytest.raises(ValueError, match="timezone"):
        _two_day_calendar(days=(trading, holiday), timezone_name="UTC")
    with pytest.raises(ValueError, match="calendar and venue"):
        _two_day_calendar(days=(trading, holiday), calendar_id="CN.XSHE")


def test_frozen_calendar_and_component_hashes_match_spec_literals() -> None:
    shanghai = CnAShareCashSessionModel(frozen_calendar("xshg"))
    shenzhen = CnAShareCashSessionModel(frozen_calendar("xshe"))

    assert (
        shanghai.calendar.calendar_hash
        == "sha256:0eb554a4554b1ff8eafb841ab447a720ca69383fca9a20b400a7e4a030a1462d"
    )
    assert (
        shenzhen.calendar.calendar_hash
        == "sha256:99c4a2c8e06ccb696c15b6b8d676c42195f54465d6b46237ed74dfd699d3bb73"
    )
    assert (
        shanghai.component_ref.component_digest
        == "sha256:351957c2fd1fab7b63da654ccbde9a95c03047dc74fa2d85e089cc3e14f5be8f"
    )
    assert (
        shenzhen.component_ref.component_digest
        == "sha256:58377db746d9c37967b94c1291ede824ac6a4597402d92c05e7d386f36bf1d52"
    )


def test_component_identity_is_venue_specific_and_implements_session_port() -> None:
    shanghai = CnAShareCashSessionModel(frozen_calendar("xshg"))
    shenzhen = CnAShareCashSessionModel(frozen_calendar("xshe"))

    assert CnAShareSessionFailure.__name__ == "CnAShareSessionFailure"
    assert isinstance(shanghai, SessionModel)
    assert shanghai.component_ref.port_type is ProfilePortType.SESSION_MODEL
    assert (
        shanghai.component_ref.component_key
        == "equity.cn_a_share.cash.session.v1"
    )
    assert shanghai.component_ref.component_version == 1
    assert shanghai.component_ref != shenzhen.component_ref
    assert shanghai.component_ref == CnAShareCashSessionModel(
        frozen_calendar("xshg")
    ).component_ref
    assert not hasattr(crypto_quant_trading, "CnAShareCashSessionModel")


def test_component_digest_changes_when_calendar_semantics_change() -> None:
    original = frozen_calendar()
    changed_days = tuple(
        CnAShareFrozenCalendarDay(
            day.local_date,
            CnAShareCalendarDayKind.WEEKEND
            if day.local_date == date(2024, 2, 8)
            else day.kind,
        )
        for day in original.days
    )
    changed = CnAShareFrozenCalendar(
        venue_id=original.venue_id,
        calendar_id=original.calendar_id,
        coverage_start=original.coverage_start,
        coverage_end_exclusive=original.coverage_end_exclusive,
        days=changed_days,
    )

    assert original.calendar_hash != changed.calendar_hash
    assert (
        CnAShareCashSessionModel(original).component_ref.component_digest
        != CnAShareCashSessionModel(changed).component_ref.component_digest
    )


def test_calendar_values_are_immutable() -> None:
    calendar = frozen_calendar()
    with pytest.raises(FrozenInstanceError):
        calendar.calendar_id = "CN.XSHE"  # type: ignore[misc]


def test_concrete_calendar_source_has_no_io_network_or_wall_clock_access() -> None:
    root = Path(__file__).resolve().parents[4]
    profile_root = (
        root
        / "packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share"
    )
    forbidden_imports = {
        "aiohttp",
        "binance",
        "ccxt",
        "http",
        "httpx",
        "hummingbot",
        "os",
        "paho",
        "pathlib",
        "requests",
        "socket",
        "urllib",
        "urllib3",
        "websockets",
    }
    for source_path in sorted(profile_root.rglob("*.py")):
        tree = ast.parse(_read_text(source_path))
        imported_roots = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            (node.module or "").split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert imported_roots.isdisjoint(forbidden_imports)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            assert not isinstance(node.func, ast.Name) or node.func.id != "open"
            if isinstance(node.func, ast.Attribute):
                wall_clock = (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id in {"date", "datetime", "time"}
                    and node.func.attr
                    in {"now", "utcnow", "today", "time", "time_ns"}
                )
                assert not wall_clock
    generic_root = root / "packages/trading-kernel/src/crypto_quant_trading"
    for path in generic_root.glob("*.py"):
        assert "profiles.cn_a_share" not in _read_text(path)
