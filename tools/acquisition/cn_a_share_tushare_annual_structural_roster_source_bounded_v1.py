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
    _ALLOWED_ENDPOINTS,
    _MINIMUM_DELAY_SECONDS,
    _PROXY_KEY,
    ProxyPost,
    _headers,
    _post_with_retries,
    _request_body,
    _stdlib_post,
)
from .cn_a_share_tushare_trade_calendar import _validate_trade_calendar_range_v2

_CAPTURE_KEY = "20260826-annual-structural-candidate-01"
_CALENDAR_PARAMS = {
    "exchange": "SSE",
    "start_date": "20160430",
    "end_date": "20250510",
}
_CALENDAR_FIELDS = ("exchange", "cal_date", "is_open", "pretrade_date")
_ROSTER_DATES = (
    "20160503",
    "20170502",
    "20180502",
    "20190506",
    "20200506",
    "20210506",
    "20220505",
    "20230504",
    "20240506",
    "20250506",
)
_ROSTER_FIELDS = ("trade_date", "ts_code", "name", "industry", "list_date")
_EXPECTED_ROWS = {
    "20160503": 0,
    "20170502": 3232,
    "20180502": 3518,
    "20190506": 3622,
    "20200506": 3850,
    "20210506": 4326,
    "20220505": 4719,
    "20230504": 4994,
    "20240506": 5364,
    "20250506": 5415,
}
_CALENDAR_MEMBER_KEY = "response/tushare/trade_cal/sse-20160430-20250510-v1.json"
_ROSTER_MEMBER_KEYS = {
    trade_date: f"response/tushare/bak_basic/{trade_date}-v1.json"
    for trade_date in _ROSTER_DATES
}
_LIMITATIONS = (
    "2010-2015 annual primary-screen roster observations are unavailable in this capture",
    "20160503 zero rows are a bounded provider gap, not an empty Universe",
    "Tushare trade_cal is source-bounded and not accepted Calendar authority",
    "bak_basic row presence is not exchange listing or tradability authority",
    "bak_basic list_date=0 is retained as provider unknown, not a listing date",
    "board and official CSRC industry history are not established",
    "provider revision, absence, completeness, and terminal closure are not established",
    "formal S1, Fold, Strategy, Validation, and deployment authority are not granted",
)


@dataclass(frozen=True, slots=True)
class TushareAnnualStructuralRosterSourceBoundedRequestV1:
    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "tushare_annual_structural_roster_source_bounded_request_v1",
            "schema_version": 1,
            "capture_key": _CAPTURE_KEY,
            "calendar_request": dict(_CALENDAR_PARAMS),
            "calendar_fields": list(_CALENDAR_FIELDS),
            "roster_dates": list(_ROSTER_DATES),
            "roster_fields": list(_ROSTER_FIELDS),
        }


def _timestamp(time_ns: Callable[[], int]) -> int:
    try:
        value = time_ns()
    except Exception:  # noqa: BLE001 -- redact callback details.
        raise AcquisitionError("response timestamp acquisition failed") from None
    if type(value) is not int or value < 0:
        raise AcquisitionError("response timestamp must be nonnegative integer")
    return value


def _validate_trade_calendar_rows(rows: list[list[object]]) -> tuple[str, ...]:
    _validate_trade_calendar_range_v2(rows, **_CALENDAR_PARAMS)
    dates: list[str] = []
    for year in range(2016, 2026):
        opens = [
            row[1]
            for row in rows
            if row[2] == 1 and f"{year}0430" < row[1] <= f"{year}0510"
        ]
        if not opens:
            raise AcquisitionError("provider trade_cal response has no annual screen date")
        dates.append(min(opens))
    result = tuple(dates)
    if result != _ROSTER_DATES:
        raise AcquisitionError("provider trade_cal annual screen dates drifted")
    return result


def _validate_roster_rows(rows: list[list[object]], trade_date: str) -> None:
    seen: set[str] = set()
    for row in rows:
        if row[0] != trade_date:
            raise AcquisitionError("provider bak_basic row has wrong trade_date")
        if any(type(row[index]) is not str or not row[index] for index in (1, 2, 4)):
            raise AcquisitionError("provider bak_basic row has empty identity field")
        if row[3] is not None and type(row[3]) is not str:
            raise AcquisitionError("provider bak_basic row has invalid industry")
        if row[4] != "0" and (
            not _is_real_historical_date(row[4]) or row[4] > trade_date
        ):
            raise AcquisitionError("provider bak_basic row has invalid list_date")
        if row[1] in seen:
            raise AcquisitionError("provider bak_basic response has duplicate ts_code")
        seen.add(row[1])


def acquire_tushare_annual_structural_roster_source_bounded_v1(
    request: TushareAnnualStructuralRosterSourceBoundedRequestV1,
    *,
    token: str,
    endpoint: str,
    output_dir: str | Path,
    post: ProxyPost,
    sleep: Callable[[float], object] = time.sleep,
    time_ns: Callable[[], int] = time.time_ns,
) -> dict[str, object]:
    if type(request) is not TushareAnnualStructuralRosterSourceBoundedRequestV1:
        raise AcquisitionError(
            "request must be exact TushareAnnualStructuralRosterSourceBoundedRequestV1"
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
    captured: list[
        tuple[str, dict[str, object], bytes, int, int, list[list[object]]]
    ] = []
    calendar_body = _request_body("trade_cal", dict(_CALENDAR_PARAMS), _CALENDAR_FIELDS)
    try:
        calendar_bytes, calendar_attempts = _post_with_retries(
            "trade_cal",
            endpoint=endpoint,
            body=calendar_body,
            headers=request_headers,
            post=post,
            sleep=sleep,
        )
    except Exception:  # noqa: BLE001 -- redact transport and retry callback details.
        raise AcquisitionError("provider trade_cal transport failed") from None
    calendar_received_at = _timestamp(time_ns)
    calendar_rows = _authority_rows(
        calendar_bytes,
        api_name="trade_cal",
        expected_fields=_CALENDAR_FIELDS,
        forbidden_text=token,
    )
    if len(calendar_rows) != 3298:
        raise AcquisitionError("provider trade_cal response cardinality mismatch")
    roster_dates = _validate_trade_calendar_rows(calendar_rows)
    captured.append(
        (
            _CALENDAR_MEMBER_KEY,
            calendar_body,
            calendar_bytes,
            calendar_attempts,
            calendar_received_at,
            calendar_rows,
        )
    )

    for trade_date in roster_dates:
        try:
            sleep(_MINIMUM_DELAY_SECONDS)
        except Exception:  # noqa: BLE001 -- redact callback details.
            raise AcquisitionError("inter-request delay failed") from None
        body = _request_body("bak_basic", {"trade_date": trade_date}, _ROSTER_FIELDS)
        try:
            source_bytes, attempts = _post_with_retries(
                "bak_basic",
                endpoint=endpoint,
                body=body,
                headers=request_headers,
                post=post,
                sleep=sleep,
            )
        except Exception:  # noqa: BLE001 -- redact transport and retry callback details.
            raise AcquisitionError("provider bak_basic transport failed") from None
        received_at = _timestamp(time_ns)
        rows = _authority_rows(
            source_bytes,
            api_name="bak_basic",
            expected_fields=_ROSTER_FIELDS,
            forbidden_text=token,
        )
        if len(rows) != _EXPECTED_ROWS[trade_date]:
            raise AcquisitionError("provider bak_basic response cardinality mismatch")
        _validate_roster_rows(rows, trade_date)
        captured.append(
            (
                _ROSTER_MEMBER_KEYS[trade_date],
                body,
                source_bytes,
                attempts,
                received_at,
                rows,
            )
        )

    snapshot = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(member_key, source_bytes, "0644", received_at, None)
            for member_key, _body, source_bytes, _attempts, received_at, _rows in captured
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro",
            source_key=(
                "tushare.pro.via.xiaodefa.approved-proxy."
                "annual-structural-roster.2016-2025.20260826"
            ),
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    if snapshot is None:
        raise AcquisitionError("annual structural roster snapshot freeze failed")

    provider_requests = [
        {
            "api_name": body["api_name"],
            "params": body["params"],
            "fields": body["fields"],
            "member_key": member_key,
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
        for member_key, body, source_bytes, attempts, received_at, rows in captured
    ]
    receipt: dict[str, object] = {
        "type": "tushare_annual_structural_roster_source_bounded_acquisition_receipt_v1",
        "schema_version": 1,
        "request": request.to_canonical_dict(),
        "provider_key": "tushare.pro",
        "transport_proxy_key": _PROXY_KEY,
        "transport_endpoint": endpoint,
        "provider_requests": provider_requests,
        "acquired_at_epoch_nanoseconds": max(item[4] for item in captured),
        "snapshot": snapshot.to_canonical_dict(),
        "limitations": list(_LIMITATIONS),
        "source_bounded": True,
        "calendar_authority_qualified": False,
        "historical_roster_qualified": False,
        "listing_membership_qualified": False,
        "board_history_qualified": False,
        "industry_history_qualified": False,
        "provider_completeness_qualified": False,
        "revision_closure_complete": False,
        "survivorship_bias_safe": False,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
        "absence_authority": False,
        "provider_revision_id": None,
    }
    published = {item[0]: item[2] for item in captured}
    published["source-snapshot.json"] = json_bytes(snapshot.to_canonical_dict())
    published["acquisition-receipt.json"] = json_bytes(receipt)
    if any(token.encode() in value for value in published.values()):
        raise AcquisitionError("proxy response unexpectedly contains credential material")
    _common.publish_directory(output_dir, published)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture source-bounded Tushare annual structural roster responses"
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
        receipt = acquire_tushare_annual_structural_roster_source_bounded_v1(
            TushareAnnualStructuralRosterSourceBoundedRequestV1(),
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
