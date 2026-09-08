from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from time import sleep as real_sleep

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)

from ._common import (
    AcquisitionError,
    json_bytes,
    publish_directory,
    require_new_output,
    sha256,
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

_DATES = (
    "20260706",
    "20260707",
    "20260708",
    "20260709",
    "20260710",
    "20260713",
    "20260714",
    "20260715",
    "20260716",
    "20260717",
    "20260720",
    "20260721",
    "20260722",
    "20260723",
    "20260724",
    "20260727",
    "20260728",
    "20260729",
    "20260730",
)
_FIELDS = ("trade_date", "ts_code", "name", "list_date")
_TS_CODE = "000001.SZ"
_NAME = "平安银行"
_LIST_DATE = "19910403"
_SOURCE_KEY = (
    "tushare.pro.via.xiaodefa.approved-proxy."
    "bak_basic.000001.sz.20260706.20260730"
)
_MINIMUM_DELAY_SECONDS = 0.5

ProxyPost = Callable[
    [str, dict[str, object], dict[str, str]],
    tuple[int, bytes],
]


def acquire_tushare_july_listing_presence_v1(
    *,
    token: str,
    endpoint: str,
    output_dir: str | Path,
    acquired_at_epoch_nanoseconds: int,
    post: ProxyPost,
    sleep: Callable[[float], object] = real_sleep,
) -> dict[str, object]:
    require_new_output(output_dir)
    if endpoint not in _ALLOWED_ENDPOINTS:
        raise AcquisitionError("proxy endpoint is not approved")
    if (
        type(token) is not str
        or len(token) != 56
        or token != token.strip()
        or any(character.isspace() for character in token)
    ):
        raise AcquisitionError("TUSHARE_PROXY_TOKEN must be exact 56-character text")
    if (
        type(acquired_at_epoch_nanoseconds) is not int
        or acquired_at_epoch_nanoseconds < 0
    ):
        raise AcquisitionError("acquired_at_epoch_nanoseconds must be nonnegative int")

    headers = _headers(token)
    responses: dict[str, bytes] = {}
    requests: list[dict[str, object]] = []
    for index, trade_date in enumerate(_DATES):
        if index:
            sleep(_MINIMUM_DELAY_SECONDS)
        params = {"trade_date": trade_date, "ts_code": _TS_CODE}
        body = _request_body("bak_basic", params, _FIELDS)
        source, attempts = _post_with_retries(
            "bak_basic",
            endpoint=endpoint,
            body=body,
            headers=headers,
            post=post,
            sleep=sleep,
        )
        rows = _authority_rows(
            source,
            api_name="bak_basic",
            expected_fields=_FIELDS,
            forbidden_text=token,
        )
        if rows != [[trade_date, _TS_CODE, _NAME, _LIST_DATE]]:
            raise AcquisitionError(
                f"proxy bak_basic response does not exact-cover {trade_date}"
            )
        member_key = f"response/bak-basic/{trade_date}.json"
        responses[member_key] = source
        requests.append(
            {
                "api_name": "bak_basic",
                "params": params,
                "fields": ",".join(_FIELDS),
                "member_key": member_key,
                "attempts": attempts,
                "auth_mode": "x-api-key",
                "response_byte_count": len(source),
                "response_sha256": sha256(source),
                "returned_row_count": 1,
                "declared_sha256": None,
                "provider_revision_id": None,
            }
        )

    snapshot_outcome = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                member_key,
                source,
                "0644",
                acquired_at_epoch_nanoseconds,
                None,
            )
            for member_key, source in sorted(responses.items())
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro",
            source_key=_SOURCE_KEY,
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    )
    if snapshot_outcome.snapshot is None:
        raise AcquisitionError("failed to freeze G12A SourceSnapshot")
    receipt: dict[str, object] = {
        "type": "tushare_july_listing_presence_acquisition_receipt_v1",
        "schema_version": 1,
        "provider_key": "tushare.pro",
        "transport_proxy_key": _PROXY_KEY,
        "transport_endpoint": endpoint,
        "request": {
            "type": "tushare_july_listing_presence_request_v1",
            "schema_version": 1,
            "ts_code": _TS_CODE,
            "trade_dates": _DATES,
        },
        "provider_requests": requests,
        "acquired_at_epoch_nanoseconds": acquired_at_epoch_nanoseconds,
        "returned_row_count": len(_DATES),
        "snapshot": snapshot_outcome.snapshot.to_canonical_dict(),
        "provider_revision_id": None,
        "revision_closure_complete": False,
        "provider_completeness_qualified": False,
        "absence_authority": False,
        "historical_listing_lifecycle_qualified": False,
        "corporate_action_lifecycle_qualified": False,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    publish_directory(
        output_dir,
        {
            **responses,
            "acquisition-receipt.json": json_bytes(receipt),
        },
    )
    return json.loads(json_bytes(receipt))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Acquire exact July-2026 Tushare listing-presence rows"
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
        receipt = acquire_tushare_july_listing_presence_v1(
            token=token,
            endpoint=args.endpoint,
            output_dir=args.output_dir,
            acquired_at_epoch_nanoseconds=time.time_ns(),
            post=_stdlib_post,
        )
    except AcquisitionError as error:
        raise SystemExit(f"acquisition failed: {error}") from None
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
