"""Concrete public preparation for native shared-CNY DEVELOPMENT portfolios.

Definition precedes the request. Uses the sole catalog/registry/resolver and
standard attempt writer/publisher; never converts diagnostic Case/Result values.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import crypto_quant_domain as d
import crypto_quant_trading as t
from crypto_quant_market_data import MarketBundleReader

from .artifact_envelope_reader import ArtifactEnvelopeReader
from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .cash_development_provider import (
    CashDevelopmentRequestIntent, PreparedBacktestExecution,
    _provider_build_manifest, _publish, _verify_published,
)
from .cn_a_share_portfolio_standard_case_v1 import (
    _native_initial_financial_state_v1, _read_opening_sources_v1,
    _standard_identity_plan_v1, _bind_standard_portfolio_sources_v1,
)
from .cn_a_share_portfolio_standard_definition_v1 import CnASharePortfolioStandardDevelopmentInputsV1
from .cn_a_share_portfolio_standard_engine_v1 import _CnASharePortfolioStandardEngineV1
from .composition import _compose_profile_portfolio_execution_case
from .execution import BAR_OPEN_CAPABILITY
from .execution_inputs import (
    BacktestExecutionRequest, _EXECUTION_INPUT_CATALOG, _DecodedExecutionInputBundleV8,
    _materialize_execution_input_bundle_v8,
)
from .facade import BacktestRuntime
from .ports import SimulationComponentRef, SimulationPortType
from .profile_portfolio_execution import (
    _ProfilePortfolioExecutionPlanV1, _ResolvedProfilePortfolioCaseV1,
    _profile_portfolio_semantic_spec_from_case,
)
from .request_registration import BacktestRequestRef
from .resolution import (
    BacktestProfileRegistry, BacktestRequest, BuildArtifactManifest, ProfileResolver,
    MarketSemanticsProfileRegistration, SimulationProfileRegistration,
    ExecutionAccountProfileRegistration, RequestedResultGrade, StrategyFamily,
)
from .target_repository import BacktestTargetStreamRepository
from .timeline import DeterministicTimelineV2

_PREFIX = "cn.portfolio.shared-cny.standard.development.v1"
_LIMITATIONS = tuple(sorted(("development_only", "modeled_shared_cny_paper_account_only",
    "historical_source_availability_unqualified", "account_fee_assumptions_not_broker_authority",
    "retained_dividends_are_fail_closed_guards_not_entitlement_model",
    "zero_slippage_full_fill_only", "no_validation_live_or_deployment_authority")))


@dataclass(frozen=True, slots=True)
class _NativePortfolioProfileV1:
    kind: str
    definition_hash: str
    component_manifest: tuple

    @property
    def profile_digest(self) -> str:
        return d.canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_standard_" + self.kind + "_profile", "schema_version": 1,
            "definition_hash": self.definition_hash, "component_manifest": self.component_manifest,
            "development_only": True, "trade_authorized": False}

    def build_portfolio_engine(self, *, case: _ResolvedProfilePortfolioCaseV1,
        artifact_reader: ArtifactEnvelopeReader,
    ) -> _CnASharePortfolioStandardEngineV1:
        if self.kind != "market" or d.canonical_sha256(case.execution_case_plan.definition) != self.definition_hash:
            raise ValueError("native portfolio profile/whole-definition binding mismatch")
        _bind_standard_portfolio_sources_v1(case, artifact_reader)
        return _CnASharePortfolioStandardEngineV1(artifact_reader=artifact_reader)


def _registry(inputs: CnASharePortfolioStandardDevelopmentInputsV1) -> BacktestProfileRegistry:
    definition_hash = d.canonical_sha256(inputs.definition())
    market_refs = tuple(t.ProfileComponentRef(port, _PREFIX + ".native." + port.value, 1,
        d.canonical_sha256({"definition": definition_hash, "port": port.value, "native_version": 1}))
        for port in sorted(t.ProfilePortType, key=lambda port: port.value))
    simulation_refs = tuple(SimulationComponentRef(port, _PREFIX + "." + port.value, 1,
        d.canonical_sha256({"definition": definition_hash, "simulation_port": port.value,
            "policy": "real-next-open-full-fill-zero-slippage-mark-to-market"}))
        for port in sorted(SimulationPortType, key=lambda port: port.value))
    market = _NativePortfolioProfileV1("market", definition_hash, market_refs)
    simulation = _NativePortfolioProfileV1("simulation", definition_hash, simulation_refs)
    account = _NativePortfolioProfileV1("account", definition_hash, ())
    venue, grade = "cn-a-share-shared-cny", RequestedResultGrade.DEVELOPMENT
    return BacktestProfileRegistry((MarketSemanticsProfileRegistration(_PREFIX + ".market", 1,
        market.profile_digest, market, venue, (BAR_OPEN_CAPABILITY,), market_refs, grade, _LIMITATIONS, False),),
        (SimulationProfileRegistration(_PREFIX + ".simulation", 1, simulation.profile_digest, simulation,
            "bar", (StrategyFamily.PRECOMPUTED_TARGET,), (BAR_OPEN_CAPABILITY,), simulation_refs,
            grade, _LIMITATIONS, False),),
        (ExecutionAccountProfileRegistration(_PREFIX + ".account", 1, account.profile_digest, account,
            inputs.scope.account_id, venue, "cash", "none", (d.CurrencyId("CNY"),), grade, _LIMITATIONS, False),))


def prepare_cn_a_share_portfolio_standard_development_backtest(
    *, request_intent: CashDevelopmentRequestIntent,
    provider_inputs: CnASharePortfolioStandardDevelopmentInputsV1,
    build_artifact_manifest: BuildArtifactManifest,
    artifact_reader: ArtifactEnvelopeReader, artifact_publisher: ArtifactEnvelopePublisher,
    market_reader: MarketBundleReader, publication_root: Path,
) -> PreparedBacktestExecution:
    """Prepare source-only inputs; execute exclusively through returned Runtime."""
    if (type(request_intent) is not CashDevelopmentRequestIntent
            or type(provider_inputs) is not CnASharePortfolioStandardDevelopmentInputsV1
            or type(build_artifact_manifest) is not BuildArtifactManifest):
        raise TypeError("standard portfolio prepare needs exact immutable public inputs")
    if (not isinstance(market_reader, MarketBundleReader) or not isinstance(publication_root, Path)
            or request_intent.execution_account_id != provider_inputs.scope.account_id
            or request_intent.reporting_currency != d.CurrencyId("CNY")
            or market_reader.bundle_ref != provider_inputs.scope.market_bundle_ref):
        raise ValueError("standard portfolio request/account/CNY/market mismatch")
    target = BacktestTargetStreamRepository(reader=artifact_reader).load(provider_inputs.scope.target_stream_ref).target_stream
    openings = _read_opening_sources_v1(provider_inputs, market_reader, request_intent.timeline_window)
    definition = provider_inputs.definition()  # Whole economic input BEFORE request.
    definition_ref = _publish(artifact_publisher, definition)
    _verify_published(artifact_reader, definition_ref, definition)
    plan = _ProfilePortfolioExecutionPlanV1(definition, _native_initial_financial_state_v1(provider_inputs),
        (("definition", definition_ref), ("target_stream", provider_inputs.scope.target_stream_ref.to_artifact_ref())))
    timeline = DeterministicTimelineV2.open(reader=market_reader,
        stream_keys=(openings[0].stream_key,), target_stream=target, window=request_intent.timeline_window)
    if type(timeline) is not DeterministicTimelineV2:
        raise ValueError("standard native embedded-target timeline rejected")
    template = _ResolvedProfilePortfolioCaseV1(_PREFIX, 1, timeline, target, 64, plan, d.canonical_sha256("unsealed"))
    spec = _profile_portfolio_semantic_spec_from_case(template, spec_key=_PREFIX, spec_version=1,
        identity_namespace=d.IdentityNamespace("backtest", "1"),
        identity_plan=_standard_identity_plan_v1(provider_inputs, target, openings))
    registry = _registry(provider_inputs)
    manifest = _provider_build_manifest(build_artifact_manifest, registry)
    request = BacktestRequest(1, request_intent.experiment_id, request_intent.timeline_window,
        _PREFIX + ".market", _PREFIX + ".simulation", _PREFIX + ".account",
        request_intent.execution_account_id, request_intent.reporting_currency,
        market_reader.bundle_ref, spec.target_stream_digest, spec.semantic_spec_hash,
        request_intent.master_random_seed, manifest.manifest_hash, StrategyFamily.PRECOMPUTED_TARGET,
        "bar", RequestedResultGrade.DEVELOPMENT)
    outcome = ProfileResolver().resolve(request=request, registry=registry,
        market_bundle_manifest=market_reader.manifest, build_artifact_manifest=manifest)
    if outcome.resolved is None:
        raise ValueError("standard portfolio request did not resolve: " + str(outcome.failure))
    case = _compose_profile_portfolio_execution_case(resolved_request=outcome.resolved,
        market_reader=market_reader, semantic_spec=spec, target_stream=target,
        timeline_stream_keys=timeline.stream_keys, timeline_batch_size=64, execution_case_plan=plan)
    _bind_standard_portfolio_sources_v1(case, artifact_reader)
    bundle = _materialize_execution_input_bundle_v8(resolved_request=outcome.resolved, execution_case=case)
    decoded = _EXECUTION_INPUT_CATALOG.read(d.canonical_bytes(bundle))
    if decoded.envelope != bundle or type(decoded.artifact) is not _DecodedExecutionInputBundleV8:
        raise ValueError("standard input8 failed sole-catalog cold round trip")
    request_envelope = d.ArtifactEnvelope.create("backtest_request", 1, request)
    request_ref = _publish(artifact_publisher, request_envelope)
    bundle_ref = _publish(artifact_publisher, bundle)
    _verify_published(artifact_reader, request_ref, request_envelope)
    _verify_published(artifact_reader, bundle_ref, bundle)
    runtime = BacktestRuntime(registry=registry, artifact_reader=artifact_reader,
        artifact_publisher=artifact_publisher, market_reader=market_reader, publication_root=publication_root)
    return PreparedBacktestExecution(BacktestRequestRef.from_artifact_ref(request_ref),
        outcome.resolved.semantic_run_id, BacktestExecutionRequest(8, request, bundle_ref), runtime)


__all__ = ["prepare_cn_a_share_portfolio_standard_development_backtest"]
