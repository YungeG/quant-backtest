from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    Money,
    OrderSide,
    Scale,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import ProfileComponentRef, ProfilePortType
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareExecutionAccessRoute,
    CnAShareFeeProductClass,
)
from crypto_quant_trading.profiles.cn_a_share.january_2024_development_fee_authority import (
    JANUARY_2024_AUTHORITY_SNAPSHOT_SHA256,
    assess_january_2024_commission,
    january_2024_commission_scenarios,
    january_2024_fee_rule_books,
)
from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    filled_stream,
    partial_cancelled_stream,
    single_fill_stream,
    unfilled_cancelled_stream,
)


ROOT = Path(__file__).resolve().parents[4]
SNAPSHOT = (
    ROOT / "evidence/000703-january-2024-statutory-fee-development-v1/snapshot.json"
)
START = UtcInstant(1_704_124_800_000_000_000)
END = UtcInstant(1_706_716_800_000_000_000)
CNY_CENT = Scale(2)


def _id(digit: str) -> DomainId:
    return DomainId(DomainIdKind.FEE, f"fee_{digit * 64}")


def _component(port_type: ProfilePortType, key: str) -> ProfileComponentRef:
    return ProfileComponentRef(
        port_type,
        key,
        1,
        canonical_sha256({"ticket": 26, "component": key}),
    )


MARKET = _component(ProfilePortType.FEE_ASSESSMENT_POLICY, "ticket-26.market")
TAX = _component(ProfilePortType.TAX_POLICY, "ticket-26.tax")


def test_january_authority_is_finite_v2_and_binds_the_frozen_snapshot() -> None:
    assert JANUARY_2024_AUTHORITY_SNAPSHOT_SHA256 == (
        "sha256:" + sha256(SNAPSHOT.read_bytes()).hexdigest()
    )
    market, stamp = january_2024_fee_rule_books()
    assert (
        market.access_route,
        market.fee_product_class,
        stamp.access_route,
        stamp.fee_product_class,
    ) == (
        CnAShareExecutionAccessRoute.DOMESTIC,
        CnAShareFeeProductClass.ORDINARY_A_SHARE,
        CnAShareExecutionAccessRoute.DOMESTIC,
        CnAShareFeeProductClass.ORDINARY_A_SHARE,
    )
    [market_band] = market.bands
    [stamp_band] = stamp.bands
    assert (market_band.effective_from, market_band.effective_to_exclusive) == (
        START,
        END,
    )
    assert (stamp_band.effective_from, stamp_band.effective_to_exclusive) == (
        START,
        END,
    )
    assert (market_band.handling_rate.units, market_band.handling_rate.scale.places) == (
        341,
        7,
    )
    assert (
        market_band.regulatory_rate.units,
        market_band.regulatory_rate.scale.places,
    ) == (2, 5)
    assert (
        market_band.chinaclear_transfer_rate.units,
        market_band.chinaclear_transfer_rate.scale.places,
    ) == (1, 5)
    assert not market_band.hkscc_transfer_applies
    assert market_band.hkscc_transfer_source_refs
    assert stamp_band.applies_to_sell
    assert (stamp_band.rate.units, stamp_band.rate.scale.places) == (5, 4)


def test_immutable_account_scenarios_produce_the_ticket_commissions() -> None:
    stream = single_fill_stream(
        quantity_units=1_000, side=OrderSide.BUY, effective_at=START
    )
    expected = {"3bps": 500, "5bps": 500, "8bps": 800}
    scenarios = january_2024_commission_scenarios()
    assert [scenario.scenario_key for scenario in scenarios] == list(expected)
    assert all(scenario.development_only for scenario in scenarios)
    assert len({scenario.account_fee_schedule_ref for scenario in scenarios}) == 3

    for index, scenario in enumerate(scenarios, start=1):
        outcome = assess_january_2024_commission(
            scenario,
            stream,
            MARKET,
            TAX,
            _id(str(index)),
            UtcInstant(START.epoch_nanoseconds + 50 + index),
        )
        assert outcome.result is not None
        assert outcome.result.assessment.amount == Money(
            expected[scenario.scenario_key], CNY_CENT, "CNY"
        )


def test_half_cent_is_rounded_before_the_per_order_minimum() -> None:
    scenario = january_2024_commission_scenarios()[1]
    stream = single_fill_stream(
        quantity_units=1, side=OrderSide.BUY, effective_at=START
    )
    outcome = assess_january_2024_commission(
        scenario,
        stream,
        MARKET,
        TAX,
        _id("a"),
        UtcInstant(START.epoch_nanoseconds + 50),
    )
    assert outcome.result is not None
    [commission_line] = [
        line
        for line in outcome.result.lines
        if line.rule.source.value == "account_schedule"
    ]
    assert commission_line.amount == Money(1, CNY_CENT, "CNY")
    assert outcome.result.minimum_adjustments[0].amount == Money(499, CNY_CENT, "CNY")
    assert outcome.result.assessment.amount == Money(500, CNY_CENT, "CNY")


def test_commission_scenarios_fail_closed_outside_the_january_authority() -> None:
    stream = single_fill_stream(
        quantity_units=1_000, side=OrderSide.BUY, effective_at=END
    )
    with pytest.raises(ValueError, match="outside January authority"):
        assess_january_2024_commission(
            january_2024_commission_scenarios()[0],
            stream,
            MARKET,
            TAX,
            _id("d"),
            UtcInstant(END.epoch_nanoseconds + 50),
        )


def test_unfilled_terminal_order_is_zero_but_partial_or_multiple_fills_fail_closed() -> None:
    scenario = january_2024_commission_scenarios()[0]
    unfilled = unfilled_cancelled_stream(side=OrderSide.SELL, effective_at=START)
    outcome = assess_january_2024_commission(
        scenario,
        unfilled,
        MARKET,
        TAX,
        _id("b"),
        UtcInstant(START.epoch_nanoseconds + 50),
    )
    assert outcome.result is not None
    assert outcome.result.assessment.amount == Money(0, CNY_CENT, "CNY")
    assert not outcome.result.minimum_adjustments

    for stream in (
        partial_cancelled_stream(
            quantity_units=1_000, side=OrderSide.SELL, effective_at=START
        ),
        filled_stream(
            quantity_units=1_000,
            side=OrderSide.SELL,
            effective_at=START,
            fill_quantities=(400, 600),
        ),
    ):
        with pytest.raises(ValueError, match="one full fill"):
            assess_january_2024_commission(
                scenario,
                stream,
                MARKET,
                TAX,
                _id("c"),
                UtcInstant(START.epoch_nanoseconds + 50),
            )
