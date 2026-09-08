from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

from crypto_quant_backtest.g12m_tushare_july_listing_presence_binding_v2 import (
    G12MTushareJulyListingPresenceBindingFailureCodeV2 as Code,
)
from crypto_quant_backtest.g12m_tushare_july_listing_presence_binding_v2 import (
    G12MTushareJulyListingPresenceBindingOutcomeV2,
    G12MTushareJulyListingPresenceBindingV2,
    bind_g12m_tushare_july_listing_presence_v2,
)
from crypto_quant_domain import UtcInstant, canonical_bytes, canonical_sha256

from tests.runtime.g12m.test_tushare_listing_presence_binding_v1 import (
    _bind as _bind_v1,
    base_assessment,
)

ROOT = Path(__file__).parents[3]
JULY = ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/observation-report.expected.json"
IDENTITY = ROOT / "tests/fixtures/runtime/g12m-tushare-july-listing-presence-binding-v2/identity.expected.json"
BOUND_AT = UtcInstant(1787543480633962555)


def _bypass(value: Any, **changes: object) -> Any:
    result = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(result, field.name, changes.get(field.name, getattr(value, field.name)))
    return result


@pytest.fixture(scope="module")
def predecessor_binding(base_assessment):
    binding = _bind_v1(base_assessment).binding
    assert binding is not None
    return binding


def _bind(predecessor, **changes: object):
    values = {"predecessor_binding": predecessor, "july_report_bytes": JULY.read_bytes(), "bound_at": BOUND_AT}
    values.update(changes)
    return bind_g12m_tushare_july_listing_presence_v2(**values)  # type: ignore[arg-type]


def _code(outcome: G12MTushareJulyListingPresenceBindingOutcomeV2) -> Code:
    assert outcome.binding is None and outcome.failure is not None
    return outcome.failure.code


def test_exact_direct_successor_binding_and_golden(predecessor_binding) -> None:
    outcome = _bind(predecessor_binding)
    assert outcome.failure is None and outcome.binding is not None
    binding = outcome.binding
    assert binding.supersedes_binding_hash == predecessor_binding.binding_hash
    assert binding.base_assessment_hash == predecessor_binding.base_assessment_hash
    assert binding.semantic_run_id == predecessor_binding.semantic_run_id
    assert binding.base_requested_grade is predecessor_binding.base_requested_grade
    assert binding.base_result_grade is predecessor_binding.base_result_grade
    assert len(binding.trade_dates) == 19
    assert len(binding.source_record_hashes) == 19
    assert binding.july_observed_at == BOUND_AT
    assert "post_assessment_observation_not_causal_run_input" in binding.limitations
    assert binding.live_eligible is False and binding.deployment_authorized is False
    identity = {
        "type": "g12m_tushare_july_listing_presence_binding_identity_v2",
        "schema_version": 2,
        "binding_hash": binding.binding_hash,
        "supersedes_binding_hash": binding.supersedes_binding_hash,
        "base_assessment_hash": binding.base_assessment_hash,
        "semantic_run_id": binding.semantic_run_id,
        "july_report_file_hash": binding.july_report_file_hash,
        "july_report_hash": binding.july_report_hash,
        "july_snapshot_id": binding.july_snapshot_id,
        "july_request_scope_hash": binding.july_request_scope_hash,
        "trade_dates": binding.trade_dates,
        "july_observed_at": binding.july_observed_at,
        "bound_at": binding.bound_at,
        "base_requested_grade": binding.base_requested_grade.value,
        "base_result_grade": binding.base_result_grade.value,
        "live_eligible": binding.live_eligible,
        "deployment_authorized": binding.deployment_authorized,
    }
    assert json.loads(canonical_bytes(identity)) == json.loads(IDENTITY.read_text(encoding="utf-8"))
    assert canonical_bytes(binding) == canonical_bytes(binding.to_canonical_dict())


def test_failure_precedence_and_constructor_bypass(predecessor_binding) -> None:
    assert _code(_bind(predecessor_binding, predecessor_binding=object())) is Code.INVALID_EXACT_INPUT_TYPE
    forged_predecessor = _bypass(predecessor_binding, binding_hash="sha256:" + "0" * 64)
    assert _code(_bind(predecessor_binding, predecessor_binding=forged_predecessor)) is Code.PREDECESSOR_BINDING_MISMATCH
    assert _code(_bind(predecessor_binding, july_report_bytes=JULY.read_bytes() + b"\n")) is Code.MALFORMED_OR_NONCANONICAL_JULY_REPORT

    report = json.loads(JULY.read_bytes())
    report["trade_dates"][0] = "20260705"
    body = dict(report); body.pop("report_hash")
    report["report_hash"] = canonical_sha256(body)
    assert _code(_bind(predecessor_binding, july_report_bytes=canonical_bytes(report))) is Code.JULY_REPORT_IDENTITY_MISMATCH
    assert _code(_bind(predecessor_binding, bound_at=UtcInstant(1787543480633962554))) is Code.BINDING_TIME_INVALID
    assert _code(_bind(predecessor_binding, bound_at=object.__new__(UtcInstant))) is Code.BINDING_TIME_INVALID

    success = _bind(predecessor_binding).binding
    assert success is not None
    forged = _bypass(success, source_record_hashes=("sha256:" + "0" * 64,) * 19)
    object.__setattr__(forged, "binding_hash", canonical_sha256(forged._body()))
    with pytest.raises(ValueError, match="grades, rows, time, or nonclaims mismatch"):
        forged.__post_init__()
    with pytest.raises(ValueError):
        G12MTushareJulyListingPresenceBindingOutcomeV2(forged, None)

    class BindingSubclass(G12MTushareJulyListingPresenceBindingV2):
        pass

    values = {field.name: getattr(success, field.name) for field in fields(success)}
    with pytest.raises(TypeError, match="exact July listing binding v2"):
        BindingSubclass(**values)
