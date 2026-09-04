from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from crypto_quant_backtest.multi_resolution_market_data import (
    ExecutionDataBinding,
    MultiResolutionMarketDataBindings,
    SignalBarBinding,
    ValuationDataBinding,
    construct_multi_resolution_market_data_bindings,
    validate_schedule_signal_exact_cover,
)
from crypto_quant_domain import InstrumentId, PricePurpose, VenueId, canonical_sha256

from tests.runtime.decision_schedule._fixtures import requirement, schedule


FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/runtime/multi_resolution/mrmd-01-v1.expected.json"
H1 = "sha256:" + "1" * 64
H2 = "sha256:" + "2" * 64


def signal(requirement_hash: str = H1, stream_key: str = "bars.1m") -> SignalBarBinding:
    return SignalBarBinding(requirement_hash, stream_key, PricePurpose.VALUATION, H2)


def execution(key: str = "profile.execution.5s", stream_key: str = "trades.5s") -> ExecutionDataBinding:
    return ExecutionDataBinding(key, stream_key)


def valuation(stable_key: str = "asset", stream_key: str = "marks.1m") -> ValuationDataBinding:
    return ValuationDataBinding(InstrumentId(VenueId("test"), stable_key), stream_key)


def test_canonical_values_sort_hash_and_match_static_fixture() -> None:
    assert tuple(field.name for field in fields(SignalBarBinding)) == (
        "requirement_hash", "stream_key", "price_purpose", "aggregation_input_hash"
    )
    assert tuple(field.name for field in fields(ExecutionDataBinding)) == (
        "profile_binding_key", "stream_key"
    )
    assert tuple(field.name for field in fields(ValuationDataBinding)) == (
        "instrument_id", "stream_key"
    )
    assert tuple(field.name for field in fields(MultiResolutionMarketDataBindings)) == (
        "signal_bindings", "execution_bindings", "valuation_bindings"
    )
    value = construct_multi_resolution_market_data_bindings(
        signal_bindings=(signal(),),
        execution_bindings=(execution(),),
        valuation_bindings=(valuation(),),
    )
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))["bindings"]

    assert value.to_canonical_dict() == expected
    assert value.bindings_hash == canonical_sha256({key: item for key, item in expected.items() if key != "bindings_hash"})
    assert not hasattr(value, "frequency")
    assert not hasattr(value, "resolution")


def test_bindings_canonical_sort_and_reject_duplicate_role_identities() -> None:
    value = MultiResolutionMarketDataBindings(
        signal_bindings=(signal("sha256:" + "b" * 64), signal("sha256:" + "a" * 64)),
        execution_bindings=(execution("z"), execution("a")),
        valuation_bindings=(valuation("z"), valuation("a")),
    )
    assert tuple(item.requirement_hash for item in value.signal_bindings) == tuple(sorted(item.requirement_hash for item in value.signal_bindings))
    assert tuple(item.profile_binding_key for item in value.execution_bindings) == ("a", "z")
    assert tuple(item.instrument_id.stable_key for item in value.valuation_bindings) == ("a", "z")

    with pytest.raises(ValueError, match="duplicate signal"):
        MultiResolutionMarketDataBindings((signal(), signal()), (), ())
    with pytest.raises(ValueError, match="duplicate execution"):
        MultiResolutionMarketDataBindings((), (execution(), execution(stream_key="other")), ())
    with pytest.raises(ValueError, match="duplicate valuation"):
        MultiResolutionMarketDataBindings((), (), (valuation(), valuation(stream_key="other")))


def test_exact_types_and_constructor_bypass_are_closed_at_canonical_boundary() -> None:
    with pytest.raises(TypeError):
        SignalBarBinding(H1, "bars", "valuation", H2)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        MultiResolutionMarketDataBindings([signal()], (), ())  # type: ignore[arg-type]

    forged = object.__new__(SignalBarBinding)
    for field in fields(signal()):
        object.__setattr__(forged, field.name, getattr(signal(), field.name))
    object.__setattr__(forged, "aggregation_input_hash", "not-a-hash")
    with pytest.raises(ValueError):
        forged.to_canonical_dict()
    with pytest.raises(ValueError):
        MultiResolutionMarketDataBindings((forged,), (), ())

    forged_instrument = object.__new__(InstrumentId)
    object.__setattr__(forged_instrument, "venue", VenueId("test"))
    object.__setattr__(forged_instrument, "stable_key", " bad ")
    with pytest.raises(ValueError):
        ValuationDataBinding(forged_instrument, "marks")


def test_schedule_signal_bindings_must_exact_cover_requirements() -> None:
    first = requirement()
    second = type(first)(
        requirement_key="secondary-bars",
        observation_query=first.observation_query,
        bar_definition=type(first.bar_definition)(
            "secondary", 1, "sha256:" + "3" * 64
        ),
        minimum_count=1,
    )
    current = schedule(requirements=(first, second))
    exact = MultiResolutionMarketDataBindings(
        signal_bindings=(
            signal(first.requirement_hash, first.observation_query.dataset_key),
            signal(second.requirement_hash, second.observation_query.dataset_key),
        ),
        execution_bindings=(),
        valuation_bindings=(),
    )
    assert validate_schedule_signal_exact_cover(current, exact) is exact

    with pytest.raises(ValueError, match="exact-cover"):
        validate_schedule_signal_exact_cover(current, MultiResolutionMarketDataBindings(exact.signal_bindings[:1], (), ()))
    with pytest.raises(ValueError, match="exact-cover"):
        validate_schedule_signal_exact_cover(schedule(requirements=(first,)), exact)
    wrong_stream = MultiResolutionMarketDataBindings((signal(first.requirement_hash, "other"),), (), ())
    with pytest.raises(ValueError, match="stream"):
        validate_schedule_signal_exact_cover(schedule(requirements=(first,)), wrong_stream)
