from __future__ import annotations

from dataclasses import replace
from datetime import date

from crypto_quant_bundle_builder import (
    BarAggregationFailureCode,
    BarBucket,
    BarBucketPlan,
    BarDefinition,
    aggregate_bars_v1,
    validate_market_bundle_v1,
)
from crypto_quant_domain import (
    InstrumentId,
    PricePurpose,
    Scale,
    SessionId,
    SourceSequence,
    TimelinePhase,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketBundleManifest,
    MarketEvent,
    MarketStreamManifest,
)

CAPABILITY = MarketBundleCapability("synthetic_prices", 1)
SOURCE_PHASE = TimelinePhase(10, "source")
OUTPUT_PHASE = TimelinePhase(20, "bar.close")
CODE_HASH = canonical_sha256("aggregation-code")
CATALOG_HASH = canonical_sha256("catalog")
INSTRUMENT = InstrumentId(VenueId("test"), "asset")
OTHER_INSTRUMENT = InstrumentId(VenueId("test"), "other")


def definition() -> BarDefinition:
    return BarDefinition(
        key="test-bars",
        version=1,
        output_stream_key="bars.explicit",
        aggregation_kind="explicit_bucket_price_ohlc",
        source_stream_key="synthetic.prices",
        source_event_type="synthetic_price_point.v1",
        source_capability=CAPABILITY,
        price_purpose=PricePurpose.VALUATION,
        price_scale=Scale(4),
        volume_semantics="none",
        empty_interval_policy="omit",
        output_phase=OUTPUT_PHASE,
    )


def bucket(start: int, end: int) -> BarBucket:
    return BarBucket(
        session_id=SessionId("test", f"{start}-{end}"),
        trading_date=TradingDate("test", date(2025, 1, 1)),
        included_spans=((UtcInstant(start), UtcInstant(end)),),
        interval_start=UtcInstant(start),
        interval_end_exclusive=UtcInstant(end),
    )


def plan(*buckets: BarBucket, value: BarDefinition | None = None) -> BarBucketPlan:
    selected = definition() if value is None else value
    return BarBucketPlan(
        plan_key="test-plan",
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(1_000),
        bar_definition_key=selected.key,
        bar_definition_version=selected.version,
        bar_definition_hash=selected.definition_hash,
        buckets=buckets,
    )


def event(
    position: int,
    *,
    event_time: int,
    price_units: int,
    record_key: str | None = None,
    available_time: int | None = None,
    purpose: PricePurpose = PricePurpose.VALUATION,
    scale: int = 4,
    instrument_id: InstrumentId | None = INSTRUMENT,
    phase: TimelinePhase = SOURCE_PHASE,
    supersedes_revision_id: str | None = None,
    source_sequence: int | None = None,
) -> MarketEvent:
    return MarketEvent(
        event_id=f"event-{position}",
        stream_key="synthetic.prices",
        event_type="synthetic_price_point.v1",
        capability=CAPABILITY,
        instrument_id=instrument_id,
        event_time=UtcInstant(event_time),
        available_time=UtcInstant(
            event_time if available_time is None else available_time
        ),
        phase=phase,
        source_sequence=SourceSequence(
            position if source_sequence is None else source_sequence
        ),
        revision_id=f"revision-{position}",
        supersedes_revision_id=supersedes_revision_id,
        source_key="fixture",
        source_hash=canonical_sha256(f"source-{position}"),
        payload={
            "synthetic_record_key": record_key or f"record-{position}",
            "price_units": price_units,
            "price_scale": scale,
            "price_purpose": purpose.value,
        },
    )


def manifest(events: tuple[MarketEvent, ...]) -> MarketBundleManifest:
    outcome = validate_market_bundle_v1(
        bundle_key="source",
        schema_version=1,
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(1_000),
        instrument_catalog_hash=CATALOG_HASH,
        events=events,
    )
    assert outcome.failure is None
    assert outcome.manifest is not None
    return outcome.manifest


def aggregate(
    events: tuple[MarketEvent, ...],
    *,
    bucket_plan: BarBucketPlan | None = None,
    source_manifest: MarketBundleManifest | None = None,
    bar_definition: BarDefinition | None = None,
):
    return aggregate_bars_v1(
        source_manifest=manifest(events)
        if source_manifest is None
        else source_manifest,
        source_events=events,
        bucket_plan=plan(bucket(100, 200), bucket(200, 300))
        if bucket_plan is None
        else bucket_plan,
        definition=definition() if bar_definition is None else bar_definition,
        aggregation_code_hash=CODE_HASH,
    )


def test_aggregates_exact_integer_ohlc_and_half_open_boundaries() -> None:
    events = (
        event(0, event_time=100, price_units=100),
        event(1, event_time=150, price_units=300),
        event(2, event_time=175, price_units=50),
        event(3, event_time=199, price_units=200),
        event(4, event_time=200, price_units=700),
    )

    outcome = aggregate(events)

    assert outcome.failure is None
    assert outcome.result is not None
    bars = outcome.result.generated_events
    assert len(bars) == 2
    assert bars[0].event_time == UtcInstant(100)
    assert bars[0].available_time == UtcInstant(200)
    assert bars[0].supersedes_revision_id is None
    assert bars[0].payload["open"] == {"units": 100, "scale": 4}
    assert bars[0].payload["high"] == {"units": 300, "scale": 4}
    assert bars[0].payload["low"] == {"units": 50, "scale": 4}
    assert bars[0].payload["close"] == {"units": 200, "scale": 4}
    assert bars[0].payload["volume"] is None
    assert bars[0].payload["observation_count"] == 4
    assert bars[1].payload["open"] == {"units": 700, "scale": 4}
    assert (
        outcome.result.output_manifest
        == validate_market_bundle_v1(
            bundle_key=outcome.result.output_manifest.bundle_key,
            schema_version=1,
            coverage_start=UtcInstant(0),
            coverage_end_exclusive=UtcInstant(1_000),
            instrument_catalog_hash=CATALOG_HASH,
            events=events + bars,
        ).manifest
    )


def test_public_aggregation_rejects_ambiguous_economic_tie() -> None:
    outcome = aggregate_bars_v1(
        source_manifest=manifest(
            (
                event(0, event_time=110, price_units=100, record_key="one"),
                event(1, event_time=110, price_units=200, record_key="two"),
            )
        ),
        source_events=(
            event(0, event_time=110, price_units=100, record_key="one"),
            event(1, event_time=110, price_units=200, record_key="two"),
        ),
        bucket_plan=plan(bucket(100, 200)),
        definition=definition(),
        aggregation_code_hash=CODE_HASH,
    )

    assert_failure(outcome, BarAggregationFailureCode.SOURCE_EVENT_INVALID)
    assert outcome.failure is not None
    assert outcome.failure.input_position == 1


def test_mixed_scale_or_invalid_price_units_rejected() -> None:
    e0 = event(0, event_time=110, price_units=100)
    invalid_units = replace(e0, payload={**e0.payload, "price_units": -1})
    mixed_scale = event(0, event_time=110, price_units=100, scale=2)

    assert_failure(
        aggregate((invalid_units,)), BarAggregationFailureCode.SOURCE_EVENT_INVALID
    )
    assert_failure(
        aggregate((mixed_scale,)), BarAggregationFailureCode.SOURCE_EVENT_INVALID
    )


def test_root_bar_binds_exact_source_lineage_and_late_availability() -> None:
    source = event(0, event_time=110, available_time=250, price_units=100)

    outcome = aggregate((source,))

    assert outcome.failure is None
    assert outcome.result is not None
    bar = outcome.result.generated_events[0]
    source_hashes = (source.event_hash,)
    selected_source_set_hash = canonical_sha256(source_hashes)
    identity = canonical_sha256(
        {
            "type": "bar_revision_identity",
            "schema_version": 1,
            "aggregation_spec_hash": bar.payload["aggregation_spec_hash"],
            "aggregation_input_hash": bar.payload["aggregation_input_hash"],
            "instrument_id": INSTRUMENT.to_canonical_dict(),
            "bucket_hash": bar.payload["bucket_hash"],
            "selected_source_set_hash": selected_source_set_hash,
        }
    )
    assert bar.available_time == UtcInstant(250)
    assert bar.event_id == "bar-event-v1:" + identity
    assert bar.revision_id == "bar-revision-v1:" + identity
    assert bar.source_hash == bar.payload["aggregation_input_hash"]
    assert bar.payload["source_event_hashes"] == source_hashes
    assert bar.payload["selected_source_set_hash"] == selected_source_set_hash
    assert outcome.result.aggregation_manifest.output_stream_manifest == (
        MarketStreamManifest.from_events("bars.explicit", (bar,))
    )


def test_omits_empty_buckets_and_counts_nonselected_and_out_of_plan() -> None:
    events = (
        event(0, event_time=110, price_units=100),
        event(
            1,
            event_time=120,
            price_units=200,
            purpose=PricePurpose.MARGIN,
            instrument_id=None,
        ),
        event(
            2,
            event_time=900,
            price_units=300,
            instrument_id=OTHER_INSTRUMENT,
        ),
    )

    outcome = aggregate(events)

    assert outcome.result is not None
    report = outcome.result.aggregation_manifest
    assert len(outcome.result.generated_events) == 1
    assert report.selected_source_revision_count == 2
    assert report.assigned_source_revision_count == 1
    assert report.out_of_plan_source_revision_count == 1
    assert report.nonselected_source_event_count == 1
    assert report.candidate_instrument_count == 2
    assert report.planned_bucket_count == 2
    assert report.empty_bucket_instrument_count == 3
    assert report.output_root_count == report.output_revision_count == 1


def assert_failure(outcome: object, code: BarAggregationFailureCode) -> None:
    assert hasattr(outcome, "result") and outcome.result is None  # type: ignore[attr-defined]
    assert outcome.failure is not None  # type: ignore[attr-defined]
    assert outcome.failure.code is code  # type: ignore[attr-defined]
