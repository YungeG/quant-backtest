from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from crypto_quant_domain import PricePurpose, UtcInstant, canonical_bytes, canonical_sha256
from crypto_quant_trading.profiles.binance_usdm import BinanceUsdmPriceStreamModel

from ._price_stream_fixtures import (
    BAR_START,
    MILLISECOND,
    REQUESTED_AT,
    aggregate_trade,
    mark_bars,
    price_book,
    price_query,
    simulation_instant,
)

ROOT = Path(__file__).resolve().parents[3]
SOURCE_FIXTURE = ROOT / "tests/fixtures/profiles/binance-usdm-historical-price-source-v1.json"
GOLDEN_FIXTURE = ROOT / "tests/fixtures/profiles/binance-usdm-price-purpose-streams-v1.json"


def _decode(value: object) -> object:
    try:
        return json.loads(canonical_bytes(value))
    except json.JSONDecodeError as error:
        raise AssertionError("canonical price-stream payload did not decode") from error


def _read(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot read canonical fixture: {path.name}") from error


def build_cases():
    bars = mark_bars()
    observed = UtcInstant(REQUESTED_AT.epoch_nanoseconds - 5 * MILLISECOND)
    same_utc_late = aggregate_trade(
        trade_at=observed,
        available_at=simulation_instant(observed, phase=1, sequence=1),
    )
    malformed = replace(aggregate_trade(), price="5E4")
    return {
        "execution_reference": price_query(PricePurpose.EXECUTION_REFERENCE),
        "valuation": price_query(PricePurpose.VALUATION),
        "margin": price_query(PricePurpose.MARGIN),
        "liquidation": price_query(
            PricePurpose.LIQUIDATION,
            liquidation_interval_start=BAR_START,
            liquidation_interval_end_exclusive=REQUESTED_AT,
        ),
        "settlement_unsupported": price_query(PricePurpose.SETTLEMENT),
        "funding_owned_by_g10e": price_query(PricePurpose.FUNDING),
        "input_order_reverse": price_query(
            PricePurpose.VALUATION,
            book=price_book(bars=tuple(reversed(bars))),
        ),
        "liquidation_gap": price_query(
            PricePurpose.LIQUIDATION,
            book=price_book(bars=(bars[0],)),
            liquidation_interval_start=BAR_START,
            liquidation_interval_end_exclusive=REQUESTED_AT,
        ),
        "invalid_decimal": price_query(
            PricePurpose.EXECUTION_REFERENCE,
            book=price_book(aggregate_trades=(malformed,)),
        ),
        "same_utc_late": price_query(
            PricePurpose.EXECUTION_REFERENCE,
            book=price_book(aggregate_trades=(same_utc_late,)),
        ),
    }


def build_source_actual() -> object:
    return _decode(
        {
            "fixture_id": "binance-usdm-historical-price-source-v1",
            "provider": "binance_usdm",
            "source_contract": "archived-aggregate-trades-and-closed-mark-price-klines",
            "price_book": price_book(),
        }
    )


def build_golden_actual() -> object:
    model = BinanceUsdmPriceStreamModel()
    cases = build_cases()
    summaries: dict[str, object] = {}
    for name, query in cases.items():
        outcome = model.resolve_price_purpose(query)
        if outcome.result is not None:
            summaries[name] = {
                "query_hash": query.query_hash,
                "outcome_hash": canonical_sha256(outcome),
                "resolution_hash": outcome.result.resolution_hash,
                "resolved_mark_id": (
                    None
                    if outcome.result.resolved_mark is None
                    else outcome.result.resolved_mark.mark_id
                ),
                "observation_hashes": [
                    value.observation_hash for value in outcome.result.observations
                ],
                "liquidation_bar_hashes": [
                    value.bar_hash for value in outcome.result.liquidation_bars
                ],
                "decision_grade_eligible": outcome.result.decision_grade_eligible,
            }
        else:
            assert outcome.failure is not None
            summaries[name] = {
                "query_hash": query.query_hash,
                "outcome_hash": canonical_sha256(outcome),
                "failure_hash": outcome.failure.failure_hash,
                "failure_code": outcome.failure.code.value,
                "mark_failure_id": (
                    None
                    if outcome.failure.mark_failure is None
                    else outcome.failure.mark_failure.failure_id
                ),
            }
    return _decode(
        {
            "fixture_id": "binance-usdm-price-purpose-streams-v1",
            "allowed_grade": "development",
            "deployment_authorized": False,
            "model_digest": model.model_digest,
            "cases": summaries,
            "limitations": (
                "offline-caller-supplied-evidence-only",
                "archive-completeness-owned-by-g12",
                "settlement-price-unsupported",
                "funding-price-owned-by-g10e",
                "no-live-or-deployment-authorization",
            ),
        }
    )


def test_historical_price_sources_match_static_fixture() -> None:
    assert build_source_actual() == _read(SOURCE_FIXTURE)


def test_price_purpose_outcomes_match_static_golden() -> None:
    assert build_golden_actual() == _read(GOLDEN_FIXTURE)
