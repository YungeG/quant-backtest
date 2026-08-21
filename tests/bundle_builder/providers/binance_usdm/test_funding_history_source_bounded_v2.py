from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import fields
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import pytest
from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    validate_market_bundle_v1,
)
from crypto_quant_domain import canonical_bytes, canonical_sha256

MODULE = import_module(
    "crypto_quant_bundle_builder.binance_usdm_funding_history_source_bounded_v2"
)
ROOT = Path(__file__).resolve().parents[3]
FIXTURE = (
    ROOT
    / "fixtures/market_data/providers/binance_usdm/funding-history-source-bounded-v2"
)
REPORT_EXPECTED = FIXTURE / "observation-report.expected.json"
RECEIPT_BYTES = (FIXTURE / "acquisition-receipt.json").read_bytes()
RESPONSE_BYTES = (FIXTURE / "response/funding-history.json").read_bytes()
RECEIPT = cast(dict[str, Any], json.loads(RECEIPT_BYTES))
PROVENANCE = SourceSnapshotProvenance(
    "binance.fapi",
    "binance.fapi.funding_rate_history.btcusdt.1704067200000.1704153599999",
    "binance.api.terms",
    "backtest.acquisition.candidate",
)
MEMBER_KEY = "response/funding-history.json"


def _json_bytes(value: object) -> bytes:
    return canonical_bytes(value) + b"\n"


def _snapshot(
    response_bytes: bytes = RESPONSE_BYTES,
    *,
    acquired_at: int = RECEIPT["acquired_at_epoch_nanoseconds"],
    provenance: SourceSnapshotProvenance = PROVENANCE,
):
    outcome = freeze_source_snapshot(
        members=(
            RawSourceMember(
                MEMBER_KEY,
                response_bytes,
                "0644",
                acquired_at,
                None,
            ),
        ),
        provenance=provenance,
    )
    assert outcome.failure is None and outcome.snapshot is not None
    return outcome.snapshot


def _capture(
    response_bytes: bytes,
    *,
    acquired_at: int = RECEIPT["acquired_at_epoch_nanoseconds"],
    mutate_receipt=None,
    provenance: SourceSnapshotProvenance = PROVENANCE,
) -> tuple[bytes, object]:
    receipt = deepcopy(RECEIPT)
    snapshot = _snapshot(
        response_bytes,
        acquired_at=acquired_at,
        provenance=provenance,
    )
    receipt["acquired_at_epoch_nanoseconds"] = acquired_at
    receipt["response_sha256"] = "sha256:" + hashlib.sha256(response_bytes).hexdigest()
    receipt["snapshot"] = snapshot.to_canonical_dict()
    try:
        rows = json.loads(response_bytes)
        receipt["record_count"] = len(rows)
        receipt["missing_mark_price_count"] = sum(
            type(row) is dict and row.get("markPrice") == "" for row in rows
        )
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    if mutate_receipt is not None:
        mutate_receipt(receipt)
    return _json_bytes(receipt), snapshot


def _wire_rows(mutate) -> bytes:
    rows = json.loads(RESPONSE_BYTES)
    mutate(rows)
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()


def _observe(
    receipt_bytes: bytes = RECEIPT_BYTES,
    snapshot=None,
    **predecessor,
):
    return MODULE.observe_binance_usdm_funding_history_source_bounded_v2(
        acquisition_receipt_bytes=receipt_bytes,
        snapshot=_snapshot() if snapshot is None else snapshot,
        **predecessor,
    )


def _failure(outcome, code: str) -> None:
    assert outcome.report is None and outcome.failure is not None
    assert outcome.failure.code.value == code
    assert set(outcome.failure.to_canonical_dict()) == {
        "type",
        "schema_version",
        "code",
        "member_key",
        "failure_hash",
    }
    assert "token" not in json.dumps(outcome.failure.to_canonical_dict()).lower()


def _publication(snapshot, report):
    rows = MODULE._normalize(report.source_rows)
    events = MODULE._events(
        rows,
        snapshot_id=snapshot.snapshot_id,
        response_hash=snapshot.members[0].content_hash,
        observed_at=report.observed_at,
    )
    validation = validate_market_bundle_v1(
        bundle_key=report.bundle_ref.bundle_key,
        schema_version=1,
        coverage_start=report.coverage_start,
        coverage_end_exclusive=report.coverage_end_exclusive,
        instrument_catalog_hash="sha256:" + "0" * 64,
        events=events,
    )
    assert validation.failure is None and validation.manifest is not None
    return events, validation.manifest


def test_exact_fixture_report_rows_events_manifest_hashes_and_g12d_publication(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot()
    outcome = _observe(snapshot=snapshot)
    assert outcome.failure is None and outcome.report is not None
    report = outcome.report
    expected = json.loads(REPORT_EXPECTED.read_bytes())

    assert hashlib.sha256(RESPONSE_BYTES).hexdigest() == (
        "e9f73f9c845c28abb31037d8230df2d6f13d5d368c43436e891fcc757372c338"
    )
    assert hashlib.sha256(RECEIPT_BYTES).hexdigest() == (
        "a92989478047de7d744744aedeaf365f7d16240b536c1ccece749abe3b4efa36"
    )
    assert len(RESPONSE_BYTES) == 379
    assert snapshot.to_canonical_dict() == RECEIPT["snapshot"]
    assert json.loads(canonical_bytes(report.to_canonical_dict())) == expected
    assert report.report_hash == expected["report_hash"]
    assert report.source_rows == (
        ("BTCUSDT", 1_704_067_200_000, "0.00037409", "42313.90000000", "Regular"),
        ("BTCUSDT", 1_704_096_000_000, "0.00027213", "42525.11019858", "Regular"),
        ("BTCUSDT", 1_704_124_800_000, "0.00033601", "42811.29637234", "Regular"),
    )
    assert report.source_record_hashes == tuple(
        canonical_sha256(
            {
                "fields": (
                    "symbol",
                    "fundingTime",
                    "fundingRate",
                    "markPrice",
                    "rateType",
                ),
                "row": row,
            }
        )
        for row in report.source_rows
    )

    events, manifest = _publication(snapshot, report)
    assert [event.payload["funding_rate_units"] for event in events] == [
        37409,
        27213,
        33601,
    ]
    assert [event.payload["mark_price_units"] for event in events] == [
        4_231_390_000_000,
        4_252_511_019_858,
        4_281_129_637_234,
    ]
    assert [event.payload["funding_rate"] for event in events] == [
        "0.00037409",
        "0.00027213",
        "0.00033601",
    ]
    assert tuple(event.event_hash for event in events) == report.published_event_hashes
    assert canonical_sha256(events) == report.stream_content_hash
    assert manifest.content_hash == report.manifest_content_hash
    assert manifest.streams[0].content_hash == report.stream_content_hash
    assert MODULE.MarketBundleRef.from_manifest(manifest) == report.bundle_ref

    repository = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(tmp_path.resolve())
    )
    arguments = {
        "manifest": manifest,
        "stream_payloads": {events[0].stream_key: canonical_bytes(events)},
        "retention_policy_ref": "backtest.g12l-binance-funding-source-bounded-v2",
    }
    first = repository.publish_market_bundle_v1(**arguments)
    replay = repository.publish_market_bundle_v1(**arguments)
    assert first.failure is None and first.result is not None
    assert replay.failure is None and replay.result is not None
    assert first.result.bundle_ref == replay.result.bundle_ref == report.bundle_ref
    assert first.result.already_published is False
    assert replay.result.already_published is True


def test_deep_reconstruction_rejects_constructor_bypass_and_canonical_tampering() -> (
    None
):
    outcome = _observe()
    assert outcome.report is not None
    report = outcome.report
    canonical = json.loads(canonical_bytes(report.to_canonical_dict()))
    rebuilt = MODULE.BinanceUsdmFundingHistorySourceBoundedObservationReportV2.from_canonical_dict(
        canonical
    )
    assert rebuilt == report and rebuilt is not report

    cases = []
    unknown = deepcopy(canonical)
    unknown["unknown"] = False
    cases.append(unknown)
    nested = deepcopy(canonical)
    nested["observed_at"] = {"type": "utc_instant", "epoch_nanoseconds": True}
    cases.append(nested)
    row = deepcopy(canonical)
    row["source_rows"][0][2] = "0.00037408"
    row["report_hash"] = canonical_sha256(
        {key: value for key, value in row.items() if key != "report_hash"}
    )
    cases.append(row)
    event = deepcopy(canonical)
    event["published_event_hashes"][0] = "sha256:" + "f" * 64
    event["report_hash"] = canonical_sha256(
        {key: value for key, value in event.items() if key != "report_hash"}
    )
    cases.append(event)
    manifest = deepcopy(canonical)
    manifest["stream_content_hash"] = "sha256:" + "f" * 64
    manifest["report_hash"] = canonical_sha256(
        {key: value for key, value in manifest.items() if key != "report_hash"}
    )
    cases.append(manifest)
    true_flag = deepcopy(canonical)
    true_flag["live_eligible"] = True
    true_flag["report_hash"] = canonical_sha256(
        {key: value for key, value in true_flag.items() if key != "report_hash"}
    )
    cases.append(true_flag)
    for bad in cases:
        with pytest.raises((TypeError, ValueError)):
            MODULE.BinanceUsdmFundingHistorySourceBoundedObservationReportV2.from_canonical_dict(
                bad
            )

    forged = object.__new__(type(report))
    for item in fields(report):
        object.__setattr__(forged, item.name, getattr(report, item.name))
    object.__setattr__(forged, "stream_content_hash", "sha256:" + "f" * 64)
    with pytest.raises(ValueError, match="authority"):
        MODULE.BinanceUsdmFundingHistorySourceBoundedObservationOutcomeV2(report=forged)


def test_exact_scale_accepts_trailing_zero_and_never_rounds() -> None:
    exact = _wire_rows(lambda rows: rows[0].__setitem__("fundingRate", "0.000374090"))
    receipt_bytes, snapshot = _capture(exact)
    outcome = _observe(receipt_bytes, snapshot)
    assert outcome.report is not None
    events, _ = _publication(snapshot, outcome.report)
    assert events[0].payload["raw_funding_rate"] == "0.000374090"
    assert events[0].payload["funding_rate"] == "0.00037409"
    assert events[0].payload["funding_rate_units"] == 37_409

    overprecise = _wire_rows(
        lambda rows: rows[0].__setitem__("fundingRate", "0.000374091")
    )
    receipt_bytes, snapshot = _capture(overprecise)
    _failure(_observe(receipt_bytes, snapshot), "normalization_failed")

    zero_mark = _wire_rows(lambda rows: rows[0].__setitem__("markPrice", "0.00000000"))
    receipt_bytes, snapshot = _capture(zero_mark)
    _failure(_observe(receipt_bytes, snapshot), "normalization_failed")


@pytest.mark.parametrize(
    ("response_bytes", "expected"),
    (
        (
            RESPONSE_BYTES.replace(
                b'"fundingRate":"0.00037409"',
                b'"fundingRate":"0.00037409","fundingRate":"0.00037409"',
                1,
            ),
            "response_schema_mismatch",
        ),
        (RESPONSE_BYTES + b"\n", "response_schema_mismatch"),
        (
            _wire_rows(lambda rows: rows[0].__setitem__("fundingRate", "+0.00037409")),
            "response_schema_mismatch",
        ),
        (
            _wire_rows(lambda rows: rows[0].__setitem__("fundingRate", "-0.00000000")),
            "response_schema_mismatch",
        ),
        (
            _wire_rows(lambda rows: rows[0].__setitem__("rateType", "Special")),
            "response_scope_mismatch",
        ),
        (
            _wire_rows(lambda rows: rows[0].__setitem__("markPrice", "")),
            "response_scope_mismatch",
        ),
        (
            _wire_rows(lambda rows: rows.reverse()),
            "response_scope_mismatch",
        ),
    ),
)
def test_response_duplicate_canonical_schema_and_scope_fail_closed(
    response_bytes: bytes, expected: str
) -> None:
    receipt_bytes, snapshot = _capture(response_bytes)
    _failure(_observe(receipt_bytes, snapshot), expected)


def test_failure_precedence_all_classes_and_lookahead_preflights_event_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _failure(
        MODULE.observe_binance_usdm_funding_history_source_bounded_v2(
            acquisition_receipt_bytes=b"{}",
            snapshot=object(),
        ),
        "invalid_input",
    )

    bad_receipt = deepcopy(RECEIPT)
    bad_receipt["attempts"] = True
    _failure(_observe(_json_bytes(bad_receipt)), "evidence_invalid")

    wrong_request = deepcopy(RECEIPT)
    wrong_request["request"]["symbol"] = "ETHUSDT"
    _failure(_observe(_json_bytes(wrong_request)), "request_scope_mismatch")

    receipt_bytes, snapshot = _capture(b"not-json")
    _failure(_observe(receipt_bytes, snapshot), "response_schema_mismatch")

    wrong_scope = _wire_rows(lambda rows: rows[0].__setitem__("symbol", "ETHUSDT"))
    receipt_bytes, snapshot = _capture(wrong_scope)
    _failure(_observe(receipt_bytes, snapshot), "response_scope_mismatch")

    overprecise = _wire_rows(
        lambda rows: rows[0].__setitem__("markPrice", "42313.900000001")
    )
    receipt_bytes, snapshot = _capture(overprecise)
    _failure(_observe(receipt_bytes, snapshot), "normalization_failed")

    event_calls = 0
    real_event = MODULE.MarketEvent

    def tracking_event(*args, **kwargs):
        nonlocal event_calls
        event_calls += 1
        return real_event(*args, **kwargs)

    monkeypatch.setattr(MODULE, "MarketEvent", tracking_event)
    receipt_bytes, snapshot = _capture(
        RESPONSE_BYTES,
        acquired_at=1_704_124_800_000_000_000,
    )
    _failure(_observe(receipt_bytes, snapshot), "lookahead_violation")
    assert event_calls == 0
    monkeypatch.setattr(MODULE, "MarketEvent", real_event)

    monkeypatch.setattr(MODULE, "_publication", lambda _: None)
    _failure(_observe(), "publication_failed")
    monkeypatch.undo()

    first = _observe()
    assert first.report is not None
    _failure(
        _observe(supersedes_report=first.report),
        "predecessor_invalid",
    )
    _failure(
        _observe(
            supersedes_report=first.report,
            supersedes_acquisition_receipt_bytes=RECEIPT_BYTES,
            supersedes_snapshot=_snapshot(),
        ),
        "correction_edge_invalid",
    )

    monkeypatch.setattr(MODULE, "_reconstruct_report", lambda _: None)
    _failure(_observe(), "report_binding_mismatch")


def test_correction_requires_changed_response_and_full_predecessor_evidence() -> None:
    first = _observe()
    assert first.report is not None
    first_bytes = canonical_bytes(first.report.to_canonical_dict())

    corrected_response = _wire_rows(
        lambda rows: rows[0].__setitem__("fundingRate", "0.00037408")
    )
    receipt_bytes, snapshot = _capture(
        corrected_response,
        acquired_at=RECEIPT["acquired_at_epoch_nanoseconds"] + 10_000_000_000,
    )
    corrected = _observe(
        receipt_bytes,
        snapshot,
        supersedes_report=first.report,
        supersedes_acquisition_receipt_bytes=RECEIPT_BYTES,
        supersedes_snapshot=_snapshot(),
    )
    assert corrected.failure is None and corrected.report is not None
    report = corrected.report
    assert canonical_bytes(first.report.to_canonical_dict()) == first_bytes
    assert report.supersedes_report_hash == first.report.report_hash
    assert report.report_hash != first.report.report_hash
    assert report.snapshot_id != first.report.snapshot_id
    assert report.member_content_hashes != first.report.member_content_hashes
    assert report.published_event_hashes != first.report.published_event_hashes
    assert report.observed_at > first.report.observed_at

    replay = _observe(
        receipt_bytes,
        snapshot,
        supersedes_report=first.report,
        supersedes_acquisition_receipt_bytes=RECEIPT_BYTES,
        supersedes_snapshot=_snapshot(),
    )
    assert replay.report == report

    for predecessor in (
        {"supersedes_report": first.report},
        {"supersedes_acquisition_receipt_bytes": RECEIPT_BYTES},
        {"supersedes_snapshot": _snapshot()},
        {
            "supersedes_report": first.report,
            "supersedes_acquisition_receipt_bytes": RECEIPT_BYTES,
        },
    ):
        _failure(
            _observe(receipt_bytes, snapshot, **predecessor), "predecessor_invalid"
        )

    tampered_predecessor = bytearray(RECEIPT_BYTES)
    tampered_predecessor[-2] = ord("x")
    _failure(
        _observe(
            receipt_bytes,
            snapshot,
            supersedes_report=first.report,
            supersedes_acquisition_receipt_bytes=bytes(tampered_predecessor),
            supersedes_snapshot=_snapshot(),
        ),
        "predecessor_invalid",
    )
