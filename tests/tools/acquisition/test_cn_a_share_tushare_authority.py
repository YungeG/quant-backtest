from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.acquisition.cn_a_share_tushare_authority import (
    AcquisitionError,
    TushareAuthorityRequest,
    acquire_listing_corporate_action_authority,
)


STOCK_FIELDS = [
    "ts_code",
    "symbol",
    "name",
    "area",
    "industry",
    "market",
    "exchange",
    "list_status",
    "list_date",
    "delist_date",
]
NAME_FIELDS = [
    "ts_code",
    "name",
    "start_date",
    "end_date",
    "ann_date",
    "change_reason",
]
ADJ_FIELDS = ["ts_code", "trade_date", "adj_factor"]
DIVIDEND_FIELDS = [
    "ts_code",
    "end_date",
    "ann_date",
    "div_proc",
    "stk_div",
    "stk_bo_rate",
    "stk_co_rate",
    "cash_div",
    "cash_div_tax",
    "record_date",
    "ex_date",
    "pay_date",
    "div_listdate",
    "imp_ann_date",
    "base_date",
    "base_share",
]


class FakePost:
    def __init__(self, responses: dict[str, tuple[int, bytes]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    def __call__(self, url: str, body: dict[str, object]) -> tuple[int, bytes]:
        self.calls.append((url, body))
        return self.responses[str(body["api_name"])]


def response(fields: list[str], items: list[list[object]]) -> bytes:
    return json.dumps(
        {
            "request_id": "request-id",
            "code": 0,
            "msg": "",
            "data": {
                "fields": fields,
                "items": items,
                "has_more": False,
                "count": 0,
            },
            "detail": "...",
        },
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()


def request() -> TushareAuthorityRequest:
    return TushareAuthorityRequest(
        "000001.SZ",
        "20240102",
        "20231229",
        "20240103",
    )


def responses() -> dict[str, tuple[int, bytes]]:
    return {
        "stock_basic": (
            200,
            response(
                STOCK_FIELDS,
                [[
                    "000001.SZ",
                    "000001",
                    "平安银行",
                    "深圳",
                    "银行",
                    "主板",
                    "SZSE",
                    "L",
                    "19910403",
                    None,
                ]],
            ),
        ),
        "namechange": (
            200,
            response(
                NAME_FIELDS,
                [
                    ["000001.SZ", "平安银行", "20120802", None, "20120120", "其他"],
                    ["000001.SZ", "深发展A", "20070620", "20120801", "20070614", "其他"],
                    ["000001.SZ", "S深发展A", "20061009", "20070619", "20060928", "其他"],
                    ["000001.SZ", "深发展A", "19910403", "20061008", "19910403", "其他"],
                ],
            ),
        ),
        "adj_factor": (
            200,
            response(
                ADJ_FIELDS,
                [
                    ["000001.SZ", "20240103", 116.713],
                    ["000001.SZ", "20240102", 116.713],
                    ["000001.SZ", "20231229", 116.713],
                ],
            ),
        ),
        "dividend": (200, response(DIVIDEND_FIELDS, [])),
    }


def test_authority_acquisition_is_exact_atomic_redacted_and_receipt_last(
    tmp_path: Path,
) -> None:
    secret = "secret-must-never-persist"
    post = FakePost(responses())
    output = tmp_path / "capture"
    receipt = acquire_listing_corporate_action_authority(
        request(),
        token=secret,
        output_dir=output,
        acquired_at_epoch_nanoseconds=1_800_000_000_000_000_000,
        post=post,
    )

    assert tuple(path.name for path in sorted(output.iterdir())) == (
        "acquisition-receipt.json",
        "adj-factor.json",
        "dividend-ex-date.json",
        "namechange.json",
        "stock-basic.json",
    )
    assert [call[1]["api_name"] for call in post.calls] == [
        "stock_basic",
        "namechange",
        "adj_factor",
        "dividend",
    ]
    assert all(call[0].startswith("https://") for call in post.calls)
    assert all(call[1]["token"] == secret for call in post.calls)
    assert receipt["request"] == {
        "next_trade_date": "20240103",
        "previous_trade_date": "20231229",
        "trade_date": "20240102",
        "ts_code": "000001.SZ",
    }
    assert receipt["listing_row_count"] == 1
    assert receipt["namechange_row_count"] == 4
    assert receipt["adj_factor_row_count"] == 3
    assert receipt["target_ex_date_dividend_row_count"] == 0
    assert receipt["listing_interval_covers_trade_date"] is True
    assert receipt["name_interval_covers_trade_date"] is True
    assert receipt["provider_revision_id"] is None
    assert receipt["revision_closure_complete"] is False
    assert receipt["historical_listing_status_qualified"] is False
    assert receipt["corporate_action_lifecycle_qualified"] is False
    assert receipt["decision_grade_eligible"] is False
    assert receipt["deployment_authorized"] is False
    assert len(receipt["snapshot"]["members"]) == 4
    assert all(
        member["declared_sha256"] is None
        for member in receipt["snapshot"]["members"]
    )
    assert all(secret.encode() not in path.read_bytes() for path in output.iterdir())

    before = {path.name: path.read_bytes() for path in output.iterdir()}
    with pytest.raises(AcquisitionError, match="already exists"):
        acquire_listing_corporate_action_authority(
            request(),
            token=secret,
            output_dir=output,
            acquired_at_epoch_nanoseconds=1_800_000_000_000_000_001,
            post=FakePost(responses()),
        )
    assert {path.name: path.read_bytes() for path in output.iterdir()} == before


def test_scope_or_late_provider_failure_leaves_no_partial_authority(
    tmp_path: Path,
) -> None:
    wrong_dates = responses()
    wrong_dates["adj_factor"] = (
        200,
        response(ADJ_FIELDS, [["000001.SZ", "20240102", 116.713]]),
    )
    with pytest.raises(AcquisitionError, match="adj_factor response"):
        acquire_listing_corporate_action_authority(
            request(),
            token="secret",
            output_dir=tmp_path / "wrong-dates",
            acquired_at_epoch_nanoseconds=1,
            post=FakePost(wrong_dates),
        )
    assert not (tmp_path / "wrong-dates").exists()

    late_failure = responses()
    late_failure["dividend"] = (
        200,
        json.dumps(
            {
                "request_id": "id",
                "code": -2001,
                "msg": "permission denied",
                "data": None,
                "detail": "...",
            },
            separators=(",", ":"),
        ).encode(),
    )
    with pytest.raises(AcquisitionError, match="provider rejected") as error:
        acquire_listing_corporate_action_authority(
            request(),
            token="secret",
            output_dir=tmp_path / "late-failure",
            acquired_at_epoch_nanoseconds=1,
            post=FakePost(late_failure),
        )
    assert "secret" not in str(error.value)
    assert not (tmp_path / "late-failure").exists()


def test_impossible_provider_interval_dates_are_rejected(tmp_path: Path) -> None:
    cases = (
        ("stock_basic", 0, 8, "listing interval"),
        ("namechange", 0, 2, "target interval"),
    )
    for api_name, row_index, field_index, message in cases:
        provider = responses()
        payload = json.loads(provider[api_name][1])
        payload["data"]["items"][row_index][field_index] = "20230230"
        provider[api_name] = (
            200,
            json.dumps(
                payload,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode(),
        )
        output = tmp_path / api_name
        with pytest.raises(AcquisitionError, match=message):
            acquire_listing_corporate_action_authority(
                request(),
                token="secret",
                output_dir=output,
                acquired_at_epoch_nanoseconds=1,
                post=FakePost(provider),
            )
        assert not output.exists()


def test_nonterminal_or_duplicate_key_response_is_rejected(tmp_path: Path) -> None:
    valid = responses()["adj_factor"][1]
    has_more = json.loads(valid)
    has_more["data"]["has_more"] = True
    nonzero_count = json.loads(valid)
    nonzero_count["data"]["count"] = 1
    duplicate = valid.replace(
        b'"has_more":false',
        b'"has_more":false,"has_more":false',
        1,
    )
    cases = (
        ("has-more", json.dumps(has_more, separators=(",", ":")).encode(), "not terminal"),
        ("count", json.dumps(nonzero_count, separators=(",", ":")).encode(), "not terminal"),
        ("duplicate", duplicate, "unique-key JSON"),
    )
    for name, malformed, message in cases:
        provider = responses()
        provider["adj_factor"] = (200, malformed)
        output = tmp_path / name
        with pytest.raises(AcquisitionError, match=message):
            acquire_listing_corporate_action_authority(
                request(),
                token="secret",
                output_dir=output,
                acquired_at_epoch_nanoseconds=1,
                post=FakePost(provider),
            )
        assert not output.exists()
