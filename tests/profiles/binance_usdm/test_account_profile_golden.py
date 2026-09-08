from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_domain import canonical_bytes
from crypto_quant_trading.profiles.binance_usdm import BinanceUsdmAccountProfileModel

from ._account_profile_fixtures import account_band, account_book, account_query


FIXTURES = Path(__file__).parents[2] / "fixtures" / "profiles"


def _decode(value: object) -> object:
    try:
        return json.loads(canonical_bytes(value))
    except json.JSONDecodeError as error:
        raise AssertionError("canonical account-profile payload did not decode") from error


def _load(name: str) -> object:
    try:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid golden fixture: {name}") from error


def build_source_actual() -> object:
    return _decode(
        {
            "fixture_id": "binance-usdm-historical-account-profile-source-v1",
            "provider": "binance_usdm",
            "source_contract": "account-symbol-commission-feeburn-snapshots",
            "account_profile_book": account_book(),
        }
    )


def build_golden_actual() -> object:
    model = BinanceUsdmAccountProfileModel()
    success = model.resolve_account_profile(account_query())
    hedge = model.resolve_account_profile(
        account_query(book=account_book(bands=(account_band(dual_side_position=True),)))
    )
    return _decode(
        {
            "fixture_id": "binance-usdm-fee-account-profile-v1",
            "allowed_grade": "development",
            "deployment_authorized": False,
            "model_digest": model.model_digest,
            "success": success,
            "hedge_failure": hedge,
            "limitations": (
                "offline-caller-supplied-evidence-only",
                "account-history-completeness-owned-by-g12",
                "fee-rounding-parity-owned-by-g10h",
                "negative-rebates-and-bnb-discount-unsupported",
                "no-live-or-deployment-authorization",
            ),
        }
    )


def test_historical_account_profile_source_fixture_is_static() -> None:
    assert build_source_actual() == _load(
        "binance-usdm-historical-account-profile-source-v1.json"
    )


def test_fee_account_profile_golden_is_static() -> None:
    assert build_golden_actual() == _load("binance-usdm-fee-account-profile-v1.json")
