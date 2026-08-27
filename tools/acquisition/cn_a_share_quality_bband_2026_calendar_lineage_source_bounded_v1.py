from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import cast

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)
from crypto_quant_domain import canonical_bytes

from ._common import AcquisitionError, sha256
from .cn_a_share_official_s2_remediation_source_bounded_v1 import (
    _NoRedirect,
    _read_bounded,
    _require_safe_output,
    _RETRYABLE_STATUSES,
    _RETRY_DELAYS,
)
from .cn_a_share_tushare_authority import _authority_rows
from .cn_a_share_tushare_listing_source_bounded_v2 import (
    _ALLOWED_ENDPOINTS,
    _PROXY_KEY,
    ProxyPost,
    _headers,
    _request_body,
    _stdlib_post,
)

HeaderPairs = tuple[tuple[str, str], ...]
Get = Callable[[str, HeaderPairs], tuple[int, object, bytes, str]]
Sleep = Callable[[float], object]
Clock = Callable[[], int]

_CAPTURE_KEY = "20260827-quality-bband-2026-calendar-lineage-source-candidate-01"
_CALENDAR_FIELDS = ("exchange", "cal_date", "is_open", "pretrade_date")
_CALENDAR_PARAMS = {
    "start_date": "20260430",
    "end_date": "20260510",
}
_CALENDAR_MEMBER_KEYS = {
    "SSE": "response/tushare/trade_cal/sse-20260430-20260510-v1.json",
    "SZSE": "response/tushare/trade_cal/szse-20260430-20260510-v1.json",
}
_EXPECTED_CALENDAR_DAYS = (
    ("20260510", 0, "20260508"),
    ("20260509", 0, "20260508"),
    ("20260508", 1, "20260507"),
    ("20260507", 1, "20260506"),
    ("20260506", 1, "20260430"),
    ("20260505", 0, "20260430"),
    ("20260504", 0, "20260430"),
    ("20260503", 0, "20260430"),
    ("20260502", 0, "20260430"),
    ("20260501", 0, "20260430"),
    ("20260430", 1, "20260429"),
)
_NEEQ_URL = "https://neeq.cs.com.cn/xsb/v1/xsb_search/&gs=400267&st=2025-07-01&ed=2025-08-10&1.json"
_NEEQ_HEADERS: HeaderPairs = (
    ("Accept", "application/json,*/*"),
    ("Referer", "https://neeq.cs.com.cn/"),
    ("User-Agent", "Mozilla/5.0"),
)
_NEEQ_MEMBER_KEY = "response/neeq/disclosure-search/400267-20250701-20250810-v1.json"
_NEEQ_OUTER_KEYS = ("code", "errorMessage", "data")
_NEEQ_INNER_KEYS = ("code", "errorMessage", "data", "currentPage", "size", "total")
_METADATA_PDF_URL = "http://dataclouds.cninfo.com.cn/sjother/neeqs/2025/20250731/d906b07f748045d4aef1718916182a99.pdf"
_PDF_URL = "https://dataclouds.cninfo.com.cn/sjother/neeqs/2025/20250731/d906b07f748045d4aef1718916182a99.pdf"
_PDF_HEADERS: HeaderPairs = (
    ("Accept", "application/pdf,*/*"),
    ("Referer", "https://neeq.cs.com.cn/"),
    ("User-Agent", "Mozilla/5.0"),
)
_PDF_MEMBER_KEY = "response/official/601028/d906b07f748045d4aef1718916182a99.pdf"
_PDF_BYTE_COUNT = 166170
_PDF_SHA256 = "sha256:c8a0b8cc80b666247455e2b345947531728d73f710ccb525c98a909f521717a6"
_SELECTED_NEEQ_FACT = (
    "400267",
    "R玉龙1",
    "2025-07-31T00:00:00.000+00:00",
    "[临时公告]R玉龙1:2025-016 公司全称变更公告",
    _METADATA_PDF_URL,
    "PDF",
)
_MAX_ATTEMPTS = 3
MAX_LOGICAL_REQUESTS = 4
MAX_METADATA_MEMBER_BYTES = 1 << 20
MAX_PDF_MEMBER_BYTES = 1 << 20
MAX_TOTAL_BYTES = 4 << 20
_FALSE_FLAGS = (
    "calendar_boundary_reviewed",
    "issuer_lineage_reviewed",
    "nonfiling_declarations_constructed",
    "formal_s1_qualified",
    "s2b_exact_cover_complete",
    "decision_grade",
    "strategy_authorized",
    "deployment_authorized",
)
_LIMITATIONS = (
    "SOURCE_BOUNDED_ONLY",
    "CALENDAR_BOUNDARY_NOT_REVIEWED",
    "ISSUER_LINEAGE_NOT_REVIEWED",
    "NONFILING_DECLARATIONS_NOT_CONSTRUCTED",
    "FORMAL_S1_NOT_QUALIFIED",
    "S2B_EXACT_COVER_FALSE",
    "DECISION_GRADE_FALSE",
    "STRATEGY_AUTHORIZED_FALSE",
    "DEPLOYMENT_AUTHORIZED_FALSE",
)


def _timestamp(clock: Clock) -> int:
    try:
        value = clock()
    except Exception:  # noqa: BLE001 -- collaborator details are not receipt data.
        raise AcquisitionError("acquisition clock failed") from None
    if type(value) is not int or value < 0:
        raise AcquisitionError("acquisition clock failed")
    return value


def _proxy_with_retries(
    endpoint: str,
    body: dict[str, object],
    headers: dict[str, str],
    post: ProxyPost,
    sleep: Sleep,
    *,
    total_remaining: int,
) -> tuple[bytes, int]:
    if (
        endpoint not in _ALLOWED_ENDPOINTS
        or body not in {
            exchange: _request_body(
                "trade_cal", {"exchange": exchange, **_CALENDAR_PARAMS}, _CALENDAR_FIELDS
            )
            for exchange in _CALENDAR_MEMBER_KEYS
        }.values()
        or set(headers) != {"Accept-Encoding", "Content-Type", "x-api-key"}
    ):
        raise AcquisitionError("proxy request is not allowed")
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = post(endpoint, body, headers)
        except Exception:  # noqa: BLE001 -- credential-bearing collaborator details are redacted.
            response = None
        if response is not None:
            if (
                type(response) is not tuple
                or len(response) != 2
                or type(response[0]) is not int
                or isinstance(response[0], bool)
                or type(response[1]) is not bytes
            ):
                raise AcquisitionError("proxy transport failed")
            status, source = response
            if len(source) > min(MAX_METADATA_MEMBER_BYTES, total_remaining):
                raise AcquisitionError("response byte ceiling exceeded")
            if status == 200:
                return source, attempt
            if status not in _RETRYABLE_STATUSES:
                raise AcquisitionError("proxy response status mismatch")
        if attempt == _MAX_ATTEMPTS:
            raise AcquisitionError("proxy transport failed")
        try:
            sleep(_RETRY_DELAYS[attempt - 1])
        except Exception:  # noqa: BLE001 -- collaborator details are not receipt data.
            raise AcquisitionError("proxy transport failed") from None
    raise AssertionError("unreachable")


def _get_with_retries(
    url: str,
    headers: HeaderPairs,
    get: Get,
    sleep: Sleep,
    *,
    member_limit: int,
    total_remaining: int,
) -> tuple[int, HeaderPairs, bytes, str, int]:
    if (url, headers, member_limit) not in {
        (_NEEQ_URL, _NEEQ_HEADERS, MAX_METADATA_MEMBER_BYTES),
        (_PDF_URL, _PDF_HEADERS, MAX_PDF_MEMBER_BYTES),
    }:
        raise AcquisitionError("GET request is not allowed")
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            raw_response = get(url, headers)
        except _NoRedirect.ResponseBoundaryError:
            raise
        except Exception:  # noqa: BLE001 -- collaborator details are not receipt data.
            response = None
        else:
            response = _NoRedirect.semantic_response(
                raw_response, member_limit, total_remaining
            )
        if response is not None:
            status, response_headers, source, final_url = response
            if final_url != url:
                raise AcquisitionError("GET final URL mismatch")
            if status not in _RETRYABLE_STATUSES:
                return status, response_headers, source, final_url, attempt
        if attempt == _MAX_ATTEMPTS:
            raise AcquisitionError("provider transport failed")
        try:
            sleep(_RETRY_DELAYS[attempt - 1])
        except Exception:  # noqa: BLE001 -- collaborator details are not receipt data.
            raise AcquisitionError("provider transport failed") from None
    raise AssertionError("unreachable")


def _validate_calendar(source: bytes, exchange: str, token: str) -> list[list[object]]:
    rows = _authority_rows(
        source,
        api_name="trade_cal",
        expected_fields=_CALENDAR_FIELDS,
        forbidden_text=token,
    )
    expected = [[exchange, *day] for day in _EXPECTED_CALENDAR_DAYS]
    if (
        any(
            type(row[0]) is not str
            or type(row[1]) is not str
            or type(row[2]) is not int
            or isinstance(row[2], bool)
            or type(row[3]) is not str
            for row in rows
        )
        or rows != expected
    ):
        raise AcquisitionError("provider trade_cal exact rows mismatch")
    return rows


def _parse_neeq(source: bytes) -> tuple[dict[str, object], int]:
    try:
        payload = json.loads(
            source,
            object_pairs_hook=_NoRedirect.json_object,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        raise AcquisitionError("NEEQ metadata response is invalid") from None
    if (
        type(payload) is not dict
        or set(payload) != set(_NEEQ_OUTER_KEYS)
        or type(payload["code"]) is not int
        or payload["code"] != 0
        or payload["errorMessage"] is not None
    ):
        raise AcquisitionError("NEEQ metadata response is invalid")
    inner = payload["data"]
    if (
        type(inner) is not dict
        or set(inner) != set(_NEEQ_INNER_KEYS)
        or type(inner["code"]) is not int
        or inner["code"] != 0
        or inner["errorMessage"] is not None
        or type(inner["currentPage"]) is not int
        or inner["currentPage"] != 1
        or type(inner["size"]) is not int
        or inner["size"] != 30
        or type(inner["total"]) is not int
        or inner["total"] != 13
        or type(inner["data"]) is not list
        or len(inner["data"]) != 13
    ):
        raise AcquisitionError("NEEQ metadata response scope mismatch")
    if any(type(record) is not dict for record in inner["data"]):
        raise AcquisitionError("NEEQ metadata record mismatch")
    records = [
        record
        for record in inner["data"]
        if record.get("f003v") == _METADATA_PDF_URL
    ]
    if len(records) != 1:
        raise AcquisitionError("selected NEEQ metadata URL mismatch")
    record = cast(dict[str, object], records[0])
    if tuple(
        record.get(key)
        for key in ("seccode", "secname", "f001d", "f002v", "f003v", "f004v")
    ) != _SELECTED_NEEQ_FACT:
        raise AcquisitionError("selected NEEQ metadata fact mismatch")
    return {
        "seccode": _SELECTED_NEEQ_FACT[0],
        "secname": _SELECTED_NEEQ_FACT[1],
        "published_at": _SELECTED_NEEQ_FACT[2],
        "title": _SELECTED_NEEQ_FACT[3],
        "metadata_pdf_url": _SELECTED_NEEQ_FACT[4],
        "retained_pdf_url": _PDF_URL,
    }, 12


def _freeze(files: dict[str, bytes], received_at: dict[str, int]):
    try:
        outcome = freeze_source_snapshot(
            members=tuple(
                RawSourceMember(key, value, "0644", received_at[key], None)
                for key, value in files.items()
            ),
            provenance=SourceSnapshotProvenance(
                vendor_key="tushare.pro-neeq.cs.com.cn-cninfo.com.cn",
                source_key="quality-bband.2026-calendar-boundary.601028-400267-lineage.source-bounded.v1",
                license_ref="tushare.pro.terms-official.public-disclosure",
                retention_policy_ref="backtest.acquisition.candidate",
            ),
        )
    except Exception:  # noqa: BLE001 -- snapshot internals are not receipt data.
        raise AcquisitionError("source snapshot freeze failed") from None
    if outcome.snapshot is None:
        raise AcquisitionError("source snapshot freeze failed")
    snapshot = outcome.snapshot
    try:
        verification = verify_source_snapshot(snapshot)
        rebuilt = {
            member.member_key: snapshot.member_bytes(member.member_key)
            for member in snapshot.members
        }
    except Exception:  # noqa: BLE001 -- snapshot internals are not receipt data.
        raise AcquisitionError("source snapshot verification failed") from None
    if verification.failure is not None or rebuilt != files:
        raise AcquisitionError("source snapshot verification failed")
    return snapshot


def _publish(
    output_dir: Path,
    files: dict[str, bytes],
    received_at: dict[str, int],
    receipt: dict[str, object],
) -> None:
    output = _require_safe_output(output_dir)
    staging = output.parent / f".{output.name}.staging-v1"
    _require_safe_output(staging)
    published = {
        **files,
        "source-snapshot.json": canonical_bytes(receipt["snapshot"]),
        "acquisition-receipt.json": canonical_bytes(receipt),
    }
    if len(files) != 4 or len(published) != 6:
        raise AcquisitionError("publication layout mismatch")
    renamed = False
    try:
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _require_safe_output(output)
        _require_safe_output(staging)
        staging.mkdir(mode=0o700)
        ordered = sorted(
            published.items(), key=lambda item: item[0] == "acquisition-receipt.json"
        )
        for relative, source in ordered:
            path = staging / relative
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "wb") as handle:
                    descriptor = -1
                    handle.write(source)
                    handle.flush()
                    os.fsync(handle.fileno())
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
        for relative, source in published.items():
            path = staging / relative
            persisted = path.read_bytes()
            if persisted != source or path.stat().st_mode & 0o777 != 0o600:
                raise OSError("staged readback mismatch")
        staged_files = {key: (staging / key).read_bytes() for key in files}
        if _freeze(staged_files, received_at).to_canonical_dict() != receipt["snapshot"]:
            raise OSError("staged snapshot mismatch")
        for directory_path in sorted(
            {staging, *(path.parent for path in staging.rglob("*") if path.is_file())},
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            descriptor = os.open(
                directory_path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            )
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        _require_safe_output(output)
        os.rename(staging, output)
        renamed = True
        descriptor = os.open(
            output.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except BaseException:
        shutil.rmtree(output if renamed else staging, ignore_errors=True)
        raise AcquisitionError("publication failed") from None


def acquire_cn_a_share_quality_bband_2026_calendar_lineage_source_bounded_v1(
    *,
    token: str,
    endpoint: str,
    output_dir: Path,
    proxy_post: ProxyPost,
    get: Get,
    sleep: Sleep,
    clock: Clock,
) -> dict[str, object]:
    output = _require_safe_output(output_dir)
    if (
        type(token) is not str
        or len(token) != 56
        or token != token.strip()
        or any(character.isspace() for character in token)
    ):
        raise AcquisitionError("TUSHARE_PROXY_TOKEN must be exact 56-character text")
    if endpoint not in _ALLOWED_ENDPOINTS:
        raise AcquisitionError("proxy endpoint is not approved")
    if not all(callable(value) for value in (proxy_post, get, sleep, clock)):
        raise AcquisitionError("acquisition callbacks must be callable")
    if token in os.fspath(output):
        raise AcquisitionError("credential input is invalid")

    files: dict[str, bytes] = {}
    received_at: dict[str, int] = {}
    logical_requests: list[dict[str, object]] = []
    total_bytes = 0
    proxy_headers = _headers(token)
    public_proxy_headers = [
        [name, value] for name, value in proxy_headers.items() if name.lower() != "x-api-key"
    ]

    for exchange, member_key in _CALENDAR_MEMBER_KEYS.items():
        body = _request_body(
            "trade_cal", {"exchange": exchange, **_CALENDAR_PARAMS}, _CALENDAR_FIELDS
        )
        source, attempts = _proxy_with_retries(
            endpoint,
            body,
            proxy_headers,
            proxy_post,
            sleep,
            total_remaining=MAX_TOTAL_BYTES - total_bytes,
        )
        received = _timestamp(clock)
        rows = _validate_calendar(source, exchange, token)
        files[member_key] = source
        received_at[member_key] = received
        total_bytes += len(source)
        logical_requests.append(
            {
                "logical_index": len(logical_requests),
                "request_kind": "tushare_proxy_post",
                "member_key": member_key,
                "url": endpoint,
                "request_body": body,
                "ordered_headers": public_proxy_headers,
                "auth_mode": "x-api-key-redacted",
                "attempts": attempts,
                "status": 200,
                "response_received_at_epoch_nanoseconds": received,
                "response_byte_count": len(source),
                "response_sha256": sha256(source),
                "returned_row_count": len(rows),
            }
        )

    response = _get_with_retries(
        _NEEQ_URL,
        _NEEQ_HEADERS,
        get,
        sleep,
        member_limit=MAX_METADATA_MEMBER_BYTES,
        total_remaining=MAX_TOTAL_BYTES - total_bytes,
    )
    status, response_headers, source, final_url, attempts = response
    received = _timestamp(clock)
    if status != 200:
        raise AcquisitionError("NEEQ response status mismatch")
    selected_neeq_fact, extra_count = _parse_neeq(source)
    files[_NEEQ_MEMBER_KEY] = source
    received_at[_NEEQ_MEMBER_KEY] = received
    total_bytes += len(source)
    logical_requests.append(
        {
            "logical_index": len(logical_requests),
            "request_kind": "neeq_metadata_get",
            "member_key": _NEEQ_MEMBER_KEY,
            "url": _NEEQ_URL,
            "request_body": None,
            "ordered_headers": [list(pair) for pair in _NEEQ_HEADERS],
            "auth_mode": "none",
            "attempts": attempts,
            "status": status,
            "final_url": final_url,
            "response_headers": [list(pair) for pair in response_headers],
            "response_received_at_epoch_nanoseconds": received,
            "response_byte_count": len(source),
            "response_sha256": sha256(source),
            "returned_row_count": 13,
        }
    )

    response = _get_with_retries(
        _PDF_URL,
        _PDF_HEADERS,
        get,
        sleep,
        member_limit=MAX_PDF_MEMBER_BYTES,
        total_remaining=MAX_TOTAL_BYTES - total_bytes,
    )
    status, response_headers, source, final_url, attempts = response
    received = _timestamp(clock)
    if status != 200:
        raise AcquisitionError("PDF response status mismatch")
    content_types = [value for name, value in response_headers if name == "Content-Type"]
    if (
        len(content_types) != 1
        or content_types[0].split(";", 1)[0].strip().lower() != "application/pdf"
    ):
        raise AcquisitionError("PDF content type mismatch")
    if not source.startswith(b"%PDF-"):
        raise AcquisitionError("PDF magic mismatch")
    if len(source) != _PDF_BYTE_COUNT:
        raise AcquisitionError("PDF byte count mismatch")
    if sha256(source) != _PDF_SHA256:
        raise AcquisitionError("PDF hash mismatch")
    files[_PDF_MEMBER_KEY] = source
    received_at[_PDF_MEMBER_KEY] = received
    total_bytes += len(source)
    logical_requests.append(
        {
            "logical_index": len(logical_requests),
            "request_kind": "official_pdf_get",
            "member_key": _PDF_MEMBER_KEY,
            "url": _PDF_URL,
            "request_body": None,
            "ordered_headers": [list(pair) for pair in _PDF_HEADERS],
            "auth_mode": "none",
            "attempts": attempts,
            "status": status,
            "final_url": final_url,
            "response_headers": [list(pair) for pair in response_headers],
            "response_received_at_epoch_nanoseconds": received,
            "response_byte_count": len(source),
            "response_sha256": sha256(source),
            "returned_row_count": None,
        }
    )

    if len(logical_requests) != MAX_LOGICAL_REQUESTS or total_bytes > MAX_TOTAL_BYTES:
        raise AcquisitionError("captured source scope mismatch")
    snapshot = _freeze(files, received_at)
    receipt: dict[str, object] = {
        "type": "cn_a_share_quality_bband_2026_calendar_lineage_source_bounded_acquisition_receipt_v1",
        "schema_version": 1,
        "capture_key": _CAPTURE_KEY,
        "acquired_at_epoch_nanoseconds": max(received_at.values()),
        "logical_requests": logical_requests,
        "selected_neeq_fact": selected_neeq_fact,
        "neeq_extra_record_count": extra_count,
        "snapshot": snapshot.to_canonical_dict(),
        "limitations": list(_LIMITATIONS),
        **{flag: False for flag in _FALSE_FLAGS},
    }
    if any(token.encode() in value for value in (*files.values(), canonical_bytes(receipt))):
        raise AcquisitionError("credential material detected")
    _publish(output, files, received_at, receipt)
    return receipt


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture source-bounded 2026 calendar boundary and 601028/400267 lineage evidence"
    )
    parser.add_argument(
        "--endpoint", choices=_ALLOWED_ENDPOINTS, default=_ALLOWED_ENDPOINTS[0]
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(sys.argv[1:] if argv is None else argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    token = os.environ.get("TUSHARE_PROXY_TOKEN", "")
    if not token:
        raise SystemExit("TUSHARE_PROXY_TOKEN must be provided through the environment")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    retained_bytes = 0

    def get(url: str, headers: HeaderPairs) -> tuple[int, HeaderPairs, bytes, str]:
        nonlocal retained_bytes
        if (url, headers) not in {(_NEEQ_URL, _NEEQ_HEADERS), (_PDF_URL, _PDF_HEADERS)}:
            raise AcquisitionError("GET request is not allowed")
        member_limit = MAX_METADATA_MEMBER_BYTES if url == _NEEQ_URL else MAX_PDF_MEMBER_BYTES
        request = urllib.request.Request(url, headers=dict(headers), method="GET")
        try:
            with opener.open(request, timeout=30) as response:
                source = _read_bounded(
                    response, member_limit, MAX_TOTAL_BYTES - retained_bytes
                )
                result = (
                    int(response.status),
                    _NoRedirect.header_pairs(response.headers),
                    source,
                    response.geturl(),
                )
        except urllib.error.HTTPError as error:
            try:
                source = _read_bounded(
                    error, member_limit, MAX_TOTAL_BYTES - retained_bytes
                )
                result = (
                    int(error.code),
                    _NoRedirect.header_pairs(error.headers),
                    source,
                    error.geturl(),
                )
            finally:
                error.close()
        if result[0] == 200:
            retained_bytes += len(result[2])
        return result

    try:
        receipt = acquire_cn_a_share_quality_bband_2026_calendar_lineage_source_bounded_v1(
            token=token,
            endpoint=args.endpoint,
            output_dir=args.output_dir,
            proxy_post=_stdlib_post,
            get=get,
            sleep=time.sleep,
            clock=time.time_ns,
        )
    except AcquisitionError as error:
        raise SystemExit(f"acquisition failed: {error}") from None
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
