from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import crypto_quant_backtest.binance_usdm_tradifi_case_planner as case_planner
from crypto_quant_backtest import DeterministicBarEngine
from crypto_quant_backtest.binance_usdm_tradifi_case_planner import (
    _price_event,
    plan_binance_usdm_tradifi_case_v1,
)
from crypto_quant_domain import Money, PricePurpose
from crypto_quant_market_data import (
    InMemoryMarketBundleReader,
    MarketBundleManifest,
    MarketStreamManifest,
)

from tests.runtime.providers.test_binance_usdm_tradifi_preparation import _resolve
from tests.runtime.providers.test_binance_usdm_tradifi_preparation_v2 import (
    _nonempty_bundle,
)
from tests.runtime.providers.test_binance_usdm_tradifi_preparation_v2 import (
    _resolve as _resolve_v2,
)


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


def test_production_planner_has_no_test_builder_or_financial_simulation_imports() -> None:
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
