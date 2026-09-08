# ruff: noqa: DTZ007 -- these validators parse provider calendar dates, not instants.

from __future__ import annotations

import argparse
import json
import os
import re
import time
from calendar import monthrange
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from time import sleep as real_sleep

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshot,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)

from ._common import AcquisitionError, json_bytes, publish_directory, require_new_output, sha256
from .cn_a_share_tushare_authority import _authority_rows
from .cn_a_share_tushare_listing_source_bounded_v2 import (
    _ALLOWED_ENDPOINTS,
    _PROXY_KEY,
    _headers,
    _post_with_retries,
    _request_body,
    _stdlib_post,
)

_EXCHANGE = "SZSE"
_MONTH = re.compile(r"20[0-9]{4}\Z")
_FIELDS = ("exchange", "cal_date", "is_open", "pretrade_date")

ProxyPost = Callable[[str, dict[str, object], dict[str, str]], tuple[int, bytes]]


@dataclass(frozen=True, slots=True)
class TushareProxyTradeCalendarMonthSourceBoundedRequestV1:
    exchange: str
    month: str

    def __post_init__(self) -> None:
        if self.exchange != _EXCHANGE:
            raise ValueError("request exchange must be exact SZSE")
        if _MONTH.fullmatch(self.month) is None:
            raise ValueError("month must be YYYYMM")
        try:
            datetime.strptime(self.month, "%Y%m")
        except ValueError as error:
            raise ValueError("month must be a real YYYYMM month") from error

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "tushare_proxy_trade_calendar_month_source_bounded_request_v1",
            "schema_version": 1,
            "exchange": self.exchange,
            "month": self.month,
        }


def _month_dates(month: str) -> tuple[str, ...]:
    try:
        year, month_number = int(month[:4]), int(month[4:])
        days = monthrange(year, month_number)[1]
    except (TypeError, ValueError) as error:
        raise ValueError("month must be a real YYYYMM month") from error
    return tuple(
        date(year, month_number, day).strftime("%Y%m%d")
        for day in range(1, days + 1)
    )


def _source_dates(month: str) -> tuple[str, ...]:
    try:
        year, month_number = int(month[:4]), int(month[4:])
    except (TypeError, ValueError) as error:
        raise ValueError("month must be a real YYYYMM month") from error
    previous_month = f"{year - 1:04}12" if month_number == 1 else f"{year:04}{month_number - 1:02}"
    return _month_dates(previous_month) + _month_dates(month)


def _validate_rows(
    rows: list[list[object]], request: TushareProxyTradeCalendarMonthSourceBoundedRequestV1
) -> None:
    expected_dates = _source_dates(request.month)
    by_date: dict[str, list[object]] = {}
    for row in rows:
        exchange, cal_date, is_open, pretrade_date = row
        if (
            exchange != _EXCHANGE
            or type(cal_date) is not str
            or type(is_open) is not int
            or is_open not in (0, 1)
            or type(pretrade_date) is not str
        ):
            raise AcquisitionError("trade_cal response violates request scope")
        try:
            parsed_date = datetime.strptime(cal_date, "%Y%m%d").date()
            parsed_pretrade = datetime.strptime(pretrade_date, "%Y%m%d").date()
        except ValueError as error:
            raise AcquisitionError("trade_cal response has invalid calendar dates") from error
        if parsed_pretrade >= parsed_date:
            raise AcquisitionError("trade_cal response has invalid pretrade_date")
        if cal_date in by_date:
            raise AcquisitionError("trade_cal response has duplicate calendar dates")
        by_date[cal_date] = row

    if set(by_date) != set(expected_dates):
        raise AcquisitionError("trade_cal response does not exact-cover requested month")

    previous_open: str | None = None
    for cal_date in expected_dates:
        _, _, is_open, pretrade_date = by_date[cal_date]
        if previous_open is not None and pretrade_date != previous_open:
            raise AcquisitionError("trade_cal response has invalid pretrade_date semantics")
        if is_open == 1:
            previous_open = cal_date


def _target_open_sessions(
    rows: list[list[object]], request: TushareProxyTradeCalendarMonthSourceBoundedRequestV1
) -> list[str]:
    target_dates = set(_month_dates(request.month))
    return sorted(row[1] for row in rows if row[1] in target_dates and row[2] == 1)


def verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v1(
    receipt_bytes: bytes, snapshot: SourceSnapshot, expected_receipt_hash: str
) -> dict[str, object]:
    """Verify a receipt and snapshot; raw snapshot validates provider bytes while expected receipt hash binds non-byte receipt claims."""
    if type(receipt_bytes) is not bytes:
        raise AcquisitionError("receipt must be bytes")
    if type(expected_receipt_hash) is not str or sha256(receipt_bytes) != expected_receipt_hash:
        raise AcquisitionError("receipt hash does not match expected receipt hash")

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        receipt: dict[str, object] = {}
        for key, value in pairs:
            if key in receipt:
                raise ValueError("duplicate key")
            receipt[key] = value
        return receipt

    def reject_constant(value: str) -> object:
        raise ValueError(f"invalid JSON constant {value}")

    try:
        receipt = json.loads(
            receipt_bytes, object_pairs_hook=unique_object, parse_constant=reject_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise AcquisitionError("receipt is not valid JSON") from error
    if type(receipt) is not dict:
        raise AcquisitionError("receipt must be a JSON object")
    expected_receipt_fields = {
        "type", "schema_version", "source_bounded", "development_only", "request",
        "provider_key", "transport_proxy_key", "transport_endpoint", "provider_requests",
        "acquired_at_epoch_nanoseconds", "snapshot", "calendar_row_count",
        "target_calendar_row_count", "open_sessions", "open_session_count", "open_day_count",
        "decision_grade_eligible", "live_eligible", "deployment_authorized",
    }
    if set(receipt) != expected_receipt_fields:
        raise AcquisitionError("receipt has unexpected fields")
    if (
        receipt.get("type")
        != "tushare_proxy_trade_calendar_month_source_bounded_acquisition_receipt_v1"
        or receipt.get("schema_version") != 1
        or receipt.get("provider_key") != "tushare.pro"
        or receipt.get("transport_proxy_key") != _PROXY_KEY
        or receipt.get("transport_endpoint") not in _ALLOWED_ENDPOINTS
        or type(receipt.get("acquired_at_epoch_nanoseconds")) is not int
        or receipt["acquired_at_epoch_nanoseconds"] < 0
    ):
        raise AcquisitionError("receipt has unexpected type or schema")
    request_data = receipt.get("request")
    if type(request_data) is not dict:
        raise AcquisitionError("receipt has invalid request")
    try:
        request = TushareProxyTradeCalendarMonthSourceBoundedRequestV1(
            request_data["exchange"], request_data["month"]
        )
    except (KeyError, TypeError, ValueError) as error:
        raise AcquisitionError("receipt has invalid request") from error
    if request_data != request.to_canonical_dict():
        raise AcquisitionError("receipt has noncanonical request")
    development_flags = (
        receipt.get("source_bounded"),
        receipt.get("development_only"),
        receipt.get("decision_grade_eligible"),
        receipt.get("live_eligible"),
        receipt.get("deployment_authorized"),
    )
    if (
        any(type(value) is not bool for value in development_flags)
        or development_flags != (True, True, False, False, False)
    ):
        raise AcquisitionError("receipt has invalid development flags")
    open_sessions = receipt.get("open_sessions")
    if (
        type(open_sessions) is not list
        or any(type(value) is not str for value in open_sessions)
        or any(
            type(receipt.get(field)) is not int
            for field in (
                "calendar_row_count", "target_calendar_row_count", "open_session_count", "open_day_count",
            )
        )
        or receipt.get("open_session_count") != len(open_sessions)
    ):
        raise AcquisitionError("receipt has invalid open-session worklist")
    outcome = verify_source_snapshot(snapshot)
    if outcome.snapshot != snapshot:
        raise AcquisitionError("source snapshot verification failed")
    member_key = "response/trade-calendar.json"
    expected_provenance = SourceSnapshotProvenance(
        vendor_key="tushare.pro",
        source_key=(
            "tushare.pro.via.xiaodefa.approved-proxy.trade_cal."
            f"{receipt['transport_endpoint'].removeprefix('https://')}.szse.{request.month}"
        ),
        license_ref="tushare.pro.terms",
        retention_policy_ref="backtest.acquisition.candidate",
    )
    if (
        receipt.get("snapshot") != snapshot.to_canonical_dict()
        or snapshot.provenance != expected_provenance
        or len(snapshot.members) != 1
        or snapshot.members[0].member_key != member_key
        or snapshot.members[0].declared_sha256 is not None
        or snapshot.members[0].acquired_at_epoch_nanoseconds
        != receipt.get("acquired_at_epoch_nanoseconds")
    ):
        raise AcquisitionError("receipt snapshot identity does not match source snapshot")
    provider_requests = receipt.get("provider_requests")
    expected_params = {
        "exchange": _EXCHANGE,
        "start_date": _source_dates(request.month)[0],
        "end_date": _source_dates(request.month)[-1],
    }
    if type(provider_requests) is not list or len(provider_requests) != 1:
        raise AcquisitionError("receipt has invalid provider requests")
    provider_request = provider_requests[0]
    expected_provider_request_fields = {
        "api_name", "params", "fields", "member_key", "auth_mode", "attempts",
        "response_byte_count", "response_sha256", "returned_row_count",
        "provider_revision_id", "declared_sha256",
    }
    if (
        type(provider_request) is not dict
        or set(provider_request) != expected_provider_request_fields
        or provider_request.get("api_name") != "trade_cal"
        or provider_request.get("params") != expected_params
        or provider_request.get("fields") != ",".join(_FIELDS)
        or provider_request.get("member_key") != member_key
        or provider_request.get("auth_mode") != "x-api-key"
        or any(
            type(provider_request.get(field)) is not int
            for field in ("attempts", "response_byte_count", "returned_row_count")
        )
        or provider_request["attempts"] not in range(1, 4)
        or provider_request.get("provider_revision_id") is not None
        or provider_request.get("declared_sha256") is not None
    ):
        raise AcquisitionError("receipt has invalid provider request")
    source = snapshot.member_bytes(member_key)
    response_hash = sha256(source)
    if (
        provider_request.get("response_sha256") != response_hash
        or provider_request.get("response_byte_count") != len(source)
        or snapshot.members[0].content_hash != response_hash
    ):
        raise AcquisitionError("receipt provider response does not match source snapshot")
    rows = _authority_rows(
        source, api_name="trade_cal", expected_fields=_FIELDS, forbidden_text="\0"
    )
    _validate_rows(rows, request)
    if provider_request.get("returned_row_count") != len(rows):
        raise AcquisitionError("receipt provider request row count does not match source")
    expected_sessions = _target_open_sessions(rows, request)
    if (
        receipt.get("calendar_row_count") != len(rows)
        or receipt.get("target_calendar_row_count") != len(_month_dates(request.month))
        or receipt.get("open_day_count") != len(expected_sessions)
        or open_sessions != expected_sessions
    ):
        raise AcquisitionError("receipt open-session worklist does not match source")
    return receipt


def acquire_tushare_proxy_trade_calendar_month_source_bounded_v1(
    request: TushareProxyTradeCalendarMonthSourceBoundedRequestV1,
    *,
    endpoint: str,
    output_dir: str | Path,
    acquired_at_epoch_nanoseconds: int,
    post: ProxyPost,
    sleep: Callable[[float], object] = real_sleep,
) -> dict[str, object]:
    if type(request) is not TushareProxyTradeCalendarMonthSourceBoundedRequestV1:
        raise AcquisitionError("request must be exact TushareProxyTradeCalendarMonthSourceBoundedRequestV1")
    require_new_output(output_dir)
    if endpoint not in _ALLOWED_ENDPOINTS:
        raise AcquisitionError("proxy endpoint is not approved")
    if type(acquired_at_epoch_nanoseconds) is not int or acquired_at_epoch_nanoseconds < 0:
        raise AcquisitionError("acquired_at_epoch_nanoseconds must be nonnegative")
    token = os.environ.get("TUSHARE_PROXY_TOKEN", "")
    if not isinstance(token, str) or len(token) != 56 or token != token.strip() or any(char.isspace() for char in token):
        raise AcquisitionError("TUSHARE_PROXY_TOKEN must be exact 56-character text")

    target_dates = _month_dates(request.month)
    dates = _source_dates(request.month)
    params = {"exchange": _EXCHANGE, "start_date": dates[0], "end_date": dates[-1]}
    body = _request_body("trade_cal", params, _FIELDS)
    source, attempts = _post_with_retries(
        "trade_cal", endpoint=endpoint, body=body, headers=_headers(token), post=post, sleep=sleep
    )
    rows = _authority_rows(source, api_name="trade_cal", expected_fields=_FIELDS, forbidden_text=token)
    _validate_rows(rows, request)
    open_sessions = _target_open_sessions(rows, request)

    member_key = "response/trade-calendar.json"
    snapshot = freeze_source_snapshot(
        members=(RawSourceMember(member_key, source, "0644", acquired_at_epoch_nanoseconds, None),),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro",
            source_key=(
                "tushare.pro.via.xiaodefa.approved-proxy.trade_cal."
                f"{endpoint.removeprefix('https://')}.szse.{request.month}"
            ),
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    if snapshot is None:
        raise AcquisitionError("SourceSnapshot freeze failed")

    receipt: dict[str, object] = {
        "type": "tushare_proxy_trade_calendar_month_source_bounded_acquisition_receipt_v1",
        "schema_version": 1,
        "source_bounded": True,
        "development_only": True,
        "request": request.to_canonical_dict(),
        "provider_key": "tushare.pro",
        "transport_proxy_key": _PROXY_KEY,
        "transport_endpoint": endpoint,
        "provider_requests": [{
            "api_name": "trade_cal", "params": params, "fields": ",".join(_FIELDS),
            "member_key": member_key, "auth_mode": "x-api-key", "attempts": attempts,
            "response_byte_count": len(source), "response_sha256": sha256(source),
            "returned_row_count": len(rows), "provider_revision_id": None, "declared_sha256": None,
        }],
        "acquired_at_epoch_nanoseconds": acquired_at_epoch_nanoseconds,
        "snapshot": snapshot.to_canonical_dict(),
        "calendar_row_count": len(rows),
        "target_calendar_row_count": len(target_dates),
        "open_sessions": open_sessions,
        "open_session_count": len(open_sessions),
        "open_day_count": sum(row[2] for row in rows if row[1] in target_dates),
        "decision_grade_eligible": False,
        "live_eligible": False,
        "deployment_authorized": False,
    }
    published = {member_key: source, "acquisition-receipt.json": json_bytes(receipt)}
    if any(token.encode() in value for value in published.values()):
        raise AcquisitionError("proxy response unexpectedly contains credential material")
    publish_directory(output_dir, published)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Acquire one bounded development-only SZSE Tushare trade calendar month")
    parser.add_argument("--month", required=True)
    parser.add_argument("--endpoint", choices=_ALLOWED_ENDPOINTS, default=_ALLOWED_ENDPOINTS[0])
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not os.environ.get("TUSHARE_PROXY_TOKEN"):
        raise SystemExit("TUSHARE_PROXY_TOKEN must be provided through the environment")
    try:
        receipt = acquire_tushare_proxy_trade_calendar_month_source_bounded_v1(
            TushareProxyTradeCalendarMonthSourceBoundedRequestV1(_EXCHANGE, args.month),
            endpoint=args.endpoint,
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
