from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_backtest import BinanceUsdmTradifiProfileComposer
from crypto_quant_domain import canonical_bytes

from ._tradifi_fixtures import composition_request

FIXTURE = (
    Path(__file__).parents[3]
    / "fixtures/runtime/profiles/binance-usdm-tradifi-resolved-profile-composition-v1.json"
)


def _actual() -> object:
    outcome = BinanceUsdmTradifiProfileComposer().compose(composition_request())
    assert outcome.result is not None
    result = outcome.result
    return json.loads(
        canonical_bytes(
            {
                "fixture_id": "binance-usdm-tradifi-resolved-profile-composition-v1",
                "profile_digest": result.profile_digest,
                "market_registration": result.market_registration,
                "simulation_registration": result.simulation_registration,
                "execution_account_registration": result.execution_account_registration,
                "simulation": result.simulation,
                "financial_dispatcher_spec": result.financial_dispatcher_spec,
                "limitations": result.limitations,
                "decision_grade_eligible": result.decision_grade_eligible,
                "deployment_authorized": result.deployment_authorized,
            }
        )
    )


def test_binance_usdm_tradifi_profile_composition_golden_is_static() -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert _actual() == expected
