from __future__ import annotations

from dataclasses import fields, replace

import pytest
import crypto_quant_domain
import crypto_quant_trading

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    CashBalanceKey,
    DomainIdKind,
    Money,
    OrderSide,
    Quantity,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
    round_ratio,
)
from crypto_quant_trading import (
    LedgerBalanceRegistration,
    AccountingJournal,
    GenericLedger,
    JournalEntryConflictError,
    LedgerSchema,
    ExactLinearRealizedPnl,
    LinearDerivativeAccounting,
    LinearDerivativeAccountingFailureCode,
    LinearDerivativeAccountingRequest,
    LinearDerivativeAccountingResult,
    LinearDerivativeJournalEntry,
    LinearDerivativeLedgerProjection,
    LinearDerivativeLedgerProjector,
    LinearDerivativeLedgerReplayFailure,
    LinearDerivativeLedgerReplayFailureCode,
    LinearDerivativeLedgerReplayOutcome,
    LinearDerivativeLedgerReplayRequest,
    LinearPositionProjector,
    LinearPositionTransition,
    PositionAccountingModel,
)

from tests.kernel.derivatives._fixtures import (
    ACCOUNT_ID,
    QUOTE_CURRENCY,
    VENUE_ID,
    contract,
    domain_id,
    fill,
    position_key,
    request,
)


def _transition(*fills_) -> LinearPositionTransition:
    position = LinearPositionProjector().project(request(*fills_))
    assert position.result is not None
    return position.result.transitions[-1]


def _accounting_request(
    transition: LinearPositionTransition,
    *,
    rounding: RoundingPolicy = RoundingPolicy.HALF_EVEN,
    target_scale: Scale = Scale(2),
    cash_key: CashBalanceKey | None = None,
    recorded_nanoseconds: int | None = None,
    journal_digit: str = "9",
) -> LinearDerivativeAccountingRequest:
    return LinearDerivativeAccountingRequest(
        transition=transition,
        settlement_cash_registration=LedgerBalanceRegistration(
            cash_key or CashBalanceKey(ACCOUNT_ID, VENUE_ID, QUOTE_CURRENCY),
            Scale(2),
        ),
        pnl_quantization=QuantizationPolicy(
            f"synthetic-{rounding.value}-v1", target_scale, rounding
        ),
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, journal_digit),
        recorded_at=SimulationInstant(
            UtcInstant(
                transition.fill.execution_time.epoch_nanoseconds
                if recorded_nanoseconds is None
                else recorded_nanoseconds
            ),
            TimelinePhase(10, "accounting"),
            SourceSequence(0),
        ),
    )


def _close_request() -> LinearDerivativeAccountingRequest:
    transition = _transition(
        fill(
            "1",
            side=OrderSide.BUY,
            quantity_units=1_000,
            price_units=10_000,
            execution_nanoseconds=1,
        ),
        fill(
            "2",
            side=OrderSide.SELL,
            quantity_units=1_000,
            price_units=10_100,
            execution_nanoseconds=2,
        ),
    )
    return _accounting_request(transition, journal_digit="2")


def test_close_translation_uses_exact_pnl_and_one_money_boundary() -> None:
    assert round_ratio(1, 2, RoundingPolicy.HALF_EVEN) == 0
    assert round_ratio(3, 2, RoundingPolicy.HALF_EVEN) == 2
    accounting = LinearDerivativeAccounting()
    assert isinstance(accounting, PositionAccountingModel)

    accounting_request = _close_request()
    outcome = accounting.translate_position_fact(accounting_request)

    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    entry = result.journal_entry
    assert isinstance(entry, LinearDerivativeJournalEntry)
    assert entry.entry_type is AccountingEntryType.FILL_BOOKED
    assert entry.exact_realized_pnl.numerator == 1
    assert entry.exact_realized_pnl.denominator == 8
    assert entry.balance_changes[0].value.units == -1_000
    assert entry.balance_changes[1].value == Money(12, Scale(2), "USDT")
    assert entry.realized_pnl == (Money(12, Scale(2), "USDT"),)
    assert not entry.fees
    assert not entry.financing
    assert result.request == accounting_request
    assert result.request_hash == accounting_request.request_hash


def test_transition_formula_effects_and_exact_prior_basis_are_preserved() -> None:
    fills = (
        fill("1", side=OrderSide.BUY, quantity_units=1_000, price_units=10_000, execution_nanoseconds=1),
        fill("2", side=OrderSide.BUY, quantity_units=2_000, price_units=10_050, execution_nanoseconds=2),
        fill("3", side=OrderSide.SELL, quantity_units=1_000, price_units=9_900, execution_nanoseconds=3),
        fill("4", side=OrderSide.SELL, quantity_units=2_000, price_units=9_900, execution_nanoseconds=4),
        fill("5", side=OrderSide.SELL, quantity_units=1_000, price_units=10_100, execution_nanoseconds=5),
        fill("6", side=OrderSide.SELL, quantity_units=1_000, price_units=10_200, execution_nanoseconds=6),
        fill("7", side=OrderSide.BUY, quantity_units=500, price_units=10_000, execution_nanoseconds=7),
        fill("8", side=OrderSide.BUY, quantity_units=2_000, price_units=9_900, execution_nanoseconds=8),
    )
    projection = LinearPositionProjector().project(request(*fills))
    assert projection.result is not None
    expected = (
        (0, 1, 0),
        (0, 1, 0),
        (-1, 6, -17),
        (-1, 3, -33),
        (0, 1, 0),
        (0, 1, 0),
        (3, 32, 9),
        (15, 32, 47),
    )
    accounting = LinearDerivativeAccounting()
    for index, (transition, row) in enumerate(
        zip(projection.result.transitions, expected, strict=True), start=1
    ):
        outcome = accounting.translate_position_fact(
            _accounting_request(transition, journal_digit=str(index))
        )
        assert outcome.result is not None
        entry = outcome.result.journal_entry
        numerator, denominator, money_units = row
        assert (
            entry.exact_realized_pnl.numerator,
            entry.exact_realized_pnl.denominator,
        ) == (numerator, denominator)
        position_change = entry.balance_changes[0]
        assert position_change.value.units == (
            transition.after.quantity.units - transition.before.quantity.units
        )
        if money_units == 0:
            assert len(entry.balance_changes) == 1
            assert not entry.realized_pnl
        else:
            assert entry.balance_changes[1].value == Money(
                money_units, Scale(2), "USDT"
            )
            assert entry.realized_pnl == (
                Money(money_units, Scale(2), "USDT"),
            )
        assert not entry.fees
        assert not entry.financing


def test_rounding_ties_quantize_once_and_rounded_zero_omits_cash() -> None:
    accounting = LinearDerivativeAccounting()

    def translated_units(*, short: bool, difference_units: int, rounding: RoundingPolicy) -> tuple[int, int, int]:
        open_side = OrderSide.SELL if short else OrderSide.BUY
        close_side = OrderSide.BUY if short else OrderSide.SELL
        open_price = 10_000
        close_price = open_price - difference_units if short else open_price + difference_units
        transition = _transition(
            fill("a", side=open_side, quantity_units=1_000, price_units=open_price, execution_nanoseconds=1),
            fill("b", side=close_side, quantity_units=1_000, price_units=close_price, execution_nanoseconds=2),
        )
        outcome = accounting.translate_position_fact(
            _accounting_request(transition, rounding=rounding)
        )
        assert outcome.result is not None
        entry = outcome.result.journal_entry
        units = entry.realized_pnl[0].units if entry.realized_pnl else 0
        return entry.exact_realized_pnl.numerator, entry.exact_realized_pnl.denominator, units

    assert translated_units(short=False, difference_units=4, rounding=RoundingPolicy.HALF_EVEN) == (1, 200, 0)
    assert translated_units(short=False, difference_units=4, rounding=RoundingPolicy.HALF_UP) == (1, 200, 1)
    assert translated_units(short=True, difference_units=-4, rounding=RoundingPolicy.HALF_EVEN) == (-1, 200, 0)
    assert translated_units(short=True, difference_units=-4, rounding=RoundingPolicy.HALF_UP) == (-1, 200, -1)
    assert translated_units(short=False, difference_units=12, rounding=RoundingPolicy.HALF_EVEN) == (3, 200, 2)
    assert translated_units(short=True, difference_units=-12, rounding=RoundingPolicy.HALF_UP) == (-3, 200, -2)


def test_translation_failures_precedence_subjects_and_constructors_are_closed() -> None:
    transition = _close_request().transition
    accounting = LinearDerivativeAccounting()
    wrong_key = CashBalanceKey("other-account", VENUE_ID, QUOTE_CURRENCY)
    settlement_failure = accounting.translate_position_fact(
        _accounting_request(
            transition,
            target_scale=Scale(3),
            cash_key=wrong_key,
            recorded_nanoseconds=1,
        )
    )
    assert settlement_failure.failure is not None
    failure = settlement_failure.failure
    assert failure.code is LinearDerivativeAccountingFailureCode.SETTLEMENT_CONTEXT_MISMATCH
    assert failure.subject_ids == (
        "settlement_context_mismatch",
        str(transition.fill.fill_id),
        domain_id(DomainIdKind.JOURNAL, "9").value,
        ACCOUNT_ID,
        str(transition.before.position_key.instrument_id),
        "USDT",
    )

    scale_failure = accounting.translate_position_fact(
        _accounting_request(
            transition, target_scale=Scale(3), recorded_nanoseconds=1
        )
    )
    assert scale_failure.failure is not None
    assert scale_failure.failure.code is LinearDerivativeAccountingFailureCode.QUANTIZATION_SCALE_MISMATCH

    time_failure = accounting.translate_position_fact(
        _accounting_request(transition, recorded_nanoseconds=1)
    )
    assert time_failure.failure is not None
    assert time_failure.failure.code is LinearDerivativeAccountingFailureCode.RECORDED_BEFORE_EXECUTION

    with pytest.raises(ValueError, match="first Request failure"):
        replace(
            failure,
            code=LinearDerivativeAccountingFailureCode.RECORDED_BEFORE_EXECUTION,
        )
    with pytest.raises(ValueError, match="subject_ids"):
        replace(failure, subject_ids=("forged",) * 6)

    result = accounting.translate_position_fact(_close_request()).result
    assert result is not None
    with pytest.raises(ValueError, match="Journal entry fields"):
        money = result.journal_entry.realized_pnl[0]
        replace(
            result.journal_entry,
            realized_pnl=(replace(money, units=money.units + 1),),
        )
    with pytest.raises(ValueError, match="request_hash"):
        replace(result.journal_entry, request_hash="sha256:" + "0" * 64)


def _sequence_fills():
    return (
        fill("1", side=OrderSide.BUY, quantity_units=1_000, price_units=10_000, execution_nanoseconds=1),
        fill("2", side=OrderSide.BUY, quantity_units=2_000, price_units=10_050, execution_nanoseconds=2),
        fill("3", side=OrderSide.SELL, quantity_units=1_000, price_units=9_900, execution_nanoseconds=3),
        fill("4", side=OrderSide.SELL, quantity_units=2_000, price_units=9_900, execution_nanoseconds=4),
        fill("5", side=OrderSide.SELL, quantity_units=1_000, price_units=10_100, execution_nanoseconds=5),
        fill("6", side=OrderSide.SELL, quantity_units=1_000, price_units=10_200, execution_nanoseconds=6),
        fill("7", side=OrderSide.BUY, quantity_units=500, price_units=10_000, execution_nanoseconds=7),
        fill("8", side=OrderSide.BUY, quantity_units=2_000, price_units=9_900, execution_nanoseconds=8),
    )


def _ledger_schema() -> LedgerSchema:
    return LedgerSchema(
        (
            LedgerBalanceRegistration(
                CashBalanceKey(ACCOUNT_ID, VENUE_ID, QUOTE_CURRENCY), Scale(2)
            ),
            LedgerBalanceRegistration(position_key(), Scale(3)),
        )
    )


def _translated_entries():
    projection = LinearPositionProjector().project(request(*_sequence_fills()))
    assert projection.result is not None
    accounting = LinearDerivativeAccounting()
    entries = []
    for index, transition in enumerate(projection.result.transitions, start=1):
        translated = accounting.translate_position_fact(
            _accounting_request(transition, journal_digit=str(index))
        )
        assert translated.result is not None
        entries.append(translated.result.journal_entry)
    return projection.result, tuple(entries)


def _replay_request(journal: AccountingJournal) -> LinearDerivativeLedgerReplayRequest:
    return LinearDerivativeLedgerReplayRequest(
        journal=journal,
        ledger_schema=_ledger_schema(),
        position_key=position_key(),
        contract=contract(),
        settlement_cash_key=CashBalanceKey(
            ACCOUNT_ID, VENUE_ID, QUOTE_CURRENCY
        ),
    )


def test_specialized_entry_preserves_generic_journal_idempotency_and_conflict() -> None:
    accounting = LinearDerivativeAccounting()
    request_even = _accounting_request(
        _transition(
            fill("a", side=OrderSide.BUY, quantity_units=1_000, price_units=10_000, execution_nanoseconds=1),
            fill("b", side=OrderSide.SELL, quantity_units=1_000, price_units=10_004, execution_nanoseconds=2),
        ),
        rounding=RoundingPolicy.HALF_EVEN,
    )
    request_up = replace(
        request_even,
        pnl_quantization=QuantizationPolicy(
            "synthetic-half-up-v1", Scale(2), RoundingPolicy.HALF_UP
        ),
    )
    even = accounting.translate_position_fact(request_even).result
    up = accounting.translate_position_fact(request_up).result
    assert even is not None and up is not None
    journal = AccountingJournal.empty().append(even.journal_entry)
    assert journal.append(even.journal_entry) is journal
    with pytest.raises(JournalEntryConflictError):
        journal.append(up.journal_entry)


def test_replay_matches_every_direct_prefix_and_generic_ledger_quantity() -> None:
    direct, entries = _translated_entries()
    expected = (
        (0, 1, 0),
        (0, 1, 0),
        (0, 1, 0),
        (-1, 6, -17),
        (-1, 2, -50),
        (-1, 2, -50),
        (-1, 2, -50),
        (-13, 32, -41),
        (1, 16, 6),
    )
    projector = LinearDerivativeLedgerProjector()
    for count, row in enumerate(expected):
        journal = AccountingJournal.from_entries(tuple(reversed(entries[:count])))
        outcome = projector.project(_replay_request(journal))
        assert outcome.failure is None
        assert outcome.result is not None
        result = outcome.result
        expected_state = (
            direct.transitions[count - 1].after
            if count
            else direct.transitions[0].before
        )
        assert result.position_state == expected_state
        assert (
            result.exact_realized_pnl.numerator,
            result.exact_realized_pnl.denominator,
            result.realized_pnl.units,
        ) == row
        assert result.cursor == journal.cursor_at(journal.entry_count)
        assert result.journal_entry_ids == tuple(
            entry.journal_entry_id for entry in entries[:count]
        )
        ledger = GenericLedger(_ledger_schema()).project(journal)
        assert ledger.position_quantity(position_key()) == result.position_state.quantity
        assert ledger.state_hash == result.ledger_state_hash


def test_replay_uses_per_transition_money_and_accepts_unrelated_cash_entries() -> None:
    accounting = LinearDerivativeAccounting()
    transitions = LinearPositionProjector().project(
        request(
            fill("1", side=OrderSide.BUY, quantity_units=1_000, price_units=10_000, execution_nanoseconds=1),
            fill("2", side=OrderSide.SELL, quantity_units=1_000, price_units=10_004, execution_nanoseconds=2),
            fill("3", side=OrderSide.BUY, quantity_units=1_000, price_units=10_000, execution_nanoseconds=3),
            fill("4", side=OrderSide.SELL, quantity_units=1_000, price_units=10_004, execution_nanoseconds=4),
        )
    )
    assert transitions.result is not None
    entries = []
    for index, transition in enumerate(transitions.result.transitions, start=1):
        translated = accounting.translate_position_fact(
            _accounting_request(transition, journal_digit=str(index))
        )
        assert translated.result is not None
        entries.append(translated.result.journal_entry)
    cash_key = CashBalanceKey(ACCOUNT_ID, VENUE_ID, QUOTE_CURRENCY)
    deposit = AccountingJournalEntry(
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "a"),
        entry_type=AccountingEntryType.CAPITAL_DEPOSITED,
        account_id=ACCOUNT_ID,
        venue_id=VENUE_ID,
        effective_time=UtcInstant(5),
        recorded_at=SimulationInstant(
            UtcInstant(5), TimelinePhase(10, "accounting"), SourceSequence(0)
        ),
        source_ids=("unrelated-cash-deposit",),
        balance_changes=(BalanceChange(cash_key, Money(10_000, Scale(2), "USDT")),),
        realized_pnl=(),
        fees=(),
        financing=(),
    )
    journal = AccountingJournal.from_entries((*entries, deposit))
    outcome = LinearDerivativeLedgerProjector().project(_replay_request(journal))
    assert outcome.result is not None
    assert outcome.result.exact_realized_pnl.numerator == 1
    assert outcome.result.exact_realized_pnl.denominator == 100
    assert outcome.result.realized_pnl == Money(0, Scale(2), "USDT")
    ledger = GenericLedger(_ledger_schema()).project(journal)
    assert ledger.cash_amount(cash_key) == Money(10_000, Scale(2), "USDT")


def test_replay_failures_follow_journal_wide_and_target_precedence() -> None:
    direct, entries = _translated_entries()
    projector = LinearDerivativeLedgerProjector()
    cash_key = CashBalanceKey(ACCOUNT_ID, VENUE_ID, QUOTE_CURRENCY)

    bad_context = replace(
        _replay_request(AccountingJournal.empty()),
        settlement_cash_key=CashBalanceKey("other-account", VENUE_ID, QUOTE_CURRENCY),
    )
    context = projector.project(bad_context)
    assert context.failure is not None
    assert context.failure.code is LinearDerivativeLedgerReplayFailureCode.REPLAY_CONTEXT_MISMATCH
    assert context.failure.journal_entry_id is None
    assert context.failure.fill_id is None

    repeated_result = LinearDerivativeAccounting().translate_position_fact(
        _accounting_request(
            entries[0].request.transition,
            recorded_nanoseconds=9,
            journal_digit="9",
        )
    ).result
    assert repeated_result is not None
    repeated = repeated_result.journal_entry
    duplicate_journal = AccountingJournal.from_entries((entries[0], repeated))
    duplicate = projector.project(_replay_request(duplicate_journal))
    assert duplicate.failure is not None
    assert duplicate.failure.code is LinearDerivativeLedgerReplayFailureCode.DUPLICATE_FILL_ID
    assert duplicate.failure.journal_entry_id == repeated.journal_entry_id
    assert duplicate.failure.fill_id == repeated.request.transition.fill.fill_id

    ordinary = AccountingJournalEntry(
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "a"),
        entry_type=AccountingEntryType.FILL_BOOKED,
        account_id=ACCOUNT_ID,
        venue_id=VENUE_ID,
        effective_time=UtcInstant(1),
        recorded_at=SimulationInstant(
            UtcInstant(1), TimelinePhase(10, "accounting"), SourceSequence(0)
        ),
        source_ids=("ordinary-target-position-change",),
        balance_changes=(
            BalanceChange(
                position_key(), Quantity(1, Scale(3), str(position_key().instrument_id))
            ),
        ),
        realized_pnl=(),
        fees=(),
        financing=(),
    )
    unsupported = projector.project(
        _replay_request(AccountingJournal.from_entries((ordinary,)))
    )
    assert unsupported.failure is not None
    assert unsupported.failure.code is LinearDerivativeLedgerReplayFailureCode.UNSUPPORTED_TARGET_POSITION_ENTRY
    assert unsupported.failure.journal_entry_id == ordinary.journal_entry_id
    assert unsupported.failure.fill_id is None

    lineage = projector.project(
        _replay_request(AccountingJournal.from_entries((entries[1],)))
    )
    assert lineage.failure is not None
    assert lineage.failure.code is LinearDerivativeLedgerReplayFailureCode.TRANSITION_LINEAGE_MISMATCH
    assert lineage.failure.journal_entry_id == entries[1].journal_entry_id

    alternate_contract = replace(
        contract(),
        contract_multiplier=Rate(250, Scale(3), "base_quantity_per_contract"),
    )
    entry_context = projector.project(
        replace(
            _replay_request(AccountingJournal.from_entries((entries[0],))),
            contract=alternate_contract,
        )
    )
    assert entry_context.failure is not None
    assert entry_context.failure.code is LinearDerivativeLedgerReplayFailureCode.ENTRY_CONTEXT_MISMATCH
    assert direct.transitions[0] == entries[0].request.transition


def test_public_exports_component_and_canonical_preimages_are_frozen() -> None:
    expected_domain_exports = {"round_ratio"}
    expected_kernel_exports = {
        "ExactLinearRealizedPnl",
        "LinearDerivativeAccountingRequest",
        "LinearDerivativeJournalEntry",
        "LinearDerivativeAccountingResult",
        "LinearDerivativeAccountingFailureCode",
        "LinearDerivativeAccountingFailure",
        "LinearDerivativeAccounting",
        "LinearDerivativeLedgerReplayRequest",
        "LinearDerivativeLedgerProjection",
        "LinearDerivativeLedgerReplayFailureCode",
        "LinearDerivativeLedgerReplayFailure",
        "LinearDerivativeLedgerReplayOutcome",
        "LinearDerivativeLedgerProjector",
    }
    assert expected_domain_exports <= set(crypto_quant_domain.__all__)
    assert expected_kernel_exports <= set(crypto_quant_trading.__all__)

    accounting = LinearDerivativeAccounting()
    assert accounting.component_ref.component_key == "instrument.linear-perpetual.accounting.v1"
    assert accounting.component_ref.component_version == 1
    assert accounting.component_ref.component_digest == (
        "sha256:d95d6d5b761413ca961c94870774b4420870a476d8693f4da7e3b7fb4a568a3e"
    )
    assert tuple(value.value for value in LinearDerivativeAccountingFailureCode) == (
        "settlement_context_mismatch",
        "quantization_scale_mismatch",
        "recorded_before_execution",
    )
    assert tuple(value.value for value in LinearDerivativeLedgerReplayFailureCode) == (
        "replay_context_mismatch",
        "unsupported_target_position_entry",
        "entry_context_mismatch",
        "duplicate_fill_id",
        "transition_lineage_mismatch",
        "ledger_position_mismatch",
    )

    translation_request = _close_request()
    translated = accounting.translate_position_fact(translation_request)
    assert translated.result is not None
    _, entries = _translated_entries()
    journal = AccountingJournal.from_entries(entries)
    replay_request = _replay_request(journal)
    replay = LinearDerivativeLedgerProjector().project(replay_request)
    assert replay.result is not None
    values = (
        translated.result.journal_entry.exact_realized_pnl,
        translation_request,
        translated.result.journal_entry,
        translated.result,
        replay_request,
        replay.result,
        replay,
    )
    expected_types = (
        "exact_linear_realized_pnl",
        "linear_derivative_accounting_request",
        "linear_derivative_journal_entry",
        "linear_derivative_accounting_result",
        "linear_derivative_ledger_replay_request",
        "linear_derivative_ledger_projection",
        "linear_derivative_ledger_replay_outcome",
    )
    assert tuple(value.to_canonical_dict()["type"] for value in values) == expected_types
    assert all(value.to_canonical_dict()["schema_version"] == 1 for value in values)
    assert translated.result.result_hash == canonical_sha256(translated.result)
    assert replay.result.projection_hash == canonical_sha256(replay.result)
    assert replay.outcome_hash == canonical_sha256(replay)


def test_large_integer_exactness_constructor_closure_and_no_mutation() -> None:
    huge = 10**40
    transition = _transition(
        fill("a", side=OrderSide.BUY, quantity_units=huge, price_units=10_000, execution_nanoseconds=1),
        fill("b", side=OrderSide.SELL, quantity_units=huge, price_units=10_001, execution_nanoseconds=2),
    )
    accounting_request = _accounting_request(transition)
    before = canonical_bytes(accounting_request)
    translated = LinearDerivativeAccounting().translate_position_fact(accounting_request)
    assert translated.result is not None
    assert canonical_bytes(accounting_request) == before
    exact = translated.result.journal_entry.exact_realized_pnl
    assert exact == ExactLinearRealizedPnl(QUOTE_CURRENCY, 125 * 10**32, 1)

    with pytest.raises(ValueError, match="GCD-reduced"):
        ExactLinearRealizedPnl(QUOTE_CURRENCY, 2, 2)
    with pytest.raises(ValueError, match="positive"):
        ExactLinearRealizedPnl(QUOTE_CURRENCY, 1, 0)

    direct, entries = _translated_entries()
    replay_request = _replay_request(AccountingJournal.from_entries(entries))
    replay_before = canonical_bytes(replay_request)
    replay = LinearDerivativeLedgerProjector().project(replay_request)
    assert replay.result is not None
    assert canonical_bytes(replay_request) == replay_before
    with pytest.raises(ValueError, match="Projection fields"):
        replace(
            replay.result,
            realized_pnl=replace(
                replay.result.realized_pnl,
                units=replay.result.realized_pnl.units + 1,
            ),
        )
    with pytest.raises(ValueError, match="exactly one"):
        LinearDerivativeLedgerReplayOutcome(
            replay_request.request_hash,
            replay.result,
            LinearDerivativeLedgerProjector()
            .project(
                replace(
                    replay_request,
                    settlement_cash_key=CashBalanceKey(
                        "other-account", VENUE_ID, QUOTE_CURRENCY
                    ),
                )
            )
            .failure,
        )

    failed = LinearDerivativeLedgerProjector().project(
        replace(
            replay_request,
            settlement_cash_key=CashBalanceKey(
                "other-account", VENUE_ID, QUOTE_CURRENCY
            ),
        )
    )
    assert failed.failure is not None
    with pytest.raises(ValueError, match="first replay failure"):
        replace(
            failed.failure,
            code=LinearDerivativeLedgerReplayFailureCode.LEDGER_POSITION_MISMATCH,
        )

    assert direct.final_state == replay.result.position_state


def test_requests_reject_nested_subclass_identity_forgery() -> None:
    transition = _close_request().transition

    class ForgedScale(Scale):
        pass

    forged_scale = ForgedScale(2)
    with pytest.raises(TypeError, match="registration scale"):
        LinearDerivativeAccountingRequest(
            transition,
            LedgerBalanceRegistration(
                CashBalanceKey(ACCOUNT_ID, VENUE_ID, QUOTE_CURRENCY),
                forged_scale,
            ),
            QuantizationPolicy(
                "synthetic-half-even-v1", Scale(2), RoundingPolicy.HALF_EVEN
            ),
            domain_id(DomainIdKind.JOURNAL, "f"),
            SimulationInstant(
                UtcInstant(2), TimelinePhase(10, "accounting"), SourceSequence(0)
            ),
        )

    class ForgedText(str):
        pass

    forged_key = CashBalanceKey(
        ForgedText(ACCOUNT_ID), VENUE_ID, QUOTE_CURRENCY
    )
    with pytest.raises(TypeError, match="registration key"):
        replace(
            _close_request(),
            settlement_cash_registration=LedgerBalanceRegistration(
                forged_key, Scale(2)
            ),
        )

    class ForgedRegistration(LedgerBalanceRegistration):
        pass

    valid_replay = _replay_request(AccountingJournal.empty())
    forged_schema = LedgerSchema(
        (
            ForgedRegistration(
                CashBalanceKey(ACCOUNT_ID, VENUE_ID, QUOTE_CURRENCY), Scale(2)
            ),
            LedgerBalanceRegistration(position_key(), Scale(3)),
        )
    )
    with pytest.raises(TypeError, match="registration"):
        replace(valid_replay, ledger_schema=forged_schema)


def test_replay_rejects_specialized_entry_subclass_as_non_authoritative() -> None:
    _, entries = _translated_entries()
    authoritative = entries[0]

    class ForgedEntry(LinearDerivativeJournalEntry):
        def __post_init__(self) -> None:
            pass

    forged = ForgedEntry(
        **{
            value.name: getattr(authoritative, value.name)
            for value in fields(authoritative)
        }
    )
    assert isinstance(forged, LinearDerivativeJournalEntry)
    assert type(forged) is not LinearDerivativeJournalEntry
    outcome = LinearDerivativeLedgerProjector().project(
        _replay_request(AccountingJournal.from_entries((forged,)))
    )
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is LinearDerivativeLedgerReplayFailureCode.UNSUPPORTED_TARGET_POSITION_ENTRY
    )

    values = {value.name: getattr(authoritative, value.name) for value in fields(authoritative)}
    cash = Money(1, Scale(2), "USDT")
    values["balance_changes"] = (
        BalanceChange(CashBalanceKey(ACCOUNT_ID, VENUE_ID, QUOTE_CURRENCY), cash),
    )
    values["realized_pnl"] = (cash,)
    cash_only_forgery = ForgedEntry(**values)
    cash_only = LinearDerivativeLedgerProjector().project(
        _replay_request(AccountingJournal.from_entries((cash_only_forgery,)))
    )
    assert cash_only.failure is not None
    assert (
        cash_only.failure.code
        is LinearDerivativeLedgerReplayFailureCode.UNSUPPORTED_TARGET_POSITION_ENTRY
    )

    values["request"] = None
    malformed = ForgedEntry(**values)
    malformed_outcome = LinearDerivativeLedgerProjector().project(
        _replay_request(AccountingJournal.from_entries((malformed,)))
    )
    assert malformed_outcome.failure is not None
    assert (
        malformed_outcome.failure.code
        is LinearDerivativeLedgerReplayFailureCode.UNSUPPORTED_TARGET_POSITION_ENTRY
    )
