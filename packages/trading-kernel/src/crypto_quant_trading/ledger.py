"""Deterministic projection of an immutable accounting journal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from crypto_quant_domain import (
    AccountingJournalEntry,
    BalanceChange,
    CashBalance,
    CashBalanceKey,
    CurrencyId,
    Money,
    PositionBalance,
    PositionBalanceKey,
    Quantity,
    Scale,
    canonical_bytes,
    canonical_sha256,
)

from .journal import (
    AccountingJournal,
    JournalCursorError,
    JournalReplay,
    JournalReplayCursor,
)


class LedgerError(ValueError):
    """Base class for deterministic generic-ledger contract failures."""


class UnregisteredBalanceKeyError(LedgerError):
    """Raised when a journal fact refers to an undeclared balance dimension."""


class LedgerFinancialInvariantError(LedgerError):
    """Raised when a journal fact violates exact identity or scale invariants."""


class LedgerStateMismatchError(LedgerError):
    """Raised when a resume state is not the projection of its journal prefix."""


def _key_description(key: CashBalanceKey | PositionBalanceKey) -> str:
    if isinstance(key, CashBalanceKey):
        return (
            f"cash_balance_key:{key.account_id}:{key.venue_id}:{key.currency_id}"
        )
    return (
        f"position_balance_key:{key.account_id}:{key.venue_id}:{key.instrument_id}"
    )


@dataclass(frozen=True, slots=True)
class LedgerBalanceRegistration:
    """A balance dimension and the one exact scale accepted for it."""

    key: CashBalanceKey | PositionBalanceKey
    scale: Scale

    def __post_init__(self) -> None:
        if not isinstance(self.key, (CashBalanceKey, PositionBalanceKey)):
            raise TypeError("key must be CashBalanceKey or PositionBalanceKey")
        if not isinstance(self.scale, Scale):
            raise TypeError("scale must be Scale")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "ledger_balance_registration",
            "key": self.key,
            "scale": self.scale.places,
        }


@dataclass(frozen=True, slots=True)
class LedgerSchema:
    """The closed set of dimensions a generic ledger may project."""

    registrations: tuple[LedgerBalanceRegistration, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.registrations, tuple) or not self.registrations:
            raise LedgerFinancialInvariantError(
                "LedgerSchema registrations must be a non-empty tuple"
            )
        if not all(
            isinstance(registration, LedgerBalanceRegistration)
            for registration in self.registrations
        ):
            raise TypeError(
                "registrations must contain LedgerBalanceRegistration values"
            )
        ordered = tuple(
            sorted(self.registrations, key=lambda value: canonical_bytes(value.key))
        )
        keys = tuple(canonical_bytes(registration.key) for registration in ordered)
        if len(set(keys)) != len(keys):
            raise LedgerFinancialInvariantError(
                "duplicate Ledger balance registration"
            )
        object.__setattr__(self, "registrations", ordered)

    @property
    def schema_hash(self) -> str:
        return canonical_sha256(self)

    @property
    def cash_registrations(self) -> tuple[LedgerBalanceRegistration, ...]:
        return tuple(
            registration
            for registration in self.registrations
            if isinstance(registration.key, CashBalanceKey)
        )

    def registration_for(
        self, key: CashBalanceKey | PositionBalanceKey
    ) -> LedgerBalanceRegistration:
        if not isinstance(key, (CashBalanceKey, PositionBalanceKey)):
            raise TypeError("key must be CashBalanceKey or PositionBalanceKey")
        for registration in self.registrations:
            if registration.key == key:
                return registration
        raise UnregisteredBalanceKeyError(
            f"unregistered {_key_description(key)}"
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "ledger_schema",
            "schema_version": 1,
            "registrations": self.registrations,
        }


def _sorted_cash_balances(
    values: dict[CashBalanceKey, Money],
    *,
    omit_zero: bool,
) -> tuple[CashBalance, ...]:
    return tuple(
        CashBalance(key, amount)
        for key, amount in sorted(
            values.items(), key=lambda item: canonical_bytes(item[0])
        )
        if not omit_zero or amount.units != 0
    )


def _sorted_position_balances(
    values: dict[PositionBalanceKey, Quantity],
) -> tuple[PositionBalance, ...]:
    return tuple(
        PositionBalance(key, quantity, ())
        for key, quantity in sorted(
            values.items(), key=lambda item: canonical_bytes(item[0])
        )
        if quantity.units != 0
    )


@dataclass(frozen=True, slots=True)
class LedgerState:
    """An immutable, exactly reproducible projection of one journal prefix."""

    schema: LedgerSchema
    cursor: JournalReplayCursor
    cash_balances: tuple[CashBalance, ...]
    position_balances: tuple[PositionBalance, ...]
    realized_pnl: tuple[CashBalance, ...]
    fees: tuple[CashBalance, ...]
    financing: tuple[CashBalance, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.schema, LedgerSchema):
            raise TypeError("schema must be LedgerSchema")
        if not isinstance(self.cursor, JournalReplayCursor):
            raise TypeError("cursor must be JournalReplayCursor")
        self._validate_cash_collection(
            "cash_balances", self.cash_balances, require_all_registered=True
        )
        self._validate_position_collection(self.position_balances)
        self._validate_cash_collection("realized_pnl", self.realized_pnl)
        self._validate_cash_collection("fees", self.fees)
        self._validate_cash_collection("financing", self.financing)

    def _validate_cash_collection(
        self,
        name: str,
        values: tuple[CashBalance, ...],
        *,
        require_all_registered: bool = False,
    ) -> None:
        if not isinstance(values, tuple) or not all(
            isinstance(value, CashBalance) for value in values
        ):
            raise TypeError(f"{name} must be a tuple of CashBalance")
        expected_order = tuple(sorted(values, key=lambda value: canonical_bytes(value.key)))
        if values != expected_order:
            raise LedgerFinancialInvariantError(f"{name} must use canonical key order")
        keys = tuple(value.key for value in values)
        if len(set(keys)) != len(keys):
            raise LedgerFinancialInvariantError(f"duplicate key in {name}")
        for value in values:
            registration = self.schema.registration_for(value.key)
            if value.amount.scale != registration.scale:
                raise LedgerFinancialInvariantError(
                    f"{name} scale mismatch for {_key_description(value.key)}"
                )
            if not require_all_registered and value.amount.units == 0:
                raise LedgerFinancialInvariantError(
                    f"{name} cannot persist a zero attribution"
                )
        if require_all_registered:
            registered_keys = tuple(
                registration.key for registration in self.schema.cash_registrations
            )
            if keys != registered_keys:
                raise LedgerFinancialInvariantError(
                    "cash_balances must contain every registered Cash balance key"
                )

    def _validate_position_collection(
        self, values: tuple[PositionBalance, ...]
    ) -> None:
        if not isinstance(values, tuple) or not all(
            isinstance(value, PositionBalance) for value in values
        ):
            raise TypeError("position_balances must be a tuple of PositionBalance")
        expected_order = tuple(sorted(values, key=lambda value: canonical_bytes(value.key)))
        if values != expected_order:
            raise LedgerFinancialInvariantError(
                "position_balances must use canonical key order"
            )
        keys = tuple(value.key for value in values)
        if len(set(keys)) != len(keys):
            raise LedgerFinancialInvariantError("duplicate Position balance key")
        for value in values:
            registration = self.schema.registration_for(value.key)
            if value.quantity.scale != registration.scale:
                raise LedgerFinancialInvariantError(
                    "position balance scale mismatch for "
                    f"{_key_description(value.key)}"
                )
            if value.lots:
                raise LedgerFinancialInvariantError(
                    "Generic Ledger does not project Position lots"
                )

    @property
    def schema_hash(self) -> str:
        return self.schema.schema_hash

    @property
    def state_hash(self) -> str:
        return canonical_sha256(self)

    def cash_amount(self, key: CashBalanceKey) -> Money:
        if not isinstance(key, CashBalanceKey):
            raise TypeError("key must be CashBalanceKey")
        registration = self.schema.registration_for(key)
        for balance in self.cash_balances:
            if balance.key == key:
                return balance.amount
        return Money(0, registration.scale, str(key.currency_id))

    def position_quantity(self, key: PositionBalanceKey) -> Quantity:
        if not isinstance(key, PositionBalanceKey):
            raise TypeError("key must be PositionBalanceKey")
        registration = self.schema.registration_for(key)
        for balance in self.position_balances:
            if balance.key == key:
                return balance.quantity
        return Quantity(0, registration.scale, str(key.instrument_id))

    def _attribution_amount(
        self, values: tuple[CashBalance, ...], key: CashBalanceKey
    ) -> Money:
        if not isinstance(key, CashBalanceKey):
            raise TypeError("key must be CashBalanceKey")
        registration = self.schema.registration_for(key)
        for balance in values:
            if balance.key == key:
                return balance.amount
        return Money(0, registration.scale, str(key.currency_id))

    def realized_pnl_amount(self, key: CashBalanceKey) -> Money:
        return self._attribution_amount(self.realized_pnl, key)

    def fee_amount(self, key: CashBalanceKey) -> Money:
        return self._attribution_amount(self.fees, key)

    def financing_amount(self, key: CashBalanceKey) -> Money:
        return self._attribution_amount(self.financing, key)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "ledger_state",
            "schema_hash": self.schema_hash,
            "cursor": self.cursor,
            "cash_balances": self.cash_balances,
            "position_balances": self.position_balances,
            "realized_pnl": self.realized_pnl,
            "fees": self.fees,
            "financing": self.financing,
        }


@dataclass(frozen=True, slots=True)
class GenericLedger:
    """Projects registered balances and native attributions from Journal facts."""

    schema: LedgerSchema

    def __post_init__(self) -> None:
        if not isinstance(self.schema, LedgerSchema):
            raise TypeError("schema must be LedgerSchema")

    def _empty_state(self, journal: AccountingJournal) -> LedgerState:
        cash = {
            registration.key: Money(
                0,
                registration.scale,
                str(registration.key.currency_id),
            )
            for registration in self.schema.cash_registrations
            if isinstance(registration.key, CashBalanceKey)
        }
        return LedgerState(
            schema=self.schema,
            cursor=journal.cursor_at(0),
            cash_balances=_sorted_cash_balances(cash, omit_zero=False),
            position_balances=(),
            realized_pnl=(),
            fees=(),
            financing=(),
        )

    def _validate_change(self, change: BalanceChange) -> None:
        registration = self.schema.registration_for(change.key)
        if change.value.scale != registration.scale:
            raise LedgerFinancialInvariantError(
                f"balance change scale mismatch for {_key_description(change.key)}"
            )

    def _attribution_key(
        self, entry: AccountingJournalEntry, value: Money
    ) -> CashBalanceKey:
        try:
            key = CashBalanceKey(
                entry.account_id,
                entry.venue_id,
                CurrencyId(value.currency),
            )
        except (TypeError, ValueError) as error:
            raise LedgerFinancialInvariantError(
                f"invalid attribution currency identity: {value.currency}"
            ) from error
        registration = self.schema.registration_for(key)
        if value.scale != registration.scale:
            raise LedgerFinancialInvariantError(
                f"attribution scale mismatch for {_key_description(key)}"
            )
        return key

    @staticmethod
    def _add_money(
        values: dict[CashBalanceKey, Money], key: CashBalanceKey, change: Money
    ) -> None:
        current = values.get(key)
        values[key] = change if current is None else current + change

    def _apply_replay(self, state: LedgerState, replay: JournalReplay) -> LedgerState:
        if replay.start_cursor != state.cursor:
            raise LedgerStateMismatchError(
                "Journal replay start cursor does not match Ledger state cursor"
            )
        if not replay.entries:
            return state

        cash = {balance.key: balance.amount for balance in state.cash_balances}
        positions = {
            balance.key: balance.quantity for balance in state.position_balances
        }
        realized_pnl = {
            balance.key: balance.amount for balance in state.realized_pnl
        }
        fees = {balance.key: balance.amount for balance in state.fees}
        financing = {balance.key: balance.amount for balance in state.financing}

        for entry in replay.entries:
            for change in entry.balance_changes:
                self._validate_change(change)
                if isinstance(change.key, CashBalanceKey):
                    if not isinstance(change.value, Money):
                        raise LedgerFinancialInvariantError(
                            "Cash balance change must contain Money"
                        )
                    self._add_money(cash, change.key, change.value)
                elif isinstance(change.key, PositionBalanceKey):
                    if not isinstance(change.value, Quantity):
                        raise LedgerFinancialInvariantError(
                            "Position balance change must contain Quantity"
                        )
                    current = positions.get(change.key)
                    positions[change.key] = (
                        change.value if current is None else current + change.value
                    )
                else:
                    raise LedgerFinancialInvariantError(
                        "unsupported Ledger balance key type"
                    )
            for value in entry.realized_pnl:
                self._add_money(
                    realized_pnl, self._attribution_key(entry, value), value
                )
            for value in entry.fees:
                self._add_money(fees, self._attribution_key(entry, value), value)
            for value in entry.financing:
                self._add_money(
                    financing, self._attribution_key(entry, value), value
                )

        return LedgerState(
            schema=self.schema,
            cursor=replay.end_cursor,
            cash_balances=_sorted_cash_balances(cash, omit_zero=False),
            position_balances=_sorted_position_balances(positions),
            realized_pnl=_sorted_cash_balances(realized_pnl, omit_zero=True),
            fees=_sorted_cash_balances(fees, omit_zero=True),
            financing=_sorted_cash_balances(financing, omit_zero=True),
        )

    def project(
        self,
        journal: AccountingJournal,
        *,
        stop: JournalReplayCursor | None = None,
    ) -> LedgerState:
        if not isinstance(journal, AccountingJournal):
            raise TypeError("journal must be AccountingJournal")
        state = self._empty_state(journal)
        return self._apply_replay(state, journal.replay(stop=stop))

    def resume(
        self,
        journal: AccountingJournal,
        state: LedgerState,
        *,
        stop: JournalReplayCursor | None = None,
    ) -> LedgerState:
        if not isinstance(journal, AccountingJournal):
            raise TypeError("journal must be AccountingJournal")
        if not isinstance(state, LedgerState):
            raise TypeError("state must be LedgerState")
        if state.schema != self.schema:
            raise LedgerStateMismatchError("Ledger state schema mismatch")
        try:
            expected = self.project(journal, stop=state.cursor)
        except JournalCursorError as error:
            raise LedgerStateMismatchError(
                "Ledger state cursor does not match Journal"
            ) from error
        if expected != state:
            raise LedgerStateMismatchError(
                "Ledger resume state does not match Journal prefix state"
            )
        replay = journal.replay(start=state.cursor, stop=stop)
        return self._apply_replay(state, replay)
