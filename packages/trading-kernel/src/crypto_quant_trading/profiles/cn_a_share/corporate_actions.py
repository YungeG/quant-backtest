"""Finite development-grade A-share corporate-action entitlement semantics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
from typing import Any
import re
import unicodedata
from zoneinfo import ZoneInfo

from crypto_quant_domain import (
    CurrencyId,
    InstrumentDefinition,
    InstrumentType,
    Money,
    PositionBalanceKey,
    Quantity,
    Rate,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_sha256,
)

from crypto_quant_trading.ports import (
    ProfileComponentRef,
    ProfilePortOutcome,
    ProfilePortType,
)
from .calendar import (
    CnAShareCalendarDayKind,
    CnAShareCashSessionModel,
    CnAShareFrozenCalendar,
    CnAShareSessionPhase,
    CnAShareSessionQuery,
)

_SCHEMA_VERSION = 1
_COMPONENT_KEY = "equity.cn_a_share.corporate-action-entitlement.v1"
_ALGORITHM_KEY = "cn-a-share-record-register-entitlement-v1"
_RECORD_PHASE = TimelinePhase(100, "corporate_action_record")
_RECORD_SEQUENCE = SourceSequence(0)
_CNY = CurrencyId("CNY")
_TIMEZONE = ZoneInfo("Asia/Shanghai")
_COVERAGE_START = UtcInstant.from_datetime(
    datetime(2026, 7, 6, tzinfo=_TIMEZONE)
)
_COVERAGE_END = UtcInstant.from_datetime(
    datetime(2026, 7, 31, tzinfo=_TIMEZONE)
)
_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_XSHG_SOURCE_IDENTITIES = (
    (
        "chinaclear.sh-issuer-guide.2026-33",
        "sha256:2e0947b9a19b9962c8a43d603b722e907fbd47d7615be5643be1005661f00ec8",
    ),
    (
        "sse.announcement-format.2025-36",
        "sha256:b441a51f63ace1c715128324e68dd7c66f00cbc4ad6205924bb5bb516e34b275",
    ),
    (
        "sse.distribution-guide.2025-document-5",
        "sha256:2830333711f19875734f6662f506c490429ac2eeba31a74dc52850d556933e40",
    ),
    (
        "sse.trading-rules.2026-41.corporate-actions",
        "sha256:fc922c433438b2636cb631eab25cca405209712acbb6aaded768c45456ff8888",
    ),
)
_XSHE_SOURCE_IDENTITIES = (
    (
        "chinaclear.sz-issuer-guide.2025-68",
        "sha256:e8db1f9761b083542d72568a25dcbab02b5d0e86d41309ca108eb362c822e902",
    ),
    (
        "szse.announcement-format.2026-7",
        "sha256:704eea0816d091c5502023fafc91b4ca6fe790b34843ee8b8006041d1a731175",
    ),
    (
        "szse.trading-rules.2026-551.corporate-actions",
        "sha256:9b66f8b0db70f84a25ef1ccb4ee2351001724e408117552d75f6d8993483c586",
    ),
)


def _calendar_id(venue: str) -> str | None:
    if venue == "xshg":
        return "CN.XSHG"
    if venue == "xshe":
        return "CN.XSHE"
    return None


def _official_source_identities(venue: str) -> tuple[tuple[str, str], ...] | None:
    if venue == "xshg":
        return _XSHG_SOURCE_IDENTITIES
    if venue == "xshe":
        return _XSHE_SOURCE_IDENTITIES
    return None


class CnAShareCorporateActionAnnouncementStatus(str, Enum):
    FINAL_IMPLEMENTATION = "final_implementation"
    PLAN_ONLY = "plan_only"
    CANCELLED = "cancelled"


class CnAShareCorporateActionFailureCode(str, Enum):
    MISSING_ANNOUNCEMENT = "missing_announcement"
    UNSUPPORTED_VENUE = "unsupported_venue"
    UNSUPPORTED_INSTRUMENT = "unsupported_instrument"
    UNSUPPORTED_CURRENCY = "unsupported_currency"
    UNSUPPORTED_ANNOUNCEMENT_STATUS = "unsupported_announcement_status"
    UNSUPPORTED_ANNOUNCEMENT_REVISION = "unsupported_announcement_revision"
    INVALID_ANNOUNCEMENT_CAUSALITY = "invalid_announcement_causality"
    MISSING_DISTRIBUTION_COMPONENT = "missing_distribution_component"
    MISSING_LIFECYCLE_TERM = "missing_lifecycle_term"
    INVALID_LIFECYCLE_ORDER = "invalid_lifecycle_order"
    UNSUPPORTED_DISTRIBUTION_RATE_BASIS = "unsupported_distribution_rate_basis"
    UNSUPPORTED_VENUE_ACTION_COMBINATION = "unsupported_venue_action_combination"
    NON_POSITIVE_DISTRIBUTION_TERM = "non_positive_distribution_term"
    ANNOUNCEMENT_NOT_AVAILABLE = "announcement_not_available"
    LATE_ANNOUNCEMENT = "late_announcement"
    MISSING_RULE_INTERVAL = "missing_rule_interval"
    OVERLAPPING_RULE_INTERVALS = "overlapping_rule_intervals"
    INVALID_RECORD_SESSION = "invalid_record_session"
    MISSING_REGISTERED_POSITION = "missing_registered_position"
    UNSUPPORTED_REGISTER_REVISION = "unsupported_register_revision"
    ACCOUNT_MISMATCH = "account_mismatch"
    INSTRUMENT_MISMATCH = "instrument_mismatch"
    RECORD_INSTANT_MISMATCH = "record_instant_mismatch"
    INVALID_REGISTER_CAUSALITY = "invalid_register_causality"
    REGISTER_NOT_AVAILABLE = "register_not_available"
    NEGATIVE_REGISTERED_QUANTITY = "negative_registered_quantity"
    UNSUPPORTED_CASH_PRECISION = "unsupported_cash_precision"
    UNSUPPORTED_FRACTIONAL_SHARE = "unsupported_fractional_share"


def _text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if (
        not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be non-empty canonical text")


def _hash(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 identity")


def _source_refs(
    values: tuple[CnAShareCorporateActionSourceRef, ...],
) -> tuple[CnAShareCorporateActionSourceRef, ...]:
    if not isinstance(values, tuple) or not values:
        raise ValueError("source_refs must be a non-empty tuple")
    if not all(isinstance(value, CnAShareCorporateActionSourceRef) for value in values):
        raise TypeError("source_refs must contain CnAShareCorporateActionSourceRef")
    ordered = tuple(sorted(values, key=lambda value: (value.source_key, value.source_hash)))
    if values != ordered:
        raise ValueError("source_refs must use canonical order")
    if len(set(values)) != len(values):
        raise ValueError("source_refs must be unique")
    return values


@dataclass(frozen=True, slots=True)
class CnAShareCorporateActionSourceRef:
    source_key: str
    source_hash: str

    def __post_init__(self) -> None:
        _text("source_key", self.source_key)
        _hash("source_hash", self.source_hash)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_corporate_action_source_ref",
            "schema_version": _SCHEMA_VERSION,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class CnAShareCorporateActionEntitlementBand:
    venue_id: VenueId
    effective_start: UtcInstant
    effective_end: UtcInstant
    source_refs: tuple[CnAShareCorporateActionSourceRef, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.venue_id, VenueId):
            raise TypeError("venue_id must be VenueId")
        if not isinstance(self.effective_start, UtcInstant) or not isinstance(
            self.effective_end, UtcInstant
        ):
            raise TypeError("effective bounds must be UtcInstant")
        if self.effective_start >= self.effective_end:
            raise ValueError("effective interval must be non-empty")
        _source_refs(self.source_refs)
        expected_sources = _official_source_identities(self.venue_id.value)
        actual_sources = tuple(
            (value.source_key, value.source_hash) for value in self.source_refs
        )
        if expected_sources is None or actual_sources != expected_sources:
            raise ValueError("source_refs must match the frozen Venue source identities")

    @property
    def band_hash(self) -> str:
        return canonical_sha256(self)

    def contains(self, instant: UtcInstant) -> bool:
        return self.effective_start <= instant < self.effective_end

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_corporate_action_entitlement_band",
            "schema_version": _SCHEMA_VERSION,
            "venue_id": self.venue_id,
            "effective_start": self.effective_start,
            "effective_end": self.effective_end,
            "source_refs": self.source_refs,
        }


@dataclass(frozen=True, slots=True)
class CnAShareCorporateActionEntitlementRuleBook:
    bands: tuple[CnAShareCorporateActionEntitlementBand, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.bands, tuple) or not self.bands:
            raise ValueError("bands must be a non-empty tuple")
        if not all(
            isinstance(value, CnAShareCorporateActionEntitlementBand)
            for value in self.bands
        ):
            raise TypeError("bands must contain entitlement bands")
        ordered = tuple(
            sorted(
                self.bands,
                key=lambda value: (
                    value.venue_id.value,
                    value.effective_start.epoch_nanoseconds,
                    value.effective_end.epoch_nanoseconds,
                    value.band_hash,
                ),
            )
        )
        if self.bands != ordered:
            raise ValueError("bands must use canonical order")
        if len(set(self.bands)) != len(self.bands):
            raise ValueError("bands must be unique")

    @property
    def rule_book_hash(self) -> str:
        return canonical_sha256(self)

    def active_bands(
        self, venue_id: VenueId, instant: UtcInstant
    ) -> tuple[CnAShareCorporateActionEntitlementBand, ...]:
        return tuple(
            value
            for value in self.bands
            if value.venue_id == venue_id and value.contains(instant)
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_corporate_action_entitlement_rule_book",
            "schema_version": _SCHEMA_VERSION,
            "bands": self.bands,
        }


def _component_ref(
    rule_book: CnAShareCorporateActionEntitlementRuleBook,
    calendar: CnAShareFrozenCalendar,
) -> ProfileComponentRef:
    session_ref = CnAShareCashSessionModel(calendar).component_ref
    digest = canonical_sha256(
        {
            "type": "cn_a_share_corporate_action_entitlement_component",
            "schema_version": _SCHEMA_VERSION,
            "component_key": _COMPONENT_KEY,
            "component_version": 1,
            "algorithm_key": _ALGORITHM_KEY,
            "rule_book_hash": rule_book.rule_book_hash,
            "session_component_digest": session_ref.component_digest,
            "record_phase": _RECORD_PHASE,
            "record_sequence": _RECORD_SEQUENCE,
            "cash_scale": 2,
            "share_scale": 0,
            "allowed_grade": "development",
        }
    )
    return ProfileComponentRef(
        ProfilePortType.CORPORATE_ACTION_MODEL,
        _COMPONENT_KEY,
        1,
        digest,
    )


def _next_trading_date(
    calendar: CnAShareFrozenCalendar, record_date: TradingDate
) -> TradingDate | None:
    for value in calendar.days:
        if (
            value.local_date > record_date.value
            and value.kind is CnAShareCalendarDayKind.TRADING
        ):
            return TradingDate(calendar.calendar_id, value.local_date)
    return None


@dataclass(frozen=True, slots=True)
class CnAShareCorporateActionAnnouncementCandidate:
    corporate_action_id: str
    instrument: InstrumentDefinition
    status: CnAShareCorporateActionAnnouncementStatus
    event_id: str
    event_hash: str
    event_time: UtcInstant
    announcement_available_at: SimulationInstant
    revision_id: str
    supersedes_revision_id: str | None
    record_date: TradingDate | None
    ex_date: TradingDate | None
    payment_date: TradingDate | None
    listing_date: TradingDate | None
    cash_per_share: Money | None
    bonus_rate: Rate | None
    capitalization_rate: Rate | None
    source_refs: tuple[CnAShareCorporateActionSourceRef, ...]

    def __post_init__(self) -> None:
        _text("corporate_action_id", self.corporate_action_id)
        if not isinstance(self.instrument, InstrumentDefinition):
            raise TypeError("instrument must be InstrumentDefinition")
        if not isinstance(self.status, CnAShareCorporateActionAnnouncementStatus):
            raise TypeError("status must be CnAShareCorporateActionAnnouncementStatus")
        _text("event_id", self.event_id)
        _hash("event_hash", self.event_hash)
        if not isinstance(self.event_time, UtcInstant):
            raise TypeError("event_time must be UtcInstant")
        if not isinstance(self.announcement_available_at, SimulationInstant):
            raise TypeError("announcement_available_at must be SimulationInstant")
        _text("revision_id", self.revision_id)
        if self.supersedes_revision_id is not None:
            _text("supersedes_revision_id", self.supersedes_revision_id)
        for name, value in (
            ("record_date", self.record_date),
            ("ex_date", self.ex_date),
            ("payment_date", self.payment_date),
            ("listing_date", self.listing_date),
        ):
            if value is not None and not isinstance(value, TradingDate):
                raise TypeError(f"{name} must be TradingDate or None")
        if self.cash_per_share is not None and not isinstance(self.cash_per_share, Money):
            raise TypeError("cash_per_share must be Money or None")
        if self.bonus_rate is not None and not isinstance(self.bonus_rate, Rate):
            raise TypeError("bonus_rate must be Rate or None")
        if self.capitalization_rate is not None and not isinstance(
            self.capitalization_rate, Rate
        ):
            raise TypeError("capitalization_rate must be Rate or None")
        _source_refs(self.source_refs)

    @property
    def candidate_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_corporate_action_announcement_candidate",
            "schema_version": _SCHEMA_VERSION,
            "corporate_action_id": self.corporate_action_id,
            "instrument": self.instrument,
            "status": self.status.value,
            "event_id": self.event_id,
            "event_hash": self.event_hash,
            "event_time": self.event_time,
            "announcement_available_at": self.announcement_available_at,
            "revision_id": self.revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
            "record_date": self.record_date,
            "ex_date": self.ex_date,
            "payment_date": self.payment_date,
            "listing_date": self.listing_date,
            "cash_per_share": self.cash_per_share,
            "bonus_rate": self.bonus_rate,
            "capitalization_rate": self.capitalization_rate,
            "source_refs": self.source_refs,
        }


@dataclass(frozen=True, slots=True)
class CnAShareRegisteredPositionSnapshot:
    snapshot_id: str
    register_series_id: str
    revision_id: str
    supersedes_revision_id: str | None
    account_id: str
    position_key: PositionBalanceKey
    eligibility_instant: SimulationInstant
    available_at: SimulationInstant
    registered_quantity: Quantity
    source_ref: CnAShareCorporateActionSourceRef

    def __post_init__(self) -> None:
        for name, value in (
            ("snapshot_id", self.snapshot_id),
            ("register_series_id", self.register_series_id),
            ("revision_id", self.revision_id),
            ("account_id", self.account_id),
        ):
            _text(name, value)
        if self.supersedes_revision_id is not None:
            _text("supersedes_revision_id", self.supersedes_revision_id)
        if not isinstance(self.position_key, PositionBalanceKey):
            raise TypeError("position_key must be PositionBalanceKey")
        if not isinstance(self.eligibility_instant, SimulationInstant):
            raise TypeError("eligibility_instant must be SimulationInstant")
        if not isinstance(self.available_at, SimulationInstant):
            raise TypeError("available_at must be SimulationInstant")
        if not isinstance(self.registered_quantity, Quantity):
            raise TypeError("registered_quantity must be Quantity")
        if not isinstance(self.source_ref, CnAShareCorporateActionSourceRef):
            raise TypeError("source_ref must be CnAShareCorporateActionSourceRef")

    @property
    def snapshot_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_registered_position_snapshot",
            "schema_version": _SCHEMA_VERSION,
            "snapshot_id": self.snapshot_id,
            "register_series_id": self.register_series_id,
            "revision_id": self.revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
            "account_id": self.account_id,
            "position_key": self.position_key,
            "eligibility_instant": self.eligibility_instant,
            "available_at": self.available_at,
            "registered_quantity": self.registered_quantity,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class CnAShareCorporateActionEntitlementQuery:
    instrument: InstrumentDefinition
    account_id: str
    announcement: CnAShareCorporateActionAnnouncementCandidate | None
    snapshot: CnAShareRegisteredPositionSnapshot | None
    captured_at: SimulationInstant

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, InstrumentDefinition):
            raise TypeError("instrument must be InstrumentDefinition")
        _text("account_id", self.account_id)
        if self.announcement is not None and not isinstance(
            self.announcement, CnAShareCorporateActionAnnouncementCandidate
        ):
            raise TypeError("announcement must be a Candidate or None")
        if self.snapshot is not None and not isinstance(
            self.snapshot, CnAShareRegisteredPositionSnapshot
        ):
            raise TypeError("snapshot must be a registered-position snapshot or None")
        if not isinstance(self.captured_at, SimulationInstant):
            raise TypeError("captured_at must be SimulationInstant")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_corporate_action_entitlement_query",
            "schema_version": _SCHEMA_VERSION,
            "instrument": self.instrument,
            "account_id": self.account_id,
            "announcement": self.announcement,
            "snapshot": self.snapshot,
            "captured_at": self.captured_at,
        }


def _validate_component_ref(value: ProfileComponentRef) -> None:
    if not isinstance(value, ProfileComponentRef):
        raise TypeError("component_ref must be ProfileComponentRef")
    if (
        value.port_type is not ProfilePortType.CORPORATE_ACTION_MODEL
        or value.component_key != _COMPONENT_KEY
        or value.component_version != 1
    ):
        raise ValueError("component_ref must identify the frozen Corporate Action Model")


def _validate_evidence_component(
    component_ref: ProfileComponentRef,
    rule_book: CnAShareCorporateActionEntitlementRuleBook,
    calendar: CnAShareFrozenCalendar,
) -> None:
    _validate_component_ref(component_ref)
    if not isinstance(rule_book, CnAShareCorporateActionEntitlementRuleBook):
        raise TypeError("rule_book must be an entitlement RuleBook")
    if not isinstance(calendar, CnAShareFrozenCalendar):
        raise TypeError("calendar must be CnAShareFrozenCalendar")
    if _component_ref(rule_book, calendar) != component_ref:
        raise ValueError("component_ref must match embedded RuleBook and Calendar")


def _failure_subject_ids(
    query: CnAShareCorporateActionEntitlementQuery,
    code: CnAShareCorporateActionFailureCode,
) -> tuple[str, ...]:
    return (
        code.value,
        (
            "missing-corporate-action"
            if query.announcement is None
            else query.announcement.corporate_action_id
        ),
        (
            "missing-register-snapshot"
            if query.snapshot is None
            else query.snapshot.snapshot_id
        ),
        query.account_id,
        str(query.instrument.instrument_id),
    )


@dataclass(frozen=True, slots=True)
class CnAShareCorporateActionEntitlement:
    component_ref: ProfileComponentRef
    rule_book: CnAShareCorporateActionEntitlementRuleBook
    calendar: CnAShareFrozenCalendar
    query: CnAShareCorporateActionEntitlementQuery
    active_band: CnAShareCorporateActionEntitlementBand
    band_hash: str
    query_hash: str
    candidate_hash: str
    event_id: str
    event_hash: str
    snapshot_hash: str
    account_id: str
    position_key: PositionBalanceKey
    eligibility_instant: SimulationInstant
    captured_at: SimulationInstant
    registered_quantity: Quantity
    gross_cash: Money
    bonus_quantity: Quantity
    capitalization_quantity: Quantity

    def __post_init__(self) -> None:
        _validate_evidence_component(
            self.component_ref, self.rule_book, self.calendar
        )
        if not isinstance(self.query, CnAShareCorporateActionEntitlementQuery):
            raise TypeError("query must be CnAShareCorporateActionEntitlementQuery")
        if not isinstance(
            self.active_band, CnAShareCorporateActionEntitlementBand
        ):
            raise TypeError("active_band must be an entitlement Band")
        for name, value in (
            ("band_hash", self.band_hash),
            ("query_hash", self.query_hash),
            ("candidate_hash", self.candidate_hash),
            ("event_hash", self.event_hash),
            ("snapshot_hash", self.snapshot_hash),
        ):
            _hash(name, value)
        _text("event_id", self.event_id)
        _text("account_id", self.account_id)
        if not isinstance(self.position_key, PositionBalanceKey):
            raise TypeError("position_key must be PositionBalanceKey")
        if self.position_key.account_id != self.account_id:
            raise ValueError("entitlement account must match position_key account")
        if not isinstance(self.eligibility_instant, SimulationInstant) or not isinstance(
            self.captured_at, SimulationInstant
        ):
            raise TypeError("entitlement instants must be SimulationInstant")
        if self.captured_at < self.eligibility_instant:
            raise ValueError("captured_at cannot precede eligibility_instant")
        if not isinstance(self.registered_quantity, Quantity):
            raise TypeError("registered_quantity must be Quantity")
        if not isinstance(self.gross_cash, Money):
            raise TypeError("gross_cash must be Money")
        if not isinstance(self.bonus_quantity, Quantity) or not isinstance(
            self.capitalization_quantity, Quantity
        ):
            raise TypeError("share entitlements must be Quantity")
        quantities = (
            self.registered_quantity,
            self.bonus_quantity,
            self.capitalization_quantity,
        )
        if any(
            value.instrument_id != str(self.position_key.instrument_id)
            or value.scale != Scale(0)
            or value.units < 0
            for value in quantities
        ):
            raise ValueError("entitlement quantity identity, scale, and sign must match")
        if (
            self.gross_cash.currency != "CNY"
            or self.gross_cash.scale != Scale(2)
            or self.gross_cash.units < 0
        ):
            raise ValueError("gross_cash must be non-negative CNY Scale 2")
        if canonical_sha256(self.query) != self.query_hash:
            raise ValueError("query_hash must match the embedded Query")
        if self.active_band.band_hash != self.band_hash:
            raise ValueError("band_hash must match the embedded active Band")
        announcement = self.query.announcement
        snapshot = self.query.snapshot
        if announcement is None or snapshot is None:
            raise ValueError("successful entitlement requires Announcement and Snapshot")
        if (
            announcement.candidate_hash != self.candidate_hash
            or announcement.event_id != self.event_id
            or announcement.event_hash != self.event_hash
            or snapshot.snapshot_hash != self.snapshot_hash
        ):
            raise ValueError("entitlement source identities must match the embedded Query")
        if (
            self.query.account_id != self.account_id
            or snapshot.position_key != self.position_key
            or snapshot.eligibility_instant != self.eligibility_instant
            or self.query.captured_at != self.captured_at
            or snapshot.registered_quantity != self.registered_quantity
        ):
            raise ValueError("entitlement account and position evidence must match Query")
        if self.rule_book.active_bands(
            self.query.instrument.instrument_id.venue,
            self.eligibility_instant.instant,
        ) != (self.active_band,):
            raise ValueError("active Band must be the unique RuleBook match")
        expected_cash, expected_bonus, expected_capitalization = (
            _successful_entitlement_values(
                self.query, self.active_band, self.calendar
            )
        )
        if (
            self.gross_cash != expected_cash
            or self.bonus_quantity != expected_bonus
            or self.capitalization_quantity != expected_capitalization
        ):
            raise ValueError("entitlement numeric values must match the embedded Query")

    @property
    def entitlement_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_corporate_action_entitlement",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "rule_book": self.rule_book,
            "calendar": self.calendar,
            "query": self.query,
            "active_band": self.active_band,
            "band_hash": self.band_hash,
            "query_hash": self.query_hash,
            "candidate_hash": self.candidate_hash,
            "event_id": self.event_id,
            "event_hash": self.event_hash,
            "snapshot_hash": self.snapshot_hash,
            "account_id": self.account_id,
            "position_key": self.position_key,
            "eligibility_instant": self.eligibility_instant,
            "captured_at": self.captured_at,
            "registered_quantity": self.registered_quantity,
            "gross_cash": self.gross_cash,
            "bonus_quantity": self.bonus_quantity,
            "capitalization_quantity": self.capitalization_quantity,
        }


@dataclass(frozen=True, slots=True)
class CnAShareCorporateActionFailure:
    component_ref: ProfileComponentRef
    rule_book: CnAShareCorporateActionEntitlementRuleBook
    calendar: CnAShareFrozenCalendar
    query: CnAShareCorporateActionEntitlementQuery
    query_hash: str
    code: CnAShareCorporateActionFailureCode
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_evidence_component(
            self.component_ref, self.rule_book, self.calendar
        )
        if not isinstance(self.query, CnAShareCorporateActionEntitlementQuery):
            raise TypeError("query must be CnAShareCorporateActionEntitlementQuery")
        _hash("query_hash", self.query_hash)
        if canonical_sha256(self.query) != self.query_hash:
            raise ValueError("query_hash must match the embedded Query")
        if not isinstance(self.code, CnAShareCorporateActionFailureCode):
            raise TypeError("code must be CnAShareCorporateActionFailureCode")
        if not isinstance(self.subject_ids, tuple) or len(self.subject_ids) != 5:
            raise ValueError("subject_ids must contain the frozen five identities")
        for value in self.subject_ids:
            _text("subject_id", value)
        expected_subjects = _failure_subject_ids(self.query, self.code)
        if self.subject_ids != expected_subjects:
            raise ValueError("failure subject_ids must match the embedded Query and code")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_corporate_action_failure",
            "schema_version": _SCHEMA_VERSION,
            "component_ref": self.component_ref,
            "rule_book": self.rule_book,
            "calendar": self.calendar,
            "query": self.query,
            "query_hash": self.query_hash,
            "code": self.code.value,
            "subject_ids": self.subject_ids,
        }


def _record_instant(record_date: TradingDate) -> SimulationInstant:
    # ponytail: local close is a frozen ordering boundary, not a clearing timestamp.
    value = datetime.combine(record_date.value, time(hour=15), tzinfo=_TIMEZONE)
    return SimulationInstant(
        UtcInstant.from_datetime(value), _RECORD_PHASE, _RECORD_SEQUENCE
    )


def _share_quantity(
    quantity: Quantity, rate: Rate | None
) -> Quantity | None:
    if rate is None:
        return Quantity(0, Scale(0), quantity.instrument_id)
    numerator = quantity.units * rate.units
    denominator = rate.scale.factor
    units, remainder = divmod(numerator, denominator)
    if remainder:
        return None
    return Quantity(units, Scale(0), quantity.instrument_id)


def _successful_entitlement_values(
    query: CnAShareCorporateActionEntitlementQuery,
    active_band: CnAShareCorporateActionEntitlementBand,
    calendar: CnAShareFrozenCalendar,
) -> tuple[Money, Quantity, Quantity]:
    announcement = query.announcement
    snapshot = query.snapshot
    if announcement is None or snapshot is None:
        raise ValueError("successful entitlement requires Announcement and Snapshot")
    venue = query.instrument.instrument_id.venue
    if (
        _calendar_id(venue.value) is None
        or query.instrument.instrument_type is not InstrumentType.EQUITY
        or query.instrument.quote_currency != _CNY
        or query.instrument.settlement_currency != _CNY
    ):
        raise ValueError("successful entitlement requires a supported CNY Equity")
    if (
        active_band.venue_id != venue
        or active_band.effective_start != _COVERAGE_START
        or active_band.effective_end != _COVERAGE_END
    ):
        raise ValueError("successful entitlement requires the exact frozen Band")
    if (
        announcement.instrument != query.instrument
        or announcement.status
        is not CnAShareCorporateActionAnnouncementStatus.FINAL_IMPLEMENTATION
        or announcement.supersedes_revision_id is not None
        or announcement.announcement_available_at.instant < announcement.event_time
        or announcement.record_date is None
        or announcement.ex_date is None
    ):
        raise ValueError("successful entitlement requires authoritative Announcement evidence")
    has_shares = (
        announcement.bonus_rate is not None
        or announcement.capitalization_rate is not None
    )
    if (
        (announcement.cash_per_share is None and not has_shares)
        or (announcement.cash_per_share is not None and announcement.payment_date is None)
        or (has_shares and announcement.listing_date is None)
        or any(
            value is not None and value.basis != "shares_per_share"
            for value in (announcement.bonus_rate, announcement.capitalization_rate)
        )
        or (venue.value == "xshg" and has_shares)
        or any(
            value is not None and value.units <= 0
            for value in (
                announcement.cash_per_share,
                announcement.bonus_rate,
                announcement.capitalization_rate,
            )
        )
    ):
        raise ValueError("successful entitlement has unsupported distribution terms")
    record_instant = _record_instant(announcement.record_date)
    expected_calendar = _calendar_id(venue.value)
    session_model = CnAShareCashSessionModel(calendar)
    record_session = session_model.resolve_session(
        CnAShareSessionQuery(venue, record_instant.instant)
    )
    next_date = _next_trading_date(calendar, announcement.record_date)
    lifecycle_dates: list[TradingDate | None] = [announcement.ex_date]
    if announcement.cash_per_share is not None:
        lifecycle_dates.append(announcement.payment_date)
    if has_shares:
        lifecycle_dates.append(announcement.listing_date)
    if (
        expected_calendar is None
        or calendar.calendar_id != expected_calendar
        or record_session.result is None
        or record_session.result.day_kind is not CnAShareCalendarDayKind.TRADING
        or record_session.result.phase is not CnAShareSessionPhase.POST_CLOSE
        or record_session.result.trading_date != announcement.record_date
        or next_date is None
        or any(value != next_date for value in lifecycle_dates)
        or announcement.announcement_available_at > record_instant
        or query.captured_at < announcement.announcement_available_at
        or not active_band.contains(record_instant.instant)
    ):
        raise ValueError("successful entitlement has invalid lifecycle evidence")
    if (
        snapshot.supersedes_revision_id is not None
        or snapshot.position_key.account_id
        != snapshot.account_id
        or snapshot.account_id != query.account_id
        or snapshot.position_key.instrument_id != query.instrument.instrument_id
        or snapshot.registered_quantity.instrument_id
        != str(query.instrument.instrument_id)
        or snapshot.eligibility_instant != record_instant
        or snapshot.available_at < snapshot.eligibility_instant
        or snapshot.available_at > query.captured_at
        or snapshot.registered_quantity.scale != Scale(0)
        or snapshot.registered_quantity.units < 0
    ):
        raise ValueError("successful entitlement has invalid registered-position evidence")
    if announcement.cash_per_share is not None and (
        announcement.cash_per_share.currency != "CNY"
        or announcement.cash_per_share.scale != Scale(2)
    ):
        raise ValueError("successful entitlement requires CNY Scale 2 cash")
    bonus = _share_quantity(snapshot.registered_quantity, announcement.bonus_rate)
    capitalization = _share_quantity(
        snapshot.registered_quantity, announcement.capitalization_rate
    )
    if bonus is None or capitalization is None:
        raise ValueError("successful entitlement cannot contain fractional shares")
    gross_cash = Money(
        0
        if announcement.cash_per_share is None
        else snapshot.registered_quantity.units * announcement.cash_per_share.units,
        Scale(2),
        "CNY",
    )
    return gross_cash, bonus, capitalization


@dataclass(frozen=True, slots=True)
class CnAShareCorporateActionEntitlementModel:
    rule_book: CnAShareCorporateActionEntitlementRuleBook
    session_model: CnAShareCashSessionModel

    def __post_init__(self) -> None:
        if not isinstance(self.rule_book, CnAShareCorporateActionEntitlementRuleBook):
            raise TypeError("rule_book must be an entitlement RuleBook")
        if not isinstance(self.session_model, CnAShareCashSessionModel):
            raise TypeError("session_model must be CnAShareCashSessionModel")

    @property
    def component_ref(self) -> ProfileComponentRef:
        return _component_ref(self.rule_book, self.session_model.calendar)

    def apply_corporate_action(
        self, query: CnAShareCorporateActionEntitlementQuery, /
    ) -> ProfilePortOutcome[
        CnAShareCorporateActionEntitlement, CnAShareCorporateActionFailure
    ]:
        if not isinstance(query, CnAShareCorporateActionEntitlementQuery):
            raise TypeError("query must be CnAShareCorporateActionEntitlementQuery")
        announcement = query.announcement
        if announcement is None:
            return self._failure(query, CnAShareCorporateActionFailureCode.MISSING_ANNOUNCEMENT)
        venue = query.instrument.instrument_id.venue
        if _calendar_id(venue.value) is None:
            return self._failure(query, CnAShareCorporateActionFailureCode.UNSUPPORTED_VENUE)
        if query.instrument.instrument_type is not InstrumentType.EQUITY:
            return self._failure(query, CnAShareCorporateActionFailureCode.UNSUPPORTED_INSTRUMENT)
        if (
            query.instrument.quote_currency != _CNY
            or query.instrument.settlement_currency != _CNY
        ):
            return self._failure(query, CnAShareCorporateActionFailureCode.UNSUPPORTED_CURRENCY)
        if announcement.status is not CnAShareCorporateActionAnnouncementStatus.FINAL_IMPLEMENTATION:
            return self._failure(
                query, CnAShareCorporateActionFailureCode.UNSUPPORTED_ANNOUNCEMENT_STATUS
            )
        if announcement.supersedes_revision_id is not None:
            return self._failure(
                query, CnAShareCorporateActionFailureCode.UNSUPPORTED_ANNOUNCEMENT_REVISION
            )
        if announcement.announcement_available_at.instant < announcement.event_time:
            return self._failure(
                query, CnAShareCorporateActionFailureCode.INVALID_ANNOUNCEMENT_CAUSALITY
            )
        components = (
            announcement.cash_per_share,
            announcement.bonus_rate,
            announcement.capitalization_rate,
        )
        if all(value is None for value in components):
            return self._failure(
                query, CnAShareCorporateActionFailureCode.MISSING_DISTRIBUTION_COMPONENT
            )
        if (
            announcement.record_date is None
            or announcement.ex_date is None
            or (announcement.cash_per_share is not None and announcement.payment_date is None)
            or (
                (
                    announcement.bonus_rate is not None
                    or announcement.capitalization_rate is not None
                )
                and announcement.listing_date is None
            )
        ):
            return self._failure(query, CnAShareCorporateActionFailureCode.MISSING_LIFECYCLE_TERM)
        next_trading_date = _next_trading_date(
            self.session_model.calendar, announcement.record_date
        )
        required_dates: list[TradingDate | None] = [announcement.ex_date]
        if announcement.cash_per_share is not None:
            required_dates.append(announcement.payment_date)
        if announcement.bonus_rate is not None or announcement.capitalization_rate is not None:
            required_dates.append(announcement.listing_date)
        if next_trading_date is None or any(
            value != next_trading_date for value in required_dates
        ):
            return self._failure(
                query, CnAShareCorporateActionFailureCode.INVALID_LIFECYCLE_ORDER
            )
        if any(
            value is not None and value.basis != "shares_per_share"
            for value in (announcement.bonus_rate, announcement.capitalization_rate)
        ):
            return self._failure(
                query,
                CnAShareCorporateActionFailureCode.UNSUPPORTED_DISTRIBUTION_RATE_BASIS,
            )
        if venue.value == "xshg" and (
            announcement.bonus_rate is not None
            or announcement.capitalization_rate is not None
        ):
            return self._failure(
                query,
                CnAShareCorporateActionFailureCode.UNSUPPORTED_VENUE_ACTION_COMBINATION,
            )
        if any(value is not None and value.units <= 0 for value in components):
            return self._failure(
                query, CnAShareCorporateActionFailureCode.NON_POSITIVE_DISTRIBUTION_TERM
            )
        if query.captured_at < announcement.announcement_available_at:
            return self._failure(
                query, CnAShareCorporateActionFailureCode.ANNOUNCEMENT_NOT_AVAILABLE
            )
        record_instant = _record_instant(announcement.record_date)
        if announcement.announcement_available_at > record_instant:
            return self._failure(query, CnAShareCorporateActionFailureCode.LATE_ANNOUNCEMENT)
        active = self.rule_book.active_bands(venue, record_instant.instant)
        if not active:
            return self._failure(query, CnAShareCorporateActionFailureCode.MISSING_RULE_INTERVAL)
        if len(active) != 1:
            return self._failure(
                query, CnAShareCorporateActionFailureCode.OVERLAPPING_RULE_INTERVALS
            )
        active_band = active[0]
        if (
            active_band.effective_start != _COVERAGE_START
            or active_band.effective_end != _COVERAGE_END
        ):
            return self._failure(
                query, CnAShareCorporateActionFailureCode.MISSING_RULE_INTERVAL
            )
        expected_calendar = _calendar_id(venue.value)
        if expected_calendar is None:
            raise AssertionError("supported Venue must have a calendar identity")
        session = self.session_model.resolve_session(
            CnAShareSessionQuery(venue, record_instant.instant)
        )
        if (
            session.result is None
            or session.result.day_kind is not CnAShareCalendarDayKind.TRADING
            or session.result.phase is not CnAShareSessionPhase.POST_CLOSE
            or session.result.trading_date != announcement.record_date
            or announcement.record_date.calendar_id != expected_calendar
            or any(
                value is not None and value.calendar_id != expected_calendar
                for value in (
                    announcement.ex_date,
                    announcement.payment_date,
                    announcement.listing_date,
                )
            )
        ):
            return self._failure(query, CnAShareCorporateActionFailureCode.INVALID_RECORD_SESSION)
        snapshot = query.snapshot
        if snapshot is None:
            return self._failure(
                query, CnAShareCorporateActionFailureCode.MISSING_REGISTERED_POSITION
            )
        if snapshot.supersedes_revision_id is not None:
            return self._failure(
                query, CnAShareCorporateActionFailureCode.UNSUPPORTED_REGISTER_REVISION
            )
        if not (
            snapshot.position_key.account_id
            == snapshot.account_id
            == query.account_id
        ):
            return self._failure(query, CnAShareCorporateActionFailureCode.ACCOUNT_MISMATCH)
        if (
            announcement.instrument != query.instrument
            or snapshot.position_key.instrument_id != query.instrument.instrument_id
            or snapshot.registered_quantity.instrument_id
            != str(query.instrument.instrument_id)
        ):
            return self._failure(query, CnAShareCorporateActionFailureCode.INSTRUMENT_MISMATCH)
        if snapshot.eligibility_instant != record_instant:
            return self._failure(
                query, CnAShareCorporateActionFailureCode.RECORD_INSTANT_MISMATCH
            )
        if snapshot.available_at < snapshot.eligibility_instant:
            return self._failure(
                query, CnAShareCorporateActionFailureCode.INVALID_REGISTER_CAUSALITY
            )
        if snapshot.available_at > query.captured_at:
            return self._failure(query, CnAShareCorporateActionFailureCode.REGISTER_NOT_AVAILABLE)
        if snapshot.registered_quantity.units < 0:
            return self._failure(
                query, CnAShareCorporateActionFailureCode.NEGATIVE_REGISTERED_QUANTITY
            )
        if (
            snapshot.registered_quantity.scale != Scale(0)
            or (
                announcement.cash_per_share is not None
                and (
                    announcement.cash_per_share.currency != "CNY"
                    or announcement.cash_per_share.scale != Scale(2)
                )
            )
        ):
            return self._failure(
                query, CnAShareCorporateActionFailureCode.UNSUPPORTED_CASH_PRECISION
            )
        bonus = _share_quantity(snapshot.registered_quantity, announcement.bonus_rate)
        capitalization = _share_quantity(
            snapshot.registered_quantity, announcement.capitalization_rate
        )
        if bonus is None or capitalization is None:
            return self._failure(
                query, CnAShareCorporateActionFailureCode.UNSUPPORTED_FRACTIONAL_SHARE
            )
        gross_cash, bonus, capitalization = _successful_entitlement_values(
            query, active_band, self.session_model.calendar
        )
        result = CnAShareCorporateActionEntitlement(
            component_ref=self.component_ref,
            rule_book=self.rule_book,
            calendar=self.session_model.calendar,
            query=query,
            active_band=active_band,
            band_hash=active_band.band_hash,
            query_hash=canonical_sha256(query),
            candidate_hash=announcement.candidate_hash,
            event_id=announcement.event_id,
            event_hash=announcement.event_hash,
            snapshot_hash=snapshot.snapshot_hash,
            account_id=query.account_id,
            position_key=snapshot.position_key,
            eligibility_instant=record_instant,
            captured_at=query.captured_at,
            registered_quantity=snapshot.registered_quantity,
            gross_cash=gross_cash,
            bonus_quantity=bonus,
            capitalization_quantity=capitalization,
        )
        return ProfilePortOutcome.for_result(self.component_ref, query, result)

    def _failure(
        self,
        query: CnAShareCorporateActionEntitlementQuery,
        code: CnAShareCorporateActionFailureCode,
    ) -> ProfilePortOutcome[
        CnAShareCorporateActionEntitlement, CnAShareCorporateActionFailure
    ]:
        failure = CnAShareCorporateActionFailure(
            component_ref=self.component_ref,
            rule_book=self.rule_book,
            calendar=self.session_model.calendar,
            query=query,
            query_hash=canonical_sha256(query),
            code=code,
            subject_ids=_failure_subject_ids(query, code),
        )
        return ProfilePortOutcome.for_failure(self.component_ref, query, failure)
