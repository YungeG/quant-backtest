from __future__ import annotations

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshot,
    SourceSnapshotProvenance,
    SyntheticJsonlV1Config,
    freeze_source_snapshot,
)
from crypto_quant_domain import InstrumentId, PricePurpose, TimelinePhase, VenueId
from crypto_quant_market_data import MarketBundleCapability


ROOT_LINE = (
    b'{"available_time_epoch_nanoseconds":110,"event_time_epoch_nanoseconds":100,'
    b'"instrument":"BTCUSDT","price_scale":2,"price_units":12345,'
    b'"purpose":"valuation","record_key":"btc-close","revision_id":"v1",'
    b'"schema_version":1,"supersedes_revision_id":null,'
    b'"type":"synthetic_price_point"}'
)
CORRECTION_LINE = (
    b'{"available_time_epoch_nanoseconds":210,"event_time_epoch_nanoseconds":100,'
    b'"instrument":"BTCUSDT","price_scale":2,"price_units":12350,'
    b'"purpose":"valuation","record_key":"btc-close","revision_id":"v2",'
    b'"schema_version":1,"supersedes_revision_id":"v1",'
    b'"type":"synthetic_price_point"}'
)
FUNDING_LINE = (
    b'{"available_time_epoch_nanoseconds":310,"event_time_epoch_nanoseconds":300,'
    b'"instrument":"BTCUSDT","price_scale":4,"price_units":125,'
    b'"purpose":"funding","record_key":"btc-funding","revision_id":"f1",'
    b'"schema_version":1,"supersedes_revision_id":null,'
    b'"type":"synthetic_price_point"}'
)
JSONL = b"\n".join((ROOT_LINE, CORRECTION_LINE, FUNDING_LINE)) + b"\n"


def provenance(*, source_key: str = "fixture.source") -> SourceSnapshotProvenance:
    return SourceSnapshotProvenance(
        "fixture.vendor", source_key, "license.fixture", "retention.fixture"
    )


def snapshot(value: bytes = JSONL, *, source_key: str = "fixture.source") -> SourceSnapshot:
    result = freeze_source_snapshot(
        members=(RawSourceMember("prices.jsonl", value, "0644", 400, None),),
        provenance=provenance(source_key=source_key),
    ).snapshot
    assert result is not None
    return result


def config(
    *,
    instruments: tuple[tuple[str, InstrumentId], ...] | None = None,
    purposes: tuple[tuple[str, PricePurpose], ...] | None = None,
) -> SyntheticJsonlV1Config:
    return SyntheticJsonlV1Config(
        member_key="prices.jsonl",
        stream_key="synthetic.prices",
        capability=MarketBundleCapability("price_points", 1),
        phase=TimelinePhase(20, "market_data"),
        instrument_bindings=(
            (("BTCUSDT", InstrumentId(VenueId("test"), "btc-usdt")),)
            if instruments is None
            else instruments
        ),
        price_purpose_bindings=(
            (
                ("funding", PricePurpose.FUNDING),
                ("valuation", PricePurpose.VALUATION),
            )
            if purposes is None
            else purposes
        ),
    )
