from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, replace
import hashlib
from inspect import signature
import json
from pathlib import Path

import pytest

import crypto_quant_backtest
from crypto_quant_backtest.composition import (
    _ExecutionCasePlan,
    _HydratedExecutionCaseInputs,
    _execution_case_semantic_spec_v3,
)
from crypto_quant_backtest.execution_inputs import (
    _EXECUTION_INPUT_CATALOG,
    _ExecutionInputsHydrationFailureCode,
    _ExecutionInputsHydrationFailureCodeV3,
    _hydrate_execution_inputs,
    _hydrate_execution_inputs_v3,
    _materialize_execution_input_bundle_v3,
)
from crypto_quant_backtest.engine import ExecutionCaseSemanticSpec
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
from crypto_quant_backtest.resolution import (
    ProfileResolver,
    ResolvedBacktestRequest,
    RuntimeLibraryRef,
)
from crypto_quant_backtest.run_end import MarkToMarketCloseoutPolicy
from crypto_quant_market_data import InMemoryMarketBundleReader, MarketBundleRef
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


_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/runtime/bt-gap02b-execution-input-bundle-v3.json"
)
_FIXTURE_SHA256 = "ac17536771914f599b3ea58f936049208f29b3f707815456e5b763d0762e5179"


class _Reader:
    def __init__(self, envelope: ArtifactEnvelope | None = None, error: BaseException | None = None):
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


def _contract(*, extra_runtime_library: bool = False):
    values = prepared_inputs()
    prepared_outcome = prepare_multi_resolution_market_data_v1(**values)
    assert type(prepared_outcome.prepared) is PreparedMultiResolutionMarketData
    prepared = prepared_outcome.prepared
    assert prepared is not None
    base_resolved, base_case = resolved_request_and_case()
    build_manifest = base_resolved.build_artifact_manifest
    if extra_runtime_library:
        build_manifest = replace(
            build_manifest,
            runtime_libraries=(
                *build_manifest.runtime_libraries,
                RuntimeLibraryRef(
                    "stdlib",
                    "3.13",
                    "sha256:" + "ab" * 32,
                ),
            ),
        )
    authority = values["case_authority"]
    assert type(base_case.semantic_spec) is ExecutionCaseSemanticSpec
    assert type(base_case.closeout_policy) is MarkToMarketCloseoutPolicy
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
        build_artifact_manifest_hash=build_manifest.manifest_hash,
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
        build_artifact_manifest=build_manifest,
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


def _resolved_for_spec(prepared, resolved, spec):
    request = replace(
        resolved.request,
        execution_case_semantic_hash=spec.semantic_spec_hash,
    )
    outcome = ProfileResolver().resolve(
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
    assert outcome.resolved is not None
    return outcome.resolved


def _transport(envelope, resolved):
    return crypto_quant_backtest.BacktestExecutionRequest(
        schema_version=3,
        request=resolved.request,
        execution_input_bundle_ref=ArtifactRef.from_envelope(envelope),
    )


def _payload(envelope):
    return json.loads(canonical_bytes(envelope).decode())["payload"]


def _hydrate(envelope, transport, prepared, resolved, recorder=None):
    return _hydrate_execution_inputs_v3(
        _Reader(envelope),
        transport,
        market_reader=prepared.verified_reader,
        resolved_request=resolved,
        prepared_market_data=prepared,
        recorder=recorder,
    )


def test_v3_frozen_fixture_locks_bundle_and_identity_chain() -> None:
    fixture = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert hashlib.sha256(_FIXTURE.read_bytes()).hexdigest() == _FIXTURE_SHA256
    prepared, resolved, hydrated, envelope, _ = _contract()
    assert fixture["fixture_id"] == "backtest-execution-input-bundle-v3"
    assert fixture["bundle"]["envelope"] == json.loads(canonical_bytes(envelope).decode())
    assert fixture["bundle"]["expected_canonical_sha256"] == canonical_sha256(envelope)
    assert fixture["identity"] == {
        "decision_inputs_hash": hydrated.execution_case_semantic_spec.decision_inputs_hash,
        "execution_inputs_hash": hydrated.execution_case_semantic_spec.execution_inputs_hash,
        "snapshot_inputs_hash": hydrated.execution_case_semantic_spec.snapshot_inputs_hash,
        "execution_case_semantic_hash": hydrated.execution_case_semantic_spec.semantic_spec_hash,
        "request_hash": resolved.request.request_hash,
        "semantic_run_id": resolved.semantic_run_id,
        "preparation_hash": prepared.preparation.preparation_hash,
    }


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


def test_v3_constructor_bypass_preserves_wrong_ref_precedence_without_io() -> None:
    prepared, resolved, _, _, _ = _contract()
    wrong_ref = ArtifactRef(
        "evidence_manifest",
        3,
        "sha256:" + "00" * 32,
    )
    forged = object.__new__(crypto_quant_backtest.BacktestExecutionRequest)
    object.__setattr__(forged, "schema_version", 3)
    object.__setattr__(forged, "request", resolved.request)
    object.__setattr__(forged, "execution_input_bundle_ref", wrong_ref)

    outcome = _hydrate_execution_inputs_v3(
        _Reader(error=AssertionError("reader must not be called")),
        forged,
        market_reader=prepared.verified_reader,
        resolved_request=resolved,
        prepared_market_data=prepared,
    )
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is (
        _ExecutionInputsHydrationFailureCodeV3.WRONG_EXECUTION_INPUT_BUNDLE_REF
    )


@pytest.mark.parametrize("schema_version", [1, 2])
def test_v3_wrong_ref_precedence_matches_legacy_v1_v2(schema_version) -> None:
    resolved, case = resolved_request_and_case()
    wrong_ref = ArtifactRef(
        "evidence_manifest",
        schema_version,
        "sha256:" + "00" * 32,
    )
    forged = object.__new__(crypto_quant_backtest.BacktestExecutionRequest)
    object.__setattr__(forged, "schema_version", schema_version)
    object.__setattr__(forged, "request", resolved.request)
    object.__setattr__(forged, "execution_input_bundle_ref", wrong_ref)

    outcome = _hydrate_execution_inputs(
        _Reader(error=AssertionError("reader must not be called")),
        forged,
        market_reader=case.timeline.reader,
        resolved_request=resolved if schema_version == 2 else None,
    )
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is (
        _ExecutionInputsHydrationFailureCode.WRONG_EXECUTION_INPUT_BUNDLE_REF
    )


def test_v3_materialization_rejects_empty_or_target_omitting_timeline_keys() -> None:
    prepared, resolved, hydrated, _, _ = _contract()
    for stream_keys in ((), ("bars.open",)):
        invalid = replace(hydrated, timeline_stream_keys=stream_keys)
        with pytest.raises(ValueError, match="target_stream_key|timeline_stream_keys"):
            _materialize_execution_input_bundle_v3(
                resolved_request=resolved,
                hydrated_inputs=invalid,
                market_data_preparation=prepared.preparation,
            )


def test_every_materialized_v3_bundle_decodes_and_hydrates_round_trip() -> None:
    prepared, resolved, _, envelope, transport = _contract()
    decoded = _EXECUTION_INPUT_CATALOG.read(canonical_bytes(envelope))
    assert decoded.envelope == envelope
    outcome = _hydrate(envelope, transport, prepared, resolved)
    assert outcome.failure is None
    assert outcome.result is not None


def test_v3_replays_embedded_preparation_against_decoded_case_authority() -> None:
    prepared, resolved, hydrated, _, _ = _contract()
    changed_plan = replace(hydrated.execution_case_plan, decision_cycles=())
    changed_spec = _execution_case_semantic_spec_v3(
        base_spec=hydrated.execution_case_semantic_spec,
        execution_case_plan=changed_plan,
        market_data_preparation=prepared.preparation,
    )
    changed_resolved = _resolved_for_spec(prepared, resolved, changed_spec)
    changed_inputs = replace(
        hydrated,
        execution_case_semantic_spec=changed_spec,
        execution_case_plan=changed_plan,
    )
    envelope = _materialize_execution_input_bundle_v3(
        resolved_request=changed_resolved,
        hydrated_inputs=changed_inputs,
        market_data_preparation=prepared.preparation,
    )

    outcome = _hydrate(
        envelope,
        _transport(envelope, changed_resolved),
        prepared,
        changed_resolved,
    )
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is (
        _ExecutionInputsHydrationFailureCodeV3.PREPARED_MARKET_DATA_REPLAY_MISMATCH
    )


@pytest.mark.parametrize("authority", ["financial_state", "financial_dispatch_plan"])
def test_v3_materialization_rejects_valid_plan_financial_tamper(authority) -> None:
    prepared, resolved, hydrated, _, _ = _contract()
    plan = hydrated.execution_case_plan
    if authority == "financial_state":
        changed_plan = replace(
            plan,
            financial_state=replace(plan.financial_state, lot_books=()),
        )
    else:
        dispatch = plan.financial_dispatch_plan
        changed_plan = replace(
            plan,
            financial_dispatch_plan=replace(
                dispatch,
                expected_artifact_roles=(
                    *dispatch.expected_artifact_roles,
                    "tampered_financial_role",
                ),
            ),
        )
    with pytest.raises(ValueError, match="semantic spec"):
        _materialize_execution_input_bundle_v3(
            resolved_request=resolved,
            hydrated_inputs=replace(hydrated, execution_case_plan=changed_plan),
            market_data_preparation=prepared.preparation,
        )


@pytest.mark.parametrize("authority", ["financial_state", "financial_dispatch_plan"])
def test_v3_hydration_rejects_valid_plan_financial_tamper(authority) -> None:
    prepared, resolved, _, envelope, _ = _contract()
    payload = _payload(envelope)
    plan = payload["execution_case_plan"]
    if authority == "financial_state":
        plan["financial_state"]["lot_books"] = []
    else:
        plan["financial_dispatch_plan"]["expected_artifact_roles"].append(
            "tampered_financial_role"
        )
    tampered = ArtifactEnvelope.create("backtest_execution_input_bundle", 3, payload)

    outcome = _hydrate(
        tampered,
        _transport(tampered, resolved),
        prepared,
        resolved,
    )
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is (
        _ExecutionInputsHydrationFailureCodeV3.PREPARED_MARKET_DATA_REPLAY_MISMATCH
    )


def test_v3_hydration_rejects_valid_run_end_hash_tamper() -> None:
    prepared, resolved, hydrated, envelope, _ = _contract()
    tampered_spec = replace(
        hydrated.execution_case_semantic_spec,
        run_end_inputs_hash="sha256:" + "00" * 32,
    )
    tampered_resolved = _resolved_for_spec(prepared, resolved, tampered_spec)
    payload = _payload(envelope)
    payload["request_hash"] = tampered_resolved.request.request_hash
    payload["semantic_run_id"] = tampered_resolved.semantic_run_id
    payload["execution_case_semantic_spec"]["run_end_inputs_hash"] = (
        tampered_spec.run_end_inputs_hash
    )
    tampered = ArtifactEnvelope.create("backtest_execution_input_bundle", 3, payload)

    outcome = _hydrate(
        tampered,
        _transport(tampered, tampered_resolved),
        prepared,
        tampered_resolved,
    )
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is (
        _ExecutionInputsHydrationFailureCodeV3.PREPARED_MARKET_DATA_REPLAY_MISMATCH
    )


@pytest.mark.parametrize(
    "nested_sequence",
    ["artifacts", "runtime_libraries", "identity_plan"],
)
def test_v3_decode_rejects_nested_sequence_normalization(nested_sequence) -> None:
    prepared, resolved, _, envelope, _ = _contract(extra_runtime_library=True)
    payload = _payload(envelope)
    if nested_sequence == "identity_plan":
        payload["execution_case_semantic_spec"]["identity_plan"].reverse()
    else:
        payload["build_artifact_manifest"]["identity"][nested_sequence].reverse()
    reordered = ArtifactEnvelope.create("backtest_execution_input_bundle", 3, payload)

    outcome = _hydrate(
        reordered,
        _transport(reordered, resolved),
        prepared,
        resolved,
    )
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is (
        _ExecutionInputsHydrationFailureCodeV3.EXECUTION_INPUT_DECODE_FAILED
    )


def test_v3_hydration_rejects_nested_forged_retained_reader_before_artifact_io() -> None:
    prepared, resolved, _, _, transport = _contract()
    secret = "SECRET-nested-reader-bundle-ref-/private/path"

    class SecretEquality:
        def __eq__(self, other):
            raise RuntimeError(secret)

    forged_ref = object.__new__(MarketBundleRef)
    object.__setattr__(forged_ref, "bundle_key", SecretEquality())
    object.__setattr__(
        forged_ref,
        "manifest_hash",
        prepared.verified_reader.bundle_ref.manifest_hash,
    )
    forged_reader = object.__new__(InMemoryMarketBundleReader)
    object.__setattr__(forged_reader, "bundle_ref", forged_ref)
    object.__setattr__(forged_reader, "manifest", prepared.verified_reader.manifest)
    object.__setattr__(forged_reader, "streams", prepared.verified_reader.streams)
    forged_prepared = replace(prepared, verified_reader=forged_reader)

    class NoArtifactIO:
        calls = 0

        def read(self, *, ref):
            self.calls += 1
            raise RuntimeError(secret)

    artifact_reader = NoArtifactIO()
    outcome = _hydrate_execution_inputs_v3(
        artifact_reader,  # pyright: ignore[reportArgumentType]
        transport,
        market_reader=forged_reader,
        resolved_request=resolved,
        prepared_market_data=forged_prepared,
    )
    assert artifact_reader.calls == 0
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is (
        _ExecutionInputsHydrationFailureCodeV3.MALFORMED_EXECUTION_REQUEST
    )
    assert secret.encode() not in canonical_bytes(outcome.failure)


def test_v3_nested_retained_reader_revalidation_preserves_baseexception() -> None:
    prepared, resolved, _, _, transport = _contract()

    class FatalAuthorityFailure(BaseException):
        pass

    fatal = FatalAuthorityFailure("fatal-nested-reader-authority")

    class FatalStreams(Mapping):
        def __getitem__(self, key):
            raise fatal

        def __iter__(self):
            raise fatal

        def __len__(self):
            raise fatal

    forged_reader = object.__new__(InMemoryMarketBundleReader)
    object.__setattr__(forged_reader, "bundle_ref", prepared.verified_reader.bundle_ref)
    object.__setattr__(forged_reader, "manifest", prepared.verified_reader.manifest)
    object.__setattr__(forged_reader, "streams", FatalStreams())
    forged_prepared = replace(prepared, verified_reader=forged_reader)

    with pytest.raises(FatalAuthorityFailure) as raised:
        _hydrate_execution_inputs_v3(
            _Reader(error=AssertionError("artifact I/O must not occur")),
            transport,
            market_reader=forged_reader,
            resolved_request=resolved,
            prepared_market_data=forged_prepared,
        )
    assert raised.value is fatal


def test_v3_hydration_revalidates_forged_caller_authority_before_io() -> None:
    prepared, resolved, _, envelope, transport = _contract()
    secret = "SECRET-forged-caller-token-/private/path"

    class SecretRef:
        @property
        def artifact_type(self):
            raise RuntimeError(secret)

    forged_transport = object.__new__(crypto_quant_backtest.BacktestExecutionRequest)
    object.__setattr__(forged_transport, "schema_version", 3)
    object.__setattr__(forged_transport, "request", resolved.request)
    object.__setattr__(forged_transport, "execution_input_bundle_ref", SecretRef())

    forged_resolved = object.__new__(ResolvedBacktestRequest)
    object.__setattr__(forged_resolved, "request", object())

    forged_prepared = object.__new__(PreparedMultiResolutionMarketData)
    object.__setattr__(forged_prepared, "preparation", object())
    object.__setattr__(forged_prepared, "eligibilities", ())
    object.__setattr__(forged_prepared, "verified_reader", prepared.verified_reader)

    for request_value, resolved_value, prepared_value in (
        (forged_transport, resolved, prepared),
        (transport, forged_resolved, prepared),
        (transport, resolved, forged_prepared),
    ):
        outcome = _hydrate_execution_inputs_v3(
            _Reader(error=AssertionError("reader must not be called")),
            request_value,
            market_reader=prepared.verified_reader,
            resolved_request=resolved_value,
            prepared_market_data=prepared_value,
        )
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is (
            _ExecutionInputsHydrationFailureCodeV3.MALFORMED_EXECUTION_REQUEST
        )
        assert secret.encode() not in canonical_bytes(outcome.failure)


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

    class SecretPropertyReader:
        @property
        def read(self):
            raise RuntimeError(secret)

    property_outcome = _hydrate_execution_inputs_v3(
        SecretPropertyReader(),  # pyright: ignore[reportArgumentType]
        transport,
        market_reader=prepared.verified_reader,
        resolved_request=resolved,
        prepared_market_data=prepared,
    )
    assert property_outcome.failure is not None
    assert property_outcome.failure.code is (
        _ExecutionInputsHydrationFailureCodeV3.EXECUTION_INPUT_UNAVAILABLE
    )
    assert secret.encode() not in canonical_bytes(property_outcome.failure)


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


def test_v3_instrumentation_failures_preserve_authority_and_baseexceptions(monkeypatch) -> None:
    prepared, resolved, _, envelope, transport = _contract()
    expected = _hydrate(envelope, transport, prepared, resolved)

    def fail_instrumentation(*args, **kwargs):
        raise RuntimeError("SECRET-instrumentation")

    monkeypatch.setattr(
        "crypto_quant_backtest.execution_inputs._clock", fail_instrumentation
    )
    monkeypatch.setattr(
        "crypto_quant_backtest.execution_inputs._binding_count_v3",
        fail_instrumentation,
    )
    observed = _hydrate(
        envelope, transport, prepared, resolved, BoundedPerformanceRecorder()
    )
    assert observed == expected

    class FatalAuthorityFailure(BaseException):
        pass

    fatal = FatalAuthorityFailure("fatal-authority")
    with pytest.raises(FatalAuthorityFailure) as raised:
        _hydrate_execution_inputs_v3(
            _Reader(error=fatal),
            transport,
            market_reader=prepared.verified_reader,
            resolved_request=resolved,
            prepared_market_data=prepared,
        )
    assert raised.value is fatal


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
