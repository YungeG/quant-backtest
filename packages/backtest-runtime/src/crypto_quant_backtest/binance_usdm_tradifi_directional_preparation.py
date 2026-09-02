"""V3 directional preparation over separately verified V2 economic authority."""

from __future__ import annotations

from collections.abc import Mapping
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
from .binance_usdm_koru_directional_profile_v3 import (
    BinanceUsdmKoruDirectionalPlannerV3,
    BinanceUsdmKoruDirectionalTargetConsumptionV3,
    KoruDirectionalV3StrategyAuthority,
    verify_binance_usdm_koru_directional_strategy_authority_v3,
)
from .binance_usdm_tradifi_directional_case_planner_v3 import (
    plan_binance_usdm_tradifi_directional_case_v3,
)
from .binance_usdm_tradifi_preparation import (
    BinanceUsdmTradifiBarRequestIntent,
    BinanceUsdmTradifiProviderInputs,
    _account_authority_v2,
    _artifact_ref,
    _authority,
    _execution_projection_events_v2,
    _price_purpose_authority,
    _profile_v2,
    _source_events_v2,
    _source_profile_authority_v2,
    _validate_authority_support_v2,
    _validate_manifest_stream_cover_v2,
    _verify_artifact,
)
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
from .profile_build_manifest import _provider_build_manifest
from .request_registration import BacktestRequestRef
from .resolution import RequestedResultGrade
from .timeline import TimelineWindow


def _failure(subject: str) -> BinanceUsdmTradifiBarBacktestFailure:
    return BinanceUsdmTradifiBarBacktestFailure(
        BinanceUsdmTradifiBarBacktestFailureCode.PREPARATION_AUTHORITY_INVALID, subject
    )


def _publish(publisher: ArtifactEnvelopePublisher, envelope: domain.ArtifactEnvelope) -> domain.ArtifactRef:
    ref = publisher.put(envelope=envelope)
    if type(ref) is not domain.ArtifactRef or ref != domain.ArtifactRef.from_envelope(envelope):
        raise ValueError("publisher_ref")
    return ref


def _verify_published(reader: ArtifactEnvelopeReader, ref: domain.ArtifactRef, envelope: domain.ArtifactEnvelope) -> None:
    result = reader.read(ref=ref)
    if (
        type(result) is not domain.ArtifactReadResult
        or result.envelope != envelope
        or result.source_bytes != domain.canonical_bytes(envelope)
        or result.source_hash != domain.canonical_sha256(envelope)
        or domain.ArtifactRef.from_envelope(result.envelope) != ref
    ):
        raise ValueError("published_artifact")


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiDirectionalRequestIntentV3:
    """V3 strategy identity; V2 is never admitted as strategy authority here."""

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
            type(self.experiment_id) is not str
            or not self.experiment_id
            or type(self.timeline_window) is not TimelineWindow
            or type(self.execution_account_id) is not str
            or not self.execution_account_id
            or type(self.reporting_currency) is not domain.CurrencyId
            or self.reporting_currency != domain.CurrencyId("USDT")
            or type(self.master_random_seed) is not int
            or self.master_random_seed != 0
            or type(self.market_bundle_ref) is not MarketBundleRef
            or type(self.strategy_definition_ref) is not domain.ArtifactRef
            or type(self.strategy_parameter_set_ref) is not domain.ArtifactRef
            or self.strategy_definition_ref.artifact_type != "strategy_definition"
            or self.strategy_definition_ref.schema_version != 1
            or self.strategy_parameter_set_ref.artifact_type != "strategy_parameter_set"
            or self.strategy_parameter_set_ref.schema_version != 1
            or type(self.strategy_id) is not str
            or not self.strategy_id
            or type(self.sleeve_id) is not str
            or not self.sleeve_id
            or self.result_grade_requested is not RequestedResultGrade.DEVELOPMENT
        ):
            raise ValueError("directional_v3_intent")


@dataclass(frozen=True, slots=True)
class _V3EconomicsProfile:
    """V2-sealed market, funding, and financial inputs with no V2 target authority."""

    source_ref: domain.ArtifactRef
    source_artifact: object
    profile: object
    build_manifest: object


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiDirectionalPreparationV3:
    """The V3 target and V2 economics bindings used by the directional runtime."""

    directional_authority: KoruDirectionalV3StrategyAuthority
    target: BinanceUsdmKoruDirectionalTargetConsumptionV3
    v2_bundle_ref: MarketBundleRef
    v2_bundle_digest: str
    source_profile_authority_ref: domain.ArtifactRef
    source_fragment_digest: str
    intent: BinanceUsdmTradifiDirectionalRequestIntentV3
    resolved_profile: object
    profile_registry: object
    financial_dispatcher_spec: object
    build_artifact_manifest: object
    market_bundle_manifest: MarketBundleManifest
    market_bundle_ref: MarketBundleRef
    market_reader: MarketBundleReader

    def __post_init__(self) -> None:
        if (
            type(self.directional_authority) is not KoruDirectionalV3StrategyAuthority
            or type(self.target) is not BinanceUsdmKoruDirectionalTargetConsumptionV3
            or type(self.intent) is not BinanceUsdmTradifiDirectionalRequestIntentV3
            or self.intent.strategy_definition_ref != self.directional_authority.strategy_ref
            or self.intent.strategy_parameter_set_ref != self.directional_authority.parameter_ref
            or self.intent.strategy_id != self.directional_authority.strategy_id
            or self.intent.sleeve_id != self.directional_authority.sleeve_id
            or type(self.v2_bundle_ref) is not MarketBundleRef
            or self.v2_bundle_digest != self.v2_bundle_ref.manifest_hash
            or type(self.source_profile_authority_ref) is not domain.ArtifactRef
            or self.source_fragment_digest != self.directional_authority.source_fragment_digest
            or self.target.target_stream_digest != self.directional_authority.target_stream_digest
            or type(self.market_reader) is not LocalMarketBundleReader
            or self.market_bundle_ref != self.market_reader.bundle_ref
            or self.market_bundle_manifest != self.market_reader.manifest
        ):
            raise ValueError("directional_v3_binding")

    @property
    def target_stream(self):
        return self.target.target_stream

    @property
    def profile_composition_request(self):
        return self.resolved_profile.request

    @property
    def result_digest(self) -> str:
        return self.authority_digest

    @property
    def bundle_schema_version(self) -> int:
        return 2

    @property
    def target_stream_key(self) -> str:
        return self.target.target_stream.stream_key

    @property
    def target_stream_digest(self) -> str:
        return self.target.target_stream_digest

    @property
    def authority_digest(self) -> str:
        return domain.canonical_sha256(
            {
                "type": "binance_usdm_tradifi_directional_preparation_v3",
                "v3_bundle_ref": self.directional_authority.bundle_ref,
                "v3_bundle_digest": self.directional_authority.bundle_digest,
                "v2_bundle_ref": self.v2_bundle_ref,
                "v2_bundle_digest": self.v2_bundle_digest,
                "source_profile_authority_ref": self.source_profile_authority_ref,
                "source_fragment_digest": self.source_fragment_digest,
                "scope_ref": self.directional_authority.scope_ref,
                "strategy_ref": self.target.strategy_ref,
                "parameter_ref": self.target.parameter_ref,
                "strategy_id": self.target.strategy_id,
                "sleeve_id": self.target.sleeve_id,
                "target_stream_digest": self.target.target_stream_digest,
            }
        )


def verify_binance_usdm_tradifi_directional_preparation_authority_v3(
    *, market_reader: MarketBundleReader
) -> KoruDirectionalV3StrategyAuthority | BinanceUsdmTradifiBarBacktestFailure:
    return verify_binance_usdm_koru_directional_strategy_authority_v3(market_reader=market_reader)


def _v2_validation_intent(reader: MarketBundleReader) -> tuple[BinanceUsdmTradifiBarRequestIntent, Mapping[str, object]]:
    manifest = reader.manifest
    bundle_ref = reader.bundle_ref
    if (
        type(manifest) is not MarketBundleManifest
        or type(bundle_ref) is not MarketBundleRef
        or manifest.schema_version != 3
        or MarketBundleRef.from_manifest(manifest) != bundle_ref
    ):
        raise ValueError("published_hybrid_bundle")
    events = tuple(
        event
        for stream in manifest.streams
        if stream.stream_key == "binance_usdm.tradifi.preparation_authority.v2"
        for event in _read(reader, stream.stream_key)
    )
    if len(events) != 1 or not isinstance(events[0].payload, Mapping):
        raise ValueError("v2_preparation_event")
    payload = events[0].payload
    strategy_ref = _artifact_ref(payload.get("strategy_definition_ref"), "strategy_definition_ref")
    bindings = payload.get("parameter_target_bindings")
    if not isinstance(bindings, tuple) or not bindings or not isinstance(bindings[0], Mapping):
        raise ValueError("v2_parameter_bindings")
    parameter_ref = _artifact_ref(bindings[0].get("parameter_ref"), "parameter_ref")
    return (
        BinanceUsdmTradifiBarRequestIntent(
            experiment_id="binance-usdm-tradifi-directional-v3",
            timeline_window=TimelineWindow(manifest.coverage_start, manifest.coverage_start, manifest.coverage_end_exclusive),
            execution_account_id="account-1",
            reporting_currency=domain.CurrencyId("USDT"),
            master_random_seed=0,
            market_bundle_ref=bundle_ref,
            strategy_definition_ref=strategy_ref,
            strategy_parameter_set_ref=parameter_ref,
            result_grade_requested=RequestedResultGrade.DEVELOPMENT,
        ),
        payload,
    )


def _read(reader: MarketBundleReader, stream_key: str) -> tuple:
    cursor = reader.open_cursor(stream_key, batch_size=64)
    events = []
    while not cursor.exhausted:
        batch, cursor = reader.read_batch(cursor)
        events.extend(batch)
    return tuple(events)


def _build_v3_economics_profile(
    *, reader: MarketBundleReader, artifact_reader: ArtifactEnvelopeReader, provider_inputs: BinanceUsdmTradifiProviderInputs
) -> _V3EconomicsProfile:
    """Validate only the sealed V2 market, funding, and financial profile inputs."""
    v2_intent, _ = _v2_validation_intent(reader)
    manifest = reader.manifest
    _, payload = _authority(reader, manifest, v2_intent, 2)
    authority_refs, source_ref = _validate_authority_support_v2(payload, provider_inputs)
    _price_purpose_authority(reader, manifest, v2_intent, payload, 2)
    source_artifact = _verify_artifact(artifact_reader, source_ref)
    source_payload = _source_profile_authority_v2(payload, source_artifact)
    _validate_manifest_stream_cover_v2(manifest, source_payload, hybrid_v3=True)
    _execution_projection_events_v2(reader, manifest, v2_intent, source_payload)
    _account_authority_v2(reader, manifest, v2_intent, provider_inputs, payload)
    source_events = _source_events_v2(reader, manifest, source_payload)
    profile = _profile_v2(
        payload,
        v2_intent,
        (*authority_refs[:2], *authority_refs),
        source_artifact,
        source_events,
    )
    return _V3EconomicsProfile(
        source_ref,
        source_artifact,
        profile,
        _provider_build_manifest(provider_inputs.build_artifact_manifest, profile.profile_registry),
    )



def prepare_binance_usdm_tradifi_directional_bar_backtest(
    *,
    market_reader: LocalMarketBundleReader,
    provider_inputs: BinanceUsdmTradifiProviderInputs,
    artifact_reader: ArtifactEnvelopeReader,
    artifact_publisher: ArtifactEnvelopePublisher,
    publication_root: Path,
) -> PreparedBacktestExecution | BinanceUsdmTradifiBarBacktestFailure:
    """Prepare a normal runtime only after both sealed authorities verify."""
    if (
        type(provider_inputs) is not BinanceUsdmTradifiProviderInputs
        or type(market_reader) is not LocalMarketBundleReader
        or not callable(getattr(artifact_reader, "read", None))
        or not callable(getattr(artifact_publisher, "put", None))
        or not isinstance(publication_root, Path)
    ):
        raise TypeError("directional V3 public inputs are invalid")
    directional = verify_binance_usdm_koru_directional_strategy_authority_v3(market_reader=market_reader)
    if isinstance(directional, BinanceUsdmTradifiBarBacktestFailure):
        return directional
    try:
        target = BinanceUsdmKoruDirectionalPlannerV3.target(directional)
        economics = _build_v3_economics_profile(
            reader=market_reader,
            artifact_reader=artifact_reader,
            provider_inputs=provider_inputs,
        )
        if (
            directional.source_fragment_digest != economics.source_artifact.envelope.payload.get("source_fragment_digest")
            or directional.source_profile_authority_ref != economics.source_ref
            or directional.source_profile_authority_envelope != economics.source_artifact.envelope
        ):
            raise ValueError("v3_v2_source_binding")
        intent = BinanceUsdmTradifiDirectionalRequestIntentV3(
            "binance-usdm-tradifi-directional-v3",
            TimelineWindow(market_reader.manifest.coverage_start, market_reader.manifest.coverage_start, market_reader.manifest.coverage_end_exclusive),
            "account-1",
            domain.CurrencyId("USDT"),
            0,
            market_reader.bundle_ref,
            directional.strategy_ref,
            directional.parameter_ref,
            directional.strategy_id,
            directional.sleeve_id,
            RequestedResultGrade.DEVELOPMENT,
        )
        profile = economics.profile
        values = BinanceUsdmTradifiDirectionalPreparationV3(
            directional,
            target,
            directional.v2_bundle_ref,
            directional.v2_bundle_digest,
            economics.source_ref,
            directional.source_fragment_digest,
            intent,
            profile,
            profile.profile_registry,
            profile.financial_dispatcher_spec,
            economics.build_manifest,
            market_reader.manifest,
            market_reader.bundle_ref,
            market_reader,
        )
        planned = plan_binance_usdm_tradifi_directional_case_v3(values)
        request_envelope = domain.ArtifactEnvelope.create("backtest_request", 1, planned.request)
        execution_input = _materialize_execution_input_bundle_v8(
            resolved_request=planned.resolved_request,
            hydrated_inputs=planned.hydrated_inputs,
            market_data_preparation=planned.market_data_preparation,
        )
        request_ref = _publish(artifact_publisher, request_envelope)
        execution_ref = _publish(artifact_publisher, execution_input)
        _verify_published(artifact_reader, request_ref, request_envelope)
        _verify_published(artifact_reader, execution_ref, execution_input)
        return PreparedBacktestExecution(
            BacktestRequestRef.from_artifact_ref(request_ref),
            planned.resolved_request.semantic_run_id,
            BacktestExecutionRequest(8, planned.request, execution_ref),
            BacktestRuntime(
                registry=profile.profile_registry,
                artifact_reader=artifact_reader,
                artifact_publisher=artifact_publisher,
                market_reader=market_reader,
                publication_root=publication_root,
            ),
        )
    except Exception:  # noqa: BLE001 - sealed authority boundary must fail closed
        return _failure("directional_v3_execution_authority")


__all__ = [
    "BinanceUsdmTradifiDirectionalPreparationV3",
    "prepare_binance_usdm_tradifi_directional_bar_backtest",
    "verify_binance_usdm_tradifi_directional_preparation_authority_v3",
]
