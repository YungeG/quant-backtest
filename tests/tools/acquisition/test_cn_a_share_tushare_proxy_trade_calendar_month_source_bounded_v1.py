from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)

from tools.acquisition._common import AcquisitionError
from tools.acquisition.cn_a_share_tushare_proxy_trade_calendar_month_source_bounded_v1 import (
    TushareProxyTradeCalendarMonthSourceBoundedRequestV1,
    _month_dates,
    _source_dates,
    acquire_tushare_proxy_trade_calendar_month_source_bounded_v1,
    verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v1,
)

TOKEN = "x" * 56
FIELDS = ["exchange", "cal_date", "is_open", "pretrade_date"]


class FakePost:
    def __init__(self, source: bytes) -> None:
        self.source = source
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def __call__(self, endpoint: str, body: dict[str, object], headers: dict[str, str]) -> tuple[int, bytes]:
        self.calls.append((endpoint, body, headers))
        return 200, self.source


def rows() -> list[list[object]]:
    previous_open = "20231229"
    result = []
    for calendar_date in _source_dates("202402"):
        is_open = int(datetime.strptime(calendar_date, "%Y%m%d").weekday() < 5)
        result.append(["SZSE", calendar_date, is_open, previous_open])
        if is_open:
            previous_open = calendar_date
    return result


def response(items: list[list[object]], *, has_more: bool = False) -> bytes:
    return json.dumps({
        "request_id": "synthetic-request",
        "code": 0,
        "data": {"fields": FIELDS, "items": items, "has_more": has_more, "count": 0},
        "msg": "",
        "detail": "synthetic",
    }, separators=(",", ":")).encode()


def request() -> TushareProxyTradeCalendarMonthSourceBoundedRequestV1:
    return TushareProxyTradeCalendarMonthSourceBoundedRequestV1("SZSE", "202402")


def receipt_hash(receipt_bytes: bytes) -> str:
    return "sha256:" + hashlib.sha256(receipt_bytes).hexdigest()


def acquire(tmp_path: Path, source: bytes) -> tuple[dict[str, object], FakePost]:
    post = FakePost(source)
    receipt = acquire_tushare_proxy_trade_calendar_month_source_bounded_v1(
        request(), endpoint="https://fast.xiaodefa.cn", output_dir=tmp_path / "capture",
        acquired_at_epoch_nanoseconds=1, post=post, sleep=lambda _: None,
    )
    return receipt, post


def test_capture_exact_covers_reversed_rows_and_preserves_raw_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    source = response(list(reversed(rows())))
    receipt, post = acquire(tmp_path, source)
    output = tmp_path / "capture"

    assert (output / "response/trade-calendar.json").read_bytes() == source
    assert post.calls[0][1] == {
        "api_name": "trade_cal",
        "params": {"exchange": "SZSE", "start_date": "20240101", "end_date": "20240229"},
        "fields": ",".join(FIELDS),
    }
    assert post.calls[0][2]["x-api-key"] == TOKEN
    assert receipt["source_bounded"] is True
    assert receipt["development_only"] is True
    assert receipt["calendar_row_count"] == 60
    assert receipt["target_calendar_row_count"] == 29
    assert receipt["open_sessions"] == [
        "20240201", "20240202", "20240205", "20240206", "20240207",
        "20240208", "20240209", "20240212", "20240213", "20240214",
        "20240215", "20240216", "20240219", "20240220", "20240221",
        "20240222", "20240223", "20240226", "20240227", "20240228",
        "20240229",
    ]
    assert receipt["open_session_count"] == 21
    assert receipt["open_day_count"] == 21
    assert receipt["decision_grade_eligible"] is False
    assert receipt["live_eligible"] is False
    assert receipt["deployment_authorized"] is False
    assert receipt["provider_requests"][0]["response_sha256"] == "sha256:" + hashlib.sha256(source).hexdigest()
    assert all(TOKEN.encode() not in path.read_bytes() for path in output.rglob("*") if path.is_file())


def test_open_sessions_are_chronological_and_independent_of_provider_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    normal, _ = acquire(tmp_path / "normal", response(rows()))
    reversed_, _ = acquire(tmp_path / "reversed", response(list(reversed(rows()))))

    assert normal["open_sessions"] == reversed_["open_sessions"]
    assert normal["open_session_count"] == reversed_["open_session_count"]


def test_receipt_verification_binds_raw_snapshot_worklist_and_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    receipt, _ = acquire(tmp_path, response(rows()))
    receipt_bytes = (tmp_path / "capture/acquisition-receipt.json").read_bytes()
    source = (tmp_path / "capture/response/trade-calendar.json").read_bytes()
    snapshot = freeze_source_snapshot(
        members=(RawSourceMember("response/trade-calendar.json", source, "0644", 1, None),),
        provenance=SourceSnapshotProvenance(
            "tushare.pro",
            "tushare.pro.via.xiaodefa.approved-proxy.trade_cal.fast.xiaodefa.cn.szse.202402",
            "tushare.pro.terms",
            "backtest.acquisition.candidate",
        ),
    ).snapshot
    assert snapshot is not None
    assert verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v1(
        receipt_bytes, snapshot, receipt_hash(receipt_bytes)
    ) == receipt

    substituted_source = response(rows(), has_more=False) + b"\n"
    substituted_snapshot = freeze_source_snapshot(
        members=(RawSourceMember("response/trade-calendar.json", substituted_source, "0644", 1, None),),
        provenance=snapshot.provenance,
    ).snapshot
    assert substituted_snapshot is not None
    with pytest.raises(AcquisitionError, match="snapshot identity|provider response"):
        verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v1(
            receipt_bytes, substituted_snapshot, receipt_hash(receipt_bytes)
        )

    substituted_worklist = dict(receipt)
    substituted_worklist["open_sessions"] = []
    substituted_worklist["open_session_count"] = 0
    with pytest.raises(AcquisitionError, match="open-session worklist"):
        verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v1(
            json.dumps(substituted_worklist).encode(), snapshot,
            receipt_hash(json.dumps(substituted_worklist).encode())
        )

    substituted_identity = dict(receipt)
    substituted_identity["snapshot"] = substituted_snapshot.to_canonical_dict()
    with pytest.raises(AcquisitionError, match="snapshot identity"):
        verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v1(
            json.dumps(substituted_identity).encode(), snapshot,
            receipt_hash(json.dumps(substituted_identity).encode())
        )


def test_receipt_verification_rejects_endpoint_substitution_by_snapshot_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    receipt, _ = acquire(tmp_path, response(rows()))
    receipt_bytes = (tmp_path / "capture/acquisition-receipt.json").read_bytes()
    source = (tmp_path / "capture/response/trade-calendar.json").read_bytes()
    snapshot = freeze_source_snapshot(
        members=(RawSourceMember("response/trade-calendar.json", source, "0644", 1, None),),
        provenance=SourceSnapshotProvenance(
            "tushare.pro",
            "tushare.pro.via.xiaodefa.approved-proxy.trade_cal.fast.xiaodefa.cn.szse.202402",
            "tushare.pro.terms",
            "backtest.acquisition.candidate",
        ),
    ).snapshot
    assert snapshot is not None
    tampered = dict(receipt)
    tampered["transport_endpoint"] = "https://tt.xiaodefa.cn"
    tampered_bytes = json.dumps(tampered).encode()
    with pytest.raises(AcquisitionError, match="snapshot identity"):
        verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v1(
            tampered_bytes, snapshot, receipt_hash(tampered_bytes)
        )


def test_receipt_verification_rejects_attempt_substitution_by_receipt_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    receipt, _ = acquire(tmp_path, response(rows()))
    receipt_bytes = (tmp_path / "capture/acquisition-receipt.json").read_bytes()
    source = (tmp_path / "capture/response/trade-calendar.json").read_bytes()
    snapshot = freeze_source_snapshot(
        members=(RawSourceMember("response/trade-calendar.json", source, "0644", 1, None),),
        provenance=SourceSnapshotProvenance(
            "tushare.pro",
            "tushare.pro.via.xiaodefa.approved-proxy.trade_cal.fast.xiaodefa.cn.szse.202402",
            "tushare.pro.terms",
            "backtest.acquisition.candidate",
        ),
    ).snapshot
    assert snapshot is not None
    tampered_request = dict(receipt["provider_requests"][0])
    tampered_request["attempts"] = 2
    tampered = dict(receipt)
    tampered["provider_requests"] = [tampered_request]
    with pytest.raises(AcquisitionError, match="receipt hash"):
        verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v1(
            json.dumps(tampered).encode(), snapshot, receipt_hash(receipt_bytes)
        )


def test_receipt_verification_rejects_expected_receipt_hash_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    _, _ = acquire(tmp_path, response(rows()))
    receipt_bytes = (tmp_path / "capture/acquisition-receipt.json").read_bytes()
    source = (tmp_path / "capture/response/trade-calendar.json").read_bytes()
    snapshot = freeze_source_snapshot(
        members=(RawSourceMember("response/trade-calendar.json", source, "0644", 1, None),),
        provenance=SourceSnapshotProvenance(
            "tushare.pro",
            "tushare.pro.via.xiaodefa.approved-proxy.trade_cal.fast.xiaodefa.cn.szse.202402",
            "tushare.pro.terms",
            "backtest.acquisition.candidate",
        ),
    ).snapshot
    assert snapshot is not None
    with pytest.raises(AcquisitionError, match="receipt hash"):
        verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v1(
            receipt_bytes, snapshot, "sha256:" + "0" * 64
        )


@pytest.mark.parametrize(
    "field",
    (
        "calendar_row_count", "target_calendar_row_count", "open_session_count", "open_day_count",
        "returned_row_count", "response_byte_count", "attempts",
    ),
)
def test_receipt_verification_rejects_boolean_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    receipt, _ = acquire(tmp_path, response(rows()))
    source = (tmp_path / "capture/response/trade-calendar.json").read_bytes()
    snapshot = freeze_source_snapshot(
        members=(RawSourceMember("response/trade-calendar.json", source, "0644", 1, None),),
        provenance=SourceSnapshotProvenance(
            "tushare.pro",
            "tushare.pro.via.xiaodefa.approved-proxy.trade_cal.fast.xiaodefa.cn.szse.202402",
            "tushare.pro.terms",
            "backtest.acquisition.candidate",
        ),
    ).snapshot
    assert snapshot is not None
    tampered = dict(receipt)
    if field in {"returned_row_count", "response_byte_count", "attempts"}:
        provider_request = dict(receipt["provider_requests"][0])
        provider_request[field] = False
        tampered["provider_requests"] = [provider_request]
    else:
        tampered[field] = False
    tampered_bytes = json.dumps(tampered).encode()
    with pytest.raises(AcquisitionError, match="open-session worklist|provider request"):
        verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v1(
            tampered_bytes, snapshot, receipt_hash(tampered_bytes)
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("calendar_row_count", 0),
        ("target_calendar_row_count", 0),
        ("open_day_count", 0),
    ],
)
def test_receipt_verification_rejects_derived_count_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: int
) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    receipt, _ = acquire(tmp_path, response(rows()))
    source = (tmp_path / "capture/response/trade-calendar.json").read_bytes()
    snapshot = freeze_source_snapshot(
        members=(RawSourceMember("response/trade-calendar.json", source, "0644", 1, None),),
        provenance=SourceSnapshotProvenance(
            "tushare.pro",
            "tushare.pro.via.xiaodefa.approved-proxy.trade_cal.fast.xiaodefa.cn.szse.202402",
            "tushare.pro.terms",
            "backtest.acquisition.candidate",
        ),
    ).snapshot
    assert snapshot is not None
    tampered = dict(receipt)
    tampered[field] = value
    with pytest.raises(AcquisitionError, match="open-session worklist"):
        verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v1(
            json.dumps(tampered).encode(), snapshot,
            receipt_hash(json.dumps(tampered).encode())
        )

    tampered_request = dict(receipt["provider_requests"][0])
    tampered_request["fields"] = "exchange,cal_date"
    tampered = dict(receipt)
    tampered["provider_requests"] = [tampered_request]
    with pytest.raises(AcquisitionError, match="provider request"):
        verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v1(
            json.dumps(tampered).encode(), snapshot,
            receipt_hash(json.dumps(tampered).encode())
        )

    tampered_request = dict(receipt["provider_requests"][0])
    tampered_request["returned_row_count"] = 0
    tampered = dict(receipt)
    tampered["provider_requests"] = [tampered_request]
    with pytest.raises(AcquisitionError, match="row count"):
        verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v1(
            json.dumps(tampered).encode(), snapshot,
            receipt_hash(json.dumps(tampered).encode())
        )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda values: values.pop(), "does not exact-cover"),
        (lambda values: values.append(values[-1].copy()), "duplicate"),
        (lambda values: values.__setitem__(0, ["SSE", *values[0][1:]]), "violates request scope"),
    ],
    ids=("missing", "duplicate", "wrong-calendar"),
)
def test_rejects_missing_duplicate_or_wrong_calendar_without_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutate, message: str
) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    items = rows()
    mutate(items)
    with pytest.raises(AcquisitionError, match=message):
        acquire(tmp_path, response(items))
    assert not (tmp_path / "capture").exists()


def test_rejects_wrong_pretrade_anchor_without_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    items = rows()
    items[len(_month_dates("202401"))][3] = "20240101"
    with pytest.raises(AcquisitionError, match="invalid pretrade_date semantics"):
        acquire(tmp_path, response(items))
    assert not (tmp_path / "capture").exists()


def test_rejects_nonterminal_pagination_without_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    with pytest.raises(AcquisitionError, match="not terminal"):
        acquire(tmp_path, response(rows(), has_more=True))
    assert not (tmp_path / "capture").exists()


def test_rejects_token_echo_without_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    source = response(rows()).replace(b'"synthetic"', f'"{TOKEN}"'.encode())
    with pytest.raises(AcquisitionError, match="contains credential material") as raised:
        acquire(tmp_path, source)
    assert TOKEN not in str(raised.value)
    assert not (tmp_path / "capture").exists()


@pytest.mark.parametrize("exchange, month", [("SSE", "202402"), ("SZSE", "202413"), ("SZSE", "2024 2")])
def test_request_requires_exact_szse_and_real_month(exchange: str, month: str) -> None:
    with pytest.raises(ValueError):
        TushareProxyTradeCalendarMonthSourceBoundedRequestV1(exchange, month)


def test_rejects_noncanonical_environment_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN + " ")
    with pytest.raises(AcquisitionError, match="exact 56-character"):
        acquire(tmp_path, response(rows()))
    assert not (tmp_path / "capture").exists()
