from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)

from . import _common
from ._common import AcquisitionError, json_bytes, sha256
from .cn_a_share_official_s2_remediation_source_bounded_v1 import (
    _CNINFO_PDF_HEADERS,
    _CNINFO_POST_HEADERS,
    _FORM_KEYS,
    _METADATA_ENDPOINT,
    _NoRedirect,
    _read_bounded,
    _require_safe_output,
    _RETRYABLE_STATUSES,
    _RETRY_DELAYS,
)

HeaderPairs = tuple[tuple[str, str], ...]
FormPairs = tuple[tuple[str, str], ...]
Post = Callable[[str, FormPairs, HeaderPairs], tuple[int, object, bytes, str]]
Get = Callable[[str, HeaderPairs], tuple[int, object, bytes, str]]
Sleep = Callable[[float], object]
Clock = Callable[[], int]

_CAPTURE_KEY = "20260826-official-s2-remediation-supplement-candidate-01"
_NEEQ_URL = "https://neeq.cs.com.cn/xsb/v1/xsb_search/&gs=R%E9%91%AB%E5%8D%871&st=2026-04-01&ed=2026-05-10&1.json"
_NEEQ_HEADERS: HeaderPairs = (
    ("Accept", "application/json,*/*"),
    ("Referer", "https://neeq.cs.com.cn/"),
    ("User-Agent", "Mozilla/5.0"),
)
_METADATA_ENVELOPE_KEYS = (
    "classifiedAnnouncements", "totalSecurities", "totalAnnouncement", "totalRecordNum",
    "announcements", "categoryList", "hasMore", "totalpages",
)
_NEEQ_OUTER_KEYS = ("code", "errorMessage", "data")
_NEEQ_INNER_KEYS = ("code", "errorMessage", "data", "currentPage", "size", "total")
_NEEQ_METADATA_PDF_URL = "http://dataclouds.cninfo.com.cn/sjother2/neeqs/2026/20260429/5e69266176024a6dae6eb9392c5e22b5.pdf"
_NEEQ_RETAINED_PDF_URL = "https://dataclouds.cninfo.com.cn/sjother2/neeqs/2026/20260429/5e69266176024a6dae6eb9392c5e22b5.pdf"
_LIMITATIONS = (
    "SOURCE_BOUNDED_ONLY",
    "OFFICIAL_EVIDENCE_NOT_REVIEWED_BY_BUILDER",
    "NONFILING_DECLARATIONS_NOT_CONSTRUCTED",
    "FINANCIAL_AVAILABILITY_NOT_QUALIFIED",
    "REVISION_CLOSURE_INCOMPLETE",
    "S2B_EXACT_COVER_FALSE",
    "DECISION_GRADE_FALSE",
    "DEPLOYMENT_AUTHORIZED_FALSE",
)
_FALSE_FLAGS = (
    "official_evidence_reviewed",
    "nonfiling_declarations_constructed",
    "financial_availability_qualified",
    "revision_closure_complete",
    "s2b_exact_cover_complete",
    "decision_grade_eligible",
    "deployment_authorized",
)
MAX_LOGICAL_REQUESTS = 6
MAX_METADATA_MEMBER_BYTES = 1 << 20
MAX_PDF_MEMBER_BYTES = 1 << 20
MAX_TOTAL_BYTES = 4 << 20


@dataclass(frozen=True, slots=True)
class MetadataRequest:
    key: str
    stock: str
    se_date: str
    expected_total: int
    selected_id: str

    @property
    def member_key(self) -> str:
        return f"response/cninfo/announcement-query/{self.key}-v1.json"

    @property
    def form(self) -> FormPairs:
        return (
            ("pageNum", "1"), ("pageSize", "30"), ("column", "szse"),
            ("tabName", "fulltext"), ("plate", "sz"), ("stock", self.stock),
            ("searchkey", ""), ("secid", ""), ("category", ""),
            ("trade", ""), ("seDate", self.se_date), ("sortName", ""),
            ("sortType", ""), ("isHLtitle", "true"),
        )


@dataclass(frozen=True, slots=True)
class JsonGetRequest:
    key: str
    member_key: str
    url: str
    headers: HeaderPairs


@dataclass(frozen=True, slots=True)
class PdfRequest:
    member_key: str
    url: str
    byte_count: int
    content_hash: str

    @property
    def headers(self) -> HeaderPairs:
        return _CNINFO_PDF_HEADERS


_METADATA_REQUESTS = (
    MetadataRequest("000038-predeadline", "000038,gssz0000038", "2023-04-25~2023-04-30", 3, "1216706117"),
    MetadataRequest("000976-predeadline", "000976,gssz0000976", "2024-04-20~2024-04-30", 10, "1219960138"),
)
_SELECTED_CNINFO_FACTS = (
    ("1216706117", "关于无法在法定期限内披露定期报告致股票可能被终止上市暨停牌的风险提示公告", 1682701857000, "finalpage/2023-04-29/1216706117.PDF"),
    ("1219960138", "关于无法在法定期限内披露定期报告暨股票停牌的公告", 1714474662000, "finalpage/2024-04-30/1219960138.PDF"),
)
_SELECTED_CNINFO_BY_ID = {fact[0]: fact for fact in _SELECTED_CNINFO_FACTS}
_SELECTED_NEEQ_FACT = (
    "400267",
    "R鑫升1",
    "2026-04-29T00:00:00.000+00:00",
    "[券商公告]R鑫升1:中泰证券股份有限公司关于山东鑫升矿业股份有限公司无法披露2025年年度报告的风险提示性公告",
    _NEEQ_METADATA_PDF_URL,
    "PDF",
)
_NEEQ_REQUEST = JsonGetRequest(
    "400267-202604",
    "response/neeq/disclosure-search/400267-202604-v1.json",
    _NEEQ_URL,
    _NEEQ_HEADERS,
)
_PDF_REQUESTS = (
    PdfRequest("response/official/000038/1216706117.pdf", "https://static.cninfo.com.cn/finalpage/2023-04-29/1216706117.PDF", 132535, "sha256:221bbba784c88dbe6deec97085033de38419fa78f5d6a9b08c2fa2f13bb55bab"),
    PdfRequest("response/official/000976/1219960138.pdf", "https://static.cninfo.com.cn/finalpage/2024-04-30/1219960138.PDF", 202749, "sha256:e57fa6e99f452b8e1eb59f0be39b44cfebbfc7775dd050f1050d754b190d1aec"),
    PdfRequest("response/official/601028/5e69266176024a6dae6eb9392c5e22b5.pdf", _NEEQ_RETAINED_PDF_URL, 124766, "sha256:a00a87a6b4e96e93c04d02bc3816fbe9b0488744fca65a53d3603bf509eaa464"),
)
_PDF_URLS = frozenset(request.url for request in _PDF_REQUESTS)


def _post_with_retries(url: str, form: FormPairs, headers: HeaderPairs, post: Post, sleep: Sleep, *, total_remaining: int) -> tuple[int, HeaderPairs, bytes, str, int]:
    if url != _METADATA_ENDPOINT or tuple(name for name, _ in form) != _FORM_KEYS or form not in {request.form for request in _METADATA_REQUESTS} or headers != _CNINFO_POST_HEADERS:
        raise AcquisitionError("metadata request is not allowed")
    for attempt in range(1, 4):
        try:
            raw_response = post(url, form, headers)
        except _NoRedirect.ResponseBoundaryError:
            raise
        except Exception:  # noqa: BLE001 -- collaborator details are not receipt data.
            response = None
        else:
            response = _NoRedirect.semantic_response(raw_response, MAX_METADATA_MEMBER_BYTES, total_remaining)
        if response is not None:
            status, response_headers, source, final_url = response
            if final_url != url:
                raise AcquisitionError("metadata final URL mismatch")
            if status not in _RETRYABLE_STATUSES:
                return status, response_headers, source, final_url, attempt
        if attempt == 3:
            raise AcquisitionError("provider transport failed")
        try:
            sleep(_RETRY_DELAYS[attempt - 1])
        except Exception:  # noqa: BLE001 -- collaborator details are not receipt data.
            raise AcquisitionError("provider transport failed") from None
    raise AssertionError("unreachable")


def _get_with_retries(url: str, headers: HeaderPairs, get: Get, sleep: Sleep, *, member_limit: int, total_remaining: int) -> tuple[int, HeaderPairs, bytes, str, int]:
    allowed = (
        url == _NEEQ_REQUEST.url and headers == _NEEQ_REQUEST.headers and member_limit == MAX_METADATA_MEMBER_BYTES
    ) or (
        url in _PDF_URLS and headers == _CNINFO_PDF_HEADERS and member_limit == MAX_PDF_MEMBER_BYTES
    )
    if not allowed:
        raise AcquisitionError("GET request is not allowed")
    for attempt in range(1, 4):
        try:
            raw_response = get(url, headers)
        except _NoRedirect.ResponseBoundaryError:
            raise
        except Exception:  # noqa: BLE001 -- collaborator details are not receipt data.
            response = None
        else:
            response = _NoRedirect.semantic_response(raw_response, member_limit, total_remaining)
        if response is not None:
            status, response_headers, source, final_url = response
            if final_url != url:
                raise AcquisitionError("GET final URL mismatch")
            if status not in _RETRYABLE_STATUSES:
                return status, response_headers, source, final_url, attempt
        if attempt == 3:
            raise AcquisitionError("provider transport failed")
        try:
            sleep(_RETRY_DELAYS[attempt - 1])
        except Exception:  # noqa: BLE001 -- collaborator details are not receipt data.
            raise AcquisitionError("provider transport failed") from None
    raise AssertionError("unreachable")


def _parse_cninfo_metadata(source: bytes, request: MetadataRequest) -> tuple[dict[str, object], int]:
    try:
        payload = json.loads(source, object_pairs_hook=_NoRedirect.json_object, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        raise AcquisitionError("CNINFO metadata response is invalid") from None
    if type(payload) is not dict or set(payload) != set(_METADATA_ENVELOPE_KEYS):
        raise AcquisitionError("CNINFO metadata response is invalid")
    announcements = payload["announcements"]
    if (
        payload["classifiedAnnouncements"] is not None
        or type(payload["totalSecurities"]) is not int
        or isinstance(payload["totalSecurities"], bool)
        or payload["totalSecurities"] != 0
        or payload["categoryList"] is not None
        or type(payload["totalAnnouncement"]) is not int
        or isinstance(payload["totalAnnouncement"], bool)
        or type(payload["totalRecordNum"]) is not int
        or isinstance(payload["totalRecordNum"], bool)
        or payload["totalAnnouncement"] != request.expected_total
        or payload["totalRecordNum"] != request.expected_total
        or type(announcements) is not list
        or len(announcements) != request.expected_total
        or payload["hasMore"] is not False
        or type(payload["totalpages"]) is not int
        or isinstance(payload["totalpages"], bool)
        or payload["totalpages"] != 0
    ):
        raise AcquisitionError("CNINFO metadata response scope mismatch")
    records = [record for record in announcements if type(record) is dict and record.get("announcementId") == request.selected_id]
    if len(records) != 1:
        raise AcquisitionError("selected CNINFO metadata record mismatch")
    record = cast(dict[str, object], records[0])
    expected = _SELECTED_CNINFO_BY_ID[request.selected_id]
    title = record.get("announcementTitle")
    normalized_title = title.replace("<em>", "").replace("</em>", "") if type(title) is str else None
    if normalized_title != expected[1] or record.get("announcementTime") != expected[2] or record.get("adjunctUrl") != expected[3]:
        raise AcquisitionError("selected CNINFO metadata fact mismatch")
    return {
        "announcement_id": expected[0],
        "title": expected[1],
        "announcement_time_epoch_milliseconds": expected[2],
        "adjunct_url": expected[3],
    }, request.expected_total - 1


def _parse_neeq_metadata(source: bytes) -> tuple[dict[str, object], int]:
    try:
        payload = json.loads(source, object_pairs_hook=_NoRedirect.json_object, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        raise AcquisitionError("NEEQ metadata response is invalid") from None
    if type(payload) is not dict or set(payload) != set(_NEEQ_OUTER_KEYS) or payload["code"] != 0 or type(payload["code"]) is not int or payload["errorMessage"] is not None:
        raise AcquisitionError("NEEQ metadata response is invalid")
    inner = payload["data"]
    if (
        type(inner) is not dict
        or set(inner) != set(_NEEQ_INNER_KEYS)
        or inner["code"] != 0
        or type(inner["code"]) is not int
        or inner["errorMessage"] is not None
        or inner["currentPage"] != 1
        or type(inner["currentPage"]) is not int
        or inner["size"] != 30
        or type(inner["size"]) is not int
        or inner["total"] != 27
        or type(inner["total"]) is not int
        or type(inner["data"]) is not list
        or len(inner["data"]) != 27
    ):
        raise AcquisitionError("NEEQ metadata response scope mismatch")
    records = [record for record in inner["data"] if type(record) is dict and record.get("seccode") == _SELECTED_NEEQ_FACT[0]]
    if len(records) != 1:
        raise AcquisitionError("selected NEEQ metadata record mismatch")
    record = cast(dict[str, object], records[0])
    actual = tuple(record.get(key) for key in ("seccode", "secname", "f001d", "f002v", "f003v", "f004v"))
    if actual != _SELECTED_NEEQ_FACT:
        raise AcquisitionError("selected NEEQ metadata fact mismatch")
    parsed = urllib.parse.urlsplit(cast(str, record["f003v"]))
    normalized = parsed._replace(scheme="https").geturl()
    if (
        parsed.scheme != "http"
        or parsed.hostname != "dataclouds.cninfo.com.cn"
        or parsed.port is not None
        or parsed.path != urllib.parse.urlsplit(_NEEQ_METADATA_PDF_URL).path
        or parsed.query
        or parsed.fragment
        or normalized != _NEEQ_RETAINED_PDF_URL
        or _PDF_REQUESTS[-1].url != normalized
    ):
        raise AcquisitionError("NEEQ retained PDF binding mismatch")
    return {
        "seccode": _SELECTED_NEEQ_FACT[0],
        "secname": _SELECTED_NEEQ_FACT[1],
        "published_at": _SELECTED_NEEQ_FACT[2],
        "title": _SELECTED_NEEQ_FACT[3],
        "metadata_pdf_url": _SELECTED_NEEQ_FACT[4],
        "retained_pdf_url": normalized,
    }, 26


def acquire_official_s2_remediation_supplement_source_v1(*, output_dir: Path, post: Post, get: Get, sleep: Sleep, clock: Clock) -> dict[str, object]:
    output = _require_safe_output(output_dir)
    if not callable(post) or not callable(get) or not callable(sleep) or not callable(clock):
        raise AcquisitionError("acquisition input is invalid")
    if len(_METADATA_REQUESTS) + 1 + len(_PDF_REQUESTS) != MAX_LOGICAL_REQUESTS:
        raise AcquisitionError("logical request ceiling mismatch")

    files: dict[str, bytes] = {}
    received_at: dict[str, int] = {}
    logical_requests: list[dict[str, object]] = []
    selected_cninfo_facts: list[dict[str, object]] = []
    metadata_extra_record_count = 0
    total_bytes = 0

    def retain(request_kind: str, request_key: str, member_key: str, url: str, ordered_form: FormPairs | None, ordered_headers: HeaderPairs, response: tuple[int, HeaderPairs, bytes, str, int], member_limit: int) -> bytes:
        nonlocal total_bytes
        status, response_headers, source, final_url, attempts = response
        received = _NoRedirect.timestamp(clock)
        if status != 200:
            raise AcquisitionError("response status mismatch")
        if final_url != url:
            raise AcquisitionError("response final URL mismatch")
        if len(source) > member_limit or total_bytes + len(source) > MAX_TOTAL_BYTES:
            raise AcquisitionError("response byte ceiling exceeded")
        files[member_key] = source
        received_at[member_key] = received
        total_bytes += len(source)
        logical_requests.append({
            "logical_index": len(logical_requests),
            "request_kind": request_kind,
            "request_key": request_key,
            "member_key": member_key,
            "url": url,
            "ordered_form": None if ordered_form is None else [list(item) for item in ordered_form],
            "ordered_headers": [list(item) for item in ordered_headers],
            "attempts": attempts,
            "status": status,
            "final_url": final_url,
            "response_headers": [list(item) for item in response_headers],
            "response_sha256": sha256(source),
            "response_byte_count": len(source),
            "response_received_at_epoch_nanoseconds": received,
        })
        return source

    for metadata in _METADATA_REQUESTS:
        response = _post_with_retries(
            _METADATA_ENDPOINT, metadata.form, _CNINFO_POST_HEADERS, post, sleep,
            total_remaining=MAX_TOTAL_BYTES - total_bytes,
        )
        source = retain("cninfo_metadata_post", metadata.key, metadata.member_key, _METADATA_ENDPOINT, metadata.form, _CNINFO_POST_HEADERS, response, MAX_METADATA_MEMBER_BYTES)
        fact, extras = _parse_cninfo_metadata(source, metadata)
        selected_cninfo_facts.append(fact)
        metadata_extra_record_count += extras

    response = _get_with_retries(
        _NEEQ_REQUEST.url, _NEEQ_REQUEST.headers, get, sleep,
        member_limit=MAX_METADATA_MEMBER_BYTES,
        total_remaining=MAX_TOTAL_BYTES - total_bytes,
    )
    source = retain("neeq_metadata_get", _NEEQ_REQUEST.key, _NEEQ_REQUEST.member_key, _NEEQ_REQUEST.url, None, _NEEQ_REQUEST.headers, response, MAX_METADATA_MEMBER_BYTES)
    selected_neeq_fact, extras = _parse_neeq_metadata(source)
    metadata_extra_record_count += extras

    for pdf in _PDF_REQUESTS:
        response = _get_with_retries(
            pdf.url, pdf.headers, get, sleep,
            member_limit=MAX_PDF_MEMBER_BYTES,
            total_remaining=MAX_TOTAL_BYTES - total_bytes,
        )
        source = retain("pdf_get", pdf.member_key, pdf.member_key, pdf.url, None, pdf.headers, response, MAX_PDF_MEMBER_BYTES)
        content_types = [value for name, value in response[1] if name == "Content-Type"]
        if len(content_types) != 1 or content_types[0].split(";", 1)[0].strip().lower() != "application/pdf":
            raise AcquisitionError("PDF content type mismatch")
        if not source.startswith(b"%PDF-"):
            raise AcquisitionError("PDF magic mismatch")
        if len(source) != pdf.byte_count:
            raise AcquisitionError("PDF byte count mismatch")
        if sha256(source) != pdf.content_hash:
            raise AcquisitionError("PDF hash mismatch")

    if metadata_extra_record_count != 37 or tuple(fact["announcement_id"] for fact in selected_cninfo_facts) != tuple(fact[0] for fact in _SELECTED_CNINFO_FACTS):
        raise AcquisitionError("captured source scope mismatch")
    try:
        outcome = freeze_source_snapshot(
            members=tuple(RawSourceMember(key, value, "0644", received_at[key], None) for key, value in files.items()),
            provenance=SourceSnapshotProvenance(
                vendor_key="cninfo.com.cn-neeq.cs.com.cn",
                source_key="official.s2-remediation.nonfiling-effective-boundary-supplement.v1",
                license_ref="official.public-disclosure",
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
        reconstructed = {member.member_key: snapshot.member_bytes(member.member_key) for member in snapshot.members}
    except Exception:  # noqa: BLE001 -- snapshot internals are not receipt data.
        raise AcquisitionError("source snapshot verification failed") from None
    if verification.failure is not None or reconstructed != files:
        raise AcquisitionError("source snapshot verification failed")

    receipt: dict[str, object] = {
        "type": "official_s2_remediation_supplement_source_receipt",
        "schema_version": 1,
        "capture_key": _CAPTURE_KEY,
        "acquired_at_epoch_nanoseconds": max(received_at.values()),
        "logical_requests": logical_requests,
        "selected_cninfo_facts": selected_cninfo_facts,
        "selected_neeq_fact": selected_neeq_fact,
        "metadata_extra_record_count": metadata_extra_record_count,
        "snapshot": snapshot.to_canonical_dict(),
        "limitations": list(_LIMITATIONS),
        **{flag: False for flag in _FALSE_FLAGS},
    }
    _build_output(output, files, receipt)
    return receipt


def _build_output(output_dir: Path, files: dict[str, bytes], receipt: dict[str, object]) -> None:
    published = {
        **files,
        "source-snapshot.json": json_bytes(receipt["snapshot"]),
        "acquisition-receipt.json": json_bytes(receipt),
    }
    if len(published) != 8 or set(published) != set(files) | {"source-snapshot.json", "acquisition-receipt.json"}:
        raise AcquisitionError("publication layout mismatch")
    try:
        _common.publish_directory(output_dir, published)
    except Exception:  # noqa: BLE001 -- publication internals are not receipt data.
        raise AcquisitionError("publication failed") from None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture frozen official S2 remediation supplement source evidence")
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(sys.argv[1:] if argv is None else argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    retained_bytes = 0

    def open_response(request: urllib.request.Request, member_limit: int) -> tuple[int, HeaderPairs, bytes, str]:
        nonlocal retained_bytes
        try:
            with opener.open(request, timeout=30) as response:
                source = _read_bounded(response, member_limit, MAX_TOTAL_BYTES - retained_bytes)
                status, final_url, response_headers = int(response.status), response.geturl(), _NoRedirect.header_pairs(response.headers)
        except urllib.error.HTTPError as error:
            try:
                source = _read_bounded(error, member_limit, MAX_TOTAL_BYTES - retained_bytes)
                status, final_url, response_headers = int(error.code), error.geturl(), _NoRedirect.header_pairs(error.headers)
            finally:
                error.close()
        if status == 200:
            retained_bytes += len(source)
        return status, response_headers, source, final_url

    def post(url: str, form: FormPairs, headers: HeaderPairs) -> tuple[int, HeaderPairs, bytes, str]:
        if url != _METADATA_ENDPOINT or tuple(name for name, _ in form) != _FORM_KEYS or form not in {request.form for request in _METADATA_REQUESTS} or headers != _CNINFO_POST_HEADERS:
            raise AcquisitionError("metadata request is not allowed")
        request = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode("utf-8"), headers=dict(headers), method="POST")
        return open_response(request, MAX_METADATA_MEMBER_BYTES)

    def get(url: str, headers: HeaderPairs) -> tuple[int, HeaderPairs, bytes, str]:
        if (url, headers) not in {(_NEEQ_REQUEST.url, _NEEQ_REQUEST.headers), *((pdf.url, pdf.headers) for pdf in _PDF_REQUESTS)}:
            raise AcquisitionError("GET request is not allowed")
        member_limit = MAX_METADATA_MEMBER_BYTES if url == _NEEQ_REQUEST.url else MAX_PDF_MEMBER_BYTES
        return open_response(urllib.request.Request(url, headers=dict(headers), method="GET"), member_limit)

    try:
        receipt = acquire_official_s2_remediation_supplement_source_v1(
            output_dir=args.output_dir,
            post=post,
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
