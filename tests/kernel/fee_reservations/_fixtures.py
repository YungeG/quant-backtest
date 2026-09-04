from __future__ import annotations

from crypto_quant_domain import (
    CurrencyId,
    Money,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
    UtcInstant,
)
from crypto_quant_trading import (
    AccountFeeScheduleRef,
    FeeReservationApplicability,
    FeeReservationBasis,
    FeeReservationChargeRule,
    FeeReservationMinimum,
    FeeReservationRuleSet,
    FeeReservationRuleSource,
    MarketRuleApproval,
    MarketRuleEvaluator,
    ProfileComponentRef,
    ProfilePortType,
)
from tests.kernel.market_rules._fixtures import evaluation_input, timeline


USD = CurrencyId("USD")
FEE_SCALE = Scale(2)
QUANTIZATION = QuantizationPolicy(
    version="fee-reservation-usd-cent.v1",
    target_scale=FEE_SCALE,
    rounding=RoundingPolicy.CEILING,
)


def market_rule_approval() -> MarketRuleApproval:
    decision = MarketRuleEvaluator().evaluate(evaluation_input(), timeline())
    assert decision.approval is not None
    return decision.approval


def market_fee_ref() -> ProfileComponentRef:
    return ProfileComponentRef(
        port_type=ProfilePortType.FEE_ASSESSMENT_POLICY,
        component_key="synthetic.cash.market-fee.v1",
        component_version=1,
        component_digest="sha256:" + "a" * 64,
    )


def tax_ref() -> ProfileComponentRef:
    return ProfileComponentRef(
        port_type=ProfilePortType.TAX_POLICY,
        component_key="synthetic.cash.tax.v1",
        component_version=1,
        component_digest="sha256:" + "b" * 64,
    )


def account_ref() -> AccountFeeScheduleRef:
    return AccountFeeScheduleRef(
        schedule_key="synthetic.cash.account-fee.vip0.v1",
        schedule_version=1,
        schedule_digest="sha256:" + "c" * 64,
    )


def market_rule(
    *,
    basis: FeeReservationBasis = FeeReservationBasis.ORDER_NOTIONAL,
    applicability: FeeReservationApplicability = FeeReservationApplicability.APPLIES,
) -> FeeReservationChargeRule:
    return FeeReservationChargeRule(
        source=FeeReservationRuleSource.MARKET_FEE,
        rule_id="market_taker_fee",
        basis=basis,
        applicability=applicability,
        rate=(
            Rate(10, Scale(4), "fee_fraction")
            if basis is FeeReservationBasis.ORDER_NOTIONAL
            else None
        ),
        flat_amount=None,
        quantization=QUANTIZATION,
    )


def tax_rule(
    *,
    applicability: FeeReservationApplicability = FeeReservationApplicability.NOT_APPLICABLE,
) -> FeeReservationChargeRule:
    return FeeReservationChargeRule(
        source=FeeReservationRuleSource.TAX,
        rule_id="transaction_tax",
        basis=FeeReservationBasis.ORDER_NOTIONAL,
        applicability=applicability,
        rate=Rate(5, Scale(4), "fee_fraction"),
        flat_amount=None,
        quantization=QUANTIZATION,
    )


def account_rule() -> FeeReservationChargeRule:
    return FeeReservationChargeRule(
        source=FeeReservationRuleSource.ACCOUNT_SCHEDULE,
        rule_id="account_order_charge",
        basis=FeeReservationBasis.FLAT_PER_ORDER,
        applicability=FeeReservationApplicability.APPLIES,
        rate=None,
        flat_amount=Money(100, FEE_SCALE, str(USD)),
        quantization=QUANTIZATION,
    )


def minimum() -> FeeReservationMinimum:
    return FeeReservationMinimum(
        source=FeeReservationRuleSource.MARKET_FEE,
        minimum_id="market_order_minimum",
        charge_rule_ids=("market_taker_fee",),
        minimum_amount=Money(7_500, FEE_SCALE, str(USD)),
    )


def rule_set(
    *,
    rules: tuple[FeeReservationChargeRule, ...] | None = None,
    minimums: tuple[FeeReservationMinimum, ...] | None = None,
) -> FeeReservationRuleSet:
    return FeeReservationRuleSet.create(
        market_fee_policy_ref=market_fee_ref(),
        tax_policy_ref=tax_ref(),
        account_fee_schedule_ref=account_ref(),
        reservation_currency=USD,
        reservation_scale=FEE_SCALE,
        charge_rules=(market_rule(), tax_rule(), account_rule()) if rules is None else rules,
        minimums=(minimum(),) if minimums is None else minimums,
    )


def estimate_time() -> UtcInstant:
    return UtcInstant(160)
