from __future__ import annotations

from hashlib import sha256
from inspect import Parameter, signature
import json
from pathlib import Path

import pytest

import crypto_quant_backtest
from crypto_quant_backtest import (
    BacktestExecutionRequest,
    BinanceUsdmProfileComposer,
    MarkToMarketCloseoutPolicy,
    NextEligibleBarOpenModel,
    NoEligibleBarAction,
)
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    TimeInForce,
    canonical_bytes,
    canonical_sha256,
)
from tests.runtime.profiles.binance_usdm._fixtures import composition_request
from tests.runtime.runner._fixtures import resolved_request_and_case

_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/runtime/bt-gap02c-execution-closure-v2.json"
)
_FIXTURE_SHA256 = "c082042640382dde2dad61f758058ab93c3ba741ed19df0256d7989a157eced1"
_PRESERVED_FIXTURES = {
    "bt_gap02b_execution_input_bundle_v1": Path(
        "tests/fixtures/runtime/bt-gap02b-execution-input-bundle-v1.json"
    ),
    "cn_a_share_resolved_profile_composition_v1": Path(
        "tests/fixtures/runtime/profiles/cn-a-share-resolved-profile-composition-v1.json"
    ),
    "binance_usdm_resolved_profile_composition_v1": Path(
        "tests/fixtures/runtime/profiles/binance-usdm-resolved-profile-composition-v1.json"
    ),
}


def _fixture() -> dict[str, object]:
    try:
        return json.loads(_FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid BT-GAP-02C fixture: {error}")


def _standard_execution_model() -> NextEligibleBarOpenModel:
    return NextEligibleBarOpenModel.create(
        actions=(
            (TimeInForce.DAY, NoEligibleBarAction.EXPIRE),
            (TimeInForce.GTC, NoEligibleBarAction.KEEP_ACTIVE),
            (TimeInForce.IOC, NoEligibleBarAction.EXPIRE),
            (TimeInForce.FOK, NoEligibleBarAction.EXPIRE),
            (TimeInForce.GTX, NoEligibleBarAction.KEEP_ACTIVE),
        )
    )


def test_v2_fixture_is_request_bound_and_preserves_all_v1_bytes() -> None:
    fixture = _fixture()
    assert sha256(_FIXTURE.read_bytes()).hexdigest() == _FIXTURE_SHA256
    assert fixture["fixture_id"] == "bt-gap02c-execution-closure-v2"
    assert fixture["schema_version"] == 1

    envelope = ArtifactEnvelope(**fixture["bundle"]["envelope"])
    ref_fields = dict(fixture["bundle"]["ref"])
    assert ref_fields.pop("type") == "artifact_ref"
    ref = ArtifactRef(**ref_fields)
    assert envelope.schema_version == 2
    assert ref == ArtifactRef.from_envelope(envelope)
    assert canonical_bytes(envelope).decode() == fixture["bundle"][
        "expected_canonical_utf8"
    ]
    assert envelope.content_hash == fixture["bundle"]["content_hash"]

    payload = envelope.payload
    assert set(payload) == {
        "type",
        "schema_version",
        "request_hash",
        "semantic_run_id",
        "build_artifact_manifest",
        "execution_case_semantic_spec",
        "timeline_stream_keys",
        "target_stream_key",
        "timeline_batch_size",
        "execution_case_plan",
    }
    plan = payload["execution_case_plan"]
    assert set(plan) == {
        "type",
        "schema_version",
        "decision_cycles",
        "bar_executions",
        "financial_state",
        "financial_dispatch_plan",
        "execution_model_spec",
        "snapshot_plan",
        "closeout_policy_spec",
    }
    assert "target_stream" not in plan
    assert "timeline" not in plan
    assert "identity_manifest" not in plan
    assert '"type":"market_event"' not in fixture["bundle"][
        "expected_canonical_utf8"
    ]
    assert payload["semantic_run_id"] == fixture["semantic_run_id"]

    for key, path in _PRESERVED_FIXTURES.items():
        assert sha256(path.read_bytes()).hexdigest() == fixture[
            "preserved_fixture_sha256"
        ][key]


def test_v2_materializer_has_one_deep_public_interface_and_exact_bytes() -> None:
    materializer = getattr(
        crypto_quant_backtest,
        "materialize_execution_input_bundle_v2",
        None,
    )
    assert materializer is not None, (
        "BT-GAP-02C RED: missing materialize_execution_input_bundle_v2"
    )
    assert "materialize_execution_input_bundle_v2" in crypto_quant_backtest.__all__
    parameters = tuple(signature(materializer).parameters.values())
    assert tuple(value.name for value in parameters) == (
        "resolved_request",
        "execution_case",
    )
    assert all(value.kind is Parameter.KEYWORD_ONLY for value in parameters)

    resolved, case = resolved_request_and_case()
    envelope = materializer(resolved_request=resolved, execution_case=case)
    fixture = _fixture()
    assert canonical_bytes(envelope).decode() == fixture["bundle"][
        "expected_canonical_utf8"
    ]
    assert envelope.content_hash == fixture["bundle"]["content_hash"]


def test_transport_v2_retains_one_ref_and_no_second_identity() -> None:
    fixture = _fixture()
    resolved, _ = resolved_request_and_case()
    ref_fields = dict(fixture["bundle"]["ref"])
    assert ref_fields.pop("type") == "artifact_ref"
    ref = ArtifactRef(**ref_fields)
    transport = BacktestExecutionRequest(
        schema_version=2,
        request=resolved.request,
        execution_input_bundle_ref=ref,
    )
    assert canonical_bytes(transport).decode() == fixture["transport"][
        "expected_canonical_utf8"
    ]
    assert canonical_sha256(transport) == fixture["transport"]["canonical_sha256"]
    assert not hasattr(transport, "content_hash")
    assert not hasattr(transport, "artifact_ref")
    assert not hasattr(transport, "path")
    assert not hasattr(transport, "status")


def test_binance_executable_profile_v2_uses_concrete_runtime_refs() -> None:
    compose_executable = getattr(BinanceUsdmProfileComposer(), "compose_executable", None)
    assert compose_executable is not None, (
        "BT-GAP-02C RED: missing additive Binance executable profile v2"
    )
    outcome = compose_executable(composition_request())
    assert outcome.result is not None
    profile = outcome.result
    frozen = _fixture()["binance_executable_simulation_v2"]
    assert profile.simulation.profile_key == frozen["profile_key"]
    assert profile.simulation.profile_version == frozen["profile_version"]

    refs = {
        value.port_type.value: value.to_canonical_dict()
        for value in profile.simulation.component_manifest
    }
    execution_ref = dict(refs["execution_model"])
    execution_ref.pop("type")
    closeout_ref = dict(refs["closeout_policy"])
    closeout_ref.pop("type")
    assert execution_ref == frozen["execution_model_ref"]
    assert closeout_ref == frozen["closeout_policy_ref"]
    assert refs["slippage_model"]["component_key"] == frozen[
        "slippage_component_key"
    ]
    legacy = BinanceUsdmProfileComposer().compose(composition_request())
    assert legacy.result is not None
    assert (
        profile.simulation.component_manifest
        != legacy.result.simulation.component_manifest
    )
    assert _standard_execution_model().component_ref.to_canonical_dict() == refs[
        "execution_model"
    ]
    assert MarkToMarketCloseoutPolicy().component_ref.to_canonical_dict() == refs[
        "closeout_policy"
    ]
