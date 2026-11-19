"""Concrete public preparation for native shared-CNY DEVELOPMENT portfolios.

Definition precedes the request. Uses the sole catalog/registry/resolver and
economic attempt writer/publisher; never converts diagnostic Case/Result values.
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
from .cn_a_share_portfolio_economic_case_v1 import (
    _native_initial_economic_financial_state_v1, _read_economic_opening_sources_v1,
    _economic_identity_plan_v1, _bind_economic_portfolio_sources_v1,
    _validate_economic_coordinates_v1, _read_exact_economic_source_v1,
)
from .cn_a_share_portfolio_economic_definition_v1 import CnASharePortfolioEconomicDevelopmentInputsV1
from .composition import _compose_profile_portfolio_economic_execution_case
from .execution import BAR_OPEN_CAPABILITY
from .execution_inputs import (
    BacktestExecutionRequest, _EXECUTION_INPUT_CATALOG, _DecodedExecutionInputBundleV9,
    _materialize_execution_input_bundle_v9,
)
from .facade import BacktestRuntime
from .ports import SimulationComponentRef, SimulationPortType
from .profile_portfolio_execution import (
    _ECONOMIC_BOUNDED_SIGNAL_SPEC_VERSION, _ECONOMIC_SEGMENTED_OPENINGS_SPEC_VERSION, _ECONOMIC_SEGMENTED_SPECS,
    _ProfilePortfolioExecutionPlanV2, _ResolvedProfilePortfolioCaseV2,
    _profile_portfolio_economic_semantic_spec_from_case_v1,
)
from .request_registration import BacktestRequestRef
from .resolution import (
    BacktestProfileRegistry, BacktestRequest, BuildArtifactManifest, ProfileResolver,
    MarketSemanticsProfileRegistration, SimulationProfileRegistration,
    ExecutionAccountProfileRegistration, RequestedResultGrade, StrategyFamily,
)
from .target_repository import BacktestTargetStreamRepository
from .timeline import DeterministicTimelineV2

_PREFIX = "cn.portfolio.shared-cny.economic.development.v1"
_LIMITATIONS = tuple(sorted(("account_fee_assumptions_not_broker_authority",
    "cash_dividend_declared_model_inputs_not_source_qualification", "development_only",
    "full_fill_or_reject_no_partial_fills", "historical_source_availability_unqualified",
    "known_tax_unpaid_reserve_no_deferred_tax_engine", "modeled_1500_payment_tax_timing_not_receipt_authority",
    "modeled_shared_cny_paper_account_only", "no_validation_live_or_deployment_authority",
    "simulated_ledger_register_not_broker_chinaclear", "slippage_development_scenario_not_calibrated_capacity")))


@dataclass(frozen=True, slots=True)
class _NativeEconomicPortfolioProfileV1:
    kind: str
    definition_hash: str
    component_manifest: tuple
    spec_version: int = 1

    def __post_init__(self):
        if type(self.kind) is not str or self.kind not in {"market", "simulation", "account"}:
            raise ValueError("economic profile kind must be fixed market/simulation/account")
        if type(self.spec_version) is not int or self.spec_version not in (1, 2, *_ECONOMIC_SEGMENTED_SPECS):
            raise ValueError("unsupported economic V1 profile spec version")
        if type(self.component_manifest) is not tuple:
            raise TypeError("economic component manifest must be exact tuple")
        if type(self.definition_hash) is not str or len(self.definition_hash) != 71 or not self.definition_hash.startswith("sha256:"):
            raise ValueError("economic profile definition hash must be canonical")

    @property
    def profile_digest(self) -> str:
        return d.canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_economic_" + self.kind + "_profile", "schema_version": self.spec_version,
            "definition_hash": self.definition_hash, "component_manifest": self.component_manifest,
            "development_only": True, "trade_authorized": False}

    def build_portfolio_engine(self, *, case: _ResolvedProfilePortfolioCaseV2,
        artifact_reader: ArtifactEnvelopeReader,
    ):
        from .cn_a_share_portfolio_economic_engine_v1 import _CnASharePortfolioEconomicEngineV1
        if type(case) is not _ResolvedProfilePortfolioCaseV2:
            raise TypeError("economic profile requires exact CaseV2")
        if (self.kind != "market" or d.canonical_sha256(case.execution_case_plan.definition) != self.definition_hash
                or case.semantic_spec is None or case.semantic_spec.spec_version != self.spec_version):
            raise ValueError("native portfolio profile/whole-definition binding mismatch")
        _bind_economic_portfolio_sources_v1(case, artifact_reader)
        return _CnASharePortfolioEconomicEngineV1(artifact_reader=artifact_reader)


def _require_opening_proof_version(version: int) -> None:
    if type(version) is not int or version not in (1, 2):
        raise ValueError("economic V1 opening_proof_version must be 1 or 2")


def _registry(inputs: CnASharePortfolioEconomicDevelopmentInputsV1, *, spec_version: int = 1) -> BacktestProfileRegistry:
    definition_hash = d.canonical_sha256(inputs.definition())
    market_refs = tuple(t.ProfileComponentRef(port, _PREFIX + ".native." + port.value, 1,
        d.canonical_sha256({"definition": definition_hash, "port": port.value, "native_version": 1}))
        for port in sorted(t.ProfilePortType, key=lambda port: port.value))
    simulation_refs = tuple(SimulationComponentRef(port, _PREFIX + "." + port.value, 1,
        d.canonical_sha256({"definition": definition_hash, "simulation_port": port.value,
            "policy": "economic_full_fill_known_tax_v1"}))
        for port in sorted(SimulationPortType, key=lambda port: port.value))
    market = _NativeEconomicPortfolioProfileV1("market", definition_hash, market_refs, spec_version)
    simulation = _NativeEconomicPortfolioProfileV1("simulation", definition_hash, simulation_refs, spec_version)
    account = _NativeEconomicPortfolioProfileV1("account", definition_hash, (), spec_version)
    venue, grade = "cn-a-share-shared-cny", RequestedResultGrade.DEVELOPMENT
    return BacktestProfileRegistry((MarketSemanticsProfileRegistration(_PREFIX + ".market", spec_version,
        market.profile_digest, market, venue, (BAR_OPEN_CAPABILITY,), market_refs, grade, _LIMITATIONS, False),),
        (SimulationProfileRegistration(_PREFIX + ".simulation", spec_version, simulation.profile_digest, simulation,
            "bar", (StrategyFamily.PRECOMPUTED_TARGET,), (BAR_OPEN_CAPABILITY,), simulation_refs,
            grade, _LIMITATIONS, False),),
        (ExecutionAccountProfileRegistration(_PREFIX + ".account", spec_version, account.profile_digest, account,
            inputs.scope.account_id, venue, "cash", "none", (d.CurrencyId("CNY"),), grade, _LIMITATIONS, False),))


def prepare_cn_a_share_portfolio_economic_development_backtest(
    *, request_intent: CashDevelopmentRequestIntent,
    provider_inputs: CnASharePortfolioEconomicDevelopmentInputsV1,
    build_artifact_manifest: BuildArtifactManifest,
    artifact_reader: ArtifactEnvelopeReader, artifact_publisher: ArtifactEnvelopePublisher,
    market_reader: MarketBundleReader, publication_root: Path, opening_proof_version: int = 1,
    segmented_openings: bool = False, bounded_signal_identity: bool = False,
) -> PreparedBacktestExecution:
    """Prepare frozen V1 sources; segmented openings require compact proofs."""
    _require_opening_proof_version(opening_proof_version)
    if type(segmented_openings) is not bool or (segmented_openings and opening_proof_version != 2):
        raise ValueError("segmented economic openings require compact proof version 2")
    if type(bounded_signal_identity) is not bool or (bounded_signal_identity and not segmented_openings):
        raise ValueError("bounded economic identity requires segmented openings")
    spec_version = (_ECONOMIC_BOUNDED_SIGNAL_SPEC_VERSION if bounded_signal_identity else
        _ECONOMIC_SEGMENTED_OPENINGS_SPEC_VERSION if segmented_openings else opening_proof_version)
    if (type(request_intent) is not CashDevelopmentRequestIntent
            or type(provider_inputs) is not CnASharePortfolioEconomicDevelopmentInputsV1
            or type(build_artifact_manifest) is not BuildArtifactManifest):
        raise TypeError("economic portfolio prepare needs exact immutable public inputs")
    if (not isinstance(market_reader, MarketBundleReader) or not isinstance(publication_root, Path)
            or request_intent.execution_account_id != provider_inputs.scope.account_id
            or request_intent.reporting_currency != d.CurrencyId("CNY")
            or market_reader.bundle_ref != provider_inputs.scope.market_bundle_ref):
        raise ValueError("economic portfolio request/account/CNY/market mismatch")
    _validate_economic_coordinates_v1(provider_inputs, request_intent.timeline_window)
    target = BacktestTargetStreamRepository(reader=artifact_reader).load(provider_inputs.scope.target_stream_ref).target_stream
    for action in provider_inputs.dividend_actions.actions:
        for ref in action.source_evidence_refs:
            _read_exact_economic_source_v1(artifact_reader, ref)
    openings = _read_economic_opening_sources_v1(provider_inputs, market_reader, request_intent.timeline_window,
        segmented=segmented_openings)
    action_envelope = d.ArtifactEnvelope.create("cn_a_share_cash_dividend_action_set", 1, provider_inputs.dividend_actions)
    action_ref = _publish(artifact_publisher, action_envelope)
    _verify_published(artifact_reader, action_ref, action_envelope)
    definition = provider_inputs.definition()  # Whole economic input BEFORE request.
    definition_ref = _publish(artifact_publisher, definition)
    _verify_published(artifact_reader, definition_ref, definition)
    financial, state, projection = _native_initial_economic_financial_state_v1(provider_inputs)
    plan = _ProfilePortfolioExecutionPlanV2(definition, financial, state, projection,
        (("cash_dividend_action_set", action_ref), ("definition", definition_ref),
         ("target_stream", provider_inputs.scope.target_stream_ref.to_artifact_ref())))
    timeline = DeterministicTimelineV2.open(reader=market_reader,
        stream_keys=tuple(sorted({event.stream_key for event in openings})), target_stream=target,
        window=request_intent.timeline_window)
    if type(timeline) is not DeterministicTimelineV2:
        raise ValueError("economic native embedded-target timeline rejected")
    template = _ResolvedProfilePortfolioCaseV2(_PREFIX, 1, timeline, target, 64, plan, d.canonical_sha256("unsealed"))
    spec = _profile_portfolio_economic_semantic_spec_from_case_v1(template, spec_key=_PREFIX, spec_version=spec_version,
        identity_namespace=d.IdentityNamespace("backtest", "1"),
        identity_plan=_economic_identity_plan_v1(provider_inputs, target, openings, bounded_signals=bounded_signal_identity))
    registry = _registry(provider_inputs, spec_version=spec_version)
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
        raise ValueError("economic portfolio request did not resolve: " + str(outcome.failure))
    case = _compose_profile_portfolio_economic_execution_case(resolved_request=outcome.resolved,
        market_reader=market_reader, semantic_spec=spec, target_stream=target,
        timeline_stream_keys=timeline.stream_keys, timeline_batch_size=64, execution_case_plan=plan)
    _bind_economic_portfolio_sources_v1(case, artifact_reader)
    bundle = _materialize_execution_input_bundle_v9(resolved_request=outcome.resolved, execution_case=case)
    decoded = _EXECUTION_INPUT_CATALOG.read(d.canonical_bytes(bundle))
    if decoded.envelope != bundle or type(decoded.artifact) is not _DecodedExecutionInputBundleV9:
        raise ValueError("economic input9 failed sole-catalog cold round trip")
    request_envelope = d.ArtifactEnvelope.create("backtest_request", 1, request)
    request_ref = _publish(artifact_publisher, request_envelope)
    bundle_ref = _publish(artifact_publisher, bundle)
    _verify_published(artifact_reader, request_ref, request_envelope)
    _verify_published(artifact_reader, bundle_ref, bundle)
    runtime = BacktestRuntime(registry=registry, artifact_reader=artifact_reader,
        artifact_publisher=artifact_publisher, market_reader=market_reader, publication_root=publication_root)
    return PreparedBacktestExecution(BacktestRequestRef.from_artifact_ref(request_ref),
        outcome.resolved.semantic_run_id, BacktestExecutionRequest(9, request, bundle_ref), runtime)


__all__ = ["prepare_cn_a_share_portfolio_economic_development_backtest"]
