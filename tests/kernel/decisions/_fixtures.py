from __future__ import annotations

from crypto_quant_domain import (
    InstrumentId,
    StrategyDecision,
    StrategySleeveId,
    TargetExposureFraction,
    TargetSnapshot,
    UtcInstant,
    VenueId,
)
from crypto_quant_trading import (
    DecisionBatchExpectation,
    DecisionBatchSubmission,
    StrategyValidationResult,
)


VENUE = VenueId("binance_usdm")
BTC = InstrumentId(VENUE, "linear_perpetual:btc-usdt")
ETH = InstrumentId(VENUE, "linear_perpetual:eth-usdt")
TREND = DecisionBatchExpectation("trend-v1", StrategySleeveId("trend.primary"))
CARRY = DecisionBatchExpectation("carry-v1", StrategySleeveId("carry.primary"))


def decision(
    expectation: DecisionBatchExpectation,
    *,
    decision_time: int = 100,
    instrument_id: InstrumentId = BTC,
    units: int = 500_000_000_000,
) -> StrategyDecision:
    instant = UtcInstant(decision_time)
    return StrategyDecision(
        strategy_id=expectation.strategy_id,
        decision_time=instant,
        observed_through=UtcInstant(decision_time - 1),
        target_snapshot=TargetSnapshot(
            sleeve_id=expectation.sleeve_id,
            effective_time=instant,
            expires_at=UtcInstant(decision_time + 100),
            targets=(TargetExposureFraction(instrument_id, units),),
        ),
        confidence=None,
        reason="scheduled rebalance",
        evidence={"model_revision": "sha256:model-v1"},
    )


def submission(
    expectation: DecisionBatchExpectation,
    *,
    decision_time: int = 100,
    instrument_id: InstrumentId = BTC,
    units: int = 500_000_000_000,
) -> DecisionBatchSubmission:
    return DecisionBatchSubmission(
        expectation=expectation,
        result=StrategyValidationResult.valid(
            decision(
                expectation,
                decision_time=decision_time,
                instrument_id=instrument_id,
                units=units,
            )
        ),
    )
