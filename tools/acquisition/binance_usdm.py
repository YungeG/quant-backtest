from __future__ import annotations

import argparse
import http.client
import json
import re
import ssl
import time
from dataclasses import dataclass
from pathlib import Path
from time import sleep as real_sleep
from typing import Any
from urllib.parse import urlencode, urlsplit

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)

from ._common import (
    AcquisitionError,
    Fetch,
    json_bytes,
    publish_directory,
    require_new_output,
    sha256,
)


_ARCHIVE_ROOT = "https://data.binance.vision/data/futures/um/daily"
_FUNDING_ROOT = "https://fapi.binance.com/fapi/v1/fundingRate"
_SYMBOL = re.compile(r"[A-Z0-9]{5,20}\Z")
_DATE = re.compile(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]\Z")
_KINDS = ("aggTrades", "bookTicker")
_MAX_ATTEMPTS = 5


@dataclass(frozen=True, slots=True)
class BinanceArchiveRequest:
    symbol: str
    kind: str
    utc_date: str

    def __post_init__(self) -> None:
        if _SYMBOL.fullmatch(self.symbol) is None:
            raise ValueError("symbol must be canonical uppercase Binance text")
        if self.kind not in _KINDS:
            raise ValueError(f"kind must be one of {_KINDS}")
        if _DATE.fullmatch(self.utc_date) is None:
            raise ValueError("utc_date must be YYYY-MM-DD")

    @property
    def filename(self) -> str:
        return f"{self.symbol}-{self.kind}-{self.utc_date}.zip"

    @property
    def archive_url(self) -> str:
        return f"{_ARCHIVE_ROOT}/{self.kind}/{self.symbol}/{self.filename}"

    @property
    def checksum_url(self) -> str:
        return self.archive_url + ".CHECKSUM"

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_archive_acquisition_request",
            "schema_version": 1,
            "symbol": self.symbol,
            "kind": self.kind,
            "utc_date": self.utc_date,
            "archive_url": self.archive_url,
            "checksum_url": self.checksum_url,
        }


@dataclass(frozen=True, slots=True)
class BinanceFundingHistoryRequest:
    symbol: str
    start_time_milliseconds: int
    end_time_milliseconds: int
    limit: int = 1000

    def __post_init__(self) -> None:
        if _SYMBOL.fullmatch(self.symbol) is None:
            raise ValueError("symbol must be canonical uppercase Binance text")
        if (
            type(self.start_time_milliseconds) is not int
            or type(self.end_time_milliseconds) is not int
            or self.start_time_milliseconds < 0
            or self.end_time_milliseconds < self.start_time_milliseconds
        ):
            raise ValueError("funding time range must be finite nonnegative milliseconds")
        if type(self.limit) is not int or not 1 <= self.limit <= 1000:
            raise ValueError("limit must be in 1..1000")

    @property
    def url(self) -> str:
        query = urlencode(
            {
                "symbol": self.symbol,
                "startTime": self.start_time_milliseconds,
                "endTime": self.end_time_milliseconds,
                "limit": self.limit,
            }
        )
        return f"{_FUNDING_ROOT}?{query}"

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_funding_history_acquisition_request",
            "schema_version": 1,
            "symbol": self.symbol,
            "start_time_milliseconds": self.start_time_milliseconds,
            "end_time_milliseconds": self.end_time_milliseconds,
            "limit": self.limit,
            "url": self.url,
        }


def _get_with_retries(
    url: str,
    get: Fetch,
    sleep: Any,
) -> tuple[bytes, int]:
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = get(url)
        except (OSError, RuntimeError):
            response = None
        if response is not None:
            if (
                type(response) is not tuple
                or len(response) != 2
                or type(response[0]) is not int
                or type(response[1]) is not bytes
            ):
                raise AcquisitionError("fetch must return exact (status, bytes)")
            status, body = response
            if status == 200:
                return body, attempt
            if status not in (429,) and not 500 <= status <= 599:
                raise AcquisitionError(f"GET failed with status {status}: {url}")
        if attempt < _MAX_ATTEMPTS:
            sleep(2 ** (attempt - 1))
    raise AcquisitionError(f"GET exhausted {_MAX_ATTEMPTS} attempts: {url}")


def _checksum(body: bytes, filename: str) -> str:
    try:
        parts = body.decode("utf-8").strip().split()
    except UnicodeDecodeError as error:
        raise AcquisitionError("checksum must be UTF-8") from error
    if (
        len(parts) != 2
        or parts[1] != filename
        or re.fullmatch(r"[0-9a-f]{64}", parts[0]) is None
    ):
        raise AcquisitionError("checksum does not bind the exact archive filename")
    return parts[0]


def acquire_archive(
    request: BinanceArchiveRequest,
    *,
    output_dir: str | Path,
    acquired_at_epoch_nanoseconds: int,
    get: Fetch,
    sleep: Any = real_sleep,
) -> dict[str, object]:
    if type(request) is not BinanceArchiveRequest:
        raise AcquisitionError("request must be exact BinanceArchiveRequest")
    require_new_output(output_dir)
    if type(acquired_at_epoch_nanoseconds) is not int or acquired_at_epoch_nanoseconds < 0:
        raise AcquisitionError("acquired_at_epoch_nanoseconds must be nonnegative")
    checksum_bytes, checksum_attempts = _get_with_retries(
        request.checksum_url, get, sleep
    )
    expected_hash = _checksum(checksum_bytes, request.filename)
    archive_bytes, archive_attempts = _get_with_retries(
        request.archive_url, get, sleep
    )
    archive_hash = sha256(archive_bytes)
    if archive_hash != "sha256:" + expected_hash:
        raise AcquisitionError("archive checksum mismatch")
    checksum_hash = sha256(checksum_bytes)
    snapshot = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "archive/" + request.filename,
                archive_bytes,
                "0644",
                acquired_at_epoch_nanoseconds,
                archive_hash,
            ),
            RawSourceMember(
                "archive/" + request.filename + ".CHECKSUM",
                checksum_bytes,
                "0644",
                acquired_at_epoch_nanoseconds,
                checksum_hash,
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="binance.public_data",
            source_key=(
                "binance.public_data.futures.um.daily."
                f"{request.kind.lower()}.{request.symbol.lower()}.{request.utc_date}"
            ),
            license_ref="binance.public_data.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    if snapshot is None:
        raise AcquisitionError("G12A snapshot freeze failed")
    receipt: dict[str, object] = {
        "type": "binance_usdm_archive_acquisition_receipt",
        "schema_version": 1,
        "request": request.to_canonical_dict(),
        "acquired_at_epoch_nanoseconds": acquired_at_epoch_nanoseconds,
        "archive_attempts": archive_attempts,
        "checksum_attempts": checksum_attempts,
        "archive_sha256": archive_hash,
        "checksum_sha256": checksum_hash,
        "snapshot": snapshot.to_canonical_dict(),
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    publish_directory(
        output_dir,
        {
            request.filename: archive_bytes,
            request.filename + ".CHECKSUM": checksum_bytes,
            "acquisition-receipt.json": json_bytes(receipt),
        },
    )
    return receipt


def _funding_records(
    response_bytes: bytes,
    request: BinanceFundingHistoryRequest,
) -> tuple[list[dict[str, object]], int]:
    try:
        payload = json.loads(response_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AcquisitionError("funding response must be valid JSON") from error
    if not isinstance(payload, list) or not payload:
        raise AcquisitionError("funding response must be a non-empty list")
    previous = request.start_time_milliseconds - 1
    missing_mark_prices = 0
    for item in payload:
        if not isinstance(item, dict):
            raise AcquisitionError("funding response items must be objects")
        try:
            symbol = item["symbol"]
            funding_time = item["fundingTime"]
            funding_rate = item["fundingRate"]
            mark_price = item["markPrice"]
        except KeyError as error:
            raise AcquisitionError("funding response item is missing a required field") from error
        if (
            symbol != request.symbol
            or type(funding_time) is not int
            or not request.start_time_milliseconds
            <= funding_time
            <= request.end_time_milliseconds
            or funding_time <= previous
            or type(funding_rate) is not str
            or type(mark_price) is not str
        ):
            raise AcquisitionError("funding response item violates request scope")
        previous = funding_time
        missing_mark_prices += not bool(mark_price)
    return payload, missing_mark_prices


def acquire_funding_history(
    request: BinanceFundingHistoryRequest,
    *,
    output_dir: str | Path,
    acquired_at_epoch_nanoseconds: int,
    get: Fetch,
    sleep: Any = real_sleep,
) -> dict[str, object]:
    if type(request) is not BinanceFundingHistoryRequest:
        raise AcquisitionError("request must be exact BinanceFundingHistoryRequest")
    require_new_output(output_dir)
    if type(acquired_at_epoch_nanoseconds) is not int or acquired_at_epoch_nanoseconds < 0:
        raise AcquisitionError("acquired_at_epoch_nanoseconds must be nonnegative")
    response_bytes, attempts = _get_with_retries(request.url, get, sleep)
    records, missing_mark_prices = _funding_records(response_bytes, request)
    response_hash = sha256(response_bytes)
    snapshot = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "response/funding-history.json",
                response_bytes,
                "0644",
                acquired_at_epoch_nanoseconds,
                response_hash,
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="binance.fapi",
            source_key=(
                "binance.fapi.funding_rate_history."
                f"{request.symbol.lower()}.{request.start_time_milliseconds}."
                f"{request.end_time_milliseconds}"
            ),
            license_ref="binance.api.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    if snapshot is None:
        raise AcquisitionError("G12A snapshot freeze failed")
    receipt: dict[str, object] = {
        "type": "binance_usdm_funding_history_acquisition_receipt",
        "schema_version": 1,
        "request": request.to_canonical_dict(),
        "acquired_at_epoch_nanoseconds": acquired_at_epoch_nanoseconds,
        "attempts": attempts,
        "record_count": len(records),
        "missing_mark_price_count": missing_mark_prices,
        "response_sha256": response_hash,
        "snapshot": snapshot.to_canonical_dict(),
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    publish_directory(
        output_dir,
        {
            "funding-history.json": response_bytes,
            "acquisition-receipt.json": json_bytes(receipt),
        },
    )
    return receipt


def _stdlib_get(url: str) -> tuple[int, bytes]:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"data.binance.vision", "fapi.binance.com"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise AcquisitionError("refusing non-Binance HTTPS URL")
    connection = http.client.HTTPSConnection(
        parsed.hostname, timeout=30, context=ssl.create_default_context()
    )
    try:
        target = parsed.path + (("?" + parsed.query) if parsed.query else "")
        connection.request(
            "GET",
            target,
            headers={"User-Agent": "crypto-quant-backtest-acquisition/1"},
        )
        response = connection.getresponse()
        return int(response.status), response.read()
    finally:
        connection.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Acquire exact public Binance USD-M source bytes")
    subparsers = parser.add_subparsers(dest="command", required=True)
    archive = subparsers.add_parser("archive")
    archive.add_argument("--symbol", required=True)
    archive.add_argument("--kind", required=True, choices=_KINDS)
    archive.add_argument("--date", required=True)
    archive.add_argument("--output-dir", required=True, type=Path)
    funding = subparsers.add_parser("funding")
    funding.add_argument("--symbol", required=True)
    funding.add_argument("--start-ms", required=True, type=int)
    funding.add_argument("--end-ms", required=True, type=int)
    funding.add_argument("--limit", type=int, default=1000)
    funding.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    acquired_at = time.time_ns()
    try:
        if args.command == "archive":
            receipt = acquire_archive(
                BinanceArchiveRequest(args.symbol.upper(), args.kind, args.date),
                output_dir=args.output_dir,
                acquired_at_epoch_nanoseconds=acquired_at,
                get=_stdlib_get,
            )
        else:
            receipt = acquire_funding_history(
                BinanceFundingHistoryRequest(
                    args.symbol.upper(), args.start_ms, args.end_ms, args.limit
                ),
                output_dir=args.output_dir,
                acquired_at_epoch_nanoseconds=acquired_at,
                get=_stdlib_get,
            )
    except (AcquisitionError, ValueError) as error:
        raise SystemExit(f"acquisition failed: {error}") from None
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
