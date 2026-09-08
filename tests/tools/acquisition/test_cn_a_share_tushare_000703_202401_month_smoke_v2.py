from __future__ import annotations

import json
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import RawSourceMember, SourceSnapshotProvenance, freeze_source_snapshot

from tools.acquisition._common import AcquisitionError, sha256
from tools.acquisition.cn_a_share_tushare_000703_202401_month_smoke_v2 import (
    _WORKLIST,
    acquire_tushare_000703_202401_month_smoke_v2,
    verify_tushare_000703_202401_month_smoke_v2,
)
from tools.acquisition.cn_a_share_tushare_minute_source_bounded_v2 import TushareMinuteSourceBoundedRequestV2, acquire_tushare_minute_source_bounded_v2
from tools.acquisition.cn_a_share_tushare_proxy_trade_calendar_month_source_bounded_v1 import TushareProxyTradeCalendarMonthSourceBoundedRequestV1, acquire_tushare_proxy_trade_calendar_month_source_bounded_v1
from tools.acquisition.cn_a_share_tushare_proxy_trade_calendar_month_source_bounded_v2 import TushareProxyTradeCalendarMonthSourceBoundedRequestV2, _source_dates, acquire_tushare_proxy_trade_calendar_month_source_bounded_v2

TOKEN = "x" * 56
FIELDS = {
    "stock_basic": ["ts_code", "symbol", "name", "area", "industry", "market", "exchange", "list_status", "list_date", "delist_date"],
    "daily": ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"],
    "stk_limit": ["trade_date", "ts_code", "up_limit", "down_limit"],
    "stock_st": ["ts_code", "trade_date", "name"],
    "suspend_d": ["ts_code", "trade_date", "suspend_timing", "suspend_type"],
    "trade_cal": ["exchange", "cal_date", "is_open", "pretrade_date"],
    "stk_mins": ["ts_code", "trade_time", "close", "open", "high", "low", "vol", "amount"],
}


def response(fields: list[str], rows: list[list[object]], terminal: bool = True) -> bytes:
    return json.dumps({"request_id": "id", "code": 0, "data": {"fields": fields, "items": rows, "has_more": not terminal, "count": 0}, "msg": "", "detail": ""}).encode()


def calendar_response() -> bytes:
    previous = "20231130"
    rows = []
    for day in _source_dates("202401"):
        open_ = day in _WORKLIST or day == "20231229"
        rows.append(["SZSE", day, int(open_), previous])
        if open_:
            previous = day
    return response(FIELDS["trade_cal"], rows)


def minute_response(day: str) -> bytes:
    from tools.acquisition.cn_a_share_tushare_minute_source_bounded_v2 import _expected_trade_times
    return response(FIELDS["stk_mins"], [["000703.SZ", time, 10, 10, 10, 10, 0, 0] for time in _expected_trade_times(day)])


class AuthorityPost:
    def __call__(self, _url: str, body: dict[str, object], _headers: dict[str, str]) -> tuple[int, bytes]:
        params = body["params"]
        return 200, calendar_response() if body["api_name"] == "trade_cal" else minute_response(str(params["start_date"])[:10].replace("-", ""))


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
            if self.bad == "negative-return":
                rows = [["000703.SZ", day, 10, 10, 9, 9, 10, -1, -10, 100, 1000]]
            if self.bad == "daily-ohlc":
                rows = [["000703.SZ", day, 12, 11, 9, 10, 10, 0, 0, 100, 1000]]
        elif api == "stk_limit":
            rows = [[day, "000703.SZ", 11, 9]]
        else:
            rows = []
        if self.bad == "stock_st" and api == "stock_st": rows = [["000703.SZ", day, "*ST"]]
        if self.bad == "suspend" and api == "suspend_d": rows = [["000703.SZ", day, "09:30", params["suspend_type"]]]
        if self.bad == "daily-schema" and api == "daily": fields = list(reversed(fields))
        if self.bad == "daily-scope" and api == "daily": rows[0][1] = "20240101"
        if self.bad == "limit-schema" and api == "stk_limit": fields = list(reversed(fields))
        if self.bad == "limit-scope" and api == "stk_limit": rows[0][0] = "20240101"
        return 200, response(
            fields,
            rows,
            terminal=not (
                (self.bad == "daily-nonterminal" and api == "daily")
                or (self.bad == "limit-nonterminal" and api == "stk_limit")
            ),
        )


def authorities(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, str, dict[str, str]]:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    calendar = tmp_path / "calendar"
    acquire_tushare_proxy_trade_calendar_month_source_bounded_v2(TushareProxyTradeCalendarMonthSourceBoundedRequestV2("SZSE", "202401"), endpoint="https://fast.xiaodefa.cn", output_dir=calendar, post=AuthorityPost(), clock=lambda: 1, sleep=lambda _: None)
    minutes = tmp_path / "minutes"; hashes = {}
    for day in _WORKLIST:
        output = minutes / day
        acquire_tushare_minute_source_bounded_v2(TushareMinuteSourceBoundedRequestV2("000703.SZ", day, "5min"), endpoint="https://fast.xiaodefa.cn", output_dir=output, post=AuthorityPost(), clock=lambda: 1, sleep=lambda _: None)
        receipt = (output / "acquisition-receipt.json").read_bytes()
        hashes[day] = sha256(receipt)
    return calendar, minutes, sha256((calendar / "acquisition-receipt.json").read_bytes()), hashes


def capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    post: FakePost,
    *,
    sleep=lambda _: None,
    **overrides: object,
) -> dict[str, object]:
    calendar, minutes, calendar_hash, minute_hashes = authorities(tmp_path, monkeypatch)
    return acquire_tushare_000703_202401_month_smoke_v2(
        token=TOKEN,
        endpoint="https://fast.xiaodefa.cn",
        output_dir=tmp_path / "out",
        calendar_authority_dir=calendar,
        minute_authority_root=minutes,
        calendar_receipt_hash=calendar_hash,
        minute_receipt_hashes=minute_hashes,
        post=post,
        clock=iter(range(100, 1000)).__next__,
        sleep=sleep,
        **overrides,
    )


def test_full_monthly_fake_post_success_uses_strict_v2_calendar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt = capture(tmp_path, monkeypatch, FakePost())
    declaration = json.loads((tmp_path / "out/declaration.json").read_bytes())
    assert len(receipt["provider_requests"]) == 1 + len(_WORKLIST) * 5
    assert declaration["calendar_receipt_sha256"] == sha256((tmp_path / "calendar/acquisition-receipt.json").read_bytes())
    assert declaration["minute_receipt_sha256"] == {
        day: sha256((tmp_path / "minutes" / day / "acquisition-receipt.json").read_bytes())
        for day in _WORKLIST
    }
    assert declaration["negative_evidence"] == {
        "stock_st_terminal_zero": True,
        "suspend_d_s_terminal_zero": True,
        "suspend_d_r_terminal_zero": True,
        "classification": "STANDARD + NORMAL",
        "corporate_action_absence_claimed": False,
    }
    assert all(TOKEN.encode() not in path.read_bytes() for path in (tmp_path / "out").rglob("*") if path.is_file())



def test_monthly_verifier_attests_all_retained_authorities(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt = capture(tmp_path, monkeypatch, FakePost())
    assert receipt["snapshot"]["provenance"]["source_key"] == "tushare.pro.via.xiaodefa.approved-proxy.fast.xiaodefa.cn.000703.sz.202401.month-development-smoke"
    assert verify_tushare_000703_202401_month_smoke_v2(
        tmp_path / "out", calendar_authority_dir=tmp_path / "calendar", minute_authority_root=tmp_path / "minutes"
    ) == receipt


@pytest.mark.parametrize("target", [
    "response/20240131/stock-st.json",
    "declaration-raw-member-hash",
    "provider-request-hash",
    "zero-row-count-bool",
    "calendar-receipt-hash",
    "minute-receipt-hash",
])
def test_monthly_verifier_rejects_representative_retained_authority_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    capture(tmp_path, monkeypatch, FakePost())
    root = tmp_path / "out"
    if target.startswith("response/"):
        path = root / target
        path.write_bytes(path.read_bytes() + b" ")
    elif target == "declaration-raw-member-hash":
        path = root / "declaration.json"
        declaration = json.loads(path.read_bytes())
        declaration["raw_members"]["response/20240131/stock-st.json"] = "sha256:" + "0" * 64
        path.write_bytes(json.dumps(declaration, sort_keys=True, separators=(",", ":")).encode())
        receipt_path = root / "acquisition-receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        receipt["declaration_sha256"] = sha256(path.read_bytes())
        receipt_path.write_bytes(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode())
    elif target == "provider-request-hash":
        path = root / "acquisition-receipt.json"
        receipt = json.loads(path.read_bytes())
        receipt["provider_requests"][-1]["response_sha256"] = "sha256:" + "0" * 64
        path.write_bytes(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode())
    elif target == "zero-row-count-bool":
        path = root / "acquisition-receipt.json"
        receipt = json.loads(path.read_bytes())
        receipt["provider_requests"][-1]["returned_row_count"] = False
        path.write_bytes(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode())
    else:
        path = root / "declaration.json"
        declaration = json.loads(path.read_bytes())
        key = "calendar_receipt_sha256" if target == "calendar-receipt-hash" else "minute_receipt_sha256"
        if key == "calendar_receipt_sha256":
            declaration[key] = "sha256:" + "0" * 64
        else:
            declaration[key][_WORKLIST[0]] = "sha256:" + "0" * 64
        path.write_bytes(json.dumps(declaration, sort_keys=True, separators=(",", ":")).encode())
        receipt_path = root / "acquisition-receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        receipt["declaration_sha256"] = sha256(path.read_bytes())
        receipt_path.write_bytes(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode())
    with pytest.raises(AcquisitionError):
        verify_tushare_000703_202401_month_smoke_v2(
            root, calendar_authority_dir=tmp_path / "calendar", minute_authority_root=tmp_path / "minutes"
        )


def test_monthly_capture_spaces_successful_proxy_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pauses: list[float] = []
    receipt = capture(tmp_path, monkeypatch, FakePost(), sleep=pauses.append)
    assert len(pauses) == len(receipt["provider_requests"]) - 1
    assert set(pauses) == {0.5}


def test_negative_daily_return_is_valid_monthly_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt = capture(tmp_path, monkeypatch, FakePost(bad="negative-return"))
    assert receipt["source_bounded"] is True
    assert (tmp_path / "out").is_dir()


@pytest.mark.parametrize("bad", ["stock_st", "suspend", "daily-schema", "daily-scope", "daily-ohlc", "daily-nonterminal", "limit-schema", "limit-scope", "limit-nonterminal"])
def test_present_exception_or_daily_limit_schema_scope_nonterminal_failure_is_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: str) -> None:
    with pytest.raises(AcquisitionError):
        capture(tmp_path, monkeypatch, FakePost(bad=bad))
    assert not (tmp_path / "out").exists()


def test_legacy_non_endpoint_bound_calendar_receipt_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calendar, minutes, _calendar_hash, hashes = authorities(tmp_path, monkeypatch)
    legacy = tmp_path / "legacy"; (legacy / "response").mkdir(parents=True)
    source = (calendar / "response/trade-calendar.json").read_bytes()
    receipt = json.loads((calendar / "acquisition-receipt.json").read_bytes())
    snapshot = freeze_source_snapshot(members=(RawSourceMember("response/trade-calendar.json", source, "0644", 1, None),), provenance=SourceSnapshotProvenance("tushare.pro", "tushare.pro.via.xiaodefa.approved-proxy.trade_cal.szse.202401", "tushare.pro.terms", "backtest.acquisition.candidate")).snapshot
    assert snapshot is not None
    receipt["snapshot"] = snapshot.to_canonical_dict()
    receipt_bytes = json.dumps(receipt, separators=(",", ":")).encode()
    (legacy / "response/trade-calendar.json").write_bytes(source)
    (legacy / "acquisition-receipt.json").write_bytes(receipt_bytes)
    with pytest.raises(AcquisitionError, match="snapshot identity"):
        acquire_tushare_000703_202401_month_smoke_v2(token=TOKEN, endpoint="https://fast.xiaodefa.cn", output_dir=tmp_path / "out", calendar_authority_dir=legacy, minute_authority_root=minutes, calendar_receipt_hash=sha256(receipt_bytes), minute_receipt_hashes=hashes, post=FakePost(), clock=lambda: 1, sleep=lambda _: None)
    assert not (tmp_path / "out").exists()


def test_calendar_and_minute_hash_mismatch_are_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calendar, minutes, calendar_hash, hashes = authorities(tmp_path, monkeypatch)
    for bad_calendar_hash, bad_hashes in (("sha256:" + "0" * 64, hashes), (calendar_hash, {**hashes, _WORKLIST[0]: "sha256:" + "0" * 64})):
        with pytest.raises(AcquisitionError, match="receipt hash"):
            acquire_tushare_000703_202401_month_smoke_v2(token=TOKEN, endpoint="https://fast.xiaodefa.cn", output_dir=tmp_path / f"out-{bad_calendar_hash[-1]}", calendar_authority_dir=calendar, minute_authority_root=minutes, calendar_receipt_hash=bad_calendar_hash, minute_receipt_hashes=bad_hashes, post=FakePost(), clock=lambda: 1, sleep=lambda _: None)
    assert not list(tmp_path.glob("out-*"))


def test_monthly_response_times_are_unique_and_exactly_three_way_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt = capture(tmp_path, monkeypatch, FakePost())
    declaration = json.loads((tmp_path / "out/declaration.json").read_bytes())
    requests = receipt["provider_requests"]
    times = [item["response_acquired_at_epoch_nanoseconds"] for item in requests]
    snapshot_times = {item["member_key"]: item["acquired_at_epoch_nanoseconds"] for item in receipt["snapshot"]["members"]}
    assert len(times) == len(set(times))
    assert receipt["acquired_at_epoch_nanoseconds"] == max(times)
    for item in requests:
        member = item["member_key"]
        assert snapshot_times[member] == item["response_acquired_at_epoch_nanoseconds"]
        assert declaration["raw_members"][member] == {"sha256": item["response_sha256"], "acquired_at_epoch_nanoseconds": item["response_acquired_at_epoch_nanoseconds"]}


def test_monthly_verifier_rejects_swapped_response_time_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    capture(tmp_path, monkeypatch, FakePost())
    root = tmp_path / "out"
    receipt_path = root / "acquisition-receipt.json"
    receipt = json.loads(receipt_path.read_bytes())
    receipt["provider_requests"][0]["response_acquired_at_epoch_nanoseconds"] = receipt["provider_requests"][1]["response_acquired_at_epoch_nanoseconds"]
    receipt_path.write_bytes(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode())
    with pytest.raises(AcquisitionError):
        verify_tushare_000703_202401_month_smoke_v2(root, calendar_authority_dir=tmp_path / "calendar", minute_authority_root=tmp_path / "minutes")


def test_monthly_capture_rejects_v1_calendar_authority_atomically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    calendar = tmp_path / "calendar-v1"
    acquire_tushare_proxy_trade_calendar_month_source_bounded_v1(
        TushareProxyTradeCalendarMonthSourceBoundedRequestV1("SZSE", "202401"),
        endpoint="https://fast.xiaodefa.cn", output_dir=calendar,
        acquired_at_epoch_nanoseconds=1, post=AuthorityPost(), sleep=lambda _: None,
    )
    minutes = tmp_path / "minutes"; hashes: dict[str, str] = {}
    for day in _WORKLIST:
        output = minutes / day
        acquire_tushare_minute_source_bounded_v2(TushareMinuteSourceBoundedRequestV2("000703.SZ", day, "5min"), endpoint="https://fast.xiaodefa.cn", output_dir=output, post=AuthorityPost(), clock=lambda: 1, sleep=lambda _: None)
        hashes[day] = sha256((output / "acquisition-receipt.json").read_bytes())
    calendar_bytes = (calendar / "acquisition-receipt.json").read_bytes()
    with pytest.raises(AcquisitionError, match="unexpected fields|type or schema"):
        acquire_tushare_000703_202401_month_smoke_v2(token=TOKEN, endpoint="https://fast.xiaodefa.cn", output_dir=tmp_path / "out", calendar_authority_dir=calendar, minute_authority_root=minutes, calendar_receipt_hash=sha256(calendar_bytes), minute_receipt_hashes=hashes, post=FakePost(), clock=lambda: 1, sleep=lambda _: None)
    assert not (tmp_path / "out").exists()
