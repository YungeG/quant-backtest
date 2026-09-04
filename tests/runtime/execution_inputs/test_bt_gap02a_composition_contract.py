from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from inspect import Parameter, signature
import json
from pathlib import Path

import pytest

import crypto_quant_backtest
from crypto_quant_backtest import (
    BacktestExecutionRequest,
    BinanceUsdmProfileComposer,
    CnAShareProfileComposer,
    ResolvedExecutionCase,
)
from crypto_quant_backtest import composition
from crypto_quant_backtest.execution_inputs import _hydrate_execution_inputs
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactReadResult,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)
from tests.runtime.profiles.binance_usdm._fixtures import composition_request
from tests.runtime.runner._fixtures import resolved_request_and_case
from tests.support.cn_a_share import build_cn_a_share_resolved_request

_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE = _ROOT / "tests/fixtures/runtime/bt-gap02a-production-composition-v2.json"
_CLOSURE_FIXTURE = _ROOT / "tests/fixtures/runtime/bt-gap02c-execution-closure-v2.json"
_FIXTURE_SHA256 = "bfa0ddff37bb6e1c813f50da14db4abcc2fab76fa8262c522fbf5facb1b5f764"
_PRESERVED_FIXTURES = {
    "bt_gap02b_execution_input_bundle_v1": _ROOT
    / "tests/fixtures/runtime/bt-gap02b-execution-input-bundle-v1.json",
    "bt_gap02c_execution_closure_v2": _CLOSURE_FIXTURE,
    "cn_a_share_resolved_profile_composition_v1": _ROOT
    / "tests/fixtures/runtime/profiles/cn-a-share-resolved-profile-composition-v1.json",
    "binance_usdm_resolved_profile_composition_v1": _ROOT
    / "tests/fixtures/runtime/profiles/binance-usdm-resolved-profile-composition-v1.json",
}


def _load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid JSON fixture {path}: {error}")
    assert type(value) is dict
    return value


@dataclass(frozen=True, slots=True)
class _Reader:
    envelope: ArtifactEnvelope

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        assert ref == ArtifactRef.from_envelope(self.envelope)
        return ArtifactReadResult(
            envelope=self.envelope,
            artifact={"not": "semantic authority"},
            source_bytes=canonical_bytes(self.envelope),
            source_hash=canonical_sha256(self.envelope),
        )


def _profiles() -> tuple[object, object]:
    cn_a = CnAShareProfileComposer().compose(build_cn_a_share_resolved_request())
    binance = BinanceUsdmProfileComposer().compose_executable(composition_request())
    assert cn_a.result is not None
    assert binance.result is not None
    return cn_a.result, binance.result


def _hydration_outcome():
    closure = _load(_CLOSURE_FIXTURE)
    bundle = closure["bundle"]
    assert type(bundle) is dict
    envelope = ArtifactEnvelope(**bundle["envelope"])
    resolved, case = resolved_request_and_case()
    transport = BacktestExecutionRequest(
        schema_version=2,
        request=resolved.request,
        execution_input_bundle_ref=ArtifactRef.from_envelope(envelope),
    )
    return (
        _hydrate_execution_inputs(
            _Reader(envelope),
            transport,
            market_reader=case.timeline.reader,
            resolved_request=resolved,
        ),
        case,
    )


def test_contract_fixture_freezes_v2_runtime_ownership_and_preserves_bytes() -> None:
    fixture = _load(_FIXTURE)
    assert sha256(_FIXTURE.read_bytes()).hexdigest() == _FIXTURE_SHA256
    assert fixture["fixture_id"] == "bt-gap02a-production-composition-v2"
    assert fixture["schema_version"] == 1
    assert fixture["private_entry_point"] == (
        "crypto_quant_backtest.composition._compose_execution_case"
    )
    assert fixture["private_input_type"] == (
        "crypto_quant_backtest.composition._HydratedExecutionCaseInputs"
    )
    assert fixture["forbidden_runtime_ownership"] == [
        "simulation_registration_implementation_hidden_builder",
        "second_profile_selector",
        "profile_branch_table",
        "tests_support_dependency",
        "second_decoder_or_schema_catalog",
    ]
    for key, path in _PRESERVED_FIXTURES.items():
        assert sha256(path.read_bytes()).hexdigest() == fixture[
            "preserved_fixture_sha256"
        ][key]


def test_selected_profile_registrations_match_the_frozen_v1_v2_authorities() -> None:
    fixture = _load(_FIXTURE)
    profiles = fixture["profiles"]
    assert type(profiles) is list
    for frozen, profile in zip(profiles, _profiles(), strict=True):
        assert frozen["market_profile_key"] == profile.market_registration.profile_key
        assert frozen["simulation_profile_key"] == (
            profile.simulation_registration.profile_key
        )
        assert frozen["execution_account_profile_key"] == (
            profile.execution_account_registration.profile_key
        )
        assert frozen["simulation_component_refs"] == [
            value.to_canonical_dict()
            for value in profile.simulation_registration.component_manifest
        ]


def test_one_package_private_entry_point_consumes_typed_hydrated_inputs() -> None:
    entry_point = getattr(composition, "_compose_execution_case", None)
    assert entry_point is not None, (
        "BT-GAP-02A RED: missing package-private production composition entry point"
    )
    assert "_compose_execution_case" not in crypto_quant_backtest.__all__
    parameters = tuple(signature(entry_point).parameters.values())
    names = [value.name for value in parameters]
    assert names == ["resolved_request", "market_reader", "hydrated_inputs"]
    assert all(value.kind is Parameter.KEYWORD_ONLY for value in parameters)

    input_type = getattr(composition, "_HydratedExecutionCaseInputs", None)
    assert isinstance(input_type, type), (
        "BT-GAP-02A RED: missing typed package-private composition input"
    )
    assert "_HydratedExecutionCaseInputs" not in crypto_quant_backtest.__all__


def test_v2_hydration_returns_one_exact_sealed_execution_case() -> None:
    outcome, expected = _hydration_outcome()
    assert outcome.failure is None
    assert outcome.result is not None
    actual = getattr(outcome.result, "execution_case", None)
    assert type(actual) is ResolvedExecutionCase, (
        "BT-GAP-02A RED: hydration did not compose one exact execution case"
    )
    assert canonical_bytes(actual) == canonical_bytes(expected)
    assert actual.semantic_spec == expected.semantic_spec
    assert actual.identity_manifest == expected.identity_manifest
    assert actual.verify_identity_manifest(expected.identity_manifest.semantic_run_id)


def test_repeat_hydration_is_byte_and_hash_deterministic() -> None:
    first, _ = _hydration_outcome()
    second, _ = _hydration_outcome()
    assert first.failure is None and second.failure is None
    assert first.result is not None and second.result is not None
    first_case = getattr(first.result, "execution_case", None)
    second_case = getattr(second.result, "execution_case", None)
    assert type(first_case) is ResolvedExecutionCase
    assert type(second_case) is ResolvedExecutionCase
    assert canonical_bytes(first_case) == canonical_bytes(second_case)
    assert first_case.case_hash == second_case.case_hash
