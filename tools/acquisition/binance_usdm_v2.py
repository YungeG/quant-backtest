"""Explicit post-response acquisition entry point; v1 remains byte-protected."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from time import sleep as real_sleep
from typing import Any

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
from .binance_usdm import (
    BinanceArchiveRequest,
    BinanceFundingHistoryRequest,
    _checksum,
    _funding_records,
    _get_with_retries,
    _parser,
    _stdlib_get,
)


def _acquisition_clock(
    acquired_at_epoch_nanoseconds: int | None,
    clock: Callable[[], int] | None,
) -> Callable[[], int]:
    if (acquired_at_epoch_nanoseconds is None) == (clock is None):
        raise AcquisitionError("supply exactly one of acquired_at_epoch_nanoseconds or clock")
    if clock is None:
        if type(acquired_at_epoch_nanoseconds) is not int or acquired_at_epoch_nanoseconds < 0:
            raise AcquisitionError("acquired_at_epoch_nanoseconds must be nonnegative")
        return lambda: acquired_at_epoch_nanoseconds
    if not callable(clock):
        raise AcquisitionError("clock must be callable")
    previous: int | None = None

    def received_at() -> int:
        nonlocal previous
        value = clock()
        if type(value) is not int or value < 0:
            raise AcquisitionError("clock must return a nonnegative exact int")
        if previous is not None and value < previous:
            raise AcquisitionError("acquisition clock moved backwards")
        previous = value
        return value

    return received_at


def acquire_archive(
    request: BinanceArchiveRequest,
    *,
    output_dir: str | Path,
    acquired_at_epoch_nanoseconds: int | None = None,
    clock: Callable[[], int] | None = None,
    get: Fetch,
    sleep: Any = real_sleep,
) -> dict[str, object]:
    if type(request) is not BinanceArchiveRequest:
        raise AcquisitionError("request must be exact BinanceArchiveRequest")
    require_new_output(output_dir)
    received_at = _acquisition_clock(acquired_at_epoch_nanoseconds, clock)
    checksum_bytes, checksum_attempts = _get_with_retries(
        request.checksum_url, get, sleep
    )
    checksum_acquired_at = received_at()
    expected_hash = _checksum(checksum_bytes, request.filename)
    archive_bytes, archive_attempts = _get_with_retries(
        request.archive_url, get, sleep
    )
    archive_acquired_at = received_at()
    acquired_at_epoch_nanoseconds = max(checksum_acquired_at, archive_acquired_at)
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
                archive_acquired_at,
                archive_hash,
            ),
            RawSourceMember(
                "archive/" + request.filename + ".CHECKSUM",
                checksum_bytes,
                "0644",
                checksum_acquired_at,
                None,
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


def acquire_funding_history(
    request: BinanceFundingHistoryRequest,
    *,
    output_dir: str | Path,
    acquired_at_epoch_nanoseconds: int | None = None,
    clock: Callable[[], int] | None = None,
    get: Fetch,
    sleep: Any = real_sleep,
) -> dict[str, object]:
    if type(request) is not BinanceFundingHistoryRequest:
        raise AcquisitionError("request must be exact BinanceFundingHistoryRequest")
    require_new_output(output_dir)
    received_at = _acquisition_clock(acquired_at_epoch_nanoseconds, clock)
    response_bytes, attempts = _get_with_retries(request.url, get, sleep)
    acquired_at_epoch_nanoseconds = received_at()
    records, missing_mark_prices = _funding_records(response_bytes, request)
    response_hash = sha256(response_bytes)
    snapshot = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "response/funding-history.json",
                response_bytes,
                "0644",
                acquired_at_epoch_nanoseconds,
                None,
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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "archive":
            receipt = acquire_archive(
                BinanceArchiveRequest(args.symbol.upper(), args.kind, args.date),
                output_dir=args.output_dir,
                clock=time.time_ns,
                get=_stdlib_get,
            )
        else:
            receipt = acquire_funding_history(
                BinanceFundingHistoryRequest(
                    args.symbol.upper(), args.start_ms, args.end_ms, args.limit
                ),
                output_dir=args.output_dir,
                clock=time.time_ns,
                get=_stdlib_get,
            )
    except (AcquisitionError, ValueError) as error:
        raise SystemExit(f"acquisition failed: {error}") from None
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
