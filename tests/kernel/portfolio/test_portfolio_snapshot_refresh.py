from __future__ import annotations

from crypto_quant_domain import PricePurpose
from crypto_quant_trading import (
    CurrencyValuationGraph,
    PortfolioSnapshotRefreshInputV1,
    PortfolioSnapshotRefresherV1,
    PortfolioSnapshotRefreshPolicyV1,
    ResourceReservationBook,
    SettlementBook,
)

from tests.runtime.engine._fixtures import ACCOUNT, final_valuation_mark, run_result, snapshot_plan


def test_refresher_derives_current_snapshot_from_ledger_lots_and_marks() -> None:
    result = run_result()
    accounting = next(
        artifact.payload
        for artifact in result.financial_artifacts
        if artifact.role == "position_accounting"
    )
    position = result.final_ledger_state.position_balances[0]
    plan = snapshot_plan()
    graph = CurrencyValuationGraph(
        valuation_at=plan.timestamp,
        price_purpose=PricePurpose.VALUATION,
        edges=(),
    )
    refresh_input = PortfolioSnapshotRefreshInputV1(
        ledger_state=result.final_ledger_state,
        position_lot_books=((position.key, accounting.open_lots),),
        settlement_state=SettlementBook(ACCOUNT).project(),
        reservation_state=ResourceReservationBook(ACCOUNT).project((), ()),
        working_orders=(),
        resolved_marks=(final_valuation_mark(),),
        currency_valuation_graph=graph,
        reporting_currency=plan.reporting_currency,
        quantization_policy=next(
            value.quantization_policy
            for value in plan.valuations
            if value.quantization_policy is not None
        ),
        timestamp=plan.timestamp,
    )

    snapshot = PortfolioSnapshotRefresherV1(
        PortfolioSnapshotRefreshPolicyV1(
            policy_key="equity.cn_a_share.portfolio.snapshot-refresh.v1",
            policy_version=1,
            price_purpose=PricePurpose.VALUATION,
        )
    ).refresh(refresh_input)

    assert snapshot == result.final_portfolio_snapshot
    assert refresh_input.lot_book_hash
    assert refresh_input.working_order_set_hash
    assert refresh_input.decision_mark_set_hash
