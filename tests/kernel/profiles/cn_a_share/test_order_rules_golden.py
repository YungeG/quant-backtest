from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from crypto_quant_domain import OrderSide, canonical_bytes
from crypto_quant_trading import MarketRuleEvaluator
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareBarLimitLiquidityEvaluator,
    CnAShareCashOrderRuleModel,
    CnAShareLimitLiquidityInput,
    CnAShareOpenObservationState,
    CnAShareOrderRuleBook,
    CnAShareTradeStatus,
)
from tests.kernel.market_rules._fixtures import (
    evaluation_input,
    interval,
    snapshot as generic_snapshot,
    timeline,
)
from tests.kernel.market_rules.test_market_rule_position_evidence import (
    _position_evidence,
    _residual_lattice,
    _sell_spec,
)
from tests.kernel.profiles.cn_a_share.test_order_rules import (
    PRICE_SCALE,
    _chinext_band,
    _instrument,
    _main_case,
    _resolve_chinext,
    _star_band,
)


ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "tests/fixtures/kernel/profiles/cn_a_share/historical-order-rules-v1.json"


def _read_json(path: Path) -> dict[str, object]:
    try:
        decoded = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot read canonical JSON: {path.name}") from error
    assert isinstance(decoded, dict)
    return decoded


def _decision_summary(decision: object) -> dict[str, object]:
    rejection = getattr(decision, "rejection")
    failure = getattr(decision, "data_integrity_failure")
    return {
        "decision_id": getattr(decision, "decision_id"),
        "decision_hash": getattr(decision, "decision_hash"),
        "outcome": (
            "approved"
            if getattr(decision, "approval") is not None
            else "rejected"
            if rejection is not None
            else "data_integrity_failure"
        ),
        "issues": () if rejection is None else rejection.issues,
        "data_integrity_code": None if failure is None else failure.code.value,
    }


def build_actual() -> dict[str, object]:
    main_model, main_query = _main_case(
        local_date=date(2024, 2, 8),
        status=CnAShareTradeStatus.NORMAL,
        include_previous_close=True,
    )
    main = main_model.resolve_order_rules(main_query)
    suspended_model, suspended_query = _main_case(
        local_date=date(2024, 2, 8),
        status=CnAShareTradeStatus.SUSPENDED,
        include_previous_close=True,
    )
    suspended = suspended_model.resolve_order_rules(suspended_query)
    no_trade_model, no_trade_query = _main_case(
        local_date=date(2024, 2, 9),
        status=None,
        include_previous_close=False,
    )
    no_trade = no_trade_model.resolve_order_rules(no_trade_query)
    missing_model, missing_query = _main_case(
        local_date=date(2024, 2, 8),
        status=None,
        include_previous_close=True,
    )
    missing = missing_model.resolve_order_rules(missing_query)
    assert main.result is not None
    assert main.result.timeline is not None
    main_snapshot = main.result.timeline.intervals[0].snapshot

    chinext_model = CnAShareCashOrderRuleModel(
        CnAShareOrderRuleBook(
            rule_book_key="chinext-transition-v1",
            rule_book_version=1,
            bands=(
                _chinext_band(date(2020, 8, 20), date(2020, 8, 24), 1_000),
                _chinext_band(date(2020, 8, 24), date(2020, 8, 26), 2_000),
            ),
        ),
        notional_scale=PRICE_SCALE,
    )
    chinext_instrument = _instrument("xshe", "300001")
    chinext_before = _resolve_chinext(
        chinext_model, chinext_instrument, date(2020, 8, 21)
    )
    chinext_after = _resolve_chinext(
        chinext_model, chinext_instrument, date(2020, 8, 24)
    )

    liquidity = {}
    evaluator = CnAShareBarLimitLiquidityEvaluator()
    assert main_snapshot.lower_price_limit is not None
    assert main_snapshot.upper_price_limit is not None
    for name, side, price in (
        ("buy-upper", OrderSide.BUY, main_snapshot.upper_price_limit),
        ("sell-lower", OrderSide.SELL, main_snapshot.lower_price_limit),
        ("sell-upper", OrderSide.SELL, main_snapshot.upper_price_limit),
        ("buy-lower", OrderSide.BUY, main_snapshot.lower_price_limit),
    ):
        liquidity[name] = evaluator.evaluate(
            CnAShareLimitLiquidityInput(
                side=side,
                snapshot=main_snapshot,
                observation_state=CnAShareOpenObservationState.AVAILABLE,
                bar_open=price,
            )
        )

    lattice = _residual_lattice()
    rule_timeline = timeline(
        intervals=(interval(rule_snapshot=generic_snapshot(quantity_lattice=lattice)),)
    )
    market = MarketRuleEvaluator()
    residual_decisions = {
        "sell-99": market.evaluate(
            evaluation_input(
                spec=_sell_spec(99),
                position_evidence=_position_evidence(lattice),
            ),
            rule_timeline,
        ),
        "split-sell-1": market.evaluate(
            evaluation_input(
                spec=_sell_spec(1),
                position_evidence=_position_evidence(lattice),
            ),
            rule_timeline,
        ),
        "sellable-98-sell-99": market.evaluate(
            evaluation_input(
                spec=_sell_spec(99),
                position_evidence=_position_evidence(lattice, sellable_units=98),
            ),
            rule_timeline,
        ),
    }

    payload = {
        "fixture_id": "cn-a-share-historical-order-rules-v1",
        "qualification": {
            "allowed_grade": "development",
            "deployment_authorized": False,
            "supported": (
                "standard-seasoned-xshg-main",
                "standard-seasoned-xshg-star",
                "standard-seasoned-xshe-main",
                "standard-seasoned-xshe-chinext",
            ),
            "limitations": (
                "risk-warning-cumulative-buy-not-supported",
                "no-daily-limit-price-cage-and-intraday-halt-not-supported",
                "no-full-day-volume-or-queue-inference",
                "no-fee-tax-corporate-action-or-runtime-engine-integration",
            ),
            "official_facts": {
                "main_daily_limit_fraction": "0.10",
                "star_daily_limit_fraction": "0.20",
                "chinext_transition_date": "2020-08-24",
                "main_limit_market_caps": (1_000_000, 1_000_000),
                "star_limit_market_caps": (100_000, 50_000),
                "chinext_limit_market_caps": (300_000, 150_000),
                "price_tick_cny": "0.01",
                "rounding": "half_up",
            },
        },
        "main": {
            "component_ref": main_model.component_ref,
            "input_hash": main.input_hash,
            "resolution": main.result,
        },
        "star_band": _star_band(),
        "chinext": {
            "component_ref": chinext_model.component_ref,
            "before": chinext_before.result,
            "after": chinext_after.result,
        },
        "availability_classification": {
            "suspended": suspended.result,
            "no_trade": no_trade.result,
            "missing_status": missing.failure,
        },
        "limit_liquidity": liquidity,
        "residual_sell_admission": {
            key: _decision_summary(value)
            for key, value in residual_decisions.items()
        },
        "legacy_compatibility": {
            "snapshot_hash": generic_snapshot().snapshot_hash,
            "evaluation_input_hash": evaluation_input().input_hash,
        },
    }
    try:
        decoded = json.loads(canonical_bytes(payload))
    except json.JSONDecodeError as error:
        raise AssertionError("canonical fixture did not decode") from error
    assert isinstance(decoded, dict)
    return decoded


def test_order_rules_match_static_golden() -> None:
    assert build_actual() == _read_json(FIXTURE)
