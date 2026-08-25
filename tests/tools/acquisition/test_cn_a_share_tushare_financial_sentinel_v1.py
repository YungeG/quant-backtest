from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotFailureCode,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)

from tools.acquisition import _common
from tools.acquisition._common import AcquisitionError
from tools.acquisition import cn_a_share_tushare_financial_sentinel_v1 as sentinel

TOKEN = "financial-sentinel-secret"


def response(fields: tuple[str, ...], items: list[list[object]]) -> bytes:
    return json.dumps(
        {
            "request_id": "fixed-request-id",
            "code": 0,
            "data": {
                "fields": list(fields),
                "items": items,
                "has_more": False,
                "count": len(items),
            },
            "msg": "",
            "detail": "",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


def row(fields: tuple[str, ...], *, report_type: str = "1") -> list[object]:
    values: dict[str, object] = {
        "ts_code": "000651.SZ",
        "ann_date": "20240430",
        "f_ann_date": "20240430",
        "end_date": "20231231",
        "report_type": report_type,
        "comp_type": "1",
        "update_flag": "1",
    }
    return [values.get(field, 1.0) for field in fields]


class FakePost:
    def __init__(
        self,
        responder: Callable[[str, tuple[str, ...]], bytes] | None = None,
        statuses: list[int] | None = None,
    ) -> None:
        self.responder = responder or (
            lambda _api, fields: response(fields, [row(fields), row(fields, report_type="5")])
        )
        self.statuses = list(statuses or [])
        self.calls: list[dict[str, object]] = []

    def __call__(self, _url: str, body: dict[str, object]) -> tuple[int, bytes]:
        self.calls.append(body)
        status = self.statuses.pop(0) if self.statuses else 200
        fields = tuple(str(body["fields"]).split(","))
        return (
            status,
            b"" if status != 200 else self.responder(str(body["api_name"]), fields),
        )


class Clock:
    def __init__(self) -> None:
        self.value = 1_900_000_000_000_000_000

    def __call__(self) -> int:
        self.value += 1
        return self.value


def acquire(
    output: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    post: sentinel.Post | None = None,
    get: sentinel.Get | None = None,
    pdf: bytes = b"%PDF-1.5\nfixture\n",
) -> dict[str, object]:
    monkeypatch.setattr(sentinel, "_REPORT_BYTES", len(pdf))
    monkeypatch.setattr(sentinel, "_REPORT_SHA256", _common.sha256(pdf))
    return sentinel.acquire_tushare_cn_a_share_financial_source_sentinel_v1(
        sentinel.TushareCnAShareFinancialSourceSentinelRequestV1(),
        token=TOKEN,
        output_dir=output,
        post=post or FakePost(),
        get=get or (lambda url: (200, pdf, url)),
        time_ns=Clock(),
        sleep=lambda _: None,
    )


def test_capture_freezes_exact_members_redacts_token_and_writes_receipt_last(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writes: list[str] = []
    real_open = _common.os.open

    def tracking_open(
        path: os.PathLike[str] | str,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if flags & os.O_WRONLY:
            writes.append(str(path))
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(_common.os, "open", tracking_open)
    output = tmp_path / "capture"
    post = FakePost()
    receipt = acquire(output, monkeypatch, post=post)

    expected_members = {
        "response/tushare/income/000651.SZ-20231231-20240430.json",
        "response/tushare/balancesheet/000651.SZ-20231231-20240430.json",
        "response/tushare/cashflow/000651.SZ-20231231-20240430.json",
        "response/cninfo/annual-report/1219928418.pdf",
    }
    assert {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    } == {*expected_members, "acquisition-receipt.json"}
    assert Path(writes[-1]).name == "acquisition-receipt.json"
    assert json.loads((output / "acquisition-receipt.json").read_bytes()) == receipt
    assert [request["api_name"] for request in receipt["provider_requests"]] == [
        "income",
        "balancesheet",
        "cashflow",
    ]
    assert [body["fields"] for body in post.calls] == [
        ",".join(sentinel._INCOME_FIELDS),
        ",".join(sentinel._BALANCE_FIELDS),
        ",".join(sentinel._CASHFLOW_FIELDS),
    ]
    assert all(
        request["params"]
        == {"ts_code": "000651.SZ", "ann_date": "20240430", "period": "20231231"}
        for request in receipt["provider_requests"]
    )
    assert all(
        request["observed_rows"]
        == {
            "row_count": 2,
            "report_types": ["1", "5"],
            "duplicate_row_count": 0,
            "conflicting_identity_count": 0,
        }
        for request in receipt["provider_requests"]
    )
    assert receipt["limitations"] == list(sentinel._LIMITATIONS)
    assert receipt["decision_grade_eligible"] is False
    assert receipt["deployment_authorized"] is False
    assert TOKEN.encode() not in b"".join(
        path.read_bytes() for path in output.rglob("*") if path.is_file()
    )
    canonical_members = {
        member["member_key"]: member for member in receipt["snapshot"]["members"]
    }
    assert set(canonical_members) == expected_members
    rebuilt = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                member_key,
                (output / member_key).read_bytes(),
                evidence["mode"],
                evidence["acquired_at_epoch_nanoseconds"],
                evidence["declared_sha256"],
            )
            for member_key, evidence in canonical_members.items()
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro-cninfo.com.cn",
            source_key="cn_a_share.financial_source_sentinel.000651.sz.20231231.v1",
            license_ref="tushare.pro.terms-cninfo.public-disclosure",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    assert rebuilt is not None
    assert verify_source_snapshot(rebuilt).failure is None
    assert rebuilt.to_canonical_dict() == receipt["snapshot"]


@pytest.mark.parametrize(
    ("failure", "expected_code"),
    [
        ("empty", sentinel.FinancialSentinelFailureCode.FINANCIAL_ROW_SCOPE_MISMATCH),
        ("foreign", sentinel.FinancialSentinelFailureCode.FINANCIAL_ROW_SCOPE_MISMATCH),
        ("foreign_ann", sentinel.FinancialSentinelFailureCode.FINANCIAL_ROW_SCOPE_MISMATCH),
        ("foreign_period", sentinel.FinancialSentinelFailureCode.FINANCIAL_ROW_SCOPE_MISMATCH),
        ("fields", sentinel.FinancialSentinelFailureCode.PROVIDER_FIELDS_MISMATCH),
        ("row_length", sentinel.FinancialSentinelFailureCode.PROVIDER_RESPONSE_INVALID),
        ("provider_code", sentinel.FinancialSentinelFailureCode.PROVIDER_RESPONSE_INVALID),
        ("nan", sentinel.FinancialSentinelFailureCode.PROVIDER_RESPONSE_INVALID),
        ("infinity", sentinel.FinancialSentinelFailureCode.PROVIDER_RESPONSE_INVALID),
        ("duplicate", sentinel.FinancialSentinelFailureCode.PROVIDER_RESPONSE_INVALID),
        ("credential", sentinel.FinancialSentinelFailureCode.CREDENTIAL_LEAK_DETECTED),
        ("malformed_credential", sentinel.FinancialSentinelFailureCode.PROVIDER_RESPONSE_INVALID),
        ("fields_credential", sentinel.FinancialSentinelFailureCode.PROVIDER_FIELDS_MISMATCH),
        ("fields_bad_row", sentinel.FinancialSentinelFailureCode.PROVIDER_RESPONSE_INVALID),
        ("row_credential", sentinel.FinancialSentinelFailureCode.FINANCIAL_ROW_SCOPE_MISMATCH),
        ("code_fields", sentinel.FinancialSentinelFailureCode.PROVIDER_RESPONSE_INVALID),
    ],
)
def test_invalid_statement_response_fails_atomically(
    failure: str,
    expected_code: sentinel.FinancialSentinelFailureCode,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid(_api: str, fields: tuple[str, ...]) -> bytes:
        if failure == "empty":
            return response(fields, [])
        if failure in {"foreign", "foreign_ann", "foreign_period"}:
            values = row(fields)
            positions = {field: index for index, field in enumerate(fields)}
            replacements = {
                "foreign": ("ts_code", "600519.SH"),
                "foreign_ann": ("ann_date", "20240429"),
                "foreign_period": ("end_date", "20221231"),
            }
            field, value = replacements[failure]
            values[positions[field]] = value
            return response(fields, [values])
        if failure == "fields":
            return response((*fields[:-1], "wrong_field"), [row(fields)])
        if failure == "fields_bad_row":
            return response((*fields[:-1], "wrong_field"), [row(fields)[:-1]])
        if failure == "row_length":
            return response(fields, [row(fields)[:-1]])
        if failure in {"provider_code", "code_fields"}:
            payload = json.loads(response(fields, [row(fields)]))
            payload["code"] = 10001
            if failure == "code_fields":
                payload["data"]["fields"][-1] = "wrong_field"
            return json.dumps(payload, separators=(",", ":")).encode()
        if failure == "duplicate":
            return b'{"request_id":"x","request_id":"y","code":0}'
        if failure == "credential":
            values = row(fields)
            values[-2] = TOKEN
            return response(fields, [values])
        if failure == "malformed_credential":
            return f'{{"token":"{TOKEN}"'.encode()
        if failure == "fields_credential":
            payload = json.loads(
                response((*fields[:-1], "wrong_field"), [row(fields)])
            )
            payload["detail"] = TOKEN
            return json.dumps(payload, separators=(",", ":")).encode()
        if failure == "row_credential":
            values = row(fields)
            values[0] = TOKEN
            return response(fields, [values])
        if failure == "infinity":
            values = row(fields)
            values[-2] = float("inf")
            return response(fields, [values])
        return (
            b'{"request_id":"x","code":0,"data":{"fields":[],"items":[NaN],'
            b'"has_more":false,"count":1},"msg":"","detail":""}'
        )

    output = tmp_path / failure
    with pytest.raises(sentinel.FinancialSentinelAcquisitionError) as caught:
        acquire(output, monkeypatch, post=FakePost(invalid))
    assert caught.value.code is expected_code
    assert not output.exists()


@pytest.mark.parametrize(
    "get",
    [
        lambda url: (200, b"<html>blocked</html>", url),
        lambda url: (200, b"%PDF-1.5\nwrong\n", url),
        lambda url: (200, b"%PDF-1.5\nchanged\n", url),
        lambda _url: (200, b"%PDF-1.5\nfixture\n", "https://evil.example/report.pdf"),
    ],
)
def test_official_report_mismatch_fails_atomically(
    get: sentinel.Get,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = b"%PDF-1.5\nfixture\n"
    monkeypatch.setattr(sentinel, "_REPORT_BYTES", len(expected))
    monkeypatch.setattr(sentinel, "_REPORT_SHA256", _common.sha256(expected))
    output = tmp_path / "capture"
    with pytest.raises(sentinel.FinancialSentinelAcquisitionError) as caught:
        sentinel.acquire_tushare_cn_a_share_financial_source_sentinel_v1(
            sentinel.TushareCnAShareFinancialSourceSentinelRequestV1(),
            token=TOKEN,
            output_dir=output,
            post=FakePost(),
            get=get,
            time_ns=Clock(),
            sleep=lambda _: None,
        )
    assert caught.value.code is sentinel.FinancialSentinelFailureCode.OFFICIAL_REPORT_MISMATCH
    assert not output.exists()


def test_valid_escaped_nul_provider_text_is_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def with_nul(_api: str, fields: tuple[str, ...]) -> bytes:
        payload = json.loads(response(fields, [row(fields)]))
        payload["detail"] = "\x00"
        return json.dumps(payload, separators=(",", ":")).encode()

    output = tmp_path / "capture"
    acquire(output, monkeypatch, post=FakePost(with_nul))
    assert b"\\u0000" in next((output / "response/tushare").rglob("*.json")).read_bytes()


def test_redirect_handler_rejects_an_intermediate_foreign_host() -> None:
    handler = sentinel._ReportRedirectHandler()
    with pytest.raises(sentinel.FinancialSentinelAcquisitionError) as caught:
        handler.redirect_request(
            sentinel.UrlRequest(sentinel._REPORT_URL),
            None,
            302,
            "Found",
            {},
            "https://evil.example/1219928418.pdf",
        )
    assert caught.value.code is sentinel.FinancialSentinelFailureCode.OFFICIAL_REPORT_MISMATCH


def test_conflicting_rows_are_reported_without_deduplication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def conflicting(_api: str, fields: tuple[str, ...]) -> bytes:
        first = row(fields)
        second = list(first)
        second[-2] = 2.0
        return response(fields, [first, second])

    output = tmp_path / "capture"
    receipt = acquire(output, monkeypatch, post=FakePost(conflicting))
    assert all(
        request["observed_rows"]["conflicting_identity_count"] == 1
        for request in receipt["provider_requests"]
    )
    for request in receipt["provider_requests"]:
        payload = json.loads((output / request["member_key"]).read_bytes())
        assert len(payload["data"]["items"]) == 2


def test_credential_is_rejected_before_path_or_network_use(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    output = tmp_path / TOKEN / "capture"
    with pytest.raises(sentinel.FinancialSentinelAcquisitionError) as caught:
        sentinel.acquire_tushare_cn_a_share_financial_source_sentinel_v1(
            sentinel.TushareCnAShareFinancialSourceSentinelRequestV1(),
            token=TOKEN,
            output_dir=output,
            post=lambda _url, _body: calls.append("post") or (500, b""),
            get=lambda _url: calls.append("get") or (500, b"", ""),
        )
    assert caught.value.code is sentinel.FinancialSentinelFailureCode.CREDENTIAL_INPUT_INVALID
    assert calls == []
    assert not (tmp_path / TOKEN).exists()

    with pytest.raises(sentinel.FinancialSentinelAcquisitionError) as canonical:
        sentinel.acquire_tushare_cn_a_share_financial_source_sentinel_v1(
            sentinel.TushareCnAShareFinancialSourceSentinelRequestV1(),
            token="000651.SZ",
            output_dir=tmp_path / "other",
            post=lambda _url, _body: (500, b""),
            get=lambda _url: (500, b"", ""),
        )
    assert canonical.value.code is sentinel.FinancialSentinelFailureCode.CREDENTIAL_INPUT_INVALID


def test_symlink_and_traversal_outputs_fail_before_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(AcquisitionError, match="symlinks"):
        acquire(link / "capture", monkeypatch)
    with pytest.raises(AcquisitionError, match="traversal"):
        acquire(tmp_path / "child" / ".." / "capture", monkeypatch)
    assert list(target.iterdir()) == []


def test_snapshot_failure_code_is_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sentinel,
        "verify_source_snapshot",
        lambda _snapshot: SimpleNamespace(
            failure=SimpleNamespace(code=SourceSnapshotFailureCode.ARCHIVE_INVALID)
        ),
    )
    with pytest.raises(sentinel.FinancialSentinelAcquisitionError) as caught:
        acquire(tmp_path / "capture", monkeypatch)
    assert caught.value.code is SourceSnapshotFailureCode.ARCHIVE_INVALID
    assert not (tmp_path / "capture").exists()


def test_publication_failure_cleans_partial_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_open = _common.os.open
    writes = 0

    def fail_second_write(
        path: os.PathLike[str] | str,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal writes
        if flags & os.O_WRONLY:
            writes += 1
            if writes == 2:
                raise OSError("fixture write failure")
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(_common.os, "open", fail_second_write)
    output = tmp_path / "capture"
    with pytest.raises(OSError, match="fixture write failure"):
        acquire(output, monkeypatch)
    assert not output.exists()


def test_transient_provider_and_report_failures_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = b"%PDF-1.5\nfixture\n"
    report_statuses = [503, 200]

    def get(url: str) -> tuple[int, bytes, str]:
        status = report_statuses.pop(0)
        return status, b"" if status != 200 else pdf, url

    post = FakePost(statuses=[500, 200])
    receipt = acquire(tmp_path / "capture", monkeypatch, post=post, get=get, pdf=pdf)
    assert receipt["provider_requests"][0]["attempts"] == 2
    assert receipt["official_report"]["attempts"] == 2
    assert len(post.calls) == 4


def test_transport_and_retry_exceptions_are_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed_post(_url: str, _body: dict[str, object]) -> tuple[int, bytes]:
        raise RuntimeError(TOKEN)

    with pytest.raises(sentinel.FinancialSentinelAcquisitionError) as post_failure:
        acquire(tmp_path / "post", monkeypatch, post=failed_post)
    assert post_failure.value.code is sentinel.FinancialSentinelFailureCode.PROVIDER_TRANSPORT_FAILURE
    assert TOKEN not in str(post_failure.value)

    def failed_sleep(_attempt: int) -> None:
        raise RuntimeError(TOKEN)

    post = FakePost(statuses=[500])
    with pytest.raises(sentinel.FinancialSentinelAcquisitionError) as sleep_failure:
        sentinel.acquire_tushare_cn_a_share_financial_source_sentinel_v1(
            sentinel.TushareCnAShareFinancialSourceSentinelRequestV1(),
            token=TOKEN,
            output_dir=tmp_path / "sleep",
            post=post,
            get=lambda url: (200, b"%PDF-1.5\nfixture\n", url),
            time_ns=Clock(),
            sleep=failed_sleep,
        )
    assert sleep_failure.value.code is sentinel.FinancialSentinelFailureCode.PROVIDER_TRANSPORT_FAILURE
    assert TOKEN not in str(sleep_failure.value)


def test_request_and_output_scope_are_frozen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError):
        sentinel.TushareCnAShareFinancialSourceSentinelRequestV1(schema_version=2)

    output = tmp_path / "capture"
    output.mkdir()
    with pytest.raises(AcquisitionError):
        acquire(output, monkeypatch)
