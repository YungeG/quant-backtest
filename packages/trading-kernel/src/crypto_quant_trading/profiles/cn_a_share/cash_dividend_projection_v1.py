"""Pure, source-bound economic projection for declared CNY cash dividends.

This proof is not source qualification, account authority or a journal commit.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields, replace
from enum import Enum
from hashlib import sha256
import re
import unicodedata

from crypto_quant_domain import (
    CashBalanceKey, CurrencyId, InstrumentCatalog, InstrumentId, InstrumentType,
    Money, PortfolioSnapshot, PositionBalanceKey, PricePurpose, QuantizationPolicy,
    Scale, SimulationInstant, canonical_bytes, canonical_sha256,
)
from crypto_quant_trading.journal import AccountingJournal
from crypto_quant_trading.ledger import GenericLedger, LedgerSchema
from crypto_quant_trading.marks import ResolvedMark
from crypto_quant_trading.orders import OrderEventStream
from crypto_quant_trading.reservations import OrderReservationSchedule, ResourceReservationBook
from crypto_quant_trading.settlement import CashReservationUse, MarketSettlementRules, SettlementBook
from crypto_quant_trading.snapshots import PortfolioSnapshotProjector, SnapshotProjectionFailure
from crypto_quant_trading.valuation import CurrencyValuationGraph
from .shared_cny_cash_v1 import project_cn_a_share_shared_cny_cash_v1

_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CENT = Scale(2)
_CNY = CurrencyId("CNY")


def _exact(name: str, value: object, expected: type) -> None:
    if type(value) is not expected:
        raise TypeError(f"{name} must be exact {expected.__name__}")


def _text(name: str, value: str) -> None:
    _exact(name, value, str)
    if not value or value.strip() != value or unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{name} must be nonempty canonical text")
    canonical_bytes(value)


def _hash(name: str, value: str) -> None:
    _exact(name, value, str)
    if _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be a full canonical sha256 hash")


def _money(name: str, value: Money, *, nonnegative: bool = True) -> None:
    _exact(name, value, Money)
    _exact(name + ".units", value.units, int)
    if value.scale != _CENT or value.currency != "CNY" or (nonnegative and value.units < 0):
        raise ValueError(f"{name} must be {'nonnegative ' if nonnegative else ''}CNY cents")


def _cny(units: int) -> Money:
    return Money(units, _CENT, "CNY")


def _payload(value: object, tag: str) -> dict[str, object]:
    return {"type": tag, "schema_version": 1,
            **{f.name: getattr(value, f.name) for f in fields(value)}}


def _book_body_v1(book: SettlementBook) -> dict[str, object]:
    """Preserve the existing complete settlement-source wire representation."""
    return {"type": "cn_portfolio_development_settlement_book_source",
            "schema_version": 1, "account_id": book.account_id,
            "book_hash": book.book_hash, "obligations": book.obligations,
            "events": book.events}


def _ordered(name: str, values: tuple, expected: type, key) -> None:
    _exact(name, values, tuple)
    for value in values:
        _exact(name + " item", value, expected)
    keys = tuple(key(v) for v in values)
    if any(a >= b for a, b in zip(keys, keys[1:])):
        raise ValueError(f"{name} must be strictly sorted and unique")


def _instrument(value: InstrumentId) -> None:
    _exact("instrument_id", value, InstrumentId)
    if value.venue.value not in {"xshg", "xshe"}:
        raise ValueError("cash dividend requires XSHG/XSHE instrument")


@dataclass(frozen=True, slots=True)
class CnAShareCashDividendClaimV1:
    account_id: str
    action_id: str
    instrument_id: InstrumentId
    action_terms_hash: str
    tax_policy_hash: str
    record_journal_hash: str
    registered_at: SimulationInstant
    entitlement_at: SimulationInstant
    payment_due_at: SimulationInstant
    entitled_quantity: int
    tax_mode: str
    tax_due_at: SimulationInstant | None
    recognized_gross: Money
    gross_paid: Money
    tax_assessed: Money
    tax_settled: Money
    applied_events: tuple[tuple[str, str, SimulationInstant, str], ...]

    def __post_init__(self) -> None:
        for name in ("account_id", "action_id"):
            _text(name, getattr(self, name))
        _instrument(self.instrument_id)
        for name in ("action_terms_hash", "tax_policy_hash", "record_journal_hash"):
            _hash(name, getattr(self, name))
        for name in ("registered_at", "entitlement_at", "payment_due_at"):
            _exact(name, getattr(self, name), SimulationInstant)
        if not self.registered_at < self.entitlement_at <= self.payment_due_at:
            raise ValueError("claim clock order mismatch")
        _exact("entitled_quantity", self.entitled_quantity, int)
        if self.entitled_quantity < 0:
            raise ValueError("entitled_quantity cannot be negative")
        _exact("tax_mode", self.tax_mode, str)
        if self.tax_mode not in {"KNOWN_ZERO", "KNOWN_AMOUNT"}:
            raise ValueError("unknown dividend tax mode")
        if self.tax_mode == "KNOWN_ZERO":
            if self.tax_due_at is not None:
                raise ValueError("known zero tax cannot have due clock")
        else:
            _exact("tax_due_at", self.tax_due_at, SimulationInstant)
            if self.tax_due_at < self.entitlement_at:
                raise ValueError("tax due before entitlement")
        for name in ("recognized_gross", "gross_paid", "tax_assessed", "tax_settled"):
            _money(name, getattr(self, name))
        g, p, t, s = (self.recognized_gross.units, self.gross_paid.units,
                       self.tax_assessed.units, self.tax_settled.units)
        if p not in {0, g} or not 0 <= s <= t <= g or s not in {0, t}:
            raise ValueError("partial or inconsistent claim amounts")
        if (self.entitled_quantity == 0 and any((g, p, t, s))) or (self.tax_mode == "KNOWN_ZERO" and (t or s)):
            raise ValueError("zero quantity/tax claim has nonzero amounts")
        _exact("applied_events", self.applied_events, tuple)
        if not 1 <= len(self.applied_events) <= 4:
            raise ValueError("claim must retain one to four events")
        by_kind = {}
        ids = set()
        previous = None
        for row in self.applied_events:
            _exact("applied event", row, tuple)
            if len(row) != 4:
                raise ValueError("applied event must have four fields")
            kind, event_id, at, payload_hash = row
            _exact("event kind", kind, str)
            _text("event_id", event_id)
            _hash("payload_hash", payload_hash)
            _exact("event clock", at, SimulationInstant)
            if kind not in {"REGISTER", "ENTITLE", "PAY", "TAX"} or kind in by_kind or event_id in ids:
                raise ValueError("duplicate or unsupported claim event")
            if previous is not None and at <= previous:
                raise ValueError("applied events must be full-clock increasing")
            previous = at
            by_kind[kind] = at
            ids.add(event_id)
        if by_kind.get("REGISTER") != self.registered_at:
            raise ValueError("claim must retain REGISTER at registration clock")
        if "ENTITLE" not in by_kind:
            if any((g, p, t, s)) or set(by_kind) != {"REGISTER"}:
                raise ValueError("claim amounts/events precede ENTITLE")
        elif by_kind["ENTITLE"] != self.entitlement_at:
            raise ValueError("ENTITLE clock mismatch")
        for kind, due, paid, amount in (("PAY", self.payment_due_at, p, g), ("TAX", self.tax_due_at, s, t)):
            if kind in by_kind:
                if due is None or by_kind[kind] < due or by_kind[kind] <= self.entitlement_at or paid != amount:
                    raise ValueError(f"{kind} clock or amount mismatch")
            elif paid != 0:
                raise ValueError(f"claim amount lacks {kind}")

    def to_canonical_dict(self) -> dict[str, object]:
        return _payload(self, "cn_a_share_cash_dividend_claim")


@dataclass(frozen=True, slots=True)
class CnAShareCashDividendStateV1:
    account_id: str
    as_of: SimulationInstant
    claims: tuple[CnAShareCashDividendClaimV1, ...]

    def __post_init__(self) -> None:
        _text("account_id", self.account_id)
        _exact("as_of", self.as_of, SimulationInstant)
        _ordered("claims", self.claims, CnAShareCashDividendClaimV1, lambda c: (str(c.instrument_id), c.action_id))
        if len(self.claims) > 4096:
            raise ValueError("claim count exceeds 4096")
        ids = []
        for claim in self.claims:
            if claim.account_id != self.account_id or any(e[2] > self.as_of for e in claim.applied_events):
                raise ValueError("claim account or applied clock mismatches state")
            ids.extend(e[1] for e in claim.applied_events)
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate state event identity")

    def to_canonical_dict(self) -> dict[str, object]:
        return _payload(self, "cn_a_share_cash_dividend_state")


def _native_types(value) -> None:
    for name, expected in (("journal", AccountingJournal), ("ledger_schema", LedgerSchema),
            ("settlement_book", SettlementBook), ("market_rules", MarketSettlementRules),
            ("as_of", SimulationInstant)):
        _exact(name, getattr(value, name), expected)
    _ordered("order_streams", value.order_streams, OrderEventStream, lambda s: s.order.order_id.value)
    _ordered("reservation_schedules", value.reservation_schedules, OrderReservationSchedule, lambda s: s.order_id.value)


@dataclass(frozen=True, slots=True)
class CnASharePortfolioEconomicProjectionInputsV1:
    journal: AccountingJournal
    ledger_schema: LedgerSchema
    settlement_book: SettlementBook
    order_streams: tuple[OrderEventStream, ...]
    reservation_schedules: tuple[OrderReservationSchedule, ...]
    market_rules: MarketSettlementRules
    instrument_catalog: InstrumentCatalog
    marks: tuple[ResolvedMark, ...]
    currency_valuation_graph: CurrencyValuationGraph
    notional_quantization: QuantizationPolicy
    dividend_state: CnAShareCashDividendStateV1
    as_of: SimulationInstant

    def __post_init__(self) -> None:
        _native_types(self)
        _exact("instrument_catalog", self.instrument_catalog, InstrumentCatalog)
        _exact("currency_valuation_graph", self.currency_valuation_graph, CurrencyValuationGraph)
        _exact("notional_quantization", self.notional_quantization, QuantizationPolicy)
        _exact("dividend_state", self.dividend_state, CnAShareCashDividendStateV1)
        _ordered("marks", self.marks, ResolvedMark, lambda m: str(m.instrument_id))
        for mark in self.marks:
            _exact("available_at_instant", mark.available_at_instant, SimulationInstant)
            _exact("resolved_at_instant", mark.resolved_at_instant, SimulationInstant)
        if self.notional_quantization.target_scale != _CENT:
            raise ValueError("notional quantization must target CNY cents")

    def to_canonical_dict(self) -> dict[str, object]:
        return {**_payload(self, "cn_a_share_portfolio_economic_projection_inputs"),
                "settlement_book": _book_body_v1(self.settlement_book)}

    @staticmethod
    def scoped_projector() -> Callable[
        [CnASharePortfolioEconomicProjectionInputsV1], CnAShareEconomicProjectionOutcomeV1
    ]:
        """Create a projector for one serial replay of immutable source values."""
        return _ProjectionInputDigestMemoV1().project


class _ProjectionInputDigestMemoV1:
    """Reuse canonical fields within a replay without retaining full input encodings."""

    _fields = frozenset({
        "journal", "ledger_schema", "settlement_book", "order_streams", "reservation_schedules",
        "market_rules", "instrument_catalog", "notional_quantization",
    })
    _byte_limit = 4 * 1024 * 1024

    def __init__(self) -> None:
        self._encoded: dict[str, tuple[object, bytes]] = {}

    @staticmethod
    def _same_source(current: object, previous: object) -> bool:
        if current is previous:
            return True
        return (type(current) is tuple and type(previous) is tuple and len(current) == len(previous)
                and all(left is right for left, right in zip(current, previous, strict=True)))

    def digest(self, inputs: CnASharePortfolioEconomicProjectionInputsV1) -> str:
        try:
            result = self._memoized_digest(inputs)
        except MemoryError:
            self._encoded.clear()
            raise
        except Exception:
            # Re-run the authoritative traversal for its original path and first error.
            result = None
        if result is not None:
            return result
        self._encoded.clear()
        return canonical_sha256(inputs)

    def _memoized_digest(self, inputs: CnASharePortfolioEconomicProjectionInputsV1) -> str | None:
        updated: dict[str, tuple[object, bytes]] = {}
        retained = 0
        digest = sha256(b"{")
        # The root has fixed ASCII keys. Each field uses the canonical encoder
        # or its previously encoded bytes for the identical source.
        for index, (name, value) in enumerate(sorted(inputs.to_canonical_dict().items())):
            if index:
                digest.update(b",")
            digest.update(canonical_bytes(name))
            digest.update(b":")
            if name in self._fields:
                source = getattr(inputs, name)
                previous = self._encoded.get(name)
                encoded = (previous[1] if previous is not None and self._same_source(source, previous[0])
                           else canonical_bytes(value))
                retained += len(encoded)
                if retained > self._byte_limit:
                    return None
                updated[name] = source, encoded
            else:
                encoded = canonical_bytes(value)
            digest.update(encoded)
        digest.update(b"}")
        self._encoded = updated
        return "sha256:" + digest.hexdigest()

    def project(self, inputs: CnASharePortfolioEconomicProjectionInputsV1) -> CnAShareEconomicProjectionOutcomeV1:
        return _project_economic_state_v1(inputs, self)


@dataclass(frozen=True, slots=True)
class CnAShareEconomicCashRowV1:
    key: CashBalanceKey
    ledger_cash: Money
    pending_cash: Money
    reserved_principal: Money
    reserved_fees: Money
    native_available: Money
    tax_liability: Money
    tax_hold: Money
    tax_shortfall: Money
    spendable: Money

    def __post_init__(self) -> None:
        _exact("key", self.key, CashBalanceKey)
        if self.key.currency_id != _CNY or self.key.venue_id.value not in {"xshg", "xshe"}:
            raise ValueError("cash row requires SH/SZ CNY key")
        for f in fields(self):
            if f.name != "key":
                _money(f.name, getattr(self, f.name))
        a = self.ledger_cash.units - self.pending_cash.units - self.reserved_principal.units - self.reserved_fees.units
        hold = min(a, self.tax_liability.units)
        if (self.native_available.units != a or self.tax_hold.units != hold
                or self.tax_shortfall.units != self.tax_liability.units - hold
                or self.spendable.units != a - hold):
            raise ValueError("cash row conservation mismatch")

    def to_canonical_dict(self) -> dict[str, object]:
        return _payload(self, "cn_a_share_economic_cash_row")


@dataclass(frozen=True, slots=True)
class CnASharePortfolioEconomicProjectionV1:
    account_id: str
    as_of: SimulationInstant
    native_source_hash: str
    dividend_state_hash: str
    base_snapshot: PortfolioSnapshot
    snapshot: PortfolioSnapshot
    gross_receivable: Money
    tax_liability: Money
    cash_rows: tuple[CnAShareEconomicCashRowV1, ...]
    spendable: Money
    tax_shortfall: Money
    buy_budget: Money

    def __post_init__(self) -> None:
        _text("account_id", self.account_id)
        _exact("as_of", self.as_of, SimulationInstant)
        for name in ("native_source_hash", "dividend_state_hash"):
            _hash(name, getattr(self, name))
        for name in ("base_snapshot", "snapshot"):
            _exact(name, getattr(self, name), PortfolioSnapshot)
        for name in ("gross_receivable", "tax_liability", "spendable", "tax_shortfall", "buy_budget"):
            _money(name, getattr(self, name))
        _money("base equity", self.base_snapshot.equity, nonnegative=False)
        _money("economic equity", self.snapshot.equity, nonnegative=False)
        if (self.base_snapshot.account_id != self.account_id or self.base_snapshot.timestamp != self.as_of.instant
                or self.base_snapshot.timestamp_instant != self.as_of
                or canonical_bytes(replace(self.snapshot, equity=self.base_snapshot.equity)) != canonical_bytes(self.base_snapshot)):
            raise ValueError("economic snapshot changes native context or fields other than equity")
        if self.snapshot.equity.units != self.base_snapshot.equity.units + self.gross_receivable.units - self.tax_liability.units:
            raise ValueError("economic equity conservation mismatch")
        _ordered("cash_rows", self.cash_rows, CnAShareEconomicCashRowV1, lambda r: r.key.venue_id.value)
        if len(self.cash_rows) != 2 or {r.key.venue_id.value for r in self.cash_rows} != {"xshg", "xshe"} or any(r.key.account_id != self.account_id for r in self.cash_rows):
            raise ValueError("economic cash rows must exact-cover both account venues")
        if any(getattr(self, name).units != sum(getattr(r, row_name).units for r in self.cash_rows)
               for name, row_name in (("tax_liability", "tax_liability"), ("spendable", "spendable"), ("tax_shortfall", "tax_shortfall"))):
            raise ValueError("economic cash row aggregate mismatch")
        if self.buy_budget.units != (self.spendable.units if self.tax_shortfall.units == 0 else 0):
            raise ValueError("buy budget must be zero for any tax shortfall")

    @property
    def projection_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return _payload(self, "cn_a_share_portfolio_economic_projection")


class CnAShareEconomicProjectionFailureCodeV1(str, Enum):
    CONTEXT_MISMATCH = "context_mismatch"
    FUTURE_NATIVE_FACT = "future_native_fact"
    DIVIDEND_STATE_MISMATCH = "dividend_state_mismatch"
    NATIVE_CASH_OVERCOMMITTED = "native_cash_overcommitted"
    NATIVE_SNAPSHOT_REJECTED = "native_snapshot_rejected"


@dataclass(frozen=True, slots=True)
class CnAShareEconomicProjectionFailureV1:
    code: CnAShareEconomicProjectionFailureCodeV1
    subject_hashes: tuple[str, ...]
    native_snapshot_failure: SnapshotProjectionFailure | None

    def __post_init__(self) -> None:
        _exact("code", self.code, CnAShareEconomicProjectionFailureCodeV1)
        _ordered("subject_hashes", self.subject_hashes, str, lambda h: h)
        for h in self.subject_hashes:
            _hash("subject hash", h)
        if self.code is CnAShareEconomicProjectionFailureCodeV1.NATIVE_SNAPSHOT_REJECTED:
            _exact("native_snapshot_failure", self.native_snapshot_failure, SnapshotProjectionFailure)
        elif self.native_snapshot_failure is not None:
            raise ValueError("only native snapshot rejection may carry native failure")

    def to_canonical_dict(self) -> dict[str, object]:
        return {**_payload(self, "cn_a_share_economic_projection_failure"), "code": self.code.value}


@dataclass(frozen=True, slots=True)
class CnAShareEconomicProjectionOutcomeV1:
    projection: CnASharePortfolioEconomicProjectionV1 | None
    failure: CnAShareEconomicProjectionFailureV1 | None

    def __post_init__(self) -> None:
        if (self.projection is None) == (self.failure is None):
            raise ValueError("economic outcome requires exactly one branch")
        if self.projection is not None:
            _exact("projection", self.projection, CnASharePortfolioEconomicProjectionV1)
        if self.failure is not None:
            _exact("failure", self.failure, CnAShareEconomicProjectionFailureV1)

    def to_canonical_dict(self) -> dict[str, object]:
        return _payload(self, "cn_a_share_economic_projection_outcome")


def _context_matches(value) -> bool:
    account = value.market_rules.account_id
    schema = value.ledger_schema
    cash = tuple(r for r in schema.cash_registrations)
    positions = tuple(r for r in schema.registrations if type(r.key) is PositionBalanceKey)
    catalog = value.instrument_catalog
    instruments = {d.instrument_id for d in catalog.instruments}
    return (value.dividend_state.account_id == account and value.settlement_book.account_id == account
        and len(cash) == 2 and {r.key.venue_id.value for r in cash} == {"xshg", "xshe"}
        and all(r.key.account_id == account for r in schema.registrations)
        and all(r.key.currency_id == _CNY and r.scale == _CENT for r in cash)
        and all(r.scale == Scale(0) and r.key.venue_id.value in {"xshg", "xshe"} for r in positions)
        and {r.key.instrument_id for r in positions} == instruments
        and _CNY in catalog.currencies
        and all(d.instrument_type is InstrumentType.EQUITY and d.quote_currency == _CNY and d.settlement_currency == _CNY for d in catalog.instruments)
        and {r.key for r in value.market_rules.cash_rules} == {r.key for r in cash}
        and {r.key for r in value.market_rules.position_rules} == {r.key for r in positions}
        and all(not r.pending_receivable_tradable and not r.pending_receivable_withdrawable
                and not r.pending_receivable_margin_eligible
                and set(r.tradable_reservation_uses) == {CashReservationUse.CASH, CashReservationUse.FEE_RESERVE}
                for r in value.market_rules.cash_rules)
        and all(c.instrument_id in instruments for c in value.dividend_state.claims)
        and all(s.order.account_id == account and s.order.intent.instrument_id in instruments for s in value.order_streams)
        and all(e.account_id == account for e in value.journal.entries))


def _future_native(value, *, marks: tuple[ResolvedMark, ...] = ()) -> bool:
    at = value.as_of
    return (any(e.recorded_at > at for e in value.journal.entries)
        or any(s.order.created_at > at or (s.state is not None and s.state.updated_at > at)
               or any(r.event.occurred_at > at for r in s.records) for s in value.order_streams)
        or any(e.occurred_at > at for e in value.settlement_book.events)
        or any(m.observed_at > at.instant or m.available_at_instant > at or m.resolved_at_instant > at for m in marks))


def _cash_components(value):
    """Keep each Order's currency-only reservation in its actual venue."""
    ledger = GenericLedger(value.ledger_schema).project(value.journal)
    settlement = value.settlement_book.project()
    cash_keys = tuple(sorted((r.key for r in value.ledger_schema.cash_registrations), key=lambda k: k.venue_id.value))
    rows = []
    all_keys = {r.key for r in value.ledger_schema.registrations}
    if any(p.balance_key not in all_keys for p in settlement.pending_obligations):
        raise ValueError("unregistered pending settlement balance")
    by_order = {s.order.order_id: s for s in value.order_streams}
    if any(s.order_id not in by_order for s in value.reservation_schedules):
        raise ValueError("reservation schedule has no Order source")
    for key in cash_keys:
        amount = ledger.cash_amount(key)
        _money("ledger cash", amount, nonnegative=False)
        pending = 0
        for p in settlement.pending_obligations:
            if p.balance_key == key:
                _money("pending cash", p.value)
                pending += p.value.units
        streams = tuple(s for s in value.order_streams if s.order.intent.instrument_id.venue == key.venue_id)
        order_ids = {s.order.order_id for s in streams}
        schedules = tuple(s for s in value.reservation_schedules if s.order_id in order_ids)
        totals = ResourceReservationBook(value.market_rules.account_id).project(streams, schedules).totals
        if totals.margin or totals.exposure_capacity:
            raise ValueError("cash dividend profile does not support margin reservations")
        def reserved(values):
            if len(values) > 1:
                raise ValueError("only CNY cash reservations supported")
            for v in values:
                _money("reserved cash", v)
            return sum(v.units for v in values)
        principal, fees = reserved(totals.cash), reserved(totals.fee_reserve)
        rows.append((key, amount.units, pending, principal, fees, amount.units - pending - principal - fees))
    return ledger, tuple(rows)


def project_cn_a_share_portfolio_economic_state_v1(
    inputs: CnASharePortfolioEconomicProjectionInputsV1,
) -> CnAShareEconomicProjectionOutcomeV1:
    return _project_economic_state_v1(inputs, None)


def _project_economic_state_v1(
    inputs: CnASharePortfolioEconomicProjectionInputsV1,
    memo: _ProjectionInputDigestMemoV1 | None,
) -> CnAShareEconomicProjectionOutcomeV1:
    _exact("inputs", inputs, CnASharePortfolioEconomicProjectionInputsV1)
    codes = CnAShareEconomicProjectionFailureCodeV1
    def fail(code, native=None):
        return CnAShareEconomicProjectionOutcomeV1(None, CnAShareEconomicProjectionFailureV1(
            code, (canonical_sha256(inputs),), native))
    graph = inputs.currency_valuation_graph
    if (not _context_matches(inputs) or graph.valuation_at != inputs.as_of.instant
            or graph.price_purpose is not PricePurpose.VALUATION or graph.edges):
        return fail(codes.CONTEXT_MISMATCH)
    if _future_native(inputs, marks=inputs.marks):
        return fail(codes.FUTURE_NATIVE_FACT)
    if inputs.dividend_state.as_of != inputs.as_of:
        return fail(codes.DIVIDEND_STATE_MISMATCH)
    ledger, components = _cash_components(inputs)
    if any(row[-1] < 0 for row in components):
        return fail(codes.NATIVE_CASH_OVERCOMMITTED)
    shared = project_cn_a_share_shared_cny_cash_v1(journal=inputs.journal,
        ledger_schema=inputs.ledger_schema, settlement_book=inputs.settlement_book,
        order_streams=inputs.order_streams, reservation_schedules=inputs.reservation_schedules,
        market_rules=inputs.market_rules, as_of=inputs.as_of.instant)
    if (shared.total.units, shared.unsettled_receivables.units, shared.reserved_principal.units,
            shared.reserved_fees.units, shared.spendable.units) != tuple(sum(r[i] for r in components) for i in range(1, 6)):
        raise ValueError("venue cash components disagree with native shared-cash projection")
    base = PortfolioSnapshotProjector().project_cash_ledger(ledger_state=ledger,
        resolved_marks=inputs.marks, reporting_currency=_CNY, reporting_scale=_CENT,
        projection_at=inputs.as_of, instrument_catalog=inputs.instrument_catalog,
        currency_valuation_graph=graph, notional_quantization=inputs.notional_quantization)
    if base.snapshot is None:
        return fail(codes.NATIVE_SNAPSHOT_REJECTED, base.failure)
    claims = inputs.dividend_state.claims
    gross = sum(c.recognized_gross.units - c.gross_paid.units for c in claims)
    tax = sum(c.tax_assessed.units - c.tax_settled.units for c in claims)
    rows = []
    for key, cash, pending, principal, fees, available in components:
        liability = sum(c.tax_assessed.units - c.tax_settled.units for c in claims if c.instrument_id.venue == key.venue_id)
        hold = min(available, liability)
        rows.append(CnAShareEconomicCashRowV1(key, *map(_cny,
            (cash, pending, principal, fees, available, liability, hold, liability - hold, available - hold))))
    spendable = sum(r.spendable.units for r in rows)
    shortfall = sum(r.tax_shortfall.units for r in rows)
    input_hash = canonical_sha256(inputs) if memo is None else memo.digest(inputs)
    projection = CnASharePortfolioEconomicProjectionV1(inputs.market_rules.account_id, inputs.as_of,
        input_hash, canonical_sha256(inputs.dividend_state), base.snapshot,
        replace(base.snapshot, equity=_cny(base.snapshot.equity.units + gross - tax)),
        _cny(gross), _cny(tax), tuple(rows), _cny(spendable), _cny(shortfall), _cny(spendable if shortfall == 0 else 0))
    return CnAShareEconomicProjectionOutcomeV1(projection, None)
