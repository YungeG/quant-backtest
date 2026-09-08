from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.acquisition._common import AcquisitionError, json_bytes, sha256
from tools.acquisition.cn_a_share_tushare_000703_dividend_authority_v1 import (
    Tushare000703DividendAuthorityRequest,
    acquire_tushare_000703_dividend_authority_v1,
    verify_tushare_000703_dividend_authority_v1,
)


TOKEN = "x" * 56
FIELDS = [
    "ts_code", "end_date", "ann_date", "div_proc", "stk_div", "stk_bo_rate",
    "stk_co_rate", "cash_div", "cash_div_tax", "record_date", "ex_date",
    "pay_date", "div_listdate", "imp_ann_date",
]


def _response(rows: list[list[object]], *, terminal: bool = True) -> bytes:
    return json.dumps(
        {
            "request_id": "id",
            "code": 0,
            "data": {"fields": FIELDS, "items": rows, "has_more": not terminal, "count": 0},
            "msg": "",
            "detail": "",
        },
        separators=(",", ":"),
    ).encode()


def _row(*, procedure: str = "实施") -> list[object]:
    return [
        "000703.SZ", "20231231", "20240511", procedure, 0, None, None, 0.1,
        0.1, "20240625", "20240626", "20240626", None, "20240620",
    ]


class FakePost:
    def __init__(self, source: bytes) -> None:
        self.source = source
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def __call__(
        self, endpoint: str, body: dict[str, object], headers: dict[str, str]
    ) -> tuple[int, bytes]:
        self.calls.append((endpoint, body, headers))
        return 200, self.source


def _capture(tmp_path: Path, post: FakePost) -> dict[str, object]:
    return acquire_tushare_000703_dividend_authority_v1(
        Tushare000703DividendAuthorityRequest(),
        token=TOKEN,
        endpoint="https://fast.xiaodefa.cn",
        output_dir=tmp_path / "out",
        post=post,
        clock=iter(range(10, 100)).__next__,
        sleep=lambda _: None,
    )


def test_retains_exact_proxy_dividend_response_and_development_convention(
    tmp_path: Path,
) -> None:
    post = FakePost(_response([_row()]))
    receipt = _capture(tmp_path, post)
    assert post.calls[0][0] == "https://fast.xiaodefa.cn"
    assert post.calls[0][1]["api_name"] == "dividend"
    assert post.calls[0][1]["params"] == {"ts_code": "000703.SZ"}
    assert "token" not in post.calls[0][1]
    assert post.calls[0][2]["x-api-key"] == TOKEN
    assert receipt["request"] == {
        "type": "tushare_000703_dividend_authority_request_v1",
        "schema_version": 1,
        "ts_code": "000703.SZ",
        "coverage_start_date": "20240102",
        "coverage_end_date_exclusive": "20260901",
    }
    assert receipt["action_selection"] == {
        "basis": "div_proc=实施 + record_date",
        "coverage_start_date": "20240102",
        "coverage_end_date_exclusive": "20260901",
        "selected_implementation_rows": [
            {
                "row_index": 0,
                "row_sha256": sha256(json_bytes(_row())),
                "record_date": "20240625",
                "ex_date": "20240626",
            }
        ],
        "out_of_scope_implementation_row_count": 0,
    }
    assert receipt["tushare_dividend_assumed_correct"] is True
    assert receipt["zero_row_authoritative"] is True
    assert receipt["decision_grade_eligible"] is False
    assert receipt["live_eligible"] is False
    assert receipt["deployment_authorized"] is False
    assert all(
        TOKEN.encode() not in path.read_bytes()
        for path in (tmp_path / "out").rglob("*")
        if path.is_file()
    )
    assert verify_tushare_000703_dividend_authority_v1(tmp_path / "out") == receipt


@pytest.mark.parametrize("mutation", ["raw", "receipt_hash", "timestamp", "flag"])
def test_verifier_rejects_raw_receipt_and_timestamp_tampering(
    tmp_path: Path, mutation: str
) -> None:
    _capture(tmp_path, FakePost(_response([_row()])))
    root = tmp_path / "out"
    if mutation == "raw":
        raw = root / "response/dividend.json"
        raw.write_bytes(raw.read_bytes() + b" ")
    else:
        receipt_path = root / "acquisition-receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        if mutation == "flag":
            receipt["development_only"] = 1
        else:
            key = "response_sha256" if mutation == "receipt_hash" else "response_acquired_at_epoch_nanoseconds"
            receipt["provider_request"][key] = "sha256:" + "0" * 64 if mutation == "receipt_hash" else 99
        receipt_path.write_bytes(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode())
    with pytest.raises(AcquisitionError):
        verify_tushare_000703_dividend_authority_v1(root)


@pytest.mark.parametrize(
    "source",
    (
        _response([_row()], terminal=False),
        json.dumps({"code": 0, "data": {"fields": list(reversed(FIELDS)), "items": [_row()]}}).encode(),
        _response([["000001.SZ", *_row()[1:]]]),
    ),
)
def test_nonterminal_schema_or_scope_failure_is_atomic(tmp_path: Path, source: bytes) -> None:
    with pytest.raises(AcquisitionError):
        _capture(tmp_path, FakePost(source))
    assert not (tmp_path / "out").exists()
