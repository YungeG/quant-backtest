"""Synthetic-only cross-venue CNY funding candidate; never portfolio trade authority."""
from __future__ import annotations

from dataclasses import replace
import json
from typing import Any

import pytest

from crypto_quant_backtest.cn_a_share_portfolio_funding_development_v1 import (
    build_synthetic_cross_venue_funding_candidate_v1,
    load_synthetic_cross_venue_funding_candidate_v1,
    read_retained_synthetic_cross_venue_funding_candidate_v1,
    retain_synthetic_cross_venue_funding_candidate_v1,
)
from crypto_quant_backtest.cn_a_share_synthetic_funding_owner_v1 import (
    publish_synthetic_cn_funding_owner_v1, read_synthetic_cn_funding_owner_v1,
)
from crypto_quant_domain import (
    AccountingEntryType, AccountingJournalEntry, ArtifactEnvelope, ArtifactReadResult, ArtifactRef,
    BalanceChange, CashBalanceKey,
    CurrencyId, DomainId, DomainIdKind, Money, Scale, SimulationInstant,
    SourceSequence, TimelinePhase, UtcInstant, VenueId, canonical_bytes, canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal, AvailabilityEvidenceError, CashAvailabilityRule, CashReservationUse,
    GenericLedger, LedgerBalanceRegistration, LedgerSchema, MarketSettlementRules, SettlementBook,
)

ACCOUNT = "account:synthetic-portfolio"
CNY = CurrencyId("CNY")
SCALE = Scale(2)
SH = CashBalanceKey(ACCOUNT, VenueId("xshg"), CNY)
SZ = CashBalanceKey(ACCOUNT, VenueId("xshe"), CNY)
AT = SimulationInstant(UtcInstant(30), TimelinePhase(40, "accounting"), SourceSequence(1))


def fixture() -> dict[str, Any]:
    initial = AccountingJournalEntry(
        DomainId(DomainIdKind.JOURNAL, "jnl_" + "1" * 64),
        AccountingEntryType.CAPITAL_DEPOSITED, ACCOUNT, SH.venue_id,
        UtcInstant(9), SimulationInstant(UtcInstant(10), TimelinePhase(40, "accounting"), SourceSequence(1)),
        ("synthetic-initial-capital",), (BalanceChange(SH, Money(100_000, SCALE, "CNY")),),
        (), (), (),
    )
    journal = AccountingJournal.from_entries((initial,))
    schema = LedgerSchema((LedgerBalanceRegistration(SH, SCALE), LedgerBalanceRegistration(SZ, SCALE)))
    rules = MarketSettlementRules.create(
        policy_key="cn.synthetic.shsz.cash.v1", policy_version=1, account_id=ACCOUNT,
        cash_rules=tuple(CashAvailabilityRule(
            key=key, pending_receivable_tradable=False, pending_receivable_withdrawable=False,
            pending_receivable_margin_eligible=False,
            tradable_reservation_uses=(CashReservationUse.CASH, CashReservationUse.FEE_RESERVE),
            withdrawable_reservation_uses=(CashReservationUse.CASH, CashReservationUse.FEE_RESERVE),
            available_margin_reservation_uses=(),
        ) for key in (SH, SZ)), position_rules=(),
    )
    return dict(prior_journal=journal, ledger_schema=schema, settlement_book=SettlementBook(ACCOUNT),
                reservation_streams=(), reservation_schedules=(), settlement_rules=rules,
                source_key=SH, destination_key=SZ, amount=Money(40_000, SCALE, "CNY"),
                transfer_key="weekly-w1", at=AT, expected_prior_hash=journal.journal_hash)


def test_two_venue_candidate_is_balanced_and_deterministic_without_mutating_prior():
    args = fixture()
    result = build_synthetic_cross_venue_funding_candidate_v1(**args)
    assert result == build_synthetic_cross_venue_funding_candidate_v1(**args)
    assert result.prior_journal_hash == args["prior_journal"].journal_hash
    assert args["prior_journal"].entry_count == 1 and result.journal.entry_count == 3
    assert [entry.entry_type for entry in result.journal.entries[1:]] == [AccountingEntryType.CAPITAL_TRANSFERRED] * 2
    assert [entry.venue_id for entry in result.journal.entries[1:]] == [SH.venue_id, SZ.venue_id]
    assert result.ledger_state.cash_amount(SH) == Money(60_000, SCALE, "CNY")
    assert result.ledger_state.cash_amount(SZ) == Money(40_000, SCALE, "CNY")
    assert result.synthetic_only and not result.trade_authorized
    with pytest.raises(ValueError, match="already appears"):
        build_synthetic_cross_venue_funding_candidate_v1(
            **{**args, "prior_journal": result.journal, "expected_prior_hash": result.journal.journal_hash})
    with pytest.raises(ValueError, match="initial capital-only"):
        build_synthetic_cross_venue_funding_candidate_v1(
            **{**args, "prior_journal": result.journal, "expected_prior_hash": result.journal.journal_hash,
               "transfer_key": "second-transfer"})


@pytest.mark.parametrize(("mutation", "reason"), [
    ({"amount": Money(100_001, SCALE, "CNY")}, "insufficient"),
    ({"amount": Money(0, SCALE, "CNY")}, "positive CNY"),
    ({"expected_prior_hash": "sha256:" + "0" * 64}, "prior Journal hash mismatch"),
    ({"destination_key": SH}, "cash scope"),
    ({"at": SimulationInstant(UtcInstant(30), TimelinePhase(40, "accounting"), SourceSequence(2**63 - 1))}, "successor"),
])
def test_failing_leg_or_source_cannot_produce_a_partial_candidate(mutation, reason):
    args = fixture()
    with pytest.raises(ValueError, match=reason):
        build_synthetic_cross_venue_funding_candidate_v1(**{**args, **mutation})
    assert args["prior_journal"].entry_count == 1


def test_synthetic_candidate_rejects_partial_leg_imbalance_and_forged_projection():
    args = fixture()
    original = build_synthetic_cross_venue_funding_candidate_v1(**args)
    with pytest.raises(ValueError, match="prior Journal prefix mismatch"):
        replace(original, journal=AccountingJournal.from_entries(original.journal.entries[:-1]))
    credit = original.journal.entries[-1]
    altered = replace(credit, balance_changes=(BalanceChange(SZ, Money(40_001, SCALE, "CNY")),))
    with pytest.raises(ValueError, match="conserve CNY"):
        replace(original, journal=AccountingJournal.from_entries((*original.journal.entries[:-1], altered)))
    with pytest.raises(ValueError, match="Ledger state mismatch"):
        replace(original, ledger_state=GenericLedger(args["ledger_schema"]).project(args["prior_journal"]))


def test_nonempty_order_evidence_cannot_be_backdated_into_synthetic_funding():
    args = fixture()
    with pytest.raises(ValueError, match="empty settlement and Order reservations"):
        build_synthetic_cross_venue_funding_candidate_v1(**{**args, "reservation_schedules": (object(),)})
    assert args["prior_journal"].entry_count == 1


class _Cas:
    def __init__(self):
        self.values = {}

    def put(self, *, envelope):
        ref = ArtifactRef.from_envelope(envelope)
        self.values[ref] = envelope
        return ref

    def read(self, *, ref):
        envelope = self.values[ref]
        return ArtifactReadResult(envelope, None, canonical_bytes(envelope), canonical_sha256(envelope))


def test_retained_funding_replay_uses_source_bytes_and_independent_ledger_schema():
    args = fixture()
    candidate = build_synthetic_cross_venue_funding_candidate_v1(**args)
    store = _Cas()
    ref = retain_synthetic_cross_venue_funding_candidate_v1(candidate, reader=store, publisher=store)
    assert read_retained_synthetic_cross_venue_funding_candidate_v1(
        ref, ledger_schema=args["ledger_schema"], reader=store) == candidate
    wrong_schema = LedgerSchema((LedgerBalanceRegistration(SH, SCALE),))
    with pytest.raises(ValueError, match="LedgerSchema mismatch"):
        read_retained_synthetic_cross_venue_funding_candidate_v1(
            ref, ledger_schema=wrong_schema, reader=store)
    altered = build_synthetic_cross_venue_funding_candidate_v1(
        **{**args, "amount": Money(30_000, SCALE, "CNY")})
    store.values[ref] = ArtifactEnvelope.create(
        "synthetic_cn_cross_venue_funding_candidate", 1, {"candidate": altered})
    with pytest.raises(ValueError, match="ref does not bind"):
        read_retained_synthetic_cross_venue_funding_candidate_v1(
            ref, ledger_schema=args["ledger_schema"], reader=store)


def test_synthetic_owner_pointer_commits_one_complete_pair_and_replays(tmp_path):
    args = fixture()
    first = build_synthetic_cross_venue_funding_candidate_v1(**args)
    store = _Cas()
    ref = retain_synthetic_cross_venue_funding_candidate_v1(first, reader=store, publisher=store)
    with pytest.raises(FileNotFoundError):
        read_synthetic_cn_funding_owner_v1(
            publication_root=tmp_path, account_id=ACCOUNT,
            expected_record_hash="sha256:" + "0" * 64,
            ledger_schema=args["ledger_schema"], reader=store)
    path, record_hash = publish_synthetic_cn_funding_owner_v1(
        first, ref, publication_root=tmp_path, ledger_schema=args["ledger_schema"], reader=store)
    original = path.read_bytes()
    assert read_synthetic_cn_funding_owner_v1(
        publication_root=tmp_path, account_id=ACCOUNT, expected_record_hash=record_hash,
        ledger_schema=args["ledger_schema"], reader=store) == first
    assert publish_synthetic_cn_funding_owner_v1(
        first, ref, publication_root=tmp_path, ledger_schema=args["ledger_schema"], reader=store) == (path, record_hash)
    second = build_synthetic_cross_venue_funding_candidate_v1(
        **{**args, "amount": Money(30_000, SCALE, "CNY")})
    other = retain_synthetic_cross_venue_funding_candidate_v1(second, reader=store, publisher=store)
    with pytest.raises(ValueError, match="already committed"):
        publish_synthetic_cn_funding_owner_v1(
            second, other, publication_root=tmp_path, ledger_schema=args["ledger_schema"], reader=store)
    assert path.read_bytes() == original
    swapped = json.loads(original)
    swapped["candidate_ref"] = other.to_canonical_dict()
    swapped["journal_hash"] = second.journal.journal_hash
    swapped["transfer_identity"] = second.transfer_identity
    path.write_bytes(canonical_bytes(swapped))
    with pytest.raises(ValueError, match="owner (?:pointer|record) (?:hash|identity)"):
        read_synthetic_cn_funding_owner_v1(
            publication_root=tmp_path, account_id=ACCOUNT, expected_record_hash=record_hash,
            ledger_schema=args["ledger_schema"], reader=store)
    path.write_bytes(original[:-1])
    with pytest.raises(ValueError, match="canonical JSON"):
        read_synthetic_cn_funding_owner_v1(
            publication_root=tmp_path, account_id=ACCOUNT, expected_record_hash=record_hash,
            ledger_schema=args["ledger_schema"], reader=store)


def test_whole_synthetic_candidate_retention_is_one_cas_artifact_and_tamper_rejected():
    candidate = build_synthetic_cross_venue_funding_candidate_v1(**fixture())
    store = _Cas()
    ref = retain_synthetic_cross_venue_funding_candidate_v1(candidate, reader=store, publisher=store)
    assert retain_synthetic_cross_venue_funding_candidate_v1(candidate, reader=store, publisher=store) == ref
    assert len(store.values) == 1 and ref.artifact_type == "synthetic_cn_cross_venue_funding_candidate"
    assert store.values[ref].payload["candidate"]["journal"]["entries"]
    assert len(store.values[ref].payload["candidate"]["journal"]["entries"]) == 3
    alternate = build_synthetic_cross_venue_funding_candidate_v1(
        **{**fixture(), "amount": Money(30_000, SCALE, "CNY")})
    store.values[ref] = ArtifactEnvelope.create("synthetic_cn_cross_venue_funding_candidate", 1,
                                                {"candidate": alternate})
    with pytest.raises(ValueError, match="retained synthetic funding candidate mismatch"):
        load_synthetic_cross_venue_funding_candidate_v1(ref, candidate, reader=store)


def test_wrong_publisher_ref_never_returns_a_funding_artifact():
    candidate = build_synthetic_cross_venue_funding_candidate_v1(**fixture())
    class WrongPublisher:
        def put(self, *, envelope):
            return ArtifactRef("synthetic_cn_cross_venue_funding_candidate", 1, "sha256:" + "f" * 64)
    with pytest.raises(ValueError, match="publisher ref mismatch"):
        retain_synthetic_cross_venue_funding_candidate_v1(candidate, reader=_Cas(), publisher=WrongPublisher())


def test_destination_without_settlement_rule_fails_before_two_legs():
    args = fixture()
    prior = args["settlement_rules"]
    reduced = MarketSettlementRules.create(
        policy_key=prior.policy_key, policy_version=prior.policy_version,
        account_id=ACCOUNT, cash_rules=(prior.cash_rules[0],), position_rules=(),
    )
    with pytest.raises(AvailabilityEvidenceError, match="Cash rule coverage mismatch"):
        build_synthetic_cross_venue_funding_candidate_v1(**{**args, "settlement_rules": reduced})
    assert args["prior_journal"].entry_count == 1
