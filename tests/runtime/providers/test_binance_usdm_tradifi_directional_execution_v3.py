from __future__ import annotations

from pathlib import Path

import crypto_quant_domain as domain
from crypto_quant_backtest import BinanceUsdmTradifiProviderInputs
from crypto_quant_backtest.binance_usdm_koru_directional_profile_v3 import (
    BinanceUsdmKoruDirectionalPlannerV3,
    verify_binance_usdm_koru_directional_strategy_authority_v3,
)
from crypto_quant_backtest.binance_usdm_tradifi_directional_case_planner_v3 import (
    plan_binance_usdm_tradifi_directional_case_v3,
)
from crypto_quant_backtest.binance_usdm_tradifi_directional_preparation import (
    BinanceUsdmTradifiDirectionalPreparationV3,
    BinanceUsdmTradifiDirectionalRequestIntentV3,
)
from crypto_quant_backtest.binance_usdm_tradifi_provider import (
    BinanceUsdmTradifiBarBacktestFailure,
)
from crypto_quant_backtest.koru_tradifi_economics_authority_v3 import (
    resolve_koru_tradifi_economics_authority_v3,
)
from crypto_quant_backtest.resolution import RequestedResultGrade
from crypto_quant_backtest.timeline import TimelineWindow

from tests.runtime.providers import (
    test_binance_usdm_tradifi_directional_preparation_v3 as fixture,
)
from tests.runtime.providers.test_binance_usdm_tradifi_preparation_v2 import _EQUITY
from tests.runtime.resolution._fixtures import build_manifest


def _values(tmp_path: Path) -> BinanceUsdmTradifiDirectionalPreparationV3:
    _, overlay, artifacts = fixture._overlay(tmp_path)
    authority = verify_binance_usdm_koru_directional_strategy_authority_v3(market_reader=overlay.reader)
    assert not isinstance(authority, BinanceUsdmTradifiBarBacktestFailure)
    economics = resolve_koru_tradifi_economics_authority_v3(
        market_reader=overlay.reader, artifact_reader=artifacts,
        provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY), experiment_id="directional-v3-economic",
    )
    assert not isinstance(economics, BinanceUsdmTradifiBarBacktestFailure)
    intent = BinanceUsdmTradifiDirectionalRequestIntentV3(
        "directional-v3-economic",
        TimelineWindow(overlay.manifest.coverage_start, overlay.manifest.coverage_start, overlay.manifest.coverage_end_exclusive),
        "account-1", domain.CurrencyId("USDT"), 0, overlay.reader.bundle_ref,
        authority.strategy_ref, authority.parameter_ref, authority.strategy_id, authority.sleeve_id,
        RequestedResultGrade.DEVELOPMENT,
    )
    return BinanceUsdmTradifiDirectionalPreparationV3(
        authority, BinanceUsdmKoruDirectionalPlannerV3.target(authority), economics, intent,
    )


def test_v3_sealed_overlay_plans_deterministically(tmp_path: Path) -> None:
    values = _values(tmp_path)
    first = plan_binance_usdm_tradifi_directional_case_v3(values)
    second = plan_binance_usdm_tradifi_directional_case_v3(values)

    assert domain.canonical_bytes(second.execution_case) == domain.canonical_bytes(first.execution_case)
    assert len(first.execution_case.decision_cycles) == len(values.target_stream.events)
    assert first.request.target_stream_digest == values.target_stream_digest
    assert first.request.market_bundle_ref == values.market_bundle_ref
