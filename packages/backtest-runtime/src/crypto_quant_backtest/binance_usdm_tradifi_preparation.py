"""Fail-closed StageA preparation for the Binance USD-M TradFi bar profile."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum

import crypto_quant_domain as domain
from crypto_quant_market_data import (
    EventCursor,
    MarketBundleCapability,
    MarketBundleManifest,
    MarketBundleReader,
    MarketBundleRef,
    MarketEvent,
    MarketStreamManifest,
)

from .artifact_envelope_reader import ArtifactEnvelopeReader
from .binance_usdm_koru_tradifi_development_profile_v1 import (
    BinanceUsdmKoruTradifiDevelopmentProfileRequestV1,
    build_binance_usdm_koru_tradifi_development_profile_v1,
)
from .binance_usdm_tradifi_profile import (
    BinanceUsdmTradifiProfileComposer,
    BinanceUsdmTradifiProfileCompositionRequest,
    BinanceUsdmTradifiResolvedProfile,
)
from .binance_usdm_tradifi_profile_wire import (
    decode_binance_usdm_tradifi_profile_composition_request_v1,
)
from .financial_dispatch import FinancialDispatcherSpec
from .profile_build_manifest import _provider_build_manifest
from .resolution import (
    BacktestProfileRegistry,
    BuildArtifactManifest,
    RequestedResultGrade,
)
from .slippage import DeterministicBpsSlippageModel
from .target_stream import (
    TARGET_STREAM_CAPABILITY,
    TARGET_STREAM_EVENT_TYPE,
    PrecomputedTargetStream,
)
from .timeline import TimelineWindow

_SCHEMA_VERSION = 1
_BUNDLE_SCHEMA_VERSION_V2 = 2
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_V2_BUNDLE_KEY = re.compile(
    r"binance-usdm-koru-tradifi-execution-development-v2-[0-9a-f]{64}\Z"
)
_PARAMETER_IDS = tuple(f"p{index:02d}" for index in range(1, 9))
_TARGET_PREFIX = "binance_usdm.tradifi.target.koruusdt.closed_market_range."
_PREPARATION_STREAM = "binance_usdm.tradifi.preparation_authority.v1"
_PREPARATION_EVENT_TYPE = "binance_usdm_tradifi_preparation_authority_v1"
_PREPARATION_STREAM_V2 = "binance_usdm.tradifi.preparation_authority.v2"
_PREPARATION_EVENT_TYPE_V2 = "binance_usdm_tradifi_preparation_authority_v2"
_PREPARATION_CAPABILITY = MarketBundleCapability(
    "binance_usdm.tradifi.preparation-authority", 1
)
_REQUIRED_EQUITY = domain.Money(1_000_000_000_000, domain.Scale(8), "USDT")
_USDT = domain.CurrencyId("USDT")
_REQUIRED_ALLOCATION = "1"
_REQUIRED_NOTIONAL = "1000"
_STRATEGY_ID = "koruusdt_closed_market_range_v1"
_SLEEVE_ID = "koruusdt-closed-market-range"
_INSTRUMENT = {"stable_key": "koru-usdt-tradifi-perpetual", "venue": "binance_usdm"}
_INSTRUMENT_WIRE = {"type": "instrument_id", **_INSTRUMENT}
_AUTHORITY_PAYLOAD_KEYS = frozenset(
    {
        "schema_version",
        "profile_composition_request_wire",
        "profile_composition_request_hash",
        "strategy_definition_ref",
        "parameter_target_bindings",
        "xkrx_calendar_ref",
        "arcx_calendar_ref",
        "post_adjustment_unit_regime_ref",
        "source_snapshot_bindings",
        "source_fragment_digest",
        "target_result_digest",
        "price_purpose_authority_binding",
        "required_initial_equity",
        "required_sleeve_allocation_fraction",
        "required_position_notional_usdt",
        "source_limitations",
    }
)
_STREAMING_AUTHORITY_KEYS = frozenset(
    {
        "source_fragment_digest",
        "target_result_digest",
        "aggregate_trade_boundary_index_request_hash",
        "aggregate_trade_boundary_index_result_digest",
        "aggregate_trade_streamed_reconstruction_digest",
        "aggregate_trade_intra_day_raw_id_gap_stream",
        "aggregate_trade_cross_date_raw_id_gap_stream",
        "aggregate_trade_coverage_gaps",
        "missing_boundaries",
        "source_profile_authority_ref",
        "source_profile_authority_hash",
        "profile_composition_request_hash",
    }
)
_AUTHORITY_PAYLOAD_KEYS_V2 = frozenset(
    {
        "schema_version",
        "profile_composition_request_wire",
        "strategy_definition_ref",
        "parameter_target_bindings",
        "xkrx_calendar_ref",
        "arcx_calendar_ref",
        "post_adjustment_unit_regime_ref",
        "source_profile_authority_envelope",
        "source_snapshot_bindings",
        "price_purpose_authority_binding",
        "required_initial_equity",
        "required_sleeve_allocation_fraction",
        "required_position_notional_usdt",
        "source_limitations",
        *_STREAMING_AUTHORITY_KEYS,
    }
)
_PARAMETER_BINDING_KEYS = frozenset(
    {
        "parameter_id",
        "parameter_ref",
        "target_stream_key",
        "target_stream_digest",
    }
)
_STRATEGY_PAYLOAD_KEYS = frozenset(
    {
        "strategy_id",
        "sleeve_id",
        "instrument_id",
        "required_synthetic_equity_usdt",
        "required_sleeve_allocation_fraction",
        "target_exposure_fraction",
        "position_notional_usdt",
        "future_preparation_binding",
        "rules",
        "parameter_schema",
        "parameter_grid",
        "development_authorized",
        "deployment_authorized",
    }
)
_PARAMETER_PAYLOAD_KEYS = frozenset(
    {
        "strategy_definition_ref",
        "strategy_id",
        "parameter_set_id",
        "formation_hours",
        "max_formation_range",
        "max_hold_hours",
        "entry_zone_fraction",
        "stop_range_multiple",
        "max_abs_premium",
        "max_trades_per_closed_interval",
        "position_notional_usdt",
        "development_authorized",
        "deployment_authorized",
    }
)
_CALENDAR_PAYLOAD_KEYS = {
    "xkrx_regular_session_calendar": frozenset(
        {
            "type",
            "schema_version",
            "venue",
            "session_kind",
            "coverage",
            "source_timezone",
            "source_utc_offset",
            "source_dst_observance",
            "source_local_regular_hours",
            "source_closures_2026",
            "applied_closure_dates",
            "source_retained_not_emitted_boundary_closure_dates",
            "sessions",
            "source",
            "limitations",
            "decision_grade_eligible",
            "deployment_authorized",
        }
    ),
    "arcx_koru_core_session_calendar": frozenset(
        {
            "type",
            "schema_version",
            "venue",
            "instrument",
            "session_kind",
            "coverage",
            "source_timezone",
            "source_utc_offset_for_coverage",
            "source_dst_state_for_coverage",
            "source_local_core_hours",
            "source_closures_2026",
            "applied_closure_dates",
            "source_early_close_dates_2026",
            "early_close_dates_in_coverage",
            "sessions",
            "source",
            "limitations",
            "decision_grade_eligible",
            "deployment_authorized",
        }
    ),
}
_UNIT_PAYLOAD_KEYS = frozenset(
    {
        "type",
        "schema_version",
        "venue",
        "instrument",
        "coverage",
        "adjustment",
        "market_session_states",
        "authoritative_post_adjustment_admission",
        "source_articles",
        "source",
        "limitations",
        "decision_grade_eligible",
        "deployment_authorized",
    }
)
_EXPECTED_STRATEGY_REF = domain.ArtifactRef(
    "strategy_definition",
    1,
    "sha256:b5c153a127ad3ed4c1286ba4d2948fa52e581239f0d3bd01f3074c410eed9c81",
)
_EXPECTED_PARAMETER_REFS = tuple(
    domain.ArtifactRef("strategy_parameter_set", 1, content_hash)
    for content_hash in (
        "sha256:23911e260d3fe6e4fbc009851523bbb095209466e44c70b63ae2114e37f05f78",
        "sha256:f02521f9194c671a24c7a05bb0ebe3e11eac2cfddccd5b3c52e11f58b1bab9f9",
        "sha256:b577c11a94a1f4fed3247cf9bd3508de092be7d14a01dfd58e3805b1a4a69c43",
        "sha256:bd3c440d01a144317ddacad9814b0791e13079bc898c4e06dea455566ad7a14a",
        "sha256:cbcd7d3a81c71411abe0c2191b0f7b17209b3d55965361c8e6c0798b5c1e30e9",
        "sha256:bec582ad24da484a13c0fc960e4ae351c4cbd62f7806d07a03d579db04cdffc0",
        "sha256:aa46923df87d9ed25ee58fde6e4af0108d7e79e3ad7cfe17ac26d0dd9bf910d3",
        "sha256:e85e8a778fcdfdc4176f9fa6c395c86e47bd7a356309dc08b3074024bfa89911",
    )
)
_EXPECTED_AUTHORITY_REFS = (
    domain.ArtifactRef(
        "xkrx_regular_session_calendar",
        1,
        "sha256:dcffef007cd8a9c00319259663c32cd09812904562229b3a2084d03718624d35",
    ),
    domain.ArtifactRef(
        "arcx_koru_core_session_calendar",
        1,
        "sha256:d9a75b431730740b6e5793f99a71978513422ed78f6dd7bda4485f20a75a9926",
    ),
    domain.ArtifactRef(
        "binance_usdm_tradifi_post_adjustment_unit_regime",
        1,
        "sha256:dca20ef381e3e95469e7507d422430317e471677a1d2450b188a918cbb146e18",
    ),
)
_SOURCE_LIMITATIONS = (
    "aggregate_trade_event_represented_by_bar_open_v1",
    "development_only",
    "first_retained_trade_full_fill_only",
    "historical_account_and_market_archive_completeness_unproven",
    "post_adjustment_single_unit_regime_only",
    "source_fragment_decision_grade_ineligible",
    "source_fragment_deployment_unauthorized",
)
_SOURCE_LIMITATIONS_V2 = (
    "selected_source_events_form_the_executable_stream",
    "full_raw_data_is_retained_transitively_in_source_snapshots",
    "v2_projection_target_and_authority_identities",
    "development_only",
)
_PRICE_PURPOSE_STREAM = "binance_usdm.tradifi.price_purpose.authority.koruusdt.v1"
_PRICE_PURPOSE_EVENT_TYPE = "binance_usdm_tradifi_price_purpose_binding_v1"
_PRICE_PURPOSE_STREAM_V2 = "binance_usdm.tradifi.price_purpose.authority.koruusdt.v2"
_PRICE_PURPOSE_EVENT_TYPE_V2 = "binance_usdm_tradifi_price_purpose_binding_v2"
_PRICE_PURPOSE_CAPABILITY = MarketBundleCapability(
    "binance_usdm.price-purpose-streams", 1
)
_PRICE_PURPOSES = (
    "execution_reference",
    "liquidation",
    "margin",
    "valuation",
)
_PRICE_PURPOSE_SOURCE_KINDS = {
    "execution_reference": "aggregate_trade",
    "liquidation": "mark_price_kline",
    "margin": "mark_price_kline",
    "valuation": "mark_price_kline",
}
_PRICE_PURPOSE_SOURCE_STREAMS = {
    "execution_reference": "binance_usdm.aggregate_trades.execution_reference.koruusdt.tradifi.v1",
    "liquidation": "binance_usdm.mark_price.liquidation.koruusdt.1h.v1",
    "margin": "binance_usdm.mark_price.margin.koruusdt.1h.v1",
    "valuation": "binance_usdm.mark_price.valuation.koruusdt.1h.v1",
}
_SOURCE_SNAPSHOT_KEYS = frozenset(
    {
        "source_kind",
        "source_snapshot_id",
        "source_snapshot_hash",
        "source_normalization_hash",
    }
)
_EXPECTED_SOURCE_SNAPSHOT_BINDINGS = (
    (
        "aggregate_trades",
        "sha256:0ed7220e28fe2a26298eb473385801e15ee054dada76bf07666326fb4f548a1d",
        "sha256:3bb575203793dd746836cf823f48462658a03abd61294735e9244f8ef0e6746b",
        "sha256:bab37b043fa05d1a09570ef84a673bc0c45d69365ce9db5830bc2f9508209658",
    ),
    (
        "calendar_unit",
        "sha256:f4c5e93cc274e9e5ea6ba52f79d90900fff3963a2c569b4c5b97a0668e76e838",
        "sha256:96efa663b51e75cbe3667e6f8684c3aa2368bf03b76ebc3e27f50d2768469189",
        "sha256:88a974a0f29d7ba293aa94d9ffc501ac1c2ae310f76f2f6895f9f5f109bc3bab",
    ),
    (
        "funding_history",
        "sha256:550cdfcce44af8d3687c87334bca29ccff4492fb8eba185b8a46c0b4ed0bced8",
        "sha256:951e9363fad34f29e1e839395b507bf0bd6453098146f91c3e09b544064475b9",
        "sha256:27a6d00659b9d3a27647f850fff97cfebd5630895ba6dc09243b741e9f297631",
    ),
    (
        "index_price",
        "sha256:a7ce6172b2ff99f0e8d4d80af96d801ab272f9eb492720110161fb8c511f7e58",
        "sha256:f292a492c04de2b49aa14373151d16a99c9b85bf40ad6ec7a4af98d3092e885a",
        "sha256:a655d278888f9e02e49ac3c716b5e4e4aaa215211c7674a7dbcb8ad6d2c984f4",
    ),
    (
        "index_price",
        "sha256:bc81d9859ab17e8c19e83c3d9787d63fe05ef3a4c8a5b7e94450bead181ef450",
        "sha256:0ddac2acbf3655235aece0937b3b653f597d72e5dcc9f227afadfa636d317da5",
        "sha256:fb6be873ae059dbea1c6a1359d8083dbce190313f20601a8aa56135ae40df36b",
    ),
    (
        "mark_price",
        "sha256:a7ce6172b2ff99f0e8d4d80af96d801ab272f9eb492720110161fb8c511f7e58",
        "sha256:5186090f5c18843dd90aa84b4996349d8d7041db6605ab857f8ddcc5a7162101",
        "sha256:9ce04f68438a9403a43f299a10ee64e1af59e59bd13b4ad1ddbeea2d454bffea",
    ),
    (
        "mark_price",
        "sha256:bc81d9859ab17e8c19e83c3d9787d63fe05ef3a4c8a5b7e94450bead181ef450",
        "sha256:3f95a94fdd354ebea6012dc330bd798869577180f9181896f50f169444a888d5",
        "sha256:29eccb57504240f4b31d363309fd18184f05aee461b8dd6e1a37778fbb4a4dbb",
    ),
)
_PRICE_AUTHORITY_PAYLOAD_KEYS = frozenset(
    {
        "schema_version",
        "instrument_id",
        "price_purpose_bindings",
        "source_fragment_digest",
        "profile_composition_request_hash",
    }
)
_PRICE_AUTHORITY_PAYLOAD_KEYS_V2 = frozenset(
    {"schema_version", "instrument_id", "price_purpose_bindings"}
    | _STREAMING_AUTHORITY_KEYS
)
_PRICE_BINDING_KEYS = frozenset(
    {
        "price_purpose",
        "source_kind",
        "stream_id",
        "source_ref",
        "coverage_from",
        "coverage_to_exclusive",
        "coverage_hash",
        "price_resolution_hash",
        "source_stream_manifest",
    }
)
_SOURCE_MANIFEST_KEYS = frozenset(
    {
        "stream_key",
        "event_type",
        "original_capability",
        "event_count",
        "content_hash",
    }
)
_PRICE_EVENT_BINDING_KEYS = frozenset(
    {"stream_key", "event_type", "event_id", "event_hash"}
)
_SOURCE_SNAPSHOT_KEYS_V2 = frozenset(
    {
        "source_kind",
        "source_snapshot_id",
        "source_snapshot_hash",
        "source_evidence_hash",
    }
)
_SOURCE_PROFILE_AUTHORITY_TYPE = "binance_usdm_koru_source_profile_authority"
_SOURCE_PROFILE_AUTHORITY_SCHEMA_VERSION = 2
_EXECUTION_PROJECTION_STREAM_V1 = (
    "binance_usdm.tradifi.bar_open.first_retained_aggregate_trade.koruusdt.1h.v1"
)
_EXECUTION_PROJECTION_STREAM_V2 = (
    "binance_usdm.tradifi.bar_open.first_retained_aggregate_trade.koruusdt.1h.v2"
)
_EXECUTION_PROJECTION_EVENT_TYPE = "bar_open"
_EXECUTION_PROJECTION_CAPABILITY = MarketBundleCapability("bar_open", 1)
_EXECUTION_PROJECTION_SOURCE_V2 = (
    "binance_usdm.tradifi.first_retained_aggregate_trade_projection.koruusdt.1h.v2"
)
_ACCOUNT_STREAM_V1 = "binance_usdm.tradifi.account.authority.koruusdt.v1"
_ACCOUNT_STREAM_V2 = "binance_usdm.tradifi.account.authority.koruusdt.v2"
_ACCOUNT_EVENT_TYPE = "account_financial_event"
_ACCOUNT_CAPABILITY = MarketBundleCapability("account.financial-event", 1)
_SOURCE_STREAM_KEYS = frozenset(
    {
        "binance_usdm.aggregate_trades.execution_reference.koruusdt.tradifi.v1",
        "binance_usdm.funding_history.publications.koruusdt.v1",
        "binance_usdm.mark_price.strategy.koruusdt.1h.v1",
        "binance_usdm.mark_price.valuation.koruusdt.1h.v1",
        "binance_usdm.mark_price.margin.koruusdt.1h.v1",
        "binance_usdm.mark_price.liquidation.koruusdt.1h.v1",
        "binance_usdm.index_price.strategy.koruusdt.1h.v1",
    }
)
_SOURCE_PROFILE_AUTHORITY_PAYLOAD_KEYS = frozenset(
    {
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
)
_SOURCE_MANIFEST_WIRE_KEYS = frozenset(
    {
        "type",
        "stream_key",
        "event_type",
        "capability",
        "event_count",
        "content_hash",
    }
)


def _canonical_text(name: str, value: object) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be canonical non-empty text")
    return value


def _canonical_hash(name: str, value: object) -> str:
    text = _canonical_text(name, value)
    if _HASH.fullmatch(text) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return text


def _mapping(value: object, subject: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        raise ValueError(f"{subject} must be an object")
    return value


def _sequence(value: object, subject: str) -> tuple[object, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{subject} must be an array")
    return tuple(value)


def _same(left: object, right: object) -> bool:
    return domain.canonical_bytes(left) == domain.canonical_bytes(right)


def _exact_false(value: object) -> bool:
    return type(value) is bool and not value


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiBarRequestIntent:
    experiment_id: str | None
    timeline_window: TimelineWindow
    execution_account_id: str
    reporting_currency: domain.CurrencyId
    master_random_seed: int
    market_bundle_ref: MarketBundleRef
    strategy_definition_ref: domain.ArtifactRef
    strategy_parameter_set_ref: domain.ArtifactRef
    result_grade_requested: RequestedResultGrade

    def __post_init__(self) -> None:
        if self.experiment_id is not None:
            _canonical_text("experiment_id", self.experiment_id)
        if type(self.timeline_window) is not TimelineWindow:
            raise TypeError("timeline_window must be exact TimelineWindow")
        _canonical_text("execution_account_id", self.execution_account_id)
        if (
            type(self.reporting_currency) is not domain.CurrencyId
            or self.reporting_currency != _USDT
        ):
            raise ValueError("reporting_currency must be exact USDT CurrencyId")
        if type(self.master_random_seed) is not int or self.master_random_seed != 0:
            raise ValueError("master_random_seed must be exact 0")
        if type(self.market_bundle_ref) is not MarketBundleRef:
            raise TypeError("market_bundle_ref must be exact MarketBundleRef")
        if (
            type(self.strategy_definition_ref) is not domain.ArtifactRef
            or self.strategy_definition_ref != _EXPECTED_STRATEGY_REF
        ):
            raise ValueError(
                "strategy_definition_ref must be the frozen V1 authority ref"
            )
        if (
            type(self.strategy_parameter_set_ref) is not domain.ArtifactRef
            or self.strategy_parameter_set_ref not in _EXPECTED_PARAMETER_REFS
        ):
            raise ValueError(
                "strategy_parameter_set_ref must be one frozen V1 parameter ref"
            )
        if (
            type(self.result_grade_requested) is not RequestedResultGrade
            or self.result_grade_requested is not RequestedResultGrade.DEVELOPMENT
        ):
            raise ValueError("result_grade_requested must be DEVELOPMENT")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_bar_request_intent",
            "schema_version": _SCHEMA_VERSION,
            "experiment_id": self.experiment_id,
            "timeline_window": self.timeline_window,
            "execution_account_id": self.execution_account_id,
            "reporting_currency": self.reporting_currency,
            "master_random_seed": self.master_random_seed,
            "market_bundle_ref": self.market_bundle_ref,
            "strategy_definition_ref": self.strategy_definition_ref,
            "strategy_parameter_set_ref": self.strategy_parameter_set_ref,
            "result_grade_requested": self.result_grade_requested.value,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiProviderInputs:
    build_artifact_manifest: BuildArtifactManifest
    initial_equity: domain.Money

    def __post_init__(self) -> None:
        if type(self.build_artifact_manifest) is not BuildArtifactManifest:
            raise TypeError(
                "build_artifact_manifest must be exact BuildArtifactManifest"
            )
        if (
            type(self.initial_equity) is not domain.Money
            or self.initial_equity != _REQUIRED_EQUITY
        ):
            raise ValueError("initial_equity must be exact 10000 USDT at scale 8")

    @property
    def sleeve_allocation_fraction(self) -> str:
        return _REQUIRED_ALLOCATION

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_provider_inputs",
            "schema_version": _SCHEMA_VERSION,
            "build_artifact_manifest": self.build_artifact_manifest,
            "initial_equity": self.initial_equity,
            "sleeve_allocation_fraction": _REQUIRED_ALLOCATION,
        }


class BinanceUsdmTradifiPreparationFailureCode(str, Enum):
    INVALID_INTENT = "invalid_intent"
    INVALID_PROVIDER_INPUTS = "invalid_provider_inputs"
    MARKET_BUNDLE_MISMATCH = "market_bundle_mismatch"
    PREPARATION_AUTHORITY_INVALID = "preparation_authority_invalid"
    PARAMETER_TARGET_BINDING_INVALID = "parameter_target_binding_invalid"
    TARGET_STREAM_INVALID = "target_stream_invalid"
    ARTIFACT_READ_INVALID = "artifact_read_invalid"
    ARTIFACT_BINDING_INVALID = "artifact_binding_invalid"
    PROFILE_WIRE_INVALID = "profile_wire_invalid"
    PROFILE_BINDING_INVALID = "profile_binding_invalid"
    PROFILE_COMPOSITION_FAILED = "profile_composition_failed"
    BUILD_MANIFEST_CONFLICT = "build_manifest_conflict"
    RESULT_INVALID = "result_invalid"


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiPreparationFailure:
    code: BinanceUsdmTradifiPreparationFailureCode
    subject: str

    def __post_init__(self) -> None:
        if type(self.code) is not BinanceUsdmTradifiPreparationFailureCode:
            raise TypeError("code must be exact preparation failure code")
        _canonical_text("subject", self.subject)

    @property
    def failure_hash(self) -> str:
        return domain.canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_preparation_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
        }


@dataclass(frozen=True, slots=True)
class _VerifiedArtifact:
    envelope: domain.ArtifactEnvelope
    ref: domain.ArtifactRef
    source_bytes: bytes
    source_hash: str

    def __post_init__(self) -> None:
        if type(self.envelope) is not domain.ArtifactEnvelope:
            raise TypeError("envelope must be exact ArtifactEnvelope")
        if type(
            self.ref
        ) is not domain.ArtifactRef or self.ref != domain.ArtifactRef.from_envelope(
            self.envelope
        ):
            raise ValueError("artifact ref must bind envelope")
        if type(
            self.source_bytes
        ) is not bytes or self.source_bytes != domain.canonical_bytes(self.envelope):
            raise ValueError("artifact source bytes must be the canonical envelope")
        _canonical_hash("source_hash", self.source_hash)
        if (
            self.source_hash
            != "sha256:" + hashlib.sha256(self.source_bytes).hexdigest()
        ):
            raise ValueError("artifact source hash must bind canonical envelope bytes")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_verified_artifact",
            "envelope": self.envelope,
            "ref": self.ref,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class _VerifiedParameterTargetBinding:
    parameter_id: str
    parameter_ref: domain.ArtifactRef
    target_stream_key: str
    target_stream_digest: str
    stream_manifest: MarketStreamManifest
    target_stream: PrecomputedTargetStream
    bundle_schema_version: int = 1

    def __post_init__(self) -> None:
        if self.parameter_id not in _PARAMETER_IDS:
            raise ValueError("parameter_id must be a frozen V1 parameter id")
        index = _PARAMETER_IDS.index(self.parameter_id)
        if self.parameter_ref != _EXPECTED_PARAMETER_REFS[index]:
            raise ValueError("parameter ref does not bind frozen parameter id")
        if self.bundle_schema_version not in (1, _BUNDLE_SCHEMA_VERSION_V2):
            raise ValueError("bundle_schema_version must be exact V1 or V2")
        if self.target_stream_key != (
            f"{_TARGET_PREFIX}{self.parameter_id}.v{self.bundle_schema_version}"
        ):
            raise ValueError("target stream key does not bind parameter id")
        _canonical_hash("target_stream_digest", self.target_stream_digest)
        if (
            type(self.stream_manifest) is not MarketStreamManifest
            or self.stream_manifest.stream_key != self.target_stream_key
            or self.stream_manifest.event_type != TARGET_STREAM_EVENT_TYPE
            or self.stream_manifest.capability != TARGET_STREAM_CAPABILITY
            or type(self.target_stream) is not PrecomputedTargetStream
            or self.target_stream.stream_key != self.target_stream_key
            or self.stream_manifest.event_count != len(self.target_stream.events)
            or self.stream_manifest.content_hash
            != domain.canonical_sha256(self.target_stream.events)
            or self.target_stream.target_stream_digest != self.target_stream_digest
        ):
            raise ValueError("target stream evidence mismatch")

    def to_canonical_dict(self) -> dict[str, object]:
        value = {
            "type": "binance_usdm_tradifi_verified_parameter_target_binding",
            "schema_version": _SCHEMA_VERSION,
            "parameter_id": self.parameter_id,
            "parameter_ref": self.parameter_ref,
            "target_stream_key": self.target_stream_key,
            "target_stream_digest": self.target_stream_digest,
            "stream_manifest": self.stream_manifest,
            "target_stream": self.target_stream,
        }
        if self.bundle_schema_version == _BUNDLE_SCHEMA_VERSION_V2:
            value["bundle_schema_version"] = self.bundle_schema_version
        return value


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiPreparationResult:
    intent: BinanceUsdmTradifiBarRequestIntent
    provider_inputs: BinanceUsdmTradifiProviderInputs
    preparation_authority_event: MarketEvent
    preparation_authority_hash: str
    verified_target_bindings: tuple[_VerifiedParameterTargetBinding, ...]
    target_stream: PrecomputedTargetStream
    target_stream_key: str
    target_stream_digest: str
    profile_composition_request: BinanceUsdmTradifiProfileCompositionRequest
    resolved_profile: BinanceUsdmTradifiResolvedProfile
    profile_registry: BacktestProfileRegistry
    financial_dispatcher_spec: FinancialDispatcherSpec
    verified_artifacts: tuple[_VerifiedArtifact, ...]
    build_artifact_manifest: BuildArtifactManifest
    market_bundle_manifest: MarketBundleManifest
    market_bundle_ref: MarketBundleRef
    market_reader: MarketBundleReader
    bundle_schema_version: int = 1
    source_profile_authority_ref: domain.ArtifactRef | None = None
    source_profile_authority_hash: str | None = None
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _validate_preparation_result(self)
        object.__setattr__(self, "result_digest", domain.canonical_sha256(self._body()))

    @property
    def verified_artifact_envelopes(self) -> tuple[domain.ArtifactEnvelope, ...]:
        return tuple(value.envelope for value in self.verified_artifacts)

    @property
    def verified_artifact_refs(self) -> tuple[domain.ArtifactRef, ...]:
        return tuple(value.ref for value in self.verified_artifacts)

    @property
    def verified_artifact_source_hashes(self) -> tuple[str, ...]:
        return tuple(value.source_hash for value in self.verified_artifacts)

    @property
    def verified_artifact_source_bytes(self) -> tuple[bytes, ...]:
        return tuple(value.source_bytes for value in self.verified_artifacts)

    @property
    def strategy_definition_envelope(self) -> domain.ArtifactEnvelope:
        return self.verified_artifacts[0].envelope

    @property
    def strategy_definition_ref(self) -> domain.ArtifactRef:
        return self.verified_artifacts[0].ref

    @property
    def strategy_definition_source_hash(self) -> str:
        return self.verified_artifacts[0].source_hash

    @property
    def strategy_parameter_set_envelope(self) -> domain.ArtifactEnvelope:
        return self.verified_artifacts[self._selected_parameter_index + 1].envelope

    @property
    def strategy_parameter_set_ref(self) -> domain.ArtifactRef:
        return self.verified_artifacts[self._selected_parameter_index + 1].ref

    @property
    def strategy_parameter_set_source_hash(self) -> str:
        return self.verified_artifacts[self._selected_parameter_index + 1].source_hash

    @property
    def _selected_parameter_index(self) -> int:
        return _EXPECTED_PARAMETER_REFS.index(self.intent.strategy_parameter_set_ref)

    @property
    def xkrx_calendar_ref(self) -> domain.ArtifactRef:
        return self.verified_artifacts[9].ref

    @property
    def arcx_calendar_ref(self) -> domain.ArtifactRef:
        return self.verified_artifacts[10].ref

    @property
    def post_adjustment_unit_regime_ref(self) -> domain.ArtifactRef:
        return self.verified_artifacts[11].ref

    @property
    def source_profile_authority_envelope(self) -> domain.ArtifactEnvelope | None:
        if self.bundle_schema_version == 1:
            return None
        return self.verified_artifacts[12].envelope

    def _body(self) -> dict[str, object]:
        value = {
            "type": "binance_usdm_tradifi_preparation_result",
            "schema_version": _SCHEMA_VERSION,
            "intent": self.intent,
            "provider_inputs": self.provider_inputs,
            "preparation_authority_event": self.preparation_authority_event,
            "preparation_authority_hash": self.preparation_authority_hash,
            "verified_target_bindings": self.verified_target_bindings,
            "target_stream": self.target_stream,
            "target_stream_key": self.target_stream_key,
            "target_stream_digest": self.target_stream_digest,
            "profile_composition_request": self.profile_composition_request,
            "resolved_profile": self.resolved_profile,
            "profile_registry": self.profile_registry,
            "financial_dispatcher_spec": self.financial_dispatcher_spec,
            "verified_artifacts": self.verified_artifacts,
            "build_artifact_manifest": self.build_artifact_manifest,
            "market_bundle_manifest": self.market_bundle_manifest,
            "market_bundle_ref": self.market_bundle_ref,
        }
        if self.bundle_schema_version == _BUNDLE_SCHEMA_VERSION_V2:
            value.update(
                {
                    "bundle_schema_version": self.bundle_schema_version,
                    "source_profile_authority_ref": self.source_profile_authority_ref,
                    "source_profile_authority_hash": self.source_profile_authority_hash,
                }
            )
        return value

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "result_digest": self.result_digest}


def _trusted_result(
    value: object,
) -> BinanceUsdmTradifiPreparationResult | None:
    if type(value) is not BinanceUsdmTradifiPreparationResult:
        return None
    try:
        rebuilt = BinanceUsdmTradifiPreparationResult(
            intent=value.intent,
            provider_inputs=value.provider_inputs,
            preparation_authority_event=value.preparation_authority_event,
            preparation_authority_hash=value.preparation_authority_hash,
            verified_target_bindings=value.verified_target_bindings,
            target_stream=value.target_stream,
            target_stream_key=value.target_stream_key,
            target_stream_digest=value.target_stream_digest,
            profile_composition_request=value.profile_composition_request,
            resolved_profile=value.resolved_profile,
            profile_registry=value.profile_registry,
            financial_dispatcher_spec=value.financial_dispatcher_spec,
            verified_artifacts=value.verified_artifacts,
            build_artifact_manifest=value.build_artifact_manifest,
            market_bundle_manifest=value.market_bundle_manifest,
            market_bundle_ref=value.market_bundle_ref,
            market_reader=value.market_reader,
            bundle_schema_version=value.bundle_schema_version,
            source_profile_authority_ref=value.source_profile_authority_ref,
            source_profile_authority_hash=value.source_profile_authority_hash,
        )
        if not _same(rebuilt, value) or value.result_digest != domain.canonical_sha256(
            value._body()
        ):
            return None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return rebuilt


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiPreparationOutcome:
    result: BinanceUsdmTradifiPreparationResult | None = None
    failure: BinanceUsdmTradifiPreparationFailure | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one branch")
        if self.result is not None and _trusted_result(self.result) is None:
            raise ValueError("result must be an exact trusted preparation result")
        if (
            self.failure is not None
            and type(self.failure) is not BinanceUsdmTradifiPreparationFailure
        ):
            raise TypeError("failure must be exact preparation failure")

    @property
    def outcome_hash(self) -> str:
        return domain.canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_preparation_outcome",
            "schema_version": _SCHEMA_VERSION,
            "result": self.result,
            "failure": self.failure,
        }


class _PreparationError(ValueError):
    def __init__(
        self, code: BinanceUsdmTradifiPreparationFailureCode, subject: str
    ) -> None:
        self.code = code
        self.subject = subject
        super().__init__(subject)


def _fail(
    code: BinanceUsdmTradifiPreparationFailureCode, subject: str
) -> BinanceUsdmTradifiPreparationOutcome:
    return BinanceUsdmTradifiPreparationOutcome(
        failure=BinanceUsdmTradifiPreparationFailure(code, subject)
    )


def _manifest_stream(
    manifest: MarketBundleManifest, stream_key: str
) -> MarketStreamManifest:
    matches = tuple(
        value for value in manifest.streams if value.stream_key == stream_key
    )
    if len(matches) != 1:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH,
            "required_stream",
        )
    return matches[0]


def _read_stream(
    reader: MarketBundleReader, manifest: MarketBundleManifest, stream_key: str
) -> tuple[MarketEvent, ...]:
    stream_manifest = _manifest_stream(manifest, stream_key)
    try:
        cursor = reader.open_cursor(stream_key, batch_size=16)
    except Exception as error:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH,
            "open_cursor",
        ) from error
    if type(cursor) is not EventCursor or cursor.stream_manifest != stream_manifest:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH,
            "cursor_evidence",
        )
    events: list[MarketEvent] = []
    while not cursor.exhausted:
        previous = cursor.position
        try:
            batch, cursor = reader.read_batch(cursor)
        except Exception as error:
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH,
                "read_batch",
            ) from error
        if (
            type(batch) is not tuple
            or type(cursor) is not EventCursor
            or cursor.stream_manifest != stream_manifest
            or cursor.position <= previous
            or cursor.position > stream_manifest.event_count
            or any(type(event) is not MarketEvent for event in batch)
        ):
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH,
                "cursor_progress",
            )
        events.extend(batch)
    result = tuple(events)
    if (
        len(result) != stream_manifest.event_count
        or domain.canonical_sha256(result) != stream_manifest.content_hash
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH,
            "stream_manifest",
        )
    return result


def _artifact_ref(
    value: object,
    subject: str,
    code: BinanceUsdmTradifiPreparationFailureCode = (
        BinanceUsdmTradifiPreparationFailureCode.PARAMETER_TARGET_BINDING_INVALID
    ),
) -> domain.ArtifactRef:
    payload = _mapping(value, subject)
    if (
        set(payload) != {"type", "artifact_type", "schema_version", "content_hash"}
        or payload.get("type") != "artifact_ref"
    ):
        raise _PreparationError(code, subject)
    try:
        ref = domain.ArtifactRef(
            _canonical_text(f"{subject}.artifact_type", payload.get("artifact_type")),
            payload.get("schema_version"),  # type: ignore[arg-type]
            _canonical_hash(f"{subject}.content_hash", payload.get("content_hash")),
        )
    except (TypeError, ValueError) as error:
        raise _PreparationError(code, subject) from error
    if not _same(ref, payload):
        raise _PreparationError(code, subject)
    return ref


def _authority(
    reader: MarketBundleReader,
    manifest: MarketBundleManifest,
    intent: BinanceUsdmTradifiBarRequestIntent,
    bundle_schema_version: int = 1,
) -> tuple[MarketEvent, Mapping[str, object]]:
    stream_key = (
        _PREPARATION_STREAM
        if bundle_schema_version == 1
        else _PREPARATION_STREAM_V2
    )
    event_type = (
        _PREPARATION_EVENT_TYPE
        if bundle_schema_version == 1
        else _PREPARATION_EVENT_TYPE_V2
    )
    payload_keys = (
        _AUTHORITY_PAYLOAD_KEYS
        if bundle_schema_version == 1
        else _AUTHORITY_PAYLOAD_KEYS_V2
    )
    events = _read_stream(reader, manifest, stream_key)
    if len(events) != 1:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
            "event_count",
        )
    event = events[0]
    window = intent.timeline_window
    if (
        event.stream_key != stream_key
        or event.event_type != event_type
        or event.capability != _PREPARATION_CAPABILITY
        or event.instrument_id is not None
        or event.event_time != window.data_start
        or event.available_time != window.data_start
        or event.phase != domain.TimelinePhase(0, "market_data")
        or event.source_sequence != domain.SourceSequence(0)
        or set(event.payload) != payload_keys
        or event.payload.get("schema_version") != bundle_schema_version
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
            "event_contract",
        )
    return event, event.payload


def _target_bindings(
    payload: Mapping[str, object],
    intent: BinanceUsdmTradifiBarRequestIntent,
    bundle_schema_version: int = 1,
) -> tuple[tuple[str, domain.ArtifactRef, str, str], ...]:
    strategy_ref = _artifact_ref(
        payload.get("strategy_definition_ref"), "strategy_definition_ref"
    )
    if (
        strategy_ref != _EXPECTED_STRATEGY_REF
        or strategy_ref != intent.strategy_definition_ref
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PARAMETER_TARGET_BINDING_INVALID,
            "strategy_definition_ref",
        )
    rows = _sequence(
        payload.get("parameter_target_bindings"), "parameter_target_bindings"
    )
    if len(rows) != 8:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PARAMETER_TARGET_BINDING_INVALID,
            "parameter_count",
        )
    normalized: list[tuple[str, domain.ArtifactRef, str, str]] = []
    for index, raw in enumerate(rows):
        row = _mapping(raw, "parameter_target_binding")
        if set(row) != _PARAMETER_BINDING_KEYS:
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.PARAMETER_TARGET_BINDING_INVALID,
                "parameter_binding_keys",
            )
        parameter_id = _canonical_text("parameter_id", row.get("parameter_id"))
        parameter_ref = _artifact_ref(row.get("parameter_ref"), "parameter_ref")
        stream_key = _canonical_text("target_stream_key", row.get("target_stream_key"))
        digest = _canonical_hash(
            "target_stream_digest", row.get("target_stream_digest")
        )
        if (
            parameter_id != _PARAMETER_IDS[index]
            or parameter_ref != _EXPECTED_PARAMETER_REFS[index]
            or stream_key
            != f"{_TARGET_PREFIX}{parameter_id}.v{bundle_schema_version}"
        ):
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.PARAMETER_TARGET_BINDING_INVALID,
                "parameter_binding_identity",
            )
        normalized.append((parameter_id, parameter_ref, stream_key, digest))
    values = tuple(normalized)
    if (
        len({value[1] for value in values}) != 8
        or len({value[2] for value in values}) != 8
        or len({value[3] for value in values}) != 8
        or intent.strategy_parameter_set_ref not in tuple(value[1] for value in values)
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PARAMETER_TARGET_BINDING_INVALID,
            "parameter_binding_cover",
        )
    return values


def _validate_target_event(
    event: MarketEvent,
    intent: BinanceUsdmTradifiBarRequestIntent,
    refs: tuple[domain.ArtifactRef, ...],
    source_fragment_digest: str,
) -> None:
    if (
        event.event_type != TARGET_STREAM_EVENT_TYPE
        or event.capability != TARGET_STREAM_CAPABILITY
        or event.instrument_id is not None
        or event.available_time != event.event_time
        or event.phase != domain.TimelinePhase(30, "strategy_decision")
        or not (
            intent.timeline_window.data_start
            <= event.event_time
            < intent.timeline_window.end_exclusive
        )
        or set(event.payload) != {"schema_version", "candidate"}
        or event.payload.get("schema_version") != 1
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.TARGET_STREAM_INVALID,
            "event_contract",
        )
    candidate = _mapping(event.payload.get("candidate"), "target_candidate")
    expected_keys = {
        "schema_version",
        "strategy_id",
        "sleeve_id",
        "decision_time",
        "observed_through",
        "effective_time",
        "expires_at",
        "targets",
        "confidence",
        "reason",
        "evidence",
    }
    decision_ns = event.event_time.epoch_nanoseconds
    if (
        set(candidate) != expected_keys
        or candidate.get("schema_version") != 1
        or candidate.get("strategy_id") != _STRATEGY_ID
        or candidate.get("sleeve_id") != _SLEEVE_ID
        or candidate.get("decision_time") != decision_ns
        or candidate.get("observed_through") != decision_ns
        or candidate.get("effective_time") != decision_ns
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.TARGET_STREAM_INVALID,
            "candidate_contract",
        )
    evidence = _mapping(candidate.get("evidence"), "target_evidence")
    evidence_refs = (
        _artifact_ref(evidence.get("strategy_definition_ref"), "target_strategy_ref"),
        _artifact_ref(
            evidence.get("strategy_parameter_set_ref"), "target_parameter_ref"
        ),
        _artifact_ref(evidence.get("xkrx_calendar_ref"), "target_xkrx_ref"),
        _artifact_ref(evidence.get("arcx_calendar_ref"), "target_arcx_ref"),
        _artifact_ref(
            evidence.get("post_adjustment_unit_regime_ref"), "target_unit_ref"
        ),
    )
    if (
        evidence_refs != refs
        or evidence.get("source_fragment_digest") != source_fragment_digest
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.TARGET_STREAM_INVALID,
            "candidate_artifact_refs",
        )


def _target_stream(
    reader: MarketBundleReader,
    manifest: MarketBundleManifest,
    intent: BinanceUsdmTradifiBarRequestIntent,
    stream_key: str,
    digest: str,
    refs: tuple[domain.ArtifactRef, ...],
    source_fragment_digest: str,
) -> PrecomputedTargetStream:
    stream_manifest = _manifest_stream(manifest, stream_key)
    if (
        stream_manifest.event_type != TARGET_STREAM_EVENT_TYPE
        or stream_manifest.capability != TARGET_STREAM_CAPABILITY
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.TARGET_STREAM_INVALID,
            "manifest_contract",
        )
    events = _read_stream(reader, manifest, stream_key)
    for event in events:
        _validate_target_event(event, intent, refs, source_fragment_digest)
    stream = PrecomputedTargetStream(stream_key, events)
    if stream.target_stream_digest != digest:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.TARGET_STREAM_INVALID,
            "target_stream_digest",
        )
    return stream


def _verify_artifact(
    reader: ArtifactEnvelopeReader, ref: domain.ArtifactRef
) -> _VerifiedArtifact:
    try:
        value = reader.read(ref=ref)
    except Exception as error:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_READ_INVALID,
            ref.artifact_type,
        ) from error
    if type(value) is not domain.ArtifactReadResult:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_READ_INVALID,
            ref.artifact_type,
        )
    envelope = value.envelope
    source = value.source_bytes
    expected_source_hash = (
        "sha256:" + hashlib.sha256(source).hexdigest()
        if type(source) is bytes
        else None
    )
    if (
        type(envelope) is not domain.ArtifactEnvelope
        or type(source) is not bytes
        or source != domain.canonical_bytes(envelope)
        or value.source_hash != expected_source_hash
        or domain.ArtifactRef.from_envelope(envelope) != ref
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_READ_INVALID,
            ref.artifact_type,
        )
    return _VerifiedArtifact(envelope, ref, source, value.source_hash)


def _payload_identity(
    artifacts: tuple[_VerifiedArtifact, ...],
) -> None:
    expected_refs = (
        _EXPECTED_STRATEGY_REF,
        *_EXPECTED_PARAMETER_REFS,
        *_EXPECTED_AUTHORITY_REFS,
    )
    if (
        len(artifacts) != len(expected_refs)
        or tuple(value.ref for value in artifacts) != expected_refs
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            "artifact_ref_cover",
        )
    strategy = artifacts[0]
    strategy_payload = _mapping(strategy.envelope.payload, "strategy_payload")
    if (
        strategy.envelope.artifact_type != "strategy_definition"
        or strategy.envelope.schema_version != 1
        or set(strategy_payload) != _STRATEGY_PAYLOAD_KEYS
        or strategy_payload.get("strategy_id") != _STRATEGY_ID
        or strategy_payload.get("sleeve_id") != _SLEEVE_ID
        or not _same(strategy_payload.get("instrument_id"), _INSTRUMENT)
        or strategy_payload.get("required_synthetic_equity_usdt") != "10000"
        or strategy_payload.get("required_sleeve_allocation_fraction")
        != _REQUIRED_ALLOCATION
        or strategy_payload.get("position_notional_usdt") != _REQUIRED_NOTIONAL
        or not _exact_false(strategy_payload.get("development_authorized"))
        or not _exact_false(strategy_payload.get("deployment_authorized"))
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            "strategy_definition",
        )
    for index, parameter in enumerate(artifacts[1:9]):
        parameter_id = _PARAMETER_IDS[index]
        parameter_payload = _mapping(parameter.envelope.payload, "parameter_payload")
        if (
            parameter.envelope.artifact_type != "strategy_parameter_set"
            or parameter.envelope.schema_version != 1
            or set(parameter_payload) != _PARAMETER_PAYLOAD_KEYS
            or parameter_payload.get("strategy_id") != _STRATEGY_ID
            or parameter_payload.get("parameter_set_id") != parameter_id
            or not _same(
                parameter_payload.get("strategy_definition_ref"),
                _EXPECTED_STRATEGY_REF,
            )
            or parameter_payload.get("position_notional_usdt") != _REQUIRED_NOTIONAL
            or not _exact_false(parameter_payload.get("development_authorized"))
            or not _exact_false(parameter_payload.get("deployment_authorized"))
        ):
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
                f"strategy_parameter_set:{parameter_id}",
            )
    xkrx, arcx, unit = artifacts[9:12]
    expected = (
        (
            xkrx,
            "xkrx_regular_session_calendar",
            "xkrx_regular_session_calendar_v1",
            "XKRX",
        ),
        (
            arcx,
            "arcx_koru_core_session_calendar",
            "arcx_koru_core_session_calendar_v1",
            "ARCX",
        ),
    )
    for artifact, artifact_type, payload_type, venue in expected:
        payload = _mapping(artifact.envelope.payload, artifact_type)
        if (
            artifact.envelope.artifact_type != artifact_type
            or artifact.envelope.schema_version != 1
            or set(payload) != _CALENDAR_PAYLOAD_KEYS[artifact_type]
            or payload.get("type") != payload_type
            or payload.get("schema_version") != 1
            or payload.get("venue") != venue
            or not _exact_false(payload.get("decision_grade_eligible"))
            or not _exact_false(payload.get("deployment_authorized"))
        ):
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
                artifact_type,
            )
    unit_payload = _mapping(unit.envelope.payload, "unit_regime")
    if (
        unit.envelope.artifact_type
        != "binance_usdm_tradifi_post_adjustment_unit_regime"
        or unit.envelope.schema_version != 1
        or set(unit_payload) != _UNIT_PAYLOAD_KEYS
        or unit_payload.get("type")
        != "binance_usdm_tradifi_post_adjustment_unit_regime_v1"
        or unit_payload.get("schema_version") != 1
        or unit_payload.get("venue") != "BINANCE_USDM"
        or unit_payload.get("instrument") != "KORUUSDT"
        or not _exact_false(unit_payload.get("decision_grade_eligible"))
        or not _exact_false(unit_payload.get("deployment_authorized"))
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            "post_adjustment_unit_regime",
        )


def _profile(
    payload: Mapping[str, object],
    intent: BinanceUsdmTradifiBarRequestIntent,
    refs: tuple[domain.ArtifactRef, ...],
) -> BinanceUsdmTradifiResolvedProfile:
    wire = _mapping(payload.get("profile_composition_request_wire"), "profile_wire")
    expected_hash = _canonical_hash(
        "profile_composition_request_hash",
        payload.get("profile_composition_request_hash"),
    )
    if domain.canonical_sha256(wire) != expected_hash:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PROFILE_WIRE_INVALID,
            "profile_hash",
        )
    try:
        json_wire = json.loads(domain.canonical_bytes(wire))
        request = decode_binance_usdm_tradifi_profile_composition_request_v1(
            json_wire, expected_hash
        )
    except Exception as error:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PROFILE_WIRE_INVALID,
            "profile_codec",
        ) from error
    account = request.account_profile
    slippage = request.slippage_model
    if (
        request.timeline_window != intent.timeline_window
        or account is None
        or account.account_id != intent.execution_account_id
        or request.calendar_refs != refs[2:4]
        or request.post_adjustment_unit_regime_ref != refs[4]
        or type(slippage) is not DeterministicBpsSlippageModel
        or slippage.applicability_envelope.valid_from
        != intent.timeline_window.data_start
        or slippage.applicability_envelope.valid_to_exclusive
        != intent.timeline_window.end_exclusive
        or request.required_market_state_keys != ("normal",)
        or slippage.applicability_envelope.allowed_market_state_keys
        != request.required_market_state_keys
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PROFILE_BINDING_INVALID,
            "profile_request",
        )
    outcome = BinanceUsdmTradifiProfileComposer().compose(request)
    resolved = outcome.result
    if (
        outcome.failure is not None
        or type(resolved) is not BinanceUsdmTradifiResolvedProfile
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PROFILE_COMPOSITION_FAILED,
            "profile_composition",
        )
    exact_registry = BacktestProfileRegistry(
        (resolved.market_registration,),
        (resolved.simulation_registration,),
        (resolved.execution_account_registration,),
    )
    if resolved.profile_registry != exact_registry:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PROFILE_BINDING_INVALID,
            "profile_registry",
        )
    return resolved


def _validate_source_snapshot_bindings(payload: Mapping[str, object]) -> None:
    rows = tuple(
        _mapping(value, "source_snapshot_binding")
        for value in _sequence(
            payload.get("source_snapshot_bindings"), "source_snapshot_bindings"
        )
    )
    if not rows or any(set(row) != _SOURCE_SNAPSHOT_KEYS for row in rows):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
            "source_snapshot_binding_schema",
        )
    normalized = []
    for row in rows:
        kind = _canonical_text("source_kind", row.get("source_kind"))
        normalized.append(
            (
                kind,
                _canonical_hash("source_snapshot_id", row.get("source_snapshot_id")),
                _canonical_hash(
                    "source_snapshot_hash", row.get("source_snapshot_hash")
                ),
                _canonical_hash(
                    "source_normalization_hash",
                    row.get("source_normalization_hash"),
                ),
            )
        )
    values = tuple(normalized)
    if (
        values != _EXPECTED_SOURCE_SNAPSHOT_BINDINGS
        or tuple(sorted({value[0] for value in values}))
        != (
            "aggregate_trades",
            "calendar_unit",
            "funding_history",
            "index_price",
            "mark_price",
        )
        or sum(value[0] == "calendar_unit" for value in values) != 1
        or sum(value[0] == "funding_history" for value in values) != 1
        or sum(value[0] == "index_price" for value in values)
        != sum(value[0] == "mark_price" for value in values)
        or len(set(values)) != len(values)
        or values
        != tuple(sorted(values, key=lambda value: (value[0], value[1], value[3])))
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
            "source_snapshot_binding_cover",
        )


def _validate_authority_support(
    payload: Mapping[str, object],
    provider: BinanceUsdmTradifiProviderInputs,
) -> tuple[domain.ArtifactRef, domain.ArtifactRef, domain.ArtifactRef]:
    if (
        not _same(payload.get("required_initial_equity"), provider.initial_equity)
        or payload.get("required_sleeve_allocation_fraction")
        != provider.sleeve_allocation_fraction
        or payload.get("required_position_notional_usdt") != _REQUIRED_NOTIONAL
        or not _same(payload.get("source_limitations"), _SOURCE_LIMITATIONS)
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
            "required_financial_authority",
        )
    refs = (
        _artifact_ref(payload.get("xkrx_calendar_ref"), "xkrx_calendar_ref"),
        _artifact_ref(payload.get("arcx_calendar_ref"), "arcx_calendar_ref"),
        _artifact_ref(
            payload.get("post_adjustment_unit_regime_ref"),
            "post_adjustment_unit_regime_ref",
        ),
    )
    if refs != _EXPECTED_AUTHORITY_REFS:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            "authority_artifact_refs",
        )
    _validate_source_snapshot_bindings(payload)
    for name in ("source_fragment_digest", "target_result_digest"):
        _canonical_hash(name, payload.get(name))
    return refs


def _artifact_envelope(
    value: object, subject: str
) -> domain.ArtifactEnvelope:
    payload = _mapping(value, subject)
    if set(payload) != {
        "artifact_type",
        "schema_version",
        "payload",
        "content_hash",
    }:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            subject,
        )
    try:
        envelope = domain.ArtifactEnvelope.create(
            _canonical_text(
                f"{subject}.artifact_type", payload.get("artifact_type")
            ),
            payload.get("schema_version"),  # type: ignore[arg-type]
            payload.get("payload"),
        )
    except (TypeError, ValueError) as error:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            subject,
        ) from error
    if not _same(envelope, payload):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            subject,
        )
    return envelope


def _validate_source_snapshot_bindings_v2(payload: Mapping[str, object]) -> None:
    rows = tuple(
        _mapping(value, "source_snapshot_binding")
        for value in _sequence(
            payload.get("source_snapshot_bindings"), "source_snapshot_bindings"
        )
    )
    normalized = []
    for row in rows:
        if set(row) != _SOURCE_SNAPSHOT_KEYS_V2:
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
                "source_snapshot_binding_schema",
            )
        normalized.append(
            (
                _canonical_text("source_kind", row.get("source_kind")),
                _canonical_hash("source_snapshot_id", row.get("source_snapshot_id")),
                _canonical_hash(
                    "source_snapshot_hash", row.get("source_snapshot_hash")
                ),
                _canonical_hash(
                    "source_evidence_hash", row.get("source_evidence_hash")
                ),
            )
        )
    values = tuple(normalized)
    if (
        not values
        or len(set(values)) != len(values)
        or values
        != tuple(sorted(values, key=lambda value: (value[0], value[1], value[3])))
        or tuple(sorted({value[0] for value in values}))
        != (
            "aggregate_trades",
            "calendar_unit",
            "funding_history",
            "index_price",
            "mark_price",
        )
        or sum(value[0] == "calendar_unit" for value in values) != 1
        or sum(value[0] == "funding_history" for value in values) != 1
        or sum(value[0] == "index_price" for value in values)
        != sum(value[0] == "mark_price" for value in values)
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
            "source_snapshot_binding_cover",
        )


def _validate_authority_support_v2(
    payload: Mapping[str, object],
    provider: BinanceUsdmTradifiProviderInputs,
) -> tuple[
    tuple[domain.ArtifactRef, domain.ArtifactRef, domain.ArtifactRef],
    domain.ArtifactRef,
]:
    if (
        not _same(payload.get("required_initial_equity"), provider.initial_equity)
        or payload.get("required_sleeve_allocation_fraction")
        != provider.sleeve_allocation_fraction
        or payload.get("required_position_notional_usdt") != _REQUIRED_NOTIONAL
        or not _same(payload.get("source_limitations"), _SOURCE_LIMITATIONS_V2)
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
            "required_financial_authority",
        )
    refs = (
        _artifact_ref(payload.get("xkrx_calendar_ref"), "xkrx_calendar_ref"),
        _artifact_ref(payload.get("arcx_calendar_ref"), "arcx_calendar_ref"),
        _artifact_ref(
            payload.get("post_adjustment_unit_regime_ref"),
            "post_adjustment_unit_regime_ref",
        ),
    )
    if refs != _EXPECTED_AUTHORITY_REFS:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            "authority_artifact_refs",
        )
    source_ref = _artifact_ref(
        payload.get("source_profile_authority_ref"),
        "source_profile_authority_ref",
        BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
    )
    if (
        source_ref.artifact_type != _SOURCE_PROFILE_AUTHORITY_TYPE
        or source_ref.schema_version != _SOURCE_PROFILE_AUTHORITY_SCHEMA_VERSION
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            "source_profile_authority_ref",
        )
    _validate_source_snapshot_bindings_v2(payload)
    for name in (
        "source_fragment_digest",
        "target_result_digest",
        "aggregate_trade_boundary_index_request_hash",
        "aggregate_trade_boundary_index_result_digest",
        "aggregate_trade_streamed_reconstruction_digest",
        "source_profile_authority_hash",
        "profile_composition_request_hash",
    ):
        _canonical_hash(name, payload.get(name))
    for name in (
        "aggregate_trade_intra_day_raw_id_gap_stream",
        "aggregate_trade_cross_date_raw_id_gap_stream",
        "aggregate_trade_coverage_gaps",
        "missing_boundaries",
    ):
        if name.endswith("gaps") or name == "missing_boundaries":
            _sequence(payload.get(name), name)
        else:
            _mapping(payload.get(name), name)
    return refs, source_ref


def _source_profile_authority_v2(
    preparation_payload: Mapping[str, object],
    artifact: _VerifiedArtifact,
) -> Mapping[str, object]:
    embedded = _artifact_envelope(
        preparation_payload.get("source_profile_authority_envelope"),
        "source_profile_authority_envelope",
    )
    if (
        artifact.ref.artifact_type != _SOURCE_PROFILE_AUTHORITY_TYPE
        or artifact.ref.schema_version != _SOURCE_PROFILE_AUTHORITY_SCHEMA_VERSION
        or artifact.ref
        != _artifact_ref(
            preparation_payload.get("source_profile_authority_ref"),
            "source_profile_authority_ref",
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
        )
        or not _same(artifact.envelope, embedded)
        or preparation_payload.get("source_profile_authority_hash")
        != artifact.envelope.content_hash
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            "source_profile_authority",
        )
    payload = _mapping(artifact.envelope.payload, "source_profile_authority_payload")
    if (
        set(payload) != _SOURCE_PROFILE_AUTHORITY_PAYLOAD_KEYS
        or payload.get("type") != "binance_usdm_koru_source_profile_authority_v2"
        or payload.get("schema_version") != _SOURCE_PROFILE_AUTHORITY_SCHEMA_VERSION
        or payload.get("development_only") is not True
        or payload.get("decision_grade_eligible") is not False
        or payload.get("deployment_authorized") is not False
        or any(
            not _same(payload.get(key), preparation_payload.get(key))
            for key in (
                "source_fragment_digest",
                "aggregate_trade_boundary_index_request_hash",
                "aggregate_trade_boundary_index_result_digest",
                "aggregate_trade_streamed_reconstruction_digest",
                "aggregate_trade_intra_day_raw_id_gap_stream",
                "aggregate_trade_cross_date_raw_id_gap_stream",
                "aggregate_trade_coverage_gaps",
                "missing_boundaries",
            )
        )
        or any(
            not _same(payload.get(key), preparation_payload.get(key))
            for key in (
                "xkrx_calendar_ref",
                "arcx_calendar_ref",
                "post_adjustment_unit_regime_ref",
            )
        )
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            "source_profile_authority_payload",
        )
    _canonical_hash(
        "source_projection_request_hash", payload.get("source_projection_request_hash")
    )
    return payload


def _stream_manifest_wire(value: object, subject: str) -> MarketStreamManifest:
    row = _mapping(value, subject)
    capability = _mapping(row.get("capability"), f"{subject}.capability")
    if (
        set(row) != _SOURCE_MANIFEST_WIRE_KEYS
        or set(capability) != {"type", "key", "version"}
        or capability.get("type") != "market_bundle_capability"
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            subject,
        )
    try:
        stream_manifest = MarketStreamManifest(
            _canonical_text(f"{subject}.stream_key", row.get("stream_key")),
            _canonical_text(f"{subject}.event_type", row.get("event_type")),
            MarketBundleCapability(
                _canonical_text(f"{subject}.capability.key", capability.get("key")),
                capability.get("version"),  # type: ignore[arg-type]
            ),
            row.get("event_count"),  # type: ignore[arg-type]
            _canonical_hash(f"{subject}.content_hash", row.get("content_hash")),
        )
    except (TypeError, ValueError) as error:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            subject,
        ) from error
    if not _same(stream_manifest, row):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            subject,
        )
    return stream_manifest


def _source_manifest_rows_v2(
    source_authority_payload: Mapping[str, object],
) -> tuple[MarketStreamManifest, ...]:
    rows = tuple(
        _stream_manifest_wire(value, "source_stream_manifest")
        for value in _sequence(
            source_authority_payload.get("source_stream_manifests"),
            "source_stream_manifests",
        )
    )
    keys = tuple(value.stream_key for value in rows)
    if (
        frozenset(keys) != _SOURCE_STREAM_KEYS
        or keys != tuple(sorted(keys))
        or len(set(keys)) != len(keys)
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            "source_stream_manifests",
        )
    return rows


def _source_events_v2(
    reader: MarketBundleReader,
    manifest: MarketBundleManifest,
    source_authority_payload: Mapping[str, object],
) -> tuple[MarketEvent, ...]:
    events: list[MarketEvent] = []
    for authority_manifest in _source_manifest_rows_v2(source_authority_payload):
        bundle_manifest = _manifest_stream(manifest, authority_manifest.stream_key)
        if not _same(authority_manifest, bundle_manifest):
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
                f"source_stream_manifest:{authority_manifest.stream_key}",
            )
        events.extend(_read_stream(reader, manifest, authority_manifest.stream_key))
    return tuple(events)


def _execution_projection_events_v2(
    reader: MarketBundleReader,
    manifest: MarketBundleManifest,
    intent: BinanceUsdmTradifiBarRequestIntent,
    source_authority_payload: Mapping[str, object],
) -> tuple[MarketEvent, ...]:
    authority_manifest = _stream_manifest_wire(
        source_authority_payload.get("execution_projection_stream_manifest"),
        "execution_projection_stream_manifest",
    )
    bundle_manifest = _manifest_stream(manifest, _EXECUTION_PROJECTION_STREAM_V2)
    if (
        authority_manifest.stream_key != _EXECUTION_PROJECTION_STREAM_V2
        or authority_manifest.event_type != _EXECUTION_PROJECTION_EVENT_TYPE
        or authority_manifest.capability != _EXECUTION_PROJECTION_CAPABILITY
        or not _same(authority_manifest, bundle_manifest)
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            "execution_projection_stream_manifest",
        )
    events = _read_stream(reader, manifest, _EXECUTION_PROJECTION_STREAM_V2)
    bindings = tuple(
        _mapping(value, "execution_projection_event_binding")
        for value in _sequence(
            source_authority_payload.get("execution_projection_event_bindings"),
            "execution_projection_event_bindings",
        )
    )
    expected_bindings = tuple(
        sorted(
            (
                {
                    "stream_key": event.stream_key,
                    "event_id": event.event_id,
                    "event_hash": event.event_hash,
                }
                for event in events
            ),
            key=lambda value: (
                value["stream_key"],
                value["event_id"],
                value["event_hash"],
            ),
        )
    )
    if not _same(bindings, expected_bindings):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            "execution_projection_event_bindings",
        )
    for index, event in enumerate(events):
        open_price = _mapping(event.payload.get("open_price"), "bar_open.open_price")
        if (
            event.stream_key != _EXECUTION_PROJECTION_STREAM_V2
            or event.event_type != _EXECUTION_PROJECTION_EVENT_TYPE
            or event.capability != _EXECUTION_PROJECTION_CAPABILITY
            or event.instrument_id is None
            or not _same(event.instrument_id, _INSTRUMENT_WIRE)
            or not intent.timeline_window.data_start
            <= event.event_time
            < intent.timeline_window.end_exclusive
            or event.available_time != event.event_time
            or event.phase != domain.TimelinePhase(20, "bar_open")
            or event.source_sequence != domain.SourceSequence(index)
            or event.supersedes_revision_id is not None
            or event.source_key != _EXECUTION_PROJECTION_SOURCE_V2
            or not event.event_id.startswith(
                "binance-usdm-koru-first-retained-trade-bar-open-v2:sha256:"
            )
            or set(event.payload) != {"schema_version", "bar_kind", "open_price"}
            or event.payload.get("schema_version") != 1
            or event.payload.get("bar_kind") != "real"
            or set(open_price) != {"units", "scale", "quote_currency"}
            or type(open_price.get("units")) is not int
            or open_price.get("units", 0) <= 0  # type: ignore[operator]
            or open_price.get("scale") != 8
            or open_price.get("quote_currency") != "USDT"
        ):
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH,
                "execution_projection_event",
            )
    return events


def _account_authority_v2(
    reader: MarketBundleReader,
    manifest: MarketBundleManifest,
    intent: BinanceUsdmTradifiBarRequestIntent,
    provider_inputs: BinanceUsdmTradifiProviderInputs,
    preparation_payload: Mapping[str, object],
) -> MarketEvent:
    events = _read_stream(reader, manifest, _ACCOUNT_STREAM_V2)
    if len(events) != 1:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
            "account_event_count",
        )
    event = events[0]
    payload = event.payload
    strategy_ref = _artifact_ref(payload.get("strategy_definition_ref"), "account_strategy_ref")
    if (
        event.stream_key != _ACCOUNT_STREAM_V2
        or event.event_type != _ACCOUNT_EVENT_TYPE
        or event.capability != _ACCOUNT_CAPABILITY
        or event.instrument_id is None
        or not _same(event.instrument_id, _INSTRUMENT_WIRE)
        or event.event_time != intent.timeline_window.data_start
        or event.available_time != intent.timeline_window.data_start
        or event.phase != domain.TimelinePhase(110, "account_financial_dispatch")
        or event.source_sequence != domain.SourceSequence(0)
        or set(payload)
        != {
            "schema_version",
            "account_id",
            "initial_equity",
            "sleeve_allocation_fraction",
            "position_notional_usdt",
            "profile_composition_request_hash",
            "strategy_definition_ref",
            "strategy_definition_hash",
            "operation_authorized",
            "order_authorized",
            "deployment_authorized",
        }
        or payload.get("schema_version") != _BUNDLE_SCHEMA_VERSION_V2
        or payload.get("account_id") != intent.execution_account_id
        or not _same(payload.get("initial_equity"), provider_inputs.initial_equity)
        or payload.get("sleeve_allocation_fraction")
        != provider_inputs.sleeve_allocation_fraction
        or payload.get("position_notional_usdt") != _REQUIRED_NOTIONAL
        or payload.get("profile_composition_request_hash")
        != preparation_payload.get("profile_composition_request_hash")
        or strategy_ref != intent.strategy_definition_ref
        or payload.get("strategy_definition_hash") != strategy_ref.content_hash
        or not _exact_false(payload.get("operation_authorized"))
        or not _exact_false(payload.get("order_authorized"))
        or not _exact_false(payload.get("deployment_authorized"))
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
            "account_event_contract",
        )
    return event


def _expected_stream_keys_v2(
    source_authority_payload: Mapping[str, object],
) -> frozenset[str]:
    source_keys = {
        value.stream_key for value in _source_manifest_rows_v2(source_authority_payload)
    }
    projection_manifest = _stream_manifest_wire(
        source_authority_payload.get("execution_projection_stream_manifest"),
        "execution_projection_stream_manifest",
    )
    if projection_manifest.stream_key != _EXECUTION_PROJECTION_STREAM_V2:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
            "execution_projection_stream_manifest",
        )
    return frozenset(
        {
            *source_keys,
            _EXECUTION_PROJECTION_STREAM_V2,
            *(f"{_TARGET_PREFIX}{value}.v2" for value in _PARAMETER_IDS),
            _PREPARATION_STREAM_V2,
            _PRICE_PURPOSE_STREAM_V2,
            _ACCOUNT_STREAM_V2,
        }
    )


def _validate_manifest_stream_cover_v2(
    manifest: MarketBundleManifest,
    source_authority_payload: Mapping[str, object],
) -> None:
    actual = tuple(value.stream_key for value in manifest.streams)
    expected = _expected_stream_keys_v2(source_authority_payload)
    if len(actual) != len(expected) or frozenset(actual) != expected:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH,
            "manifest_stream_cover",
        )


def _profile_v2(
    preparation_payload: Mapping[str, object],
    intent: BinanceUsdmTradifiBarRequestIntent,
    refs: tuple[domain.ArtifactRef, ...],
    source_artifact: _VerifiedArtifact,
    source_events: tuple[MarketEvent, ...],
) -> BinanceUsdmTradifiResolvedProfile:
    resolved = _profile(preparation_payload, intent, refs)
    request = resolved.request
    development = build_binance_usdm_koru_tradifi_development_profile_v1(
        BinanceUsdmKoruTradifiDevelopmentProfileRequestV1(
            timeline_window=intent.timeline_window,
            composed_at=request.composed_at,
            account_id=intent.execution_account_id,
            xkrx_calendar_ref=refs[2],
            arcx_calendar_ref=refs[3],
            post_adjustment_unit_regime_ref=refs[4],
            source_profile_authority_envelope=source_artifact.envelope,
            source_profile_authority_ref=source_artifact.ref,
            source_events=source_events,
        )
    )
    result = development.result
    wire = _mapping(
        preparation_payload.get("profile_composition_request_wire"), "profile_wire"
    )
    expected_hash = preparation_payload.get("profile_composition_request_hash")
    if (
        development.failure is not None
        or result is None
        or result.source_profile_authority_ref != source_artifact.ref
        or result.source_profile_authority_hash != source_artifact.envelope.content_hash
        or result.profile_composition_request_hash != expected_hash
        or not _same(result.profile_composition_request_wire, wire)
        or not _same(result.profile_composition_request, request)
        or not _same(result.resolved_profile, resolved)
        or not _same(result.profile_registry, resolved.profile_registry)
        or not _same(
            result.financial_dispatcher_spec, resolved.financial_dispatcher_spec
        )
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PROFILE_BINDING_INVALID,
            "development_profile_authority",
        )
    source_manifest_rows = tuple(
        _mapping(value, "source_stream_manifest")
        for value in _sequence(
            _mapping(
                source_artifact.envelope.payload, "source_profile_authority_payload"
            ).get("source_stream_manifests"),
            "source_stream_manifests",
        )
    )
    expected_stream_hashes = tuple(
        (
            _canonical_text("stream_key", row.get("stream_key")),
            _canonical_hash("content_hash", row.get("content_hash")),
        )
        for row in source_manifest_rows
    )
    if result.source_stream_hashes != expected_stream_hashes:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PROFILE_BINDING_INVALID,
            "development_profile_stream_hashes",
        )
    return resolved


def _price_purpose_authority(
    reader: MarketBundleReader,
    manifest: MarketBundleManifest,
    intent: BinanceUsdmTradifiBarRequestIntent,
    preparation_payload: Mapping[str, object],
    bundle_schema_version: int = 1,
) -> MarketEvent:
    stream_key = (
        _PRICE_PURPOSE_STREAM
        if bundle_schema_version == 1
        else _PRICE_PURPOSE_STREAM_V2
    )
    event_type = (
        _PRICE_PURPOSE_EVENT_TYPE
        if bundle_schema_version == 1
        else _PRICE_PURPOSE_EVENT_TYPE_V2
    )
    payload_keys = (
        _PRICE_AUTHORITY_PAYLOAD_KEYS
        if bundle_schema_version == 1
        else _PRICE_AUTHORITY_PAYLOAD_KEYS_V2
    )
    events = _read_stream(reader, manifest, stream_key)
    if len(events) != 1:
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
            "price_purpose_event_count",
        )
    event = events[0]
    payload = event.payload
    binding = _mapping(
        preparation_payload.get("price_purpose_authority_binding"),
        "price_purpose_authority_binding",
    )
    expected_binding = {
        "stream_key": event.stream_key,
        "event_type": event.event_type,
        "event_id": event.event_id,
        "event_hash": event.event_hash,
    }
    if (
        event.stream_key != stream_key
        or event.event_type != event_type
        or event.capability != _PRICE_PURPOSE_CAPABILITY
        or event.instrument_id is None
        or not _same(event.instrument_id.to_canonical_dict(), _INSTRUMENT_WIRE)
        or event.event_time != intent.timeline_window.data_start
        or event.available_time != intent.timeline_window.data_start
        or event.phase != domain.TimelinePhase(0, "market_data")
        or event.source_sequence != domain.SourceSequence(0)
        or set(binding) != _PRICE_EVENT_BINDING_KEYS
        or not _same(binding, expected_binding)
        or set(payload) != payload_keys
        or payload.get("schema_version") != bundle_schema_version
        or not _same(payload.get("instrument_id"), _INSTRUMENT_WIRE)
        or payload.get("source_fragment_digest")
        != preparation_payload.get("source_fragment_digest")
        or payload.get("profile_composition_request_hash")
        != preparation_payload.get("profile_composition_request_hash")
        or (
            bundle_schema_version == _BUNDLE_SCHEMA_VERSION_V2
            and any(
                not _same(payload.get(key), preparation_payload.get(key))
                for key in _STREAMING_AUTHORITY_KEYS
            )
        )
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
            "price_purpose_event_binding",
        )
    resolutions: dict[object, Mapping[str, object]] = {}
    for value in _sequence(
        _mapping(
            preparation_payload.get("profile_composition_request_wire"),
            "profile_wire",
        ).get("price_purposes"),
        "profile_price_purposes",
    ):
        resolution = _mapping(value, "price_resolution")
        query = _mapping(resolution.get("query"), "price_resolution.query")
        resolutions[query.get("price_purpose")] = resolution
    rows = tuple(
        _mapping(value, "price_purpose_binding")
        for value in _sequence(
            payload.get("price_purpose_bindings"), "price_purpose_bindings"
        )
    )
    if (
        len(rows) != 4
        or tuple(row.get("price_purpose") for row in rows) != _PRICE_PURPOSES
    ):
        raise _PreparationError(
            BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
            "price_purpose_cover",
        )
    for row in rows:
        purpose = row.get("price_purpose")
        if type(purpose) is not str or set(row) != _PRICE_BINDING_KEYS:
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
                "price_purpose_binding_schema",
            )
        source_manifest = _mapping(
            row.get("source_stream_manifest"), "source_stream_manifest"
        )
        bound_manifest = _manifest_stream(
            manifest, _PRICE_PURPOSE_SOURCE_STREAMS[purpose]
        )
        _read_stream(reader, manifest, bound_manifest.stream_key)
        selected_resolution = resolutions.get(purpose)
        if selected_resolution is None:
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
                "price_purpose_profile_binding",
            )
        query = _mapping(selected_resolution.get("query"), "price_purpose_query")
        book = _mapping(query.get("price_book"), "price_book")
        coverages = tuple(
            _mapping(value, "price_coverage")
            for value in _sequence(book.get("coverages"), "price_coverages")
        )
        matching = tuple(
            value
            for value in coverages
            if value.get("price_purpose") == purpose
            and value.get("source_kind") == _PRICE_PURPOSE_SOURCE_KINDS[purpose]
        )
        expected_manifest = {
            "stream_key": bound_manifest.stream_key,
            "event_type": bound_manifest.event_type,
            "original_capability": bound_manifest.capability,
            "event_count": bound_manifest.event_count,
            "content_hash": bound_manifest.content_hash,
        }
        if (
            len(matching) != 1
            or row.get("source_kind") != _PRICE_PURPOSE_SOURCE_KINDS[purpose]
            or row.get("stream_id") != matching[0].get("stream_id")
            or not _same(row.get("source_ref"), matching[0].get("source_ref"))
            or not _same(row.get("coverage_from"), matching[0].get("coverage_from"))
            or not _same(
                row.get("coverage_to_exclusive"),
                matching[0].get("coverage_to_exclusive"),
            )
            or row.get("coverage_hash") != domain.canonical_sha256(matching[0])
            or row.get("price_resolution_hash")
            != domain.canonical_sha256(selected_resolution)
            or set(source_manifest) != _SOURCE_MANIFEST_KEYS
            or not _same(source_manifest, expected_manifest)
        ):
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
                f"price_purpose_binding:{purpose}",
            )
    return event


def _validate_preparation_result_v1(
    result: BinanceUsdmTradifiPreparationResult,
) -> None:
    if (
        result.bundle_schema_version != 1
        or result.source_profile_authority_ref is not None
        or result.source_profile_authority_hash is not None
    ):
        raise ValueError("V1 result cannot retain V2 authority evidence")
    if type(result.intent) is not BinanceUsdmTradifiBarRequestIntent:
        raise TypeError("intent must be exact BinanceUsdmTradifiBarRequestIntent")
    if type(result.provider_inputs) is not BinanceUsdmTradifiProviderInputs:
        raise TypeError(
            "provider_inputs must be exact BinanceUsdmTradifiProviderInputs"
        )
    if (
        type(result.market_bundle_manifest) is not MarketBundleManifest
        or type(result.market_bundle_ref) is not MarketBundleRef
        or result.market_bundle_ref != result.intent.market_bundle_ref
        or MarketBundleRef.from_manifest(result.market_bundle_manifest)
        != result.market_bundle_ref
        or result.market_bundle_manifest.coverage_start
        != result.intent.timeline_window.data_start
        or result.market_bundle_manifest.coverage_end_exclusive
        != result.intent.timeline_window.end_exclusive
        or getattr(result.market_reader, "bundle_ref", None) != result.market_bundle_ref
        or not _same(
            getattr(result.market_reader, "manifest", None),
            result.market_bundle_manifest,
        )
    ):
        raise ValueError("retained market reader manifest/ref mismatch")
    authority_event, payload = _authority(
        result.market_reader, result.market_bundle_manifest, result.intent
    )
    if (
        type(result.preparation_authority_event) is not MarketEvent
        or not _same(result.preparation_authority_event, authority_event)
        or result.preparation_authority_hash != authority_event.event_hash
    ):
        raise ValueError("preparation authority evidence mismatch")
    _validate_authority_support(payload, result.provider_inputs)
    _price_purpose_authority(
        result.market_reader,
        result.market_bundle_manifest,
        result.intent,
        payload,
    )
    rows = _target_bindings(payload, result.intent)
    if (
        type(result.verified_target_bindings) is not tuple
        or len(result.verified_target_bindings) != 8
        or any(
            type(value) is not _VerifiedParameterTargetBinding
            for value in result.verified_target_bindings
        )
        or tuple(
            (
                value.parameter_id,
                value.parameter_ref,
                value.target_stream_key,
                value.target_stream_digest,
            )
            for value in result.verified_target_bindings
        )
        != rows
    ):
        raise ValueError("verified target binding evidence mismatch")
    source_fragment_digest = _canonical_hash(
        "source_fragment_digest", payload.get("source_fragment_digest")
    )
    for evidence in result.verified_target_bindings:
        refs = (
            _EXPECTED_STRATEGY_REF,
            evidence.parameter_ref,
            *_EXPECTED_AUTHORITY_REFS,
        )
        rebuilt = _target_stream(
            result.market_reader,
            result.market_bundle_manifest,
            result.intent,
            evidence.target_stream_key,
            evidence.target_stream_digest,
            refs,
            source_fragment_digest,
        )
        if evidence.stream_manifest != _manifest_stream(
            result.market_bundle_manifest, evidence.target_stream_key
        ) or not _same(evidence.target_stream, rebuilt):
            raise ValueError("retained target stream evidence mismatch")
    selected = next(
        value
        for value in result.verified_target_bindings
        if value.parameter_ref == result.intent.strategy_parameter_set_ref
    )
    if (
        type(result.target_stream) is not PrecomputedTargetStream
        or not _same(result.target_stream, selected.target_stream)
        or result.target_stream_key != selected.target_stream_key
        or result.target_stream_digest != selected.target_stream_digest
    ):
        raise ValueError("selected target stream mismatch")
    if (
        type(result.verified_artifacts) is not tuple
        or len(result.verified_artifacts) != 12
        or any(
            type(value) is not _VerifiedArtifact for value in result.verified_artifacts
        )
    ):
        raise ValueError("verified_artifacts must exact-cover twelve frozen artifacts")
    _payload_identity(result.verified_artifacts)
    refs = (
        _EXPECTED_STRATEGY_REF,
        result.intent.strategy_parameter_set_ref,
        *_EXPECTED_AUTHORITY_REFS,
    )
    resolved = _profile(payload, result.intent, refs)
    if (
        type(result.profile_composition_request)
        is not BinanceUsdmTradifiProfileCompositionRequest
        or not _same(result.profile_composition_request, resolved.request)
        or type(result.resolved_profile) is not BinanceUsdmTradifiResolvedProfile
        or not _same(result.resolved_profile, resolved)
        or type(result.profile_registry) is not BacktestProfileRegistry
        or not _same(result.profile_registry, resolved.profile_registry)
        or type(result.financial_dispatcher_spec) is not FinancialDispatcherSpec
        or not _same(
            result.financial_dispatcher_spec,
            resolved.financial_dispatcher_spec,
        )
    ):
        raise ValueError("resolved profile evidence mismatch")
    expected_build_manifest = _provider_build_manifest(
        result.provider_inputs.build_artifact_manifest,
        resolved.profile_registry,
    )
    if type(result.build_artifact_manifest) is not BuildArtifactManifest or not _same(
        result.build_artifact_manifest, expected_build_manifest
    ):
        raise ValueError("build artifact manifest mismatch")
    required_capabilities = tuple(
        dict.fromkeys(
            (
                *resolved.market_registration.required_bundle_capabilities,
                *resolved.simulation_registration.required_bundle_capabilities,
            )
        )
    )
    if (
        result.market_reader.validate_requirements(
            required_capabilities=required_capabilities
        )
        is not None
    ):
        raise ValueError("profile bundle requirements are not retained")


def _validate_preparation_result_v2(
    result: BinanceUsdmTradifiPreparationResult,
) -> None:
    if type(result.intent) is not BinanceUsdmTradifiBarRequestIntent:
        raise TypeError("intent must be exact BinanceUsdmTradifiBarRequestIntent")
    if type(result.provider_inputs) is not BinanceUsdmTradifiProviderInputs:
        raise TypeError(
            "provider_inputs must be exact BinanceUsdmTradifiProviderInputs"
        )
    manifest = result.market_bundle_manifest
    if (
        result.bundle_schema_version != _BUNDLE_SCHEMA_VERSION_V2
        or type(manifest) is not MarketBundleManifest
        or manifest.schema_version != _BUNDLE_SCHEMA_VERSION_V2
        or _V2_BUNDLE_KEY.fullmatch(manifest.bundle_key) is None
        or type(result.market_bundle_ref) is not MarketBundleRef
        or result.market_bundle_ref != result.intent.market_bundle_ref
        or MarketBundleRef.from_manifest(manifest) != result.market_bundle_ref
        or manifest.coverage_start != result.intent.timeline_window.data_start
        or manifest.coverage_end_exclusive
        != result.intent.timeline_window.end_exclusive
        or getattr(result.market_reader, "bundle_ref", None)
        != result.market_bundle_ref
        or not _same(getattr(result.market_reader, "manifest", None), manifest)
        or any(
            stream.stream_key
            in {
                _PREPARATION_STREAM,
                _PRICE_PURPOSE_STREAM,
                _ACCOUNT_STREAM_V1,
                _EXECUTION_PROJECTION_STREAM_V1,
                *(f"{_TARGET_PREFIX}{value}.v1" for value in _PARAMETER_IDS),
            }
            for stream in manifest.streams
        )
    ):
        raise ValueError("retained V2 market reader manifest/ref mismatch")
    authority_event, payload = _authority(
        result.market_reader,
        manifest,
        result.intent,
        _BUNDLE_SCHEMA_VERSION_V2,
    )
    if (
        type(result.preparation_authority_event) is not MarketEvent
        or not _same(result.preparation_authority_event, authority_event)
        or result.preparation_authority_hash != authority_event.event_hash
    ):
        raise ValueError("preparation authority evidence mismatch")
    authority_refs, source_ref = _validate_authority_support_v2(
        payload, result.provider_inputs
    )
    _price_purpose_authority(
        result.market_reader,
        manifest,
        result.intent,
        payload,
        _BUNDLE_SCHEMA_VERSION_V2,
    )
    rows = _target_bindings(payload, result.intent, _BUNDLE_SCHEMA_VERSION_V2)
    if (
        type(result.verified_target_bindings) is not tuple
        or len(result.verified_target_bindings) != 8
        or any(
            type(value) is not _VerifiedParameterTargetBinding
            or value.bundle_schema_version != _BUNDLE_SCHEMA_VERSION_V2
            for value in result.verified_target_bindings
        )
        or tuple(
            (
                value.parameter_id,
                value.parameter_ref,
                value.target_stream_key,
                value.target_stream_digest,
            )
            for value in result.verified_target_bindings
        )
        != rows
    ):
        raise ValueError("verified V2 target binding evidence mismatch")
    source_fragment_digest = _canonical_hash(
        "source_fragment_digest", payload.get("source_fragment_digest")
    )
    for evidence in result.verified_target_bindings:
        refs = (
            _EXPECTED_STRATEGY_REF,
            evidence.parameter_ref,
            *authority_refs,
        )
        rebuilt = _target_stream(
            result.market_reader,
            manifest,
            result.intent,
            evidence.target_stream_key,
            evidence.target_stream_digest,
            refs,
            source_fragment_digest,
        )
        if evidence.stream_manifest != _manifest_stream(
            manifest, evidence.target_stream_key
        ) or not _same(evidence.target_stream, rebuilt):
            raise ValueError("retained V2 target stream evidence mismatch")
    selected = next(
        value
        for value in result.verified_target_bindings
        if value.parameter_ref == result.intent.strategy_parameter_set_ref
    )
    if (
        type(result.target_stream) is not PrecomputedTargetStream
        or not _same(result.target_stream, selected.target_stream)
        or result.target_stream_key != selected.target_stream_key
        or result.target_stream_digest != selected.target_stream_digest
    ):
        raise ValueError("selected V2 target stream mismatch")
    if (
        type(result.verified_artifacts) is not tuple
        or len(result.verified_artifacts) != 13
        or any(
            type(value) is not _VerifiedArtifact for value in result.verified_artifacts
        )
    ):
        raise ValueError("V2 verified_artifacts must exact-cover thirteen artifacts")
    _payload_identity(result.verified_artifacts[:12])
    source_artifact = result.verified_artifacts[12]
    source_payload = _source_profile_authority_v2(payload, source_artifact)
    _validate_manifest_stream_cover_v2(manifest, source_payload)
    _execution_projection_events_v2(
        result.market_reader, manifest, result.intent, source_payload
    )
    _account_authority_v2(
        result.market_reader,
        manifest,
        result.intent,
        result.provider_inputs,
        payload,
    )
    if (
        source_artifact.ref != source_ref
        or result.source_profile_authority_ref != source_ref
        or result.source_profile_authority_hash != source_artifact.envelope.content_hash
    ):
        raise ValueError("retained source profile authority evidence mismatch")
    source_events = _source_events_v2(
        result.market_reader, manifest, source_payload
    )
    refs = (
        _EXPECTED_STRATEGY_REF,
        result.intent.strategy_parameter_set_ref,
        *authority_refs,
    )
    resolved = _profile_v2(
        payload, result.intent, refs, source_artifact, source_events
    )
    if (
        type(result.profile_composition_request)
        is not BinanceUsdmTradifiProfileCompositionRequest
        or not _same(result.profile_composition_request, resolved.request)
        or type(result.resolved_profile) is not BinanceUsdmTradifiResolvedProfile
        or not _same(result.resolved_profile, resolved)
        or type(result.profile_registry) is not BacktestProfileRegistry
        or not _same(result.profile_registry, resolved.profile_registry)
        or type(result.financial_dispatcher_spec) is not FinancialDispatcherSpec
        or not _same(
            result.financial_dispatcher_spec,
            resolved.financial_dispatcher_spec,
        )
    ):
        raise ValueError("resolved V2 profile evidence mismatch")
    expected_build_manifest = _provider_build_manifest(
        result.provider_inputs.build_artifact_manifest,
        resolved.profile_registry,
    )
    if type(result.build_artifact_manifest) is not BuildArtifactManifest or not _same(
        result.build_artifact_manifest, expected_build_manifest
    ):
        raise ValueError("V2 build artifact manifest mismatch")
    required_capabilities = tuple(
        dict.fromkeys(
            (
                *resolved.market_registration.required_bundle_capabilities,
                *resolved.simulation_registration.required_bundle_capabilities,
            )
        )
    )
    if (
        result.market_reader.validate_requirements(
            required_capabilities=required_capabilities
        )
        is not None
    ):
        raise ValueError("V2 profile bundle requirements are not retained")


def _validate_preparation_result(
    result: BinanceUsdmTradifiPreparationResult,
) -> None:
    if result.bundle_schema_version == 1:
        _validate_preparation_result_v1(result)
    elif result.bundle_schema_version == _BUNDLE_SCHEMA_VERSION_V2:
        _validate_preparation_result_v2(result)
    else:
        raise ValueError("unsupported bundle_schema_version")


def resolve_binance_usdm_tradifi_preparation_authority_v1(
    *,
    intent: BinanceUsdmTradifiBarRequestIntent,
    provider_inputs: BinanceUsdmTradifiProviderInputs,
    artifact_reader: ArtifactEnvelopeReader,
    market_reader: MarketBundleReader,
) -> BinanceUsdmTradifiPreparationOutcome:
    if type(intent) is not BinanceUsdmTradifiBarRequestIntent:
        return _fail(BinanceUsdmTradifiPreparationFailureCode.INVALID_INTENT, "intent")
    if type(provider_inputs) is not BinanceUsdmTradifiProviderInputs:
        return _fail(
            BinanceUsdmTradifiPreparationFailureCode.INVALID_PROVIDER_INPUTS,
            "provider_inputs",
        )
    if not callable(getattr(artifact_reader, "read", None)):
        return _fail(
            BinanceUsdmTradifiPreparationFailureCode.INVALID_PROVIDER_INPUTS,
            "artifact_reader",
        )
    try:
        bundle_ref = market_reader.bundle_ref
        manifest = market_reader.manifest
        if (
            type(bundle_ref) is not MarketBundleRef
            or type(manifest) is not MarketBundleManifest
            or bundle_ref != intent.market_bundle_ref
            or MarketBundleRef.from_manifest(manifest) != bundle_ref
            or manifest.coverage_start != intent.timeline_window.data_start
            or manifest.coverage_end_exclusive != intent.timeline_window.end_exclusive
        ):
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH,
                "bundle_ref_window",
            )
        requirement_failure = market_reader.validate_requirements(
            required_capabilities=(
                _PREPARATION_CAPABILITY,
                _PRICE_PURPOSE_CAPABILITY,
                TARGET_STREAM_CAPABILITY,
            ),
            required_streams=(
                _PREPARATION_STREAM,
                _PRICE_PURPOSE_STREAM,
                *(f"{_TARGET_PREFIX}{value}.v1" for value in _PARAMETER_IDS),
            ),
        )
        if requirement_failure is not None:
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH,
                "authority_requirements",
            )
        authority_event, payload = _authority(market_reader, manifest, intent)
        rows = _target_bindings(payload, intent)
        authority_refs = _validate_authority_support(payload, provider_inputs)
        _price_purpose_authority(market_reader, manifest, intent, payload)
        source_fragment_digest = _canonical_hash(
            "source_fragment_digest", payload.get("source_fragment_digest")
        )
        verified_targets = []
        for parameter_id, parameter_ref, stream_key, target_digest in rows:
            refs = (_EXPECTED_STRATEGY_REF, parameter_ref, *authority_refs)
            target_stream = _target_stream(
                market_reader,
                manifest,
                intent,
                stream_key,
                target_digest,
                refs,
                source_fragment_digest,
            )
            verified_targets.append(
                _VerifiedParameterTargetBinding(
                    parameter_id,
                    parameter_ref,
                    stream_key,
                    target_digest,
                    _manifest_stream(manifest, stream_key),
                    target_stream,
                )
            )
        verified_target_bindings = tuple(verified_targets)
        selected = next(
            value
            for value in verified_target_bindings
            if value.parameter_ref == intent.strategy_parameter_set_ref
        )
        artifact_refs = (
            _EXPECTED_STRATEGY_REF,
            *_EXPECTED_PARAMETER_REFS,
            *_EXPECTED_AUTHORITY_REFS,
        )
        artifacts = tuple(
            _verify_artifact(artifact_reader, ref) for ref in artifact_refs
        )
        _payload_identity(artifacts)
        profile_refs = (
            _EXPECTED_STRATEGY_REF,
            intent.strategy_parameter_set_ref,
            *authority_refs,
        )
        resolved = _profile(payload, intent, profile_refs)
        try:
            build_manifest = _provider_build_manifest(
                provider_inputs.build_artifact_manifest, resolved.profile_registry
            )
        except (TypeError, ValueError) as error:
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.BUILD_MANIFEST_CONFLICT,
                "profile_registration",
            ) from error
        result = BinanceUsdmTradifiPreparationResult(
            intent=intent,
            provider_inputs=provider_inputs,
            preparation_authority_event=authority_event,
            preparation_authority_hash=authority_event.event_hash,
            verified_target_bindings=verified_target_bindings,
            target_stream=selected.target_stream,
            target_stream_key=selected.target_stream_key,
            target_stream_digest=selected.target_stream_digest,
            profile_composition_request=resolved.request,
            resolved_profile=resolved,
            profile_registry=resolved.profile_registry,
            financial_dispatcher_spec=resolved.financial_dispatcher_spec,
            verified_artifacts=artifacts,
            build_artifact_manifest=build_manifest,
            market_bundle_manifest=manifest,
            market_bundle_ref=bundle_ref,
            market_reader=market_reader,
        )
        return BinanceUsdmTradifiPreparationOutcome(result=result)
    except _PreparationError as error:
        return _fail(error.code, error.subject)
    except Exception:  # noqa: BLE001 - the public boundary must fail closed
        return _fail(
            BinanceUsdmTradifiPreparationFailureCode.RESULT_INVALID,
            "unexpected_input",
        )


def resolve_binance_usdm_tradifi_preparation_authority_v2(
    *,
    intent: BinanceUsdmTradifiBarRequestIntent,
    provider_inputs: BinanceUsdmTradifiProviderInputs,
    artifact_reader: ArtifactEnvelopeReader,
    market_reader: MarketBundleReader,
) -> BinanceUsdmTradifiPreparationOutcome:
    if type(intent) is not BinanceUsdmTradifiBarRequestIntent:
        return _fail(BinanceUsdmTradifiPreparationFailureCode.INVALID_INTENT, "intent")
    if type(provider_inputs) is not BinanceUsdmTradifiProviderInputs:
        return _fail(
            BinanceUsdmTradifiPreparationFailureCode.INVALID_PROVIDER_INPUTS,
            "provider_inputs",
        )
    if not callable(getattr(artifact_reader, "read", None)):
        return _fail(
            BinanceUsdmTradifiPreparationFailureCode.INVALID_PROVIDER_INPUTS,
            "artifact_reader",
        )
    try:
        bundle_ref = market_reader.bundle_ref
        manifest = market_reader.manifest
        mixed_streams = {
            _PREPARATION_STREAM,
            _PRICE_PURPOSE_STREAM,
            _ACCOUNT_STREAM_V1,
            _EXECUTION_PROJECTION_STREAM_V1,
            *(f"{_TARGET_PREFIX}{value}.v1" for value in _PARAMETER_IDS),
        }
        if (
            type(bundle_ref) is not MarketBundleRef
            or type(manifest) is not MarketBundleManifest
            or manifest.schema_version != _BUNDLE_SCHEMA_VERSION_V2
            or _V2_BUNDLE_KEY.fullmatch(manifest.bundle_key) is None
            or bundle_ref != intent.market_bundle_ref
            or MarketBundleRef.from_manifest(manifest) != bundle_ref
            or manifest.coverage_start != intent.timeline_window.data_start
            or manifest.coverage_end_exclusive
            != intent.timeline_window.end_exclusive
            or any(value.stream_key in mixed_streams for value in manifest.streams)
        ):
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH,
                "bundle_ref_window_version",
            )
        target_stream_keys = tuple(
            f"{_TARGET_PREFIX}{value}.v2" for value in _PARAMETER_IDS
        )
        requirement_failure = market_reader.validate_requirements(
            required_capabilities=(
                _PREPARATION_CAPABILITY,
                _PRICE_PURPOSE_CAPABILITY,
                TARGET_STREAM_CAPABILITY,
            ),
            required_streams=(
                _PREPARATION_STREAM_V2,
                _PRICE_PURPOSE_STREAM_V2,
                _ACCOUNT_STREAM_V2,
                _EXECUTION_PROJECTION_STREAM_V2,
                *target_stream_keys,
            ),
        )
        if requirement_failure is not None:
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH,
                "authority_requirements",
            )
        authority_event, payload = _authority(
            market_reader, manifest, intent, _BUNDLE_SCHEMA_VERSION_V2
        )
        rows = _target_bindings(payload, intent, _BUNDLE_SCHEMA_VERSION_V2)
        authority_refs, source_ref = _validate_authority_support_v2(
            payload, provider_inputs
        )
        _price_purpose_authority(
            market_reader,
            manifest,
            intent,
            payload,
            _BUNDLE_SCHEMA_VERSION_V2,
        )
        source_fragment_digest = _canonical_hash(
            "source_fragment_digest", payload.get("source_fragment_digest")
        )
        verified_targets = []
        for parameter_id, parameter_ref, stream_key, target_digest in rows:
            refs = (_EXPECTED_STRATEGY_REF, parameter_ref, *authority_refs)
            target_stream = _target_stream(
                market_reader,
                manifest,
                intent,
                stream_key,
                target_digest,
                refs,
                source_fragment_digest,
            )
            verified_targets.append(
                _VerifiedParameterTargetBinding(
                    parameter_id,
                    parameter_ref,
                    stream_key,
                    target_digest,
                    _manifest_stream(manifest, stream_key),
                    target_stream,
                    _BUNDLE_SCHEMA_VERSION_V2,
                )
            )
        verified_target_bindings = tuple(verified_targets)
        selected = next(
            value
            for value in verified_target_bindings
            if value.parameter_ref == intent.strategy_parameter_set_ref
        )
        artifact_refs = (
            _EXPECTED_STRATEGY_REF,
            *_EXPECTED_PARAMETER_REFS,
            *_EXPECTED_AUTHORITY_REFS,
            source_ref,
        )
        artifacts = tuple(
            _verify_artifact(artifact_reader, ref) for ref in artifact_refs
        )
        _payload_identity(artifacts[:12])
        source_artifact = artifacts[12]
        source_payload = _source_profile_authority_v2(payload, source_artifact)
        _validate_manifest_stream_cover_v2(manifest, source_payload)
        _execution_projection_events_v2(
            market_reader, manifest, intent, source_payload
        )
        _account_authority_v2(
            market_reader, manifest, intent, provider_inputs, payload
        )
        source_events = _source_events_v2(market_reader, manifest, source_payload)
        profile_refs = (
            _EXPECTED_STRATEGY_REF,
            intent.strategy_parameter_set_ref,
            *authority_refs,
        )
        resolved = _profile_v2(
            payload,
            intent,
            profile_refs,
            source_artifact,
            source_events,
        )
        try:
            build_manifest = _provider_build_manifest(
                provider_inputs.build_artifact_manifest, resolved.profile_registry
            )
        except (TypeError, ValueError) as error:
            raise _PreparationError(
                BinanceUsdmTradifiPreparationFailureCode.BUILD_MANIFEST_CONFLICT,
                "profile_registration",
            ) from error
        result = BinanceUsdmTradifiPreparationResult(
            intent=intent,
            provider_inputs=provider_inputs,
            preparation_authority_event=authority_event,
            preparation_authority_hash=authority_event.event_hash,
            verified_target_bindings=verified_target_bindings,
            target_stream=selected.target_stream,
            target_stream_key=selected.target_stream_key,
            target_stream_digest=selected.target_stream_digest,
            profile_composition_request=resolved.request,
            resolved_profile=resolved,
            profile_registry=resolved.profile_registry,
            financial_dispatcher_spec=resolved.financial_dispatcher_spec,
            verified_artifacts=artifacts,
            build_artifact_manifest=build_manifest,
            market_bundle_manifest=manifest,
            market_bundle_ref=bundle_ref,
            market_reader=market_reader,
            bundle_schema_version=_BUNDLE_SCHEMA_VERSION_V2,
            source_profile_authority_ref=source_ref,
            source_profile_authority_hash=source_artifact.envelope.content_hash,
        )
        return BinanceUsdmTradifiPreparationOutcome(result=result)
    except _PreparationError as error:
        return _fail(error.code, error.subject)
    except Exception:  # noqa: BLE001 - the public boundary must fail closed
        return _fail(
            BinanceUsdmTradifiPreparationFailureCode.RESULT_INVALID,
            "unexpected_input",
        )


__all__ = [
    "BinanceUsdmTradifiBarRequestIntent",
    "BinanceUsdmTradifiPreparationFailure",
    "BinanceUsdmTradifiPreparationFailureCode",
    "BinanceUsdmTradifiPreparationOutcome",
    "BinanceUsdmTradifiPreparationResult",
    "BinanceUsdmTradifiProviderInputs",
    "resolve_binance_usdm_tradifi_preparation_authority_v1",
    "resolve_binance_usdm_tradifi_preparation_authority_v2",
]
