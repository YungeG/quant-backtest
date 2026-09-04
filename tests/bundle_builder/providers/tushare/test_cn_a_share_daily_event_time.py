from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from crypto_quant_bundle_builder import (
    BarBucket,
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from crypto_quant_domain import UtcInstant, VenueId
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCalendarDayKind,
    CnAShareCashSessionModel,
    CnAShareFrozenCalendar,
    CnAShareFrozenCalendarDay,
    CnAShareSessionPhase,
    CnAShareSessionQuery,
)


ROOT = Path(__file__).parents[4]
FIXTURE = (
    ROOT
    / "tests/fixtures/market_data/providers/tushare/cn-a-share-trade-calendar-v1"
)
RESPONSE = FIXTURE / "trade-calendar.json"
RECEIPT = FIXTURE / "acquisition-receipt.json"
EXPECTED = json.loads((FIXTURE / "daily-event-time.expected.json").read_text())
CALENDAR_MODULE = (
    ROOT
    / "packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share/calendar.py"
)
G08H_CALENDAR = ROOT / "tests/fixtures/kernel/profiles/cn_a_share/calendar-session-v1.json"


def _instant(hour: int, minute: int) -> UtcInstant:
    return UtcInstant.from_datetime(
        datetime(2024, 1, 2, hour, minute, tzinfo=ZoneInfo("Asia/Shanghai"))
    )


def test_real_trade_calendar_and_g08h_phase_table_freeze_daily_bucket() -> None:
    response_bytes = RESPONSE.read_bytes()
    receipt_bytes = RECEIPT.read_bytes()
    receipt = json.loads(receipt_bytes)
    response = json.loads(response_bytes)
    assert "sha256:" + hashlib.sha256(response_bytes).hexdigest() == EXPECTED[
        "trade_calendar"
    ]["response_sha256"]
    assert "sha256:" + hashlib.sha256(receipt_bytes).hexdigest() == EXPECTED[
        "trade_calendar"
    ]["receipt_sha256"]
    assert response["data"]["fields"] == [
        "exchange",
        "cal_date",
        "is_open",
        "pretrade_date",
    ]
    assert response["data"]["items"] == [["SZSE", "20240102", 1, "20231229"]]
    assert "token" not in receipt

    acquired_at = receipt["acquired_at_epoch_nanoseconds"]
    outcome = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "response/trade-calendar.json",
                response_bytes,
                "0644",
                acquired_at,
                None,
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro",
            source_key="tushare.pro.trade_calendar.szse.20240102",
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    )
    assert outcome.failure is None
    assert outcome.snapshot is not None
    assert outcome.snapshot.to_canonical_dict() == EXPECTED["trade_calendar"][
        "snapshot"
    ]

    assert "sha256:" + hashlib.sha256(CALENDAR_MODULE.read_bytes()).hexdigest() == EXPECTED[
        "phase_authority"
    ]["calendar_module_sha256"]
    assert "sha256:" + hashlib.sha256(G08H_CALENDAR.read_bytes()).hexdigest() == EXPECTED[
        "phase_authority"
    ]["g08h_calendar_fixture_sha256"]

    calendar = CnAShareFrozenCalendar(
        venue_id=VenueId("xshe"),
        calendar_id="CN.XSHE",
        coverage_start=date(2024, 1, 2),
        coverage_end_exclusive=date(2024, 1, 3),
        days=(
            CnAShareFrozenCalendarDay(
                date(2024, 1, 2), CnAShareCalendarDayKind.TRADING
            ),
        ),
    )
    model = CnAShareCashSessionModel(calendar)
    resolutions = tuple(
        model.resolve_session(CnAShareSessionQuery(VenueId("xshe"), instant))
        for instant in (_instant(9, 15), _instant(9, 30), _instant(13, 0), _instant(14, 57))
    )
    assert all(outcome.result is not None for outcome in resolutions)
    values = tuple(outcome.result for outcome in resolutions)
    assert [value.phase for value in values if value is not None] == [
        CnAShareSessionPhase.OPENING_CALL,
        CnAShareSessionPhase.CONTINUOUS_MORNING,
        CnAShareSessionPhase.CONTINUOUS_AFTERNOON,
        CnAShareSessionPhase.CLOSING_CALL,
    ]
    assert all(value is not None for value in values)
    bucket = BarBucket(
        session_id=values[0].session_id,  # type: ignore[union-attr]
        trading_date=values[0].trading_date,  # type: ignore[union-attr]
        included_spans=tuple(
            (value.phase_start, value.phase_end_exclusive)  # type: ignore[misc]
            for value in values
        ),
        interval_start=values[0].phase_start,  # type: ignore[union-attr]
        interval_end_exclusive=values[-1].phase_end_exclusive,  # type: ignore[union-attr]
    )
    assert bucket.to_canonical_dict() == EXPECTED["bucket"]
    assert bucket.interval_start == _instant(9, 15)
    assert bucket.interval_end_exclusive == _instant(15, 0)
    assert EXPECTED["mapping"]["daily_bar_event_time"] == bucket.interval_start.to_canonical_dict()
    assert EXPECTED["mapping"]["daily_bar_finality_time"] == bucket.interval_end_exclusive.to_canonical_dict()
