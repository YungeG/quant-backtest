"""Immutable projection of supplied Working Order resource commitments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, TypeVar

from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    Money,
    OrderEventType,
    OrderStatus,
    Quantity,
    canonical_bytes,
    canonical_sha256,
)

from .orders import OrderEventStream


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ACTIVATION_EVENTS = {
    OrderEventType.ORDER_ACCEPTED,
    OrderEventType.ORDER_ACTIVATED,
}
_TERMINAL_STATUSES = {
    OrderStatus.FILLED,
    OrderStatus.CANCELLED,
    OrderStatus.EXPIRED,
    OrderStatus.REJECTED,
}


class ResourceReservationError(ValueError):
    """Base class for invalid reservation evidence or replay state."""


class ReservationEvidenceError(ResourceReservationError):
    """Raised when supplied reservation evidence does not match an Order stream."""


class ReservationStateMismatchError(ResourceReservationError):
    """Raised when a prior reservation state is not its claimed stream prefix."""


def _require_text(name: str, value: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{name} must be text")
    if not value or value.strip() != value:
        raise ValueError(f"{name} must be non-empty trimmed text")
    canonical_bytes(value)


def _require_hash(name: str, value: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{name} must be text")
    if _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 identity")


def _require_order_id(name: str, value: DomainId) -> None:
    if not isinstance(value, DomainId) or value.kind is not DomainIdKind.ORDER:
        raise TypeError(f"{name} must be an ORDER DomainId")


def _money_key(value: Money) -> str:
    return value.currency


def _quantity_key(value: Quantity) -> str:
    return value.instrument_id


def _validate_values(
    name: str,
    values: tuple[Money, ...] | tuple[Quantity, ...],
    expected_type: type[Money] | type[Quantity],
) -> None:
    if not isinstance(values, tuple) or not all(
        isinstance(value, expected_type) for value in values
    ):
        raise TypeError(f"{name} must be a tuple of {expected_type.__name__}")
    keys: list[str] = []
    for value in values:
        if value.units <= 0:
            raise ValueError(f"{name} entries must be positive")
        keys.append(
            value.currency if isinstance(value, Money) else value.instrument_id
        )
    if len(keys) != len(set(keys)):
        raise ValueError(f"{name} contains a duplicate resource dimension")


def _sorted_money(values: tuple[Money, ...]) -> tuple[Money, ...]:
    return tuple(sorted(values, key=_money_key))


def _sorted_quantity(values: tuple[Quantity, ...]) -> tuple[Quantity, ...]:
    return tuple(sorted(values, key=_quantity_key))


@dataclass(frozen=True, slots=True)
class ReservationCommitment:
    """Exact resource units reserved for one remaining Order commitment."""

    cash: tuple[Money, ...] = ()
    sellable_quantities: tuple[Quantity, ...] = ()
    margin: tuple[Money, ...] = ()
    fee_reserve: tuple[Money, ...] = ()
    order_capacity_units: int = 0
    exposure_capacity: tuple[Money, ...] = ()

    def __post_init__(self) -> None:
        _validate_values("cash", self.cash, Money)
        _validate_values(
            "sellable_quantities", self.sellable_quantities, Quantity
        )
        _validate_values("margin", self.margin, Money)
        _validate_values("fee_reserve", self.fee_reserve, Money)
        _validate_values("exposure_capacity", self.exposure_capacity, Money)
        if isinstance(self.order_capacity_units, bool) or not isinstance(
            self.order_capacity_units, int
        ):
            raise TypeError("order_capacity_units must be an integer")
        if self.order_capacity_units < 0:
            raise ValueError("order_capacity_units must be non-negative")
        object.__setattr__(self, "cash", _sorted_money(self.cash))
        object.__setattr__(
            self,
            "sellable_quantities",
            _sorted_quantity(self.sellable_quantities),
        )
        object.__setattr__(self, "margin", _sorted_money(self.margin))
        object.__setattr__(self, "fee_reserve", _sorted_money(self.fee_reserve))
        object.__setattr__(
            self,
            "exposure_capacity",
            _sorted_money(self.exposure_capacity),
        )

    @classmethod
    def empty(cls) -> ReservationCommitment:
        return cls()

    @property
    def is_empty(self) -> bool:
        return not (
            self.cash
            or self.sellable_quantities
            or self.margin
            or self.fee_reserve
            or self.order_capacity_units
            or self.exposure_capacity
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "reservation_commitment",
            "schema_version": 1,
            "cash": self.cash,
            "sellable_quantities": self.sellable_quantities,
            "margin": self.margin,
            "fee_reserve": self.fee_reserve,
            "order_capacity_units": self.order_capacity_units,
            "exposure_capacity": self.exposure_capacity,
        }


@dataclass(frozen=True, slots=True)
class OrderReservationUpdate:
    """Supplied exact commitment after one accepted/active/partial event."""

    order_id: DomainId
    event_id: str
    event_type: OrderEventType
    remaining_quantity: Quantity
    commitment: ReservationCommitment
    source_evidence_hash: str

    def __post_init__(self) -> None:
        _require_order_id("order_id", self.order_id)
        _require_text("event_id", self.event_id)
        if self.event_type not in _ACTIVATION_EVENTS | {
            OrderEventType.ORDER_PARTIALLY_FILLED
        }:
            raise ReservationEvidenceError(
                "reservation update event_type must be accepted, activated, or partial"
            )
        if not isinstance(self.remaining_quantity, Quantity):
            raise TypeError("remaining_quantity must be Quantity")
        if self.remaining_quantity.units <= 0:
            raise ValueError("remaining_quantity must be positive")
        if not isinstance(self.commitment, ReservationCommitment):
            raise TypeError("commitment must be ReservationCommitment")
        if self.commitment.is_empty:
            raise ValueError("reservation update commitment cannot be empty")
        _require_hash("source_evidence_hash", self.source_evidence_hash)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_reservation_update",
            "order_id": self.order_id,
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "remaining_quantity": self.remaining_quantity,
            "commitment": self.commitment,
            "source_evidence_hash": self.source_evidence_hash,
        }


@dataclass(frozen=True, slots=True)
class OrderReservationSchedule:
    """Immutable supplied proposal/update evidence for one Order."""

    order_id: DomainId
    source_proposal_hash: str
    updates: tuple[OrderReservationUpdate, ...]

    def __post_init__(self) -> None:
        _require_order_id("order_id", self.order_id)
        _require_hash("source_proposal_hash", self.source_proposal_hash)
        if not isinstance(self.updates, tuple) or not all(
            isinstance(update, OrderReservationUpdate) for update in self.updates
        ):
            raise TypeError("updates must be a tuple of OrderReservationUpdate")
        ordered = tuple(sorted(self.updates, key=lambda update: update.event_id))
        if any(update.order_id != self.order_id for update in ordered):
            raise ReservationEvidenceError("reservation update Order identity mismatch")
        event_ids = tuple(update.event_id for update in ordered)
        if len(event_ids) != len(set(event_ids)):
            raise ReservationEvidenceError("duplicate reservation update Event identity")
        object.__setattr__(self, "updates", ordered)

    @property
    def schedule_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_reservation_schedule",
            "schema_version": 1,
            "order_id": self.order_id,
            "source_proposal_hash": self.source_proposal_hash,
            "updates": self.updates,
        }


@dataclass(frozen=True, slots=True)
class ActiveOrderReservation:
    account_id: str
    order_id: DomainId
    last_update_event_id: str
    remaining_quantity: Quantity
    commitment: ReservationCommitment
    source_proposal_hash: str

    def __post_init__(self) -> None:
        _require_text("account_id", self.account_id)
        _require_order_id("order_id", self.order_id)
        _require_text("last_update_event_id", self.last_update_event_id)
        if not isinstance(self.remaining_quantity, Quantity):
            raise TypeError("remaining_quantity must be Quantity")
        if self.remaining_quantity.units <= 0:
            raise ValueError("active reservation remaining_quantity must be positive")
        if not isinstance(self.commitment, ReservationCommitment):
            raise TypeError("commitment must be ReservationCommitment")
        if self.commitment.is_empty:
            raise ValueError("active reservation commitment cannot be empty")
        _require_hash("source_proposal_hash", self.source_proposal_hash)

    @property
    def reservation_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "active_order_reservation",
            "account_id": self.account_id,
            "order_id": self.order_id,
            "last_update_event_id": self.last_update_event_id,
            "remaining_quantity": self.remaining_quantity,
            "commitment": self.commitment,
            "source_proposal_hash": self.source_proposal_hash,
        }


@dataclass(frozen=True, slots=True)
class OrderReservationCursor:
    order_id: DomainId
    event_count: int
    stream_hash: str
    evidence_prefix_hash: str | None

    def __post_init__(self) -> None:
        _require_order_id("order_id", self.order_id)
        if isinstance(self.event_count, bool) or not isinstance(self.event_count, int):
            raise TypeError("event_count must be an integer")
        if self.event_count < 0:
            raise ValueError("event_count must be non-negative")
        _require_hash("stream_hash", self.stream_hash)
        if self.evidence_prefix_hash is not None:
            _require_hash("evidence_prefix_hash", self.evidence_prefix_hash)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_reservation_cursor",
            "order_id": self.order_id,
            "event_count": self.event_count,
            "stream_hash": self.stream_hash,
            "evidence_prefix_hash": self.evidence_prefix_hash,
        }


_ReservationValueT = TypeVar("_ReservationValueT", Money, Quantity)


def _aggregate_values(
    values: Iterable[_ReservationValueT],
    expected_type: type[_ReservationValueT],
) -> tuple[_ReservationValueT, ...]:
    totals: dict[str, _ReservationValueT] = {}
    for value in values:
        if not isinstance(value, expected_type):
            raise TypeError(f"reservation total must contain {expected_type.__name__}")
        key = value.currency if isinstance(value, Money) else value.instrument_id
        previous = totals.get(key)
        if previous is None:
            totals[key] = value
            continue
        if previous.scale != value.scale:
            raise ReservationEvidenceError(
                f"resource dimension {key} uses inconsistent Scale"
            )
        totals[key] = previous + value
    return tuple(totals[key] for key in sorted(totals))


def _aggregate_commitments(
    reservations: tuple[ActiveOrderReservation, ...],
) -> ReservationCommitment:
    commitments = tuple(reservation.commitment for reservation in reservations)
    cash = _aggregate_values(
        (value for commitment in commitments for value in commitment.cash), Money
    )
    sellable = _aggregate_values(
        (
            value
            for commitment in commitments
            for value in commitment.sellable_quantities
        ),
        Quantity,
    )
    margin = _aggregate_values(
        (value for commitment in commitments for value in commitment.margin), Money
    )
    fees = _aggregate_values(
        (value for commitment in commitments for value in commitment.fee_reserve),
        Money,
    )
    exposure = _aggregate_values(
        (
            value
            for commitment in commitments
            for value in commitment.exposure_capacity
        ),
        Money,
    )
    return ReservationCommitment(
        cash=cash,
        sellable_quantities=sellable,
        margin=margin,
        fee_reserve=fees,
        order_capacity_units=sum(
            commitment.order_capacity_units for commitment in commitments
        ),
        exposure_capacity=exposure,
    )


@dataclass(frozen=True, slots=True)
class ResourceReservationState:
    account_id: str
    cursors: tuple[OrderReservationCursor, ...]
    active_reservations: tuple[ActiveOrderReservation, ...]
    totals: ReservationCommitment

    def __post_init__(self) -> None:
        _require_text("account_id", self.account_id)
        if not isinstance(self.cursors, tuple) or not all(
            isinstance(cursor, OrderReservationCursor) for cursor in self.cursors
        ):
            raise TypeError("cursors must be a tuple of OrderReservationCursor")
        if not isinstance(self.active_reservations, tuple) or not all(
            isinstance(reservation, ActiveOrderReservation)
            for reservation in self.active_reservations
        ):
            raise TypeError(
                "active_reservations must be a tuple of ActiveOrderReservation"
            )
        if not isinstance(self.totals, ReservationCommitment):
            raise TypeError("totals must be ReservationCommitment")
        cursors = tuple(sorted(self.cursors, key=lambda value: value.order_id.value))
        active = tuple(
            sorted(self.active_reservations, key=lambda value: value.order_id.value)
        )
        cursor_ids = tuple(cursor.order_id.value for cursor in cursors)
        active_ids = tuple(reservation.order_id.value for reservation in active)
        if len(cursor_ids) != len(set(cursor_ids)):
            raise ReservationEvidenceError("duplicate reservation cursor Order identity")
        if len(active_ids) != len(set(active_ids)):
            raise ReservationEvidenceError("duplicate active reservation Order identity")
        if not set(active_ids).issubset(cursor_ids):
            raise ReservationEvidenceError("active reservation is missing its cursor")
        if any(reservation.account_id != self.account_id for reservation in active):
            raise ReservationEvidenceError("active reservation account mismatch")
        expected_totals = _aggregate_commitments(active)
        if self.totals != expected_totals:
            raise ReservationEvidenceError(
                "reservation totals do not equal active Order commitments"
            )
        object.__setattr__(self, "cursors", cursors)
        object.__setattr__(self, "active_reservations", active)

    @property
    def state_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "resource_reservation_state",
            "schema_version": 1,
            "account_id": self.account_id,
            "cursors": self.cursors,
            "active_reservations": self.active_reservations,
            "totals": self.totals,
        }


def _dimension_map(
    values: tuple[Money, ...] | tuple[Quantity, ...],
) -> dict[str, Money | Quantity]:
    return {
        value.currency if isinstance(value, Money) else value.instrument_id: value
        for value in values
    }


def _validate_nonincreasing(
    previous: ReservationCommitment,
    replacement: ReservationCommitment,
) -> None:
    for name in (
        "cash",
        "sellable_quantities",
        "margin",
        "fee_reserve",
        "exposure_capacity",
    ):
        before = _dimension_map(getattr(previous, name))
        after = _dimension_map(getattr(replacement, name))
        introduced = set(after) - set(before)
        if introduced:
            raise ReservationEvidenceError(
                f"Partial Fill cannot introduce {name} resource dimension"
            )
        for key, value in after.items():
            prior = before[key]
            if type(prior) is not type(value) or prior.scale != value.scale:
                raise ReservationEvidenceError(
                    f"Partial Fill {name} resource identity/Scale mismatch"
                )
            if value.units > prior.units:
                raise ReservationEvidenceError(
                    f"Partial Fill cannot increase {name} reservation"
                )
    if replacement.order_capacity_units > previous.order_capacity_units:
        raise ReservationEvidenceError(
            "Partial Fill cannot increase order_capacity reservation"
        )


def _evidence_prefix_hash(
    schedule: OrderReservationSchedule,
    updates: tuple[OrderReservationUpdate, ...],
) -> str:
    return canonical_sha256(
        {
            "type": "order_reservation_evidence_prefix",
            "schema_version": 1,
            "order_id": schedule.order_id,
            "source_proposal_hash": schedule.source_proposal_hash,
            "updates": tuple(sorted(updates, key=lambda value: value.event_id)),
        }
    )


@dataclass(frozen=True, slots=True)
class ResourceReservationBook:
    """Pure account-level projection of Order streams and supplied commitments."""

    account_id: str

    def __post_init__(self) -> None:
        _require_text("account_id", self.account_id)

    def project(
        self,
        streams: Iterable[OrderEventStream],
        schedules: Iterable[OrderReservationSchedule],
    ) -> ResourceReservationState:
        stream_tuple = tuple(streams)
        schedule_tuple = tuple(schedules)
        if not all(isinstance(stream, OrderEventStream) for stream in stream_tuple):
            raise TypeError("streams must contain OrderEventStream values")
        if not all(
            isinstance(schedule, OrderReservationSchedule)
            for schedule in schedule_tuple
        ):
            raise TypeError("schedules must contain OrderReservationSchedule values")

        stream_by_order: dict[str, OrderEventStream] = {}
        for stream in stream_tuple:
            order_id = stream.order.order_id.value
            if order_id in stream_by_order:
                raise ReservationEvidenceError("duplicate Order Event stream")
            if stream.order.account_id != self.account_id:
                raise ReservationEvidenceError("Order stream account mismatch")
            stream_by_order[order_id] = stream

        schedule_by_order: dict[str, OrderReservationSchedule] = {}
        for schedule_item in schedule_tuple:
            order_id = schedule_item.order_id.value
            if order_id in schedule_by_order:
                raise ReservationEvidenceError("duplicate Order reservation schedule")
            schedule_by_order[order_id] = schedule_item

        extra_schedules = set(schedule_by_order) - set(stream_by_order)
        if extra_schedules:
            raise ReservationEvidenceError("reservation schedule has no Order stream")

        active: list[ActiveOrderReservation] = []
        cursors: list[OrderReservationCursor] = []
        for order_id in sorted(stream_by_order):
            stream = stream_by_order[order_id]
            schedule = schedule_by_order.get(order_id)
            reservation, used_updates = self._project_order(stream, schedule)
            if reservation is not None:
                active.append(reservation)
            cursors.append(
                OrderReservationCursor(
                    order_id=stream.order.order_id,
                    event_count=stream.event_count,
                    stream_hash=stream.stream_hash,
                    evidence_prefix_hash=(
                        None
                        if schedule is None
                        else _evidence_prefix_hash(schedule, used_updates)
                    ),
                )
            )

        active_tuple = tuple(active)
        return ResourceReservationState(
            account_id=self.account_id,
            cursors=tuple(cursors),
            active_reservations=active_tuple,
            totals=_aggregate_commitments(active_tuple),
        )

    def resume(
        self,
        prior_state: ResourceReservationState,
        streams: Iterable[OrderEventStream],
        schedules: Iterable[OrderReservationSchedule],
    ) -> ResourceReservationState:
        if not isinstance(prior_state, ResourceReservationState):
            raise TypeError("prior_state must be ResourceReservationState")
        if prior_state.account_id != self.account_id:
            raise ReservationStateMismatchError("prior state account mismatch")
        stream_tuple = tuple(streams)
        schedule_tuple = tuple(schedules)
        stream_by_order = {stream.order.order_id.value: stream for stream in stream_tuple}
        schedule_by_order = {
            schedule.order_id.value: schedule for schedule in schedule_tuple
        }
        if len(stream_by_order) != len(stream_tuple):
            raise ReservationEvidenceError("duplicate Order Event stream")
        if len(schedule_by_order) != len(schedule_tuple):
            raise ReservationEvidenceError("duplicate Order reservation schedule")

        prefix_streams: list[OrderEventStream] = []
        prefix_schedules: list[OrderReservationSchedule] = []
        for cursor in prior_state.cursors:
            stream = stream_by_order.get(cursor.order_id.value)
            if stream is None or cursor.event_count > stream.event_count:
                raise ReservationStateMismatchError(
                    "prior state cursor has no matching full Order stream"
                )
            prefix = OrderEventStream(
                stream.order,
                stream.records[: cursor.event_count],
            )
            if prefix.stream_hash != cursor.stream_hash:
                raise ReservationStateMismatchError(
                    "prior state cursor does not match Order stream prefix"
                )
            prefix_streams.append(prefix)
            schedule = schedule_by_order.get(cursor.order_id.value)
            if schedule is not None:
                visible_event_ids = {
                    record.event.event_id for record in prefix.records
                }
                visible_updates = tuple(
                    update
                    for update in schedule.updates
                    if update.event_id in visible_event_ids
                    or update.event_type in _ACTIVATION_EVENTS
                )
                prefix_schedules.append(
                    OrderReservationSchedule(
                        order_id=schedule.order_id,
                        source_proposal_hash=schedule.source_proposal_hash,
                        updates=visible_updates,
                    )
                )

        try:
            rebuilt_prior = self.project(prefix_streams, prefix_schedules)
        except ResourceReservationError as error:
            raise ReservationStateMismatchError(
                "prior state cannot be rebuilt from supplied prefixes"
            ) from error
        if rebuilt_prior != prior_state:
            raise ReservationStateMismatchError(
                "prior state does not equal supplied stream-prefix projection"
            )
        return self.project(stream_tuple, schedule_tuple)

    def _project_order(
        self,
        stream: OrderEventStream,
        schedule: OrderReservationSchedule | None,
    ) -> tuple[ActiveOrderReservation | None, tuple[OrderReservationUpdate, ...]]:
        records_by_id = {record.event.event_id: record for record in stream.records}
        accepted_or_active_ids = {
            record.event.event_id
            for record in stream.records
            if record.event.event_type in _ACTIVATION_EVENTS
        }
        partial_ids = {
            record.event.event_id
            for record in stream.records
            if record.event.event_type
            is OrderEventType.ORDER_PARTIALLY_FILLED
        }
        has_reservable_event = bool(accepted_or_active_ids or partial_ids)
        if schedule is None:
            if has_reservable_event:
                raise ReservationEvidenceError(
                    "accepted/active Order is missing reservation schedule"
                )
            return None, ()
        if schedule.order_id != stream.order.order_id:
            raise ReservationEvidenceError("reservation schedule Order mismatch")

        updates_by_event = {update.event_id: update for update in schedule.updates}
        known_update_ids = set(updates_by_event) & set(records_by_id)
        eligible_ids = accepted_or_active_ids | partial_ids
        ineligible = known_update_ids - eligible_ids
        if ineligible:
            raise ReservationEvidenceError(
                "reservation update is not bound to an eligible Order Event"
            )
        for event_id in known_update_ids:
            if updates_by_event[event_id].event_type is not records_by_id[
                event_id
            ].event.event_type:
                raise ReservationEvidenceError(
                    "reservation update Event type does not match Order Event"
                )
        unknown_update_ids = set(updates_by_event) - set(records_by_id)
        if stream.state is not None and stream.state.status in _TERMINAL_STATUSES:
            if unknown_update_ids:
                raise ReservationEvidenceError(
                    "terminal Order schedule contains extra reservation update"
                )

        activation_ids = {
            update.event_id
            for update in schedule.updates
            if update.event_type in _ACTIVATION_EVENTS
        }
        if len(activation_ids) != 1:
            raise ReservationEvidenceError(
                "reservation schedule requires exactly one activation update"
            )
        missing_partial = partial_ids - set(updates_by_event)
        if missing_partial:
            raise ReservationEvidenceError(
                "every Partial Fill requires an exact reservation update"
            )

        current: ActiveOrderReservation | None = None
        used_updates: list[OrderReservationUpdate] = []
        activation_id = next(iter(activation_ids), None)
        for position, record in enumerate(stream.records, start=1):
            event = record.event
            update = updates_by_event.get(event.event_id)
            if update is not None:
                state = stream.state_at(position)
                if state is None or update.remaining_quantity != state.remaining_quantity:
                    raise ReservationEvidenceError(
                        "reservation update remaining Quantity mismatch"
                    )
                if update.remaining_quantity.instrument_id != str(
                    stream.order.intent.instrument_id
                ):
                    raise ReservationEvidenceError(
                        "reservation update Quantity Instrument mismatch"
                    )
                if event.event_id == activation_id:
                    current = ActiveOrderReservation(
                        account_id=self.account_id,
                        order_id=stream.order.order_id,
                        last_update_event_id=event.event_id,
                        remaining_quantity=update.remaining_quantity,
                        commitment=update.commitment,
                        source_proposal_hash=schedule.source_proposal_hash,
                    )
                elif event.event_type is OrderEventType.ORDER_PARTIALLY_FILLED:
                    if current is None:
                        raise ReservationEvidenceError(
                            "Partial Fill reservation update precedes activation"
                        )
                    _validate_nonincreasing(current.commitment, update.commitment)
                    current = ActiveOrderReservation(
                        account_id=self.account_id,
                        order_id=stream.order.order_id,
                        last_update_event_id=event.event_id,
                        remaining_quantity=update.remaining_quantity,
                        commitment=update.commitment,
                        source_proposal_hash=schedule.source_proposal_hash,
                    )
                used_updates.append(update)

            state = stream.state_at(position)
            if state is not None and state.status in _TERMINAL_STATUSES:
                current = None

        final_state = stream.state
        if (
            final_state is not None
            and final_state.status not in _TERMINAL_STATUSES
            and activation_id in records_by_id
            and current is None
        ):
            raise ReservationEvidenceError(
                "accepted/active Order has no activated reservation"
            )
        return current, tuple(used_updates)
