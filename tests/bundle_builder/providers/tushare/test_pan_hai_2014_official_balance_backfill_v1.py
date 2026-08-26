from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from crypto_quant_domain import InstrumentId, UtcInstant, VenueId, canonical_sha256

import crypto_quant_bundle_builder.pan_hai_2014_official_balance_backfill_v1 as pan_hai

METADATA_BYTES = b'{"fixture":"announcement metadata"}'
PDF_BYTES = b"%PDF-1.7\nretained fixture bytes\n"
REVIEWED_AT = 1_800_000_000_000_000_000
SOURCE_VISIBILITY = UtcInstant(1_493_688_600_000_000_000)
PUBLICATION_BOUNDARY = UtcInstant(1_493_688_600_000_000_000)
CALENDAR_AUTHORITY_ID = (
    "sha256:22585fa4c2070d87544f0ba977be757770aeeaad5bead30188317c1794680ee8"
)
SOURCE_AVAILABILITY_ID = (
    "sha256:8195e9d9e99949802c829f218929bdbf740b336152d83ad789a060e0355d116e"
)
HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64

FIELD_SPECS = (
    ("money_cap", "货币资金", 77, pan_hai.BalanceFieldApplicability.VALUE, "11473676835.21"),
    ("total_assets", "资产总计", 78, pan_hai.BalanceFieldApplicability.VALUE, "70889108573.14"),
    ("total_liab", "负债合计", 79, pan_hai.BalanceFieldApplicability.VALUE, "58374057829.63"),
    (
        "total_hldr_eqy_inc_min_int",
        "所有者权益合计",
        79,
        pan_hai.BalanceFieldApplicability.VALUE,
        "12515050743.51",
    ),
    (
        "total_hldr_eqy_exc_min_int",
        "归属于母公司所有者权益合计",
        79,
        pan_hai.BalanceFieldApplicability.VALUE,
        "9273976463.95",
    ),
    ("minority_int", "少数股东权益", 79, pan_hai.BalanceFieldApplicability.VALUE, "3241074279.56"),
    (
        "total_liab_hldr_eqy",
        "负债和所有者权益总计",
        79,
        pan_hai.BalanceFieldApplicability.VALUE,
        "70889108573.14",
    ),
    ("st_borr", "短期借款", 78, pan_hai.BalanceFieldApplicability.VALUE, "4316020932.89"),
    (
        "non_cur_liab_due_1y",
        "一年内到期的非流动负债",
        79,
        pan_hai.BalanceFieldApplicability.VALUE,
        "8785180000.00",
    ),
    ("lt_borr", "长期借款", 79, pan_hai.BalanceFieldApplicability.VALUE, "24359970013.75"),
    ("bond_payable", "应付债券", 79, pan_hai.BalanceFieldApplicability.VALUE, "2732689313.18"),
    (
        "st_bonds_payable",
        None,
        79,
        pan_hai.BalanceFieldApplicability.NOT_SEPARATELY_PRESENT,
        None,
    ),
)


def _snapshot(monkeypatch: pytest.MonkeyPatch):
    outcome = freeze_source_snapshot(
        members=(
            RawSourceMember(
                pan_hai._METADATA_MEMBER,
                METADATA_BYTES,
                "0644",
                1_700_000_000_000_000_000,
                None,
            ),
            RawSourceMember(
                pan_hai._PDF_MEMBER,
                PDF_BYTES,
                "0644",
                1_700_000_000_000_000_001,
                None,
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="official.authority",
            source_key="pan.hai.2014",
            license_ref="official.disclosure",
            retention_policy_ref="immutable.bytes",
        ),
    )
    assert outcome.snapshot is not None
    source = outcome.snapshot
    pdf = next(
        member for member in source.members if member.member_key == pan_hai._PDF_MEMBER
    )
    monkeypatch.setattr(pan_hai, "_SNAPSHOT_ID", source.snapshot_id)
    monkeypatch.setattr(pan_hai, "_SOURCE_AVAILABILITY_ID", source.snapshot_id)
    monkeypatch.setattr(pan_hai, "_CONTENT_TREE_HASH", source.content_tree_hash)
    monkeypatch.setattr(pan_hai, "_PROVENANCE_HASH", source.provenance_hash)
    monkeypatch.setattr(pan_hai, "_PDF_HASH", pdf.content_hash)
    monkeypatch.setattr(pan_hai, "_PDF_BYTES", pdf.byte_count)
    return source


def _field_reviews() -> tuple[pan_hai.PanHai2014BalanceFieldReviewV1, ...]:
    return tuple(
        pan_hai.PanHai2014BalanceFieldReviewV1(
            type="pan_hai_2014_balance_field_review",
            schema_version=1,
            field_key=field_key,
            source_label=source_label,
            pdf_page=pdf_page,
            applicability=applicability,
            value_decimal_text=value,
        )
        for field_key, source_label, pdf_page, applicability, value in FIELD_SPECS
    )


def _evidence(
    *,
    field_reviews: tuple[pan_hai.PanHai2014BalanceFieldReviewV1, ...] | None = None,
    reviewed_at: int = REVIEWED_AT,
) -> pan_hai.PanHai2014ReviewedBalanceEvidenceV1:
    return pan_hai.PanHai2014ReviewedBalanceEvidenceV1(
        type="pan_hai_2014_reviewed_balance_evidence",
        schema_version=1,
        reviewer_key="quality-bband-pan-hai-2014-balance-review-v1",
        reviewed_at_epoch_nanoseconds=reviewed_at,
        pdf_member_key=pan_hai._PDF_MEMBER,
        metadata_member_key=pan_hai._METADATA_MEMBER,
        statement_pages=(77, 78, 79),
        audit_page=76,
        statement_title="合并资产负债表",
        issuer_name="泛海控股股份有限公司",
        provider_code="000046.SZ",
        fiscal_period_end_date=date(2014, 12, 31),
        publication_date=date(2015, 4, 4),
        currency="CNY",
        unit_text="人民币元",
        unit_multiplier=Decimal("1"),
        consolidation="CONSOLIDATED",
        company_layout="MIXED_REAL_ESTATE_SECURITIES_CONSOLIDATION",
        audit_opinion="STANDARD_UNQUALIFIED",
        audit_report_date=date(2015, 4, 3),
        audit_report_number="信会师报字[2015]第310292号",
        field_reviews=field_reviews or _field_reviews(),
        limitations=(
            "REVIEWED_PDF_PAGES_ONLY",
            "NO_PDF_PARSER_AUTHORITY",
            "MIXED_REAL_ESTATE_SECURITIES_LAYOUT",
            "SHORT_TERM_BONDS_NOT_SEPARATELY_PRESENT",
        ),
    )


def _availability(
    *,
    source_visibility_at: UtcInstant = SOURCE_VISIBILITY,
    publication_boundary_at: UtcInstant = PUBLICATION_BOUNDARY,
    available_at: UtcInstant | None = None,
) -> pan_hai.PanHai2014BalanceAvailabilityV1:
    resolved = available_at or max(source_visibility_at, publication_boundary_at)
    body = {
        "type": "pan_hai_2014_balance_availability",
        "schema_version": 1,
        "pdf_member_key": pan_hai._PDF_MEMBER,
        "source_publication_date": "2015-04-04",
        "source_visibility_at": source_visibility_at.to_canonical_dict(),
        "publication_boundary_at": publication_boundary_at.to_canonical_dict(),
        "available_at": resolved.to_canonical_dict(),
        "calendar_authority_id": CALENDAR_AUTHORITY_ID,
        "source_availability_id": pan_hai._SOURCE_AVAILABILITY_ID,
    }
    return pan_hai.PanHai2014BalanceAvailabilityV1(
        type="pan_hai_2014_balance_availability",
        schema_version=1,
        availability_id=canonical_sha256(body),
        pdf_member_key=pan_hai._PDF_MEMBER,
        source_publication_date=date(2015, 4, 4),
        source_visibility_at=source_visibility_at,
        publication_boundary_at=publication_boundary_at,
        available_at=resolved,
        calendar_authority_id=CALENDAR_AUTHORITY_ID,
        source_availability_id=pan_hai._SOURCE_AVAILABILITY_ID,
    )


def _request(
    monkeypatch: pytest.MonkeyPatch,
    *,
    source=None,
    evidence: pan_hai.PanHai2014ReviewedBalanceEvidenceV1 | None = None,
    availability: pan_hai.PanHai2014BalanceAvailabilityV1 | None = None,
) -> pan_hai.PanHai2014OfficialBalanceBackfillRequestV1:
    return pan_hai.PanHai2014OfficialBalanceBackfillRequestV1(
        type="pan_hai_2014_official_balance_backfill_request",
        schema_version=1,
        source_snapshot=source or _snapshot(monkeypatch),
        reviewed_evidence=evidence or _evidence(),
        availability=availability or _availability(),
    )


def _build(monkeypatch: pytest.MonkeyPatch, request=None):
    return pan_hai.build_pan_hai_2014_official_balance_backfill_v1(
        request or _request(monkeypatch)
    )


def test_exact_candidate_builds_one_canonical_o_key_with_unsupported_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert pan_hai._CALENDAR_AUTHORITY_ID == CALENDAR_AUTHORITY_ID
    assert pan_hai._SOURCE_AVAILABILITY_ID == SOURCE_AVAILABILITY_ID
    outcome = _build(monkeypatch)
    assert outcome.failure is None
    assert outcome.backfill is not None
    value = outcome.backfill

    assert value.instrument_id == InstrumentId(VenueId("xshe"), "000046")
    assert value.provider_code == "000046.SZ"
    assert (value.api_name, value.period, value.statement_kind) == (
        "balancesheet_vip",
        "20141231",
        "BALANCE_SHEET",
    )
    assert value.covered_member_key == (
        "balancesheet_vip",
        "xshe:000046",
        "20141231",
    )
    assert len(value.field_reviews) == 12
    assert value.field_reviews[-1].applicability is (
        pan_hai.BalanceFieldApplicability.NOT_SEPARATELY_PRESENT
    )
    assert value.field_reviews[-1].value_decimal_text is None
    assert value.financial_payload_complete is False
    assert value.financial_scope_qualified is False
    assert value.scope_reason == "STATEMENT_SCOPE_UNSUPPORTED"
    body = value.to_canonical_dict()
    backfill_id = body.pop("backfill_id")
    assert backfill_id == canonical_sha256(body)
    assert value.availability.available_at == PUBLICATION_BOUNDARY
    assert not any(
        key in body
        for key in ("report_type", "comp_type", "update_flag", "provider_revision")
    )
    assert outcome.to_canonical_dict()["backfill"] == value.to_canonical_dict()


@pytest.mark.skipif(
    not os.environ.get("QB_OFFICIAL_S2_REMEDIATION_ROOT"),
    reason="QB_OFFICIAL_S2_REMEDIATION_ROOT is not configured",
)
def test_real_accepted_source_snapshot_builds_without_authority_monkeypatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(os.environ["QB_OFFICIAL_S2_REMEDIATION_ROOT"])
    receipt = json.loads((root / "acquisition-receipt.json").read_bytes())
    snapshot_metadata = json.loads((root / "source-snapshot.json").read_bytes())
    timestamps = {
        item["member_key"]: item["response_received_at_epoch_nanoseconds"]
        for item in receipt["logical_requests"]
    }
    rebuilt = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                key,
                (root / key).read_bytes(),
                "0644",
                timestamps[key],
                None,
            )
            for key in timestamps
        ),
        provenance=SourceSnapshotProvenance(**snapshot_metadata["provenance"]),
    )
    assert rebuilt.snapshot is not None
    assert rebuilt.snapshot.to_canonical_dict() == snapshot_metadata
    request = _request(
        monkeypatch,
        source=rebuilt.snapshot,
        evidence=_evidence(reviewed_at=max(timestamps.values()) + 1),
        availability=_availability(),
    )
    outcome = pan_hai.build_pan_hai_2014_official_balance_backfill_v1(request)
    assert outcome.failure is None
    assert outcome.backfill is not None
    assert outcome.backfill.covered_member_key == (
        "balancesheet_vip",
        "xshe:000046",
        "20141231",
    )


def test_field_reviews_are_exact_ordered_canonical_decimal_evidence() -> None:
    evidence = _evidence()
    assert tuple(
        (
            review.field_key,
            review.source_label,
            review.pdf_page,
            review.applicability,
            review.value_decimal_text,
        )
        for review in evidence.field_reviews
    ) == FIELD_SPECS
    canonical = evidence.to_canonical_dict()
    assert canonical["fiscal_period_end_date"] == "2014-12-31"
    assert canonical["publication_date"] == "2015-04-04"
    assert canonical["unit_multiplier"] == "1"
    assert all(
        isinstance(review["value_decimal_text"], str)
        for review in canonical["field_reviews"][:-1]
    )
    assert canonical["field_reviews"][-1]["value_decimal_text"] is None


def test_snapshot_pdf_metadata_hash_and_byte_mutations_fail_before_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(monkeypatch)
    wrong_page = replace(request.reviewed_evidence.field_reviews[0], pdf_page=78)
    bad_evidence = replace(
        request.reviewed_evidence,
        field_reviews=(wrong_page, *request.reviewed_evidence.field_reviews[1:]),
    )
    mutated_sources = []
    for metadata_bytes, pdf_bytes in (
        (METADATA_BYTES + b"x", PDF_BYTES),
        (METADATA_BYTES, PDF_BYTES + b"x"),
    ):
        mutated = freeze_source_snapshot(
            members=(
                RawSourceMember(
                    pan_hai._METADATA_MEMBER,
                    metadata_bytes,
                    "0644",
                    1_700_000_000_000_000_000,
                    None,
                ),
                RawSourceMember(
                    pan_hai._PDF_MEMBER,
                    pdf_bytes,
                    "0644",
                    1_700_000_000_000_000_001,
                    None,
                ),
            ),
            provenance=request.source_snapshot.provenance,
        ).snapshot
        assert mutated is not None
        mutated_sources.append(mutated)

    for source in (
        replace(request.source_snapshot, archive_bytes=b"corrupt"),
        replace(request.source_snapshot, snapshot_id="sha256:" + "0" * 64),
        replace(request.source_snapshot, content_tree_hash="sha256:" + "0" * 64),
        replace(request.source_snapshot, provenance_hash="sha256:" + "0" * 64),
        *mutated_sources,
    ):
        outcome = _build(
            monkeypatch,
            replace(request, source_snapshot=source, reviewed_evidence=bad_evidence),
        )
        assert outcome.failure is (
            pan_hai.PanHai2014OfficialBalanceBackfillFailure.SOURCE_MEMBER_CONFLICT
        )

    monkeypatch.setattr(pan_hai, "_PDF_BYTES", len(PDF_BYTES) + 1)
    outcome = _build(monkeypatch, request)
    assert outcome.failure is (
        pan_hai.PanHai2014OfficialBalanceBackfillFailure.SOURCE_MEMBER_CONFLICT
    )


def test_provider_and_period_identity_precede_source_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(monkeypatch)
    corrupted = replace(request.source_snapshot, archive_bytes=b"corrupt")
    for evidence in (
        replace(request.reviewed_evidence, provider_code="000046.SH"),
        replace(
            request.reviewed_evidence,
            fiscal_period_end_date=date(2013, 12, 31),
        ),
    ):
        outcome = _build(
            monkeypatch,
            replace(request, source_snapshot=corrupted, reviewed_evidence=evidence),
        )
        assert outcome.failure is (
            pan_hai.PanHai2014OfficialBalanceBackfillFailure.CATALOG_IDENTITY_MISMATCH
        )


def test_float_noncanonical_decimal_and_foreign_tuple_are_input_mismatches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(monkeypatch)
    for value in (1.0, "01.00", "1e2"):
        review = request.reviewed_evidence.field_reviews[0]
        object.__setattr__(review, "value_decimal_text", value)
        outcome = _build(monkeypatch, request)
        assert outcome.failure is (
            pan_hai.PanHai2014OfficialBalanceBackfillFailure.INPUT_TYPE_MISMATCH
        )
        object.__setattr__(review, "value_decimal_text", "11473676835.21")

    for multiplier in (Decimal("1.0"), Decimal("1.00")):
        object.__setattr__(request.reviewed_evidence, "unit_multiplier", multiplier)
        outcome = _build(monkeypatch, request)
        assert outcome.failure is (
            pan_hai.PanHai2014OfficialBalanceBackfillFailure.INPUT_TYPE_MISMATCH
        )
    object.__setattr__(request.reviewed_evidence, "unit_multiplier", Decimal("1"))

    object.__setattr__(request.reviewed_evidence, "field_reviews", list(_field_reviews()))
    outcome = _build(monkeypatch, request)
    assert outcome.failure is (
        pan_hai.PanHai2014OfficialBalanceBackfillFailure.INPUT_TYPE_MISMATCH
    )


@pytest.mark.parametrize("mutation", ["reordered", "duplicate", "wrong-page", "null-as-zero"])
def test_field_tuple_applicability_and_page_fail_payload(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviews = list(_field_reviews())
    if mutation == "reordered":
        reviews[0], reviews[1] = reviews[1], reviews[0]
    elif mutation == "duplicate":
        reviews[1] = reviews[0]
    elif mutation == "wrong-page":
        reviews[0] = replace(reviews[0], pdf_page=78)
    else:
        reviews[-1] = replace(
            reviews[-1],
            source_label="短期应付债券",
            applicability=pan_hai.BalanceFieldApplicability.VALUE,
            value_decimal_text="0",
        )
    outcome = _build(monkeypatch, _request(monkeypatch, evidence=_evidence(field_reviews=tuple(reviews))))
    assert outcome.failure is (
        pan_hai.PanHai2014OfficialBalanceBackfillFailure.FINANCIAL_PAYLOAD_INCOMPLETE
    )


@pytest.mark.parametrize(
    ("field_key", "value"),
    [
        ("total_liab", "58374057829.64"),
        ("total_hldr_eqy_exc_min_int", "9273976463.96"),
        ("total_liab_hldr_eqy", "70889108573.13"),
    ],
)
def test_each_required_reconciliation_failure_maps_to_payload_incomplete(
    field_key: str,
    value: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviews = tuple(
        replace(review, value_decimal_text=value)
        if review.field_key == field_key
        else review
        for review in _field_reviews()
    )
    outcome = _build(monkeypatch, _request(monkeypatch, evidence=_evidence(field_reviews=reviews)))
    assert outcome.failure is (
        pan_hai.PanHai2014OfficialBalanceBackfillFailure.FINANCIAL_PAYLOAD_INCOMPLETE
    )


def test_availability_hash_formula_and_review_causality_fail_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(monkeypatch)
    cases = (
        replace(request.availability, availability_id="sha256:" + "0" * 64),
        replace(
            request.availability,
            available_at=UtcInstant(SOURCE_VISIBILITY.epoch_nanoseconds + 1),
            availability_id=HASH_A,
        ),
        _availability(
            publication_boundary_at=UtcInstant(
                PUBLICATION_BOUNDARY.epoch_nanoseconds - 1
            )
        ),
        _availability(source_visibility_at=UtcInstant(REVIEWED_AT + 1)),
    )
    for availability in cases:
        outcome = _build(monkeypatch, replace(request, availability=availability))
        assert outcome.failure is (
            pan_hai.PanHai2014OfficialBalanceBackfillFailure.FINANCIAL_REVISION_MISMATCH
        )

    too_early = replace(
        request.reviewed_evidence,
        reviewed_at_epoch_nanoseconds=1_699_999_999_999_999_999,
    )
    outcome = _build(monkeypatch, replace(request, reviewed_evidence=too_early))
    assert outcome.failure is (
        pan_hai.PanHai2014OfficialBalanceBackfillFailure.FINANCIAL_REVISION_MISMATCH
    )


def test_backfill_constructor_rejects_hash_cover_scope_and_provider_fiction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome = _build(monkeypatch)
    assert outcome.backfill is not None
    value = outcome.backfill
    with pytest.raises(ValueError, match="catalog identity"):
        replace(value, provider_code="000046.SH", backfill_id="")
    with pytest.raises(ValueError, match="exact cover"):
        replace(
            value,
            covered_member_key=("income_vip", "xshe:000046", "20141231"),
            backfill_id="",
        )
    with pytest.raises(ValueError, match="unsupported scope"):
        replace(value, financial_scope_qualified=True, backfill_id="")
    with pytest.raises(ValueError, match="source identity"):
        replace(value, source_snapshot_id=HASH_A, backfill_id="")
    with pytest.raises(ValueError, match="availability reconstruction"):
        replace(
            value,
            availability=replace(value.availability, availability_id=HASH_A),
            backfill_id="",
        )
    with pytest.raises(ValueError, match="reviewed payload"):
        replace(
            value,
            reviewed_evidence=replace(value.reviewed_evidence, audit_page=75),
            backfill_id="",
        )
    with pytest.raises(ValueError, match="reconstruction hash"):
        replace(value, backfill_id="sha256:" + "0" * 64)


def test_build_failure_mapping_keeps_covered_key_before_publication_integrity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(monkeypatch)

    def broken_cover(*_args: object) -> object:
        raise ValueError("backfill exact cover mismatch")

    monkeypatch.setattr(pan_hai, "_build_backfill", broken_cover)
    outcome = _build(monkeypatch, request)
    assert outcome.failure is (
        pan_hai.PanHai2014OfficialBalanceBackfillFailure.FINANCIAL_PAYLOAD_INCOMPLETE
    )

    def broken_hash(*_args: object) -> object:
        raise ValueError("backfill reconstruction hash mismatch")

    monkeypatch.setattr(pan_hai, "_build_backfill", broken_hash)
    outcome = _build(monkeypatch, request)
    assert outcome.failure is (
        pan_hai.PanHai2014OfficialBalanceBackfillFailure.PUBLICATION_INTEGRITY_FAILURE
    )


def test_malformed_request_and_outcome_are_typed_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome = pan_hai.build_pan_hai_2014_official_balance_backfill_v1(None)  # type: ignore[arg-type]
    assert outcome.failure is (
        pan_hai.PanHai2014OfficialBalanceBackfillFailure.INPUT_TYPE_MISMATCH
    )
    with pytest.raises(ValueError, match="exactly one"):
        pan_hai.PanHai2014OfficialBalanceBackfillOutcome(None, None)
    good = _build(monkeypatch)
    assert good.backfill is not None
    with pytest.raises(ValueError, match="exactly one"):
        pan_hai.PanHai2014OfficialBalanceBackfillOutcome(
            good.backfill,
            pan_hai.PanHai2014OfficialBalanceBackfillFailure.INPUT_TYPE_MISMATCH,
        )
