"""Backtest-owned DEVELOPMENT two-venue Fill/Fee financial fan-in.

Book the already source-approved SH/SZ opening Fills through native Kernel
CashInstrumentAccounting and FeeAssessmentEngine into ONE immutable Journal.
This is NOT economic owner-log publication, real historical fee authority,
public prepare, terminal Backtest, NAV or OOS evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from crypto_quant_domain import (
    CashBalanceKey, CurrencyId, DomainId, DomainIdKind, FeeAssessment, Fill, InstrumentId,
    OrderSide, OrderStatus, PositionBalanceKey, QuantizationPolicy, SimulationInstant,
    SourceSequence, TimelinePhase, canonical_sha256,
)
from crypto_quant_trading.profiles.cn_a_share.commission_tax import (
    CnAShareMarketFeeRuleResolution, CnAShareStampDutyRuleResolution,
)
from crypto_quant_trading.fees import FinalFeeRuleSource
from crypto_quant_trading import (
    AccountingJournal, CashInstrumentAccounting, CostBasisPolicy,
    FeeAssessmentBasisEvidence, FeeAssessmentEngine, FinalFeeRuleSet,
    GenericLedger, LedgerSchema, LedgerState, OrderEventStream,
)
from crypto_quant_trading.profiles.cn_a_share.portfolio_open_risk_development_v1 import (
    CnASharePortfolioOpenRiskApprovalDevelopmentV1,
)
from .cn_a_share_portfolio_financial_core_v1 import book_native_cn_portfolio_financial_core_v1
from .cn_a_share_portfolio_next_open_development_v1 import (
    CnASharePortfolioNextOpenDevelopmentOutcomeV1,
)
from .execution import NoEligibleBarAction


def _id(kind: DomainIdKind, role: str, outcome_hash: str) -> DomainId:
    return DomainId(kind, f"{kind.prefix}_" + canonical_sha256({
        "type": "cn_a_share_portfolio_development_financial_identity",
        "role": role, "outcome_hash": outcome_hash,
    })[7:])


def _fill(step: CnASharePortfolioFinancialStepDevelopmentV1) -> Fill:
    value = step.opening.fill
    if type(value) is not Fill:
        raise ValueError("financial step lacks actual full Fill")
    return value


def _rule_ids(rule_set: FinalFeeRuleSet, source: FinalFeeRuleSource) -> tuple[str, ...]:
    return tuple(sorted(canonical_sha256(rule) for rule in rule_set.charge_rules
                        if rule.source is source))


def _at(fill: Fill, phase: int, key: str, sequence: int) -> SimulationInstant:
    return SimulationInstant(fill.execution_time, TimelinePhase(phase, key), SourceSequence(sequence))


@dataclass(frozen=True, slots=True)
class CnASharePortfolioFinancialStepDevelopmentV1:
    opening: CnASharePortfolioNextOpenDevelopmentOutcomeV1
    risk: CnASharePortfolioOpenRiskApprovalDevelopmentV1
    terminal_order: OrderEventStream
    final_fill_rules: FinalFeeRuleSet
    final_order_rules: FinalFeeRuleSet
    market_fee_resolution: CnAShareMarketFeeRuleResolution
    tax_resolution: CnAShareStampDutyRuleResolution

    def __post_init__(self) -> None:
        if (type(self.opening) is not CnASharePortfolioNextOpenDevelopmentOutcomeV1
                or type(self.risk) is not CnASharePortfolioOpenRiskApprovalDevelopmentV1
                or type(self.terminal_order) is not OrderEventStream
                or type(self.final_fill_rules) is not FinalFeeRuleSet
                or type(self.final_order_rules) is not FinalFeeRuleSet
                or type(self.market_fee_resolution) is not CnAShareMarketFeeRuleResolution
                or type(self.tax_resolution) is not CnAShareStampDutyRuleResolution):
            raise TypeError("development financial step needs exact native Fill, Order and fee rules")
        fill = self.opening.fill
        if (type(fill) is not Fill or self.opening.risk_approval_hash != self.risk.approval_hash
                or self.opening.plan_hash != self.risk.plan.plan_hash
                or self.terminal_order.order != self.risk.order
                or self.terminal_order.state is None
                or self.terminal_order.state.status is not OrderStatus.FILLED
                or tuple(record.fill for record in self.terminal_order.records
                         if record.fill is not None) != (fill,)
                or self.final_fill_rules.market_fee_policy_ref != self.risk.fee.fee_estimate.rule_set.market_fee_policy_ref
                or self.final_fill_rules.tax_policy_ref != self.risk.fee.fee_estimate.rule_set.tax_policy_ref
                or self.final_fill_rules.account_fee_schedule_ref != self.risk.fee.fee_estimate.rule_set.account_fee_schedule_ref
                or self.final_order_rules.market_fee_policy_ref != self.final_fill_rules.market_fee_policy_ref
                or self.final_order_rules.tax_policy_ref != self.final_fill_rules.tax_policy_ref
                or self.final_order_rules.account_fee_schedule_ref != self.final_fill_rules.account_fee_schedule_ref):
            raise ValueError("portfolio Fill/terminal Order/final Fee source does not bind open risk")
        market, tax = self.market_fee_resolution, self.tax_resolution
        if (any(res.venue_id != fill.venue_id or res.instrument_id != fill.instrument_id
                or res.side is not fill.side or res.effective_at != fill.execution_time
                for res in (market, tax))
                or _rule_ids(self.final_fill_rules, FinalFeeRuleSource.MARKET_FEE)
                   != tuple(sorted(canonical_sha256(rule) for rule in market.final_fill_charge_rules))
                or _rule_ids(self.final_fill_rules, FinalFeeRuleSource.TAX)
                   != (canonical_sha256(tax.final_fill_charge_rule),)
                or _rule_ids(self.final_order_rules, FinalFeeRuleSource.MARKET_FEE)
                   != (canonical_sha256(market.final_order_not_applicable_rule),)
                or _rule_ids(self.final_order_rules, FinalFeeRuleSource.TAX)
                   != (canonical_sha256(tax.final_order_not_applicable_rule),)):
            raise ValueError("portfolio venue fee resolution does not match actual Fill/Order")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_financial_step_development",
                "schema_version": 1, "opening": self.opening, "risk": self.risk,
                "terminal_order": self.terminal_order,
                "final_fill_rules": self.final_fill_rules,
                "final_order_rules": self.final_order_rules,
                "market_fee_resolution": self.market_fee_resolution,
                "tax_resolution": self.tax_resolution}


@dataclass(frozen=True, slots=True)
class CnASharePortfolioNoFillDevelopmentV1:
    """A blocked/due-to-expire Order is evidence, not a zero-fee trade."""
    stream: OrderEventStream
    outcome: CnASharePortfolioNextOpenDevelopmentOutcomeV1

    def __post_init__(self) -> None:
        if (type(self.stream) is not OrderEventStream
                or type(self.outcome) is not CnASharePortfolioNextOpenDevelopmentOutcomeV1
                or self.outcome.fill is not None
                or self.outcome.action is NoEligibleBarAction.FULL_FILL
                or self.outcome.order_stream_hash != self.stream.stream_hash
                or self.stream.state is None
                or self.stream.state.status not in {OrderStatus.ACCEPTED, OrderStatus.ACTIVE}):
            raise ValueError("blocked development Order must remain exact working stream with no Fill")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_no_fill_development", "schema_version": 1,
                "stream": self.stream, "outcome": self.outcome}

@dataclass(frozen=True, slots=True)
class CnASharePortfolioFinancialBatchDevelopmentV1:
    prior_journal_hash: str
    journal: AccountingJournal
    ledger_state: LedgerState
    fills: tuple[Fill, ...]
    fee_assessments: tuple[FeeAssessment, ...]
    blocked: tuple[CnASharePortfolioNoFillDevelopmentV1, ...] = ()
    synthetic_development_only: bool = field(default=True, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (type(self.journal) is not AccountingJournal or type(self.ledger_state) is not LedgerState
                or type(self.fills) is not tuple or not all(type(f) is Fill for f in self.fills)
                or type(self.fee_assessments) is not tuple
                or not all(type(a) is FeeAssessment for a in self.fee_assessments)
                or type(self.blocked) is not tuple
                or not all(type(value) is CnASharePortfolioNoFillDevelopmentV1 for value in self.blocked)
                or len(self.fills) not in (1, 2)
                or len(self.fills) + len(self.blocked) != 2
                or len(self.fee_assessments) != 2 * len(self.fills)
                or self.journal.entry_count < 3 * len(self.fills)
                or self.journal.cursor_at(self.journal.entry_count - 3 * len(self.fills)).prefix_hash != self.prior_journal_hash
                or GenericLedger(self.ledger_state.schema).project(self.journal) != self.ledger_state):
            raise ValueError("development two-stock Journal prefix or ledger replay mismatch")
        if any(value.amount.units < 0 for value in self.ledger_state.cash_balances):
            raise ValueError("development venue cash overspend requires atomic shared-CNY funding")

    @property
    def batch_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_financial_batch_development",
                "schema_version": 1, "prior_journal_hash": self.prior_journal_hash,
                "journal": self.journal, "ledger_state": self.ledger_state,
                "fills": self.fills, "fee_assessments": self.fee_assessments,
                "blocked": self.blocked,
                "synthetic_development_only": True, "trade_authorized": False}


def book_cn_a_share_portfolio_financial_batch_development_v1(
    *, prior_journal: AccountingJournal, ledger_schema: LedgerSchema,
    cost_basis_policy: CostBasisPolicy, notional_quantization: QuantizationPolicy,
    steps: tuple[CnASharePortfolioFinancialStepDevelopmentV1, ...],
    blocked: tuple[CnASharePortfolioNoFillDevelopmentV1, ...] = (),
) -> CnASharePortfolioFinancialBatchDevelopmentV1:
    """Atomic immutable append/replay; never publishes an economic account head."""
    if (type(prior_journal) is not AccountingJournal or type(ledger_schema) is not LedgerSchema
            or type(cost_basis_policy) is not CostBasisPolicy
            or type(notional_quantization) is not QuantizationPolicy
            or type(steps) is not tuple or len(steps) not in (1, 2)
            or type(blocked) is not tuple or len(steps) + len(blocked) != 2
            or not all(type(s) is CnASharePortfolioFinancialStepDevelopmentV1 for s in steps)
            or not all(type(b) is CnASharePortfolioNoFillDevelopmentV1 for b in blocked)):
        raise TypeError("two-stock financial batch needs exact Kernel authorities")
    ordered = tuple(sorted(steps, key=lambda step: (
        _fill(step).execution_time, str(_fill(step).instrument_id))))
    fills = tuple(_fill(step) for step in ordered)
    plan = ordered[0].risk.plan
    if (len({fill.instrument_id for fill in fills}) != len(fills)
            or {fill.venue_id.value for fill in fills}
               | {b.stream.order.intent.instrument_id.venue.value for b in blocked} != {"xshg", "xshe"}
            or any(b.outcome.plan_hash != plan.plan_hash
                   or b.stream.order.account_id != plan.account_id
                   or all(p.intent != b.stream.order.intent for p in plan.proposed)
                   or not any(res.order_id == b.stream.order.order_id
                              for res in ordered[0].risk.reservation_state.active_reservations)
                   for b in blocked)
            or {fill.order_id for fill in fills} & {b.stream.order.order_id for b in blocked}
            or len({fill.order_id for fill in fills}) != len(fills)
            or len({fill.fill_id for fill in fills}) != len(fills)
            or len({step.risk.plan.plan_hash for step in ordered}) != 1
            or len({step.risk.open_cash.reservation_state_hash for step in ordered}) != 1
            or prior_journal.journal_hash != ordered[0].risk.plan.cash.journal_hash):
        raise ValueError("financial batch is not one account/two-venue common frozen source")
    combined, after, booked_fills, assessments = book_native_cn_portfolio_financial_core_v1(
        prior_journal=prior_journal, ledger_schema=ledger_schema,
        cost_basis_policy=cost_basis_policy, notional_quantization=notional_quantization,
        steps=ordered)
    if booked_fills != fills:
        raise ValueError("native financial core changed two-stock Fill ordering")
    return CnASharePortfolioFinancialBatchDevelopmentV1(
        prior_journal.journal_hash, combined, after, booked_fills, assessments, blocked)


@dataclass(frozen=True, slots=True)
class CnASharePortfolioFinancialBatchDevelopmentV2:
    """Variable-N native accounting result; no canonical Backtest completion or NAV."""

    universe: tuple[InstrumentId, ...]
    prior_journal_hash: str
    journal: AccountingJournal
    ledger_state: LedgerState
    fills: tuple[Fill, ...]
    fee_assessments: tuple[FeeAssessment, ...]
    blocked: tuple[CnASharePortfolioNoFillDevelopmentV1, ...] = ()
    synthetic_development_only: bool = field(default=True, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        ids = self.universe
        if (type(ids) is not tuple or not ids
                or any(type(i) is not InstrumentId or i.venue.value not in {"xshg", "xshe"} for i in ids)
                or ids != tuple(sorted(set(ids), key=lambda i: (i.venue.value, i.stable_key)))
                or type(self.journal) is not AccountingJournal or type(self.ledger_state) is not LedgerState
                or type(self.fills) is not tuple or not self.fills or not all(type(f) is Fill for f in self.fills)
                or type(self.fee_assessments) is not tuple
                or not all(type(a) is FeeAssessment for a in self.fee_assessments)
                or type(self.blocked) is not tuple
                or not all(type(value) is CnASharePortfolioNoFillDevelopmentV1 for value in self.blocked)
                or len(self.fills) + len(self.blocked) != len(ids)
                or {f.instrument_id for f in self.fills}
                   | {b.stream.order.intent.instrument_id for b in self.blocked} != set(ids)
                or len(self.fee_assessments) != 2 * len(self.fills)
                or self.journal.entry_count < 3 * len(self.fills)
                or self.journal.cursor_at(self.journal.entry_count - 3 * len(self.fills)).prefix_hash
                   != self.prior_journal_hash
                or GenericLedger(self.ledger_state.schema).project(self.journal) != self.ledger_state):
            raise ValueError("variable-N financial batch native universe/Journal/fee prefix mismatch")
        if (any(value.amount.units < 0 for value in self.ledger_state.cash_balances)
                or {registration.key.instrument_id for registration in self.ledger_state.schema.registrations
                    if isinstance(registration.key, PositionBalanceKey)} != set(ids)):
            raise ValueError("variable-N financial batch venue cash or position scope mismatch")

    @property
    def batch_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_financial_batch_development",
                "schema_version": 2, "universe": self.universe,
                "prior_journal_hash": self.prior_journal_hash, "journal": self.journal,
                "ledger_state": self.ledger_state, "fills": self.fills,
                "fee_assessments": self.fee_assessments, "blocked": self.blocked,
                "synthetic_development_only": True, "trade_authorized": False}


@dataclass(frozen=True, slots=True)
class CnASharePortfolioFinancialBatchDevelopmentV3:
    """Subset actual Fills in one frozen portfolio; rejected/expired Orders are NOT Fills."""
    portfolio_scope: tuple[InstrumentId, ...]
    prior_journal_hash: str
    journal: AccountingJournal
    ledger_state: LedgerState
    fills: tuple[Fill, ...]
    fee_assessments: tuple[FeeAssessment, ...]
    synthetic_development_only: bool = field(default=True, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        scope = self.portfolio_scope
        if (type(scope) is not tuple or not scope
                or any(type(i) is not InstrumentId or i.venue.value not in {"xshg", "xshe"} for i in scope)
                or scope != tuple(sorted(set(scope), key=lambda i: (i.venue.value, i.stable_key)))
                or type(self.journal) is not AccountingJournal or type(self.ledger_state) is not LedgerState
                or type(self.fills) is not tuple or not self.fills or any(type(f) is not Fill for f in self.fills)
                or len({f.instrument_id for f in self.fills}) != len(self.fills)
                or not {f.instrument_id for f in self.fills}.issubset(scope)
                or type(self.fee_assessments) is not tuple or any(type(f) is not FeeAssessment for f in self.fee_assessments)
                or len(self.fee_assessments) != 2 * len(self.fills)
                or self.journal.entry_count < 3 * len(self.fills)
                or self.journal.cursor_at(self.journal.entry_count - 3 * len(self.fills)).prefix_hash != self.prior_journal_hash
                or GenericLedger(self.ledger_state.schema).project(self.journal) != self.ledger_state
                or any(v.amount.units < 0 for v in self.ledger_state.cash_balances)
                or {r.key.instrument_id for r in self.ledger_state.schema.registrations
                    if isinstance(r.key, PositionBalanceKey)} != set(scope)):
            raise ValueError("subset financial batch scope/Fill/fee/Journal mismatch")

    @property
    def batch_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_financial_batch_development", "schema_version": 3,
                "portfolio_scope": self.portfolio_scope, "prior_journal_hash": self.prior_journal_hash,
                "journal": self.journal, "ledger_state": self.ledger_state, "fills": self.fills,
                "fee_assessments": self.fee_assessments, "synthetic_development_only": True,
                "trade_authorized": False}


def book_cn_a_share_portfolio_financial_batch_development_v3(
    *, portfolio_scope: tuple[InstrumentId, ...], prior_journal: AccountingJournal,
    ledger_schema: LedgerSchema, cost_basis_policy: CostBasisPolicy,
    notional_quantization: QuantizationPolicy,
    steps: tuple[CnASharePortfolioFinancialStepDevelopmentV1, ...],
) -> CnASharePortfolioFinancialBatchDevelopmentV3:
    """Native monetary fan-in only; no-fill orders stay in the rotation result, uncharged."""
    if (type(steps) is not tuple or not steps or any(type(s) is not CnASharePortfolioFinancialStepDevelopmentV1 for s in steps)
            or type(prior_journal) is not AccountingJournal or type(ledger_schema) is not LedgerSchema
            or type(cost_basis_policy) is not CostBasisPolicy or type(notional_quantization) is not QuantizationPolicy):
        raise TypeError("subset financial batch requires exact native steps and ledger sources")
    ordered = tuple(sorted(steps, key=lambda s: (_fill(s).execution_time, str(_fill(s).instrument_id))))
    plan = ordered[0].risk.plan
    if (plan.cash.journal_hash != prior_journal.journal_hash
            or any(s.risk.plan.plan_hash != plan.plan_hash
                   or s.risk.plan.account_id != plan.account_id
                   or s.risk.open_cash.reservation_state_hash != ordered[0].risk.open_cash.reservation_state_hash
                   for s in ordered)):
        raise ValueError("subset financial batch mixed plan/account/reservation prefix")
    journal, ledger, fills, fees = book_native_cn_portfolio_financial_core_v1(
        prior_journal=prior_journal, ledger_schema=ledger_schema, cost_basis_policy=cost_basis_policy,
        notional_quantization=notional_quantization, steps=ordered)
    return CnASharePortfolioFinancialBatchDevelopmentV3(
        portfolio_scope, prior_journal.journal_hash, journal, ledger, fills, fees)

def book_cn_a_share_portfolio_financial_batch_development_v2(
    *, universe: tuple[InstrumentId, ...], prior_journal: AccountingJournal,
    ledger_schema: LedgerSchema, cost_basis_policy: CostBasisPolicy,
    notional_quantization: QuantizationPolicy,
    steps: tuple[CnASharePortfolioFinancialStepDevelopmentV1, ...],
    blocked: tuple[CnASharePortfolioNoFillDevelopmentV1, ...] = (),
) -> CnASharePortfolioFinancialBatchDevelopmentV2:
    """One account's N Fill/fee postings, never N single-stock simulations."""
    if (type(prior_journal) is not AccountingJournal or type(ledger_schema) is not LedgerSchema
            or type(cost_basis_policy) is not CostBasisPolicy or type(notional_quantization) is not QuantizationPolicy
            or type(universe) is not tuple or not universe
            or type(steps) is not tuple or not steps or type(blocked) is not tuple
            or not all(type(s) is CnASharePortfolioFinancialStepDevelopmentV1 for s in steps)
            or not all(type(b) is CnASharePortfolioNoFillDevelopmentV1 for b in blocked)):
        raise TypeError("variable-N financial batch needs exact native sources")
    if (len(steps) + len(blocked) != len(universe)
            or len({i for i in universe}) != len(universe)
            or len({step.opening.fill.instrument_id for step in steps if step.opening.fill is not None}
                   | {b.stream.order.intent.instrument_id for b in blocked}) != len(universe)):
        raise ValueError("variable-N financial batch incomplete or duplicate scope")
    ordered = tuple(sorted(steps, key=lambda step: (
        _fill(step).execution_time, str(_fill(step).instrument_id))))
    plan = ordered[0].risk.plan
    if (any(step.risk.plan.plan_hash != plan.plan_hash
            or step.risk.plan.account_id != plan.account_id
            or step.risk.open_cash.reservation_state_hash != ordered[0].risk.open_cash.reservation_state_hash
            for step in ordered)
            or any(b.outcome.plan_hash != plan.plan_hash or b.stream.order.account_id != plan.account_id
                   or all(p.intent != b.stream.order.intent for p in plan.proposed)
                   for b in blocked)
            or plan.cash.journal_hash != prior_journal.journal_hash):
        raise ValueError("variable-N financial batch account/plan/funding source mismatch")
    combined, after, fills, assessments = book_native_cn_portfolio_financial_core_v1(
        prior_journal=prior_journal, ledger_schema=ledger_schema,
        cost_basis_policy=cost_basis_policy, notional_quantization=notional_quantization,
        steps=ordered)
    return CnASharePortfolioFinancialBatchDevelopmentV2(
        universe, prior_journal.journal_hash, combined, after, fills, assessments, blocked)
