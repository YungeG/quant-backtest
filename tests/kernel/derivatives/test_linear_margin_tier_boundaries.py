from __future__ import annotations

import json
from dataclasses import replace

from crypto_quant_domain import Money, PricePurpose, UtcInstant, canonical_bytes
from crypto_quant_trading import (
    LinearInstrumentMarginFailureCode,
    LinearInstrumentMarginModel,
    LinearMarginRuleInterval,
    LinearMarginTierBoundaryConvention,
)
from tests.kernel.derivatives.test_linear_margin_requirement import (
    QUOTE_CURRENCY,
    TIER_SCALE,
    _interval,
    _request,
    _rule_book,
    _tiers,
    _with_mark,
)


def _decode(value: object) -> dict[str, object]:
    try:
        decoded = json.loads(canonical_bytes(value))
    except json.JSONDecodeError as error:
        raise AssertionError("canonical margin payload did not decode") from error
    assert isinstance(decoded, dict)
    return decoded


LEGACY_HASHES = {
    "interval": "sha256:69495ad82e96a2120ea8f741de1a446a0c54d8f3afd19601d5ee25f50206913c",
    "rule_book": "sha256:2f4bffc82560866b4f5b882b2eace9b343e03293f0dfcab13aab4c3a4fb7e863",
    "request": "sha256:e0709ce12aad6b2ae801e60163ab40d048cf552d960f3e5c2f39c393cdf98db1",
    "result": "sha256:0004fa3d6bdb2d01472bc59add0e5d749c2c5524106d4b0f7940398e57c3c0f6",
}


def _finite_rule_book(
    convention: LinearMarginTierBoundaryConvention,
):
    first, second = _tiers()
    tiers = (
        first,
        replace(
            second,
            notional_cap=Money(
                10_000,
                TIER_SCALE,
                str(QUOTE_CURRENCY),
            ),
        ),
    )
    base = _interval(tiers=tiers)
    interval = LinearMarginRuleInterval(
        interval_id=base.interval_id,
        effective_from=base.effective_from,
        effective_to_exclusive=base.effective_to_exclusive,
        available_at=base.available_at,
        tiers=base.tiers,
        source_key=base.source_key,
        source_hash=base.source_hash,
        tier_boundary_convention=convention,
    )
    return _rule_book((interval,))


def _evaluate(
    quantity_units: int,
    convention: LinearMarginTierBoundaryConvention,
):
    return LinearInstrumentMarginModel().evaluate_margin(
        _request(
            quantity_units,
            rule_book=_finite_rule_book(convention),
        )
    )


def test_legacy_interval_bytes_hashes_and_boundary_selection_are_unchanged() -> None:
    interval = _interval()
    rule_book = _rule_book()
    request = _request()
    outcome = LinearInstrumentMarginModel().evaluate_margin(request)
    assert outcome.result is not None

    payload = _decode(interval)
    assert payload["schema_version"] == 1
    assert "tier_boundary_convention" not in payload
    assert interval.interval_hash == LEGACY_HASHES["interval"]
    assert rule_book.rule_book_hash == LEGACY_HASHES["rule_book"]
    assert request.request_hash == LEGACY_HASHES["request"]
    assert outcome.result.result_hash == LEGACY_HASHES["result"]

    shared_boundary = LinearInstrumentMarginModel().evaluate_margin(_request(4_000))
    assert shared_boundary.result is not None
    assert shared_boundary.result.resolved_tier.tier_id == "synthetic-margin-tier-2"


def test_non_default_boundary_convention_uses_schema_v2_identity() -> None:
    interval = _finite_rule_book(
        LinearMarginTierBoundaryConvention.LOWER_EXCLUSIVE_UPPER_INCLUSIVE
    ).intervals[0]
    payload = _decode(interval)

    assert payload["schema_version"] == 2
    assert payload["tier_boundary_convention"] == (
        "lower_exclusive_upper_inclusive"
    )
    assert interval.interval_hash != LEGACY_HASHES["interval"]


def test_binance_boundaries_select_zero_and_shared_caps_without_epsilon() -> None:
    convention = (
        LinearMarginTierBoundaryConvention.LOWER_EXCLUSIVE_UPPER_INCLUSIVE
    )
    expected = (
        (0, "synthetic-margin-tier-1"),
        (3_999, "synthetic-margin-tier-1"),
        (4_000, "synthetic-margin-tier-1"),
        (4_001, "synthetic-margin-tier-2"),
        (8_000, "synthetic-margin-tier-2"),
    )

    for quantity_units, tier_id in expected:
        outcome = _evaluate(quantity_units, convention)
        assert outcome.failure is None
        assert outcome.result is not None
        assert outcome.result.resolved_tier.tier_id == tier_id


def test_finite_terminal_cap_overflow_is_structured_and_precedes_leverage() -> None:
    convention = (
        LinearMarginTierBoundaryConvention.LOWER_EXCLUSIVE_UPPER_INCLUSIVE
    )
    overflow = _evaluate(8_001, convention)

    assert overflow.result is None
    assert overflow.failure is not None
    assert overflow.failure.code is (
        LinearInstrumentMarginFailureCode.NOTIONAL_OUTSIDE_TIER_COVERAGE
    )


def test_margin_mark_failures_still_precede_finite_tier_coverage() -> None:
    convention = (
        LinearMarginTierBoundaryConvention.LOWER_EXCLUSIVE_UPPER_INCLUSIVE
    )
    request = _request(8_001, rule_book=_finite_rule_book(convention))
    evidence = request.margin_mark_evidence
    assert evidence is not None
    invalid = _with_mark(
        request,
        replace(evidence.resolved_mark, price_purpose=PricePurpose.FUNDING),
    )

    outcome = LinearInstrumentMarginModel().evaluate_margin(invalid)

    assert outcome.failure is not None
    assert outcome.failure.code is (
        LinearInstrumentMarginFailureCode.MARGIN_MARK_PURPOSE_MISMATCH
    )


def test_time_interval_semantics_remain_lower_inclusive_upper_exclusive() -> None:
    interval = _finite_rule_book(
        LinearMarginTierBoundaryConvention.LOWER_EXCLUSIVE_UPPER_INCLUSIVE
    ).intervals[0]

    assert interval.contains(UtcInstant(0))
