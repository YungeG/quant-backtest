"""Two-venue CNY cash availability over the existing immutable Kernel facts.

Pure account-wide affordability only. It does not admit/publish an Order or
replace venue-local risk/settlement or source-qualified historical fee rules.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from crypto_quant_domain import CashBalanceKey, Money, Scale, UtcInstant, canonical_sha256
from crypto_quant_trading.journal import AccountingJournal
from crypto_quant_trading.ledger import GenericLedger, LedgerSchema
from crypto_quant_trading.orders import OrderEventStream
from crypto_quant_trading.reservations import OrderReservationSchedule, ResourceReservationBook
from crypto_quant_trading.settlement import CashReservationUse, MarketSettlementRules, SettlementBook

_CNY = "CNY"
_SCALE = Scale(2)
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _cny(units: int) -> Money:
    return Money(units, _SCALE, _CNY)


def _reserved(values: tuple[Money, ...]) -> int:
    if len(values) > 1 or any(v.currency != _CNY or v.scale != _SCALE or v.units < 0 for v in values):
        raise ValueError("portfolio cash reservations must be nonnegative CNY cents")
    return values[0].units if values else 0


@dataclass(frozen=True, slots=True)
class CnAShareSharedCnyCashSnapshotV1:
    account_id: str
    as_of: UtcInstant
    journal_hash: str
    ledger_schema_hash: str
    settlement_state_hash: str
    reservation_state_hash: str
    market_rules_hash: str
    total: Money
    unsettled_receivables: Money
    reserved_principal: Money
    reserved_fees: Money
    spendable: Money
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (type(self.account_id) is not str or not self.account_id
                or self.account_id.strip() != self.account_id
                or type(self.as_of) is not UtcInstant):
            raise ValueError("shared CNY account identity/as_of must be canonical")
        for identity in (self.journal_hash, self.ledger_schema_hash, self.settlement_state_hash,
                         self.reservation_state_hash, self.market_rules_hash):
            if type(identity) is not str or _HASH.fullmatch(identity) is None:
                raise ValueError("shared CNY source hash must be canonical")
        values = (self.total, self.unsettled_receivables, self.reserved_principal,
                  self.reserved_fees, self.spendable)
        if any(type(v) is not Money or v.currency != _CNY or v.scale != _SCALE or v.units < 0 for v in values):
            raise ValueError("shared CNY amounts must be nonnegative cents")
        if self.spendable.units != (self.total.units - self.unsettled_receivables.units
                                   - self.reserved_principal.units - self.reserved_fees.units):
            raise ValueError("shared CNY cash conservation mismatch")

    def can_fund_buy(self, *, principal: Money, estimated_fee: Money) -> bool:
        if (type(principal) is not Money or type(estimated_fee) is not Money
                or principal.currency != _CNY or estimated_fee.currency != _CNY
                or principal.scale != _SCALE or estimated_fee.scale != _SCALE
                or principal.units <= 0 or estimated_fee.units < 0):
            raise ValueError("buy principal/fee must be positive CNY cents and nonnegative fee")
        return principal.units + estimated_fee.units <= self.spendable.units

    @property
    def snapshot_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_shared_cny_cash_snapshot", "schema_version": 1,
                "account_id": self.account_id, "as_of": self.as_of,
                "journal_hash": self.journal_hash,
                "ledger_schema_hash": self.ledger_schema_hash,
                "settlement_state_hash": self.settlement_state_hash,
                "reservation_state_hash": self.reservation_state_hash,
                "market_rules_hash": self.market_rules_hash, "total": self.total,
                "unsettled_receivables": self.unsettled_receivables,
                "reserved_principal": self.reserved_principal, "reserved_fees": self.reserved_fees,
                "spendable": self.spendable, "trade_authorized": False}


def project_cn_a_share_shared_cny_cash_v1(
    *, journal: AccountingJournal, ledger_schema: LedgerSchema,
    settlement_book: SettlementBook, order_streams: tuple[OrderEventStream, ...],
    reservation_schedules: tuple[OrderReservationSchedule, ...],
    market_rules: MarketSettlementRules, as_of: UtcInstant,
) -> CnAShareSharedCnyCashSnapshotV1:
    """Reproject Journal, pending receipts and accepted Order reservations from source."""
    if (type(journal) is not AccountingJournal or type(ledger_schema) is not LedgerSchema
            or type(settlement_book) is not SettlementBook or type(market_rules) is not MarketSettlementRules
            or type(order_streams) is not tuple or type(reservation_schedules) is not tuple
            or type(as_of) is not UtcInstant):
        raise TypeError("shared CNY projection requires exact Kernel source values")
    account = market_rules.account_id
    cash_keys = tuple(r.key for r in ledger_schema.cash_registrations
                      if isinstance(r.key, CashBalanceKey))
    if (len(cash_keys) != 2 or any(r.key.account_id != account for r in ledger_schema.registrations)
            or not all(type(k) is CashBalanceKey and k.account_id == account
            and k.currency_id.value == _CNY for k in cash_keys)
            or {k.venue_id.value for k in cash_keys} != {"xshg", "xshe"}
            or settlement_book.account_id != account
            or {rule.key for rule in market_rules.cash_rules} != set(cash_keys)
            or {rule.key for rule in market_rules.position_rules} != {
                r.key for r in ledger_schema.registrations if not isinstance(r.key, CashBalanceKey)
            }):
        raise ValueError("shared CNY requires one account, two covered venue cash keys and position rules")
    for rule in market_rules.cash_rules:
        if (rule.pending_receivable_tradable or rule.pending_receivable_withdrawable
                or rule.pending_receivable_margin_eligible
                or set(rule.tradable_reservation_uses) != {CashReservationUse.CASH, CashReservationUse.FEE_RESERVE}):
            raise ValueError("shared CNY rule must exclude pending sales and reserve cash plus fees")
    if any(entry.recorded_at.instant > as_of for entry in journal.entries):
        raise ValueError("future Journal entry cannot fund CNY buys")
    if any(stream.state is not None and stream.state.updated_at.instant > as_of for stream in order_streams):
        raise ValueError("future Order reservation cannot fund CNY buys")
    ledger = GenericLedger(ledger_schema).project(journal)
    event_count = sum(event.occurred_at.instant <= as_of for event in settlement_book.events)
    settlement = settlement_book.project(stop=settlement_book.cursor_at(event_count))
    reservations = ResourceReservationBook(account).project(order_streams, reservation_schedules)
    total = 0
    for key in cash_keys:
        amount = ledger.cash_amount(key)
        if amount.scale != _SCALE or amount.currency != _CNY or amount.units < 0:
            raise ValueError("shared CNY venue cash must be nonnegative cents")
        total += amount.units
    receivables = 0
    for pending in settlement.pending_obligations:
        if pending.balance_key not in {r.key for r in ledger_schema.registrations}:
            raise ValueError("shared CNY settlement balance key is unregistered")
        if isinstance(pending.balance_key, CashBalanceKey):
            if (pending.balance_key not in cash_keys or not isinstance(pending.value, Money)
                    or pending.value.currency != _CNY or pending.value.scale != _SCALE
                    or pending.value.units < 0):
                raise ValueError("shared CNY negative or mismatched pending cash is unsupported")
            receivables += pending.value.units
    commitment = reservations.totals
    if commitment.margin or commitment.exposure_capacity:
        raise ValueError("shared cash model does not admit margin or exposure reservations")
    principal = _reserved(commitment.cash)
    fees = _reserved(commitment.fee_reserve)
    spendable = total - receivables - principal - fees
    if spendable < 0:
        raise ValueError("shared CNY cash is overcommitted or unsettled")
    return CnAShareSharedCnyCashSnapshotV1(
        account, as_of, journal.journal_hash, ledger_schema.schema_hash,
        settlement.state_hash, reservations.state_hash, market_rules.rules_hash,
        _cny(total), _cny(receivables), _cny(principal), _cny(fees), _cny(spendable),
    )
