from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.acquisition.binance_usdm import (
    AcquisitionError,
    BinanceArchiveRequest,
    BinanceFundingHistoryRequest,
    acquire_archive,
    acquire_funding_history,
)


class FakeGet:
    def __init__(self, responses: dict[str, tuple[tuple[int, bytes], ...]]) -> None:
        self.responses = {url: list(values) for url, values in responses.items()}
        self.calls: list[str] = []

    def __call__(self, url: str) -> tuple[int, bytes]:
        self.calls.append(url)
        return self.responses[url].pop(0)


def test_checksummed_archive_acquisition_is_atomic_and_repeatable(tmp_path: Path) -> None:
    request = BinanceArchiveRequest("ETHUSDT", "aggTrades", "2024-03-01")
    archive = b"PK\x03\x04exact-provider-archive"
    digest = hashlib.sha256(archive).hexdigest()
    checksum = f"{digest}  ETHUSDT-aggTrades-2024-03-01.zip\n".encode()
    fetch = FakeGet(
        {
            request.checksum_url: ((500, b""), (200, checksum)),
            request.archive_url: ((200, archive),),
        }
    )

    output = tmp_path / "capture"
    result = acquire_archive(
        request,
        output_dir=output,
        acquired_at_epoch_nanoseconds=1_800_000_000_000_000_000,
        get=fetch,
        sleep=lambda _: None,
    )

    assert (output / "ETHUSDT-aggTrades-2024-03-01.zip").read_bytes() == archive
    assert (output / "ETHUSDT-aggTrades-2024-03-01.zip.CHECKSUM").read_bytes() == checksum
    receipt = json.loads((output / "acquisition-receipt.json").read_text())
    assert receipt == result
    assert receipt["archive_sha256"] == "sha256:" + digest
    assert receipt["archive_attempts"] == 1
    assert receipt["checksum_attempts"] == 2
    assert receipt["snapshot"]["members"][0]["member_key"].endswith(".zip")
    assert receipt["snapshot"]["members"][0]["declared_sha256"] == receipt["archive_sha256"]
    assert receipt["snapshot"]["members"][1]["declared_sha256"] is None

    repeated = acquire_archive(
        request,
        output_dir=tmp_path / "repeat",
        acquired_at_epoch_nanoseconds=1_800_000_000_000_000_000,
        get=FakeGet(
            {
                request.checksum_url: ((200, checksum),),
                request.archive_url: ((200, archive),),
            }
        ),
        sleep=lambda _: None,
    )
    assert repeated["snapshot"]["snapshot_id"] == receipt["snapshot"]["snapshot_id"]


def test_existing_output_is_rejected_before_network(tmp_path: Path) -> None:
    request = BinanceArchiveRequest("ETHUSDT", "aggTrades", "2024-03-01")
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "keep"
    marker.write_text("unchanged")
    fetch = FakeGet({})
    with pytest.raises(AcquisitionError, match="already exists"):
        acquire_archive(
            request,
            output_dir=output,
            acquired_at_epoch_nanoseconds=1_800_000_000_000_000_000,
            get=fetch,
            sleep=lambda _: None,
        )
    assert fetch.calls == []
    assert marker.read_text() == "unchanged"


def test_concurrent_output_claim_is_not_replaced(tmp_path: Path) -> None:
    request = BinanceArchiveRequest("ETHUSDT", "aggTrades", "2024-03-01")
    archive = b"archive"
    digest = hashlib.sha256(archive).hexdigest()
    checksum = f"{digest}  {request.filename}\n".encode()
    output = tmp_path / "raced"

    def racing_get(url: str) -> tuple[int, bytes]:
        if url == request.archive_url:
            output.mkdir()
            (output / "foreign").write_text("keep")
            return (200, archive)
        return (200, checksum)

    with pytest.raises(AcquisitionError, match="already exists"):
        acquire_archive(
            request,
            output_dir=output,
            acquired_at_epoch_nanoseconds=1_800_000_000_000_000_000,
            get=racing_get,
            sleep=lambda _: None,
        )
    assert (output / "foreign").read_text() == "keep"
    assert not (output / "acquisition-receipt.json").exists()


def test_archive_failure_writes_no_partial_authority(tmp_path: Path) -> None:
    request = BinanceArchiveRequest("ETHUSDT", "bookTicker", "2024-03-01")
    with pytest.raises(AcquisitionError, match="checksum"):
        acquire_archive(
            request,
            output_dir=tmp_path / "failed",
            acquired_at_epoch_nanoseconds=1_800_000_000_000_000_000,
            get=FakeGet(
                {
                    request.checksum_url: ((200, b"0" * 64 + b"  wrong.zip\n"),),
                    request.archive_url: ((200, b"replacement"),),
                }
            ),
            sleep=lambda _: None,
        )
    assert not (tmp_path / "failed").exists()


def test_funding_history_preserves_raw_response_and_request_receipt(tmp_path: Path) -> None:
    request = BinanceFundingHistoryRequest(
        "ETHUSDT", 1_709_251_200_000, 1_709_337_599_999, 1000
    )
    response = (
        b'[{"symbol":"ETHUSDT","fundingTime":1709251200000,'
        b'"fundingRate":"0.00053040","markPrice":"3343.06219697"},'
        b'{"symbol":"ETHUSDT","fundingTime":1709280000000,'
        b'"fundingRate":"0.00039096","markPrice":"3367.47848485"}]'
    )
    output = tmp_path / "funding"
    result = acquire_funding_history(
        request,
        output_dir=output,
        acquired_at_epoch_nanoseconds=1_800_000_000_000_000_000,
        get=FakeGet({request.url: ((200, response),)}),
        sleep=lambda _: None,
    )
    assert (output / "funding-history.json").read_bytes() == response
    assert result["record_count"] == 2
    assert result["request"]["symbol"] == "ETHUSDT"
    assert result["snapshot"]["members"][0]["content_hash"] == result["response_sha256"]
    assert result["snapshot"]["members"][0]["declared_sha256"] is None


@pytest.mark.parametrize(
    "response",
    (
        b'[{"symbol":"ETHUSDT","fundingTime":1709251200000,"fundingRate":"Infinity","markPrice":"3343.0"}]',
        b'[{"symbol":"ETHUSDT","fundingTime":1709251200000,"fundingRate":"0.1","markPrice":"NaN"}]',
        b'[{"symbol":"ETHUSDT","fundingTime":1709251200000,"fundingRate":"x","markPrice":"-1"}]',
        b'[{"symbol":"ETHUSDT","fundingTime":1709251200000,"fundingRate":"00.1","markPrice":"1"}]',
        b'[{"symbol":"ETHUSDT","fundingTime":1709251200000,"fundingRate":"-00","markPrice":"1"}]',
        b'[{"symbol":"ETHUSDT","fundingTime":1709251200000,"fundingRate":"-0","markPrice":"1"}]',
        b'[{"symbol":"ETHUSDT","fundingTime":1709251200000,"fundingRate":"0.1","markPrice":"-0"}]',
        b'[{"symbol":"ETHUSDT","fundingTime":1709251200000,"fundingRate":"0.1","markPrice":"x"}]',
        b'[{"symbol":"ETHUSDT","fundingTime":1709251200000,"fundingRate":"0.1","markPrice":"01.0"}]',
    ),
)
def test_funding_history_rejects_nonfinite_provider_decimals(
    tmp_path: Path, response: bytes
) -> None:
    request = BinanceFundingHistoryRequest(
        "ETHUSDT", 1_709_251_200_000, 1_709_337_599_999, 1000
    )
    output = tmp_path / "invalid"
    with pytest.raises(AcquisitionError, match="violates request scope"):
        acquire_funding_history(
            request,
            output_dir=output,
            acquired_at_epoch_nanoseconds=1_800_000_000_000_000_000,
            get=FakeGet({request.url: ((200, response),)}),
            sleep=lambda _: None,
        )
    assert not output.exists()


def test_funding_history_enforces_limit_and_archive_date_is_real(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="real calendar"):
        BinanceArchiveRequest("ETHUSDT", "aggTrades", "2024-19-39")
    request = BinanceFundingHistoryRequest(
        "ETHUSDT", 1_709_251_200_000, 1_709_337_599_999, 1
    )
    response = (
        b'[{"symbol":"ETHUSDT","fundingTime":1709251200000,"fundingRate":"0.1","markPrice":"1"},'
        b'{"symbol":"ETHUSDT","fundingTime":1709280000000,"fundingRate":"0.1","markPrice":"1"}]'
    )
    with pytest.raises(AcquisitionError, match="requested limit"):
        acquire_funding_history(
            request,
            output_dir=tmp_path / "too-many",
            acquired_at_epoch_nanoseconds=1_800_000_000_000_000_000,
            get=FakeGet({request.url: ((200, response),)}),
            sleep=lambda _: None,
        )
