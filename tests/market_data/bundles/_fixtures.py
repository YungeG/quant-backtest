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


PRICE_BARS = MarketBundleCapability(key="price_bars", version=1)
AVAILABILITY = MarketBundleCapability(key="market_availability", version=1)
INSTRUMENT = InstrumentId(venue=VenueId("test"), stable_key="BTC-USD")
PHASE = TimelinePhase(rank=20, code="market_data")


def event(
    event_id: str,
    *,
    stream_key: str = "bars.1m",
    event_type: str = "bar",
    capability: MarketBundleCapability = PRICE_BARS,
    event_time: int,
    available_time: int | None = None,
    source_sequence: int,
    price_units: int,
    revision_id: str = "rev-1",
) -> MarketEvent:
    return MarketEvent(
        event_id=event_id,
        stream_key=stream_key,
        event_type=event_type,
        capability=capability,
        instrument_id=INSTRUMENT,
        event_time=UtcInstant(event_time),
        available_time=UtcInstant(
            event_time if available_time is None else available_time
        ),
        phase=PHASE,
        source_sequence=SourceSequence(source_sequence),
        revision_id=revision_id,
        supersedes_revision_id=None,
        source_key="fixture.vendor.bars",
        source_hash="sha256:" + "a" * 64,
        payload={"open": {"units": price_units, "scale": 2}},
    )


def reader() -> InMemoryMarketBundleReader:
    events = (
        event("evt-3", event_time=300, source_sequence=3, price_units=10_300),
        event("evt-1", event_time=100, source_sequence=1, price_units=10_100),
        event("evt-2", event_time=200, source_sequence=2, price_units=10_200),
    )
    return InMemoryMarketBundleReader.build(
        bundle_key="fixture.market.v1",
        schema_version=1,
        coverage_start=UtcInstant(100),
        coverage_end_exclusive=UtcInstant(400),
        instrument_catalog_hash="sha256:" + "b" * 64,
        capabilities=(PRICE_BARS, AVAILABILITY),
        streams={"bars.1m": events},
    )
