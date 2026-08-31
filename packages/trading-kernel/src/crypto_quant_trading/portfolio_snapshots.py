"""Current-state portfolio snapshot refresh for the additive portfolio runtime."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from crypto_quant_domain import (
    CurrencyId,
    Money,
    PortfolioSnapshot,
    PositionBalanceKey,
    PositionLot,
    PricePurpose,
    QuantizationPolicy,
    Scale,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)

from .ledger import LedgerState
from .marks import ResolvedMark
from .orders import OrderEventStream
from .reservations import ResourceReservationState
from .settlement import SettlementBookState
from .snapshots import (
    PortfolioSnapshotProjector,
    PortfolioValueKind,
    PortfolioValueRef,
    ReportingCurrencyValuation,
)
from .valuation import CurrencyValuationGraph, CurrencyValuationResolution


@dataclass(frozen=True, slots=True)
class PortfolioSnapshotRefreshPolicyV1:
    policy_key: str
    policy_version: int
    price_purpose: PricePurpose

    def __post_init__(self) -> None:
        if not isinstance(self.policy_key, str) or not self.policy_key:
            raise ValueError("policy_key must be nonempty text")
        if type(self.policy_version) is not int or self.policy_version <= 0:
            raise ValueError("policy_version must be positive integer")
        if self.price_purpose is not PricePurpose.VALUATION:
            raise ValueError("snapshot refresh requires VALUATION marks")

    @property
    def policy_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "portfolio_snapshot_refresh_policy_v1",
            "schema_version": 1,
            "policy_key": self.policy_key,
            "policy_version": self.policy_version,
            "price_purpose": self.price_purpose.value,
        }


PositionLotBooks = tuple[tuple[PositionBalanceKey, tuple[PositionLot, ...]], ...]


@dataclass(frozen=True, slots=True)
class PortfolioSnapshotRefreshInputV1:
    ledger_state: LedgerState
    position_lot_books: PositionLotBooks
    settlement_state: SettlementBookState
    reservation_state: ResourceReservationState
    working_orders: tuple[OrderEventStream, ...]
    resolved_marks: tuple[ResolvedMark, ...]
    currency_valuation_graph: CurrencyValuationGraph
    reporting_currency: CurrencyId
    quantization_policy: QuantizationPolicy
    timestamp: UtcInstant

    def __post_init__(self) -> None:
        if not isinstance(self.ledger_state, LedgerState):
            raise TypeError("ledger_state must be LedgerState")
        if type(self.position_lot_books) is not tuple:
            raise TypeError("position_lot_books must be tuple")
        for key, lots in self.position_lot_books:
            if not isinstance(key, PositionBalanceKey) or type(lots) is not tuple or not all(
                isinstance(lot, PositionLot) for lot in lots
            ):
                raise TypeError("invalid position lot book")
        lot_books = tuple(sorted(self.position_lot_books, key=lambda value: canonical_bytes(value[0])))
        if len({canonical_bytes(key) for key, _ in lot_books}) != len(lot_books):
            raise ValueError("duplicate position lot book")
        if not isinstance(self.settlement_state, SettlementBookState):
            raise TypeError("settlement_state must be SettlementBookState")
        if not isinstance(self.reservation_state, ResourceReservationState):
            raise TypeError("reservation_state must be ResourceReservationState")
        if type(self.working_orders) is not tuple or not all(
            isinstance(value, OrderEventStream) for value in self.working_orders
        ):
            raise TypeError("working_orders must contain OrderEventStream")
        working = tuple(sorted(self.working_orders, key=lambda value: value.order.order_id.value))
        if len({value.order.order_id for value in working}) != len(working):
            raise ValueError("duplicate working Order")
        if type(self.resolved_marks) is not tuple or not all(
            isinstance(value, ResolvedMark) for value in self.resolved_marks
        ):
            raise TypeError("resolved_marks must contain ResolvedMark")
        marks = tuple(sorted(self.resolved_marks, key=canonical_bytes))
        if not isinstance(self.currency_valuation_graph, CurrencyValuationGraph):
            raise TypeError("currency_valuation_graph must be CurrencyValuationGraph")
        if not isinstance(self.reporting_currency, CurrencyId):
            raise TypeError("reporting_currency must be CurrencyId")
        if not isinstance(self.quantization_policy, QuantizationPolicy):
            raise TypeError("quantization_policy must be QuantizationPolicy")
        if not isinstance(self.timestamp, UtcInstant):
            raise TypeError("timestamp must be UtcInstant")
        if (
            self.currency_valuation_graph.valuation_at != self.timestamp
            or self.currency_valuation_graph.price_purpose is not PricePurpose.VALUATION
        ):
            raise ValueError("valuation graph must match refresh time and purpose")
        account_ids = {
            registration.key.account_id
            for registration in self.ledger_state.schema.registrations
        }
        if len(account_ids) != 1:
            raise ValueError("snapshot refresh requires one ledger account")
        account_id = next(iter(account_ids))
        if (
            self.settlement_state.account_id != account_id
            or self.reservation_state.account_id != account_id
            or any(value.order.account_id != account_id for value in working)
        ):
            raise ValueError("snapshot refresh account mismatch")
        object.__setattr__(self, "position_lot_books", lot_books)
        object.__setattr__(self, "working_orders", working)
        object.__setattr__(self, "resolved_marks", marks)

    @property
    def input_hash(self) -> str:
        return canonical_sha256(self)

    @property
    def lot_book_hash(self) -> str:
        return canonical_sha256(self.position_lot_books)

    @property
    def working_order_set_hash(self) -> str:
        return canonical_sha256(self.working_orders)

    @property
    def decision_mark_set_hash(self) -> str:
        return canonical_sha256(self.resolved_marks)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "portfolio_snapshot_refresh_input_v1",
            "schema_version": 1,
            "ledger_state_hash": self.ledger_state.state_hash,
            "position_lot_books": self.position_lot_books,
            "settlement_state": self.settlement_state,
            "reservation_state": self.reservation_state,
            "working_orders": self.working_orders,
            "resolved_marks": self.resolved_marks,
            "currency_valuation_graph": self.currency_valuation_graph,
            "reporting_currency": self.reporting_currency,
            "quantization_policy": self.quantization_policy,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True, slots=True)
class PortfolioSnapshotRefresherV1:
    policy: PortfolioSnapshotRefreshPolicyV1

    def __post_init__(self) -> None:
        if not isinstance(self.policy, PortfolioSnapshotRefreshPolicyV1):
            raise TypeError("policy must be PortfolioSnapshotRefreshPolicyV1")

    def refresh(self, value: PortfolioSnapshotRefreshInputV1) -> PortfolioSnapshot:
        if not isinstance(value, PortfolioSnapshotRefreshInputV1):
            raise TypeError("value must be PortfolioSnapshotRefreshInputV1")
        self._validate_lot_books(value)
        valuations = self._valuations(value)
        outcome = PortfolioSnapshotProjector().project(
            ledger_state=value.ledger_state,
            resolved_marks=value.resolved_marks,
            valuations=valuations,
            reporting_currency=value.reporting_currency,
            reporting_scale=value.quantization_policy.target_scale,
            timestamp=value.timestamp,
            currency_valuation_graph_hash=value.currency_valuation_graph.graph_hash,
        )
        if outcome.snapshot is None:
            failure = outcome.failure
            code = "unknown" if failure is None else failure.code.value
            raise ValueError(f"portfolio snapshot refresh failed: {code}")
        return outcome.snapshot

    @staticmethod
    def _validate_lot_books(value: PortfolioSnapshotRefreshInputV1) -> None:
        supplied = dict(value.position_lot_books)
        positions = {position.key: position for position in value.ledger_state.position_balances}
        if set(supplied) != set(positions):
            raise ValueError("position lot books must exact-cover current ledger positions")
        for key, position in positions.items():
            lots = supplied[key]
            if (
                not lots
                or sum(lot.quantity.units for lot in lots) != position.quantity.units
                or (position.lots and position.lots != lots)
            ):
                raise ValueError("position lot quantity must match current ledger")

    def _valuations(
        self, value: PortfolioSnapshotRefreshInputV1
    ) -> tuple[ReportingCurrencyValuation, ...]:
        valuations: list[ReportingCurrencyValuation] = []
        for kind, balances in (
            (PortfolioValueKind.CASH, value.ledger_state.cash_balances),
            (PortfolioValueKind.REALIZED_PNL, value.ledger_state.realized_pnl),
            (PortfolioValueKind.FEES, value.ledger_state.fees),
            (PortfolioValueKind.FINANCING, value.ledger_state.financing),
        ):
            for balance in balances:
                valuations.append(
                    self._valuation(value, PortfolioValueRef(kind, balance.key), balance.amount)
                )
        marks = {mark.instrument_id: mark for mark in value.resolved_marks}
        lot_books = dict(value.position_lot_books)
        for position in value.ledger_state.position_balances:
            mark = marks.get(position.key.instrument_id)
            if mark is None:
                raise ValueError("current position is missing its decision-time mark")
            market_value = mark.price.notional(
                position.quantity,
                result_scale=value.quantization_policy.target_scale,
                rounding=value.quantization_policy.rounding,
            )
            cost_basis = self._cost_basis(lot_books[position.key], value.quantization_policy)
            if cost_basis.currency != market_value.currency:
                raise ValueError("position cost basis and mark currency mismatch")
            unrealized = Money(
                market_value.units - cost_basis.units,
                market_value.scale,
                market_value.currency,
            )
            valuations.append(
                self._valuation(
                    value,
                    PortfolioValueRef(PortfolioValueKind.POSITION_MARKET_VALUE, position.key),
                    market_value,
                    position_market=True,
                )
            )
            valuations.append(
                self._valuation(
                    value,
                    PortfolioValueRef(PortfolioValueKind.UNREALIZED_PNL, position.key),
                    unrealized,
                )
            )
        return tuple(sorted(valuations, key=canonical_bytes))

    @staticmethod
    def _cost_basis(
        lots: tuple[PositionLot, ...], quantization: QuantizationPolicy
    ) -> Money:
        currency: str | None = None
        total = Decimal(0)
        for lot in lots:
            if lot.total_cost_basis is not None:
                basis = lot.total_cost_basis
                amount = Decimal(basis.units).scaleb(-basis.scale.places)
            elif lot.unit_cost is not None:
                basis = lot.unit_cost.notional(
                    lot.quantity,
                    result_scale=quantization.target_scale,
                    rounding=quantization.rounding,
                )
                amount = Decimal(basis.units).scaleb(-basis.scale.places)
                amount += sum(
                    Decimal(fee.units).scaleb(-fee.scale.places)
                    for fee in lot.allocated_fees
                )
            else:
                raise ValueError("position lot is missing cost basis")
            if currency is None:
                currency = basis.currency
            elif currency != basis.currency:
                raise ValueError("position lot cost basis currency mismatch")
            total += amount
        if currency is None:
            raise ValueError("position lot book cannot be empty")
        return Money(
            quantization.quantize_decimal(total),
            quantization.target_scale,
            currency,
        )

    def _valuation(
        self,
        value: PortfolioSnapshotRefreshInputV1,
        value_ref: PortfolioValueRef,
        native_value: Money,
        *,
        position_market: bool = False,
    ) -> ReportingCurrencyValuation:
        outcome = value.currency_valuation_graph.resolve(
            CurrencyId(native_value.currency), value.reporting_currency
        )
        if outcome.resolution is None:
            raise ValueError("missing reporting-currency valuation path")
        reporting = self._convert(
            native_value, outcome.resolution, value.quantization_policy
        )
        return ReportingCurrencyValuation(
            value_ref=value_ref,
            native_value=native_value,
            reporting_value=reporting,
            resolution=outcome.resolution,
            currency_valuation_graph_hash=value.currency_valuation_graph.graph_hash,
            quantization_policy=(value.quantization_policy if position_market else None),
        )

    @staticmethod
    def _convert(
        native: Money,
        resolution: CurrencyValuationResolution,
        quantization: QuantizationPolicy,
    ) -> Money:
        if resolution.path.is_identity:
            if native.scale != quantization.target_scale:
                raise ValueError("identity valuation scale must match reporting scale")
            return native
        amount = Decimal(native.units).scaleb(-native.scale.places)
        for edge in resolution.path.edges:
            price = edge.resolved_mark.price
            amount *= Decimal(price.units).scaleb(-price.scale.places)
        return Money(
            quantization.quantize_decimal(amount),
            quantization.target_scale,
            str(resolution.path.reporting_currency_id),
        )


__all__ = [
    "PortfolioSnapshotRefreshInputV1",
    "PortfolioSnapshotRefresherV1",
    "PortfolioSnapshotRefreshPolicyV1",
]
