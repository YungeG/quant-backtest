"""Portfolio-only A-share T+1 sellability across two CNY venues.

Source-projected availability, not an admission or fill: old single-venue
AvailabilityProjection rejects the two CNY owners for currency-only reservations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

from crypto_quant_domain import (
    InstrumentId, PositionBalanceKey, Quantity, UtcInstant, canonical_bytes, canonical_sha256,
)
from crypto_quant_trading.journal import AccountingJournal
from crypto_quant_trading.ledger import GenericLedger, LedgerSchema
from crypto_quant_trading.orders import OrderEventStream
from crypto_quant_trading.reservations import OrderReservationSchedule, ResourceReservationBook
from crypto_quant_trading.settlement import (
    MarketSettlementRules, PositionAvailability, SettlementBook,
)

_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class CnASharePortfolioSellabilitySnapshotV1:
    account_id: str
    as_of: UtcInstant
    journal_hash: str
    settlement_state_hash: str
    reservation_state_hash: str
    market_rules_hash: str
    positions: tuple[PositionAvailability, ...]
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (type(self.account_id) is not str or not self.account_id
                or not isinstance(self.as_of, UtcInstant)
                or type(self.positions) is not tuple
                or any(type(p) is not PositionAvailability or p.key.account_id != self.account_id
                       or p.key.venue_id.value not in {"xshg", "xshe"}
                       or p.sellable.units < 0 for p in self.positions)
                or self.positions != tuple(sorted(self.positions, key=lambda p: canonical_bytes(p.key)))
                or len({p.key for p in self.positions}) != len(self.positions)):
            raise ValueError("portfolio sellability scope/order mismatch")
        for h in (self.journal_hash, self.settlement_state_hash,
                  self.reservation_state_hash, self.market_rules_hash):
            if type(h) is not str or _HASH.fullmatch(h) is None:
                raise ValueError("sellability source identity mismatch")

    def sellable_for(self, instrument: InstrumentId) -> Quantity:
        if type(instrument) is not InstrumentId:
            raise TypeError("instrument must be InstrumentId")
        matched = tuple(p.sellable for p in self.positions if p.key.instrument_id == instrument)
        if len(matched) != 1:
            raise ValueError("missing unique source-backed position for instrument")
        return matched[0]

    @property
    def snapshot_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_sellability_snapshot", "schema_version": 1,
                "account_id": self.account_id, "as_of": self.as_of,
                "journal_hash": self.journal_hash, "settlement_state_hash": self.settlement_state_hash,
                "reservation_state_hash": self.reservation_state_hash,
                "market_rules_hash": self.market_rules_hash, "positions": self.positions,
                "trade_authorized": False}


def project_cn_a_share_portfolio_sellability_v1(
    *, journal: AccountingJournal, ledger_schema: LedgerSchema,
    settlement_book: SettlementBook, order_streams: tuple[OrderEventStream, ...],
    reservation_schedules: tuple[OrderReservationSchedule, ...],
    market_rules: MarketSettlementRules, as_of: UtcInstant,
) -> CnASharePortfolioSellabilitySnapshotV1:
    if (type(journal) is not AccountingJournal or type(ledger_schema) is not LedgerSchema
            or type(settlement_book) is not SettlementBook or type(market_rules) is not MarketSettlementRules
            or type(order_streams) is not tuple or type(reservation_schedules) is not tuple
            or type(as_of) is not UtcInstant):
        raise TypeError("portfolio sellability needs exact source values and as_of")
    account = market_rules.account_id
    cash_keys = {r.key for r in ledger_schema.cash_registrations}
    position_keys = {r.key for r in ledger_schema.registrations if isinstance(r.key, PositionBalanceKey)}
    if (len(cash_keys) != 2 or {k.venue_id.value for k in cash_keys} != {"xshg", "xshe"}
            or any(k.account_id != account for k in cash_keys | position_keys)
            or {r.key for r in market_rules.cash_rules} != cash_keys
            or {r.key for r in market_rules.position_rules} != position_keys
            or any(r.pending_receivable_sellable for r in market_rules.position_rules)
            or settlement_book.account_id != account):
        raise ValueError("portfolio sellability needs complete two-venue account rules and T+1")
    if any(entry.recorded_at.instant > as_of for entry in journal.entries):
        raise ValueError("future Journal entry cannot make shares sellable")
    if any(stream.state is not None and stream.state.updated_at.instant > as_of for stream in order_streams):
        raise ValueError("future Order evidence cannot change sellability")
    ledger = GenericLedger(ledger_schema).project(journal)
    count = sum(e.occurred_at.instant <= as_of for e in settlement_book.events)
    settlement = settlement_book.project(stop=settlement_book.cursor_at(count))
    reservations = ResourceReservationBook(account).project(order_streams, reservation_schedules)
    pending: dict[PositionBalanceKey, int] = {}
    for item in settlement.pending_obligations:
        if item.balance_key not in cash_keys | position_keys:
            raise ValueError("unregistered settlement key")
        if isinstance(item.balance_key, PositionBalanceKey):
            if not isinstance(item.value, Quantity):
                raise ValueError("pending position must be Quantity")
            if item.value.units > 0:
                pending[item.balance_key] = pending.get(item.balance_key, 0) + item.value.units
    reserved = {value.instrument_id: value for value in reservations.totals.sellable_quantities}
    if set(reserved) - {str(key.instrument_id) for key in position_keys}:
        raise ValueError("sell reservation for unknown position")
    positions: list[PositionAvailability] = []
    for rule in market_rules.position_rules:
        total = ledger.position_quantity(rule.key)
        held = reserved.get(total.instrument_id)
        if held is not None and held.scale != total.scale:
            raise ValueError("sell reservation Scale mismatch")
        units = total.units - pending.get(rule.key, 0) - (held.units if held is not None else 0)
        if units < 0:
            raise ValueError("unsettled or reserved shares exceed position")
        positions.append(PositionAvailability(
            rule.key, total, Quantity(units, total.scale, total.instrument_id)))
    return CnASharePortfolioSellabilitySnapshotV1(
        account, as_of, journal.journal_hash, settlement.state_hash,
        reservations.state_hash, market_rules.rules_hash,
        tuple(sorted(positions, key=lambda value: canonical_bytes(value.key))),
    )
