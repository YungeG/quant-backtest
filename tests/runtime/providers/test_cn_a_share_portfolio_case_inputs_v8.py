"""Retained synthetic case source closure, not a portfolio economic result."""
from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import (
    BAR_OPEN_CAPABILITY, BAR_OPEN_EVENT_TYPE, BacktestTargetStreamError,
    BacktestTargetStreamFailureCode, BacktestTargetStreamRepository, PrecomputedTargetStream,
)
from crypto_quant_backtest.cn_a_share_portfolio_case_inputs_v8 import (
    CnASharePortfolioCaseInputV8, read_retained_cn_a_share_portfolio_case_input_v8,
    retain_cn_a_share_portfolio_case_input_v8,
)
from crypto_quant_backtest.execution_inputs import _EXECUTION_INPUT_CATALOG
from crypto_quant_domain import (
    ArtifactDecodeError, ArtifactEnvelope, ArtifactRef, SourceSequence, TimelinePhase, UtcInstant,
    canonical_bytes, canonical_sha256,
)
from crypto_quant_market_data import InMemoryMarketBundleReader, MarketEvent
from tests.runtime.providers.test_cn_a_share_portfolio_preparation_inputs_v1 import (
    _CODES, _inputs, _target_event,
)


def _fixture(codes):
    scope, _, store = _inputs(codes)
    events = tuple(MarketEvent(
        event_id=f"fixture.open.{index}", stream_key="bars.open", event_type=BAR_OPEN_EVENT_TYPE,
        capability=BAR_OPEN_CAPABILITY, instrument_id=instrument,
        event_time=UtcInstant(200), available_time=UtcInstant(200),
        phase=TimelinePhase(60, "bar_open"), source_sequence=SourceSequence(index),
        revision_id="fixture.rev1", supersedes_revision_id=None,
        source_key=f"fixture.pharma.open.{index}", source_hash="sha256:" + f"{index:x}" * 64,
        payload={"schema_version": 1, "bar_kind": "real",
                 "open_price": {"units": 1000 + index, "scale": 2, "quote_currency": "CNY"}},
    ) for index, instrument in enumerate(scope.instrument_ids, 1))
    reader = _market(scope, events)
    return replace(scope, market_bundle_ref=reader.bundle_ref), reader, store, events


def _market(scope, events):
    return InMemoryMarketBundleReader.build(
        bundle_key="fixture.pharma.two-stock.open.v1", schema_version=1,
        coverage_start=UtcInstant(199), coverage_end_exclusive=UtcInstant(300),
        instrument_catalog_hash=canonical_sha256(scope.instrument_catalog),
        capabilities=(BAR_OPEN_CAPABILITY,), streams={"bars.open": events},
    )


def _retained(scope, reader, store):
    return retain_cn_a_share_portfolio_case_input_v8(
        scope, target_reader=store, market_reader=reader, publisher=store)


@pytest.mark.parametrize("codes", ((_CODES[0],), (_CODES[0], _CODES[4])))
def test_frozen_case_source_only_rebuild_and_standard_decoder_rejects(codes):
    scope, market, store, _ = _fixture(codes)
    ref = _retained(scope, market, store)
    assert ref.artifact_type == "backtest_execution_input_bundle" and ref.schema_version == 8
    assert type(read_retained_cn_a_share_portfolio_case_input_v8(
        ref, reader=store, target_reader=store, market_reader=market)) is CnASharePortfolioCaseInputV8
    # Reopen without carrying the caller's typed Case object.
    case = read_retained_cn_a_share_portfolio_case_input_v8(
        ref, reader=store, target_reader=store, market_reader=market)
    assert len(case.bar_bindings) == len(codes) and case.scope.account_id == "pharma.cash.account"
    assert case.case_hash == read_retained_cn_a_share_portfolio_case_input_v8(
        ref, reader=store, target_reader=store, market_reader=market).case_hash
    assert not case.to_canonical_dict()["trade_authorized"]
    assert not case.scope.to_canonical_dict()["shared_cny_funding_authority_qualified"]
    # The standard catalog supports V8, but not this diagnostic source-only protocol.
    with pytest.raises(ArtifactDecodeError):
        _EXECUTION_INPUT_CATALOG.read(canonical_bytes(store.values[ref]))


def test_case_identity_is_stable_when_bundle_event_input_order_reverses():
    scope, market, store, events = _fixture((_CODES[0], _CODES[4]))
    reordered = _market(scope, tuple(reversed(events)))
    assert reordered.bundle_ref == market.bundle_ref
    assert _retained(scope, reordered, store) == _retained(scope, market, store)


def test_ten_stock_frozen_case_requires_every_open_without_claiming_engine_fill():
    scope, market, store, events = _fixture(_CODES)
    ref = _retained(scope, market, store)
    decoded = read_retained_cn_a_share_portfolio_case_input_v8(
        ref, reader=store, target_reader=store, market_reader=market)
    assert len(decoded.scope.instrument_ids) == len(decoded.bar_bindings) == 10
    assert not decoded.to_canonical_dict()["trade_authorized"]
    missing = _market(scope, events[:-1])
    with pytest.raises(ValueError, match="opening events must exact-cover"):
        _retained(replace(scope, market_bundle_ref=missing.bundle_ref), missing, store)


def test_reopen_rejects_changed_market_bundle_and_absent_open():
    scope, market, store, events = _fixture((_CODES[0], _CODES[4]))
    ref = _retained(scope, market, store)
    changed = _market(scope, (replace(events[0], payload={"schema_version": 1, "bar_kind": "real",
                                "open_price": {"units": 998, "scale": 2, "quote_currency": "CNY"}}), events[1]))
    with pytest.raises(ValueError, match="bundle/catalog identity mismatch"):
        read_retained_cn_a_share_portfolio_case_input_v8(
            ref, reader=store, target_reader=store, market_reader=changed)
    missing = _market(scope, events[:1])
    with pytest.raises(ValueError, match="opening events must exact-cover"):
        _retained(replace(scope, market_bundle_ref=missing.bundle_ref), missing, store)


def test_reopen_rejects_replacement_cas_bytes_and_fake_real_source():
    scope, market, store, events = _fixture((_CODES[0], _CODES[4]))
    ref = _retained(scope, market, store)
    original = store.values[ref]
    changed = dict(original.payload)
    changed_case = dict(changed["case"])
    changed_case["trade_authorized"] = True
    changed["case"] = changed_case
    store.values[ref] = ArtifactEnvelope.create("backtest_execution_input_bundle", 8, changed)
    with pytest.raises(ValueError, match="raw Case ref/bytes mismatch"):
        read_retained_cn_a_share_portfolio_case_input_v8(
            ref, reader=store, target_reader=store, market_reader=market)
    forged = _market(scope, (replace(events[0], source_key="tushare.forged"), events[1]))
    with pytest.raises(ValueError, match="fixture BarOpen identity"):
        _retained(replace(scope, market_bundle_ref=forged.bundle_ref), forged, store)


def test_independent_raw_decoder_rejects_canonical_grade_elevation():
    scope, market, store, _ = _fixture((_CODES[0], _CODES[4]))
    ref = _retained(scope, market, store)
    original = dict(store.values[ref].payload)
    case = dict(original["case"])
    case["trade_authorized"] = True
    malicious = ArtifactEnvelope.create("backtest_execution_input_bundle", 8, {**original, "case": case})
    malicious_ref = store.put(envelope=malicious)
    with pytest.raises(ArtifactDecodeError):
        read_retained_cn_a_share_portfolio_case_input_v8(
            malicious_ref, reader=store, target_reader=store, market_reader=market)


def test_source_close_rejects_future_target_and_duplicate_stock_open_without_publication():
    scope, market, store, events = _fixture((_CODES[0], _CODES[4]))
    late = replace(_target_event(scope.instrument_ids), event_time=UtcInstant(200),
                   available_time=UtcInstant(200))
    later_ref = BacktestTargetStreamRepository(reader=store, publisher=store).publish(
        ArtifactRef("fixture_context", 1, "sha256:" + "9" * 64),
        PrecomputedTargetStream("targets", (late,)))
    with pytest.raises(ValueError, match="target must precede"):
        _retained(replace(scope, target_stream_ref=later_ref), market, store)
    duplicate = replace(events[0], event_id="fixture.open.3", source_sequence=SourceSequence(3))
    repeated = _market(scope, (*events, duplicate))
    with pytest.raises(ValueError, match="fixture BarOpen identity"):
        _retained(replace(scope, market_bundle_ref=repeated.bundle_ref), repeated, store)
    assert all(ref.artifact_type != "backtest_execution_input_bundle" for ref in store.values)


def test_v8_source_close_rejects_tampered_target_cas_before_case_publication():
    scope, market, store, _ = _fixture((_CODES[0], _CODES[4]))
    target_ref = scope.target_stream_ref.artifact_ref
    original = dict(store.values[target_ref].payload)
    store.values[target_ref] = ArtifactEnvelope.create("backtest_target_stream", 1,
        {**original, "target_stream": PrecomputedTargetStream("targets", ())})
    with pytest.raises(BacktestTargetStreamError) as failure:
        _retained(scope, market, store)
    assert failure.value.code is BacktestTargetStreamFailureCode.TAMPERED
    assert all(ref.artifact_type != "backtest_execution_input_bundle" for ref in store.values)
