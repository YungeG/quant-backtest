from __future__ import annotations

import copy
import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from tools.acquisition import _common
from tools.acquisition import cn_a_share_tushare_s2a_vip_financial_source_bounded_v1 as sentinel

TOKEN = "p" * 56
ENDPOINT = "https://fast.xiaodefa.cn"
EXPECTED_INCOME_FIELDS = (
    "ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type",
    "revenue", "operate_profit", "total_profit", "income_tax", "n_income",
    "n_income_attr_p", "minority_gain", "fin_exp_int_exp", "ebit", "ebitda",
    "update_flag",
)
EXPECTED_BALANCE_FIELDS = (
    "ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type",
    "money_cap", "total_assets", "total_liab", "total_hldr_eqy_inc_min_int",
    "total_hldr_eqy_exc_min_int", "minority_int", "total_liab_hldr_eqy", "st_borr",
    "non_cur_liab_due_1y", "lt_borr", "bond_payable", "st_bonds_payable",
    "update_flag",
)
EXPECTED_CASHFLOW_FIELDS = (
    "ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type",
    "n_cashflow_act", "c_pay_acq_const_fiolta", "depr_fa_coga_dpba",
    "use_right_asset_dep", "amort_intang_assets", "lt_amort_deferred_exp",
    "c_cash_equ_end_period", "free_cashflow", "update_flag",
)
EXPECTED_LIMITATIONS = (
    "full-market source superset is not exact S1 or S2 scope",
    "provider announcement-date slicing is source-bounded, not revision or terminal authority",
    "lease_liab is unavailable from the captured VIP balance schema",
    "provider computed EBIT, EBITDA, and free_cashflow are advisory",
    "expected S1 extraction and missing-member closure are not performed",
    "financial statement revisions, supersession, and finality are not qualified",
    "accounting currency and unit authority are not established",
    "accepted financial availability is not established",
    "coherent presentation selection is not performed",
    "financing-note and debt-scope closure are not established",
    "no S2 qualification, Strategy, Validation, or deployment authority is granted",
)


def row(
    fields: tuple[str, ...],
    *,
    period: str,
    ann_date: str,
    ts_code: str = "000001.SZ",
    update_flag: str = "0",
    numeric: object = 1,
) -> list[object]:
    context: dict[str, object] = {
        "ts_code": ts_code,
        "ann_date": ann_date,
        "f_ann_date": ann_date,
        "end_date": period,
        "report_type": "1",
        "comp_type": "1",
        "update_flag": update_flag,
    }
    return [context.get(field, numeric) for field in fields]


def response(
    fields: tuple[str, ...],
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
                "fields": list(fields),
                "items": rows,
                "has_more": has_more,
                "count": count,
            },
            "msg": "",
            "detail": "",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


class FakePost:
    def __init__(
        self,
        *,
        split_intervals: set[tuple[str, str]] | None = None,
        statuses: list[int] | None = None,
        mutate: Callable[[dict[str, object], bytes], bytes] | None = None,
        duplicate_rows: bool = False,
    ) -> None:
        self.split_intervals = split_intervals or set()
        self.statuses = list(statuses or [])
        self.mutate = mutate
        self.duplicate_rows = duplicate_rows
        self.calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def __call__(
        self, url: str, body: dict[str, object], headers: dict[str, str]
    ) -> tuple[int, bytes]:
        self.calls.append((url, copy.deepcopy(body), dict(headers)))
        status = self.statuses.pop(0) if self.statuses else 200
        if status != 200:
            return status, b""
        fields = tuple(cast(str, body["fields"]).split(","))
        params = cast(dict[str, str], body["params"])
        rows = [row(fields, period=params["period"], ann_date=params["start_date"])]
        if self.duplicate_rows:
            rows *= 2
        source = response(
            fields,
            rows,
            has_more=(params["start_date"], params["end_date"])
            in self.split_intervals,
        )
        return 200, self.mutate(body, source) if self.mutate else source


class Clock:
    def __init__(self, start: int = 1000) -> None:
        self.value = start

    def __call__(self) -> int:
        self.value += 1
        return self.value


def reduced(monkeypatch: pytest.MonkeyPatch, *, end: str = "20240104") -> None:
    monkeypatch.setattr(sentinel, "_API_ORDER", ("income_vip",))
    monkeypatch.setattr(sentinel, "_PERIOD_ORDER", ("20240101",))
    monkeypatch.setattr(sentinel, "_ROOT_END_DATE", end)
    monkeypatch.setattr(sentinel, "MAX_SPLIT_DEPTH", 4)
    monkeypatch.setattr(sentinel, "MAX_TOTAL_REQUESTS", 32)
    monkeypatch.setattr(sentinel, "MAX_TOTAL_RESPONSE_BYTES", 1_000_000)


def acquire(
    output: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    post: sentinel.ProxyPost | None = None,
    sleep: Callable[[float], object] | None = None,
    time_ns: Callable[[], int] | None = None,
    end: str = "20240104",
) -> tuple[dict[str, Any], FakePost, list[float]]:
    reduced(monkeypatch, end=end)
    proxy = post if post is not None else FakePost()
    sleeps: list[float] = []
    receipt = sentinel.acquire_tushare_s2a_vip_financial_source_bounded_v1(
        sentinel.TushareS2aVipFinancialSourceBoundedRequestV1(),
        token=TOKEN,
        endpoint=ENDPOINT,
        output_dir=output,
        post=proxy,
        sleep=sleep or sleeps.append,
        time_ns=time_ns or Clock(),
    )
    assert isinstance(proxy, FakePost)
    return cast(dict[str, Any], receipt), proxy, sleeps


def test_recursive_capture_is_depth_first_gap_free_and_exactly_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "capture"
    proxy = FakePost(
        split_intervals={("20240101", "20240104"), ("20240101", "20240102")},
        duplicate_rows=True,
    )
    opened: list[str] = []
    real_open = _common.os.open

    def tracked_open(
        path: os.PathLike[str] | str,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if flags & os.O_WRONLY:
            opened.append(os.fspath(path))
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(_common.os, "open", tracked_open)
    receipt, _, sleeps = acquire(output, monkeypatch, post=proxy)
    intervals = [
        (request["params"]["start_date"], request["params"]["end_date"])
        for request in receipt["provider_requests"]
    ]
    assert intervals == [
        ("20240101", "20240104"),
        ("20240101", "20240102"),
        ("20240101", "20240101"),
        ("20240102", "20240102"),
        ("20240103", "20240104"),
    ]
    assert sleeps == [0.5] * 4
    assert [request["depth"] for request in receipt["provider_requests"]] == [0, 1, 2, 2, 1]
    assert [request["returned_row_count"] for request in receipt["provider_requests"]] == [2] * 5
    tree = receipt["root_trees"][0]
    assert tree["page_member_keys"] == [
        request["member_key"] for request in receipt["provider_requests"]
    ]
    assert tree["terminal_leaf_member_keys"] == [
        receipt["provider_requests"][index]["member_key"] for index in (2, 3, 4)
    ]
    assert tree["maximum_depth"] == 2
    assert receipt["provider_requests"][0]["child_member_keys"] == [
        receipt["provider_requests"][1]["member_key"],
        receipt["provider_requests"][4]["member_key"],
    ]
    assert receipt["provider_requests"][1]["child_member_keys"] == [
        receipt["provider_requests"][2]["member_key"],
        receipt["provider_requests"][3]["member_key"],
    ]
    assert all(
        request["terminal"] == (not request["observed_envelope"]["has_more"])
        for request in receipt["provider_requests"]
    )

    expected_files = {
        request["member_key"] for request in receipt["provider_requests"]
    } | {"source-snapshot.json", "acquisition-receipt.json"}
    assert {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    } == expected_files
    assert Path(opened[-1]).name == "acquisition-receipt.json"
    assert (output.stat().st_mode & 0o777) == 0o700
    assert all(
        path.stat().st_mode & 0o777 == 0o600
        for path in output.rglob("*")
        if path.is_file()
    )
    assert (output / "acquisition-receipt.json").read_bytes() == _common.json_bytes(receipt)
    assert (output / "source-snapshot.json").read_bytes() == _common.json_bytes(receipt["snapshot"])
    assert receipt["acquired_at_epoch_nanoseconds"] == 1005
    assert [member["mode"] for member in receipt["snapshot"]["members"]] == ["0644"] * 5
    assert all(member["declared_sha256"] is None for member in receipt["snapshot"]["members"])
    assert TOKEN.encode() not in b"".join(
        path.read_bytes() for path in output.rglob("*") if path.is_file()
    )
    assert receipt["snapshot"]["provenance"] == {
        "vendor_key": "tushare.pro",
        "source_key": "tushare.pro.via.xiaodefa.approved-proxy.s2a-vip-financial.2012-2024.20260826",
        "license_ref": "tushare.pro.terms",
        "retention_policy_ref": "backtest.acquisition.candidate",
    }
    snapshot_members = {
        member["member_key"]: member for member in receipt["snapshot"]["members"]
    }
    for expected_timestamp, request_item in enumerate(
        receipt["provider_requests"], start=1001
    ):
        fields = tuple(request_item["fields"].split(","))
        params = request_item["params"]
        expected_rows = [
            row(fields, period=params["period"], ann_date=params["start_date"])
        ] * 2
        expected_raw = response(
            fields,
            expected_rows,
            has_more=not request_item["terminal"],
        )
        assert (output / request_item["member_key"]).read_bytes() == expected_raw
        assert request_item["response_byte_count"] == len(expected_raw)
        assert request_item["response_sha256"] == (
            "sha256:" + hashlib.sha256(expected_raw).hexdigest()
        )
        assert (
            request_item["response_received_at_epoch_nanoseconds"]
            == expected_timestamp
        )
        member = snapshot_members[request_item["member_key"]]
        assert member == {
            "member_key": request_item["member_key"],
            "content_hash": "sha256:" + hashlib.sha256(expected_raw).hexdigest(),
            "byte_count": len(expected_raw),
            "mode": "0644",
            "acquired_at_epoch_nanoseconds": expected_timestamp,
            "declared_sha256": None,
        }

    parent_rows = json.loads(
        (output / receipt["provider_requests"][0]["member_key"]).read_bytes()
    )["data"]["items"]
    leaf_rows = [
        item
        for key in tree["terminal_leaf_member_keys"]
        for item in json.loads((output / key).read_bytes())["data"]["items"]
    ]
    assert len(parent_rows) == 2
    assert len(leaf_rows) == 6
    assert parent_rows[0] == parent_rows[1]


def test_frozen_field_sets_and_limitations_are_literal() -> None:
    assert sentinel._INCOME_FIELDS == EXPECTED_INCOME_FIELDS
    assert sentinel._BALANCE_FIELDS == EXPECTED_BALANCE_FIELDS
    assert sentinel._CASHFLOW_FIELDS == EXPECTED_CASHFLOW_FIELDS
    assert sentinel._FIELD_SETS == {
        "income_vip": EXPECTED_INCOME_FIELDS,
        "balancesheet_vip": EXPECTED_BALANCE_FIELDS,
        "cashflow_vip": EXPECTED_CASHFLOW_FIELDS,
    }
    assert sentinel._LIMITATIONS == EXPECTED_LIMITATIONS


def test_request_receipt_limitations_flags_and_root_order_are_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sentinel, "_API_ORDER", ("income_vip", "cashflow_vip"))
    monkeypatch.setattr(sentinel, "_PERIOD_ORDER", ("20230101", "20240101"))
    monkeypatch.setattr(sentinel, "_ROOT_END_DATE", "20240101")
    monkeypatch.setattr(sentinel, "MAX_SPLIT_DEPTH", 3)
    monkeypatch.setattr(sentinel, "MAX_TOTAL_REQUESTS", 9)
    monkeypatch.setattr(sentinel, "MAX_TOTAL_RESPONSE_BYTES", 9999)
    receipt = cast(
        dict[str, Any],
        sentinel.acquire_tushare_s2a_vip_financial_source_bounded_v1(
            sentinel.TushareS2aVipFinancialSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=tmp_path / "capture",
            post=FakePost(),
            sleep=lambda _seconds: None,
            time_ns=Clock(),
        ),
    )
    assert [(item["api_name"], item["period"]) for item in receipt["root_trees"]] == [
        ("income_vip", "20230101"),
        ("income_vip", "20240101"),
        ("cashflow_vip", "20230101"),
        ("cashflow_vip", "20240101"),
    ]
    assert set(receipt) == {
        "type", "schema_version", "request", "provider_key", "transport_proxy_key",
        "transport_endpoint", "provider_requests", "root_trees",
        "acquired_at_epoch_nanoseconds", "snapshot", "limitations", "source_bounded",
        "source_superset", "expected_scope_extracted", "financial_payload_complete",
        "accounting_unit_qualified", "financial_availability_qualified",
        "presentation_selection_qualified", "financing_debt_scope_qualified",
        "provider_completeness_qualified", "revision_closure_complete",
        "decision_grade_eligible", "deployment_authorized", "provider_revision_id",
    }
    assert receipt["request"] == {
        "type": "tushare_s2a_vip_financial_source_bounded_request_v1",
        "schema_version": 1,
        "capture_key": "20260826-s2a-vip-financial-candidate-01",
        "api_order": ["income_vip", "cashflow_vip"],
        "period_order": ["20230101", "20240101"],
        "root_end_date": "20240101",
        "field_sets": {
            "income_vip": list(EXPECTED_INCOME_FIELDS),
            "cashflow_vip": list(EXPECTED_CASHFLOW_FIELDS),
        },
        "max_split_depth": 3,
        "max_total_requests": 9,
        "max_total_response_bytes": 9999,
    }
    assert receipt["limitations"] == list(EXPECTED_LIMITATIONS)
    assert receipt["source_bounded"] is True
    assert receipt["source_superset"] is True
    for name in (
        "expected_scope_extracted", "financial_payload_complete", "accounting_unit_qualified",
        "financial_availability_qualified", "presentation_selection_qualified",
        "financing_debt_scope_qualified", "provider_completeness_qualified",
        "revision_closure_complete", "decision_grade_eligible", "deployment_authorized",
    ):
        assert receipt[name] is False
    assert receipt["provider_revision_id"] is None
    assert all(
        set(item) == {
            "api_name", "period", "params", "fields", "member_key", "parent_member_key",
            "depth", "attempts", "response_received_at_epoch_nanoseconds",
            "response_byte_count", "response_sha256", "returned_row_count",
            "observed_envelope", "terminal", "child_member_keys", "provider_revision_id",
            "declared_sha256",
        }
        for item in receipt["provider_requests"]
    )
    assert all(
        set(tree) == {
            "api_name", "period", "root_start_date", "root_end_date", "root_member_key",
            "page_member_keys", "terminal_leaf_member_keys", "maximum_depth",
        }
        for tree in receipt["root_trees"]
    )


def test_midpoint_uses_calendar_days_and_rejects_unsplittable_values() -> None:
    assert sentinel._midpoint("20240228", "20240302") == ("20240229", "20240301")
    assert sentinel._midpoint("20240101", "20240102") == ("20240101", "20240102")
    for start, end in (("20240101", "20240101"), ("bad", "20240102"), ("20240103", "20240102")):
        with pytest.raises(_common.AcquisitionError):
            sentinel._midpoint(start, end)


def test_one_day_depth_request_and_byte_ceilings_publish_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "one-day"
    with pytest.raises(_common.AcquisitionError, match="one-day"):
        acquire(
            output,
            monkeypatch,
            post=FakePost(split_intervals={("20240101", "20240101")}),
            end="20240101",
        )
    assert not output.exists()

    reduced(monkeypatch, end="20240102")
    monkeypatch.setattr(sentinel, "MAX_SPLIT_DEPTH", 0)
    with pytest.raises(_common.AcquisitionError, match="depth"):
        sentinel.acquire_tushare_s2a_vip_financial_source_bounded_v1(
            sentinel.TushareS2aVipFinancialSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=tmp_path / "depth",
            post=FakePost(split_intervals={("20240101", "20240102")}),
            sleep=lambda _seconds: None,
            time_ns=Clock(),
        )

    reduced(monkeypatch, end="20240102")
    monkeypatch.setattr(sentinel, "MAX_TOTAL_REQUESTS", 1)
    with pytest.raises(_common.AcquisitionError, match="request ceiling"):
        sentinel.acquire_tushare_s2a_vip_financial_source_bounded_v1(
            sentinel.TushareS2aVipFinancialSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=tmp_path / "requests",
            post=FakePost(split_intervals={("20240101", "20240102")}),
            sleep=lambda _seconds: None,
            time_ns=Clock(),
        )

    reduced(monkeypatch, end="20240101")
    monkeypatch.setattr(sentinel, "MAX_TOTAL_RESPONSE_BYTES", 1)
    with pytest.raises(_common.AcquisitionError, match="byte ceiling"):
        sentinel.acquire_tushare_s2a_vip_financial_source_bounded_v1(
            sentinel.TushareS2aVipFinancialSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=tmp_path / "bytes",
            post=FakePost(),
            sleep=lambda _seconds: None,
            time_ns=Clock(),
        )
    assert not any((tmp_path / name).exists() for name in ("depth", "requests", "bytes"))


@pytest.mark.parametrize(
    "mutation",
    ["json", "duplicate-key", "fields", "width", "has-more", "count-type", "count-value", "nonfinite"],
)
def test_parse_page_rejects_invalid_json_envelope_fields_count_and_width(mutation: str) -> None:
    fields = sentinel._INCOME_FIELDS
    source = response(fields, [row(fields, period="20240101", ann_date="20240101")])
    if mutation == "json":
        source = b"not-json"
    elif mutation == "duplicate-key":
        source = source.replace(b'"code":0', b'"code":0,"code":0')
    elif mutation == "nonfinite":
        source = source.replace(b'"code":0', b'"code":NaN')
    else:
        payload = json.loads(source)
        if mutation == "fields":
            payload["data"]["fields"][-1] = "wrong"
        elif mutation == "width":
            payload["data"]["items"][0].pop()
        elif mutation == "has-more":
            payload["data"]["has_more"] = 1
        elif mutation == "count-type":
            payload["data"]["count"] = False
        elif mutation == "count-value":
            payload["data"]["count"] = 1
        source = json.dumps(payload, separators=(",", ":")).encode()
    with pytest.raises(_common.AcquisitionError):
        sentinel._parse_page(source, fields, TOKEN)


def test_parse_page_rejects_raw_and_escaped_credentials() -> None:
    fields = sentinel._INCOME_FIELDS
    payload = json.loads(response(fields, []))
    payload["request_id"] = TOKEN
    with pytest.raises(_common.AcquisitionError, match="credential"):
        sentinel._parse_page(json.dumps(payload).encode(), fields, TOKEN)
    escaped = json.dumps(payload).replace(TOKEN, "\\u0070" * len(TOKEN)).encode()
    with pytest.raises(_common.AcquisitionError, match="credential"):
        sentinel._parse_page(escaped, fields, TOKEN)


@pytest.mark.parametrize(
    ("name", "change"),
    [
        ("ts-code", {"ts_code": "bad"}),
        ("ann-before", {"ann_date": "20231231"}),
        ("ann-invalid", {"ann_date": "20240230"}),
        ("f-ann", {"f_ann_date": "bad"}),
        ("period", {"end_date": "20231231"}),
        ("report", {"report_type": "2"}),
        ("company", {"comp_type": "2"}),
        ("flag", {"update_flag": "2"}),
        ("quoted", {"numeric": "1.0"}),
        ("boolean", {"numeric": True}),
        ("infinite", {"numeric": float("inf")}),
    ],
)
def test_validate_rows_rejects_semantic_and_numeric_domain_failures(
    name: str, change: dict[str, object]
) -> None:
    fields = sentinel._INCOME_FIELDS
    values: dict[str, object] = {
        "ts_code": "000001.SZ",
        "ann_date": "20240101",
        "f_ann_date": "20240101",
        "end_date": "20240101",
        "report_type": "1",
        "comp_type": "1",
        "update_flag": "0",
        "numeric": 1,
    }
    values.update(change)
    candidate = row(
        fields,
        period=cast(str, values["end_date"]),
        ann_date=cast(str, values["ann_date"]),
        ts_code=cast(str, values["ts_code"]),
        update_flag=cast(str, values["update_flag"]),
        numeric=values["numeric"],
    )
    candidate[fields.index("f_ann_date")] = values["f_ann_date"]
    candidate[fields.index("report_type")] = values["report_type"]
    candidate[fields.index("comp_type")] = values["comp_type"]
    with pytest.raises(_common.AcquisitionError, match="row scope"):
        sentinel._validate_rows(
            [candidate],
            api_name="income_vip",
            period="20240101",
            start_date="20240101",
            end_date="20240102",
        )


def test_validate_rows_allows_null_finite_numbers_bj_and_duplicate_revisions() -> None:
    fields = sentinel._BALANCE_FIELDS
    first = row(
        fields,
        period="20240101",
        ann_date="20240102",
        ts_code="430001.BJ",
        numeric=None,
    )
    second = row(
        fields,
        period="20240101",
        ann_date="20240102",
        ts_code="430001.BJ",
        update_flag="1",
        numeric=2.5,
    )
    sentinel._validate_rows(
        [first, first, second],
        api_name="balancesheet_vip",
        period="20240101",
        start_date="20240101",
        end_date="20240102",
    )


def test_retry_normal_delays_clock_and_transport_redaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleeps: list[float] = []
    receipt, proxy, _ = acquire(
        tmp_path / "retry",
        monkeypatch,
        post=FakePost(statuses=[500, 200]),
        sleep=sleeps.append,
        end="20240101",
    )
    assert len(proxy.calls) == 2
    assert receipt["provider_requests"][0]["attempts"] == 2
    assert sleeps == [1.0]

    monkeypatch.setattr(sentinel, "_PERIOD_ORDER", ("20240101", "20240102"))
    monkeypatch.setattr(sentinel, "_ROOT_END_DATE", "20240102")
    sleeps.clear()
    sentinel.acquire_tushare_s2a_vip_financial_source_bounded_v1(
        sentinel.TushareS2aVipFinancialSourceBoundedRequestV1(),
        token=TOKEN,
        endpoint=ENDPOINT,
        output_dir=tmp_path / "normal",
        post=FakePost(),
        sleep=sleeps.append,
        time_ns=Clock(),
    )
    assert sleeps == [0.5]

    def leaking_post(*_args: object) -> tuple[int, bytes]:
        raise RuntimeError(TOKEN)

    with pytest.raises(_common.AcquisitionError) as caught:
        acquire(tmp_path / "redacted", monkeypatch, post=cast(sentinel.ProxyPost, leaking_post))
    assert TOKEN not in str(caught.value)
    assert str(caught.value) == "provider transport failed"

    for clock in (lambda: True, lambda: -1, lambda: (_ for _ in ()).throw(RuntimeError(TOKEN))):
        with pytest.raises(_common.AcquisitionError) as clock_error:
            acquire(tmp_path / f"clock-{id(clock)}", monkeypatch, time_ns=clock)
        assert TOKEN not in str(clock_error.value)


def test_callback_mutation_delay_failure_snapshot_failure_and_no_clobber_are_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def mutate(body: dict[str, object], source: bytes) -> bytes:
        cast(dict[str, object], body["params"])["period"] = "forged"
        return source

    with pytest.raises(_common.AcquisitionError, match="transport"):
        acquire(tmp_path / "mutation", monkeypatch, post=FakePost(mutate=mutate))

    reduced(monkeypatch, end="20240102")
    with pytest.raises(_common.AcquisitionError, match="transport"):
        sentinel.acquire_tushare_s2a_vip_financial_source_bounded_v1(
            sentinel.TushareS2aVipFinancialSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=tmp_path / "delay",
            post=FakePost(split_intervals={("20240101", "20240102")}),
            sleep=lambda _seconds: (_ for _ in ()).throw(RuntimeError(TOKEN)),
            time_ns=Clock(),
        )

    reduced(monkeypatch, end="20240101")
    monkeypatch.setattr(
        sentinel,
        "verify_source_snapshot",
        lambda _snapshot: SimpleNamespace(failure=SimpleNamespace(code="fixture")),
    )
    with pytest.raises(_common.AcquisitionError, match="verification"):
        sentinel.acquire_tushare_s2a_vip_financial_source_bounded_v1(
            sentinel.TushareS2aVipFinancialSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=tmp_path / "snapshot",
            post=FakePost(),
            sleep=lambda _seconds: None,
            time_ns=Clock(),
        )
    assert not (tmp_path / "snapshot").exists()

    monkeypatch.undo()
    existing = tmp_path / "existing"
    existing.mkdir()
    calls: list[str] = []
    with pytest.raises(_common.AcquisitionError, match="output path"):
        sentinel.acquire_tushare_s2a_vip_financial_source_bounded_v1(
            sentinel.TushareS2aVipFinancialSourceBoundedRequestV1(),
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=existing,
            post=lambda *_args: calls.append("post") or (500, b""),
        )
    assert calls == []


def test_publication_fsync_failure_cleans_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "capture"
    real_fsync = _common.os.fsync
    calls = 0

    def fail_first_fsync(descriptor: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("fixture")
        real_fsync(descriptor)

    monkeypatch.setattr(_common.os, "fsync", fail_first_fsync)
    with pytest.raises(_common.AcquisitionError, match="publication"):
        acquire(output, monkeypatch, end="20240101")
    assert not output.exists()


def test_input_token_endpoint_output_and_cli_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    for kwargs in (
        {"token": "short", "endpoint": ENDPOINT, "output_dir": tmp_path / "short"},
        {"token": TOKEN, "endpoint": "https://example.com", "output_dir": tmp_path / "endpoint"},
        {"token": TOKEN, "endpoint": ENDPOINT, "output_dir": tmp_path / TOKEN / "capture"},
    ):
        with pytest.raises(_common.AcquisitionError):
            sentinel.acquire_tushare_s2a_vip_financial_source_bounded_v1(
                sentinel.TushareS2aVipFinancialSourceBoundedRequestV1(),
                post=lambda *_args: calls.append("post") or (500, b""),
                **kwargs,
            )
    assert calls == []
    with pytest.raises(ValueError):
        sentinel.TushareS2aVipFinancialSourceBoundedRequestV1(True)

    captured: dict[str, object] = {}

    def fake_acquire(request: object, **kwargs: object) -> dict[str, object]:
        captured["request"] = request
        captured.update(kwargs)
        return {"type": "fixture", "schema_version": 1}

    monkeypatch.setenv("TUSHARE_PROXY_TOKEN", TOKEN)
    monkeypatch.setattr(
        sentinel,
        "acquire_tushare_s2a_vip_financial_source_bounded_v1",
        fake_acquire,
    )
    assert sentinel.main(["--endpoint", ENDPOINT, "--output-dir", str(tmp_path / "cli")]) == 0
    assert captured["token"] == TOKEN
    assert captured["endpoint"] == ENDPOINT
    assert captured["post"] is sentinel._stdlib_post
    assert '"schema_version": 1' in capsys.readouterr().out
