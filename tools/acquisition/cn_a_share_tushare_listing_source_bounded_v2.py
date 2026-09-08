from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
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
from .cn_a_share_tushare_authority import (
    _authority_rows,
    _is_real_historical_date,
)


_TS_CODE = re.compile(r"[0-9]{6}\.(?:SZ|SH|BJ)\Z")
_DATE = re.compile(r"20[0-9]{6}\Z")
_ALLOWED_ENDPOINTS = (
    "https://fast.xiaodefa.cn",
    "https://tt.xiaodefa.cn",
)
_PROXY_KEY = "xiaodefa.approved-tushare-proxy.v1"
_FIXED_TS_CODE = "000001.SZ"
_FIXED_TRADE_DATE = "20240102"
_MINIMUM_DELAY_SECONDS = 0.5
_MAX_ATTEMPTS = 3
_STOCK_FIELDS = (
    "ts_code",
    "symbol",
    "name",
    "market",
    "exchange",
    "list_status",
    "list_date",
    "delist_date",
)
_BAK_FIELDS = ("trade_date", "ts_code", "name", "list_date")
_NAME_FIELDS = (
    "ts_code",
    "name",
    "start_date",
    "end_date",
    "ann_date",
    "change_reason",
)

ProxyPost = Callable[
    [str, dict[str, object], dict[str, str]],
    tuple[int, bytes],
]


@dataclass(frozen=True, slots=True)
class TushareListingSourceBoundedRequestV2:
    ts_code: str
    trade_date: str

    def __post_init__(self) -> None:
        if _TS_CODE.fullmatch(self.ts_code) is None:
            raise ValueError("ts_code must be a canonical SZ/SH/BJ Tushare code")
        if _DATE.fullmatch(self.trade_date) is None:
            raise ValueError("trade_date must be YYYYMMDD")
        try:
            datetime.strptime(self.trade_date, "%Y%m%d")
        except ValueError as error:
            raise ValueError("trade_date must be a real calendar date") from error
        if self.ts_code != _FIXED_TS_CODE or self.trade_date != _FIXED_TRADE_DATE:
            raise ValueError("request must match fixed 000001.SZ / 20240102 scope")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "tushare_listing_source_bounded_request_v2",
            "schema_version": 2,
            "ts_code": self.ts_code,
            "trade_date": self.trade_date,
        }


def _request_body(
    api_name: str,
    params: dict[str, object],
    fields: tuple[str, ...],
) -> dict[str, object]:
    return {
        "api_name": api_name,
        "params": params,
        "fields": ",".join(fields),
    }


def _headers(token: str) -> dict[str, str]:
    return {
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json",
        "x-api-key": token,
    }


def _decode_transport_body(source: bytes, content_encoding: str | None) -> bytes:
    if content_encoding in (None, "", "identity"):
        return source
    if content_encoding.lower() == "gzip":
        try:
            return gzip.decompress(source)
        except (OSError, EOFError) as error:
            raise AcquisitionError("proxy returned invalid gzip response") from error
    raise AcquisitionError("proxy returned unsupported content encoding")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def _stdlib_post(
    url: str,
    body: dict[str, object],
    headers: dict[str, str],
) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url,
        data=json.dumps(
            body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode(),
        headers=headers,
        method="POST",
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=30) as response:
            source = response.read()
            return int(response.status), _decode_transport_body(
                source,
                response.headers.get("Content-Encoding"),
            )
    except urllib.error.HTTPError as error:
        status = int(error.code)
        if 300 <= status <= 399:
            return status, b""
        source = error.read()
        content_encoding = (
            error.headers.get("Content-Encoding") if error.headers is not None else None
        )
        return status, _decode_transport_body(source, content_encoding)


def _post_with_retries(
    api_name: str,
    *,
    endpoint: str,
    body: dict[str, object],
    headers: dict[str, str],
    post: ProxyPost,
    sleep: Callable[[float], object],
) -> tuple[bytes, int]:
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = post(endpoint, body, headers)
        except (AcquisitionError, OSError, RuntimeError):
            response = None
        if response is not None:
            if (
                type(response) is not tuple
                or len(response) != 2
                or type(response[0]) is not int
                or type(response[1]) is not bytes
            ):
                raise AcquisitionError("post must return exact (status, bytes)")
            status, response_bytes = response
            if status == 200:
                return response_bytes, attempt
            if status != 429 and not 500 <= status <= 599:
                raise AcquisitionError(
                    f"proxy rejected {api_name} request with HTTP status {status}"
                )
        if attempt < _MAX_ATTEMPTS:
            sleep(max(_MINIMUM_DELAY_SECONDS, float(2 ** (attempt - 1))))
    raise AcquisitionError(f"proxy {api_name} request exhausted retries")


def _covering_name_rows(
    rows: list[list[object]],
    *,
    ts_code: str,
    trade_date: str,
) -> list[list[object]]:
    if any(
        row[0] != ts_code
        or type(row[1]) is not str
        or not row[1]
        or not _is_real_historical_date(row[2])
        or (
            row[3] is not None
            and (
                not _is_real_historical_date(row[3])
                or row[3] < row[2]
            )
        )
        or not _is_real_historical_date(row[4])
        or type(row[5]) is not str
        for row in rows
    ) or len({tuple(row) for row in rows}) != len(rows):
        raise AcquisitionError("proxy namechange response has invalid intervals")
    return [
        row
        for row in rows
        if row[2] <= trade_date and (row[3] is None or trade_date <= row[3])
    ]


def acquire_tushare_listing_source_bounded_v2(
    request: TushareListingSourceBoundedRequestV2,
    *,
    token: str,
    endpoint: str,
    output_dir: str | Path,
    acquired_at_epoch_nanoseconds: int,
    post: ProxyPost,
    sleep: Callable[[float], object] = real_sleep,
) -> dict[str, object]:
    if type(request) is not TushareListingSourceBoundedRequestV2:
        raise AcquisitionError(
            "request must be exact TushareListingSourceBoundedRequestV2"
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

    specifications = (
        (
            "stock_basic",
            {"ts_code": request.ts_code, "list_status": "L"},
            _STOCK_FIELDS,
            "response/stock-basic.json",
        ),
        (
            "bak_basic",
            {"trade_date": request.trade_date, "ts_code": request.ts_code},
            _BAK_FIELDS,
            "response/bak-basic.json",
        ),
        (
            "namechange",
            {"ts_code": request.ts_code},
            _NAME_FIELDS,
            "response/namechange.json",
        ),
    )
    request_headers = _headers(token)
    captured: dict[
        str,
        tuple[dict[str, object], bytes, int, list[list[object]], str],
    ] = {}
    for position, (api_name, params, fields, member_key) in enumerate(specifications):
        body = _request_body(api_name, params, fields)
        response_bytes, attempts = _post_with_retries(
            api_name,
            endpoint=endpoint,
            body=body,
            headers=request_headers,
            post=post,
            sleep=sleep,
        )
        rows = _authority_rows(
            response_bytes,
            api_name=api_name,
            expected_fields=fields,
            forbidden_text=token,
        )
        captured[api_name] = (body, response_bytes, attempts, rows, member_key)
        if position + 1 < len(specifications):
            sleep(_MINIMUM_DELAY_SECONDS)

    stock_rows = captured["stock_basic"][3]
    if len(stock_rows) != 1 or stock_rows[0][0] != request.ts_code:
        raise AcquisitionError("proxy stock_basic response does not exact-cover request")
    stock = stock_rows[0]
    if (
        stock[1] != "000001"
        or stock[4] != "SZSE"
        or stock[5] != "L"
        or not _is_real_historical_date(stock[6])
        or stock[6] > request.trade_date
        or (
            stock[7] is not None
            and (
                not _is_real_historical_date(stock[7])
                or stock[7] < request.trade_date
            )
        )
    ):
        raise AcquisitionError("proxy stock_basic row is outside fixed scope")

    historical_rows = captured["bak_basic"][3]
    if (
        len(historical_rows) != 1
        or historical_rows[0][0] != request.trade_date
        or historical_rows[0][1] != request.ts_code
        or type(historical_rows[0][2]) is not str
        or not historical_rows[0][2]
        or not _is_real_historical_date(historical_rows[0][3])
    ):
        raise AcquisitionError("proxy bak_basic response does not exact-cover request")
    historical = historical_rows[0]
    covering_names = _covering_name_rows(
        captured["namechange"][3],
        ts_code=request.ts_code,
        trade_date=request.trade_date,
    )
    if len(covering_names) != 1:
        raise AcquisitionError("proxy namechange response has no unique target interval")
    if (
        stock[2] != historical[2]
        or historical[2] != covering_names[0][1]
        or stock[6] != historical[3]
    ):
        raise AcquisitionError("proxy listing identity sources conflict")

    files = {
        member_key: captured[api_name][1]
        for api_name, _, _, member_key in specifications
    }
    snapshot = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                member_key,
                source_bytes,
                "0644",
                acquired_at_epoch_nanoseconds,
                None,
            )
            for member_key, source_bytes in sorted(files.items())
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro",
            source_key=(
                "tushare.pro.via.xiaodefa.approved-proxy.listing_presence."
                f"{request.ts_code.lower()}.{request.trade_date}"
            ),
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    if snapshot is None:
        raise AcquisitionError("G12A snapshot freeze failed")

    provider_requests = []
    for api_name, _, _, _ in specifications:
        body, response_bytes, attempts, rows, member_key = captured[api_name]
        provider_requests.append(
            {
                "api_name": api_name,
                "params": body["params"],
                "fields": body["fields"],
                "member_key": member_key,
                "auth_mode": "x-api-key",
                "attempts": attempts,
                "response_byte_count": len(response_bytes),
                "response_sha256": sha256(response_bytes),
                "returned_row_count": len(rows),
                "provider_revision_id": None,
                "declared_sha256": None,
            }
        )
    receipt: dict[str, object] = {
        "type": "tushare_listing_source_bounded_acquisition_receipt_v2",
        "schema_version": 2,
        "request": request.to_canonical_dict(),
        "provider_key": "tushare.pro",
        "transport_proxy_key": _PROXY_KEY,
        "transport_endpoint": endpoint,
        "provider_requests": provider_requests,
        "acquired_at_epoch_nanoseconds": acquired_at_epoch_nanoseconds,
        "snapshot": snapshot.to_canonical_dict(),
        "current_listing_row_count": len(stock_rows),
        "historical_list_row_count": len(historical_rows),
        "namechange_row_count": len(captured["namechange"][3]),
        "target_name_interval_count": len(covering_names),
        "provider_revision_id": None,
        "revision_closure_complete": False,
        "provider_completeness_qualified": False,
        "absence_authority": False,
        "historical_listing_lifecycle_qualified": False,
        "corporate_action_lifecycle_qualified": False,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    published = {
        member_key.removeprefix("response/"): source_bytes
        for member_key, source_bytes in files.items()
    }
    published["acquisition-receipt.json"] = json_bytes(receipt)
    if any(token.encode() in value for value in published.values()):
        raise AcquisitionError("proxy response unexpectedly contains credential material")
    publish_directory(output_dir, published)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Acquire bounded Tushare listing evidence through approved proxy"
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
        receipt = acquire_tushare_listing_source_bounded_v2(
            TushareListingSourceBoundedRequestV2(
                _FIXED_TS_CODE,
                _FIXED_TRADE_DATE,
            ),
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
