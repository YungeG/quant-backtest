"""Private source/coordinate binding for the standard CN portfolio profile.

Source refs are independently read transport bytes, not economic identity.
Coordinates reserve possible Order events, never future quantities or Fills.
"""
from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from crypto_quant_domain import (
    ArtifactReadResult, ArtifactRef, CashBalanceKey, DomainIdKind, OrderSide,
    PositionBalanceKey, canonical_bytes, canonical_sha256,
)
from crypto_quant_market_data import EventCursor, MarketBundleReader, MarketEvent
from crypto_quant_trading import (
    CashAvailabilityRule, CashReservationUse, MarketSettlementRules, PositionAvailabilityRule,
    SettlementBook,
)

from crypto_quant_trading.profiles.cn_a_share import CnAShareCalendarDayKind

from .artifact_envelope_reader import ArtifactEnvelopeReader
from .cn_a_share_portfolio_standard_definition_v1 import (
    CnASharePortfolioStandardDevelopmentInputsV1, _read_standard_definition_v1,
)
from .cn_a_share_portfolio_standard_native_state_v1 import _native_snapshot_at_v1
from .engine import ExecutionCaseIdentityRule, PositionLotBook, ResolvedFinancialState
from .execution import BAR_OPEN_CAPABILITY, BarOpenKind, BarOpenObservation
from .profile_portfolio_execution import _ResolvedProfilePortfolioCaseV1
from .target_repository import BacktestTargetStreamRef, BacktestTargetStreamRepository
from .target_stream import PrecomputedTargetStream
from .timeline import TimelineWindow


# The registry/profile freezes this policy; capital/transfers are model facts,
# not a broker shared account or qualification for historical source availability.
def _native_initial_financial_state_v1(
    inputs: CnASharePortfolioStandardDevelopmentInputsV1,
) -> ResolvedFinancialState:
    scope = inputs.scope
    cash = tuple(r.key for r in scope.ledger_schema.cash_registrations if type(r.key) is CashBalanceKey)
    positions = tuple(r.key for r in scope.ledger_schema.registrations if type(r.key) is PositionBalanceKey)
    rules = MarketSettlementRules.create(
        policy_key="cn.portfolio.standard.settled-only.development", policy_version=1,
        account_id=scope.account_id,
        cash_rules=tuple(CashAvailabilityRule(key, False, False, False,
            (CashReservationUse.CASH, CashReservationUse.FEE_RESERVE),
            (CashReservationUse.CASH, CashReservationUse.FEE_RESERVE), ()) for key in cash),
        position_rules=tuple(PositionAvailabilityRule(key, False) for key in positions))
    return ResolvedFinancialState(inputs.initial_journal, scope.ledger_schema,
        _native_snapshot_at_v1(inputs, inputs.initial_journal, inputs.signal_marks[0]),
        tuple(PositionLotBook(key) for key in positions), (), (), (), SettlementBook(scope.account_id), rules)


def _read_opening_sources_v1(
    inputs: CnASharePortfolioStandardDevelopmentInputsV1,
    reader: MarketBundleReader, window: TimelineWindow,
) -> tuple[MarketEvent, ...]:
    if (reader.bundle_ref != inputs.scope.market_bundle_ref
            or window.trading_start > inputs.signal_marks[0].at.instant
            or inputs.daily_marks[-1].at.instant >= window.end_exclusive):
        raise ValueError("standard portfolio market/window source binding mismatch")
    streams = tuple(s for s in reader.manifest.streams if s.capability == BAR_OPEN_CAPABILITY)
    # ponytail: one finite opening stream, max4096; a wider source contract needs
    # a new profile version, not silent filtering of unrelated observations.
    if len(streams) != 1 or not 0 < streams[0].event_count <= 4096:
        raise ValueError("standard portfolio needs one finite native opening stream")
    source = streams[0]
    cursor = reader.open_cursor(source.stream_key, batch_size=64)
    if (type(cursor) is not EventCursor or cursor.bundle_ref != reader.bundle_ref
            or cursor.stream_manifest != source or cursor.position != 0):
        raise ValueError("standard portfolio opening cursor identity mismatch")
    events = []
    while not cursor.exhausted:
        batch, advanced = reader.read_batch(cursor)
        if (type(batch) is not tuple or not batch or any(type(e) is not MarketEvent for e in batch)
                or type(advanced) is not EventCursor or advanced.bundle_ref != cursor.bundle_ref
                or advanced.stream_manifest != source or advanced.position != cursor.position + len(batch)):
            raise ValueError("standard portfolio opening cursor did not advance exactly")
        events.extend(batch)
        cursor = advanced
    if len(events) != source.event_count or canonical_sha256(events) != source.content_hash:
        raise ValueError("standard portfolio retained opening stream hash mismatch")
    scope = set(inputs.scope.instrument_ids)
    if any(e.stream_key != source.stream_key or e.capability != BAR_OPEN_CAPABILITY
           or e.event_type != "bar_open" or e.instrument_id not in scope
           or e.event_time != e.available_time
           or not window.trading_start <= e.event_time < window.end_exclusive for e in events):
        raise ValueError("standard portfolio opening event scope/availability/window mismatch")
    if len({e.event_id for e in events}) != len(events):
        raise ValueError("standard portfolio opening event identity is duplicated")
    by_time = {e.event_time for e in events}
    if any(len(tuple(e for e in events if e.event_time == when)) != len(scope)
           or {e.instrument_id for e in events if e.event_time == when} != scope for when in by_time):
        raise ValueError("standard portfolio opening instants require exact instrument cover")
    zone = ZoneInfo("Asia/Shanghai")
    day_of = lambda instant: instant.to_datetime().astimezone(zone).date()
    first_day, end_day = min(day_of(e.event_time) for e in events), day_of(window.end_exclusive)
    calendars = inputs.calendars
    if any(c.coverage_start > first_day or c.coverage_end_exclusive < end_day for c in calendars):
        raise ValueError("standard portfolio frozen calendar does not cover the native window")
    trading_days = tuple(tuple(d.local_date for d in c.days
        if first_day <= d.local_date < end_day and d.kind is CnAShareCalendarDayKind.TRADING)
        for c in calendars)
    daily_days = tuple(day_of(b.at.instant) for b in inputs.daily_marks)
    if (trading_days[0] != trading_days[1] or daily_days != trading_days[0]
            or {day_of(e.event_time) for e in events} != set(daily_days)
            or len(by_time) != len(daily_days)):
        raise ValueError("standard portfolio calendar/opening/daily mark exact-cover mismatch")
    daily = dict(zip(daily_days, inputs.daily_marks, strict=True))
    if any(daily[day_of(e.event_time)].at <= type(daily[day_of(e.event_time)].at)(
            e.event_time, e.phase, e.source_sequence) for e in events):
        raise ValueError("standard portfolio daily valuation must follow the exact raw opening clock")
    expected = {}
    for event in events:
        observation = BarOpenObservation.from_event(event)
        if observation.kind is BarOpenKind.REAL:
            for side in (OrderSide.BUY, OrderSide.SELL):
                expected[(event.event_id, side)] = event
    terms = {(t.bar_event_id, t.side): t for t in inputs.opening_terms}
    if set(terms) != set(expected):
        raise ValueError("standard portfolio real openings need exact BUY/SELL source terms")
    for key, event in expected.items():
        term = terms[key]
        observation = BarOpenObservation.from_event(event)
        if (term.bar_event_hash != event.event_hash or term.instrument_id != event.instrument_id
                or term.opening_at != event.event_time or term.notional_evidence.price != observation.open_price
                or term.notional_evidence.available_at != event.available_time
                or term.liquidity.evaluated_at != event.available_time
                or term.market_state.observed_at > event.event_time
                or term.market_state.revision_id != event.revision_id):
            raise ValueError("standard portfolio opening rule/fee/price source substitution")
    return tuple(events)


_ORDER_STAGES = ("intent", "capability", "translation", "market", "fee", "risk",
                 "submitted", "accepted", "activated", "filled", "expired", "rejected")


def _standard_identity_plan_v1(
    inputs: CnASharePortfolioStandardDevelopmentInputsV1,
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
    rules = tuple(ExecutionCaseIdentityRule(key, "cn.portfolio.standard." + key, index, kind)
                  for index, (key, kind) in enumerate(rows))
    return tuple(sorted(rules, key=lambda rule: rule.binding_key))


@dataclass(frozen=True, slots=True)
class _BoundStandardPortfolioSourcesV1:
    inputs: CnASharePortfolioStandardDevelopmentInputsV1
    openings: tuple[MarketEvent, ...]


def _bind_standard_portfolio_sources_v1(
    case: _ResolvedProfilePortfolioCaseV1, reader: ArtifactEnvelopeReader,
) -> _BoundStandardPortfolioSourcesV1:
    refs = dict(case.execution_case_plan.source_refs)
    if set(refs) != {"definition", "target_stream"}:
        raise ValueError("standard portfolio needs exact independently retained definition/target refs")
    retained = reader.read(ref=refs["definition"])
    if (type(retained) is not ArtifactReadResult
            or ArtifactRef.from_envelope(retained.envelope) != refs["definition"]
            or retained.source_bytes != canonical_bytes(retained.envelope)
            or retained.source_hash != canonical_sha256(retained.envelope)
            or retained.envelope != case.execution_case_plan.definition):
        raise ValueError("standard portfolio retained whole definition source mismatch")
    target_ref = BacktestTargetStreamRef.from_artifact_ref(refs["target_stream"])
    verified = BacktestTargetStreamRepository(reader=reader).load(target_ref)
    if (verified.target_stream.target_stream_digest != case.target_stream.target_stream_digest
            or canonical_bytes(verified.target_stream) != canonical_bytes(case.target_stream)):
        raise ValueError("standard portfolio retained target economic projection mismatch")
    inputs = _read_standard_definition_v1(retained.envelope, target_ref)
    if (inputs.scope.market_bundle_ref != case.timeline.reader.bundle_ref
            or inputs.signal_marks[0].at.instant < case.timeline.window.trading_start
            or tuple(b.at for b in inputs.signal_marks) != tuple(
                type(b.at)(e.event_time, e.phase, e.source_sequence)
                for e, b in zip(case.target_stream.events, inputs.signal_marks, strict=True))):
        raise ValueError("standard portfolio target/signal/full-clock source mismatch")
    if canonical_bytes(_native_initial_financial_state_v1(inputs)) != canonical_bytes(case.financial_state):
        raise ValueError("standard portfolio native initial state differs from frozen source projection")
    openings = _read_opening_sources_v1(inputs, case.timeline.reader, case.timeline.window)
    if (case.semantic_spec is None or case.identity_manifest is None
            or not case.verify_identity_manifest(case.identity_manifest.semantic_run_id)
            or case.semantic_spec.identity_plan != _standard_identity_plan_v1(inputs, case.target_stream, openings)):
        raise ValueError("standard portfolio finite native identity coordinate plan mismatch")
    return _BoundStandardPortfolioSourcesV1(inputs, openings)
