from __future__ import annotations

import copy
import email.message
import gzip
import hashlib
import io
import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from tools.acquisition import cn_a_share_tushare_s2c_2011_prior_balance_source_bounded_v1 as source
from tools.acquisition._common import AcquisitionError

TOKEN = "p" * 56
ENDPOINT = "https://fast.xiaodefa.cn"
EXPECTED_FIELDS = (
    "ts_code",
    "ann_date",
    "f_ann_date",
    "end_date",
    "report_type",
    "comp_type",
    "money_cap",
    "total_assets",
    "total_liab",
    "total_hldr_eqy_inc_min_int",
    "total_hldr_eqy_exc_min_int",
    "minority_int",
    "total_liab_hldr_eqy",
    "st_borr",
    "non_cur_liab_due_1y",
    "lt_borr",
    "bond_payable",
    "st_bonds_payable",
    "update_flag",
)
EXPECTED_FALSE_FLAGS = {
    "expected_scope_extracted",
    "financial_payload_complete",
    "accounting_unit_qualified",
    "financial_availability_qualified",
    "presentation_selection_qualified",
    "financing_debt_scope_qualified",
    "provider_completeness_qualified",
    "revision_closure_complete",
    "formal_s1_qualified",
    "s2b_exact_cover_complete",
    "prior_balance_endpoint_cover_complete",
    "formal_s2_qualified",
    "strategy_authorized",
    "backtest_authorized",
    "strategy_target_authorized",
    "validation_authorized",
    "deployment_authorized",
    "decision_grade_eligible",
}
EXPECTED_LIMITATIONS = [
    "full-market SOURCE_SUPERSET is not the exact 1,995-key logical extraction scope",
    "zero provider rows never exclude an issuer",
    "provider announcement-date slicing is source-bounded, not revision or terminal authority",
    "financial statement revisions, supersession, and finality are not qualified",
    "accounting currency and unit authority are not established",
    "accepted financial availability is not established",
    "coherent presentation selection is not performed",
    "financing-note and debt-scope closure are not established",
    "no S2 qualification, Strategy, Backtest, Validation, or deployment authority is granted",
]


def row(
    *,
    ann_date: str,
    ts_code: str = "000001.SZ",
    update_flag: str = "0",
    numeric: object = 1,
) -> list[object]:
    context: dict[str, object] = {
        "ts_code": ts_code,
        "ann_date": ann_date,
        "f_ann_date": ann_date,
        "end_date": "20111231",
        "report_type": "1",
        "comp_type": "1",
        "update_flag": update_flag,
    }
    return [context.get(field, numeric) for field in EXPECTED_FIELDS]


def response(
    rows: list[list[object]],
    *,
    has_more: bool = False,
    count: int = 0,
) -> bytes:
    return json.dumps(
        {
            "request_id": "fixture-request",
            "code": 0,
            "data": {
                "fields": list(EXPECTED_FIELDS),
                "items": rows,
                "has_more": has_more,
                "count": count,
            },
            "msg": "",
            "detail": "",
        },
        separators=(",", ":"),
    ).encode()


class FakePost:
    def __init__(
        self,
        *,
        split_intervals: set[tuple[str, str]] | None = None,
        statuses: list[int | BaseException] | None = None,
        mutate: Callable[[dict[str, object], bytes], bytes] | None = None,
        duplicate_rows: bool = False,
        empty_rows: bool = False,
    ) -> None:
        self.split_intervals = split_intervals or set()
        self.statuses = list(statuses or [])
        self.mutate = mutate
        self.duplicate_rows = duplicate_rows
        self.empty_rows = empty_rows
        self.calls: list[tuple[str, dict[str, object], dict[str, str], int]] = []

    def __call__(
        self,
        url: str,
        body: dict[str, object],
        headers: dict[str, str],
        ceiling: int,
    ) -> tuple[int, bytes]:
        self.calls.append((url, copy.deepcopy(body), dict(headers), ceiling))
        status = self.statuses.pop(0) if self.statuses else 200
        if isinstance(status, BaseException):
            raise status
        if status != 200:
            return status, b"retryable"
        params = cast(dict[str, str], body["params"])
        rows = [] if self.empty_rows else [row(ann_date=params["start_date"])]
        if self.duplicate_rows:
            rows *= 2
        payload = response(
            rows,
            has_more=(params["start_date"], params["end_date"]) in self.split_intervals,
        )
        return 200, self.mutate(body, payload) if self.mutate else payload


class Clock:
    def __init__(self, value: int = 1000) -> None:
        self.value = value

    def __call__(self) -> int:
        self.value += 1
        return self.value


def reduced(monkeypatch: pytest.MonkeyPatch, *, end: str = "20120103") -> None:
    monkeypatch.setattr(source, "_ROOT_START_DATE", "20120101")
    monkeypatch.setattr(source, "_ROOT_END_DATE", end)
    monkeypatch.setattr(source, "MAX_SPLIT_DEPTH", 4)
    monkeypatch.setattr(source, "MAX_TOTAL_REQUESTS", 32)
    monkeypatch.setattr(source, "MAX_TOTAL_RESPONSE_BYTES", 1_000_000)


def acquire(
    output: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    post: source.ProxyPost | None = None,
    sleep: Callable[[float], object] | None = None,
    time_ns: Callable[[], int] | None = None,
    end: str = "20120103",
) -> tuple[dict[str, Any], FakePost, list[float]]:
    reduced(monkeypatch, end=end)
    fake = post if post is not None else FakePost()
    sleeps: list[float] = []
    receipt = source.acquire_tushare_s2c_2011_prior_balance_source_bounded_v1(
        source.TushareS2c2011PriorBalanceSourceBoundedRequestV1(),
        token=TOKEN,
        endpoint=ENDPOINT,
        output_dir=output,
        post=fake,
        sleep=sleep or sleeps.append,
        time_ns=time_ns or Clock(),
    )
    assert isinstance(fake, FakePost)
    return cast(dict[str, Any], receipt), fake, sleeps


def test_frozen_request_is_one_exact_balance_root() -> None:
    assert source._BALANCE_FIELDS == EXPECTED_FIELDS
    assert source.TushareS2c2011PriorBalanceSourceBoundedRequestV1().to_canonical_dict() == {
        "type": "tushare_s2c_2011_prior_balance_source_bounded_request_v1",
        "schema_version": 1,
        "capture_key": "20260827-s2c-2011-prior-balance-source-candidate-01",
        "api_name": "balancesheet_vip",
        "period": "20111231",
        "start_date": "20111231",
        "end_date": "20260826",
        "comp_type": "1",
        "report_type": "1",
        "fields": list(EXPECTED_FIELDS),
        "max_split_depth": 16,
        "max_total_requests": 4096,
        "max_total_response_bytes": 536_870_912,
        "minimum_delay_seconds": 0.5,
    }
    with pytest.raises(ValueError):
        source.TushareS2c2011PriorBalanceSourceBoundedRequestV1(True)


def test_recursive_capture_is_depth_first_gap_free_and_leaf_accounted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "capture"
    fake = FakePost(
        split_intervals={("20120101", "20120103"), ("20120101", "20120102")},
        duplicate_rows=True,
    )
    receipt, fake, sleeps = acquire(output, monkeypatch, post=fake)
    requests = receipt["provider_requests"]
    intervals = [
        (item["params"]["start_date"], item["params"]["end_date"])
        for item in requests
    ]
    assert intervals == [
        ("20120101", "20120103"),
        ("20120101", "20120102"),
        ("20120101", "20120101"),
        ("20120102", "20120102"),
        ("20120103", "20120103"),
    ]
    assert [item["depth"] for item in requests] == [0, 1, 2, 2, 1]
    assert sleeps == [0.5] * 4
    assert receipt["logical_request_count"] == len(requests) == 5
    assert receipt["provider_attempt_count"] == len(fake.calls) == 5
    assert receipt["decoded_response_byte_count"] == sum(
        item["response_byte_count"] for item in requests
    )
    tree = receipt["root_tree"]
    assert tree["page_member_keys"] == [item["member_key"] for item in requests]
    assert tree["terminal_leaf_member_keys"] == [
        requests[index]["member_key"] for index in (2, 3, 4)
    ]
    assert tree["maximum_depth"] == 2
    assert requests[0]["child_member_keys"] == [
        requests[1]["member_key"],
        requests[4]["member_key"],
    ]
    assert requests[1]["child_member_keys"] == [
        requests[2]["member_key"],
        requests[3]["member_key"],
    ]

    expected_paths = {item["member_key"] for item in requests} | {
        "source-snapshot.json",
        "acquisition-receipt.json",
    }
    assert {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    } == expected_paths
    assert output.stat().st_mode & 0o777 == 0o700
    assert all(
        path.stat().st_mode & 0o777 == 0o600
        for path in output.rglob("*")
        if path.is_file()
    )
    assert TOKEN.encode() not in b"".join(
        path.read_bytes() for path in output.rglob("*") if path.is_file()
    )
    assert receipt["snapshot"]["provenance"]["source_key"] == (
        "tushare.pro.via.xiaodefa.approved-proxy."
        "s2c-2011-prior-balance.20111231.20260826"
    )
    snapshot_members = {item["member_key"]: item for item in receipt["snapshot"]["members"]}
    for item in requests:
        raw = (output / item["member_key"]).read_bytes()
        assert item["response_sha256"] == "sha256:" + hashlib.sha256(raw).hexdigest()
        assert snapshot_members[item["member_key"]]["content_hash"] == item["response_sha256"]
        assert snapshot_members[item["member_key"]]["byte_count"] == len(raw)
    leaf_rows = sum(
        len(json.loads((output / key).read_bytes())["data"]["items"])
        for key in tree["terminal_leaf_member_keys"]
    )
    assert leaf_rows == 6


def test_request_body_headers_and_receipt_authority_are_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt, fake, _ = acquire(tmp_path / "capture", monkeypatch, end="20120101")
    assert fake.calls == [
        (
            ENDPOINT,
            {
                "api_name": "balancesheet_vip",
                "params": {
                    "period": "20111231",
                    "comp_type": "1",
                    "report_type": "1",
                    "start_date": "20120101",
                    "end_date": "20120101",
                },
                "fields": ",".join(EXPECTED_FIELDS),
            },
            {
                "Accept-Encoding": "gzip",
                "Content-Type": "application/json",
                "x-api-key": TOKEN,
            },
            1_000_000,
        )
    ]
    assert receipt["source_bounded"] is True
    assert receipt["source_superset"] is True
    assert receipt["provider_revision_id"] is None
    assert receipt["limitations"] == EXPECTED_LIMITATIONS
    assert set(source._FALSE_FLAGS) == EXPECTED_FALSE_FLAGS
    assert {flag for flag in EXPECTED_FALSE_FLAGS if receipt[flag] is False} == EXPECTED_FALSE_FLAGS
    assert set(receipt) == {
        "type",
        "schema_version",
        "request",
        "provider_key",
        "transport_proxy_key",
        "transport_endpoint",
        "provider_requests",
        "root_tree",
        "logical_request_count",
        "provider_attempt_count",
        "decoded_response_byte_count",
        "acquired_at_epoch_nanoseconds",
        "snapshot",
        "limitations",
        "source_bounded",
        "source_superset",
        "provider_revision_id",
        *EXPECTED_FALSE_FLAGS,
    }


def test_retry_spacing_ceilings_and_failures_publish_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleeps: list[float] = []
    receipt, fake, _ = acquire(
        tmp_path / "retry",
        monkeypatch,
        post=FakePost(statuses=[500, 200]),
        sleep=sleeps.append,
        end="20120101",
    )
    assert len(fake.calls) == 2
    assert [call[3] for call in fake.calls] == [1_000_000, 1_000_000 - len(b"retryable")]
    assert receipt["logical_request_count"] == 1
    assert receipt["provider_attempt_count"] == 2
    assert receipt["decoded_response_byte_count"] == (
        len(b"retryable") + receipt["provider_requests"][0]["response_byte_count"]
    )
    assert receipt["provider_requests"][0]["attempts"] == 2
    assert sleeps == [1.0]

    transport = FakePost(statuses=[OSError("fixture"), 200])
    receipt, transport, _ = acquire(
        tmp_path / "transport-retry",
        monkeypatch,
        post=transport,
        sleep=lambda _seconds: None,
        end="20120101",
    )
    assert len(transport.calls) == 2
    assert receipt["provider_attempt_count"] == 2
    assert receipt["decoded_response_byte_count"] == receipt["provider_requests"][0][
        "response_byte_count"
    ]

    reduced(monkeypatch, end="20120102")
    monkeypatch.setattr(source, "MAX_SPLIT_DEPTH", 0)
    with pytest.raises(AcquisitionError, match="depth"):
        source.acquire_tushare_s2c_2011_prior_balance_source_bounded_v1(
            source.TushareS2c2011PriorBalanceSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=tmp_path / "depth",
            post=FakePost(split_intervals={("20120101", "20120102")}),
            sleep=lambda _seconds: None,
            time_ns=Clock(),
        )
    assert not (tmp_path / "depth").exists()

    reduced(monkeypatch, end="20120101")
    monkeypatch.setattr(source, "MAX_TOTAL_REQUESTS", 1)
    request_ceiling = FakePost(statuses=[500, 200])
    with pytest.raises(AcquisitionError, match="request ceiling"):
        source.acquire_tushare_s2c_2011_prior_balance_source_bounded_v1(
            source.TushareS2c2011PriorBalanceSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=tmp_path / "requests",
            post=request_ceiling,
            sleep=lambda _seconds: None,
            time_ns=Clock(),
        )
    assert len(request_ceiling.calls) == 1

    reduced(monkeypatch, end="20120101")
    monkeypatch.setattr(source, "MAX_TOTAL_RESPONSE_BYTES", len(b"retryable"))
    byte_ceiling = FakePost(statuses=[500, 200])
    with pytest.raises(AcquisitionError, match="byte ceiling"):
        source.acquire_tushare_s2c_2011_prior_balance_source_bounded_v1(
            source.TushareS2c2011PriorBalanceSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=tmp_path / "retry-bytes",
            post=byte_ceiling,
            sleep=lambda _seconds: None,
            time_ns=Clock(),
        )
    assert [call[3] for call in byte_ceiling.calls] == [len(b"retryable"), 0]

    reduced(monkeypatch, end="20120101")
    monkeypatch.setattr(source, "MAX_TOTAL_RESPONSE_BYTES", 1)
    with pytest.raises(AcquisitionError, match="byte ceiling"):
        source.acquire_tushare_s2c_2011_prior_balance_source_bounded_v1(
            source.TushareS2c2011PriorBalanceSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=tmp_path / "bytes",
            post=FakePost(),
            sleep=lambda _seconds: None,
            time_ns=Clock(),
        )


def test_invalid_envelopes_rows_credentials_and_callback_mutation_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    valid = response([row(ann_date="20120101")])
    for payload in (
        b"not-json",
        valid.replace(b'"code":0', b'"code":0,"code":0'),
        valid.replace(b'"has_more":false', b'"has_more":1'),
        valid.replace(b'"count":0', b'"count":1'),
    ):
        with pytest.raises(AcquisitionError):
            source._parse_page(payload, TOKEN)

    raw_secret = json.loads(valid)
    raw_secret["request_id"] = TOKEN
    with pytest.raises(AcquisitionError, match="credential"):
        source._parse_page(json.dumps(raw_secret).encode(), TOKEN)
    escaped = json.dumps(raw_secret).replace(TOKEN, "\\u0070" * len(TOKEN)).encode()
    with pytest.raises(AcquisitionError, match="credential"):
        source._parse_page(escaped, TOKEN)

    invalid = row(ann_date="20120101")
    invalid[EXPECTED_FIELDS.index("report_type")] = "2"
    with pytest.raises(AcquisitionError, match="row scope"):
        source._validate_rows([invalid], start_date="20120101", end_date="20120101")
    source._validate_rows(
        [
            row(ann_date="20120101", ts_code="430001.BJ", numeric=None),
            row(ann_date="20120101", ts_code="LEGACY.CODE.SH", update_flag="1", numeric=2.5),
        ],
        start_date="20120101",
        end_date="20120101",
    )

    def mutate(body: dict[str, object], payload: bytes) -> bytes:
        cast(dict[str, object], body["params"])["period"] = "forged"
        return payload

    with pytest.raises(AcquisitionError, match="transport"):
        acquire(tmp_path / "mutation", monkeypatch, post=FakePost(mutate=mutate))


def test_zero_row_source_superset_publication_never_excludes_an_issuer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "zero-row"
    receipt, _, _ = acquire(
        output,
        monkeypatch,
        post=FakePost(empty_rows=True),
        end="20120101",
    )
    request = receipt["provider_requests"][0]
    assert request["returned_row_count"] == 0
    assert json.loads((output / request["member_key"]).read_bytes())["data"]["items"] == []
    assert receipt["source_superset"] is True
    assert receipt["expected_scope_extracted"] is False
    assert receipt["provider_completeness_qualified"] is False
    assert "zero provider rows never exclude an issuer" in receipt["limitations"]
    assert (output / "acquisition-receipt.json").is_file()


def test_snapshot_reconstruction_failure_and_credential_scan_are_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reduced(monkeypatch, end="20120101")
    monkeypatch.setattr(
        source,
        "verify_source_snapshot",
        lambda _snapshot: SimpleNamespace(failure=SimpleNamespace(code="fixture")),
    )
    with pytest.raises(AcquisitionError, match="verification"):
        source.acquire_tushare_s2c_2011_prior_balance_source_bounded_v1(
            source.TushareS2c2011PriorBalanceSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=tmp_path / "snapshot",
            post=FakePost(),
            sleep=lambda _seconds: None,
            time_ns=Clock(),
        )
    assert not (tmp_path / "snapshot").exists()

    monkeypatch.undo()
    with pytest.raises(AcquisitionError, match="credential"):
        acquire(
            tmp_path / "secret",
            monkeypatch,
            post=FakePost(
                mutate=lambda _body, payload: payload.replace(
                    b'"request_id":"fixture-request"',
                    b'"request_id":"' + TOKEN.encode() + b'"',
                )
            ),
            end="20120101",
        )
    assert not (tmp_path / "secret").exists()


def test_created_ancestor_nested_and_staging_substitution_fail_without_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_stat = os.stat
    ancestor_parent = tmp_path / "ancestor-parent"
    ancestor_parent.mkdir()
    swapped_ancestor = False

    def swap_ancestor(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        nonlocal swapped_ancestor
        identity = real_stat(path, *args, **kwargs)
        if path == "created" and not swapped_ancestor:
            swapped_ancestor = True
            descriptor = cast(int, kwargs["dir_fd"])
            os.rename("created", "created-original", src_dir_fd=descriptor, dst_dir_fd=descriptor)
            os.mkdir("created", 0o700, dir_fd=descriptor)
        return identity

    monkeypatch.setattr(source.os, "stat", swap_ancestor)
    with pytest.raises(OSError, match="changed before open"):
        source._open_directory_path(ancestor_parent / "created" / "child", create=True)
    assert (ancestor_parent / "created").is_dir()
    assert (ancestor_parent / "created-original").is_dir()

    monkeypatch.undo()
    nested_root = tmp_path / "nested-root"
    nested_root.mkdir()
    root_fd = os.open(nested_root, os.O_RDONLY | os.O_DIRECTORY)
    swapped_nested = False

    def swap_nested(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        nonlocal swapped_nested
        identity = real_stat(path, *args, **kwargs)
        if path == "nested" and not swapped_nested:
            swapped_nested = True
            descriptor = cast(int, kwargs["dir_fd"])
            os.rename("nested", "nested-original", src_dir_fd=descriptor, dst_dir_fd=descriptor)
            os.mkdir("nested", 0o700, dir_fd=descriptor)
        return identity

    monkeypatch.setattr(source.os, "stat", swap_nested)
    try:
        with pytest.raises(OSError, match="changed before open"):
            source._open_relative_directory(root_fd, ("nested",), create=True)
    finally:
        os.close(root_fd)
    assert (nested_root / "nested").is_dir()
    assert (nested_root / "nested-original").is_dir()

    monkeypatch.undo()
    output = tmp_path / "staging-parent" / "capture"
    real_open = os.open
    staging_names: list[str] = []

    def swap_staging(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if (
            isinstance(path, str)
            and path.startswith(".capture.staging-")
            and path not in staging_names
        ):
            staging_names.append(path)
            descriptor = cast(int, kwargs["dir_fd"])
            os.rename(path, path + "-original", src_dir_fd=descriptor, dst_dir_fd=descriptor)
            os.mkdir(path, 0o700, dir_fd=descriptor)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(source.os, "open", swap_staging)
    with pytest.raises(AcquisitionError, match="publication"):
        acquire(output, monkeypatch, end="20120101")
    assert len(staging_names) == 1
    assert (output.parent / staging_names[0]).is_dir()
    assert (output.parent / (staging_names[0] + "-original")).is_dir()
    assert not output.exists()


def test_output_symlinks_parent_swap_and_target_collision_never_clobber(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(target, target_is_directory=True)
    calls: list[str] = []
    with pytest.raises(AcquisitionError, match="output path"):
        source.acquire_tushare_s2c_2011_prior_balance_source_bounded_v1(
            source.TushareS2c2011PriorBalanceSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=linked / "capture",
            post=lambda *_args: calls.append("post") or (500, b""),
        )
    assert calls == []
    with pytest.raises(AcquisitionError, match="output path"):
        source.acquire_tushare_s2c_2011_prior_balance_source_bounded_v1(
            source.TushareS2c2011PriorBalanceSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=tmp_path / "safe" / ".." / "capture",
            post=lambda *_args: (500, b""),
        )

    parent = tmp_path / "race-parent"
    parent.mkdir()
    moved = tmp_path / "moved-parent"

    class SwapPost(FakePost):
        def __call__(self, *args: object) -> tuple[int, bytes]:
            result = super().__call__(*cast(tuple[Any, ...], args))
            parent.rename(moved)
            parent.mkdir()
            return result

    with pytest.raises(AcquisitionError, match="publication"):
        acquire(parent / "capture", monkeypatch, post=SwapPost(), end="20120101")
    assert not (parent / "capture").exists()
    assert not (moved / "capture").exists()

    monkeypatch.undo()
    output = tmp_path / "collision-parent" / "capture"
    real_rename = source._rename_noreplace_at

    def collide(parent_fd: int, staging: str, target_name: str) -> None:
        os.mkdir(target_name, 0o700, dir_fd=parent_fd)
        target_fd = os.open(
            target_name,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        try:
            marker = os.open("marker", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=target_fd)
            os.close(marker)
        finally:
            os.close(target_fd)
        real_rename(parent_fd, staging, target_name)

    monkeypatch.setattr(source, "_rename_noreplace_at", collide)
    with pytest.raises(AcquisitionError, match="publication"):
        acquire(output, monkeypatch, end="20120101")
    assert (output / "marker").read_bytes() == b""
    assert any(path.name.startswith(".capture.staging-") for path in output.parent.iterdir())


def test_stdlib_transport_disables_proxies_rejects_redirects_and_bounds_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"api_name": "balancesheet_vip", "params": {}, "fields": "ts_code"}
    headers = {"x-api-key": TOKEN}
    payload = response([])
    encoded = gzip.compress(payload)
    handlers: list[object] = []

    class FakeResponse:
        status = 200

        def __init__(self, data: bytes, response_headers: dict[str, str]) -> None:
            self.stream = io.BytesIO(data)
            self.headers = response_headers
            self.read_sizes: list[int] = []

        def read(self, amount: int) -> bytes:
            self.read_sizes.append(amount)
            return self.stream.read(amount)

        def geturl(self) -> str:
            return ENDPOINT

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(
            self,
            exception_type: type[BaseException] | None,
            exception: BaseException | None,
            traceback: object,
        ) -> None:
            return None

    fake_response = FakeResponse(encoded, {"Content-Encoding": "gzip"})

    class FakeOpener:
        def open(self, _request: object, timeout: int) -> FakeResponse:
            assert timeout == 30
            return fake_response

    def build_opener(*values: object) -> FakeOpener:
        handlers.extend(values)
        return FakeOpener()

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
    assert source._stdlib_post(ENDPOINT, body, headers, len(payload)) == (200, payload)
    assert any(
        isinstance(handler, urllib.request.ProxyHandler)
        and getattr(handler, "proxies", None) == {}
        for handler in handlers
    )
    assert any(isinstance(handler, source._NoRedirect) for handler in handlers)
    assert fake_response.read_sizes and max(fake_response.read_sizes) <= len(payload) + 1

    class RedirectOpener:
        def open(self, request: urllib.request.Request, timeout: int) -> object:
            raise urllib.error.HTTPError(
                request.full_url,
                302,
                "redirect",
                email.message.Message(),
                io.BytesIO(b""),
            )

    monkeypatch.setattr(urllib.request, "build_opener", lambda *_handlers: RedirectOpener())
    assert source._stdlib_post(ENDPOINT, body, headers, 100) == (302, b"")
    with pytest.raises(AcquisitionError, match="status"):
        source._post_with_retries(
            endpoint=ENDPOINT,
            body=body,
            headers=headers,
            post=source._stdlib_post,
            sleep=lambda _seconds: None,
            state=source._PageCaptureState([]),
        )

    oversized = FakeResponse(b"abcd", {"Content-Length": "4"})
    with pytest.raises(AcquisitionError, match="ceiling"):
        source._read_bounded(oversized, 3)


def test_token_file_and_cli_are_explicit_and_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    token_file = tmp_path / "token"
    token_file.write_text(TOKEN + "\n", encoding="ascii")
    token_file.chmod(0o600)
    assert source._read_token_file(token_file) == TOKEN
    token_file.chmod(0o640)
    with pytest.raises(AcquisitionError, match="token file"):
        source._read_token_file(token_file)
    token_file.chmod(0o600)
    target = tmp_path / "target"
    target.write_text(TOKEN, encoding="ascii")
    symlink = tmp_path / "token-link"
    symlink.symlink_to(target)
    with pytest.raises(AcquisitionError, match="token file"):
        source._read_token_file(symlink)

    captured: dict[str, object] = {}

    def fake_acquire(request: object, **kwargs: object) -> dict[str, object]:
        captured["request"] = request
        captured.update(kwargs)
        return {"type": "fixture", "schema_version": 1}

    monkeypatch.setattr(
        source,
        "acquire_tushare_s2c_2011_prior_balance_source_bounded_v1",
        fake_acquire,
    )
    assert source.main(
        [
            "--endpoint",
            ENDPOINT,
            "--token-file",
            str(token_file),
            "--output-dir",
            str(tmp_path / "cli"),
        ]
    ) == 0
    assert captured["token"] == TOKEN
    assert captured["output_dir"] == tmp_path / "cli"
    assert captured["post"] is source._stdlib_post
    assert TOKEN not in capsys.readouterr().out
