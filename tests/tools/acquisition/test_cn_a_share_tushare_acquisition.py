from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.acquisition.cn_a_share_tushare import (
    AcquisitionError,
    TushareDailyListingRequest,
    acquire_daily_listing,
)


class FakePost:
    def __init__(self, responses: dict[str, tuple[int, bytes]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    def __call__(self, url: str, body: dict[str, object]) -> tuple[int, bytes]:
        self.calls.append((url, body))
        return self.responses[str(body["api_name"])]


def tushare_response(fields: list[str], items: list[list[object]]) -> bytes:
    return json.dumps(
        {"request_id": "request-id", "code": 0, "msg": None, "data": {"fields": fields, "items": items}},
        separators=(",", ":"),
    ).encode()


def test_tushare_daily_listing_acquisition_uses_env_token_without_persisting_it(
    tmp_path: Path,
) -> None:
    daily = tushare_response(
        [
            "ts_code",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "pre_close",
            "change",
            "pct_chg",
            "vol",
            "amount",
        ],
        [["000001.SZ", "20240102", 9.39, 9.42, 9.21, 9.21, 9.39, -0.18, -1.9169, 1158366.45, 1075742.252]],
    )
    listing = tushare_response(
        [
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
        ],
        [["000001.SZ", "000001", "平安银行", "深圳", "银行", "主板", "SZSE", "L", "19910403", None]],
    )
    post = FakePost({"daily": (200, daily), "stock_basic": (200, listing)})
    secret = "test-secret-must-not-be-written"
    output = tmp_path / "capture"
    result = acquire_daily_listing(
        TushareDailyListingRequest("000001.SZ", "20240102"),
        token=secret,
        output_dir=output,
        acquired_at_epoch_nanoseconds=1_800_000_000_000_000_000,
        post=post,
    )

    assert (output / "daily.json").read_bytes() == daily
    assert (output / "stock-basic.json").read_bytes() == listing
    assert result["request"] == {"trade_date": "20240102", "ts_code": "000001.SZ"}
    assert result["daily_row_count"] == 1
    assert result["listing_row_count"] == 1
    assert all(member["declared_sha256"] is None for member in result["snapshot"]["members"])
    assert all(call[0].startswith("https://") for call in post.calls)
    assert all(call[1]["token"] == secret for call in post.calls)
    assert all(secret.encode() not in path.read_bytes() for path in output.iterdir())


def test_json_escaped_token_echo_is_rejected(tmp_path: Path) -> None:
    token = 'secret"value'
    daily = tushare_response(
        [
            "ts_code",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "pre_close",
            "change",
            "pct_chg",
            "vol",
            "amount",
        ],
        [["000001.SZ", "20240102", 9.39, 9.42, 9.21, 9.21, 9.39, -0.18, -1.9169, 1158366.45, 1075742.252]],
    )
    listing = tushare_response(
        [
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
        ],
        [["000001.SZ", "000001", token, "深圳", "银行", "主板", "SZSE", "L", "19910403", None]],
    )
    output = tmp_path / "echo"
    with pytest.raises(AcquisitionError, match="credential material"):
        acquire_daily_listing(
            TushareDailyListingRequest("000001.SZ", "20240102"),
            token=token,
            output_dir=output,
            acquired_at_epoch_nanoseconds=1_800_000_000_000_000_000,
            post=FakePost({"daily": (200, daily), "stock_basic": (200, listing)}),
        )
    assert not output.exists()


def test_late_tushare_failure_leaves_no_daily_partial_output(tmp_path: Path) -> None:
    daily = tushare_response(
        [
            "ts_code",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "pre_close",
            "change",
            "pct_chg",
            "vol",
            "amount",
        ],
        [["000001.SZ", "20240102", 9.39, 9.42, 9.21, 9.21, 9.39, -0.18, -1.9169, 1158366.45, 1075742.252]],
    )
    failure = json.dumps(
        {"request_id": "id", "code": -2001, "msg": "permission denied", "data": None},
        separators=(",", ":"),
    ).encode()
    output = tmp_path / "late-failure"
    with pytest.raises(AcquisitionError, match="provider rejected"):
        acquire_daily_listing(
            TushareDailyListingRequest("000001.SZ", "20240102"),
            token="secret-value",
            output_dir=output,
            acquired_at_epoch_nanoseconds=1_800_000_000_000_000_000,
            post=FakePost({"daily": (200, daily), "stock_basic": (200, failure)}),
        )
    assert not output.exists()


def test_tushare_failure_is_atomic_and_redacted(tmp_path: Path) -> None:
    provider_failure = json.dumps(
        {"request_id": "id", "code": -2001, "msg": "permission denied", "data": None},
        separators=(",", ":"),
    ).encode()
    post = FakePost(
        {
            "daily": (200, provider_failure),
            "stock_basic": (200, provider_failure),
        }
    )
    with pytest.raises(AcquisitionError, match="provider rejected") as error:
        acquire_daily_listing(
            TushareDailyListingRequest("000001.SZ", "20240102"),
            token="secret-value",
            output_dir=tmp_path / "failed",
            acquired_at_epoch_nanoseconds=1_800_000_000_000_000_000,
            post=post,
        )
    assert "secret-value" not in str(error.value)
    assert not (tmp_path / "failed").exists()
