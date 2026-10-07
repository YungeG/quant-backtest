"""Profile-owned native multi-stock DEVELOPMENT Engine; no publication I/O.

One financial fan-in per observed opening. Native sizing, market, fees, cash,
reservations, journal, lots and T+1 remain the sole economic implementations.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from zoneinfo import ZoneInfo

import crypto_quant_domain as d
import crypto_quant_trading as t
from crypto_quant_market_data import InputValidationFailure, MarketEvent
from crypto_quant_trading.profiles.cn_a_share.portfolio_order_plan_v1 import (
    CnASharePortfolioOrderPlanV1, CnASharePortfolioOrderProposalV1,
)

from .artifact_envelope_reader import ArtifactEnvelopeReader
from .cn_a_share_portfolio_daily_nav_diagnostic_v1 import _reject_unmodeled_dividends_v1
from .cn_a_share_portfolio_standard_case_v1 import _bind_standard_portfolio_sources_v1
from .cn_a_share_portfolio_standard_definition_v1 import CnASharePortfolioStandardDevelopmentInputsV1
from .cn_a_share_portfolio_standard_native_state_v1 import (
    _NativeSignalTargetV1, _native_signal_target_v1, _native_rebalance_plan_v1, _native_snapshot_at_v1,
)
from .cn_a_share_portfolio_standard_opening_v1 import (
    _StandardOpenSourcesV1, _StandardCurrentOpenProofV1, _StandardOpeningOutcomeV1,
    _StandardFinancialStepV1, _standard_market_fee_v1, _standard_opening_v1,
    _book_standard_full_fill_batch_v1,
)
from .cn_a_share_portfolio_settlement_development_v1 import (
    CnASharePortfolioSettlementDevelopmentV1, _build_cn_a_share_portfolio_settlement_facts_v1,
    _book_body,
)
from .cn_a_share_portfolio_venue_funding_development_v1 import plan_cn_portfolio_venue_funding_development_v1
from .engine import (
    EngineCancellationRequest, EngineCancellation, EngineExecutionOutcome, EngineExecutionResult,
    EngineFailure, EngineFailureCode, EngineStage, ExecutionTrace, ExecutionTraceEntry,
)
from .execution import BarOpenObservation, BarOpenKind, NoEligibleBarAction
from .financial_dispatch import FinancialDispatchArtifact
from .profile_portfolio_execution import _ResolvedProfilePortfolioCaseV1, _RuntimeExecutionCase
from .run_end import RunEndCoordinator, RunEndEvidence, MarkToMarketCloseoutPolicy
from .timeline import TimelineCursorV2

_COMPONENT = "cn.portfolio.standard.native.engine.v1"
_COMPONENT_HASH = d.canonical_sha256({"component": _COMPONENT, "policy": "native-sell-first-one-batch-settled-only",
    "admission": "native-proposal-prefix-reject-without-sale-prefinance", "run_end_carry_max_nanoseconds": 86_400_000_000_000})
_WORKING = {d.OrderStatus.ACCEPTED, d.OrderStatus.ACTIVE}
_ZONE = ZoneInfo("Asia/Shanghai")
_RUN_END_MARK_POLICY = t.StaleMarkPolicy("cn.portfolio.standard.run-end-last-daily", 1,
    d.PricePurpose.VALUATION, 86_400_000_000_000, True)


def _at(when: d.UtcInstant, phase: int, sequence: int = 0) -> d.SimulationInstant:
    return d.SimulationInstant(when, d.TimelinePhase(phase, "cn_standard_native"), d.SourceSequence(sequence))


def _day(when: d.UtcInstant) -> date:
    return when.to_datetime().astimezone(_ZONE).date()


def _native_run_end_marks_v1(inputs: CnASharePortfolioStandardDevelopmentInputsV1,
    boundary: d.SimulationInstant,
) -> tuple[t.ResolvedMark, ...]:
    """New valuation QUERY only; keep last daily price/observation/availability."""
    last = inputs.daily_marks[-1]
    if last.at >= boundary or boundary.instant.epoch_nanoseconds - last.at.instant.epoch_nanoseconds > _RUN_END_MARK_POLICY.max_age_nanoseconds:
        raise ValueError("native RunEnd is outside the frozen one-day last-daily carry policy")
    marks = []
    for source in last.marks:
        observation = t.MarkObservation(source.instrument_id, source.quote_currency_id,
            source.price_purpose, source.price, source.observed_at, source.available_at,
            source.stream_id, source.source_event_id, source.revision_id)
        outcome = t.MarkResolver().resolve((observation,), instrument_id=source.instrument_id,
            price_purpose=d.PricePurpose.VALUATION, requested_at=boundary.instant,
            stale_policy=_RUN_END_MARK_POLICY)
        if outcome.resolved_mark is None:
            raise ValueError("native RunEnd retained mark rejected: " + str(outcome.failure))
        marks.append(replace(outcome.resolved_mark, available_at_instant=source.available_at_instant,
            resolved_at_instant=boundary))
    return tuple(marks)


def _checkpoint(sources: _StandardOpenSourcesV1) -> dict[str, object]:
    return {"at": sources.at, "source_hash": d.canonical_sha256(sources),
        "journal_count": sources.journal.entry_count,
        "book_event_count": len(sources.settlement_book.events),
        "obligation_ids": tuple(o.obligation.settlement_obligation_id for o in sources.settlement_book.obligations),
        "streams": tuple((s.order.order_id, s.event_count) for s in sources.order_streams),
        "schedules": tuple(s.order_id for s in sources.reservation_schedules)}


@dataclass(frozen=True, slots=True)
class _Admission:
    signal_index: int
    plan: CnASharePortfolioOrderPlanV1
    sources: _StandardOpenSourcesV1
    fee: t.ResourceReservationProposal


def _append_event(case: _ResolvedProfilePortfolioCaseV1, stream: t.OrderEventStream,
    key: str, kind: d.OrderEventType, at: d.SimulationInstant, evidence: str,
    fill: d.Fill | None = None,
) -> t.OrderEventStream:
    cause = stream.state.last_event_id if stream.state is not None else stream.order.intent.parent_id
    event = d.OrderEvent(case.event_id(key), stream.order.order_id, cause, kind, at,
        fill_id=None if fill is None else fill.fill_id, evidence_id=evidence,
        reason_code="native_cash_or_t1_unavailable" if kind is d.OrderEventType.PRE_TRADE_RISK_REJECTED else None)
    return stream.append(t.OrderEventRecord(event, fill))


def _admit(case: _ResolvedProfilePortfolioCaseV1, order: d.Order, opening_index: int,
    admission: _Admission, terms,
) -> tuple[t.OrderEventStream, t.OrderReservationSchedule]:
    market, fee = _standard_market_fee_v1(order, terms)
    if fee != admission.fee:
        raise ValueError("native admission fee changed before acceptance")
    spec = market.evaluation_input.executable_order_spec
    kinds = (d.OrderEventType.ORDER_INTENT_CREATED, d.OrderEventType.ORDER_CAPABILITY_APPROVED,
        d.OrderEventType.ORDER_TRANSLATED, d.OrderEventType.MARKET_RULE_APPROVED,
        d.OrderEventType.FEE_RESERVATION_ESTIMATED, d.OrderEventType.PRE_TRADE_RISK_APPROVED,
        d.OrderEventType.ORDER_SUBMITTED, d.OrderEventType.ORDER_ACCEPTED)
    stages = ("intent", "capability", "translation", "market", "fee", "risk", "submitted", "accepted")
    evidence = (admission.plan.plan_hash, spec.capability_approval.decision_id, spec.spec_id,
        market.decision_id, fee.proposal_hash, admission.plan.plan_hash, terms.bar_event_hash, terms.bar_event_hash)
    phases = (40, 41, 42, 60, 61, 62, 63, 66)
    root = f"signal.{admission.signal_index}.{order.intent.instrument_id}.open.{opening_index}."
    stream = t.OrderEventStream(order)
    for index, (kind, stage, value, phase) in enumerate(zip(kinds, stages, evidence, phases, strict=True)):
        at = order.created_at if index == 0 else _at(
            order.created_at.instant if index < 3 else terms.opening_at, phase, order.created_at.source_sequence.value)
        stream = _append_event(case, stream, root + stage, kind, at, value)
    proposed = next(p for p in admission.plan.proposed if p.intent == order.intent)
    commitment = t.ReservationCommitment(
        cash=(proposed.principal,) if order.intent.side is d.OrderSide.BUY else (),
        sellable_quantities=(order.intent.quantity,) if order.intent.side is d.OrderSide.SELL else (),
        fee_reserve=fee.commitment.fee_reserve, order_capacity_units=1)
    update = t.OrderReservationUpdate(order.order_id, stream.records[-1].event.event_id,
        d.OrderEventType.ORDER_ACCEPTED, order.intent.quantity, commitment, admission.plan.plan_hash)
    return stream, t.OrderReservationSchedule(order.order_id, fee.proposal_hash, (update,))


def _native_admission_plan_v1(signal: _NativeSignalTargetV1, sources: _StandardOpenSourcesV1,
    proposals: tuple[CnASharePortfolioOrderProposalV1, ...],
) -> CnASharePortfolioOrderPlanV1:
    return CnASharePortfolioOrderPlanV1.create(account_id=sources.inputs.scope.account_id,
        target_id=signal.normalized_target.normalized_target_id,
        target_hash=signal.normalized_target.normalized_target_hash, as_of=sources.at.instant,
        policy=sources.inputs.execution_policy, cash=sources.cash, sellability=sources.sellability,
        working_orders=sources.order_streams, reservation_schedules=sources.reservation_schedules,
        proposed=proposals)


def _rejected_admission_stream_v1(case: _ResolvedProfilePortfolioCaseV1, order: d.Order,
    signal_index: int, opening_index: int, terms, rejection_hash: str,
) -> t.OrderEventStream:
    market, fee = _standard_market_fee_v1(order, terms)
    spec = market.evaluation_input.executable_order_spec
    rows = (("intent", d.OrderEventType.ORDER_INTENT_CREATED, 40, rejection_hash),
        ("capability", d.OrderEventType.ORDER_CAPABILITY_APPROVED, 41, spec.capability_approval.decision_id),
        ("translation", d.OrderEventType.ORDER_TRANSLATED, 42, spec.spec_id),
        ("market", d.OrderEventType.MARKET_RULE_APPROVED, 60, market.decision_id),
        ("fee", d.OrderEventType.FEE_RESERVATION_ESTIMATED, 61, fee.proposal_hash),
        ("rejected", d.OrderEventType.PRE_TRADE_RISK_REJECTED, 62, rejection_hash))
    stream = t.OrderEventStream(order)
    root = f"signal.{signal_index}.{order.intent.instrument_id}.open.{opening_index}."
    for index, (stage, kind, phase, proof) in enumerate(rows):
        at = order.created_at if index == 0 else _at(
            order.created_at.instant if index < 3 else terms.opening_at, phase, order.created_at.source_sequence.value)
        stream = _append_event(case, stream, root + stage, kind, at, proof)
    return stream


class _CnASharePortfolioStandardEngineV1:
    def __init__(self, *, artifact_reader: ArtifactEnvelopeReader) -> None:
        self._reader = artifact_reader

    def run(self, case: _RuntimeExecutionCase | InputValidationFailure, *,
        cancellation: EngineCancellationRequest | None = None,
    ) -> EngineExecutionOutcome:
        if isinstance(case, InputValidationFailure):
            return EngineExecutionOutcome(input_validation_failure=case)
        if type(case) is not _ResolvedProfilePortfolioCaseV1:
            raise TypeError("CN native portfolio Engine requires its exact standard case")
        try:
            return self._run(case, cancellation)
        except (TypeError, ValueError) as error:
            return EngineExecutionOutcome(engine_failure=EngineFailure(
                EngineFailureCode.CASE_EVIDENCE_MISMATCH, case.case_hash,
                ExecutionTrace().trace_hash, (str(error),)))

    def _run(self, case: _ResolvedProfilePortfolioCaseV1,
        cancellation: EngineCancellationRequest | None,
    ) -> EngineExecutionOutcome:
        bound = _bind_standard_portfolio_sources_v1(case, self._reader)
        inputs, openings = bound.inputs, bound.openings
        journal, book = inputs.initial_journal, case.financial_state.settlement_book
        rules = case.financial_state.settlement_rules
        streams: dict[d.DomainId, t.OrderEventStream] = {}
        schedules: list[t.OrderReservationSchedule] = []
        admissions: dict[d.DomainId, _Admission] = {}
        pending: dict[d.InstrumentId, tuple[int, d.Order]] = {}
        signals: list[_NativeSignalTargetV1] = []
        coordinator_plans: list[t.OrderPlan] = []
        artifacts: list[FinancialDispatchArtifact] = []
        trace: list[ExecutionTraceEntry] = []
        fills: list[d.Fill] = []
        fees: list[d.FeeAssessment] = []
        history: list[dict[str, object]] = []
        days: list[dict[str, object]] = []

        def sources(at: d.SimulationInstant) -> _StandardOpenSourcesV1:
            return _StandardOpenSourcesV1(inputs, journal, book, tuple(streams.values()),
                tuple(schedules), rules, at)

        def evidence(role: str, event_id: str, at: d.SimulationInstant, payload: object) -> None:
            fact = d.ArtifactEnvelope.create("cn_a_share_portfolio_" + role, 1, payload)
            value = FinancialDispatchArtifact(role, event_id, at, _COMPONENT, 1, _COMPONENT_HASH,
                d.canonical_sha256(case.execution_case_plan.definition), d.canonical_sha256(fact), fact)
            artifacts.append(value)
            trace.append(ExecutionTraceEntry(len(trace), EngineStage.FINANCIAL_EVENT,
                at, event_id, value.artifact_hash))

        def settle(when: d.UtcInstant) -> None:
            nonlocal book
            book = CnASharePortfolioSettlementDevelopmentV1(d.canonical_sha256(journal),
                (inputs.calendars[0].calendar_hash, inputs.calendars[1].calendar_hash), book).apply_due(when).book

        # Consume the real embedded-target timeline once. Never manufacture a
        # completed cursor or use a second source stream for economic behavior.
        cursor = case.timeline.open_cursor(batch_size=case.timeline_batch_size)
        emitted = []
        while not cursor.window_complete:
            outcome = case.timeline.read_batch(cursor)
            if outcome.batch is None:
                raise ValueError("standard native timeline failed: " + str(outcome.failure))
            emitted.extend(outcome.batch.events)
            advanced = outcome.batch.next_cursor
            if type(advanced) is not TimelineCursorV2:
                raise ValueError("native embedded-target cursor changed type")
            cursor = advanced
        event_ids = tuple(e.event.event_id for e in emitted)
        if set(event_ids) != {e.event_id for e in (*case.target_stream.events, *openings)}:
            raise ValueError("native timeline must exact-cover targets and source openings")
        if cancellation is not None and cancellation.cancel_before_event_id not in event_ids:
            raise ValueError("native cancellation event is outside the actual timeline")
        times = sorted({e.event_time for e in openings})
        actions = [(b.at, "signal", i) for i, b in enumerate(inputs.signal_marks)]
        actions += [(_at(when, 10), "opening", when) for when in times]
        actions += [(b.at, "daily", i) for i, b in enumerate(inputs.daily_marks)]
        for at, kind, value in sorted(actions, key=lambda row: row[0]):
            if kind == "signal":
                assert type(value) is int
                signal_index = value
                event = case.target_stream.events[signal_index]
                if cancellation is not None and cancellation.cancel_before_event_id == event.event_id:
                    return EngineExecutionOutcome(cancellation=EngineCancellation(case.case_hash,
                        cancellation, event_ids.index(event.event_id), ExecutionTrace(tuple(trace)).trace_hash))
                settle(at.instant)
                signal = _native_signal_target_v1(inputs=inputs, journal=journal, event=event)
                signals.append(signal)
                before = sources(_at(at.instant, 35))
                cancel_plan = CnASharePortfolioOrderPlanV1.create(account_id=inputs.scope.account_id,
                    target_id=signal.normalized_target.normalized_target_id,
                    target_hash=signal.normalized_target.normalized_target_hash, as_of=at.instant,
                    policy=inputs.execution_policy, cash=before.cash, sellability=before.sellability,
                    working_orders=tuple(streams.values()), reservation_schedules=tuple(schedules), proposed=())
                for cancel in cancel_plan.cancel_intents:
                    stream = streams[cancel.order_id]
                    origin = admissions[cancel.order_id].signal_index
                    root = f"signal.{origin}.{cancel.instrument_id}.signal.{signal_index}."
                    for phase, stage, event_kind in ((37, "cancel_requested", d.OrderEventType.ORDER_CANCEL_REQUESTED),
                        (38, "cancelled", d.OrderEventType.ORDER_CANCELLED)):
                        stream = _append_event(case, stream, root + stage, event_kind,
                            _at(at.instant, phase), cancel.cancel_intent_hash)
                    streams[cancel.order_id] = stream
                pending.clear()  # Superseded intentions never leak into W2.
                plan = _native_rebalance_plan_v1(inputs=inputs, signal=signal, journal=journal,
                    settlement_book=book, order_streams=tuple(streams.values()),
                    reservation_schedules=tuple(schedules), market_rules=rules, at=_at(at.instant, 45))
                coordinator_plans.append(plan)
                for ordinal, planned in enumerate(plan.planned_orders, 1):
                    intent = replace(planned.intent,
                        time_in_force=inputs.execution_policy.time_in_force_for(planned.intent.side))
                    root = f"signal.{signal_index}.{intent.instrument_id}"
                    pending[intent.instrument_id] = (signal_index,
                        d.Order(case.domain_id(root + ".order"), inputs.scope.account_id, intent,
                            _at(at.instant, 40, ordinal)))
                evidence("native_signal", event.event_id, _at(at.instant, 45),
                    {"signal": signal, "coordinator_plan": plan, "cancel_plan": cancel_plan,
                     "cancel_sources": _checkpoint(before),
                     "coordinator_sources": _checkpoint(sources(_at(at.instant, 45)))})
            elif kind == "opening":
                when = value
                assert type(when) is d.UtcInstant
                bars = tuple((index, e) for index, e in enumerate(openings) if e.event_time == when)
                if cancellation is not None and any(e.event_id == cancellation.cancel_before_event_id for _, e in bars):
                    return EngineExecutionOutcome(cancellation=EngineCancellation(case.case_hash, cancellation,
                        event_ids.index(cancellation.cancel_before_event_id), ExecutionTrace(tuple(trace)).trace_hash))
                settle(when)
                by_instrument = {e.instrument_id: (index, e) for index, e in bars}
                new = []
                for instrument, (signal_index, order) in tuple(pending.items()):
                    index, event = by_instrument[instrument]
                    if order.created_at.instant >= when:
                        continue
                    if BarOpenObservation.from_event(event).kind is not BarOpenKind.REAL:
                        evidence("pending_no_real_open", event.event_id, _at(when, 44),
                            {"order": order, "raw_event_hash": event.event_hash,
                             "action": "expire_at_daily_close" if order.intent.time_in_force is d.TimeInForce.DAY else "keep_intent"})
                        continue
                    term = next(t for t in inputs.opening_terms if t.bar_event_id == event.event_id and t.side is order.intent.side)
                    market, fee = _standard_market_fee_v1(order, term)
                    proposal = CnASharePortfolioOrderProposalV1(order.intent,
                        market.calculated_notional if order.intent.side is d.OrderSide.BUY else d.Money(0, d.Scale(2), "CNY"),
                        fee.fee_estimate.total_fee, term.reservation_rules.rule_set_hash)
                    new.append((signal_index, order, index, term, proposal, fee))
                before = sources(_at(when, 49))
                admitted = []
                rejected = []
                for row in sorted(new, key=lambda row: (row[1].intent.side is d.OrderSide.BUY, row[1].intent.instrument_id)):
                    candidate = tuple(r[4] for r in admitted) + (row[4],)
                    try:
                        _native_admission_plan_v1(signals[-1], before, candidate)
                    except ValueError as error:
                        if str(error) not in {"portfolio plan may not reuse cash or prefinance sell receipts",
                            "portfolio plan T+1 forbids unsettled or reserved sell"}:
                            raise
                        signal_index, order, index, term, _, fee = row
                        rejection = {"order": order, "signal_index": signal_index,
                            "sources": _checkpoint(before), "candidate_proposals": candidate,
                            "native_failure": str(error), "fee": fee}
                        stream = _rejected_admission_stream_v1(case, order, signal_index, index,
                            term, d.canonical_sha256(rejection))
                        rejected.append((row, stream, rejection))
                    else:
                        admitted.append(row)
                new = admitted
                required = {key: 0 for key, _ in before.available_by_venue}
                for _, order, _, _, proposal, _ in new:
                    key = next(k for k in required if k.venue_id == order.intent.instrument_id.venue)
                    required[key] += proposal.principal.units + proposal.estimated_fee.units
                for stream in streams.values():
                    if stream.state is None or stream.state.status not in _WORKING:
                        continue
                    _, event = by_instrument[stream.order.intent.instrument_id]
                    if BarOpenObservation.from_event(event).kind is not BarOpenKind.REAL:
                        continue
                    term = next(t for t in inputs.opening_terms if t.bar_event_id == event.event_id and t.side is stream.order.intent.side)
                    _, fresh = _standard_market_fee_v1(stream.order, term)
                    old = admissions[stream.order.order_id].fee
                    key = next(k for k in required if k.venue_id == stream.order.intent.instrument_id.venue)
                    required[key] += max(0, fresh.fee_estimate.total_fee.units - old.fee_estimate.total_fee.units)
                funding = plan_cn_portfolio_venue_funding_development_v1(journal=journal,
                    ledger_schema=inputs.scope.ledger_schema, settlement_book=book,
                    order_streams=tuple(streams.values()), reservation_schedules=tuple(schedules), market_rules=rules,
                    required_by_venue=tuple((key, d.Money(units, d.Scale(2), "CNY")) for key, units in required.items()),
                    at=_at(when, 50), target_hash=d.canonical_sha256(signals[-1].normalized_target))
                journal = journal.append_many(funding)  # Empty or WHOLE pair, never one leg.
                origin = sources(_at(when, 55))
                if new:
                    plan = CnASharePortfolioOrderPlanV1.create(account_id=inputs.scope.account_id,
                        target_id=signals[-1].normalized_target.normalized_target_id,
                        target_hash=signals[-1].normalized_target.normalized_target_hash, as_of=when,
                        policy=inputs.execution_policy, cash=origin.cash, sellability=origin.sellability,
                        working_orders=tuple(streams.values()), reservation_schedules=tuple(schedules),
                        proposed=tuple(row[4] for row in new))
                    for signal_index, order, index, term, _, fee in new:
                        admission = _Admission(signal_index, plan, origin, fee)
                        stream, schedule = _admit(case, order, index, admission, term)
                        admissions[order.order_id] = admission
                        streams[order.order_id] = stream
                        schedules.append(schedule)
                        del pending[order.intent.instrument_id]
                for row, stream, rejection in rejected:
                    _, order, index, _, _, _ = row
                    streams[order.order_id] = stream
                    del pending[order.intent.instrument_id]
                    evidence("native_pretrade_rejection", openings[index].event_id, _at(when, 66),
                        {"rejection": rejection, "stream": stream})
                current = sources(_at(when, 67))
                proofs = []
                for stream in streams.values():
                    if stream.state is None or stream.state.status not in _WORKING:
                        continue
                    index, event = by_instrument[stream.order.intent.instrument_id]
                    observation = BarOpenObservation.from_event(event)
                    if observation.kind is not BarOpenKind.REAL:
                        evidence("working_no_real_open", event.event_id, _at(when, 67),
                            {"order_id": stream.order.order_id, "raw_event_hash": event.event_hash,
                             "stream_hash": stream.stream_hash, "schedule_hash": next(s.schedule_hash for s in schedules if s.order_id == stream.order.order_id)})
                        continue
                    term = next(t for t in inputs.opening_terms if t.bar_event_id == event.event_id and t.side is stream.order.intent.side)
                    original = admissions[stream.order.order_id]
                    proofs.append((index, _StandardCurrentOpenProofV1(original.plan, original.sources,
                        current, stream, original.fee, observation, term)))
                selected: list[_StandardCurrentOpenProofV1] = []
                steps = []
                outcomes = []
                for index, proof in sorted(proofs, key=lambda row: (
                    row[1].stream.order.intent.side is d.OrderSide.BUY, row[1].stream.order.intent.instrument_id)):
                    opening = _standard_opening_v1(proof, budget_prefix=tuple(selected))
                    outcomes.append(opening)
                    if opening.fill is None:
                        continue
                    admission = admissions[proof.stream.order.order_id]
                    root = f"signal.{admission.signal_index}.{proof.stream.order.intent.instrument_id}.open.{index}."
                    stream = proof.stream
                    stream = _append_event(case, stream, root + "activated", d.OrderEventType.ORDER_ACTIVATED,
                        _at(when, 68, index + 1), opening.outcome_hash)
                    stream = _append_event(case, stream, root + "filled", d.OrderEventType.ORDER_FILLED,
                        _at(when, 69, index + 1), opening.outcome_hash, opening.fill)
                    steps.append(_StandardFinancialStepV1(opening, stream))
                    selected.append(proof)
                if steps:
                    journal, _, new_fills, new_fees = _book_standard_full_fill_batch_v1(tuple(steps))
                    native = _build_cn_a_share_portfolio_settlement_facts_v1(fills=new_fills, journal=journal,
                        source_hash=d.canonical_sha256(tuple(steps)), calendars=inputs.calendars).book
                    book = book.append(obligations=native.obligations, events=native.events)
                    fills.extend(new_fills)
                    fees.extend(new_fees)
                    for step in steps:
                        streams[step.terminal_order.order.order_id] = step.terminal_order
                for opening in outcomes:
                    if opening.action is NoEligibleBarAction.EXPIRE:
                        proof = opening.proof
                        index, _ = by_instrument[proof.stream.order.intent.instrument_id]
                        admission = admissions[proof.stream.order.order_id]
                        root = f"signal.{admission.signal_index}.{proof.stream.order.intent.instrument_id}.open.{index}."
                        streams[proof.stream.order.order_id] = _append_event(case, proof.stream, root + "expired",
                            d.OrderEventType.ORDER_EXPIRED, _at(when, 95, index + 1), opening.outcome_hash)
                row = {"when": when, "prior": _checkpoint(before), "current": _checkpoint(current),
                    "funding": funding, "outcomes": tuple(outcomes),
                    "steps": tuple(steps), "journal_count_after": journal.entry_count,
                    "book_after": _book_body(book)}
                history.append(row)
                evidence("native_opening_batch", bars[0][1].event_id, _at(when, 96), row)
            else:
                assert type(value) is int
                batch = inputs.daily_marks[value]
                settle(at.instant)
                _reject_unmodeled_dividends_v1(journal=journal, schema=inputs.scope.ledger_schema,
                    account=inputs.scope.account_id, instruments=inputs.scope.instrument_ids,
                    guards=inputs.dividend_guards, start=_day(openings[0].event_time),
                    end_exclusive=date.fromordinal(_day(at.instant).toordinal() + 1))
                snapshot = _native_snapshot_at_v1(inputs, journal, batch)
                for instrument, (_, order) in tuple(pending.items()):
                    if order.intent.time_in_force is d.TimeInForce.DAY and order.created_at.instant < at.instant:
                        del pending[instrument]
                row = {"marks": batch, "snapshot": snapshot, "journal_count": journal.entry_count,
                    "book": _book_body(book), "pending_intentions": tuple(o for _, o in pending.values())}
                days.append(row)
                evidence("native_daily_snapshot", "daily." + str(at.instant.epoch_nanoseconds), at, row)
        if len(signals) != len(case.target_stream.events) or len(days) != len(inputs.daily_marks):
            raise ValueError("native result does not exact-cover signals/daily states")
        ledger = t.GenericLedger(inputs.scope.ledger_schema).project(journal)
        boundary = _at(case.timeline.window.end_exclusive, 200)
        final_marks = _native_run_end_marks_v1(inputs, boundary)
        projected = t.PortfolioSnapshotProjector().project_cash_ledger(ledger_state=ledger,
            resolved_marks=final_marks, reporting_currency=d.CurrencyId("CNY"),
            reporting_scale=d.Scale(2), projection_at=boundary, instrument_catalog=inputs.scope.instrument_catalog,
            currency_valuation_graph=t.CurrencyValuationGraph(boundary.instant, d.PricePurpose.VALUATION, ()),
            notional_quantization=inputs.notional_quantization)
        if projected.snapshot is None:
            raise ValueError("native final snapshot projection rejected: " + str(projected.failure))
        reservations = t.ResourceReservationBook(inputs.scope.account_id).project(tuple(streams.values()), tuple(schedules))
        run_end = RunEndCoordinator().coordinate(RunEndEvidence(case.timeline.window, cursor,
            projected.snapshot, tuple(streams.values()), reservations, book.project(), ()), MarkToMarketCloseoutPolicy())
        if run_end.report is None:
            raise ValueError("native run-end rejected: " + str(run_end.termination))
        witness = {"type": "cn_a_share_portfolio_standard_native_witness", "schema_version": 1,
            "case_hash": case.case_hash, "definition_hash": d.canonical_sha256(inputs.definition()),
            "target_stream_digest": case.target_stream.target_stream_digest,
            "initial_journal_hash": inputs.initial_journal.journal_hash,
            "schedules": tuple(schedules), "book": _book_body(book),
            "admissions": tuple({"order_id": key, "signal_index": value.signal_index,
                "plan": value.plan, "sources": _checkpoint(value.sources), "fee": value.fee}
                for key, value in admissions.items()),
            "opening_count": len(history), "daily_count": len(days),
            "cursor": cursor, "final_journal_hash": journal.journal_hash,
            "final_ledger_hash": ledger.state_hash, "run_end_report_hash": run_end.report.report_hash,
            "pending_intentions": tuple(o for _, o in pending.values()),
            "final_mark_queries": final_marks, "run_end_mark_policy": _RUN_END_MARK_POLICY,
            "source_qualification_verified": False, "broker_shared_pool_verified": False, "trade_authorized": False}
        evidence("native_attempt_witness", "native.final", boundary, witness)
        return EngineExecutionOutcome(result=EngineExecutionResult(case.case_hash,
            case.target_stream.target_stream_digest, ExecutionTrace(tuple(trace)),
            tuple(s.decision_batch for s in signals), tuple(s.allocation for s in signals),
            tuple(s.approved_target for s in signals), tuple(s.normalized_target for s in signals),
            (), tuple(streams.values()), tuple(fills), (), tuple(fees), tuple(artifacts),
            journal, ledger, projected.snapshot, run_end.report))

    def verify_result(self, case: _ResolvedProfilePortfolioCaseV1, result: EngineExecutionResult) -> None:
        from .cn_a_share_portfolio_standard_result_v1 import _verify_standard_native_result_v1
        _verify_standard_native_result_v1(case=case, reader=self._reader, result=result.to_canonical_dict())

    def verify_cached(self, case: _ResolvedProfilePortfolioCaseV1, publication_ref: d.ArtifactRef) -> None:
        from .cn_a_share_portfolio_standard_result_v1 import _verify_standard_native_cached_v1
        _verify_standard_native_cached_v1(case=case, reader=self._reader, publication_ref=publication_ref)
