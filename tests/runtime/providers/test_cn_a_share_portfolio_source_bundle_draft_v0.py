"""Offline source-exact-cover samples are synthetic, NEVER formal evidence."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from crypto_quant_backtest import BAR_OPEN_CAPABILITY, BacktestTargetStreamRepository, PrecomputedTargetStream
from crypto_quant_backtest.cn_a_share_portfolio_preparation_inputs_v1 import (
    CnASharePortfolioSourceAdmissionBlockedV1, require_cn_a_share_portfolio_source_qualification_v1,
)
from crypto_quant_backtest.cn_a_share_portfolio_source_bundle_draft_v0 import (
    read_cn_a_share_portfolio_source_bundle_draft_v0,
)
from crypto_quant_domain import (
    ArtifactEnvelope, ArtifactRef, InstrumentId, SourceSequence, TimelinePhase, UtcInstant, VenueId, canonical_sha256,
)
from crypto_quant_market_data import EventCursor, InMemoryMarketBundleReader, MarketEvent
from tests.runtime.providers.test_cn_a_share_portfolio_preparation_inputs_v1 import _CODES, _inputs

_COMPONENT = "backtest_cn_a_share_portfolio_source_component_draft"
_BUNDLE = "backtest_cn_a_share_portfolio_source_bundle_draft"
_DECISION, _EXECUTION = UtcInstant(100), UtcInstant(200)


def _component(store, kind: str, instrument: InstrumentId | None, venue: VenueId,
               **changes: object) -> ArtifactRef:
    name = f"synthetic.{kind}.{venue.value}.{instrument.stable_key if instrument else 'account'}"
    facts = {
        "membership": {"member": True, "revision_closed": True},
        "trade_status": {"listed": True, "st": False, "suspended": False,
                         "upper_limit_open": False, "lower_limit_open": False},
        "corporate_action": {"no_action_window": True, "absence_closed": True},
        "fee": {"route": "domestic", "product_class": "ordinary_a_share", "fee_basis": "turnover",
                "commission_bps": 5, "minimum_commission_cents": 500,
                "market_fee_bps": 1, "sell_tax_bps": 5},
    }[kind]
    payload = {"type": "cn_a_share_portfolio_source_component_draft", "schema_version": 1,
               "kind": kind, "instrument_id": instrument, "venue_id": venue.value,
               "effective_from": UtcInstant(90), "effective_to_exclusive": UtcInstant(250),
               "available_at": UtcInstant(95 if kind == "membership" else 180),
               "source_key": name, "source_hash": canonical_sha256({"synthetic_source": name}),
               "revision_id": "synthetic.rev1", "facts": facts,
               "synthetic_only": True, "trade_authorized": False, **changes}
    return store.put(envelope=ArtifactEnvelope.create(_COMPONENT, 1, payload))


def _bundle(codes, *, omit: str = ""):
    inputs, _, store = _inputs(codes)
    stocks = []
    for instrument in inputs.instrument_ids:
        row: dict[str, Any] = {"instrument_id": instrument}
        for key in ("membership", "trade_status", "corporate_action"):
            if omit == key and instrument == inputs.instrument_ids[-1]:
                continue
            row[key] = _component(store, key, instrument, instrument.venue)
        stocks.append(row)
    fees = []
    for venue in (VenueId("xshg"), VenueId("xshe")):
        if omit == f"{venue.value}_fee":
            continue
        fees.append({"venue_id": venue.value, "fee": _component(store, "fee", None, venue)})
    payload = {"type": "cn_a_share_portfolio_source_bundle_draft", "schema_version": 1,
               "input_hash": inputs.input_hash, "decision_at": _DECISION, "execution_at": _EXECUTION,
               "stock_sources": stocks, "venue_fees": fees,
               "synthetic_only": True, "formal_qualified": False}
    ref = store.put(envelope=ArtifactEnvelope.create(_BUNDLE, 1, payload))
    return ref, inputs, store, stocks, fees


def test_single_stock_source_readback_smoke_requires_three_stock_and_two_venue_artifacts():
    ref, inputs, store, _, _ = _bundle((_CODES[0],))
    value = read_cn_a_share_portfolio_source_bundle_draft_v0(ref, inputs=inputs, reader=store)
    assert value.instrument_ids == inputs.instrument_ids
    assert value.bundle_ref == ref and value.component_count == 5
    assert value.synthetic_complete and not value.formal_qualified and not value.trade_authorized


def test_ten_stock_exact_cover_readback_and_independent_component_removal():
    ref, inputs, store, stocks, _ = _bundle(_CODES)
    value = read_cn_a_share_portfolio_source_bundle_draft_v0(ref, inputs=inputs, reader=store)
    assert value.component_count == 32
    assert len(store.reads) == 33  # one manifest + thirty individually fetched stock components + two fees
    store.values.pop(stocks[3]["corporate_action"])
    with pytest.raises(ValueError, match="missing, tampered or unavailable"):
        read_cn_a_share_portfolio_source_bundle_draft_v0(ref, inputs=inputs, reader=store)


@pytest.mark.parametrize("omitted", ["membership", "trade_status", "corporate_action", "xshg_fee", "xshe_fee"])
def test_missing_single_stock_or_venue_component_fails_closed(omitted):
    ref, inputs, store, _, _ = _bundle((_CODES[0], _CODES[4]), omit=omitted)
    with pytest.raises((ValueError, KeyError)):
        read_cn_a_share_portfolio_source_bundle_draft_v0(ref, inputs=inputs, reader=store)


def test_tampered_component_bytes_or_ref_are_rejected_without_trusting_old_readback():
    ref, inputs, store, stocks, _ = _bundle((_CODES[0], _CODES[4]))
    read_cn_a_share_portfolio_source_bundle_draft_v0(ref, inputs=inputs, reader=store)
    subject = stocks[0]["trade_status"]
    original = store.values[subject]
    store.values[subject] = ArtifactEnvelope.create(_COMPONENT, 1,
        {**original.payload, "revision_id": "synthetic.rev2"})
    with pytest.raises(ValueError, match="readback identity mismatch"):
        read_cn_a_share_portfolio_source_bundle_draft_v0(ref, inputs=inputs, reader=store)


def test_late_membership_partial_action_window_and_out_of_interval_status_rejected():
    for key, changed in (("membership", {"available_at": UtcInstant(101)}),
                         ("corporate_action", {"effective_from": UtcInstant(150)}),
                         ("trade_status", {"effective_to_exclusive": UtcInstant(200)})):
        ref, inputs, store, stocks, _ = _bundle((_CODES[0],))
        subject = stocks[0][key]
        original = store.values[subject]
        replacement = ArtifactEnvelope.create(_COMPONENT, 1, {**original.payload, **changed})
        new_ref = store.put(envelope=replacement)
        manifest = store.values[ref]
        rows = list(manifest.payload["stock_sources"])
        rows[0] = {**rows[0], key: new_ref}
        altered_ref = store.put(envelope=ArtifactEnvelope.create(_BUNDLE, 1,
            {**manifest.payload, "stock_sources": rows}))
        with pytest.raises(ValueError, match="effective/availability interval"):
            read_cn_a_share_portfolio_source_bundle_draft_v0(altered_ref, inputs=inputs, reader=store)


def test_adverse_status_and_false_corporate_absence_cannot_be_positive_synthetic_coverage():
    for key, facts_change in (("trade_status", {"suspended": True}),
                              ("corporate_action", {"absence_closed": False})):
        ref, inputs, store, stocks, _ = _bundle((_CODES[0],))
        subject = stocks[0][key]
        old = store.values[subject]
        new_facts = {**old.payload["facts"], **facts_change}
        new_ref = store.put(envelope=ArtifactEnvelope.create(_COMPONENT, 1,
            {**old.payload, "facts": new_facts}))
        manifest = store.values[ref]
        rows = list(manifest.payload["stock_sources"])
        rows[0] = {**rows[0], key: new_ref}
        new_bundle = store.put(envelope=ArtifactEnvelope.create(_BUNDLE, 1,
            {**manifest.payload, "stock_sources": rows}))
        with pytest.raises(ValueError, match="missing, adverse or ineligible"):
            read_cn_a_share_portfolio_source_bundle_draft_v0(new_bundle, inputs=inputs, reader=store)


def test_fake_grade_elevation_on_manifest_fails_before_any_component_read():
    ref, inputs, store, _, _ = _bundle((_CODES[0],))
    old = store.values[ref]
    new_ref = store.put(envelope=ArtifactEnvelope.create(_BUNDLE, 1,
        {**old.payload, "formal_qualified": True}))
    with pytest.raises(ValueError, match="scope/grade mismatch"):
        read_cn_a_share_portfolio_source_bundle_draft_v0(new_ref, inputs=inputs, reader=store)
    assert set(store.reads) == {new_ref}


def _gate_bundle(*, codes=(_CODES[0], _CODES[4]), open_at=_EXECUTION):
    ref, inputs, store, _, _ = _bundle(codes)
    bars = tuple(MarketEvent(
        event_id=f"synthetic-open-{i}", stream_key="bars.open", event_type="bar_open",
        capability=BAR_OPEN_CAPABILITY, instrument_id=stock,
        event_time=open_at, available_time=open_at,
        phase=TimelinePhase(60, "bar_open"), source_sequence=SourceSequence(i),
        revision_id="synthetic.rev1", supersedes_revision_id=None,
        source_key=f"synthetic.bar.{stock.stable_key}",
        source_hash=canonical_sha256({"synthetic_stock": str(stock)}),
        # REAL is the native price-bearing row kind, not a real-market/source authority grant.
        payload={"schema_version": 1, "bar_kind": "real",
                 "open_price": {"units": 1000, "scale": 2, "quote_currency": "CNY"}},
    ) for i, stock in enumerate(inputs.instrument_ids, 1))
    market = InMemoryMarketBundleReader.build(
        bundle_key="synthetic-only-membership-status-fee", schema_version=1,
        coverage_start=UtcInstant(199), coverage_end_exclusive=UtcInstant(210),
        instrument_catalog_hash=canonical_sha256(inputs.instrument_catalog),
        capabilities=(BAR_OPEN_CAPABILITY,), streams={"bars.open": bars})
    matched = replace(inputs, market_bundle_ref=market.bundle_ref)
    retained = store.values[ref]
    matched_ref = store.put(envelope=ArtifactEnvelope.create(_BUNDLE, 1,
        {**retained.payload, "input_hash": matched.input_hash}))
    return matched_ref, matched, store, market


def test_even_complete_synthetic_source_and_bar_open_metadata_cannot_clear_formal_gate():
    matched_ref, matched, store, market = _gate_bundle()
    assert read_cn_a_share_portfolio_source_bundle_draft_v0(
        matched_ref, inputs=matched, reader=store).component_count == 8
    before = len(store.values)
    with pytest.raises(CnASharePortfolioSourceAdmissionBlockedV1) as failure:
        require_cn_a_share_portfolio_source_qualification_v1(
            matched, market_reader=market, artifact_reader=store,
            source_bundle_ref=matched_ref)
    assert "membership_effective_revision_unverified" in failure.value.reason_codes
    assert "xshg_xshe_account_fee_effective_interval_unverified" in failure.value.reason_codes
    assert len(store.values) == before  # no case/result/publication


@pytest.mark.parametrize("missing", ("membership", "trade_status", "corporate_action"))
def test_missing_each_stock_source_fails_before_bar_capability_or_target_read(missing):
    codes = (_CODES[0], _CODES[4])
    ref, inputs, store, _, _ = _bundle(codes, omit=missing)
    _, market, _ = _inputs(codes)  # Same immutable bundle identity, deliberately NO BarOpen capability.
    assert market.bundle_ref == inputs.market_bundle_ref
    with pytest.raises(ValueError, match="stock source fields"):
        require_cn_a_share_portfolio_source_qualification_v1(
            inputs, market_reader=market, artifact_reader=store, source_bundle_ref=ref)
    assert store.reads.get(inputs.target_stream_ref.artifact_ref, 0) == 0


def test_missing_retained_stock_component_fails_before_bar_capability_and_publication():
    codes = (_CODES[0], _CODES[4])
    ref, inputs, store, stocks, _ = _bundle(codes)
    _, market, _ = _inputs(codes)
    store.values.pop(stocks[-1]["trade_status"])
    before = len(store.values)
    with pytest.raises(ValueError, match="missing, tampered or unavailable"):
        require_cn_a_share_portfolio_source_qualification_v1(
            inputs, market_reader=market, artifact_reader=store, source_bundle_ref=ref)
    assert store.reads.get(inputs.target_stream_ref.artifact_ref, 0) == 0
    assert len(store.values) == before


@pytest.mark.parametrize("clock,value", (("decision_at", UtcInstant(99)),
                                          ("execution_at", UtcInstant(201))))
def test_gate_source_clocks_cannot_float_away_from_frozen_target_or_open(clock, value):
    ref, inputs, store, market = _gate_bundle()
    original = store.values[ref]
    changed_ref = store.put(envelope=ArtifactEnvelope.create(_BUNDLE, 1,
        {**original.payload, clock: value}))
    before = len(store.values)
    with pytest.raises(ValueError, match="source (decision|execution) binding mismatch") as failure:
        require_cn_a_share_portfolio_source_qualification_v1(
            inputs, market_reader=market, artifact_reader=store, source_bundle_ref=changed_ref)
    assert type(failure.value) is ValueError  # clock error, not the eventual formal BLOCKED result
    assert len(store.values) == before


def test_later_missing_member_slot_is_detected_before_earlier_corrupt_component():
    ref, inputs, store, stocks, _ = _bundle((_CODES[0], _CODES[4]), omit="membership")
    _, market, _ = _inputs((_CODES[0], _CODES[4]))
    first_ref = stocks[0]["trade_status"]
    original = store.values[first_ref]
    store.values[first_ref] = ArtifactEnvelope.create(_COMPONENT, 1,
        {**original.payload, "revision_id": "synthetic.corrupt"})
    with pytest.raises(ValueError, match="stock source fields"):
        require_cn_a_share_portfolio_source_qualification_v1(
            inputs, market_reader=market, artifact_reader=store, source_bundle_ref=ref)
    assert store.reads.get(first_ref, 0) == 0
    assert store.reads.get(inputs.target_stream_ref.artifact_ref, 0) == 0


def _ref(raw) -> ArtifactRef:
    return ArtifactRef(raw["artifact_type"], raw["schema_version"], raw["content_hash"])


def _rewrite(store, ref, **changes) -> ArtifactRef:
    old = store.values[ref]
    return store.put(envelope=ArtifactEnvelope.create(
        old.artifact_type, old.schema_version, {**old.payload, **changes}))


@pytest.mark.parametrize("venue_index", (0, 1), ids=("SH", "SZ"))
@pytest.mark.parametrize("missing_kind", ("manifest", "artifact"))
def test_gate_missing_either_venue_fee_manifest_or_cas_precedes_target(venue_index, missing_kind):
    ref, inputs, store, market = _gate_bundle()
    fees = list(store.values[ref].payload["venue_fees"])
    if missing_kind == "manifest":
        fees.pop(venue_index)
        ref = _rewrite(store, ref, venue_fees=fees)
        expected = "fee source coverage incomplete"
    else:
        store.values.pop(_ref(fees[venue_index]["fee"]))
        expected = "missing, tampered or unavailable"
    before = len(store.values)
    with pytest.raises(ValueError, match=expected):
        require_cn_a_share_portfolio_source_qualification_v1(
            inputs, market_reader=market, artifact_reader=store, source_bundle_ref=ref)
    assert store.reads.get(inputs.target_stream_ref.artifact_ref, 0) == 0
    assert len(store.values) == before


def test_gate_cross_venue_fee_swapping_is_not_account_fee_coverage():
    ref, inputs, store, market = _gate_bundle()
    fees = list(store.values[ref].payload["venue_fees"])
    changed = [{**fees[0], "fee": fees[1]["fee"]}, {**fees[1], "fee": fees[0]["fee"]}]
    ref = _rewrite(store, ref, venue_fees=changed)
    with pytest.raises(ValueError, match="grade/kind/subject mismatch"):
        require_cn_a_share_portfolio_source_qualification_v1(
            inputs, market_reader=market, artifact_reader=store, source_bundle_ref=ref)
    assert store.reads.get(inputs.target_stream_ref.artifact_ref, 0) == 0


def test_gate_reused_stock_component_ref_fails_before_any_component_read():
    ref, inputs, store, market = _gate_bundle()
    stocks = list(store.values[ref].payload["stock_sources"])
    stocks[1] = {**stocks[1], "membership": stocks[0]["membership"]}
    ref = _rewrite(store, ref, stock_sources=stocks)
    with pytest.raises(ValueError, match="independent and unique"):
        require_cn_a_share_portfolio_source_qualification_v1(
            inputs, market_reader=market, artifact_reader=store, source_bundle_ref=ref)
    assert set(store.reads) == {ref}


@pytest.mark.parametrize("venue_index", (0, 1), ids=("SH", "SZ"))
@pytest.mark.parametrize("mutation", ("expired", "late", "missing_minimum", "northbound", "boolean_rate"))
def test_gate_each_venue_fee_date_route_and_minimum_are_strict(venue_index, mutation):
    ref, inputs, store, market = _gate_bundle()
    fees = list(store.values[ref].payload["venue_fees"])
    fee_ref = _ref(fees[venue_index]["fee"])
    fee = store.values[fee_ref].payload
    if mutation == "expired":
        changes = {"effective_to_exclusive": _EXECUTION}
    elif mutation == "late":
        changes = {"available_at": UtcInstant(201)}
    else:
        facts = dict(fee["facts"])
        if mutation == "missing_minimum":
            facts.pop("minimum_commission_cents")
        elif mutation == "northbound":
            facts["route"] = "northbound_stock_connect"
        else:
            facts["commission_bps"] = True
        changes = {"facts": facts}
    fees[venue_index] = {**fees[venue_index], "fee": _rewrite(store, fee_ref, **changes)}
    ref = _rewrite(store, ref, venue_fees=fees)
    with pytest.raises(ValueError, match="interval incomplete|fee fields|adverse or ineligible"):
        require_cn_a_share_portfolio_source_qualification_v1(
            inputs, market_reader=market, artifact_reader=store, source_bundle_ref=ref)
    assert store.reads.get(inputs.target_stream_ref.artifact_ref, 0) == 0


@pytest.mark.parametrize("venue_index", (0, 1), ids=("SH", "SZ"))
def test_gate_fee_effective_and_available_boundary_only_reaches_formal_blocker(venue_index):
    ref, inputs, store, market = _gate_bundle()
    fees = list(store.values[ref].payload["venue_fees"])
    fee_ref = _ref(fees[venue_index]["fee"])
    fees[venue_index] = {**fees[venue_index], "fee": _rewrite(
        store, fee_ref, effective_from=_EXECUTION, available_at=_EXECUTION)}
    ref = _rewrite(store, ref, venue_fees=fees)
    with pytest.raises(CnASharePortfolioSourceAdmissionBlockedV1):
        require_cn_a_share_portfolio_source_qualification_v1(
            inputs, market_reader=market, artifact_reader=store, source_bundle_ref=ref)


def _replace_market(ref, inputs, store, market, bars):
    changed = InMemoryMarketBundleReader.build(
        bundle_key="synthetic-source-binding-probe", schema_version=1,
        coverage_start=market.manifest.coverage_start,
        coverage_end_exclusive=market.manifest.coverage_end_exclusive,
        instrument_catalog_hash=canonical_sha256(inputs.instrument_catalog),
        capabilities=(BAR_OPEN_CAPABILITY,), streams={"bars.open": tuple(bars)} if bars else {})
    matched = replace(inputs, market_bundle_ref=changed.bundle_ref)
    return _rewrite(store, ref, input_hash=matched.input_hash), matched, changed


@pytest.mark.parametrize("mutation", ("missing", "duplicate", "foreign", "late", "empty"))
def test_gate_open_capability_cannot_replace_exact_retained_stock_time_cover(mutation):
    ref, inputs, store, market = _gate_bundle()
    bars = list(market.streams["bars.open"])
    if mutation == "missing":
        bars.pop()
    elif mutation == "duplicate":
        bars[1] = replace(bars[1], instrument_id=bars[0].instrument_id)
    elif mutation == "foreign":
        bars[1] = replace(bars[1], instrument_id=InstrumentId(VenueId("xshe"), "000999"))
    elif mutation == "late":
        bars[1] = replace(bars[1], available_time=UtcInstant(201))
    else:
        bars = []
    ref, inputs, market = _replace_market(ref, inputs, store, market, bars)
    before = len(store.values)
    with pytest.raises(ValueError, match="source execution binding mismatch") as failure:
        require_cn_a_share_portfolio_source_qualification_v1(
            inputs, market_reader=market, artifact_reader=store, source_bundle_ref=ref)
    assert type(failure.value) is ValueError
    assert len(store.values) == before


@pytest.mark.parametrize("mutation", ("unsupported_kind", "zero_price", "foreign_currency", "extra_fields"))
def test_gate_rejects_invalid_native_open_payload(mutation):
    ref, inputs, store, market = _gate_bundle()
    bars = list(market.streams["bars.open"])
    payload: dict[str, Any] = dict(bars[0].payload)
    if mutation == "unsupported_kind":
        payload["bar_kind"] = "synthetic"
    elif mutation == "zero_price":
        payload["open_price"] = {**payload["open_price"], "units": 0}
    elif mutation == "foreign_currency":
        payload["open_price"] = {**payload["open_price"], "quote_currency": "USD"}
    else:
        payload["extra_future_volume"] = 999999
    bars[0] = replace(bars[0], payload=payload)
    ref, inputs, market = _replace_market(ref, inputs, store, market, bars)
    with pytest.raises(ValueError, match="bar_kind|positive|CNY|exact fields") as rejected:
        require_cn_a_share_portfolio_source_qualification_v1(
            inputs, market_reader=market, artifact_reader=store, source_bundle_ref=ref)
    assert type(rejected.value) is ValueError


@pytest.mark.parametrize("mutation", ("late_visible", "second_decision"))

def test_gate_single_source_window_cannot_cover_late_or_multiple_target_decisions(mutation):
    ref, inputs, store, market = _gate_bundle()
    repository = BacktestTargetStreamRepository(reader=store, publisher=store)
    old = repository.load(inputs.target_stream_ref)
    original = old.target_stream.events[0]
    events = ((replace(original, available_time=UtcInstant(101)),) if mutation == "late_visible" else
              (original, replace(original, event_id="second-decision", event_time=UtcInstant(110),
                                 available_time=UtcInstant(110))))
    target_ref = repository.publish(old.producer_context_ref, PrecomputedTargetStream("targets", events))
    inputs = replace(inputs, target_stream_ref=target_ref)
    ref = _rewrite(store, ref, input_hash=inputs.input_hash)
    with pytest.raises(ValueError, match="source decision binding mismatch"):
        require_cn_a_share_portfolio_source_qualification_v1(
            inputs, market_reader=market, artifact_reader=store, source_bundle_ref=ref)


class _StalledReader(InMemoryMarketBundleReader):
    def read_batch(self, cursor: EventCursor) -> tuple[tuple[MarketEvent, ...], EventCursor]:
        return (), cursor


class _CorruptReader(InMemoryMarketBundleReader):
    def read_batch(self, cursor: EventCursor) -> tuple[tuple[MarketEvent, ...], EventCursor]:
        batch, advanced = super().read_batch(cursor)
        changed = tuple(replace(event, source_key="synthetic.changed_after_manifest") for event in batch)
        return changed, advanced


@pytest.mark.parametrize("reader_type,expected", ((_StalledReader, "did not advance exactly"),
                                                (_CorruptReader, "stream digest mismatch")))
def test_gate_bounded_open_cursor_stall_or_raw_event_tamper_fails_closed(reader_type, expected):
    ref, inputs, store, market = _gate_bundle()
    reader = reader_type(market.bundle_ref, market.manifest, market.streams)
    with pytest.raises(ValueError, match=expected):
        require_cn_a_share_portfolio_source_qualification_v1(
            inputs, market_reader=reader, artifact_reader=store, source_bundle_ref=ref)
