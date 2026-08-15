from __future__ import annotations

from dataclasses import fields
import hashlib
import json
from pathlib import Path

from crypto_quant_backtest.cn_a_share_profile import (
    CnAShareProfileComposer,
    CnAShareProfileCompositionFailureCode,
)
from crypto_quant_domain import canonical_sha256
from tests.support.cn_a_share import build_cn_a_share_resolved_request


FIXTURE = Path(__file__).parents[3] / "fixtures/runtime/profiles/cn-a-share-resolved-profile-composition-v1.json"
FIXTURE_SHA256 = "aa032668a5207b61b6c8815894e0087f1c1e734d41e9707c7d32111b6c1cd79f"


def _refs(values: tuple[object, ...]) -> dict[str, object]:
    return {value.port_type.value: value for value in values}


def test_cn_a_share_profile_composition_contract_golden_is_static() -> None:
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA256
    try:
        expected = json.loads(raw)
    except json.JSONDecodeError as error:
        raise AssertionError("invalid G08H composition golden fixture") from error
    request = build_cn_a_share_resolved_request()
    outcome = CnAShareProfileComposer().compose(request)
    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert result.model_key == expected["model_key"]
    assert result.model_version == expected["model_version"]
    assert {"account": result.execution_account.profile_key, "market": result.market_semantics.profile_key, "simulation": result.simulation.profile_key} == expected["profile_keys"]
    assert tuple(code.value for code in CnAShareProfileCompositionFailureCode) == tuple(expected["failure_precedence"])
    market_refs = _refs(result.market_semantics.component_manifest)
    assert len(market_refs) == len(expected["market_components"]) == 12
    for row in expected["market_components"]:
        ref = market_refs[row["port_type"]]
        assert ref.component_key == row["component_key"]
        assert ref.component_version == row["component_version"]
        if "component_digest" in row:
            assert ref.component_digest == row["component_digest"]
    simulation_refs = _refs(result.simulation.component_manifest)
    assert len(simulation_refs) == len(expected["simulation_components"]) == 6
    for row in expected["simulation_components"]:
        ref = simulation_refs[row["port_type"]]
        assert ref.component_key == row["component_key"]
        assert ref.component_version == row["component_version"]
        if "component_digest" in row:
            assert ref.component_digest == row["component_digest"]
    for key, payload in expected["static_component_payloads"].items():
        ref = next(value for value in result.market_semantics.component_manifest if value.component_key == key)
        assert ref.component_digest == canonical_sha256(payload)
    assert {f"{value.key}@{value.version}" for value in result.market_registration.required_bundle_capabilities} == set(expected["market_capabilities"])
    assert {f"{value.key}@{value.version}" for value in result.simulation_registration.required_bundle_capabilities} == set(expected["simulation_capabilities"])
    dispatcher = expected["dispatcher"]
    assert result.financial_dispatcher_spec.dispatcher_key == dispatcher["dispatcher_key"]
    assert result.financial_dispatcher_spec.dispatcher_version == dispatcher["dispatcher_version"]
    assert result.financial_dispatcher_spec.snapshot_projection_key == dispatcher["snapshot_projection_key"]
    assert result.financial_dispatcher_spec.snapshot_projection_version == dispatcher["snapshot_projection_version"]
    assert list(result.limitations) == expected["limitations"]
    assert expected["qualification"] == {"allowed_grade": "development", "decision_grade_eligible": result.decision_grade_eligible, "profile_qualified": result.profile_qualified, "deployment_authorized": result.deployment_authorized}
    assert set(expected["inherited_fixture_sha256"].values()).issubset(set(result.source_manifest))


def test_cn_a_share_canonical_contract_fixture_matches_public_fields() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError("invalid G08H composition golden fixture") from error
    request = build_cn_a_share_resolved_request()
    outcome = CnAShareProfileComposer().compose(request)
    assert outcome.result is not None
    instances = {
        type(request.instrument_scope).__name__: request.instrument_scope,
        type(request.account_scope).__name__: request.account_scope,
        type(request.announcement_revision_set).__name__: request.announcement_revision_set,
        type(request.register_revision_set).__name__: request.register_revision_set,
        type(request.identity_history).__name__: request.identity_history,
        type(request).__name__: request,
        type(outcome.result.market_semantics).__name__: outcome.result.market_semantics,
        type(outcome.result.simulation).__name__: outcome.result.simulation,
        type(outcome.result.execution_account).__name__: outcome.result.execution_account,
        type(outcome.result).__name__: outcome.result,
        type(outcome).__name__: outcome,
    }
    for name, contract in expected["canonical_contracts"].items():
        if name not in instances:
            continue
        value = instances[name]
        assert value is not None
        assert [field.name for field in fields(type(value))] == contract["fields"]
        assert value.to_canonical_dict()["type"] == contract["type"]
        assert getattr(value, contract["hash_property"]).startswith("sha256:")
