from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import ssl
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import sleep as real_sleep
from typing import Any
from urllib.parse import urlsplit

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)

from ._common import (
    AcquisitionError,
    Post,
    json_bytes,
    publish_directory,
    require_new_output,
    sha256,
)


_ENDPOINT_ROOT = "https://api.waditu.com/dataapi"
_TS_CODE = re.compile(r"[0-9]{6}\.(?:SZ|SH|BJ)\Z")
_DATE = re.compile(r"20[0-9]{6}\Z")
_MAX_ATTEMPTS = 3
_DAILY_FIELDS = (
    "ts_code",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "pre_close",
    "change",
    "pct_chg",
    "vol",
    "amount",
)
_LISTING_FIELDS = (
    "ts_code",
    "symbol",
    "name",
    "area",
    "industry",
    "market",
    "exchange",
    "list_status",
    "list_date",
    "delist_date",
)


@dataclass(frozen=True, slots=True)
class TushareDailyListingRequest:
    ts_code: str
    trade_date: str

    def __post_init__(self) -> None:
        if _TS_CODE.fullmatch(self.ts_code) is None:
            raise ValueError("ts_code must be a canonical SZ/SH/BJ Tushare code")
        if _DATE.fullmatch(self.trade_date) is None:
            raise ValueError("trade_date must be YYYYMMDD")
        try:
            datetime.strptime(self.trade_date, "%Y%m%d")
        except ValueError as error:
            raise ValueError("trade_date must be a real calendar date") from error

    def to_canonical_dict(self) -> dict[str, object]:
        return {"ts_code": self.ts_code, "trade_date": self.trade_date}


def _provider_body(
    *, api_name: str, token: str, params: dict[str, object], fields: tuple[str, ...]
) -> dict[str, object]:
    return {
        "api_name": api_name,
        "token": token,
        "params": params,
        "fields": ",".join(fields),
    }


def _post_with_retries(
    api_name: str,
    body: dict[str, object],
    post: Post,
    sleep: Any,
) -> tuple[bytes, int]:
    url = f"{_ENDPOINT_ROOT}/{api_name}"
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = post(url, body)
        except (OSError, RuntimeError):
            response = None
        if response is not None:
            if (
                type(response) is not tuple
                or len(response) != 2
                or type(response[0]) is not int
                or type(response[1]) is not bytes
            ):
                raise AcquisitionError("post must return exact (status, bytes)")
            status, response_bytes = response
            if status == 200:
                return response_bytes, attempt
            if status != 429 and not 500 <= status <= 599:
                raise AcquisitionError(
                    f"provider rejected {api_name} request with HTTP status {status}"
                )
        if attempt < _MAX_ATTEMPTS:
            sleep(2 ** (attempt - 1))
    raise AcquisitionError(f"provider {api_name} request exhausted retries")


def _rows(
    response_bytes: bytes,
    *,
    api_name: str,
    expected_fields: tuple[str, ...],
) -> list[list[object]]:
    try:
        payload = json.loads(response_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AcquisitionError(f"provider {api_name} response must be valid JSON") from error
    if not isinstance(payload, dict) or type(payload.get("code")) is not int:
        raise AcquisitionError(f"provider {api_name} response has invalid envelope")
    if payload["code"] != 0:
        raise AcquisitionError(f"provider rejected {api_name} request")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise AcquisitionError(f"provider {api_name} response has no data")
    fields = data.get("fields")
    items = data.get("items")
    if fields != list(expected_fields) or not isinstance(items, list):
        raise AcquisitionError(f"provider {api_name} response schema mismatch")
    if any(not isinstance(item, list) or len(item) != len(fields) for item in items):
        raise AcquisitionError(f"provider {api_name} response row mismatch")
    return items


def acquire_daily_listing(
    request: TushareDailyListingRequest,
    *,
    token: str,
    output_dir: str | Path,
    acquired_at_epoch_nanoseconds: int,
    post: Post,
    sleep: Any = real_sleep,
) -> dict[str, object]:
    if type(request) is not TushareDailyListingRequest:
        raise AcquisitionError("request must be exact TushareDailyListingRequest")
    require_new_output(output_dir)
    if type(token) is not str or not token or token != token.strip():
        raise AcquisitionError("TUSHARE_TOKEN must be canonical non-empty text")
    if type(acquired_at_epoch_nanoseconds) is not int or acquired_at_epoch_nanoseconds < 0:
        raise AcquisitionError("acquired_at_epoch_nanoseconds must be nonnegative")

    daily_body = _provider_body(
        api_name="daily",
        token=token,
        params={
            "ts_code": request.ts_code,
            "start_date": request.trade_date,
            "end_date": request.trade_date,
        },
        fields=_DAILY_FIELDS,
    )
    daily_bytes, daily_attempts = _post_with_retries(
        "daily", daily_body, post, sleep
    )
    daily_rows = _rows(
        daily_bytes, api_name="daily", expected_fields=_DAILY_FIELDS
    )
    if (
        len(daily_rows) != 1
        or daily_rows[0][0] != request.ts_code
        or str(daily_rows[0][1]) != request.trade_date
    ):
        raise AcquisitionError("provider daily response does not exact-cover request")

    listing_body = _provider_body(
        api_name="stock_basic",
        token=token,
        params={"ts_code": request.ts_code},
        fields=_LISTING_FIELDS,
    )
    listing_bytes, listing_attempts = _post_with_retries(
        "stock_basic", listing_body, post, sleep
    )
    listing_rows = _rows(
        listing_bytes, api_name="stock_basic", expected_fields=_LISTING_FIELDS
    )
    if len(listing_rows) != 1 or listing_rows[0][0] != request.ts_code:
        raise AcquisitionError("provider stock_basic response does not exact-cover request")

    daily_hash = sha256(daily_bytes)
    listing_hash = sha256(listing_bytes)
    snapshot = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "response/daily.json",
                daily_bytes,
                "0644",
                acquired_at_epoch_nanoseconds,
                daily_hash,
            ),
            RawSourceMember(
                "response/stock-basic.json",
                listing_bytes,
                "0644",
                acquired_at_epoch_nanoseconds,
                listing_hash,
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro",
            source_key=(
                "tushare.pro.daily_listing."
                f"{request.ts_code.lower()}.{request.trade_date}"
            ),
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    if snapshot is None:
        raise AcquisitionError("G12A snapshot freeze failed")

    receipt: dict[str, object] = {
        "type": "tushare_daily_listing_acquisition_receipt",
        "schema_version": 1,
        "request": request.to_canonical_dict(),
        "provider_requests": [
            {
                "api_name": "daily",
                "params": daily_body["params"],
                "fields": daily_body["fields"],
                "attempts": daily_attempts,
            },
            {
                "api_name": "stock_basic",
                "params": listing_body["params"],
                "fields": listing_body["fields"],
                "attempts": listing_attempts,
            },
        ],
        "acquired_at_epoch_nanoseconds": acquired_at_epoch_nanoseconds,
        "daily_row_count": len(daily_rows),
        "listing_row_count": len(listing_rows),
        "daily_response_sha256": daily_hash,
        "listing_response_sha256": listing_hash,
        "snapshot": snapshot.to_canonical_dict(),
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    published = {
        "daily.json": daily_bytes,
        "stock-basic.json": listing_bytes,
        "acquisition-receipt.json": json_bytes(receipt),
    }
    if any(token.encode() in value for value in published.values()):
        raise AcquisitionError("provider response unexpectedly contains credential material")
    publish_directory(output_dir, published)
    return receipt


def _stdlib_post(url: str, body: dict[str, object]) -> tuple[int, bytes]:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.waditu.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise AcquisitionError("refusing non-Tushare HTTPS URL")
    payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    connection = http.client.HTTPSConnection(
        parsed.hostname, timeout=30, context=ssl.create_default_context()
    )
    try:
        connection.request(
            "POST",
            parsed.path,
            body=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "crypto-quant-backtest-acquisition/1",
            },
        )
        response = connection.getresponse()
        return int(response.status), response.read()
    finally:
        connection.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Acquire exact Tushare daily and listing response bytes"
    )
    parser.add_argument("--ts-code", required=True)
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        raise SystemExit("TUSHARE_TOKEN must be provided through the environment")
    try:
        receipt = acquire_daily_listing(
            TushareDailyListingRequest(args.ts_code.upper(), args.trade_date),
            token=token,
            output_dir=args.output_dir,
            acquired_at_epoch_nanoseconds=time.time_ns(),
            post=_stdlib_post,
        )
    except (AcquisitionError, ValueError) as error:
        raise SystemExit(f"acquisition failed: {error}") from None
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
