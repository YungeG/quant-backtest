"""Finite synthetic source facts for the single-prestart public V2 lane."""
from dataclasses import replace

import crypto_quant_domain as d
from crypto_quant_market_data import InMemoryMarketBundleReader
from crypto_quant_trading import MarkObservation, MarkResolver, StaleMarkPolicy
from crypto_quant_trading.profiles.cn_a_share.portfolio_economic_v1 import CnAShareCashDividendActionSetV1
from crypto_quant_backtest import CnASharePortfolioEconomicDevelopmentInputsV2
from crypto_quant_backtest.cn_a_share_portfolio_standard_definition_v1 import CnASharePortfolioMarkBatchDevelopmentV1
from crypto_quant_backtest.timeline import TimelineWindow
from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_public_sources_v1


def economic_public_sources_v2():
    source, original_bars, _, store, target, old_window = economic_public_sources_v1(bps=10)
    initial_utc = d.UtcInstant(source.signal_marks[0].at.instant.epoch_nanoseconds + 9 * 3_600_000_000_000)
    initial_at = d.SimulationInstant(initial_utc, d.TimelinePhase(0, "cn_economic_initial"), d.SourceSequence(0))
    policy = StaleMarkPolicy("synthetic.economic.activation.9h", 1, d.PricePurpose.VALUATION,
        9 * 3_600_000_000_000, True)
    initial = []
    for old in source.signal_marks[0].marks:
        observation = MarkObservation(old.instrument_id, old.quote_currency_id, old.price_purpose,
            old.price, old.observed_at, old.available_at, old.stream_id, old.source_event_id, old.revision_id)
        result = MarkResolver().resolve((observation,), instrument_id=old.instrument_id,
            price_purpose=d.PricePurpose.VALUATION, requested_at=initial_utc, stale_policy=policy)
        assert result.resolved_mark is not None
        initial.append(replace(result.resolved_mark, available_at_instant=old.available_at_instant,
            resolved_at_instant=initial_at))
    bars = tuple(b for b in original_bars if b.event_time >= initial_utc)
    window = TimelineWindow(old_window.data_start, initial_utc, old_window.end_exclusive)
    market = InMemoryMarketBundleReader.build(bundle_key="economic.synthetic.single-prestart.v2", schema_version=1,
        coverage_start=window.data_start, coverage_end_exclusive=window.end_exclusive,
        instrument_catalog_hash=d.canonical_sha256(source.scope.instrument_catalog), capabilities=(bars[0].capability,),
        streams={bars[0].stream_key: bars})
    opening_ids = {b.event_id for b in bars}
    terms = tuple(replace(t, slippage_model=replace(t.slippage_model, basis_points_units=10,
        basis_points_scale=d.Scale(0), rounding=d.RoundingPolicy.HALF_UP))
        for t in source.opening_terms if t.bar_event_id in opening_ids)
    checkpoints = tuple(b for b in source.checkpoint_marks
        if (b.at.phase.rank in (49, 55, 67, 97) and b.at.instant in {v.event_time for v in bars})
        or b.at.phase.rank == 200)
    inputs = CnASharePortfolioEconomicDevelopmentInputsV2.from_sources(
        scope=replace(source.scope, market_bundle_ref=market.bundle_ref), source_target_stream=target,
        initial_journal=source.initial_journal, calendars=source.calendars, execution_policy=source.execution_policy,
        opening_terms=terms, initial_marks=CnASharePortfolioMarkBatchDevelopmentV1(initial_at, tuple(initial)),
        retained_signal_marks=source.signal_marks,
        daily_marks=tuple(b for b in source.daily_marks if b.at.instant >= initial_utc), checkpoint_marks=checkpoints,
        cost_basis_policy=source.cost_basis_policy, notional_quantization=source.notional_quantization,
        dividend_actions=CnAShareCashDividendActionSetV1(source.scope.account_id, initial_utc,
            window.end_exclusive, "MODEL_INPUTS_ONLY", ()), activation_stale_policy=policy)
    return inputs, bars, market, store, target, window


def _prepare_sources_v2(publication_root, inputs, market, store, window, *, build_artifact_manifest=None):
    from crypto_quant_backtest import CashDevelopmentRequestIntent, prepare_cn_a_share_portfolio_economic_development_backtest_v2
    from crypto_quant_backtest.cn_a_share_portfolio_economic_prepare_v2 import _registry_v2
    from crypto_quant_backtest.composition import _compose_profile_portfolio_economic_execution_case
    from crypto_quant_backtest.execution_inputs import _read_execution_inputs_v9_from_snapshot
    from crypto_quant_backtest.resolution import ProfileResolver
    from tests.runtime.providers.test_cash_development_provider import build_manifest
    prepared = prepare_cn_a_share_portfolio_economic_development_backtest_v2(
        request_intent=CashDevelopmentRequestIntent(1, "economic.synthetic.public.v2", window,
            inputs.scope.account_id, d.CurrencyId("CNY"), 0), provider_inputs=inputs,
        build_artifact_manifest=build_manifest() if build_artifact_manifest is None else build_artifact_manifest,
        artifact_reader=store, artifact_publisher=store, market_reader=market, publication_root=publication_root)
    bundle, failure = _read_execution_inputs_v9_from_snapshot(store, prepared.execution_request)
    assert failure is None
    resolved = ProfileResolver().resolve(request=prepared.execution_request.request, registry=_registry_v2(inputs),
        market_bundle_manifest=market.manifest, build_artifact_manifest=bundle.build_artifact_manifest).resolved
    case = _compose_profile_portfolio_economic_execution_case(resolved_request=resolved, market_reader=market,
        semantic_spec=bundle.execution_case_semantic_spec, target_stream=bundle.target_stream,
        timeline_stream_keys=bundle.timeline_stream_keys, timeline_batch_size=64, execution_case_plan=bundle.execution_case_plan)
    return prepared, case, inputs, store, market


def economic_prepared_case_v2(publication_root, *, build_artifact_manifest=None):
    inputs, _, market, store, _, window = economic_public_sources_v2()
    return _prepare_sources_v2(publication_root, inputs, market, store, window,
        build_artifact_manifest=build_artifact_manifest)


def _changed_target_v2(inputs, store, **candidate_fields):
    import json
    from crypto_quant_backtest import BacktestTargetStreamRepository
    from crypto_quant_backtest.target_stream import PrecomputedTargetStream
    event = inputs.source_target_stream.events[0]
    payload = json.loads(d.canonical_bytes(event.payload))
    payload["candidate"].update(candidate_fields)
    target = PrecomputedTargetStream(inputs.source_target_stream.stream_key, (replace(event, payload=payload),))
    context = store.put(envelope=d.ArtifactEnvelope.create("synthetic_economic_v2_target_context", 1, candidate_fields))
    ref = BacktestTargetStreamRepository(reader=store, publisher=store).publish(context, target)
    return replace(inputs, scope=replace(inputs.scope, target_stream_ref=ref), source_target_stream=target)
