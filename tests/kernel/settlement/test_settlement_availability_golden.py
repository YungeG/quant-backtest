from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_domain import canonical_sha256
from crypto_quant_trading import AvailabilityProjection

from ._fixtures import ledger_state, market_rules, reservation_state, settlement_book


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "tests/fixtures/kernel/settlement-availability-replay-v1.json"


def actual_fixture() -> dict[str, object]:
    book = settlement_book()
    recorded = book.project(stop=book.cursor_at(3))
    position_applied = book.project(stop=book.cursor_at(4))
    cash_applied = book.project(stop=book.cursor_at(5))
    final = book.resume(position_applied)
    rules = market_rules()
    projection = AvailabilityProjection()
    before_cash_settlement = projection.project(
        ledger_state(), position_applied, reservation_state(), rules
    )
    after_cash_settlement = projection.project(
        ledger_state(), cash_applied, reservation_state(), rules
    )
    return {
        "fixture_id": "settlement-availability-replay-v1",
        "book_hash": book.book_hash,
        "recorded_state_hash": recorded.state_hash,
        "position_applied_state_hash": position_applied.state_hash,
        "final_state_hash": final.state_hash,
        "rules_hash": rules.rules_hash,
        "before_cash_settlement_hash": before_cash_settlement.state_hash,
        "after_cash_settlement_hash": after_cash_settlement.state_hash,
        "pending_after_position_apply": [
            item.obligation.settlement_obligation_id.value
            for item in position_applied.pending_obligations
        ],
        "applied_final": [
            item.obligation.settlement_obligation_id.value
            for item in final.applied_obligations
        ],
        "before_cash_units": {
            "total": before_cash_settlement.cash[0].total.units,
            "settled": before_cash_settlement.cash[0].settled.units,
            "tradable": before_cash_settlement.cash[0].tradable.units,
            "withdrawable": before_cash_settlement.cash[0].withdrawable.units,
            "available_margin": before_cash_settlement.cash[0].available_margin.units,
        },
        "before_position_units": {
            "total": before_cash_settlement.positions[0].total.units,
            "sellable": before_cash_settlement.positions[0].sellable.units,
        },
        "after_cash_units": {
            "settled": after_cash_settlement.cash[0].settled.units,
            "tradable": after_cash_settlement.cash[0].tradable.units,
            "withdrawable": after_cash_settlement.cash[0].withdrawable.units,
        },
        "canonical_final_hash": canonical_sha256(final),
    }


def test_settlement_availability_replay_matches_the_frozen_golden() -> None:
    try:
        expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid frozen Settlement/Availability fixture: {error}")

    assert actual_fixture() == expected
