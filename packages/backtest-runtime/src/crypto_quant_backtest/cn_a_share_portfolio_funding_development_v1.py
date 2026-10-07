"""Synthetic-only candidate for an atomic pair of venue-local CNY funding facts.

This does NOT authorize broker transfers, fills, fees, real-data preparation, or
publication of a partial Journal. A portfolio provider must verify/publish the
entire candidate as one immutable economic input before execution is possible.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from crypto_quant_domain import (
    AccountingEntryType, AccountingJournalEntry, ArtifactEnvelope, ArtifactReadResult, ArtifactRef,
    BalanceChange, CashBalanceKey,
    CurrencyId, DomainId, DomainIdKind, Money, Scale, SimulationInstant,
    SourceSequence, canonical_bytes, canonical_sha256,
)
from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .artifact_envelope_reader import ArtifactEnvelopeReader

from crypto_quant_trading import (
    AccountingJournal, AvailabilityProjection, GenericLedger, LedgerSchema,
    LedgerState, MarketSettlementRules, OrderEventStream, OrderReservationSchedule,
    ResourceReservationBook, SettlementBook,
)


@dataclass(frozen=True, slots=True)
class SyntheticCrossVenueFundingCandidateV1:
    transfer_identity: str
    prior_journal_hash: str
    journal: AccountingJournal
    ledger_state: LedgerState
    synthetic_only: bool = field(default=True, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "synthetic_cn_cross_venue_funding_candidate", "schema_version": 1,
                "transfer_identity": self.transfer_identity, "prior_journal_hash": self.prior_journal_hash,
                "journal": self.journal, "ledger_state": self.ledger_state,
                "synthetic_only": True, "trade_authorized": False}

    def __post_init__(self) -> None:
        if (type(self.transfer_identity) is not str
                or re.fullmatch(r"sha256:[0-9a-f]{64}", self.transfer_identity) is None
                or type(self.prior_journal_hash) is not str
                or re.fullmatch(r"sha256:[0-9a-f]{64}", self.prior_journal_hash) is None):
            raise ValueError("synthetic funding identity must be canonical")
        if type(self.journal) is not AccountingJournal or type(self.ledger_state) is not LedgerState:
            raise TypeError("funding candidate must contain exact Journal and LedgerState")
        if (self.journal.entry_count < 2
                or self.journal.cursor_at(self.journal.entry_count - 2).prefix_hash != self.prior_journal_hash):
            raise ValueError("prior Journal prefix mismatch or missing transfer leg")
        debit, credit = self.journal.entries[-2:]
        if (debit.entry_type is not AccountingEntryType.CAPITAL_TRANSFERRED
                or credit.entry_type is not AccountingEntryType.CAPITAL_TRANSFERRED
                or len(debit.balance_changes) != 1 or len(credit.balance_changes) != 1
                or debit.source_ids != credit.source_ids
                or debit.recorded_at >= credit.recorded_at
                or debit.recorded_at.instant != credit.recorded_at.instant):
            raise ValueError("transfer must be an ordered linked two-leg pair")
        outgoing, incoming = debit.balance_changes[0], credit.balance_changes[0]
        if not isinstance(outgoing.value, Money) or not isinstance(incoming.value, Money):
            raise ValueError("transfer pair must contain CNY Money")
        if (type(outgoing.key) is not CashBalanceKey or type(incoming.key) is not CashBalanceKey
                or outgoing.key.account_id != incoming.key.account_id
                or {outgoing.key.venue_id.value, incoming.key.venue_id.value} != {"xshg", "xshe"}
                or outgoing.value.currency != "CNY" or incoming.value.currency != "CNY"
                or outgoing.value.scale != Scale(2) or incoming.value.scale != Scale(2)
                or outgoing.value.units >= 0 or incoming.value.units != -outgoing.value.units):
            raise ValueError("transfer pair must conserve CNY across two venues")
        if GenericLedger(self.ledger_state.schema).project(self.journal) != self.ledger_state:
            raise ValueError("funding candidate Ledger state mismatch")


def build_synthetic_cross_venue_funding_candidate_v1(
    *, prior_journal: AccountingJournal, ledger_schema: LedgerSchema,
    settlement_book: SettlementBook, reservation_streams: tuple[OrderEventStream, ...],
    reservation_schedules: tuple[OrderReservationSchedule, ...],
    settlement_rules: MarketSettlementRules, source_key: CashBalanceKey,
    destination_key: CashBalanceKey, amount: Money, transfer_key: str,
    at: SimulationInstant, expected_prior_hash: str,
) -> SyntheticCrossVenueFundingCandidateV1:
    """Fail closed; return *both* legs only after whole-Journal projection succeeds.

    This synthetic development candidate is deliberately not a public portfolio
    Backtest preparation operation. It uses exact Ledger/Settlement/Reservation
    values, not a caller-supplied `cash_available=True` or market-data API.
    """
    if (type(prior_journal) is not AccountingJournal or type(ledger_schema) is not LedgerSchema
            or type(settlement_book) is not SettlementBook or type(settlement_rules) is not MarketSettlementRules
            or type(reservation_streams) is not tuple or type(reservation_schedules) is not tuple
            or type(source_key) is not CashBalanceKey or type(destination_key) is not CashBalanceKey
            or type(amount) is not Money or type(at) is not SimulationInstant):
        raise TypeError("cross-venue funding requires exact frozen input values")
    if type(transfer_key) is not str or re.fullmatch(r"[a-z][a-z0-9._-]{0,63}", transfer_key) is None:
        raise ValueError("transfer_key must be a canonical local identity")
    if type(expected_prior_hash) is not str or prior_journal.journal_hash != expected_prior_hash:
        raise ValueError("prior Journal hash mismatch")
    if (source_key.account_id != destination_key.account_id
            or source_key.account_id != settlement_rules.account_id
            or source_key.account_id != settlement_book.account_id
            or {source_key.venue_id.value, destination_key.venue_id.value} != {"xshg", "xshe"}
            or source_key.currency_id != CurrencyId("CNY") or destination_key.currency_id != CurrencyId("CNY")
            or amount.currency != "CNY" or amount.scale != Scale(2) or amount.units <= 0):
        raise ValueError("cross-venue cash scope or positive CNY amount mismatch")
    if settlement_book.obligations or settlement_book.events or reservation_streams or reservation_schedules:
        raise ValueError("synthetic funding requires empty settlement and Order reservations")
    source_id = "synthetic-cross-venue:" + transfer_key
    if any(source_id in value.source_ids for value in prior_journal.entries):
        raise ValueError("transfer identity already appears in Journal")
    if any(value.entry_type is not AccountingEntryType.CAPITAL_DEPOSITED for value in prior_journal.entries):
        raise ValueError("synthetic funding requires initial capital-only Journal")
    # Reproject exact immutable sources; no assertion of available funds comes from the caller.
    ledger = GenericLedger(ledger_schema)
    before = ledger.project(prior_journal)
    availability = AvailabilityProjection().project(
        before, settlement_book.project(),
        ResourceReservationBook(source_key.account_id).project(reservation_streams, reservation_schedules),
        settlement_rules,
    )
    source_matches = [value for value in availability.cash if value.key == source_key]
    if len(source_matches) != 1 or before.cash_amount(destination_key).scale != amount.scale:
        raise ValueError("missing source or destination cash Scale mismatch")
    source = source_matches[0]
    if source.total.scale != amount.scale:
        raise ValueError("source cash Scale mismatch")
    if amount.units > min(source.total.units, source.settled.units, source.tradable.units):
        raise ValueError("source settled unreserved CNY is insufficient")
    if at.source_sequence.value >= 2**63 - 1:
        raise ValueError("funding leg SourceSequence cannot have a successor")
    identity = canonical_sha256({
        "type": "synthetic_cn_cross_venue_funding_candidate", "schema_version": 1,
        "transfer_key": transfer_key, "prior_journal_hash": expected_prior_hash,
        "availability_state_hash": availability.state_hash, "source_key": source_key,
        "destination_key": destination_key, "amount": amount, "recorded_at": at,
    })
    instants = (at, SimulationInstant(at.instant, at.phase, SourceSequence(at.source_sequence.value + 1)))
    entries = tuple(AccountingJournalEntry(
        DomainId(DomainIdKind.JOURNAL, "jnl_" + canonical_sha256({"identity": identity, "leg": leg})[7:]),
        AccountingEntryType.CAPITAL_TRANSFERRED, source_key.account_id, key.venue_id,
        at.instant, instant, (source_id,),
        (BalanceChange(key, Money(units, amount.scale, amount.currency)),), (), (), (),
    ) for leg, key, units, instant in (("debit", source_key, -amount.units, instants[0]),
                                      ("credit", destination_key, amount.units, instants[1])))
    journal = prior_journal.append_many(entries)
    after = ledger.project(journal)
    if (after.cash_amount(source_key).units != before.cash_amount(source_key).units - amount.units
            or after.cash_amount(destination_key).units != before.cash_amount(destination_key).units + amount.units):
        raise ValueError("cross-venue synthetic transfer did not conserve CNY")
    return SyntheticCrossVenueFundingCandidateV1(identity, expected_prior_hash, journal, after)


def read_retained_synthetic_cross_venue_funding_candidate_v1(
    ref: ArtifactRef, *, ledger_schema: LedgerSchema, reader: ArtifactEnvelopeReader,
) -> SyntheticCrossVenueFundingCandidateV1:
    """Rebuild a retained candidate from its own bytes; never an economic owner log.

    The schema is a separately frozen authority, not a caller-provided balance.
    A published owner head may call this when replaying linked whole-pair facts.
    """
    if type(ref) is not ArtifactRef or type(ledger_schema) is not LedgerSchema:
        raise TypeError("funding replay requires exact ref and frozen ledger schema")
    if not callable(getattr(reader, "read", None)):
        raise TypeError("funding replay requires reader")
    try:
        retained = reader.read(ref=ref)
    except Exception as error:
        raise RuntimeError("synthetic funding retention unavailable") from error
    if type(retained) is not ArtifactReadResult or ArtifactRef.from_envelope(retained.envelope) != ref:
        raise ValueError("funding ref does not bind retained source")
    envelope = retained.envelope
    if (envelope.artifact_type != "synthetic_cn_cross_venue_funding_candidate"
            or envelope.schema_version != 1 or not isinstance(envelope.payload, Mapping)
            or set(envelope.payload) != {"candidate"}
            or not isinstance(envelope.payload["candidate"], Mapping)):
        raise ValueError("retained funding schema mismatch")
    source = envelope.payload["candidate"]
    state = source.get("ledger_state")
    if (not isinstance(state, Mapping) or state.get("schema_hash") != ledger_schema.schema_hash):
        raise ValueError("retained funding LedgerSchema mismatch")
    # Reuse the canonical Backtest execution-case Journal reader, including
    # its strict entry/hash checks; never trust a decoded caller-side candidate.
    from .execution_inputs import _read_journal  # pyright: ignore[reportPrivateUsage]

    journal = _read_journal(source["journal"])
    candidate = SyntheticCrossVenueFundingCandidateV1(
        source["transfer_identity"], source["prior_journal_hash"],
        journal, GenericLedger(ledger_schema).project(journal),
    )
    expected = ArtifactEnvelope.create(
        "synthetic_cn_cross_venue_funding_candidate", 1, {"candidate": candidate},
    )
    if envelope != expected or retained.source_bytes != canonical_bytes(expected):
        raise ValueError("retained funding replay content mismatch")
    return candidate


def load_synthetic_cross_venue_funding_candidate_v1(
    ref: ArtifactRef, candidate: SyntheticCrossVenueFundingCandidateV1,
    *, reader: ArtifactEnvelopeReader,
) -> SyntheticCrossVenueFundingCandidateV1:
    """Read existing retained bytes without rewriting them; not economic admission."""
    if type(ref) is not ArtifactRef or type(candidate) is not SyntheticCrossVenueFundingCandidateV1:
        raise TypeError("synthetic funding load requires exact ref and candidate")
    if not callable(getattr(reader, "read", None)):
        raise TypeError("synthetic funding load requires reader")
    envelope = ArtifactEnvelope.create(
        "synthetic_cn_cross_venue_funding_candidate", 1, {"candidate": candidate},
    )
    if ArtifactRef.from_envelope(envelope) != ref:
        raise ValueError("funding ref does not bind complete candidate")
    try:
        retained = reader.read(ref=ref)
    except Exception as error:
        raise RuntimeError("synthetic funding retention unavailable") from error
    if (type(retained) is not ArtifactReadResult or retained.envelope != envelope
            or retained.source_bytes != canonical_bytes(envelope)
            or retained.source_hash != canonical_sha256(envelope)):
        raise ValueError("retained synthetic funding candidate mismatch")
    return candidate


def retain_synthetic_cross_venue_funding_candidate_v1(
    candidate: SyntheticCrossVenueFundingCandidateV1,
    *, reader: ArtifactEnvelopeReader, publisher: ArtifactEnvelopePublisher,
) -> ArtifactRef:
    """Retain and exact-readback ONE whole synthetic candidate; no owner-log evidence."""
    if type(candidate) is not SyntheticCrossVenueFundingCandidateV1:
        raise TypeError("synthetic funding requires exact candidate")
    if not callable(getattr(publisher, "put", None)):
        raise TypeError("synthetic funding retention requires publisher")
    envelope = ArtifactEnvelope.create(
        "synthetic_cn_cross_venue_funding_candidate", 1, {"candidate": candidate},
    )
    ref = ArtifactRef.from_envelope(envelope)
    try:
        actual = publisher.put(envelope=envelope)
    except Exception as error:
        raise RuntimeError("synthetic funding retention unavailable") from error
    if type(actual) is not ArtifactRef or actual != ref:
        raise ValueError("synthetic funding publisher ref mismatch")
    load_synthetic_cross_venue_funding_candidate_v1(ref, candidate, reader=reader)
    return ref
