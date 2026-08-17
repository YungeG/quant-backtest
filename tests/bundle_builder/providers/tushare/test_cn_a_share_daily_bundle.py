from __future__ import annotations

import json
from dataclasses import fields
from datetime import date
from importlib import import_module
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import (
    BarBucket,
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    validate_market_bundle_v1,
)
from crypto_quant_domain import (
    InstrumentId,
    SessionId,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_bytes,
)
from crypto_quant_market_data import MarketEvent


ROOT = Path(__file__).parents[3]
DAILY_FIXTURE = (
    ROOT / "fixtures/market_data/providers/tushare/cn-a-share-daily-listing-v1"
)
EVENT_TIME_FIXTURE = (
    ROOT
    / "fixtures/market_data/providers/tushare/cn-a-share-trade-calendar-v1"
    / "daily-event-time.expected.json"
)
EXPECTED_FIXTURE = (
    ROOT
    / "fixtures/market_data/providers/tushare/cn-a-share-daily-bundle-v1.expected.json"
)
EXPECTED = json.loads(EXPECTED_FIXTURE.read_text())
ACQUIRED_AT = 1_786_943_026_685_846_805


def _normalized_result():
    normalizer = import_module(
        "crypto_quant_bundle_builder.tushare_cn_a_share_daily"
    )
    event_time = json.loads(EVENT_TIME_FIXTURE.read_text())
    spans = tuple(
        (
            UtcInstant(value["start"]["epoch_nanoseconds"]),
            UtcInstant(value["end_exclusive"]["epoch_nanoseconds"]),
        )
        for value in event_time["bucket"]["included_spans"]
    )
    bucket = BarBucket(
        SessionId("CN.XSHE", "2024-01-02.regular"),
        TradingDate("CN.XSHE", date(2024, 1, 2)),
        spans,
        spans[0][0],
        spans[-1][1],
    )
    snapshot_outcome = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "response/daily.json",
                (DAILY_FIXTURE / "daily.json").read_bytes(),
                "0644",
                ACQUIRED_AT,
                None,
            ),
            RawSourceMember(
                "response/stock-basic.json",
                (DAILY_FIXTURE / "stock-basic.json").read_bytes(),
                "0644",
                ACQUIRED_AT,
                None,
            ),
        ),
        provenance=SourceSnapshotProvenance(
            "tushare.pro",
            "tushare.pro.daily_listing.000001.sz.20240102",
            "tushare.pro.terms",
            "backtest.acquisition.candidate",
        ),
    )
    assert snapshot_outcome.snapshot is not None
    snapshot = snapshot_outcome.snapshot
    daily_member = next(
        member for member in snapshot.members if member.member_key == "response/daily.json"
    )
    normalized = normalizer.normalize_tushare_cn_a_share_daily_v1(
        snapshot,
        normalizer.TushareCnAShareDailyNormalizationRequest(
            1,
            snapshot.snapshot_id,
            snapshot.provenance_hash,
            "response/daily.json",
            daily_member.content_hash,
            InstrumentId(VenueId("xshe"), "000001"),
            "20240102",
            bucket,
        ),
    )
    assert normalized.failure is None and normalized.result is not None
    return normalized.result


def test_tushare_daily_result_projects_one_purpose_preserving_event_and_publishes(
    tmp_path: Path,
) -> None:
    result = _normalized_result()
    bundle = import_module(
        "crypto_quant_bundle_builder.tushare_cn_a_share_daily_bundle"
    )
    project = getattr(
        bundle, "project_tushare_cn_a_share_daily_market_event_v1", None
    )
    assert callable(project), "G12C/D Tushare RED: missing publication projection"

    event = project(result)

    assert type(event) is MarketEvent
    assert json.loads(canonical_bytes(event)) == EXPECTED["event"]
    assert event.event_hash == EXPECTED["event_hash"]
    assert event.event_id == f"tushare-cn-a-share-daily-v1:{result.normalization_hash}"
    assert (
        event.stream_key
        == "tushare_cn_a_share.daily.publication.xshe.000001.v1"
    )
    assert event.event_type == "tushare_cn_a_share_daily_publication.v1"
    assert event.capability.identity == "tushare_cn_a_share.daily-publications@1"
    assert event.instrument_id == result.raw_bar.instrument_id
    assert event.event_time == result.raw_bar.bucket.interval_start
    assert event.available_time == result.raw_bar.available_time
    assert event.phase.rank == 0 and event.phase.code == "market_data"
    assert event.source_sequence.value == 0
    assert event.revision_id == result.trace.revision_id
    assert event.supersedes_revision_id is None
    assert event.source_key == result.trace.source_key
    assert event.source_hash == result.trace.member_content_hash
    assert set(event.payload) == {
        "normalization_hash",
        "raw_bar",
        "source_trace",
        "execution_reference",
        "valuation",
        "qualification",
    }
    assert event.payload["normalization_hash"] == result.normalization_hash
    assert canonical_bytes(event.payload["raw_bar"]) == canonical_bytes(result.raw_bar)
    assert "price_purpose" not in event.payload["raw_bar"]
    assert event.payload["raw_bar"]["raw_bar_hash"] == result.raw_bar.raw_bar_hash
    assert event.payload["raw_bar"]["decision_grade_eligible"] is False
    assert event.payload["raw_bar"]["deployment_authorized"] is False
    assert canonical_bytes(event.payload["source_trace"]) == canonical_bytes(result.trace)
    assert event.payload["source_trace"]["revision_closure_complete"] is False
    assert canonical_bytes(event.payload["execution_reference"]) == canonical_bytes(
        result.execution_reference
    )
    assert event.payload["execution_reference"]["price_purpose"] == "execution_reference"
    assert canonical_bytes(event.payload["valuation"]) == canonical_bytes(
        result.valuation
    )
    assert event.payload["valuation"]["price_purpose"] == "valuation"
    assert event.payload["qualification"] == {
        "revision_closure_complete": False,
        "historical_listing_status_qualified": False,
        "corporate_actions_qualified": False,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }

    with pytest.raises(TypeError, match="exact Tushare daily normalization result"):
        project(object())
    forged_raw = object.__new__(type(result.raw_bar))
    for field in fields(result.raw_bar):
        object.__setattr__(forged_raw, field.name, getattr(result.raw_bar, field.name))
    object.__setattr__(forged_raw, "source_record_hash", "sha256:" + "f" * 64)
    forged_result = object.__new__(type(result))
    for field in fields(result):
        object.__setattr__(forged_result, field.name, getattr(result, field.name))
    object.__setattr__(forged_result, "raw_bar", forged_raw)
    with pytest.raises(ValueError, match="authority is invalid"):
        project(forged_result)

    validation = validate_market_bundle_v1(
        bundle_key="tushare-cn-a-share-daily-000001-20240102",
        schema_version=1,
        coverage_start=result.raw_bar.bucket.interval_start,
        coverage_end_exclusive=result.raw_bar.bucket.interval_end_exclusive,
        instrument_catalog_hash="sha256:" + "0" * 64,
        events=(event,),
    )
    assert validation.failure is None and validation.manifest is not None
    manifest = validation.manifest
    assert manifest.content_hash == EXPECTED["manifest_content_hash"]
    assert manifest.streams[0].content_hash == EXPECTED["stream_content_hash"]
    repository = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(tmp_path.resolve())
    )
    publication = repository.publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads={event.stream_key: canonical_bytes((event,))},
        retention_policy_ref="retention.g12cd-tushare-cn-a-share-daily-v1",
    )
    assert publication.failure is None and publication.result is not None
    assert publication.result.already_published is False
    assert publication.result.bundle_ref.to_canonical_dict() == EXPECTED["bundle_ref"]
    assert (
        publication.result.retention_proof.proof_hash
        == EXPECTED["retention_proof_hash"]
    )
    replay = repository.publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads={event.stream_key: canonical_bytes((event,))},
        retention_policy_ref="retention.g12cd-tushare-cn-a-share-daily-v1",
    )
    assert replay.failure is None and replay.result is not None
    assert replay.result.already_published is True
    assert replay.result.bundle_ref == publication.result.bundle_ref
    assert replay.result.retention_proof == publication.result.retention_proof
