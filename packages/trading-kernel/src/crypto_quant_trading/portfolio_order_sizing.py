"""Availability- and fee-aware capping for the additive portfolio path."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    ExecutionStyle,
    InstrumentId,
    Money,
    Order,
    OrderIntent,
    OrderSide,
    PositionEffect,
    Quantity,
    SimulationInstant,
    TimeInForce,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)

from .capabilities import OrderCapabilitySet, OrderCapabilityValidator
from .fee_reservations import (
    FeeReservationEstimate,
    FeeReservationEstimator,
    FeeReservationRuleSet,
)
from .market_rules import (
    MarketRuleEvaluator,
    OrderRuleEvaluationInput,
    OrderRuleNotionalEvidence,
    OrderRuleTimeline,
)
from .settlement import CashAvailability
from .sizing import QuantityLattice
from .translation import OrderTranslationMapping, OrderTranslator


class PortfolioSizingOmissionReason(str, Enum):
    T1_UNSELLABLE = "T1_UNSELLABLE"
    ZERO_AFTER_LATTICE = "ZERO_AFTER_LATTICE"
    SETTLED_CASH_CAPPED = "SETTLED_CASH_CAPPED"
    MINIMUM_COMMISSION_CAPPED = "MINIMUM_COMMISSION_CAPPED"
    ACTIVE_ORDER_COVERAGE = "ACTIVE_ORDER_COVERAGE"
    # Phase 4 owns supersession; Phase 3 reserves this durable code but never emits it.
    TARGET_SUPERSEDED = "TARGET_SUPERSEDED"


@dataclass(frozen=True, slots=True)
class PortfolioSizingOrderIdentityV1:
    schema_version: int
    decision_ordinal: int
    instrument_id: InstrumentId
    side: OrderSide
    preallocated_order_id: DomainId
    source_target_hash: str
    identity_hash: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        if type(self.decision_ordinal) is not int or self.decision_ordinal < 0:
            raise ValueError("decision_ordinal must be nonnegative integer")
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be OrderSide")
        if not isinstance(self.preallocated_order_id, DomainId) or (
            self.preallocated_order_id.kind is not DomainIdKind.ORDER
        ):
            raise TypeError("preallocated_order_id must be ORDER DomainId")
        if (
            not isinstance(self.source_target_hash, str)
            or not self.source_target_hash.startswith("sha256:")
        ):
            raise ValueError("source_target_hash must be sha256 identity")
        expected = canonical_sha256(self._body())
        if self.identity_hash != expected:
            raise ValueError("identity_hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        decision_ordinal: int,
        instrument_id: InstrumentId,
        side: OrderSide,
        preallocated_order_id: DomainId,
        source_target_hash: str,
    ) -> PortfolioSizingOrderIdentityV1:
        body = {
            "schema_version": 1,
            "decision_ordinal": decision_ordinal,
            "instrument_id": instrument_id,
            "side": side.value,
            "preallocated_order_id": preallocated_order_id,
            "source_target_hash": source_target_hash,
        }
        return cls(
            1,
            decision_ordinal,
            instrument_id,
            side,
            preallocated_order_id,
            source_target_hash,
            canonical_sha256(body),
        )

    def _body(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "decision_ordinal": self.decision_ordinal,
            "instrument_id": self.instrument_id,
            "side": self.side.value,
            "preallocated_order_id": self.preallocated_order_id,
            "source_target_hash": self.source_target_hash,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "portfolio_sizing_order_identity_v1",
            **self._body(),
            "identity_hash": self.identity_hash,
        }


@dataclass(frozen=True, slots=True)
class PortfolioSizingCandidateV1:
    identity: PortfolioSizingOrderIdentityV1
    account_id: str
    current_quantity: Quantity
    requested_target_quantity: Quantity
    sellable_quantity: Quantity
    retained_working_buy_coverage: Quantity
    retained_working_sell_coverage: Quantity
    lattice: QuantityLattice
    capability_set: OrderCapabilitySet
    translation_mapping: OrderTranslationMapping
    order_rule_timeline: OrderRuleTimeline
    notional_evidence: OrderRuleNotionalEvidence
    fee_rule_set: FeeReservationRuleSet
    created_at: SimulationInstant
    market_rule_evaluated_at: UtcInstant
    fee_estimated_at: UtcInstant

    def __post_init__(self) -> None:
        if not isinstance(self.identity, PortfolioSizingOrderIdentityV1):
            raise TypeError("identity must be PortfolioSizingOrderIdentityV1")
        if not isinstance(self.account_id, str) or not self.account_id:
            raise ValueError("account_id must be nonempty text")
        quantities = (
            self.current_quantity,
            self.requested_target_quantity,
            self.sellable_quantity,
            self.retained_working_buy_coverage,
            self.retained_working_sell_coverage,
        )
        if not all(isinstance(value, Quantity) for value in quantities):
            raise TypeError("candidate quantities must be Quantity")
        if any(
            value.instrument_id != str(self.identity.instrument_id)
            or value.scale != self.current_quantity.scale
            or value.units < 0
            for value in quantities
        ):
            raise ValueError("candidate quantity context mismatch")
        if self.identity.side is OrderSide.BUY and (
            self.requested_target_quantity.units < self.current_quantity.units
        ):
            raise ValueError("BUY identity requires a nondecreasing target")
        if self.identity.side is OrderSide.SELL and (
            self.requested_target_quantity.units > self.current_quantity.units
        ):
            raise ValueError("SELL identity requires a nonincreasing target")
        for value, expected in (
            (self.lattice, QuantityLattice),
            (self.capability_set, OrderCapabilitySet),
            (self.translation_mapping, OrderTranslationMapping),
            (self.order_rule_timeline, OrderRuleTimeline),
            (self.notional_evidence, OrderRuleNotionalEvidence),
            (self.fee_rule_set, FeeReservationRuleSet),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"invalid candidate authority: {expected.__name__}")
        if self.lattice.instrument_id != self.identity.instrument_id:
            raise ValueError("lattice Instrument mismatch")
        if not isinstance(self.created_at, SimulationInstant):
            raise TypeError("created_at must be SimulationInstant")
        if not isinstance(self.market_rule_evaluated_at, UtcInstant) or not isinstance(
            self.fee_estimated_at, UtcInstant
        ):
            raise TypeError("fee authority times must be UtcInstant")

    @property
    def requested_order_units(self) -> int:
        delta = self.requested_target_quantity.units - self.current_quantity.units
        coverage = (
            self.retained_working_buy_coverage.units
            if delta >= 0
            else self.retained_working_sell_coverage.units
        )
        return max(abs(delta) - coverage, 0)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "portfolio_sizing_candidate_v1",
            "schema_version": 1,
            "identity": self.identity,
            "account_id": self.account_id,
            "current_quantity": self.current_quantity,
            "requested_target_quantity": self.requested_target_quantity,
            "sellable_quantity": self.sellable_quantity,
            "retained_working_buy_coverage": self.retained_working_buy_coverage,
            "retained_working_sell_coverage": self.retained_working_sell_coverage,
            "lattice": self.lattice,
            "capability_set": self.capability_set,
            "translation_mapping": self.translation_mapping,
            "order_rule_timeline": self.order_rule_timeline,
            "notional_evidence": self.notional_evidence,
            "fee_rule_set": self.fee_rule_set,
            "created_at": self.created_at,
            "market_rule_evaluated_at": self.market_rule_evaluated_at,
            "fee_estimated_at": self.fee_estimated_at,
        }


@dataclass(frozen=True, slots=True)
class PortfolioOrderSizingEvidenceV1:
    identity: PortfolioSizingOrderIdentityV1
    requested_quantity: Quantity
    final_quantity: Quantity
    exact_notional: Money
    exact_fee_reservation: Money
    market_rule_approval_hash: str
    fee_estimate: FeeReservationEstimate
    fee_estimate_hash: str
    iteration_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.identity, PortfolioSizingOrderIdentityV1):
            raise TypeError("identity must be PortfolioSizingOrderIdentityV1")
        if not isinstance(self.requested_quantity, Quantity) or not isinstance(
            self.final_quantity, Quantity
        ):
            raise TypeError("sizing quantities must be Quantity")
        if not isinstance(self.exact_notional, Money) or not isinstance(
            self.exact_fee_reservation, Money
        ):
            raise TypeError("sizing financial values must be Money")
        if self.final_quantity.units <= 0 or (
            self.final_quantity.units > self.requested_quantity.units
        ):
            raise ValueError("final quantity must be positive and capped")
        if not isinstance(self.fee_estimate, FeeReservationEstimate) or (
            self.fee_estimate.total_fee != self.exact_fee_reservation
            or self.fee_estimate.estimate_hash != self.fee_estimate_hash
        ):
            raise ValueError("fee estimate must bind exact reservation")
        if type(self.iteration_count) is not int or self.iteration_count <= 0:
            raise ValueError("iteration_count must be positive integer")
        for name in ("market_rule_approval_hash", "fee_estimate_hash"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.startswith("sha256:"):
                raise ValueError(f"{name} must be sha256 identity")

    @property
    def evidence_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "portfolio_order_sizing_evidence_v1",
            "schema_version": 1,
            "identity": self.identity,
            "requested_quantity": self.requested_quantity,
            "final_quantity": self.final_quantity,
            "exact_notional": self.exact_notional,
            "exact_fee_reservation": self.exact_fee_reservation,
            "market_rule_approval_hash": self.market_rule_approval_hash,
            "fee_estimate": self.fee_estimate,
            "fee_estimate_hash": self.fee_estimate_hash,
            "iteration_count": self.iteration_count,
        }


@dataclass(frozen=True, slots=True)
class PortfolioSizingOmissionV1:
    instrument_id: InstrumentId
    reason: PortfolioSizingOmissionReason
    requested_quantity: Quantity
    omitted_quantity: Quantity

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.reason, PortfolioSizingOmissionReason):
            raise TypeError("reason must be PortfolioSizingOmissionReason")
        if not isinstance(self.requested_quantity, Quantity) or not isinstance(
            self.omitted_quantity, Quantity
        ):
            raise TypeError("omission quantities must be Quantity")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "portfolio_sizing_omission_v1",
            "instrument_id": self.instrument_id,
            "reason": self.reason.value,
            "requested_quantity": self.requested_quantity,
            "omitted_quantity": self.omitted_quantity,
        }


@dataclass(frozen=True, slots=True)
class CappedPortfolioTargetV1:
    source_target_hash: str
    cash_availability_hash: str
    sizing_evidence: tuple[PortfolioOrderSizingEvidenceV1, ...]
    omissions: tuple[PortfolioSizingOmissionV1, ...]
    available_buy_budget: Money
    exact_sell_fee_reservation: Money

    def __post_init__(self) -> None:
        if not isinstance(self.source_target_hash, str) or not self.source_target_hash.startswith(
            "sha256:"
        ):
            raise ValueError("source_target_hash must be sha256 identity")
        if not isinstance(self.cash_availability_hash, str) or not self.cash_availability_hash.startswith(
            "sha256:"
        ):
            raise ValueError("cash_availability_hash must be sha256 identity")
        if not isinstance(self.available_buy_budget, Money) or not isinstance(
            self.exact_sell_fee_reservation, Money
        ):
            raise TypeError("portfolio sizing budgets must be Money")
        if (
            self.available_buy_budget.currency
            != self.exact_sell_fee_reservation.currency
            or self.available_buy_budget.scale
            != self.exact_sell_fee_reservation.scale
        ):
            raise ValueError("portfolio sizing budget context mismatch")
        object.__setattr__(
            self,
            "sizing_evidence",
            tuple(sorted(self.sizing_evidence, key=lambda value: canonical_bytes(value.identity.instrument_id))),
        )
        object.__setattr__(
            self,
            "omissions",
            tuple(sorted(self.omissions, key=lambda value: (canonical_bytes(value.instrument_id), value.reason.value))),
        )

    @property
    def capped_target_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "capped_portfolio_target_v1",
            "schema_version": 1,
            "source_target_hash": self.source_target_hash,
            "cash_availability_hash": self.cash_availability_hash,
            "sizing_evidence": self.sizing_evidence,
            "omissions": self.omissions,
            "available_buy_budget": self.available_buy_budget,
            "exact_sell_fee_reservation": self.exact_sell_fee_reservation,
        }


class PortfolioOrderSizerV1:
    def size(
        self,
        *,
        source_target_hash: str,
        candidates: tuple[PortfolioSizingCandidateV1, ...],
        cash_availability: CashAvailability,
        active_cash_reservations: Money | None = None,
        active_fee_reservations: Money | None = None,
    ) -> CappedPortfolioTargetV1:
        if not isinstance(cash_availability, CashAvailability):
            raise TypeError("cash_availability must be CashAvailability")
        zero = Money(
            0,
            cash_availability.tradable.scale,
            cash_availability.tradable.currency,
        )
        active_cash_reservations = active_cash_reservations or zero
        active_fee_reservations = active_fee_reservations or zero
        if any(
            not isinstance(value, Money)
            or value.currency != cash_availability.tradable.currency
            or value.scale != cash_availability.tradable.scale
            or value.units < 0
            for value in (active_cash_reservations, active_fee_reservations)
        ):
            raise ValueError("active reservations must match Cash availability")
        ordered = tuple(
            sorted(
                candidates,
                key=lambda value: (
                    canonical_bytes(value.identity.instrument_id),
                    value.identity.side.value,
                ),
            )
        )
        identities = tuple(
            (value.identity.instrument_id, value.identity.side) for value in ordered
        )
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate portfolio sizing identity")
        if any(
            value.identity.source_target_hash != source_target_hash
            or value.fee_rule_set.reservation_currency.value
            != cash_availability.tradable.currency
            or value.fee_rule_set.reservation_scale
            != cash_availability.tradable.scale
            for value in ordered
        ):
            raise ValueError("portfolio sizing source or Cash context mismatch")
        sell_evidence: list[PortfolioOrderSizingEvidenceV1] = []
        buy_candidates: list[PortfolioSizingCandidateV1] = []
        omissions: list[PortfolioSizingOmissionV1] = []
        sell_fee_units = 0
        iterations = 0

        for candidate in ordered:
            coverage = (
                candidate.retained_working_buy_coverage.units
                if candidate.identity.side is OrderSide.BUY
                else candidate.retained_working_sell_coverage.units
            )
            requested = candidate.requested_order_units
            if coverage:
                omissions.append(
                    self._omission(
                        candidate,
                        PortfolioSizingOmissionReason.ACTIVE_ORDER_COVERAGE,
                        coverage,
                    )
                )
            if requested == 0:
                continue
            if candidate.identity.side is OrderSide.BUY:
                buy_candidates.append(candidate)
                continue
            maximum = max(
                candidate.sellable_quantity.units
                - candidate.retained_working_sell_coverage.units,
                0,
            )
            capped = min(requested, maximum)
            final_units = self._round_units(candidate, capped)
            if maximum < requested:
                omissions.append(self._omission(candidate, PortfolioSizingOmissionReason.T1_UNSELLABLE, requested - final_units))
            if final_units == 0:
                omissions.append(self._omission(candidate, PortfolioSizingOmissionReason.ZERO_AFTER_LATTICE, requested))
                continue
            evidence = self._evidence(candidate, final_units, 1)
            sell_evidence.append(evidence)
            sell_fee_units += evidence.exact_fee_reservation.units

        budget_units = max(
            min(cash_availability.settled.units, cash_availability.tradable.units)
            - active_cash_reservations.units
            - active_fee_reservations.units
            - sell_fee_units,
            0,
        )
        full = tuple((candidate, self._round_units(candidate, candidate.requested_order_units)) for candidate in buy_candidates)
        full_cost = sum(self._cost(candidate, units)[0] for candidate, units in full if units)
        full_notional = sum(self._cost(candidate, units)[1] for candidate, units in full if units)
        chosen = {candidate.identity.instrument_id: units for candidate, units in full}
        if full_cost > budget_units:
            breakpoints = {Fraction(0), Fraction(1)}
            # ponytail: O(total requested lots); replace with breakpoint search if portfolios become very large.
            for candidate, requested_units in full:
                lot = self._lot_units(candidate)
                for units in range(lot, requested_units + 1, lot):
                    breakpoints.add(Fraction(units, max(candidate.requested_order_units, 1)))
            for scale in sorted(breakpoints, reverse=True):
                vector = {
                    candidate.identity.instrument_id: self._round_units(
                        candidate,
                        candidate.requested_order_units * scale.numerator // scale.denominator,
                    )
                    for candidate in buy_candidates
                }
                iterations += 1
                total = sum(
                    self._cost(candidate, vector[candidate.identity.instrument_id])[0]
                    for candidate in buy_candidates
                    if vector[candidate.identity.instrument_id]
                )
                if total <= budget_units:
                    chosen = vector
                    break

        buy_evidence: list[PortfolioOrderSizingEvidenceV1] = []
        cap_reason = (
            PortfolioSizingOmissionReason.MINIMUM_COMMISSION_CAPPED
            if full_notional <= budget_units < full_cost
            else PortfolioSizingOmissionReason.SETTLED_CASH_CAPPED
        )
        for candidate in buy_candidates:
            requested = candidate.requested_order_units
            units = chosen[candidate.identity.instrument_id]
            if units < requested:
                omissions.append(self._omission(candidate, cap_reason, requested - units))
            if units == 0:
                omissions.append(self._omission(candidate, PortfolioSizingOmissionReason.ZERO_AFTER_LATTICE, requested))
                continue
            buy_evidence.append(self._evidence(candidate, units, max(iterations, 1)))

        money_type = type(cash_availability.tradable)
        return CappedPortfolioTargetV1(
            source_target_hash=source_target_hash,
            cash_availability_hash=canonical_sha256(cash_availability),
            sizing_evidence=tuple((*sell_evidence, *buy_evidence)),
            omissions=tuple(omissions),
            available_buy_budget=money_type(
                budget_units,
                cash_availability.tradable.scale,
                cash_availability.tradable.currency,
            ),
            exact_sell_fee_reservation=money_type(
                sell_fee_units,
                cash_availability.tradable.scale,
                cash_availability.tradable.currency,
            ),
        )

    @staticmethod
    def _lot_units(candidate: PortfolioSizingCandidateV1) -> int:
        return (
            candidate.lattice.buy_lot_units
            if candidate.identity.side is OrderSide.BUY
            else candidate.lattice.sell_lot_units
        ) or candidate.lattice.step_units

    def _round_units(self, candidate: PortfolioSizingCandidateV1, units: int) -> int:
        if (
            candidate.identity.side is OrderSide.SELL
            and candidate.lattice.whole_sell_residual_permitted
            and units == candidate.current_quantity.units
        ):
            return units
        lot = self._lot_units(candidate)
        return max(units, 0) // lot * lot

    def _cost(self, candidate: PortfolioSizingCandidateV1, units: int) -> tuple[int, int]:
        evidence = self._evidence(candidate, units, 1)
        return (
            evidence.exact_notional.units + evidence.exact_fee_reservation.units,
            evidence.exact_notional.units,
        )

    def _evidence(
        self, candidate: PortfolioSizingCandidateV1, units: int, iterations: int
    ) -> PortfolioOrderSizingEvidenceV1:
        quantity = Quantity(units, candidate.current_quantity.scale, str(candidate.identity.instrument_id))
        intent = OrderIntent(
            instrument_id=candidate.identity.instrument_id,
            side=candidate.identity.side,
            quantity=quantity,
            execution_style=ExecutionStyle.MARKET,
            price_constraint=None,
            time_in_force=(TimeInForce.GTC if candidate.identity.side is OrderSide.SELL else TimeInForce.DAY),
            reduce_only=False,
            position_effect=(PositionEffect.CLOSE if candidate.identity.side is OrderSide.SELL else PositionEffect.OPEN),
            urgency="normal",
            reason="portfolio-sizing-v1",
            parent_id=f"portfolio-sizing:{candidate.identity.source_target_hash}",
        )
        order = Order(candidate.identity.preallocated_order_id, candidate.account_id, intent, candidate.created_at)
        capability = OrderCapabilityValidator().validate(intent, candidate.capability_set)
        if capability.approval is None:
            raise ValueError("candidate capability rejected")
        translated = OrderTranslator().translate(
            order,
            capability.approval,
            candidate.translation_mapping,
            candidate.created_at.instant,
        )
        if translated.executable_spec is None:
            raise ValueError("candidate translation rejected")
        market = MarketRuleEvaluator().evaluate(
            OrderRuleEvaluationInput(
                translated.executable_spec,
                candidate.market_rule_evaluated_at,
                candidate.notional_evidence,
            ),
            candidate.order_rule_timeline,
        )
        if market.approval is None:
            raise ValueError("candidate market rule rejected")
        fees = FeeReservationEstimator().estimate(
            market.approval,
            candidate.fee_rule_set,
            candidate.fee_estimated_at,
        )
        if fees.estimate is None:
            raise ValueError("candidate fee reservation failed")
        return PortfolioOrderSizingEvidenceV1(
            identity=candidate.identity,
            requested_quantity=Quantity(
                candidate.requested_order_units,
                candidate.current_quantity.scale,
                str(candidate.identity.instrument_id),
            ),
            final_quantity=quantity,
            exact_notional=market.approval.calculated_notional,
            exact_fee_reservation=fees.estimate.total_fee,
            market_rule_approval_hash=canonical_sha256(market.approval),
            fee_estimate=fees.estimate,
            fee_estimate_hash=fees.estimate.estimate_hash,
            iteration_count=iterations,
        )

    @staticmethod
    def _omission(
        candidate: PortfolioSizingCandidateV1,
        reason: PortfolioSizingOmissionReason,
        omitted_units: int,
    ) -> PortfolioSizingOmissionV1:
        return PortfolioSizingOmissionV1(
            candidate.identity.instrument_id,
            reason,
            Quantity(
                candidate.requested_order_units,
                candidate.current_quantity.scale,
                str(candidate.identity.instrument_id),
            ),
            Quantity(
                max(omitted_units, 0),
                candidate.current_quantity.scale,
                str(candidate.identity.instrument_id),
            ),
        )


__all__ = [
    "CappedPortfolioTargetV1",
    "PortfolioOrderSizerV1",
    "PortfolioOrderSizingEvidenceV1",
    "PortfolioSizingCandidateV1",
    "PortfolioSizingOmissionReason",
    "PortfolioSizingOmissionV1",
    "PortfolioSizingOrderIdentityV1",
]
