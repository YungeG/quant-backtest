"""V4 directional preparation over separately verified target-free economics."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

import crypto_quant_domain as domain
from crypto_quant_market_data import (
    LocalMarketBundleReader,
    MarketBundleManifest,
    MarketBundleReader,
    MarketBundleRef,
)

from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .binance_usdm_koru_directional_profile_v4 import (
    BinanceUsdmKoruDirectionalPlannerV4,
    BinanceUsdmKoruDirectionalTargetConsumptionV4,
    KoruDirectionalV4StrategyAuthority,
    verify_binance_usdm_koru_directional_strategy_authority_v4,
)
from .binance_usdm_tradifi_directional_case_planner_v4 import (
    plan_binance_usdm_tradifi_directional_case_v4,
)
from .binance_usdm_tradifi_preparation import BinanceUsdmTradifiProviderInputs
from .binance_usdm_tradifi_provider import (
    BinanceUsdmTradifiBarBacktestFailure,
    BinanceUsdmTradifiBarBacktestFailureCode,
)
from .cash_development_provider import PreparedBacktestExecution
from .execution_inputs import (
    BacktestExecutionRequest,
    _materialize_execution_input_bundle_v8,
)
from .facade import BacktestRuntime
from .koru_tradifi_economics_authority_v4 import (
    KoruTradifiEconomicsAuthorityV4,
    resolve_koru_tradifi_economics_authority_v4,
)
from .request_registration import BacktestRequestRef
from .resolution import RequestedResultGrade
from .timeline import TimelineWindow


def _failure(subject: str) -> BinanceUsdmTradifiBarBacktestFailure:
    return BinanceUsdmTradifiBarBacktestFailure(BinanceUsdmTradifiBarBacktestFailureCode.PREPARATION_AUTHORITY_INVALID, subject)


def _publish(publisher: ArtifactEnvelopePublisher, envelope: domain.ArtifactEnvelope) -> domain.ArtifactRef:
    ref = publisher.put(envelope=envelope)
    if type(ref) is not domain.ArtifactRef or ref != domain.ArtifactRef.from_envelope(envelope):
        raise ValueError("publisher_ref")
    return ref


def _verify_published(reader: ArtifactEnvelopeReader, ref: domain.ArtifactRef, envelope: domain.ArtifactEnvelope) -> None:
    result = reader.read(ref=ref)
    if (
        type(result) is not domain.ArtifactReadResult or result.envelope != envelope
        or result.source_bytes != domain.canonical_bytes(envelope) or result.source_hash != domain.canonical_sha256(envelope)
        or domain.ArtifactRef.from_envelope(result.envelope) != ref
    ):
        raise ValueError("published_artifact")


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiDirectionalRequestIntentV4:
    """V4 strategy identity; V2 is never admitted as strategy authority here."""

    experiment_id: str
    timeline_window: TimelineWindow
    execution_account_id: str
    reporting_currency: domain.CurrencyId
    master_random_seed: int
    market_bundle_ref: MarketBundleRef
    strategy_definition_ref: domain.ArtifactRef
    strategy_parameter_set_ref: domain.ArtifactRef
    strategy_id: str
    sleeve_id: str
    result_grade_requested: RequestedResultGrade

    def __post_init__(self) -> None:
        if (
            type(self.experiment_id) is not str or not self.experiment_id or type(self.timeline_window) is not TimelineWindow
            or type(self.execution_account_id) is not str or not self.execution_account_id
            or type(self.reporting_currency) is not domain.CurrencyId or self.reporting_currency != domain.CurrencyId("USDT")
            or type(self.master_random_seed) is not int or self.master_random_seed != 0
            or type(self.market_bundle_ref) is not MarketBundleRef
            or type(self.strategy_definition_ref) is not domain.ArtifactRef or type(self.strategy_parameter_set_ref) is not domain.ArtifactRef
            or self.strategy_definition_ref.artifact_type != "strategy_definition" or self.strategy_definition_ref.schema_version != 1
            or self.strategy_parameter_set_ref.artifact_type != "strategy_parameter_set" or self.strategy_parameter_set_ref.schema_version != 1
            or type(self.strategy_id) is not str or not self.strategy_id or type(self.sleeve_id) is not str or not self.sleeve_id
            or self.result_grade_requested is not RequestedResultGrade.DEVELOPMENT
        ):
            raise ValueError("directional_v4_intent")


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiDirectionalPreparationV4:
    """One V4 target overlay paired only at planning time with V4 economics."""

    directional_authority: KoruDirectionalV4StrategyAuthority
    target: BinanceUsdmKoruDirectionalTargetConsumptionV4
    economics: KoruTradifiEconomicsAuthorityV4
    intent: BinanceUsdmTradifiDirectionalRequestIntentV4

    def __post_init__(self) -> None:
        if (
            type(self.directional_authority) is not KoruDirectionalV4StrategyAuthority
            or type(self.target) is not BinanceUsdmKoruDirectionalTargetConsumptionV4
            or type(self.economics) is not KoruTradifiEconomicsAuthorityV4
            or type(self.intent) is not BinanceUsdmTradifiDirectionalRequestIntentV4
            or self.intent.strategy_definition_ref != self.directional_authority.strategy_ref
            or self.intent.strategy_parameter_set_ref != self.directional_authority.parameter_ref
            or self.intent.strategy_id != self.directional_authority.strategy_id or self.intent.sleeve_id != self.directional_authority.sleeve_id
            or self.target.strategy_ref != self.directional_authority.strategy_ref
            or self.target.parameter_ref != self.directional_authority.parameter_ref
            or self.target.strategy_id != self.directional_authority.strategy_id or self.target.sleeve_id != self.directional_authority.sleeve_id
            or self.target.target_exposure != self.directional_authority.target_exposure
            or self.target.source_fragment_digest != self.directional_authority.source_fragment_digest
            or self.target.scope_ref != self.directional_authority.scope_ref
            or self.target.target_stream.stream_key != self.directional_authority.target_stream_key
            or self.target.target_stream_digest != self.directional_authority.target_stream_digest
            or self.target.target_stream.target_stream_digest != self.directional_authority.target_stream_digest
            or domain.canonical_bytes(self.target.target_stream) != domain.canonical_bytes(self.directional_authority.target_stream)
            or self.intent.market_bundle_ref != self.economics.bundle_ref
            or self.directional_authority.bundle_ref != self.economics.bundle_ref
            or self.directional_authority.economics_authority_digest != self.economics.authority_digest
            or self.directional_authority.source_fragment_digest != self.economics.source_fragment_digest
            or self.directional_authority.source_projection_authority_ref != self.economics.source_projection_authority_ref
            or self.directional_authority.source_projection_authority_content_hash != self.economics.source_projection_authority_content_hash
            or self.directional_authority.source_profile_authority_ref != self.economics.source_profile_authority_ref
        ):
            raise ValueError("directional_v4_binding")

    @property
    def target_stream(self):
        return self.target.target_stream

    @property
    def profile_composition_request(self):
        return self.economics.resolved_profile.request

    @property
    def resolved_profile(self):
        return self.economics.resolved_profile

    @property
    def profile_registry(self):
        return self.economics.resolved_profile.profile_registry

    @property
    def financial_dispatcher_spec(self):
        return self.economics.financial_dispatcher_spec

    @property
    def build_artifact_manifest(self):
        return self.economics.build_artifact_manifest

    @property
    def market_bundle_manifest(self) -> MarketBundleManifest:
        return self.economics.market_manifest

    @property
    def market_bundle_ref(self) -> MarketBundleRef:
        return self.economics.bundle_ref

    @property
    def market_reader(self) -> LocalMarketBundleReader:
        return self.economics.market_reader

    @property
    def target_stream_key(self) -> str:
        return self.target.target_stream.stream_key

    @property
    def target_stream_digest(self) -> str:
        return self.target.target_stream_digest

    @property
    def result_digest(self) -> str:
        return self.authority_digest

    @property
    def authority_digest(self) -> str:
        return domain.canonical_sha256({
            "type": "binance_usdm_tradifi_directional_preparation_v4",
            "overlay_bundle_ref": self.directional_authority.bundle_ref,
            "economics_bundle_ref": self.economics.bundle_ref,
            "economics_authority_digest": self.economics.authority_digest,
            "source_profile_authority_ref": self.economics.source_profile_authority_ref,
            "source_fragment_digest": self.economics.source_fragment_digest,
            "scope_ref": self.directional_authority.scope_ref,
            "strategy_ref": self.target.strategy_ref,
            "parameter_ref": self.target.parameter_ref,
            "strategy_id": self.target.strategy_id,
            "sleeve_id": self.target.sleeve_id,
            "target_stream_digest": self.target.target_stream_digest,
        })


def verify_binance_usdm_tradifi_directional_preparation_authority_v4(
    *, market_reader: MarketBundleReader
) -> KoruDirectionalV4StrategyAuthority | BinanceUsdmTradifiBarBacktestFailure:
    return verify_binance_usdm_koru_directional_strategy_authority_v4(market_reader=market_reader)


def prepare_binance_usdm_tradifi_directional_bar_backtest_v4(
    *, experiment_id: str, market_reader: MarketBundleReader, provider_inputs: BinanceUsdmTradifiProviderInputs,
    artifact_reader: ArtifactEnvelopeReader, artifact_publisher: ArtifactEnvelopePublisher, publication_root: Path,
) -> PreparedBacktestExecution | BinanceUsdmTradifiBarBacktestFailure:
    """Publish request@1/input@8 only after both V4 authorities verify."""
    if type(experiment_id) is not str:
        raise TypeError("experiment_id must be canonical non-empty text")
    if not experiment_id or experiment_id.strip() != experiment_id or unicodedata.normalize("NFC", experiment_id) != experiment_id:
        raise ValueError("experiment_id must be canonical non-empty text")
    if (
        type(provider_inputs) is not BinanceUsdmTradifiProviderInputs or not callable(getattr(artifact_reader, "read", None))
        or not callable(getattr(artifact_publisher, "put", None)) or not isinstance(publication_root, Path)
    ):
        raise TypeError("directional V4 public inputs are invalid")
    market_reader = LocalMarketBundleReader.validate_repository_open_reader_v1(market_reader)
    directional = verify_binance_usdm_koru_directional_strategy_authority_v4(market_reader=market_reader)
    if isinstance(directional, BinanceUsdmTradifiBarBacktestFailure):
        return directional
    economics = resolve_koru_tradifi_economics_authority_v4(
        market_reader=market_reader, artifact_reader=artifact_reader, provider_inputs=provider_inputs, experiment_id=experiment_id,
    )
    if isinstance(economics, BinanceUsdmTradifiBarBacktestFailure):
        return economics
    try:
        target = BinanceUsdmKoruDirectionalPlannerV4.target(directional)
        intent = BinanceUsdmTradifiDirectionalRequestIntentV4(
            experiment_id, TimelineWindow(market_reader.manifest.coverage_start, market_reader.manifest.coverage_start, market_reader.manifest.coverage_end_exclusive),
            "account-1", domain.CurrencyId("USDT"), 0, market_reader.bundle_ref, directional.strategy_ref,
            directional.parameter_ref, directional.strategy_id, directional.sleeve_id, RequestedResultGrade.DEVELOPMENT,
        )
        values = BinanceUsdmTradifiDirectionalPreparationV4(directional, target, economics, intent)
        planned = plan_binance_usdm_tradifi_directional_case_v4(values)
        request_envelope = domain.ArtifactEnvelope.create("backtest_request", 1, planned.request)
        execution_input = _materialize_execution_input_bundle_v8(
            resolved_request=planned.resolved_request, hydrated_inputs=planned.hydrated_inputs,
            market_data_preparation=planned.market_data_preparation,
        )
        request_ref = _publish(artifact_publisher, request_envelope)
        execution_ref = _publish(artifact_publisher, execution_input)
        _verify_published(artifact_reader, request_ref, request_envelope)
        _verify_published(artifact_reader, execution_ref, execution_input)
        return PreparedBacktestExecution(
            BacktestRequestRef.from_artifact_ref(request_ref), planned.resolved_request.semantic_run_id,
            BacktestExecutionRequest(8, planned.request, execution_ref),
            BacktestRuntime(registry=values.profile_registry, artifact_reader=artifact_reader, artifact_publisher=artifact_publisher,
                            market_reader=market_reader, publication_root=publication_root),
        )
    except Exception:  # noqa: BLE001 - sealed authority boundary must fail closed
        return _failure("directional_v4_execution_authority")


__all__ = [
    "BinanceUsdmTradifiDirectionalPreparationV4",
    "BinanceUsdmTradifiDirectionalRequestIntentV4",
    "prepare_binance_usdm_tradifi_directional_bar_backtest_v4",
    "verify_binance_usdm_tradifi_directional_preparation_authority_v4",
]
