from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import Any, cast

import pytest

from crypto_quant_domain import (
    DomainIdKind,
    OrderEventType,
    OrderStatus,
    Quantity,
    canonical_sha256,
)
from crypto_quant_trading import (
    CancelReplaceCausation,
    OrderEventConflictError,
    OrderEventOrderingError,
    OrderEventRecord,
    OrderEventStream,
    OrderFillError,
    OrderTransitionError,
)

from ._fixtures import domain_id, event, fill, full_lifecycle_records, instant, order


def test_full_lifecycle_replays_exact_state_independent_of_initial_input_order() -> None:
    subject = order()
    records = full_lifecycle_records(subject)

    forward = OrderEventStream.from_records(subject, records)
    reverse = OrderEventStream.from_records(subject, tuple(reversed(records)))

    assert reverse.records == forward.records
    assert reverse.stream_hash == forward.stream_hash
    assert reverse.state_hash == forward.state_hash
    assert forward.state is not None
    assert forward.state.status is OrderStatus.FILLED
    assert forward.state.cumulative_filled_quantity.units == 1_000
    assert forward.state.remaining_quantity.units == 0
    partial_state = forward.state_at(10)
    assert partial_state is not None
    assert partial_state.status is OrderStatus.PARTIALLY_FILLED
    assert forward.state_at(forward.event_count) == forward.state
    assert canonical_sha256(forward.state_at(10)) == forward.state_hash_at(10)


def test_identical_event_is_idempotent_but_conflict_and_late_insert_fail() -> None:
    subject = order()
    records = full_lifecycle_records(subject)
    stream = OrderEventStream.from_records(subject, records[:3])

    assert stream.append(records[2]) is stream
    conflict = replace(
        records[2],
        event=replace(records[2].event, evidence_id="evidence:conflict"),
    )
    with pytest.raises(OrderEventConflictError, match=records[2].event.event_id):
        stream.append(conflict)

    late = OrderEventRecord(
        event(
            subject,
            "late-capability",
            OrderEventType.ORDER_CAPABILITY_APPROVED,
            15,
            records[0].event.event_id,
        )
    )
    with pytest.raises(OrderEventOrderingError, match="published prefix"):
        stream.append(late)


def test_gate_order_and_terminal_state_regression_fail_closed() -> None:
    subject = order()
    records = full_lifecycle_records(subject)

    out_of_order_translation = replace(
        records[2], event=replace(records[2].event, causation_id=records[0].event.event_id)
    )
    with pytest.raises(OrderTransitionError, match="ORDER_TRANSLATED"):
        OrderEventStream.from_records(subject, (records[0], out_of_order_translation))

    rejected = OrderEventRecord(
        event(
            subject,
            "capability-rejected",
            OrderEventType.ORDER_CAPABILITY_REJECTED,
            20,
            records[0].event.event_id,
            reason_code="unsupported_style",
        )
    )
    rejected_stream = OrderEventStream.from_records(subject, (records[0], rejected))
    assert rejected_stream.state is not None
    assert rejected_stream.state.status is OrderStatus.REJECTED

    post_terminal = OrderEventRecord(
        event(
            subject,
            "post-terminal-capability",
            OrderEventType.ORDER_CAPABILITY_APPROVED,
            30,
            rejected.event.event_id,
        )
    )
    with pytest.raises(OrderTransitionError, match="terminal"):
        rejected_stream.append(post_terminal)


def test_fill_facts_are_exact_and_overfill_or_wrong_fill_event_fails() -> None:
    subject = order()
    records = full_lifecycle_records(subject)
    prefix = records[:9]

    wrong_partial_fill = fill(subject, "4", 1_000, 100)
    wrong_partial = OrderEventRecord(
        replace(records[9].event, fill_id=wrong_partial_fill.fill_id),
        wrong_partial_fill,
    )
    with pytest.raises(OrderFillError, match="partial.*remaining"):
        OrderEventStream.from_records(subject, prefix + (wrong_partial,))

    wrong_final_fill = fill(subject, "5", 500, 110)
    wrong_final = OrderEventRecord(
        replace(records[10].event, fill_id=wrong_final_fill.fill_id),
        wrong_final_fill,
    )
    with pytest.raises(OrderFillError, match="final.*remaining"):
        OrderEventStream.from_records(subject, records[:10] + (wrong_final,))

    overfill = fill(subject, "6", 700, 110)
    overfill_record = OrderEventRecord(
        replace(records[10].event, fill_id=overfill.fill_id),
        overfill,
    )
    with pytest.raises(OrderFillError, match="exceeds"):
        OrderEventStream.from_records(subject, records[:10] + (overfill_record,))

    with pytest.raises(ValueError, match="requires matching Fill"):
        OrderEventRecord(records[9].event)
    with pytest.raises(ValueError, match="non-Fill"):
        OrderEventRecord(records[8].event, fill(subject, "7", 1, 90))


def test_unknown_causation_and_order_context_mismatch_are_rejected() -> None:
    subject = order()
    records = full_lifecycle_records(subject)
    unknown_cause = OrderEventRecord(
        replace(records[1].event, causation_id="event:unknown")
    )
    with pytest.raises(OrderTransitionError, match="causation"):
        OrderEventStream.from_records(subject, (records[0], unknown_cause))

    other_order = order("9")
    with pytest.raises(OrderTransitionError, match="order_id"):
        OrderEventStream.from_records(other_order, (records[0],))


def test_cancel_pending_fill_race_preserves_remaining_then_cancels() -> None:
    subject = order()
    records = full_lifecycle_records(subject)
    accepted_prefix = records[:8]
    cancel_requested = OrderEventRecord(
        event(
            subject,
            "cancel-requested",
            OrderEventType.ORDER_CANCEL_REQUESTED,
            90,
            records[7].event.event_id,
        )
    )
    race_fill = fill(subject, "8", 400, 100)
    partial_after_cancel = OrderEventRecord(
        event(
            subject,
            "partial-after-cancel",
            OrderEventType.ORDER_PARTIALLY_FILLED,
            100,
            cancel_requested.event.event_id,
            fill_id=race_fill.fill_id,
        ),
        race_fill,
    )
    cancelled = OrderEventRecord(
        event(
            subject,
            "cancelled",
            OrderEventType.ORDER_CANCELLED,
            110,
            cancel_requested.event.event_id,
        )
    )

    stream = OrderEventStream.from_records(
        subject, accepted_prefix + (cancel_requested, partial_after_cancel, cancelled)
    )
    assert stream.state is not None
    assert stream.state.status is OrderStatus.CANCELLED
    assert stream.state.cumulative_filled_quantity.units == 400
    assert stream.state.remaining_quantity.units == 600
    cancel_pending_state = stream.state_at(10)
    assert cancel_pending_state is not None
    assert cancel_pending_state.status is OrderStatus.CANCEL_REQUESTED


def test_cancel_replace_requires_direct_terminal_causation_and_new_identity() -> None:
    subject = order()
    records = full_lifecycle_records(subject)
    cancel_requested = OrderEventRecord(
        event(
            subject,
            "cancel-requested",
            OrderEventType.ORDER_CANCEL_REQUESTED,
            90,
            records[7].event.event_id,
        )
    )
    cancelled = OrderEventRecord(
        event(
            subject,
            "cancelled",
            OrderEventType.ORDER_CANCELLED,
            100,
            cancel_requested.event.event_id,
        )
    )
    cancelled_stream = OrderEventStream.from_records(
        subject, records[:8] + (cancel_requested, cancelled)
    )

    replacement = replace(order("2"), created_at=instant(110))
    replacement_created = OrderEventRecord(
        event(
            replacement,
            "replacement-created",
            OrderEventType.ORDER_INTENT_CREATED,
            110,
            cancelled.event.event_id,
        )
    )
    replacement_stream = OrderEventStream.from_records(
        replacement, (replacement_created,)
    )
    link = CancelReplaceCausation(cancelled_stream, replacement_stream)

    assert link.cancelled_order_id == subject.order_id
    assert link.replacement_order_id == replacement.order_id
    assert link.cancelled_event_id == cancelled.event.event_id
    assert link.replacement_created_event_id == replacement_created.event.event_id

    bad_replacement = replace(order("3"), created_at=instant(110))
    bad_created = OrderEventRecord(
        event(
            bad_replacement,
            "bad-replacement-created",
            OrderEventType.ORDER_INTENT_CREATED,
            110,
            bad_replacement.intent.parent_id,
        )
    )
    bad_stream = OrderEventStream.from_records(bad_replacement, (bad_created,))
    with pytest.raises(OrderTransitionError, match="cancelled event"):
        CancelReplaceCausation(cancelled_stream, bad_stream)


def test_stream_is_immutable_and_rejects_forged_state_positions() -> None:
    stream = OrderEventStream.from_records(order(), full_lifecycle_records())

    with pytest.raises(FrozenInstanceError):
        cast(Any, stream).records = ()
    with pytest.raises(IndexError, match="position"):
        stream.state_at(stream.event_count + 1)
    with pytest.raises(TypeError, match="integer"):
        stream.state_at(cast(Any, True))

    assert stream.order.intent.quantity == Quantity(
        1_000,
        stream.order.intent.quantity.scale,
        stream.order.intent.quantity.instrument_id,
    )
    assert stream.order.order_id == domain_id(DomainIdKind.ORDER, "1")
