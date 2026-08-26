from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from crypto_quant_bundle_builder import RawSourceMember, SourceSnapshotProvenance, freeze_source_snapshot
from tools.acquisition import _common
from tools.acquisition import cn_a_share_official_s2_remediation_supplement_source_bounded_v1 as sentinel

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
EXPECTED_NEEQ_HEADERS = (
    ("Accept", "application/json,*/*"),
    ("Referer", "https://neeq.cs.com.cn/"),
    ("User-Agent", "Mozilla/5.0"),
)
EXPECTED_PDF_HEADERS = (
    ("Accept", "application/pdf,*/*"),
    ("Referer", "https://www.cninfo.com.cn/"),
    ("User-Agent", "Mozilla/5.0"),
)
EXPECTED_METADATA = (
    ("000038-predeadline", "000038,gssz0000038", "2023-04-25~2023-04-30", 3, "1216706117"),
    ("000976-predeadline", "000976,gssz0000976", "2024-04-20~2024-04-30", 10, "1219960138"),
)
EXPECTED_CNINFO_FACTS = (
    ("1216706117", "关于无法在法定期限内披露定期报告致股票可能被终止上市暨停牌的风险提示公告", 1682701857000, "finalpage/2023-04-29/1216706117.PDF"),
    ("1219960138", "关于无法在法定期限内披露定期报告暨股票停牌的公告", 1714474662000, "finalpage/2024-04-30/1219960138.PDF"),
)
EXPECTED_NEEQ_FACT = (
    "400267",
    "R鑫升1",
    "2026-04-29T00:00:00.000+00:00",
    "[券商公告]R鑫升1:中泰证券股份有限公司关于山东鑫升矿业股份有限公司无法披露2025年年度报告的风险提示性公告",
    "http://dataclouds.cninfo.com.cn/sjother2/neeqs/2026/20260429/5e69266176024a6dae6eb9392c5e22b5.pdf",
    "PDF",
)
EXPECTED_NEEQ_URL = "https://neeq.cs.com.cn/xsb/v1/xsb_search/&gs=R%E9%91%AB%E5%8D%871&st=2026-04-01&ed=2026-05-10&1.json"
EXPECTED_PDFS = (
    ("response/official/000038/1216706117.pdf", "https://static.cninfo.com.cn/finalpage/2023-04-29/1216706117.PDF", 132535, "sha256:221bbba784c88dbe6deec97085033de38419fa78f5d6a9b08c2fa2f13bb55bab"),
    ("response/official/000976/1219960138.pdf", "https://static.cninfo.com.cn/finalpage/2024-04-30/1219960138.PDF", 202749, "sha256:e57fa6e99f452b8e1eb59f0be39b44cfebbfc7775dd050f1050d754b190d1aec"),
    ("response/official/601028/5e69266176024a6dae6eb9392c5e22b5.pdf", "https://dataclouds.cninfo.com.cn/sjother2/neeqs/2026/20260429/5e69266176024a6dae6eb9392c5e22b5.pdf", 124766, "sha256:a00a87a6b4e96e93c04d02bc3816fbe9b0488744fca65a53d3603bf509eaa464"),
)
EXPECTED_LIMITATIONS = (
    "SOURCE_BOUNDED_ONLY", "OFFICIAL_EVIDENCE_NOT_REVIEWED_BY_BUILDER",
    "NONFILING_DECLARATIONS_NOT_CONSTRUCTED", "FINANCIAL_AVAILABILITY_NOT_QUALIFIED",
    "REVISION_CLOSURE_INCOMPLETE", "S2B_EXACT_COVER_FALSE", "DECISION_GRADE_FALSE",
    "DEPLOYMENT_AUTHORIZED_FALSE",
)
EXPECTED_FALSE_FLAGS = (
    "official_evidence_reviewed", "nonfiling_declarations_constructed",
    "financial_availability_qualified", "revision_closure_complete",
    "s2b_exact_cover_complete", "decision_grade_eligible", "deployment_authorized",
)


def cninfo_bytes(request: sentinel.MetadataRequest, mutation: Callable[[dict[str, Any]], None] | None = None) -> bytes:
    fact = dict((item[0], item) for item in EXPECTED_CNINFO_FACTS)[request.selected_id]
    records: list[dict[str, object]] = [{
        "announcementId": request.selected_id,
        "announcementTitle": f"<em>{fact[1]}</em>",
        "announcementTime": fact[2],
        "adjunctUrl": fact[3],
        "retainedExtraField": "raw-source",
    }]
    records.extend({"announcementId": f"extra-{request.key}-{index}"} for index in range(request.expected_total - 1))
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


def neeq_bytes(mutation: Callable[[dict[str, Any]], None] | None = None) -> bytes:
    row = dict(zip(("seccode", "secname", "f001d", "f002v", "f003v", "f004v"), EXPECTED_NEEQ_FACT, strict=True))
    row["retainedExtraField"] = "raw-source"
    rows = [
        row,
        *(
            {
                "seccode": "400267",
                "secname": "R鑫升1",
                "f003v": f"http://example.invalid/extra-{index}.pdf",
                "retainedExtraField": "raw-source-extra",
            }
            for index in range(26)
        ),
    ]
    payload: dict[str, Any] = {
        "code": 0,
        "errorMessage": None,
        "data": {
            "code": 0,
            "errorMessage": None,
            "data": rows,
            "currentPage": 1,
            "size": 30,
            "total": 27,
        },
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
        self.cninfo_mutation: Callable[[dict[str, Any]], None] | None = None
        self.neeq_mutation: Callable[[dict[str, Any]], None] | None = None
        self.post_final_url: str | None = None
        self.get_final_url: str | None = None
        self.pdf_headers: object = (("Content-Type", "application/pdf"), ("Server", "fixture"))
        self.pdf_mutation: Callable[[bytes], bytes] | None = None

    def post(self, url: str, form: sentinel.FormPairs, headers: sentinel.HeaderPairs) -> tuple[int, object, bytes, str]:
        self.calls.append(("POST", url, (form, headers)))
        request = next(item for item in sentinel._METADATA_REQUESTS if item.form == form)
        status = self.post_statuses.pop(0) if self.post_statuses else 200
        return status, (("Content-Type", "application/json;charset=UTF-8"), ("Date", "ignored")), cninfo_bytes(request, self.cninfo_mutation), self.post_final_url or url

    def get(self, url: str, headers: sentinel.HeaderPairs) -> tuple[int, object, bytes, str]:
        self.calls.append(("GET", url, headers))
        status = self.get_statuses.pop(0) if self.get_statuses else 200
        if url == sentinel._NEEQ_REQUEST.url:
            source = neeq_bytes(self.neeq_mutation)
            response_headers: object = (("Content-Type", "application/json"),)
        else:
            source = self.pdfs[url]
            if self.pdf_mutation:
                source = self.pdf_mutation(source)
            response_headers = self.pdf_headers
        return status, response_headers, source, self.get_final_url or url


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
    receipt = sentinel.acquire_official_s2_remediation_supplement_source_v1(
        output_dir=output,
        post=fixture.post,
        get=fixture.get,
        sleep=sleep or sleeps.append,
        clock=clock or Clock(),
    )
    return cast(dict[str, Any], receipt), fixture, output, sleeps


def test_frozen_requests_facts_headers_pdfs_ceilings_and_provenance_are_literal() -> None:
    assert sentinel._FORM_KEYS == EXPECTED_FORM_KEYS
    assert sentinel._CNINFO_POST_HEADERS == EXPECTED_POST_HEADERS
    assert sentinel._NEEQ_HEADERS == EXPECTED_NEEQ_HEADERS
    assert sentinel._CNINFO_PDF_HEADERS == EXPECTED_PDF_HEADERS
    assert tuple((r.key, r.stock, r.se_date, r.expected_total, r.selected_id) for r in sentinel._METADATA_REQUESTS) == EXPECTED_METADATA
    assert tuple(request.form for request in sentinel._METADATA_REQUESTS) == tuple(
        (("pageNum", "1"), ("pageSize", "30"), ("column", "szse"), ("tabName", "fulltext"),
         ("plate", "sz"), ("stock", stock), ("searchkey", ""), ("secid", ""),
         ("category", ""), ("trade", ""), ("seDate", se_date), ("sortName", ""),
         ("sortType", ""), ("isHLtitle", "true"))
        for _key, stock, se_date, _total, _selected in EXPECTED_METADATA
    )
    assert sentinel._SELECTED_CNINFO_FACTS == EXPECTED_CNINFO_FACTS
    assert sentinel._SELECTED_NEEQ_FACT == EXPECTED_NEEQ_FACT
    assert (sentinel._NEEQ_REQUEST.key, sentinel._NEEQ_REQUEST.member_key, sentinel._NEEQ_REQUEST.url, sentinel._NEEQ_REQUEST.headers) == (
        "400267-202604", "response/neeq/disclosure-search/400267-202604-v1.json", EXPECTED_NEEQ_URL, EXPECTED_NEEQ_HEADERS,
    )
    assert tuple((r.member_key, r.url, r.byte_count, r.content_hash) for r in sentinel._PDF_REQUESTS) == EXPECTED_PDFS
    assert all(request.headers == EXPECTED_PDF_HEADERS for request in sentinel._PDF_REQUESTS)
    assert (sentinel.MAX_LOGICAL_REQUESTS, sentinel.MAX_METADATA_MEMBER_BYTES, sentinel.MAX_PDF_MEMBER_BYTES, sentinel.MAX_TOTAL_BYTES) == (6, 1 << 20, 1 << 20, 4 << 20)
    assert sentinel._LIMITATIONS == EXPECTED_LIMITATIONS
    assert sentinel._FALSE_FLAGS == EXPECTED_FALSE_FLAGS


def test_success_receipt_order_layout_snapshot_and_reconstruction_are_exact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt, transport, output, sleeps = acquire(tmp_path, monkeypatch)
    assert sleeps == []
    assert [(method, url) for method, url, _ in transport.calls] == [
        ("POST", sentinel._METADATA_ENDPOINT),
        ("POST", sentinel._METADATA_ENDPOINT),
        ("GET", EXPECTED_NEEQ_URL),
        *(("GET", request.url) for request in sentinel._PDF_REQUESTS),
    ]
    requests = receipt["logical_requests"]
    assert [item["logical_index"] for item in requests] == list(range(6))
    assert [item["request_kind"] for item in requests] == ["cninfo_metadata_post", "cninfo_metadata_post", "neeq_metadata_get", "pdf_get", "pdf_get", "pdf_get"]
    assert [item["member_key"] for item in requests] == [
        *(request.member_key for request in sentinel._METADATA_REQUESTS),
        sentinel._NEEQ_REQUEST.member_key,
        *(request.member_key for request in sentinel._PDF_REQUESTS),
    ]
    request_keys = {
        "logical_index", "request_kind", "request_key", "member_key", "url",
        "ordered_form", "ordered_headers", "attempts", "status", "final_url",
        "response_headers", "response_sha256", "response_byte_count",
        "response_received_at_epoch_nanoseconds",
    }
    assert all(set(item) == request_keys for item in requests)
    assert all(item["ordered_form"] is not None for item in requests[:2])
    assert all(item["ordered_form"] is None for item in requests[2:])
    assert all(item["ordered_headers"] == [list(pair) for pair in EXPECTED_PDF_HEADERS] for item in requests[3:])
    assert receipt["metadata_extra_record_count"] == 37
    assert tuple((item["announcement_id"], item["title"], item["announcement_time_epoch_milliseconds"], item["adjunct_url"]) for item in receipt["selected_cninfo_facts"]) == EXPECTED_CNINFO_FACTS
    assert receipt["selected_neeq_fact"] == {
        "seccode": EXPECTED_NEEQ_FACT[0],
        "secname": EXPECTED_NEEQ_FACT[1],
        "published_at": EXPECTED_NEEQ_FACT[2],
        "title": EXPECTED_NEEQ_FACT[3],
        "metadata_pdf_url": EXPECTED_NEEQ_FACT[4],
        "retained_pdf_url": EXPECTED_PDFS[-1][1],
    }
    assert set(receipt) == {
        "type", "schema_version", "capture_key", "acquired_at_epoch_nanoseconds",
        "logical_requests", "selected_cninfo_facts", "selected_neeq_fact",
        "metadata_extra_record_count", "snapshot", "limitations", *EXPECTED_FALSE_FLAGS,
    }
    assert receipt["type"] == "official_s2_remediation_supplement_source_receipt"
    assert receipt["schema_version"] == 1
    assert receipt["capture_key"] == "20260826-official-s2-remediation-supplement-candidate-01"
    assert receipt["acquired_at_epoch_nanoseconds"] == 1006
    assert receipt["limitations"] == list(EXPECTED_LIMITATIONS)
    assert all(receipt[flag] is False for flag in EXPECTED_FALSE_FLAGS)
    assert receipt["snapshot"]["provenance"] == {
        "vendor_key": "cninfo.com.cn-neeq.cs.com.cn",
        "source_key": "official.s2-remediation.nonfiling-effective-boundary-supplement.v1",
        "license_ref": "official.public-disclosure",
        "retention_policy_ref": "backtest.acquisition.candidate",
    }

    regular = [path for path in output.rglob("*") if path.is_file()]
    assert len(regular) == 8
    assert {path.relative_to(output).as_posix() for path in regular} == {
        *(item["member_key"] for item in requests), "source-snapshot.json", "acquisition-receipt.json",
    }
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in regular)
    assert (output / "acquisition-receipt.json").read_bytes() == _common.json_bytes(receipt)
    assert (output / "source-snapshot.json").read_bytes() == _common.json_bytes(receipt["snapshot"])
    files = {item["member_key"]: (output / item["member_key"]).read_bytes() for item in requests}
    for request in sentinel._METADATA_REQUESTS:
        assert files[request.member_key] == cninfo_bytes(request)
    assert files[sentinel._NEEQ_REQUEST.member_key] == neeq_bytes()
    assert [item["response_headers"] for item in requests] == [
        [["Content-Type", "application/json;charset=UTF-8"]],
        [["Content-Type", "application/json;charset=UTF-8"]],
        [["Content-Type", "application/json"]],
        [["Content-Type", "application/pdf"]],
        [["Content-Type", "application/pdf"]],
        [["Content-Type", "application/pdf"]],
    ]
    snapshot_members = {item["member_key"]: item for item in receipt["snapshot"]["members"]}
    assert list(snapshot_members) == sorted(files)
    for item in requests:
        raw = files[item["member_key"]]
        content_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
        assert item["response_sha256"] == content_hash
        assert item["response_byte_count"] == len(raw)
        assert snapshot_members[item["member_key"]]["mode"] == "0644"
        assert snapshot_members[item["member_key"]]["content_hash"] == content_hash
    timestamps = {item["member_key"]: item["response_received_at_epoch_nanoseconds"] for item in requests}
    rebuilt = freeze_source_snapshot(
        members=tuple(RawSourceMember(key, value, "0644", timestamps[key], None) for key, value in files.items()),
        provenance=SourceSnapshotProvenance(**receipt["snapshot"]["provenance"]),
    )
    assert rebuilt.snapshot is not None
    assert rebuilt.snapshot.to_canonical_dict() == receipt["snapshot"]


@pytest.mark.parametrize("failure", ["missing", "duplicate", "title", "time", "url", "total", "has-more", "keys", "duplicate-key"])
def test_cninfo_scope_failures_publish_nothing(failure: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = FixtureTransport(fixture_pdfs(monkeypatch))

    def mutate(payload: dict[str, Any]) -> None:
        record = payload["announcements"][0]
        if failure == "missing":
            record["announcementId"] = "missing"
        elif failure == "duplicate":
            payload["announcements"][1] = dict(record)
        elif failure == "title":
            record["announcementTitle"] = "wrong"
        elif failure == "time":
            record["announcementTime"] = 0
        elif failure == "url":
            record["adjunctUrl"] = "wrong"
        elif failure == "total":
            payload["totalRecordNum"] += 1
        elif failure == "has-more":
            payload["hasMore"] = True
        elif failure == "keys":
            payload["unexpected"] = False

    fixture.cninfo_mutation = mutate
    if failure == "duplicate-key":
        original = fixture.post
        fixture.post = cast(Any, lambda url, form, headers: (lambda value: (value[0], value[1], value[2].replace(b'"hasMore":false', b'"hasMore":false,"hasMore":false'), value[3]))(original(url, form, headers)))
    with pytest.raises(_common.AcquisitionError):
        sentinel.acquire_official_s2_remediation_supplement_source_v1(output_dir=tmp_path / "capture", post=fixture.post, get=fixture.get, sleep=lambda _: None, clock=Clock())
    assert not (tmp_path / "capture").exists()


@pytest.mark.parametrize("failure", ["outer-code", "inner-code", "page", "size", "total", "rows", "missing", "duplicate", "secname", "date", "title", "scheme", "host", "path", "query", "fragment", "format", "keys", "duplicate-key"])
def test_neeq_envelope_selected_fact_and_pdf_binding_failures_are_atomic(failure: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = FixtureTransport(fixture_pdfs(monkeypatch))

    def mutate(payload: dict[str, Any]) -> None:
        inner = payload["data"]
        row = inner["data"][0]
        if failure == "outer-code":
            payload["code"] = 1
        elif failure == "inner-code":
            inner["code"] = 1
        elif failure == "page":
            inner["currentPage"] = 2
        elif failure == "size":
            inner["size"] = 20
        elif failure == "total":
            inner["total"] = 28
        elif failure == "rows":
            inner["data"].pop()
        elif failure == "missing":
            row["seccode"] = "missing"
        elif failure == "duplicate":
            inner["data"][1] = dict(row)
        elif failure == "secname":
            row["secname"] = "wrong"
        elif failure == "date":
            row["f001d"] = "wrong"
        elif failure == "title":
            row["f002v"] = "wrong"
        elif failure == "scheme":
            row["f003v"] = row["f003v"].replace("http://", "https://")
        elif failure == "host":
            row["f003v"] = row["f003v"].replace("dataclouds.cninfo.com.cn", "example.com")
        elif failure == "path":
            row["f003v"] = row["f003v"].replace("5e692661", "deadbeef")
        elif failure == "query":
            row["f003v"] += "?x=1"
        elif failure == "fragment":
            row["f003v"] += "#x"
        elif failure == "format":
            row["f004v"] = "HTML"
        elif failure == "keys":
            inner["unexpected"] = False

    fixture.neeq_mutation = mutate
    if failure == "duplicate-key":
        original = fixture.get
        fixture.get = cast(Any, lambda url, headers: (lambda value: (value[0], value[1], value[2].replace(b'"currentPage":1', b'"currentPage":1,"currentPage":1'), value[3]))(original(url, headers)))
    with pytest.raises(_common.AcquisitionError):
        sentinel.acquire_official_s2_remediation_supplement_source_v1(output_dir=tmp_path / "capture", post=fixture.post, get=fixture.get, sleep=lambda _: None, clock=Clock())
    assert not (tmp_path / "capture").exists()


@pytest.mark.parametrize("failure", ["redirect", "content-type", "magic", "size", "hash", "not-allowed"])
def test_pdf_boundary_failures_are_atomic(failure: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = FixtureTransport(fixture_pdfs(monkeypatch))
    if failure == "redirect":
        original = fixture.get
        fixture.get = cast(Any, lambda url, headers: (lambda value: value if url == sentinel._NEEQ_REQUEST.url else (value[0], value[1], value[2], "https://example.com/redirected.pdf"))(original(url, headers)))
    elif failure == "content-type":
        fixture.pdf_headers = (("Content-Type", "text/html"),)
    elif failure == "magic":
        fixture.pdf_mutation = lambda source: b"!" + source[1:]
    elif failure == "size":
        fixture.pdf_mutation = lambda source: source + b"x"
    elif failure == "hash":
        fixture.pdf_mutation = lambda source: source[:-1] + bytes([source[-1] ^ 1])
    else:
        first = sentinel._PDF_REQUESTS[0]
        monkeypatch.setattr(sentinel, "_PDF_REQUESTS", (sentinel.PdfRequest(first.member_key, "https://example.com/not-allowed.pdf", first.byte_count, first.content_hash), *sentinel._PDF_REQUESTS[1:]))
    with pytest.raises(_common.AcquisitionError):
        sentinel.acquire_official_s2_remediation_supplement_source_v1(output_dir=tmp_path / "capture", post=fixture.post, get=fixture.get, sleep=lambda _: None, clock=Clock())
    assert not (tmp_path / "capture").exists()


def test_local_allowlists_headers_forms_and_redirects_fail_before_transport_or_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    request = sentinel._METADATA_REQUESTS[0]
    with pytest.raises(_common.AcquisitionError, match="not allowed"):
        sentinel._post_with_retries(sentinel._METADATA_ENDPOINT, tuple(reversed(request.form)), EXPECTED_POST_HEADERS, lambda *_: pytest.fail("must not run"), lambda _: None, total_remaining=sentinel.MAX_TOTAL_BYTES)
    with pytest.raises(_common.AcquisitionError, match="not allowed"):
        sentinel._post_with_retries(sentinel._METADATA_ENDPOINT, request.form, (*EXPECTED_POST_HEADERS, ("Authorization", "secret")), lambda *_: pytest.fail("must not run"), lambda _: None, total_remaining=sentinel.MAX_TOTAL_BYTES)
    with pytest.raises(_common.AcquisitionError, match="not allowed"):
        sentinel._get_with_retries(EXPECTED_NEEQ_URL, EXPECTED_PDF_HEADERS, lambda *_: pytest.fail("must not run"), lambda _: None, member_limit=sentinel.MAX_METADATA_MEMBER_BYTES, total_remaining=sentinel.MAX_TOTAL_BYTES)
    with pytest.raises(_common.AcquisitionError, match="not allowed"):
        sentinel._get_with_retries(EXPECTED_PDFS[0][1], EXPECTED_PDF_HEADERS, lambda *_: pytest.fail("must not run"), lambda _: None, member_limit=sentinel.MAX_METADATA_MEMBER_BYTES + 1, total_remaining=sentinel.MAX_TOTAL_BYTES)

    calls = 0
    def redirecting_get(url: str, headers: sentinel.HeaderPairs) -> tuple[int, object, bytes, str]:
        nonlocal calls
        calls += 1
        return 500, (), b"", "https://example.com/redirected"
    with pytest.raises(_common.AcquisitionError, match="final URL"):
        sentinel._get_with_retries(EXPECTED_NEEQ_URL, EXPECTED_NEEQ_HEADERS, redirecting_get, lambda _: pytest.fail("must not retry"), member_limit=sentinel.MAX_METADATA_MEMBER_BYTES, total_remaining=sentinel.MAX_TOTAL_BYTES)
    assert calls == 1


def test_retries_statuses_transport_redaction_and_byte_ceilings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = FixtureTransport(fixture_pdfs(monkeypatch))
    fixture.post_statuses = [500, 429, 200]
    receipt, _, _, sleeps = acquire(tmp_path, monkeypatch, transport=fixture)
    assert sleeps == [1.0, 2.0]
    assert receipt["logical_requests"][0]["attempts"] == 3

    fixture = FixtureTransport(fixture_pdfs(monkeypatch))
    fixture.get_statuses = [503, 200]
    receipt, _, _, sleeps = acquire(tmp_path / "get", monkeypatch, transport=fixture)
    assert sleeps == [1.0]
    assert receipt["logical_requests"][2]["attempts"] == 2

    fixture = FixtureTransport(fixture_pdfs(monkeypatch))
    fixture.post_statuses = [404]
    with pytest.raises(_common.AcquisitionError, match="status"):
        sentinel.acquire_official_s2_remediation_supplement_source_v1(output_dir=tmp_path / "status", post=fixture.post, get=fixture.get, sleep=lambda _: pytest.fail("must not retry"), clock=Clock())

    calls = 0
    def failing_post(*_args: object) -> tuple[int, object, bytes, str]:
        nonlocal calls
        calls += 1
        raise RuntimeError("credential-fixture")
    with pytest.raises(_common.AcquisitionError) as caught:
        sentinel.acquire_official_s2_remediation_supplement_source_v1(output_dir=tmp_path / "transport", post=failing_post, get=fixture.get, sleep=lambda _: None, clock=Clock())
    assert calls == 3
    assert "credential-fixture" not in str(caught.value)

    fixture = FixtureTransport(fixture_pdfs(monkeypatch))
    fixture.post = cast(Any, lambda url, form, headers: (200, (), b"x" * (sentinel.MAX_METADATA_MEMBER_BYTES + 1), url))
    with pytest.raises(_common.AcquisitionError, match="ceiling"):
        sentinel.acquire_official_s2_remediation_supplement_source_v1(output_dir=tmp_path / "member", post=fixture.post, get=fixture.get, sleep=lambda _: None, clock=Clock())

    fixture = FixtureTransport(fixture_pdfs(monkeypatch))
    original = fixture.post
    fixture.post = cast(Any, lambda url, form, headers: (lambda value: (value[0], (("Content-Length", str(len(value[2]) + 1)),), value[2], value[3]))(original(url, form, headers)))
    with pytest.raises(_common.AcquisitionError, match="Length"):
        sentinel.acquire_official_s2_remediation_supplement_source_v1(output_dir=tmp_path / "length", post=fixture.post, get=fixture.get, sleep=lambda _: None, clock=Clock())

    monkeypatch.setattr(sentinel, "MAX_TOTAL_BYTES", 10)
    with pytest.raises(_common.AcquisitionError, match="ceiling"):
        sentinel.acquire_official_s2_remediation_supplement_source_v1(output_dir=tmp_path / "total", post=original, get=fixture.get, sleep=lambda _: None, clock=Clock())


def test_reused_bounded_reader_prechecks_lengths_and_reads_only_ceiling_plus_one() -> None:
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


def test_output_clock_snapshot_publication_and_layout_failures_are_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = FixtureTransport(fixture_pdfs(monkeypatch))
    existing = tmp_path / "existing"
    existing.mkdir()
    symlink = tmp_path / "symlink"
    symlink.symlink_to(existing, target_is_directory=True)
    for output in (existing, symlink):
        with pytest.raises(_common.AcquisitionError, match="output"):
            sentinel.acquire_official_s2_remediation_supplement_source_v1(output_dir=output, post=fixture.post, get=fixture.get, sleep=lambda _: None, clock=Clock())
    assert fixture.calls == []

    for clock in (lambda: True, lambda: -1, lambda: (_ for _ in ()).throw(RuntimeError("secret"))):
        with pytest.raises(_common.AcquisitionError, match="clock"):
            sentinel.acquire_official_s2_remediation_supplement_source_v1(output_dir=tmp_path / f"clock-{id(clock)}", post=fixture.post, get=fixture.get, sleep=lambda _: None, clock=clock)

    monkeypatch.setattr(sentinel, "verify_source_snapshot", lambda _: SimpleNamespace(failure=object()))
    with pytest.raises(_common.AcquisitionError, match="verification"):
        sentinel.acquire_official_s2_remediation_supplement_source_v1(output_dir=tmp_path / "snapshot", post=fixture.post, get=fixture.get, sleep=lambda _: None, clock=Clock())
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
        sentinel.acquire_official_s2_remediation_supplement_source_v1(output_dir=tmp_path / "publication", post=fixture.post, get=fixture.get, sleep=lambda _: None, clock=Clock())
    assert not (tmp_path / "publication").exists()

    monkeypatch.undo()
    fixture = FixtureTransport(fixture_pdfs(monkeypatch))
    monkeypatch.setattr(sentinel, "_PDF_REQUESTS", sentinel._PDF_REQUESTS[:-1])
    with pytest.raises(_common.AcquisitionError, match="request ceiling"):
        sentinel.acquire_official_s2_remediation_supplement_source_v1(output_dir=tmp_path / "layout", post=fixture.post, get=fixture.get, sleep=lambda _: None, clock=Clock())


def test_no_credentials_proxy_environment_or_authoritative_outputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    original_environment = dict(sentinel.sys.modules["os"].environ)
    forbidden_keys = {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy", "TUSHARE_PROXY_TOKEN", "TUSHARE_TOKEN", "XIAODEFA_TOKEN"}

    class ForbiddenEnvironment(dict[str, str]):
        def __getitem__(self, key: str) -> str:
            if key in forbidden_keys:
                raise AssertionError(key)
            return dict.__getitem__(self, key)

        def get(self, key: str, default: object = None) -> object:
            if key in forbidden_keys:
                raise AssertionError(key)
            return dict.get(self, key, default)

    monkeypatch.setattr(sentinel.sys.modules["os"], "environ", ForbiddenEnvironment(original_environment))
    monkeypatch.setattr(sentinel.urllib.request, "getproxies", lambda: (_ for _ in ()).throw(AssertionError("proxy environment read")))
    receipt, _, output, _ = acquire(tmp_path, monkeypatch)
    text = json.dumps(receipt, ensure_ascii=False)
    for forbidden in ("FinancialStatement(", "NonfilingDeclaration(", "Strategy", "Target", "Execution", "Promotion"):
        assert forbidden not in text
    assert not any(any(name in path.name for name in ("declaration", "statement", "strategy", "deployment")) for path in output.rglob("*"))

    captured: dict[str, object] = {}
    def fake_acquire(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"type": "fixture"}
    monkeypatch.setattr(sentinel, "acquire_official_s2_remediation_supplement_source_v1", fake_acquire)
    assert sentinel.main(["--output-dir", str(tmp_path / "cli")]) == 0
    assert isinstance(captured["output_dir"], Path)
    assert callable(captured["post"]) and callable(captured["get"])
    assert captured["sleep"] is sentinel.time.sleep
    assert captured["clock"] is sentinel.time.time_ns
    assert '"type": "fixture"' in capsys.readouterr().out
