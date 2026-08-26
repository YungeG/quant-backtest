from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotFailureCode,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from crypto_quant_domain import UtcInstant, canonical_sha256

import crypto_quant_bundle_builder.gree_2023_financial_document_declarations_v1 as declarations

REPORT = b"%PDF-1.5\nreport fixture\n"
CONFIRMATION = b"%PDF-1.5\nconfirmation fixture\n"


def snapshot(monkeypatch: pytest.MonkeyPatch):
    outcome = freeze_source_snapshot(
        members=(
            RawSourceMember(
                declarations._REPORT_MEMBER,
                REPORT,
                "0644",
                10,
                None,
            ),
            RawSourceMember(
                declarations._CONFIRMATION_MEMBER,
                CONFIRMATION,
                "0644",
                20,
                None,
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="fixture.vendor",
            source_key="fixture.source",
            license_ref="fixture.license",
            retention_policy_ref="fixture.retention",
        ),
    )
    assert outcome.snapshot is not None
    value = outcome.snapshot
    monkeypatch.setattr(declarations, "_SNAPSHOT_ID", value.snapshot_id)
    monkeypatch.setattr(declarations, "_REVIEWED_AT", UtcInstant(21))
    monkeypatch.setattr(declarations, "_CONTENT_TREE_HASH", value.content_tree_hash)
    monkeypatch.setattr(declarations, "_PROVENANCE_HASH", value.provenance_hash)
    monkeypatch.setattr(
        declarations,
        "_REPORT_HASH",
        next(member.content_hash for member in value.members if member.member_key == declarations._REPORT_MEMBER),
    )
    monkeypatch.setattr(
        declarations,
        "_CONFIRMATION_HASH",
        next(
            member.content_hash
            for member in value.members
            if member.member_key == declarations._CONFIRMATION_MEMBER
        ),
    )
    return value


def test_real_scope_declaration_is_reconstructed_and_source_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = snapshot(monkeypatch)
    outcome = declarations.declare_gree_2023_financial_documents_v1(
        source,
        reviewed_at=UtcInstant(21),
    )
    assert outcome.failure is None
    assert outcome.declaration is not None
    value = outcome.declaration

    assert value.source_snapshot_id == source.snapshot_id
    assert value.reviewer_identity == "platform.a-share-research-orchestrator.v1"
    assert value.confirmed_disclosure_date == "20240430"
    assert value.accounting_currency == "CNY"
    assert value.accounting_unit == "yuan"
    assert value.ending_interest_bearing_debt == "88533001486.99"
    assert value.ending_depreciation_and_amortization == "5283331216.38"
    assert value.source_bounded is True
    assert value.revision_closure_complete is False
    assert value.decision_grade_eligible is False
    assert value.deployment_authorized is False
    body = value.to_canonical_dict()
    declaration_hash = body.pop("declaration_hash")
    assert declaration_hash == canonical_sha256(body)
    assert declaration_hash == "sha256:5a69365ba8759025ce8a9b1480b75d18ae64c8dc75bb3bd3731a8fe19df8761f"
    assert outcome.to_canonical_dict()["declaration"] == value.to_canonical_dict()


@pytest.mark.parametrize(
    ("reviewed_at", "code"),
    [
        (UtcInstant(20), declarations.Gree2023FinancialDeclarationFailureCode.REVIEW_TIME_INVALID),
        (UtcInstant(21), None),
    ],
)
def test_review_time_is_not_backdated(
    reviewed_at: UtcInstant,
    code: declarations.Gree2023FinancialDeclarationFailureCode | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome = declarations.declare_gree_2023_financial_documents_v1(
        snapshot(monkeypatch), reviewed_at=reviewed_at
    )
    assert (outcome.failure.code if outcome.failure else None) is code


def test_snapshot_verification_and_identity_failures_are_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = snapshot(monkeypatch)
    tampered = replace(source, snapshot_id="sha256:" + "0" * 64)
    failed = declarations.declare_gree_2023_financial_documents_v1(
        tampered, reviewed_at=UtcInstant(21)
    )
    assert failed.failure is not None
    assert failed.failure.code is SourceSnapshotFailureCode.SNAPSHOT_ID_MISMATCH

    tree = declarations.declare_gree_2023_financial_documents_v1(
        replace(source, content_tree_hash="sha256:" + "0" * 64),
        reviewed_at=UtcInstant(21),
    )
    provenance = declarations.declare_gree_2023_financial_documents_v1(
        replace(source, provenance_hash="sha256:" + "0" * 64),
        reviewed_at=UtcInstant(21),
    )
    assert tree.failure is not None
    assert tree.failure.code is SourceSnapshotFailureCode.CONTENT_TREE_HASH_MISMATCH
    assert provenance.failure is not None
    assert provenance.failure.code is SourceSnapshotFailureCode.PROVENANCE_HASH_MISMATCH

    other = freeze_source_snapshot(
        members=(
            RawSourceMember(declarations._REPORT_MEMBER, b"other", "0644", 10, None),
            RawSourceMember(
                declarations._CONFIRMATION_MEMBER,
                CONFIRMATION,
                "0644",
                20,
                None,
            ),
        ),
        provenance=source.provenance,
    ).snapshot
    assert other is not None
    mismatch = declarations.declare_gree_2023_financial_documents_v1(
        other, reviewed_at=UtcInstant(21)
    )
    assert mismatch.failure is not None
    assert (
        mismatch.failure.code
        is declarations.Gree2023FinancialDeclarationFailureCode.SOURCE_SNAPSHOT_IDENTITY_MISMATCH
    )

    missing = freeze_source_snapshot(
        members=(
            RawSourceMember(declarations._REPORT_MEMBER, REPORT, "0644", 10, None),
        ),
        provenance=source.provenance,
    ).snapshot
    assert missing is not None
    monkeypatch.setattr(declarations, "_SNAPSHOT_ID", missing.snapshot_id)
    monkeypatch.setattr(declarations, "_CONTENT_TREE_HASH", missing.content_tree_hash)
    monkeypatch.setattr(declarations, "_PROVENANCE_HASH", missing.provenance_hash)
    monkeypatch.setattr(
        declarations,
        "_REPORT_HASH",
        missing.members[0].content_hash,
    )
    missing_result = declarations.declare_gree_2023_financial_documents_v1(
        missing, reviewed_at=UtcInstant(21)
    )
    assert missing_result.failure is not None
    assert (
        missing_result.failure.code
        is declarations.Gree2023FinancialDeclarationFailureCode.DOCUMENT_IDENTITY_MISMATCH
    )


def test_source_member_input_order_does_not_change_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = snapshot(monkeypatch)
    reversed_source = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                member.member_key,
                source.member_bytes(member.member_key),
                member.mode,
                member.acquired_at_epoch_nanoseconds,
                member.declared_sha256,
            )
            for member in reversed(source.members)
        ),
        provenance=source.provenance,
    ).snapshot
    assert reversed_source is not None
    assert reversed_source.snapshot_id == source.snapshot_id
    first = declarations.declare_gree_2023_financial_documents_v1(
        source, reviewed_at=UtcInstant(21)
    )
    second = declarations.declare_gree_2023_financial_documents_v1(
        reversed_source, reviewed_at=UtcInstant(21)
    )
    assert first.to_canonical_dict() == second.to_canonical_dict()


def test_declaration_constructor_rejects_forged_debt_da_and_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome = declarations.declare_gree_2023_financial_documents_v1(
        snapshot(monkeypatch), reviewed_at=UtcInstant(21)
    )
    assert outcome.declaration is not None
    value = outcome.declaration

    with pytest.raises(ValueError, match="exact value"):
        replace(
            value,
            bank_borrowings_and_other="10.00",
            bonds_payable="20.00",
            lease_liabilities_including_current="30.00",
            non_debt_dividends_payable="40.00",
            official_table_total="100.00",
            ending_interest_bearing_debt="60.00",
            declaration_hash="",
        )
    with pytest.raises(ValueError, match="debt reconciliation"):
        replace(value, ending_interest_bearing_debt="1.00")
    with pytest.raises(ValueError, match="D&A reconciliation"):
        replace(value, ending_depreciation_and_amortization="1.00")
    with pytest.raises(ValueError, match="declaration hash"):
        replace(value, declaration_hash="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="review time"):
        replace(value, reviewed_at=UtcInstant(19), declaration_hash="")
    with pytest.raises(TypeError, match="exact true"):
        replace(value, source_bounded=False, declaration_hash="")
    with pytest.raises(TypeError, match="exact false"):
        replace(value, decision_grade_eligible=True, declaration_hash="")

    class Text(str):
        pass

    with pytest.raises(ValueError, match="context"):
        replace(value, reviewer_identity=Text(value.reviewer_identity), declaration_hash="")
    with pytest.raises(TypeError, match="declaration_hash"):
        replace(value, declaration_hash=Text(""))


@pytest.mark.parametrize(
    ("message", "code"),
    [
        ("declaration context mismatch", declarations.Gree2023FinancialDeclarationFailureCode.DECLARATION_CONTEXT_MISMATCH),
        ("debt reconciliation mismatch", declarations.Gree2023FinancialDeclarationFailureCode.DEBT_RECONCILIATION_MISMATCH),
        ("D&A reconciliation mismatch", declarations.Gree2023FinancialDeclarationFailureCode.DA_RECONCILIATION_MISMATCH),
        ("other", declarations.Gree2023FinancialDeclarationFailureCode.DECLARATION_RECONSTRUCTION_MISMATCH),
    ],
)
def test_declaration_failure_mapping_preserves_precedence(
    message: str,
    code: declarations.Gree2023FinancialDeclarationFailureCode,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = snapshot(monkeypatch)

    def broken(*_args: object) -> object:
        raise ValueError(message)

    monkeypatch.setattr(declarations, "_declaration", broken)
    outcome = declarations.declare_gree_2023_financial_documents_v1(
        source, reviewed_at=UtcInstant(21)
    )
    assert outcome.failure is not None
    assert outcome.failure.code is code


def test_qualification_literal_failure_maps_to_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = snapshot(monkeypatch)

    def broken(*_args: object) -> object:
        raise TypeError("qualification flags must be exact false")

    monkeypatch.setattr(declarations, "_declaration", broken)
    outcome = declarations.declare_gree_2023_financial_documents_v1(
        source, reviewed_at=UtcInstant(21)
    )
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is declarations.Gree2023FinancialDeclarationFailureCode.DECLARATION_CONTEXT_MISMATCH
    )


def test_input_types_fail_before_snapshot_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = snapshot(monkeypatch)
    outcome = declarations.declare_gree_2023_financial_documents_v1(
        source, reviewed_at=21  # type: ignore[arg-type]
    )
    assert outcome.failure is not None
    assert outcome.failure.code is declarations.Gree2023FinancialDeclarationFailureCode.INPUT_MISMATCH


def test_real_source_snapshot_when_explicitly_configured() -> None:
    root_value = os.environ.get("QB_FIN_REAL_SNAPSHOT_ROOT")
    if not root_value:
        pytest.skip("QB_FIN_REAL_SNAPSHOT_ROOT is not configured")
    root = Path(root_value)
    receipt = json.loads((root / "acquisition-receipt.json").read_bytes())
    members = {member["member_key"]: member for member in receipt["snapshot"]["members"]}
    source = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                member_key,
                (root / member_key).read_bytes(),
                evidence["mode"],
                evidence["acquired_at_epoch_nanoseconds"],
                evidence["declared_sha256"],
            )
            for member_key, evidence in members.items()
        ),
        provenance=SourceSnapshotProvenance(**receipt["snapshot"]["provenance"]),
    ).snapshot
    assert source is not None
    outcome = declarations.declare_gree_2023_financial_documents_v1(
        source, reviewed_at=declarations._REVIEWED_AT
    )
    assert outcome.failure is None
    assert outcome.declaration is not None
    assert outcome.declaration.declaration_hash == "sha256:59e09eb542a6e2ec480a7b8ed322d9ae9106416460f0999216fd5564f7278007"
