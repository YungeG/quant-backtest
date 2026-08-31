from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import crypto_quant_backtest._durable_rebuild as durable
import pytest
from crypto_quant_backtest import (
    ExecutionCaseComposer,
    ExecutionResultHasher,
    ProfileResolver,
    RequestedResultGrade,
)
from crypto_quant_backtest._durable_rebuild import (
    DurableRebuildError,
    DurableRebuildPublisherV1,
)
from crypto_quant_backtest._publication import RunPublicationLock
from crypto_quant_backtest.composition import (
    _compose_execution_case_v3,
    _execution_case_semantic_spec_v3,
    _ExecutionCasePlan,
    _HydratedExecutionCaseInputs,
)
from crypto_quant_backtest.engine import (
    DeterministicBarEngine,
    ExecutionCaseIdentityFactory,
    ResolvedBarExecution,
)
from crypto_quant_backtest.execution_hash import CanonicalExecutionSummary
from crypto_quant_backtest.execution_inputs import (
    BacktestExecutionRequest,
    _materialize_execution_input_bundle_v6,
)
from crypto_quant_backtest.financial_dispatch import CashFillAccountingPlan
from crypto_quant_backtest.integrity import (
    IntegrityEvaluationContextV2,
    _evaluate_integrity_v2,
)
from crypto_quant_backtest.multi_resolution_preparation import (
    PreparedMultiResolutionMarketData,
)
from crypto_quant_backtest.run_end import MarkToMarketCloseoutPolicy
from crypto_quant_backtest.timeline import DeterministicTimeline
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactReadResult,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import InMemoryMarketBundleReader
from crypto_quant_trading import FinalFeeRuleSet

from tests.kernel.fees._fixtures import all_rules
from tests.runtime.durable_rebuild.test_verification import _proof_fixture
from tests.runtime.engine._fixtures import SyntheticExecutionCaseBuilder
from tests.runtime.execution_inputs.test_multi_resolution_bundle_v3 import _contract
from tests.runtime.providers import (
    test_binance_usdm_tradifi_preparation_v2 as koru_fixture,
)
from tests.runtime.providers import test_binance_usdm_tradifi_provider as koru_provider
from tests.runtime.test_durable_rebuild_facade import _decision_registry
from tests.runtime.test_durable_rebuild_facade_v4 import _v4_values


def _taker_execution(execution: ResolvedBarExecution) -> ResolvedBarExecution:
    accounting = execution.accounting_plan
    legacy = accounting.fee_plan.final_fee_rule_set
    taker_rules = FinalFeeRuleSet.create(
        market_fee_policy_ref=legacy.market_fee_policy_ref,
        tax_policy_ref=legacy.tax_policy_ref,
        account_fee_schedule_ref=legacy.account_fee_schedule_ref,
        assessment_currency=legacy.assessment_currency,
        assessment_scale=legacy.assessment_scale,
        charge_rules=all_rules(),
        minimums=(),
    )
    accounting = replace(
        accounting,
        position_payload=replace(
            cast(CashFillAccountingPlan, accounting.position_payload),
            final_fee_rule_set=taker_rules,
        ),
        fee_plan=replace(
            accounting.fee_plan,
            final_fee_rule_set=taker_rules,
        ),
    )
    return replace(
        execution,
        accounting_plan=accounting,
        fill_liquidity_role="taker",
    )


def _schema6_values():
    prepared, resolved, hydrated, _, _ = _contract()
    timeline = DeterministicTimeline.open(
        reader=prepared.verified_reader,
        stream_keys=hydrated.timeline_stream_keys,
        window=resolved.request.timeline_window,
    )
    assert isinstance(timeline, DeterministicTimeline)
    base_spec = replace(
        hydrated.execution_case_semantic_spec,
        timeline_semantic_hash=ExecutionCaseComposer.timeline_semantic_hash(timeline),
    )
    authority_plan = replace(
        hydrated.execution_case_plan,
        bar_executions=tuple(
            _taker_execution(execution)
            for execution in hydrated.execution_case_plan.bar_executions
        ),
    )
    spec = _execution_case_semantic_spec_v3(
        base_spec=base_spec,
        execution_case_plan=authority_plan,
        market_data_preparation=prepared.preparation,
    )
    registry = _decision_registry(prepared)
    resolution = ProfileResolver().resolve(
        request=replace(
            resolved.request,
            execution_case_semantic_hash=spec.semantic_spec_hash,
            result_grade_requested=RequestedResultGrade.DECISION_GRADE,
        ),
        registry=registry,
        market_bundle_manifest=prepared.verified_reader.manifest,
        build_artifact_manifest=resolved.build_artifact_manifest,
    )
    assert resolution.resolved is not None
    resolved = resolution.resolved
    generated = SyntheticExecutionCaseBuilder().build(
        ExecutionCaseIdentityFactory(
            semantic_run_id=resolved.semantic_run_id,
            namespace=spec.identity_namespace,
            identity_plan=spec.identity_plan,
        ),
        spec.semantic_spec_hash,
    )
    plan = _ExecutionCasePlan(
        decision_cycles=generated.decision_cycles,
        bar_executions=tuple(
            _taker_execution(execution)
            for execution in generated.bar_executions
        ),
        financial_state=generated.financial_state,
        financial_dispatch_plan=generated.financial_dispatch_plan,
        execution_model=authority_plan.execution_model,
        snapshot_plan=authority_plan.snapshot_plan,
        closeout_policy=cast(
            MarkToMarketCloseoutPolicy,
            generated.closeout_policy,
        ),
    )
    assert (
        _execution_case_semantic_spec_v3(
            base_spec=base_spec,
            execution_case_plan=plan,
            market_data_preparation=prepared.preparation,
        )
        == spec
    )
    hydrated = _HydratedExecutionCaseInputs(
        spec,
        hydrated.timeline_stream_keys,
        hydrated.target_stream,
        hydrated.timeline_batch_size,
        plan,
    )
    case = _compose_execution_case_v3(
        resolved_request=resolved,
        market_reader=prepared.verified_reader,
        hydrated_inputs=hydrated,
        market_data_preparation=prepared.preparation,
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
    return prepared, resolved, case, envelope, request, registry


def _schema7_values(bundle=None):
    outcome = koru_provider._prepare(bundle or koru_fixture._two_funding_bundle())
    assert outcome.failure is None and outcome.result is not None
    result = outcome.result
    planned = result.case_planning_result
    case = planned.execution_case
    prepared = PreparedMultiResolutionMarketData(
        planned.market_data_preparation,
        (),
        cast(InMemoryMarketBundleReader, result.preparation_result.market_reader),
    )
    return (
        prepared,
        planned.resolved_request,
        case,
        result.execution_input_envelope,
        BacktestExecutionRequest(8, planned.request, result.execution_input_ref),
        result.preparation_result.profile_registry,
    )


def _payload(envelope: ArtifactEnvelope) -> dict[str, Any]:
    return json.loads(canonical_bytes(envelope))["payload"]


def test_schema6_fresh_rebuild_preserves_taker_fill_and_result_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _proof_fixture(
        tmp_path,
        monkeypatch=monkeypatch,
        values=_schema6_values(),
    )
    verification = fixture["verification"]
    rebuilt = fixture["rebuilt_result"]
    attempt_result = fixture["attempts"].attempt_hashes[0].engine_result

    assert rebuilt is not None
    assert fixture["case"].bar_executions[0].fill_liquidity_role == "taker"
    assert rebuilt.fills[0].liquidity == "taker"
    assert rebuilt.fills[0] == attempt_result.fills[0]
    assert rebuilt.result_hash == attempt_result.result_hash
    assert verification.fresh_rebuild.execution_result_hash == (
        CanonicalExecutionSummary.from_result(rebuilt).execution_result_hash
    )
    assert verification.fresh_rebuild.execution_result_hash == (
        fixture["attempts"].attempt_hashes[0].execution_result_hash
    )


def test_schema7_durable_fresh_rebuild_runs_public_koru_batch_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _proof_fixture(
        tmp_path,
        monkeypatch=monkeypatch,
        values=_schema7_values(koru_fixture._raw_scale8_two_funding_bundle()),
    )
    payload = _payload(fixture["store"].values[fixture["request"].execution_input_bundle_ref].envelope)
    plan = payload["execution_case_plan"]
    batches = tuple(
        event["payload"]
        for event in plan["financial_dispatch_plan"]["scheduled_account_events"]
        if event["operation_key"] == "margin_liquidation_audit_batch"
    )
    rebuilt = fixture["rebuilt_result"]

    assert fixture["request"].schema_version == 8
    assert (
        fixture["case"].financial_dispatch_plan.dispatcher_spec.margin_component.component_key
        == "account.linear-perpetual.raw-valuation-margin-projection.v2"
    )
    assert fixture["verification"].execution_input_bundle_ref.schema_version == 8
    assert plan["schema_version"] == 4
    assert batches and all(batch["subwindows"] for batch in batches)
    funding = tuple(
        event
        for event in plan["financial_dispatch_plan"]["scheduled_account_events"]
        if event["operation_key"] == "funding"
    )
    assert len(funding) == 2
    assert all(
        event["payload"]["funding_mark_evidence"]["resolved_mark"]["price"]["scale"]
        == 8
        and event["payload"]["funding_mark_evidence"]["resolved_mark"]["price"]["units"]
        % 1_000_000
        for event in funding
    )
    assert all(
        price["scale"] == 8 and price["units"] % 1_000_000
        for batch in batches
        for price in (batch["liquidation_bar"]["low"], batch["liquidation_bar"]["high"])
    )
    assert len(
        {role for event in funding for role in event["expected_artifact_roles"]}
    ) == 4
    assert all(
        event["payload"]["settlement_evidence"]["event_id"] == event["event_id"]
        and event["payload"]["settlement_evidence"]["application_key"]
        == event["payload"]["settlement_identity"]["application_key"]
        for event in funding
    )
    assert rebuilt is not None
    assert rebuilt.result_hash == fixture["attempts"].attempt_hashes[0].engine_result.result_hash
    assert len(rebuilt.fills) == 2
    assert tuple(fill.liquidity for fill in rebuilt.fills) == ("taker", "taker")
    assert sum(
        artifact.role.startswith("funding_accounting.")
        for artifact in rebuilt.financial_artifacts
    ) == 2
    assert rebuilt.final_portfolio_snapshot.positions == ()
    roles = tuple(artifact.role for artifact in rebuilt.financial_artifacts)
    for batch in batches:
        for child in batch["subwindows"]:
            assert child["plan"]["liquidation_bars"] == [batch["liquidation_bar"]]
            assert child["start_checkpoint"]["instant"] == child["plan"]["interval_start"]
            assert child["end_checkpoint"]["instant"] == child["plan"]["interval_end_exclusive"]
            assert f"liquidation_audit.{child['plan']['role_suffix']}" in roles
            assert f"margin_projection.{child['plan']['role_suffix']}" in roles


@pytest.mark.parametrize("tamper", ("batch", "checkpoint"))
def test_schema7_batch_tampering_fails_before_rebuild_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    values = _schema7_values()
    fixture = _proof_fixture(tmp_path, values=values)
    payload = _payload(values[3])
    batch = next(
        event["payload"]
        for event in payload["execution_case_plan"]["financial_dispatch_plan"]["scheduled_account_events"]
        if event["operation_key"] == "margin_liquidation_audit_batch"
    )
    if tamper == "batch":
        batch["subwindows"] = []
    else:
        batch["subwindows"][0]["start_checkpoint"]["source_sequence"]["value"] += 1
    envelope = ArtifactEnvelope.create("backtest_execution_input_bundle", 7, payload)
    ref = ArtifactRef.from_envelope(envelope)
    fixture["store"].values[ref] = ArtifactReadResult(
        envelope=envelope,
        artifact=object(),
        source_bytes=canonical_bytes(envelope),
        source_hash=canonical_sha256(envelope),
    )
    request = BacktestExecutionRequest(7, values[1].request, ref)
    monkeypatch.setattr(
        DeterministicBarEngine,  # pyright: ignore[reportPrivateUsage]
        "run",
        lambda *args, **kwargs: pytest.fail("tampered input reached rebuild execution"),
    )

    with pytest.raises(DurableRebuildError):
        fixture["verifier"].verify(
            request=request,
            resolved_request=fixture["resolved"],
            prepared_market_data=fixture["prepared"],
            execution_case=fixture["case"],
            attempts=fixture["attempts"],
        )


def test_schema6_proof_and_integrity_report_identities_bind_execution_input(
    tmp_path: Path,
) -> None:
    fixture = _proof_fixture(tmp_path, values=_schema6_values())
    verification = fixture["verification"]
    request = fixture["request"]
    assert verification.execution_input_bundle_ref == request.execution_input_bundle_ref
    assert verification.execution_input_bundle_ref.schema_version == 6
    assert verification.execution_input_source_hash == canonical_sha256(
        fixture["store"].values[request.execution_input_bundle_ref].envelope
    )

    with RunPublicationLock(
        root=fixture["root"],
        semantic_run_id=verification.semantic_run_id,
    ) as lock:
        observation = DurableRebuildPublisherV1(
            root=fixture["root"],
            artifact_reader=fixture["store"],
        ).publish(lock=lock, verification=verification)
    expected_proof_id = "proof_" + canonical_sha256(
        {
            "type": "deterministic_rebuild_proof_identity",
            "schema_version": 1,
            "semantic_run_id": verification.semantic_run_id,
            "verification_ref": observation.verification_ref,
        }
    ).removeprefix("sha256:")
    assert observation.publication_manifest.proof_id == expected_proof_id

    attempt_hashes = tuple(fixture["attempts"].attempt_hashes)
    context = IntegrityEvaluationContextV2(
        fixture["resolved"],
        fixture["attempts"],
        ExecutionResultHasher.check_same_semantic_run(attempt_hashes),
        observation,
    )
    report = _evaluate_integrity_v2(context)
    assert context.to_canonical_dict()["rebuild_verification_ref"] == (
        observation.verification_ref
    )
    assert report.context.observation.verification.execution_input_bundle_ref == (
        request.execution_input_bundle_ref
    )
    assert report.report_hash == canonical_sha256(report)


@pytest.mark.parametrize(
    "tamper",
    ["maker", "unknown", "removed", "plan-downgrade", "bundle-downgrade"],
)
def test_schema6_role_and_downgrade_tampering_fails_before_rebuild_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    values = _schema6_values()
    fixture = _proof_fixture(tmp_path, values=values)
    payload = _payload(values[3])
    execution = payload["execution_case_plan"]["bar_executions"][0]
    bundle_schema = 6
    if tamper == "maker":
        execution["fill_liquidity_role"] = "maker"
    elif tamper == "unknown":
        execution["fill_liquidity_role"] = "unknown"
    elif tamper == "removed":
        execution.pop("fill_liquidity_role")
    elif tamper == "plan-downgrade":
        payload["execution_case_plan"]["schema_version"] = 1
    else:
        bundle_schema = 4
        payload["schema_version"] = 4
        payload["execution_case_plan"]["schema_version"] = 1

    envelope = ArtifactEnvelope.create(
        "backtest_execution_input_bundle",
        bundle_schema,
        payload,
    )
    source = canonical_bytes(envelope)
    ref = ArtifactRef.from_envelope(envelope)
    fixture["store"].values[ref] = ArtifactReadResult(
        envelope=envelope,
        artifact=object(),
        source_bytes=source,
        source_hash=canonical_sha256(envelope),
    )
    request = BacktestExecutionRequest(bundle_schema, values[1].request, ref)
    monkeypatch.setattr(
        durable.DeterministicBarEngine,  # pyright: ignore[reportPrivateUsage]
        "run",
        lambda *args, **kwargs: pytest.fail("tampered input reached rebuild execution"),
    )

    with pytest.raises(DurableRebuildError):
        fixture["verifier"].verify(
            request=request,
            resolved_request=fixture["resolved"],
            prepared_market_data=fixture["prepared"],
            execution_case=fixture["case"],
            attempts=fixture["attempts"],
        )


def test_schema4_durable_verification_hash_remains_exact(tmp_path: Path) -> None:
    values, envelope, request, registry = _v4_values()
    fixture = _proof_fixture(
        tmp_path,
        values=(values[0], values[1], values[2], envelope, request, registry),
    )
    assert canonical_sha256(fixture["verification"]) == (
        "sha256:7ba9ebc1d13bd86e2919b6ec571168eab40b72260341cc8da07c4c1c3d20f4b1"
    )
