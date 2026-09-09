"""Public preparation of the finite, single-instrument CN closed-bar route.

Preparation resolves immutable market rules and reserves identities only. Orders,
quantities, fees, holdings and settlement amounts belong to the standard Engine.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import hashlib
import json
import re

import crypto_quant_domain as d
import crypto_quant_trading as t
import crypto_quant_trading.profiles.cn_a_share as cn
from crypto_quant_market_data import MarketBundleReader, MarketBundleRef, MarketEvent

from .artifact_envelope_reader import ArtifactEnvelopeReader
from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .cash_development_provider import (
    CashDevelopmentRequestIntent, PreparedBacktestExecution, _canonical_text,
    _events, _provider_build_manifest, _publish, _verify_published,
)
from .cn_a_share_development_profile_v2 import CnAShareResolvedProfileV2
from .cn_a_share_development_runtime_v2 import CnAShareDevelopmentFinancialDispatcherV2
from .composition import ExecutionCaseComposer
from .engine import (
    ExecutionCaseIdentityFactory, ExecutionCaseIdentityRule, ExecutionCaseSemanticSpec,
    OrderEventPlan, PositionLotBook, ResolvedBarPlanV2, ResolvedCashPreTradeAuthority,
    ResolvedDecisionCycleV2, ResolvedExecutionCaseV2, ResolvedFinancialState, ResolvedOrderAdmissionSlot,
)
from .execution import BAR_CLOSE_CAPABILITY, BarLiquidityEvidence, NextEligibleBarCloseModel, NoEligibleBarAction
from .execution_inputs import BacktestExecutionRequest, materialize_execution_input_bundle_v7
from .facade import BacktestRuntime
from .financial_dispatch import (
    CashFillAccountingPlan, FeeAccountingDispatchPlan, FinancialDispatchPlan, FinancialDispatcherSpec,
    FullFillOrderFeeAccountingPlan, LedgerCashSnapshotProjectionPlan, ProfileFeeRuleBinding,
    SettlementFillAccountingDispatchPlan, SettlementIdentitySlot,
)
from .ports import SimulationComponentRef, SimulationPortType
from .request_registration import BacktestRequestRef
from .resolution import (
    BacktestProfileRegistry, BacktestRequest, BuildArtifactManifest, ExecutionAccountProfileRegistration,
    MarketSemanticsProfileRegistration, ProfileResolver, RequestedResultGrade,
    SimulationProfileRegistration, StrategyFamily,
)
from .run_end import MarkToMarketCloseoutPolicy
from .slippage import (
    DeterministicBpsSlippageModel, SlippageApplicabilityEnvelope, SlippageCalibrationRef,
    SlippageLimitation, SlippageMarketState,
)
from .target_repository import BacktestTargetStreamRef, BacktestTargetStreamRepository
from .target_stream import (
    PrecomputedTargetStream, PrecomputedTargetStreamAdapter, TargetStreamDecisionSchedule, TargetStreamScheduleEntry,
)
from .timeline import DeterministicTimelineV2, TimelineEvent, TimelineSegment

_PREFIX = "equity.cn_a_share.000703.closed-bar.development.v1"
_CNY, _CENT = d.CurrencyId("CNY"), d.Scale(2)
_NAMESPACE = d.IdentityNamespace("backtest", "1")
_QUANT = d.QuantizationPolicy(_PREFIX + ".notional", _CENT, d.RoundingPolicy.HALF_UP)
_COST = t.CostBasisPolicy(_PREFIX + ".fifo", 2, t.CostBasisMethod.FIFO, d.RoundingPolicy.HALF_UP)
_EVENT_TYPES = (d.OrderEventType.ORDER_INTENT_CREATED, d.OrderEventType.ORDER_CAPABILITY_APPROVED,
    d.OrderEventType.ORDER_TRANSLATED, d.OrderEventType.MARKET_RULE_APPROVED, d.OrderEventType.FEE_RESERVATION_ESTIMATED,
    d.OrderEventType.PRE_TRADE_RISK_APPROVED, d.OrderEventType.ORDER_SUBMITTED, d.OrderEventType.ORDER_ACCEPTED)
_LIMITATIONS = ("development_only", "single_cash_equity_full_fill", "zero_slippage_development_only",
    "full_liquidity_development_assumption", "no_scheduled_corporate_actions_in_window")


@dataclass(frozen=True, slots=True)
class CnAShareDailyOrderAuthority:
    """Source-backed daily inputs; prices are facts, never future order values."""

    trading_date: d.TradingDate
    trade_status: cn.CnAShareTradeStatusEvidence
    previous_close: cn.CnASharePreviousCloseEvidence
    lower_price_limit: d.Price
    upper_price_limit: d.Price
    price_limit_source_hash: str
    source_members: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        for name, expected in (("trading_date", d.TradingDate), ("trade_status", cn.CnAShareTradeStatusEvidence),
                ("previous_close", cn.CnASharePreviousCloseEvidence), ("lower_price_limit", d.Price), ("upper_price_limit", d.Price)):
            if type(getattr(self, name)) is not expected:
                raise TypeError(f"{name} must be exact {expected.__name__}")
        if type(self.price_limit_source_hash) is not str or re.fullmatch(r"sha256:[0-9a-f]{64}", self.price_limit_source_hash) is None:
            raise ValueError("price_limit_source_hash must be canonical")
        if (type(self.source_members) is not tuple or len(self.source_members) != 5
                or any(type(pair) is not tuple or len(pair) != 2 or any(type(value) is not str or not value for value in pair)
                    for pair in self.source_members)
                or tuple(key for key, _ in self.source_members) != tuple(sorted({key for key, _ in self.source_members}))):
            raise ValueError("retained daily source_members must be five sorted unique raw JSON members")
        iid = self.trade_status.instrument_id
        if (iid != self.previous_close.instrument_id
                or self.previous_close.reference_trading_date.calendar_id != self.trading_date.calendar_id
                or self.previous_close.reference_trading_date.value >= self.trading_date.value
                or self.trade_status.session_id.calendar_id != self.trading_date.calendar_id
                or any(price.instrument_id != str(iid) or price.quote_currency != "CNY" or price.scale != _CENT
                    or price.units <= 0 for price in (self.lower_price_limit, self.upper_price_limit))
                or self.lower_price_limit.units > self.upper_price_limit.units):
            raise ValueError("daily order authority instrument/date/price mismatch")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_daily_order_authority", "schema_version": 1,
            "trading_date": self.trading_date, "trade_status": self.trade_status, "previous_close": self.previous_close,
            "lower_price_limit": self.lower_price_limit, "upper_price_limit": self.upper_price_limit,
            "price_limit_source_hash": self.price_limit_source_hash, "source_members": self.source_members}


@dataclass(frozen=True, slots=True)
class CnAShareDevelopmentProviderInputs:
    schema_version: int
    build_artifact_manifest: BuildArtifactManifest
    profile: CnAShareResolvedProfileV2
    strategy_id: str
    sleeve_id: d.StrategySleeveId
    initial_cash: d.Money
    daily_order_authorities: tuple[CnAShareDailyOrderAuthority, ...]
    order_authority_declaration_json: str

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("CN provider schema_version must be 1")
        for name, expected in (("build_artifact_manifest", BuildArtifactManifest), ("profile", CnAShareResolvedProfileV2),
                ("sleeve_id", d.StrategySleeveId), ("initial_cash", d.Money)):
            if type(getattr(self, name)) is not expected:
                raise TypeError(f"{name} must be exact {expected.__name__}")
        _canonical_text("strategy_id", self.strategy_id)
        if type(self.order_authority_declaration_json) is not str or not self.order_authority_declaration_json:
            raise TypeError("order_authority_declaration_json must retain exact UTF-8 declaration text")
        if self.initial_cash.currency != "CNY" or self.initial_cash.scale != _CENT or self.initial_cash.units <= 0:
            raise ValueError("initial_cash must be positive CNY cents")
        values = self.daily_order_authorities
        if type(values) is not tuple or not values or any(type(value) is not CnAShareDailyOrderAuthority for value in values):
            raise TypeError("daily_order_authorities must be a nonempty exact tuple")
        dates = tuple(value.trading_date.value for value in values)
        if dates != tuple(sorted(set(dates))):
            raise ValueError("daily order authorities must be sorted and unique")
        scope = self.profile.request.instrument_scope
        if any(value.trade_status.instrument_id != scope.instrument.instrument_id
                or value.trade_status.source_hash != scope.rule_context.source_hash for value in values):
            raise ValueError("daily order authorities must bind the resolved instrument declaration")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_development_provider_inputs", "schema_version": 1,
            "build_artifact_manifest_hash": self.build_artifact_manifest.manifest_hash, "profile": self.profile,
            "strategy_id": self.strategy_id, "sleeve_id": self.sleeve_id, "initial_cash": self.initial_cash,
            "daily_order_authorities": self.daily_order_authorities,
            "order_authority_declaration_json": self.order_authority_declaration_json}


def _raw_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("retained JSON has duplicate fields")
    return result


def _retained_json(text: str) -> dict:
    value = json.loads(text, parse_float=Decimal, object_pairs_hook=_json_pairs)
    if type(value) is not dict:
        raise ValueError("retained JSON must contain an object")
    return value


def _retained_rows(text: str) -> tuple[dict, ...]:
    response = _retained_json(text)
    data = response["data"]
    fields, rows = data["fields"], data["items"]
    if (type(response["code"]) is not int or response["code"] != 0 or data["has_more"] is not False
            or type(fields) is not list or not fields or any(type(key) is not str for key in fields)
            or len(set(fields)) != len(fields) or type(rows) is not list
            or any(type(row) is not list for row in rows)):
        raise ValueError("retained response must be complete and successful")
    return tuple(dict(zip(fields, row, strict=True)) for row in rows)


def _verify_retained_daily_authority(inputs: CnAShareDevelopmentProviderInputs) -> None:
    """Bind parsed economic facts to exact bytes, not merely mutually consistent hashes."""
    try:
        declaration = _retained_json(inputs.order_authority_declaration_json)
        if (_raw_hash(inputs.order_authority_declaration_json) != inputs.profile.request.instrument_scope.rule_context.source_hash
                or declaration["type"] != "tushare_000703_month_order_authority_declaration_v1"
                or type(declaration["schema_version"]) is not int or declaration["schema_version"] != 1
                or declaration["ts_code"] != "000703.SZ" or declaration["development_only"] is not True
                or any(declaration[key] is not False for key in ("decision_grade_eligible", "live_eligible", "deployment_authorized"))):
            raise ValueError("retained declaration does not bind the resolved profile")
        members = declaration["raw_members"]
        for authority in inputs.daily_order_authorities:
            day = authority.trading_date.value.strftime("%Y%m%d")
            sources = dict(authority.source_members)
            prefix = f"response/{day}/"
            expected_keys = {prefix + name + ".json" for name in ("daily", "stk-limit", "stock-st", "suspend-d-r", "suspend-d-s")}
            if set(sources) != expected_keys or day not in declaration["open_sessions"]:
                raise ValueError("retained daily source member coverage mismatch")
            for key, raw in sources.items():
                if _raw_hash(raw) != members[key]["sha256"]:
                    raise ValueError("retained daily source member hash mismatch")
            [daily] = _retained_rows(sources[prefix + "daily.json"])
            [limits] = _retained_rows(sources[prefix + "stk-limit.json"])
            if any(value["ts_code"] != "000703.SZ" or value["trade_date"] != day for value in (daily, limits)):
                raise ValueError("retained daily instrument/date mismatch")
            if any(_retained_rows(sources[prefix + key + ".json"]) for key in ("stock-st", "suspend-d-r", "suspend-d-s")):
                raise ValueError("retained status is not the supported NORMAL terminal-zero authority")
            if (authority.trade_status.status is not cn.CnAShareTradeStatus.NORMAL
                    or authority.previous_close.source_hash != members[prefix + "daily.json"]["sha256"]
                    or authority.price_limit_source_hash != members[prefix + "stk-limit.json"]["sha256"]):
                raise ValueError("retained daily evidence source mismatch")
            for price, value in ((authority.previous_close.price, daily["pre_close"]),
                    (authority.lower_price_limit, limits["down_limit"]), (authority.upper_price_limit, limits["up_limit"])):
                if type(value) not in (int, Decimal) or Decimal(value) * 100 != price.units:
                    raise ValueError("retained daily economic value mismatch")
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ValueError("retained daily order authority verification failed") from error


def _clock(at: d.UtcInstant, rank: int, code: str, sequence: int = 0) -> d.SimulationInstant:
    return d.SimulationInstant(at, d.TimelinePhase(rank, code), d.SourceSequence(sequence))


def _bar_clock(event: MarketEvent, offset: int, code: str, sequence: int = 0) -> d.SimulationInstant:
    return _clock(event.event_time, event.phase.rank + offset, code, sequence)


def _simulation_ref(port: SimulationPortType, key: str, policy: object) -> SimulationComponentRef:
    return SimulationComponentRef(port, _PREFIX + "." + key, 1, d.canonical_sha256(policy))


def _profile_ref(port: t.ProfilePortType, key: str, policy: object) -> t.ProfileComponentRef:
    return t.ProfileComponentRef(port, _PREFIX + "." + key, 1, d.canonical_sha256(policy))


@dataclass(frozen=True, slots=True)
class _BarAuthority:
    event: MarketEvent
    receipt: cn.CnAShareBarCloseReceipt
    daily: CnAShareDailyOrderAuthority
    session: cn.CnAShareBarCloseSessionResolution
    rules: cn.CnAShareOrderRuleResolution
    pretrade: ResolvedCashPreTradeAuthority

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_closed_bar_authority", "schema_version": 1,
            "receipt": self.receipt, "daily": self.daily, "session": self.session, "rules": self.rules}


@dataclass(frozen=True, slots=True)
class _AccountingSemantics:
    cash_key: d.CashBalanceKey
    position_key: d.PositionBalanceKey
    preparation_authority_ref: d.ArtifactRef
    bar_authority: _BarAuthority

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_closed_bar_accounting_semantics", "schema_version": 1,
            "cash_key": self.cash_key, "position_key": self.position_key, "cost_basis_policy": _COST,
            "notional_quantization": _QUANT, "preparation_authority_ref": self.preparation_authority_ref,
            "bar_authority": self.bar_authority}


class _CnCaseBuilder:
    def __init__(self, intent: CashDevelopmentRequestIntent, inputs: CnAShareDevelopmentProviderInputs,
                 stream: PrecomputedTargetStream, reader: MarketBundleReader, authority_ref: d.ArtifactRef) -> None:
        _verify_retained_daily_authority(inputs)
        self.intent, self.inputs, self.stream, self.authority_ref = intent, inputs, stream, authority_ref
        request, window = inputs.profile.request, intent.timeline_window
        instrument = request.instrument_scope.instrument
        if (intent.execution_account_id != request.account_scope.account_id or intent.reporting_currency != _CNY
                or not request.timeline_window.data_start <= window.data_start < window.trading_start
                or not request.timeline_window.trading_start <= window.trading_start < window.end_exclusive <= request.timeline_window.end_exclusive):
            raise ValueError("CN request account/currency/window does not match resolved profile")
        [minute] = [value for value in request.minute_authorities if value.manifest == reader.manifest
            and MarketBundleRef.from_manifest(value.manifest) == reader.bundle_ref] or [None]
        if minute is None:
            raise ValueError("market reader must bind an exact resolved minute authority")
        events = _events(reader, minute.manifest.streams[0].stream_key)
        if events != minute.events:
            raise ValueError("market reader does not contain exact retained close events")
        events = tuple(event for event in events if window.data_start <= event.event_time < window.end_exclusive)
        if not events or not stream.events:
            raise ValueError("CN preparation requires actual close and target events")
        self.dispatcher = CnAShareDevelopmentFinancialDispatcherV2(inputs.profile, closed_bar_execution=True)
        if any(window.data_start <= event.event_at.instant < window.end_exclusive for event in self.dispatcher.scheduled_account_events):
            raise ValueError("scheduled corporate actions are not supported by this preparation version")
        self.catalog = d.InstrumentCatalog((_CNY,), (instrument,), ())
        self.cash_key = d.CashBalanceKey(intent.execution_account_id, instrument.instrument_id.venue, _CNY)
        self.position_key = d.PositionBalanceKey(intent.execution_account_id, instrument.instrument_id.venue, instrument.instrument_id)
        self.binding = ProfileFeeRuleBinding(self.dispatcher.spec.spec_hash, _CNY, _CENT)
        self.account_risk = t.AccountRiskPolicy.create(policy_key=_PREFIX + ".account-risk", policy_version=1,
            account_id=intent.execution_account_id, venue_id=instrument.instrument_id.venue,
            allowed_sides=(d.OrderSide.BUY, d.OrderSide.SELL),
            allowed_position_effects=(d.PositionEffect.AUTO, d.PositionEffect.OPEN, d.PositionEffect.CLOSE),
            allowed_reduce_only_values=(False, True), fee_reserve_funding_source=t.FeeReserveFundingSource.TRADABLE_CASH,
            order_capacity_limit=1, exposure_capacity_limits=(t.ExposureCapacityLimit(inputs.initial_cash),))
        session_model = cn.CnAShareCashSessionModel(request.calendar)
        rule_model = cn.CnAShareCashOrderRuleModel(request.order_rule_book, _CENT)
        daily_by_date = {value.trading_date.value: value for value in inputs.daily_order_authorities}
        authorities = []
        used_dates = set()
        for event in events:
            receipt = self.dispatcher.bar_close_receipt(event.event_id)
            session = session_model.resolve_bar_close(receipt).result
            if session is None or not session.is_eligible or session.physical_session.trading_date is None:
                raise ValueError("close lacks eligible frozen session authority")
            day = session.physical_session.trading_date.value
            daily = daily_by_date.get(day)
            if daily is None or daily.trading_date != session.physical_session.trading_date:
                raise ValueError("missing daily order authority")
            # The calendar remains the sole owner of successor dates. No guessed
            # next weekday, not even when this bar ultimately has no order.
            if not any(value.local_date > day and value.kind is cn.CnAShareCalendarDayKind.TRADING for value in request.calendar.days):
                raise ValueError("missing frozen settlement successor")
            known_previous = tuple(value.local_date for value in request.calendar.days
                if value.local_date < day and value.kind is cn.CnAShareCalendarDayKind.TRADING)
            if known_previous and daily.previous_close.reference_trading_date.value != known_previous[-1]:
                raise ValueError("previous close does not bind the frozen preceding trading date")
            query = cn.CnAShareBarCloseOrderRuleQuery(instrument, session, request.instrument_scope.rule_context,
                daily.trade_status, daily.previous_close)
            outcome = rule_model.resolve_bar_close_rules(query)
            rules = outcome.result
            if rules is None or rules.timeline is None:
                raise ValueError("closed-bar order authority cannot resolve")
            [interval] = rules.timeline.intervals
            if (interval.snapshot.session_state is not t.MarketSessionState.EXECUTION_RECEIPT
                    or interval.snapshot.lower_price_limit != daily.lower_price_limit
                    or interval.snapshot.upper_price_limit != daily.upper_price_limit):
                raise ValueError("retained daily limits/status do not match closed-bar rules")
            pretrade = ResolvedCashPreTradeAuthority(rules.timeline, t.OrderRuleNotionalEvidence(
                t.NotionalPriceBasis.SUPPLIED_REFERENCE, receipt.close_price, event.event_hash, event.available_time),
                event.event_time, self.binding, _PREFIX + ".resource-requirement", 1,
                d.canonical_sha256({"order_rule_outcome": outcome, "daily": daily, "preparation_authority_ref": authority_ref}),
                self.account_risk)
            authorities.append(_BarAuthority(event, receipt, daily, session, rules, pretrade))
            used_dates.add(day)
        if used_dates != set(daily_by_date):
            raise ValueError("daily order authorities must exact-cover the preparation window")
        self.bars = tuple(authorities)
        by_time = {bar.event.event_time: bar for bar in self.bars}
        self.signals = []
        self.expiries: dict[str, d.UtcInstant] = {}
        for target in stream.events:
            source = by_time.get(target.event_time)
            candidate = target.payload.get("candidate")
            if (source is None or not window.trading_start <= target.event_time < window.end_exclusive
                    or target.available_time != target.event_time
                    or target.timeline_instant <= _bar_clock(source.event, 5, "order_fee", 2)
                    or not isinstance(candidate, Mapping)
                    or candidate.get("observed_through") != source.event.event_time.epoch_nanoseconds):
                raise ValueError("target must observe an actual same-UTC close after its processing receipt")
            expiry = candidate.get("expires_at")
            if type(expiry) is not int or not target.event_time.epoch_nanoseconds < expiry <= window.end_exclusive.epoch_nanoseconds:
                raise ValueError("target expiry must be explicit and within the preparation window")
            schedule = self.schedule(target)
            injection = PrecomputedTargetStreamAdapter().inject(stream=stream,
                timeline_events=(TimelineEvent(TimelineSegment.ACTIVE_TRADING, target),), schedule=schedule)
            if injection.injection is None:
                raise ValueError("target candidate does not match the bound strategy/sleeve/instrument")
            self.signals.append(source)
            self.expiries[target.event_id] = d.UtcInstant(expiry)
        self.signals = tuple(self.signals)
        timeline = DeterministicTimelineV2.open(reader=reader, stream_keys=(minute.manifest.streams[0].stream_key,),
            target_stream=stream, window=window)
        if type(timeline) is not DeterministicTimelineV2:
            raise ValueError("CN timeline cannot resolve")
        self.timeline = timeline
        self.execution = NextEligibleBarCloseModel.create(actions=tuple((tif, NoEligibleBarAction.EXPIRE) for tif in d.TimeInForce))
        self.closeout = MarkToMarketCloseoutPolicy()
        maximum = min(interval.snapshot.max_market_order_quantity_units for bar in self.bars
            if bar.rules.timeline is not None for interval in bar.rules.timeline.intervals)
        if maximum is None:
            raise ValueError("CN order authority requires a finite market order quantity limit")
        zero_policy = {"type": "cn_closed_bar_zero_slippage", "schema_version": 1,
            "basis_points": 0, "price_policy": "exact_retained_close", "rounding": "half_up"}
        self.slippage = DeterministicBpsSlippageModel(SimulationComponentRef(SimulationPortType.SLIPPAGE_MODEL,
            "zero_slippage.development.v1", 1, d.canonical_sha256(zero_policy)),
            SlippageCalibrationRef(_PREFIX + ".zero-slippage", 1, d.canonical_sha256(zero_policy)),
            SlippageApplicabilityEnvelope.create(envelope_key=_PREFIX + ".zero-slippage", envelope_version=1,
                instrument_id=instrument.instrument_id, valid_from=window.data_start, valid_to_exclusive=window.end_exclusive,
                maximum_quantity=d.Quantity(maximum, d.Scale(0), str(instrument.instrument_id)), allowed_market_state_keys=("normal",)),
            0, d.Scale(0), d.RoundingPolicy.HALF_UP, (SlippageLimitation.ZERO_SLIPPAGE_DEVELOPMENT_ONLY,))

    def schedule(self, event: MarketEvent) -> TargetStreamDecisionSchedule:
        inputs = self.inputs
        context = t.StrategyOutputValidationContext(inputs.strategy_id, inputs.sleeve_id, event.event_time,
            self.catalog, (self.position_key.instrument_id,), decision_instant=event.timeline_instant)
        return TargetStreamDecisionSchedule(event.event_time, TimelineSegment.ACTIVE_TRADING, (
            TargetStreamScheduleEntry(event.event_id, t.DecisionBatchExpectation(inputs.strategy_id, inputs.sleeve_id), context),))

    def identity_plan(self) -> tuple[ExecutionCaseIdentityRule, ...]:
        kinds: dict[str, d.DomainIdKind | None] = {"journal.initial.0": d.DomainIdKind.JOURNAL}
        for i in range(len(self.stream.events)):
            kinds[f"order.{i}.0"], kinds[f"order-event.expire.{i}"] = d.DomainIdKind.ORDER, None
            for j in range(8):
                kinds[f"order-event.{i}.0.{j}"] = None
        for i in range(len(self.bars)):
            for key, kind in (("fill", d.DomainIdKind.FILL), ("journal.fill", d.DomainIdKind.JOURNAL),
                    ("fee", d.DomainIdKind.FEE), ("journal.fee", d.DomainIdKind.JOURNAL),
                    ("fee.fill", d.DomainIdKind.FEE), ("journal.fee.fill", d.DomainIdKind.JOURNAL), ("order-event.fill", None)):
                kinds[f"{key}.{i}"] = kind
            for j in range(2):
                for key, kind in (("settlement", d.DomainIdKind.SETTLEMENT), ("settlement-event.recorded", None), ("settlement-event.applied", None)):
                    kinds[f"{key}.{i}.{j}"] = kind
        return tuple(ExecutionCaseIdentityRule(key, _PREFIX + "." + key, 0, kind) for key, kind in kinds.items())

    def snapshot(self, at: d.SimulationInstant, source: _BarAuthority) -> LedgerCashSnapshotProjectionPlan:
        event = source.event
        age = at.instant.epoch_nanoseconds - event.event_time.epoch_nanoseconds
        mark = t.ResolvedMark(self.position_key.instrument_id, _CNY, d.PricePurpose.VALUATION, source.receipt.close_price,
            event.event_time, event.available_time, at.instant, age, event.stream_key, event.event_id, event.revision_id,
            _PREFIX + ".actual-close-valuation", 1,
            d.canonical_sha256({"source_receipt": source.receipt, "projection_at": at, "policy": "last_observed_close_with_explicit_age"}),
            available_at_instant=event.timeline_instant, resolved_at_instant=at)
        return LedgerCashSnapshotProjectionPlan((mark,), _CNY, _CENT, at, self.catalog,
            t.CurrencyValuationGraph(at.instant, d.PricePurpose.VALUATION, ()), _QUANT)

    def semantic_spec(self) -> ExecutionCaseSemanticSpec:
        identities = ExecutionCaseIdentityFactory(semantic_run_id="cn-preparation-template", namespace=_NAMESPACE, identity_plan=self.identity_plan())
        case = self.build(identities, "sha256:" + "0" * 64)
        return ExecutionCaseComposer.semantic_spec_from_case(case, spec_key=_PREFIX, spec_version=1,
            identity_namespace=_NAMESPACE, identity_plan=self.identity_plan())

    def build(self, identities: ExecutionCaseIdentityFactory, semantic_spec_hash: str) -> ResolvedExecutionCaseV2:
        initial = self.inputs.initial_cash
        start = self.intent.timeline_window.data_start
        schema = t.LedgerSchema((t.LedgerBalanceRegistration(self.cash_key, _CENT), t.LedgerBalanceRegistration(self.position_key, d.Scale(0))))
        deposit = d.AccountingJournalEntry(identities.domain_id("journal.initial.0"), d.AccountingEntryType.CAPITAL_DEPOSITED,
            self.intent.execution_account_id, self.cash_key.venue_id, start, _clock(start, 1, "initial_capital"),
            (self.authority_ref.content_hash,), (d.BalanceChange(self.cash_key, initial),), (), (), ())
        journal = t.AccountingJournal.from_entries((deposit,))
        ledger, zero = t.GenericLedger(schema).project(journal), d.Money(0, _CENT, "CNY")
        snapshot = d.PortfolioSnapshot(self.intent.execution_account_id, start, _CNY, ledger.cash_balances, (),
            zero, zero, zero, zero, initial, (), ledger.state_hash, d.canonical_sha256(()), d.canonical_sha256(()),
            t.CurrencyValuationGraph(start, d.PricePurpose.VALUATION, ()).graph_hash)
        financial = ResolvedFinancialState(journal, schema, snapshot, (PositionLotBook(self.position_key),), (), (), (),
            t.SettlementBook(self.intent.execution_account_id), cn.CnAShareCashSettlementModel(self.inputs.profile.request.calendar).availability_rules(schema))
        risk = t.PortfolioRiskPolicy.create(policy_key=_PREFIX + ".portfolio-risk", policy_version=1,
            valuation_currency=_CNY, notional_scale=_CENT, limits=tuple(t.PortfolioRiskLimit(name, scope, initial, t.PortfolioRiskAction.REJECT, iid)
                for name, scope, iid in (("gross", t.PortfolioRiskScope.GROSS_EXPOSURE, None),
                    ("net", t.PortfolioRiskScope.ABSOLUTE_NET_EXPOSURE, None),
                    ("target", t.PortfolioRiskScope.TARGET_ABSOLUTE_NOTIONAL, self.position_key.instrument_id))))
        sizing = t.PositionSizingPolicy.create(policy_key=_PREFIX + ".sizing", policy_version=1,
            price_purpose=d.PricePurpose.VALUATION, rounding=d.RoundingPolicy.TOWARD_ZERO, residual_policy=t.ResidualPositionPolicy.CLOSE_IF_PERMITTED)
        allocation = t.CapitalAllocationPolicyRef(_PREFIX + ".capital", 1,
            d.canonical_sha256({"allocation_basis": "current_equity", "strategy_id": self.inputs.strategy_id, "sleeve_id": self.inputs.sleeve_id}))
        rebalance = t.RebalancePolicy.create(policy_key=_PREFIX + ".rebalance", policy_version=1,
            execution_style=d.ExecutionStyle.MARKET, time_in_force=d.TimeInForce.GTC, urgency="normal", plan_valid_for_nanoseconds=None)
        capability = t.OrderCapabilitySet.create(capability_set_key=_PREFIX + ".capabilities", capability_set_version=1,
            style_capabilities=(t.OrderStyleCapability(d.ExecutionStyle.MARKET, (t.PriceConstraintShape.NONE,), (d.TimeInForce.GTC,)),),
            supports_reduce_only=True, supported_position_effects=(d.PositionEffect.AUTO, d.PositionEffect.OPEN, d.PositionEffect.CLOSE),
            declared_capability_keys=tuple(value.value for value in t.OrderCapabilityKey))
        names = ("instrument_id", "side", "quantity", "execution_style", "price_constraint", "time_in_force", "reduce_only", "position_effect", "urgency", "reason", "parent_id")
        translation = t.OrderTranslationMapping.create(translator_key=_PREFIX + ".translation", translator_version=1,
            target_profile_id=_PREFIX, field_rules=tuple(t.OrderTranslationFieldRule(name, name) for name in names))
        cycles = []
        for i, (event, source) in enumerate(zip(self.stream.events, self.signals, strict=True)):
            plans = tuple(OrderEventPlan(kind, identities.event_id(f"order-event.{i}.0.{j}"),
                _clock(event.event_time, event.phase.rank + 1, "order_admission", j),
                _PREFIX + ".simulated_venue" if j >= 6 else None) for j, kind in enumerate(_EVENT_TYPES))
            slot = ResolvedOrderAdmissionSlot(identities.domain_id(f"order.{i}.0"), capability, translation, event.event_time,
                source.pretrade, plans, identities.event_id(f"order-event.expire.{i}"))
            assert source.rules.timeline is not None
            cycles.append(ResolvedDecisionCycleV2(self.schedule(event), self.snapshot(event.timeline_instant, source),
                allocation, _CENT, risk, sizing, source.rules.timeline.intervals[0].snapshot.quantity_lattice,
                self.expiries[event.event_id], rebalance, slot))
        scenario = self.inputs.profile.request.commission_scenario
        legacy_order_rules = cn.CnAShareJanuary2024CommissionScenario(scenario.scenario_key, scenario.commission_rate,
            scenario.account_fee_schedule_ref, scenario.development_only).final_order_rule_set(*self.dispatcher.fee_policy_components)
        bars = []
        for i, source in enumerate(self.bars):
            event = source.event
            fill_at, fee_at = _bar_clock(event, 3, "fill_accounting"), _bar_clock(event, 5, "order_fee", 2)
            payload = CashFillAccountingPlan(self.cash_key, self.position_key, _COST, _QUANT,
                identities.domain_id(f"journal.fill.{i}"), fill_at, legacy_order_rules,
                identities.domain_id(f"fee.{i}"), event.event_time, identities.domain_id(f"journal.fee.{i}"), fee_at)
            child = FeeAccountingDispatchPlan(self.cash_key, self.binding, identities.domain_id(f"fee.fill.{i}"),
                event.event_time, identities.domain_id(f"journal.fee.fill.{i}"), _bar_clock(event, 4, "fill_fee", 2))
            fee = FullFillOrderFeeAccountingPlan(self.cash_key, self.binding, payload.fee_assessment_id,
                event.event_time, payload.fee_journal_entry_id, fee_at, child)
            accounting = SettlementFillAccountingDispatchPlan(event.event_id, identities.domain_id(f"fill.{i}"),
                self.dispatcher.spec.position_accounting_component, payload,
                _AccountingSemantics(self.cash_key, self.position_key, self.authority_ref, source),
                payload.fill_journal_entry_id, fill_at, fee,
                tuple(f"{role}.{event.event_id}" for role in ("position_accounting", "settlement", "settlement_resolution")),
                settlement_slots=tuple(SettlementIdentitySlot(key, identities.domain_id(f"settlement.{i}.{j}"),
                    identities.event_id(f"settlement-event.recorded.{i}.{j}"), identities.event_id(f"settlement-event.applied.{i}.{j}"))
                    for j, key in enumerate((self.cash_key, self.position_key))),
                settlement_recorded_at=_bar_clock(event, 2, "settlement_record"))
            bars.append(ResolvedBarPlanV2(event.event_id, self.position_key.instrument_id, source.pretrade,
                BarLiquidityEvidence.create(evidence_key=_PREFIX + ".full-liquidity", evidence_version=1,
                    market_event=event, evaluated_at=event.event_time, approved=True, reason_code=None,
                    source_hash=d.canonical_sha256({"event_hash": event.event_hash, "policy": "development_full_fill_only"})),
                SlippageMarketState("normal", event.event_time, event.available_time, event.event_id, event.revision_id, event.event_hash),
                self.slippage, identities.domain_id(f"fill.{i}"), identities.event_id(f"order-event.fill.{i}"),
                _bar_clock(event, 1, "fill"), accounting))
        final = self.snapshot(_clock(self.intent.timeline_window.end_exclusive, 1_000_000, "engine_finalize"), self.bars[-1])
        dispatch = FinancialDispatchPlan(self.dispatcher.spec, (), final,
            ("final_snapshot", "runtime.identity_closure", *(f"snapshot.{event.event_id}" for event in self.stream.events)))
        return ResolvedExecutionCaseV2(_PREFIX, 1, semantic_spec_hash, self.timeline, 128, self.stream,
            tuple(cycles), tuple(bars), financial, dispatch, self.execution, final, self.closeout)


@dataclass(frozen=True, slots=True)
class _ProfileImplementation:
    kind: str
    profile: CnAShareResolvedProfileV2
    preparation_authority_ref: d.ArtifactRef
    component_manifest: tuple
    financial_dispatcher_spec: FinancialDispatcherSpec | None = None

    @property
    def profile_digest(self) -> str:
        return d.canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_closed_bar_" + self.kind + "_profile", "schema_version": 1,
            "profile_hash": self.profile.profile_hash, "preparation_authority_ref": self.preparation_authority_ref,
            "component_manifest": self.component_manifest, "financial_dispatcher_spec": self.financial_dispatcher_spec}

    def build_financial_dispatcher(self) -> CnAShareDevelopmentFinancialDispatcherV2:
        return CnAShareDevelopmentFinancialDispatcherV2(self.profile, closed_bar_execution=True)


def _registry(builder: _CnCaseBuilder) -> BacktestProfileRegistry:
    profile = builder.inputs.profile
    request, dispatcher = profile.request, builder.dispatcher
    spec = dispatcher.spec
    market_refs = tuple(sorted((cn.CnAShareCashSessionModel(request.calendar).closed_bar_component_ref,
        cn.CnAShareCashQuantityLatticeModel(builder.cash_key.venue_id, _CENT).component_ref,
        cn.CnAShareCashOrderRuleModel(request.order_rule_book, _CENT).closed_bar_component_ref,
        *dispatcher.fee_policy_components, cn.CnAShareCashSettlementModel(request.calendar).closed_bar_component_ref,
        spec.position_accounting_component, spec.financing_component, spec.margin_component,
        _profile_ref(t.ProfilePortType.LIQUIDATION_RULES, "no-liquidation", {"policy": "cash_long_only_no_liquidation"}),
        _profile_ref(t.ProfilePortType.CORPORATE_ACTION_MODEL, "no-in-window-actions",
            {"dividend_profile_hash": request.dividend_profile.profile_hash, "policy": "reject_scheduled_actions"}),
        _profile_ref(t.ProfilePortType.CURRENCY_VALUATION_POLICY, "cny-valuation", {"policy": "cny_identity_path_only"})),
        key=lambda ref: ref.port_type.value))
    simulation_refs = tuple(sorted((builder.execution.component_ref, builder.closeout.spec().component_ref,
        builder.slippage.component_ref, spec.liquidation_audit_component,
        _simulation_ref(SimulationPortType.LATENCY_MODEL, "latency", {"policy": "strictly_later_close"}),
        _simulation_ref(SimulationPortType.LIQUIDITY_MODEL, "full-liquidity", {"policy": "development_full_fill_only"})),
        key=lambda ref: ref.port_type.value))
    market = _ProfileImplementation("market", profile, builder.authority_ref, market_refs, spec)
    simulation = _ProfileImplementation("simulation", profile, builder.authority_ref, simulation_refs)
    account = _ProfileImplementation("account", profile, builder.authority_ref, ())
    limitations = tuple(sorted(set((*profile.limitations, *_LIMITATIONS))))
    venue, grade = builder.cash_key.venue_id.value, RequestedResultGrade.DEVELOPMENT
    return BacktestProfileRegistry((MarketSemanticsProfileRegistration(_PREFIX + ".market", 1, market.profile_digest,
        market, venue, (BAR_CLOSE_CAPABILITY,), market_refs, grade, limitations, False, spec),),
        (SimulationProfileRegistration(_PREFIX + ".simulation", 1, simulation.profile_digest, simulation, "bar",
            (StrategyFamily.PRECOMPUTED_TARGET,), (BAR_CLOSE_CAPABILITY,), simulation_refs, grade, limitations, False),),
        (ExecutionAccountProfileRegistration(_PREFIX + ".account", 1, account.profile_digest, account,
            builder.intent.execution_account_id, venue, "cash", "none", (_CNY,), grade, limitations, False),))


def prepare_cn_a_share_development_backtest(
    *, request_intent: CashDevelopmentRequestIntent, provider_inputs: CnAShareDevelopmentProviderInputs,
    target_stream_ref: BacktestTargetStreamRef, artifact_reader: ArtifactEnvelopeReader,
    artifact_publisher: ArtifactEnvelopePublisher, market_reader: MarketBundleReader, publication_root: Path,
) -> PreparedBacktestExecution:
    """Prepare only; call the returned standard runtime separately to execute."""
    if type(request_intent) is not CashDevelopmentRequestIntent or type(provider_inputs) is not CnAShareDevelopmentProviderInputs:
        raise TypeError("request and provider inputs must be exact public immutable values")
    if type(target_stream_ref) is not BacktestTargetStreamRef:
        raise TypeError("target_stream_ref must be exact BacktestTargetStreamRef")
    if not isinstance(market_reader, MarketBundleReader) or not isinstance(publication_root, Path):
        raise TypeError("market_reader/publication_root must satisfy the public ports")
    if not callable(getattr(artifact_reader, "read", None)) or not callable(getattr(artifact_publisher, "put", None)):
        raise TypeError("artifact reader/publisher must satisfy the public ports")
    target = BacktestTargetStreamRepository(reader=artifact_reader).load(target_stream_ref)
    authority = d.ArtifactEnvelope.create("cn_a_share_development_preparation_authority", 1, provider_inputs)
    builder = _CnCaseBuilder(request_intent, provider_inputs, target.target_stream, market_reader, d.ArtifactRef.from_envelope(authority))
    spec = builder.semantic_spec()
    registry = _registry(builder)
    build_manifest = _provider_build_manifest(provider_inputs.build_artifact_manifest, registry)
    request = BacktestRequest(1, request_intent.experiment_id, request_intent.timeline_window,
        _PREFIX + ".market", _PREFIX + ".simulation", _PREFIX + ".account", request_intent.execution_account_id,
        request_intent.reporting_currency, market_reader.bundle_ref, spec.target_stream_digest, spec.semantic_spec_hash,
        request_intent.master_random_seed, build_manifest.manifest_hash, StrategyFamily.PRECOMPUTED_TARGET,
        "bar", RequestedResultGrade.DEVELOPMENT)
    outcome = ProfileResolver().resolve(request=request, registry=registry, market_bundle_manifest=market_reader.manifest,
        build_artifact_manifest=build_manifest)
    if outcome.resolved is None:
        raise ValueError("CN development request cannot resolve")
    case = ExecutionCaseComposer().compose(resolved_request=outcome.resolved, builder=builder)
    bundle = materialize_execution_input_bundle_v7(resolved_request=outcome.resolved, execution_case=case)
    request_envelope = d.ArtifactEnvelope.create("backtest_request", 1, request)
    refs = []
    for envelope in (authority, request_envelope, bundle):
        ref = _publish(artifact_publisher, envelope)
        _verify_published(artifact_reader, ref, envelope)
        refs.append(ref)
    execution = BacktestExecutionRequest(7, request, refs[2])
    runtime = BacktestRuntime(registry=registry, artifact_reader=artifact_reader, artifact_publisher=artifact_publisher,
        market_reader=market_reader, publication_root=publication_root)
    return PreparedBacktestExecution(BacktestRequestRef.from_artifact_ref(refs[1]), outcome.resolved.semantic_run_id, execution, runtime)


__all__ = ["CnAShareDailyOrderAuthority", "CnAShareDevelopmentProviderInputs", "prepare_cn_a_share_development_backtest"]
