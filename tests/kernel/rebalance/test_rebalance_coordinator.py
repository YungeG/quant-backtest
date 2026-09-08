from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from crypto_quant_domain import (
    OrderSide,
    OrderStatus,
    PositionEffect,
    Quantity,
    Scale,
    TimeInForce,
    UtcInstant,
)
from crypto_quant_trading import (
    PlanningOmissionCode,
    RebalanceCoordinator,
    RebalanceFailureCode,
)

from ._fixtures import (
    QUANTITY_SCALE,
    availability,
    normalized_target,
    policy,
    reservation_state,
    snapshot,
    validity,
    working_order,
    working_stream,
)


def coordinate(
    *,
    portfolio_snapshot=None,
    streams=(),
    target_validity=None,
    rebalance_policy=policy(),
    prior_plan=None,
    as_of: int = 200,
):
    target = normalized_target()
    current = snapshot() if portfolio_snapshot is None else portfolio_snapshot
    reservations = reservation_state(streams)
    available = availability(current, reservations)
    return RebalanceCoordinator().coordinate(
        target=target,
        target_validity=validity() if target_validity is None else target_validity,
        portfolio_snapshot=current,
        working_orders=streams,
        reservations=reservations,
        availability=available,
        policy=rebalance_policy,
        as_of=UtcInstant(as_of),
        prior_plan=prior_plan,
    )


def test_exact_delta_is_planned_once_with_explicit_order_semantics() -> None:
    outcome = coordinate()
    assert outcome.failure is None
    assert outcome.decision is not None
    plan = outcome.decision.plan
    target = normalized_target()
    btc, eth = (value.instrument_id for value in target.targets)
    planned = {value.instrument_id: value for value in plan.planned_orders}

    assert planned[btc].intent.side is OrderSide.BUY
    assert planned[btc].intent.quantity == Quantity(10_000, QUANTITY_SCALE, str(btc))
    assert planned[btc].intent.position_effect is PositionEffect.OPEN
    assert not planned[btc].intent.reduce_only
    assert planned[btc].intent.time_in_force is TimeInForce.DAY
    assert planned[btc].intent.parent_id == target.normalized_target_id
    assert eth not in planned
    assert plan.omissions[0].code is PlanningOmissionCode.ALREADY_COVERED
    assert plan.valid_until == UtcInstant(250)

    repeated = coordinate(prior_plan=plan)
    assert repeated == outcome
    assert repeated.decision is not None
    assert repeated.decision.plan is plan


def test_working_order_and_partial_fill_cover_exact_remaining_delta() -> None:
    target = normalized_target()
    btc = target.targets[0].instrument_id
    order = working_order(
        "7",
        instrument_id=btc,
        side=OrderSide.BUY,
        quantity_units=10_000,
        parent_id=target.normalized_target_id,
    )
    active = working_stream(order)
    active_outcome = coordinate(streams=(active,))

    assert active.state is not None
    assert active.state.status is OrderStatus.ACTIVE
    assert active_outcome.decision is not None
    assert not active_outcome.decision.plan.planned_orders
    assert active_outcome.decision.plan.omissions[0].code is PlanningOmissionCode.ALREADY_COVERED

    partial = working_stream(order, partial_fill_units=4_000)
    partially_filled = coordinate(
        portfolio_snapshot=snapshot(btc_units=4_000),
        streams=(partial,),
    )
    assert partial.state is not None
    assert partial.state.remaining_quantity.units == 6_000
    assert partially_filled.decision is not None
    assert not partially_filled.decision.plan.planned_orders

    cancelled = working_stream(order, partial_fill_units=4_000, cancelled=True)
    assert cancelled.state is not None
    assert cancelled.state.status is OrderStatus.CANCELLED
    replanned = coordinate(portfolio_snapshot=snapshot(btc_units=4_000), streams=())
    assert replanned.decision is not None
    btc_order = replanned.decision.plan.planned_orders[0]
    assert btc_order.instrument_id == btc
    assert btc_order.intent.quantity.units == 6_000


def test_conflicting_working_order_is_cancelled_before_replacement() -> None:
    target = normalized_target()
    btc = target.targets[0].instrument_id
    old = working_order(
        "8",
        instrument_id=btc,
        side=OrderSide.BUY,
        quantity_units=10_000,
    )
    stream = working_stream(old)
    outcome = coordinate(
        portfolio_snapshot=snapshot(btc_units=5_000),
        streams=(stream,),
    )

    assert outcome.decision is not None
    plan = outcome.decision.plan
    assert [value.order_id for value in plan.cancel_intents] == [old.order_id]
    assert all(value.instrument_id != btc for value in plan.planned_orders)
    assert any(
        value.instrument_id == btc and value.code is PlanningOmissionCode.CANCELLATION_PENDING
        for value in plan.omissions
    )

    pending = working_stream(old, cancel_requested=True)
    pending_outcome = coordinate(
        portfolio_snapshot=snapshot(btc_units=5_000),
        streams=(pending,),
    )
    assert pending_outcome.decision is not None
    assert not pending_outcome.decision.plan.cancel_intents
    assert all(value.instrument_id != btc for value in pending_outcome.decision.plan.planned_orders)


def test_sign_reversal_closes_before_opening_opposite_exposure() -> None:
    target = normalized_target()
    btc = target.targets[0].instrument_id

    close = coordinate(portfolio_snapshot=snapshot(btc_units=-4_000))
    assert close.decision is not None
    btc_close = next(
        value for value in close.decision.plan.planned_orders if value.instrument_id == btc
    )
    assert btc_close.intent.side is OrderSide.BUY
    assert btc_close.intent.quantity.units == 4_000
    assert btc_close.intent.reduce_only
    assert btc_close.intent.position_effect is PositionEffect.CLOSE

    opened = coordinate(portfolio_snapshot=snapshot(btc_units=0))
    assert opened.decision is not None
    btc_open = next(
        value for value in opened.decision.plan.planned_orders if value.instrument_id == btc
    )
    assert btc_open.intent.quantity.units == 10_000
    assert not btc_open.intent.reduce_only
    assert btc_open.intent.position_effect is PositionEffect.OPEN


def test_expired_target_cancels_working_orders_without_conflating_plan_or_tif() -> None:
    target = normalized_target()
    btc = target.targets[0].instrument_id
    order = working_order(
        "9", instrument_id=btc, side=OrderSide.BUY, quantity_units=10_000
    )
    stream = working_stream(order)
    outcome = coordinate(
        streams=(stream,),
        target_validity=validity(valid_until=190),
        as_of=200,
    )

    assert outcome.decision is not None
    plan = outcome.decision.plan
    assert not plan.planned_orders
    assert plan.cancel_intents[0].order_id == order.order_id
    assert all(value.code is PlanningOmissionCode.TARGET_EXPIRED for value in plan.omissions)
    assert plan.valid_until == UtcInstant(250)
    assert order.intent.time_in_force is TimeInForce.DAY


def test_input_order_does_not_change_plan_and_changed_basis_supersedes_prior_plan() -> None:
    target = normalized_target()
    btc, eth = (value.instrument_id for value in target.targets)
    btc_order = working_order(
        "5", instrument_id=btc, side=OrderSide.BUY, quantity_units=2_000
    )
    eth_order = working_order(
        "6", instrument_id=eth, side=OrderSide.SELL, quantity_units=1_000
    )
    streams = (working_stream(btc_order), working_stream(eth_order))

    forward = coordinate(streams=streams)
    reverse = coordinate(streams=tuple(reversed(streams)))
    assert reverse == forward

    initial = coordinate()
    assert initial.decision is not None
    changed = coordinate(
        portfolio_snapshot=snapshot(btc_units=1_000, timestamp=201),
        prior_plan=initial.decision.plan,
        as_of=201,
    )
    assert changed.decision is not None
    assert changed.decision.plan.plan_id != initial.decision.plan.plan_id
    assert changed.decision.plan.supersedes_plan_id == initial.decision.plan.plan_id


def test_contract_evidence_failures_are_atomic_and_structured() -> None:
    missing = coordinate(rebalance_policy=None)
    assert missing.decision is None
    assert missing.failure is not None
    assert missing.failure.code is RebalanceFailureCode.MISSING_POLICY

    target = normalized_target()
    btc = target.targets[0].instrument_id
    order = working_order(
        "7", instrument_id=btc, side=OrderSide.BUY, quantity_units=10_000
    )
    terminal = working_stream(order, cancelled=True)
    invalid_terminal = coordinate(streams=(terminal,))
    assert invalid_terminal.decision is None
    assert invalid_terminal.failure is not None
    assert invalid_terminal.failure.code is RebalanceFailureCode.TERMINAL_WORKING_ORDER

    active = working_stream(order)
    current = snapshot()
    active_reservations = reservation_state((active,))
    duplicate = RebalanceCoordinator().coordinate(
        target=target,
        target_validity=validity(),
        portfolio_snapshot=current,
        working_orders=(active, active),
        reservations=active_reservations,
        availability=availability(current, active_reservations),
        policy=policy(),
        as_of=UtcInstant(200),
    )
    assert duplicate.decision is None
    assert duplicate.failure is not None
    assert duplicate.failure.code is RebalanceFailureCode.DUPLICATE_WORKING_ORDER

    empty_reservations = reservation_state()
    missing_reservation = RebalanceCoordinator().coordinate(
        target=target,
        target_validity=validity(),
        portfolio_snapshot=current,
        working_orders=(active,),
        reservations=empty_reservations,
        availability=availability(current, empty_reservations),
        policy=policy(),
        as_of=UtcInstant(200),
    )
    assert missing_reservation.failure is not None
    assert missing_reservation.failure.code is RebalanceFailureCode.CONTEXT_MISMATCH

    mismatched_order = replace(
        order,
        intent=replace(
            order.intent,
            quantity=Quantity(1_000, Scale(2), str(btc)),
        ),
    )
    mismatched_stream = working_stream(mismatched_order)
    mismatched_reservations = reservation_state((mismatched_stream,))
    quantity_mismatch = RebalanceCoordinator().coordinate(
        target=target,
        target_validity=validity(),
        portfolio_snapshot=current,
        working_orders=(mismatched_stream,),
        reservations=mismatched_reservations,
        availability=availability(current, mismatched_reservations),
        policy=policy(),
        as_of=UtcInstant(200),
    )
    assert quantity_mismatch.failure is not None
    assert quantity_mismatch.failure.code is RebalanceFailureCode.QUANTITY_SCALE_MISMATCH

    invalid_validity = coordinate(
        target_validity=replace(
            validity(), normalized_target_hash="sha256:" + "e" * 64
        )
    )
    assert invalid_validity.failure is not None
    assert invalid_validity.failure.code is RebalanceFailureCode.TARGET_VALIDITY_MISMATCH

    current = snapshot()
    reservations = reservation_state()
    forged_availability = replace(
        availability(current, reservations),
        reservation_state_hash="sha256:" + "f" * 64,
    )
    mismatch = RebalanceCoordinator().coordinate(
        target=target,
        target_validity=validity(),
        portfolio_snapshot=current,
        working_orders=(),
        reservations=reservations,
        availability=forged_availability,
        policy=policy(),
        as_of=UtcInstant(200),
    )
    assert mismatch.failure is not None
    assert mismatch.failure.code is RebalanceFailureCode.CONTEXT_MISMATCH


def test_values_are_immutable() -> None:
    outcome = coordinate()
    assert outcome.decision is not None
    with pytest.raises(FrozenInstanceError):
        setattr(outcome.decision.plan, "created_at", UtcInstant(999))
