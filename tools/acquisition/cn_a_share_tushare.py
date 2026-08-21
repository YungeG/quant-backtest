# ruff: noqa: DTZ007 -- these validators parse provider calendar dates, not instants.

from __future__ import annotations

import argparse
import http.client
import json
import math
import os
import re
import ssl
import sys
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
_SOURCE_BOUNDED_DATES_V2 = (
    "20260706",
    "20260707",
    "20260708",
    "20260709",
    "20260710",
    "20260711",
    "20260712",
    "20260713",
    "20260714",
    "20260715",
    "20260716",
    "20260717",
    "20260718",
    "20260719",
    "20260720",
    "20260721",
    "20260722",
    "20260723",
    "20260724",
    "20260725",
    "20260726",
    "20260727",
    "20260728",
    "20260729",
    "20260730",
)
_SUSPEND_FIELDS_V2 = (
    "ts_code",
    "trade_date",
    "suspend_timing",
    "suspend_type",
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


@dataclass(frozen=True, slots=True)
class TushareCnAShareDailySourceBoundedRequestV2:
    schema_version: int = 2
    ts_code: str = "000001.SZ"
    exchange: str = "SZSE"
    provider_dates: tuple[str, ...] = _SOURCE_BOUNDED_DATES_V2

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not int
            or self.schema_version != 2
            or type(self.ts_code) is not str
            or self.ts_code != "000001.SZ"
            or type(self.exchange) is not str
            or self.exchange != "SZSE"
            or type(self.provider_dates) is not tuple
            or any(type(value) is not str for value in self.provider_dates)
            or self.provider_dates != _SOURCE_BOUNDED_DATES_V2
        ):
            raise ValueError("request must be the exact frozen source-bounded v2 scope")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_daily_source_bounded_request",
            "schema_version": self.schema_version,
            "ts_code": self.ts_code,
            "exchange": self.exchange,
            "provider_dates": list(self.provider_dates),
            "start_date": self.provider_dates[0],
            "end_date": self.provider_dates[-1],
        }


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


def _contains_text(value: object, text: str) -> bool:
    if isinstance(value, str):
        return text in value
    if isinstance(value, dict):
        return any(
            _contains_text(key, text) or _contains_text(item, text)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_text(item, text) for item in value)
    return False


def _rows(
    response_bytes: bytes,
    *,
    api_name: str,
    expected_fields: tuple[str, ...],
    forbidden_text: str,
) -> list[list[object]]:
    try:
        payload = json.loads(response_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AcquisitionError(
            f"provider {api_name} response must be valid JSON"
        ) from error
    if _contains_text(payload, forbidden_text):
        raise AcquisitionError(
            f"provider {api_name} response contains credential material"
        )
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
    if any(
        not isinstance(item, list) or len(item) != len(expected_fields)
        for item in items
    ):
        raise AcquisitionError(f"provider {api_name} response row mismatch")
    return items


def _source_bounded_rows_v2(
    response_bytes: bytes,
    *,
    api_name: str,
    expected_fields: tuple[str, ...],
    forbidden_text: str,
) -> tuple[list[list[object]], bool, int]:
    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise ValueError(f"invalid JSON constant {value}")

    try:
        payload = json.loads(
            response_bytes,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        payload = None
    if payload is None:
        raise AcquisitionError(
            f"provider {api_name} response must be valid unique-key JSON"
        ) from None
    if _contains_text(payload, forbidden_text):
        raise AcquisitionError(
            f"provider {api_name} response contains credential material"
        )
    if (
        type(payload) is not dict
        or set(payload) != {"request_id", "code", "data", "msg", "detail"}
        or type(payload["request_id"]) is not str
        or not payload["request_id"]
        or payload["request_id"] != payload["request_id"].strip()
        or type(payload["code"]) is not int
        or type(payload["msg"]) is not str
        or type(payload["detail"]) is not str
    ):
        raise AcquisitionError(f"provider {api_name} response has invalid envelope")
    if payload["code"] != 0:
        raise AcquisitionError(f"provider rejected {api_name} request")
    data = payload["data"]
    if (
        type(data) is not dict
        or set(data) != {"fields", "items", "has_more", "count"}
        or data["fields"] != list(expected_fields)
        or type(data["items"]) is not list
        or type(data["has_more"]) is not bool
        or type(data["count"]) is not int
    ):
        raise AcquisitionError(f"provider {api_name} response schema mismatch")
    if any(
        type(item) is not list or len(item) != len(expected_fields)
        for item in data["items"]
    ):
        raise AcquisitionError(f"provider {api_name} response row mismatch")
    return data["items"], data["has_more"], data["count"]


def _is_number(value: object) -> bool:
    return type(value) is int or (type(value) is float and math.isfinite(value))


def _validate_daily_rows_v2(rows: list[list[object]], trade_date: str) -> None:
    keys: set[tuple[object, object]] = set()
    for row in rows:
        if (
            row[0] != "000001.SZ"
            or type(row[0]) is not str
            or row[1] != trade_date
            or type(row[1]) is not str
            or any(not _is_number(value) for value in row[2:])
        ):
            raise AcquisitionError("provider daily response violates request scope")
        key = (row[0], row[1])
        if key in keys:
            raise AcquisitionError("provider daily response has duplicate logical rows")
        keys.add(key)


def _validate_suspend_rows_v2(rows: list[list[object]], trade_date: str) -> None:
    keys: set[tuple[object, ...]] = set()
    for row in rows:
        timing = row[2]
        if (
            row[0] != "000001.SZ"
            or type(row[0]) is not str
            or row[1] != trade_date
            or type(row[1]) is not str
            or (
                timing is not None
                and (type(timing) is not str or not timing or timing != timing.strip())
            )
            or row[3] != "S"
            or type(row[3]) is not str
        ):
            raise AcquisitionError("provider suspend_d response violates request scope")
        key = tuple(row)
        if key in keys:
            raise AcquisitionError(
                "provider suspend_d response has duplicate logical rows"
            )
        keys.add(key)


def _exact_source_bounded_request_v2(request: object) -> bool:
    if type(request) is not TushareCnAShareDailySourceBoundedRequestV2:
        return False
    try:
        rebuilt = TushareCnAShareDailySourceBoundedRequestV2(
            request.schema_version,
            request.ts_code,
            request.exchange,
            request.provider_dates,
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return rebuilt == request


def acquire_tushare_cn_a_share_daily_source_bounded_v2(
    request: TushareCnAShareDailySourceBoundedRequestV2,
    *,
    token: str,
    output_dir: str | Path,
    post: Post,
    time_ns: Any = time.time_ns,
    sleep: Any = real_sleep,
) -> dict[str, object]:
    if not _exact_source_bounded_request_v2(request):
        raise AcquisitionError(
            "request must be exact TushareCnAShareDailySourceBoundedRequestV2"
        )
    require_new_output(output_dir)
    if type(token) is not str or not token or token != token.strip():
        raise AcquisitionError("TUSHARE_TOKEN must be canonical non-empty text")
    if not callable(time_ns):
        raise AcquisitionError("time_ns must be callable")

    from . import cn_a_share_tushare_trade_calendar as trade_calendar

    files: dict[str, bytes] = {}
    received_at: dict[str, int] = {}
    provider_requests: list[dict[str, object]] = []

    def capture(
        api_name: str,
        params: dict[str, object],
        fields: tuple[str, ...],
        member_key: str,
    ) -> list[list[object]]:
        body = _provider_body(
            api_name=api_name,
            token=token,
            params=params,
            fields=fields,
        )
        response_bytes, attempts = _post_with_retries(api_name, body, post, sleep)
        try:
            response_received_at = time_ns()
        except Exception:  # noqa: BLE001 -- redact failures from the injected clock.
            raise AcquisitionError("response receipt clock failed") from None
        if type(response_received_at) is not int or response_received_at < 0:
            raise AcquisitionError("response receipt time must be nonnegative integer")
        rows, has_more, count = _source_bounded_rows_v2(
            response_bytes,
            api_name=api_name,
            expected_fields=fields,
            forbidden_text=token,
        )
        files[member_key] = response_bytes
        received_at[member_key] = response_received_at
        provider_requests.append(
            {
                "api_name": api_name,
                "params": body["params"],
                "fields": body["fields"],
                "member_key": member_key,
                "attempts": attempts,
                "response_received_at_epoch_nanoseconds": response_received_at,
                "response_byte_count": len(response_bytes),
                "response_sha256": sha256(response_bytes),
                "observed_envelope": {"has_more": has_more, "count": count},
                "declared_sha256": None,
                "provider_revision_id": None,
            }
        )
        return rows

    for trade_date in request.provider_dates:
        rows = capture(
            "daily",
            {
                "ts_code": request.ts_code,
                "start_date": trade_date,
                "end_date": trade_date,
            },
            _DAILY_FIELDS,
            f"response/daily/{trade_date}.json",
        )
        _validate_daily_rows_v2(rows, trade_date)

    calendar_rows = capture(
        "trade_cal",
        {
            "exchange": request.exchange,
            "start_date": request.provider_dates[0],
            "end_date": request.provider_dates[-1],
        },
        trade_calendar._FIELDS,
        "response/trade-cal/20260706-20260730.json",
    )
    trade_calendar._validate_trade_calendar_range_v2(
        calendar_rows,
        exchange=request.exchange,
        start_date=request.provider_dates[0],
        end_date=request.provider_dates[-1],
    )

    for trade_date in request.provider_dates:
        rows = capture(
            "suspend_d",
            {
                "ts_code": request.ts_code,
                "trade_date": trade_date,
                "suspend_type": "S",
            },
            _SUSPEND_FIELDS_V2,
            f"response/suspend-d/{trade_date}.json",
        )
        _validate_suspend_rows_v2(rows, trade_date)

    snapshot = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                member_key, response_bytes, "0644", received_at[member_key], None
            )
            for member_key, response_bytes in files.items()
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro",
            source_key=(
                "tushare.pro.cn_a_share_daily_source_bounded_v2."
                "000001.sz.20260706.20260730"
            ),
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    if snapshot is None:
        raise AcquisitionError("G12A snapshot freeze failed")

    receipt: dict[str, object] = {
        "type": "tushare_cn_a_share_daily_source_bounded_acquisition_receipt",
        "schema_version": 2,
        "request": request.to_canonical_dict(),
        "provider_requests": provider_requests,
        "acquired_at_epoch_nanoseconds": max(received_at.values()),
        "snapshot": snapshot.to_canonical_dict(),
        "provider_declared_sha256": None,
        "provider_revision_id": None,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    published = {**files, "acquisition-receipt.json": json_bytes(receipt)}
    if any(token.encode() in value for value in published.values()):
        raise AcquisitionError(
            "provider response unexpectedly contains credential material"
        )
    publish_directory(output_dir, published)
    return receipt


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
    if (
        type(acquired_at_epoch_nanoseconds) is not int
        or acquired_at_epoch_nanoseconds < 0
    ):
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
    daily_bytes, daily_attempts = _post_with_retries("daily", daily_body, post, sleep)
    daily_rows = _rows(
        daily_bytes,
        api_name="daily",
        expected_fields=_DAILY_FIELDS,
        forbidden_text=token,
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
        listing_bytes,
        api_name="stock_basic",
        expected_fields=_LISTING_FIELDS,
        forbidden_text=token,
    )
    if len(listing_rows) != 1 or listing_rows[0][0] != request.ts_code:
        raise AcquisitionError(
            "provider stock_basic response does not exact-cover request"
        )

    daily_hash = sha256(daily_bytes)
    listing_hash = sha256(listing_bytes)
    snapshot = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "response/daily.json",
                daily_bytes,
                "0644",
                acquired_at_epoch_nanoseconds,
                None,
            ),
            RawSourceMember(
                "response/stock-basic.json",
                listing_bytes,
                "0644",
                acquired_at_epoch_nanoseconds,
                None,
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
        raise AcquisitionError(
            "provider response unexpectedly contains credential material"
        )
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


def _source_bounded_parser_v2() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Acquire the frozen G12I Tushare source-bounded v2 responses"
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    source_bounded_v2 = arguments[:1] == ["source-bounded-v2"]
    args = (
        _source_bounded_parser_v2().parse_args(arguments[1:])
        if source_bounded_v2
        else _parser().parse_args(arguments)
    )
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        raise SystemExit("TUSHARE_TOKEN must be provided through the environment")
    try:
        if source_bounded_v2:
            receipt = acquire_tushare_cn_a_share_daily_source_bounded_v2(
                TushareCnAShareDailySourceBoundedRequestV2(),
                token=token,
                output_dir=args.output_dir,
                post=_stdlib_post,
            )
        else:
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
