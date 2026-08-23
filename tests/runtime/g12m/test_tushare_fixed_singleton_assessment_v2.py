from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest
from crypto_quant_backtest.g12m_tushare_fixed_singleton_assessment_v2 import (
    TushareFixedSingletonAssessmentFailureCodeV2 as Code,
)
from crypto_quant_backtest.g12m_tushare_fixed_singleton_assessment_v2 import (
    TushareFixedSingletonAssessmentOutcomeV2,
    TushareFixedSingletonSourceBoundedAssessmentV2,
    assess_g12m_tushare_fixed_singleton_v2,
)
from crypto_quant_backtest.g12m_tushare_fixed_singleton_route_v2 import (
    _G12MTushareFixedSingletonRouteResultV2,
    run_g12m_tushare_fixed_singleton_route_v2,
)
from crypto_quant_domain import UtcInstant, canonical_bytes

from tests.runtime.g12m.test_tushare_fixed_singleton_route_v2 import (
    _install_exact_test_artifact_mirror,
    _reader,
)
from tests.runtime.test_durable_rebuild_facade import _Store

ROOT = Path(__file__).parents[3]
DECISION = (
    ROOT
    / "evidence/g12m-tushare-fixed-singleton-successor-prerequisite-authority-v2/"
    "decision.json"
)
G12I = (
    ROOT
    / "tests/fixtures/market_data/providers/tushare/"
    "cn-a-share-daily-source-bounded-v2/observation-report.expected.json"
)
G12K = (
    ROOT
    / "tests/fixtures/market_data/providers/tushare/"
    "g12k-fixed-instrument-source-bounded-v1/observation-report.expected.json"
)
IDENTITY = (
    ROOT
    / "tests/fixtures/runtime/g12m-tushare-fixed-singleton-assessment-v2/"
    "identity.expected.json"
)


def _bypass(value: Any, **changes: object) -> Any:
    result = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(
            result,
            field.name,
            changes.get(field.name, getattr(value, field.name)),
        )
    return result


@pytest.fixture(scope="module")
def route_result(tmp_path_factory: pytest.TempPathFactory):
    monkeypatch = pytest.MonkeyPatch()
    _install_exact_test_artifact_mirror(monkeypatch)
    root = tmp_path_factory.mktemp("assessment-route")
    store = _Store()
    result = run_g12m_tushare_fixed_singleton_route_v2(
        market_reader=_reader(root),
        artifact_reader=store,
        artifact_publisher=store,
        publication_root=root / "publication",
    )
    monkeypatch.undo()
    return result


def _assess(
    route: _G12MTushareFixedSingletonRouteResultV2,
    **changes: object,
) -> TushareFixedSingletonAssessmentOutcomeV2:
    values = {
        "successor_decision_bytes": DECISION.read_bytes(),
        "g12i_report_bytes": G12I.read_bytes(),
        "g12k_report_bytes": G12K.read_bytes(),
        "route_result": route,
        "assessed_at": UtcInstant(1787299622295499670),
        "predecessor_assessment": None,
    }
    values.update(changes)
    return assess_g12m_tushare_fixed_singleton_v2(**values)  # type: ignore[arg-type]


def _code(outcome: TushareFixedSingletonAssessmentOutcomeV2) -> Code:
    assert outcome.assessment is None
    assert outcome.failure is not None
    return outcome.failure.code


def test_exact_pure_assessment_and_golden_identity(route_result) -> None:
    outcome = _assess(route_result)
    assert outcome.failure is None
    assessment = outcome.assessment
    assert assessment is not None
    assert type(assessment) is TushareFixedSingletonSourceBoundedAssessmentV2
    assert assessment.requested_grade is (
        route_result.completed_evidence.resolved_request.request.result_grade_requested
    )
    assert assessment.result_grade is route_result.completed_evidence.integrity.result_grade
    assert len(assessment.source_event_triples) == 19
    assert len(assessment.projection_event_triples) == 19
    assert len(assessment.timeline_event_pairs) == 39
    assert assessment.accounting_disposition == (
        "ZERO_EXPOSURE_NO_ENTITLEMENT_NO_CORPORATE_ACTION_DISPATCH"
    )
    assert "corporate_action_lifecycle_not_claimed" in assessment.limitations
    identity = {
        "type": "g12m_tushare_fixed_singleton_assessment_identity_v2",
        "schema_version": 2,
        "assessment_hash": assessment.assessment_hash,
        "route_hash": route_result.route_hash,
        "semantic_run_id": assessment.semantic_run_id,
        "attempt_ids": assessment.attempt_ids,
        "trace_hash": assessment.trace_hash,
        "static_verification_hash": assessment.static_verification_hash,
        "analysis_hash": assessment.analysis_hash,
        "source_event_count": len(assessment.source_event_triples),
        "projection_event_count": len(assessment.projection_event_triples),
        "timeline_event_count": len(assessment.timeline_event_pairs),
        "requested_grade": assessment.requested_grade.value,
        "result_grade": assessment.result_grade.value,
        "accounting_disposition": assessment.accounting_disposition,
    }
    assert json.loads(canonical_bytes(identity)) == json.loads(
        IDENTITY.read_text(encoding="utf-8")
    )
    assert canonical_bytes(assessment) == canonical_bytes(assessment.to_canonical_dict())


def test_bytes_and_source_reconstruction_precedence(route_result) -> None:
    assert _code(_assess(route_result, successor_decision_bytes=bytearray(DECISION.read_bytes()))) is Code.INVALID_EXACT_INPUT_TYPE
    duplicate = DECISION.read_bytes().replace(b"{", b'{"type":"duplicate",', 1)
    assert _code(_assess(route_result, successor_decision_bytes=duplicate)) is Code.MALFORMED_OR_NONCANONICAL_BYTES

    g12i = json.loads(G12I.read_bytes())
    g12i["provider_key"] = "other"
    assert _code(_assess(route_result, g12i_report_bytes=canonical_bytes(g12i) + b"\n")) is Code.G12I_RECONSTRUCTION_MISMATCH

    g12k = json.loads(G12K.read_bytes())
    g12k["provider_key"] = "other"
    assert _code(_assess(route_result, g12k_report_bytes=canonical_bytes(g12k) + b"\n")) is Code.G12K_RECONSTRUCTION_MISMATCH


def test_authority_bundle_target_run_and_grade_precedence(route_result) -> None:
    changed = _bypass(route_result, authority_hash="sha256:" + "0" * 64)
    assert _code(_assess(changed)) is Code.SUCCESSOR_AUTHORITY_MISMATCH

    changed = _bypass(route_result, source_events=route_result.source_events[:-1])
    assert _code(_assess(changed)) is Code.BUNDLE_SOURCE_PROJECTION_MEMBERSHIP_MISMATCH

    changed = _bypass(route_result, target_stream=object())
    assert _code(_assess(changed)) is Code.TARGET_SINGLETON_MISMATCH

    changed = _bypass(route_result, completed_evidence=object())
    assert _code(_assess(changed)) is Code.RUN_ATTEMPT_PROOF_MISMATCH

    rich = route_result.completed_evidence
    changed_rich = _bypass(rich, integrity=object())
    changed = _bypass(route_result, completed_evidence=changed_rich)
    assert _code(_assess(changed)) is Code.RESOLUTION_INTEGRITY_GRADE_MISMATCH


def test_timeline_accounting_time_and_predecessor_precedence(route_result) -> None:
    rich = route_result.completed_evidence
    first_hash = rich.attempt_hashes[0]
    engine = first_hash.engine_result
    removed_timeline = False
    changed_entries = []
    for entry in engine.trace.entries:
        if not removed_timeline and entry.stage.value == "timeline_event":
            removed_timeline = True
            continue
        changed_entries.append(entry)
    changed_engine = _bypass(
        engine,
        trace=_bypass(engine.trace, entries=tuple(changed_entries)),
    )
    changed_hash = _bypass(first_hash, engine_result=changed_engine)
    changed_rich = _bypass(rich, attempt_hashes=(changed_hash, rich.attempt_hashes[1]))
    changed = _bypass(route_result, completed_evidence=changed_rich)
    assert _code(_assess(changed)) is Code.TIMELINE_CAUSALITY_MISMATCH

    changed_engine = _bypass(engine, financial_artifacts=(object(),))
    changed_hash = _bypass(first_hash, engine_result=changed_engine)
    changed_rich = _bypass(rich, attempt_hashes=(changed_hash, rich.attempt_hashes[1]))
    changed = _bypass(route_result, completed_evidence=changed_rich)
    assert _code(_assess(changed)) is Code.ACCOUNTING_DISPOSITION_MISMATCH

    assert _code(_assess(route_result, assessed_at=UtcInstant(1787299622295499669))) is Code.ASSESSMENT_TIME_INVALID
    success = _assess(route_result).assessment
    assert success is not None
    assert _code(_assess(route_result, predecessor_assessment=success)) is Code.DIRECT_PREDECESSOR_INVALID


def test_constructor_bypass_and_subclasses_fail_closed(route_result) -> None:
    class RouteSubclass(_G12MTushareFixedSingletonRouteResultV2):
        pass

    route_values = {field.name: getattr(route_result, field.name) for field in fields(route_result)}
    with pytest.raises(TypeError, match="exact G12M route result"):
        RouteSubclass(**route_values)
    assert _code(_assess(route_result, route_result=object())) is Code.INVALID_EXACT_INPUT_TYPE
    missing_route = object.__new__(type(route_result))
    assert _code(_assess(missing_route)) is Code.SUCCESSOR_AUTHORITY_MISMATCH

    success = _assess(route_result).assessment
    assert success is not None
    bypassed = _bypass(success, assessment_hash="sha256:" + "0" * 64)
    assert _code(_assess(route_result, predecessor_assessment=bypassed)) is Code.DIRECT_PREDECESSOR_INVALID
    missing_assessment = object.__new__(
        TushareFixedSingletonSourceBoundedAssessmentV2
    )
    assert _code(
        _assess(route_result, predecessor_assessment=missing_assessment)
    ) is Code.DIRECT_PREDECESSOR_INVALID

    class AssessmentSubclass(TushareFixedSingletonSourceBoundedAssessmentV2):
        pass

    values = {field.name: getattr(success, field.name) for field in fields(success)}
    with pytest.raises(TypeError, match="exact source-bounded assessment"):
        AssessmentSubclass(**values)
