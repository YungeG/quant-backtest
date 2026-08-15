from __future__ import annotations

from crypto_quant_domain import (
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    FeeAssessment,
    FeeBasisType,
    Fill,
    InstrumentId,
    Money,
    OrderSide,
    PositionBalanceKey,
    Price,
    PricePurpose,
    QuantizationPolicy,
    Quantity,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
)
from crypto_quant_trading import CostBasisMethod, CostBasisPolicy


VENUE = VenueId("synthetic")
ACCOUNT = "account:primary"
USD = CurrencyId("USD")
INSTRUMENT = InstrumentId(VENUE, "cash-asset-1")
CASH_KEY = CashBalanceKey(ACCOUNT, VENUE, USD)
POSITION_KEY = PositionBalanceKey(ACCOUNT, VENUE, INSTRUMENT)
MONEY_SCALE = Scale(2)
QUANTITY_SCALE = Scale(1)
NOTIONAL_POLICY = QuantizationPolicy(
    version="cash-notional.half-even.v1",
    target_scale=MONEY_SCALE,
    rounding=RoundingPolicy.HALF_EVEN,
)
COST_BASIS_POLICY = CostBasisPolicy(
    policy_key="cash-cost-basis.fifo.v1",
    policy_version=1,
    method=CostBasisMethod.FIFO,
    fee_allocation_rounding=RoundingPolicy.HALF_EVEN,
)

COST_BASIS_POLICY_V2 = CostBasisPolicy(
    policy_key="cash-cost-basis.fifo.v2",
    policy_version=2,
    method=CostBasisMethod.FIFO,
    fee_allocation_rounding=RoundingPolicy.HALF_EVEN,
)


def domain_id(kind: DomainIdKind, digit: str) -> DomainId:
    return DomainId(kind, f"{kind.prefix}_{digit * 64}")


def recorded_at(nanoseconds: int, sequence: int = 1) -> SimulationInstant:
    return SimulationInstant(
        UtcInstant(nanoseconds),
        TimelinePhase(50, "accounting"),
        SourceSequence(sequence),
    )


def fill(
    digit: str,
    *,
    side: OrderSide,
    quantity_units: int,
    price_units: int,
    execution_time: int,
) -> Fill:
    price = Price(price_units, MONEY_SCALE, str(INSTRUMENT), str(USD))
    return Fill(
        fill_id=domain_id(DomainIdKind.FILL, digit),
        order_id=domain_id(DomainIdKind.ORDER, digit),
        account_id=ACCOUNT,
        venue_id=VENUE,
        instrument_id=INSTRUMENT,
        side=side,
        quantity=Quantity(quantity_units, QUANTITY_SCALE, str(INSTRUMENT)),
        reference_price=price,
        reference_price_purpose=PricePurpose.EXECUTION_REFERENCE,
        price=price,
        slippage_amount=Money(0, MONEY_SCALE, str(USD)),
        slippage_decision_id=f"slippage:{digit}",
        slippage_model_key="slippage.zero.fixture.v1",
        slippage_calibration_id=None,
        liquidity="taker",
        execution_time=UtcInstant(execution_time),
    )


def fee_assessment(
    digit: str,
    basis_fill: Fill,
    *,
    amount_units: int,
    assessment_time: int,
) -> FeeAssessment:
    return FeeAssessment(
        fee_assessment_id=domain_id(DomainIdKind.FEE, digit),
        basis_type=FeeBasisType.FILL,
        basis_ids=(basis_fill.fill_id,),
        market_fee_rule_id="market-fee.synthetic.v1",
        account_fee_schedule_id="account-fee.primary.v1",
        tax_rule_id=None,
        amount=Money(amount_units, MONEY_SCALE, str(USD)),
        assessment_time=UtcInstant(assessment_time),
    )
