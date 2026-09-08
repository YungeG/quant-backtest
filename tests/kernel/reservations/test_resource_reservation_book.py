from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import Any, cast

import pytest

from crypto_quant_domain import Money, OrderEventType, OrderSide, Quantity, Scale
from crypto_quant_trading import (
    OrderEventRecord,
    OrderEventStream,
    OrderReservationSchedule,
    OrderReservationUpdate,
    ReservationCommitment,
    ReservationEvidenceError,
    ReservationStateMismatchError,
    ResourceReservationBook,
)

from tests.kernel.orders._fixtures import event, full_lifecycle_records

from ._fixtures import (
    ACCOUNT,
    buy_commitment,
    schedule,
    source_hash,
    stream,
    subject_order,
)


MONEY_SCALE = Scale(2)


def test_activation_partial_fill_and_terminal_release_are_exact() -> None:
    subject = subject_order()
    reservation_schedule = schedule(subject)
    book = ResourceReservationBook(ACCOUNT)

    accepted = book.project((stream(subject, 8),), (reservation_schedule,))
    activated = book.project((stream(subject, 9),), (reservation_schedule,))
    partial = book.project((stream(subject, 10),), (reservation_schedule,))
    terminal = book.project((stream(subject, 11),), (reservation_schedule,))

    assert len(accepted.active_reservations) == 1
    assert accepted.totals == buy_commitment()
    assert activated.totals == accepted.totals
    assert len(activated.active_reservations) == 1
    assert partial.active_reservations[0].remaining_quantity.units == 600
    assert partial.totals == buy_commitment(partial=True)
    assert not terminal.active_reservations
    assert terminal.totals == ReservationCommitment.empty()


def test_activation_can_be_explicitly_deferred_to_active_event() -> None:
    subject = subject_order()
    records = full_lifecycle_records(subject)
    valid = schedule(subject)
    activate_on_active = replace(
        valid.updates[0],
        event_id=records[8].event.event_id,
        event_type=OrderEventType.ORDER_ACTIVATED,
    )
    deferred = replace(
        valid,
        updates=(activate_on_active, valid.updates[1]),
    )
    book = ResourceReservationBook(ACCOUNT)

    accepted = book.project((stream(subject, 8),), (deferred,))
    activated = book.project((stream(subject, 9),), (deferred,))

    resumed = book.resume(accepted, (stream(subject, 9),), (deferred,))

    assert not accepted.active_reservations
    assert accepted.totals.is_empty
    assert activated.totals == buy_commitment()
    assert resumed == activated


def test_terminal_cancel_expire_and_preaccept_reject_release_all() -> None:
    subject = subject_order()
    records = full_lifecycle_records(subject)
    valid_schedule = schedule(subject)
    activation_only = replace(valid_schedule, updates=valid_schedule.updates[:1])
    cancel_requested = OrderEventRecord(
        event(
            subject,
            "reservation-cancel-requested",
            OrderEventType.ORDER_CANCEL_REQUESTED,
            90,
            records[7].event.event_id,
        )
    )
    cancelled = OrderEventRecord(
        event(
            subject,
            "reservation-cancelled",
            OrderEventType.ORDER_CANCELLED,
            100,
            cancel_requested.event.event_id,
        )
    )
    expired = OrderEventRecord(
        event(
            subject,
            "reservation-expired",
            OrderEventType.ORDER_EXPIRED,
            90,
            records[7].event.event_id,
        )
    )
    rejected = OrderEventRecord(
        event(
            subject,
            "reservation-rejected",
            OrderEventType.ORDER_REJECTED,
            80,
            records[6].event.event_id,
            reason_code="venue_rejected",
        )
    )
    book = ResourceReservationBook(ACCOUNT)

    cancelled_state = book.project(
        (
            OrderEventStream.from_records(
                subject,
                records[:8] + (cancel_requested, cancelled),
            ),
        ),
        (activation_only,),
    )
    expired_state = book.project(
        (OrderEventStream.from_records(subject, records[:8] + (expired,)),),
        (activation_only,),
    )
    rejected_state = book.project(
        (OrderEventStream.from_records(subject, records[:7] + (rejected,)),),
        (),
    )

    assert cancelled_state.totals.is_empty
    assert expired_state.totals.is_empty
    assert rejected_state.totals.is_empty


def test_stream_schedule_and_resource_input_order_do_not_change_state() -> None:
    buy = subject_order("1")
    sell = subject_order("9", side=OrderSide.SELL)
    buy_stream = stream(buy, 10)
    sell_stream = stream(sell, 10)
    buy_schedule = schedule(buy)
    sell_schedule = schedule(sell, sell=True)
    book = ResourceReservationBook(ACCOUNT)

    forward = book.project(
        (buy_stream, sell_stream),
        (buy_schedule, sell_schedule),
    )
    reverse = book.project(
        (sell_stream, buy_stream),
        (sell_schedule, buy_schedule),
    )

    assert reverse == forward
    assert reverse.state_hash == forward.state_hash
    assert forward.totals.cash == (Money(6_300, MONEY_SCALE, "USD"),)
    assert forward.totals.sellable_quantities[0].units == 600
    assert forward.totals.fee_reserve == (Money(500, MONEY_SCALE, "USD"),)
    assert forward.totals.order_capacity_units == 2
    assert forward.totals.exposure_capacity == (Money(12_000, MONEY_SCALE, "USD"),)


def test_identical_event_replay_is_idempotent() -> None:
    subject = subject_order()
    prefix = stream(subject, 8)
    duplicate = prefix.append(prefix.records[-1])
    book = ResourceReservationBook(ACCOUNT)

    assert duplicate is prefix
    assert book.project((duplicate,), (schedule(subject),)).state_hash == book.project(
        (prefix,), (schedule(subject),)
    ).state_hash


def test_schedule_requires_one_activation_and_every_partial_update() -> None:
    subject = subject_order()
    valid = schedule(subject)
    records = stream(subject, 10).records
    book = ResourceReservationBook(ACCOUNT)

    with pytest.raises(ReservationEvidenceError, match="activation"):
        book.project((stream(subject, 10),), (replace(valid, updates=valid.updates[1:]),))

    activated_twice = replace(
        valid,
        updates=valid.updates
        + (
            replace(
                valid.updates[0],
                event_id=records[8].event.event_id,
                event_type=OrderEventType.ORDER_ACTIVATED,
                source_evidence_hash=source_hash("c"),
            ),
        ),
    )
    with pytest.raises(ReservationEvidenceError, match="activation"):
        book.project((stream(subject, 10),), (activated_twice,))

    with pytest.raises(ReservationEvidenceError, match="Partial Fill"):
        book.project(
            (stream(subject, 10),),
            (replace(valid, updates=valid.updates[:1]),),
        )

    extra = replace(
        valid.updates[1],
        event_id=records[6].event.event_id,
        source_evidence_hash=source_hash("d"),
    )
    with pytest.raises(ReservationEvidenceError, match="eligible"):
        book.project(
            (stream(subject, 10),),
            (replace(valid, updates=valid.updates + (extra,)),),
        )


def test_update_quantity_and_nonincreasing_commitment_fail_closed() -> None:
    subject = subject_order()
    valid = schedule(subject)
    book = ResourceReservationBook(ACCOUNT)

    wrong_quantity = replace(
        valid.updates[1],
        remaining_quantity=Quantity(
            500,
            valid.updates[1].remaining_quantity.scale,
            valid.updates[1].remaining_quantity.instrument_id,
        ),
    )
    with pytest.raises(ReservationEvidenceError, match="remaining Quantity"):
        book.project(
            (stream(subject, 10),),
            (replace(valid, updates=(valid.updates[0], wrong_quantity)),),
        )

    increased = replace(
        valid.updates[1],
        commitment=replace(
            buy_commitment(partial=True),
            cash=(Money(10_600, MONEY_SCALE, "USD"),),
        ),
    )
    with pytest.raises(ReservationEvidenceError, match="increase"):
        book.project(
            (stream(subject, 10),),
            (replace(valid, updates=(valid.updates[0], increased)),),
        )

    new_dimension = replace(
        valid.updates[1],
        commitment=replace(
            buy_commitment(partial=True),
            cash=(
                Money(6_300, MONEY_SCALE, "USD"),
                Money(1, MONEY_SCALE, "EUR"),
            ),
        ),
    )
    with pytest.raises(ReservationEvidenceError, match="introduce"):
        book.project(
            (stream(subject, 10),),
            (replace(valid, updates=(valid.updates[0], new_dimension)),),
        )


def test_commitment_and_account_contracts_fail_closed() -> None:
    with pytest.raises(ValueError, match="positive"):
        ReservationCommitment(cash=(Money(0, MONEY_SCALE, "USD"),))
    with pytest.raises(ValueError, match="duplicate"):
        ReservationCommitment(
            cash=(
                Money(100, MONEY_SCALE, "USD"),
                Money(1, Scale(3), "USD"),
            ),
        )
    with pytest.raises(TypeError, match="integer"):
        ReservationCommitment(order_capacity_units=cast(Any, True))

    subject = subject_order()
    with pytest.raises(ReservationEvidenceError, match="account"):
        ResourceReservationBook("account:other").project(
            (stream(subject, 8),),
            (schedule(subject),),
        )


def test_prefix_resume_verifies_prior_state_and_matches_full_replay() -> None:
    subject = subject_order()
    reservation_schedule = schedule(subject)
    book = ResourceReservationBook(ACCOUNT)
    prior = book.project((stream(subject, 10),), (reservation_schedule,))

    resumed = book.resume(prior, (stream(subject, 11),), (reservation_schedule,))
    rebuilt = book.project((stream(subject, 11),), (reservation_schedule,))

    assert resumed == rebuilt
    assert resumed.state_hash == rebuilt.state_hash

    forged_cursor = replace(
        prior.cursors[0],
        event_count=prior.cursors[0].event_count - 1,
    )
    forged = replace(prior, cursors=(forged_cursor,))
    with pytest.raises(ReservationStateMismatchError, match="prior state"):
        book.resume(forged, (stream(subject, 11),), (reservation_schedule,))


def test_state_is_immutable_and_schedule_rejects_wrong_event_context() -> None:
    subject = subject_order()
    valid = schedule(subject)
    state = ResourceReservationBook(ACCOUNT).project(
        (stream(subject, 8),),
        (valid,),
    )

    with pytest.raises(FrozenInstanceError):
        cast(Any, state).active_reservations = ()

    records = stream(subject, 8).records
    wrong_event = replace(
        valid.updates[0],
        event_id=records[0].event.event_id,
        source_evidence_hash=source_hash("e"),
    )
    with pytest.raises(ReservationEvidenceError, match="eligible"):
        ResourceReservationBook(ACCOUNT).project(
            (stream(subject, 8),),
            (replace(valid, updates=(wrong_event,)),),
        )

    assert records[-1].event.event_type is OrderEventType.ORDER_ACCEPTED
