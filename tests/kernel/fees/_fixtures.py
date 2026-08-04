from __future__ import annotations

from dataclasses import replace

from crypto_quant_domain import (
    CashBalanceKey,
    DomainId,
    DomainIdKind,
    FeeBasisType,
    Money,
    OrderSide,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
    SessionId,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
)
from crypto_quant_trading import (
    AccountFeeScheduleRef,
    FeeAssessmentBasisEvidence,
    FeeBasisClosureRef,
    FinalFeeApplicability,
    FinalFeeCalculationBasis,
    FinalFeeChargeRule,
    FinalFeeMinimum,
    FinalFeeRuleSet,
    FinalFeeRuleSource,
    OrderEventStream,
    ProfileComponentRef,
    ProfilePortType,
)
from tests.kernel.orders._fixtures import (
    ACCOUNT,
    USD,
    VENUE,
    fill,
    full_lifecycle_records,
    order,
)


FEE_SCALE = Scale(2)
FEE_QUANTIZATION = QuantizationPolicy(
    version="final-fee.usd-cent.ceiling.v1",
    target_scale=FEE_SCALE,
    rounding=RoundingPolicy.CEILING,
)
SESSION = SessionId("synthetic.calendar.v1", "2026-01-05.regular")


def domain_id(kind: DomainIdKind, digit: str) -> DomainId:
    return DomainId(kind, f"{kind.prefix}_{digit * 64}")


def market_fee_ref() -> ProfileComponentRef:
    return ProfileComponentRef(
        port_type=ProfilePortType.FEE_ASSESSMENT_POLICY,
        component_key="synthetic.cash.final-market-fee.v1",
        component_version=1,
        component_digest="sha256:" + "d" * 64,
    )


def tax_ref() -> ProfileComponentRef:
    return ProfileComponentRef(
        port_type=ProfilePortType.TAX_POLICY,
        component_key="synthetic.cash.final-tax.v1",
        component_version=1,
        component_digest="sha256:" + "e" * 64,
    )


def account_ref() -> AccountFeeScheduleRef:
    return AccountFeeScheduleRef(
        schedule_key="synthetic.cash.final-account-fee.v1",
        schedule_version=1,
        schedule_digest="sha256:" + "f" * 64,
    )


def charge_rule(
    source: FinalFeeRuleSource,
    rule_id: str,
    basis_type: FeeBasisType,
    *,
    calculation_basis: FinalFeeCalculationBasis = FinalFeeCalculationBasis.NOTIONAL_RATE,
    applicability: FinalFeeApplicability = FinalFeeApplicability.NOT_APPLICABLE,
    rate_units: int = 0,
    flat_units: int | None = None,
) -> FinalFeeChargeRule:
    return FinalFeeChargeRule(
        source=source,
        rule_id=rule_id,
        basis_type=basis_type,
        calculation_basis=calculation_basis,
        applicability=applicability,
        rate=(
            Rate(rate_units, Scale(4), "fee_fraction")
            if calculation_basis is FinalFeeCalculationBasis.NOTIONAL_RATE
            else None
        ),
        flat_amount=(
            Money(0 if flat_units is None else flat_units, FEE_SCALE, str(USD))
            if calculation_basis is FinalFeeCalculationBasis.FLAT_PER_BASIS
            else None
        ),
        quantization=FEE_QUANTIZATION,
    )


def all_rules() -> tuple[FinalFeeChargeRule, ...]:
    rules: list[FinalFeeChargeRule] = []
    for basis_type in FeeBasisType:
        rules.extend(
            (
                charge_rule(
                    FinalFeeRuleSource.MARKET_FEE,
                    f"market-{basis_type.value}",
                    basis_type,
                    applicability=(
                        FinalFeeApplicability.TAKER_ONLY
                        if basis_type is FeeBasisType.FILL
                        else FinalFeeApplicability.NOT_APPLICABLE
                    ),
                    rate_units=10,
                ),
                charge_rule(
                    FinalFeeRuleSource.TAX,
                    f"tax-{basis_type.value}",
                    basis_type,
                    applicability=(
                        FinalFeeApplicability.SELL_ONLY
                        if basis_type is FeeBasisType.FILL
                        else FinalFeeApplicability.NOT_APPLICABLE
                    ),
                    rate_units=5,
                ),
                charge_rule(
                    FinalFeeRuleSource.ACCOUNT_SCHEDULE,
                    f"account-{basis_type.value}",
                    basis_type,
                    calculation_basis=(
                        FinalFeeCalculationBasis.FLAT_PER_BASIS
                        if basis_type is FeeBasisType.SESSION
                        else FinalFeeCalculationBasis.NOTIONAL_RATE
                    ),
                    applicability=(
                        FinalFeeApplicability.ALWAYS
                        if basis_type is FeeBasisType.ORDER
                        else (
                            FinalFeeApplicability.ALWAYS
                            if basis_type is FeeBasisType.SESSION
                            else FinalFeeApplicability.NOT_APPLICABLE
                        )
                    ),
                    rate_units=10,
                    flat_units=200,
                ),
            )
        )
    return tuple(rules)


def order_minimum() -> FinalFeeMinimum:
    return FinalFeeMinimum(
        source=FinalFeeRuleSource.ACCOUNT_SCHEDULE,
        minimum_id="account-order-minimum",
        basis_type=FeeBasisType.ORDER,
        charge_rule_ids=("account-order",),
        minimum_amount=Money(500, FEE_SCALE, str(USD)),
    )


def rule_set(
    *,
    rules: tuple[FinalFeeChargeRule, ...] | None = None,
    minimums: tuple[FinalFeeMinimum, ...] | None = None,
) -> FinalFeeRuleSet:
    return FinalFeeRuleSet.create(
        market_fee_policy_ref=market_fee_ref(),
        tax_policy_ref=tax_ref(),
        account_fee_schedule_ref=account_ref(),
        assessment_currency=USD,
        assessment_scale=FEE_SCALE,
        charge_rules=all_rules() if rules is None else rules,
        minimums=(order_minimum(),) if minimums is None else minimums,
    )


def filled_stream(digit: str = "1", *, side: OrderSide = OrderSide.BUY) -> OrderEventStream:
    subject = order(digit)
    if side is not subject.intent.side:
        subject = replace(subject, intent=replace(subject.intent, side=side))
    return OrderEventStream.from_records(subject, full_lifecycle_records(subject))


def fill_basis(*, side: OrderSide = OrderSide.BUY, liquidity: str | None = "taker") -> FeeAssessmentBasisEvidence:
    subject = order("1")
    if side is not subject.intent.side:
        subject = replace(subject, intent=replace(subject.intent, side=side))
    basis_fill = replace(fill(subject, "2", 1_000, 100), liquidity=liquidity)
    return FeeAssessmentBasisEvidence.for_fill(basis_fill)


def order_basis(*, side: OrderSide = OrderSide.BUY) -> FeeAssessmentBasisEvidence:
    return FeeAssessmentBasisEvidence.for_order(filled_stream(side=side))


def closure_ref() -> FeeBasisClosureRef:
    return FeeBasisClosureRef.create(
        closure_key="synthetic.session-close.v1",
        closure_version=1,
        source_digest="sha256:" + "9" * 64,
        closed_at=UtcInstant(200),
    )


def session_basis() -> FeeAssessmentBasisEvidence:
    return FeeAssessmentBasisEvidence.for_session(
        session_id=SESSION,
        account_id=ACCOUNT,
        venue_id=VENUE,
        order_streams=(filled_stream(),),
        closure_ref=closure_ref(),
    )


def assessment_time() -> UtcInstant:
    return UtcInstant(220)


def recorded_at() -> SimulationInstant:
    return SimulationInstant(
        UtcInstant(230), TimelinePhase(90, "fees"), SourceSequence(1)
    )


def cash_key() -> CashBalanceKey:
    return CashBalanceKey(ACCOUNT, VENUE, USD)
