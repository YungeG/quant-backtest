"""#30 approved public preparation/run/evidence seams; retained Jan 2/3 sources.

Targets are an explicit wiring scenario, not a strategy/research experiment.
The account is a declared simulated cash account, never broker authority.
"""
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from functools import cache
from pathlib import Path
import hashlib
import json
import sys

import pytest

import crypto_quant_backtest as bt
import crypto_quant_domain as d
import crypto_quant_trading as t
from crypto_quant_trading.profiles import cn_a_share as cn
from crypto_quant_market_data import InMemoryMarketBundleReader, MarketBundleRef, MarketEvent
from tests.runtime.profiles.cn_a_share.test_000703_development_profile_v2 import (
    _request, _rebind, _retained_source, ROOT, CALENDAR, january_2024_commission_scenarios,
    verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v2,
)
from tests.runtime.providers.test_cash_development_provider import _Cas, build_manifest
from tools.acquisition.cn_a_share_tushare_000703_month_order_authority_v1 import (
    verify_tushare_000703_month_order_authority_v1,
)
from tools.acquisition.cn_a_share_szse_trading_rules_2023_fixed_source_v1 import (
    verify_szse_trading_rules_2023_fixed_source_v1,
)
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")
ORDER = ROOT / "evidence/tushare-000703-month-order-authority-202401-v1"


def instant(day, hour=0, minute=0):
    return d.UtcInstant.from_datetime(datetime(2024, 1, day, hour, minute, tzinfo=SHANGHAI))


def digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def row(path):
    data = json.loads(path.read_bytes())["data"]
    [values] = data["items"]
    return dict(zip(data["fields"], values, strict=True))


@cache
def retained_profile():
    verified = verify_tushare_000703_month_order_authority_v1(ORDER,
        calendar_authority_dir=CALENDAR,
        minute_authority_root=ROOT / "evidence/tushare-minute-000703-development-month-202401-v2/sessions")
    assert verified["development_only"] and not verified["deployment_authorized"]
    declaration_hash = digest(ORDER / "declaration.json")
    assert verified["declaration_sha256"] == declaration_hash
    szse = verify_szse_trading_rules_2023_fixed_source_v1(ROOT / "evidence/szse-trading-rules-2023-fixed-source-v1")
    request = _request()
    instrument = replace(request.instrument_scope,
        source_snapshot_hash=digest(ORDER / "response/stock-basic.json"),
        rule_context=replace(request.instrument_scope.rule_context, source_hash=declaration_hash,
            source_key="tushare.000703.retained-month-order-authority.202401.v1"))
    account_declaration = {"type": "test_simulated_cash_account_declaration", "schema_version": 1,
        "account_id": request.account_scope.account_id, "coverage_from": instant(2),
        "coverage_to_exclusive": request.timeline_window.end_exclusive,
        "cash_only": True, "domestic": True, "margin_or_short": False, "broker_authority": False}
    account = replace(request.account_scope, source_snapshot_hash=d.canonical_sha256(account_declaration))
    attachment_hash = szse["attachment_sha256"]
    assert type(attachment_hash) is str
    band = replace(request.order_rule_book.bands[0],
        source_ref=cn.CnAShareRuleSourceRef("szse-trading-rules-2023", attachment_hash))
    request = _rebind(request, instrument_scope=instrument, account_scope=account,
        order_rule_book=cn.CnAShareOrderRuleBook("szse-main-2023.retained-202401", 1, (band,)))
    outcome = bt.CnAShareProfileComposerV2().compose(request)
    assert outcome.result is not None, outcome.failure
    return outcome.result


@cache
def profile_with_verified_successor():
    profile = retained_profile()
    root = ROOT / "evidence/tushare-calendar-szse-development-month-202402-v1"
    raw, snapshot = _retained_source(root, "response/trade-calendar.json")
    verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v2(raw, snapshot, digest(root / "acquisition-receipt.json"))
    data = json.loads((root / "response/trade-calendar.json").read_bytes())["data"]
    days = {day.local_date: day for day in profile.request.calendar.days}
    for values in data["items"]:
        value = dict(zip(data["fields"], values, strict=True))
        day = cn.CnAShareFrozenCalendarDay(datetime.strptime(value["cal_date"], "%Y%m%d").date(),
            cn.CnAShareCalendarDayKind.TRADING if value["is_open"] == 1 else cn.CnAShareCalendarDayKind.FROZEN_HOLIDAY)
        assert day.local_date not in days or days[day.local_date] == day
        days[day.local_date] = day
    ordered = tuple(days[key] for key in sorted(days))
    calendar = cn.CnAShareFrozenCalendar(profile.request.calendar.venue_id, profile.request.calendar.calendar_id,
        ordered[0].local_date, ordered[-1].local_date + timedelta(days=1), ordered)
    request = _rebind(profile.request, calendar=calendar)
    # Calendar successor only: never widen the finite January fees.
    assert request.market_fee_rule_book == profile.request.market_fee_rule_book
    assert request.stamp_duty_rule_book == profile.request.stamp_duty_rule_book
    outcome = bt.CnAShareProfileComposerV2().compose(request)
    assert outcome.result is not None, outcome.failure
    return outcome.result


def daily_authorities(profile, days=(2, 3)):
    request = profile.request
    instrument = request.instrument_scope.instrument.instrument_id
    data = json.loads((CALENDAR / "response/trade-calendar.json").read_bytes())["data"]
    calendar_rows = {values[1]: dict(zip(data["fields"], values, strict=True)) for values in data["items"]}
    result = []
    for day in days:
        key = f"202401{day:02}"
        daily_path, limit_path = ORDER / f"response/{key}/daily.json", ORDER / f"response/{key}/stk-limit.json"
        daily, limits = row(daily_path), row(limit_path)
        session = cn.CnAShareCashSessionModel(request.calendar).resolve_session(
            cn.CnAShareSessionQuery(instrument.venue, instant(day, 9, 35))).result
        assert session is not None and session.session_id is not None and session.trading_date is not None
        def price(value):
            return d.Price(int(Decimal(str(value)) * 100), d.Scale(2), str(instrument), "CNY")
        previous = cn.CnASharePreviousCloseEvidence(instrument,
            d.TradingDate("CN.XSHE", datetime.strptime(calendar_rows[key]["pretrade_date"], "%Y%m%d").date()),
            price(daily["pre_close"]), instant(day, 9, 30), digest(daily_path))
        status = cn.CnAShareTradeStatusEvidence(instrument, session.session_id, cn.CnAShareTradeStatus.NORMAL,
            instant(day, 9, 30), instant(day, 15), request.instrument_scope.rule_context.source_hash)
        members = tuple((f"response/{key}/{name}.json", (ORDER / f"response/{key}/{name}.json").read_bytes().decode("utf-8"))
            for name in ("daily", "stk-limit", "stock-st", "suspend-d-r", "suspend-d-s"))
        result.append(bt.CnAShareDailyOrderAuthority(session.trading_date, status, previous,
            price(limits["down_limit"]), price(limits["up_limit"]), digest(limit_path), members))
    return tuple(result)


@cache
def actual_build_manifest():
    base = build_manifest()
    sources = {bt.BuildArtifactRole.DECISION_SOURCE: Path(__file__),
        bt.BuildArtifactRole.TRADING_DOMAIN: ROOT / "packages/trading-domain/src",
        bt.BuildArtifactRole.TRADING_KERNEL: ROOT / "packages/trading-kernel/src",
        bt.BuildArtifactRole.MARKET_DATA_CONTRACTS: ROOT / "packages/market-data-contracts/src",
        bt.BuildArtifactRole.BACKTEST_RUNTIME: ROOT / "packages/backtest-runtime/src"}
    artifacts = []
    for artifact in base.artifacts:
        root = sources[artifact.role]
        # Bind actual dirty source bytes, not the old synthetic build hashes.
        paths = (root,) if root.is_file() else tuple(sorted(root.rglob("*.py")))
        assert paths
        snapshot_hash = d.canonical_sha256(tuple((str(path.relative_to(ROOT)), digest(path)) for path in paths))
        artifacts.append(replace(artifact, install_mode=bt.ArtifactInstallMode.EDITABLE,
            source_tree_state=bt.SourceTreeState.DIRTY, content_hash=None, source_snapshot_hash=snapshot_hash))
    return replace(base, artifacts=tuple(artifacts), dependency_lock_hash=digest(ROOT / "uv.lock"),
        runtime_libraries=(bt.RuntimeLibraryRef("python", sys.version.split()[0], d.canonical_sha256(sys.version)),),
        provenance=bt.BuildProvenance("0907d1bf688424120320052fab50e757f056cf60", "public-cn-test", str(ROOT),
            retained_profile().request.composed_at.instant))


def inputs():
    profile = retained_profile()
    return bt.CnAShareDevelopmentProviderInputs(1, actual_build_manifest(), profile,
        "cn-public-wiring", d.StrategySleeveId("cn-public-wiring.primary"),
        d.Money(10_000_000, d.Scale(2), "CNY"), daily_authorities(profile),
        (ORDER / "declaration.json").read_bytes().decode("utf-8"))


def intent():
    return bt.CashDevelopmentRequestIntent(1, "test:cn-public-retained",
        bt.TimelineWindow(instant(2), instant(2, 9, 30), instant(4)),
        retained_profile().request.account_scope.account_id, d.CurrencyId("CNY"), 7)


def target_stream(provider, *, times=None, weights=("0.5", "0", "0"), expires_at=None):
    times = times or (instant(2, 9, 35), instant(2, 10), instant(3, 9, 35))
    expires_at = expires_at or intent().timeline_window.end_exclusive
    iid = provider.profile.request.instrument_scope.instrument.instrument_id
    events = []
    for i, (at, weight) in enumerate(zip(times, weights, strict=True)):
        payload = {"schema_version": 1, "strategy_id": provider.strategy_id, "sleeve_id": provider.sleeve_id.value,
            "decision_time": at.epoch_nanoseconds, "observed_through": at.epoch_nanoseconds,
            "effective_time": at.epoch_nanoseconds, "expires_at": expires_at.epoch_nanoseconds,
            "targets": [{"instrument_id": {"venue": iid.venue.value, "stable_key": iid.stable_key}, "value": weight}],
            "confidence": "1", "reason": "explicit Jan2/3 public wiring sentinel", "evidence": {"research_execute": False}}
        events.append(MarketEvent(f"cn-public-target:{i}", "targets", bt.TARGET_STREAM_EVENT_TYPE, bt.TARGET_STREAM_CAPABILITY,
            None, at, at, d.TimelinePhase(100, "decision"), d.SourceSequence(i), "public-wiring.v1", None,
            "test.cn-public-wiring", d.canonical_sha256(payload), {"schema_version": 1, "candidate": payload}))
    return bt.PrecomputedTargetStream("targets", tuple(events))


def market_reader(provider):
    [authority] = provider.profile.request.minute_authorities
    return InMemoryMarketBundleReader(MarketBundleRef.from_manifest(authority.manifest), authority.manifest,
        {authority.events[0].stream_key: authority.events})


def prepare(tmp_path, *, provider=None, stream=None, reader=None, store=None, request_intent=None):
    provider = provider or inputs()
    store = store or _Cas()
    context = store.put(envelope=d.ArtifactEnvelope.create("test_cn_public_context", 1, {"test": "#30 public preparation"}))
    ref = bt.BacktestTargetStreamRepository(reader=store, publisher=store).publish(context, stream or target_stream(provider))
    prepared = bt.prepare_cn_a_share_development_backtest(request_intent=request_intent or intent(), provider_inputs=provider,
        target_stream_ref=ref, artifact_reader=store, artifact_publisher=store, market_reader=reader or market_reader(provider),
        publication_root=tmp_path)
    return prepared, store


def engine_payload(store, publication):
    manifest = store.read(ref=publication.to_artifact_ref()).envelope.payload
    assert manifest["deployment_authorized"] is False
    entry = next(row for row in manifest["artifacts"] if row["artifact_type"] == "canonical_attempt_ref")
    attempt = store.read(ref=d.ArtifactRef(entry["artifact_type"], entry["schema_version"], entry["content_hash"])).envelope.payload
    return store.read(ref=d.ArtifactRef("engine_execution_result", 1, attempt["engine_result_artifact_content_hash"])).envelope.payload


def test_public_retained_two_session_roundtrip_owns_real_fills_fees_and_t1(tmp_path):
    prepared, store = prepare(tmp_path)
    assert type(prepared) is bt.PreparedBacktestExecution
    assert prepared.execution_request.schema_version == 7
    assert not (tmp_path / "runs").exists()
    publication = prepared.runtime.run(prepared.execution_request)
    assert type(publication) is bt.BacktestCanonicalPublicationRef
    completed = bt.BacktestEvidenceRepository(store).load_completed(publication)
    result = completed.execution_summary
    assert [(fill.side, fill.quantity.units, fill.price.units, fill.execution_time) for fill in result.fills] == [
        (d.OrderSide.BUY, 7400, 673, instant(2, 9, 40)), (d.OrderSide.SELL, 7400, 672, instant(3, 9, 40))]
    assert result.final_portfolio_snapshot.positions == ()
    assert result.final_portfolio_snapshot.fees.units == 8101
    assert result.final_portfolio_snapshot.cash[0].amount.units == 9_984_499
    assert completed.result_grade.value == "development"
    payload = engine_payload(store, publication)
    assert len(payload["order_streams"]) == 2
    closure = next(a["payload"] for a in payload["financial_artifacts"] if a["role"] == "runtime.identity_closure")
    rows = {row["binding_key"]: row for row in closure["dispositions"]}
    assert rows["order.1.0"]["reason"] == "pending_position_settlement"
    assert rows["fill.0"]["reason"] == "no_active_order"
    bundle = store.read(ref=prepared.execution_request.execution_input_bundle_ref).envelope.payload
    plan = bundle["execution_case_plan"]
    assert len(plan["bar_executions"]) == 96  # Both endpoint labels retained, no valid-close filtering.
    assert all("order_id" not in bar for bar in plan["bar_executions"])
    assert all(set(slot) == {"type", "schema_version", "balance_key", "obligation_id", "recorded_event_id", "applied_event_id"}
        for bar in plan["bar_executions"] for slot in bar["accounting_plan"]["settlement_slots"])
    source_ref = plan["bar_executions"][0]["accounting_plan"]["semantic_payload"]["preparation_authority_ref"]
    source = store.read(ref=d.ArtifactRef(source_ref["artifact_type"], source_ref["schema_version"], source_ref["content_hash"])).envelope.payload
    assert source["profile"]["profile_hash"] == retained_profile().profile_hash
    assert source["profile"]["deployment_authorized"] is False
    assert source["daily_order_authorities"][0]["previous_close"]["source_hash"] == digest(ORDER / "response/20240102/daily.json")
    assert prepared.runtime.run(prepared.execution_request) == publication


@pytest.mark.parametrize("change", ("daily_missing", "daily_extra", "daily_limit", "late_previous", "wrong_previous_date",
    "source_missing_close", "source_open", "signal_before_receipt", "signal_noon", "signal_future_observation", "wrong_account", "fee_horizon"))
def test_public_preparation_fails_closed_before_publication(change, tmp_path):
    provider, request, store = inputs(), intent(), _Cas()
    reader, stream = market_reader(provider), target_stream(provider)
    if change == "daily_missing":
        provider = replace(provider, daily_order_authorities=provider.daily_order_authorities[:1])
    elif change == "daily_extra":
        provider = replace(provider, daily_order_authorities=daily_authorities(provider.profile, (2, 3, 4)))
    elif change in {"daily_limit", "late_previous", "wrong_previous_date"}:
        first, second = provider.daily_order_authorities
        if change == "daily_limit":
            first = replace(first, upper_price_limit=replace(first.upper_price_limit, units=first.upper_price_limit.units + 1))
        elif change == "late_previous":
            first = replace(first, previous_close=replace(first.previous_close, available_at=instant(2, 9, 35)))
        else:
            second = replace(second, previous_close=replace(second.previous_close,
                reference_trading_date=first.previous_close.reference_trading_date))
        provider = replace(provider, daily_order_authorities=(first, second))
    elif change.startswith("source_"):
        [authority] = provider.profile.request.minute_authorities
        events = authority.events[1:]
        if change == "source_open":
            events = tuple(replace(event, event_type=bt.BAR_OPEN_EVENT_TYPE, capability=bt.BAR_OPEN_CAPABILITY) for event in events)
        reader = InMemoryMarketBundleReader.build(bundle_key="tampered.source", schema_version=1,
            coverage_start=authority.manifest.coverage_start, coverage_end_exclusive=authority.manifest.coverage_end_exclusive,
            instrument_catalog_hash=authority.manifest.instrument_catalog_hash, capabilities=(events[0].capability,),
            streams={events[0].stream_key: events})
    elif change.startswith("signal_"):
        first, *rest = stream.events
        if change == "signal_before_receipt":
            first = replace(first, phase=d.TimelinePhase(0, "market_data"))
        elif change == "signal_noon":
            first = replace(first, event_time=instant(2, 12), available_time=instant(2, 12))
        else:
            candidate = first.payload["candidate"]
            assert isinstance(candidate, Mapping)
            payload = dict(candidate)
            payload["observed_through"] = first.event_time.epoch_nanoseconds + 1
            first = replace(first, payload={"schema_version": 1, "candidate": payload})
        stream = bt.PrecomputedTargetStream("targets", (first, *rest))
    elif change == "wrong_account":
        request = replace(request, execution_account_id="foreign-account")
    else:
        request = replace(request, timeline_window=replace(request.timeline_window,
            end_exclusive=d.UtcInstant(provider.profile.request.timeline_window.end_exclusive.epoch_nanoseconds + 1)))
    with pytest.raises(ValueError):
        prepare(tmp_path, provider=provider, stream=stream, reader=reader, store=store, request_intent=request)
    assert not (tmp_path / "runs").exists()
    assert not any(ref.artifact_type in {"backtest_request", "backtest_execution_input_bundle", "cn_a_share_development_preparation_authority"}
        for ref in store.by_ref)


@pytest.mark.parametrize("signal, expected", ((instant(2, 11, 25), instant(2, 11, 30)),
    (instant(2, 11, 30), instant(2, 13, 5)), (instant(2, 15), instant(3, 9, 35))))
def test_public_first_later_close_preserves_endpoints_lunch_and_next_session(tmp_path, signal, expected):
    provider = inputs()
    prepared, store = prepare(tmp_path, provider=provider,
        stream=target_stream(provider, times=(signal,), weights=("0.5",)))
    publication = prepared.runtime.run(prepared.execution_request)
    assert type(publication) is bt.BacktestCanonicalPublicationRef
    [fill] = bt.BacktestEvidenceRepository(store).load_completed(publication).execution_summary.fills
    assert fill.execution_time == expected
    event = next(event for authority in provider.profile.request.minute_authorities for event in authority.events if event.event_time == expected)
    assert fill.price == fill.reference_price == bt.BarCloseObservation.from_event(event).close_price


@pytest.mark.parametrize("scenario_key, expected_fee", (("3bps", 1422), ("5bps", 1422), ("8bps", 1498)))
def test_public_bound_account_scenarios_apply_actual_order_minimum(tmp_path, scenario_key, expected_fee):
    provider = inputs()
    scenario = next(value for value in january_2024_commission_scenarios() if value.scenario_key == scenario_key)
    commission = bt.CnAShareDevelopmentCommissionScenarioV2(scenario.scenario_key, scenario.commission_rate,
        scenario.account_fee_schedule_ref, True)
    request = _rebind(provider.profile.request, commission_scenario=commission)
    profile = bt.CnAShareProfileComposerV2().compose(request).result
    assert profile is not None
    provider = replace(provider, profile=profile, initial_cash=d.Money(2_000_000, d.Scale(2), "CNY"))
    prepared, store = prepare(tmp_path, provider=provider, stream=target_stream(provider, weights=("0.35", "0", "0")))
    publication = prepared.runtime.run(prepared.execution_request)
    assert type(publication) is bt.BacktestCanonicalPublicationRef
    summary = bt.BacktestEvidenceRepository(store).load_completed(publication).execution_summary
    assert [(fill.side, fill.quantity.units) for fill in summary.fills] == [(d.OrderSide.BUY, 1000), (d.OrderSide.SELL, 1000)]
    assert summary.final_portfolio_snapshot.fees.units == expected_fee
    assert summary.final_portfolio_snapshot.positions == ()


@pytest.mark.parametrize("keep_source_hashes", (False, True))
def test_public_cannot_substitute_coherent_daily_economics_with_unretained_hashes(tmp_path, keep_source_hashes):
    provider = inputs()
    first, second = provider.daily_order_authorities
    # Coherent 10% bounds would pass a rules-only check; none are retained facts.
    changed = replace(first, previous_close=replace(first.previous_close,
        price=d.Price(700, d.Scale(2), "xshe:000703", "CNY"), source_hash="sha256:" + "a" * 64),
        lower_price_limit=d.Price(630, d.Scale(2), "xshe:000703", "CNY"),
        upper_price_limit=d.Price(770, d.Scale(2), "xshe:000703", "CNY"),
        price_limit_source_hash="sha256:" + "b" * 64)
    if keep_source_hashes:
        changed = replace(changed, price_limit_source_hash=first.price_limit_source_hash,
            previous_close=replace(changed.previous_close, source_hash=first.previous_close.source_hash))
    with pytest.raises(ValueError, match="retained"):
        altered = replace(provider, daily_order_authorities=(changed, second))
        prepare(tmp_path, provider=altered)
    assert not (tmp_path / "runs").exists()


def test_public_month_end_receipt_keeps_february_settlement_pending_without_extending_fees(tmp_path):
    provider = inputs()
    profile = profile_with_verified_successor()
    end = profile.request.timeline_window.end_exclusive
    request = replace(intent(), timeline_window=bt.TimelineWindow(instant(30), instant(30, 9, 30), end))
    provider = replace(provider, profile=profile, daily_order_authorities=daily_authorities(profile, (30, 31)))
    prepared, store = prepare(tmp_path, provider=provider, request_intent=request,
        stream=target_stream(provider, times=(instant(31, 14, 55),), weights=("0.5",), expires_at=end))
    publication = prepared.runtime.run(prepared.execution_request)
    assert type(publication) is bt.BacktestCanonicalPublicationRef
    completed = bt.BacktestEvidenceRepository(store).load_completed(publication)
    [fill] = completed.execution_summary.fills
    assert fill.execution_time == instant(31, 15)
    payload = engine_payload(store, publication)
    settlement = next(a["payload"]["result"] for a in payload["financial_artifacts"] if a["role"].startswith("settlement_resolution."))
    assert settlement["position_availability_time"]["epoch_nanoseconds"] == end.epoch_nanoseconds
    closure = next(a["payload"] for a in payload["financial_artifacts"] if a["role"] == "runtime.identity_closure")
    rows = {row["binding_key"]: row for row in closure["dispositions"]}
    assert rows["settlement-event.applied.95.1"]["reason"] == "pending_beyond_window"
    assert completed.execution_summary.final_portfolio_snapshot.positions[0].quantity == fill.quantity


def test_public_full_january_retained_route_covers_all_1056_closes_and_replays(tmp_path):
    provider = inputs()
    profile = profile_with_verified_successor()
    days = tuple(day.local_date.day for day in profile.request.calendar.days
        if day.kind is cn.CnAShareCalendarDayKind.TRADING and day.local_date.strftime("%Y%m") == "202401")
    end = profile.request.timeline_window.end_exclusive
    provider = replace(provider, profile=profile, daily_order_authorities=daily_authorities(profile, days))
    request = replace(intent(), timeline_window=replace(intent().timeline_window, end_exclusive=end))
    prepared, store = prepare(tmp_path, provider=provider, request_intent=request,
        stream=target_stream(provider, expires_at=end))
    bundle = store.read(ref=prepared.execution_request.execution_input_bundle_ref).envelope.payload
    assert len(bundle["execution_case_plan"]["bar_executions"]) == 1056
    publication = prepared.runtime.run(prepared.execution_request)
    assert type(publication) is bt.BacktestCanonicalPublicationRef
    completed = bt.BacktestEvidenceRepository(store).load_completed(publication)
    summary = completed.execution_summary
    assert [(fill.price.units, fill.quantity.units, fill.execution_time) for fill in summary.fills] == [
        (673, 7400, instant(2, 9, 40)), (672, 7400, instant(3, 9, 40))]
    assert summary.final_portfolio_snapshot.positions == ()
    assert summary.final_portfolio_snapshot.cash[0].amount.units == 9_984_499
    assert summary.final_portfolio_snapshot.fees.units == 8101
    assert prepared.runtime.run(prepared.execution_request) == publication


@pytest.mark.parametrize("change", ("declaration_bytes", "member_bytes", "declaration_hash"))
def test_public_retained_input_bytes_cannot_be_replaced_by_equivalent_json(tmp_path, change):
    provider = inputs()
    if change == "declaration_bytes":
        provider = replace(provider, order_authority_declaration_json=" " + provider.order_authority_declaration_json)
    elif change == "member_bytes":
        first, second = provider.daily_order_authorities
        key, raw = first.source_members[0]
        first = replace(first, source_members=((key, " " + raw), *first.source_members[1:]))
        provider = replace(provider, daily_order_authorities=(first, second))
    else:
        declaration = json.loads(provider.order_authority_declaration_json)
        declaration["raw_members"]["response/20240102/daily.json"]["sha256"] = "sha256:" + "e" * 64
        provider = replace(provider, order_authority_declaration_json=json.dumps(declaration))
    with pytest.raises(ValueError, match="retained"):
        prepare(tmp_path, provider=provider)
    assert not (tmp_path / "runs").exists()
