from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import sleep as real_sleep
from typing import Any, cast

from crypto_quant_bundle_builder import RawSourceMember, SourceSnapshotProvenance, freeze_source_snapshot

from ._common import AcquisitionError, json_bytes, publish_directory, require_new_output, sha256
from .cn_a_share_tushare_authority import _authority_rows, _is_real_historical_date
from .cn_a_share_tushare_listing_source_bounded_v2 import (
    _ALLOWED_ENDPOINTS, _PROXY_KEY, _headers, _post_with_retries, _request_body, _stdlib_post,
)

_TS_CODE = "000703.SZ"
_DATE = "20240102"
_TOKEN_LENGTH = 56
_CALENDAR_RECEIPT_HASH = "sha256:77b6932301c4dbc42bb13aca5e88dbe649499601f3406caaa309d8e6ab92324b"
_CALENDAR_SNAPSHOT_ID = "sha256:ae11e7d4e241e6d85c73fd8479fcfde0c8d6dd8b0e8b5e1aba9a7ba08ddb7f27"
_CALENDAR_CONTENT_HASH = "sha256:d5321de3162aed37b003a3493381a0e8af688a8e1bbea283984761dcf60b9d41"
_MINUTE_RECEIPT_HASH = "sha256:a37828d1aa8acbcacb4c1abbcb0a3c6990956c5fb31dce2fa1d092a2ac4223fc"
_MINUTE_SNAPSHOT_ID = "sha256:4bde7bb4d1a8d7fb1e410caa5d0bf1d04246d365d70b7fd6e0b1d4e4422931f5"
_MINUTE_CONTENT_HASH = "sha256:520091248f7869eeb5a6b72d4b19ea75c75cfa96daf2b5b5cd48d3641f866a15"

_FIELDS = {
    "stock_basic": ("ts_code", "symbol", "name", "area", "industry", "market", "exchange", "list_status", "list_date", "delist_date"),
    "daily": ("ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"),
    "stk_limit": ("trade_date", "ts_code", "up_limit", "down_limit"),
    "stock_st": ("ts_code", "trade_date", "name"),
    "suspend_s": ("ts_code", "trade_date", "suspend_timing", "suspend_type"),
    "suspend_r": ("ts_code", "trade_date", "suspend_timing", "suspend_type"),
}
_SPECS: tuple[tuple[str, str, dict[str, object], str], ...] = (
    ("stock_basic", "stock_basic", {"ts_code": _TS_CODE, "list_status": "L"}, "response/stock-basic.json"),
    ("daily", "daily", {"ts_code": _TS_CODE, "start_date": _DATE, "end_date": _DATE}, "response/daily.json"),
    ("stk_limit", "stk_limit", {"ts_code": _TS_CODE, "trade_date": _DATE}, "response/stk-limit.json"),
    ("stock_st", "stock_st", {"ts_code": _TS_CODE, "start_date": _DATE, "end_date": _DATE}, "response/stock-st.json"),
    ("suspend_s", "suspend_d", {"ts_code": _TS_CODE, "trade_date": _DATE, "suspend_type": "S"}, "response/suspend-d-s.json"),
    ("suspend_r", "suspend_d", {"ts_code": _TS_CODE, "trade_date": _DATE, "suspend_type": "R"}, "response/suspend-d-r.json"),
)

ProxyPost = Callable[[str, dict[str, object], dict[str, str]], tuple[int, bytes]]


@dataclass(frozen=True, slots=True)
class Tushare000703DevelopmentSmokeRequestV1:
    ts_code: str = _TS_CODE
    trade_date: str = _DATE

    def __post_init__(self) -> None:
        if (self.ts_code, self.trade_date) != (_TS_CODE, _DATE):
            raise ValueError("request must be exact 000703.SZ / 20240102 scope")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "tushare_000703_development_smoke_request_v1", "schema_version": 1, "ts_code": self.ts_code, "trade_date": self.trade_date}


def _load_json(path: Path) -> tuple[bytes, dict[str, object]]:
    raw = path.read_bytes()

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value

    def reject_constant(value: str) -> object:
        raise ValueError(f"invalid JSON constant {value}")

    try:
        value = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise AcquisitionError("frozen authority is not valid JSON") from error
    if type(value) is not dict:
        raise AcquisitionError("frozen authority is not a JSON object")
    return raw, value


def _object(value: object, message: str) -> dict[str, object]:
    if type(value) is not dict:
        raise AcquisitionError(message)
    return value


def _verify_frozen_authorities(calendar_dir: str | Path, minute_dir: str | Path) -> dict[str, object]:
    calendar_root, minute_root = Path(calendar_dir), Path(minute_dir)
    calendar_receipt_bytes, calendar_receipt = _load_json(calendar_root / "acquisition-receipt.json")
    minute_receipt_bytes, minute_receipt = _load_json(minute_root / "acquisition-receipt.json")
    calendar_raw = (calendar_root / "response/trade-calendar.json").read_bytes()
    minute_raw = (minute_root / "response/stk-mins.json").read_bytes()
    if sha256(calendar_receipt_bytes) != _CALENDAR_RECEIPT_HASH or sha256(minute_receipt_bytes) != _MINUTE_RECEIPT_HASH:
        raise AcquisitionError("frozen authority receipt identity mismatch")
    if sha256(calendar_raw) != _CALENDAR_CONTENT_HASH or sha256(minute_raw) != _MINUTE_CONTENT_HASH:
        raise AcquisitionError("frozen authority content identity mismatch")
    calendar_snapshot = _object(calendar_receipt.get("snapshot"), "frozen calendar snapshot is invalid")
    minute_snapshot = _object(minute_receipt.get("snapshot"), "frozen minute snapshot is invalid")
    if calendar_snapshot.get("snapshot_id") != _CALENDAR_SNAPSHOT_ID or minute_snapshot.get("snapshot_id") != _MINUTE_SNAPSHOT_ID:
        raise AcquisitionError("frozen authority snapshot identity mismatch")
    calendar_rows = _authority_rows(calendar_raw, api_name="trade_cal", expected_fields=("exchange", "cal_date", "is_open", "pretrade_date"), forbidden_text="\0")
    minute_rows = _authority_rows(minute_raw, api_name="stk_mins", expected_fields=("ts_code", "trade_time", "close", "open", "high", "low", "vol", "amount"), forbidden_text="\0")
    if [row for row in calendar_rows if row[0] == "SZSE" and row[1] == _DATE and row[2] == 1] != [["SZSE", _DATE, 1, "20231229"]]:
        raise AcquisitionError("frozen calendar does not mark target open")
    if (
        len(minute_rows) != 49
        or minute_receipt.get("strategy_trade_time_count") != 48
    ):
        raise AcquisitionError("frozen minute authority is not a verified 48 closed-bar session")
    return {
        "calendar": {"receipt_sha256": _CALENDAR_RECEIPT_HASH, "snapshot_id": _CALENDAR_SNAPSHOT_ID, "content_hash": _CALENDAR_CONTENT_HASH},
        "minute": {"receipt_sha256": _MINUTE_RECEIPT_HASH, "snapshot_id": _MINUTE_SNAPSHOT_ID, "content_hash": _MINUTE_CONTENT_HASH, "closed_bar_count": 48},
    }


def _number(value: object) -> float:
    if type(value) not in (int, float):
        raise AcquisitionError("provider numeric value is invalid")
    try:
        return float(cast(int | float, value))
    except (TypeError, ValueError, OverflowError) as error:
        raise AcquisitionError("provider numeric value is invalid") from error


def _positive(value: object) -> bool:
    return math.isfinite(_number(value)) and _number(value) > 0


def _validate_capture(captured: dict[str, list[list[object]]]) -> None:
    stock = captured["stock_basic"]
    if len(stock) != 1:
        raise AcquisitionError("stock_basic response is outside ordinary domestic XSHE Main listed scope")
    list_date, delist_date = stock[0][8], stock[0][9]
    if (stock[0][0] != _TS_CODE or stock[0][1] != "000703" or stock[0][5] != "主板"
            or stock[0][6] != "SZSE" or stock[0][7] != "L"
            or not _is_real_historical_date(list_date) or cast(str, list_date) > _DATE
            or (delist_date is not None and (not _is_real_historical_date(delist_date) or cast(str, delist_date) < _DATE))):
        raise AcquisitionError("stock_basic response is outside ordinary domestic XSHE Main listed scope")
    daily, limits = captured["daily"], captured["stk_limit"]
    if (len(daily) != 1 or daily[0][0:2] != [_TS_CODE, _DATE]
            or not all(_positive(value) for value in daily[0][2:7])
            or any(type(value) not in (int, float) or not math.isfinite(_number(value)) for value in daily[0][7:])
            or _number(daily[0][9]) < 0 or _number(daily[0][10]) < 0):
        raise AcquisitionError("daily response does not exact-cover valid target scope")
    if (len(limits) != 1 or limits[0][0:2] != [_DATE, _TS_CODE]
            or not all(_positive(value) for value in limits[0][2:])
            or not _number(limits[0][3]) <= _number(daily[0][6]) <= _number(limits[0][2])):
        raise AcquisitionError("stk_limit response does not exact-cover valid target limits")
    for key, suspend_type in (("stock_st", None), ("suspend_s", "S"), ("suspend_r", "R")):
        rows = captured[key]
        if rows:
            if any(row[0] != _TS_CODE or row[1] != _DATE or (suspend_type is not None and row[3] != suspend_type) for row in rows):
                raise AcquisitionError(f"{key} exception response is outside target scope")
            raise AcquisitionError("exception row prevents STANDARD + NORMAL negative evidence")


def acquire_tushare_000703_development_smoke_v1(request: Tushare000703DevelopmentSmokeRequestV1, *, token: str, endpoint: str, output_dir: str | Path, calendar_authority_dir: str | Path, minute_authority_dir: str | Path, acquired_at_epoch_nanoseconds: int, post: ProxyPost, sleep: Callable[[float], object] = real_sleep) -> dict[str, object]:
    if type(request) is not Tushare000703DevelopmentSmokeRequestV1:
        raise AcquisitionError("request must be exact smoke request")
    require_new_output(output_dir)
    if type(token) is not str or len(token) != _TOKEN_LENGTH or token != token.strip() or any(char.isspace() for char in token):
        raise AcquisitionError("TUSHARE_PROXY_TOKEN must be exact 56-character text")
    if endpoint not in _ALLOWED_ENDPOINTS or type(acquired_at_epoch_nanoseconds) is not int or acquired_at_epoch_nanoseconds < 0:
        raise AcquisitionError("invalid approved transport or acquisition time")
    authority = _verify_frozen_authorities(calendar_authority_dir, minute_authority_dir)
    captured: dict[str, tuple[dict[str, object], bytes, int, list[list[object]], str, str]] = {}
    for key, api_name, params, member_key in _SPECS:
        body = _request_body(api_name, params, _FIELDS[key])
        source, attempts = _post_with_retries(api_name, endpoint=endpoint, body=body, headers=_headers(token), post=post, sleep=sleep)
        captured[key] = (body, source, attempts, _authority_rows(source, api_name=api_name, expected_fields=_FIELDS[key], forbidden_text=token), member_key, api_name)
    _validate_capture({key: item[3] for key, item in captured.items()})
    files = {item[4]: item[1] for item in captured.values()}
    snapshot = freeze_source_snapshot(members=tuple(RawSourceMember(key, value, "0644", acquired_at_epoch_nanoseconds, None) for key, value in sorted(files.items())), provenance=SourceSnapshotProvenance(vendor_key="tushare.pro", source_key="tushare.pro.via.xiaodefa.approved-proxy.000703.sz.20240102.development-smoke", license_ref="tushare.pro.terms", retention_policy_ref="backtest.acquisition.candidate")).snapshot
    if snapshot is None:
        raise AcquisitionError("SourceSnapshot freeze failed")
    provider_requests = [{"api_name": item[5], "params": item[0]["params"], "fields": item[0]["fields"], "member_key": item[4], "auth_mode": "x-api-key", "attempts": item[2], "response_byte_count": len(item[1]), "response_sha256": sha256(item[1]), "returned_row_count": len(item[3]), "provider_revision_id": None, "declared_sha256": None} for item in captured.values()]
    declaration = {"type": "tushare_000703_development_smoke_declaration_v1", "schema_version": 1, "request": request.to_canonical_dict(), "raw_members": {key: sha256(value) for key, value in sorted(files.items())}, "frozen_authority": authority, "negative_evidence": {"stock_st_terminal_zero": True, "suspend_d_s_terminal_zero": True, "suspend_d_r_terminal_zero": True, "classification": "STANDARD + NORMAL", "corporate_action_absence_claimed": False}, "source_bounded": True, "development_only": True, "decision_grade_eligible": False, "live_eligible": False, "deployment_authorized": False}
    declaration_bytes = json_bytes(declaration)
    receipt: dict[str, object] = {"type": "tushare_000703_development_smoke_acquisition_receipt_v1", "schema_version": 1, "request": request.to_canonical_dict(), "provider_key": "tushare.pro", "transport_proxy_key": _PROXY_KEY, "transport_endpoint": endpoint, "provider_requests": provider_requests, "acquired_at_epoch_nanoseconds": acquired_at_epoch_nanoseconds, "snapshot": snapshot.to_canonical_dict(), "declaration_sha256": sha256(declaration_bytes), "source_bounded": True, "development_only": True, "decision_grade_eligible": False, "live_eligible": False, "deployment_authorized": False}
    published = files | {"source-snapshot.json": json_bytes(snapshot.to_canonical_dict()), "declaration.json": declaration_bytes, "acquisition-receipt.json": json_bytes(receipt)}
    if any(token.encode() in value for value in published.values()):
        raise AcquisitionError("proxy response unexpectedly contains credential material")
    publish_directory(output_dir, published)
    return receipt


def verify_tushare_000703_development_smoke_v1(output_dir: str | Path) -> dict[str, object]:
    root = Path(output_dir)
    receipt_bytes, receipt = _load_json(root / "acquisition-receipt.json")
    declaration_bytes, declaration = _load_json(root / "declaration.json")
    snapshot_bytes, snapshot = _load_json(root / "source-snapshot.json")
    member_keys = {spec[3] for spec in _SPECS}
    expected_files = member_keys | {"acquisition-receipt.json", "declaration.json", "source-snapshot.json"}
    if {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()} != expected_files:
        raise AcquisitionError("published file set mismatch")
    expected_receipt_fields = {
        "type", "schema_version", "request", "provider_key", "transport_proxy_key",
        "transport_endpoint", "provider_requests", "acquired_at_epoch_nanoseconds", "snapshot",
        "declaration_sha256", "source_bounded", "development_only", "decision_grade_eligible",
        "live_eligible", "deployment_authorized",
    }
    expected_declaration_fields = {
        "type", "schema_version", "request", "raw_members", "frozen_authority",
        "negative_evidence", "source_bounded", "development_only", "decision_grade_eligible",
        "live_eligible", "deployment_authorized",
    }
    request = Tushare000703DevelopmentSmokeRequestV1().to_canonical_dict()
    flags = ("source_bounded", "development_only", "decision_grade_eligible", "live_eligible", "deployment_authorized")
    acquired_at = receipt.get("acquired_at_epoch_nanoseconds")
    if (
        set(receipt) != expected_receipt_fields
        or receipt.get("type") != "tushare_000703_development_smoke_acquisition_receipt_v1"
        or receipt.get("schema_version") != 1
        or receipt.get("request") != request
        or receipt.get("provider_key") != "tushare.pro"
        or receipt.get("transport_proxy_key") != _PROXY_KEY
        or receipt.get("transport_endpoint") not in _ALLOWED_ENDPOINTS
        or type(acquired_at) is not int
        or cast(int, acquired_at) < 0
        or any(type(receipt.get(flag)) is not bool for flag in flags)
        or tuple(receipt[flag] for flag in flags) != (True, True, False, False, False)
    ):
        raise AcquisitionError("receipt schema or policy flags mismatch")
    if (
        set(declaration) != expected_declaration_fields
        or declaration.get("type") != "tushare_000703_development_smoke_declaration_v1"
        or declaration.get("schema_version") != 1
        or declaration.get("request") != request
        or any(type(declaration.get(flag)) is not bool for flag in flags)
        or tuple(declaration[flag] for flag in flags) != (True, True, False, False, False)
        or declaration.get("negative_evidence") != {
            "stock_st_terminal_zero": True,
            "suspend_d_s_terminal_zero": True,
            "suspend_d_r_terminal_zero": True,
            "classification": "STANDARD + NORMAL",
            "corporate_action_absence_claimed": False,
        }
        or declaration.get("frozen_authority") != {
            "calendar": {"receipt_sha256": _CALENDAR_RECEIPT_HASH, "snapshot_id": _CALENDAR_SNAPSHOT_ID, "content_hash": _CALENDAR_CONTENT_HASH},
            "minute": {"receipt_sha256": _MINUTE_RECEIPT_HASH, "snapshot_id": _MINUTE_SNAPSHOT_ID, "content_hash": _MINUTE_CONTENT_HASH, "closed_bar_count": 48},
        }
    ):
        raise AcquisitionError("declaration schema or policy flags mismatch")
    raw_members = _object(declaration.get("raw_members"), "declaration raw-member manifest mismatch")
    files = {key: (root / key).read_bytes() for key in member_keys}
    if set(raw_members) != member_keys or any(raw_members[key] != sha256(files[key]) for key in member_keys):
        raise AcquisitionError("published raw member hash mismatch")
    captured: dict[str, list[list[object]]] = {}
    provider_requests = receipt.get("provider_requests")
    if type(provider_requests) is not list or len(provider_requests) != len(_SPECS):
        raise AcquisitionError("receipt provider request count mismatch")
    provider_request_fields = {
        "api_name", "params", "fields", "member_key", "auth_mode", "attempts",
        "response_byte_count", "response_sha256", "returned_row_count", "provider_revision_id",
        "declared_sha256",
    }
    for provider_request, (key, api_name, params, member_key) in zip(provider_requests, _SPECS, strict=True):
        item = _object(provider_request, "receipt provider request is invalid")
        source = files[member_key]
        if (
            set(item) != provider_request_fields
            or item.get("api_name") != api_name
            or item.get("params") != params
            or item.get("fields") != ",".join(_FIELDS[key])
            or item.get("member_key") != member_key
            or item.get("auth_mode") != "x-api-key"
            or type(item.get("attempts")) is not int
            or item["attempts"] not in range(1, 4)
            or type(item.get("response_byte_count")) is not int
            or item.get("response_byte_count") != len(source)
            or item.get("response_sha256") != sha256(source)
            or item.get("provider_revision_id") is not None
            or item.get("declared_sha256") is not None
        ):
            raise AcquisitionError("receipt provider request mismatch")
        rows = _authority_rows(source, api_name=api_name, expected_fields=_FIELDS[key], forbidden_text="\0")
        if item.get("returned_row_count") != len(rows):
            raise AcquisitionError("receipt provider row count mismatch")
        captured[key] = rows
    _validate_capture(captured)
    expected_snapshot = freeze_source_snapshot(
        members=tuple(RawSourceMember(key, value, "0644", cast(int, acquired_at), None) for key, value in sorted(files.items())),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro",
            source_key="tushare.pro.via.xiaodefa.approved-proxy.000703.sz.20240102.development-smoke",
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    if (
        expected_snapshot is None
        or snapshot != expected_snapshot.to_canonical_dict()
        or snapshot_bytes != json_bytes(snapshot)
        or receipt.get("snapshot") != snapshot
        or receipt.get("declaration_sha256") != sha256(declaration_bytes)
    ):
        raise AcquisitionError("published receipt, declaration, or snapshot identity mismatch")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture fixed 000703.SZ / 2024-01-02 development smoke evidence")
    parser.add_argument("--endpoint", choices=_ALLOWED_ENDPOINTS, default=_ALLOWED_ENDPOINTS[0])
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--calendar-authority-dir", required=True, type=Path)
    parser.add_argument("--minute-authority-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    token = os.environ.get("TUSHARE_PROXY_TOKEN", "")
    if not token:
        raise SystemExit("TUSHARE_PROXY_TOKEN must be provided through the environment")
    try:
        receipt = acquire_tushare_000703_development_smoke_v1(Tushare000703DevelopmentSmokeRequestV1(), token=token, endpoint=args.endpoint, output_dir=args.output_dir, calendar_authority_dir=args.calendar_authority_dir, minute_authority_dir=args.minute_authority_dir, acquired_at_epoch_nanoseconds=time.time_ns(), post=_stdlib_post)
    except (AcquisitionError, ValueError) as error:
        raise SystemExit(f"acquisition failed: {error}") from None
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
