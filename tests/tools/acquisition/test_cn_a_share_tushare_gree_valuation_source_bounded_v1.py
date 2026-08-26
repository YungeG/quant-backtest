from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import date, timedelta
from pathlib import Path

import pytest

from tools.acquisition import _common
from tools.acquisition._common import AcquisitionError
from tools.acquisition.cn_a_share_tushare_gree_valuation_source_bounded_v1 import (
    TushareGreeValuationSourceBoundedRequestV1,
    acquire_tushare_gree_valuation_source_bounded_v1,
)


FIELDS = [
    "ts_code",
    "trade_date",
    "close",
    "pe",
    "pe_ttm",
    "total_share",
    "total_mv",
    "circ_mv",
]
TOKEN = "x" * 56


class FakePost:
    def __init__(self, replies: list[tuple[int, bytes]]) -> None:
        self.replies = replies
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def __call__(
        self,
        url: str,
        body: dict[str, object],
        headers: dict[str, str],
    ) -> tuple[int, bytes]:
        self.calls.append((url, body, headers))
        return self.replies.pop(0)


def rows() -> list[list[object]]:
    start = date(2019, 5, 6)
    dates = [start + timedelta(days=offset) for offset in range(1212)]
    dates.append(date(2024, 5, 6))
    return [
        [
            "000651.SZ",
            value.strftime("%Y%m%d"),
            40.0 + index / 100,
            None if index == 0 else 10.0,
            9.0,
            563140.5741,
            24445932.3217,
            24236452.5004,
        ]
        for index, value in enumerate(dates)
    ]


def response(
    items: list[list[object]],
    *,
    fields: list[str] = FIELDS,
    code: int = 0,
    has_more: bool = False,
    count: int = 0,
) -> bytes:
    return json.dumps(
        {
            "request_id": "request-id",
            "code": code,
            "data": {
                "fields": fields,
                "items": items,
                "has_more": has_more,
                "count": count,
            }
            if code == 0
            else None,
            "msg": "" if code == 0 else "permission denied",
            "detail": "...",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


def acquire(
    tmp_path: Path,
    *,
    replies: list[tuple[int, bytes]] | None = None,
    sleeps: list[float] | None = None,
    time_ns=None,
):
    post = FakePost(replies or [(200, response(rows()))])
    delays = sleeps if sleeps is not None else []
    receipt = acquire_tushare_gree_valuation_source_bounded_v1(
        TushareGreeValuationSourceBoundedRequestV1(),
        token=TOKEN,
        endpoint="https://fast.xiaodefa.cn",
        output_dir=tmp_path / "capture",
        post=post,
        sleep=delays.append,
        time_ns=time_ns or (lambda: 1_800_000_000_000_000_000),
    )
    return receipt, post, delays


def test_capture_is_exact_immutable_source_bounded_and_credential_safe(
    tmp_path: Path,
) -> None:
    receipt, post, delays = acquire(tmp_path)
    output = tmp_path / "capture"
    raw = output / "response/tushare/daily_basic/000651.SZ-20190506-20240506-v1.json"

    assert sorted(path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()) == [
        "acquisition-receipt.json",
        "response/tushare/daily_basic/000651.SZ-20190506-20240506-v1.json",
        "source-snapshot.json",
    ]
    assert len(post.calls) == 1 and delays == []
    endpoint, body, headers = post.calls[0]
    assert endpoint == "https://fast.xiaodefa.cn"
    assert body == {
        "api_name": "daily_basic",
        "params": {
            "ts_code": "000651.SZ",
            "start_date": "20190506",
            "end_date": "20240506",
        },
        "fields": ",".join(FIELDS),
    }
    assert headers["Accept-Encoding"] == "gzip"
    assert headers["x-api-key"] == TOKEN
    assert all(
        stat.S_IMODE(path.stat().st_mode) == 0o600
        for path in output.rglob("*")
        if path.is_file()
    )
    assert all(TOKEN.encode() not in path.read_bytes() for path in output.rglob("*") if path.is_file())

    snapshot = json.loads((output / "source-snapshot.json").read_text())
    assert snapshot == receipt["snapshot"]
    assert snapshot["members"] == [
        {
            "acquired_at_epoch_nanoseconds": 1_800_000_000_000_000_000,
            "content_hash": "sha256:" + hashlib.sha256(raw.read_bytes()).hexdigest(),
            "declared_sha256": None,
            "mode": "0644",
            "member_key": "response/tushare/daily_basic/000651.SZ-20190506-20240506-v1.json",
            "byte_count": len(raw.read_bytes()),
        }
    ]
    assert receipt["provider_request"]["returned_row_count"] == 1213
    assert receipt["provider_request"]["observed_envelope"] == {
        "has_more": False,
        "count": 0,
    }
    assert receipt["source_bounded"] is True
    for key in (
        "revision_closure_complete",
        "decision_grade_eligible",
        "deployment_authorized",
    ):
        assert receipt[key] is False

    before = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
    with pytest.raises(AcquisitionError, match="already exists"):
        acquire_tushare_gree_valuation_source_bounded_v1(
            TushareGreeValuationSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            post=FakePost([(200, response(rows()))]),
            time_ns=lambda: 2,
        )
    assert {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()} == before


def test_retry_is_bounded_and_recorded(tmp_path: Path) -> None:
    replies = [(429, b"rate limited"), (200, response(rows()))]
    receipt, post, delays = acquire(tmp_path, replies=replies)
    assert len(post.calls) == 2
    assert delays == [1.0]
    assert receipt["provider_request"]["attempts"] == 2


def test_response_timestamp_is_taken_after_transport(tmp_path: Path) -> None:
    events: list[str] = []

    class OrderedPost(FakePost):
        def __call__(self, url, body, headers):
            events.append("response")
            return super().__call__(url, body, headers)

    post = OrderedPost([(200, response(rows()))])

    def clock() -> int:
        assert events == ["response"]
        events.append("timestamp")
        return 123

    receipt = acquire_tushare_gree_valuation_source_bounded_v1(
        TushareGreeValuationSourceBoundedRequestV1(),
        token=TOKEN,
        endpoint="https://fast.xiaodefa.cn",
        output_dir=tmp_path / "ordered",
        post=post,
        sleep=lambda _: None,
        time_ns=clock,
    )
    assert events == ["response", "timestamp"]
    assert receipt["acquired_at_epoch_nanoseconds"] == 123


def test_transport_and_timestamp_exceptions_are_redacted(tmp_path: Path) -> None:
    def leaking_post(url, body, headers):
        raise ValueError(TOKEN)

    with pytest.raises(AcquisitionError, match="transport failed") as transport:
        acquire_tushare_gree_valuation_source_bounded_v1(
            TushareGreeValuationSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=tmp_path / "transport",
            post=leaking_post,
            sleep=lambda _: None,
            time_ns=lambda: 1,
        )
    assert TOKEN not in str(transport.value)
    assert not (tmp_path / "transport").exists()

    with pytest.raises(AcquisitionError, match="timestamp acquisition failed") as timestamp:
        acquire_tushare_gree_valuation_source_bounded_v1(
            TushareGreeValuationSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=tmp_path / "timestamp",
            post=FakePost([(200, response(rows()))]),
            sleep=lambda _: None,
            time_ns=lambda: (_ for _ in ()).throw(ValueError(TOKEN)),
        )
    assert TOKEN not in str(timestamp.value)
    assert not (tmp_path / "timestamp").exists()


def test_publication_failure_cleans_partial_directory(
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
    output = tmp_path / "publication"
    with pytest.raises(OSError, match="fixture write failure"):
        acquire_tushare_gree_valuation_source_bounded_v1(
            TushareGreeValuationSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            post=FakePost([(200, response(rows()))]),
            sleep=lambda _: None,
            time_ns=lambda: 1,
        )
    assert not output.exists()


@pytest.mark.parametrize(
    ("name", "mutate", "message"),
    [
        ("short", lambda values: values.pop(), "cardinality mismatch"),
        (
            "duplicate",
            lambda values: values.__setitem__(1, values[0].copy()),
            "duplicate trade_date",
        ),
        (
            "wrong-issuer",
            lambda values: values[0].__setitem__(0, "000001.SZ"),
            "fixed issuer scope",
        ),
        (
            "wrong-date",
            lambda values: values[0].__setitem__(1, "20190230"),
            "fixed date scope",
        ),
        (
            "quoted-close",
            lambda values: values[0].__setitem__(2, "43.41"),
            "positive numeric",
        ),
        (
            "zero-market-value",
            lambda values: values[0].__setitem__(6, 0),
            "positive numeric",
        ),
        (
            "boolean-shares",
            lambda values: values[0].__setitem__(5, True),
            "positive numeric",
        ),
        (
            "quoted-pe",
            lambda values: values[0].__setitem__(3, "8.4"),
            "optional numeric",
        ),
    ],
)
def test_invalid_rows_fail_atomically(
    tmp_path: Path,
    name: str,
    mutate,
    message: str,
) -> None:
    values = rows()
    mutate(values)
    output = tmp_path / name
    with pytest.raises(AcquisitionError, match=message) as raised:
        acquire_tushare_gree_valuation_source_bounded_v1(
            TushareGreeValuationSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            post=FakePost([(200, response(values))]),
            sleep=lambda _: None,
            time_ns=lambda: 1,
        )
    assert TOKEN not in str(raised.value)
    assert not output.exists()


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (lambda: response(rows(), fields=list(reversed(FIELDS))), "schema mismatch"),
        (lambda: response(rows(), has_more=True), "not terminal"),
        (lambda: response(rows(), count=1213), "not terminal"),
        (lambda: response([], code=40203), "provider rejected"),
        (lambda: b'{"request_id":"x","request_id":"y"}', "unique-key JSON"),
        (lambda: b'{"request_id":"x","code":0,"data":NaN,"msg":"","detail":""}', "unique-key JSON"),
    ],
)
def test_invalid_envelopes_fail_atomically(tmp_path: Path, source, message: str) -> None:
    output = tmp_path / message.replace(" ", "-")
    with pytest.raises(AcquisitionError, match=message):
        acquire_tushare_gree_valuation_source_bounded_v1(
            TushareGreeValuationSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            post=FakePost([(200, source())]),
            sleep=lambda _: None,
            time_ns=lambda: 1,
        )
    assert not output.exists()


def test_invalid_scope_token_endpoint_and_time_fail_before_network(tmp_path: Path) -> None:
    post = FakePost([(200, response(rows()))])
    with pytest.raises(ValueError, match="fixed 000651.SZ"):
        TushareGreeValuationSourceBoundedRequestV1(ts_code="000001.SZ")
    with pytest.raises(ValueError, match="fixed 000651.SZ"):
        TushareGreeValuationSourceBoundedRequestV1(start_date="20190507")

    for kwargs, message in (
        ({"token": "short"}, "56-character"),
        ({"endpoint": "https://api.tushare.pro"}, "not approved"),
        ({"time_ns": None}, "callbacks must be callable"),
    ):
        arguments = {
            "token": TOKEN,
            "endpoint": "https://fast.xiaodefa.cn",
            "time_ns": lambda: 1,
        }
        arguments.update(kwargs)
        with pytest.raises(AcquisitionError, match=message):
            acquire_tushare_gree_valuation_source_bounded_v1(
                TushareGreeValuationSourceBoundedRequestV1(),
                output_dir=tmp_path / message,
                post=post,
                **arguments,
            )
    assert post.calls == []
