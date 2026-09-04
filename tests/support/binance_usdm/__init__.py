from __future__ import annotations

from dataclasses import dataclass, replace

from crypto_quant_backtest import (
    ArtifactInstallMode,
    BacktestProfileRegistry,
    BinanceUsdmProfileComposer,
    BinanceUsdmProfileCompositionRequest,
    BuildArtifactManifest,
    BuildArtifactRef,
    BuildArtifactRole,
    DeterministicBarEngine,
    DeterministicTimeline,
    ExecutionCaseComposer,
    ExecutionCaseIdentityFactory,
    ExecutionCaseIdentityRule,
    ExecutionCaseSemanticSpec,
    FinancialDispatchOutcome,
    FinancialDispatchResult,
    ProfileResolver,
    RequestedResultGrade,
    ResolvedBacktestRequest,
    ResolvedExecutionCase,
    SourceTreeState,
)
from crypto_quant_domain import CurrencyId, IdentityNamespace
from crypto_quant_market_data import InMemoryMarketBundleReader, MarketBundleRef
from tests.runtime.resolution import _fixtures as resolution_fixtures
from tests.support.synthetic_market.linear_perpetual import (
    SyntheticLinearExecutionCaseBuilder,
    SyntheticLinearFinancialDispatcher,
    build_execution_case,
)


_USDT = CurrencyId("USDT")
_ROLE_ALIASES = {
    "position_accounting.1": "linear_position_transition",
    "funding_accounting": "funding_settlement",
    "margin_projection.long": "account_margin_projection",
    "liquidation_audit.long": "liquidation_audit",
    "final_snapshot": "portfolio_snapshot",
}


def _composed(request: BinanceUsdmProfileCompositionRequest):
    outcome = BinanceUsdmProfileComposer().compose(request)
    if outcome.result is None:
        raise ValueError(f"Binance USD-M profile composition failed: {outcome.failure!r}")
    return outcome.result


def _rename_outcome(outcome: FinancialDispatchOutcome) -> FinancialDispatchOutcome:
    if outcome.result is None:
        return outcome
    result = outcome.result
    artifacts = tuple(
        replace(artifact, role=_ROLE_ALIASES.get(artifact.role, artifact.role))
        for artifact in result.artifacts
    )
    renamed = FinancialDispatchResult(
        result.dispatcher_spec,
        result.source_event_id,
        result.journal_entries,
        result.position_lot_books,
        artifacts,
        result.snapshot,
    )
    return FinancialDispatchOutcome(
        outcome.dispatcher_spec,
        outcome.input_hash,
        result=renamed,
    )


class BinanceUsdmDevelopmentFinancialDispatcher(SyntheticLinearFinancialDispatcher):
    def __init__(self, request: BinanceUsdmProfileCompositionRequest) -> None:
        super().__init__()
        self._spec = _composed(request).financial_dispatcher_spec

    def book_fill(self, plan, fill, state_view, /):
        return _rename_outcome(super().book_fill(plan, fill, state_view))

    def book_fee(self, plan, fill, assessment, state_view, /):
        return _rename_outcome(super().book_fee(plan, fill, assessment, state_view))

    def dispatch_scheduled_event(self, event, state_view, /):
        return _rename_outcome(super().dispatch_scheduled_event(event, state_view))

    def project_final_snapshot(self, plan, state_view, /):
        return _rename_outcome(super().project_final_snapshot(plan, state_view))


def _adapt_case(
    case: ResolvedExecutionCase,
    request: BinanceUsdmProfileCompositionRequest,
    semantic_spec_hash: str,
) -> ResolvedExecutionCase:
    profile = _composed(request)
    spec = profile.financial_dispatcher_spec
    base_reader = case.timeline.reader
    capabilities = tuple(
        sorted(
            set(base_reader.manifest.capabilities)
            | set(profile.market_registration.required_bundle_capabilities)
            | set(profile.simulation_registration.required_bundle_capabilities),
            key=lambda value: value.identity,
        )
    )
    reader = InMemoryMarketBundleReader.build(
        bundle_key="crypto.binance_usdm.development-journey.v1",
        schema_version=1,
        coverage_start=base_reader.manifest.coverage_start,
        coverage_end_exclusive=base_reader.manifest.coverage_end_exclusive,
        instrument_catalog_hash=base_reader.manifest.instrument_catalog_hash,
        capabilities=capabilities,
        streams=base_reader.streams,
    )
    timeline = DeterministicTimeline.open(
        reader=reader,
        stream_keys=case.timeline.stream_keys,
        window=case.timeline.window,
    )
    if not isinstance(timeline, DeterministicTimeline):
        raise ValueError("Binance USD-M development timeline failed")

    bars = tuple(
        replace(
            bar,
            accounting_plan=replace(
                bar.accounting_plan,
                position_accounting_component=spec.position_accounting_component,
                expected_artifact_roles=tuple(
                    _ROLE_ALIASES.get(role, role)
                    for role in bar.accounting_plan.expected_artifact_roles
                ),
            ),
        )
        for bar in case.bar_executions
    )
    scheduled = tuple(
        replace(
            event,
            component_keys=(spec.financing_component.component_key,)
            if event.operation_key == "funding"
            else (
                spec.margin_component.component_key,
                spec.liquidation_audit_component.component_key,
            ),
            expected_artifact_roles=tuple(
                _ROLE_ALIASES.get(role, role)
                for role in event.expected_artifact_roles
            ),
        )
        for event in case.financial_dispatch_plan.scheduled_account_events
    )
    expected_roles = tuple(
        sorted(
            _ROLE_ALIASES.get(role, role)
            for role in case.financial_dispatch_plan.expected_artifact_roles
        )
    )
    financial_plan = replace(
        case.financial_dispatch_plan,
        dispatcher_spec=spec,
        scheduled_account_events=scheduled,
        expected_artifact_roles=expected_roles,
    )
    return replace(
        case,
        semantic_spec_hash=semantic_spec_hash,
        timeline=timeline,
        bar_executions=bars,
        financial_dispatch_plan=financial_plan,
    )


@dataclass(frozen=True, slots=True)
class _BinanceExecutionCaseBuilder:
    request: BinanceUsdmProfileCompositionRequest
    batch_size: int = 1

    def identity_plan(self) -> tuple[ExecutionCaseIdentityRule, ...]:
        return SyntheticLinearExecutionCaseBuilder(self.batch_size).identity_plan()

    def semantic_spec(self) -> ExecutionCaseSemanticSpec:
        template = _adapt_case(
            build_execution_case(batch_size=self.batch_size),
            self.request,
            "sha256:" + "9a" * 32,
        )
        return ExecutionCaseComposer.semantic_spec_from_case(
            template,
            spec_key="crypto.binance_usdm.development-journey.execution-case.v1",
            spec_version=1,
            identity_namespace=IdentityNamespace("backtest", "1"),
            identity_plan=self.identity_plan(),
        )

    def build(
        self,
        identities: ExecutionCaseIdentityFactory,
        semantic_spec_hash: str,
    ) -> ResolvedExecutionCase:
        case = SyntheticLinearExecutionCaseBuilder(self.batch_size).build(
            identities,
            semantic_spec_hash,
        )
        return _adapt_case(case, self.request, semantic_spec_hash)


def _build_manifest(profile) -> BuildArtifactManifest:
    base = resolution_fixtures.build_manifest()
    registrations = (
        profile.market_registration,
        profile.simulation_registration,
        profile.execution_account_registration,
    )
    non_profiles = tuple(
        artifact
        for artifact in base.artifacts
        if artifact.role is not BuildArtifactRole.PROFILE_COMPONENT
    )
    profile_artifacts = tuple(
        BuildArtifactRef(
            BuildArtifactRole.PROFILE_COMPONENT,
            registration.profile_key,
            str(registration.profile_version),
            ArtifactInstallMode.WHEEL,
            SourceTreeState.CLEAN,
            registration.profile_digest,
            None,
        )
        for registration in registrations
    )
    return replace(base, artifacts=non_profiles + profile_artifacts)


def build_binance_usdm_resolved_request(
    request: BinanceUsdmProfileCompositionRequest,
    *,
    requested_grade: RequestedResultGrade = RequestedResultGrade.DEVELOPMENT,
    timeline_batch_size: int = 1,
) -> ResolvedBacktestRequest:
    profile = _composed(request)
    builder = _BinanceExecutionCaseBuilder(request, timeline_batch_size)
    spec = builder.semantic_spec()
    template = _adapt_case(
        build_execution_case(batch_size=timeline_batch_size),
        request,
        spec.semantic_spec_hash,
    )
    manifest = _build_manifest(profile)
    base_request = resolution_fixtures.request(
        manifest,
        bundle=template.timeline.reader.manifest,
    )
    backtest_request = replace(
        base_request,
        experiment_id="binance-usdm-development-journey",
        timeline_window=template.timeline.window,
        market_semantics_profile_key=profile.market_registration.profile_key,
        simulation_profile_key=profile.simulation_registration.profile_key,
        execution_account_profile_key=profile.execution_account_registration.profile_key,
        execution_account_id=profile.execution_account.account_id,
        reporting_currency=_USDT,
        market_bundle_ref=MarketBundleRef.from_manifest(template.timeline.reader.manifest),
        target_stream_digest=template.target_stream.target_stream_digest,
        execution_case_semantic_hash=spec.semantic_spec_hash,
        build_artifact_manifest_hash=manifest.manifest_hash,
        result_grade_requested=requested_grade,
    )
    outcome = ProfileResolver().resolve(
        request=backtest_request,
        registry=profile.profile_registry,
        market_bundle_manifest=template.timeline.reader.manifest,
        build_artifact_manifest=manifest,
    )
    if outcome.resolved is None:
        if requested_grade is RequestedResultGrade.DECISION_GRADE:
            raise ValueError("decision-grade Binance USD-M profile resolution failed")
        raise ValueError(f"Binance USD-M profile resolution failed: {outcome.failure!r}")
    return outcome.resolved


def build_binance_usdm_execution_case(
    request: BinanceUsdmProfileCompositionRequest,
    *,
    timeline_batch_size: int = 1,
    resolved_request: ResolvedBacktestRequest | None = None,
) -> ResolvedExecutionCase:
    resolved = resolved_request or build_binance_usdm_resolved_request(
        request,
        timeline_batch_size=timeline_batch_size,
    )
    return ExecutionCaseComposer().compose(
        resolved_request=resolved,
        builder=_BinanceExecutionCaseBuilder(request, timeline_batch_size),
    )


def run_binance_usdm_development_journey():
    from tests.runtime.profiles.binance_usdm._fixtures import composition_request

    request = composition_request()
    resolved = build_binance_usdm_resolved_request(request)
    case = build_binance_usdm_execution_case(request, resolved_request=resolved)
    outcome = DeterministicBarEngine(
        BinanceUsdmDevelopmentFinancialDispatcher(request)
    ).run(case)
    if outcome.result is None:
        raise ValueError(f"Binance USD-M development journey failed: {outcome.failure!r}")
    return outcome.result


__all__ = [
    "BinanceUsdmDevelopmentFinancialDispatcher",
    "build_binance_usdm_execution_case",
    "build_binance_usdm_resolved_request",
    "run_binance_usdm_development_journey",
]
