from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)

from ._common import AcquisitionError, json_bytes, publish_directory, require_new_output, sha256
from .cn_a_share_tushare_authority import _authority_rows, _is_real_historical_date
from .cn_a_share_tushare_listing_source_bounded_v2 import (
    ProxyPost,
    _ALLOWED_ENDPOINTS,
    _PROXY_KEY,
    _headers,
    _post_with_retries,
    _request_body,
    _stdlib_post,
)


_FIXED_TS_CODE = "000651.SZ"
_FIXED_START_DATE = "20190506"
_FIXED_END_DATE = "20240506"
_EXPECTED_ROWS = 1213
_FIELDS = (
    "ts_code",
    "trade_date",
    "close",
    "pe",
    "pe_ttm",
    "total_share",
    "total_mv",
    "circ_mv",
)
_MEMBER_KEY = (
    "response/tushare/daily_basic/000651.SZ-20190506-20240506-v1.json"
)
_LIMITATIONS = (
    "source-bounded fixed issuer and date window only",
    "provider revision closure and exact historical availability are not established",
    "provider pe and pe_ttm have no formula-version or denominator-lineage authority",
    "share-count and corporate-action lineage are not established",
    "no Strategy, Backtest, Promotion, Live, or deployment authority is granted",
)


@dataclass(frozen=True, slots=True)
class TushareGreeValuationSourceBoundedRequestV1:
    ts_code: str = _FIXED_TS_CODE
    start_date: str = _FIXED_START_DATE
    end_date: str = _FIXED_END_DATE

    def __post_init__(self) -> None:
        if (
            self.ts_code != _FIXED_TS_CODE
            or self.start_date != _FIXED_START_DATE
            or self.end_date != _FIXED_END_DATE
        ):
            raise ValueError(
                "request must match fixed 000651.SZ / 20190506..20240506 scope"
            )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "tushare_gree_valuation_source_bounded_request_v1",
            "schema_version": 1,
            "ts_code": self.ts_code,
            "start_date": self.start_date,
            "end_date": self.end_date,
        }


def _positive_number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _optional_number(value: object) -> bool:
    return value is None or (type(value) in (int, float) and math.isfinite(value))


def _validate_rows(rows: list[list[object]]) -> None:
    if len(rows) != _EXPECTED_ROWS:
        raise AcquisitionError("provider daily_basic response cardinality mismatch")
    dates: set[str] = set()
    for row in rows:
        ts_code, trade_date, close, pe, pe_ttm, total_share, total_mv, circ_mv = row
        if ts_code != _FIXED_TS_CODE:
            raise AcquisitionError("provider daily_basic row is outside fixed issuer scope")
        if (
            type(trade_date) is not str
            or not _is_real_historical_date(trade_date)
            or not (_FIXED_START_DATE <= trade_date <= _FIXED_END_DATE)
        ):
            raise AcquisitionError("provider daily_basic row is outside fixed date scope")
        if trade_date in dates:
            raise AcquisitionError("provider daily_basic response has duplicate trade_date")
        dates.add(trade_date)
        if not all(
            _positive_number(value)
            for value in (close, total_share, total_mv, circ_mv)
        ):
            raise AcquisitionError("provider daily_basic row has invalid positive numeric")
        if not _optional_number(pe) or not _optional_number(pe_ttm):
            raise AcquisitionError("provider daily_basic row has invalid optional numeric")
    if {_FIXED_START_DATE, _FIXED_END_DATE} - dates:
        raise AcquisitionError("provider daily_basic response is missing fixed endpoint")


def acquire_tushare_gree_valuation_source_bounded_v1(
    request: TushareGreeValuationSourceBoundedRequestV1,
    *,
    token: str,
    endpoint: str,
    output_dir: str | Path,
    acquired_at_epoch_nanoseconds: int,
    post: ProxyPost,
    sleep: Callable[[float], object] = time.sleep,
) -> dict[str, object]:
    if type(request) is not TushareGreeValuationSourceBoundedRequestV1:
        raise AcquisitionError(
            "request must be exact TushareGreeValuationSourceBoundedRequestV1"
        )
    require_new_output(output_dir)
    if (
        type(token) is not str
        or len(token) != 56
        or token != token.strip()
        or any(character.isspace() for character in token)
    ):
        raise AcquisitionError("TUSHARE_PROXY_TOKEN must be exact 56-character text")
    if endpoint not in _ALLOWED_ENDPOINTS:
        raise AcquisitionError("proxy endpoint is not approved")
    if (
        type(acquired_at_epoch_nanoseconds) is not int
        or acquired_at_epoch_nanoseconds < 0
    ):
        raise AcquisitionError("acquired_at_epoch_nanoseconds must be nonnegative")

    body = _request_body(
        "daily_basic",
        {
            "ts_code": request.ts_code,
            "start_date": request.start_date,
            "end_date": request.end_date,
        },
        _FIELDS,
    )
    source_bytes, attempts = _post_with_retries(
        "daily_basic",
        endpoint=endpoint,
        body=body,
        headers=_headers(token),
        post=post,
        sleep=sleep,
    )
    rows = _authority_rows(
        source_bytes,
        api_name="daily_basic",
        expected_fields=_FIELDS,
        forbidden_text=token,
    )
    _validate_rows(rows)

    snapshot = freeze_source_snapshot(
        members=(
            RawSourceMember(
                _MEMBER_KEY,
                source_bytes,
                "0644",
                acquired_at_epoch_nanoseconds,
                None,
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro",
            source_key=(
                "tushare.pro.via.xiaodefa.approved-proxy.daily_basic."
                "000651.sz.20190506.20240506"
            ),
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    if snapshot is None:
        raise AcquisitionError("G12A valuation snapshot freeze failed")

    receipt: dict[str, object] = {
        "type": "tushare_gree_valuation_source_bounded_acquisition_receipt_v1",
        "schema_version": 1,
        "request": request.to_canonical_dict(),
        "provider_key": "tushare.pro",
        "transport_proxy_key": _PROXY_KEY,
        "transport_endpoint": endpoint,
        "provider_request": {
            "api_name": "daily_basic",
            "params": body["params"],
            "fields": body["fields"],
            "member_key": _MEMBER_KEY,
            "auth_mode": "x-api-key",
            "attempts": attempts,
            "response_byte_count": len(source_bytes),
            "response_sha256": sha256(source_bytes),
            "returned_row_count": len(rows),
            "observed_envelope": {"has_more": False, "count": 0},
            "provider_revision_id": None,
            "declared_sha256": None,
        },
        "acquired_at_epoch_nanoseconds": acquired_at_epoch_nanoseconds,
        "snapshot": snapshot.to_canonical_dict(),
        "limitations": list(_LIMITATIONS),
        "source_bounded": True,
        "provider_revision_id": None,
        "revision_closure_complete": False,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    published = {
        _MEMBER_KEY: source_bytes,
        "source-snapshot.json": json_bytes(snapshot.to_canonical_dict()),
        "acquisition-receipt.json": json_bytes(receipt),
    }
    if any(token.encode() in value for value in published.values()):
        raise AcquisitionError("proxy response unexpectedly contains credential material")
    publish_directory(output_dir, published)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture source-bounded 000651.SZ valuation inputs"
    )
    parser.add_argument("--endpoint", choices=_ALLOWED_ENDPOINTS, default=_ALLOWED_ENDPOINTS[0])
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    token = os.environ.get("TUSHARE_PROXY_TOKEN", "")
    if not token:
        raise SystemExit("TUSHARE_PROXY_TOKEN must be provided through the environment")
    try:
        receipt = acquire_tushare_gree_valuation_source_bounded_v1(
            TushareGreeValuationSourceBoundedRequestV1(),
            token=token,
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
