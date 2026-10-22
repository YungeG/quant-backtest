"""Direct CAS-only source-pair fixtures, not economic/preflight qualification."""
from dataclasses import replace

import pytest

from crypto_quant_backtest import BacktestTargetStreamRepository, PrecomputedTargetStream
from crypto_quant_backtest.cn_a_share_portfolio_source_pair_draft_v0 import (
    _PAIR, read_cn_a_share_portfolio_source_pair_draft_v0,
)
from crypto_quant_domain import ArtifactEnvelope, ArtifactRef, SourceSequence, UtcInstant, VenueId
from tests.runtime.providers.test_cn_a_share_portfolio_preparation_inputs_v1 import _target_event
from tests.runtime.providers.test_cn_a_share_portfolio_source_bundle_draft_v0 import (
    _BUNDLE, _CODES, _bundle, _component, _ref, _rewrite,
)


def _pair(codes=(_CODES[0], _CODES[4])):
    first, inputs, store, _, _ = _bundle(codes)
    event = _target_event(inputs.instrument_ids)
    candidate = dict(event.payload["candidate"])
    candidate.update(decision_time=300, observed_through=299, effective_time=300, expires_at=450)
    later = replace(event, event_id="synthetic.second.target", event_time=UtcInstant(300),
                    available_time=UtcInstant(300), source_sequence=SourceSequence(2),
                    payload={**event.payload, "candidate": candidate})
    target = BacktestTargetStreamRepository(reader=store, publisher=store).publish(
        ArtifactRef("fixture_context", 1, "sha256:" + "9" * 64),
        PrecomputedTargetStream("targets", (event, later)))
    inputs = replace(inputs, target_stream_ref=target)
    first = _rewrite(store, first, input_hash=inputs.input_hash)
    # No fills, financial preparation, Engine, or historical payloads are needed
    # to exercise this source-only reader. Market qualification remains separate.
    stocks = []
    for instrument in inputs.instrument_ids:
        row = {"instrument_id": instrument}
        for kind in ("membership", "trade_status", "corporate_action"):
            row[kind] = _component(
                store, kind, instrument, instrument.venue,
                effective_from=UtcInstant(290), effective_to_exclusive=UtcInstant(450),
                available_at=UtcInstant(295 if kind == "membership" else 380))
        stocks.append(row)
    fees = [{"venue_id": venue, "fee": _component(
        store, "fee", None, VenueId(venue), effective_from=UtcInstant(290),
        effective_to_exclusive=UtcInstant(450), available_at=UtcInstant(380))}
        for venue in ("xshg", "xshe")]
    second = store.put(envelope=ArtifactEnvelope.create(_BUNDLE, 1, {
        **store.values[first].payload, "decision_at": UtcInstant(300),
        "execution_at": UtcInstant(400), "stock_sources": stocks, "venue_fees": fees,
    }))
    ref = store.put(envelope=ArtifactEnvelope.create(_PAIR, 1, {
        "type": "cn_a_share_portfolio_source_pair_draft", "schema_version": 1,
        "input_hash": inputs.input_hash, "synthetic_only": True, "formal_qualified": False,
        "windows": (
            {"decision_at": UtcInstant(100), "execution_at": UtcInstant(200), "bundle_ref": first},
            {"decision_at": UtcInstant(300), "execution_at": UtcInstant(400), "bundle_ref": second},
        ),
    }))
    return ref, inputs, store, first, second


@pytest.mark.parametrize("codes", ((_CODES[0], _CODES[4]), _CODES), ids=("two_stock", "ten_stock"))
def test_pure_cas_pair_reads_both_windows_without_formal_qualification(codes):
    ref, inputs, store, first, second = _pair(codes)
    before = dict(store.values)
    values = read_cn_a_share_portfolio_source_pair_draft_v0(ref, inputs=inputs, reader=store)
    assert tuple(value.bundle_ref for value in values) == (first, second)
    assert tuple((value.decision_at, value.execution_at) for value in values) == (
        (UtcInstant(100), UtcInstant(200)), (UtcInstant(300), UtcInstant(400)))
    assert all(value.component_count == 3 * len(codes) + 2 for value in values)
    assert all(value.synthetic_complete and not value.formal_qualified
               and not value.trade_authorized for value in values)
    assert len(store.reads) == 3 + 2 * (3 * len(codes) + 2)
    assert store.values == before


@pytest.mark.parametrize("mutation,reason", (
    ("one", "exactly two"), ("three", "exactly two"),
    ("same_snapshot", "distinct ordered"), ("reverse", "distinct ordered"),
    ("overlap", "distinct ordered"), ("first_clock", "retained snapshot clocks"),
    ("second_clock", "retained snapshot clocks"),
))
def test_pair_requires_distinct_ordered_windows_bound_to_snapshot_clocks(mutation, reason):
    ref, inputs, store, first, _ = _pair()
    rows = list(store.values[ref].payload["windows"])
    if mutation == "one":
        rows = rows[:1]
    elif mutation == "three":
        rows += rows[:1]
    elif mutation == "same_snapshot":
        rows[1] = {**rows[1], "bundle_ref": first}
    elif mutation == "reverse":
        rows.reverse()
    elif mutation == "overlap":
        rows[1] = {**rows[1], "decision_at": UtcInstant(200)}
    elif mutation == "first_clock":
        rows[0] = {**rows[0], "decision_at": UtcInstant(99)}
    else:
        rows[1] = {**rows[1], "execution_at": UtcInstant(401)}
    changed = _rewrite(store, ref, windows=rows)
    before = dict(store.values)
    with pytest.raises(ValueError, match=reason):
        read_cn_a_share_portfolio_source_pair_draft_v0(changed, inputs=inputs, reader=store)
    assert store.values == before
    if mutation in {"one", "three", "same_snapshot", "reverse", "overlap"}:
        assert set(store.reads) == {changed}


@pytest.mark.parametrize("changes", (
    {"formal_qualified": True}, {"synthetic_only": False}, {"input_hash": "sha256:" + "0" * 64},
))
def test_pair_scope_and_grade_reject_before_window_reads(changes):
    ref, inputs, store, _, _ = _pair()
    changed = _rewrite(store, ref, **changes)
    with pytest.raises(ValueError, match="scope/grade mismatch"):
        read_cn_a_share_portfolio_source_pair_draft_v0(changed, inputs=inputs, reader=store)
    assert set(store.reads) == {changed}


@pytest.mark.parametrize("fault", ("missing_snapshot", "corrupt_snapshot", "missing_component", "borrow_first"))
def test_prior_pair_success_cannot_hide_second_window_fault_or_borrow_expired_first_source(fault):
    ref, inputs, store, first, second = _pair()
    read_cn_a_share_portfolio_source_pair_draft_v0(ref, inputs=inputs, reader=store)
    store.reads.clear()  # Reset only test-adapter counters, not any source or consumption facts.
    if fault == "missing_snapshot":
        store.values.pop(second)
        reason = "missing, tampered or unavailable"
    elif fault == "corrupt_snapshot":
        store.values[second] = ArtifactEnvelope.create(_BUNDLE, 1, {
            **store.values[second].payload, "decision_at": UtcInstant(301)})
        reason = "readback identity mismatch"
    else:
        stocks = list(store.values[second].payload["stock_sources"])
        if fault == "missing_component":
            store.values.pop(_ref(stocks[-1]["corporate_action"]))
            reason = "missing, tampered or unavailable"
        else:
            stocks[0] = {**stocks[0], "membership": store.values[first].payload["stock_sources"][0]["membership"]}
            second = _rewrite(store, second, stock_sources=stocks)
            rows = list(store.values[ref].payload["windows"])
            rows[1] = {**rows[1], "bundle_ref": second}
            ref = _rewrite(store, ref, windows=rows)
            reason = "effective/availability interval incomplete"
    before = dict(store.values)
    with pytest.raises(ValueError, match=reason):
        read_cn_a_share_portfolio_source_pair_draft_v0(ref, inputs=inputs, reader=store)
    assert store.values == before
    assert first in store.reads and second in store.reads
