"""Synthetic source facts and observable package origins; no second execution engine."""
from dataclasses import replace
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

import crypto_quant_domain as d
from crypto_quant_trading import FeeReservationRuleSet, FeeReservationRuleSource, ResolvedMark
from crypto_quant_trading.profiles.cn_a_share import CnAShareFeeReservationBuffer
from crypto_quant_trading.profiles.cn_a_share.portfolio_economic_v1 import CnAShareCashDividendActionSetV1
from crypto_quant_backtest.cn_a_share_portfolio_economic_definition_v1 import (
    CnASharePortfolioEconomicDevelopmentInputsV1, CnASharePortfolioEconomicOpeningTermsV1,
)
from crypto_quant_backtest.cn_a_share_portfolio_standard_definition_v1 import CnASharePortfolioMarkBatchDevelopmentV1
from crypto_quant_backtest.slippage import SlippageModelKind
from tests.runtime.providers.test_cn_a_share_portfolio_standard_definition_v1 import source_definition


def assert_economic_package_origins_v1():
    root = Path(__file__).resolve().parents[3]
    mode = os.environ.get("V18_EXPECT_INSTALL_MODE", "source")
    if mode not in {"source", "wheel"}:
        raise AssertionError("unknown economic test install mode")
    origins = {}
    for module, package, distribution in (
        ("crypto_quant_domain", "trading-domain", "crypto-quant-domain"),
        ("crypto_quant_trading", "trading-kernel", "crypto-quant-trading"),
        ("crypto_quant_market_data", "market-data-contracts", "crypto-quant-market-data"),
        ("crypto_quant_bundle_builder", "market-bundle-builder", "crypto-quant-bundle-builder"),
        ("crypto_quant_backtest", "backtest-runtime", "crypto-quant-backtest"),
    ):
        path = Path(importlib.import_module(module).__file__).resolve()
        dist = importlib.metadata.distribution(distribution)
        direct = dist.read_text("direct_url.json")
        if mode == "source":
            assert path.is_relative_to(root / "packages" / package / "src")
        else:
            assert path.is_relative_to(Path(sys.prefix).resolve()) and "site-packages" in path.parts
            assert not path.is_relative_to(root)
            if direct:
                assert not json.loads(direct).get("dir_info", {}).get("editable", False)
        origins[module] = {"path": str(path), "version": dist.version, "direct_url": direct}
    print(json.dumps({"economic_install_mode": mode, "python": sys.version, "packages": origins}, sort_keys=True))


def economic_definition_source_v1(*, bps=5):
    assert_economic_package_origins_v1()
    source = source_definition()
    initial_utc = d.UtcInstant(source.signal_marks[0].at.instant.epoch_nanoseconds - 86_400_000_000_000)
    initial_at = d.SimulationInstant(initial_utc, d.TimelinePhase(0, "cn_economic_initial"), d.SourceSequence(0))
    # Independent synthetic initial observation, not a future close re-dated to initialization.
    prices = {"600000": 1137, "000001": 2231}
    initial_marks = CnASharePortfolioMarkBatchDevelopmentV1(initial_at, tuple(
        ResolvedMark(i, d.CurrencyId("CNY"), d.PricePurpose.VALUATION,
            d.Price(prices[i.stable_key], d.Scale(2), str(i), "CNY"), initial_utc, initial_utc, initial_utc, 0,
            "synthetic.economic.initial", "initial:" + str(i), "fixture.initial.v1", "synthetic.economic.initial", 1,
            d.canonical_sha256({"purpose": "independent_initial_fixture"}),
            available_at_instant=initial_at, resolved_at_instant=initial_at) for i in source.scope.instrument_ids))
    terms = []
    for old in source.opening_terms:
        buffer = CnAShareFeeReservationBuffer.create(market_resolution=old.market_fee_resolution,
            tax_resolution=old.tax_resolution, maximum_fill_count=1)
        charges = tuple(c for c in old.reservation_rules.charge_rules if c.source is FeeReservationRuleSource.ACCOUNT_SCHEDULE)
        charges += (*old.market_fee_resolution.reservation_charge_rules, buffer.market_charge_rule,
                    old.tax_resolution.reservation_charge_rule, buffer.tax_charge_rule)
        original = old.reservation_rules
        rules = FeeReservationRuleSet.create(market_fee_policy_ref=original.market_fee_policy_ref,
            tax_policy_ref=original.tax_policy_ref, account_fee_schedule_ref=original.account_fee_schedule_ref,
            reservation_currency=original.reservation_currency, reservation_scale=original.reservation_scale,
            charge_rules=charges, minimums=original.minimums)
        slip = old.slippage_model
        if bps:
            slip = replace(slip, component_ref=replace(slip.component_ref,
                component_key=SlippageModelKind.DETERMINISTIC_BPS_V1.value,
                component_digest=d.canonical_sha256({"fixture_bps": bps})), basis_points_units=bps, limitations=())
        terms.append(CnASharePortfolioEconomicOpeningTermsV1(old.bar_event_id, old.bar_event_hash,
            old.instrument_id, old.side, old.capability_set, old.translation_mapping, old.rule_timeline,
            old.notional_evidence, rules, old.final_fill_rules, old.final_order_rules, old.market_fee_resolution,
            old.tax_resolution, old.liquidity, old.market_state, slip, 1))
    actions = CnAShareCashDividendActionSetV1(source.scope.account_id, initial_utc,
        d.UtcInstant(source.daily_marks[-1].at.instant.epoch_nanoseconds + 86_400_000_000_000), "MODEL_INPUTS_ONLY", ())
    return CnASharePortfolioEconomicDevelopmentInputsV1(source.scope, source.initial_journal, source.calendars,
        source.execution_policy, tuple(terms), initial_marks, source.signal_marks, source.daily_marks,
        source.daily_marks, source.cost_basis_policy, source.notional_quantization, actions)


def economic_public_sources_v1(*, tax_shortfall=False, bps=10):
    """Two instruments, three complete sessions, retained fixture-owner sources."""
    from datetime import date, datetime, timedelta
    from zoneinfo import ZoneInfo
    import crypto_quant_trading as t
    from crypto_quant_trading.profiles.cn_a_share import (CnAShareFrozenCalendar, CnAShareFrozenCalendarDay,
        CnAShareCalendarDayKind, CnAShareCashFeeRuleQuery, CnAShareFeeTradeMechanism)
    from crypto_quant_trading.profiles.cn_a_share.portfolio_economic_v1 import (
        CnAShareCashDividendTaxPolicyV1, CnAShareCashDividendActionV1,
    )
    from crypto_quant_market_data import InMemoryMarketBundleReader
    from crypto_quant_backtest import BacktestTargetStreamRepository
    from crypto_quant_backtest.cn_a_share_portfolio_economic_case_v1 import _economic_events_v1
    from crypto_quant_backtest.execution import BarLiquidityEvidence
    from crypto_quant_backtest.slippage import SlippageCalibrationRef
    from crypto_quant_backtest.target_stream import PrecomputedTargetStream
    from crypto_quant_backtest.timeline import TimelineWindow
    from tests.runtime.providers.test_cn_a_share_portfolio_standard_native_state_v1 import _target
    from tests.runtime.providers.test_cn_a_share_portfolio_financial_variable_n_v2 import _native_n
    from tests.runtime.providers.test_cn_a_share_portfolio_preparation_inputs_v1 import _Cas
    from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import policies, reservation_rule_set, final_order_rule_set
    assert_economic_package_origins_v1()
    zone = ZoneInfo("Asia/Shanghai")
    def utc(day, hour=0, minute=0):
        return d.UtcInstant.from_datetime(datetime(2023, 8, day, hour, minute, tzinfo=zone))
    def clock(day, hour, rank, sequence=0, minute=0):
        return d.SimulationInstant(utc(day, hour, minute), d.TimelinePhase(rank, "cn_economic_native"), d.SourceSequence(sequence))
    calendars = tuple(CnAShareFrozenCalendar(d.VenueId(venue), "CN.XSHG" if venue == "xshg" else "CN.XSHE",
        date(2023, 8, 25), date(2023, 8, 31), tuple(CnAShareFrozenCalendarDay(date(2023, 8, day),
            CnAShareCalendarDayKind.TRADING if day not in (26, 27) else CnAShareCalendarDayKind.WEEKEND)
            for day in range(25, 31)), "Asia/Shanghai") for venue in ("xshg", "xshe"))
    bars, terms = [], []
    scope = journal = cost_basis = quantization = None
    price_rows = {25: {"600000": 1137, "000001": 2231}, 28: {"600000": 1137, "000001": 2231},
                  29: {"600000": 1136, "000001": 2231}}
    market_policy, tax_policy = policies()
    for day in (25, 28, 29):
        values = _native_n(2, capital=10_000_000, price_units_by_code=price_rows[day],
            at_override=utc(day, 9, 30), calendars_override=calendars)
        source_scope, initial_journal, _, _, steps, _, raw_bars, witnesses, _ = values
        if scope is None:
            scope, journal = replace(source_scope, initial_cash=d.Money(10_000_000, d.Scale(2), "CNY")), initial_journal
        for step, raw, witness in zip(steps, raw_bars, witnesses, strict=True):
            bar = replace(raw, event_id=f"economic.open.{day}.{raw.instrument_id}",
                phase=d.TimelinePhase(20, "economic_raw_open"), source_sequence=d.SourceSequence(len(bars) + 1))
            bars.append(bar)
            liquidity, state, model = witness
            liquidity = BarLiquidityEvidence.create(evidence_key=liquidity.evidence_key,
                evidence_version=liquidity.evidence_version, market_event=bar, evaluated_at=bar.available_time,
                approved=liquidity.approved, reason_code=liquidity.reason_code,
                source_hash=d.canonical_sha256({"fixture_liquidity_source": bar.event_hash}))
            state = replace(state, source_event_id=bar.event_id, evidence_hash=bar.event_hash)
            maximum = replace(model.applicability_envelope.maximum_quantity, units=1_000_000)
            applicability = type(model.applicability_envelope).create(
                envelope_key="synthetic.economic.bps.window", envelope_version=1,
                instrument_id=bar.instrument_id, valid_from=model.applicability_envelope.valid_from,
                valid_to_exclusive=model.applicability_envelope.valid_to_exclusive,
                maximum_quantity=maximum, allowed_market_state_keys=model.applicability_envelope.allowed_market_state_keys)
            if bps:
                model = replace(model, component_ref=replace(model.component_ref,
                    component_key=SlippageModelKind.DETERMINISTIC_BPS_V1.value,
                    component_digest=d.canonical_sha256({"scenario": "synthetic.economic.adverse", "bps": bps})),
                    calibration_ref=SlippageCalibrationRef("synthetic.economic.uncalibrated", 1,
                        d.canonical_sha256({"scenario_bps": bps, "calibrated": False})),
                    applicability_envelope=applicability, basis_points_units=bps, limitations=())
            else:
                model = replace(model, applicability_envelope=applicability)
            risk = step.risk
            spec = risk.market.evaluation_input.executable_order_spec
            definition = scope.instrument_catalog.instrument(bar.instrument_id)
            for side in (d.OrderSide.BUY, d.OrderSide.SELL):
                query = CnAShareCashFeeRuleQuery(definition, side, bar.event_time, CnAShareFeeTradeMechanism.AUCTION)
                m, tax = market_policy.assess_fees(query).result, tax_policy.assess_taxes(query).result
                assert m is not None and tax is not None
                reservation = reservation_rule_set(side=side, effective_at=bar.event_time,
                    maximum_fill_count=1, venue=bar.instrument_id.venue.value, instrument_definition=definition)
                old = step.final_fill_rules
                final = t.FinalFeeRuleSet.create(market_fee_policy_ref=old.market_fee_policy_ref,
                    tax_policy_ref=old.tax_policy_ref, account_fee_schedule_ref=old.account_fee_schedule_ref,
                    assessment_currency=old.assessment_currency, assessment_scale=old.assessment_scale,
                    charge_rules=(*m.final_fill_charge_rules, tax.final_fill_charge_rule,
                        *(r for r in old.charge_rules if r.source is t.FinalFeeRuleSource.ACCOUNT_SCHEDULE)), minimums=old.minimums)
                terms.append(CnASharePortfolioEconomicOpeningTermsV1(bar.event_id, bar.event_hash, bar.instrument_id,
                    side, spec.capability_approval.capability_set, spec.translation_mapping, risk.market.rule_timeline,
                    t.OrderRuleNotionalEvidence(t.NotionalPriceBasis.SUPPLIED_REFERENCE,
                        risk.market.evaluation_input.notional_evidence.price, bar.event_hash, bar.available_time), reservation, final,
                    final_order_rule_set(side=side, effective_at=bar.event_time, venue=bar.instrument_id.venue.value,
                        instrument_definition=definition), m, tax, liquidity, state, model, 1))
    window = TimelineWindow(utc(25), utc(25), utc(30))
    reader = InMemoryMarketBundleReader.build(bundle_key="economic.synthetic.three-sessions.v1", schema_version=1,
        coverage_start=window.data_start, coverage_end_exclusive=window.end_exclusive,
        instrument_catalog_hash=d.canonical_sha256(scope.instrument_catalog), capabilities=(bars[0].capability,),
        streams={bars[0].stream_key: tuple(bars)})
    scope = replace(scope, market_bundle_ref=reader.bundle_ref)
    policy = t.StaleMarkPolicy("synthetic.economic.valuation_age", 1, d.PricePurpose.VALUATION, 86_400_000_000_000, True)
    def marks(at):
        local = at.instant.to_datetime().astimezone(zone)
        prices = price_rows[local.day]
        available = at if at.phase.rank == 0 else d.SimulationInstant(at.instant,
            d.TimelinePhase(0, "cn_economic_mark_source"), d.SourceSequence(0))
        rows = []
        for instrument in scope.instrument_ids:
            observation = t.MarkObservation(instrument, d.CurrencyId("CNY"), d.PricePurpose.VALUATION,
                d.Price(prices[instrument.stable_key], d.Scale(2), str(instrument), "CNY"), at.instant, at.instant,
                "synthetic.economic.independent.marks", f"economic.mark.{local.day}.{local.hour}.{local.minute}.{instrument}", "fixture.v1")
            resolved = t.MarkResolver().resolve((observation,), instrument_id=instrument,
                price_purpose=d.PricePurpose.VALUATION, requested_at=at.instant, stale_policy=policy).resolved_mark
            assert resolved is not None
            rows.append(replace(resolved, available_at_instant=available, resolved_at_instant=at))
        return CnASharePortfolioMarkBatchDevelopmentV1(at, tuple(rows))
    initial = marks(d.SimulationInstant(utc(25), d.TimelinePhase(0, "cn_economic_initial"), d.SourceSequence(0)))
    signals = (marks(d.SimulationInstant(utc(25, 15), d.TimelinePhase(20, "economic_target_source"), d.SourceSequence(1))),)
    daily = tuple(marks(clock(day, 15, 160)) for day in (25, 28, 29))
    instrument = next(i for i in scope.instrument_ids if i.venue.value == "xshg")
    q = d.QuantizationPolicy("synthetic.economic.dividend.cents", d.Scale(2), d.RoundingPolicy.HALF_EVEN)
    first_tax = CnAShareCashDividendTaxPolicyV1("fixture.tax.first", scope.account_id, "FIXED_RATIO", 1, 5, q, clock(29, 15, 152, 1))
    first = CnAShareCashDividendActionV1("a.first", instrument, clock(28, 15, 150, 1), clock(29, 9, 10, 1),
        clock(29, 15, 151, 1), d.Money(1, d.Scale(2), "CNY"), q, first_tax, None, None, None, ())
    actions = (first,)
    if tax_shortfall:
        second_tax = CnAShareCashDividendTaxPolicyV1("fixture.tax.second", scope.account_id, "FIXED_RATIO", 1, 1, q, clock(29, 15, 152, 2))
        second = CnAShareCashDividendActionV1("b.second", instrument, clock(28, 15, 150, 2), clock(29, 9, 10, 2),
            clock(30, 15, 151, 1), d.Money(100, d.Scale(2), "CNY"), q, second_tax, None, None, None, ())
        actions += (second,)
    action_set = CnAShareCashDividendActionSetV1(scope.account_id, window.trading_start, window.end_exclusive, "MODEL_INPUTS_ONLY", actions)
    required = {clock(day, 9, rank, minute=30) for day in (25, 28, 29) for rank in (49, 55, 67, 97)}
    required.add(clock(25, 15, 45))
    for action in actions:
        events = (action.registered_at, action.entitlement_at, action.payment_due_at, action.tax_policy.due_at)
        for at in events:
            if at.instant < window.end_exclusive:
                required.add(at)
                required.add(d.SimulationInstant(at.instant, at.phase, d.SourceSequence(at.source_sequence.value - 1)))
    checkpoints = [marks(at) for at in sorted(required)]
    boundary = clock(30, 0, 200)
    final = []
    for last in daily[-1].marks:
        observation = t.MarkObservation(last.instrument_id, last.quote_currency_id, last.price_purpose,
            last.price, last.observed_at, last.available_at, last.stream_id, last.source_event_id, last.revision_id)
        resolved = t.MarkResolver().resolve((observation,), instrument_id=last.instrument_id,
            price_purpose=last.price_purpose, requested_at=boundary.instant, stale_policy=policy).resolved_mark
        assert resolved is not None
        final.append(replace(resolved, available_at_instant=last.available_at_instant, resolved_at_instant=boundary))
    checkpoints.append(CnASharePortfolioMarkBatchDevelopmentV1(boundary, tuple(final)))
    from tests.runtime.providers.test_cn_a_share_portfolio_financial_variable_n_v2 import COST_BASIS, QUANTIZATION
    inputs = CnASharePortfolioEconomicDevelopmentInputsV1(scope, journal, calendars, steps[0].risk.plan.policy,
        tuple(sorted(terms, key=lambda v: (v.opening_at, v.instrument_id, v.side.value))), initial, signals, daily,
        tuple(sorted(checkpoints, key=lambda v: v.at)), COST_BASIS, QUANTIZATION, action_set)
    store = _Cas()
    context_ref = store.put(envelope=d.ArtifactEnvelope.create("synthetic_economic_target_context", 1, {"scope": "three-sessions-only"}))
    target = PrecomputedTargetStream("targets", (_target(inputs, 0),))
    target_ref = BacktestTargetStreamRepository(reader=store, publisher=store).publish(context_ref, target)
    inputs = replace(inputs, scope=replace(inputs.scope, target_stream_ref=target_ref))
    return inputs, tuple(bars), reader, store, target, window


def economic_native_step_v1(publication_root):
    """One real new-lane step, using production signal/admission/opening helpers."""
    import crypto_quant_trading as t
    from crypto_quant_backtest import CashDevelopmentRequestIntent
    from crypto_quant_backtest.cn_a_share_portfolio_economic_prepare_v1 import prepare_cn_a_share_portfolio_economic_development_backtest, _registry
    from crypto_quant_backtest.cn_a_share_portfolio_economic_case_v1 import _bind_economic_portfolio_sources_v1, _clock_v1
    from crypto_quant_backtest.cn_a_share_portfolio_economic_native_state_v1 import _EconomicOpenSourcesV1, _economic_signal_target_v1
    from crypto_quant_backtest.cn_a_share_portfolio_standard_native_state_v1 import _native_rebalance_plan_v1
    from crypto_quant_backtest.cn_a_share_portfolio_economic_opening_v1 import _economic_evaluation_v1, _economic_opening_v1, _EconomicFinancialStepV1
    from crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 import _EconomicAdmissionV1, _admit_economic_order_v1, _terminal_economic_order_v1
    from crypto_quant_backtest.composition import _compose_profile_portfolio_economic_execution_case
    from crypto_quant_backtest.execution_inputs import _read_execution_inputs_v9_from_snapshot
    from crypto_quant_backtest.execution import BarOpenObservation
    from crypto_quant_backtest.resolution import ProfileResolver
    from tests.runtime.providers.test_cash_development_provider import build_manifest
    source, bars, market, store, targets, window = economic_public_sources_v1(bps=0)
    prepared = prepare_cn_a_share_portfolio_economic_development_backtest(
        request_intent=CashDevelopmentRequestIntent(1, "economic.native.step.unit", window, source.scope.account_id, d.CurrencyId("CNY"), 0),
        provider_inputs=source, build_artifact_manifest=build_manifest(), artifact_reader=store, artifact_publisher=store,
        market_reader=market, publication_root=publication_root)
    bundle, failure = _read_execution_inputs_v9_from_snapshot(store, prepared.execution_request)
    assert failure is None
    resolved = ProfileResolver().resolve(request=prepared.execution_request.request, registry=_registry(source),
        market_bundle_manifest=market.manifest, build_artifact_manifest=bundle.build_artifact_manifest).resolved
    case = _compose_profile_portfolio_economic_execution_case(resolved_request=resolved, market_reader=market,
        semantic_spec=bundle.execution_case_semantic_spec, target_stream=targets, timeline_stream_keys=bundle.timeline_stream_keys,
        timeline_batch_size=64, execution_case_plan=bundle.execution_case_plan)
    bound = _bind_economic_portfolio_sources_v1(case, store)
    initial = case.financial_state
    def sources(at, streams=(), schedules=()):
        return _EconomicOpenSourcesV1(source, initial.journal, initial.settlement_book, streams, schedules,
            initial.settlement_rules, case.execution_case_plan.initial_dividend_state, bound.journal_entry_ids, at)
    raw_signal = targets.events[0]
    signal_at = source.signal_marks[0].at
    signal, proof = _economic_signal_target_v1(sources=sources(signal_at), event=raw_signal)
    plan = _native_rebalance_plan_v1(inputs=source, signal=signal, journal=initial.journal,
        settlement_book=initial.settlement_book, order_streams=(), reservation_schedules=(),
        market_rules=initial.settlement_rules, at=_clock_v1(signal_at.instant, 45))
    planned = plan.planned_orders[0]
    intent = replace(planned.intent, time_in_force=source.execution_policy.time_in_force_for(planned.intent.side))
    order = d.Order(case.domain_id(f"signal.0.{intent.instrument_id}.order"), source.scope.account_id,
                    intent, _clock_v1(signal_at.instant, 40, 1))
    index, event = next((i, b) for i, b in enumerate(bars) if b.instrument_id == intent.instrument_id and b.event_time > signal_at.instant)
    observation = BarOpenObservation.from_event(event)
    terms = next(v for v in source.opening_terms if v.bar_event_id == event.event_id and v.side is intent.side)
    quote, market_decision, issues, fee, reason = _economic_evaluation_v1(order, observation, terms)
    assert reason is None
    origin = sources(_clock_v1(event.event_time, 55))
    from crypto_quant_trading.profiles.cn_a_share.portfolio_v1 import CnASharePortfolioOrderProposalV1, CnASharePortfolioOrderPlanV1
    proposal = CnASharePortfolioOrderProposalV1(intent, market_decision.approval.calculated_notional,
        fee.fee_estimate.total_fee, terms.reservation_rules.rule_set_hash)
    admission_plan = CnASharePortfolioOrderPlanV1.create(account_id=source.scope.account_id,
        target_id=signal.normalized_target.normalized_target_id, target_hash=signal.normalized_target.normalized_target_hash,
        as_of=event.event_time, policy=source.execution_policy, cash=origin.cash, sellability=origin.sellability,
        working_orders=(), reservation_schedules=(), proposed=(proposal,))
    admission = _EconomicAdmissionV1(0, admission_plan, origin, fee, quote)
    stream, schedule = _admit_economic_order_v1(case, order, index, admission, terms, observation, 1)
    current = sources(_clock_v1(event.event_time, 67), (stream,), (schedule,))
    opening = _economic_opening_v1(sources=current, stream=stream, observation=observation, terms=terms, admission=admission)
    assert opening.fill is not None
    terminal = _terminal_economic_order_v1(case, stream, opening, 0, index, 1)
    return current, _EconomicFinancialStepV1(opening, terminal, terms)


def economic_prepared_case_v1(publication_root, *, tax_shortfall=False, cash_exit=False, missing_next_open=False, sell_fee_shortfall=False, reject_sell_capability=False):
    from crypto_quant_backtest import CashDevelopmentRequestIntent
    from crypto_quant_backtest.cn_a_share_portfolio_economic_prepare_v1 import prepare_cn_a_share_portfolio_economic_development_backtest, _registry
    from crypto_quant_backtest.composition import _compose_profile_portfolio_economic_execution_case
    from crypto_quant_backtest.execution_inputs import _read_execution_inputs_v9_from_snapshot
    from crypto_quant_backtest.resolution import ProfileResolver
    from tests.runtime.providers.test_cash_development_provider import build_manifest
    source, bars, market, store, targets, window = economic_public_sources_v1(tax_shortfall=tax_shortfall)
    if missing_next_open:
        from crypto_quant_market_data import InMemoryMarketBundleReader
        from zoneinfo import ZoneInfo
        bars = tuple(replace(bar, payload={"schema_version":1,"bar_kind":"gap_placeholder","open_price":None})
            if bar.event_time.to_datetime().astimezone(ZoneInfo("Asia/Shanghai")).day == 28 else bar for bar in bars)
        missing_ids = {bar.event_id for bar in bars if bar.payload["bar_kind"] == "gap_placeholder"}
        market = InMemoryMarketBundleReader.build(bundle_key="economic.synthetic.missing-next-open.v1",schema_version=1,
            coverage_start=window.data_start,coverage_end_exclusive=window.end_exclusive,
            instrument_catalog_hash=d.canonical_sha256(source.scope.instrument_catalog),capabilities=(bars[0].capability,),
            streams={bars[0].stream_key:bars})
        source = replace(source,scope=replace(source.scope,market_bundle_ref=market.bundle_ref),
            opening_terms=tuple(t for t in source.opening_terms if t.bar_event_id not in missing_ids))
    if cash_exit:
        from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import cn_a_share_portfolio_cash_capabilities_development_v1
        source = replace(source, opening_terms=tuple(replace(t, capability_set=cn_a_share_portfolio_cash_capabilities_development_v1())
            if t.side is d.OrderSide.SELL else t for t in source.opening_terms))
        from tests.runtime.providers.test_cn_a_share_portfolio_standard_native_state_v1 import _target
        from crypto_quant_backtest.target_stream import PrecomputedTargetStream
        from crypto_quant_backtest import BacktestTargetStreamRepository
        daily = source.daily_marks[1]
        at = d.SimulationInstant(daily.at.instant, d.TimelinePhase(20, "economic_target_source"), d.SourceSequence(2))
        signal = CnASharePortfolioMarkBatchDevelopmentV1(at, tuple(replace(m, resolved_at_instant=at) for m in daily.marks))
        coordinate = d.SimulationInstant(at.instant, d.TimelinePhase(45, "cn_economic_native"), d.SourceSequence(0))
        checkpoint = CnASharePortfolioMarkBatchDevelopmentV1(coordinate, tuple(replace(m, resolved_at_instant=coordinate) for m in daily.marks))
        source = replace(source, signal_marks=(*source.signal_marks, signal),
            checkpoint_marks=tuple(sorted((*source.checkpoint_marks, checkpoint), key=lambda b:b.at)))
        targets = PrecomputedTargetStream("targets", (_target(source,0),_target(source,1,selected=())))
        context = store.put(envelope=d.ArtifactEnvelope.create("synthetic_economic_target_context",1,{"cash_exit":True}))
        target_ref = BacktestTargetStreamRepository(reader=store,publisher=store).publish(context,targets)
        source = replace(source,scope=replace(source.scope,target_stream_ref=target_ref))
    if reject_sell_capability:
        buy_capability=next(t.capability_set for t in source.opening_terms if t.side is d.OrderSide.BUY)
        source=replace(source,opening_terms=tuple(replace(t,capability_set=buy_capability) if t.side is d.OrderSide.SELL else t for t in source.opening_terms))
    if sell_fee_shortfall:
        import crypto_quant_trading as native
        from dataclasses import fields
        declared_minimum=d.Money(100_000_000,d.Scale(2),"CNY")
        changed=[]
        for term in source.opening_terms:
            if term.side is not d.OrderSide.SELL:
                changed.append(term)
                continue
            schedule=replace(term.reservation_rules.account_fee_schedule_ref,
                schedule_digest=d.canonical_sha256({"synthetic_sell_account_schedule":1,"minimum":declared_minimum}))
            def large_minimum(rules):
                kwargs={f.name:getattr(rules,f.name) for f in fields(rules) if f.name!="config_hash"}
                kwargs["account_fee_schedule_ref"]=schedule
                kwargs["minimums"]=tuple(replace(m,minimum_amount=declared_minimum) for m in rules.minimums)
                return type(rules).create(**kwargs)
            changed.append(replace(term,reservation_rules=large_minimum(term.reservation_rules),
                final_fill_rules=large_minimum(term.final_fill_rules),final_order_rules=large_minimum(term.final_order_rules)))
        source=replace(source,opening_terms=tuple(changed))
    prepared = prepare_cn_a_share_portfolio_economic_development_backtest(
        request_intent=CashDevelopmentRequestIntent(1, "economic.synthetic.public.v1", window, source.scope.account_id, d.CurrencyId("CNY"), 0),
        provider_inputs=source, build_artifact_manifest=build_manifest(), artifact_reader=store,
        artifact_publisher=store, market_reader=market, publication_root=publication_root)
    bundle, failure = _read_execution_inputs_v9_from_snapshot(store, prepared.execution_request)
    assert failure is None
    resolved = ProfileResolver().resolve(request=prepared.execution_request.request, registry=_registry(source),
        market_bundle_manifest=market.manifest, build_artifact_manifest=bundle.build_artifact_manifest).resolved
    case = _compose_profile_portfolio_economic_execution_case(resolved_request=resolved, market_reader=market,
        semantic_spec=bundle.execution_case_semantic_spec, target_stream=targets, timeline_stream_keys=bundle.timeline_stream_keys,
        timeline_batch_size=64, execution_case_plan=bundle.execution_case_plan)
    return prepared, case, source, store, market
