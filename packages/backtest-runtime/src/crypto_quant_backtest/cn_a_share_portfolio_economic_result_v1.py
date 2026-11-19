"""Read-only verification of recorded economic facts; never execute or publish a run."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import json

import crypto_quant_domain as d
import crypto_quant_trading as t
import crypto_quant_trading.profiles.cn_a_share.portfolio_economic_v1 as e
from crypto_quant_trading.profiles.cn_a_share.portfolio_v1 import CnASharePortfolioOrderPlanV1, CnASharePortfolioOrderProposalV1
from . import execution_inputs as x
from .cn_a_share_portfolio_economic_case_v1 import (
    _bind_economic_portfolio_sources_v1, _clock_v1 as _at, _economic_events_v1, _economic_opening_proof_version_v1,
    _verify_bounded_signal_cancellation_v1,
)
from .cn_a_share_portfolio_economic_native_state_v1 import (_EconomicOpenSourcesV1, _economic_signal_target_v1,
    _advance_economic_settlement_v1, _EconomicFailureContextV1)
from .cn_a_share_portfolio_economic_opening_v1 import (_EconomicOpeningOutcomeV1, _EconomicFinancialStepV1,
    _economic_evaluation_v1, _verify_economic_opening_inputs_v1, _economic_venue_funding_v1, _cent)
from .cn_a_share_portfolio_economic_engine_v1 import _EconomicAdmissionV1, _used_identity_keys_v1, _economic_native_finance_identity_v1
from .cn_a_share_portfolio_economic_definition_v2 import CnASharePortfolioEconomicDevelopmentInputsV2, _read_economic_definition_v2
from .cn_a_share_portfolio_economic_activation_v2 import (
    _economic_activation_at_v2, _economic_activation_signal_v2, _economic_activation_value_v2, _economic_native_failure_inputs_v2,
)
from .cn_a_share_portfolio_economic_values_v1 import (_read_cn_a_share_cash_dividend_state_v1,
    _read_cn_a_share_cash_dividend_transition_v1, _read_cn_a_share_cash_dividend_transition_inputs_v1,
    _read_cn_a_share_cash_dividend_transition_failure_v1)
from .cn_a_share_portfolio_standard_native_state_v1 import _native_rebalance_plan_v1
from .cn_a_share_portfolio_financial_core_v1 import _id
from .cn_a_share_portfolio_engine_result_source_v1 import _fee
from .cn_a_share_portfolio_settlement_development_v1 import (
    _NativeSettlementResolutionMemo, _build_cn_a_share_portfolio_settlement_facts_v1, _book_body,
)
from .engine import EngineExecutionResult, EngineFailure, EngineFailureCode, ExecutionTrace, ExecutionTraceEntry, EngineStage
from .execution import BarOpenObservation, BarOpenKind, NoEligibleBarAction
from .financial_dispatch import FinancialDispatchArtifact
from .profile_portfolio_execution import _ResolvedProfilePortfolioCaseV2
from .run_end import RunEndCoordinator, RunEndEvidence, MarkToMarketCloseoutPolicy
from .timeline import TimelineCursorV2
from .target_repository import _artifact_ref

_PREFIX = "cn.portfolio.shared-cny.economic.development.v1"
_RESULT_FIELDS = {"type", "schema_version", "case_hash", "target_stream_digest", "trace", "decision_batches",
    "allocations", "approved_targets", "normalized_targets", "order_plans", "order_streams", "fills",
    "slippage_decisions", "fee_assessments", "financial_artifacts", "final_journal", "final_ledger_state",
    "final_portfolio_snapshot", "run_end_report"}
_SOURCE_FIELDS = {"type", "schema_version", "definition_hash", "at", "journal_count", "journal_hash",
    "ledger_hash", "book", "order_stream_hashes", "schedule_hashes", "market_rules_hash", "dividend_state",
    "journal_entry_ids", "economic_projection", "sellability", "reservations"}


def _map(value, fields=None):
    if not isinstance(value, Mapping) or (fields is not None and set(value) != fields):
        raise d.ArtifactIntegrityError("economic evidence exact mapping fields mismatch")
    return value


def _seq(value):
    if type(value) not in (list, tuple):
        raise TypeError("economic evidence requires a finite sequence")
    return tuple(value)


def _equal(expected, actual, label):
    if d.canonical_bytes(expected) != d.canonical_bytes(actual):
        raise d.ArtifactIntegrityError("economic evidence mismatch: " + label)


def _raw(value):
    return json.loads(d.canonical_bytes(value))


def _envelope(value):
    raw = _map(value, {"artifact_type", "schema_version", "payload", "content_hash"})
    return d.ArtifactEnvelope(raw["artifact_type"], raw["schema_version"], raw["payload"], raw["content_hash"])


def _artifact(value):
    raw = _map(value, {"type", "schema_version", "role", "source_event_id", "occurred_at", "component_key",
        "component_version", "component_digest", "input_hash", "result_hash", "payload"})
    if raw["type"] != "financial_dispatch_artifact" or type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise d.ArtifactIntegrityError("economic financial artifact version mismatch")
    result = FinancialDispatchArtifact(raw["role"], raw["source_event_id"], x._read_simulation_instant(raw["occurred_at"]),
        raw["component_key"], raw["component_version"], raw["component_digest"], raw["input_hash"], raw["result_hash"], _envelope(raw["payload"]))
    _equal(result, raw, "financial artifact canonical reconstruction")
    return result


def _trace(value):
    raw = _map(value, {"type", "schema_version", "entries"})
    if raw["type"] != "execution_trace" or type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise d.ArtifactIntegrityError("economic trace version mismatch")
    entries = []
    for value in _seq(raw["entries"]):
        row = _map(value, {"sequence", "stage", "instant", "subject_id", "evidence_hash"})
        entries.append(ExecutionTraceEntry(row["sequence"], EngineStage(row["stage"]), x._read_simulation_instant(row["instant"]), row["subject_id"], row["evidence_hash"]))
    result = ExecutionTrace(tuple(entries))
    _equal(result, raw, "trace")
    return result


def _verify_recorded_financial_batch_v1(*, inputs, prior, steps, recorded, fees):
    """C05: only derive expected immutable values for these recorded original claims."""
    ledger = t.GenericLedger(inputs.scope.ledger_schema).project(prior)
    accounting, assessment = t.CashInstrumentAccounting(), t.FeeAssessmentEngine()
    expected_fill, expected_fill_fee, expected_order_fee, assessed = [], [], [], []
    for ordinal, step in enumerate(steps, 1):
        fill = step.opening.fill
        cash = d.CashBalanceKey(fill.account_id, fill.venue_id, d.CurrencyId("CNY"))
        position = d.PositionBalanceKey(fill.account_id, fill.venue_id, fill.instrument_id)
        lots = next((row.lots for row in ledger.position_balances if row.key == position), ())
        def at(rank, code):
            return d.SimulationInstant(fill.execution_time, d.TimelinePhase(rank, code), d.SourceSequence(ordinal))
        booked = accounting.book_fill(fill=fill, cash_key=cash, position_key=position, open_lots=lots,
            cost_basis_policy=inputs.cost_basis_policy, notional_quantization=inputs.notional_quantization,
            journal_entry_id=_id(d.DomainIdKind.JOURNAL, "fill", step.opening.outcome_hash), recorded_at=at(70, "accounting"))
        if booked.result is None:
            raise d.ArtifactIntegrityError("recorded Fill fails native accounting derivation")
        expected_fill.append(booked.result.journal_entry)
        fill_fee = assessment.assess(basis=t.FeeAssessmentBasisEvidence.for_fill(fill), rule_set=step.final_fill_rules,
            fee_assessment_id=_id(d.DomainIdKind.FEE, "fill_fee", step.opening.outcome_hash), assessment_time=fill.execution_time)
        if fill_fee.result is None:
            raise d.ArtifactIntegrityError("recorded Fill fee fails native assessment")
        charged_fill = accounting.charge_fee(assessment=fill_fee.result.assessment, related_fill=fill, cash_key=cash,
            open_lots=booked.result.open_lots, cost_basis_policy=inputs.cost_basis_policy,
            journal_entry_id=_id(d.DomainIdKind.JOURNAL, "fill_fee", step.opening.outcome_hash), recorded_at=at(90, "fees"))
        if charged_fill.result is None:
            raise d.ArtifactIntegrityError("recorded Fill fee fails native immutable derivation")
        expected_fill_fee.append(charged_fill.result.journal_entry)
        order_fee = assessment.assess(basis=t.FeeAssessmentBasisEvidence.for_order(step.terminal_order), rule_set=step.final_order_rules,
            fee_assessment_id=_id(d.DomainIdKind.FEE, "order_fee", step.opening.outcome_hash), assessment_time=fill.execution_time)
        if order_fee.result is None:
            raise d.ArtifactIntegrityError("recorded Order fee fails native assessment")
        charged_order = accounting.charge_order_fee(assessment=order_fee.result.assessment, order_stream=step.terminal_order,
            cash_key=cash, open_lots=charged_fill.result.open_lots, cost_basis_policy=inputs.cost_basis_policy,
            journal_entry_id=_id(d.DomainIdKind.JOURNAL, "order_fee", step.opening.outcome_hash), recorded_at=at(91, "order_fee"))
        if charged_order.result is None:
            raise d.ArtifactIntegrityError("recorded Order fee fails native immutable derivation")
        expected_order_fee.append(charged_order.result.journal_entry)
        assessed.extend((fill_fee.result.assessment, order_fee.result.assessment))
    _equal((*expected_fill, *expected_fill_fee, *expected_order_fee), recorded, "complete original native journal entries/cost/fees/PNL")
    _equal(tuple(sorted(assessed, key=d.canonical_bytes)), tuple(sorted(fees, key=d.canonical_bytes)), "recorded native assessments")


def _verify_recorded_admission_v1(case, order, stream, admission, terms, observation, opening_index, ordinal, schedule):
    quote, market, issues, fee, reason = _economic_evaluation_v1(order, observation, terms)
    if reason is not None or quote != admission.quote or fee != admission.fee:
        raise d.ArtifactIntegrityError("recorded original admission native inputs mismatch")
    spec = market.approval.evaluation_input.executable_order_spec
    stages = ("intent", "capability", "translation", "market", "fee", "risk", "submitted", "accepted")
    kinds = (d.OrderEventType.ORDER_INTENT_CREATED, d.OrderEventType.ORDER_CAPABILITY_APPROVED,
        d.OrderEventType.ORDER_TRANSLATED, d.OrderEventType.MARKET_RULE_APPROVED,
        d.OrderEventType.FEE_RESERVATION_ESTIMATED, d.OrderEventType.PRE_TRADE_RISK_APPROVED,
        d.OrderEventType.ORDER_SUBMITTED, d.OrderEventType.ORDER_ACCEPTED)
    proofs = (admission.plan.plan_hash, spec.capability_approval.decision_id, spec.spec_id,
        market.approval.decision_id, fee.proposal_hash, admission.plan.plan_hash, terms.bar_event_hash, terms.bar_event_hash)
    records = stream.records[:8]
    if len(records) != 8:
        raise d.ArtifactIntegrityError("recorded original admission incomplete")
    root = f"signal.{admission.signal_index}.{order.intent.instrument_id}.open.{opening_index}."
    for i, (stage, kind, proof) in enumerate(zip(stages, kinds, proofs, strict=True)):
        cause = order.intent.parent_id if i == 0 else records[i-1].event.event_id
        at = order.created_at if i == 0 else _at(terms.opening_at, 55 + i, ordinal)
        expected = d.OrderEvent(case.event_id(root + stage), order.order_id, cause, kind, at, evidence_id=proof)
        _equal(t.OrderEventRecord(expected), records[i], "original actual acceptance coordinate/full clock")
    proposal = next(p for p in admission.plan.proposed if p.intent == order.intent)
    commitment = t.ReservationCommitment(cash=(proposal.principal,) if order.intent.side is d.OrderSide.BUY else (),
        sellable_quantities=(order.intent.quantity,) if order.intent.side is d.OrderSide.SELL else (),
        fee_reserve=fee.commitment.fee_reserve, order_capacity_units=1)
    expected_schedule = t.OrderReservationSchedule(order.order_id, fee.proposal_hash,
        (t.OrderReservationUpdate(order.order_id, records[-1].event.event_id, d.OrderEventType.ORDER_ACCEPTED,
            order.intent.quantity, commitment, admission.plan.plan_hash),))
    _equal(expected_schedule, schedule, "actual original reservation source")


def _expected_terminal_stream_v1(*,case,stream,opening,signal_index,opening_index,ordinal,when):
    """Reconstruct exact sealed terminal records without appending or selecting a Fill."""
    root=f"signal.{signal_index}.{stream.order.intent.instrument_id}.open.{opening_index}."
    records=list(stream.records)
    def record(stage,kind,at,fill=None):
        cause=records[-1].event.event_id
        event=d.OrderEvent(case.event_id(root+stage),stream.order.order_id,cause,kind,at,
            fill_id=None if fill is None else fill.fill_id,evidence_id=opening.outcome_hash)
        records.append(t.OrderEventRecord(event,fill))
    if opening.action is NoEligibleBarAction.EXPIRE:
        record("expired",d.OrderEventType.ORDER_EXPIRED,_at(when,95,opening_index+1))
    else:
        if stream.state.status is d.OrderStatus.ACCEPTED:
            record("activated",d.OrderEventType.ORDER_ACTIVATED,_at(when,68,ordinal))
        record("filled",d.OrderEventType.ORDER_FILLED,_at(when,69,ordinal),opening.fill)
    return t.OrderEventStream(stream.order,tuple(records))


def _verify_recorded_terminal_v1(*,terminal,case,stream,opening,signal_index,opening_index,ordinal,when):
    expected=_expected_terminal_stream_v1(case=case,stream=stream,opening=opening,signal_index=signal_index,
        opening_index=opening_index,ordinal=ordinal,when=when)
    if terminal!=expected:
        raise d.ArtifactIntegrityError("economic terminal exact sealed activation/Fill/expiry coordinates mismatch")
    return expected


def _expected_pending_admissions_v1(*, funded, candidates, target):
    """Derive the complete immutable native plan from source pending intentions, never witness rows."""
    inputs=funded.inputs
    accepted,blocked,proposals=[],{},[]
    for order,observation,terms in candidates:
        if any(s.order.order_id==order.order_id for s in funded.order_streams):
            continue
        quote,market,issues,fee,reason=_economic_evaluation_v1(order,observation,terms)
        if reason is None:
            proposal=CnASharePortfolioOrderProposalV1(order.intent,
                market.approval.calculated_notional if order.intent.side is d.OrderSide.BUY else _cent(0),
                fee.fee_estimate.total_fee,terms.reservation_rules.rule_set_hash)
            chosen=tuple(proposals)+(proposal,)
            try:
                CnASharePortfolioOrderPlanV1.create(account_id=inputs.scope.account_id,target_id=target.normalized_target_id,
                    target_hash=target.normalized_target_hash,as_of=funded.at.instant,policy=inputs.execution_policy,
                    cash=funded.cash,sellability=funded.sellability,working_orders=funded.order_streams,
                    reservation_schedules=funded.reservation_schedules,proposed=chosen)
            except ValueError as error:
                if str(error) not in {"portfolio plan may not reuse cash or prefinance sell receipts","portfolio plan T+1 forbids unsettled or reserved sell"}:
                    raise
                reason="native_cash_or_t1_unavailable"
            else:
                required={row.key.venue_id:0 for row in funded.economic_projection.cash_rows}
                buy=0
                for item in chosen:
                    demand=item.principal.units+item.estimated_fee.units
                    required[item.intent.instrument_id.venue]+=demand
                    if item.intent.side is d.OrderSide.BUY:
                        buy+=demand
                if order.intent.side is d.OrderSide.BUY and funded.economic_projection.tax_shortfall.units:
                    reason="tax_shortfall_buy_blocked"
                elif any(required[row.key.venue_id]>row.spendable.units for row in funded.economic_projection.cash_rows):
                    reason="venue_spendable_unavailable"
                elif buy>funded.economic_projection.buy_budget.units and any(p.intent.side is d.OrderSide.BUY for p in chosen):
                    reason="account_buy_budget_unavailable"
                else:
                    proposals.append(proposal)
                    accepted.append((order,observation,terms,quote,fee))
        if reason is not None:
            blocked[order.order_id]=(order,observation,terms,quote,market,issues,fee,reason)
    plan=None
    if accepted:
        plan=CnASharePortfolioOrderPlanV1.create(account_id=inputs.scope.account_id,target_id=target.normalized_target_id,
            target_hash=target.normalized_target_hash,as_of=funded.at.instant,policy=inputs.execution_policy,
            cash=funded.cash,sellability=funded.sellability,working_orders=funded.order_streams,
            reservation_schedules=funded.reservation_schedules,proposed=tuple(proposals))
    return tuple(accepted),blocked,plan


def _verify_economic_facts_v1(*, case, reader, journal, final_streams, final_schedules, artifacts, trace,
    admission_rows, final_pending, final_checkpoint=None, result=None, bound=None):
    if bound is None:
        bound = _bind_economic_portfolio_sources_v1(case, reader)
    inputs, openings, mapping = bound.inputs, bound.openings, bound.journal_entry_ids
    initial = case.financial_state
    current_journal, book, state = initial.journal, initial.settlement_book, case.execution_case_plan.initial_dividend_state
    streams, schedules, pending, admissions = {}, {}, {}, {}
    signals, collected_fills, collected_fees, collected_slips = [], [], [], []
    intention_ids = set()
    by_order = {s.order.order_id: s for s in final_streams}
    by_schedule = {s.order_id: s for s in final_schedules}
    if len(by_order) != len(final_streams) or len(by_schedule) != len(final_schedules):
        raise d.ArtifactIntegrityError("economic final order/schedule identities duplicated")
    v2 = type(inputs) is CnASharePortfolioEconomicDevelopmentInputsV2
    prefix, component = _economic_native_finance_identity_v1(inputs)
    opening_proof_version = _economic_opening_proof_version_v1(
        definition=case.execution_case_plan.definition, spec=case.semantic_spec)
    opening_source_keys = {"prior", "funded", "current"}
    if opening_proof_version == 2:
        opening_source_keys = {key + "_hash" for key in opening_source_keys}
    allowed = {"economic_signal", "economic_opening_batch", "economic_dividend_transition", "economic_daily_projection",
        "economic_pending_no_real_open", "economic_working_no_real_open", "economic_attempt_witness"}
    for artifact in artifacts:
        version = (opening_proof_version if artifact.role == "economic_opening_batch" else
            2 if artifact.role == "economic_attempt_witness" or (v2 and artifact.role == "economic_signal") else 1)
        if (artifact.role not in allowed or artifact.component_key != prefix + ".native-finance" or artifact.component_version != 1
                or artifact.component_digest != component or artifact.input_hash != inputs._definition_source_hash
                or artifact.payload.artifact_type != "cn_a_share_portfolio_" + artifact.role
                or artifact.payload.schema_version != version
                or (v2 and artifact.occurred_at < inputs.initial_marks.at)):
            raise d.ArtifactIntegrityError("economic role/component/source closure mismatch")
    ordered = sorted(artifacts, key=lambda row: (row.occurred_at, row.source_event_id, row.role))
    expected_no_real = {}
    settlement_memo = (_NativeSettlementResolutionMemo(inputs.calendars)
        if inputs.definition().schema_version == 4 else None)
    def make(at, j, b, ss, sch, st):
        b = _advance_economic_settlement_v1(case=case, inputs=inputs, journal=j, book=b, consumer=at)
        return _EconomicOpenSourcesV1(inputs, j, b, tuple(sorted(ss.values(), key=lambda s: s.order.order_id.value)),
            tuple(sorted(sch.values(), key=lambda s: s.order_id.value)), initial.settlement_rules, st, mapping, at, settlement_memo=settlement_memo)
    def commit(source):
        nonlocal current_journal, book, state, streams, schedules
        current_journal, book, state = source.journal, source.settlement_book, source.dividend_state
        streams = {s.order.order_id: s for s in source.order_streams}
        schedules = {s.order_id: s for s in source.reservation_schedules}
    def compare_source(source, raw):
        _map(raw, _SOURCE_FIELDS)
        _equal(source, raw, "full source checkpoint")
    def compare_opening_source(source, fact, key):
        if opening_proof_version == 2:
            if d.canonical_sha256(source) != fact[key + "_hash"]:
                raise d.ArtifactIntegrityError("economic opening source digest mismatch: " + key)
        else:
            compare_source(source, fact[key])
    def take(count):
        if type(count) is not int or not 0 <= count <= journal.entry_count:
            raise d.ArtifactIntegrityError("economic journal prefix count invalid")
        return t.AccountingJournal(journal.entries[:count])
    def event_prefix(stream, records):
        return t.OrderEventStream(stream.order, records)
    admission_raw = {}
    for row in admission_rows:
        row = _map(row, {"order_id", "signal_index", "plan", "sources", "fee", "quote"})
        identity = x._read_domain_id(row["order_id"])
        if identity in admission_raw:
            raise d.ArtifactIntegrityError("economic admission identity duplicated")
        admission_raw[identity] = row
    signal_count = opening_count = daily_count = dividend_count = 0
    seen_ca, seen_open, seen_daily, seen_no_real = set(), set(), set(), set()
    seen_sources, seen_activations = set(), set()
    for artifact in ordered:
        role, fact = artifact.role, _raw(artifact.payload.payload)
        if role == "economic_attempt_witness":
            continue
        if role == "economic_signal":
            fields = {"signal", "projection", "cancel_plan", "cancel_sources", "coordinator_plan", "coordinator_sources"}
            _map(fact, fields | {"activation"} if v2 else fields)
            index = signal_count
            if index >= len(case.target_stream.events):
                raise d.ArtifactIntegrityError("extra economic signal")
            event = case.target_stream.events[index]
            at = _economic_activation_at_v2(inputs) if v2 else inputs.signal_marks[index].at
            if v2:
                activation = _economic_activation_value_v2(inputs, event)
                _equal(activation, fact["activation"], "source-derived complete activation")
                coordinate = (event.event_id, activation.source_at, activation.activation_at)
                if event.event_id in seen_sources or coordinate in seen_activations:
                    raise d.ArtifactIntegrityError("economic V2 duplicate source/activation")
                seen_sources.add(event.event_id)
                seen_activations.add(coordinate)
            before = make(at, current_journal, book, streams, schedules, state)
            compare_source(before, fact["cancel_sources"])
            signal, projection = (_economic_activation_signal_v2(sources=before, event=event) if v2
                else _economic_signal_target_v1(sources=before, event=event))
            _equal(signal, fact["signal"], "native signal allocation/risk/sizing")
            _equal(projection, fact["projection"], "signal economic projection")
            cancel = CnASharePortfolioOrderPlanV1.create(account_id=inputs.scope.account_id,
                target_id=signal.normalized_target.normalized_target_id, target_hash=signal.normalized_target.normalized_target_hash,
                as_of=at.instant, policy=inputs.execution_policy, cash=before.cash, sellability=before.sellability,
                working_orders=before.order_streams, reservation_schedules=before.reservation_schedules, proposed=())
            _equal(cancel, fact["cancel_plan"], "native cancel plan")
            _verify_bounded_signal_cancellation_v1(case, cancel, admissions, index)
            changed = dict(streams)
            for cancellation in cancel.cancel_intents:
                prior = changed[cancellation.order_id]
                original = admissions[cancellation.order_id].signal_index
                root = f"signal.{original}.{cancellation.instrument_id}.signal.{index}."
                existing = by_order[cancellation.order_id]
                records = list(prior.records)
                for rank, stage, kind in ((37, "cancel_requested", d.OrderEventType.ORDER_CANCEL_REQUESTED), (38, "cancelled", d.OrderEventType.ORDER_CANCELLED)):
                    actual = existing.records[len(records)]
                    expected = d.OrderEvent(case.event_id(root + stage), prior.order.order_id,
                        records[-1].event.event_id, kind, _at(at.instant, rank), evidence_id=cancellation.cancel_intent_hash)
                    _equal(expected, actual.event, "recorded cancellation coordinate")
                    records.append(actual)
                changed[cancellation.order_id] = event_prefix(prior, tuple(records))
            after = make(_at(at.instant, 45), current_journal, before.settlement_book, changed, schedules, before.dividend_state)
            compare_source(after, fact["coordinator_sources"])
            plan = _native_rebalance_plan_v1(inputs=inputs, signal=signal, journal=current_journal,
                settlement_book=after.settlement_book, order_streams=after.order_streams,
                reservation_schedules=after.reservation_schedules, market_rules=after.market_rules, at=after.at)
            _equal(plan, fact["coordinator_plan"], "native coordination")
            if artifact.occurred_at != after.at or artifact.source_event_id != event.event_id:
                raise d.ArtifactIntegrityError("economic signal clock/owner mismatch")
            pending = {}
            planned = sorted(plan.planned_orders, key=lambda p: (p.intent.side is d.OrderSide.BUY,
                str(p.intent.instrument_id), case.domain_id(f"signal.{index}.{p.intent.instrument_id}.order").value))
            for ordinal, proposal in enumerate(planned, 1):
                intent = replace(proposal.intent, time_in_force=inputs.execution_policy.time_in_force_for(proposal.intent.side))
                order = d.Order(case.domain_id(f"signal.{index}.{intent.instrument_id}.order"), inputs.scope.account_id, intent, _at(at.instant, 40, ordinal))
                pending[intent.instrument_id] = (index, order)
                intention_ids.add(order.order_id)
            signals.append(signal)
            signal_count += 1
            commit(after)
        elif role == "economic_dividend_transition":
            _map(fact, {"transition", "post_checkpoint"})
            transition = _read_cn_a_share_cash_dividend_transition_v1(fact["transition"])
            matches = tuple(row for row in _economic_events_v1(inputs) if row[3] == artifact.source_event_id)
            if len(matches) != 1 or matches[0][0] != artifact.occurred_at or artifact.source_event_id in seen_ca:
                raise d.ArtifactIntegrityError("economic C-A source event mismatch")
            at, kind, action, event_id = matches[0]
            pre = make(d.SimulationInstant(at.instant, at.phase, d.SourceSequence(at.source_sequence.value - 1)), current_journal, book, streams, schedules, state)
            if (transition.kind != kind or transition.event_id != event_id or transition.event_at != at
                    or transition.input_journal_hash != pre.journal.journal_hash or transition.input_state_hash != d.canonical_sha256(pre.dividend_state)
                    or transition.action_set_hash != d.canonical_sha256(inputs.dividend_actions)
                    or transition.action_terms_hash != d.canonical_sha256(action) or transition.tax_policy_hash != d.canonical_sha256(action.tax_policy)):
                raise d.ArtifactIntegrityError("economic C-A transition input/source mismatch")
            count = pre.journal.entry_count + len(transition.journal_entries)
            candidate = take(count)
            _equal(candidate.entries[pre.journal.entry_count:], transition.journal_entries, "actual C-A entries")
            if candidate.journal_hash != transition.output_journal_hash:
                raise d.ArtifactIntegrityError("economic C-A output journal mismatch")
            post = make(at, candidate, pre.settlement_book, streams, schedules, transition.state_after)
            compare_source(post, fact["post_checkpoint"])
            claim = next(c for c in post.dividend_state.claims if c.instrument_id == action.instrument_id and c.action_id == action.action_id)
            if next(row[3] for row in claim.applied_events if row[0] == kind) != transition.payload_hash:
                raise d.ArtifactIntegrityError("economic C-A payload not bound to verified history")
            seen_ca.add(event_id)
            dividend_count += 1
            commit(post)
        elif role == "economic_opening_batch":
            if v2 and not seen_activations:
                raise d.ArtifactIntegrityError("economic V2 opening lacks prior activation")
            _map(fact, opening_source_keys | {"when", "funding", "outcomes", "steps", "journal_count_after", "book_after", "dividend_state_after", "post_projection"})
            when = x._read_utc(fact["when"])
            bars = bound.opening_batches.get(when, ())
            if not bars or when in seen_open or artifact.source_event_id != bars[0][1].event_id or artifact.occurred_at != _at(when, 98):
                raise d.ArtifactIntegrityError("economic opening source/clock/cover mismatch")
            prior = make(_at(when, 49), current_journal, book, streams, schedules, state)
            compare_opening_source(prior, fact, "prior")
            by_instrument = {event.instrument_id: (i, event) for i, event in bars}
            candidates = []
            for _, order in pending.values():
                _, event = by_instrument[order.intent.instrument_id]
                if order.created_at.instant < when and BarOpenObservation.from_event(event).kind is BarOpenKind.REAL:
                    term = bound.terms_by_side[event.event_id, order.intent.side]
                    candidates.append((order, BarOpenObservation.from_event(event), term))
            for stream in streams.values():
                _, event = by_instrument[stream.order.intent.instrument_id]
                if stream.state is not None and stream.state.status in {d.OrderStatus.ACCEPTED, d.OrderStatus.ACTIVE} and BarOpenObservation.from_event(event).kind is BarOpenKind.REAL:
                    term = bound.terms_by_side[event.event_id, stream.order.intent.side]
                    candidates.append((stream.order, BarOpenObservation.from_event(event), term))
            candidates.sort(key=lambda row: (row[0].intent.side is d.OrderSide.BUY, str(row[0].intent.instrument_id), row[0].order_id.value))
            funding = tuple(x._read_economic_journal_entry_v1(v) for v in _seq(fact["funding"]))
            _equal(_economic_venue_funding_v1(sources=prior, candidates=tuple(candidates)), funding, "recorded native funding purpose/amount/tax bounds")
            funded_journal = take(prior.journal.entry_count + len(funding))
            _equal(funded_journal.entries[prior.journal.entry_count:], funding, "whole native funding suffix")
            funded = make(_at(when, 55), funded_journal, prior.settlement_book, streams, schedules, prior.dividend_state)
            compare_opening_source(funded, fact, "funded")
            changed, changed_schedules = dict(streams), dict(schedules)
            new_rows = [row for key, row in admission_raw.items() if key not in admissions
                and x._read_simulation_instant(row["sources"]["at"]).instant == when]
            new_rows.sort(key=lambda row: (by_order[x._read_domain_id(row["order_id"])].order.intent.side is d.OrderSide.BUY,
                str(by_order[x._read_domain_id(row["order_id"])].order.intent.instrument_id), row["order_id"]["value"]))
            accepted,blocked,plan=_expected_pending_admissions_v1(funded=funded,candidates=tuple(candidates),target=signals[-1].normalized_target if signals else None)
            if tuple(x._read_domain_id(row["order_id"]) for row in new_rows)!=tuple(row[0].order_id for row in accepted):
                raise d.ArtifactIntegrityError("economic admission omits or invents source-eligible pending candidate")
            if new_rows:
                for ordinal, row in enumerate(new_rows, 1):
                    identity = x._read_domain_id(row["order_id"])
                    stream = by_order[identity]
                    source_order=accepted[ordinal-1][0]
                    source_origin=pending[source_order.intent.instrument_id][0]
                    if stream.order!=source_order or row["signal_index"]!=source_origin:
                        raise d.ArtifactIntegrityError("economic admission complete source Order or signal origin mismatch")
                    _equal(plan, row["plan"], "recorded admission plan")
                    compare_source(funded, row["sources"])
                    order = stream.order
                    _, event = by_instrument[order.intent.instrument_id]
                    term = bound.terms_by_side[event.event_id, order.intent.side]
                    quote, market, issues, fee, reason = _economic_evaluation_v1(order, BarOpenObservation.from_event(event), term)
                    admission = _EconomicAdmissionV1(row["signal_index"], plan, funded, fee, quote)
                    opening_index, _ = by_instrument[order.intent.instrument_id]
                    _verify_recorded_admission_v1(case, order, stream, admission, term, BarOpenObservation.from_event(event),
                        opening_index, ordinal, by_schedule[identity])
                    admissions[identity] = admission
                    changed[identity] = event_prefix(stream, stream.records[:8])
                    changed_schedules[identity] = by_schedule[identity]
                    del pending[order.intent.instrument_id]
            current = make(_at(when, 67), funded_journal, funded.settlement_book, changed, changed_schedules, funded.dividend_state)
            compare_opening_source(current, fact, "current")
            for _,order in pending.values():
                _,event=by_instrument[order.intent.instrument_id]
                if order.created_at.instant<when and BarOpenObservation.from_event(event).kind is not BarOpenKind.REAL:
                    expected_no_real[("economic_pending_no_real_open",order.order_id,event.event_id)]=(_at(when,98),{
                        "order":order,"stream_hash":None,"schedule_hash":None,"raw_event_hash":event.event_hash,
                        "action":"expire_at_daily_close" if order.intent.time_in_force is d.TimeInForce.DAY else "keep_original","prefix":current})
            for stream in streams.values():
                _,event=by_instrument[stream.order.intent.instrument_id]
                if (stream.state is not None and stream.state.status in {d.OrderStatus.ACCEPTED,d.OrderStatus.ACTIVE}
                        and BarOpenObservation.from_event(event).kind is not BarOpenKind.REAL):
                    order=stream.order
                    expected_no_real[("economic_working_no_real_open",order.order_id,event.event_id)]=(_at(when,98),{
                        "order":order,"stream_hash":stream.stream_hash,"schedule_hash":schedules[order.order_id].schedule_hash,
                        "raw_event_hash":event.event_hash,"action":"expire_at_daily_close" if order.intent.time_in_force is d.TimeInForce.DAY else "keep_original","prefix":current})
            selected, outcomes, steps = [], [], []
            outcome_ids = set()
            for value in _seq(fact["outcomes"]):
                value = _map(value)
                identity = x._read_domain_id(value["order_id"])
                if identity in outcome_ids:
                    raise d.ArtifactIntegrityError("economic opening duplicates Order")
                outcome_ids.add(identity)
                if value["original_admission_hash"] is None:
                    if identity not in blocked:
                        raise d.ArtifactIntegrityError("economic pending intention fabricates budget refusal")
                    order,observation,term,quote,market,issues,fee,reason=blocked[identity]
                    action=NoEligibleBarAction.EXPIRE if order.intent.time_in_force is d.TimeInForce.DAY else NoEligibleBarAction.KEEP_ACTIVE
                    expected=_EconomicOpeningOutcomeV1(identity,observation.observation_hash,d.canonical_sha256(current),None,
                        d.canonical_sha256(term),quote,market,issues,fee,action,reason,None,_cent(0),_cent(0),())
                    _equal(expected,value,"complete pending rejection/deferral")
                    continue
                stream = changed[identity]
                _, event = by_instrument[stream.order.intent.instrument_id]
                observation = BarOpenObservation.from_event(event)
                term = bound.terms_by_side[event.event_id, stream.order.intent.side]
                admission = admissions[identity]
                quote, market, issues, fee, reason, extra_p, extra_f = _verify_economic_opening_inputs_v1(sources=current,
                    stream=stream, observation=observation, terms=term, admission=admission, budget_prefix=tuple(selected))
                fill = None if value["fill"] is None else x._read_fill(value["fill"])
                action = NoEligibleBarAction.FULL_FILL if reason is None else NoEligibleBarAction.EXPIRE if stream.order.intent.time_in_force is d.TimeInForce.DAY else NoEligibleBarAction.KEEP_ACTIVE
                outcome = _EconomicOpeningOutcomeV1(identity, observation.observation_hash, d.canonical_sha256(current),
                    d.canonical_sha256(admission), d.canonical_sha256(term), quote, market, issues, fee, action, reason, fill,
                    _cent(extra_p), _cent(extra_f), tuple(row.order_id for row in selected))
                _equal(outcome, value, "recorded opening eligibility/budget/quote")
                outcomes.append(outcome)
                if fill is not None:
                    decision = quote.result
                    expected_id = d.DomainId(d.DomainIdKind.FILL, d.DomainIdKind.FILL.prefix + "_" + d.canonical_sha256({
                        "type": "cn_a_share_portfolio_economic_open_fill_identity", "order_id": identity,
                        "open_event_hash": event.event_hash, "economic_proof_hash": d.canonical_sha256(current),
                        "slippage_decision_id": decision.decision_id})[7:])
                    if (fill.fill_id != expected_id or fill.order_id != identity or fill.quantity != stream.order.intent.quantity
                            or fill.instrument_id != stream.order.intent.instrument_id or fill.account_id != inputs.scope.account_id
                            or fill.side is not stream.order.intent.side or fill.reference_price != observation.open_price
                            or fill.price != decision.execution_price or fill.execution_time != when
                            or fill.slippage_decision_id != decision.decision_id or fill.slippage_model_key != decision.component_ref.component_key
                            or fill.slippage_calibration_id != d.canonical_sha256(decision.calibration_ref)
                            or fill.slippage_amount != d.Money(decision.slippage_amount.units, decision.slippage_amount.scale, decision.slippage_amount.quote_currency)):
                        raise d.ArtifactIntegrityError("recorded Fill is not its original native slippage/identity")
                    selected.append(outcome)
                    collected_fills.append(fill)
                    collected_slips.append(decision)
            expected_working = {s.order.order_id for s in changed.values() if s.state is not None
                and s.state.status in {d.OrderStatus.ACCEPTED, d.OrderStatus.ACTIVE}
                and BarOpenObservation.from_event(by_instrument[s.order.intent.instrument_id][1]).kind is BarOpenKind.REAL}
            expected_order=tuple(blocked)+tuple(s.order.order_id for s in sorted((s for s in changed.values() if s.order.order_id in expected_working),
                key=lambda s:(s.order.intent.side is d.OrderSide.BUY,str(s.order.intent.instrument_id),s.order.order_id.value)))
            if tuple(x._read_domain_id(v["order_id"]) for v in _seq(fact["outcomes"]))!=expected_order:
                raise d.ArtifactIntegrityError("economic opening pending/working outcome exact cover/order mismatch")
            raw_steps = _seq(fact["steps"])
            if len(raw_steps) != len(selected):
                raise d.ArtifactIntegrityError("economic step/selected Fill exact cover mismatch")
            for opening, raw_step in zip(selected, raw_steps, strict=True):
                raw_step = _map(raw_step, {"type", "schema_version", "opening", "terminal_order", "terms"})
                terminal = x._read_order_event_stream(raw_step["terminal_order"])
                prior_stream = changed[opening.order_id]
                prior_intent = prior_stream.order.intent
                opening_index, event = by_instrument[prior_intent.instrument_id]
                term = bound.terms_by_side[event.event_id, prior_intent.side]
                if d.canonical_sha256(term) != opening.terms_hash:
                    raise d.ArtifactIntegrityError("recorded financial step terms differ from source coordinate")
                step = _EconomicFinancialStepV1(opening, terminal, term)
                _equal(step, raw_step, "recorded financial step")
                working_order=tuple(s.order.order_id for s in sorted((s for s in current.order_streams if s.state is not None and s.state.status in {d.OrderStatus.ACCEPTED,d.OrderStatus.ACTIVE}),
                    key=lambda s:(s.order.intent.side is d.OrderSide.BUY,str(s.order.intent.instrument_id),s.order.order_id.value)))
                expected_terminal=_verify_recorded_terminal_v1(terminal=terminal,case=case,stream=prior_stream,opening=opening,
                    signal_index=admissions[opening.order_id].signal_index,opening_index=opening_index,ordinal=working_order.index(opening.order_id)+1,when=when)
                if terminal!=expected_terminal or by_order[opening.order_id].records[:len(terminal.records)]!=terminal.records:
                    raise d.ArtifactIntegrityError("economic terminal exact sealed activation/Fill coordinates mismatch")
                steps.append(step)
                changed[opening.order_id] = terminal
            after = take(fact["journal_count_after"])
            recorded = after.entries[current.journal.entry_count:]
            expected_fees = []
            for step in steps:
                for role_name, basis, ruleset in (("fill_fee", t.FeeAssessmentBasisEvidence.for_fill(step.opening.fill), step.final_fill_rules),
                    ("order_fee", t.FeeAssessmentBasisEvidence.for_order(step.terminal_order), step.final_order_rules)):
                    checked = t.FeeAssessmentEngine().assess(basis=basis, rule_set=ruleset,
                        fee_assessment_id=_id(d.DomainIdKind.FEE, role_name, step.opening.outcome_hash), assessment_time=when)
                    if checked.result is None:
                        raise d.ArtifactIntegrityError("recorded fee source rejected")
                    expected_fees.append(checked.result.assessment)
            _verify_recorded_financial_batch_v1(inputs=inputs, prior=current.journal, steps=tuple(steps), recorded=recorded, fees=tuple(expected_fees))
            collected_fees.extend(expected_fees)
            if steps:
                native = _build_cn_a_share_portfolio_settlement_facts_v1(fills=tuple(s.opening.fill for s in steps), journal=after,
                    source_hash=d.canonical_sha256(tuple(steps)), calendars=inputs.calendars).book
                obligations = tuple(sorted((*current.settlement_book.obligations, *native.obligations), key=lambda ob: ob.obligation.settlement_obligation_id.value))
                events = tuple(sorted((*current.settlement_book.events, *native.events), key=lambda event: (event.occurred_at, event.event_id)))
                next_book = t.SettlementBook(inputs.scope.account_id, obligations, events)
            else:
                next_book = current.settlement_book
            for opening in outcomes:
                if opening.action is NoEligibleBarAction.EXPIRE:
                    existing = by_order[opening.order_id]
                    prior_stream = changed[opening.order_id]
                    opening_index,_=by_instrument[prior_stream.order.intent.instrument_id]
                    supplied=event_prefix(existing,existing.records[:len(prior_stream.records)+1])
                    changed[opening.order_id]=_verify_recorded_terminal_v1(terminal=supplied,case=case,stream=prior_stream,opening=opening,
                        signal_index=admissions[opening.order_id].signal_index,opening_index=opening_index,ordinal=opening_index+1,when=when)
            post = make(_at(when, 97), after, next_book, changed, changed_schedules, current.dividend_state)
            _equal(_book_body(post.settlement_book), fact["book_after"], "post native Book")
            _equal(post.dividend_state, fact["dividend_state_after"], "post dividend state")
            _equal(post.economic_projection, fact["post_projection"], "post complete economic projection")
            commit(post)
            seen_open.add(when)
            opening_count += 1
        elif role == "economic_daily_projection":
            if v2 and not seen_activations:
                raise d.ArtifactIntegrityError("economic V2 daily finance lacks prior activation")
            _map(fact, {"marks", "checkpoint", "pending_intentions"})
            at = artifact.occurred_at
            expected = tuple(b for b in inputs.daily_marks if b.at == at)
            if len(expected) != 1 or at in seen_daily:
                raise d.ArtifactIntegrityError("economic daily source/count mismatch")
            _equal(expected[0], fact["marks"], "daily mark source")
            checkpoint = make(at, current_journal, book, streams, schedules, state)
            compare_source(checkpoint, fact["checkpoint"])
            pending = {key: row for key, row in pending.items() if not (row[1].intent.time_in_force is d.TimeInForce.DAY and row[1].created_at.instant < at.instant)}
            _equal(tuple(order for _, order in sorted(pending.values(), key=lambda row: row[1].order_id.value)), fact["pending_intentions"], "daily original intention lifecycle")
            commit(checkpoint)
            seen_daily.add(at)
            daily_count += 1
        else:
            _map(fact, {"order", "stream_hash", "schedule_hash", "raw_event_hash", "action", "prefix"})
            order = x._read_order(fact["order"])
            event = next(v for v in openings if v.event_id == artifact.source_event_id)
            if BarOpenObservation.from_event(event).kind is BarOpenKind.REAL or event.event_hash != fact["raw_event_hash"]:
                raise d.ArtifactIntegrityError("economic no-real-open source is false")
            key = (role, order.order_id, event.event_id)
            if key in seen_no_real:
                raise d.ArtifactIntegrityError("economic no-real-open duplicate")
            if key not in expected_no_real:
                raise d.ArtifactIntegrityError("economic no-real-open invents original pending/working obligation")
            expected_at,expected_fact=expected_no_real[key]
            if artifact.occurred_at!=expected_at:
                raise d.ArtifactIntegrityError("economic no-real-open clock mismatch")
            _equal(expected_fact,fact,"complete no-real-open retained obligation")
            seen_no_real.add(key)
    if v2:
        source = case.target_stream.events[0]
        activation = _economic_activation_value_v2(inputs, source)
        expected_sources = {source.event_id}
        expected_activations = {(source.event_id, activation.source_at, activation.activation_at)}
        end = _at(case.timeline.window.end_exclusive, 200) if final_checkpoint is None else x._read_simulation_instant(final_checkpoint["at"])
        required = final_checkpoint is None or end >= _at(activation.activation_at.instant, 45)
        expected_open = {event.event_time for event in openings if _at(event.event_time, 97) <= end}
        expected_daily = {batch.at for batch in inputs.daily_marks if batch.at <= end}
        if seen_open != expected_open or seen_daily != expected_daily:
            raise d.ArtifactIntegrityError("economic V2 committed active prefix omits required opening/daily facts")
        if ((required and (seen_sources != expected_sources or seen_activations != expected_activations))
                or (not required and (seen_sources or seen_activations))):
            raise d.ArtifactIntegrityError("economic V2 source/activation exact cover mismatch")
    # A typed native batch failure may follow the committed67 admission checkpoint,
    # while its provisional Fill/fee/Book candidates have never committed at97.
    if final_checkpoint is not None:
        end_at = x._read_simulation_instant(final_checkpoint["at"])
        if end_at.phase.rank == 67 and end_at.instant not in seen_open:
            when = end_at.instant
            bars = bound.opening_batches.get(when, ())
            if not bars:
                raise d.ArtifactIntegrityError("failed admission checkpoint has no raw opening")
            by_instrument = {event.instrument_id:(i,event) for i,event in bars}
            prior = make(_at(when,49), current_journal, book, streams, schedules, state)
            candidates = []
            for _, order in pending.values():
                _, event = by_instrument[order.intent.instrument_id]
                if order.created_at.instant < when and BarOpenObservation.from_event(event).kind is BarOpenKind.REAL:
                    terms = bound.terms_by_side[event.event_id, order.intent.side]
                    candidates.append((order,BarOpenObservation.from_event(event),terms))
            for stream in streams.values():
                _, event = by_instrument[stream.order.intent.instrument_id]
                if stream.state is not None and stream.state.status in {d.OrderStatus.ACCEPTED,d.OrderStatus.ACTIVE} and BarOpenObservation.from_event(event).kind is BarOpenKind.REAL:
                    terms = bound.terms_by_side[event.event_id, stream.order.intent.side]
                    candidates.append((stream.order,BarOpenObservation.from_event(event),terms))
            candidates.sort(key=lambda row:(row[0].intent.side is d.OrderSide.BUY,str(row[0].intent.instrument_id),row[0].order_id.value))
            funding = _economic_venue_funding_v1(sources=prior,candidates=tuple(candidates))
            funded_journal = take(prior.journal.entry_count+len(funding))
            _equal(funded_journal.entries[prior.journal.entry_count:],funding,"failed actual full funding suffix")
            funded = make(_at(when,55),funded_journal,prior.settlement_book,streams,schedules,prior.dividend_state)
            rows = [row for identity,row in admission_raw.items() if identity not in admissions]
            rows.sort(key=lambda row:(by_order[x._read_domain_id(row["order_id"])].order.intent.side is d.OrderSide.BUY,
                str(by_order[x._read_domain_id(row["order_id"])].order.intent.instrument_id),row["order_id"]["value"]))
            expected_accepted,_,expected_plan=_expected_pending_admissions_v1(funded=funded,candidates=tuple(candidates),target=signals[-1].normalized_target if signals else None)
            if tuple(x._read_domain_id(row["order_id"]) for row in rows)!=tuple(row[0].order_id for row in expected_accepted):
                raise d.ArtifactIntegrityError("failed admission omits source-eligible pending candidate")
            proposals, native = [], []
            for row in rows:
                identity=x._read_domain_id(row["order_id"]);order=by_order[identity].order
                if (order.intent.instrument_id not in pending or pending[order.intent.instrument_id][1]!=order
                        or row["signal_index"]!=pending[order.intent.instrument_id][0]):
                    raise d.ArtifactIntegrityError("failed admission complete source Order or signal origin mismatch")
                i,event=by_instrument[order.intent.instrument_id]
                term=next(t for t in inputs.opening_terms if t.bar_event_id==event.event_id and t.side is order.intent.side)
                quote,market,issues,fee,reason=_economic_evaluation_v1(order,BarOpenObservation.from_event(event),term)
                if reason is not None:
                    raise d.ArtifactIntegrityError("failed committed admission is ineligible")
                proposals.append(CnASharePortfolioOrderProposalV1(order.intent,market.approval.calculated_notional if order.intent.side is d.OrderSide.BUY else _cent(0),fee.fee_estimate.total_fee,term.reservation_rules.rule_set_hash))
                native.append((row,order,i,event,term,quote,fee))
            if native:
                plan=CnASharePortfolioOrderPlanV1.create(account_id=inputs.scope.account_id,target_id=signals[-1].normalized_target.normalized_target_id,
                    target_hash=signals[-1].normalized_target.normalized_target_hash,as_of=when,policy=inputs.execution_policy,cash=funded.cash,
                    sellability=funded.sellability,working_orders=funded.order_streams,reservation_schedules=funded.reservation_schedules,proposed=tuple(proposals))
                for ordinal,(row,order,i,event,term,quote,fee) in enumerate(native,1):
                    compare_source(funded,row["sources"]);_equal(expected_plan,row["plan"],"failed complete source admission plan")
                    _equal(quote,row["quote"],"failed original quote");_equal(fee,row["fee"],"failed original fee")
                    admission=_EconomicAdmissionV1(row["signal_index"],plan,funded,fee,quote)
                    _verify_recorded_admission_v1(case,order,by_order[order.order_id],admission,term,BarOpenObservation.from_event(event),i,ordinal,by_schedule[order.order_id])
                    admissions[order.order_id]=admission;streams[order.order_id]=event_prefix(by_order[order.order_id],by_order[order.order_id].records[:8])
                    schedules[order.order_id]=by_schedule[order.order_id];del pending[order.intent.instrument_id]
            current_journal,book,state=funded_journal,funded.settlement_book,funded.dividend_state
    if set(expected_no_real)!=seen_no_real:
        raise d.ArtifactIntegrityError("economic no-real-open obligation exact cover mismatch")
    if set(admissions) != set(admission_raw):
        raise d.ArtifactIntegrityError("economic recorded admission missing from native chronology")
    ending_at = _at(case.timeline.window.end_exclusive, 200) if final_checkpoint is None else x._read_simulation_instant(final_checkpoint["at"])
    ending = make(ending_at, current_journal, book, streams, schedules, state)
    if final_checkpoint is not None:
        compare_source(ending, final_checkpoint)
    _equal(ending.journal, journal, "final/failed committed journal exact cover")
    _equal(ending.order_streams, tuple(sorted(final_streams, key=lambda s: s.order.order_id.value)), "final committed Order streams")
    _equal(ending.reservation_schedules, tuple(sorted(final_schedules, key=lambda s: s.order_id.value)), "final schedules")
    _equal(tuple(order for _, order in sorted(pending.values(), key=lambda row: row[1].order_id.value)), final_pending, "final original pending intentions")
    return ending, signals, tuple(collected_fills), tuple(collected_fees), tuple(collected_slips), (signal_count, opening_count, daily_count, dividend_count), admissions, pending, intention_ids


def _verify_economic_native_result_v1(*, case, reader, result):
    if type(case) is not _ResolvedProfilePortfolioCaseV2:
        raise TypeError("economic result requires exact CaseV2")
    native = type(result) is EngineExecutionResult and case.execution_case_plan.definition.schema_version == 4
    raw = _map(result.to_canonical_dict() if native else _raw(result), _RESULT_FIELDS)
    if (raw["type"] != "engine_execution_result" or type(raw["schema_version"]) is not int or raw["schema_version"] != 1
            or raw["case_hash"] != case.case_hash or raw["target_stream_digest"] != case.target_stream.target_stream_digest or _seq(raw["order_plans"])):
        raise d.ArtifactIntegrityError("economic result case/schema/plan mismatch")
    journal = x._read_economic_journal_v1(_raw(raw["final_journal"]) if native else raw["final_journal"])
    streams = tuple(x._read_order_event_stream(_raw(v) if native else v) for v in _seq(raw["order_streams"]))
    if native:
        # Prove each encoding against the value used below without retaining a
        # second copy of every large financial proof. Never trust a subclass's
        # in-memory component coordinates over its serialized evidence.
        artifacts = result.financial_artifacts
        for artifact in artifacts:
            if type(artifact) is not FinancialDispatchArtifact or _artifact(_raw(artifact)) != artifact:
                raise d.ArtifactIntegrityError("economic financial artifact component or wire mismatch")
    else:
        artifacts = tuple(_artifact(v) for v in _seq(raw["financial_artifacts"]))
    if any(a.role=="economic_native_failure" for a in artifacts):
        raise d.ArtifactIntegrityError("COMPLETED cannot contain a native failure diagnostic")
    witnesses = tuple(a for a in artifacts if a.role == "economic_attempt_witness")
    if len(witnesses) != 1:
        raise d.ArtifactIntegrityError("economic result requires one completion witness")
    outer = _map(_raw(witnesses[0].payload.payload), {"type", "schema_version", "economic_witness", "economic_witness_hash", "source_binding"})
    if (outer["type"] != "cn_a_share_portfolio_economic_native_witness" or type(outer["schema_version"]) is not int or outer["schema_version"] != 2
            or outer["economic_witness_hash"] != d.canonical_sha256(outer["economic_witness"])):
        raise d.ArtifactIntegrityError("economic witness requires exact version2/inner hash")
    binding = _map(outer["source_binding"], {"type", "schema_version", "source_refs", "semantic_spec", "identity_manifest", "timeline_stream_keys"})
    expected_binding = {"type": "cn_a_share_portfolio_economic_completed_sources", "schema_version": 1,
        "source_refs": case.execution_case_plan.source_refs, "semantic_spec": case.semantic_spec,
        "identity_manifest": case.identity_manifest, "timeline_stream_keys": case.timeline.stream_keys}
    _equal(expected_binding, binding, "completed original retained source binding")
    witness = _map(outer["economic_witness"])
    expected_fields = {"type", "schema_version", "case_hash", "definition_hash", "target_stream_digest", "initial_journal_hash",
        "initial_economic_projection_hash", "schedules", "book", "admissions", "opening_count", "daily_count", "dividend_event_count",
        "financial_schedule_hash", "journal_entry_ids", "used_identity_keys", "cursor", "final_journal_hash", "final_ledger_hash",
        "final_dividend_state", "final_economic_projection", "run_end_report_hash", "pending_intentions", "checkpoint_head",
        "source_qualification_verified", "broker_shared_pool_verified", "trade_authorized"}
    _map(witness, expected_fields)
    if (witness["type"] != "cn_a_share_portfolio_economic_native_witness" or type(witness["schema_version"]) is not int or witness["schema_version"] != 1
            or witness["case_hash"] != case.case_hash or witness["definition_hash"] != d.canonical_sha256(case.execution_case_plan.definition)
            or witness["target_stream_digest"] != case.target_stream.target_stream_digest
            or witness["initial_journal_hash"] != case.financial_state.journal.journal_hash
            or witness["initial_economic_projection_hash"] != case.execution_case_plan.initial_economic_projection.projection_hash
            or any(witness[key] is not False for key in ("source_qualification_verified", "broker_shared_pool_verified", "trade_authorized"))):
        raise d.ArtifactIntegrityError("economic witness source/initial/qualification mismatch")
    schedules = tuple(x._read_reservation_schedule(v) for v in _seq(witness["schedules"]))
    trace = _trace(_raw(raw["trace"]) if native else raw["trace"])
    bound = _bind_economic_portfolio_sources_v1(case, reader)
    ending, signals, fills, fees, slips, counts, _admissions, _pending, _intentions = _verify_economic_facts_v1(case=case, reader=reader, journal=journal,
        final_streams=streams, final_schedules=schedules, artifacts=artifacts, trace=trace,
        admission_rows=_seq(witness["admissions"]), final_pending=witness["pending_intentions"], bound=bound)
    inputs = bound.inputs
    if counts != (len(case.target_stream.events), len({e.event_time for e in bound.openings}), len(inputs.daily_marks),
            len(tuple(row for row in _economic_events_v1(inputs) if row[0].instant < case.timeline.window.end_exclusive))):
        raise d.ArtifactIntegrityError("economic facts omit or duplicate a required source event")
    if (witness["opening_count"], witness["daily_count"], witness["dividend_event_count"]) != counts[1:]:
        raise d.ArtifactIntegrityError("economic witness fact counts mismatch")
    _equal(bound.journal_entry_ids, witness["journal_entry_ids"], "sealed complete journal ID mapping")
    _equal(_used_identity_keys_v1(case, journal, {s.order.order_id:s for s in streams},
        {o.intent.instrument_id:(0,o) for o in (x._read_order(v) for v in _seq(witness["pending_intentions"]))}, _intentions), witness["used_identity_keys"], "actually used identity keys")
    expected_schedule = d.canonical_sha256({"action_set": inputs.dividend_actions,
        "events": tuple((eid, kind, at) for at, kind, _, eid in _economic_events_v1(inputs))})
    if witness["financial_schedule_hash"] != expected_schedule:
        raise d.ArtifactIntegrityError("economic financial schedule hash mismatch")
    ledger = t.GenericLedger(inputs.scope.ledger_schema).project(journal)
    _equal(ledger, raw["final_ledger_state"], "native ledger")
    _equal(ending.economic_projection.snapshot, raw["final_portfolio_snapshot"], "economic final snapshot")
    _equal(ending.economic_projection, witness["final_economic_projection"], "final economic proof")
    _equal(ending.dividend_state, witness["final_dividend_state"], "final dividend state")
    _equal(_book_body(ending.settlement_book), witness["book"], "final Book")
    for name, values in (("fills", fills), ("fee_assessments", fees), ("slippage_decisions", slips),
            ("decision_batches", tuple(s.decision_batch for s in signals)), ("allocations", tuple(s.allocation for s in signals)),
            ("approved_targets", tuple(s.approved_target for s in signals)), ("normalized_targets", tuple(s.normalized_target for s in signals))):
        expected = tuple(sorted(values, key=d.canonical_bytes)) if name in {"fills", "fee_assessments", "slippage_decisions"} else values
        _equal(expected, raw[name], "final collection " + name)
    head = d.canonical_sha256(tuple(a.artifact_hash for a in sorted((a for a in artifacts if a.role != "economic_attempt_witness"),
        key=lambda a:(a.occurred_at,a.source_event_id,a.role))))
    if (witness["checkpoint_head"] != head or witness["final_journal_hash"] != journal.journal_hash
            or witness["final_ledger_hash"] != ledger.state_hash or witness["run_end_report_hash"] != d.canonical_sha256(raw["run_end_report"])):
        raise d.ArtifactIntegrityError("economic final head/hash mismatch")
    cursor = case.timeline.open_cursor(batch_size=64)
    while not cursor.window_complete:
        batch = case.timeline.read_batch(cursor)
        if batch.batch is None:
            raise d.ArtifactIntegrityError("economic cold timeline source unavailable")
        cursor = batch.batch.next_cursor
    _equal(cursor, witness["cursor"], "actual completed timeline cursor")
    run_end = RunEndCoordinator().coordinate(RunEndEvidence(case.timeline.window, cursor, ending.economic_projection.snapshot,
        ending.order_streams, ending.reservations, ending.settlement_book.project(), ()), MarkToMarketCloseoutPolicy())
    _equal(run_end.report, raw["run_end_report"], "native run-end report")
    hashes = {a.artifact_hash:a for a in artifacts}
    if len(trace.entries) != len(artifacts) or len(hashes) != len(artifacts):
        raise d.ArtifactIntegrityError("economic trace/artifact exact cover mismatch")
    for entry in trace.entries:
        artifact = hashes.get(entry.evidence_hash)
        if artifact is None or entry.stage is not EngineStage.FINANCIAL_EVENT or entry.instant != artifact.occurred_at or entry.subject_id != artifact.source_event_id:
            raise d.ArtifactIntegrityError("economic trace source/hash mismatch")


def _base_failure_v1(raw):
    raw = _map(raw, {"type", "code", "case_hash", "trace_hash", "subject_keys", "evidence_hashes", "termination"})
    if raw["type"] != "engine_failure" or raw["termination"] is not None:
        raise d.ArtifactIntegrityError("economic base failure type/termination mismatch")
    result = EngineFailure(EngineFailureCode(raw["code"]), raw["case_hash"], raw["trace_hash"],
        tuple(_seq(raw["subject_keys"])), tuple(_seq(raw["evidence_hashes"])))
    _equal(result, raw, "base native failure")
    return result


def _prove_native_financial_failure_v1(*,case,bound,ending,admissions,diagnostic):
    claim=_map(diagnostic["original_claim"],{"source","steps","failed_step"})
    _equal(ending,claim["source"],"native failure original committed financial source")
    raw_steps=_seq(claim["steps"])
    selected,steps=[],[]
    working=sorted((s for s in ending.order_streams if s.state is not None and s.state.status in {d.OrderStatus.ACCEPTED,d.OrderStatus.ACTIVE}),
        key=lambda s:(s.order.intent.side is d.OrderSide.BUY,str(s.order.intent.instrument_id),s.order.order_id.value))
    for ordinal,stream in enumerate(working,1):
        matching=tuple((i,event) for i,event in enumerate(bound.openings) if event.event_time==ending.at.instant and event.instrument_id==stream.order.intent.instrument_id)
        if len(matching)!=1:
            raise d.ArtifactIntegrityError("native failure provisional step lacks original source opening")
        opening_index,event=matching[0];observation=BarOpenObservation.from_event(event)
        if observation.kind is not BarOpenKind.REAL:
            continue
        term=next(t for t in bound.inputs.opening_terms if t.bar_event_id==event.event_id and t.side is stream.order.intent.side)
        admission=admissions[stream.order.order_id]
        quote,market,issues,fee,reason,extra_p,extra_f=_verify_economic_opening_inputs_v1(sources=ending,stream=stream,
            observation=observation,terms=term,admission=admission,budget_prefix=tuple(selected))
        if reason is not None:
            continue
        if len(steps)>=len(raw_steps):
            raise d.ArtifactIntegrityError("native failure omits eligible original provisional financial step")
        raw_step=_map(raw_steps[len(steps)],{"type","schema_version","opening","terminal_order","terms"})
        raw_open=_map(raw_step["opening"])
        fill=x._read_fill(raw_open["fill"])
        decision=quote.result
        expected_id=d.DomainId(d.DomainIdKind.FILL,d.DomainIdKind.FILL.prefix+"_"+d.canonical_sha256({
            "type":"cn_a_share_portfolio_economic_open_fill_identity","order_id":stream.order.order_id,
            "open_event_hash":event.event_hash,"economic_proof_hash":d.canonical_sha256(ending),"slippage_decision_id":decision.decision_id})[7:])
        if (fill.fill_id!=expected_id or fill.order_id!=stream.order.order_id or fill.quantity!=stream.order.intent.quantity
                or fill.instrument_id!=stream.order.intent.instrument_id or fill.account_id!=bound.inputs.scope.account_id
                or fill.side is not stream.order.intent.side or fill.reference_price!=observation.open_price or fill.price!=decision.execution_price
                or fill.execution_time!=event.event_time or fill.slippage_decision_id!=decision.decision_id
                or fill.slippage_model_key!=decision.component_ref.component_key or fill.slippage_calibration_id!=d.canonical_sha256(decision.calibration_ref)
                or fill.slippage_amount!=d.Money(decision.slippage_amount.units,decision.slippage_amount.scale,decision.slippage_amount.quote_currency)):
            raise d.ArtifactIntegrityError("native failure substitutes provisional original Fill claim")
        opening=_EconomicOpeningOutcomeV1(stream.order.order_id,observation.observation_hash,d.canonical_sha256(ending),
            d.canonical_sha256(admission),d.canonical_sha256(term),quote,market,issues,fee,NoEligibleBarAction.FULL_FILL,None,fill,
            _cent(extra_p),_cent(extra_f),tuple(o.order_id for o in selected))
        terminal=_expected_terminal_stream_v1(case=case,stream=stream,opening=opening,signal_index=admission.signal_index,
            opening_index=opening_index,ordinal=ordinal,when=event.event_time)
        step=_EconomicFinancialStepV1(opening,terminal,term)
        _equal(step,raw_step,"native failure complete provisional original step")
        selected.append(opening);steps.append(step)
    if len(steps)!=len(raw_steps):
        raise d.ArtifactIntegrityError("native failure invents provisional financial batch step")
    ledger=t.GenericLedger(bound.inputs.scope.ledger_schema).project(ending.journal)
    accounting,fees=t.CashInstrumentAccounting(),t.FeeAssessmentEngine()
    def check(operation,kwargs,outcome,code,step):
        if operation!=diagnostic["operation"] or d.canonical_bytes(step)!=d.canonical_bytes(claim["failed_step"]):
            if outcome.result is None:
                raise d.ArtifactIntegrityError("native failure substitutes original failed operation/step")
            return None
        _equal(kwargs,diagnostic["native_inputs"],"native failure exact source-derived call arguments")
        _equal(outcome,diagnostic["native_outcome"],"native failure complete actual rejected outcome")
        if outcome.result is not None or outcome.failure is None or diagnostic["engine_failure_code"]!=code.value:
            raise d.ArtifactIntegrityError("native failure derivation actually succeeds or classification differs")
        return outcome
    for ordinal,step in enumerate(steps,1):
        fill=step.opening.fill
        cash=d.CashBalanceKey(fill.account_id,fill.venue_id,d.CurrencyId("CNY"))
        position=d.PositionBalanceKey(fill.account_id,fill.venue_id,fill.instrument_id)
        lots=next((p.lots for p in ledger.position_balances if p.key==position),())
        def at(rank,code):
            return d.SimulationInstant(fill.execution_time,d.TimelinePhase(rank,code),d.SourceSequence(ordinal))
        kwargs=dict(fill=fill,cash_key=cash,position_key=position,open_lots=lots,cost_basis_policy=bound.inputs.cost_basis_policy,
            notional_quantization=bound.inputs.notional_quantization,journal_entry_id=_id(d.DomainIdKind.JOURNAL,"fill",step.opening.outcome_hash),recorded_at=at(70,"accounting"))
        booked=accounting.book_fill(**kwargs)
        actual=check("fill_accounting",kwargs,booked,EngineFailureCode.ACCOUNTING_FAILURE,step)
        if actual is not None:return actual
        kwargs=dict(basis=t.FeeAssessmentBasisEvidence.for_fill(fill),rule_set=step.final_fill_rules,
            fee_assessment_id=_id(d.DomainIdKind.FEE,"fill_fee",step.opening.outcome_hash),assessment_time=fill.execution_time)
        assessed=fees.assess(**kwargs)
        actual=check("fill_fee_assessment",kwargs,assessed,EngineFailureCode.FEE_ASSESSMENT_FAILURE,step)
        if actual is not None:return actual
        kwargs=dict(assessment=assessed.result.assessment,related_fill=fill,cash_key=cash,open_lots=booked.result.open_lots,
            cost_basis_policy=bound.inputs.cost_basis_policy,journal_entry_id=_id(d.DomainIdKind.JOURNAL,"fill_fee",step.opening.outcome_hash),recorded_at=at(90,"fees"))
        charged=accounting.charge_fee(**kwargs)
        actual=check("fill_fee_accounting",kwargs,charged,EngineFailureCode.FEE_ACCOUNTING_FAILURE,step)
        if actual is not None:return actual
        kwargs=dict(basis=t.FeeAssessmentBasisEvidence.for_order(step.terminal_order),rule_set=step.final_order_rules,
            fee_assessment_id=_id(d.DomainIdKind.FEE,"order_fee",step.opening.outcome_hash),assessment_time=fill.execution_time)
        order_fee=fees.assess(**kwargs)
        actual=check("order_fee_assessment",kwargs,order_fee,EngineFailureCode.FEE_ASSESSMENT_FAILURE,step)
        if actual is not None:return actual
        kwargs=dict(assessment=order_fee.result.assessment,order_stream=step.terminal_order,cash_key=cash,open_lots=charged.result.open_lots,
            cost_basis_policy=bound.inputs.cost_basis_policy,journal_entry_id=_id(d.DomainIdKind.JOURNAL,"order_fee",step.opening.outcome_hash),recorded_at=at(91,"order_fee"))
        charged_order=accounting.charge_order_fee(**kwargs)
        actual=check("order_fee_accounting",kwargs,charged_order,EngineFailureCode.FEE_ACCOUNTING_FAILURE,step)
        if actual is not None:return actual
    raise d.ArtifactIntegrityError("native failure has no source-derived rejected financial operation")


def _prove_native_failure_v1(*,case,bound,ending,admissions,pending,diagnostic,failed_id,failed_at):
    from .cn_a_share_portfolio_economic_native_state_v1 import _EconomicNativeFailureV1
    operation=diagnostic["operation"]
    financial={"fill_accounting","fill_fee_assessment","fill_fee_accounting","order_fee_assessment","order_fee_accounting"}
    if operation in financial:
        bars=tuple(event for event in bound.openings if event.event_time==ending.at.instant)
        if (not bars or failed_at!=_at(ending.at.instant,97) or ending.at!=_at(ending.at.instant,67)
                or failed_id!=bars[0].event_id):
            raise d.ArtifactIntegrityError("native financial failure lacks exact first-bar committed67/provisional97 boundary")
        return _prove_native_financial_failure_v1(case=case,bound=bound,ending=ending,admissions=admissions,diagnostic=diagnostic)
    signal_ops={"economic_equity_allocation","target_decode","target_validation","decision_batch_collection","portfolio_allocation","portfolio_risk","quantity_lattice","position_sizing"}
    if operation in signal_ops:
        claim=_map(diagnostic["original_claim"],{"source","event"})
        event=next((event for event in case.target_stream.events if event.event_id==failed_id),None)
        v2 = type(bound.inputs) is CnASharePortfolioEconomicDevelopmentInputsV2
        expected_at = _economic_activation_at_v2(bound.inputs) if v2 else (
            None if event is None else d.SimulationInstant(event.event_time,event.phase,event.source_sequence))
        if (event is None or failed_at != expected_at or ending.at != failed_at
                or (v2 and operation in {"target_decode", "target_validation", "decision_batch_collection"})):
            raise d.ArtifactIntegrityError("native signal failure has no exact actual source event/clock")
        _equal(ending,claim["source"],"native signal original source")
        _equal(event,claim["event"],"native signal original event")
        try:
            if v2:
                _economic_activation_signal_v2(sources=ending, event=event)
            else:
                _economic_signal_target_v1(sources=ending,event=event)
        except _EconomicNativeFailureV1 as rejected:
            actual=rejected
        else:
            raise d.ArtifactIntegrityError("native signal failure derivation actually succeeds")
    elif operation in {"capability_validation","order_translation","fee_reservation"}:
        bars=tuple((i,event) for i,event in enumerate(bound.openings) if event.event_time==ending.at.instant)
        if (not bars or failed_at!=_at(ending.at.instant,49) or ending.at!=failed_at or failed_id!=bars[0][1].event_id):
            raise d.ArtifactIntegrityError("native opening failure lacks exact first-bar49 funding frontier")
        by_instrument={event.instrument_id:event for _,event in bars}
        candidates=[]
        for _,order in pending.values():
            event=by_instrument[order.intent.instrument_id]
            if order.created_at.instant<ending.at.instant and BarOpenObservation.from_event(event).kind is BarOpenKind.REAL:
                term=next(t for t in bound.inputs.opening_terms if t.bar_event_id==event.event_id and t.side is order.intent.side)
                candidates.append((order,BarOpenObservation.from_event(event),term))
        for stream in ending.order_streams:
            event=by_instrument[stream.order.intent.instrument_id]
            if stream.state is not None and stream.state.status in {d.OrderStatus.ACCEPTED,d.OrderStatus.ACTIVE} and BarOpenObservation.from_event(event).kind is BarOpenKind.REAL:
                term=next(t for t in bound.inputs.opening_terms if t.bar_event_id==event.event_id and t.side is stream.order.intent.side)
                candidates.append((stream.order,BarOpenObservation.from_event(event),term))
        candidates.sort(key=lambda row:(row[0].intent.side is d.OrderSide.BUY,str(row[0].intent.instrument_id),row[0].order_id.value))
        actual=None
        for order,observation,term in candidates:
            try:
                _economic_evaluation_v1(order,observation,term)
            except _EconomicNativeFailureV1 as rejected:
                actual=rejected
                break
        if actual is None:
            raise d.ArtifactIntegrityError("native opening failure derivation actually succeeds")
        _equal(actual.original_claim,diagnostic["original_claim"],"native deterministic FIRST failing candidate/call frontier")
    elif operation=="timeline_read":
        _equal({"case_hash":case.case_hash},diagnostic["original_claim"],"native timeline original case")
        if ending.journal!=case.financial_state.journal or pending or admissions:
            raise d.ArtifactIntegrityError("native timeline failure cannot follow financial execution")
        cursor=case.timeline.open_cursor(batch_size=64)
        rejected=None
        while not cursor.window_complete:
            read=case.timeline.read_batch(cursor)
            if read.batch is None:
                _equal({"cursor":cursor,"batch_size":64},diagnostic["native_inputs"],"actual failing timeline cursor")
                rejected=read.failure
                break
            cursor=read.batch.next_cursor
        if rejected is None or diagnostic["engine_failure_code"]!=EngineFailureCode.TIMELINE_FAILURE.value:
            raise d.ArtifactIntegrityError("native timeline failure derivation actually succeeds or classification differs")
        _equal(rejected,diagnostic["native_outcome"],"actual native timeline failure")
        return rejected
    elif operation=="run_end":
        _equal({"source":ending},diagnostic["original_claim"],"native run-end original source")
        cursor=case.timeline.open_cursor(batch_size=64)
        while not cursor.window_complete:
            read=case.timeline.read_batch(cursor)
            if read.batch is None:raise d.ArtifactIntegrityError("run-end failure has incomplete timeline")
            cursor=read.batch.next_cursor
        evidence=RunEndEvidence(case.timeline.window,cursor,ending.economic_projection.snapshot,ending.order_streams,
            ending.reservations,ending.settlement_book.project(),())
        _equal({"evidence":evidence,"policy":MarkToMarketCloseoutPolicy().component_ref},diagnostic["native_inputs"],"native run-end actual arguments")
        rejected=RunEndCoordinator().coordinate(evidence,MarkToMarketCloseoutPolicy()).termination
        if rejected is None or diagnostic["engine_failure_code"]!=EngineFailureCode.RUN_END_TERMINATED.value:
            raise d.ArtifactIntegrityError("native run-end failure derivation actually succeeds or classification differs")
        _equal(rejected,diagnostic["native_outcome"],"actual native run-end termination")
        return rejected
    elif operation=="economic_projection":
        from .cn_a_share_portfolio_economic_native_state_v1 import _economic_marks_at_v1
        from crypto_quant_trading import CurrencyValuationGraph
        marks=_economic_marks_at_v1(bound.inputs,failed_at)
        _equal({"marks":marks},diagnostic["original_claim"],"native failed projection retained marks")
        book=_advance_economic_settlement_v1(case=case,inputs=bound.inputs,journal=ending.journal,book=ending.settlement_book,consumer=failed_at)
        request=e.CnASharePortfolioEconomicProjectionInputsV1(ending.journal,bound.inputs.scope.ledger_schema,book,
            ending.order_streams,ending.reservation_schedules,ending.market_rules,bound.inputs.scope.instrument_catalog,marks.marks,
            CurrencyValuationGraph(failed_at.instant,d.PricePurpose.VALUATION,()),bound.inputs.notional_quantization,
            replace(ending.dividend_state,as_of=failed_at),failed_at)
        _equal({"inputs":request},diagnostic["native_inputs"],"native failed projection source; provisional financial projections require separate verified claims")
        rejected=e.project_cn_a_share_portfolio_economic_state_v1(request).failure
        if rejected is None or diagnostic["engine_failure_code"]!=EngineFailureCode.SNAPSHOT_PROJECTION_FAILURE.value:
            raise d.ArtifactIntegrityError("native projection failure derivation actually succeeds or classification differs")
        _equal(rejected,diagnostic["native_outcome"],"actual native projection failure")
        return rejected
    else:
        raise d.ArtifactIntegrityError("unknown native failure operation: "+str(operation))
    if actual.operation!=operation or actual.code.value!=diagnostic["engine_failure_code"]:
        raise d.ArtifactIntegrityError("native failure operation/classification substitution")
    wire_inputs = (_economic_native_failure_inputs_v2(operation, actual.native_inputs)
        if type(bound.inputs) is CnASharePortfolioEconomicDevelopmentInputsV2 else actual.native_inputs)
    _equal(wire_inputs,diagnostic["native_inputs"],"native original typed arguments")
    _equal(actual.evidence,diagnostic["native_outcome"],"native complete rejected outcome")
    return actual.evidence


def _verify_economic_failure_context_v1(*, case, reader, failure):
    if type(case) is not _ResolvedProfilePortfolioCaseV2 or type(failure) is not EngineFailure or failure.economic_failure_context is None:
        raise TypeError("economic failure requires exact case/failure and complete context")
    envelope = failure.economic_failure_context
    if envelope.artifact_type != "cn_a_share_portfolio_economic_failure_context" or envelope.schema_version != 1:
        raise d.ArtifactIntegrityError("economic failure context envelope mismatch")
    raw = _raw(envelope.payload)
    expected = {"type", "schema_version", "case_hash", "definition_hash", "target_stream_digest", "failed_event_id", "failed_at",
        "base_failure", "prefix_checkpoint", "journal", "order_streams", "reservation_schedules", "financial_artifacts", "trace",
        "pending_intentions", "admissions", "journal_entry_ids", "used_identity_keys", "ca_transition_inputs", "ca_failure",
        "semantic_spec", "identity_manifest", "source_refs", "timeline_stream_keys"}
    _map(raw, expected)
    if (raw["type"] != "cn_a_share_portfolio_economic_failure_context" or type(raw["schema_version"]) is not int or raw["schema_version"] != 1
            or raw["case_hash"] != case.case_hash or raw["definition_hash"] != d.canonical_sha256(case.execution_case_plan.definition)
            or raw["target_stream_digest"] != case.target_stream.target_stream_digest):
        raise d.ArtifactIntegrityError("economic failed case/definition/target mismatch")
    _equal(case.semantic_spec, raw["semantic_spec"], "failed semantic spec")
    _equal(case.identity_manifest, raw["identity_manifest"], "failed identity manifest")
    _equal(case.execution_case_plan.source_refs, raw["source_refs"], "failed retained source roles")
    _equal(case.timeline.stream_keys, raw["timeline_stream_keys"], "failed timeline streams")
    bound = _bind_economic_portfolio_sources_v1(case, reader)
    _equal(bound.journal_entry_ids, raw["journal_entry_ids"], "failed sealed journal mapping including unused slots")
    journal = x._read_economic_journal_v1(raw["journal"])
    streams = tuple(x._read_order_event_stream(v) for v in _seq(raw["order_streams"]))
    schedules = tuple(x._read_reservation_schedule(v) for v in _seq(raw["reservation_schedules"]))
    artifacts = tuple(_artifact(v) for v in _seq(raw["financial_artifacts"]))
    if any(a.role == "economic_attempt_witness" for a in artifacts):
        raise d.ArtifactIntegrityError("failed prefix cannot claim completed witness")
    trace = _trace(raw["trace"])
    base = _base_failure_v1(raw["base_failure"])
    if base.case_hash != case.case_hash or base.trace_hash != trace.trace_hash:
        raise d.ArtifactIntegrityError("economic failed trace/base binding mismatch")
    diagnostics=tuple(a for a in artifacts if a.role=="economic_native_failure")
    committed_artifacts=tuple(a for a in artifacts if a.role!="economic_native_failure")
    if len(diagnostics)!=(0 if raw["ca_failure"] is not None else 1):
        raise d.ArtifactIntegrityError("native failure diagnostic exact cover mismatch")
    ending, signals, fills, fees, slips, counts, admissions, pending, intentions = _verify_economic_facts_v1(case=case, reader=reader,
        journal=journal, final_streams=streams, final_schedules=schedules, artifacts=committed_artifacts, trace=trace,
        admission_rows=_seq(raw["admissions"]), final_pending=raw["pending_intentions"], final_checkpoint=raw["prefix_checkpoint"])
    failed_at = x._read_simulation_instant(raw["failed_at"])
    if ending.at > failed_at or any(a.occurred_at > failed_at for a in artifacts):
        raise d.ArtifactIntegrityError("economic failure contains future committed facts")
    if len(trace.entries) != len(artifacts) + 1:
        raise d.ArtifactIntegrityError("economic failed trace prefix count mismatch")
    by_hash = {a.artifact_hash:a for a in artifacts}
    for entry in trace.entries[:-1]:
        artifact = by_hash.get(entry.evidence_hash)
        if artifact is None or entry.instant != artifact.occurred_at or entry.subject_id != artifact.source_event_id or entry.stage is not EngineStage.FINANCIAL_EVENT:
            raise d.ArtifactIntegrityError("economic failed financial trace mismatch")
    last = trace.entries[-1]
    if last.instant != failed_at or last.subject_id != raw["failed_event_id"] or last.evidence_hash not in base.evidence_hashes:
        raise d.ArtifactIntegrityError("economic native failure trace cause mismatch")
    _equal(_used_identity_keys_v1(case, journal, {s.order.order_id:s for s in streams}, pending, intentions), raw["used_identity_keys"], "failed actually-used identity keys")
    if (raw["ca_transition_inputs"] is None) != (raw["ca_failure"] is None):
        raise d.ArtifactIntegrityError("economic C-A input/failure pair is incomplete")
    if raw["ca_failure"] is not None:
        request = _read_cn_a_share_cash_dividend_transition_inputs_v1(raw["ca_transition_inputs"])
        rejected = _read_cn_a_share_cash_dividend_transition_failure_v1(raw["ca_failure"])
        if (base.code is not EngineFailureCode.FINANCIAL_DISPATCH_FAILURE
                or rejected.code is not e.CnAShareCashDividendTransitionFailureCodeV1.TAX_CASH_SHORTFALL
                or request.kind != "TAX" or request.history.as_of != failed_at):
            raise d.ArtifactIntegrityError("economic C-A failure code/event mismatch")
        h = request.history
        _equal(h.journal, ending.journal, "failed C-A original journal")
        _equal(h.dividend_state, ending.dividend_state, "failed C-A original state")
        _equal(_book_body(h.settlement_book), _book_body(ending.settlement_book), "failed C-A original Book")
        _equal(h.order_streams, ending.order_streams, "failed C-A original Orders")
        _equal(h.reservation_schedules, ending.reservation_schedules, "failed C-A original schedules")
        _equal(h.action_set, bound.inputs.dividend_actions, "failed C-A retained ActionSet")
        _equal(h.journal_entry_ids, bound.journal_entry_ids, "failed C-A sealed IDs")
        matches = tuple(row for row in _economic_events_v1(bound.inputs) if row[3] == raw["failed_event_id"])
        if len(matches) != 1 or matches[0][0] != failed_at or matches[0][1] != "TAX" or matches[0][2].action_id != request.action_id or matches[0][2].instrument_id != request.instrument_id:
            raise d.ArtifactIntegrityError("economic failed C-A coordinate mismatch")
        claim = next(c for c in ending.dividend_state.claims if c.action_id == request.action_id and c.instrument_id == request.instrument_id)
        available = next(r.native_available.units for r in ending.economic_projection.cash_rows if r.key.venue_id == request.instrument_id.venue)
        if claim.tax_assessed.units - claim.tax_settled.units <= available:
            raise d.ArtifactIntegrityError("economic failed tax claim has sufficient native cash")
        # Guaranteed failure branch: no candidate journal append is invoked.
        actual = e.transition_cn_a_share_cash_dividend_v1(request)
        _equal(actual.failure, rejected, "actual original native TAX shortfall")
        if actual.transition is not None:
            raise d.ArtifactIntegrityError("economic failed TAX was actually successful")
        native_cause=actual.failure
    else:
        diagnostic=diagnostics[0]
        diagnostic_version = 2 if type(bound.inputs) is CnASharePortfolioEconomicDevelopmentInputsV2 else 1
        if (diagnostic.source_event_id!=raw["failed_event_id"] or diagnostic.occurred_at!=failed_at
                or diagnostic.payload.artifact_type!="cn_a_share_portfolio_economic_native_failure" or diagnostic.payload.schema_version!=diagnostic_version
                or trace.entries[-2].evidence_hash!=diagnostic.artifact_hash):
            raise d.ArtifactIntegrityError("native failure terminal diagnostic source/trace/envelope mismatch")
        prefix, component = _economic_native_finance_identity_v1(bound.inputs)
        if (diagnostic.component_key!=prefix+".native-finance" or diagnostic.component_version!=1
                or diagnostic.component_digest!=component or diagnostic.input_hash!=bound.inputs._definition_source_hash):
            raise d.ArtifactIntegrityError("native failure diagnostic component binding mismatch")
        value=_map(diagnostic.payload.payload,{"type","schema_version","operation","engine_failure_code","original_claim","native_inputs","native_outcome"})
        if (value["type"]!="cn_a_share_portfolio_economic_native_failure" or type(value["schema_version"]) is not int
                or value["schema_version"]!=diagnostic_version or value["engine_failure_code"]!=base.code.value):
            raise d.ArtifactIntegrityError("native failure diagnostic type/code mismatch")
        native_cause=_prove_native_failure_v1(case=case,bound=bound,ending=ending,admissions=admissions,pending=pending,
            diagnostic=value,failed_id=raw["failed_event_id"],failed_at=failed_at)
    cause_hash=d.canonical_sha256(native_cause)
    reason=native_cause.failure if hasattr(native_cause,"failure") and native_cause.failure is not None else native_cause
    subjects={raw["failed_event_id"],base.code.value}
    if hasattr(reason,"code"):subjects.add(reason.code.value)
    if base.evidence_hashes!=(cause_hash,) or last.evidence_hash!=cause_hash or set(base.subject_keys)!=subjects:
        raise d.ArtifactIntegrityError("native failure cause/code/subjects do not bind complete actual outcome")
    return None


def _read_economic_failure_v1(*, case, reader, value):
    raw = _map(_raw(value), {"type", "schema_version", "code", "case_hash", "trace_hash", "subject_keys", "evidence_hashes", "termination", "economic_failure_context"})
    if raw["type"] != "engine_failure" or type(raw["schema_version"]) is not int or raw["schema_version"] != 2 or raw["termination"] is not None:
        raise d.ArtifactIntegrityError("economic outer failure requires exact schema2")
    result = EngineFailure(EngineFailureCode(raw["code"]), raw["case_hash"], raw["trace_hash"], tuple(_seq(raw["subject_keys"])),
        tuple(_seq(raw["evidence_hashes"])), economic_failure_context=_envelope(raw["economic_failure_context"]))
    _equal(result, raw, "outer failure canonical reconstruction")
    _verify_economic_failure_context_v1(case=case, reader=reader, failure=result)
    return result


from .cn_a_share_portfolio_economic_case_v1 import _read_exact_economic_source_v1, _native_initial_economic_financial_state_v1
from .cn_a_share_portfolio_economic_definition_v1 import _read_economic_definition_v1
from .cn_a_share_portfolio_economic_values_v1 import _read_cn_a_share_cash_dividend_action_set_v1
from .cn_a_share_portfolio_economic_prepare_v1 import _registry
from .composition import _compose_profile_portfolio_economic_execution_case
from .profile_portfolio_execution import _ProfilePortfolioExecutionPlanV2
from .resolution import BacktestRequest, ProfileResolver, StrategyFamily, RequestedResultGrade
from .target_repository import BacktestTargetStreamRef, BacktestTargetStreamRepository
from .timeline import TimelineWindow


def _entry_ref(raw):
    return d.ArtifactRef(raw["artifact_type"], raw["schema_version"], raw["content_hash"])


def _request_v1(raw, market_reader):
    raw = _map(raw)
    _equal(market_reader.bundle_ref, raw["market_bundle_ref"], "explicit cold MarketBundle reader")
    window = raw["timeline_window"]
    request = BacktestRequest(raw["schema_version"], raw["experiment_id"],
        TimelineWindow(x._read_utc(window["data_start"]), x._read_utc(window["trading_start"]), x._read_utc(window["end_exclusive"])),
        raw["market_semantics_profile_key"], raw["simulation_profile_key"], raw["execution_account_profile_key"],
        raw["execution_account_id"], x._read_currency(raw["reporting_currency"]), market_reader.bundle_ref,
        raw["target_stream_digest"], raw["execution_case_semantic_hash"], raw["master_random_seed"], raw["build_artifact_manifest_hash"],
        StrategyFamily(raw["strategy_family"]), raw["engine_kind"], RequestedResultGrade(raw["result_grade_requested"]))
    _equal(request, raw, "retained native request")
    keys = (request.market_semantics_profile_key, request.simulation_profile_key, request.execution_account_profile_key)
    triples = tuple(tuple(prefix + suffix for suffix in (".market", ".simulation", ".account"))
        for prefix in (_PREFIX, "cn.portfolio.shared-cny.economic.development.v2"))
    if keys not in triples or request.result_grade_requested is not RequestedResultGrade.DEVELOPMENT:
        raise d.ArtifactIntegrityError("economic retained request profile/grade mismatch")
    return request


def _bootstrap_economic_case_v1(*, reader, market_reader, resolved_raw, binding, build_artifact_manifest):
    if market_reader is None:
        raise ValueError("economic evidence requires explicit matching MarketBundleReader")
    binding = _map(binding, {"type", "schema_version", "source_refs", "semantic_spec", "identity_manifest", "timeline_stream_keys"})
    if binding["type"] != "cn_a_share_portfolio_economic_completed_sources" or type(binding["schema_version"]) is not int or binding["schema_version"] != 1:
        raise d.ArtifactIntegrityError("economic source binding version mismatch")
    refs = tuple((row[0], _artifact_ref(row[1])) for row in _seq(binding["source_refs"]))
    definition_version = next((ref.schema_version for key, ref in refs if key == "definition"), None)
    expected = (("cash_dividend_action_set", "cn_a_share_cash_dividend_action_set", 1),
        ("definition", "backtest_profile_portfolio_definition", definition_version), ("target_stream", "backtest_target_stream", 1))
    if definition_version not in (2, 3, 4) or tuple((key, ref.artifact_type, ref.schema_version) for key, ref in refs) != expected:
        raise d.ArtifactIntegrityError("economic source binding role/type/version mismatch")
    by_role = dict(refs)
    action_envelope = _read_exact_economic_source_v1(reader, by_role["cash_dividend_action_set"])
    actions = _read_cn_a_share_cash_dividend_action_set_v1(action_envelope.payload)
    definition = _read_exact_economic_source_v1(reader, by_role["definition"])
    target_ref = BacktestTargetStreamRef.from_artifact_ref(by_role["target_stream"])
    target = BacktestTargetStreamRepository(reader=reader).load(target_ref).target_stream
    inputs = (_read_economic_definition_v2(definition, target_ref, actions, target) if definition.schema_version == 3
        else _read_economic_definition_v1(definition, target_ref, actions, source_reader=reader))
    financial, state, projection = _native_initial_economic_financial_state_v1(inputs)
    plan = _ProfilePortfolioExecutionPlanV2(definition, financial, state, projection, refs)
    resolved_raw = _map(resolved_raw)
    request = _request_v1(resolved_raw["request"], market_reader)
    manifest = x._read_build_manifest(_raw(build_artifact_manifest))
    from .cn_a_share_portfolio_economic_prepare_v2 import _registry_v2
    spec = x._read_semantic_spec(binding["semantic_spec"])
    _economic_opening_proof_version_v1(definition=definition, spec=spec)
    registry = (_registry_v2(inputs, spec_version=spec.spec_version)
        if type(inputs) is CnASharePortfolioEconomicDevelopmentInputsV2
        else _registry(inputs, spec_version=spec.spec_version))
    del inputs
    resolved = ProfileResolver().resolve(request=request, registry=registry, market_bundle_manifest=market_reader.manifest,
        build_artifact_manifest=manifest).resolved
    if resolved is None:
        raise d.ArtifactIntegrityError("economic original retained request no longer resolves")
    _equal(resolved, resolved_raw, "original fixed-registry resolved request/cohort")
    case = _compose_profile_portfolio_economic_execution_case(resolved_request=resolved, market_reader=market_reader,
        semantic_spec=spec, target_stream=target, timeline_stream_keys=tuple(_seq(binding["timeline_stream_keys"])),
        timeline_batch_size=64, execution_case_plan=plan)
    _equal(case.identity_manifest, binding["identity_manifest"], "original sealed identity manifest")
    expected_input = x._materialize_execution_input_bundle_v9(resolved_request=resolved, execution_case=case)
    candidate_ref = d.ArtifactRef.from_envelope(expected_input)
    actual = _read_exact_economic_source_v1(reader, candidate_ref)
    _equal(expected_input, actual, "ACTUAL retained input9 complete envelope")
    request_wrapper = x.BacktestExecutionRequest(9, request, candidate_ref)
    decoded, failure = x._read_execution_inputs_v9_from_snapshot(reader, request_wrapper)
    if failure is not None or type(decoded) is not x._DecodedExecutionInputBundleV9 or decoded.semantic_run_id != resolved.semantic_run_id:
        raise d.ArtifactIntegrityError("actual retained input9 hydration/binding failed")
    _bind_economic_portfolio_sources_v1(case, reader)
    return resolved, case, candidate_ref, by_role


def _completed_children_v1(reader, publication_ref):
    root = _read_exact_economic_source_v1(reader, publication_ref.artifact_ref)
    result_entry = next(row for row in _seq(root.payload["artifacts"]) if row["relative_path"] == "result.json")
    completed = _read_exact_economic_source_v1(reader, _entry_ref(result_entry))
    evidence_ref = _artifact_ref(completed.payload["canonical_evidence_manifest_ref"])
    evidence = _read_exact_economic_source_v1(reader, evidence_ref)
    engine_entry = next(row for row in _seq(evidence.payload["artifacts"]) if row["role"] == "engine_execution_result")
    engine_ref = _entry_ref(engine_entry)
    engine = _read_exact_economic_source_v1(reader, engine_ref)
    return completed, evidence, engine_ref, engine


def _load_verified_economic_completed_v1(*, reader, publication_ref, market_reader, structural=None):
    from .evidence_repository import BacktestEvidenceRepository
    if structural is None:
        structural = BacktestEvidenceRepository(reader=reader)._load_completed_structural_v1(publication_ref)
    completed, evidence, engine_ref, engine = _completed_children_v1(reader, publication_ref)
    witnesses = tuple(row for row in _seq(engine.payload["financial_artifacts"]) if row["role"] == "economic_attempt_witness")
    if len(witnesses) != 1:
        raise d.ArtifactIntegrityError("completed economic result has no unique source witness")
    envelope = _envelope(witnesses[0]["payload"])
    outer = _map(envelope.payload, {"type", "schema_version", "economic_witness", "economic_witness_hash", "source_binding"})
    if envelope.schema_version != 2 or type(outer["schema_version"]) is not int or outer["schema_version"] != 2 or outer["economic_witness_hash"] != d.canonical_sha256(outer["economic_witness"]):
        raise d.ArtifactIntegrityError("economic completed source witness requires exact v2")
    build_entry = next(row for row in _seq(evidence.payload["artifacts"]) if row["role"] == "build_artifact_manifest")
    retained_build = _read_exact_economic_source_v1(reader, _entry_ref(build_entry))
    resolved, case, actual_ref, refs = _bootstrap_economic_case_v1(reader=reader, market_reader=market_reader,
        resolved_raw=completed.payload["resolved_request"], binding=outer["source_binding"], build_artifact_manifest=retained_build.payload)
    context = completed.payload["engine_execution_context"]
    if (context["case_hash"] != case.case_hash or context["semantic_spec_hash"] != case.semantic_spec_hash
            or context["identity_manifest_hash"] != d.canonical_sha256(case.identity_manifest)
            or structural.semantic_run_id != resolved.semantic_run_id):
        raise d.ArtifactIntegrityError("economic completed native context/seal mismatch")
    _equal(case.financial_state, context["financial_state"], "published original initial native state")
    _verify_economic_native_result_v1(case=case, reader=reader, result=engine.payload)
    return structural, case, actual_ref, engine_ref, engine, refs["definition"], refs["cash_dividend_action_set"], resolved


def _verify_economic_native_cached_v1(*, case, reader, publication_ref):
    from .publication_refs import BacktestCanonicalPublicationRef
    nominal = BacktestCanonicalPublicationRef.from_artifact_ref(publication_ref)
    verified = _load_verified_economic_completed_v1(reader=reader, publication_ref=nominal, market_reader=case.timeline.reader)
    original = verified[1]
    if original.case_hash != case.case_hash or original.semantic_spec != case.semantic_spec or original.identity_manifest != case.identity_manifest:
        raise d.ArtifactIntegrityError("economic cache is not the same sealed economy")


def _load_verified_economic_terminal_v1(*, reader, publication_ref, market_reader, report, attempt_record, status, build_artifact_manifest):
    from .evidence_repository import VerifiedTerminalPublication, TerminalStatus
    report = _map(report)
    issue = _map(report["issue"])
    failure_raw = _map(issue["source_evidence"])
    if failure_raw.get("schema_version") != 2 or failure_raw.get("economic_failure_context") is None:
        raise d.ArtifactIntegrityError("economic terminal lacks full EngineFailure@2")
    context = _envelope(failure_raw["economic_failure_context"]).payload
    binding = {"type": "cn_a_share_portfolio_economic_completed_sources", "schema_version": 1,
        **{name: context[name] for name in ("source_refs", "semantic_spec", "identity_manifest", "timeline_stream_keys")}}
    _, case, actual_ref, _ = _bootstrap_economic_case_v1(reader=reader, market_reader=market_reader,
        resolved_raw=report["resolved_request"], binding=binding, build_artifact_manifest=build_artifact_manifest)
    branch = attempt_record["failed_report"] if status == "FAILED" else attempt_record["blocked_report"]
    _equal(report, branch, "terminal report/attempt complete duplicate")
    failure = _read_economic_failure_v1(case=case, reader=reader, value=failure_raw)
    if issue["source_hash"] != failure.failure_hash or issue["code"] != failure.code.value:
        raise d.ArtifactIntegrityError("economic terminal native cause hash/code mismatch")
    return VerifiedTerminalPublication(TerminalStatus(status), publication_ref)
