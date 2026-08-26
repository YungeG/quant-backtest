from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Literal

from crypto_quant_domain import InstrumentId, UtcInstant, VenueId, canonical_sha256

from .source_snapshots import SourceSnapshot, verify_source_snapshot

_SCHEMA_VERSION = 1
_SNAPSHOT_ID = "sha256:8195e9d9e99949802c829f218929bdbf740b336152d83ad789a060e0355d116e"
_CONTENT_TREE_HASH = "sha256:c315b9b36d5817fc058da240b50e2c170f530f2b2b4b49808554ef6ddedac15b"
_PROVENANCE_HASH = "sha256:cbce2903c280938647526abfc0511cc497d85d61f5486e79469ab0714a9c05a2"
_METADATA_MEMBER = "response/cninfo/announcement-query/000046-v1.json"
_PDF_MEMBER = "response/official/000046/1200788303.pdf"
_PDF_HASH = "sha256:0a5bce6a608fcc444d5405c29e81428efe349370c6d8cc4ba72dca26272bec1c"
_PDF_BYTES = 4_164_254
_REVIEWER_KEY = "quality-bband-pan-hai-2014-balance-review-v1"
_INSTRUMENT_ID = InstrumentId(VenueId("xshe"), "000046")
_PROVIDER_CODE = "000046.SZ"
_FISCAL_PERIOD_END = date(2014, 12, 31)
_PUBLICATION_DATE = date(2015, 4, 4)
_AUDIT_REPORT_DATE = date(2015, 4, 3)
_LIMITATIONS = (
    "REVIEWED_PDF_PAGES_ONLY",
    "NO_PDF_PARSER_AUTHORITY",
    "MIXED_REAL_ESTATE_SECURITIES_LAYOUT",
    "SHORT_TERM_BONDS_NOT_SEPARATELY_PRESENT",
)
_COVERED_MEMBER_KEY = ("balancesheet_vip", "xshe:000046", "20141231")
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DECIMAL = re.compile(r"0|[1-9][0-9]*(?:\.[0-9]+)?\Z")
_CALENDAR_AUTHORITY_ID = (
    "sha256:22585fa4c2070d87544f0ba977be757770aeeaad5bead30188317c1794680ee8"
)
_SOURCE_AVAILABILITY_ID = _SNAPSHOT_ID
_CONSERVATIVE_AVAILABLE = UtcInstant(1_493_688_600_000_000_000)

_FIELD_SPECS = (
    ("money_cap", "货币资金", 77, "VALUE", "11473676835.21"),
    ("total_assets", "资产总计", 78, "VALUE", "70889108573.14"),
    ("total_liab", "负债合计", 79, "VALUE", "58374057829.63"),
    (
        "total_hldr_eqy_inc_min_int",
        "所有者权益合计",
        79,
        "VALUE",
        "12515050743.51",
    ),
    (
        "total_hldr_eqy_exc_min_int",
        "归属于母公司所有者权益合计",
        79,
        "VALUE",
        "9273976463.95",
    ),
    ("minority_int", "少数股东权益", 79, "VALUE", "3241074279.56"),
    (
        "total_liab_hldr_eqy",
        "负债和所有者权益总计",
        79,
        "VALUE",
        "70889108573.14",
    ),
    ("st_borr", "短期借款", 78, "VALUE", "4316020932.89"),
    (
        "non_cur_liab_due_1y",
        "一年内到期的非流动负债",
        79,
        "VALUE",
        "8785180000.00",
    ),
    ("lt_borr", "长期借款", 79, "VALUE", "24359970013.75"),
    ("bond_payable", "应付债券", 79, "VALUE", "2732689313.18"),
    ("st_bonds_payable", None, 79, "NOT_SEPARATELY_PRESENT", None),
)


class BalanceFieldApplicability(str, Enum):
    VALUE = "VALUE"
    NOT_SEPARATELY_PRESENT = "NOT_SEPARATELY_PRESENT"


class PanHai2014OfficialBalanceBackfillFailure(str, Enum):
    INPUT_TYPE_MISMATCH = "INPUT_TYPE_MISMATCH"
    CATALOG_IDENTITY_MISMATCH = "CATALOG_IDENTITY_MISMATCH"
    SOURCE_MEMBER_CONFLICT = "SOURCE_MEMBER_CONFLICT"
    FINANCIAL_REVISION_MISMATCH = "FINANCIAL_REVISION_MISMATCH"
    FINANCIAL_PAYLOAD_INCOMPLETE = "FINANCIAL_PAYLOAD_INCOMPLETE"
    PUBLICATION_INTEGRITY_FAILURE = "PUBLICATION_INTEGRITY_FAILURE"


def _text(name: str, value: object) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or value != unicodedata.normalize("NFC", value)
    ):
        raise ValueError(f"{name} must be canonical non-empty text")
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    if _HASH.fullmatch(text) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return text


def _exact_date(name: str, value: object) -> date:
    if type(value) is not date:
        raise TypeError(f"{name} must be exact date")
    if date.fromisoformat(value.isoformat()) != value:
        raise ValueError(f"{name} must reconstruct exactly")
    return value


def _instant(name: str, value: object) -> UtcInstant:
    if type(value) is not UtcInstant:
        raise TypeError(f"{name} must be exact UtcInstant")
    if type(value.epoch_nanoseconds) is not int or value.epoch_nanoseconds < 0:
        raise ValueError(f"{name} must be a nonnegative exact instant")
    rebuilt = UtcInstant(value.epoch_nanoseconds)
    if rebuilt.to_canonical_dict() != value.to_canonical_dict():
        raise ValueError(f"{name} must reconstruct exactly")
    return rebuilt


def _decimal_text(name: str, value: object) -> str:
    if type(value) is not str or _DECIMAL.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical decimal text")
    try:
        if format(Decimal(value), "f") != value:
            raise ValueError
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{name} must reconstruct exactly through Decimal") from error
    return value


def _unit_multiplier(value: object) -> Decimal:
    expected = Decimal("1")
    if (
        type(value) is not Decimal
        or value.as_tuple() != expected.as_tuple()
    ):
        raise TypeError("unit_multiplier must be exact Decimal('1')")
    return value


@dataclass(frozen=True, slots=True)
class PanHai2014BalanceFieldReviewV1:
    type: Literal["pan_hai_2014_balance_field_review"]
    schema_version: Literal[1]
    field_key: str
    source_label: str | None
    pdf_page: int
    applicability: BalanceFieldApplicability
    value_decimal_text: str | None

    def __post_init__(self) -> None:
        if type(self.type) is not str or self.type != "pan_hai_2014_balance_field_review":
            raise ValueError("field review type mismatch")
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION:
            raise ValueError("field review schema_version mismatch")
        _text("field_key", self.field_key)
        if self.source_label is not None:
            _text("source_label", self.source_label)
        if type(self.pdf_page) is not int or self.pdf_page <= 0:
            raise ValueError("pdf_page must be a positive exact integer")
        if type(self.applicability) is not BalanceFieldApplicability:
            raise TypeError("applicability must be exact BalanceFieldApplicability")
        if self.applicability is BalanceFieldApplicability.VALUE:
            if self.source_label is None or self.value_decimal_text is None:
                raise ValueError("VALUE requires source label and decimal text")
            _decimal_text("value_decimal_text", self.value_decimal_text)
        elif self.source_label is not None or self.value_decimal_text is not None:
            raise ValueError("NOT_SEPARATELY_PRESENT requires null label and value")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": self.type,
            "schema_version": self.schema_version,
            "field_key": self.field_key,
            "source_label": self.source_label,
            "pdf_page": self.pdf_page,
            "applicability": self.applicability.value,
            "value_decimal_text": self.value_decimal_text,
        }


@dataclass(frozen=True, slots=True)
class PanHai2014ReviewedBalanceEvidenceV1:
    type: Literal["pan_hai_2014_reviewed_balance_evidence"]
    schema_version: Literal[1]
    reviewer_key: str
    reviewed_at_epoch_nanoseconds: int
    pdf_member_key: str
    metadata_member_key: str
    statement_pages: tuple[int, int, int]
    audit_page: int
    statement_title: str
    issuer_name: str
    provider_code: str
    fiscal_period_end_date: date
    publication_date: date
    currency: str
    unit_text: str
    unit_multiplier: Decimal
    consolidation: str
    company_layout: str
    audit_opinion: str
    audit_report_date: date
    audit_report_number: str
    field_reviews: tuple[PanHai2014BalanceFieldReviewV1, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.type) is not str or self.type != "pan_hai_2014_reviewed_balance_evidence":
            raise ValueError("reviewed evidence type mismatch")
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION:
            raise ValueError("reviewed evidence schema_version mismatch")
        for name in (
            "reviewer_key",
            "pdf_member_key",
            "metadata_member_key",
            "statement_title",
            "issuer_name",
            "provider_code",
            "currency",
            "unit_text",
            "consolidation",
            "company_layout",
            "audit_opinion",
            "audit_report_number",
        ):
            _text(name, getattr(self, name))
        if (
            type(self.reviewed_at_epoch_nanoseconds) is not int
            or self.reviewed_at_epoch_nanoseconds < 0
        ):
            raise ValueError("reviewed_at_epoch_nanoseconds must be nonnegative integer")
        if (
            type(self.statement_pages) is not tuple
            or len(self.statement_pages) != 3
            or any(type(page) is not int or page <= 0 for page in self.statement_pages)
        ):
            raise TypeError("statement_pages must be an exact three-page tuple")
        if type(self.audit_page) is not int or self.audit_page <= 0:
            raise ValueError("audit_page must be a positive exact integer")
        _exact_date("fiscal_period_end_date", self.fiscal_period_end_date)
        _exact_date("publication_date", self.publication_date)
        _exact_date("audit_report_date", self.audit_report_date)
        _unit_multiplier(self.unit_multiplier)
        if type(self.field_reviews) is not tuple or any(
            type(review) is not PanHai2014BalanceFieldReviewV1
            for review in self.field_reviews
        ):
            raise TypeError("field_reviews must be exact field-review tuple")
        if type(self.limitations) is not tuple or any(
            type(value) is not str for value in self.limitations
        ):
            raise TypeError("limitations must be exact text tuple")
        for value in self.limitations:
            _text("limitation", value)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": self.type,
            "schema_version": self.schema_version,
            "reviewer_key": self.reviewer_key,
            "reviewed_at_epoch_nanoseconds": self.reviewed_at_epoch_nanoseconds,
            "pdf_member_key": self.pdf_member_key,
            "metadata_member_key": self.metadata_member_key,
            "statement_pages": self.statement_pages,
            "audit_page": self.audit_page,
            "statement_title": self.statement_title,
            "issuer_name": self.issuer_name,
            "provider_code": self.provider_code,
            "fiscal_period_end_date": self.fiscal_period_end_date.isoformat(),
            "publication_date": self.publication_date.isoformat(),
            "currency": self.currency,
            "unit_text": self.unit_text,
            "unit_multiplier": format(self.unit_multiplier, "f"),
            "consolidation": self.consolidation,
            "company_layout": self.company_layout,
            "audit_opinion": self.audit_opinion,
            "audit_report_date": self.audit_report_date.isoformat(),
            "audit_report_number": self.audit_report_number,
            "field_reviews": tuple(
                review.to_canonical_dict() for review in self.field_reviews
            ),
            "limitations": self.limitations,
        }


@dataclass(frozen=True, slots=True)
class PanHai2014BalanceAvailabilityV1:
    type: Literal["pan_hai_2014_balance_availability"]
    schema_version: Literal[1]
    availability_id: str
    pdf_member_key: str
    source_publication_date: date
    source_visibility_at: UtcInstant
    publication_boundary_at: UtcInstant
    available_at: UtcInstant
    calendar_authority_id: str
    source_availability_id: str

    def __post_init__(self) -> None:
        if type(self.type) is not str or self.type != "pan_hai_2014_balance_availability":
            raise ValueError("availability type mismatch")
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION:
            raise ValueError("availability schema_version mismatch")
        _hash("availability_id", self.availability_id)
        _text("pdf_member_key", self.pdf_member_key)
        _exact_date("source_publication_date", self.source_publication_date)
        for name in (
            "source_visibility_at",
            "publication_boundary_at",
            "available_at",
        ):
            _instant(name, getattr(self, name))
        _hash("calendar_authority_id", self.calendar_authority_id)
        _hash("source_availability_id", self.source_availability_id)

    def _body(self) -> dict[str, object]:
        return {
            "type": self.type,
            "schema_version": self.schema_version,
            "pdf_member_key": self.pdf_member_key,
            "source_publication_date": self.source_publication_date.isoformat(),
            "source_visibility_at": self.source_visibility_at.to_canonical_dict(),
            "publication_boundary_at": self.publication_boundary_at.to_canonical_dict(),
            "available_at": self.available_at.to_canonical_dict(),
            "calendar_authority_id": self.calendar_authority_id,
            "source_availability_id": self.source_availability_id,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "availability_id": self.availability_id}


@dataclass(frozen=True, slots=True)
class PanHai2014OfficialBalanceBackfillRequestV1:
    type: Literal["pan_hai_2014_official_balance_backfill_request"]
    schema_version: Literal[1]
    source_snapshot: SourceSnapshot
    reviewed_evidence: PanHai2014ReviewedBalanceEvidenceV1
    availability: PanHai2014BalanceAvailabilityV1

    def __post_init__(self) -> None:
        if (
            type(self.type) is not str
            or self.type != "pan_hai_2014_official_balance_backfill_request"
        ):
            raise ValueError("request type mismatch")
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION:
            raise ValueError("request schema_version mismatch")
        if type(self.source_snapshot) is not SourceSnapshot:
            raise TypeError("source_snapshot must be exact SourceSnapshot")
        if type(self.reviewed_evidence) is not PanHai2014ReviewedBalanceEvidenceV1:
            raise TypeError("reviewed_evidence must be exact reviewed evidence")
        if type(self.availability) is not PanHai2014BalanceAvailabilityV1:
            raise TypeError("availability must be exact balance availability")


@dataclass(frozen=True, slots=True)
class PanHai2014OfficialBalanceBackfillV1:
    type: Literal["pan_hai_2014_official_balance_backfill"]
    schema_version: Literal[1]
    backfill_id: str
    instrument_id: InstrumentId
    provider_code: str
    api_name: str
    period: str
    statement_kind: str
    source_snapshot_id: str
    source_content_tree_hash: str
    source_provenance_hash: str
    reviewed_evidence: PanHai2014ReviewedBalanceEvidenceV1
    availability: PanHai2014BalanceAvailabilityV1
    field_reviews: tuple[PanHai2014BalanceFieldReviewV1, ...]
    covered_member_key: tuple[str, str, str]
    financial_payload_complete: bool
    financial_scope_qualified: bool
    scope_reason: str
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.type) is not str or self.type != "pan_hai_2014_official_balance_backfill":
            raise ValueError("backfill type mismatch")
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION:
            raise ValueError("backfill schema_version mismatch")
        if (
            type(self.instrument_id) is not InstrumentId
            or type(self.instrument_id.venue) is not VenueId
            or type(self.instrument_id.stable_key) is not str
            or self.instrument_id != _INSTRUMENT_ID
            or self.provider_code != _PROVIDER_CODE
            or self.api_name != "balancesheet_vip"
            or self.period != "20141231"
            or self.statement_kind != "BALANCE_SHEET"
        ):
            raise ValueError("backfill catalog identity mismatch")
        for name in (
            "source_snapshot_id",
            "source_content_tree_hash",
            "source_provenance_hash",
        ):
            _hash(name, getattr(self, name))
        if (
            self.source_snapshot_id != _SNAPSHOT_ID
            or self.source_content_tree_hash != _CONTENT_TREE_HASH
            or self.source_provenance_hash != _PROVENANCE_HASH
        ):
            raise ValueError("backfill source identity mismatch")
        if type(self.reviewed_evidence) is not PanHai2014ReviewedBalanceEvidenceV1:
            raise TypeError("backfill reviewed evidence mismatch")
        if type(self.availability) is not PanHai2014BalanceAvailabilityV1:
            raise TypeError("backfill availability mismatch")
        if (
            not _identity_valid(self.reviewed_evidence)
            or self.reviewed_evidence.pdf_member_key != _PDF_MEMBER
            or self.reviewed_evidence.metadata_member_key != _METADATA_MEMBER
            or not _field_payload_valid(self.reviewed_evidence)
        ):
            raise ValueError("backfill reviewed payload mismatch")
        if not _availability_identity_valid(
            self.reviewed_evidence, self.availability
        ):
            raise ValueError("backfill availability reconstruction mismatch")
        if (
            type(self.field_reviews) is not tuple
            or self.field_reviews != self.reviewed_evidence.field_reviews
            or self.covered_member_key != _COVERED_MEMBER_KEY
        ):
            raise ValueError("backfill exact cover mismatch")
        if (
            type(self.financial_payload_complete) is not bool
            or self.financial_payload_complete
            or type(self.financial_scope_qualified) is not bool
            or self.financial_scope_qualified
            or self.scope_reason != "STATEMENT_SCOPE_UNSUPPORTED"
            or self.limitations != _LIMITATIONS
            or self.reviewed_evidence.limitations != self.limitations
        ):
            raise ValueError("backfill unsupported scope mismatch")
        expected = canonical_sha256(self._body())
        if type(self.backfill_id) is not str:
            raise TypeError("backfill_id must be exact str")
        if self.backfill_id == "":
            object.__setattr__(self, "backfill_id", expected)
        else:
            _hash("backfill_id", self.backfill_id)
            if self.backfill_id != expected:
                raise ValueError("backfill reconstruction hash mismatch")

    def _body(self) -> dict[str, object]:
        return {
            "type": self.type,
            "schema_version": self.schema_version,
            "instrument_id": self.instrument_id.to_canonical_dict(),
            "provider_code": self.provider_code,
            "api_name": self.api_name,
            "period": self.period,
            "statement_kind": self.statement_kind,
            "source_snapshot_id": self.source_snapshot_id,
            "source_content_tree_hash": self.source_content_tree_hash,
            "source_provenance_hash": self.source_provenance_hash,
            "reviewed_evidence": self.reviewed_evidence.to_canonical_dict(),
            "availability": self.availability.to_canonical_dict(),
            "field_reviews": tuple(
                review.to_canonical_dict() for review in self.field_reviews
            ),
            "covered_member_key": self.covered_member_key,
            "financial_payload_complete": self.financial_payload_complete,
            "financial_scope_qualified": self.financial_scope_qualified,
            "scope_reason": self.scope_reason,
            "limitations": self.limitations,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "backfill_id": self.backfill_id}


@dataclass(frozen=True, slots=True)
class PanHai2014OfficialBalanceBackfillOutcome:
    backfill: PanHai2014OfficialBalanceBackfillV1 | None
    failure: PanHai2014OfficialBalanceBackfillFailure | None

    def __post_init__(self) -> None:
        if (self.backfill is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one backfill or failure")
        if self.backfill is not None and type(self.backfill) is not PanHai2014OfficialBalanceBackfillV1:
            raise TypeError("backfill must be exact PanHai2014OfficialBalanceBackfillV1")
        if self.failure is not None and type(self.failure) is not PanHai2014OfficialBalanceBackfillFailure:
            raise TypeError("failure must be exact PanHai2014OfficialBalanceBackfillFailure")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "pan_hai_2014_official_balance_backfill_outcome",
            "schema_version": _SCHEMA_VERSION,
            "backfill": None if self.backfill is None else self.backfill.to_canonical_dict(),
            "failure": None if self.failure is None else self.failure.value,
        }


def _failed(
    code: PanHai2014OfficialBalanceBackfillFailure,
) -> PanHai2014OfficialBalanceBackfillOutcome:
    return PanHai2014OfficialBalanceBackfillOutcome(None, code)


def _dataclass_values(value: object, class_type: type[object]) -> dict[str, object]:
    return {name: getattr(value, name) for name in class_type.__dataclass_fields__}


def _trusted_request(
    value: object,
) -> PanHai2014OfficialBalanceBackfillRequestV1 | None:
    if type(value) is not PanHai2014OfficialBalanceBackfillRequestV1:
        return None
    try:
        evidence = value.reviewed_evidence
        if (
            type(evidence) is not PanHai2014ReviewedBalanceEvidenceV1
            or type(evidence.statement_pages) is not tuple
            or type(evidence.field_reviews) is not tuple
            or type(evidence.limitations) is not tuple
            or any(
                type(review) is not PanHai2014BalanceFieldReviewV1
                for review in evidence.field_reviews
            )
            or type(value.availability) is not PanHai2014BalanceAvailabilityV1
        ):
            return None
        reviews = tuple(
            PanHai2014BalanceFieldReviewV1(
                **_dataclass_values(review, PanHai2014BalanceFieldReviewV1)
            )
            for review in evidence.field_reviews
        )
        rebuilt_evidence = PanHai2014ReviewedBalanceEvidenceV1(
            **{
                **_dataclass_values(evidence, PanHai2014ReviewedBalanceEvidenceV1),
                "field_reviews": reviews,
            }
        )
        availability = PanHai2014BalanceAvailabilityV1(
            **_dataclass_values(value.availability, PanHai2014BalanceAvailabilityV1)
        )
        rebuilt = PanHai2014OfficialBalanceBackfillRequestV1(
            type=value.type,
            schema_version=value.schema_version,
            source_snapshot=value.source_snapshot,
            reviewed_evidence=rebuilt_evidence,
            availability=availability,
        )
        if (
            rebuilt_evidence.to_canonical_dict()
            != value.reviewed_evidence.to_canonical_dict()
            or availability.to_canonical_dict() != value.availability.to_canonical_dict()
        ):
            return None
        return rebuilt
    except (AttributeError, InvalidOperation, TypeError, ValueError):
        return None


def _source_valid(request: PanHai2014OfficialBalanceBackfillRequestV1) -> bool:
    snapshot = request.source_snapshot
    try:
        verified = verify_source_snapshot(snapshot)
    except (AttributeError, TypeError, ValueError):
        return False
    if (
        verified.snapshot is None
        or snapshot.snapshot_id != _SNAPSHOT_ID
        or snapshot.content_tree_hash != _CONTENT_TREE_HASH
        or snapshot.provenance_hash != _PROVENANCE_HASH
    ):
        return False
    members = {member.member_key: member for member in snapshot.members}
    pdf = members.get(_PDF_MEMBER)
    return (
        _METADATA_MEMBER in members
        and pdf is not None
        and pdf.content_hash == _PDF_HASH
        and pdf.byte_count == _PDF_BYTES
        and request.reviewed_evidence.pdf_member_key == _PDF_MEMBER
        and request.reviewed_evidence.metadata_member_key == _METADATA_MEMBER
    )


def _identity_valid(evidence: PanHai2014ReviewedBalanceEvidenceV1) -> bool:
    return (
        evidence.provider_code == _PROVIDER_CODE
        and evidence.fiscal_period_end_date == _FISCAL_PERIOD_END
    )


def _availability_identity_valid(
    evidence: PanHai2014ReviewedBalanceEvidenceV1,
    availability: PanHai2014BalanceAvailabilityV1,
) -> bool:
    try:
        return (
            availability.pdf_member_key == _PDF_MEMBER
            and availability.source_publication_date == _PUBLICATION_DATE
            and evidence.publication_date == _PUBLICATION_DATE
            and availability.source_visibility_at == _CONSERVATIVE_AVAILABLE
            and availability.publication_boundary_at == _CONSERVATIVE_AVAILABLE
            and availability.available_at == _CONSERVATIVE_AVAILABLE
            and availability.calendar_authority_id == _CALENDAR_AUTHORITY_ID
            and availability.source_availability_id
            == _SOURCE_AVAILABILITY_ID
            == _SNAPSHOT_ID
            and evidence.reviewed_at_epoch_nanoseconds
            >= availability.available_at.epoch_nanoseconds
            and availability.availability_id == canonical_sha256(availability._body())
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _availability_valid(
    evidence: PanHai2014ReviewedBalanceEvidenceV1,
    availability: PanHai2014BalanceAvailabilityV1,
    source_snapshot: SourceSnapshot,
) -> bool:
    try:
        return (
            evidence.reviewed_at_epoch_nanoseconds
            >= max(member.acquired_at_epoch_nanoseconds for member in source_snapshot.members)
            and _availability_identity_valid(evidence, availability)
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _field_payload_valid(
    evidence: PanHai2014ReviewedBalanceEvidenceV1,
) -> bool:
    expected_context = (
        evidence.reviewer_key == _REVIEWER_KEY
        and evidence.statement_pages == (77, 78, 79)
        and evidence.audit_page == 76
        and evidence.statement_title == "合并资产负债表"
        and evidence.issuer_name == "泛海控股股份有限公司"
        and evidence.currency == "CNY"
        and evidence.unit_text == "人民币元"
        and evidence.unit_multiplier == Decimal("1")
        and evidence.consolidation == "CONSOLIDATED"
        and evidence.company_layout
        == "MIXED_REAL_ESTATE_SECURITIES_CONSOLIDATION"
        and evidence.audit_opinion == "STANDARD_UNQUALIFIED"
        and evidence.audit_report_date == _AUDIT_REPORT_DATE
        and evidence.audit_report_number == "信会师报字[2015]第310292号"
        and evidence.limitations == _LIMITATIONS
    )
    actual_specs = tuple(
        (
            review.field_key,
            review.source_label,
            review.pdf_page,
            review.applicability.value,
            review.value_decimal_text,
        )
        for review in evidence.field_reviews
    )
    if not expected_context or actual_specs != _FIELD_SPECS:
        return False
    values = {
        review.field_key: Decimal(review.value_decimal_text)
        for review in evidence.field_reviews
        if review.value_decimal_text is not None
    }
    return (
        values["total_assets"]
        == values["total_liab"] + values["total_hldr_eqy_inc_min_int"]
        and values["total_hldr_eqy_inc_min_int"]
        == values["total_hldr_eqy_exc_min_int"] + values["minority_int"]
        and values["total_liab_hldr_eqy"] == values["total_assets"]
    )


def _build_backfill(
    request: PanHai2014OfficialBalanceBackfillRequestV1,
) -> PanHai2014OfficialBalanceBackfillV1:
    snapshot = request.source_snapshot
    evidence = request.reviewed_evidence
    return PanHai2014OfficialBalanceBackfillV1(
        type="pan_hai_2014_official_balance_backfill",
        schema_version=_SCHEMA_VERSION,
        backfill_id="",
        instrument_id=_INSTRUMENT_ID,
        provider_code=_PROVIDER_CODE,
        api_name="balancesheet_vip",
        period="20141231",
        statement_kind="BALANCE_SHEET",
        source_snapshot_id=snapshot.snapshot_id,
        source_content_tree_hash=snapshot.content_tree_hash,
        source_provenance_hash=snapshot.provenance_hash,
        reviewed_evidence=evidence,
        availability=request.availability,
        field_reviews=evidence.field_reviews,
        covered_member_key=_COVERED_MEMBER_KEY,
        financial_payload_complete=False,
        financial_scope_qualified=False,
        scope_reason="STATEMENT_SCOPE_UNSUPPORTED",
        limitations=_LIMITATIONS,
    )


def build_pan_hai_2014_official_balance_backfill_v1(
    request: PanHai2014OfficialBalanceBackfillRequestV1,
) -> PanHai2014OfficialBalanceBackfillOutcome:
    trusted = _trusted_request(request)
    if trusted is None:
        return _failed(PanHai2014OfficialBalanceBackfillFailure.INPUT_TYPE_MISMATCH)
    if not _identity_valid(trusted.reviewed_evidence):
        return _failed(
            PanHai2014OfficialBalanceBackfillFailure.CATALOG_IDENTITY_MISMATCH
        )
    if not _source_valid(trusted):
        return _failed(PanHai2014OfficialBalanceBackfillFailure.SOURCE_MEMBER_CONFLICT)
    if not _availability_valid(
        trusted.reviewed_evidence,
        trusted.availability,
        trusted.source_snapshot,
    ):
        return _failed(
            PanHai2014OfficialBalanceBackfillFailure.FINANCIAL_REVISION_MISMATCH
        )
    if not _field_payload_valid(trusted.reviewed_evidence):
        return _failed(
            PanHai2014OfficialBalanceBackfillFailure.FINANCIAL_PAYLOAD_INCOMPLETE
        )
    try:
        backfill = _build_backfill(trusted)
        rebuilt = PanHai2014OfficialBalanceBackfillV1(
            **_dataclass_values(backfill, PanHai2014OfficialBalanceBackfillV1)
        )
        if rebuilt.to_canonical_dict() != backfill.to_canonical_dict():
            raise ValueError("backfill reconstruction mismatch")
    except (AttributeError, InvalidOperation, TypeError, ValueError) as error:
        message = str(error)
        if "catalog identity" in message:
            return _failed(
                PanHai2014OfficialBalanceBackfillFailure.CATALOG_IDENTITY_MISMATCH
            )
        if "source identity" in message:
            return _failed(
                PanHai2014OfficialBalanceBackfillFailure.SOURCE_MEMBER_CONFLICT
            )
        if "availability" in message:
            return _failed(
                PanHai2014OfficialBalanceBackfillFailure.FINANCIAL_REVISION_MISMATCH
            )
        if "payload" in message or "exact cover" in message:
            return _failed(
                PanHai2014OfficialBalanceBackfillFailure.FINANCIAL_PAYLOAD_INCOMPLETE
            )
        return _failed(
            PanHai2014OfficialBalanceBackfillFailure.PUBLICATION_INTEGRITY_FAILURE
        )
    return PanHai2014OfficialBalanceBackfillOutcome(rebuilt, None)
