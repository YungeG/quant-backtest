from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crypto_quant_backtest import (
    ConservativeLinearLiquidationAuditModel,
    RequestedResultGrade,
)

from tests.runtime.liquidation.test_conservative_linear_liquidation_audit import (
    _mixed_long_short_request,
    _request,
)


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/runtime/liquidation/conservative-linear-liquidation-audit-v1.json"
)


def _case(request=None, **kwargs: Any) -> dict[str, Any]:
    request = _request(**kwargs) if request is None else request
    outcome = ConservativeLinearLiquidationAuditModel().audit_liquidation(request)
    if outcome.failure is not None:
        return {
            "request_hash": request.request_hash,
            "failure_code": outcome.failure.code.value,
            "failure_hash": outcome.failure.failure_hash,
            "subject_ids": list(outcome.failure.subject_ids),
        }
    assert outcome.result is not None
    result = outcome.result
    return {
        "request_hash": request.request_hash,
        "classification": result.classification.value,
        "decision_grade_eligible": result.decision_grade_eligible,
        "position_audits": [
            {
                "direction": value.direction,
                "adverse_price_units": value.adverse_price.units,
                "tier_id": value.resolved_tier.tier_id,
                "exact_unrealized": [
                    value.exact_adverse_unrealized.numerator,
                    value.exact_adverse_unrealized.denominator,
                ],
                "unrealized_units": value.adverse_unrealized.units,
                "exact_maintenance": [
                    value.exact_adverse_maintenance.numerator,
                    value.exact_adverse_maintenance.denominator,
                ],
                "maintenance_units": value.adverse_maintenance.units,
                "audit_hash": value.audit_hash,
            }
            for value in result.position_audits
        ],
        "wallet_units": result.wallet_balance.units,
        "adverse_unrealized_units": result.adverse_unrealized.units,
        "adverse_equity_units": result.adverse_equity.units,
        "adverse_maintenance_units": result.adverse_maintenance.units,
        "limitation": result.limitation,
        "result_hash": result.result_hash,
    }


def build_actual() -> dict[str, Any]:
    model = ConservativeLinearLiquidationAuditModel()
    return {
        "fixture_id": "synthetic-conservative-linear-liquidation-audit-v1",
        "schema_version": 1,
        "component_ref": model.component_ref.to_canonical_dict(),
        "cases": {
            "long_safe": _case(),
            "short_cross_tier_safe": _case(
                quantity_units=-1_000, high_units=50_000
            ),
            "mixed_long_short_safe": _case(_mixed_long_short_request()),
            "equality_safe": _case(wallet_units=135),
            "development_ambiguous": _case(wallet_units=100, low_units=100),
            "decision_grade_ambiguous": _case(
                wallet_units=100,
                low_units=100,
                requested_grade=RequestedResultGrade.DECISION_GRADE,
            ),
        },
    }


def _read_fixture() -> dict[str, Any]:
    try:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid Liquidation Audit fixture: {FIXTURE}") from error


def test_conservative_linear_liquidation_audit_matches_static_golden() -> None:
    assert build_actual() == _read_fixture()
