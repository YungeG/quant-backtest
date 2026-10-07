"""Pure live-state two-venue funding plan; no append, publication or trade grant.

Current native commitments and pending cash remain unavailable. The owning
standard Engine must append the complete pair atomically and verify its prefix.
This operator alone is not a qualified source, economic owner or Backtest run.
"""
from __future__ import annotations

import re

from crypto_quant_domain import (
    AccountingEntryType, AccountingJournalEntry, BalanceChange, CashBalanceKey,
    DomainId, DomainIdKind, Money, Scale, SimulationInstant, SourceSequence,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal, GenericLedger, LedgerSchema, MarketSettlementRules,
    OrderEventStream, OrderReservationSchedule, ResourceReservationBook, SettlementBook,
)
from crypto_quant_trading.profiles.cn_a_share.shared_cny_cash_v1 import (
    project_cn_a_share_shared_cny_cash_v1,
)

_CENT = Scale(2)
_MODEL = "cn.portfolio.live-venue-funding.development.v1"


def plan_cn_portfolio_venue_funding_development_v1(
    *, journal: AccountingJournal, ledger_schema: LedgerSchema,
    settlement_book: SettlementBook, order_streams: tuple[OrderEventStream, ...],
    reservation_schedules: tuple[OrderReservationSchedule, ...],
    market_rules: MarketSettlementRules,
    required_by_venue: tuple[tuple[CashBalanceKey, Money], ...],
    at: SimulationInstant, target_hash: str,
) -> tuple[AccountingJournalEntry, ...]:
    """Return zero entries or a complete debit/credit pair, never mutate facts.

    Requirements are NEW principal plus worst-case fees; existing reservations
    are deducted independently. Quantities, fee calculation and acceptance are
    the caller's native sizing/risk responsibilities, not this planner's.
    """
    if type(at) is not SimulationInstant or type(target_hash) is not str or re.fullmatch(r"sha256:[0-9a-f]{64}", target_hash) is None:
        raise TypeError("venue funding requires exact simulation clock and target hash")
    if (type(journal) is not AccountingJournal or type(ledger_schema) is not LedgerSchema
            or type(settlement_book) is not SettlementBook or type(market_rules) is not MarketSettlementRules
            or type(order_streams) is not tuple or any(type(s) is not OrderEventStream for s in order_streams)
            or type(reservation_schedules) is not tuple or any(type(s) is not OrderReservationSchedule for s in reservation_schedules)):
        raise TypeError("venue funding requires exact native source facts")
    if (any(e.recorded_at > at for e in journal.entries)
            or any(e.occurred_at > at for e in settlement_book.events)
            or any(s.order.created_at > at or (s.state is not None and s.state.updated_at > at) for s in order_streams)):
        raise ValueError("venue funding cannot consume future source facts or phases")
    cash = project_cn_a_share_shared_cny_cash_v1(
        journal=journal, ledger_schema=ledger_schema, settlement_book=settlement_book,
        order_streams=order_streams, reservation_schedules=reservation_schedules,
        market_rules=market_rules, as_of=at.instant)
    keys = tuple(sorted((r.key for r in ledger_schema.cash_registrations if isinstance(r.key, CashBalanceKey)),
                        key=lambda key: key.venue_id.value))
    if (type(required_by_venue) is not tuple or len(required_by_venue) != 2
            or any(type(row) is not tuple or len(row) != 2 or type(row[0]) is not CashBalanceKey
                   or type(row[1]) is not Money or row[1].scale != _CENT or row[1].currency != "CNY"
                   or row[1].units < 0 for row in required_by_venue)
            or len({row[0] for row in required_by_venue}) != 2
            or {row[0] for row in required_by_venue} != set(keys)):
        raise ValueError("venue funding requirements must exact-cover both CNY keys in cents")
    required = dict(required_by_venue)
    if sum(value.units for value in required.values()) > cash.spendable.units:
        raise ValueError("venue funding exceeds settled unreserved shared cash")
    ledger = GenericLedger(ledger_schema).project(journal)
    settlement = settlement_book.project()
    available = {}
    for key in keys:
        streams = tuple(s for s in order_streams if s.order.intent.instrument_id.venue == key.venue_id)
        ids = {s.order.order_id for s in streams}
        schedules = tuple(s for s in reservation_schedules if s.order_id in ids)
        committed = ResourceReservationBook(cash.account_id).project(streams, schedules).totals
        pending = sum(p.value.units for p in settlement.pending_obligations
                      if p.balance_key == key and isinstance(p.value, Money))
        available[key] = (ledger.cash_amount(key).units - pending
                          - sum(value.units for value in committed.cash)
                          - sum(value.units for value in committed.fee_reserve))
    if any(value < 0 for value in available.values()) or sum(available.values()) != cash.spendable.units:
        raise ValueError("venue funding source is overcommitted or reservation ownership mismatches")
    deficits = tuple(key for key in keys if required[key].units > available[key])
    if not deficits:
        return ()
    if len(deficits) != 1:
        raise ValueError("venue funding has no settled source surplus")
    destination = deficits[0]
    source = next(key for key in keys if key != destination)
    units = required[destination].units - available[destination]
    if units > available[source] - required[source].units:
        raise ValueError("venue funding would spend the source venue's own requirements")
    identity = canonical_sha256({"model": _MODEL, "target_hash": target_hash,
        "cash_snapshot_hash": cash.snapshot_hash, "required_by_venue": tuple((key, required[key]) for key in keys),
        "at": at, "source": source, "destination": destination, "amount": Money(units, _CENT, "CNY")})
    source_id = _MODEL + ":" + identity
    if any(source_id in entry.source_ids for entry in journal.entries):
        raise ValueError("venue funding pair already committed")
    return tuple(AccountingJournalEntry(
        DomainId(DomainIdKind.JOURNAL, "jnl_" + canonical_sha256({"funding": identity, "leg": leg})[7:]),
        AccountingEntryType.CAPITAL_TRANSFERRED, cash.account_id, key.venue_id, at.instant,
        SimulationInstant(at.instant, at.phase, SourceSequence(at.source_sequence.value + index)),
        (source_id,), (BalanceChange(key, Money(amount, _CENT, "CNY")),), (), (), ())
        for index, (leg, key, amount) in enumerate((("debit", source, -units), ("credit", destination, units)), 1))
