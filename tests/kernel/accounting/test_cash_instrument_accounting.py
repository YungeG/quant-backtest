from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import Any, cast

import pytest

from crypto_quant_domain import (
    AccountingEntryType,
    FeeBasisType,
    Money,
    OrderSide,
    PositionLot,
    PositionLotChange,
    Quantity,
    RoundingPolicy,
    Scale,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import (
    CashAccountingFailureCode,
    CashInstrumentAccounting,
    CostBasisMethod,
    CostBasisPolicy,
)

from ._fixtures import (
    CASH_KEY,
    COST_BASIS_POLICY,
    COST_BASIS_POLICY_V2,
    MONEY_SCALE,
    NOTIONAL_POLICY,
    POSITION_KEY,
    QUANTITY_SCALE,
    USD,
    domain_id,
    fee_assessment,
    fill,
    recorded_at,
)
from crypto_quant_domain import DomainIdKind


ACCOUNTING = CashInstrumentAccounting()


def book_fill(
    value: Any,
    lots: tuple[PositionLot, ...] = (),
    *,
    policy: CostBasisPolicy = COST_BASIS_POLICY,
    notional_quantization=NOTIONAL_POLICY,
) -> Any:
    return ACCOUNTING.book_fill(
        fill=value,
        cash_key=CASH_KEY,
        position_key=POSITION_KEY,
        open_lots=lots,
        cost_basis_policy=policy,
        notional_quantization=notional_quantization,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, value.fill_id.value[4]),
        recorded_at=recorded_at(value.execution_time.epoch_nanoseconds + 1),
    )


def test_cost_basis_policy_is_explicit_versioned_and_immutable() -> None:
    assert COST_BASIS_POLICY.method is CostBasisMethod.FIFO
    assert COST_BASIS_POLICY.policy_hash == canonical_sha256(COST_BASIS_POLICY)

    with pytest.raises(FrozenInstanceError):
        cast(Any, COST_BASIS_POLICY).policy_version = 2
    with pytest.raises(ValueError, match="policy_key"):
        replace(COST_BASIS_POLICY, policy_key=" fifo ")
    with pytest.raises(ValueError, match="positive"):
        replace(COST_BASIS_POLICY, policy_version=0)

    buy = fill(
        "1", side=OrderSide.BUY, quantity_units=20, price_units=10_000, execution_time=10
    )
    blocked = ACCOUNTING.book_fill(
        fill=buy,
        cash_key=CASH_KEY,
        position_key=POSITION_KEY,
        open_lots=(),
        cost_basis_policy=None,
        notional_quantization=NOTIONAL_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "1"),
        recorded_at=recorded_at(11),
    )
    assert blocked.result is None
    assert blocked.failure is not None
    assert blocked.failure.code is CashAccountingFailureCode.MISSING_COST_BASIS_POLICY


def test_buy_books_balanced_cash_position_and_source_fill_lot() -> None:
    buy = fill(
        "1", side=OrderSide.BUY, quantity_units=20, price_units=10_000, execution_time=10
    )
    outcome = book_fill(buy)

    assert outcome.failure is None
    result = outcome.result
    assert result is not None
    assert result.journal_entry.entry_type is AccountingEntryType.FILL_BOOKED
    assert result.journal_entry.source_ids == (str(buy.fill_id), str(buy.order_id))
    assert result.journal_entry.balance_changes[0].value == Money(
        -20_000, MONEY_SCALE, str(USD)
    )
    assert result.journal_entry.balance_changes[1].value == buy.quantity
    assert result.gross_realized_pnl is None
    assert result.price_cost_basis is None
    assert len(result.open_lots) == 1
    lot = result.open_lots[0]
    assert lot.lot_id == f"lot:{buy.fill_id}"
    assert lot.source_id == str(buy.fill_id)
    assert lot.quantity == buy.quantity
    assert lot.unit_cost == buy.price
    assert lot.allocated_fees == ()
    assert lot.total_cost_basis is None
    assert result.journal_entry.position_lot_changes == ()


def test_add_and_partial_sell_use_fifo_independent_of_input_order() -> None:
    buy_one = fill(
        "1", side=OrderSide.BUY, quantity_units=20, price_units=10_000, execution_time=10
    )
    buy_two = fill(
        "2", side=OrderSide.BUY, quantity_units=10, price_units=12_000, execution_time=20
    )
    first = book_fill(buy_one).result
    assert first is not None
    second = book_fill(buy_two, first.open_lots).result
    assert second is not None

    sell = fill(
        "3", side=OrderSide.SELL, quantity_units=25, price_units=13_000, execution_time=30
    )
    forward = book_fill(sell, second.open_lots)
    reverse = book_fill(sell, tuple(reversed(second.open_lots)))

    assert forward == reverse
    result = forward.result
    assert result is not None
    assert [item.source_fill_id for item in result.lot_consumptions] == [
        str(buy_one.fill_id),
        str(buy_two.fill_id),
    ]
    assert [item.quantity.units for item in result.lot_consumptions] == [20, 5]
    assert [item.total_cost_basis for item in result.lot_consumptions] == [None, None]
    assert result.price_cost_basis == Money(26_000, MONEY_SCALE, str(USD))
    assert result.gross_realized_pnl == Money(6_500, MONEY_SCALE, str(USD))
    assert result.journal_entry.position_lot_changes == ()
    assert len(result.open_lots) == 1
    assert result.open_lots[0].source_id == str(buy_two.fill_id)
    assert result.open_lots[0].quantity.units == 5
    assert result.open_lots[0].total_cost_basis is None


def test_full_sell_closes_all_lots_and_zero_gross_pnl_is_not_attributed() -> None:
    buy = fill(
        "1", side=OrderSide.BUY, quantity_units=20, price_units=10_000, execution_time=10
    )
    bought = book_fill(buy).result
    assert bought is not None
    sell = fill(
        "2", side=OrderSide.SELL, quantity_units=20, price_units=10_000, execution_time=20
    )
    sold = book_fill(sell, bought.open_lots).result

    assert sold is not None
    assert sold.open_lots == ()
    assert sold.gross_realized_pnl == Money(0, MONEY_SCALE, str(USD))
    assert sold.journal_entry.realized_pnl == ()
    assert sold.journal_entry.position_lot_changes == ()


def test_sell_beyond_long_lots_fails_without_implicit_short() -> None:
    buy = fill(
        "1", side=OrderSide.BUY, quantity_units=10, price_units=10_000, execution_time=10
    )
    bought = book_fill(buy).result
    assert bought is not None
    sell = fill(
        "2", side=OrderSide.SELL, quantity_units=11, price_units=11_000, execution_time=20
    )

    outcome = book_fill(sell, bought.open_lots)

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is CashAccountingFailureCode.INSUFFICIENT_LONG_QUANTITY
    assert outcome.failure.subject_id == str(sell.fill_id)
    assert bought.open_lots[0].quantity.units == 10


def test_fill_fee_is_charged_once_and_buy_fee_updates_lot_provenance() -> None:
    buy = fill(
        "1", side=OrderSide.BUY, quantity_units=20, price_units=10_000, execution_time=10
    )
    bought = book_fill(buy).result
    assert bought is not None
    assessment = fee_assessment("4", buy, amount_units=100, assessment_time=12)

    outcome = ACCOUNTING.charge_fee(
        assessment=assessment,
        related_fill=buy,
        cash_key=CASH_KEY,
        open_lots=bought.open_lots,
        cost_basis_policy=COST_BASIS_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "4"),
        recorded_at=recorded_at(13),
    )

    assert outcome.failure is None
    result = outcome.result
    assert result is not None
    assert result.journal_entry.entry_type is AccountingEntryType.FEE_CHARGED
    assert result.journal_entry.balance_changes[0].value == Money(
        -100, MONEY_SCALE, str(USD)
    )
    assert result.journal_entry.fees == (assessment.amount,)
    assert set(result.journal_entry.source_ids) == {
        str(assessment.fee_assessment_id),
        str(buy.fill_id),
        "market-fee.synthetic.v1",
        "account-fee.primary.v1",
    }
    assert result.allocated_lot_id == f"lot:{buy.fill_id}"
    assert result.open_lots[0].allocated_fees == (assessment.amount,)
    assert result.open_lots[0].total_cost_basis is None
    assert result.journal_entry.position_lot_changes == ()


def test_partial_consumption_splits_allocated_fee_exactly() -> None:
    buy = fill(
        "1", side=OrderSide.BUY, quantity_units=20, price_units=10_000, execution_time=10
    )
    bought = book_fill(buy).result
    assert bought is not None
    fee = ACCOUNTING.charge_fee(
        assessment=fee_assessment("4", buy, amount_units=101, assessment_time=12),
        related_fill=buy,
        cash_key=CASH_KEY,
        open_lots=bought.open_lots,
        cost_basis_policy=COST_BASIS_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "4"),
        recorded_at=recorded_at(13),
    ).result
    assert fee is not None

    sell = fill(
        "2", side=OrderSide.SELL, quantity_units=10, price_units=11_000, execution_time=20
    )
    sold = book_fill(sell, fee.open_lots).result

    assert sold is not None
    assert sold.lot_consumptions[0].allocated_fees == (
        Money(50, MONEY_SCALE, str(USD)),
    )
    assert sold.open_lots[0].allocated_fees == (
        Money(51, MONEY_SCALE, str(USD)),
    )
    assert (
        sold.lot_consumptions[0].allocated_fees[0]
        + sold.open_lots[0].allocated_fees[0]
        == Money(101, MONEY_SCALE, str(USD))
    )


def test_v2_buy_records_exact_cost_basis_and_lot_change() -> None:
    buy = fill(
        "1", side=OrderSide.BUY, quantity_units=20, price_units=10_000, execution_time=10
    )
    result = book_fill(buy, policy=COST_BASIS_POLICY_V2).result
    assert result is not None

    lot = result.open_lots[0]
    assert lot.total_cost_basis == Money(20_000, MONEY_SCALE, str(USD))
    assert result.journal_entry.position_lot_changes == (
        PositionLotChange(before=None, after=lot),
    )
    assert result.journal_entry.position_lot_changes[0].after is not None


def test_v2_rejects_mixed_legacy_and_exact_lot_state() -> None:
    exact_buy = fill(
        "1", side=OrderSide.BUY, quantity_units=10, price_units=12_000, execution_time=10
    )
    exact_outcome = book_fill(exact_buy, policy=COST_BASIS_POLICY_V2).result
    assert exact_outcome is not None
    exact_lot = exact_outcome.open_lots[0]
    legacy_lot = PositionLot(
        lot_id="lot:legacy",
        position_key=POSITION_KEY,
        source_id="legacy:fill",
        quantity=Quantity(5, QUANTITY_SCALE, exact_lot.quantity.instrument_id),
        unit_cost=exact_lot.unit_cost,
        allocated_fees=(),
        opened_at=UtcInstant(5),
        total_cost_basis=None,
    )
    sell = fill(
        "2", side=OrderSide.SELL, quantity_units=8, price_units=11_000, execution_time=20
    )

    outcome = book_fill(
        sell,
        (legacy_lot, exact_lot),
        policy=COST_BASIS_POLICY_V2,
    )

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is CashAccountingFailureCode.INVALID_LOT_STATE


def test_v2_buy_fee_preserves_exact_basis_and_records_lot_change() -> None:
    buy = fill(
        "1", side=OrderSide.BUY, quantity_units=20, price_units=10_000, execution_time=10
    )
    bought = book_fill(buy, policy=COST_BASIS_POLICY_V2).result
    assert bought is not None

    assessment = fee_assessment("4", buy, amount_units=100, assessment_time=12)
    outcome = ACCOUNTING.charge_fee(
        assessment=assessment,
        related_fill=buy,
        cash_key=CASH_KEY,
        open_lots=bought.open_lots,
        cost_basis_policy=COST_BASIS_POLICY_V2,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "4"),
        recorded_at=recorded_at(13),
    )
    assert outcome.result is not None
    result = outcome.result
    assert result.open_lots[0].total_cost_basis == Money(20_000, MONEY_SCALE, str(USD))
    assert len(result.journal_entry.position_lot_changes) == 1
    change = result.journal_entry.position_lot_changes[0]
    assert change.before is not None
    assert change.after is not None
    assert change.before.total_cost_basis == Money(20_000, MONEY_SCALE, str(USD))
    assert change.after.total_cost_basis == Money(20_000, MONEY_SCALE, str(USD))


def test_v1_rejects_open_lot_with_exact_cost_basis() -> None:
    buy = fill(
        "1", side=OrderSide.BUY, quantity_units=10, price_units=10_000, execution_time=10
    )
    exact = book_fill(buy, policy=COST_BASIS_POLICY_V2).result
    assert exact is not None

    sell = fill(
        "2", side=OrderSide.SELL, quantity_units=5, price_units=11_000, execution_time=20
    )
    outcome = book_fill(sell, (exact.open_lots[0],))

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is CashAccountingFailureCode.INVALID_LOT_STATE


def test_v2_rejects_exact_basis_scale_mismatch() -> None:
    buy = fill(
        "1", side=OrderSide.BUY, quantity_units=10, price_units=10_000, execution_time=10
    )
    exact = book_fill(buy, policy=COST_BASIS_POLICY_V2).result
    assert exact is not None
    sell = fill(
        "2", side=OrderSide.SELL, quantity_units=5, price_units=11_000, execution_time=20
    )

    outcome = book_fill(
        sell,
        exact.open_lots,
        policy=COST_BASIS_POLICY_V2,
        notional_quantization=replace(NOTIONAL_POLICY, target_scale=Scale(3)),
    )

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is CashAccountingFailureCode.INVALID_LOT_STATE


def test_v2_exact_basis_split_allows_zero_consumed_basis() -> None:
    sell = fill(
        "2", side=OrderSide.SELL, quantity_units=1, price_units=10_000, execution_time=20
    )
    exact_lot = PositionLot(
        lot_id="lot:zero-rounding",
        position_key=POSITION_KEY,
        source_id="zero-rounding",
        quantity=Quantity(3, QUANTITY_SCALE, str(sell.instrument_id)),
        unit_cost=sell.price,
        allocated_fees=(),
        opened_at=UtcInstant(10),
        total_cost_basis=Money(1, MONEY_SCALE, str(USD)),
    )

    sold = book_fill(
        sell,
        (exact_lot,),
        policy=COST_BASIS_POLICY_V2,
        notional_quantization=replace(
            NOTIONAL_POLICY,
            rounding=RoundingPolicy.FLOOR,
        ),
    ).result

    assert sold is not None
    zero_basis = Money(0, MONEY_SCALE, str(USD))
    consumption = sold.lot_consumptions[0]
    assert consumption.total_cost_basis == zero_basis
    assert consumption.to_canonical_dict()["schema_version"] == 2
    assert consumption.to_canonical_dict()["total_cost_basis"] == zero_basis
    assert sold.open_lots[0].total_cost_basis == Money(1, MONEY_SCALE, str(USD))


def test_v2_exact_basis_split_uses_notional_rounding_for_cost_basis_not_fee_rounding() -> None:
    sell = fill(
        "2", side=OrderSide.SELL, quantity_units=1, price_units=10_000, execution_time=20
    )
    exact_lot = PositionLot(
        lot_id="lot:rounding",
        position_key=POSITION_KEY,
        source_id="rounding",
        quantity=Quantity(2, QUANTITY_SCALE, str(sell.instrument_id)),
        unit_cost=sell.price,
        allocated_fees=(),
        opened_at=UtcInstant(10),
        total_cost_basis=Money(11, MONEY_SCALE, str(USD)),
    )
    policy = replace(
        COST_BASIS_POLICY_V2,
        fee_allocation_rounding=RoundingPolicy.FLOOR,
    )

    outcome = ACCOUNTING.book_fill(
        fill=sell,
        cash_key=CASH_KEY,
        position_key=POSITION_KEY,
        open_lots=(exact_lot,),
        cost_basis_policy=policy,
        notional_quantization=NOTIONAL_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "2"),
        recorded_at=recorded_at(21),
    )
    sold = outcome.result
    assert sold is not None

    assert sold.lot_consumptions[0].total_cost_basis == Money(6, MONEY_SCALE, str(USD))
    assert sold.open_lots[0].total_cost_basis == Money(5, MONEY_SCALE, str(USD))


def test_invalid_context_and_unsupported_fee_basis_fail_closed() -> None:
    buy = fill(
        "1", side=OrderSide.BUY, quantity_units=20, price_units=10_000, execution_time=10
    )
    wrong_cash = replace(CASH_KEY, account_id="account:other")
    mismatch = ACCOUNTING.book_fill(
        fill=buy,
        cash_key=wrong_cash,
        position_key=POSITION_KEY,
        open_lots=(),
        cost_basis_policy=COST_BASIS_POLICY,
        notional_quantization=NOTIONAL_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "1"),
        recorded_at=recorded_at(11),
    )
    assert mismatch.failure is not None
    assert mismatch.failure.code is CashAccountingFailureCode.CONTEXT_MISMATCH

    assessment = replace(
        fee_assessment("4", buy, amount_units=100, assessment_time=12),
        basis_type=FeeBasisType.ORDER,
        basis_ids=(buy.order_id,),
    )
    unsupported = ACCOUNTING.charge_fee(
        assessment=assessment,
        related_fill=buy,
        cash_key=CASH_KEY,
        open_lots=(),
        cost_basis_policy=COST_BASIS_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "4"),
        recorded_at=recorded_at(13),
    )
    assert unsupported.failure is not None
    assert unsupported.failure.code is CashAccountingFailureCode.UNSUPPORTED_FEE_BASIS

    with pytest.raises(ValueError, match="method"):
        cast(Any, CostBasisPolicy)(
            policy_key="cash-cost-basis.invalid.v1",
            policy_version=1,
            method="fifo",
            fee_allocation_rounding=RoundingPolicy.HALF_EVEN,
        )
    zero_fee = replace(
        fee_assessment("4", buy, amount_units=100, assessment_time=12),
        amount=Money(0, Scale(2), str(USD)),
    )
    zero = ACCOUNTING.charge_fee(
        assessment=zero_fee,
        related_fill=buy,
        cash_key=CASH_KEY,
        open_lots=(),
        cost_basis_policy=COST_BASIS_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "4"),
        recorded_at=recorded_at(13),
    )
    assert zero.failure is not None
    assert zero.failure.code is CashAccountingFailureCode.NON_POSITIVE_FEE_AMOUNT

    early_assessment = fee_assessment(
        "5", buy, amount_units=100, assessment_time=9
    )
    early = ACCOUNTING.charge_fee(
        assessment=early_assessment,
        related_fill=buy,
        cash_key=CASH_KEY,
        open_lots=(),
        cost_basis_policy=COST_BASIS_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "5"),
        recorded_at=recorded_at(13),
    )
    assert early.failure is not None
    assert early.failure.code is CashAccountingFailureCode.CONTEXT_MISMATCH
