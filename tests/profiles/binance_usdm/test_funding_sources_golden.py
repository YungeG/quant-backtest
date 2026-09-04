from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_domain import canonical_bytes
from crypto_quant_trading.profiles.binance_usdm import BinanceUsdmFundingSourceModel

from ._funding_source_fixtures import funding_book, funding_query, funding_record


FIXTURES = Path(__file__).parents[2] / "fixtures" / "profiles"


def _decode(value: object) -> object:
    try:
        return json.loads(canonical_bytes(value))
    except json.JSONDecodeError as error:
        raise AssertionError("canonical funding payload did not decode") from error


def _load(name: str) -> object:
    try:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid golden fixture: {name}") from error


def build_source_actual() -> object:
    return _decode(
        {
            "fixture_id": "binance-usdm-historical-funding-source-v1",
            "provider": "binance_usdm",
            "source_contract": "funding-rate-history-regular-root-row",
            "funding_book": funding_book(),
        }
    )


def build_golden_actual() -> object:
    model = BinanceUsdmFundingSourceModel()
    success = model.resolve_funding_source(funding_query())
    special = model.resolve_funding_source(
        funding_query(
            book=funding_book(records=(funding_record(rate_type="Special"),))
        )
    )
    return _decode(
        {
            "fixture_id": "binance-usdm-funding-source-semantics-v1",
            "allowed_grade": "development",
            "deployment_authorized": False,
            "model_digest": model.model_digest,
            "success": success,
            "special_failure": special,
            "limitations": (
                "offline-caller-supplied-evidence-only",
                "archive-completeness-owned-by-g12",
                "regular-rate-type-only",
                "root-source-revision-only",
                "no-live-or-deployment-authorization",
            ),
        }
    )


def test_historical_funding_source_fixture_is_static() -> None:
    assert build_source_actual() == _load(
        "binance-usdm-historical-funding-source-v1.json"
    )


def test_funding_source_resolution_golden_is_static() -> None:
    assert build_golden_actual() == _load(
        "binance-usdm-funding-source-semantics-v1.json"
    )
