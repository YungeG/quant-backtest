from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from crypto_quant_domain import (
    BalanceChange,
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    FeeBasisType,
    Money,
    OrderSide,
    PositionBalanceKey,
    QuantizationPolicy,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
)
from crypto_quant_trading import CashAccountingFailureCode, CashInstrumentAccounting
from crypto_quant_trading.profiles.cn_a_share.january_2024_development_fee_authority import (
    assess_january_2024_commission,
    january_2024_commission_scenarios,
)
from tests.kernel.accounting._fixtures import COST_BASIS_POLICY_V2
from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    filled_stream,
    partial_cancelled_stream,
    single_fill_stream,
    unfilled_cancelled_stream,
)
from tests.kernel.profiles.cn_a_share.test_000703_january_2024_fee_scenarios import (
    MARKET,
    START,
    TAX,
)


def _inputs():
    stream = single_fill_stream(
        quantity_units=1_000, side=OrderSide.BUY, effective_at=START
    )
    fill = next(record.fill for record in stream.records if record.fill is not None)
    at = UtcInstant(START.epoch_nanoseconds + 100)
    recorded = SimulationInstant(at, TimelinePhase(90, "accounting"), SourceSequence(1))
    cash_key = CashBalanceKey(fill.account_id, fill.venue_id, CurrencyId("CNY"))
    booked = CashInstrumentAccounting().book_fill(
        fill=fill,
        cash_key=cash_key,
        position_key=PositionBalanceKey(fill.account_id, fill.venue_id, fill.instrument_id),
        open_lots=(),
        cost_basis_policy=COST_BASIS_POLICY_V2,
        notional_quantization=QuantizationPolicy("order-fee-test.v1", Scale(2), RoundingPolicy.HALF_UP),
        journal_entry_id=DomainId(DomainIdKind.JOURNAL, DomainIdKind.JOURNAL.prefix + "_" + "d" * 64),
        recorded_at=recorded,
    )
    assert booked.result is not None
    assessed = assess_january_2024_commission(
        january_2024_commission_scenarios()[1],
        stream, MARKET, TAX,
        DomainId(DomainIdKind.FEE, "fee_" + "e" * 64),
        at,
    )
    assert assessed.result is not None
    inputs: dict[str, Any] = {
        "assessment": assessed.result.assessment,
        "order_stream": stream,
        "cash_key": cash_key,
        "open_lots": booked.result.open_lots,
        "cost_basis_policy": COST_BASIS_POLICY_V2,
        "journal_entry_id": DomainId(DomainIdKind.JOURNAL, DomainIdKind.JOURNAL.prefix + "_" + "f" * 64),
        "recorded_at": replace(recorded, source_sequence=SourceSequence(2)),
    }
    return stream, fill, booked.result, inputs


def test_frozen_january_order_commission_posts_without_relabeling_the_basis():
    stream, fill, booked, inputs = _inputs()
    outcome = CashInstrumentAccounting().charge_order_fee(**inputs)
    assert outcome.result is not None
    result = outcome.result
    assert inputs["assessment"].basis_type is FeeBasisType.ORDER
    assert result.journal_entry.fees == (Money(500, Scale(2), "CNY"),)
    assert result.journal_entry.balance_changes == (
        BalanceChange(inputs["cash_key"], Money(-500, Scale(2), "CNY")),
    )
    assert str(stream.order.order_id) in result.journal_entry.source_ids
    assert str(fill.fill_id) in result.journal_entry.source_ids
    assert result.open_lots[0].total_cost_basis == Money(1_000_000, Scale(2), "CNY")
    assert result.open_lots[0].allocated_fees == (Money(500, Scale(2), "CNY"),)
    assert result.journal_entry.position_lot_changes[0].before == booked.open_lots[0]


@pytest.mark.parametrize("stream", (
    partial_cancelled_stream(quantity_units=1_000, side=OrderSide.BUY, effective_at=START),
    filled_stream(quantity_units=1_000, side=OrderSide.BUY, effective_at=START, fill_quantities=(400, 600)),
    unfilled_cancelled_stream(side=OrderSide.BUY, effective_at=START),
))
def test_partial_multiple_and_unfilled_orders_have_no_order_fee_posting(stream):
    _, _, _, inputs = _inputs()
    outcome = CashInstrumentAccounting().charge_order_fee(**{**inputs, "order_stream": stream})
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is CashAccountingFailureCode.UNSUPPORTED_FEE_BASIS


def test_order_fee_cannot_borrow_another_order_identity_or_a_fill_assessment():
    _, fill, _, inputs = _inputs()
    assessment = inputs["assessment"]
    for substituted in (
        replace(assessment, basis_ids=(DomainId(DomainIdKind.ORDER, DomainIdKind.ORDER.prefix + "_" + "a" * 64),)),
        replace(assessment, basis_type=FeeBasisType.FILL, basis_ids=(fill.fill_id,)),
    ):
        outcome = CashInstrumentAccounting().charge_order_fee(**{**inputs, "assessment": substituted})
        assert outcome.result is None
        assert outcome.failure is not None


def test_order_fee_cannot_be_recorded_before_its_terminal_event_at_the_same_utc_time():
    stream, _, _, inputs = _inputs()
    terminal = stream.records[-1].event.occurred_at
    inputs["assessment"] = replace(inputs["assessment"], assessment_time=terminal.instant)
    inputs["recorded_at"] = SimulationInstant(terminal.instant, TimelinePhase(0, "before_fill"), SourceSequence(0))
    outcome = CashInstrumentAccounting().charge_order_fee(**inputs)
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is CashAccountingFailureCode.CONTEXT_MISMATCH


def test_order_assessment_cannot_be_posted_through_the_legacy_fill_operation():
    _, fill, _, inputs = _inputs()
    del inputs["order_stream"]
    outcome = CashInstrumentAccounting().charge_fee(**inputs, related_fill=fill)
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is CashAccountingFailureCode.UNSUPPORTED_FEE_BASIS
