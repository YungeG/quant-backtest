from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)

from tools.acquisition import _common
from tools.acquisition.binance_usdm import (
    AcquisitionError,
    BinanceFundingHistoryRequest,
    acquire_funding_history,
)

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "fixtures/market_data/providers/binance_usdm/funding-history-source-bounded-v2"
)
TOKEN_SENTINEL = "redaction-sentinel-value"
REQUEST = BinanceFundingHistoryRequest(
    "BTCUSDT", 1_704_067_200_000, 1_704_153_599_999, 100
)
ACQUIRED_AT = 1_787_304_863_983_843_230


class FakeGet:
    def __init__(self, response: bytes | Callable[[str], bytes]) -> None:
        self.response = response
        self.calls: list[str] = []

    def __call__(self, url: str) -> tuple[int, bytes]:
        self.calls.append(url)
        return 200, self.response(url) if callable(self.response) else self.response


def snapshot_for(response_bytes: bytes) -> dict[str, object]:
    return freeze_source_snapshot(
        members=(
            RawSourceMember(
                "response/funding-history.json",
                response_bytes,
                "0644",
                ACQUIRED_AT,
                None,
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="binance.fapi",
            source_key=(
                "binance.fapi.funding_rate_history.btcusdt.1704067200000.1704153599999"
            ),
            license_ref="binance.api.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot.to_canonical_dict()


def acquire(
    output: Path,
    get: FakeGet,
    *,
    acquired_at_epoch_nanoseconds: int = ACQUIRED_AT,
) -> dict[str, object]:
    return acquire_funding_history(
        REQUEST,
        output_dir=output,
        acquired_at_epoch_nanoseconds=acquired_at_epoch_nanoseconds,
        get=get,
        sleep=lambda _: None,
    )


def test_source_bounded_v2_replays_exact_live_capture_and_preserves_canonical_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writes: list[str] = []
    real_open = _common.os.open

    def tracking_open(
        path: os.PathLike[str] | str,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if flags & os.O_WRONLY:
            writes.append(str(path))
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(_common.os, "open", tracking_open)

    response_bytes = (FIXTURE_ROOT / "response/funding-history.json").read_bytes()
    expected_receipt = json.loads(
        (FIXTURE_ROOT / "acquisition-receipt.json").read_bytes()
    )
    output = tmp_path / "capture"
    post = FakeGet(response_bytes)
    result = acquire(output, post)

    assert post.calls == [REQUEST.url]
    assert {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    } == {"funding-history.json", "acquisition-receipt.json"}
    assert writes and Path(writes[-1]).name == "acquisition-receipt.json"
    assert result == expected_receipt
    assert result["snapshot"] == snapshot_for(response_bytes)
    assert (output / "funding-history.json").read_bytes() == response_bytes
    assert (output / "acquisition-receipt.json").read_bytes() == _common.json_bytes(
        result
    )
    assert TOKEN_SENTINEL not in (output / "acquisition-receipt.json").read_text()


def test_source_bounded_v2_no_clobber_before_transport_and_race_before_publish(
    tmp_path: Path,
) -> None:
    response_bytes = (FIXTURE_ROOT / "response/funding-history.json").read_bytes()

    existing = tmp_path / "existing"
    existing.mkdir()
    marker = existing / "keep"
    marker.write_bytes(b"preserve")
    with pytest.raises(AcquisitionError, match="already exists"):
        acquire(existing, FakeGet(response_bytes))
    assert marker.read_bytes() == b"preserve"

    raced = tmp_path / "raced"
    calls = 0

    def claim_before_publish(_: str) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 1:
            raced.mkdir()
            (raced / "foreign").write_bytes(b"foreign")
        return response_bytes

    with pytest.raises(AcquisitionError, match="already exists"):
        acquire(raced, FakeGet(claim_before_publish))

    assert calls == 1
    assert (raced / "foreign").read_bytes() == b"foreign"
    assert not (raced / "acquisition-receipt.json").exists()


@pytest.mark.parametrize(
    (
        "response",
        "message",
    ),
    (
        (
            (
                b'[{"symbol":"BTCUSDT","fundingTime":1704067200000,'
                b'"fundingRate":"Infinity","markPrice":"42313.90000000",'
                b'"rateType":"Regular"}]'
            ),
            "violates request scope",
        ),
        (
            (
                b'[{"symbol":"ETHUSDT","fundingTime":1704067200000,'
                b'"fundingRate":"0.00037409","markPrice":"42313.90000000",'
                b'"rateType":"Regular"}]'
            ),
            "violates request scope",
        ),
        (
            (
                b'[{"symbol":"BTCUSDT","fundingTime":1704153600000,'
                b'"fundingRate":"0.00037409","markPrice":"42313.90000000",'
                b'"rateType":"Regular"}]'
            ),
            "violates request scope",
        ),
        (
            b"{bad json",
            "valid JSON",
        ),
        (
            (
                b'[{"symbol":"BTCUSDT","fundingTime":1704067200000,'
                b'"fundingRate":0.1,'
                b'"markPrice":"42313.90000000","rateType":"Regular"}]'
            ),
            "violates request scope",
        ),
    ),
)
def test_source_bounded_v2_rejects_malformed_or_out_of_scope_payloads(
    tmp_path: Path, response: bytes, message: str
) -> None:
    with pytest.raises(AcquisitionError, match=message) as error:
        acquire(tmp_path / "bad", FakeGet(response))
    assert TOKEN_SENTINEL not in str(error.value)
    assert error.value.__context__ is None if "valid JSON" not in message else True
    assert not (tmp_path / "bad").exists()


def test_source_bounded_v2_does_not_leak_secret_material_in_failure(
    tmp_path: Path,
) -> None:
    malicious = (
        b'[{"symbol":"BTCUSDT","fundingTime":1704067200000,'
        b'"fundingRate":"0.00037409","markPrice":"' + TOKEN_SENTINEL.encode() + b'",'
        b'"rateType":"Regular"}]'
    )
    with pytest.raises(AcquisitionError, match="violates request scope") as error:
        acquire(tmp_path / "secret", FakeGet(malicious))
    assert TOKEN_SENTINEL not in str(error.value)
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
