"""Variable-N single-week synthetic DEVELOPMENT Engine Case/Result; no NAV or publication."""
from __future__ import annotations

from dataclasses import dataclass, field

from crypto_quant_domain import (
    ArtifactRef, Fill, InstrumentId, Money, QuantizationPolicy, canonical_sha256,
)
from crypto_quant_market_data import MarketBundleReader, MarketEvent
from crypto_quant_trading import AccountingJournal, CostBasisPolicy, GenericLedger, LedgerSchema
from crypto_quant_trading.profiles.cn_a_share import CnAShareFrozenCalendar

from .artifact_envelope_reader import ArtifactEnvelopeReader
from .cn_a_share_portfolio_case_inputs_v8 import (
    CnASharePortfolioCaseInputV8, read_retained_cn_a_share_portfolio_case_input_v8,
)
from .cn_a_share_portfolio_engine_case_v1 import _witnesses_source
from .cn_a_share_portfolio_financial_development_v1 import (
    CnASharePortfolioFinancialBatchDevelopmentV2,
    CnASharePortfolioFinancialStepDevelopmentV1,
)
from .cn_a_share_portfolio_settlement_development_v1 import CnASharePortfolioSettlementDevelopmentV1
from .execution import BarLiquidityEvidence, BarOpenObservation
from .slippage import DeterministicBpsSlippageModel, SlippageMarketState


@dataclass(frozen=True, slots=True)
class ResolvedCnASharePortfolioExecutionCaseV2:
    source_ref: ArtifactRef
    source: CnASharePortfolioCaseInputV8
    initial_journal: AccountingJournal
    ledger_schema: LedgerSchema
    cost_basis_policy: CostBasisPolicy
    notional_quantization: QuantizationPolicy
    steps: tuple[CnASharePortfolioFinancialStepDevelopmentV1, ...]
    bars: tuple[MarketEvent, ...]
    witnesses: tuple[tuple[BarLiquidityEvidence, SlippageMarketState,
                           DeterministicBpsSlippageModel], ...]
    calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar]
    synthetic_development_only: bool = field(default=True, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (type(self.source_ref) is not ArtifactRef
                or self.source_ref.artifact_type != "backtest_execution_input_bundle"
                or self.source_ref.schema_version != 8
                or type(self.source) is not CnASharePortfolioCaseInputV8
                or type(self.initial_journal) is not AccountingJournal
                or type(self.ledger_schema) is not LedgerSchema
                or type(self.cost_basis_policy) is not CostBasisPolicy
                or type(self.notional_quantization) is not QuantizationPolicy
                or type(self.steps) is not tuple or not self.steps
                or any(type(step) is not CnASharePortfolioFinancialStepDevelopmentV1 for step in self.steps)
                or type(self.bars) is not tuple or not all(type(bar) is MarketEvent for bar in self.bars)
                or type(self.witnesses) is not tuple or len(self.witnesses) != len(self.steps)
                or type(self.calendars) is not tuple or len(self.calendars) != 2
                or not all(type(c) is CnAShareFrozenCalendar for c in self.calendars)):
            raise TypeError("variable-N Engine Case requires exact V8 and native financial witnesses")
        ids = self.source.scope.instrument_ids
        if (self.ledger_schema != self.source.scope.ledger_schema
                or len(ids) != len(self.steps) or len(ids) != len(self.bars)
                or {step.risk.order.intent.instrument_id for step in self.steps} != set(ids)
                or {bar.instrument_id for bar in self.bars} != set(ids)
                or len({step.risk.plan.plan_hash for step in self.steps}) != 1
                or any(step.risk.plan.account_id != self.source.scope.account_id for step in self.steps)
                or self.steps[0].risk.plan.cash.journal_hash != self.initial_journal.journal_hash):
            raise ValueError("variable-N Engine Case account, plan, Bar or source exact-cover mismatch")
        initial = GenericLedger(self.ledger_schema).project(self.initial_journal)
        total = sum(item.amount.units for item in initial.cash_balances)
        if Money(total, self.source.scope.initial_cash.scale, "CNY") != self.source.scope.initial_cash:
            raise ValueError("variable-N Engine initial CNY capital differs from frozen V8 Case")
        binding = {(item[0], item[1]) for item in self.source.bar_bindings}
        if len(binding) != len(ids) or {(event.event_id, event.event_hash) for event in self.bars} != binding:
            raise ValueError("variable-N Engine Bar source differs from V8 retained stream")
        for step, witness in zip(self.steps, self.witnesses, strict=True):
            if (type(witness) is not tuple or len(witness) != 3
                    or tuple(type(item) for item in witness) != (
                        BarLiquidityEvidence, SlippageMarketState, DeterministicBpsSlippageModel)):
                raise ValueError("variable-N Engine witness types mismatch")
            events = [BarOpenObservation.from_event(event) for event in self.bars
                      if event.instrument_id == step.risk.order.intent.instrument_id]
            if (len(events) != 1 or events[0].observation_hash != step.opening.observation_hash
                    or events[0].event.event_hash != step.risk.open_event_hash
                    or witness[0].market_event_hash != events[0].event.event_hash
                    or witness[1].evidence_hash != events[0].event.event_hash):
                raise ValueError("variable-N Engine witness not bound to frozen BarOpen/Fill")
        if {c.venue_id.value for c in self.calendars} != {"xshg", "xshe"}:
            raise ValueError("variable-N Engine needs two frozen venue calendars")

    @classmethod
    def from_retained_source(cls, *, source_ref: ArtifactRef,
                             reader: ArtifactEnvelopeReader, target_reader: ArtifactEnvelopeReader,
                             market_reader: MarketBundleReader, initial_journal: AccountingJournal,
                             ledger_schema: LedgerSchema, cost_basis_policy: CostBasisPolicy,
                             notional_quantization: QuantizationPolicy,
                             steps: tuple[CnASharePortfolioFinancialStepDevelopmentV1, ...],
                             bars: tuple[MarketEvent, ...],
                             witnesses: tuple[tuple[BarLiquidityEvidence, SlippageMarketState,
                                                    DeterministicBpsSlippageModel], ...],
                             calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar],
                             ) -> ResolvedCnASharePortfolioExecutionCaseV2:
        source = read_retained_cn_a_share_portfolio_case_input_v8(
            source_ref, reader=reader, target_reader=target_reader, market_reader=market_reader)
        return cls(source_ref, source, initial_journal, ledger_schema,
                   cost_basis_policy, notional_quantization, steps, bars, witnesses, calendars)

    @property
    def case_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "resolved_cn_a_share_portfolio_execution_case", "schema_version": 2,
                "source_ref": self.source_ref, "source": self.source,
                "initial_journal": self.initial_journal, "ledger_schema": self.ledger_schema,
                "cost_basis_policy": self.cost_basis_policy,
                "notional_quantization": self.notional_quantization,
                "steps": self.steps, "bars": self.bars,
                "witnesses": _witnesses_source(self.witnesses), "calendars": self.calendars,
                "synthetic_development_only": True, "trade_authorized": False}


@dataclass(frozen=True, slots=True)
class CnASharePortfolioEngineDevelopmentResultV2:
    """Native N-stock Fill/Fee/Book evidence, not daily NAV or an account owner head."""

    case_hash: str
    source_ref: ArtifactRef
    batch: CnASharePortfolioFinancialBatchDevelopmentV2
    settlement: CnASharePortfolioSettlementDevelopmentV1
    synthetic_development_only: bool = field(default=True, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (type(self.batch) is not CnASharePortfolioFinancialBatchDevelopmentV2
                or type(self.settlement) is not CnASharePortfolioSettlementDevelopmentV1
                or self.settlement.financial_batch_hash != self.batch.batch_hash
                or self.settlement.book.account_id != self.batch.journal.entries[-1].account_id
                or len(self.settlement.book.project().pending_obligations) != len(self.batch.universe)):
            raise ValueError("variable-N Engine result is not one account native Settlement/fee prefix")

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_engine_development_result", "schema_version": 2,
                "case_hash": self.case_hash, "source_ref": self.source_ref,
                "batch": self.batch, "settlement": self.settlement,
                "synthetic_development_only": True, "trade_authorized": False}
