from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotFailureCode,
    freeze_source_snapshot,
    verify_source_snapshot,
)

from tools.acquisition import _common
from tools.acquisition import cn_a_share_tushare_financial_history_sentinel_v3 as sentinel

TOKEN = "p" * 56


def provider_response(fields: tuple[str, ...], rows: list[list[object]]) -> bytes:
    return json.dumps(
        {
            "request_id": "v3-request-id",
            "code": 0,
            "data": {
                "fields": list(fields),
                "items": rows,
                "has_more": False,
                "count": 0,
            },
            "msg": "",
            "detail": "",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


def provider_row(
    fields: tuple[str, ...], period: str, ann_date: str, update_flag: str
) -> list[object]:
    values: dict[str, object] = {
        "ts_code": "000651.SZ",
        "ann_date": ann_date,
        "f_ann_date": ann_date,
        "end_date": period,
        "report_type": "1",
        "comp_type": "1",
        "update_flag": update_flag,
    }
    return [values.get(field, 1 if update_flag == "0" else 2.0) for field in fields]


def announcement(
    period: str, announcement_id: str, announcement_time: int, adjunct_url: str
) -> dict[str, object]:
    record: dict[str, object] = {
        name: None for name in sentinel._ANNOUNCEMENT_KEYS
    }
    record.update(
        {
            "id": int(announcement_id),
            "secCode": "000651",
            "secName": "格力电器",
            "orgId": "gssz0000651",
            "announcementId": announcement_id,
            "announcementTitle": f"<em>{period[:4]}</em>年年度报告",
            "announcementTime": announcement_time,
            "adjunctUrl": adjunct_url,
            "adjunctSize": 123,
            "adjunctType": "PDF",
            "secNameList": ["格力电器"],
        }
    )
    return record


def metadata_bytes() -> bytes:
    records = [announcement(*fact) for fact in sentinel._METADATA_FACTS]
    records.append(
        {
            **announcement(
                "20221231",
                "9999999999",
                1_682_697_600_000,
                "finalpage/2023-04-29/9999999999.PDF",
            ),
            "announcementTitle": "2022年年度报告摘要",
        }
    )
    return json.dumps(
        {
            "announcements": records,
            "categoryList": None,
            "classifiedAnnouncements": None,
            "hasMore": False,
            "totalAnnouncement": len(records),
            "totalRecordNum": len(records),
            "totalSecurities": 0,
            "totalpages": 1,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


class FakeProxyPost:
    def __init__(
        self,
        mutate: Callable[[dict[str, object], bytes], bytes] | None = None,
        statuses: list[int] | None = None,
    ) -> None:
        self.mutate = mutate
        self.statuses = list(statuses or [])
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def __call__(
        self, url: str, body: dict[str, object], headers: dict[str, str]
    ) -> tuple[int, bytes]:
        self.calls.append((url, body, headers))
        status = self.statuses.pop(0) if self.statuses else 200
        if status != 200:
            return status, b""
        fields = tuple(str(body["fields"]).split(","))
        params = body["params"]
        assert isinstance(params, dict)
        expected = next(
            item
            for item in sentinel._REQUESTS
            if item[0] == body["api_name"] and item[1] == params["period"]
        )
        flags = expected[5]
        source = provider_response(
            fields,
            [provider_row(fields, expected[1], expected[2], flag) for flag in flags],
        )
        return 200, self.mutate(body, source) if self.mutate else source


class Clock:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> int:
        self.calls += 1
        return 1_900_000_000_000_000_000 + self.calls


def synthetic_documents(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    documents: dict[str, bytes] = {}
    facts = []
    for period, announcement_id, url, member_key, _size, _digest in sentinel._ANNUAL_REPORT_FACTS:
        source = f"%PDF-1.7\n{period}\n".encode()
        documents[url] = source
        facts.append(
            (
                period,
                announcement_id,
                url,
                member_key,
                len(source),
                _common.sha256(source),
            )
        )
    monkeypatch.setattr(sentinel, "_ANNUAL_REPORT_FACTS", tuple(facts))
    return documents


def acquire(
    output: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    proxy_post: sentinel.ProxyPost | None = None,
    cninfo_post: sentinel.CninfoPost | None = None,
    get: sentinel.Get | None = None,
    clock: Clock | None = None,
    sleep: Callable[[float], None] | None = None,
) -> tuple[dict[str, Any], FakeProxyPost, Clock, list[float]]:
    documents = synthetic_documents(monkeypatch)
    proxy = proxy_post if proxy_post is not None else FakeProxyPost()
    timer = clock or Clock()
    sleeps: list[float] = []

    def default_cninfo(
        endpoint: str,
        form: tuple[tuple[str, str], ...],
        headers: dict[str, str],
    ) -> tuple[int, bytes]:
        assert endpoint == sentinel._CNINFO_ENDPOINT
        assert form == sentinel._CNINFO_FORM
        assert headers == dict(sentinel._CNINFO_HEADERS)
        return 200, metadata_bytes()

    receipt = cast(
        dict[str, Any],
        sentinel.acquire_tushare_cn_a_share_financial_history_sentinel_v3(
            sentinel.TushareCnAShareFinancialHistorySentinelRequestV3(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            proxy_post=proxy,
            cninfo_post=cninfo_post or default_cninfo,
            get=get or (lambda url: (200, documents[url], url)),
            time_ns=timer,
            sleep=sleep or sleeps.append,
        ),
    )
    assert isinstance(proxy, FakeProxyPost)
    return receipt, proxy, timer, sleeps


def test_v3_exact_capture_receipt_snapshot_and_wire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "capture"
    writes: list[str] = []
    real_open = sentinel.os.open

    def track_open(
        path: os.PathLike[str] | str,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if flags & os.O_WRONLY:
            writes.append(os.fspath(path))
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(sentinel.os, "open", track_open)
    receipt, proxy, clock, sleeps = acquire(output, monkeypatch)

    assert Path(writes[-1]).name == "acquisition-receipt.json"
    assert len(writes) == 20
    member_paths = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file() and path.name != "acquisition-receipt.json"
    }
    assert len(member_paths) == 19
    assert member_paths == {
        request["member_key"] for request in receipt["provider_requests"]
    } | {sentinel._CNINFO_MEMBER} | {
        document["member_key"] for document in receipt["official_documents"]
    }
    assert clock.calls == 19
    assert sleeps == [0.5] * 12
    assert [call[1]["api_name"] for call in proxy.calls] == [
        request[0] for request in sentinel._REQUESTS
    ]
    assert [call[1]["params"] for call in proxy.calls] == [
        {
            "ts_code": "000651.SZ",
            "comp_type": "1",
            "period": period,
            "ann_date": ann_date,
        }
        for _api, period, ann_date, _fields, _count, _flags in sentinel._REQUESTS
    ]
    assert all(call[2] == sentinel._proxy_headers(TOKEN) for call in proxy.calls)
    assert [item["item_cardinality"] for item in receipt["provider_requests"]] == [
        item[4] for item in sentinel._REQUESTS
    ]
    assert [item["update_flags"] for item in receipt["provider_requests"]] == [
        list(item[5]) for item in sentinel._REQUESTS
    ]
    assert [item["contexts"] for item in receipt["provider_requests"]] == [
        [
            ["000651.SZ", ann_date, ann_date, period, "1", "1", flag]
            for flag in flags
        ]
        for _api, period, ann_date, _fields, _count, flags in sentinel._REQUESTS
    ]
    assert receipt["official_metadata"]["form"] == sentinel._CNINFO_FORM
    assert receipt["official_metadata"]["selected_records"] == [
        {
            "report_period": period,
            "sec_code": "000651",
            "org_id": "gssz0000651",
            "announcement_id": announcement_id,
            "raw_announcement_title": f"<em>{period[:4]}</em>年年度报告",
            "normalized_announcement_title": f"{period[:4]}年年度报告",
            "announcement_time_epoch_milliseconds": announcement_time,
            "adjunct_url": adjunct_url,
            "adjunct_type": "PDF",
        }
        for period, announcement_id, announcement_time, adjunct_url in sentinel._METADATA_FACTS
    ]
    assert receipt["acquired_at_epoch_nanoseconds"] == 1_900_000_000_000_000_019
    assert (output / "acquisition-receipt.json").read_bytes() == _common.json_bytes(receipt)
    assert (output.stat().st_mode & 0o777) == 0o700
    assert all(
        (path.stat().st_mode & 0o777) == 0o600
        for path in output.rglob("*")
        if path.is_file()
    )
    assert TOKEN.encode() not in b"".join(
        path.read_bytes() for path in output.rglob("*") if path.is_file()
    )
    assert not any(
        key in receipt
        for key in ("available_at", "declaration", "normalization", "formula")
    )

    by_key = {
        member["member_key"]: member for member in receipt["snapshot"]["members"]
    }
    reversed_snapshot = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                key,
                (output / key).read_bytes(),
                evidence["mode"],
                evidence["acquired_at_epoch_nanoseconds"],
                evidence["declared_sha256"],
            )
            for key, evidence in reversed(tuple(by_key.items()))
        ),
        provenance=sentinel._provenance(),
    ).snapshot
    assert reversed_snapshot is not None
    assert verify_source_snapshot(reversed_snapshot).failure is None
    assert reversed_snapshot.to_canonical_dict() == receipt["snapshot"]


def test_v3_request_facts_are_fresh_and_exact() -> None:
    assert sentinel._ANNUAL_REPORT_FACTS == (
        (
            "20181231",
            "1206125365",
            "https://static.cninfo.com.cn/finalpage/2019-04-29/1206125365.PDF",
            "response/cninfo/annual-report/1206125365.pdf",
            6_718_851,
            "sha256:b147eb6b8a4aaf093f3b83550c70e8526415b5b54fe24e4258ce7bfd11d5406a",
        ),
        (
            "20191231",
            "1207685438",
            "https://static.cninfo.com.cn/finalpage/2020-04-30/1207685438.PDF",
            "response/cninfo/annual-report/1207685438.pdf",
            7_535_725,
            "sha256:1b4869caab122969b322738df69955d788c8dc19b4c6d57188619177e922e708",
        ),
        (
            "20201231",
            "1209855305",
            "https://static.cninfo.com.cn/finalpage/2021-04-29/1209855305.PDF",
            "response/cninfo/annual-report/1209855305.pdf",
            3_444_361,
            "sha256:0d3c39090adf97fede39149a731a5636bd0eca2002606fb942ca70121dba9072",
        ),
        (
            "20211231",
            "1213262535",
            "https://static.cninfo.com.cn/finalpage/2022-04-30/1213262535.PDF",
            "response/cninfo/annual-report/1213262535.pdf",
            4_110_139,
            "sha256:96065ec44285bce7a9c0cbee25dfeb2368ec4552d72f06ebf3ecab35136e2444",
        ),
        (
            "20221231",
            "1216702261",
            "https://static.cninfo.com.cn/finalpage/2023-04-29/1216702261.PDF",
            "response/cninfo/annual-report/1216702261.pdf",
            3_765_397,
            "sha256:7cfc80c2badbf4cd74c5adc080d5072b02cd6c700b04fa7ca0ac44cb8b8fe987",
        ),
    )
    first = sentinel._annual_report_request_facts()
    second = sentinel._annual_report_request_facts()
    assert first == second
    assert first is not second
    assert all(left is not right for left, right in zip(first, second, strict=True))
    first[0]["period"] = "mutated"
    request_facts = cast(
        tuple[dict[str, object], ...],
        sentinel.TushareCnAShareFinancialHistorySentinelRequestV3().to_canonical_dict()[
            "annual_reports"
        ],
    )
    assert request_facts[0]["period"] == "20181231"
    with pytest.raises(ValueError):
        sentinel.TushareCnAShareFinancialHistorySentinelRequestV3(True)


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("json", sentinel.FinancialHistorySentinelV3FailureCode.PROVIDER_RESPONSE_INVALID),
        ("recursion", sentinel.FinancialHistorySentinelV3FailureCode.PROVIDER_RESPONSE_INVALID),
        ("fields", sentinel.FinancialHistorySentinelV3FailureCode.PROVIDER_FIELDS_MISMATCH),
        ("envelope", sentinel.FinancialHistorySentinelV3FailureCode.PROVIDER_RESPONSE_INVALID),
        ("issuer", sentinel.FinancialHistorySentinelV3FailureCode.FINANCIAL_ROW_SCOPE_MISMATCH),
        ("numeric", sentinel.FinancialHistorySentinelV3FailureCode.FINANCIAL_ROW_SCOPE_MISMATCH),
        ("flags", sentinel.FinancialHistorySentinelV3FailureCode.FINANCIAL_ROW_SCOPE_MISMATCH),
        ("credential", sentinel.FinancialHistorySentinelV3FailureCode.CREDENTIAL_LEAK_DETECTED),
    ],
)
def test_v3_provider_failures_are_typed_and_publish_nothing(
    mutation: str,
    code: sentinel.FinancialHistorySentinelV3FailureCode,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mutate(_body: dict[str, object], source: bytes) -> bytes:
        if mutation == "json":
            return b'{"bad":NaN}'
        if mutation == "recursion":
            return b"[" * 2_000 + b"]" * 2_000
        payload = json.loads(source)
        if mutation == "fields":
            payload["data"]["fields"][-1] = "wrong"
        elif mutation == "envelope":
            payload["data"]["count"] = 2
        elif mutation == "issuer":
            payload["data"]["items"][0][0] = "600519.SH"
        elif mutation == "numeric":
            payload["data"]["items"][0][6] = "1.0"
        elif mutation == "flags":
            payload["data"]["items"][0][-1] = "9"
        elif mutation == "credential":
            payload["request_id"] = TOKEN
        return json.dumps(payload, separators=(",", ":")).encode()

    output = tmp_path / mutation
    with pytest.raises(sentinel.FinancialHistorySentinelV3AcquisitionError) as caught:
        acquire(output, monkeypatch, proxy_post=FakeProxyPost(mutate))
    assert caught.value.code is code
    assert not output.exists()


def test_v3_proxy_callback_cannot_forge_receipt_request_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def mutate(body: dict[str, object], source: bytes) -> bytes:
        params = cast(dict[str, object], body["params"])
        params["period"] = "forged"
        body["fields"] = "forged"
        return source

    output = tmp_path / "mutated-request"
    with pytest.raises(sentinel.FinancialHistorySentinelV3AcquisitionError) as caught:
        acquire(output, monkeypatch, proxy_post=FakeProxyPost(mutate))
    assert (
        caught.value.code
        is sentinel.FinancialHistorySentinelV3FailureCode.PROVIDER_TRANSPORT_FAILURE
    )
    assert not output.exists()


def test_v3_cninfo_callback_cannot_mutate_wire_headers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def cninfo(
        _endpoint: str,
        _form: tuple[tuple[str, str], ...],
        headers: dict[str, str],
    ) -> tuple[int, bytes]:
        headers["x-api-key"] = "forged"
        return 200, metadata_bytes()

    output = tmp_path / "mutated-cninfo-headers"
    with pytest.raises(sentinel.FinancialHistorySentinelV3AcquisitionError) as caught:
        acquire(output, monkeypatch, cninfo_post=cninfo)
    assert (
        caught.value.code
        is sentinel.FinancialHistorySentinelV3FailureCode.OFFICIAL_METADATA_TRANSPORT_FAILURE
    )
    assert not output.exists()


@pytest.mark.parametrize(
    ("kind", "code"),
    [
        ("duplicate", sentinel.FinancialHistorySentinelV3FailureCode.OFFICIAL_METADATA_INVALID),
        ("markup", sentinel.FinancialHistorySentinelV3FailureCode.OFFICIAL_METADATA_INVALID),
        ("selected", sentinel.FinancialHistorySentinelV3FailureCode.OFFICIAL_METADATA_INVALID),
        ("credential", sentinel.FinancialHistorySentinelV3FailureCode.CREDENTIAL_LEAK_DETECTED),
        ("escaped_credential", sentinel.FinancialHistorySentinelV3FailureCode.CREDENTIAL_LEAK_DETECTED),
        ("malformed_credential", sentinel.FinancialHistorySentinelV3FailureCode.OFFICIAL_METADATA_INVALID),
        ("recursion", sentinel.FinancialHistorySentinelV3FailureCode.OFFICIAL_METADATA_INVALID),
    ],
)
def test_v3_metadata_failures_are_typed_and_atomic(
    kind: str,
    code: sentinel.FinancialHistorySentinelV3FailureCode,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def cninfo(
        _endpoint: str,
        _form: tuple[tuple[str, str], ...],
        _headers: dict[str, str],
    ) -> tuple[int, bytes]:
        source = metadata_bytes()
        if kind == "duplicate":
            return 200, source.replace(b'"hasMore":false', b'"hasMore":false,"hasMore":false')
        if kind == "recursion":
            return 200, b"[" * 2_000 + b"]" * 2_000
        payload = json.loads(source)
        if kind == "markup":
            payload["announcements"][0]["announcementTitle"] = "<em>2018年年度报告"
        elif kind == "selected":
            payload["announcements"][0]["announcementId"] = "wrong"
        elif kind in {"credential", "escaped_credential"}:
            payload["announcements"][-1]["announcementContent"] = TOKEN
        elif kind == "malformed_credential":
            payload["announcements"][0]["announcementId"] = "wrong"
            payload["announcements"][-1]["announcementContent"] = TOKEN
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        if kind == "escaped_credential":
            encoded = encoded.replace(TOKEN.encode(), b"\\u0070" * len(TOKEN))
        return 200, encoded

    output = tmp_path / kind
    with pytest.raises(sentinel.FinancialHistorySentinelV3AcquisitionError) as caught:
        acquire(output, monkeypatch, cninfo_post=cninfo)
    assert caught.value.code is code
    assert not output.exists()


def test_v3_transport_retries_redaction_and_document_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata_statuses = [503, 200]
    metadata_sleeps: list[float] = []

    def cninfo(
        _endpoint: str,
        _form: tuple[tuple[str, str], ...],
        _headers: dict[str, str],
    ) -> tuple[int, bytes]:
        status = metadata_statuses.pop(0)
        return status, metadata_bytes() if status == 200 else b""

    receipt, _proxy, _clock, sleeps = acquire(
        tmp_path / "retry",
        monkeypatch,
        proxy_post=FakeProxyPost(statuses=[500, 200]),
        cninfo_post=cninfo,
        sleep=metadata_sleeps.append,
    )
    assert receipt["provider_requests"][0]["attempts"] == 2
    assert receipt["official_metadata"]["attempts"] == 2
    assert metadata_sleeps[:2] == [1.0, 0.5]
    assert len(sleeps) == 0

    def leaking_proxy(
        _url: str, _body: dict[str, object], _headers: dict[str, str]
    ) -> tuple[int, bytes]:
        raise RuntimeError(TOKEN)

    with pytest.raises(sentinel.FinancialHistorySentinelV3AcquisitionError) as caught:
        acquire(tmp_path / "transport", monkeypatch, proxy_post=leaking_proxy)
    assert caught.value.code is sentinel.FinancialHistorySentinelV3FailureCode.PROVIDER_TRANSPORT_FAILURE
    assert str(caught.value) == "PROVIDER_TRANSPORT_FAILURE"

    documents = synthetic_documents(monkeypatch)
    first_url = sentinel._ANNUAL_REPORT_FACTS[0][2]
    with pytest.raises(sentinel.FinancialHistorySentinelV3AcquisitionError) as mismatch:
        acquire(
            tmp_path / "document",
            monkeypatch,
            get=lambda url: (
                200,
                documents[url] + (b"x" if url == first_url else b""),
                url,
            ),
        )
    assert mismatch.value.code is sentinel.FinancialHistorySentinelV3FailureCode.ANNUAL_REPORT_MISMATCH

    with pytest.raises(sentinel.FinancialHistorySentinelV3AcquisitionError) as redirect:
        acquire(
            tmp_path / "redirect",
            monkeypatch,
            get=lambda url: (200, documents[url], url + "?redirected=1"),
        )
    assert redirect.value.code is sentinel.FinancialHistorySentinelV3FailureCode.OFFICIAL_DOCUMENT_TRANSPORT_FAILURE


def test_v3_output_preflight_atomic_visibility_lock_and_destination_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "capture"
    real_rename = sentinel.os.rename
    observed: dict[str, object] = {}

    def inspect_rename(source: os.PathLike[str] | str, destination: os.PathLike[str] | str) -> None:
        staging = Path(source)
        observed["final_invisible"] = not output.exists()
        observed["receipt_present"] = (staging / "acquisition-receipt.json").is_file()
        calls: list[str] = []
        with pytest.raises(sentinel.FinancialHistorySentinelV3AcquisitionError) as second:
            sentinel.acquire_tushare_cn_a_share_financial_history_sentinel_v3(
                sentinel.TushareCnAShareFinancialHistorySentinelRequestV3(),
                token=TOKEN,
                endpoint="https://fast.xiaodefa.cn",
                output_dir=output,
                proxy_post=lambda *_args: calls.append("proxy") or (500, b""),
                cninfo_post=lambda *_args: calls.append("cninfo") or (500, b""),
                get=lambda _url: (500, b"", ""),
            )
        observed["second_code"] = second.value.code
        observed["second_calls"] = calls
        real_rename(source, destination)

    monkeypatch.setattr(sentinel.os, "rename", inspect_rename)
    acquire(output, monkeypatch)
    assert observed == {
        "final_invisible": True,
        "receipt_present": True,
        "second_code": sentinel.FinancialHistorySentinelV3FailureCode.OUTPUT_PATH_INVALID,
        "second_calls": [],
    }

    race = tmp_path / "race"
    real_require = sentinel._require_safe_output
    checks = 0

    def destination_race(path: str | Path) -> None:
        nonlocal checks
        checks += 1
        if checks == 3:
            race.mkdir()
        real_require(path)

    monkeypatch.setattr(sentinel, "_require_safe_output", destination_race)
    with pytest.raises(sentinel.FinancialHistorySentinelV3AcquisitionError) as caught:
        acquire(race, monkeypatch)
    assert caught.value.code is sentinel.FinancialHistorySentinelV3FailureCode.OUTPUT_PATH_INVALID
    assert race.is_dir()
    assert not (tmp_path / ".race.staging-v3").exists()


def test_v3_publication_failure_cleans_staging_and_preserves_snapshot_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "publication"
    real_fsync = sentinel.os.fsync
    calls = 0

    def fail_fsync(descriptor: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("fixture")
        real_fsync(descriptor)

    monkeypatch.setattr(sentinel.os, "fsync", fail_fsync)
    with pytest.raises(sentinel.FinancialHistorySentinelV3AcquisitionError) as caught:
        acquire(output, monkeypatch)
    assert caught.value.code is sentinel.FinancialHistorySentinelV3FailureCode.PUBLICATION_FAILURE
    assert not output.exists()
    assert not (tmp_path / ".publication.staging-v3").exists()

    monkeypatch.setattr(sentinel.os, "fsync", real_fsync)
    monkeypatch.setattr(
        sentinel,
        "verify_source_snapshot",
        lambda _snapshot: SimpleNamespace(
            failure=SimpleNamespace(code=SourceSnapshotFailureCode.ARCHIVE_INVALID)
        ),
    )
    with pytest.raises(sentinel.FinancialHistorySentinelV3AcquisitionError) as snapshot:
        acquire(tmp_path / "snapshot", monkeypatch)
    assert snapshot.value.code is SourceSnapshotFailureCode.ARCHIVE_INVALID
    assert not (tmp_path / "snapshot").exists()


def test_v3_stdlib_cninfo_wire_is_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[tuple[Any, int]] = []

    class Response:
        status = 200

        def __init__(self, url: str, body: bytes) -> None:
            self.url = url
            self.body = body

        def __enter__(self) -> Response:
            return self

        def __exit__(
            self,
            exception_type: type[BaseException] | None,
            exception: BaseException | None,
            traceback: object,
        ) -> None:
            return None

        def read(self) -> bytes:
            return self.body

        def geturl(self) -> str:
            return self.url

    class Opener:
        def open(self, request: Any, timeout: int) -> Response:
            opened.append((request, timeout))
            url = request.full_url
            return Response(url, b"body")

    handlers: list[object] = []

    def build_opener(handler: object) -> Opener:
        handlers.append(handler)
        return Opener()

    monkeypatch.setattr(sentinel.urllib.request, "build_opener", build_opener)
    status, body = sentinel._stdlib_cninfo_post(
        sentinel._CNINFO_ENDPOINT,
        sentinel._CNINFO_FORM,
        dict(sentinel._CNINFO_HEADERS),
    )
    assert (status, body) == (200, b"body")
    metadata_request, timeout = opened.pop(0)
    assert timeout == 30
    assert metadata_request.get_method() == "POST"
    assert metadata_request.data == sentinel.urllib.parse.urlencode(
        sentinel._CNINFO_FORM
    ).encode("ascii")
    assert {name.lower(): value for name, value in metadata_request.header_items()} == {
        name.lower(): value for name, value in sentinel._CNINFO_HEADERS
    }

    url = sentinel._ANNUAL_REPORT_FACTS[0][2]
    assert sentinel._stdlib_get(url) == (200, b"body", url)
    document_request, timeout = opened.pop(0)
    assert timeout == 30
    assert document_request.get_method() == "GET"
    assert document_request.data is None
    assert {name.lower(): value for name, value in document_request.header_items()} == {
        name.lower(): value for name, value in sentinel._CNINFO_HEADERS
    }
    assert len(handlers) == 2
    assert all(type(handler) is sentinel._NoRedirect for handler in handlers)


def test_v3_input_credential_output_and_cli_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    callbacks: list[str] = []
    with pytest.raises(sentinel.FinancialHistorySentinelV3AcquisitionError) as credential:
        sentinel.acquire_tushare_cn_a_share_financial_history_sentinel_v3(
            sentinel.TushareCnAShareFinancialHistorySentinelRequestV3(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=tmp_path / TOKEN / "capture",
            proxy_post=lambda *_args: callbacks.append("proxy") or (500, b""),
            cninfo_post=lambda *_args: callbacks.append("cninfo") or (500, b""),
            get=lambda _url: (500, b"", ""),
        )
    assert credential.value.code is sentinel.FinancialHistorySentinelV3FailureCode.CREDENTIAL_INPUT_INVALID
    assert callbacks == []

    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(sentinel.FinancialHistorySentinelV3AcquisitionError) as output:
        sentinel.acquire_tushare_cn_a_share_financial_history_sentinel_v3(
            sentinel.TushareCnAShareFinancialHistorySentinelRequestV3(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=existing,
            proxy_post=lambda *_args: callbacks.append("proxy") or (500, b""),
            cninfo_post=lambda *_args: callbacks.append("cninfo") or (500, b""),
            get=lambda _url: (500, b"", ""),
        )
    assert output.value.code is sentinel.FinancialHistorySentinelV3FailureCode.OUTPUT_PATH_INVALID
    assert callbacks == []

    captured: dict[str, object] = {}

    def fake_acquire(request: object, **kwargs: object) -> dict[str, object]:
        captured["request"] = request
        captured.update(kwargs)
        return {"type": "fixture", "schema_version": 3}

    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    monkeypatch.setattr(
        sentinel,
        "acquire_tushare_cn_a_share_financial_history_sentinel_v3",
        fake_acquire,
    )
    assert sentinel.main(
        ["--endpoint", "https://fast.xiaodefa.cn", "--output-dir", str(tmp_path / "cli")]
    ) == 0
    assert captured["proxy_post"] is sentinel._proxy_stdlib_post
    assert captured["cninfo_post"] is sentinel._stdlib_cninfo_post
    assert captured["get"] is sentinel._stdlib_get
    assert captured["token"] == TOKEN
    assert '"schema_version": 3' in capsys.readouterr().out
