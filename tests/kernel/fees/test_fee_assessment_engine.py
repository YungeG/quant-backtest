from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from crypto_quant_domain import (
    AccountingEntryType,
    CurrencyId,
    DomainIdKind,
    FeeBasisType,
    Money,
    OrderEventType,
    OrderSide,
    Rate,
    Scale,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal,
    FeeAssessmentBasisEvidence,
    FeeAssessmentEngine,
    FeeChargedJournalFailureCode,
    FeeChargedJournalTranslator,
    FinalFeeApplicability,
    FinalFeeAssessmentFailureCode,
    FinalFeeCalculationBasis,
    FinalFeeRuleSource,
    OrderEventRecord,
    OrderEventStream,
)
from tests.kernel.orders._fixtures import event, full_lifecycle_records, order

from ._fixtures import (
    assessment_time,
    cash_key,
    charge_rule,
    domain_id,
    fill_basis,
    filled_stream,
    order_basis,
    recorded_at,
    rule_set,
    session_basis,
)


def test_fill_basis_maker_taker_and_sell_only_tax_are_explicit() -> None:
    engine = FeeAssessmentEngine()

    buy = engine.assess(
        basis=fill_basis(side=OrderSide.BUY),
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "4"),
        assessment_time=assessment_time(),
    )
    sell = engine.assess(
        basis=fill_basis(side=OrderSide.SELL),
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "5"),
        assessment_time=assessment_time(),
    )

    assert buy.failure is None
    assert buy.result is not None
    assert buy.result.assessment.basis_type is FeeBasisType.FILL
    assert buy.result.assessment.amount == Money(10, Scale(2), "USD")
    expected_buy_lines = (10, 0, 0)
    assert tuple(line.amount.units for line in buy.result.lines) == expected_buy_lines

    assert sell.result is not None
    assert sell.result.assessment.amount == Money(15, Scale(2), "USD")
    expected_sell_lines = (10, 5, 0)
    assert tuple(line.amount.units for line in sell.result.lines) == expected_sell_lines


def test_maker_and_taker_rules_are_selected_from_fill_liquidity_evidence() -> None:
    rules = rule_set()
    market_fill = next(
        rule
        for rule in rules.charge_rules
        if rule.source is FinalFeeRuleSource.MARKET_FEE
        and rule.basis_type is FeeBasisType.FILL
    )
    maker_rule = replace(
        market_fill,
        applicability=FinalFeeApplicability.MAKER_ONLY,
        rate=Rate(8, Scale(4), "fee_fraction"),
    )
    maker_rules = rule_set(
        rules=tuple(
            maker_rule if rule.rule_id == market_fill.rule_id else rule
            for rule in rules.charge_rules
        )
    )

    outcome = FeeAssessmentEngine().assess(
        basis=fill_basis(liquidity="maker"),
        rule_set=maker_rules,
        fee_assessment_id=domain_id(DomainIdKind.FEE, "0"),
        assessment_time=assessment_time(),
    )

    assert outcome.result is not None
    assert outcome.result.assessment.amount == Money(8, Scale(2), "USD")


def test_order_minimum_is_charged_once_on_actual_terminal_fill_basis() -> None:
    basis = order_basis()
    engine = FeeAssessmentEngine()

    first = engine.assess(
        basis=basis,
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "6"),
        assessment_time=assessment_time(),
    )
    second = engine.assess(
        basis=basis,
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "6"),
        assessment_time=assessment_time(),
    )

    assert first == second
    assert first.result is not None
    assert first.result.assessment.amount == Money(500, Scale(2), "USD")
    assert len(first.result.minimum_adjustments) == 1
    assert first.result.minimum_adjustments[0].amount == Money(490, Scale(2), "USD")
    assert first.result.basis.fills == tuple(
        record.fill for record in basis.order_streams[0].records if record.fill is not None
    )


def test_session_flat_fee_uses_explicit_closure_and_is_order_independent() -> None:
    first_basis = session_basis()
    second_basis = replace(
        first_basis, order_streams=tuple(reversed(first_basis.order_streams))
    )
    engine = FeeAssessmentEngine()

    first = engine.assess(
        basis=first_basis,
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "7"),
        assessment_time=assessment_time(),
    )
    second = engine.assess(
        basis=second_basis,
        rule_set=rule_set(rules=tuple(reversed(rule_set().charge_rules))),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "7"),
        assessment_time=assessment_time(),
    )
    duplicated_basis = replace(
        first_basis,
        order_streams=first_basis.order_streams + first_basis.order_streams,
    )
    duplicated = engine.assess(
        basis=duplicated_basis,
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "7"),
        assessment_time=assessment_time(),
    )

    assert first == second == duplicated
    assert first.result is not None
    assert first.result.assessment.amount == Money(200, Scale(2), "USD")


def test_incomplete_and_ambiguous_basis_fail_without_partial_assessment() -> None:
    subject = order()
    incomplete_stream = OrderEventStream.from_records(
        subject, full_lifecycle_records(subject)[:8]
    )
    incomplete_basis = order_basis()
    incomplete_basis = replace(incomplete_basis, order_streams=(incomplete_stream,))

    incomplete = FeeAssessmentEngine().assess(
        basis=incomplete_basis,
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "8"),
        assessment_time=assessment_time(),
    )
    duplicate_stream = filled_stream()
    duplicate_subject = duplicate_stream.order
    duplicate_records = full_lifecycle_records(duplicate_subject)
    cancel_requested = OrderEventRecord(
        event(
            duplicate_subject,
            "fee-basis-cancel-requested",
            OrderEventType.ORDER_CANCEL_REQUESTED,
            90,
            duplicate_records[7].event.event_id,
        )
    )
    cancelled = OrderEventRecord(
        event(
            duplicate_subject,
            "fee-basis-cancelled",
            OrderEventType.ORDER_CANCELLED,
            100,
            cancel_requested.event.event_id,
        )
    )
    conflicting_stream = OrderEventStream.from_records(
        duplicate_subject, duplicate_records[:8] + (cancel_requested, cancelled)
    )
    ambiguous_basis = replace(
        session_basis(), order_streams=(duplicate_stream, conflicting_stream)
    )
    ambiguous = FeeAssessmentEngine().assess(
        basis=ambiguous_basis,
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "9"),
        assessment_time=assessment_time(),
    )

    assert incomplete.result is None
    assert incomplete.failure is not None
    expected_incomplete_codes = (
        FinalFeeAssessmentFailureCode.INCOMPLETE_BASIS,
    )
    assert incomplete.failure.codes == expected_incomplete_codes
    assert ambiguous.result is None
    assert ambiguous.failure is not None
    expected_ambiguous_codes = (
        FinalFeeAssessmentFailureCode.AMBIGUOUS_BASIS,
    )
    assert ambiguous.failure.codes == expected_ambiguous_codes


def test_missing_liquidity_unknown_rule_and_missing_source_fail_closed() -> None:
    no_liquidity = FeeAssessmentEngine().assess(
        basis=fill_basis(liquidity=None),
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "a"),
        assessment_time=assessment_time(),
    )
    assert no_liquidity.failure is not None
    expected_liquidity_codes = (
        FinalFeeAssessmentFailureCode.LIQUIDITY_ROLE_MISSING,
    )
    assert no_liquidity.failure.codes == expected_liquidity_codes

    rules = rule_set()
    unknown_rule = replace(
        rules.charge_rules[0],
        calculation_basis=FinalFeeCalculationBasis.UNKNOWN,
        rate=None,
    )
    unknown = FeeAssessmentEngine().assess(
        basis=fill_basis(),
        rule_set=rule_set(
            rules=(unknown_rule,) + rules.charge_rules[1:],
            minimums=rules.minimums,
        ),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "b"),
        assessment_time=assessment_time(),
    )
    assert unknown.failure is not None
    assert FinalFeeAssessmentFailureCode.UNKNOWN_CALCULATION_BASIS in unknown.failure.codes

    fill_market = next(
        rule
        for rule in rules.charge_rules
        if rule.source is FinalFeeRuleSource.MARKET_FEE
        and rule.basis_type is FeeBasisType.FILL
    )
    unknown_applicability_rule = replace(
        fill_market, applicability=FinalFeeApplicability.UNKNOWN
    )
    unknown_applicability = FeeAssessmentEngine().assess(
        basis=fill_basis(),
        rule_set=rule_set(
            rules=tuple(
                unknown_applicability_rule
                if rule.rule_id == fill_market.rule_id
                else rule
                for rule in rules.charge_rules
            )
        ),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "0"),
        assessment_time=assessment_time(),
    )
    assert unknown_applicability.failure is not None
    assert FinalFeeAssessmentFailureCode.UNKNOWN_APPLICABILITY in (
        unknown_applicability.failure.codes
    )

    missing_market = FeeAssessmentEngine().assess(
        basis=fill_basis(),
        rule_set=rule_set(
            rules=tuple(
                rule
                for rule in rules.charge_rules
                if not (
                    rule.basis_type is FeeBasisType.FILL
                    and rule.source is FinalFeeRuleSource.MARKET_FEE
                )
            ),
            minimums=rules.minimums,
        ),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "c"),
        assessment_time=assessment_time(),
    )
    assert missing_market.failure is not None
    expected_missing_source_codes = (
        FinalFeeAssessmentFailureCode.MISSING_RULE_SOURCE,
    )
    assert missing_market.failure.codes == expected_missing_source_codes


def test_unfilled_cancelled_order_does_not_activate_notional_minimum() -> None:
    subject = order()
    records = full_lifecycle_records(subject)
    cancel_requested = OrderEventRecord(
        event(
            subject,
            "unfilled-cancel-requested",
            OrderEventType.ORDER_CANCEL_REQUESTED,
            90,
            records[7].event.event_id,
        )
    )
    cancelled = OrderEventRecord(
        event(
            subject,
            "unfilled-cancelled",
            OrderEventType.ORDER_CANCELLED,
            100,
            cancel_requested.event.event_id,
        )
    )
    stream = OrderEventStream.from_records(
        subject, records[:8] + (cancel_requested, cancelled)
    )
    outcome = FeeAssessmentEngine().assess(
        basis=FeeAssessmentBasisEvidence.for_order(stream),
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "2"),
        assessment_time=assessment_time(),
    )

    assert outcome.result is not None
    assert outcome.result.assessment.amount == Money(0, Scale(2), "USD")
    assert not outcome.result.minimum_adjustments


def test_fee_charged_translation_references_every_rule_and_is_journal_idempotent() -> None:
    assessment = FeeAssessmentEngine().assess(
        basis=order_basis(),
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "d"),
        assessment_time=assessment_time(),
    )
    assert assessment.result is not None

    first = FeeChargedJournalTranslator().translate(
        result=assessment.result,
        cash_key=cash_key(),
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "e"),
        recorded_at=recorded_at(),
    )
    second = FeeChargedJournalTranslator().translate(
        result=assessment.result,
        cash_key=cash_key(),
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "e"),
        recorded_at=recorded_at(),
    )

    assert first == second
    assert first.failure is None
    assert first.result is not None
    entry = first.result.journal_entry
    assert entry.entry_type is AccountingEntryType.FEE_CHARGED
    assert entry.balance_changes[0].value == Money(-500, Scale(2), "USD")
    expected_fees = (Money(500, Scale(2), "USD"),)
    assert entry.fees == expected_fees
    assert assessment.result.assessment.fee_assessment_id.value in entry.source_ids
    for rule_id in assessment.result.rule_identity_ids:
        assert rule_id in entry.source_ids

    once = AccountingJournal.empty().append(entry)
    twice = once.append(entry)
    assert twice is once
    assert twice.entry_count == 1


def test_zero_fee_and_cash_context_mismatch_do_not_create_journal_entries() -> None:
    zero = FeeAssessmentEngine().assess(
        basis=fill_basis(liquidity="maker"),
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "3"),
        assessment_time=assessment_time(),
    )
    assert zero.result is not None
    zero_journal = FeeChargedJournalTranslator().translate(
        result=zero.result,
        cash_key=cash_key(),
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "3"),
        recorded_at=recorded_at(),
    )
    assert zero_journal.failure is not None
    assert zero_journal.failure.code is FeeChargedJournalFailureCode.NON_POSITIVE_FEE
    assert zero_journal.result is None

    positive = FeeAssessmentEngine().assess(
        basis=order_basis(),
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "4"),
        assessment_time=assessment_time(),
    )
    assert positive.result is not None
    wrong_cash = replace(cash_key(), currency_id=CurrencyId("EUR"))
    mismatch = FeeChargedJournalTranslator().translate(
        result=positive.result,
        cash_key=wrong_cash,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "4"),
        recorded_at=recorded_at(),
    )
    assert mismatch.failure is not None
    assert mismatch.failure.code is FeeChargedJournalFailureCode.CASH_CONTEXT_MISMATCH
    assert mismatch.result is None


def test_sell_only_and_minimum_semantics_cannot_be_silently_rewritten() -> None:
    rules = rule_set()
    tax_fill = next(
        rule
        for rule in rules.charge_rules
        if rule.source is FinalFeeRuleSource.TAX
        and rule.basis_type is FeeBasisType.FILL
    )
    assert tax_fill.applicability is FinalFeeApplicability.SELL_ONLY

    buy = FeeAssessmentEngine().assess(
        basis=fill_basis(side=OrderSide.BUY),
        rule_set=rules,
        fee_assessment_id=domain_id(DomainIdKind.FEE, "f"),
        assessment_time=assessment_time(),
    )
    assert buy.result is not None
    tax_line = next(
        line
        for line in buy.result.lines
        if line.rule.source is FinalFeeRuleSource.TAX
    )
    assert tax_line.amount.units == 0
    assert not tax_line.applicable_fill_ids


def test_forged_final_assessment_result_is_rejected() -> None:
    outcome = FeeAssessmentEngine().assess(
        basis=order_basis(),
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "0"),
        assessment_time=assessment_time(),
    )
    assert outcome.result is not None

    with pytest.raises(ValueError, match="minimum adjustments"):
        replace(outcome.result, minimum_adjustments=())
    with pytest.raises(ValueError, match="total or rule identity"):
        replace(
            outcome.result,
            assessment=replace(
                outcome.result.assessment,
                amount=Money(499, Scale(2), "USD"),
            ),
        )


def test_rule_basis_and_closure_values_are_immutable_and_hash_checked() -> None:
    rules = rule_set()
    basis = session_basis()

    with pytest.raises(FrozenInstanceError):
        rules.assessment_scale = Scale(3)  # type: ignore[misc]
    with pytest.raises(ValueError, match="config_hash mismatch"):
        replace(rules, config_hash="sha256:" + "0" * 64)
    assert basis.closure_ref is not None
    with pytest.raises(ValueError, match="closure_hash mismatch"):
        replace(basis.closure_ref, closure_hash="sha256:" + "0" * 64)

    assert canonical_sha256(rules) == rules.rule_set_hash
    assert canonical_sha256(basis) == basis.basis_hash


def test_assessment_before_closed_basis_is_structured_failure() -> None:
    outcome = FeeAssessmentEngine().assess(
        basis=session_basis(),
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "1"),
        assessment_time=UtcInstant(199),
    )
    assert outcome.failure is not None
    expected_codes = (
        FinalFeeAssessmentFailureCode.ASSESSMENT_BEFORE_BASIS_CLOSED,
    )
    assert outcome.failure.codes == expected_codes
