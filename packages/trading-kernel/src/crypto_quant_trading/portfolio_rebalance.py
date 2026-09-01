"""Side-specific ordering for the additive portfolio rebalance path."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
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
    PortfolioSizingOrderIdentityV1,
)
from .rebalance import CancelIntent


@dataclass(frozen=True, slots=True)
class PortfolioCancelReplaceV1:
    schema_version: int
    instrument_id: InstrumentId
    cancelled_order_id: DomainId
    cancel_intent_id: str
    prior_working_order_stream_hash: str
    replacement_order_id: DomainId
    replacement_sizing_identity_hash: str
    source_target_hash: str
    link_hash: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        for value in (self.cancelled_order_id, self.replacement_order_id):
            if not isinstance(value, DomainId) or value.kind is not DomainIdKind.ORDER:
                raise TypeError("cancel-replace Order IDs must be ORDER DomainId")
        if self.cancelled_order_id == self.replacement_order_id:
            raise ValueError("replacement requires a new Order identity")
        if not self.cancel_intent_id or not self.cancel_intent_id.startswith(
            "cancel-intent-v1:sha256:"
        ):
            raise ValueError("cancel_intent_id must be canonical identity")
        for name in (
            "prior_working_order_stream_hash",
            "replacement_sizing_identity_hash",
            "source_target_hash",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.startswith("sha256:"):
                raise ValueError(f"{name} must be sha256 identity")
        if self.link_hash != canonical_sha256(self._body()):
            raise ValueError("link_hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        instrument_id: InstrumentId,
        cancelled_order_id: DomainId,
        cancel_intent_id: str,
        prior_working_order_stream_hash: str,
        replacement_identity: PortfolioSizingOrderIdentityV1,
        source_target_hash: str,
    ) -> PortfolioCancelReplaceV1:
        if (
            replacement_identity.instrument_id != instrument_id
            or replacement_identity.source_target_hash != source_target_hash
        ):
            raise ValueError("replacement sizing identity context mismatch")
        body = {
            "schema_version": 1,
            "instrument_id": instrument_id,
            "cancelled_order_id": cancelled_order_id,
            "cancel_intent_id": cancel_intent_id,
            "prior_working_order_stream_hash": prior_working_order_stream_hash,
            "replacement_order_id": replacement_identity.preallocated_order_id,
            "replacement_sizing_identity_hash": replacement_identity.identity_hash,
            "source_target_hash": source_target_hash,
        }
        return cls(
            1,
            instrument_id,
            cancelled_order_id,
            cancel_intent_id,
            prior_working_order_stream_hash,
            replacement_identity.preallocated_order_id,
            replacement_identity.identity_hash,
            source_target_hash,
            canonical_sha256(body),
        )

    def _body(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "instrument_id": self.instrument_id,
            "cancelled_order_id": self.cancelled_order_id,
            "cancel_intent_id": self.cancel_intent_id,
            "prior_working_order_stream_hash": self.prior_working_order_stream_hash,
            "replacement_order_id": self.replacement_order_id,
            "replacement_sizing_identity_hash": self.replacement_sizing_identity_hash,
            "source_target_hash": self.source_target_hash,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "portfolio_cancel_replace_v1", **self._body(), "link_hash": self.link_hash}


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


@dataclass(frozen=True, slots=True)
class PortfolioOrderPlanV2:
    schema_version: int
    source_normalized_target_id: str
    source_normalized_target_hash: str
    decision_time: UtcInstant
    policy_hash: str
    sizing_evidence_hash: str
    cancellation_intents: tuple[CancelIntent, ...]
    planned_orders: tuple[PortfolioPlannedOrderV1, ...]
    cancel_replacements: tuple[PortfolioCancelReplaceV1, ...]
    omission_evidence_hashes: tuple[str, ...]
    plan_hash: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        cancellations = tuple(sorted(self.cancellation_intents, key=lambda value: (canonical_bytes(value.instrument_id), value.order_id.value)))
        orders = tuple(sorted(self.planned_orders, key=lambda value: (value.side_rank, canonical_bytes(value.instrument_id), value.sizing_evidence.identity.preallocated_order_id.value)))
        links = tuple(sorted(self.cancel_replacements, key=lambda value: (canonical_bytes(value.instrument_id), value.cancelled_order_id.value, value.replacement_order_id.value)))
        omissions = tuple(sorted(self.omission_evidence_hashes))
        if (
            self.cancellation_intents != cancellations
            or self.planned_orders != orders
            or self.cancel_replacements != links
            or self.omission_evidence_hashes != omissions
        ):
            raise ValueError("portfolio Order plan tuples must be canonical order")
        cancel_by_id = {value.order_id: value for value in cancellations}
        order_by_id = {value.sizing_evidence.identity.preallocated_order_id: value for value in orders}
        if len(cancel_by_id) != len(cancellations) or len(order_by_id) != len(orders):
            raise ValueError("duplicate cancellation or replacement Order identity")
        linked_cancel: set[DomainId] = set()
        linked_replace: set[DomainId] = set()
        for link in links:
            cancellation = cancel_by_id.get(link.cancelled_order_id)
            replacement = order_by_id.get(link.replacement_order_id)
            if (
                cancellation is None
                or replacement is None
                or cancellation.cancel_intent_id != link.cancel_intent_id
                or cancellation.instrument_id != link.instrument_id
                or replacement.instrument_id != link.instrument_id
                or replacement.sizing_evidence.identity.identity_hash
                != link.replacement_sizing_identity_hash
                or replacement.sizing_evidence.identity.source_target_hash
                != link.source_target_hash
                or link.source_target_hash != self.source_normalized_target_hash
                or link.cancelled_order_id in linked_cancel
                or link.replacement_order_id in linked_replace
            ):
                raise ValueError("cancel-replace exact-cover mismatch")
            linked_cancel.add(link.cancelled_order_id)
            linked_replace.add(link.replacement_order_id)
        cancel_instruments = {value.instrument_id: value.order_id for value in cancellations}
        order_instruments = {value.instrument_id: value.sizing_evidence.identity.preallocated_order_id for value in orders}
        for instrument_id in set(cancel_instruments) & set(order_instruments):
            if cancel_instruments[instrument_id] not in linked_cancel or order_instruments[instrument_id] not in linked_replace:
                raise ValueError("same-instrument cancel and replacement requires link")
        if any(value.normalized_target_id != self.source_normalized_target_id for value in cancellations) or any(
            value.sizing_evidence.identity.source_target_hash
            != self.source_normalized_target_hash
            for value in orders
        ):
            raise ValueError("portfolio Order plan source target mismatch")
        body = {
            "schema_version": self.schema_version,
            "source_normalized_target_id": self.source_normalized_target_id,
            "source_normalized_target_hash": self.source_normalized_target_hash,
            "decision_time": self.decision_time,
            "policy_hash": self.policy_hash,
            "sizing_evidence_hash": self.sizing_evidence_hash,
            "cancellation_intents": self.cancellation_intents,
            "planned_orders": self.planned_orders,
            "cancel_replacements": self.cancel_replacements,
            "omission_evidence_hashes": self.omission_evidence_hashes,
        }
        if self.plan_hash != canonical_sha256(body):
            raise ValueError("plan_hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        source_normalized_target_id: str,
        source_normalized_target_hash: str,
        decision_time: UtcInstant,
        policy_hash: str,
        sizing_evidence_hash: str,
        cancellation_intents: tuple[CancelIntent, ...],
        planned_orders: tuple[PortfolioPlannedOrderV1, ...],
        cancel_replacements: tuple[PortfolioCancelReplaceV1, ...],
        omission_evidence_hashes: tuple[str, ...],
    ) -> PortfolioOrderPlanV2:
        cancellations = tuple(sorted(cancellation_intents, key=lambda value: (canonical_bytes(value.instrument_id), value.order_id.value)))
        orders = tuple(sorted(planned_orders, key=lambda value: (value.side_rank, canonical_bytes(value.instrument_id), value.sizing_evidence.identity.preallocated_order_id.value)))
        links = tuple(sorted(cancel_replacements, key=lambda value: (canonical_bytes(value.instrument_id), value.cancelled_order_id.value, value.replacement_order_id.value)))
        omissions = tuple(sorted(omission_evidence_hashes))
        cancel_by_id = {value.order_id: value for value in cancellations}
        order_by_id = {value.sizing_evidence.identity.preallocated_order_id: value for value in orders}
        if len(cancel_by_id) != len(cancellations) or len(order_by_id) != len(orders):
            raise ValueError("duplicate cancellation or replacement Order identity")
        linked_cancel: set[DomainId] = set()
        linked_replace: set[DomainId] = set()
        for link in links:
            cancellation = cancel_by_id.get(link.cancelled_order_id)
            replacement = order_by_id.get(link.replacement_order_id)
            if (
                cancellation is None
                or replacement is None
                or cancellation.cancel_intent_id != link.cancel_intent_id
                or cancellation.instrument_id != link.instrument_id
                or replacement.instrument_id != link.instrument_id
                or replacement.sizing_evidence.identity.identity_hash
                != link.replacement_sizing_identity_hash
                or link.cancelled_order_id in linked_cancel
                or link.replacement_order_id in linked_replace
            ):
                raise ValueError("cancel-replace exact-cover mismatch")
            linked_cancel.add(link.cancelled_order_id)
            linked_replace.add(link.replacement_order_id)
        cancel_instruments = {value.instrument_id: value.order_id for value in cancellations}
        order_instruments = {value.instrument_id: value.sizing_evidence.identity.preallocated_order_id for value in orders}
        for instrument_id in set(cancel_instruments) & set(order_instruments):
            if (
                cancel_instruments[instrument_id] not in linked_cancel
                or order_instruments[instrument_id] not in linked_replace
            ):
                raise ValueError("same-instrument cancel and replacement requires link")
        body = {
            "schema_version": 1,
            "source_normalized_target_id": source_normalized_target_id,
            "source_normalized_target_hash": source_normalized_target_hash,
            "decision_time": decision_time,
            "policy_hash": policy_hash,
            "sizing_evidence_hash": sizing_evidence_hash,
            "cancellation_intents": cancellations,
            "planned_orders": orders,
            "cancel_replacements": links,
            "omission_evidence_hashes": omissions,
        }
        return cls(1, source_normalized_target_id, source_normalized_target_hash, decision_time, policy_hash, sizing_evidence_hash, cancellations, orders, links, omissions, canonical_sha256(body))

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "portfolio_order_plan_v2",
            "schema_version": self.schema_version,
            "source_normalized_target_id": self.source_normalized_target_id,
            "source_normalized_target_hash": self.source_normalized_target_hash,
            "decision_time": self.decision_time,
            "policy_hash": self.policy_hash,
            "sizing_evidence_hash": self.sizing_evidence_hash,
            "cancellation_intents": self.cancellation_intents,
            "planned_orders": self.planned_orders,
            "cancel_replacements": self.cancel_replacements,
            "omission_evidence_hashes": self.omission_evidence_hashes,
            "plan_hash": self.plan_hash,
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
    "PortfolioCancelReplaceV1",
    "PortfolioOrderPlanV2",
    "PortfolioPlanStageKind",
    "PortfolioPlanStageV1",
    "PortfolioPlannedOrderV1",
    "PortfolioRebalanceCoordinatorV2",
    "PortfolioRebalanceExecutionPolicyV1",
    "PortfolioRebalancePlanV1",
]
