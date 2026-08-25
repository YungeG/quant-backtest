from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from crypto_quant_domain import UtcInstant, canonical_sha256

import crypto_quant_bundle_builder.gree_2023_financial_document_declarations_v1 as declarations
import crypto_quant_bundle_builder.gree_2023_financial_statement_normalization_v1 as normalization
import crypto_quant_bundle_builder.gree_2023_financial_statement_trio_selection_v1 as selection

AVAILABLE_AT = UtcInstant(1_714_959_000_000_000_000)
REVISION_IDS = (
    "sha256:8957590f45f32ed9b285e940f2fa0c0524cb28377e86c745ab39aa3875ba63e8",
    "sha256:3e64ee623ca3676f1ec10daf56588dceabdd77a41ba0419d4c9010241313f45d",
    "sha256:71f4428e79d3bd7638cc9c1d98c1471f9802e9a90d25f7fa06b739bc57f0f986",
)


def _revision(
    kind: normalization.Gree2023FinancialStatementKind,
    economic_key: str,
    lineage_key: str,
    member_key: str,
    member_hash: str,
    row_hashes: tuple[str, ...],
    update_flags: tuple[str, ...],
    raw_nulls: tuple[str, ...],
    line_items: tuple[tuple[str, str | None], ...],
    line_items_hash: str,
    revision_id: str,
) -> normalization.Gree2023FinancialStatementObservationRevisionV1:
    return normalization.Gree2023FinancialStatementObservationRevisionV1(
        schema_version=1,
        statement_kind=kind,
        economic_statement_key=economic_key,
        observation_lineage_key=lineage_key,
        instrument_id="xshe:000651",
        report_period_end="20231231",
        period_kind="ANNUAL",
        consolidation_scope="CONSOLIDATED",
        accounting_currency="CNY",
        accounting_unit="yuan",
        presentation_basis="CURRENT_CONSOLIDATED",
        announcement_date="20240430",
        actual_announcement_date="20240430",
        available_at_utc=AVAILABLE_AT,
        source_snapshot_id="sha256:dec0abb1828f8b87256347e72b6ccfe2f84a2ca13f36aa1415c9a53e96a0c7d5",
        source_content_tree_hash="sha256:d7e92674dd42a4eeabfde354922cfafa9d50837f2076c1ad88233da8c0456b13",
        source_provenance_hash="sha256:0fcef32df8c6b41ef0ce55121adc9c392cf483ca71134dc27175f6c9512cab17",
        source_member_key=member_key,
        source_member_content_hash=member_hash,
        source_row_hashes=row_hashes,
        provider_update_flags=update_flags,
        official_document_hash="sha256:32ebc475a2291ce4f1b5c1a9f9da55227e03192f07e75041e976c29d213ec8aa",
        publication_confirmation_hash="sha256:a78a67865a7ea989c4fd8b053fad1aa75f36d22c10d14387800ff16b698dbc60",
        declaration_hash="sha256:59e09eb542a6e2ec480a7b8ed322d9ae9106416460f0999216fd5564f7278007",
        raw_null_fields=raw_nulls,
        line_items=line_items,
        line_items_hash=line_items_hash,
        provider_revision_id=None,
        supersedes_revision_id=None,
        source_bounded=True,
        revision_closure_complete=False,
        decision_grade_eligible=False,
        deployment_authorized=False,
        revision_id=revision_id,
    )


def _exact_observation_set() -> normalization.Gree2023FinancialStatementObservationSetV1:
    revisions = (
        _revision(
            normalization.Gree2023FinancialStatementKind.INCOME,
            "sha256:57858dce64ca6e0a61848a114288b4ca95ad523e66bfd2cc7cc17aff0bf2de4c",
            "sha256:6204b3bf96688eb47b8358766dec474957caf4e633b42627827ad2904857719f",
            "response/tushare/income/000651.SZ-20231231-20240430-v2.json",
            "sha256:fcde549fe51112d8721810476483c88cb2b509fbcf0e8483ddd87c435edf1d35",
            ("sha256:7650431917f2c6d302075cb08265e2c0993681bff2e964f793d179476792e4a0",),
            ("1",),
            (),
            (
                ("revenue", "203979266387.09"),
                ("operate_profit", "32864780357.76"),
                ("total_profit", "32815703838.19"),
                ("income_tax", "5096680924.6"),
                ("n_income", "27719022913.59"),
                ("n_income_attr_p", "29017387604.18"),
                ("minority_gain", "-1298364690.59"),
                ("fin_exp_int_exp", "2962205439.75"),
                ("ebit", "28716608257.66"),
                ("ebitda", "33999939474.04"),
            ),
            "sha256:bde8708f468527a65be273a53f03f453c59e15f7ce2af2bfaecc559792ad37c7",
            REVISION_IDS[0],
        ),
        _revision(
            normalization.Gree2023FinancialStatementKind.BALANCE,
            "sha256:69e29dc458fc1427d60c4be3c692c3e7b03949d9a520118b4b534db2ed70494e",
            "sha256:c855ed3f778100876797f2bef527625099f401a67871646d218a0082f37e3162",
            "response/tushare/balancesheet/000651.SZ-20231231-20240430-v2.json",
            "sha256:59e6d57ea45aa0649c402327e67b7098618f71c636ff0f5be670030552e4960d",
            (
                "sha256:42558caf71776422ea55d8c54f5cbe20c5a5869c6a72e44b37d7d8662adb37e3",
                "sha256:f891a94138f37fb1dad697354f9278a45e779a2b8c700ffafa0ea34090a00688",
            ),
            ("0", "1"),
            ("bond_payable", "st_bonds_payable"),
            (
                ("money_cap", "124104987289.62"),
                ("total_assets", "368053902576.37"),
                ("total_liab", "247407749159.93"),
                ("total_hldr_eqy_inc_min_int", "120646153416.44"),
                ("total_hldr_eqy_exc_min_int", "116793716103.39"),
                ("minority_int", "3852437313.05"),
                ("total_liab_hldr_eqy", "368053902576.37"),
                ("st_borr", "26443476388.52"),
                ("non_cur_liab_due_1y", "20605521073.03"),
                ("lt_borr", "39035742535.09"),
                ("bond_payable", "0.00"),
                ("st_bonds_payable", "0.00"),
                ("lease_liab", "767007951.92"),
            ),
            "sha256:9906ef7f84c2ee2713d59f8884948bf414c5af318f572b2e12c4d0f948ad6792",
            REVISION_IDS[1],
        ),
        _revision(
            normalization.Gree2023FinancialStatementKind.CASH_FLOW,
            "sha256:fc49c3dfc2d9375a355f74d5b3cbe3d2734e93171a870ff01dca38ff768fe994",
            "sha256:0a5f22ce3a15576d168aefd6dc8c9c5a4c7b1fdd57901424bbc1d4b96f26c376",
            "response/tushare/cashflow/000651.SZ-20231231-20240430-v2.json",
            "sha256:94b9483fd4dd37c9f83c0d5d0174473497ac5641f915490e452bacdb379a5e60",
            ("sha256:7765c5315c9e65a9799af793050520dc2a7f21dd4dc9e410820b0b326ccbeba7",),
            ("1",),
            ("use_right_asset_dep", "lt_amort_deferred_exp"),
            (
                ("n_cashflow_act", "56398426354.17"),
                ("c_pay_acq_const_fiolta", "5425734302.92"),
                ("depr_fa_coga_dpba", "4808144624.82"),
                ("use_right_asset_dep", None),
                ("amort_intang_assets", "475186591.56"),
                ("lt_amort_deferred_exp", None),
                ("c_cash_equ_end_period", "30914196186.41"),
                ("free_cashflow", "14242168298.2958"),
            ),
            "sha256:37f772107e53728a6be8ebb6e516c152ee0c01d35c1f571ca0f295c389ce64cf",
            REVISION_IDS[2],
        ),
    )
    return normalization.Gree2023FinancialStatementObservationSetV1(
        schema_version=1,
        source_snapshot_id="sha256:dec0abb1828f8b87256347e72b6ccfe2f84a2ca13f36aa1415c9a53e96a0c7d5",
        declaration_hash="sha256:59e09eb542a6e2ec480a7b8ed322d9ae9106416460f0999216fd5564f7278007",
        available_at_utc=AVAILABLE_AT,
        revisions=revisions,
        ending_interest_bearing_debt="88533001486.99",
        ending_depreciation_and_amortization="5283331216.38",
        source_bounded=True,
        revision_closure_complete=False,
        decision_grade_eligible=False,
        deployment_authorized=False,
        observation_set_hash="sha256:632206f85bcff71dbcccfd20a3593e14fb895b33bd138ac25bbf9b947e4a4a7c",
    )


def test_first_visible_selection_pins_golden() -> None:
    observation_set = _exact_observation_set()
    outcome = selection.select_gree_2023_financial_statement_trio_v1(
        observation_set, AVAILABLE_AT
    )
    assert outcome.failure is None
    assert outcome.selection is not None
    result = outcome.selection
    assert result.request_hash == "sha256:6c8e38908cbc77f0ba4bfac62d8381235489e667b592fd2702fa37833e49cc7d"
    assert result.selection_hash == "sha256:34d09c7649143ee784f95f25873dd462ee56fc37cae91fa8bc7a604ef37f890c"
    assert result.chosen_revision_ids == REVISION_IDS
    assert result.visible_candidate_revision_ids == REVISION_IDS
    assert result.rejected_pre_adjustment_revision_ids == ()
    assert result.observation_set.to_canonical_dict() == observation_set.to_canonical_dict()
    assert result.source_snapshot_family_hash == "sha256:0d94a3298739339e6b54315f3193eba722604f0c354246abf06046c10dc6b6b9"
    assert result.source_bounded is True
    assert result.revision_closure_complete is False
    assert result.decision_grade_eligible is False
    assert result.deployment_authorized is False
    assert selection.Gree2023FinancialTrioSelectionOutcome(result, None).to_canonical_dict() == outcome.to_canonical_dict()


def test_one_nanosecond_before_is_not_visible() -> None:
    outcome = selection.select_gree_2023_financial_statement_trio_v1(
        _exact_observation_set(), UtcInstant(AVAILABLE_AT.epoch_nanoseconds - 1)
    )
    assert outcome.selection is None
    assert outcome.failure is not None
    assert outcome.failure.code is selection.Gree2023FinancialTrioSelectionFailureCode.NOT_VISIBLE
    assert outcome.failure.to_canonical_dict()["failure_hash"] == canonical_sha256(
        {
            "type": "gree_2023_financial_trio_selection_failure",
            "schema_version": 1,
            "code": "NOT_VISIBLE",
        }
    )


def test_later_decision_changes_request_and_selection_only() -> None:
    first = selection.select_gree_2023_financial_statement_trio_v1(
        _exact_observation_set(), AVAILABLE_AT
    ).selection
    later = selection.select_gree_2023_financial_statement_trio_v1(
        _exact_observation_set(), UtcInstant(AVAILABLE_AT.epoch_nanoseconds + 1)
    ).selection
    assert first is not None and later is not None
    assert later.chosen_revision_ids == first.chosen_revision_ids
    assert later.visible_candidate_revision_ids == first.visible_candidate_revision_ids
    assert later.observation_set.to_canonical_dict() == first.observation_set.to_canonical_dict()
    assert later.request_hash != first.request_hash
    assert later.selection_hash != first.selection_hash


def test_observation_set_forgery_maps_to_mismatch() -> None:
    forged_set = _exact_observation_set()
    object.__setattr__(forged_set, "observation_set_hash", "sha256:" + "0" * 64)
    outcome = selection.select_gree_2023_financial_statement_trio_v1(forged_set, AVAILABLE_AT)
    assert outcome.selection is None
    assert outcome.failure is not None
    assert outcome.failure.code is selection.Gree2023FinancialTrioSelectionFailureCode.OBSERVATION_SET_MISMATCH

    nested = _exact_observation_set()
    object.__setattr__(nested.revisions[0], "revision_id", "sha256:" + "0" * 64)
    outcome = selection.select_gree_2023_financial_statement_trio_v1(nested, AVAILABLE_AT)
    assert outcome.failure is not None
    assert outcome.failure.code is selection.Gree2023FinancialTrioSelectionFailureCode.OBSERVATION_SET_MISMATCH


def test_selection_constructor_rejects_coherent_forgery() -> None:
    result = selection.select_gree_2023_financial_statement_trio_v1(
        _exact_observation_set(), AVAILABLE_AT
    ).selection
    assert result is not None
    with pytest.raises(ValueError, match="selection evidence"):
        replace(
            result,
            chosen_revision_ids=tuple(reversed(REVISION_IDS)),
            visible_candidate_revision_ids=tuple(reversed(REVISION_IDS)),
            selection_hash="",
        )
    with pytest.raises(ValueError, match="selection evidence"):
        replace(
            result,
            request_hash=canonical_sha256({"forged": True}),
            selection_hash="",
        )
    with pytest.raises(ValueError, match="selection_hash"):
        replace(result, selection_hash="sha256:" + "0" * 64)
    with pytest.raises(TypeError, match="exact false"):
        replace(result, decision_grade_eligible=True, selection_hash="")


def test_input_and_result_failure_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_args: object) -> object:
        raise ValueError("synthetic result failure")

    monkeypatch.setattr(selection, "_build_selection", broken)
    first = selection.select_gree_2023_financial_statement_trio_v1(
        object(), object()  # type: ignore[arg-type]
    )
    assert first.failure is not None
    assert first.failure.code is selection.Gree2023FinancialTrioSelectionFailureCode.INPUT_MISMATCH

    forged_instant = UtcInstant(AVAILABLE_AT.epoch_nanoseconds)
    object.__setattr__(forged_instant, "epoch_nanoseconds", "invalid")
    forged = selection.select_gree_2023_financial_statement_trio_v1(
        _exact_observation_set(), forged_instant
    )
    assert forged.selection is None
    assert forged.failure is not None
    assert forged.failure.code is selection.Gree2023FinancialTrioSelectionFailureCode.INPUT_MISMATCH

    last = selection.select_gree_2023_financial_statement_trio_v1(
        _exact_observation_set(), AVAILABLE_AT
    )
    assert last.selection is None
    assert last.failure is not None
    assert last.failure.code is selection.Gree2023FinancialTrioSelectionFailureCode.RESULT_RECONSTRUCTION_MISMATCH


def _real_snapshot(root: Path):
    receipt = json.loads((root / "acquisition-receipt.json").read_bytes())
    members = {member["member_key"]: member for member in receipt["snapshot"]["members"]}
    outcome = freeze_source_snapshot(
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
    )
    assert outcome.snapshot is not None
    return outcome.snapshot


def _real_declaration(root: Path) -> declarations.Gree2023FinancialDocumentDeclarationsV1:
    value = json.loads((root / "declaration.json").read_bytes())
    publication = value["publication_confirmation"]
    unit = value["statement_unit"]
    debt = value["financing_liability"]
    da = value["depreciation_and_amortization"]
    return declarations.Gree2023FinancialDocumentDeclarationsV1(
        source_snapshot_id=value["source_snapshot_id"],
        content_tree_hash=value["content_tree_hash"],
        provenance_hash=value["provenance_hash"],
        reviewer_identity=value["reviewer_identity"],
        reviewed_at=UtcInstant(value["reviewed_at"]["epoch_nanoseconds"]),
        confirmed_disclosure_date=publication["confirmed_disclosure_date"],
        accounting_currency=unit["accounting_currency"],
        accounting_unit=unit["accounting_unit"],
        bank_borrowings_and_other=debt["bank_borrowings_and_other"],
        bonds_payable=debt["bonds_payable"],
        lease_liabilities_including_current=debt["lease_liabilities_including_current"],
        non_debt_dividends_payable=debt["non_debt_dividends_payable"],
        official_table_total=debt["official_table_total"],
        ending_interest_bearing_debt=debt["ending_interest_bearing_debt"],
        combined_depreciation_amount=da["combined_depreciation_amount"],
        intangible_amortization_amount=da["intangible_amortization_amount"],
        separate_use_right_addition=da["separate_use_right_addition"],
        separate_long_term_deferred_addition=da["separate_long_term_deferred_addition"],
        ending_depreciation_and_amortization=da["ending_depreciation_and_amortization"],
        source_bounded=value["source_bounded"],
        revision_closure_complete=value["revision_closure_complete"],
        decision_grade_eligible=value["decision_grade_eligible"],
        deployment_authorized=value["deployment_authorized"],
        declaration_hash=value["declaration_hash"],
    )


def test_real_normalization_to_selection_when_explicitly_configured() -> None:
    snapshot_root = os.environ.get("QB_FIN_REAL_SNAPSHOT_ROOT")
    declaration_root = os.environ.get("QB_FIN_REAL_DECLARATION_ROOT")
    if not snapshot_root or not declaration_root:
        pytest.skip("QB_FIN_REAL_SNAPSHOT_ROOT and QB_FIN_REAL_DECLARATION_ROOT are not configured")
    normalized = normalization.normalize_gree_2023_financial_statements_v1(
        _real_snapshot(Path(snapshot_root)),
        _real_declaration(Path(declaration_root)),
    )
    assert normalized.failure is None
    assert normalized.observation_set is not None
    assert normalized.observation_set.observation_set_hash == "sha256:632206f85bcff71dbcccfd20a3593e14fb895b33bd138ac25bbf9b947e4a4a7c"
    outcome = selection.select_gree_2023_financial_statement_trio_v1(
        normalized.observation_set, AVAILABLE_AT
    )
    assert outcome.failure is None
    assert outcome.selection is not None
    assert outcome.selection.request_hash == "sha256:6c8e38908cbc77f0ba4bfac62d8381235489e667b592fd2702fa37833e49cc7d"
    assert outcome.selection.selection_hash == "sha256:34d09c7649143ee784f95f25873dd462ee56fc37cae91fa8bc7a604ef37f890c"
    assert outcome.selection.chosen_revision_ids == REVISION_IDS
