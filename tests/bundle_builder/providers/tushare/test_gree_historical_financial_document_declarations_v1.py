from __future__ import annotations

import hashlib
import json
import os
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotFailureCode,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from crypto_quant_domain import UtcInstant, canonical_sha256

import crypto_quant_bundle_builder.gree_historical_financial_document_declarations_v1 as declarations


SUCCESS_HASHES = {
    "20181231": "sha256:51b1ae41791336ead0487148e721c530ff0de8b5a718d81d4b3d2fe63a55a575",
    "20191231": "sha256:0f52ca93b04c25d2135a584d853198ad2655f0cec31cc161867c22010927aa96",
    "20201231": "sha256:14143974d80d622721ecf78e3eae1e3467815366dc9bd90657774bd8473ee099",
    "20221231": "sha256:1124c88497385f9233df6c4f8c6ece397379d382a18d27aeacead31b82539aba",
}


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    *,
    reverse: bool = False,
    omit_member: str | None = None,
    acquired_start: int = 10,
    mutate_member: str | None = None,
    trust_member_hashes: bool = True,
):
    original_sources = {
        declarations._METADATA_MEMBER: b'{"synthetic":"metadata"}',
        **{
            member: f"%PDF-1.5\n{period}\n".encode()
            for period, member, _content_hash in declarations._DOCUMENT_FACTS
        },
    }
    sources = dict(original_sources)
    if mutate_member is not None:
        sources[mutate_member] += b"mutated"
    ordered = [declarations._METADATA_MEMBER] + [
        member for _period, member, _content_hash in declarations._DOCUMENT_FACTS
    ]
    members = tuple(
        RawSourceMember(key, sources[key], "0644", acquired_start + index, None)
        for index, key in enumerate(ordered)
        if key != omit_member
    )
    outcome = freeze_source_snapshot(
        members=tuple(reversed(members)) if reverse else members,
        provenance=SourceSnapshotProvenance(
            vendor_key="synthetic.vendor",
            source_key="synthetic.gree.history",
            license_ref="synthetic.license",
            retention_policy_ref="synthetic.retention",
        ),
    )
    assert outcome.snapshot is not None
    snapshot = outcome.snapshot
    by_key = {member.member_key: member for member in snapshot.members}
    monkeypatch.setattr(declarations, "_SNAPSHOT_ID", snapshot.snapshot_id)
    monkeypatch.setattr(declarations, "_CONTENT_TREE_HASH", snapshot.content_tree_hash)
    monkeypatch.setattr(declarations, "_PROVENANCE_HASH", snapshot.provenance_hash)
    expected_metadata_hash = (
        by_key.get(
            declarations._METADATA_MEMBER,
            SimpleNamespace(content_hash="sha256:" + "0" * 64),
        ).content_hash
        if trust_member_hashes
        else "sha256:"
        + hashlib.sha256(original_sources[declarations._METADATA_MEMBER]).hexdigest()
    )
    monkeypatch.setattr(declarations, "_METADATA_HASH", expected_metadata_hash)
    monkeypatch.setattr(declarations, "_REVIEWED_AT", UtcInstant(100))
    monkeypatch.setattr(
        declarations,
        "_DOCUMENT_FACTS",
        tuple(
            (
                period,
                member,
                (
                    by_key.get(member, SimpleNamespace(content_hash=content_hash)).content_hash
                    if trust_member_hashes
                    else "sha256:" + hashlib.sha256(original_sources[member]).hexdigest()
                ),
            )
            for period, member, content_hash in declarations._DOCUMENT_FACTS
        ),
    )
    return snapshot, UtcInstant(100)


def _declare(monkeypatch: pytest.MonkeyPatch, period: str, **kwargs: object):
    snapshot, reviewed_at = _configure(monkeypatch, **kwargs)
    return declarations.declare_gree_historical_financial_period_v1(
        snapshot, period, reviewed_at=reviewed_at
    )


def test_four_synthetic_successes_preserve_exact_period_bodies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_debt = {
        "20181231": "22383629781.83",
        "20191231": "17344021324.26",
        "20201231": "23201159352.29",
        "20221231": "86027130079.25",
    }
    expected_da = {
        "20181231": "3110329271.82",
        "20191231": "3194419239.65",
        "20201231": "3588706333.78",
        "20221231": "4997685416.88",
    }
    for period in declarations._SUCCESS_PERIODS:
        outcome = _declare(monkeypatch, period)
        assert outcome.failure is None
        assert outcome.declaration is not None
        value = outcome.declaration
        assert value.report_period == period
        assert value.ending_interest_bearing_debt == expected_debt[period]
        assert value.ending_depreciation_and_amortization == expected_da[period]
        assert value.declaration_hash == canonical_sha256(value._body())
        body = value.to_canonical_dict()
        assert body["publication_evidence"]["source_member_key"] == declarations._METADATA_MEMBER
        assert body["publication_evidence"]["source_content_hash"] == declarations._METADATA_HASH
        assert body["statement_unit"]["accounting_currency"] == "CNY"
        assert body["statement_unit"]["accounting_unit"] == "yuan"
        assert body["source_bounded"] is True
        assert body["revision_closure_complete"] is False
        assert body["decision_grade_eligible"] is False
        assert body["deployment_authorized"] is False

    value_2022 = _declare(monkeypatch, "20221231").declaration
    assert value_2022 is not None
    body_2022 = value_2022.to_canonical_dict()
    assert body_2022["statement_unit"]["unit_evidence"] == [
        {
            "report_page": 151,
            "pdf_page": 152,
            "text": "如无特殊说明，金额单位为人民币元",
        }
    ]
    assert body_2022["depreciation_and_amortization"]["combined_depreciation_includes"] == [
        "fixed_assets",
        "investment_property",
        "right_of_use_assets",
    ]
    assert body_2022["depreciation_and_amortization"]["separate_long_term_deferred_addition"] == "27739400.53"


def test_2021_conflict_is_canonical_and_returns_no_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome = _declare(monkeypatch, "20211231")
    assert outcome.declaration is None
    assert outcome.failure is not None
    failure = outcome.failure
    assert failure.code is declarations.GreeHistoricalFinancialDeclarationFailureCode.DEBT_SCOPE_INCOMPLETE
    assert failure.report_period == "20211231"
    assert failure.debt_scope_conflict is not None
    conflict = failure.debt_scope_conflict
    assert conflict.short_bonds_payable == "4048840948.73"
    assert conflict.short_bonds_already_in_official_total is True
    assert conflict.omitted_financing_report_page == 187
    assert conflict.omitted_financing_pdf_page == 188
    assert conflict.narrow_candidate == "43561695281.25"
    assert conflict.broad_candidate == "46293375395.45"
    assert conflict.conflict_hash == canonical_sha256(conflict._body())
    assert failure.failure_hash == canonical_sha256(failure._body())


def test_failure_precedence_and_period_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, reviewed_at = _configure(monkeypatch)
    invalid = declarations.declare_gree_historical_financial_period_v1(
        object(), object(), reviewed_at=object()  # type: ignore[arg-type]
    )
    assert invalid.failure is not None
    assert invalid.failure.code is declarations.GreeHistoricalFinancialDeclarationFailureCode.INPUT_MISMATCH
    assert invalid.failure.report_period is None

    class Period(str):
        pass

    for invalid_period in (1, Period("20181231")):
        exact_snapshot, exact_review = _configure(monkeypatch)
        non_exact_period = declarations.declare_gree_historical_financial_period_v1(
            exact_snapshot, invalid_period, reviewed_at=exact_review  # type: ignore[arg-type]
        )
        assert non_exact_period.failure is not None
        assert non_exact_period.failure.code is declarations.GreeHistoricalFinancialDeclarationFailureCode.INPUT_MISMATCH
        assert non_exact_period.failure.report_period is None

    forged_instant = UtcInstant(100)
    object.__setattr__(forged_instant, "epoch_nanoseconds", "invalid")
    invalid_instant = declarations.declare_gree_historical_financial_period_v1(
        snapshot, "unsupported", reviewed_at=forged_instant
    )
    assert invalid_instant.failure is not None
    assert invalid_instant.failure.code is declarations.GreeHistoricalFinancialDeclarationFailureCode.INPUT_MISMATCH
    assert invalid_instant.failure.report_period == "unsupported"

    real_verify = declarations.verify_source_snapshot
    monkeypatch.setattr(
        declarations,
        "verify_source_snapshot",
        lambda _snapshot: SimpleNamespace(
            failure=SimpleNamespace(code=SourceSnapshotFailureCode.ARCHIVE_INVALID)
        ),
    )
    nested = declarations.declare_gree_historical_financial_period_v1(
        snapshot, "unsupported", reviewed_at=reviewed_at
    )
    assert nested.failure is not None
    assert nested.failure.code is SourceSnapshotFailureCode.ARCHIVE_INVALID
    assert nested.failure.report_period == "unsupported"
    monkeypatch.setattr(declarations, "verify_source_snapshot", real_verify)

    snapshot, reviewed_at = _configure(monkeypatch)
    unsupported = declarations.declare_gree_historical_financial_period_v1(
        snapshot, "20171231", reviewed_at=reviewed_at
    )
    assert unsupported.failure is not None
    assert unsupported.failure.code is declarations.GreeHistoricalFinancialDeclarationFailureCode.PERIOD_UNSUPPORTED
    assert unsupported.failure.report_period == "20171231"


def test_nested_snapshot_exact_class_forgery_is_input_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, reviewed_at = _configure(monkeypatch)
    object.__setattr__(
        snapshot.members[0], "acquired_at_epoch_nanoseconds", "invalid"
    )
    member_forgery = declarations.declare_gree_historical_financial_period_v1(
        snapshot, "20181231", reviewed_at=reviewed_at
    )
    assert member_forgery.failure is not None
    assert member_forgery.failure.code is declarations.GreeHistoricalFinancialDeclarationFailureCode.INPUT_MISMATCH

    snapshot, reviewed_at = _configure(monkeypatch)
    object.__setattr__(snapshot.provenance, "vendor_key", object())
    provenance_forgery = declarations.declare_gree_historical_financial_period_v1(
        snapshot, "20181231", reviewed_at=reviewed_at
    )
    assert provenance_forgery.failure is not None
    assert provenance_forgery.failure.code is declarations.GreeHistoricalFinancialDeclarationFailureCode.INPUT_MISMATCH


def test_source_document_review_and_reconstruction_failures_are_ordered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, reviewed_at = _configure(monkeypatch)
    other = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                member.member_key,
                snapshot.member_bytes(member.member_key),
                member.mode,
                member.acquired_at_epoch_nanoseconds + 1,
                member.declared_sha256,
            )
            for member in snapshot.members
        ),
        provenance=snapshot.provenance,
    ).snapshot
    assert other is not None
    identity = declarations.declare_gree_historical_financial_period_v1(
        other, "20181231", reviewed_at=reviewed_at
    )
    assert identity.failure is not None
    assert identity.failure.code is declarations.GreeHistoricalFinancialDeclarationFailureCode.SOURCE_SNAPSHOT_IDENTITY_MISMATCH

    member_periods = [(declarations._METADATA_MEMBER, "20181231")] + [
        (member, period) for period, member, _hash in declarations._DOCUMENT_FACTS
    ]
    for omitted, period in member_periods:
        missing, reviewed_at = _configure(monkeypatch, omit_member=omitted)
        document = declarations.declare_gree_historical_financial_period_v1(
            missing, period, reviewed_at=reviewed_at
        )
        assert document.failure is not None
        assert document.failure.code is declarations.GreeHistoricalFinancialDeclarationFailureCode.DOCUMENT_IDENTITY_MISMATCH

    snapshot, _reviewed_at = _configure(monkeypatch)
    review = declarations.declare_gree_historical_financial_period_v1(
        snapshot, "20181231", reviewed_at=UtcInstant(99)
    )
    assert review.failure is not None
    assert review.failure.code is declarations.GreeHistoricalFinancialDeclarationFailureCode.REVIEW_TIME_INVALID

    late_snapshot, matching_review = _configure(monkeypatch, acquired_start=100)
    before_acquisition = declarations.declare_gree_historical_financial_period_v1(
        late_snapshot, "20181231", reviewed_at=matching_review
    )
    assert before_acquisition.failure is not None
    assert before_acquisition.failure.code is declarations.GreeHistoricalFinancialDeclarationFailureCode.REVIEW_TIME_INVALID

    snapshot, reviewed_at = _configure(monkeypatch)
    monkeypatch.setattr(
        declarations,
        "_declaration",
        lambda *_args: (_ for _ in ()).throw(ValueError("synthetic")),
    )
    reconstruction = declarations.declare_gree_historical_financial_period_v1(
        snapshot, "20181231", reviewed_at=reviewed_at
    )
    assert reconstruction.failure is not None
    assert reconstruction.failure.code is declarations.GreeHistoricalFinancialDeclarationFailureCode.DECLARATION_RECONSTRUCTION_MISMATCH


def test_metadata_and_each_report_content_hash_mutation_fail_document_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    member_periods = [(declarations._METADATA_MEMBER, "20181231")] + [
        (member, period) for period, member, _hash in declarations._DOCUMENT_FACTS
    ]
    for member, period in member_periods:
        snapshot, reviewed_at = _configure(
            monkeypatch,
            mutate_member=member,
            trust_member_hashes=False,
        )
        outcome = declarations.declare_gree_historical_financial_period_v1(
            snapshot, period, reviewed_at=reviewed_at
        )
        assert outcome.failure is not None
        assert outcome.failure.code is declarations.GreeHistoricalFinancialDeclarationFailureCode.DOCUMENT_IDENTITY_MISMATCH


@pytest.mark.parametrize("mutation", ["unit", "page", "body"])
def test_nested_authority_mutation_breaks_declaration_reconstruction(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    declaration = _declare(monkeypatch, "20221231").declaration
    assert declaration is not None
    if mutation == "unit":
        facts = list(declarations._STATEMENT_FACTS)
        target = list(facts[-1])
        target[-1] = ((151, 152, "单位：万元"),)
        facts[-1] = tuple(target)
        monkeypatch.setattr(declarations, "_STATEMENT_FACTS", tuple(facts))
    elif mutation == "page":
        facts = list(declarations._STATEMENT_FACTS)
        target = list(facts[-1])
        target[1] = (116, 118)
        facts[-1] = tuple(target)
        monkeypatch.setattr(declarations, "_STATEMENT_FACTS", tuple(facts))
    else:
        facts = list(declarations._DEPRECIATION_FACTS)
        target = list(facts[-1])
        target[4] = ("fixed_assets", "right_of_use_assets")
        facts[-1] = tuple(target)
        monkeypatch.setattr(declarations, "_DEPRECIATION_FACTS", tuple(facts))
    with pytest.raises(ValueError, match="declaration hash"):
        declarations.GreeHistoricalFinancialDeclarationOutcome(declaration, None)


def test_constructors_reject_coherent_forgery_and_are_frozen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    declaration = _declare(monkeypatch, "20221231").declaration
    assert declaration is not None
    with pytest.raises(ValueError, match="exact value"):
        replace(
            declaration,
            ending_interest_bearing_debt="86027130079.26",
            declaration_hash="",
        )
    with pytest.raises(ValueError, match="declaration hash"):
        replace(declaration, declaration_hash="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="exact value"):
        replace(declaration, decision_grade_eligible=True, declaration_hash="")

    conflict_outcome = _declare(monkeypatch, "20211231")
    assert conflict_outcome.failure is not None
    conflict = conflict_outcome.failure.debt_scope_conflict
    assert conflict is not None
    with pytest.raises(ValueError, match="exact value"):
        replace(conflict, short_bonds_payable="0.00", conflict_hash="")
    with pytest.raises(ValueError, match="exact value"):
        replace(conflict, omitted_financing_pdf_page=189, conflict_hash="")
    with pytest.raises(ValueError, match="conflict hash"):
        replace(conflict, conflict_hash="sha256:" + "0" * 64)

    object.__setattr__(declaration, "declaration_hash", "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="declaration hash"):
        declarations.GreeHistoricalFinancialDeclarationOutcome(declaration, None)
    with pytest.raises(FrozenInstanceError):
        declaration.report_period = "forged"  # type: ignore[misc]


def test_source_member_input_order_does_not_change_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _declare(monkeypatch, "20191231")
    second = _declare(monkeypatch, "20191231", reverse=True)
    assert first.to_canonical_dict() == second.to_canonical_dict()


def _real_snapshot(root: Path):
    receipt = json.loads((root / "acquisition-receipt.json").read_bytes())
    snapshot_value = receipt["snapshot"]
    outcome = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                member["member_key"],
                (root / member["member_key"]).read_bytes(),
                member["mode"],
                member["acquired_at_epoch_nanoseconds"],
                member["declared_sha256"],
            )
            for member in snapshot_value["members"]
        ),
        provenance=SourceSnapshotProvenance(**snapshot_value["provenance"]),
    )
    assert outcome.snapshot is not None
    assert outcome.snapshot.to_canonical_dict() == snapshot_value
    return outcome.snapshot


def test_real_snapshot_when_explicitly_configured() -> None:
    root = os.environ.get("QB_FIN_HISTORY_REAL_SNAPSHOT_ROOT")
    if not root:
        pytest.skip("QB_FIN_HISTORY_REAL_SNAPSHOT_ROOT is not configured")
    snapshot = _real_snapshot(Path(root))
    for period, expected_hash in SUCCESS_HASHES.items():
        outcome = declarations.declare_gree_historical_financial_period_v1(
            snapshot,
            period,
            reviewed_at=UtcInstant(1787668131165592196),
        )
        assert outcome.failure is None
        assert outcome.declaration is not None
        assert outcome.declaration.declaration_hash == expected_hash
    conflict = declarations.declare_gree_historical_financial_period_v1(
        snapshot,
        "20211231",
        reviewed_at=UtcInstant(1787668131165592196),
    )
    assert conflict.declaration is None
    assert conflict.failure is not None
    assert conflict.failure.failure_hash == "sha256:2c5b90d0cbd89ccd584c0a33234d796ec9b039abe683ad897b7a5fe61cac5792"
    assert conflict.failure.debt_scope_conflict is not None
    assert conflict.failure.debt_scope_conflict.conflict_hash == "sha256:8cb5ef55e745b6e3858eef5bb1806ebf22c9123490764e79e68f2928ffb66c6f"
