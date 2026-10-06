"""Public daily-NAV seam; source/metric checks never confer OOS authority."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, time, timedelta
from collections.abc import Mapping
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
import crypto_quant_backtest as bt
import crypto_quant_domain as d
from tests.runtime.providers.test_cn_a_share_portfolio_standard_case_v1 import _sources
from tests.runtime.providers.test_cash_development_provider import build_manifest


def _flat_prepared(root):
    source, _, market, store, targets, window = _sources()
    zone = ZoneInfo("Asia/Shanghai")
    day = source.daily_marks[0].at.instant.to_datetime().astimezone(zone).date()
    when = d.UtcInstant.from_datetime(datetime.combine(day, time(15), zone))
    at = d.SimulationInstant(when, d.TimelinePhase(100, "test_frozen_close"), d.SourceSequence(1))
    daily = replace(source.daily_marks[0], at=at, marks=tuple(replace(m,
        observed_at=when, available_at=when, resolved_at=when, age_nanoseconds=0,
        available_at_instant=at, resolved_at_instant=at) for m in source.daily_marks[0].marks))
    events = []
    for event in targets.events:
        assert isinstance(event.payload, Mapping)
        candidate = dict(cast(Mapping[str, Any], event.payload["candidate"]))
        candidate["targets"] = []
        events.append(replace(event, payload={"schema_version": 1, "candidate": candidate}))
    target_ref = bt.BacktestTargetStreamRepository(reader=store, publisher=store).publish(
        d.ArtifactRef("synthetic_cash_nav_test", 1, d.canonical_sha256("precommitted-flat-cash")),
        bt.PrecomputedTargetStream(targets.stream_key, tuple(events)))
    source = replace(source, scope=replace(source.scope, target_stream_ref=target_ref), daily_marks=(daily,))
    end = d.UtcInstant.from_datetime(datetime.combine(day + timedelta(days=1), time(), zone))
    window = replace(window, end_exclusive=end)
    prepared = bt.prepare_cn_a_share_portfolio_standard_development_backtest(
        request_intent=bt.CashDevelopmentRequestIntent(1, "nav.public.flat-cash.smoke", window,
            source.scope.account_id, d.CurrencyId("CNY"), 0), provider_inputs=source,
        build_artifact_manifest=build_manifest(), artifact_reader=store, artifact_publisher=store,
        market_reader=market, publication_root=root)
    return prepared, store


@pytest.fixture(scope="module")
def flat_completed(tmp_path_factory):
    prepared, store = _flat_prepared(tmp_path_factory.mktemp("public-cash-close-nav"))
    publication = prepared.runtime.run(prepared.execution_request)
    assert type(publication) is bt.BacktestCanonicalPublicationRef
    return prepared, store, publication


def test_public_flat_cash_close_analysis_roundtrip_without_second_engine(flat_completed, monkeypatch):
    prepared, store, publication = flat_completed
    from crypto_quant_backtest.cn_a_share_portfolio_standard_engine_v1 import _CnASharePortfolioStandardEngineV1
    def forbidden(*args, **kwargs):
        pytest.fail("analysis must not run the economic Engine")
    monkeypatch.setattr(_CnASharePortfolioStandardEngineV1, "run", forbidden)
    runtime = bt.CnASharePortfolioDailyNavAnalysisRuntimeV1(reader=store, publisher=store)
    profile = runtime.publish_metric_profile()
    ref = runtime.derive(publication_ref=publication,
        execution_input_ref=prepared.execution_request.execution_input_bundle_ref, metric_profile_ref=profile)
    assert type(ref) is bt.CnASharePortfolioDailyNavAnalysisRefV1
    result = bt.BacktestEvidenceRepository(reader=store).load_cn_a_share_portfolio_daily_nav(ref)
    assert result.simple_period_return == result.maximum_drawdown == "0"
    assert result.initial_equity == result.points[0].equity == d.Money(10_000_000, d.Scale(2), "CNY")
    assert tuple(p.trade_date for p in result.points) == ("2023-08-25",)
    assert result.trade_count == 0 and result.result_grade is bt.ResultGrade.DEVELOPMENT
    assert result.to_canonical_dict()["validation_eligible"] is False
    assert runtime.derive(publication_ref=publication,
        execution_input_ref=prepared.execution_request.execution_input_bundle_ref, metric_profile_ref=profile) == ref


def _value_analysis(tmp_path, units):
    from crypto_quant_foundation import LocalFoundation
    store = LocalFoundation(tmp_path / "passive-values-only")
    profile = bt.CnASharePortfolioDailyNavAnalysisRuntimeV1(reader=store, publisher=store).publish_metric_profile()
    ref = lambda name, version=1: d.ArtifactRef(name, version, "sha256:" + "1" * 64)
    points = tuple(bt.CnASharePortfolioDailyNavPointV1(f"2024-10-{14+n:02d}",
        d.SimulationInstant(d.UtcInstant.from_datetime(datetime(2024, 10, 14+n, 15, tzinfo=ZoneInfo("Asia/Shanghai"))),
            d.TimelinePhase(100, "value-only-close"), d.SourceSequence(n+1)),
        d.Money(v, d.Scale(2), "CNY"), *("sha256:" + "2" * 64 for _ in range(4))) for n, v in enumerate(units))
    return bt.CnASharePortfolioDailyNavAnalysisV1(profile,
        bt.BacktestCanonicalPublicationRef(ref("canonical_publication_manifest")),
        ref("backtest_execution_input_bundle", 8), ref("backtest_profile_portfolio_definition"),
        ref("engine_execution_result"), "sha256:" + "3" * 64, "sha256:" + "4" * 64,
        d.Money(10_000, d.Scale(2), "CNY"), points, 0)


@pytest.mark.parametrize("units,returned,drawdown", (
    ((11_000, 9_900, 12_000), "0.2", "0.1"),
    ((8_000,), "-0.2", "0.2"),
    ((30_000, 20_000), "1", "0.333333333333333333"),
    ((10_000, 10_000), "0", "0"),
))
def test_public_value_peak_initial_equity_and_rounding(tmp_path, units, returned, drawdown):
    # Passive worked examples, not completed source evidence or admissible refs.
    value = _value_analysis(tmp_path, units)
    assert value.simple_period_return == returned
    assert value.maximum_drawdown == drawdown
    assert value.to_canonical_dict()["formal_publication_eligible"] is False


@pytest.mark.parametrize("part", ("duplicate", "reverse", "zero", "currency", "scale", "clock", "grade", "count"))
def test_public_value_rejects_invalid_series_and_grade(tmp_path, part):
    value = _value_analysis(tmp_path, (11_000, 9_900))
    with pytest.raises((ValueError, TypeError)):
        if part == "duplicate":
            replace(value, points=(value.points[0], value.points[0]))
        elif part == "reverse":
            replace(value, points=tuple(reversed(value.points)))
        elif part == "zero":
            replace(value.points[0], equity=d.Money(0, d.Scale(2), "CNY"))
        elif part == "currency":
            replace(value.points[0], equity=d.Money(10_000, d.Scale(2), "USD"))
        elif part == "scale":
            replace(value.points[0], equity=d.Money(10_000, d.Scale(3), "CNY"))
        elif part == "clock":
            replace(value.points[0], occurred_at=value.points[0].occurred_at.instant)
        elif part == "grade":
            replace(value, result_grade=bt.ResultGrade.DECISION_GRADE)
        else:
            replace(value, trade_count=True)


@pytest.mark.parametrize("part", ("missing_input", "missing_definition", "missing_target", "foreign_initial", "extra_source_role", "wrong_profile", "wrong_publication"))
def test_public_runtime_rejects_missing_or_replaced_sources_before_publish(flat_completed, part):
    prepared, original, publication = flat_completed
    store = type(original)()
    store.values.update(original.values)
    runtime = bt.CnASharePortfolioDailyNavAnalysisRuntimeV1(reader=store, publisher=store)
    profile = runtime.publish_metric_profile()
    input_ref = prepared.execution_request.execution_input_bundle_ref
    input_envelope = store.values[input_ref]
    import json
    payload = json.loads(d.canonical_bytes(input_envelope.payload))
    if part == "missing_input":
        del store.values[input_ref]
    elif part in ("missing_definition", "missing_target"):
        role = "definition" if part == "missing_definition" else "target_stream"
        raw = dict(payload["execution_case_plan"]["source_refs"])[role]
        del store.values[d.ArtifactRef(raw["artifact_type"], raw["schema_version"], raw["content_hash"])]
    elif part == "foreign_initial":
        payload["execution_case_plan"]["financial_state"]["initial_snapshot"]["equity"]["units"] += 1
        input_ref = store.put(envelope=d.ArtifactEnvelope.create("backtest_execution_input_bundle", 8, payload))
    elif part == "extra_source_role":
        payload["execution_case_plan"]["source_refs"].append(["unexpected", d.ArtifactRef(
            "unpublished_role", 1, "sha256:" + "5" * 64).to_canonical_dict()])
        input_ref = store.put(envelope=d.ArtifactEnvelope.create("backtest_execution_input_bundle", 8, payload))
    elif part == "wrong_profile":
        profile = d.ArtifactRef("cn_a_share_portfolio_daily_nav_metric_profile", 1, "sha256:" + "6" * 64)
    else:
        publication = bt.BacktestCanonicalPublicationRef(d.ArtifactRef(
            "canonical_publication_manifest", 1, "sha256:" + "7" * 64))
    before = frozenset(store.values)
    with pytest.raises((ValueError, TypeError, KeyError, bt.BacktestEvidenceError, bt.BacktestTargetStreamError)):
        runtime.derive(publication_ref=publication, execution_input_ref=input_ref, metric_profile_ref=profile)
    assert frozenset(store.values) == before


def test_new_nav_ref_cannot_enter_old_simple_return_analysis(flat_completed):
    prepared, store, publication = flat_completed
    runtime = bt.CnASharePortfolioDailyNavAnalysisRuntimeV1(reader=store, publisher=store)
    profile = runtime.publish_metric_profile()
    ref = runtime.derive(publication_ref=publication,
        execution_input_ref=prepared.execution_request.execution_input_bundle_ref, metric_profile_ref=profile)
    repo = bt.BacktestEvidenceRepository(reader=store)
    with pytest.raises(bt.BacktestEvidenceError) as error:
        repo.load_analysis(cast(Any, ref))
    assert error.value.code is bt.BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH
    with pytest.raises(ValueError, match="accepted metric profile"):
        bt.BacktestAnalysisRuntime(store).derive(repo.load_completed(publication), profile)


@pytest.mark.parametrize("part", ("equity", "snapshot_hash", "execution_hash", "date", "upgrade", "missing_input", "missing_definition"))
def test_public_cold_read_rejects_rehashed_substitution_and_missing_sources(flat_completed, part):
    import json
    prepared, original, publication = flat_completed
    store = type(original)()
    store.values.update(original.values)
    runtime = bt.CnASharePortfolioDailyNavAnalysisRuntimeV1(reader=store, publisher=store)
    profile = runtime.publish_metric_profile()
    ref = runtime.derive(publication_ref=publication,
        execution_input_ref=prepared.execution_request.execution_input_bundle_ref, metric_profile_ref=profile)
    value = bt.BacktestEvidenceRepository(reader=store).load_cn_a_share_portfolio_daily_nav(ref)
    if part == "missing_input":
        del store.values[value.execution_input_ref]
    elif part == "missing_definition":
        del store.values[value.definition_ref]
    else:
        raw = json.loads(d.canonical_bytes(store.values[ref.artifact_ref].payload))
        if part == "equity":
            raw["points"][0]["equity"]["units"] += 1
            raw["simple_period_return"] = "0.0000001"  # Valid arithmetic, false source snapshot.
        elif part == "snapshot_hash":
            raw["points"][0]["snapshot_hash"] = "sha256:" + "8" * 64
        elif part == "execution_hash":
            raw["source_execution_result_hash"] = "sha256:" + "9" * 64
        elif part == "date":
            raw["points"][0]["trade_date"] = "2023-08-28"
            raw["points"][0]["occurred_at"]["instant"]["epoch_nanoseconds"] += 3 * 86_400_000_000_000
        else:
            raw["validation_eligible"] = True
        altered = store.put(envelope=d.ArtifactEnvelope.create("cn_a_share_portfolio_daily_nav_analysis", 1, raw))
        ref = bt.CnASharePortfolioDailyNavAnalysisRefV1(altered)
    before = frozenset(store.values)
    with pytest.raises((ValueError, TypeError, KeyError, bt.BacktestEvidenceError)):
        bt.BacktestEvidenceRepository(reader=store).load_cn_a_share_portfolio_daily_nav(ref)
    assert frozenset(store.values) == before  # Cold read never publishes or falls back to prior success.


def test_public_runtime_accepts_no_caller_equity_or_unverified_completion(flat_completed):
    prepared, store, publication = flat_completed
    runtime = bt.CnASharePortfolioDailyNavAnalysisRuntimeV1(reader=store, publisher=store)
    profile = runtime.publish_metric_profile()
    before = frozenset(store.values)
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        runtime.derive(publication_ref=publication,
            execution_input_ref=prepared.execution_request.execution_input_bundle_ref, metric_profile_ref=profile,
            **{"equity": d.Money(99_999_999, d.Scale(2), "CNY")})
    with pytest.raises(TypeError, match="exact standard canonical"):
        runtime.derive(publication_ref=cast(Any, object()),
            execution_input_ref=prepared.execution_request.execution_input_bundle_ref, metric_profile_ref=profile)
    assert frozenset(store.values) == before


@pytest.mark.parametrize("mode,reason", (("deposit", "external cash flows"), ("cross_clock", "same-clock opposite")))
def test_public_runtime_rejects_nonatomic_transfers_and_post_initial_deposits(flat_completed, monkeypatch, mode, reason):
    import crypto_quant_trading as t
    prepared, store, publication = flat_completed
    completed = bt.BacktestEvidenceRepository(reader=store).load_completed(publication)
    initial = completed.execution_summary.final_journal.entries[0]
    at = d.UtcInstant.from_datetime(datetime(2023, 8, 25, 10, tzinfo=ZoneInfo("Asia/Shanghai")))
    clock = d.SimulationInstant(at, d.TimelinePhase(50, "native_transfer_source"), d.SourceSequence(1))
    source_id = "cn.portfolio.live-venue-funding.development.v1:sha256:" + "f" * 64
    debit = replace(initial, journal_entry_id=d.DomainId(d.DomainIdKind.JOURNAL, "jnl_" + "b" * 64),
        entry_type=d.AccountingEntryType.CAPITAL_DEPOSITED if mode == "deposit" else d.AccountingEntryType.CAPITAL_TRANSFERRED,
        effective_time=at, recorded_at=clock, source_ids=(source_id,),
        balance_changes=(d.BalanceChange(initial.balance_changes[0].key,
            d.Money(100 if mode == "deposit" else -100, d.Scale(2), "CNY")),))
    added = (debit,)
    if mode == "cross_clock":
        later = d.UtcInstant(at.epoch_nanoseconds + 3_600_000_000_000)
        credit = replace(debit, journal_entry_id=d.DomainId(d.DomainIdKind.JOURNAL, "jnl_" + "c" * 64),
            venue_id=d.VenueId("xshe"), effective_time=later,
            recorded_at=d.SimulationInstant(later, clock.phase, d.SourceSequence(2)),
            balance_changes=(d.BalanceChange(d.CashBalanceKey(initial.account_id, d.VenueId("xshe"), d.CurrencyId("CNY")),
                d.Money(100, d.Scale(2), "CNY")),))
        added += (credit,)
    altered = replace(completed, execution_summary=replace(completed.execution_summary,
        final_journal=t.AccountingJournal.from_entries((*completed.execution_summary.final_journal.entries, *added))))
    # Fault injection at the approved public repository seam, not qualifying a
    # forged publication: exercise flow precedence before valuation/publication.
    monkeypatch.setattr(bt.BacktestEvidenceRepository, "load_completed", lambda self, ref: altered)
    runtime = bt.CnASharePortfolioDailyNavAnalysisRuntimeV1(reader=store, publisher=store)
    profile = runtime.publish_metric_profile()
    before = frozenset(store.values)
    with pytest.raises(ValueError, match=reason):
        runtime.derive(publication_ref=publication,
            execution_input_ref=prepared.execution_request.execution_input_bundle_ref, metric_profile_ref=profile)
    assert frozenset(store.values) == before

def test_public_nav_surface_and_new_profile_identity():
    names = tuple("CnASharePortfolioDailyNav" + suffix + "V1" for suffix in
                  ("MetricProfile", "Point", "Analysis", "AnalysisRef", "AnalysisRuntime"))
    assert all(hasattr(bt, name) and name in bt.__all__ for name in names)
    profile = bt.CnASharePortfolioDailyNavMetricProfileV1()
    value = profile.to_canonical_dict()
    assert value["drawdown_sampling"] == "initial_peak_and_every_frozen_trading_close"
    assert value["rounding"] == "half_even_18_decimal_places"
    envelope = d.ArtifactEnvelope.create("cn_a_share_portfolio_daily_nav_metric_profile", 1, profile)
    assert d.ArtifactRef.from_envelope(envelope).artifact_type != "backtest_metric_profile"
    assert bt.BacktestMetricProfile("simple_period_return.fill_count.v1", 1).to_canonical_dict()[
        "drawdown_sampling"] == "not_applicable"
