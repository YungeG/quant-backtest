from __future__ import annotations

import hashlib
import json
import os
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotFailureCode,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from crypto_quant_domain import UtcInstant, canonical_sha256

import crypto_quant_bundle_builder.gree_2023_financial_document_declarations_v1 as declaration_module
import crypto_quant_bundle_builder.gree_2023_financial_statement_normalization_v1 as normalization

REPORT = b"%PDF-1.5\nsynthetic report\n"
CONFIRMATION = b"%PDF-1.5\nsynthetic confirmation\n"


class Number(str):
    pass


def _atom(value: object) -> str:
    return str(value) if type(value) is Number else json.dumps(value, ensure_ascii=False)


def _response(fields: tuple[str, ...], rows: list[list[object]]) -> bytes:
    items = "[" + ",".join("[" + ",".join(_atom(value) for value in row) + "]" for row in rows) + "]"
    return (
        "{"
        '"request_id":"synthetic-request",'
        '"code":0,'
        '"data":{'
        f'"fields":{json.dumps(fields, separators=(",", ":"))},'
        f'"items":{items},'
        '"has_more":false,'
        '"count":0},'
        '"msg":"",'
        '"detail":"synthetic"}'
    ).encode()


def _numeric_rows(fields: tuple[str, ...], rows: list[list[object]]) -> list[list[object]]:
    result: list[list[object]] = []
    for row in rows:
        values = list(row)
        for index in range(6, len(fields) - 1):
            if type(values[index]) is str:
                values[index] = Number(values[index])
        result.append(values)
    return result


def _row(fields: tuple[str, ...], values: tuple[str | None, ...], update_flag: str = "1") -> list[object]:
    context: dict[str, object] = {
        "ts_code": "000651.SZ",
        "ann_date": "20240430",
        "f_ann_date": "20240430",
        "end_date": "20231231",
        "report_type": "1",
        "comp_type": "1",
        "update_flag": update_flag,
    }
    context.update(
        {
            name: None if value is None else Number(value)
            for name, value in zip(fields[6:-1], values, strict=True)
        }
    )
    return [context[name] for name in fields]


def payloads() -> dict[str, bytes]:
    income = _row(
        normalization._INCOME_FIELDS,
        (
            "203979266387.09",
            "32864780357.76",
            "32815703838.19",
            "5096680924.6",
            "27719022913.59",
            "29017387604.18",
            "-1298364690.59",
            "2962205439.75",
            "28716608257.66",
            "33999939474.04",
        ),
    )
    balance_values = (
        "124104987289.62",
        "368053902576.37",
        "247407749159.93",
        "120646153416.44",
        "116793716103.39",
        "3852437313.05",
        "368053902576.37",
        "26443476388.52",
        "20605521073.03",
        "39035742535.09",
        None,
        None,
        "767007951.92",
    )
    balance = [
        _row(normalization._BALANCE_FIELDS, balance_values, "0"),
        _row(normalization._BALANCE_FIELDS, balance_values, "1"),
    ]
    cashflow = _row(
        normalization._CASHFLOW_FIELDS,
        (
            "56398426354.17",
            "5425734302.92",
            "4808144624.82",
            None,
            "475186591.56",
            None,
            "30914196186.41",
            "14242168298.2958",
        ),
    )
    return {
        normalization._INCOME_MEMBER: _response(normalization._INCOME_FIELDS, [income]),
        normalization._BALANCE_MEMBER: _response(normalization._BALANCE_FIELDS, balance),
        normalization._CASHFLOW_MEMBER: _response(normalization._CASHFLOW_FIELDS, [cashflow]),
    }


def _rows(source: bytes) -> tuple[tuple[str | None, ...], ...]:
    parsed = json.loads(source, parse_int=str, parse_float=str)
    return tuple(tuple(row) for row in parsed["data"]["items"])


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    sources: dict[str, bytes] | None = None,
    *,
    trust_current_rows: bool = False,
    reverse_members: bool = False,
):
    source_bytes = payloads() if sources is None else sources
    members = [
        RawSourceMember(normalization._INCOME_MEMBER, source_bytes[normalization._INCOME_MEMBER], "0644", 10, None),
        RawSourceMember(normalization._BALANCE_MEMBER, source_bytes[normalization._BALANCE_MEMBER], "0644", 11, None),
        RawSourceMember(normalization._CASHFLOW_MEMBER, source_bytes[normalization._CASHFLOW_MEMBER], "0644", 12, None),
        RawSourceMember(declaration_module._REPORT_MEMBER, REPORT, "0644", 13, None),
        RawSourceMember(declaration_module._CONFIRMATION_MEMBER, CONFIRMATION, "0644", 14, None),
    ]
    outcome = freeze_source_snapshot(
        members=tuple(reversed(members) if reverse_members else members),
        provenance=SourceSnapshotProvenance(
            vendor_key="synthetic.vendor",
            source_key="synthetic.financial",
            license_ref="synthetic.license",
            retention_policy_ref="synthetic.retention",
        ),
    )
    assert outcome.snapshot is not None
    snapshot = outcome.snapshot
    by_key = {member.member_key: member for member in snapshot.members}

    monkeypatch.setattr(declaration_module, "_SNAPSHOT_ID", snapshot.snapshot_id)
    monkeypatch.setattr(declaration_module, "_CONTENT_TREE_HASH", snapshot.content_tree_hash)
    monkeypatch.setattr(declaration_module, "_PROVENANCE_HASH", snapshot.provenance_hash)
    monkeypatch.setattr(declaration_module, "_REVIEWED_AT", UtcInstant(15))
    monkeypatch.setattr(
        declaration_module,
        "_REPORT_HASH",
        by_key[declaration_module._REPORT_MEMBER].content_hash,
    )
    monkeypatch.setattr(
        declaration_module,
        "_CONFIRMATION_HASH",
        by_key[declaration_module._CONFIRMATION_MEMBER].content_hash,
    )
    declared = declaration_module.declare_gree_2023_financial_documents_v1(
        snapshot, reviewed_at=UtcInstant(15)
    )
    assert declared.declaration is not None
    declaration = declared.declaration

    monkeypatch.setattr(normalization, "_SNAPSHOT_ID", snapshot.snapshot_id)
    monkeypatch.setattr(normalization, "_CONTENT_TREE_HASH", snapshot.content_tree_hash)
    monkeypatch.setattr(
        normalization,
        "_AVAILABLE_AT",
        UtcInstant(normalization._EXPECTED_AVAILABLE_AT_NS),
    )
    monkeypatch.setattr(normalization, "_PROVENANCE_HASH", snapshot.provenance_hash)
    monkeypatch.setattr(normalization, "_DECLARATION_HASH", declaration.declaration_hash)
    monkeypatch.setattr(normalization, "_REPORT_HASH", declaration_module._REPORT_HASH)
    monkeypatch.setattr(normalization, "_CONFIRMATION_HASH", declaration_module._CONFIRMATION_HASH)
    monkeypatch.setattr(
        normalization,
        "_MEMBER_HASHES",
        {
            kind.value: by_key[normalization._statement_spec(kind)[0]].content_hash
            for kind in normalization.Gree2023FinancialStatementKind
        },
    )
    expected_sources = source_bytes if trust_current_rows else payloads()
    monkeypatch.setattr(
        normalization,
        "_REAL_ROW_HASHES",
        {
            kind.value: tuple(
                sorted(canonical_sha256(row) for row in _rows(expected_sources[normalization._statement_spec(kind)[0]]))
            )
            for kind in normalization.Gree2023FinancialStatementKind
        },
    )
    baseline_sources = payloads()
    parsed = {
        kind: normalization._parse_statement(
            baseline_sources[normalization._statement_spec(kind)[0]], kind
        )
        for kind in normalization.Gree2023FinancialStatementKind
    }
    resolved = {
        kind: normalization._resolved_line_items(value, declaration)
        for kind, value in parsed.items()
    }
    monkeypatch.setattr(
        normalization,
        "_EXPECTED_LINE_ITEMS",
        {kind.value: value[0] for kind, value in resolved.items()},
    )
    monkeypatch.setattr(
        normalization,
        "_EXPECTED_NULL_FIELDS",
        {kind.value: value[1] for kind, value in resolved.items()},
    )
    monkeypatch.setattr(
        normalization,
        "_EXPECTED_UPDATE_FLAGS",
        {
            kind.value: tuple(flag for _, flag in value[2])
            for kind, value in resolved.items()
        },
    )
    return snapshot, declaration


def _normalize(monkeypatch: pytest.MonkeyPatch, sources: dict[str, bytes] | None = None, **kwargs: object):
    snapshot, declaration = _configure(monkeypatch, sources, **kwargs)
    return normalization.normalize_gree_2023_financial_statements_v1(snapshot, declaration)


def test_synthetic_success_preserves_decimal_tokens_and_pins_independent_golden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome = _normalize(monkeypatch)
    assert outcome.failure is None
    assert outcome.observation_set is not None
    result = outcome.observation_set
    assert result.available_at_utc == UtcInstant(1_714_959_000_000_000_000)
    assert result.ending_interest_bearing_debt == "88533001486.99"
    assert result.ending_depreciation_and_amortization == "5283331216.38"
    assert result.source_bounded is True
    assert result.revision_closure_complete is False
    assert result.decision_grade_eligible is False
    assert result.deployment_authorized is False

    income, balance, cashflow = result.revisions
    assert dict(income.line_items)["income_tax"] == "5096680924.6"
    assert dict(cashflow.line_items)["free_cashflow"] == "14242168298.2958"
    assert balance.raw_null_fields == ("bond_payable", "st_bonds_payable")
    assert dict(balance.line_items)["bond_payable"] == "0.00"
    assert dict(balance.line_items)["st_bonds_payable"] == "0.00"
    assert cashflow.raw_null_fields == ("use_right_asset_dep", "lt_amort_deferred_exp")
    assert dict(cashflow.line_items)["use_right_asset_dep"] is None
    assert result.observation_set_hash == "sha256:abca0d608b1c12a7dbfcf21d86be6c3d347fbf4e8c9cf1a045ef4fd95cf1b9da"
    assert tuple(value.revision_id for value in result.revisions) == (
        "sha256:ee9a349c6cff90b4422dad74a874bc4070b03f5deb9d81afca7746190c1853a0",
        "sha256:2193954aeb3efafa6f5509db62ad837c2596c4766b51ecd32ad705bee56e0fff",
        "sha256:d7518b53e0c4d90079bb65445273829e59d3b10d9498848e02b114d99a95248c",
    )


def test_row_hashes_use_decimal_token_strings_never_binary_float(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome = _normalize(monkeypatch)
    assert outcome.observation_set is not None
    income_row = _rows(payloads()[normalization._INCOME_MEMBER])[0]
    token_hash = canonical_sha256(income_row)
    float_row = [
        float(value) if 6 <= index < len(income_row) - 1 else value
        for index, value in enumerate(income_row)
    ]
    float_hash = "sha256:" + hashlib.sha256(
        json.dumps(float_row, separators=(",", ":")).encode()
    ).hexdigest()
    assert outcome.observation_set.revisions[0].source_row_hashes == (token_hash,)
    assert token_hash != float_hash


@pytest.mark.parametrize("mutation", ["duplicate", "nan", "envelope", "fields", "row_shape", "quoted_numeric"])
def test_invalid_json_envelope_field_and_row_shapes_fail_atomically(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = payloads()
    source = sources[normalization._INCOME_MEMBER]
    if mutation == "duplicate":
        source = source.replace(b'"msg":""', b'"msg":"","msg":""')
    elif mutation == "nan":
        source = source.replace(b"203979266387.09", b"NaN")
    elif mutation == "envelope":
        source = source.replace(b'"detail":"synthetic"', b'"extra":0')
    elif mutation == "fields":
        source = source.replace(b'"revenue"', b'"wrong"', 1)
    elif mutation == "quoted_numeric":
        source = source.replace(b"203979266387.09", b'"203979266387.09"', 1)
    else:
        source = source.replace(b',"1"]],"has_more"', b']],"has_more"')
    sources[normalization._INCOME_MEMBER] = source
    outcome = _normalize(monkeypatch, sources)
    assert outcome.observation_set is None
    assert outcome.failure is not None
    assert outcome.failure.code is normalization.Gree2023FinancialNormalizationFailureCode.SOURCE_RESPONSE_INVALID


@pytest.mark.parametrize("mutation", ["hash", "cardinality"])
def test_row_hash_and_cardinality_mismatch_precede_context(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = payloads()
    parsed = json.loads(sources[normalization._INCOME_MEMBER], parse_int=str, parse_float=str)
    if mutation == "hash":
        parsed["data"]["items"][0][0] = "600519.SH"
    else:
        parsed["data"]["items"].append(parsed["data"]["items"][0])
    sources[normalization._INCOME_MEMBER] = _response(
        normalization._INCOME_FIELDS,
        _numeric_rows(normalization._INCOME_FIELDS, parsed["data"]["items"]),
    )
    outcome = _normalize(monkeypatch, sources)
    assert outcome.failure is not None
    assert outcome.failure.code is normalization.Gree2023FinancialNormalizationFailureCode.SOURCE_ROW_SET_MISMATCH


def test_context_mismatch_is_typed_when_row_set_is_trusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = payloads()
    parsed = json.loads(sources[normalization._INCOME_MEMBER], parse_int=str, parse_float=str)
    parsed["data"]["items"][0][4] = "5"
    sources[normalization._INCOME_MEMBER] = _response(
        normalization._INCOME_FIELDS,
        _numeric_rows(normalization._INCOME_FIELDS, parsed["data"]["items"]),
    )
    outcome = _normalize(monkeypatch, sources, trust_current_rows=True)
    assert outcome.failure is not None
    assert outcome.failure.code is normalization.Gree2023FinancialNormalizationFailureCode.STATEMENT_CONTEXT_MISMATCH


def test_balance_duplicate_collapse_ignores_only_update_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    success = _normalize(monkeypatch)
    assert success.observation_set is not None
    balance = success.observation_set.revisions[1]
    assert balance.provider_update_flags == ("0", "1")
    assert len(balance.source_row_hashes) == 2

    sources = payloads()
    parsed = json.loads(sources[normalization._BALANCE_MEMBER], parse_int=str, parse_float=str)
    parsed["data"]["items"][1][7] = "368053902576.38"
    sources[normalization._BALANCE_MEMBER] = _response(
        normalization._BALANCE_FIELDS,
        _numeric_rows(normalization._BALANCE_FIELDS, parsed["data"]["items"]),
    )
    conflict = _normalize(monkeypatch, sources, trust_current_rows=True)
    assert conflict.failure is not None
    assert conflict.failure.code is normalization.Gree2023FinancialNormalizationFailureCode.BALANCE_PRESENTATION_CONFLICT


def test_required_null_and_declaration_substitution_failures_are_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = payloads()
    parsed = json.loads(sources[normalization._INCOME_MEMBER], parse_int=str, parse_float=str)
    parsed["data"]["items"][0][6] = None
    sources[normalization._INCOME_MEMBER] = _response(
        normalization._INCOME_FIELDS,
        _numeric_rows(normalization._INCOME_FIELDS, parsed["data"]["items"]),
    )
    missing = _normalize(monkeypatch, sources, trust_current_rows=True)
    assert missing.failure is not None
    assert missing.failure.code is normalization.Gree2023FinancialNormalizationFailureCode.REQUIRED_LINE_ITEM_MISSING

    sources = payloads()
    parsed = json.loads(sources[normalization._BALANCE_MEMBER], parse_int=str, parse_float=str)
    parsed["data"]["items"][0][16] = parsed["data"]["items"][1][16] = "1.00"
    sources[normalization._BALANCE_MEMBER] = _response(
        normalization._BALANCE_FIELDS,
        _numeric_rows(normalization._BALANCE_FIELDS, parsed["data"]["items"]),
    )
    substitution = _normalize(monkeypatch, sources, trust_current_rows=True)
    assert substitution.failure is not None
    assert substitution.failure.code is normalization.Gree2023FinancialNormalizationFailureCode.DECLARATION_SUBSTITUTION_MISMATCH

    sources = payloads()
    parsed = json.loads(sources[normalization._CASHFLOW_MEMBER], parse_int=str, parse_float=str)
    parsed["data"]["items"][0][8] = "4808144624.83"
    sources[normalization._CASHFLOW_MEMBER] = _response(
        normalization._CASHFLOW_FIELDS,
        _numeric_rows(normalization._CASHFLOW_FIELDS, parsed["data"]["items"]),
    )
    source_value = _normalize(monkeypatch, sources, trust_current_rows=True)
    assert source_value.failure is not None
    assert source_value.failure.code is normalization.Gree2023FinancialNormalizationFailureCode.DECLARATION_SUBSTITUTION_MISMATCH


def test_source_declaration_availability_and_result_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, declaration = _configure(monkeypatch)
    nested = normalization.normalize_gree_2023_financial_statements_v1(
        replace(snapshot, snapshot_id="sha256:" + "0" * 64), declaration
    )
    assert nested.failure is not None
    assert nested.failure.code is SourceSnapshotFailureCode.SNAPSHOT_ID_MISMATCH

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
    identity = normalization.normalize_gree_2023_financial_statements_v1(other, declaration)
    assert identity.failure is not None
    assert identity.failure.code is normalization.Gree2023FinancialNormalizationFailureCode.SOURCE_IDENTITY_MISMATCH

    object.__setattr__(declaration, "declaration_hash", "sha256:" + "0" * 64)
    declaration_failure = normalization.normalize_gree_2023_financial_statements_v1(snapshot, declaration)
    assert declaration_failure.failure is not None
    assert declaration_failure.failure.code is normalization.Gree2023FinancialNormalizationFailureCode.DECLARATION_MISMATCH

    snapshot, declaration = _configure(monkeypatch)
    monkeypatch.setattr(normalization, "_AVAILABLE_AT", UtcInstant(0))
    availability = normalization.normalize_gree_2023_financial_statements_v1(snapshot, declaration)
    assert availability.failure is not None
    assert availability.failure.code is normalization.Gree2023FinancialNormalizationFailureCode.AVAILABILITY_MISMATCH

    snapshot, declaration = _configure(monkeypatch)

    def broken(*_args: object) -> object:
        raise ValueError("synthetic reconstruction failure")

    monkeypatch.setattr(normalization, "_build_set", broken)
    reconstruction = normalization.normalize_gree_2023_financial_statements_v1(snapshot, declaration)
    assert reconstruction.failure is not None
    assert reconstruction.failure.code is normalization.Gree2023FinancialNormalizationFailureCode.RESULT_RECONSTRUCTION_MISMATCH


def test_input_types_fail_before_inspection() -> None:
    outcome = normalization.normalize_gree_2023_financial_statements_v1(
        object(), object()  # type: ignore[arg-type]
    )
    assert outcome.failure is not None
    assert outcome.failure.code is normalization.Gree2023FinancialNormalizationFailureCode.INPUT_MISMATCH


def test_revision_and_set_constructors_reject_forged_nested_values_and_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome = _normalize(monkeypatch)
    assert outcome.observation_set is not None
    value = outcome.observation_set
    revision = value.revisions[0]

    with pytest.raises(ValueError, match="revision_id"):
        replace(revision, revision_id="sha256:" + "0" * 64)
    with pytest.raises(TypeError, match="exact false"):
        replace(revision, decision_grade_eligible=True, revision_id="")
    with pytest.raises(ValueError, match="line_items_hash"):
        replace(revision, line_items_hash="sha256:" + "0" * 64, revision_id="")

    forged_items = list(revision.line_items)
    forged_items[0] = (forged_items[0][0], "1.00")
    forged_tuple = tuple(forged_items)
    with pytest.raises(ValueError, match="exact value"):
        replace(
            revision,
            line_items=forged_tuple,
            line_items_hash=canonical_sha256(dict(forged_tuple)),
            revision_id="",
        )
    balance = value.revisions[1]
    with pytest.raises(ValueError, match="source row evidence"):
        replace(balance, provider_update_flags=("1", "1"), revision_id="")
    with pytest.raises(ValueError, match="observation_set_hash"):
        replace(value, observation_set_hash="sha256:" + "0" * 64)
    with pytest.raises(TypeError, match="exact false"):
        replace(value, deployment_authorized=True, observation_set_hash="")
    with pytest.raises(ValueError, match="D&A supplement"):
        replace(
            value,
            ending_depreciation_and_amortization="5283331216.380",
            observation_set_hash="",
        )

    object.__setattr__(revision, "revision_id", "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="nested revision"):
        replace(value, observation_set_hash="")
    with pytest.raises(FrozenInstanceError):
        value.observation_set_hash = "forged"  # type: ignore[misc]


def test_source_member_input_order_does_not_change_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _normalize(monkeypatch)
    second = _normalize(monkeypatch, reverse_members=True)
    assert first.to_canonical_dict() == second.to_canonical_dict()


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


def _real_declaration(root: Path) -> declaration_module.Gree2023FinancialDocumentDeclarationsV1:
    value = json.loads((root / "declaration.json").read_bytes())
    publication = value["publication_confirmation"]
    unit = value["statement_unit"]
    debt = value["financing_liability"]
    da = value["depreciation_and_amortization"]
    return declaration_module.Gree2023FinancialDocumentDeclarationsV1(
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


def test_real_snapshot_and_declaration_when_explicitly_configured() -> None:
    snapshot_root = os.environ.get("QB_FIN_REAL_SNAPSHOT_ROOT")
    declaration_root = os.environ.get("QB_FIN_REAL_DECLARATION_ROOT")
    if not snapshot_root or not declaration_root:
        pytest.skip("QB_FIN_REAL_SNAPSHOT_ROOT and QB_FIN_REAL_DECLARATION_ROOT are not configured")
    snapshot = _real_snapshot(Path(snapshot_root))
    declaration = _real_declaration(Path(declaration_root))
    outcome = normalization.normalize_gree_2023_financial_statements_v1(snapshot, declaration)
    assert outcome.failure is None
    assert outcome.observation_set is not None
    result = outcome.observation_set
    assert snapshot.snapshot_id == "sha256:dec0abb1828f8b87256347e72b6ccfe2f84a2ca13f36aa1415c9a53e96a0c7d5"
    assert declaration.declaration_hash == "sha256:59e09eb542a6e2ec480a7b8ed322d9ae9106416460f0999216fd5564f7278007"
    assert tuple(value.source_row_hashes for value in result.revisions) == (
        ("sha256:7650431917f2c6d302075cb08265e2c0993681bff2e964f793d179476792e4a0",),
        (
            "sha256:42558caf71776422ea55d8c54f5cbe20c5a5869c6a72e44b37d7d8662adb37e3",
            "sha256:f891a94138f37fb1dad697354f9278a45e779a2b8c700ffafa0ea34090a00688",
        ),
        ("sha256:7765c5315c9e65a9799af793050520dc2a7f21dd4dc9e410820b0b326ccbeba7",),
    )
    assert tuple(value.revision_id for value in result.revisions) == (
        "sha256:8957590f45f32ed9b285e940f2fa0c0524cb28377e86c745ab39aa3875ba63e8",
        "sha256:3e64ee623ca3676f1ec10daf56588dceabdd77a41ba0419d4c9010241313f45d",
        "sha256:71f4428e79d3bd7638cc9c1d98c1471f9802e9a90d25f7fa06b739bc57f0f986",
    )
    assert result.observation_set_hash == "sha256:632206f85bcff71dbcccfd20a3593e14fb895b33bd138ac25bbf9b947e4a4a7c"
