"""Public standard route probes, synthetic Aug2023; NOT actual October A/B."""
from dataclasses import replace

import crypto_quant_backtest as bt
import crypto_quant_domain as d
from tests.runtime.providers.test_cn_a_share_portfolio_standard_case_v1 import _sources
from tests.runtime.providers.test_cash_development_provider import build_manifest


def _prepared(tmp_path):
    source, bars, market, store, _, window = _sources()
    def widen(term):
        old = term.slippage_model.applicability_envelope
        envelope = bt.SlippageApplicabilityEnvelope.create(envelope_key=old.envelope_key,
            envelope_version=old.envelope_version, instrument_id=old.instrument_id,
            valid_from=old.valid_from, valid_to_exclusive=old.valid_to_exclusive,
            maximum_quantity=replace(old.maximum_quantity, units=1_000_000),
            allowed_market_state_keys=old.allowed_market_state_keys)
        return replace(term, slippage_model=replace(term.slippage_model, applicability_envelope=envelope))
    source = replace(source, opening_terms=tuple(widen(t) for t in source.opening_terms))
    intent = bt.CashDevelopmentRequestIntent(1, "native.portfolio.public.test", window,
        source.scope.account_id, d.CurrencyId("CNY"), 0)
    prepared = bt.prepare_cn_a_share_portfolio_standard_development_backtest(request_intent=intent,
        provider_inputs=source, build_artifact_manifest=build_manifest(), artifact_reader=store,
        artifact_publisher=store, market_reader=market, publication_root=tmp_path)
    return prepared, store, source


def test_public_prepare_registered_engine_two_attempts_and_cold_cache(tmp_path, monkeypatch):
    prepared, store, source = _prepared(tmp_path)
    assert prepared.execution_request.schema_version == 8
    ref = prepared.runtime.run(prepared.execution_request)
    assert type(ref) is bt.BacktestCanonicalPublicationRef, ref
    verified = bt.BacktestEvidenceRepository(reader=store).load_completed(ref)
    assert len(verified.execution_summary.fills) == 2
    assert verified.execution_summary.final_portfolio_snapshot.account_id == source.scope.account_id
    assert verified.semantic_run_id == prepared.semantic_run_id
    from crypto_quant_backtest.cn_a_share_portfolio_standard_engine_v1 import _CnASharePortfolioStandardEngineV1
    from crypto_quant_backtest import cn_a_share_portfolio_standard_opening_v1 as opening
    def forbidden(*args, **kwargs):
        raise AssertionError("cached native result must not run Engine/select Fill/book journal")
    monkeypatch.setattr(_CnASharePortfolioStandardEngineV1, "run", forbidden)
    monkeypatch.setattr(opening, "_standard_opening_v1", forbidden)
    monkeypatch.setattr(opening, "_book_standard_full_fill_batch_v1", forbidden)
    cache_errors = []
    native_cache_check = _CnASharePortfolioStandardEngineV1.verify_cached
    def checked_cache(self, case, publication_ref):
        try:
            return native_cache_check(self, case, publication_ref)
        except Exception as error:
            cache_errors.append(error)
            raise
    monkeypatch.setattr(_CnASharePortfolioStandardEngineV1, "verify_cached", checked_cache)
    try:
        repeated = prepared.runtime.run(prepared.execution_request)
    except RuntimeError:
        if cache_errors:
            raise cache_errors[-1]
        raise
    assert repeated == ref
    assert len(tuple(p for p in tmp_path.glob("runs/*/attempts/*") if p.name != ".staging")) == 2
