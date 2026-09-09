"""#30 public Engine seam: real retained endpoint receipts, synthetic account/rule declarations.

This does not claim retained-source public preparation acceptance.
"""
from collections.abc import Mapping
from dataclasses import replace
from datetime import date

import pytest
import crypto_quant_backtest as bt
import crypto_quant_domain as d
import crypto_quant_trading as t
from crypto_quant_trading.profiles import cn_a_share as cn
from crypto_quant_market_data import InMemoryMarketBundleReader

from tests.runtime.engine.test_cn_a_share_live_settlement import cn_case, instant, profile
from tests.runtime.engine.test_live_execution_case import _respec


def closed_receipt_case(hour, minute, *, identity_factory=None):
    resolved = profile()
    dispatcher = bt.CnAShareDevelopmentFinancialDispatcherV2(resolved, closed_bar_execution=True)
    at = instant(2, hour, minute)
    signal_at = d.UtcInstant(at.epoch_nanoseconds - 300_000_000_000)
    events = {event.event_time: event for event in resolved.request.minute_authorities[0].events}
    event, signal = events[at], events[signal_at]
    price = bt.BarCloseObservation.from_event(event).close_price
    assert price is not None
    case, _ = cn_case(weights=("0.5",), decision_times=(signal_at,), close_times=(at,),
        end_at=d.UtcInstant(at.epoch_nanoseconds + 300_000_000_000), source_bars=(event,), source_price=price,
        identity_factory=identity_factory, combined_fees=True)
    fee_binding = bt.ProfileFeeRuleBinding(dispatcher.spec.spec_hash, d.CurrencyId("CNY"), d.Scale(2))
    request = resolved.request
    model = cn.CnAShareCashOrderRuleModel(request.order_rule_book, d.Scale(2))

    def authority(original, source):
        observation = bt.BarCloseObservation.from_event(source)
        assert observation.close_price is not None
        receipt = cn.CnAShareBarCloseReceipt(source.instrument_id, observation.close_price,
            observation.interval_start, observation.interval_end_exclusive, source.timeline_instant,
            source.event_id, source.event_hash)
        session = cn.CnAShareCashSessionModel(request.calendar).resolve_bar_close(receipt).result
        assert session is not None and session.physical_session.session_id is not None
        status = cn.CnAShareTradeStatusEvidence(source.instrument_id, session.physical_session.session_id,
            cn.CnAShareTradeStatus.NORMAL, instant(2, 9, 30), instant(2, 15), "sha256:" + "a" * 64)
        previous = cn.CnASharePreviousCloseEvidence(source.instrument_id, d.TradingDate("CN.XSHE", date(2023, 12, 29)),
            d.Price(670, d.Scale(2), str(source.instrument_id), "CNY"), instant(2, 9, 30), "sha256:" + "b" * 64)
        outcome = model.resolve_bar_close_rules(cn.CnAShareBarCloseOrderRuleQuery(request.instrument_scope.instrument,
            session, request.instrument_scope.rule_context, status, previous))
        assert outcome.result is not None, outcome.failure
        assert outcome.result.timeline is not None
        return replace(original, order_rule_timeline=outcome.result.timeline, fee_reservation_rule_set=fee_binding,
            notional_evidence=t.OrderRuleNotionalEvidence(t.NotionalPriceBasis.SUPPLIED_REFERENCE,
                observation.close_price, source.event_hash, source.available_time),
            requirement_source_hash=d.canonical_sha256(outcome))

    def snapshot(plan, source):
        old = plan.resolved_marks[0]
        mark = replace(old, price=bt.BarCloseObservation.from_event(source).close_price,
            observed_at=source.event_time, available_at=source.available_time,
            available_at_instant=source.timeline_instant, source_event_id=source.event_id,
            stream_id=source.stream_key, revision_id=source.revision_id,
            age_nanoseconds=plan.projection_at.instant.epoch_nanoseconds - source.event_time.epoch_nanoseconds)
        return replace(plan, resolved_marks=(mark,))

    cycle = case.decision_cycles[0]
    cycle = replace(cycle, snapshot_plan=snapshot(cycle.snapshot_plan, signal),
        sizing_policy=t.PositionSizingPolicy.create(policy_key="closed-receipt.lot-sizing", policy_version=1,
            price_purpose=d.PricePurpose.VALUATION, rounding=d.RoundingPolicy.TOWARD_ZERO,
            residual_policy=t.ResidualPositionPolicy.CLOSE_IF_PERMITTED),
        admission_slot=replace(cycle.admission_slot, pretrade_authority=authority(cycle.admission_slot.pretrade_authority, signal)))
    bar = case.bar_executions[0]
    fee = bar.accounting_plan.fee_plan
    assert isinstance(fee, bt.FullFillOrderFeeAccountingPlan) and fee.fill_fee_plan is not None
    bar = replace(bar, pretrade_authority=authority(bar.pretrade_authority, event),
        accounting_plan=replace(bar.accounting_plan, fee_plan=replace(fee, final_fee_rule_set=fee_binding,
            fill_fee_plan=replace(fee.fill_fee_plan, final_fee_rule_set=fee_binding))))
    final = snapshot(case.snapshot_plan, event)
    case = _respec(replace(case, decision_cycles=(cycle,), bar_executions=(bar,), snapshot_plan=final,
        financial_dispatch_plan=replace(case.financial_dispatch_plan, dispatcher_spec=dispatcher.spec, final_snapshot_payload=final)))
    return case, dispatcher, event


@pytest.mark.parametrize("hour,minute", ((11, 30), (15, 0)))
def test_actual_endpoint_receipt_can_fill_and_settle_without_retiming(hour, minute):
    case, dispatcher, event = closed_receipt_case(hour, minute)
    outcome = bt.DeterministicBarEngine(dispatcher).run(case)
    assert outcome.result is not None, outcome.engine_failure
    [fill] = outcome.result.fills
    assert fill.execution_time == event.event_time
    assert fill.reference_price == fill.price == bt.BarCloseObservation.from_event(event).close_price
    assert case.bar_executions[0].pretrade_authority.order_rule_timeline.intervals[0].snapshot.session_state is t.MarketSessionState.EXECUTION_RECEIPT
    normal = cn.CnAShareCashSessionModel(profile().request.calendar).resolve_session(cn.CnAShareSessionQuery(fill.venue_id, fill.execution_time)).result
    assert normal is not None and normal.is_open is False
    artifact = next(value for value in outcome.result.financial_artifacts if value.role == f"settlement_resolution.{event.event_id}")
    assert isinstance(artifact.payload, t.ProfilePortOutcome)
    result = artifact.payload.result
    assert isinstance(result, cn.CnAShareBarCloseSettlementResolution)
    assert result.position_availability_time == instant(3)
    assert all(obligation.obligation.trade_time == event.event_time for obligation in result.obligations)


@pytest.mark.parametrize("change", ("price", "source"))
def test_closed_dispatch_requires_exact_profile_source_receipt(change):
    case, dispatcher, event = closed_receipt_case(15, 0)
    if change == "price":
        payload = dict(event.payload)
        raw_price = payload["close_price"]
        assert isinstance(raw_price, Mapping) and type(raw_price["units"]) is int
        payload["close_price"] = {**raw_price, "units": raw_price["units"] + 1}
        event = replace(event, payload=payload)
    else:
        event = replace(event, event_id="unretained-close")
    bar = case.bar_executions[0]
    roles = tuple(f"{role}.{event.event_id}" for role in ("position_accounting", "settlement", "settlement_resolution"))
    bar = replace(bar, event_id=event.event_id,
        accounting_plan=replace(bar.accounting_plan, source_event_id=event.event_id, expected_artifact_roles=roles),
        liquidity_evidence=bt.BarLiquidityEvidence.create(evidence_key="closed-test.tampered", evidence_version=1,
            market_event=event, evaluated_at=event.available_time, approved=True, reason_code=None, source_hash=event.event_hash),
        market_state=replace(bar.market_state, source_event_id=event.event_id, evidence_hash=event.event_hash))
    reader = InMemoryMarketBundleReader.build(bundle_key="closed-test.tampered", schema_version=1,
        coverage_start=case.timeline.window.data_start, coverage_end_exclusive=case.timeline.window.end_exclusive,
        instrument_catalog_hash=case.timeline.reader.manifest.instrument_catalog_hash,
        capabilities=(bt.BAR_CLOSE_CAPABILITY, bt.TARGET_STREAM_CAPABILITY),
        streams={event.stream_key: (event,), case.target_stream.stream_key: case.target_stream.events})
    timeline = bt.DeterministicTimeline.open(reader=reader, stream_keys=(event.stream_key, case.target_stream.stream_key), window=case.timeline.window)
    assert isinstance(timeline, bt.DeterministicTimeline)
    case = _respec(replace(case, timeline=timeline, bar_executions=(bar,)))
    outcome = bt.DeterministicBarEngine(dispatcher).run(case)
    assert outcome.result is None and outcome.engine_failure is not None
    assert "cn_a_share_closed_receipt_mismatch" in d.canonical_bytes(outcome).decode()


def test_closed_receipt_rejects_execution_price_different_from_retained_close():
    case, dispatcher, _ = closed_receipt_case(15, 0)
    bar = case.bar_executions[0]
    bar = replace(bar, slippage_model=replace(bar.slippage_model, basis_points_units=30, limitations=(),
        component_ref=replace(bar.slippage_model.component_ref, component_key="deterministic_bps.v1")))
    outcome = bt.DeterministicBarEngine(dispatcher).run(_respec(replace(case, bar_executions=(bar,))))
    assert outcome.result is None and outcome.engine_failure is not None
    assert "cn_a_share_closed_receipt_mismatch" in d.canonical_bytes(outcome).decode()


def test_closed_execution_authority_is_one_timestamp_not_a_reopened_session():
    case, dispatcher, event = closed_receipt_case(15, 0)
    interval = case.bar_executions[0].pretrade_authority.order_rule_timeline.intervals[0]
    assert interval.contains(event.event_time)
    assert not interval.contains(d.UtcInstant(event.event_time.epoch_nanoseconds - 1))
    assert not interval.contains(d.UtcInstant(event.event_time.epoch_nanoseconds + 1))
    with pytest.raises(ValueError, match="exactly one nanosecond"):
        t.OrderRuleInterval.create(effective_from=interval.effective_from,
            effective_to_exclusive=d.UtcInstant(interval.effective_from.epoch_nanoseconds + 2), snapshot=interval.snapshot)
    receipt = dispatcher.bar_close_receipt(event.event_id)
    with pytest.raises(ValueError, match="availability"):
        replace(receipt, received_at=replace(receipt.received_at, instant=d.UtcInstant(event.event_time.epoch_nanoseconds + 1)))
    with pytest.raises(ValueError, match="48 session-valid"):
        replace(receipt, interval_start=instant(2, 11, 55), interval_end_exclusive=instant(2, 12),
            received_at=replace(receipt.received_at, instant=instant(2, 12)))
    weekend = replace(receipt, interval_start=instant(6, 14, 55), interval_end_exclusive=instant(6, 15),
        received_at=replace(receipt.received_at, instant=instant(6, 15)))
    closed = cn.CnAShareCashSessionModel(profile().request.calendar).resolve_bar_close(weekend)
    assert closed.result is not None and closed.result.is_eligible is False


def test_v7_public_backtest_hydrates_closed_receipt_rules_and_profile_binding(tmp_path):
    from tests.runtime.execution_inputs.test_live_execution_input_v7 import _prepared, _published_engine_payload
    runtime, request, store, _ = _prepared(tmp_path, dispatcher_mode="closed", closed_endpoint=(15, 0))
    publication = runtime.run(request)
    assert type(publication) is bt.BacktestCanonicalPublicationRef
    completed = bt.BacktestEvidenceRepository(store).load_completed(publication)
    [fill] = completed.execution_summary.fills
    assert fill.execution_time == instant(2, 15)
    assert fill.price.units == 669
    assert completed.execution_summary.final_portfolio_snapshot.fees.units > 0
    payload = _published_engine_payload(store, publication)
    settlements = [row for row in payload["financial_artifacts"] if row["role"].startswith("settlement_resolution.")]
    assert len(settlements) == 1
    assert settlements[0]["payload"]["result"]["type"] == "cn_a_share_bar_close_settlement_resolution"
    assert runtime.run(request) == publication
