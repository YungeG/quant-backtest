from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crypto_quant_domain import RoundingPolicy, canonical_sha256
from crypto_quant_trading import LinearFundingAccounting

from tests.kernel.derivatives.test_linear_funding_accounting import (
    _settlement_request,
)


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/kernel/derivatives/linear-funding-accounting-v1.json"
)


def _case(
    *,
    target_nanoseconds: int,
    rate_units: int,
    rounding: RoundingPolicy = RoundingPolicy.HALF_EVEN,
) -> dict[str, Any]:
    request = _settlement_request(
        rate_units,
        rounding,
        target_nanoseconds=target_nanoseconds,
    )
    outcome = LinearFundingAccounting().assess_financing(request)
    assert outcome.result is not None
    result = outcome.result
    eligibility = request.eligibility
    assert eligibility is not None
    entry = result.journal_entry
    return {
        "target_nanoseconds": target_nanoseconds,
        "position_quantity_units": eligibility.position_state.quantity.units,
        "rate_units": rate_units,
        "rounding": rounding.value,
        "exact_numerator": result.exact_cash_flow.numerator,
        "exact_denominator": result.exact_cash_flow.denominator,
        "payment_units": result.payment.units,
        "application_key": result.application_key.value,
        "settlement_id": entry.settlement_id.value,
        "journal_entry_id": entry.journal_entry_id.value,
        "request_hash": request.request_hash,
        "application_body_hash": entry.application_body_hash,
        "journal_entry_hash": canonical_sha256(entry),
        "source_ids": list(entry.source_ids),
    }


def build_actual() -> dict[str, Any]:
    accounting = LinearFundingAccounting()
    return {
        "fixture_id": "synthetic-linear-funding-accounting-v1",
        "schema_version": 1,
        "component_ref": accounting.component_ref.to_canonical_dict(),
        "direction_cases": {
            "long_positive": _case(target_nanoseconds=3, rate_units=8),
            "long_negative": _case(target_nanoseconds=3, rate_units=-8),
            "short_positive": _case(target_nanoseconds=5, rate_units=8),
            "short_negative": _case(target_nanoseconds=5, rate_units=-8),
            "flat_positive": _case(target_nanoseconds=4, rate_units=8),
            "zero_rate": _case(target_nanoseconds=3, rate_units=0),
            "rounded_zero": _case(target_nanoseconds=3, rate_units=1),
        },
        "tie_controls": {
            f"{rate_units}:{rounding.value}": _case(
                target_nanoseconds=3,
                rate_units=rate_units,
                rounding=rounding,
            )["payment_units"]
            for rate_units in (50, 150, 250, -50, -150, -250)
            for rounding in (RoundingPolicy.HALF_EVEN, RoundingPolicy.HALF_UP)
        },
    }


def _read_fixture() -> dict[str, Any]:
    try:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid Funding accounting fixture: {FIXTURE}") from error


def test_linear_funding_accounting_matches_static_golden() -> None:
    assert build_actual() == _read_fixture()
