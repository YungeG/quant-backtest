from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crypto_quant_trading import LinearAccountMarginProjector

from tests.kernel.derivatives.test_linear_account_margin_projection import (
    _request,
    _reservation_evidence,
)


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/kernel/derivatives/linear-account-margin-projection-v1.json"
)


def _case(quantity_units: int, reservation_units: int) -> dict[str, Any]:
    request = _request(
        quantity_units,
        reservation_evidence=_reservation_evidence(reservation_units),
    )
    outcome = LinearAccountMarginProjector().project(request)
    assert outcome.projection is not None
    projection = outcome.projection
    position = projection.position_unrealized_pnl[0]
    return {
        "quantity_units": quantity_units,
        "reservation_units": reservation_units,
        "exact_unrealized": [
            position.exact_unrealized_pnl.numerator,
            position.exact_unrealized_pnl.denominator,
        ],
        "unrealized_units": position.unrealized_pnl.units,
        "wallet_units": projection.wallet_balance.units,
        "realized_pnl_units": projection.realized_pnl.units,
        "fee_units": projection.fees.units,
        "funding_units": projection.funding.units,
        "equity_units": projection.equity.units,
        "initial_margin_units": projection.total_initial_margin.units,
        "maintenance_margin_units": projection.total_maintenance_margin.units,
        "working_order_margin_units": (
            projection.working_order_margin_reservation.units
        ),
        "available_margin_units": projection.available_margin.units,
        "request_hash": request.request_hash,
        "projection_hash": projection.projection_hash,
    }


def build_actual() -> dict[str, Any]:
    projector = LinearAccountMarginProjector()
    return {
        "fixture_id": "synthetic-linear-account-margin-projection-v1",
        "schema_version": 1,
        "component_ref": projector.component_ref.to_canonical_dict(),
        "cases": {
            "long_reserved": _case(1_000, 200),
            "short_reserved": _case(-1_000, 200),
            "long_unreserved": _case(1_000, 0),
            "negative_available": _case(1_000, 200_000),
        },
    }


def _read_fixture() -> dict[str, Any]:
    try:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid Account Margin fixture: {FIXTURE}") from error


def test_linear_account_margin_projection_matches_static_golden() -> None:
    assert build_actual() == _read_fixture()
