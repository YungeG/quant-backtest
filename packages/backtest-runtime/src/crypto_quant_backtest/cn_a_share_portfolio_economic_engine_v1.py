"""Economic profile orchestration over native immutable financial mechanisms."""
from __future__ import annotations

from dataclasses import dataclass, replace
import crypto_quant_domain as d
import crypto_quant_trading as t
from .cn_a_share_portfolio_economic_case_v1 import _clock_v1 as _at
from .cn_a_share_portfolio_economic_opening_v1 import _economic_evaluation_v1
from .cn_a_share_portfolio_economic_native_state_v1 import _EconomicOpenSourcesV1
from crypto_quant_trading.profiles.cn_a_share.portfolio_v1 import CnASharePortfolioOrderPlanV1


@dataclass(frozen=True, slots=True)
class _EconomicAdmissionV1:
    signal_index: int
    plan: CnASharePortfolioOrderPlanV1
    sources: _EconomicOpenSourcesV1
    fee: t.ResourceReservationProposal
    quote: object

    def to_canonical_dict(self):
        return {"order_id": self.fee.order_id, "signal_index": self.signal_index,
            "plan": self.plan, "sources": self.sources, "fee": self.fee, "quote": self.quote}


def _append_event_v1(case, stream, key, kind, at, evidence, fill=None):
    cause = stream.state.last_event_id if stream.state is not None else stream.order.intent.parent_id
    event = d.OrderEvent(case.event_id(key), stream.order.order_id, cause, kind, at,
        fill_id=None if fill is None else fill.fill_id, evidence_id=evidence)
    return stream.append(t.OrderEventRecord(event, fill))


def _admit_economic_order_v1(case, order, opening_index, admission, terms, observation, ordinal):
    quote, market, issues, fee, reason = _economic_evaluation_v1(order, observation, terms)
    if reason is not None or fee != admission.fee or quote != admission.quote:
        raise d.ArtifactIntegrityError("economic admission quote/market/fee changed before acceptance")
    spec = market.approval.evaluation_input.executable_order_spec
    kinds = (d.OrderEventType.ORDER_INTENT_CREATED, d.OrderEventType.ORDER_CAPABILITY_APPROVED,
        d.OrderEventType.ORDER_TRANSLATED, d.OrderEventType.MARKET_RULE_APPROVED,
        d.OrderEventType.FEE_RESERVATION_ESTIMATED, d.OrderEventType.PRE_TRADE_RISK_APPROVED,
        d.OrderEventType.ORDER_SUBMITTED, d.OrderEventType.ORDER_ACCEPTED)
    stages = ("intent", "capability", "translation", "market", "fee", "risk", "submitted", "accepted")
    evidence = (admission.plan.plan_hash, spec.capability_approval.decision_id, spec.spec_id,
        market.approval.decision_id, fee.proposal_hash, admission.plan.plan_hash, terms.bar_event_hash, terms.bar_event_hash)
    root = f"signal.{admission.signal_index}.{order.intent.instrument_id}.open.{opening_index}."
    stream = t.OrderEventStream(order)
    for index, (kind, stage, proof) in enumerate(zip(kinds, stages, evidence, strict=True)):
        at = order.created_at if index == 0 else _at(terms.opening_at, 55 + index, ordinal)
        stream = _append_event_v1(case, stream, root + stage, kind, at, proof)
    proposal = next(p for p in admission.plan.proposed if p.intent == order.intent)
    commitment = t.ReservationCommitment(cash=(proposal.principal,) if order.intent.side is d.OrderSide.BUY else (),
        sellable_quantities=(order.intent.quantity,) if order.intent.side is d.OrderSide.SELL else (),
        fee_reserve=fee.commitment.fee_reserve, order_capacity_units=1)
    update = t.OrderReservationUpdate(order.order_id, stream.records[-1].event.event_id,
        d.OrderEventType.ORDER_ACCEPTED, order.intent.quantity, commitment, admission.plan.plan_hash)
    return stream, t.OrderReservationSchedule(order.order_id, fee.proposal_hash, (update,))


def _terminal_economic_order_v1(case, stream, opening, signal_index, opening_index, ordinal):
    root = f"signal.{signal_index}.{stream.order.intent.instrument_id}.open.{opening_index}."
    when = opening.fill.execution_time
    if stream.state.status is d.OrderStatus.ACCEPTED:
        stream = _append_event_v1(case, stream, root + "activated", d.OrderEventType.ORDER_ACTIVATED,
            _at(when, 68, ordinal), opening.outcome_hash)
    return _append_event_v1(case, stream, root + "filled", d.OrderEventType.ORDER_FILLED,
        _at(when, 69, ordinal), opening.outcome_hash, opening.fill)


from crypto_quant_market_data import InputValidationFailure
import crypto_quant_trading.profiles.cn_a_share.portfolio_economic_v1 as e
from crypto_quant_trading.profiles.cn_a_share.portfolio_v1 import CnASharePortfolioOrderProposalV1
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .cn_a_share_portfolio_economic_case_v1 import (
    _bind_economic_portfolio_sources_v1, _economic_events_v1, _economic_opening_proof_version_v1,
    _verify_bounded_signal_cancellation_v1,
)
from .cn_a_share_portfolio_economic_native_state_v1 import (
    _economic_signal_target_v1, _EconomicNativeFailureV1, _EconomicFailureContextV1, _advance_economic_settlement_v1,
)
from .cn_a_share_portfolio_economic_opening_v1 import (
    _economic_opening_v1, _EconomicOpeningOutcomeV1, _EconomicFinancialStepV1,
    _book_economic_full_fill_batch_v1, _economic_venue_funding_v1, _cent,
)
from .cn_a_share_portfolio_standard_native_state_v1 import _native_rebalance_plan_v1
from .cn_a_share_portfolio_settlement_development_v1 import (
    _NativeSettlementResolutionMemo, _build_cn_a_share_portfolio_settlement_facts_v1, _book_body,
)
from .engine import (EngineExecutionOutcome, EngineExecutionResult, EngineFailure, EngineFailureCode,
    EngineStage, ExecutionTrace, ExecutionTraceEntry, EngineCancellation, EngineCancellationRequest)
from .execution import BarOpenObservation, BarOpenKind, NoEligibleBarAction
from .financial_dispatch import FinancialDispatchArtifact
from .profile_portfolio_execution import _ResolvedProfilePortfolioCaseV2
from .run_end import RunEndCoordinator, RunEndEvidence, MarkToMarketCloseoutPolicy
from .timeline import TimelineCursorV2

_PREFIX = "cn.portfolio.shared-cny.economic.development.v1"
_WORKING = {d.OrderStatus.ACCEPTED, d.OrderStatus.ACTIVE}


def _economic_native_finance_identity_v1(inputs):
    from .cn_a_share_portfolio_economic_definition_v1 import CnASharePortfolioEconomicDevelopmentInputsV1
    from .cn_a_share_portfolio_economic_definition_v2 import CnASharePortfolioEconomicDevelopmentInputsV2
    from .profile_portfolio_execution import _economic_profile_prefix_v1
    if type(inputs) not in (CnASharePortfolioEconomicDevelopmentInputsV1, CnASharePortfolioEconomicDevelopmentInputsV2):
        raise TypeError("economic component requires exact V1 or V2 inputs")
    v2 = type(inputs) is CnASharePortfolioEconomicDevelopmentInputsV2
    prefix = _economic_profile_prefix_v1(inputs.definition())
    return prefix, d.canonical_sha256({"type": "cn_a_share_portfolio_economic_native_component", "schema_version": 2 if v2 else 1,
        "definition_hash": inputs._definition_source_hash,
        "policy_key": "economic_single_prestart_activation_v2" if v2 else "economic_full_fill_known_tax_v1"})


def _used_identity_keys_v1(case, journal, streams, pending, intention_ids=()):
    actual = {entry.journal_entry_id.value for entry in journal.entries}
    actual.update(identity.value for identity in intention_ids)
    actual.update(stream.order.order_id.value for stream in streams.values())
    actual.update(order.order_id.value for _, order in pending.values())
    actual.update(record.event.event_id for stream in streams.values() for record in stream.records)
    return tuple(sorted(binding.binding_key for binding in case.identity_manifest.bindings if binding.value in actual))


class _CnASharePortfolioEconomicEngineV1:
    def __init__(self, *, artifact_reader: ArtifactEnvelopeReader):
        self._reader = artifact_reader

    def run(self, case, *, cancellation=None):
        if type(case) is InputValidationFailure:
            return EngineExecutionOutcome(input_validation_failure=case)
        if type(case) is not _ResolvedProfilePortfolioCaseV2:
            raise TypeError("economic Engine requires exact sealed CaseV2")
        if cancellation is not None and type(cancellation) is not EngineCancellationRequest:
            raise TypeError("economic cancellation requires exact native request")
        return self._run(case, cancellation)

    def _run(self, case, cancellation):
        bound = _bind_economic_portfolio_sources_v1(case, self._reader)
        inputs, openings, mapping = bound.inputs, bound.openings, bound.journal_entry_ids
        initial = case.financial_state
        journal, book, state = initial.journal, initial.settlement_book, case.execution_case_plan.initial_dividend_state
        rules = initial.settlement_rules
        streams, schedules, admissions, pending = {}, {}, {}, {}
        intention_ids = set()
        signals, artifacts, trace, fills, fees, slips = [], [], [], [], [], []
        opening_count = daily_count = dividend_count = 0
        failed_id, failed_at = "economic.initial", inputs.initial_marks.at
        from .cn_a_share_portfolio_economic_definition_v2 import CnASharePortfolioEconomicDevelopmentInputsV2
        from .cn_a_share_portfolio_economic_activation_v2 import (
            _economic_activation_at_v2, _retained_economic_decision_v2,
            _economic_activation_signal_v2, _economic_activation_value_v2, _economic_native_failure_inputs_v2,
        )
        v2 = type(inputs) is CnASharePortfolioEconomicDevelopmentInputsV2
        profile_prefix, component_hash = _economic_native_finance_identity_v1(inputs)
        opening_proof_version = _economic_opening_proof_version_v1(
            definition=case.execution_case_plan.definition, spec=case.semantic_spec)
        settlement_memo = (_NativeSettlementResolutionMemo(inputs.calendars)
            if inputs.definition().schema_version == 4 else None)
        def make(at, j, b, ss, sch, st):
            b = _advance_economic_settlement_v1(case=case, inputs=inputs, journal=j, book=b, consumer=at)
            return _EconomicOpenSourcesV1(inputs, j, b, tuple(sorted(ss.values(), key=lambda row: row.order.order_id.value)),
                tuple(sorted(sch.values(), key=lambda row: row.order_id.value)), rules, st, mapping, at, settlement_memo=settlement_memo)
        last = make(inputs.initial_marks.at, journal, book, streams, schedules, state)
        def commit(source):
            nonlocal journal, book, streams, schedules, state, last
            journal, book, state, last = source.journal, source.settlement_book, source.dividend_state, source
            streams = {s.order.order_id: s for s in source.order_streams}
            schedules = {s.order_id: s for s in source.reservation_schedules}
        def evidence(role, event_id, at, payload):
            version = (opening_proof_version if role == "economic_opening_batch" else
                2 if role == "economic_attempt_witness" or (v2 and role in {"economic_signal", "economic_native_failure"}) else 1)
            envelope = d.ArtifactEnvelope.create("cn_a_share_portfolio_" + role, version, payload)
            artifact = FinancialDispatchArtifact(role, event_id, at, profile_prefix + ".native-finance", 1,
                component_hash, inputs._definition_source_hash, d.canonical_sha256(envelope), envelope)
            artifacts.append(artifact)
            trace.append(ExecutionTraceEntry(len(trace), EngineStage.FINANCIAL_EVENT, at, event_id, artifact.artifact_hash))
        def failure(code, native, ca_inputs=None, ca_failure=None, native_rejection=None):
            if ca_failure is None:
                if native_rejection is None or native_rejection.operation is None or native_rejection.native_inputs is None:
                    raise d.ArtifactIntegrityError("native failure lacks explicit original typed diagnostic")
                evidence("economic_native_failure",failed_id,failed_at,{
                    "type":"cn_a_share_portfolio_economic_native_failure","schema_version":2 if v2 else 1,
                    "operation":native_rejection.operation,"engine_failure_code":code.value,
                    "original_claim":native_rejection.original_claim,
                    "native_inputs":(_economic_native_failure_inputs_v2(native_rejection.operation, native_rejection.native_inputs)
                        if v2 else native_rejection.native_inputs),
                    "native_outcome":native})
            cause_hash = d.canonical_sha256(native)
            trace.append(ExecutionTraceEntry(len(trace), EngineStage.FINANCIAL_EVENT, failed_at, failed_id, cause_hash))
            full_trace = ExecutionTrace(tuple(trace))
            subjects = [failed_id, code.value]
            cause = native.failure if hasattr(native, "failure") and native.failure is not None else native
            if hasattr(cause, "code"):
                subjects.append(cause.code.value)
            base = EngineFailure(code, case.case_hash, full_trace.trace_hash, tuple(subjects), (cause_hash,))
            context = _EconomicFailureContextV1(case.case_hash, inputs._definition_source_hash,
                case.target_stream.target_stream_digest, failed_id, failed_at, base, last, last.journal,
                last.order_streams, last.reservation_schedules, tuple(artifacts), full_trace,
                tuple(order for _, order in sorted(pending.values(), key=lambda row: row[1].order_id.value)),
                tuple(value for _, value in sorted(admissions.items(), key=lambda row: row[0].value)), mapping,
                _used_identity_keys_v1(case, journal, streams, pending, intention_ids), ca_inputs, ca_failure,
                case.semantic_spec, case.identity_manifest, case.execution_case_plan.source_refs, case.timeline.stream_keys)
            envelope = d.ArtifactEnvelope.create("cn_a_share_portfolio_economic_failure_context", 1, context)
            hashes = set(base.evidence_hashes) | {d.canonical_sha256(envelope)}
            if ca_failure is not None:
                hashes.add(d.canonical_sha256(ca_failure))
            return EngineExecutionOutcome(engine_failure=replace(base, evidence_hashes=tuple(sorted(hashes)), economic_failure_context=envelope))
        try:
            cursor = case.timeline.open_cursor(batch_size=64)
            emitted = []
            while not cursor.window_complete:
                outcome = case.timeline.read_batch(cursor)
                if outcome.batch is None:
                    raise _EconomicNativeFailureV1(EngineFailureCode.TIMELINE_FAILURE, outcome.failure,operation="timeline_read",native_inputs={"cursor":cursor,"batch_size":64},original_claim={"case_hash":case.case_hash})
                emitted.extend(outcome.batch.events)
                cursor = outcome.batch.next_cursor
                if type(cursor) is not TimelineCursorV2:
                    raise d.ArtifactIntegrityError("economic embedded timeline cursor changed type")
            event_ids = tuple(row.event.event_id for row in emitted)
            expected = tuple(event.event_id for event in (*case.target_stream.events, *openings))
            if len(event_ids) != len(expected) or set(event_ids) != set(expected):
                raise d.ArtifactIntegrityError("economic timeline did not exact-cover native source events")
            if cancellation is not None and cancellation.cancel_before_event_id not in event_ids:
                raise ValueError("economic cancellation is not a real market/target event")
            if v2:
                actions = [(inputs.retained_signal_marks[0].at, "source", 0),
                    (_economic_activation_at_v2(inputs), "signal", 0)]
            else:
                actions = [(b.at, "signal", i) for i, b in enumerate(inputs.signal_marks)]
            actions += [(_at(when, 49), "opening", when) for when in sorted({event.event_time for event in openings})]
            actions += [(at, "dividend", (kind, action, event_id)) for at, kind, action, event_id in _economic_events_v1(inputs)
                        if at.instant < case.timeline.window.end_exclusive]
            actions += [(b.at, "daily", i) for i, b in enumerate(inputs.daily_marks)]
            for at, kind, value in sorted(actions, key=lambda row: row[0]):
                failed_at = at
                if kind == "source":
                    event = case.target_stream.events[0]
                    if cancellation is not None and cancellation.cancel_before_event_id == event.event_id:
                        return EngineExecutionOutcome(cancellation=EngineCancellation(case.case_hash, cancellation,
                            event_ids.index(event.event_id), ExecutionTrace(tuple(trace)).trace_hash))
                    _retained_economic_decision_v2(inputs)
                    continue
                if kind == "signal":
                    index = value
                    event = case.target_stream.events[index]
                    failed_id = event.event_id
                    if cancellation is not None and cancellation.cancel_before_event_id == event.event_id:
                        return EngineExecutionOutcome(cancellation=EngineCancellation(case.case_hash, cancellation,
                            event_ids.index(event.event_id), ExecutionTrace(tuple(trace)).trace_hash))
                    before = make(at, journal, book, streams, schedules, state)
                    commit(before)
                    signal, projection = (_economic_activation_signal_v2(sources=before, event=event) if v2
                        else _economic_signal_target_v1(sources=before, event=event))
                    cancel_plan = CnASharePortfolioOrderPlanV1.create(account_id=inputs.scope.account_id,
                        target_id=signal.normalized_target.normalized_target_id, target_hash=signal.normalized_target.normalized_target_hash,
                        as_of=at.instant, policy=inputs.execution_policy, cash=before.cash, sellability=before.sellability,
                        working_orders=before.order_streams, reservation_schedules=before.reservation_schedules, proposed=())
                    _verify_bounded_signal_cancellation_v1(case, cancel_plan, admissions, index)
                    candidate_streams = dict(streams)
                    for cancel in cancel_plan.cancel_intents:
                        stream = candidate_streams[cancel.order_id]
                        origin = admissions[cancel.order_id].signal_index
                        root = f"signal.{origin}.{cancel.instrument_id}.signal.{index}."
                        for rank, stage, event_kind in ((37, "cancel_requested", d.OrderEventType.ORDER_CANCEL_REQUESTED),
                                (38, "cancelled", d.OrderEventType.ORDER_CANCELLED)):
                            stream = _append_event_v1(case, stream, root + stage, event_kind, _at(at.instant, rank), cancel.cancel_intent_hash)
                        candidate_streams[cancel.order_id] = stream
                    failed_at = _at(at.instant, 45)
                    coordinated = make(failed_at, journal, book, candidate_streams, schedules, state)
                    plan = _native_rebalance_plan_v1(inputs=inputs, signal=signal, journal=journal,
                        settlement_book=coordinated.settlement_book, order_streams=coordinated.order_streams,
                        reservation_schedules=coordinated.reservation_schedules, market_rules=rules, at=failed_at)
                    candidate_pending = {}
                    ordered = sorted(plan.planned_orders, key=lambda row: (row.intent.side is d.OrderSide.BUY,
                        str(row.intent.instrument_id), case.domain_id(f"signal.{index}.{row.intent.instrument_id}.order").value))
                    for ordinal, planned in enumerate(ordered, 1):
                        intent = replace(planned.intent, time_in_force=inputs.execution_policy.time_in_force_for(planned.intent.side))
                        order = d.Order(case.domain_id(f"signal.{index}.{intent.instrument_id}.order"), inputs.scope.account_id,
                            intent, _at(at.instant, 40, ordinal))
                        candidate_pending[intent.instrument_id] = (index, order)
                    commit(coordinated)
                    pending = candidate_pending
                    intention_ids.update(order.order_id for _, order in pending.values())
                    signals.append(signal)
                    fact = {"signal": signal, "projection": projection, "cancel_plan": cancel_plan,
                        "cancel_sources": before, "coordinator_plan": plan, "coordinator_sources": coordinated}
                    if v2:
                        fact["activation"] = _economic_activation_value_v2(inputs, event)
                    evidence("economic_signal", event.event_id, failed_at, fact)
                elif kind == "dividend":
                    event_kind, action, failed_id = value
                    pre_at = d.SimulationInstant(at.instant, at.phase, d.SourceSequence(at.source_sequence.value - 1))
                    prefix = make(pre_at, journal, book, streams, schedules, state)
                    commit(prefix)
                    history = e.CnAShareCashDividendHistoryInputsV1(journal, inputs.scope.ledger_schema, book,
                        prefix.order_streams, prefix.reservation_schedules, rules, inputs.scope.instrument_catalog,
                        state, inputs.dividend_actions, mapping, at)
                    request = e.CnAShareCashDividendTransitionInputsV1(history, action.action_id, action.instrument_id, event_kind)
                    outcome = e.transition_cn_a_share_cash_dividend_v1(request)
                    if outcome.failure is not None:
                        if outcome.failure.code is e.CnAShareCashDividendTransitionFailureCodeV1.TAX_CASH_SHORTFALL:
                            return failure(EngineFailureCode.FINANCIAL_DISPATCH_FAILURE, outcome.failure, request, outcome.failure)
                        raise d.ArtifactIntegrityError("economic C-A transition rejected: " + outcome.failure.code.value)
                    transition = outcome.transition
                    proposed_journal = journal.append_many(transition.journal_entries)
                    if proposed_journal.journal_hash != transition.output_journal_hash:
                        raise d.ArtifactIntegrityError("economic C-A proposed journal hash mismatch")
                    post = make(at, proposed_journal, book, streams, schedules, transition.state_after)
                    commit(post)
                    dividend_count += 1
                    evidence("economic_dividend_transition", failed_id, at, {"transition": transition, "post_checkpoint": post})
                elif kind == "opening":
                    when = value
                    bars = bound.opening_batches[when]
                    failed_id = bars[0][1].event_id
                    if cancellation is not None and any(event.event_id == cancellation.cancel_before_event_id for _, event in bars):
                        return EngineExecutionOutcome(cancellation=EngineCancellation(case.case_hash, cancellation,
                            event_ids.index(cancellation.cancel_before_event_id), ExecutionTrace(tuple(trace)).trace_hash))
                    prior = make(at, journal, book, streams, schedules, state)
                    commit(prior)
                    by_instrument = {event.instrument_id: (i, event) for i, event in bars}
                    candidates, no_real = [], []
                    for signal_index, order in pending.values():
                        i, event = by_instrument[order.intent.instrument_id]
                        if order.created_at.instant >= when:
                            continue
                        observation = BarOpenObservation.from_event(event)
                        if observation.kind is not BarOpenKind.REAL:
                            no_real.append(("economic_pending_no_real_open", order, None, None, event))
                            continue
                        terms = bound.terms_by_side[event.event_id, order.intent.side]
                        candidates.append((order, observation, terms))
                    for stream in streams.values():
                        if stream.state is None or stream.state.status not in _WORKING:
                            continue
                        i, event = by_instrument[stream.order.intent.instrument_id]
                        observation = BarOpenObservation.from_event(event)
                        if observation.kind is not BarOpenKind.REAL:
                            no_real.append(("economic_working_no_real_open", stream.order, stream.stream_hash,
                                schedules[stream.order.order_id].schedule_hash, event))
                            continue
                        terms = bound.terms_by_side[event.event_id, stream.order.intent.side]
                        candidates.append((stream.order, observation, terms))
                    candidates.sort(key=lambda row: (row[0].intent.side is d.OrderSide.BUY, str(row[0].intent.instrument_id), row[0].order_id.value))
                    funding = _economic_venue_funding_v1(sources=prior, candidates=tuple(candidates))
                    proposed_journal = journal.append_many(funding)
                    funded = make(_at(when, 55), proposed_journal, book, streams, schedules, state)
                    accepted, blocked, proposals = [], [], []
                    for order, observation, terms in candidates:
                        if order.order_id in streams:
                            continue
                        quote, market, issues, fee, reason = _economic_evaluation_v1(order, observation, terms)
                        if reason is None:
                            proposal = CnASharePortfolioOrderProposalV1(order.intent,
                                market.approval.calculated_notional if order.intent.side is d.OrderSide.BUY else _cent(0),
                                fee.fee_estimate.total_fee, terms.reservation_rules.rule_set_hash)
                            chosen = tuple(proposals) + (proposal,)
                            try:
                                plan = CnASharePortfolioOrderPlanV1.create(account_id=inputs.scope.account_id,
                                    target_id=signals[-1].normalized_target.normalized_target_id,
                                    target_hash=signals[-1].normalized_target.normalized_target_hash, as_of=when,
                                    policy=inputs.execution_policy, cash=funded.cash, sellability=funded.sellability,
                                    working_orders=funded.order_streams, reservation_schedules=funded.reservation_schedules, proposed=chosen)
                            except ValueError as error:
                                if str(error) not in {"portfolio plan may not reuse cash or prefinance sell receipts", "portfolio plan T+1 forbids unsettled or reserved sell"}:
                                    raise
                                reason = "native_cash_or_t1_unavailable"
                            else:
                                required = {row.key.venue_id: 0 for row in funded.economic_projection.cash_rows}
                                buy = 0
                                for item in chosen:
                                    demand = item.principal.units + item.estimated_fee.units
                                    required[item.intent.instrument_id.venue] += demand
                                    if item.intent.side is d.OrderSide.BUY:
                                        buy += demand
                                if order.intent.side is d.OrderSide.BUY and funded.economic_projection.tax_shortfall.units:
                                    reason = "tax_shortfall_buy_blocked"
                                elif any(required[row.key.venue_id] > row.spendable.units for row in funded.economic_projection.cash_rows):
                                    reason = "venue_spendable_unavailable"
                                elif buy > funded.economic_projection.buy_budget.units and any(p.intent.side is d.OrderSide.BUY for p in chosen):
                                    reason = "account_buy_budget_unavailable"
                                else:
                                    proposals.append(proposal)
                                    accepted.append((order, observation, terms, quote, fee))
                        if reason is not None:
                            blocked.append((order, observation, terms, quote, market, issues, fee, reason))
                    candidate_streams, candidate_schedules, candidate_admissions = dict(streams), dict(schedules), dict(admissions)
                    if accepted:
                        plan = CnASharePortfolioOrderPlanV1.create(account_id=inputs.scope.account_id,
                            target_id=signals[-1].normalized_target.normalized_target_id,
                            target_hash=signals[-1].normalized_target.normalized_target_hash, as_of=when,
                            policy=inputs.execution_policy, cash=funded.cash, sellability=funded.sellability,
                            working_orders=funded.order_streams, reservation_schedules=funded.reservation_schedules, proposed=tuple(proposals))
                        for ordinal, (order, observation, terms, quote, fee) in enumerate(accepted, 1):
                            signal_index = pending[order.intent.instrument_id][0]
                            i, _ = by_instrument[order.intent.instrument_id]
                            admission = _EconomicAdmissionV1(signal_index, plan, funded, fee, quote)
                            stream, schedule = _admit_economic_order_v1(case, order, i, admission, terms, observation, ordinal)
                            candidate_admissions[order.order_id], candidate_streams[order.order_id], candidate_schedules[order.order_id] = admission, stream, schedule
                    failed_at = _at(when, 67)
                    current = make(failed_at, proposed_journal, funded.settlement_book, candidate_streams, candidate_schedules, funded.dividend_state)
                    commit(current)
                    admissions = candidate_admissions
                    for order, *_ in accepted:
                        del pending[order.intent.instrument_id]
                    outcomes, selected, steps = [], [], []
                    for order, observation, terms, quote, market, issues, fee, reason in blocked:
                        action = NoEligibleBarAction.EXPIRE if order.intent.time_in_force is d.TimeInForce.DAY else NoEligibleBarAction.KEEP_ACTIVE
                        outcomes.append(_EconomicOpeningOutcomeV1(order.order_id, observation.observation_hash,
                            d.canonical_sha256(current), None, d.canonical_sha256(terms), quote, market, issues, fee,
                            action, reason, None, _cent(0), _cent(0), ()))
                    working = sorted((stream for stream in streams.values() if stream.state is not None and stream.state.status in _WORKING),
                        key=lambda stream: (stream.order.intent.side is d.OrderSide.BUY, str(stream.order.intent.instrument_id), stream.order.order_id.value))
                    for ordinal, stream in enumerate(working, 1):
                        i, event = by_instrument[stream.order.intent.instrument_id]
                        observation = BarOpenObservation.from_event(event)
                        if observation.kind is not BarOpenKind.REAL:
                            continue
                        terms = bound.terms_by_side[event.event_id, stream.order.intent.side]
                        opening = _economic_opening_v1(sources=current, stream=stream, observation=observation,
                            terms=terms, admission=admissions[stream.order.order_id], budget_prefix=tuple(selected))
                        outcomes.append(opening)
                        if opening.fill is not None:
                            terminal = _terminal_economic_order_v1(case, stream, opening, admissions[stream.order.order_id].signal_index, i, ordinal)
                            steps.append(_EconomicFinancialStepV1(opening, terminal, terms))
                            selected.append(opening)
                    failed_at = _at(when, 97)
                    proposed_journal, proposed_book, proposed_streams = journal, book, dict(streams)
                    new_fills = new_fees = ()
                    if steps:
                        proposed_journal, _, new_fills, new_fees = _book_economic_full_fill_batch_v1(sources=current, steps=tuple(steps))
                        native = _build_cn_a_share_portfolio_settlement_facts_v1(fills=new_fills, journal=proposed_journal,
                            source_hash=d.canonical_sha256(tuple(steps)), calendars=inputs.calendars).book
                        proposed_book = book.append(obligations=native.obligations, events=native.events)
                        for step in steps:
                            proposed_streams[step.opening.order_id] = step.terminal_order
                    for opening in outcomes:
                        if opening.action is NoEligibleBarAction.EXPIRE and opening.order_id in proposed_streams:
                            stream = proposed_streams[opening.order_id]
                            i, _ = by_instrument[stream.order.intent.instrument_id]
                            admission = admissions[opening.order_id]
                            root = f"signal.{admission.signal_index}.{stream.order.intent.instrument_id}.open.{i}.expired"
                            proposed_streams[opening.order_id] = _append_event_v1(case, stream, root, d.OrderEventType.ORDER_EXPIRED,
                                _at(when, 95, i + 1), opening.outcome_hash)
                    post = make(failed_at, proposed_journal, proposed_book, proposed_streams, schedules, state)
                    commit(post)
                    fills.extend(new_fills)
                    fees.extend(new_fees)
                    slips.extend(opening.slippage_outcome.result for opening in selected)
                    opening_count += 1
                    opening_sources = {"prior": prior, "funded": funded, "current": current}
                    opening_proof = ({key + "_hash": d.canonical_sha256(source) for key, source in opening_sources.items()}
                        if opening_proof_version == 2 else opening_sources)
                    evidence("economic_opening_batch", failed_id, _at(when, 98), {"when": when, **opening_proof,
                        "funding": funding, "outcomes": tuple(outcomes), "steps": tuple(steps),
                        "journal_count_after": journal.entry_count, "book_after": _book_body(book),
                        "dividend_state_after": state, "post_projection": post.economic_projection})
                    for role, order, stream_hash, schedule_hash, event in no_real:
                        evidence(role, event.event_id, _at(when, 98), {"order": order, "stream_hash": stream_hash,
                            "schedule_hash": schedule_hash, "raw_event_hash": event.event_hash,
                            "action": "expire_at_daily_close" if order.intent.time_in_force is d.TimeInForce.DAY else "keep_original",
                            "prefix": current})
                else:
                    failed_id = "economic.daily." + str(at.instant.epoch_nanoseconds)
                    checkpoint = make(at, journal, book, streams, schedules, state)
                    commit(checkpoint)
                    pending = {key: row for key, row in pending.items() if not (row[1].intent.time_in_force is d.TimeInForce.DAY and row[1].created_at.instant < at.instant)}
                    daily_count += 1
                    evidence("economic_daily_projection", failed_id, at, {"marks": inputs.daily_marks[value],
                        "checkpoint": checkpoint, "pending_intentions": tuple(order for _, order in sorted(pending.values(), key=lambda row: row[1].order_id.value))})
            failed_id, failed_at = "economic.final", _at(case.timeline.window.end_exclusive, 200)
            final = make(failed_at, journal, book, streams, schedules, state)
            commit(final)
            ledger = t.GenericLedger(inputs.scope.ledger_schema).project(journal)
            run_end = RunEndCoordinator().coordinate(RunEndEvidence(case.timeline.window, cursor, final.economic_projection.snapshot,
                final.order_streams, final.reservations, book.project(), ()), MarkToMarketCloseoutPolicy())
            if run_end.report is None:
                raise _EconomicNativeFailureV1(EngineFailureCode.RUN_END_TERMINATED, run_end.termination,operation="run_end",native_inputs={"evidence":RunEndEvidence(case.timeline.window,cursor,final.economic_projection.snapshot,final.order_streams,final.reservations,book.project(),()),"policy":MarkToMarketCloseoutPolicy().component_ref},original_claim={"source":final})
            head = d.canonical_sha256(tuple(a.artifact_hash for a in sorted(artifacts, key=lambda row: (row.occurred_at, row.source_event_id, row.role))))
            schedule_hash = d.canonical_sha256({"action_set": inputs.dividend_actions,
                "events": tuple((event_id, kind, at) for at, kind, _, event_id in _economic_events_v1(inputs))})
            witness = {"type": "cn_a_share_portfolio_economic_native_witness", "schema_version": 1,
                "case_hash": case.case_hash, "definition_hash": inputs._definition_source_hash,
                "target_stream_digest": case.target_stream.target_stream_digest, "initial_journal_hash": inputs.initial_journal.journal_hash,
                "initial_economic_projection_hash": case.execution_case_plan.initial_economic_projection.projection_hash,
                "schedules": final.reservation_schedules, "book": _book_body(book),
                "admissions": tuple(value for _, value in sorted(admissions.items(), key=lambda row: row[0].value)),
                "opening_count": opening_count, "daily_count": daily_count, "dividend_event_count": dividend_count,
                "financial_schedule_hash": schedule_hash, "journal_entry_ids": mapping,
                "used_identity_keys": _used_identity_keys_v1(case, journal, streams, pending, intention_ids), "cursor": cursor,
                "final_journal_hash": journal.journal_hash, "final_ledger_hash": ledger.state_hash,
                "final_dividend_state": state, "final_economic_projection": final.economic_projection,
                "run_end_report_hash": run_end.report.report_hash,
                "pending_intentions": tuple(order for _, order in sorted(pending.values(), key=lambda row: row[1].order_id.value)),
                "checkpoint_head": head, "source_qualification_verified": False, "broker_shared_pool_verified": False, "trade_authorized": False}
            witness_v2 = {"type": "cn_a_share_portfolio_economic_native_witness", "schema_version": 2,
                "economic_witness": witness, "economic_witness_hash": d.canonical_sha256(witness),
                "source_binding": {"type": "cn_a_share_portfolio_economic_completed_sources", "schema_version": 1,
                    "source_refs": case.execution_case_plan.source_refs, "semantic_spec": case.semantic_spec,
                    "identity_manifest": case.identity_manifest, "timeline_stream_keys": case.timeline.stream_keys}}
            evidence("economic_attempt_witness", failed_id, failed_at, witness_v2)
            return EngineExecutionOutcome(result=EngineExecutionResult(case.case_hash, case.target_stream.target_stream_digest,
                ExecutionTrace(tuple(trace)), tuple(s.decision_batch for s in signals), tuple(s.allocation for s in signals),
                tuple(s.approved_target for s in signals), tuple(s.normalized_target for s in signals), (),
                tuple(sorted(streams.values(), key=lambda row: row.order.order_id.value)), tuple(fills), tuple(slips), tuple(fees),
                tuple(artifacts), journal, ledger, final.economic_projection.snapshot, run_end.report))
        except _EconomicNativeFailureV1 as rejected:
            return failure(rejected.code, rejected.evidence,native_rejection=rejected)

    def verify_result(self, case, result):
        from .cn_a_share_portfolio_economic_result_v1 import _verify_economic_native_result_v1
        _verify_economic_native_result_v1(case=case, reader=self._reader, result=result)

    def verify_cached(self, case, publication_ref):
        from .cn_a_share_portfolio_economic_result_v1 import _verify_economic_native_cached_v1
        _verify_economic_native_cached_v1(case=case, reader=self._reader, publication_ref=publication_ref)

    def verify_failure(self, case, failure):
        from .cn_a_share_portfolio_economic_result_v1 import _verify_economic_failure_context_v1
        _verify_economic_failure_context_v1(case=case, reader=self._reader, failure=failure)
