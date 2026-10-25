from __future__ import annotations

from dataclasses import replace
import json

import pytest
import crypto_quant_domain as d
from crypto_quant_trading import AccountingJournal, GenericLedger
from crypto_quant_trading.profiles.cn_a_share.portfolio_economic_v1 import (
    CnAShareCashDividendActionSetV1 as ActionSet,
    CnAShareCashDividendActionV1 as Action,
    CnAShareCashDividendHistoryInputsV1 as History,
    CnAShareCashDividendStateV1 as State,
    CnAShareCashDividendTaxPolicyV1 as Policy,
    CnAShareCashDividendTransitionFailureCodeV1 as Code,
    CnAShareCashDividendTransitionInputsV1 as Request,
    transition_cn_a_share_cash_dividend_v1 as transition,
    verify_cn_a_share_cash_dividend_history_v1 as verify,
)
from tests.kernel.profiles.cn_a_share.test_cash_dividend_projection_v1 import _at, _inputs


Q = d.QuantizationPolicy("declared.cents.v1", d.Scale(2), d.RoundingPolicy.HALF_UP)


def _event_id(action_set, action, kind, at):
    return d.canonical_sha256({"type": "cn_a_share_cash_dividend_event_coordinate", "schema_version": 1,
        "account_id": action_set.account_id, "instrument_id": action.instrument_id, "action_id": action.action_id,
        "action_set_hash": d.canonical_sha256(action_set), "action_terms_hash": d.canonical_sha256(action),
        "tax_policy_hash": d.canonical_sha256(action.tax_policy), "kind": kind, "event_at": at})


def _rows(action):
    rows = (("REGISTER", action.registered_at), ("ENTITLE", action.entitlement_at), ("PAY", action.payment_due_at))
    return rows + ((("TAX", action.tax_policy.due_at),) if action.tax_policy.due_at is not None else ())


def _history(*, zero_quantity=False, rounding=d.RoundingPolicy.HALF_EVEN, huge_tax=False):
    base = _inputs()
    t = base.as_of.instant.epoch_nanoseconds
    clocks = tuple(_at(d.UtcInstant(t + n), rank, 1) for n, rank in ((10, 150), (20, 10), (30, 151), (40, 152)))
    instrument = base.instrument_catalog.instruments[0].instrument_id
    policy = Policy("declared.fixed", base.market_rules.account_id, "FIXED_RATIO", 1, 1 if huge_tax else 5, Q, clocks[3])
    action = Action("declared.cash", instrument, *clocks[:3],
        d.Money(100_000_000 if huge_tax else 12345, d.Scale(2 if huge_tax else 5), "CNY"),
        replace(Q, rounding=rounding), policy, None, None, None, ())
    if huge_tax:
        action = replace(action, payment_due_at=_at(d.UtcInstant(t + 50), 151, 1))
    actions = ActionSet(base.market_rules.account_id, base.as_of.instant, d.UtcInstant(t + 100), "MODEL_INPUTS_ONLY", (action,))
    ids = tuple(sorted((_event_id(actions, action, kind, at), d.DomainId(d.DomainIdKind.JOURNAL, "jnl_" + str(n) * 64))
        for n, (kind, at) in enumerate((r for r in _rows(action) if r[0] in {"PAY", "TAX"}), 7)))
    journal = _capital_only(base.journal) if zero_quantity else base.journal
    return History(journal, base.ledger_schema, base.settlement_book, base.order_streams,
        base.reservation_schedules, base.market_rules, base.instrument_catalog,
        State(base.market_rules.account_id, base.as_of, ()), actions, ids, base.as_of)


def _capital_only(journal):
    return AccountingJournal(tuple(e for e in journal.entries if e.entry_type in {
        d.AccountingEntryType.CAPITAL_DEPOSITED, d.AccountingEntryType.CAPITAL_TRANSFERRED}))


def _step(h, kind):
    action = h.action_set.actions[0]
    at = dict(_rows(action))[kind]
    request = Request(replace(h, as_of=at), action.action_id, action.instrument_id, kind)
    result = transition(request)
    assert result.failure is None
    tr = result.transition
    assert tr == transition(request).transition
    assert tr is not None
    journal = h.journal.append_many(tr.journal_entries)
    assert tr.output_journal_hash == journal.journal_hash
    result_h = replace(h, journal=journal, dividend_state=tr.state_after, as_of=at)
    assert verify(result_h) is None
    retry = transition(Request(result_h, action.action_id, action.instrument_id, kind))
    assert retry.transition is not None and retry.transition.journal_entries == ()
    assert retry.transition.state_after == tr.state_after
    return result_h, tr


@pytest.mark.parametrize(("rounding", "gross", "tax"), [
    (d.RoundingPolicy.HALF_EVEN, 1234, 247), (d.RoundingPolicy.HALF_UP, 1235, 247),
])
def test_native_registration_precision_and_payment_tax_conservation(rounding, gross, tax):
    h = _history(rounding=rounding)
    initial_hash = h.journal.journal_hash
    h, register = _step(h, "REGISTER")
    claim = h.dividend_state.claims[0]
    assert claim.entitled_quantity == 100 and claim.record_journal_hash == initial_hash
    assert claim.recognized_gross.units == claim.tax_assessed.units == 0
    assert register.journal_entries == ()
    h, entitled = _step(h, "ENTITLE")
    claim = h.dividend_state.claims[0]
    assert claim.recognized_gross.units == gross and claim.tax_assessed.units == tax
    assert entitled.journal_entries == ()
    key = d.CashBalanceKey(h.market_rules.account_id, claim.instrument_id.venue, d.CurrencyId("CNY"))
    initial_cash = GenericLedger(h.ledger_schema).project(h.journal).cash_amount(key).units
    h, paid = _step(h, "PAY")
    assert paid.journal_entries[0].entry_type is d.AccountingEntryType.CORPORATE_ACTION_CASH_PAID
    assert GenericLedger(h.ledger_schema).project(h.journal).cash_amount(key).units == initial_cash + gross
    h, taxed = _step(h, "TAX")
    entry = taxed.journal_entries[0]
    assert entry.entry_type is d.AccountingEntryType.CORPORATE_ACTION_TAX_PAID
    assert entry.fees == entry.financing == entry.realized_pnl == entry.position_lot_changes == ()
    assert entry.source_ids == tuple(sorted(entry.source_ids)) and len(set(entry.source_ids)) == 6
    assert GenericLedger(h.ledger_schema).project(h.journal).cash_amount(key).units == initial_cash + gross - tax
    assert h.dividend_state.claims[0].tax_settled.units == tax
    from crypto_quant_backtest.execution_inputs import _read_journal_entry
    with pytest.raises(ValueError, match="legacy accounting entry"):
        _read_journal_entry(json.loads(d.canonical_bytes(entry)))


def test_zero_quantity_retains_every_event_and_unused_journal_slots():
    h = _history(zero_quantity=True)
    assert len(h.journal_entry_ids) == 2
    original = h.journal.journal_hash
    for kind in ("REGISTER", "ENTITLE", "PAY", "TAX"):
        h, tr = _step(h, kind)
        assert tr.journal_entries == () and h.journal.journal_hash == original
    claim = h.dividend_state.claims[0]
    assert claim.entitled_quantity == 0 and len(claim.applied_events) == 4
    assert verify(replace(h, journal_entry_ids=h.journal_entry_ids[:-1])).code is Code.HISTORY_MISMATCH
    missing = replace(claim, applied_events=claim.applied_events[:-1])
    assert verify(replace(h, dividend_state=replace(h.dividend_state, claims=(missing,)))).code is Code.HISTORY_MISMATCH


def test_tax_shortfall_is_atomic_and_cannot_use_later_cash():
    h = _history(huge_tax=True)
    h, _ = _step(h, "REGISTER")
    h, _ = _step(h, "ENTITLE")
    action = h.action_set.actions[0]
    request = Request(replace(h, as_of=action.tax_policy.due_at), action.action_id, action.instrument_id, "TAX")
    before = d.canonical_bytes(h)
    failed = transition(request)
    assert failed.failure.code is Code.TAX_CASH_SHORTFALL and failed.transition is None
    assert d.canonical_bytes(h) == before
    assert h.dividend_state.claims[0].tax_settled.units == 0


@pytest.mark.parametrize("mutation", ["quantity", "record_hash", "terms", "missing_claim", "missing_entry", "orphan", "mapping"])
def test_source_driven_history_rejects_rehashed_structural_substitutions(mutation):
    h = _history()
    for kind in ("REGISTER", "ENTITLE", "PAY", "TAX"):
        h, _ = _step(h, kind)
    c = h.dividend_state.claims[0]
    if mutation == "quantity":
        h = replace(h, dividend_state=replace(h.dividend_state, claims=(replace(c, entitled_quantity=101),)))
    elif mutation == "record_hash":
        h = replace(h, dividend_state=replace(h.dividend_state, claims=(replace(c, record_journal_hash=d.canonical_sha256("different-prefix")),)))
    elif mutation == "terms":
        h = replace(h, dividend_state=replace(h.dividend_state, claims=(replace(c, action_terms_hash=d.canonical_sha256("same-net-other-terms")),)))
    elif mutation == "missing_claim":
        h = replace(h, dividend_state=replace(h.dividend_state, claims=()))
    elif mutation == "missing_entry":
        h = replace(h, journal=AccountingJournal(h.journal.entries[:-1]))
    elif mutation == "mapping":
        rows = list(h.journal_entry_ids)
        rows[0] = (rows[0][0], d.DomainId(d.DomainIdKind.JOURNAL, "jnl_" + "a" * 64))
        h = replace(h, journal_entry_ids=tuple(rows))
    else:
        entry = replace(h.journal.entries[-1], journal_entry_id=d.DomainId(d.DomainIdKind.JOURNAL, "jnl_" + "a" * 64),
                        recorded_at=_at(d.UtcInstant(h.as_of.instant.epoch_nanoseconds + 1), 152, 1))
        h = replace(h, journal=h.journal.append(entry), as_of=entry.recorded_at)
    assert verify(h).code is Code.HISTORY_MISMATCH


def test_sequence_future_and_history_failure_priority():
    h = _history()
    action = h.action_set.actions[0]
    late = Request(replace(h, as_of=action.entitlement_at), action.action_id, action.instrument_id, "ENTITLE")
    assert transition(late).failure.code is Code.EVENT_SEQUENCE_MISMATCH
    assert verify(replace(h, dividend_state=replace(h.dividend_state, as_of=action.registered_at))).code is Code.FUTURE_NATIVE_FACT
    no_mapping = replace(h, journal_entry_ids=())
    assert transition(replace(late, history=replace(no_mapping, as_of=action.entitlement_at))).failure.code is Code.HISTORY_MISMATCH
    foreign = replace(h, action_set=replace(h.action_set, account_id="other", actions=()))
    assert verify(foreign).code is Code.CONTEXT_MISMATCH


def test_cold_history_never_appends_journal_or_runs_fee_engine(monkeypatch):
    h = _history()
    for kind in ("REGISTER", "ENTITLE", "PAY", "TAX"):
        h, _ = _step(h, kind)
    def forbidden(*args, **kwargs):
        raise AssertionError("cold history cannot append")
    monkeypatch.setattr(AccountingJournal, "append_many", forbidden)
    assert verify(h) is None


def test_history_and_failure_preimages_bind_full_populated_settlement_book():
    h = _history()
    book = h.settlement_book
    assert book.obligations and book.events
    body = h.to_canonical_dict()["settlement_book"]
    assert body == {"type": "cn_portfolio_development_settlement_book_source",
        "schema_version": 1, "account_id": book.account_id, "book_hash": book.book_hash,
        "obligations": book.obligations, "events": book.events}
    changed = replace(h, settlement_book=replace(book, events=book.events[:-1]))
    assert d.canonical_sha256(h) == d.canonical_sha256(h)
    assert d.canonical_sha256(h) != d.canonical_sha256(changed)
    action = h.action_set.actions[0]
    request = Request(replace(h, as_of=action.entitlement_at), action.action_id, action.instrument_id, "ENTITLE")
    changed_request = replace(request, history=replace(changed, as_of=action.entitlement_at))
    original = transition(request).failure
    other = transition(changed_request).failure
    assert original.code is other.code is Code.EVENT_SEQUENCE_MISMATCH
    assert original.subject_hashes == (d.canonical_sha256(request),)
    assert other.subject_hashes == (d.canonical_sha256(changed_request),)
    assert d.canonical_sha256(original) != d.canonical_sha256(other)


def test_precise_policy_and_action_shape_rejections_and_unknown_source_times():
    h = _history()
    action = h.action_set.actions[0]
    assert action.fact_event_time is action.provider_available_at is action.acquired_at is None
    with pytest.raises(TypeError):
        replace(action.tax_policy, numerator=True)
    with pytest.raises(ValueError):
        replace(action.tax_policy, numerator=2, denominator=10)
    with pytest.raises(ValueError):
        replace(action, cash_per_share=d.Money(1, d.Scale(9), "CNY"))
    with pytest.raises(ValueError):
        replace(h.action_set, actions=(action, action))
    with pytest.raises(ValueError):
        replace(action, provider_available_at=d.UtcInstant(10), fact_event_time=d.UtcInstant(11))
