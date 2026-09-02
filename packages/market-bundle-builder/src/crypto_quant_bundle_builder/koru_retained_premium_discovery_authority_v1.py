"""Builder-owned KORU premium discovery declaration; it performs no publication."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    InstrumentId,
    Money,
    Scale,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleRef

from .binance_usdm_koru_aggtrade_boundary_index_v1 import (
    BinanceUsdmKoruAggregateTradeBoundaryIndexResultV2,
)
from .binance_usdm_koru_closed_market_range_targets_v2 import (
    BinanceUsdmKoruClosedMarketRangeTargetsResultV2,
)
from .binance_usdm_koru_directional_target_compiler_v1 import (
    KoruDirectionalDiscoveryScopeV1,
    KoruDirectionalTargetRecipeV1,
    KoruMarkIndexPremiumParametersV1,
)
from .binance_usdm_koru_funding_rate_history_source_bounded_v1 import (
    BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationResultV1,
)
from .binance_usdm_koru_price_bars_source_bounded_v1 import (
    BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1,
)
from .binance_usdm_koru_tradifi_execution_bundle_v2 import (
    BinanceUsdmKoruTradifiExecutionBundleRequestV2,
    build_binance_usdm_koru_tradifi_execution_bundle_v2,
)
from .binance_usdm_koru_tradifi_source_projection_v2 import (
    BinanceUsdmKoruTradifiSourceProjectionRequestV2,
    BinanceUsdmKoruTradifiSourceProjectionResultV2,
    build_binance_usdm_koru_source_profile_authority_v2,
    build_binance_usdm_koru_tradifi_source_projection_v2,
)
from .koru_tradifi_calendar_unit_authority_v1 import (
    KoruTradifiCalendarUnitAuthorityResultV1,
)

_SCHEMA_VERSION = 1
_REQUEST_SCHEMA_VERSION = "koru_retained_premium_discovery_authority_v1"
_SOURCE_ARTIFACT_TYPE = "binance_usdm_koru_source_projection"
_SOURCE_SCHEMA_VERSION = 2
_INSTRUMENT = InstrumentId(VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual")
_REQUIRED_EQUITY = Money(1_000_000_000_000, Scale(8), "USDT")
_REQUIRED_ALLOCATION = "1"
_PREMIUM_IDS = tuple(f"KORU-PRM-{index:02d}" for index in range(1, 5))
_ENTRY_BPS = ("20", "30", "40", "60")


def _same(left: object, right: object) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def _hash(name: str, value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(f"{name} must be a canonical sha256 digest")
    return value


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical text")
    return value


def _scope_is_exact(start: object, end: object) -> bool:
    scope = KoruDirectionalDiscoveryScopeV1()
    return (
        type(start) is UtcInstant
        and type(end) is UtcInstant
        and start == scope.discovery_start
        and end == scope.discovery_end_exclusive
    )


@dataclass(frozen=True, slots=True)
class KoruRetainedPremiumDiscoveryAuthorityRequestV1:
    """Exact normalized V2 inputs, with legacy targets restricted to economics."""

    timeline_window_start: UtcInstant
    timeline_window_end_exclusive: UtcInstant
    instrument_catalog_hash: str
    projection_scale: Scale
    aggregate_trade_boundary_index_result: BinanceUsdmKoruAggregateTradeBoundaryIndexResultV2
    mark_price_results: tuple[BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1, ...]
    index_price_results: tuple[BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1, ...]
    funding_result: BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationResultV1
    authority_result: KoruTradifiCalendarUnitAuthorityResultV1
    legacy_v2_economics_target_result: BinanceUsdmKoruClosedMarketRangeTargetsResultV2
    profile_composition_request_wire: Mapping[str, object]
    profile_composition_request_hash: str
    execution_account_id: str
    initial_equity: Money
    sleeve_allocation_fraction: str
    schema_version: str = _REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.timeline_window_start) is not UtcInstant or type(self.timeline_window_end_exclusive) is not UtcInstant:
            raise TypeError("timeline window must use exact UtcInstant values")
        _hash("instrument_catalog_hash", self.instrument_catalog_hash)
        if type(self.projection_scale) is not Scale:
            raise TypeError("projection_scale must be exact Scale")
        if (
            type(self.aggregate_trade_boundary_index_result) is not BinanceUsdmKoruAggregateTradeBoundaryIndexResultV2
            or type(self.mark_price_results) is not tuple
            or any(type(value) is not BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1 for value in self.mark_price_results)
            or type(self.index_price_results) is not tuple
            or any(type(value) is not BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1 for value in self.index_price_results)
            or type(self.funding_result) is not BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationResultV1
            or type(self.authority_result) is not KoruTradifiCalendarUnitAuthorityResultV1
            or type(self.legacy_v2_economics_target_result) is not BinanceUsdmKoruClosedMarketRangeTargetsResultV2
        ):
            raise TypeError("request must use exact normalized V2 source and economics inputs")
        if not isinstance(self.profile_composition_request_wire, Mapping):
            raise TypeError("profile_composition_request_wire must be a mapping")
        _hash("profile_composition_request_hash", self.profile_composition_request_hash)
        _text("execution_account_id", self.execution_account_id)
        if type(self.initial_equity) is not Money or self.initial_equity != _REQUIRED_EQUITY:
            raise ValueError("initial_equity must be exact 10000 USDT at scale 8")
        if type(self.sleeve_allocation_fraction) is not str or self.sleeve_allocation_fraction != _REQUIRED_ALLOCATION:
            raise ValueError("sleeve_allocation_fraction must be exact full allocation 1")
        if self.schema_version != _REQUEST_SCHEMA_VERSION:
            raise ValueError("request schema_version is invalid")

    def source_projection_request(self) -> BinanceUsdmKoruTradifiSourceProjectionRequestV2:
        return BinanceUsdmKoruTradifiSourceProjectionRequestV2(
            self.timeline_window_start,
            self.timeline_window_end_exclusive,
            self.instrument_catalog_hash,
            self.projection_scale,
            self.aggregate_trade_boundary_index_result,
            self.mark_price_results,
            self.index_price_results,
            self.funding_result,
            self.authority_result,
        )

    @property
    def request_digest(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_retained_premium_discovery_authority_request_v1",
            "schema_version": self.schema_version,
            "timeline_window_start": self.timeline_window_start,
            "timeline_window_end_exclusive": self.timeline_window_end_exclusive,
            "instrument_catalog_hash": self.instrument_catalog_hash,
            "projection_scale": self.projection_scale.places,
            "aggregate_trade_boundary_index_result": self.aggregate_trade_boundary_index_result,
            "mark_price_results": self.mark_price_results,
            "index_price_results": self.index_price_results,
            "funding_result": self.funding_result,
            "authority_result": self.authority_result,
            "legacy_v2_economics_target_result": self.legacy_v2_economics_target_result,
            "profile_composition_request_wire": self.profile_composition_request_wire,
            "profile_composition_request_hash": self.profile_composition_request_hash,
            "execution_account_id": self.execution_account_id,
            "initial_equity": self.initial_equity,
            "sleeve_allocation_fraction": self.sleeve_allocation_fraction,
        }


class KoruRetainedPremiumDiscoveryAuthorityFailureCodeV1(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    DISCOVERY_SCOPE_INVALID = "DISCOVERY_SCOPE_INVALID"
    SOURCE_PROJECTION_INVALID = "SOURCE_PROJECTION_INVALID"
    LEGACY_ECONOMICS_INVALID = "LEGACY_ECONOMICS_INVALID"
    PROFILE_INVALID = "PROFILE_INVALID"
    RESULT_INVALID = "RESULT_INVALID"


@dataclass(frozen=True, slots=True)
class KoruRetainedPremiumDiscoveryAuthorityFailureV1:
    code: KoruRetainedPremiumDiscoveryAuthorityFailureCodeV1
    subject: str

    def __post_init__(self) -> None:
        if type(self.code) is not KoruRetainedPremiumDiscoveryAuthorityFailureCodeV1:
            raise TypeError("code must be exact authority failure code")
        _text("subject", self.subject)

    @property
    def failure_digest(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_retained_premium_discovery_authority_failure_v1",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
        }


@dataclass(frozen=True, slots=True)
class KoruRetainedPremiumDiscoveryAuthorityResultV1:
    """Source authority plus V2 economics identity; legacy target streams are absent."""

    request: KoruRetainedPremiumDiscoveryAuthorityRequestV1
    source_projection: BinanceUsdmKoruTradifiSourceProjectionResultV2
    source_projection_ref: ArtifactRef
    source_fragment_digest: str
    source_profile_authority_envelope: ArtifactEnvelope
    source_profile_authority_ref: ArtifactRef
    legacy_v2_economics_bundle_ref: MarketBundleRef
    legacy_v2_economics_bundle_digest: str
    legacy_v2_economics_result_digest: str
    legacy_v2_economics_role: str = "economics_only_not_strategy_authority"
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not KoruRetainedPremiumDiscoveryAuthorityRequestV1:
            raise TypeError("result request must be exact")
        if type(self.source_projection) is not BinanceUsdmKoruTradifiSourceProjectionResultV2:
            raise TypeError("source_projection must be exact V2 result")
        replay = build_binance_usdm_koru_tradifi_source_projection_v2(
            self.request.source_projection_request()
        )
        if replay.result is None or not _same(self.source_projection, replay.result):
            raise ValueError("source_projection must exactly replay normalized request inputs")
        expected_ref = ArtifactRef(_SOURCE_ARTIFACT_TYPE, _SOURCE_SCHEMA_VERSION, self.source_projection.fragment_digest)
        if (
            type(self.source_projection_ref) is not ArtifactRef
            or self.source_projection_ref != expected_ref
            or self.source_fragment_digest != self.source_projection.fragment_digest
        ):
            raise ValueError("source projection identity mismatch")
        envelope, ref = build_binance_usdm_koru_source_profile_authority_v2(self.source_projection)
        if (
            type(self.source_profile_authority_envelope) is not ArtifactEnvelope
            or not _same(self.source_profile_authority_envelope, envelope)
            or type(self.source_profile_authority_ref) is not ArtifactRef
            or self.source_profile_authority_ref != ref
        ):
            raise ValueError("source profile authority binding mismatch")
        if (
            type(self.legacy_v2_economics_bundle_ref) is not MarketBundleRef
            or self.legacy_v2_economics_bundle_digest != self.legacy_v2_economics_bundle_ref.manifest_hash
            or self.legacy_v2_economics_role != "economics_only_not_strategy_authority"
        ):
            raise ValueError("legacy V2 economics identity must not be strategy authority")
        _hash("legacy_v2_economics_result_digest", self.legacy_v2_economics_result_digest)
        object.__setattr__(self, "result_digest", canonical_sha256(self._body()))

    @property
    def legacy_v2_economics_declared_non_strategy(self) -> bool:
        return True

    def _body(self) -> dict[str, object]:
        return {
            "type": "koru_retained_premium_discovery_authority_result_v1",
            "schema_version": _SCHEMA_VERSION,
            "request_digest": self.request.request_digest,
            "source_projection": self.source_projection,
            "source_projection_ref": self.source_projection_ref,
            "source_fragment_digest": self.source_fragment_digest,
            "source_profile_authority_envelope": self.source_profile_authority_envelope,
            "source_profile_authority_ref": self.source_profile_authority_ref,
            "legacy_v2_economics_bundle_ref": self.legacy_v2_economics_bundle_ref,
            "legacy_v2_economics_bundle_digest": self.legacy_v2_economics_bundle_digest,
            "legacy_v2_economics_result_digest": self.legacy_v2_economics_result_digest,
            "legacy_v2_economics_role": self.legacy_v2_economics_role,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "result_digest": self.result_digest}


@dataclass(frozen=True, slots=True)
class KoruRetainedPremiumDiscoveryAuthorityOutcomeV1:
    result: KoruRetainedPremiumDiscoveryAuthorityResultV1 | None = None
    failure: KoruRetainedPremiumDiscoveryAuthorityFailureV1 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")
        if self.result is not None and type(self.result) is not KoruRetainedPremiumDiscoveryAuthorityResultV1:
            raise TypeError("result must be exact authority result")
        if self.failure is not None and type(self.failure) is not KoruRetainedPremiumDiscoveryAuthorityFailureV1:
            raise TypeError("failure must be exact authority failure")


def build_koru_retained_premium_discovery_authority_v1(
    request: KoruRetainedPremiumDiscoveryAuthorityRequestV1,
) -> KoruRetainedPremiumDiscoveryAuthorityOutcomeV1:
    """Build the frozen discovery source and V2 economics identity, without publishing."""
    if type(request) is not KoruRetainedPremiumDiscoveryAuthorityRequestV1:
        return KoruRetainedPremiumDiscoveryAuthorityOutcomeV1(
            failure=KoruRetainedPremiumDiscoveryAuthorityFailureV1(
                KoruRetainedPremiumDiscoveryAuthorityFailureCodeV1.INVALID_REQUEST, "request"
            )
        )
    if not _scope_is_exact(request.timeline_window_start, request.timeline_window_end_exclusive):
        return KoruRetainedPremiumDiscoveryAuthorityOutcomeV1(
            failure=KoruRetainedPremiumDiscoveryAuthorityFailureV1(
                KoruRetainedPremiumDiscoveryAuthorityFailureCodeV1.DISCOVERY_SCOPE_INVALID, "timeline_window"
            )
        )
    try:
        source_outcome = build_binance_usdm_koru_tradifi_source_projection_v2(request.source_projection_request())
    except (AttributeError, KeyError, TypeError, ValueError):
        return KoruRetainedPremiumDiscoveryAuthorityOutcomeV1(
            failure=KoruRetainedPremiumDiscoveryAuthorityFailureV1(
                KoruRetainedPremiumDiscoveryAuthorityFailureCodeV1.SOURCE_PROJECTION_INVALID, "source_inputs"
            )
        )
    if source_outcome.result is None:
        return KoruRetainedPremiumDiscoveryAuthorityOutcomeV1(
            failure=KoruRetainedPremiumDiscoveryAuthorityFailureV1(
                KoruRetainedPremiumDiscoveryAuthorityFailureCodeV1.SOURCE_PROJECTION_INVALID, "source_projection"
            )
        )
    source = source_outcome.result
    try:
        source_authority, source_authority_ref = build_binance_usdm_koru_source_profile_authority_v2(source)
        economics_request = BinanceUsdmKoruTradifiExecutionBundleRequestV2(
            source_projection=source,
            target_result=request.legacy_v2_economics_target_result,
            source_profile_authority_envelope=source_authority,
            source_profile_authority_ref=source_authority_ref,
            profile_composition_request_wire=request.profile_composition_request_wire,
            profile_composition_request_hash=request.profile_composition_request_hash,
            execution_account_id=request.execution_account_id,
            initial_equity=request.initial_equity,
            sleeve_allocation_fraction=request.sleeve_allocation_fraction,
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return KoruRetainedPremiumDiscoveryAuthorityOutcomeV1(
            failure=KoruRetainedPremiumDiscoveryAuthorityFailureV1(
                KoruRetainedPremiumDiscoveryAuthorityFailureCodeV1.LEGACY_ECONOMICS_INVALID, "legacy_v2_economics"
            )
        )
    economics_outcome = build_binance_usdm_koru_tradifi_execution_bundle_v2(economics_request)
    if economics_outcome.result is None:
        return KoruRetainedPremiumDiscoveryAuthorityOutcomeV1(
            failure=KoruRetainedPremiumDiscoveryAuthorityFailureV1(
                KoruRetainedPremiumDiscoveryAuthorityFailureCodeV1.PROFILE_INVALID, "profile"
            )
        )
    economics = economics_outcome.result
    try:
        return KoruRetainedPremiumDiscoveryAuthorityOutcomeV1(
            result=KoruRetainedPremiumDiscoveryAuthorityResultV1(
                request=request,
                source_projection=source,
                source_projection_ref=ArtifactRef(_SOURCE_ARTIFACT_TYPE, _SOURCE_SCHEMA_VERSION, source.fragment_digest),
                source_fragment_digest=source.fragment_digest,
                source_profile_authority_envelope=source_authority,
                source_profile_authority_ref=source_authority_ref,
                legacy_v2_economics_bundle_ref=economics.bundle_ref,
                legacy_v2_economics_bundle_digest=economics.bundle_ref.manifest_hash,
                legacy_v2_economics_result_digest=economics.result_digest,
            )
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return KoruRetainedPremiumDiscoveryAuthorityOutcomeV1(
            failure=KoruRetainedPremiumDiscoveryAuthorityFailureV1(
                KoruRetainedPremiumDiscoveryAuthorityFailureCodeV1.RESULT_INVALID, "result"
            )
        )


def canonical_koru_premium_payload_v1(
    recipe: KoruDirectionalTargetRecipeV1, *, artifact_type: str
) -> dict[str, object]:
    """Return the sole payload accepted for one premium strategy or parameter artifact."""
    if type(recipe) is not KoruDirectionalTargetRecipeV1:
        raise TypeError("recipe must be exact KoruDirectionalTargetRecipeV1")
    if artifact_type not in {"strategy_definition", "strategy_parameter_set"}:
        raise ValueError("artifact_type must be a premium artifact type")
    if recipe.family != "mark_index_premium" or type(recipe.parameters) is not KoruMarkIndexPremiumParametersV1:
        raise ValueError("recipe must be a premium recipe")
    if recipe.instrument_id != _INSTRUMENT or recipe.bar_interval != "1h" or recipe.target_exposure != "0.25":
        raise ValueError("recipe must use the frozen KORU premium scope")
    return {
        "type": f"koru_premium_{artifact_type}_v1",
        "schema_version": _SCHEMA_VERSION,
        "premium_id": recipe.recipe_id,
        "premium_key": recipe.target_stream_key,
        "family": recipe.family,
        "strategy_id": recipe.strategy_id,
        "sleeve_id": recipe.sleeve_id,
        "instrument_id": {"venue": _INSTRUMENT.venue.value, "stable_key": _INSTRUMENT.stable_key},
        "bar_interval": recipe.bar_interval,
        "target_exposure": recipe.target_exposure,
        "entry_premium_bps": recipe.parameters.entry_premium_bps,
        "exit_premium_bps": recipe.parameters.exit_premium_bps,
        "max_hold_hours": recipe.parameters.max_hold_hours,
        "flat_when_inside_band": recipe.parameters.flat_when_inside_band,
    }


@dataclass(frozen=True, slots=True)
class KoruPremiumRecipeAuthorityV1:
    """Exact envelope binding for one V3 premium recipe; no executable publication occurs."""

    recipe: KoruDirectionalTargetRecipeV1
    strategy_definition_envelope: ArtifactEnvelope
    strategy_parameter_set_envelope: ArtifactEnvelope
    strategy_ref: ArtifactRef = field(init=False)
    parameter_ref: ArtifactRef = field(init=False)
    premium_id: str = field(init=False)
    premium_key: str = field(init=False)
    authority_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.recipe) is not KoruDirectionalTargetRecipeV1:
            raise TypeError("recipe must be exact KoruDirectionalTargetRecipeV1")
        if (
            type(self.strategy_definition_envelope) is not ArtifactEnvelope
            or type(self.strategy_parameter_set_envelope) is not ArtifactEnvelope
            or self.strategy_definition_envelope.artifact_type != "strategy_definition"
            or self.strategy_definition_envelope.schema_version != 1
            or self.strategy_parameter_set_envelope.artifact_type != "strategy_parameter_set"
            or self.strategy_parameter_set_envelope.schema_version != 1
        ):
            raise ValueError("premium recipe requires exact strategy_definition@1 and strategy_parameter_set@1 envelopes")
        strategy_ref = ArtifactRef.from_envelope(self.strategy_definition_envelope)
        parameter_ref = ArtifactRef.from_envelope(self.strategy_parameter_set_envelope)
        if self.recipe.strategy_ref != strategy_ref or self.recipe.parameter_ref != parameter_ref:
            raise ValueError("recipe refs must be derived from the supplied envelopes")
        expected_strategy = canonical_koru_premium_payload_v1(self.recipe, artifact_type="strategy_definition")
        expected_parameter = canonical_koru_premium_payload_v1(self.recipe, artifact_type="strategy_parameter_set")
        if (
            not _same(self.strategy_definition_envelope.payload, expected_strategy)
            or not _same(self.strategy_parameter_set_envelope.payload, expected_parameter)
        ):
            raise ValueError("premium envelope payload does not exactly bind the recipe")
        object.__setattr__(self, "strategy_ref", strategy_ref)
        object.__setattr__(self, "parameter_ref", parameter_ref)
        object.__setattr__(self, "premium_id", self.recipe.recipe_id)
        object.__setattr__(self, "premium_key", self.recipe.target_stream_key)
        object.__setattr__(self, "authority_digest", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "koru_premium_recipe_authority_v1",
            "schema_version": _SCHEMA_VERSION,
            "recipe": self.recipe,
            "recipe_digest": self.recipe.recipe_digest,
            "strategy_definition_envelope": self.strategy_definition_envelope,
            "strategy_ref": self.strategy_ref,
            "strategy_parameter_set_envelope": self.strategy_parameter_set_envelope,
            "parameter_ref": self.parameter_ref,
            "premium_id": self.premium_id,
            "premium_key": self.premium_key,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "authority_digest": self.authority_digest}


def build_koru_premium_recipe_authority_v1(
    recipe: KoruDirectionalTargetRecipeV1,
    strategy_definition_envelope: ArtifactEnvelope,
    strategy_parameter_set_envelope: ArtifactEnvelope,
) -> KoruPremiumRecipeAuthorityV1:
    return KoruPremiumRecipeAuthorityV1(recipe, strategy_definition_envelope, strategy_parameter_set_envelope)


@dataclass(frozen=True, slots=True)
class KoruPremiumDiscoveryDeclarationV1:
    """The sealed, ordered four-row premium declaration for the fixed discovery scope."""

    discovery_authority: KoruRetainedPremiumDiscoveryAuthorityResultV1
    recipe_authorities: tuple[KoruPremiumRecipeAuthorityV1, ...]
    scope: KoruDirectionalDiscoveryScopeV1 = field(default_factory=KoruDirectionalDiscoveryScopeV1)
    scope_ref: ArtifactRef = field(init=False)
    source_fragment_digest: str = field(init=False)
    legacy_v2_economics_bundle_ref: MarketBundleRef = field(init=False)
    legacy_v2_economics_result_digest: str = field(init=False)
    declaration_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.discovery_authority) is not KoruRetainedPremiumDiscoveryAuthorityResultV1:
            raise TypeError("discovery_authority must be exact authority result")
        if type(self.recipe_authorities) is not tuple or any(type(value) is not KoruPremiumRecipeAuthorityV1 for value in self.recipe_authorities):
            raise TypeError("recipe_authorities must be an exact authority tuple")
        if type(self.scope) is not KoruDirectionalDiscoveryScopeV1 or self.scope != KoruDirectionalDiscoveryScopeV1():
            raise ValueError("scope must be the fixed premium discovery scope")
        authority = self.discovery_authority
        replay = build_binance_usdm_koru_tradifi_source_projection_v2(
            authority.request.source_projection_request()
        )
        if replay.result is None or not _same(authority.source_projection, replay.result):
            raise ValueError("discovery authority source must exactly replay normalized inputs")
        if not _scope_is_exact(authority.source_projection.request.timeline_window_start, authority.source_projection.request.timeline_window_end_exclusive):
            raise ValueError("discovery authority source must exactly cover the fixed scope")
        ids = tuple(value.premium_id for value in self.recipe_authorities)
        keys = tuple(value.premium_key for value in self.recipe_authorities)
        recipes = tuple(value.recipe for value in self.recipe_authorities)
        if ids != _PREMIUM_IDS or keys != _PREMIUM_IDS or len(recipes) != 4:
            raise ValueError("declaration must contain the four canonical premium rows in order")
        if (
            tuple(recipe.parameters.entry_premium_bps for recipe in recipes) != _ENTRY_BPS
            or any(recipe.parameters.exit_premium_bps != "5" for recipe in recipes)
            or any(recipe.parameters.max_hold_hours != 12 for recipe in recipes)
            or any(recipe.target_exposure != "0.25" for recipe in recipes)
            or any(not recipe.parameters.flat_when_inside_band for recipe in recipes)
        ):
            raise ValueError("premium row thresholds are not canonical")
        refs = tuple(ref for value in self.recipe_authorities for ref in (value.strategy_ref, value.parameter_ref))
        if len(set(refs)) != len(refs):
            raise ValueError("premium rows must have unique envelope refs")
        scope_ref = ArtifactRef("koru_directional_discovery_scope", 1, self.scope.scope_digest)
        object.__setattr__(self, "scope_ref", scope_ref)
        object.__setattr__(self, "source_fragment_digest", authority.source_fragment_digest)
        object.__setattr__(self, "legacy_v2_economics_bundle_ref", authority.legacy_v2_economics_bundle_ref)
        object.__setattr__(self, "legacy_v2_economics_result_digest", authority.legacy_v2_economics_result_digest)
        object.__setattr__(self, "declaration_digest", canonical_sha256(self._body()))

    @property
    def rows(self) -> tuple[KoruPremiumRecipeAuthorityV1, ...]:
        return self.recipe_authorities

    def _body(self) -> dict[str, object]:
        return {
            "type": "koru_premium_discovery_declaration_v1",
            "schema_version": _SCHEMA_VERSION,
            "scope": self.scope,
            "scope_ref": self.scope_ref,
            "source_fragment_digest": self.source_fragment_digest,
            "source_profile_authority_ref": self.discovery_authority.source_profile_authority_ref,
            "legacy_v2_economics_bundle_ref": self.legacy_v2_economics_bundle_ref,
            "legacy_v2_economics_bundle_digest": self.discovery_authority.legacy_v2_economics_bundle_digest,
            "legacy_v2_economics_result_digest": self.legacy_v2_economics_result_digest,
            "legacy_v2_economics_role": self.discovery_authority.legacy_v2_economics_role,
            "rows": self.recipe_authorities,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "declaration_digest": self.declaration_digest}


def build_koru_premium_discovery_declaration_v1(
    discovery_authority: KoruRetainedPremiumDiscoveryAuthorityResultV1,
    recipe_authorities: tuple[KoruPremiumRecipeAuthorityV1, ...],
) -> KoruPremiumDiscoveryDeclarationV1:
    """Create the sealed declaration from ordered authorities, never an intent map."""
    return KoruPremiumDiscoveryDeclarationV1(discovery_authority, recipe_authorities)


__all__ = [
    "KoruPremiumDiscoveryDeclarationV1",
    "KoruPremiumRecipeAuthorityV1",
    "KoruRetainedPremiumDiscoveryAuthorityFailureCodeV1",
    "KoruRetainedPremiumDiscoveryAuthorityFailureV1",
    "KoruRetainedPremiumDiscoveryAuthorityOutcomeV1",
    "KoruRetainedPremiumDiscoveryAuthorityRequestV1",
    "KoruRetainedPremiumDiscoveryAuthorityResultV1",
    "build_koru_premium_discovery_declaration_v1",
    "build_koru_premium_recipe_authority_v1",
    "build_koru_retained_premium_discovery_authority_v1",
    "canonical_koru_premium_payload_v1",
]
