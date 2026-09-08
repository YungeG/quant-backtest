"""Pure cash-instrument Fill and FeeAssessment accounting translation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from fractions import Fraction
from math import ceil, floor
from typing import Any, cast

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    CashBalanceKey,
    DomainId,
    DomainIdKind,
    FeeAssessment,
    FeeBasisType,
    Fill,
    Money,
    OrderSide,
    PositionBalanceKey,
    PositionLot,
    PositionLotChange,
    Price,
    QuantizationPolicy,
    Quantity,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    canonical_bytes,
    canonical_sha256,
)


class CostBasisMethod(str, Enum):
    FIFO = "fifo"


@dataclass(frozen=True, slots=True)
class CostBasisPolicy:
    policy_key: str
    policy_version: int
    method: CostBasisMethod
    fee_allocation_rounding: RoundingPolicy

    def __post_init__(self) -> None:
        if (
            not isinstance(self.policy_key, str)
            or not self.policy_key
            or self.policy_key != self.policy_key.strip()
        ):
            raise ValueError("policy_key must be canonical non-empty text")
        canonical_bytes(self.policy_key)
        if isinstance(self.policy_version, bool) or not isinstance(
            self.policy_version, int
        ):
            raise TypeError("policy_version must be an integer")
        if self.policy_version <= 0:
            raise ValueError("policy_version must be positive")
        if not isinstance(self.method, CostBasisMethod):
            raise ValueError("method must be CostBasisMethod")
        if not isinstance(self.fee_allocation_rounding, RoundingPolicy):
            raise TypeError("fee_allocation_rounding must be RoundingPolicy")

    @property
    def policy_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cost_basis_policy",
            "policy_key": self.policy_key,
            "policy_version": self.policy_version,
            "method": self.method.value,
            "fee_allocation_rounding": self.fee_allocation_rounding.value,
        }


@dataclass(frozen=True, slots=True)
class LotConsumption:
    lot_id: str
    source_fill_id: str
    quantity: Quantity
    unit_cost: Price
    allocated_fees: tuple[Money, ...]
    total_cost_basis: Money | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        for name, value in (
            ("lot_id", self.lot_id),
            ("source_fill_id", self.source_fill_id),
        ):
            if not isinstance(value, str) or not value or value != value.strip():
                raise ValueError(f"{name} must be canonical non-empty text")
            canonical_bytes(value)
        if not isinstance(self.quantity, Quantity) or self.quantity.units <= 0:
            raise ValueError("LotConsumption quantity must be positive Quantity")
        if not isinstance(self.unit_cost, Price) or self.unit_cost.units <= 0:
            raise ValueError("LotConsumption unit_cost must be positive Price")
        if self.quantity.instrument_id != self.unit_cost.instrument_id:
            raise ValueError("LotConsumption instrument identity mismatch")
        if self.total_cost_basis is not None:
            if not isinstance(self.total_cost_basis, Money):
                raise TypeError("LotConsumption total_cost_basis must be Money or None")
            if self.total_cost_basis.units < 0:
                raise ValueError("LotConsumption total_cost_basis cannot be negative")
            if self.total_cost_basis.currency != self.unit_cost.quote_currency:
                raise ValueError("LotConsumption total_cost_basis currency mismatch")
        _validate_fee_tuple(self.allocated_fees)
        if any(
            fee.currency != self.unit_cost.quote_currency
            for fee in self.allocated_fees
        ):
            raise ValueError("LotConsumption allocated fee currency mismatch")

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = {
            "type": "lot_consumption",
            "lot_id": self.lot_id,
            "source_fill_id": self.source_fill_id,
            "quantity": self.quantity,
            "unit_cost": self.unit_cost,
            "allocated_fees": self.allocated_fees,
        }
        if self.total_cost_basis is not None:
            payload["schema_version"] = 2
            payload["total_cost_basis"] = self.total_cost_basis
        return payload


@dataclass(frozen=True, slots=True)
class CashFillAccountingResult:
    journal_entry: AccountingJournalEntry
    open_lots: tuple[PositionLot, ...]
    opened_lot: PositionLot | None
    lot_consumptions: tuple[LotConsumption, ...]
    price_cost_basis: Money | None
    gross_realized_pnl: Money | None
    cost_basis_policy: CostBasisPolicy

    def __post_init__(self) -> None:
        _validate_accounting_result(
            self.journal_entry,
            self.open_lots,
            self.cost_basis_policy,
            AccountingEntryType.FILL_BOOKED,
        )
        if self.opened_lot is not None and not isinstance(self.opened_lot, PositionLot):
            raise TypeError("opened_lot must be PositionLot or None")
        if not isinstance(self.lot_consumptions, tuple) or not all(
            isinstance(value, LotConsumption) for value in self.lot_consumptions
        ):
            raise TypeError("lot_consumptions must contain LotConsumption")
        if self.price_cost_basis is not None and not isinstance(
            self.price_cost_basis, Money
        ):
            raise TypeError("price_cost_basis must be Money or None")
        if self.gross_realized_pnl is not None and not isinstance(
            self.gross_realized_pnl, Money
        ):
            raise TypeError("gross_realized_pnl must be Money or None")
        if not isinstance(self.cost_basis_policy, CostBasisPolicy):
            raise TypeError("cost_basis_policy must be CostBasisPolicy")
        if self.journal_entry.entry_type is not AccountingEntryType.FILL_BOOKED:
            raise ValueError("CashFillAccountingResult requires FILL_BOOKED entry")
        if self.opened_lot is not None:
            if self.opened_lot not in self.open_lots:
                raise ValueError("opened_lot must remain in open_lots")
            if self.lot_consumptions or self.price_cost_basis is not None or self.gross_realized_pnl is not None:
                raise ValueError("Buy result cannot contain Sell accounting")
        else:
            if not self.lot_consumptions:
                raise ValueError("Sell result requires lot consumption")
            if self.price_cost_basis is None or self.gross_realized_pnl is None:
                raise ValueError("Sell result requires cost basis and realized profit/loss")
            if (
                self.price_cost_basis.currency != self.gross_realized_pnl.currency
                or self.price_cost_basis.scale != self.gross_realized_pnl.scale
            ):
                raise ValueError("Sell result Money context mismatch")
            expected_realized = (
                (self.gross_realized_pnl,)
                if self.gross_realized_pnl.units
                else ()
            )
            if self.journal_entry.realized_pnl != expected_realized:
                raise ValueError("Sell result Journal realized profit/loss mismatch")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cash_fill_accounting_result",
            "journal_entry": self.journal_entry,
            "open_lots": self.open_lots,
            "opened_lot": self.opened_lot,
            "lot_consumptions": self.lot_consumptions,
            "price_cost_basis": self.price_cost_basis,
            "gross_realized_pnl": self.gross_realized_pnl,
            "cost_basis_policy": self.cost_basis_policy,
        }


@dataclass(frozen=True, slots=True)
class FeeChargeAccountingResult:
    journal_entry: AccountingJournalEntry
    open_lots: tuple[PositionLot, ...]
    allocated_lot_id: str | None
    cost_basis_policy: CostBasisPolicy

    def __post_init__(self) -> None:
        _validate_accounting_result(
            self.journal_entry,
            self.open_lots,
            self.cost_basis_policy,
            AccountingEntryType.FEE_CHARGED,
        )
        if self.allocated_lot_id is not None:
            if (
                not isinstance(self.allocated_lot_id, str)
                or not self.allocated_lot_id
                or self.allocated_lot_id != self.allocated_lot_id.strip()
            ):
                raise ValueError("allocated_lot_id must be canonical text or None")
            canonical_bytes(self.allocated_lot_id)
            if self.allocated_lot_id not in {lot.lot_id for lot in self.open_lots}:
                raise ValueError("allocated_lot_id must identify an open lot")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "fee_charge_accounting_result",
            "journal_entry": self.journal_entry,
            "open_lots": self.open_lots,
            "allocated_lot_id": self.allocated_lot_id,
            "cost_basis_policy": self.cost_basis_policy,
        }


class CashAccountingFailureCode(str, Enum):
    MISSING_COST_BASIS_POLICY = "missing_cost_basis_policy"
    UNSUPPORTED_COST_BASIS_METHOD = "unsupported_cost_basis_method"
    CONTEXT_MISMATCH = "context_mismatch"
    INVALID_LOT_STATE = "invalid_lot_state"
    INSUFFICIENT_LONG_QUANTITY = "insufficient_long_quantity"
    UNSUPPORTED_FEE_BASIS = "unsupported_fee_basis"
    MISSING_RELATED_FILL = "missing_related_fill"
    BUY_FEE_MISSING_LOT = "buy_fee_missing_lot"
    NON_POSITIVE_FEE_AMOUNT = "non_positive_fee_amount"


@dataclass(frozen=True, slots=True)
class CashAccountingFailure:
    code: CashAccountingFailureCode
    subject_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, CashAccountingFailureCode):
            raise TypeError("code must be CashAccountingFailureCode")
        if (
            not isinstance(self.subject_id, str)
            or not self.subject_id
            or self.subject_id != self.subject_id.strip()
        ):
            raise ValueError("subject_id must be canonical non-empty text")
        canonical_bytes(self.subject_id)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cash_accounting_failure",
            "code": self.code.value,
            "subject_id": self.subject_id,
        }


@dataclass(frozen=True, slots=True)
class CashFillAccountingOutcome:
    result: CashFillAccountingResult | None = None
    failure: CashAccountingFailure | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("CashFillAccountingOutcome requires exactly one result/failure")
        if self.result is not None and not isinstance(self.result, CashFillAccountingResult):
            raise TypeError("result must be CashFillAccountingResult")
        if self.failure is not None and not isinstance(self.failure, CashAccountingFailure):
            raise TypeError("failure must be CashAccountingFailure")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cash_fill_accounting_outcome",
            "result": self.result,
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class FeeChargeAccountingOutcome:
    result: FeeChargeAccountingResult | None = None
    failure: CashAccountingFailure | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("FeeChargeAccountingOutcome requires exactly one result/failure")
        if self.result is not None and not isinstance(self.result, FeeChargeAccountingResult):
            raise TypeError("result must be FeeChargeAccountingResult")
        if self.failure is not None and not isinstance(self.failure, CashAccountingFailure):
            raise TypeError("failure must be CashAccountingFailure")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "fee_charge_accounting_outcome",
            "result": self.result,
            "failure": self.failure,
        }


def _failure(code: CashAccountingFailureCode, subject_id: str) -> CashAccountingFailure:
    return CashAccountingFailure(code, subject_id)


def _lot_order(lot: PositionLot) -> tuple[int, str]:
    return (lot.opened_at.epoch_nanoseconds, lot.lot_id)


def _supports_exact_cost_basis(policy: CostBasisPolicy) -> bool:
    return policy.policy_version >= 2


def _apply_position_lot_changes(
    open_lots: tuple[PositionLot, ...],
    lot_changes: tuple[PositionLotChange, ...],
) -> tuple[PositionLot, ...]:
    working: dict[str, PositionLot] = {lot.lot_id: lot for lot in open_lots}
    for lot_change in lot_changes:
        before = lot_change.before
        after = lot_change.after
        if before is None:
            if after is None:
                raise ValueError("PositionLotChange requires before or after")
            if after.lot_id in working:
                raise ValueError("position lot create conflict")
            working[after.lot_id] = after
        else:
            existing = working.get(before.lot_id)
            if existing is None:
                raise ValueError("position lot before state missing")
            if existing != before:
                raise ValueError("position lot before mismatch")
            if after is None:
                del working[before.lot_id]
            else:
                working[before.lot_id] = after
    return tuple(sorted(working.values(), key=_lot_order))


def _assert_lot_changes_match(
    before_open_lots: tuple[PositionLot, ...],
    after_open_lots: tuple[PositionLot, ...],
    lot_changes: tuple[PositionLotChange, ...],
) -> None:
    if _apply_position_lot_changes(before_open_lots, lot_changes) != after_open_lots:
        raise ValueError("position_lot_changes must reconcile open lot transition")


def _validate_accounting_result(
    journal_entry: AccountingJournalEntry,
    open_lots: tuple[PositionLot, ...],
    policy: CostBasisPolicy,
    expected_entry_type: AccountingEntryType,
) -> None:
    if not isinstance(journal_entry, AccountingJournalEntry):
        raise TypeError("journal_entry must be AccountingJournalEntry")
    _require_lot_tuple(open_lots)
    if tuple(sorted(open_lots, key=_lot_order)) != open_lots:
        raise ValueError("open_lots must use CostBasisPolicy order")
    if len({lot.lot_id for lot in open_lots}) != len(open_lots):
        raise ValueError("duplicate open lot")
    if not isinstance(policy, CostBasisPolicy):
        raise TypeError("cost_basis_policy must be CostBasisPolicy")
    if journal_entry.entry_type is not expected_entry_type:
        raise ValueError(f"accounting result requires {expected_entry_type.value} entry")


def _require_lot_tuple(lots: tuple[PositionLot, ...]) -> None:
    if not isinstance(lots, tuple) or not all(
        isinstance(lot, PositionLot) for lot in lots
    ):
        raise TypeError("open_lots must be a tuple of PositionLot")


def _validate_fee_tuple(fees: tuple[Money, ...]) -> None:
    if not isinstance(fees, tuple) or not all(isinstance(fee, Money) for fee in fees):
        raise TypeError("allocated_fees must be a tuple of Money")
    if any(fee.units == 0 for fee in fees):
        raise ValueError("allocated_fees cannot contain zero")
    if len({fee.currency for fee in fees}) != len(fees):
        raise ValueError("allocated_fees cannot repeat currency")


def _validate_open_lots(
    lots: tuple[PositionLot, ...],
    *,
    position_key: PositionBalanceKey,
    fill: Fill,
    policy_version: int,
    total_cost_basis_scale: Scale | None = None,
) -> tuple[PositionLot, ...] | None:
    try:
        _require_lot_tuple(lots)
    except TypeError:
        return None
    if len({lot.lot_id for lot in lots}) != len(lots):
        return None
    if len({lot.source_id for lot in lots}) != len(lots):
        return None
    if policy_version >= 2 and lots and any(
        lot.total_cost_basis is None for lot in lots
    ):
        return None
    for lot in lots:
        if (
            lot.position_key != position_key
            or lot.quantity.units <= 0
            or lot.quantity.scale != fill.quantity.scale
            or lot.quantity.instrument_id != str(fill.instrument_id)
            or lot.unit_cost is None
            or lot.unit_cost.instrument_id != str(fill.instrument_id)
            or lot.unit_cost.quote_currency != fill.price.quote_currency
            or (policy_version < 2 and lot.total_cost_basis is not None)
            or (
                lot.total_cost_basis is not None
                and total_cost_basis_scale is not None
                and lot.total_cost_basis.scale != total_cost_basis_scale
            )
        ):
            return None
        if any(fee.currency != fill.price.quote_currency for fee in lot.allocated_fees):
            return None
    return tuple(sorted(lots, key=_lot_order))


def _round_ratio(
    numerator: int, denominator: int, rounding: RoundingPolicy
) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    ratio = Fraction(numerator, denominator)
    if rounding is RoundingPolicy.TOWARD_ZERO:
        numerator_value = ratio.numerator
        denominator_value = ratio.denominator
        if numerator_value >= 0:
            return numerator_value // denominator_value
        return -((-numerator_value) // denominator_value)
    if rounding is RoundingPolicy.AWAY_FROM_ZERO:
        return ceil(ratio) if ratio > 0 else floor(ratio)
    if rounding is RoundingPolicy.FLOOR:
        return floor(ratio)
    if rounding is RoundingPolicy.CEILING:
        return ceil(ratio)
    if rounding is RoundingPolicy.HALF_EVEN:
        return round(ratio)
    if rounding is RoundingPolicy.HALF_UP:
        half = Fraction(1, 2)
        return floor(ratio + half) if ratio >= 0 else ceil(ratio - half)
    raise AssertionError(f"Unhandled rounding policy: {rounding}")


def _split_fees(
    fees: tuple[Money, ...],
    *,
    consumed_units: int,
    total_units: int,
    rounding: RoundingPolicy,
) -> tuple[tuple[Money, ...], tuple[Money, ...]]:
    consumed: list[Money] = []
    remaining: list[Money] = []
    for fee in fees:
        consumed_units_for_fee = _round_ratio(
            fee.units * consumed_units, total_units, rounding
        )
        remaining_units_for_fee = fee.units - consumed_units_for_fee
        if consumed_units_for_fee:
            consumed.append(replace(fee, units=consumed_units_for_fee))
        if remaining_units_for_fee:
            remaining.append(replace(fee, units=remaining_units_for_fee))
    return tuple(consumed), tuple(remaining)


def _policy_failure(
    policy: CostBasisPolicy | None, subject_id: str
) -> CashAccountingFailure | None:
    if policy is None:
        return _failure(
            CashAccountingFailureCode.MISSING_COST_BASIS_POLICY, subject_id
        )
    if not isinstance(policy, CostBasisPolicy):
        raise TypeError("cost_basis_policy must be CostBasisPolicy or None")
    if policy.method is not CostBasisMethod.FIFO:
        return _failure(
            CashAccountingFailureCode.UNSUPPORTED_COST_BASIS_METHOD,
            policy.policy_key,
        )
    return None


def _require_journal_context(
    journal_entry_id: DomainId, recorded_at: SimulationInstant
) -> None:
    if not isinstance(journal_entry_id, DomainId) or (
        journal_entry_id.kind is not DomainIdKind.JOURNAL
    ):
        raise ValueError("journal_entry_id must use DomainIdKind.JOURNAL")
    if not isinstance(recorded_at, SimulationInstant):
        raise TypeError("recorded_at must be SimulationInstant")


def _context_matches(
    fill: Fill, cash_key: CashBalanceKey, position_key: PositionBalanceKey
) -> bool:
    return (
        cash_key.account_id == fill.account_id
        and cash_key.venue_id == fill.venue_id
        and str(cash_key.currency_id) == fill.price.quote_currency
        and position_key.account_id == fill.account_id
        and position_key.venue_id == fill.venue_id
        and position_key.instrument_id == fill.instrument_id
    )


def _fill_journal_entry(
    *,
    fill: Fill,
    cash_key: CashBalanceKey,
    position_key: PositionBalanceKey,
    journal_entry_id: DomainId,
    recorded_at: SimulationInstant,
    cash_change: Money,
    position_change: Quantity,
    realized_pnl: Money | None,
    position_lot_changes: tuple[PositionLotChange, ...] = (),
) -> AccountingJournalEntry:
    return AccountingJournalEntry(
        journal_entry_id=journal_entry_id,
        entry_type=AccountingEntryType.FILL_BOOKED,
        account_id=fill.account_id,
        venue_id=fill.venue_id,
        effective_time=fill.execution_time,
        recorded_at=recorded_at,
        source_ids=(str(fill.fill_id), str(fill.order_id)),
        balance_changes=(
            BalanceChange(cash_key, cash_change),
            BalanceChange(position_key, position_change),
        ),
        realized_pnl=(realized_pnl,) if realized_pnl is not None and realized_pnl.units else (),
        fees=(),
        financing=(),
        position_lot_changes=tuple(sorted(position_lot_changes, key=canonical_bytes)),
    )


class CashInstrumentAccounting:
    """Translate supplied cash-instrument facts into immutable Journal entries."""

    def book_fill(
        self,
        *,
        fill: Fill,
        cash_key: CashBalanceKey,
        position_key: PositionBalanceKey,
        open_lots: tuple[PositionLot, ...],
        cost_basis_policy: CostBasisPolicy | None,
        notional_quantization: QuantizationPolicy,
        journal_entry_id: DomainId,
        recorded_at: SimulationInstant,
    ) -> CashFillAccountingOutcome:
        if not isinstance(fill, Fill):
            raise TypeError("fill must be Fill")
        if not isinstance(cash_key, CashBalanceKey):
            raise TypeError("cash_key must be CashBalanceKey")
        if not isinstance(position_key, PositionBalanceKey):
            raise TypeError("position_key must be PositionBalanceKey")
        policy_failure = _policy_failure(cost_basis_policy, str(fill.fill_id))
        if policy_failure is not None:
            return CashFillAccountingOutcome(failure=policy_failure)
        policy = cast(CostBasisPolicy, cost_basis_policy)
        if not isinstance(notional_quantization, QuantizationPolicy):
            raise TypeError("notional_quantization must be QuantizationPolicy")
        _require_journal_context(journal_entry_id, recorded_at)
        if not _context_matches(fill, cash_key, position_key):
            return CashFillAccountingOutcome(
                failure=_failure(
                    CashAccountingFailureCode.CONTEXT_MISMATCH, str(fill.fill_id)
                )
            )
        ordered_lots = _validate_open_lots(
            open_lots,
            position_key=position_key,
            fill=fill,
            policy_version=policy.policy_version,
            total_cost_basis_scale=notional_quantization.target_scale,
        )
        if ordered_lots is None:
            return CashFillAccountingOutcome(
                failure=_failure(
                    CashAccountingFailureCode.INVALID_LOT_STATE, str(fill.fill_id)
                )
            )
        if recorded_at.instant < fill.execution_time:
            return CashFillAccountingOutcome(
                failure=_failure(
                    CashAccountingFailureCode.CONTEXT_MISMATCH, str(fill.fill_id)
                )
            )

        notional = fill.price.notional(
            fill.quantity,
            result_scale=notional_quantization.target_scale,
            rounding=notional_quantization.rounding,
        )
        if fill.side is OrderSide.BUY:
            return self._book_buy(
                fill=fill,
                cash_key=cash_key,
                position_key=position_key,
                open_lots=ordered_lots,
                policy=policy,
                journal_entry_id=journal_entry_id,
                recorded_at=recorded_at,
                notional=notional,
            )
        return self._book_sell(
            fill=fill,
            cash_key=cash_key,
            position_key=position_key,
            open_lots=ordered_lots,
            policy=policy,
            notional_quantization=notional_quantization,
            journal_entry_id=journal_entry_id,
            recorded_at=recorded_at,
            proceeds=notional,
        )

    def _book_buy(
        self,
        *,
        fill: Fill,
        cash_key: CashBalanceKey,
        position_key: PositionBalanceKey,
        open_lots: tuple[PositionLot, ...],
        policy: CostBasisPolicy,
        journal_entry_id: DomainId,
        recorded_at: SimulationInstant,
        notional: Money,
    ) -> CashFillAccountingOutcome:
        lot = PositionLot(
            lot_id=f"lot:{fill.fill_id}",
            position_key=position_key,
            source_id=str(fill.fill_id),
            quantity=fill.quantity,
            unit_cost=fill.price,
            allocated_fees=(),
            opened_at=fill.execution_time,
        )
        if _supports_exact_cost_basis(policy):
            lot = replace(lot, total_cost_basis=notional)
        if any(
            existing.lot_id == lot.lot_id or existing.source_id == lot.source_id
            for existing in open_lots
        ):
            return CashFillAccountingOutcome(
                failure=_failure(
                    CashAccountingFailureCode.INVALID_LOT_STATE, str(fill.fill_id)
                )
            )
        remaining = tuple(sorted((*open_lots, lot), key=_lot_order))
        lot_changes: tuple[PositionLotChange, ...] = ()
        if _supports_exact_cost_basis(policy):
            lot_change = PositionLotChange(before=None, after=lot)
            lot_changes = (lot_change,)
            _assert_lot_changes_match(open_lots, remaining, lot_changes)
        entry = _fill_journal_entry(
            fill=fill,
            cash_key=cash_key,
            position_key=position_key,
            journal_entry_id=journal_entry_id,
            recorded_at=recorded_at,
            cash_change=-notional,
            position_change=fill.quantity,
            realized_pnl=None,
            position_lot_changes=lot_changes,
        )
        return CashFillAccountingOutcome(
            result=CashFillAccountingResult(
                journal_entry=entry,
                open_lots=remaining,
                opened_lot=lot,
                lot_consumptions=(),
                price_cost_basis=None,
                gross_realized_pnl=None,
                cost_basis_policy=policy,
            )
        )

    def _book_sell(
        self,
        *,
        fill: Fill,
        cash_key: CashBalanceKey,
        position_key: PositionBalanceKey,
        open_lots: tuple[PositionLot, ...],
        policy: CostBasisPolicy,
        notional_quantization: QuantizationPolicy,
        journal_entry_id: DomainId,
        recorded_at: SimulationInstant,
        proceeds: Money,
    ) -> CashFillAccountingOutcome:
        available = sum(lot.quantity.units for lot in open_lots)
        if available < fill.quantity.units:
            return CashFillAccountingOutcome(
                failure=_failure(
                    CashAccountingFailureCode.INSUFFICIENT_LONG_QUANTITY,
                    str(fill.fill_id),
                )
            )
        remaining_to_consume = fill.quantity.units
        supports_exact = _supports_exact_cost_basis(policy)
        remaining_lots: list[PositionLot] = []
        lot_changes: list[PositionLotChange] = []
        consumptions: list[LotConsumption] = []
        price_cost_basis = Money(
            0, notional_quantization.target_scale, fill.price.quote_currency
        )
        for lot in open_lots:
            if remaining_to_consume == 0:
                remaining_lots.append(lot)
                continue
            consumed_units = min(remaining_to_consume, lot.quantity.units)
            consumed_quantity = replace(lot.quantity, units=consumed_units)
            unit_cost = cast(Price, lot.unit_cost)
            consumed_fees, residual_fees = _split_fees(
                lot.allocated_fees,
                consumed_units=consumed_units,
                total_units=lot.quantity.units,
                rounding=policy.fee_allocation_rounding,
            )
            consumed_basis: Money | None = None
            residual_basis: Money | None = None
            if supports_exact and lot.total_cost_basis is not None:
                consumed_basis_units = _round_ratio(
                    lot.total_cost_basis.units * consumed_units,
                    lot.quantity.units,
                    notional_quantization.rounding,
                )
                consumed_basis = replace(
                    lot.total_cost_basis, units=consumed_basis_units
                )
                residual_basis = replace(
                    lot.total_cost_basis,
                    units=lot.total_cost_basis.units - consumed_basis_units,
                )

            consumptions.append(
                LotConsumption(
                    lot_id=lot.lot_id,
                    source_fill_id=lot.source_id,
                    quantity=consumed_quantity,
                    unit_cost=unit_cost,
                    allocated_fees=consumed_fees,
                    total_cost_basis=consumed_basis,
                )
            )
            if consumed_basis is not None:
                price_cost_basis += consumed_basis
            else:
                price_cost_basis += unit_cost.notional(
                    consumed_quantity,
                    result_scale=notional_quantization.target_scale,
                    rounding=notional_quantization.rounding,
                )
            residual_units = lot.quantity.units - consumed_units
            if residual_units:
                residual_lot = replace(
                    lot,
                    quantity=replace(lot.quantity, units=residual_units),
                    allocated_fees=residual_fees,
                )
                if supports_exact:
                    residual_lot = replace(
                        residual_lot,
                        total_cost_basis=residual_basis,
                    )
                else:
                    residual_lot = replace(
                        residual_lot,
                        total_cost_basis=None,
                    )
                if supports_exact:
                    lot_changes.append(
                        PositionLotChange(before=lot, after=residual_lot)
                    )
                remaining_lots.append(residual_lot)
            else:
                if supports_exact:
                    lot_changes.append(PositionLotChange(before=lot, after=None))
            remaining_to_consume -= consumed_units
        remaining_lots_tuple = tuple(remaining_lots)
        if supports_exact:
            _assert_lot_changes_match(open_lots, remaining_lots_tuple, tuple(lot_changes))
        gross = proceeds - price_cost_basis
        entry = _fill_journal_entry(
            fill=fill,
            cash_key=cash_key,
            position_key=position_key,
            journal_entry_id=journal_entry_id,
            recorded_at=recorded_at,
            cash_change=proceeds,
            position_change=-fill.quantity,
            realized_pnl=gross,
            position_lot_changes=tuple(lot_changes) if supports_exact else (),
        )
        return CashFillAccountingOutcome(
            result=CashFillAccountingResult(
                journal_entry=entry,
                open_lots=remaining_lots_tuple,
                opened_lot=None,
                lot_consumptions=tuple(consumptions),
                price_cost_basis=price_cost_basis,
                gross_realized_pnl=gross,
                cost_basis_policy=policy,
            )
        )

    def charge_fee(
        self,
        *,
        assessment: FeeAssessment,
        related_fill: Fill | None,
        cash_key: CashBalanceKey,
        open_lots: tuple[PositionLot, ...],
        cost_basis_policy: CostBasisPolicy | None,
        journal_entry_id: DomainId,
        recorded_at: SimulationInstant,
    ) -> FeeChargeAccountingOutcome:
        if not isinstance(assessment, FeeAssessment):
            raise TypeError("assessment must be FeeAssessment")
        policy_failure = _policy_failure(
            cost_basis_policy, str(assessment.fee_assessment_id)
        )
        if policy_failure is not None:
            return FeeChargeAccountingOutcome(failure=policy_failure)
        policy = cast(CostBasisPolicy, cost_basis_policy)
        if not isinstance(cash_key, CashBalanceKey):
            raise TypeError("cash_key must be CashBalanceKey")
        _require_journal_context(journal_entry_id, recorded_at)
        if assessment.basis_type is not FeeBasisType.FILL or len(
            assessment.basis_ids
        ) != 1:
            return FeeChargeAccountingOutcome(
                failure=_failure(
                    CashAccountingFailureCode.UNSUPPORTED_FEE_BASIS,
                    str(assessment.fee_assessment_id),
                )
            )
        if related_fill is None or not isinstance(related_fill, Fill):
            return FeeChargeAccountingOutcome(
                failure=_failure(
                    CashAccountingFailureCode.MISSING_RELATED_FILL,
                    str(assessment.fee_assessment_id),
                )
            )
        if assessment.basis_ids[0] != related_fill.fill_id:
            return FeeChargeAccountingOutcome(
                failure=_failure(
                    CashAccountingFailureCode.MISSING_RELATED_FILL,
                    str(assessment.fee_assessment_id),
                )
            )
        if assessment.amount.units <= 0:
            return FeeChargeAccountingOutcome(
                failure=_failure(
                    CashAccountingFailureCode.NON_POSITIVE_FEE_AMOUNT,
                    str(assessment.fee_assessment_id),
                )
            )
        if (
            cash_key.account_id != related_fill.account_id
            or cash_key.venue_id != related_fill.venue_id
            or str(cash_key.currency_id) != assessment.amount.currency
            or assessment.amount.currency != related_fill.price.quote_currency
            or assessment.assessment_time < related_fill.execution_time
            or recorded_at.instant < assessment.assessment_time
        ):
            return FeeChargeAccountingOutcome(
                failure=_failure(
                    CashAccountingFailureCode.CONTEXT_MISMATCH,
                    str(assessment.fee_assessment_id),
                )
            )
        position_key = PositionBalanceKey(
            related_fill.account_id,
            related_fill.venue_id,
            related_fill.instrument_id,
        )
        ordered_lots = _validate_open_lots(
            open_lots,
            position_key=position_key,
            fill=related_fill,
            policy_version=policy.policy_version,
        )
        if ordered_lots is None:
            return FeeChargeAccountingOutcome(
                failure=_failure(
                    CashAccountingFailureCode.INVALID_LOT_STATE,
                    str(assessment.fee_assessment_id),
                )
            )

        lot_change: PositionLotChange | None = None
        allocated_lot_id: str | None = None
        supports_exact = _supports_exact_cost_basis(policy)
        if related_fill.side is OrderSide.BUY:
            matching = [
                lot for lot in ordered_lots if lot.source_id == str(related_fill.fill_id)
            ]
            if len(matching) != 1:
                return FeeChargeAccountingOutcome(
                    failure=_failure(
                        CashAccountingFailureCode.BUY_FEE_MISSING_LOT,
                        str(assessment.fee_assessment_id),
                    )
                )
            target = matching[0]
            if (
                target.position_key.account_id != related_fill.account_id
                or target.position_key.venue_id != related_fill.venue_id
                or target.position_key.instrument_id != related_fill.instrument_id
            ):
                return FeeChargeAccountingOutcome(
                    failure=_failure(
                        CashAccountingFailureCode.INVALID_LOT_STATE,
                        str(assessment.fee_assessment_id),
                    )
                )
            updated_fees: list[Money] = []
            found_currency = False
            for fee in target.allocated_fees:
                if fee.currency == assessment.amount.currency:
                    if fee.scale != assessment.amount.scale:
                        return FeeChargeAccountingOutcome(
                            failure=_failure(
                                CashAccountingFailureCode.CONTEXT_MISMATCH,
                                str(assessment.fee_assessment_id),
                            )
                        )
                    updated_fees.append(fee + assessment.amount)
                    found_currency = True
                else:
                    updated_fees.append(fee)
            if not found_currency:
                updated_fees.append(assessment.amount)
            updated_target = replace(
                target,
                allocated_fees=tuple(
                    sorted(updated_fees, key=lambda value: value.currency)
                ),
            )
            if supports_exact:
                lot_change = PositionLotChange(before=target, after=updated_target)
                ordered_lots = tuple(
                    updated_target if lot.lot_id == target.lot_id else lot
                    for lot in ordered_lots
                )
                _assert_lot_changes_match(open_lots, ordered_lots, (lot_change,))
            else:
                ordered_lots = tuple(
                    updated_target if lot.lot_id == target.lot_id else lot
                    for lot in ordered_lots
                )
            allocated_lot_id = target.lot_id

        source_ids = {
            str(assessment.fee_assessment_id),
            str(assessment.basis_ids[0]),
        }
        source_ids.update(
            value
            for value in (
                assessment.market_fee_rule_id,
                assessment.account_fee_schedule_id,
                assessment.tax_rule_id,
            )
            if value is not None
        )
        entry = AccountingJournalEntry(
            journal_entry_id=journal_entry_id,
            entry_type=AccountingEntryType.FEE_CHARGED,
            account_id=related_fill.account_id,
            venue_id=related_fill.venue_id,
            effective_time=assessment.assessment_time,
            recorded_at=recorded_at,
            source_ids=tuple(sorted(source_ids)),
            balance_changes=(BalanceChange(cash_key, -assessment.amount),),
            realized_pnl=(),
            fees=(assessment.amount,),
            financing=(),
            position_lot_changes=() if lot_change is None else (lot_change,),
        )
        return FeeChargeAccountingOutcome(
            result=FeeChargeAccountingResult(
                journal_entry=entry,
                open_lots=ordered_lots,
                allocated_lot_id=allocated_lot_id,
                cost_basis_policy=policy,
            )
        )
