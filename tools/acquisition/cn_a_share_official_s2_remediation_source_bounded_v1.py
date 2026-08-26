from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)

from . import _common
from ._common import AcquisitionError, json_bytes, sha256

HeaderPairs = tuple[tuple[str, str], ...]
FormPairs = tuple[tuple[str, str], ...]
Post = Callable[[str, FormPairs, HeaderPairs], tuple[int, object, bytes, str]]
Get = Callable[[str, HeaderPairs], tuple[int, object, bytes, str]]
Sleep = Callable[[float], object]
Clock = Callable[[], int]

_METADATA_ENDPOINT = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
_CAPTURE_KEY = "20260826-official-s2-remediation-candidate-01"
_FORM_KEYS = (
    "pageNum", "pageSize", "column", "tabName", "plate", "stock", "searchkey",
    "secid", "category", "trade", "seDate", "sortName", "sortType", "isHLtitle",
)
_CNINFO_POST_HEADERS: HeaderPairs = (
    ("Accept", "application/json, text/javascript, */*; q=0.01"),
    ("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8"),
    ("Referer", "https://www.cninfo.com.cn/"),
    ("User-Agent", "Mozilla/5.0"),
    ("X-Requested-With", "XMLHttpRequest"),
)
_CNINFO_PDF_HEADERS: HeaderPairs = (
    ("Accept", "application/pdf,*/*"),
    ("Referer", "https://www.cninfo.com.cn/"),
    ("User-Agent", "Mozilla/5.0"),
)
_SSE_PDF_HEADERS: HeaderPairs = (
    ("Accept", "application/pdf,*/*"),
    ("Referer", "https://www.sse.com.cn/"),
    ("User-Agent", "Mozilla/5.0"),
)
_METADATA_ENVELOPE_KEYS = (
    "classifiedAnnouncements", "totalSecurities", "totalAnnouncement", "totalRecordNum",
    "announcements", "categoryList", "hasMore", "totalpages",
)
_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
_RETRY_DELAYS = (1.0, 2.0)
MAX_LOGICAL_REQUESTS = 22
MAX_METADATA_MEMBER_BYTES = 1 << 20
MAX_PDF_MEMBER_BYTES = 8 << 20
MAX_TOTAL_BYTES = 32 << 20
_LIMITATIONS = (
    "SOURCE_BOUNDED_ONLY",
    "OFFICIAL_EVIDENCE_NOT_REVIEWED_BY_BUILDER",
    "NONFILING_DECLARATIONS_NOT_CONSTRUCTED",
    "FINANCIAL_STATEMENT_NOT_EXTRACTED",
    "FINANCIAL_AVAILABILITY_NOT_QUALIFIED",
    "REVISION_CLOSURE_INCOMPLETE",
    "S1_AUTHORITY_MISSING",
    "S2B_EXACT_COVER_FALSE",
    "DECISION_GRADE_FALSE",
    "DEPLOYMENT_AUTHORIZED_FALSE",
)
_FALSE_FLAGS = (
    "official_evidence_reviewed",
    "nonfiling_declarations_constructed",
    "financial_statement_extracted",
    "financial_payload_complete",
    "financial_availability_qualified",
    "revision_closure_complete",
    "s2b_exact_cover_complete",
    "decision_grade_eligible",
    "deployment_authorized",
)


@dataclass(frozen=True, slots=True)
class MetadataRequest:
    key: str
    column: str
    plate: str
    stock: str
    searchkey: str
    category: str
    se_date: str
    selected_ids: tuple[str, ...]
    expected_total: int

    @property
    def member_key(self) -> str:
        return f"response/cninfo/announcement-query/{self.key}-v1.json"

    @property
    def form(self) -> FormPairs:
        return (
            ("pageNum", "1"), ("pageSize", "30"), ("column", self.column),
            ("tabName", "fulltext"), ("plate", self.plate), ("stock", self.stock),
            ("searchkey", self.searchkey), ("secid", ""), ("category", self.category),
            ("trade", ""), ("seDate", self.se_date), ("sortName", ""),
            ("sortType", ""), ("isHLtitle", "true"),
        )


@dataclass(frozen=True, slots=True)
class PdfRequest:
    member_key: str
    url: str
    byte_count: int
    content_hash: str

    @property
    def headers(self) -> HeaderPairs:
        return _SSE_PDF_HEADERS if self.url.startswith("https://www.sse.com.cn/") else _CNINFO_PDF_HEADERS


_METADATA_REQUESTS = (
    MetadataRequest("000046", "szse", "sz", "000046,gssz0000046", "", "category_ndbg_szsh", "2015-01-01~2015-12-31", ("1200788303",), 2),
    MetadataRequest("000693", "szse", "sz", "000693,gssz0000693", "", "", "2019-04-25~2019-05-20", ("1206163240", "1206283352"), 4),
    MetadataRequest("000038", "szse", "sz", "000038,gssz0000038", "", "", "2023-04-25~2023-06-15", ("1216782869", "1217029890"), 7),
    MetadataRequest("000976-initial", "szse", "sz", "000976,gssz0000976", "", "", "2024-05-01~2024-05-31", ("1220037786",), 14),
    MetadataRequest("000976-terminal", "szse", "sz", "000976,gssz0000976", "", "", "2024-08-20~2024-08-30", ("1220964685",), 4),
    MetadataRequest("000622", "szse", "sz", "000622,gssz0000622", "", "", "2025-04-20~2025-06-25", ("1223449834", "1223910946"), 18),
    MetadataRequest("601028", "sse", "sh", "", "玉龙股份", "", "2025-04-20~2025-05-31", ("1223364517", "1223607424"), 14),
)
_SELECTED_FACTS = (
    ("1200788303", "2014年年度报告", 1428076800000, "finalpage/2015-04-04/1200788303.PDF"),
    ("1206163240", "关于无法在法定期限内披露2018年年度报告及公司股票可能被终止上市的风险提示公告", 1556553600000, "finalpage/2019-04-30/1206163240.PDF"),
    ("1206283352", "关于公司股票终止上市的公告", 1558108800000, "finalpage/2019-05-18/1206283352.PDF"),
    ("1216782869", "关于收到深圳证券交易所《事先告知书》暨公司股票可能被终止上市的风险提示性公告", 1683648000000, "finalpage/2023-05-10/1216782869.PDF"),
    ("1217029890", "关于收到股票终止上市决定的公告", 1686326400000, "finalpage/2023-06-10/1217029890.PDF"),
    ("1220037786", "关于公司股票交易被叠加实施其他风险警示的公告", 1715502229000, "finalpage/2024-05-12/1220037786.PDF"),
    ("1220964685", "关于公司未在规定期限内披露定期报告的风险提示公告", 1724428800000, "finalpage/2024-08-24/1220964685.PDF"),
    ("1223449834", "关于无法在法定期限内披露定期报告致股票可能被终止上市暨停牌的风险提示公告", 1746460800000, "finalpage/2025-05-06/1223449834.pdf"),
    ("1223910946", "关于收到股票终止上市决定的公告", 1750262400000, "finalpage/2025-06-19/1223910946.PDF"),
    ("1223364517", "关于无法在法定期限内披露2024年年度报告及2025年第一季度报告的公告", 1745856000000, "finalpage/2025-04-29/1223364517.PDF"),
    ("1223607424", "关于股票终止上市暨摘牌的公告", 1747756800000, "finalpage/2025-05-21/1223607424.PDF"),
)
_SELECTED_BY_ID = {fact[0]: fact for fact in _SELECTED_FACTS}
_PDF_REQUESTS = (
    PdfRequest("response/official/000046/1200788303.pdf", "https://static.cninfo.com.cn/finalpage/2015-04-04/1200788303.PDF", 4164254, "sha256:0a5bce6a608fcc444d5405c29e81428efe349370c6d8cc4ba72dca26272bec1c"),
    PdfRequest("response/official/000693/1206163240.pdf", "https://static.cninfo.com.cn/finalpage/2019-04-30/1206163240.PDF", 250606, "sha256:6578ea31d44ca91fc596ce72c27e66953bd90e2c4bbda77b927957e4f1c1e7b5"),
    PdfRequest("response/official/000693/1206283352.pdf", "https://static.cninfo.com.cn/finalpage/2019-05-18/1206283352.PDF", 238020, "sha256:7f83246f3b971d2f0eaf7c3abb2548005e0126b2b351a7660142195add46e5f6"),
    PdfRequest("response/official/600090/a38770503b904cf88f85ebe52a75ad36.pdf", "https://www.sse.com.cn/disclosure/credibility/supervision/inquiries/enquiry/c/10111560/files/a38770503b904cf88f85ebe52a75ad36.pdf", 125353, "sha256:cdcdb05206c914e643eb39abc12aaf435b6763d332557c36fda986ce4e699ffe"),
    PdfRequest("response/official/600090/16e8ccc4577d410891dfba7e2a691af0.pdf", "https://www.sse.com.cn/disclosure/credibility/supervision/measures/focus/c/10107770/files/16e8ccc4577d410891dfba7e2a691af0.pdf", 349016, "sha256:f2bcc3e0b18aa974c1b52922d96d30d507ca82826c042fc64c662ae8fa74686d"),
    PdfRequest("response/official/600146/514dd89bf3c24c4a95afb42c4aa7cfba.pdf", "https://www.sse.com.cn/disclosure/credibility/supervision/inquiries/enquiry/c/10111562/files/514dd89bf3c24c4a95afb42c4aa7cfba.pdf", 129449, "sha256:7d7a6cc76001b950075f8a4bfcd4c1477f9fe998ffb05d8834ef72ccfca09c73"),
    PdfRequest("response/official/600146/8f60b5e2db23462e84d9ef368cb683ac.pdf", "https://www.sse.com.cn/disclosure/credibility/supervision/measures/focus/c/10107748/files/8f60b5e2db23462e84d9ef368cb683ac.pdf", 341493, "sha256:7a14ec4babb3ae73211bb7a0cb775ae010563071c454c56df34a9f97b6bdb5fa"),
    PdfRequest("response/official/000038/1216782869.pdf", "https://static.cninfo.com.cn/finalpage/2023-05-10/1216782869.PDF", 91169, "sha256:3cdd32ebbf332aa65a344ab1163c453a9329cbc165d807e182a210b14da62db6"),
    PdfRequest("response/official/000038/1217029890.pdf", "https://static.cninfo.com.cn/finalpage/2023-06-10/1217029890.PDF", 107944, "sha256:6167f546f845c8d5cf52cc20874387b3e7072cb5e8fb44950a10cb7f4068ff6f"),
    PdfRequest("response/official/000976/1220037786.pdf", "https://static.cninfo.com.cn/finalpage/2024-05-12/1220037786.PDF", 204419, "sha256:dc9a031017f6a610084814bf953e2fbdc84623dbf56a9c5e61abb8da4bc7c833"),
    PdfRequest("response/official/000976/1220964685.pdf", "https://static.cninfo.com.cn/finalpage/2024-08-24/1220964685.PDF", 155897, "sha256:94849b146f85130caf0a839a1819318d5ea308029027aef79d823cf95e272839"),
    PdfRequest("response/official/000622/1223449834.pdf", "https://static.cninfo.com.cn/finalpage/2025-05-06/1223449834.pdf", 75386, "sha256:2b6b64ab65162384089c9dfa3155c56ceda4f4694e9f755d50f7f3a4241a8747"),
    PdfRequest("response/official/000622/1223910946.pdf", "https://static.cninfo.com.cn/finalpage/2025-06-19/1223910946.PDF", 412757, "sha256:6d428f36a27ec29a21953dfef08dca180fc1b6194e92df7964c1e08ab938a2fa"),
    PdfRequest("response/official/601028/1223364517.pdf", "https://static.cninfo.com.cn/finalpage/2025-04-29/1223364517.PDF", 70480, "sha256:a25fda7dca2204bb9929188f47428edfde884233431ab62680e75f537ee56d1d"),
    PdfRequest("response/official/601028/1223607424.pdf", "https://static.cninfo.com.cn/finalpage/2025-05-21/1223607424.PDF", 96288, "sha256:627c57066b5b494b35f571150b26e91faafd03b44bd574506e70a65bddf59c75"),
)
_PDF_URLS = frozenset(request.url for request in _PDF_REQUESTS)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    class ResponseBoundaryError(AcquisitionError):
        pass

    def redirect_request(self, request: object, file_pointer: object, code: int, message: str, headers: object, new_url: str) -> None:
        return None

    @staticmethod
    def header_pairs(value: object) -> HeaderPairs:
        if isinstance(value, Mapping):
            items = tuple(value.items())
        elif callable(getattr(value, "items", None)):
            items = tuple(value.items())
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            items = tuple(value)
        else:
            raise AcquisitionError("response headers are invalid")
        pairs: list[tuple[str, str]] = []
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, Sequence) or isinstance(item, (str, bytes, bytearray)) or len(item) != 2:
                raise AcquisitionError("response headers are invalid")
            name, header_value = item
            if type(name) is not str or type(header_value) is not str:
                raise AcquisitionError("response headers are invalid")
            lowered = name.lower()
            if lowered in {"content-type", "content-length"}:
                if lowered in seen:
                    raise AcquisitionError("response headers are invalid")
                seen.add(lowered)
                pairs.append(("Content-Type" if lowered == "content-type" else "Content-Length", header_value))
        return tuple(pairs)

    @classmethod
    def content_length(cls, headers: HeaderPairs) -> int | None:
        values = [value for name, value in headers if name == "Content-Length"]
        if not values:
            return None
        value = values[0]
        if not value or not value.isascii() or not value.isdecimal():
            raise cls.ResponseBoundaryError("Content-Length is invalid")
        return int(value)

    @classmethod
    def semantic_response(cls, value: object, member_limit: int, total_remaining: int) -> tuple[int, HeaderPairs, bytes, str]:
        if type(value) is not tuple or len(value) != 4:
            raise AcquisitionError("provider transport failed")
        status, raw_headers, source, final_url = value
        if type(status) is not int or isinstance(status, bool) or not 100 <= status <= 599 or type(source) is not bytes or type(final_url) is not str:
            raise AcquisitionError("provider transport failed")
        headers = cls.header_pairs(raw_headers)
        declared = cls.content_length(headers)
        ceiling = min(member_limit, total_remaining)
        if len(source) > ceiling or declared is not None and declared > ceiling:
            raise cls.ResponseBoundaryError("response byte ceiling exceeded")
        if declared is not None and declared != len(source):
            raise cls.ResponseBoundaryError("Content-Length mismatch")
        return status, headers, source, final_url

    @staticmethod
    def json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    @staticmethod
    def timestamp(clock: Clock) -> int:
        try:
            value = clock()
        except Exception:  # noqa: BLE001 -- collaborator details are not receipt data.
            raise AcquisitionError("acquisition clock failed") from None
        if type(value) is not int or value < 0:
            raise AcquisitionError("acquisition clock failed")
        return value


def _require_safe_output(output_dir: Path) -> Path:
    if not isinstance(output_dir, Path):
        raise AcquisitionError("output path is not safe")
    output = output_dir.absolute()
    if output.is_symlink() or os.path.lexists(output) or output == output.parent:
        raise AcquisitionError("output path is not safe")
    for ancestor in output.parents:
        if os.path.lexists(ancestor) and (ancestor.is_symlink() or not ancestor.is_dir()):
            raise AcquisitionError("output path is not safe")
    return output


def _read_bounded(response: Any, member_limit: int, total_remaining: int) -> bytes:
    if type(member_limit) is not int or type(total_remaining) is not int or member_limit < 0 or total_remaining < 0:
        raise _NoRedirect.ResponseBoundaryError("response byte ceiling is invalid")
    headers = _NoRedirect.header_pairs(response.headers)
    ceiling = min(member_limit, total_remaining)
    declared = _NoRedirect.content_length(headers)
    if declared is not None and declared > ceiling:
        raise _NoRedirect.ResponseBoundaryError("response byte ceiling exceeded")
    chunks: list[bytes] = []
    remaining = ceiling + 1
    while remaining:
        chunk = response.read(remaining)
        if type(chunk) is not bytes:
            raise AcquisitionError("provider transport failed")
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    source = b"".join(chunks)
    if len(source) > ceiling:
        raise _NoRedirect.ResponseBoundaryError("response byte ceiling exceeded")
    if declared is not None and declared != len(source):
        raise _NoRedirect.ResponseBoundaryError("Content-Length mismatch")
    return source


def _post_with_retries(url: str, form: FormPairs, headers: HeaderPairs, post: Post, sleep: Sleep, *, total_remaining: int) -> tuple[int, HeaderPairs, bytes, str, int]:
    if url != _METADATA_ENDPOINT or tuple(name for name, _ in form) != _FORM_KEYS or headers != _CNINFO_POST_HEADERS:
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


def _get_with_retries(url: str, headers: HeaderPairs, get: Get, sleep: Sleep, *, total_remaining: int) -> tuple[int, HeaderPairs, bytes, str, int]:
    if url not in _PDF_URLS or headers not in {_CNINFO_PDF_HEADERS, _SSE_PDF_HEADERS}:
        raise AcquisitionError("PDF request is not allowed")
    for attempt in range(1, 4):
        try:
            raw_response = get(url, headers)
        except _NoRedirect.ResponseBoundaryError:
            raise
        except Exception:  # noqa: BLE001 -- collaborator details are not receipt data.
            response = None
        else:
            response = _NoRedirect.semantic_response(raw_response, MAX_PDF_MEMBER_BYTES, total_remaining)
        if response is not None:
            status, response_headers, source, final_url = response
            if final_url != url:
                raise AcquisitionError("PDF final URL mismatch")
            if status not in _RETRYABLE_STATUSES:
                return status, response_headers, source, final_url, attempt
        if attempt == 3:
            raise AcquisitionError("provider transport failed")
        try:
            sleep(_RETRY_DELAYS[attempt - 1])
        except Exception:  # noqa: BLE001 -- collaborator details are not receipt data.
            raise AcquisitionError("provider transport failed") from None
    raise AssertionError("unreachable")


def _parse_metadata(source: bytes, request: MetadataRequest) -> tuple[list[dict[str, object]], int]:
    try:
        payload = json.loads(source, object_pairs_hook=_NoRedirect.json_object, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        raise AcquisitionError("metadata response is invalid") from None
    if type(payload) is not dict or set(payload) != set(_METADATA_ENVELOPE_KEYS):
        raise AcquisitionError("metadata response is invalid")
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
        or payload["totalpages"] != 0
        or type(payload["totalpages"]) is not int
    ):
        raise AcquisitionError("metadata response scope mismatch")
    selected: list[dict[str, object]] = []
    for selected_id in request.selected_ids:
        records = [
            record for record in announcements
            if type(record) is dict and record.get("announcementId") == selected_id
        ]
        if len(records) != 1:
            raise AcquisitionError("selected metadata record mismatch")
        record = cast(dict[str, object], records[0])
        expected = _SELECTED_BY_ID[selected_id]
        title = record.get("announcementTitle")
        normalized_title = title.replace("<em>", "").replace("</em>", "") if type(title) is str else None
        if normalized_title != expected[1] or record.get("announcementTime") != expected[2] or record.get("adjunctUrl") != expected[3]:
            raise AcquisitionError("selected metadata fact mismatch")
        selected.append({
            "announcement_id": selected_id,
            "title": expected[1],
            "announcement_time_epoch_milliseconds": expected[2],
            "adjunct_url": expected[3],
        })
    return selected, request.expected_total - len(request.selected_ids)


def _validate_pdf(source: bytes, request: PdfRequest, response_headers: HeaderPairs) -> None:
    content_types = [value for name, value in response_headers if name == "Content-Type"]
    if len(content_types) != 1 or content_types[0].split(";", 1)[0].strip().lower() != "application/pdf":
        raise AcquisitionError("PDF content type mismatch")
    if not source.startswith(b"%PDF-"):
        raise AcquisitionError("PDF magic mismatch")
    if len(source) != request.byte_count:
        raise AcquisitionError("PDF byte count mismatch")
    if sha256(source) != request.content_hash:
        raise AcquisitionError("PDF hash mismatch")


def acquire_official_s2_remediation_source_v1(*, output_dir: Path, post: Post, get: Get, sleep: Sleep, clock: Clock) -> dict[str, object]:
    output = _require_safe_output(output_dir)
    if not callable(post) or not callable(get) or not callable(sleep) or not callable(clock):
        raise AcquisitionError("acquisition input is invalid")
    if len(_METADATA_REQUESTS) + len(_PDF_REQUESTS) != MAX_LOGICAL_REQUESTS:
        raise AcquisitionError("logical request ceiling mismatch")

    files: dict[str, bytes] = {}
    received_at: dict[str, int] = {}
    logical_requests: list[dict[str, object]] = []
    selected_facts: list[dict[str, object]] = []
    metadata_extra_record_count = 0
    total_bytes = 0

    for metadata in _METADATA_REQUESTS:
        if len(logical_requests) >= MAX_LOGICAL_REQUESTS:
            raise AcquisitionError("logical request ceiling exceeded")
        status, response_headers, source, final_url, attempts = _post_with_retries(
            _METADATA_ENDPOINT, metadata.form, _CNINFO_POST_HEADERS, post, sleep,
            total_remaining=MAX_TOTAL_BYTES - total_bytes,
        )
        received = _NoRedirect.timestamp(clock)
        if status != 200:
            raise AcquisitionError("metadata response status mismatch")
        if final_url != _METADATA_ENDPOINT:
            raise AcquisitionError("metadata final URL mismatch")
        facts, extras = _parse_metadata(source, metadata)
        selected_facts.extend(facts)
        metadata_extra_record_count += extras
        files[metadata.member_key] = source
        received_at[metadata.member_key] = received
        total_bytes += len(source)
        logical_requests.append({
            "logical_index": len(logical_requests),
            "request_kind": "metadata_post",
            "request_key": metadata.key,
            "member_key": metadata.member_key,
            "url": _METADATA_ENDPOINT,
            "ordered_form": [list(item) for item in metadata.form],
            "ordered_headers": [list(item) for item in _CNINFO_POST_HEADERS],
            "attempts": attempts,
            "status": status,
            "final_url": final_url,
            "response_headers": [list(item) for item in response_headers],
            "response_sha256": sha256(source),
            "response_byte_count": len(source),
            "response_received_at_epoch_nanoseconds": received,
        })

    for pdf in _PDF_REQUESTS:
        if len(logical_requests) >= MAX_LOGICAL_REQUESTS:
            raise AcquisitionError("logical request ceiling exceeded")
        status, response_headers, source, final_url, attempts = _get_with_retries(
            pdf.url, pdf.headers, get, sleep, total_remaining=MAX_TOTAL_BYTES - total_bytes,
        )
        received = _NoRedirect.timestamp(clock)
        if status != 200:
            raise AcquisitionError("PDF response status mismatch")
        if final_url != pdf.url:
            raise AcquisitionError("PDF final URL mismatch")
        _validate_pdf(source, pdf, response_headers)
        files[pdf.member_key] = source
        received_at[pdf.member_key] = received
        total_bytes += len(source)
        logical_requests.append({
            "logical_index": len(logical_requests),
            "request_kind": "pdf_get",
            "request_key": pdf.member_key,
            "member_key": pdf.member_key,
            "url": pdf.url,
            "ordered_headers": [list(item) for item in pdf.headers],
            "attempts": attempts,
            "status": status,
            "final_url": final_url,
            "response_headers": [list(item) for item in response_headers],
            "response_sha256": sha256(source),
            "response_byte_count": len(source),
            "response_received_at_epoch_nanoseconds": received,
        })

    if total_bytes > MAX_TOTAL_BYTES or tuple(fact["announcement_id"] for fact in selected_facts) != tuple(fact[0] for fact in _SELECTED_FACTS):
        raise AcquisitionError("captured source scope mismatch")
    try:
        outcome = freeze_source_snapshot(
            members=tuple(RawSourceMember(key, value, "0644", received_at[key], None) for key, value in files.items()),
            provenance=SourceSnapshotProvenance(
                vendor_key="cninfo.com.cn-sse.com.cn",
                source_key="official.s2-remediation.000046-000693-600090-600146-000038-000976-000622-601028.v1",
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
        "type": "official_s2_remediation_source_receipt",
        "schema_version": 1,
        "capture_key": _CAPTURE_KEY,
        "acquired_at_epoch_nanoseconds": max(received_at.values()),
        "logical_requests": logical_requests,
        "selected_metadata_facts": selected_facts,
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
    if len(published) != 24 or set(published) != set(files) | {"source-snapshot.json", "acquisition-receipt.json"}:
        raise AcquisitionError("publication layout mismatch")
    try:
        _common.publish_directory(output_dir, published)
    except Exception:  # noqa: BLE001 -- publication internals are not receipt data.
        raise AcquisitionError("publication failed") from None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture frozen official S2 remediation source evidence")
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
        if url != _METADATA_ENDPOINT or tuple(name for name, _ in form) != _FORM_KEYS or headers != _CNINFO_POST_HEADERS:
            raise AcquisitionError("metadata request is not allowed")
        request = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode("utf-8"), headers=dict(headers), method="POST")
        return open_response(request, MAX_METADATA_MEMBER_BYTES)

    def get(url: str, headers: HeaderPairs) -> tuple[int, HeaderPairs, bytes, str]:
        if url not in _PDF_URLS or headers not in {_CNINFO_PDF_HEADERS, _SSE_PDF_HEADERS}:
            raise AcquisitionError("PDF request is not allowed")
        return open_response(urllib.request.Request(url, headers=dict(headers), method="GET"), MAX_PDF_MEMBER_BYTES)

    try:
        receipt = acquire_official_s2_remediation_source_v1(
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
