from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, replace

import pytest

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    CashBalanceKey,
    DomainId,
    DomainIdKind,
    IdentityNamespace,
    InstrumentId,
    Price,
    PricePurpose,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    derive_domain_id,
)
from crypto_quant_trading import (
    FundingSlotId,
    LinearFundingApplicationIdentity,
    LinearFundingApplicationKey,
    LinearFundingEligibility,
    LinearFundingAccounting,
    LinearFundingEligibilityRequest,
    LinearFundingEligibilityResolver,
    LinearFundingJournalEntry,
    LinearFundingJournalProjector,
    LinearFundingJournalReplayFailureCode,
    LinearFundingJournalReplayRequest,
    LinearFundingMarkEvidence,
    LinearFundingSettlementEvidence,
    LinearFundingSettlementFailureCode,
    LinearFundingSettlementRequest,
    AccountingJournal,
    JournalEntryConflictError,
    LedgerBalanceRegistration,
    LedgerSchema,
    ResolvedMark,
    StaleMarkPolicy,
)

from tests.kernel.derivatives._fixtures import (
    ACCOUNT_ID,
    INSTRUMENT_ID,
    PRICE_SCALE,
    QUOTE_CURRENCY,
    VENUE_ID,
    contract,
    position_key,
)
from tests.kernel.derivatives.test_linear_funding_eligibility import (
    _instant as _eligibility_instant,
    _publication,
    _snapshot,
    _valid_request,
)


def _instant(nanoseconds: int) -> SimulationInstant:
    return SimulationInstant(
        UtcInstant(nanoseconds),
        TimelinePhase(100, "funding_settlement"),
        SourceSequence(0),
    )


def _eligibility(rate_units: int = 1) -> LinearFundingEligibility:
    request = _valid_request()
    publication = replace(
        request.publications[-1],
        published_rate=Rate(
            rate_units, Scale(4), "funding_fraction_of_notional"
        ),
    )
    outcome = LinearFundingEligibilityResolver().resolve(
        replace(request, publications=(publication,))
    )
    assert outcome.result is not None
    return outcome.result


def _eligibility_at(
    target_nanoseconds: int, rate_units: int
) -> LinearFundingEligibility:
    target = UtcInstant(target_nanoseconds)
    instant = _eligibility_instant(
        target_nanoseconds, 100, "funding_eligibility"
    )
    slot = FundingSlotId.derive(INSTRUMENT_ID, target)
    request = LinearFundingEligibilityRequest(
        slot_id=slot,
        position_key=position_key(),
        contract=contract(),
        eligibility_instant=instant,
        publications=(
            _publication(
                slot,
                rate=Rate(
                    rate_units, Scale(4), "funding_fraction_of_notional"
                ),
                event_time=target,
                available_at=_eligibility_instant(
                    target_nanoseconds, 50, "funding_publication"
                ),
            ),
        ),
        position_snapshot=_snapshot(
            slot,
            instant,
            available_at=_eligibility_instant(8, 20, "position_snapshot"),
        ),
        captured_at=_eligibility_instant(9, 0, "capture"),
    )
    outcome = LinearFundingEligibilityResolver().resolve(request)
    assert outcome.result is not None
    return outcome.result


def _identity(eligibility: LinearFundingEligibility) -> LinearFundingApplicationIdentity:
    return LinearFundingApplicationIdentity.derive(
        LinearFundingApplicationKey.derive(ACCOUNT_ID, eligibility.slot_id),
        IdentityNamespace("synthetic-funding", "1"),
        "synthetic-linear-funding-run",
    )


def test_application_key_is_exactly_account_and_funding_slot() -> None:
    slot = FundingSlotId.derive(INSTRUMENT_ID, UtcInstant(3))

    key = LinearFundingApplicationKey.derive(ACCOUNT_ID, slot)

    assert key.account_id == ACCOUNT_ID
    assert key.funding_slot_id == slot
    assert key.value == (
        "funding-application-v1:"
        "59b56bbbf2bf0a3259974ea46c05bd81fb963047ca8ca65a6215cd22a6b7cda8"
    )
    with pytest.raises(ValueError, match="semantic key"):
        LinearFundingApplicationKey(
            ACCOUNT_ID, slot, "funding-application-v1:" + "0" * 64
        )


def test_application_identity_derives_settlement_and_journal_ids() -> None:
    slot = FundingSlotId.derive(INSTRUMENT_ID, UtcInstant(3))
    key = LinearFundingApplicationKey.derive(ACCOUNT_ID, slot)
    namespace = IdentityNamespace("synthetic-funding", "1")
    semantic_run_id = "synthetic-linear-funding-run"

    identity = LinearFundingApplicationIdentity.derive(
        key, namespace, semantic_run_id
    )

    assert identity.settlement_id == derive_domain_id(
        namespace=namespace,
        kind=DomainIdKind.SETTLEMENT,
        semantic_run_id=semantic_run_id,
        semantic_key=key.value.encode("utf-8"),
        ordinal=0,
    )
    assert identity.journal_entry_id == derive_domain_id(
        namespace=namespace,
        kind=DomainIdKind.JOURNAL,
        semantic_run_id=semantic_run_id,
        semantic_key=key.value.encode("utf-8"),
        ordinal=0,
    )
    assert identity.to_canonical_dict()["identity_namespace"] == {
        "value": namespace.value,
        "version": namespace.version,
        "algorithm": namespace.algorithm,
    }
    with pytest.raises(ValueError, match="derived IDs"):
        LinearFundingApplicationIdentity(
            key,
            namespace,
            semantic_run_id,
            identity.settlement_id,
            derive_domain_id(
                namespace=namespace,
                kind=DomainIdKind.JOURNAL,
                semantic_run_id=semantic_run_id,
                semantic_key=b"forged",
                ordinal=0,
            ),
        )


def test_mark_and_settlement_evidence_preserve_authoritative_inputs() -> None:
    eligibility = _eligibility()
    identity = _identity(eligibility)
    policy = StaleMarkPolicy(
        "synthetic.funding-mark.v1", 1, PricePurpose.FUNDING, 10, True
    )
    resolved_mark = ResolvedMark(
        instrument_id=INSTRUMENT_ID,
        quote_currency_id=QUOTE_CURRENCY,
        price_purpose=PricePurpose.FUNDING,
        price=Price(
            10_000,
            PRICE_SCALE,
            str(INSTRUMENT_ID),
            str(QUOTE_CURRENCY),
        ),
        observed_at=UtcInstant(1),
        available_at=UtcInstant(2),
        resolved_at=eligibility.slot_id.target_funding_time,
        age_nanoseconds=2,
        stream_id="synthetic.funding-mark.stream.v1",
        source_event_id="funding-mark-event-root",
        revision_id="funding-mark-revision-root",
        stale_policy_key=policy.policy_key,
        stale_policy_version=policy.policy_version,
        stale_policy_hash=policy.policy_hash,
    )

    mark_evidence = LinearFundingMarkEvidence(resolved_mark, policy)
    settlement_evidence = LinearFundingSettlementEvidence(
        application_key=identity.application_key,
        effective_time=eligibility.slot_id.target_funding_time,
        applied_at=_instant(10),
        applied_rate=eligibility.published_rate,
        event_id="funding-settlement-event-root",
        event_hash="sha256:" + "3" * 64,
        revision_id="funding-settlement-revision-root",
        supersedes_revision_id=None,
        source_key="synthetic.funding.settlement.v1",
        source_hash="sha256:" + "4" * 64,
    )

    assert mark_evidence.resolved_mark is resolved_mark
    assert mark_evidence.stale_policy is policy
    assert settlement_evidence.application_key == identity.application_key
    assert settlement_evidence.applied_rate == eligibility.published_rate
    assert settlement_evidence.applied_at == _instant(10)


def _mark_evidence(eligibility: LinearFundingEligibility) -> LinearFundingMarkEvidence:
    policy = StaleMarkPolicy(
        "synthetic.funding-mark.v1", 1, PricePurpose.FUNDING, 10, True
    )
    return LinearFundingMarkEvidence(
        ResolvedMark(
            instrument_id=INSTRUMENT_ID,
            quote_currency_id=QUOTE_CURRENCY,
            price_purpose=PricePurpose.FUNDING,
            price=Price(
                10_000,
                PRICE_SCALE,
                str(INSTRUMENT_ID),
                str(QUOTE_CURRENCY),
            ),
            observed_at=UtcInstant(1),
            available_at=UtcInstant(2),
            resolved_at=eligibility.slot_id.target_funding_time,
            age_nanoseconds=(
                eligibility.slot_id.target_funding_time.epoch_nanoseconds - 1
            ),
            stream_id="synthetic.funding-mark.stream.v1",
            source_event_id="funding-mark-event-root",
            revision_id="funding-mark-revision-root",
            stale_policy_key=policy.policy_key,
            stale_policy_version=policy.policy_version,
            stale_policy_hash=policy.policy_hash,
        ),
        policy,
    )


def _settlement_evidence(
    eligibility: LinearFundingEligibility,
    identity: LinearFundingApplicationIdentity,
) -> LinearFundingSettlementEvidence:
    return LinearFundingSettlementEvidence(
        application_key=identity.application_key,
        effective_time=eligibility.slot_id.target_funding_time,
        applied_at=_instant(10),
        applied_rate=eligibility.published_rate,
        event_id="funding-settlement-event-root",
        event_hash="sha256:" + "3" * 64,
        revision_id="funding-settlement-revision-root",
        supersedes_revision_id=None,
        source_key="synthetic.funding.settlement.v1",
        source_hash="sha256:" + "4" * 64,
    )


def _settlement_request(
    rate_units: int = 8,
    rounding: RoundingPolicy = RoundingPolicy.HALF_EVEN,
    target_nanoseconds: int = 3,
) -> LinearFundingSettlementRequest:
    eligibility = (
        _eligibility(rate_units)
        if target_nanoseconds == 3
        else _eligibility_at(target_nanoseconds, rate_units)
    )
    identity = _identity(eligibility)
    return LinearFundingSettlementRequest(
        eligibility=eligibility,
        settlement_evidence=_settlement_evidence(eligibility, identity),
        funding_mark_evidence=_mark_evidence(eligibility),
        application_identity=identity,
        position_key=position_key(),
        contract=contract(),
        settlement_cash_registration=LedgerBalanceRegistration(
            CashBalanceKey(ACCOUNT_ID, VENUE_ID, QUOTE_CURRENCY), Scale(2)
        ),
        payment_quantization=QuantizationPolicy(
            "synthetic.funding-payment.v1", Scale(2), rounding
        ),
    )


def test_settlement_uses_historical_quantity_and_one_money_boundary() -> None:
    request = _settlement_request()

    outcome = LinearFundingAccounting().assess_financing(request)

    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert result.application_key == request.application_identity.application_key
    assert result.exact_cash_flow.numerator == -1
    assert result.exact_cash_flow.denominator == 50
    assert result.payment.units == -2
    assert result.payment.scale == Scale(2)
    assert type(result.journal_entry) is LinearFundingJournalEntry
    assert result.journal_entry.entry_type is AccountingEntryType.FUNDING_APPLIED
    assert result.journal_entry.balance_changes[0].value == result.payment
    assert result.journal_entry.financing == (result.payment,)
    assert not result.journal_entry.realized_pnl
    assert not result.journal_entry.fees


def _with_mark(
    request: LinearFundingSettlementRequest, resolved_mark: ResolvedMark
) -> LinearFundingSettlementRequest:
    evidence = request.funding_mark_evidence
    assert evidence is not None
    return replace(
        request,
        funding_mark_evidence=replace(evidence, resolved_mark=resolved_mark),
    )


def _failure_cases() -> list[
    tuple[LinearFundingSettlementFailureCode, LinearFundingSettlementRequest]
]:
    request = _settlement_request()
    eligibility = request.eligibility
    settlement = request.settlement_evidence
    evidence = request.funding_mark_evidence
    assert eligibility is not None and settlement is not None and evidence is not None
    mark = evidence.resolved_mark
    other_slot = FundingSlotId.derive(INSTRUMENT_ID, UtcInstant(4))
    other_key = LinearFundingApplicationKey.derive(ACCOUNT_ID, other_slot)
    other_instrument = InstrumentId(VENUE_ID, "eth-usdt-linear-perpetual")
    forged_late_mark = deepcopy(mark)
    object.__setattr__(forged_late_mark, "available_at", UtcInstant(11))
    return [
        (
            LinearFundingSettlementFailureCode.MISSING_ELIGIBILITY,
            replace(request, eligibility=None),
        ),
        (
            LinearFundingSettlementFailureCode.MISSING_SETTLEMENT_EVIDENCE,
            replace(request, settlement_evidence=None),
        ),
        (
            LinearFundingSettlementFailureCode.MISSING_FUNDING_MARK,
            replace(request, funding_mark_evidence=None),
        ),
        (
            LinearFundingSettlementFailureCode.SLOT_CONTEXT_MISMATCH,
            replace(
                request,
                settlement_evidence=replace(settlement, application_key=other_key),
            ),
        ),
        (
            LinearFundingSettlementFailureCode.POSITION_CONTEXT_MISMATCH,
            replace(
                request,
                position_key=replace(request.position_key, account_id="other-account"),
            ),
        ),
        (
            LinearFundingSettlementFailureCode.UNSUPPORTED_RATE_BASIS,
            replace(
                request,
                settlement_evidence=replace(
                    settlement,
                    applied_rate=Rate(8, Scale(4), "other-rate-basis"),
                ),
            ),
        ),
        (
            LinearFundingSettlementFailureCode.APPLIED_RATE_MISMATCH,
            replace(
                request,
                settlement_evidence=replace(
                    settlement,
                    applied_rate=Rate(
                        7, Scale(4), "funding_fraction_of_notional"
                    ),
                ),
            ),
        ),
        (
            LinearFundingSettlementFailureCode.INVALID_SETTLEMENT_EFFECTIVE_TIME,
            replace(
                request,
                settlement_evidence=replace(
                    settlement, effective_time=UtcInstant(4)
                ),
            ),
        ),
        (
            LinearFundingSettlementFailureCode.SETTLEMENT_EVIDENCE_NOT_AVAILABLE,
            replace(
                request,
                settlement_evidence=replace(settlement, applied_at=_instant(8)),
            ),
        ),
        (
            LinearFundingSettlementFailureCode.FUNDING_MARK_PURPOSE_MISMATCH,
            _with_mark(request, replace(mark, price_purpose=PricePurpose.SETTLEMENT)),
        ),
        (
            LinearFundingSettlementFailureCode.FUNDING_MARK_CONTEXT_MISMATCH,
            _with_mark(
                request,
                replace(
                    mark,
                    instrument_id=other_instrument,
                    price=Price(
                        mark.price.units,
                        mark.price.scale,
                        str(other_instrument),
                        str(QUOTE_CURRENCY),
                    ),
                ),
            ),
        ),
        (
            LinearFundingSettlementFailureCode.FUNDING_MARK_INSTANT_MISMATCH,
            _with_mark(
                request,
                replace(mark, resolved_at=UtcInstant(4), age_nanoseconds=3),
            ),
        ),
        (
            LinearFundingSettlementFailureCode.FUNDING_MARK_SCALE_MISMATCH,
            _with_mark(
                request,
                replace(
                    mark,
                    price=Price(
                        100_000,
                        Scale(3),
                        str(INSTRUMENT_ID),
                        str(QUOTE_CURRENCY),
                    ),
                ),
            ),
        ),
        (
            LinearFundingSettlementFailureCode.NON_POSITIVE_FUNDING_MARK,
            _with_mark(request, replace(mark, price=replace(mark.price, units=0))),
        ),
        (
            LinearFundingSettlementFailureCode.FUNDING_MARK_POLICY_MISMATCH,
            replace(
                request,
                funding_mark_evidence=replace(
                    evidence,
                    stale_policy=replace(
                        evidence.stale_policy,
                        policy_key="other.funding-mark.v1",
                    ),
                ),
            ),
        ),
        (
            LinearFundingSettlementFailureCode.FUNDING_MARK_NOT_AVAILABLE,
            _with_mark(request, forged_late_mark),
        ),
        (
            LinearFundingSettlementFailureCode.SETTLEMENT_CASH_CONTEXT_MISMATCH,
            replace(
                request,
                settlement_cash_registration=replace(
                    request.settlement_cash_registration,
                    key=CashBalanceKey("other-account", VENUE_ID, QUOTE_CURRENCY),
                ),
            ),
        ),
        (
            LinearFundingSettlementFailureCode.QUANTIZATION_SCALE_MISMATCH,
            replace(
                request,
                payment_quantization=replace(
                    request.payment_quantization, target_scale=Scale(3)
                ),
            ),
        ),
    ]


def test_all_settlement_failures_follow_frozen_precedence() -> None:
    assert [code.value for code in LinearFundingSettlementFailureCode] == [
        "missing_eligibility",
        "missing_settlement_evidence",
        "missing_funding_mark",
        "slot_context_mismatch",
        "position_context_mismatch",
        "unsupported_rate_basis",
        "applied_rate_mismatch",
        "invalid_settlement_effective_time",
        "settlement_evidence_not_available",
        "funding_mark_purpose_mismatch",
        "funding_mark_context_mismatch",
        "funding_mark_instant_mismatch",
        "funding_mark_scale_mismatch",
        "non_positive_funding_mark",
        "funding_mark_policy_mismatch",
        "funding_mark_not_available",
        "settlement_cash_context_mismatch",
        "quantization_scale_mismatch",
    ]

    for expected, request in _failure_cases():
        outcome = LinearFundingAccounting().assess_financing(request)
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is expected
        assert outcome.failure.subject_ids[0] == expected.value


@pytest.mark.parametrize(
    ("rate_units", "rounding", "expected_units"),
    (
        (50, RoundingPolicy.HALF_EVEN, -12),
        (150, RoundingPolicy.HALF_EVEN, -38),
        (250, RoundingPolicy.HALF_EVEN, -62),
        (50, RoundingPolicy.HALF_UP, -13),
        (150, RoundingPolicy.HALF_UP, -38),
        (250, RoundingPolicy.HALF_UP, -63),
        (-50, RoundingPolicy.HALF_EVEN, 12),
        (-50, RoundingPolicy.HALF_UP, 13),
    ),
)
def test_payment_rounding_ties_are_per_application(
    rate_units: int,
    rounding: RoundingPolicy,
    expected_units: int,
) -> None:
    outcome = LinearFundingAccounting().assess_financing(
        _settlement_request(rate_units, rounding)
    )

    assert outcome.result is not None
    assert outcome.result.payment.units == expected_units


@pytest.mark.parametrize(
    ("target_nanoseconds", "rate_units", "expected_units"),
    (
        (3, 8, -2),
        (3, -8, 2),
        (5, 8, 1),
        (5, -8, -1),
        (4, 8, 0),
    ),
)
def test_long_short_flat_and_rate_sign_have_exact_cash_direction(
    target_nanoseconds: int, rate_units: int, expected_units: int
) -> None:
    outcome = LinearFundingAccounting().assess_financing(
        _settlement_request(
            rate_units, target_nanoseconds=target_nanoseconds
        )
    )

    assert outcome.result is not None
    assert outcome.result.payment.units == expected_units


@pytest.mark.parametrize("rate_units", (0, 1))
def test_zero_and_rounded_zero_keep_specialized_journal_identity(
    rate_units: int,
) -> None:
    outcome = LinearFundingAccounting().assess_financing(
        _settlement_request(rate_units)
    )

    assert outcome.result is not None
    result = outcome.result
    if rate_units == 0:
        assert (result.exact_cash_flow.numerator, result.exact_cash_flow.denominator) == (
            0,
            1,
        )
    assert result.payment.units == 0
    assert type(result.journal_entry) is LinearFundingJournalEntry
    assert not result.journal_entry.balance_changes
    assert not result.journal_entry.financing


def _ledger_schema(request: LinearFundingSettlementRequest) -> LedgerSchema:
    return LedgerSchema((request.settlement_cash_registration,))


def _entry(request: LinearFundingSettlementRequest) -> LinearFundingJournalEntry:
    outcome = LinearFundingAccounting().assess_financing(request)
    assert outcome.result is not None
    return outcome.result.journal_entry


def test_journal_idempotency_and_full_replay_are_branchless() -> None:
    request = _settlement_request()
    entry = _entry(request)
    journal = AccountingJournal.from_entries((entry,))

    assert journal.append(entry) is journal
    replay = LinearFundingJournalProjector().project(
        LinearFundingJournalReplayRequest(journal, _ledger_schema(request))
    )

    assert replay.failure is None
    assert replay.projection is not None
    projection = replay.projection
    cash_key = request.settlement_cash_registration.key
    assert type(cash_key) is CashBalanceKey
    assert projection.application_keys == (entry.application_key,)
    assert projection.journal_entry_ids == (entry.journal_entry_id,)
    assert projection.ledger_state.cash_amount(cash_key) == entry.payment
    assert projection.ledger_state.financing_amount(cash_key) == entry.payment
    assert not projection.ledger_state.position_balances

    settlement = request.settlement_evidence
    assert settlement is not None
    changed = _entry(
        replace(
            request,
            settlement_evidence=replace(
                settlement, source_hash="sha256:" + "5" * 64
            ),
        )
    )
    with pytest.raises(JournalEntryConflictError):
        journal.append(changed)


def test_full_journal_rejects_duplicate_conflict_and_ordinary_funding_entries() -> None:
    request = _settlement_request()
    first = _entry(request)
    alternate_identity = LinearFundingApplicationIdentity.derive(
        request.application_identity.application_key,
        IdentityNamespace("alternate-funding", "1"),
        "alternate-linear-funding-run",
    )
    duplicate = _entry(replace(request, application_identity=alternate_identity))
    duplicate_journal = AccountingJournal.from_entries((first, duplicate))
    duplicate_outcome = LinearFundingJournalProjector().project(
        LinearFundingJournalReplayRequest(
            duplicate_journal, _ledger_schema(request)
        )
    )
    assert duplicate_outcome.failure is not None
    assert (
        duplicate_outcome.failure.code
        is LinearFundingJournalReplayFailureCode.DUPLICATE_FUNDING_APPLICATION
    )

    settlement = request.settlement_evidence
    assert settlement is not None
    conflict = _entry(
        replace(
            request,
            application_identity=alternate_identity,
            settlement_evidence=replace(
                settlement, source_hash="sha256:" + "5" * 64
            ),
        )
    )
    conflict_journal = AccountingJournal.from_entries((first, conflict))
    conflict_outcome = LinearFundingJournalProjector().project(
        LinearFundingJournalReplayRequest(conflict_journal, _ledger_schema(request))
    )
    assert conflict_outcome.failure is not None
    assert (
        conflict_outcome.failure.code
        is LinearFundingJournalReplayFailureCode.CONFLICTING_FUNDING_APPLICATION
    )

    ordinary = AccountingJournalEntry(
        journal_entry_id=DomainId(DomainIdKind.JOURNAL, "jnl_" + "f" * 64),
        entry_type=AccountingEntryType.FUNDING_APPLIED,
        account_id=ACCOUNT_ID,
        venue_id=VENUE_ID,
        effective_time=UtcInstant(3),
        recorded_at=_instant(11),
        source_ids=("ordinary-funding-entry",),
        balance_changes=(),
        realized_pnl=(),
        fees=(),
        financing=(),
    )
    unauthorized = LinearFundingJournalProjector().project(
        LinearFundingJournalReplayRequest(
            AccountingJournal.from_entries((ordinary,)), _ledger_schema(request)
        )
    )
    assert unauthorized.failure is not None
    assert (
        unauthorized.failure.code
        is LinearFundingJournalReplayFailureCode.UNAUTHORIZED_FUNDING_ENTRY
    )


def test_normalized_body_conflicts_cover_all_economic_authorities() -> None:
    request = _settlement_request()
    first = _entry(request)
    alternate_identity = LinearFundingApplicationIdentity.derive(
        request.application_identity.application_key,
        IdentityNamespace("alternate-funding", "1"),
        "alternate-linear-funding-run",
    )
    settlement = request.settlement_evidence
    mark_evidence = request.funding_mark_evidence
    assert settlement is not None and mark_evidence is not None
    policy = replace(mark_evidence.stale_policy, max_age_nanoseconds=9)
    policy_mark = replace(
        mark_evidence.resolved_mark,
        stale_policy_hash=policy.policy_hash,
    )
    scale_three_registration = replace(
        request.settlement_cash_registration, scale=Scale(3)
    )
    changed_requests = (
        replace(
            _settlement_request(7),
            application_identity=alternate_identity,
        ),
        replace(
            request,
            application_identity=alternate_identity,
            funding_mark_evidence=replace(
                mark_evidence,
                resolved_mark=replace(
                    mark_evidence.resolved_mark,
                    price=replace(mark_evidence.resolved_mark.price, units=10_001),
                ),
            ),
        ),
        replace(
            request,
            application_identity=alternate_identity,
            funding_mark_evidence=LinearFundingMarkEvidence(policy_mark, policy),
        ),
        replace(
            request,
            application_identity=alternate_identity,
            settlement_evidence=replace(
                settlement, source_hash="sha256:" + "5" * 64
            ),
        ),
        replace(
            request,
            application_identity=alternate_identity,
            settlement_cash_registration=scale_three_registration,
            payment_quantization=replace(
                request.payment_quantization, target_scale=Scale(3)
            ),
        ),
        replace(
            request,
            application_identity=alternate_identity,
            payment_quantization=replace(
                request.payment_quantization, rounding=RoundingPolicy.HALF_UP
            ),
        ),
    )

    for changed_request in changed_requests:
        changed = _entry(changed_request)
        assert changed.application_body_hash != first.application_body_hash
        outcome = LinearFundingJournalProjector().project(
            LinearFundingJournalReplayRequest(
                AccountingJournal.from_entries((first, changed)),
                _ledger_schema(request),
            )
        )
        assert outcome.failure is not None
        assert (
            outcome.failure.code
            is LinearFundingJournalReplayFailureCode.CONFLICTING_FUNDING_APPLICATION
        )


def test_full_journal_rejects_funding_entry_subclasses() -> None:
    request = _settlement_request()
    authoritative = _entry(request)

    class ForgedFundingEntry(LinearFundingJournalEntry):
        def __post_init__(self) -> None:
            pass

    forged = ForgedFundingEntry(
        **{
            value.name: getattr(authoritative, value.name)
            for value in fields(authoritative)
        }
    )
    outcome = LinearFundingJournalProjector().project(
        LinearFundingJournalReplayRequest(
            AccountingJournal.from_entries((forged,)), _ledger_schema(request)
        )
    )

    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is LinearFundingJournalReplayFailureCode.UNAUTHORIZED_FUNDING_ENTRY
    )
