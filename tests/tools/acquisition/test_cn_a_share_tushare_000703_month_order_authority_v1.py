from __future__ import annotations

from datetime import date, datetime, timedelta
import json
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import RawSourceMember, SourceSnapshotProvenance, freeze_source_snapshot

from tools.acquisition._common import AcquisitionError, sha256
from tools.acquisition.cn_a_share_tushare_000703_month_order_authority_v1 import (
    Tushare000703MonthlyOrderAuthorityRequest,
    acquire_tushare_000703_month_order_authority_v1,
    verify_tushare_000703_month_order_authority_v1,
)
from tools.acquisition.cn_a_share_tushare_minute_source_bounded_v2 import (
    TushareMinuteSourceBoundedRequestV2,
    acquire_tushare_minute_source_bounded_v2,
)
from tools.acquisition.cn_a_share_tushare_proxy_trade_calendar_month_source_bounded_v2 import (
    TushareProxyTradeCalendarMonthSourceBoundedRequestV2,
    _source_dates,
    acquire_tushare_proxy_trade_calendar_month_source_bounded_v2,
)


TOKEN = "x" * 56
FIELDS = {
    "stock_basic": [
        "ts_code", "symbol", "name", "area", "industry", "market", "exchange",
        "list_status", "list_date", "delist_date",
    ],
    "daily": [
        "ts_code", "trade_date", "open", "high", "low", "close", "pre_close",
        "change", "pct_chg", "vol", "amount",
    ],
    "stk_limit": ["trade_date", "ts_code", "up_limit", "down_limit"],
    "stock_st": ["ts_code", "trade_date", "name"],
    "suspend_d": ["ts_code", "trade_date", "suspend_timing", "suspend_type"],
    "trade_cal": ["exchange", "cal_date", "is_open", "pretrade_date"],
    "stk_mins": ["ts_code", "trade_time", "close", "open", "high", "low", "vol", "amount"],
}


def _open_sessions(month: str) -> tuple[str, ...]:
    year, number = int(month[:4]), int(month[4:])
    current = date(year, number, 1)
    values = []
    while current.month == number:
        if current.weekday() < 5:
            values.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return tuple(values)


def _response(fields: list[str], rows: list[list[object]], *, terminal: bool = True) -> bytes:
    return json.dumps(
        {
            "request_id": "id",
            "code": 0,
            "data": {"fields": fields, "items": rows, "has_more": not terminal, "count": 0},
            "msg": "",
            "detail": "",
        },
        separators=(",", ":"),
    ).encode()


def _calendar_response(month: str) -> bytes:
    open_sessions = set(_open_sessions(month))
    source_dates = _source_dates(month)
    previous = (
        datetime.strptime(source_dates[0], "%Y%m%d").date() - timedelta(days=1)
    ).strftime("%Y%m%d")
    rows = []
    for day in source_dates:
        open_ = day in open_sessions
        rows.append(["SZSE", day, int(open_), previous])
        if open_:
            previous = day
    return _response(FIELDS["trade_cal"], rows)


def _minute_response(day: str) -> bytes:
    from tools.acquisition.cn_a_share_tushare_minute_source_bounded_v2 import _expected_trade_times

    return _response(
        FIELDS["stk_mins"],
        [["000703.SZ", value, 10, 10, 10, 10, 0, 0] for value in _expected_trade_times(day)],
    )


class AuthorityPost:
    def __call__(self, _url: str, body: dict[str, object], _headers: dict[str, str]) -> tuple[int, bytes]:
        params = body["params"]
        if body["api_name"] == "trade_cal":
            return 200, _calendar_response(str(params["end_date"])[:6])
        return 200, _minute_response(str(params["start_date"])[:10].replace("-", ""))


class FakePost:
    def __init__(self, *, bad: str | None = None) -> None:
        self.bad = bad

    def __call__(self, _url: str, body: dict[str, object], _headers: dict[str, str]) -> tuple[int, bytes]:
        api, params = str(body["api_name"]), body["params"]
        day = str(params.get("trade_date", params.get("start_date")))
        fields = body["fields"].split(",")
        if api == "stock_basic":
            rows = [["000703.SZ", "000703", "x", "x", "x", "主板", "SZSE", "L", "19970528", None]]
        elif api == "daily":
            rows = [["000703.SZ", day, 10, 11, 9, 10, 10, 0, 0, 100, 1000]]
        elif api == "stk_limit":
            rows = [[day, "000703.SZ", 11, 9]]
        else:
            rows = []
        if self.bad == "stock_st" and api == "stock_st":
            rows = [["000703.SZ", day, "*ST"]]
        if self.bad == "daily_scope" and api == "daily":
            rows[0][1] = "20240201"
        return 200, _response(
            fields,
            rows,
            terminal=not (self.bad == "daily_nonterminal" and api == "daily"),
        )


def _authorities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, month: str
) -> tuple[Path, Path, str, dict[str, str], tuple[str, ...]]:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    calendar = tmp_path / "calendar"
    acquire_tushare_proxy_trade_calendar_month_source_bounded_v2(
        TushareProxyTradeCalendarMonthSourceBoundedRequestV2("SZSE", month),
        endpoint="https://fast.xiaodefa.cn",
        output_dir=calendar,
        post=AuthorityPost(),
        clock=lambda: 1,
        sleep=lambda _: None,
    )
    minutes = tmp_path / "minutes"
    hashes: dict[str, str] = {}
    sessions = _open_sessions(month)
    for day in sessions:
        output = minutes / day
        acquire_tushare_minute_source_bounded_v2(
            TushareMinuteSourceBoundedRequestV2("000703.SZ", day, "5min"),
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            post=AuthorityPost(),
            clock=lambda: 1,
            sleep=lambda _: None,
        )
        hashes[day] = sha256((output / "acquisition-receipt.json").read_bytes())
    return (
        calendar,
        minutes,
        sha256((calendar / "acquisition-receipt.json").read_bytes()),
        hashes,
        sessions,
    )


def _capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    month: str = "202402",
    *,
    bad: str | None = None,
) -> tuple[dict[str, object], tuple[str, ...]]:
    calendar, minutes, calendar_hash, minute_hashes, sessions = _authorities(
        tmp_path, monkeypatch, month
    )
    receipt = acquire_tushare_000703_month_order_authority_v1(
        Tushare000703MonthlyOrderAuthorityRequest(month),
        token=TOKEN,
        endpoint="https://fast.xiaodefa.cn",
        output_dir=tmp_path / "out",
        calendar_authority_dir=calendar,
        minute_authority_root=minutes,
        calendar_receipt_hash=calendar_hash,
        minute_receipt_hashes=minute_hashes,
        post=FakePost(bad=bad),
        clock=iter(range(100, 10_000)).__next__,
        sleep=lambda _: None,
    )
    return receipt, sessions


def test_leap_february_worklist_is_calendar_derived_not_january_hardcoded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt, sessions = _capture(tmp_path, monkeypatch)
    declaration = json.loads((tmp_path / "out/declaration.json").read_bytes())
    assert "20240229" in sessions
    assert declaration["request"] == {
        "type": "tushare_000703_monthly_order_authority_request_v1",
        "schema_version": 1,
        "month": "202402",
    }
    assert declaration["open_sessions"] == list(sessions)
    assert len(receipt["provider_requests"]) == 1 + len(sessions) * 5
    assert receipt["acquired_at_epoch_nanoseconds"] == max(
        item["response_acquired_at_epoch_nanoseconds"]
        for item in receipt["provider_requests"]
    )


def test_verifier_rebuilds_all_calendar_and_minute_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt, _ = _capture(tmp_path, monkeypatch)
    assert verify_tushare_000703_month_order_authority_v1(
        tmp_path / "out",
        calendar_authority_dir=tmp_path / "calendar",
        minute_authority_root=tmp_path / "minutes",
    ) == receipt


@pytest.mark.parametrize("bad", ["stock_st", "daily_scope", "daily_nonterminal"])
def test_provider_exception_scope_or_nonterminal_failure_is_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    calendar, minutes, calendar_hash, minute_hashes, _ = _authorities(
        tmp_path, monkeypatch, "202402"
    )
    with pytest.raises(AcquisitionError):
        acquire_tushare_000703_month_order_authority_v1(
            Tushare000703MonthlyOrderAuthorityRequest("202402"),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=tmp_path / "out",
            calendar_authority_dir=calendar,
            minute_authority_root=minutes,
            calendar_receipt_hash=calendar_hash,
            minute_receipt_hashes=minute_hashes,
            post=FakePost(bad=bad),
            clock=lambda: 1,
            sleep=lambda _: None,
        )
    assert not (tmp_path / "out").exists()


def test_verifier_rejects_open_session_and_response_timestamp_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _capture(tmp_path, monkeypatch)
    root = tmp_path / "out"
    declaration_path = root / "declaration.json"
    declaration = json.loads(declaration_path.read_bytes())
    declaration["open_sessions"] = declaration["open_sessions"][:-1]
    declaration_path.write_bytes(json.dumps(declaration, sort_keys=True, separators=(",", ":")).encode())
    with pytest.raises(AcquisitionError):
        verify_tushare_000703_month_order_authority_v1(
            root,
            calendar_authority_dir=tmp_path / "calendar",
            minute_authority_root=tmp_path / "minutes",
        )

    _capture(tmp_path / "january", monkeypatch, month="202401")
    root = tmp_path / "january/out"
    receipt_path = root / "acquisition-receipt.json"
    receipt = json.loads(receipt_path.read_bytes())
    receipt["provider_requests"][0]["response_acquired_at_epoch_nanoseconds"] = receipt[
        "provider_requests"
    ][1]["response_acquired_at_epoch_nanoseconds"]
    receipt_path.write_bytes(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode())
    with pytest.raises(AcquisitionError):
        verify_tushare_000703_month_order_authority_v1(
            root,
            calendar_authority_dir=tmp_path / "calendar",
            minute_authority_root=tmp_path / "minutes",
        )


def test_verifier_rejects_raw_member_and_upstream_minute_hash_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _capture(tmp_path / "raw", monkeypatch)
    root = tmp_path / "raw/out"
    raw = root / "response/20240229/daily.json"
    raw.write_bytes(raw.read_bytes() + b" ")
    with pytest.raises(AcquisitionError):
        verify_tushare_000703_month_order_authority_v1(
            root,
            calendar_authority_dir=tmp_path / "raw/calendar",
            minute_authority_root=tmp_path / "raw/minutes",
        )

    _capture(tmp_path / "upstream", monkeypatch)
    root = tmp_path / "upstream/out"
    declaration_path = root / "declaration.json"
    declaration = json.loads(declaration_path.read_bytes())
    declaration["minute_receipt_sha256"]["20240229"] = "sha256:" + "0" * 64
    declaration_path.write_bytes(
        json.dumps(declaration, sort_keys=True, separators=(",", ":")).encode()
    )
    with pytest.raises(AcquisitionError):
        verify_tushare_000703_month_order_authority_v1(
            root,
            calendar_authority_dir=tmp_path / "upstream/calendar",
            minute_authority_root=tmp_path / "upstream/minutes",
        )


def test_output_is_no_clobber(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _capture(tmp_path, monkeypatch)
    calendar, minutes, calendar_hash, minute_hashes, _ = _authorities(
        tmp_path / "second", monkeypatch, "202402"
    )
    with pytest.raises(AcquisitionError, match="already exists"):
        acquire_tushare_000703_month_order_authority_v1(
            Tushare000703MonthlyOrderAuthorityRequest("202402"),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=tmp_path / "out",
            calendar_authority_dir=calendar,
            minute_authority_root=minutes,
            calendar_receipt_hash=calendar_hash,
            minute_receipt_hashes=minute_hashes,
            post=FakePost(),
            clock=lambda: 1,
            sleep=lambda _: None,
        )
