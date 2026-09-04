from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import SourceSequence, UtcInstant, canonical_sha256
from crypto_quant_market_data import (
    EventCursor,
    InMemoryMarketBundleReader,
    InputValidationFailure,
    InputValidationIssueCode,
    MarketBundleCapability,
    MarketBundleIntegrityError,
    MarketBundleManifest,
    MarketBundleReader,
    MarketBundleRef,
    MarketBundleStreamError,
    MarketEvent,
)
from tests.market_data.bundles._fixtures import (
    AVAILABILITY,
    PHASE,
    PRICE_BARS,
    event,
    reader,
)


def collect(
    bundle: InMemoryMarketBundleReader, cursor: EventCursor
) -> tuple[MarketEvent, ...]:
    events: list[MarketEvent] = []
    while not cursor.exhausted:
        batch, cursor = bundle.read_batch(cursor)
        events.extend(batch)
    return tuple(events)


def test_reader_is_content_addressed_and_batch_size_independent() -> None:
    bundle = reader()

    assert isinstance(bundle, MarketBundleReader)
    assert bundle.bundle_ref.manifest_hash == canonical_sha256(bundle.manifest)
    expected_ids = ("evt-1", "evt-2", "evt-3")

    for batch_size in (1, 2, 10):
        cursor = bundle.open_cursor("bars.1m", batch_size=batch_size)
        assert isinstance(cursor, EventCursor)
        assert not hasattr(cursor, "events")
        assert tuple(item.event_id for item in collect(bundle, cursor)) == expected_ids
        assert cursor.position == 0


def test_market_event_freezes_canonical_payload_and_enforces_causality() -> None:
    nested: list[object] = [1, {"value": "ok"}]
    payload: dict[str, object] = {"label": " raw observation ", "nested": nested}
    market_event = event(
        "evt-frozen", event_time=100, source_sequence=1, price_units=1
    )
    custom_event = replace(market_event, payload=payload)
    nested.append(2)

    expected_payload = {
        "label": " raw observation ",
        "nested": (1, {"value": "ok"}),
    }
    assert custom_event.to_canonical_dict()["payload"] == expected_payload
    with pytest.raises(MarketBundleIntegrityError, match="available_time"):
        replace(
            market_event,
            event_time=UtcInstant(200),
            available_time=UtcInstant(100),
        )
    with pytest.raises(MarketBundleIntegrityError, match="canonical"):
        replace(market_event, payload={"price": 1.5})


def test_missing_capability_and_unknown_stream_are_structured_input_failures() -> None:
    bundle = reader()
    missing = MarketBundleCapability(key="funding_publications", version=1)

    failure = bundle.validate_requirements(
        required_capabilities=(PRICE_BARS, missing),
        required_streams=("bars.1m", "funding"),
    )
    assert isinstance(failure, InputValidationFailure)
    expected_codes = (
        InputValidationIssueCode.MISSING_REQUIRED_CAPABILITY,
        InputValidationIssueCode.UNKNOWN_STREAM,
    )
    assert tuple(issue.code for issue in failure.issues) == expected_codes
    unknown = bundle.open_cursor("funding", batch_size=1)
    assert isinstance(unknown, InputValidationFailure)
    assert unknown.issues[0].code is InputValidationIssueCode.UNKNOWN_STREAM


def test_reader_rejects_reference_stream_hash_and_ordering_conflicts() -> None:
    bundle = reader()
    wrong_ref = MarketBundleRef(
        bundle_key=bundle.bundle_ref.bundle_key,
        manifest_hash="sha256:" + "f" * 64,
    )
    with pytest.raises(MarketBundleIntegrityError, match="manifest hash"):
        InMemoryMarketBundleReader(
            bundle_ref=wrong_ref,
            manifest=bundle.manifest,
            streams=bundle.streams,
        )

    stream = bundle.manifest.streams[0]
    bad_manifest = MarketBundleManifest.build(
        bundle_key=bundle.manifest.bundle_key,
        schema_version=bundle.manifest.schema_version,
        coverage_start=bundle.manifest.coverage_start,
        coverage_end_exclusive=bundle.manifest.coverage_end_exclusive,
        instrument_catalog_hash=bundle.manifest.instrument_catalog_hash,
        capabilities=bundle.manifest.capabilities,
        streams=(replace(stream, content_hash="sha256:" + "e" * 64),),
    )
    bad_ref = MarketBundleRef.from_manifest(bad_manifest)
    with pytest.raises(MarketBundleIntegrityError, match="stream content hash"):
        InMemoryMarketBundleReader(
            bundle_ref=bad_ref,
            manifest=bad_manifest,
            streams=bundle.streams,
        )

    duplicate_key = event(
        "evt-other",
        event_time=100,
        source_sequence=1,
        price_units=10_999,
    )
    with pytest.raises(MarketBundleIntegrityError, match="ordering key"):
        InMemoryMarketBundleReader.build(
            bundle_key="fixture.duplicate.v1",
            schema_version=1,
            coverage_start=UtcInstant(100),
            coverage_end_exclusive=UtcInstant(400),
            instrument_catalog_hash="sha256:" + "b" * 64,
            capabilities=(PRICE_BARS, AVAILABILITY),
            streams={
                "bars.1m": (
                    event(
                        "evt-original",
                        event_time=100,
                        source_sequence=1,
                        price_units=10_100,
                    ),
                    duplicate_key,
                )
            },
        )


def test_cursor_rejects_invalid_position_batch_and_cross_bundle_resume() -> None:
    bundle = reader()
    cursor = bundle.open_cursor("bars.1m", batch_size=1)
    assert isinstance(cursor, EventCursor)
    _, advanced = bundle.read_batch(cursor)

    with pytest.raises(MarketBundleStreamError, match="batch_size"):
        bundle.open_cursor("bars.1m", batch_size=0)
    with pytest.raises(MarketBundleStreamError, match="position"):
        replace(cursor, position=99)

    other = InMemoryMarketBundleReader.build(
        bundle_key="fixture.other.v1",
        schema_version=1,
        coverage_start=UtcInstant(100),
        coverage_end_exclusive=UtcInstant(400),
        instrument_catalog_hash="sha256:" + "b" * 64,
        capabilities=(PRICE_BARS,),
        streams={
            "bars.1m": (
                event("other-1", event_time=100, source_sequence=1, price_units=1),
            )
        },
    )
    with pytest.raises(MarketBundleStreamError, match="bundle"):
        other.resume_cursor(advanced)


def test_event_order_uses_available_time_phase_and_source_sequence() -> None:
    delayed = event(
        "delayed",
        event_time=50,
        available_time=300,
        source_sequence=1,
        price_units=1,
    )
    immediate = event(
        "immediate",
        event_time=200,
        available_time=200,
        source_sequence=2,
        price_units=2,
    )
    later_sequence = replace(
        immediate,
        event_id="later-sequence",
        source_sequence=SourceSequence(3),
    )

    ordered = sorted((delayed, later_sequence, immediate), key=lambda item: item.ordering_key)
    expected_order = ("immediate", "later-sequence", "delayed")
    assert tuple(item.event_id for item in ordered) == expected_order
    assert immediate.timeline_instant.instant == immediate.available_time
    assert immediate.timeline_instant.phase == PHASE
