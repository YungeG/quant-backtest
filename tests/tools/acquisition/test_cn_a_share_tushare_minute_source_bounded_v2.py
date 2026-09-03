from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import RawSourceMember, SourceSnapshotProvenance, freeze_source_snapshot

from tools.acquisition._common import AcquisitionError, sha256
from tools.acquisition.cn_a_share_tushare_minute_source_bounded_v2 import (
    TushareMinuteSourceBoundedRequestV2,
    _expected_trade_times,
    acquire_tushare_minute_source_bounded_v2,
    verify_tushare_minute_source_bounded_receipt_v2,
)

TOKEN = "x" * 56
FIELDS = ["ts_code", "trade_time", "close", "open", "high", "low", "vol", "amount"]


class FakePost:
    def __init__(self, source: bytes) -> None:
        self.source = source
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def __call__(
        self, endpoint: str, body: dict[str, object], headers: dict[str, str]
    ) -> tuple[int, bytes]:
        self.calls.append((endpoint, body, headers))
        return 200, self.source


def rows() -> list[list[object]]:
    return [
        ["000703.SZ", trade_time, 10.5, 10.0, 11.0, 9.5, 100, 1_000]
        for trade_time in _expected_trade_times("20240102")
    ]


def response(items: list[list[object]]) -> bytes:
    return json.dumps(
        {
            "request_id": "synthetic-request",
            "code": 0,
            "data": {"fields": FIELDS, "items": items, "has_more": False, "count": 0},
            "msg": "",
            "detail": "synthetic",
        },
        separators=(",", ":"),
    ).encode()


def request() -> TushareMinuteSourceBoundedRequestV2:
    return TushareMinuteSourceBoundedRequestV2("000703.SZ", "20240102", "5min")


def test_capture_preserves_raw_snapshot_and_redacts_env_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    source = response(rows())
    post = FakePost(source)
    output = tmp_path / "capture"

    receipt = acquire_tushare_minute_source_bounded_v2(
        request(),
        endpoint="https://fast.xiaodefa.cn",
        output_dir=output,
        clock=lambda: 2,
        post=post,
        sleep=lambda _: None,
    )

    assert (output / "response/stk-mins.json").read_bytes() == source
    assert tuple(path.name for path in sorted(output.iterdir())) == (
        "acquisition-receipt.json",
        "response",
    )
    assert post.calls[0][0] == "https://fast.xiaodefa.cn"
    assert post.calls[0][1] == {
        "api_name": "stk_mins",
        "params": {
            "ts_code": "000703.SZ",
            "freq": "5min",
            "start_date": "2024-01-02 09:30:00",
            "end_date": "2024-01-02 15:00:00",
        },
        "fields": ",".join(FIELDS),
    }
    assert post.calls[0][2]["x-api-key"] == TOKEN
    assert receipt["source_bounded"] is True
    assert receipt["development_only"] is True
    assert receipt["anchor_strategy_eligible"] is False
    assert receipt["strategy_trade_time_count"] == 48
    assert receipt["decision_grade_eligible"] is False
    assert receipt["live_eligible"] is False
    assert receipt["snapshot"]["members"][0]["content_hash"] == (
        "sha256:" + hashlib.sha256(source).hexdigest()
    )
    assert all(TOKEN.encode() not in path.read_bytes() for path in output.rglob("*") if path.is_file())


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda values: values.pop(0), "missing or off-grid"),
        (lambda values: values.append(values[-1].copy()), "duplicate"),
        (
            lambda values: values.__setitem__(1, ["000703.SZ", "2024-01-02 12:00:00", 10.5, 10.0, 11.0, 9.5, 100, 1_000]),
            "missing or off-grid",
        ),
    ],
    ids=("missing-anchor", "duplicate", "noon"),
)
def test_rejects_missing_anchor_duplicate_or_noon_without_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate,
    message: str,
) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    items = rows()
    mutate(items)
    output = tmp_path / "rejected"

    with pytest.raises(AcquisitionError, match=message):
        acquire_tushare_minute_source_bounded_v2(
            request(),
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            clock=lambda: 2,
            post=FakePost(response(items)),
            sleep=lambda _: None,
        )
    assert not output.exists()


def test_verifier_rejects_tampered_minute_receipt_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    acquire_tushare_minute_source_bounded_v2(
        request(), endpoint="https://fast.xiaodefa.cn", output_dir=tmp_path / "capture",
        clock=lambda: 2, post=FakePost(response(rows())), sleep=lambda _: None,
    )
    receipt_bytes = (tmp_path / "capture/acquisition-receipt.json").read_bytes()
    source = (tmp_path / "capture/response/stk-mins.json").read_bytes()
    snapshot = freeze_source_snapshot(
        members=(RawSourceMember("response/stk-mins.json", source, "0644", 2, None),),
        provenance=SourceSnapshotProvenance("tushare.pro", "tushare.pro.via.xiaodefa.approved-proxy.fast.xiaodefa.cn.stk_mins.000703.sz.20240102.5min", "tushare.pro.terms", "backtest.acquisition.candidate"),
    ).snapshot
    assert snapshot is not None
    assert "fast.xiaodefa.cn" in snapshot.provenance.source_key
    assert verify_tushare_minute_source_bounded_receipt_v2(receipt_bytes, snapshot, sha256(receipt_bytes))["strategy_trade_time_count"] == 48

    with pytest.raises(AcquisitionError, match="receipt hash"):
        verify_tushare_minute_source_bounded_receipt_v2(receipt_bytes, snapshot, "sha256:" + "0" * 64)

    tampered = json.loads(receipt_bytes)
    tampered["transport_endpoint"] = "https://unapproved.example"
    tampered_bytes = json.dumps(tampered).encode()
    with pytest.raises(AcquisitionError, match="transport"):
        verify_tushare_minute_source_bounded_receipt_v2(tampered_bytes, snapshot, sha256(tampered_bytes))

    tampered = json.loads(receipt_bytes)
    tampered["snapshot"]["snapshot_id"] = "sha256:" + "0" * 64
    tampered_bytes = json.dumps(tampered).encode()
    with pytest.raises(AcquisitionError, match="snapshot identity"):
        verify_tushare_minute_source_bounded_receipt_v2(tampered_bytes, snapshot, sha256(tampered_bytes))

    tampered_snapshot = replace(snapshot, provenance=SourceSnapshotProvenance(
        "tushare.pro", "tushare.pro.via.xiaodefa.approved-proxy.fast.xiaodefa.cn.stk_mins.000703.sz.20240102.5min.tampered",
        "tushare.pro.terms", "backtest.acquisition.candidate",
    ))
    with pytest.raises(AcquisitionError, match="snapshot"):
        verify_tushare_minute_source_bounded_receipt_v2(receipt_bytes, tampered_snapshot, sha256(receipt_bytes))


def test_rejects_token_echo_without_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    output = tmp_path / "credential-echo"
    source = response(rows()).replace(b'"synthetic"', f'"{TOKEN}"'.encode())

    with pytest.raises(AcquisitionError, match="contains credential material") as raised:
        acquire_tushare_minute_source_bounded_v2(
            request(),
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            clock=lambda: 2,
            post=FakePost(source),
            sleep=lambda _: None,
        )
    assert TOKEN not in str(raised.value)
    assert not output.exists()


def test_clock_is_sampled_after_response_and_exactly_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    events: list[str] = []
    class OrderedPost(FakePost):
        def __call__(self, *args, **kwargs):
            events.append("response")
            return super().__call__(*args, **kwargs)
    receipt = acquire_tushare_minute_source_bounded_v2(request(), endpoint="https://fast.xiaodefa.cn", output_dir=tmp_path / "capture", post=OrderedPost(response(rows())), clock=lambda: (events.append("clock") or 17), sleep=lambda _: None)
    provider_request = receipt["provider_requests"][0]
    assert events == ["response", "clock"]
    assert receipt["acquired_at_epoch_nanoseconds"] == provider_request["response_acquired_at_epoch_nanoseconds"] == receipt["snapshot"]["members"][0]["acquired_at_epoch_nanoseconds"] == 17


def test_v2_verifier_rejects_v1_like_provenance_and_timestamp_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    acquire_tushare_minute_source_bounded_v2(request(), endpoint="https://fast.xiaodefa.cn", output_dir=tmp_path / "capture", post=FakePost(response(rows())), clock=lambda: 2, sleep=lambda _: None)
    root = tmp_path / "capture"
    receipt_bytes = (root / "acquisition-receipt.json").read_bytes()
    source = (root / "response/stk-mins.json").read_bytes()
    v1_snapshot = freeze_source_snapshot(members=(RawSourceMember("response/stk-mins.json", source, "0644", 2, None),), provenance=SourceSnapshotProvenance("tushare.pro", "tushare.pro.via.xiaodefa.approved-proxy.stk_mins.000703.sz.20240102.5min", "tushare.pro.terms", "backtest.acquisition.candidate")).snapshot
    assert v1_snapshot is not None
    with pytest.raises(AcquisitionError, match="snapshot"):
        verify_tushare_minute_source_bounded_receipt_v2(receipt_bytes, v1_snapshot, sha256(receipt_bytes))
    receipt = json.loads(receipt_bytes)
    receipt["provider_requests"][0]["response_acquired_at_epoch_nanoseconds"] = 3
    altered = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    snapshot = freeze_source_snapshot(members=(RawSourceMember("response/stk-mins.json", source, "0644", 2, None),), provenance=SourceSnapshotProvenance("tushare.pro", "tushare.pro.via.xiaodefa.approved-proxy.fast.xiaodefa.cn.stk_mins.000703.sz.20240102.5min", "tushare.pro.terms", "backtest.acquisition.candidate")).snapshot
    assert snapshot is not None
    with pytest.raises(AcquisitionError, match="provider request"):
        verify_tushare_minute_source_bounded_receipt_v2(altered, snapshot, sha256(altered))
