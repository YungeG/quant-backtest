from __future__ import annotations

from dataclasses import replace
from typing import cast

from crypto_quant_backtest import CashFillAccountingPlan, FillAccountingDispatchPlan
from crypto_quant_domain import PositionBalanceKey, PositionLot, canonical_bytes

from tests.kernel.accounting._fixtures import (
    CASH_KEY,
    COST_BASIS_POLICY_V2,
    POSITION_KEY,
)
from tests.runtime.engine._fixtures import (
    CashAccountingSemanticPayload,
    cash_accounting_plan,
)


def v2_cash_plan() -> FillAccountingDispatchPlan:
    plan = cash_accounting_plan()
    position_payload = replace(
        cast(CashFillAccountingPlan, plan.position_payload),
        cash_key=CASH_KEY,
        position_key=POSITION_KEY,
        cost_basis_policy=COST_BASIS_POLICY_V2,
    )
    semantic_payload = replace(
        cast(CashAccountingSemanticPayload, plan.semantic_payload),
        cash_key=CASH_KEY,
        position_key=POSITION_KEY,
        cost_basis_policy=COST_BASIS_POLICY_V2,
    )
    return replace(
        plan,
        position_payload=position_payload,
        semantic_payload=semantic_payload,
        fee_plan=replace(plan.fee_plan, cash_key=CASH_KEY),
    )


def lot_books_from_ledger(
    ledger_state,
) -> tuple[tuple[PositionBalanceKey, tuple[PositionLot, ...]], ...]:
    return tuple(
        sorted(
            (
                (position.key, position.lots)
                for position in ledger_state.position_balances
                if position.lots
            ),
            key=lambda value: canonical_bytes(value[0]),
        )
    )
