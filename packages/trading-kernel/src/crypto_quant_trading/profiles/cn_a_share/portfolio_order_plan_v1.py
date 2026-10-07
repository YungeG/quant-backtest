"""Versioned CN portfolio ORDER-INTENT plan; no admission, fills or trade grant.

Separate from frozen order-plan-v1. All buy/sell TIF, cash, T+1 and working
Order cancellation facts are bound into one canonical identity for future Runtime.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from crypto_quant_domain import (
    DomainId, ExecutionStyle, Money, OrderIntent, OrderSide, OrderStatus,
    PositionEffect, UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading.orders import OrderEventStream
from crypto_quant_trading.rebalance import CancelIntent
from crypto_quant_trading.reservations import OrderReservationSchedule, ResourceReservationBook

from .portfolio_rebalance_policy_v1 import CnAShareRebalanceExecutionPolicyV1
from .portfolio_sellability_v1 import CnASharePortfolioSellabilitySnapshotV1
from .shared_cny_cash_v1 import CnAShareSharedCnyCashSnapshotV1

_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TARGET = re.compile(r"normalized-portfolio-target-v[12]:sha256:[0-9a-f]{64}\Z")
_WORKING = {OrderStatus.ACCEPTED, OrderStatus.ACTIVE, OrderStatus.PARTIALLY_FILLED,
            OrderStatus.CANCEL_REQUESTED}


@dataclass(frozen=True, slots=True)
class CnASharePortfolioOrderProposalV1:
    intent: OrderIntent
    principal: Money
    estimated_fee: Money
    fee_authority_hash: str

    def __post_init__(self) -> None:
        if type(self.intent) is not OrderIntent or self.intent.instrument_id.venue.value not in {"xshg", "xshe"}:
            raise ValueError("portfolio proposal needs exact SH/SZ OrderIntent")
        if (self.intent.execution_style is not ExecutionStyle.MARKET
                or self.intent.price_constraint is not None
                or (self.intent.side is OrderSide.SELL and (
                    not self.intent.reduce_only or self.intent.position_effect is not PositionEffect.CLOSE))
                or (self.intent.side is OrderSide.BUY and (
                    self.intent.reduce_only or self.intent.position_effect is not PositionEffect.OPEN))):
            raise ValueError("CN cash portfolio requires MARKET buy-open or reduce-only sell-close")
        if (type(self.principal) is not Money or type(self.estimated_fee) is not Money
                or any(value.currency != "CNY" or value.scale.places != 2 or value.units < 0
                       for value in (self.principal, self.estimated_fee))
                or (self.intent.side is OrderSide.BUY and self.principal.units <= 0)
                or (self.intent.side is OrderSide.SELL and self.principal.units != 0)
                or type(self.fee_authority_hash) is not str
                or _HASH.fullmatch(self.fee_authority_hash) is None):
            raise ValueError("portfolio proposal needs CNY principal/fee and frozen fee authority")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_order_proposal", "schema_version": 1,
                "intent": self.intent, "principal": self.principal,
                "estimated_fee": self.estimated_fee, "fee_authority_hash": self.fee_authority_hash}


@dataclass(frozen=True, slots=True)
class CnASharePortfolioOrderPlanV1:
    plan_id: str
    account_id: str
    target_id: str
    target_hash: str
    as_of: UtcInstant
    policy: CnAShareRebalanceExecutionPolicyV1
    cash: CnAShareSharedCnyCashSnapshotV1
    sellability: CnASharePortfolioSellabilitySnapshotV1
    working_order_set_hash: str
    proposed: tuple[CnASharePortfolioOrderProposalV1, ...]
    cancel_intents: tuple[CancelIntent, ...]
    retained_working_order_ids: tuple[DomainId, ...]
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (type(self.account_id) is not str or not self.account_id
                or type(self.target_id) is not str or _TARGET.fullmatch(self.target_id) is None
                or type(self.as_of) is not UtcInstant
                or any(type(value) is not str or _HASH.fullmatch(value) is None
                       for value in (self.target_hash, self.working_order_set_hash))
                or type(self.policy) is not CnAShareRebalanceExecutionPolicyV1
                or type(self.cash) is not CnAShareSharedCnyCashSnapshotV1
                or type(self.sellability) is not CnASharePortfolioSellabilitySnapshotV1
                or not isinstance(self.proposed, tuple) or not isinstance(self.cancel_intents, tuple)
                or not isinstance(self.retained_working_order_ids, tuple)):
            raise ValueError("portfolio plan requires exact frozen values")
        if (self.cash.account_id != self.account_id or self.sellability.account_id != self.account_id
                or self.cash.as_of != self.as_of or self.sellability.as_of != self.as_of
                or self.cash.journal_hash != self.sellability.journal_hash
                or self.cash.settlement_state_hash != self.sellability.settlement_state_hash
                or self.cash.reservation_state_hash != self.sellability.reservation_state_hash
                or self.cash.market_rules_hash != self.sellability.market_rules_hash):
            raise ValueError("portfolio plan cash and T+1 source prefixes differ")
        if (not all(type(p) is CnASharePortfolioOrderProposalV1 for p in self.proposed)
                or not all(type(c) is CancelIntent and c.normalized_target_id == self.target_id
                           for c in self.cancel_intents)
                or not all(type(i) is DomainId for i in self.retained_working_order_ids)):
            raise ValueError("portfolio plan proposal/cancel/working type mismatch")
        instruments = [p.intent.instrument_id for p in self.proposed]
        if len(instruments) != len(set(instruments)) or self.proposed != tuple(sorted(
            self.proposed, key=lambda p: (p.intent.side is OrderSide.BUY, p.intent.instrument_id))):
            raise ValueError("portfolio plan must be unique, sell-first and instrument-sorted")
        if (len({c.order_id for c in self.cancel_intents}) != len(self.cancel_intents)
                or len(set(self.retained_working_order_ids)) != len(self.retained_working_order_ids)
                or set(instruments) & {c.instrument_id for c in self.cancel_intents}):
            raise ValueError("portfolio plan duplicate or cancellation pending for instrument")
        buy_cost = 0
        sell_fees = 0
        for proposal in self.proposed:
            intent = proposal.intent
            if (intent.parent_id != self.target_id
                    or intent.time_in_force is not self.policy.time_in_force_for(intent.side)):
                raise ValueError("portfolio plan target/TIF mismatch")
            if intent.side is OrderSide.SELL:
                if self.sellability.sellable_for(intent.instrument_id).units < intent.quantity.units:
                    raise ValueError("portfolio plan T+1 forbids unsettled or reserved sell")
                sell_fees += proposal.estimated_fee.units
            else:
                buy_cost += proposal.principal.units + proposal.estimated_fee.units
        if buy_cost + sell_fees > self.cash.spendable.units:
            raise ValueError("portfolio plan may not reuse cash or prefinance sell receipts")
        if self.plan_id != "cn-a-share-portfolio-order-plan-v1:" + canonical_sha256(self.identity_payload()):
            raise ValueError("portfolio plan identity mismatch")

    @classmethod
    def create(cls, *, account_id: str, target_id: str, target_hash: str,
               as_of: UtcInstant, policy: CnAShareRebalanceExecutionPolicyV1,
               cash: CnAShareSharedCnyCashSnapshotV1,
               sellability: CnASharePortfolioSellabilitySnapshotV1,
               working_orders: tuple[OrderEventStream, ...],
               reservation_schedules: tuple[OrderReservationSchedule, ...],
               proposed: tuple[CnASharePortfolioOrderProposalV1, ...]) -> CnASharePortfolioOrderPlanV1:
        if type(working_orders) is not tuple or not all(type(s) is OrderEventStream for s in working_orders):
            raise TypeError("working_orders must be exact OrderEventStreams")
        if type(reservation_schedules) is not tuple or not all(
                type(s) is OrderReservationSchedule for s in reservation_schedules):
            raise TypeError("reservation_schedules must be exact OrderReservationSchedules")
        ordered = tuple(sorted(working_orders, key=lambda s: s.order.order_id.value))
        if ResourceReservationBook(account_id).project(ordered, reservation_schedules).state_hash != cash.reservation_state_hash:
            raise ValueError("working Orders do not bind shared CNY reservation prefix")
        if len({s.order.order_id for s in ordered}) != len(ordered):
            raise ValueError("duplicate working Order identity")
        cancels: list[CancelIntent] = []
        retained: list[DomainId] = []
        for stream in ordered:
            order, state = stream.order, stream.state
            if (order.account_id != account_id or state is None
                    or state.updated_at.instant > as_of
                    or order.intent.time_in_force is not policy.time_in_force_for(order.intent.side)):
                raise ValueError("working Order account/time/TIF mismatch")
            if state.status not in _WORKING:
                continue  # EXPIRED buy does not persist into W+1; a filled Order is terminal.
            if state.status is OrderStatus.CANCEL_REQUESTED:
                retained.append(order.order_id)  # Wait for cancellation confirmation.
            elif order.intent.parent_id == target_id:
                retained.append(order.order_id)  # Unfilled GTC sell persists if same target.
            else:
                payload = {"type": "cancel_intent_identity", "schema_version": 1,
                           "order_id": order.order_id, "stream_hash": stream.stream_hash,
                           "instrument_id": order.intent.instrument_id,
                           "reason_code": "prior_target_superseded", "normalized_target_id": target_id}
                cancels.append(CancelIntent(
                    "cancel-intent-v1:" + canonical_sha256(payload),
                    order.order_id, order.intent.instrument_id,
                    "prior_target_superseded", target_id))
        occupied = {s.order.intent.instrument_id for s in ordered
                    if s.state is not None and s.state.status in _WORKING}
        if occupied & {p.intent.instrument_id for p in proposed}:
            raise ValueError("portfolio plan cannot replan an instrument with working or cancelling Order")
        proposed_sorted = tuple(sorted(proposed, key=lambda p: (
            p.intent.side is OrderSide.BUY, p.intent.instrument_id)))
        working_hash = canonical_sha256(tuple(s.stream_hash for s in ordered))
        content = dict(account_id=account_id, target_id=target_id, target_hash=target_hash,
                       as_of=as_of, policy=policy, cash=cash, sellability=sellability,
                       working_order_set_hash=working_hash,
                       proposed=proposed_sorted, cancel_intents=tuple(cancels),
                       retained_working_order_ids=tuple(retained))
        plan_id = "cn-a-share-portfolio-order-plan-v1:" + canonical_sha256({
            "type": "cn_a_share_portfolio_order_plan_identity", "schema_version": 1, **content})
        return cls(plan_id=plan_id, account_id=account_id, target_id=target_id,
                   target_hash=target_hash, as_of=as_of, policy=policy, cash=cash,
                   sellability=sellability,
                   working_order_set_hash=working_hash,
                   proposed=proposed_sorted, cancel_intents=tuple(cancels),
                   retained_working_order_ids=tuple(retained))

    def identity_payload(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_order_plan_identity", "schema_version": 1,
                "account_id": self.account_id, "target_id": self.target_id,
                "target_hash": self.target_hash, "as_of": self.as_of, "policy": self.policy,
                "cash": self.cash, "sellability": self.sellability,
                "working_order_set_hash": self.working_order_set_hash,
                "proposed": self.proposed, "cancel_intents": self.cancel_intents,
                "retained_working_order_ids": self.retained_working_order_ids}

    @property
    def plan_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self.identity_payload(), "type": "cn_a_share_portfolio_order_plan",
                "plan_id": self.plan_id, "trade_authorized": False}
