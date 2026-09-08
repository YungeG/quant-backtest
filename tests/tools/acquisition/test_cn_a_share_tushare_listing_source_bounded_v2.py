from __future__ import annotations

import gzip
import hashlib
import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tools.acquisition._common import AcquisitionError
from tools.acquisition.cn_a_share_tushare_listing_source_bounded_v2 import (
    TushareListingSourceBoundedRequestV2,
    _NoRedirect,
    _decode_transport_body,
    _post_with_retries,
    _stdlib_post,
    acquire_tushare_listing_source_bounded_v2,
)


STOCK_FIELDS = [
    "ts_code",
    "symbol",
    "name",
    "market",
    "exchange",
    "list_status",
    "list_date",
    "delist_date",
]
BAK_FIELDS = ["trade_date", "ts_code", "name", "list_date"]
TOKEN = "x" * 56

NAME_FIELDS = [
    "ts_code",
    "name",
    "start_date",
    "end_date",
    "ann_date",
    "change_reason",
]


class FakePost:
    def __init__(self, responses: dict[str, list[tuple[int, bytes]]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def __call__(
        self,
        url: str,
        body: dict[str, object],
        headers: dict[str, str],
    ) -> tuple[int, bytes]:
        self.calls.append((url, body, headers))
        return self.responses[str(body["api_name"])].pop(0)


def response(fields: list[str], items: list[list[object]], *, code: int = 0) -> bytes:
    return json.dumps(
        {
            "request_id": "request-id",
            "code": code,
            "data": {
                "fields": fields,
                "items": items,
                "has_more": False,
                "count": 0,
            }
            if code == 0
            else None,
            "msg": "" if code == 0 else "permission denied",
            "detail": "...",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


def request() -> TushareListingSourceBoundedRequestV2:
    return TushareListingSourceBoundedRequestV2("000001.SZ", "20240102")


def responses() -> dict[str, list[tuple[int, bytes]]]:
    return {
        "stock_basic": [
            (
                200,
                response(
                    STOCK_FIELDS,
                    [[
                        "000001.SZ",
                        "000001",
                        "平安银行",
                        "主板",
                        "SZSE",
                        "L",
                        "19910403",
                        None,
                    ]],
                ),
            )
        ],
        "bak_basic": [
            (
                200,
                response(
                    BAK_FIELDS,
                    [["20240102", "000001.SZ", "平安银行", "19910403"]],
                ),
            )
        ],
        "namechange": [
            (
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
            )
        ],
    }


def acquire(
    tmp_path: Path,
    *,
    provider: dict[str, list[tuple[int, bytes]]] | None = None,
    sleeps: list[float] | None = None,
):
    post = FakePost(provider or responses())
    delays = sleeps if sleeps is not None else []
    receipt = acquire_tushare_listing_source_bounded_v2(
        request(),
        token=TOKEN,
        endpoint="https://fast.xiaodefa.cn",
        output_dir=tmp_path / "capture",
        acquired_at_epoch_nanoseconds=1_800_000_000_000_000_000,
        post=post,
        sleep=delays.append,
    )
    return receipt, post, delays


def test_proxy_acquisition_uses_header_gzip_delay_and_no_clobber(
    tmp_path: Path,
) -> None:
    receipt, post, delays = acquire(tmp_path)
    output = tmp_path / "capture"

    assert tuple(path.name for path in sorted(output.iterdir())) == (
        "acquisition-receipt.json",
        "bak-basic.json",
        "namechange.json",
        "stock-basic.json",
    )
    assert [call[1]["api_name"] for call in post.calls] == [
        "stock_basic",
        "bak_basic",
        "namechange",
    ]
    assert all(call[0] == "https://fast.xiaodefa.cn" for call in post.calls)
    assert all("token" not in call[1] for call in post.calls)
    assert all(call[2]["Accept-Encoding"] == "gzip" for call in post.calls)
    assert all(call[2]["x-api-key"] == TOKEN for call in post.calls)
    assert delays == [0.5, 0.5]
    assert receipt["provider_key"] == "tushare.pro"
    assert receipt["transport_proxy_key"] == "xiaodefa.approved-tushare-proxy.v1"
    assert receipt["transport_endpoint"] == "https://fast.xiaodefa.cn"
    assert receipt["current_listing_row_count"] == 1
    assert receipt["historical_list_row_count"] == 1
    assert receipt["target_name_interval_count"] == 1
    members = {
        member["member_key"]: member["content_hash"]
        for member in receipt["snapshot"]["members"]
    }
    assert members == {
        f"response/{name}": "sha256:" + hashlib.sha256((output / name).read_bytes()).hexdigest()
        for name in ("stock-basic.json", "bak-basic.json", "namechange.json")
    }
    qualification = {
        key: receipt[key]
        for key in (
            "revision_closure_complete",
            "provider_completeness_qualified",
            "absence_authority",
            "historical_listing_lifecycle_qualified",
            "corporate_action_lifecycle_qualified",
            "decision_grade_eligible",
            "deployment_authorized",
        )
    }
    assert qualification == {key: False for key in qualification}
    assert all(
        TOKEN.encode() not in path.read_bytes()
        for path in output.iterdir()
    )

    before = {path.name: path.read_bytes() for path in output.iterdir()}
    with pytest.raises(AcquisitionError, match="already exists"):
        acquire_tushare_listing_source_bounded_v2(
            request(),
            token=TOKEN,
            endpoint="https://fast.xiaodefa.cn",
            output_dir=output,
            acquired_at_epoch_nanoseconds=2,
            post=FakePost(responses()),
            sleep=lambda _: None,
        )
    assert {path.name: path.read_bytes() for path in output.iterdir()} == before


def test_gzip_and_bounded_retry_are_deterministic(tmp_path: Path) -> None:
    source = b'{"code":0}'
    assert _decode_transport_body(gzip.compress(source), "gzip") == source
    assert _decode_transport_body(source, None) == source
    with pytest.raises(AcquisitionError, match="unsupported content encoding"):
        _decode_transport_body(source, "br")

    provider = responses()
    provider["stock_basic"].insert(0, (429, b"rate limited"))
    delays: list[float] = []
    _, post, delays = acquire(tmp_path, provider=provider, sleeps=delays)
    assert [call[1]["api_name"] for call in post.calls[:2]] == [
        "stock_basic",
        "stock_basic",
    ]
    assert delays == [1.0, 0.5, 0.5]


def test_stdlib_wire_is_canonical_gzip_and_redirect_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        status = 200
        headers = {"Content-Encoding": "gzip"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        @staticmethod
        def read() -> bytes:
            return gzip.compress(b'{"ok":true}')

    class Opener:
        def __init__(self, redirect: bool = False) -> None:
            self.redirect = redirect
            self.requests: list[urllib.request.Request] = []

        def open(self, request: urllib.request.Request, timeout: int):
            self.requests.append(request)
            assert timeout == 30
            if self.redirect:
                raise urllib.error.HTTPError(
                    request.full_url,
                    302,
                    "Found",
                    {
                        "Location": "https://unapproved.example",
                        "Content-Encoding": "gzip",
                    },
                    io.BytesIO(b"invalid-gzip-must-not-be-decoded"),
                )
            return Response()

    opener = Opener()

    def build_opener(*handlers):
        assert len(handlers) == 1 and isinstance(handlers[0], _NoRedirect)
        return opener

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
    headers = {
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json",
        "x-api-key": TOKEN,
    }
    status, source = _stdlib_post(
        "https://fast.xiaodefa.cn",
        {"z": "值", "a": 1},
        headers,
    )
    assert status == 200 and source == b'{"ok":true}'
    sent = opener.requests[0]
    assert sent.full_url == "https://fast.xiaodefa.cn"
    assert sent.get_method() == "POST"
    assert sent.data == '{"a":1,"z":"值"}'.encode()
    assert {key.lower(): value for key, value in sent.header_items()}["x-api-key"] == TOKEN

    redirect = Opener(redirect=True)
    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *handlers: redirect,
    )
    redirect_delays: list[float] = []
    with pytest.raises(AcquisitionError, match="HTTP status 302"):
        _post_with_retries(
            "bak_basic",
            endpoint="https://fast.xiaodefa.cn",
            body={"api_name": "bak_basic"},
            headers=headers,
            post=_stdlib_post,
            sleep=redirect_delays.append,
        )
    assert len(redirect.requests) == 1
    assert redirect_delays == []


def test_transport_decode_failure_is_retryable() -> None:
    calls = 0
    delays: list[float] = []

    def flaky(url: str, body: dict[str, object], headers: dict[str, str]):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise AcquisitionError("proxy returned invalid gzip response")
        return 200, b"accepted"

    source, attempts = _post_with_retries(
        "bak_basic",
        endpoint="https://fast.xiaodefa.cn",
        body={"api_name": "bak_basic"},
        headers={"x-api-key": TOKEN},
        post=flaky,
        sleep=delays.append,
    )
    assert source == b"accepted" and attempts == 2
    assert calls == 2 and delays == [1.0]


def test_scope_conflicts_and_provider_failure_leave_no_output(tmp_path: Path) -> None:
    cases: list[tuple[str, dict[str, list[tuple[int, bytes]]], str]] = []

    empty = responses()
    empty["bak_basic"] = [(200, response(BAK_FIELDS, []))]
    cases.append(("missing-history", empty, "bak_basic response"))

    duplicate = responses()
    duplicate["bak_basic"] = [
        (
            200,
            response(
                BAK_FIELDS,
                [
                    ["20240102", "000001.SZ", "平安银行", "19910403"],
                    ["20240102", "000001.SZ", "平安银行", "19910403"],
                ],
            ),
        )
    ]
    cases.append(("duplicate-history", duplicate, "bak_basic response"))

    conflict = responses()
    conflict["bak_basic"] = [
        (200, response(BAK_FIELDS, [["20240102", "000001.SZ", "不同名称", "19910403"]]))
    ]
    cases.append(("identity-conflict", conflict, "identity sources conflict"))

    wrong_symbol = responses()
    wrong_symbol["stock_basic"] = [
        (
            200,
            response(
                STOCK_FIELDS,
                [["000001.SZ", "999999", "平安银行", "主板", "SZSE", "L", "19910403", None]],
            ),
        )
    ]
    cases.append(("wrong-symbol", wrong_symbol, "outside fixed scope"))

    wrong_exchange = responses()
    wrong_exchange["stock_basic"] = [
        (
            200,
            response(
                STOCK_FIELDS,
                [["000001.SZ", "000001", "平安银行", "主板", "SSE", "L", "19910403", None]],
            ),
        )
    ]
    cases.append(("wrong-exchange", wrong_exchange, "outside fixed scope"))

    rejected = responses()
    rejected["bak_basic"] = [(200, response(BAK_FIELDS, [], code=40203))]
    cases.append(("permission", rejected, "provider rejected"))

    for name, provider, message in cases:
        output = tmp_path / name
        with pytest.raises(AcquisitionError, match=message) as raised:
            acquire_tushare_listing_source_bounded_v2(
                request(),
                token=TOKEN,
                endpoint="https://fast.xiaodefa.cn",
                output_dir=output,
                acquired_at_epoch_nanoseconds=1,
                post=FakePost(provider),
                sleep=lambda _: None,
            )
        assert TOKEN not in str(raised.value)
        assert not output.exists()


def test_unapproved_endpoint_and_invalid_request_fail_before_network(
    tmp_path: Path,
) -> None:
    post = FakePost(responses())
    with pytest.raises(AcquisitionError, match="endpoint is not approved"):
        acquire_tushare_listing_source_bounded_v2(
            request(),
            token=TOKEN,
            endpoint="https://api.tushare.pro",
            output_dir=tmp_path / "wrong-endpoint",
            acquired_at_epoch_nanoseconds=1,
            post=post,
        )
    assert post.calls == []

    with pytest.raises(AcquisitionError, match="exact 56-character"):
        acquire_tushare_listing_source_bounded_v2(
            request(),
            token="short",
            endpoint="https://fast.xiaodefa.cn",
            output_dir=tmp_path / "short-token",
            acquired_at_epoch_nanoseconds=1,
            post=post,
        )
    assert post.calls == []

    with pytest.raises(ValueError, match="real calendar date"):
        TushareListingSourceBoundedRequestV2("000001.SZ", "20240230")
    with pytest.raises(ValueError, match="fixed 000001.SZ / 20240102"):
        TushareListingSourceBoundedRequestV2("000002.SZ", "20240102")
    with pytest.raises(ValueError, match="fixed 000001.SZ / 20240102"):
        TushareListingSourceBoundedRequestV2("000001.SZ", "20240103")
