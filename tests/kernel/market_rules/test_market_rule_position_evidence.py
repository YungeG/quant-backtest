from __future__ import annotations

from dataclasses import replace

from crypto_quant_domain import (
    CurrencyId,
    ExecutionStyle,
    Money,
    OrderSide,
    PortfolioSnapshot,
    PositionBalance,
    PositionBalanceKey,
    PositionEffect,
    Quantity,
    Scale,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import (
    AvailabilityState,
    MarketRuleDataIntegrityCode,
    MarketRuleEvaluator,
    MarketRuleIssueCode,
    MarketSessionState,
    OrderRulePositionEvidence,
    PositionAvailability,
    QuantityLattice,
    ReservationCommitment,
    OrderEventStream,
    ResourceReservationState,
)
from tests.kernel.capabilities._fixtures import INSTRUMENT, QUANTITY_SCALE
from tests.kernel.market_rules._fixtures import (
    evaluation_input,
    interval,
    limit_intent,
    order_with_intent,
    snapshot,
    timeline,
    translated_spec,
)
from tests.kernel.rebalance._fixtures import (
    reservation_state,
    working_order,
    working_stream,
)


def _issue_codes(decision: object) -> tuple[MarketRuleIssueCode, ...]:
    rejection = getattr(decision, "rejection")
    assert rejection is not None
    return tuple(issue.code for issue in rejection.issues)


def test_execution_style_uses_its_own_single_order_quantity_cap() -> None:
    rule_snapshot = snapshot(
        max_limit_order_quantity_units=1_500,
        max_market_order_quantity_units=2_500,
    )
    market = MarketRuleEvaluator()

    rule_timeline = timeline(intervals=(interval(rule_snapshot=rule_snapshot),))
    market_decision = market.evaluate(evaluation_input(), rule_timeline)
    assert market_decision.approval is not None

    limit_spec = translated_spec(order_with_intent(limit_intent()))
    limit_decision = market.evaluate(
        evaluation_input(spec=limit_spec),
        rule_timeline,
    )
    assert list(_issue_codes(limit_decision)) == [MarketRuleIssueCode.MAXIMUM_QUANTITY]
    assert limit_spec.intent.execution_style is ExecutionStyle.LIMIT


def test_suspension_is_distinct_from_a_closed_session() -> None:
    decision = MarketRuleEvaluator().evaluate(
        evaluation_input(),
        timeline(
            intervals=(
                interval(rule_snapshot=snapshot(session_state=MarketSessionState.SUSPENDED)),
            )
        ),
    )

    assert list(_issue_codes(decision)) == [MarketRuleIssueCode.INSTRUMENT_SUSPENDED]


def _residual_lattice() -> QuantityLattice:
    return QuantityLattice.create(
        instrument_id=INSTRUMENT,
        lattice_key="synthetic.cash.residual.v1",
        lattice_version=1,
        atomic_scale=QUANTITY_SCALE,
        step_units=1,
        buy_lot_units=100,
        sell_lot_units=100,
        min_quantity_units=0,
        min_notional=Money(0, Scale(2), "USD"),
        odd_lot_close_permitted=True,
        whole_sell_residual_permitted=True,
    )


def _position_evidence(
    lattice: QuantityLattice,
    *,
    total_units: int = 299,
    sellable_units: int | None = None,
    lattice_hash: str | None = None,
    account_id: str = "account:primary",
    working_orders: tuple[OrderEventStream, ...] = (),
    reservations: ResourceReservationState | None = None,
) -> OrderRulePositionEvidence:
    evaluated_at = UtcInstant(150)
    position_key = PositionBalanceKey(account_id, INSTRUMENT.venue, INSTRUMENT)
    total = Quantity(total_units, QUANTITY_SCALE, str(INSTRUMENT))
    sellable = Quantity(
        total_units if sellable_units is None else sellable_units,
        QUANTITY_SCALE,
        str(INSTRUMENT),
    )
    journal_hash = "sha256:" + "1" * 64
    if reservations is None:
        reservations = ResourceReservationState(
            account_id=account_id,
            cursors=(),
            active_reservations=(),
            totals=ReservationCommitment.empty(),
        )
    zero = Money(0, Scale(2), "USD")
    portfolio = PortfolioSnapshot(
        account_id=account_id,
        timestamp=evaluated_at,
        reporting_currency=CurrencyId("USD"),
        cash=(),
        positions=(PositionBalance(position_key, total, ()),),
        realized_pnl=zero,
        unrealized_pnl=zero,
        fees=zero,
        financing=zero,
        equity=zero,
        valuation_marks=(),
        journal_state_hash=journal_hash,
        valuation_mark_set_hash=canonical_sha256(()),
        valuation_staleness_report_hash="sha256:" + "2" * 64,
        currency_valuation_graph_hash="sha256:" + "3" * 64,
    )
    availability = AvailabilityState(
        account_id=account_id,
        ledger_state_hash=journal_hash,
        settlement_state_hash="sha256:" + "4" * 64,
        reservation_state_hash=reservations.state_hash,
        market_settlement_rules_hash="sha256:" + "5" * 64,
        cash=(),
        positions=(PositionAvailability(position_key, total, sellable),),
    )
    return OrderRulePositionEvidence(
        account_id=account_id,
        evaluated_at=evaluated_at,
        instrument_id=INSTRUMENT,
        portfolio_snapshot=portfolio,
        working_orders=working_orders,
        working_order_set_hash=canonical_sha256(
            tuple(
                {
                    "order_id": stream.order.order_id,
                    "stream_hash": stream.stream_hash,
                    "state_hash": stream.state_hash,
                    "remaining_quantity": (
                        stream.state.remaining_quantity if stream.state else None
                    ),
                }
                for stream in working_orders
            )
        ),
        reservations=reservations,
        availability=availability,
        total_quantity=total,
        sellable_quantity=sellable,
        quantity_lattice_hash=lattice.lattice_hash if lattice_hash is None else lattice_hash,
    )


def _sell_spec(quantity_units: int):
    return translated_spec(
        order_with_intent(
            replace(
                limit_intent(),
                side=OrderSide.SELL,
                quantity=Quantity(quantity_units, QUANTITY_SCALE, str(INSTRUMENT)),
                reduce_only=True,
                position_effect=PositionEffect.CLOSE,
            )
        )
    )


def test_odd_residual_sell_requires_authoritative_position_evidence() -> None:
    lattice = _residual_lattice()
    spec = _sell_spec(99)
    rule_timeline = timeline(
        intervals=(interval(rule_snapshot=snapshot(quantity_lattice=lattice)),)
    )
    market = MarketRuleEvaluator()

    missing = market.evaluate(evaluation_input(spec=spec), rule_timeline)
    assert missing.data_integrity_failure is not None
    assert (
        missing.data_integrity_failure.code
        is MarketRuleDataIntegrityCode.MISSING_POSITION_EVIDENCE
    )

    approved = market.evaluate(
        evaluation_input(spec=spec, position_evidence=_position_evidence(lattice)),
        rule_timeline,
    )
    assert approved.approval is not None


def test_residual_sell_rejects_split_excess_and_invalid_lattice_evidence() -> None:
    lattice = _residual_lattice()
    rule_timeline = timeline(
        intervals=(interval(rule_snapshot=snapshot(quantity_lattice=lattice)),)
    )
    market = MarketRuleEvaluator()

    split = market.evaluate(
        evaluation_input(
            spec=_sell_spec(1),
            position_evidence=_position_evidence(lattice),
        ),
        rule_timeline,
    )
    assert list(_issue_codes(split)) == [
        MarketRuleIssueCode.SELL_RESIDUAL_NOT_PERMITTED
    ]

    excess = market.evaluate(
        evaluation_input(
            spec=_sell_spec(99),
            position_evidence=_position_evidence(lattice, sellable_units=98),
        ),
        rule_timeline,
    )
    assert list(_issue_codes(excess)) == [MarketRuleIssueCode.SELLABLE_QUANTITY]

    invalid = market.evaluate(
        evaluation_input(
            spec=_sell_spec(99),
            position_evidence=_position_evidence(
                lattice, lattice_hash="sha256:" + "f" * 64
            ),
        ),
        rule_timeline,
    )
    assert invalid.data_integrity_failure is not None
    assert (
        invalid.data_integrity_failure.code
        is MarketRuleDataIntegrityCode.INVALID_POSITION_EVIDENCE
    )


def test_star_step_one_minimum_allows_201_and_authoritative_full_close_199() -> None:
    star_lattice = QuantityLattice.create(
        instrument_id=INSTRUMENT,
        lattice_key="synthetic.cash.star.v1",
        lattice_version=1,
        atomic_scale=QUANTITY_SCALE,
        step_units=1,
        buy_lot_units=1,
        sell_lot_units=1,
        min_quantity_units=200,
        min_notional=Money(0, Scale(2), "USD"),
        odd_lot_close_permitted=True,
    )
    rule_timeline = timeline(
        intervals=(interval(rule_snapshot=snapshot(quantity_lattice=star_lattice)),)
    )
    market = MarketRuleEvaluator()

    regular = market.evaluate(evaluation_input(spec=_sell_spec(201)), rule_timeline)
    assert regular.approval is not None

    close = market.evaluate(
        evaluation_input(
            spec=_sell_spec(199),
            position_evidence=_position_evidence(
                star_lattice, total_units=199, sellable_units=199
            ),
        ),
        rule_timeline,
    )
    assert close.approval is not None


def test_cross_account_position_evidence_fails_closed() -> None:
    lattice = _residual_lattice()
    decision = MarketRuleEvaluator().evaluate(
        evaluation_input(
            spec=_sell_spec(99),
            position_evidence=_position_evidence(
                lattice, account_id="account:other"
            ),
        ),
        timeline(intervals=(interval(rule_snapshot=snapshot(quantity_lattice=lattice)),)),
    )

    assert decision.data_integrity_failure is not None
    assert (
        decision.data_integrity_failure.code
        is MarketRuleDataIntegrityCode.INVALID_POSITION_EVIDENCE
    )


def test_active_odd_sell_reservation_prevents_a_second_residual_order() -> None:
    lattice = _residual_lattice()
    order = working_order(
        "e",
        instrument_id=INSTRUMENT,
        side=OrderSide.SELL,
        quantity_units=199,
    )
    stream = working_stream(order)
    reservations = reservation_state((stream,))
    evidence = _position_evidence(
        lattice,
        account_id=order.account_id,
        working_orders=(stream,),
        reservations=reservations,
    )
    decision = MarketRuleEvaluator().evaluate(
        evaluation_input(spec=_sell_spec(99), position_evidence=evidence),
        timeline(intervals=(interval(rule_snapshot=snapshot(quantity_lattice=lattice)),)),
    )

    assert list(_issue_codes(decision)) == [
        MarketRuleIssueCode.SELL_RESIDUAL_NOT_PERMITTED
    ]


def test_duplicate_or_wrong_scale_working_order_evidence_fails_closed() -> None:
    lattice = _residual_lattice()
    order = working_order(
        "d",
        instrument_id=INSTRUMENT,
        side=OrderSide.SELL,
        quantity_units=199,
    )
    stream = working_stream(order)
    reservations = reservation_state((stream,))
    duplicate = MarketRuleEvaluator().evaluate(
        evaluation_input(
            spec=_sell_spec(99),
            position_evidence=_position_evidence(
                lattice,
                working_orders=(stream, stream),
                reservations=reservations,
            ),
        ),
        timeline(intervals=(interval(rule_snapshot=snapshot(quantity_lattice=lattice)),)),
    )
    assert duplicate.data_integrity_failure is not None
    assert (
        duplicate.data_integrity_failure.code
        is MarketRuleDataIntegrityCode.INVALID_POSITION_EVIDENCE
    )

    wrong_scale_order = replace(
        order,
        intent=replace(
            order.intent,
            quantity=Quantity(199, Scale(2), str(INSTRUMENT)),
        ),
    )
    wrong_scale_stream = working_stream(wrong_scale_order)
    wrong_scale_reservations = reservation_state((wrong_scale_stream,))
    wrong_scale = MarketRuleEvaluator().evaluate(
        evaluation_input(
            spec=_sell_spec(99),
            position_evidence=_position_evidence(
                lattice,
                working_orders=(wrong_scale_stream,),
                reservations=wrong_scale_reservations,
            ),
        ),
        timeline(intervals=(interval(rule_snapshot=snapshot(quantity_lattice=lattice)),)),
    )
    assert wrong_scale.data_integrity_failure is not None
    assert (
        wrong_scale.data_integrity_failure.code
        is MarketRuleDataIntegrityCode.INVALID_POSITION_EVIDENCE
    )


def test_legacy_snapshot_and_evaluation_input_hashes_remain_schema_v1() -> None:
    legacy_snapshot = snapshot()
    legacy_input = evaluation_input()

    assert legacy_snapshot.snapshot_hash == (
        "sha256:bb698906ddea161ac22b9e828d70107508070e60f574830194e241b43d8c1dcf"
    )
    assert legacy_input.input_hash == (
        "sha256:7e0aba759add4cf38ef82a4cef78085978366fb916237d3374319cb33b509cd4"
    )
    assert legacy_snapshot.to_canonical_dict()["schema_version"] == 1
    assert legacy_input.to_canonical_dict()["schema_version"] == 1
    assert "max_limit_order_quantity_units" not in legacy_snapshot.to_canonical_dict()
    assert "position_evidence" not in legacy_input.to_canonical_dict()

    capped = snapshot(max_limit_order_quantity_units=1_000)
    evidenced = evaluation_input(position_evidence=_position_evidence(_residual_lattice()))
    assert capped.to_canonical_dict()["schema_version"] == 2
    assert evidenced.to_canonical_dict()["schema_version"] == 2
