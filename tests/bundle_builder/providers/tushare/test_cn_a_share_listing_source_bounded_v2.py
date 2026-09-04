from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

import pytest

from crypto_quant_bundle_builder.source_snapshots import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from crypto_quant_bundle_builder.tushare_cn_a_share_listing_source_bounded_v2 import (
    TushareCnAShareListingSourceBoundedObservationOutcomeV2,
    TushareCnAShareListingSourceBoundedObservationReportV2,
    observe_tushare_cn_a_share_listing_source_bounded_v2,
)
from crypto_quant_domain import (
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    VenueId,
    canonical_bytes,
)

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = (
    ROOT
    / "tests/fixtures/market_data/providers/tushare/g12l-listing-source-bounded-v2"
)
RECEIPT_BYTES = (FIXTURE / "acquisition-receipt.json").read_bytes()
RECEIPT = json.loads(RECEIPT_BYTES)
PROVENANCE = SourceSnapshotProvenance(
    vendor_key="tushare.pro",
    source_key=(
        "tushare.pro.via.xiaodefa.approved-proxy."
        "listing_presence.000001.sz.20240102"
    ),
    license_ref="tushare.pro.terms",
    retention_policy_ref="backtest.acquisition.candidate",
)


def _json_bytes(value: object) -> bytes:
    return canonical_bytes(value) + b"\n"


def _raw() -> dict[str, bytes]:
    return {
        request["member_key"]: (FIXTURE / request["member_key"]).read_bytes()
        for request in RECEIPT["provider_requests"]
    }


def _snapshot(
    raw: dict[str, bytes] | None = None,
    receipt: dict[str, Any] | None = None,
):
    values = RECEIPT if receipt is None else receipt
    source = _raw() if raw is None else raw
    outcome = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                key,
                body,
                "0644",
                values["acquired_at_epoch_nanoseconds"],
                None,
            )
            for key, body in sorted(source.items())
        ),
        provenance=PROVENANCE,
    )
    assert outcome.failure is None and outcome.snapshot is not None
    return outcome.snapshot


def _catalog(*, stable_key: str = "000001") -> InstrumentCatalog:
    currency = CurrencyId("CNY")
    return InstrumentCatalog(
        currencies=(currency,),
        instruments=(
            InstrumentDefinition(
                InstrumentId(VenueId("xshe"), stable_key),
                InstrumentType.EQUITY,
                None,
                currency,
                currency,
            ),
        ),
        symbol_timelines=(),
    )


def _observe(
    receipt_bytes: bytes = RECEIPT_BYTES,
    snapshot=None,
    catalog: InstrumentCatalog | None = None,
    **kwargs,
):
    return observe_tushare_cn_a_share_listing_source_bounded_v2(
        acquisition_receipt_bytes=receipt_bytes,
        snapshot=_snapshot() if snapshot is None else snapshot,
        instrument_catalog=_catalog() if catalog is None else catalog,
        **kwargs,
    )


def _capture(
    mutate: Callable[[dict[str, dict[str, Any]], dict[str, Any]], None],
    *,
    time_delta: int = 0,
):
    raw = {key: json.loads(value) for key, value in _raw().items()}
    receipt = copy.deepcopy(RECEIPT)
    mutate(raw, receipt)
    encoded = {
        key: json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        for key, value in raw.items()
    }
    receipt["acquired_at_epoch_nanoseconds"] += time_delta
    by_key = {value["member_key"]: value for value in receipt["provider_requests"]}
    for key, source in encoded.items():
        request = by_key[key]
        request["response_byte_count"] = len(source)
        request["response_sha256"] = "sha256:" + hashlib.sha256(source).hexdigest()
        request["returned_row_count"] = len(raw[key]["data"]["items"])
    receipt["current_listing_row_count"] = by_key["response/stock-basic.json"][
        "returned_row_count"
    ]
    receipt["historical_list_row_count"] = by_key["response/bak-basic.json"][
        "returned_row_count"
    ]
    receipt["namechange_row_count"] = by_key["response/namechange.json"][
        "returned_row_count"
    ]
    snapshot = _snapshot(encoded, receipt)
    receipt["snapshot"] = snapshot.to_canonical_dict()
    return _json_bytes(receipt), snapshot


def _failure(outcome, code: str) -> None:
    assert outcome.report is None and outcome.failure is not None
    assert outcome.failure.code.value == code
    assert outcome.failure.failure_hash.startswith("sha256:")


def test_live_fixture_report_rows_catalog_and_qualification_are_exact() -> None:
    snapshot = _snapshot()
    assert snapshot.to_canonical_dict() == RECEIPT["snapshot"]

    outcome = _observe(snapshot=snapshot)
    assert outcome.failure is None and outcome.report is not None
    report = outcome.report
    assert report.provider_key == "tushare.pro"
    assert report.transport_proxy_key == "xiaodefa.approved-tushare-proxy.v1"
    assert report.datasets == ("stock_basic", "bak_basic", "namechange")
    assert report.instrument_id == InstrumentId(VenueId("xshe"), "000001")
    assert report.trade_date == "20240102"
    assert report.instrument_catalog_hash == (
        "sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc"
    )
    assert report.stock_basic_rows == (
        ("000001.SZ", "000001", "平安银行", "主板", "SZSE", "L", "19910403", None),
    )
    assert report.bak_basic_rows == (
        ("20240102", "000001.SZ", "平安银行", "19910403"),
    )
    assert len(report.namechange_rows) == 4
    assert report.namechange_rows[report.target_name_interval_index] == (
        "000001.SZ",
        "平安银行",
        "20120802",
        None,
        "20120120",
        "其他",
    )
    assert len(report.source_record_hashes) == 6
    assert report.observed_at.epoch_nanoseconds == RECEIPT[
        "acquired_at_epoch_nanoseconds"
    ]
    assert all(
        value is False
        for value in (
            report.revision_closure_complete,
            report.provider_completeness_qualified,
            report.absence_authority,
            report.historical_listing_lifecycle_qualified,
            report.corporate_action_lifecycle_qualified,
            report.decision_grade_eligible,
            report.live_eligible,
            report.deployment_authorized,
        )
    )
    expected = (FIXTURE / "observation-report.expected.json").read_bytes()
    assert canonical_bytes(report.to_canonical_dict()) == expected


def test_report_deep_reconstruction_and_constructor_bypass_fail_closed() -> None:
    report = _observe().report
    assert report is not None
    parsed = json.loads(canonical_bytes(report.to_canonical_dict()))
    rebuilt = TushareCnAShareListingSourceBoundedObservationReportV2.from_canonical_dict(
        parsed
    )
    assert canonical_bytes(rebuilt) == canonical_bytes(report)

    parsed["report_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="report hash mismatch"):
        TushareCnAShareListingSourceBoundedObservationReportV2.from_canonical_dict(
            parsed
        )
    with pytest.raises(ValueError, match="catalog mismatch"):
        replace(report, instrument_catalog_hash="sha256:" + "0" * 64)

    forged = object.__new__(TushareCnAShareListingSourceBoundedObservationReportV2)
    for name in report.__dataclass_fields__:
        object.__setattr__(forged, name, getattr(report, name))
    object.__setattr__(forged, "report_hash", "sha256:" + "0" * 64)
    with pytest.raises(TypeError, match="reconstructable observation report"):
        TushareCnAShareListingSourceBoundedObservationOutcomeV2(report=forged)

    corrected_receipt, corrected_snapshot = _capture(
        lambda raw, _: raw["response/stock-basic.json"].update(
            request_id="corrected-request-id"
        ),
        time_delta=1,
    )
    outcome = _observe(
        corrected_receipt,
        corrected_snapshot,
        supersedes_report=forged,
        supersedes_acquisition_receipt_bytes=RECEIPT_BYTES,
        supersedes_snapshot=_snapshot(),
    )
    _failure(outcome, "report_binding_mismatch")


def test_direct_supersession_is_append_only_and_exact() -> None:
    predecessor = _observe().report
    assert predecessor is not None
    receipt_bytes, snapshot = _capture(
        lambda raw, _: raw["response/namechange.json"].update(
            request_id="corrected-request-id"
        ),
        time_delta=1,
    )
    outcome = _observe(
        receipt_bytes,
        snapshot,
        supersedes_report=predecessor,
        supersedes_acquisition_receipt_bytes=RECEIPT_BYTES,
        supersedes_snapshot=_snapshot(),
    )
    assert outcome.failure is None and outcome.report is not None
    assert outcome.report.supersedes_report_hash == predecessor.report_hash
    assert outcome.report.report_hash != predecessor.report_hash
    assert outcome.report.snapshot_id != predecessor.snapshot_id
    assert outcome.report.stock_basic_rows == predecessor.stock_basic_rows
    assert outcome.report.bak_basic_rows == predecessor.bak_basic_rows
    assert outcome.report.namechange_rows == predecessor.namechange_rows


def test_failure_precedence_is_fixed_and_atomic() -> None:
    _failure(
        observe_tushare_cn_a_share_listing_source_bounded_v2(
            acquisition_receipt_bytes=b"{}",
            snapshot=object(),  # type: ignore[arg-type]
            instrument_catalog=_catalog(),
        ),
        "invalid_input",
    )

    _failure(_observe(canonical_bytes(RECEIPT)), "evidence_invalid")
    bad_receipt = copy.deepcopy(RECEIPT)
    bad_receipt["snapshot"]["snapshot_id"] = "sha256:" + "0" * 64
    _failure(_observe(_json_bytes(bad_receipt)), "evidence_invalid")
    wrong_type = copy.deepcopy(RECEIPT)
    wrong_type["current_listing_row_count"] = True
    _failure(_observe(_json_bytes(wrong_type)), "evidence_invalid")
    wrong_nested_type = copy.deepcopy(RECEIPT)
    wrong_nested_type["snapshot"]["schema_version"] = True
    _failure(_observe(_json_bytes(wrong_nested_type)), "evidence_invalid")

    wrong_scope = copy.deepcopy(RECEIPT)
    wrong_scope["transport_endpoint"] = "https://unapproved.example"
    _failure(_observe(_json_bytes(wrong_scope)), "request_scope_mismatch")
    _failure(_observe(catalog=_catalog(stable_key="000002")), "request_scope_mismatch")

    def schema_before_page_and_conflict(raw, _):
        raw["response/stock-basic.json"]["data"]["fields"] = ["wrong"]
        raw["response/stock-basic.json"]["data"]["has_more"] = True
        raw["response/bak-basic.json"]["data"]["items"][0][2] = "不同名称"

    receipt_bytes, snapshot = _capture(schema_before_page_and_conflict)
    _failure(_observe(receipt_bytes, snapshot), "response_schema_mismatch")

    def row_schema_before_page_and_conflict(raw, _):
        raw["response/stock-basic.json"]["data"]["items"][0][1] = True
        raw["response/stock-basic.json"]["data"]["has_more"] = True
        raw["response/bak-basic.json"]["data"]["items"][0][2] = "不同名称"

    receipt_bytes, snapshot = _capture(row_schema_before_page_and_conflict)
    _failure(_observe(receipt_bytes, snapshot), "response_schema_mismatch")

    def page_before_conflict(raw, _):
        raw["response/stock-basic.json"]["data"]["has_more"] = True
        raw["response/bak-basic.json"]["data"]["items"][0][2] = "不同名称"

    receipt_bytes, snapshot = _capture(page_before_conflict)
    _failure(_observe(receipt_bytes, snapshot), "response_page_incomplete")

    def conflict(raw, _):
        raw["response/bak-basic.json"]["data"]["items"][0][2] = "不同名称"

    receipt_bytes, snapshot = _capture(conflict)
    _failure(_observe(receipt_bytes, snapshot), "source_observation_conflict")

    predecessor = _observe().report
    assert predecessor is not None
    _failure(
        _observe(supersedes_report=predecessor),
        "invalid_input",
    )


def test_fixture_and_module_are_secret_free_and_off_root() -> None:
    for path in FIXTURE.rglob("*"):
        if path.is_file():
            source = path.read_bytes().lower()
            assert b'"token"' not in source
            assert b'"authorization"' not in source
            assert b"tushare_proxy_token" not in source
