from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
from pathlib import Path

import pytest

from tools.acquisition import _common
from tools.acquisition._common import AcquisitionError
from tools.acquisition.cn_a_share_tushare_s0_lightweight_catalog_source_bounded_v1 import (
    TushareS0LightweightCatalogSourceBoundedRequestV1,
    acquire_tushare_s0_lightweight_catalog_source_bounded_v1,
)


TOKEN = "x" * 56
FIELDS = [
    "ts_code",
    "symbol",
    "name",
    "area",
    "industry",
    "fullname",
    "enname",
    "cnspell",
    "market",
    "exchange",
    "curr_type",
    "list_status",
    "list_date",
    "delist_date",
    "is_hs",
    "act_name",
    "act_ent_type",
]
MEMBER_KEYS = {
    "L": "response/tushare/stock_basic/listed-v1.json",
    "D": "response/tushare/stock_basic/delisted-v1.json",
    "P": "response/tushare/stock_basic/suspended-listing-v1.json",
}


class FakePost:
    def __init__(self, replies: dict[str, list[object]]) -> None:
        self.replies = replies
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def __call__(
        self,
        url: str,
        body: dict[str, object],
        headers: dict[str, str],
    ) -> tuple[int, bytes]:
        self.calls.append((url, body, headers))
        status = str(body["params"]["list_status"])  # type: ignore[index]
        reply = self.replies[status].pop(0)
        if isinstance(reply, BaseException):
            raise reply
        assert type(reply) is tuple
        return reply


def row(ts_code: str, list_status: str) -> list[object]:
    symbol = ts_code.split(".", 1)[0].removeprefix("T")
    exchange = "BSE" if ts_code.endswith(".BJ") else "SSE" if ts_code.endswith(".SH") else "SZSE"
    return [
        ts_code,
        symbol,
        f"name-{symbol}",
        None,
        None,
        f"fullname-{symbol}",
        None,
        f"spell-{symbol}",
        None,
        exchange,
        "CNY",
        list_status,
        "19910101",
        "20200101" if list_status == "D" else None,
        None,
        None,
        None,
    ]


def rows(list_status: str) -> list[list[object]]:
    if list_status == "P":
        return []
    count, start = (5550, 100000) if list_status == "L" else (339, 200000)
    values = [row(f"{start + index:06d}.SZ", list_status) for index in range(count)]
    if list_status == "L":
        values[0] = row("T600018.SH", "L")
        values[1] = row("430001.BJ", "L")
    return values


def response(
    items: list[list[object]],
    *,
    fields: list[str] = FIELDS,
    has_more: bool = False,
    count: int = 0,
) -> bytes:
    return json.dumps(
        {
            "request_id": "request-id",
            "code": 0,
            "data": {
                "fields": fields,
                "items": items,
                "has_more": has_more,
                "count": count,
            },
            "msg": "",
            "detail": "",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


def provider(values: dict[str, list[list[object]]] | None = None) -> dict[str, list[object]]:
    source = values or {status: rows(status) for status in ("L", "D", "P")}
    return {status: [(200, response(source[status]))] for status in ("L", "D", "P")}


def acquire(
    tmp_path: Path,
    *,
    replies: dict[str, list[object]] | None = None,
    sleeps: list[float] | None = None,
    clocks: list[int] | None = None,
    output_name: str = "capture",
):
    post = FakePost(replies or provider())
    delays = sleeps if sleeps is not None else []
    times = iter(clocks or [11, 22, 17])
    receipt = acquire_tushare_s0_lightweight_catalog_source_bounded_v1(
        TushareS0LightweightCatalogSourceBoundedRequestV1(),
        token=TOKEN,
        endpoint="https://fast.xiaodefa.cn",
        output_dir=tmp_path / output_name,
        post=post,
        sleep=delays.append,
        time_ns=lambda: next(times),
    )
    return receipt, post, delays


def test_capture_exactly_binds_requests_raw_bytes_snapshot_and_receipt(
    tmp_path: Path,
) -> None:
    replies = provider()
    expected_raw = {status: replies[status][0][1] for status in ("L", "D", "P")}
    receipt, post, delays = acquire(tmp_path, replies=replies)
    output = tmp_path / "capture"

    assert sorted(
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    ) == [
        "acquisition-receipt.json",
        "response/tushare/stock_basic/delisted-v1.json",
        "response/tushare/stock_basic/listed-v1.json",
        "response/tushare/stock_basic/suspended-listing-v1.json",
        "source-snapshot.json",
    ]
    assert [call[1] for call in post.calls] == [
        {
            "api_name": "stock_basic",
            "params": {"list_status": status},
            "fields": ",".join(FIELDS),
        }
        for status in ("L", "D", "P")
    ]
    assert all(call[0] == "https://fast.xiaodefa.cn" for call in post.calls)
    assert all(call[2] == {
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json",
        "x-api-key": TOKEN,
    } for call in post.calls)
    assert delays == [0.5, 0.5]
    for status, member_key in MEMBER_KEYS.items():
        assert (output / member_key).read_bytes() == expected_raw[status]
    listed = json.loads((output / MEMBER_KEYS["L"]).read_bytes())["data"]["items"]
    assert listed[0][0] == "T600018.SH" and listed[1][0] == "430001.BJ"

    assert set(receipt) == {
        "type",
        "schema_version",
        "request",
        "provider_key",
        "transport_proxy_key",
        "transport_endpoint",
        "provider_requests",
        "acquired_at_epoch_nanoseconds",
        "snapshot",
        "limitations",
        "source_bounded",
        "provider_revision_id",
        "historical_as_of_qualified",
        "provider_completeness_qualified",
        "revision_closure_complete",
        "survivorship_bias_safe",
        "industry_history_qualified",
        "trade_status_history_qualified",
        "decision_grade_eligible",
        "deployment_authorized",
        "absence_authority",
    }
    assert receipt["type"] == "tushare_s0_lightweight_catalog_source_bounded_acquisition_receipt_v1"
    assert receipt["schema_version"] == 1
    assert receipt["request"] == {
        "type": "tushare_s0_lightweight_catalog_source_bounded_request_v1",
        "schema_version": 1,
        "capture_key": "20260826-s0-candidate-01",
        "list_statuses": ["L", "D", "P"],
        "fields": FIELDS,
    }
    assert receipt["acquired_at_epoch_nanoseconds"] == 22
    assert receipt["provider_key"] == "tushare.pro"
    assert receipt["transport_proxy_key"] == "xiaodefa.approved-tushare-proxy.v1"
    assert receipt["transport_endpoint"] == "https://fast.xiaodefa.cn"
    assert [item["params"] for item in receipt["provider_requests"]] == [
        {"list_status": "L"},
        {"list_status": "D"},
        {"list_status": "P"},
    ]
    for request_item, status, timestamp, count in zip(
        receipt["provider_requests"],
        ("L", "D", "P"),
        (11, 22, 17),
        (5550, 339, 0),
        strict=True,
    ):
        raw = expected_raw[status]
        assert request_item == {
            "api_name": "stock_basic",
            "params": {"list_status": status},
            "fields": ",".join(FIELDS),
            "member_key": MEMBER_KEYS[status],
            "auth_mode": "x-api-key",
            "attempts": 1,
            "response_received_at_epoch_nanoseconds": timestamp,
            "response_byte_count": len(raw),
            "response_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "returned_row_count": count,
            "observed_envelope": {"has_more": False, "count": 0},
            "provider_revision_id": None,
            "declared_sha256": None,
        }

    snapshot = json.loads((output / "source-snapshot.json").read_text())
    assert snapshot == receipt["snapshot"]
    assert snapshot["provenance"] == {
        "vendor_key": "tushare.pro",
        "source_key": "tushare.pro.via.xiaodefa.approved-proxy.stock_basic.s0-lightweight.20260826",
        "license_ref": "tushare.pro.terms",
        "retention_policy_ref": "backtest.acquisition.candidate",
    }
    timestamps = {"L": 11, "D": 22, "P": 17}
    assert snapshot["members"] == sorted(
        [
            {
                "member_key": MEMBER_KEYS[status],
                "content_hash": "sha256:" + hashlib.sha256(expected_raw[status]).hexdigest(),
                "byte_count": len(expected_raw[status]),
                "mode": "0644",
                "acquired_at_epoch_nanoseconds": timestamps[status],
                "declared_sha256": None,
            }
            for status in ("L", "D", "P")
        ],
        key=lambda member: member["member_key"],
    )
    assert receipt["source_bounded"] is True
    assert receipt["provider_revision_id"] is None
    for key in (
        "historical_as_of_qualified",
        "provider_completeness_qualified",
        "revision_closure_complete",
        "survivorship_bias_safe",
        "industry_history_qualified",
        "trade_status_history_qualified",
        "decision_grade_eligible",
        "deployment_authorized",
        "absence_authority",
    ):
        assert receipt[key] is False
    assert receipt["limitations"] == [
        "complete historical inventory is not established",
        "provider event or as-of identity is not established",
        "code-change continuity is not established",
        "board, industry, and trade-status history are not established",
        "provider revision and terminal closure are not established",
        "survivorship safety is not established",
        "S0 authority, S1 eligibility, and later-stage qualification are not granted",
    ]
    assert all(
        stat.S_IMODE(path.stat().st_mode) == 0o600
        and TOKEN.encode() not in path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    )

    before = {
        path.relative_to(output): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    }
    with pytest.raises(AcquisitionError, match="already exists"):
        acquire(tmp_path)
    assert {
        path.relative_to(output): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    } == before


@pytest.mark.parametrize("failure", [429, 503, OSError("fixture transport")])
def test_retryable_transport_is_bounded_and_recorded(
    tmp_path: Path,
    failure: object,
) -> None:
    replies = provider()
    first = failure if isinstance(failure, BaseException) else (failure, b"retry")
    replies["L"].insert(0, first)
    receipt, post, delays = acquire(tmp_path, replies=replies)
    assert len(post.calls) == 4
    assert delays == [1.0, 0.5, 0.5]
    assert receipt["provider_requests"][0]["attempts"] == 2


@pytest.mark.parametrize("status", [302, 400])
def test_nonretryable_transport_fails_without_failover(tmp_path: Path, status: int) -> None:
    replies = provider()
    replies["L"] = [(status, b"rejected")]
    post = FakePost(replies)
    output = tmp_path / str(status)
    with pytest.raises(AcquisitionError, match="transport failed"):
        acquire_tushare_s0_lightweight_catalog_source_bounded_v1(
            TushareS0LightweightCatalogSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            post=post,
            sleep=lambda _: None,
            time_ns=lambda: 1,
        )
    assert len(post.calls) == 1
    assert post.calls[0][0] == "https://fast.xiaodefa.cn"
    assert not output.exists()


def test_each_timestamp_immediately_follows_its_response(tmp_path: Path) -> None:
    events: list[str] = []
    base = provider()

    class OrderedPost(FakePost):
        def __call__(self, url, body, headers):
            status = str(body["params"]["list_status"])
            events.append(f"post-{status}")
            return super().__call__(url, body, headers)

    post = OrderedPost(base)
    timestamps = iter((31, 41, 37))

    def clock() -> int:
        assert events[-1].startswith("post-")
        events.append("clock")
        return next(timestamps)

    receipt = acquire_tushare_s0_lightweight_catalog_source_bounded_v1(
        TushareS0LightweightCatalogSourceBoundedRequestV1(),
        token=TOKEN,
        endpoint="https://fast.xiaodefa.cn",
        output_dir=tmp_path / "ordered",
        post=post,
        sleep=lambda _: events.append("sleep"),
        time_ns=clock,
    )
    assert events == [
        "post-L",
        "clock",
        "sleep",
        "post-D",
        "clock",
        "sleep",
        "post-P",
        "clock",
    ]
    assert receipt["acquired_at_epoch_nanoseconds"] == 41


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (b'{"request_id":"x","request_id":"y"}', "unique-key JSON"),
        (
            b'{"request_id":"x","code":0,"data":NaN,"msg":"","detail":""}',
            "unique-key JSON",
        ),
        ("wrong-fields", "schema mismatch"),
        ("has-more", "not terminal"),
        ("count", "not terminal"),
        ("short", "cardinality mismatch"),
        ("short-width", "row mismatch"),
        ("overflow", "non-text field"),
    ],
)
def test_json_envelope_schema_and_cardinality_fail_closed(
    tmp_path: Path,
    source: bytes | str,
    message: str,
) -> None:
    listed = rows("L")
    if source == "wrong-fields":
        invalid = response(listed, fields=list(reversed(FIELDS)))
    elif source == "has-more":
        invalid = response(listed, has_more=True)
    elif source == "count":
        invalid = response(listed, count=5550)
    elif source == "short":
        invalid = response(listed[:-1])
    elif source == "short-width":
        listed[0].pop()
        invalid = response(listed[:-1])
    elif source == "overflow":
        invalid = response(listed).replace(b'null', b'1e999', 1)
    else:
        invalid = source
    replies = provider()
    replies["L"] = [(200, invalid)]
    output = tmp_path / message.replace(" ", "-")
    with pytest.raises(AcquisitionError, match=message):
        acquire_tushare_s0_lightweight_catalog_source_bounded_v1(
            TushareS0LightweightCatalogSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            post=FakePost(replies),
            sleep=lambda _: None,
            time_ns=lambda: 1,
        )
    assert not output.exists()


@pytest.mark.parametrize(
    ("name", "mutate", "message"),
    [
        ("status", lambda values: values["L"][0].__setitem__(11, "D"), "wrong list_status"),
        ("ts-code", lambda values: values["L"][0].__setitem__(0, ""), "empty identity"),
        ("symbol", lambda values: values["L"][0].__setitem__(1, None), "empty identity"),
        ("name", lambda values: values["L"][0].__setitem__(2, ""), "empty identity"),
        ("exchange", lambda values: values["L"][0].__setitem__(9, ""), "empty identity"),
        ("currency", lambda values: values["L"][0].__setitem__(10, ""), "empty identity"),
        ("list-date-empty", lambda values: values["L"][0].__setitem__(12, ""), "empty identity"),
        ("list-date-invalid", lambda values: values["L"][0].__setitem__(12, "20260230"), "invalid list_date"),
        ("delist-date-invalid", lambda values: values["D"][0].__setitem__(13, "19900101"), "invalid delist_date"),
        ("non-text", lambda values: values["L"][0].__setitem__(4, 7), "non-text field"),
        ("duplicate", lambda values: values["L"].__setitem__(1, copy.deepcopy(values["L"][0])), "duplicate ts_code"),
    ],
)
def test_invalid_rows_fail_atomically(tmp_path: Path, name: str, mutate, message: str) -> None:
    values = {status: rows(status) for status in ("L", "D", "P")}
    mutate(values)
    output = tmp_path / name
    with pytest.raises(AcquisitionError, match=message):
        acquire_tushare_s0_lightweight_catalog_source_bounded_v1(
            TushareS0LightweightCatalogSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            post=FakePost(provider(values)),
            sleep=lambda _: None,
            time_ns=lambda: 1,
        )
    assert not output.exists()


def test_cross_status_conflict_fails_after_individual_validation(tmp_path: Path) -> None:
    values = {status: rows(status) for status in ("L", "D", "P")}
    values["D"][0][0] = values["L"][0][0]
    output = tmp_path / "conflict"
    with pytest.raises(AcquisitionError, match="conflicting ts_code"):
        acquire_tushare_s0_lightweight_catalog_source_bounded_v1(
            TushareS0LightweightCatalogSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            post=FakePost(provider(values)),
            sleep=lambda _: None,
            time_ns=lambda: 1,
        )
    assert not output.exists()


@pytest.mark.parametrize("callback", ["transport", "retry-sleep", "inter-sleep", "clock"])
def test_callback_exceptions_are_redacted(tmp_path: Path, callback: str) -> None:
    replies = provider()
    post: object = FakePost(replies)
    delays = 0

    if callback == "transport":
        post = lambda url, body, headers: (_ for _ in ()).throw(ValueError(TOKEN))
    elif callback == "retry-sleep":
        replies["L"].insert(0, (429, b"retry"))

    def sleeper(_: float) -> None:
        nonlocal delays
        delays += 1
        if callback == "retry-sleep" or (callback == "inter-sleep" and delays == 1):
            raise ValueError(TOKEN)

    def clock() -> int:
        if callback == "clock":
            raise ValueError(TOKEN)
        return 1

    output = tmp_path / callback
    with pytest.raises(AcquisitionError) as caught:
        acquire_tushare_s0_lightweight_catalog_source_bounded_v1(
            TushareS0LightweightCatalogSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            post=post,  # type: ignore[arg-type]
            sleep=sleeper,
            time_ns=clock,
        )
    assert TOKEN not in str(caught.value)
    assert not output.exists()


@pytest.mark.parametrize("timestamp", [True, -1, 1.5])
def test_invalid_timestamps_fail_closed(tmp_path: Path, timestamp: object) -> None:
    output = tmp_path / str(timestamp)
    with pytest.raises(AcquisitionError, match="nonnegative integer"):
        acquire_tushare_s0_lightweight_catalog_source_bounded_v1(
            TushareS0LightweightCatalogSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            post=FakePost(provider()),
            sleep=lambda _: None,
            time_ns=lambda: timestamp,  # type: ignore[return-value]
        )
    assert not output.exists()


def test_request_token_endpoint_and_callbacks_fail_before_network(tmp_path: Path) -> None:
    request = TushareS0LightweightCatalogSourceBoundedRequestV1()
    with pytest.raises(TypeError):
        TushareS0LightweightCatalogSourceBoundedRequestV1("scope")  # type: ignore[call-arg]
    post = FakePost(provider())
    cases = (
        ({"request": object()}, "request must be exact"),
        ({"token": "short"}, "56-character"),
        ({"token": "x" * 55 + " "}, "56-character"),
        ({"endpoint": "https://api.tushare.pro"}, "not approved"),
        ({"post": None}, "callbacks must be callable"),
        ({"sleep": None}, "callbacks must be callable"),
        ({"time_ns": None}, "callbacks must be callable"),
    )
    for overrides, message in cases:
        arguments = {
            "request": request,
            "token": TOKEN,
            "endpoint": "https://fast.xiaodefa.cn",
            "output_dir": tmp_path / message,
            "post": post,
            "sleep": lambda _: None,
            "time_ns": lambda: 1,
        }
        arguments.update(overrides)
        with pytest.raises(AcquisitionError, match=message):
            acquire_tushare_s0_lightweight_catalog_source_bounded_v1(**arguments)  # type: ignore[arg-type]
    assert post.calls == []


@pytest.mark.parametrize("failed_fsync", [1, 6])
def test_file_and_directory_fsync_failures_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failed_fsync: int,
) -> None:
    real_fsync = _common.os.fsync
    calls = 0

    def fsync(descriptor: int) -> None:
        nonlocal calls
        calls += 1
        if calls == failed_fsync:
            raise OSError("fixture fsync failure")
        real_fsync(descriptor)

    monkeypatch.setattr(_common.os, "fsync", fsync)
    output = tmp_path / f"fsync-{failed_fsync}"
    with pytest.raises(OSError, match="fixture fsync failure"):
        acquire_tushare_s0_lightweight_catalog_source_bounded_v1(
            TushareS0LightweightCatalogSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            post=FakePost(provider()),
            sleep=lambda _: None,
            time_ns=lambda: 1,
        )
    assert not output.exists()


def test_receipt_is_opened_last_for_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_open = _common.os.open
    opened: list[str] = []

    def recording_open(
        path: os.PathLike[str] | str,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if flags & os.O_WRONLY:
            opened.append(Path(path).name)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(_common.os, "open", recording_open)
    acquire(tmp_path)
    assert opened[-1] == "acquisition-receipt.json"
