"""Production factory for the retained KORU TradFi development profile."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import Enum

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    CurrencyId,
    InstrumentId,
    PricePurpose,
    Quantity,
    RoundingPolicy,
    Scale,
    SessionId,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketEvent,
    MarketStreamManifest,
)
from crypto_quant_trading import (
    FundingSlotId,
    LinearAccountMarginProjectorV2,
    LinearFundingApplicationKey,
    LinearPerpetualContract,
    StaleMarkPolicy,
)
from crypto_quant_trading.profiles.binance_usdm import (
    BINANCE_USDM_OPEN_ENDED_DELIVERY_AT,
    BinanceUsdmAccountProfileBand,
    BinanceUsdmAccountProfileModel,
    BinanceUsdmAccountProfileQuery,
    BinanceUsdmAccountProfileScope,
    BinanceUsdmAccountProfileSourceRef,
    BinanceUsdmAccountSourceKind,
    BinanceUsdmAggregateTradePrice,
    BinanceUsdmFundingCoverage,
    BinanceUsdmFundingRateRecord,
    BinanceUsdmFundingSourceModelV2,
    BinanceUsdmFundingSourceQuery,
    BinanceUsdmFundingSourceRef,
    BinanceUsdmHistoricalAccountProfileBook,
    BinanceUsdmHistoricalFundingBook,
    BinanceUsdmHistoricalPriceBook,
    BinanceUsdmInstrumentMetadataQuery,
    BinanceUsdmInstrumentMetadataRevision,
    BinanceUsdmInstrumentMetadataSourceRef,
    BinanceUsdmInstrumentModel,
    BinanceUsdmMarginTierBand,
    BinanceUsdmMarginTierBracket,
    BinanceUsdmMarginTierModel,
    BinanceUsdmMarginTierQuery,
    BinanceUsdmMarginTierRuleBook,
    BinanceUsdmMarginTierScope,
    BinanceUsdmMarginTierSourceRef,
    BinanceUsdmMarkPriceKline,
    BinanceUsdmOrderAdmissionMode,
    BinanceUsdmOrderRuleBand,
    BinanceUsdmOrderRuleBook,
    BinanceUsdmOrderRuleModel,
    BinanceUsdmOrderRuleQuery,
    BinanceUsdmOrderRuleSourceRef,
    BinanceUsdmPricePurposeQuery,
    BinanceUsdmPriceSourceKind,
    BinanceUsdmPriceSourceRef,
    BinanceUsdmPriceStreamCoverage,
    BinanceUsdmPriceStreamModel,
    BinanceUsdmTradifiInstrumentMetadataModel,
)

from .binance_usdm_profile import BinanceUsdmAccountCapacityEvidence
from .binance_usdm_tradifi_profile import (
    BinanceUsdmTradifiProfileComposer,
    BinanceUsdmTradifiProfileCompositionRequest,
    BinanceUsdmTradifiResolvedProfile,
)
from .binance_usdm_tradifi_profile_wire import (
    decode_binance_usdm_tradifi_profile_composition_request_v1,
)
from .financial_dispatch import FinancialDispatcherSpec
from .ports import SimulationComponentRef, SimulationPortType
from .resolution import BacktestProfileRegistry
from .slippage import (
    DeterministicBpsSlippageModel,
    SlippageApplicabilityEnvelope,
    SlippageCalibrationRef,
    SlippageModelKind,
)
from .timeline import TimelineWindow

_SCHEMA_VERSION = 1
_SOURCE_AUTHORITY_ARTIFACT_TYPE = "binance_usdm_koru_source_profile_authority"
_SOURCE_AUTHORITY_SCHEMA_VERSION = 2
_HOUR_NS = 3_600_000_000_000
_MILLISECOND_NS = 1_000_000
_POST_ADJUSTMENT_START = UtcInstant(1_784_109_600_000_000_000)
_AUTHORITY_END_EXCLUSIVE = UtcInstant(1_791_158_400_000_000_000)
_INSTRUMENT = InstrumentId(VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual")
_USDT = CurrencyId("USDT")
_EVIDENCE_INSTANT = SimulationInstant(
    _POST_ADJUSTMENT_START,
    TimelinePhase(0, "market_data"),
    SourceSequence(0),
)
_SESSION_ID = SessionId("binance_usdm", "continuous")
_EXECUTION_STREAM = (
    "binance_usdm.aggregate_trades.execution_reference.koruusdt.tradifi.v1"
)
_EXECUTION_EVENT_TYPE = "binance_usdm_koru_aggregate_trade.v1"
_EXECUTION_CAPABILITY = MarketBundleCapability(
    "price.aggregate_trade.koru-usdt-tradifi-perpetual", 1
)
_EXECUTION_PROJECTION_STREAM = (
    "binance_usdm.tradifi.bar_open.first_retained_aggregate_trade.koruusdt.1h.v2"
)
_EXECUTION_PROJECTION_EVENT_TYPE = "bar_open"
_EXECUTION_PROJECTION_CAPABILITY = MarketBundleCapability("bar_open", 1)
_FUNDING_STREAM = "binance_usdm.funding_history.publications.koruusdt.v1"
_FUNDING_EVENT_TYPE = "binance_usdm_koru_funding_history_publication_v1"
_FUNDING_CAPABILITY = MarketBundleCapability("binance_usdm.funding-publications", 1)
_POINT_CAPABILITY = MarketBundleCapability("price.point", 1)
_BAR_CAPABILITY = MarketBundleCapability("price.bar", 1)
_PRICE_STREAMS = {
    ("mark_price", "strategy"): (
        "binance_usdm.mark_price.strategy.koruusdt.1h.v1",
        "binance_usdm_koru_mark_price_strategy_bar_v1",
        _BAR_CAPABILITY,
    ),
    ("mark_price", "valuation"): (
        "binance_usdm.mark_price.valuation.koruusdt.1h.v1",
        "binance_usdm_koru_mark_price_point_v1",
        _POINT_CAPABILITY,
    ),
    ("mark_price", "margin"): (
        "binance_usdm.mark_price.margin.koruusdt.1h.v1",
        "binance_usdm_koru_mark_price_point_v1",
        _POINT_CAPABILITY,
    ),
    ("mark_price", "liquidation"): (
        "binance_usdm.mark_price.liquidation.koruusdt.1h.v1",
        "binance_usdm_koru_mark_price_liquidation_bar_v1",
        _BAR_CAPABILITY,
    ),
    ("index_price", "strategy"): (
        "binance_usdm.index_price.strategy.koruusdt.1h.v1",
        "binance_usdm_koru_index_price_strategy_bar_v1",
        _BAR_CAPABILITY,
    ),
}
_PRICE_PURPOSES = {
    "valuation": PricePurpose.VALUATION,
    "margin": PricePurpose.MARGIN,
    "liquidation": PricePurpose.LIQUIDATION,
}
_MODEL_SOURCE_HASHES = {
    name: canonical_sha256(
        {
            "type": "binance_usdm_koru_tradifi_development_profile_model_authority_v1",
            "authority": name,
        }
    )
    for name in (
        "instrument",
        "order_rules",
        "margin_tiers",
        "account_config",
        "symbol_config",
        "commission_rate",
        "fee_burn",
    )
}
_LIMITATIONS = (
    "development_profile",
    "retained_source_projection_v2_only",
    "selected_aggregate_execution_reference_only",
    "index_strategy_stream_validated_but_not_substituted_for_public_price_purposes",
    "composed_at_and_acquisition_are_evidence_only",
    "single_instrument_single_usdt_cross_account_only",
    "deployment_unauthorized",
)


class BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1(str, Enum):
    INVALID_REQUEST = "invalid_request"
    TIMELINE_INVALID = "timeline_invalid"
    AUTHORITY_INVALID = "authority_invalid"
    SOURCE_ORDER_INVALID = "source_order_invalid"
    SOURCE_CONTEXT_INVALID = "source_context_invalid"
    PRICE_GRID_INVALID = "price_grid_invalid"
    EXECUTION_SOURCE_MISSING = "execution_source_missing"
    FUNDING_INVALID = "funding_invalid"
    MODEL_RESOLUTION_FAILED = "model_resolution_failed"
    PROFILE_COMPOSITION_FAILED = "profile_composition_failed"
    RESULT_INVALID = "result_invalid"


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiDevelopmentProfileRequestV1:
    timeline_window: TimelineWindow
    composed_at: SimulationInstant
    account_id: str
    xkrx_calendar_ref: ArtifactRef
    arcx_calendar_ref: ArtifactRef
    post_adjustment_unit_regime_ref: ArtifactRef
    source_profile_authority_envelope: ArtifactEnvelope
    source_profile_authority_ref: ArtifactRef
    source_events: tuple[MarketEvent, ...]

    def __post_init__(self) -> None:
        if type(self.timeline_window) is not TimelineWindow:
            raise TypeError("timeline_window must be exact TimelineWindow")
        if type(self.composed_at) is not SimulationInstant:
            raise TypeError("composed_at must be exact SimulationInstant")
        if (
            type(self.account_id) is not str
            or not self.account_id
            or self.account_id != self.account_id.strip()
        ):
            raise ValueError("account_id must be canonical non-empty text")
        refs = (
            self.xkrx_calendar_ref,
            self.arcx_calendar_ref,
            self.post_adjustment_unit_regime_ref,
        )
        if any(type(value) is not ArtifactRef for value in refs):
            raise TypeError("authority refs must be exact ArtifactRefs")
        if tuple((value.artifact_type, value.schema_version) for value in refs) != (
            ("xkrx_regular_session_calendar", 1),
            ("arcx_koru_core_session_calendar", 1),
            ("binance_usdm_tradifi_post_adjustment_unit_regime", 1),
        ):
            raise ValueError("authority ref identities are not admitted")
        if (
            type(self.source_profile_authority_envelope) is not ArtifactEnvelope
            or type(self.source_profile_authority_ref) is not ArtifactRef
        ):
            raise TypeError("source profile authority must use exact envelope and ref")
        if (
            self.source_profile_authority_envelope.artifact_type
            != _SOURCE_AUTHORITY_ARTIFACT_TYPE
            or self.source_profile_authority_envelope.schema_version
            != _SOURCE_AUTHORITY_SCHEMA_VERSION
            or self.source_profile_authority_ref
            != ArtifactRef.from_envelope(self.source_profile_authority_envelope)
        ):
            raise ValueError("source profile authority envelope/ref mismatch")
        if type(self.source_events) is not tuple or any(
            type(value) is not MarketEvent for value in self.source_events
        ):
            raise TypeError("source_events must contain exact MarketEvents")
        ordered = tuple(
            sorted(
                self.source_events,
                key=lambda value: (
                    value.stream_key,
                    value.ordering_key,
                    value.event_id,
                ),
            )
        )
        if ordered != self.source_events:
            raise ValueError("source_events must use SourceProjectionV2 order")
        if len({value.event_id for value in ordered}) != len(ordered):
            raise ValueError("source_events cannot contain duplicate event ids")

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_tradifi_development_profile_request_v1",
            "schema_version": _SCHEMA_VERSION,
            "timeline_window": self.timeline_window,
            "composed_at": self.composed_at,
            "account_id": self.account_id,
            "authority_refs": (
                self.xkrx_calendar_ref,
                self.arcx_calendar_ref,
                self.post_adjustment_unit_regime_ref,
            ),
            "source_profile_authority_envelope": self.source_profile_authority_envelope,
            "source_profile_authority_ref": self.source_profile_authority_ref,
            "source_events": self.source_events,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiDevelopmentProfileFailureV1:
    code: BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1
    subject: str

    def __post_init__(self) -> None:
        if type(self.code) is not BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1:
            raise TypeError("code must be exact development-profile failure code")
        if (
            type(self.subject) is not str
            or not self.subject
            or self.subject != self.subject.strip()
        ):
            raise ValueError("subject must be canonical non-empty text")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_tradifi_development_profile_failure_v1",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiDevelopmentProfileResultV1:
    request: BinanceUsdmKoruTradifiDevelopmentProfileRequestV1
    profile_composition_request: BinanceUsdmTradifiProfileCompositionRequest
    resolved_profile: BinanceUsdmTradifiResolvedProfile
    profile_registry: BacktestProfileRegistry
    financial_dispatcher_spec: FinancialDispatcherSpec
    profile_composition_request_wire: Mapping[str, object]
    profile_composition_request_hash: str
    source_stream_hashes: tuple[tuple[str, str], ...]
    source_stream_counts: tuple[tuple[str, int], ...]
    source_profile_authority_ref: ArtifactRef
    source_profile_authority_hash: str
    limitations: tuple[str, ...] = _LIMITATIONS
    source_authority_verified: bool = True
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not BinanceUsdmKoruTradifiDevelopmentProfileRequestV1:
            raise TypeError("request must be exact development-profile request")
        if (
            type(self.profile_composition_request)
            is not BinanceUsdmTradifiProfileCompositionRequest
        ):
            raise TypeError("profile_composition_request must be exact request")
        if type(self.resolved_profile) is not BinanceUsdmTradifiResolvedProfile:
            raise TypeError("resolved_profile must be exact resolved profile")
        if self.resolved_profile.request != self.profile_composition_request:
            raise ValueError("resolved profile request binding mismatch")
        if not self.profile_composition_request.raw_exact_valuation:
            raise ValueError("KORU profile must authorize raw exact valuation")
        if not self.profile_composition_request.raw_exact_margin:
            raise ValueError("KORU profile must authorize raw exact margin")
        if not self.profile_composition_request.raw_exact_strategy:
            raise ValueError("KORU profile must authorize raw exact strategy")
        if not self.profile_composition_request.raw_exact_liquidation:
            raise ValueError("KORU profile must authorize raw exact liquidation")
        if self.financial_dispatcher_spec.margin_component != LinearAccountMarginProjectorV2().component_ref:
            raise ValueError("KORU profile must bind V2 account margin")
        if self.profile_registry != self.resolved_profile.profile_registry:
            raise ValueError("profile registry binding mismatch")
        if (
            self.financial_dispatcher_spec
            != self.resolved_profile.financial_dispatcher_spec
        ):
            raise ValueError("dispatcher binding mismatch")
        if not isinstance(self.profile_composition_request_wire, Mapping):
            raise TypeError("profile_composition_request_wire must be a mapping")
        if (
            self.profile_composition_request_hash
            != self.profile_composition_request.request_hash
            or canonical_sha256(self.profile_composition_request_wire)
            != self.profile_composition_request_hash
            or canonical_bytes(self.profile_composition_request_wire)
            != canonical_bytes(self.profile_composition_request)
        ):
            raise ValueError("profile request wire binding mismatch")
        manifests = _source_manifests(self.request.source_events)
        if self.source_stream_hashes != tuple(
            (value.stream_key, value.content_hash) for value in manifests
        ) or self.source_stream_counts != tuple(
            (value.stream_key, value.event_count) for value in manifests
        ):
            raise ValueError("source stream evidence binding mismatch")
        if (
            self.source_profile_authority_ref
            != self.request.source_profile_authority_ref
            or self.source_profile_authority_hash
            != self.request.source_profile_authority_envelope.content_hash
            or self.limitations != _LIMITATIONS
            or type(self.source_authority_verified) is not bool
            or not self.source_authority_verified
        ):
            raise ValueError("development profile result authority/flags mismatch")
        object.__setattr__(self, "result_digest", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_tradifi_development_profile_result_v1",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "profile_composition_request": self.profile_composition_request,
            "resolved_profile": self.resolved_profile,
            "profile_registry": self.profile_registry,
            "financial_dispatcher_spec": self.financial_dispatcher_spec,
            "profile_composition_request_wire": self.profile_composition_request_wire,
            "profile_composition_request_hash": self.profile_composition_request_hash,
            "source_stream_hashes": self.source_stream_hashes,
            "source_stream_counts": self.source_stream_counts,
            "source_profile_authority_ref": self.source_profile_authority_ref,
            "source_profile_authority_hash": self.source_profile_authority_hash,
            "limitations": self.limitations,
            "source_authority_verified": self.source_authority_verified,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "result_digest": self.result_digest}


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiDevelopmentProfileOutcomeV1:
    result: BinanceUsdmKoruTradifiDevelopmentProfileResultV1 | None = None
    failure: BinanceUsdmKoruTradifiDevelopmentProfileFailureV1 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")
        if (
            self.result is not None
            and type(self.result)
            is not BinanceUsdmKoruTradifiDevelopmentProfileResultV1
        ):
            raise TypeError("result must be exact development-profile result")
        if (
            self.failure is not None
            and type(self.failure)
            is not BinanceUsdmKoruTradifiDevelopmentProfileFailureV1
        ):
            raise TypeError("failure must be exact development-profile failure")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_tradifi_development_profile_outcome_v1",
            "schema_version": _SCHEMA_VERSION,
            "result": self.result,
            "failure": self.failure,
        }


class _BuildError(ValueError):
    def __init__(
        self,
        code: BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1,
        subject: str,
    ) -> None:
        self.code = code
        self.subject = subject
        super().__init__(subject)


def _failed(
    code: BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1,
    subject: str,
) -> BinanceUsdmKoruTradifiDevelopmentProfileOutcomeV1:
    return BinanceUsdmKoruTradifiDevelopmentProfileOutcomeV1(
        failure=BinanceUsdmKoruTradifiDevelopmentProfileFailureV1(code, subject)
    )


def _trusted_request(
    value: object,
) -> BinanceUsdmKoruTradifiDevelopmentProfileRequestV1:
    if type(value) is not BinanceUsdmKoruTradifiDevelopmentProfileRequestV1:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.INVALID_REQUEST,
            "request",
        )
    request = value
    try:
        rebuilt = BinanceUsdmKoruTradifiDevelopmentProfileRequestV1(
            request.timeline_window,
            request.composed_at,
            request.account_id,
            request.xkrx_calendar_ref,
            request.arcx_calendar_ref,
            request.post_adjustment_unit_regime_ref,
            request.source_profile_authority_envelope,
            request.source_profile_authority_ref,
            request.source_events,
        )
        if canonical_bytes(rebuilt) != canonical_bytes(request):
            raise ValueError
    except (AttributeError, TypeError, ValueError) as error:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.INVALID_REQUEST,
            "request",
        ) from error
    return rebuilt


def _validate_timeline(
    request: BinanceUsdmKoruTradifiDevelopmentProfileRequestV1,
) -> None:
    window = request.timeline_window
    if not (
        _POST_ADJUSTMENT_START <= window.data_start
        and window.trading_start == window.data_start
        and window.end_exclusive <= _AUTHORITY_END_EXCLUSIVE
        and window.data_start.epoch_nanoseconds % _HOUR_NS == 0
        and window.end_exclusive.epoch_nanoseconds % _HOUR_NS == 0
        and request.composed_at.instant >= _POST_ADJUSTMENT_START
    ):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.TIMELINE_INVALID,
            "timeline_window",
        )


def _required_price_grid(window: TimelineWindow) -> tuple[tuple[int, int], ...]:
    first_completed = max(
        ((window.data_start.epoch_nanoseconds + _HOUR_NS - 1) // _HOUR_NS) * _HOUR_NS,
        _POST_ADJUSTMENT_START.epoch_nanoseconds + _HOUR_NS,
    )
    return tuple(
        (completed, (completed - _HOUR_NS) // _MILLISECOND_NS)
        for completed in range(
            first_completed,
            window.end_exclusive.epoch_nanoseconds,
            _HOUR_NS,
        )
    )


def _integer(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if type(value) is not int:
        raise ValueError(key)
    return value


def _text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if type(value) is not str or not value:
        raise ValueError(key)
    return value


def _source_manifests(
    events: tuple[MarketEvent, ...],
) -> tuple[MarketStreamManifest, ...]:
    grouped: dict[str, list[MarketEvent]] = defaultdict(list)
    for event in events:
        grouped[event.stream_key].append(event)
    return tuple(
        MarketStreamManifest.from_events(key, tuple(values))
        for key, values in sorted(grouped.items())
    )


def _source_stream_authority(
    manifest: MarketStreamManifest,
    events: tuple[MarketEvent, ...],
) -> dict[str, object]:
    return {
        "stream_manifest": manifest.to_canonical_dict(),
        "event_bindings": tuple(
            {
                "event_id": event.event_id,
                "event_hash": event.event_hash,
                "instrument_id": event.instrument_id,
                "source_key": event.source_key,
                "source_hash": event.source_hash,
                "revision_id": event.revision_id,
                "payload_keys": tuple(sorted(event.payload)),
                "payload_context": {
                    key: event.payload[key]
                    for key in (
                        "price_purpose",
                        "source_kind",
                        "interval",
                        "price_scale",
                        "funding_purpose",
                        "funding_rate_scale",
                        "mark_price_scale",
                        "rate_type",
                    )
                    if key in event.payload
                },
                "provenance": {
                    key: event.payload[key]
                    for key in (
                        "source_snapshot_id",
                        "source_snapshot_hash",
                        "source_provenance_hash",
                        "source_record_hash",
                        "request_hash",
                        "capture_hash",
                    )
                    if key in event.payload
                },
            }
            for event in events
        ),
    }


def _canonical_digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 71
        and value.startswith("sha256:")
        and all(digit in "0123456789abcdef" for digit in value[7:])
    )


def _validate_source_profile_authority(
    request: BinanceUsdmKoruTradifiDevelopmentProfileRequestV1,
) -> tuple[MarketStreamManifest, ...]:
    envelope = request.source_profile_authority_envelope
    try:
        rebuilt = ArtifactEnvelope.create(
            _SOURCE_AUTHORITY_ARTIFACT_TYPE,
            _SOURCE_AUTHORITY_SCHEMA_VERSION,
            envelope.payload,
        )
    except (TypeError, ValueError) as error:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID,
            "source_profile_authority_envelope",
        ) from error
    if rebuilt != envelope or ArtifactRef.from_envelope(rebuilt) != request.source_profile_authority_ref:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID,
            "source_profile_authority_ref",
        )
    payload = envelope.payload
    expected_keys = {
        "type",
        "schema_version",
        "timeline_window",
        "source_projection_request_hash",
        "source_fragment_digest",
        "aggregate_trade_boundary_index_request_hash",
        "aggregate_trade_boundary_index_result_digest",
        "aggregate_trade_streamed_reconstruction_digest",
        "aggregate_trade_intra_day_raw_id_gap_stream",
        "aggregate_trade_cross_date_raw_id_gap_stream",
        "aggregate_trade_coverage_gaps",
        "missing_boundaries",
        "source_stream_manifests",
        "source_event_bindings",
        "execution_projection_stream_manifest",
        "execution_projection_event_bindings",
        "source_stream_authorities",
        "xkrx_calendar_ref",
        "arcx_calendar_ref",
        "post_adjustment_unit_regime_ref",
        "development_only",
        "decision_grade_eligible",
        "deployment_authorized",
    }
    if not isinstance(payload, Mapping) or set(payload) != expected_keys:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID,
            "source_profile_authority_payload",
        )
    window = request.timeline_window
    expected_timeline = {
        "data_start": window.data_start,
        "trading_start": window.trading_start,
        "end_exclusive": window.end_exclusive,
    }
    refs = (
        ("xkrx_calendar_ref", request.xkrx_calendar_ref),
        ("arcx_calendar_ref", request.arcx_calendar_ref),
        (
            "post_adjustment_unit_regime_ref",
            request.post_adjustment_unit_regime_ref,
        ),
    )
    digest_keys = (
        "source_projection_request_hash",
        "source_fragment_digest",
        "aggregate_trade_boundary_index_request_hash",
        "aggregate_trade_boundary_index_result_digest",
        "aggregate_trade_streamed_reconstruction_digest",
    )
    if (
        payload.get("type") != "binance_usdm_koru_source_profile_authority_v2"
        or payload.get("schema_version") != _SOURCE_AUTHORITY_SCHEMA_VERSION
        or canonical_bytes(payload.get("timeline_window"))
        != canonical_bytes(expected_timeline)
        or any(
            canonical_bytes(payload.get(key)) != canonical_bytes(ref)
            for key, ref in refs
        )
        or any(not _canonical_digest(payload.get(key)) for key in digest_keys)
        or payload.get("development_only") is not True
        or payload.get("decision_grade_eligible") is not False
        or payload.get("deployment_authorized") is not False
    ):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID,
            "source_profile_authority_context",
        )
    manifests = _source_manifests(request.source_events)
    if canonical_bytes(payload.get("source_stream_manifests")) != canonical_bytes(
        tuple(value.to_canonical_dict() for value in manifests)
    ):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID,
            "source_stream_manifests",
        )
    projection_manifest = payload.get("execution_projection_stream_manifest")
    projection_bindings = payload.get("execution_projection_event_bindings")
    if not isinstance(projection_manifest, Mapping) or not isinstance(
        projection_bindings, tuple
    ):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID,
            "execution_projection_authority",
        )
    try:
        capability = projection_manifest["capability"]
        if not isinstance(capability, Mapping):
            raise TypeError
        rebuilt_projection_manifest = MarketStreamManifest(
            stream_key=projection_manifest["stream_key"],  # type: ignore[arg-type]
            event_type=projection_manifest["event_type"],  # type: ignore[arg-type]
            capability=MarketBundleCapability(
                capability["key"], capability["version"]  # type: ignore[arg-type]
            ),
            event_count=projection_manifest["event_count"],  # type: ignore[arg-type]
            content_hash=projection_manifest["content_hash"],  # type: ignore[arg-type]
        )
    except (KeyError, TypeError, ValueError) as error:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID,
            "execution_projection_stream_manifest",
        ) from error
    if (
        set(projection_manifest)
        != {
            "type",
            "stream_key",
            "event_type",
            "capability",
            "event_count",
            "content_hash",
        }
        or set(capability) != {"type", "key", "version"}
        or canonical_bytes(projection_manifest)
        != canonical_bytes(rebuilt_projection_manifest)
        or rebuilt_projection_manifest.stream_key != _EXECUTION_PROJECTION_STREAM
        or rebuilt_projection_manifest.event_type != _EXECUTION_PROJECTION_EVENT_TYPE
        or rebuilt_projection_manifest.capability
        != _EXECUTION_PROJECTION_CAPABILITY
    ):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID,
            "execution_projection_stream_manifest",
        )
    normalized_projection_bindings = []
    for value in projection_bindings:
        if not isinstance(value, Mapping) or set(value) != {
            "stream_key",
            "event_id",
            "event_hash",
        }:
            raise _BuildError(
                BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID,
                "execution_projection_event_bindings",
            )
        stream_key = value.get("stream_key")
        event_id = value.get("event_id")
        event_hash = value.get("event_hash")
        if (
            stream_key != _EXECUTION_PROJECTION_STREAM
            or type(event_id) is not str
            or not event_id
            or not _canonical_digest(event_hash)
        ):
            raise _BuildError(
                BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID,
                "execution_projection_event_bindings",
            )
        normalized_projection_bindings.append((stream_key, event_id, event_hash))
    projection_binding_values = tuple(normalized_projection_bindings)
    if (
        len(projection_binding_values) != rebuilt_projection_manifest.event_count
        or len(set(projection_binding_values)) != len(projection_binding_values)
        or projection_binding_values != tuple(sorted(projection_binding_values))
    ):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID,
            "execution_projection_event_bindings",
        )
    expected_events = tuple(
        {
            "stream_key": event.stream_key,
            "event_id": event.event_id,
            "event_hash": event.event_hash,
        }
        for event in request.source_events
    )
    if canonical_bytes(payload.get("source_event_bindings")) != canonical_bytes(
        expected_events
    ):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID,
            "source_event_bindings",
        )
    grouped: dict[str, list[MarketEvent]] = defaultdict(list)
    for event in request.source_events:
        grouped[event.stream_key].append(event)
    expected_authorities = tuple(
        _source_stream_authority(manifest, tuple(grouped[manifest.stream_key]))
        for manifest in manifests
    )
    if canonical_bytes(payload.get("source_stream_authorities")) != canonical_bytes(
        expected_authorities
    ):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID,
            "source_stream_authorities",
        )
    required_streams = {
        _EXECUTION_STREAM,
        _FUNDING_STREAM,
        *(value[0] for value in _PRICE_STREAMS.values()),
    }
    if {value.stream_key for value in manifests} != required_streams or any(
        value.event_count <= 0 for value in manifests
    ):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.AUTHORITY_INVALID,
            "source_stream_cover",
        )
    return manifests


def _validate_common_event(
    request: BinanceUsdmKoruTradifiDevelopmentProfileRequestV1,
    event: MarketEvent,
) -> None:
    if event.instrument_id != _INSTRUMENT or event.supersedes_revision_id is not None:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.SOURCE_CONTEXT_INVALID,
            event.event_id,
        )
    common_provenance = {
        "source_snapshot_id",
        "source_snapshot_hash",
        "source_provenance_hash",
        "source_record_hash",
        "request_hash",
        "capture_hash",
    }
    if (
        not common_provenance <= set(event.payload)
        or any(
            not _canonical_digest(event.payload.get(key)) for key in common_provenance
        )
        or not _canonical_digest(event.source_hash)
        or type(event.source_key) is not str
        or not event.source_key
    ):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.SOURCE_CONTEXT_INVALID,
            "provenance:" + event.event_id,
        )
    source_mode = event.payload.get("source_mode")
    if event.stream_key == _EXECUTION_STREAM:
        required = {
            "archive_member_hash",
            "checksum_member_hash",
            "source_member_hash",
        }
        if source_mode == "execution_manifest_bounded_rest_observations":
            source_prefix = "binance.fapi.bounded-rest.koruusdt.aggtrades."
            required |= {
                "retained_authority_hash",
                "execution_manifest_identity",
                "execution_manifest_file_sha256",
                "availability_authority_digest",
            }
        else:
            source_prefix = "binance.public_data.futures.um.daily.aggtrades."
    elif event.stream_key == _FUNDING_STREAM:
        required = {
            "receipt_hash",
            "receipt_member_hash",
            "response_member_hash",
        }
        source_prefix = "binance.fapi.funding_rate_history."
    else:
        required = {
            "archive_member_hash",
            "checksum_member_hash",
            "source_member_hash",
        }
        if source_mode == "base_manifest_derived_raw_observations":
            source_prefix = "binance.fapi.base-manifest-derived.koruusdt.1h.2026-08-24."
            required.add("retained_authority_hash")
        else:
            source_prefix = "binance.public_data.futures.um.daily."
    if (
        not required <= set(event.payload)
        or any(not _canonical_digest(event.payload.get(key)) for key in required)
        or not event.source_key.startswith(source_prefix)
    ):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.SOURCE_CONTEXT_INVALID,
            "provenance:" + event.event_id,
        )
    if event.timeline_instant > request.composed_at:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.SOURCE_CONTEXT_INVALID,
            "unavailable:" + event.event_id,
        )
    for key in (
        "acquired_at_epoch_nanoseconds",
        "local_retained_acquired_at_epoch_nanoseconds",
    ):
        value = event.payload.get(key)
        if value is not None and (
            type(value) is not int
            or value > request.composed_at.instant.epoch_nanoseconds
        ):
            raise _BuildError(
                BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.SOURCE_CONTEXT_INVALID,
                "acquisition:" + event.event_id,
            )


def _validate_price_event(event: MarketEvent) -> tuple[str, str, int]:
    payload = event.payload
    source_kind = _text(payload, "source_kind")
    purpose = _text(payload, "price_purpose")
    expected = _PRICE_STREAMS.get((source_kind, purpose))
    if (
        expected is None
        or (event.stream_key, event.event_type, event.capability) != expected
    ):
        raise ValueError("price authority")
    opened = _integer(payload, "open_time_milliseconds")
    closed = _integer(payload, "close_time_milliseconds")
    values = tuple(
        _integer(payload, key)
        for key in ("open_units", "high_units", "low_units", "close_units")
    )
    open_units, high_units, low_units, close_units = values
    if (
        payload.get("interval") != "1h"
        or _integer(payload, "price_scale") != 8
        or closed != opened + _HOUR_NS // _MILLISECOND_NS - 1
        or event.event_time.epoch_nanoseconds != (closed + 1) * _MILLISECOND_NS
        or event.available_time != event.event_time
        or min(values) <= 0
        or not low_units <= open_units <= high_units
        or not low_units <= close_units <= high_units
        or (
            purpose in {"valuation", "margin"}
            and payload.get("price_units") != close_units
        )
    ):
        raise ValueError("price row")
    return source_kind, purpose, opened


def _validated_sources(
    request: BinanceUsdmKoruTradifiDevelopmentProfileRequestV1,
) -> tuple[
    tuple[MarketEvent, ...],
    dict[str, tuple[MarketEvent, ...]],
    tuple[MarketEvent, ...],
]:
    executions: list[MarketEvent] = []
    prices: dict[str, list[MarketEvent]] = defaultdict(list)
    funding: list[MarketEvent] = []
    for event in request.source_events:
        _validate_common_event(request, event)
        if event.stream_key == _EXECUTION_STREAM:
            payload = event.payload
            try:
                if (
                    event.event_type != _EXECUTION_EVENT_TYPE
                    or event.capability != _EXECUTION_CAPABILITY
                    or payload.get("price_purpose") != "execution_reference"
                    or _integer(payload, "transaction_time_milliseconds")
                    * _MILLISECOND_NS
                    != event.event_time.epoch_nanoseconds
                    or _integer(payload, "aggregate_trade_id") < 0
                    or _integer(payload, "first_trade_id")
                    > _integer(payload, "last_trade_id")
                    or not _text(payload, "price")
                    or not _text(payload, "quantity")
                    or type(payload.get("is_buyer_maker")) is not bool
                ):
                    raise ValueError
            except ValueError as error:
                raise _BuildError(
                    BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.SOURCE_CONTEXT_INVALID,
                    event.event_id,
                ) from error
            executions.append(event)
            continue
        if event.stream_key == _FUNDING_STREAM:
            payload = event.payload
            try:
                if (
                    event.event_type != _FUNDING_EVENT_TYPE
                    or event.capability != _FUNDING_CAPABILITY
                    or payload.get("funding_purpose") != "funding_publication"
                    or _integer(payload, "funding_slot_milliseconds") * _MILLISECOND_NS
                    != event.event_time.epoch_nanoseconds
                    or event.available_time != event.event_time
                    or payload.get("rate_type") != "Regular"
                    or _integer(payload, "funding_rate_scale") != 8
                    or _integer(payload, "mark_price_scale") != 8
                    or type(payload.get("funding_rate_units")) is not int
                    or _integer(payload, "mark_price_units") <= 0
                    or not _text(payload, "raw_funding_rate")
                    or not _text(payload, "raw_mark_price")
                ):
                    raise ValueError
            except ValueError as error:
                raise _BuildError(
                    BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.FUNDING_INVALID,
                    event.event_id,
                ) from error
            funding.append(event)
            continue
        try:
            _, purpose, _ = _validate_price_event(event)
        except ValueError as error:
            raise _BuildError(
                BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.SOURCE_CONTEXT_INVALID,
                event.event_id,
            ) from error
        prices[purpose].append(event)

    if not executions:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.EXECUTION_SOURCE_MISSING,
            _EXECUTION_STREAM,
        )
    if not funding:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.FUNDING_INVALID,
            _FUNDING_STREAM,
        )
    if len({event.event_time for event in funding}) != len(funding):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.FUNDING_INVALID,
            "duplicate_funding_slot",
        )
    window = request.timeline_window
    if any(
        not window.data_start <= event.event_time < window.end_exclusive
        for event in (*executions, *funding)
    ):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.SOURCE_CONTEXT_INVALID,
            "event_outside_timeline",
        )

    grid = _required_price_grid(window)
    expected_opened = tuple(opened for _, opened in grid)
    if not grid:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.PRICE_GRID_INVALID,
            "empty_price_grid",
        )
    for purpose in ("strategy", "valuation", "margin", "liquidation"):
        rows = tuple(prices.get(purpose, ()))
        mark_rows = tuple(
            event for event in rows if event.payload.get("source_kind") == "mark_price"
        )
        if (
            tuple(
                _integer(event.payload, "open_time_milliseconds") for event in mark_rows
            )
            != expected_opened
        ):
            raise _BuildError(
                BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.PRICE_GRID_INVALID,
                "mark_price:" + purpose,
            )
    index_rows = tuple(
        event
        for event in prices.get("strategy", ())
        if event.payload.get("source_kind") == "index_price"
    )
    if (
        tuple(_integer(event.payload, "open_time_milliseconds") for event in index_rows)
        != expected_opened
    ):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.PRICE_GRID_INVALID,
            "index_price:strategy",
        )
    expected_price_count = len(grid) * 5
    if sum(len(value) for value in prices.values()) != expected_price_count:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.PRICE_GRID_INVALID,
            "price_event_count",
        )
    return (
        tuple(executions),
        {key: tuple(value) for key, value in prices.items()},
        tuple(funding),
    )


def _instrument_revision(contract_type: str) -> BinanceUsdmInstrumentMetadataRevision:
    source = BinanceUsdmInstrumentMetadataSourceRef(
        "crypto.binance_usdm.koru-tradifi.instrument-authority.v1",
        _MODEL_SOURCE_HASHES["instrument"],
    )
    return BinanceUsdmInstrumentMetadataRevision(
        revision_id="koru-usdt-tradifi-post-adjustment-v1:" + contract_type.lower(),
        supersedes_revision_id=None,
        stable_instrument_key=_INSTRUMENT.stable_key,
        symbol="KORUUSDT",
        pair="KORUUSDT",
        contract_type=contract_type,
        status="TRADING",
        onboard_at=_POST_ADJUSTMENT_START,
        delivery_at=BINANCE_USDM_OPEN_ENDED_DELIVERY_AT,
        base_asset="KORU",
        quote_asset="USDT",
        margin_asset="USDT",
        effective_from=_POST_ADJUSTMENT_START,
        available_at=_POST_ADJUSTMENT_START,
        source_ref=source,
    )


def _ordinary_instrument(effective_at: UtcInstant, captured_at: UtcInstant):
    outcome = BinanceUsdmInstrumentModel().resolve_instrument(
        BinanceUsdmInstrumentMetadataQuery(
            _INSTRUMENT.stable_key,
            effective_at,
            captured_at,
            (_instrument_revision("PERPETUAL"),),
        )
    )
    if outcome.result is None:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.MODEL_RESOLUTION_FAILED,
            "ordinary_instrument:" + outcome.failure.code.value,
        )
    return outcome.result


def _tradifi_instrument(request: BinanceUsdmKoruTradifiDevelopmentProfileRequestV1):
    outcome = BinanceUsdmTradifiInstrumentMetadataModel().resolve_instrument(
        BinanceUsdmInstrumentMetadataQuery(
            _INSTRUMENT.stable_key,
            request.timeline_window.data_start,
            request.composed_at.instant,
            (_instrument_revision("TRADIFI_PERPETUAL"),),
        )
    )
    if outcome.result is None:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.MODEL_RESOLUTION_FAILED,
            "tradifi_instrument:" + outcome.failure.code.value,
        )
    return outcome.result


def _order_rules(request, ordinary):
    window = request.timeline_window
    source = BinanceUsdmOrderRuleSourceRef(
        "crypto.binance_usdm.koru-tradifi.order-rules.v1",
        _MODEL_SOURCE_HASHES["order_rules"],
    )
    band = BinanceUsdmOrderRuleBand(
        "koru-tradifi-development-order-rules-v1",
        _INSTRUMENT,
        window.data_start,
        window.end_exclusive,
        _POST_ADJUSTMENT_START,
        "0.01",
        "1000000.00",
        "0.01",
        "0.001",
        "1000.000",
        "0.001",
        "0.001",
        "1000.000",
        "0.001",
        "5.00",
        ("LOT_SIZE", "MARKET_LOT_SIZE", "MIN_NOTIONAL", "PRICE_FILTER"),
        ("LIMIT", "MARKET"),
        ("FOK", "GTC", "GTX", "IOC"),
        BinanceUsdmOrderAdmissionMode.NORMAL,
        True,
        ("MAX_NUM_ALGO_ORDERS", "MAX_NUM_ORDERS"),
        source,
    )
    book = BinanceUsdmOrderRuleBook(
        "binance-usdm-koru-tradifi-development-order-rules-v1",
        1,
        _INSTRUMENT,
        window.data_start,
        window.end_exclusive,
        (band,),
    )
    outcome = BinanceUsdmOrderRuleModel().resolve_order_rules(
        BinanceUsdmOrderRuleQuery(
            ordinary,
            _SESSION_ID,
            window.data_start,
            request.composed_at.instant,
            book,
        )
    )
    if outcome.result is None:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.MODEL_RESOLUTION_FAILED,
            "order_rules:" + outcome.failure.code.value,
        )
    return outcome.result


def _margin_tiers(request, ordinary):
    window = request.timeline_window
    bracket = BinanceUsdmMarginTierBracket("1", "0", "10000", "0.05", "0", "1", "1")
    band = BinanceUsdmMarginTierBand(
        "koru-tradifi-development-margin-v1",
        _INSTRUMENT,
        window.data_start,
        window.end_exclusive,
        _EVIDENCE_INSTANT,
        BinanceUsdmMarginTierScope.DEFAULT_SYMBOL,
        None,
        (bracket,),
        BinanceUsdmMarginTierSourceRef(
            "crypto.binance_usdm.koru-tradifi.margin-tiers.v1",
            _MODEL_SOURCE_HASHES["margin_tiers"],
            "CONTRACT_INFO_BRACKET_UPDATE",
        ),
    )
    book = BinanceUsdmMarginTierRuleBook(
        "binance-usdm-koru-tradifi-development-margin-v1",
        1,
        _INSTRUMENT,
        _USDT,
        window.data_start,
        window.end_exclusive,
        (band,),
    )
    outcome = BinanceUsdmMarginTierModel().resolve_margin_tiers(
        BinanceUsdmMarginTierQuery(
            ordinary,
            window.data_start,
            request.composed_at,
            book,
        )
    )
    if outcome.result is None:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.MODEL_RESOLUTION_FAILED,
            "margin_tiers:" + outcome.failure.code.value,
        )
    return outcome.result


def _account_profile(request, ordinary):
    refs = tuple(
        BinanceUsdmAccountProfileSourceRef(
            kind,
            f"crypto.binance_usdm.koru-tradifi.account.{kind.value}.v1",
            _MODEL_SOURCE_HASHES[kind.value],
            f"development/{kind.value}/koruusdt.v1",
            f"koru-tradifi-{kind.value}-v1",
            None,
        )
        for kind in BinanceUsdmAccountSourceKind
    )
    window = request.timeline_window
    band = BinanceUsdmAccountProfileBand(
        "koru-tradifi-development-account-v1",
        request.account_id,
        _INSTRUMENT,
        window.data_start,
        window.end_exclusive,
        _EVIDENCE_INSTANT,
        BinanceUsdmAccountProfileScope.STANDARD_UM,
        0,
        True,
        False,
        False,
        -1,
        "CROSSED",
        False,
        "1",
        "10000.00000000",
        "0.00020000",
        "0.00050000",
        False,
        refs,
    )
    book = BinanceUsdmHistoricalAccountProfileBook(
        "binance-usdm-koru-tradifi-development-account-v1",
        1,
        request.account_id,
        _INSTRUMENT,
        window.data_start,
        window.end_exclusive,
        (band,),
    )
    outcome = BinanceUsdmAccountProfileModel().resolve_account_profile(
        BinanceUsdmAccountProfileQuery(
            ordinary,
            request.account_id,
            book,
            window.data_start,
            request.composed_at,
            _USDT,
        )
    )
    if outcome.result is None:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.MODEL_RESOLUTION_FAILED,
            "account_profile:" + outcome.failure.code.value,
        )
    return outcome.result


def _sim_at(instant: UtcInstant) -> SimulationInstant:
    return SimulationInstant(
        instant, TimelinePhase(0, "market_data"), SourceSequence(0)
    )


def _price_source_ref(event: MarketEvent) -> BinanceUsdmPriceSourceRef:
    return BinanceUsdmPriceSourceRef(
        event.source_key,
        event.source_hash,
        event.stream_key,
        event.revision_id,
        None,
    )


def _decimal_from_units(units: int, scale: int = 8) -> str:
    whole, fraction = divmod(abs(units), 10**scale)
    sign = "-" if units < 0 else ""
    return f"{sign}{whole}.{fraction:0{scale}d}"


def _aggregate_record(event: MarketEvent) -> BinanceUsdmAggregateTradePrice:
    payload = event.payload
    return BinanceUsdmAggregateTradePrice(
        event.event_id,
        _INSTRUMENT,
        _integer(payload, "aggregate_trade_id"),
        _text(payload, "price"),
        _text(payload, "quantity"),
        _integer(payload, "first_trade_id"),
        _integer(payload, "last_trade_id"),
        event.event_time,
        _sim_at(event.event_time),
        bool(payload["is_buyer_maker"]),
        _price_source_ref(event),
    )


def _mark_record(event: MarketEvent) -> BinanceUsdmMarkPriceKline:
    payload = event.payload
    closed = UtcInstant(
        (_integer(payload, "close_time_milliseconds") + 1) * _MILLISECOND_NS
    )
    return BinanceUsdmMarkPriceKline(
        event.event_id,
        _INSTRUMENT,
        "1h",
        _integer(payload, "open_time_milliseconds"),
        _integer(payload, "close_time_milliseconds"),
        _decimal_from_units(_integer(payload, "open_units")),
        _decimal_from_units(_integer(payload, "high_units")),
        _decimal_from_units(_integer(payload, "low_units")),
        _decimal_from_units(_integer(payload, "close_units")),
        _sim_at(closed),
        _sim_at(closed),
        True,
        _price_source_ref(event),
    )


def _price_resolution(request, events, purpose):
    window = request.timeline_window
    source_kind = (
        BinanceUsdmPriceSourceKind.AGGREGATE_TRADE
        if purpose is PricePurpose.EXECUTION_REFERENCE
        else BinanceUsdmPriceSourceKind.MARK_PRICE_KLINE
    )
    first = events[0]
    coverage_from = (
        first.event_time
        if purpose is PricePurpose.EXECUTION_REFERENCE
        else UtcInstant(
            _integer(first.payload, "open_time_milliseconds") * _MILLISECOND_NS
        )
    )
    coverage_to_exclusive = (
        UtcInstant(events[-1].event_time.epoch_nanoseconds + 1)
        if purpose is PricePurpose.EXECUTION_REFERENCE
        else window.end_exclusive
    )
    coverage = BinanceUsdmPriceStreamCoverage(
        (
            "koru-tradifi-execution_reference-coverage-v2"
            if purpose is PricePurpose.EXECUTION_REFERENCE
            else f"koru-tradifi-{purpose.value}-coverage-v1"
        ),
        _INSTRUMENT,
        purpose,
        source_kind,
        coverage_from,
        coverage_to_exclusive,
        first.stream_key,
        _price_source_ref(
            first if purpose is PricePurpose.LIQUIDATION else events[-1]
        ),
    )
    aggregate = (
        tuple(_aggregate_record(event) for event in events)
        if purpose is PricePurpose.EXECUTION_REFERENCE
        else ()
    )
    marks = (
        tuple(_mark_record(event) for event in events)
        if purpose is not PricePurpose.EXECUTION_REFERENCE
        else ()
    )
    book = BinanceUsdmHistoricalPriceBook(
        f"binance-usdm-koru-tradifi-{purpose.value}-price-book-v1",
        1,
        _INSTRUMENT,
        _USDT,
        (coverage,),
        aggregate,
        marks,
    )
    if purpose is PricePurpose.LIQUIDATION:
        liquidation_start = marks[0].interval_start
        liquidation_end = marks[-1].interval_end_exclusive
        requested_at = liquidation_start
        stale = None
    else:
        liquidation_start = None
        liquidation_end = None
        requested_at = events[-1].event_time
        stale = StaleMarkPolicy(
            f"binance-usdm-koru-tradifi-{purpose.value}-stale-v1",
            1,
            purpose,
            _HOUR_NS,
            True,
        )
    resolution = _ordinary_instrument(requested_at, request.composed_at.instant)
    outcome = BinanceUsdmPriceStreamModel().resolve_price_purpose(
        BinanceUsdmPricePurposeQuery(
            resolution,
            book,
            purpose,
            requested_at,
            request.composed_at,
            stale,
            liquidation_start,
            liquidation_end,
        )
    )
    if outcome.result is None:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.MODEL_RESOLUTION_FAILED,
            f"price_{purpose.value}:" + outcome.failure.code.value,
        )
    return outcome.result


def _funding_resolutions(request, events, order_rules):
    records = tuple(
        BinanceUsdmFundingRateRecord(
            _INSTRUMENT,
            _integer(event.payload, "funding_slot_milliseconds"),
            _text(event.payload, "raw_funding_rate"),
            _text(event.payload, "raw_mark_price"),
            "Regular",
            _sim_at(event.event_time),
            event.event_id,
            event.revision_id,
            BinanceUsdmFundingSourceRef(
                "funding_rate_history",
                event.source_key,
                event.source_hash,
                event.stream_key,
                event.revision_id,
                None,
            ),
        )
        for event in events
    )
    resolutions = []
    for record in records:
        target = record.funding_time
        coverage = BinanceUsdmFundingCoverage(
            "koru-tradifi-funding-coverage-v1",
            _INSTRUMENT,
            request.timeline_window.data_start,
            request.timeline_window.end_exclusive,
            _FUNDING_STREAM,
            1,
            record.source_ref,
        )
        book = BinanceUsdmHistoricalFundingBook(
            "binance-usdm-koru-tradifi-funding-v1",
            1,
            _INSTRUMENT,
            (coverage,),
            (record,),
        )
        ordinary = _ordinary_instrument(target, request.composed_at.instant)
        contract = LinearPerpetualContract(
            ordinary.instrument,
            order_rules.quantity_scale,
            order_rules.price_scale,
            ordinary.contract_metadata.contract_multiplier,
        )
        key = LinearFundingApplicationKey.derive(
            request.account_id,
            FundingSlotId.derive(_INSTRUMENT, target),
        )
        outcome = BinanceUsdmFundingSourceModelV2().resolve_funding_source(
            BinanceUsdmFundingSourceQuery(
                ordinary,
                contract,
                key,
                book,
                target,
                request.composed_at,
            )
        )
        if outcome.result is None:
            raise _BuildError(
                BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.MODEL_RESOLUTION_FAILED,
                "funding:" + outcome.failure.code.value,
            )
        resolutions.append(outcome.result)
    if len(resolutions) != len(events) or len(
        {value.query.application_key for value in resolutions}
    ) != len(events):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.FUNDING_INVALID,
            "funding_application_identity",
        )
    return tuple(resolutions)


def _slippage(window: TimelineWindow) -> tuple[DeterministicBpsSlippageModel, Quantity]:
    quantity = Quantity(1_000_000, Scale(3), str(_INSTRUMENT))
    envelope = SlippageApplicabilityEnvelope.create(
        envelope_key="koruusdt-first-retained-trade-development-v1",
        envelope_version=1,
        instrument_id=_INSTRUMENT,
        valid_from=window.data_start,
        valid_to_exclusive=window.end_exclusive,
        maximum_quantity=quantity,
        allowed_market_state_keys=("normal",),
    )
    calibration = SlippageCalibrationRef(
        "koruusdt-first-retained-trade-development-v1",
        1,
        canonical_sha256(
            {
                "type": "koruusdt_first_retained_trade_slippage_calibration_v1",
                "basis_points": 5,
            }
        ),
    )
    model = DeterministicBpsSlippageModel(
        SimulationComponentRef(
            SimulationPortType.SLIPPAGE_MODEL,
            SlippageModelKind.DETERMINISTIC_BPS_V1.value,
            1,
            canonical_sha256(
                {
                    "calibration_ref": calibration,
                    "basis_points": 5,
                    "applicability_envelope": envelope,
                }
            ),
        ),
        calibration,
        envelope,
        5,
        Scale(0),
        RoundingPolicy.HALF_UP,
        (),
    )
    return model, quantity


class _ImmutableWireMapping(Mapping[str, object]):
    __slots__ = ("_items", "_values")

    def __init__(self, value: Mapping[str, object]) -> None:
        self._items = tuple(value)
        self._values = tuple(_freeze(value[key]) for key in self._items)

    def __getitem__(self, key: str) -> object:
        try:
            value = self._values[self._items.index(key)]
        except ValueError as error:
            raise KeyError(key) from error
        return _wire_value(value)

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)


def _wire_value(value: object) -> object:
    if type(value) is tuple:
        return [_wire_value(item) for item in value]
    return value


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return _ImmutableWireMapping(value)
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


def _build_result(
    request: BinanceUsdmKoruTradifiDevelopmentProfileRequestV1,
) -> BinanceUsdmKoruTradifiDevelopmentProfileResultV1:
    _validate_timeline(request)
    manifests = _validate_source_profile_authority(request)
    executions, prices, funding_events = _validated_sources(request)
    ordinary = _ordinary_instrument(
        request.timeline_window.data_start,
        request.composed_at.instant,
    )
    tradifi = _tradifi_instrument(request)
    order = _order_rules(request, ordinary)
    margin = _margin_tiers(request, ordinary)
    account = _account_profile(request, ordinary)
    price_resolutions = (
        _price_resolution(
            request,
            executions,
            PricePurpose.EXECUTION_REFERENCE,
        ),
        *(
            _price_resolution(
                request,
                tuple(
                    event
                    for event in prices[purpose_name]
                    if event.payload.get("source_kind") == "mark_price"
                ),
                purpose,
            )
            for purpose_name, purpose in _PRICE_PURPOSES.items()
        ),
    )
    funding = _funding_resolutions(request, funding_events, order)
    capacity = BinanceUsdmAccountCapacityEvidence(
        "binance-usdm-koru-tradifi-development-capacity-v1",
        1,
        request.account_id,
        _INSTRUMENT,
        request.timeline_window.data_start,
        request.timeline_window.end_exclusive,
        _EVIDENCE_INSTANT,
        200,
        10,
        order.active_band.source_ref.source_key,
        order.active_band.source_ref.source_hash,
        "koru-tradifi-development-capacity-v1",
    )
    slippage, quantity = _slippage(request.timeline_window)
    composition_request = BinanceUsdmTradifiProfileCompositionRequest(
        instrument_metadata=tradifi,
        order_rules=order,
        margin_tiers=margin,
        price_purposes=price_resolutions,
        funding_sources=funding,
        account_profile=account,
        account_capacity=capacity,
        timeline_window=request.timeline_window,
        composed_at=request.composed_at,
        calendar_refs=(request.xkrx_calendar_ref, request.arcx_calendar_ref),
        post_adjustment_unit_regime_ref=request.post_adjustment_unit_regime_ref,
        slippage_model=slippage,
        admitted_maximum_quantity=quantity,
        required_market_state_keys=("normal",),
        raw_exact_valuation=True,
        raw_exact_margin=True,
        raw_exact_strategy=True,
        raw_exact_liquidation=True,
    )
    composed = BinanceUsdmTradifiProfileComposer().compose(composition_request)
    if composed.result is None:
        failure = composed.failure
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.PROFILE_COMPOSITION_FAILED,
            failure.code.value if failure is not None else "missing_failure",
        )
    raw_wire = json.loads(canonical_bytes(composition_request))
    decoded = decode_binance_usdm_tradifi_profile_composition_request_v1(
        raw_wire,
        composition_request.request_hash,
    )
    replay = BinanceUsdmTradifiProfileComposer().compose(decoded)
    if replay.result is None or replay.result != composed.result:
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.RESULT_INVALID,
            "profile_wire_replay",
        )
    wire = _freeze(raw_wire)
    if not isinstance(wire, Mapping):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.RESULT_INVALID,
            "profile_wire",
        )
    funding_manifest = next(
        value for value in manifests if value.stream_key == _FUNDING_STREAM
    )
    if (
        len(funding) != funding_manifest.event_count
        or len({value.query.application_key for value in funding})
        != funding_manifest.event_count
        or len({value.query.application_key.funding_slot_id for value in funding})
        != funding_manifest.event_count
    ):
        raise _BuildError(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.FUNDING_INVALID,
            "funding_manifest_identity",
        )
    return BinanceUsdmKoruTradifiDevelopmentProfileResultV1(
        request=request,
        profile_composition_request=composition_request,
        resolved_profile=composed.result,
        profile_registry=composed.result.profile_registry,
        financial_dispatcher_spec=composed.result.financial_dispatcher_spec,
        profile_composition_request_wire=wire,
        profile_composition_request_hash=composition_request.request_hash,
        source_stream_hashes=tuple(
            (value.stream_key, value.content_hash) for value in manifests
        ),
        source_stream_counts=tuple(
            (value.stream_key, value.event_count) for value in manifests
        ),
        source_profile_authority_ref=request.source_profile_authority_ref,
        source_profile_authority_hash=(
            request.source_profile_authority_envelope.content_hash
        ),
    )


def build_binance_usdm_koru_tradifi_development_profile_v1(
    request: BinanceUsdmKoruTradifiDevelopmentProfileRequestV1,
) -> BinanceUsdmKoruTradifiDevelopmentProfileOutcomeV1:
    """Build the fixed offline development profile from retained V2 source events."""

    try:
        trusted = _trusted_request(request)
        result = _build_result(trusted)
    except _BuildError as error:
        return _failed(error.code, error.subject)
    except (KeyError, TypeError, ValueError) as error:
        return _failed(
            BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1.RESULT_INVALID,
            f"{type(error).__name__}:{error}".rstrip(":"),
        )
    return BinanceUsdmKoruTradifiDevelopmentProfileOutcomeV1(result=result)


__all__ = [
    "BinanceUsdmKoruTradifiDevelopmentProfileFailureCodeV1",
    "BinanceUsdmKoruTradifiDevelopmentProfileFailureV1",
    "BinanceUsdmKoruTradifiDevelopmentProfileOutcomeV1",
    "BinanceUsdmKoruTradifiDevelopmentProfileRequestV1",
    "BinanceUsdmKoruTradifiDevelopmentProfileResultV1",
    "build_binance_usdm_koru_tradifi_development_profile_v1",
]
