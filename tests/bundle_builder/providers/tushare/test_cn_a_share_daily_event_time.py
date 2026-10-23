from __future__ import annotations

import hashlib
import importlib.util
import sys
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from crypto_quant_bundle_builder import (
    BarBucket,
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from crypto_quant_domain import UtcInstant, VenueId, canonical_bytes
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
CALENDAR_MODULE = FIXTURE / "calendar-source-v1.py"
G08H_CALENDAR = ROOT / "tests/fixtures/kernel/profiles/cn_a_share/calendar-session-v1.json"


def _instant(hour: int, minute: int) -> UtcInstant:
    return UtcInstant.from_datetime(
        datetime(2024, 1, 2, hour, minute, tzinfo=ZoneInfo("Asia/Shanghai"))
    )


def _load_frozen_calendar_module(monkeypatch):
    assert "sha256:" + hashlib.sha256(CALENDAR_MODULE.read_bytes()).hexdigest() == EXPECTED[
        "phase_authority"
    ]["calendar_module_sha256"], "archived calendar source hash mismatch"
    name = "_ar09_frozen_cn_a_share_calendar_v1"
    spec = importlib.util.spec_from_file_location(name, CALENDAR_MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def _calendar_model(module):
    calendar = module.CnAShareFrozenCalendar(
        venue_id=VenueId("xshe"),
        calendar_id="CN.XSHE",
        coverage_start=date(2024, 1, 2),
        coverage_end_exclusive=date(2024, 1, 3),
        days=(module.CnAShareFrozenCalendarDay(
            date(2024, 1, 2), module.CnAShareCalendarDayKind.TRADING
        ),),
    )
    return module.CnAShareCashSessionModel(calendar)


def _assert_phase_parity(current, frozen, frozen_module, instants):
    assert canonical_bytes(current.component_ref) == canonical_bytes(frozen.component_ref)
    for instant in instants:
        current_outcome = current.resolve_session(CnAShareSessionQuery(VenueId("xshe"), instant))
        frozen_outcome = frozen.resolve_session(frozen_module.CnAShareSessionQuery(VenueId("xshe"), instant))
        assert current_outcome.result is not None
        assert frozen_outcome.result is not None
        assert canonical_bytes(current_outcome.result) == canonical_bytes(frozen_outcome.result)


def _daily_bucket(values):
    return BarBucket(
        session_id=values[0].session_id,  # type: ignore[union-attr]
        trading_date=values[0].trading_date,  # type: ignore[union-attr]
        included_spans=tuple(
            (value.phase_start, value.phase_end_exclusive)  # type: ignore[misc]
            for value in values
        ),
        interval_start=values[0].phase_start,  # type: ignore[union-attr]
        interval_end_exclusive=values[-1].phase_end_exclusive,  # type: ignore[union-attr]
    )


def test_real_trade_calendar_and_g08h_phase_table_freeze_daily_bucket(monkeypatch) -> None:
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

    frozen_module = _load_frozen_calendar_module(monkeypatch)
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
    frozen = _calendar_model(frozen_module)
    _assert_phase_parity(
        model, frozen, frozen_module,
        tuple(_instant(hour, minute) for hour, minute in (
            (9, 15), (9, 20), (9, 25), (9, 30), (10, 0), (11, 30),
            (13, 0), (14, 0), (14, 57), (14, 59), (15, 0),
        )),
    )
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
    bucket = _daily_bucket(values)
    frozen_values = tuple(
        frozen.resolve_session(frozen_module.CnAShareSessionQuery(VenueId("xshe"), instant)).result
        for instant in (_instant(9, 15), _instant(9, 30), _instant(13, 0), _instant(14, 57))
    )
    assert all(value is not None for value in frozen_values)
    assert _daily_bucket(frozen_values).to_canonical_dict() == EXPECTED["bucket"]
    assert bucket.to_canonical_dict() == EXPECTED["bucket"]
    assert bucket.interval_start == _instant(9, 15)
    assert bucket.interval_end_exclusive == _instant(15, 0)
    assert EXPECTED["mapping"]["daily_bar_event_time"] == bucket.interval_start.to_canonical_dict()
    assert EXPECTED["mapping"]["daily_bar_finality_time"] == bucket.interval_end_exclusive.to_canonical_dict()


def test_modified_archive_is_rejected_before_loading(tmp_path: Path, monkeypatch) -> None:
    modified = tmp_path / "calendar-source-v1.py"
    modified.write_bytes(CALENDAR_MODULE.read_bytes() + b"\nraise RuntimeError('must not execute')\n")
    monkeypatch.setattr(sys.modules[__name__], "CALENDAR_MODULE", modified)
    def unexpected_load(*args, **kwargs):
        pytest.fail("hash mismatch must be rejected before creating a module spec")
    monkeypatch.setattr(importlib.util, "spec_from_file_location", unexpected_load)
    with pytest.raises(AssertionError, match="archived calendar source hash mismatch"):
        _load_frozen_calendar_module(monkeypatch)


@pytest.mark.parametrize("mutation", ("phase", "boundary"))
def test_current_phase_drift_is_rejected_by_archived_parity(monkeypatch, mutation: str) -> None:
    import crypto_quant_trading.profiles.cn_a_share.calendar as current_module

    frozen_module = _load_frozen_calendar_module(monkeypatch)
    frozen = _calendar_model(frozen_module)
    current = _calendar_model(current_module)
    table = list(current_module._PHASE_TABLE)
    phase, start, end, is_open = table[1]
    table[1] = (
        current_module.CnAShareSessionPhase.PRE_OPEN if mutation == "phase" else phase,
        start,
        end + 1 if mutation == "boundary" else end,
        is_open,
    )
    monkeypatch.setattr(current_module, "_PHASE_TABLE", tuple(table))
    with pytest.raises(AssertionError):
        _assert_phase_parity(current, frozen, frozen_module, (_instant(9, 15), _instant(9, 25)))
