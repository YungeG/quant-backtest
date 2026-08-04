from __future__ import annotations

from crypto_quant_domain import (
    InstrumentId,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
)
from crypto_quant_market_data import (
    InMemoryMarketBundleReader,
    MarketBundleCapability,
    MarketEvent,
)


BARS = MarketBundleCapability("price_bars", 1)
UNIVERSE = MarketBundleCapability("universe", 1)
CORPORATE_ACTIONS = MarketBundleCapability("corporate_actions", 1)
INSTRUMENT = InstrumentId(VenueId("test"), "asset-1")


def event(
    event_id: str,
    *,
    stream_key: str,
    capability: MarketBundleCapability,
    available_time: int,
    phase_rank: int,
    phase_code: str,
    source_sequence: int,
) -> MarketEvent:
    return MarketEvent(
        event_id=event_id,
        stream_key=stream_key,
        event_type=capability.key,
        capability=capability,
        instrument_id=INSTRUMENT,
        event_time=UtcInstant(available_time - 1),
        available_time=UtcInstant(available_time),
        phase=TimelinePhase(phase_rank, phase_code),
        source_sequence=SourceSequence(source_sequence),
        revision_id="rev-1",
        supersedes_revision_id=None,
        source_key=f"fixture.{stream_key}",
        source_hash="sha256:" + event_id.encode().hex().ljust(64, "0")[:64],
        payload={"event": event_id},
    )


def timeline_reader() -> InMemoryMarketBundleReader:
    return InMemoryMarketBundleReader.build(
        bundle_key="fixture.timeline.v1",
        schema_version=1,
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(1_000),
        instrument_catalog_hash="sha256:" + "ab" * 32,
        capabilities=(BARS, UNIVERSE, CORPORATE_ACTIONS),
        streams={
            "bars": (
                event(
                    "bar-before-window",
                    stream_key="bars",
                    capability=BARS,
                    available_time=50,
                    phase_rank=20,
                    phase_code="market_data",
                    source_sequence=1,
                ),
                event(
                    "bar-warmup",
                    stream_key="bars",
                    capability=BARS,
                    available_time=120,
                    phase_rank=20,
                    phase_code="market_data",
                    source_sequence=4,
                ),
                event(
                    "bar-active",
                    stream_key="bars",
                    capability=BARS,
                    available_time=200,
                    phase_rank=20,
                    phase_code="market_data",
                    source_sequence=7,
                ),
                event(
                    "bar-end-exclusive",
                    stream_key="bars",
                    capability=BARS,
                    available_time=500,
                    phase_rank=20,
                    phase_code="market_data",
                    source_sequence=10,
                ),
            ),
            "universe": (
                event(
                    "universe-warmup",
                    stream_key="universe",
                    capability=UNIVERSE,
                    available_time=120,
                    phase_rank=10,
                    phase_code="reference",
                    source_sequence=3,
                ),
                event(
                    "universe-active",
                    stream_key="universe",
                    capability=UNIVERSE,
                    available_time=200,
                    phase_rank=20,
                    phase_code="market_data",
                    source_sequence=6,
                ),
                event(
                    "universe-after-window",
                    stream_key="universe",
                    capability=UNIVERSE,
                    available_time=600,
                    phase_rank=10,
                    phase_code="reference",
                    source_sequence=11,
                ),
            ),
            "corporate_actions": (
                event(
                    "corporate-action-active",
                    stream_key="corporate_actions",
                    capability=CORPORATE_ACTIONS,
                    available_time=200,
                    phase_rank=5,
                    phase_code="corporate_action",
                    source_sequence=5,
                ),
            ),
        },
    )
