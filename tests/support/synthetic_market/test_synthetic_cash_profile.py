from __future__ import annotations

from pathlib import Path

from crypto_quant_backtest import (
    CloseoutPolicy,
    ExecutionModel,
    LatencyModel,
    LiquidationAuditModel,
    LiquidityModel,
    SlippageModel,
)
from crypto_quant_trading import (
    CorporateActionModel,
    CurrencyValuationPolicy,
    FeeAssessmentPolicy,
    FinancingModel,
    InstrumentModel,
    LiquidationRules,
    MarginModel,
    OrderRuleModel,
    PositionAccountingModel,
    SessionModel,
    SettlementModel,
    TaxPolicy,
)

from tests.support.synthetic_market import (
    SYNTHETIC_PROFILE_KEY,
    SYNTHETIC_PROFILE_LIMITATION,
    SyntheticCashDevelopmentProfile,
    SyntheticPortRequest,
    SyntheticProfileLookupFailureCode,
    TestProfileRegistry,
    build_synthetic_bundle,
    build_synthetic_execution_case,
    build_synthetic_target_stream,
)


ROOT = Path(__file__).resolve().parents[3]


def _development_profile() -> SyntheticCashDevelopmentProfile:
    lookup = TestProfileRegistry(allow_development_profiles=True).lookup(
        SYNTHETIC_PROFILE_KEY
    )
    assert lookup.profile is not None
    assert lookup.failure is None
    return lookup.profile


def test_default_registry_rejects_the_development_profile() -> None:
    lookup = TestProfileRegistry().lookup(SYNTHETIC_PROFILE_KEY)

    assert lookup.profile is None
    assert lookup.failure is not None
    assert (
        lookup.failure.code
        is SyntheticProfileLookupFailureCode.DEVELOPMENT_PROFILE_NOT_ALLOWED
    )
    assert lookup.failure.profile_key == SYNTHETIC_PROFILE_KEY
    assert not hasattr(SyntheticCashDevelopmentProfile, "create")


def test_unknown_profile_fails_without_fallback() -> None:
    lookup = TestProfileRegistry(allow_development_profiles=True).lookup(
        "unknown.profile.v1"
    )

    assert lookup.profile is None
    assert lookup.failure is not None
    assert lookup.failure.code is SyntheticProfileLookupFailureCode.PROFILE_NOT_FOUND


def test_profile_is_explicitly_development_only_and_not_deployment_authorized() -> None:
    profile = _development_profile()

    assert profile.profile_key == SYNTHETIC_PROFILE_KEY
    assert profile.profile_version == 1
    expected_limitations = tuple([SYNTHETIC_PROFILE_LIMITATION])
    assert profile.grade == "development"
    assert profile.limitations == expected_limitations
    assert not profile.decision_grade_eligible
    assert not profile.deployment_authorized


def test_market_profile_exactly_implements_all_kernel_ports() -> None:
    market = _development_profile().market_semantics
    bindings = (
        (market.session_model, SessionModel, "resolve_session"),
        (market.instrument_model, InstrumentModel, "resolve_instrument"),
        (market.order_rule_model, OrderRuleModel, "resolve_order_rules"),
        (market.fee_assessment_policy, FeeAssessmentPolicy, "assess_fees"),
        (market.tax_policy, TaxPolicy, "assess_taxes"),
        (market.settlement_model, SettlementModel, "resolve_settlement"),
        (
            market.position_accounting_model,
            PositionAccountingModel,
            "translate_position_fact",
        ),
        (market.financing_model, FinancingModel, "assess_financing"),
        (market.margin_model, MarginModel, "evaluate_margin"),
        (market.liquidation_rules, LiquidationRules, "evaluate_liquidation"),
        (
            market.corporate_action_model,
            CorporateActionModel,
            "apply_corporate_action",
        ),
        (
            market.currency_valuation_policy,
            CurrencyValuationPolicy,
            "select_valuation_path",
        ),
    )

    for component, protocol, method_name in bindings:
        assert isinstance(component, protocol)
        outcome = getattr(component, method_name)(
            SyntheticPortRequest(method_name, "fixture-request")
        )
        assert outcome.result is not None
        assert outcome.failure is None
        assert outcome.component_ref == component.component_ref

    refs = market.component_manifest
    assert len(refs) == 12
    assert len({ref.port_type for ref in refs}) == 12
    assert tuple(sorted(ref.port_type.value for ref in refs)) == tuple(
        ref.port_type.value for ref in refs
    )


def test_simulation_profile_exactly_implements_all_simulation_ports() -> None:
    simulation = _development_profile().simulation

    assert isinstance(simulation.execution_model, ExecutionModel)
    assert isinstance(simulation.slippage_model, SlippageModel)
    assert isinstance(simulation.latency_model, LatencyModel)
    assert isinstance(simulation.liquidity_model, LiquidityModel)
    assert isinstance(simulation.liquidation_audit_model, LiquidationAuditModel)
    assert isinstance(simulation.closeout_policy, CloseoutPolicy)

    generic_bindings = (
        (simulation.latency_model, "resolve_latency"),
        (simulation.liquidity_model, "evaluate_liquidity"),
        (simulation.liquidation_audit_model, "audit_liquidation"),
    )
    for component, method_name in generic_bindings:
        outcome = getattr(component, method_name)(
            SyntheticPortRequest(method_name, "fixture-request")
        )
        assert outcome.result is not None
        assert outcome.failure is None
        assert outcome.component_ref == component.spec().component_ref

    refs = simulation.component_manifest
    assert len(refs) == 6
    assert len({ref.port_type for ref in refs}) == 6
    assert tuple(sorted(ref.port_type.value for ref in refs)) == tuple(
        ref.port_type.value for ref in refs
    )


def test_offline_factories_are_stable_and_use_the_resolved_profile() -> None:
    profile = _development_profile()

    first_bundle = build_synthetic_bundle(profile)
    second_bundle = build_synthetic_bundle(profile)
    first_targets = build_synthetic_target_stream(profile)
    second_targets = build_synthetic_target_stream(profile)
    first_case = build_synthetic_execution_case(profile, timeline_batch_size=1)
    second_case = build_synthetic_execution_case(profile, timeline_batch_size=10)

    assert first_bundle.bundle_ref == second_bundle.bundle_ref
    assert first_targets.target_stream_digest == second_targets.target_stream_digest
    assert first_case.case_hash == second_case.case_hash
    assert first_case.timeline.reader.bundle_ref == first_bundle.bundle_ref
    assert first_case.target_stream == first_targets
    assert (
        first_case.execution_model.component_ref
        == profile.simulation.execution_model.component_ref
    )
    assert (
        first_case.bar_executions[0].slippage_model.component_ref
        == profile.simulation.slippage_model.component_ref
    )
    assert (
        first_case.closeout_policy.spec().component_ref
        == profile.simulation.closeout_policy.spec().component_ref
    )


def test_production_packages_have_no_synthetic_profile_branch() -> None:
    forbidden = (SYNTHETIC_PROFILE_KEY, SYNTHETIC_PROFILE_LIMITATION)
    for package_root in (ROOT / "packages").iterdir():
        source_root = package_root / "src"
        if not source_root.exists():
            continue
        for path in source_root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            for marker in forbidden:
                assert marker not in source, f"synthetic branch leaked into {path}"
