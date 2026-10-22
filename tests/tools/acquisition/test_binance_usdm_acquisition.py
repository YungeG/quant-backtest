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


def _funding_response() -> bytes:
    return b'[{"symbol":"ETHUSDT","fundingTime":1,"fundingRate":"0.1","markPrice":"1"}]'


def test_funding_cli_samples_clock_after_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.acquisition import binance_usdm

    now = [100]
    reads = []

    def get(url: str) -> tuple[int, bytes]:
        now[0] = 200
        return 200, _funding_response()

    def clock() -> int:
        reads.append(now[0])
        return now[0]

    monkeypatch.setattr(binance_usdm, "_stdlib_get", get)
    monkeypatch.setattr(binance_usdm.time, "time_ns", clock)
    output = tmp_path / "cli"
    assert binance_usdm.main([
        "funding", "--symbol", "ETHUSDT", "--start-ms", "0", "--end-ms", "2",
        "--output-dir", str(output),
    ]) == 0
    receipt = json.loads((output / "acquisition-receipt.json").read_bytes())
    assert reads == [200]
    assert receipt["acquired_at_epoch_nanoseconds"] == 200
    assert receipt["snapshot"]["members"][0]["acquired_at_epoch_nanoseconds"] == 200


def test_archive_clock_records_separate_response_instants_and_retry_delay(tmp_path: Path) -> None:
    request = BinanceArchiveRequest("ETHUSDT", "aggTrades", "2024-03-01")
    archive = b"synthetic archive"
    checksum = f"{hashlib.sha256(archive).hexdigest()}  {request.filename}\n".encode()
    fetch = FakeGet({
        request.checksum_url: ((503, b""), (200, checksum)),
        request.archive_url: ((200, archive),),
    })
    now = [100]
    events = []

    def get(url: str) -> tuple[int, bytes]:
        now[0] += 10
        events.append("get")
        return fetch(url)

    def sleep(delay: int) -> None:
        now[0] += delay * 100
        events.append("sleep")

    def clock() -> int:
        events.append("clock")
        return now[0]

    receipt = acquire_archive(
        request, output_dir=tmp_path / "timed", clock=clock, get=get, sleep=sleep
    )
    assert events == ["get", "sleep", "get", "clock", "get", "clock"]
    assert receipt["checksum_attempts"] == 2
    assert receipt["acquired_at_epoch_nanoseconds"] == 230
    archive_member, checksum_member = receipt["snapshot"]["members"]
    assert archive_member["acquired_at_epoch_nanoseconds"] == 230
    assert checksum_member["acquired_at_epoch_nanoseconds"] == 220


@pytest.mark.parametrize("kind", ("archive", "funding"))
@pytest.mark.parametrize("mode", ("neither", "both", "invalid_fixed", "invalid_clock"))
def test_time_source_rejected_before_fetch(tmp_path: Path, kind: str, mode: str) -> None:
    request = (
        BinanceArchiveRequest("ETHUSDT", "aggTrades", "2024-03-01")
        if kind == "archive" else BinanceFundingHistoryRequest("ETHUSDT", 0, 2)
    )
    acquire = acquire_archive if kind == "archive" else acquire_funding_history
    kwargs = {
        "neither": {},
        "both": {"acquired_at_epoch_nanoseconds": 1, "clock": lambda: 2},
        "invalid_fixed": {"acquired_at_epoch_nanoseconds": True},
        "invalid_clock": {"clock": 1},
    }[mode]
    fetch = FakeGet({})
    output = tmp_path / "invalid"
    with pytest.raises(AcquisitionError):
        acquire(request, output_dir=output, get=fetch, **kwargs)
    assert fetch.calls == []
    assert not output.exists()


@pytest.mark.parametrize("values", ((True,), (-1,), (1.0,), (None,), (200, 100)))
def test_invalid_archive_clock_never_publishes(
    tmp_path: Path, values: tuple[object, ...]
) -> None:
    request = BinanceArchiveRequest("ETHUSDT", "aggTrades", "2024-03-01")
    archive = b"synthetic"
    checksum = f"{hashlib.sha256(archive).hexdigest()}  {request.filename}\n".encode()
    output = tmp_path / "invalid"
    with pytest.raises(AcquisitionError):
        acquire_archive(
            request, output_dir=output,
            get=FakeGet({
                request.checksum_url: ((200, checksum),),
                request.archive_url: ((200, archive),),
            }),
            clock=iter(values).__next__,
        )
    assert not output.exists()


@pytest.mark.parametrize("kind", ("archive", "funding"))
def test_failed_clock_path_fetch_publishes_nothing(tmp_path: Path, kind: str) -> None:
    request = (
        BinanceArchiveRequest("ETHUSDT", "aggTrades", "2024-03-01")
        if kind == "archive" else BinanceFundingHistoryRequest("ETHUSDT", 0, 2)
    )
    acquire = acquire_archive if kind == "archive" else acquire_funding_history
    calls = []

    def get(url: str) -> tuple[int, bytes]:
        calls.append(url)
        return 503, b""

    def clock() -> int:
        pytest.fail("failed fetch must not sample acquisition clock")

    output = tmp_path / "failed"
    delays = []
    with pytest.raises(AcquisitionError, match="exhausted"):
        acquire(request, output_dir=output, get=get, clock=clock, sleep=delays.append)
    assert len(calls) == 5 and delays == [1, 2, 4, 8]
    assert not output.exists()


@pytest.mark.parametrize("value", (True, -1, 1.0, None))
def test_invalid_funding_clock_never_publishes(tmp_path: Path, value: object) -> None:
    request = BinanceFundingHistoryRequest("ETHUSDT", 0, 2)
    output = tmp_path / "invalid"
    with pytest.raises(AcquisitionError, match="nonnegative exact int"):
        acquire_funding_history(
            request, output_dir=output,
            get=FakeGet({request.url: ((200, _funding_response()),)}),
            clock=lambda: value,
        )
    assert not output.exists()


def test_archive_cli_samples_each_response_and_accepts_equal_times(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.acquisition import binance_usdm

    request = BinanceArchiveRequest("ETHUSDT", "aggTrades", "2024-03-01")
    archive = b"synthetic archive"
    checksum = f"{hashlib.sha256(archive).hexdigest()}  {request.filename}\n".encode()
    now = [100]
    reads = []

    def get(url: str) -> tuple[int, bytes]:
        now[0] = 200
        return 200, checksum if url == request.checksum_url else archive

    def clock() -> int:
        reads.append(now[0])
        return now[0]

    monkeypatch.setattr(binance_usdm, "_stdlib_get", get)
    monkeypatch.setattr(binance_usdm.time, "time_ns", clock)
    output = tmp_path / "cli"
    assert binance_usdm.main([
        "archive", "--symbol", "ETHUSDT", "--kind", "aggTrades", "--date",
        "2024-03-01", "--output-dir", str(output),
    ]) == 0
    receipt = json.loads((output / "acquisition-receipt.json").read_bytes())
    assert reads == [200, 200]
    assert receipt["acquired_at_epoch_nanoseconds"] == 200
    assert all(member["acquired_at_epoch_nanoseconds"] == 200 for member in receipt["snapshot"]["members"])
