from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.acquisition._common import AcquisitionError
from tools.acquisition.cn_a_share_tushare_july_listing_presence_v1 import (
    _DATES,
    acquire_tushare_july_listing_presence_v1,
)

TOKEN = "x" * 56
FIELDS = ["trade_date", "ts_code", "name", "list_date"]


def response(trade_date: str, rows: list[list[object]] | None = None) -> bytes:
    return json.dumps(
        {
            "request_id": f"request-{trade_date}",
            "code": 0,
            "data": {
                "fields": FIELDS,
                "items": (
                    [[trade_date, "000001.SZ", "平安银行", "19910403"]]
                    if rows is None
                    else rows
                ),
                "has_more": False,
                "count": 0,
            },
            "msg": "",
            "detail": "...",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


class FakePost:
    def __init__(self, values: dict[str, list[tuple[int, bytes]]]) -> None:
        self.values = values
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def __call__(
        self,
        endpoint: str,
        body: dict[str, object],
        headers: dict[str, str],
    ) -> tuple[int, bytes]:
        self.calls.append((endpoint, body, headers))
        trade_date = body["params"]["trade_date"]  # type: ignore[index]
        return self.values[str(trade_date)].pop(0)


def values() -> dict[str, list[tuple[int, bytes]]]:
    return {date: [(200, response(date))] for date in _DATES}


def acquire(
    tmp_path: Path,
    *,
    provider: dict[str, list[tuple[int, bytes]]] | None = None,
    sleeps: list[float] | None = None,
):
    post = FakePost(values() if provider is None else provider)
    delays = [] if sleeps is None else sleeps
    receipt = acquire_tushare_july_listing_presence_v1(
        token=TOKEN,
        endpoint="https://fast.xiaodefa.cn",
        output_dir=tmp_path / "capture",
        acquired_at_epoch_nanoseconds=1,
        post=post,
        sleep=delays.append,
    )
    return receipt, post, delays


def test_exact_19_date_acquisition_is_header_only_snapshot_bound_and_no_clobber(
    tmp_path: Path,
) -> None:
    receipt, post, delays = acquire(tmp_path)
    output = tmp_path / "capture"

    assert len(post.calls) == 19
    assert [call[1]["params"]["trade_date"] for call in post.calls] == list(_DATES)  # type: ignore[index]
    assert all(call[0] == "https://fast.xiaodefa.cn" for call in post.calls)
    assert all("token" not in call[1] for call in post.calls)
    assert all(call[2]["x-api-key"] == TOKEN for call in post.calls)
    assert delays == [0.5] * 18
    assert receipt["returned_row_count"] == 19
    assert len(receipt["provider_requests"]) == 19
    assert len(receipt["snapshot"]["members"]) == 19
    assert tuple(path.name for path in sorted((output / "response/bak-basic").iterdir())) == tuple(
        f"{date}.json" for date in _DATES
    )
    assert all(
        TOKEN.encode() not in path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    )
    assert all(
        receipt[key] is False
        for key in (
            "revision_closure_complete",
            "provider_completeness_qualified",
            "absence_authority",
            "historical_listing_lifecycle_qualified",
            "corporate_action_lifecycle_qualified",
            "decision_grade_eligible",
            "deployment_authorized",
        )
    )

    before = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
    with pytest.raises(AcquisitionError, match="already exists"):
        acquire_tushare_july_listing_presence_v1(
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            acquired_at_epoch_nanoseconds=2,
            post=FakePost(values()),
        )
    assert {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()} == before


def test_retry_and_provider_conflict_are_bounded_and_publish_nothing(tmp_path: Path) -> None:
    retry = values()
    retry[_DATES[0]].insert(0, (429, b"rate limited"))
    delays: list[float] = []
    receipt, post, delays = acquire(tmp_path / "retry", provider=retry, sleeps=delays)
    assert receipt["provider_requests"][0]["attempts"] == 2
    assert len(post.calls) == 20
    assert delays == [1.0] + [0.5] * 18

    conflict = values()
    conflict[_DATES[5]] = [
        (200, response(_DATES[5], [[_DATES[5], "000001.SZ", "不同名称", "19910403"]]))
    ]
    output = tmp_path / "conflict" / "capture"
    with pytest.raises(AcquisitionError, match="does not exact-cover"):
        acquire_tushare_july_listing_presence_v1(
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            acquired_at_epoch_nanoseconds=1,
            post=FakePost(conflict),
            sleep=lambda _: None,
        )
    assert not output.exists()


def test_invalid_endpoint_token_and_time_fail_before_network(tmp_path: Path) -> None:
    post = FakePost(values())
    for changes, message in (
        ({"endpoint": "https://api.tushare.pro"}, "endpoint is not approved"),
        ({"token": "short"}, "exact 56-character"),
        ({"acquired_at_epoch_nanoseconds": -1}, "nonnegative int"),
    ):
        arguments = {
            "token": TOKEN,
            "endpoint": "https://fast.xiaodefa.cn",
            "output_dir": tmp_path / str(len(post.calls)),
            "acquired_at_epoch_nanoseconds": 1,
            "post": post,
        }
        arguments.update(changes)
        with pytest.raises(AcquisitionError, match=message):
            acquire_tushare_july_listing_presence_v1(**arguments)  # type: ignore[arg-type]
    assert post.calls == []
