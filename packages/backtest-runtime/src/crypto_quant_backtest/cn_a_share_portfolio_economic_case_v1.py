"""Retained source binding, exact coordinates and sealed identities for economic portfolios."""
from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo
import crypto_quant_domain as d
from crypto_quant_domain import (ArtifactReadResult, ArtifactRef, CashBalanceKey, DomainIdKind,
    OrderSide, PositionBalanceKey, canonical_bytes, canonical_sha256)
from crypto_quant_market_data import EventCursor, MarketBundleReader, MarketEvent
from crypto_quant_trading import (CashAvailabilityRule, CashReservationUse, MarketSettlementRules,
    PositionAvailabilityRule, SettlementBook, CurrencyValuationGraph)
from crypto_quant_trading.profiles.cn_a_share import CnAShareCalendarDayKind
from crypto_quant_trading.profiles.cn_a_share.portfolio_economic_v1 import (
    CnAShareCashDividendStateV1, CnASharePortfolioEconomicProjectionInputsV1,
    project_cn_a_share_portfolio_economic_state_v1,
)
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .cn_a_share_portfolio_economic_definition_v1 import (
    CnASharePortfolioEconomicDevelopmentInputsV1, _read_economic_definition_v1,
)
from .cn_a_share_portfolio_economic_values_v1 import _read_cn_a_share_cash_dividend_action_set_v1
from .engine import ExecutionCaseIdentityRule, PositionLotBook, ResolvedFinancialState
from .execution import BAR_OPEN_CAPABILITY, BarOpenKind, BarOpenObservation
from .profile_portfolio_execution import _ResolvedProfilePortfolioCaseV2
from .target_repository import BacktestTargetStreamRef, BacktestTargetStreamRepository
from .target_stream import PrecomputedTargetStream
from .timeline import TimelineWindow


def _native_initial_economic_financial_state_v1(inputs: CnASharePortfolioEconomicDevelopmentInputsV1):
    if type(inputs) is not CnASharePortfolioEconomicDevelopmentInputsV1:
        raise TypeError("economic initialization requires exact inputs")
    scope = inputs.scope
    cash = tuple(r.key for r in scope.ledger_schema.cash_registrations)
    positions = tuple(r.key for r in scope.ledger_schema.registrations if type(r.key) is PositionBalanceKey)
    rules = MarketSettlementRules.create(policy_key="cn.portfolio.economic.settled-only.development", policy_version=1,
        account_id=scope.account_id,
        cash_rules=tuple(CashAvailabilityRule(key, False, False, False,
            (CashReservationUse.CASH, CashReservationUse.FEE_RESERVE),
            (CashReservationUse.CASH, CashReservationUse.FEE_RESERVE), ()) for key in cash),
        position_rules=tuple(PositionAvailabilityRule(key, False) for key in positions))
    state = CnAShareCashDividendStateV1(scope.account_id, inputs.initial_marks.at, ())
    book = SettlementBook(scope.account_id)
    outcome = project_cn_a_share_portfolio_economic_state_v1(CnASharePortfolioEconomicProjectionInputsV1(
        inputs.initial_journal, scope.ledger_schema, book, (), (), rules, scope.instrument_catalog,
        inputs.initial_marks.marks, CurrencyValuationGraph(state.as_of.instant, d.PricePurpose.VALUATION, ()),
        inputs.notional_quantization, state, state.as_of))
    if outcome.projection is None:
        raise ValueError("economic initial native projection rejected: " + str(outcome.failure))
    projection = outcome.projection
    financial = ResolvedFinancialState(inputs.initial_journal, scope.ledger_schema, projection.base_snapshot,
        tuple(PositionLotBook(key) for key in positions), (), (), (), book, rules)
    return financial, state, projection


def _wall_clock_v1(instant, hour, minute):
    local = instant.to_datetime().astimezone(ZoneInfo("Asia/Shanghai"))
    return (local.hour, local.minute, local.second, local.microsecond) == (hour, minute, 0, 0) and instant.epoch_nanoseconds % 1000000000 == 0


def _clock_v1(instant, rank, sequence=0):
    return d.SimulationInstant(instant, d.TimelinePhase(rank, "cn_economic_native"), d.SourceSequence(sequence))


def _economic_events_v1(inputs):
    action_set = inputs.dividend_actions
    rows = []
    for action in action_set.actions:
        coordinates = (("REGISTER", action.registered_at), ("ENTITLE", action.entitlement_at), ("PAY", action.payment_due_at))
        if action.tax_policy.mode == "FIXED_RATIO":
            coordinates += (("TAX", action.tax_policy.due_at),)
        for kind, at in coordinates:
            event_id = canonical_sha256({"type": "cn_a_share_cash_dividend_event_coordinate", "schema_version": 1,
                "account_id": action_set.account_id, "instrument_id": action.instrument_id, "action_id": action.action_id,
                "action_set_hash": canonical_sha256(action_set), "action_terms_hash": canonical_sha256(action),
                "tax_policy_hash": canonical_sha256(action.tax_policy), "kind": kind, "event_at": at})
            rows.append((at, kind, action, event_id))
    return tuple(sorted(rows, key=lambda row: row[0]))


def _validate_economic_coordinates_v1(inputs, window, *, opening_times=None):
    if (not _wall_clock_v1(window.trading_start, 0, 0) or not _wall_clock_v1(window.end_exclusive, 0, 0)
            or inputs.initial_marks.at.instant != window.trading_start
            or inputs.dividend_actions.coverage_start != window.trading_start
            or inputs.dividend_actions.coverage_end_exclusive != window.end_exclusive):
        raise ValueError("economic case requires exact complete-local-day initialized coverage")
    events = _economic_events_v1(inputs)
    grouped = {}
    calendars = {c.venue_id: c for c in inputs.calendars}
    ranks = {"REGISTER": 150, "ENTITLE": 10, "PAY": 151, "TAX": 152}
    for at, kind, action, _ in events:
        if at.phase.rank != ranks[kind] or at.phase.code != "cn_economic_native" or not _wall_clock_v1(at.instant, 9 if kind == "ENTITLE" else 15, 0):
            raise ValueError("economic action model phase/wall clock mismatch")
        grouped.setdefault((at.instant, at.phase.rank), []).append((at, action))
        if kind in {"REGISTER", "ENTITLE"}:
            local_day = at.instant.to_datetime().astimezone(ZoneInfo("Asia/Shanghai")).date()
            if not any(day.local_date == local_day and day.kind is CnAShareCalendarDayKind.TRADING
                       for day in calendars[action.instrument_id.venue].days):
                raise ValueError("economic registration/entitlement lacks frozen trading day")
    for rows in grouped.values():
        ordered = sorted(rows, key=lambda row: (str(row[1].instrument_id), row[1].action_id))
        if any(at.source_sequence.value != n for n, (at, _) in enumerate(ordered, 1)):
            raise ValueError("economic action source sequence is not its declared ordinal")
    if any(not _wall_clock_v1(b.at.instant, 15, 0) or b.at != _clock_v1(b.at.instant, 160) for b in inputs.daily_marks):
        raise ValueError("economic daily marks require exact close160 clock")
    times = {t.opening_at for t in inputs.opening_terms} if opening_times is None else set(opening_times)
    expected = {_clock_v1(when, rank) for when in times for rank in (49, 55, 67, 97)}
    expected.update(_clock_v1(b.at.instant, 45) for b in inputs.signal_marks)
    for at, _, _, _ in events:
        if at.instant < window.end_exclusive:
            expected.add(at)
            expected.add(d.SimulationInstant(at.instant, at.phase, d.SourceSequence(at.source_sequence.value - 1)))
    final_at = _clock_v1(window.end_exclusive, 200)
    expected.add(final_at)
    if ((opening_times is None and not expected <= {b.at for b in inputs.checkpoint_marks})
            or (opening_times is not None and {b.at for b in inputs.checkpoint_marks} != expected)):
        raise ValueError("economic checkpoint marks do not exact-cover required coordinates")
    final = next(b for b in inputs.checkpoint_marks if b.at == final_at)
    last = inputs.daily_marks[-1]
    for closing, mark in zip(last.marks, final.marks, strict=True):
        if (mark.instrument_id != closing.instrument_id or mark.price != closing.price
                or mark.observed_at != closing.observed_at or mark.available_at != closing.available_at
                or mark.available_at_instant != closing.available_at_instant
                or any(getattr(mark, name) != getattr(closing, name) for name in
                    ("stream_id", "source_event_id", "revision_id", "stale_policy_key", "stale_policy_version", "stale_policy_hash"))):
            raise ValueError("economic final marks differ from retained last daily source")


def _read_economic_opening_sources_v1(
    inputs: CnASharePortfolioEconomicDevelopmentInputsV1,
    reader: MarketBundleReader, window: TimelineWindow,
) -> tuple[MarketEvent, ...]:
    _validate_economic_coordinates_v1(inputs, window)
    if (reader.bundle_ref != inputs.scope.market_bundle_ref
            or window.trading_start > inputs.signal_marks[0].at.instant
            or inputs.daily_marks[-1].at.instant >= window.end_exclusive):
        raise ValueError("economic portfolio market/window source binding mismatch")
    streams = tuple(s for s in reader.manifest.streams if s.capability == BAR_OPEN_CAPABILITY)
    # ponytail: one finite opening stream, max4096; a wider source contract needs
    # a new profile version, not silent filtering of unrelated observations.
    if len(streams) != 1 or not 0 < streams[0].event_count <= 4096:
        raise ValueError("economic portfolio needs one finite native opening stream")
    source = streams[0]
    cursor = reader.open_cursor(source.stream_key, batch_size=64)
    if (type(cursor) is not EventCursor or cursor.bundle_ref != reader.bundle_ref
            or cursor.stream_manifest != source or cursor.position != 0):
        raise ValueError("economic portfolio opening cursor identity mismatch")
    events = []
    while not cursor.exhausted:
        batch, advanced = reader.read_batch(cursor)
        if (type(batch) is not tuple or not batch or any(type(e) is not MarketEvent for e in batch)
                or type(advanced) is not EventCursor or advanced.bundle_ref != cursor.bundle_ref
                or advanced.stream_manifest != source or advanced.position != cursor.position + len(batch)):
            raise ValueError("economic portfolio opening cursor did not advance exactly")
        events.extend(batch)
        cursor = advanced
    if len(events) != source.event_count or canonical_sha256(events) != source.content_hash:
        raise ValueError("economic portfolio retained opening stream hash mismatch")
    scope = set(inputs.scope.instrument_ids)
    if any(e.stream_key != source.stream_key or e.capability != BAR_OPEN_CAPABILITY
           or e.event_type != "bar_open" or e.instrument_id not in scope
           or e.event_time != e.available_time
           or not window.trading_start <= e.event_time < window.end_exclusive for e in events):
        raise ValueError("economic portfolio opening event scope/availability/window mismatch")
    if len({e.event_id for e in events}) != len(events):
        raise ValueError("economic portfolio opening event identity is duplicated")
    by_time = {e.event_time for e in events}
    if any(len(tuple(e for e in events if e.event_time == when)) != len(scope)
           or {e.instrument_id for e in events if e.event_time == when} != scope for when in by_time):
        raise ValueError("economic portfolio opening instants require exact instrument cover")
    zone = ZoneInfo("Asia/Shanghai")
    day_of = lambda instant: instant.to_datetime().astimezone(zone).date()
    first_day, end_day = day_of(window.trading_start), day_of(window.end_exclusive)
    calendars = inputs.calendars
    if any(c.coverage_start > first_day or c.coverage_end_exclusive < end_day for c in calendars):
        raise ValueError("economic portfolio frozen calendar does not cover the native window")
    trading_days = tuple(tuple(d.local_date for d in c.days
        if first_day <= d.local_date < end_day and d.kind is CnAShareCalendarDayKind.TRADING)
        for c in calendars)
    daily_days = tuple(day_of(b.at.instant) for b in inputs.daily_marks)
    if (trading_days[0] != trading_days[1] or daily_days != trading_days[0]
            or {day_of(e.event_time) for e in events} != set(daily_days)
            or len(by_time) != len(daily_days)):
        raise ValueError("economic portfolio calendar/opening/daily mark exact-cover mismatch")
    daily = dict(zip(daily_days, inputs.daily_marks, strict=True))
    if any(daily[day_of(e.event_time)].at <= type(daily[day_of(e.event_time)].at)(
            e.event_time, e.phase, e.source_sequence) for e in events):
        raise ValueError("economic portfolio daily valuation must follow the exact raw opening clock")
    expected = {}
    for event in events:
        observation = BarOpenObservation.from_event(event)
        if observation.kind is BarOpenKind.REAL:
            for side in (OrderSide.BUY, OrderSide.SELL):
                expected[(event.event_id, side)] = event
    terms = {(t.bar_event_id, t.side): t for t in inputs.opening_terms}
    if set(terms) != set(expected):
        raise ValueError("economic portfolio real openings need exact BUY/SELL source terms")
    for key, event in expected.items():
        term = terms[key]
        observation = BarOpenObservation.from_event(event)
        if (term.bar_event_hash != event.event_hash or term.instrument_id != event.instrument_id
                or term.opening_at != event.event_time or term.notional_evidence.price != observation.open_price
                or term.notional_evidence.available_at != event.available_time
                or term.liquidity.evaluated_at != event.available_time
                or term.market_state.observed_at > event.event_time
                or term.market_state.revision_id != event.revision_id):
            raise ValueError("economic portfolio opening rule/fee/price source substitution")
    if any(not _wall_clock_v1(e.event_time, 9, 30) or e.phase.rank >= 30 for e in events):
        raise ValueError("economic raw openings require09:30 and source phase below30")
    _validate_economic_coordinates_v1(inputs, window, opening_times=by_time)
    return tuple(events)

_ORDER_STAGES = ("intent", "capability", "translation", "market", "fee", "risk",
                 "submitted", "accepted", "activated", "filled", "expired", "rejected")


def _economic_identity_plan_v1(
    inputs: CnASharePortfolioEconomicDevelopmentInputsV1,
    targets: PrecomputedTargetStream, openings: tuple[MarketEvent, ...],
) -> tuple[ExecutionCaseIdentityRule, ...]:
    """Reserve source/branch coordinates even when a branch produces no Order."""
    rows: list[tuple[str, DomainIdKind | None]] = []
    for signal_index, _ in enumerate(targets.events):
        for instrument in inputs.scope.instrument_ids:
            root = f"signal.{signal_index}.{instrument}"
            rows.append((root + ".order", DomainIdKind.ORDER))
            for opening_index, event in enumerate(openings):
                if event.instrument_id == instrument:
                    rows.extend((f"{root}.open.{opening_index}.{stage}", None) for stage in _ORDER_STAGES)
            for next_signal in range(signal_index + 1, len(targets.events)):
                rows.extend((f"{root}.signal.{next_signal}.{stage}", None)
                    for stage in ("cancel_requested", "cancelled"))
    for index, action in enumerate(inputs.dividend_actions.actions):
        rows.append((f"dividend.{index}.pay.journal", DomainIdKind.JOURNAL))
        if action.tax_policy.mode == "FIXED_RATIO":
            rows.append((f"dividend.{index}.tax.journal", DomainIdKind.JOURNAL))
    rules = tuple(ExecutionCaseIdentityRule(key, "cn.portfolio.economic." + key, index, kind)
                  for index, (key, kind) in enumerate(rows))
    return tuple(sorted(rules, key=lambda rule: rule.binding_key))


@dataclass(frozen=True, slots=True)
class _BoundEconomicPortfolioSourcesV1:
    inputs: CnASharePortfolioEconomicDevelopmentInputsV1
    openings: tuple[MarketEvent, ...]
    journal_entry_ids: tuple[tuple[str, d.DomainId], ...]


def _economic_journal_entry_ids_v1(case, inputs):
    if (type(case) is not _ResolvedProfilePortfolioCaseV2 or case.semantic_spec is None or case.identity_manifest is None
            or not case.verify_identity_manifest(case.identity_manifest.semantic_run_id)
            or case.execution_case_plan.definition != inputs.definition()):
        raise ValueError("economic journal mapping requires exact sealed source-bound case")
    openings = _read_economic_opening_sources_v1(inputs, case.timeline.reader, case.timeline.window)
    if case.semantic_spec.identity_plan != _economic_identity_plan_v1(inputs, case.target_stream, openings):
        raise ValueError("economic identity plan differs from full source coordinate plan")
    events = _economic_events_v1(inputs)
    result = []
    for index, action in enumerate(inputs.dividend_actions.actions):
        for at, kind, owner, event_id in events:
            if owner == action and kind in {"PAY", "TAX"}:
                result.append((event_id, case.domain_id(f"dividend.{index}.{kind.lower()}.journal")))
    return tuple(sorted(result))


def _read_exact_economic_source_v1(reader, ref):
    retained = reader.read(ref=ref)
    if (type(retained) is not ArtifactReadResult or ArtifactRef.from_envelope(retained.envelope) != ref
            or retained.source_bytes != canonical_bytes(retained.envelope)
            or retained.source_hash != canonical_sha256(retained.envelope)):
        raise ValueError("economic retained ref/raw bytes/source hash mismatch")
    return retained.envelope


def _bind_economic_portfolio_sources_v1(case, reader):
    if type(case) is not _ResolvedProfilePortfolioCaseV2:
        raise TypeError("economic source binding requires exact CaseV2")
    refs = dict(case.execution_case_plan.source_refs)
    retained = _read_exact_economic_source_v1(reader, refs["definition"])
    if retained != case.execution_case_plan.definition:
        raise ValueError("economic retained definition differs from case")
    action_envelope = _read_exact_economic_source_v1(reader, refs["cash_dividend_action_set"])
    actions = _read_cn_a_share_cash_dividend_action_set_v1(action_envelope.payload)
    for action in actions.actions:
        for ref in action.source_evidence_refs:
            _read_exact_economic_source_v1(reader, ref)
    target_ref = BacktestTargetStreamRef.from_artifact_ref(refs["target_stream"])
    verified = BacktestTargetStreamRepository(reader=reader).load(target_ref)
    if canonical_bytes(verified.target_stream) != canonical_bytes(case.target_stream):
        raise ValueError("economic retained target differs from case")
    inputs = _read_economic_definition_v1(retained, target_ref, actions)
    if inputs.scope.market_bundle_ref != case.timeline.reader.bundle_ref:
        raise ValueError("economic market Bundle source binding mismatch")
    expected_signal = tuple(d.SimulationInstant(e.event_time, e.phase, e.source_sequence) for e in case.target_stream.events)
    if tuple(b.at for b in inputs.signal_marks) != expected_signal or any(
            not _wall_clock_v1(e.event_time, 15, 0) or e.phase.rank >= 30 or e.event_time != e.available_time
            for e in case.target_stream.events):
        raise ValueError("economic target/signal source full-clock mismatch")
    actual = (case.financial_state, case.execution_case_plan.initial_dividend_state, case.execution_case_plan.initial_economic_projection)
    if canonical_bytes(actual) != canonical_bytes(_native_initial_economic_financial_state_v1(inputs)):
        raise ValueError("economic initial native triple differs from retained source")
    openings = _read_economic_opening_sources_v1(inputs, case.timeline.reader, case.timeline.window)
    mapping = _economic_journal_entry_ids_v1(case, inputs)
    return _BoundEconomicPortfolioSourcesV1(inputs, openings, mapping)
