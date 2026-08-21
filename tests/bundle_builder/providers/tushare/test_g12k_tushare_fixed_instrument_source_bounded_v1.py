from __future__ import annotations

import hashlib
import inspect
import json
from copy import deepcopy
from dataclasses import fields
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import pytest
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from crypto_quant_domain import (
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)

MODULE = import_module(
    "crypto_quant_bundle_builder.g12k_tushare_fixed_instrument_source_bounded_v1"
)
ROOT = Path(__file__).parents[3]
PROVIDER_FIXTURES = ROOT / "fixtures/market_data/providers/tushare"
FIXTURE = PROVIDER_FIXTURES / "g12k-fixed-instrument-source-bounded-v1"
G12I_FIXTURE = (
    PROVIDER_FIXTURES
    / "cn-a-share-daily-source-bounded-v2/observation-report.expected.json"
)
CATALOG_FIXTURE = PROVIDER_FIXTURES / "cn-a-share-daily-bundle-v2.expected.json"
REPORT_EXPECTED = FIXTURE / "observation-report.expected.json"
G12I_BYTES = G12I_FIXTURE.read_bytes()
RECEIPT_BYTES = (FIXTURE / "acquisition-receipt.json").read_bytes()
RECEIPT = cast(dict[str, Any], json.loads(RECEIPT_BYTES))
RESPONSE_BYTES = (FIXTURE / "response/dividend.json").read_bytes()


def _json_bytes(value: object) -> bytes:
    return canonical_bytes(value) + b"\n"


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


def _snapshot(
    *,
    raw: bytes = RESPONSE_BYTES,
    receipt: dict[str, Any] | None = None,
    provenance: SourceSnapshotProvenance | None = None,
):
    value = RECEIPT if receipt is None else receipt
    request = value["provider_requests"][0]
    outcome = freeze_source_snapshot(
        members=(
            RawSourceMember(
                request["member_key"],
                raw,
                "0644",
                request["response_received_at_epoch_nanoseconds"],
                None,
            ),
        ),
        provenance=provenance
        or SourceSnapshotProvenance(**value["snapshot"]["provenance"]),
    )
    assert outcome.failure is None and outcome.snapshot is not None
    return outcome.snapshot


def _capture(
    mutate_response=lambda value: None,
    mutate_receipt=lambda value: None,
    *,
    time_delta: int = 0,
    provenance: SourceSnapshotProvenance | None = None,
) -> tuple[bytes, object]:
    response = json.loads(RESPONSE_BYTES)
    receipt = deepcopy(RECEIPT)
    mutate_response(response)
    mutate_receipt(receipt)
    raw = json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode()
    request = receipt["provider_requests"][0]
    request["response_received_at_epoch_nanoseconds"] += time_delta
    request["response_byte_count"] = len(raw)
    request["response_sha256"] = "sha256:" + hashlib.sha256(raw).hexdigest()
    data = response.get("data")
    if type(data) is dict:
        if type(data.get("items")) is list:
            request["returned_row_count"] = len(data["items"])
        if "has_more" in data and "count" in data:
            request["observed_envelope"] = {
                "has_more": data["has_more"],
                "count": data["count"],
            }
    receipt["acquired_at_epoch_nanoseconds"] = request[
        "response_received_at_epoch_nanoseconds"
    ]
    snapshot = _snapshot(raw=raw, receipt=receipt, provenance=provenance)
    receipt["snapshot"] = snapshot.to_canonical_dict()
    return _json_bytes(receipt), snapshot


def _observe(
    *,
    g12i: bytes = G12I_BYTES,
    receipt: bytes = RECEIPT_BYTES,
    snapshot=None,
    catalog: InstrumentCatalog | None = None,
    predecessor=None,
    predecessor_receipt: bytes | None = None,
    predecessor_snapshot=None,
):
    if predecessor is not None:
        predecessor_receipt = (
            RECEIPT_BYTES if predecessor_receipt is None else predecessor_receipt
        )
        predecessor_snapshot = (
            _snapshot() if predecessor_snapshot is None else predecessor_snapshot
        )
    return MODULE.observe_g12k_tushare_fixed_instrument_source_bounded_v1(
        g12i_report_bytes=g12i,
        acquisition_receipt_bytes=receipt,
        snapshot=_snapshot() if snapshot is None else snapshot,
        instrument_catalog=_catalog() if catalog is None else catalog,
        supersedes_report=predecessor,
        supersedes_acquisition_receipt_bytes=predecessor_receipt,
        supersedes_snapshot=predecessor_snapshot,
    )


def _failure(outcome, code: str, member_key: str | None = None) -> None:
    assert outcome.report is None and outcome.failure is not None
    assert outcome.failure.code.value == code
    assert outcome.failure.member_key == member_key
    canonical = outcome.failure.to_canonical_dict()
    assert set(canonical) == {
        "type",
        "schema_version",
        "code",
        "member_key",
        "failure_hash",
    }
    assert "token" not in json.dumps(canonical).lower()


def _valid_alternate_g12i() -> bytes:
    value = json.loads(G12I_BYTES)
    value["supersedes_report_hash"] = "sha256:" + "a" * 64
    value["report_hash"] = canonical_sha256(
        {key: item for key, item in value.items() if key != "report_hash"}
    )
    return _json_bytes(value)


def _forge(value: Any, **changes: object) -> object:
    forged = object.__new__(type(value))
    for item in fields(value):
        object.__setattr__(
            forged,
            item.name,
            changes.get(item.name, getattr(value, item.name)),
        )
    return forged


def test_exact_public_contract_and_nominal_accepted_report() -> None:
    signature = inspect.signature(
        MODULE.observe_g12k_tushare_fixed_instrument_source_bounded_v1
    )
    assert list(signature.parameters) == [
        "g12i_report_bytes",
        "acquisition_receipt_bytes",
        "snapshot",
        "instrument_catalog",
        "supersedes_report",
        "supersedes_acquisition_receipt_bytes",
        "supersedes_snapshot",
    ]
    assert all(
        value.kind is inspect.Parameter.KEYWORD_ONLY
        for value in signature.parameters.values()
    )
    assert signature.return_annotation == (
        "G12KFixedInstrumentSourceBoundedObservationOutcomeV1"
    )
    assert [
        item.name
        for item in fields(MODULE.G12KFixedInstrumentSourceBoundedObservationOutcomeV1)
    ] == ["report", "failure"]

    outcome = _observe()
    assert outcome.failure is None and outcome.report is not None
    report = outcome.report
    expected = json.loads(REPORT_EXPECTED.read_bytes())
    assert (
        canonical_bytes(report.to_canonical_dict()) + b"\n"
        == REPORT_EXPECTED.read_bytes()
    )
    assert json.loads(canonical_bytes(report.to_canonical_dict())) == expected
    assert report.report_hash == (
        "sha256:5a49065d87286a9673893337328ddbbab9a19cd3addf178bf96033b9b1babfd7"
    )
    assert report.observed_at.epoch_nanoseconds == 1_787_299_622_295_499_670
    assert len(report.dividend_source_rows) == 96
    assert len(report.dividend_source_row_hashes) == 96
    assert len(set(report.dividend_source_row_hashes)) == 96
    assert report.target_relevance_fields == (
        "ann_date",
        "record_date",
        "ex_date",
        "pay_date",
        "div_listdate",
        "imp_ann_date",
    )
    assert report.target_relevant_row_hashes == ()
    assert report.dividend_response_has_more is False
    assert report.dividend_response_count_metadata == 0
    assert report.supersedes_report_hash is None
    assert not any(
        getattr(report, name)
        for name in (
            "availability_closure_complete",
            "revision_closure_complete",
            "provider_authority_qualified",
            "provider_revision_completeness_qualified",
            "historical_listing_status_qualified",
            "listing_membership_continuity_qualified",
            "whole_universe_complete",
            "survivorship_bias_safe",
            "corporate_action_lifecycle_qualified",
            "decision_grade_eligible",
            "profile_qualified",
            "live_eligible",
            "deployment_authorized",
        )
    )


def test_real_g12i_d2_and_g12cd_fixture_identities_are_bound() -> None:
    snapshot = _snapshot()
    assert hashlib.sha256(G12I_BYTES).hexdigest() == (
        "9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6"
    )
    assert hashlib.sha256(CATALOG_FIXTURE.read_bytes()).hexdigest() == (
        "d71ca8ed8977bf5fa0aa7cd1ab11fb85abcd5382f42c7e2bb2243d5b5290e456"
    )
    assert hashlib.sha256(RECEIPT_BYTES).hexdigest() == (
        "5524257ee9a464d8e72df803c1493bc92e59420f0af1f6593b23a22dbb93a240"
    )
    assert hashlib.sha256(RESPONSE_BYTES).hexdigest() == (
        "af19248549b55de24f36e120e4c416dd9a23d225c84f96edaa1534cfb377a8af"
    )
    assert snapshot.to_canonical_dict() == RECEIPT["snapshot"]
    assert snapshot.snapshot_id == (
        "sha256:ecb17991e82a73cc2eaaaa457ff72ccd89cb1a4a23fd595419983028f2c4a5c4"
    )
    assert snapshot.content_tree_hash == (
        "sha256:734b7b3460fda376ee105619fc4f20da33f88a3e5693de50c92389782b872809"
    )
    assert snapshot.provenance_hash == (
        "sha256:475f9a488e7e8c761bd01f55528f1185a1aacbba4868c00190d51a1200c18e0d"
    )
    assert snapshot.member_bytes("response/dividend.json") == RESPONSE_BYTES
    assert canonical_sha256(_catalog()) == (
        "sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc"
    )


def test_report_canonical_replay_rejects_tamper_flags_and_constructor_bypass() -> None:
    outcome = _observe()
    assert outcome.report is not None
    report = outcome.report
    rebuilt = (
        MODULE.G12KFixedInstrumentSourceBoundedObservationReportV1.from_canonical_dict(
            json.loads(canonical_bytes(report.to_canonical_dict()))
        )
    )
    assert rebuilt == report and rebuilt is not report

    for change in (
        {"unexpected": None},
        {"target_relevant_row_hashes": [report.dividend_source_row_hashes[0]]},
        {
            "dividend_source_row_hashes": list(
                reversed(report.dividend_source_row_hashes)
            )
        },
        {"decision_grade_eligible": True},
    ):
        value = json.loads(canonical_bytes(report.to_canonical_dict()))
        value.update(change)
        value["report_hash"] = canonical_sha256(
            {key: item for key, item in value.items() if key != "report_hash"}
        )
        with pytest.raises((TypeError, ValueError)):
            MODULE.G12KFixedInstrumentSourceBoundedObservationReportV1.from_canonical_dict(
                value
            )

    nested = json.loads(canonical_bytes(report.to_canonical_dict()))
    nested["instrument_id"]["stable_key"] = "000002"
    nested["report_hash"] = canonical_sha256(
        {key: item for key, item in nested.items() if key != "report_hash"}
    )
    with pytest.raises(ValueError, match="instrument scope"):
        MODULE.G12KFixedInstrumentSourceBoundedObservationReportV1.from_canonical_dict(
            nested
        )

    forged = _forge(report, report_hash="sha256:" + "f" * 64)
    with pytest.raises(ValueError, match="authority"):
        MODULE.G12KFixedInstrumentSourceBoundedObservationOutcomeV1(report=forged)


def test_unique_key_canonical_lf_and_source_substitution_fail_closed() -> None:
    _failure(_observe(g12i=G12I_BYTES.rstrip(b"\n")), "evidence_invalid")
    _failure(
        _observe(
            g12i=G12I_BYTES.replace(
                b'"provider_key":', b'"provider_key":"x","provider_key":', 1
            )
        ),
        "evidence_invalid",
    )
    _failure(_observe(g12i=_valid_alternate_g12i()), "source_reference_mismatch")

    noncanonical_receipt = json.dumps(RECEIPT, indent=2).encode()
    _failure(_observe(receipt=noncanonical_receipt), "evidence_invalid")
    duplicate_receipt = RECEIPT_BYTES.replace(
        b'"schema_version":1', b'"schema_version":1,"schema_version":1', 1
    )
    _failure(_observe(receipt=duplicate_receipt), "evidence_invalid")

    other_receipt, other_snapshot = _capture(
        lambda value: value.__setitem__("detail", "other source")
    )
    assert other_receipt != RECEIPT_BYTES
    _failure(_observe(snapshot=other_snapshot), "evidence_invalid")


def test_request_scope_response_page_and_catalog_failures_are_exact() -> None:
    receipt, snapshot = _capture(
        mutate_receipt=lambda value: value["request"].__setitem__(
            "coverage_start_date", "20260707"
        )
    )
    _failure(
        _observe(receipt=receipt, snapshot=snapshot),
        "request_scope_mismatch",
        "response/dividend.json",
    )

    receipt, snapshot = _capture(
        lambda value: value["data"].__setitem__(
            "fields", list(reversed(value["data"]["fields"]))
        )
    )
    _failure(
        _observe(receipt=receipt, snapshot=snapshot),
        "response_schema_mismatch",
        "response/dividend.json",
    )

    receipt, snapshot = _capture(
        lambda value: value["data"].__setitem__("has_more", True)
    )
    _failure(
        _observe(receipt=receipt, snapshot=snapshot),
        "response_page_incomplete",
        "response/dividend.json",
    )

    _failure(
        _observe(catalog=_catalog(stable_key="000002")), "source_reference_mismatch"
    )


def test_row_replay_relevance_and_receipt_metadata_tamper_are_detected() -> None:
    baseline = _observe()
    assert baseline.report is not None

    receipt, snapshot = _capture(
        lambda value: value["data"]["items"][0].__setitem__(8, 0.25)
    )
    changed = _observe(receipt=receipt, snapshot=snapshot)
    assert changed.failure is None and changed.report is not None
    assert (
        changed.report.dividend_source_row_hashes
        != baseline.report.dividend_source_row_hashes
    )
    assert changed.report.target_relevant_row_hashes == ()

    receipt, snapshot = _capture(
        lambda value: value["data"]["items"][0].__setitem__(2, "20260706")
    )
    relevant = _observe(receipt=receipt, snapshot=snapshot)
    assert relevant.failure is None and relevant.report is not None
    assert relevant.report.target_relevant_row_hashes == (
        relevant.report.dividend_source_row_hashes[0],
    )

    receipt = deepcopy(RECEIPT)
    receipt["provider_requests"][0]["returned_row_count"] = 95
    _failure(
        _observe(receipt=_json_bytes(receipt)),
        "evidence_invalid",
        "response/dividend.json",
    )


def test_direct_predecessor_is_deep_validated_without_currentness_claims() -> None:
    first = _observe()
    assert first.report is not None
    first_bytes = canonical_bytes(first.report)

    def corrected_response(value: dict[str, Any]) -> None:
        value["detail"] = "corrected capture"
        value["data"]["items"][0][2] = "20260706"

    receipt, snapshot = _capture(
        corrected_response,
        time_delta=10_000_000_000,
    )
    corrected = _observe(
        receipt=receipt,
        snapshot=snapshot,
        predecessor=first.report,
    )
    assert corrected.failure is None and corrected.report is not None
    report = corrected.report
    assert canonical_bytes(first.report) == first_bytes
    assert report.supersedes_report_hash == first.report.report_hash
    assert report.snapshot_id != first.report.snapshot_id
    assert report.observed_at > first.report.observed_at
    assert report.dividend_source_row_hashes != first.report.dividend_source_row_hashes
    assert report.target_relevant_row_hashes == (report.dividend_source_row_hashes[0],)
    assert report.report_hash != first.report.report_hash
    replay = _observe(
        receipt=receipt,
        snapshot=snapshot,
        predecessor=first.report,
    )
    assert replay.report == report

    forged = _forge(first.report, report_hash="sha256:" + "f" * 64)
    _failure(_observe(predecessor=forged), "predecessor_invalid")

    reordered_value = json.loads(canonical_bytes(first.report.to_canonical_dict()))
    reordered_value["dividend_source_rows"].reverse()
    reordered_value["dividend_source_row_hashes"].reverse()
    reordered_value["report_hash"] = canonical_sha256(
        {key: value for key, value in reordered_value.items() if key != "report_hash"}
    )
    reordered = (
        MODULE.G12KFixedInstrumentSourceBoundedObservationReportV1.from_canonical_dict(
            reordered_value
        )
    )
    _failure(_observe(predecessor=reordered), "predecessor_invalid")

    wrong_receipt, wrong_snapshot = _capture(
        lambda value: value["data"]["items"][0].__setitem__(8, 0.25)
    )
    _failure(
        _observe(
            predecessor=first.report,
            predecessor_receipt=wrong_receipt,
            predecessor_snapshot=wrong_snapshot,
        ),
        "predecessor_invalid",
    )
    _failure(_observe(predecessor=first.report), "correction_edge_invalid")

    partial = MODULE.observe_g12k_tushare_fixed_instrument_source_bounded_v1(
        g12i_report_bytes=G12I_BYTES,
        acquisition_receipt_bytes=RECEIPT_BYTES,
        snapshot=_snapshot(),
        instrument_catalog=_catalog(),
        supersedes_report=first.report,
    )
    _failure(partial, "predecessor_invalid")

    earlier_receipt, earlier_snapshot = _capture(
        lambda value: value.__setitem__("detail", "earlier correction"),
        time_delta=-1,
    )
    _failure(
        _observe(
            receipt=earlier_receipt,
            snapshot=earlier_snapshot,
            predecessor=first.report,
        ),
        "correction_edge_invalid",
    )


def test_failure_precedence_is_structured_and_atomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome = MODULE.observe_g12k_tushare_fixed_instrument_source_bounded_v1(
        g12i_report_bytes=b"{}",
        acquisition_receipt_bytes=b"{}",
        snapshot=object(),
        instrument_catalog=object(),
    )
    _failure(outcome, "invalid_input")

    receipt, snapshot = _capture(
        lambda value: value.__setitem__("data", "bad"),
        mutate_receipt=lambda value: value["request"].__setitem__(
            "coverage_start_date", "20260707"
        ),
    )
    _failure(
        _observe(receipt=receipt, snapshot=snapshot),
        "request_scope_mismatch",
        "response/dividend.json",
    )

    receipt, snapshot = _capture(
        lambda value: value["data"].__setitem__("has_more", True)
    )
    _failure(
        _observe(
            g12i=_valid_alternate_g12i(),
            receipt=receipt,
            snapshot=snapshot,
        ),
        "response_page_incomplete",
        "response/dividend.json",
    )

    first = _observe()
    assert first.report is not None
    forged = _forge(first.report, report_hash="sha256:" + "f" * 64)
    _failure(
        _observe(g12i=_valid_alternate_g12i(), predecessor=forged),
        "source_reference_mismatch",
    )

    original = MODULE._build_report
    monkeypatch.setattr(
        MODULE,
        "_build_report",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("binding")),
    )
    _failure(_observe(), "report_binding_mismatch")
    monkeypatch.setattr(MODULE, "_build_report", original)


def test_observer_has_no_io_network_runtime_kernel_or_generic_framework() -> None:
    source = Path(cast(str, MODULE.__file__)).read_text(encoding="utf-8")
    for forbidden in (
        "crypto_quant_backtest",
        "crypto_quant_trading",
        "pathlib",
        "httpx",
        "socket",
        "open(",
        "MarketBundle",
        "MarketEvent",
        "Runtime",
        "Kernel",
        "LocalMarketBundleRepository",
    ):
        assert forbidden not in source
