from __future__ import annotations

from crypto_quant_domain import CurrencyId, Money, Scale, canonical_sha256
from crypto_quant_trading import (
    LatestSleeveDecisionState,
    PortfolioAllocation,
    PortfolioAllocator,
    PortfolioRiskAction,
    PortfolioRiskLimit,
    PortfolioRiskPolicy,
    PortfolioRiskScope,
)
from tests.kernel.allocation._fixtures import (
    BTC,
    CARRY,
    ETH,
    MONEY_SCALE,
    NOTIONAL_SCALE,
    TREND,
    USD,
    allocations,
    decision,
    snapshot,
)


def allocated_targets(
    *,
    carry_units: int = -750_000_000_000,
) -> PortfolioAllocation:
    portfolio_snapshot = snapshot()
    sleeve_state = LatestSleeveDecisionState(
        as_of=portfolio_snapshot.timestamp,
        decisions=(
            decision("trend-v1", TREND, 500_000_000_000, instrument_id=BTC),
            decision("carry-v1", CARRY, carry_units, instrument_id=ETH),
        ),
    )
    outcome = PortfolioAllocator().allocate(
        sleeve_state=sleeve_state,
        portfolio_snapshot=portfolio_snapshot,
        allocations=allocations(portfolio_snapshot),
        target_notional_scale=NOTIONAL_SCALE,
    )
    if outcome.allocation is None:
        raise AssertionError(f"allocation fixture failed: {outcome.failure!r}")
    return outcome.allocation


def notional(units: int, *, currency: str = "USD", scale: Scale = NOTIONAL_SCALE) -> Money:
    return Money(units, scale, currency)


def policy(
    *,
    btc_max: int = 40_000_000_000_000_000,
    btc_action: PortfolioRiskAction = PortfolioRiskAction.CLAMP,
    eth_max: int = 40_000_000_000_000_000,
    eth_action: PortfolioRiskAction = PortfolioRiskAction.REJECT,
    gross_max: int = 80_000_000_000_000_000,
    net_max: int = 80_000_000_000_000_000,
    currency: CurrencyId = USD,
    scale: Scale = NOTIONAL_SCALE,
    include_eth: bool = True,
    extra_instrument: bool = False,
    reverse: bool = False,
) -> PortfolioRiskPolicy:
    limits = [
        PortfolioRiskLimit(
            limit_id="target.btc.absolute.v1",
            scope=PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL,
            maximum=notional(btc_max, currency=str(currency), scale=scale),
            breach_action=btc_action,
            instrument_id=BTC,
        ),
        PortfolioRiskLimit(
            limit_id="aggregate.gross.v1",
            scope=PortfolioRiskScope.GROSS_EXPOSURE,
            maximum=notional(gross_max, currency=str(currency), scale=scale),
            breach_action=PortfolioRiskAction.REJECT,
            instrument_id=None,
        ),
        PortfolioRiskLimit(
            limit_id="aggregate.absolute-net.v1",
            scope=PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE,
            maximum=notional(net_max, currency=str(currency), scale=scale),
            breach_action=PortfolioRiskAction.REJECT,
            instrument_id=None,
        ),
    ]
    if include_eth:
        limits.append(
            PortfolioRiskLimit(
                limit_id="target.eth.absolute.v1",
                scope=PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL,
                maximum=notional(eth_max, currency=str(currency), scale=scale),
                breach_action=eth_action,
                instrument_id=ETH,
            )
        )
    if extra_instrument:
        from crypto_quant_domain import InstrumentId, VenueId

        limits.append(
            PortfolioRiskLimit(
                limit_id="target.extra.absolute.v1",
                scope=PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL,
                maximum=notional(1, currency=str(currency), scale=scale),
                breach_action=PortfolioRiskAction.REJECT,
                instrument_id=InstrumentId(VenueId("synthetic"), "cash:extra-usd"),
            )
        )
    if reverse:
        limits.reverse()
    return PortfolioRiskPolicy.create(
        policy_key="portfolio.absolute-notional.v1",
        policy_version=1,
        valuation_currency=currency,
        notional_scale=scale,
        limits=tuple(limits),
    )


def expected_policy_config_hash(policy_value: PortfolioRiskPolicy) -> str:
    return canonical_sha256(policy_value.config_payload())


__all__ = [
    "MONEY_SCALE",
    "NOTIONAL_SCALE",
    "USD",
    "allocated_targets",
    "expected_policy_config_hash",
    "notional",
    "policy",
]
