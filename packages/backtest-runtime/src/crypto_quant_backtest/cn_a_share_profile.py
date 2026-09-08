from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
import re
import unicodedata
from zoneinfo import ZoneInfo

from crypto_quant_domain import (
    CurrencyId,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    OrderSide,
    PositionBalanceKey,
    PositionEffect,
    Scale,
    SimulationInstant,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability
from crypto_quant_trading import (
    AccountRiskPolicy,
    FeeReserveFundingSource,
    ProfileComponentRef,
    ProfilePortType,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashMarketFeePolicy,
    CnAShareCashOrderRuleModel,
    CnAShareCashPaymentRequest,
    CnAShareCashQuantityLatticeModel,
    CnAShareCashSessionModel,
    CnAShareCashSettlementModel,
    CnAShareCashStampDutyTaxPolicy,
    CnAShareCorporateActionEntitlement,
    CnAShareCorporateActionEntitlementModel,
    CnAShareCorporateActionEntitlementRuleBook,
    CnAShareCorporateActionTaxDisposition,
    CnAShareFrozenCalendar,
    CnAShareInstrumentRuleContext,
    CnAShareListingPhase,
    CnAShareMarketFeeRuleBook,
    CnAShareOrderRuleBook,
    CnAShareRiskClass,
    CnAShareShareDeliveryRequest,
    CnAShareStampDutyRuleBook,
)

from .financial_dispatch import (
    FinancialDispatcherSpec,
    default_cash_financial_dispatcher_spec,
)
from .ports import SimulationComponentRef, SimulationPortType
from .resolution import (
    BacktestProfileRegistry,
    ExecutionAccountProfileRegistration,
    MarketSemanticsProfileRegistration,
    RequestedResultGrade,
    SimulationProfileRegistration,
    StrategyFamily,
)
from .timeline import TimelineWindow


_SCHEMA_VERSION = 1
_MODEL_KEY = "equity.cn_a_share.resolved-profile-composition.v1"
_MARKET_KEY = "equity.cn_a_share.v1"
_SIMULATION_KEY = "bar.next_eligible_open.cn_a_share.development.v1"
_ACCOUNT_KEY = "equity.cn_a_share.cash.long-only.v1"
_DISPATCHER_KEY = "equity.cn_a_share.cash-financial-dispatch.v1"
_CNY = CurrencyId("CNY")
_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_LIMITATIONS = (
    "bar_open_full_fill_has_no_queue_volume_or_intrabar_path",
    "caller_supplied_scope_and_revision_closure_not_external_archive_completeness",
    "corporate_action_tax_disposition_not_applicable_only",
    "development_profile",
    "finite_caller_supplied_calendar_rule_fee_and_corporate_action_coverage",
    "margin_short_stock_connect_and_non_cash_account_unsupported",
    "non_ordinary_or_non_standard_cash_auction_equity_unsupported",
    "real_market_profile_qualification_unproven",
    "risk_warning_new_listing_no_daily_limit_and_intraday_halt_unsupported",
    "single_working_order_capacity",
    "xshg_bonus_and_capitalization_unsupported",
    "zero_slippage_development_only",
)
_INHERITED_FIXTURE_HASHES = (
    "ef2ed7296ca9da16791ca7839583b93f151b1425734f53b02dd6e8556c0dd26d",
    "4b66c6ed6594c05de8723f11b69839507ba5991b8b913b6fe32f61d6960ba800",
    "7b6a4e76260955735ea62a81c897dfb11eecc0af89b571143bbfcea244cecd1c",
    "af74733a438d35a6d58712ee8f66f371af87f53dbb2f39692d22eaf5231d817d",
    "3ef26743bc9cebfe546f77812c6773cbdf3353e0337d03ed512d5f1c396f702b",
    "dd489fc4488414f1a3d1d493ea7781952bad707d0c4df839ec8645466c33b011",
    "dfed0880cae559b5c4c0f54c3cd461e0e6008af7eda09a1c57254a2db73747c3",
    "63de3b4dc8f5a674d1d759ac09d868ca505e2dfbdc9707a9a348a939c342faeb",
)


class CnAShareProfileCompositionFailureCode(str, Enum):
    MISSING_INSTRUMENT_SCOPE = "missing_instrument_scope"
    MISSING_ACCOUNT_SCOPE = "missing_account_scope"
    MISSING_ANNOUNCEMENT_REVISION_SET = "missing_announcement_revision_set"
    MISSING_REGISTER_REVISION_SET = "missing_register_revision_set"
    MISSING_IDENTITY_HISTORY = "missing_identity_history"
    INSTRUMENT_SCOPE_MISMATCH = "instrument_scope_mismatch"
    ACCOUNT_SCOPE_MISMATCH = "account_scope_mismatch"
    AUTHORITY_CONTEXT_MISMATCH = "authority_context_mismatch"
    REVISION_CLOSURE_MISMATCH = "revision_closure_mismatch"
    CROSS_QUERY_IDENTITY_CONFLICT = "cross_query_identity_conflict"
    TIMELINE_COVERAGE_MISMATCH = "timeline_coverage_mismatch"
    EVIDENCE_NOT_AVAILABLE = "evidence_not_available"
    UNSUPPORTED_TAX_DISPOSITION = "unsupported_tax_disposition"
    UNSUPPORTED_XSHG_SHARE_DELIVERY = "unsupported_xshg_share_delivery"
    COMPONENT_IDENTITY_CONFLICT = "component_identity_conflict"


def _text(name: str, value: object) -> str:
    if (
        type(value) is not str
        or not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be canonical non-empty text")
    return value


def _hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _interval(start: object, end: object) -> None:
    if type(start) is not UtcInstant or type(end) is not UtcInstant:
        raise TypeError("coverage bounds must be exact UtcInstant")
    if start >= end:
        raise ValueError("coverage interval must be finite and non-empty")


def _availability(value: object) -> None:
    if type(value) is not SimulationInstant:
        raise TypeError("available_at must be exact SimulationInstant")


def _bools(value: object, names: tuple[str, ...]) -> None:
    if any(type(getattr(value, name)) is not bool for name in names):
        raise TypeError("scope flags must be exact bool")


def _revision_chain(value: object) -> None:
    chain = getattr(value, "revision_chain")
    if type(chain) is not tuple:
        raise TypeError("revision_chain must be tuple")
    for row in chain:
        if type(row) is not tuple or len(row) != 3:
            raise TypeError("revision_chain rows must be three-tuples")
        revision_id, parent_id, payload_hash = row
        _text("revision_id", revision_id)
        if parent_id is not None:
            _text("parent_revision_id", parent_id)
        _hash("revision_payload_hash", payload_hash)


def _pairs(name: str, values: object) -> tuple[tuple[str, str], ...]:
    if type(values) is not tuple:
        raise TypeError(f"{name} must be tuple")
    result: list[tuple[str, str]] = []
    for row in values:
        if type(row) is not tuple or len(row) != 2:
            raise TypeError(f"{name} rows must be pairs")
        key, payload_hash = row
        result.append((_text("scoped_identity_key", key), _hash("payload_hash", payload_hash)))
    return tuple(sorted(result))


def _canonical_with_hash(type_name: str, fields: dict[str, object], hash_name: str) -> dict[str, object]:
    body = {"type": type_name, "schema_version": _SCHEMA_VERSION, **fields}
    return {**body, hash_name: canonical_sha256(body)}


@dataclass(frozen=True, slots=True)
class CnAShareInstrumentScopeDeclaration:
    instrument: InstrumentDefinition
    rule_context: CnAShareInstrumentRuleContext
    coverage_from: UtcInstant
    coverage_to_exclusive: UtcInstant
    available_at: SimulationInstant
    is_ordinary_domestic_a_share: bool
    is_standard_cash_auction: bool
    is_b_or_h_share: bool
    is_fund_or_bond: bool
    is_stock_connect: bool
    has_lending_or_repo: bool
    has_pledge_or_freeze: bool
    is_restricted_or_pre_ipo: bool
    has_differential_distribution: bool
    has_issuer_self_distribution: bool
    source_snapshot_hash: str
    source_manifest_hash: str

    def __post_init__(self) -> None:
        if type(self.instrument) is not InstrumentDefinition:
            raise TypeError("instrument must be exact InstrumentDefinition")
        if type(self.rule_context) is not CnAShareInstrumentRuleContext:
            raise TypeError("rule_context must be exact CnAShareInstrumentRuleContext")
        _interval(self.coverage_from, self.coverage_to_exclusive)
        _availability(self.available_at)
        _bools(self, (
            "is_ordinary_domestic_a_share", "is_standard_cash_auction", "is_b_or_h_share",
            "is_fund_or_bond", "is_stock_connect", "has_lending_or_repo",
            "has_pledge_or_freeze", "is_restricted_or_pre_ipo",
            "has_differential_distribution", "has_issuer_self_distribution",
        ))
        _hash("source_snapshot_hash", self.source_snapshot_hash)
        _hash("source_manifest_hash", self.source_manifest_hash)

    def _body(self) -> dict[str, object]:
        return {
            "instrument": self.instrument, "rule_context": self.rule_context,
            "coverage_from": self.coverage_from, "coverage_to_exclusive": self.coverage_to_exclusive,
            "available_at": self.available_at, "is_ordinary_domestic_a_share": self.is_ordinary_domestic_a_share,
            "is_standard_cash_auction": self.is_standard_cash_auction, "is_b_or_h_share": self.is_b_or_h_share,
            "is_fund_or_bond": self.is_fund_or_bond, "is_stock_connect": self.is_stock_connect,
            "has_lending_or_repo": self.has_lending_or_repo, "has_pledge_or_freeze": self.has_pledge_or_freeze,
            "is_restricted_or_pre_ipo": self.is_restricted_or_pre_ipo,
            "has_differential_distribution": self.has_differential_distribution,
            "has_issuer_self_distribution": self.has_issuer_self_distribution,
            "source_snapshot_hash": self.source_snapshot_hash, "source_manifest_hash": self.source_manifest_hash,
        }

    @property
    def declaration_hash(self) -> str:
        return canonical_sha256({"type": "cn_a_share_instrument_scope_declaration", "schema_version": 1, **self._body()})

    def to_canonical_dict(self) -> dict[str, object]:
        return _canonical_with_hash("cn_a_share_instrument_scope_declaration", self._body(), "declaration_hash")


@dataclass(frozen=True, slots=True)
class CnAShareAccountScopeDeclaration:
    account_id: str
    venue_id: VenueId
    coverage_from: UtcInstant
    coverage_to_exclusive: UtcInstant
    available_at: SimulationInstant
    is_cash_account: bool
    is_domestic_access: bool
    has_margin_or_short_permission: bool
    has_stock_connect_permission: bool
    authorizes_available_margin_use: bool
    source_snapshot_hash: str
    source_manifest_hash: str

    def __post_init__(self) -> None:
        _text("account_id", self.account_id)
        if type(self.venue_id) is not VenueId:
            raise TypeError("venue_id must be exact VenueId")
        _interval(self.coverage_from, self.coverage_to_exclusive)
        _availability(self.available_at)
        _bools(self, ("is_cash_account", "is_domestic_access", "has_margin_or_short_permission", "has_stock_connect_permission", "authorizes_available_margin_use"))
        _hash("source_snapshot_hash", self.source_snapshot_hash)
        _hash("source_manifest_hash", self.source_manifest_hash)

    def _body(self) -> dict[str, object]:
        return {
            "account_id": self.account_id, "venue_id": self.venue_id,
            "coverage_from": self.coverage_from, "coverage_to_exclusive": self.coverage_to_exclusive,
            "available_at": self.available_at, "is_cash_account": self.is_cash_account,
            "is_domestic_access": self.is_domestic_access,
            "has_margin_or_short_permission": self.has_margin_or_short_permission,
            "has_stock_connect_permission": self.has_stock_connect_permission,
            "authorizes_available_margin_use": self.authorizes_available_margin_use,
            "source_snapshot_hash": self.source_snapshot_hash, "source_manifest_hash": self.source_manifest_hash,
        }

    @property
    def declaration_hash(self) -> str:
        return canonical_sha256({"type": "cn_a_share_account_scope_declaration", "schema_version": 1, **self._body()})

    def to_canonical_dict(self) -> dict[str, object]:
        return _canonical_with_hash("cn_a_share_account_scope_declaration", self._body(), "declaration_hash")


@dataclass(frozen=True, slots=True)
class CnAShareAnnouncementRevisionSetDeclaration:
    venue_id: VenueId
    instrument_id: InstrumentId
    corporate_action_id: str
    revision_chain: tuple[tuple[str, str | None, str], ...]
    terminal_revision_id: str
    is_cancelled: bool
    coverage_from: UtcInstant
    coverage_to_exclusive: UtcInstant
    available_at: SimulationInstant
    source_snapshot_hash: str
    source_manifest_hash: str

    def __post_init__(self) -> None:
        if type(self.venue_id) is not VenueId or type(self.instrument_id) is not InstrumentId:
            raise TypeError("revision scope identities must use exact domain IDs")
        _text("corporate_action_id", self.corporate_action_id)
        _revision_chain(self)
        _text("terminal_revision_id", self.terminal_revision_id)
        if type(self.is_cancelled) is not bool:
            raise TypeError("is_cancelled must be bool")
        _interval(self.coverage_from, self.coverage_to_exclusive)
        _availability(self.available_at)
        _hash("source_snapshot_hash", self.source_snapshot_hash)
        _hash("source_manifest_hash", self.source_manifest_hash)

    def _body(self) -> dict[str, object]:
        return {
            "venue_id": self.venue_id, "instrument_id": self.instrument_id,
            "corporate_action_id": self.corporate_action_id, "revision_chain": self.revision_chain,
            "terminal_revision_id": self.terminal_revision_id, "is_cancelled": self.is_cancelled,
            "coverage_from": self.coverage_from, "coverage_to_exclusive": self.coverage_to_exclusive,
            "available_at": self.available_at, "source_snapshot_hash": self.source_snapshot_hash,
            "source_manifest_hash": self.source_manifest_hash,
        }

    @property
    def declaration_hash(self) -> str:
        return canonical_sha256({"type": "cn_a_share_announcement_revision_set_declaration", "schema_version": 1, **self._body()})

    def to_canonical_dict(self) -> dict[str, object]:
        return _canonical_with_hash("cn_a_share_announcement_revision_set_declaration", self._body(), "declaration_hash")


@dataclass(frozen=True, slots=True)
class CnAShareRegisterRevisionSetDeclaration:
    account_id: str
    position_key: PositionBalanceKey
    register_series_id: str
    revision_chain: tuple[tuple[str, str | None, str], ...]
    terminal_revision_id: str
    coverage_from: UtcInstant
    coverage_to_exclusive: UtcInstant
    available_at: SimulationInstant
    source_snapshot_hash: str
    source_manifest_hash: str

    def __post_init__(self) -> None:
        _text("account_id", self.account_id)
        if type(self.position_key) is not PositionBalanceKey:
            raise TypeError("position_key must be exact PositionBalanceKey")
        _text("register_series_id", self.register_series_id)
        _revision_chain(self)
        _text("terminal_revision_id", self.terminal_revision_id)
        _interval(self.coverage_from, self.coverage_to_exclusive)
        _availability(self.available_at)
        _hash("source_snapshot_hash", self.source_snapshot_hash)
        _hash("source_manifest_hash", self.source_manifest_hash)

    def _body(self) -> dict[str, object]:
        return {
            "account_id": self.account_id, "position_key": self.position_key,
            "register_series_id": self.register_series_id, "revision_chain": self.revision_chain,
            "terminal_revision_id": self.terminal_revision_id, "coverage_from": self.coverage_from,
            "coverage_to_exclusive": self.coverage_to_exclusive, "available_at": self.available_at,
            "source_snapshot_hash": self.source_snapshot_hash, "source_manifest_hash": self.source_manifest_hash,
        }

    @property
    def declaration_hash(self) -> str:
        return canonical_sha256({"type": "cn_a_share_register_revision_set_declaration", "schema_version": 1, **self._body()})

    def to_canonical_dict(self) -> dict[str, object]:
        return _canonical_with_hash("cn_a_share_register_revision_set_declaration", self._body(), "declaration_hash")


@dataclass(frozen=True, slots=True)
class CnAShareIdentityHistoryDeclaration:
    corporate_action_hashes: tuple[tuple[str, str], ...]
    register_snapshot_hashes: tuple[tuple[str, str], ...]
    register_revision_hashes: tuple[tuple[str, str], ...]
    coverage_from: UtcInstant
    coverage_to_exclusive: UtcInstant
    available_at: SimulationInstant
    source_snapshot_hash: str
    source_manifest_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "corporate_action_hashes", _pairs("corporate_action_hashes", self.corporate_action_hashes))
        object.__setattr__(self, "register_snapshot_hashes", _pairs("register_snapshot_hashes", self.register_snapshot_hashes))
        object.__setattr__(self, "register_revision_hashes", _pairs("register_revision_hashes", self.register_revision_hashes))
        _interval(self.coverage_from, self.coverage_to_exclusive)
        _availability(self.available_at)
        _hash("source_snapshot_hash", self.source_snapshot_hash)
        _hash("source_manifest_hash", self.source_manifest_hash)

    def _body(self) -> dict[str, object]:
        return {
            "corporate_action_hashes": self.corporate_action_hashes,
            "register_snapshot_hashes": self.register_snapshot_hashes,
            "register_revision_hashes": self.register_revision_hashes,
            "coverage_from": self.coverage_from, "coverage_to_exclusive": self.coverage_to_exclusive,
            "available_at": self.available_at, "source_snapshot_hash": self.source_snapshot_hash,
            "source_manifest_hash": self.source_manifest_hash,
        }

    @property
    def declaration_hash(self) -> str:
        return canonical_sha256({"type": "cn_a_share_identity_history_declaration", "schema_version": 1, **self._body()})

    def to_canonical_dict(self) -> dict[str, object]:
        return _canonical_with_hash("cn_a_share_identity_history_declaration", self._body(), "declaration_hash")


@dataclass(frozen=True, slots=True)
class CnAShareProfileCompositionRequest:
    instrument_scope: CnAShareInstrumentScopeDeclaration | None
    account_scope: CnAShareAccountScopeDeclaration | None
    announcement_revision_set: CnAShareAnnouncementRevisionSetDeclaration | None
    register_revision_set: CnAShareRegisterRevisionSetDeclaration | None
    identity_history: CnAShareIdentityHistoryDeclaration | None
    calendar: CnAShareFrozenCalendar
    order_rule_book: CnAShareOrderRuleBook
    market_fee_rule_book: CnAShareMarketFeeRuleBook
    stamp_duty_rule_book: CnAShareStampDutyRuleBook
    corporate_action_rule_book: CnAShareCorporateActionEntitlementRuleBook
    corporate_action_entitlements: tuple[CnAShareCorporateActionEntitlement, ...]
    cash_payment_requests: tuple[CnAShareCashPaymentRequest, ...]
    share_delivery_requests: tuple[CnAShareShareDeliveryRequest, ...]
    timeline_window: TimelineWindow
    composed_at: SimulationInstant

    def __post_init__(self) -> None:
        for name, declaration_type in (
            ("instrument_scope", CnAShareInstrumentScopeDeclaration),
            ("account_scope", CnAShareAccountScopeDeclaration),
            ("announcement_revision_set", CnAShareAnnouncementRevisionSetDeclaration),
            ("register_revision_set", CnAShareRegisterRevisionSetDeclaration),
            ("identity_history", CnAShareIdentityHistoryDeclaration),
        ):
            value = getattr(self, name)
            if value is not None and type(value) is not declaration_type:
                raise TypeError(f"{name} must be exact {declaration_type.__name__} or None")
        for name, authority_type in (
            ("calendar", CnAShareFrozenCalendar), ("order_rule_book", CnAShareOrderRuleBook),
            ("market_fee_rule_book", CnAShareMarketFeeRuleBook),
            ("stamp_duty_rule_book", CnAShareStampDutyRuleBook),
            ("corporate_action_rule_book", CnAShareCorporateActionEntitlementRuleBook),
        ):
            if type(getattr(self, name)) is not authority_type:
                raise TypeError(f"{name} must be exact {authority_type.__name__}")
        for name, item_type in (
            ("corporate_action_entitlements", CnAShareCorporateActionEntitlement),
            ("cash_payment_requests", CnAShareCashPaymentRequest),
            ("share_delivery_requests", CnAShareShareDeliveryRequest),
        ):
            values = getattr(self, name)
            if type(values) is not tuple or not all(type(value) is item_type for value in values):
                raise TypeError(f"{name} must contain exact {item_type.__name__}")
        object.__setattr__(self, "corporate_action_entitlements", tuple(sorted(self.corporate_action_entitlements, key=lambda value: (value.position_key.venue_id.value, str(value.position_key.instrument_id), value.query.announcement.corporate_action_id if value.query.announcement else "", value.entitlement_hash))))
        object.__setattr__(self, "cash_payment_requests", tuple(sorted(self.cash_payment_requests, key=lambda value: (value.evidence.trigger_at, value.journal_entry_id.value, value.request_hash))))
        object.__setattr__(self, "share_delivery_requests", tuple(sorted(self.share_delivery_requests, key=lambda value: (value.evidence.trigger_at, value.journal_entry_id.value, value.request_hash))))
        if type(self.timeline_window) is not TimelineWindow:
            raise TypeError("timeline_window must be exact TimelineWindow")
        _availability(self.composed_at)

    def _body(self) -> dict[str, object]:
        return {
            "instrument_scope": self.instrument_scope, "account_scope": self.account_scope,
            "announcement_revision_set": self.announcement_revision_set,
            "register_revision_set": self.register_revision_set, "identity_history": self.identity_history,
            "calendar": self.calendar, "order_rule_book": self.order_rule_book,
            "market_fee_rule_book": self.market_fee_rule_book,
            "stamp_duty_rule_book": self.stamp_duty_rule_book,
            "corporate_action_rule_book": self.corporate_action_rule_book,
            "corporate_action_entitlements": self.corporate_action_entitlements,
            "cash_payment_requests": self.cash_payment_requests,
            "share_delivery_requests": self.share_delivery_requests,
            "timeline_window": self.timeline_window, "composed_at": self.composed_at,
        }

    @property
    def request_hash(self) -> str:
        return canonical_sha256({"type": "cn_a_share_profile_composition_request", "schema_version": 1, **self._body()})

    def to_canonical_dict(self) -> dict[str, object]:
        return _canonical_with_hash("cn_a_share_profile_composition_request", self._body(), "request_hash")


@dataclass(frozen=True, slots=True)
class CnAShareMarketSemanticsProfile:
    model_digest: str
    source_manifest_hash: str
    component_manifest: tuple[ProfileComponentRef, ...]
    financial_dispatcher_spec: FinancialDispatcherSpec
    profile_key: str = _MARKET_KEY
    profile_version: int = 1

    def __post_init__(self) -> None:
        _hash("model_digest", self.model_digest); _hash("source_manifest_hash", self.source_manifest_hash)
        if type(self.component_manifest) is not tuple or not all(type(value) is ProfileComponentRef for value in self.component_manifest):
            raise TypeError("component_manifest must contain exact ProfileComponentRef")
        ordered = tuple(sorted(self.component_manifest, key=lambda value: value.port_type.value))
        if (
            len(ordered) != len(ProfilePortType)
            or {value.port_type for value in ordered} != set(ProfilePortType)
        ):
            raise ValueError("market component manifest must exact-cover ProfilePortType")
        object.__setattr__(self, "component_manifest", ordered)
        if type(self.financial_dispatcher_spec) is not FinancialDispatcherSpec:
            raise TypeError("financial_dispatcher_spec must be exact FinancialDispatcherSpec")
        if (
            self.profile_key != _MARKET_KEY
            or type(self.profile_version) is not int
            or self.profile_version != 1
        ):
            raise ValueError("market profile identity mismatch")

    def _body(self) -> dict[str, object]:
        return {"model_digest": self.model_digest, "source_manifest_hash": self.source_manifest_hash, "component_manifest": self.component_manifest, "financial_dispatcher_spec": self.financial_dispatcher_spec, "profile_key": self.profile_key, "profile_version": self.profile_version}

    @property
    def profile_digest(self) -> str:
        return canonical_sha256({"type": "cn_a_share_market_semantics_profile", "schema_version": 1, **self._body()})

    def to_canonical_dict(self) -> dict[str, object]:
        return _canonical_with_hash("cn_a_share_market_semantics_profile", self._body(), "profile_digest")


@dataclass(frozen=True, slots=True)
class CnAShareSimulationProfile:
    model_digest: str
    component_manifest: tuple[SimulationComponentRef, ...]
    profile_key: str = _SIMULATION_KEY
    profile_version: int = 1

    def __post_init__(self) -> None:
        _hash("model_digest", self.model_digest)
        if type(self.component_manifest) is not tuple or not all(type(value) is SimulationComponentRef for value in self.component_manifest):
            raise TypeError("component_manifest must contain exact SimulationComponentRef")
        ordered = tuple(sorted(self.component_manifest, key=lambda value: value.port_type.value))
        if (
            len(ordered) != len(SimulationPortType)
            or {value.port_type for value in ordered} != set(SimulationPortType)
        ):
            raise ValueError("simulation component manifest must exact-cover SimulationPortType")
        object.__setattr__(self, "component_manifest", ordered)
        if (
            self.profile_key != _SIMULATION_KEY
            or type(self.profile_version) is not int
            or self.profile_version != 1
        ):
            raise ValueError("simulation profile identity mismatch")

    def _body(self) -> dict[str, object]:
        return {"model_digest": self.model_digest, "component_manifest": self.component_manifest, "profile_key": self.profile_key, "profile_version": self.profile_version}

    @property
    def profile_digest(self) -> str:
        return canonical_sha256({"type": "cn_a_share_simulation_profile", "schema_version": 1, **self._body()})

    def to_canonical_dict(self) -> dict[str, object]:
        return _canonical_with_hash("cn_a_share_simulation_profile", self._body(), "profile_digest")


@dataclass(frozen=True, slots=True)
class CnAShareExecutionAccountProfile:
    model_digest: str
    source_manifest_hash: str
    account_id: str
    venue_id: str
    account_risk_policy: AccountRiskPolicy
    profile_key: str = _ACCOUNT_KEY
    profile_version: int = 1
    account_type: str = "equity"
    margin_mode: str = "cash_only"

    def __post_init__(self) -> None:
        _hash("model_digest", self.model_digest); _hash("source_manifest_hash", self.source_manifest_hash)
        _text("account_id", self.account_id); _text("venue_id", self.venue_id)
        if type(self.account_risk_policy) is not AccountRiskPolicy:
            raise TypeError("account_risk_policy must be exact AccountRiskPolicy")
        if (
            self.profile_key != _ACCOUNT_KEY
            or type(self.profile_version) is not int
            or self.profile_version != 1
            or self.account_type != "equity"
            or self.margin_mode != "cash_only"
        ):
            raise ValueError("execution-account profile identity mismatch")

    def _body(self) -> dict[str, object]:
        return {"model_digest": self.model_digest, "source_manifest_hash": self.source_manifest_hash, "account_id": self.account_id, "venue_id": self.venue_id, "account_risk_policy": self.account_risk_policy, "profile_key": self.profile_key, "profile_version": self.profile_version, "account_type": self.account_type, "margin_mode": self.margin_mode}

    @property
    def profile_digest(self) -> str:
        return canonical_sha256({"type": "cn_a_share_execution_account_profile", "schema_version": 1, **self._body()})

    def to_canonical_dict(self) -> dict[str, object]:
        return _canonical_with_hash("cn_a_share_execution_account_profile", self._body(), "profile_digest")


def _source_manifest(request: CnAShareProfileCompositionRequest) -> tuple[str, ...]:
    declarations = (request.instrument_scope, request.account_scope, request.announcement_revision_set, request.register_revision_set, request.identity_history)
    values = [*(_INHERITED_FIXTURE_HASHES), request.calendar.calendar_hash, request.order_rule_book.rule_book_hash, request.market_fee_rule_book.rule_book_hash, request.stamp_duty_rule_book.rule_book_hash, request.corporate_action_rule_book.rule_book_hash]
    values.extend(value.declaration_hash for value in declarations if value is not None)
    values.extend(value.entitlement_hash for value in request.corporate_action_entitlements)
    values.extend(value.request_hash for value in request.cash_payment_requests)
    values.extend(value.request_hash for value in request.share_delivery_requests)
    return tuple(sorted(set(values)))


def _model_digest(request: CnAShareProfileCompositionRequest) -> str:
    return canonical_sha256({
        "type": "cn_a_share_profile_composition_model", "schema_version": 1,
        "model_key": _MODEL_KEY, "model_version": 1, "request_hash": request.request_hash,
        "source_manifest": _source_manifest(request), "market_key": _MARKET_KEY,
        "simulation_key": _SIMULATION_KEY, "account_key": _ACCOUNT_KEY,
        "dispatcher_key": _DISPATCHER_KEY, "limitations": _LIMITATIONS,
    })


def _profile_component(port: ProfilePortType, key: str, payload: object) -> ProfileComponentRef:
    return ProfileComponentRef(port, key, 1, canonical_sha256(payload))


def _simulation_component(port: SimulationPortType, key: str, payload: object) -> SimulationComponentRef:
    return SimulationComponentRef(port, key, 1, canonical_sha256(payload))


def _components(request: CnAShareProfileCompositionRequest) -> tuple[ProfileComponentRef, ...]:
    scope = request.instrument_scope
    if scope is None:
        raise ValueError("instrument scope is required")
    base = default_cash_financial_dispatcher_spec()
    static_liquidation = {
        "type": "cn_a_share_profile_static_component", "schema_version": 1,
        "port_type": "liquidation_rules", "component_key": "equity.cn_a_share.cash.liquidation-not-applicable.v1",
        "component_version": 1, "policy": "cash_long_only_no_liquidation",
    }
    static_valuation = {
        "type": "cn_a_share_profile_static_component", "schema_version": 1,
        "port_type": "currency_valuation_policy", "component_key": "equity.cn_a_share.cny-identity-valuation.v1",
        "component_version": 1, "policy": "cny_identity_path_only",
    }
    session = CnAShareCashSessionModel(request.calendar)
    values = (
        session.component_ref,
        CnAShareCashQuantityLatticeModel(scope.instrument.instrument_id.venue, Scale(2)).component_ref,
        CnAShareCashOrderRuleModel(request.order_rule_book, Scale(2)).component_ref,
        CnAShareCashMarketFeePolicy(request.market_fee_rule_book, Scale(2)).component_ref,
        CnAShareCashStampDutyTaxPolicy(request.stamp_duty_rule_book, Scale(2)).component_ref,
        CnAShareCashSettlementModel(request.calendar).component_ref,
        base.position_accounting_component,
        base.financing_component,
        base.margin_component,
        _profile_component(ProfilePortType.LIQUIDATION_RULES, "equity.cn_a_share.cash.liquidation-not-applicable.v1", static_liquidation),
        CnAShareCorporateActionEntitlementModel(request.corporate_action_rule_book, session).component_ref,
        _profile_component(ProfilePortType.CURRENCY_VALUATION_POLICY, "equity.cn_a_share.cny-identity-valuation.v1", static_valuation),
    )
    return tuple(sorted(values, key=lambda value: value.port_type.value))


def _simulation_components(model_digest: str) -> tuple[SimulationComponentRef, ...]:
    values = (
        SimulationComponentRef(SimulationPortType.EXECUTION_MODEL, "next_eligible_bar_open.v1", 1, "sha256:d69d6d96c9081f730db6ff8cdd02431d4babdef2e3967f0094971e73aedf30fe"),
        _simulation_component(SimulationPortType.SLIPPAGE_MODEL, "zero_slippage.development.v1", {"model_digest": model_digest, "bps": 0, "rounding": "toward_zero", "limitation": "zero_slippage_development_only"}),
        _simulation_component(SimulationPortType.LATENCY_MODEL, "latency.zero.development.v1", {"model_digest": model_digest}),
        _simulation_component(SimulationPortType.LIQUIDITY_MODEL, "liquidity.next-bar-full-fill.development.v1", {"model_digest": model_digest}),
        SimulationComponentRef(SimulationPortType.LIQUIDATION_AUDIT_MODEL, "cash.no-liquidation-audit.v1", 1, "sha256:2cce82368126aca72a49690cb11e083af7fd857e1b0cd46894515d89f09e5955"),
        SimulationComponentRef(SimulationPortType.CLOSEOUT_POLICY, "mark_to_market.v1", 1, "sha256:d9be291bff3147a191296ec5b3d37cc79aecc9ee2bff4877d7bca86f9aeb0ea8"),
    )
    return tuple(sorted(values, key=lambda value: value.port_type.value))


def _chain_closed(chain: tuple[tuple[str, str | None, str], ...], terminal: str) -> bool:
    if not chain or chain[0][1] is not None or chain[-1][0] != terminal:
        return False
    ids = tuple(row[0] for row in chain)
    return len(ids) == len(set(ids)) and all(chain[index][1] == chain[index - 1][0] for index in range(1, len(chain)))


def _has_identity_conflict(values: tuple[tuple[str, str], ...]) -> bool:
    seen: dict[str, str] = {}
    for key, payload_hash in values:
        previous = seen.setdefault(key, payload_hash)
        if previous != payload_hash:
            return True
    return False


def _covers(start: UtcInstant, end: UtcInstant, window: TimelineWindow) -> bool:
    return start <= window.data_start and end >= window.end_exclusive


def _date_covers(start: date, end: date, window: TimelineWindow) -> bool:
    timezone = ZoneInfo("Asia/Shanghai")
    start_date = datetime.fromtimestamp(window.data_start.epoch_nanoseconds // 1_000_000_000, timezone).date()
    end_date = datetime.fromtimestamp((window.end_exclusive.epoch_nanoseconds - 1) // 1_000_000_000, timezone).date()
    return start <= start_date and end > end_date


def _authority_context_mismatch(request: CnAShareProfileCompositionRequest) -> bool:
    instrument_scope = request.instrument_scope; account_scope = request.account_scope
    announcement_set = request.announcement_revision_set; register_set = request.register_revision_set
    if (
        instrument_scope is None
        or account_scope is None
        or announcement_set is None
        or register_set is None
    ):
        return True
    instrument = instrument_scope.instrument
    venue = instrument.instrument_id.venue
    if account_scope.venue_id != venue or request.calendar.venue_id != venue:
        return True
    if announcement_set.venue_id != venue or announcement_set.instrument_id != instrument.instrument_id:
        return True
    if register_set.account_id != account_scope.account_id or register_set.position_key != PositionBalanceKey(account_scope.account_id, venue, instrument.instrument_id):
        return True
    for entitlement in request.corporate_action_entitlements:
        announcement = entitlement.query.announcement
        snapshot = entitlement.query.snapshot
        if (
            announcement is None
            or snapshot is None
            or entitlement.query.instrument != instrument
            or entitlement.account_id != account_scope.account_id
            or entitlement.position_key != register_set.position_key
        ):
            return True
        announcement_row = (
            announcement.revision_id,
            announcement.supersedes_revision_id,
            announcement.candidate_hash,
        )
        snapshot_row = (
            snapshot.revision_id,
            snapshot.supersedes_revision_id,
            snapshot.snapshot_hash,
        )
        if (
            announcement.corporate_action_id != announcement_set.corporate_action_id
            or announcement.revision_id != announcement_set.terminal_revision_id
            or announcement_row not in announcement_set.revision_chain
            or snapshot.register_series_id != register_set.register_series_id
            or snapshot.revision_id != register_set.terminal_revision_id
            or snapshot_row not in register_set.revision_chain
        ):
            return True
        if entitlement.calendar != request.calendar or entitlement.rule_book != request.corporate_action_rule_book:
            return True
    entitlement_hashes = {value.entitlement_hash for value in request.corporate_action_entitlements}
    for cash_request in request.cash_payment_requests:
        if cash_request.entitlement.entitlement_hash not in entitlement_hashes or cash_request.entitlement.account_id != account_scope.account_id or cash_request.entitlement.position_key != register_set.position_key:
            return True
    for share_request in request.share_delivery_requests:
        if share_request.entitlement.entitlement_hash not in entitlement_hashes or share_request.entitlement.account_id != account_scope.account_id or share_request.entitlement.position_key != register_set.position_key:
            return True
    if any(band.venue_id != venue for band in request.order_rule_book.bands):
        return True
    if not any(band.venue_id == venue for band in request.market_fee_rule_book.bands):
        return True
    if not any(band.venue_id == venue for band in request.stamp_duty_rule_book.bands):
        return True
    return False


def _first_failure(request: CnAShareProfileCompositionRequest) -> CnAShareProfileCompositionFailureCode | None:
    code = CnAShareProfileCompositionFailureCode
    if request.instrument_scope is None: return code.MISSING_INSTRUMENT_SCOPE
    if request.account_scope is None: return code.MISSING_ACCOUNT_SCOPE
    if request.announcement_revision_set is None: return code.MISSING_ANNOUNCEMENT_REVISION_SET
    if request.register_revision_set is None: return code.MISSING_REGISTER_REVISION_SET
    if request.identity_history is None: return code.MISSING_IDENTITY_HISTORY
    instrument = request.instrument_scope
    excluded = (instrument.is_b_or_h_share, instrument.is_fund_or_bond, instrument.is_stock_connect, instrument.has_lending_or_repo, instrument.has_pledge_or_freeze, instrument.is_restricted_or_pre_ipo, instrument.has_differential_distribution, instrument.has_issuer_self_distribution)
    definition = instrument.instrument
    if (
        definition.instrument_id.venue.value not in {"xshg", "xshe"}
        or definition.instrument_type is not InstrumentType.EQUITY
        or definition.quote_currency != _CNY
        or definition.settlement_currency != _CNY
        or instrument.rule_context.risk_class is not CnAShareRiskClass.STANDARD
        or instrument.rule_context.listing_phase is not CnAShareListingPhase.SEASONED
        or not instrument.is_ordinary_domestic_a_share
        or not instrument.is_standard_cash_auction
        or any(excluded)
    ):
        return code.INSTRUMENT_SCOPE_MISMATCH
    account = request.account_scope
    if not account.is_cash_account or not account.is_domestic_access or account.has_margin_or_short_permission or account.has_stock_connect_permission or account.authorizes_available_margin_use:
        return code.ACCOUNT_SCOPE_MISMATCH
    if _authority_context_mismatch(request): return code.AUTHORITY_CONTEXT_MISMATCH
    announcement = request.announcement_revision_set; register = request.register_revision_set
    if announcement.is_cancelled or not _chain_closed(announcement.revision_chain, announcement.terminal_revision_id) or not _chain_closed(register.revision_chain, register.terminal_revision_id):
        return code.REVISION_CLOSURE_MISMATCH
    history = request.identity_history
    identity_values = (
        history.corporate_action_hashes
        + history.register_snapshot_hashes
        + history.register_revision_hashes
    )
    if _has_identity_conflict(identity_values):
        return code.CROSS_QUERY_IDENTITY_CONFLICT
    declarations = (instrument, account, announcement, register, history)
    if any(not _covers(value.coverage_from, value.coverage_to_exclusive, request.timeline_window) for value in declarations):
        return code.TIMELINE_COVERAGE_MISMATCH
    if not _date_covers(request.calendar.coverage_start, request.calendar.coverage_end_exclusive, request.timeline_window):
        return code.TIMELINE_COVERAGE_MISMATCH
    if any(value.available_at > request.composed_at for value in declarations):
        return code.EVIDENCE_NOT_AVAILABLE
    nested_availability = [value.query.captured_at for value in request.corporate_action_entitlements]
    nested_availability += [value.evidence.available_at for value in request.cash_payment_requests]
    nested_availability += [value.evidence.available_at for value in request.share_delivery_requests]
    if any(value > request.composed_at for value in nested_availability):
        return code.EVIDENCE_NOT_AVAILABLE
    if any(value.evidence.tax_disposition is not CnAShareCorporateActionTaxDisposition.NOT_APPLICABLE for value in request.cash_payment_requests) or any(value.evidence.tax_disposition is not CnAShareCorporateActionTaxDisposition.NOT_APPLICABLE for value in request.share_delivery_requests):
        return code.UNSUPPORTED_TAX_DISPOSITION
    if any(value.entitlement.position_key.venue_id.value == "xshg" for value in request.share_delivery_requests):
        return code.UNSUPPORTED_XSHG_SHARE_DELIVERY
    manifest_hashes = {value.source_manifest_hash for value in declarations}
    if len(manifest_hashes) != 1:
        return code.COMPONENT_IDENTITY_CONFLICT
    identities: dict[tuple[str, int], str] = {}
    for profile_component in _components(request):
        identity = (profile_component.component_key, profile_component.component_version)
        if identities.setdefault(identity, profile_component.component_digest) != profile_component.component_digest:
            return code.COMPONENT_IDENTITY_CONFLICT
    for simulation_component in _simulation_components(_model_digest(request)):
        identity = (simulation_component.component_key, simulation_component.component_version)
        if identities.setdefault(identity, simulation_component.component_digest) != simulation_component.component_digest:
            return code.COMPONENT_IDENTITY_CONFLICT
    return None


@dataclass(frozen=True, slots=True)
class _Values:
    model_digest: str
    source_manifest: tuple[str, ...]
    account_risk_policy: AccountRiskPolicy
    market_semantics: CnAShareMarketSemanticsProfile
    simulation: CnAShareSimulationProfile
    execution_account: CnAShareExecutionAccountProfile
    market_registration: MarketSemanticsProfileRegistration
    simulation_registration: SimulationProfileRegistration
    execution_account_registration: ExecutionAccountProfileRegistration
    profile_registry: BacktestProfileRegistry
    financial_dispatcher_spec: FinancialDispatcherSpec


def _values(request: CnAShareProfileCompositionRequest) -> _Values:
    instrument = request.instrument_scope; account = request.account_scope
    if instrument is None or account is None:
        raise ValueError("complete declarations required")
    model_digest = _model_digest(request)
    source_manifest = _source_manifest(request)
    source_manifest_hash = canonical_sha256(source_manifest)
    policy = AccountRiskPolicy.create(
        policy_key="equity.cn_a_share.cash.long-only.risk.v1", policy_version=1,
        account_id=account.account_id, venue_id=account.venue_id,
        allowed_sides=(OrderSide.BUY, OrderSide.SELL),
        allowed_position_effects=(PositionEffect.OPEN, PositionEffect.CLOSE),
        allowed_reduce_only_values=(False, True),
        fee_reserve_funding_source=FeeReserveFundingSource.TRADABLE_CASH,
        order_capacity_limit=1, exposure_capacity_limits=(),
    )
    market_components = _components(request); simulation_components = _simulation_components(model_digest)
    base = default_cash_financial_dispatcher_spec()
    dispatcher = FinancialDispatcherSpec(
        _DISPATCHER_KEY, 1,
        canonical_sha256({
            "type": "cn_a_share_financial_dispatcher_config", "schema_version": 1,
            "model_digest": model_digest, "source_manifest": source_manifest,
            "market_component_manifest": market_components,
            "simulation_component_manifest": simulation_components,
            "operation_keys": ("cn_a_share.corporate_action.cash_payment.v1", "cn_a_share.corporate_action.share_delivery.v1"),
            "cash_payment_request_hashes": tuple(value.request_hash for value in request.cash_payment_requests),
            "share_delivery_request_hashes": tuple(value.request_hash for value in request.share_delivery_requests),
            "limitations": _LIMITATIONS,
        }),
        base.position_accounting_component, base.financing_component, base.margin_component,
        base.liquidation_audit_component, base.snapshot_projection_key, base.snapshot_projection_version,
    )
    market = CnAShareMarketSemanticsProfile(model_digest, source_manifest_hash, market_components, dispatcher)
    simulation = CnAShareSimulationProfile(model_digest, simulation_components)
    execution_account = CnAShareExecutionAccountProfile(model_digest, source_manifest_hash, account.account_id, account.venue_id.value, policy)
    market_registration = MarketSemanticsProfileRegistration(
        _MARKET_KEY, 1, market.profile_digest, market, account.venue_id.value,
        (MarketBundleCapability("account.financial-event", 1), MarketBundleCapability("bar_open", 1), MarketBundleCapability("corporate_actions", 1)),
        market.component_manifest, RequestedResultGrade.DEVELOPMENT, _LIMITATIONS, False,
    )
    simulation_registration = SimulationProfileRegistration(
        _SIMULATION_KEY, 1, simulation.profile_digest, simulation, "bar",
        (StrategyFamily.PRECOMPUTED_TARGET,), (MarketBundleCapability("bar_open", 1),),
        simulation.component_manifest, RequestedResultGrade.DEVELOPMENT, _LIMITATIONS, False,
    )
    account_registration = ExecutionAccountProfileRegistration(
        _ACCOUNT_KEY, 1, execution_account.profile_digest, execution_account,
        account.account_id, account.venue_id.value, "equity", "cash_only", (_CNY,),
        RequestedResultGrade.DEVELOPMENT, _LIMITATIONS, False,
    )
    registry = BacktestProfileRegistry((market_registration,), (simulation_registration,), (account_registration,))
    return _Values(model_digest, source_manifest, policy, market, simulation, execution_account, market_registration, simulation_registration, account_registration, registry, dispatcher)


@dataclass(frozen=True, slots=True)
class CnAShareResolvedProfile:
    request: CnAShareProfileCompositionRequest
    model_key: str
    model_version: int
    model_digest: str
    source_manifest: tuple[str, ...]
    account_risk_policy: AccountRiskPolicy
    market_semantics: CnAShareMarketSemanticsProfile
    simulation: CnAShareSimulationProfile
    execution_account: CnAShareExecutionAccountProfile
    market_registration: MarketSemanticsProfileRegistration
    simulation_registration: SimulationProfileRegistration
    execution_account_registration: ExecutionAccountProfileRegistration
    profile_registry: BacktestProfileRegistry
    financial_dispatcher_spec: FinancialDispatcherSpec
    limitations: tuple[str, ...]
    decision_grade_eligible: bool
    profile_qualified: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        if type(self.request) is not CnAShareProfileCompositionRequest:
            raise TypeError("request must be exact composition request")
        if type(self.model_version) is not int or any(
            type(value) is not bool
            for value in (
                self.decision_grade_eligible,
                self.profile_qualified,
                self.deployment_authorized,
            )
        ):
            raise TypeError("resolved profile version and qualification types mismatch")
        values = _values(self.request)
        expected = (_MODEL_KEY, 1, values.model_digest, values.source_manifest, values.account_risk_policy, values.market_semantics, values.simulation, values.execution_account, values.market_registration, values.simulation_registration, values.execution_account_registration, values.profile_registry, values.financial_dispatcher_spec, _LIMITATIONS, False, False, False)
        actual = (self.model_key, self.model_version, self.model_digest, self.source_manifest, self.account_risk_policy, self.market_semantics, self.simulation, self.execution_account, self.market_registration, self.simulation_registration, self.execution_account_registration, self.profile_registry, self.financial_dispatcher_spec, self.limitations, self.decision_grade_eligible, self.profile_qualified, self.deployment_authorized)
        if actual != expected or canonical_sha256(actual) != canonical_sha256(expected):
            raise ValueError("resolved profile fields do not match composition authority")

    def _body(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @property
    def profile_digest(self) -> str:
        return canonical_sha256({"type": "cn_a_share_resolved_profile", "schema_version": 1, **self._body()})

    def to_canonical_dict(self) -> dict[str, object]:
        return _canonical_with_hash("cn_a_share_resolved_profile", self._body(), "profile_digest")


@dataclass(frozen=True, slots=True)
class CnAShareProfileCompositionFailure:
    request: CnAShareProfileCompositionRequest
    model_digest: str
    code: CnAShareProfileCompositionFailureCode
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.request) is not CnAShareProfileCompositionRequest or type(self.code) is not CnAShareProfileCompositionFailureCode:
            raise TypeError("failure authority types mismatch")
        if self.model_digest != _model_digest(self.request) or self.code is not _first_failure(self.request) or self.subject_ids != (self.code.value, self.request.request_hash):
            raise ValueError("failure fields do not match first-failure authority")

    def _body(self) -> dict[str, object]:
        return {"request": self.request, "model_digest": self.model_digest, "code": self.code.value, "subject_ids": self.subject_ids}

    @property
    def failure_hash(self) -> str:
        return canonical_sha256({"type": "cn_a_share_profile_composition_failure", "schema_version": 1, **self._body()})

    def to_canonical_dict(self) -> dict[str, object]:
        return _canonical_with_hash("cn_a_share_profile_composition_failure", self._body(), "failure_hash")


@dataclass(frozen=True, slots=True)
class CnAShareProfileCompositionOutcome:
    request_hash: str
    model_digest: str
    result: CnAShareResolvedProfile | None
    failure: CnAShareProfileCompositionFailure | None

    def __post_init__(self) -> None:
        _hash("request_hash", self.request_hash); _hash("model_digest", self.model_digest)
        if self.result is not None and type(self.result) is not CnAShareResolvedProfile:
            raise TypeError("result must be exact CnAShareResolvedProfile")
        if self.failure is not None and type(self.failure) is not CnAShareProfileCompositionFailure:
            raise TypeError("failure must be exact CnAShareProfileCompositionFailure")
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one result or failure")
        authority = self.result if self.result is not None else self.failure
        if authority is None or authority.request.request_hash != self.request_hash or authority.model_digest != self.model_digest:
            raise ValueError("outcome identity mismatch")
        code = _first_failure(authority.request)
        if (self.result is not None) != (code is None):
            raise ValueError("outcome branch does not match composition authority")

    def _body(self) -> dict[str, object]:
        return {"request_hash": self.request_hash, "model_digest": self.model_digest, "result": self.result, "failure": self.failure}

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256({"type": "cn_a_share_profile_composition_outcome", "schema_version": 1, **self._body()})

    def to_canonical_dict(self) -> dict[str, object]:
        return _canonical_with_hash("cn_a_share_profile_composition_outcome", self._body(), "outcome_hash")


class CnAShareProfileComposer:
    def compose(self, request: CnAShareProfileCompositionRequest, /) -> CnAShareProfileCompositionOutcome:
        if type(request) is not CnAShareProfileCompositionRequest:
            raise TypeError("request must be exact composition request")
        model_digest = _model_digest(request)
        code = _first_failure(request)
        if code is not None:
            failure = CnAShareProfileCompositionFailure(request, model_digest, code, (code.value, request.request_hash))
            return CnAShareProfileCompositionOutcome(request.request_hash, model_digest, None, failure)
        values = _values(request)
        result = CnAShareResolvedProfile(request, _MODEL_KEY, 1, values.model_digest, values.source_manifest, values.account_risk_policy, values.market_semantics, values.simulation, values.execution_account, values.market_registration, values.simulation_registration, values.execution_account_registration, values.profile_registry, values.financial_dispatcher_spec, _LIMITATIONS, False, False, False)
        return CnAShareProfileCompositionOutcome(request.request_hash, model_digest, result, None)


__all__ = [
    "CnAShareInstrumentScopeDeclaration", "CnAShareAccountScopeDeclaration",
    "CnAShareAnnouncementRevisionSetDeclaration", "CnAShareRegisterRevisionSetDeclaration",
    "CnAShareIdentityHistoryDeclaration", "CnAShareProfileCompositionRequest",
    "CnAShareMarketSemanticsProfile", "CnAShareSimulationProfile",
    "CnAShareExecutionAccountProfile", "CnAShareResolvedProfile",
    "CnAShareProfileCompositionFailureCode", "CnAShareProfileCompositionFailure",
    "CnAShareProfileCompositionOutcome", "CnAShareProfileComposer",
]
