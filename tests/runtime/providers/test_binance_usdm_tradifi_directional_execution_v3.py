from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import crypto_quant_domain as domain
import pytest
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
    _build_v3_economics_profile,
)
from crypto_quant_backtest.resolution import RequestedResultGrade
from crypto_quant_backtest.target_stream import PrecomputedTargetStream
from crypto_quant_backtest.timeline import TimelineWindow

from tests.runtime.providers import (
    test_binance_usdm_tradifi_directional_preparation_v3 as fixture,
)
from tests.runtime.providers.test_binance_usdm_tradifi_preparation_v2 import _EQUITY
from tests.runtime.resolution._fixtures import build_manifest


def _synthetic_values(
    tmp_path: Path, exposure: str, *, delayed_flatten: bool = True
) -> object:
    v2, v3, artifacts = fixture._authorities()
    reader = fixture._hybrid(v2, v3, tmp_path)
    authority = verify_binance_usdm_koru_directional_strategy_authority_v3(
        market_reader=reader
    )
    assert not hasattr(authority, "code")
    economics = _build_v3_economics_profile(
        reader=reader,
        experiment_id="directional-v3-economic",
        artifact_reader=artifacts,
        provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY),
    )
    target = BinanceUsdmKoruDirectionalPlannerV3.target(authority)
    intent = BinanceUsdmTradifiDirectionalRequestIntentV3(
        "directional-v3-economic",
        TimelineWindow(
            reader.manifest.coverage_start,
            reader.manifest.coverage_start,
            reader.manifest.coverage_end_exclusive,
        ),
        "account-1",
        domain.CurrencyId("USDT"),
        0,
        reader.bundle_ref,
        authority.strategy_ref,
        authority.parameter_ref,
        authority.strategy_id,
        authority.sleeve_id,
        RequestedResultGrade.DEVELOPMENT,
    )
    values = BinanceUsdmTradifiDirectionalPreparationV3(
        authority,
        target,
        authority.v2_bundle_ref,
        authority.v2_bundle_digest,
        economics.source_ref,
        authority.source_fragment_digest,
        intent,
        economics.profile,
        economics.profile.profile_registry,
        economics.profile.financial_dispatcher_spec,
        economics.build_manifest,
        reader.manifest,
        reader.bundle_ref,
        reader,
    )
    events = list(target.target_stream.events)
    changes = ((1, exposure), (2, exposure), (3, "0"))
    if not delayed_flatten:
        changes = ((1, exposure), (2, "0"))
    for index, value in changes:
        candidate = dict(events[index].payload["candidate"])
        target_wire = dict(candidate["targets"][0])
        target_wire["value"] = value
        candidate["targets"] = (target_wire,)
        events[index] = replace(
            events[index], payload={"schema_version": 1, "candidate": candidate}
        )
    stream = PrecomputedTargetStream(target.target_stream.stream_key, tuple(events))
    target = replace(
        target, target_stream=stream, target_stream_digest=stream.target_stream_digest
    )
    fields = {name: getattr(values, name) for name in values.__slots__}
    fields.update(
        target=target,
        target_stream=stream,
        target_stream_key=stream.stream_key,
        target_stream_digest=stream.target_stream_digest,
        profile_composition_request=values.resolved_profile.request,
        bundle_schema_version=2,
        result_digest=values.authority_digest,
        authority_digest=values.authority_digest,
    )
    return SimpleNamespace(**fields)


@pytest.mark.parametrize(
    ("exposure", "entry_side", "flatten_side"),
    (("0.25", domain.OrderSide.BUY, domain.OrderSide.SELL), ("-0.25", domain.OrderSide.SELL, domain.OrderSide.BUY)),
)
def test_v3_target_changes_use_v2_economics_and_skip_unchanged_candidates(
    tmp_path: Path, exposure: str, entry_side: domain.OrderSide, flatten_side: domain.OrderSide
) -> None:
    values = _synthetic_values(tmp_path, exposure)
    first = plan_binance_usdm_tradifi_directional_case_v3(values)
    second = plan_binance_usdm_tradifi_directional_case_v3(values)
    case = first.execution_case

    assert domain.canonical_bytes(second.execution_case) == domain.canonical_bytes(case)
    assert len(case.decision_cycles) == len(values.target_stream.events)
    assert [len(cycle.admissions) for cycle in case.decision_cycles] == [0, 1, 0, 1, *([0] * 8)]
    assert len(case.bar_executions) == 2
    assert [bar.event_id for bar in case.bar_executions] == [
        values.target_stream.events[index].payload["candidate"]["evidence"]["source_events"][2]["event_id"]
        for index in (1, 3)
    ]
    assert [bar.fill_liquidity_role for bar in case.bar_executions] == ["taker", "taker"]
    assert [bar.order_id for bar in case.bar_executions] == [
        case.decision_cycles[1].admissions[0].order.order_id,
        case.decision_cycles[3].admissions[0].order.order_id,
    ]
    assert [
        case.decision_cycles[index].admissions[0].order.intent.side
        for index in (1, 3)
    ] == [entry_side, flatten_side]
    assert all(
        bar.pretrade_plan.resource_commitment.margin[0]
        == domain.Money(250_000_000_000, domain.Scale(8), "USDT")
        for bar in case.bar_executions
    )
    assert all(
        cycle.sizing_policy.rounding is domain.RoundingPolicy.TOWARD_ZERO
        for cycle in case.decision_cycles
    )
    assert {event.operation_key for event in case.financial_dispatch_plan.scheduled_account_events} >= {
        "funding",
        "margin_liquidation_audit_batch",
    }
    assert all(
        bar.accounting_plan.expected_artifact_roles
        == (f"position_accounting.{index}",)
        for index, bar in enumerate(case.bar_executions, 1)
    )


def test_v3_rejects_a_distinct_target_before_its_pending_fill(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="pending-target-conflict"):
        plan_binance_usdm_tradifi_directional_case_v3(
            _synthetic_values(tmp_path, "0.25", delayed_flatten=False)
        )
