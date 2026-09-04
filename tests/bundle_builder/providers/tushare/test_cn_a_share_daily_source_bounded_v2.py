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
from crypto_quant_domain import PricePurpose, canonical_bytes, canonical_sha256

MODULE = import_module(
    "crypto_quant_bundle_builder.tushare_cn_a_share_daily_source_bounded_v2"
)
NORMALIZER = import_module("crypto_quant_bundle_builder.tushare_cn_a_share_daily")
ROOT = Path(__file__).parents[3]
FIXTURE = (
    ROOT / "fixtures/market_data/providers/tushare/cn-a-share-daily-source-bounded-v2"
)
REPORT_EXPECTED = FIXTURE / "observation-report.expected.json"
PUBLICATION_EXPECTED = FIXTURE / "publication.expected.json"
RECEIPT_BYTES = (FIXTURE / "acquisition-receipt.json").read_bytes()
RECEIPT = cast(dict[str, Any], json.loads(RECEIPT_BYTES))
PROVENANCE = SourceSnapshotProvenance(
    "tushare.pro",
    "tushare.pro.cn_a_share_daily_source_bounded_v2.000001.sz.20260706.20260730",
    "tushare.pro.terms",
    "backtest.acquisition.candidate",
)
OPEN_DATES = (
    "20260706",
    "20260707",
    "20260708",
    "20260709",
    "20260710",
    "20260713",
    "20260714",
    "20260715",
    "20260716",
    "20260717",
    "20260720",
    "20260721",
    "20260722",
    "20260723",
    "20260724",
    "20260727",
    "20260728",
    "20260729",
    "20260730",
)
CLOSED_DATES = (
    "20260711",
    "20260712",
    "20260718",
    "20260719",
    "20260725",
    "20260726",
)


def _json_bytes(value: object) -> bytes:
    return canonical_bytes(value) + b"\n"


def _raw_members() -> dict[str, bytes]:
    return {
        request["member_key"]: (FIXTURE / request["member_key"]).read_bytes()
        for request in RECEIPT["provider_requests"]
    }


def _snapshot(
    raw: dict[str, bytes] | None = None,
    receipt: dict[str, Any] | None = None,
):
    values = RECEIPT if receipt is None else receipt
    by_key = {request["member_key"]: request for request in values["provider_requests"]}
    outcome = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                key,
                source,
                "0644",
                by_key[key]["response_received_at_epoch_nanoseconds"],
                None,
            )
            for key, source in (raw or _raw_members()).items()
        ),
        provenance=PROVENANCE,
    )
    assert outcome.failure is None and outcome.snapshot is not None
    return outcome.snapshot


def _capture(
    mutate,
    *,
    time_delta: int = 0,
) -> tuple[bytes, object]:
    raw = _raw_members()
    receipt = deepcopy(RECEIPT)
    mutate(raw, receipt)
    for request in receipt["provider_requests"]:
        key = request["member_key"]
        request["response_received_at_epoch_nanoseconds"] += time_delta
        source = raw[key]
        request["response_byte_count"] = len(source)
        request["response_sha256"] = "sha256:" + hashlib.sha256(source).hexdigest()
        try:
            payload = json.loads(source)
            request["observed_envelope"] = {
                "has_more": payload["data"]["has_more"],
                "count": payload["data"]["count"],
            }
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
            pass
    receipt["acquired_at_epoch_nanoseconds"] = max(
        request["response_received_at_epoch_nanoseconds"]
        for request in receipt["provider_requests"]
    )
    snapshot = _snapshot(raw, receipt)
    receipt["snapshot"] = snapshot.to_canonical_dict()
    return _json_bytes(receipt), snapshot


def _wire_change(raw: dict[str, bytes], key: str, mutate) -> None:
    value = json.loads(raw[key])
    mutate(value)
    raw[key] = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def _observe(
    receipt_bytes: bytes = RECEIPT_BYTES,
    snapshot=None,
    supersedes=None,
):
    return MODULE.observe_tushare_cn_a_share_daily_source_bounded_v2(
        receipt_bytes,
        _snapshot() if snapshot is None else snapshot,
        supersedes,
    )


def _publication(snapshot, report):
    events = MODULE._normalize_events(snapshot, report.published_provider_dates)
    assert events is not None
    validation = validate_market_bundle_v1(
        bundle_key=report.bundle_ref.bundle_key,
        schema_version=1,
        coverage_start=report.coverage_start,
        coverage_end_exclusive=report.coverage_end_exclusive,
        instrument_catalog_hash="sha256:" + "0" * 64,
        events=events,
    )
    assert validation.failure is None and validation.manifest is not None
    return events, validation.manifest, MODULE._requirements(snapshot)


def _failure(outcome, code: str) -> None:
    assert outcome.report is None and outcome.failure is not None
    assert outcome.failure.code.value == code
    assert set(outcome.failure.to_canonical_dict()) == {
        "type",
        "schema_version",
        "code",
        "provider_date",
        "member_key",
        "failure_hash",
    }
    assert "token" not in json.dumps(outcome.failure.to_canonical_dict()).lower()


def test_live_fixture_receipt_snapshot_rows_report_and_publication_are_exact(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot()
    outcome = _observe(snapshot=snapshot)
    assert outcome.failure is None and outcome.report is not None
    report = outcome.report
    report_expected = json.loads(REPORT_EXPECTED.read_bytes())
    publication_expected = json.loads(PUBLICATION_EXPECTED.read_bytes())

    assert hashlib.sha256(RECEIPT_BYTES).hexdigest() == (
        "95ba0d8e28414aa997e232c90eee03318f13f2c9041b36f4da046bbc5b2fb623"
    )
    assert len(snapshot.members) == len(RECEIPT["provider_requests"]) == 51
    assert snapshot.snapshot_id == (
        "sha256:9f1915e302e1a1f5b74a2cdccb54c08676642da3b48642eb9bbf728dc4c98f2e"
    )
    assert snapshot.content_tree_hash == (
        "sha256:ef44ecd44476dcd3d1cd69f82305df29d186c82350c45f427b5bf008b62d57af"
    )
    assert snapshot.provenance_hash == (
        "sha256:4dba800ca4688504c804009bcb21a4698cc431761be6847a81bfeef02a0e05e4"
    )
    assert snapshot.to_canonical_dict() == RECEIPT["snapshot"]
    assert json.loads(canonical_bytes(report.to_canonical_dict())) == report_expected
    assert canonical_bytes(report.to_canonical_dict()) == canonical_bytes(
        report_expected
    )
    assert report.report_hash == (
        "sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029"
    )
    assert report.published_provider_dates == OPEN_DATES
    assert report.no_session_provider_dates == CLOSED_DATES
    assert report.suspended_provider_dates == ()
    assert report.observed_at.epoch_nanoseconds == 1_787_292_861_381_694_496
    assert report.supersedes_report_hash is None
    assert not any(
        (
            report.availability_closure_complete,
            report.revision_closure_complete,
            report.generic_price_bars_capability,
            report.g12i_analyzer_ready,
            report.provider_qualified,
            report.historical_listing_status_qualified,
            report.corporate_actions_qualified,
            report.decision_grade_eligible,
            report.deployment_authorized,
        )
    )

    parsed = {request["api_name"]: [] for request in RECEIPT["provider_requests"]}
    for request in RECEIPT["provider_requests"]:
        parsed[request["api_name"]].extend(
            json.loads((FIXTURE / request["member_key"]).read_bytes())["data"]["items"]
        )
    assert len(parsed["daily"]) == 19
    assert len(parsed["trade_cal"]) == 25
    assert sum(row[2] for row in parsed["trade_cal"]) == 19
    assert len(parsed["suspend_d"]) == 0

    events, manifest, requirements = _publication(snapshot, report)
    assert [json.loads(canonical_bytes(value)) for value in events] == (
        publication_expected["events"]
    )
    assert json.loads(canonical_bytes(manifest)) == publication_expected["manifest"]
    assert [
        json.loads(canonical_bytes(value)) for value in requirements
    ] == publication_expected["requirements"]
    assert [value.event_hash for value in events] == list(report.published_event_hashes)
    assert [
        value.payload["raw_bar"]["provider_trade_date"] for value in events
    ] == list(OPEN_DATES)
    assert events[0].payload["raw_bar"]["amount"] == {
        "type": "money",
        "units": 110_390_258_344,
        "scale": 2,
        "currency": "CNY",
    }
    assert events[8].payload["raw_bar"]["amount"] == {
        "type": "money",
        "units": 864_435_895,
        "scale": 0,
        "currency": "CNY",
    }
    assert "price_purpose" not in events[0].payload["raw_bar"]
    assert [value.price_purpose for value in requirements] == [
        PricePurpose.EXECUTION_REFERENCE,
        PricePurpose.VALUATION,
    ]
    assert all(
        value.stale_policy.max_age_nanoseconds == 0
        and value.stale_policy.allow_forward_fill is False
        for value in requirements
    )
    assert report.bundle_ref.to_canonical_dict() == publication_expected["bundle_ref"]
    assert report.manifest_content_hash == manifest.content_hash
    assert report.stream_content_hash == manifest.streams[0].content_hash

    repository = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(tmp_path.resolve())
    )
    arguments = {
        "manifest": manifest,
        "stream_payloads": {events[0].stream_key: canonical_bytes(events)},
        "retention_policy_ref": "retention.g12i-tushare-source-bounded-v2",
    }
    first = repository.publish_market_bundle_v1(**arguments)
    replay = repository.publish_market_bundle_v1(**arguments)
    assert first.failure is None and first.result is not None
    assert replay.failure is None and replay.result is not None
    assert first.result.bundle_ref == replay.result.bundle_ref == report.bundle_ref
    assert first.result.already_published is False
    assert replay.result.already_published is True


def test_report_deep_reconstruction_and_constructor_bypass_fail_closed() -> None:
    outcome = _observe()
    assert outcome.report is not None
    report = outcome.report
    rebuilt = (
        MODULE.TushareCnAShareDailySourceBoundedObservationReportV2.from_canonical_dict(
            json.loads(canonical_bytes(report.to_canonical_dict()))
        )
    )
    assert rebuilt == report and rebuilt is not report

    bad = json.loads(canonical_bytes(report.to_canonical_dict()))
    bad["stream_content_hash"] = "sha256:" + "f" * 64
    with pytest.raises(ValueError, match="manifest binding mismatch"):
        MODULE.TushareCnAShareDailySourceBoundedObservationReportV2.from_canonical_dict(
            bad
        )

    mismatched_manifest = json.loads(canonical_bytes(report.to_canonical_dict()))
    mismatched_manifest["bundle_ref"]["manifest_hash"] = "sha256:" + "f" * 64
    mismatched_manifest["report_hash"] = canonical_sha256(
        {
            key: value
            for key, value in mismatched_manifest.items()
            if key != "report_hash"
        }
    )
    with pytest.raises(ValueError, match="Bundle ref mismatch"):
        MODULE.TushareCnAShareDailySourceBoundedObservationReportV2.from_canonical_dict(
            mismatched_manifest
        )

    forged = object.__new__(type(report))
    for item in fields(report):
        object.__setattr__(forged, item.name, getattr(report, item.name))
    object.__setattr__(forged, "stream_content_hash", "sha256:" + "f" * 64)
    with pytest.raises(ValueError, match="authority"):
        MODULE.TushareCnAShareDailySourceBoundedObservationOutcomeV2(report=forged)
    _failure(_observe(supersedes=forged), "invalid_input")


def test_correction_is_append_only_and_exactly_supersedes_prior_report() -> None:
    first = _observe()
    assert first.report is not None
    first_bytes = canonical_bytes(first.report)

    receipt_bytes, snapshot = _capture(
        lambda raw, _: _wire_change(
            raw,
            "response/daily/20260706.json",
            lambda value: value.__setitem__("detail", "corrected capture"),
        ),
        time_delta=10_000_000_000,
    )
    corrected = _observe(receipt_bytes, snapshot, first.report)
    assert corrected.failure is None and corrected.report is not None
    report = corrected.report
    assert canonical_bytes(first.report) == first_bytes
    assert report.supersedes_report_hash == first.report.report_hash
    assert report.report_hash != first.report.report_hash
    assert report.snapshot_id != first.report.snapshot_id
    assert report.acquisition_receipt_sha256 != (
        first.report.acquisition_receipt_sha256
    )
    assert report.published_event_hashes != first.report.published_event_hashes
    assert report.observed_at > first.report.observed_at

    replay = _observe(receipt_bytes, snapshot, first.report)
    assert replay.failure is None and replay.report == report
    _failure(
        _observe(RECEIPT_BYTES, _snapshot(), first.report), "report_binding_mismatch"
    )


def test_failure_precedence_is_atomic_for_scope_schema_page_conflict_and_absence() -> (
    None
):
    _failure(
        MODULE.observe_tushare_cn_a_share_daily_source_bounded_v2(b"{}", object()),
        "invalid_input",
    )

    corrupted = bytearray(RECEIPT_BYTES)
    corrupted[-2] = ord("x")
    _failure(_observe(bytes(corrupted)), "evidence_invalid")

    def wrong_scope_and_schema(raw, receipt) -> None:
        receipt["request"]["exchange"] = "SSE"
        raw["response/daily/20260706.json"] = b"not-json"

    receipt_bytes, snapshot = _capture(wrong_scope_and_schema)
    _failure(_observe(receipt_bytes, snapshot), "request_scope_mismatch")

    receipt_bytes, snapshot = _capture(
        lambda raw, _: raw.__setitem__("response/daily/20260706.json", b"not-json")
    )
    _failure(_observe(receipt_bytes, snapshot), "response_schema_mismatch")

    def page_and_conflict(raw, _) -> None:
        _wire_change(
            raw,
            "response/daily/20260706.json",
            lambda value: value["data"].__setitem__("has_more", True),
        )
        row = json.loads(raw["response/daily/20260706.json"])["data"]["items"][0]
        _wire_change(
            raw,
            "response/daily/20260711.json",
            lambda value: value["data"]["items"].append([row[0], "20260711", *row[2:]]),
        )

    receipt_bytes, snapshot = _capture(page_and_conflict)
    _failure(_observe(receipt_bytes, snapshot), "response_page_incomplete")

    def closed_day_conflict(raw, _) -> None:
        row = json.loads(raw["response/daily/20260706.json"])["data"]["items"][0]
        _wire_change(
            raw,
            "response/daily/20260711.json",
            lambda value: value["data"]["items"].append([row[0], "20260711", *row[2:]]),
        )
        _wire_change(
            raw,
            "response/daily/20260707.json",
            lambda value: value["data"].__setitem__("items", []),
        )

    receipt_bytes, snapshot = _capture(closed_day_conflict)
    _failure(_observe(receipt_bytes, snapshot), "source_observation_conflict")

    receipt_bytes, snapshot = _capture(
        lambda raw, _: _wire_change(
            raw,
            "response/daily/20260707.json",
            lambda value: value["data"].__setitem__("items", []),
        )
    )
    outcome = _observe(receipt_bytes, snapshot)
    _failure(outcome, "missing_classification")
    assert outcome.failure.provider_date == "20260707"


def test_full_day_suspension_classifies_but_intraday_absence_does_not() -> None:
    def suspended(raw, _) -> None:
        _wire_change(
            raw,
            "response/daily/20260707.json",
            lambda value: value["data"].__setitem__("items", []),
        )
        _wire_change(
            raw,
            "response/suspend-d/20260707.json",
            lambda value: value["data"]["items"].append(
                ["000001.SZ", "20260707", None, "S"]
            ),
        )

    receipt_bytes, snapshot = _capture(suspended)
    outcome = _observe(receipt_bytes, snapshot)
    assert outcome.failure is None and outcome.report is not None
    assert "20260707" in outcome.report.suspended_provider_dates
    assert "20260707" not in outcome.report.published_provider_dates

    def intraday(raw, _) -> None:
        suspended(raw, _)
        _wire_change(
            raw,
            "response/suspend-d/20260707.json",
            lambda value: value["data"]["items"][0].__setitem__(2, "09:30-10:30"),
        )

    receipt_bytes, snapshot = _capture(intraday)
    _failure(_observe(receipt_bytes, snapshot), "missing_classification")


def test_normalization_publication_purpose_lookahead_and_report_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_normalize = MODULE._normalize_events
    monkeypatch.setattr(MODULE, "_normalize_events", lambda *args: None)
    _failure(_observe(), "normalization_failed")
    monkeypatch.setattr(MODULE, "_normalize_events", original_normalize)

    original_validate = MODULE.validate_market_bundle_v1
    monkeypatch.setattr(
        MODULE,
        "validate_market_bundle_v1",
        lambda **kwargs: type("Outcome", (), {"failure": object(), "manifest": None})(),
    )
    _failure(_observe(), "publication_failed")
    monkeypatch.setattr(MODULE, "validate_market_bundle_v1", original_validate)

    original_requirements = MODULE._requirements
    monkeypatch.setattr(
        MODULE,
        "_requirements",
        lambda snapshot: tuple(reversed(original_requirements(snapshot))),
    )
    _failure(_observe(), "purpose_scope_mismatch")
    monkeypatch.setattr(MODULE, "_requirements", original_requirements)

    monkeypatch.setattr(MODULE, "_lookahead_valid", lambda *args: False)
    _failure(_observe(), "lookahead_violation")
    monkeypatch.undo()

    original_report = MODULE._report
    monkeypatch.setattr(
        MODULE,
        "_report",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("binding")),
    )
    _failure(_observe(), "report_binding_mismatch")
    monkeypatch.setattr(MODULE, "_report", original_report)


def test_existing_2024_normalization_and_publication_golden_files_are_unchanged() -> (
    None
):
    expected = {
        "tests/fixtures/market_data/providers/tushare/cn-a-share-daily-bundle-v1.expected.json": "0ccb4ebeb0f71ce45cb67c98aafd3bebd227eb01e2ccc368002660ff022e78f3",
        "tests/fixtures/market_data/providers/tushare/cn-a-share-daily-listing-v1/daily.json": "c2950a35c093b983e538f97830b7b3fcb0bba1a7dac98a17bd20f6db9296f846",
        "tests/fixtures/market_data/providers/tushare/cn-a-share-daily-listing-v1/stock-basic.json": "d78fc472268deacb5af7c59c113325e2a00c5b4619c53fbbfe6fa23c96d471d2",
    }
    repository = ROOT.parent
    for relative, digest in expected.items():
        assert (
            hashlib.sha256((repository / relative).read_bytes()).hexdigest() == digest
        )


def test_fixture_is_secret_free_and_module_has_no_runtime_kernel_or_io_imports() -> (
    None
):
    fixture_bytes = b"".join(
        path.read_bytes() for path in FIXTURE.rglob("*") if path.is_file()
    )
    lowered = fixture_bytes.lower()
    assert b"tushare_token" not in lowered
    assert b'"token"' not in lowered
    source = Path(cast(str, MODULE.__file__)).read_text(encoding="utf-8")
    assert "crypto_quant_backtest" not in source
    assert "crypto_quant_trading" not in source
    assert "pathlib" not in source
    assert "LocalMarketBundleRepository" not in source
    assert "aggregate_bars_v1" not in source
    assert "synthetic_price_point" not in source
    assert "open(" not in source
