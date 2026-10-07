"""One native Kernel Fill/Fee/Journal fan-in shared by versioned CN portfolio batches.

Pure, source-bound DEVELOPMENT accounting. No owner publication, NAV or real fee authority.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from crypto_quant_domain import (
    CashBalanceKey, CurrencyId, DomainId, DomainIdKind, FeeAssessment, Fill,
    OrderSide, PositionBalanceKey, QuantizationPolicy, SimulationInstant,
    SourceSequence, TimelinePhase, canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal, CashInstrumentAccounting, CostBasisPolicy,
    FeeAssessmentBasisEvidence, FeeAssessmentEngine, GenericLedger, LedgerSchema,
    LedgerState,
)

if TYPE_CHECKING:
    from .cn_a_share_portfolio_financial_development_v1 import CnASharePortfolioFinancialStepDevelopmentV1
    from .cn_a_share_portfolio_standard_opening_v1 import _StandardFinancialStepV1


def _id(kind: DomainIdKind, role: str, outcome_hash: str) -> DomainId:
    return DomainId(kind, f"{kind.prefix}_" + canonical_sha256({
        "type": "cn_a_share_portfolio_development_financial_identity",
        "role": role, "outcome_hash": outcome_hash,
    })[7:])


def _at(fill: Fill, phase: int, key: str, sequence: int) -> SimulationInstant:
    return SimulationInstant(fill.execution_time, TimelinePhase(phase, key), SourceSequence(sequence))


def _fill(step: CnASharePortfolioFinancialStepDevelopmentV1 | _StandardFinancialStepV1) -> Fill:
    value = step.opening.fill
    if type(value) is not Fill:
        raise ValueError("native portfolio financial step has no typed Fill")
    return value

def book_native_cn_portfolio_financial_core_v1(
    *, prior_journal: AccountingJournal, ledger_schema: LedgerSchema,
    cost_basis_policy: CostBasisPolicy, notional_quantization: QuantizationPolicy,
    steps: tuple[CnASharePortfolioFinancialStepDevelopmentV1 | _StandardFinancialStepV1, ...],
    sell_first: bool = False,
) -> tuple[AccountingJournal, LedgerState, tuple[Fill, ...], tuple[FeeAssessment, ...]]:
    """Append all real Fills then Fill fees then Order fees atomically in one Journal."""
    if not steps or type(sell_first) is not bool:
        raise ValueError("native portfolio financial core requires Fill steps and exact ordering policy")
    ordered = tuple(sorted(steps, key=lambda step: (
        _fill(step).execution_time,
        _fill(step).side is OrderSide.BUY if sell_first else False,
        str(_fill(step).instrument_id))))
    fills = tuple(_fill(step) for step in ordered)
    ledger = GenericLedger(ledger_schema)
    prior = ledger.project(prior_journal)
    accounting = CashInstrumentAccounting()
    engine = FeeAssessmentEngine()
    fill_entries = []
    fill_fee_entries = []
    order_fee_entries = []
    assessments = []
    for sequence, step in enumerate(ordered, start=1):
        fill = _fill(step)
        cash = CashBalanceKey(fill.account_id, fill.venue_id, CurrencyId("CNY"))
        position = PositionBalanceKey(fill.account_id, fill.venue_id, fill.instrument_id)
        prior_position = tuple(value for value in prior.position_balances if value.key == position)
        if len(prior_position) > 1 or (not prior_position and fill.side is OrderSide.SELL):
            raise ValueError("financial batch has no uniquely registered sell inventory")
        booked = accounting.book_fill(
            fill=fill, cash_key=cash, position_key=position,
            open_lots=prior_position[0].lots if prior_position else (),
            cost_basis_policy=cost_basis_policy,
            notional_quantization=notional_quantization,
            journal_entry_id=_id(DomainIdKind.JOURNAL, "fill", step.opening.outcome_hash),
            recorded_at=_at(fill, 70, "accounting", sequence))
        if booked.result is None:
            raise ValueError("native portfolio Fill accounting rejected")
        fill_entries.append(booked.result.journal_entry)
        fill_fee = engine.assess(
            basis=FeeAssessmentBasisEvidence.for_fill(fill),
            rule_set=step.final_fill_rules,
            fee_assessment_id=_id(DomainIdKind.FEE, "fill_fee", step.opening.outcome_hash),
            assessment_time=fill.execution_time)
        if fill_fee.result is None:
            raise ValueError("native portfolio Fill fee assessment rejected")
        assessments.append(fill_fee.result.assessment)
        charged_fill = accounting.charge_fee(
            assessment=fill_fee.result.assessment, related_fill=fill, cash_key=cash,
            open_lots=booked.result.open_lots,
            cost_basis_policy=cost_basis_policy,
            journal_entry_id=_id(DomainIdKind.JOURNAL, "fill_fee", step.opening.outcome_hash),
            recorded_at=_at(fill, 90, "fees", sequence))
        if charged_fill.result is None:
            raise ValueError("native portfolio Fill fee Journal rejected")
        fill_fee_entries.append(charged_fill.result.journal_entry)
        order_fee = engine.assess(
            basis=FeeAssessmentBasisEvidence.for_order(step.terminal_order),
            rule_set=step.final_order_rules,
            fee_assessment_id=_id(DomainIdKind.FEE, "order_fee", step.opening.outcome_hash),
            assessment_time=fill.execution_time)
        if order_fee.result is None:
            raise ValueError("native portfolio Order fee assessment rejected")
        assessments.append(order_fee.result.assessment)
        charged_order = accounting.charge_order_fee(
            assessment=order_fee.result.assessment, order_stream=step.terminal_order,
            cash_key=cash, open_lots=charged_fill.result.open_lots,
            cost_basis_policy=cost_basis_policy,
            journal_entry_id=_id(DomainIdKind.JOURNAL, "order_fee", step.opening.outcome_hash),
            recorded_at=_at(fill, 91, "order_fee", sequence))
        if charged_order.result is None:
            raise ValueError("native portfolio Order fee Journal rejected")
        order_fee_entries.append(charged_order.result.journal_entry)
    combined = prior_journal.append_many((*fill_entries, *fill_fee_entries, *order_fee_entries))
    after = ledger.resume(combined, prior)
    if after != ledger.project(combined):
        raise ValueError("portfolio Journal replay not reproducible")
    return combined, after, fills, tuple(assessments)
