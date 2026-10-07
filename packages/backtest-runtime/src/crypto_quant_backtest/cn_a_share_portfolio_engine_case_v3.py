"""Two-week variable-N paired-arm synthetic DEVELOPMENT Case, not a NAV or public run."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from crypto_quant_domain import (
    ArtifactRef, Fill, InstrumentId, Money, OrderSide, QuantizationPolicy,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleReader, MarketEvent
from crypto_quant_trading import (
    AccountingJournal, CostBasisPolicy, GenericLedger, LedgerSchema,
    OrderEventStream, SettlementBook,
)
from crypto_quant_trading.profiles.cn_a_share import CnAShareFrozenCalendar

from .artifact_envelope_reader import ArtifactEnvelopeReader
from .cn_a_share_portfolio_case_inputs_v8 import (
    CnASharePortfolioCaseInputV8, read_retained_cn_a_share_portfolio_case_input_v8,
)
from .cn_a_share_portfolio_engine_case_v1 import _fill, _witnesses_source
from .cn_a_share_portfolio_financial_development_v1 import (
    CnASharePortfolioFinancialBatchDevelopmentV2,
    CnASharePortfolioFinancialStepDevelopmentV1,
    CnASharePortfolioNoFillDevelopmentV1,
)
from .cn_a_share_portfolio_settlement_development_v1 import CnASharePortfolioSettlementDevelopmentV1
from .execution import BarLiquidityEvidence, BarOpenObservation
from .slippage import DeterministicBpsSlippageModel, SlippageMarketState
from .target_repository import BacktestTargetStreamRepository
from .target_stream import PrecomputedTargetStream

_Witnesses = tuple[tuple[BarLiquidityEvidence, SlippageMarketState,
                         DeterministicBpsSlippageModel], ...]


def _target_codes(event: MarketEvent) -> tuple[InstrumentId, ...]:
    candidate = event.payload.get("candidate")
    if not isinstance(candidate, Mapping) or not isinstance(candidate.get("targets"), (tuple, list)):
        raise ValueError("paired weekly target source missing")
    raw = candidate["targets"]
    codes = []
    for item in raw:
        if not isinstance(item, Mapping) or not isinstance(item.get("instrument_id"), Mapping):
            raise ValueError("paired weekly target instrument malformed")
        source = item["instrument_id"]
        from crypto_quant_domain import VenueId
        codes.append(InstrumentId(VenueId(source["venue"]), source["stable_key"]))
    if len(set(codes)) != len(codes):
        raise ValueError("paired weekly target contains duplicate stocks")
    return tuple(sorted(codes, key=lambda i: (i.venue.value, i.stable_key)))


@dataclass(frozen=True, slots=True)
class ResolvedCnASharePortfolioExecutionCaseV3:
    source_ref: ArtifactRef
    source: CnASharePortfolioCaseInputV8
    target_stream_key: str
    target_events: tuple[MarketEvent, MarketEvent]
    account_arm: str
    initial_journal: AccountingJournal
    ledger_schema: LedgerSchema
    cost_basis_policy: CostBasisPolicy
    notional_quantization: QuantizationPolicy
    first_steps: tuple[CnASharePortfolioFinancialStepDevelopmentV1, ...]
    first_bars: tuple[MarketEvent, ...]
    first_witnesses: _Witnesses
    first_calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar]
    second_steps: tuple[CnASharePortfolioFinancialStepDevelopmentV1, ...]
    second_bars: tuple[MarketEvent, ...]
    second_witnesses: _Witnesses
    second_calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar]
    second_blocked: tuple[CnASharePortfolioNoFillDevelopmentV1, ...] = ()
    synthetic_development_only: bool = field(default=True, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (type(self.source_ref) is not ArtifactRef or self.source_ref.artifact_type != "backtest_execution_input_bundle"
                or self.source_ref.schema_version != 8 or type(self.source) is not CnASharePortfolioCaseInputV8
                or self.account_arm not in {"A", "B"} or type(self.initial_journal) is not AccountingJournal
                or type(self.ledger_schema) is not LedgerSchema or type(self.cost_basis_policy) is not CostBasisPolicy
                or type(self.notional_quantization) is not QuantizationPolicy
                or type(self.first_steps) is not tuple or type(self.second_steps) is not tuple
                or type(self.second_blocked) is not tuple
                or any(type(s) is not CnASharePortfolioFinancialStepDevelopmentV1
                       for s in (*self.first_steps, *self.second_steps))
                or any(type(s) is not CnASharePortfolioNoFillDevelopmentV1 for s in self.second_blocked)):
            raise TypeError("paired weekly Case needs exact V8 and native account/fee facts")
        ids = self.source.scope.instrument_ids
        if (not ids or self.ledger_schema != self.source.scope.ledger_schema
                or len(self.first_steps) != len(ids) or len(self.first_bars) != len(ids)
                or len(self.second_bars) != len(ids)
                or len(self.first_witnesses) != len(ids)
                or self.account_arm == "A" and (self.second_steps or self.second_blocked or self.second_witnesses)
                or self.account_arm == "B" and (not self.second_steps
                   or len(self.second_steps) + len(self.second_blocked) != len(ids)
                   or len(self.second_witnesses) != len(self.second_steps))):
            raise ValueError("paired weekly Case active/cash target coverage mismatch")
        if type(self.target_events) is not tuple or len(self.target_events) != 2 or not all(
                type(e) is MarketEvent for e in self.target_events):
            raise TypeError("paired weekly Case requires two retained target snapshots")
        if PrecomputedTargetStream(self.target_stream_key, self.target_events).target_stream_digest != self.source.target_stream_digest:
            raise ValueError("paired weekly Case target digest differs from CAS")
        first_target, second_target = self.target_events
        if (_target_codes(first_target) != ids or
                _target_codes(second_target) != (() if self.account_arm == "B" else ids)):
            raise ValueError("paired weekly Case not one W stock list with B cash/A hold")
        phase = second_target.payload.get("candidate")
        evidence = phase.get("evidence") if isinstance(phase, Mapping) else None
        if not isinstance(evidence, Mapping) or evidence.get("industry_phase_confirmed") != "transition":
            raise ValueError("paired weekly non-bull phase not frozen before target")
        first_at = min(e.event_time for e in self.first_bars)
        second_at = min(e.event_time for e in self.second_bars)
        if (first_at >= second_at or first_target.event_time >= first_at
                or second_target.event_time <= max(e.event_time for e in self.first_bars)
                or second_target.event_time >= second_at):
            raise ValueError("paired weekly Case target causes next-week opens only")
        if len({first_target.event_id, second_target.event_id}) != 2:
            raise ValueError("paired weekly target identities not unique")
        bindings = {(v[0], v[1]) for v in self.source.bar_bindings}
        bars = (*self.first_bars, *self.second_bars)
        if len(bindings) != 2 * len(ids) or bindings != {(bar.event_id, bar.event_hash) for bar in bars}:
            raise ValueError("paired weekly Case Bar source not exact two-week cover")
        for steps, observed, witnesses in ((self.first_steps, self.first_bars, self.first_witnesses),
                                           (self.second_steps, self.second_bars, self.second_witnesses)):
            if len({step.risk.plan.plan_hash for step in steps}) > 1:
                raise ValueError("paired weekly Case mixed plan in one snapshot")
            for step, witness in zip(steps, witnesses, strict=True):
                fill = step.opening.fill
                found = [BarOpenObservation.from_event(event) for event in observed
                         if event.instrument_id == step.risk.order.intent.instrument_id]
                if (type(fill) is not Fill or len(found) != 1
                        or found[0].observation_hash != step.opening.observation_hash
                        or found[0].event.event_hash != step.risk.open_event_hash
                        or witness[0].market_event_hash != found[0].event.event_hash
                        or witness[1].evidence_hash != found[0].event.event_hash):
                    raise ValueError("paired weekly Fill/fee witness not bound to frozen open")
        if ({s.risk.order.intent.instrument_id for s in self.first_steps} != set(ids)
                or any(_fill(s).side is not OrderSide.BUY for s in self.first_steps)
                or any(_fill(s).side is not OrderSide.SELL for s in self.second_steps)
                or self.first_steps[0].risk.plan.cash.journal_hash != self.initial_journal.journal_hash
                or any(s.risk.plan.account_id != self.source.scope.account_id
                       for s in (*self.first_steps, *self.second_steps))):
            raise ValueError("paired weekly Case money/side/account mismatch")
        ledger = GenericLedger(self.ledger_schema).project(self.initial_journal)
        if (Money(sum(v.amount.units for v in ledger.cash_balances),
                  self.source.scope.initial_cash.scale, "CNY") != self.source.scope.initial_cash
                or any({c.venue_id.value for c in calendars} != {"xshg", "xshe"}
                       for calendars in (self.first_calendars, self.second_calendars))):
            raise ValueError("paired weekly Case capital or calendars differ from V8 source")
        for step in self.second_blocked:
            matches = [BarOpenObservation.from_event(e) for e in self.second_bars
                       if e.instrument_id == step.stream.order.intent.instrument_id]
            if len(matches) != 1 or matches[0].observation_hash != step.outcome.observation_hash:
                raise ValueError("paired weekly blocked GTC has no source gap")

    @classmethod
    def from_retained_source(cls, *, source_ref: ArtifactRef, reader: ArtifactEnvelopeReader,
                             target_reader: ArtifactEnvelopeReader, market_reader: MarketBundleReader,
                             account_arm: str, initial_journal: AccountingJournal, ledger_schema: LedgerSchema,
                             cost_basis_policy: CostBasisPolicy, notional_quantization: QuantizationPolicy,
                             first_steps: tuple[CnASharePortfolioFinancialStepDevelopmentV1, ...],
                             first_bars: tuple[MarketEvent, ...], first_witnesses: _Witnesses,
                             first_calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar],
                             second_steps: tuple[CnASharePortfolioFinancialStepDevelopmentV1, ...],
                             second_bars: tuple[MarketEvent, ...], second_witnesses: _Witnesses,
                             second_calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar],
                             second_blocked: tuple[CnASharePortfolioNoFillDevelopmentV1, ...] = (),
                             ) -> ResolvedCnASharePortfolioExecutionCaseV3:
        source = read_retained_cn_a_share_portfolio_case_input_v8(
            source_ref, reader=reader, target_reader=target_reader, market_reader=market_reader)
        target = BacktestTargetStreamRepository(reader=target_reader).load(source.scope.target_stream_ref)
        events = target.target_stream.events
        if len(events) != 2:
            raise ValueError("paired weekly target CAS needs two complete weekly snapshots")
        return cls(source_ref, source, target.target_stream.stream_key, (events[0], events[1]), account_arm,
                   initial_journal, ledger_schema, cost_basis_policy, notional_quantization,
                   first_steps, first_bars, first_witnesses, first_calendars,
                   second_steps, second_bars, second_witnesses, second_calendars, second_blocked)

    @property
    def case_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "resolved_cn_a_share_portfolio_execution_case", "schema_version": 3,
                "source_ref": self.source_ref, "source": self.source,
                "target_stream_key": self.target_stream_key, "target_events": self.target_events,
                "account_arm": self.account_arm, "initial_journal": self.initial_journal,
                "ledger_schema": self.ledger_schema, "cost_basis_policy": self.cost_basis_policy,
                "notional_quantization": self.notional_quantization,
                "first_steps": self.first_steps, "first_bars": self.first_bars,
                "first_witnesses": _witnesses_source(self.first_witnesses),
                "first_calendars": self.first_calendars,
                "second_steps": self.second_steps, "second_bars": self.second_bars,
                "second_witnesses": _witnesses_source(self.second_witnesses),
                "second_calendars": self.second_calendars,
                "second_blocked": self.second_blocked,
                "synthetic_development_only": True, "trade_authorized": False}


@dataclass(frozen=True, slots=True)
class CnASharePortfolioEngineDevelopmentResultV3:
    case_hash: str
    source_ref: ArtifactRef
    account_arm: str
    first_batch: CnASharePortfolioFinancialBatchDevelopmentV2
    first_settlement: CnASharePortfolioSettlementDevelopmentV1
    matured_first_settlement: CnASharePortfolioSettlementDevelopmentV1
    second_batch: CnASharePortfolioFinancialBatchDevelopmentV2 | None
    second_settlement: CnASharePortfolioSettlementDevelopmentV1 | None
    synthetic_development_only: bool = field(default=True, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (type(self.first_batch) is not CnASharePortfolioFinancialBatchDevelopmentV2
                or type(self.first_settlement) is not CnASharePortfolioSettlementDevelopmentV1
                or type(self.matured_first_settlement) is not CnASharePortfolioSettlementDevelopmentV1
                or self.first_settlement.financial_batch_hash != self.first_batch.batch_hash
                or self.matured_first_settlement.book.cursor_at(self.first_settlement.book.event_count).prefix_hash
                   != self.first_settlement.book.book_hash):
            raise ValueError("paired weekly Result lacks native first Journal/T+1 prefix")
        if self.account_arm == "A":
            if self.second_batch is not None or self.second_settlement is not None:
                raise ValueError("A hold must not invent a week2 Fill")
        elif self.account_arm == "B":
            if (type(self.second_batch) is not CnASharePortfolioFinancialBatchDevelopmentV2
                    or type(self.second_settlement) is not CnASharePortfolioSettlementDevelopmentV1
                    or self.second_batch.prior_journal_hash != self.first_batch.journal.journal_hash
                    or self.second_batch.journal.cursor_at(self.first_batch.journal.entry_count).prefix_hash
                       != self.first_batch.journal.journal_hash
                    or self.second_settlement.financial_batch_hash != self.second_batch.batch_hash
                    or GenericLedger(self.first_batch.ledger_state.schema).resume(
                        self.second_batch.journal, self.first_batch.ledger_state) != self.second_batch.ledger_state):
                raise ValueError("B cash does not have one account Journal/Settlement prefix")
        else:
            raise ValueError("paired weekly Result arm must be A or B")

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_engine_development_result", "schema_version": 3,
                "case_hash": self.case_hash, "source_ref": self.source_ref,
                "account_arm": self.account_arm, "first_batch": self.first_batch,
                "first_settlement": self.first_settlement,
                "matured_first_settlement": self.matured_first_settlement,
                "second_batch": self.second_batch, "second_settlement": self.second_settlement,
                "synthetic_development_only": True, "trade_authorized": False}
