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
from tools.acquisition import cn_a_share_tushare_financial_sentinel_v2 as sentinel

TOKEN = "p" * 56
REPORT = b"%PDF-1.5\nannual-report\n"
CONFIRMATION = b"%PDF-1.5\npublication-confirmation\n"


def response(fields: tuple[str, ...], items: list[list[object]]) -> bytes:
    return json.dumps(
        {
            "request_id": "v2-request-id",
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
        self.headers: list[dict[str, str]] = []

    def __call__(
        self,
        _url: str,
        body: dict[str, object],
        headers: dict[str, str],
    ) -> tuple[int, bytes]:
        self.calls.append(body)
        self.headers.append(headers)
        status = self.statuses.pop(0) if self.statuses else 200
        fields = tuple(str(body["fields"]).split(","))
        return (
            status,
            b"" if status != 200 else self.responder(str(body["api_name"]), fields),
        )


class Clock:
    def __init__(self) -> None:
        self.value = 1_910_000_000_000_000_000

    def __call__(self) -> int:
        self.value += 1
        return self.value


def acquire(
    output: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    post: sentinel.ProxyPost | None = None,
    get: sentinel.Get | None = None,
) -> dict[str, object]:
    monkeypatch.setattr(sentinel, "_REPORT_BYTES", len(REPORT))
    monkeypatch.setattr(sentinel, "_REPORT_SHA256", _common.sha256(REPORT))
    monkeypatch.setattr(sentinel, "_CONFIRMATION_BYTES", len(CONFIRMATION))
    monkeypatch.setattr(
        sentinel, "_CONFIRMATION_SHA256", _common.sha256(CONFIRMATION)
    )
    monkeypatch.setattr(
        sentinel,
        "_DOCUMENTS",
        {
            sentinel._REPORT_URL: (
                sentinel._REPORT_MEMBER,
                "annual_report",
                len(REPORT),
                _common.sha256(REPORT),
                sentinel.FinancialSentinelV2FailureCode.ANNUAL_REPORT_MISMATCH,
            ),
            sentinel._CONFIRMATION_URL: (
                sentinel._CONFIRMATION_MEMBER,
                "confirmation",
                len(CONFIRMATION),
                _common.sha256(CONFIRMATION),
                sentinel.FinancialSentinelV2FailureCode.PUBLICATION_CONFIRMATION_MISMATCH,
            ),
        },
    )

    def default_get(url: str) -> tuple[int, bytes, str]:
        return 200, CONFIRMATION if url == sentinel._CONFIRMATION_URL else REPORT, url

    return sentinel.acquire_tushare_cn_a_share_financial_source_sentinel_v2(
        sentinel.TushareCnAShareFinancialSourceSentinelRequestV2(),
        token=TOKEN,
        endpoint="https://fast.xiaodefa.cn",
        output_dir=output,
        post=post or FakePost(),
        get=get or default_get,
        time_ns=Clock(),
        sleep=lambda _: None,
    )


def test_v2_captures_expanded_fields_and_exact_five_members(
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

    expected = {
        "response/tushare/income/000651.SZ-20231231-20240430-v2.json",
        "response/tushare/balancesheet/000651.SZ-20231231-20240430-v2.json",
        "response/tushare/cashflow/000651.SZ-20231231-20240430-v2.json",
        "response/cninfo/annual-report/1219928418.pdf",
        "response/cninfo/publication-confirmation/1220300051.pdf",
    }
    assert {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    } == {*expected, "acquisition-receipt.json"}
    expected_fields = [
        "ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,revenue,operate_profit,total_profit,income_tax,n_income,n_income_attr_p,minority_gain,fin_exp_int_exp,ebit,ebitda,update_flag",
        "ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,money_cap,total_assets,total_liab,total_hldr_eqy_inc_min_int,total_hldr_eqy_exc_min_int,minority_int,total_liab_hldr_eqy,st_borr,non_cur_liab_due_1y,lt_borr,bond_payable,st_bonds_payable,lease_liab,update_flag",
        "ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,n_cashflow_act,c_pay_acq_const_fiolta,depr_fa_coga_dpba,use_right_asset_dep,amort_intang_assets,lt_amort_deferred_exp,c_cash_equ_end_period,free_cashflow,update_flag",
    ]
    assert [body["fields"] for body in post.calls] == expected_fields
    assert receipt["transport_proxy_key"] == "xiaodefa.approved-tushare-proxy.v1"
    assert receipt["transport_endpoint"] == "https://fast.xiaodefa.cn"
    assert all(headers["x-api-key"] == TOKEN for headers in post.headers)
    assert all(
        body["params"]
        == {
            "ts_code": "000651.SZ",
            "ann_date": "20240430",
            "period": "20231231",
            "comp_type": "1",
        }
        for body in post.calls
    )
    assert Path(writes[-1]).name == "acquisition-receipt.json"
    assert json.loads((output / "acquisition-receipt.json").read_bytes()) == receipt
    canonical_members = {
        member["member_key"]: member for member in receipt["snapshot"]["members"]
    }
    assert set(canonical_members) == expected
    assert "confirmation_claim" not in receipt
    assert "confirmation_disclosed_on" not in receipt["request"]
    assert receipt["limitations"] == [
        *sentinel._V1_LIMITATIONS,
        "publication confirmation is retained as raw retrospective date-only evidence",
        "confirmation semantics require a separate accepted declaration",
        "provider EBIT, EBITDA, and free cash flow are advisory only",
        "accounting unit requires a separate accepted declaration",
        "debt classification may remain incomplete",
        "no normalized revision, presentation selection, or formula evidence",
        "no five-year history, full-market coverage, or terminal-set closure",
        "approved proxy transport is not provider completeness",
    ]
    for request in receipt["provider_requests"]:
        payload = json.loads((output / request["member_key"]).read_bytes())
        positions = {
            field: index for index, field in enumerate(payload["data"]["fields"])
        }
        assert [
            item[positions["report_type"]] for item in payload["data"]["items"]
        ] == ["1", "5"]

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
            vendor_key="tushare.pro-via-xiaodefa-cninfo.com.cn",
            source_key="cn_a_share.financial_source_sentinel.000651.sz.20231231.v2.proxy",
            license_ref="tushare.pro.terms-cninfo.public-disclosure",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    assert rebuilt is not None
    assert verify_source_snapshot(rebuilt).failure is None
    assert rebuilt.to_canonical_dict() == receipt["snapshot"]
    assert receipt["decision_grade_eligible"] is False
    assert receipt["deployment_authorized"] is False
    assert TOKEN.encode() not in b"".join(
        path.read_bytes() for path in output.rglob("*") if path.is_file()
    )


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        ("empty", sentinel.FinancialSentinelV2FailureCode.FINANCIAL_ROW_SCOPE_MISMATCH),
        ("foreign", sentinel.FinancialSentinelV2FailureCode.FINANCIAL_ROW_SCOPE_MISMATCH),
        ("foreign_comp", sentinel.FinancialSentinelV2FailureCode.FINANCIAL_ROW_SCOPE_MISMATCH),
        ("fields", sentinel.FinancialSentinelV2FailureCode.PROVIDER_FIELDS_MISMATCH),
        ("invalid", sentinel.FinancialSentinelV2FailureCode.PROVIDER_RESPONSE_INVALID),
        ("credential", sentinel.FinancialSentinelV2FailureCode.CREDENTIAL_LEAK_DETECTED),
        ("fields_bad_row", sentinel.FinancialSentinelV2FailureCode.PROVIDER_RESPONSE_INVALID),
        ("code_fields", sentinel.FinancialSentinelV2FailureCode.PROVIDER_RESPONSE_INVALID),
        ("malformed_credential", sentinel.FinancialSentinelV2FailureCode.PROVIDER_RESPONSE_INVALID),
    ],
)
def test_v2_statement_failures_are_atomic_and_typed(
    failure: str,
    code: sentinel.FinancialSentinelV2FailureCode,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid(_api: str, fields: tuple[str, ...]) -> bytes:
        if failure == "empty":
            return response(fields, [])
        if failure in {"foreign", "foreign_comp"}:
            values = row(fields)
            positions = {field: index for index, field in enumerate(fields)}
            if failure == "foreign":
                values[positions["ts_code"]] = "600519.SH"
            else:
                values[positions["comp_type"]] = "2"
            return response(fields, [values])
        if failure == "fields":
            return response((*fields[:-1], "wrong_field"), [row(fields)])
        if failure == "fields_bad_row":
            return response((*fields[:-1], "wrong_field"), [row(fields)[:-1]])
        if failure == "code_fields":
            payload = json.loads(response((*fields[:-1], "wrong_field"), [row(fields)]))
            payload["code"] = 10001
            return json.dumps(payload, separators=(",", ":")).encode()
        if failure == "credential":
            values = row(fields)
            values[-2] = TOKEN
            return response(fields, [values])
        if failure == "malformed_credential":
            return f'{{"token":"{TOKEN}"'.encode()
        return b'{"request_id":"x","code":0,"data":{"fields":[],"items":[NaN]}}'

    output = tmp_path / failure
    with pytest.raises(sentinel.FinancialSentinelV2AcquisitionError) as caught:
        acquire(output, monkeypatch, post=FakePost(invalid))
    assert caught.value.code is code
    assert not output.exists()


@pytest.mark.parametrize(
    ("failed_url", "code"),
    [
        ("report", sentinel.FinancialSentinelV2FailureCode.ANNUAL_REPORT_MISMATCH),
        ("report_hash", sentinel.FinancialSentinelV2FailureCode.ANNUAL_REPORT_MISMATCH),
        (
            "confirmation",
            sentinel.FinancialSentinelV2FailureCode.PUBLICATION_CONFIRMATION_MISMATCH,
        ),
        (
            "confirmation_hash",
            sentinel.FinancialSentinelV2FailureCode.PUBLICATION_CONFIRMATION_MISMATCH,
        ),
    ],
)
def test_v2_official_document_identity_failures_are_distinct(
    failed_url: str,
    code: sentinel.FinancialSentinelV2FailureCode,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def get(url: str) -> tuple[int, bytes, str]:
        if failed_url == "report" and url == sentinel._REPORT_URL:
            return 200, b"%PDF-1.5\nwrong-report\n", url
        if failed_url == "report_hash" and url == sentinel._REPORT_URL:
            return 200, REPORT[:-1] + (b"X" if REPORT[-1:] != b"X" else b"Y"), url
        if failed_url == "confirmation" and url == sentinel._CONFIRMATION_URL:
            return 200, b"%PDF-1.5\nwrong-confirmation\n", url
        if failed_url == "confirmation_hash" and url == sentinel._CONFIRMATION_URL:
            return (
                200,
                CONFIRMATION[:-1] + (b"X" if CONFIRMATION[-1:] != b"X" else b"Y"),
                url,
            )
        return 200, CONFIRMATION if url == sentinel._CONFIRMATION_URL else REPORT, url

    output = tmp_path / failed_url
    with pytest.raises(sentinel.FinancialSentinelV2AcquisitionError) as caught:
        acquire(output, monkeypatch, get=get)
    assert caught.value.code is code
    assert not output.exists()


def test_v2_preserves_source_snapshot_failure_code(
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
    with pytest.raises(sentinel.FinancialSentinelV2AcquisitionError) as caught:
        acquire(tmp_path / "capture", monkeypatch)
    assert caught.value.code is SourceSnapshotFailureCode.ARCHIVE_INVALID
    assert not (tmp_path / "capture").exists()


def test_v2_credential_and_output_scope_fail_before_network(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    with pytest.raises(sentinel.FinancialSentinelV2AcquisitionError) as caught:
        sentinel.acquire_tushare_cn_a_share_financial_source_sentinel_v2(
            sentinel.TushareCnAShareFinancialSourceSentinelRequestV2(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=tmp_path / TOKEN / "capture",
            post=lambda _url, _body, _headers: calls.append("post") or (500, b""),
            get=lambda _url: calls.append("get") or (500, b"", ""),
        )
    assert caught.value.code is sentinel.FinancialSentinelV2FailureCode.CREDENTIAL_INPUT_INVALID
    assert calls == []

    for invalid in ("short", "x" * 27 + " " + "x" * 28):
        with pytest.raises(sentinel.FinancialSentinelV2AcquisitionError) as malformed:
            sentinel.acquire_tushare_cn_a_share_financial_source_sentinel_v2(
                sentinel.TushareCnAShareFinancialSourceSentinelRequestV2(),
                token=invalid,
                endpoint="https://fast.xiaodefa.cn",
                output_dir=tmp_path / "malformed",
                post=lambda _url, _body, _headers: calls.append("post") or (500, b""),
                get=lambda _url: calls.append("get") or (500, b"", ""),
            )
        assert malformed.value.code is sentinel.FinancialSentinelV2FailureCode.CREDENTIAL_INPUT_INVALID
    assert calls == []


def test_v2_redirect_confinement_prevents_https_downgrade() -> None:
    assert sentinel._valid_document_url(
        sentinel._REPORT_URL,
        sentinel._REPORT_URL.replace("http://", "https://"),
    )
    assert not sentinel._valid_document_url(
        sentinel._CONFIRMATION_URL,
        sentinel._CONFIRMATION_URL.replace("https://", "http://"),
    )
    assert not sentinel._valid_document_url(
        sentinel._CONFIRMATION_URL,
        "https://evil.example/finalpage/2024-06-08/1220300051.PDF",
    )


def test_v2_symlink_traversal_and_transport_fail_closed(
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

    def failed_post(
        _url: str,
        _body: dict[str, object],
        _headers: dict[str, str],
    ) -> tuple[int, bytes]:
        raise RuntimeError(TOKEN)

    with pytest.raises(sentinel.FinancialSentinelV2AcquisitionError) as caught:
        acquire(tmp_path / "transport", monkeypatch, post=failed_post)
    assert caught.value.code is sentinel.FinancialSentinelV2FailureCode.PROVIDER_TRANSPORT_FAILURE
    assert TOKEN not in str(caught.value)
    assert list(target.iterdir()) == []


def test_v2_publication_failure_cleans_partial_directory(
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


def test_v2_no_clobber_and_transient_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(AcquisitionError):
        acquire(existing, monkeypatch)

    report_statuses = [503, 200]

    def get(url: str) -> tuple[int, bytes, str]:
        if url == sentinel._REPORT_URL and report_statuses:
            status = report_statuses.pop(0)
            return status, b"" if status != 200 else REPORT, url
        return 200, CONFIRMATION if url == sentinel._CONFIRMATION_URL else REPORT, url

    post = FakePost(statuses=[500, 200])
    receipt = acquire(tmp_path / "retry", monkeypatch, post=post, get=get)
    assert receipt["provider_requests"][0]["attempts"] == 2
    assert receipt["official_documents"]["annual_report"]["attempts"] == 2


def test_v2_cli_uses_approved_proxy_token_and_endpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_acquire(request: object, **kwargs: object) -> dict[str, object]:
        captured["request"] = request
        captured.update(kwargs)
        return {"type": "fixture_receipt", "schema_version": 2}

    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    monkeypatch.setattr(
        sentinel,
        "acquire_tushare_cn_a_share_financial_source_sentinel_v2",
        fake_acquire,
    )
    assert sentinel.main(
        [
            "--endpoint",
            "https://fast.xiaodefa.cn",
            "--output-dir",
            str(tmp_path / "capture"),
        ]
    ) == 0
    assert captured["token"] == TOKEN
    assert captured["endpoint"] == "https://fast.xiaodefa.cn"
    assert captured["post"] is sentinel._proxy_stdlib_post
    assert "fixture_receipt" in capsys.readouterr().out
