"""Separate single-regime Binance USD-M TradFi profile composition."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from crypto_quant_domain import (
    ArtifactRef,
    CurrencyId,
    InstrumentId,
    Money,
    PricePurpose,
    Quantity,
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
    BinanceUsdmMarginTierResolution,
    BinanceUsdmOrderAdmissionMode,
    BinanceUsdmOrderRuleModel,
    BinanceUsdmOrderRuleResolution,
    BinanceUsdmPricePurposeResolution,
    BinanceUsdmPriceSourceKind,
    BinanceUsdmTradifiInstrumentMetadataModel,
    BinanceUsdmTradifiInstrumentMetadataResolution,
)

from .binance_usdm_profile import BinanceUsdmAccountCapacityEvidence
from .execution import (
    LiquidityRoleFullFillBuilder,
    NextEligibleBarOpenModel,
    NoEligibleBarAction,
)
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
from .slippage import DeterministicBpsSlippageModel, SlippageModelKind
from .timeline import TimelineWindow

_SCHEMA_VERSION = 1
_MODEL_KEY = "crypto.binance_usdm.tradifi.resolved-profile-composition.v1"
_MARKET_KEY = "crypto.binance_usdm.tradifi.v1"
_SIMULATION_KEY = "bar.next_eligible_trade_event.tradifi.v1"
_ACCOUNT_KEY = "binance.usdm.standard-cross.v1"
_DISPATCHER_KEY = "crypto.binance_usdm.tradifi.linear-financial-dispatch.v1"
_POST_ADJUSTMENT_START = UtcInstant(1_784_109_600_000_000_000)
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
_SELECTED_EXECUTION_COVERAGE_KEY = (
    "koru-tradifi-execution_reference-coverage-v2"
)
_RESOLVABLE_DEFERRED = (
    BinanceUsdmDeferredRuleKey.MAX_NUM_ALGO_ORDERS,
    BinanceUsdmDeferredRuleKey.MAX_NUM_ORDERS,
)
_LIMITATIONS = (
    "aggregate_trade_event_represented_by_bar_open_v1",
    "bar_execution_not_matching_engine_parity",
    "conservative_bar_extreme_liquidation_audit_only",
    "development_profile",
    "fee_rounding_parity_unproven",
    "first_retained_trade_full_fill_only",
    "historical_account_and_market_archive_completeness_unproven",
    "post_adjustment_single_unit_regime_only",
    "single_instrument_single_usdt_cross_account_only",
    "taker_liquidity_role_only",
    "automatic_settlement_unsupported",
)
_MARKET_CAPABILITIES = (
    MarketBundleCapability("account.financial-event", 1),
    MarketBundleCapability("bar_open", 1),
    MarketBundleCapability("binance_usdm.funding-publications", 1),
    MarketBundleCapability("binance_usdm.price-purpose-streams", 1),
)
_SIMULATION_CAPABILITIES = (MarketBundleCapability("bar_open", 1),)
_CALENDAR_IDENTITIES = (
    ("xkrx_regular_session_calendar", 1),
    ("arcx_koru_core_session_calendar", 1),
)
_UNIT_REGIME_IDENTITY = (
    "binance_usdm_tradifi_post_adjustment_unit_regime",
    1,
)


class BinanceUsdmTradifiProfileCompositionFailureCode(str, Enum):
    MISSING_TRADIFI_INSTRUMENT_METADATA = "missing_tradifi_instrument_metadata"
    FOREIGN_INSTRUMENT_METADATA = "foreign_instrument_metadata"
    INSTRUMENT_CONTEXT_MISMATCH = "instrument_context_mismatch"
    ACCOUNT_CONTEXT_MISMATCH = "account_context_mismatch"
    CROSS_BAND_COVERAGE_MISMATCH = "cross_band_coverage_mismatch"
    EVIDENCE_NOT_AVAILABLE = "evidence_not_available"
    ORDER_ADMISSION_CLOSED = "order_admission_closed"
    CALENDAR_REF_MISMATCH = "calendar_ref_mismatch"
    UNIT_REGIME_REF_MISMATCH = "unit_regime_ref_mismatch"
    MISSING_PRICE_PURPOSE = "missing_price_purpose"
    MISSING_FUNDING_SOURCE = "missing_funding_source"
    PRICE_PURPOSE_COVERAGE_MISMATCH = "price_purpose_coverage_mismatch"
    FUNDING_CONTEXT_MISMATCH = "funding_context_mismatch"
    SPECIAL_FUNDING_UNSUPPORTED = "special_funding_unsupported"
    MISSING_ACCOUNT_PROFILE = "missing_account_profile"
    ACCOUNT_PROFILE_INVALID = "account_profile_invalid"
    MISSING_ACCOUNT_CAPACITY = "missing_account_capacity"
    ACCOUNT_CAPACITY_INVALID = "account_capacity_invalid"
    ZERO_SLIPPAGE_UNSUPPORTED = "zero_slippage_unsupported"
    SLIPPAGE_APPLICABILITY_MISMATCH = "slippage_applicability_mismatch"
    DEFERRED_ORDER_RULE_UNSUPPORTED = "deferred_order_rule_unsupported"
    COMPONENT_IDENTITY_CONFLICT = "component_identity_conflict"


def _hash(name: str, value: object) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    return value


def _interval_covers(start: UtcInstant, end: UtcInstant, window: TimelineWindow) -> bool:
    return start <= window.data_start and end >= window.end_exclusive


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


def _taker_liquidity_component() -> SimulationComponentRef:
    return _simulation_component(
        SimulationPortType.LIQUIDITY_MODEL,
        "liquidity.first-retained-trade.taker-full-fill.development.v1",
        {
            "builder": "crypto_quant_backtest.execution.LiquidityRoleFullFillBuilder",
            "liquidity_role": "taker",
        },
    )


def _artifact_identity(ref: ArtifactRef) -> tuple[str, int]:
    return ref.artifact_type, ref.schema_version


def _calendar_refs_match(refs: tuple[ArtifactRef, ...]) -> bool:
    return tuple(_artifact_identity(value) for value in refs) == _CALENDAR_IDENTITIES


def _unit_regime_ref_matches(ref: ArtifactRef | None) -> bool:
    return ref is not None and _artifact_identity(ref) == _UNIT_REGIME_IDENTITY


def _pow10(places: int) -> int:
    result = 1
    for _ in range(places):
        result *= 10
    return result


def _decimal_money(value: str) -> Money | None:
    match = _DECIMAL.fullmatch(value)
    if match is None:
        return None
    whole, _, fraction = value.partition(".")
    if len(fraction) > _SCALE.places:
        return None
    try:
        units = int(whole + fraction) * _pow10(8 - len(fraction))
    except ValueError:
        return None
    return Money(units, _SCALE, str(_USDT))


def _money_at_scale(value: Money) -> Money | None:
    if value.currency != str(_USDT) or value.scale.places > _SCALE.places:
        return None
    units = value.units * _pow10(8 - value.scale.places)
    return Money(units, _SCALE, value.currency)


def _slippage_payload(model: DeterministicBpsSlippageModel) -> dict[str, object]:
    return {
        "type": "deterministic_bps_slippage_model_binding",
        "component_ref": model.component_ref,
        "calibration_ref": model.calibration_ref,
        "applicability_envelope": model.applicability_envelope,
        "basis_points_units": model.basis_points_units,
        "basis_points_scale": model.basis_points_scale.places,
        "rounding": model.rounding.value,
        "limitations": tuple(value.value for value in model.limitations),
    }


def _execution_payload(model: NextEligibleBarOpenModel) -> dict[str, object]:
    return {
        "type": "next_eligible_bar_open_model_binding",
        "component_ref": model.component_ref,
        "applicability": model.applicability,
    }


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiProfileCompositionRequest:
    instrument_metadata: (
        BinanceUsdmTradifiInstrumentMetadataResolution
        | BinanceUsdmInstrumentMetadataResolution
        | None
    )
    order_rules: BinanceUsdmOrderRuleResolution | None
    margin_tiers: BinanceUsdmMarginTierResolution | None
    price_purposes: tuple[BinanceUsdmPricePurposeResolution, ...]
    funding_sources: tuple[BinanceUsdmFundingSourceResolution, ...]
    account_profile: BinanceUsdmAccountProfileResolution | None
    account_capacity: BinanceUsdmAccountCapacityEvidence | None
    timeline_window: TimelineWindow
    composed_at: SimulationInstant
    calendar_refs: tuple[ArtifactRef, ...]
    post_adjustment_unit_regime_ref: ArtifactRef | None
    slippage_model: DeterministicBpsSlippageModel
    admitted_maximum_quantity: Quantity
    required_market_state_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.instrument_metadata is not None and type(self.instrument_metadata) not in (
            BinanceUsdmTradifiInstrumentMetadataResolution,
            BinanceUsdmInstrumentMetadataResolution,
        ):
            raise TypeError("instrument_metadata must be exact known Binance resolution or None")
        for name, value, expected in (
            ("order_rules", self.order_rules, BinanceUsdmOrderRuleResolution),
            ("margin_tiers", self.margin_tiers, BinanceUsdmMarginTierResolution),
            ("account_profile", self.account_profile, BinanceUsdmAccountProfileResolution),
            ("account_capacity", self.account_capacity, BinanceUsdmAccountCapacityEvidence),
        ):
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
        if type(self.composed_at) is not SimulationInstant:
            raise TypeError("composed_at must be exact SimulationInstant")
        if type(self.calendar_refs) is not tuple or not all(
            type(value) is ArtifactRef for value in self.calendar_refs
        ):
            raise TypeError("calendar_refs must contain exact ArtifactRefs")
        if self.post_adjustment_unit_regime_ref is not None and type(
            self.post_adjustment_unit_regime_ref
        ) is not ArtifactRef:
            raise TypeError("post_adjustment_unit_regime_ref must be exact ArtifactRef or None")
        if type(self.slippage_model) is not DeterministicBpsSlippageModel:
            raise TypeError("slippage_model must be exact DeterministicBpsSlippageModel")
        if type(self.admitted_maximum_quantity) is not Quantity:
            raise TypeError("admitted_maximum_quantity must be exact Quantity")
        if self.admitted_maximum_quantity.units <= 0:
            raise ValueError("admitted_maximum_quantity must be positive")
        if type(self.required_market_state_keys) is not tuple:
            raise TypeError("required_market_state_keys must be tuple")
        states = tuple(
            sorted(
                _text("required market state key", value)
                for value in self.required_market_state_keys
            )
        )
        if not states or len(states) != len(set(states)):
            raise ValueError("required_market_state_keys must be nonempty and unique")
        object.__setattr__(self, "required_market_state_keys", states)

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_profile_composition_request",
            "schema_version": _SCHEMA_VERSION,
            "instrument_metadata": self.instrument_metadata,
            "order_rules": self.order_rules,
            "margin_tiers": self.margin_tiers,
            "price_purposes": self.price_purposes,
            "funding_sources": self.funding_sources,
            "account_profile": self.account_profile,
            "account_capacity": self.account_capacity,
            "timeline_window": self.timeline_window,
            "composed_at": self.composed_at,
            "calendar_refs": self.calendar_refs,
            "post_adjustment_unit_regime_ref": self.post_adjustment_unit_regime_ref,
            "slippage_model": _slippage_payload(self.slippage_model),
            "admitted_maximum_quantity": self.admitted_maximum_quantity,
            "required_market_state_keys": self.required_market_state_keys,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiMarketSemanticsProfile:
    model_digest: str
    source_manifest_hash: str
    component_manifest: tuple[ProfileComponentRef, ...]
    financial_dispatcher_spec: FinancialDispatcherSpec
    calendar_refs: tuple[ArtifactRef, ArtifactRef]
    post_adjustment_unit_regime_ref: ArtifactRef
    profile_key: str = _MARKET_KEY
    profile_version: int = 1

    def __post_init__(self) -> None:
        _ = _hash("model_digest", self.model_digest)
        _ = _hash("source_manifest_hash", self.source_manifest_hash)
        if type(self.component_manifest) is not tuple or not all(
            type(value) is ProfileComponentRef for value in self.component_manifest
        ):
            raise TypeError("component_manifest must contain exact refs")
        ordered = tuple(sorted(self.component_manifest, key=lambda value: value.port_type.value))
        if (
            len(ordered) != len(ProfilePortType)
            or {value.port_type for value in ordered} != set(ProfilePortType)
        ):
            raise ValueError("market profile must exact-cover ProfilePortType")
        object.__setattr__(self, "component_manifest", ordered)
        if type(self.financial_dispatcher_spec) is not FinancialDispatcherSpec:
            raise TypeError("financial_dispatcher_spec must be exact spec")
        if type(self.calendar_refs) is not tuple or not all(
            type(value) is ArtifactRef for value in self.calendar_refs
        ):
            raise TypeError("calendar_refs must contain exact XKRX and ARCX refs")
        if not _calendar_refs_match(self.calendar_refs):
            raise ValueError("calendar_refs must identify ordered XKRX and ARCX authorities")
        if type(self.post_adjustment_unit_regime_ref) is not ArtifactRef:
            raise TypeError("post_adjustment_unit_regime_ref must be exact ArtifactRef")
        if not _unit_regime_ref_matches(self.post_adjustment_unit_regime_ref):
            raise ValueError("post_adjustment_unit_regime_ref identity mismatch")
        if self.profile_key != _MARKET_KEY or self.profile_version != 1:
            raise ValueError("TradFi market profile identity mismatch")

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_market_semantics_profile",
            "schema_version": _SCHEMA_VERSION,
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
            "model_digest": self.model_digest,
            "source_manifest_hash": self.source_manifest_hash,
            "components": self.component_manifest,
            "financial_dispatcher_spec": self.financial_dispatcher_spec,
            "calendar_refs": self.calendar_refs,
            "post_adjustment_unit_regime_ref": self.post_adjustment_unit_regime_ref,
            "limitations": _LIMITATIONS,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiSimulationProfile:
    model_digest: str
    component_manifest: tuple[SimulationComponentRef, ...]
    execution_model: NextEligibleBarOpenModel
    fill_builder: LiquidityRoleFullFillBuilder
    slippage_model: DeterministicBpsSlippageModel
    profile_key: str = _SIMULATION_KEY
    profile_version: int = 1

    def __post_init__(self) -> None:
        _ = _hash("model_digest", self.model_digest)
        if type(self.component_manifest) is not tuple or not all(
            type(value) is SimulationComponentRef for value in self.component_manifest
        ):
            raise TypeError("component_manifest must contain exact simulation refs")
        ordered = tuple(sorted(self.component_manifest, key=lambda value: value.port_type.value))
        if (
            len(ordered) != len(SimulationPortType)
            or {value.port_type for value in ordered} != set(SimulationPortType)
        ):
            raise ValueError("simulation profile must exact-cover SimulationPortType")
        object.__setattr__(self, "component_manifest", ordered)
        if type(self.execution_model) is not NextEligibleBarOpenModel:
            raise TypeError("execution_model must be exact NextEligibleBarOpenModel")
        if type(self.fill_builder) is not LiquidityRoleFullFillBuilder or self.fill_builder.liquidity_role != "taker":
            raise ValueError("fill_builder must be exact taker LiquidityRoleFullFillBuilder")
        if type(self.slippage_model) is not DeterministicBpsSlippageModel:
            raise TypeError("slippage_model must be exact DeterministicBpsSlippageModel")
        by_port = {value.port_type: value for value in ordered}
        if by_port[SimulationPortType.EXECUTION_MODEL] != self.execution_model.component_ref:
            raise ValueError("execution component does not match execution model")
        if by_port[SimulationPortType.SLIPPAGE_MODEL] != self.slippage_model.component_ref:
            raise ValueError("slippage component does not match slippage model")
        if by_port[SimulationPortType.LIQUIDITY_MODEL] != _taker_liquidity_component():
            raise ValueError("liquidity component does not match taker fill builder")
        if self.profile_key != _SIMULATION_KEY or self.profile_version != 1:
            raise ValueError("TradFi simulation profile identity mismatch")

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_simulation_profile",
            "schema_version": _SCHEMA_VERSION,
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
            "model_digest": self.model_digest,
            "components": self.component_manifest,
            "execution_model": _execution_payload(self.execution_model),
            "fill_builder_identity": {
                "type": "liquidity_role_full_fill_builder_identity",
                "builder": "crypto_quant_backtest.execution.LiquidityRoleFullFillBuilder",
                "liquidity_role": self.fill_builder.liquidity_role,
            },
            "slippage_model": _slippage_payload(self.slippage_model),
            "limitations": _LIMITATIONS,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiExecutionAccountProfile:
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
        _ = _hash("model_digest", self.model_digest)
        _ = _hash("source_manifest_hash", self.source_manifest_hash)
        _ = _text("account_id", self.account_id)
        _ = _text("venue_id", self.venue_id)
        if type(self.account_risk_policy) is not AccountRiskPolicy:
            raise TypeError("account_risk_policy must be exact AccountRiskPolicy")
        _ = _text("account_fee_schedule_key", self.account_fee_schedule_key)
        if self.profile_key != _ACCOUNT_KEY or self.profile_version != 1:
            raise ValueError("TradFi account profile identity mismatch")

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_execution_account_profile",
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


def _instrument_id(request: BinanceUsdmTradifiProfileCompositionRequest) -> InstrumentId | None:
    instrument = request.instrument_metadata
    if not isinstance(instrument, BinanceUsdmTradifiInstrumentMetadataResolution):
        return None
    return instrument.instrument.instrument_id


def _instrument_context_failure(
    request: BinanceUsdmTradifiProfileCompositionRequest,
) -> bool:
    instrument_id = _instrument_id(request)
    if instrument_id is None:
        return False
    order = request.order_rules
    margin = request.margin_tiers
    account = request.account_profile
    order_snapshots = (
        (
            order.active_snapshot,
            *(value.snapshot for value in order.rule_timeline.intervals),
        )
        if order is not None
        else ()
    )
    instruments = (
        *(
            (
                order.query.instrument_metadata.instrument.instrument_id,
                order.query.rule_book.instrument_id,
                *(value.instrument_id for value in order.query.rule_book.bands),
                *(value.instrument_id for value in order.visible_bands),
                order.active_band.instrument_id,
                order.rule_timeline.instrument_id,
                *(value.instrument_id for value in order_snapshots),
                *(value.quantity_lattice.instrument_id for value in order_snapshots),
                *(
                    value.market_quantity_lattice.instrument_id
                    for value in order_snapshots
                    if value.market_quantity_lattice is not None
                ),
                order.limit_quantity_lattice.instrument_id,
                order.market_quantity_lattice.instrument_id,
            )
            if order is not None
            else ()
        ),
        *(
            (
                margin.query.instrument_metadata.instrument.instrument_id,
                margin.query.rule_book.instrument_id,
                *(value.instrument_id for value in margin.query.rule_book.bands),
                *(value.instrument_id for value in margin.visible_bands),
                margin.active_band.instrument_id,
                margin.margin_rule_book.instrument_id,
            )
            if margin is not None
            else ()
        ),
        *(
            (
                account.query.instrument_resolution.instrument.instrument_id,
                account.query.account_profile_book.instrument_id,
                *(
                    value.instrument_id
                    for value in account.query.account_profile_book.bands
                ),
                *(value.instrument_id for value in account.visible_bands),
                account.active_band.instrument_id,
                account.leverage_evidence.instrument_id,
            )
            if account is not None
            else ()
        ),
        *(
            (request.account_capacity.instrument_id,)
            if request.account_capacity
            else ()
        ),
        *(
            value.query.instrument_metadata.instrument.instrument_id
            for value in request.price_purposes
        ),
        *(
            value.query.contract.instrument.instrument_id
            for value in request.funding_sources
        ),
    )
    return any(value != instrument_id for value in instruments) or any(
        (
            value.lower_price_limit is not None
            and value.lower_price_limit.instrument_id != str(instrument_id)
        )
        or (
            value.upper_price_limit is not None
            and value.upper_price_limit.instrument_id != str(instrument_id)
        )
        for value in order_snapshots
    )


def _account_context_failure(
    request: BinanceUsdmTradifiProfileCompositionRequest,
) -> bool:
    account = request.account_profile
    if account is None:
        return False
    book = account.query.account_profile_book
    account_ids = (
        account.query.account_id,
        book.account_id,
        *(value.account_id for value in book.bands),
        *(value.account_id for value in account.visible_bands),
        account.active_band.account_id,
        account.leverage_evidence.account_id,
        *(
            (request.account_capacity.account_id,)
            if request.account_capacity
            else ()
        ),
        *(value.query.application_key.account_id for value in request.funding_sources),
    )
    return any(value != account.account_id for value in account_ids) or any(
        value.scope is not account.account_scope
        for value in (*book.bands, *account.visible_bands, account.active_band)
    )


def _cross_band_failure(request: BinanceUsdmTradifiProfileCompositionRequest) -> bool:
    instrument = request.instrument_metadata
    order = request.order_rules
    margin = request.margin_tiers
    if not isinstance(instrument, BinanceUsdmTradifiInstrumentMetadataResolution):
        return False
    if order is None or margin is None:
        return True
    window = request.timeline_window
    last = UtcInstant(window.end_exclusive.epoch_nanoseconds - 1)
    return not (
        window.data_start >= _POST_ADJUSTMENT_START
        and instrument.listing_interval.contains(window.data_start)
        and instrument.listing_interval.contains(last)
        and instrument.active_revision.effective_from <= window.data_start
        and not any(
            revision.effective_from < window.end_exclusive
            and revision.effective_from > instrument.active_revision.effective_from
            for revision in instrument.visible_revisions
        )
        and _interval_covers(order.active_band.effective_from, order.active_band.effective_to_exclusive, window)
        and _interval_covers(margin.active_band.effective_from, margin.active_band.effective_to_exclusive, window)
    )


def _evidence_unavailable(request: BinanceUsdmTradifiProfileCompositionRequest) -> bool:
    instrument = request.instrument_metadata
    if not isinstance(instrument, BinanceUsdmTradifiInstrumentMetadataResolution):
        return False
    utc_values = [instrument.query.captured_at, instrument.active_revision.available_at]
    simulation_values: list[SimulationInstant] = []
    if request.order_rules is not None:
        utc_values.extend((request.order_rules.query.captured_at, request.order_rules.active_band.available_at))
    if request.margin_tiers is not None:
        simulation_values.extend((request.margin_tiers.query.captured_at, request.margin_tiers.active_band.available_at))
    if request.account_profile is not None:
        simulation_values.extend(
            (
                request.account_profile.query.captured_at,
                request.account_profile.active_band.available_at,
            )
        )
    if request.account_capacity is not None:
        simulation_values.append(request.account_capacity.available_at)
    simulation_values.extend(value.query.captured_at for value in request.price_purposes)
    simulation_values.extend(value.query.captured_at for value in request.funding_sources)
    return any(value > request.composed_at.instant for value in utc_values) or any(
        value > request.composed_at for value in simulation_values
    )


def _purpose_values(request: BinanceUsdmTradifiProfileCompositionRequest) -> tuple[str, ...]:
    return tuple(value.query.price_purpose.value for value in request.price_purposes)


def _price_failure(request: BinanceUsdmTradifiProfileCompositionRequest) -> bool:
    instrument_id = _instrument_id(request)
    if instrument_id is None:
        return False
    window = request.timeline_window
    purposes = _purpose_values(request)

    def has_coverage(value: BinanceUsdmPricePurposeResolution) -> bool:
        selected = tuple(
            coverage
            for coverage in value.active_coverages
            if coverage.coverage_id == _SELECTED_EXECUTION_COVERAGE_KEY
        )
        if selected:
            records = value.visible_source_records
            return (
                value.query.price_purpose is PricePurpose.EXECUTION_REFERENCE
                and len(selected) == 1
                and bool(records)
                and selected[0].source_kind
                is BinanceUsdmPriceSourceKind.AGGREGATE_TRADE
                and selected[0].coverage_from == records[0].trade_at
                and selected[0].coverage_to_exclusive.epoch_nanoseconds
                == records[-1].trade_at.epoch_nanoseconds + 1
            )
        return any(
            coverage.coverage_from <= window.data_start
            and coverage.coverage_to_exclusive >= window.end_exclusive
            for coverage in value.active_coverages
        )

    return (
        tuple(sorted(purposes)) != _REQUIRED_PURPOSES
        or len(purposes) != len(_REQUIRED_PURPOSES)
        or any(
            value.query.instrument_metadata.instrument.instrument_id != instrument_id
            or not has_coverage(value)
            for value in request.price_purposes
        )
    )


def _funding_failure(request: BinanceUsdmTradifiProfileCompositionRequest) -> bool:
    instrument = request.instrument_metadata
    order = request.order_rules
    if not isinstance(instrument, BinanceUsdmTradifiInstrumentMetadataResolution) or order is None:
        return False
    expected_contract = LinearPerpetualContract(
        instrument.instrument,
        order.quantity_scale,
        order.price_scale,
        instrument.contract_metadata.contract_multiplier,
    )
    window = request.timeline_window
    slots = tuple(value.slot_id for value in request.funding_sources)
    return len(set(slots)) != len(slots) or any(
        value.query.contract != expected_contract
        or value.slot_id.instrument_id != instrument.instrument.instrument_id
        or value.slot_id.target_funding_time < window.data_start
        or value.slot_id.target_funding_time >= window.end_exclusive
        or not value.source_coverage.contains(value.slot_id.target_funding_time)
        for value in request.funding_sources
    )


def _has_special_funding(request: BinanceUsdmTradifiProfileCompositionRequest) -> bool:
    window = request.timeline_window
    return any(
        record.rate_type == "Special"
        and window.data_start <= record.funding_time < window.end_exclusive
        for resolution in request.funding_sources
        for record in resolution.query.funding_book.records
    )


def _account_invalid(request: BinanceUsdmTradifiProfileCompositionRequest) -> bool:
    account = request.account_profile
    instrument_id = _instrument_id(request)
    if account is None or instrument_id is None:
        return False
    window = request.timeline_window
    leverage = account.leverage_evidence.selected_leverage
    return (
        account.active_band.instrument_id != instrument_id
        or not _interval_covers(account.active_band.effective_from, account.active_band.effective_to_exclusive, window)
        or account.active_band.available_at > request.composed_at
        or not account.can_trade
        or account.position_mode != "one_way"
        or account.asset_mode != "single_asset"
        or account.margin_type != "CROSSED"
        or account.fee_burn
        or account.reporting_currency_id != _USDT
        or account.fee_currency_id != _USDT
        or leverage.units != leverage.scale.factor
    )


def _capacity_invalid(request: BinanceUsdmTradifiProfileCompositionRequest) -> bool:
    capacity = request.account_capacity
    account = request.account_profile
    order = request.order_rules
    instrument_id = _instrument_id(request)
    if capacity is None or account is None or order is None or instrument_id is None:
        return False
    window = request.timeline_window
    source = order.active_band.source_ref
    return (
        capacity.instrument_id != instrument_id
        or capacity.account_id != account.account_id
        or not _interval_covers(capacity.effective_from, capacity.effective_to_exclusive, window)
        or capacity.available_at > request.composed_at
        or capacity.source_key != source.source_key
        or capacity.source_hash != source.source_hash
        or min(capacity.max_num_orders, capacity.max_num_algo_orders) <= 0
    )


def _slippage_outside(request: BinanceUsdmTradifiProfileCompositionRequest) -> bool:
    instrument_id = _instrument_id(request)
    if instrument_id is None:
        return False
    envelope = request.slippage_model.applicability_envelope
    maximum = envelope.maximum_quantity
    admitted = request.admitted_maximum_quantity
    window = request.timeline_window
    return (
        envelope.instrument_id != instrument_id
        or envelope.valid_from > window.data_start
        or envelope.valid_to_exclusive < window.end_exclusive
        or maximum.instrument_id != admitted.instrument_id
        or maximum.scale != admitted.scale
        or maximum.units < admitted.units
        or not set(request.required_market_state_keys).issubset(
            envelope.allowed_market_state_keys
        )
    )


def _first_failure(
    request: BinanceUsdmTradifiProfileCompositionRequest,
) -> BinanceUsdmTradifiProfileCompositionFailureCode | None:
    if request.instrument_metadata is None:
        return BinanceUsdmTradifiProfileCompositionFailureCode.MISSING_TRADIFI_INSTRUMENT_METADATA
    if not isinstance(
        request.instrument_metadata, BinanceUsdmTradifiInstrumentMetadataResolution
    ):
        return BinanceUsdmTradifiProfileCompositionFailureCode.FOREIGN_INSTRUMENT_METADATA
    if _instrument_context_failure(request):
        return BinanceUsdmTradifiProfileCompositionFailureCode.INSTRUMENT_CONTEXT_MISMATCH
    if _account_context_failure(request):
        return BinanceUsdmTradifiProfileCompositionFailureCode.ACCOUNT_CONTEXT_MISMATCH
    if _cross_band_failure(request):
        return BinanceUsdmTradifiProfileCompositionFailureCode.CROSS_BAND_COVERAGE_MISMATCH
    if _evidence_unavailable(request):
        return BinanceUsdmTradifiProfileCompositionFailureCode.EVIDENCE_NOT_AVAILABLE
    if request.order_rules is not None and request.order_rules.active_band.admission_mode is BinanceUsdmOrderAdmissionMode.CLOSED:
        return BinanceUsdmTradifiProfileCompositionFailureCode.ORDER_ADMISSION_CLOSED
    if not _calendar_refs_match(request.calendar_refs):
        return BinanceUsdmTradifiProfileCompositionFailureCode.CALENDAR_REF_MISMATCH
    if not _unit_regime_ref_matches(request.post_adjustment_unit_regime_ref):
        return BinanceUsdmTradifiProfileCompositionFailureCode.UNIT_REGIME_REF_MISMATCH
    purposes = _purpose_values(request)
    if not purposes or any(value not in purposes for value in _REQUIRED_PURPOSES):
        return BinanceUsdmTradifiProfileCompositionFailureCode.MISSING_PRICE_PURPOSE
    if not request.funding_sources:
        return BinanceUsdmTradifiProfileCompositionFailureCode.MISSING_FUNDING_SOURCE
    if _price_failure(request):
        return BinanceUsdmTradifiProfileCompositionFailureCode.PRICE_PURPOSE_COVERAGE_MISMATCH
    if _funding_failure(request):
        return BinanceUsdmTradifiProfileCompositionFailureCode.FUNDING_CONTEXT_MISMATCH
    if _has_special_funding(request):
        return BinanceUsdmTradifiProfileCompositionFailureCode.SPECIAL_FUNDING_UNSUPPORTED
    if request.account_profile is None:
        return BinanceUsdmTradifiProfileCompositionFailureCode.MISSING_ACCOUNT_PROFILE
    if _account_invalid(request):
        return BinanceUsdmTradifiProfileCompositionFailureCode.ACCOUNT_PROFILE_INVALID
    if request.account_capacity is None:
        return BinanceUsdmTradifiProfileCompositionFailureCode.MISSING_ACCOUNT_CAPACITY
    if _capacity_invalid(request):
        return BinanceUsdmTradifiProfileCompositionFailureCode.ACCOUNT_CAPACITY_INVALID
    slippage = request.slippage_model
    if (
        slippage.component_ref.component_key != SlippageModelKind.DETERMINISTIC_BPS_V1.value
        or slippage.basis_points_units == 0
    ):
        return BinanceUsdmTradifiProfileCompositionFailureCode.ZERO_SLIPPAGE_UNSUPPORTED
    if _slippage_outside(request):
        return BinanceUsdmTradifiProfileCompositionFailureCode.SLIPPAGE_APPLICABILITY_MISMATCH
    if request.order_rules is None or tuple(request.order_rules.active_deferred_rule_keys) != _RESOLVABLE_DEFERRED:
        return BinanceUsdmTradifiProfileCompositionFailureCode.DEFERRED_ORDER_RULE_UNSUPPORTED
    refs: tuple[ProfileComponentRef | SimulationComponentRef, ...] = (
        *_components(request, _model_digest(request)),
        *_simulation_components(request),
    )
    identities: dict[tuple[str, int], str] = {}
    for ref in refs:
        identity = (ref.component_key, ref.component_version)
        previous = identities.setdefault(identity, ref.component_digest)
        if previous != ref.component_digest:
            return BinanceUsdmTradifiProfileCompositionFailureCode.COMPONENT_IDENTITY_CONFLICT
    return None


def _source_manifest(request: BinanceUsdmTradifiProfileCompositionRequest) -> tuple[str, ...]:
    values = (
        *(
            (request.instrument_metadata.resolution_hash,)
            if isinstance(
                request.instrument_metadata,
                BinanceUsdmTradifiInstrumentMetadataResolution,
            )
            else ()
        ),
        *((request.order_rules.resolution_hash,) if request.order_rules is not None else ()),
        *((request.margin_tiers.resolution_hash,) if request.margin_tiers is not None else ()),
        *(value.resolution_hash for value in request.price_purposes),
        *(value.resolution_hash for value in request.funding_sources),
        *((request.account_profile.resolution_hash,) if request.account_profile is not None else ()),
        *((request.account_capacity.evidence_hash,) if request.account_capacity is not None else ()),
        *(value.content_hash for value in request.calendar_refs),
        *(
            (request.post_adjustment_unit_regime_ref.content_hash,)
            if request.post_adjustment_unit_regime_ref is not None
            else ()
        ),
        request.slippage_model.calibration_ref.calibration_digest,
        request.slippage_model.applicability_envelope.envelope_hash,
        canonical_sha256(
            {
                "type": "binance_usdm_tradifi_slippage_admission_binding",
                "schema_version": 1,
                "admitted_maximum_quantity": request.admitted_maximum_quantity,
                "required_market_state_keys": request.required_market_state_keys,
            }
        ),
    )
    return tuple(sorted(values))


def _model_digest(request: BinanceUsdmTradifiProfileCompositionRequest) -> str:
    return canonical_sha256(
        {
            "type": "binance_usdm_tradifi_profile_composition_model",
            "schema_version": _SCHEMA_VERSION,
            "model_key": _MODEL_KEY,
            "model_version": 1,
            "request_hash": request.request_hash,
            "source_manifest": _source_manifest(request),
            "post_adjustment_start": _POST_ADJUSTMENT_START,
            "required_price_purposes": _REQUIRED_PURPOSES,
            "resolved_deferred_rules": tuple(value.value for value in _RESOLVABLE_DEFERRED),
            "liquidity_role": "taker",
            "fill_builder": "crypto_quant_backtest.execution.LiquidityRoleFullFillBuilder",
            "market_key": _MARKET_KEY,
            "simulation_key": _SIMULATION_KEY,
            "account_key": _ACCOUNT_KEY,
            "dispatcher_key": _DISPATCHER_KEY,
            "limitations": _LIMITATIONS,
        }
    )


def _components(
    request: BinanceUsdmTradifiProfileCompositionRequest,
    model_digest: str,
) -> tuple[ProfileComponentRef, ...]:
    account = request.account_profile
    margin = request.margin_tiers
    if account is None or margin is None:
        raise ValueError("components require account and margin authorities")
    refs = request.calendar_refs
    unit_ref = request.post_adjustment_unit_regime_ref
    if len(refs) != 2 or unit_ref is None:
        raise ValueError("components require calendar and unit-regime authorities")
    components = (
        _profile_component(ProfilePortType.SESSION_MODEL, "crypto.binance_usdm.tradifi.dual-calendar-session.v1", {"model_digest": model_digest, "xkrx_regular": refs[0], "arcx_koru_core": refs[1]}),
        BinanceUsdmTradifiInstrumentMetadataModel().component_ref,
        BinanceUsdmOrderRuleModel().component_ref,
        _profile_component(ProfilePortType.FEE_ASSESSMENT_POLICY, "crypto.binance_usdm.tradifi.account-fee-composition.v1", {"model_digest": model_digest, "schedule": account.account_fee_schedule_ref, "liquidity_role": "taker"}),
        account.final_fee_rule_set.tax_policy_ref,
        _profile_component(ProfilePortType.SETTLEMENT_MODEL, "crypto.binance_usdm.tradifi.perpetual-settlement-not-applicable.v1", {"model_digest": model_digest}),
        LinearDerivativeAccounting().component_ref,
        _profile_component(ProfilePortType.FINANCING_MODEL, "crypto.binance_usdm.tradifi.linear-funding-composition.v1", {"model_digest": model_digest, "funding_accounting": LinearFundingAccounting().component_ref, "funding_resolutions": [value.resolution_hash for value in request.funding_sources]}),
        _profile_component(ProfilePortType.MARGIN_MODEL, "crypto.binance_usdm.tradifi.linear-margin-composition.v1", {"model_digest": model_digest, "instrument_margin": LinearInstrumentMarginModel().component_ref, "margin_resolution": margin.resolution_hash}),
        _profile_component(ProfilePortType.LIQUIDATION_RULES, "crypto.binance_usdm.tradifi.conservative-liquidation-rules.v1", {"model_digest": model_digest, "price_resolutions": [value.resolution_hash for value in request.price_purposes if value.query.price_purpose.value == "liquidation"]}),
        _profile_component(ProfilePortType.CORPORATE_ACTION_MODEL, "crypto.binance_usdm.tradifi.post-adjustment-unit-regime.v1", {"model_digest": model_digest, "unit_regime_ref": unit_ref}),
        _profile_component(ProfilePortType.CURRENCY_VALUATION_POLICY, "crypto.binance_usdm.tradifi.usdt-identity-valuation.v1", {"model_digest": model_digest, "currency": _USDT}),
    )
    return tuple(sorted(components, key=lambda value: value.port_type.value))


def _execution_model() -> NextEligibleBarOpenModel:
    return NextEligibleBarOpenModel.create(
        actions=(
            (TimeInForce.DAY, NoEligibleBarAction.EXPIRE),
            (TimeInForce.GTC, NoEligibleBarAction.KEEP_ACTIVE),
            (TimeInForce.IOC, NoEligibleBarAction.EXPIRE),
            (TimeInForce.FOK, NoEligibleBarAction.EXPIRE),
            (TimeInForce.GTX, NoEligibleBarAction.KEEP_ACTIVE),
        )
    )


def _simulation_components(
    request: BinanceUsdmTradifiProfileCompositionRequest,
) -> tuple[SimulationComponentRef, ...]:
    execution = _execution_model()
    slippage = request.slippage_model
    components = (
        execution.component_ref,
        slippage.component_ref,
        _simulation_component(SimulationPortType.LATENCY_MODEL, "latency.zero.development.v1", {"availability": "retained_trade_event_time"}),
        _taker_liquidity_component(),
        ConservativeLinearLiquidationAuditModel().component_ref,
        MarkToMarketCloseoutPolicy().component_ref,
    )
    return tuple(sorted(components, key=lambda value: value.port_type.value))


@dataclass(frozen=True, slots=True)
class _Values:
    model_digest: str
    source_manifest: tuple[str, ...]
    linear_contract: LinearPerpetualContract
    account_risk_policy: AccountRiskPolicy
    market_semantics: BinanceUsdmTradifiMarketSemanticsProfile
    simulation: BinanceUsdmTradifiSimulationProfile
    execution_account: BinanceUsdmTradifiExecutionAccountProfile
    market_registration: MarketSemanticsProfileRegistration
    simulation_registration: SimulationProfileRegistration
    execution_account_registration: ExecutionAccountProfileRegistration
    profile_registry: BacktestProfileRegistry
    financial_dispatcher_spec: FinancialDispatcherSpec


def _values(request: BinanceUsdmTradifiProfileCompositionRequest) -> _Values:
    instrument = request.instrument_metadata
    order = request.order_rules
    margin = request.margin_tiers
    account = request.account_profile
    capacity = request.account_capacity
    unit_ref = request.post_adjustment_unit_regime_ref
    if (
        not isinstance(instrument, BinanceUsdmTradifiInstrumentMetadataResolution)
        or order is None
        or margin is None
        or account is None
        or capacity is None
        or not _calendar_refs_match(request.calendar_refs)
        or unit_ref is None
        or not _unit_regime_ref_matches(unit_ref)
    ):
        raise ValueError("composition values require complete authorities")
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
    simulation_components = _simulation_components(request)
    financing = next(value for value in profile_components if value.port_type is ProfilePortType.FINANCING_MODEL)
    margin_component = next(value for value in profile_components if value.port_type is ProfilePortType.MARGIN_MODEL)
    dispatcher = FinancialDispatcherSpec(
        _DISPATCHER_KEY,
        1,
        canonical_sha256({"model_digest": model_digest, "contract": contract, "risk_policy": policy, "source_manifest": source_manifest}),
        LinearDerivativeAccounting().component_ref,
        financing,
        margin_component,
        ConservativeLinearLiquidationAuditModel().component_ref,
        "crypto.binance_usdm.tradifi.linear-snapshot.v1",
        1,
    )
    calendars = (request.calendar_refs[0], request.calendar_refs[1])
    market = BinanceUsdmTradifiMarketSemanticsProfile(model_digest, source_manifest_hash, profile_components, dispatcher, calendars, unit_ref)
    simulation = BinanceUsdmTradifiSimulationProfile(model_digest, simulation_components, _execution_model(), LiquidityRoleFullFillBuilder("taker"), request.slippage_model)
    execution_account = BinanceUsdmTradifiExecutionAccountProfile(model_digest, source_manifest_hash, account.account_id, instrument.instrument.instrument_id.venue.value, policy, account.account_fee_schedule_ref.schedule_key)
    market_registration = MarketSemanticsProfileRegistration(
        _MARKET_KEY, 1, market.profile_digest, market,
        instrument.instrument.instrument_id.venue.value, _MARKET_CAPABILITIES,
        market.component_manifest, RequestedResultGrade.DEVELOPMENT,
        _LIMITATIONS, False,
    )
    simulation_registration = SimulationProfileRegistration(
        _SIMULATION_KEY, 1, simulation.profile_digest, simulation,
        "bar", (StrategyFamily.PRECOMPUTED_TARGET,), _SIMULATION_CAPABILITIES,
        simulation.component_manifest, RequestedResultGrade.DEVELOPMENT,
        _LIMITATIONS, False,
    )
    account_registration = ExecutionAccountProfileRegistration(
        _ACCOUNT_KEY, 1, execution_account.profile_digest, execution_account,
        account.account_id, instrument.instrument.instrument_id.venue.value,
        "linear_perpetual", "cross_single_asset_one_way", (_USDT,),
        RequestedResultGrade.DEVELOPMENT, _LIMITATIONS, False,
    )
    registry = BacktestProfileRegistry((market_registration,), (simulation_registration,), (account_registration,))
    return _Values(model_digest, source_manifest, contract, policy, market, simulation, execution_account, market_registration, simulation_registration, account_registration, registry, dispatcher)


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiResolvedProfile:
    request: BinanceUsdmTradifiProfileCompositionRequest
    model_key: str
    model_version: int
    model_digest: str
    source_manifest: tuple[str, ...]
    linear_contract: LinearPerpetualContract
    account_risk_policy: AccountRiskPolicy
    market_semantics: BinanceUsdmTradifiMarketSemanticsProfile
    simulation: BinanceUsdmTradifiSimulationProfile
    execution_account: BinanceUsdmTradifiExecutionAccountProfile
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
        if type(self.request) is not BinanceUsdmTradifiProfileCompositionRequest:
            raise TypeError("request must be exact TradFi composition request")
        values = _values(self.request)
        order = self.request.order_rules
        expected = (
            _MODEL_KEY, 1, values.model_digest, values.source_manifest,
            values.linear_contract, values.account_risk_policy, values.market_semantics,
            values.simulation, values.execution_account, values.market_registration,
            values.simulation_registration, values.execution_account_registration,
            values.profile_registry, values.financial_dispatcher_spec,
            tuple(value.value for value in order.active_deferred_rule_keys) if order is not None else (),
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
            raise ValueError("resolved TradFi profile fields do not match composition authority")

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
            "type": "binance_usdm_tradifi_resolved_profile",
            "schema_version": _SCHEMA_VERSION,
            **self._canonical_body(),
            "profile_digest": self.profile_digest,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiProfileCompositionFailure:
    request: BinanceUsdmTradifiProfileCompositionRequest
    model_digest: str
    code: BinanceUsdmTradifiProfileCompositionFailureCode
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.request) is not BinanceUsdmTradifiProfileCompositionRequest:
            raise TypeError("request must be exact TradFi composition request")
        if type(self.code) is not BinanceUsdmTradifiProfileCompositionFailureCode:
            raise TypeError("code must be exact TradFi composition failure code")
        if self.model_digest != _model_digest(self.request) or self.code is not _first_failure(self.request):
            raise ValueError("failure fields do not match TradFi composition authority")
        if self.subject_ids != (self.code.value, self.request.request_hash):
            raise ValueError("failure subjects do not match TradFi composition authority")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_profile_composition_failure",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "model_digest": self.model_digest,
            "code": self.code.value,
            "subject_ids": self.subject_ids,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiProfileCompositionOutcome:
    request_hash: str
    model_digest: str
    result: BinanceUsdmTradifiResolvedProfile | None
    failure: BinanceUsdmTradifiProfileCompositionFailure | None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one authority")
        authority = self.result if self.result is not None else self.failure
        if authority is None or authority.request.request_hash != self.request_hash or authority.model_digest != self.model_digest:
            raise ValueError("outcome identity mismatch")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_profile_composition_outcome",
            "schema_version": _SCHEMA_VERSION,
            "request_hash": self.request_hash,
            "model_digest": self.model_digest,
            "result": self.result,
            "failure": self.failure,
        }


class BinanceUsdmTradifiProfileComposer:
    def compose(
        self, request: BinanceUsdmTradifiProfileCompositionRequest, /
    ) -> BinanceUsdmTradifiProfileCompositionOutcome:
        if type(request) is not BinanceUsdmTradifiProfileCompositionRequest:
            raise TypeError("request must be exact TradFi composition request")
        code = _first_failure(request)
        model_digest = _model_digest(request)
        if code is not None:
            failure = BinanceUsdmTradifiProfileCompositionFailure(
                request, model_digest, code, (code.value, request.request_hash)
            )
            return BinanceUsdmTradifiProfileCompositionOutcome(
                request.request_hash, model_digest, None, failure
            )
        values = _values(request)
        order = request.order_rules
        if order is None:
            raise ValueError("successful composition requires order rules")
        result = BinanceUsdmTradifiResolvedProfile(
            request, _MODEL_KEY, 1, values.model_digest, values.source_manifest,
            values.linear_contract, values.account_risk_policy, values.market_semantics,
            values.simulation, values.execution_account, values.market_registration,
            values.simulation_registration, values.execution_account_registration,
            values.profile_registry, values.financial_dispatcher_spec,
            tuple(value.value for value in order.active_deferred_rule_keys),
            tuple(value.value for value in _RESOLVABLE_DEFERRED),
            _LIMITATIONS, False, False,
        )
        return BinanceUsdmTradifiProfileCompositionOutcome(
            request.request_hash, model_digest, result, None
        )
