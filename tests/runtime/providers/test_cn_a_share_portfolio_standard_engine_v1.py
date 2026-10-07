"""Native Engine unit sentinels; synthetic Aug2023, NOT actual October A/B."""
from dataclasses import replace
import json

import pytest
import crypto_quant_domain as d
from crypto_quant_backtest.cn_a_share_portfolio_standard_native_state_v1 import _native_snapshot_at_v1
from crypto_quant_backtest.cn_a_share_portfolio_standard_result_v1 import _verify_standard_native_result_v1
from crypto_quant_backtest.cn_a_share_portfolio_settlement_development_v1 import (
    _book_body, read_cn_a_share_portfolio_settlement_book_source_v1,
)
import crypto_quant_trading as t
from crypto_quant_backtest.profile_portfolio_execution import _profile_portfolio_semantic_spec_from_case
from crypto_quant_backtest.slippage import SlippageApplicabilityEnvelope
from crypto_quant_backtest.cn_a_share_portfolio_standard_engine_v1 import _CnASharePortfolioStandardEngineV1
from tests.runtime.providers.test_cn_a_share_portfolio_standard_case_v1 import _case


def _engine_case(*, blocked=False):
    case, inputs, store, bars = _case()
    if blocked:
        from crypto_quant_backtest.execution import BarLiquidityEvidence
        inputs = replace(inputs, opening_terms=tuple(replace(term,
            liquidity=BarLiquidityEvidence.create(evidence_key="native.expiry.synthetic", evidence_version=1,
                market_event=next(b for b in bars if b.event_id == term.bar_event_id),
                evaluated_at=term.opening_at, approved=False, reason_code="synthetic_limit_lock",
                source_hash=term.bar_event_hash)) for term in inputs.opening_terms))
    # Freeze a broad model applicability bound BEFORE definition/case sealing.
    # The inherited fixture only admitted old 100-share orders, not live sizing.
    def widen(term):
        old = term.slippage_model.applicability_envelope
        bound = SlippageApplicabilityEnvelope.create(envelope_key=old.envelope_key,
            envelope_version=old.envelope_version, instrument_id=old.instrument_id,
            valid_from=old.valid_from, valid_to_exclusive=old.valid_to_exclusive,
            maximum_quantity=replace(old.maximum_quantity, units=1_000_000),
            allowed_market_state_keys=old.allowed_market_state_keys)
        return replace(term, slippage_model=replace(term.slippage_model, applicability_envelope=bound))
    inputs = replace(inputs, opening_terms=tuple(widen(term) for term in inputs.opening_terms))
    definition = inputs.definition()
    plan = replace(case.execution_case_plan, definition=definition,
        source_refs=(("definition", store.put(envelope=definition)),
            ("target_stream", inputs.scope.target_stream_ref.to_artifact_ref())))
    template = replace(case, execution_case_plan=plan, semantic_spec=None)
    old = case.semantic_spec
    assert old is not None
    spec = _profile_portfolio_semantic_spec_from_case(template, spec_key=old.spec_key,
        spec_version=old.spec_version, identity_namespace=old.identity_namespace,
        identity_plan=old.identity_plan)
    case = replace(template, semantic_spec_hash=spec.semantic_spec_hash, semantic_spec=spec)
    return case, inputs, store


@pytest.fixture(scope="module")
def native_result():
    case, inputs, store = _engine_case()
    outcome = _CnASharePortfolioStandardEngineV1(artifact_reader=store)._run(case, None)
    assert outcome.result is not None, outcome
    _verify_standard_native_result_v1(case=case, reader=store, result=outcome.result.to_canonical_dict())
    return case, inputs, store, outcome.result


def test_profile_owned_engine_books_two_stocks_in_one_native_batch(native_result):
    _, inputs, _, result = native_result
    assert len(result.fills) == 2
    assert len(result.fee_assessments) == 4
    assert len(result.decision_batches) == len(result.normalized_targets) == 1
    assert result.final_ledger_state == t.GenericLedger(inputs.scope.ledger_schema).project(result.final_journal)
    assert {fill.instrument_id for fill in result.fills} == set(inputs.scope.instrument_ids)
    assert all(b.amount.units >= 0 for b in result.final_ledger_state.cash_balances)
    assert sum(a.role == "native_opening_batch" for a in result.financial_artifacts) == 1
    assert sum(a.role == "native_daily_snapshot" for a in result.financial_artifacts) == 1
    assert sum(a.role == "native_attempt_witness" for a in result.financial_artifacts) == 1
    assert result.order_plans == ()  # Native coordinator/plans retained in financial artifacts.


def _inline(raw, role):
    return next(a for a in raw["financial_artifacts"] if a["role"] == role)


def _reseal(raw, artifact):
    """Keep envelope, artifact and trace hashes valid so a semantic guard must reject."""
    envelope = d.ArtifactEnvelope.create("cn_a_share_portfolio_" + artifact["role"], 1,
        artifact["payload"]["payload"])
    artifact["payload"] = json.loads(d.canonical_bytes(envelope))
    artifact["result_hash"] = d.canonical_sha256(envelope)
    index = raw["financial_artifacts"].index(artifact)
    raw["trace"]["entries"][index]["evidence_hash"] = d.canonical_sha256(artifact)


@pytest.mark.parametrize("part", ["final_filled_evidence", "daily_book", "batch_book",
    "daily_stale_head", "daily_pending", "final_pending", "incomplete_cursor",
    "run_end_report", "trace_omission"])
def test_cold_native_result_rejects_rehashed_incomplete_witness(native_result, part):
    case, inputs, store, result = native_result
    raw = json.loads(d.canonical_bytes(result.to_canonical_dict()))
    day_artifact = _inline(raw, "native_daily_snapshot")
    day = day_artifact["payload"]["payload"]
    witness_artifact = _inline(raw, "native_attempt_witness")
    witness = witness_artifact["payload"]["payload"]
    artifact = None
    if part == "final_filled_evidence":
        stream = result.order_streams[0]
        last = stream.records[-1]
        assert last.event.event_type is d.OrderEventType.ORDER_FILLED
        forged = t.OrderEventStream.from_records(stream.order, (*stream.records[:-1],
            replace(last, event=replace(last.event, evidence_id=d.canonical_sha256("foreign-terminal-proof")))))
        raw["order_streams"][0] = json.loads(d.canonical_bytes(forged))
    elif part in {"daily_book", "batch_book"}:
        empty = _book_body(t.SettlementBook(inputs.scope.account_id))
        # Unlike the worker probe, this is an independently decoded VALID Native Book.
        assert read_cn_a_share_portfolio_settlement_book_source_v1(json.loads(d.canonical_bytes(empty))) == t.SettlementBook(inputs.scope.account_id)
        artifact = day_artifact if part == "daily_book" else _inline(raw, "native_opening_batch")
        artifact["payload"]["payload"]["book" if part == "daily_book" else "book_after"] = json.loads(d.canonical_bytes(empty))
    elif part == "daily_stale_head":
        assert inputs.initial_journal.entry_count > 0
        assert day["journal_count"] > inputs.initial_journal.entry_count
        day["journal_count"] = inputs.initial_journal.entry_count
        # LEGAL complete initial prefix, independently reprojected at the real daily clock.
        day["snapshot"] = json.loads(d.canonical_bytes(_native_snapshot_at_v1(
            inputs, inputs.initial_journal, inputs.daily_marks[0])))
        artifact = day_artifact
    elif part in {"daily_pending", "final_pending"}:
        artifact = day_artifact if part == "daily_pending" else witness_artifact
        artifact["payload"]["payload"]["pending_intentions"] = [json.loads(d.canonical_bytes(result.order_streams[0].order))]
    elif part == "incomplete_cursor":
        cursor = case.timeline.open_cursor(batch_size=case.timeline_batch_size)
        assert not cursor.window_complete and cursor.emitted_count == 0
        witness["cursor"] = json.loads(d.canonical_bytes(cursor))
        artifact = witness_artifact
    elif part == "run_end_report":
        forged = replace(result.run_end_report, settlement_state_hash=d.canonical_sha256("foreign-settlement-state"))
        raw["run_end_report"] = json.loads(d.canonical_bytes(forged))
        witness["run_end_report_hash"] = forged.report_hash
        artifact = witness_artifact
    else:
        entries = raw["trace"]["entries"]
        entries.pop(0)
        for i, entry in enumerate(entries):
            entry["sequence"] = i
    if artifact is not None:
        _reseal(raw, artifact)
    with pytest.raises(ValueError, match="standard native"):
        _verify_standard_native_result_v1(case=case, reader=store, result=raw)


@pytest.fixture(scope="module")
def expired_result():
    case, inputs, store = _engine_case(blocked=True)
    outcome = _CnASharePortfolioStandardEngineV1(artifact_reader=store)._run(case, None)
    assert outcome.result is not None, outcome
    _verify_standard_native_result_v1(case=case, reader=store, result=outcome.result.to_canonical_dict())
    assert not outcome.result.fills and not outcome.result.fee_assessments
    assert all(s.state is not None and s.state.status is d.OrderStatus.EXPIRED for s in outcome.result.order_streams)
    return case, store, outcome.result


@pytest.mark.parametrize("part", ["valid", "omit", "evidence"])
def test_day_expiry_closes_exact_native_history(expired_result, part):
    case, store, result = expired_result
    raw = json.loads(d.canonical_bytes(result.to_canonical_dict()))
    if part == "valid":
        assert len(result.order_streams) == 2
        assert all(s.order.intent.time_in_force is d.TimeInForce.DAY for s in result.order_streams)
        assert not result.run_end_report.terminated_orders
        return
    stream = result.order_streams[0]
    assert stream.records[-1].event.event_type is d.OrderEventType.ORDER_EXPIRED
    records = stream.records[:-1] if part == "omit" else (*stream.records[:-1],
        replace(stream.records[-1], event=replace(stream.records[-1].event,
            evidence_id=d.canonical_sha256("foreign-expiry-proof"))))
    forged = t.OrderEventStream.from_records(stream.order, records)
    raw["order_streams"][0] = json.loads(d.canonical_bytes(forged))
    with pytest.raises(ValueError, match="final Order streams differ from complete native event history"):
        _verify_standard_native_result_v1(case=case, reader=store, result=raw)
