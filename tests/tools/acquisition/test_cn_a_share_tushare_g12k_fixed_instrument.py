from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

import pytest
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshot,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)

from tools.acquisition import _common
from tools.acquisition.cn_a_share_tushare_g12k_fixed_instrument import (
    _REQUEST_SCOPE_HASH,
    TushareG12KFixedInstrumentSourceBoundedRequestV1,
    _request_scope_preimage,
    acquire_tushare_g12k_fixed_instrument_source_bounded_v1,
)

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
TOKEN_SENTINEL = "redaction-sentinel-value"
FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "fixtures/market_data/providers/tushare/g12k-fixed-instrument-source-bounded-v1"
)
_EXPECTED_SCOPE_HASH = (
    "sha256:5738442bf477fc2f60542fa4b0ddee7be8d737d068077eefaa63d72489935ed7"
)


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
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()


def dividend_row() -> list[object]:
    return [
        "000001.SZ",
        "20260706",
        "20260706",
        "P",
        1,
        0.0,
        1,
        0.0,
        None,
        None,
        "20260709",
        "20260710",
        "20260711",
        "20260712",
        "20260713",
        10.0,
    ]


class FakePost:
    def __init__(self, responder: Any, statuses: list[int] | None = None) -> None:
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
        value = self.value
        self.value += 1
        return value


def acquire(
    output: Path,
    post: FakePost,
    *,
    sleep: Any | None = None,
    clock: Any | None = None,
) -> dict[str, object]:
    return acquire_tushare_g12k_fixed_instrument_source_bounded_v1(
        TushareG12KFixedInstrumentSourceBoundedRequestV1(),
        token=TOKEN_SENTINEL,
        output_dir=output,
        post=post,
        time_ns=Clock() if clock is None else clock,
        sleep=(lambda _: None) if sleep is None else sleep,
    )


def snapshot_for(bytes_payload: bytes, receipt_time: int) -> SourceSnapshot:
    return freeze_source_snapshot(
        members=(
            RawSourceMember(
                "response/dividend.json",
                bytes_payload,
                "0644",
                receipt_time,
                None,
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro",
            source_key=(
                "tushare.pro.g12k.fixed_instrument_dividend.000001.sz.20260706.20260730"
            ),
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot


def test_capture_exact_order_envelope_snapshot_and_receipt_last(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writes: list[str] = []
    real_open = _common.os.open

    def tracking_open(
        path: str | Path, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        if flags & os.O_WRONLY:
            writes.append(str(path))
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(_common.os, "open", tracking_open)
    output = tmp_path / "capture"
    post = FakePost(lambda _body: response(DIVIDEND_FIELDS, [dividend_row()]))

    receipt = acquire(output, post)
    provider_request = cast(list[dict[str, object]], receipt["provider_requests"])

    assert len(post.calls) == 1
    assert post.calls[0][0].startswith("https://api.waditu.com/dataapi/")
    assert post.calls[0][1]["api_name"] == "dividend"
    assert post.calls[0][1]["params"] == {"ts_code": "000001.SZ"}
    assert post.calls[0][1]["fields"] == ",".join(DIVIDEND_FIELDS)

    assert provider_request[0]["api_name"] == "dividend"
    assert provider_request[0]["member_key"] == "response/dividend.json"
    assert provider_request[0]["fields"] == ",".join(DIVIDEND_FIELDS)
    assert provider_request[0]["observed_envelope"] == {"has_more": False, "count": 0}
    assert provider_request[0]["attempts"] == 1
    assert provider_request[0]["declared_sha256"] is None
    assert provider_request[0]["provider_revision_id"] is None

    expected_files = {"acquisition-receipt.json", "response/dividend.json"}
    assert {
        str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()
    } == expected_files
    assert writes and Path(writes[-1]).name == "acquisition-receipt.json"
    assert (
        receipt["request"]
        == TushareG12KFixedInstrumentSourceBoundedRequestV1().to_canonical_dict()
    )
    assert receipt["request_scope_hash"] == _REQUEST_SCOPE_HASH == _EXPECTED_SCOPE_HASH

    written = (output / "response/dividend.json").read_bytes()
    assert provider_request[0]["response_byte_count"] == len(written)
    assert provider_request[0]["response_sha256"] == _common.sha256(written)
    assert provider_request[0]["returned_row_count"] == 1

    expected_snapshot = snapshot_for(
        written,
        cast(int, provider_request[0]["response_received_at_epoch_nanoseconds"]),
    )
    assert expected_snapshot.to_canonical_dict() == cast(
        dict[str, object], receipt["snapshot"]
    )

    assert (output / "acquisition-receipt.json").read_bytes() == json.dumps(
        receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode() + b"\n"
    assert TOKEN_SENTINEL not in json.dumps(receipt, ensure_ascii=False)
    assert all(
        TOKEN_SENTINEL.encode() not in path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    )


def test_retries_preserve_request_metadata(tmp_path: Path) -> None:
    sleeps: list[int] = []
    post = FakePost(
        lambda _: response(DIVIDEND_FIELDS, [dividend_row()]),
        statuses=[500, 429],
    )
    request = acquire(
        tmp_path / "retries", post, sleep=lambda value: sleeps.append(value)
    )
    assert sleeps == [1, 2]
    assert len(post.calls) == 3
    assert post.calls[0][1] == post.calls[1][1] == post.calls[2][1]
    assert request["provider_requests"][0]["attempts"] == 3


def test_no_clobber_before_transport_and_race_before_publish(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "keep"
    marker.write_bytes(b"unchanged")
    with pytest.raises(Exception, match="already exists"):
        acquire(output, FakePost(lambda _: response(DIVIDEND_FIELDS, [dividend_row()])))
    assert marker.read_bytes() == b"unchanged"

    raced = tmp_path / "raced"
    calls = 0

    def raced_responder(body: dict[str, object]) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 1:
            raced.mkdir()
            (raced / "foreign").write_bytes(b"keep")
        return response(DIVIDEND_FIELDS, [dividend_row()])

    with pytest.raises(Exception, match="already exists"):
        acquire(raced, FakePost(raced_responder))
    assert (raced / "foreign").read_bytes() == b"keep"
    assert not (raced / "acquisition-receipt.json").exists()


def test_late_provider_failure_and_retry_exhaustion_cleanup(tmp_path: Path) -> None:
    duplicate_key_payload = b'{"request_id":"id","request_id":"again","code":0,"data":{},"msg":"","detail":""}'
    with pytest.raises(Exception, match="unique-key JSON"):
        acquire(tmp_path / "bad", FakePost(lambda _: duplicate_key_payload))
    assert not (tmp_path / "bad").exists()

    post = FakePost(
        lambda _: response(DIVIDEND_FIELDS, [dividend_row()]),
        statuses=[500, 500, 500],
    )
    with pytest.raises(Exception, match="exhausted retries"):
        acquire(tmp_path / "exhausted", post)
    assert not (tmp_path / "exhausted").exists()


def test_publish_failure_cleans_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "publish-failure"
    sibling = tmp_path / "sibling"
    sibling.write_bytes(b"foreign")
    real_open = _common.os.open
    writes = 0

    def failing_open(
        path: str | Path, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        nonlocal writes
        if flags & os.O_WRONLY:
            writes += 1
            if writes == 2:
                raise OSError("publication failure")
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(_common.os, "open", failing_open)
    with pytest.raises(OSError, match="publication failure"):
        acquire(output, FakePost(lambda _: response(DIVIDEND_FIELDS, [dividend_row()])))

    assert not output.exists()
    assert sibling.read_bytes() == b"foreign"


def test_credential_echo_and_malformed_schema_and_field_validation(
    tmp_path: Path,
) -> None:
    def echoed(_: dict[str, object]) -> bytes:
        payload = json.loads(response(DIVIDEND_FIELDS, [dividend_row()]).decode())
        payload["detail"] = TOKEN_SENTINEL
        return json.dumps(payload, separators=(",", ":")).encode()

    with pytest.raises(Exception) as error:
        acquire(tmp_path / "echo", FakePost(echoed))
    assert TOKEN_SENTINEL not in str(error.value)
    assert error.value.__cause__ is None
    assert error.value.__context__ is None

    malformed_order = response(list(reversed(DIVIDEND_FIELDS)), [dividend_row()])
    bad_ts_code = response(
        DIVIDEND_FIELDS,
        [
            [
                "000002.SZ",
                "20260706",
                "20260706",
                "P",
                1,
                0.0,
                1,
                0.0,
                None,
                None,
                "20260709",
                "20260710",
                "20260711",
                "20260712",
                "20260713",
                10.0,
            ]
        ],
    )
    bad_date = response(
        DIVIDEND_FIELDS,
        [
            [
                "000001.SZ",
                "20260706",
                "bad",
                "P",
                1,
                0.0,
                1,
                0.0,
                None,
                None,
                "20260709",
                "20260710",
                "20260711",
                "20260712",
                "20260713",
                10.0,
            ]
        ],
    )
    bad_number = response(
        DIVIDEND_FIELDS,
        [
            [
                "000001.SZ",
                "20260706",
                "20260706",
                "P",
                "one",
                0.0,
                1,
                0.0,
                None,
                None,
                "20260709",
                "20260710",
                "20260711",
                "20260712",
                "20260713",
                10.0,
            ]
        ],
    )
    bad_declaration = response(
        DIVIDEND_FIELDS,
        [
            [
                "000001.SZ",
                "20260706",
                "20260706",
                None,
                1,
                0.0,
                1,
                0.0,
                None,
                None,
                "20260709",
                "20260710",
                "20260711",
                "20260712",
                "20260713",
                10.0,
            ]
        ],
    )
    duplicate_key = b'{"request_id":"id","request_id":"again","code":0,"data":{},"msg":"","detail":""}'

    cases = (
        ("field-order", malformed_order, "schema mismatch"),
        ("ts-code", bad_ts_code, "does not exact-cover request"),
        ("date", bad_date, "invalid date field"),
        ("number", bad_number, "invalid numeric field"),
        ("decl", bad_declaration, "invalid declaration field"),
        ("duplicate", duplicate_key, "unique-key JSON"),
    )
    for name, malformed, message in cases:
        with pytest.raises(Exception, match=message):
            acquire(tmp_path / name, FakePost(lambda _body, raw=malformed: raw))
        assert not (tmp_path / name).exists()


def test_has_more_and_count_metadata_retained(tmp_path: Path) -> None:
    post = FakePost(
        lambda _: response(
            DIVIDEND_FIELDS,
            [dividend_row()],
            has_more=True,
            count=18,
        )
    )
    receipt = acquire(tmp_path / "hasmore", post)
    provider_request = cast(list[dict[str, object]], receipt["provider_requests"])[0]
    assert provider_request["observed_envelope"] == {"has_more": True, "count": 18}


def test_preserves_duplicate_rows_and_pre_2000_dates(tmp_path: Path) -> None:
    historical = dividend_row()
    historical[1] = "19911231"
    historical[2] = "19911201"
    duplicated = [historical, historical]
    payload = response(DIVIDEND_FIELDS, duplicated)
    output = tmp_path / "preserve"
    receipt = acquire(output, FakePost(lambda _body: payload))
    raw = json.loads((output / "response/dividend.json").read_bytes())
    assert raw["data"]["items"] == duplicated
    assert receipt["provider_requests"][0]["returned_row_count"] == 2


def test_request_scope_hash_and_preimage_are_fixed() -> None:
    preimage = _request_scope_preimage()
    assert _REQUEST_SCOPE_HASH == _EXPECTED_SCOPE_HASH
    assert preimage["member_key"] == "response/dividend.json"
    assert tuple(preimage["fields"]) == tuple(DIVIDEND_FIELDS)
    assert preimage["instrument_id"] == {
        "type": "instrument_id",
        "venue": "xshe",
        "stable_key": "000001",
    }
    preimage["params"]["ts_code"] = "tampered"
    assert _request_scope_preimage()["params"] == {"ts_code": "000001.SZ"}


def test_live_fixture_freezes_exact_secret_free_response_and_receipt() -> None:
    response_bytes = (FIXTURE_ROOT / "response/dividend.json").read_bytes()
    receipt_bytes = (FIXTURE_ROOT / "acquisition-receipt.json").read_bytes()
    response_payload = json.loads(response_bytes)
    receipt = json.loads(receipt_bytes)
    provider_request = cast(list[dict[str, object]], receipt["provider_requests"])[0]
    rows = response_payload["data"]["items"]

    assert _common.sha256(response_bytes) == (
        "sha256:af19248549b55de24f36e120e4c416dd9a23d225c84f96edaa1534cfb377a8af"
    )
    assert _common.sha256(receipt_bytes) == (
        "sha256:5524257ee9a464d8e72df803c1493bc92e59420f0af1f6593b23a22dbb93a240"
    )
    assert receipt_bytes == _common.json_bytes(receipt)
    assert response_payload["data"]["fields"] == DIVIDEND_FIELDS
    assert len(rows) == provider_request["returned_row_count"] == 96
    assert response_payload["data"]["has_more"] is False
    assert response_payload["data"]["count"] == 0
    assert provider_request["observed_envelope"] == {"has_more": False, "count": 0}
    assert provider_request["response_sha256"] == _common.sha256(response_bytes)
    assert receipt["request_scope_hash"] == _EXPECTED_SCOPE_HASH
    assert receipt["snapshot"]["snapshot_id"] == (
        "sha256:ecb17991e82a73cc2eaaaa457ff72ccd89cb1a4a23fd595419983028f2c4a5c4"
    )
    assert receipt["snapshot"]["content_tree_hash"] == (
        "sha256:734b7b3460fda376ee105619fc4f20da33f88a3e5693de50c92389782b872809"
    )
    assert receipt["snapshot"]["provenance_hash"] == (
        "sha256:475f9a488e7e8c761bd01f55528f1185a1aacbba4868c00190d51a1200c18e0d"
    )
    expected_snapshot = snapshot_for(
        response_bytes,
        cast(int, provider_request["response_received_at_epoch_nanoseconds"]),
    )
    assert expected_snapshot.to_canonical_dict() == receipt["snapshot"]
    assert all(row[0] == "000001.SZ" for row in rows)
    assert not [
        row
        for row in rows
        if any(
            type(row[index]) is str and "20260706" <= row[index] < "20260731"
            for index in (2, 9, 10, 11, 12, 13)
        )
    ]
    assert "TUSHARE_TOKEN" not in receipt_bytes.decode()


def test_cli_requires_environment_token_and_invokes_no_arg_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tools.acquisition import cn_a_share_tushare_g12k_fixed_instrument as module

    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    with pytest.raises(
        SystemExit, match="TUSHARE_TOKEN must be provided through the environment"
    ):
        module.main(["--output-dir", str(tmp_path / "missing-token")])

    monkeypatch.setenv("TUSHARE_TOKEN", TOKEN_SENTINEL)
    module._stdlib_post = FakePost(
        lambda _body: response(DIVIDEND_FIELDS, [dividend_row()])
    )
    assert module.main(["--output-dir", str(tmp_path / "cli")]) == 0
