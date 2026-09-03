"""Source-bounded Tushare dividend authority for 000703.SZ."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
import math
import os
from pathlib import Path
import time
from collections.abc import Callable
from time import sleep as real_sleep

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
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


_TS_CODE = "000703.SZ"
_COVERAGE_START = "20240102"
_COVERAGE_END_EXCLUSIVE = "20260901"
_MEMBER_KEY = "response/dividend.json"
_FIELDS = (
    "ts_code", "end_date", "ann_date", "div_proc", "stk_div", "stk_bo_rate",
    "stk_co_rate", "cash_div", "cash_div_tax", "record_date", "ex_date",
    "pay_date", "div_listdate", "imp_ann_date",
)
ProxyPost = Callable[[str, dict[str, object], dict[str, str]], tuple[int, bytes]]


@dataclass(frozen=True, slots=True)
class Tushare000703DividendAuthorityRequest:
    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "tushare_000703_dividend_authority_request_v1",
            "schema_version": 1,
            "ts_code": _TS_CODE,
            "coverage_start_date": _COVERAGE_START,
            "coverage_end_date_exclusive": _COVERAGE_END_EXCLUSIVE,
        }


def _date_or_none(value: object) -> bool:
    if value is None:
        return True
    if type(value) is not str or len(value) != 8 or not value.isascii() or not value.isdigit():
        return False
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError:
        return False
    return True


def _number_or_none(value: object) -> bool:
    if value is None:
        return True
    if type(value) not in (int, float):
        return False
    return math.isfinite(float(value))


def _validate_rows(rows: list[list[object]]) -> None:
    seen = set()
    for row in rows:
        if row[0] != _TS_CODE:
            raise AcquisitionError("provider dividend response does not exact-cover 000703.SZ")
        if type(row[3]) is not str or not row[3].strip():
            raise AcquisitionError("provider dividend response has invalid procedure")
        if any(not _date_or_none(row[index]) for index in (1, 2, 9, 10, 11, 12, 13)):
            raise AcquisitionError("provider dividend response has invalid date")
        if any(not _number_or_none(row[index]) for index in (4, 5, 6, 7, 8)):
            raise AcquisitionError("provider dividend response has invalid numeric value")
        identity = tuple(row)
        if identity in seen:
            raise AcquisitionError("provider dividend response has duplicate row")
        seen.add(identity)


def _action_selection(rows: list[list[object]]) -> dict[str, object]:
    selected = []
    out_of_scope = 0
    for index, row in enumerate(rows):
        if row[3] != "实施":
            continue
        record_date = row[9]
        if type(record_date) is not str:
            raise AcquisitionError("implementation dividend row lacks record_date")
        row_hash = sha256(json_bytes(row))
        if _COVERAGE_START <= record_date < _COVERAGE_END_EXCLUSIVE:
            selected.append(
                {
                    "row_index": index,
                    "row_sha256": row_hash,
                    "record_date": record_date,
                    "ex_date": row[10],
                }
            )
        else:
            out_of_scope += 1
    return {
        "basis": "div_proc=实施 + record_date",
        "coverage_start_date": _COVERAGE_START,
        "coverage_end_date_exclusive": _COVERAGE_END_EXCLUSIVE,
        "selected_implementation_rows": selected,
        "out_of_scope_implementation_row_count": out_of_scope,
    }


def _snapshot(raw: bytes, acquired_at: int, endpoint: str) -> dict[str, object]:
    value = freeze_source_snapshot(
        members=(RawSourceMember(_MEMBER_KEY, raw, "0644", acquired_at, None),),
        provenance=SourceSnapshotProvenance(
            "tushare.pro",
            (
                "tushare.pro.via.xiaodefa.approved-proxy."
                f"{endpoint.removeprefix('https://')}.000703.sz.dividend.authority.v1"
            ),
            "tushare.pro.terms",
            "backtest.acquisition.candidate",
        ),
    ).snapshot
    if value is None:
        raise AcquisitionError("SourceSnapshot freeze failed")
    return value.to_canonical_dict()


def acquire_tushare_000703_dividend_authority_v1(
    request: Tushare000703DividendAuthorityRequest,
    *,
    token: str,
    endpoint: str,
    output_dir: str | Path,
    post: ProxyPost,
    clock: Callable[[], int] = time.time_ns,
    sleep: Callable[[float], object] = real_sleep,
) -> dict[str, object]:
    if type(request) is not Tushare000703DividendAuthorityRequest:
        raise TypeError("request must be concrete Tushare000703DividendAuthorityRequest")
    require_new_output(output_dir)
    if (
        type(token) is not str
        or len(token) != 56
        or token != token.strip()
        or any(character.isspace() for character in token)
        or endpoint not in _ALLOWED_ENDPOINTS
    ):
        raise AcquisitionError("invalid acquisition inputs")
    body = _request_body("dividend", {"ts_code": _TS_CODE}, _FIELDS)
    raw, attempts = _post_with_retries(
        "dividend",
        endpoint=endpoint,
        body=body,
        headers=_headers(token),
        post=post,
        sleep=sleep,
    )
    acquired_at = clock()
    if type(acquired_at) is not int or acquired_at < 0:
        raise AcquisitionError("clock must return a nonnegative integer nanosecond timestamp")
    rows = _authority_rows(raw, api_name="dividend", expected_fields=_FIELDS, forbidden_text=token)
    _validate_rows(rows)
    action_selection = _action_selection(rows)
    provider_request = {
        "api_name": "dividend",
        "params": body["params"],
        "fields": body["fields"],
        "member_key": _MEMBER_KEY,
        "auth_mode": "x-api-key",
        "attempts": attempts,
        "response_byte_count": len(raw),
        "response_sha256": sha256(raw),
        "response_acquired_at_epoch_nanoseconds": acquired_at,
        "returned_row_count": len(rows),
        "provider_revision_id": None,
        "declared_sha256": None,
    }
    receipt = {
        "type": "tushare_000703_dividend_authority_acquisition_receipt_v1",
        "schema_version": 1,
        "request": request.to_canonical_dict(),
        "provider_key": "tushare.pro",
        "transport_proxy_key": _PROXY_KEY,
        "transport_endpoint": endpoint,
        "provider_request": provider_request,
        "acquired_at_epoch_nanoseconds": acquired_at,
        "snapshot": _snapshot(raw, acquired_at, endpoint),
        "action_selection": action_selection,
        "tushare_dividend_assumed_correct": True,
        "zero_row_authoritative": True,
        "source_bounded": True,
        "development_only": True,
        "decision_grade_eligible": False,
        "live_eligible": False,
        "deployment_authorized": False,
    }
    published = {_MEMBER_KEY: raw, "acquisition-receipt.json": json_bytes(receipt)}
    if any(token.encode() in value for value in published.values()):
        raise AcquisitionError("proxy response unexpectedly contains credential material")
    publish_directory(output_dir, published)
    return receipt


def _load(path: Path) -> tuple[bytes, dict[str, object]]:
    def object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        raw = path.read_bytes()
        value = json.loads(raw, object_pairs_hook=object_pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise AcquisitionError("retained dividend authority JSON is invalid") from error
    if type(value) is not dict:
        raise AcquisitionError("retained dividend authority JSON must be an object")
    return raw, value


def verify_tushare_000703_dividend_authority_v1(output_dir: str | Path) -> dict[str, object]:
    root = Path(output_dir)
    receipt_bytes, receipt = _load(root / "acquisition-receipt.json")
    try:
        raw = (root / _MEMBER_KEY).read_bytes()
    except OSError as error:
        raise AcquisitionError("retained dividend response is missing") from error
    if {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()} != {
        _MEMBER_KEY, "acquisition-receipt.json"
    }:
        raise AcquisitionError("retained dividend authority file set mismatch")
    expected_fields = {
        "type", "schema_version", "request", "provider_key", "transport_proxy_key",
        "transport_endpoint", "provider_request", "acquired_at_epoch_nanoseconds",
        "snapshot", "action_selection", "tushare_dividend_assumed_correct", "zero_row_authoritative",
        "source_bounded", "development_only", "decision_grade_eligible", "live_eligible",
        "deployment_authorized",
    }
    request = Tushare000703DividendAuthorityRequest().to_canonical_dict()
    provider = receipt.get("provider_request")
    acquired_at = receipt.get("acquired_at_epoch_nanoseconds")
    provider_fields = {
        "api_name", "params", "fields", "member_key", "auth_mode", "attempts",
        "response_byte_count", "response_sha256", "response_acquired_at_epoch_nanoseconds",
        "returned_row_count", "provider_revision_id", "declared_sha256",
    }
    if (
        set(receipt) != expected_fields
        or receipt.get("type") != "tushare_000703_dividend_authority_acquisition_receipt_v1"
        or receipt.get("schema_version") != 1
        or receipt.get("request") != request
        or receipt.get("provider_key") != "tushare.pro"
        or receipt.get("transport_proxy_key") != _PROXY_KEY
        or receipt.get("transport_endpoint") not in _ALLOWED_ENDPOINTS
        or type(acquired_at) is not int
        or acquired_at < 0
        or type(provider) is not dict
        or set(provider) != provider_fields
        or provider.get("api_name") != "dividend"
        or provider.get("params") != {"ts_code": _TS_CODE}
        or provider.get("fields") != ",".join(_FIELDS)
        or provider.get("member_key") != _MEMBER_KEY
        or provider.get("auth_mode") != "x-api-key"
        or type(provider.get("attempts")) is not int
        or provider["attempts"] not in range(1, 4)
        or provider.get("response_byte_count") != len(raw)
        or provider.get("response_sha256") != sha256(raw)
        or provider.get("response_acquired_at_epoch_nanoseconds") != acquired_at
        or provider.get("provider_revision_id") is not None
        or provider.get("declared_sha256") is not None
        or receipt_bytes != json_bytes(receipt)
        or receipt.get("action_selection") != _action_selection(_authority_rows(raw, api_name="dividend", expected_fields=_FIELDS, forbidden_text="\0"))
        or tuple(receipt.get(key) for key in (
            "tushare_dividend_assumed_correct", "zero_row_authoritative", "source_bounded",
            "development_only", "decision_grade_eligible", "live_eligible", "deployment_authorized",
        )) != (True, True, True, True, False, False, False)
    ):
        raise AcquisitionError("retained dividend receipt schema or identity mismatch")
    rows = _authority_rows(raw, api_name="dividend", expected_fields=_FIELDS, forbidden_text="\0")
    _validate_rows(rows)
    if provider.get("returned_row_count") != len(rows):
        raise AcquisitionError("retained dividend row count mismatch")
    if receipt.get("snapshot") != _snapshot(raw, acquired_at, receipt["transport_endpoint"]):
        raise AcquisitionError("retained dividend snapshot mismatch")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture 000703.SZ Tushare dividend authority")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--endpoint", choices=_ALLOWED_ENDPOINTS, default=_ALLOWED_ENDPOINTS[0])
    args = parser.parse_args(argv)
    try:
        acquire_tushare_000703_dividend_authority_v1(
            Tushare000703DividendAuthorityRequest(),
            token=os.environ.get("TUSHARE_PROXY_TOKEN", ""),
            endpoint=args.endpoint,
            output_dir=args.output_dir,
            post=_stdlib_post,
        )
    except AcquisitionError as error:
        raise SystemExit(f"acquisition failed: {error}") from None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
