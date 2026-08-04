from __future__ import annotations

from dataclasses import replace

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    Money,
    Price,
    PricePurpose,
    Quantity,
    RoundingPolicy,
    Scale,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import (
    ApprovedPortfolioTarget,
    InstrumentSizingInput,
    PortfolioRiskEvaluator,
    PositionSizingPolicy,
    QuantityLattice,
    ResidualPositionPolicy,
    ResolvedMark,
)
from tests.kernel.allocation._fixtures import BTC, ETH, USD
from tests.kernel.risk._fixtures import allocated_targets, policy as risk_policy


QUANTITY_SCALE = Scale(3)
PRICE_SCALE = Scale(2)
BATCH_ID = "decision-batch-v1:sha256:" + "1" * 64


def approved_targets() -> ApprovedPortfolioTarget:
    outcome = PortfolioRiskEvaluator().evaluate(
        allocation=allocated_targets(),
        policy=risk_policy(),
    )
    if outcome.approved_target is None:
        raise AssertionError(f"risk fixture failed: {outcome.failure!r}")
    return outcome.approved_target


def sizing_policy(
    *,
    residual: ResidualPositionPolicy = ResidualPositionPolicy.HOLD_DUST,
    rounding: RoundingPolicy = RoundingPolicy.TOWARD_ZERO,
    price_purpose: PricePurpose = PricePurpose.VALUATION,
) -> PositionSizingPolicy:
    return PositionSizingPolicy.create(
        policy_key="position-sizing.toward-zero.v1",
        policy_version=1,
        price_purpose=price_purpose,
        rounding=rounding,
        residual_policy=residual,
    )


def resolved_mark(
    instrument_id: InstrumentId,
    *,
    price_units: int,
    resolved_at: UtcInstant = UtcInstant(100),
    currency: CurrencyId = USD,
    purpose: PricePurpose = PricePurpose.VALUATION,
    revision: str = "v1",
) -> ResolvedMark:
    return ResolvedMark(
        instrument_id=instrument_id,
        quote_currency_id=currency,
        price_purpose=purpose,
        price=Price(price_units, PRICE_SCALE, str(instrument_id), str(currency)),
        observed_at=resolved_at,
        available_at=resolved_at,
        resolved_at=resolved_at,
        age_nanoseconds=0,
        stream_id=f"mark:{instrument_id}:{purpose.value}",
        source_event_id=f"event:{instrument_id}:{resolved_at.epoch_nanoseconds}",
        revision_id=revision,
        stale_policy_key=f"stale.{purpose.value}.v1",
        stale_policy_version=1,
        stale_policy_hash="sha256:" + "a" * 64,
    )


def lattice(
    instrument_id: InstrumentId,
    *,
    buy_lot_units: int | None = 100,
    sell_lot_units: int | None = 100,
    min_quantity_units: int = 100,
    min_notional_units: int = 1_000_000_000_000_000,
    odd_lot_close_permitted: bool = False,
    currency: CurrencyId = USD,
) -> QuantityLattice:
    return QuantityLattice.create(
        instrument_id=instrument_id,
        lattice_key=f"quantity-lattice:{instrument_id}:v1",
        lattice_version=1,
        atomic_scale=QUANTITY_SCALE,
        step_units=1,
        buy_lot_units=buy_lot_units,
        sell_lot_units=sell_lot_units,
        min_quantity_units=min_quantity_units,
        min_notional=Money(min_notional_units, Scale(14), str(currency)),
        odd_lot_close_permitted=odd_lot_close_permitted,
    )


def sizing_inputs(
    *,
    btc_price_units: int = 2_900,
    eth_price_units: int = 2_000,
    reverse: bool = False,
) -> tuple[InstrumentSizingInput, ...]:
    values = (
        InstrumentSizingInput(
            instrument_id=BTC,
            mark=resolved_mark(BTC, price_units=btc_price_units),
            current_quantity=Quantity(0, QUANTITY_SCALE, str(BTC)),
            lattice=lattice(BTC),
        ),
        InstrumentSizingInput(
            instrument_id=ETH,
            mark=resolved_mark(ETH, price_units=eth_price_units),
            current_quantity=Quantity(0, QUANTITY_SCALE, str(ETH)),
            lattice=lattice(ETH),
        ),
    )
    return tuple(reversed(values)) if reverse else values


def expected_policy_hash(value: PositionSizingPolicy) -> str:
    return canonical_sha256(value.config_payload())


def expected_lattice_hash(value: QuantityLattice) -> str:
    return canonical_sha256(value.config_payload())


def zero_approved_target() -> ApprovedPortfolioTarget:
    outcome = PortfolioRiskEvaluator().evaluate(
        allocation=allocated_targets(),
        policy=risk_policy(gross_max=1),
    )
    if outcome.approved_target is None:
        raise AssertionError(f"risk fixture failed: {outcome.failure!r}")
    if any(target.approved_notional.units for target in outcome.approved_target.targets):
        raise AssertionError("zero approved target fixture is not zero")
    return outcome.approved_target


__all__ = [
    "BATCH_ID",
    "BTC",
    "ETH",
    "PRICE_SCALE",
    "QUANTITY_SCALE",
    "approved_targets",
    "expected_lattice_hash",
    "expected_policy_hash",
    "lattice",
    "replace",
    "resolved_mark",
    "sizing_inputs",
    "sizing_policy",
    "zero_approved_target",
]
