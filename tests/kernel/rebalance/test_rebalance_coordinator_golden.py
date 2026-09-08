from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_domain import OrderSide, canonical_sha256
from crypto_quant_trading import RebalanceCoordinator

from ._fixtures import (
    availability,
    normalized_target,
    policy,
    reservation_state,
    snapshot,
    validity,
    working_order,
    working_stream,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/rebalance-coordination-v1.json"


def test_rebalance_coordination_matches_the_frozen_golden() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid frozen Rebalance fixture: {error}")

    target = normalized_target()
    btc, eth = (value.instrument_id for value in target.targets)
    current = snapshot(btc_units=2_000, eth_units=16_000)
    working = working_stream(
        working_order(
            "b",
            instrument_id=btc,
            side=OrderSide.BUY,
            quantity_units=3_000,
            parent_id=target.normalized_target_id,
        )
    )
    reservations = reservation_state((working,))
    outcome = RebalanceCoordinator().coordinate(
        target=target,
        target_validity=validity(),
        portfolio_snapshot=current,
        working_orders=(working,),
        reservations=reservations,
        availability=availability(current, reservations),
        policy=policy(),
        as_of=current.timestamp,
    )
    if outcome.decision is None:
        raise AssertionError(f"rebalance fixture failed: {outcome.failure!r}")

    plan = outcome.decision.plan
    actual = {
        "fixture_id": "rebalance-coordination-v1",
        "decision_id": outcome.decision.decision_id,
        "decision_hash": outcome.decision.decision_hash,
        "plan_id": plan.plan_id,
        "plan_hash": plan.plan_hash,
        "planned": [
            {
                "instrument_id": str(value.instrument_id),
                "side": value.intent.side.value,
                "quantity_units": value.intent.quantity.units,
                "position_effect": value.intent.position_effect.value,
                "reduce_only": value.intent.reduce_only,
                "planned_order_id": value.planned_order_id,
            }
            for value in plan.planned_orders
        ],
        "cancel_order_ids": [value.order_id.value for value in plan.cancel_intents],
        "omissions": [
            {
                "instrument_id": str(value.instrument_id),
                "code": value.code.value,
            }
            for value in plan.omissions
        ],
        "working_order_set_hash": plan.based_on_working_order_set_hash,
        "canonical_plan_hash": canonical_sha256(plan),
    }
    assert actual == expected
