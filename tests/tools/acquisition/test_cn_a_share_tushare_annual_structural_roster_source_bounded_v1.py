from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from tools.acquisition import _common
from tools.acquisition import (
    cn_a_share_tushare_annual_structural_roster_source_bounded_v1 as sentinel,
)
from tools.acquisition._common import AcquisitionError

TOKEN = "x" * 56
ENDPOINT = "https://fast.xiaodefa.cn"
DATES = sentinel._ROSTER_DATES
COUNTS = sentinel._EXPECTED_ROWS
CALENDAR_FIELDS = sentinel._CALENDAR_FIELDS
ROSTER_FIELDS = sentinel._ROSTER_FIELDS


def response(
    fields: tuple[str, ...],
    items: list[list[object]],
    *,
    has_more: bool = False,
    count: int = 0,
) -> bytes:
    return json.dumps(
        {
            "request_id": "request-id",
            "code": 0,
            "data": {
                "fields": list(fields),
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


def calendar_rows() -> list[list[object]]:
    current = date(2016, 4, 30)
    end = date(2025, 5, 10)
    rows: list[list[object]] = []
    while current <= end:
        text = current.strftime("%Y%m%d")
        rows.append(
            [
                "SSE",
                text,
                int(text in DATES),
                (current - timedelta(days=1)).strftime("%Y%m%d"),
            ]
        )
        current += timedelta(days=1)
    assert len(rows) == 3298
    return list(reversed(rows))


def roster_rows(trade_date: str) -> list[list[object]]:
    values = [
        [
            trade_date,
            f"{index:06d}.SZ",
            f"name-{index}",
            None if index == 0 else f"industry-{index % 7}",
            "19910101",
        ]
        for index in range(COUNTS[trade_date])
    ]
    if values:
        values[0][1] = "000001.SZ"
        values[0][2] = "same-code-across-years"
    if len(values) > 1:
        values[1][1] = "430001.BJ"
    if len(values) > 2:
        values[2][4] = "0"
    return values


class FakePost:
    def __init__(
        self,
        mutate: Callable[[dict[str, object], bytes], bytes] | None = None,
        replies: list[object] | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.mutate = mutate
        self.replies = list(replies or [])
        self.events = events
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []
        self.raw: dict[str, bytes] = {}

    def __call__(
        self, url: str, body: dict[str, object], headers: dict[str, str]
    ) -> tuple[int, bytes]:
        self.calls.append((url, body, headers))
        if self.events is not None:
            self.events.append(f"post-{body['api_name']}-{len(self.calls)}")
        if self.replies:
            reply = self.replies.pop(0)
            if isinstance(reply, BaseException):
                raise reply
            if reply is not None:
                assert type(reply) is tuple
                return reply
        if body["api_name"] == "trade_cal":
            source = response(CALENDAR_FIELDS, calendar_rows())
            key = "calendar"
        else:
            params = body["params"]
            assert isinstance(params, dict)
            trade_date = str(params["trade_date"])
            source = response(ROSTER_FIELDS, roster_rows(trade_date))
            key = trade_date
        source = self.mutate(body, source) if self.mutate else source
        self.raw[key] = source
        return 200, source


def acquire(
    output: Path,
    *,
    post: FakePost | None = None,
    clocks: list[int] | None = None,
    sleep: Callable[[float], object] | None = None,
) -> tuple[dict[str, Any], FakePost, list[float]]:
    provider = post or FakePost()
    delays: list[float] = []
    times = iter(clocks or list(range(101, 112)))
    receipt = sentinel.acquire_tushare_annual_structural_roster_source_bounded_v1(
        sentinel.TushareAnnualStructuralRosterSourceBoundedRequestV1(),
        token=TOKEN,
        endpoint=ENDPOINT,
        output_dir=output,
        post=provider,
        sleep=sleep or delays.append,
        time_ns=lambda: next(times),
    )
    return receipt, provider, delays


def test_exact_capture_binds_wire_raw_snapshot_receipt_and_nonclaims(tmp_path: Path) -> None:
    output = tmp_path / "capture"
    clocks = [11, 27, 13, 19, 17, 23, 29, 31, 37, 41, 43]
    receipt, post, delays = acquire(output, clocks=clocks)

    expected_bodies = [
        {
            "api_name": "trade_cal",
            "params": {
                "exchange": "SSE",
                "start_date": "20160430",
                "end_date": "20250510",
            },
            "fields": ",".join(CALENDAR_FIELDS),
        }
    ] + [
        {
            "api_name": "bak_basic",
            "params": {"trade_date": trade_date},
            "fields": ",".join(ROSTER_FIELDS),
        }
        for trade_date in DATES
    ]
    assert [call[1] for call in post.calls] == expected_bodies
    assert all(call[0] == ENDPOINT for call in post.calls)
    assert all(
        call[2]
        == {
            "Accept-Encoding": "gzip",
            "Content-Type": "application/json",
            "x-api-key": TOKEN,
        }
        for call in post.calls
    )
    assert delays == [0.5] * 10

    member_keys = [sentinel._CALENDAR_MEMBER_KEY] + [
        sentinel._ROSTER_MEMBER_KEYS[trade_date] for trade_date in DATES
    ]
    expected_raw = [post.raw["calendar"]] + [post.raw[trade_date] for trade_date in DATES]
    assert sorted(
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    ) == sorted(member_keys + ["source-snapshot.json", "acquisition-receipt.json"])
    for member_key, raw in zip(member_keys, expected_raw, strict=True):
        assert (output / member_key).read_bytes() == raw
    rows_2017 = json.loads((output / sentinel._ROSTER_MEMBER_KEYS[DATES[1]]).read_bytes())[
        "data"
    ]["items"]
    assert rows_2017[0][3] is None
    assert rows_2017[1][1] == "430001.BJ"
    assert all(
        json.loads((output / sentinel._ROSTER_MEMBER_KEYS[trade_date]).read_bytes())[
            "data"
        ]["items"][0][1]
        == "000001.SZ"
        for trade_date in DATES[1:]
    )

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
        "calendar_authority_qualified",
        "historical_roster_qualified",
        "listing_membership_qualified",
        "board_history_qualified",
        "industry_history_qualified",
        "provider_completeness_qualified",
        "revision_closure_complete",
        "survivorship_bias_safe",
        "decision_grade_eligible",
        "deployment_authorized",
        "absence_authority",
        "provider_revision_id",
    }
    assert receipt["type"] == (
        "tushare_annual_structural_roster_source_bounded_acquisition_receipt_v1"
    )
    assert receipt["schema_version"] == 1
    assert receipt["request"] == {
        "type": "tushare_annual_structural_roster_source_bounded_request_v1",
        "schema_version": 1,
        "capture_key": "20260826-annual-structural-candidate-01",
        "calendar_request": {
            "exchange": "SSE",
            "start_date": "20160430",
            "end_date": "20250510",
        },
        "calendar_fields": list(CALENDAR_FIELDS),
        "roster_dates": list(DATES),
        "roster_fields": list(ROSTER_FIELDS),
    }
    assert receipt["provider_key"] == "tushare.pro"
    assert receipt["transport_proxy_key"] == "xiaodefa.approved-tushare-proxy.v1"
    assert receipt["transport_endpoint"] == ENDPOINT
    assert receipt["acquired_at_epoch_nanoseconds"] == 43
    assert receipt["limitations"] == [
        "2010-2015 annual primary-screen roster observations are unavailable in this capture",
        "20160503 zero rows are a bounded provider gap, not an empty Universe",
        "Tushare trade_cal is source-bounded and not accepted Calendar authority",
        "bak_basic row presence is not exchange listing or tradability authority",
        "bak_basic list_date=0 is retained as provider unknown, not a listing date",
        "board and official CSRC industry history are not established",
        "provider revision, absence, completeness, and terminal closure are not established",
        "formal S1, Fold, Strategy, Validation, and deployment authority are not granted",
    ]
    roster_2017 = json.loads(
        (output / "response/tushare/bak_basic/20170502-v1.json").read_text()
    )["data"]["items"]
    assert roster_2017[1][1] == "430001.BJ"
    assert roster_2017[2][4] == "0"

    assert receipt["source_bounded"] is True
    assert receipt["provider_revision_id"] is None
    for key in (
        "calendar_authority_qualified",
        "historical_roster_qualified",
        "listing_membership_qualified",
        "board_history_qualified",
        "industry_history_qualified",
        "provider_completeness_qualified",
        "revision_closure_complete",
        "survivorship_bias_safe",
        "decision_grade_eligible",
        "deployment_authorized",
        "absence_authority",
    ):
        assert receipt[key] is False

    requests = receipt["provider_requests"]
    assert isinstance(requests, list)
    expected_counts = [3298] + [COUNTS[trade_date] for trade_date in DATES]
    for item, body, member_key, raw, timestamp, count in zip(
        requests,
        expected_bodies,
        member_keys,
        expected_raw,
        clocks,
        expected_counts,
        strict=True,
    ):
        assert item == {
            "api_name": body["api_name"],
            "params": body["params"],
            "fields": body["fields"],
            "member_key": member_key,
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

    snapshot = json.loads((output / "source-snapshot.json").read_bytes())
    assert snapshot == receipt["snapshot"]
    assert snapshot["provenance"] == {
        "vendor_key": "tushare.pro",
        "source_key": (
            "tushare.pro.via.xiaodefa.approved-proxy."
            "annual-structural-roster.2016-2025.20260826"
        ),
        "license_ref": "tushare.pro.terms",
        "retention_policy_ref": "backtest.acquisition.candidate",
    }
    assert snapshot["members"] == sorted(
        [
            {
                "member_key": member_key,
                "content_hash": "sha256:" + hashlib.sha256(raw).hexdigest(),
                "byte_count": len(raw),
                "mode": "0644",
                "acquired_at_epoch_nanoseconds": timestamp,
                "declared_sha256": None,
            }
            for member_key, raw, timestamp in zip(
                member_keys, expected_raw, clocks, strict=True
            )
        ],
        key=lambda member: member["member_key"],
    )
    assert json.loads((output / "acquisition-receipt.json").read_bytes()) == receipt
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
        acquire(output)
    assert {
        path.relative_to(output): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    } == before


@pytest.mark.parametrize("failure", [429, 503, OSError("fixture transport")])
def test_retryable_transport_is_bounded_and_recorded(
    tmp_path: Path, failure: object
) -> None:
    first = failure if isinstance(failure, BaseException) else (failure, b"retry")
    post = FakePost(replies=[first, None])
    receipt, post, delays = acquire(tmp_path / "retry", post=post)
    assert len(post.calls) == 12
    assert delays == [1.0] + [0.5] * 10
    assert receipt["provider_requests"][0]["attempts"] == 2


@pytest.mark.parametrize("status", [302, 400])
def test_nonretryable_transport_fails_without_failover(tmp_path: Path, status: int) -> None:
    post = FakePost(replies=[(status, b"rejected")])
    output = tmp_path / str(status)
    with pytest.raises(AcquisitionError, match="trade_cal transport failed"):
        acquire(output, post=post)
    assert len(post.calls) == 1
    assert post.calls[0][0] == ENDPOINT
    assert not output.exists()


def test_calendar_order_drives_chronological_roster_requests(tmp_path: Path) -> None:
    _, post, _ = acquire(tmp_path / "ordered")
    assert [call[1]["params"] for call in post.calls[1:]] == [
        {"trade_date": trade_date} for trade_date in DATES
    ]


def test_each_of_eleven_timestamps_immediately_follows_its_response(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    post = FakePost(events=events)
    timestamps = iter(range(11))

    def clock() -> int:
        assert events[-1].startswith("post-")
        events.append("clock")
        return next(timestamps)

    sentinel.acquire_tushare_annual_structural_roster_source_bounded_v1(
        sentinel.TushareAnnualStructuralRosterSourceBoundedRequestV1(),
        token=TOKEN,
        endpoint=ENDPOINT,
        output_dir=tmp_path / "timestamps",
        post=post,
        sleep=lambda _: events.append("sleep"),
        time_ns=clock,
    )
    assert events == ["post-trade_cal-1", "clock"] + [
        event
        for position in range(2, 12)
        for event in ("sleep", f"post-bak_basic-{position}", "clock")
    ]


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        ("duplicate-json", "unique-key JSON"),
        ("nonfinite", "unique-key JSON"),
        ("wrong-fields", "schema mismatch"),
        ("has-more", "not terminal"),
        ("count", "not terminal"),
        ("cardinality", "cardinality mismatch"),
        ("row-width", "row mismatch"),
    ],
)
def test_envelope_schema_width_and_cardinality_fail_closed(
    tmp_path: Path, kind: str, message: str
) -> None:
    def mutate(body: dict[str, object], source: bytes) -> bytes:
        if body["api_name"] != "trade_cal":
            return source
        rows = calendar_rows()
        if kind == "duplicate-json":
            return b'{"request_id":"x","request_id":"y"}'
        if kind == "nonfinite":
            return b'{"request_id":"x","code":0,"data":NaN,"msg":"","detail":""}'
        if kind == "wrong-fields":
            return response(tuple(reversed(CALENDAR_FIELDS)), rows)
        if kind == "has-more":
            return response(CALENDAR_FIELDS, rows, has_more=True)
        if kind == "count":
            return response(CALENDAR_FIELDS, rows, count=3298)
        if kind == "cardinality":
            return response(CALENDAR_FIELDS, rows[:-1])
        rows[0].pop()
        return response(CALENDAR_FIELDS, rows)

    output = tmp_path / kind
    with pytest.raises(AcquisitionError, match=message):
        acquire(output, post=FakePost(mutate))
    assert not output.exists()


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        ("exchange", "violates request scope"),
        ("date", "violates request scope"),
        ("bool-open", "violates request scope"),
        ("pretrade", "violates request scope"),
        ("duplicate", "duplicate logical rows"),
        ("missing-open", "no annual screen date"),
        ("drift", "annual screen dates drifted"),
    ],
)
def test_calendar_scope_and_derived_dates_fail_closed(
    tmp_path: Path, kind: str, message: str
) -> None:
    def mutate(body: dict[str, object], source: bytes) -> bytes:
        if body["api_name"] != "trade_cal":
            return source
        rows = calendar_rows()
        target = next(index for index, row in enumerate(rows) if row[1] == "20160503")
        if kind == "exchange":
            rows[target][0] = "SZSE"
        elif kind == "date":
            rows[target][1] = "20250230"
        elif kind == "bool-open":
            rows[target][2] = True
        elif kind == "pretrade":
            rows[target][3] = rows[target][1]
        elif kind == "duplicate":
            rows[target] = copy.deepcopy(rows[target + 1])
        elif kind == "missing-open":
            rows[target][2] = 0
        else:
            rows[target][2] = 0
            replacement = next(
                index for index, row in enumerate(rows) if row[1] == "20160504"
            )
            rows[replacement][2] = 1
        return response(CALENDAR_FIELDS, rows)

    output = tmp_path / kind
    with pytest.raises(AcquisitionError, match=message):
        acquire(output, post=FakePost(mutate))
    assert not output.exists()


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        ("trade-date", "wrong trade_date"),
        ("ts-code", "empty identity field"),
        ("name", "empty identity field"),
        ("list-date-empty", "empty identity field"),
        ("industry", "invalid industry"),
        ("list-date-invalid", "invalid list_date"),
        ("list-date-future", "invalid list_date"),
        ("duplicate", "duplicate ts_code"),
    ],
)
def test_roster_semantics_fail_closed(tmp_path: Path, kind: str, message: str) -> None:
    target_date = "20170502"

    def mutate(body: dict[str, object], source: bytes) -> bytes:
        params = body["params"]
        if body["api_name"] != "bak_basic" or params != {"trade_date": target_date}:
            return source
        rows = roster_rows(target_date)
        if kind == "trade-date":
            rows[0][0] = "20170503"
        elif kind == "ts-code":
            rows[0][1] = ""
        elif kind == "name":
            rows[0][2] = None
        elif kind == "list-date-empty":
            rows[0][4] = ""
        elif kind == "industry":
            rows[0][3] = 7
        elif kind == "list-date-invalid":
            rows[0][4] = "20170230"
        elif kind == "list-date-future":
            rows[0][4] = "20170503"
        else:
            rows[1][1] = rows[0][1]
        return response(ROSTER_FIELDS, rows)

    output = tmp_path / kind
    with pytest.raises(AcquisitionError, match=message):
        acquire(output, post=FakePost(mutate))
    assert not output.exists()


def test_roster_cardinality_precedes_semantic_validation(tmp_path: Path) -> None:
    def mutate(body: dict[str, object], source: bytes) -> bytes:
        if body["api_name"] != "bak_basic":
            return source
        params = body["params"]
        assert isinstance(params, dict)
        trade_date = str(params["trade_date"])
        if trade_date == "20170502":
            rows = roster_rows(trade_date)[:-1]
            rows[0][0] = "wrong"
            return response(ROSTER_FIELDS, rows)
        return source

    with pytest.raises(AcquisitionError, match="cardinality mismatch"):
        acquire(tmp_path / "order", post=FakePost(mutate))


@pytest.mark.parametrize("callback", ["transport", "retry-sleep", "inter-sleep", "clock"])
def test_callback_exceptions_are_redacted(tmp_path: Path, callback: str) -> None:
    post: Any = FakePost()
    if callback == "transport":
        post = lambda url, body, headers: (_ for _ in ()).throw(ValueError(TOKEN))
    elif callback == "retry-sleep":
        post = FakePost(replies=[(429, b"retry")])
    calls = 0

    def sleeper(_: float) -> None:
        nonlocal calls
        calls += 1
        if callback == "retry-sleep" or (callback == "inter-sleep" and calls == 1):
            raise ValueError(TOKEN)

    def clock() -> int:
        if callback == "clock":
            raise ValueError(TOKEN)
        return 1

    output = tmp_path / callback
    with pytest.raises(AcquisitionError) as caught:
        sentinel.acquire_tushare_annual_structural_roster_source_bounded_v1(
            sentinel.TushareAnnualStructuralRosterSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=output,
            post=post,
            sleep=sleeper,
            time_ns=clock,
        )
    assert TOKEN not in str(caught.value)
    assert not output.exists()


@pytest.mark.parametrize("timestamp", [True, -1, 1.5])
def test_invalid_timestamps_fail_closed(tmp_path: Path, timestamp: object) -> None:
    output = tmp_path / str(timestamp)
    with pytest.raises(AcquisitionError, match="nonnegative integer"):
        sentinel.acquire_tushare_annual_structural_roster_source_bounded_v1(
            sentinel.TushareAnnualStructuralRosterSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=output,
            post=FakePost(),
            sleep=lambda _: None,
            time_ns=lambda: timestamp,  # type: ignore[return-value]
        )
    assert not output.exists()


def test_request_token_endpoint_and_callbacks_fail_before_network(tmp_path: Path) -> None:
    request = sentinel.TushareAnnualStructuralRosterSourceBoundedRequestV1()
    with pytest.raises(TypeError):
        sentinel.TushareAnnualStructuralRosterSourceBoundedRequestV1("scope")  # type: ignore[call-arg]
    post = FakePost()
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
            "endpoint": ENDPOINT,
            "output_dir": tmp_path / message,
            "post": post,
            "sleep": lambda _: None,
            "time_ns": lambda: 1,
        }
        arguments.update(overrides)
        with pytest.raises(AcquisitionError, match=message):
            sentinel.acquire_tushare_annual_structural_roster_source_bounded_v1(
                **arguments  # type: ignore[arg-type]
            )
    assert post.calls == []


@pytest.mark.parametrize("failed_fsync", [1, 14])
def test_file_and_directory_fsync_failures_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_fsync: int
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
        acquire(output)
    assert not output.exists()


def test_receipt_is_opened_last_for_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    acquire(tmp_path / "capture")
    assert opened[-1] == "acquisition-receipt.json"
