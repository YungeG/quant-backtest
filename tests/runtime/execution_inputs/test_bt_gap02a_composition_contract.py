from __future__ import annotations

from hashlib import sha256
from inspect import Parameter, signature
import json
from pathlib import Path
from typing import Any

import pytest

import crypto_quant_backtest
from crypto_quant_backtest import (
    BinanceUsdmProfileComposer,
    CnAShareProfileComposer,
    SimulationPortType,
)
from crypto_quant_backtest import composition
from tests.runtime.profiles.binance_usdm._fixtures import composition_request
from tests.support.binance_usdm import build_binance_usdm_execution_case
from tests.support.cn_a_share import (
    build_cn_a_share_execution_case,
    build_cn_a_share_resolved_request,
)

_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/runtime/bt-gap02a-production-composition-v1.json"
)
_FIXTURE_SHA256 = "816358c92ac6e223ffe91cb01a1088a3721b08eac5f5623350affe7ba373437b"
_PRESERVED_FIXTURES = {
    "bt_gap02b_execution_input_bundle_v1": Path("tests/fixtures/runtime/bt-gap02b-execution-input-bundle-v1.json"),
    "cn_a_share_resolved_profile_composition_v1": Path("tests/fixtures/runtime/profiles/cn-a-share-resolved-profile-composition-v1.json"),
    "binance_usdm_resolved_profile_composition_v1": Path("tests/fixtures/runtime/profiles/binance-usdm-resolved-profile-composition-v1.json"),
}


def _fixture() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _profiles():
    cn_a = CnAShareProfileComposer().compose(build_cn_a_share_resolved_request())
    binance = BinanceUsdmProfileComposer().compose(composition_request())
    assert cn_a.result is not None
    assert binance.result is not None
    return cn_a.result, binance.result


def _represented_components(case) -> dict[SimulationPortType, object]:
    represented = {
        SimulationPortType.EXECUTION_MODEL: case.execution_model.component_ref,
        SimulationPortType.CLOSEOUT_POLICY: case.closeout_policy.component_ref,
    }
    if case.bar_executions:
        represented[SimulationPortType.SLIPPAGE_MODEL] = (
            case.bar_executions[0].slippage_model.component_ref
        )
    return represented


def test_contract_fixture_is_small_and_preserves_all_passed_fixture_bytes() -> None:
    fixture = _fixture()
    assert sha256(_FIXTURE.read_bytes()).hexdigest() == _FIXTURE_SHA256
    assert fixture["fixture_id"] == "bt-gap02a-production-composition-v1"
    assert fixture["schema_version"] == 1
    assert [value["profile_id"] for value in fixture["profiles"]] == [
        "cn_a_share",
        "binance_usdm",
    ]
    assert fixture["initial_state_scope_v1"] == {
        "order_streams": "must_be_empty",
        "order_admissions": "must_be_empty",
        "reservation_schedules": "must_be_empty",
        "settlement_state": "must_be_pristine",
    }
    for key, path in _PRESERVED_FIXTURES.items():
        assert sha256(path.read_bytes()).hexdigest() == fixture[
            "preserved_fixture_sha256"
        ][key]

    for frozen, profile in zip(fixture["profiles"], _profiles(), strict=True):
        assert profile.market_registration.profile_key == frozen["market_profile_key"]
        assert profile.simulation_registration.profile_key == frozen[
            "simulation_profile_key"
        ]
        assert profile.execution_account_registration.profile_key == frozen[
            "execution_account_profile_key"
        ]
        selected = {
            value.port_type.value: value.to_canonical_dict()
            for value in profile.simulation_registration.component_manifest
        }
        for expected in frozen["represented_component_refs"]:
            actual = dict(selected[expected["port_type"]])
            actual.pop("type")
            assert actual == expected


def test_one_package_private_entry_point_has_the_frozen_keyword_only_shape() -> None:
    entry_point = getattr(composition, "_compose_execution_case", None)
    assert entry_point is not None, (
        "BT-GAP-02A RED: missing package-private production composition entry point"
    )
    assert "_compose_execution_case" not in crypto_quant_backtest.__all__
    parameters = tuple(signature(entry_point).parameters.values())
    assert tuple(value.name for value in parameters) == (
        "resolved_request",
        "market_reader",
        "hydrated_inputs",
    )
    assert all(value.kind is Parameter.KEYWORD_ONLY for value in parameters)


@pytest.mark.parametrize("profile_index", (0, 1))
def test_only_the_selected_simulation_implementation_owns_concrete_construction(
    profile_index: int,
) -> None:
    profile = _profiles()[profile_index]
    owner = profile.simulation_registration.implementation
    assert callable(getattr(owner, "_build_execution_case", None)), (
        "BT-GAP-02A RED: selected simulation implementation does not own construction"
    )
    assert not hasattr(profile.market_registration.implementation, "_build_execution_case")
    assert not hasattr(
        profile.execution_account_registration.implementation,
        "_build_execution_case",
    )
    assert not hasattr(profile.profile_registry, "_build_execution_case")


def test_every_represented_case_component_equals_selected_registration_authority() -> None:
    cn_a, binance = _profiles()
    cases = (
        build_cn_a_share_execution_case(resolved_profile=cn_a),
        build_binance_usdm_execution_case(composition_request()),
    )
    for profile, case in zip((cn_a, binance), cases, strict=True):
        selected = {
            value.port_type: value
            for value in profile.simulation_registration.component_manifest
        }
        represented = _represented_components(case)
        assert represented == {port: selected[port] for port in represented}
