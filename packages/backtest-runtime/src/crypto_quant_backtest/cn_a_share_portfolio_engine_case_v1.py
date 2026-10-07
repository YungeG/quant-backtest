"""Resolved CN two-stock synthetic DEVELOPMENT Case/Result for native Engine V1.

The V8 input, BarOpen/fee witnesses and account Journal are immutable. This Case
is not a public preparation, real historical source qualification or NAV grant.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from crypto_quant_domain import (
    ArtifactRef, Fill, OrderSide, PositionBalanceKey, QuantizationPolicy,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleReader, MarketEvent
from crypto_quant_trading import (
    AccountingJournal, CostBasisPolicy, GenericLedger, LedgerSchema,
)
from crypto_quant_trading.profiles.cn_a_share import CnAShareFrozenCalendar

from .artifact_envelope_reader import ArtifactEnvelopeReader
from .cn_a_share_portfolio_case_inputs_v8 import (
    CnASharePortfolioCaseInputV8, read_retained_cn_a_share_portfolio_case_input_v8,
)
from .cn_a_share_portfolio_financial_development_v1 import (
    CnASharePortfolioFinancialBatchDevelopmentV1,
    CnASharePortfolioFinancialStepDevelopmentV1,
    CnASharePortfolioNoFillDevelopmentV1,
)
from .cn_a_share_portfolio_settlement_development_v1 import CnASharePortfolioSettlementDevelopmentV1
from .execution import BarLiquidityEvidence, BarOpenObservation
from .slippage import DeterministicBpsSlippageModel, SlippageMarketState


def _witnesses_source(values: tuple[tuple[BarLiquidityEvidence, SlippageMarketState,
                                          DeterministicBpsSlippageModel], ...]) -> tuple:
    return tuple((liquidity, market_state, {
        "component_ref": slippage.component_ref,
        "calibration_ref": slippage.calibration_ref,
        "applicability_envelope": slippage.applicability_envelope,
        "basis_points_units": slippage.basis_points_units,
        "basis_points_scale": slippage.basis_points_scale.places,
        "rounding": slippage.rounding.value,
        "limitations": tuple(item.value for item in slippage.limitations),
    }) for liquidity, market_state, slippage in values)

def _fill(step: CnASharePortfolioFinancialStepDevelopmentV1) -> Fill:
    value = step.opening.fill
    if type(value) is not Fill:
        raise ValueError("portfolio Engine Case financial step has no native Fill")
    return value


@dataclass(frozen=True, slots=True)
class ResolvedCnASharePortfolioExecutionCaseV1:
    source_ref: ArtifactRef
    source: CnASharePortfolioCaseInputV8
    initial_journal: AccountingJournal
    ledger_schema: LedgerSchema
    cost_basis_policy: CostBasisPolicy
    notional_quantization: QuantizationPolicy
    first_steps: tuple[CnASharePortfolioFinancialStepDevelopmentV1, ...]
    first_bars: tuple[MarketEvent, ...]
    first_witnesses: tuple[tuple[BarLiquidityEvidence, SlippageMarketState, DeterministicBpsSlippageModel], ...]
    first_calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar]
    second_steps: tuple[CnASharePortfolioFinancialStepDevelopmentV1, ...]
    second_bars: tuple[MarketEvent, ...]
    second_witnesses: tuple[tuple[BarLiquidityEvidence, SlippageMarketState, DeterministicBpsSlippageModel], ...]
    second_calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar]
    second_blocked: tuple[CnASharePortfolioNoFillDevelopmentV1, ...] = ()
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
                or type(self.notional_quantization) is not QuantizationPolicy):
            raise TypeError("portfolio Engine Case needs exact V8/source and native financial types")
        if (type(self.first_steps) is not tuple or len(self.first_steps) != 2
                or type(self.second_steps) is not tuple or len(self.second_steps) not in (1, 2)
                or type(self.second_blocked) is not tuple
                or len(self.second_steps) + len(self.second_blocked) != 2
                or any(type(witnesses) is not tuple or len(witnesses) != len(steps)
                       or any(type(witness) is not tuple or len(witness) != 3
                              or tuple(type(value) for value in witness) != (
                                  BarLiquidityEvidence, SlippageMarketState, DeterministicBpsSlippageModel)
                              for witness in witnesses)
                       for witnesses, steps in ((self.first_witnesses, self.first_steps),
                                                (self.second_witnesses, self.second_steps)))
                or any(type(step) is not CnASharePortfolioFinancialStepDevelopmentV1
                       for step in (*self.first_steps, *self.second_steps))
                or any(type(step) is not CnASharePortfolioNoFillDevelopmentV1 for step in self.second_blocked)
                or any(type(values) is not tuple or len(values) != 2 or
                       not all(type(value) is expected for value in values)
                       for values, expected in ((self.first_bars, MarketEvent),
                                                (self.second_bars, MarketEvent),
                                                (self.first_calendars, CnAShareFrozenCalendar),
                                                (self.second_calendars, CnAShareFrozenCalendar)))):
            raise TypeError("portfolio Engine Case needs two venue Bar/calendars and exact step coverage")
        if self.source.scope.ledger_schema != self.ledger_schema:
            raise ValueError("portfolio Engine Case LedgerSchema differs from retained V8 input")
        if (len({registration.key.account_id for registration in self.ledger_schema.cash_registrations}) != 1
                or self.initial_journal.journal_hash != self.first_steps[0].risk.plan.cash.journal_hash):
            raise ValueError("portfolio Engine Case account/initial Journal source mismatch")
        account = self.source.scope.account_id
        plans = tuple(step.risk.plan for step in (*self.first_steps, *self.second_steps))
        if (any(plan.account_id != account for plan in plans)
                or len({plan.plan_hash for plan in (self.first_steps[0].risk.plan,
                                                   self.first_steps[1].risk.plan)}) != 1
                or len({step.risk.plan.plan_hash for step in self.second_steps}) != 1
                or self.first_steps[0].risk.plan.target_id == self.second_steps[0].risk.plan.target_id):
            raise ValueError("portfolio Engine Case W/W+1 plan, cash or target lineage mismatch")
        first_fills = tuple(_fill(step) for step in self.first_steps)
        second_fills = tuple(_fill(step) for step in self.second_steps)
        if (any(fill.side is not OrderSide.BUY for fill in first_fills)
                or any(fill.side is not OrderSide.SELL for fill in second_fills)
                or not max(fill.execution_time for fill in first_fills)
                    < min(fill.execution_time for fill in second_fills)
                or {fill.instrument_id for fill in first_fills} != set(self.source.scope.instrument_ids)
                or {bar.instrument_id for bar in self.first_bars} != set(self.source.scope.instrument_ids)
                or {bar.instrument_id for bar in self.second_bars} != set(self.source.scope.instrument_ids)):
            raise ValueError("portfolio Engine Case not two sorted distinct weeks/instruments/sides")
        binding = {(item[0], item[1]) for item in self.source.bar_bindings}
        events = (*self.first_bars, *self.second_bars)
        if len(binding) != 4 or {(e.event_id, e.event_hash) for e in events} != binding:
            raise ValueError("portfolio Engine Case Bar events differ from retained V8 source")
        for steps, bars, witnesses in ((self.first_steps, self.first_bars, self.first_witnesses),
                                       (self.second_steps, self.second_bars, self.second_witnesses)):
            for step, witness in zip(steps, witnesses, strict=True):
                matches = [BarOpenObservation.from_event(event) for event in bars
                           if event.instrument_id == _fill(step).instrument_id]
                if (len(matches) != 1 or matches[0].observation_hash != step.opening.observation_hash
                        or matches[0].event.event_hash != step.risk.open_event_hash
                        or witness[0].market_event_hash != matches[0].event.event_hash
                        or witness[1].evidence_hash != matches[0].event.event_hash):
                    raise ValueError("portfolio Engine Case Fill/risk does not bind BarOpen source")
        for blocked in self.second_blocked:
            matches = [BarOpenObservation.from_event(event) for event in self.second_bars
                       if event.instrument_id == blocked.stream.order.intent.instrument_id]
            if len(matches) != 1 or matches[0].observation_hash != blocked.outcome.observation_hash:
                raise ValueError("portfolio Engine Case blocked Order lacks exact gap source")
        for calendars, bars in ((self.first_calendars, self.first_bars),
                                (self.second_calendars, self.second_bars)):
            if {calendar.venue_id.value for calendar in calendars} != {"xshg", "xshe"} or (
                {bar.instrument_id.venue.value for bar in bars if bar.instrument_id is not None}
                != {"xshg", "xshe"}):
                raise ValueError("portfolio Engine Case frozen calendar/Bar venue mismatch")

    @classmethod
    def from_retained_source(cls, *, source_ref: ArtifactRef,
                             reader: ArtifactEnvelopeReader, target_reader: ArtifactEnvelopeReader,
                             market_reader: MarketBundleReader, initial_journal: AccountingJournal,
                             ledger_schema: LedgerSchema, cost_basis_policy: CostBasisPolicy,
                             notional_quantization: QuantizationPolicy,
                             first_steps: tuple[CnASharePortfolioFinancialStepDevelopmentV1, ...],
                             first_bars: tuple[MarketEvent, ...],
                             first_witnesses: tuple[tuple[BarLiquidityEvidence, SlippageMarketState, DeterministicBpsSlippageModel], ...],
                             first_calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar],
                             second_steps: tuple[CnASharePortfolioFinancialStepDevelopmentV1, ...],
                             second_bars: tuple[MarketEvent, ...],
                             second_witnesses: tuple[tuple[BarLiquidityEvidence, SlippageMarketState, DeterministicBpsSlippageModel], ...],
                             second_calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar],
                             second_blocked: tuple[CnASharePortfolioNoFillDevelopmentV1, ...] = (),
                             ) -> ResolvedCnASharePortfolioExecutionCaseV1:
        source = read_retained_cn_a_share_portfolio_case_input_v8(
            source_ref, reader=reader, target_reader=target_reader, market_reader=market_reader)
        return cls(source_ref, source, initial_journal, ledger_schema, cost_basis_policy,
                   notional_quantization, first_steps, first_bars, first_witnesses, first_calendars,
                   second_steps, second_bars, second_witnesses, second_calendars, second_blocked)

    @property
    def case_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "resolved_cn_a_share_portfolio_execution_case", "schema_version": 1,
                "source_ref": self.source_ref, "source": self.source,
                "initial_journal": self.initial_journal, "ledger_schema": self.ledger_schema,
                "cost_basis_policy": self.cost_basis_policy,
                "notional_quantization": self.notional_quantization,
                "first_steps": self.first_steps, "first_bars": self.first_bars,
                "first_witnesses": _witnesses_source(self.first_witnesses),
                "first_calendars": self.first_calendars,
                "second_steps": self.second_steps, "second_bars": self.second_bars,
                "second_witnesses": _witnesses_source(self.second_witnesses),
                "second_calendars": self.second_calendars,
                "second_blocked": self.second_blocked, "synthetic_development_only": True,
                "trade_authorized": False}


@dataclass(frozen=True, slots=True)
class CnASharePortfolioEngineDevelopmentResultV1:
    case_hash: str
    source_ref: ArtifactRef
    first_batch: CnASharePortfolioFinancialBatchDevelopmentV1
    first_settlement: CnASharePortfolioSettlementDevelopmentV1
    matured_first_settlement: CnASharePortfolioSettlementDevelopmentV1
    second_batch: CnASharePortfolioFinancialBatchDevelopmentV1
    second_settlement: CnASharePortfolioSettlementDevelopmentV1
    synthetic_development_only: bool = field(default=True, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (type(self.first_batch) is not CnASharePortfolioFinancialBatchDevelopmentV1
                or type(self.second_batch) is not CnASharePortfolioFinancialBatchDevelopmentV1
                or type(self.first_settlement) is not CnASharePortfolioSettlementDevelopmentV1
                or type(self.matured_first_settlement) is not CnASharePortfolioSettlementDevelopmentV1
                or type(self.second_settlement) is not CnASharePortfolioSettlementDevelopmentV1
                or self.second_batch.prior_journal_hash != self.first_batch.journal.journal_hash
                or self.second_batch.journal.cursor_at(self.first_batch.journal.entry_count).prefix_hash
                   != self.first_batch.journal.journal_hash
                or self.first_settlement.financial_batch_hash != self.first_batch.batch_hash
                or self.second_settlement.financial_batch_hash != self.second_batch.batch_hash
                or self.matured_first_settlement.book.cursor_at(self.first_settlement.book.event_count).prefix_hash
                   != self.first_settlement.book.book_hash
                or GenericLedger(self.first_batch.ledger_state.schema).resume(
                    self.second_batch.journal, self.first_batch.ledger_state) != self.second_batch.ledger_state):
            raise ValueError("portfolio Engine result must be one Journal and native T+1 Book prefix")

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_engine_development_result", "schema_version": 1,
                "case_hash": self.case_hash, "source_ref": self.source_ref,
                "first_batch": self.first_batch, "first_settlement": self.first_settlement,
                "matured_first_settlement": self.matured_first_settlement,
                "second_batch": self.second_batch, "second_settlement": self.second_settlement,
                "synthetic_development_only": True, "trade_authorized": False}
