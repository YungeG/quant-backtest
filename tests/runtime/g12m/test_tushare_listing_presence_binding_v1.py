from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

from crypto_quant_backtest.g12m_tushare_fixed_singleton_assessment_v2 import (
    assess_g12m_tushare_fixed_singleton_v2,
)
from crypto_quant_backtest.g12m_tushare_fixed_singleton_route_v2 import (
    run_g12m_tushare_fixed_singleton_route_v2,
)
from crypto_quant_backtest.g12m_tushare_listing_presence_binding_v1 import (
    G12MTushareListingPresenceBindingFailureCodeV1 as Code,
)
from crypto_quant_backtest.g12m_tushare_listing_presence_binding_v1 import (
    G12MTushareListingPresenceBindingOutcomeV1,
    G12MTushareListingPresenceBindingV1,
    bind_g12m_tushare_listing_presence_v1,
)
from crypto_quant_domain import UtcInstant, canonical_bytes, canonical_sha256

from tests.runtime.g12m.test_tushare_fixed_singleton_assessment_v2 import (
    DECISION,
    G12I,
    G12K,
)
from tests.runtime.g12m.test_tushare_fixed_singleton_route_v2 import (
    _install_exact_test_artifact_mirror,
    _reader,
)
from tests.runtime.test_durable_rebuild_facade import _Store

ROOT = Path(__file__).parents[3]
LISTING = (
    ROOT
    / "tests/fixtures/market_data/providers/tushare/"
    "g12l-listing-source-bounded-v2/observation-report.expected.json"
)
IDENTITY = (
    ROOT
    / "tests/fixtures/runtime/g12m-tushare-listing-presence-binding-v1/"
    "identity.expected.json"
)
BOUND_AT = UtcInstant(1787533249650679470)


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
def base_assessment(tmp_path_factory: pytest.TempPathFactory):
    monkeypatch = pytest.MonkeyPatch()
    _install_exact_test_artifact_mirror(monkeypatch)
    root = tmp_path_factory.mktemp("listing-binding-route")
    store = _Store()
    route = run_g12m_tushare_fixed_singleton_route_v2(
        market_reader=_reader(root),
        artifact_reader=store,
        artifact_publisher=store,
        publication_root=root / "publication",
    )
    monkeypatch.undo()
    route_result = route
    outcome = assess_g12m_tushare_fixed_singleton_v2(
        successor_decision_bytes=DECISION.read_bytes(),
        g12i_report_bytes=G12I.read_bytes(),
        g12k_report_bytes=G12K.read_bytes(),
        route_result=route_result,
        assessed_at=UtcInstant(1787299622295499670),
        predecessor_assessment=None,
    )
    assert outcome.failure is None and outcome.assessment is not None
    return outcome.assessment


def _bind(base, **changes: object):
    values = {
        "base_assessment": base,
        "listing_report_bytes": LISTING.read_bytes(),
        "bound_at": BOUND_AT,
        "predecessor_binding": None,
    }
    values.update(changes)
    return bind_g12m_tushare_listing_presence_v1(**values)  # type: ignore[arg-type]


def _code(outcome: G12MTushareListingPresenceBindingOutcomeV1) -> Code:
    assert outcome.binding is None and outcome.failure is not None
    return outcome.failure.code


def test_exact_post_assessment_binding_and_golden_identity(base_assessment) -> None:
    outcome = _bind(base_assessment)
    assert outcome.failure is None and outcome.binding is not None
    binding = outcome.binding
    assert type(binding) is G12MTushareListingPresenceBindingV1
    assert binding.base_assessment_hash == base_assessment.assessment_hash
    assert binding.semantic_run_id == base_assessment.semantic_run_id
    assert binding.base_requested_grade is base_assessment.requested_grade
    assert binding.base_result_grade is base_assessment.result_grade
    assert binding.trade_date == "20240102"
    assert binding.current_name == "平安银行"
    assert binding.list_date == "19910403"
    assert binding.target_name_interval_start == "20120802"
    assert binding.target_name_interval_end is None
    assert binding.listing_observed_at == BOUND_AT
    assert "post_assessment_observation_not_causal_run_input" in binding.limitations
    assert "listing_continuity_to_july_2026_execution_window_unavailable" in binding.limitations
    assert "grade_upgrade_not_claimed" in binding.nonclaims
    assert binding.live_eligible is False
    assert binding.deployment_authorized is False

    identity = {
        "type": "g12m_tushare_listing_presence_binding_identity_v1",
        "schema_version": 1,
        "binding_hash": binding.binding_hash,
        "base_assessment_hash": binding.base_assessment_hash,
        "semantic_run_id": binding.semantic_run_id,
        "listing_report_file_hash": binding.listing_report_file_hash,
        "listing_report_hash": binding.listing_report_hash,
        "listing_snapshot_id": binding.listing_snapshot_id,
        "listing_request_scope_hash": binding.listing_request_scope_hash,
        "instrument_catalog_hash": binding.instrument_catalog_hash,
        "trade_date": binding.trade_date,
        "current_name": binding.current_name,
        "list_date": binding.list_date,
        "target_name_interval_start": binding.target_name_interval_start,
        "target_name_interval_end": binding.target_name_interval_end,
        "listing_observed_at": binding.listing_observed_at,
        "bound_at": binding.bound_at,
        "base_requested_grade": binding.base_requested_grade.value,
        "base_result_grade": binding.base_result_grade.value,
        "live_eligible": binding.live_eligible,
        "deployment_authorized": binding.deployment_authorized,
    }
    assert json.loads(canonical_bytes(identity)) == json.loads(
        IDENTITY.read_text(encoding="utf-8")
    )
    assert canonical_bytes(binding) == canonical_bytes(binding.to_canonical_dict())


def test_failure_precedence_is_exact(base_assessment) -> None:
    assert _code(_bind(base_assessment, base_assessment=object())) is Code.INVALID_EXACT_INPUT_TYPE

    forged = _bypass(base_assessment, assessment_hash="sha256:" + "0" * 64)
    assert _code(_bind(base_assessment, base_assessment=forged)) is Code.BASE_ASSESSMENT_MISMATCH

    duplicate = LISTING.read_bytes().replace(b'{"absence_authority"', b'{"type":0,"absence_authority"', 1)
    assert _code(_bind(base_assessment, listing_report_bytes=duplicate)) is Code.MALFORMED_OR_NONCANONICAL_LISTING_REPORT
    assert _code(_bind(base_assessment, listing_report_bytes=LISTING.read_bytes() + b"\n")) is Code.MALFORMED_OR_NONCANONICAL_LISTING_REPORT

    report = json.loads(LISTING.read_bytes())
    report["trade_date"] = "20240103"
    body = dict(report)
    body.pop("report_hash")
    report["report_hash"] = canonical_sha256(body)
    assert _code(_bind(base_assessment, listing_report_bytes=canonical_bytes(report))) is Code.LISTING_REPORT_IDENTITY_MISMATCH

    assert _code(_bind(base_assessment, bound_at=UtcInstant(1787533249650679469))) is Code.BINDING_TIME_INVALID
    malformed_time = object.__new__(UtcInstant)
    assert _code(_bind(base_assessment, bound_at=malformed_time)) is Code.BINDING_TIME_INVALID

    success = _bind(base_assessment).binding
    assert success is not None
    assert _code(_bind(base_assessment, predecessor_binding=success)) is Code.DIRECT_PREDECESSOR_INVALID
    malformed_predecessor = object.__new__(G12MTushareListingPresenceBindingV1)
    assert _code(_bind(base_assessment, predecessor_binding=malformed_predecessor)) is Code.DIRECT_PREDECESSOR_INVALID


def test_constructor_bypass_and_subclasses_fail_closed(base_assessment) -> None:
    success = _bind(base_assessment).binding
    assert success is not None
    forged = _bypass(success, binding_hash="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="binding_hash does not bind body"):
        G12MTushareListingPresenceBindingOutcomeV1(forged, None)

    class BindingSubclass(G12MTushareListingPresenceBindingV1):
        pass

    values = {field.name: getattr(success, field.name) for field in fields(success)}
    with pytest.raises(TypeError, match="exact listing presence binding v1"):
        BindingSubclass(**values)
    assert _code(_bind(base_assessment, predecessor_binding=forged)) is Code.DIRECT_PREDECESSOR_INVALID


def test_listing_fixture_is_unchanged_and_secret_free() -> None:
    source = LISTING.read_bytes().lower()
    assert b'"token"' not in source
    assert b'"authorization"' not in source
    assert b"tushare_proxy_token" not in source
