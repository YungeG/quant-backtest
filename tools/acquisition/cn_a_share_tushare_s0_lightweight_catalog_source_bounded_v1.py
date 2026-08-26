from __future__ import annotations

import argparse
import json
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

from . import _common
from ._common import AcquisitionError, json_bytes, require_new_output, sha256
from .cn_a_share_tushare_authority import _authority_rows, _is_real_historical_date
from .cn_a_share_tushare_listing_source_bounded_v2 import (
    ProxyPost,
    _ALLOWED_ENDPOINTS,
    _MINIMUM_DELAY_SECONDS,
    _PROXY_KEY,
    _headers,
    _post_with_retries,
    _request_body,
    _stdlib_post,
)


_CAPTURE_KEY = "20260826-s0-candidate-01"
_STATUSES = ("L", "D", "P")
_FIELDS = (
    "ts_code",
    "symbol",
    "name",
    "area",
    "industry",
    "fullname",
    "enname",
    "cnspell",
    "market",
    "exchange",
    "curr_type",
    "list_status",
    "list_date",
    "delist_date",
    "is_hs",
    "act_name",
    "act_ent_type",
)
_EXPECTED_ROWS = {"L": 5550, "D": 339, "P": 0}
_MEMBER_KEYS = {
    "L": "response/tushare/stock_basic/listed-v1.json",
    "D": "response/tushare/stock_basic/delisted-v1.json",
    "P": "response/tushare/stock_basic/suspended-listing-v1.json",
}
_LIMITATIONS = (
    "complete historical inventory is not established",
    "provider event or as-of identity is not established",
    "code-change continuity is not established",
    "board, industry, and trade-status history are not established",
    "provider revision and terminal closure are not established",
    "survivorship safety is not established",
    "S0 authority, S1 eligibility, and later-stage qualification are not granted",
)


@dataclass(frozen=True, slots=True)
class TushareS0LightweightCatalogSourceBoundedRequestV1:
    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "tushare_s0_lightweight_catalog_source_bounded_request_v1",
            "schema_version": 1,
            "capture_key": _CAPTURE_KEY,
            "list_statuses": list(_STATUSES),
            "fields": list(_FIELDS),
        }


def _timestamp(time_ns: Callable[[], int]) -> int:
    try:
        value = time_ns()
    except Exception:  # noqa: BLE001 -- redact callback details.
        raise AcquisitionError("response timestamp acquisition failed") from None
    if type(value) is not int or value < 0:
        raise AcquisitionError("response timestamp must be nonnegative integer")
    return value


def _validate_rows(rows: list[list[object]], list_status: str) -> None:
    seen: set[str] = set()
    for row in rows:
        if row[11] != list_status:
            raise AcquisitionError("provider stock_basic row has wrong list_status")
        for index in (0, 1, 2, 9, 10, 12):
            if type(row[index]) is not str or not row[index]:
                raise AcquisitionError("provider stock_basic row has empty identity field")
        if not _is_real_historical_date(row[12]):
            raise AcquisitionError("provider stock_basic row has invalid list_date")
        if row[13] is not None and (
            not _is_real_historical_date(row[13]) or row[13] < row[12]
        ):
            raise AcquisitionError("provider stock_basic row has invalid delist_date")
        if any(value is not None and type(value) is not str for value in row):
            raise AcquisitionError("provider stock_basic row has non-text field")
        if row[0] in seen:
            raise AcquisitionError("provider stock_basic response has duplicate ts_code")
        seen.add(row[0])


def acquire_tushare_s0_lightweight_catalog_source_bounded_v1(
    request: TushareS0LightweightCatalogSourceBoundedRequestV1,
    *,
    token: str,
    endpoint: str,
    output_dir: str | Path,
    post: ProxyPost,
    sleep: Callable[[float], object] = time.sleep,
    time_ns: Callable[[], int] = time.time_ns,
) -> dict[str, object]:
    if type(request) is not TushareS0LightweightCatalogSourceBoundedRequestV1:
        raise AcquisitionError(
            "request must be exact TushareS0LightweightCatalogSourceBoundedRequestV1"
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
    if not callable(post) or not callable(sleep) or not callable(time_ns):
        raise AcquisitionError("transport, sleep, and time callbacks must be callable")

    request_headers = _headers(token)
    captured: dict[
        str,
        tuple[dict[str, object], bytes, int, int, list[list[object]]],
    ] = {}
    for position, list_status in enumerate(_STATUSES):
        if position:
            try:
                sleep(_MINIMUM_DELAY_SECONDS)
            except Exception:  # noqa: BLE001 -- redact callback details.
                raise AcquisitionError("inter-request delay failed") from None
        body = _request_body("stock_basic", {"list_status": list_status}, _FIELDS)
        try:
            source_bytes, attempts = _post_with_retries(
                "stock_basic",
                endpoint=endpoint,
                body=body,
                headers=request_headers,
                post=post,
                sleep=sleep,
            )
        except Exception:  # noqa: BLE001 -- redact callback details.
            raise AcquisitionError("provider stock_basic transport failed") from None
        response_received_at = _timestamp(time_ns)
        rows = _authority_rows(
            source_bytes,
            api_name="stock_basic",
            expected_fields=_FIELDS,
            forbidden_text=token,
        )
        if len(rows) != _EXPECTED_ROWS[list_status]:
            raise AcquisitionError("provider stock_basic response cardinality mismatch")
        _validate_rows(rows, list_status)
        captured[list_status] = (
            body,
            source_bytes,
            attempts,
            response_received_at,
            rows,
        )

    seen: set[str] = set()
    for list_status in _STATUSES:
        codes = {row[0] for row in captured[list_status][4]}
        if seen.intersection(codes):
            raise AcquisitionError("provider stock_basic statuses have conflicting ts_code")
        seen.update(codes)

    snapshot = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                _MEMBER_KEYS[list_status],
                captured[list_status][1],
                "0644",
                captured[list_status][3],
                None,
            )
            for list_status in _STATUSES
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro",
            source_key=(
                "tushare.pro.via.xiaodefa.approved-proxy.stock_basic."
                "s0-lightweight.20260826"
            ),
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    if snapshot is None:
        raise AcquisitionError("G12A S0 lightweight catalog snapshot freeze failed")

    provider_requests = []
    for list_status in _STATUSES:
        body, source_bytes, attempts, received_at, rows = captured[list_status]
        provider_requests.append(
            {
                "api_name": "stock_basic",
                "params": body["params"],
                "fields": body["fields"],
                "member_key": _MEMBER_KEYS[list_status],
                "auth_mode": "x-api-key",
                "attempts": attempts,
                "response_received_at_epoch_nanoseconds": received_at,
                "response_byte_count": len(source_bytes),
                "response_sha256": sha256(source_bytes),
                "returned_row_count": len(rows),
                "observed_envelope": {"has_more": False, "count": 0},
                "provider_revision_id": None,
                "declared_sha256": None,
            }
        )
    receipt: dict[str, object] = {
        "type": "tushare_s0_lightweight_catalog_source_bounded_acquisition_receipt_v1",
        "schema_version": 1,
        "request": request.to_canonical_dict(),
        "provider_key": "tushare.pro",
        "transport_proxy_key": _PROXY_KEY,
        "transport_endpoint": endpoint,
        "provider_requests": provider_requests,
        "acquired_at_epoch_nanoseconds": max(
            captured[list_status][3] for list_status in _STATUSES
        ),
        "snapshot": snapshot.to_canonical_dict(),
        "limitations": list(_LIMITATIONS),
        "source_bounded": True,
        "provider_revision_id": None,
        "historical_as_of_qualified": False,
        "provider_completeness_qualified": False,
        "revision_closure_complete": False,
        "survivorship_bias_safe": False,
        "industry_history_qualified": False,
        "trade_status_history_qualified": False,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
        "absence_authority": False,
    }
    published = {
        _MEMBER_KEYS[list_status]: captured[list_status][1]
        for list_status in _STATUSES
    }
    published["source-snapshot.json"] = json_bytes(snapshot.to_canonical_dict())
    published["acquisition-receipt.json"] = json_bytes(receipt)
    if any(token.encode() in value for value in published.values()):
        raise AcquisitionError("proxy response unexpectedly contains credential material")
    _common.publish_directory(output_dir, published)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture source-bounded Tushare broad lightweight catalog responses"
    )
    parser.add_argument(
        "--endpoint", choices=_ALLOWED_ENDPOINTS, default=_ALLOWED_ENDPOINTS[0]
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    token = os.environ.get("TUSHARE_PROXY_TOKEN", "")
    if not token:
        raise SystemExit("TUSHARE_PROXY_TOKEN must be provided through the environment")
    try:
        receipt = acquire_tushare_s0_lightweight_catalog_source_bounded_v1(
            TushareS0LightweightCatalogSourceBoundedRequestV1(),
            token=token,
            endpoint=args.endpoint,
            output_dir=args.output_dir,
            post=_stdlib_post,
        )
    except (AcquisitionError, ValueError) as error:
        raise SystemExit(f"acquisition failed: {error}") from None
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
