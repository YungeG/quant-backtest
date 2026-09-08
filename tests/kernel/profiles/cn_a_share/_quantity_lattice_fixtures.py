from __future__ import annotations

from dataclasses import dataclass

from crypto_quant_domain import (
    CurrencyId,
    ExecutionStyle,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    Money,
    PortfolioSnapshot,
    PositionBalance,
    PositionBalanceKey,
    Price,
    PricePurpose,
    Quantity,
    RoundingPolicy,
    Scale,
    StrategySleeveId,
    TargetExposureFraction,
    TimeInForce,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading import (
    ApprovedInstrumentTarget,
    ApprovedPortfolioTarget,
    AvailabilityState,
    CapitalAllocationPolicyRef,
    InstrumentSizingInput,
    NetInstrumentTarget,
    NormalizedPortfolioTarget,
    PortfolioAllocation,
    PortfolioRiskAction,
    PortfolioRiskDecision,
    PortfolioRiskReasonCode,
    PortfolioRiskScope,
    PositionSizer,
    PositionSizingOutcome,
    PositionSizingPolicy,
    RebalanceCoordinator,
    RebalanceOutcome,
    RebalancePolicy,
    ReservationCommitment,
    ResidualPositionPolicy,
    ResolvedMark,
    ResourceReservationState,
    SleeveTargetNotional,
    StrategyAllocation,
    TargetValidity,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashQuantityLatticeModel,
    CnAShareQuantityLatticeQuery,
    CnAShareQuantityLatticeResolution,
)
from tests.kernel.risk._fixtures import allocated_targets
from tests.kernel.sizing._fixtures import approved_targets


CNY = CurrencyId("CNY")
ACCOUNT = "account:cn-a-primary"
MONEY_SCALE = Scale(2)
PRICE_SCALE = Scale(2)
QUANTITY_SCALE = Scale(0)
BATCH_ID = "decision-batch-v1:sha256:" + "8" * 64


@dataclass(frozen=True, slots=True)
class QuantitySizingCase:
    model: CnAShareCashQuantityLatticeModel
    instrument: InstrumentDefinition
    resolution: CnAShareQuantityLatticeResolution
    approved_target: ApprovedPortfolioTarget
    sizing_input: InstrumentSizingInput
    policy: PositionSizingPolicy
    outcome: PositionSizingOutcome


def _instrument(venue: str, stable_key: str | None = None) -> InstrumentDefinition:
    venue_id = VenueId(venue)
    return InstrumentDefinition(
        instrument_id=InstrumentId(
            venue_id,
            stable_key or ("600000" if venue == "xshg" else "000001"),
        ),
        instrument_type=InstrumentType.EQUITY,
        base_currency=None,
        quote_currency=CNY,
        settlement_currency=CNY,
    )


def _allocation(
    instrument: InstrumentDefinition,
    target_notional: Money,
) -> PortfolioAllocation:
    source = allocated_targets()
    policy_ref: CapitalAllocationPolicyRef = source.policy_ref
    allocation_nav = Money(
        abs(target_notional.units) or 1,
        target_notional.scale,
        "CNY",
    )
    fraction = TargetExposureFraction(
        instrument.instrument_id,
        0 if target_notional.units == 0 else (1 if target_notional.units > 0 else -1) * 10**12,
        Scale(12),
    )
    strategy = StrategyAllocation(
        strategy_id="g08c-fixture",
        sleeve_id=StrategySleeveId("g08c.primary"),
        valuation_time=UtcInstant(100),
        valuation_currency=CNY,
        allocation_nav=allocation_nav,
        policy_ref=policy_ref,
        source_portfolio_snapshot_hash="sha256:" + "1" * 64,
    )
    sleeve = SleeveTargetNotional(
        strategy_id=strategy.strategy_id,
        sleeve_id=strategy.sleeve_id,
        instrument_id=instrument.instrument_id,
        target_fraction=fraction,
        allocation_nav=allocation_nav,
        target_notional=target_notional,
    )
    net = NetInstrumentTarget(
        instrument_id=instrument.instrument_id,
        valuation_currency=CNY,
        target_notional=target_notional,
        sleeve_attributions=(sleeve,),
    )
    payload = {
        "type": "portfolio_allocation_identity",
        "schema_version": 1,
        "valuation_time": strategy.valuation_time,
        "valuation_currency": CNY,
        "target_notional_scale": target_notional.scale.places,
        "policy_ref": policy_ref,
        "source_sleeve_state_hash": "sha256:" + "2" * 64,
        "source_portfolio_snapshot_hash": strategy.source_portfolio_snapshot_hash,
        "allocations": (strategy,),
        "sleeve_targets": (sleeve,),
        "net_targets": (net,),
    }
    return PortfolioAllocation(
        allocation_id=f"portfolio-allocation-v1:{canonical_sha256(payload)}",
        valuation_time=strategy.valuation_time,
        valuation_currency=CNY,
        target_notional_scale=target_notional.scale,
        policy_ref=policy_ref,
        source_sleeve_state_hash="sha256:" + "2" * 64,
        source_portfolio_snapshot_hash=strategy.source_portfolio_snapshot_hash,
        allocations=(strategy,),
        total_allocation_nav=allocation_nav,
        sleeve_targets=(sleeve,),
        net_targets=(net,),
    )


def _approved_target(
    instrument: InstrumentDefinition,
    raw_units: int,
    price_units: int,
) -> ApprovedPortfolioTarget:
    target_notional = Money(
        raw_units * price_units * 10 ** (MONEY_SCALE.places - PRICE_SCALE.places),
        MONEY_SCALE,
        "CNY",
    )
    allocation = _allocation(instrument, target_notional)
    risk_ref = approved_targets().policy_ref
    approved = ApprovedInstrumentTarget(allocation.net_targets[0], target_notional)
    gross = Money(abs(target_notional.units), MONEY_SCALE, "CNY")
    limit = Money(abs(target_notional.units) + 1, MONEY_SCALE, "CNY")
    decisions = (
        PortfolioRiskDecision(
            PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL,
            PortfolioRiskAction.APPROVE,
            PortfolioRiskReasonCode.WITHIN_LIMIT,
            "g08c.target",
            risk_ref,
            target_notional,
            target_notional,
            limit,
            instrument.instrument_id,
        ),
        PortfolioRiskDecision(
            PortfolioRiskScope.GROSS_EXPOSURE,
            PortfolioRiskAction.APPROVE,
            PortfolioRiskReasonCode.WITHIN_LIMIT,
            "g08c.gross",
            risk_ref,
            gross,
            gross,
            limit,
            None,
        ),
        PortfolioRiskDecision(
            PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE,
            PortfolioRiskAction.APPROVE,
            PortfolioRiskReasonCode.WITHIN_LIMIT,
            "g08c.net",
            risk_ref,
            target_notional,
            target_notional,
            limit,
            None,
        ),
    )
    return ApprovedPortfolioTarget.create(
        approved_at=UtcInstant(100),
        source_allocation=allocation,
        policy_ref=risk_ref,
        targets=(approved,),
        decisions=decisions,
    )


def _mark(instrument: InstrumentDefinition, price_units: int) -> ResolvedMark:
    instant = UtcInstant(100)
    return ResolvedMark(
        instrument_id=instrument.instrument_id,
        quote_currency_id=CNY,
        price_purpose=PricePurpose.VALUATION,
        price=Price(
            price_units,
            PRICE_SCALE,
            str(instrument.instrument_id),
            "CNY",
        ),
        observed_at=instant,
        available_at=instant,
        resolved_at=instant,
        age_nanoseconds=0,
        stream_id=f"mark:{instrument.instrument_id}:valuation",
        source_event_id=f"event:{instrument.instrument_id}:100",
        revision_id="g08c-v1",
        stale_policy_key="stale.valuation.v1",
        stale_policy_version=1,
        stale_policy_hash="sha256:" + "3" * 64,
    )


def quantity_sizing_case(
    *,
    venue: str = "xshg",
    current_units: int,
    raw_units: int,
    residual_policy: ResidualPositionPolicy = ResidualPositionPolicy.CLOSE_IF_PERMITTED,
    stable_key: str | None = None,
) -> QuantitySizingCase:
    instrument = _instrument(venue, stable_key)
    model = CnAShareCashQuantityLatticeModel(VenueId(venue), Scale(2))
    resolved = model.resolve_instrument(CnAShareQuantityLatticeQuery(instrument))
    assert resolved.result is not None
    resolution = resolved.result
    price_units = 1_000 if venue == "xshg" else 2_000
    approved = _approved_target(instrument, raw_units, price_units)
    sizing_input = InstrumentSizingInput(
        instrument_id=instrument.instrument_id,
        mark=_mark(instrument, price_units),
        current_quantity=Quantity(
            current_units,
            QUANTITY_SCALE,
            str(instrument.instrument_id),
        ),
        lattice=resolution.quantity_lattice,
    )
    policy = PositionSizingPolicy.create(
        policy_key="equity.cn_a_share.cash.position-sizing.v1",
        policy_version=1,
        price_purpose=PricePurpose.VALUATION,
        rounding=RoundingPolicy.TOWARD_ZERO,
        residual_policy=residual_policy,
    )
    outcome = PositionSizer().materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=policy,
        inputs=(sizing_input,),
    )
    return QuantitySizingCase(
        model=model,
        instrument=instrument,
        resolution=resolution,
        approved_target=approved,
        sizing_input=sizing_input,
        policy=policy,
        outcome=outcome,
    )


def _snapshot(case: QuantitySizingCase, current_units: int) -> PortfolioSnapshot:
    zero = Money(0, Scale(2), "CNY")
    positions = (
        (
            PositionBalance(
                PositionBalanceKey(
                    ACCOUNT,
                    case.model.venue_id,
                    case.instrument.instrument_id,
                ),
                Quantity(
                    current_units,
                    QUANTITY_SCALE,
                    str(case.instrument.instrument_id),
                ),
                (),
            ),
        )
        if current_units
        else ()
    )
    return PortfolioSnapshot(
        account_id=ACCOUNT,
        timestamp=UtcInstant(200),
        reporting_currency=CNY,
        cash=(),
        positions=positions,
        realized_pnl=zero,
        unrealized_pnl=zero,
        fees=zero,
        financing=zero,
        equity=Money(1_000_000, Scale(2), "CNY"),
        valuation_marks=(),
        journal_state_hash="sha256:" + "4" * 64,
        valuation_mark_set_hash=canonical_sha256(()),
        valuation_staleness_report_hash="sha256:" + "5" * 64,
        currency_valuation_graph_hash="sha256:" + "6" * 64,
    )


def coordinate_quantity_case(
    case: QuantitySizingCase,
    *,
    current_units: int | None = None,
) -> RebalanceOutcome:
    assert case.outcome.normalized_target is not None
    target: NormalizedPortfolioTarget = case.outcome.normalized_target
    current = (
        case.sizing_input.current_quantity.units
        if current_units is None
        else current_units
    )
    snapshot = _snapshot(case, current)
    reservations = ResourceReservationState(
        account_id=ACCOUNT,
        cursors=(),
        active_reservations=(),
        totals=ReservationCommitment(),
    )
    availability = AvailabilityState(
        account_id=ACCOUNT,
        ledger_state_hash=snapshot.journal_state_hash,
        settlement_state_hash="sha256:" + "7" * 64,
        reservation_state_hash=reservations.state_hash,
        market_settlement_rules_hash="sha256:" + "8" * 64,
        cash=(),
        positions=(),
    )
    policy = RebalancePolicy.create(
        policy_key="equity.cn_a_share.cash.rebalance.v1",
        policy_version=1,
        execution_style=ExecutionStyle.MARKET,
        time_in_force=TimeInForce.DAY,
        urgency="normal",
        plan_valid_for_nanoseconds=50,
    )
    return RebalanceCoordinator().coordinate(
        target=target,
        target_validity=TargetValidity(
            normalized_target_id=target.normalized_target_id,
            normalized_target_hash=target.normalized_target_hash,
            valid_from=target.materialized_at,
            valid_until=UtcInstant(300),
        ),
        portfolio_snapshot=snapshot,
        working_orders=(),
        reservations=reservations,
        availability=availability,
        policy=policy,
        as_of=UtcInstant(200),
    )
