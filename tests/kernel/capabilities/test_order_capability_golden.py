from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_domain import ExecutionStyle, PositionEffect, TimeInForce
from crypto_quant_trading import (
    OrderCapabilityValidator,
    OrderStyleCapability,
    PriceConstraintShape,
)

from ._fixtures import capability_set, intent, limit_constraint


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/order-capability-validation-v1.json"


def test_order_capability_decisions_match_the_frozen_golden() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid frozen Order Capability fixture: {error}")

    validator = OrderCapabilityValidator()
    approved = validator.validate(intent(), capability_set())
    rejected = validator.validate(
        intent(
            style=ExecutionStyle.LIMIT,
            constraint=limit_constraint(),
            tif=TimeInForce.GTC,
            reduce_only=True,
            position_effect=PositionEffect.CLOSE,
        ),
        capability_set(
            styles=(
                OrderStyleCapability(
                    ExecutionStyle.LIMIT,
                    (PriceConstraintShape.NONE,),
                    (TimeInForce.DAY,),
                ),
            ),
            supports_reduce_only=False,
            position_effects=(PositionEffect.AUTO,),
        ),
    )
    assert approved.approval is not None
    assert rejected.rejection is not None

    actual = {
        "fixture_id": "order-capability-validation-v1",
        "approved": {
            "decision_id": approved.decision_id,
            "decision_hash": approved.decision_hash,
            "intent_hash": approved.approval.intent_hash,
            "capability_set_hash": approved.approval.capability_set_hash,
        },
        "rejected": {
            "decision_id": rejected.decision_id,
            "decision_hash": rejected.decision_hash,
            "intent_hash": rejected.rejection.intent_hash,
            "capability_set_hash": rejected.rejection.capability_set_hash,
            "unsupported": [
                {
                    "capability": value.capability,
                    "requested_value": value.requested_value,
                    "reason_code": value.reason_code,
                }
                for value in rejected.rejection.unsupported_capabilities
            ],
        },
    }
    assert actual == expected
