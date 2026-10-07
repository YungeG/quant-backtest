"""Native observed-open/retry money proof for the standard DEVELOPMENT Engine.

Standing GTC Orders retain their ONE original reservation. Fresh observed fees
are not amendments: an atomic full-fill batch may use own-held plus genuinely
uncommitted cash, never another Order's hold or unsettled sale proceeds. Native
market/fee/slippage/accounting remain the only economic implementations.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from crypto_quant_domain import (
    AccountingEntryType, AccountingJournalEntry, CashBalanceKey, FeeAssessment, Fill, Money, Order, OrderEventType, OrderSide, OrderStatus,
    Scale, SimulationInstant, TimeInForce, canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal, FeeReservationEstimator, GenericLedger,
    LedgerState, MarketRuleApproval, MarketRuleEvaluator, MarketSettlementRules,
    OrderCapabilityValidator, OrderEventStream, OrderReservationSchedule,
    OrderRuleEvaluationInput, OrderTranslator, ResourceReservationBook,
    ResourceReservationProposal, ResourceReservationState, SettlementBook,
)
from crypto_quant_trading.profiles.cn_a_share.portfolio_order_plan_v1 import CnASharePortfolioOrderPlanV1
from crypto_quant_trading.profiles.cn_a_share.portfolio_sellability_v1 import (
    CnASharePortfolioSellabilitySnapshotV1, project_cn_a_share_portfolio_sellability_v1,
)
from crypto_quant_trading.profiles.cn_a_share.shared_cny_cash_v1 import (
    CnAShareSharedCnyCashSnapshotV1, project_cn_a_share_shared_cny_cash_v1,
)

from .cn_a_share_portfolio_standard_definition_v1 import (
    CnASharePortfolioOpeningTermsDevelopmentV1, CnASharePortfolioStandardDevelopmentInputsV1,
)
from .cn_a_share_portfolio_next_open_development_v1 import _native_cn_portfolio_zero_slippage_fill_v1
from .cn_a_share_portfolio_financial_development_v1 import _rule_ids
from .cn_a_share_portfolio_financial_core_v1 import book_native_cn_portfolio_financial_core_v1
from .cn_a_share_portfolio_settlement_development_v1 import _build_cn_a_share_portfolio_settlement_facts_v1
from .execution import BarOpenKind, BarOpenObservation, NoEligibleBarAction
from crypto_quant_trading.fees import FinalFeeRuleSource

_CENT = Scale(2)


@dataclass(frozen=True, slots=True)
class _StandardOpenSourcesV1:
    inputs: CnASharePortfolioStandardDevelopmentInputsV1
    journal: AccountingJournal
    settlement_book: SettlementBook
    order_streams: tuple[OrderEventStream, ...]
    reservation_schedules: tuple[OrderReservationSchedule, ...]
    market_rules: MarketSettlementRules
    at: SimulationInstant
    cash: CnAShareSharedCnyCashSnapshotV1 = field(init=False)
    sellability: CnASharePortfolioSellabilitySnapshotV1 = field(init=False)
    reservations: ResourceReservationState = field(init=False)
    available_by_venue: tuple[tuple[CashBalanceKey, Money], ...] = field(init=False)

    def __post_init__(self) -> None:
        if (type(self.inputs) is not CnASharePortfolioStandardDevelopmentInputsV1
                or type(self.journal) is not AccountingJournal
                or type(self.settlement_book) is not SettlementBook
                or type(self.market_rules) is not MarketSettlementRules
                or type(self.at) is not SimulationInstant
                or type(self.order_streams) is not tuple
                or any(type(s) is not OrderEventStream for s in self.order_streams)
                or type(self.reservation_schedules) is not tuple
                or any(type(s) is not OrderReservationSchedule for s in self.reservation_schedules)):
            raise TypeError("standard opening requires exact native full-clock source facts")
        scope = self.inputs.scope
        initial = self.inputs.initial_journal.entries
        if (self.journal.entries[:len(initial)] != initial
                or self.settlement_book.account_id != scope.account_id
                or self.market_rules.account_id != scope.account_id
                or any(e.account_id != scope.account_id or e.recorded_at > self.at for e in self.journal.entries)
                or any(e.occurred_at > self.at for e in self.settlement_book.events)
                or any(s.order.account_id != scope.account_id
                       or s.order.intent.instrument_id not in scope.instrument_ids or s.order.created_at > self.at
                       or s.state is None or s.state.updated_at > self.at for s in self.order_streams)):
            raise ValueError("standard opening source account, Journal prefix or full-clock mismatch")
        suffix = self.journal.entries[len(initial):]
        if any(e.entry_type not in {AccountingEntryType.FILL_BOOKED, AccountingEntryType.FEE_CHARGED,
                                   AccountingEntryType.CAPITAL_TRANSFERRED} for e in suffix):
            raise ValueError("standard runtime cannot create new capital or unrelated economic attribution")
        transfers: dict[tuple[str, ...], list[AccountingJournalEntry]] = {}
        for entry in suffix:
            if entry.entry_type is AccountingEntryType.CAPITAL_TRANSFERRED:
                transfers.setdefault(entry.source_ids, []).append(entry)
        for pair in transfers.values():
            changes = tuple(c for e in pair for c in e.balance_changes)
            if (len(pair) != 2 or len(changes) != 2
                    or {e.venue_id.value for e in pair} != {"xshg", "xshe"}
                    or pair[0].recorded_at.instant != pair[1].recorded_at.instant
                    or any(e.position_lot_changes or e.realized_pnl or e.fees or e.financing for e in pair)
                    or any(type(c.key) is not CashBalanceKey or type(c.value) is not Money
                           or c.value.currency != "CNY" or c.value.scale != _CENT for c in changes)
                    or changes[0].value.units == 0
                    or any(e.venue_id != c.key.venue_id for e in pair for c in e.balance_changes)
                    or changes[0].value.units + changes[1].value.units != 0):
                raise ValueError("standard funding must retain the WHOLE native equal-CNY two-leg pair")
        fills = tuple(r.fill for s in self.order_streams for r in s.records if r.fill is not None)
        entries = tuple(e for e in suffix if e.entry_type is AccountingEntryType.FILL_BOOKED)
        if len(fills) != len(entries) or len({f.fill_id for f in fills}) != len(fills):
            raise ValueError("standard current sources lost historical native Fill/Journal facts")
        for fill in fills:
            linked = tuple(e for e in entries if fill.fill_id.value in e.source_ids)
            obligations = tuple(ob for ob in self.settlement_book.obligations
                                if ob.obligation.source_fill_id == fill.fill_id)
            if (len(linked) != 1 or len(obligations) != 2
                    or linked[0].account_id != fill.account_id or linked[0].venue_id != fill.venue_id):
                raise ValueError("standard current sources lost native Fill/Journal/T+1 obligation cover")
        if {ob.obligation.source_fill_id for ob in self.settlement_book.obligations} != {f.fill_id for f in fills}:
            raise ValueError("standard current Book contains foreign or missing Fill sources")
        if fills:
            expected = _build_cn_a_share_portfolio_settlement_facts_v1(fills=fills,
                journal=self.journal, source_hash=canonical_sha256(fills), calendars=self.inputs.calendars).book
            if self.settlement_book.obligations != expected.obligations:
                raise ValueError("standard current Book differs from exact native T+1 amount/key/time resolution")
        cash = project_cn_a_share_shared_cny_cash_v1(journal=self.journal,
            ledger_schema=scope.ledger_schema, settlement_book=self.settlement_book,
            order_streams=self.order_streams, reservation_schedules=self.reservation_schedules,
            market_rules=self.market_rules, as_of=self.at.instant)
        sellability = project_cn_a_share_portfolio_sellability_v1(journal=self.journal,
            ledger_schema=scope.ledger_schema, settlement_book=self.settlement_book,
            order_streams=self.order_streams, reservation_schedules=self.reservation_schedules,
            market_rules=self.market_rules, as_of=self.at.instant)
        reservations = ResourceReservationBook(scope.account_id).project(
            self.order_streams, self.reservation_schedules)
        ledger = GenericLedger(scope.ledger_schema).project(self.journal)
        pending = self.settlement_book.project().pending_obligations
        available = []
        for registration in scope.ledger_schema.cash_registrations:
            key = registration.key
            if type(key) is not CashBalanceKey:
                raise ValueError("standard opening needs native venue cash keys")
            streams = tuple(s for s in self.order_streams if s.order.intent.instrument_id.venue == key.venue_id)
            ids = {s.order.order_id for s in streams}
            schedules = tuple(s for s in self.reservation_schedules if s.order_id in ids)
            held = ResourceReservationBook(scope.account_id).project(streams, schedules).totals
            units = (ledger.cash_amount(key).units
                - sum(p.value.units for p in pending if p.balance_key == key and isinstance(p.value, Money))
                - sum(m.units for m in (*held.cash, *held.fee_reserve)))
            if units < 0:
                raise ValueError("standard opening venue cash is overcommitted or unsettled")
            available.append((key, Money(units, _CENT, "CNY")))
        available.sort(key=lambda row: row[0].venue_id.value)
        if sum(value.units for _, value in available) != cash.spendable.units:
            raise ValueError("standard opening reservation venue ownership mismatch")
        object.__setattr__(self, "cash", cash)
        object.__setattr__(self, "sellability", sellability)
        object.__setattr__(self, "reservations", reservations)
        object.__setattr__(self, "available_by_venue", tuple(available))

    def to_canonical_dict(self) -> dict[str, object]:
        # Whole source facts live in the attempt graph. No transport ref leaks
        # into economic identities through the DTO's target/producer context.
        return {"type": "cn_a_share_portfolio_standard_open_sources", "schema_version": 1,
            "definition_hash": self.inputs._definition_source_hash, "at": self.at,
            "journal_hash": self.journal.journal_hash,
            "book_hash": self.settlement_book.book_hash, "cash": self.cash,
            "sellability": self.sellability, "reservations": self.reservations,
            "order_stream_hashes": tuple(s.stream_hash for s in self.order_streams),
            "schedule_hashes": tuple(s.schedule_hash for s in self.reservation_schedules),
            "market_rules_hash": self.market_rules.rules_hash,
            "available_by_venue": self.available_by_venue}


def _standard_market_fee_v1(order: Order, terms: CnASharePortfolioOpeningTermsDevelopmentV1
) -> tuple[MarketRuleApproval, ResourceReservationProposal]:
    """Derive both approvals through native evaluators from retained current sources."""
    capability = OrderCapabilityValidator().validate(order.intent, terms.capability_set).approval
    if capability is None:
        raise ValueError("standard opening native capability rejected")
    translated = OrderTranslator().translate(order, capability, terms.translation_mapping,
        order.created_at.instant)
    spec = translated.executable_spec
    if spec is None:
        raise ValueError("standard opening native translation rejected")
    decision = MarketRuleEvaluator().evaluate(
        OrderRuleEvaluationInput(spec, terms.opening_at, terms.notional_evidence), terms.rule_timeline)
    if decision.approval is None:
        raise ValueError("standard opening native market rule rejected: " + str(decision))
    fee = FeeReservationEstimator().estimate(decision.approval, terms.reservation_rules, terms.opening_at)
    if fee.proposal is None:
        raise ValueError("standard opening native fee estimate rejected: " + str(fee.failure))
    return decision.approval, fee.proposal


@dataclass(frozen=True, slots=True)
class _StandardCurrentOpenProofV1:
    plan: CnASharePortfolioOrderPlanV1
    plan_sources: _StandardOpenSourcesV1
    sources: _StandardOpenSourcesV1
    stream: OrderEventStream
    original_fee: ResourceReservationProposal
    observation: BarOpenObservation
    terms: CnASharePortfolioOpeningTermsDevelopmentV1
    market: MarketRuleApproval = field(init=False)
    fee: ResourceReservationProposal = field(init=False)

    def __post_init__(self) -> None:
        if (type(self.plan) is not CnASharePortfolioOrderPlanV1
                or type(self.plan_sources) is not _StandardOpenSourcesV1
                or type(self.sources) is not _StandardOpenSourcesV1
                or type(self.stream) is not OrderEventStream
                or type(self.original_fee) is not ResourceReservationProposal
                or type(self.observation) is not BarOpenObservation
                or type(self.terms) is not CnASharePortfolioOpeningTermsDevelopmentV1):
            raise TypeError("standard current-open proof needs exact native values")
        plan, origin, current = self.plan, self.plan_sources, self.sources
        order, state, event = self.stream.order, self.stream.state, self.observation.event
        if (origin.inputs._definition_source_hash != current.inputs._definition_source_hash
                or origin.market_rules != current.market_rules
                or origin.at > current.at
                or current.journal.entries[:len(origin.journal.entries)] != origin.journal.entries
                or current.settlement_book.events[:len(origin.settlement_book.events)] != origin.settlement_book.events
                or any(ob not in current.settlement_book.obligations for ob in origin.settlement_book.obligations)
                or any(not any(s.order == prior.order and s.records[:len(prior.records)] == prior.records
                           for s in current.order_streams) for prior in origin.order_streams)
                or any(s not in current.reservation_schedules for s in origin.reservation_schedules)
                or plan.account_id != current.inputs.scope.account_id
                or plan.policy != current.inputs.execution_policy or plan.as_of != origin.at.instant
                or plan.cash != origin.cash or plan.sellability != origin.sellability
                or plan.working_order_set_hash != canonical_sha256(tuple(s.stream_hash for s in
                    sorted(origin.order_streams, key=lambda s: s.order.order_id.value)))
                or self.stream not in current.order_streams
                or order.account_id != plan.account_id
                or state is None or state.status not in {OrderStatus.ACCEPTED, OrderStatus.ACTIVE}
                or state.remaining_quantity != order.intent.quantity
                or event.instrument_id != order.intent.instrument_id
                or event.event_time != event.available_time or current.at.instant != event.event_time
                or SimulationInstant(event.event_time, event.phase, event.source_sequence) >= current.at
                or order.created_at.instant >= event.event_time
                or state.updated_at > current.at
                or self.observation.kind is not BarOpenKind.REAL
                or self.observation.open_price != self.terms.notional_evidence.price
                or self.terms not in current.inputs.opening_terms
                or self.terms.bar_event_id != event.event_id or self.terms.bar_event_hash != event.event_hash
                or self.terms.instrument_id != order.intent.instrument_id
                or self.terms.side is not order.intent.side or self.terms.opening_at != event.event_time
                or self.terms.market_state.evidence_hash != event.event_hash
                or self.terms.market_state.revision_id != event.revision_id
                or self.terms.liquidity.evaluated_at != event.event_time
                or self.terms.market_state.observed_at > event.event_time
                or self.terms.market_state.available_at > event.event_time):
            raise ValueError("standard current-open source, clock, plan or Order mismatch")
        proposals = tuple(p for p in plan.proposed if p.intent == order.intent)
        fee = self.original_fee
        original_terms = tuple(t for t in origin.inputs.opening_terms
            if t.instrument_id == order.intent.instrument_id and t.side is order.intent.side
            and t.opening_at == origin.at.instant)
        if len(proposals) != 1 or len(original_terms) != 1:
            raise ValueError("standard original admission lacks exact source/intent cover")
        proposal = proposals[0]
        old_market, old_fee = _standard_market_fee_v1(order, original_terms[0])
        records = tuple(r.event for r in self.stream.records)
        kinds = (OrderEventType.ORDER_INTENT_CREATED, OrderEventType.ORDER_CAPABILITY_APPROVED,
            OrderEventType.ORDER_TRANSLATED, OrderEventType.MARKET_RULE_APPROVED,
            OrderEventType.FEE_RESERVATION_ESTIMATED, OrderEventType.PRE_TRADE_RISK_APPROVED,
            OrderEventType.ORDER_SUBMITTED, OrderEventType.ORDER_ACCEPTED)
        spec = old_market.evaluation_input.executable_order_spec
        if (fee != old_fee or fee.order_id != order.order_id
                or proposal.estimated_fee != fee.fee_estimate.total_fee
                or proposal.fee_authority_hash != fee.fee_estimate.rule_set.rule_set_hash
                or proposal.principal.units != (old_market.calculated_notional.units if order.intent.side is OrderSide.BUY else 0)
                or tuple(e.event_type for e in records[:8]) != kinds
                or tuple(e.evidence_id for e in records[1:8]) != (
                    spec.capability_approval.decision_id, spec.spec_id, old_market.decision_id,
                    fee.proposal_hash, plan.plan_hash, original_terms[0].bar_event_hash,
                    original_terms[0].bar_event_hash)
                or any(e.occurred_at.instant != order.created_at.instant for e in records[:3])
                or any(e.occurred_at.instant != origin.at.instant for e in records[3:8])
                or records[7].occurred_at <= origin.at
                or (order.intent.time_in_force is TimeInForce.DAY and event.event_time != origin.at.instant)):
            raise ValueError("standard original market/fee/acceptance evidence is stale or substituted")
        own = tuple(r for r in current.reservations.active_reservations if r.order_id == order.order_id)
        schedules = tuple(s for s in current.reservation_schedules if s.order_id == order.order_id)
        if (len(own) != 1 or len(schedules) != 1 or own[0].source_proposal_hash != fee.proposal_hash
                or own[0].remaining_quantity != order.intent.quantity
                or schedules[0].source_proposal_hash != fee.proposal_hash
                or own[0].commitment.fee_reserve != fee.commitment.fee_reserve
                or own[0].commitment.margin or own[0].commitment.exposure_capacity
                or own[0].commitment.order_capacity_units != 1
                or own[0].commitment.cash != ((proposal.principal,) if order.intent.side is OrderSide.BUY else ())
                or own[0].commitment.sellable_quantities != ((order.intent.quantity,) if order.intent.side is OrderSide.SELL else ())):
            raise ValueError("standard standing Order does not retain its ONE original commitment")
        market, current_fee = _standard_market_fee_v1(order, self.terms)
        object.__setattr__(self, "market", market)
        object.__setattr__(self, "fee", current_fee)

    @property
    def proof_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_standard_current_open_proof", "schema_version": 1,
            "plan": self.plan, "plan_sources": self.plan_sources, "sources": self.sources,
            "stream_hash": self.stream.stream_hash, "original_fee": self.original_fee,
            "observation_hash": self.observation.observation_hash, "terms_hash": canonical_sha256(self.terms),
            "market": self.market, "fee": self.fee}


def _standard_full_fill_budget_v1(proofs: tuple[_StandardCurrentOpenProofV1, ...]) -> bool:
    """One atomic batch: own holds are freed once; every other hold stays protected."""
    if not proofs or any(type(p) is not _StandardCurrentOpenProofV1 for p in proofs):
        raise TypeError("standard full-fill budget needs exact current-open proofs")
    sources = proofs[0].sources
    if (any(canonical_sha256(p.sources) != canonical_sha256(sources) for p in proofs)
            or len({p.stream.order.order_id for p in proofs}) != len(proofs)
            or len({p.stream.order.intent.instrument_id for p in proofs}) != len(proofs)):
        raise ValueError("standard full-fill batch has mixed prefixes or duplicate Orders/instruments")
    available = {key.venue_id: value.units for key, value in sources.available_by_venue}
    for proof in proofs:
        order = proof.stream.order
        own = next(r for r in sources.reservations.active_reservations if r.order_id == order.order_id)
        venue = order.intent.instrument_id.venue
        available[venue] += sum(m.units for m in (*own.commitment.cash, *own.commitment.fee_reserve))
        available[venue] -= proof.fee.fee_estimate.total_fee.units
        if order.intent.side is OrderSide.BUY:
            available[venue] -= proof.market.calculated_notional.units
        elif (sources.sellability.sellable_for(order.intent.instrument_id).units
                + sum(q.units for q in own.commitment.sellable_quantities) < order.intent.quantity.units):
            return False
    return all(units >= 0 for units in available.values())


@dataclass(frozen=True, slots=True)
class _StandardOpeningOutcomeV1:
    proof: _StandardCurrentOpenProofV1
    action: NoEligibleBarAction
    reason: str | None
    fill: Fill | None
    budget_prefix: tuple[_StandardCurrentOpenProofV1, ...] = ()

    def __post_init__(self) -> None:
        if (type(self.proof) is not _StandardCurrentOpenProofV1 or type(self.action) is not NoEligibleBarAction
                or (self.action is NoEligibleBarAction.FULL_FILL) != (type(self.fill) is Fill)
                or (self.fill is not None) != (self.reason is None)):
            raise ValueError("standard opening action/Fill/reason mismatch")
        if (type(self.budget_prefix) is not tuple
                or any(type(p) is not _StandardCurrentOpenProofV1 or not p.terms.liquidity.approved
                       for p in self.budget_prefix)):
            raise ValueError("standard opening budget prefix is not source-approved native proofs")
        reason = ("liquidity_blocked" if not self.proof.terms.liquidity.approved else
            "settled_cash_or_t1_unavailable" if not _standard_full_fill_budget_v1((*self.budget_prefix, self.proof)) else None)
        action = (NoEligibleBarAction.FULL_FILL if reason is None else
            NoEligibleBarAction.EXPIRE if self.proof.stream.order.intent.time_in_force is TimeInForce.DAY else
            NoEligibleBarAction.KEEP_ACTIVE)
        if self.reason != reason or self.action is not action:
            raise ValueError("standard opening action does not bind native liquidity/batch budget")
        if self.fill is not None:
            terms = self.proof.terms
            expected = _native_cn_portfolio_zero_slippage_fill_v1(stream=self.proof.stream,
                observation=self.proof.observation, market_state=terms.market_state,
                slippage_model=terms.slippage_model, approval_hash=self.proof.proof_hash)
            if self.fill != expected or not terms.liquidity.approved:
                raise ValueError("standard opening Fill does not bind native observed proof/slippage")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_standard_opening_outcome", "schema_version": 1,
            "proof": self.proof, "action": self.action.value, "reason": self.reason,
            "fill": self.fill, "budget_prefix_hashes": tuple(p.proof_hash for p in self.budget_prefix),
            "development_only": True, "trade_authorized": False}


def _standard_opening_v1(proof: _StandardCurrentOpenProofV1, *,
    budget_prefix: tuple[_StandardCurrentOpenProofV1, ...] = (),
) -> _StandardOpeningOutcomeV1:
    if type(proof) is not _StandardCurrentOpenProofV1 or type(budget_prefix) is not tuple:
        raise TypeError("standard opening requires typed native proof and budget prefix")
    terms = proof.terms
    reason = ("liquidity_blocked" if not terms.liquidity.approved else
        "settled_cash_or_t1_unavailable" if not _standard_full_fill_budget_v1((*budget_prefix, proof)) else None)
    if reason is not None:
        action = (NoEligibleBarAction.EXPIRE if proof.stream.order.intent.time_in_force is TimeInForce.DAY
                  else NoEligibleBarAction.KEEP_ACTIVE)
        return _StandardOpeningOutcomeV1(proof, action, reason, None, budget_prefix)
    fill = _native_cn_portfolio_zero_slippage_fill_v1(stream=proof.stream,
        observation=proof.observation, market_state=terms.market_state,
        slippage_model=terms.slippage_model, approval_hash=proof.proof_hash)
    return _StandardOpeningOutcomeV1(proof, NoEligibleBarAction.FULL_FILL, None, fill, budget_prefix)


@dataclass(frozen=True, slots=True)
class _StandardFinancialStepV1:
    opening: _StandardOpeningOutcomeV1
    terminal_order: OrderEventStream

    def __post_init__(self) -> None:
        if type(self.opening) is not _StandardOpeningOutcomeV1 or type(self.terminal_order) is not OrderEventStream:
            raise TypeError("standard financial step needs exact native outcome and terminal stream")
        proof, fill = self.opening.proof, self.opening.fill
        stream = self.terminal_order
        if (type(fill) is not Fill or stream.order != proof.stream.order
                or stream.records[:len(proof.stream.records)] != proof.stream.records
                or stream.state is None or stream.state.status is not OrderStatus.FILLED
                or tuple(r.fill for r in stream.records if r.fill is not None) != (fill,)):
            raise ValueError("standard terminal Order does not extend its exact full-Fill proof")
        terms = proof.terms
        market, tax = terms.market_fee_resolution, terms.tax_resolution
        if (any(r.venue_id != fill.venue_id or r.instrument_id != fill.instrument_id
                or r.side is not fill.side or r.effective_at != fill.execution_time for r in (market, tax))
                or _rule_ids(terms.final_fill_rules, FinalFeeRuleSource.MARKET_FEE)
                    != tuple(sorted(canonical_sha256(r) for r in market.final_fill_charge_rules))
                or _rule_ids(terms.final_fill_rules, FinalFeeRuleSource.TAX) != (canonical_sha256(tax.final_fill_charge_rule),)):
            raise ValueError("standard final fees do not bind CURRENT observed Fill sources")

    @property
    def final_fill_rules(self):
        return self.opening.proof.terms.final_fill_rules

    @property
    def final_order_rules(self):
        return self.opening.proof.terms.final_order_rules

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_standard_financial_step", "schema_version": 1,
            "opening": self.opening, "terminal_order": self.terminal_order}


def _book_standard_full_fill_batch_v1(steps: tuple[_StandardFinancialStepV1, ...]
) -> tuple[AccountingJournal, LedgerState, tuple[Fill, ...], tuple[FeeAssessment, ...]]:
    if not steps or any(type(s) is not _StandardFinancialStepV1 for s in steps):
        raise TypeError("standard booking needs exact full-Fill steps")
    proofs = tuple(s.opening.proof for s in steps)
    if not _standard_full_fill_budget_v1(proofs):
        raise ValueError("standard atomic Fill set would spend another hold or unsettled receipts")
    sources = proofs[0].sources
    ordered = tuple(sorted(steps, key=lambda s: (
        s.opening.proof.stream.order.intent.side is OrderSide.BUY,
        s.opening.proof.stream.order.intent.instrument_id)))
    for index, step in enumerate(ordered):
        if step.opening.budget_prefix != tuple(s.opening.proof for s in ordered[:index]):
            raise ValueError("standard full-Fill selection does not carry its exact sell-first budget prefix")
    journal, ledger, fills, fees = book_native_cn_portfolio_financial_core_v1(
        prior_journal=sources.journal, ledger_schema=sources.inputs.scope.ledger_schema,
        cost_basis_policy=sources.inputs.cost_basis_policy,
        notional_quantization=sources.inputs.notional_quantization, steps=ordered, sell_first=True)
    protected = {key.venue_id: value.units for key, value in sources.available_by_venue}
    for proof in proofs:
        own = next(r for r in sources.reservations.active_reservations if r.order_id == proof.stream.order.order_id)
        protected[proof.stream.order.intent.instrument_id.venue] += sum(m.units for m in (*own.commitment.cash, *own.commitment.fee_reserve))
    for entry in journal.entries[len(sources.journal.entries):]:
        # Native cash DEBITS, not a recomputed notional or net cash change.
        # No SELL credit may finance this batch's BUY principal or any fee.
        for change in entry.balance_changes:
            if type(change.key) is CashBalanceKey and isinstance(change.value, Money) and change.value.units < 0:
                protected[change.key.venue_id] += change.value.units
    if (any(units < 0 for units in protected.values())
            or any(value.amount.units < 0 for value in ledger.cash_balances)
            or any(sum(f.amount.units for f in fees
                        if proof.stream.order.order_id in f.basis_ids
                        or any(fill.fill_id in f.basis_ids for fill in fills
                               if fill.order_id == proof.stream.order.order_id))
                   > proof.fee.fee_estimate.total_fee.units for proof in proofs)):
        raise ValueError("standard native final fees exceed reserved worst-case budget or venue cash")
    return journal, ledger, fills, fees
