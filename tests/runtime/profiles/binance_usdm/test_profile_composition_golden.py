from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_backtest import BinanceUsdmProfileComposer
from crypto_quant_domain import canonical_bytes

from ._fixtures import composition_request


FIXTURE = (
    Path(__file__).parents[3]
    / "fixtures/runtime/profiles/binance-usdm-resolved-profile-composition-v1.json"
)


def _actual() -> object:
    outcome = BinanceUsdmProfileComposer().compose(composition_request())
    assert outcome.result is not None
    try:
        return json.loads(
            canonical_bytes(
                {
                    "fixture_id": "binance-usdm-resolved-profile-composition-v1",
                    "allowed_grade": "development",
                    "deployment_authorized": False,
                    "result": outcome.result,
                }
            )
        )
    except json.JSONDecodeError as error:
        raise AssertionError("canonical composition payload did not decode") from error


def test_binance_usdm_profile_composition_golden_is_static() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError("invalid composition golden fixture") from error
    assert _actual() == expected
