"""One same-config public input9→native execution→owner evidence→cold economic NAV vertical."""
from dataclasses import fields
import json
from pathlib import Path

import pytest
import crypto_quant_domain as d
import crypto_quant_backtest as bt
from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_prepared_case_v1


def _forbidden(*args, **kwargs):
    raise AssertionError("cold/cache cannot execute/select/live-book/append/publish")


def test_public_economic_prepare_run_cold_nav_smoke(tmp_path, monkeypatch):
    prepared, case, inputs, store, market = economic_prepared_case_v1(tmp_path)
    assert prepared.execution_request.schema_version == 9
    ref = prepared.runtime.run(prepared.execution_request)
    assert type(ref) is bt.BacktestCanonicalPublicationRef
    repository = bt.BacktestEvidenceRepository(reader=store)
    with pytest.raises(bt.BacktestEvidenceError, match="explicit matching MarketBundleReader"):
        repository.load_completed(ref)
    completed = repository.load_completed(ref, economic_market_reader=market)
    assert len(completed.execution_summary.fills) == 2
    assert all(fill.price.units > fill.reference_price.units for fill in completed.execution_summary.fills)
    input_ref = prepared.execution_request.execution_input_bundle_ref
    before_reads = store.reads.get(input_ref, 0)
    nav = bt.CnASharePortfolioEconomicDailyNavAnalysisRuntimeV1(reader=store, publisher=store, market_reader=market)
    profile = nav.publish_metric_profile()
    analysis_ref = nav.derive(publication_ref=ref, metric_profile_ref=profile)
    assert store.reads[input_ref] > before_reads
    value = repository.load_cn_a_share_portfolio_economic_daily_nav(analysis_ref, market_reader=market)
    assert value.execution_input_ref == input_ref
    assert len(value.points) == 3 and value.trade_count == 2
    assert len([f for f in fields(bt.CnASharePortfolioEconomicDailyNavAnalysisV1) if f.init]) == 13
    assert len(fields(bt.CnASharePortfolioEconomicDailyNavPointV1)) == 11
    assert len(value.to_canonical_dict()) == 24
    assert value.points[-1].equity == completed.execution_summary.final_portfolio_snapshot.equity
    assert value.to_canonical_dict()["source_qualification_verified"] is False
    from crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 import _CnASharePortfolioEconomicEngineV1
    import crypto_quant_backtest.cn_a_share_portfolio_economic_opening_v1 as opening
    import crypto_quant_backtest.cn_a_share_portfolio_financial_core_v1 as core
    monkeypatch.setattr(_CnASharePortfolioEconomicEngineV1, "run", _forbidden)
    monkeypatch.setattr(opening, "_economic_opening_v1", _forbidden)
    monkeypatch.setattr(opening, "_book_economic_full_fill_batch_v1", _forbidden)
    monkeypatch.setattr(core, "book_native_cn_portfolio_financial_core_v1", _forbidden)
    assert prepared.runtime.run(prepared.execution_request) == ref
    assert len(tuple(p for p in tmp_path.glob("runs/*/attempts/*") if p.name != ".staging")) == 2
    assert repository.load_cn_a_share_portfolio_economic_daily_nav(analysis_ref, market_reader=market) == value


def test_public_economic_tax_shortfall_fails_atomically(tmp_path, monkeypatch):
    prepared, case, inputs, store, market = economic_prepared_case_v1(tmp_path, tax_shortfall=True)
    ref = prepared.runtime.run(prepared.execution_request)
    assert type(ref) is d.ArtifactRef
    repository = bt.BacktestEvidenceRepository(reader=store)
    with pytest.raises(bt.BacktestEvidenceError, match="explicit matching MarketBundleReader"):
        repository.load_terminal(ref)
    terminal = repository.load_terminal(ref, economic_market_reader=market)
    assert terminal.status.value == "FAILED"
    attempt_paths = tuple(tmp_path.glob("runs/*/attempts/*/attempt-execution-record.json"))
    report_paths = tuple(tmp_path.glob("runs/*/attempts/*/failure-report.json"))
    assert len(attempt_paths) == len(report_paths) == 1
    record = json.loads(attempt_paths[0].read_bytes())["payload"]
    report = json.loads(report_paths[0].read_bytes())["payload"]
    assert record["failed_report"] == report
    failure = report["issue"]["source_evidence"]
    assert failure["schema_version"] == 2
    context = failure["economic_failure_context"]["payload"]
    assert any(e["entry_type"] == "corporate_action_cash_paid" for e in context["journal"]["entries"])
    assert context["ca_failure"]["code"] == "tax_cash_shortfall"
    from crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 import _CnASharePortfolioEconomicEngineV1
    monkeypatch.setattr(_CnASharePortfolioEconomicEngineV1, "run", _forbidden)
    assert prepared.runtime.run(prepared.execution_request) == ref
    assert len(tuple(tmp_path.glob("runs/*/attempts/*/attempt-execution-record.json"))) == 1
    nav = bt.CnASharePortfolioEconomicDailyNavAnalysisRuntimeV1(reader=store, publisher=store, market_reader=market)
    with pytest.raises(TypeError):
        nav.derive(publication_ref=ref, metric_profile_ref=nav.publish_metric_profile())


def test_public_economic_io_errors_propagate_without_fake_terminal(tmp_path, monkeypatch):
    prepared, case, inputs, store, market = economic_prepared_case_v1(tmp_path)
    sentinel = OSError("economic original input9 read fault")
    def broken(*args, **kwargs):
        raise sentinel
    monkeypatch.setattr(store, "read", broken)
    with pytest.raises(OSError) as caught:
        prepared.runtime.run(prepared.execution_request)
    assert caught.value is sentinel
    assert not tuple(tmp_path.glob("runs/*/attempts/*/evidence-manifest.json"))
