from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from crypto_quant_domain import InstrumentId, UtcInstant, VenueId, canonical_sha256

import crypto_quant_bundle_builder.official_annual_report_nonfiling_v1 as nonfiling

INITIAL_BYTES = b"official initial non-filing proof"
TERMINAL_BYTES = b"official terminal confirmation"
INITIAL_KEY = "official/initial.pdf"
TERMINAL_KEY = "official/terminal.pdf"
DEADLINE = date(2022, 4, 30)
INITIAL_PUBLISHED_NS = 1_651_276_800_000_000_000
INITIAL_VISIBILITY = UtcInstant(1_651_363_800_000_000_000)
TERMINAL_PUBLISHED_NS = 1_672_531_200_000_000_000
TERMINAL_VISIBILITY = UtcInstant(1_672_531_201_000_000_000)
BOUNDARY = UtcInstant(1_651_363_800_000_000_000)
END = UtcInstant(1_683_163_800_000_000_000)
HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def _snapshot():
    outcome = freeze_source_snapshot(
        members=(
            RawSourceMember(INITIAL_KEY, INITIAL_BYTES, "0644", INITIAL_PUBLISHED_NS + 10, None),
            RawSourceMember(TERMINAL_KEY, TERMINAL_BYTES, "0644", TERMINAL_PUBLISHED_NS + 10, None),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="official.authority",
            source_key="annual.nonfiling",
            license_ref="retained.review",
            retention_policy_ref="immutable.bytes",
        ),
    )
    assert outcome.snapshot is not None
    return outcome.snapshot


def _availability(
    member_key: str,
    source_visibility_at: UtcInstant,
    *,
    deadline_boundary_at: UtcInstant = BOUNDARY,
) -> nonfiling.OfficialNonFilingAvailabilityV1:
    body = {
        "type": "official_nonfiling_availability",
        "schema_version": 1,
        "document_member_key": member_key,
        "source_visibility_at": source_visibility_at,
        "deadline_boundary_at": deadline_boundary_at,
        "available_at": max(source_visibility_at, deadline_boundary_at),
        "calendar_authority_id": HASH_A,
        "source_availability_id": HASH_B,
    }
    return nonfiling.OfficialNonFilingAvailabilityV1(
        **body,
        availability_id=canonical_sha256(body),
    )


def _documents(snapshot=None):
    source = snapshot or _snapshot()
    members = {value.member_key: value for value in source.members}
    initial = nonfiling.ReviewedNonFilingDocumentV1(
        type="reviewed_nonfiling_document",
        schema_version=1,
        role=nonfiling.NonFilingDocumentRole.INITIAL_NONFILING_PROOF,
        evidence_kind=nonfiling.NonFilingEvidenceKind.POST_DEADLINE_NONFILING_CONFIRMATION,
        authority=nonfiling.NonFilingAuthority.SSE,
        member_key=INITIAL_KEY,
        source_url="https://example.invalid/initial",
        published_date=DEADLINE,
        publication_precision="DATE_ONLY",
        published_at_epoch_nanoseconds=None,
        content_hash=members[INITIAL_KEY].content_hash,
        byte_count=members[INITIAL_KEY].byte_count,
        reviewed_pages=(1,),
        reviewed_excerpt="The annual report was not filed by the statutory deadline.",
        issuer_assertion="600090.SH did not file the named annual report by the deadline.",
        period_assertion="Annual period ended 2021-12-31.",
        supersedes_member_key=None,
        reviewer_key="quality-bband-eight-issuer-official-authority-audit-v1",
        reviewed_at_epoch_nanoseconds=INITIAL_PUBLISHED_NS + 20,
    )
    terminal = nonfiling.ReviewedNonFilingDocumentV1(
        type="reviewed_nonfiling_document",
        schema_version=1,
        role=nonfiling.NonFilingDocumentRole.TERMINAL_CONFIRMATION,
        evidence_kind=nonfiling.NonFilingEvidenceKind.TERMINAL_NONFILING_CONFIRMATION,
        authority=nonfiling.NonFilingAuthority.SSE,
        member_key=TERMINAL_KEY,
        source_url="https://example.invalid/terminal",
        published_date=date(2023, 1, 1),
        publication_precision="EXACT_INSTANT",
        published_at_epoch_nanoseconds=TERMINAL_PUBLISHED_NS,
        content_hash=members[TERMINAL_KEY].content_hash,
        byte_count=members[TERMINAL_KEY].byte_count,
        reviewed_pages=(1, 2),
        reviewed_excerpt="The report remained unfiled through listing termination.",
        issuer_assertion="600090.SH remained a non-filer through listing termination.",
        period_assertion="Annual period ended 2021-12-31.",
        supersedes_member_key=INITIAL_KEY,
        reviewer_key="quality-bband-eight-issuer-official-authority-audit-v1",
        reviewed_at_epoch_nanoseconds=TERMINAL_PUBLISHED_NS + 20,
    )
    return initial, terminal


def _request(
    *,
    snapshot=None,
    documents=None,
    initial_availability=None,
    terminal_availability=None,
    active_interval_end: UtcInstant = END,
) -> nonfiling.OfficialAnnualReportNonFilingRequestV1:
    source = snapshot or _snapshot()
    refs = documents or _documents(source)
    return nonfiling.OfficialAnnualReportNonFilingRequestV1(
        type="official_annual_report_nonfiling_request",
        schema_version=1,
        instrument_id=InstrumentId(VenueId("xshg"), "600090"),
        provider_code="600090.SH",
        fiscal_period_end_date=date(2021, 12, 31),
        statutory_deadline_date=DEADLINE,
        source_snapshot=source,
        source_documents=refs,
        initial_availability=initial_availability or _availability(INITIAL_KEY, INITIAL_VISIBILITY),
        terminal_availability=terminal_availability
        or _availability(TERMINAL_KEY, TERMINAL_VISIBILITY),
        active_interval_end=active_interval_end,
        terminal_confirmation_fact_date=date(2023, 1, 1),
        limitations=("terminal evidence is reviewed", "no numeric statement values"),
    )


def _declare(request=None):
    return nonfiling.declare_official_annual_report_nonfiling_v1(request or _request())


def test_declaration_reconstructs_canonical_terminal_cover() -> None:
    outcome = _declare()
    assert outcome.failure is None
    assert outcome.declaration is not None
    value = outcome.declaration

    assert value.instrument_id == InstrumentId(VenueId("xshg"), "600090")
    assert value.filing_status == "NOT_FILED_BY_STATUTORY_DEADLINE"
    assert value.economic_effective_date == DEADLINE
    assert value.available_at == value.active_interval_start == INITIAL_VISIBILITY
    assert value.active_interval_end == END
    assert value.covered_api_names == ("income_vip", "balancesheet_vip", "cashflow_vip")
    assert value.covered_statement_kinds == (
        "INCOME_STATEMENT",
        "BALANCE_SHEET",
        "CASH_FLOW_STATEMENT",
    )
    assert value.terminal_confirmation == "NOT_FILED_THROUGH_LISTING_TERMINATION"
    assert value.terminal_confirmation_available_at == TERMINAL_VISIBILITY
    assert value.limitations == tuple(sorted(value.limitations))
    body = value.to_canonical_dict()
    declaration_id = body.pop("declaration_id")
    assert declaration_id == canonical_sha256(body)
    assert not any(
        key in body
        for key in ("value", "amount", "threshold_failure", "exit", "slot_release", "replacement_target")
    )


def test_source_ref_input_order_does_not_change_declaration_id() -> None:
    request = _request()
    first = _declare(request)
    second = _declare(replace(request, source_documents=tuple(reversed(request.source_documents))))
    assert first.declaration is not None and second.declaration is not None
    assert first.declaration.declaration_id == second.declaration.declaration_id
    assert tuple(value.role for value in second.declaration.source_document_refs) == tuple(
        nonfiling.NonFilingDocumentRole
    )


def test_snapshot_identity_bytes_and_member_conflicts_fail_as_source() -> None:
    request = _request()
    for source in (
        replace(request.source_snapshot, provenance_hash="sha256:" + "0" * 64),
        replace(request.source_snapshot, archive_bytes=b"corrupt"),
    ):
        outcome = _declare(replace(request, source_snapshot=source))
        assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.SOURCE_MEMBER_CONFLICT

    initial, terminal = request.source_documents
    outcome = _declare(
        replace(request, source_documents=(replace(initial, content_hash=terminal.content_hash), terminal))
    )
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.SOURCE_MEMBER_CONFLICT


def test_provider_identity_mismatch_precedes_source_inspection() -> None:
    request = _request()
    corrupted = replace(request.source_snapshot, archive_bytes=b"corrupt")
    outcome = _declare(replace(request, provider_code="600090.SZ", source_snapshot=corrupted))
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.CATALOG_IDENTITY_MISMATCH


@pytest.mark.parametrize(
    "provider_code",
    ["600090.HK", "xshg:600090", "60090.SH", "600090.sh"],
)
def test_foreign_provider_codes_fail_identity(provider_code: str) -> None:
    outcome = _declare(replace(_request(), provider_code=provider_code))
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.CATALOG_IDENTITY_MISMATCH


def test_predeadline_proof_and_availability_conflicts_fail_financial_revision() -> None:
    request = _request()
    initial, terminal = request.source_documents
    early = replace(initial, published_date=date(2022, 4, 29))
    outcome = _declare(replace(request, source_documents=(early, terminal)))
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.FINANCIAL_REVISION_MISMATCH

    definitive = replace(
        early,
        evidence_kind=nonfiling.NonFilingEvidenceKind.PREDEADLINE_DEFINITIVE_INABILITY,
        authority=nonfiling.NonFilingAuthority.ISSUER,
    )
    outcome = _declare(replace(request, source_documents=(definitive, terminal)))
    assert outcome.failure is None
    assert outcome.declaration is not None

    incompatible = replace(definitive, authority=nonfiling.NonFilingAuthority.SSE)
    outcome = _declare(replace(request, source_documents=(incompatible, terminal)))
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.FINANCIAL_REVISION_MISMATCH

    exchange_effective = replace(
        initial,
        evidence_kind=nonfiling.NonFilingEvidenceKind.EXCHANGE_NONFILING_SUSPENSION_EFFECTIVE,
        authority=nonfiling.NonFilingAuthority.SZSE,
    )
    exchange_request = replace(
        request,
        source_documents=(exchange_effective, terminal),
    )
    outcome = _declare(exchange_request)
    assert outcome.failure is None
    assert outcome.declaration is not None

    early_exchange_availability = _availability(
        INITIAL_KEY,
        UtcInstant(BOUNDARY.epoch_nanoseconds - 1),
    )
    outcome = _declare(
        replace(
            exchange_request,
            initial_availability=early_exchange_availability,
        )
    )
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.FINANCIAL_REVISION_MISMATCH
    valid_exchange = _declare(exchange_request)
    assert valid_exchange.declaration is not None
    with pytest.raises(ValueError, match="evidence compatibility"):
        replace(
            valid_exchange.declaration,
            initial_availability=early_exchange_availability,
            declaration_id="",
        )

    sponsor_terminal = replace(
        terminal,
        authority=nonfiling.NonFilingAuthority.NEEQ_SPONSOR,
    )
    outcome = _declare(replace(request, source_documents=(initial, sponsor_terminal)))
    assert outcome.failure is None
    assert outcome.declaration is not None

    wrong_id = replace(request.initial_availability, availability_id="sha256:" + "0" * 64)
    outcome = _declare(replace(request, initial_availability=wrong_id))
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.FINANCIAL_REVISION_MISMATCH

    too_early = _availability(INITIAL_KEY, UtcInstant(INITIAL_PUBLISHED_NS - 1))
    outcome = _declare(replace(request, initial_availability=too_early))
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.FINANCIAL_REVISION_MISMATCH

    noncanonical = replace(
        request.initial_availability,
        document_member_key="e\u0301",
        availability_id=HASH_A,
    )
    outcome = _declare(replace(request, initial_availability=noncanonical))
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.FINANCIAL_REVISION_MISMATCH

    huge = 10**100
    huge_initial = _availability(INITIAL_KEY, UtcInstant(huge))
    huge_terminal = _availability(TERMINAL_KEY, UtcInstant(huge + 1))
    outcome = _declare(
        replace(
            request,
            initial_availability=huge_initial,
            terminal_availability=huge_terminal,
            active_interval_end=UtcInstant(huge + 2),
        )
    )
    assert outcome.failure is None
    assert outcome.declaration is not None


def test_supersession_terminal_chronology_and_half_open_interval_are_enforced() -> None:
    request = _request()
    initial, terminal = request.source_documents
    wrong_supersession = replace(terminal, supersedes_member_key=TERMINAL_KEY)
    outcome = _declare(replace(request, source_documents=(initial, wrong_supersession)))
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.FINANCIAL_REVISION_MISMATCH

    reversed_terminal = _availability(TERMINAL_KEY, UtcInstant(INITIAL_VISIBILITY.epoch_nanoseconds - 1))
    outcome = _declare(replace(request, terminal_availability=reversed_terminal))
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.FINANCIAL_REVISION_MISMATCH

    outcome = _declare(replace(request, active_interval_end=INITIAL_VISIBILITY))
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.FINANCIAL_REVISION_MISMATCH


def test_duplicate_terminal_fails_exact_cover_after_source_verification() -> None:
    request = _request()
    initial, terminal = request.source_documents
    duplicate_terminal = replace(initial, role=nonfiling.NonFilingDocumentRole.TERMINAL_CONFIRMATION)
    outcome = _declare(replace(request, source_documents=(duplicate_terminal, terminal)))
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.BUNDLE_EXACT_COVER_MISMATCH

    corrupted = replace(request.source_snapshot, archive_bytes=b"corrupt")
    outcome = _declare(
        replace(
            request,
            source_snapshot=corrupted,
            source_documents=(duplicate_terminal, terminal),
        )
    )
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.SOURCE_MEMBER_CONFLICT


def test_later_filing_boundary_shortens_interval_without_backfill() -> None:
    request = _request()
    shortened_end = UtcInstant(INITIAL_VISIBILITY.epoch_nanoseconds + 1)
    original = _declare(request)
    shortened = _declare(replace(request, active_interval_end=shortened_end))
    assert original.declaration is not None and shortened.declaration is not None
    assert shortened.declaration.active_interval_start == original.declaration.active_interval_start
    assert shortened.declaration.active_interval_end == shortened_end
    assert shortened.declaration.declaration_id != original.declaration.declaration_id


def test_declaration_constructor_rejects_api_kind_overlap_and_hash_forgery() -> None:
    outcome = _declare()
    assert outcome.declaration is not None
    value = outcome.declaration
    with pytest.raises(ValueError, match="exact cover"):
        replace(
            value,
            covered_api_names=("income_vip", "balancesheet_vip", "income_vip"),
            declaration_id="",
        )
    with pytest.raises(ValueError, match="exact cover"):
        replace(
            value,
            covered_api_names=("income_vip", "balancesheet_vip", ""),
            declaration_id="",
        )
    with pytest.raises(ValueError, match="exact cover"):
        replace(
            value,
            covered_statement_kinds=("INCOME_STATEMENT", "BALANCE_SHEET", "BALANCE_SHEET"),
            declaration_id="",
        )
    with pytest.raises(ValueError, match="source terminal exact cover"):
        replace(
            value,
            source_document_refs=(
                replace(
                    value.source_document_refs[0],
                    role=nonfiling.NonFilingDocumentRole.TERMINAL_CONFIRMATION,
                ),
                value.source_document_refs[1],
            ),
            declaration_id="",
        )
    with pytest.raises(ValueError, match="availability reconstruction"):
        replace(
            value,
            initial_availability=replace(
                value.initial_availability,
                availability_id="sha256:" + "0" * 64,
            ),
            declaration_id="",
        )
    with pytest.raises(ValueError, match="provider identity"):
        replace(value, provider_code="600090.SZ", declaration_id="")
    with pytest.raises(ValueError, match="reconstruction hash"):
        replace(value, declaration_id="sha256:" + "0" * 64)


def test_build_failures_map_to_exact_cover_before_publication_integrity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_cover(*_args: object) -> object:
        raise ValueError("declaration API-kind exact cover mismatch")

    monkeypatch.setattr(nonfiling, "_build_declaration", broken_cover)
    outcome = _declare()
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.BUNDLE_EXACT_COVER_MISMATCH

    def broken_hash(*_args: object) -> object:
        raise ValueError("declaration reconstruction hash mismatch")

    monkeypatch.setattr(nonfiling, "_build_declaration", broken_hash)
    outcome = _declare()
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.PUBLICATION_INTEGRITY_FAILURE


def test_malformed_request_fails_before_semantic_inspection() -> None:
    outcome = nonfiling.declare_official_annual_report_nonfiling_v1(None)  # type: ignore[arg-type]
    assert outcome.failure is nonfiling.OfficialAnnualReportNonFilingFailure.INPUT_TYPE_MISMATCH
