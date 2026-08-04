from __future__ import annotations

from crypto_quant_domain import (
    CashBalanceKey,
    CurrencyId,
    Money,
    OrderSide,
    PositionBalanceKey,
    PositionEffect,
    Quantity,
    Scale,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountRiskPolicy,
    AvailabilityState,
    CashAvailability,
    ExposureCapacityLimit,
    FeeReservationEstimator,
    FeeReserveFundingSource,
    PositionAvailability,
    PreTradeResourceRequirement,
    PreTradeRiskEvaluationInput,
    ReservationCommitment,
    ResourceReservationState,
)
from tests.kernel.fee_reservations._fixtures import (
    estimate_time,
    market_rule_approval,
    rule_set,
)


ACCOUNT = "account:primary"
USD = CurrencyId("USD")
EUR = CurrencyId("EUR")
MONEY_SCALE = Scale(2)
QUANTITY_SCALE = Scale(3)


def fee_proposal():
    outcome = FeeReservationEstimator().estimate(
        market_rule_approval(), rule_set(), estimate_time()
    )
    assert outcome.proposal is not None
    return outcome.proposal


def reservation_state(
    *,
    commitment: ReservationCommitment | None = None,
) -> ResourceReservationState:
    commitment = ReservationCommitment.empty() if commitment is None else commitment
    return ResourceReservationState(
        account_id=ACCOUNT,
        cursors=(),
        active_reservations=(),
        totals=commitment,
    )


def availability_state(
    state: ResourceReservationState,
    *,
    usd_tradable_units: int = 10_000_000,
    usd_margin_units: int = 8_000_000,
    sellable_units: int = 5_000,
    include_eur: bool = False,
) -> AvailabilityState:
    approval = market_rule_approval()
    order = approval.evaluation_input.executable_order_spec.source_order
    venue = order.intent.instrument_id.venue
    usd_key = CashBalanceKey(ACCOUNT, venue, USD)
    cash = [
        CashAvailability(
            key=usd_key,
            total=Money(12_000_000, MONEY_SCALE, str(USD)),
            settled=Money(12_000_000, MONEY_SCALE, str(USD)),
            tradable=Money(usd_tradable_units, MONEY_SCALE, str(USD)),
            withdrawable=Money(9_000_000, MONEY_SCALE, str(USD)),
            available_margin=Money(usd_margin_units, MONEY_SCALE, str(USD)),
        )
    ]
    if include_eur:
        eur_key = CashBalanceKey(ACCOUNT, venue, EUR)
        cash.append(
            CashAvailability(
                key=eur_key,
                total=Money(50_000, MONEY_SCALE, str(EUR)),
                settled=Money(50_000, MONEY_SCALE, str(EUR)),
                tradable=Money(50_000, MONEY_SCALE, str(EUR)),
                withdrawable=Money(50_000, MONEY_SCALE, str(EUR)),
                available_margin=Money(50_000, MONEY_SCALE, str(EUR)),
            )
        )
    position_key = PositionBalanceKey(ACCOUNT, venue, order.intent.instrument_id)
    return AvailabilityState(
        account_id=ACCOUNT,
        ledger_state_hash="sha256:" + "1" * 64,
        settlement_state_hash="sha256:" + "2" * 64,
        reservation_state_hash=state.state_hash,
        market_settlement_rules_hash="sha256:" + "3" * 64,
        cash=tuple(sorted(cash, key=lambda value: canonical_bytes(value.key))),
        positions=(
            PositionAvailability(
                key=position_key,
                total=Quantity(5_000, QUANTITY_SCALE, str(order.intent.instrument_id)),
                sellable=Quantity(
                    sellable_units,
                    QUANTITY_SCALE,
                    str(order.intent.instrument_id),
                ),
            ),
        ),
    )


def policy(
    *,
    funding_source: FeeReserveFundingSource = FeeReserveFundingSource.TRADABLE_CASH,
    allowed_sides: tuple[OrderSide, ...] = (OrderSide.BUY, OrderSide.SELL),
    order_capacity_limit: int = 5,
    exposure_limits: tuple[ExposureCapacityLimit, ...] | None = None,
) -> AccountRiskPolicy:
    approval = market_rule_approval()
    order = approval.evaluation_input.executable_order_spec.source_order
    return AccountRiskPolicy.create(
        policy_key="synthetic.cash.account-risk.v1",
        policy_version=1,
        account_id=ACCOUNT,
        venue_id=order.intent.instrument_id.venue,
        allowed_sides=allowed_sides,
        allowed_position_effects=(
            PositionEffect.AUTO,
            PositionEffect.OPEN,
            PositionEffect.CLOSE,
        ),
        allowed_reduce_only_values=(False, True),
        fee_reserve_funding_source=funding_source,
        order_capacity_limit=order_capacity_limit,
        exposure_capacity_limits=(
            (ExposureCapacityLimit(Money(20_000_000, MONEY_SCALE, str(USD))),)
            if exposure_limits is None
            else exposure_limits
        ),
    )


def requirement(
    *,
    commitment: ReservationCommitment | None = None,
    reverse: bool = False,
) -> PreTradeResourceRequirement:
    approval = market_rule_approval()
    proposal = fee_proposal()
    if commitment is None:
        values: tuple[Money, ...] = (
            Money(6_000_000, MONEY_SCALE, str(USD)),
            Money(10_000, MONEY_SCALE, str(EUR)),
        )
        exposure: tuple[Money, ...] = (
            Money(6_000_000, MONEY_SCALE, str(USD)),
            Money(10_000, MONEY_SCALE, str(EUR)),
        )
        if reverse:
            values = tuple(reversed(values))
            exposure = tuple(reversed(exposure))
        commitment = ReservationCommitment(
            cash=values,
            fee_reserve=proposal.commitment.fee_reserve,
            order_capacity_units=1,
            exposure_capacity=exposure,
        )
    return PreTradeResourceRequirement.create(
        requirement_source_key="synthetic.cash.resource-requirement.v1",
        requirement_source_version=1,
        requirement_source_hash=canonical_sha256(
            {
                "market_rule_decision_id": approval.decision_id,
                "fee_proposal_id": proposal.proposal_id,
                "account_profile": "synthetic.cash.account.v1",
            }
        ),
        market_rule_approval=approval,
        fee_reservation_proposal=proposal,
        commitment=commitment,
    )


def evaluation_input(
    *,
    state: ResourceReservationState | None = None,
    availability: AvailabilityState | None = None,
    resource_requirement: PreTradeResourceRequirement | None = None,
    risk_policy: AccountRiskPolicy | None = None,
    evaluated_at: int = 170,
) -> PreTradeRiskEvaluationInput:
    state = reservation_state() if state is None else state
    availability = (
        availability_state(state, include_eur=True)
        if availability is None
        else availability
    )
    return PreTradeRiskEvaluationInput(
        market_rule_approval=market_rule_approval(),
        fee_reservation_proposal=fee_proposal(),
        resource_requirement=(
            requirement() if resource_requirement is None else resource_requirement
        ),
        reservation_state=state,
        availability_state=availability,
        account_risk_policy=policy(
            exposure_limits=(
                ExposureCapacityLimit(Money(20_000_000, MONEY_SCALE, str(USD))),
                ExposureCapacityLimit(Money(100_000, MONEY_SCALE, str(EUR))),
            )
        )
        if risk_policy is None
        else risk_policy,
        evaluated_at=UtcInstant(evaluated_at),
    )


__all__ = [
    "ACCOUNT",
    "EUR",
    "MONEY_SCALE",
    "QUANTITY_SCALE",
    "USD",
    "availability_state",
    "evaluation_input",
    "fee_proposal",
    "policy",
    "requirement",
    "reservation_state",
]
