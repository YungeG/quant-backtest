from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.acquisition.cn_a_share_tushare_trade_calendar import (
    AcquisitionError,
    TushareTradeCalendarRequest,
    acquire_trade_calendar,
)


class FakePost:
    def __init__(self, response: bytes) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object]]] = []

    def __call__(self, url: str, body: dict[str, object]) -> tuple[int, bytes]:
        self.calls.append((url, body))
        return (200, self.response)


def response(item: list[object]) -> bytes:
    return json.dumps(
        {
            "request_id": "id",
            "code": 0,
            "msg": "",
            "data": {
                "fields": ["exchange", "cal_date", "is_open", "pretrade_date"],
                "items": [item],
            },
        },
        separators=(",", ":"),
    ).encode()


def test_trade_calendar_acquisition_is_exact_atomic_and_redacted(tmp_path: Path) -> None:
    request = TushareTradeCalendarRequest("SZSE", "20240102")
    post = FakePost(response(["SZSE", "20240102", 1, "20231229"]))
    output = tmp_path / "calendar"
    secret = 'secret"value'
    result = acquire_trade_calendar(
        request,
        token=secret,
        output_dir=output,
        acquired_at_epoch_nanoseconds=1_800_000_000_000_000_000,
        post=post,
    )
    assert json.loads((output / "trade-calendar.json").read_text())["data"][
        "items"
    ] == [["SZSE", "20240102", 1, "20231229"]]
    assert result["request"] == {"exchange": "SZSE", "trade_date": "20240102"}
    assert result["is_open"] is True
    assert result["pretrade_date"] == "20231229"
    assert result["snapshot"]["members"][0]["declared_sha256"] is None
    assert all(secret.encode() not in path.read_bytes() for path in output.iterdir())
    assert post.calls[0][1]["token"] == secret


@pytest.mark.parametrize(
    "item",
    (
        ["SSE", "20240102", 1, "20231229"],
        ["SZSE", 20240102, 1, "20231229"],
        ["SZSE", "20240102", True, "20231229"],
        ["SZSE", "20240102", 1, "20241399"],
        ["SZSE", "20240102", 1, "20240102"],
        ["SZSE", "20240102", 1, "20240103"],
    ),
)
def test_trade_calendar_rejects_wrong_scope_without_output(
    tmp_path: Path, item: list[object]
) -> None:
    output = tmp_path / "wrong"
    with pytest.raises(AcquisitionError, match="exact-cover"):
        acquire_trade_calendar(
            TushareTradeCalendarRequest("SZSE", "20240102"),
            token="secret",
            output_dir=output,
            acquired_at_epoch_nanoseconds=1_800_000_000_000_000_000,
            post=FakePost(response(item)),
        )
    assert not output.exists()
