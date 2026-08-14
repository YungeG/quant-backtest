from __future__ import annotations

from typing import Any

from crypto_quant_domain import (
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    SimulationInstant,
    StrategyDecisionCandidate,
    StrategyDecisionPayload,
    StrategySleeveId,
    UtcInstant,
    VenueId,
)
from crypto_quant_trading import StrategyOutputValidationContext


VENUE = VenueId("binance_usdm")
BTC = InstrumentId(VENUE, "linear_perpetual:btc-usdt")
ETH = InstrumentId(VENUE, "linear_perpetual:eth-usdt")


def catalog() -> InstrumentCatalog:
    btc = CurrencyId("BTC")
    eth = CurrencyId("ETH")
    usdt = CurrencyId("USDT")
    return InstrumentCatalog(
        currencies=(btc, eth, usdt),
        instruments=(
            InstrumentDefinition(
                instrument_id=BTC,
                instrument_type=InstrumentType.LINEAR_PERPETUAL,
                base_currency=btc,
                quote_currency=usdt,
                settlement_currency=usdt,
            ),
            InstrumentDefinition(
                instrument_id=ETH,
                instrument_type=InstrumentType.LINEAR_PERPETUAL,
                base_currency=eth,
                quote_currency=usdt,
                settlement_currency=usdt,
            ),
        ),
        symbol_timelines=(),
    )


def context(
    *,
    universe: tuple[InstrumentId, ...] = (BTC,),
    decision_instant: SimulationInstant | None = None,
) -> StrategyOutputValidationContext:
    return StrategyOutputValidationContext(
        expected_strategy_id="trend-v1",
        expected_sleeve_id=StrategySleeveId("trend.primary"),
        decision_time=UtcInstant(100),
        instrument_catalog=catalog(),
        universe=universe,
        decision_instant=decision_instant,
    )


def valid_payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "strategy_id": "trend-v1",
        "sleeve_id": "trend.primary",
        "decision_time": 100,
        "observed_through": 90,
        "effective_time": 110,
        "expires_at": 200,
        "targets": [
            {
                "instrument_id": {
                    "venue": "binance_usdm",
                    "stable_key": "linear_perpetual:btc-usdt",
                },
                "value": "0.5",
            }
        ],
        "confidence": "0.875",
        "reason": "scheduled rebalance",
        "evidence": {
            "model_revision": "sha256:model-v1",
            "signal_count": 2,
        },
    }


def candidate(payload: dict[str, Any] | None = None) -> StrategyDecisionCandidate:
    return StrategyDecisionCandidate(
        StrategyDecisionPayload(payload if payload is not None else valid_payload())
    )
