"""Full-clock native due-prefix tests; no synthetic market event for settlement."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
import crypto_quant_domain as d
from crypto_quant_trading import SettlementBook
from crypto_quant_backtest.cn_a_share_portfolio_economic_native_state_v1 import _advance_economic_settlement_v1
from crypto_quant_backtest.cn_a_share_portfolio_settlement_development_v1 import CnASharePortfolioSettlementDevelopmentV1, _book_body
from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_definition_source_v1
from tests.kernel.settlement._fixtures import registered_obligation, recorded_event


@pytest.fixture(scope="module")
def due_source():
    return economic_definition_source_v1()


def _at(n, rank, code="cn_economic_native", sequence=0):
    return d.SimulationInstant(d.UtcInstant(n), d.TimelinePhase(rank, code), d.SourceSequence(sequence))


def _book(source, dues):
    key = next(r.key for r in source.scope.ledger_schema.cash_registrations if r.key.venue_id.value == "xshg")
    obligations = tuple(registered_obligation(str(i), key=key, units=100, settlement_time=due) for i, due in enumerate(dues, 1))
    events = tuple(recorded_event(ob, str(i), sequence=i) for i, ob in enumerate(obligations, 1))
    return SettlementBook.from_events(source.scope.account_id, obligations, events)


def _advance(source, book, at):
    case = SimpleNamespace(semantic_spec=SimpleNamespace(spec_version=1))
    return _advance_economic_settlement_v1(
        case=case, inputs=source, journal=source.initial_journal, book=book, consumer=at)


def test_native_due_prefix_rank10_unchanged_then45_exact_native20(due_source):
    book = _book(due_source, (200,))
    assert _advance(due_source, book, _at(200, 10)) is book
    result = _advance(due_source, book, _at(200, 45))
    expected = CnASharePortfolioSettlementDevelopmentV1(d.canonical_sha256(due_source.initial_journal),
        tuple(c.calendar_hash for c in due_source.calendars), book).apply_due(d.UtcInstant(200)).book
    assert d.canonical_bytes(_book_body(result)) == d.canonical_bytes(_book_body(expected))
    assert result.events[-1].occurred_at == _at(200, 20, "settlement_due", 1)
    assert _advance(due_source, result, _at(200, 45)) is result
    assert len(result.events) == len(book.events) + 1


def test_multiple_due_groups_use_due_times_not_later_consumer_and_need_no_bar(due_source):
    book = _book(due_source, (200, 300))
    advanced = _advance(due_source, book, _at(500, 10))
    assert tuple(e.occurred_at.instant for e in advanced.events[len(book.events):]) == (d.UtcInstant(200), d.UtcInstant(300))
    cold = _advance(due_source, book, _at(500, 10))
    assert d.canonical_bytes(_book_body(cold)) == d.canonical_bytes(_book_body(advanced))
    assert not advanced.project().pending_obligations
    assert _advance(due_source, book, _at(100, 45)) is book


def test_native_batch_compares_phase_code_and_sequence_and_rejects_split(due_source):
    book = _book(due_source, (200, 200))
    assert _advance(due_source, book, _at(200, 20, "aaa")) is book
    assert _advance(due_source, book, _at(200, 20, "settlement_due", 0)) is book
    original = book.book_hash
    with pytest.raises(ValueError, match="splits"):
        _advance(due_source, book, _at(200, 20, "settlement_due", 1))
    assert book.book_hash == original
    exact = _advance(due_source, book, _at(200, 20, "settlement_due", 2))
    after_code = _advance(due_source, book, _at(200, 20, "zzz"))
    assert exact == after_code
    assert tuple(e.occurred_at.source_sequence.value for e in exact.events[len(book.events):]) == (1, 2)


def test_missed_native_due_boundary_and_future_book_are_rejected_without_backdating(due_source):
    base = _book(due_source, (200, 400))
    later = replace(base.obligations[1], obligation=replace(base.obligations[1].obligation, trade_time=d.UtcInstant(250)))
    events = (base.events[0], recorded_event(later, "2", sequence=2))
    late = SettlementBook.from_events(base.account_id, (base.obligations[0], later), events)
    before = late.book_hash
    with pytest.raises(ValueError, match="missed native"):
        _advance(due_source, late, _at(500, 45))
    with pytest.raises(ValueError, match="future"):
        _advance(due_source, late, _at(200, 45))
    assert late.book_hash == before


@pytest.mark.parametrize("tax_shortfall", [False, True])
def test_native_economic_engine_executes_or_preserves_actual_pay_prefix(tmp_path, tax_shortfall):
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_prepared_case_v1
    from crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 import _CnASharePortfolioEconomicEngineV1
    from crypto_quant_backtest.engine import EngineFailureCode
    prepared, case, inputs, store, market = economic_prepared_case_v1(tmp_path, tax_shortfall=tax_shortfall)
    outcome = _CnASharePortfolioEconomicEngineV1(artifact_reader=store).run(case)
    (tmp_path / "native-outcome.json").write_bytes(d.canonical_bytes(outcome.result if outcome.result is not None else outcome.engine_failure))
    if tax_shortfall:
        assert outcome.result is None and outcome.engine_failure is not None
        failure = outcome.engine_failure
        assert failure.code is EngineFailureCode.FINANCIAL_DISPATCH_FAILURE
        context = failure.economic_failure_context.payload
        assert context["ca_failure"]["code"] == "tax_cash_shortfall"
        entries = context["journal"]["entries"]
        assert any(entry["entry_type"] == "corporate_action_cash_paid" for entry in entries)
        claims = context["prefix_checkpoint"]["dividend_state"]["claims"]
        assert claims[0]["gross_paid"]["units"] > 0 and claims[1]["tax_settled"]["units"] == 0
        assert context["ca_transition_inputs"]["history"]["journal"] == context["journal"]
    else:
        assert outcome.engine_failure is None, outcome.engine_failure
        result = outcome.result
        assert result is not None and len(result.fills) == len(result.slippage_decisions) == 2
        assert all(fill.price.units > fill.reference_price.units for fill in result.fills)
        assert any(entry.entry_type is d.AccountingEntryType.CORPORATE_ACTION_TAX_PAID for entry in result.final_journal.entries)
        witness = next(a.payload.payload["economic_witness"] for a in result.financial_artifacts if a.role == "economic_attempt_witness")
        assert witness["opening_count"] == witness["daily_count"] == 3
        assert witness["dividend_event_count"] == 4
        assert result.final_portfolio_snapshot.equity.units > 0


@pytest.mark.parametrize("missing_next_open", [False,True])
def test_pending_day_same_close_retained_then_next_session_filled_or_expires_without_resurrection(tmp_path, missing_next_open):
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_prepared_case_v1
    from crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 import _CnASharePortfolioEconomicEngineV1
    from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _verify_economic_native_result_v1
    prepared,case,inputs,store,market=economic_prepared_case_v1(tmp_path,missing_next_open=missing_next_open)
    outcome=_CnASharePortfolioEconomicEngineV1(artifact_reader=store).run(case)
    assert outcome.result is not None
    result=outcome.result
    days=sorted((a for a in result.financial_artifacts if a.role=="economic_daily_projection"),key=lambda a:a.occurred_at)
    pending=days[0].payload.payload["pending_intentions"]
    assert len(pending)==2
    assert all(order["created_at"]["phase"]["rank"]==40 for order in pending)
    assert all(order["created_at"]["instant"]==__import__("json").loads(d.canonical_bytes(inputs.signal_marks[0].at.instant)) for order in pending)
    if missing_next_open:
        assert not result.fills
        assert len(days[1].payload.payload["pending_intentions"])==0
        assert len(days[2].payload.payload["pending_intentions"])==0
        assert len([a for a in result.financial_artifacts if a.role=="economic_pending_no_real_open"])==2
    else:
        assert len(result.fills)==2
        assert all(fill.execution_time>inputs.signal_marks[0].at.instant for fill in result.fills)
        assert {fill.order_id.value for fill in result.fills}=={order["order_id"]["value"] for order in pending}
    _verify_economic_native_result_v1(case=case,reader=store,result=result)
