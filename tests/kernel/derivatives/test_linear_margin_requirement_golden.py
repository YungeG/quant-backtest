from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crypto_quant_domain import canonical_sha256
from crypto_quant_trading import LinearInstrumentMarginModel

from tests.kernel.derivatives.test_linear_margin_requirement import _request


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/kernel/derivatives/linear-margin-requirement-v1.json"
)


def _case(quantity_units: int) -> dict[str, Any]:
    request = _request(quantity_units)
    outcome = LinearInstrumentMarginModel().evaluate_margin(request)
    assert outcome.result is not None
    result = outcome.result
    leverage = request.leverage_evidence
    rule_book = request.rule_book
    mark = request.margin_mark_evidence
    assert leverage is not None and rule_book is not None and mark is not None
    return {
        "quantity_units": quantity_units,
        "tier_id": result.resolved_tier.tier_id,
        "exact_notional": [
            result.exact_notional.numerator,
            result.exact_notional.denominator,
        ],
        "exact_initial_margin": [
            result.exact_initial_margin.numerator,
            result.exact_initial_margin.denominator,
        ],
        "exact_maintenance_margin": [
            result.exact_maintenance_margin.numerator,
            result.exact_maintenance_margin.denominator,
        ],
        "initial_margin_units": result.initial_margin.units,
        "maintenance_margin_units": result.maintenance_margin.units,
        "leverage_hash": leverage.leverage_hash,
        "rule_book_hash": rule_book.rule_book_hash,
        "config_hash": rule_book.config_hash,
        "interval_hash": result.resolved_interval.interval_hash,
        "tier_hash": result.resolved_tier.tier_hash,
        "mark_evidence_hash": mark.mark_evidence_hash,
        "request_hash": request.request_hash,
        "result_hash": result.result_hash,
        "result_canonical_hash": canonical_sha256(result.to_canonical_dict()),
    }


def build_actual() -> dict[str, Any]:
    model = LinearInstrumentMarginModel()
    return {
        "fixture_id": "synthetic-linear-margin-requirement-v1",
        "schema_version": 1,
        "component_ref": model.component_ref.to_canonical_dict(),
        "cases": {
            "long_lower_tier": _case(1_000),
            "short_lower_tier": _case(-1_000),
            "flat": _case(0),
            "below_tier_boundary": _case(3_999),
            "at_tier_boundary": _case(4_000),
            "above_tier_boundary": _case(4_001),
        },
    }


def _read_fixture() -> dict[str, Any]:
    try:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid Margin requirement fixture: {FIXTURE}") from error


def test_linear_margin_requirement_matches_static_golden() -> None:
    assert build_actual() == _read_fixture()
