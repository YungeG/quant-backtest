from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from crypto_quant_domain import (
    CurrencyId,
    DomainIdKind,
    FeeBasisType,
    Money,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    OrderSide,
    Rate,
    Scale,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal,
    FeeAssessmentBasisEvidence,
    FeeAssessmentEngine,
    FeeChargedJournalTranslator,
    FeeReservationApplicability,
    FeeReservationBasis,
    FeeReservationEstimator,
    FeeReservationRuleSource,
    FeeAssessmentPolicy,
    FinalFeeApplicability,
    FinalFeeRuleSource,
    ProfilePortType,
    TaxPolicy,
)
import crypto_quant_trading.profiles.cn_a_share as cn_a_share_profile
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashFeeRuleQuery,
    CnAShareCashMarketFeePolicy,
    CnAShareCashStampDutyTaxPolicy,
    CnAShareFeeRuleFailureCode,
    CnAShareFeeTradeMechanism,
    CnAShareFeeRuleSourceRef,
    CnAShareMarketFeeBand,
    CnAShareMarketFeeRuleBook,
    CnAShareStampDutyBand,
    CnAShareStampDutyRuleBook,
)
from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    cash_key,
    domain_id,
    fee_query,
    fill,
    filled_stream,
    final_fill_rule_set,
    final_order_rule_set,
    local_instant,
    market_rule_approval,
    partial_cancelled_stream,
    policies,
    reservation_buffer,
    reservation_rule_set,
    reservation_states,
    source_order,
    unfilled_cancelled_stream,
)


CNY = CurrencyId("CNY")
SHANGHAI = timezone(timedelta(hours=8))


def _instant(day: int, *, nanoseconds: int = 0) -> UtcInstant:
    value = UtcInstant.from_datetime(datetime(2023, 8, day, tzinfo=SHANGHAI))
    return UtcInstant(value.epoch_nanoseconds + nanoseconds)


def _source(key: str, digit: str) -> CnAShareFeeRuleSourceRef:
    return CnAShareFeeRuleSourceRef(key, "sha256:" + digit * 64)


def _instrument(venue: str = "xshg") -> InstrumentDefinition:
    venue_id = VenueId(venue)
    return InstrumentDefinition(
        InstrumentId(venue_id, "600000" if venue == "xshg" else "000001"),
        InstrumentType.EQUITY,
        None,
        CNY,
        CNY,
    )


def _market_band(
    start: int, stop: int, rate_units: int, source_key: str, source_digit: str
) -> CnAShareMarketFeeBand:
    return CnAShareMarketFeeBand(
        venue_id=VenueId("xshg"),
        effective_from=_instant(start),
        effective_to_exclusive=_instant(stop),
        handling_rate=Rate(rate_units, Scale(7), "fee_fraction"),
        handling_source_refs=(_source(source_key, source_digit),),
        regulatory_rate=Rate(2, Scale(5), "fee_fraction"),
        regulatory_source_refs=(
            _source("ndrc-regulatory", "3"),
            _source("sse-bilateral", "4"),
        ),
        transfer_rate=Rate(1, Scale(5), "fee_fraction"),
        transfer_source_refs=(_source("chinaclear-transfer", "5"),),
    )


def _market_book(*, overlap: bool = False) -> CnAShareMarketFeeRuleBook:
    bands = [
        _market_band(25, 28, 487, "sse-handling-old", "1"),
        _market_band(28, 30, 341, "sse-handling-new", "2"),
    ]
    if overlap:
        bands.append(_market_band(27, 29, 400, "overlap", "6"))
    return CnAShareMarketFeeRuleBook("fixture.market-fees.v1", 1, tuple(bands))


def _tax_book() -> CnAShareStampDutyRuleBook:
    baseline = _source("stamp-2008", "7")
    return CnAShareStampDutyRuleBook(
        "fixture.stamp-duty.v1",
        1,
        (
            CnAShareStampDutyBand(
                VenueId("xshg"), _instant(25), _instant(28),
                Rate(1, Scale(3), "fee_fraction"), (baseline,),
            ),
            CnAShareStampDutyBand(
                VenueId("xshg"), _instant(28), _instant(30),
                Rate(5, Scale(4), "fee_fraction"),
                (baseline, _source("stamp-2023", "8")),
            ),
        ),
    )


def _query(side: OrderSide, instant: UtcInstant) -> CnAShareCashFeeRuleQuery:
    return CnAShareCashFeeRuleQuery(
        _instrument(), side, instant, CnAShareFeeTradeMechanism.AUCTION
    )


def test_commission_tax_policies_are_public_profile_ports() -> None:
    market, tax = policies()
    assert isinstance(market, FeeAssessmentPolicy)
    assert isinstance(tax, TaxPolicy)
    for name in (
        "CnAShareCashFeeRuleQuery",
        "CnAShareCashMarketFeePolicy",
        "CnAShareCashStampDutyTaxPolicy",
        "CnAShareFeeReservationBuffer",
        "CnAShareFeeRuleFailure",
        "CnAShareFeeRuleFailureCode",
        "CnAShareFeeRuleSourceRef",
        "CnAShareFeeTradeMechanism",
        "CnAShareMarketFeeBand",
        "CnAShareMarketFeeRuleBook",
        "CnAShareMarketFeeRuleResolution",
        "CnAShareStampDutyBand",
        "CnAShareStampDutyRuleBook",
        "CnAShareStampDutyRuleResolution",
    ):
        assert name in cn_a_share_profile.__all__


def test_reservation_buffer_binds_fill_count_and_resolution_context() -> None:
    effective_at = local_instant(28, 10)
    buffer = reservation_buffer(
        side=OrderSide.SELL,
        effective_at=effective_at,
        maximum_fill_count=2,
    )
    assert buffer.market_charge_rule.basis is FeeReservationBasis.FLAT_PER_ORDER
    assert buffer.market_charge_rule.flat_amount == Money(3, Scale(2), "CNY")
    assert buffer.tax_charge_rule.flat_amount == Money(1, Scale(2), "CNY")
    assert buffer.covers_fill_count(2)
    assert not buffer.covers_fill_count(3)
    subject = source_order(
        quantity_units=300,
        side=OrderSide.SELL,
        effective_at=effective_at,
    )
    fills = tuple(
        fill(
            subject,
            str(index),
            UtcInstant(effective_at.epoch_nanoseconds + index),
        )
        for index in range(1, 4)
    )
    buffer.require_covers_fills(fills[:2])
    with pytest.raises(ValueError, match="exceeds reservation bound"):
        buffer.require_covers_fills(fills)

    buy_buffer = reservation_buffer(side=OrderSide.BUY, effective_at=effective_at)
    assert (
        buy_buffer.tax_charge_rule.applicability
        is FeeReservationApplicability.NOT_APPLICABLE
    )
    with pytest.raises(ValueError, match="resolution context mismatch"):
        replace(buffer, tax_resolution=buy_buffer.tax_resolution)
    with pytest.raises(ValueError, match="positive integer"):
        reservation_buffer(
            side=OrderSide.SELL,
            effective_at=effective_at,
            maximum_fill_count=0,
        )


def test_historical_market_and_tax_policies_resolve_the_exact_transition() -> None:
    market = CnAShareCashMarketFeePolicy(_market_book())
    tax = CnAShareCashStampDutyTaxPolicy(_tax_book())

    old_market = market.assess_fees(_query(OrderSide.SELL, _instant(28, nanoseconds=-1)))
    new_market = market.assess_fees(_query(OrderSide.SELL, _instant(28)))
    buy_tax = tax.assess_taxes(_query(OrderSide.BUY, _instant(28)))
    sell_tax = tax.assess_taxes(_query(OrderSide.SELL, _instant(28)))

    assert market.component_ref.port_type is ProfilePortType.FEE_ASSESSMENT_POLICY
    assert tax.component_ref.port_type is ProfilePortType.TAX_POLICY
    assert old_market.result is not None
    assert new_market.result is not None
    assert buy_tax.result is not None
    assert sell_tax.result is not None

    assert old_market.result.reservation_charge_rules[0].rate == Rate(
        487, Scale(7), "fee_fraction"
    )
    assert new_market.result.reservation_charge_rules[0].rate == Rate(
        341, Scale(7), "fee_fraction"
    )
    assert len(new_market.result.reservation_charge_rules) == 3
    assert all(
        rule.basis is FeeReservationBasis.ORDER_NOTIONAL
        and rule.applicability is FeeReservationApplicability.APPLIES
        for rule in new_market.result.reservation_charge_rules
    )
    assert all(
        rule.source.value == FinalFeeRuleSource.MARKET_FEE.value
        and rule.basis_type is FeeBasisType.FILL
        and rule.applicability is FinalFeeApplicability.ALWAYS
        for rule in new_market.result.final_fill_charge_rules
    )
    assert buy_tax.result.reservation_charge_rule.applicability is FeeReservationApplicability.NOT_APPLICABLE
    assert sell_tax.result.reservation_charge_rule.applicability is FeeReservationApplicability.APPLIES
    assert sell_tax.result.final_fill_charge_rule.applicability is FinalFeeApplicability.SELL_ONLY
    assert sell_tax.result.final_fill_charge_rule.rate == Rate(5, Scale(4), "fee_fraction")


def test_fee_rule_failures_are_precedence_ordered_and_never_fall_back() -> None:
    market = CnAShareCashMarketFeePolicy(_market_book())
    unsupported = replace(
        _query(OrderSide.SELL, _instant(28)),
        instrument=_instrument("other"),
        trade_mechanism=CnAShareFeeTradeMechanism.BLOCK,
    )
    gap = _query(OrderSide.SELL, _instant(30))
    block = replace(
        _query(OrderSide.SELL, _instant(28)),
        trade_mechanism=CnAShareFeeTradeMechanism.BLOCK,
    )
    usd = CurrencyId("USD")
    currency = replace(
        _query(OrderSide.SELL, _instant(28)),
        instrument=replace(_instrument(), quote_currency=usd, settlement_currency=usd),
    )
    overlap = CnAShareCashMarketFeePolicy(_market_book(overlap=True)).assess_fees(
        _query(OrderSide.SELL, _instant(28))
    )

    unsupported_outcome = market.assess_fees(unsupported)
    block_outcome = market.assess_fees(block)
    currency_outcome = market.assess_fees(currency)
    gap_outcome = market.assess_fees(gap)
    assert unsupported_outcome.failure is not None
    assert unsupported_outcome.failure.code is CnAShareFeeRuleFailureCode.UNSUPPORTED_VENUE
    assert block_outcome.failure is not None
    assert block_outcome.failure.code is CnAShareFeeRuleFailureCode.UNSUPPORTED_TRADE_MECHANISM
    assert currency_outcome.failure is not None
    assert currency_outcome.failure.code is CnAShareFeeRuleFailureCode.UNSUPPORTED_CURRENCY
    assert gap_outcome.failure is not None
    assert gap_outcome.failure.code is CnAShareFeeRuleFailureCode.MISSING_RULE_INTERVAL
    assert overlap.failure is not None
    assert overlap.failure.code is CnAShareFeeRuleFailureCode.OVERLAPPING_RULE_INTERVALS


def test_resolution_identity_binds_full_query_and_active_band() -> None:
    market = CnAShareCashMarketFeePolicy(_market_book())
    query = _query(OrderSide.SELL, _instant(28))
    outcome = market.assess_fees(query)
    distinct_query = replace(
        query,
        instrument=replace(query.instrument, base_currency=CNY),
    )
    distinct = market.assess_fees(distinct_query)
    assert outcome.result is not None and distinct.result is not None
    assert outcome.result.query_hash != distinct.result.query_hash
    assert outcome.result.resolution_hash != distinct.result.resolution_hash

    with pytest.raises(ValueError, match="resolution identity"):
        replace(outcome.result, venue_id=VenueId("xshe"))
    with pytest.raises(ValueError, match="query context mismatch"):
        replace(
            outcome.result,
            instrument_id=InstrumentId(VenueId("xshg"), "600001"),
        )
    block_query = replace(query, trade_mechanism=CnAShareFeeTradeMechanism.BLOCK)
    with pytest.raises(ValueError, match="query context mismatch"):
        replace(
            outcome.result,
            query=block_query,
            query_hash=canonical_sha256(block_query),
        )
    with pytest.raises(ValueError, match="active market fee Band"):
        replace(outcome.result, active_band=_market_book().bands[0])
    with pytest.raises(ValueError, match="rule semantics"):
        replace(
            outcome.result,
            reservation_charge_rules=tuple(
                reversed(outcome.result.reservation_charge_rules)
            ),
        )


def test_rule_identity_text_must_be_trimmed_nfc() -> None:
    with pytest.raises(ValueError, match="canonical NFC"):
        CnAShareFeeRuleSourceRef(" source", "sha256:" + "1" * 64)
    with pytest.raises(ValueError, match="canonical NFC"):
        CnAShareMarketFeeRuleBook("e\u0301", 1, _market_book().bands)


def test_one_source_may_support_multiple_market_charge_components() -> None:
    book = _market_book()
    first = book.bands[0]
    shared = first.handling_source_refs
    market = CnAShareCashMarketFeePolicy(
        CnAShareMarketFeeRuleBook(
            book.rule_book_key,
            book.rule_book_version,
            (
                replace(
                    first,
                    regulatory_source_refs=shared,
                ),
                *book.bands[1:],
            ),
        )
    )

    outcome = market.assess_fees(
        _query(OrderSide.SELL, _instant(28, nanoseconds=-1))
    )
    assert outcome.result is not None


def test_resolution_construction_rejects_cross_source_rules() -> None:
    outcome = CnAShareCashMarketFeePolicy(_market_book()).assess_fees(
        _query(OrderSide.SELL, _instant(28))
    )
    assert outcome.result is not None
    rules = outcome.result.reservation_charge_rules

    with pytest.raises(ValueError, match="market fee resolution rule semantics"):
        replace(
            outcome.result,
            reservation_charge_rules=(
                replace(rules[0], source=FeeReservationRuleSource.TAX),
                *rules[1:],
            ),
        )


def test_partial_cancel_separates_reservation_fill_fees_and_order_minimum() -> None:
    effective_at = local_instant(28, 10)
    approval = market_rule_approval(
        quantity_units=1_000, side=OrderSide.SELL, effective_at=effective_at
    )
    estimate = FeeReservationEstimator().estimate(
        approval,
        reservation_rule_set(side=OrderSide.SELL, effective_at=effective_at),
        UtcInstant(effective_at.epoch_nanoseconds + 1),
    )
    stream = partial_cancelled_stream(
        quantity_units=1_000, side=OrderSide.SELL, effective_at=effective_at
    )
    order_basis = FeeAssessmentBasisEvidence.for_order(stream)
    fills = order_basis.fills
    engine = FeeAssessmentEngine()
    fill_results = []
    for index, value in enumerate(fills, start=4):
        outcome = engine.assess(
            basis=FeeAssessmentBasisEvidence.for_fill(value),
            rule_set=final_fill_rule_set(value),
            fee_assessment_id=domain_id(DomainIdKind.FEE, str(index)),
            assessment_time=UtcInstant(value.execution_time.epoch_nanoseconds + 1),
        )
        assert outcome.result is not None
        fill_results.append(outcome.result)
    order_outcome = engine.assess(
        basis=order_basis,
        rule_set=final_order_rule_set(
            side=OrderSide.SELL,
            effective_at=UtcInstant(effective_at.epoch_nanoseconds + 40),
        ),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "6"),
        assessment_time=UtcInstant(effective_at.epoch_nanoseconds + 50),
    )

    assert estimate.estimate is not None and estimate.proposal is not None
    accepted_reservation, partial_reservation, terminal_reservation = reservation_states(
        estimate.proposal, stream
    )
    expected_accepted_fee_reserve = (Money(1_068, Scale(2), "CNY"),)
    expected_partial_fee_reserve = (Money(900, Scale(2), "CNY"),)
    assert accepted_reservation.totals.fee_reserve == expected_accepted_fee_reserve
    assert partial_reservation.totals.fee_reserve == expected_partial_fee_reserve
    assert terminal_reservation.totals.is_empty
    assert estimate.estimate.total_fee == Money(1_068, Scale(2), "CNY")
    assert [value.assessment.amount for value in fill_results] == [
        Money(56, Scale(2), "CNY"),
        Money(56, Scale(2), "CNY"),
    ]
    assert order_outcome.result is not None
    assert order_outcome.result.assessment.amount == Money(500, Scale(2), "CNY")
    assert order_outcome.result.minimum_adjustments[0].amount == Money(
        440, Scale(2), "CNY"
    )
    assert estimate.estimate.total_fee.units - sum(
        value.assessment.amount.units for value in fill_results
    ) - order_outcome.result.assessment.amount.units == 456

    journal = AccountingJournal.empty()
    results = (*fill_results, order_outcome.result)
    for index, result in enumerate(results, start=7):
        translated = FeeChargedJournalTranslator().translate(
            result=result,
            cash_key=cash_key(),
            journal_entry_id=domain_id(DomainIdKind.JOURNAL, str(index)),
            recorded_at=SimulationInstant(
                UtcInstant(effective_at.epoch_nanoseconds + 100 + index),
                TimelinePhase(90, "fees"),
                SourceSequence(index),
            ),
        )
        assert translated.result is not None
        journal = journal.append(translated.result.journal_entry)
    assert journal.entry_count == 3
    assert journal.append_many(journal.entries) == journal


def test_two_fill_rounding_buffer_covers_per_fill_final_total() -> None:
    effective_at = local_instant(28, 10)
    approval = market_rule_approval(
        quantity_units=200, side=OrderSide.SELL, effective_at=effective_at
    )
    estimate = FeeReservationEstimator().estimate(
        approval,
        reservation_rule_set(side=OrderSide.SELL, effective_at=effective_at),
        UtcInstant(effective_at.epoch_nanoseconds + 1),
    )
    stream = filled_stream(
        quantity_units=200, side=OrderSide.SELL, effective_at=effective_at
    )
    basis = FeeAssessmentBasisEvidence.for_order(stream)
    engine = FeeAssessmentEngine()
    fill_total = 0
    for index, value in enumerate(basis.fills, start=1):
        outcome = engine.assess(
            basis=FeeAssessmentBasisEvidence.for_fill(value),
            rule_set=final_fill_rule_set(value),
            fee_assessment_id=domain_id(DomainIdKind.FEE, str(index)),
            assessment_time=UtcInstant(value.execution_time.epoch_nanoseconds + 1),
        )
        assert outcome.result is not None
        fill_total += outcome.result.assessment.amount.units
    order = engine.assess(
        basis=basis,
        rule_set=final_order_rule_set(
            side=OrderSide.SELL,
            effective_at=UtcInstant(effective_at.epoch_nanoseconds + 20),
        ),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "3"),
        assessment_time=UtcInstant(effective_at.epoch_nanoseconds + 30),
    )

    assert estimate.estimate is not None
    assert estimate.estimate.total_fee == Money(617, Scale(2), "CNY")
    assert fill_total == 112
    assert order.result is not None
    assert order.result.assessment.amount == Money(500, Scale(2), "CNY")
    assert fill_total + order.result.assessment.amount.units == 612
    assert estimate.estimate.total_fee.units >= 612


def test_rounding_buffer_covers_an_adversarial_two_fill_partition() -> None:
    effective_at = local_instant(28, 10)
    approval = market_rule_approval(
        quantity_units=600,
        side=OrderSide.SELL,
        effective_at=effective_at,
    )
    estimate = FeeReservationEstimator().estimate(
        approval,
        reservation_rule_set(side=OrderSide.SELL, effective_at=effective_at),
        UtcInstant(effective_at.epoch_nanoseconds + 1),
    )
    stream = filled_stream(
        quantity_units=600,
        side=OrderSide.SELL,
        effective_at=effective_at,
        fill_quantities=(200, 400),
    )
    basis = FeeAssessmentBasisEvidence.for_order(stream)
    reservation_buffer(
        side=OrderSide.SELL, effective_at=effective_at
    ).require_covers_fills(basis.fills)
    engine = FeeAssessmentEngine()
    final_units = 0
    for index, value in enumerate(basis.fills, start=1):
        outcome = engine.assess(
            basis=FeeAssessmentBasisEvidence.for_fill(value),
            rule_set=final_fill_rule_set(value),
            fee_assessment_id=domain_id(DomainIdKind.FEE, str(index)),
            assessment_time=UtcInstant(value.execution_time.epoch_nanoseconds + 1),
        )
        assert outcome.result is not None
        final_units += outcome.result.assessment.amount.units
    order = engine.assess(
        basis=basis,
        rule_set=final_order_rule_set(
            side=OrderSide.SELL,
            effective_at=UtcInstant(effective_at.epoch_nanoseconds + 20),
        ),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "3"),
        assessment_time=UtcInstant(effective_at.epoch_nanoseconds + 30),
    )
    assert estimate.estimate is not None and order.result is not None
    final_units += order.result.assessment.amount.units
    assert estimate.estimate.total_fee == Money(842, Scale(2), "CNY")
    assert estimate.estimate.total_fee.units - 4 == 838
    assert final_units == 839
    assert estimate.estimate.total_fee.units >= final_units


def test_side_and_execution_time_select_tax_and_historical_band() -> None:
    old_at = local_instant(25, 10)
    new_at = local_instant(28, 10)
    estimates = []
    for side, effective_at in (
        (OrderSide.SELL, old_at),
        (OrderSide.SELL, new_at),
        (OrderSide.BUY, new_at),
    ):
        approval = market_rule_approval(
            quantity_units=1_000, side=side, effective_at=effective_at
        )
        outcome = FeeReservationEstimator().estimate(
            approval,
            reservation_rule_set(side=side, effective_at=effective_at),
            UtcInstant(effective_at.epoch_nanoseconds + 1),
        )
        assert outcome.estimate is not None
        estimates.append(outcome.estimate.total_fee)
    assert estimates == [
        Money(1_583, Scale(2), "CNY"),
        Money(1_068, Scale(2), "CNY"),
        Money(567, Scale(2), "CNY"),
    ]

    accepted_old = source_order(
        quantity_units=1_000, side=OrderSide.SELL, effective_at=old_at
    )
    filled_new = fill(
        accepted_old,
        "b",
        UtcInstant(new_at.epoch_nanoseconds + 10),
    )
    final = FeeAssessmentEngine().assess(
        basis=FeeAssessmentBasisEvidence.for_fill(filled_new),
        rule_set=final_fill_rule_set(filled_new),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "b"),
        assessment_time=UtcInstant(filled_new.execution_time.epoch_nanoseconds + 1),
    )
    assert final.result is not None
    assert final.result.assessment.amount == Money(56, Scale(2), "CNY")


def test_venues_share_rates_but_keep_distinct_rule_evidence() -> None:
    market, tax = policies()
    at = local_instant(28, 10)
    sh_market = market.assess_fees(
        fee_query(OrderSide.SELL, at, venue="xshg")
    )
    sz_market = market.assess_fees(
        fee_query(OrderSide.SELL, at, venue="xshe")
    )
    sh_tax = tax.assess_taxes(fee_query(OrderSide.SELL, at, venue="xshg"))
    sz_tax = tax.assess_taxes(fee_query(OrderSide.SELL, at, venue="xshe"))
    assert sh_market.result is not None and sz_market.result is not None
    assert sh_tax.result is not None and sz_tax.result is not None
    assert tuple(rule.rate for rule in sh_market.result.reservation_charge_rules) == tuple(
        rule.rate for rule in sz_market.result.reservation_charge_rules
    )
    assert sh_market.result.active_band_hash != sz_market.result.active_band_hash
    assert sh_market.result.resolution_hash != sz_market.result.resolution_hash
    assert sh_tax.result.final_fill_charge_rule.rate == sz_tax.result.final_fill_charge_rule.rate
    assert sh_tax.result.active_band_hash != sz_tax.result.active_band_hash


def test_rule_book_input_order_does_not_change_component_or_resolution() -> None:
    market, tax = policies()
    at = local_instant(28, 10)
    reversed_market = CnAShareCashMarketFeePolicy(
        CnAShareMarketFeeRuleBook(
            market.rule_book.rule_book_key,
            market.rule_book.rule_book_version,
            tuple(reversed(market.rule_book.bands)),
        )
    )
    reversed_tax = CnAShareCashStampDutyTaxPolicy(
        CnAShareStampDutyRuleBook(
            tax.rule_book.rule_book_key,
            tax.rule_book.rule_book_version,
            tuple(reversed(tax.rule_book.bands)),
        )
    )
    query = fee_query(OrderSide.SELL, at)

    assert reversed_market.component_ref == market.component_ref
    assert reversed_tax.component_ref == tax.component_ref
    assert reversed_market.assess_fees(query) == market.assess_fees(query)
    assert reversed_tax.assess_taxes(query) == tax.assess_taxes(query)


def test_unfilled_cancel_has_zero_final_commission_and_no_minimum() -> None:
    effective_at = local_instant(28, 10)
    stream = unfilled_cancelled_stream(
        side=OrderSide.SELL, effective_at=effective_at
    )
    outcome = FeeAssessmentEngine().assess(
        basis=FeeAssessmentBasisEvidence.for_order(stream),
        rule_set=final_order_rule_set(
            side=OrderSide.SELL,
            effective_at=UtcInstant(effective_at.epoch_nanoseconds + 20),
        ),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "a"),
        assessment_time=UtcInstant(effective_at.epoch_nanoseconds + 30),
    )

    assert outcome.result is not None
    assert outcome.result.assessment.amount == Money(0, Scale(2), "CNY")
    assert not outcome.result.minimum_adjustments
