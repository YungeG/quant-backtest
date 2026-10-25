"""Declared dividend history verification and immutable native journal proposals."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import gcd

from crypto_quant_domain import (
    AccountingEntryType, AccountingJournalEntry, ArtifactRef, BalanceChange,
    CashBalanceKey, DomainId, DomainIdKind, InstrumentCatalog, InstrumentId,
    Money, PositionBalanceKey, QuantizationPolicy, RoundingPolicy, Scale,
    SimulationInstant, UtcInstant, canonical_bytes, canonical_sha256, round_ratio,
)
from crypto_quant_trading.journal import AccountingJournal
from crypto_quant_trading.ledger import GenericLedger, LedgerSchema
from crypto_quant_trading.orders import OrderEventStream
from crypto_quant_trading.reservations import OrderReservationSchedule
from crypto_quant_trading.settlement import MarketSettlementRules, SettlementBook
from .cash_dividend_projection_v1 import (
    CnAShareCashDividendClaimV1, CnAShareCashDividendStateV1,
    _CNY, _book_body_v1, _cash_components, _cny, _context_matches, _exact, _future_native,
    _hash, _instrument, _native_types, _ordered, _payload, _text,
)


def _quantization(name: str, value: QuantizationPolicy) -> None:
    _exact(name, value, QuantizationPolicy)
    _text(name + ".version", value.version)
    _exact(name + ".rounding", value.rounding, RoundingPolicy)
    _exact(name + ".target_scale", value.target_scale, Scale)
    if value.target_scale != Scale(2):
        raise ValueError("dividend quantization must target CNY cents")


@dataclass(frozen=True, slots=True)
class CnAShareCashDividendTaxPolicyV1:
    policy_id: str
    account_id: str
    mode: str
    numerator: int
    denominator: int
    quantization: QuantizationPolicy
    due_at: SimulationInstant | None

    def __post_init__(self) -> None:
        for name in ("policy_id", "account_id", "mode"):
            _text(name, getattr(self, name))
        for name in ("numerator", "denominator"):
            _exact(name, getattr(self, name), int)
        _quantization("quantization", self.quantization)
        if self.mode == "KNOWN_ZERO":
            if (self.numerator, self.denominator, self.due_at) != (0, 1, None):
                raise ValueError("known zero policy requires 0/1 and no due clock")
        elif self.mode == "FIXED_RATIO":
            _exact("due_at", self.due_at, SimulationInstant)
            if not 0 < self.numerator <= self.denominator <= 100_000_000 or gcd(self.numerator, self.denominator) != 1:
                raise ValueError("tax ratio must be reduced, positive, bounded and at most one")
        else:
            raise ValueError("unsupported dividend tax policy mode")

    def to_canonical_dict(self) -> dict[str, object]:
        return _payload(self, "cn_a_share_cash_dividend_tax_policy")


@dataclass(frozen=True, slots=True)
class CnAShareCashDividendActionV1:
    action_id: str
    instrument_id: InstrumentId
    registered_at: SimulationInstant
    entitlement_at: SimulationInstant
    payment_due_at: SimulationInstant
    cash_per_share: Money
    gross_quantization: QuantizationPolicy
    tax_policy: CnAShareCashDividendTaxPolicyV1
    fact_event_time: UtcInstant | None
    provider_available_at: UtcInstant | None
    acquired_at: UtcInstant | None
    source_evidence_refs: tuple[ArtifactRef, ...]

    def __post_init__(self) -> None:
        _text("action_id", self.action_id)
        _instrument(self.instrument_id)
        for name in ("registered_at", "entitlement_at", "payment_due_at"):
            _exact(name, getattr(self, name), SimulationInstant)
        if not self.registered_at < self.entitlement_at <= self.payment_due_at:
            raise ValueError("action clock order mismatch")
        _exact("cash_per_share", self.cash_per_share, Money)
        _exact("cash_per_share.units", self.cash_per_share.units, int)
        _exact("cash_per_share.scale", self.cash_per_share.scale, Scale)
        if self.cash_per_share.currency != "CNY" or self.cash_per_share.units <= 0 or not 0 <= self.cash_per_share.scale.places <= 8:
            raise ValueError("cash per share must retain positive CNY precision in scale 0..8")
        _quantization("gross_quantization", self.gross_quantization)
        _exact("tax_policy", self.tax_policy, CnAShareCashDividendTaxPolicyV1)
        if self.tax_policy.due_at is not None and self.tax_policy.due_at < self.entitlement_at:
            raise ValueError("tax due before entitlement")
        for name in ("fact_event_time", "provider_available_at", "acquired_at"):
            if getattr(self, name) is not None:
                _exact(name, getattr(self, name), UtcInstant)
        if self.fact_event_time is not None and self.provider_available_at is not None and self.provider_available_at < self.fact_event_time:
            raise ValueError("provider availability before fact event")
        _ordered("source_evidence_refs", self.source_evidence_refs, ArtifactRef,
                 lambda r: (r.artifact_type, r.schema_version, r.content_hash))
        if len(self.source_evidence_refs) > 16:
            raise ValueError("too many action source refs")

    def to_canonical_dict(self) -> dict[str, object]:
        return _payload(self, "cn_a_share_cash_dividend_action")


def _coordinates(action: CnAShareCashDividendActionV1):
    result = (("REGISTER", action.registered_at), ("ENTITLE", action.entitlement_at), ("PAY", action.payment_due_at))
    if action.tax_policy.mode == "FIXED_RATIO":
        result += (("TAX", action.tax_policy.due_at),)
    return result


@dataclass(frozen=True, slots=True)
class CnAShareCashDividendActionSetV1:
    account_id: str
    coverage_start: UtcInstant
    coverage_end_exclusive: UtcInstant
    declaration_basis: str
    actions: tuple[CnAShareCashDividendActionV1, ...]

    def __post_init__(self) -> None:
        _text("account_id", self.account_id)
        _exact("coverage_start", self.coverage_start, UtcInstant)
        _exact("coverage_end_exclusive", self.coverage_end_exclusive, UtcInstant)
        _exact("declaration_basis", self.declaration_basis, str)
        if self.coverage_start >= self.coverage_end_exclusive or self.declaration_basis != "MODEL_INPUTS_ONLY":
            raise ValueError("action set must declare finite model-input-only coverage")
        _ordered("actions", self.actions, CnAShareCashDividendActionV1, lambda a: (str(a.instrument_id), a.action_id))
        if len(self.actions) > 4096:
            raise ValueError("action count exceeds 4096")
        policies = {}
        clocks = set()
        for action in self.actions:
            policy = action.tax_policy
            if policy.account_id != self.account_id or not self.coverage_start <= action.registered_at.instant < self.coverage_end_exclusive:
                raise ValueError("action registration/account outside declared coverage")
            if policy.policy_id in policies and policies[policy.policy_id] != policy:
                raise ValueError("same policy identity names different content")
            policies[policy.policy_id] = policy
            for _, clock in _coordinates(action):
                if clock in clocks:
                    raise ValueError("model event clocks must be globally unique")
                clocks.add(clock)

    def to_canonical_dict(self) -> dict[str, object]:
        return _payload(self, "cn_a_share_cash_dividend_action_set")


@dataclass(frozen=True, slots=True)
class CnAShareCashDividendHistoryInputsV1:
    journal: AccountingJournal
    ledger_schema: LedgerSchema
    settlement_book: SettlementBook
    order_streams: tuple[OrderEventStream, ...]
    reservation_schedules: tuple[OrderReservationSchedule, ...]
    market_rules: MarketSettlementRules
    instrument_catalog: InstrumentCatalog
    dividend_state: CnAShareCashDividendStateV1
    action_set: CnAShareCashDividendActionSetV1
    journal_entry_ids: tuple[tuple[str, DomainId], ...]
    as_of: SimulationInstant

    def __post_init__(self) -> None:
        _native_types(self)
        _exact("instrument_catalog", self.instrument_catalog, InstrumentCatalog)
        _exact("dividend_state", self.dividend_state, CnAShareCashDividendStateV1)
        _exact("action_set", self.action_set, CnAShareCashDividendActionSetV1)
        _exact("journal_entry_ids", self.journal_entry_ids, tuple)
        if len(self.journal_entry_ids) > 8192:
            raise ValueError("journal ID mapping exceeds 8192")
        keys, ids = [], []
        for row in self.journal_entry_ids:
            _exact("journal ID row", row, tuple)
            if len(row) != 2:
                raise ValueError("journal ID row must have two fields")
            event_id, entry_id = row
            _hash("mapped event_id", event_id)
            _exact("journal entry ID", entry_id, DomainId)
            if entry_id.kind is not DomainIdKind.JOURNAL:
                raise ValueError("cash event mapping requires JOURNAL DomainId")
            keys.append(event_id)
            ids.append(entry_id)
        if any(a >= b for a, b in zip(keys, keys[1:])) or len(ids) != len(set(ids)):
            raise ValueError("journal mapping must be sorted and event/ID unique")

    def to_canonical_dict(self) -> dict[str, object]:
        return {**_payload(self, "cn_a_share_cash_dividend_history_inputs"),
                "settlement_book": _book_body_v1(self.settlement_book)}


@dataclass(frozen=True, slots=True)
class CnAShareCashDividendTransitionInputsV1:
    history: CnAShareCashDividendHistoryInputsV1
    action_id: str
    instrument_id: InstrumentId
    kind: str

    def __post_init__(self) -> None:
        _exact("history", self.history, CnAShareCashDividendHistoryInputsV1)
        _text("action_id", self.action_id)
        _instrument(self.instrument_id)
        _exact("kind", self.kind, str)
        if self.kind not in {"REGISTER", "ENTITLE", "PAY", "TAX"}:
            raise ValueError("unsupported dividend event kind")

    def to_canonical_dict(self) -> dict[str, object]:
        return _payload(self, "cn_a_share_cash_dividend_transition_inputs")


@dataclass(frozen=True, slots=True)
class CnAShareCashDividendTransitionV1:
    action_set_hash: str
    action_terms_hash: str
    tax_policy_hash: str
    kind: str
    event_id: str
    event_at: SimulationInstant
    payload_hash: str
    input_journal_hash: str
    input_state_hash: str
    journal_entries: tuple[AccountingJournalEntry, ...]
    output_journal_hash: str
    state_after: CnAShareCashDividendStateV1

    def __post_init__(self) -> None:
        for name in ("action_set_hash", "action_terms_hash", "tax_policy_hash", "event_id", "payload_hash",
                     "input_journal_hash", "input_state_hash", "output_journal_hash"):
            _hash(name, getattr(self, name))
        _exact("kind", self.kind, str)
        if self.kind not in {"REGISTER", "ENTITLE", "PAY", "TAX"}:
            raise ValueError("unsupported transition kind")
        _exact("event_at", self.event_at, SimulationInstant)
        _exact("state_after", self.state_after, CnAShareCashDividendStateV1)
        _exact("journal_entries", self.journal_entries, tuple)
        if len(self.journal_entries) > 1 or (self.kind in {"REGISTER", "ENTITLE"} and self.journal_entries):
            raise ValueError("invalid transition journal entry count")
        if self.state_after.as_of != self.event_at:
            raise ValueError("transition output clock mismatch")
        for entry in self.journal_entries:
            _exact("journal entry", entry, AccountingJournalEntry)
            expected = AccountingEntryType.CORPORATE_ACTION_CASH_PAID if self.kind == "PAY" else AccountingEntryType.CORPORATE_ACTION_TAX_PAID
            if entry.entry_type is not expected or entry.recorded_at != self.event_at:
                raise ValueError("transition entry type/clock mismatch")
        if not self.journal_entries and self.output_journal_hash != self.input_journal_hash:
            raise ValueError("empty transition changes journal hash")

    def to_canonical_dict(self) -> dict[str, object]:
        return _payload(self, "cn_a_share_cash_dividend_transition")


class CnAShareCashDividendTransitionFailureCodeV1(str, Enum):
    CONTEXT_MISMATCH = "context_mismatch"
    FUTURE_NATIVE_FACT = "future_native_fact"
    HISTORY_MISMATCH = "history_mismatch"
    EVENT_SEQUENCE_MISMATCH = "event_sequence_mismatch"
    NATIVE_CASH_OVERCOMMITTED = "native_cash_overcommitted"
    TAX_CASH_SHORTFALL = "tax_cash_shortfall"


@dataclass(frozen=True, slots=True)
class CnAShareCashDividendTransitionFailureV1:
    code: CnAShareCashDividendTransitionFailureCodeV1
    subject_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        _exact("code", self.code, CnAShareCashDividendTransitionFailureCodeV1)
        _ordered("subject_hashes", self.subject_hashes, str, lambda h: h)
        for h in self.subject_hashes:
            _hash("subject hash", h)

    def to_canonical_dict(self) -> dict[str, object]:
        return {**_payload(self, "cn_a_share_cash_dividend_transition_failure"), "code": self.code.value}


@dataclass(frozen=True, slots=True)
class CnAShareCashDividendTransitionOutcomeV1:
    transition: CnAShareCashDividendTransitionV1 | None
    failure: CnAShareCashDividendTransitionFailureV1 | None

    def __post_init__(self) -> None:
        if (self.transition is None) == (self.failure is None):
            raise ValueError("transition outcome requires exactly one branch")
        if self.transition is not None:
            _exact("transition", self.transition, CnAShareCashDividendTransitionV1)
        if self.failure is not None:
            _exact("failure", self.failure, CnAShareCashDividendTransitionFailureV1)

    def to_canonical_dict(self) -> dict[str, object]:
        return _payload(self, "cn_a_share_cash_dividend_transition_outcome")


def _event_id(action_set, action, kind, at):
    return canonical_sha256({"type": "cn_a_share_cash_dividend_event_coordinate", "schema_version": 1,
        "account_id": action_set.account_id, "instrument_id": action.instrument_id, "action_id": action.action_id,
        "action_set_hash": canonical_sha256(action_set), "action_terms_hash": canonical_sha256(action),
        "tax_policy_hash": canonical_sha256(action.tax_policy), "kind": kind, "event_at": at})


def _events(action_set):
    return tuple(sorted(((at, kind, action, _event_id(action_set, action, kind, at))
        for action in action_set.actions for kind, at in _coordinates(action)), key=lambda row: row[0]))


def _journal_prefix(journal, at, *, inclusive):
    n = sum(e.recorded_at <= at if inclusive else e.recorded_at < at for e in journal.entries)
    return AccountingJournal(journal.replay(stop=journal.cursor_at(n)).entries)


def _historical_sources(inputs, at):
    journal = _journal_prefix(inputs.journal, at, inclusive=False)
    streams = tuple(OrderEventStream(s.order, tuple(r for r in s.records if r.event.occurred_at < at))
        for s in inputs.order_streams if s.order.created_at < at)
    ids = {s.order.order_id: {r.event.event_id for r in s.records} for s in streams}
    schedules = tuple(replace(s, updates=tuple(u for u in s.updates if u.event_id in ids[s.order_id]))
        for s in inputs.reservation_schedules if s.order_id in ids)
    events = tuple(e for e in inputs.settlement_book.events if e.occurred_at < at)
    obligation_ids = {e.settlement_obligation_id for e in events}
    obligations = tuple(o for o in inputs.settlement_book.obligations
                        if o.obligation.settlement_obligation_id in obligation_ids)
    book = SettlementBook(inputs.settlement_book.account_id, obligations, events)
    return replace(inputs, journal=journal, order_streams=streams, reservation_schedules=schedules,
                   settlement_book=book, as_of=at)


def _amounts(action, quantity):
    gross = round_ratio(quantity * action.cash_per_share.units * 100,
                        action.cash_per_share.scale.factor, action.gross_quantization.rounding)
    tax = 0 if action.tax_policy.mode == "KNOWN_ZERO" else round_ratio(
        gross * action.tax_policy.numerator, action.tax_policy.denominator, action.tax_policy.quantization.rounding)
    return gross, tax


def _apply_event(inputs, action, kind, at, event_id, claims):
    """Reconstruct a single declaration from the registration journal prefix."""
    key = (str(action.instrument_id), action.action_id)
    claim = claims.get(key)
    if kind == "REGISTER":
        prefix = _journal_prefix(inputs.journal, at, inclusive=True)
        quantity = GenericLedger(inputs.ledger_schema).project(prefix).position_quantity(
            PositionBalanceKey(inputs.action_set.account_id, action.instrument_id.venue, action.instrument_id))
        if quantity.scale != Scale(0) or quantity.units < 0:
            return None
        entitled_quantity, record_journal_hash = quantity.units, prefix.journal_hash
    elif claim is None:
        return None
    else:
        entitled_quantity, record_journal_hash = claim.entitled_quantity, claim.record_journal_hash
    gross, tax = _amounts(action, entitled_quantity)
    entry_id = dict(inputs.journal_entry_ids).get(event_id) if kind in {"PAY", "TAX"} else None
    payload_hash = canonical_sha256({"type": "cn_a_share_cash_dividend_event_payload", "schema_version": 1,
        "event_id": event_id, "kind": kind, "event_at": at, "action_set_hash": canonical_sha256(inputs.action_set),
        "action_terms_hash": canonical_sha256(action), "tax_policy_hash": canonical_sha256(action.tax_policy),
        "record_journal_hash": record_journal_hash, "entitled_quantity": entitled_quantity,
        "gross_entitlement": _cny(gross), "tax_entitlement": _cny(tax), "journal_entry_id": entry_id})
    applied = (kind, event_id, at, payload_hash)
    if kind == "REGISTER":
        claim = CnAShareCashDividendClaimV1(inputs.action_set.account_id, action.action_id, action.instrument_id,
            canonical_sha256(action), canonical_sha256(action.tax_policy), record_journal_hash,
            action.registered_at, action.entitlement_at, action.payment_due_at, entitled_quantity,
            "KNOWN_ZERO" if action.tax_policy.mode == "KNOWN_ZERO" else "KNOWN_AMOUNT", action.tax_policy.due_at,
            _cny(0), _cny(0), _cny(0), _cny(0), (applied,))
    else:
        updates = {"applied_events": (*claim.applied_events, applied)}
        if kind == "ENTITLE":
            updates.update(recognized_gross=_cny(gross), tax_assessed=_cny(tax))
        elif kind == "PAY":
            updates.update(gross_paid=_cny(gross))
        else:
            updates.update(tax_settled=_cny(tax))
        claim = replace(claim, **updates)
    entries = ()
    units = gross if kind == "PAY" else -tax if kind == "TAX" else 0
    if units:
        source_ids = tuple(sorted((canonical_sha256(inputs.action_set), canonical_sha256(action),
            canonical_sha256(action.tax_policy), claim.record_journal_hash, event_id, payload_hash)))
        entries = (AccountingJournalEntry(entry_id,
            AccountingEntryType.CORPORATE_ACTION_CASH_PAID if kind == "PAY" else AccountingEntryType.CORPORATE_ACTION_TAX_PAID,
            inputs.action_set.account_id, action.instrument_id.venue, at.instant, at, source_ids,
            (BalanceChange(CashBalanceKey(inputs.action_set.account_id, action.instrument_id.venue, _CNY), _cny(units)),),
            (), (), ()),)
    return claim, entries, payload_hash


def _failure(code, inputs):
    return CnAShareCashDividendTransitionFailureV1(code, (canonical_sha256(inputs),))


def verify_cn_a_share_cash_dividend_history_v1(
    inputs: CnAShareCashDividendHistoryInputsV1,
) -> CnAShareCashDividendTransitionFailureV1 | None:
    _exact("inputs", inputs, CnAShareCashDividendHistoryInputsV1)
    codes = CnAShareCashDividendTransitionFailureCodeV1
    instruments = {d.instrument_id for d in inputs.instrument_catalog.instruments}
    if (not _context_matches(inputs) or inputs.action_set.account_id != inputs.market_rules.account_id
            or any(a.instrument_id not in instruments for a in inputs.action_set.actions)):
        return _failure(codes.CONTEXT_MISMATCH, inputs)
    if _future_native(inputs) or inputs.dividend_state.as_of > inputs.as_of:
        return _failure(codes.FUTURE_NATIVE_FACT, inputs)
    events = _events(inputs.action_set)
    if {r[0] for r in inputs.journal_entry_ids} != {eid for _, k, _, eid in events if k in {"PAY", "TAX"}}:
        return _failure(codes.HISTORY_MISMATCH, inputs)
    claims, expected_entries = {}, []
    for at, kind, action, event_id in events:
        if at > inputs.dividend_state.as_of:
            break
        applied = _apply_event(inputs, action, kind, at, event_id, claims)
        if applied is None:
            return _failure(codes.HISTORY_MISMATCH, inputs)
        claim, entries, _ = applied
        if kind == "TAX":
            _, rows = _cash_components(_historical_sources(inputs, at))
            available = next(r[-1] for r in rows if r[0].venue_id == action.instrument_id.venue)
            if available < claim.tax_settled.units or any(r[-1] < 0 for r in rows):
                return _failure(codes.HISTORY_MISMATCH, inputs)
        claims[(str(action.instrument_id), action.action_id)] = claim
        expected_entries.extend(entries)
    expected_state = CnAShareCashDividendStateV1(inputs.action_set.account_id, inputs.dividend_state.as_of,
                                              tuple(claims[k] for k in sorted(claims)))
    action_types = {AccountingEntryType.CORPORATE_ACTION_CASH_PAID, AccountingEntryType.CORPORATE_ACTION_TAX_PAID,
                    AccountingEntryType.CORPORATE_ACTION_ENTITLEMENT_BOOKED, AccountingEntryType.CORPORATE_ACTION_POSITION_ADJUSTED}
    actual = tuple(e for e in inputs.journal.entries if e.entry_type in action_types)
    if canonical_bytes(actual) != canonical_bytes(tuple(expected_entries)) or canonical_bytes(expected_state) != canonical_bytes(inputs.dividend_state):
        return _failure(codes.HISTORY_MISMATCH, inputs)
    return None


def transition_cn_a_share_cash_dividend_v1(
    inputs: CnAShareCashDividendTransitionInputsV1,
) -> CnAShareCashDividendTransitionOutcomeV1:
    _exact("inputs", inputs, CnAShareCashDividendTransitionInputsV1)
    h = inputs.history
    codes = CnAShareCashDividendTransitionFailureCodeV1
    failure = verify_cn_a_share_cash_dividend_history_v1(h)
    if failure is not None:
        return CnAShareCashDividendTransitionOutcomeV1(None, failure)
    events = _events(h.action_set)
    requested = tuple(row for row in events if row[1] == inputs.kind and row[2].action_id == inputs.action_id
                      and row[2].instrument_id == inputs.instrument_id and row[0] == h.as_of)
    def fail(code):
        return CnAShareCashDividendTransitionOutcomeV1(None, _failure(code, inputs))
    if len(requested) != 1:
        return fail(codes.EVENT_SEQUENCE_MISMATCH)
    at, kind, action, event_id = requested[0]
    claims = {(str(c.instrument_id), c.action_id): c for c in h.dividend_state.claims}
    applied_event = next((e for c in h.dividend_state.claims for e in c.applied_events if e[1] == event_id), None)
    if applied_event is not None:
        if h.dividend_state.as_of != at:
            return fail(codes.EVENT_SEQUENCE_MISMATCH)
        entries, state, payload_hash = (), h.dividend_state, applied_event[3]
        output_hash = h.journal.journal_hash
    else:
        remaining = tuple(row for row in events if row[0] > h.dividend_state.as_of)
        if not remaining or remaining[0] != requested[0] or h.dividend_state.as_of >= h.as_of:
            return fail(codes.EVENT_SEQUENCE_MISMATCH)
        _, rows = _cash_components(h)
        if any(r[-1] < 0 for r in rows):
            return fail(codes.NATIVE_CASH_OVERCOMMITTED)
        if kind == "TAX":
            claim = claims[(str(action.instrument_id), action.action_id)]
            available = next(r[-1] for r in rows if r[0].venue_id == action.instrument_id.venue)
            if claim.tax_assessed.units - claim.tax_settled.units > available:
                return fail(codes.TAX_CASH_SHORTFALL)
        result = _apply_event(h, action, kind, at, event_id, claims)
        if result is None:
            return fail(codes.HISTORY_MISMATCH)
        claim, entries, payload_hash = result
        claims[(str(action.instrument_id), action.action_id)] = claim
        state = CnAShareCashDividendStateV1(h.action_set.account_id, at, tuple(claims[k] for k in sorted(claims)))
        output_hash = h.journal.append_many(entries).journal_hash
    transition = CnAShareCashDividendTransitionV1(canonical_sha256(h.action_set), canonical_sha256(action),
        canonical_sha256(action.tax_policy), kind, event_id, at, payload_hash, h.journal.journal_hash,
        canonical_sha256(h.dividend_state), entries, output_hash, state)
    return CnAShareCashDividendTransitionOutcomeV1(transition, None)
