from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)

from tools.acquisition import _common
from tools.acquisition._common import AcquisitionError
from tools.acquisition.cn_a_share_tushare import (
    TushareCnAShareDailySourceBoundedRequestV2,
    acquire_tushare_cn_a_share_daily_source_bounded_v2,
)

DAILY_FIELDS = [
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
]
CALENDAR_FIELDS = ["exchange", "cal_date", "is_open", "pretrade_date"]
SUSPEND_FIELDS = ["ts_code", "trade_date", "suspend_timing", "suspend_type"]
TOKEN_SENTINEL = "redaction-sentinel-value"


def response(
    fields: list[str],
    items: list[list[object]],
    *,
    has_more: bool = False,
    count: int = 0,
) -> bytes:
    return json.dumps(
        {
            "request_id": "deterministic-request-id",
            "code": 0,
            "data": {
                "fields": fields,
                "items": items,
                "has_more": has_more,
                "count": count,
            },
            "msg": "",
            "detail": "...",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


def daily_row(trade_date: str) -> list[object]:
    return [
        "000001.SZ",
        trade_date,
        9.39,
        9.42,
        9.21,
        9.21,
        9.39,
        -0.18,
        -1.9169,
        0,
        0.0,
    ]


def valid_response(body: dict[str, object]) -> bytes:
    api_name = body["api_name"]
    params = body["params"]
    assert type(params) is dict
    items: list[list[object]]
    if api_name == "daily":
        trade_date = str(params["start_date"])
        items = [daily_row(trade_date)] if trade_date == "20260706" else []
        return response(
            DAILY_FIELDS,
            items,
            has_more=trade_date == "20260706",
            count=17 if trade_date == "20260706" else 0,
        )
    if api_name == "trade_cal":
        return response(
            CALENDAR_FIELDS,
            [
                ["SZSE", "20260706", 1, "20260703"],
                ["SZSE", "20260707", 1, "20260706"],
                ["SZSE", "20260711", 0, "20260710"],
            ],
            count=99,
        )
    trade_date = str(params["trade_date"])
    if trade_date == "20260706":
        items = [["000001.SZ", trade_date, None, "S"]]
    elif trade_date == "20260707":
        items = [
            ["000001.SZ", trade_date, "09:30-10:00", "S"],
            ["000001.SZ", trade_date, "14:00-15:00", "S"],
        ]
    else:
        items = []
    return response(SUSPEND_FIELDS, items)


class FakePost:
    def __init__(
        self,
        responder: Callable[[dict[str, object]], bytes] = valid_response,
        statuses: list[int] | None = None,
    ) -> None:
        self.responder = responder
        self.statuses = list(statuses or [])
        self.calls: list[tuple[str, dict[str, object]]] = []

    def __call__(self, url: str, body: dict[str, object]) -> tuple[int, bytes]:
        self.calls.append((url, body))
        status = self.statuses.pop(0) if self.statuses else 200
        return status, b"" if status != 200 else self.responder(body)


class Clock:
    def __init__(self, start: int = 1_800_000_000_000_000_000) -> None:
        self.value = start

    def __call__(self) -> int:
        result = self.value
        self.value += 1
        return result


def acquire(
    output: Path,
    post: FakePost,
    *,
    sleep: Callable[[int], None] = lambda _: None,
) -> dict[str, object]:
    return acquire_tushare_cn_a_share_daily_source_bounded_v2(
        TushareCnAShareDailySourceBoundedRequestV2(),
        token=TOKEN_SENTINEL,
        output_dir=output,
        post=post,
        time_ns=Clock(),
        sleep=sleep,
    )


def response_paths(request: TushareCnAShareDailySourceBoundedRequestV2) -> list[str]:
    return [
        *(f"response/daily/{date}.json" for date in request.provider_dates),
        "response/trade-cal/20260706-20260730.json",
        *(f"response/suspend-d/{date}.json" for date in request.provider_dates),
    ]


def test_source_bounded_v2_captures_exact_order_envelopes_snapshot_and_receipt_last(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    request = TushareCnAShareDailySourceBoundedRequestV2()
    post = FakePost()
    output = tmp_path / "capture"
    receipt = acquire(output, post)
    provider_requests = cast(list[dict[str, object]], receipt["provider_requests"])
    snapshot_receipt = cast(dict[str, object], receipt["snapshot"])
    snapshot_members = cast(list[dict[str, object]], snapshot_receipt["members"])

    assert len(post.calls) == 51
    assert [body["api_name"] for _, body in post.calls] == [
        *("daily" for _ in request.provider_dates),
        "trade_cal",
        *("suspend_d" for _ in request.provider_dates),
    ]
    assert [entry["member_key"] for entry in provider_requests] == response_paths(
        request
    )
    assert [
        path.relative_to(output).as_posix()
        for path in sorted(output.rglob("*"))
        if path.is_file()
    ] == sorted([*response_paths(request), "acquisition-receipt.json"])
    assert Path(writes[-1]).name == "acquisition-receipt.json"
    assert json.loads((output / "acquisition-receipt.json").read_bytes()) == receipt

    daily_calls = post.calls[:25]
    assert [body["params"] for _, body in daily_calls] == [
        {"ts_code": "000001.SZ", "start_date": date, "end_date": date}
        for date in request.provider_dates
    ]
    assert all(body["fields"] == ",".join(DAILY_FIELDS) for _, body in daily_calls)
    assert post.calls[25][1]["params"] == {
        "exchange": "SZSE",
        "start_date": "20260706",
        "end_date": "20260730",
    }
    assert post.calls[25][1]["fields"] == ",".join(CALENDAR_FIELDS)
    assert [body["params"] for _, body in post.calls[26:]] == [
        {"ts_code": "000001.SZ", "trade_date": date, "suspend_type": "S"}
        for date in request.provider_dates
    ]
    assert all(
        body["fields"] == ",".join(SUSPEND_FIELDS) for _, body in post.calls[26:]
    )
    assert all(
        url.startswith("https://api.waditu.com/dataapi/") for url, _ in post.calls
    )
    assert all(body["token"] == TOKEN_SENTINEL for _, body in post.calls)

    assert provider_requests[0]["observed_envelope"] == {
        "has_more": True,
        "count": 17,
    }
    assert provider_requests[25]["observed_envelope"] == {
        "has_more": False,
        "count": 99,
    }
    assert receipt["acquired_at_epoch_nanoseconds"] == 1_800_000_000_000_000_050
    assert all(entry["declared_sha256"] is None for entry in provider_requests)
    assert all(entry["provider_revision_id"] is None for entry in provider_requests)
    assert all(
        entry["response_byte_count"]
        == len((output / str(entry["member_key"])).read_bytes())
        and entry["response_sha256"]
        == _common.sha256((output / str(entry["member_key"])).read_bytes())
        for entry in provider_requests
    )

    snapshot = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                str(entry["member_key"]),
                (output / str(entry["member_key"])).read_bytes(),
                "0644",
                cast(int, entry["response_received_at_epoch_nanoseconds"]),
                None,
            )
            for entry in provider_requests
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro",
            source_key=(
                "tushare.pro.cn_a_share_daily_source_bounded_v2."
                "000001.sz.20260706.20260730"
            ),
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    assert snapshot is not None
    assert verify_source_snapshot(snapshot).snapshot == snapshot
    assert snapshot.to_canonical_dict() == snapshot_receipt
    assert len(snapshot_members) == 51
    assert all(member["declared_sha256"] is None for member in snapshot_members)
    assert TOKEN_SENTINEL not in json.dumps(receipt, ensure_ascii=False)
    assert all(
        TOKEN_SENTINEL.encode() not in path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    )


def test_source_bounded_v2_retries_without_changing_logical_request_order(
    tmp_path: Path,
) -> None:
    sleeps: list[int] = []
    post = FakePost(statuses=[500, 429])
    receipt = acquire(tmp_path / "retry", post, sleep=sleeps.append)

    assert sleeps == [1, 2]
    assert len(post.calls) == 53
    assert post.calls[0][1] == post.calls[1][1] == post.calls[2][1]
    provider_requests = cast(list[dict[str, object]], receipt["provider_requests"])
    assert provider_requests[0]["attempts"] == 3
    assert all(entry["attempts"] == 1 for entry in provider_requests[1:])


def test_source_bounded_v2_is_no_clobber_before_transport(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "keep"
    marker.write_bytes(b"unchanged")
    post = FakePost()

    with pytest.raises(AcquisitionError, match="already exists"):
        acquire(output, post)

    assert post.calls == []
    assert marker.read_bytes() == b"unchanged"

    raced = tmp_path / "raced"
    calls = 0

    def claim_before_publish(body: dict[str, object]) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 51:
            raced.mkdir()
            (raced / "foreign").write_bytes(b"keep")
        return valid_response(body)

    with pytest.raises(AcquisitionError, match="already exists"):
        acquire(raced, FakePost(claim_before_publish))
    assert (raced / "foreign").read_bytes() == b"keep"
    assert not (raced / "acquisition-receipt.json").exists()


def test_source_bounded_v2_late_failure_and_retry_exhaustion_publish_nothing(
    tmp_path: Path,
) -> None:
    calls = 0

    def fail_last(body: dict[str, object]) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 51:
            return b'{"request_id":"id","code":0,"code":0}'
        return valid_response(body)

    late_output = tmp_path / "late"
    with pytest.raises(AcquisitionError, match="unique-key JSON") as error:
        acquire(late_output, FakePost(fail_last))
    assert TOKEN_SENTINEL not in str(error.value)
    assert not late_output.exists()

    exhausted_output = tmp_path / "exhausted"
    post = FakePost(statuses=[500, 500, 500])
    with pytest.raises(AcquisitionError, match="exhausted retries") as error:
        acquire(exhausted_output, post)
    assert TOKEN_SENTINEL not in str(error.value)
    assert not exhausted_output.exists()


def test_source_bounded_v2_publish_failure_removes_only_claimed_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "publish-failure"
    sibling = tmp_path / "keep"
    sibling.write_bytes(b"foreign")
    real_open = _common.os.open
    writes = 0

    def failing_open(
        path: os.PathLike[str] | str,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal writes
        if flags & os.O_WRONLY:
            writes += 1
            if writes == 20:
                raise OSError("deterministic publication failure")
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(_common.os, "open", failing_open)
    with pytest.raises(OSError, match="publication failure"):
        acquire(output, FakePost())

    assert not output.exists()
    assert sibling.read_bytes() == b"foreign"


def test_source_bounded_request_constructor_and_deep_tamper_fail_closed(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="exact frozen"):
        TushareCnAShareDailySourceBoundedRequestV2(ts_code="000002.SZ")
    with pytest.raises(ValueError, match="exact frozen"):
        TushareCnAShareDailySourceBoundedRequestV2(schema_version=True)
    with pytest.raises(ValueError, match="exact frozen"):
        TushareCnAShareDailySourceBoundedRequestV2(
            provider_dates=("20260706", "20260730")
        )

    request = TushareCnAShareDailySourceBoundedRequestV2()
    object.__setattr__(
        request, "provider_dates", tuple(reversed(request.provider_dates))
    )
    post = FakePost()
    with pytest.raises(AcquisitionError, match="exact Tushare"):
        acquire_tushare_cn_a_share_daily_source_bounded_v2(
            request,
            token=TOKEN_SENTINEL,
            output_dir=tmp_path / "tampered",
            post=post,
            time_ns=Clock(),
            sleep=lambda _: None,
        )
    assert post.calls == []
    assert not (tmp_path / "tampered").exists()


@pytest.mark.parametrize(
    ("malformed", "message"),
    (
        (
            b'{"request_id":"id","request_id":"again","code":0,"data":{},"msg":"","detail":""}',
            "unique-key JSON",
        ),
        (
            json.dumps(
                {
                    "request_id": 1,
                    "code": 0,
                    "data": {
                        "fields": DAILY_FIELDS,
                        "items": [],
                        "has_more": False,
                        "count": 0,
                    },
                    "msg": "",
                    "detail": "",
                },
                separators=(",", ":"),
            ).encode(),
            "invalid envelope",
        ),
        (
            json.dumps(
                {
                    "request_id": "id",
                    "code": 0,
                    "data": {
                        "fields": DAILY_FIELDS,
                        "items": [],
                        "has_more": 0,
                        "count": 0,
                    },
                    "msg": "",
                    "detail": "",
                },
                separators=(",", ":"),
            ).encode(),
            "schema mismatch",
        ),
        (
            json.dumps(
                {
                    "request_id": "id",
                    "code": 0,
                    "data": {
                        "fields": DAILY_FIELDS,
                        "items": [],
                        "has_more": False,
                        "count": True,
                    },
                    "msg": "",
                    "detail": "",
                },
                separators=(",", ":"),
            ).encode(),
            "schema mismatch",
        ),
        (response(list(reversed(DAILY_FIELDS)), []), "schema mismatch"),
    ),
)
def test_source_bounded_v2_rejects_malformed_envelope_and_field_order(
    tmp_path: Path, malformed: bytes, message: str
) -> None:
    output = tmp_path / message.replace(" ", "-")
    with pytest.raises(AcquisitionError, match=message):
        acquire(output, FakePost(lambda _: malformed))
    assert not output.exists()


@pytest.mark.parametrize(
    ("api_name", "items", "message"),
    (
        ("daily", [["000002.SZ", *daily_row("20260706")[1:]]], "daily response"),
        ("daily", [daily_row("20260706"), daily_row("20260706")], "duplicate"),
        (
            "daily",
            [["000001.SZ", "20260706", True, *daily_row("20260706")[3:]]],
            "daily response",
        ),
        ("trade_cal", [["SSE", "20260706", 1, "20260703"]], "trade_cal response"),
        (
            "trade_cal",
            [
                ["SZSE", "20260706", 1, "20260703"],
                ["SZSE", "20260706", 0, "20260703"],
            ],
            "duplicate",
        ),
        ("trade_cal", [["SZSE", "20260731", 1, "20260730"]], "trade_cal response"),
        ("trade_cal", [["SZSE", "20260706", True, "20260703"]], "trade_cal response"),
        (
            "suspend_d",
            [["000001.SZ", "20260706", None, "R"]],
            "suspend_d response",
        ),
        (
            "suspend_d",
            [
                ["000001.SZ", "20260706", None, "S"],
                ["000001.SZ", "20260706", None, "S"],
            ],
            "duplicate",
        ),
        (
            "suspend_d",
            [["000001.SZ", "20260706", " ", "S"]],
            "suspend_d response",
        ),
    ),
)
def test_source_bounded_v2_rejects_out_of_scope_and_duplicate_rows(
    tmp_path: Path, api_name: str, items: list[list[object]], message: str
) -> None:
    def malformed_scope(body: dict[str, object]) -> bytes:
        if body["api_name"] != api_name:
            return valid_response(body)
        fields = {
            "daily": DAILY_FIELDS,
            "trade_cal": CALENDAR_FIELDS,
            "suspend_d": SUSPEND_FIELDS,
        }[api_name]
        return response(fields, items)

    output = tmp_path / f"{api_name}-{message.replace(' ', '-')}"
    with pytest.raises(AcquisitionError, match=message):
        acquire(output, FakePost(malformed_scope))
    assert not output.exists()


def test_source_bounded_v2_rejects_credential_echo_without_serializing_it(
    tmp_path: Path,
) -> None:
    def echoed(body: dict[str, object]) -> bytes:
        payload = json.loads(valid_response(body))
        payload["detail"] = TOKEN_SENTINEL
        return json.dumps(payload, separators=(",", ":")).encode()

    output = tmp_path / "echo"
    with pytest.raises(AcquisitionError, match="credential material") as error:
        acquire(output, FakePost(echoed))
    assert TOKEN_SENTINEL not in str(error.value)
    assert not output.exists()


def test_source_bounded_v2_malformed_credential_echo_has_no_exception_chain(
    tmp_path: Path,
) -> None:
    def malformed(_: dict[str, object]) -> bytes:
        return f'{{"detail":"{TOKEN_SENTINEL}'.encode()

    output = tmp_path / "malformed-echo"
    with pytest.raises(AcquisitionError, match="valid unique-key JSON") as error:
        acquire(output, FakePost(malformed))

    assert TOKEN_SENTINEL not in str(error.value)
    assert TOKEN_SENTINEL not in repr(error.value)
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    assert not output.exists()
