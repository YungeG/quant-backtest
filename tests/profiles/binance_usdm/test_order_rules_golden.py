from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from crypto_quant_domain import UtcInstant, canonical_bytes, canonical_sha256
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmDeferredRuleKey,
    BinanceUsdmOrderAdmissionMode,
    BinanceUsdmOrderRuleModel,
    BinanceUsdmOrderRuleQuery,
    BinanceUsdmOrderRuleSourceRef,
)
from tests.profiles.binance_usdm._order_rule_fixtures import (
    DELIST_AT,
    ONBOARD_AT,
    RENAME_AT,
    REQUIRED_FILTERS,
    band,
    complete_bands,
    order_rule_query,
)


ROOT = Path(__file__).resolve().parents[3]
SOURCE_FIXTURE = (
    ROOT / "tests/fixtures/profiles/binance-usdm-historical-order-rule-source-v1.json"
)
GOLDEN_FIXTURE = (
    ROOT / "tests/fixtures/profiles/binance-usdm-historical-order-rules-v1.json"
)
SUSPEND_END = UtcInstant(RENAME_AT.epoch_nanoseconds + 60_000_000_000)


def _decode(value: object) -> object:
    try:
        return json.loads(canonical_bytes(value))
    except json.JSONDecodeError as error:
        raise AssertionError("canonical payload did not decode") from error


def _read(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot read canonical fixture: {path.name}") from error


def build_cases() -> dict[str, BinanceUsdmOrderRuleQuery]:
    first, second = complete_bands()
    closed = band(
        "rules-closed",
        effective_from=RENAME_AT,
        effective_to_exclusive=SUSPEND_END,
        tick_size="0.01",
        admission_mode=BinanceUsdmOrderAdmissionMode.CLOSED,
    )
    resumed = band(
        "rules-resumed",
        effective_from=SUSPEND_END,
        effective_to_exclusive=DELIST_AT,
        tick_size="0.01",
    )
    _, reduce_only = complete_bands(
        second_admission=BinanceUsdmOrderAdmissionMode.REDUCE_ONLY,
        second_deferred=(BinanceUsdmDeferredRuleKey.PERCENT_PRICE.value,),
    )
    late_at = UtcInstant(RENAME_AT.epoch_nanoseconds + 100)
    _, late = complete_bands(second_available_at=late_at)
    source_conflict = replace(
        second,
        source_ref=BinanceUsdmOrderRuleSourceRef(
            source_key=first.source_ref.source_key,
            source_hash="sha256:" + "f" * 64,
        ),
    )
    return {
        "tick_before": order_rule_query(
            first,
            second,
            evaluated_at=UtcInstant(RENAME_AT.epoch_nanoseconds - 1),
        ),
        "tick_at": order_rule_query(first, second, evaluated_at=RENAME_AT),
        "tick_after": order_rule_query(
            first,
            second,
            evaluated_at=UtcInstant(RENAME_AT.epoch_nanoseconds + 1),
        ),
        "input_order_reverse": order_rule_query(second, first),
        "closed_suspension": order_rule_query(
            first,
            closed,
            resumed,
            evaluated_at=UtcInstant(RENAME_AT.epoch_nanoseconds + 10),
        ),
        "reduce_only_deferred": order_rule_query(first, reduce_only),
        "late_band_hidden": order_rule_query(first, late),
        "late_band_visible": order_rule_query(
            first,
            late,
            captured_at=UtcInstant(late_at.epoch_nanoseconds + 1),
        ),
        "coverage_gap": order_rule_query(
            replace(
                first,
                effective_to_exclusive=UtcInstant(RENAME_AT.epoch_nanoseconds - 1),
            ),
            second,
        ),
        "coverage_overlap": order_rule_query(
            replace(
                first,
                effective_to_exclusive=UtcInstant(RENAME_AT.epoch_nanoseconds + 1),
            ),
            second,
        ),
        "missing_filter": order_rule_query(
            first,
            replace(
                second,
                filter_keys=tuple(
                    value for value in REQUIRED_FILTERS if value != "MIN_NOTIONAL"
                ),
            ),
        ),
        "invalid_decimal": order_rule_query(
            first,
            replace(second, tick_size="1E-2"),
        ),
        "invalid_offset": order_rule_query(
            first,
            replace(second, min_price="0.015", tick_size="0.01"),
        ),
        "unknown_filter": order_rule_query(
            first,
            replace(second, filter_keys=(*REQUIRED_FILTERS, "UNKNOWN")),
        ),
        "unknown_capability": order_rule_query(
            first,
            replace(second, order_types=("LIMIT", "MARKET", "PEGGED")),
        ),
        "unknown_tif": order_rule_query(
            first,
            replace(second, time_in_forces=("GTC", "RPI")),
        ),
        "unknown_deferred": order_rule_query(
            first,
            replace(second, deferred_rule_keys=("UNKNOWN_DEFERRED",)),
        ),
        "instrument_metadata_mismatch": replace(
            order_rule_query(first, second),
            evaluated_at=UtcInstant(RENAME_AT.epoch_nanoseconds + 11),
        ),
        "source_conflict": order_rule_query(first, source_conflict),
        "closed_status_conflict": order_rule_query(
            first,
            second,
            metadata_status="TRADING_HALT",
        ),
        "open_ended_source_boundary": order_rule_query(
            band(effective_from=ONBOARD_AT, effective_to_exclusive=RENAME_AT),
            second,
        ),
    }


def build_source_actual() -> object:
    return _decode(
        {
            "fixture_id": "binance-usdm-historical-order-rule-source-v1",
            "provider": "binance_usdm",
            "source_contract": "frozen-normalized-exchange-info-rule-bands",
            "rule_books": {
                name: value.rule_book for name, value in build_cases().items()
            },
        }
    )


def build_golden_actual() -> object:
    model = BinanceUsdmOrderRuleModel()
    cases = build_cases()
    outcomes = {name: model.resolve_order_rules(value) for name, value in cases.items()}
    return _decode(
        {
            "fixture_id": "binance-usdm-historical-order-rules-v1",
            "allowed_grade": "development",
            "deployment_authorized": False,
            "component_ref": model.component_ref,
            "queries": cases,
            "outcomes": outcomes,
            "outcome_hashes": {
                name: canonical_sha256(value) for name, value in outcomes.items()
            },
            "limitations": (
                "offline-frozen-source-only",
                "deferred-rules-are-not-decision-grade",
                "no-mark-account-or-current-rule-fallback",
                "no-live-or-deployment-authorization",
            ),
        }
    )


def test_normalized_order_rule_sources_match_static_fixture() -> None:
    assert build_source_actual() == _read(SOURCE_FIXTURE)


def test_order_rule_outcomes_match_static_golden() -> None:
    assert build_golden_actual() == _read(GOLDEN_FIXTURE)
