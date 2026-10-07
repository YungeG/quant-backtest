"""Development-only portfolio pre-trade approval using native Kernel fee/market facts.

This is NOT legacy venue-local PreTradeRiskApproval or an economic owner grant.
A separate versioned Backtest opening port must check the actual Bar event hash.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from crypto_quant_domain import Money, Order, OrderSide, Price, UtcInstant, canonical_sha256
from crypto_quant_trading.fee_reservations import ResourceReservationProposal
from crypto_quant_trading.market_rules import MarketRuleApproval, MarketSessionState
from crypto_quant_trading.reservations import ResourceReservationState
from .portfolio_order_plan_v1 import CnASharePortfolioOrderPlanV1, CnASharePortfolioOrderProposalV1
from .portfolio_sellability_v1 import CnASharePortfolioSellabilitySnapshotV1
from .shared_cny_cash_v1 import CnAShareSharedCnyCashSnapshotV1

_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class CnASharePortfolioOpenRiskApprovalDevelopmentV1:
    approval_id: str
    plan: CnASharePortfolioOrderPlanV1
    proposal: CnASharePortfolioOrderProposalV1
    order: Order
    market: MarketRuleApproval
    fee: ResourceReservationProposal
    open_price: Price
    open_event_hash: str
    evaluated_at: UtcInstant
    open_cash: CnAShareSharedCnyCashSnapshotV1
    open_sellability: CnASharePortfolioSellabilitySnapshotV1
    reservation_state: ResourceReservationState
    development_only: bool = field(default=True, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (type(self.plan) is not CnASharePortfolioOrderPlanV1
                or type(self.proposal) is not CnASharePortfolioOrderProposalV1
                or type(self.order) is not Order or type(self.market) is not MarketRuleApproval
                or type(self.fee) is not ResourceReservationProposal
                or type(self.open_price) is not Price or type(self.evaluated_at) is not UtcInstant
                or type(self.open_cash) is not CnAShareSharedCnyCashSnapshotV1
                or type(self.open_sellability) is not CnASharePortfolioSellabilitySnapshotV1
                or type(self.reservation_state) is not ResourceReservationState
                or type(self.open_event_hash) is not str or _HASH.fullmatch(self.open_event_hash) is None):
            raise TypeError("portfolio open risk needs exact native market, fee and account values")
        if (self.proposal not in self.plan.proposed
                or self.order.account_id != self.plan.account_id
                or self.order.intent != self.proposal.intent
                or self.order.created_at.instant >= self.evaluated_at
                or self.market.evaluation_input.executable_order_spec.source_order != self.order
                or self.market.evaluation_input.evaluated_at != self.evaluated_at
                or self.market.resolved_interval.snapshot.session_state is not MarketSessionState.OPEN
                or not self.market.resolved_interval.contains(self.evaluated_at)
                or self.market.evaluation_input.notional_evidence.price != self.open_price
                or self.market.evaluation_input.notional_evidence.available_at != self.evaluated_at
                or self.open_price.instrument_id != str(self.order.intent.instrument_id)
                or self.open_price.quote_currency != "CNY"
                or self.market.calculated_notional.currency != "CNY"
                or self.market.calculated_notional.scale.places != 2):
            raise ValueError("portfolio open market/Order/price evidence mismatch")
        if (self.fee.order_id != self.order.order_id
                or self.fee.fee_estimate.market_rule_approval != self.market
                or self.fee.fee_estimate.estimated_at != self.evaluated_at
                or self.fee.fee_estimate.total_fee != self.proposal.estimated_fee
                or self.proposal.fee_authority_hash != self.fee.fee_estimate.rule_set.rule_set_hash
                or self.fee.commitment.fee_reserve != ((self.proposal.estimated_fee,)
                     if self.proposal.estimated_fee.units else ())
                or self.fee.fee_estimate.rule_set.reservation_currency.value != "CNY"):
            raise ValueError("portfolio open fee proposal is not the actual Kernel estimate")
        if (self.open_cash.account_id != self.plan.account_id
                or self.open_sellability.account_id != self.plan.account_id
                or self.reservation_state.account_id != self.plan.account_id
                or self.open_cash.as_of != self.evaluated_at
                or self.open_sellability.as_of != self.evaluated_at
                or self.open_cash.journal_hash != self.plan.cash.journal_hash
                or self.open_sellability.journal_hash != self.open_cash.journal_hash
                or self.open_cash.settlement_state_hash != self.plan.cash.settlement_state_hash
                or self.open_sellability.settlement_state_hash != self.open_cash.settlement_state_hash
                or self.open_cash.market_rules_hash != self.plan.cash.market_rules_hash
                or self.open_sellability.market_rules_hash != self.open_cash.market_rules_hash
                or self.open_cash.reservation_state_hash != self.reservation_state.state_hash
                or self.open_sellability.reservation_state_hash != self.reservation_state.state_hash):
            raise ValueError("portfolio open shared CNY/T+1 source prefix mismatch")
        matches = tuple(value for value in self.reservation_state.active_reservations
                        if value.order_id == self.order.order_id)
        if (len(matches) != 1 or matches[0].source_proposal_hash != self.fee.proposal_hash
                or matches[0].remaining_quantity != self.order.intent.quantity):
            raise ValueError("portfolio open Order reservation does not bind Kernel fee proposal")
        commitment = matches[0].commitment
        if (commitment.fee_reserve != self.fee.commitment.fee_reserve
                or (self.order.intent.side is OrderSide.BUY and (
                    commitment.cash != (self.proposal.principal,)
                    or commitment.sellable_quantities
                    or self.market.calculated_notional != self.proposal.principal))
                or (self.order.intent.side is OrderSide.SELL and (
                    commitment.cash or commitment.sellable_quantities != (self.order.intent.quantity,)
                    or self.proposal.principal != Money(0, self.proposal.principal.scale, "CNY")))):
            raise ValueError("portfolio open principal, sell quantity or fee reserve mismatch")
        # The plan checks T+1 sellability before reserving shares. Requiring its
        # exact settlement prefix here prevents a post-plan availability switch.
        if self.approval_id != "cn-a-share-portfolio-open-risk-development-v1:" + canonical_sha256(self.identity_payload()):
            raise ValueError("portfolio open risk approval identity mismatch")

    @classmethod
    def create(cls, *, plan: CnASharePortfolioOrderPlanV1,
               proposal: CnASharePortfolioOrderProposalV1, order: Order,
               market: MarketRuleApproval, fee: ResourceReservationProposal,
               open_price: Price, open_event_hash: str, evaluated_at: UtcInstant,
               open_cash: CnAShareSharedCnyCashSnapshotV1,
               open_sellability: CnASharePortfolioSellabilitySnapshotV1,
               reservation_state: ResourceReservationState
               ) -> CnASharePortfolioOpenRiskApprovalDevelopmentV1:
        values = dict(plan=plan, proposal=proposal, order=order, market=market, fee=fee,
                      open_price=open_price, open_event_hash=open_event_hash,
                      evaluated_at=evaluated_at, open_cash=open_cash,
                      open_sellability=open_sellability, reservation_state=reservation_state)
        identity = {"type": "cn_a_share_portfolio_open_risk_development_identity",
                    "schema_version": 1, **values}
        return cls("cn-a-share-portfolio-open-risk-development-v1:" + canonical_sha256(identity),
                   plan, proposal, order, market, fee, open_price, open_event_hash,
                   evaluated_at, open_cash, open_sellability, reservation_state)

    def identity_payload(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_open_risk_development_identity",
                "schema_version": 1, "plan": self.plan, "proposal": self.proposal,
                "order": self.order, "market": self.market, "fee": self.fee,
                "open_price": self.open_price, "open_event_hash": self.open_event_hash,
                "evaluated_at": self.evaluated_at, "open_cash": self.open_cash,
                "open_sellability": self.open_sellability,
                "reservation_state": self.reservation_state}

    @property
    def approval_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self.identity_payload(), "type": "cn_a_share_portfolio_open_risk_development",
                "approval_id": self.approval_id, "development_only": True,
                "trade_authorized": False}
