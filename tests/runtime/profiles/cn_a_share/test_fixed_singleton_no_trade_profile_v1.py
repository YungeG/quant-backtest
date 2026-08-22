from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest
from crypto_quant_backtest import (
    ArtifactInstallMode,
    BacktestProfileRegistry,
    BacktestRequest,
    PrecomputedTargetStream,
    PrecomputedTargetStreamAdapter,
    ProfileResolver,
    RequestedResultGrade,
    StrategyFamily,
    TargetStreamDecisionSchedule,
    TargetStreamScheduleEntry,
    TimelineEvent,
    TimelineSegment,
    TimelineWindow,
)
from crypto_quant_backtest.cn_a_share_fixed_singleton_no_trade_profile_v1 import (
    CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V1,
    create_cn_a_share_fixed_singleton_no_trade_authority_v1,
    validate_cn_a_share_fixed_singleton_no_trade_target_stream_v1,
)
from crypto_quant_domain import (
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentType,
    StrategySleeveId,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketBundleManifest,
    MarketBundleRef,
    MarketStreamManifest,
)
from crypto_quant_trading import (
    DecisionBatchExpectation,
    PreTradeRiskEvaluator,
    PreTradeRiskReasonCode,
    StrategyOutputValidationContext,
)

from tests.kernel.pretrade_risk._fixtures import evaluation_input

ROOT = Path(__file__).resolve().parents[4]
DECISION = (
    ROOT
    / "evidence/g12m-tushare-fixed-singleton-profile-build-authority-v1/decision.json"
)
MANIFEST = DECISION.with_name("manifest.sha256")
AUTHORITY_HASH = "sha256:a0f0fb905dbc34d877c39130bf615f2f5d725b97aa618ed97bffdd1a12bce654"
TARGET_DIGEST = "sha256:8e4bdddbd91e1bafd65363e133d382673df88e4dc4061d1f0dd776a42afc6cee"
PROFILE_DIGESTS = (
    "sha256:c04c32477654531c643c7bdc3527bf5a3c52671581a1444b864ac685f0b0a8e7",
    "sha256:c21f8a46546690bb5227e6bf228418daa56d8becb9a4506cc649bd7fde2acc8f",
    "sha256:bac4efa7e4874d3ab915ae6d775c3213db29c12c992663e065dc363ac8c78406",
)
BUILD_HASH = "sha256:a6a73cb72a9ad4cf98bca789c19a6a261f00dc4b1e538478a0ca9674137ab516"


def _authority():
    return create_cn_a_share_fixed_singleton_no_trade_authority_v1()


def _candidate_payload(event):
    candidate = dict(event.payload["candidate"])
    candidate["evidence"] = dict(candidate["evidence"])
    candidate["targets"] = [dict(value) for value in candidate["targets"]]
    return candidate


def _event_with(**changes):
    event = _authority().target_commitment.stream.events[0]
    return replace(event, **changes)


def _registry(authority) -> BacktestProfileRegistry:
    return BacktestProfileRegistry(
        (authority.market_registration,),
        (authority.simulation_registration,),
        (authority.execution_account_registration,),
    )


def _bundle(authority) -> MarketBundleManifest:
    event = authority.target_commitment.stream.events[0]
    return MarketBundleManifest.build(
        bundle_key="synthetic-fixed-singleton-no-trade-v1",
        schema_version=1,
        coverage_start=UtcInstant(authority.case.decision_time.epoch_nanoseconds - 1),
        coverage_end_exclusive=UtcInstant(
            authority.case.decision_time.epoch_nanoseconds + 2
        ),
        instrument_catalog_hash=canonical_sha256({"instrument": "xshe:000001"}),
        capabilities=(
            MarketBundleCapability("tushare_cn_a_share.daily-publications", 1),
            MarketBundleCapability("precomputed_target_stream", 1),
        ),
        streams=(MarketStreamManifest.from_events(event.stream_key, (event,)),),
    )


def _request(authority, bundle, build=None) -> BacktestRequest:
    build = authority.build_manifest if build is None else build
    decision_ns = authority.case.decision_time.epoch_nanoseconds
    return BacktestRequest(
        schema_version=1,
        experiment_id=None,
        timeline_window=TimelineWindow(
            UtcInstant(decision_ns - 1),
            UtcInstant(decision_ns),
            UtcInstant(decision_ns + 1),
        ),
        market_semantics_profile_key=authority.market_registration.profile_key,
        simulation_profile_key=authority.simulation_registration.profile_key,
        execution_account_profile_key=authority.execution_account_registration.profile_key,
        execution_account_id=authority.execution_account_registration.account_id,
        reporting_currency=CurrencyId("CNY"),
        market_bundle_ref=MarketBundleRef.from_manifest(bundle),
        target_stream_digest=authority.target_commitment.target_stream_digest,
        execution_case_semantic_hash=authority.authority_hash,
        master_random_seed=0,
        build_artifact_manifest_hash=build.manifest_hash,
        strategy_family=StrategyFamily.PRECOMPUTED_TARGET,
        engine_kind=authority.simulation_registration.engine_kind,
        result_grade_requested=RequestedResultGrade.DECISION_GRADE,
    )


def test_authority_matches_canonical_golden_and_exact_hashes() -> None:
    authority = CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V1

    assert canonical_bytes(authority) == DECISION.read_bytes()
    assert authority.authority_hash == AUTHORITY_HASH
    assert authority.target_commitment.target_stream_digest == TARGET_DIGEST
    assert (
        authority.market_registration.profile_digest,
        authority.simulation_registration.profile_digest,
        authority.execution_account_registration.profile_digest,
    ) == PROFILE_DIGESTS
    assert authority.build_manifest.manifest_hash == BUILD_HASH
    assert authority.limitations == authority.build_manifest.limitations == ()
    assert authority.decision_grade_eligible
    assert authority.build_manifest.decision_grade_eligible
    assert not authority.deployment_authorized
    assert authority.supersedes_authority_hash is None
    assert authority.case.latest_accepted_member_acquired_at == UtcInstant(
        1_787_292_861_381_694_496
    )
    assert authority.case.decision_time == UtcInstant(1_787_292_861_381_694_497)
    assert authority.source_identities[0].assessment_time == UtcInstant(
        1_787_292_861_381_694_496
    )
    assert authority.source_identities[1].assessment_time == UtcInstant(
        1_787_299_622_295_499_670
    )
    assert (
        authority.source_identities[1].assessment_time
        > authority.case.decision_time
    )
    assert authority.build_manifest.provenance.built_at == UtcInstant(
        1_787_391_728_000_000_000
    )
    assert (
        "does_not_claim_historical_provider_availability_or_future_revision_finality"
        in authority.nonclaims
    )
    assert MANIFEST.read_text(encoding="utf-8").splitlines() == [
        "0a22eb7368eb0838d772efbcd6fc08cf48d333783d3ae881a12ba304f25ae1ca  evidence/g12m-tushare-fixed-singleton-profile-build-authority-v1/decision.json",
        "a0f0fb905dbc34d877c39130bf615f2f5d725b97aa618ed97bffdd1a12bce654  semantic-authority-hash",
    ]


def test_target_stream_validates_and_adapter_decodes_exact_singleton_zero() -> None:
    authority = _authority()
    stream = authority.target_commitment.stream
    validate_cn_a_share_fixed_singleton_no_trade_target_stream_v1(stream)
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
    event = stream.events[0]
    evidence = event.payload["candidate"]["evidence"]
    assert "g12i_report_hash" in evidence
    assert "g12i_assessment_time" in evidence
    assert not any(str(key).startswith("g12k_") for key in evidence)
    schedule = TargetStreamDecisionSchedule(
        authority.case.decision_time,
        TimelineSegment.ACTIVE_TRADING,
        (TargetStreamScheduleEntry(event.event_id, expectation, context),),
    )

    outcome = PrecomputedTargetStreamAdapter().inject(
        stream=stream,
        timeline_events=(TimelineEvent(TimelineSegment.ACTIVE_TRADING, event),),
        schedule=schedule,
    )

    assert outcome.injection is not None
    decisions = outcome.injection.batch.decisions
    assert len(decisions) == 1
    targets = decisions[0].target_snapshot.targets
    assert len(targets) == 1
    assert targets[0].instrument_id == instrument
    assert targets[0].units == 0
    assert decisions[0].observed_through.epoch_nanoseconds + 1 == (
        decisions[0].decision_time.epoch_nanoseconds
    )


def test_target_validator_rejects_empty_nonzero_extra_and_identity_mutations() -> None:
    authority = _authority()
    stream = authority.target_commitment.stream
    event = stream.events[0]

    with pytest.raises(ValueError, match="commitment"):
        authority.validate_target_stream(PrecomputedTargetStream(stream.stream_key, ()))

    candidate = _candidate_payload(event)
    candidate["targets"][0]["value"] = "0.01"
    nonzero = replace(event, payload={"schema_version": 1, "candidate": candidate})
    with pytest.raises(ValueError, match="commitment"):
        authority.validate_target_stream(PrecomputedTargetStream(stream.stream_key, (nonzero,)))

    candidate = _candidate_payload(event)
    candidate["targets"].append(
        {"instrument_id": {"venue": "xshe", "stable_key": "000002"}, "value": "0"}
    )
    extra_instrument = replace(
        event, payload={"schema_version": 1, "candidate": candidate}
    )
    with pytest.raises(ValueError, match="commitment"):
        authority.validate_target_stream(
            PrecomputedTargetStream(stream.stream_key, (extra_instrument,))
        )

    extra = replace(
        event,
        event_id="cn-a-share-fixed-singleton-zero-target-extra-v1",
        source_sequence=type(event.source_sequence)(2),
        source_hash=canonical_sha256({"extra": True}),
    )
    with pytest.raises(ValueError, match="commitment"):
        authority.validate_target_stream(PrecomputedTargetStream(stream.stream_key, (event, extra)))

    mutations = (
        replace(event, event_time=UtcInstant(event.event_time.epoch_nanoseconds + 1), available_time=UtcInstant(event.available_time.epoch_nanoseconds + 1)),
        replace(event, phase=type(event.phase)(31, "strategy_decision")),
        replace(event, source_key="wrong-source"),
        replace(event, source_hash="sha256:" + "0" * 64),
        replace(event, revision_id="changed"),
        replace(event, event_id="changed-event"),
    )
    for mutated in mutations:
        with pytest.raises(ValueError, match="commitment"):
            authority.validate_target_stream(PrecomputedTargetStream(stream.stream_key, (mutated,)))

    with pytest.raises(ValueError, match="commitment"):
        authority.validate_target_stream(
            PrecomputedTargetStream("changed-stream", (replace(event, stream_key="changed-stream"),))
        )


class _TargetStreamSubclass(PrecomputedTargetStream):
    pass


def test_target_validator_rejects_subclass_and_target_fails_before_risk_capacity() -> None:
    authority = _authority()
    stream = authority.target_commitment.stream
    with pytest.raises(TypeError, match="exact PrecomputedTargetStream"):
        authority.validate_target_stream(_TargetStreamSubclass(stream.stream_key, stream.events))

    event = stream.events[0]
    candidate = _candidate_payload(event)
    candidate["targets"][0]["value"] = "1"
    nonzero = PrecomputedTargetStream(
        stream.stream_key,
        (replace(event, payload={"schema_version": 1, "candidate": candidate}),),
    )
    with pytest.raises(ValueError, match="commitment"):
        authority.validate_target_stream(nonzero)

    # If a nonzero target bypassed the exact target validator, the independent
    # order-capacity gate still rejects the first proposed order.
    assert authority.account_risk_policy.order_capacity_limit == 0
    source = evaluation_input()
    source_policy = source.account_risk_policy
    zero_capacity_policy = type(source_policy).create(
        policy_key=source_policy.policy_key,
        policy_version=source_policy.policy_version,
        account_id=source_policy.account_id,
        venue_id=source_policy.venue_id,
        allowed_sides=source_policy.allowed_sides,
        allowed_position_effects=source_policy.allowed_position_effects,
        allowed_reduce_only_values=source_policy.allowed_reduce_only_values,
        fee_reserve_funding_source=source_policy.fee_reserve_funding_source,
        order_capacity_limit=authority.account_risk_policy.order_capacity_limit,
        exposure_capacity_limits=source_policy.exposure_capacity_limits,
    )
    risk_outcome = PreTradeRiskEvaluator().evaluate(
        replace(source, account_risk_policy=zero_capacity_policy)
    )
    assert risk_outcome.approval is None
    assert risk_outcome.rejection is not None
    assert PreTradeRiskReasonCode.ORDER_CAPACITY in {
        check.reason_code
        for check in risk_outcome.rejection.checks
        if not check.approved
    }


def test_authority_exact_reconstruction_rejects_nested_mutation_and_bypass() -> None:
    authority = _authority()
    with pytest.raises(ValueError, match="exact reconstruction"):
        replace(authority, decision_grade_eligible=False)
    with pytest.raises(ValueError, match="authority_hash"):
        replace(authority, authority_hash="sha256:" + "0" * 64)

    mutated = _authority()
    object.__setattr__(
        mutated.market_registration.implementation.component_manifest[0],
        "component_digest",
        "sha256:" + "0" * 64,
    )
    with pytest.raises(ValueError, match="exact reconstruction"):
        mutated.to_canonical_dict()

    mutated = _authority()
    object.__setattr__(
        mutated.target_commitment.stream.events[0], "source_key", "bypassed-source"
    )
    with pytest.raises(ValueError, match="exact reconstruction"):
        mutated.to_canonical_dict()

    mutated = _authority()
    object.__setattr__(
        mutated.build_manifest.artifacts[0], "content_hash", "sha256:" + "0" * 64
    )
    with pytest.raises(ValueError, match="exact reconstruction"):
        mutated.to_canonical_dict()

    forged_case = object.__new__(type(authority.case))
    with pytest.raises(AttributeError):
        replace(authority, case=forged_case)


def test_source_identity_mutation_changes_semantics_and_fails_accepted_constants() -> None:
    authority = _authority()
    source = authority.source_identities[0]
    changed = replace(source, report_hash="sha256:" + "0" * 64)
    assert canonical_sha256((changed, *authority.source_identities[1:])) != canonical_sha256(
        authority.source_identities
    )
    with pytest.raises(ValueError, match="exact reconstruction"):
        replace(authority, source_identities=(changed, *authority.source_identities[1:]))


def test_profile_and_build_resolve_decision_grade_with_exact_two_capabilities() -> None:
    authority = _authority()
    bundle = _bundle(authority)
    assert {value.identity for value in bundle.capabilities} == {
        "precomputed_target_stream@1",
        "tushare_cn_a_share.daily-publications@1",
    }
    assert not {
        "bar_open",
        "corporate_actions",
        "account.financial-event",
    }.intersection(value.key for value in bundle.capabilities)

    outcome = ProfileResolver().resolve(
        request=_request(authority, bundle),
        registry=_registry(authority),
        market_bundle_manifest=bundle,
        build_artifact_manifest=authority.build_manifest,
    )

    assert outcome.failure is None
    assert outcome.resolved is not None
    report = outcome.resolved.environment.compatibility_report
    assert report.compatible
    assert report.allowed_grade is RequestedResultGrade.DECISION_GRADE
    assert report.limitations == ()
    assert outcome.resolved.environment.limitations == ()
    assert not outcome.resolved.environment.deployment_authorized


def test_resolution_rejects_missing_editable_and_hash_mismatched_builds() -> None:
    authority = _authority()
    bundle = _bundle(authority)
    build = authority.build_manifest

    missing = replace(
        build,
        artifacts=tuple(
            value
            for value in build.artifacts
            if value.artifact_key != authority.market_registration.profile_key
        ),
    )
    editable_artifact = replace(
        build.artifacts[0], install_mode=ArtifactInstallMode.EDITABLE
    )
    editable = replace(
        build,
        artifacts=(editable_artifact, *build.artifacts[1:]),
    )
    assert not editable.decision_grade_eligible
    assert editable.limitations

    for candidate, request_build in (
        (missing, missing),
        (editable, editable),
        (build, replace(build, dependency_lock_hash="sha256:" + "0" * 64)),
    ):
        outcome = ProfileResolver().resolve(
            request=_request(authority, bundle, request_build),
            registry=_registry(authority),
            market_bundle_manifest=bundle,
            build_artifact_manifest=candidate,
        )
        assert outcome.resolved is None
        assert outcome.failure is not None


def test_existing_development_profile_bytes_and_public_root_are_unchanged() -> None:
    development = (
        ROOT
        / "packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_profile.py"
    )
    public_root = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/__init__.py"
    assert hashlib.sha256(development.read_bytes()).hexdigest() == (
        "f5ec4c572b6bb84fe94997051b9d382be6e3a0a9e227b1fea56a193113114a3c"
    )
    assert hashlib.sha256(public_root.read_bytes()).hexdigest() == (
        "05b1e1520ac31e8b094de195962ffea395441c823286ca95e868add22a5bfe02"
    )
    assert "CnAShareFixedSingletonNoTradeAuthorityV1" not in public_root.read_text(
        encoding="utf-8"
    )
