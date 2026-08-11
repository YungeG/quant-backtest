from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from crypto_quant_domain import UtcInstant, canonical_bytes, canonical_sha256
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmMarginTierModel,
    BinanceUsdmMarginTierQuery,
    BinanceUsdmMarginTierScope,
)
from tests.profiles.binance_usdm._fixtures import RENAME_AT
from tests.profiles.binance_usdm._margin_tier_fixtures import (
    CONTRACT_INFO_STATUS_UPDATE,
    band,
    complete_bands,
    margin_tier_query,
    simulation_instant,
)


ROOT = Path(__file__).resolve().parents[3]
SOURCE_FIXTURE = (
    ROOT
    / "tests/fixtures/profiles/binance-usdm-contract-info-margin-tier-source-v1.json"
)
GOLDEN_FIXTURE = (
    ROOT / "tests/fixtures/profiles/binance-usdm-historical-margin-tiers-v1.json"
)


def _decode(value: object) -> object:
    try:
        return json.loads(canonical_bytes(value))
    except json.JSONDecodeError as error:
        raise AssertionError("canonical margin-tier payload did not decode") from error


def _read(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot read canonical fixture: {path.name}") from error


def build_cases() -> dict[str, BinanceUsdmMarginTierQuery]:
    first, second = complete_bands()
    late_at = simulation_instant(
        UtcInstant(RENAME_AT.epoch_nanoseconds + 100)
    )
    _, late = complete_bands(second_available_at=late_at)
    return {
        "before_update": margin_tier_query(
            first,
            second,
            evaluated_at=UtcInstant(RENAME_AT.epoch_nanoseconds - 1),
        ),
        "at_update": margin_tier_query(first, second, evaluated_at=RENAME_AT),
        "after_update": margin_tier_query(
            first,
            second,
            evaluated_at=UtcInstant(RENAME_AT.epoch_nanoseconds + 1),
        ),
        "input_order_reverse": margin_tier_query(second, first),
        "late_band_hidden": margin_tier_query(first, late),
        "late_band_visible": margin_tier_query(
            first,
            late,
            captured_at=simulation_instant(
                UtcInstant(late_at.instant.epoch_nanoseconds + 1)
            ),
        ),
        "coverage_gap": margin_tier_query(
            replace(
                first,
                effective_to_exclusive=UtcInstant(
                    RENAME_AT.epoch_nanoseconds - 1
                ),
            ),
            second,
        ),
        "coverage_overlap": margin_tier_query(
            replace(
                first,
                effective_to_exclusive=UtcInstant(
                    RENAME_AT.epoch_nanoseconds + 1
                ),
            ),
            second,
        ),
        "bracket_order": margin_tier_query(
            first,
            replace(second, brackets=tuple(reversed(second.brackets))),
        ),
        "invalid_decimal": margin_tier_query(
            first,
            replace(
                second,
                brackets=(
                    replace(second.brackets[0], notional_cap="1E4"),
                    *second.brackets[1:],
                ),
            ),
        ),
        "account_adjusted": margin_tier_query(
            first,
            replace(
                second,
                scope=BinanceUsdmMarginTierScope.ACCOUNT_ADJUSTED,
            ),
        ),
        "notional_coef": margin_tier_query(
            first,
            replace(second, notional_coef="1"),
        ),
        "status_only_source": margin_tier_query(
            first,
            band(
                "margin-tiers-v2",
                effective_from=RENAME_AT,
                effective_to_exclusive=second.effective_to_exclusive,
                brackets=second.brackets,
                source_kind=CONTRACT_INFO_STATUS_UPDATE,
            ),
        ),
    }


def build_source_actual() -> object:
    return _decode(
        {
            "fixture_id": "binance-usdm-contract-info-margin-tier-source-v1",
            "provider": "binance_usdm",
            "source_contract": "archived-contract-info-bracket-update-bands",
            "rule_books": {
                name: query.rule_book for name, query in build_cases().items()
            },
        }
    )


def build_golden_actual() -> object:
    model = BinanceUsdmMarginTierModel()
    cases = build_cases()
    outcomes = {
        name: model.resolve_margin_tiers(query)
        for name, query in cases.items()
    }
    return _decode(
        {
            "fixture_id": "binance-usdm-historical-margin-tiers-v1",
            "allowed_grade": "development",
            "deployment_authorized": False,
            "component_ref": model.component_ref,
            "queries": cases,
            "outcomes": outcomes,
            "outcome_hashes": {
                name: canonical_sha256(outcome)
                for name, outcome in outcomes.items()
            },
            "limitations": (
                "offline-archived-contract-info-only",
                "finite-terminal-notional-coverage",
                "no-account-adjusted-or-current-bracket-fallback",
                "no-live-or-deployment-authorization",
            ),
        }
    )


def test_contract_info_margin_tier_sources_match_static_fixture() -> None:
    assert build_source_actual() == _read(SOURCE_FIXTURE)


def test_historical_margin_tier_outcomes_match_static_golden() -> None:
    assert build_golden_actual() == _read(GOLDEN_FIXTURE)
