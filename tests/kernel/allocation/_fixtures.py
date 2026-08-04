from __future__ import annotations

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    Money,
    PortfolioSnapshot,
    Scale,
    StrategyDecision,
    StrategySleeveId,
    TargetExposureFraction,
    TargetSnapshot,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading import (
    CapitalAllocationPolicyRef,
    LatestSleeveDecisionState,
    StrategyAllocation,
)


USD = CurrencyId("USD")
MONEY_SCALE = Scale(2)
NOTIONAL_SCALE = Scale(14)
VALUATION_TIME = UtcInstant(100)
VENUE = VenueId("synthetic")
BTC = InstrumentId(VENUE, "cash:btc-usd")
ETH = InstrumentId(VENUE, "cash:eth-usd")
TREND = StrategySleeveId("trend.primary")
CARRY = StrategySleeveId("carry.primary")
POLICY = CapitalAllocationPolicyRef(
    policy_key="capital.current-equity-fraction.v1",
    policy_version=1,
    config_hash="sha256:" + "a" * 64,
)


def snapshot(*, equity_units: int = 100_000, timestamp: int = 100) -> PortfolioSnapshot:
    zero = Money(0, MONEY_SCALE, "USD")
    return PortfolioSnapshot(
        account_id="account:primary",
        timestamp=UtcInstant(timestamp),
        reporting_currency=USD,
        cash=(),
        positions=(),
        realized_pnl=zero,
        unrealized_pnl=zero,
        fees=zero,
        financing=zero,
        equity=Money(equity_units, MONEY_SCALE, "USD"),
        valuation_marks=(),
        journal_state_hash="sha256:" + "b" * 64,
        valuation_mark_set_hash=canonical_sha256(()),
        valuation_staleness_report_hash="sha256:" + "c" * 64,
        currency_valuation_graph_hash="sha256:" + "d" * 64,
    )


def decision(
    strategy_id: str,
    sleeve_id: StrategySleeveId,
    units: int,
    *,
    instrument_id: InstrumentId = BTC,
    decision_time: int = 100,
    effective_time: int = 100,
    expires_at: int | None = 200,
) -> StrategyDecision:
    return StrategyDecision(
        strategy_id=strategy_id,
        decision_time=UtcInstant(decision_time),
        observed_through=UtcInstant(decision_time - 1),
        target_snapshot=TargetSnapshot(
            sleeve_id=sleeve_id,
            effective_time=UtcInstant(effective_time),
            expires_at=UtcInstant(expires_at) if expires_at is not None else None,
            targets=(TargetExposureFraction(instrument_id, units),),
        ),
        confidence=None,
        reason="scheduled rebalance",
        evidence={"model_revision": f"{strategy_id}:v1"},
    )


def state(*, reverse: bool = False) -> LatestSleeveDecisionState:
    decisions = (
        decision("trend-v1", TREND, 500_000_000_000),
        decision("carry-v1", CARRY, -750_000_000_000),
    )
    return LatestSleeveDecisionState(
        as_of=VALUATION_TIME,
        decisions=tuple(reversed(decisions)) if reverse else decisions,
    )


def allocations(
    portfolio_snapshot: PortfolioSnapshot,
    *,
    reverse: bool = False,
) -> tuple[StrategyAllocation, ...]:
    source_hash = canonical_sha256(portfolio_snapshot)
    values = (
        StrategyAllocation(
            strategy_id="trend-v1",
            sleeve_id=TREND,
            valuation_time=VALUATION_TIME,
            valuation_currency=USD,
            allocation_nav=Money(60_000, MONEY_SCALE, "USD"),
            policy_ref=POLICY,
            source_portfolio_snapshot_hash=source_hash,
        ),
        StrategyAllocation(
            strategy_id="carry-v1",
            sleeve_id=CARRY,
            valuation_time=VALUATION_TIME,
            valuation_currency=USD,
            allocation_nav=Money(40_000, MONEY_SCALE, "USD"),
            policy_ref=POLICY,
            source_portfolio_snapshot_hash=source_hash,
        ),
    )
    return tuple(reversed(values)) if reverse else values
