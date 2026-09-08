"""Source-bounded monthly 000703.SZ order-authority acquisition."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
import os
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from time import sleep as real_sleep

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)

from ._common import AcquisitionError, json_bytes, publish_directory, require_new_output, sha256
from .cn_a_share_tushare_000703_20240102_smoke_v1 import _FIELDS
from .cn_a_share_tushare_000703_202401_month_smoke_v2 import (
    _load_json,
    _load_snapshot,
    _validate,
)
from .cn_a_share_tushare_authority import _authority_rows
from .cn_a_share_tushare_listing_source_bounded_v2 import (
    _ALLOWED_ENDPOINTS,
    _PROXY_KEY,
    _headers,
    _post_with_retries,
    _request_body,
    _stdlib_post,
)
from .cn_a_share_tushare_minute_source_bounded_v2 import (
    verify_tushare_minute_source_bounded_receipt_v2,
)
from .cn_a_share_tushare_proxy_trade_calendar_month_source_bounded_v2 import (
    verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v2,
)


_TS_CODE = "000703.SZ"
ProxyPost = Callable[[str, dict[str, object], dict[str, str]], tuple[int, bytes]]
_SPECS = (
    ("daily", "daily", _FIELDS["daily"], "daily"),
    ("stk_limit", "stk_limit", _FIELDS["stk_limit"], "stk-limit"),
    ("stock_st", "stock_st", _FIELDS["stock_st"], "stock-st"),
    ("suspend_s", "suspend_d", _FIELDS["suspend_s"], "suspend-d-s"),
    ("suspend_r", "suspend_d", _FIELDS["suspend_r"], "suspend-d-r"),
)
_FLAGS = (
    "source_bounded",
    "development_only",
    "decision_grade_eligible",
    "live_eligible",
    "deployment_authorized",
)
_NEGATIVE_EVIDENCE = {
    "stock_st_terminal_zero": True,
    "suspend_d_s_terminal_zero": True,
    "suspend_d_r_terminal_zero": True,
    "classification": "STANDARD + NORMAL",
    "corporate_action_absence_claimed": False,
}


@dataclass(frozen=True, slots=True)
class Tushare000703MonthlyOrderAuthorityRequest:
    month: str

    def __post_init__(self) -> None:
        if type(self.month) is not str or len(self.month) != 6 or not self.month.isascii() or not self.month.isdigit():
            raise ValueError("month must be canonical YYYYMM text")
        try:
            datetime.strptime(self.month, "%Y%m")
        except ValueError as error:
            raise ValueError("month must be a real calendar month") from error

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "tushare_000703_monthly_order_authority_request_v1",
            "schema_version": 1,
            "month": self.month,
        }


def _worklist(calendar: object, request: Tushare000703MonthlyOrderAuthorityRequest) -> tuple[str, ...]:
    if not isinstance(calendar, dict) or calendar.get("request") != {
        "type": "tushare_proxy_trade_calendar_month_source_bounded_request_v2",
        "schema_version": 2,
        "exchange": "SZSE",
        "month": request.month,
    }:
        raise AcquisitionError("calendar does not exact-cover monthly request")
    values = calendar.get("open_sessions")
    if type(values) is not list or not values:
        raise AcquisitionError("calendar open_sessions must be a nonempty list")
    sessions = tuple(values)
    if any(type(day) is not str or len(day) != 8 or not day.isascii() or not day.isdigit() for day in sessions):
        raise AcquisitionError("calendar open_sessions must contain canonical dates")
    try:
        parsed = tuple(datetime.strptime(day, "%Y%m%d") for day in sessions)
    except ValueError as error:
        raise AcquisitionError("calendar open_sessions has invalid date") from error
    if any(day.strftime("%Y%m") != request.month for day in parsed):
        raise AcquisitionError("calendar open_sessions is outside requested month")
    if sessions != tuple(sorted(sessions)) or len(sessions) != len(set(sessions)):
        raise AcquisitionError("calendar open_sessions must be ordered and unique")
    return sessions


def _minute_root(root: str | Path, day: str) -> Path:
    base = Path(root)
    direct = base / day
    return direct if direct.is_dir() else base / "sessions" / day


def _request_rows(day: str) -> list[tuple[str, dict[str, object], tuple[str, ...], str]]:
    values = []
    for key, api_name, fields, filename in _SPECS:
        params: dict[str, object] = (
            {"ts_code": _TS_CODE, "trade_date": day}
            if key in {"stk_limit", "suspend_s", "suspend_r"}
            else {"ts_code": _TS_CODE, "start_date": day, "end_date": day}
        )
        if key == "suspend_s":
            params["suspend_type"] = "S"
        if key == "suspend_r":
            params["suspend_type"] = "R"
        values.append((api_name, params, fields, f"response/{day}/{filename}.json"))
    return values


def _expected_requests(sessions: tuple[str, ...]) -> list[tuple[str, dict[str, object], tuple[str, ...], str]]:
    return [
        (
            "stock_basic",
            {"ts_code": _TS_CODE, "list_status": "L"},
            _FIELDS["stock_basic"],
            "response/stock-basic.json",
        ),
        *(
            row
            for day in sessions
            for row in _request_rows(day)
        ),
    ]


def _member_keys(sessions: tuple[str, ...]) -> set[str]:
    return {member_key for _, _, _, member_key in _expected_requests(sessions)}


def _minute_receipts(
    *,
    sessions: tuple[str, ...],
    minute_authority_root: str | Path,
    minute_receipt_hashes: Mapping[str, str],
) -> dict[str, str]:
    if set(minute_receipt_hashes) != set(sessions) or any(type(value) is not str for value in minute_receipt_hashes.values()):
        raise AcquisitionError("minute receipt hashes do not exact-cover calendar worklist")
    result: dict[str, str] = {}
    for day in sessions:
        receipt_bytes, snapshot = _load_snapshot(
            _minute_root(minute_authority_root, day), "response/stk-mins.json"
        )
        receipt = verify_tushare_minute_source_bounded_receipt_v2(
            receipt_bytes, snapshot, minute_receipt_hashes[day]
        )
        if receipt.get("request", {}).get("trade_date") != day:
            raise AcquisitionError("minute authority does not exact-cover calendar worklist")
        result[day] = sha256(receipt_bytes)
    return result


def _calendar(
    *,
    request: Tushare000703MonthlyOrderAuthorityRequest,
    calendar_authority_dir: str | Path,
    calendar_receipt_hash: str,
) -> tuple[bytes, object, tuple[str, ...]]:
    receipt_bytes, snapshot = _load_snapshot(
        Path(calendar_authority_dir), "response/trade-calendar.json"
    )
    calendar = verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v2(
        receipt_bytes, snapshot, calendar_receipt_hash
    )
    return receipt_bytes, snapshot, _worklist(calendar, request)


def _capture_response(
    *,
    api_name: str,
    params: dict[str, object],
    fields: tuple[str, ...],
    endpoint: str,
    token: str,
    post: ProxyPost,
    clock: Callable[[], int],
    sleep: Callable[[float], object],
) -> tuple[dict[str, object], bytes, int, int, list[list[object]]]:
    body = _request_body(api_name, params, fields)
    source, attempts = _post_with_retries(
        api_name,
        endpoint=endpoint,
        body=body,
        headers=_headers(token),
        post=post,
        sleep=sleep,
    )
    acquired_at = clock()
    if type(acquired_at) is not int or acquired_at < 0:
        raise AcquisitionError("clock must return a nonnegative integer nanosecond timestamp")
    rows = _authority_rows(
        source,
        api_name=api_name,
        expected_fields=fields,
        forbidden_text=token,
    )
    return body, source, attempts, acquired_at, rows


def acquire_tushare_000703_month_order_authority_v1(
    request: Tushare000703MonthlyOrderAuthorityRequest,
    *,
    token: str,
    endpoint: str,
    output_dir: str | Path,
    calendar_authority_dir: str | Path,
    minute_authority_root: str | Path,
    calendar_receipt_hash: str,
    minute_receipt_hashes: Mapping[str, str],
    post: ProxyPost,
    clock: Callable[[], int] = time.time_ns,
    sleep: Callable[[float], object] = real_sleep,
) -> dict[str, object]:
    if type(request) is not Tushare000703MonthlyOrderAuthorityRequest:
        raise TypeError("request must be concrete Tushare000703MonthlyOrderAuthorityRequest")
    require_new_output(output_dir)
    if (
        type(token) is not str
        or len(token) != 56
        or token != token.strip()
        or any(character.isspace() for character in token)
        or endpoint not in _ALLOWED_ENDPOINTS
        or not isinstance(minute_receipt_hashes, Mapping)
    ):
        raise AcquisitionError("invalid acquisition inputs")

    calendar_bytes, _, sessions = _calendar(
        request=request,
        calendar_authority_dir=calendar_authority_dir,
        calendar_receipt_hash=calendar_receipt_hash,
    )
    minute_authority = _minute_receipts(
        sessions=sessions,
        minute_authority_root=minute_authority_root,
        minute_receipt_hashes=minute_receipt_hashes,
    )
    files: dict[str, bytes] = {}
    provider_requests: list[dict[str, object]] = []
    request_count = 0

    def capture(
        api_name: str, params: dict[str, object], fields: tuple[str, ...], member_key: str
    ) -> list[list[object]]:
        nonlocal request_count
        if request_count:
            sleep(0.5)
        body, source, attempts, acquired_at, rows = _capture_response(
            api_name=api_name,
            params=params,
            fields=fields,
            endpoint=endpoint,
            token=token,
            post=post,
            clock=clock,
            sleep=sleep,
        )
        files[member_key] = source
        provider_requests.append(
            {
                "api_name": api_name,
                "params": body["params"],
                "fields": body["fields"],
                "member_key": member_key,
                "auth_mode": "x-api-key",
                "attempts": attempts,
                "response_byte_count": len(source),
                "response_sha256": sha256(source),
                "response_acquired_at_epoch_nanoseconds": acquired_at,
                "returned_row_count": len(rows),
                "provider_revision_id": None,
                "declared_sha256": None,
            }
        )
        request_count += 1
        return rows

    stock = capture(
        "stock_basic",
        {"ts_code": _TS_CODE, "list_status": "L"},
        _FIELDS["stock_basic"],
        "response/stock-basic.json",
    )
    for day in sessions:
        captured = {
            member_key: capture(api_name, params, fields, member_key)
            for api_name, params, fields, member_key in _request_rows(day)
        }
        _validate(
            stock,
            captured[f"response/{day}/daily.json"],
            captured[f"response/{day}/stk-limit.json"],
            {
                "stock_st": captured[f"response/{day}/stock-st.json"],
                "suspend_s": captured[f"response/{day}/suspend-d-s.json"],
                "suspend_r": captured[f"response/{day}/suspend-d-r.json"],
            },
            day,
        )

    by_member = {item["member_key"]: item for item in provider_requests}
    snapshot = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                member_key,
                value,
                "0644",
                by_member[member_key]["response_acquired_at_epoch_nanoseconds"],
                None,
            )
            for member_key, value in sorted(files.items())
        ),
        provenance=SourceSnapshotProvenance(
            "tushare.pro",
            (
                "tushare.pro.via.xiaodefa.approved-proxy."
                f"{endpoint.removeprefix('https://')}.000703.sz.{request.month}."
                "month-order-authority"
            ),
            "tushare.pro.terms",
            "backtest.acquisition.candidate",
        ),
    ).snapshot
    if snapshot is None:
        raise AcquisitionError("SourceSnapshot freeze failed")
    raw_members = {
        member_key: {
            "sha256": sha256(value),
            "acquired_at_epoch_nanoseconds": by_member[member_key][
                "response_acquired_at_epoch_nanoseconds"
            ],
        }
        for member_key, value in sorted(files.items())
    }
    declaration = {
        "type": "tushare_000703_month_order_authority_declaration_v1",
        "schema_version": 1,
        "request": request.to_canonical_dict(),
        "ts_code": _TS_CODE,
        "open_sessions": list(sessions),
        "raw_members": raw_members,
        "calendar_receipt_sha256": calendar_receipt_hash,
        "minute_receipt_sha256": minute_authority,
        "negative_evidence": _NEGATIVE_EVIDENCE,
        "source_bounded": True,
        "development_only": True,
        "decision_grade_eligible": False,
        "live_eligible": False,
        "deployment_authorized": False,
    }
    declaration_bytes = json_bytes(declaration)
    receipt = {
        "type": "tushare_000703_month_order_authority_acquisition_receipt_v1",
        "schema_version": 1,
        "request": request.to_canonical_dict(),
        "ts_code": _TS_CODE,
        "open_sessions": list(sessions),
        "provider_key": "tushare.pro",
        "transport_proxy_key": _PROXY_KEY,
        "transport_endpoint": endpoint,
        "provider_requests": provider_requests,
        "acquired_at_epoch_nanoseconds": max(
            item["response_acquired_at_epoch_nanoseconds"]
            for item in provider_requests
        ),
        "snapshot": snapshot.to_canonical_dict(),
        "declaration_sha256": sha256(declaration_bytes),
        "source_bounded": True,
        "development_only": True,
        "decision_grade_eligible": False,
        "live_eligible": False,
        "deployment_authorized": False,
    }
    published = files | {
        "source-snapshot.json": json_bytes(snapshot.to_canonical_dict()),
        "declaration.json": declaration_bytes,
        "acquisition-receipt.json": json_bytes(receipt),
    }
    if any(token.encode() in value for value in published.values()):
        raise AcquisitionError("proxy response unexpectedly contains credential material")
    publish_directory(output_dir, published)
    return receipt


def _verify_request(value: object) -> Tushare000703MonthlyOrderAuthorityRequest:
    if type(value) is not dict:
        raise AcquisitionError("monthly request is invalid")
    try:
        request = Tushare000703MonthlyOrderAuthorityRequest(value["month"])
    except (KeyError, TypeError, ValueError) as error:
        raise AcquisitionError("monthly request is invalid") from error
    if value != request.to_canonical_dict():
        raise AcquisitionError("monthly request is noncanonical")
    return request


def verify_tushare_000703_month_order_authority_v1(
    output_dir: str | Path,
    *,
    calendar_authority_dir: str | Path,
    minute_authority_root: str | Path,
) -> dict[str, object]:
    root = Path(output_dir)
    receipt_bytes, receipt = _load_json(root / "acquisition-receipt.json")
    declaration_bytes, declaration = _load_json(root / "declaration.json")
    snapshot_bytes, published_snapshot = _load_json(root / "source-snapshot.json")
    request = _verify_request(declaration.get("request"))
    declaration_fields = {
        "type", "schema_version", "request", "ts_code", "open_sessions", "raw_members",
        "calendar_receipt_sha256", "minute_receipt_sha256", "negative_evidence", *_FLAGS,
    }
    receipt_fields = {
        "type", "schema_version", "request", "ts_code", "open_sessions", "provider_key",
        "transport_proxy_key", "transport_endpoint", "provider_requests",
        "acquired_at_epoch_nanoseconds", "snapshot", "declaration_sha256", *_FLAGS,
    }
    if (
        set(declaration) != declaration_fields
        or declaration.get("type") != "tushare_000703_month_order_authority_declaration_v1"
        or declaration.get("schema_version") != 1
        or declaration.get("ts_code") != _TS_CODE
        or declaration.get("negative_evidence") != _NEGATIVE_EVIDENCE
        or tuple(declaration.get(flag) for flag in _FLAGS) != (True, True, False, False, False)
        or declaration_bytes != json_bytes(declaration)
    ):
        raise AcquisitionError("monthly declaration schema or identity mismatch")
    calendar_hash = declaration.get("calendar_receipt_sha256")
    if type(calendar_hash) is not str:
        raise AcquisitionError("monthly calendar authority hash is invalid")
    calendar_bytes, _, sessions = _calendar(
        request=request,
        calendar_authority_dir=calendar_authority_dir,
        calendar_receipt_hash=calendar_hash,
    )
    if declaration.get("open_sessions") != list(sessions):
        raise AcquisitionError("monthly declaration worklist mismatch")
    member_keys = _member_keys(sessions)
    expected_files = member_keys | {
        "source-snapshot.json", "declaration.json", "acquisition-receipt.json"
    }
    try:
        found_files = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
        files = {member_key: (root / member_key).read_bytes() for member_key in member_keys}
    except OSError as error:
        raise AcquisitionError("retained monthly raw member is missing") from error
    if found_files != expected_files:
        raise AcquisitionError("retained monthly file set mismatch")
    minute_hashes = declaration.get("minute_receipt_sha256")
    if not isinstance(minute_hashes, dict):
        raise AcquisitionError("monthly minute authority manifest is invalid")
    minute_authority = _minute_receipts(
        sessions=sessions,
        minute_authority_root=minute_authority_root,
        minute_receipt_hashes=minute_hashes,
    )
    if minute_authority != minute_hashes:
        raise AcquisitionError("monthly minute authority hash mismatch")
    if (
        set(receipt) != receipt_fields
        or receipt.get("type") != "tushare_000703_month_order_authority_acquisition_receipt_v1"
        or receipt.get("schema_version") != 1
        or receipt.get("request") != request.to_canonical_dict()
        or receipt.get("ts_code") != _TS_CODE
        or receipt.get("open_sessions") != list(sessions)
        or receipt.get("provider_key") != "tushare.pro"
        or receipt.get("transport_proxy_key") != _PROXY_KEY
        or receipt.get("transport_endpoint") not in _ALLOWED_ENDPOINTS
        or tuple(receipt.get(flag) for flag in _FLAGS) != (True, True, False, False, False)
        or receipt.get("declaration_sha256") != sha256(declaration_bytes)
        or receipt_bytes != json_bytes(receipt)
    ):
        raise AcquisitionError("monthly receipt schema or identity mismatch")
    provider_requests = receipt.get("provider_requests")
    acquired_at = receipt.get("acquired_at_epoch_nanoseconds")
    expected_requests = _expected_requests(sessions)
    request_fields = {
        "api_name", "params", "fields", "member_key", "auth_mode", "attempts",
        "response_byte_count", "response_sha256", "response_acquired_at_epoch_nanoseconds",
        "returned_row_count", "provider_revision_id", "declared_sha256",
    }
    if (
        type(provider_requests) is not list
        or len(provider_requests) != len(expected_requests)
        or any(type(item) is not dict for item in provider_requests)
        or type(acquired_at) is not int
        or acquired_at < 0
        or acquired_at != max(
            item.get("response_acquired_at_epoch_nanoseconds", -1)
            for item in provider_requests
            if type(item) is dict
        )
    ):
        raise AcquisitionError("monthly provider request count or acquisition time mismatch")
    by_member: dict[str, dict[str, object]] = {}
    stock: list[list[object]] | None = None
    for item, (api_name, params, fields, member_key) in zip(
        provider_requests, expected_requests, strict=True
    ):
        if type(item) is not dict or set(item) != request_fields:
            raise AcquisitionError("monthly provider request is invalid")
        source = files[member_key]
        response_time = item.get("response_acquired_at_epoch_nanoseconds")
        if (
            item.get("api_name") != api_name
            or item.get("params") != params
            or item.get("fields") != ",".join(fields)
            or item.get("member_key") != member_key
            or item.get("auth_mode") != "x-api-key"
            or type(item.get("attempts")) is not int
            or item["attempts"] not in range(1, 4)
            or type(response_time) is not int
            or response_time < 0
            or item.get("response_byte_count") != len(source)
            or item.get("response_sha256") != sha256(source)
            or type(item.get("returned_row_count")) is not int
            or item.get("provider_revision_id") is not None
            or item.get("declared_sha256") is not None
        ):
            raise AcquisitionError("monthly provider request mismatch")
        rows = _authority_rows(source, api_name=api_name, expected_fields=fields, forbidden_text="\0")
        if item.get("returned_row_count") != len(rows):
            raise AcquisitionError("monthly provider request row count mismatch")
        by_member[member_key] = item
        if member_key == "response/stock-basic.json":
            stock = rows
    if stock is None:
        raise AcquisitionError("monthly stock-basic member is missing")
    for day in sessions:
        _validate(
            stock,
            _authority_rows(files[f"response/{day}/daily.json"], api_name="daily", expected_fields=_FIELDS["daily"], forbidden_text="\0"),
            _authority_rows(files[f"response/{day}/stk-limit.json"], api_name="stk_limit", expected_fields=_FIELDS["stk_limit"], forbidden_text="\0"),
            {
                "stock_st": _authority_rows(files[f"response/{day}/stock-st.json"], api_name="stock_st", expected_fields=_FIELDS["stock_st"], forbidden_text="\0"),
                "suspend_s": _authority_rows(files[f"response/{day}/suspend-d-s.json"], api_name="suspend_d", expected_fields=_FIELDS["suspend_s"], forbidden_text="\0"),
                "suspend_r": _authority_rows(files[f"response/{day}/suspend-d-r.json"], api_name="suspend_d", expected_fields=_FIELDS["suspend_r"], forbidden_text="\0"),
            },
            day,
        )
    raw_members = declaration.get("raw_members")
    if type(raw_members) is not dict or set(raw_members) != member_keys or any(
        raw_members[member_key]
        != {
            "sha256": sha256(files[member_key]),
            "acquired_at_epoch_nanoseconds": by_member[member_key][
                "response_acquired_at_epoch_nanoseconds"
            ],
        }
        for member_key in member_keys
    ):
        raise AcquisitionError("monthly declaration raw-member manifest mismatch")
    endpoint = receipt["transport_endpoint"]
    snapshot = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                member_key,
                value,
                "0644",
                by_member[member_key]["response_acquired_at_epoch_nanoseconds"],
                None,
            )
            for member_key, value in sorted(files.items())
        ),
        provenance=SourceSnapshotProvenance(
            "tushare.pro",
            (
                "tushare.pro.via.xiaodefa.approved-proxy."
                f"{endpoint.removeprefix('https://')}.000703.sz.{request.month}."
                "month-order-authority"
            ),
            "tushare.pro.terms",
            "backtest.acquisition.candidate",
        ),
    ).snapshot
    if (
        snapshot is None
        or published_snapshot != snapshot.to_canonical_dict()
        or snapshot_bytes != json_bytes(published_snapshot)
        or receipt.get("snapshot") != published_snapshot
    ):
        raise AcquisitionError("monthly source snapshot identity mismatch")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture month-bounded 000703.SZ development order authority"
    )
    parser.add_argument("--month", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--calendar-authority-dir", required=True, type=Path)
    parser.add_argument("--minute-authority-root", required=True, type=Path)
    parser.add_argument("--calendar-receipt-hash", required=True)
    parser.add_argument("--minute-receipt-hashes-json", required=True, type=Path)
    parser.add_argument("--endpoint", choices=_ALLOWED_ENDPOINTS, default=_ALLOWED_ENDPOINTS[0])
    args = parser.parse_args(argv)
    try:
        acquire_tushare_000703_month_order_authority_v1(
            Tushare000703MonthlyOrderAuthorityRequest(args.month),
            token=os.environ.get("TUSHARE_PROXY_TOKEN", ""),
            endpoint=args.endpoint,
            output_dir=args.output_dir,
            calendar_authority_dir=args.calendar_authority_dir,
            minute_authority_root=args.minute_authority_root,
            calendar_receipt_hash=args.calendar_receipt_hash,
            minute_receipt_hashes=json.loads(args.minute_receipt_hashes_json.read_bytes()),
            post=_stdlib_post,
        )
    except (AcquisitionError, OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"acquisition failed: {error}") from None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
