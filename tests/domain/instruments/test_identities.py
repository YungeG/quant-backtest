from __future__ import annotations

import pytest

from crypto_quant_domain import (
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    VenueId,
)


def perpetual_definition() -> InstrumentDefinition:
    return InstrumentDefinition(
        instrument_id=InstrumentId(
            venue=VenueId("binance_usdm"),
            stable_key="linear_perpetual:btc-usdt",
        ),
        instrument_type=InstrumentType.LINEAR_PERPETUAL,
        base_currency=CurrencyId("BTC"),
        quote_currency=CurrencyId("USDT"),
        settlement_currency=CurrencyId("USDT"),
    )


def test_identity_values_are_canonical_and_symbol_independent() -> None:
    definition = perpetual_definition()

    assert definition.instrument_id.to_canonical_dict() == {
        "type": "instrument_id",
        "venue": "binance_usdm",
        "stable_key": "linear_perpetual:btc-usdt",
    }
    assert definition.to_canonical_dict()["instrument_id"] == (
        definition.instrument_id.to_canonical_dict()
    )


def test_identity_formats_fail_closed() -> None:
    with pytest.raises(ValueError, match="CurrencyId"):
        CurrencyId("usd")
    with pytest.raises(ValueError, match="VenueId"):
        VenueId("BINANCE")
    with pytest.raises(ValueError, match="stable_key"):
        InstrumentId(VenueId("xshg"), "bad key")


def test_catalog_rejects_unknown_currency_reference() -> None:
    definition = perpetual_definition()

    with pytest.raises(ValueError, match="unknown CurrencyId"):
        InstrumentCatalog(
            currencies=(CurrencyId("USDT"),),
            instruments=(definition,),
            symbol_timelines=(),
        )


def test_catalog_rejects_duplicate_instrument_definition() -> None:
    definition = perpetual_definition()

    with pytest.raises(ValueError, match="duplicate InstrumentId"):
        InstrumentCatalog(
            currencies=(CurrencyId("BTC"), CurrencyId("USDT")),
            instruments=(definition, definition),
            symbol_timelines=(),
        )


def test_instrument_definition_is_immutable() -> None:
    definition = perpetual_definition()

    with pytest.raises((AttributeError, TypeError)):
        definition.quote_currency = CurrencyId("USD")  # type: ignore[misc]
