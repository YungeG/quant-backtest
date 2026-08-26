from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Literal

from crypto_quant_domain import InstrumentId, UtcInstant, VenueId, canonical_sha256

from .source_snapshots import SourceSnapshot, verify_source_snapshot

_SCHEMA_VERSION = 1
_REVIEWER_KEY = "quality-bband-eight-issuer-official-authority-audit-v1"
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_PROVIDER_CODE = re.compile(r"([0-9]{6})\.(SZ|SH)\Z")
_DAY_NS = 86_400_000_000_000
_EPOCH_DATE = date(1970, 1, 1)
_COVERED_API_NAMES = ("income_vip", "balancesheet_vip", "cashflow_vip")
_COVERED_STATEMENT_KINDS = (
    "INCOME_STATEMENT",
    "BALANCE_SHEET",
    "CASH_FLOW_STATEMENT",
)


class NonFilingDocumentRole(str, Enum):
    INITIAL_NONFILING_PROOF = "INITIAL_NONFILING_PROOF"
    TERMINAL_CONFIRMATION = "TERMINAL_CONFIRMATION"


class NonFilingAuthority(str, Enum):
    ISSUER = "ISSUER"
    SSE = "SSE"
    SZSE = "SZSE"
    CSRC = "CSRC"
    CSRC_BRANCH = "CSRC_BRANCH"


class OfficialAnnualReportNonFilingFailure(str, Enum):
    INPUT_TYPE_MISMATCH = "INPUT_TYPE_MISMATCH"
    CATALOG_IDENTITY_MISMATCH = "CATALOG_IDENTITY_MISMATCH"
    SOURCE_MEMBER_CONFLICT = "SOURCE_MEMBER_CONFLICT"
    FINANCIAL_REVISION_MISMATCH = "FINANCIAL_REVISION_MISMATCH"
    BUNDLE_EXACT_COVER_MISMATCH = "BUNDLE_EXACT_COVER_MISMATCH"
    PUBLICATION_INTEGRITY_FAILURE = "PUBLICATION_INTEGRITY_FAILURE"


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
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


def _utc_day_index(value: UtcInstant) -> int:
    return value.epoch_nanoseconds // _DAY_NS


def _date_day_index(value: date) -> int:
    return (value - _EPOCH_DATE).days


def _date_start_ns(value: date) -> int:
    return (value - _EPOCH_DATE).days * _DAY_NS


def _provider_identity_matches(instrument_id: InstrumentId, provider_code: str) -> bool:
    if (
        type(instrument_id) is not InstrumentId
        or type(instrument_id.venue) is not VenueId
        or type(instrument_id.stable_key) is not str
        or type(provider_code) is not str
    ):
        return False
    match = _PROVIDER_CODE.fullmatch(provider_code)
    if match is None:
        return False
    code, suffix = match.groups()
    return instrument_id == InstrumentId(
        VenueId("xshe" if suffix == "SZ" else "xshg"), code
    )


@dataclass(frozen=True, slots=True)
class ReviewedNonFilingDocumentV1:
    type: Literal["reviewed_nonfiling_document"]
    schema_version: Literal[1]
    role: NonFilingDocumentRole
    authority: NonFilingAuthority
    member_key: str
    source_url: str
    published_date: date
    publication_precision: Literal["DATE_ONLY", "EXACT_INSTANT"]
    published_at_epoch_nanoseconds: int | None
    content_hash: str
    byte_count: int
    reviewed_pages: tuple[int, ...]
    reviewed_excerpt: str
    issuer_assertion: str
    period_assertion: str
    supersedes_member_key: str | None
    reviewer_key: Literal["quality-bband-eight-issuer-official-authority-audit-v1"]
    reviewed_at_epoch_nanoseconds: int

    def __post_init__(self) -> None:
        if type(self.type) is not str or self.type != "reviewed_nonfiling_document":
            raise ValueError("reviewed document type mismatch")
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION:
            raise ValueError("reviewed document schema_version mismatch")
        if type(self.role) is not NonFilingDocumentRole:
            raise TypeError("role must be exact NonFilingDocumentRole")
        if type(self.authority) is not NonFilingAuthority:
            raise TypeError("authority must be exact NonFilingAuthority")
        for name in (
            "member_key",
            "source_url",
            "reviewed_excerpt",
            "issuer_assertion",
            "period_assertion",
        ):
            _text(name, getattr(self, name))
        _exact_date("published_date", self.published_date)
        if type(self.publication_precision) is not str or self.publication_precision not in {
            "DATE_ONLY",
            "EXACT_INSTANT",
        }:
            raise ValueError("publication_precision mismatch")
        if self.publication_precision == "EXACT_INSTANT":
            if (
                type(self.published_at_epoch_nanoseconds) is not int
                or self.published_at_epoch_nanoseconds < 0
            ):
                raise ValueError("EXACT_INSTANT requires nonnegative publication instant")
        elif self.published_at_epoch_nanoseconds is not None:
            raise ValueError("DATE_ONLY requires null publication instant")
        _hash("content_hash", self.content_hash)
        if type(self.byte_count) is not int or self.byte_count <= 0:
            raise ValueError("byte_count must be a positive integer")
        if (
            type(self.reviewed_pages) is not tuple
            or not self.reviewed_pages
            or any(type(page) is not int or page <= 0 for page in self.reviewed_pages)
            or tuple(sorted(self.reviewed_pages)) != self.reviewed_pages
            or len(set(self.reviewed_pages)) != len(self.reviewed_pages)
        ):
            raise ValueError("reviewed_pages must be positive, unique, and increasing")
        if self.supersedes_member_key is not None:
            _text("supersedes_member_key", self.supersedes_member_key)
        if type(self.reviewer_key) is not str or self.reviewer_key != _REVIEWER_KEY:
            raise ValueError("reviewer_key mismatch")
        if (
            type(self.reviewed_at_epoch_nanoseconds) is not int
            or self.reviewed_at_epoch_nanoseconds < 0
        ):
            raise ValueError("reviewed_at_epoch_nanoseconds must be nonnegative integer")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": self.type,
            "schema_version": self.schema_version,
            "role": self.role.value,
            "authority": self.authority.value,
            "member_key": self.member_key,
            "source_url": self.source_url,
            "published_date": self.published_date.isoformat(),
            "publication_precision": self.publication_precision,
            "published_at_epoch_nanoseconds": self.published_at_epoch_nanoseconds,
            "content_hash": self.content_hash,
            "byte_count": self.byte_count,
            "reviewed_pages": self.reviewed_pages,
            "reviewed_excerpt": self.reviewed_excerpt,
            "issuer_assertion": self.issuer_assertion,
            "period_assertion": self.period_assertion,
            "supersedes_member_key": self.supersedes_member_key,
            "reviewer_key": self.reviewer_key,
            "reviewed_at_epoch_nanoseconds": self.reviewed_at_epoch_nanoseconds,
        }


@dataclass(frozen=True, slots=True)
class OfficialNonFilingAvailabilityV1:
    type: Literal["official_nonfiling_availability"]
    schema_version: Literal[1]
    availability_id: str
    document_member_key: str
    source_visibility_at: UtcInstant
    deadline_boundary_at: UtcInstant
    available_at: UtcInstant
    calendar_authority_id: str
    source_availability_id: str

    def __post_init__(self) -> None:
        if type(self.type) is not str or self.type != "official_nonfiling_availability":
            raise ValueError("availability type mismatch")
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION:
            raise ValueError("availability schema_version mismatch")
        _hash("availability_id", self.availability_id)
        _text("document_member_key", self.document_member_key)
        _instant("source_visibility_at", self.source_visibility_at)
        _instant("deadline_boundary_at", self.deadline_boundary_at)
        _instant("available_at", self.available_at)
        _hash("calendar_authority_id", self.calendar_authority_id)
        _hash("source_availability_id", self.source_availability_id)

    def _body(self) -> dict[str, object]:
        return {
            "type": self.type,
            "schema_version": self.schema_version,
            "document_member_key": self.document_member_key,
            "source_visibility_at": self.source_visibility_at,
            "deadline_boundary_at": self.deadline_boundary_at,
            "available_at": self.available_at,
            "calendar_authority_id": self.calendar_authority_id,
            "source_availability_id": self.source_availability_id,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "availability_id": self.availability_id}


@dataclass(frozen=True, slots=True)
class OfficialAnnualReportNonFilingRequestV1:
    type: Literal["official_annual_report_nonfiling_request"]
    schema_version: Literal[1]
    instrument_id: InstrumentId
    provider_code: str
    fiscal_period_end_date: date
    statutory_deadline_date: date
    source_snapshot: SourceSnapshot
    source_documents: tuple[ReviewedNonFilingDocumentV1, ReviewedNonFilingDocumentV1]
    initial_availability: OfficialNonFilingAvailabilityV1
    terminal_availability: OfficialNonFilingAvailabilityV1
    active_interval_end: UtcInstant
    terminal_confirmation_fact_date: date
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.type) is not str or self.type != "official_annual_report_nonfiling_request":
            raise ValueError("request type mismatch")
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION:
            raise ValueError("request schema_version mismatch")
        if (
            type(self.instrument_id) is not InstrumentId
            or type(self.instrument_id.venue) is not VenueId
            or type(self.instrument_id.stable_key) is not str
        ):
            raise TypeError("instrument_id must be exact InstrumentId")
        _text("provider_code", self.provider_code)
        _exact_date("fiscal_period_end_date", self.fiscal_period_end_date)
        _exact_date("statutory_deadline_date", self.statutory_deadline_date)
        if type(self.source_snapshot) is not SourceSnapshot:
            raise TypeError("source_snapshot must be exact SourceSnapshot")
        if type(self.source_documents) is not tuple or len(self.source_documents) != 2 or any(
            type(value) is not ReviewedNonFilingDocumentV1 for value in self.source_documents
        ):
            raise TypeError("source_documents must be an exact two-document tuple")
        if type(self.initial_availability) is not OfficialNonFilingAvailabilityV1 or type(
            self.terminal_availability
        ) is not OfficialNonFilingAvailabilityV1:
            raise TypeError("availability values must be exact OfficialNonFilingAvailabilityV1")
        _instant("active_interval_end", self.active_interval_end)
        _exact_date("terminal_confirmation_fact_date", self.terminal_confirmation_fact_date)
        if type(self.limitations) is not tuple or not self.limitations:
            raise TypeError("limitations must be a nonempty tuple")
        for value in self.limitations:
            _text("limitation", value)
        if len(set(self.limitations)) != len(self.limitations):
            raise ValueError("limitations must be unique")


@dataclass(frozen=True, slots=True)
class OfficialAnnualReportNonFilingDeclarationV1:
    type: Literal["official_annual_report_nonfiling_declaration"]
    schema_version: Literal[1]
    declaration_id: str
    instrument_id: InstrumentId
    provider_code: str
    fiscal_period_end_date: date
    statutory_deadline_date: date
    filing_status: Literal["NOT_FILED_BY_STATUTORY_DEADLINE"]
    economic_effective_date: date
    initial_availability: OfficialNonFilingAvailabilityV1
    terminal_availability: OfficialNonFilingAvailabilityV1
    available_at: UtcInstant
    active_interval_start: UtcInstant
    active_interval_end: UtcInstant
    covered_api_names: tuple[str, str, str]
    covered_statement_kinds: tuple[str, str, str]
    source_snapshot_id: str
    source_content_tree_hash: str
    source_provenance_hash: str
    source_document_refs: tuple[ReviewedNonFilingDocumentV1, ReviewedNonFilingDocumentV1]
    terminal_confirmation: Literal["NOT_FILED_THROUGH_LISTING_TERMINATION"]
    terminal_confirmation_fact_date: date
    terminal_confirmation_available_at: UtcInstant
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.type) is not str or self.type != "official_annual_report_nonfiling_declaration":
            raise ValueError("declaration type mismatch")
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION:
            raise ValueError("declaration schema_version mismatch")
        if (
            type(self.instrument_id) is not InstrumentId
            or type(self.instrument_id.venue) is not VenueId
            or type(self.instrument_id.stable_key) is not str
        ):
            raise TypeError("instrument_id must be exact InstrumentId")
        _text("provider_code", self.provider_code)
        if not _provider_identity_matches(self.instrument_id, self.provider_code):
            raise ValueError("declaration provider identity mismatch")
        _exact_date("fiscal_period_end_date", self.fiscal_period_end_date)
        _exact_date("statutory_deadline_date", self.statutory_deadline_date)
        _exact_date("economic_effective_date", self.economic_effective_date)
        if type(self.filing_status) is not str or self.filing_status != "NOT_FILED_BY_STATUTORY_DEADLINE":
            raise ValueError("filing_status mismatch")
        if self.economic_effective_date != self.statutory_deadline_date:
            raise ValueError("economic effective date mismatch")
        if type(self.initial_availability) is not OfficialNonFilingAvailabilityV1 or type(
            self.terminal_availability
        ) is not OfficialNonFilingAvailabilityV1:
            raise TypeError("declaration availability mismatch")
        for name in (
            "available_at",
            "active_interval_start",
            "active_interval_end",
            "terminal_confirmation_available_at",
        ):
            _instant(name, getattr(self, name))
        if (
            self.available_at != self.active_interval_start
            or self.available_at != self.initial_availability.available_at
            or self.terminal_confirmation_available_at != self.terminal_availability.available_at
            or self.active_interval_end <= self.active_interval_start
        ):
            raise ValueError("declaration active interval mismatch")
        if (
            type(self.covered_api_names) is not tuple
            or self.covered_api_names != _COVERED_API_NAMES
            or type(self.covered_statement_kinds) is not tuple
            or self.covered_statement_kinds != _COVERED_STATEMENT_KINDS
            or len(set(self.covered_api_names)) != 3
            or len(set(self.covered_statement_kinds)) != 3
        ):
            raise ValueError("declaration API-kind exact cover mismatch")
        for name in (
            "source_snapshot_id",
            "source_content_tree_hash",
            "source_provenance_hash",
        ):
            _hash(name, getattr(self, name))
        if type(self.source_document_refs) is not tuple or len(self.source_document_refs) != 2 or any(
            type(value) is not ReviewedNonFilingDocumentV1 for value in self.source_document_refs
        ):
            raise TypeError("source_document_refs must be an exact two-document tuple")
        if self.source_document_refs != _ordered_documents(self.source_document_refs):
            raise ValueError("source_document_refs are not canonical")
        initial, terminal = self.source_document_refs
        if tuple(value.role for value in self.source_document_refs) != tuple(NonFilingDocumentRole):
            raise ValueError("declaration source terminal exact cover mismatch")
        if (
            initial.supersedes_member_key is not None
            or terminal.supersedes_member_key != initial.member_key
            or self.initial_availability.document_member_key != initial.member_key
            or self.terminal_availability.document_member_key != terminal.member_key
        ):
            raise ValueError("declaration source availability mismatch")
        if not _availability_valid(self.initial_availability) or not _availability_valid(
            self.terminal_availability
        ):
            raise ValueError("declaration availability reconstruction mismatch")
        if type(self.terminal_confirmation) is not str or self.terminal_confirmation != (
            "NOT_FILED_THROUGH_LISTING_TERMINATION"
        ):
            raise ValueError("terminal confirmation mismatch")
        _exact_date("terminal_confirmation_fact_date", self.terminal_confirmation_fact_date)
        if not initial.published_date <= self.terminal_confirmation_fact_date <= terminal.published_date:
            raise ValueError("terminal confirmation fact date mismatch")
        if (
            type(self.limitations) is not tuple
            or not self.limitations
            or self.limitations != tuple(sorted(self.limitations))
            or len(set(self.limitations)) != len(self.limitations)
        ):
            raise ValueError("limitations must be canonical, unique, and nonempty")
        for value in self.limitations:
            _text("limitation", value)
        expected = canonical_sha256(self._body())
        if type(self.declaration_id) is not str:
            raise TypeError("declaration_id must be exact str")
        if self.declaration_id == "":
            object.__setattr__(self, "declaration_id", expected)
        else:
            _hash("declaration_id", self.declaration_id)
            if self.declaration_id != expected:
                raise ValueError("declaration reconstruction hash mismatch")

    def _body(self) -> dict[str, object]:
        return {
            "type": self.type,
            "schema_version": self.schema_version,
            "instrument_id": self.instrument_id,
            "provider_code": self.provider_code,
            "fiscal_period_end_date": self.fiscal_period_end_date.isoformat(),
            "statutory_deadline_date": self.statutory_deadline_date.isoformat(),
            "filing_status": self.filing_status,
            "economic_effective_date": self.economic_effective_date.isoformat(),
            "initial_availability": self.initial_availability.to_canonical_dict(),
            "terminal_availability": self.terminal_availability.to_canonical_dict(),
            "available_at": self.available_at,
            "active_interval_start": self.active_interval_start,
            "active_interval_end": self.active_interval_end,
            "covered_api_names": self.covered_api_names,
            "covered_statement_kinds": self.covered_statement_kinds,
            "source_snapshot_id": self.source_snapshot_id,
            "source_content_tree_hash": self.source_content_tree_hash,
            "source_provenance_hash": self.source_provenance_hash,
            "source_document_refs": tuple(value.to_canonical_dict() for value in self.source_document_refs),
            "terminal_confirmation": self.terminal_confirmation,
            "terminal_confirmation_fact_date": self.terminal_confirmation_fact_date.isoformat(),
            "terminal_confirmation_available_at": self.terminal_confirmation_available_at,
            "limitations": self.limitations,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "declaration_id": self.declaration_id}


@dataclass(frozen=True, slots=True)
class OfficialAnnualReportNonFilingOutcome:
    declaration: OfficialAnnualReportNonFilingDeclarationV1 | None
    failure: OfficialAnnualReportNonFilingFailure | None

    def __post_init__(self) -> None:
        if (self.declaration is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one declaration or failure")
        if self.declaration is not None and type(self.declaration) is not OfficialAnnualReportNonFilingDeclarationV1:
            raise TypeError("declaration must be exact OfficialAnnualReportNonFilingDeclarationV1")
        if self.failure is not None and type(self.failure) is not OfficialAnnualReportNonFilingFailure:
            raise TypeError("failure must be exact OfficialAnnualReportNonFilingFailure")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "official_annual_report_nonfiling_outcome",
            "schema_version": _SCHEMA_VERSION,
            "declaration": None if self.declaration is None else self.declaration.to_canonical_dict(),
            "failure": None if self.failure is None else self.failure.value,
        }


def _failed(code: OfficialAnnualReportNonFilingFailure) -> OfficialAnnualReportNonFilingOutcome:
    return OfficialAnnualReportNonFilingOutcome(None, code)


def _ordered_documents(
    documents: tuple[ReviewedNonFilingDocumentV1, ReviewedNonFilingDocumentV1],
) -> tuple[ReviewedNonFilingDocumentV1, ReviewedNonFilingDocumentV1]:
    role_order = {
        NonFilingDocumentRole.INITIAL_NONFILING_PROOF: 0,
        NonFilingDocumentRole.TERMINAL_CONFIRMATION: 1,
    }
    return tuple(  # type: ignore[return-value]
        sorted(
            documents,
            key=lambda value: (
                role_order[value.role],
                value.published_at_epoch_nanoseconds
                if value.published_at_epoch_nanoseconds is not None
                else _date_start_ns(value.published_date),
                value.member_key,
            ),
        )
    )


def _availability_valid(value: OfficialNonFilingAvailabilityV1) -> bool:
    try:
        return value.available_at == max(
            value.source_visibility_at, value.deadline_boundary_at
        ) and value.availability_id == canonical_sha256(value._body())
    except (AttributeError, TypeError, ValueError, OverflowError):
        return False


def _publication_causality_valid(
    document: ReviewedNonFilingDocumentV1,
    availability: OfficialNonFilingAvailabilityV1,
    acquired_at: int,
) -> bool:
    if document.publication_precision == "EXACT_INSTANT":
        published_at = document.published_at_epoch_nanoseconds
        return (
            published_at is not None
            and _utc_day_index(UtcInstant(published_at))
            == _date_day_index(document.published_date)
            and acquired_at >= published_at
            and availability.source_visibility_at.epoch_nanoseconds >= published_at
        )
    return (
        acquired_at >= _date_start_ns(document.published_date)
        and _utc_day_index(availability.source_visibility_at)
        > _date_day_index(document.published_date)
    )


def _trusted_request(value: object) -> OfficialAnnualReportNonFilingRequestV1 | None:
    if type(value) is not OfficialAnnualReportNonFilingRequestV1:
        return None
    try:
        rebuilt = OfficialAnnualReportNonFilingRequestV1(
            **{
                name: getattr(value, name)
                for name in OfficialAnnualReportNonFilingRequestV1.__dataclass_fields__
            }
        )
        instrument = InstrumentId(VenueId(value.instrument_id.venue.value), value.instrument_id.stable_key)
        if instrument.to_canonical_dict() != value.instrument_id.to_canonical_dict():
            return None
        for document in value.source_documents:
            ReviewedNonFilingDocumentV1(
                **{
                    name: getattr(document, name)
                    for name in ReviewedNonFilingDocumentV1.__dataclass_fields__
                }
            )
        for availability in (value.initial_availability, value.terminal_availability):
            OfficialNonFilingAvailabilityV1(
                **{
                    name: getattr(availability, name)
                    for name in OfficialNonFilingAvailabilityV1.__dataclass_fields__
                }
            )
        return rebuilt
    except (AttributeError, TypeError, ValueError):
        return None


def _identity_matches(request: OfficialAnnualReportNonFilingRequestV1) -> bool:
    return _provider_identity_matches(request.instrument_id, request.provider_code)


def _build_declaration(
    request: OfficialAnnualReportNonFilingRequestV1,
    ordered: tuple[ReviewedNonFilingDocumentV1, ReviewedNonFilingDocumentV1],
) -> OfficialAnnualReportNonFilingDeclarationV1:
    snapshot = request.source_snapshot
    return OfficialAnnualReportNonFilingDeclarationV1(
        type="official_annual_report_nonfiling_declaration",
        schema_version=_SCHEMA_VERSION,
        declaration_id="",
        instrument_id=request.instrument_id,
        provider_code=request.provider_code,
        fiscal_period_end_date=request.fiscal_period_end_date,
        statutory_deadline_date=request.statutory_deadline_date,
        filing_status="NOT_FILED_BY_STATUTORY_DEADLINE",
        economic_effective_date=request.statutory_deadline_date,
        initial_availability=request.initial_availability,
        terminal_availability=request.terminal_availability,
        available_at=request.initial_availability.available_at,
        active_interval_start=request.initial_availability.available_at,
        active_interval_end=request.active_interval_end,
        covered_api_names=_COVERED_API_NAMES,
        covered_statement_kinds=_COVERED_STATEMENT_KINDS,
        source_snapshot_id=snapshot.snapshot_id,
        source_content_tree_hash=snapshot.content_tree_hash,
        source_provenance_hash=snapshot.provenance_hash,
        source_document_refs=ordered,
        terminal_confirmation="NOT_FILED_THROUGH_LISTING_TERMINATION",
        terminal_confirmation_fact_date=request.terminal_confirmation_fact_date,
        terminal_confirmation_available_at=request.terminal_availability.available_at,
        limitations=tuple(sorted(request.limitations)),
    )


def declare_official_annual_report_nonfiling_v1(
    request: OfficialAnnualReportNonFilingRequestV1,
) -> OfficialAnnualReportNonFilingOutcome:
    trusted = _trusted_request(request)
    if trusted is None:
        return _failed(OfficialAnnualReportNonFilingFailure.INPUT_TYPE_MISMATCH)
    if not _identity_matches(trusted):
        return _failed(OfficialAnnualReportNonFilingFailure.CATALOG_IDENTITY_MISMATCH)

    snapshot = trusted.source_snapshot
    if verify_source_snapshot(snapshot).snapshot is None:
        return _failed(OfficialAnnualReportNonFilingFailure.SOURCE_MEMBER_CONFLICT)
    members = {value.member_key: value for value in snapshot.members}
    documents = trusted.source_documents
    document_keys = tuple(value.member_key for value in documents)
    if (
        len(snapshot.members) != 2
        or len(set(document_keys)) != 2
        or set(document_keys) != set(members)
        or any(
            members[value.member_key].content_hash != value.content_hash
            or members[value.member_key].byte_count != value.byte_count
            for value in documents
        )
    ):
        return _failed(OfficialAnnualReportNonFilingFailure.SOURCE_MEMBER_CONFLICT)

    initial_values = [value for value in documents if value.role is NonFilingDocumentRole.INITIAL_NONFILING_PROOF]
    terminal_values = [value for value in documents if value.role is NonFilingDocumentRole.TERMINAL_CONFIRMATION]
    availability_values = (trusted.initial_availability, trusted.terminal_availability)
    if (
        any(not _availability_valid(value) for value in availability_values)
        or trusted.initial_availability.deadline_boundary_at
        != trusted.terminal_availability.deadline_boundary_at
        or _utc_day_index(trusted.initial_availability.deadline_boundary_at)
        <= _date_day_index(trusted.statutory_deadline_date)
        or trusted.terminal_availability.source_visibility_at
        < trusted.initial_availability.source_visibility_at
        or trusted.terminal_availability.available_at < trusted.initial_availability.available_at
        or trusted.active_interval_end <= trusted.initial_availability.available_at
    ):
        return _failed(OfficialAnnualReportNonFilingFailure.FINANCIAL_REVISION_MISMATCH)
    for document in documents:
        member = members[document.member_key]
        linked = next(
            (value for value in availability_values if value.document_member_key == document.member_key),
            None,
        )
        if (
            linked is None
            or not _publication_causality_valid(document, linked, member.acquired_at_epoch_nanoseconds)
            or document.reviewed_at_epoch_nanoseconds < member.acquired_at_epoch_nanoseconds
        ):
            return _failed(OfficialAnnualReportNonFilingFailure.FINANCIAL_REVISION_MISMATCH)
    if initial_values and initial_values[0].published_date < trusted.statutory_deadline_date:
        return _failed(OfficialAnnualReportNonFilingFailure.FINANCIAL_REVISION_MISMATCH)
    if len(initial_values) != 1 or len(terminal_values) != 1:
        return _failed(OfficialAnnualReportNonFilingFailure.BUNDLE_EXACT_COVER_MISMATCH)
    initial = initial_values[0]
    terminal = terminal_values[0]
    if (
        not initial.published_date
        <= trusted.terminal_confirmation_fact_date
        <= terminal.published_date
        or trusted.initial_availability.document_member_key != initial.member_key
        or trusted.terminal_availability.document_member_key != terminal.member_key
        or initial.supersedes_member_key is not None
        or terminal.supersedes_member_key != initial.member_key
    ):
        return _failed(OfficialAnnualReportNonFilingFailure.FINANCIAL_REVISION_MISMATCH)

    try:
        ordered = _ordered_documents(documents)
        declaration = _build_declaration(trusted, ordered)
    except (AttributeError, TypeError, ValueError) as error:
        if "exact cover" in str(error):
            return _failed(OfficialAnnualReportNonFilingFailure.BUNDLE_EXACT_COVER_MISMATCH)
        return _failed(OfficialAnnualReportNonFilingFailure.PUBLICATION_INTEGRITY_FAILURE)
    try:
        rebuilt = OfficialAnnualReportNonFilingDeclarationV1(
            **{
                name: getattr(declaration, name)
                for name in OfficialAnnualReportNonFilingDeclarationV1.__dataclass_fields__
            }
        )
        if rebuilt.to_canonical_dict() != declaration.to_canonical_dict():
            raise ValueError("declaration reconstruction mismatch")
    except (AttributeError, TypeError, ValueError):
        return _failed(OfficialAnnualReportNonFilingFailure.PUBLICATION_INTEGRITY_FAILURE)
    return OfficialAnnualReportNonFilingOutcome(rebuilt, None)
