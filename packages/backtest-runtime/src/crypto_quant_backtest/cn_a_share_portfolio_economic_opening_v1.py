"""Native execution-price, own-reservation and conservative dividend-tax budgets."""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass

import crypto_quant_domain as d
import crypto_quant_trading as t
from .cn_a_share_portfolio_economic_definition_v1 import CnASharePortfolioEconomicOpeningTermsV1
from .cn_a_share_portfolio_economic_native_state_v1 import (
    _EconomicOpenSourcesV1, _EconomicNativeFailureV1, _economic_sources_hash_v1,
)
from .cn_a_share_portfolio_financial_core_v1 import book_native_cn_portfolio_financial_core_v1
from .cn_a_share_portfolio_venue_funding_development_v1 import plan_cn_portfolio_venue_funding_development_v1
from .engine import EngineFailureCode
from .execution import BarOpenObservation, BarOpenKind, NoEligibleBarAction, _reference_mark
from .slippage import ExecutionReferencePrice, SlippageRequest
from .ports import SimulationPortOutcome


def _cent(units):
    return d.Money(units, d.Scale(2), "CNY")


def _cash_money(value):
    if type(value) is not d.Money or value.currency != "CNY" or value.scale != d.Scale(2) or type(value.units) is not int:
        raise ValueError("economic execution money must be exact CNY cents")
    return value


def _economic_quote_v1(order: d.Order, observation: BarOpenObservation, terms: CnASharePortfolioEconomicOpeningTermsV1):
    return terms.slippage_model.decide_slippage(SlippageRequest(
        ExecutionReferencePrice(_reference_mark(observation)), order.intent.side, order.intent.quantity, terms.market_state))


def _economic_assessment_for_quote_v1(order, terms, quote):
    capability = t.OrderCapabilityValidator().validate(order.intent, terms.capability_set)
    if capability.approval is None:
        raise _EconomicNativeFailureV1(EngineFailureCode.CAPABILITY_REJECTED, capability, operation="capability_validation", native_inputs={"intent":order.intent,"capability_set":terms.capability_set}, original_claim={"order":order,"terms":terms})
    translated = t.OrderTranslator().translate(order, capability.approval, terms.translation_mapping, terms.opening_at)
    if translated.executable_spec is None:
        raise _EconomicNativeFailureV1(EngineFailureCode.TRANSLATION_REJECTED, translated, operation="order_translation", native_inputs={"order":order,"approval":capability.approval,"mapping":terms.translation_mapping,"at":terms.opening_at}, original_claim={"order":order,"terms":terms})
    evidence = t.OrderRuleNotionalEvidence(t.NotionalPriceBasis.SUPPLIED_REFERENCE, quote.result.execution_price,
        d.canonical_sha256(quote.result), terms.opening_at)
    market = t.MarketRuleEvaluator().evaluate(t.OrderRuleEvaluationInput(
        translated.executable_spec, terms.opening_at, evidence), terms.rule_timeline)
    if market.data_integrity_failure is not None:
        raise d.ArtifactIntegrityError("economic market source rejected: " + d.canonical_sha256(market))
    if market.approval is None:
        return market, None, None, "market_rule_restricted"
    issues = t.MarketRuleEvaluator.validate_execution_price(market.approval, quote.result.execution_price)
    if issues:
        return market, issues, None, "execution_price_restricted"
    _cash_money(market.approval.calculated_notional)
    estimate = t.FeeReservationEstimator().estimate(market.approval, terms.reservation_rules, terms.opening_at)
    if estimate.proposal is None:
        raise _EconomicNativeFailureV1(EngineFailureCode.FEE_RESERVATION, estimate, operation="fee_reservation", native_inputs={"approval":market.approval,"rules":terms.reservation_rules,"at":terms.opening_at}, original_claim={"order":order,"terms":terms})
    _cash_money(estimate.proposal.fee_estimate.total_fee)
    return market, issues, estimate.proposal, None


def _economic_evaluation_v1(order, observation, terms):
    if type(order) is not d.Order or type(observation) is not BarOpenObservation or type(terms) is not CnASharePortfolioEconomicOpeningTermsV1:
        raise TypeError("economic quote requires exact order, raw observation and source terms")
    event = observation.event
    if (order.intent.instrument_id != terms.instrument_id or order.intent.side is not terms.side
            or event.instrument_id != terms.instrument_id or terms.bar_event_id != event.event_id
            or terms.bar_event_hash != event.event_hash or event.event_time != event.available_time
            or terms.opening_at != event.event_time or terms.notional_evidence.price != observation.open_price
            or terms.market_state.evidence_hash != event.event_hash or terms.market_state.revision_id != event.revision_id):
        raise d.ArtifactIntegrityError("economic raw quote/order/source binding mismatch")
    if order.created_at.instant >= event.event_time:
        raise ValueError("economic opening cannot use a same-time or future intention")
    if observation.kind is not BarOpenKind.REAL:
        return None, None, None, None, "no_real_open"
    if not terms.liquidity.approved:
        return None, None, None, None, "liquidity_blocked"
    capability = t.OrderCapabilityValidator().validate(order.intent, terms.capability_set)
    if capability.approval is None:
        raise _EconomicNativeFailureV1(EngineFailureCode.CAPABILITY_REJECTED, capability, operation="capability_validation", native_inputs={"intent":order.intent,"capability_set":terms.capability_set}, original_claim={"order":order,"terms":terms})
    translated = t.OrderTranslator().translate(order, capability.approval, terms.translation_mapping, terms.opening_at)
    if translated.executable_spec is None:
        raise _EconomicNativeFailureV1(EngineFailureCode.TRANSLATION_REJECTED, translated, operation="order_translation", native_inputs={"order":order,"approval":capability.approval,"mapping":terms.translation_mapping,"at":terms.opening_at}, original_claim={"order":order,"terms":terms})
    slip = _economic_quote_v1(order, observation, terms)
    if slip.result is None:
        return slip, None, None, None, "slippage_not_applicable"
    evidence = t.OrderRuleNotionalEvidence(t.NotionalPriceBasis.SUPPLIED_REFERENCE, slip.result.execution_price,
        d.canonical_sha256(slip.result), terms.opening_at)
    market = t.MarketRuleEvaluator().evaluate(t.OrderRuleEvaluationInput(
        translated.executable_spec, terms.opening_at, evidence), terms.rule_timeline)
    if market.data_integrity_failure is not None:
        raise d.ArtifactIntegrityError("economic market source rejected: " + d.canonical_sha256(market))
    if market.approval is None:
        return slip, market, None, None, "market_rule_restricted"
    issues = t.MarketRuleEvaluator.validate_execution_price(market.approval, slip.result.execution_price)
    if issues:
        return slip, market, issues, None, "execution_price_restricted"
    _cash_money(market.approval.calculated_notional)
    estimate = t.FeeReservationEstimator().estimate(market.approval, terms.reservation_rules, terms.opening_at)
    if estimate.proposal is None:
        raise _EconomicNativeFailureV1(EngineFailureCode.FEE_RESERVATION, estimate, operation="fee_reservation", native_inputs={"approval":market.approval,"rules":terms.reservation_rules,"at":terms.opening_at}, original_claim={"order":order,"terms":terms})
    _cash_money(estimate.proposal.fee_estimate.total_fee)
    return slip, market, issues, estimate.proposal, None


def _own_v1(sources, order):
    rows = tuple(r for r in sources.reservations.active_reservations if r.order_id == order.order_id)
    if not rows:
        return 0, 0, 0
    if len(rows) != 1 or rows[0].remaining_quantity != order.intent.quantity:
        raise d.ArtifactIntegrityError("economic Order has no unique whole own reservation")
    own = rows[0].commitment
    principal = sum(_cash_money(m).units for m in own.cash)
    fees = sum(_cash_money(m).units for m in own.fee_reserve)
    shares = sum(q.units for q in own.sellable_quantities if q.instrument_id == str(order.intent.instrument_id))
    if (own.margin or own.exposure_capacity or own.order_capacity_units != 1
            or any(q.instrument_id != str(order.intent.instrument_id) or q.scale != d.Scale(0) for q in own.sellable_quantities)
            or (order.intent.side is d.OrderSide.SELL and principal)):
        raise d.ArtifactIntegrityError("economic own reservation has foreign resources")
    return principal, fees, shares


def _extras_v1(sources, order, market, fee):
    principal, held_fee, shares = _own_v1(sources, order)
    current = market.approval.calculated_notional.units if order.intent.side is d.OrderSide.BUY else 0
    return max(0, current - principal), max(0, fee.fee_estimate.total_fee.units - held_fee), shares


@dataclass(frozen=True, slots=True)
class _EconomicOpeningOutcomeV1:
    order_id: d.DomainId
    observation_hash: str
    sources_hash: str
    original_admission_hash: str | None
    terms_hash: str
    slippage_outcome: object | None
    market_decision: t.MarketRuleDecision | None
    execution_price_issues: tuple[t.MarketRuleIssue, ...] | None
    fee: t.ResourceReservationProposal | None
    action: NoEligibleBarAction
    reason: str | None
    fill: d.Fill | None
    extra_principal: d.Money
    extra_fee: d.Money
    budget_prefix_order_ids: tuple[d.DomainId, ...]

    def __post_init__(self):
        if type(self.order_id) is not d.DomainId or self.order_id.kind is not d.DomainIdKind.ORDER:
            raise TypeError("economic outcome requires exact Order DomainId")
        for name in ("observation_hash", "sources_hash", "terms_hash"):
            value = getattr(self, name)
            if type(value) is not str or len(value) != 71 or not value.startswith("sha256:") or any(c not in "0123456789abcdef" for c in value[7:]):
                raise ValueError("economic outcome hash must be canonical")
        if self.slippage_outcome is not None and type(self.slippage_outcome) is not SimulationPortOutcome:
            raise TypeError("economic slippage outcome must be exact native SimulationPortOutcome")
        if self.reason is not None and (type(self.reason) is not str or not self.reason or self.reason.strip() != self.reason):
            raise ValueError("economic opening reason must be canonical text or null")
        if self.original_admission_hash is not None and (type(self.original_admission_hash) is not str
                or len(self.original_admission_hash) != 71 or not self.original_admission_hash.startswith("sha256:")
                or any(c not in "0123456789abcdef" for c in self.original_admission_hash[7:])):
            raise ValueError("economic admission hash must be canonical or null")
        if type(self.action) is not NoEligibleBarAction or (self.action is NoEligibleBarAction.FULL_FILL) != (self.fill is not None):
            raise ValueError("economic opening action/Fill branch mismatch")
        if (self.fill is not None) != (self.reason is None) or (self.fill is not None and (type(self.fill) is not d.Fill or self.fill.order_id != self.order_id)):
            raise ValueError("economic opening Fill/reason/Order mismatch")
        for value in (self.extra_principal, self.extra_fee):
            if _cash_money(value).units < 0:
                raise ValueError("economic extra resource demand cannot be negative")
        if (type(self.budget_prefix_order_ids) is not tuple or len(set(self.budget_prefix_order_ids)) != len(self.budget_prefix_order_ids)
                or self.order_id in self.budget_prefix_order_ids or any(type(v) is not d.DomainId or v.kind is not d.DomainIdKind.ORDER for v in self.budget_prefix_order_ids)):
            raise ValueError("economic budget prefix must contain unique prior Order IDs")
        if self.market_decision is not None and type(self.market_decision) is not t.MarketRuleDecision:
            raise TypeError("economic market decision must be exact native value")
        if self.fee is not None and type(self.fee) is not t.ResourceReservationProposal:
            raise TypeError("economic fee must be exact native proposal")
        if self.execution_price_issues is not None and (type(self.execution_price_issues) is not tuple or any(type(i) is not t.MarketRuleIssue for i in self.execution_price_issues)):
            raise TypeError("economic execution price issues must be native tuple or null")

    @property
    def outcome_hash(self):
        return d.canonical_sha256(self)

    def to_canonical_dict(self):
        return {"type": "cn_a_share_portfolio_economic_opening_outcome", "schema_version": 1,
            **{name: getattr(self, name) for name in ("order_id", "observation_hash", "sources_hash", "original_admission_hash",
                "terms_hash", "slippage_outcome", "market_decision", "execution_price_issues", "fee", "reason", "fill",
                "extra_principal", "extra_fee", "budget_prefix_order_ids")}, "action": self.action.value}


def _retained_opening_term_v1(terms, when, instrument, side):
    """Find the unique coordinate in the definition's validated sorted terms."""
    def coordinate(term):
        return term.opening_at, term.instrument_id, term.side.value

    key = when, instrument, side.value
    index = bisect_left(terms, key, key=coordinate)
    if index < len(terms) and coordinate(terms[index]) == key:
        return terms[index]
    return None


def _verify_economic_opening_inputs_v1(*, sources, stream, observation, terms, admission, budget_prefix=()):
    if type(sources) is not _EconomicOpenSourcesV1 or type(stream) is not t.OrderEventStream:
        raise TypeError("economic opening requires exact native committed source and stream")
    order, state = stream.order, stream.state
    if (stream not in sources.order_streams or state is None or state.status not in {d.OrderStatus.ACCEPTED, d.OrderStatus.ACTIVE}
            or state.remaining_quantity != order.intent.quantity or state.updated_at > sources.at
            or sources.at.instant != observation.event.event_time
            or type(terms) is not CnASharePortfolioEconomicOpeningTermsV1
            or terms != _retained_opening_term_v1(sources.inputs.opening_terms, terms.opening_at,
                                                terms.instrument_id, terms.side)):
        raise d.ArtifactIntegrityError("economic current opening has wrong source clock/Order/terms")
    own = tuple(r for r in sources.reservations.active_reservations if r.order_id == order.order_id)
    if len(own) != 1 or own[0].source_proposal_hash != admission.fee.proposal_hash:
        raise d.ArtifactIntegrityError("economic existing Order lost original fee reservation")
    if (admission.sources.inputs.definition() != sources.inputs.definition() or admission.sources.at > sources.at
            or admission.plan.cash != admission.sources.cash or admission.plan.sellability != admission.sources.sellability
            or not any(p.intent == order.intent for p in admission.plan.proposed)):
        raise d.ArtifactIntegrityError("economic original admission is not source-bound")
    original_terms = _retained_opening_term_v1(
        sources.inputs.opening_terms, admission.sources.at.instant, order.intent.instrument_id, order.intent.side,
    )
    if original_terms is None or admission.quote.result is None:
        raise d.ArtifactIntegrityError("economic original quote lacks exact retained term cover")
    reference = admission.quote.result.reference_price
    if reference.mark.price != original_terms.notional_evidence.price or reference.mark.source_event_id != original_terms.bar_event_id:
        raise d.ArtifactIntegrityError("economic original quote reference is substituted")
    expected_quote = original_terms.slippage_model.decide_slippage(SlippageRequest(
        reference, order.intent.side, order.intent.quantity, original_terms.market_state))
    old_market, old_issues, old_fee, old_reason = _economic_assessment_for_quote_v1(order, original_terms, expected_quote)
    proposal = next(p for p in admission.plan.proposed if p.intent == order.intent)
    if (expected_quote != admission.quote or old_reason is not None or old_issues
            or old_fee != admission.fee or proposal.estimated_fee != old_fee.fee_estimate.total_fee
            or proposal.fee_authority_hash != old_fee.fee_estimate.rule_set.rule_set_hash
            or proposal.principal.units != (old_market.approval.calculated_notional.units if order.intent.side is d.OrderSide.BUY else 0)
            or own[0].commitment.cash != ((proposal.principal,) if order.intent.side is d.OrderSide.BUY else ())
            or own[0].commitment.fee_reserve != old_fee.commitment.fee_reserve):
        raise d.ArtifactIntegrityError("economic original admission/own reservation differs from native quote/fees")
    records = tuple(r.event for r in stream.records)
    kinds = (d.OrderEventType.ORDER_INTENT_CREATED, d.OrderEventType.ORDER_CAPABILITY_APPROVED,
        d.OrderEventType.ORDER_TRANSLATED, d.OrderEventType.MARKET_RULE_APPROVED,
        d.OrderEventType.FEE_RESERVATION_ESTIMATED, d.OrderEventType.PRE_TRADE_RISK_APPROVED,
        d.OrderEventType.ORDER_SUBMITTED, d.OrderEventType.ORDER_ACCEPTED)
    spec = old_market.approval.evaluation_input.executable_order_spec
    if (tuple(r.event_type for r in records[:8]) != kinds
            or tuple(r.evidence_id for r in records[1:8]) != (spec.capability_approval.decision_id, spec.spec_id,
                old_market.approval.decision_id, old_fee.proposal_hash, admission.plan.plan_hash,
                original_terms.bar_event_hash, original_terms.bar_event_hash)
            or any(r.occurred_at.instant != original_terms.opening_at or r.occurred_at.phase.rank != phase
                   or r.occurred_at.phase.code != "cn_economic_native" for r, phase in zip(records[1:8], range(56, 63), strict=True))):
        raise d.ArtifactIntegrityError("economic admission evidence is missing or backdated")
    if len({p.order_id for p in budget_prefix}) != len(budget_prefix) or any(p.order_id == order.order_id for p in budget_prefix):
        raise d.ArtifactIntegrityError("economic opening repeats an Order budget")
    quote, market, issues, fee, reason = _economic_evaluation_v1(order, observation, terms)
    extra_p = extra_f = 0
    if reason is None:
        extra_p, extra_f, own_shares = _extras_v1(sources, order, market, fee)
        if any(type(p) is not _EconomicOpeningOutcomeV1 or p.fill is None or p.sources_hash != _economic_sources_hash_v1(sources) for p in budget_prefix):
            raise d.ArtifactIntegrityError("economic opening prefix must be the actual prior selected set")
        used = {}
        for prior in budget_prefix:
            venue = prior.market_decision.approval.evaluation_input.executable_order_spec.intent.instrument_id.venue
            used[venue] = used.get(venue, 0) + prior.extra_principal.units + prior.extra_fee.units
        venue = order.intent.instrument_id.venue
        row = next(r for r in sources.economic_projection.cash_rows if r.key.venue_id == venue)
        if order.intent.side is d.OrderSide.SELL and sources.sellability.sellable_for(order.intent.instrument_id).units + own_shares < order.intent.quantity.units:
            reason = "t1_unavailable"
        elif (order.intent.side is d.OrderSide.BUY and sources.economic_projection.tax_shortfall.units > 0):
            reason = "tax_shortfall_buy_blocked"
        elif extra_p + extra_f + used.get(venue, 0) > row.spendable.units:
            reason = "venue_spendable_unavailable"
        elif order.intent.side is d.OrderSide.BUY and extra_p + extra_f + sum(used.values()) > sources.economic_projection.buy_budget.units:
            reason = "account_buy_budget_unavailable"
    return quote, market, issues, fee, reason, extra_p, extra_f


def _economic_opening_v1(*, sources, stream, observation, terms, admission, budget_prefix=()):
    quote, market, issues, fee, reason, extra_p, extra_f = _verify_economic_opening_inputs_v1(
        sources=sources, stream=stream, observation=observation, terms=terms, admission=admission, budget_prefix=budget_prefix)
    order, state = stream.order, stream.state
    fill = None
    if reason is None:
        decision = quote.result
        fill_id = d.DomainId(d.DomainIdKind.FILL, d.DomainIdKind.FILL.prefix + "_" + d.canonical_sha256({
            "type": "cn_a_share_portfolio_economic_open_fill_identity", "order_id": order.order_id,
            "open_event_hash": observation.event.event_hash, "economic_proof_hash": _economic_sources_hash_v1(sources),
            "slippage_decision_id": decision.decision_id})[7:])
        fill = d.Fill(fill_id=fill_id, order_id=order.order_id, account_id=order.account_id,
            venue_id=order.intent.instrument_id.venue, instrument_id=order.intent.instrument_id, side=order.intent.side,
            quantity=state.remaining_quantity, reference_price=observation.open_price,
            reference_price_purpose=d.PricePurpose.EXECUTION_REFERENCE, price=decision.execution_price,
            slippage_amount=d.Money(decision.slippage_amount.units, decision.slippage_amount.scale, decision.slippage_amount.quote_currency),
            slippage_decision_id=decision.decision_id, slippage_model_key=decision.component_ref.component_key,
            slippage_calibration_id=d.canonical_sha256(decision.calibration_ref), liquidity="full", execution_time=observation.event.event_time)
    action = NoEligibleBarAction.FULL_FILL if fill is not None else NoEligibleBarAction.EXPIRE if order.intent.time_in_force is d.TimeInForce.DAY else NoEligibleBarAction.KEEP_ACTIVE
    return _EconomicOpeningOutcomeV1(order.order_id, observation.observation_hash, _economic_sources_hash_v1(sources),
        d.canonical_sha256(admission), d.canonical_sha256(terms), quote, market, issues, fee, action, reason, fill,
        _cent(extra_p), _cent(extra_f), tuple(p.order_id for p in budget_prefix))


@dataclass(frozen=True, slots=True)
class _EconomicFinancialStepV1:
    opening: _EconomicOpeningOutcomeV1
    terminal_order: t.OrderEventStream
    terms: CnASharePortfolioEconomicOpeningTermsV1

    def __post_init__(self):
        if type(self.opening) is not _EconomicOpeningOutcomeV1 or type(self.terminal_order) is not t.OrderEventStream or type(self.terms) is not CnASharePortfolioEconomicOpeningTermsV1:
            raise TypeError("economic financial step requires exact opening/terminal/terms")
        if (d.canonical_sha256(self.terms) != self.opening.terms_hash or self.opening.fill is None
                or self.terminal_order.order.order_id != self.opening.order_id or self.terminal_order.state is None
                or self.terminal_order.state.status is not d.OrderStatus.FILLED
                or tuple(r.fill for r in self.terminal_order.records if r.fill is not None) != (self.opening.fill,)):
            raise ValueError("economic terminal Order does not extend its one full Fill")

    @property
    def final_fill_rules(self):
        return self.terms.final_fill_rules

    @property
    def final_order_rules(self):
        return self.terms.final_order_rules

    def to_canonical_dict(self):
        return {"type": "cn_a_share_portfolio_economic_financial_step", "schema_version": 1,
                "opening": self.opening, "terminal_order": self.terminal_order, "terms": self.terms}


def _book_economic_full_fill_batch_v1(*, sources, steps):
    if type(sources) is not _EconomicOpenSourcesV1 or type(steps) is not tuple or not steps or any(type(s) is not _EconomicFinancialStepV1 for s in steps):
        raise TypeError("economic native fan-in requires exact source and nonempty step tuple")
    ordered = tuple(sorted(steps, key=lambda s: (s.opening.fill.side is d.OrderSide.BUY, str(s.opening.fill.instrument_id), s.opening.order_id.value)))
    for index, step in enumerate(ordered):
        opening = step.opening
        original = next(s for s in sources.order_streams if s.order.order_id == opening.order_id)
        if (opening.sources_hash != _economic_sources_hash_v1(sources)
                or opening.budget_prefix_order_ids != tuple(s.opening.order_id for s in ordered[:index])
                or step.terminal_order.records[:len(original.records)] != original.records):
            raise d.ArtifactIntegrityError("economic booking lost exact common source/selection/Order prefix")
    try:
        journal, ledger, fills, fees = book_native_cn_portfolio_financial_core_v1(prior_journal=sources.journal,
            ledger_schema=sources.inputs.scope.ledger_schema, cost_basis_policy=sources.inputs.cost_basis_policy,
            notional_quantization=sources.inputs.notional_quantization, steps=ordered, sell_first=True)
    except _EconomicNativeFailureV1 as rejected:
        rejected.original_claim={"source":sources,"steps":ordered,"failed_step":rejected.original_claim["step"]}
        raise
    protected = {r.key.venue_id: r.spendable.units for r in sources.economic_projection.cash_rows}
    for step in ordered:
        own_p, own_f, _ = _own_v1(sources, step.terminal_order.order)
        protected[step.opening.fill.venue_id] += own_p + own_f
    for entry in journal.entries[len(sources.journal.entries):]:
        for change in entry.balance_changes:
            if type(change.key) is d.CashBalanceKey and type(change.value) is d.Money and change.value.units < 0:
                protected[change.key.venue_id] += _cash_money(change.value).units
    for step in ordered:
        order_id = step.opening.order_id
        related = tuple(fill.fill_id for fill in fills if fill.order_id == order_id)
        actual = sum(_cash_money(f.amount).units for f in fees if order_id in f.basis_ids or any(i in f.basis_ids for i in related))
        if actual > step.opening.fee.fee_estimate.total_fee.units:
            raise ValueError("economic native actual fees exceed this Order current estimate")
    if any(v < 0 for v in protected.values()) or any(b.amount.units < 0 for b in ledger.cash_balances):
        raise ValueError("economic native debit invades another Order or dividend-tax hold")
    return journal, ledger, fills, fees


def _economic_venue_funding_v1(*, sources, candidates, use_checkpoint_cash=False, evaluations=None):
    if type(sources) is not _EconomicOpenSourcesV1 or type(candidates) is not tuple:
        raise TypeError("economic funding must derive from exact source and actual order candidates")
    if len({row[0].order_id for row in candidates}) != len(candidates):
        raise d.ArtifactIntegrityError("economic funding repeats an Order requirement")
    if evaluations is not None and (type(evaluations) is not dict or evaluations):
        raise ValueError("economic funding evaluations require a fresh opening-local dict")
    cash_rows = sources.economic_projection.cash_rows
    required = {r.key: 0 for r in cash_rows}
    buy_extra = 0
    coordinates = []
    for order, observation, terms in candidates:
        evaluation = _economic_evaluation_v1(order, observation, terms)
        if evaluations is not None:
            evaluations[order.order_id] = evaluation
        quote, market, issues, fee, reason = evaluation
        if reason is not None or (order.intent.side is d.OrderSide.BUY and sources.economic_projection.tax_shortfall.units):
            continue
        extra_p, extra_f, own_shares = _extras_v1(sources, order, market, fee)
        if order.intent.side is d.OrderSide.SELL and sources.sellability.sellable_for(order.intent.instrument_id).units + own_shares < order.intent.quantity.units:
            continue
        key = next(k for k in required if k.venue_id == order.intent.instrument_id.venue)
        required[key] += extra_p + extra_f
        if order.intent.side is d.OrderSide.BUY:
            buy_extra += extra_p + extra_f
        coordinates.append((order.order_id, quote.result.decision_id, _cent(extra_p), _cent(extra_f)))
    if (sum(required.values()) > sum(row.spendable.units for row in cash_rows)
            or buy_extra > sources.economic_projection.buy_budget.units):
        return ()
    # Phase 49 already proved the exact Journal, Book, and reservations
    # through this UTC. With no deficit in pre-tax native cash, the funding
    # planner reaches its empty result before using a transfer identity.
    if (use_checkpoint_cash and sources.at.phase.rank == 49 and sources.at.phase.code == "cn_economic_native"
            and sources.at.source_sequence.value == 0
            and sum(row.native_available.units for row in cash_rows) == sources.cash.spendable.units
            and all(0 <= required[row.key] <= row.native_available.units for row in cash_rows)):
        return ()
    at = d.SimulationInstant(sources.at.instant, d.TimelinePhase(50, "cn_economic_native"), d.SourceSequence(0))
    pair = plan_cn_portfolio_venue_funding_development_v1(journal=sources.journal,
        ledger_schema=sources.inputs.scope.ledger_schema, settlement_book=sources.settlement_book,
        order_streams=sources.order_streams, reservation_schedules=sources.reservation_schedules,
        market_rules=sources.market_rules, required_by_venue=tuple(sorted(((k, _cent(v)) for k, v in required.items()), key=lambda row: row[0].venue_id.value)),
        at=at, target_hash=d.canonical_sha256({"type": "cn_a_share_economic_funding_requirements", "schema_version": 1,
            "source_hash": _economic_sources_hash_v1(sources), "order_requirements": tuple(coordinates)}))
    spendable = {r.key: r.spendable.units for r in cash_rows}
    if any(-change.value.units > spendable[change.key] for entry in pair for change in entry.balance_changes if change.value.units < 0):
        return ()
    return pair
