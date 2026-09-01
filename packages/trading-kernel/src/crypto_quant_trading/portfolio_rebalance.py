"""Side-specific ordering for the additive portfolio rebalance path."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from crypto_quant_domain import (
    ExecutionStyle,
    InstrumentId,
    OrderIntent,
    OrderSide,
    PositionEffect,
    Quantity,
    TimeInForce,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)

from .portfolio_order_sizing import (
    CappedPortfolioTargetV1,
    PortfolioOrderSizingEvidenceV1,
)
from .rebalance import CancelIntent


class PortfolioPlanStageKind(str, Enum):
    CANCELLATION = "cancellation"
    ORDER = "order"


@dataclass(frozen=True, slots=True)
class PortfolioRebalanceExecutionPolicyV1:
    policy_key: str
    policy_version: int
    sell_tif: TimeInForce = TimeInForce.GTC
    buy_tif: TimeInForce = TimeInForce.DAY
    order_sequence: str = "SELL_THEN_BUY"
    sell_retry: str = "UNTIL_FILL_EXPIRY_OR_SUPERSESSION"
    buy_retry: str = "NEVER_AFTER_DAY_EXPIRY"
    supersession: str = "ATOMIC_CANCEL_REPLACE"
    buy_cash_basis: str = "SETTLED_UNRESERVED_CASH_AFTER_FEES"
    sell_quantity_basis: str = "SELLABLE_POSITION"
    target_snapshot_semantics: str = "COMPLETE_ABSOLUTE"

    def __post_init__(self) -> None:
        expected = (
            self.sell_tif is TimeInForce.GTC,
            self.buy_tif is TimeInForce.DAY,
            self.order_sequence == "SELL_THEN_BUY",
            self.sell_retry == "UNTIL_FILL_EXPIRY_OR_SUPERSESSION",
            self.buy_retry == "NEVER_AFTER_DAY_EXPIRY",
            self.supersession == "ATOMIC_CANCEL_REPLACE",
            self.buy_cash_basis == "SETTLED_UNRESERVED_CASH_AFTER_FEES",
            self.sell_quantity_basis == "SELLABLE_POSITION",
            self.target_snapshot_semantics == "COMPLETE_ABSOLUTE",
        )
        if not all(expected):
            raise ValueError("portfolio rebalance policy semantics are fixed")
        if not self.policy_key or type(self.policy_version) is not int or self.policy_version <= 0:
            raise ValueError("invalid portfolio rebalance policy identity")

    @property
    def policy_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "portfolio_rebalance_execution_policy_v1",
            "schema_version": 1,
            "policy_key": self.policy_key,
            "policy_version": self.policy_version,
            "sell_tif": self.sell_tif.value,
            "buy_tif": self.buy_tif.value,
            "order_sequence": self.order_sequence,
            "sell_retry": self.sell_retry,
            "buy_retry": self.buy_retry,
            "supersession": self.supersession,
            "buy_cash_basis": self.buy_cash_basis,
            "sell_quantity_basis": self.sell_quantity_basis,
            "target_snapshot_semantics": self.target_snapshot_semantics,
        }


@dataclass(frozen=True, slots=True)
class PortfolioPlannedOrderV1:
    instrument_id: InstrumentId
    intent: OrderIntent
    sizing_evidence: PortfolioOrderSizingEvidenceV1
    stage_rank: int
    side_rank: int

    @property
    def planned_order_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "portfolio_planned_order_v1",
            "schema_version": 1,
            "instrument_id": self.instrument_id,
            "intent": self.intent,
            "sizing_evidence": self.sizing_evidence,
            "stage_rank": self.stage_rank,
            "side_rank": self.side_rank,
        }


@dataclass(frozen=True, slots=True)
class PortfolioPlanStageV1:
    stage_kind: PortfolioPlanStageKind
    stage_rank: int
    side_rank: int
    instrument_id: InstrumentId
    source_hash: str

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "portfolio_plan_stage_v1",
            "stage_kind": self.stage_kind.value,
            "stage_rank": self.stage_rank,
            "side_rank": self.side_rank,
            "instrument_id": self.instrument_id,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class PortfolioRebalancePlanV1:
    plan_id: str
    source_capped_target_hash: str
    created_at: UtcInstant
    policy: PortfolioRebalanceExecutionPolicyV1
    cancellations: tuple[CancelIntent, ...]
    planned_orders: tuple[PortfolioPlannedOrderV1, ...]
    stages: tuple[PortfolioPlanStageV1, ...]

    @property
    def plan_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "portfolio_rebalance_plan_v1",
            "schema_version": 1,
            "plan_id": self.plan_id,
            "source_capped_target_hash": self.source_capped_target_hash,
            "created_at": self.created_at,
            "policy": self.policy,
            "cancellations": self.cancellations,
            "planned_orders": self.planned_orders,
            "stages": self.stages,
        }


class PortfolioRebalanceCoordinatorV2:
    def coordinate(
        self,
        *,
        capped_target: CappedPortfolioTargetV1,
        policy: PortfolioRebalanceExecutionPolicyV1,
        created_at: UtcInstant,
        cancellations: tuple[CancelIntent, ...] = (),
    ) -> PortfolioRebalancePlanV1:
        if not isinstance(capped_target, CappedPortfolioTargetV1):
            raise TypeError("capped_target must be CappedPortfolioTargetV1")
        if not isinstance(policy, PortfolioRebalanceExecutionPolicyV1):
            raise TypeError("policy must be PortfolioRebalanceExecutionPolicyV1")
        if not isinstance(created_at, UtcInstant):
            raise TypeError("created_at must be UtcInstant")
        ordered_cancellations = tuple(
            sorted(cancellations, key=lambda value: (canonical_bytes(value.instrument_id), value.order_id.value))
        )
        planned: list[PortfolioPlannedOrderV1] = []
        for evidence in capped_target.sizing_evidence:
            side = evidence.identity.side
            intent = OrderIntent(
                instrument_id=evidence.identity.instrument_id,
                side=side,
                quantity=evidence.final_quantity,
                execution_style=ExecutionStyle.MARKET,
                price_constraint=None,
                time_in_force=(policy.sell_tif if side is OrderSide.SELL else policy.buy_tif),
                reduce_only=False,
                position_effect=(PositionEffect.CLOSE if side is OrderSide.SELL else PositionEffect.OPEN),
                urgency="normal",
                reason="portfolio-rebalance-v1",
                parent_id=f"capped-target:{capped_target.capped_target_hash}",
            )
            planned.append(
                PortfolioPlannedOrderV1(
                    evidence.identity.instrument_id,
                    intent,
                    evidence,
                    100 if side is OrderSide.SELL else 110,
                    0 if side is OrderSide.SELL else 1,
                )
            )
        orders = tuple(
            sorted(
                planned,
                key=lambda value: (
                    value.stage_rank,
                    value.side_rank,
                    canonical_bytes(value.instrument_id),
                ),
            )
        )
        stages = tuple(
            [
                PortfolioPlanStageV1(
                    PortfolioPlanStageKind.CANCELLATION,
                    90,
                    0,
                    value.instrument_id,
                    value.cancel_intent_hash,
                )
                for value in ordered_cancellations
            ]
            + [
                PortfolioPlanStageV1(
                    PortfolioPlanStageKind.ORDER,
                    value.stage_rank,
                    value.side_rank,
                    value.instrument_id,
                    value.planned_order_hash,
                )
                for value in orders
            ]
        )
        identity = {
            "source_capped_target_hash": capped_target.capped_target_hash,
            "created_at": created_at,
            "policy_hash": policy.policy_hash,
            "stages": stages,
        }
        return PortfolioRebalancePlanV1(
            plan_id=f"portfolio-rebalance-plan-v1:{canonical_sha256(identity)}",
            source_capped_target_hash=capped_target.capped_target_hash,
            created_at=created_at,
            policy=policy,
            cancellations=ordered_cancellations,
            planned_orders=orders,
            stages=stages,
        )


__all__ = [
    "PortfolioPlanStageKind",
    "PortfolioPlanStageV1",
    "PortfolioPlannedOrderV1",
    "PortfolioRebalanceCoordinatorV2",
    "PortfolioRebalanceExecutionPolicyV1",
    "PortfolioRebalancePlanV1",
]
