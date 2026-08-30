"""Production Case planning for accepted Binance USD-M TradFi preparation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from itertools import pairwise

import crypto_quant_domain as domain
import crypto_quant_trading as trading
from crypto_quant_market_data import MarketEvent

from .binance_usdm_tradifi_preparation import (
    BinanceUsdmTradifiPreparationResult,
)
from .binance_usdm_tradifi_preparation import (
    _trusted_result as _trusted_preparation,
)
from .composition import (
    ExecutionCaseComposer,
    _compose_execution_case_v3,
    _execution_case_semantic_spec_v3,
    _ExecutionCasePlan,
    _HydratedExecutionCaseInputs,
)
from .decision_schedule import DecisionSchedule, DecisionScheduleEntry
from .engine import (
    ExecutionCaseIdentityFactory,
    ExecutionCaseIdentityRule,
    ExecutionCaseSemanticSpec,
    OrderEventPlan,
    PositionLotBook,
    ResolvedBarExecution,
    ResolvedDecisionCycle,
    ResolvedExecutionCase,
    ResolvedFinancialState,
    ResolvedOrderAdmission,
    ResolvedPreTradePlan,
    SnapshotProjectionPlan,
)
from .execution import BarLiquidityEvidence, BarOpenObservation
from .financial_dispatch import (
    FeeAccountingDispatchPlan,
    FillAccountingDispatchPlan,
    FinancialDispatchPlan,
    LinearDerivativeFillAccountingPlan,
    LinearFundingAccountEventPlan,
    LinearMarginLiquidationAuditBatchPlan,
    LinearMarginLiquidationAuditPlan,
    LinearMarginLiquidationAuditSubwindowPlan,
    LinearMarginProjectionPlan,
    ScheduledAccountEvent,
)
from .liquidation_audit import LinearLiquidationMarkBarEvidence
from .multi_resolution_market_data import (
    ExecutionDataBinding,
    MultiResolutionMarketDataBindings,
)
from .multi_resolution_preparation import MultiResolutionMarketDataPreparation
from .resolution import (
    BacktestRequest,
    ProfileResolver,
    ResolvedBacktestRequest,
    StrategyFamily,
)
from .run_end import MarkToMarketCloseoutPolicy
from .slippage import SlippageMarketState
from .target_stream import (
    PrecomputedTargetStreamAdapter,
    TargetStreamDecisionSchedule,
    TargetStreamScheduleEntry,
)
from .timeline import DeterministicTimeline, TimelineEvent, TimelineSegment

_SCHEMA_VERSION = 1
_INSTRUMENT = domain.InstrumentId(
    domain.VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual"
)
_USDT = domain.CurrencyId("USDT")
_MONEY_SCALE = domain.Scale(8)
_NOTIONAL_SCALE = domain.Scale(5)
_INITIAL_EQUITY = domain.Money(1_000_000_000_000, _MONEY_SCALE, "USDT")
_NOTIONAL_LIMIT = domain.Money(1_000_000_000, _NOTIONAL_SCALE, "USDT")
_PROJECTION_STREAM_PREFIX = (
    "binance_usdm.tradifi.bar_open.first_retained_aggregate_trade.koruusdt.1h.v"
)
_FUNDING_STREAM = "binance_usdm.funding_history.publications.koruusdt.v1"
_STRATEGY_STREAM = "binance_usdm.mark_price.strategy.koruusdt.1h.v1"
_LIQUIDATION_STREAM = "binance_usdm.mark_price.liquidation.koruusdt.1h.v1"
_MARGIN_STREAM = "binance_usdm.mark_price.margin.koruusdt.1h.v1"
_VALUATION_STREAM = "binance_usdm.mark_price.valuation.koruusdt.1h.v1"
_PLACEHOLDER_RUN_ID = "run_" + "0" * 64
_NAMESPACE = domain.IdentityNamespace("backtest", "1")


def _same(left: object, right: object) -> bool:
    return domain.canonical_bytes(left) == domain.canonical_bytes(right)


def _projection_stream(result: BinanceUsdmTradifiPreparationResult) -> str:
    return f"{_PROJECTION_STREAM_PREFIX}{result.bundle_schema_version}"


def _events(
    result: BinanceUsdmTradifiPreparationResult, stream: str
) -> tuple[MarketEvent, ...]:
    values = getattr(result.market_reader, "streams", {}).get(stream)
    if type(values) is tuple and all(type(value) is MarketEvent for value in values):
        return values
    cursor = result.market_reader.open_cursor(stream, batch_size=64)
    output: list[MarketEvent] = []
    while not cursor.exhausted:
        batch, cursor = result.market_reader.read_batch(cursor)
        output.extend(batch)
    if any(type(value) is not MarketEvent for value in output):
        raise ValueError(f"{stream} must retain exact MarketEvent values")
    return tuple(output)


def _price_event(
    result: BinanceUsdmTradifiPreparationResult,
    stream: str,
    purpose: domain.PricePurpose,
    requested_at: domain.UtcInstant,
) -> tuple[trading.ResolvedMark, trading.StaleMarkPolicy]:
    candidates = tuple(
        event
        for event in _events(result, stream)
        if event.instrument_id == _INSTRUMENT and event.available_time <= requested_at
    )
    if not candidates:
        raise ValueError(f"missing retained {purpose.value} mark")
    event = max(candidates, key=lambda value: (value.timeline_instant, value.event_id))
    payload = event.payload
    units = payload.get("price_units", payload.get("close_units"))
    scale = payload.get("price_scale")
    if type(units) is not int or units <= 0 or type(scale) is not int or scale < 0:
        raise ValueError(f"malformed retained {purpose.value} mark")
    price_scale = result.resolved_profile.linear_contract.price_scale
    if (
        (
            purpose is domain.PricePurpose.VALUATION
            and result.resolved_profile.request.raw_exact_valuation
        )
        or (
            purpose is domain.PricePurpose.MARGIN
            and result.resolved_profile.request.raw_exact_margin
        )
    ):
        mark_units = units
        mark_scale = domain.Scale(scale)
    else:
        divisor = 10 ** (scale - price_scale.places)
        if scale < price_scale.places or units % divisor:
            raise ValueError(f"retained {purpose.value} mark does not fit price lattice")
        mark_units = units // divisor
        mark_scale = price_scale
    age = requested_at.epoch_nanoseconds - event.event_time.epoch_nanoseconds
    policy = trading.StaleMarkPolicy(
        f"binance-usdm-tradifi-case.{purpose.value}.v1",
        1,
        purpose,
        age,
        True,
    )
    mark = trading.ResolvedMark(
        _INSTRUMENT,
        _USDT,
        purpose,
        domain.Price(mark_units, mark_scale, str(_INSTRUMENT), "USDT"),
        event.event_time,
        event.available_time,
        requested_at,
        age,
        stream,
        event.event_id,
        event.revision_id,
        policy.policy_key,
        policy.policy_version,
        policy.policy_hash,
        available_at_instant=event.timeline_instant,
        resolved_at_instant=domain.SimulationInstant(
            requested_at,
            domain.TimelinePhase(90, f"{purpose.value}_projection"),
            domain.SourceSequence(0),
        ),
    )
    return mark, policy


def _keys(
    result: BinanceUsdmTradifiPreparationResult,
) -> tuple[domain.CashBalanceKey, domain.PositionBalanceKey]:
    account = result.intent.execution_account_id
    venue = _INSTRUMENT.venue
    return (
        domain.CashBalanceKey(account, venue, _USDT),
        domain.PositionBalanceKey(account, venue, _INSTRUMENT),
    )


def _ledger_schema(
    result: BinanceUsdmTradifiPreparationResult,
) -> tuple[
    trading.LedgerSchema, trading.LedgerBalanceRegistration, domain.PositionBalanceKey
]:
    cash_key, position_key = _keys(result)
    cash = trading.LedgerBalanceRegistration(cash_key, _MONEY_SCALE)
    position = trading.LedgerBalanceRegistration(
        position_key, result.resolved_profile.linear_contract.quantity_scale
    )
    return trading.LedgerSchema((cash, position)), cash, position_key


def _initial_financial_state(
    result: BinanceUsdmTradifiPreparationResult,
    journal_id: domain.DomainId,
    snapshot_at: domain.UtcInstant,
) -> ResolvedFinancialState:
    schema, _, position_key = _ledger_schema(result)
    cash_key, _ = _keys(result)
    window = result.intent.timeline_window
    recorded_at = domain.SimulationInstant(
        window.data_start,
        domain.TimelinePhase(90, "accounting"),
        domain.SourceSequence(0),
    )
    entry = domain.AccountingJournalEntry(
        journal_id,
        domain.AccountingEntryType.CAPITAL_DEPOSITED,
        result.intent.execution_account_id,
        _INSTRUMENT.venue,
        window.data_start,
        recorded_at,
        ("binance-usdm-tradifi:initial-capital",),
        (domain.BalanceChange(cash_key, _INITIAL_EQUITY),),
        (),
        (),
        (),
    )
    journal = trading.AccountingJournal.from_entries((entry,))
    ledger = trading.GenericLedger(schema).project(journal)
    zero = domain.Money(0, _MONEY_SCALE, "USDT")
    graph = trading.CurrencyValuationGraph(
        snapshot_at, domain.PricePurpose.VALUATION, ()
    )
    snapshot = domain.PortfolioSnapshot(
        result.intent.execution_account_id,
        snapshot_at,
        _USDT,
        ledger.cash_balances,
        ledger.position_balances,
        zero,
        zero,
        zero,
        zero,
        _INITIAL_EQUITY,
        (),
        ledger.state_hash,
        domain.canonical_sha256(()),
        domain.canonical_sha256(()),
        graph.graph_hash,
        timestamp_instant=domain.SimulationInstant(
            snapshot_at,
            domain.TimelinePhase(30, "strategy_decision"),
            domain.SourceSequence(0),
        ),
    )
    rules = trading.MarketSettlementRules.create(
        policy_key="binance-usdm-tradifi-cross-settlement.v1",
        policy_version=1,
        account_id=result.intent.execution_account_id,
        cash_rules=(
            trading.CashAvailabilityRule(
                cash_key,
                False,
                False,
                False,
                (
                    trading.CashReservationUse.CASH,
                    trading.CashReservationUse.FEE_RESERVE,
                    trading.CashReservationUse.MARGIN,
                ),
                (
                    trading.CashReservationUse.CASH,
                    trading.CashReservationUse.FEE_RESERVE,
                    trading.CashReservationUse.MARGIN,
                ),
                (),
            ),
        ),
        position_rules=(trading.PositionAvailabilityRule(position_key, False),),
    )
    return ResolvedFinancialState(
        journal,
        schema,
        snapshot,
        (PositionLotBook(position_key),),
        (),
        (),
        (),
        trading.SettlementBook(result.intent.execution_account_id),
        rules,
    )


def _margin_projection(
    result: BinanceUsdmTradifiPreparationResult,
    evaluated_at: domain.UtcInstant,
) -> LinearMarginProjectionPlan:
    schema, cash_registration, position_key = _ledger_schema(result)
    cash_key, _ = _keys(result)
    valuation, valuation_policy = _price_event(
        result, _VALUATION_STREAM, domain.PricePurpose.VALUATION, evaluated_at
    )
    margin, margin_policy = _price_event(
        result, _MARGIN_STREAM, domain.PricePurpose.MARGIN, evaluated_at
    )
    request = result.profile_composition_request
    if request.account_profile is None or request.margin_tiers is None:
        raise ValueError("resolved profile lacks derivative margin authority")
    return LinearMarginProjectionPlan(
        result.intent.execution_account_id,
        _INSTRUMENT.venue,
        position_key,
        result.resolved_profile.linear_contract,
        schema,
        cash_key,
        domain.SimulationInstant(
            evaluated_at,
            domain.TimelinePhase(90, "margin_projection"),
            domain.SourceSequence(0),
        ),
        valuation,
        valuation_policy,
        request.account_profile.leverage_evidence,
        request.margin_tiers.margin_rule_book,
        trading.LinearMarginMarkEvidence(margin, margin_policy),
        cash_registration,
        domain.QuantizationPolicy(
            "binance-usdm-tradifi.margin-ceiling.v1",
            _MONEY_SCALE,
            domain.RoundingPolicy.CEILING,
        ),
        domain.QuantizationPolicy(
            "binance-usdm-tradifi.unrealized-half-even.v1",
            _MONEY_SCALE,
            domain.RoundingPolicy.HALF_EVEN,
        ),
        "binance-usdm-tradifi.ledger.v1",
        "binance-usdm-tradifi.reservations.v1",
    )


def _snapshot_plan(
    result: BinanceUsdmTradifiPreparationResult,
) -> SnapshotProjectionPlan:
    boundary = result.intent.timeline_window.end_exclusive
    projection = _margin_projection(result, boundary)
    graph = trading.CurrencyValuationGraph(boundary, domain.PricePurpose.VALUATION, ())
    return SnapshotProjectionPlan(
        (),
        (),
        _USDT,
        _MONEY_SCALE,
        boundary,
        graph.graph_hash,
        projection,
        "margin_projection.final",
        "final_snapshot",
    )


def _funding_events(
    result: BinanceUsdmTradifiPreparationResult,
    semantic_run_id: str,
) -> tuple[ScheduledAccountEvent, ...]:
    schema, cash_registration, position_key = _ledger_schema(result)
    cash_key, _ = _keys(result)
    output = []
    for index, event in enumerate(_events(result, _FUNDING_STREAM)):
        payload = event.payload
        if payload.get("rate_type") != "Regular":
            raise ValueError("Special or missing funding authority is unsupported")
        rate_units = payload.get("funding_rate_units")
        rate_scale = payload.get("funding_rate_scale")
        mark_units = payload.get("mark_price_units")
        mark_scale = payload.get("mark_price_scale")
        if not all(
            type(value) is int
            for value in (rate_units, rate_scale, mark_units, mark_scale)
        ):
            raise ValueError("malformed retained funding authority")
        target = event.event_time
        slot = trading.FundingSlotId.derive(_INSTRUMENT, target)
        application_key = trading.LinearFundingApplicationKey.derive(
            result.intent.execution_account_id, slot
        )
        identity = trading.LinearFundingApplicationIdentity.derive(
            application_key, _NAMESPACE, semantic_run_id
        )
        publication = trading.LinearFundingRatePublicationCandidate(
            slot,
            trading.LinearFundingPublicationStatus.FINAL_RATE,
            domain.Rate(
                rate_units, domain.Scale(rate_scale), "funding_fraction_of_notional"
            ),
            event.event_id,
            event.event_hash,
            target,
            domain.SimulationInstant(
                target,
                domain.TimelinePhase(50, "funding_publication"),
                event.source_sequence,
            ),
            event.revision_id,
            event.supersedes_revision_id,
            event.source_key,
            event.source_hash,
        )
        policy = trading.StaleMarkPolicy(
            "binance-usdm-tradifi.funding-mark.v1",
            1,
            domain.PricePurpose.FUNDING,
            0,
            False,
        )
        price_scale = result.resolved_profile.linear_contract.price_scale
        divisor = 10 ** (mark_scale - price_scale.places)
        if mark_scale < price_scale.places or mark_units % divisor:
            raise ValueError("funding mark does not fit the contract price lattice")
        resolved_mark = trading.ResolvedMark(
            _INSTRUMENT,
            _USDT,
            domain.PricePurpose.FUNDING,
            domain.Price(mark_units // divisor, price_scale, str(_INSTRUMENT), "USDT"),
            target,
            target,
            target,
            0,
            _FUNDING_STREAM,
            event.event_id,
            event.revision_id,
            policy.policy_key,
            policy.policy_version,
            policy.policy_hash,
            available_at_instant=event.timeline_instant,
            resolved_at_instant=event.timeline_instant,
        )
        settlement = trading.LinearFundingSettlementEvidence(
            application_key,
            target,
            event.timeline_instant,
            publication.published_rate,
            event.event_id,
            event.event_hash,
            event.revision_id,
            event.supersedes_revision_id,
            event.source_key,
            event.source_hash,
        )
        plan = LinearFundingAccountEventPlan(
            identity,
            domain.SimulationInstant(
                target,
                domain.TimelinePhase(120, "funding_accounting"),
                domain.SourceSequence(index),
            ),
            schema,
            cash_key,
            position_key,
            result.resolved_profile.linear_contract,
            domain.SimulationInstant(
                target,
                domain.TimelinePhase(100, "funding_eligibility"),
                domain.SourceSequence(index),
            ),
            domain.SimulationInstant(
                target,
                domain.TimelinePhase(105, "position_snapshot"),
                domain.SourceSequence(index),
            ),
            f"{event.event_id}:position-snapshot",
            "binance-usdm-tradifi.position-series.v1",
            event.revision_id,
            event.supersedes_revision_id,
            (publication,),
            settlement,
            trading.LinearFundingMarkEvidence(resolved_mark, policy),
            cash_registration,
            domain.QuantizationPolicy(
                "binance-usdm-tradifi.funding-half-even.v1",
                _MONEY_SCALE,
                domain.RoundingPolicy.HALF_EVEN,
            ),
        )
        output.append(
            ScheduledAccountEvent(
                event.event_id,
                event.timeline_instant,
                "funding",
                (result.financial_dispatcher_spec.financing_component.component_key,),
                (
                    (f"settlement.funding.{index}", identity.settlement_id),
                    (f"journal.funding.{index}", identity.journal_entry_id),
                ),
                plan,
                plan.production_semantic_authority(),
                ("funding_accounting", "funding_eligibility"),
            )
        )
    return tuple(output)


def _planning_snapshot(
    result: BinanceUsdmTradifiPreparationResult,
    at: MarketEvent,
    quantity: domain.Quantity,
    lots: tuple[domain.PositionLot, ...],
) -> domain.PortfolioSnapshot:
    cash_key, position_key = _keys(result)
    zero = domain.Money(0, _MONEY_SCALE, "USDT")
    cash = (domain.CashBalance(cash_key, _INITIAL_EQUITY),)
    positions = (
        (domain.PositionBalance(position_key, quantity, lots),)
        if quantity.units
        else ()
    )
    graph = trading.CurrencyValuationGraph(
        at.event_time, domain.PricePurpose.VALUATION, ()
    )
    return domain.PortfolioSnapshot(
        result.intent.execution_account_id,
        at.event_time,
        _USDT,
        cash,
        positions,
        zero,
        zero,
        zero,
        zero,
        _INITIAL_EQUITY,
        (),
        domain.canonical_sha256(
            {
                "type": "tradifi_causal_planning_state",
                "equity": _INITIAL_EQUITY,
                "quantity": quantity,
                "lots": lots,
            }
        ),
        domain.canonical_sha256(()),
        domain.canonical_sha256(()),
        graph.graph_hash,
    )


def _planning_lots(
    result: BinanceUsdmTradifiPreparationResult,
    normalized: trading.NormalizedPortfolioTarget,
    mark: trading.ResolvedMark,
    opened_at: domain.UtcInstant,
) -> tuple[domain.PositionLot, ...]:
    quantity = normalized.targets[0].decision.final_quantity
    if quantity.units == 0:
        return ()
    return (
        domain.PositionLot(
            f"planning-target:{normalized.normalized_target_id}",
            _keys(result)[1],
            normalized.normalized_target_id,
            quantity,
            mark.price,
            (),
            opened_at,
        ),
    )


def _liquidation_bar(
    result: BinanceUsdmTradifiPreparationResult,
    event: MarketEvent,
) -> LinearLiquidationMarkBarEvidence:
    payload = event.payload
    start = payload.get("open_time_milliseconds")
    close = payload.get("close_time_milliseconds")
    low_units = payload.get("low_units")
    high_units = payload.get("high_units")
    source_scale = payload.get("price_scale")
    if not all(
        type(value) is int
        for value in (start, close, low_units, high_units, source_scale)
    ):
        raise ValueError("malformed retained liquidation bar")
    interval_start = domain.UtcInstant(start * 1_000_000)
    interval_end = domain.UtcInstant((close + 1) * 1_000_000)
    if (
        interval_end.epoch_nanoseconds - interval_start.epoch_nanoseconds
        != 3_600_000_000_000
    ):
        raise ValueError("liquidation bar must cover one exact hour")
    price_scale = result.resolved_profile.linear_contract.price_scale
    if source_scale < price_scale.places:
        raise ValueError("liquidation bar does not fit contract price lattice")
    divisor = 10 ** (source_scale - price_scale.places)
    if (
        low_units <= 0
        or high_units < low_units
        or low_units % divisor
        or high_units % divisor
    ):
        raise ValueError("malformed retained liquidation price range")
    return LinearLiquidationMarkBarEvidence(
        event.event_id,
        _INSTRUMENT,
        domain.PricePurpose.LIQUIDATION,
        interval_start,
        interval_end,
        domain.Price(low_units // divisor, price_scale, str(_INSTRUMENT), "USDT"),
        domain.Price(high_units // divisor, price_scale, str(_INSTRUMENT), "USDT"),
        event.timeline_instant,
        event.timeline_instant,
        event.stream_key,
        event.event_id,
        event.revision_id,
        event.supersedes_revision_id,
        event.source_key,
        event.source_hash,
    )


def _position_intervals(
    rows: tuple[
        tuple[MarketEvent, Mapping[str, object], int, MarketEvent, MarketEvent], ...
    ],
    end_exclusive: domain.UtcInstant,
) -> tuple[tuple[domain.UtcInstant, domain.UtcInstant], ...]:
    opened_at: domain.UtcInstant | None = None
    intervals: list[tuple[domain.UtcInstant, domain.UtcInstant]] = []
    for _, _, target, _, projection in rows:
        if target != 0 and opened_at is None:
            opened_at = projection.event_time
        elif target == 0 and opened_at is not None:
            intervals.append((opened_at, projection.event_time))
            opened_at = None
    if opened_at is not None:
        intervals.append((opened_at, end_exclusive))
    return tuple(intervals)


def _margin_audits(
    result: BinanceUsdmTradifiPreparationResult,
    rows: tuple[
        tuple[MarketEvent, Mapping[str, object], int, MarketEvent, MarketEvent], ...
    ],
    funding: tuple[ScheduledAccountEvent, ...],
) -> tuple[ScheduledAccountEvent, ...]:
    """Bind each exposure subwindow to actual timeline events, never invented ticks."""
    intervals = _position_intervals(rows, result.intent.timeline_window.end_exclusive)
    events_at = {
        event.timeline_instant.instant: event.timeline_instant
        for manifest in result.market_bundle_manifest.streams
        for event in _events(result, manifest.stream_key)
    }
    output: list[ScheduledAccountEvent] = []
    for event in _events(result, _LIQUIDATION_STREAM):
        bar = _liquidation_bar(result, event)
        if (
            bar.interval_start < result.intent.timeline_window.trading_start
            or bar.interval_end_exclusive > result.intent.timeline_window.end_exclusive
        ):
            continue
        children: list[LinearMarginLiquidationAuditSubwindowPlan] = []
        for position_start, position_end in intervals:
            if not (bar.interval_start < position_end and position_start < bar.interval_end_exclusive):
                continue
            interval_start = max(bar.interval_start, position_start)
            interval_end = min(bar.interval_end_exclusive, position_end)
            if interval_start >= interval_end:
                continue
            if interval_start == position_start:
                start_checkpoint = next(
                    row[4].timeline_instant for row in rows if row[4].event_time == position_start
                )
                start_side = "after"
            else:
                start_checkpoint = events_at.get(interval_start)
                if start_checkpoint is None:
                    raise ValueError("liquidation subwindow start has no timeline event")
                start_side = "after"
            if interval_end == position_end:
                end_checkpoint = next(
                    row[4].timeline_instant for row in rows if row[4].event_time == position_end
                )
                end_side = "before"
            else:
                end_checkpoint = event.timeline_instant
                end_side = "before"

            boundaries = [(interval_start, start_checkpoint, start_side)]
            for funding_event in funding:
                funding_at = funding_event.event_at.instant
                if interval_start < funding_at < interval_end:
                    boundaries.extend(
                        (
                            (funding_at, funding_event.event_at, "before"),
                            (funding_at, funding_event.event_at, "after"),
                        )
                    )
            boundaries.append((interval_end, end_checkpoint, end_side))
            pairs = zip(boundaries[::2], boundaries[1::2], strict=True)
            for start, end in pairs:
                start_at, start_instant, start_side = start
                end_at, end_instant, end_side = end
                if start_at >= end_at:
                    continue
                projection = _margin_projection(result, start_at)
                suffix = f"hourly.{len(output) + 1}.{len(children) + 1}"
                plan = LinearMarginLiquidationAuditPlan(
                    projection.evaluated_at,
                    projection.valuation_mark.price,
                    projection.margin_mark_evidence.resolved_mark.price,
                    start_at,
                    end_at,
                    bar.low,
                    bar.high,
                    event.timeline_instant,
                    suffix,
                    projection,
                    (bar,),
                    result.intent.result_grade_requested,
                    "binance-usdm-tradifi.runtime-account-window.v1",
                    window_start_at=start_at,
                )
                children.append(
                    LinearMarginLiquidationAuditSubwindowPlan(
                        plan, start_instant, start_side, end_instant, end_side
                    )
                )
        if not children:
            continue
        payload = LinearMarginLiquidationAuditBatchPlan(
            event.timeline_instant, bar, tuple(children)
        )
        output.append(
            ScheduledAccountEvent(
                event.event_id,
                event.timeline_instant,
                "margin_liquidation_audit_batch",
                tuple(
                    sorted(
                        (
                            result.financial_dispatcher_spec.liquidation_audit_component.component_key,
                            result.financial_dispatcher_spec.margin_component.component_key,
                        )
                    )
                ),
                (),
                payload,
                payload.production_semantic_authority(),
                tuple(
                    sorted(
                        role
                        for child in children
                        for role in (
                            f"liquidation_audit.{child.plan.role_suffix}",
                            f"margin_projection.{child.plan.role_suffix}",
                        )
                    )
                ),
            )
        )
    return tuple(output)


def _event_by_id(
    result: BinanceUsdmTradifiPreparationResult, event_id: str
) -> MarketEvent:
    matches = tuple(
        event
        for manifest in result.market_bundle_manifest.streams
        for event in _events(result, manifest.stream_key)
        if event.event_id == event_id
    )
    if len(matches) != 1:
        raise ValueError(
            f"candidate evidence does not bind one retained Event: {event_id}"
        )
    return matches[0]


def _candidate_rows(
    result: BinanceUsdmTradifiPreparationResult,
) -> tuple[
    tuple[MarketEvent, Mapping[str, object], int, MarketEvent, MarketEvent], ...
]:
    rows = []
    previous = 0
    source_digest = result.preparation_authority_event.payload["source_fragment_digest"]
    expected_refs = (
        result.strategy_definition_ref.to_canonical_dict(),
        result.strategy_parameter_set_ref.to_canonical_dict(),
        result.xkrx_calendar_ref.to_canonical_dict(),
        result.arcx_calendar_ref.to_canonical_dict(),
        result.post_adjustment_unit_regime_ref.to_canonical_dict(),
    )
    for event in result.target_stream.events:
        candidate = event.payload.get("candidate")
        if not isinstance(candidate, Mapping):
            raise TypeError("target candidate must be an exact mapping")
        evidence = candidate.get("evidence")
        targets = candidate.get("targets")
        if (
            not isinstance(evidence, Mapping)
            or not isinstance(targets, tuple)
            or len(targets) != 1
        ):
            raise ValueError("target candidate evidence/target shape is malformed")
        target = targets[0]
        if not isinstance(target, Mapping) or target.get("instrument_id") != {
            "venue": "binance_usdm",
            "stable_key": "koru-usdt-tradifi-perpetual",
        }:
            raise ValueError("target candidate instrument mismatch")
        values = {"-0.1": -1, "0": 0, "+0.1": 1, "0.1": 1}
        raw_value = target.get("value")
        value = values.get(raw_value) if type(raw_value) is str else None
        if value is None:
            raise ValueError("target value must be -0.1, 0, or +0.1")
        if value == previous or (previous != 0 and value != 0):
            raise ValueError("target position state must alternate without overlap")
        refs = (
            evidence.get("strategy_definition_ref"),
            evidence.get("strategy_parameter_set_ref"),
            evidence.get("xkrx_calendar_ref"),
            evidence.get("arcx_calendar_ref"),
            evidence.get("post_adjustment_unit_regime_ref"),
        )
        if (
            candidate.get("strategy_id") != "koruusdt_closed_market_range_v1"
            or candidate.get("sleeve_id") != "koruusdt-closed-market-range"
            or candidate.get("decision_time") != event.event_time.epoch_nanoseconds
            or candidate.get("effective_time") != event.event_time.epoch_nanoseconds
            or evidence.get("source_fragment_digest") != source_digest
            or not _same(refs, expected_refs)
        ):
            raise ValueError("target candidate authority refs mismatch")
        mark = _event_by_id(result, str(evidence.get("mark_event_id")))
        projection = _event_by_id(result, str(evidence.get("projection_event_id")))
        expires = candidate.get("expires_at")
        if (
            evidence.get("mark_event_hash") != mark.event_hash
            or evidence.get("projection_event_hash") != projection.event_hash
            or projection.stream_key != _projection_stream(result)
            or mark.instrument_id != _INSTRUMENT
            or mark.stream_key != _STRATEGY_STREAM
            or mark.payload.get("price_purpose") != "strategy"
            or not mark.timeline_instant < event.timeline_instant
            or mark.available_time > event.event_time
            or not event.timeline_instant < projection.timeline_instant
            or type(expires) is not int
            or not (
                event.event_time.epoch_nanoseconds
                < projection.event_time.epoch_nanoseconds
                < expires
                <= result.intent.timeline_window.end_exclusive.epoch_nanoseconds
            )
        ):
            raise ValueError("candidate mark, projection, or expiry evidence mismatch")
        rows.append((event, candidate, value, mark, projection))
        previous = value
    if previous != 0:
        raise ValueError("target stream must return flat by the run boundary")
    decision_keys = tuple((row[0].timeline_instant, row[0].event_id) for row in rows)
    if decision_keys != tuple(sorted(decision_keys)) or len(set(decision_keys)) != len(
        decision_keys
    ):
        raise ValueError("target decisions must be sorted and unique")
    for left, right in pairwise(rows):
        if left[4].timeline_instant >= right[0].timeline_instant:
            raise ValueError("target orders overlap before their retained fills")
    return tuple(rows)


def _decision_mark(
    result: BinanceUsdmTradifiPreparationResult,
    event: MarketEvent,
    decision_event: MarketEvent,
) -> trading.ResolvedMark:
    payload = event.payload
    units, scale = payload.get("close_units"), payload.get("price_scale")
    price_scale = result.resolved_profile.linear_contract.price_scale
    if type(units) is not int or type(scale) is not int or scale < price_scale.places:
        raise ValueError("candidate decision mark is malformed")
    divisor = 10 ** (scale - price_scale.places)
    if units <= 0 or units % divisor:
        raise ValueError("candidate decision mark does not fit price lattice")
    age = (
        decision_event.event_time.epoch_nanoseconds
        - event.event_time.epoch_nanoseconds
    )
    policy = trading.StaleMarkPolicy(
        "binance-usdm-tradifi.decision-mark.v1",
        1,
        domain.PricePurpose.EXECUTION_REFERENCE,
        age,
        age > 0,
    )
    return trading.ResolvedMark(
        _INSTRUMENT,
        _USDT,
        domain.PricePurpose.EXECUTION_REFERENCE,
        domain.Price(units // divisor, price_scale, str(_INSTRUMENT), "USDT"),
        event.event_time,
        event.available_time,
        decision_event.event_time,
        age,
        event.stream_key,
        event.event_id,
        event.revision_id,
        policy.policy_key,
        policy.policy_version,
        policy.policy_hash,
    )


def _translation_mapping() -> trading.OrderTranslationMapping:
    canonical = (
        "instrument_id",
        "side",
        "quantity",
        "execution_style",
        "price_constraint",
        "time_in_force",
        "reduce_only",
        "position_effect",
        "urgency",
        "reason",
        "parent_id",
    )
    target = (
        "symbol",
        "side",
        "quantity",
        "type",
        "price",
        "timeInForce",
        "reduceOnly",
        "positionSide",
        "urgency",
        "reason",
        "clientOrderId",
    )
    return trading.OrderTranslationMapping.create(
        translator_key="binance-usdm-tradifi.order-translation.v1",
        translator_version=1,
        target_profile_id="binance.usdm.standard-cross.v1",
        field_rules=tuple(
            trading.OrderTranslationFieldRule(left, right)
            for left, right in zip(canonical, target, strict=True)
        ),
    )


def _capabilities(
    result: BinanceUsdmTradifiPreparationResult,
) -> trading.OrderCapabilitySet:
    rules = result.profile_composition_request.order_rules
    if rules is None:
        raise ValueError("profile lacks production order authority")
    capabilities = rules.order_capabilities
    if capabilities.declared_capability_keys != (
        "binance_usdm_limit",
        "binance_usdm_market",
        "binance_usdm_reduce_only",
    ):
        raise ValueError("profile capability declaration mismatch")
    return trading.OrderCapabilitySet.create(
        capability_set_key=capabilities.capability_set_key,
        capability_set_version=capabilities.capability_set_version,
        style_capabilities=capabilities.style_capabilities,
        supports_reduce_only=capabilities.supports_reduce_only,
        supported_position_effects=capabilities.supported_position_effects,
        declared_capability_keys=tuple(
            sorted(value.value for value in trading.OrderCapabilityKey)
        ),
    )


def _pretrade(
    result: BinanceUsdmTradifiPreparationResult,
    order: domain.Order,
    price: domain.Price,
    at: domain.UtcInstant,
) -> ResolvedPreTradePlan:
    rules = result.profile_composition_request.order_rules
    account = result.profile_composition_request.account_profile
    if rules is None or account is None:
        raise ValueError("profile lacks production order/account authority")
    capability = trading.OrderCapabilityValidator().validate(
        order.intent, _capabilities(result)
    )
    if capability.approval is None:
        raise ValueError("profile order capability rejected planned order")
    translated = trading.OrderTranslator().translate(
        order, capability.approval, _translation_mapping(), at
    )
    if translated.executable_spec is None:
        raise ValueError("profile order translation failed")
    evidence = trading.OrderRuleNotionalEvidence(
        trading.NotionalPriceBasis.SUPPLIED_REFERENCE,
        price,
        domain.canonical_sha256(
            {"event": "tradifi-reference", "price": price, "at": at}
        ),
        at,
    )
    market = trading.MarketRuleEvaluator().evaluate(
        trading.OrderRuleEvaluationInput(translated.executable_spec, at, evidence),
        rules.rule_timeline,
    )
    if market.approval is None:
        raise ValueError("production market rule rejected planned order")
    fees = trading.FeeReservationEstimator().estimate(
        market.approval, account.fee_reservation_rule_set, at
    )
    if fees.proposal is None:
        raise ValueError("production fee reservation failed")
    notional = market.approval.calculated_notional
    if notional.scale.places > _MONEY_SCALE.places:
        raise ValueError("planned notional exceeds account money scale")
    reserved_notional = domain.Money(
        notional.units * 10 ** (_MONEY_SCALE.places - notional.scale.places),
        _MONEY_SCALE,
        notional.currency,
    )
    commitment = trading.ReservationCommitment(
        margin=(reserved_notional,),
        fee_reserve=fees.proposal.commitment.fee_reserve,
        order_capacity_units=1,
        exposure_capacity=(reserved_notional,),
    )
    source_hash = domain.canonical_sha256(
        {
            "type": "binance_usdm_tradifi_resource_requirement_source",
            "order_rule_timeline": rules.rule_timeline,
            "notional_evidence": evidence,
            "fee_reservation_rule_set": account.fee_reservation_rule_set,
            "commitment": commitment,
            "account_risk_policy": result.resolved_profile.account_risk_policy,
            "evaluated_at": at,
        }
    )
    return ResolvedPreTradePlan(
        rules.rule_timeline,
        evidence,
        at,
        account.fee_reservation_rule_set,
        at,
        commitment,
        "binance-usdm-tradifi.resource-requirement.v1",
        1,
        source_hash,
        result.resolved_profile.account_risk_policy,
        at,
    )


def _identity_plan(
    result: BinanceUsdmTradifiPreparationResult,
) -> tuple[ExecutionCaseIdentityRule, ...]:
    rules = [
        ExecutionCaseIdentityRule(
            "journal.initial.0",
            "binance-usdm-tradifi.initial-deposit.v1",
            0,
            domain.DomainIdKind.JOURNAL,
        )
    ]
    event_types = (
        domain.OrderEventType.ORDER_INTENT_CREATED,
        domain.OrderEventType.ORDER_CAPABILITY_APPROVED,
        domain.OrderEventType.ORDER_TRANSLATED,
        domain.OrderEventType.MARKET_RULE_APPROVED,
        domain.OrderEventType.FEE_RESERVATION_ESTIMATED,
        domain.OrderEventType.PRE_TRADE_RISK_APPROVED,
        domain.OrderEventType.ORDER_SUBMITTED,
        domain.OrderEventType.ORDER_ACCEPTED,
    )
    for index, _ in enumerate(result.target_stream.events):
        rules.extend(
            (
                ExecutionCaseIdentityRule(
                    f"order.{index}.0",
                    "binance-usdm-tradifi.order.v1",
                    index,
                    domain.DomainIdKind.ORDER,
                ),
                ExecutionCaseIdentityRule(
                    f"fill.{index}",
                    "binance-usdm-tradifi.fill.v1",
                    index,
                    domain.DomainIdKind.FILL,
                ),
                ExecutionCaseIdentityRule(
                    f"journal.fill.{index}",
                    "binance-usdm-tradifi.fill-journal.v1",
                    index,
                    domain.DomainIdKind.JOURNAL,
                ),
                ExecutionCaseIdentityRule(
                    f"fee.{index}",
                    "binance-usdm-tradifi.fee.v1",
                    index,
                    domain.DomainIdKind.FEE,
                ),
                ExecutionCaseIdentityRule(
                    f"journal.fee.{index}",
                    "binance-usdm-tradifi.fee-journal.v1",
                    index,
                    domain.DomainIdKind.JOURNAL,
                ),
                ExecutionCaseIdentityRule(
                    f"order-event.fill.{index}",
                    "binance-usdm-tradifi.order-event.fill.v1",
                    index,
                ),
                *(
                    ExecutionCaseIdentityRule(
                        f"order-event.{index}.0.{event_index}",
                        f"binance-usdm-tradifi.order-event.{event_type.value}.v1",
                        index * 10 + event_index,
                    )
                    for event_index, event_type in enumerate(event_types)
                ),
            )
        )
    for index, event in enumerate(_events(result, _FUNDING_STREAM)):
        key = trading.LinearFundingApplicationKey.derive(
            result.intent.execution_account_id,
            trading.FundingSlotId.derive(_INSTRUMENT, event.event_time),
        ).value
        rules.extend(
            (
                ExecutionCaseIdentityRule(
                    f"settlement.funding.{index}",
                    key,
                    index,
                    domain.DomainIdKind.SETTLEMENT,
                ),
                ExecutionCaseIdentityRule(
                    f"journal.funding.{index}", key, index, domain.DomainIdKind.JOURNAL
                ),
            )
        )
    return tuple(rules)


def _request(
    result: BinanceUsdmTradifiPreparationResult,
    semantic_hash: str,
) -> BacktestRequest:
    profile = result.resolved_profile
    return BacktestRequest(
        1,
        result.intent.experiment_id,
        result.intent.timeline_window,
        profile.market_registration.profile_key,
        profile.simulation_registration.profile_key,
        profile.execution_account_registration.profile_key,
        result.intent.execution_account_id,
        _USDT,
        result.market_bundle_ref,
        result.target_stream_digest,
        semantic_hash,
        result.intent.master_random_seed,
        result.build_artifact_manifest.manifest_hash,
        StrategyFamily.PRECOMPUTED_TARGET,
        profile.simulation_registration.engine_kind,
        result.intent.result_grade_requested,
    )


def _resolve(
    result: BinanceUsdmTradifiPreparationResult,
    request: BacktestRequest,
) -> ResolvedBacktestRequest:
    outcome = ProfileResolver().resolve(
        request=request,
        registry=result.profile_registry,
        market_bundle_manifest=result.market_bundle_manifest,
        build_artifact_manifest=result.build_artifact_manifest,
    )
    if outcome.failure is not None or outcome.resolved is None:
        raise ValueError("exact TradFi Case request did not resolve")
    return outcome.resolved


def _preparation(
    result: BinanceUsdmTradifiPreparationResult,
) -> MultiResolutionMarketDataPreparation:
    target_events = result.target_stream.events
    instants = tuple(
        dict.fromkeys(event.timeline_instant for event in target_events)
    ) or (
        domain.SimulationInstant(
            result.intent.timeline_window.trading_start,
            domain.TimelinePhase(0, "empty_target_schedule"),
            domain.SourceSequence(0),
        ),
    )
    schedule = DecisionSchedule(
        "binance-usdm-tradifi.case.v1",
        1,
        result.intent.timeline_window,
        tuple(
            DecisionScheduleEntry(value, TimelineSegment.ACTIVE_TRADING)
            for value in instants
        ),
        (),
    )
    return MultiResolutionMarketDataPreparation(
        schedule,
        MultiResolutionMarketDataBindings(
            (),
            (
                ExecutionDataBinding(
                    result.resolved_profile.simulation.execution_model.component_ref.component_key,
                    _projection_stream(result),
                ),
            ),
            (),
        ),
        (),
    )


def _base_spec(
    result: BinanceUsdmTradifiPreparationResult,
    timeline: DeterministicTimeline,
    identity_plan: tuple[ExecutionCaseIdentityRule, ...],
) -> ExecutionCaseSemanticSpec:
    digest = result.result_digest
    return ExecutionCaseSemanticSpec(
        1,
        "binance-usdm-tradifi.execution-case.v1",
        1,
        "binance-usdm-tradifi.multi-order.v1",
        1,
        _NAMESPACE,
        identity_plan,
        ExecutionCaseComposer.timeline_semantic_hash(timeline),
        result.target_stream_digest,
        digest,
        digest,
        digest,
        digest,
        digest,
    )


def _execution_mark(
    result: BinanceUsdmTradifiPreparationResult, event: MarketEvent
) -> trading.ResolvedMark:
    observation = BarOpenObservation.from_event(event)
    if observation.open_price is None:
        raise ValueError("candidate projection must be a real retained bar open")
    price = observation.open_price
    scale = result.resolved_profile.linear_contract.price_scale
    divisor = 10 ** (price.scale.places - scale.places)
    if price.scale.places < scale.places or price.units % divisor:
        raise ValueError("projection open does not fit contract price lattice")
    policy = trading.StaleMarkPolicy(
        "binance-usdm-tradifi.execution-reference.v1",
        1,
        domain.PricePurpose.EXECUTION_REFERENCE,
        0,
        False,
    )
    return trading.ResolvedMark(
        _INSTRUMENT,
        _USDT,
        domain.PricePurpose.EXECUTION_REFERENCE,
        domain.Price(price.units // divisor, scale, str(_INSTRUMENT), "USDT"),
        event.event_time,
        event.available_time,
        event.available_time,
        0,
        event.stream_key,
        event.event_id,
        event.revision_id,
        policy.policy_key,
        policy.policy_version,
        policy.policy_hash,
        available_at_instant=event.timeline_instant,
        resolved_at_instant=event.timeline_instant,
    )


@dataclass(frozen=True, slots=True)
class _LinearFillSemantics:
    position_key: domain.PositionBalanceKey
    contract: trading.LinearPerpetualContract

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_linear_fill_semantics",
            "position_key": self.position_key,
            "contract": self.contract,
        }


def _plan(
    result: BinanceUsdmTradifiPreparationResult,
    semantic_run_id: str,
    journal_id: domain.DomainId,
) -> _ExecutionCasePlan:
    rows = _candidate_rows(result)
    snapshot_at = (
        rows[0][0].event_time if rows else result.intent.timeline_window.trading_start
    )
    financial = _initial_financial_state(result, journal_id, snapshot_at)
    snapshot = _snapshot_plan(result)
    funding = _funding_events(result, semantic_run_id)
    audits = _margin_audits(result, rows, funding)
    scheduled_events = (*funding, *audits)
    if not rows:
        roles = tuple(
            sorted(
                (
                    "final_snapshot",
                    "margin_projection.final",
                    *(
                        role
                        for event in scheduled_events
                        for role in event.expected_artifact_roles
                    ),
                )
            )
        )
        return _ExecutionCasePlan(
            (),
            (),
            financial,
            FinancialDispatchPlan(
                result.financial_dispatcher_spec,
                scheduled_events,
                snapshot,
                roles,
            ),
            result.resolved_profile.simulation.execution_model,
            snapshot,
            MarkToMarketCloseoutPolicy(),
        )

    identities = ExecutionCaseIdentityFactory(
        semantic_run_id=semantic_run_id,
        namespace=_NAMESPACE,
        identity_plan=_identity_plan(result),
    )
    ledger = trading.GenericLedger(financial.ledger_schema).project(financial.journal)
    reservations = trading.ResourceReservationBook(
        result.intent.execution_account_id
    ).project((), ())
    prior_state = None
    current_quantity = domain.Quantity(
        0,
        result.resolved_profile.linear_contract.quantity_scale,
        str(_INSTRUMENT),
    )
    current_lots: tuple[domain.PositionLot, ...] = ()
    cycles: list[ResolvedDecisionCycle] = []
    bars: list[ResolvedBarExecution] = []
    event_types = (
        domain.OrderEventType.ORDER_INTENT_CREATED,
        domain.OrderEventType.ORDER_CAPABILITY_APPROVED,
        domain.OrderEventType.ORDER_TRANSLATED,
        domain.OrderEventType.MARKET_RULE_APPROVED,
        domain.OrderEventType.FEE_RESERVATION_ESTIMATED,
        domain.OrderEventType.PRE_TRADE_RISK_APPROVED,
        domain.OrderEventType.ORDER_SUBMITTED,
        domain.OrderEventType.ORDER_ACCEPTED,
    )

    for index, (target_event, candidate, _, mark_event, projection_event) in enumerate(
        rows
    ):
        strategy_id = "koruusdt_closed_market_range_v1"
        sleeve_id = domain.StrategySleeveId("koruusdt-closed-market-range")
        expectation = trading.DecisionBatchExpectation(strategy_id, sleeve_id)
        catalog = domain.InstrumentCatalog(
            currencies=(domain.CurrencyId("KORU"), _USDT),
            instruments=(result.resolved_profile.linear_contract.instrument,),
            symbol_timelines=(),
        )
        schedule = TargetStreamDecisionSchedule(
            target_event.event_time,
            TimelineSegment.ACTIVE_TRADING,
            (
                TargetStreamScheduleEntry(
                    target_event.event_id,
                    expectation,
                    trading.StrategyOutputValidationContext(
                        strategy_id,
                        sleeve_id,
                        target_event.event_time,
                        catalog,
                        (_INSTRUMENT,),
                    ),
                ),
            ),
        )
        injected = PrecomputedTargetStreamAdapter().inject(
            stream=result.target_stream,
            timeline_events=(
                TimelineEvent(TimelineSegment.ACTIVE_TRADING, target_event),
            ),
            schedule=schedule,
            prior_state=prior_state,
        )
        if injected.injection is None:
            raise ValueError("accepted target did not pass the standard adapter")
        prior_state = injected.injection.state
        allocation_ref = trading.CapitalAllocationPolicyRef(
            "binance-usdm-tradifi.full-sleeve.v1",
            1,
            domain.canonical_sha256({"equity": _INITIAL_EQUITY, "fraction": "1"}),
        )
        planning_snapshot = _planning_snapshot(
            result, target_event, current_quantity, current_lots
        )
        allocations = (
            trading.StrategyAllocation(
                strategy_id,
                sleeve_id,
                target_event.event_time,
                _USDT,
                _INITIAL_EQUITY,
                allocation_ref,
                domain.canonical_sha256(planning_snapshot),
            ),
        )
        risk = trading.PortfolioRiskPolicy.create(
            policy_key="binance-usdm-tradifi.target-risk.v1",
            policy_version=1,
            valuation_currency=_USDT,
            notional_scale=_NOTIONAL_SCALE,
            limits=(
                trading.PortfolioRiskLimit(
                    "tradifi-target",
                    trading.PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL,
                    _NOTIONAL_LIMIT,
                    trading.PortfolioRiskAction.REJECT,
                    _INSTRUMENT,
                ),
                trading.PortfolioRiskLimit(
                    "tradifi-gross",
                    trading.PortfolioRiskScope.GROSS_EXPOSURE,
                    _NOTIONAL_LIMIT,
                    trading.PortfolioRiskAction.REJECT,
                    None,
                ),
                trading.PortfolioRiskLimit(
                    "tradifi-net",
                    trading.PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE,
                    _NOTIONAL_LIMIT,
                    trading.PortfolioRiskAction.REJECT,
                    None,
                ),
            ),
        )
        sizing_policy = trading.PositionSizingPolicy.create(
            policy_key="binance-usdm-tradifi.fixed-notional-sizing.v1",
            policy_version=1,
            price_purpose=domain.PricePurpose.EXECUTION_REFERENCE,
            rounding=domain.RoundingPolicy.TOWARD_ZERO,
            residual_policy=trading.ResidualPositionPolicy.FAIL,
        )
        sizing_input = trading.InstrumentSizingInput(
            _INSTRUMENT,
            _decision_mark(result, mark_event, target_event),
            current_quantity,
            result.profile_composition_request.order_rules.market_quantity_lattice,  # type: ignore[union-attr]
        )
        allocated = trading.PortfolioAllocator().allocate(
            sleeve_state=prior_state,
            portfolio_snapshot=planning_snapshot,
            allocations=allocations,
            target_notional_scale=_NOTIONAL_SCALE,
        )
        if allocated.allocation is None:
            raise ValueError("full-sleeve target allocation failed")
        approved = trading.PortfolioRiskEvaluator().evaluate(
            allocation=allocated.allocation, policy=risk
        )
        if approved.approved_target is None:
            raise ValueError("target risk evaluation failed")
        sized = trading.PositionSizer().materialize(
            approved_target=approved.approved_target,
            source_decision_batch_id=injected.injection.batch.decision_batch_id,
            policy=sizing_policy,
            inputs=(sizing_input,),
        )
        if sized.normalized_target is None:
            raise ValueError("fixed-notional target sizing failed")
        expires = candidate.get("expires_at")
        if type(expires) is not int:
            raise ValueError("candidate expiry is malformed")
        validity = trading.TargetValidity(
            sized.normalized_target.normalized_target_id,
            sized.normalized_target.normalized_target_hash,
            target_event.event_time,
            domain.UtcInstant(expires),
        )
        rebalance = trading.RebalancePolicy.create(
            policy_key="binance-usdm-tradifi.market-ioc.v1",
            policy_version=1,
            execution_style=domain.ExecutionStyle.MARKET,
            time_in_force=domain.TimeInForce.IOC,
            urgency="normal",
            plan_valid_for_nanoseconds=expires
            - target_event.event_time.epoch_nanoseconds,
        )
        availability = trading.AvailabilityProjection().project(
            ledger,
            trading.SettlementBook(result.intent.execution_account_id).project(),
            reservations,
            financial.settlement_rules,
        )
        coordinated = trading.RebalanceCoordinator().coordinate(
            target=sized.normalized_target,
            target_validity=validity,
            portfolio_snapshot=planning_snapshot,
            working_orders=(),
            reservations=reservations,
            availability=replace(
                availability,
                ledger_state_hash=planning_snapshot.journal_state_hash,
            ),
            policy=rebalance,
            as_of=target_event.event_time,
        )
        if (
            coordinated.decision is None
            or len(coordinated.decision.plan.planned_orders) != 1
        ):
            raise ValueError("each target change must produce exactly one order")
        intent = coordinated.decision.plan.planned_orders[0].intent
        order = domain.Order(
            identities.domain_id(f"order.{index}.0"),
            result.intent.execution_account_id,
            intent,
            domain.SimulationInstant(
                target_event.event_time,
                domain.TimelinePhase(80, "order_admission"),
                domain.SourceSequence(0),
            ),
        )
        admission_events = tuple(
            OrderEventPlan(
                event_type,
                identities.event_id(f"order-event.{index}.0.{event_index}"),
                domain.SimulationInstant(
                    target_event.event_time,
                    domain.TimelinePhase(80, "order_admission"),
                    domain.SourceSequence(event_index),
                ),
                f"{target_event.event_id}:{event_type.value}"
                if event_type
                in {
                    domain.OrderEventType.ORDER_SUBMITTED,
                    domain.OrderEventType.ORDER_ACCEPTED,
                }
                else None,
            )
            for event_index, event_type in enumerate(event_types)
        )
        admission = ResolvedOrderAdmission(
            order,
            _capabilities(result),
            _translation_mapping(),
            target_event.event_time,
            _pretrade(result, order, sizing_input.mark.price, target_event.event_time),
            admission_events,
        )
        cycle = ResolvedDecisionCycle(
            schedule,
            allocations,
            _NOTIONAL_SCALE,
            risk,
            sizing_policy,
            (sizing_input,),
            validity,
            rebalance,
            target_event.event_time,
            (admission,),
            planning_snapshot,
        )
        execution_mark = _execution_mark(result, projection_event)
        market_state = SlippageMarketState(
            "normal",
            projection_event.event_time,
            projection_event.available_time,
            projection_event.event_id,
            projection_event.revision_id,
            projection_event.event_hash,
        )
        fill_id = identities.domain_id(f"fill.{index}")
        fill_recorded = domain.SimulationInstant(
            projection_event.event_time,
            domain.TimelinePhase(90, "accounting"),
            domain.SourceSequence(1),
        )
        fee_recorded = domain.SimulationInstant(
            projection_event.event_time,
            domain.TimelinePhase(90, "accounting"),
            domain.SourceSequence(3),
        )
        account = result.profile_composition_request.account_profile
        if account is None:
            raise ValueError("profile lacks final fee authority")
        cash_key, position_key = _keys(result)
        payload = LinearDerivativeFillAccountingPlan(
            position_key,
            result.resolved_profile.linear_contract,
            trading.LedgerBalanceRegistration(cash_key, _MONEY_SCALE),
            domain.QuantizationPolicy(
                "binance-usdm-tradifi.realized-half-even.v1",
                _MONEY_SCALE,
                domain.RoundingPolicy.HALF_EVEN,
            ),
        )
        accounting = FillAccountingDispatchPlan(
            projection_event.event_id,
            fill_id,
            result.financial_dispatcher_spec.position_accounting_component,
            payload,
            _LinearFillSemantics(
                position_key,
                result.resolved_profile.linear_contract,
            ),
            identities.domain_id(f"journal.fill.{index}"),
            fill_recorded,
            FeeAccountingDispatchPlan(
                cash_key,
                account.final_fee_rule_set,
                identities.domain_id(f"fee.{index}"),
                projection_event.event_time,
                identities.domain_id(f"journal.fee.{index}"),
                fee_recorded,
            ),
            (f"position_accounting.{index + 1}",),
        )
        bar = ResolvedBarExecution(
            projection_event.event_id,
            order.order_id,
            _pretrade(
                result, order, execution_mark.price, projection_event.available_time
            ),
            BarLiquidityEvidence.create(
                evidence_key=f"binance-usdm-tradifi.first-retained-trade.{index + 1}",
                evidence_version=1,
                market_event=projection_event,
                evaluated_at=projection_event.available_time,
                approved=True,
                reason_code=None,
                source_hash=projection_event.event_hash,
            ),
            market_state,
            result.resolved_profile.simulation.slippage_model,
            fill_id,
            identities.event_id(f"order-event.fill.{index}"),
            domain.SimulationInstant(
                projection_event.event_time,
                domain.TimelinePhase(70, "fill"),
                domain.SourceSequence(1),
            ),
            accounting,
            "taker",
        )
        cycles.append(cycle)
        bars.append(bar)
        current_quantity = sized.normalized_target.targets[0].decision.final_quantity
        current_lots = _planning_lots(
            result,
            sized.normalized_target,
            sizing_input.mark,
            target_event.event_time,
        )

    roles = tuple(
        sorted(
            (
                "final_snapshot",
                "margin_projection.final",
                *(f"position_accounting.{index + 1}" for index in range(len(bars))),
                *(
                    role
                    for event in scheduled_events
                    for role in event.expected_artifact_roles
                ),
            )
        )
    )
    return _ExecutionCasePlan(
        tuple(cycles),
        tuple(bars),
        financial,
        FinancialDispatchPlan(
            result.financial_dispatcher_spec,
            scheduled_events,
            snapshot,
            roles,
        ),
        result.resolved_profile.simulation.execution_model,
        snapshot,
        MarkToMarketCloseoutPolicy(),
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiCasePlanningResult:
    preparation_result_digest: str
    request: BacktestRequest
    resolved_request: ResolvedBacktestRequest
    market_data_preparation: MultiResolutionMarketDataPreparation
    hydrated_inputs: _HydratedExecutionCaseInputs
    execution_case: ResolvedExecutionCase
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.request != self.resolved_request.request:
            raise ValueError("resolved request mismatch")
        if (
            self.hydrated_inputs.execution_case_semantic_spec.semantic_spec_hash
            != self.request.execution_case_semantic_hash
        ):
            raise ValueError("hydrated semantic identity mismatch")
        if (
            self.execution_case.semantic_spec_hash
            != self.request.execution_case_semantic_hash
        ):
            raise ValueError("execution Case semantic identity mismatch")
        object.__setattr__(self, "result_digest", domain.canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_case_planning_result",
            "schema_version": _SCHEMA_VERSION,
            "preparation_result_digest": self.preparation_result_digest,
            "request": self.request,
            "resolved_request": self.resolved_request,
            "market_data_preparation": self.market_data_preparation,
            "hydrated_inputs": {
                "execution_case_semantic_spec": (
                    self.hydrated_inputs.execution_case_semantic_spec
                ),
                "timeline_stream_keys": self.hydrated_inputs.timeline_stream_keys,
                "target_stream_digest": (
                    self.hydrated_inputs.target_stream.target_stream_digest
                ),
                "timeline_batch_size": self.hydrated_inputs.timeline_batch_size,
                "execution_case_hash": self.execution_case.case_hash,
            },
            "execution_case": self.execution_case,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "result_digest": self.result_digest}


def _trusted_result(value: object) -> BinanceUsdmTradifiCasePlanningResult | None:
    if type(value) is not BinanceUsdmTradifiCasePlanningResult:
        return None
    try:
        rebuilt = BinanceUsdmTradifiCasePlanningResult(
            value.preparation_result_digest,
            value.request,
            value.resolved_request,
            value.market_data_preparation,
            value.hydrated_inputs,
            value.execution_case,
        )
        if not _same(rebuilt, value) or value.result_digest != domain.canonical_sha256(
            value._body()
        ):
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt


def plan_binance_usdm_tradifi_case_v1(
    preparation_result: BinanceUsdmTradifiPreparationResult,
) -> BinanceUsdmTradifiCasePlanningResult:
    trusted = _trusted_preparation(preparation_result)
    if trusted is None:
        raise ValueError("preparation_result must be an exact accepted result")
    identity_plan = _identity_plan(trusted)
    timeline_keys = tuple(
        sorted(
            (
                trusted.target_stream_key,
                _projection_stream(trusted),
                _FUNDING_STREAM,
                _LIQUIDATION_STREAM,
            )
        )
    )
    timeline = DeterministicTimeline.open(
        reader=trusted.market_reader,
        stream_keys=timeline_keys,
        window=trusted.intent.timeline_window,
    )
    if type(timeline) is not DeterministicTimeline:
        raise ValueError("retained TradFi Bundle did not open a deterministic Timeline")
    preparation = _preparation(trusted)
    placeholder_factory = ExecutionCaseIdentityFactory(
        semantic_run_id=_PLACEHOLDER_RUN_ID,
        namespace=_NAMESPACE,
        identity_plan=identity_plan,
    )
    placeholder_plan = _plan(
        trusted,
        _PLACEHOLDER_RUN_ID,
        placeholder_factory.domain_id("journal.initial.0"),
    )
    spec = _execution_case_semantic_spec_v3(
        base_spec=_base_spec(trusted, timeline, identity_plan),
        execution_case_plan=placeholder_plan,
        market_data_preparation=preparation,
    )
    request = _request(trusted, spec.semantic_spec_hash)
    resolved = _resolve(trusted, request)
    identities = ExecutionCaseIdentityFactory(
        semantic_run_id=resolved.semantic_run_id,
        namespace=_NAMESPACE,
        identity_plan=identity_plan,
    )
    actual_plan = _plan(
        trusted,
        resolved.semantic_run_id,
        identities.domain_id("journal.initial.0"),
    )
    recomputed = _execution_case_semantic_spec_v3(
        base_spec=spec,
        execution_case_plan=actual_plan,
        market_data_preparation=preparation,
    )
    if recomputed != spec:
        raise ValueError("canonical identities changed TradFi Case semantics")
    hydrated = _HydratedExecutionCaseInputs(
        spec,
        timeline_keys,
        trusted.target_stream,
        64,
        actual_plan,
    )
    case = _compose_execution_case_v3(
        resolved_request=resolved,
        market_reader=trusted.market_reader,
        hydrated_inputs=hydrated,
        market_data_preparation=preparation,
    )
    return BinanceUsdmTradifiCasePlanningResult(
        trusted.result_digest,
        request,
        resolved,
        preparation,
        hydrated,
        case,
    )


__all__ = [
    "BinanceUsdmTradifiCasePlanningResult",
    "plan_binance_usdm_tradifi_case_v1",
]
