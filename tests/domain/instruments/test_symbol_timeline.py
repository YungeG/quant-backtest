from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from crypto_quant_domain import (
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    SymbolInterval,
    SymbolTimeline,
    UtcInstant,
    VenueId,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/domain/instrument-identity-timeline-v1.json"


def build_from_fixture() -> tuple[InstrumentDefinition, SymbolTimeline]:
    fixture = cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))
    instrument = fixture["instrument"]
    instrument_id = InstrumentId(
        venue=VenueId(instrument["venue"]), stable_key=instrument["stable_key"]
    )
    definition = InstrumentDefinition(
        instrument_id=instrument_id,
        instrument_type=InstrumentType(instrument["type"]),
        base_currency=CurrencyId(instrument["base_currency"]),
        quote_currency=CurrencyId(instrument["quote_currency"]),
        settlement_currency=CurrencyId(instrument["settlement_currency"]),
    )
    intervals = tuple(
        SymbolInterval(
            symbol=row["symbol"],
            effective_from=UtcInstant(row["effective_from"]),
            effective_until=(
                UtcInstant(row["effective_until"])
                if row["effective_until"] is not None
                else None
            ),
        )
        for row in fixture["symbols"]
    )
    return definition, SymbolTimeline(instrument_id, intervals)


def test_symbol_rename_does_not_change_instrument_identity() -> None:
    definition, timeline = build_from_fixture()

    assert timeline.symbol_at(UtcInstant(99)) == "BTCUSDT"
    assert timeline.symbol_at(UtcInstant(100)) == "XBTUSDT"
    assert timeline.instrument_id == definition.instrument_id


def test_timeline_rejects_overlap_and_invalid_interval() -> None:
    instrument_id = InstrumentId(VenueId("xshg"), "equity:600000")
    with pytest.raises(ValueError, match="overlap"):
        SymbolTimeline(
            instrument_id,
            (
                SymbolInterval("600000", UtcInstant(0), UtcInstant(100)),
                SymbolInterval("SH600000", UtcInstant(99), None),
            ),
        )
    with pytest.raises(ValueError, match="effective_until"):
        SymbolInterval("600000", UtcInstant(100), UtcInstant(100))


def test_missing_symbol_at_instant_fails_closed() -> None:
    instrument_id = InstrumentId(VenueId("xshg"), "equity:600000")
    timeline = SymbolTimeline(
        instrument_id,
        (SymbolInterval("600000", UtcInstant(100), UtcInstant(200)),),
    )

    with pytest.raises(LookupError, match="symbol"):
        timeline.symbol_at(UtcInstant(99))
    with pytest.raises(LookupError, match="symbol"):
        timeline.symbol_at(UtcInstant(200))


def test_catalog_rejects_timeline_for_unknown_instrument() -> None:
    definition, _ = build_from_fixture()
    unknown_timeline = SymbolTimeline(
        InstrumentId(VenueId("xshg"), "equity:600000"),
        (SymbolInterval("600000", UtcInstant(0), None),),
    )

    with pytest.raises(ValueError, match="unknown InstrumentId"):
        InstrumentCatalog(
            currencies=(CurrencyId("BTC"), CurrencyId("USDT")),
            instruments=(definition,),
            symbol_timelines=(unknown_timeline,),
        )
