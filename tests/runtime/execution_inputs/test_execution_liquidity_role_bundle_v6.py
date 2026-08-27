from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest
from crypto_quant_backtest.composition import (
    _execution_case_semantic_spec_v3,
)
from crypto_quant_backtest.engine import ResolvedExecutionCase
from crypto_quant_backtest.execution_inputs import (
    _EXECUTION_INPUT_CATALOG,
    BacktestExecutionRequest,
    _ExecutionInputsHydrationFailureCodeV3,
    _hydrate_execution_inputs_v6_from_decoded,
    _materialize_execution_input_bundle_v3,
    _materialize_execution_input_bundle_v4,
    _materialize_execution_input_bundle_v5,
    _materialize_execution_input_bundle_v6,
    _read_execution_input_payload,
    _read_execution_input_payload_v2,
    _read_execution_input_payload_v3,
    _read_execution_input_payload_v4,
    _read_execution_input_payload_v5,
    _read_execution_input_payload_v6,
    _read_execution_inputs_v6_from_snapshot,
    materialize_execution_input_bundle_v2,
)
from crypto_quant_backtest.timeline import DeterministicTimeline
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactReadResult,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)

from tests.runtime.engine._fixtures import bar_execution, execution_case
from tests.runtime.execution_inputs.test_hydrate_execution_inputs import (
    _frozen_envelope,
)
from tests.runtime.execution_inputs.test_multi_resolution_bundle_v3 import (
    _contract,
    _resolved_for_spec,
)
from tests.runtime.runner._fixtures import resolved_request_and_case


def _v6_contract(role: str = "taker"):
    prepared, resolved, hydrated, _, _ = _contract()
    plan = replace(
        hydrated.execution_case_plan,
        bar_executions=tuple(
            replace(execution, fill_liquidity_role=role)
            for execution in hydrated.execution_case_plan.bar_executions
        ),
    )
    spec = _execution_case_semantic_spec_v3(
        base_spec=hydrated.execution_case_semantic_spec,
        execution_case_plan=plan,
        market_data_preparation=prepared.preparation,
    )
    resolved = _resolved_for_spec(prepared, resolved, spec)
    hydrated = replace(
        hydrated,
        execution_case_semantic_spec=spec,
        execution_case_plan=plan,
    )
    envelope = _materialize_execution_input_bundle_v6(
        resolved_request=resolved,
        hydrated_inputs=hydrated,
        market_data_preparation=prepared.preparation,
    )
    request = BacktestExecutionRequest(
        6,
        resolved.request,
        ArtifactRef.from_envelope(envelope),
    )
    return prepared, resolved, hydrated, envelope, request


def _payload(envelope: ArtifactEnvelope) -> dict[str, Any]:
    return json.loads(canonical_bytes(envelope).decode())["payload"]


def _rebuilt_case(prepared, decoded) -> ResolvedExecutionCase:
    spec = decoded.execution_case_semantic_spec
    plan = decoded.execution_case_plan
    timeline = DeterministicTimeline.open(
        reader=prepared.verified_reader,
        stream_keys=decoded.timeline_stream_keys,
        window=prepared.preparation.decision_schedule.window,
    )
    assert isinstance(timeline, DeterministicTimeline)
    return ResolvedExecutionCase(
        case_key=spec.case_key,
        case_version=spec.case_version,
        semantic_spec_hash=spec.semantic_spec_hash,
        timeline=timeline,
        timeline_batch_size=decoded.timeline_batch_size,
        target_stream=_contract()[2].target_stream,
        decision_cycles=plan.decision_cycles,
        bar_executions=plan.bar_executions,
        financial_state=plan.financial_state,
        financial_dispatch_plan=plan.financial_dispatch_plan,
        execution_model=plan.execution_model,
        snapshot_plan=plan.snapshot_plan,
        closeout_policy=plan.closeout_policy,
    )


def test_legacy_execution_case_and_input_hashes_remain_exact() -> None:
    prepared, resolved, hydrated, v3, _ = _contract()
    v4 = _materialize_execution_input_bundle_v4(
        resolved_request=resolved,
        hydrated_inputs=hydrated,
        market_data_preparation=prepared.preparation,
    )
    v5 = _materialize_execution_input_bundle_v5(
        resolved_request=resolved,
        hydrated_inputs=hydrated,
        market_data_preparation=prepared.preparation,
    )

    assert bar_execution().fill_liquidity_role is None
    assert "fill_liquidity_role" not in bar_execution().to_canonical_dict()
    assert canonical_sha256(bar_execution()) == (
        "sha256:7aeb361d14d735d9fc250a383f632c1d933bdf8017bac2e5816a4ff8aad5f713"
    )
    assert canonical_sha256(execution_case()) == (
        "sha256:2eefbaf92c312d623ce0ef65aacb90fe269fe234e8e0d41002aef41a3570cbf8"
    )
    assert canonical_sha256(v3) == (
        "sha256:5fbbef746788e63f3182147011d056f3aa0af70cea1cc3f019ff31a728aa6a63"
    )
    assert canonical_sha256(v4) == (
        "sha256:ed28a19c030a0148f3effd8748c3d62dd9f0279868fff1dcf3cdf06ee7811a17"
    )
    assert canonical_sha256(v5) == (
        "sha256:80365e07169987fce16e6c574a6b30436a56b3cf9c8de649de1b2aa1d179a793"
    )


def test_v6_taker_round_trip_hydration_and_rebuild_are_stable() -> None:
    prepared, resolved, _, envelope, request = _v6_contract()
    assert envelope.schema_version == 6
    assert envelope.payload["execution_case_plan"]["schema_version"] == 2
    assert b'"fill_liquidity_role":"taker"' in canonical_bytes(envelope)

    decoded = _EXECUTION_INPUT_CATALOG.read(canonical_bytes(envelope)).artifact
    assert decoded.execution_case_plan.bar_executions[0].fill_liquidity_role == "taker"
    outcome = _hydrate_execution_inputs_v6_from_decoded(
        decoded,
        request,
        market_reader=prepared.verified_reader,
        resolved_request=resolved,
        prepared_market_data=prepared,
    )
    assert outcome.failure is None and outcome.result is not None
    assert (
        outcome.result.execution_case_plan.bar_executions[0].fill_liquidity_role
        == "taker"
    )

    first = _rebuilt_case(prepared, decoded)
    replayed = _EXECUTION_INPUT_CATALOG.read(canonical_bytes(envelope)).artifact
    second = _rebuilt_case(prepared, replayed)
    assert first.bar_executions[0].fill_liquidity_role == "taker"
    assert first.case_hash == second.case_hash
    assert first.bar_executions[0].execution_hash == (
        second.bar_executions[0].execution_hash
    )


def test_v6_planning_snapshot_round_trip_binds_semantics_and_rejects_downgrade() -> None:
    prepared, resolved, hydrated, _, _ = _contract()
    cycle = hydrated.execution_case_plan.decision_cycles[0]
    snapshot = replace(
        hydrated.execution_case_plan.financial_state.initial_snapshot,
        timestamp=cycle.planning_at,
        timestamp_instant=None,
    )
    plan = replace(
        hydrated.execution_case_plan,
        decision_cycles=(
            replace(cycle, planning_snapshot=snapshot),
            *hydrated.execution_case_plan.decision_cycles[1:],
        ),
    )
    spec = _execution_case_semantic_spec_v3(
        base_spec=hydrated.execution_case_semantic_spec,
        execution_case_plan=plan,
        market_data_preparation=prepared.preparation,
    )
    resolved = _resolved_for_spec(prepared, resolved, spec)
    inputs = replace(
        hydrated,
        execution_case_semantic_spec=spec,
        execution_case_plan=plan,
    )

    with pytest.raises(ValueError, match="planning_snapshot"):
        _materialize_execution_input_bundle_v5(
            resolved_request=resolved,
            hydrated_inputs=inputs,
            market_data_preparation=prepared.preparation,
        )

    envelope = _materialize_execution_input_bundle_v6(
        resolved_request=resolved,
        hydrated_inputs=inputs,
        market_data_preparation=prepared.preparation,
    )
    decoded = _EXECUTION_INPUT_CATALOG.read(canonical_bytes(envelope)).artifact
    assert decoded.execution_case_plan.decision_cycles[0].planning_snapshot == snapshot

    changed_plan = replace(
        plan,
        decision_cycles=(
            replace(
                plan.decision_cycles[0],
                planning_snapshot=replace(
                    snapshot,
                    journal_state_hash="sha256:" + "12" * 32,
                ),
            ),
            *plan.decision_cycles[1:],
        ),
    )
    changed_spec = _execution_case_semantic_spec_v3(
        base_spec=spec,
        execution_case_plan=changed_plan,
        market_data_preparation=prepared.preparation,
    )
    assert changed_spec.decision_inputs_hash != spec.decision_inputs_hash
    assert changed_spec.semantic_spec_hash != spec.semantic_spec_hash


def test_v6_plan_keeps_none_optional_without_emitting_role_field() -> None:
    prepared, resolved, hydrated, _, _ = _contract()
    envelope = _materialize_execution_input_bundle_v6(
        resolved_request=resolved,
        hydrated_inputs=hydrated,
        market_data_preparation=prepared.preparation,
    )
    assert envelope.payload["execution_case_plan"]["schema_version"] == 2
    assert b"fill_liquidity_role" not in canonical_bytes(envelope)
    decoded = _EXECUTION_INPUT_CATALOG.read(canonical_bytes(envelope)).artifact
    assert decoded.execution_case_plan.bar_executions[0].fill_liquidity_role is None


def test_role_changes_execution_semantics_case_and_bundle_identity() -> None:
    prepared, resolved, hydrated, taker_envelope, _ = _v6_contract("taker")
    maker_plan = replace(
        hydrated.execution_case_plan,
        bar_executions=tuple(
            replace(execution, fill_liquidity_role="maker")
            for execution in hydrated.execution_case_plan.bar_executions
        ),
    )
    maker_spec = _execution_case_semantic_spec_v3(
        base_spec=hydrated.execution_case_semantic_spec,
        execution_case_plan=maker_plan,
        market_data_preparation=prepared.preparation,
    )
    maker_resolved = _resolved_for_spec(prepared, resolved, maker_spec)
    maker_envelope = _materialize_execution_input_bundle_v6(
        resolved_request=maker_resolved,
        hydrated_inputs=replace(
            hydrated,
            execution_case_semantic_spec=maker_spec,
            execution_case_plan=maker_plan,
        ),
        market_data_preparation=prepared.preparation,
    )

    taker = hydrated.execution_case_plan.bar_executions[0]
    maker = maker_plan.bar_executions[0]
    assert taker.execution_hash != maker.execution_hash
    assert hydrated.execution_case_semantic_spec.execution_inputs_hash != (
        maker_spec.execution_inputs_hash
    )
    assert hydrated.execution_case_semantic_spec.semantic_spec_hash != (
        maker_spec.semantic_spec_hash
    )
    assert canonical_sha256(taker_envelope) != canonical_sha256(maker_envelope)
    taker_case = _rebuilt_case(
        prepared,
        _EXECUTION_INPUT_CATALOG.read(canonical_bytes(taker_envelope)).artifact,
    )
    maker_case = _rebuilt_case(
        prepared,
        _EXECUTION_INPUT_CATALOG.read(canonical_bytes(maker_envelope)).artifact,
    )
    assert taker_case.case_hash != maker_case.case_hash


@pytest.mark.parametrize("role", ["full", "unknown", "", 1, True])
def test_unknown_or_non_exact_role_cannot_construct(role: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        replace(bar_execution(), fill_liquidity_role=role)


def test_v1_through_v5_role_injection_and_v6_downgrade_fail_closed() -> None:
    v1 = _payload(_frozen_envelope())
    v1["fill_liquidity_role"] = "taker"
    with pytest.raises((TypeError, ValueError)):
        _read_execution_input_payload(v1)

    resolved, case = resolved_request_and_case()
    v2 = _payload(
        materialize_execution_input_bundle_v2(
            resolved_request=resolved,
            execution_case=case,
        )
    )
    v2["execution_case_plan"]["bar_executions"][0][
        "fill_liquidity_role"
    ] = "taker"
    with pytest.raises((TypeError, ValueError)):
        _read_execution_input_payload_v2(v2)

    _, _, _, v6, _ = _v6_contract()
    for version, reader in (
        (3, _read_execution_input_payload_v3),
        (4, _read_execution_input_payload_v4),
        (5, _read_execution_input_payload_v5),
    ):
        downgraded = _payload(v6)
        downgraded["schema_version"] = version
        downgraded["execution_case_plan"]["schema_version"] = 1
        if version == 3:
            downgraded.pop("validation_instrument_catalogs")
        with pytest.raises((TypeError, ValueError)):
            reader(downgraded)


def test_legacy_materializers_never_emit_role_aware_plan() -> None:
    prepared, resolved, hydrated, _, _ = _v6_contract()
    for materializer in (
        _materialize_execution_input_bundle_v3,
        _materialize_execution_input_bundle_v4,
        _materialize_execution_input_bundle_v5,
    ):
        with pytest.raises(ValueError, match="execution_case_plan@1"):
            materializer(
                resolved_request=resolved,
                hydrated_inputs=hydrated,
                market_data_preparation=prepared.preparation,
            )

    legacy_resolved, legacy_case = resolved_request_and_case()
    with pytest.raises(ValueError):
        materialize_execution_input_bundle_v2(
            resolved_request=legacy_resolved,
            execution_case=replace(
                legacy_case,
                bar_executions=tuple(
                    replace(execution, fill_liquidity_role="taker")
                    for execution in legacy_case.bar_executions
                ),
            ),
        )


def test_unknown_role_decode_and_tampered_role_or_source_bytes_fail_closed() -> None:
    prepared, resolved, _, envelope, request = _v6_contract()
    unknown = _payload(envelope)
    unknown["execution_case_plan"]["bar_executions"][0][
        "fill_liquidity_role"
    ] = "full"
    with pytest.raises((TypeError, ValueError)):
        _read_execution_input_payload_v6(unknown)

    changed = _payload(envelope)
    changed["execution_case_plan"]["bar_executions"][0][
        "fill_liquidity_role"
    ] = "maker"
    changed_envelope = ArtifactEnvelope.create(
        "backtest_execution_input_bundle",
        6,
        changed,
    )
    changed_request = BacktestExecutionRequest(
        6,
        resolved.request,
        ArtifactRef.from_envelope(changed_envelope),
    )
    decoded = _EXECUTION_INPUT_CATALOG.read(canonical_bytes(changed_envelope)).artifact
    changed_outcome = _hydrate_execution_inputs_v6_from_decoded(
        decoded,
        changed_request,
        market_reader=prepared.verified_reader,
        resolved_request=resolved,
        prepared_market_data=prepared,
    )
    assert changed_outcome.result is None
    assert changed_outcome.failure is not None
    assert changed_outcome.failure.code is (
        _ExecutionInputsHydrationFailureCodeV3.PREPARED_MARKET_DATA_REPLAY_MISMATCH
    )

    source = object.__new__(ArtifactReadResult)
    object.__setattr__(source, "envelope", envelope)
    object.__setattr__(source, "artifact", None)
    object.__setattr__(source, "source_bytes", canonical_bytes(envelope) + b" ")
    object.__setattr__(source, "source_hash", canonical_sha256(envelope))

    class TamperedReader:
        @staticmethod
        def read(*, ref: ArtifactRef) -> ArtifactReadResult:
            assert ref == request.execution_input_bundle_ref
            return source

    decoded, failure = _read_execution_inputs_v6_from_snapshot(
        TamperedReader(),
        request,
    )
    assert decoded is None and failure is not None
    assert failure.code is _ExecutionInputsHydrationFailureCodeV3.EXECUTION_INPUT_TAMPERED
