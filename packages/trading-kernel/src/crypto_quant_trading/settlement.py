"""Immutable settlement lifecycle and available-resource projection."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Self

from crypto_quant_domain import (
    CashBalanceKey,
    DomainId,
    DomainIdKind,
    Money,
    PositionBalanceKey,
    Quantity,
    Scale,
    SettlementObligation,
    SimulationInstant,
    canonical_bytes,
    canonical_sha256,
)

from .ledger import LedgerState, UnregisteredBalanceKeyError
from .reservations import ReservationCommitment, ResourceReservationState


_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SETTLEMENT_GENESIS_HASH = canonical_sha256(
    {"type": "settlement_book_genesis", "schema_version": 1}
)


class SettlementBookError(Exception):
    """Base class for deterministic settlement-book failures."""


class SettlementEventConflictError(SettlementBookError):
    """Raised when one obligation or event identity names different content."""


class SettlementLifecycleError(SettlementBookError):
    """Raised when settlement evidence violates its lifecycle."""


class SettlementStateMismatchError(SettlementBookError):
    """Raised when a supplied settlement state is not a verified prefix."""


class AvailabilityProjectionError(Exception):
    """Base class for deterministic availability projection failures."""


class AvailabilityEvidenceError(AvailabilityProjectionError):
    """Raised when supplied ledger, settlement, reservation, or rule evidence conflicts."""


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)


def _require_positive_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 digest")


def _require_settlement_id(name: str, value: DomainId) -> None:
    if not isinstance(value, DomainId) or value.kind is not DomainIdKind.SETTLEMENT:
        raise TypeError(f"{name} must be a SETTLEMENT DomainId")


class SettlementEventType(str, Enum):
    OBLIGATION_RECORDED = "settlement_obligation_recorded"
    SETTLEMENT_APPLIED = "settlement_applied"


@dataclass(frozen=True, slots=True)
class AccountSettlementObligation:
    """A Domain obligation explicitly bound to one account balance dimension."""

    obligation: SettlementObligation
    balance_key: CashBalanceKey | PositionBalanceKey

    def __post_init__(self) -> None:
        if not isinstance(self.obligation, SettlementObligation):
            raise TypeError("obligation must be SettlementObligation")
        if isinstance(self.balance_key, CashBalanceKey):
            if self.obligation.amount is None or self.obligation.currency_id is None:
                raise SettlementLifecycleError(
                    "Cash balance key requires a Currency settlement obligation"
                )
            if (
                self.obligation.instrument_id is not None
                or self.obligation.quantity is not None
                or self.obligation.currency_id != self.balance_key.currency_id
                or self.obligation.amount.currency != str(self.balance_key.currency_id)
            ):
                raise SettlementLifecycleError(
                    "settlement obligation Cash balance key mismatch"
                )
        elif isinstance(self.balance_key, PositionBalanceKey):
            if self.obligation.quantity is None or self.obligation.instrument_id is None:
                raise SettlementLifecycleError(
                    "Position balance key requires an Instrument settlement obligation"
                )
            if (
                self.obligation.currency_id is not None
                or self.obligation.amount is not None
                or self.obligation.instrument_id != self.balance_key.instrument_id
                or self.obligation.quantity.instrument_id
                != str(self.balance_key.instrument_id)
            ):
                raise SettlementLifecycleError(
                    "settlement obligation Position balance key mismatch"
                )
        else:
            raise TypeError("balance_key must be CashBalanceKey or PositionBalanceKey")

    @property
    def account_id(self) -> str:
        return self.balance_key.account_id

    @property
    def units(self) -> int:
        value = self.obligation.amount or self.obligation.quantity
        if value is None:  # pragma: no cover - protected by construction
            raise SettlementLifecycleError("settlement obligation has no value")
        return value.units

    @property
    def value(self) -> Money | Quantity:
        value = self.obligation.amount or self.obligation.quantity
        if value is None:  # pragma: no cover - protected by construction
            raise SettlementLifecycleError("settlement obligation has no value")
        return value

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "account_settlement_obligation",
            "obligation": self.obligation,
            "balance_key": self.balance_key,
        }


@dataclass(frozen=True, slots=True)
class SettlementEvent:
    event_id: str
    settlement_obligation_id: DomainId
    event_type: SettlementEventType
    occurred_at: SimulationInstant
    causation_id: str
    source_evidence_hash: str

    def __post_init__(self) -> None:
        _require_text("event_id", self.event_id)
        _require_settlement_id(
            "settlement_obligation_id", self.settlement_obligation_id
        )
        if not isinstance(self.event_type, SettlementEventType):
            raise TypeError("event_type must be SettlementEventType")
        if not isinstance(self.occurred_at, SimulationInstant):
            raise TypeError("occurred_at must be SimulationInstant")
        _require_text("causation_id", self.causation_id)
        _require_hash("source_evidence_hash", self.source_evidence_hash)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "settlement_event",
            "event_id": self.event_id,
            "settlement_obligation_id": self.settlement_obligation_id,
            "event_type": self.event_type.value,
            "occurred_at": self.occurred_at,
            "causation_id": self.causation_id,
            "source_evidence_hash": self.source_evidence_hash,
        }


def _event_key(event: SettlementEvent) -> tuple[SimulationInstant, str]:
    return event.occurred_at, event.event_id


def _settlement_link_hash(
    previous_hash: str,
    event: SettlementEvent,
    obligation: AccountSettlementObligation | None,
) -> str:
    return canonical_sha256(
        {
            "type": "settlement_book_link",
            "schema_version": 1,
            "previous_hash": previous_hash,
            "event": event,
            "recorded_obligation": obligation,
        }
    )


@dataclass(frozen=True, slots=True)
class SettlementBookCursor:
    position: int
    prefix_hash: str

    def __post_init__(self) -> None:
        if isinstance(self.position, bool) or not isinstance(self.position, int):
            raise TypeError("SettlementBookCursor position must be an integer")
        if self.position < 0:
            raise ValueError("SettlementBookCursor position must be non-negative")
        _require_hash("SettlementBookCursor prefix_hash", self.prefix_hash)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "settlement_book_cursor",
            "position": self.position,
            "prefix_hash": self.prefix_hash,
        }


@dataclass(frozen=True, slots=True)
class SettlementBookState:
    account_id: str
    cursor: SettlementBookCursor
    pending_obligations: tuple[AccountSettlementObligation, ...]
    applied_obligations: tuple[AccountSettlementObligation, ...]

    def __post_init__(self) -> None:
        _require_text("account_id", self.account_id)
        if not isinstance(self.cursor, SettlementBookCursor):
            raise TypeError("cursor must be SettlementBookCursor")
        for name, values in (
            ("pending_obligations", self.pending_obligations),
            ("applied_obligations", self.applied_obligations),
        ):
            if not isinstance(values, tuple) or not all(
                isinstance(value, AccountSettlementObligation) for value in values
            ):
                raise TypeError(f"{name} must contain AccountSettlementObligation")
            ordered = tuple(
                sorted(
                    values,
                    key=lambda value: value.obligation.settlement_obligation_id.value,
                )
            )
            if values != ordered:
                raise SettlementLifecycleError(f"{name} must use canonical order")
            identities = tuple(
                value.obligation.settlement_obligation_id.value for value in values
            )
            if len(identities) != len(set(identities)):
                raise SettlementLifecycleError(f"duplicate identity in {name}")
            if any(value.account_id != self.account_id for value in values):
                raise SettlementLifecycleError(f"{name} account mismatch")
        pending_ids = {
            value.obligation.settlement_obligation_id.value
            for value in self.pending_obligations
        }
        applied_ids = {
            value.obligation.settlement_obligation_id.value
            for value in self.applied_obligations
        }
        if pending_ids & applied_ids:
            raise SettlementLifecycleError(
                "settlement obligation cannot be pending and applied"
            )

    @property
    def state_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "settlement_book_state",
            "schema_version": 1,
            "account_id": self.account_id,
            "cursor": self.cursor,
            "pending_obligations": self.pending_obligations,
            "applied_obligations": self.applied_obligations,
        }


@dataclass(frozen=True, slots=True)
class SettlementBook:
    """Immutable account-local settlement evidence and replay."""

    account_id: str
    obligations: tuple[AccountSettlementObligation, ...] = ()
    events: tuple[SettlementEvent, ...] = ()
    _prefix_hashes: tuple[str, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _require_text("account_id", self.account_id)
        if not isinstance(self.obligations, tuple) or not all(
            isinstance(value, AccountSettlementObligation) for value in self.obligations
        ):
            raise TypeError("obligations must contain AccountSettlementObligation")
        if not isinstance(self.events, tuple) or not all(
            isinstance(value, SettlementEvent) for value in self.events
        ):
            raise TypeError("events must contain SettlementEvent")
        ordered_obligations = tuple(
            sorted(
                self.obligations,
                key=lambda value: value.obligation.settlement_obligation_id.value,
            )
        )
        if self.obligations != ordered_obligations:
            raise SettlementLifecycleError("obligations must use canonical order")
        obligation_ids = tuple(
            value.obligation.settlement_obligation_id.value
            for value in self.obligations
        )
        if len(obligation_ids) != len(set(obligation_ids)):
            raise SettlementLifecycleError("duplicate settlement obligation identity")
        if any(value.account_id != self.account_id for value in self.obligations):
            raise SettlementLifecycleError("settlement obligation account mismatch")

        obligation_by_id = {
            value.obligation.settlement_obligation_id.value: value
            for value in self.obligations
        }
        event_ids: set[str] = set()
        recorded_by_obligation: dict[str, SettlementEvent] = {}
        applied_obligations: set[str] = set()
        previous_key: tuple[SimulationInstant, str] | None = None
        prefix_hashes = [_SETTLEMENT_GENESIS_HASH]
        for event in self.events:
            key = _event_key(event)
            if previous_key is not None and key <= previous_key:
                raise SettlementLifecycleError(
                    "SettlementBook events must use strict stable order"
                )
            previous_key = key
            if event.event_id in event_ids:
                raise SettlementLifecycleError("duplicate Settlement Event identity")
            event_ids.add(event.event_id)
            obligation_id = event.settlement_obligation_id.value
            registered = obligation_by_id.get(obligation_id)
            if registered is None:
                raise SettlementLifecycleError(
                    "Settlement Event references unknown obligation"
                )
            obligation = registered.obligation
            if event.event_type is SettlementEventType.OBLIGATION_RECORDED:
                if obligation_id in recorded_by_obligation:
                    raise SettlementLifecycleError(
                        "settlement obligation has multiple recorded events"
                    )
                if event.occurred_at.instant != obligation.trade_time:
                    raise SettlementLifecycleError(
                        "recorded event must occur at obligation trade_time"
                    )
                if event.causation_id != obligation.source_fill_id.value:
                    raise SettlementLifecycleError(
                        "recorded event causation must reference source Fill"
                    )
                recorded_by_obligation[obligation_id] = event
                link_obligation: AccountSettlementObligation | None = registered
            else:
                recorded = recorded_by_obligation.get(obligation_id)
                if recorded is None:
                    raise SettlementLifecycleError(
                        "Settlement Applied has unknown or forward recorded causation"
                    )
                if obligation_id in applied_obligations:
                    raise SettlementLifecycleError("settlement obligation already applied")
                if event.occurred_at.instant < obligation.settlement_time:
                    raise SettlementLifecycleError(
                        "Settlement Applied occurred before settlement_time"
                    )
                if event.causation_id != recorded.event_id:
                    raise SettlementLifecycleError(
                        "Settlement Applied causation must reference recorded event"
                    )
                applied_obligations.add(obligation_id)
                link_obligation = None
            prefix_hashes.append(
                _settlement_link_hash(prefix_hashes[-1], event, link_obligation)
            )

        if set(obligation_by_id) != set(recorded_by_obligation):
            raise SettlementLifecycleError(
                "every settlement obligation requires one recorded event"
            )
        object.__setattr__(self, "_prefix_hashes", tuple(prefix_hashes))

    @classmethod
    def from_events(
        cls,
        account_id: str,
        obligations: Iterable[AccountSettlementObligation],
        events: Iterable[SettlementEvent],
    ) -> Self:
        return cls(account_id).append(obligations=obligations, events=events)

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def book_hash(self) -> str:
        return self._prefix_hashes[-1]

    def append(
        self,
        *,
        obligations: Iterable[AccountSettlementObligation] = (),
        events: Iterable[SettlementEvent] = (),
    ) -> Self:
        try:
            candidate_obligations = tuple(obligations)
            candidate_events = tuple(events)
        except TypeError as error:
            raise TypeError("obligations and events must be iterable") from error
        if not all(
            isinstance(value, AccountSettlementObligation)
            for value in candidate_obligations
        ):
            raise TypeError("obligations must contain AccountSettlementObligation")
        if not all(isinstance(value, SettlementEvent) for value in candidate_events):
            raise TypeError("events must contain SettlementEvent")

        existing_obligations = {
            value.obligation.settlement_obligation_id.value: (
                canonical_sha256(value),
                value,
            )
            for value in self.obligations
        }
        pending_obligations: dict[str, AccountSettlementObligation] = {}
        for candidate_obligation in candidate_obligations:
            identity = candidate_obligation.obligation.settlement_obligation_id.value
            content_hash = canonical_sha256(candidate_obligation)
            known_obligation = existing_obligations.get(identity)
            if known_obligation is not None:
                if known_obligation[0] != content_hash:
                    raise SettlementEventConflictError(
                        f"conflicting content for settlement obligation {identity}"
                    )
                continue
            pending_obligation = pending_obligations.get(identity)
            if (
                pending_obligation is not None
                and canonical_sha256(pending_obligation) != content_hash
            ):
                raise SettlementEventConflictError(
                    f"conflicting content for settlement obligation {identity}"
                )
            pending_obligations[identity] = candidate_obligation

        existing_events = {
            value.event_id: (canonical_sha256(value), value) for value in self.events
        }
        pending_events: dict[str, SettlementEvent] = {}
        for candidate_event in candidate_events:
            content_hash = canonical_sha256(candidate_event)
            known_event = existing_events.get(candidate_event.event_id)
            if known_event is not None:
                if known_event[0] != content_hash:
                    raise SettlementEventConflictError(
                        "conflicting content for Settlement Event "
                        f"{candidate_event.event_id}"
                    )
                continue
            pending_event = pending_events.get(candidate_event.event_id)
            if (
                pending_event is not None
                and canonical_sha256(pending_event) != content_hash
            ):
                raise SettlementEventConflictError(
                    "conflicting content for Settlement Event "
                    f"{candidate_event.event_id}"
                )
            pending_events[candidate_event.event_id] = candidate_event

        if not pending_obligations and not pending_events:
            return self
        ordered_events = tuple(sorted(pending_events.values(), key=_event_key))
        if self.events and ordered_events and _event_key(ordered_events[0]) <= _event_key(
            self.events[-1]
        ):
            raise SettlementLifecycleError(
                "append would insert before the published prefix boundary"
            )
        all_obligations = tuple(
            sorted(
                self.obligations + tuple(pending_obligations.values()),
                key=lambda value: value.obligation.settlement_obligation_id.value,
            )
        )
        return type(self)(self.account_id, all_obligations, self.events + ordered_events)

    def cursor_at(self, position: int) -> SettlementBookCursor:
        if isinstance(position, bool) or not isinstance(position, int):
            raise TypeError("cursor position must be an integer")
        if not 0 <= position <= self.event_count:
            raise SettlementStateMismatchError("cursor is outside SettlementBook range")
        return SettlementBookCursor(position, self._prefix_hashes[position])

    def _validate_cursor(self, cursor: SettlementBookCursor) -> None:
        if not isinstance(cursor, SettlementBookCursor):
            raise TypeError("cursor must be SettlementBookCursor")
        if cursor.position > self.event_count:
            raise SettlementStateMismatchError("cursor is outside SettlementBook range")
        if self._prefix_hashes[cursor.position] != cursor.prefix_hash:
            raise SettlementStateMismatchError("cursor prefix hash mismatch")

    def project(
        self, *, stop: SettlementBookCursor | None = None
    ) -> SettlementBookState:
        cursor = self.cursor_at(self.event_count) if stop is None else stop
        self._validate_cursor(cursor)
        obligations = {
            value.obligation.settlement_obligation_id.value: value
            for value in self.obligations
        }
        pending: dict[str, AccountSettlementObligation] = {}
        applied: dict[str, AccountSettlementObligation] = {}
        for event in self.events[: cursor.position]:
            identity = event.settlement_obligation_id.value
            registered = obligations[identity]
            if event.event_type is SettlementEventType.OBLIGATION_RECORDED:
                pending[identity] = registered
            else:
                pending.pop(identity)
                applied[identity] = registered
        return SettlementBookState(
            account_id=self.account_id,
            cursor=cursor,
            pending_obligations=tuple(pending[key] for key in sorted(pending)),
            applied_obligations=tuple(applied[key] for key in sorted(applied)),
        )

    def resume(
        self,
        prior_state: SettlementBookState,
        *,
        stop: SettlementBookCursor | None = None,
    ) -> SettlementBookState:
        if not isinstance(prior_state, SettlementBookState):
            raise TypeError("prior_state must be SettlementBookState")
        if prior_state.account_id != self.account_id:
            raise SettlementStateMismatchError("prior state account mismatch")
        expected = self.project(stop=prior_state.cursor)
        if expected != prior_state or expected.state_hash != prior_state.state_hash:
            raise SettlementStateMismatchError(
                "prior state does not match SettlementBook prefix"
            )
        target = self.cursor_at(self.event_count) if stop is None else stop
        if target.position < prior_state.cursor.position:
            raise SettlementStateMismatchError("resume stop precedes prior state")
        return self.project(stop=target)


class CashReservationUse(str, Enum):
    CASH = "cash"
    MARGIN = "margin"
    FEE_RESERVE = "fee_reserve"


def _sorted_uses(values: tuple[CashReservationUse, ...]) -> tuple[CashReservationUse, ...]:
    if not isinstance(values, tuple) or not all(
        isinstance(value, CashReservationUse) for value in values
    ):
        raise TypeError("reservation uses must contain CashReservationUse")
    if len(values) != len(set(values)):
        raise ValueError("duplicate Cash reservation use")
    return tuple(sorted(values, key=lambda value: value.value))


@dataclass(frozen=True, slots=True)
class CashAvailabilityRule:
    key: CashBalanceKey
    pending_receivable_tradable: bool
    pending_receivable_withdrawable: bool
    pending_receivable_margin_eligible: bool
    tradable_reservation_uses: tuple[CashReservationUse, ...]
    withdrawable_reservation_uses: tuple[CashReservationUse, ...]
    available_margin_reservation_uses: tuple[CashReservationUse, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.key, CashBalanceKey):
            raise TypeError("key must be CashBalanceKey")
        for name in (
            "pending_receivable_tradable",
            "pending_receivable_withdrawable",
            "pending_receivable_margin_eligible",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        object.__setattr__(
            self,
            "tradable_reservation_uses",
            _sorted_uses(self.tradable_reservation_uses),
        )
        object.__setattr__(
            self,
            "withdrawable_reservation_uses",
            _sorted_uses(self.withdrawable_reservation_uses),
        )
        object.__setattr__(
            self,
            "available_margin_reservation_uses",
            _sorted_uses(self.available_margin_reservation_uses),
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cash_availability_rule",
            "key": self.key,
            "pending_receivable_tradable": self.pending_receivable_tradable,
            "pending_receivable_withdrawable": self.pending_receivable_withdrawable,
            "pending_receivable_margin_eligible": self.pending_receivable_margin_eligible,
            "tradable_reservation_uses": tuple(
                value.value for value in self.tradable_reservation_uses
            ),
            "withdrawable_reservation_uses": tuple(
                value.value for value in self.withdrawable_reservation_uses
            ),
            "available_margin_reservation_uses": tuple(
                value.value for value in self.available_margin_reservation_uses
            ),
        }


@dataclass(frozen=True, slots=True)
class PositionAvailabilityRule:
    key: PositionBalanceKey
    pending_receivable_sellable: bool

    def __post_init__(self) -> None:
        if not isinstance(self.key, PositionBalanceKey):
            raise TypeError("key must be PositionBalanceKey")
        if not isinstance(self.pending_receivable_sellable, bool):
            raise TypeError("pending_receivable_sellable must be bool")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "position_availability_rule",
            "key": self.key,
            "pending_receivable_sellable": self.pending_receivable_sellable,
        }


def _rules_config(
    policy_key: str,
    policy_version: int,
    account_id: str,
    cash_rules: tuple[CashAvailabilityRule, ...],
    position_rules: tuple[PositionAvailabilityRule, ...],
) -> dict[str, Any]:
    return {
        "type": "market_settlement_rules_config",
        "schema_version": 1,
        "policy_key": policy_key,
        "policy_version": policy_version,
        "account_id": account_id,
        "cash_rules": cash_rules,
        "position_rules": position_rules,
    }


@dataclass(frozen=True, slots=True)
class MarketSettlementRules:
    policy_key: str
    policy_version: int
    account_id: str
    cash_rules: tuple[CashAvailabilityRule, ...]
    position_rules: tuple[PositionAvailabilityRule, ...]
    config_hash: str

    def __post_init__(self) -> None:
        _require_text("policy_key", self.policy_key)
        _require_positive_int("policy_version", self.policy_version)
        _require_text("account_id", self.account_id)
        if not isinstance(self.cash_rules, tuple) or not all(
            isinstance(value, CashAvailabilityRule) for value in self.cash_rules
        ):
            raise TypeError("cash_rules must contain CashAvailabilityRule")
        if not isinstance(self.position_rules, tuple) or not all(
            isinstance(value, PositionAvailabilityRule) for value in self.position_rules
        ):
            raise TypeError("position_rules must contain PositionAvailabilityRule")
        cash_rules = tuple(sorted(self.cash_rules, key=lambda value: canonical_bytes(value.key)))
        position_rules = tuple(
            sorted(self.position_rules, key=lambda value: canonical_bytes(value.key))
        )
        if len({value.key for value in cash_rules}) != len(cash_rules):
            raise ValueError("duplicate Cash availability rule")
        if len({value.key for value in position_rules}) != len(position_rules):
            raise ValueError("duplicate Position availability rule")
        if any(value.key.account_id != self.account_id for value in cash_rules):
            raise ValueError("Cash availability rule account mismatch")
        if any(value.key.account_id != self.account_id for value in position_rules):
            raise ValueError("Position availability rule account mismatch")
        _require_hash("config_hash", self.config_hash)
        expected_hash = canonical_sha256(
            _rules_config(
                self.policy_key,
                self.policy_version,
                self.account_id,
                cash_rules,
                position_rules,
            )
        )
        if self.config_hash != expected_hash:
            raise ValueError("config_hash does not match Market Settlement Rules")
        object.__setattr__(self, "cash_rules", cash_rules)
        object.__setattr__(self, "position_rules", position_rules)

    @classmethod
    def create(
        cls,
        *,
        policy_key: str,
        policy_version: int,
        account_id: str,
        cash_rules: tuple[CashAvailabilityRule, ...],
        position_rules: tuple[PositionAvailabilityRule, ...],
    ) -> Self:
        ordered_cash = tuple(sorted(cash_rules, key=lambda value: canonical_bytes(value.key)))
        ordered_position = tuple(
            sorted(position_rules, key=lambda value: canonical_bytes(value.key))
        )
        config_hash = canonical_sha256(
            _rules_config(
                policy_key,
                policy_version,
                account_id,
                ordered_cash,
                ordered_position,
            )
        )
        return cls(
            policy_key,
            policy_version,
            account_id,
            ordered_cash,
            ordered_position,
            config_hash,
        )

    @property
    def rules_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            **_rules_config(
                self.policy_key,
                self.policy_version,
                self.account_id,
                self.cash_rules,
                self.position_rules,
            ),
            "type": "market_settlement_rules",
            "config_hash": self.config_hash,
        }


@dataclass(frozen=True, slots=True)
class CashAvailability:
    key: CashBalanceKey
    total: Money
    settled: Money
    tradable: Money
    withdrawable: Money
    available_margin: Money

    def __post_init__(self) -> None:
        if not isinstance(self.key, CashBalanceKey):
            raise TypeError("key must be CashBalanceKey")
        values = (
            self.total,
            self.settled,
            self.tradable,
            self.withdrawable,
            self.available_margin,
        )
        if not all(isinstance(value, Money) for value in values):
            raise TypeError("Cash availability values must be Money")
        if any(value.currency != str(self.key.currency_id) for value in values):
            raise AvailabilityEvidenceError("Cash availability currency mismatch")
        if len({value.scale for value in values}) != 1:
            raise AvailabilityEvidenceError("Cash availability Scale mismatch")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cash_availability",
            "key": self.key,
            "total": self.total,
            "settled": self.settled,
            "tradable": self.tradable,
            "withdrawable": self.withdrawable,
            "available_margin": self.available_margin,
        }


@dataclass(frozen=True, slots=True)
class PositionAvailability:
    key: PositionBalanceKey
    total: Quantity
    sellable: Quantity

    def __post_init__(self) -> None:
        if not isinstance(self.key, PositionBalanceKey):
            raise TypeError("key must be PositionBalanceKey")
        if not isinstance(self.total, Quantity) or not isinstance(
            self.sellable, Quantity
        ):
            raise TypeError("Position availability values must be Quantity")
        if (
            self.total.instrument_id != str(self.key.instrument_id)
            or self.sellable.instrument_id != str(self.key.instrument_id)
        ):
            raise AvailabilityEvidenceError("Position availability identity mismatch")
        if self.total.scale != self.sellable.scale:
            raise AvailabilityEvidenceError("Position availability Scale mismatch")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "position_availability",
            "key": self.key,
            "total": self.total,
            "sellable": self.sellable,
        }


@dataclass(frozen=True, slots=True)
class AvailabilityState:
    account_id: str
    ledger_state_hash: str
    settlement_state_hash: str
    reservation_state_hash: str
    market_settlement_rules_hash: str
    cash: tuple[CashAvailability, ...]
    positions: tuple[PositionAvailability, ...]

    def __post_init__(self) -> None:
        _require_text("account_id", self.account_id)
        for name in (
            "ledger_state_hash",
            "settlement_state_hash",
            "reservation_state_hash",
            "market_settlement_rules_hash",
        ):
            _require_hash(name, getattr(self, name))
        if not isinstance(self.cash, tuple) or not all(
            isinstance(value, CashAvailability) for value in self.cash
        ):
            raise TypeError("cash must contain CashAvailability")
        if not isinstance(self.positions, tuple) or not all(
            isinstance(value, PositionAvailability) for value in self.positions
        ):
            raise TypeError("positions must contain PositionAvailability")
        if self.cash != tuple(sorted(self.cash, key=lambda value: canonical_bytes(value.key))):
            raise AvailabilityEvidenceError("Cash availability must use canonical order")
        if self.positions != tuple(
            sorted(self.positions, key=lambda value: canonical_bytes(value.key))
        ):
            raise AvailabilityEvidenceError(
                "Position availability must use canonical order"
            )
        if any(value.key.account_id != self.account_id for value in self.cash):
            raise AvailabilityEvidenceError("Cash availability account mismatch")
        if any(value.key.account_id != self.account_id for value in self.positions):
            raise AvailabilityEvidenceError("Position availability account mismatch")

    @property
    def state_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "availability_state",
            "schema_version": 1,
            "account_id": self.account_id,
            "ledger_state_hash": self.ledger_state_hash,
            "settlement_state_hash": self.settlement_state_hash,
            "reservation_state_hash": self.reservation_state_hash,
            "market_settlement_rules_hash": self.market_settlement_rules_hash,
            "cash": self.cash,
            "positions": self.positions,
        }


def _positive_pending(
    obligations: tuple[AccountSettlementObligation, ...],
) -> dict[CashBalanceKey | PositionBalanceKey, Money | Quantity]:
    totals: dict[CashBalanceKey | PositionBalanceKey, Money | Quantity] = {}
    for registered in obligations:
        value = registered.value
        if value.units <= 0:
            continue
        previous = totals.get(registered.balance_key)
        if previous is None:
            totals[registered.balance_key] = value
        else:
            try:
                totals[registered.balance_key] = previous + value  # type: ignore[operator]
            except (TypeError, ValueError) as error:
                raise AvailabilityEvidenceError(
                    "pending settlement identity or Scale mismatch"
                ) from error
    return totals


def _reservation_values(
    commitment: ReservationCommitment,
    use: CashReservationUse,
) -> tuple[Money, ...]:
    return {
        CashReservationUse.CASH: commitment.cash,
        CashReservationUse.MARGIN: commitment.margin,
        CashReservationUse.FEE_RESERVE: commitment.fee_reserve,
    }[use]


def _money_for_currency(
    values: tuple[Money, ...], key: CashBalanceKey, scale: Scale
) -> Money:
    matches = tuple(value for value in values if value.currency == str(key.currency_id))
    if not matches:
        return Money(0, scale, str(key.currency_id))
    if len(matches) != 1 or matches[0].scale != scale:
        raise AvailabilityEvidenceError("reservation Money identity or Scale mismatch")
    return matches[0]


@dataclass(frozen=True, slots=True)
class AvailabilityProjection:
    """Pure projection of typed available resources from supplied evidence."""

    def project(
        self,
        ledger: LedgerState,
        settlement: SettlementBookState,
        reservations: ResourceReservationState,
        rules: MarketSettlementRules,
    ) -> AvailabilityState:
        if not isinstance(ledger, LedgerState):
            raise TypeError("ledger must be LedgerState")
        if not isinstance(settlement, SettlementBookState):
            raise TypeError("settlement must be SettlementBookState")
        if not isinstance(reservations, ResourceReservationState):
            raise TypeError("reservations must be ResourceReservationState")
        if not isinstance(rules, MarketSettlementRules):
            raise TypeError("rules must be MarketSettlementRules")

        registrations = ledger.schema.registrations
        ledger_keys = tuple(registration.key for registration in registrations)
        ledger_accounts = {key.account_id for key in ledger_keys}
        if ledger_accounts != {rules.account_id}:
            raise AvailabilityEvidenceError("Ledger and rules account mismatch")
        if settlement.account_id != rules.account_id:
            raise AvailabilityEvidenceError("Settlement and rules account mismatch")
        if reservations.account_id != rules.account_id:
            raise AvailabilityEvidenceError("Reservation and rules account mismatch")

        cash_keys = {
            key for key in ledger_keys if isinstance(key, CashBalanceKey)
        }
        position_keys = {
            key for key in ledger_keys if isinstance(key, PositionBalanceKey)
        }
        if {rule.key for rule in rules.cash_rules} != cash_keys:
            raise AvailabilityEvidenceError("Cash rule coverage mismatch")
        if {rule.key for rule in rules.position_rules} != position_keys:
            raise AvailabilityEvidenceError("Position rule coverage mismatch")

        for registered in settlement.pending_obligations:
            if registered.balance_key not in set(ledger_keys):
                raise AvailabilityEvidenceError(
                    "pending settlement balance key is unregistered"
                )
            try:
                registration = ledger.schema.registration_for(registered.balance_key)
            except UnregisteredBalanceKeyError as error:  # pragma: no cover - guarded
                raise AvailabilityEvidenceError(
                    "pending settlement balance key is unregistered"
                ) from error
            if registered.value.scale != registration.scale:
                raise AvailabilityEvidenceError(
                    "pending settlement value Scale mismatch"
                )

        self._validate_reservation_owners(reservations.totals, rules)
        pending = _positive_pending(settlement.pending_obligations)
        cash_values = tuple(
            self._cash_availability(ledger, pending, reservations.totals, rule)
            for rule in rules.cash_rules
        )
        position_values = tuple(
            self._position_availability(ledger, pending, reservations.totals, rule)
            for rule in rules.position_rules
        )
        return AvailabilityState(
            account_id=rules.account_id,
            ledger_state_hash=ledger.state_hash,
            settlement_state_hash=settlement.state_hash,
            reservation_state_hash=reservations.state_hash,
            market_settlement_rules_hash=rules.rules_hash,
            cash=cash_values,
            positions=position_values,
        )

    @staticmethod
    def _validate_reservation_owners(
        commitment: ReservationCommitment, rules: MarketSettlementRules
    ) -> None:
        for use in CashReservationUse:
            for cash_reservation in _reservation_values(commitment, use):
                cash_owners = {
                    rule.key
                    for rule in rules.cash_rules
                    if rule.key.currency_id.value == cash_reservation.currency
                    and use
                    in (
                        rule.tradable_reservation_uses
                        + rule.withdrawable_reservation_uses
                        + rule.available_margin_reservation_uses
                    )
                }
                if len(cash_owners) != 1:
                    raise AvailabilityEvidenceError(
                        "reservation currency requires one unique Cash rule owner"
                    )
        for position_reservation in commitment.sellable_quantities:
            position_owners = {
                rule.key
                for rule in rules.position_rules
                if str(rule.key.instrument_id)
                == position_reservation.instrument_id
            }
            if len(position_owners) != 1:
                raise AvailabilityEvidenceError(
                    "sellable reservation requires one Position rule owner"
                )

    @staticmethod
    def _cash_availability(
        ledger: LedgerState,
        pending: dict[CashBalanceKey | PositionBalanceKey, Money | Quantity],
        commitment: ReservationCommitment,
        rule: CashAvailabilityRule,
    ) -> CashAvailability:
        total = ledger.cash_amount(rule.key)
        pending_value = pending.get(rule.key)
        if pending_value is None:
            receivable = Money(0, total.scale, total.currency)
        elif isinstance(pending_value, Money):
            receivable = pending_value
        else:  # pragma: no cover - key type prevents this
            raise AvailabilityEvidenceError("Cash pending settlement requires Money")

        def reserved(uses: tuple[CashReservationUse, ...]) -> Money:
            result = Money(0, total.scale, total.currency)
            for use in uses:
                result = result + _money_for_currency(
                    _reservation_values(commitment, use), rule.key, total.scale
                )
            return result

        settled = total - receivable
        tradable = total - reserved(rule.tradable_reservation_uses)
        if not rule.pending_receivable_tradable:
            tradable = tradable - receivable
        withdrawable = total - reserved(rule.withdrawable_reservation_uses)
        if not rule.pending_receivable_withdrawable:
            withdrawable = withdrawable - receivable
        available_margin = total - reserved(rule.available_margin_reservation_uses)
        if not rule.pending_receivable_margin_eligible:
            available_margin = available_margin - receivable
        return CashAvailability(
            rule.key,
            total,
            settled,
            tradable,
            withdrawable,
            available_margin,
        )

    @staticmethod
    def _position_availability(
        ledger: LedgerState,
        pending: dict[CashBalanceKey | PositionBalanceKey, Money | Quantity],
        commitment: ReservationCommitment,
        rule: PositionAvailabilityRule,
    ) -> PositionAvailability:
        total = ledger.position_quantity(rule.key)
        pending_value = pending.get(rule.key)
        if pending_value is None:
            receivable = Quantity(0, total.scale, total.instrument_id)
        elif isinstance(pending_value, Quantity):
            receivable = pending_value
        else:  # pragma: no cover - key type prevents this
            raise AvailabilityEvidenceError(
                "Position pending settlement requires Quantity"
            )
        matches = tuple(
            value
            for value in commitment.sellable_quantities
            if value.instrument_id == total.instrument_id
        )
        if not matches:
            reserved = Quantity(0, total.scale, total.instrument_id)
        elif len(matches) != 1 or matches[0].scale != total.scale:
            raise AvailabilityEvidenceError(
                "sellable reservation identity or Scale mismatch"
            )
        else:
            reserved = matches[0]
        sellable = total - reserved
        if not rule.pending_receivable_sellable:
            sellable = sellable - receivable
        return PositionAvailability(rule.key, total, sellable)
