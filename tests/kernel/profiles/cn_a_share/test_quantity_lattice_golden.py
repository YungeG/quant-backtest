from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_domain import canonical_bytes
from crypto_quant_trading import ResidualPositionPolicy
from tests.kernel.profiles.cn_a_share._quantity_lattice_fixtures import (
    coordinate_quantity_case,
    quantity_sizing_case,
)


ROOT = Path(__file__).resolve().parents[4]
FIXTURE = (
    ROOT
    / "tests/fixtures/kernel/profiles/cn_a_share/quantity-lattice-odd-lot-v1.json"
)
_SCENARIOS = (
    ("flat-noop", 0, 0),
    ("flat-buy", 0, 251),
    ("odd-holding-buy", 55, 251),
    ("regular-sell", 500, 451),
    ("residual-alone", 299, 200),
    ("residual-combined", 299, 100),
    ("regular-from-odd", 299, 199),
    ("invalid-sell-one", 299, 298),
    ("invalid-sell-101", 299, 198),
    ("full-odd-close-299", 299, 98),
    ("one-share-residual", 101, 100),
    ("regular-holding-invalid-one", 200, 199),
    ("regular-close", 200, 0),
    ("full-odd-close-55", 55, 0),
)


def _read_json(path: Path) -> dict[str, object]:
    try:
        decoded = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot read canonical JSON: {path.name}") from error
    assert isinstance(decoded, dict)
    return decoded


def build_actual() -> dict[str, object]:
    xshg_model = quantity_sizing_case(current_units=299, raw_units=200)
    xshe_model = quantity_sizing_case(
        venue="xshe",
        current_units=299,
        raw_units=200,
    )
    scenario_values: dict[str, object] = {}
    for name, current, raw in _SCENARIOS:
        case = quantity_sizing_case(current_units=current, raw_units=raw)
        assert case.outcome.normalized_target is not None
        coordinated = coordinate_quantity_case(case)
        assert coordinated.decision is not None
        normalized = case.outcome.normalized_target
        scenario_values[name] = {
            "approved_target_hash": case.approved_target.approved_target_hash,
            "sizing_input_hash": case.sizing_input.input_hash,
            "decision": normalized.targets[0].decision,
            "normalized_target_id": normalized.normalized_target_id,
            "normalized_target_hash": normalized.normalized_target_hash,
            "active_target": normalized.active_target,
            "order_plan": coordinated.decision.plan,
        }

    close = quantity_sizing_case(
        current_units=55,
        raw_units=251,
        residual_policy=ResidualPositionPolicy.CLOSE_IF_PERMITTED,
    )
    hold = quantity_sizing_case(
        current_units=55,
        raw_units=251,
        residual_policy=ResidualPositionPolicy.HOLD_DUST,
    )
    fail_legal = quantity_sizing_case(
        current_units=299,
        raw_units=200,
        residual_policy=ResidualPositionPolicy.FAIL,
    )
    fail_residual = quantity_sizing_case(
        current_units=299,
        raw_units=298,
        residual_policy=ResidualPositionPolicy.FAIL,
    )
    fail_regular = quantity_sizing_case(
        current_units=500,
        raw_units=401,
        residual_policy=ResidualPositionPolicy.FAIL,
    )
    fail_buy = quantity_sizing_case(
        current_units=55,
        raw_units=251,
        residual_policy=ResidualPositionPolicy.FAIL,
    )
    assert xshg_model.outcome.normalized_target is not None
    assert xshe_model.outcome.normalized_target is not None
    assert close.outcome.normalized_target is not None
    assert hold.outcome.normalized_target is not None
    assert fail_legal.outcome.normalized_target is not None

    xshg_normalized = xshg_model.outcome.normalized_target
    xshe_normalized = xshe_model.outcome.normalized_target
    close_normalized = close.outcome.normalized_target
    hold_normalized = hold.outcome.normalized_target
    fail_legal_normalized = fail_legal.outcome.normalized_target
    xshg_plan = coordinate_quantity_case(xshg_model)
    xshe_plan = coordinate_quantity_case(xshe_model)
    assert xshg_plan.decision is not None
    assert xshe_plan.decision is not None

    payload = {
        "fixture_id": "cn-a-share-quantity-lattice-odd-lot-v1",
        "qualification": {
            "allowed_grade": "development",
            "deployment_authorized": False,
            "official_quantity_facts": {
                "buy_lot_shares": 100,
                "normal_sell_lot_shares": 100,
                "whole_residual_sale_permitted": True,
                "residual_split_permitted": False,
            },
            "system_preconditions": (
                "ordinary-rmb-a-share-standard-cash-auction",
                "current-holding-equals-authoritative-sellable-balance",
                "no-working-order-or-reservation",
                "long-only-cash-account",
            ),
            "limitations": (
                "odd-sell-order-admission-awaits-g08d-position-evidence",
                "single-order-caps-and-board-history-await-g08d-g08h",
                "no-broker-auto-split-retry-or-fill-guarantee",
            ),
        },
        "xshg": {
            "component_ref": xshg_model.model.component_ref,
            "resolution": xshg_model.resolution,
            "sizing_policy": xshg_model.policy,
            "decision": xshg_normalized.targets[0].decision,
            "normalized_target_id": xshg_normalized.normalized_target_id,
            "normalized_target_hash": xshg_normalized.normalized_target_hash,
            "active_target": xshg_normalized.active_target,
            "order_plan": xshg_plan.decision.plan,
        },
        "xshe": {
            "component_ref": xshe_model.model.component_ref,
            "resolution": xshe_model.resolution,
            "sizing_policy": xshe_model.policy,
            "decision": xshe_normalized.targets[0].decision,
            "normalized_target_id": xshe_normalized.normalized_target_id,
            "normalized_target_hash": xshe_normalized.normalized_target_hash,
            "active_target": xshe_normalized.active_target,
            "order_plan": xshe_plan.decision.plan,
        },
        "scenarios": scenario_values,
        "residual_policies": {
            "close_if_permitted": {
                "policy": close.policy,
                "decision": close_normalized.targets[0].decision,
                "normalized_target_id": close_normalized.normalized_target_id,
            },
            "hold_dust": {
                "policy": hold.policy,
                "decision": hold_normalized.targets[0].decision,
                "normalized_target_id": hold_normalized.normalized_target_id,
            },
            "fail_legal": {
                "policy": fail_legal.policy,
                "decision": fail_legal_normalized.targets[0].decision,
                "normalized_target_id": fail_legal_normalized.normalized_target_id,
            },
            "fail_residual": fail_residual.outcome.failure,
            "fail_regular": fail_regular.outcome.failure,
            "fail_buy": fail_buy.outcome.failure,
        },
    }
    try:
        decoded = json.loads(canonical_bytes(payload))
    except json.JSONDecodeError as error:
        raise AssertionError("canonical fixture did not decode") from error
    assert isinstance(decoded, dict)
    return decoded


def test_quantity_lattice_matches_static_golden() -> None:
    assert build_actual() == _read_json(FIXTURE)
