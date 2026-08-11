from __future__ import annotations

from crypto_quant_backtest import (
    ObservationPurposeRef,
    ObservationQuery,
    ObservationRecord,
    ObservationView,
)
from crypto_quant_domain import (
    InstrumentId,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
)
from crypto_quant_market_data import MarketBundleCapability, MarketEvent


BARS_V1 = MarketBundleCapability("price_bars", 1)
BARS_V2 = MarketBundleCapability("price_bars", 2)
AVAILABILITY = MarketBundleCapability("market_availability", 1)
INSTRUMENT_A = InstrumentId(VenueId("test"), "asset-a")
INSTRUMENT_B = InstrumentId(VenueId("test"), "asset-b")
OHLCV = ObservationPurposeRef("bar.ohlcv", 1)
EXECUTION_REFERENCE = ObservationPurposeRef("price.execution-reference", 1)


def event(
    event_id: str,
    *,
    dataset_key: str = "bars.1m",
    instrument_id: InstrumentId = INSTRUMENT_A,
    capability: MarketBundleCapability = BARS_V1,
    available_time: int,
    source_sequence: int,
    close_units: int,
) -> MarketEvent:
    return MarketEvent(
        event_id=event_id,
        stream_key=dataset_key,
        event_type="bar",
        capability=capability,
        instrument_id=instrument_id,
        event_time=UtcInstant(available_time - 1),
        available_time=UtcInstant(available_time),
        phase=TimelinePhase(20, "market_data"),
        source_sequence=SourceSequence(source_sequence),
        revision_id="rev-1",
        supersedes_revision_id=None,
        source_key=f"fixture.{dataset_key}",
        source_hash="sha256:" + event_id.encode().hex().ljust(64, "0")[:64],
        payload={"close": {"scale": 2, "units": close_units}},
    )


def query(
    *,
    dataset_key: str = "bars.1m",
    instrument_id: InstrumentId = INSTRUMENT_A,
    purpose: ObservationPurposeRef = OHLCV,
    capability: MarketBundleCapability = BARS_V1,
) -> ObservationQuery:
    return ObservationQuery(
        dataset_key=dataset_key,
        instrument_id=instrument_id,
        purpose=purpose,
        capability=capability,
    )


def record(
    event_id: str,
    *,
    purpose: ObservationPurposeRef = OHLCV,
    dataset_key: str = "bars.1m",
    instrument_id: InstrumentId = INSTRUMENT_A,
    capability: MarketBundleCapability = BARS_V1,
    available_time: int,
    source_sequence: int,
    close_units: int,
) -> ObservationRecord:
    return ObservationRecord(
        purpose=purpose,
        event=event(
            event_id,
            dataset_key=dataset_key,
            instrument_id=instrument_id,
            capability=capability,
            available_time=available_time,
            source_sequence=source_sequence,
            close_units=close_units,
        ),
    )


def view() -> ObservationView:
    allowed = (
        query(),
        query(dataset_key="bars.empty"),
        query(purpose=EXECUTION_REFERENCE),
    )
    records = (
        record("bar-2", available_time=200, source_sequence=2, close_units=10_200),
        record(
            "hidden-instrument",
            instrument_id=INSTRUMENT_B,
            available_time=150,
            source_sequence=4,
            close_units=20_000,
        ),
        record("bar-1", available_time=100, source_sequence=1, close_units=10_100),
        record(
            "hidden-dataset",
            dataset_key="availability",
            capability=AVAILABILITY,
            available_time=120,
            source_sequence=3,
            close_units=0,
        ),
        record(
            "bar-1",
            purpose=EXECUTION_REFERENCE,
            available_time=100,
            source_sequence=1,
            close_units=10_100,
        ),
    )
    return ObservationView(allowed_queries=allowed, records=records)
