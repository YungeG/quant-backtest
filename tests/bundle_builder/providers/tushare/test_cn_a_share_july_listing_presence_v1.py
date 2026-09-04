from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import fields
from pathlib import Path
from typing import Any, Callable

import pytest

from crypto_quant_bundle_builder.source_snapshots import RawSourceMember, SourceSnapshotProvenance, freeze_source_snapshot
from crypto_quant_bundle_builder.tushare_cn_a_share_july_listing_presence_v1 import (
    TushareCnAShareJulyListingPresenceOutcomeV1,
    TushareCnAShareJulyListingPresenceReportV1,
    observe_tushare_cn_a_share_july_listing_presence_v1,
)
from crypto_quant_domain import CurrencyId, InstrumentCatalog, InstrumentDefinition, InstrumentId, InstrumentType, VenueId, canonical_bytes

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1"
RECEIPT_BYTES = (FIXTURE / "acquisition-receipt.json").read_bytes()
RECEIPT = json.loads(RECEIPT_BYTES)
G12I = ROOT / "tests/fixtures/market_data/providers/tushare/cn-a-share-daily-source-bounded-v2/observation-report.expected.json"
LISTING = ROOT / "tests/fixtures/market_data/providers/tushare/g12l-listing-source-bounded-v2/observation-report.expected.json"
PROVENANCE = SourceSnapshotProvenance(
    "tushare.pro",
    "tushare.pro.via.xiaodefa.approved-proxy.bak_basic.000001.sz.20260706.20260730",
    "tushare.pro.terms",
    "backtest.acquisition.candidate",
)


def _raw() -> dict[str, bytes]:
    return {request["member_key"]: (FIXTURE / request["member_key"]).read_bytes() for request in RECEIPT["provider_requests"]}


def _snapshot(raw: dict[str, bytes] | None = None, receipt: dict[str, Any] | None = None):
    values = RECEIPT if receipt is None else receipt
    outcome = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(key, source, "0644", values["acquired_at_epoch_nanoseconds"], None)
            for key, source in sorted((_raw() if raw is None else raw).items())
        ),
        provenance=PROVENANCE,
    )
    assert outcome.failure is None and outcome.snapshot is not None
    return outcome.snapshot


def _catalog(stable_key: str = "000001") -> InstrumentCatalog:
    currency = CurrencyId("CNY")
    return InstrumentCatalog(
        (currency,),
        (InstrumentDefinition(InstrumentId(VenueId("xshe"), stable_key), InstrumentType.EQUITY, None, currency, currency),),
        (),
    )


def _observe(receipt_bytes: bytes = RECEIPT_BYTES, snapshot=None, **changes: object):
    values = {
        "acquisition_receipt_bytes": receipt_bytes,
        "snapshot": _snapshot() if snapshot is None else snapshot,
        "g12i_report_bytes": G12I.read_bytes(),
        "listing_report_bytes": LISTING.read_bytes(),
        "instrument_catalog": _catalog(),
    }
    values.update(changes)
    return observe_tushare_cn_a_share_july_listing_presence_v1(**values)  # type: ignore[arg-type]


def _capture(mutate: Callable[[dict[str, dict[str, Any]], dict[str, Any]], None]):
    raw = {key: json.loads(value) for key, value in _raw().items()}
    receipt = copy.deepcopy(RECEIPT)
    mutate(raw, receipt)
    encoded = {key: json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode() for key, value in raw.items()}
    by_key = {request["member_key"]: request for request in receipt["provider_requests"]}
    for key, source in encoded.items():
        by_key[key]["response_byte_count"] = len(source)
        by_key[key]["response_sha256"] = "sha256:" + hashlib.sha256(source).hexdigest()
        by_key[key]["returned_row_count"] = len(raw[key]["data"]["items"])
    receipt["returned_row_count"] = sum(value["returned_row_count"] for value in by_key.values())
    snapshot = _snapshot(encoded, receipt)
    receipt["snapshot"] = snapshot.to_canonical_dict()
    return canonical_bytes(receipt) + b"\n", snapshot


def _failure(outcome, code: str) -> None:
    assert outcome.report is None and outcome.failure is not None
    assert outcome.failure.code.value == code


def _bypass(value: Any, **changes: object) -> Any:
    result = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(result, field.name, changes.get(field.name, getattr(value, field.name)))
    return result


def test_exact_fixture_report_and_golden_are_bound() -> None:
    snapshot = _snapshot()
    assert snapshot.to_canonical_dict() == RECEIPT["snapshot"]
    outcome = _observe(snapshot=snapshot)
    assert outcome.failure is None and outcome.report is not None
    report = outcome.report
    assert report.trade_dates == tuple(request["params"]["trade_date"] for request in RECEIPT["provider_requests"])
    assert len(report.source_rows) == 19
    assert all(row[1:] == ("000001.SZ", "平安银行", "19910403") for row in report.source_rows)
    assert len(report.source_record_hashes) == 19
    assert report.observed_at.epoch_nanoseconds == RECEIPT["acquired_at_epoch_nanoseconds"]
    assert "post_run_observation_not_causal_execution_input" in report.limitations
    assert all(
        value is False
        for value in (
            report.revision_closure_complete, report.provider_completeness_qualified,
            report.absence_authority, report.historical_listing_lifecycle_qualified,
            report.decision_grade_eligible, report.live_eligible, report.deployment_authorized,
        )
    )
    assert canonical_bytes(report.to_canonical_dict()) == (FIXTURE / "observation-report.expected.json").read_bytes()


def test_failure_precedence_is_exact() -> None:
    _failure(_observe(snapshot=object()), "invalid_input")
    bad_receipt = copy.deepcopy(RECEIPT)
    bad_receipt["snapshot"]["schema_version"] = True
    _failure(_observe(canonical_bytes(bad_receipt) + b"\n"), "evidence_invalid")
    wrong_count_type = copy.deepcopy(RECEIPT)
    wrong_count_type["provider_requests"][0]["returned_row_count"] = True
    _failure(_observe(canonical_bytes(wrong_count_type) + b"\n"), "evidence_invalid")
    _failure(_observe(g12i_report_bytes=G12I.read_bytes() + b"\n"), "upstream_identity_mismatch")

    wrong_scope = copy.deepcopy(RECEIPT)
    wrong_scope["transport_endpoint"] = "https://unapproved.example"
    _failure(_observe(canonical_bytes(wrong_scope) + b"\n"), "request_scope_mismatch")

    def schema_before_page_and_conflict(raw, _):
        key = next(iter(raw))
        raw[key]["data"]["items"][0][1] = True
        raw[key]["data"]["has_more"] = True

    receipt_bytes, snapshot = _capture(schema_before_page_and_conflict)
    _failure(_observe(receipt_bytes, snapshot), "response_schema_mismatch")

    def page_before_conflict(raw, _):
        key = next(iter(raw))
        raw[key]["data"]["has_more"] = True
        raw[key]["data"]["items"][0][2] = "不同名称"

    receipt_bytes, snapshot = _capture(page_before_conflict)
    _failure(_observe(receipt_bytes, snapshot), "response_page_incomplete")

    def conflict(raw, _):
        key = next(iter(raw))
        raw[key]["data"]["items"][0][2] = "不同名称"

    receipt_bytes, snapshot = _capture(conflict)
    _failure(_observe(receipt_bytes, snapshot), "source_observation_conflict")
    _failure(_observe(instrument_catalog=_catalog("000002")), "upstream_identity_mismatch")


def test_constructor_bypass_and_subclasses_fail_closed() -> None:
    report = _observe().report
    assert report is not None
    parsed = json.loads(canonical_bytes(report.to_canonical_dict()))
    rebuilt = TushareCnAShareJulyListingPresenceReportV1.from_canonical_dict(parsed)
    assert canonical_bytes(rebuilt) == canonical_bytes(report)
    parsed["report_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="report hash mismatch"):
        TushareCnAShareJulyListingPresenceReportV1.from_canonical_dict(parsed)
    forged = _bypass(report, source_record_hashes=("sha256:" + "0" * 64,) * 19)
    with pytest.raises(ValueError, match="report row hash mismatch"):
        forged.__post_init__()
    with pytest.raises((TypeError, ValueError)):
        TushareCnAShareJulyListingPresenceOutcomeV1(forged, None)

    class ReportSubclass(TushareCnAShareJulyListingPresenceReportV1):
        pass

    values = {field.name: getattr(report, field.name) for field in fields(report) if field.init}
    with pytest.raises(TypeError, match="exact July listing report v1"):
        ReportSubclass(**values)


def test_fixtures_are_secret_free() -> None:
    for path in FIXTURE.rglob("*"):
        if path.is_file():
            source = path.read_bytes().lower()
            assert b'"token"' not in source
            assert b'"authorization"' not in source
            assert b"tushare_proxy_token" not in source
