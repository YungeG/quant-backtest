from __future__ import annotations

from dataclasses import replace
from datetime import date

from crypto_quant_domain import (
    CurrencyId,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    OrderSide,
    Price,
    Rate,
    Scale,
    TradingDate,
    UtcInstant,
    VenueId,
)
from crypto_quant_trading import MarketSessionState
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareBoard,
    CnAShareCalendarDayKind,
    CnAShareCashOrderRuleModel,
    CnAShareCashQuantityLatticeModel,
    CnAShareCashSessionModel,
    CnAShareFrozenCalendar,
    CnAShareFrozenCalendarDay,
    CnAShareInstrumentRuleContext,
    CnAShareBarLimitLiquidityEvaluator,
    CnAShareLimitLiquidityDecisionCode,
    CnAShareLimitLiquidityInput,
    CnAShareListingPhase,
    CnAShareOrderRuleBand,
    CnAShareOrderRuleBook,
    CnAShareOrderRuleFailureCode,
    CnAShareOpenObservationState,
    CnAShareOrderRuleQuery,
    CnAShareOrderRuleResolutionKind,
    CnASharePreviousCloseEvidence,
    CnAShareQuantityLatticeQuery,
    CnAShareRiskClass,
    CnAShareRuleSourceRef,
    CnAShareTradeStatus,
    CnAShareTradeStatusEvidence,
)
from tests.kernel.profiles.cn_a_share._fixtures import frozen_calendar, local_query


CNY = CurrencyId("CNY")
PRICE_SCALE = Scale(2)
QUANTITY_SCALE = Scale(0)


def _instrument(venue: str, stable_key: str) -> InstrumentDefinition:
    venue_id = VenueId(venue)
    return InstrumentDefinition(
        instrument_id=InstrumentId(venue_id, stable_key),
        instrument_type=InstrumentType.EQUITY,
        base_currency=None,
        quote_currency=CNY,
        settlement_currency=CNY,
    )


def _main_band(venue: str) -> CnAShareOrderRuleBand:
    return CnAShareOrderRuleBand(
        venue_id=VenueId(venue),
        board=CnAShareBoard.MAIN,
        effective_from=date(2023, 4, 10),
        effective_to_exclusive=date(2025, 1, 1),
        daily_price_limit_ratio=Rate(1_000, Scale(4), "fraction"),
        price_tick_units=1,
        max_limit_order_quantity_units=1_000_000,
        max_market_order_quantity_units=1_000_000,
        quantity_step_units=1,
        buy_lot_units=100,
        sell_lot_units=100,
        min_quantity_units=0,
        odd_lot_close_permitted=True,
        whole_sell_residual_permitted=True,
        source_ref=CnAShareRuleSourceRef(
            source_key="sse-trading-rules-2023" if venue == "xshg" else "szse-trading-rules-2023",
            source_hash="sha256:" + ("1" if venue == "xshg" else "2") * 64,
        ),
    )


def test_main_board_rule_resolution_binds_g08c_lattice_and_price_limits() -> None:
    instrument = _instrument("xshg", "600000")
    session_model = CnAShareCashSessionModel(frozen_calendar("xshg"))
    session_outcome = session_model.resolve_session(
        local_query(date(2024, 2, 8), 10, 0, venue="xshg")
    )
    assert session_outcome.result is not None
    session = session_outcome.result
    assert session.session_id is not None
    assert session.trading_date is not None
    assert session.phase_start is not None
    assert session.phase_end_exclusive is not None

    status = CnAShareTradeStatusEvidence(
        instrument_id=instrument.instrument_id,
        session_id=session.session_id,
        status=CnAShareTradeStatus.NORMAL,
        effective_from=session.phase_start,
        effective_to_exclusive=session.phase_end_exclusive,
        source_hash="sha256:" + "3" * 64,
    )
    previous_close = CnASharePreviousCloseEvidence(
        instrument_id=instrument.instrument_id,
        reference_trading_date=TradingDate("CN.XSHG", date(2024, 2, 7)),
        price=Price(1_000, PRICE_SCALE, str(instrument.instrument_id), "CNY"),
        available_at=session.instant,
        source_hash="sha256:" + "4" * 64,
    )
    model = CnAShareCashOrderRuleModel(
        CnAShareOrderRuleBook(
            rule_book_key="cn-a-share-order-rules-fixture-v1",
            rule_book_version=1,
            bands=(_main_band("xshg"),),
        ),
        notional_scale=PRICE_SCALE,
    )
    outcome = model.resolve_order_rules(
        CnAShareOrderRuleQuery(
            instrument=instrument,
            evaluated_at=session.instant,
            session=session,
            context=CnAShareInstrumentRuleContext(
                board=CnAShareBoard.MAIN,
                risk_class=CnAShareRiskClass.STANDARD,
                listing_phase=CnAShareListingPhase.SEASONED,
                source_key="instrument-classification-fixture",
                source_hash="sha256:" + "5" * 64,
            ),
            trade_status_evidence=status,
            previous_close_evidence=previous_close,
        )
    )

    assert outcome.result is not None
    resolution = outcome.result
    assert resolution.timeline is not None
    active = resolution.timeline.active_intervals(session.instant)
    assert len(active) == 1
    snapshot = active[0].snapshot
    assert snapshot.lower_price_limit is not None
    assert snapshot.upper_price_limit is not None
    assert snapshot.lower_price_limit.units == 900
    assert snapshot.upper_price_limit.units == 1_100
    assert snapshot.max_limit_order_quantity_units == 1_000_000
    assert snapshot.max_market_order_quantity_units == 1_000_000

    lattice_outcome = CnAShareCashQuantityLatticeModel(
        VenueId("xshg"), PRICE_SCALE
    ).resolve_instrument(CnAShareQuantityLatticeQuery(instrument))
    assert lattice_outcome.result is not None
    assert (
        snapshot.quantity_lattice.lattice_hash
        == lattice_outcome.result.quantity_lattice.lattice_hash
    )

    liquidity = CnAShareBarLimitLiquidityEvaluator().evaluate(
        CnAShareLimitLiquidityInput(
            side=OrderSide.BUY,
            snapshot=snapshot,
            observation_state=CnAShareOpenObservationState.AVAILABLE,
            bar_open=snapshot.upper_price_limit,
        )
    )
    assert (
        liquidity.code
        is CnAShareLimitLiquidityDecisionCode.LIQUIDITY_BLOCKED_AT_LIMIT
    )


def _star_band() -> CnAShareOrderRuleBand:
    return CnAShareOrderRuleBand(
        venue_id=VenueId("xshg"),
        board=CnAShareBoard.STAR,
        effective_from=date(2019, 7, 22),
        effective_to_exclusive=date(2025, 1, 1),
        daily_price_limit_ratio=Rate(2_000, Scale(4), "fraction"),
        price_tick_units=1,
        max_limit_order_quantity_units=100_000,
        max_market_order_quantity_units=50_000,
        quantity_step_units=1,
        buy_lot_units=1,
        sell_lot_units=1,
        min_quantity_units=200,
        odd_lot_close_permitted=True,
        whole_sell_residual_permitted=False,
        source_ref=CnAShareRuleSourceRef(
            source_key="sse-star-rules-fixture",
            source_hash="sha256:" + "e" * 64,
        ),
    )


def _chinext_band(start: date, stop: date, ratio_units: int) -> CnAShareOrderRuleBand:
    modern = start >= date(2020, 8, 24)
    return CnAShareOrderRuleBand(
        venue_id=VenueId("xshe"),
        board=CnAShareBoard.CHINEXT,
        effective_from=start,
        effective_to_exclusive=stop,
        daily_price_limit_ratio=Rate(ratio_units, Scale(4), "fraction"),
        price_tick_units=1,
        max_limit_order_quantity_units=300_000 if modern else 1_000_000,
        max_market_order_quantity_units=150_000 if modern else 1_000_000,
        quantity_step_units=1,
        buy_lot_units=100,
        sell_lot_units=100,
        min_quantity_units=0,
        odd_lot_close_permitted=True,
        whole_sell_residual_permitted=True,
        source_ref=CnAShareRuleSourceRef(
            source_key="szse-chinext-transition-fixture",
            source_hash="sha256:" + ("6" if modern else "7") * 64,
        ),
    )


def _historical_calendar() -> CnAShareFrozenCalendar:
    days = tuple(
        CnAShareFrozenCalendarDay(
            value,
            CnAShareCalendarDayKind.WEEKEND
            if value in {date(2020, 8, 22), date(2020, 8, 23)}
            else CnAShareCalendarDayKind.TRADING,
        )
        for value in (
            date(2020, 8, 20),
            date(2020, 8, 21),
            date(2020, 8, 22),
            date(2020, 8, 23),
            date(2020, 8, 24),
            date(2020, 8, 25),
        )
    )
    return CnAShareFrozenCalendar(
        venue_id=VenueId("xshe"),
        calendar_id="CN.XSHE",
        coverage_start=date(2020, 8, 20),
        coverage_end_exclusive=date(2020, 8, 26),
        days=tuple(reversed(days)),
    )


def _resolve_chinext(
    model: CnAShareCashOrderRuleModel,
    instrument: InstrumentDefinition,
    local_date: date,
):
    session_outcome = CnAShareCashSessionModel(
        _historical_calendar()
    ).resolve_session(local_query(local_date, 10, 0, venue="xshe"))
    assert session_outcome.result is not None
    session = session_outcome.result
    assert session.session_id is not None
    assert session.trading_date is not None
    assert session.phase_start is not None
    assert session.phase_end_exclusive is not None
    return model.resolve_order_rules(
        CnAShareOrderRuleQuery(
            instrument=instrument,
            evaluated_at=session.instant,
            session=session,
            context=CnAShareInstrumentRuleContext(
                board=CnAShareBoard.CHINEXT,
                risk_class=CnAShareRiskClass.STANDARD,
                listing_phase=CnAShareListingPhase.SEASONED,
                source_key="chinext-classification-fixture",
                source_hash="sha256:" + "8" * 64,
            ),
            trade_status_evidence=CnAShareTradeStatusEvidence(
                instrument_id=instrument.instrument_id,
                session_id=session.session_id,
                status=CnAShareTradeStatus.NORMAL,
                effective_from=session.phase_start,
                effective_to_exclusive=session.phase_end_exclusive,
                source_hash="sha256:" + "9" * 64,
            ),
            previous_close_evidence=CnASharePreviousCloseEvidence(
                instrument_id=instrument.instrument_id,
                reference_trading_date=TradingDate(
                    "CN.XSHE", date.fromordinal(local_date.toordinal() - 1)
                ),
                price=Price(1_000, PRICE_SCALE, str(instrument.instrument_id), "CNY"),
                available_at=session.instant,
                source_hash="sha256:" + "a" * 64,
            ),
        )
    )


def test_chinext_historical_transition_changes_ratio_and_order_caps() -> None:
    instrument = _instrument("xshe", "300001")
    model = CnAShareCashOrderRuleModel(
        CnAShareOrderRuleBook(
            rule_book_key="chinext-transition-v1",
            rule_book_version=1,
            bands=(
                _chinext_band(date(2020, 8, 20), date(2020, 8, 24), 1_000),
                _chinext_band(date(2020, 8, 24), date(2020, 8, 26), 2_000),
            ),
        ),
        notional_scale=PRICE_SCALE,
    )

    before = _resolve_chinext(model, instrument, date(2020, 8, 21))
    after = _resolve_chinext(model, instrument, date(2020, 8, 24))
    assert before.result is not None
    assert after.result is not None
    assert before.result.timeline is not None
    assert after.result.timeline is not None
    before_snapshot = before.result.timeline.intervals[0].snapshot
    after_snapshot = after.result.timeline.intervals[0].snapshot

    assert before_snapshot.lower_price_limit is not None
    assert before_snapshot.upper_price_limit is not None
    assert after_snapshot.lower_price_limit is not None
    assert after_snapshot.upper_price_limit is not None
    assert [
        before_snapshot.lower_price_limit.units,
        before_snapshot.upper_price_limit.units,
    ] == [900, 1_100]
    assert [
        after_snapshot.lower_price_limit.units,
        after_snapshot.upper_price_limit.units,
    ] == [800, 1_200]
    assert before_snapshot.max_limit_order_quantity_units == 1_000_000
    assert before_snapshot.max_market_order_quantity_units == 1_000_000
    assert after_snapshot.max_limit_order_quantity_units == 300_000
    assert after_snapshot.max_market_order_quantity_units == 150_000


def _main_case(
    *,
    local_date: date,
    status: CnAShareTradeStatus | None,
    include_previous_close: bool,
    previous_close_units: int = 1_000,
    hour: int = 10,
):
    instrument = _instrument("xshg", "600000")
    session_outcome = CnAShareCashSessionModel(frozen_calendar("xshg")).resolve_session(
        local_query(local_date, hour, 0, venue="xshg")
    )
    assert session_outcome.result is not None
    session = session_outcome.result
    status_evidence = None
    previous_close = None
    if session.session_id is not None:
        assert session.phase_start is not None
        assert session.phase_end_exclusive is not None
        if status is not None:
            status_evidence = CnAShareTradeStatusEvidence(
                instrument_id=instrument.instrument_id,
                session_id=session.session_id,
                status=status,
                effective_from=session.phase_start,
                effective_to_exclusive=session.phase_end_exclusive,
                source_hash="sha256:" + "b" * 64,
            )
        if include_previous_close:
            previous_close = CnASharePreviousCloseEvidence(
                instrument_id=instrument.instrument_id,
                reference_trading_date=TradingDate("CN.XSHG", date(2024, 2, 7)),
                price=Price(
                    previous_close_units,
                    PRICE_SCALE,
                    str(instrument.instrument_id),
                    "CNY",
                ),
                available_at=session.instant,
                source_hash="sha256:" + "c" * 64,
            )
    model = CnAShareCashOrderRuleModel(
        CnAShareOrderRuleBook(
            rule_book_key="main-status-fixture-v1",
            rule_book_version=1,
            bands=(_main_band("xshg"),),
        ),
        notional_scale=PRICE_SCALE,
    )
    query = CnAShareOrderRuleQuery(
        instrument=instrument,
        evaluated_at=session.instant,
        session=session,
        context=CnAShareInstrumentRuleContext(
            board=CnAShareBoard.MAIN,
            risk_class=CnAShareRiskClass.STANDARD,
            listing_phase=CnAShareListingPhase.SEASONED,
            source_key="main-classification-fixture",
            source_hash="sha256:" + "d" * 64,
        ),
        trade_status_evidence=status_evidence,
        previous_close_evidence=previous_close,
    )
    return model, query


def test_star_uses_step_one_minimum_200_and_board_caps() -> None:
    instrument = _instrument("xshg", "688001")
    session_outcome = CnAShareCashSessionModel(frozen_calendar("xshg")).resolve_session(
        local_query(date(2024, 2, 8), 10, 0, venue="xshg")
    )
    assert session_outcome.result is not None
    session = session_outcome.result
    assert session.session_id is not None
    assert session.phase_start is not None
    assert session.phase_end_exclusive is not None
    model = CnAShareCashOrderRuleModel(
        CnAShareOrderRuleBook(
            rule_book_key="star-fixture-v1",
            rule_book_version=1,
            bands=(_star_band(),),
        ),
        notional_scale=PRICE_SCALE,
    )
    outcome = model.resolve_order_rules(
        CnAShareOrderRuleQuery(
            instrument=instrument,
            evaluated_at=session.instant,
            session=session,
            context=CnAShareInstrumentRuleContext(
                board=CnAShareBoard.STAR,
                risk_class=CnAShareRiskClass.STANDARD,
                listing_phase=CnAShareListingPhase.SEASONED,
                source_key="star-classification-fixture",
                source_hash="sha256:" + "f" * 64,
            ),
            trade_status_evidence=CnAShareTradeStatusEvidence(
                instrument_id=instrument.instrument_id,
                session_id=session.session_id,
                status=CnAShareTradeStatus.NORMAL,
                effective_from=session.phase_start,
                effective_to_exclusive=session.phase_end_exclusive,
                source_hash="sha256:" + "1" * 64,
            ),
            previous_close_evidence=CnASharePreviousCloseEvidence(
                instrument_id=instrument.instrument_id,
                reference_trading_date=TradingDate("CN.XSHG", date(2024, 2, 7)),
                price=Price(1_000, PRICE_SCALE, str(instrument.instrument_id), "CNY"),
                available_at=session.instant,
                source_hash="sha256:" + "2" * 64,
            ),
        )
    )
    assert outcome.result is not None
    assert outcome.result.timeline is not None
    snapshot = outcome.result.timeline.intervals[0].snapshot
    assert snapshot.quantity_lattice.step_units == 1
    assert snapshot.quantity_lattice.buy_lot_units == 1
    assert snapshot.quantity_lattice.sell_lot_units == 1
    assert snapshot.quantity_lattice.min_quantity_units == 200
    assert snapshot.max_limit_order_quantity_units == 100_000
    assert snapshot.max_market_order_quantity_units == 50_000


def test_suspension_no_trade_and_missing_data_are_distinct() -> None:
    suspended_model, suspended_query = _main_case(
        local_date=date(2024, 2, 8),
        status=CnAShareTradeStatus.SUSPENDED,
        include_previous_close=True,
    )
    suspended = suspended_model.resolve_order_rules(suspended_query)
    assert suspended.result is not None
    assert suspended.result.timeline is not None
    assert (
        suspended.result.timeline.intervals[0].snapshot.session_state
        is MarketSessionState.SUSPENDED
    )

    no_trade_model, no_trade_query = _main_case(
        local_date=date(2024, 2, 9),
        status=None,
        include_previous_close=False,
    )
    no_trade = no_trade_model.resolve_order_rules(no_trade_query)
    assert no_trade.result is not None
    assert no_trade.result.kind is CnAShareOrderRuleResolutionKind.NO_TRADE
    assert no_trade.result.timeline is None

    missing_model, missing_query = _main_case(
        local_date=date(2024, 2, 8),
        status=None,
        include_previous_close=True,
    )
    missing = missing_model.resolve_order_rules(missing_query)
    assert missing.failure is not None
    assert (
        missing.failure.code
        is CnAShareOrderRuleFailureCode.MISSING_TRADE_STATUS_EVIDENCE
    )


def test_limit_liquidity_is_direction_sensitive_without_volume() -> None:
    model, query = _main_case(
        local_date=date(2024, 2, 8),
        status=CnAShareTradeStatus.NORMAL,
        include_previous_close=True,
    )
    outcome = model.resolve_order_rules(query)
    assert outcome.result is not None
    assert outcome.result.timeline is not None
    snapshot = outcome.result.timeline.intervals[0].snapshot
    assert snapshot.lower_price_limit is not None
    assert snapshot.upper_price_limit is not None
    evaluator = CnAShareBarLimitLiquidityEvaluator()

    cases = (
        (OrderSide.BUY, snapshot.upper_price_limit, CnAShareLimitLiquidityDecisionCode.LIQUIDITY_BLOCKED_AT_LIMIT),
        (OrderSide.SELL, snapshot.lower_price_limit, CnAShareLimitLiquidityDecisionCode.LIQUIDITY_BLOCKED_AT_LIMIT),
        (OrderSide.SELL, snapshot.upper_price_limit, CnAShareLimitLiquidityDecisionCode.CONTINUE),
        (OrderSide.BUY, snapshot.lower_price_limit, CnAShareLimitLiquidityDecisionCode.CONTINUE),
    )
    for side, bar_open, expected in cases:
        decision = evaluator.evaluate(
            CnAShareLimitLiquidityInput(
                side=side,
                snapshot=snapshot,
                observation_state=CnAShareOpenObservationState.AVAILABLE,
                bar_open=bar_open,
            )
        )
        assert decision.code is expected

    no_trade = evaluator.evaluate(
        CnAShareLimitLiquidityInput(
            side=OrderSide.BUY,
            snapshot=snapshot,
            observation_state=CnAShareOpenObservationState.NO_TRADE,
            bar_open=None,
        )
    )
    missing = evaluator.evaluate(
        CnAShareLimitLiquidityInput(
            side=OrderSide.BUY,
            snapshot=snapshot,
            observation_state=CnAShareOpenObservationState.DATA_MISSING,
            bar_open=snapshot.upper_price_limit,
        )
    )
    assert no_trade.code is CnAShareLimitLiquidityDecisionCode.NO_TRADE
    assert missing.code is CnAShareLimitLiquidityDecisionCode.DATA_MISSING
    corrupt_no_trade = evaluator.evaluate(
        CnAShareLimitLiquidityInput(
            side=OrderSide.BUY,
            snapshot=snapshot,
            observation_state=CnAShareOpenObservationState.NO_TRADE,
            bar_open=Price(1_100, PRICE_SCALE, "xshg:other", "CNY"),
        )
    )
    assert corrupt_no_trade.code is CnAShareLimitLiquidityDecisionCode.DATA_MISSING

    suspended_model, suspended_query = _main_case(
        local_date=date(2024, 2, 8),
        status=CnAShareTradeStatus.SUSPENDED,
        include_previous_close=True,
    )
    suspended_outcome = suspended_model.resolve_order_rules(suspended_query)
    assert suspended_outcome.result is not None
    assert suspended_outcome.result.timeline is not None
    suspended_snapshot = suspended_outcome.result.timeline.intervals[0].snapshot
    corrupt = evaluator.evaluate(
        CnAShareLimitLiquidityInput(
            side=OrderSide.BUY,
            snapshot=suspended_snapshot,
            observation_state=CnAShareOpenObservationState.AVAILABLE,
            bar_open=Price(1_100, PRICE_SCALE, "xshg:other", "CNY"),
        )
    )
    assert corrupt.code is CnAShareLimitLiquidityDecisionCode.DATA_MISSING


def test_closed_phase_takes_precedence_over_suspended_status() -> None:
    model, query = _main_case(
        local_date=date(2024, 2, 8),
        status=CnAShareTradeStatus.SUSPENDED,
        include_previous_close=True,
        hour=12,
    )
    outcome = model.resolve_order_rules(query)
    assert outcome.result is not None
    assert outcome.result.timeline is not None
    assert (
        outcome.result.timeline.intervals[0].snapshot.session_state
        is MarketSessionState.CLOSED
    )


def test_trade_status_interval_bounds_the_resolved_rule_interval() -> None:
    model, query = _main_case(
        local_date=date(2024, 2, 8),
        status=CnAShareTradeStatus.NORMAL,
        include_previous_close=True,
    )
    assert query.trade_status_evidence is not None
    narrow_end = UtcInstant(query.evaluated_at.epoch_nanoseconds + 1)
    narrow_status = replace(
        query.trade_status_evidence,
        effective_from=query.evaluated_at,
        effective_to_exclusive=narrow_end,
    )
    outcome = model.resolve_order_rules(
        replace(query, trade_status_evidence=narrow_status)
    )
    assert outcome.result is not None
    assert outcome.result.timeline is not None
    interval = outcome.result.timeline.intervals[0]
    assert interval.effective_from == query.evaluated_at
    assert interval.effective_to_exclusive == narrow_end


def test_half_up_rounding_and_rule_overlap_fail_closed() -> None:
    model, query = _main_case(
        local_date=date(2024, 2, 8),
        status=CnAShareTradeStatus.NORMAL,
        include_previous_close=True,
        previous_close_units=1_005,
    )
    rounded = model.resolve_order_rules(query)
    assert rounded.result is not None
    assert rounded.result.timeline is not None
    rounded_snapshot = rounded.result.timeline.intervals[0].snapshot
    assert rounded_snapshot.lower_price_limit is not None
    assert rounded_snapshot.upper_price_limit is not None
    assert [
        rounded_snapshot.lower_price_limit.units,
        rounded_snapshot.upper_price_limit.units,
    ] == [905, 1_106]

    floor_model, floor_query = _main_case(
        local_date=date(2024, 2, 8),
        status=CnAShareTradeStatus.NORMAL,
        include_previous_close=True,
        previous_close_units=1,
    )
    floor = floor_model.resolve_order_rules(floor_query)
    assert floor.result is not None
    assert floor.result.timeline is not None
    floor_snapshot = floor.result.timeline.intervals[0].snapshot
    assert floor_snapshot.lower_price_limit is not None
    assert floor_snapshot.upper_price_limit is not None
    assert [
        floor_snapshot.lower_price_limit.units,
        floor_snapshot.upper_price_limit.units,
    ] == [1, 2]

    overlap_model = CnAShareCashOrderRuleModel(
        CnAShareOrderRuleBook(
            rule_book_key="overlap-fixture-v1",
            rule_book_version=1,
            bands=(_main_band("xshg"), _main_band("xshg")),
        ),
        notional_scale=PRICE_SCALE,
    )
    overlap = overlap_model.resolve_order_rules(query)
    assert overlap.failure is not None
    assert (
        overlap.failure.code
        is CnAShareOrderRuleFailureCode.OVERLAPPING_RULE_INTERVALS
    )

    unsupported = model.resolve_order_rules(
        replace(
            query,
            context=replace(query.context, risk_class=CnAShareRiskClass.RISK_WARNING),
        )
    )
    assert unsupported.failure is not None
    assert (
        unsupported.failure.code
        is CnAShareOrderRuleFailureCode.UNSUPPORTED_CLASSIFICATION
    )
