"""Cold native witness validation; no Engine run, Fill selection or journal booking.

Projection and native source/fee checks are read-only proof checks. The standard
atomic attempt graph owns the economic result; this module publishes nothing.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import json
from typing import Any

import crypto_quant_domain as d
import crypto_quant_trading as t

from .artifact_envelope_reader import ArtifactEnvelopeReader
from .cn_a_share_portfolio_engine_result_source_v1 import _financial_source_facts
from .cn_a_share_portfolio_standard_case_v1 import _bind_standard_portfolio_sources_v1
from .cn_a_share_portfolio_standard_engine_v1 import (
    _at, _day, _checkpoint, _admit, _Admission, _COMPONENT, _COMPONENT_HASH,
    _RUN_END_MARK_POLICY, _native_run_end_marks_v1, _native_admission_plan_v1, _rejected_admission_stream_v1,
    _append_event, _WORKING,
)
from .cn_a_share_portfolio_standard_native_state_v1 import (
    _native_signal_target_v1, _native_rebalance_plan_v1, _native_snapshot_at_v1,
)
from .cn_a_share_portfolio_standard_opening_v1 import (
    _StandardOpenSourcesV1, _StandardCurrentOpenProofV1,
    _StandardOpeningOutcomeV1, _StandardFinancialStepV1, _standard_market_fee_v1,
    _standard_full_fill_budget_v1,
)
from .cn_a_share_portfolio_settlement_development_v1 import (
    read_cn_a_share_portfolio_settlement_book_source_v1, _book_body,
    CnASharePortfolioSettlementDevelopmentV1, _build_cn_a_share_portfolio_settlement_facts_v1,
)
from .cn_a_share_portfolio_venue_funding_development_v1 import plan_cn_portfolio_venue_funding_development_v1
from .cn_a_share_portfolio_daily_nav_diagnostic_v1 import _reject_unmodeled_dividends_v1
from .cn_a_share_portfolio_financial_core_v1 import _id
from .execution_inputs import (
    _read_order, _read_order_event_stream, _read_reservation_schedule,
    _read_domain_id, _read_simulation_instant, _read_journal_entry, _read_fill,
    _read_portfolio_snapshot, _read_utc,
)
from .execution import BarOpenObservation, BarOpenKind, NoEligibleBarAction
from .engine import ExecutionTrace, ExecutionTraceEntry, EngineStage, _stable_tuple
from .run_end import RunEndCoordinator, RunEndEvidence, MarkToMarketCloseoutPolicy
from .timeline import TimelineCursorV2
from .profile_portfolio_execution import _ResolvedProfilePortfolioCaseV1
from .evidence_repository import BacktestEvidenceRepository
from .publication_refs import BacktestCanonicalPublicationRef
from .target_repository import _artifact_ref


def _map(value: object, fields: set[str] | None = None) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or (fields is not None and set(value) != fields):
        raise ValueError("standard native witness exact mapping fields mismatch")
    return value


def _seq(value: object) -> tuple[Any, ...]:
    if not isinstance(value, (tuple, list)):
        raise ValueError("standard native witness needs a finite sequence")
    return tuple(value)


def _equal(expected: object, actual: object, message: str) -> None:
    if d.canonical_bytes(expected) != d.canonical_bytes(actual):
        raise ValueError("standard native witness " + message)


def _count(value: object, maximum: int) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("standard native witness prefix count is invalid")
    return value


def _read_retained(reader: ArtifactEnvelopeReader, ref: d.ArtifactRef) -> d.ArtifactEnvelope:
    read = reader.read(ref=ref)
    if (type(read) is not d.ArtifactReadResult or d.ArtifactRef.from_envelope(read.envelope) != ref
            or read.source_bytes != d.canonical_bytes(read.envelope)
            or read.source_hash != d.canonical_sha256(read.envelope)):
        raise ValueError("standard native cache retained byte/ref binding mismatch")
    return read.envelope


def _verify_standard_native_result_v1(*, case: _ResolvedProfilePortfolioCaseV1,
    reader: ArtifactEnvelopeReader, result: object,
) -> None:
    # Normalize both live typed and cold raw facts through Domain canonical bytes.
    raw = _map(json.loads(d.canonical_bytes(result)), {"type", "schema_version", "case_hash",
        "target_stream_digest", "trace", "decision_batches", "allocations", "approved_targets",
        "normalized_targets", "order_plans", "order_streams", "fills", "slippage_decisions",
        "fee_assessments", "financial_artifacts", "final_journal", "final_ledger_state",
        "final_portfolio_snapshot", "run_end_report"})
    if (raw["type"] != "engine_execution_result" or type(raw["schema_version"]) is not int
            or raw["schema_version"] != 1 or raw["case_hash"] != case.case_hash
            or raw["target_stream_digest"] != case.target_stream.target_stream_digest
            or _seq(raw["order_plans"]) or _seq(raw["slippage_decisions"])):
        raise ValueError("standard native result case/version/legacy-result mismatch")
    bound = _bind_standard_portfolio_sources_v1(case, reader)
    inputs, openings = bound.inputs, bound.openings
    journal, ledger, fills, fees = _financial_source_facts({"journal": raw["final_journal"],
        "ledger_state": raw["final_ledger_state"], "fills": raw["fills"],
        "fee_assessments": raw["fee_assessments"]}, inputs.scope.ledger_schema)
    snapshot = _read_portfolio_snapshot(raw["final_portfolio_snapshot"])
    streams = tuple(_read_order_event_stream(v) for v in _seq(raw["order_streams"]))
    by_order = {s.order.order_id: s for s in streams}
    if len(by_order) != len(streams):
        raise ValueError("standard native result has duplicate Order identities")
    facts: dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {}
    ordered_facts: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for item in _seq(raw["financial_artifacts"]):
        artifact = _map(item)
        role = artifact["role"]
        inline = _map(artifact["payload"])
        fact = d.ArtifactEnvelope.create("cn_a_share_portfolio_" + role, 1, inline["payload"])
        _equal(fact, inline, "inline fact envelope substitution")
        if (artifact["component_key"] != _COMPONENT or artifact["component_version"] != 1
                or artifact["component_digest"] != _COMPONENT_HASH
                or artifact["input_hash"] != d.canonical_sha256(inputs.definition())
                or artifact["result_hash"] != d.canonical_sha256(fact)):
            raise ValueError("standard native financial artifact component/source/hash mismatch")
        pair = (artifact, _map(inline["payload"]))
        facts.setdefault(role, []).append(pair)
        ordered_facts.append(pair)
    allowed = {"native_signal", "native_opening_batch", "native_daily_snapshot", "native_attempt_witness",
        "pending_no_real_open", "working_no_real_open", "native_pretrade_rejection"}
    if set(facts) - allowed or len(facts.get("native_attempt_witness", ())) != 1:
        raise ValueError("standard native result lacks its unique whole attempt witness")
    witness_artifact, witness = facts["native_attempt_witness"][0]
    if (witness.get("type") != "cn_a_share_portfolio_standard_native_witness"
            or witness.get("schema_version") != 1 or witness["case_hash"] != case.case_hash
            or witness["definition_hash"] != d.canonical_sha256(inputs.definition())
            or witness["target_stream_digest"] != case.target_stream.target_stream_digest
            or witness["initial_journal_hash"] != inputs.initial_journal.journal_hash
            or witness["final_journal_hash"] != journal.journal_hash
            or witness["final_ledger_hash"] != ledger.state_hash
            or witness["run_end_report_hash"] != d.canonical_sha256(raw["run_end_report"])
            or any(witness[k] is not False for k in ("source_qualification_verified", "broker_shared_pool_verified", "trade_authorized"))):
        raise ValueError("standard native witness run/start/end/qualification mismatch")
    book = read_cn_a_share_portfolio_settlement_book_source_v1(witness["book"])
    schedules = tuple(_read_reservation_schedule(s) for s in _seq(witness["schedules"]))
    by_schedule = {s.order_id: s for s in schedules}
    accepted_ids = {s.order.order_id for s in streams if any(
        r.event.event_type is d.OrderEventType.ORDER_ACCEPTED for r in s.records)}
    if len(by_schedule) != len(schedules) or set(by_schedule) != accepted_ids:
        raise ValueError("standard native result schedules must exact-cover original Orders")
    by_obligation = {o.obligation.settlement_obligation_id: o for o in book.obligations}

    def context(value: object) -> _StandardOpenSourcesV1:
        item = _map(value, {"at", "source_hash", "journal_count", "book_event_count",
            "obligation_ids", "streams", "schedules"})
        count = _count(item["journal_count"], journal.entry_count)
        prefix = t.AccountingJournal.from_entries(journal.entries[:count])
        obligations = tuple(by_obligation[_read_domain_id(v)] for v in _seq(item["obligation_ids"]))
        events = book.events[:_count(item["book_event_count"], len(book.events))]
        prefix_book = t.SettlementBook.from_events(book.account_id, obligations, events)
        prefix_streams = []
        for identity, length in _seq(item["streams"]):
            stream = by_order[_read_domain_id(identity)]
            prefix_streams.append(t.OrderEventStream.from_records(stream.order,
                stream.records[:_count(length, stream.event_count)]))
        prefix_schedules = tuple(by_schedule[_read_domain_id(v)] for v in _seq(item["schedules"]))
        native = _StandardOpenSourcesV1(inputs, prefix, prefix_book, tuple(prefix_streams),
            prefix_schedules, case.financial_state.settlement_rules, _read_simulation_instant(item["at"]))
        _equal(_checkpoint(native), item, "checkpoint does not reconstruct the actual full native prefix")
        return native

    # Validate all final histories through native cash, exact T+1 and full-clock guards.
    _StandardOpenSourcesV1(inputs, journal, book, streams, schedules,
        case.financial_state.settlement_rules, _at(case.timeline.window.end_exclusive, 200))
    signal_facts = sorted(facts.get("native_signal", ()), key=lambda pair: _read_simulation_instant(pair[0]["occurred_at"]))
    if len(signal_facts) != len(case.target_stream.events):
        raise ValueError("standard native signals do not exact-cover the target stream")
    native_signals = []
    native_plans = []
    for index, (artifact, fact) in enumerate(signal_facts):
        event = case.target_stream.events[index]
        cancellation_sources = context(fact["cancel_sources"])
        coordinator_sources = context(fact["coordinator_sources"])
        signal = _native_signal_target_v1(inputs=inputs, journal=cancellation_sources.journal, event=event)
        _equal(signal, fact["signal"], "live signal equity/quantity source mismatch")
        plan = _native_rebalance_plan_v1(inputs=inputs, signal=signal, journal=coordinator_sources.journal,
            settlement_book=coordinator_sources.settlement_book, order_streams=coordinator_sources.order_streams,
            reservation_schedules=coordinator_sources.reservation_schedules,
            market_rules=coordinator_sources.market_rules, at=coordinator_sources.at)
        _equal(plan, fact["coordinator_plan"], "native current-holding delta plan mismatch")
        if artifact["source_event_id"] != event.event_id:
            raise ValueError("standard native signal used another target event")
        native_signals.append(signal)
        native_plans.append(plan)
    for name, values in (("decision_batches", tuple(s.decision_batch for s in native_signals)),
        ("allocations", tuple(s.allocation for s in native_signals)),
        ("approved_targets", tuple(s.approved_target for s in native_signals)),
        ("normalized_targets", tuple(s.normalized_target for s in native_signals))):
        _equal(values, raw[name], "signal result collection mismatch: " + name)

    from crypto_quant_trading.profiles.cn_a_share.portfolio_order_plan_v1 import (
        CnASharePortfolioOrderPlanV1, CnASharePortfolioOrderProposalV1,
    )
    admissions: dict[d.DomainId, _Admission] = {}
    original_streams: dict[d.DomainId, tuple[t.OrderEventStream, t.OrderReservationSchedule]] = {}
    for value in _seq(witness["admissions"]):
        item = _map(value, {"order_id", "signal_index", "plan", "sources", "fee"})
        identity = _read_domain_id(item["order_id"])
        stream = by_order[identity]
        origin = context(item["sources"])
        index = _count(item["signal_index"], len(native_signals) - 1)
        signal = native_signals[index]
        order = stream.order
        planned = next(p for p in _seq(signal_facts[index][1]["coordinator_plan"]["planned_orders"])
            if d.canonical_bytes(p["instrument_id"]) == d.canonical_bytes(order.intent.instrument_id))
        candidate = _read_order({"type": "order", "order_id": item["order_id"],
            "account_id": inputs.scope.account_id, "intent": planned["intent"],
            "created_at": json.loads(d.canonical_bytes(order.created_at))})
        expected_intent = replace(candidate.intent, time_in_force=inputs.execution_policy.time_in_force_for(candidate.intent.side))
        if (order.intent != expected_intent
                or order.order_id != case.domain_id(f"signal.{index}.{order.intent.instrument_id}.order")
                or order.created_at.instant != inputs.signal_marks[index].at.instant):
            raise ValueError("standard native Order is not the sealed live delta/coordinate")
        terms = next(t for t in inputs.opening_terms if t.opening_at == origin.at.instant
            and t.instrument_id == order.intent.instrument_id and t.side is order.intent.side)
        _, fee = _standard_market_fee_v1(order, terms)
        _equal(fee, item["fee"], "original native fee proposal mismatch")
        proposals = []
        for proposed in _seq(item["plan"]["proposed"]):
            matching = next(s.order for s in streams if d.canonical_bytes(s.order.intent) == d.canonical_bytes(proposed["intent"]))
            term = next(t for t in inputs.opening_terms if t.opening_at == origin.at.instant
                and t.instrument_id == matching.intent.instrument_id and t.side is matching.intent.side)
            market, estimate = _standard_market_fee_v1(matching, term)
            proposals.append(CnASharePortfolioOrderProposalV1(matching.intent,
                market.calculated_notional if matching.intent.side is d.OrderSide.BUY else d.Money(0, d.Scale(2), "CNY"),
                estimate.fee_estimate.total_fee, term.reservation_rules.rule_set_hash))
        plan = CnASharePortfolioOrderPlanV1.create(account_id=inputs.scope.account_id,
            target_id=signal.normalized_target.normalized_target_id,
            target_hash=signal.normalized_target.normalized_target_hash, as_of=origin.at.instant,
            policy=inputs.execution_policy, cash=origin.cash, sellability=origin.sellability,
            working_orders=origin.order_streams, reservation_schedules=origin.reservation_schedules, proposed=tuple(proposals))
        _equal(plan, item["plan"], "original admission plan/source substitution")
        admission = _Admission(index, plan, origin, fee)
        opening_index = next(i for i, event in enumerate(openings) if event.event_id == terms.bar_event_id)
        accepted, schedule = _admit(case, order, opening_index, admission, terms)
        if stream.records[:8] != accepted.records or by_schedule[identity] != schedule or identity in admissions:
            raise ValueError("standard native single original acceptance/reservation/coordinate mismatch")
        admissions[identity] = admission
        original_streams[identity] = (accepted, schedule)
    if set(admissions) != accepted_ids:
        raise ValueError("standard native admissions must exact-cover all accepted Orders")
    rejected_ids = set()
    rejections: dict[d.DomainId, Mapping[str, Any]] = {}
    for artifact, value in facts.get("native_pretrade_rejection", ()):
        rejection = _map(value["rejection"], {"order", "signal_index", "sources", "candidate_proposals", "native_failure", "fee"})
        order = _read_order(rejection["order"])
        origin = context(rejection["sources"])
        signal_index = _count(rejection["signal_index"], len(native_signals) - 1)
        signal = native_signals[signal_index]
        if order.order_id != case.domain_id(f"signal.{signal_index}.{order.intent.instrument_id}.order"):
            raise ValueError("standard native rejected intent has another identity")
        planned = next(p for p in _seq(signal_facts[signal_index][1]["coordinator_plan"]["planned_orders"])
            if d.canonical_bytes(p["instrument_id"]) == d.canonical_bytes(order.intent.instrument_id))
        candidate_order = _read_order({"type": "order", "order_id": rejection["order"]["order_id"],
            "account_id": inputs.scope.account_id, "intent": planned["intent"],
            "created_at": rejection["order"]["created_at"]})
        if order.intent != replace(candidate_order.intent,
                time_in_force=inputs.execution_policy.time_in_force_for(candidate_order.intent.side)):
            raise ValueError("standard native rejection does not reference its exact live delta")
        proposals = []
        for proposed in _seq(rejection["candidate_proposals"]):
            matching = next(s.order for s in streams if d.canonical_bytes(s.order.intent) == d.canonical_bytes(proposed["intent"]))
            term = next(t for t in inputs.opening_terms if t.opening_at == origin.at.instant
                and t.instrument_id == matching.intent.instrument_id and t.side is matching.intent.side)
            market, fee = _standard_market_fee_v1(matching, term)
            native = CnASharePortfolioOrderProposalV1(matching.intent,
                market.calculated_notional if matching.intent.side is d.OrderSide.BUY else d.Money(0, d.Scale(2), "CNY"),
                fee.fee_estimate.total_fee, term.reservation_rules.rule_set_hash)
            _equal(native, proposed, "rejected candidate native money/fee source mismatch")
            proposals.append(native)
        try:
            _native_admission_plan_v1(signal, origin, tuple(proposals))
        except ValueError as error:
            if str(error) != rejection["native_failure"] or str(error) not in {
                "portfolio plan may not reuse cash or prefinance sell receipts",
                "portfolio plan T+1 forbids unsettled or reserved sell"}:
                raise ValueError("standard native rejection has wrong failure source") from error
        else:
            raise ValueError("standard native intent falsely claims a money/T+1 rejection")
        terms = next(t for t in inputs.opening_terms if t.opening_at == origin.at.instant
            and t.instrument_id == order.intent.instrument_id and t.side is order.intent.side)
        _, fee = _standard_market_fee_v1(order, terms)
        _equal(fee, rejection["fee"], "rejected intent fee was substituted")
        opening_index = next(i for i, e in enumerate(openings) if e.event_id == terms.bar_event_id)
        native_stream = _rejected_admission_stream_v1(case, order, signal_index, opening_index,
            terms, d.canonical_sha256(rejection))
        _equal(native_stream, value["stream"], "rejected native lifecycle mismatch")
        if (by_order[order.order_id] != native_stream or order.order_id in accepted_ids
                or order.order_id in rejected_ids or artifact["source_event_id"] != terms.bar_event_id):
            raise ValueError("standard native rejected Order was hidden, accepted or duplicated")
        rejected_ids.add(order.order_id)
        rejections[order.order_id] = value
    if set(by_order) != accepted_ids | rejected_ids:
        raise ValueError("standard native result hides an unproved Order lifecycle")

    batches = sorted(facts.get("native_opening_batch", ()), key=lambda pair: _read_utc(pair[1]["when"]))
    expected_times = sorted({e.event_time for e in openings})
    if len(batches) != len(expected_times) or witness["opening_count"] != len(batches):
        raise ValueError("standard native opening batch exact-cover mismatch")
    collected_fills = []
    collected_fees = []
    verified_outcomes: dict[d.UtcInstant, tuple[_StandardOpeningOutcomeV1, ...]] = {}
    prior_count = inputs.initial_journal.entry_count
    for when, (artifact, batch) in zip(expected_times, batches, strict=True):
        if _read_utc(batch["when"]) != when:
            raise ValueError("standard native opening source time substitution")
        prior, current = context(batch["prior"]), context(batch["current"])
        if prior.journal.entry_count != prior_count:
            raise ValueError("standard native batch skipped the actual prior journal head")
        funding = tuple(_read_journal_entry(v) for v in _seq(batch["funding"]))
        _equal(funding, current.journal.entries[prior_count:], "funding pair is not the actual whole journal suffix")
        required = {key: 0 for key, _ in prior.available_by_venue}
        for admission in admissions.values():
            if admission.sources.at.instant == when:
                for proposed in admission.plan.proposed:
                    # A shared plan is encountered once per admitted Order.
                    if proposed.intent != by_order[next(k for k, a in admissions.items() if a is admission)].order.intent:
                        continue
                    key = next(k for k in required if k.venue_id == proposed.intent.instrument_id.venue)
                    required[key] += proposed.principal.units + proposed.estimated_fee.units
        for stream in prior.order_streams:
            if stream.state is None or stream.state.status not in {d.OrderStatus.ACCEPTED, d.OrderStatus.ACTIVE}:
                continue
            candidates = tuple(term for term in inputs.opening_terms if term.opening_at == when
                and term.instrument_id == stream.order.intent.instrument_id and term.side is stream.order.intent.side)
            if candidates:
                _, fresh = _standard_market_fee_v1(stream.order, candidates[0])
                key = next(k for k in required if k.venue_id == stream.order.intent.instrument_id.venue)
                required[key] += max(0, fresh.fee_estimate.total_fee.units - admissions[stream.order.order_id].fee.fee_estimate.total_fee.units)
        latest = max((s for s in native_signals if s.snapshot.timestamp < when), key=lambda s: s.snapshot.timestamp)
        expected_funding = plan_cn_portfolio_venue_funding_development_v1(journal=prior.journal,
            ledger_schema=inputs.scope.ledger_schema, settlement_book=prior.settlement_book,
            order_streams=prior.order_streams, reservation_schedules=prior.reservation_schedules,
            market_rules=prior.market_rules,
            required_by_venue=tuple((k, d.Money(v, d.Scale(2), "CNY")) for k, v in required.items()),
            at=_at(when, 50), target_hash=d.canonical_sha256(latest.normalized_target))
        _equal(expected_funding, funding, "actual funding does not bind settled native requirements")
        selected = []
        native_outcomes = []
        for value in _seq(batch["outcomes"]):
            item = _map(value)
            source = _map(item["proof"])
            stream = next(s for s in current.order_streams if s.stream_hash == source["stream_hash"])
            admission = admissions[stream.order.order_id]
            event = next(e for e in openings if e.event_time == when and e.instrument_id == stream.order.intent.instrument_id)
            terms = next(t for t in inputs.opening_terms if t.bar_event_id == event.event_id and t.side is stream.order.intent.side)
            proof = _StandardCurrentOpenProofV1(admission.plan, admission.sources, current, stream,
                admission.fee, BarOpenObservation.from_event(event), terms)
            _equal(proof, source, "current observed-open proof substitution")
            outcome = _StandardOpeningOutcomeV1(proof, NoEligibleBarAction(item["action"]), item["reason"],
                None if item["fill"] is None else _read_fill(item["fill"]), tuple(selected))
            _equal(outcome, item, "no-fill/full-fill selection or cumulative proof mismatch")
            native_outcomes.append(outcome)
            if outcome.fill is not None:
                selected.append(proof)
        expected_orders = {s.order.order_id for s in current.order_streams
            if s.state is not None and s.state.status in {d.OrderStatus.ACCEPTED, d.OrderStatus.ACTIVE}
            and any(t.opening_at == when and t.instrument_id == s.order.intent.instrument_id
                and t.side is s.order.intent.side for t in inputs.opening_terms)}
        if {o.proof.stream.order.order_id for o in native_outcomes} != expected_orders:
            raise ValueError("standard native opening omitted a standing/new eligible Order")
        verified_outcomes[when] = tuple(native_outcomes)
        selected_outcomes = tuple(o for o in native_outcomes if o.fill is not None)
        if tuple(o.proof for o in selected_outcomes) != tuple(sorted(selected, key=lambda p: (
                p.stream.order.intent.side is d.OrderSide.BUY, p.stream.order.intent.instrument_id))):
            raise ValueError("standard native full-Fill collection is not cumulative sell-first")
        if selected and not _standard_full_fill_budget_v1(tuple(selected)):
            raise ValueError("standard native opening budget exceeds held/free settled cash")
        steps = _seq(batch["steps"])
        if len(steps) != len(selected_outcomes):
            raise ValueError("standard native full-Fill steps omitted or duplicated")
        for outcome, source in zip(selected_outcomes, steps, strict=True):
            step = _StandardFinancialStepV1(outcome, _read_order_event_stream(source["terminal_order"]))
            _equal(step, source, "terminal financial step source mismatch")
            fill = outcome.fill
            assert fill is not None
            collected_fills.append(fill)
            for role, basis, rule_set in (("fill_fee", t.FeeAssessmentBasisEvidence.for_fill(fill), step.final_fill_rules),
                ("order_fee", t.FeeAssessmentBasisEvidence.for_order(step.terminal_order), step.final_order_rules)):
                checked = t.FeeAssessmentEngine().assess(basis=basis, rule_set=rule_set,
                    fee_assessment_id=_id(d.DomainIdKind.FEE, role, outcome.outcome_hash), assessment_time=when)
                if checked.result is None:
                    raise ValueError("standard native current final fee proof rejected")
                collected_fees.append(checked.result.assessment)
        after_count = _count(batch["journal_count_after"], journal.entry_count)
        if after_count != current.journal.entry_count + 3 * len(selected_outcomes):
            raise ValueError("standard native atomic batch journal does not exact-cover Fill and two fees")
        protected = {key.venue_id: amount.units for key, amount in current.available_by_venue}
        for proof in selected:
            own = next(r for r in current.reservations.active_reservations if r.order_id == proof.stream.order.order_id)
            protected[proof.stream.order.intent.instrument_id.venue] += sum(m.units for m in (*own.commitment.cash, *own.commitment.fee_reserve))
        for entry in journal.entries[current.journal.entry_count:after_count]:
            for change in entry.balance_changes:
                if type(change.key) is d.CashBalanceKey and isinstance(change.value, d.Money) and change.value.units < 0:
                    protected[change.key.venue_id] += change.value.units
        if any(v < 0 for v in protected.values()):
            raise ValueError("standard native actual gross debit used another hold or sale receipts")
        prior_count = after_count
    if prior_count != journal.entry_count:
        raise ValueError("standard native journal contains a hidden post-batch append")
    _equal(tuple(sorted(collected_fills, key=d.canonical_bytes)), fills, "final Fills differ from actual full-fill proof set")
    _equal(tuple(sorted(collected_fees, key=d.canonical_bytes)), fees, "actual final fees differ from current native rules")
    days = sorted(facts.get("native_daily_snapshot", ()), key=lambda pair: _read_simulation_instant(pair[0]["occurred_at"]))
    if len(days) != len(inputs.daily_marks) or witness["daily_count"] != len(days):
        raise ValueError("standard native daily state exact-cover mismatch")
    for mark, (_, day) in zip(inputs.daily_marks, days, strict=True):
        _equal(mark, day["marks"], "daily frozen mark source substitution")
        prefix = t.AccountingJournal.from_entries(journal.entries[:_count(day["journal_count"], journal.entry_count)])
        _equal(_native_snapshot_at_v1(inputs, prefix, mark), day["snapshot"], "daily native snapshot mismatch")
    _reject_unmodeled_dividends_v1(journal=journal, schema=inputs.scope.ledger_schema,
        account=inputs.scope.account_id, instruments=inputs.scope.instrument_ids, guards=inputs.dividend_guards,
        start=_day(openings[0].event_time), end_exclusive=_day(case.timeline.window.end_exclusive))
    boundary = _at(case.timeline.window.end_exclusive, 200)
    _equal(_RUN_END_MARK_POLICY, witness["run_end_mark_policy"], "RunEnd carry policy mismatch")
    marks = _native_run_end_marks_v1(inputs, boundary)
    _equal(marks, witness["final_mark_queries"], "RunEnd native mark query substitution")
    projected = t.PortfolioSnapshotProjector().project_cash_ledger(ledger_state=ledger, resolved_marks=marks,
        reporting_currency=d.CurrencyId("CNY"), reporting_scale=d.Scale(2), projection_at=boundary,
        instrument_catalog=inputs.scope.instrument_catalog,
        currency_valuation_graph=t.CurrencyValuationGraph(boundary.instant, d.PricePurpose.VALUATION, ()),
        notional_quantization=inputs.notional_quantization)
    _equal(projected.snapshot, snapshot, "final native snapshot differs from preserved mark/journal head")
    if _read_simulation_instant(witness_artifact["occurred_at"]) != boundary:
        raise ValueError("standard native witness was not sealed at the actual end boundary")

    # Read-only closure of already-proved facts. Never select a Fill, book money,
    # invoke the Engine, or publish: journal heads come only from proved batches.
    head = inputs.initial_journal.entry_count
    actual_book = case.financial_state.settlement_book
    actual_streams: dict[d.DomainId, t.OrderEventStream] = {}
    actual_schedules: list[t.OrderReservationSchedule] = []
    pending: dict[d.InstrumentId, tuple[int, d.Order]] = {}
    position = 0

    def take(role: str, event_id: str, at: d.SimulationInstant) -> Mapping[str, Any]:
        nonlocal position
        if position >= len(ordered_facts):
            raise ValueError("standard native history omitted a required financial fact")
        artifact, value = ordered_facts[position]
        if (artifact["role"] != role or artifact["source_event_id"] != event_id
                or _read_simulation_instant(artifact["occurred_at"]) != at):
            raise ValueError("standard native financial history order/source/full-clock mismatch")
        position += 1
        return value

    def actual_sources(at: d.SimulationInstant) -> _StandardOpenSourcesV1:
        return _StandardOpenSourcesV1(inputs, t.AccountingJournal.from_entries(journal.entries[:head]),
            actual_book, tuple(actual_streams.values()), tuple(actual_schedules),
            case.financial_state.settlement_rules, at)

    actions = [(b.at, "signal", i) for i, b in enumerate(inputs.signal_marks)]
    actions += [(_at(when, 10), "opening", when) for when in expected_times]
    actions += [(b.at, "daily", i) for i, b in enumerate(inputs.daily_marks)]
    batch_by_time = {_read_utc(value["when"]): value for _, value in batches}
    for at, kind, key in sorted(actions, key=lambda row: row[0]):
        actual_book = CnASharePortfolioSettlementDevelopmentV1(
            d.canonical_sha256(t.AccountingJournal.from_entries(journal.entries[:head])),
            (inputs.calendars[0].calendar_hash, inputs.calendars[1].calendar_hash), actual_book).apply_due(at.instant).book
        if kind == "signal":
            assert type(key) is int
            signal = native_signals[key]
            event = case.target_stream.events[key]
            fact = take("native_signal", event.event_id, _at(at.instant, 45))
            before = actual_sources(_at(at.instant, 35))
            _equal(_checkpoint(before), fact["cancel_sources"], "cancellation checkpoint skipped the actual history")
            cancel_plan = CnASharePortfolioOrderPlanV1.create(account_id=inputs.scope.account_id,
                target_id=signal.normalized_target.normalized_target_id,
                target_hash=signal.normalized_target.normalized_target_hash, as_of=at.instant,
                policy=inputs.execution_policy, cash=before.cash, sellability=before.sellability,
                working_orders=tuple(actual_streams.values()), reservation_schedules=tuple(actual_schedules), proposed=())
            _equal(cancel_plan, fact["cancel_plan"], "native cancellation plan substitution")
            for cancel in cancel_plan.cancel_intents:
                stream = actual_streams[cancel.order_id]
                root = f"signal.{admissions[cancel.order_id].signal_index}.{cancel.instrument_id}.signal.{key}."
                for phase, stage, event_kind in ((37, "cancel_requested", d.OrderEventType.ORDER_CANCEL_REQUESTED),
                    (38, "cancelled", d.OrderEventType.ORDER_CANCELLED)):
                    stream = _append_event(case, stream, root + stage, event_kind,
                        _at(at.instant, phase), cancel.cancel_intent_hash)
                actual_streams[cancel.order_id] = stream
            _equal(_checkpoint(actual_sources(_at(at.instant, 45))), fact["coordinator_sources"],
                "coordinator checkpoint omitted native cancellations")
            pending.clear()
            for ordinal, planned in enumerate(native_plans[key].planned_orders, 1):
                intent = replace(planned.intent, time_in_force=inputs.execution_policy.time_in_force_for(planned.intent.side))
                pending[intent.instrument_id] = (key, d.Order(case.domain_id(f"signal.{key}.{intent.instrument_id}.order"),
                    inputs.scope.account_id, intent, _at(at.instant, 40, ordinal)))
        elif kind == "opening":
            assert type(key) is d.UtcInstant
            when = key
            bars = tuple((i, e) for i, e in enumerate(openings) if e.event_time == when)
            by_instrument = {e.instrument_id: (i, e) for i, e in bars}
            batch = batch_by_time[when]
            staged = []
            for instrument, (_, order) in pending.items():
                _, event = by_instrument[instrument]
                if order.created_at.instant >= when:
                    continue
                if BarOpenObservation.from_event(event).kind is not BarOpenKind.REAL:
                    _equal({"order": order, "raw_event_hash": event.event_hash,
                        "action": "expire_at_daily_close" if order.intent.time_in_force is d.TimeInForce.DAY else "keep_intent"},
                        take("pending_no_real_open", event.event_id, _at(when, 44)), "pending non-real opening mismatch")
                else:
                    staged.append(order)
            before = actual_sources(_at(when, 49))
            _equal(_checkpoint(before), batch["prior"], "opening prior checkpoint skipped the actual history")
            head += len(_seq(batch["funding"]))
            origin = actual_sources(_at(when, 55))
            rejected = []
            for order in sorted(staged, key=lambda o: (o.intent.side is d.OrderSide.BUY, o.intent.instrument_id)):
                identity = order.order_id
                if identity in admissions:
                    admission = admissions[identity]
                    _equal(origin, admission.sources, "original admission checkpoint differs from actual history")
                    stream, schedule = original_streams[identity]
                    _equal(order, stream.order, "accepted Order differs from the current pending intention")
                    actual_streams[identity] = stream
                    actual_schedules.append(schedule)
                elif identity in rejections:
                    value = rejections[identity]
                    _equal(_checkpoint(before), value["rejection"]["sources"], "rejection skipped its actual prior head")
                    stream = by_order[identity]
                    _equal(order, stream.order, "rejected Order differs from current pending intention")
                    rejected.append((order, value))
                else:
                    raise ValueError("standard native real opening omitted pending intent admission/rejection")
                del pending[order.intent.instrument_id]
            # Engine appends all admitted Orders first, then the rejected streams.
            for order, value in rejected:
                identity = order.order_id
                actual_streams[identity] = by_order[identity]
                _, event = by_instrument[order.intent.instrument_id]
                _equal(value, take("native_pretrade_rejection", event.event_id, _at(when, 66)),
                    "native rejection financial history mismatch")
            current = actual_sources(_at(when, 67))
            _equal(_checkpoint(current), batch["current"], "opening current checkpoint skipped the actual history")
            for stream in actual_streams.values():
                if stream.state is None or stream.state.status not in _WORKING:
                    continue
                _, event = by_instrument[stream.order.intent.instrument_id]
                if BarOpenObservation.from_event(event).kind is not BarOpenKind.REAL:
                    _equal({"order_id": stream.order.order_id, "raw_event_hash": event.event_hash,
                        "stream_hash": stream.stream_hash, "schedule_hash": next(s.schedule_hash for s in actual_schedules
                            if s.order_id == stream.order.order_id)},
                        take("working_no_real_open", event.event_id, _at(when, 67)), "working non-real opening mismatch")
            _equal(batch, take("native_opening_batch", bars[0][1].event_id, _at(when, 96)), "opening batch history mismatch")
            native_steps = []
            for outcome in verified_outcomes[when]:
                stream = actual_streams[outcome.proof.stream.order.order_id]
                _equal(stream, outcome.proof.stream, "opening proof is not the actual current Order prefix")
                index, _ = by_instrument[stream.order.intent.instrument_id]
                root = f"signal.{admissions[stream.order.order_id].signal_index}.{stream.order.intent.instrument_id}.open.{index}."
                if outcome.fill is not None:
                    stream = _append_event(case, stream, root + "activated", d.OrderEventType.ORDER_ACTIVATED,
                        _at(when, 68, index + 1), outcome.outcome_hash)
                    stream = _append_event(case, stream, root + "filled", d.OrderEventType.ORDER_FILLED,
                        _at(when, 69, index + 1), outcome.outcome_hash, outcome.fill)
                    native_steps.append(_StandardFinancialStepV1(outcome, stream))
                elif outcome.action is NoEligibleBarAction.EXPIRE:
                    stream = _append_event(case, stream, root + "expired", d.OrderEventType.ORDER_EXPIRED,
                        _at(when, 95, index + 1), outcome.outcome_hash)
                actual_streams[stream.order.order_id] = stream
            _equal(tuple(native_steps), batch["steps"], "terminal steps differ from exact native event history")
            head = _count(batch["journal_count_after"], journal.entry_count)
            if native_steps:
                native_book = _build_cn_a_share_portfolio_settlement_facts_v1(
                    fills=tuple(step.opening.fill for step in native_steps if step.opening.fill is not None),
                    journal=t.AccountingJournal.from_entries(journal.entries[:head]),
                    source_hash=d.canonical_sha256(tuple(native_steps)), calendars=inputs.calendars).book
                actual_book = actual_book.append(obligations=native_book.obligations, events=native_book.events)
            _equal(_book_body(actual_book), batch["book_after"], "batch native Book differs from complete settlement history")
        else:
            assert type(key) is int
            mark = inputs.daily_marks[key]
            for instrument, (_, order) in tuple(pending.items()):
                if order.intent.time_in_force is d.TimeInForce.DAY and order.created_at.instant < at.instant:
                    del pending[instrument]
            fact = take("native_daily_snapshot", "daily." + str(at.instant.epoch_nanoseconds), at)
            _equal(head, fact["journal_count"], "daily snapshot rewound the complete actual journal head")
            _equal(_book_body(actual_book), fact["book"], "daily native Book differs from complete settlement history")
            _equal(tuple(o for _, o in pending.values()), fact["pending_intentions"], "daily pending intentions mismatch")
    take("native_attempt_witness", "native.final", boundary)
    if position != len(ordered_facts):
        raise ValueError("standard native history has extra unproved financial artifacts")
    # EngineExecutionResult canonicalizes its full stream collection, not event history.
    _equal(_stable_tuple(tuple(actual_streams.values())), raw["order_streams"], "final Order streams differ from complete native event history")
    _equal(tuple(actual_schedules), witness["schedules"], "final original schedules differ from actual history")
    _equal(_book_body(actual_book), witness["book"], "final Book differs from complete settlement history")
    _equal(tuple(o for _, o in pending.values()), witness["pending_intentions"], "final pending intentions mismatch")
    expected_trace = ExecutionTrace(tuple(ExecutionTraceEntry(i, EngineStage.FINANCIAL_EVENT,
        _read_simulation_instant(artifact["occurred_at"]), artifact["source_event_id"], d.canonical_sha256(artifact))
        for i, (artifact, _) in enumerate(ordered_facts)))
    _equal(expected_trace, raw["trace"], "trace does not exact-cover the native financial history")
    cursor = case.timeline.open_cursor(batch_size=case.timeline_batch_size)
    emitted_ids = []
    while not cursor.window_complete:
        read = case.timeline.read_batch(cursor)
        if read.batch is None or type(read.batch.next_cursor) is not TimelineCursorV2:
            raise ValueError("standard native cold timeline failed to prove completed cursor")
        emitted_ids.extend(e.event.event_id for e in read.batch.events)
        cursor = read.batch.next_cursor
    expected_ids = tuple(e.event_id for e in (*case.target_stream.events, *openings))
    if len(emitted_ids) != len(expected_ids) or set(emitted_ids) != set(expected_ids):
        raise ValueError("standard native completed timeline does not exact-cover frozen events")
    _equal(cursor, witness["cursor"], "completed native timeline cursor substitution")
    reservations = t.ResourceReservationBook(inputs.scope.account_id).project(tuple(actual_streams.values()), tuple(actual_schedules))
    run_end = RunEndCoordinator().coordinate(RunEndEvidence(case.timeline.window, cursor, snapshot,
        tuple(actual_streams.values()), reservations, actual_book.project(), ()), MarkToMarketCloseoutPolicy())
    if run_end.report is None:
        raise ValueError("standard native RunEnd proof rejected: " + str(run_end.termination))
    _equal(run_end.report, raw["run_end_report"], "whole RunEnd report differs from native completed history")


def _verify_standard_native_cached_v1(*, case: _ResolvedProfilePortfolioCaseV1,
    reader: ArtifactEnvelopeReader, publication_ref: d.ArtifactRef,
) -> None:
    nominal = BacktestCanonicalPublicationRef.from_artifact_ref(publication_ref)
    verified = BacktestEvidenceRepository(reader=reader).load_completed(nominal)
    if case.identity_manifest is None or verified.semantic_run_id != case.identity_manifest.semantic_run_id:
        raise ValueError("standard native cache semantic run mismatch")
    canonical = _read_retained(reader, publication_ref)
    entries = _seq(_map(canonical.payload)["artifacts"])
    entry = next(v for v in entries if v["relative_path"] == "result.json")
    completed_ref = d.ArtifactRef(entry["artifact_type"], entry["schema_version"], entry["content_hash"])
    completed = _read_retained(reader, completed_ref)
    evidence = _read_retained(reader, _artifact_ref(_map(completed.payload)["canonical_evidence_manifest_ref"]))
    entry = next(v for v in _seq(_map(evidence.payload)["artifacts"]) if v["role"] == "engine_execution_result")
    engine_ref = d.ArtifactRef(entry["artifact_type"], entry["schema_version"], entry["content_hash"])
    engine = _read_retained(reader, engine_ref)
    if engine.artifact_type != "engine_execution_result" or engine.schema_version != 1:
        raise ValueError("standard native cache engine child has wrong schema")
    _verify_standard_native_result_v1(case=case, reader=reader, result=_map(engine.payload))
