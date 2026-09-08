from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import (
    ArtifactInstallMode,
    BacktestProfileRegistry,
    BacktestResolutionFailureCode,
    EnvironmentCompatibilityCheckCode,
    ProfileResolver,
    RequestedResultGrade,
    SourceTreeState,
    TimelineWindow,
)
from crypto_quant_domain import UtcInstant
from crypto_quant_market_data import MarketBundleCapability
from tests.runtime.resolution._fixtures import (
    build_manifest,
    bundle_manifest,
    bundle_variant,
    market_profile_variant,
    profile_registry,
    provenance_variant,
    request,
)


def resolve(*, registry=None, manifest=None, bundle=None, backtest_request=None):
    selected_manifest = manifest or build_manifest()
    selected_bundle = bundle or bundle_manifest()
    selected_request = backtest_request or request(selected_manifest, bundle=selected_bundle)
    return ProfileResolver().resolve(
        request=selected_request,
        registry=registry or profile_registry(),
        market_bundle_manifest=selected_bundle,
        build_artifact_manifest=selected_manifest,
    )


def test_resolves_registered_development_environment_before_engine_execution() -> None:
    outcome = resolve()

    assert outcome.failure is None
    assert outcome.resolved is not None
    resolved = outcome.resolved
    assert resolved.semantic_run_id.startswith("run_")
    assert resolved.normalized_request.request_hash == resolved.request.request_hash
    assert resolved.environment.compatibility_report.compatible
    assert resolved.environment.compatibility_report.allowed_grade == RequestedResultGrade.DEVELOPMENT
    assert resolved.environment.deployment_authorized is False
    expected_limitations = ("development_profile", "synthetic_market_profile")
    assert resolved.environment.limitations == expected_limitations
    assert resolved.environment.market_semantics.profile_key.endswith(".market")
    assert resolved.environment.simulation.profile_key.endswith(".simulation")
    assert resolved.environment.execution_account.profile_key.endswith(".account")


def test_default_production_registry_and_missing_bundle_capability_fail_closed() -> None:
    empty = resolve(registry=BacktestProfileRegistry())
    assert empty.resolved is None
    assert empty.failure is not None
    assert empty.failure.code is BacktestResolutionFailureCode.PROFILE_NOT_FOUND

    missing_capability = MarketBundleCapability("order_book_l2", 1)
    incompatible = resolve(
        registry=profile_registry(extra_market_capabilities=(missing_capability,))
    )
    assert incompatible.resolved is None
    assert incompatible.failure is not None
    assert incompatible.failure.code is BacktestResolutionFailureCode.INCOMPATIBLE_ENVIRONMENT
    assert (
        EnvironmentCompatibilityCheckCode.MARKET_BUNDLE_CAPABILITIES
        in incompatible.failure.compatibility_report.failed_codes
    )
    assert missing_capability.identity in incompatible.failure.subjects


def test_semantic_run_identity_is_sensitive_only_to_semantic_inputs() -> None:
    baseline_manifest = build_manifest()
    baseline = resolve(manifest=baseline_manifest)
    assert baseline.resolved is not None
    baseline_id = baseline.resolved.semantic_run_id

    changed_code_manifest = build_manifest(
        runtime_content_hash="sha256:" + "88" * 32
    )
    changed_code = resolve(
        manifest=changed_code_manifest,
        backtest_request=request(changed_code_manifest),
    )
    assert changed_code.resolved is not None

    changed_bundle_manifest = bundle_variant()
    changed_bundle = resolve(
        bundle=changed_bundle_manifest,
        backtest_request=request(baseline_manifest, bundle=changed_bundle_manifest),
    )
    assert changed_bundle.resolved is not None

    changed_target = resolve(
        manifest=baseline_manifest,
        backtest_request=request(
            baseline_manifest,
            target_stream_digest="sha256:" + "99" * 32,
        ),
    )
    assert changed_target.resolved is not None

    changed_market_profile = market_profile_variant()
    changed_profile_build = build_manifest(
        market_profile_digest=changed_market_profile.profile_digest
    )
    changed_profile = resolve(
        registry=profile_registry(market_profile=changed_market_profile),
        manifest=changed_profile_build,
        backtest_request=request(changed_profile_build),
    )
    assert changed_profile.resolved is not None

    provenance_only_manifest = provenance_variant(baseline_manifest)
    provenance_only = resolve(
        manifest=provenance_only_manifest,
        backtest_request=request(provenance_only_manifest),
    )
    assert provenance_only.resolved is not None

    assert changed_code.resolved.semantic_run_id != baseline_id
    assert changed_bundle.resolved.semantic_run_id != baseline_id
    assert changed_target.resolved.semantic_run_id != baseline_id
    assert changed_profile.resolved.semantic_run_id != baseline_id
    assert provenance_only_manifest.manifest_hash == baseline_manifest.manifest_hash
    assert provenance_only.resolved.semantic_run_id == baseline_id


def test_editable_unidentified_build_is_development_only_and_decision_grade_blocks() -> None:
    editable = build_manifest(
        runtime_mode=ArtifactInstallMode.EDITABLE,
        runtime_content_hash=None,
        runtime_source_state=SourceTreeState.DIRTY,
    )
    development = resolve(
        manifest=editable,
        backtest_request=request(editable),
    )
    assert development.resolved is not None
    assert development.failure is None
    assert "editable_build_artifact:crypto-quant-backtest" in (
        development.resolved.environment.limitations
    )
    assert "unidentified_build_artifact:crypto-quant-backtest" in (
        development.resolved.environment.limitations
    )

    decision_grade = resolve(
        manifest=editable,
        backtest_request=request(
            editable,
            grade=RequestedResultGrade.DECISION_GRADE,
        ),
    )
    assert decision_grade.resolved is None
    assert decision_grade.failure is not None
    assert (
        EnvironmentCompatibilityCheckCode.BUILD_ARTIFACT_IDENTITY
        in decision_grade.failure.compatibility_report.failed_codes
    )
    assert (
        EnvironmentCompatibilityCheckCode.PROFILE_GRADE
        in decision_grade.failure.compatibility_report.failed_codes
    )


def test_profile_artifact_identity_and_bundle_coverage_are_verified() -> None:
    mismatched_build = build_manifest(
        market_profile_digest="sha256:" + "aa" * 32
    )
    mismatched = resolve(
        manifest=mismatched_build,
        backtest_request=request(mismatched_build),
    )
    assert mismatched.failure is not None
    assert (
        EnvironmentCompatibilityCheckCode.PROFILE_BUILD_IDENTITY
        in mismatched.failure.compatibility_report.failed_codes
    )

    baseline_manifest = build_manifest()
    mismatched_reference = replace(
        request(baseline_manifest),
        build_artifact_manifest_hash="sha256:" + "bb" * 32,
    )
    reference_failure = resolve(
        manifest=baseline_manifest,
        backtest_request=mismatched_reference,
    )
    assert reference_failure.failure is not None
    assert (
        EnvironmentCompatibilityCheckCode.BUILD_ARTIFACT_IDENTITY
        in reference_failure.failure.compatibility_report.failed_codes
    )

    outside_window = replace(
        request(baseline_manifest),
        timeline_window=TimelineWindow(
            data_start=UtcInstant(0),
            trading_start=UtcInstant(90),
            end_exclusive=UtcInstant(500),
        ),
    )
    outside = resolve(
        manifest=baseline_manifest,
        backtest_request=outside_window,
    )
    assert outside.failure is not None
    assert (
        EnvironmentCompatibilityCheckCode.MARKET_BUNDLE_COVERAGE
        in outside.failure.compatibility_report.failed_codes
    )


def test_registry_rejects_duplicate_plane_keys() -> None:
    registry = profile_registry()
    market = registry.market_semantics_profiles[0]
    with pytest.raises(ValueError, match="duplicate market semantics profile key"):
        BacktestProfileRegistry(
            market_semantics_profiles=(market, market),
            simulation_profiles=registry.simulation_profiles,
            execution_account_profiles=registry.execution_account_profiles,
        )
