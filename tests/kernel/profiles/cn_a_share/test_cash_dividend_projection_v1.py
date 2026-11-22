from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import pytest
import crypto_quant_domain as d
from crypto_quant_trading import AccountingJournal, CurrencyValuationGraph
from crypto_quant_trading.profiles.cn_a_share import cash_dividend_projection_v1 as projection_module
from crypto_quant_trading.profiles.cn_a_share.portfolio_economic_v1 import (
    CnAShareCashDividendClaimV1, CnAShareCashDividendStateV1,
    CnAShareEconomicProjectionFailureCodeV1 as Code,
    CnASharePortfolioEconomicProjectionInputsV1,
    project_cn_a_share_portfolio_economic_state_v1 as project,
)
from tests.runtime.providers.test_cn_a_share_portfolio_standard_native_state_v1 import _live_prefix


def _at(instant, rank=160, sequence=0):
    return d.SimulationInstant(instant, d.TimelinePhase(rank, "cn_economic_native"), d.SourceSequence(sequence))


def _inputs():
    source, batch, settled, streams, schedules, rules = _live_prefix()
    marks = source.signal_marks[1]
    return CnASharePortfolioEconomicProjectionInputsV1(
        batch.journal, source.scope.ledger_schema, settled, tuple(sorted(streams, key=lambda s: s.order.order_id.value)),
        tuple(sorted(schedules, key=lambda s: s.order_id.value)), rules,
        source.scope.instrument_catalog, marks.marks,
        CurrencyValuationGraph(marks.at.instant, d.PricePurpose.VALUATION, ()),
        source.notional_quantization, CnAShareCashDividendStateV1(source.scope.account_id, marks.at, ()), marks.at)


def _claim(inputs, *, gross=10000, paid=0, tax=2000, settled=0):
    end = inputs.as_of.instant.epoch_nanoseconds
    clocks = tuple(_at(d.UtcInstant(end - 50 + i * 10), rank) for i, rank in enumerate((150, 10, 151, 152)))
    mode = "KNOWN_AMOUNT" if tax else "KNOWN_ZERO"
    events = [("REGISTER", "register", clocks[0], d.canonical_sha256("register")),
              ("ENTITLE", "entitle", clocks[1], d.canonical_sha256("entitle"))]
    if paid:
        events.append(("PAY", "pay", clocks[2], d.canonical_sha256("pay")))
    if settled:
        events.append(("TAX", "tax", clocks[3], d.canonical_sha256("tax")))
    return CnAShareCashDividendClaimV1(inputs.market_rules.account_id, "declared-action",
        inputs.instrument_catalog.instruments[0].instrument_id, d.canonical_sha256("terms"),
        d.canonical_sha256("policy"), inputs.journal.journal_hash,
        clocks[0], clocks[1], clocks[2], 100, mode, clocks[3] if tax else None,
        d.Money(gross, d.Scale(2), "CNY"), d.Money(paid, d.Scale(2), "CNY"),
        d.Money(tax, d.Scale(2), "CNY"), d.Money(settled, d.Scale(2), "CNY"), tuple(events))


def test_empty_state_is_exact_native_snapshot_and_stable_proof():
    inputs = _inputs()
    outcome = project(inputs)
    assert outcome.failure is None
    p = outcome.projection
    assert p is not None
    assert d.canonical_bytes(p.snapshot) == d.canonical_bytes(p.base_snapshot)
    assert p.native_source_hash == d.canonical_sha256(inputs)
    assert p.dividend_state_hash == d.canonical_sha256(inputs.dividend_state)
    assert p.projection_hash == d.canonical_sha256(p)
    assert p == project(inputs).projection
    assert sum(r.native_available.units for r in p.cash_rows) == p.spendable.units == p.buy_budget.units


@pytest.mark.parametrize(("gross", "paid", "tax", "settled"), [
    (10000, 0, 0, 0), (10000, 10000, 0, 0), (10000, 0, 2000, 0),
    (10000, 10000, 2000, 0), (10000, 10000, 2000, 2000),
])
def test_receivable_and_tax_are_separate_from_native_cash(gross, paid, tax, settled):
    inputs = _inputs()
    claim = _claim(inputs, gross=gross, paid=paid, tax=tax, settled=settled)
    inputs = replace(inputs, dividend_state=replace(inputs.dividend_state, claims=(claim,)))
    p = project(inputs).projection
    assert p is not None
    assert p.gross_receivable.units == gross - paid
    assert p.tax_liability.units == tax - settled
    assert p.snapshot.equity.units == p.base_snapshot.equity.units + gross - paid - tax + settled
    assert d.canonical_bytes(replace(p.snapshot, equity=p.base_snapshot.equity)) == d.canonical_bytes(p.base_snapshot)
    assert sum(r.tax_hold.units for r in p.cash_rows) == tax - settled
    assert p.spendable.units == sum(r.native_available.units for r in p.cash_rows) - tax + settled
    # This is a shape/projection test, not C-A authentication of the declared claim.
    assert not hasattr(p, "source_qualification_verified")


def test_cross_venue_tax_shortfall_blocks_account_buy_budget_without_spending_receivable():
    inputs = _inputs()
    sh = next(r.key for r in inputs.ledger_schema.cash_registrations if r.key.venue_id.value == "xshg")
    from crypto_quant_trading import GenericLedger
    available = GenericLedger(inputs.ledger_schema).project(inputs.journal).cash_amount(sh).units
    claim = replace(_claim(inputs), instrument_id=next(i.instrument_id for i in inputs.instrument_catalog.instruments if i.instrument_id.venue == sh.venue_id),
                    recognized_gross=d.Money(available + 2000, d.Scale(2), "CNY"),
                    tax_assessed=d.Money(available + 1000, d.Scale(2), "CNY"))
    p = project(replace(inputs, dividend_state=replace(inputs.dividend_state, claims=(claim,)))).projection
    assert p is not None and p.tax_shortfall.units == 1000 and p.buy_budget.units == 0
    assert p.spendable.units > 0  # Other venue cash is not automatically moved to pay tax.
    row = next(r for r in p.cash_rows if r.key == sh)
    assert row.tax_hold.units == available and row.spendable.units == 0
    with pytest.raises(ValueError, match="buy budget"):
        replace(p, buy_budget=p.spendable)


def test_projection_failure_precedence_and_same_utc_future_phase():
    inputs = _inputs()
    future = replace(inputs.as_of, phase=d.TimelinePhase(inputs.as_of.phase.rank + 1, "future"))
    marks = tuple(replace(m, resolved_at_instant=future) for m in inputs.marks)
    older_state = replace(inputs.dividend_state, as_of=replace(inputs.as_of, source_sequence=d.SourceSequence(0)))
    invalid = replace(inputs, marks=marks, dividend_state=older_state)
    assert project(invalid).failure.code is Code.FUTURE_NATIVE_FACT
    wrong = replace(invalid, dividend_state=replace(older_state, account_id="foreign.account"))
    assert project(wrong).failure.code is Code.CONTEXT_MISMATCH
    old_clock = _at(d.UtcInstant(inputs.as_of.instant.epoch_nanoseconds - 1))
    assert project(replace(inputs, dividend_state=replace(inputs.dividend_state, as_of=old_clock))).failure.code is Code.DIVIDEND_STATE_MISMATCH
    missing = project(replace(inputs, marks=inputs.marks[:-1]))
    assert missing.failure.code is Code.NATIVE_SNAPSHOT_REJECTED
    assert missing.failure.native_snapshot_failure is not None


def _overcommitted(inputs):
    from crypto_quant_trading import GenericLedger
    key = inputs.ledger_schema.cash_registrations[0].key
    cash = GenericLedger(inputs.ledger_schema).project(inputs.journal).cash_amount(key)
    at = _at(d.UtcInstant(inputs.as_of.instant.epoch_nanoseconds - 1))
    debit = d.AccountingJournalEntry(d.DomainId(d.DomainIdKind.JOURNAL, "jnl_" + "e" * 64),
        d.AccountingEntryType.CAPITAL_WITHDRAWN, inputs.market_rules.account_id, key.venue_id,
        at.instant, at, ("test-overcommit",), (d.BalanceChange(key, d.Money(-cash.units - 1, d.Scale(2), "CNY")),), (), (), ())
    return replace(inputs, journal=inputs.journal.append(debit), marks=inputs.marks[:-1])


def test_negative_venue_native_cash_is_not_clipped_or_hidden_by_other_venue():
    result = project(_overcommitted(_inputs()))
    assert result.failure.code is Code.NATIVE_CASH_OVERCOMMITTED


def test_exact_shapes_reject_bool_partial_hash_float_and_unsorted_inputs():
    inputs = _inputs()
    claim = _claim(inputs)
    with pytest.raises(TypeError):
        replace(claim, entitled_quantity=True)
    with pytest.raises(ValueError):
        replace(claim, action_terms_hash="a" * 64)
    with pytest.raises(ValueError):
        replace(claim, gross_paid=d.Money(1, d.Scale(2), "CNY"))
    with pytest.raises(ValueError):
        replace(inputs, marks=tuple(reversed(inputs.marks)))
    with pytest.raises(TypeError):
        replace(inputs, marks=list(inputs.marks))
    with pytest.raises(TypeError):
        replace(inputs, marks=tuple(replace(m, available_at_instant=None, resolved_at_instant=None) for m in inputs.marks))
    with pytest.raises(ValueError):
        replace(inputs.dividend_state, claims=(replace(claim, account_id="other"),))


def test_projection_inputs_bind_complete_populated_book_and_valid_prefix():
    inputs = _inputs()
    book = inputs.settlement_book
    assert book.obligations and len(book.events) > len(book.obligations)
    body = inputs.to_canonical_dict()["settlement_book"]
    assert body == {"type": "cn_portfolio_development_settlement_book_source",
        "schema_version": 1, "account_id": book.account_id, "book_hash": book.book_hash,
        "obligations": book.obligations, "events": book.events}
    original_hash = d.canonical_sha256(inputs)
    assert original_hash == d.canonical_sha256(inputs)
    prefix = replace(book, events=book.events[:-1])
    changed = replace(inputs, settlement_book=prefix)
    assert d.canonical_sha256(changed) != original_hash
    assert project(inputs).projection.native_source_hash == original_hash
    assert project(changed).projection.native_source_hash == d.canonical_sha256(changed)


def test_native_exception_is_not_converted_to_projection_failure(monkeypatch):
    inputs = _inputs()
    from crypto_quant_trading import GenericLedger
    def broken(*args, **kwargs):
        raise OSError("native ledger I/O sentinel")
    monkeypatch.setattr(GenericLedger, "project", broken)
    with pytest.raises(OSError, match="native ledger"):
        project(inputs)


def test_scoped_projector_reuses_only_identical_stable_fields(monkeypatch):
    inputs = _inputs()
    scope = CnASharePortfolioEconomicProjectionInputsV1.scoped_projector()
    chunks = []

    class RecordingDigest:
        def __init__(self, initial):
            self.body = bytearray(initial)

        def update(self, chunk):
            self.body.extend(chunk)

        def hexdigest(self):
            chunks.append(bytes(self.body))
            return sha256(self.body).hexdigest()

    monkeypatch.setattr(projection_module, "sha256", RecordingDigest)
    assert scope.__self__ is not CnASharePortfolioEconomicProjectionInputsV1.scoped_projector().__self__
    assert d.canonical_bytes(scope(inputs)) == d.canonical_bytes(project(inputs))
    entries = scope.__self__._encoded.copy()
    rebuilt = replace(inputs, order_streams=tuple(list(inputs.order_streams)),
                      reservation_schedules=tuple(list(inputs.reservation_schedules)))
    assert rebuilt.order_streams is not inputs.order_streams
    assert d.canonical_bytes(scope(rebuilt)) == d.canonical_bytes(project(rebuilt))
    for field in ("order_streams", "reservation_schedules"):
        assert scope.__self__._encoded[field][1] is entries[field][1]

    equal_book = replace(rebuilt, settlement_book=replace(rebuilt.settlement_book))
    assert d.canonical_bytes(scope(equal_book)) == d.canonical_bytes(project(equal_book))
    assert scope.__self__._encoded["settlement_book"][0] is equal_book.settlement_book
    assert scope.__self__._encoded["settlement_book"][1] is not entries["settlement_book"][1]

    changed = replace(rebuilt, journal=AccountingJournal(rebuilt.journal.entries),
                      settlement_book=replace(rebuilt.settlement_book, events=rebuilt.settlement_book.events[:-1]),
                      order_streams=(replace(rebuilt.order_streams[0]), *rebuilt.order_streams[1:]),
                      reservation_schedules=(replace(rebuilt.reservation_schedules[0]),
                                             *rebuilt.reservation_schedules[1:]),
                      dividend_state=replace(rebuilt.dividend_state, claims=(_claim(rebuilt),)))
    assert d.canonical_bytes(scope(changed)) == d.canonical_bytes(project(changed))
    assert chunks == [d.canonical_bytes(value) for value in (inputs, rebuilt, equal_book, changed)]
    for field in ("journal", "settlement_book", "order_streams", "reservation_schedules"):
        value, encoded = scope.__self__._encoded[field]
        assert value is getattr(changed, field)
        assert encoded is not entries[field][1]
    assert not scope.__self__._same_source(rebuilt.order_streams, tuple(reversed(rebuilt.order_streams)))


def test_scoped_projector_drops_bytes_over_budget(monkeypatch):
    inputs = _inputs()
    scope = CnASharePortfolioEconomicProjectionInputsV1.scoped_projector()
    expected = d.canonical_bytes(project(inputs))
    assert d.canonical_bytes(scope(inputs)) == expected
    assert scope.__self__._encoded
    monkeypatch.setattr(scope.__self__, "_byte_limit", 0)
    assert d.canonical_bytes(scope(inputs)) == expected
    assert not scope.__self__._encoded


@pytest.mark.parametrize("error_type", (d.CanonicalizationError, TypeError))
def test_scoped_projector_falls_back_to_authoritative_encoding_error(monkeypatch, error_type):
    inputs = _inputs()
    scope = CnASharePortfolioEconomicProjectionInputsV1.scoped_projector()
    scope(inputs)
    stable = projection_module.canonical_bytes
    journal = AccountingJournal(inputs.journal.entries)
    changed = replace(inputs, journal=journal)
    direct = projection_module.canonical_sha256

    def split(value):
        if value is journal:
            raise error_type("part-only error")
        return stable(value)

    def full(value):
        if value is changed:
            raise d.CanonicalizationError("authority error at $/journal")
        return direct(value)

    monkeypatch.setattr(projection_module, "canonical_bytes", split)
    monkeypatch.setattr(projection_module, "canonical_sha256", full)
    with pytest.raises(d.CanonicalizationError, match="authority error"):
        scope(changed)
    assert not scope.__self__._encoded


def test_scoped_projector_uses_the_public_failure_path(monkeypatch):
    inputs = _inputs()
    scope = CnASharePortfolioEconomicProjectionInputsV1.scoped_projector()
    scope(inputs)

    def deny(*args):
        raise AssertionError("typed failure requested the success memo")

    monkeypatch.setattr(scope.__self__, "digest", deny)
    old_clock = _at(d.UtcInstant(inputs.as_of.instant.epoch_nanoseconds - 1))
    old_state = replace(inputs.dividend_state, as_of=old_clock)
    future = replace(inputs.as_of, phase=d.TimelinePhase(inputs.as_of.phase.rank + 1, "future"))
    marks = tuple(replace(m, resolved_at_instant=future) for m in inputs.marks)
    cases = (
        (replace(inputs, marks=marks, dividend_state=replace(old_state, account_id="foreign")), Code.CONTEXT_MISMATCH),
        (replace(inputs, marks=marks, dividend_state=old_state), Code.FUTURE_NATIVE_FACT),
        (replace(inputs, dividend_state=old_state), Code.DIVIDEND_STATE_MISMATCH),
        (_overcommitted(inputs), Code.NATIVE_CASH_OVERCOMMITTED),
        (replace(inputs, marks=inputs.marks[:-1]), Code.NATIVE_SNAPSHOT_REJECTED),
    )
    for failed, code in cases:
        expected = project(failed)
        assert expected.failure.code is code
        assert d.canonical_bytes(scope(failed)) == d.canonical_bytes(expected)
