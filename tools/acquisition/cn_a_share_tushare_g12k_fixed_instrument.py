from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from time import sleep as real_sleep
from typing import Any

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from crypto_quant_domain.canonical import canonical_sha256

from ._common import (
    AcquisitionError,
    Post,
    json_bytes,
    publish_directory,
    require_new_output,
    sha256,
)
from .cn_a_share_tushare import (
    _post_with_retries,
    _provider_body,
    _source_bounded_rows_v2,
    _stdlib_post,
)

_PROVIDER_KEY = "tushare.pro"
_API_NAME = "dividend"
_MEMBER_KEY = "response/dividend.json"
_SOURCE_KEY = "tushare.pro.g12k.fixed_instrument_dividend.000001.sz.20260706.20260730"
_CATALOG_HASH = (
    "sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc"
)
_SOURCE_SCOPE_HASH = (
    "sha256:5738442bf477fc2f60542fa4b0ddee7be8d737d068077eefaa63d72489935ed7"
)
_TS_CODE = "000001.SZ"
_COVERAGE_START_DATE = "20260706"
_COVERAGE_END_DATE_EXCLUSIVE = "20260731"
_START_NANOS = 1_783_267_200_000_000_000
_END_NANOS = 1_785_427_200_000_000_000
_DATE_RE = re.compile(r"[0-9]{8}\Z")

_DIVIDEND_FIELDS = (
    "ts_code",
    "end_date",
    "ann_date",
    "div_proc",
    "stk_div",
    "stk_bo_rate",
    "stk_co_rate",
    "cash_div",
    "cash_div_tax",
    "record_date",
    "ex_date",
    "pay_date",
    "div_listdate",
    "imp_ann_date",
    "base_date",
    "base_share",
)


_REQUEST_SCOPE_PREIMAGE = {
    "type": "g12k_fixed_instrument_acquisition_request_scope",
    "schema_version": 1,
    "provider_key": "tushare.pro",
    "api_name": "dividend",
    "params": {"ts_code": _TS_CODE},
    "fields": _DIVIDEND_FIELDS,
    "member_key": "response/dividend.json",
    "instrument_id": {
        "type": "instrument_id",
        "venue": "xshe",
        "stable_key": "000001",
    },
    "instrument_catalog_hash": _CATALOG_HASH,
    "venue_calendar": "XSHE",
    "provider_exchange": "SZSE",
    "coverage_start": {
        "type": "utc_instant",
        "epoch_nanoseconds": _START_NANOS,
    },
    "coverage_end_exclusive": {
        "type": "utc_instant",
        "epoch_nanoseconds": _END_NANOS,
    },
}

_REQUEST_SCOPE_HASH = canonical_sha256(_REQUEST_SCOPE_PREIMAGE)
if _REQUEST_SCOPE_HASH != _SOURCE_SCOPE_HASH:
    raise RuntimeError("request-scope hash contract mismatch")


def _request_scope_preimage() -> dict[str, object]:
    return copy.deepcopy(_REQUEST_SCOPE_PREIMAGE)


@dataclass(frozen=True, slots=True)
class TushareG12KFixedInstrumentSourceBoundedRequestV1:
    schema_version: int = 1
    ts_code: str = _TS_CODE
    coverage_start_date: str = _COVERAGE_START_DATE
    coverage_end_date_exclusive: str = _COVERAGE_END_DATE_EXCLUSIVE

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not int
            or self.schema_version != 1
            or type(self.ts_code) is not str
            or self.ts_code != _TS_CODE
            or type(self.coverage_start_date) is not str
            or self.coverage_start_date != _COVERAGE_START_DATE
            or type(self.coverage_end_date_exclusive) is not str
            or self.coverage_end_date_exclusive != _COVERAGE_END_DATE_EXCLUSIVE
        ):
            raise ValueError("request must be exact fixed instrument request scope")
        if _DATE_RE.fullmatch(self.coverage_start_date) is None:
            raise ValueError("coverage_start_date must be YYYYMMDD")
        if _DATE_RE.fullmatch(self.coverage_end_date_exclusive) is None:
            raise ValueError("coverage_end_date_exclusive must be YYYYMMDD")
        try:
            start = date.fromisoformat(
                f"{self.coverage_start_date[:4]}-{self.coverage_start_date[4:6]}-{self.coverage_start_date[6:]}"
            )
            end = date.fromisoformat(
                f"{self.coverage_end_date_exclusive[:4]}-{self.coverage_end_date_exclusive[4:6]}-{self.coverage_end_date_exclusive[6:]}"
            )
        except ValueError as error:
            raise ValueError("coverage dates must be canonical dates") from error
        if not end > start:
            raise ValueError("coverage interval must be non-empty")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "tushare_g12k_fixed_instrument_source_bounded_request",
            "schema_version": self.schema_version,
            "ts_code": self.ts_code,
            "coverage_start_date": self.coverage_start_date,
            "coverage_end_date_exclusive": self.coverage_end_date_exclusive,
        }


def _is_date(value: object) -> bool:
    if value is None:
        return True
    if type(value) is not str or _DATE_RE.fullmatch(value) is None:
        return False
    if value != value.strip():
        return False
    try:
        date.fromisoformat(f"{value[:4]}-{value[4:6]}-{value[6:]}")
    except ValueError:
        return False
    return True


def _is_number(value: object) -> bool:
    if value is None:
        return True
    return type(value) is int or (type(value) is float and math.isfinite(value))


def _validate_rows(rows: list[list[object]]) -> None:
    for row in rows:
        if type(row[0]) is not str or row[0] != _TS_CODE:
            raise AcquisitionError(
                "provider dividend response does not exact-cover request"
            )
        if type(row[3]) is not str:
            raise AcquisitionError(
                "provider dividend response has invalid declaration field"
            )
        for index in (1, 2, 9, 10, 11, 12, 13, 14):
            if not _is_date(row[index]):
                raise AcquisitionError(
                    "provider dividend response has invalid date field"
                )
        for index in (4, 5, 6, 7, 8, 15):
            if not _is_number(row[index]):
                raise AcquisitionError(
                    "provider dividend response has invalid numeric field"
                )


def _parse_response(
    response_bytes: bytes, token: str
) -> tuple[list[list[object]], bool, int]:
    rows, has_more, count = _source_bounded_rows_v2(
        response_bytes,
        api_name=_API_NAME,
        expected_fields=_DIVIDEND_FIELDS,
        forbidden_text=token,
    )
    if type(count) is not int:
        raise AcquisitionError("provider dividend response has invalid count")
    if count < 0:
        raise AcquisitionError("provider dividend response has invalid count")
    _validate_rows(rows)
    return rows, has_more, count


def _build_snapshot(
    response_bytes: bytes, response_received_at: int
) -> dict[str, object]:
    snapshot = freeze_source_snapshot(
        members=(
            RawSourceMember(
                _MEMBER_KEY,
                response_bytes,
                "0644",
                response_received_at,
                None,
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key=_PROVIDER_KEY,
            source_key=_SOURCE_KEY,
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    if snapshot is None:
        raise AcquisitionError("G12A snapshot freeze failed")
    return snapshot.to_canonical_dict()


def acquire_tushare_g12k_fixed_instrument_source_bounded_v1(
    request: TushareG12KFixedInstrumentSourceBoundedRequestV1,
    *,
    token: str,
    output_dir: str | Path,
    post: Post,
    time_ns: Any = time.time_ns,
    sleep: Any = real_sleep,
) -> dict[str, object]:
    if type(request) is not TushareG12KFixedInstrumentSourceBoundedRequestV1:
        raise AcquisitionError(
            "request must be exact fixed-instrument source bounded request"
        )
    try:
        reconstructed_request = TushareG12KFixedInstrumentSourceBoundedRequestV1(
            schema_version=request.schema_version,
            ts_code=request.ts_code,
            coverage_start_date=request.coverage_start_date,
            coverage_end_date_exclusive=request.coverage_end_date_exclusive,
        )
    except (AttributeError, TypeError, ValueError):
        raise AcquisitionError(
            "request must be exact fixed-instrument source bounded request"
        ) from None
    if reconstructed_request != request:
        raise AcquisitionError("request reconstruction mismatch")
    request = reconstructed_request
    if type(token) is not str or not token or token != token.strip():
        raise AcquisitionError("TUSHARE_TOKEN must be canonical non-empty text")
    if not callable(time_ns):
        raise AcquisitionError("time_ns must be callable")
    if not callable(sleep):
        raise AcquisitionError("sleep must be callable")
    require_new_output(output_dir)

    request_body = _provider_body(
        api_name=_API_NAME,
        token=token,
        params={"ts_code": request.ts_code},
        fields=_DIVIDEND_FIELDS,
    )
    response_bytes, attempts = _post_with_retries(_API_NAME, request_body, post, sleep)

    try:
        response_received_at = time_ns()
    except Exception:  # noqa: BLE001 - injected clock failures are sanitized
        raise AcquisitionError("response receipt clock failed") from None
    if type(response_received_at) is not int or response_received_at < 0:
        raise AcquisitionError("response receipt time must be nonnegative integer")

    rows, has_more, count = _parse_response(response_bytes, token)

    provider_request = {
        "api_name": _API_NAME,
        "params": request_body["params"],
        "fields": ",".join(_DIVIDEND_FIELDS),
        "member_key": _MEMBER_KEY,
        "attempts": attempts,
        "response_received_at_epoch_nanoseconds": response_received_at,
        "response_byte_count": len(response_bytes),
        "response_sha256": sha256(response_bytes),
        "returned_row_count": len(rows),
        "observed_envelope": {"has_more": has_more, "count": count},
        "declared_sha256": None,
        "provider_revision_id": None,
    }

    snapshot = _build_snapshot(response_bytes, response_received_at)
    receipt: dict[str, object] = {
        "type": "tushare_g12k_fixed_instrument_source_bounded_acquisition_receipt",
        "schema_version": 1,
        "request": request.to_canonical_dict(),
        "request_scope_hash": _SOURCE_SCOPE_HASH,
        "provider_requests": [provider_request],
        "acquired_at_epoch_nanoseconds": response_received_at,
        "snapshot": snapshot,
        "provider_declared_sha256": None,
        "provider_revision_id": None,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }

    published = {
        _MEMBER_KEY: response_bytes,
        "acquisition-receipt.json": json_bytes(receipt),
    }
    if any(token.encode() in value for value in published.values()):
        raise AcquisitionError(
            "provider response unexpectedly contains credential material"
        )
    publish_directory(output_dir, published)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Acquire the frozen G12K fixed-instrument dividend response bytes"
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        raise SystemExit("TUSHARE_TOKEN must be provided through the environment")
    try:
        receipt = acquire_tushare_g12k_fixed_instrument_source_bounded_v1(
            TushareG12KFixedInstrumentSourceBoundedRequestV1(),
            token=token,
            output_dir=arguments.output_dir,
            post=_stdlib_post,
        )
    except (AcquisitionError, ValueError) as error:
        raise SystemExit(f"acquisition failed: {error}") from None
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
