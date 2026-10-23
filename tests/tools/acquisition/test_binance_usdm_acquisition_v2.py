from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.acquisition.binance_usdm_v2 import (
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


def _funding_response() -> bytes:
    return b'[{"symbol":"ETHUSDT","fundingTime":1,"fundingRate":"0.1","markPrice":"1"}]'


def test_funding_cli_samples_clock_after_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.acquisition import binance_usdm_v2

    now = [100]
    reads = []

    def get(url: str) -> tuple[int, bytes]:
        now[0] = 200
        return 200, _funding_response()

    def clock() -> int:
        reads.append(now[0])
        return now[0]

    monkeypatch.setattr(binance_usdm_v2, "_stdlib_get", get)
    monkeypatch.setattr(binance_usdm_v2.time, "time_ns", clock)
    output = tmp_path / "cli"
    assert binance_usdm_v2.main([
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


@pytest.mark.parametrize(
    "values",
    ((True,), (-1,), (1.0,), (None,), (200, 100),
     (200, True), (200, -1), (200, 1.0), (200, None)),
)
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
    from tools.acquisition import binance_usdm_v2

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

    monkeypatch.setattr(binance_usdm_v2, "_stdlib_get", get)
    monkeypatch.setattr(binance_usdm_v2.time, "time_ns", clock)
    output = tmp_path / "cli"
    assert binance_usdm_v2.main([
        "archive", "--symbol", "ETHUSDT", "--kind", "aggTrades", "--date",
        "2024-03-01", "--output-dir", str(output),
    ]) == 0
    receipt = json.loads((output / "acquisition-receipt.json").read_bytes())
    assert reads == [200, 200]
    assert receipt["acquired_at_epoch_nanoseconds"] == 200
    assert all(member["acquired_at_epoch_nanoseconds"] == 200 for member in receipt["snapshot"]["members"])


@pytest.mark.parametrize("kind", ("archive", "funding"))
def test_fixed_time_receipt_and_published_bytes_match_protected_v1(
    tmp_path: Path, kind: str
) -> None:
    from tools.acquisition import binance_usdm

    if kind == "archive":
        request = BinanceArchiveRequest("ETHUSDT", "aggTrades", "2024-03-01")
        archive = b"synthetic archive"
        checksum = f"{hashlib.sha256(archive).hexdigest()}  {request.filename}\n".encode()
        responses = {
            request.checksum_url: ((503, b""), (200, checksum)),
            request.archive_url: ((200, archive),),
        }
        legacy_acquire = binance_usdm.acquire_archive
        acquire = acquire_archive
    else:
        request = BinanceFundingHistoryRequest("ETHUSDT", 0, 2)
        responses = {request.url: ((503, b""), (200, _funding_response()))}
        legacy_acquire = binance_usdm.acquire_funding_history
        acquire = acquire_funding_history
    legacy_output, output = tmp_path / "v1", tmp_path / "v2"
    legacy_receipt = legacy_acquire(
        request, output_dir=legacy_output, acquired_at_epoch_nanoseconds=200,
        get=FakeGet(responses), sleep=lambda _: None,
    )
    receipt = acquire(
        request, output_dir=output, acquired_at_epoch_nanoseconds=200,
        get=FakeGet(responses), sleep=lambda _: None,
    )
    assert receipt == legacy_receipt
    assert {p.name: p.read_bytes() for p in output.iterdir()} == {
        p.name: p.read_bytes() for p in legacy_output.iterdir()
    }


def test_funding_clock_samples_only_success_after_retry_delays(tmp_path: Path) -> None:
    request = BinanceFundingHistoryRequest("ETHUSDT", 0, 2)
    now = [0]
    events = []
    fetch = FakeGet({request.url: ((429, b""), (503, b""), (200, _funding_response()))})

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

    receipt = acquire_funding_history(
        request, output_dir=tmp_path / "funding", get=get, clock=clock, sleep=sleep
    )
    assert events == ["get", "sleep", "get", "sleep", "get", "clock"]
    assert receipt["attempts"] == 3
    assert receipt["acquired_at_epoch_nanoseconds"] == 330
    assert receipt["snapshot"]["members"][0]["acquired_at_epoch_nanoseconds"] == 330


@pytest.mark.parametrize("kind", ("archive", "funding"))
@pytest.mark.parametrize("value", (-1, 1.0, "1"))
def test_invalid_fixed_time_rejected_before_fetch(
    tmp_path: Path, kind: str, value: object
) -> None:
    request = (
        BinanceArchiveRequest("ETHUSDT", "aggTrades", "2024-03-01")
        if kind == "archive" else BinanceFundingHistoryRequest("ETHUSDT", 0, 2)
    )
    acquire = acquire_archive if kind == "archive" else acquire_funding_history
    fetch = FakeGet({})
    output = tmp_path / "invalid"
    with pytest.raises(AcquisitionError, match="nonnegative"):
        acquire(request, output_dir=output, acquired_at_epoch_nanoseconds=value, get=fetch)
    assert fetch.calls == []
    assert not output.exists()


@pytest.mark.parametrize("kind", ("archive", "funding"))
@pytest.mark.parametrize("mode", ("fixed", "clock"))
def test_zero_time_is_valid(tmp_path: Path, kind: str, mode: str) -> None:
    if kind == "archive":
        request = BinanceArchiveRequest("ETHUSDT", "aggTrades", "2024-03-01")
        archive = b"synthetic archive"
        checksum = f"{hashlib.sha256(archive).hexdigest()}  {request.filename}\n".encode()
        responses = {
            request.checksum_url: ((200, checksum),),
            request.archive_url: ((200, archive),),
        }
        acquire = acquire_archive
    else:
        request = BinanceFundingHistoryRequest("ETHUSDT", 0, 2)
        responses = {request.url: ((200, _funding_response()),)}
        acquire = acquire_funding_history
    kwargs = {"acquired_at_epoch_nanoseconds": 0} if mode == "fixed" else {"clock": lambda: 0}
    receipt = acquire(request, output_dir=tmp_path / "zero", get=FakeGet(responses), **kwargs)
    assert receipt["acquired_at_epoch_nanoseconds"] == 0
    assert all(m["acquired_at_epoch_nanoseconds"] == 0 for m in receipt["snapshot"]["members"])
