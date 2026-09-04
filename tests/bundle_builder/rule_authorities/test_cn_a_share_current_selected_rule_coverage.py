from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest
from crypto_quant_bundle_builder.cn_a_share_current_selected_rule_coverage import (
    CnAShareCurrentSelectedRuleCoverageFailure,
    CnAShareCurrentSelectedRuleCoverageReport,
    analyze_cn_a_share_current_selected_rule_coverage_v1,
)
from crypto_quant_domain import canonical_sha256

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = (
    ROOT / "fixtures/market_data/rule_authorities/"
    "cn-a-share-current-selected-development-v2"
)
DECLARATION = json.loads((FIXTURE_DIR / "declaration.json").read_text())
EXPECTED = json.loads((FIXTURE_DIR / "coverage.expected.json").read_text())
DIMENSIONS = (
    "calendar",
    "order_rules",
    "market_fees",
    "stamp_duty",
    "corporate_action_entitlements",
)
START = 1_783_267_200_000_000_000
END = 1_785_427_200_000_000_000


def _analyze(value: object):
    return analyze_cn_a_share_current_selected_rule_coverage_v1(value)  # type: ignore[arg-type]


def _failure(value: object) -> CnAShareCurrentSelectedRuleCoverageFailure:
    result = _analyze(value)
    assert type(result) is CnAShareCurrentSelectedRuleCoverageFailure
    return result


def _rehash(value: dict[str, object], dimension: str) -> None:
    entry = value["authorities"][dimension]
    body = entry["body"]
    entry["canonical_body_hash"] = canonical_sha256(body)
    if dimension == "calendar":
        entry["authority_hash"] = canonical_sha256(
            {
                "type": "cn_a_share_frozen_calendar",
                "schema_version": 1,
                "venue_id": body["venue_id"],
                "calendar_id": body["calendar_id"],
                "timezone_name": body["timezone_name"],
                "coverage_start": body["coverage_start"],
                "coverage_end_exclusive": body["coverage_end_exclusive"],
                "canonical_sorted_days": sorted(
                    body["days"], key=lambda item: item["local_date"]
                ),
            }
        )
    else:
        entry["authority_hash"] = entry["canonical_body_hash"]


def _set_end(value: dict[str, object], dimension: str, end: object) -> None:
    body = value["authorities"][dimension]["body"]
    if dimension == "calendar":
        body["coverage_end_exclusive"] = end
    elif dimension == "order_rules":
        body["bands"][0]["effective_to_exclusive"] = end
    elif dimension in {"market_fees", "stamp_duty"}:
        body["bands"][0]["effective_to_exclusive"]["epoch_nanoseconds"] = end
    else:
        body["bands"][0]["effective_end"]["epoch_nanoseconds"] = end
    _rehash(value, dimension)


def _duplicate_band(value: dict[str, object], dimension: str) -> None:
    body = value["authorities"][dimension]["body"]
    if dimension == "calendar":
        pytest.fail("calendar has one body-level interval")
    body["bands"].append(deepcopy(body["bands"][0]))
    _rehash(value, dimension)


def _reverse_objects(value: object) -> object:
    if type(value) is dict:
        return {
            key: _reverse_objects(item) for key, item in reversed(tuple(value.items()))
        }
    if type(value) is list:
        return [_reverse_objects(item) for item in value]
    return value


def test_complete_finite_development_coverage_matches_exact_golden_report() -> None:
    result = _analyze(DECLARATION)
    assert type(result) is CnAShareCurrentSelectedRuleCoverageReport
    assert result.to_canonical_dict() == EXPECTED
    assert (
        result.report_hash
        == EXPECTED["report_hash"]
        == ("sha256:5cbcc37871999b334709d1823f1c40ce6cdf73480f410f821cf4ebd38ceec9bb")
    )
    assert result.declaration_hash == (
        "sha256:4b21421bbe112d47a63ff03578dcb2215946e394d9971ab39a65c381d3d697d1"
    )
    assert result.snapshot_hash == (
        "sha256:747e5c88fd2810ca05841cc6bb3c9534fbfc203ccad3e0903dd3f14e25a8a5c8"
    )
    assert [value[0] for value in result.dimension_interval_evidence] == list(
        DIMENSIONS
    )
    assert all(
        value[3] == ((START, END),) for value in result.dimension_interval_evidence
    )
    assert EXPECTED["coverage_semantics"] == "finite_development_interval"
    assert EXPECTED["finite_development_interval_coverage_complete"] is True
    assert "legal" not in json.dumps(EXPECTED)
    assert "history" not in json.dumps(EXPECTED)
    assert EXPECTED["qualification"] == DECLARATION["qualification"]
    assert EXPECTED["qualification"]["rule_coverage_qualified"] is False
    for claim in (
        "official_successor_closure_complete",
        "provider_authority_qualified",
        "provider_completeness_qualified",
        "decision_grade_eligible",
        "live_eligible",
        "deployment_authorized",
    ):
        assert EXPECTED["qualification"][claim] is False


def test_canonical_json_object_order_does_not_change_result() -> None:
    reordered = _reverse_objects(DECLARATION)
    assert reordered == DECLARATION and list(reordered) != list(DECLARATION)
    result = _analyze(reordered)
    assert type(result) is CnAShareCurrentSelectedRuleCoverageReport
    assert result.to_canonical_dict() == EXPECTED


def test_rehashed_empty_calendar_cannot_return_a_report() -> None:
    forged = deepcopy(DECLARATION)
    forged["authorities"]["calendar"]["body"]["days"] = []
    _rehash(forged, "calendar")

    failure = _failure(forged)
    assert (failure.code.value, failure.dimension) == (
        "bundle_declaration_mismatch",
        None,
    )

@pytest.mark.parametrize("dimension", DIMENSIONS)
def test_each_required_dimension_reports_actual_coverage_gap(dimension: str) -> None:
    forged = deepcopy(DECLARATION)
    local_end: object = (
        "2026-07-30" if dimension in {"calendar", "order_rules"} else END - 1
    )
    _set_end(forged, dimension, local_end)
    failure = _failure(forged)
    assert (failure.code.value, failure.dimension) == ("coverage_gap", dimension)


@pytest.mark.parametrize("dimension", DIMENSIONS[1:])
def test_each_banded_dimension_reports_actual_coverage_overlap(dimension: str) -> None:
    forged = deepcopy(DECLARATION)
    _duplicate_band(forged, dimension)
    failure = _failure(forged)
    assert (failure.code.value, failure.dimension) == ("coverage_overlap", dimension)


def test_missing_dimension_and_source_identity_fail_atomically() -> None:
    missing = deepcopy(DECLARATION)
    missing["authorities"].pop("market_fees")
    failure = _failure(missing)
    assert (failure.code.value, failure.dimension) == (
        "missing_required_dimension",
        "market_fees",
    )

    source = deepcopy(DECLARATION)
    source["authorities"]["calendar"]["canonical_body_hash"] = "sha256:" + "0" * 64
    failure = _failure(source)
    assert (failure.code.value, failure.dimension) == (
        "source_identity_mismatch",
        "calendar",
    )
    assert failure.to_canonical_dict() == {
        "type": "cn_a_share_current_selected_rule_coverage_failure",
        "schema_version": 1,
        "code": "source_identity_mismatch",
        "dimension": "calendar",
    }
    assert failure.failure_hash == (
        "sha256:6404741066c38be533e1cc4ed5e85a643795bc811f06b08a0e3a0314b20fb2e3"
    )


@pytest.mark.parametrize(
    "mutate",
    (
        lambda value: value["qualification"].update({"rule_coverage_qualified": True}),
        lambda value: value["snapshot"].update({"target_from": START + 1}),
        lambda value: value.update({"snapshot_hash": "sha256:" + "0" * 64}),
        lambda value: value["snapshot"].update({"official_record_as_of": START}),
        lambda value: value.update({"extra": None}),
    ),
)
def test_declaration_snapshot_qualification_and_official_record_drift_fail(
    mutate,
) -> None:
    forged = deepcopy(DECLARATION)
    mutate(forged)
    failure = _failure(forged)
    assert (failure.code.value, failure.dimension) == (
        "bundle_declaration_mismatch",
        None,
    )


def test_failure_precedence_and_dimension_ties_are_frozen() -> None:
    invalid = deepcopy(DECLARATION)
    invalid["snapshot"]["bad"] = (1, 2)
    invalid["qualification"]["rule_coverage_qualified"] = True
    assert _failure(invalid).code.value == "invalid_input"

    bundle_before_missing = deepcopy(DECLARATION)
    bundle_before_missing["qualification"]["rule_coverage_qualified"] = True
    bundle_before_missing["authorities"].pop("calendar")
    failure = _failure(bundle_before_missing)
    assert (failure.code.value, failure.dimension) == (
        "bundle_declaration_mismatch",
        None,
    )

    missing_before_gap = deepcopy(DECLARATION)
    missing_before_gap["authorities"].pop("calendar")
    _set_end(missing_before_gap, "order_rules", "2026-07-30")
    failure = _failure(missing_before_gap)
    assert (failure.code.value, failure.dimension) == (
        "missing_required_dimension",
        "calendar",
    )

    gap_before_overlap = deepcopy(DECLARATION)
    _set_end(gap_before_overlap, "order_rules", "2026-07-30")
    _duplicate_band(gap_before_overlap, "market_fees")
    failure = _failure(gap_before_overlap)
    assert (failure.code.value, failure.dimension) == ("coverage_gap", "order_rules")

    gap_tie = deepcopy(DECLARATION)
    _set_end(gap_tie, "calendar", "2026-07-30")
    _set_end(gap_tie, "order_rules", "2026-07-30")
    failure = _failure(gap_tie)
    assert (failure.code.value, failure.dimension) == ("coverage_gap", "calendar")

    source_tie = deepcopy(DECLARATION)
    for dimension in ("calendar", "order_rules"):
        source_tie["authorities"][dimension]["authority_hash"] = "sha256:" + "0" * 64
    failure = _failure(source_tie)
    assert (failure.code.value, failure.dimension) == (
        "source_identity_mismatch",
        "calendar",
    )


def test_exact_input_and_immutable_concrete_result_types_fail_closed() -> None:
    class Declaration(dict):
        pass

    assert _failure(Declaration(DECLARATION)).code.value == "invalid_input"
    nested_subclass = deepcopy(DECLARATION)
    nested_subclass["qualification"] = Declaration(nested_subclass["qualification"])
    assert _failure(nested_subclass).code.value == "invalid_input"
    assert _failure(object()).code.value == "invalid_input"

    report = _analyze(DECLARATION)
    assert type(report) is CnAShareCurrentSelectedRuleCoverageReport
    with pytest.raises(FrozenInstanceError):
        report.target_from = 0
    detached = report.to_canonical_dict()
    detached["target_scope"]["board_ids"].append("forged")
    assert report.to_canonical_dict() == EXPECTED

    class ReportSubclass(CnAShareCurrentSelectedRuleCoverageReport):
        pass

    with pytest.raises(TypeError, match="exact concrete type"):
        ReportSubclass(
            report.declaration_hash,
            report.snapshot_hash,
            report.snapshot_key,
            report.snapshot_version,
            report.target_from,
            report.target_to_exclusive,
            report.board_ids,
            report.dimension_interval_evidence,
            report.qualification,
        )
    forged_evidence = tuple(
        (
            dimension,
            "sha256:" + "0" * 64,
            body_hash,
            intervals,
        )
        if dimension == "calendar"
        else (dimension, authority_hash, body_hash, intervals)
        for dimension, authority_hash, body_hash, intervals in (
            report.dimension_interval_evidence
        )
    )
    with pytest.raises(ValueError):
        CnAShareCurrentSelectedRuleCoverageReport(
            report.declaration_hash,
            report.snapshot_hash,
            report.snapshot_key,
            report.snapshot_version,
            report.target_from,
            report.target_to_exclusive,
            report.board_ids,
            forged_evidence,
            report.qualification,
        )
    forged = object.__new__(CnAShareCurrentSelectedRuleCoverageReport)
    with pytest.raises((AttributeError, TypeError, ValueError)):
        forged.to_canonical_dict()
    with pytest.raises(TypeError, match="exact failure code"):
        CnAShareCurrentSelectedRuleCoverageFailure("coverage_gap", "calendar")


def test_v1_blocker_and_frozen_declaration_remain_immutable() -> None:
    blocker = (
        ROOT / "bundle_builder/rule_authorities/test_g12h_rule_coverage_blocker.py"
    )
    assert "sha256:" + sha256(blocker.read_bytes()).hexdigest() == (
        "sha256:1a2a8f8a7347604ec7223d2eddadefdcb338cd62df4623315969bf6b9e710fa6"
    )
    v1_path = (
        ROOT / "fixtures/market_data/rule_authorities/"
        "cn-a-share-development-v1/declaration.json"
    )
    assert "sha256:" + sha256(v1_path.read_bytes()).hexdigest() == (
        "sha256:19017a07fbfd2da954483648fb168d87212f88e92fccca7c28fb0a514b202515"
    )
    v1 = json.loads(v1_path.read_text())
    failure = _failure(v1)
    assert (failure.code.value, failure.dimension) == (
        "bundle_declaration_mismatch",
        None,
    )
