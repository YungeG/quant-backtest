"""Native financial failure transport and execution-source seam checks."""
from dataclasses import replace

import pytest
import crypto_quant_domain as d
import crypto_quant_trading as t
from crypto_quant_backtest.cn_a_share_portfolio_economic_native_state_v1 import _EconomicNativeFailureV1
from crypto_quant_backtest.cn_a_share_portfolio_financial_core_v1 import book_native_cn_portfolio_financial_core_v1
from crypto_quant_backtest.engine import EngineFailureCode
from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_native_step_v1
from tests.runtime.providers.test_cn_a_share_portfolio_financial_variable_n_v2 import _native_n, COST_BASIS, QUANTIZATION


def _id(kind, role):
    return d.DomainId(kind, kind.prefix + "_" + d.canonical_sha256({"native_fault_fixture": role})[7:])


@pytest.fixture(scope="module")
def native_steps(tmp_path_factory):
    current, economic = economic_native_step_v1(tmp_path_factory.mktemp("economic-native-step"))
    scope, prior, schema, _, legacy, *_ = _native_n(2)
    return current, economic, prior, schema, legacy[0]


def _failed_outcomes(step):
    accounting, engine = t.CashInstrumentAccounting(), t.FeeAssessmentEngine()
    fill = step.opening.fill
    cash = d.CashBalanceKey(fill.account_id, fill.venue_id, d.CurrencyId("CNY"))
    wrong_cash = d.CashBalanceKey(fill.account_id, fill.venue_id, d.CurrencyId("USD"))
    position = d.PositionBalanceKey(fill.account_id, fill.venue_id, fill.instrument_id)
    at = d.SimulationInstant(fill.execution_time, d.TimelinePhase(70, "accounting"), d.SourceSequence(1))
    kwargs = dict(fill=fill, cash_key=cash, position_key=position, open_lots=(), cost_basis_policy=COST_BASIS,
        notional_quantization=QUANTIZATION, journal_entry_id=_id(d.DomainIdKind.JOURNAL, "book"), recorded_at=at)
    booked = accounting.book_fill(**kwargs)
    bad_booked = accounting.book_fill(**{**kwargs, "cash_key": wrong_cash})
    assert booked.result is not None and bad_booked.result is None and bad_booked.failure is not None
    fill_fee = engine.assess(basis=t.FeeAssessmentBasisEvidence.for_fill(fill), rule_set=step.final_fill_rules,
        fee_assessment_id=_id(d.DomainIdKind.FEE, "fill"), assessment_time=fill.execution_time)
    order_fee = engine.assess(basis=t.FeeAssessmentBasisEvidence.for_order(step.terminal_order), rule_set=step.final_order_rules,
        fee_assessment_id=_id(d.DomainIdKind.FEE, "order"), assessment_time=fill.execution_time)
    assert fill_fee.result is not None and order_fee.result is not None
    foreign = replace(fill, fill_id=_id(d.DomainIdKind.FILL, "foreign-basis"),
        reference_price=replace(fill.reference_price, quote_currency="USD"), price=replace(fill.price, quote_currency="USD"),
        slippage_amount=d.Money(fill.slippage_amount.units, fill.slippage_amount.scale, "USD"))
    bad_fee = engine.assess(basis=t.FeeAssessmentBasisEvidence.for_fill(foreign), rule_set=step.final_fill_rules,
        fee_assessment_id=_id(d.DomainIdKind.FEE, "foreign"), assessment_time=fill.execution_time)
    assert bad_fee.result is None and bad_fee.failure is not None
    bad_fill_charge = accounting.charge_fee(assessment=fill_fee.result.assessment, related_fill=fill,
        cash_key=wrong_cash, open_lots=booked.result.open_lots, cost_basis_policy=COST_BASIS,
        journal_entry_id=_id(d.DomainIdKind.JOURNAL, "fill-charge"), recorded_at=at)
    bad_order_charge = accounting.charge_order_fee(assessment=order_fee.result.assessment, order_stream=step.terminal_order,
        cash_key=wrong_cash, open_lots=booked.result.open_lots, cost_basis_policy=COST_BASIS,
        journal_entry_id=_id(d.DomainIdKind.JOURNAL, "order-charge"), recorded_at=at)
    assert bad_fill_charge.result is None and bad_fill_charge.failure is not None
    assert bad_order_charge.result is None and bad_order_charge.failure is not None
    return {"booked": bad_booked, "fill_fee": bad_fee, "charged_fill": bad_fill_charge,
            "order_fee": bad_fee, "charged_order": bad_order_charge}


_BRANCHES = (
    ("booked", EngineFailureCode.ACCOUNTING_FAILURE, "native portfolio Fill accounting rejected", (1, 0, 0, 0)),
    ("fill_fee", EngineFailureCode.FEE_ASSESSMENT_FAILURE, "native portfolio Fill fee assessment rejected", (1, 1, 0, 0)),
    ("charged_fill", EngineFailureCode.FEE_ACCOUNTING_FAILURE, "native portfolio Fill fee Journal rejected", (1, 1, 1, 0)),
    ("order_fee", EngineFailureCode.FEE_ASSESSMENT_FAILURE, "native portfolio Order fee assessment rejected", (1, 2, 1, 0)),
    ("charged_order", EngineFailureCode.FEE_ACCOUNTING_FAILURE, "native portfolio Order fee Journal rejected", (1, 2, 1, 1)),
)


def _exercise(monkeypatch, native_steps, branch, economic, code, message, expected):
    current, new_step, old_prior, old_schema, old_step = native_steps
    step, prior, schema = (new_step, current.journal, current.inputs.scope.ledger_schema) if economic else (old_step, old_prior, old_schema)
    outcomes = _failed_outcomes(step)
    rejected = outcomes[branch]
    original_hash = prior.journal_hash
    calls = dict(book_fill=0, assess=0, charge_fee=0, charge_order_fee=0, append=0)
    originals = {name: getattr(t.CashInstrumentAccounting, name) for name in ("book_fill", "charge_fee", "charge_order_fee")}
    assess = t.FeeAssessmentEngine.assess
    def wrap(name):
        def call(self, **kwargs):
            calls[name] += 1
            target = {"book_fill": "booked", "charge_fee": "charged_fill", "charge_order_fee": "charged_order"}[name]
            if branch == target:
                return rejected
            return originals[name](self, **kwargs)
        return call
    for name in originals:
        monkeypatch.setattr(t.CashInstrumentAccounting, name, wrap(name))
    def assess_call(self, **kwargs):
        calls["assess"] += 1
        if branch == ("fill_fee" if calls["assess"] == 1 else "order_fee"):
            return rejected
        return assess(self, **kwargs)
    monkeypatch.setattr(t.FeeAssessmentEngine, "assess", assess_call)
    def no_append(*args, **kwargs):
        calls["append"] += 1
        raise AssertionError("rejected native result cannot append provisional entries")
    monkeypatch.setattr(t.AccountingJournal, "append_many", no_append)
    if economic:
        with pytest.raises(_EconomicNativeFailureV1) as caught:
            book_native_cn_portfolio_financial_core_v1(prior_journal=prior, ledger_schema=schema,
                cost_basis_policy=COST_BASIS, notional_quantization=QUANTIZATION, steps=(step,), sell_first=True)
        assert caught.value.code is code and caught.value.evidence is rejected
        assert caught.value.evidence_hash == d.canonical_sha256(rejected)
    else:
        with pytest.raises(ValueError) as caught:
            book_native_cn_portfolio_financial_core_v1(prior_journal=prior, ledger_schema=schema,
                cost_basis_policy=COST_BASIS, notional_quantization=QUANTIZATION, steps=(step,), sell_first=True)
        assert type(caught.value) is ValueError and str(caught.value) == message
    assert tuple(calls[k] for k in ("book_fill", "assess", "charge_fee", "charge_order_fee")) == expected
    assert calls["append"] == 0 and prior.journal_hash == original_hash


def test_native_accounting_failure_transport_representative(monkeypatch, native_steps):
    branch, code, message, expected = _BRANCHES[0]
    _exercise(monkeypatch, native_steps, branch, True, code, message, expected)


@pytest.mark.parametrize(("branch", "code", "message", "expected"), _BRANCHES)
@pytest.mark.parametrize("economic", [False, True])
def test_native_financial_failure_exact_type_matrix(monkeypatch, native_steps, branch, code, message, expected, economic):
    _exercise(monkeypatch, native_steps, branch, economic, code, message, expected)


def test_shared_core_legacy_success_body_matches_base():
    import ast
    import inspect
    from pathlib import Path
    import subprocess
    import crypto_quant_backtest.cn_a_share_portfolio_financial_core_v1 as core
    root = Path(__file__).resolve().parents[3]
    baseline = subprocess.check_output(["git", "-C", str(root), "show",
        "ea957d59527e93765681d85c7a2f3fd83e6356a0:packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_portfolio_financial_core_v1.py"], text=True)
    before, after = ast.parse(baseline), ast.parse(inspect.getsource(core))
    class RemoveOnlyEconomicRejectedOutcomeDispatch(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "_raise_economic_native_failure_v1":
                return None
            return self.generic_visit(node)
    after = RemoveOnlyEconomicRejectedOutcomeDispatch().visit(after)
    for name in ("_id", "_at", "_fill", "book_native_cn_portfolio_financial_core_v1"):
        old = next(n for n in before.body if isinstance(n, ast.FunctionDef) and n.name == name)
        new = next(n for n in after.body if isinstance(n, ast.FunctionDef) and n.name == name)
        assert ast.dump(ast.Module(body=old.body, type_ignores=[])) == ast.dump(ast.Module(body=new.body, type_ignores=[]))


@pytest.mark.parametrize("economic", [False, True])
def test_native_financial_exceptions_are_not_wrapped(monkeypatch, native_steps, economic):
    current, new_step, old_prior, old_schema, old_step = native_steps
    step, prior, schema = (new_step, current.journal, current.inputs.scope.ledger_schema) if economic else (old_step, old_prior, old_schema)
    sentinel = OSError("original native accounting I/O sentinel")
    def broken(*args, **kwargs):
        raise sentinel
    monkeypatch.setattr(t.CashInstrumentAccounting, "book_fill", broken)
    with pytest.raises(OSError) as caught:
        book_native_cn_portfolio_financial_core_v1(prior_journal=prior, ledger_schema=schema,
            cost_basis_policy=COST_BASIS, notional_quantization=QUANTIZATION, steps=(step,), sell_first=True)
    assert caught.value is sentinel


def test_sell_with_native_settled_shares_but_insufficient_upfront_fee_keeps_original_gtc_without_transfer(tmp_path,monkeypatch):
    import crypto_quant_backtest.cn_a_share_portfolio_economic_opening_v1 as opening
    from crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 import _CnASharePortfolioEconomicEngineV1
    from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _verify_economic_native_result_v1
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_prepared_case_v1
    _,case,inputs,store,_=economic_prepared_case_v1(tmp_path,cash_exit=True,sell_fee_shortfall=True)
    original=opening.plan_cn_portfolio_venue_funding_development_v1
    sell_at=max(t.opening_at for t in inputs.opening_terms)
    def guarded_planner(**kwargs):
        assert kwargs["at"].instant<sell_at,"ordinary SELL fee shortage must not enter the funding planner"
        return original(**kwargs)
    monkeypatch.setattr(opening,"plan_cn_portfolio_venue_funding_development_v1",guarded_planner)
    result=_CnASharePortfolioEconomicEngineV1(artifact_reader=store).run(case).result
    assert result is not None and len(result.fills)==2
    assert all(f.side is d.OrderSide.BUY for f in result.fills)
    last=next(a.payload.payload for a in result.financial_artifacts if a.role=="economic_opening_batch" and a.payload.payload["when"]==__import__("json").loads(d.canonical_bytes(sell_at)))
    assert all(row["sellable"]["units"]>0 for row in last["funded"]["sellability"]["positions"])
    assert not last["funding"] and len(last["outcomes"])==2
    assert all(o["action"]=="keep_active" and o["reason"]=="native_cash_or_t1_unavailable" for o in last["outcomes"])
    assert {f.instrument_id for f in result.fills}==set(inputs.scope.instrument_ids)
    assert all(b.quantity.units>0 for b in result.final_ledger_state.position_balances)
    witness=next(a.payload.payload["economic_witness"] for a in result.financial_artifacts if a.role=="economic_attempt_witness")
    assert len(witness["pending_intentions"])==2
    assert all(o["intent"]["side"]=="sell" and o["intent"]["time_in_force"]=="gtc" for o in witness["pending_intentions"])
    _verify_economic_native_result_v1(case=case,reader=store,result=result)
