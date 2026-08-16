from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    Money,
    Scale,
    SimulationInstant,
    TimeInForce,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability
from crypto_quant_trading import (
    AccountRiskPolicy,
    ExposureCapacityLimit,
    FeeReserveFundingSource,
    LinearDerivativeAccounting,
    LinearFundingAccounting,
    LinearInstrumentMarginModel,
    LinearPerpetualContract,
    ProfileComponentRef,
    ProfilePortType,
)
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmAccountProfileResolution,
    BinanceUsdmDeferredRuleKey,
    BinanceUsdmFundingSourceResolution,
    BinanceUsdmInstrumentMetadataResolution,
    BinanceUsdmInstrumentModel,
    BinanceUsdmMarginTierResolution,
    BinanceUsdmOrderAdmissionMode,
    BinanceUsdmOrderRuleModel,
    BinanceUsdmOrderRuleResolution,
    BinanceUsdmPricePurposeResolution,
)

from .execution import NextEligibleBarOpenModel, NoEligibleBarAction
from .financial_dispatch import FinancialDispatcherSpec
from .liquidation_audit import ConservativeLinearLiquidationAuditModel
from .ports import SimulationComponentRef, SimulationPortType
from .resolution import (
    BacktestProfileRegistry,
    ExecutionAccountProfileRegistration,
    MarketSemanticsProfileRegistration,
    RequestedResultGrade,
    SimulationProfileRegistration,
    StrategyFamily,
)
from .run_end import MarkToMarketCloseoutPolicy
from .timeline import TimelineWindow

_SCHEMA_VERSION = 1
_MODEL_KEY = "crypto.binance_usdm.resolved-profile-composition.v1"
_MODEL_VERSION = 1
_MARKET_KEY = "crypto.binance_usdm.v1"
_SIMULATION_KEY = "bar.next_eligible_open.conservative.v1"
_EXECUTABLE_SIMULATION_KEY = "bar.next_eligible_open.conservative.v2"
_ACCOUNT_KEY = "binance.usdm.standard-cross.v1"
_DISPATCHER_KEY = "crypto.binance_usdm.linear-financial-dispatch.v1"
_USDT = CurrencyId("USDT")
_SCALE = Scale(8)
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.([0-9]{1,18}))?")
_REQUIRED_PURPOSES = (
    "execution_reference",
    "liquidation",
    "margin",
    "valuation",
)
_RESOLVABLE_DEFERRED = (
    BinanceUsdmDeferredRuleKey.MAX_NUM_ALGO_ORDERS,
    BinanceUsdmDeferredRuleKey.MAX_NUM_ORDERS,
)
_LIMITATIONS = (
    "bar_execution_not_matching_engine_parity",
    "conservative_bar_extreme_liquidation_audit_only",
    "development_profile",
    "fee_rounding_parity_unproven",
    "historical_account_and_market_archive_completeness_unproven",
    "single_instrument_single_usdt_cross_account_only",
    "single_order_capacity_conservatively_collapses_binance_counters",
    "automatic_settlement_unsupported",
)
_MARKET_CAPABILITIES = (
    MarketBundleCapability("account.financial-event", 1),
    MarketBundleCapability("bar_open", 1),
    MarketBundleCapability("binance_usdm.funding-publications", 1),
    MarketBundleCapability("binance_usdm.price-purpose-streams", 1),
)
_SIMULATION_CAPABILITIES = (MarketBundleCapability("bar_open", 1),)


class BinanceUsdmProfileCompositionFailureCode(str, Enum):
    MISSING_INSTRUMENT_METADATA = "missing_instrument_metadata"
    MISSING_ORDER_RULES = "missing_order_rules"
    MISSING_MARGIN_TIERS = "missing_margin_tiers"
    MISSING_ACCOUNT_PROFILE = "missing_account_profile"
    MISSING_ACCOUNT_CAPACITY = "missing_account_capacity"
    MISSING_PRICE_PURPOSE = "missing_price_purpose"
    MISSING_FUNDING_SOURCE = "missing_funding_source"
    INSTRUMENT_CONTEXT_MISMATCH = "instrument_context_mismatch"
    ACCOUNT_CONTEXT_MISMATCH = "account_context_mismatch"
    TIMELINE_COVERAGE_MISMATCH = "timeline_coverage_mismatch"
    EVIDENCE_NOT_AVAILABLE = "evidence_not_available"
    ORDER_ADMISSION_CLOSED = "order_admission_closed"
    DEFERRED_ORDER_RULE_UNSUPPORTED = "deferred_order_rule_unsupported"
    ORDER_CAPACITY_SOURCE_MISMATCH = "order_capacity_source_mismatch"
    ORDER_CAPACITY_UNREPRESENTABLE = "order_capacity_unrepresentable"
    EXPOSURE_CAPACITY_INVALID = "exposure_capacity_invalid"
    PRICE_PURPOSE_COVERAGE_MISMATCH = "price_purpose_coverage_mismatch"
    FUNDING_CONTEXT_MISMATCH = "funding_context_mismatch"
    COMPONENT_IDENTITY_CONFLICT = "component_identity_conflict"


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    return value


def _hash(name: str, value: object) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _sim(name: str, value: object) -> SimulationInstant:
    if type(value) is not SimulationInstant:
        raise TypeError(f"{name} must be exact SimulationInstant")
    return value


@dataclass(frozen=True, slots=True)
class BinanceUsdmAccountCapacityEvidence:
    evidence_key: str
    evidence_version: int
    account_id: str
    instrument_id: InstrumentId
    effective_from: UtcInstant
    effective_to_exclusive: UtcInstant
    available_at: SimulationInstant
    max_num_orders: int
    max_num_algo_orders: int
    source_key: str
    source_hash: str
    revision_id: str

    def __post_init__(self) -> None:
        _text("evidence_key", self.evidence_key)
        if type(self.evidence_version) is not int or self.evidence_version <= 0:
            raise ValueError("evidence_version must be positive")
        _text("account_id", self.account_id)
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        if type(self.effective_from) is not UtcInstant or type(
            self.effective_to_exclusive
        ) is not UtcInstant:
            raise TypeError("capacity interval must use exact UtcInstant")
        if self.effective_to_exclusive <= self.effective_from:
            raise ValueError("capacity interval must be finite and non-empty")
        _sim("available_at", self.available_at)
        for name in ("max_num_orders", "max_num_algo_orders"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be positive integer")
        _text("source_key", self.source_key)
        _hash("source_hash", self.source_hash)
        _text("revision_id", self.revision_id)

    @property
    def evidence_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_account_capacity_evidence",
            "schema_version": _SCHEMA_VERSION,
            "evidence_key": self.evidence_key,
            "evidence_version": self.evidence_version,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "effective_from": self.effective_from,
            "effective_to_exclusive": self.effective_to_exclusive,
            "available_at": self.available_at,
            "max_num_orders": self.max_num_orders,
            "max_num_algo_orders": self.max_num_algo_orders,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
            "revision_id": self.revision_id,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmProfileCompositionRequest:
    instrument_metadata: BinanceUsdmInstrumentMetadataResolution | None
    order_rules: BinanceUsdmOrderRuleResolution | None
    margin_tiers: BinanceUsdmMarginTierResolution | None
    price_purposes: tuple[BinanceUsdmPricePurposeResolution, ...]
    funding_sources: tuple[BinanceUsdmFundingSourceResolution, ...]
    account_profile: BinanceUsdmAccountProfileResolution | None
    account_capacity: BinanceUsdmAccountCapacityEvidence | None
    timeline_window: TimelineWindow
    composed_at: SimulationInstant

    def __post_init__(self) -> None:
        optional_types = (
            ("instrument_metadata", self.instrument_metadata, BinanceUsdmInstrumentMetadataResolution),
            ("order_rules", self.order_rules, BinanceUsdmOrderRuleResolution),
            ("margin_tiers", self.margin_tiers, BinanceUsdmMarginTierResolution),
            ("account_profile", self.account_profile, BinanceUsdmAccountProfileResolution),
            ("account_capacity", self.account_capacity, BinanceUsdmAccountCapacityEvidence),
        )
        for name, value, expected in optional_types:
            if value is not None and type(value) is not expected:
                raise TypeError(f"{name} must be exact {expected.__name__} or None")
        if type(self.price_purposes) is not tuple or not all(
            type(value) is BinanceUsdmPricePurposeResolution
            for value in self.price_purposes
        ):
            raise TypeError("price_purposes must contain exact resolutions")
        if type(self.funding_sources) is not tuple or not all(
            type(value) is BinanceUsdmFundingSourceResolution
            for value in self.funding_sources
        ):
            raise TypeError("funding_sources must contain exact resolutions")
        object.__setattr__(
            self,
            "price_purposes",
            tuple(
                sorted(
                    self.price_purposes,
                    key=lambda value: (
                        value.query.price_purpose.value,
                        value.query.requested_at,
                        value.resolution_hash,
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "funding_sources",
            tuple(
                sorted(
                    self.funding_sources,
                    key=lambda value: (
                        value.slot_id.target_funding_time,
                        value.resolution_hash,
                    ),
                )
            ),
        )
        if type(self.timeline_window) is not TimelineWindow:
            raise TypeError("timeline_window must be exact TimelineWindow")
        _sim("composed_at", self.composed_at)

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_profile_composition_request",
            "schema_version": _SCHEMA_VERSION,
            "instrument_metadata": self.instrument_metadata,
            "order_rules": self.order_rules,
            "margin_tiers": self.margin_tiers,
            "price_purposes": list(self.price_purposes),
            "funding_sources": list(self.funding_sources),
            "account_profile": self.account_profile,
            "account_capacity": self.account_capacity,
            "timeline_window": self.timeline_window,
            "composed_at": self.composed_at,
        }


def _profile_component(
    port_type: ProfilePortType,
    key: str,
    payload: object,
) -> ProfileComponentRef:
    return ProfileComponentRef(port_type, key, 1, canonical_sha256(payload))


def _simulation_component(
    port_type: SimulationPortType,
    key: str,
    payload: object,
) -> SimulationComponentRef:
    return SimulationComponentRef(port_type, key, 1, canonical_sha256(payload))


@dataclass(frozen=True, slots=True)
class BinanceUsdmMarketSemanticsProfile:
    model_digest: str
    source_manifest_hash: str
    component_manifest: tuple[ProfileComponentRef, ...]
    financial_dispatcher_spec: FinancialDispatcherSpec
    profile_key: str = _MARKET_KEY
    profile_version: int = 1

    def __post_init__(self) -> None:
        _hash("model_digest", self.model_digest)
        _hash("source_manifest_hash", self.source_manifest_hash)
        if type(self.component_manifest) is not tuple or not all(
            type(value) is ProfileComponentRef for value in self.component_manifest
        ):
            raise TypeError("component_manifest must contain exact refs")
        ordered = tuple(sorted(self.component_manifest, key=lambda value: value.port_type.value))
        if {value.port_type for value in ordered} != set(ProfilePortType):
            raise ValueError("market profile must exact-cover ProfilePortType")
        object.__setattr__(self, "component_manifest", ordered)
        if type(self.financial_dispatcher_spec) is not FinancialDispatcherSpec:
            raise TypeError("financial_dispatcher_spec must be exact spec")
        if self.profile_key != _MARKET_KEY or self.profile_version != 1:
            raise ValueError("market profile identity mismatch")

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_market_semantics_profile",
            "schema_version": _SCHEMA_VERSION,
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
            "model_digest": self.model_digest,
            "source_manifest_hash": self.source_manifest_hash,
            "components": self.component_manifest,
            "financial_dispatcher_spec": self.financial_dispatcher_spec,
            "limitations": _LIMITATIONS,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmSimulationProfile:
    model_digest: str
    component_manifest: tuple[SimulationComponentRef, ...]
    profile_key: str = _SIMULATION_KEY
    profile_version: int = 1

    def __post_init__(self) -> None:
        _hash("model_digest", self.model_digest)
        if type(self.component_manifest) is not tuple or not all(
            type(value) is SimulationComponentRef for value in self.component_manifest
        ):
            raise TypeError("component_manifest must contain exact simulation refs")
        ordered = tuple(sorted(self.component_manifest, key=lambda value: value.port_type.value))
        if {value.port_type for value in ordered} != set(SimulationPortType):
            raise ValueError("simulation profile must exact-cover SimulationPortType")
        object.__setattr__(self, "component_manifest", ordered)
        if self.profile_key != _SIMULATION_KEY or self.profile_version != 1:
            raise ValueError("simulation profile identity mismatch")

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_simulation_profile",
            "schema_version": _SCHEMA_VERSION,
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
            "model_digest": self.model_digest,
            "components": self.component_manifest,
            "limitations": _LIMITATIONS,
        }


@dataclass(frozen=True, slots=True)
class _BinanceUsdmExecutableSimulationProfile:
    model_digest: str
    component_manifest: tuple[SimulationComponentRef, ...]
    profile_key: str = _EXECUTABLE_SIMULATION_KEY
    profile_version: int = 2

    def __post_init__(self) -> None:
        _hash("model_digest", self.model_digest)
        if type(self.component_manifest) is not tuple or not all(
            type(value) is SimulationComponentRef for value in self.component_manifest
        ):
            raise TypeError("component_manifest must contain exact simulation refs")
        ordered = tuple(
            sorted(self.component_manifest, key=lambda value: value.port_type.value)
        )
        if {value.port_type for value in ordered} != set(SimulationPortType):
            raise ValueError("simulation profile must exact-cover SimulationPortType")
        object.__setattr__(self, "component_manifest", ordered)
        if (
            self.profile_key != _EXECUTABLE_SIMULATION_KEY
            or self.profile_version != 2
        ):
            raise ValueError("executable simulation profile identity mismatch")

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_simulation_profile",
            "schema_version": _SCHEMA_VERSION,
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
            "model_digest": self.model_digest,
            "components": self.component_manifest,
            "limitations": _LIMITATIONS,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmExecutionAccountProfile:
    model_digest: str
    source_manifest_hash: str
    account_id: str
    venue_id: str
    account_risk_policy: AccountRiskPolicy
    account_fee_schedule_key: str
    profile_key: str = _ACCOUNT_KEY
    profile_version: int = 1
    account_type: str = "linear_perpetual"
    margin_mode: str = "cross_single_asset_one_way"

    def __post_init__(self) -> None:
        _hash("model_digest", self.model_digest)
        _hash("source_manifest_hash", self.source_manifest_hash)
        _text("account_id", self.account_id)
        _text("venue_id", self.venue_id)
        if type(self.account_risk_policy) is not AccountRiskPolicy:
            raise TypeError("account_risk_policy must be exact AccountRiskPolicy")
        _text("account_fee_schedule_key", self.account_fee_schedule_key)
        if self.profile_key != _ACCOUNT_KEY or self.profile_version != 1:
            raise ValueError("account profile identity mismatch")

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_execution_account_profile",
            "schema_version": _SCHEMA_VERSION,
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
            "model_digest": self.model_digest,
            "source_manifest_hash": self.source_manifest_hash,
            "account_id": self.account_id,
            "venue_id": self.venue_id,
            "account_type": self.account_type,
            "margin_mode": self.margin_mode,
            "account_risk_policy": self.account_risk_policy,
            "account_fee_schedule_key": self.account_fee_schedule_key,
            "limitations": _LIMITATIONS,
        }


def _interval_covers(start: UtcInstant, end: UtcInstant, window: TimelineWindow) -> bool:
    return start <= window.data_start and end >= window.end_exclusive


def _decimal_money(value: str) -> Money | None:
    match = _DECIMAL.fullmatch(value)
    if match is None:
        return None
    whole, dot, fraction = value.partition(".")
    if len(fraction) > _SCALE.places:
        return None
    try:
        units = int(whole + fraction) * (10 ** (_SCALE.places - len(fraction)))
    except ValueError:
        return None
    return Money(units, _SCALE, str(_USDT))


def _money_at_scale(value: Money) -> Money | None:
    if value.currency != str(_USDT) or value.scale.places > _SCALE.places:
        return None
    return Money(
        value.units * 10 ** (_SCALE.places - value.scale.places),
        _SCALE,
        value.currency,
    )


def _first_failure(request: BinanceUsdmProfileCompositionRequest) -> BinanceUsdmProfileCompositionFailureCode | None:
    if request.instrument_metadata is None:
        return BinanceUsdmProfileCompositionFailureCode.MISSING_INSTRUMENT_METADATA
    if request.order_rules is None:
        return BinanceUsdmProfileCompositionFailureCode.MISSING_ORDER_RULES
    if request.margin_tiers is None:
        return BinanceUsdmProfileCompositionFailureCode.MISSING_MARGIN_TIERS
    if request.account_profile is None:
        return BinanceUsdmProfileCompositionFailureCode.MISSING_ACCOUNT_PROFILE
    if request.account_capacity is None:
        return BinanceUsdmProfileCompositionFailureCode.MISSING_ACCOUNT_CAPACITY
    purpose_values = tuple(
        value.query.price_purpose.value for value in request.price_purposes
    )
    if not purpose_values or any(value not in purpose_values for value in _REQUIRED_PURPOSES):
        return BinanceUsdmProfileCompositionFailureCode.MISSING_PRICE_PURPOSE
    if not request.funding_sources:
        return BinanceUsdmProfileCompositionFailureCode.MISSING_FUNDING_SOURCE

    instrument_id = request.instrument_metadata.instrument.instrument_id
    instruments = (
        request.order_rules.active_band.instrument_id,
        request.margin_tiers.active_band.instrument_id,
        request.account_profile.active_band.instrument_id,
        request.account_capacity.instrument_id,
        *(value.query.instrument_metadata.instrument.instrument_id for value in request.price_purposes),
        *(value.query.contract.instrument.instrument_id for value in request.funding_sources),
    )
    if any(value != instrument_id for value in instruments):
        return BinanceUsdmProfileCompositionFailureCode.INSTRUMENT_CONTEXT_MISMATCH
    if request.account_capacity.account_id != request.account_profile.account_id or any(
        value.query.application_key.account_id != request.account_profile.account_id
        for value in request.funding_sources
    ):
        return BinanceUsdmProfileCompositionFailureCode.ACCOUNT_CONTEXT_MISMATCH

    window = request.timeline_window
    if not (
        request.instrument_metadata.listing_interval.contains(window.data_start)
        and request.instrument_metadata.listing_interval.contains(UtcInstant(window.end_exclusive.epoch_nanoseconds - 1))
        and _interval_covers(request.order_rules.active_band.effective_from, request.order_rules.active_band.effective_to_exclusive, window)
        and _interval_covers(request.margin_tiers.active_band.effective_from, request.margin_tiers.active_band.effective_to_exclusive, window)
        and _interval_covers(request.account_profile.active_band.effective_from, request.account_profile.active_band.effective_to_exclusive, window)
        and _interval_covers(request.account_capacity.effective_from, request.account_capacity.effective_to_exclusive, window)
    ):
        return BinanceUsdmProfileCompositionFailureCode.TIMELINE_COVERAGE_MISMATCH
    utc_availability = (
        request.instrument_metadata.query.captured_at,
        request.instrument_metadata.active_revision.available_at,
        request.order_rules.query.captured_at,
        request.order_rules.active_band.available_at,
    )
    simulation_availability = (
        request.margin_tiers.query.captured_at,
        request.margin_tiers.active_band.available_at,
        request.account_profile.query.captured_at,
        request.account_profile.active_band.available_at,
        request.account_capacity.available_at,
        *(value.query.captured_at for value in request.price_purposes),
        *(value.query.captured_at for value in request.funding_sources),
    )
    if any(value > request.composed_at.instant for value in utc_availability) or any(
        value > request.composed_at for value in simulation_availability
    ):
        return BinanceUsdmProfileCompositionFailureCode.EVIDENCE_NOT_AVAILABLE
    if request.order_rules.active_band.admission_mode is BinanceUsdmOrderAdmissionMode.CLOSED:
        return BinanceUsdmProfileCompositionFailureCode.ORDER_ADMISSION_CLOSED
    deferred = request.order_rules.active_deferred_rule_keys
    if tuple(deferred) != _RESOLVABLE_DEFERRED:
        return BinanceUsdmProfileCompositionFailureCode.DEFERRED_ORDER_RULE_UNSUPPORTED
    source = request.order_rules.active_band.source_ref
    if request.account_capacity.source_key != source.source_key or request.account_capacity.source_hash != source.source_hash:
        return BinanceUsdmProfileCompositionFailureCode.ORDER_CAPACITY_SOURCE_MISMATCH
    if min(request.account_capacity.max_num_orders, request.account_capacity.max_num_algo_orders) <= 0:
        return BinanceUsdmProfileCompositionFailureCode.ORDER_CAPACITY_UNREPRESENTABLE
    account_max = _decimal_money(request.account_profile.active_band.max_notional_value)
    tier_max = _money_at_scale(request.margin_tiers.finite_terminal_notional_cap)
    if account_max is None or tier_max is None or min(account_max.units, tier_max.units) <= 0:
        return BinanceUsdmProfileCompositionFailureCode.EXPOSURE_CAPACITY_INVALID
    if tuple(sorted(purpose_values)) != _REQUIRED_PURPOSES or len(purpose_values) != len(_REQUIRED_PURPOSES):
        return BinanceUsdmProfileCompositionFailureCode.PRICE_PURPOSE_COVERAGE_MISMATCH
    for value in request.price_purposes:
        if not any(
            coverage.coverage_from <= window.data_start
            and coverage.coverage_to_exclusive >= window.end_exclusive
            for coverage in value.active_coverages
        ):
            return BinanceUsdmProfileCompositionFailureCode.PRICE_PURPOSE_COVERAGE_MISMATCH
    expected_contract = LinearPerpetualContract(
        request.instrument_metadata.instrument,
        request.order_rules.quantity_scale,
        request.order_rules.price_scale,
        request.instrument_metadata.contract_metadata.contract_multiplier,
    )
    funding_slots = tuple(value.slot_id for value in request.funding_sources)
    if (
        len(set(funding_slots)) != len(funding_slots)
        or any(
            value.slot_id.target_funding_time < window.data_start
            or value.slot_id.target_funding_time >= window.end_exclusive
            or not value.source_coverage.contains(value.slot_id.target_funding_time)
            or value.query.contract != expected_contract
            for value in request.funding_sources
        )
    ):
        return BinanceUsdmProfileCompositionFailureCode.FUNDING_CONTEXT_MISMATCH
    component_refs: tuple[ProfileComponentRef | SimulationComponentRef, ...] = (
        *_components(request, _model_digest(request)),
        *_simulation_components(_model_digest(request)),
    )
    component_identities: dict[tuple[str, int], str] = {}
    for component in component_refs:
        identity = (component.component_key, component.component_version)
        previous = component_identities.setdefault(identity, component.component_digest)
        if previous != component.component_digest:
            return BinanceUsdmProfileCompositionFailureCode.COMPONENT_IDENTITY_CONFLICT
    return None


def _source_manifest(request: BinanceUsdmProfileCompositionRequest) -> tuple[str, ...]:
    optional = (
        request.instrument_metadata,
        request.order_rules,
        request.margin_tiers,
        request.account_profile,
        request.account_capacity,
    )
    values = (
        *(value.resolution_hash for value in optional[:4] if value is not None),
        *(
            (request.account_capacity.evidence_hash,)
            if request.account_capacity is not None
            else ()
        ),
        *(value.resolution_hash for value in request.price_purposes),
        *(value.resolution_hash for value in request.funding_sources),
    )
    return tuple(sorted(values))


def _model_digest(request: BinanceUsdmProfileCompositionRequest) -> str:
    return canonical_sha256(
        {
            "type": "binance_usdm_profile_composition_model",
            "schema_version": _SCHEMA_VERSION,
            "model_key": _MODEL_KEY,
            "model_version": _MODEL_VERSION,
            "request_hash": request.request_hash,
            "source_manifest": _source_manifest(request),
            "required_price_purposes": _REQUIRED_PURPOSES,
            "resolved_deferred_rules": tuple(value.value for value in _RESOLVABLE_DEFERRED),
            "order_capacity": "min(max_num_orders,max_num_algo_orders)",
            "exposure_capacity": "min(account_max_notional,tier_terminal_cap)",
            "market_key": _MARKET_KEY,
            "simulation_key": _SIMULATION_KEY,
            "account_key": _ACCOUNT_KEY,
            "dispatcher_key": _DISPATCHER_KEY,
            "limitations": _LIMITATIONS,
        }
    )


def _components(request: BinanceUsdmProfileCompositionRequest, model_digest: str) -> tuple[ProfileComponentRef, ...]:
    instrument_ref = BinanceUsdmInstrumentModel().component_ref
    order_ref = BinanceUsdmOrderRuleModel().component_ref
    account = request.account_profile
    margin = request.margin_tiers
    if account is None or margin is None:
        raise ValueError("components require account and margin authorities")
    components = (
        _profile_component(ProfilePortType.SESSION_MODEL, "crypto.binance_usdm.utc-continuous-session.development.v1", {"model_digest": model_digest, "availability": "market_bundle"}),
        instrument_ref,
        order_ref,
        _profile_component(ProfilePortType.FEE_ASSESSMENT_POLICY, "crypto.binance_usdm.account-fee-composition.v1", {"model_digest": model_digest, "schedule": account.account_fee_schedule_ref}),
        account.final_fee_rule_set.tax_policy_ref,
        _profile_component(ProfilePortType.SETTLEMENT_MODEL, "crypto.binance_usdm.perpetual-settlement-not-applicable.v1", {"model_digest": model_digest, "policy": "no_automatic_delivery_settlement"}),
        LinearDerivativeAccounting().component_ref,
        _profile_component(ProfilePortType.FINANCING_MODEL, "crypto.binance_usdm.linear-funding-composition.v1", {"model_digest": model_digest, "funding_accounting": LinearFundingAccounting().component_ref, "funding_resolutions": [value.resolution_hash for value in request.funding_sources]}),
        _profile_component(ProfilePortType.MARGIN_MODEL, "crypto.binance_usdm.linear-margin-composition.v1", {"model_digest": model_digest, "instrument_margin": LinearInstrumentMarginModel().component_ref, "margin_resolution": margin.resolution_hash}),
        _profile_component(ProfilePortType.LIQUIDATION_RULES, "crypto.binance_usdm.conservative-liquidation-rules.v1", {"model_digest": model_digest, "price_resolutions": [value.resolution_hash for value in request.price_purposes if value.query.price_purpose.value == "liquidation"]}),
        _profile_component(ProfilePortType.CORPORATE_ACTION_MODEL, "crypto.binance_usdm.corporate-action-not-applicable.v1", {"model_digest": model_digest}),
        _profile_component(ProfilePortType.CURRENCY_VALUATION_POLICY, "crypto.binance_usdm.usdt-identity-valuation.v1", {"model_digest": model_digest, "currency": _USDT}),
    )
    return tuple(sorted(components, key=lambda value: value.port_type.value))


def _simulation_components(model_digest: str) -> tuple[SimulationComponentRef, ...]:
    liquidation = ConservativeLinearLiquidationAuditModel().component_ref
    values = (
        _simulation_component(SimulationPortType.EXECUTION_MODEL, "bar.next-eligible-open.v1", {"model_digest": model_digest}),
        _simulation_component(SimulationPortType.SLIPPAGE_MODEL, "slippage.deterministic-zero-bps.v1", {"model_digest": model_digest, "bps": 0}),
        _simulation_component(SimulationPortType.LATENCY_MODEL, "latency.zero.development.v1", {"model_digest": model_digest}),
        _simulation_component(SimulationPortType.LIQUIDITY_MODEL, "liquidity.next-bar-full-fill.development.v1", {"model_digest": model_digest}),
        liquidation,
        _simulation_component(SimulationPortType.CLOSEOUT_POLICY, "closeout.mark-to-market.v1", {"model_digest": model_digest}),
    )
    return tuple(sorted(values, key=lambda value: value.port_type.value))


def _executable_simulation_components(
    model_digest: str,
    legacy: BinanceUsdmSimulationProfile,
) -> tuple[SimulationComponentRef, ...]:
    execution_model = NextEligibleBarOpenModel.create(
        actions=(
            (TimeInForce.DAY, NoEligibleBarAction.EXPIRE),
            (TimeInForce.GTC, NoEligibleBarAction.KEEP_ACTIVE),
            (TimeInForce.IOC, NoEligibleBarAction.EXPIRE),
            (TimeInForce.FOK, NoEligibleBarAction.EXPIRE),
            (TimeInForce.GTX, NoEligibleBarAction.KEEP_ACTIVE),
        )
    )
    replacements = {
        SimulationPortType.EXECUTION_MODEL: execution_model.component_ref,
        SimulationPortType.SLIPPAGE_MODEL: _simulation_component(
            SimulationPortType.SLIPPAGE_MODEL,
            "zero_slippage.development.v1",
            {
                "model_digest": model_digest,
                "basis_points": 0,
                "limitation": "zero_slippage_development_only",
            },
        ),
        SimulationPortType.CLOSEOUT_POLICY: MarkToMarketCloseoutPolicy().component_ref,
    }
    return tuple(
        sorted(
            (
                replacements.get(value.port_type, value)
                for value in legacy.component_manifest
            ),
            key=lambda value: value.port_type.value,
        )
    )


@dataclass(frozen=True, slots=True)
class _Values:
    model_digest: str
    source_manifest: tuple[str, ...]
    source_manifest_hash: str
    linear_contract: LinearPerpetualContract
    account_risk_policy: AccountRiskPolicy
    market_semantics: BinanceUsdmMarketSemanticsProfile
    simulation: BinanceUsdmSimulationProfile
    execution_account: BinanceUsdmExecutionAccountProfile
    market_registration: MarketSemanticsProfileRegistration
    simulation_registration: SimulationProfileRegistration
    execution_account_registration: ExecutionAccountProfileRegistration
    profile_registry: BacktestProfileRegistry
    financial_dispatcher_spec: FinancialDispatcherSpec


def _values(request: BinanceUsdmProfileCompositionRequest) -> _Values:
    instrument = request.instrument_metadata
    order = request.order_rules
    margin = request.margin_tiers
    account = request.account_profile
    capacity = request.account_capacity
    if any(value is None for value in (instrument, order, margin, account, capacity)):
        raise ValueError("composition values require complete request")
    if instrument is None or order is None or margin is None:
        raise ValueError("composition values require market authorities")
    if account is None or capacity is None:
        raise ValueError("composition values require account authorities")
    model_digest = _model_digest(request)
    source_manifest = _source_manifest(request)
    source_manifest_hash = canonical_sha256(source_manifest)
    contract = LinearPerpetualContract(
        instrument.instrument,
        order.quantity_scale,
        order.price_scale,
        instrument.contract_metadata.contract_multiplier,
    )
    account_max = _decimal_money(account.active_band.max_notional_value)
    tier_max = _money_at_scale(margin.finite_terminal_notional_cap)
    if account_max is None or tier_max is None:
        raise ValueError("validated exposure values are missing")
    exposure = Money(min(account_max.units, tier_max.units), _SCALE, str(_USDT))
    reduce_only_values = (
        (True,)
        if order.active_band.admission_mode is BinanceUsdmOrderAdmissionMode.REDUCE_ONLY
        else (False, True)
    )
    policy = AccountRiskPolicy.create(
        policy_key="binance.usdm.standard-cross.risk.v1",
        policy_version=1,
        account_id=account.account_id,
        venue_id=instrument.instrument.instrument_id.venue,
        allowed_sides=order.active_snapshot.permitted_sides,
        allowed_position_effects=order.active_snapshot.permitted_position_effects,
        allowed_reduce_only_values=reduce_only_values,
        fee_reserve_funding_source=FeeReserveFundingSource.AVAILABLE_MARGIN,
        order_capacity_limit=min(capacity.max_num_orders, capacity.max_num_algo_orders),
        exposure_capacity_limits=(ExposureCapacityLimit(exposure),),
    )
    profile_components = _components(request, model_digest)
    simulation_components = _simulation_components(model_digest)
    financing_component = next(
        value
        for value in profile_components
        if value.port_type is ProfilePortType.FINANCING_MODEL
    )
    margin_component = next(value for value in profile_components if value.port_type is ProfilePortType.MARGIN_MODEL)
    dispatcher = FinancialDispatcherSpec(
        _DISPATCHER_KEY,
        1,
        canonical_sha256({"model_digest": model_digest, "contract": contract, "risk_policy": policy, "source_manifest": source_manifest}),
        LinearDerivativeAccounting().component_ref,
        financing_component,
        margin_component,
        ConservativeLinearLiquidationAuditModel().component_ref,
        "crypto.binance_usdm.linear-snapshot.v1",
        1,
    )
    market_profile = BinanceUsdmMarketSemanticsProfile(model_digest, source_manifest_hash, profile_components, dispatcher)
    simulation_profile = BinanceUsdmSimulationProfile(model_digest, simulation_components)
    account_profile = BinanceUsdmExecutionAccountProfile(
        model_digest,
        source_manifest_hash,
        account.account_id,
        instrument.instrument.instrument_id.venue.value,
        policy,
        account.account_fee_schedule_ref.schedule_key,
    )
    market_registration = MarketSemanticsProfileRegistration(
        _MARKET_KEY, 1, market_profile.profile_digest, market_profile,
        instrument.instrument.instrument_id.venue.value, _MARKET_CAPABILITIES,
        market_profile.component_manifest, RequestedResultGrade.DEVELOPMENT,
        _LIMITATIONS, False,
    )
    simulation_registration = SimulationProfileRegistration(
        _SIMULATION_KEY, 1, simulation_profile.profile_digest, simulation_profile,
        "bar", (StrategyFamily.PRECOMPUTED_TARGET,), _SIMULATION_CAPABILITIES,
        simulation_profile.component_manifest, RequestedResultGrade.DEVELOPMENT,
        _LIMITATIONS, False,
    )
    account_registration = ExecutionAccountProfileRegistration(
        _ACCOUNT_KEY, 1, account_profile.profile_digest, account_profile,
        account.account_id, instrument.instrument.instrument_id.venue.value,
        "linear_perpetual", "cross_single_asset_one_way", (_USDT,),
        RequestedResultGrade.DEVELOPMENT, _LIMITATIONS, False,
    )
    registry = BacktestProfileRegistry((market_registration,), (simulation_registration,), (account_registration,))
    return _Values(model_digest, source_manifest, source_manifest_hash, contract, policy, market_profile, simulation_profile, account_profile, market_registration, simulation_registration, account_registration, registry, dispatcher)


def _executable_simulation_authority(
    values: _Values,
) -> tuple[
    _BinanceUsdmExecutableSimulationProfile,
    SimulationProfileRegistration,
    BacktestProfileRegistry,
]:
    simulation = _BinanceUsdmExecutableSimulationProfile(
        values.model_digest,
        _executable_simulation_components(values.model_digest, values.simulation),
    )
    legacy = values.simulation_registration
    registration = SimulationProfileRegistration(
        simulation.profile_key,
        simulation.profile_version,
        simulation.profile_digest,
        simulation,
        legacy.engine_kind,
        legacy.supported_strategy_families,
        legacy.required_bundle_capabilities,
        simulation.component_manifest,
        legacy.grade,
        legacy.limitations,
        legacy.decision_grade_eligible,
    )
    return (
        simulation,
        registration,
        BacktestProfileRegistry(
            (values.market_registration,),
            (registration,),
            (values.execution_account_registration,),
        ),
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmResolvedProfile:
    request: BinanceUsdmProfileCompositionRequest
    model_key: str
    model_version: int
    model_digest: str
    source_manifest: tuple[str, ...]
    linear_contract: LinearPerpetualContract
    account_risk_policy: AccountRiskPolicy
    market_semantics: BinanceUsdmMarketSemanticsProfile
    simulation: BinanceUsdmSimulationProfile | _BinanceUsdmExecutableSimulationProfile
    execution_account: BinanceUsdmExecutionAccountProfile
    market_registration: MarketSemanticsProfileRegistration
    simulation_registration: SimulationProfileRegistration
    execution_account_registration: ExecutionAccountProfileRegistration
    profile_registry: BacktestProfileRegistry
    financial_dispatcher_spec: FinancialDispatcherSpec
    source_deferred_rule_keys: tuple[str, ...]
    resolved_deferred_rule_keys: tuple[str, ...]
    limitations: tuple[str, ...]
    decision_grade_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        if type(self.request) is not BinanceUsdmProfileCompositionRequest:
            raise TypeError("request must be exact composition request")
        values = _values(self.request)
        simulation: (
            BinanceUsdmSimulationProfile
            | _BinanceUsdmExecutableSimulationProfile
        )
        simulation_registration: SimulationProfileRegistration
        profile_registry: BacktestProfileRegistry
        if type(self.simulation) is BinanceUsdmSimulationProfile:
            simulation = values.simulation
            simulation_registration = values.simulation_registration
            profile_registry = values.profile_registry
        elif type(self.simulation) is _BinanceUsdmExecutableSimulationProfile:
            (
                simulation,
                simulation_registration,
                profile_registry,
            ) = _executable_simulation_authority(values)
        else:
            raise TypeError("simulation must be exact known Binance USDM authority")
        expected = (
            _MODEL_KEY, _MODEL_VERSION, values.model_digest, values.source_manifest,
            values.linear_contract, values.account_risk_policy, values.market_semantics,
            simulation, values.execution_account, values.market_registration,
            simulation_registration, values.execution_account_registration,
            profile_registry, values.financial_dispatcher_spec,
            tuple(
                value.value
                for value in self.request.order_rules.active_deferred_rule_keys
            )
            if self.request.order_rules is not None
            else (),
            tuple(value.value for value in _RESOLVABLE_DEFERRED), _LIMITATIONS, False, False,
        )
        actual = (
            self.model_key, self.model_version, self.model_digest, self.source_manifest,
            self.linear_contract, self.account_risk_policy, self.market_semantics,
            self.simulation, self.execution_account, self.market_registration,
            self.simulation_registration, self.execution_account_registration,
            self.profile_registry, self.financial_dispatcher_spec,
            self.source_deferred_rule_keys, self.resolved_deferred_rule_keys,
            self.limitations, self.decision_grade_eligible, self.deployment_authorized,
        )
        if actual != expected:
            raise ValueError("resolved profile fields do not match composition authority")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "request": self.request,
            "model_key": self.model_key,
            "model_version": self.model_version,
            "model_digest": self.model_digest,
            "source_manifest": self.source_manifest,
            "linear_contract": self.linear_contract,
            "account_risk_policy": self.account_risk_policy,
            "market_semantics": self.market_semantics,
            "simulation": self.simulation,
            "execution_account": self.execution_account,
            "market_registration": self.market_registration,
            "simulation_registration": self.simulation_registration,
            "execution_account_registration": self.execution_account_registration,
            "profile_registry": self.profile_registry,
            "financial_dispatcher_spec": self.financial_dispatcher_spec,
            "source_deferred_rule_keys": self.source_deferred_rule_keys,
            "resolved_deferred_rule_keys": self.resolved_deferred_rule_keys,
            "limitations": self.limitations,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_resolved_profile",
            "schema_version": _SCHEMA_VERSION,
            **self._canonical_body(),
            "profile_digest": self.profile_digest,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmProfileCompositionFailure:
    request: BinanceUsdmProfileCompositionRequest
    model_digest: str
    code: BinanceUsdmProfileCompositionFailureCode
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.request) is not BinanceUsdmProfileCompositionRequest:
            raise TypeError("request must be exact composition request")
        if type(self.code) is not BinanceUsdmProfileCompositionFailureCode:
            raise TypeError("code must be exact composition failure code")
        if self.model_digest != _model_digest(self.request) or self.code is not _first_failure(self.request):
            raise ValueError("failure fields do not match composition authority")
        expected = (self.code.value, self.request.request_hash)
        if self.subject_ids != expected:
            raise ValueError("failure subjects do not match composition authority")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "request": self.request,
            "model_digest": self.model_digest,
            "code": self.code.value,
            "subject_ids": self.subject_ids,
        }

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_profile_composition_failure",
            "schema_version": _SCHEMA_VERSION,
            **self._canonical_body(),
            "failure_hash": self.failure_hash,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmProfileCompositionOutcome:
    request_hash: str
    model_digest: str
    result: BinanceUsdmResolvedProfile | None
    failure: BinanceUsdmProfileCompositionFailure | None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one authority")
        authority = self.result if self.result is not None else self.failure
        if authority is None or authority.request.request_hash != self.request_hash or authority.model_digest != self.model_digest:
            raise ValueError("outcome identity mismatch")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "request_hash": self.request_hash,
            "model_digest": self.model_digest,
            "result": self.result,
            "failure": self.failure,
        }

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_profile_composition_outcome",
            "schema_version": _SCHEMA_VERSION,
            **self._canonical_body(),
            "outcome_hash": self.outcome_hash,
        }


class BinanceUsdmProfileComposer:
    def compose(self, request: BinanceUsdmProfileCompositionRequest, /) -> BinanceUsdmProfileCompositionOutcome:
        if type(request) is not BinanceUsdmProfileCompositionRequest:
            raise TypeError("request must be exact composition request")
        code = _first_failure(request)
        model_digest = _model_digest(request)
        if code is not None:
            failure = BinanceUsdmProfileCompositionFailure(
                request, model_digest, code, (code.value, request.request_hash)
            )
            return BinanceUsdmProfileCompositionOutcome(request.request_hash, model_digest, None, failure)
        values = _values(request)
        if request.order_rules is None:
            raise ValueError("successful composition requires order rules")
        result = BinanceUsdmResolvedProfile(
            request, _MODEL_KEY, _MODEL_VERSION, values.model_digest,
            values.source_manifest, values.linear_contract, values.account_risk_policy,
            values.market_semantics, values.simulation, values.execution_account,
            values.market_registration, values.simulation_registration,
            values.execution_account_registration, values.profile_registry,
            values.financial_dispatcher_spec,
            tuple(value.value for value in request.order_rules.active_deferred_rule_keys),
            tuple(value.value for value in _RESOLVABLE_DEFERRED),
            _LIMITATIONS, False, False,
        )
        return BinanceUsdmProfileCompositionOutcome(request.request_hash, model_digest, result, None)

    def compose_executable(
        self, request: BinanceUsdmProfileCompositionRequest, /
    ) -> BinanceUsdmProfileCompositionOutcome:
        legacy_outcome = self.compose(request)
        legacy = legacy_outcome.result
        if legacy is None:
            return legacy_outcome
        values = _values(request)
        simulation, registration, registry = _executable_simulation_authority(values)
        result = BinanceUsdmResolvedProfile(
            request,
            legacy.model_key,
            legacy.model_version,
            legacy.model_digest,
            legacy.source_manifest,
            legacy.linear_contract,
            legacy.account_risk_policy,
            legacy.market_semantics,
            simulation,
            legacy.execution_account,
            legacy.market_registration,
            registration,
            legacy.execution_account_registration,
            registry,
            legacy.financial_dispatcher_spec,
            legacy.source_deferred_rule_keys,
            legacy.resolved_deferred_rule_keys,
            legacy.limitations,
            legacy.decision_grade_eligible,
            legacy.deployment_authorized,
        )
        return BinanceUsdmProfileCompositionOutcome(
            request.request_hash, legacy.model_digest, result, None
        )
