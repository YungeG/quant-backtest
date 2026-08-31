from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import crypto_quant_backtest.binance_usdm_tradifi_case_planner as case_planner
import pytest
from crypto_quant_backtest import DeterministicBarEngine
from crypto_quant_backtest.binance_usdm_tradifi_case_planner import (
    _expected_artifact_roles,
    _identity_plan,
    _price_event,
    plan_binance_usdm_tradifi_case_v1,
)
from crypto_quant_domain import Money, PricePurpose
from crypto_quant_market_data import (
    InMemoryMarketBundleReader,
    MarketBundleManifest,
    MarketStreamManifest,
)
from crypto_quant_trading.profiles.binance_usdm import BinanceUsdmFundingSourceModelV2

from tests.runtime.providers.test_binance_usdm_tradifi_preparation import _resolve
from tests.runtime.providers.test_binance_usdm_tradifi_preparation_v2 import (
    _nonempty_bundle,
)
from tests.runtime.providers.test_binance_usdm_tradifi_preparation_v2 import (
    _resolve as _resolve_v2,
)


def test_planned_artifact_roles_reject_duplicates_with_exact_role_names() -> None:
    with pytest.raises(
        ValueError, match="duplicate planned artifact roles: funding_accounting"
    ):
        _expected_artifact_roles(("funding_accounting", "funding_accounting"))


def test_v1_funding_roles_and_identities_remain_frozen() -> None:
    preparation = _resolve(0).result
    assert preparation is not None

    planned = plan_binance_usdm_tradifi_case_v1(preparation)
    funding = next(
        event
        for event in planned.execution_case.financial_dispatch_plan.scheduled_account_events
        if event.operation_key == "funding"
    )
    rules = {rule.binding_key: rule for rule in _identity_plan(preparation)}

    assert funding.payload.funding_model_version is None
    assert funding.payload.funding_eligibility_role is None
    assert funding.payload.funding_accounting_role is None
    assert funding.expected_artifact_roles == (
        "funding_accounting",
        "funding_eligibility",
    )
    assert dict(funding.identity_bindings) == {
        "journal.funding.0": funding.payload.settlement_identity.journal_entry_id,
        "settlement.funding.0": funding.payload.settlement_identity.settlement_id,
    }
    assert rules["settlement.funding.0"].ordinal == 0
    assert rules["journal.funding.0"].ordinal == 0


def test_empty_retained_bundle_plans_composes_and_runs_flat() -> None:
    preparation = _resolve(0).result
    assert preparation is not None

    planned = plan_binance_usdm_tradifi_case_v1(preparation)
    outcome = DeterministicBarEngine().run(planned.execution_case)

    assert planned.execution_case.decision_cycles == ()
    assert planned.execution_case.bar_executions == ()
    assert outcome.engine_failure is None and outcome.result is not None
    snapshot = outcome.result.final_portfolio_snapshot
    assert snapshot.positions == ()
    assert snapshot.financing == Money(0, snapshot.financing.scale, "USDT")
    assert {artifact.role for artifact in outcome.result.financial_artifacts} == {
        "final_snapshot",
        "funding_accounting",
        "funding_eligibility",
        "margin_projection.final",
    }


def test_planner_preserves_non_lattice_scale8_valuation_marks() -> None:
    bundle = _nonempty_bundle()
    preparation = _resolve_v2(bundle).result
    assert preparation is not None
    stream_key = "binance_usdm.mark_price.valuation.koruusdt.1h.v1"
    streams = dict(bundle.streams)
    streams[stream_key] = tuple(
        replace(
            event,
            payload={
                **event.payload,
                "price_units": event.payload["price_units"] + 1,
                "close_units": event.payload["close_units"] + 1,
            },
        )
        for event in streams[stream_key]
    )
    manifests = {value.stream_key: value for value in bundle.manifest.streams}
    manifests[stream_key] = MarketStreamManifest.from_events(
        stream_key, streams[stream_key]
    )
    manifest = MarketBundleManifest.build(
        bundle_key=bundle.manifest.bundle_key,
        schema_version=bundle.manifest.schema_version,
        coverage_start=bundle.manifest.coverage_start,
        coverage_end_exclusive=bundle.manifest.coverage_end_exclusive,
        instrument_catalog_hash=bundle.manifest.instrument_catalog_hash,
        capabilities=tuple(sorted({value.capability for value in manifests.values()})),
        streams=manifests.values(),
    )
    reader = InMemoryMarketBundleReader(
        type(bundle.bundle_ref).from_manifest(manifest), manifest, streams
    )
    raw_preparation = SimpleNamespace(
        market_reader=reader, resolved_profile=preparation.resolved_profile
    )
    requested_at = streams[stream_key][-1].available_time

    mark, _ = _price_event(
        raw_preparation, stream_key, PricePurpose.VALUATION, requested_at
    )

    assert mark.price.units % 1_000_000 != 0
    assert mark.price.scale.places == 8


def test_planner_preserves_non_lattice_scale8_margin_mark_with_koru_authority(
    monkeypatch,
) -> None:
    bundle = _nonempty_bundle()
    preparation = _resolve_v2(bundle).result
    assert preparation is not None
    stream_key = "binance_usdm.mark_price.margin.koruusdt.1h.v1"
    events = case_planner._events

    def raw_margin_events(result, stream):
        values = events(result, stream)
        if stream != stream_key:
            return values
        return tuple(
            replace(
                event,
                payload={
                    **event.payload,
                    "price_units": event.payload["price_units"] + 1,
                    "close_units": event.payload["close_units"] + 1,
                },
            )
            for event in values
        )

    monkeypatch.setattr(case_planner, "_events", raw_margin_events)
    planned = plan_binance_usdm_tradifi_case_v1(preparation)

    assert planned.execution_case.financial_dispatch_plan is not None


def test_koru_funding_planner_reuses_exact_profile_evidence_and_fails_closed(
    monkeypatch,
) -> None:
    preparation = _resolve_v2(_nonempty_bundle()).result
    assert preparation is not None
    stream = "binance_usdm.funding_history.publications.koruusdt.v1"
    event = preparation.market_reader.streams[stream][0]
    profile_funding = preparation.resolved_profile.request.funding_sources[0]
    raw_record = replace(profile_funding.selected_record, mark_price="20.39013424")
    raw_resolution = (
        BinanceUsdmFundingSourceModelV2()
        .resolve_funding_source(
            replace(
                profile_funding.query,
                funding_book=replace(
                    profile_funding.query.funding_book, records=(raw_record,)
                ),
            )
        )
        .result
    )
    assert raw_resolution is not None
    raw_result = SimpleNamespace(
        intent=preparation.intent,
        resolved_profile=SimpleNamespace(
            request=SimpleNamespace(funding_sources=(raw_resolution,)),
            linear_contract=preparation.resolved_profile.linear_contract,
        ),
        financial_dispatcher_spec=preparation.financial_dispatcher_spec,
    )
    raw_non_lattice_event = replace(
        event,
        payload={
            **event.payload,
            "raw_mark_price": "20.39013424",
            "mark_price_units": 2_039_013_424,
        },
    )
    original_events = case_planner._events

    monkeypatch.setattr(
        case_planner,
        "_events",
        lambda result, key: (
            (raw_non_lattice_event,) if key == stream else original_events(result, key)
        ),
    )
    raw_plan = case_planner._funding_events(raw_result, "run_" + "0" * 64)[0].payload
    assert raw_plan.funding_mark_evidence is raw_resolution.funding_mark_evidence
    assert raw_plan.funding_mark_evidence.resolved_mark.price.units == 2_039_013_424
    assert raw_plan.funding_mark_evidence.resolved_mark.price.scale.places == 8

    monkeypatch.setattr(case_planner, "_events", original_events)
    planned = plan_binance_usdm_tradifi_case_v1(preparation)
    outcome = DeterministicBarEngine().run(planned.execution_case)
    audit_roles = tuple(
        role
        for account_event in planned.execution_case.financial_dispatch_plan.scheduled_account_events
        if account_event.operation_key == "margin_liquidation_audit_batch"
        for role in account_event.expected_artifact_roles
    )
    assert len(audit_roles) == len(set(audit_roles))
    funding = planned.execution_case.financial_dispatch_plan.scheduled_account_events[0]
    payload = funding.payload

    assert outcome.engine_failure is None and outcome.result is not None
    assert payload.funding_mark_evidence is profile_funding.funding_mark_evidence
    assert payload.funding_mark_evidence.resolved_mark.price.scale.places == 8
    assert (
        payload.funding_mark_evidence.resolved_mark.price.units
        != raw_non_lattice_event.payload["mark_price_units"]
    )
    assert payload.publication_candidates == (profile_funding.publication,)
    assert payload.settlement_evidence is profile_funding.settlement_evidence
    assert funding.event_id == profile_funding.selected_record.event_id
    assert (
        payload.settlement_evidence.event_hash
        == profile_funding.selected_record.event_hash
    )

    mismatched_event = replace(event, source_hash="sha256:" + "0" * 64)
    monkeypatch.setattr(
        case_planner,
        "_events",
        lambda result, key: (
            (mismatched_event,) if key == stream else original_events(result, key)
        ),
    )
    with pytest.raises(ValueError, match="exact profile resolution"):
        plan_binance_usdm_tradifi_case_v1(preparation)

    payload_tampered_event = replace(
        event,
        payload={
            **event.payload,
            "raw_funding_rate": "0.00020000",
            "funding_rate_units": event.payload["funding_rate_units"] + 10_000,
        },
    )
    monkeypatch.setattr(
        case_planner,
        "_events",
        lambda result, key: (
            (payload_tampered_event,) if key == stream else original_events(result, key)
        ),
    )
    with pytest.raises(ValueError, match="exact profile resolution"):
        plan_binance_usdm_tradifi_case_v1(preparation)


def test_production_planner_has_no_test_builder_or_financial_simulation_imports() -> (
    None
):
    source = (
        Path(__file__).parents[3]
        / "packages/backtest-runtime/src/crypto_quant_backtest/binance_usdm_tradifi_case_planner.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "crypto_quant_bundle_builder",
        "tests.",
        "BinanceUsdmTradifiLinearFinancialDispatcher",
        "FeeAssessmentEngine",
        "LinearDerivativeAccounting",
        "dispatch_funding_before",
        "book_fill(",
        "book_fee(",
    ):
        assert forbidden not in source
