from __future__ import annotations

import hashlib
from dataclasses import fields, replace
from pathlib import Path

import pytest
from crypto_quant_backtest import (
    ArtifactInstallMode,
    BacktestProfileRegistry,
    BacktestRequest,
    DecisionSchedule,
    DecisionScheduleEntry,
    ProfileResolver,
    RequestedResultGrade,
    StrategyFamily,
    TargetStreamDecisionSchedule,
    TargetStreamScheduleEntry,
    TimelineSegment,
    TimelineWindow,
)
from crypto_quant_backtest.cn_a_share_fixed_singleton_no_trade_profile_v1 import (
    CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V1,
)
from crypto_quant_backtest.cn_a_share_fixed_singleton_no_trade_profile_v2 import (
    CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V2,
    create_cn_a_share_fixed_singleton_no_trade_authority_v2,
    validate_cn_a_share_fixed_singleton_no_trade_target_stream_v2,
)
from crypto_quant_backtest.engine import SnapshotProjectionPlan
from crypto_quant_backtest.execution import (
    BAR_OPEN_CAPABILITY,
    BAR_OPEN_EVENT_TYPE,
    BarOpenObservation,
    NextEligibleBarOpenModel,
)
from crypto_quant_backtest.multi_resolution_market_data import ExecutionDataBinding
from crypto_quant_backtest.multi_resolution_preparation import (
    MarketDataCaseAuthority,
    MarketDataPreparationFailureCode,
    prepare_multi_resolution_market_data_v1,
)
from crypto_quant_backtest.ports import SimulationPortType
from crypto_quant_domain import (
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentType,
    Money,
    Scale,
    SourceSequence,
    StrategySleeveId,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    InMemoryMarketBundleReader,
    MarketBundleCapability,
    MarketEvent,
)
from crypto_quant_trading import (
    CapitalAllocationPolicyRef,
    DecisionBatchExpectation,
    ProfilePortType,
    StrategyAllocation,
    StrategyOutputValidationContext,
)

from tests.runtime.engine._fixtures import decision_cycle

ROOT = Path(__file__).resolve().parents[4]
DECISION = (
    ROOT
    / "evidence/g12m-tushare-fixed-singleton-profile-build-authority-v2/decision.json"
)
MANIFEST = DECISION.with_name("manifest.sha256")
AUTHORITY_HASH = (
    "sha256:3d19c05e552aa61a7f1ff33bc2451d2d0cc13e0d3ee30acde46462bdfa65becf"
)
MARKET_HASH = "sha256:52b02b86b4fb6ea0b481d1184f68148d8b3d074b93e332ca582cd417072c8fd1"
SIMULATION_HASH = (
    "sha256:a1f0e4dd163deebf7dd8cf10e199078b6ad1c68bf0467b1f7f449e3423114875"
)
ACCOUNT_HASH = "sha256:bac4efa7e4874d3ab915ae6d775c3213db29c12c992663e065dc363ac8c78406"
BUILD_HASH = "sha256:26048a80c045b8c49ab4f09936ab6ea3ef31acd767d54365caa20c8e457f7f45"
EXECUTION_HASH = (
    "sha256:d69d6d96c9081f730db6ff8cdd02431d4babdef2e3967f0094971e73aedf30fe"
)
V1_HASH = "sha256:a0f0fb905dbc34d877c39130bf615f2f5d725b97aa618ed97bffdd1a12bce654"
V1_TARGET = "sha256:8e4bdddbd91e1bafd65363e133d382673df88e4dc4061d1f0dd776a42afc6cee"
V1_BUILD = "sha256:a6a73cb72a9ad4cf98bca789c19a6a261f00dc4b1e538478a0ca9674137ab516"


def _authority():
    return create_cn_a_share_fixed_singleton_no_trade_authority_v2()


def _bar_event(authority) -> MarketEvent:
    decision = authority.case.decision_time
    event = MarketEvent(
        event_id="fixed-singleton:bar-open:1",
        stream_key="bars.open",
        event_type=BAR_OPEN_EVENT_TYPE,
        capability=BAR_OPEN_CAPABILITY,
        instrument_id=authority.case.instrument_id,
        event_time=decision,
        available_time=decision,
        phase=TimelinePhase(20, "market_data"),
        source_sequence=SourceSequence(1),
        revision_id="initial",
        supersedes_revision_id=None,
        source_key="future-g12i-open-price-projection",
        source_hash="sha256:" + "ab" * 32,
        payload={
            "schema_version": 1,
            "bar_kind": "real",
            "open_price": {"units": 1000, "scale": 2, "quote_currency": "CNY"},
        },
    )
    assert BarOpenObservation.from_event(event).open_price is not None
    return event


def _reader(authority, *, include_bar_open: bool = True) -> InMemoryMarketBundleReader:
    target = authority.target_commitment.stream
    streams = {target.stream_key: target.events}
    capabilities = [
        MarketBundleCapability("tushare_cn_a_share.daily-publications", 1),
        target.events[0].capability,
    ]
    if include_bar_open:
        bar = _bar_event(authority)
        streams[bar.stream_key] = (bar,)
        capabilities.append(bar.capability)
    decision_ns = authority.case.decision_time.epoch_nanoseconds
    return InMemoryMarketBundleReader.build(
        bundle_key="synthetic-fixed-singleton-no-trade-v2",
        schema_version=1,
        coverage_start=UtcInstant(decision_ns - 1),
        coverage_end_exclusive=UtcInstant(decision_ns + 2),
        instrument_catalog_hash=canonical_sha256(
            {"instrument": str(authority.case.instrument_id)}
        ),
        capabilities=tuple(capabilities),
        streams=streams,
    )


def _registry(authority) -> BacktestProfileRegistry:
    return BacktestProfileRegistry(
        (authority.market_registration,),
        (authority.simulation_registration,),
        (authority.execution_account_registration,),
    )


def _request(authority, reader, build=None) -> BacktestRequest:
    build = authority.build_manifest if build is None else build
    decision_ns = authority.case.decision_time.epoch_nanoseconds
    return BacktestRequest(
        schema_version=1,
        experiment_id=None,
        timeline_window=TimelineWindow(
            UtcInstant(decision_ns - 1),
            authority.case.decision_time,
            UtcInstant(decision_ns + 1),
        ),
        market_semantics_profile_key=authority.market_registration.profile_key,
        simulation_profile_key=authority.simulation_registration.profile_key,
        execution_account_profile_key=authority.execution_account_registration.profile_key,
        execution_account_id=authority.execution_account_registration.account_id,
        reporting_currency=CurrencyId("CNY"),
        market_bundle_ref=reader.bundle_ref,
        target_stream_digest=authority.target_commitment.target_stream_digest,
        execution_case_semantic_hash=authority.authority_hash,
        master_random_seed=0,
        build_artifact_manifest_hash=build.manifest_hash,
        strategy_family=StrategyFamily.PRECOMPUTED_TARGET,
        engine_kind=authority.simulation_registration.engine_kind,
        result_grade_requested=RequestedResultGrade.DECISION_GRADE,
    )


def _resolved(authority, reader, build=None, registry=None):
    build = authority.build_manifest if build is None else build
    outcome = ProfileResolver().resolve(
        request=_request(authority, reader, build),
        registry=_registry(authority) if registry is None else registry,
        market_bundle_manifest=reader.manifest,
        build_artifact_manifest=build,
    )
    assert outcome.failure is None
    assert outcome.resolved is not None
    return outcome.resolved


def _preparation_inputs(authority, reader, resolved):
    event = authority.target_commitment.stream.events[0]
    instrument = authority.case.instrument_id
    cny = CurrencyId("CNY")
    catalog = InstrumentCatalog(
        currencies=(cny,),
        instruments=(
            InstrumentDefinition(
                instrument,
                InstrumentType.EQUITY,
                cny,
                cny,
                cny,
            ),
        ),
        symbol_timelines=(),
    )
    expectation = DecisionBatchExpectation(
        "cn-a-share-fixed-singleton-zero-target-v1",
        StrategySleeveId("cn-a-share-fixed-singleton.primary"),
    )
    context = StrategyOutputValidationContext(
        expectation.strategy_id,
        expectation.sleeve_id,
        authority.case.decision_time,
        catalog,
        (instrument,),
    )
    target_schedule = TargetStreamDecisionSchedule(
        authority.case.decision_time,
        TimelineSegment.ACTIVE_TRADING,
        (TargetStreamScheduleEntry(event.event_id, expectation, context),),
    )
    allocation = StrategyAllocation(
        strategy_id=expectation.strategy_id,
        sleeve_id=expectation.sleeve_id,
        valuation_time=authority.case.decision_time,
        valuation_currency=cny,
        allocation_nav=Money(0, Scale(2), "CNY"),
        policy_ref=CapitalAllocationPolicyRef(
            "fixed-singleton.zero-allocation.v1",
            1,
            canonical_sha256({"allocation": "zero"}),
        ),
        source_portfolio_snapshot_hash=canonical_sha256({"positions": (), "cash": "0"}),
    )
    cycle = replace(
        decision_cycle(),
        schedule=target_schedule,
        allocations=(allocation,),
        target_notional_scale=Scale(2),
        sizing_inputs=(),
        planning_at=authority.case.decision_time,
        admissions=(),
    )
    schedule = DecisionSchedule(
        "fixed-singleton-no-trade.v2",
        1,
        resolved.request.timeline_window,
        (
            DecisionScheduleEntry(
                event.timeline_instant,
                TimelineSegment.ACTIVE_TRADING,
            ),
        ),
        (),
    )
    snapshot = SnapshotProjectionPlan(
        (),
        (),
        cny,
        Scale(2),
        authority.case.decision_time,
        canonical_sha256({"currency": "CNY", "projection": "empty"}),
    )
    return {
        "expected_bundle_ref": reader.bundle_ref,
        "reader": reader,
        "schedule": schedule,
        "signal_binding_candidates": (),
        "execution_binding_candidates": (
            ExecutionDataBinding(
                authority.execution_model.component_ref.component_key,
                "bars.open",
            ),
        ),
        "valuation_binding_candidates": (),
        "signal_lineages": (),
        "case_authority": MarketDataCaseAuthority(
            (cycle,),
            (),
            authority.execution_model,
            snapshot,
            authority.target_commitment.stream,
        ),
        "resolved_request": resolved,
    }


def test_authority_matches_canonical_golden_and_predecessor_bindings() -> None:
    authority = CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V2
    v1 = CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V1

    assert canonical_bytes(authority) == DECISION.read_bytes()
    assert hashlib.sha256(DECISION.read_bytes()).hexdigest() == (
        "8b1da7ec4aaa4b652f69ce569ed0df953e8b9e30937368e9b32396baf090f21a"
    )
    assert authority.authority_hash == AUTHORITY_HASH
    assert authority.supersedes_authority_hash == V1_HASH
    assert authority.predecessor.candidate_commit == (
        "c52c8913ef680b34c1edecf46b1892b268e013e0"
    )
    assert authority.predecessor.governance_commit == (
        "0c0a7df5b1f4b6d83928fec0b19d60696ff20d72"
    )
    assert authority.predecessor.authority_hash == V1_HASH
    assert authority.predecessor.decision_file_hash == (
        "sha256:0a22eb7368eb0838d772efbcd6fc08cf48d333783d3ae881a12ba304f25ae1ca"
    )
    assert authority.predecessor.target_stream_digest == V1_TARGET
    assert authority.predecessor.build_manifest_hash == V1_BUILD
    assert canonical_bytes(authority.case) == canonical_bytes(v1.case)
    assert canonical_bytes(authority.source_identities) == canonical_bytes(
        v1.source_identities
    )
    assert canonical_bytes(authority.generic_proof_acceptance) == canonical_bytes(
        v1.generic_proof_acceptance
    )
    assert canonical_bytes(authority.target_commitment) == canonical_bytes(
        v1.target_commitment
    )
    assert authority.nonclaims == v1.nonclaims
    assert authority.limitations == authority.build_manifest.limitations == ()
    assert authority.decision_grade_eligible
    assert authority.build_manifest.decision_grade_eligible
    assert not authority.deployment_authorized
    assert MANIFEST.read_text(encoding="utf-8").splitlines() == [
        "8b1da7ec4aaa4b652f69ce569ed0df953e8b9e30937368e9b32396baf090f21a  evidence/g12m-tushare-fixed-singleton-profile-build-authority-v2/decision.json",
        "3d19c05e552aa61a7f1ff33bc2451d2d0cc13e0d3ee30acde46462bdfa65becf  semantic-authority-hash",
    ]


def test_actual_runtime_components_replace_only_six_v1_refs() -> None:
    authority = _authority()
    v1 = CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V1
    dispatcher = authority.financial_dispatcher_spec

    assert authority.execution_model.component_ref.component_digest == EXECUTION_HASH
    assert authority.execution_spec == authority.execution_model.spec()
    assert tuple(
        (value.capability_key, value.minimum_version)
        for value in authority.execution_spec.required_capabilities
    ) == (("bar_open", 1),)
    assert authority.closeout_spec == authority.closeout_policy.spec()

    profile = {
        value.port_type: value
        for value in authority.market_registration.component_manifest
    }
    simulation = {
        value.port_type: value
        for value in authority.simulation_registration.component_manifest
    }
    assert profile[ProfilePortType.POSITION_ACCOUNTING_MODEL] == (
        dispatcher.position_accounting_component
    )
    assert profile[ProfilePortType.FINANCING_MODEL] == dispatcher.financing_component
    assert profile[ProfilePortType.MARGIN_MODEL] == dispatcher.margin_component
    assert simulation[SimulationPortType.EXECUTION_MODEL] == (
        authority.execution_model.component_ref
    )
    assert simulation[SimulationPortType.CLOSEOUT_POLICY] == (
        authority.closeout_policy.component_ref
    )
    assert simulation[SimulationPortType.LIQUIDATION_AUDIT_MODEL] == (
        dispatcher.liquidation_audit_component
    )

    old_profile = {
        value.port_type: value for value in v1.market_registration.component_manifest
    }
    old_simulation = {
        value.port_type: value
        for value in v1.simulation_registration.component_manifest
    }
    replaced_profile = {
        ProfilePortType.POSITION_ACCOUNTING_MODEL,
        ProfilePortType.FINANCING_MODEL,
        ProfilePortType.MARGIN_MODEL,
    }
    replaced_simulation = {
        SimulationPortType.EXECUTION_MODEL,
        SimulationPortType.CLOSEOUT_POLICY,
        SimulationPortType.LIQUIDATION_AUDIT_MODEL,
    }
    for port in set(ProfilePortType) - replaced_profile:
        assert profile[port] == old_profile[port]
    for port in set(SimulationPortType) - replaced_simulation:
        assert simulation[port] == old_simulation[port]
    replacements = tuple(
        value
        for value in authority.component_applicability
        if value.predecessor_component_ref is not None
    )
    assert {value.component_ref.port_type for value in replacements} == (
        replaced_profile | replaced_simulation
    )
    assert all(
        "replaces the v1 semantic-generated ref" in value.justification
        for value in replacements
    )


def test_target_validator_is_exact_v1_delegate_and_rejects_subclass() -> None:
    authority = _authority()
    stream = authority.target_commitment.stream
    validate_cn_a_share_fixed_singleton_no_trade_target_stream_v2(stream)
    authority.validate_target_stream(stream)

    class TargetSubclass(type(stream)):
        pass

    with pytest.raises(TypeError, match="exact PrecomputedTargetStream"):
        validate_cn_a_share_fixed_singleton_no_trade_target_stream_v2(
            TargetSubclass(stream.stream_key, stream.events)
        )


def test_profile_resolution_requires_exact_three_sorted_capabilities() -> None:
    authority = _authority()
    reader = _reader(authority)
    assert tuple(value.identity for value in reader.manifest.capabilities) == (
        "bar_open@1",
        "precomputed_target_stream@1",
        "tushare_cn_a_share.daily-publications@1",
    )
    assert tuple(
        value.identity
        for value in authority.simulation_registration.required_bundle_capabilities
    ) == ("bar_open@1", "precomputed_target_stream@1")

    resolved = _resolved(authority, reader)
    assert resolved.environment.compatibility_report.compatible
    assert resolved.environment.compatibility_report.allowed_grade is (
        RequestedResultGrade.DECISION_GRADE
    )
    assert resolved.environment.limitations == ()
    assert not resolved.environment.deployment_authorized

    missing_bar = _reader(authority, include_bar_open=False)
    outcome = ProfileResolver().resolve(
        request=_request(authority, missing_bar),
        registry=_registry(authority),
        market_bundle_manifest=missing_bar.manifest,
        build_artifact_manifest=authority.build_manifest,
    )
    assert outcome.resolved is None
    assert outcome.failure is not None


def test_v1_simulation_registration_is_insufficient_for_v2_build() -> None:
    authority = _authority()
    v1 = CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V1
    reader = _reader(authority)
    registry = BacktestProfileRegistry(
        (authority.market_registration,),
        (v1.simulation_registration,),
        (authority.execution_account_registration,),
    )
    v1_simulation_key = v1.simulation_registration.profile_key
    request = replace(
        _request(authority, reader),
        simulation_profile_key=v1_simulation_key,
    )

    outcome = ProfileResolver().resolve(
        request=request,
        registry=registry,
        market_bundle_manifest=reader.manifest,
        build_artifact_manifest=authority.build_manifest,
    )
    assert outcome.resolved is None
    assert outcome.failure is not None


def test_resolution_rejects_missing_editable_and_profile_hash_mismatched_builds() -> (
    None
):
    authority = _authority()
    reader = _reader(authority)
    build = authority.build_manifest
    market_key = authority.market_registration.profile_key
    missing = replace(
        build,
        artifacts=tuple(
            value for value in build.artifacts if value.artifact_key != market_key
        ),
    )
    editable_index = next(
        index
        for index, value in enumerate(build.artifacts)
        if value.role.value == "backtest_runtime"
    )
    editable_artifacts = list(build.artifacts)
    editable_artifacts[editable_index] = replace(
        editable_artifacts[editable_index], install_mode=ArtifactInstallMode.EDITABLE
    )
    editable = replace(build, artifacts=tuple(editable_artifacts))
    mismatch_artifacts = tuple(
        replace(value, content_hash="sha256:" + "0" * 64)
        if value.artifact_key == market_key
        else value
        for value in build.artifacts
    )
    mismatch = replace(build, artifacts=mismatch_artifacts)

    for candidate in (missing, editable, mismatch):
        outcome = ProfileResolver().resolve(
            request=_request(authority, reader, candidate),
            registry=_registry(authority),
            market_bundle_manifest=reader.manifest,
            build_artifact_manifest=candidate,
        )
        assert outcome.resolved is None
        assert outcome.failure is not None


def test_public_prep_accepts_real_bar_open_and_zero_trade_case() -> None:
    authority = _authority()
    reader = _reader(authority)
    inputs = _preparation_inputs(authority, reader, _resolved(authority, reader))

    outcome = prepare_multi_resolution_market_data_v1(**inputs)

    assert outcome.failure is None
    assert outcome.prepared is not None
    assert outcome.prepared.preparation.bindings.execution_bindings == (
        ExecutionDataBinding("next_eligible_bar_open.v1", "bars.open"),
    )
    assert outcome.prepared.preparation.bindings.valuation_bindings == ()
    case = inputs["case_authority"]
    assert case.bar_executions == ()
    assert case.snapshot_plan.resolved_marks == ()
    assert case.decision_cycles[0].admissions == ()


def test_public_prep_rejects_v1_execution_ref_and_missing_or_wrong_binding() -> None:
    authority = _authority()
    v1 = CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V1
    reader = _reader(authority)
    exact = _preparation_inputs(authority, reader, _resolved(authority, reader))

    for bindings in (
        (),
        (
            ExecutionDataBinding(
                "next_eligible_bar_open.v1",
                authority.target_commitment.stream.stream_key,
            ),
        ),
    ):
        outcome = prepare_multi_resolution_market_data_v1(
            **{**exact, "execution_binding_candidates": bindings}
        )
        assert outcome.prepared is None
        assert outcome.failure is not None
        assert outcome.failure.code is (
            MarketDataPreparationFailureCode.EXECUTION_PROFILE_BINDING_MISMATCH
        )

    v1_market_key = v1.market_registration.profile_key
    v1_simulation_key = v1.simulation_registration.profile_key
    v1_request = replace(
        _request(authority, reader, v1.build_manifest),
        market_semantics_profile_key=v1_market_key,
        simulation_profile_key=v1_simulation_key,
        execution_case_semantic_hash=v1.authority_hash,
    )
    v1_outcome = ProfileResolver().resolve(
        request=v1_request,
        registry=_registry(v1),
        market_bundle_manifest=reader.manifest,
        build_artifact_manifest=v1.build_manifest,
    )
    assert v1_outcome.resolved is not None
    outcome = prepare_multi_resolution_market_data_v1(
        **{**exact, "resolved_request": v1_outcome.resolved}
    )
    assert outcome.prepared is None
    assert outcome.failure is not None
    assert outcome.failure.code is (
        MarketDataPreparationFailureCode.EXECUTION_PROFILE_BINDING_MISMATCH
    )


def test_exact_reconstruction_rejects_subclass_and_constructor_bypass() -> None:
    authority = _authority()
    authority_type = type(authority)

    class AuthoritySubclass(authority_type):
        pass

    with pytest.raises(TypeError, match="exact authority type"):
        AuthoritySubclass(
            *(getattr(authority, field.name) for field in fields(authority))
        )

    with pytest.raises(ValueError, match="exact reconstruction"):
        replace(authority, decision_grade_eligible=False)
    with pytest.raises(ValueError, match="authority_hash"):
        replace(authority, authority_hash="sha256:" + "0" * 64)

    bypassed = _authority()
    object.__setattr__(
        bypassed.execution_model.component_ref,
        "component_digest",
        "sha256:" + "0" * 64,
    )
    with pytest.raises(ValueError, match="exact reconstruction"):
        bypassed.to_canonical_dict()

    class ExecutionSubclass(NextEligibleBarOpenModel):
        pass

    with pytest.raises(TypeError, match="exact NextEligibleBarOpenModel"):
        MarketDataCaseAuthority(
            (),
            (),
            ExecutionSubclass(
                authority.execution_model.component_ref,
                authority.execution_model.applicability,
            ),
            SnapshotProjectionPlan(
                (),
                (),
                CurrencyId("CNY"),
                Scale(2),
                authority.case.decision_time,
                canonical_sha256({"projection": "empty"}),
            ),
            authority.target_commitment.stream,
        )


def test_build_reuses_only_exact_v1_account_and_core_artifacts() -> None:
    authority = _authority()
    v1 = CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V1
    assert (
        authority.market_registration.profile_digest,
        authority.simulation_registration.profile_digest,
        authority.execution_account_registration.profile_digest,
    ) == (MARKET_HASH, SIMULATION_HASH, ACCOUNT_HASH)
    assert authority.build_manifest.manifest_hash == BUILD_HASH
    assert authority.execution_account_registration == v1.execution_account_registration
    assert all(
        artifact.install_mode is not ArtifactInstallMode.EDITABLE
        and artifact.has_immutable_identity
        for artifact in authority.build_manifest.artifacts
    )
    profile_keys = {
        value.artifact_key
        for value in authority.build_manifest.artifacts
        if value.role.value == "profile_component"
    }
    assert profile_keys == {
        authority.market_registration.profile_key,
        authority.simulation_registration.profile_key,
        authority.execution_account_registration.profile_key,
    }
    assert all(
        value.artifact_version == "cebb9b033b7eeffbbff712715fc017708ac5a247"
        for value in authority.build_manifest.artifacts
        if value.role.value
        in {
            "trading_domain",
            "trading_kernel",
            "market_data_contracts",
            "backtest_runtime",
        }
    )


def test_accepted_v1_artifact_bytes_remain_immutable() -> None:
    expected = (
        (
            "packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_fixed_singleton_no_trade_profile_v1.py",
            "684ba1332a0447bf0bab289b634886838603fd551d3abb38cca3cc36de141857",
        ),
        (
            "tests/architecture/test_cn_a_share_fixed_singleton_no_trade_profile_boundary.py",
            "3a6b5ed96e6dfab33fb327adfb0fb06fceaf3d29e255ec7660eaad750f4f91da",
        ),
        (
            "docs/implementation/plans/g12/g12m-tushare-fixed-singleton-profile-build-authority-v1.md",
            "7a41c11c3a0f4671f549d7b937b541563d13161fba7055798436d532769aaaa0",
        ),
        (
            "docs/research/g12m-tushare-fixed-singleton-profile-build-authority-v1.md",
            "7729a9c804f497969d19cf075ed4a6c86d2edbc1b3a061f26a11123ec7622ff4",
        ),
        (
            "evidence/g12m-tushare-fixed-singleton-profile-build-authority-v1/decision.json",
            "0a22eb7368eb0838d772efbcd6fc08cf48d333783d3ae881a12ba304f25ae1ca",
        ),
        (
            "evidence/g12m-tushare-fixed-singleton-profile-build-authority-v1/manifest.sha256",
            "bbc1db7b0f64823d2469de1f8c23918366bdc9185f9bbe4f13f05c2d00168c3c",
        ),
    )
    for path, digest in expected:
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
