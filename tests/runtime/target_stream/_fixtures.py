from __future__ import annotations

from typing import Any

from crypto_quant_backtest import TimelineEvent, TimelineSegment
from crypto_quant_domain import (
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    SourceSequence,
    StrategySleeveId,
    TimelinePhase,
    UtcInstant,
    VenueId,
)
from crypto_quant_market_data import MarketEvent
from crypto_quant_trading import (
    DecisionBatchExpectation,
    LatestSleeveDecisionState,
    StrategyOutputValidationContext,
)


DECISION_TIME = UtcInstant(100)
VENUE = VenueId("binance_usdm")
BTC = InstrumentId(VENUE, "linear_perpetual:btc-usdt")
ETH = InstrumentId(VENUE, "linear_perpetual:eth-usdt")
TREND = DecisionBatchExpectation("trend-v1", StrategySleeveId("trend.primary"))
CARRY = DecisionBatchExpectation("carry-v1", StrategySleeveId("carry.primary"))


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
    expectation: DecisionBatchExpectation,
) -> StrategyOutputValidationContext:
    return StrategyOutputValidationContext(
        expected_strategy_id=expectation.strategy_id,
        expected_sleeve_id=expectation.sleeve_id,
        decision_time=DECISION_TIME,
        instrument_catalog=catalog(),
        universe=(BTC, ETH),
    )


def candidate_payload(
    expectation: DecisionBatchExpectation,
    *,
    instrument_id: InstrumentId,
    value: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "strategy_id": expectation.strategy_id,
        "sleeve_id": expectation.sleeve_id.value,
        "decision_time": DECISION_TIME.epoch_nanoseconds,
        "observed_through": 90,
        "effective_time": DECISION_TIME.epoch_nanoseconds,
        "expires_at": 200,
        "targets": [
            {
                "instrument_id": {
                    "venue": instrument_id.venue.value,
                    "stable_key": instrument_id.stable_key,
                },
                "value": value,
            }
        ],
        "confidence": "0.9",
        "reason": "precomputed scheduled rebalance",
        "evidence": {"source_model": "sha256:model-v1"},
    }


def event(
    event_id: str,
    expectation: DecisionBatchExpectation,
    *,
    instrument_id: InstrumentId,
    value: str,
    source_sequence: int,
    payload_override: dict[str, Any] | None = None,
) -> MarketEvent:
    from crypto_quant_backtest import (
        TARGET_STREAM_CAPABILITY,
        TARGET_STREAM_EVENT_TYPE,
    )

    payload = (
        payload_override
        if payload_override is not None
        else {
            "schema_version": 1,
            "candidate": candidate_payload(
                expectation, instrument_id=instrument_id, value=value
            ),
        }
    )
    return MarketEvent(
        event_id=event_id,
        stream_key="targets",
        event_type=TARGET_STREAM_EVENT_TYPE,
        capability=TARGET_STREAM_CAPABILITY,
        instrument_id=None,
        event_time=DECISION_TIME,
        available_time=DECISION_TIME,
        phase=TimelinePhase(30, "strategy_decision"),
        source_sequence=SourceSequence(source_sequence),
        revision_id="rev-1",
        supersedes_revision_id=None,
        source_key="fixture.precomputed-targets",
        source_hash="sha256:" + event_id.encode().hex().ljust(64, "0")[:64],
        payload=payload,
    )


def source_events() -> tuple[MarketEvent, MarketEvent]:
    return (
        event(
            "target-trend",
            TREND,
            instrument_id=BTC,
            value="0.5",
            source_sequence=1,
        ),
        event(
            "target-carry",
            CARRY,
            instrument_id=ETH,
            value="-0.25",
            source_sequence=2,
        ),
    )


def timeline_events(
    *, segment: TimelineSegment = TimelineSegment.ACTIVE_TRADING
) -> tuple[TimelineEvent, TimelineEvent]:
    first, second = source_events()
    return TimelineEvent(segment, first), TimelineEvent(segment, second)


def empty_state() -> LatestSleeveDecisionState:
    return LatestSleeveDecisionState.empty()
