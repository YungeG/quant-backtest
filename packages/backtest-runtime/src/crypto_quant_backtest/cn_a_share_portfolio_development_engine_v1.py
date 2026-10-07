"""Profile-owned CN portfolio DEVELOPMENT execution; no generic-Engine market dispatch.

Rehomes the existing native replay/fill/fee/Journal/T+1 implementation unchanged.
This executor handles only the exact synthetic diagnostic Case versions. It is
not historical source admission, canonical economic publication, NAV or live.
"""
from __future__ import annotations

from dataclasses import dataclass

from crypto_quant_domain import OrderEventType, PositionBalanceKey, canonical_sha256
from crypto_quant_market_data import MarketEvent
from crypto_quant_trading import JournalError, OrderEventStream, SettlementBookError

from .cn_a_share_portfolio_engine_case_v1 import (
    CnASharePortfolioEngineDevelopmentResultV1, ResolvedCnASharePortfolioExecutionCaseV1,
)
from .cn_a_share_portfolio_engine_case_v2 import (
    CnASharePortfolioEngineDevelopmentResultV2, ResolvedCnASharePortfolioExecutionCaseV2,
)
from .cn_a_share_portfolio_engine_case_v3 import (
    CnASharePortfolioEngineDevelopmentResultV3, ResolvedCnASharePortfolioExecutionCaseV3,
)
from .cn_a_share_portfolio_financial_development_v1 import (
    CnASharePortfolioFinancialStepDevelopmentV1,
    book_cn_a_share_portfolio_financial_batch_development_v1,
    book_cn_a_share_portfolio_financial_batch_development_v2,
)
from .cn_a_share_portfolio_next_open_development_v1 import evaluate_cn_a_share_portfolio_next_open_development_v1
from .cn_a_share_portfolio_settlement_development_v1 import (
    build_cn_a_share_portfolio_settlement_development_v1,
    build_cn_a_share_portfolio_settlement_development_v2,
)
from .engine import (
    EngineCancellationRequest, EngineExecutionOutcome, EngineFailure, EngineFailureCode, ExecutionTrace,
)
from .execution import BarLiquidityEvidence, BarOpenObservation
from .slippage import DeterministicBpsSlippageModel, SlippageMarketState


@dataclass(frozen=True, slots=True)
class CnASharePortfolioEngineOutcomeV1(EngineExecutionOutcome):
    portfolio_result: CnASharePortfolioEngineDevelopmentResultV1 | None = None
    portfolio_result_v2: CnASharePortfolioEngineDevelopmentResultV2 | None = None
    portfolio_result_v3: CnASharePortfolioEngineDevelopmentResultV3 | None = None

    def __post_init__(self) -> None:
        if sum(value is not None for value in (
            self.result, self.input_validation_failure, self.engine_failure, self.cancellation,
            self.portfolio_result, self.portfolio_result_v2, self.portfolio_result_v3,
        )) != 1:
            raise ValueError("Engine outcome requires exactly one branch")

    def to_canonical_dict(self) -> dict[str, object]:
        # Preserve the already retained diagnostic outcome representation.
        return {**EngineExecutionOutcome.to_canonical_dict(self),
                **({"portfolio_result": self.portfolio_result} if self.portfolio_result is not None else {}),
                **({"portfolio_result_v2": self.portfolio_result_v2} if self.portfolio_result_v2 is not None else {}),
                **({"portfolio_result_v3": self.portfolio_result_v3} if self.portfolio_result_v3 is not None else {})}


class CnASharePortfolioDevelopmentEngineV1:
    """Explicit profile-selected native executor; never selected by generic Engine."""

    def run(
        self, case: ResolvedCnASharePortfolioExecutionCaseV1 | ResolvedCnASharePortfolioExecutionCaseV2 | ResolvedCnASharePortfolioExecutionCaseV3,
        *, cancellation: EngineCancellationRequest | None = None,
    ) -> CnASharePortfolioEngineOutcomeV1:
        if type(case) not in (ResolvedCnASharePortfolioExecutionCaseV1,
                              ResolvedCnASharePortfolioExecutionCaseV2,
                              ResolvedCnASharePortfolioExecutionCaseV3):
            raise TypeError("portfolio DEVELOPMENT executor needs an exact supported Case")
        if cancellation is not None:
            raise TypeError("portfolio DEVELOPMENT cancellation requires a versioned terminal branch")
        try:
            if type(case) is ResolvedCnASharePortfolioExecutionCaseV3:
                return CnASharePortfolioEngineOutcomeV1(portfolio_result_v3=self._execute_cn_portfolio_v3(case))
            if type(case) is ResolvedCnASharePortfolioExecutionCaseV2:
                return CnASharePortfolioEngineOutcomeV1(portfolio_result_v2=self._execute_cn_portfolio_v2(case))
            if type(case) is ResolvedCnASharePortfolioExecutionCaseV1:
                return CnASharePortfolioEngineOutcomeV1(portfolio_result=self._execute_cn_portfolio(case))
            raise TypeError("unsupported portfolio DEVELOPMENT Case")
        except (JournalError, SettlementBookError, TypeError, ValueError) as error:
            trace = ExecutionTrace()
            return CnASharePortfolioEngineOutcomeV1(engine_failure=EngineFailure(
                EngineFailureCode.CASE_EVIDENCE_MISMATCH, case.case_hash, trace.trace_hash,
                (type(error).__name__,), (canonical_sha256({"error_type": type(error).__name__}),)))

    @staticmethod
    def _replay_cn_portfolio_steps(
        steps: tuple[CnASharePortfolioFinancialStepDevelopmentV1, ...],
        bars: tuple[MarketEvent, ...],
        witnesses: tuple[tuple[BarLiquidityEvidence, SlippageMarketState,
                               DeterministicBpsSlippageModel], ...],
    ) -> None:
        # The Engine re-simulates each native Fill from the exact accepted Order prefix.
        for step, witness in zip(steps, witnesses, strict=True):
            records = step.terminal_order.records
            if not records or records[-1].event.event_type is not OrderEventType.ORDER_FILLED:
                raise ValueError("portfolio terminal Order has no actual Fill event")
            prefixes = tuple(OrderEventStream.from_records(step.terminal_order.order, records[:size])
                             for size in range(1, len(records)))
            matching = tuple(prefix for prefix in prefixes
                             if prefix.stream_hash == step.opening.order_stream_hash)
            if len(matching) != 1:
                raise ValueError("portfolio Fill does not bind unique pre-fill Order prefix")
            observed = [BarOpenObservation.from_event(e) for e in bars
                        if e.instrument_id == step.risk.order.intent.instrument_id]
            if len(observed) != 1:
                raise ValueError("portfolio Fill has no unique retained BarOpen")
            replayed = evaluate_cn_a_share_portfolio_next_open_development_v1(
                plan=step.risk.plan, stream=matching[0], observation=observed[0],
                risk=step.risk, liquidity=witness[0], market_state=witness[1],
                slippage_model=witness[2], eligibility_window_exhausted=True)
            if replayed != step.opening:
                raise ValueError("portfolio native Fill differs from frozen Bar/Order/risk source")

    @staticmethod
    def _execute_cn_portfolio(
        case: ResolvedCnASharePortfolioExecutionCaseV1,
    ) -> CnASharePortfolioEngineDevelopmentResultV1:
        from .cn_a_share_portfolio_engine_case_v1 import CnASharePortfolioEngineDevelopmentResultV1

        for steps, bars, witnesses in ((case.first_steps, case.first_bars, case.first_witnesses),
                                       (case.second_steps, case.second_bars, case.second_witnesses)):
            CnASharePortfolioDevelopmentEngineV1._replay_cn_portfolio_steps(steps, bars, witnesses)
        for blocked in case.second_blocked:
            matches = [BarOpenObservation.from_event(e) for e in case.second_bars
                       if e.instrument_id == blocked.stream.order.intent.instrument_id]
            if len(matches) != 1 or evaluate_cn_a_share_portfolio_next_open_development_v1(
                plan=case.second_steps[0].risk.plan, stream=blocked.stream,
                observation=matches[0], risk=None, liquidity=None,
                market_state=None, slippage_model=None,
                eligibility_window_exhausted=True) != blocked.outcome:
                raise ValueError("portfolio blocked Order/gap not native-replayable")
        first = book_cn_a_share_portfolio_financial_batch_development_v1(
            prior_journal=case.initial_journal, ledger_schema=case.ledger_schema,
            cost_basis_policy=case.cost_basis_policy, notional_quantization=case.notional_quantization,
            steps=case.first_steps)
        first_book = build_cn_a_share_portfolio_settlement_development_v1(
            batch=first, calendars=case.first_calendars)
        pending = first_book.book.project().pending_obligations
        if (len(pending) != 2 or not all(isinstance(p.balance_key, PositionBalanceKey)
                                         for p in pending)):
            raise ValueError("portfolio first week lacks two T+1 position obligations")
        due = max(p.obligation.settlement_time for p in pending)
        if min(step.opening.fill.execution_time for step in case.second_steps if step.opening.fill) < due:
            raise ValueError("portfolio next-week sell precedes native T+1 maturity")
        matured = first_book.apply_due(due)
        second_plan = case.second_steps[0].risk.plan
        state = matured.book.project()
        if (second_plan.cash.journal_hash != first.journal.journal_hash
                or second_plan.cash.settlement_state_hash != state.state_hash
                or second_plan.sellability.settlement_state_hash != state.state_hash
                or second_plan.as_of < due):
            raise ValueError("portfolio next-week Order spends foreign/future funding or T+1 prefix")
        second = book_cn_a_share_portfolio_financial_batch_development_v1(
            prior_journal=first.journal, ledger_schema=case.ledger_schema,
            cost_basis_policy=case.cost_basis_policy, notional_quantization=case.notional_quantization,
            steps=case.second_steps, blocked=case.second_blocked)
        second_book = build_cn_a_share_portfolio_settlement_development_v1(
            batch=second, calendars=case.second_calendars)
        return CnASharePortfolioEngineDevelopmentResultV1(
            case.case_hash, case.source_ref, first, first_book, matured, second, second_book)

    @staticmethod
    def _execute_cn_portfolio_v2(
        case: ResolvedCnASharePortfolioExecutionCaseV2,
    ) -> CnASharePortfolioEngineDevelopmentResultV2:
        from .cn_a_share_portfolio_engine_case_v2 import CnASharePortfolioEngineDevelopmentResultV2

        CnASharePortfolioDevelopmentEngineV1._replay_cn_portfolio_steps(case.steps, case.bars, case.witnesses)
        batch = book_cn_a_share_portfolio_financial_batch_development_v2(
            universe=case.source.scope.instrument_ids,
            prior_journal=case.initial_journal, ledger_schema=case.ledger_schema,
            cost_basis_policy=case.cost_basis_policy,
            notional_quantization=case.notional_quantization, steps=case.steps)
        settlement = build_cn_a_share_portfolio_settlement_development_v2(
            batch=batch, calendars=case.calendars)
        return CnASharePortfolioEngineDevelopmentResultV2(
            case.case_hash, case.source_ref, batch, settlement)

    @staticmethod
    def _execute_cn_portfolio_v3(
        case: ResolvedCnASharePortfolioExecutionCaseV3,
    ) -> CnASharePortfolioEngineDevelopmentResultV3:
        from .cn_a_share_portfolio_engine_case_v3 import CnASharePortfolioEngineDevelopmentResultV3

        CnASharePortfolioDevelopmentEngineV1._replay_cn_portfolio_steps(
            case.first_steps, case.first_bars, case.first_witnesses)
        first = book_cn_a_share_portfolio_financial_batch_development_v2(
            universe=case.source.scope.instrument_ids, prior_journal=case.initial_journal,
            ledger_schema=case.ledger_schema, cost_basis_policy=case.cost_basis_policy,
            notional_quantization=case.notional_quantization, steps=case.first_steps)
        friday = build_cn_a_share_portfolio_settlement_development_v2(
            batch=first, calendars=case.first_calendars)
        pending = friday.book.project().pending_obligations
        if (len(pending) != len(case.source.scope.instrument_ids)
                or not all(isinstance(item.balance_key, PositionBalanceKey) for item in pending)):
            raise ValueError("paired W BUY requires N native pending T+1 stocks")
        due = max(item.obligation.settlement_time for item in pending)
        if due > min(event.event_time for event in case.second_bars):
            raise ValueError("paired W+1 open precedes native T+1 maturity")
        matured = friday.apply_due(due)
        if matured.book.project().pending_obligations:
            raise ValueError("paired W stocks did not actually mature before W+1")
        if case.account_arm == "A":
            return CnASharePortfolioEngineDevelopmentResultV3(
                case.case_hash, case.source_ref, "A", first, friday, matured, None, None)
        CnASharePortfolioDevelopmentEngineV1._replay_cn_portfolio_steps(
            case.second_steps, case.second_bars, case.second_witnesses)
        second_plan = case.second_steps[0].risk.plan
        matured_state = matured.book.project()
        if (second_plan.cash.journal_hash != first.journal.journal_hash
                or second_plan.cash.settlement_state_hash != matured_state.state_hash
                or second_plan.sellability.settlement_state_hash != matured_state.state_hash
                or second_plan.as_of < due):
            raise ValueError("paired W+1 GTC sell used wrong cash/T+1 account prefix")
        for blocked in case.second_blocked:
            matched = [BarOpenObservation.from_event(event) for event in case.second_bars
                       if event.instrument_id == blocked.stream.order.intent.instrument_id]
            if (len(matched) != 1 or evaluate_cn_a_share_portfolio_next_open_development_v1(
                    plan=second_plan, stream=blocked.stream, observation=matched[0],
                    risk=None, liquidity=None, market_state=None, slippage_model=None,
                    eligibility_window_exhausted=True) != blocked.outcome):
                raise ValueError("paired blocked SELL GTC gap not replayable")
        second = book_cn_a_share_portfolio_financial_batch_development_v2(
            universe=case.source.scope.instrument_ids, prior_journal=first.journal,
            ledger_schema=case.ledger_schema, cost_basis_policy=case.cost_basis_policy,
            notional_quantization=case.notional_quantization,
            steps=case.second_steps, blocked=case.second_blocked)
        second_book = build_cn_a_share_portfolio_settlement_development_v2(
            batch=second, calendars=case.second_calendars)
        return CnASharePortfolioEngineDevelopmentResultV3(
            case.case_hash, case.source_ref, "B", first, friday, matured, second, second_book)
