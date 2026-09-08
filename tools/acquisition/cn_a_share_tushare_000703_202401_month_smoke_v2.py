from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from time import sleep as real_sleep

from crypto_quant_bundle_builder import RawSourceMember, SourceSnapshotProvenance, freeze_source_snapshot

from ._common import AcquisitionError, json_bytes, publish_directory, require_new_output, sha256
from .cn_a_share_tushare_000703_20240102_smoke_v1 import _FIELDS, _is_real_historical_date
from .cn_a_share_tushare_authority import _authority_rows
from .cn_a_share_tushare_listing_source_bounded_v2 import _ALLOWED_ENDPOINTS, _PROXY_KEY, _headers, _post_with_retries, _request_body, _stdlib_post
from .cn_a_share_tushare_minute_source_bounded_v2 import verify_tushare_minute_source_bounded_receipt_v2
from .cn_a_share_tushare_proxy_trade_calendar_month_source_bounded_v2 import verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v2

_TS_CODE = "000703.SZ"
_MONTH = "202401"
_WORKLIST = ("20240102", "20240103", "20240104", "20240105", "20240108", "20240109", "20240110", "20240111", "20240112", "20240115", "20240116", "20240117", "20240118", "20240119", "20240122", "20240123", "20240124", "20240125", "20240126", "20240129", "20240130", "20240131")
ProxyPost = Callable[[str, dict[str, object], dict[str, str]], tuple[int, bytes]]


def _load_snapshot(root: Path, member_key: str):
    try:
        raw = (root / member_key).read_bytes()
        receipt_bytes = (root / "acquisition-receipt.json").read_bytes()
        receipt = json.loads(receipt_bytes)
        if type(receipt) is not dict or type(receipt.get("snapshot")) is not dict:
            raise ValueError("missing snapshot")
        data = receipt["snapshot"]
        provenance = data.get("provenance")
        members = data.get("members")
        if type(provenance) is not dict or type(members) is not list or len(members) != 1 or type(members[0]) is not dict:
            raise ValueError("invalid snapshot")
        acquired_at = members[0].get("acquired_at_epoch_nanoseconds")
        if type(acquired_at) is not int or acquired_at < 0 or any(type(provenance.get(key)) is not str for key in ("vendor_key", "source_key", "license_ref", "retention_policy_ref")):
            raise ValueError("invalid snapshot metadata")
        snapshot = freeze_source_snapshot(
            members=(RawSourceMember(member_key, raw, "0644", acquired_at, None),),
            provenance=SourceSnapshotProvenance(
                provenance["vendor_key"], provenance["source_key"],
                provenance["license_ref"], provenance["retention_policy_ref"],
            ),
        ).snapshot
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise AcquisitionError("retained authority snapshot is invalid") from error
    if snapshot is None:
        raise AcquisitionError("retained snapshot freeze failed")
    return receipt_bytes, snapshot


def _number(value: object) -> float:
    if type(value) not in (int, float):
        raise AcquisitionError("response has invalid numeric value")
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise AcquisitionError("response has invalid numeric value") from error
    if not math.isfinite(number):
        raise AcquisitionError("response has invalid numeric value")
    return number


def _positive(value: object) -> bool:
    return _number(value) > 0


def _validate(stock: list[list[object]], daily: list[list[object]], limits: list[list[object]], exceptions: Mapping[str, list[list[object]]], day: str) -> None:
    if len(stock) != 1 or stock[0][0] != _TS_CODE or stock[0][1] != "000703" or stock[0][5:8] != ["主板", "SZSE", "L"] or not _is_real_historical_date(stock[0][8]) or stock[0][8] > day or (stock[0][9] is not None and (not _is_real_historical_date(stock[0][9]) or stock[0][9] < day)):
        raise AcquisitionError("stock_basic does not establish Main seasoned listed scope")
    if len(daily) != 1 or daily[0][:2] != [_TS_CODE, day]:
        raise AcquisitionError("daily response does not exact-cover valid target scope")
    open_, high, low, close, pre_close, _change, _pct_chg, volume, amount = (
        _number(value) for value in daily[0][2:]
    )
    if not (
        0 < low <= open_ <= high
        and 0 < low <= close <= high
        and pre_close > 0
        and volume >= 0
        and amount >= 0
    ):
        raise AcquisitionError("daily response does not exact-cover valid target scope")
    if len(limits) != 1 or limits[0][:2] != [day, _TS_CODE] or not all(_positive(value) for value in limits[0][2:]) or not _number(limits[0][3]) <= _number(daily[0][6]) <= _number(limits[0][2]):
        raise AcquisitionError("stk_limit response does not exact-cover valid target limits")
    if any(exceptions.values()):
        raise AcquisitionError("exception row prevents STANDARD + NORMAL negative evidence")


def acquire_tushare_000703_202401_month_smoke_v2(*, token: str, endpoint: str, output_dir: str | Path, calendar_authority_dir: str | Path, minute_authority_root: str | Path, calendar_receipt_hash: str, minute_receipt_hashes: Mapping[str, str], post: ProxyPost, clock: Callable[[], int] = time.time_ns, sleep: Callable[[float], object] = real_sleep) -> dict[str, object]:
    require_new_output(output_dir)
    if type(token) is not str or len(token) != 56 or token != token.strip() or any(character.isspace() for character in token) or endpoint not in _ALLOWED_ENDPOINTS or not isinstance(minute_receipt_hashes, Mapping):
        raise AcquisitionError("invalid acquisition inputs")
    calendar_bytes, calendar_snapshot = _load_snapshot(Path(calendar_authority_dir), "response/trade-calendar.json")
    calendar = verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v2(calendar_bytes, calendar_snapshot, calendar_receipt_hash)
    if calendar["request"] != {"type": "tushare_proxy_trade_calendar_month_source_bounded_request_v2", "schema_version": 2, "exchange": "SZSE", "month": _MONTH} or calendar["open_sessions"] != list(_WORKLIST):
        raise AcquisitionError("calendar does not exact-cover January worklist")
    minute_authority: dict[str, str] = {}
    for day in _WORKLIST:
        receipt_bytes, snapshot = _load_snapshot(Path(minute_authority_root) / day, "response/stk-mins.json")
        receipt = verify_tushare_minute_source_bounded_receipt_v2(receipt_bytes, snapshot, minute_receipt_hashes.get(day, ""))
        if receipt["request"]["trade_date"] != day:
            raise AcquisitionError("minute authority does not exact-cover January worklist")
        minute_authority[day] = sha256(receipt_bytes)
    specs = (
        ("daily", "daily", _FIELDS["daily"], "daily"),
        ("stk_limit", "stk_limit", _FIELDS["stk_limit"], "stk-limit"),
        ("stock_st", "stock_st", _FIELDS["stock_st"], "stock-st"),
        ("suspend_s", "suspend_d", _FIELDS["suspend_s"], "suspend-d-s"),
        ("suspend_r", "suspend_d", _FIELDS["suspend_r"], "suspend-d-r"),
    )
    files: dict[str, bytes] = {}
    requests: list[dict[str, object]] = []
    request_count = 0

    def capture(
        api_name: str,
        params: dict[str, object],
        fields: tuple[str, ...],
    ) -> tuple[dict[str, object], bytes, int, int, list[list[object]]]:
        nonlocal request_count
        if request_count:
            sleep(0.5)
        body = _request_body(api_name, params, fields)
        source, attempts = _post_with_retries(
            api_name,
            endpoint=endpoint,
            body=body,
            headers=_headers(token),
            post=post,
            sleep=sleep,
        )
        response_acquired_at_epoch_nanoseconds = clock()
        if type(response_acquired_at_epoch_nanoseconds) is not int or response_acquired_at_epoch_nanoseconds < 0:
            raise AcquisitionError("clock must return a nonnegative integer nanosecond timestamp")
        rows = _authority_rows(
            source,
            api_name=api_name,
            expected_fields=fields,
            forbidden_text=token,
        )
        request_count += 1
        return body, source, attempts, response_acquired_at_epoch_nanoseconds, rows

    body, source, attempts, stock_time, stock = capture(
        "stock_basic",
        {"ts_code": _TS_CODE, "list_status": "L"},
        _FIELDS["stock_basic"],
    )
    files["response/stock-basic.json"] = source
    requests.append(
        {
            "api_name": "stock_basic",
            "params": body["params"],
            "fields": body["fields"],
            "member_key": "response/stock-basic.json",
            "auth_mode": "x-api-key",
            "attempts": attempts,
            "response_byte_count": len(source),
            "response_sha256": sha256(source), "response_acquired_at_epoch_nanoseconds": stock_time,
            "returned_row_count": len(stock),
            "provider_revision_id": None,
            "declared_sha256": None,
        }
    )
    for day in _WORKLIST:
        captured: dict[str, list[list[object]]] = {}
        for key, api_name, fields, filename in specs:
            params = (
                {"ts_code": _TS_CODE, "trade_date": day}
                if key in {"stk_limit", "suspend_s", "suspend_r"}
                else {"ts_code": _TS_CODE, "start_date": day, "end_date": day}
            )
            if key == "suspend_s":
                params["suspend_type"] = "S"
            if key == "suspend_r":
                params["suspend_type"] = "R"
            body, source, attempts, response_time, rows = capture(api_name, params, fields)
            captured[key] = rows
            member_key = f"response/{day}/{filename}.json"
            files[member_key] = source
            requests.append(
                {
                    "api_name": api_name,
                    "params": params,
                    "fields": body["fields"],
                    "member_key": member_key,
                    "auth_mode": "x-api-key",
                    "attempts": attempts,
                    "response_byte_count": len(source),
                    "response_sha256": sha256(source), "response_acquired_at_epoch_nanoseconds": response_time,
                    "returned_row_count": len(rows),
                    "provider_revision_id": None,
                    "declared_sha256": None,
                }
            )
        _validate(
            stock,
            captured["daily"],
            captured["stk_limit"],
            {key: captured[key] for key in ("stock_st", "suspend_s", "suspend_r")},
            day,
        )
    snapshot = freeze_source_snapshot(members=tuple(RawSourceMember(key, value, "0644", next(item["response_acquired_at_epoch_nanoseconds"] for item in requests if item["member_key"] == key), None) for key, value in sorted(files.items())), provenance=SourceSnapshotProvenance("tushare.pro", f"tushare.pro.via.xiaodefa.approved-proxy.{endpoint.removeprefix('https://')}.000703.sz.202401.month-development-smoke", "tushare.pro.terms", "backtest.acquisition.candidate")).snapshot
    if snapshot is None: raise AcquisitionError("SourceSnapshot freeze failed")
    declaration = {"type":"tushare_000703_202401_month_development_smoke_declaration_v2", "schema_version":2, "ts_code":_TS_CODE, "month":_MONTH, "raw_members":{key:{"sha256":sha256(value),"acquired_at_epoch_nanoseconds":next(item["response_acquired_at_epoch_nanoseconds"] for item in requests if item["member_key"] == key)} for key,value in sorted(files.items())}, "calendar_receipt_sha256":calendar_receipt_hash, "minute_receipt_sha256":minute_authority, "negative_evidence":{"stock_st_terminal_zero":True, "suspend_d_s_terminal_zero":True, "suspend_d_r_terminal_zero":True, "classification":"STANDARD + NORMAL", "corporate_action_absence_claimed":False}, "source_bounded":True, "development_only":True, "decision_grade_eligible":False, "live_eligible":False, "deployment_authorized":False}
    declaration_bytes=json_bytes(declaration)
    receipt={"type":"tushare_000703_202401_month_development_smoke_acquisition_receipt_v2", "schema_version":2, "ts_code":_TS_CODE, "month":_MONTH, "provider_key":"tushare.pro", "transport_proxy_key":_PROXY_KEY, "transport_endpoint":endpoint, "provider_requests":requests, "acquired_at_epoch_nanoseconds":max(item["response_acquired_at_epoch_nanoseconds"] for item in requests), "snapshot":snapshot.to_canonical_dict(), "declaration_sha256":sha256(declaration_bytes), "source_bounded":True, "development_only":True, "decision_grade_eligible":False, "live_eligible":False, "deployment_authorized":False}
    published=files | {"source-snapshot.json":json_bytes(snapshot.to_canonical_dict()), "declaration.json":declaration_bytes, "acquisition-receipt.json":json_bytes(receipt)}
    if any(token.encode() in value for value in published.values()): raise AcquisitionError("proxy response unexpectedly contains credential material")
    publish_directory(output_dir, published); return receipt


def _load_json(path: Path) -> tuple[bytes, dict[str, object]]:
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
        raw = path.read_bytes()
        value = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise AcquisitionError("retained monthly smoke JSON is invalid") from error
    if type(value) is not dict:
        raise AcquisitionError("retained monthly smoke JSON must be an object")
    return raw, value


def verify_tushare_000703_202401_month_smoke_v2(
    output_dir: str | Path, *, calendar_authority_dir: str | Path,
    minute_authority_root: str | Path,
) -> dict[str, object]:
    """Verify all retained authorities for the fixed January monthly smoke output."""
    root = Path(output_dir)
    receipt_bytes, receipt = _load_json(root / "acquisition-receipt.json")
    declaration_bytes, declaration = _load_json(root / "declaration.json")
    snapshot_bytes, published_snapshot = _load_json(root / "source-snapshot.json")
    member_keys = {"response/stock-basic.json"} | {
        f"response/{day}/{filename}.json" for day in _WORKLIST
        for _, _, _, filename in (
            ("daily", "daily", _FIELDS["daily"], "daily"),
            ("stk_limit", "stk_limit", _FIELDS["stk_limit"], "stk-limit"),
            ("stock_st", "stock_st", _FIELDS["stock_st"], "stock-st"),
            ("suspend_s", "suspend_d", _FIELDS["suspend_s"], "suspend-d-s"),
            ("suspend_r", "suspend_d", _FIELDS["suspend_r"], "suspend-d-r"),
        )
    }
    expected_files = member_keys | {
        "acquisition-receipt.json", "declaration.json", "source-snapshot.json",
    }
    try:
        found_files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
        files = {key: (root / key).read_bytes() for key in member_keys}
    except OSError as error:
        raise AcquisitionError("retained monthly smoke raw member is missing") from error
    if found_files != expected_files:
        raise AcquisitionError("retained monthly smoke file set mismatch")
    receipt_fields = {
        "type", "schema_version", "ts_code", "month", "provider_key", "transport_proxy_key",
        "transport_endpoint", "provider_requests", "acquired_at_epoch_nanoseconds", "snapshot",
        "declaration_sha256", "source_bounded", "development_only", "decision_grade_eligible",
        "live_eligible", "deployment_authorized",
    }
    declaration_fields = {
        "type", "schema_version", "ts_code", "month", "raw_members", "calendar_receipt_sha256",
        "minute_receipt_sha256", "negative_evidence", "source_bounded", "development_only",
        "decision_grade_eligible", "live_eligible", "deployment_authorized",
    }
    flags = ("source_bounded", "development_only", "decision_grade_eligible", "live_eligible", "deployment_authorized")
    endpoint = receipt.get("transport_endpoint")
    acquired_at = receipt.get("acquired_at_epoch_nanoseconds")
    if (
        set(receipt) != receipt_fields
        or receipt.get("type") != "tushare_000703_202401_month_development_smoke_acquisition_receipt_v2"
        or receipt.get("schema_version") != 2 or receipt.get("ts_code") != _TS_CODE
        or receipt.get("month") != _MONTH or receipt.get("provider_key") != "tushare.pro"
        or receipt.get("transport_proxy_key") != _PROXY_KEY or endpoint not in _ALLOWED_ENDPOINTS
        or type(acquired_at) is not int or acquired_at < 0
        or any(type(receipt.get(flag)) is not bool for flag in flags)
        or tuple(receipt.get(flag) for flag in flags) != (True, True, False, False, False)
        or receipt_bytes != json_bytes(receipt)
    ):
        raise AcquisitionError("monthly receipt schema or transport mismatch")
    if (
        set(declaration) != declaration_fields
        or declaration.get("type") != "tushare_000703_202401_month_development_smoke_declaration_v2"
        or declaration.get("schema_version") != 2 or declaration.get("ts_code") != _TS_CODE
        or declaration.get("month") != _MONTH
        or any(type(declaration.get(flag)) is not bool for flag in flags)
        or tuple(declaration.get(flag) for flag in flags) != (True, True, False, False, False)
        or declaration.get("negative_evidence") != {
            "stock_st_terminal_zero": True, "suspend_d_s_terminal_zero": True,
            "suspend_d_r_terminal_zero": True, "classification": "STANDARD + NORMAL",
            "corporate_action_absence_claimed": False,
        }
        or declaration_bytes != json_bytes(declaration)
        or receipt.get("declaration_sha256") != sha256(declaration_bytes)
    ):
        raise AcquisitionError("monthly declaration schema or identity mismatch")
    raw_members = declaration.get("raw_members")
    requests = receipt.get("provider_requests")
    if type(raw_members) is not dict or set(raw_members) != member_keys or type(requests) is not list:
        raise AcquisitionError("monthly declaration raw-member manifest is invalid")
    request_by_key = {item.get("member_key"): item for item in requests if type(item) is dict}
    if set(request_by_key) != member_keys or any(
        type(raw_members[key]) is not dict
        or raw_members[key] != {
            "sha256": sha256(files[key]),
            "acquired_at_epoch_nanoseconds": request_by_key[key].get("response_acquired_at_epoch_nanoseconds"),
        }
        for key in member_keys
    ):
        raise AcquisitionError("monthly declaration raw-member manifest mismatch")
    expected_snapshot = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                key, value, "0644", request_by_key[key]["response_acquired_at_epoch_nanoseconds"], None
            )
            for key, value in sorted(files.items())
        ),
        provenance=SourceSnapshotProvenance(
            "tushare.pro",
            f"tushare.pro.via.xiaodefa.approved-proxy.{endpoint.removeprefix('https://')}.000703.sz.202401.month-development-smoke",
            "tushare.pro.terms", "backtest.acquisition.candidate",
        ),
    ).snapshot
    if (
        expected_snapshot is None or published_snapshot != expected_snapshot.to_canonical_dict()
        or snapshot_bytes != json_bytes(published_snapshot)
        or receipt.get("snapshot") != published_snapshot
    ):
        raise AcquisitionError("monthly source snapshot identity mismatch")
    specs = (
        ("daily", "daily", _FIELDS["daily"], "daily"),
        ("stk_limit", "stk_limit", _FIELDS["stk_limit"], "stk-limit"),
        ("stock_st", "stock_st", _FIELDS["stock_st"], "stock-st"),
        ("suspend_s", "suspend_d", _FIELDS["suspend_s"], "suspend-d-s"),
        ("suspend_r", "suspend_d", _FIELDS["suspend_r"], "suspend-d-r"),
    )
    request_fields = {
        "api_name", "params", "fields", "member_key", "auth_mode", "attempts",
        "response_byte_count", "response_sha256", "response_acquired_at_epoch_nanoseconds",
        "returned_row_count", "provider_revision_id", "declared_sha256",
    }
    expected_requests = [("stock_basic", {"ts_code": _TS_CODE, "list_status": "L"}, _FIELDS["stock_basic"], "response/stock-basic.json")]
    for day in _WORKLIST:
        for key, api_name, fields, filename in specs:
            params: dict[str, object] = (
                {"ts_code": _TS_CODE, "trade_date": day}
                if key in {"stk_limit", "suspend_s", "suspend_r"}
                else {"ts_code": _TS_CODE, "start_date": day, "end_date": day}
            )
            if key == "suspend_s": params["suspend_type"] = "S"
            if key == "suspend_r": params["suspend_type"] = "R"
            expected_requests.append((api_name, params, fields, f"response/{day}/{filename}.json"))
    if type(requests) is not list or len(requests) != len(expected_requests):
        raise AcquisitionError("monthly provider request count mismatch")
    if any(type(item) is not dict for item in requests) or acquired_at != max(
        item.get("response_acquired_at_epoch_nanoseconds", -1) for item in requests
    ):
        raise AcquisitionError("monthly receipt acquisition time mismatch")
    stock: list[list[object]] | None = None
    for item, (api_name, params, fields, member_key) in zip(requests, expected_requests, strict=True):
        if type(item) is not dict:
            raise AcquisitionError("monthly provider request is invalid")
        source = files[member_key]
        if (
            set(item) != request_fields or item.get("api_name") != api_name
            or item.get("params") != params or item.get("fields") != ",".join(fields)
            or item.get("member_key") != member_key or item.get("auth_mode") != "x-api-key"
            or type(item.get("attempts")) is not int or item["attempts"] not in range(1, 4)
            or type(item.get("response_byte_count")) is not int
            or type(item.get("response_acquired_at_epoch_nanoseconds")) is not int
            or item.get("response_acquired_at_epoch_nanoseconds") < 0
            or item.get("response_byte_count") != len(source) or item.get("response_sha256") != sha256(source)
            or type(item.get("returned_row_count")) is not int
            or item.get("provider_revision_id") is not None or item.get("declared_sha256") is not None
            or expected_snapshot.member_bytes(member_key) != source
            or next(member for member in expected_snapshot.members if member.member_key == member_key).acquired_at_epoch_nanoseconds != item.get("response_acquired_at_epoch_nanoseconds")
        ):
            raise AcquisitionError("monthly provider request mismatch")
        rows = _authority_rows(source, api_name=api_name, expected_fields=fields, forbidden_text="\0")
        if item.get("returned_row_count") != len(rows):
            raise AcquisitionError("monthly provider request row count mismatch")
        if member_key == "response/stock-basic.json": stock = rows
    if stock is None:
        raise AcquisitionError("monthly stock-basic member is missing")
    for day in _WORKLIST:
        daily = _authority_rows(files[f"response/{day}/daily.json"], api_name="daily", expected_fields=_FIELDS["daily"], forbidden_text="\0")
        limits = _authority_rows(files[f"response/{day}/stk-limit.json"], api_name="stk_limit", expected_fields=_FIELDS["stk_limit"], forbidden_text="\0")
        exceptions = {
            "stock_st": _authority_rows(files[f"response/{day}/stock-st.json"], api_name="stock_st", expected_fields=_FIELDS["stock_st"], forbidden_text="\0"),
            "suspend_s": _authority_rows(files[f"response/{day}/suspend-d-s.json"], api_name="suspend_d", expected_fields=_FIELDS["suspend_s"], forbidden_text="\0"),
            "suspend_r": _authority_rows(files[f"response/{day}/suspend-d-r.json"], api_name="suspend_d", expected_fields=_FIELDS["suspend_r"], forbidden_text="\0"),
        }
        _validate(stock, daily, limits, exceptions, day)
    calendar_hash = declaration.get("calendar_receipt_sha256")
    if type(calendar_hash) is not str:
        raise AcquisitionError("monthly calendar authority hash is invalid")
    calendar_bytes, calendar_snapshot = _load_snapshot(Path(calendar_authority_dir), "response/trade-calendar.json")
    calendar = verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v2(calendar_bytes, calendar_snapshot, calendar_hash)
    if calendar.get("request") != {"type": "tushare_proxy_trade_calendar_month_source_bounded_request_v2", "schema_version": 2, "exchange": "SZSE", "month": _MONTH} or calendar.get("open_sessions") != list(_WORKLIST):
        raise AcquisitionError("monthly calendar authority does not exact-cover January worklist")
    minute_hashes = declaration.get("minute_receipt_sha256")
    if type(minute_hashes) is not dict or set(minute_hashes) != set(_WORKLIST) or any(type(value) is not str for value in minute_hashes.values()):
        raise AcquisitionError("monthly minute authority manifest is invalid")
    for day in _WORKLIST:
        authority_root = Path(minute_authority_root)
        day_root = authority_root / day
        if not day_root.is_dir():
            day_root = authority_root / "sessions" / day
        minute_bytes, minute_snapshot = _load_snapshot(day_root, "response/stk-mins.json")
        minute = verify_tushare_minute_source_bounded_receipt_v2(minute_bytes, minute_snapshot, minute_hashes[day])
        if minute.get("request", {}).get("trade_date") != day:
            raise AcquisitionError("monthly minute authority does not exact-cover January worklist")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Capture fixed 000703.SZ January 2024 development smoke evidence")
    parser.add_argument("--output-dir", required=True, type=Path); parser.add_argument("--calendar-authority-dir", required=True, type=Path); parser.add_argument("--minute-authority-root", required=True, type=Path); parser.add_argument("--calendar-receipt-hash", required=True); parser.add_argument("--minute-receipt-hashes-json", required=True, type=Path); parser.add_argument("--endpoint", choices=_ALLOWED_ENDPOINTS, default=_ALLOWED_ENDPOINTS[0]); args=parser.parse_args(argv)
    try: acquire_tushare_000703_202401_month_smoke_v2(token=os.environ.get("TUSHARE_PROXY_TOKEN", ""), endpoint=args.endpoint, output_dir=args.output_dir, calendar_authority_dir=args.calendar_authority_dir, minute_authority_root=args.minute_authority_root, calendar_receipt_hash=args.calendar_receipt_hash, minute_receipt_hashes=json.loads(args.minute_receipt_hashes_json.read_bytes()), post=_stdlib_post)
    except (AcquisitionError, ValueError, OSError, json.JSONDecodeError) as error: raise SystemExit(f"acquisition failed: {error}") from None
    return 0

if __name__ == "__main__": raise SystemExit(main())
