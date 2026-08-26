from __future__ import annotations

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
import crypto_quant_bundle_builder.gree_historical_financial_statement_normalization_v1 as normalization


class Number(str):
    pass


def _atom(value: object) -> str:
    return str(value) if type(value) is Number else json.dumps(value, ensure_ascii=False)


def _response(fields: tuple[str, ...], rows: list[list[object]], *, reverse: bool = False) -> bytes:
    values = list(reversed(rows)) if reverse else rows
    items = "[" + ",".join("[" + ",".join(_atom(value) for value in row) + "]" for row in values) + "]"
    return (
        "{" + '"request_id":"synthetic-request","code":0,"data":{' +
        f'"fields":{json.dumps(fields, separators=(",", ":"))},"items":{items},' +
        '"has_more":false,"count":0},"msg":"","detail":"synthetic"}'
    ).encode()


def _rows(period: str, kind: normalization.GreeHistoricalFinancialStatementKind) -> list[list[object]]:
    statement = normalization._spec(period, kind)
    values = dict(statement.line_items)
    rows: list[list[object]] = []
    for row_hash, flag in statement.row_evidence:
        raw = dict(values)
        if period == "20221231" and kind is normalization.GreeHistoricalFinancialStatementKind.CASH_FLOW:
            raw["free_cashflow"] = {
                "sha256:336f90eb45f8cc80df7da6968751d7ec503e2bea203557ecfc1a0a841d94914b": "27066951494.8798",
                "sha256:9dc0456482960fa746c74c6e693d5497ecaa01e6a972a2c56f92f98794614438": "30735381659.7498",
            }[row_hash]
        context: dict[str, object] = {
            "ts_code": "000651.SZ",
            "ann_date": normalization._PERIOD_SPECS[period].announcement_date,
            "f_ann_date": normalization._PERIOD_SPECS[period].announcement_date,
            "end_date": period,
            "report_type": "1",
            "comp_type": "1",
            "update_flag": flag,
        }
        context.update({name: None if value is None else Number(value) for name, value in raw.items()})
        rows.append([context[name] for name in statement.fields])
    return rows


def payloads(*, reverse_rows: bool = False) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for period, period_spec in normalization._PERIOD_SPECS.items():
        for kind, statement in period_spec.statements:
            result[statement.member] = _response(statement.fields, _rows(period, kind), reverse=reverse_rows)
    return result


def _parsed_rows(source: bytes) -> tuple[tuple[str | None, ...], ...]:
    value = json.loads(source, parse_int=str, parse_float=str)
    return tuple(tuple(row) for row in value["data"]["items"])


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sources: dict[str, bytes] | None = None,
    trust_current_rows: bool = False,
    trust_current_members: bool = True,
    reverse_members: bool = False,
):
    baseline = payloads()
    source_bytes = baseline if sources is None else sources
    metadata = b'{"synthetic":"metadata"}'
    documents = {
        member: f"%PDF-1.5\n{period}\n".encode()
        for period, member, _content_hash in declarations._DOCUMENT_FACTS
    }
    members = [RawSourceMember(key, value, "0644", 10 + index, None) for index, (key, value) in enumerate({declarations._METADATA_MEMBER: metadata, **documents, **source_bytes}.items())]
    frozen = freeze_source_snapshot(
        members=tuple(reversed(members)) if reverse_members else tuple(members),
        provenance=SourceSnapshotProvenance(
            vendor_key="synthetic.vendor", source_key="synthetic.gree.history",
            license_ref="synthetic.license", retention_policy_ref="synthetic.retention",
        ),
    )
    assert frozen.snapshot is not None
    snapshot = frozen.snapshot
    by_key = {member.member_key: member for member in snapshot.members}

    monkeypatch.setattr(declarations, "_SNAPSHOT_ID", snapshot.snapshot_id)
    monkeypatch.setattr(declarations, "_CONTENT_TREE_HASH", snapshot.content_tree_hash)
    monkeypatch.setattr(declarations, "_PROVENANCE_HASH", snapshot.provenance_hash)
    monkeypatch.setattr(declarations, "_METADATA_HASH", by_key[declarations._METADATA_MEMBER].content_hash)
    monkeypatch.setattr(declarations, "_REVIEWED_AT", UtcInstant(100))
    monkeypatch.setattr(
        declarations,
        "_DOCUMENT_FACTS",
        tuple((period, member, by_key[member].content_hash) for period, member, _ in declarations._DOCUMENT_FACTS),
    )
    outcomes = {
        period: declarations.declare_gree_historical_financial_period_v1(snapshot, period, reviewed_at=UtcInstant(100))
        for period in declarations._SUPPORTED_PERIODS
    }

    monkeypatch.setattr(normalization, "_SNAPSHOT_ID", snapshot.snapshot_id)
    monkeypatch.setattr(normalization, "_CONTENT_TREE_HASH", snapshot.content_tree_hash)
    monkeypatch.setattr(normalization, "_PROVENANCE_HASH", snapshot.provenance_hash)
    monkeypatch.setattr(normalization, "_PUBLICATION_METADATA_HASH", by_key[declarations._METADATA_MEMBER].content_hash)
    monkeypatch.setattr(normalization, "_DECLARATION_FAILURE_HASH", outcomes["20211231"].failure.failure_hash)
    updated_periods = {}
    for period, period_spec in normalization._PERIOD_SPECS.items():
        declaration = outcomes[period].declaration
        assert declaration is not None
        statements = []
        for kind, statement in period_spec.statements:
            expected_source = source_bytes[statement.member] if trust_current_rows else baseline[statement.member]
            expected_rows = tuple(sorted((canonical_sha256(row), row[-1]) for row in _parsed_rows(expected_source)))
            member_hash = by_key[statement.member].content_hash
            if not trust_current_members:
                baseline_frozen = freeze_source_snapshot(
                    members=(RawSourceMember(statement.member, baseline[statement.member], "0644", 1, None),),
                    provenance=SourceSnapshotProvenance(vendor_key="x", source_key="x", license_ref="x", retention_policy_ref="x"),
                ).snapshot
                assert baseline_frozen is not None
                member_hash = baseline_frozen.members[0].content_hash
            statements.append((kind, replace(statement, member_hash=member_hash, row_evidence=expected_rows)))
        document_member = next(member for candidate, member, _ in declarations._DOCUMENT_FACTS if candidate == period)
        updated_periods[period] = replace(
            period_spec,
            declaration_hash=declaration.declaration_hash,
            official_document_hash=by_key[document_member].content_hash,
            statements=tuple(statements),
        )
    monkeypatch.setattr(normalization, "_PERIOD_SPECS", updated_periods)
    failure = normalization._failed(
        normalization.GreeHistoricalFinancialNormalizationFailureCode.DEBT_SCOPE_INCOMPLETE,
        "20211231", outcomes["20211231"].failure,
    )
    assert failure.failure is not None
    monkeypatch.setattr(normalization, "_EXPECTED_NORMALIZATION_FAILURE_HASH", failure.failure.failure_hash)

    revision_ids = {}
    set_hashes = {}
    for period, period_spec in updated_periods.items():
        parsed = tuple(normalization._parse_statement(baseline[statement.member], kind, statement.fields) for kind, statement in period_spec.statements)
        resolved = tuple(normalization._resolve(value, period) for value in parsed)
        assert all(value is not None for value in resolved)
        try:
            observation_set = normalization._build_set(parsed, period, resolved)  # type: ignore[arg-type]
        except ValueError:
            continue
        set_hashes[period] = observation_set.observation_set_hash
        revision_ids.update({(period, value.statement_kind.value): value.revision_id for value in observation_set.revisions})
    monkeypatch.setattr(normalization, "_EXPECTED_REVISION_IDS", revision_ids)
    monkeypatch.setattr(normalization, "_EXPECTED_SET_HASHES", set_hashes)
    return snapshot, outcomes


def test_four_periods_and_2021_conflict_preserve_frozen_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot, declarations_by_period = _configure(monkeypatch)
    results = {
        period: normalization.normalize_gree_historical_financial_period_v1(snapshot, outcome)
        for period, outcome in declarations_by_period.items()
    }
    for period in ("20181231", "20191231", "20201231", "20221231"):
        assert results[period].failure is None
        value = results[period].observation_set
        assert value is not None
        assert value.ending_interest_bearing_debt == normalization._PERIOD_SPECS[period].ending_debt
        assert value.ending_depreciation_and_amortization == normalization._PERIOD_SPECS[period].ending_da
        assert value.availability_source_hashes == normalization._PERIOD_SPECS[period].availability_source_hashes
    only_2018 = results["20181231"].observation_set
    assert only_2018 is not None
    assert tuple(value.statement_kind for value in only_2018.revisions) == (normalization.GreeHistoricalFinancialStatementKind.BALANCE,)
    conflict = results["20211231"]
    assert conflict.observation_set is None
    assert conflict.failure is not None
    assert conflict.failure.code is normalization.GreeHistoricalFinancialNormalizationFailureCode.DEBT_SCOPE_INCOMPLETE
    assert conflict.failure.declaration_failure is not None
    assert conflict.failure.declaration_failure.failure_hash == declarations_by_period["20211231"].failure.failure_hash


def test_frozen_real_identity_constants_are_exact() -> None:
    assert normalization._EXPECTED_SET_HASHES == {
        "20181231": "sha256:20638846aa5eb0c98e30efcae5693114553ef8794a2697783d740ec658d38c68",
        "20191231": "sha256:02bb2571ea9cef06465f0151b747004c34f4baa35b5d59b63e71f65c707fd7d1",
        "20201231": "sha256:2c6110a07d2a7c80745a3cabf35b84b4aeb13f1cd4901d53c24cca619c40f4ce",
        "20221231": "sha256:92d196719be464dc79938db432f442e2d56891effd04adb7e11031f6e31fe736",
    }
    assert normalization._EXPECTED_NORMALIZATION_FAILURE_HASH == "sha256:2cedd67871396e99f324623540ac66f1b254d31020d0e81ba075c6b5876bbc82"
    assert len(normalization._EXPECTED_REVISION_IDS) == 10
    for period, period_spec in normalization._PERIOD_SPECS.items():
        for kind, statement in period_spec.statements:
            generated = tuple(
                sorted(
                    (canonical_sha256(tuple(str(value) if type(value) is Number else value for value in row)), str(row[-1]))
                    for row in _rows(period, kind)
                )
            )
            assert generated == statement.row_evidence


def test_row_order_and_member_order_do_not_change_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    first_snapshot, first_declarations = _configure(monkeypatch)
    first = normalization.normalize_gree_historical_financial_period_v1(first_snapshot, first_declarations["20221231"])
    second_snapshot, second_declarations = _configure(monkeypatch, sources=payloads(reverse_rows=True), reverse_members=True)
    second = normalization.normalize_gree_historical_financial_period_v1(second_snapshot, second_declarations["20221231"])
    assert first.observation_set is not None and second.observation_set is not None
    first_body = first.observation_set.to_canonical_dict()
    second_body = second.observation_set.to_canonical_dict()
    for body in (first_body, second_body):
        body.pop("source_snapshot_id")
        body.pop("declaration_hash")
        body.pop("observation_set_hash")
        for revision in body["revisions"]:
            revision.pop("source_snapshot_id")
            revision.pop("source_content_tree_hash")
            revision.pop("source_provenance_hash")
            revision.pop("source_member_content_hash")
            revision.pop("declaration_hash")
            revision.pop("revision_id")
    assert first_body == second_body


def test_2022_free_cashflow_is_unresolved_immutable_advisory_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot, outcomes = _configure(monkeypatch)
    result = normalization.normalize_gree_historical_financial_period_v1(snapshot, outcomes["20221231"]).observation_set
    assert result is not None
    cashflow = result.revisions[2]
    assert cashflow.source_row_evidence == normalization._spec("20221231", normalization.GreeHistoricalFinancialStatementKind.CASH_FLOW).row_evidence
    assert cashflow.raw_null_fields == ("use_right_asset_dep", "lt_amort_deferred_exp")
    assert cashflow.unresolved_fields == ("free_cashflow",)
    assert dict(cashflow.line_items)["free_cashflow"] is None
    assert cashflow.advisory_conflicts[0].to_canonical_dict() == {
        "field": "free_cashflow",
        "observations": (
            {"source_row_hash": "sha256:336f90eb45f8cc80df7da6968751d7ec503e2bea203557ecfc1a0a841d94914b", "provider_update_flag": "0", "value": "27066951494.8798"},
            {"source_row_hash": "sha256:9dc0456482960fa746c74c6e693d5497ecaa01e6a972a2c56f92f98794614438", "provider_update_flag": "1", "value": "30735381659.7498"},
        ),
    }
    with pytest.raises(FrozenInstanceError):
        cashflow.advisory_conflicts[0].field = "forged"  # type: ignore[misc]


@pytest.mark.parametrize("mutation", ["duplicate", "nan", "envelope", "fields", "row", "quoted"])
def test_response_shape_and_numeric_string_mutations_fail_before_row_identity(mutation: str, monkeypatch: pytest.MonkeyPatch) -> None:
    sources = payloads()
    member = normalization._spec("20191231", normalization.GreeHistoricalFinancialStatementKind.INCOME).member
    source = sources[member]
    if mutation == "duplicate":
        source = source.replace(b'"msg":""', b'"msg":"","msg":""')
    elif mutation == "nan":
        source = source.replace(b"198153027540.35", b"NaN", 1)
    elif mutation == "envelope":
        source = source.replace(b'"detail":"synthetic"', b'"extra":0')
    elif mutation == "fields":
        source = source.replace(b'"revenue"', b'"wrong"', 1)
    elif mutation == "quoted":
        source = source.replace(b"198153027540.35", b'"198153027540.35"', 1)
    else:
        source = source.replace(b',"0"]],"has_more"', b']],"has_more"', 1)
    sources[member] = source
    snapshot, outcomes = _configure(monkeypatch, sources=sources, trust_current_members=True)
    result = normalization.normalize_gree_historical_financial_period_v1(snapshot, outcomes["20191231"])
    assert result.failure is not None
    assert result.failure.code is normalization.GreeHistoricalFinancialNormalizationFailureCode.SOURCE_RESPONSE_INVALID


def test_member_row_cardinality_context_and_presentation_failures_are_ordered(monkeypatch: pytest.MonkeyPatch) -> None:
    period = "20191231"
    member = normalization._spec(period, normalization.GreeHistoricalFinancialStatementKind.BALANCE).member

    sources = payloads()
    parsed = json.loads(sources[member], parse_int=str, parse_float=str)
    parsed["data"]["items"][0][7] = "282972157415.29"
    sources[member] = _response(normalization._BALANCE_FIELDS, [[Number(value) if index >= 6 and index < len(normalization._BALANCE_FIELDS) - 1 and value is not None else value for index, value in enumerate(row)] for row in parsed["data"]["items"]])
    snapshot, outcomes = _configure(monkeypatch, sources=sources, trust_current_rows=True, trust_current_members=False)
    member_mismatch = normalization.normalize_gree_historical_financial_period_v1(snapshot, outcomes[period])
    assert member_mismatch.failure is not None and member_mismatch.failure.code is normalization.GreeHistoricalFinancialNormalizationFailureCode.SOURCE_ROW_SET_MISMATCH

    sources = payloads()
    parsed = json.loads(sources[member], parse_int=str, parse_float=str)
    parsed["data"]["items"].append(parsed["data"]["items"][0])
    sources[member] = _response(normalization._BALANCE_FIELDS, [[Number(value) if index >= 6 and index < len(normalization._BALANCE_FIELDS) - 1 and value is not None else value for index, value in enumerate(row)] for row in parsed["data"]["items"]])
    snapshot, outcomes = _configure(monkeypatch, sources=sources, trust_current_members=True)
    cardinality = normalization.normalize_gree_historical_financial_period_v1(snapshot, outcomes[period])
    assert cardinality.failure is not None and cardinality.failure.code is normalization.GreeHistoricalFinancialNormalizationFailureCode.SOURCE_ROW_SET_MISMATCH

    sources = payloads()
    parsed = json.loads(sources[member], parse_int=str, parse_float=str)
    parsed["data"]["items"][0][4] = "5"
    sources[member] = _response(normalization._BALANCE_FIELDS, [[Number(value) if index >= 6 and index < len(normalization._BALANCE_FIELDS) - 1 and value is not None else value for index, value in enumerate(row)] for row in parsed["data"]["items"]])
    snapshot, outcomes = _configure(monkeypatch, sources=sources, trust_current_rows=True)
    context = normalization.normalize_gree_historical_financial_period_v1(snapshot, outcomes[period])
    assert context.failure is not None and context.failure.code is normalization.GreeHistoricalFinancialNormalizationFailureCode.STATEMENT_CONTEXT_MISMATCH

    sources = payloads()
    parsed = json.loads(sources[member], parse_int=str, parse_float=str)
    parsed["data"]["items"][1][7] = "282972157415.29"
    sources[member] = _response(normalization._BALANCE_FIELDS, [[Number(value) if index >= 6 and index < len(normalization._BALANCE_FIELDS) - 1 and value is not None else value for index, value in enumerate(row)] for row in parsed["data"]["items"]])
    snapshot, outcomes = _configure(monkeypatch, sources=sources, trust_current_rows=True)
    conflict = normalization.normalize_gree_historical_financial_period_v1(snapshot, outcomes[period])
    assert conflict.failure is not None and conflict.failure.code is normalization.GreeHistoricalFinancialNormalizationFailureCode.PRESENTATION_CONFLICT


def test_input_snapshot_declaration_supplement_availability_and_result_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    invalid = normalization.normalize_gree_historical_financial_period_v1(object(), object())  # type: ignore[arg-type]
    assert invalid.failure is not None and invalid.failure.code is normalization.GreeHistoricalFinancialNormalizationFailureCode.INPUT_MISMATCH

    snapshot, outcomes = _configure(monkeypatch)
    object.__setattr__(snapshot.members[0], "acquired_at_epoch_nanoseconds", "bad")
    nested = normalization.normalize_gree_historical_financial_period_v1(snapshot, outcomes["20181231"])
    assert nested.failure is not None and nested.failure.code is normalization.GreeHistoricalFinancialNormalizationFailureCode.INPUT_MISMATCH

    snapshot, outcomes = _configure(monkeypatch)
    real_verify = normalization.verify_source_snapshot
    monkeypatch.setattr(normalization, "verify_source_snapshot", lambda _value: SimpleNamespace(failure=SimpleNamespace(code=SourceSnapshotFailureCode.ARCHIVE_INVALID)))
    verified = normalization.normalize_gree_historical_financial_period_v1(snapshot, outcomes["20191231"])
    assert verified.failure is not None and verified.failure.code is SourceSnapshotFailureCode.ARCHIVE_INVALID and verified.failure.report_period == "20191231"
    monkeypatch.setattr(normalization, "verify_source_snapshot", real_verify)

    snapshot, outcomes = _configure(monkeypatch)
    declaration = outcomes["20191231"].declaration
    assert declaration is not None
    object.__setattr__(declaration, "declaration_hash", "sha256:" + "0" * 64)
    mismatch = normalization.normalize_gree_historical_financial_period_v1(snapshot, outcomes["20191231"])
    assert mismatch.failure is not None and mismatch.failure.code is normalization.GreeHistoricalFinancialNormalizationFailureCode.DECLARATION_MISMATCH

    snapshot, outcomes = _configure(monkeypatch)
    period_spec = normalization._PERIOD_SPECS["20191231"]
    monkeypatch.setattr(normalization, "_PERIOD_SPECS", {**normalization._PERIOD_SPECS, "20191231": replace(period_spec, ending_debt="0.00")})
    supplement = normalization.normalize_gree_historical_financial_period_v1(snapshot, outcomes["20191231"])
    assert supplement.failure is not None and supplement.failure.code is normalization.GreeHistoricalFinancialNormalizationFailureCode.DECLARATION_SUPPLEMENT_MISMATCH
    monkeypatch.setattr(normalization, "_PERIOD_SPECS", {**normalization._PERIOD_SPECS, "20191231": period_spec})

    snapshot, outcomes = _configure(monkeypatch)
    period_spec = normalization._PERIOD_SPECS["20191231"]
    monkeypatch.setattr(normalization, "_PERIOD_SPECS", {**normalization._PERIOD_SPECS, "20191231": replace(period_spec, availability_source_hashes=("sha256:" + "0" * 64,))})
    availability = normalization.normalize_gree_historical_financial_period_v1(snapshot, outcomes["20191231"])
    assert availability.failure is not None and availability.failure.code is normalization.GreeHistoricalFinancialNormalizationFailureCode.AVAILABILITY_MISMATCH
    monkeypatch.setattr(normalization, "_PERIOD_SPECS", {**normalization._PERIOD_SPECS, "20191231": period_spec})

    snapshot, outcomes = _configure(monkeypatch)
    monkeypatch.setattr(normalization, "_EXPECTED_SET_HASHES", {})
    reconstruction = normalization.normalize_gree_historical_financial_period_v1(snapshot, outcomes["20191231"])
    assert reconstruction.failure is not None and reconstruction.failure.code is normalization.GreeHistoricalFinancialNormalizationFailureCode.RESULT_RECONSTRUCTION_MISMATCH


def test_nested_advisory_revision_set_failure_and_outcome_forgery_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot, outcomes = _configure(monkeypatch)
    success = normalization.normalize_gree_historical_financial_period_v1(snapshot, outcomes["20221231"])
    assert success.observation_set is not None
    observation_set = success.observation_set
    revision = observation_set.revisions[2]
    conflict = revision.advisory_conflicts[0]
    observation = conflict.observations[0]
    with pytest.raises(ValueError, match="advisory value"):
        replace(observation, value="quoted")
    original_value = observation.value
    object.__setattr__(observation, "value", "1.0")
    with pytest.raises(ValueError, match="advisory conflict"):
        replace(revision, revision_id="")
    object.__setattr__(observation, "value", original_value)
    with pytest.raises(ValueError, match="revision_id"):
        replace(revision, revision_id="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="observation_set_hash"):
        replace(observation_set, observation_set_hash="sha256:" + "0" * 64)

    foreign_declaration_failure = declarations.GreeHistoricalFinancialDeclarationFailure(
        SourceSnapshotFailureCode.ARCHIVE_INVALID, "20211231", None
    )
    with pytest.raises(ValueError, match="canonical declaration failure"):
        normalization.GreeHistoricalFinancialNormalizationFailure(
            1,
            normalization.GreeHistoricalFinancialNormalizationFailureCode.DEBT_SCOPE_INCOMPLETE,
            "20211231",
            foreign_declaration_failure,
            "",
        )

    failure = normalization.normalize_gree_historical_financial_period_v1(snapshot, outcomes["20211231"]).failure
    assert failure is not None
    object.__setattr__(failure.declaration_failure, "report_period", "20201231")
    with pytest.raises(ValueError, match="outcome failure reconstruction"):
        normalization.GreeHistoricalFinancialNormalizationOutcome(None, failure)


def _real_snapshot(root: Path):
    receipt = json.loads((root / "acquisition-receipt.json").read_bytes())["snapshot"]
    frozen = freeze_source_snapshot(
        members=tuple(RawSourceMember(member["member_key"], (root / member["member_key"]).read_bytes(), member["mode"], member["acquired_at_epoch_nanoseconds"], member["declared_sha256"]) for member in receipt["members"]),
        provenance=SourceSnapshotProvenance(**receipt["provenance"]),
    )
    assert frozen.snapshot is not None
    assert frozen.snapshot.to_canonical_dict() == receipt
    return frozen.snapshot


def test_real_historical_snapshot_when_explicitly_configured() -> None:
    root = os.environ.get("QB_GREE_HISTORICAL_SOURCE_ROOT")
    if not root:
        pytest.skip("QB_GREE_HISTORICAL_SOURCE_ROOT is not configured")
    snapshot = _real_snapshot(Path(root))
    expected_sets = normalization._EXPECTED_SET_HASHES
    for period in ("20181231", "20191231", "20201231", "20221231"):
        declared = declarations.declare_gree_historical_financial_period_v1(snapshot, period, reviewed_at=UtcInstant(1787668131165592196))
        result = normalization.normalize_gree_historical_financial_period_v1(snapshot, declared)
        assert result.failure is None
        assert result.observation_set is not None
        assert result.observation_set.observation_set_hash == expected_sets[period]
        assert tuple(value.revision_id for value in result.observation_set.revisions) == tuple(normalization._EXPECTED_REVISION_IDS[(period, kind.value)] for kind, _ in normalization._PERIOD_SPECS[period].statements)
    declared = declarations.declare_gree_historical_financial_period_v1(snapshot, "20211231", reviewed_at=UtcInstant(1787668131165592196))
    conflict = normalization.normalize_gree_historical_financial_period_v1(snapshot, declared)
    assert conflict.observation_set is None
    assert conflict.failure is not None
    assert conflict.failure.failure_hash == "sha256:2cedd67871396e99f324623540ac66f1b254d31020d0e81ba075c6b5876bbc82"
