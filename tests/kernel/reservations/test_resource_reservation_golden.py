from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_domain import OrderSide, canonical_sha256
from crypto_quant_trading import ResourceReservationBook

from ._fixtures import ACCOUNT, schedule, stream, subject_order


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "tests/fixtures/kernel/resource-reservation-replay-v1.json"


def test_resource_reservation_replay_matches_the_frozen_golden() -> None:
    try:
        expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid frozen Resource Reservation fixture: {error}")

    buy = subject_order("1")
    sell = subject_order("9", side=OrderSide.SELL)
    schedules = (schedule(buy), schedule(sell, sell=True))
    book = ResourceReservationBook(ACCOUNT)

    accepted = book.project((stream(buy, 8), stream(sell, 8)), schedules)
    partial = book.project((stream(buy, 10), stream(sell, 10)), schedules)
    final = book.resume(
        partial,
        (stream(buy, 11), stream(sell, 11)),
        tuple(reversed(schedules)),
    )

    actual = {
        "fixture_id": "resource-reservation-replay-v1",
        "accepted_state_hash": accepted.state_hash,
        "partial_state_hash": partial.state_hash,
        "final_state_hash": final.state_hash,
        "partial_active_order_ids": [
            reservation.order_id.value for reservation in partial.active_reservations
        ],
        "partial_cash_units": [value.units for value in partial.totals.cash],
        "partial_sellable_units": [
            value.units for value in partial.totals.sellable_quantities
        ],
        "partial_margin_units": [value.units for value in partial.totals.margin],
        "partial_fee_units": [value.units for value in partial.totals.fee_reserve],
        "partial_order_capacity_units": partial.totals.order_capacity_units,
        "partial_exposure_units": [
            value.units for value in partial.totals.exposure_capacity
        ],
        "final_active_count": len(final.active_reservations),
        "final_totals_hash": canonical_sha256(final.totals),
        "final_cursor_hashes": [cursor.stream_hash for cursor in final.cursors],
        "canonical_final_hash": canonical_sha256(final),
    }

    assert actual == expected
