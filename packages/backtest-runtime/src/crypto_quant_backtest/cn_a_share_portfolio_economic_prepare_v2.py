"""Public source-retaining single-prestart economic DEVELOPMENT preparation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import crypto_quant_domain as d
import crypto_quant_trading as t
from crypto_quant_market_data import MarketBundleReader
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .cash_development_provider import (
    CashDevelopmentRequestIntent, PreparedBacktestExecution, _provider_build_manifest, _publish, _verify_published,
)
from .cn_a_share_portfolio_economic_definition_v2 import CnASharePortfolioEconomicDevelopmentInputsV2
from .cn_a_share_portfolio_economic_case_v1 import (
    _validate_economic_coordinates_v2, _read_economic_opening_sources_v1,
    _native_initial_economic_financial_state_v1, _economic_identity_plan_v1, _bind_economic_portfolio_sources_v1,
)
from .cn_a_share_portfolio_economic_prepare_v1 import _LIMITATIONS
from .composition import _compose_profile_portfolio_economic_execution_case
from .execution import BAR_OPEN_CAPABILITY
from .execution_inputs import (
    BacktestExecutionRequest, _EXECUTION_INPUT_CATALOG, _DecodedExecutionInputBundleV9, _materialize_execution_input_bundle_v9,
)
from .facade import BacktestRuntime
from .ports import SimulationComponentRef, SimulationPortType
from .profile_portfolio_execution import (
    _economic_profile_prefix_v1, _ProfilePortfolioExecutionPlanV2, _ResolvedProfilePortfolioCaseV2,
    _ECONOMIC_EXCLUSIVE_SETTLEMENT_SPEC_VERSION, _profile_portfolio_economic_semantic_spec_from_case_v1,
)
from .request_registration import BacktestRequestRef
from .resolution import (
    BacktestProfileRegistry, BacktestRequest, BuildArtifactManifest, ProfileResolver,
    MarketSemanticsProfileRegistration, SimulationProfileRegistration, ExecutionAccountProfileRegistration,
    RequestedResultGrade, StrategyFamily,
)
from .target_repository import BacktestTargetStreamRepository
from .timeline import DeterministicTimelineV2

_PREFIX = "cn.portfolio.shared-cny.economic.development.v2"


@dataclass(frozen=True, slots=True)
class _NativeEconomicPortfolioProfileV2:
    kind: str
    definition_hash: str
    component_manifest: tuple

    def __post_init__(self):
        if type(self.kind) is not str or self.kind not in {"market", "simulation", "account"}:
            raise ValueError("economic profile kind must be fixed market/simulation/account")
        if type(self.component_manifest) is not tuple:
            raise TypeError("economic component manifest must be exact tuple")
        if (type(self.definition_hash) is not str or len(self.definition_hash) != 71
                or not self.definition_hash.startswith("sha256:")
                or any(c not in "0123456789abcdef" for c in self.definition_hash[7:])):
            raise ValueError("economic profile definition hash must be canonical")

    @property
    def profile_digest(self) -> str:
        return d.canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_economic_" + self.kind + "_profile", "schema_version": 2,
            "definition_hash": self.definition_hash, "component_manifest": self.component_manifest,
            "development_only": True, "trade_authorized": False}

    def build_portfolio_engine(self, *, case: _ResolvedProfilePortfolioCaseV2, artifact_reader: ArtifactEnvelopeReader):
        from .cn_a_share_portfolio_economic_engine_v1 import _CnASharePortfolioEconomicEngineV1
        if type(case) is not _ResolvedProfilePortfolioCaseV2:
            raise TypeError("economic profile requires exact CaseV2")
        if (self.kind != "market" or _economic_profile_prefix_v1(case.execution_case_plan.definition) != _PREFIX
                or d.canonical_sha256(case.execution_case_plan.definition) != self.definition_hash):
            raise ValueError("native portfolio profile/whole-definition binding mismatch")
        settlement = next(ref for ref in self.component_manifest if ref.port_type is t.ProfilePortType.SETTLEMENT_MODEL)
        if case.semantic_spec is None or case.semantic_spec.spec_version != settlement.component_version:
            raise ValueError("economic V2 spec and settlement component versions differ")
        _bind_economic_portfolio_sources_v1(case, artifact_reader)
        return _CnASharePortfolioEconomicEngineV1(artifact_reader=artifact_reader)


def _registry_v2(inputs: CnASharePortfolioEconomicDevelopmentInputsV2, *,
                 spec_version: int = _ECONOMIC_EXCLUSIVE_SETTLEMENT_SPEC_VERSION) -> BacktestProfileRegistry:
    if type(inputs) is not CnASharePortfolioEconomicDevelopmentInputsV2:
        raise TypeError("economic V2 registry requires exact inputs")
    if type(spec_version) is not int or spec_version not in (1, _ECONOMIC_EXCLUSIVE_SETTLEMENT_SPEC_VERSION):
        raise ValueError("unsupported economic V2 settlement spec version")
    definition_hash = d.canonical_sha256(inputs.definition())
    market_refs = []
    for port in sorted(t.ProfilePortType, key=lambda port: port.value):
        policy = {"definition": definition_hash, "port": port.value, "native_version": 2}
        version = spec_version if port is t.ProfilePortType.SETTLEMENT_MODEL else 1
        if version == _ECONOMIC_EXCLUSIVE_SETTLEMENT_SPEC_VERSION:
            policy["settlement_window"] = "end_exclusive"
        market_refs.append(t.ProfileComponentRef(port, _PREFIX + ".native." + port.value, version, d.canonical_sha256(policy)))
    market_refs = tuple(market_refs)
    simulation_refs = tuple(SimulationComponentRef(port, _PREFIX + "." + port.value, 1,
        d.canonical_sha256({"definition": definition_hash, "simulation_port": port.value,
            "policy": "economic_single_prestart_activation_v2"}))
        for port in sorted(SimulationPortType, key=lambda port: port.value))
    market = _NativeEconomicPortfolioProfileV2("market", definition_hash, market_refs)
    simulation = _NativeEconomicPortfolioProfileV2("simulation", definition_hash, simulation_refs)
    account = _NativeEconomicPortfolioProfileV2("account", definition_hash, ())
    venue, grade = "cn-a-share-shared-cny", RequestedResultGrade.DEVELOPMENT
    return BacktestProfileRegistry((MarketSemanticsProfileRegistration(_PREFIX + ".market", 1,
        market.profile_digest, market, venue, (BAR_OPEN_CAPABILITY,), market_refs, grade, _LIMITATIONS, False),),
        (SimulationProfileRegistration(_PREFIX + ".simulation", 1, simulation.profile_digest, simulation,
            "bar", (StrategyFamily.PRECOMPUTED_TARGET,), (BAR_OPEN_CAPABILITY,), simulation_refs, grade, _LIMITATIONS, False),),
        (ExecutionAccountProfileRegistration(_PREFIX + ".account", 1, account.profile_digest, account,
            inputs.scope.account_id, venue, "cash", "none", (d.CurrencyId("CNY"),), grade, _LIMITATIONS, False),))


def prepare_cn_a_share_portfolio_economic_development_backtest_v2(
    *, request_intent: CashDevelopmentRequestIntent,
    provider_inputs: CnASharePortfolioEconomicDevelopmentInputsV2,
    build_artifact_manifest: BuildArtifactManifest,
    artifact_reader: ArtifactEnvelopeReader, artifact_publisher: ArtifactEnvelopePublisher,
    market_reader: MarketBundleReader, publication_root: Path, evidence_layout: str = "legacy",
) -> PreparedBacktestExecution:
    from ._referenced_evidence import _check_legacy_layout, _require_referenced_layout, _validate_evidence_layout

    _validate_evidence_layout(evidence_layout)
    if (type(request_intent) is not CashDevelopmentRequestIntent
            or type(provider_inputs) is not CnASharePortfolioEconomicDevelopmentInputsV2
            or type(build_artifact_manifest) is not BuildArtifactManifest):
        raise TypeError("economic portfolio prepare needs exact immutable public inputs")
    if (not isinstance(market_reader, MarketBundleReader) or not isinstance(publication_root, Path)
            or request_intent.execution_account_id != provider_inputs.scope.account_id
            or request_intent.reporting_currency != d.CurrencyId("CNY")
            or market_reader.bundle_ref != provider_inputs.scope.market_bundle_ref):
        raise ValueError("economic portfolio request/account/CNY/market mismatch")
    _validate_economic_coordinates_v2(provider_inputs, request_intent.timeline_window)
    if evidence_layout == "referenced_v1":
        _require_referenced_layout(publication_root, initialize=True)
    else:
        _check_legacy_layout(publication_root)
    target = BacktestTargetStreamRepository(reader=artifact_reader).load(provider_inputs.scope.target_stream_ref).target_stream
    if d.canonical_bytes(target) != d.canonical_bytes(provider_inputs.source_target_stream):
        raise ValueError("economic V2 retained target differs from original source stream")
    openings = _read_economic_opening_sources_v1(provider_inputs, market_reader, request_intent.timeline_window)
    action_envelope = d.ArtifactEnvelope.create("cn_a_share_cash_dividend_action_set", 1, provider_inputs.dividend_actions)
    action_ref = _publish(artifact_publisher, action_envelope)
    _verify_published(artifact_reader, action_ref, action_envelope)
    definition = provider_inputs.definition()
    definition_ref = _publish(artifact_publisher, definition)
    _verify_published(artifact_reader, definition_ref, definition)
    financial, state, projection = _native_initial_economic_financial_state_v1(provider_inputs)
    plan = _ProfilePortfolioExecutionPlanV2(definition, financial, state, projection,
        (("cash_dividend_action_set", action_ref), ("definition", definition_ref),
         ("target_stream", provider_inputs.scope.target_stream_ref.to_artifact_ref())))
    timeline = DeterministicTimelineV2.open(reader=market_reader, stream_keys=(openings[0].stream_key,),
        target_stream=target, window=request_intent.timeline_window)
    if type(timeline) is not DeterministicTimelineV2:
        raise ValueError("economic native embedded-target timeline rejected")
    template = _ResolvedProfilePortfolioCaseV2(_PREFIX, 1, timeline, target, 64, plan, d.canonical_sha256("unsealed"))
    spec = _profile_portfolio_economic_semantic_spec_from_case_v1(template, spec_key=_PREFIX,
        spec_version=_ECONOMIC_EXCLUSIVE_SETTLEMENT_SPEC_VERSION,
        identity_namespace=d.IdentityNamespace("backtest", "1"),
        identity_plan=_economic_identity_plan_v1(provider_inputs, target, openings))
    registry = _registry_v2(provider_inputs)
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
        artifact_publisher=artifact_publisher, market_reader=market_reader, publication_root=publication_root,
        evidence_layout=evidence_layout)
    return PreparedBacktestExecution(BacktestRequestRef.from_artifact_ref(request_ref), outcome.resolved.semantic_run_id,
        BacktestExecutionRequest(9, request, bundle_ref), runtime)


__all__ = ["prepare_cn_a_share_portfolio_economic_development_backtest_v2"]
