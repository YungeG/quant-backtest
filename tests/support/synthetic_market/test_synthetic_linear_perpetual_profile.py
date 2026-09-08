from __future__ import annotations

from dataclasses import replace

import pytest

from tests.support.synthetic_market import (
    SyntheticLinearPerpetualDevelopmentProfile,
    SyntheticProfileLookupFailureCode,
    TestProfileRegistry,
    build_synthetic_linear_perpetual_execution_case,
    build_synthetic_linear_perpetual_resolved_request,
)
from tests.support.synthetic_market.linear_perpetual import LIMITATIONS, PROFILE_KEY


def test_linear_profile_requires_explicit_development_opt_in() -> None:
    rejected = TestProfileRegistry().lookup(PROFILE_KEY)
    accepted = TestProfileRegistry(allow_development_profiles=True).lookup(PROFILE_KEY)

    assert rejected.profile is None
    assert rejected.failure is not None
    assert (
        rejected.failure.code
        is SyntheticProfileLookupFailureCode.DEVELOPMENT_PROFILE_NOT_ALLOWED
    )
    assert isinstance(accepted.profile, SyntheticLinearPerpetualDevelopmentProfile)
    assert accepted.failure is None


def test_linear_profile_is_development_only_and_cannot_authorize_deployment() -> None:
    lookup = TestProfileRegistry(allow_development_profiles=True).lookup(PROFILE_KEY)
    profile = lookup.profile

    assert isinstance(profile, SyntheticLinearPerpetualDevelopmentProfile)
    assert profile.profile_key == PROFILE_KEY
    assert profile.grade == "development"
    assert profile.limitations == LIMITATIONS
    assert not profile.decision_grade_eligible
    assert not profile.deployment_authorized
    assert not hasattr(SyntheticLinearPerpetualDevelopmentProfile, "create")

    with pytest.raises(ValueError, match="cannot authorize deployment"):
        replace(profile, deployment_authorized=True)
    with pytest.raises(ValueError, match="cannot authorize deployment"):
        replace(profile, decision_grade_eligible=True)


def test_linear_resolved_request_and_case_bind_the_profile_and_identity_manifest() -> None:
    lookup = TestProfileRegistry(allow_development_profiles=True).lookup(PROFILE_KEY)
    profile = lookup.profile
    assert isinstance(profile, SyntheticLinearPerpetualDevelopmentProfile)

    resolved = build_synthetic_linear_perpetual_resolved_request(profile)
    case = build_synthetic_linear_perpetual_execution_case(
        profile,
        resolved_request=resolved,
    )

    assert resolved.request.result_grade_requested.value == "development"
    assert resolved.request.market_semantics_profile_key == f"{PROFILE_KEY}.market"
    assert resolved.request.simulation_profile_key == f"{PROFILE_KEY}.simulation"
    assert resolved.request.execution_account_profile_key == f"{PROFILE_KEY}.account"
    assert case.verify_identity_manifest(resolved.semantic_run_id)
    assert case.semantic_spec_hash == resolved.request.execution_case_semantic_hash
