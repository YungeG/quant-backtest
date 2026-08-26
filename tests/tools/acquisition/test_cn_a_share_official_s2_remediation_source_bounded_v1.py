from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from tools.acquisition import _common
from tools.acquisition import cn_a_share_official_s2_remediation_source_bounded_v1 as sentinel

EXPECTED_FORM_KEYS = (
    "pageNum", "pageSize", "column", "tabName", "plate", "stock", "searchkey",
    "secid", "category", "trade", "seDate", "sortName", "sortType", "isHLtitle",
)
EXPECTED_POST_HEADERS = (
    ("Accept", "application/json, text/javascript, */*; q=0.01"),
    ("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8"),
    ("Referer", "https://www.cninfo.com.cn/"),
    ("User-Agent", "Mozilla/5.0"),
    ("X-Requested-With", "XMLHttpRequest"),
)
EXPECTED_CNINFO_GET_HEADERS = (
    ("Accept", "application/pdf,*/*"),
    ("Referer", "https://www.cninfo.com.cn/"),
    ("User-Agent", "Mozilla/5.0"),
)
EXPECTED_SSE_GET_HEADERS = (
    ("Accept", "application/pdf,*/*"),
    ("Referer", "https://www.sse.com.cn/"),
    ("User-Agent", "Mozilla/5.0"),
)
EXPECTED_METADATA = (
    ("000046", "szse", "sz", "000046,gssz0000046", "", "category_ndbg_szsh", "2015-01-01~2015-12-31", ("1200788303",), 2),
    ("000693", "szse", "sz", "000693,gssz0000693", "", "", "2019-04-25~2019-05-20", ("1206163240", "1206283352"), 4),
    ("000038", "szse", "sz", "000038,gssz0000038", "", "", "2023-04-25~2023-06-15", ("1216782869", "1217029890"), 7),
    ("000976-initial", "szse", "sz", "000976,gssz0000976", "", "", "2024-05-01~2024-05-31", ("1220037786",), 14),
    ("000976-terminal", "szse", "sz", "000976,gssz0000976", "", "", "2024-08-20~2024-08-30", ("1220964685",), 4),
    ("000622", "szse", "sz", "000622,gssz0000622", "", "", "2025-04-20~2025-06-25", ("1223449834", "1223910946"), 18),
    ("601028", "sse", "sh", "", "玉龙股份", "", "2025-04-20~2025-05-31", ("1223364517", "1223607424"), 14),
)
EXPECTED_FACTS = (
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
EXPECTED_PDFS = (
    ("response/official/000046/1200788303.pdf", "https://static.cninfo.com.cn/finalpage/2015-04-04/1200788303.PDF", 4164254, "sha256:0a5bce6a608fcc444d5405c29e81428efe349370c6d8cc4ba72dca26272bec1c"),
    ("response/official/000693/1206163240.pdf", "https://static.cninfo.com.cn/finalpage/2019-04-30/1206163240.PDF", 250606, "sha256:6578ea31d44ca91fc596ce72c27e66953bd90e2c4bbda77b927957e4f1c1e7b5"),
    ("response/official/000693/1206283352.pdf", "https://static.cninfo.com.cn/finalpage/2019-05-18/1206283352.PDF", 238020, "sha256:7f83246f3b971d2f0eaf7c3abb2548005e0126b2b351a7660142195add46e5f6"),
    ("response/official/600090/a38770503b904cf88f85ebe52a75ad36.pdf", "https://www.sse.com.cn/disclosure/credibility/supervision/inquiries/enquiry/c/10111560/files/a38770503b904cf88f85ebe52a75ad36.pdf", 125353, "sha256:cdcdb05206c914e643eb39abc12aaf435b6763d332557c36fda986ce4e699ffe"),
    ("response/official/600090/16e8ccc4577d410891dfba7e2a691af0.pdf", "https://www.sse.com.cn/disclosure/credibility/supervision/measures/focus/c/10107770/files/16e8ccc4577d410891dfba7e2a691af0.pdf", 349016, "sha256:f2bcc3e0b18aa974c1b52922d96d30d507ca82826c042fc64c662ae8fa74686d"),
    ("response/official/600146/514dd89bf3c24c4a95afb42c4aa7cfba.pdf", "https://www.sse.com.cn/disclosure/credibility/supervision/inquiries/enquiry/c/10111562/files/514dd89bf3c24c4a95afb42c4aa7cfba.pdf", 129449, "sha256:7d7a6cc76001b950075f8a4bfcd4c1477f9fe998ffb05d8834ef72ccfca09c73"),
    ("response/official/600146/8f60b5e2db23462e84d9ef368cb683ac.pdf", "https://www.sse.com.cn/disclosure/credibility/supervision/measures/focus/c/10107748/files/8f60b5e2db23462e84d9ef368cb683ac.pdf", 341493, "sha256:7a14ec4babb3ae73211bb7a0cb775ae010563071c454c56df34a9f97b6bdb5fa"),
    ("response/official/000038/1216782869.pdf", "https://static.cninfo.com.cn/finalpage/2023-05-10/1216782869.PDF", 91169, "sha256:3cdd32ebbf332aa65a344ab1163c453a9329cbc165d807e182a210b14da62db6"),
    ("response/official/000038/1217029890.pdf", "https://static.cninfo.com.cn/finalpage/2023-06-10/1217029890.PDF", 107944, "sha256:6167f546f845c8d5cf52cc20874387b3e7072cb5e8fb44950a10cb7f4068ff6f"),
    ("response/official/000976/1220037786.pdf", "https://static.cninfo.com.cn/finalpage/2024-05-12/1220037786.PDF", 204419, "sha256:dc9a031017f6a610084814bf953e2fbdc84623dbf56a9c5e61abb8da4bc7c833"),
    ("response/official/000976/1220964685.pdf", "https://static.cninfo.com.cn/finalpage/2024-08-24/1220964685.PDF", 155897, "sha256:94849b146f85130caf0a839a1819318d5ea308029027aef79d823cf95e272839"),
    ("response/official/000622/1223449834.pdf", "https://static.cninfo.com.cn/finalpage/2025-05-06/1223449834.pdf", 75386, "sha256:2b6b64ab65162384089c9dfa3155c56ceda4f4694e9f755d50f7f3a4241a8747"),
    ("response/official/000622/1223910946.pdf", "https://static.cninfo.com.cn/finalpage/2025-06-19/1223910946.PDF", 412757, "sha256:6d428f36a27ec29a21953dfef08dca180fc1b6194e92df7964c1e08ab938a2fa"),
    ("response/official/601028/1223364517.pdf", "https://static.cninfo.com.cn/finalpage/2025-04-29/1223364517.PDF", 70480, "sha256:a25fda7dca2204bb9929188f47428edfde884233431ab62680e75f537ee56d1d"),
    ("response/official/601028/1223607424.pdf", "https://static.cninfo.com.cn/finalpage/2025-05-21/1223607424.PDF", 96288, "sha256:627c57066b5b494b35f571150b26e91faafd03b44bd574506e70a65bddf59c75"),
)
EXPECTED_LIMITATIONS = (
    "SOURCE_BOUNDED_ONLY", "OFFICIAL_EVIDENCE_NOT_REVIEWED_BY_BUILDER",
    "NONFILING_DECLARATIONS_NOT_CONSTRUCTED", "FINANCIAL_STATEMENT_NOT_EXTRACTED",
    "FINANCIAL_AVAILABILITY_NOT_QUALIFIED", "REVISION_CLOSURE_INCOMPLETE",
    "S1_AUTHORITY_MISSING", "S2B_EXACT_COVER_FALSE", "DECISION_GRADE_FALSE",
    "DEPLOYMENT_AUTHORIZED_FALSE",
)
EXPECTED_FALSE_FLAGS = (
    "official_evidence_reviewed", "nonfiling_declarations_constructed",
    "financial_statement_extracted", "financial_payload_complete",
    "financial_availability_qualified", "revision_closure_complete",
    "s2b_exact_cover_complete", "decision_grade_eligible", "deployment_authorized",
)


def metadata_bytes(request: sentinel.MetadataRequest, mutation: Callable[[dict[str, Any]], None] | None = None) -> bytes:
    records: list[dict[str, object]] = []
    for selected_id in request.selected_ids:
        fact = dict((item[0], item) for item in EXPECTED_FACTS)[selected_id]
        records.append({
            "announcementId": selected_id,
            "announcementTitle": f"<em>{fact[1]}</em>",
            "announcementTime": fact[2],
            "adjunctUrl": fact[3],
            "retainedExtraField": "raw-source",
        })
    records.extend(
        {"announcementId": f"extra-{request.key}-{index}", "announcementTitle": "extra"}
        for index in range(request.expected_total - len(records))
    )
    payload: dict[str, Any] = {
        "classifiedAnnouncements": None,
        "totalSecurities": 0,
        "totalAnnouncement": request.expected_total,
        "totalRecordNum": request.expected_total,
        "announcements": records,
        "categoryList": None,
        "hasMore": False,
        "totalpages": 0,
    }
    if mutation:
        mutation(payload)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()


class Clock:
    def __init__(self) -> None:
        self.value = 1000

    def __call__(self) -> int:
        self.value += 1
        return self.value


class FixtureTransport:
    def __init__(self, pdfs: dict[str, bytes]) -> None:
        self.pdfs = pdfs
        self.calls: list[tuple[str, str, object]] = []
        self.post_statuses: list[int] = []
        self.get_statuses: list[int] = []
        self.metadata_mutation: Callable[[dict[str, Any]], None] | None = None
        self.post_final_url: str | None = None
        self.get_final_url: str | None = None
        self.pdf_headers: object = (("Content-Type", "application/pdf"), ("Server", "fixture"))
        self.pdf_mutation: Callable[[bytes], bytes] | None = None

    def post(self, url: str, form: sentinel.FormPairs, headers: sentinel.HeaderPairs) -> tuple[int, object, bytes, str]:
        self.calls.append(("POST", url, (form, headers)))
        status = self.post_statuses.pop(0) if self.post_statuses else 200
        request = next(item for item in sentinel._METADATA_REQUESTS if item.form == form)
        source = metadata_bytes(request, self.metadata_mutation)
        return status, (("Content-Type", "application/json;charset=UTF-8"), ("Date", "ignored")), source, self.post_final_url or url

    def get(self, url: str, headers: sentinel.HeaderPairs) -> tuple[int, object, bytes, str]:
        self.calls.append(("GET", url, headers))
        status = self.get_statuses.pop(0) if self.get_statuses else 200
        source = self.pdfs[url]
        if self.pdf_mutation:
            source = self.pdf_mutation(source)
        return status, self.pdf_headers, source, self.get_final_url or url


def fixture_pdfs(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    sources: dict[str, bytes] = {}
    requests: list[sentinel.PdfRequest] = []
    for index, request in enumerate(sentinel._PDF_REQUESTS):
        source = b"%PDF-1.7\n" + bytes([65 + index]) * (31 + index)
        sources[request.url] = source
        requests.append(sentinel.PdfRequest(request.member_key, request.url, len(source), "sha256:" + hashlib.sha256(source).hexdigest()))
    monkeypatch.setattr(sentinel, "_PDF_REQUESTS", tuple(requests))
    return sources


def acquire(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, transport: FixtureTransport | None = None, sleep: Callable[[float], object] | None = None, clock: Callable[[], int] | None = None) -> tuple[dict[str, Any], FixtureTransport, Path, list[float]]:
    pdfs = fixture_pdfs(monkeypatch)
    fixture = transport or FixtureTransport(pdfs)
    fixture.pdfs = pdfs
    sleeps: list[float] = []
    output = tmp_path / "capture"
    receipt = sentinel.acquire_official_s2_remediation_source_v1(
        output_dir=output, post=fixture.post, get=fixture.get,
        sleep=sleep or sleeps.append, clock=clock or Clock(),
    )
    return cast(dict[str, Any], receipt), fixture, output, sleeps


def test_frozen_requests_facts_headers_pdfs_ceilings_and_provenance_are_literal() -> None:
    assert tuple((r.key, r.column, r.plate, r.stock, r.searchkey, r.category, r.se_date, r.selected_ids, r.expected_total) for r in sentinel._METADATA_REQUESTS) == EXPECTED_METADATA
    assert all(tuple(name for name, _ in request.form) == EXPECTED_FORM_KEYS for request in sentinel._METADATA_REQUESTS)
    assert tuple(request.form for request in sentinel._METADATA_REQUESTS) == tuple(
        (
            ("pageNum", "1"), ("pageSize", "30"), ("column", column),
            ("tabName", "fulltext"), ("plate", plate), ("stock", stock),
            ("searchkey", searchkey), ("secid", ""), ("category", category),
            ("trade", ""), ("seDate", se_date), ("sortName", ""),
            ("sortType", ""), ("isHLtitle", "true"),
        )
        for _key, column, plate, stock, searchkey, category, se_date, _ids, _total
        in EXPECTED_METADATA
    )
    assert sentinel._CNINFO_POST_HEADERS == EXPECTED_POST_HEADERS
    assert sentinel._CNINFO_PDF_HEADERS == EXPECTED_CNINFO_GET_HEADERS
    assert sentinel._SSE_PDF_HEADERS == EXPECTED_SSE_GET_HEADERS
    assert sentinel._METADATA_ENVELOPE_KEYS == (
        "classifiedAnnouncements", "totalSecurities", "totalAnnouncement", "totalRecordNum",
        "announcements", "categoryList", "hasMore", "totalpages",
    )
    assert sentinel._SELECTED_FACTS == EXPECTED_FACTS
    assert tuple((r.member_key, r.url, r.byte_count, r.content_hash) for r in sentinel._PDF_REQUESTS) == EXPECTED_PDFS
    assert (sentinel.MAX_LOGICAL_REQUESTS, sentinel.MAX_METADATA_MEMBER_BYTES, sentinel.MAX_PDF_MEMBER_BYTES, sentinel.MAX_TOTAL_BYTES) == (22, 1 << 20, 8 << 20, 32 << 20)
    assert sentinel._LIMITATIONS == EXPECTED_LIMITATIONS
    assert sentinel._FALSE_FLAGS == EXPECTED_FALSE_FLAGS


def test_success_is_byte_identical_ordered_exactly_published_and_reconstructable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt, transport, output, sleeps = acquire(tmp_path, monkeypatch)
    assert sleeps == []
    assert [(method, url) for method, url, _ in transport.calls] == [
        *(("POST", sentinel._METADATA_ENDPOINT) for _ in range(7)),
        *(("GET", request.url) for request in sentinel._PDF_REQUESTS),
    ]
    assert [item["logical_index"] for item in receipt["logical_requests"]] == list(range(22))
    assert [item["request_kind"] for item in receipt["logical_requests"]] == ["metadata_post"] * 7 + ["pdf_get"] * 15
    assert receipt["metadata_extra_record_count"] == sum(item[-1] - len(item[-2]) for item in EXPECTED_METADATA)
    assert tuple((item["announcement_id"], item["title"], item["announcement_time_epoch_milliseconds"], item["adjunct_url"]) for item in receipt["selected_metadata_facts"]) == EXPECTED_FACTS
    assert all(set(item) == {"announcement_id", "title", "announcement_time_epoch_milliseconds", "adjunct_url"} for item in receipt["selected_metadata_facts"])
    common_request_keys = {
        "logical_index", "request_kind", "request_key", "member_key", "url",
        "ordered_headers", "attempts", "status", "final_url", "response_headers",
        "response_sha256", "response_byte_count",
        "response_received_at_epoch_nanoseconds",
    }
    assert all(set(item) == common_request_keys | {"ordered_form"} for item in receipt["logical_requests"][:7])
    assert all(set(item) == common_request_keys for item in receipt["logical_requests"][7:])
    assert set(receipt) == {
        "type", "schema_version", "capture_key", "acquired_at_epoch_nanoseconds",
        "logical_requests", "selected_metadata_facts", "metadata_extra_record_count",
        "snapshot", "limitations", *EXPECTED_FALSE_FLAGS,
    }
    assert receipt["type"] == "official_s2_remediation_source_receipt"
    assert receipt["schema_version"] == 1
    assert receipt["capture_key"] == "20260826-official-s2-remediation-candidate-01"
    assert receipt["acquired_at_epoch_nanoseconds"] == 1022
    assert receipt["limitations"] == list(EXPECTED_LIMITATIONS)
    assert all(receipt[flag] is False for flag in EXPECTED_FALSE_FLAGS)
    assert receipt["snapshot"]["provenance"] == {
        "vendor_key": "cninfo.com.cn-sse.com.cn",
        "source_key": "official.s2-remediation.000046-000693-600090-600146-000038-000976-000622-601028.v1",
        "license_ref": "official.public-disclosure",
        "retention_policy_ref": "backtest.acquisition.candidate",
    }

    regular = [path for path in output.rglob("*") if path.is_file()]
    assert len(regular) == 24
    assert {path.relative_to(output).as_posix() for path in regular} == {
        *(request.member_key for request in sentinel._METADATA_REQUESTS),
        *(request.member_key for request in sentinel._PDF_REQUESTS),
        "source-snapshot.json", "acquisition-receipt.json",
    }
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in regular)
    assert (output / "acquisition-receipt.json").read_bytes() == _common.json_bytes(receipt)
    assert (output / "source-snapshot.json").read_bytes() == _common.json_bytes(receipt["snapshot"])
    files = {
        item["member_key"]: (output / item["member_key"]).read_bytes()
        for item in receipt["logical_requests"]
    }
    assert all(files[request.member_key] == metadata_bytes(request) for request in sentinel._METADATA_REQUESTS)
    assert all(files[request.member_key] == transport.pdfs[request.url] for request in sentinel._PDF_REQUESTS)
    snapshot_members = {
        item["member_key"]: item for item in receipt["snapshot"]["members"]
    }
    for item in receipt["logical_requests"]:
        raw = files[item["member_key"]]
        expected_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
        assert item["response_byte_count"] == len(raw)
        assert item["response_sha256"] == expected_hash
        member = snapshot_members[item["member_key"]]
        assert member["byte_count"] == len(raw)
        assert member["content_hash"] == expected_hash
        assert member["mode"] == "0644"
        assert (
            member["acquired_at_epoch_nanoseconds"]
            == item["response_received_at_epoch_nanoseconds"]
        )
    timestamps = {item["member_key"]: item["response_received_at_epoch_nanoseconds"] for item in receipt["logical_requests"]}
    rebuilt = freeze_source_snapshot(
        members=tuple(RawSourceMember(key, source, "0644", timestamps[key], None) for key, source in files.items()),
        provenance=SourceSnapshotProvenance(**receipt["snapshot"]["provenance"]),
    )
    assert rebuilt.snapshot is not None
    assert rebuilt.snapshot.to_canonical_dict() == receipt["snapshot"]
    assert all(item["response_headers"] in ([["Content-Type", "application/json;charset=UTF-8"]], [["Content-Type", "application/pdf"]]) for item in receipt["logical_requests"])


@pytest.mark.parametrize("failure", ["missing", "duplicate", "has-more", "title", "time", "url", "total", "envelope-values", "keys", "duplicate-key"])
def test_metadata_scope_failures_publish_nothing(failure: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdfs = fixture_pdfs(monkeypatch)
    transport = FixtureTransport(pdfs)
    selected = sentinel._METADATA_REQUESTS[0].selected_ids[0]

    def mutate(payload: dict[str, Any]) -> None:
        if failure == "missing":
            payload["announcements"][0]["announcementId"] = "missing"
        elif failure == "duplicate":
            payload["announcements"][1] = dict(payload["announcements"][0])
        elif failure == "has-more":
            payload["hasMore"] = True
        elif failure == "title":
            payload["announcements"][0]["announcementTitle"] = "wrong"
        elif failure == "time":
            payload["announcements"][0]["announcementTime"] = 0
        elif failure == "url":
            payload["announcements"][0]["adjunctUrl"] = "wrong"
        elif failure == "total":
            payload["totalRecordNum"] += 1
        elif failure == "envelope-values":
            payload["totalSecurities"] = 1
        elif failure == "keys":
            payload["unexpected"] = False

    transport.metadata_mutation = mutate
    if failure == "duplicate-key":
        original = transport.post
        transport.post = cast(Any, lambda url, form, headers: (lambda value: (value[0], value[1], value[2].replace(b'"hasMore":false', b'"hasMore":false,"hasMore":false'), value[3]))(original(url, form, headers)))
    with pytest.raises(_common.AcquisitionError):
        sentinel.acquire_official_s2_remediation_source_v1(output_dir=tmp_path / "capture", post=transport.post, get=transport.get, sleep=lambda _: None, clock=Clock())
    assert not (tmp_path / "capture").exists()
    assert selected == "1200788303"


@pytest.mark.parametrize("failure", ["redirect", "content-type", "magic", "size", "hash", "host-path"])
def test_pdf_url_final_url_content_type_magic_size_and_hash_failures_are_atomic(failure: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdfs = fixture_pdfs(monkeypatch)
    transport = FixtureTransport(pdfs)
    if failure == "redirect":
        transport.get_final_url = "https://example.com/redirected.pdf"
    elif failure == "content-type":
        transport.pdf_headers = (("Content-Type", "text/html"),)
    elif failure == "magic":
        transport.pdf_mutation = lambda source: b"!" + source[1:]
    elif failure == "size":
        transport.pdf_mutation = lambda source: source + b"x"
    elif failure == "hash":
        transport.pdf_mutation = lambda source: source[:-1] + bytes([source[-1] ^ 1])
    else:
        first = sentinel._PDF_REQUESTS[0]
        requests = (sentinel.PdfRequest(first.member_key, "https://example.com/not-allowed.pdf", first.byte_count, first.content_hash), *sentinel._PDF_REQUESTS[1:])
        monkeypatch.setattr(sentinel, "_PDF_REQUESTS", requests)
    with pytest.raises(_common.AcquisitionError):
        sentinel.acquire_official_s2_remediation_source_v1(output_dir=tmp_path / "capture", post=transport.post, get=transport.get, sleep=lambda _: None, clock=Clock())
    assert not (tmp_path / "capture").exists()


def test_unexpected_request_headers_forms_and_metadata_final_url_are_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    request = sentinel._METADATA_REQUESTS[0]
    with pytest.raises(_common.AcquisitionError, match="not allowed"):
        sentinel._post_with_retries(
            sentinel._METADATA_ENDPOINT,
            request.form,
            (*EXPECTED_POST_HEADERS, ("Authorization", "secret")),
            lambda *_: pytest.fail("transport must not run"),
            lambda _: None,
            total_remaining=sentinel.MAX_TOTAL_BYTES,
        )
    with pytest.raises(_common.AcquisitionError, match="not allowed"):
        sentinel._post_with_retries(
            sentinel._METADATA_ENDPOINT,
            tuple(reversed(request.form)),
            EXPECTED_POST_HEADERS,
            lambda *_: pytest.fail("transport must not run"),
            lambda _: None,
            total_remaining=sentinel.MAX_TOTAL_BYTES,
        )

    fixture = FixtureTransport(fixture_pdfs(monkeypatch))
    fixture.post_final_url = "https://www.cninfo.com.cn/redirected"
    with pytest.raises(_common.AcquisitionError, match="metadata final URL"):
        sentinel.acquire_official_s2_remediation_source_v1(
            output_dir=tmp_path / "redirect",
            post=fixture.post,
            get=fixture.get,
            sleep=lambda _: None,
            clock=Clock(),
        )
    assert not (tmp_path / "redirect").exists()


def test_retryable_redirects_fail_before_a_later_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = FixtureTransport(fixture_pdfs(monkeypatch))
    original_post = fixture.post
    post_calls = 0

    def redirecting_post(url: str, form: sentinel.FormPairs, headers: sentinel.HeaderPairs) -> tuple[int, object, bytes, str]:
        nonlocal post_calls
        post_calls += 1
        response = original_post(url, form, headers)
        if post_calls == 1:
            return 500, response[1], response[2], "https://www.cninfo.com.cn/redirected"
        return response

    with pytest.raises(_common.AcquisitionError, match="metadata final URL"):
        sentinel.acquire_official_s2_remediation_source_v1(
            output_dir=tmp_path / "metadata-redirect",
            post=redirecting_post,
            get=fixture.get,
            sleep=lambda _: None,
            clock=Clock(),
        )
    assert post_calls == 1

    fixture = FixtureTransport(fixture_pdfs(monkeypatch))
    original_get = fixture.get
    get_calls = 0

    def redirecting_get(url: str, headers: sentinel.HeaderPairs) -> tuple[int, object, bytes, str]:
        nonlocal get_calls
        get_calls += 1
        response = original_get(url, headers)
        if get_calls == 1:
            return 500, response[1], response[2], "https://example.com/redirected.pdf"
        return response

    with pytest.raises(_common.AcquisitionError, match="PDF final URL"):
        sentinel.acquire_official_s2_remediation_source_v1(
            output_dir=tmp_path / "pdf-redirect",
            post=fixture.post,
            get=redirecting_get,
            sleep=lambda _: None,
            clock=Clock(),
        )
    assert get_calls == 1


def test_retries_are_deterministic_transport_errors_are_redacted_and_statuses_fail_immediately(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdfs = fixture_pdfs(monkeypatch)
    transport = FixtureTransport(pdfs)
    transport.post_statuses = [500, 429, 200]
    receipt, _, _, sleeps = acquire(tmp_path, monkeypatch, transport=transport)
    assert sleeps == [1.0, 2.0]
    assert receipt["logical_requests"][0]["attempts"] == 3

    fixture = FixtureTransport(fixture_pdfs(monkeypatch))
    fixture.post_statuses = [404]
    with pytest.raises(_common.AcquisitionError, match="status"):
        sentinel.acquire_official_s2_remediation_source_v1(output_dir=tmp_path / "status", post=fixture.post, get=fixture.get, sleep=lambda _: pytest.fail("must not retry"), clock=Clock())

    secret = "credential-fixture"
    calls = 0
    def failing_post(*_args: object) -> tuple[int, object, bytes, str]:
        nonlocal calls
        calls += 1
        raise RuntimeError(secret)
    with pytest.raises(_common.AcquisitionError) as caught:
        sentinel.acquire_official_s2_remediation_source_v1(output_dir=tmp_path / "transport", post=failing_post, get=fixture.get, sleep=lambda _: None, clock=Clock())
    assert calls == 3
    assert secret not in str(caught.value)


def test_request_member_total_byte_and_content_length_ceilings_precede_parsing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdfs = fixture_pdfs(monkeypatch)
    transport = FixtureTransport(pdfs)
    original = transport.post
    transport.post = cast(Any, lambda url, form, headers: (200, (), b"x" * (sentinel.MAX_METADATA_MEMBER_BYTES + 1), url))
    with pytest.raises(_common.AcquisitionError, match="ceiling"):
        sentinel.acquire_official_s2_remediation_source_v1(output_dir=tmp_path / "member", post=transport.post, get=transport.get, sleep=lambda _: None, clock=Clock())

    transport.post = cast(Any, lambda url, form, headers: (lambda value: (value[0], (("Content-Length", str(len(value[2]) + 1)),), value[2], value[3]))(original(url, form, headers)))
    with pytest.raises(_common.AcquisitionError, match="Length"):
        sentinel.acquire_official_s2_remediation_source_v1(output_dir=tmp_path / "length", post=transport.post, get=transport.get, sleep=lambda _: None, clock=Clock())

    monkeypatch.setattr(sentinel, "MAX_TOTAL_BYTES", 10)
    with pytest.raises(_common.AcquisitionError, match="ceiling"):
        sentinel.acquire_official_s2_remediation_source_v1(output_dir=tmp_path / "total", post=original, get=transport.get, sleep=lambda _: None, clock=Clock())

    monkeypatch.setattr(sentinel, "MAX_LOGICAL_REQUESTS", 21)
    with pytest.raises(_common.AcquisitionError, match="request ceiling"):
        sentinel.acquire_official_s2_remediation_source_v1(output_dir=tmp_path / "requests", post=original, get=transport.get, sleep=lambda _: None, clock=Clock())
    assert not any((tmp_path / name).exists() for name in ("member", "length", "total", "requests"))


def test_read_bounded_rejects_invalid_declared_lengths_and_reads_only_ceiling_plus_one() -> None:
    class Response:
        def __init__(self, headers: object, source: bytes) -> None:
            self.headers = headers
            self.source = source
            self.offset = 0
            self.amounts: list[int] = []
        def read(self, amount: int = -1) -> bytes:
            self.amounts.append(amount)
            chunk = self.source[self.offset:self.offset + amount]
            self.offset += len(chunk)
            return chunk

    for value in ("-1", "x", "1.0", ""):
        with pytest.raises(_common.AcquisitionError, match="Length"):
            sentinel._read_bounded(Response((("Content-Length", value),), b""), 10, 10)
    response = Response((), b"123456")
    with pytest.raises(_common.AcquisitionError, match="ceiling"):
        sentinel._read_bounded(response, 5, 10)
    assert sum(response.amounts) <= 6


def test_output_collision_symlink_nonregular_clock_snapshot_and_publication_failures_are_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdfs = fixture_pdfs(monkeypatch)
    fixture = FixtureTransport(pdfs)
    existing = tmp_path / "existing"
    existing.mkdir()
    symlink = tmp_path / "symlink"
    symlink.symlink_to(existing, target_is_directory=True)
    nonregular_parent = tmp_path / "file"
    nonregular_parent.write_text("x")
    real_parent = tmp_path / "real-parent"
    (real_parent / "existing-child").mkdir(parents=True)
    nested_symlink = tmp_path / "nested-symlink"
    nested_symlink.symlink_to(real_parent, target_is_directory=True)
    for output in (
        existing,
        symlink,
        nonregular_parent / "capture",
        nested_symlink / "existing-child" / "capture",
    ):
        with pytest.raises(_common.AcquisitionError, match="output"):
            sentinel.acquire_official_s2_remediation_source_v1(output_dir=output, post=fixture.post, get=fixture.get, sleep=lambda _: None, clock=Clock())
    assert fixture.calls == []

    for clock in (lambda: True, lambda: -1, lambda: (_ for _ in ()).throw(RuntimeError("secret"))):
        with pytest.raises(_common.AcquisitionError, match="clock"):
            sentinel.acquire_official_s2_remediation_source_v1(output_dir=tmp_path / f"clock-{id(clock)}", post=fixture.post, get=fixture.get, sleep=lambda _: None, clock=clock)

    monkeypatch.setattr(sentinel, "verify_source_snapshot", lambda _: SimpleNamespace(failure=object()))
    with pytest.raises(_common.AcquisitionError, match="verification"):
        sentinel.acquire_official_s2_remediation_source_v1(output_dir=tmp_path / "snapshot", post=fixture.post, get=fixture.get, sleep=lambda _: None, clock=Clock())
    monkeypatch.undo()

    fixture = FixtureTransport(fixture_pdfs(monkeypatch))
    real_fsync = _common.os.fsync
    called = False
    def fail_once(descriptor: int) -> None:
        nonlocal called
        if not called:
            called = True
            raise OSError("fixture")
        real_fsync(descriptor)
    monkeypatch.setattr(_common.os, "fsync", fail_once)
    with pytest.raises(_common.AcquisitionError, match="publication"):
        sentinel.acquire_official_s2_remediation_source_v1(output_dir=tmp_path / "publication", post=fixture.post, get=fixture.get, sleep=lambda _: None, clock=Clock())
    assert not (tmp_path / "publication").exists()


def test_acquisition_does_not_read_environment_credentials_and_cli_uses_stdlib(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    original_environment = dict(sentinel.os.environ)
    forbidden_keys = {
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
        "http_proxy", "https_proxy", "all_proxy", "no_proxy",
        "TUSHARE_PROXY_TOKEN", "TUSHARE_TOKEN", "XIAODEFA_TOKEN",
    }

    class ForbiddenEnvironment(dict[str, str]):
        def __getitem__(self, key: str) -> str:
            if key in forbidden_keys:
                raise AssertionError(key)
            return dict.__getitem__(self, key)
        def get(self, key: str, default: object = None) -> object:
            if key in forbidden_keys:
                raise AssertionError(key)
            return dict.get(self, key, default)
    monkeypatch.setattr(
        sentinel.os,
        "environ",
        ForbiddenEnvironment(original_environment),
    )
    monkeypatch.setattr(
        sentinel.urllib.request,
        "getproxies",
        lambda: (_ for _ in ()).throw(AssertionError("proxy environment read")),
    )
    receipt, _, _, _ = acquire(tmp_path, monkeypatch)
    assert receipt["schema_version"] == 1

    captured: dict[str, object] = {}
    def fake_acquire(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"type": "fixture"}
    monkeypatch.setattr(sentinel, "acquire_official_s2_remediation_source_v1", fake_acquire)
    assert sentinel.main(["--output-dir", str(tmp_path / "cli")]) == 0
    assert isinstance(captured["output_dir"], Path)
    assert callable(captured["post"]) and callable(captured["get"])
    assert captured["sleep"] is sentinel.time.sleep
    assert captured["clock"] is sentinel.time.time_ns
    assert '"type": "fixture"' in capsys.readouterr().out


def test_receipt_contains_no_declaration_statement_strategy_or_deployment_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt, _, output, _ = acquire(tmp_path, monkeypatch)
    text = json.dumps(receipt, ensure_ascii=False)
    for forbidden in ("FinancialStatement(", "NonfilingDeclaration(", "Strategy", "Target", "Execution", "Promotion"):
        assert forbidden not in text
    assert not any(
        any(name in path.name for name in ("declaration", "statement", "strategy", "deployment"))
        for path in output.rglob("*")
    )
    assert receipt["deployment_authorized"] is False
