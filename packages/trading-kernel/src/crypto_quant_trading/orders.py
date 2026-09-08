from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from crypto_quant_domain import (
    DomainId,
    Fill,
    Order,
    OrderEvent,
    OrderEventType,
    OrderState,
    OrderStatus,
    Quantity,
    SimulationInstant,
    canonical_sha256,
)


_FILL_EVENTS = {
    OrderEventType.ORDER_PARTIALLY_FILLED,
    OrderEventType.ORDER_FILLED,
}
_TERMINAL_STATUSES = {
    OrderStatus.FILLED,
    OrderStatus.CANCELLED,
    OrderStatus.EXPIRED,
    OrderStatus.REJECTED,
}
_GATE_NEXT = {
    OrderEventType.ORDER_INTENT_CREATED: {
        OrderEventType.ORDER_CAPABILITY_APPROVED,
        OrderEventType.ORDER_CAPABILITY_REJECTED,
    },
    OrderEventType.ORDER_CAPABILITY_APPROVED: {
        OrderEventType.ORDER_TRANSLATED,
    },
    OrderEventType.ORDER_TRANSLATED: {
        OrderEventType.MARKET_RULE_APPROVED,
        OrderEventType.MARKET_RULE_REJECTED,
    },
    OrderEventType.MARKET_RULE_APPROVED: {
        OrderEventType.FEE_RESERVATION_ESTIMATED,
    },
    OrderEventType.FEE_RESERVATION_ESTIMATED: {
        OrderEventType.PRE_TRADE_RISK_APPROVED,
        OrderEventType.PRE_TRADE_RISK_REJECTED,
    },
    OrderEventType.PRE_TRADE_RISK_APPROVED: {
        OrderEventType.ORDER_SUBMITTED,
    },
}
_GATE_REJECTIONS = {
    OrderEventType.ORDER_CAPABILITY_REJECTED,
    OrderEventType.MARKET_RULE_REJECTED,
    OrderEventType.PRE_TRADE_RISK_REJECTED,
}


class OrderEventStreamError(ValueError):
    """Base class for invalid immutable Order lifecycle evidence."""


class OrderEventConflictError(OrderEventStreamError):
    def __init__(
        self,
        event_id: str,
        existing_record_hash: str,
        conflicting_record_hash: str,
    ) -> None:
        self.event_id = event_id
        self.existing_record_hash = existing_record_hash
        self.conflicting_record_hash = conflicting_record_hash
        super().__init__(f"conflicting content for Order Event {event_id}")


class OrderEventOrderingError(OrderEventStreamError):
    """Raised when an event would rewrite an already-published prefix."""


class OrderTransitionError(OrderEventStreamError):
    """Raised for an illegal gate, lifecycle, or causation transition."""


class OrderFillError(OrderEventStreamError):
    """Raised when Fill evidence cannot produce an exact Order quantity state."""


@dataclass(frozen=True, slots=True)
class OrderEventRecord:
    event: OrderEvent
    fill: Fill | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.event, OrderEvent):
            raise TypeError("event must be OrderEvent")
        if self.event.event_type in _FILL_EVENTS:
            if not isinstance(self.fill, Fill) or self.fill.fill_id != self.event.fill_id:
                raise ValueError("Fill OrderEvent requires matching Fill")
        elif self.fill is not None:
            raise ValueError("non-Fill OrderEvent cannot carry Fill")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_event_record",
            "event": self.event,
            "fill": self.fill,
        }


@dataclass(frozen=True, slots=True)
class _Projection:
    state: OrderState | None
    last_event_type: OrderEventType | None
    lifecycle_rank: int
    cancel_pending: bool
    seen_event_ids: frozenset[str]
    seen_fill_ids: frozenset[str]


_EMPTY_PROJECTION = _Projection(None, None, -1, False, frozenset(), frozenset())


def _record_order_key(record: OrderEventRecord) -> tuple[SimulationInstant, str]:
    return record.event.occurred_at, record.event.event_id


def _record_hash(record: OrderEventRecord) -> str:
    return canonical_sha256(record)


def _records_tuple(records: Iterable[OrderEventRecord]) -> tuple[OrderEventRecord, ...]:
    try:
        candidates = tuple(records)
    except TypeError as error:
        raise TypeError("records must be an iterable of OrderEventRecord") from error
    if not all(isinstance(record, OrderEventRecord) for record in candidates):
        raise TypeError("records must contain only OrderEventRecord")
    return candidates


def _next_prefix_hash(previous_hash: str, record_hash: str) -> str:
    return canonical_sha256(
        {
            "type": "order_event_stream_prefix",
            "schema_version": 1,
            "previous_hash": previous_hash,
            "record_hash": record_hash,
        }
    )


def _quantity(order: Order, units: int) -> Quantity:
    source = order.intent.quantity
    return Quantity(units, source.scale, source.instrument_id)


def _state(
    order: Order,
    status: OrderStatus,
    cumulative_units: int,
    event: OrderEvent,
) -> OrderState:
    return OrderState(
        order_id=order.order_id,
        status=status,
        ordered_quantity=order.intent.quantity,
        cumulative_filled_quantity=_quantity(order, cumulative_units),
        remaining_quantity=_quantity(order, order.intent.quantity.units - cumulative_units),
        last_event_id=event.event_id,
        updated_at=event.occurred_at,
    )


def _validate_fill(order: Order, record: OrderEventRecord, cumulative_units: int) -> int:
    fill = record.fill
    if fill is None:
        raise OrderFillError("Fill event is missing its Fill fact")
    if fill.order_id != order.order_id:
        raise OrderFillError("Fill order identity mismatch")
    if fill.account_id != order.account_id:
        raise OrderFillError("Fill account identity mismatch")
    if fill.instrument_id != order.intent.instrument_id:
        raise OrderFillError("Fill instrument identity mismatch")
    if fill.side is not order.intent.side:
        raise OrderFillError("Fill side mismatch")
    if (
        fill.quantity.instrument_id != order.intent.quantity.instrument_id
        or fill.quantity.scale != order.intent.quantity.scale
    ):
        raise OrderFillError("Fill quantity identity or scale mismatch")
    if fill.execution_time != record.event.occurred_at.instant:
        raise OrderFillError("Fill execution time must equal Order Event instant")

    total = cumulative_units + fill.quantity.units
    ordered = order.intent.quantity.units
    if total > ordered:
        raise OrderFillError("cumulative Fill quantity exceeds ordered quantity")
    if record.event.event_type is OrderEventType.ORDER_PARTIALLY_FILLED and total >= ordered:
        raise OrderFillError("partial Fill must preserve positive remaining quantity")
    if record.event.event_type is OrderEventType.ORDER_FILLED and total != ordered:
        raise OrderFillError("final Fill must leave zero remaining quantity")
    return total


def _advance(order: Order, projection: _Projection, record: OrderEventRecord) -> _Projection:
    event = record.event
    if event.order_id != order.order_id:
        raise OrderTransitionError("Order Event order_id does not match Order")
    if event.occurred_at < order.created_at:
        raise OrderTransitionError("Order Event cannot occur before Order creation")

    if projection.state is None:
        if event.event_type is not OrderEventType.ORDER_INTENT_CREATED:
            raise OrderTransitionError("first Event must be ORDER_INTENT_CREATED")
        if event.occurred_at != order.created_at:
            raise OrderTransitionError("created Event must equal Order.created_at")
        state = _state(order, OrderStatus.CREATED, 0, event)
        return _Projection(
            state,
            event.event_type,
            -1,
            False,
            frozenset((event.event_id,)),
            frozenset(),
        )

    if projection.state.status in _TERMINAL_STATUSES:
        raise OrderTransitionError("terminal Order state cannot accept another Event")
    if event.causation_id not in projection.seen_event_ids:
        raise OrderTransitionError("Order Event causation must reference an earlier Event")

    previous_type = projection.last_event_type
    if previous_type is None:
        raise OrderTransitionError("nonempty Order projection is missing event type")
    expected_gate_events = _GATE_NEXT.get(previous_type)
    if expected_gate_events is not None:
        if event.event_type not in expected_gate_events:
            raise OrderTransitionError(
                f"invalid transition from {previous_type.name} to {event.event_type.name}"
            )
        if event.event_type in _GATE_REJECTIONS:
            status = OrderStatus.REJECTED
            lifecycle_rank = projection.lifecycle_rank
        elif event.event_type is OrderEventType.ORDER_SUBMITTED:
            status = OrderStatus.SUBMITTED
            lifecycle_rank = 0
        else:
            status = OrderStatus.CREATED
            lifecycle_rank = projection.lifecycle_rank
        state = _state(
            order,
            status,
            projection.state.cumulative_filled_quantity.units,
            event,
        )
        return _Projection(
            state,
            event.event_type,
            lifecycle_rank,
            projection.cancel_pending,
            projection.seen_event_ids | frozenset((event.event_id,)),
            projection.seen_fill_ids,
        )

    event_type = event.event_type
    lifecycle_rank = projection.lifecycle_rank
    cancel_pending = projection.cancel_pending
    cumulative_units = projection.state.cumulative_filled_quantity.units
    seen_fill_ids = projection.seen_fill_ids

    if event_type is OrderEventType.ORDER_ACCEPTED:
        if lifecycle_rank != 0:
            raise OrderTransitionError("ORDER_ACCEPTED requires submitted Order")
        lifecycle_rank = 1
        status = OrderStatus.CANCEL_REQUESTED if cancel_pending else OrderStatus.ACCEPTED
    elif event_type is OrderEventType.ORDER_ACTIVATED:
        if lifecycle_rank != 1:
            raise OrderTransitionError("ORDER_ACTIVATED requires accepted Order")
        lifecycle_rank = 2
        status = OrderStatus.CANCEL_REQUESTED if cancel_pending else OrderStatus.ACTIVE
    elif event_type in _FILL_EVENTS:
        if lifecycle_rank < 1:
            raise OrderTransitionError("Fill requires accepted or active Order")
        fill = record.fill
        if fill is None:
            raise OrderFillError("Fill event is missing its Fill fact")
        fill_id = fill.fill_id.value
        if fill_id in seen_fill_ids:
            raise OrderFillError("duplicate Fill identity")
        cumulative_units = _validate_fill(order, record, cumulative_units)
        seen_fill_ids = seen_fill_ids | frozenset((fill_id,))
        if event_type is OrderEventType.ORDER_FILLED:
            status = OrderStatus.FILLED
        else:
            status = (
                OrderStatus.CANCEL_REQUESTED
                if cancel_pending
                else OrderStatus.PARTIALLY_FILLED
            )
    elif event_type is OrderEventType.ORDER_CANCEL_REQUESTED:
        if lifecycle_rank < 0 or cancel_pending:
            raise OrderTransitionError("ORDER_CANCEL_REQUESTED requires working Order")
        cancel_pending = True
        status = OrderStatus.CANCEL_REQUESTED
    elif event_type is OrderEventType.ORDER_CANCELLED:
        if not cancel_pending:
            raise OrderTransitionError("ORDER_CANCELLED requires prior cancel request")
        status = OrderStatus.CANCELLED
    elif event_type is OrderEventType.ORDER_EXPIRED:
        if lifecycle_rank < 1 and not cancel_pending:
            raise OrderTransitionError("ORDER_EXPIRED requires accepted working Order")
        status = OrderStatus.EXPIRED
    elif event_type is OrderEventType.ORDER_REJECTED:
        if lifecycle_rank != 0 or cumulative_units != 0:
            raise OrderTransitionError("ORDER_REJECTED requires unfilled submitted Order")
        status = OrderStatus.REJECTED
    else:
        name = event_type.name
        raise OrderTransitionError(f"invalid lifecycle transition to {name}")

    state = _state(order, status, cumulative_units, event)
    return _Projection(
        state,
        event_type,
        lifecycle_rank,
        cancel_pending,
        projection.seen_event_ids | frozenset((event.event_id,)),
        seen_fill_ids,
    )


@dataclass(frozen=True, slots=True)
class OrderEventStream:
    order: Order
    records: tuple[OrderEventRecord, ...] = ()
    _record_hashes: tuple[str, ...] = field(init=False, repr=False)
    _prefix_hashes: tuple[str, ...] = field(init=False, repr=False)
    _states: tuple[OrderState | None, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.order, Order):
            raise TypeError("order must be Order")
        if not isinstance(self.records, tuple) or not all(
            isinstance(record, OrderEventRecord) for record in self.records
        ):
            raise TypeError("records must be a tuple of OrderEventRecord")

        previous_key: tuple[SimulationInstant, str] | None = None
        seen_ids: dict[str, str] = {}
        projection = _EMPTY_PROJECTION
        states: list[OrderState | None] = [None]
        record_hashes: list[str] = []
        prefix_hashes = [
            canonical_sha256(
                {
                    "type": "order_event_stream_genesis",
                    "schema_version": 1,
                    "order_hash": canonical_sha256(self.order),
                }
            )
        ]

        for record in self.records:
            key = _record_order_key(record)
            if previous_key is not None and key <= previous_key:
                raise OrderEventOrderingError(
                    "Order Event records must use strict stable order"
                )
            previous_key = key
            content_hash = _record_hash(record)
            existing_hash = seen_ids.get(record.event.event_id)
            if existing_hash is not None:
                if existing_hash != content_hash:
                    raise OrderEventConflictError(
                        record.event.event_id, existing_hash, content_hash
                    )
                raise OrderEventOrderingError("duplicate Event identity in stream")
            seen_ids[record.event.event_id] = content_hash
            projection = _advance(self.order, projection, record)
            record_hashes.append(content_hash)
            prefix_hashes.append(_next_prefix_hash(prefix_hashes[-1], content_hash))
            states.append(projection.state)

        object.__setattr__(self, "_record_hashes", tuple(record_hashes))
        object.__setattr__(self, "_prefix_hashes", tuple(prefix_hashes))
        object.__setattr__(self, "_states", tuple(states))

    @classmethod
    def empty(cls, order: Order) -> OrderEventStream:
        return cls(order)

    @classmethod
    def from_records(
        cls, order: Order, records: Iterable[OrderEventRecord]
    ) -> OrderEventStream:
        candidates = _records_tuple(records)

        unique: dict[str, tuple[str, OrderEventRecord]] = {}
        for record in candidates:
            event_id = record.event.event_id
            content_hash = _record_hash(record)
            existing = unique.get(event_id)
            if existing is not None:
                if existing[0] != content_hash:
                    raise OrderEventConflictError(event_id, existing[0], content_hash)
                continue
            unique[event_id] = content_hash, record
        ordered = tuple(
            sorted((item[1] for item in unique.values()), key=_record_order_key)
        )
        return cls(order, ordered)

    @property
    def event_count(self) -> int:
        return len(self.records)

    @property
    def record_hashes(self) -> tuple[str, ...]:
        return self._record_hashes

    @property
    def stream_hash(self) -> str:
        return self._prefix_hashes[-1]

    @property
    def state(self) -> OrderState | None:
        return self._states[-1]

    @property
    def state_hash(self) -> str:
        return self.state_hash_at(self.event_count)

    def state_at(self, position: int) -> OrderState | None:
        if isinstance(position, bool) or not isinstance(position, int):
            raise TypeError("state position must be an integer")
        if not 0 <= position <= self.event_count:
            raise IndexError("state position is outside Order Event stream")
        return self._states[position]

    def state_hash_at(self, position: int) -> str:
        state = self.state_at(position)
        if state is None:
            return canonical_sha256(
                {
                    "type": "empty_order_state",
                    "schema_version": 1,
                    "order_id": self.order.order_id,
                }
            )
        return canonical_sha256(state)

    def append(self, record: OrderEventRecord) -> OrderEventStream:
        if not isinstance(record, OrderEventRecord):
            raise TypeError("record must be OrderEventRecord")
        return self.append_many((record,))

    def append_many(self, records: Iterable[OrderEventRecord]) -> OrderEventStream:
        candidates = _records_tuple(records)
        if not candidates:
            return self

        existing = {
            record.event.event_id: content_hash
            for record, content_hash in zip(
                self.records, self._record_hashes, strict=True
            )
        }
        pending: dict[str, tuple[str, OrderEventRecord]] = {}
        for record in candidates:
            event_id = record.event.event_id
            content_hash = _record_hash(record)
            known_hash = existing.get(event_id)
            if known_hash is not None:
                if known_hash != content_hash:
                    raise OrderEventConflictError(event_id, known_hash, content_hash)
                continue
            known_pending = pending.get(event_id)
            if known_pending is not None:
                if known_pending[0] != content_hash:
                    raise OrderEventConflictError(
                        event_id, known_pending[0], content_hash
                    )
                continue
            pending[event_id] = content_hash, record

        if not pending:
            return self
        ordered = tuple(
            sorted((value[1] for value in pending.values()), key=_record_order_key)
        )
        if self.records and _record_order_key(ordered[0]) <= _record_order_key(
            self.records[-1]
        ):
            raise OrderEventOrderingError(
                "append would insert before the published prefix boundary"
            )
        return OrderEventStream(self.order, self.records + ordered)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_event_stream",
            "schema_version": 1,
            "order": self.order,
            "records": self.records,
            "stream_hash": self.stream_hash,
            "state_hash": self.state_hash,
        }


@dataclass(frozen=True, slots=True, init=False)
class CancelReplaceCausation:
    cancelled_order_id: DomainId
    cancel_requested_event_id: str
    cancelled_event_id: str
    replacement_order_id: DomainId
    replacement_created_event_id: str

    def __init__(
        self,
        cancelled_stream: OrderEventStream,
        replacement_stream: OrderEventStream,
    ) -> None:
        if not isinstance(cancelled_stream, OrderEventStream) or not isinstance(
            replacement_stream, OrderEventStream
        ):
            raise TypeError("cancelled_stream and replacement_stream must be OrderEventStream")
        if cancelled_stream.state is None or (
            cancelled_stream.state.status is not OrderStatus.CANCELLED
        ):
            raise OrderTransitionError("cancel-replace requires cancelled source Order")
        if not cancelled_stream.records or not replacement_stream.records:
            raise OrderTransitionError("cancel-replace streams must be nonempty")
        cancelled_record = cancelled_stream.records[-1]
        if cancelled_record.event.event_type is not OrderEventType.ORDER_CANCELLED:
            raise OrderTransitionError("cancelled source must end with ORDER_CANCELLED")
        request_records = tuple(
            record
            for record in cancelled_stream.records
            if record.event.event_type is OrderEventType.ORDER_CANCEL_REQUESTED
        )
        if len(request_records) != 1 or (
            cancelled_record.event.causation_id != request_records[0].event.event_id
        ):
            raise OrderTransitionError(
                "cancelled event must be directly caused by one cancel request"
            )
        replacement_record = replacement_stream.records[0]
        if replacement_record.event.event_type is not OrderEventType.ORDER_INTENT_CREATED:
            raise OrderTransitionError("replacement must begin with created Event")
        if (
            replacement_record.event.causation_id
            != cancelled_record.event.event_id
        ):
            raise OrderTransitionError(
                "replacement created Event must reference cancelled event"
            )
        if cancelled_stream.order.order_id == replacement_stream.order.order_id:
            raise OrderTransitionError("cancel-replace requires a new Order identity")
        if cancelled_stream.order.account_id != replacement_stream.order.account_id or (
            cancelled_stream.order.intent.instrument_id
            != replacement_stream.order.intent.instrument_id
        ):
            raise OrderTransitionError(
                "cancel-replace requires matching account and Instrument"
            )
        if replacement_record.event.occurred_at <= cancelled_record.event.occurred_at:
            raise OrderTransitionError("replacement must occur after cancelled event")

        object.__setattr__(self, "cancelled_order_id", cancelled_stream.order.order_id)
        object.__setattr__(
            self, "cancel_requested_event_id", request_records[0].event.event_id
        )
        object.__setattr__(self, "cancelled_event_id", cancelled_record.event.event_id)
        object.__setattr__(self, "replacement_order_id", replacement_stream.order.order_id)
        object.__setattr__(
            self,
            "replacement_created_event_id",
            replacement_record.event.event_id,
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cancel_replace_causation",
            "cancelled_order_id": self.cancelled_order_id,
            "cancel_requested_event_id": self.cancel_requested_event_id,
            "cancelled_event_id": self.cancelled_event_id,
            "replacement_order_id": self.replacement_order_id,
            "replacement_created_event_id": self.replacement_created_event_id,
        }
