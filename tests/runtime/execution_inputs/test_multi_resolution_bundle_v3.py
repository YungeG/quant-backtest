from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, replace
from inspect import signature
import json

import pytest

import crypto_quant_backtest
from crypto_quant_backtest.composition import (
    _ExecutionCasePlan,
    _HydratedExecutionCaseInputs,
    _execution_case_semantic_spec_v3,
)
from crypto_quant_backtest.execution_inputs import (
    _EXECUTION_INPUT_CATALOG,
    _ExecutionInputsHydrationFailureCodeV3,
    _hydrate_execution_inputs_v3,
    _materialize_execution_input_bundle_v3,
)
from crypto_quant_backtest.multi_resolution_market_data import (
    ExecutionDataBinding,
    MultiResolutionMarketDataBindings,
    ValuationDataBinding,
)
from crypto_quant_backtest.multi_resolution_preparation import (
    MultiResolutionMarketDataPreparation,
    PreparedMultiResolutionMarketData,
    prepare_multi_resolution_market_data_v1,
)
from crypto_quant_backtest.performance_observations import (
    BoundedPerformanceRecorder,
    PerformanceOperation,
)
from crypto_quant_backtest.resolution import ProfileResolver
from crypto_quant_domain import (
    ArtifactCatalogError,
    ArtifactEnvelope,
    ArtifactReadResult,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)
from tests.runtime.multi_resolution_preparation._fixtures import prepared_inputs
from tests.runtime.resolution._fixtures import profile_registry
from tests.runtime.runner._fixtures import resolved_request_and_case


class _Reader:
    def __init__(self, envelope: ArtifactEnvelope | None = None, error: Exception | None = None):
        self.envelope = envelope
        self.error = error

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        if self.error is not None:
            raise self.error
        if self.envelope is None:
            raise ArtifactCatalogError("missing")
        return ArtifactReadResult(
            envelope=self.envelope,
            artifact={"not": "authority"},
            source_bytes=canonical_bytes(self.envelope),
            source_hash=canonical_sha256(self.envelope),
        )


def _contract():
    values = prepared_inputs()
    prepared_outcome = prepare_multi_resolution_market_data_v1(**values)
    assert type(prepared_outcome.prepared) is PreparedMultiResolutionMarketData
    prepared = prepared_outcome.prepared
    assert prepared is not None
    base_resolved, base_case = resolved_request_and_case()
    authority = values["case_authority"]
    plan = _ExecutionCasePlan(
        decision_cycles=authority.decision_cycles,
        bar_executions=authority.bar_executions,
        financial_state=base_case.financial_state,
        financial_dispatch_plan=base_case.financial_dispatch_plan,
        execution_model=authority.execution_model,
        snapshot_plan=authority.snapshot_plan,
        closeout_policy=base_case.closeout_policy,
    )
    spec = _execution_case_semantic_spec_v3(
        base_spec=base_case.semantic_spec,
        execution_case_plan=plan,
        market_data_preparation=prepared.preparation,
    )
    request = replace(
        values["resolved_request"].request,
        execution_case_semantic_hash=spec.semantic_spec_hash,
    )
    resolved_outcome = ProfileResolver().resolve(
        request=request,
        registry=profile_registry(
            extra_market_capabilities=tuple(
                capability
                for capability in prepared.verified_reader.manifest.capabilities
                if capability.key == "price_bars"
            )
        ),
        market_bundle_manifest=prepared.verified_reader.manifest,
        build_artifact_manifest=base_resolved.build_artifact_manifest,
    )
    assert resolved_outcome.resolved is not None
    resolved = resolved_outcome.resolved
    hydrated = _HydratedExecutionCaseInputs(
        execution_case_semantic_spec=spec,
        timeline_stream_keys=("bars.open", "targets"),
        target_stream=authority.target_stream,
        timeline_batch_size=1,
        execution_case_plan=plan,
    )
    envelope = _materialize_execution_input_bundle_v3(
        resolved_request=resolved,
        hydrated_inputs=hydrated,
        market_data_preparation=prepared.preparation,
    )
    transport = crypto_quant_backtest.BacktestExecutionRequest(
        schema_version=3,
        request=resolved.request,
        execution_input_bundle_ref=ArtifactRef.from_envelope(envelope),
    )
    return prepared, resolved, hydrated, envelope, transport


def _hydrate(envelope, transport, prepared, resolved, recorder=None):
    return _hydrate_execution_inputs_v3(
        _Reader(envelope),
        transport,
        market_reader=prepared.verified_reader,
        resolved_request=resolved,
        prepared_market_data=prepared,
        recorder=recorder,
    )


def test_v3_is_one_private_catalog_registration_and_exact_v2_plus_preparation() -> None:
    prepared, _, _, envelope, transport = _contract()
    registrations = _EXECUTION_INPUT_CATALOG.registrations
    assert tuple((item.artifact_type, item.schema_version) for item in registrations) == (
        ("backtest_execution_input_bundle", 1),
        ("backtest_execution_input_bundle", 2),
        ("backtest_execution_input_bundle", 3),
    )
    assert set(envelope.payload) == {
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
        "market_data_preparation",
    }
    assert canonical_bytes(envelope.payload["market_data_preparation"]) == canonical_bytes(
        prepared.preparation
    )
    assert transport.schema_version == 3
    assert not hasattr(crypto_quant_backtest, "materialize_execution_input_bundle_v3")
    assert "materialize_execution_input_bundle_v3" not in crypto_quant_backtest.__all__


def test_v3_round_trip_reconstructs_every_nested_value_exactly() -> None:
    prepared, resolved, hydrated, envelope, transport = _contract()
    outcome = _hydrate(envelope, transport, prepared, resolved)
    assert outcome.failure is None
    assert outcome.result is not None
    assert outcome.result.market_data_preparation == prepared.preparation
    assert canonical_bytes(outcome.result.execution_case_plan.decision_cycles) == canonical_bytes(
        hydrated.execution_case_plan.decision_cycles
    )
    assert canonical_bytes(outcome.result.execution_case_plan.bar_executions) == canonical_bytes(
        hydrated.execution_case_plan.bar_executions
    )
    assert canonical_bytes(outcome.result.execution_case_plan.financial_state) == canonical_bytes(
        hydrated.execution_case_plan.financial_state
    )
    assert canonical_bytes(outcome.result.market_data_preparation) == canonical_bytes(
        envelope.payload["market_data_preparation"]
    )


def test_v3_decode_rejects_nested_constructor_bypass_and_noncanonical_hashes() -> None:
    prepared, resolved, hydrated, envelope, _ = _contract()
    payload = json.loads(canonical_bytes(envelope).decode())["payload"]
    payload["market_data_preparation"]["decision_schedule"]["requirements"][0][
        "minimum_count"
    ] = True
    malformed = ArtifactEnvelope.create("backtest_execution_input_bundle", 3, payload)
    transport = crypto_quant_backtest.BacktestExecutionRequest(
        3, resolved.request, ArtifactRef.from_envelope(malformed)
    )
    outcome = _hydrate(malformed, transport, prepared, resolved)
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is _ExecutionInputsHydrationFailureCodeV3.EXECUTION_INPUT_DECODE_FAILED

    forged = object.__new__(MultiResolutionMarketDataPreparation)
    object.__setattr__(forged, "decision_schedule", object())
    object.__setattr__(forged, "bindings", prepared.preparation.bindings)
    object.__setattr__(forged, "signal_lineages", prepared.preparation.signal_lineages)
    with pytest.raises(TypeError):
        _materialize_execution_input_bundle_v3(
            resolved_request=resolved,
            hydrated_inputs=hydrated,
            market_data_preparation=forged,
        )


def test_role_preimages_change_only_the_assigned_hash_then_request_and_run_identity() -> None:
    prepared, resolved, hydrated, _, _ = _contract()
    original = prepared.preparation
    lineage = replace(original.signal_lineages[0], observation_key="opaque:changed")
    decision = MultiResolutionMarketDataPreparation(
        original.decision_schedule, original.bindings, (lineage,)
    )
    execution = MultiResolutionMarketDataPreparation(
        original.decision_schedule,
        MultiResolutionMarketDataBindings(
            original.bindings.signal_bindings,
            (
                ExecutionDataBinding(
                    original.bindings.execution_bindings[0].profile_binding_key,
                    "bars.open.changed",
                ),
            ),
            original.bindings.valuation_bindings,
        ),
        original.signal_lineages,
    )
    valuation = MultiResolutionMarketDataPreparation(
        original.decision_schedule,
        MultiResolutionMarketDataBindings(
            original.bindings.signal_bindings,
            original.bindings.execution_bindings,
            (ValuationDataBinding(original.bindings.valuation_bindings[0].instrument_id, "bars.valuation.changed"),),
        ),
        original.signal_lineages,
    )
    specs = [
        _execution_case_semantic_spec_v3(
            base_spec=hydrated.execution_case_semantic_spec,
            execution_case_plan=hydrated.execution_case_plan,
            market_data_preparation=value,
        )
        for value in (original, decision, execution, valuation)
    ]
    base = specs[0]
    assert specs[1].decision_inputs_hash != base.decision_inputs_hash
    assert specs[1].execution_inputs_hash == base.execution_inputs_hash
    assert specs[1].snapshot_inputs_hash == base.snapshot_inputs_hash
    assert specs[2].decision_inputs_hash == base.decision_inputs_hash
    assert specs[2].execution_inputs_hash != base.execution_inputs_hash
    assert specs[2].snapshot_inputs_hash == base.snapshot_inputs_hash
    assert specs[3].decision_inputs_hash == base.decision_inputs_hash
    assert specs[3].execution_inputs_hash == base.execution_inputs_hash
    assert specs[3].snapshot_inputs_hash != base.snapshot_inputs_hash

    requests = [replace(resolved.request, execution_case_semantic_hash=spec.semantic_spec_hash) for spec in specs]
    outcomes = [
        ProfileResolver().resolve(
            request=request,
            registry=profile_registry(
                extra_market_capabilities=tuple(
                    capability
                    for capability in prepared.verified_reader.manifest.capabilities
                    if capability.key == "price_bars"
                )
            ),
            market_bundle_manifest=prepared.verified_reader.manifest,
            build_artifact_manifest=resolved.build_artifact_manifest,
        )
        for request in requests
    ]
    assert all(outcome.resolved is not None for outcome in outcomes)
    assert len({request.request_hash for request in requests}) == 4
    assert len({outcome.resolved.semantic_run_id for outcome in outcomes if outcome.resolved}) == 4


def test_v3_binding_and_replay_failures_are_closed_positional_and_secret_safe() -> None:
    prepared, resolved, _, envelope, transport = _contract()
    original = prepared.preparation
    changed_bindings = MultiResolutionMarketDataPreparation(
        original.decision_schedule,
        MultiResolutionMarketDataBindings(
            original.bindings.signal_bindings,
            original.bindings.execution_bindings,
            (ValuationDataBinding(original.bindings.valuation_bindings[0].instrument_id, "changed"),),
        ),
        original.signal_lineages,
    )
    changed_prepared = replace(prepared, preparation=changed_bindings)
    outcome = _hydrate(envelope, transport, changed_prepared, resolved)
    assert outcome.failure is not None
    assert tuple(field.name for field in fields(outcome.failure)) == (
        "code",
        "role_position",
        "schedule_entry_position",
        "requirement_position",
        "event_position",
    )
    assert outcome.failure.code is _ExecutionInputsHydrationFailureCodeV3.PREPARED_MARKET_DATA_BINDING_MISMATCH
    assert outcome.failure.role_position == 2

    replay = MultiResolutionMarketDataPreparation(
        replace(original.decision_schedule, key="changed.schedule"),
        original.bindings,
        original.signal_lineages,
    )
    outcome = _hydrate(envelope, transport, replace(prepared, preparation=replay), resolved)
    assert outcome.failure is not None
    assert outcome.failure.code is _ExecutionInputsHydrationFailureCodeV3.PREPARED_MARKET_DATA_REPLAY_MISMATCH

    secret = "token=SECRET-PROVIDER-PATH-/private/key"
    outcome = _hydrate_execution_inputs_v3(
        _Reader(error=RuntimeError(secret)),
        transport,
        market_reader=prepared.verified_reader,
        resolved_request=resolved,
        prepared_market_data=prepared,
    )
    assert outcome.failure is not None
    assert outcome.failure.code is _ExecutionInputsHydrationFailureCodeV3.EXECUTION_INPUT_UNAVAILABLE
    assert secret.encode() not in canonical_bytes(outcome.failure)
    assert not hasattr(outcome.failure, "message")


def test_v3_hydrate_and_replay_observations_are_direct_and_invariant(monkeypatch) -> None:
    prepared, resolved, _, envelope, transport = _contract()
    expected = _hydrate(envelope, transport, prepared, resolved)
    recorder = BoundedPerformanceRecorder()
    observed = _hydrate(envelope, transport, prepared, resolved, recorder)
    assert observed == expected
    cells = {cell.operation: cell for cell in recorder.snapshot()}
    assert cells[PerformanceOperation.HYDRATE_INPUTS].call_count == 1
    assert cells[PerformanceOperation.VERIFY_REPLAY].call_count == 1

    def fail_record(self, **kwargs):
        raise RuntimeError("SECRET-recorder")

    monkeypatch.setattr(BoundedPerformanceRecorder, "record", fail_record)
    failed_recorder = _hydrate(
        envelope, transport, prepared, resolved, BoundedPerformanceRecorder()
    )
    assert failed_recorder == expected


def test_legacy_bytes_signatures_and_request_shape_remain_locked() -> None:
    assert str(signature(crypto_quant_backtest.materialize_execution_input_bundle)) == "(*, request: 'BacktestRequest', build_artifact_manifest: 'BuildArtifactManifest', execution_case_semantic_spec: 'ExecutionCaseSemanticSpec', timeline_stream_keys: 'tuple[str, ...]', target_stream_key: 'str', timeline_batch_size: 'int', initial_financial_state_template: 'Mapping[str, Any]') -> 'ArtifactEnvelope'"
    assert str(signature(crypto_quant_backtest.materialize_execution_input_bundle_v2)) == "(*, resolved_request: 'ResolvedBacktestRequest', execution_case: 'ResolvedExecutionCase') -> 'ArtifactEnvelope'"
    assert tuple(field.name for field in fields(crypto_quant_backtest.BacktestExecutionRequest)) == (
        "schema_version",
        "request",
        "execution_input_bundle_ref",
    )
    _, _, _, envelope, transport = _contract()
    assert envelope.schema_version == 3
    assert transport.request.schema_version == 1
