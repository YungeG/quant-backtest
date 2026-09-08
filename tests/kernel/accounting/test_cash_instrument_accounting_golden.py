from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_domain import (
    DomainIdKind,
    Fill,
    OrderSide,
    PositionLot,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    CashFillAccountingResult,
    CashInstrumentAccounting,
    FeeChargeAccountingResult,
)

from ._fixtures import (
    CASH_KEY,
    COST_BASIS_POLICY,
    COST_BASIS_POLICY_V2,
    NOTIONAL_POLICY,
    POSITION_KEY,
    domain_id,
    fee_assessment,
    fill,
    recorded_at,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "tests/fixtures/kernel/cash-instrument-accounting-v1.json"
FIXTURE_PATH_V2 = ROOT / "tests/fixtures/kernel/cash-instrument-accounting-v2.json"
ACCOUNTING = CashInstrumentAccounting()


def book(
    value: Fill,
    lots: tuple[PositionLot, ...],
    journal_digit: str,
    recorded: int,
    *,
    policy=COST_BASIS_POLICY,
):
    return ACCOUNTING.book_fill(
        fill=value,
        cash_key=CASH_KEY,
        position_key=POSITION_KEY,
        open_lots=lots,
        cost_basis_policy=policy,
        notional_quantization=NOTIONAL_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, journal_digit),
        recorded_at=recorded_at(recorded),
    )


def _cash_fill_gross_realized_units(
    value: CashFillAccountingResult | FeeChargeAccountingResult,
) -> int | None:
    if isinstance(value, CashFillAccountingResult):
        return (
            value.gross_realized_pnl.units
            if value.gross_realized_pnl is not None
            else None
        )
    return None


def _cash_fill_price_cost_basis_units(
    value: CashFillAccountingResult | FeeChargeAccountingResult,
) -> int | None:
    if isinstance(value, CashFillAccountingResult):
        return (
            value.price_cost_basis.units
            if value.price_cost_basis is not None
            else None
        )
    return None


def _cash_fill_consumed_source_fills(
    value: CashFillAccountingResult | FeeChargeAccountingResult,
) -> list[str]:
    if isinstance(value, CashFillAccountingResult):
        return [item.source_fill_id for item in value.lot_consumptions]
    return []



def _expected_payload(values, policy, fixture_id: str):
    payload = {
        "fixture_id": fixture_id,
        "cost_basis_policy": json.loads(canonical_bytes(policy)),
        "cost_basis_policy_hash": policy.policy_hash,
        "result_hashes": [canonical_sha256(value) for value in values],
        "journal_entry_hashes": [canonical_sha256(value.journal_entry) for value in values],
        "open_lot_hashes_after_each_step": [
            [canonical_sha256(lot) for lot in value.open_lots] for value in values
        ],
        "gross_realized_pnl_units": [
            _cash_fill_gross_realized_units(value) for value in values
        ],
        "price_cost_basis_units": [
            _cash_fill_price_cost_basis_units(value) for value in values
        ],
        "fee_attribution_units": [
            sum(fee.units for fee in value.journal_entry.fees) for value in values
        ],
        "consumed_source_fills": [
            _cash_fill_consumed_source_fills(value) for value in values
        ],
        "final_open_lots": json.loads(canonical_bytes(values[-1].open_lots)),
    }
    if getattr(policy, "policy_version", 1) >= 2:
        payload.update(
            {
                "position_lot_change_hashes": [
                    [
                        canonical_sha256(change)
                        for change in value.journal_entry.position_lot_changes
                    ]
                    for value in values
                ],
                "position_lot_change_counts": [
                    len(value.journal_entry.position_lot_changes) for value in values
                ],
            }
        )
    return payload


def _build_sequence(policy):
    buy_one = fill("1", side=OrderSide.BUY, quantity_units=20, price_units=10_000, execution_time=10)
    bought_one = book(
        buy_one,
        (),
        "1",
        11,
        policy=policy,
    ).result
    assert bought_one is not None

    buy_fee_assessment = fee_assessment("4", buy_one, amount_units=100, assessment_time=12)
    buy_fee = ACCOUNTING.charge_fee(
        assessment=buy_fee_assessment,
        related_fill=buy_one,
        cash_key=CASH_KEY,
        open_lots=bought_one.open_lots,
        cost_basis_policy=policy,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "4"),
        recorded_at=recorded_at(13),
    ).result
    assert buy_fee is not None

    buy_two = fill("2", side=OrderSide.BUY, quantity_units=10, price_units=12_000, execution_time=20)
    bought_two = book(
        buy_two,
        buy_fee.open_lots,
        "2",
        21,
        policy=policy,
    ).result
    assert bought_two is not None

    sell_one = fill(
        "3", side=OrderSide.SELL, quantity_units=10, price_units=13_000, execution_time=30
    )
    sold_one = book(
        sell_one,
        bought_two.open_lots,
        "3",
        31,
        policy=policy,
    ).result
    assert sold_one is not None

    sell_fee_assessment = fee_assessment("5", sell_one, amount_units=150, assessment_time=32)
    sell_fee = ACCOUNTING.charge_fee(
        assessment=sell_fee_assessment,
        related_fill=sell_one,
        cash_key=CASH_KEY,
        open_lots=sold_one.open_lots,
        cost_basis_policy=policy,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "5"),
        recorded_at=recorded_at(33),
    ).result
    assert sell_fee is not None

    sell_two = fill(
        "6", side=OrderSide.SELL, quantity_units=20, price_units=14_000, execution_time=40
    )
    sold_two = book(
        sell_two,
        sell_fee.open_lots,
        "6",
        41,
        policy=policy,
    ).result
    assert sold_two is not None

    return (bought_one, buy_fee, bought_two, sold_one, sell_fee, sold_two)


def test_cash_instrument_accounting_matches_frozen_golden() -> None:
    try:
        expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid frozen cash-accounting fixture: {error}")

    values = _build_sequence(COST_BASIS_POLICY)
    actual = _expected_payload(values, COST_BASIS_POLICY, "cash-instrument-accounting-v1")
    assert actual == expected


def test_cash_instrument_accounting_v2_matches_frozen_golden() -> None:
    try:
        expected = json.loads(FIXTURE_PATH_V2.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid frozen cash-accounting v2 fixture: {error}")

    values = _build_sequence(COST_BASIS_POLICY_V2)
    actual = _expected_payload(values, COST_BASIS_POLICY_V2, "cash-instrument-accounting-v2")
    assert actual == expected
