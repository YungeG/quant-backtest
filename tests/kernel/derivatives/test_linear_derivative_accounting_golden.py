from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    CashBalanceKey,
    CurrencyId,
    DomainIdKind,
    Money,
    OrderSide,
    Quantity,
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
    AccountingJournal,
    JournalEntryConflictError,
    LinearDerivativeAccounting,
    LinearDerivativeAccountingFailureCode,
    LinearDerivativeLedgerProjector,
    LinearDerivativeLedgerReplayFailureCode,
    LinearPositionProjector,
    UnregisteredBalanceKeyError,
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
from tests.kernel.derivatives.test_linear_derivative_accounting import (
    _accounting_request,
    _close_request,
    _ledger_schema,
    _replay_request,
    _translated_entries,
    _transition,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/derivatives/linear-derivative-accounting-v1.json"


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot read canonical JSON: {path.name}") from error
    assert isinstance(value, dict)
    return value


def _translation_failures() -> dict[str, object]:
    accounting = LinearDerivativeAccounting()
    transition = _close_request().transition
    wrong_key = CashBalanceKey("other-account", VENUE_ID, QUOTE_CURRENCY)
    settlement = accounting.translate_position_fact(
        _accounting_request(
            transition,
            cash_key=wrong_key,
            target_scale=Scale(3),
            recorded_nanoseconds=1,
        )
    )
    scale = accounting.translate_position_fact(
        _accounting_request(
            transition,
            target_scale=Scale(3),
            recorded_nanoseconds=1,
        )
    )
    recorded = accounting.translate_position_fact(
        _accounting_request(transition, recorded_nanoseconds=1)
    )
    assert settlement.failure is not None
    assert scale.failure is not None
    assert recorded.failure is not None
    return {
        "settlement_precedence": settlement.failure,
        "scale_precedence": scale.failure,
        "recorded_before_execution": recorded.failure,
    }


def _replay_failures(entries) -> dict[str, object]:
    projector = LinearDerivativeLedgerProjector()
    context = projector.project(
        replace(
            _replay_request(AccountingJournal.empty()),
            settlement_cash_key=CashBalanceKey(
                "other-account", VENUE_ID, QUOTE_CURRENCY
            ),
        )
    )
    repeated_result = LinearDerivativeAccounting().translate_position_fact(
        _accounting_request(
            entries[0].request.transition,
            recorded_nanoseconds=9,
            journal_digit="9",
        )
    ).result
    assert repeated_result is not None
    repeated = repeated_result.journal_entry
    duplicate = projector.project(
        _replay_request(AccountingJournal.from_entries((entries[0], repeated)))
    )
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
                position_key(),
                Quantity(1, Scale(3), str(position_key().instrument_id)),
            ),
        ),
        realized_pnl=(),
        fees=(),
        financing=(),
    )
    unsupported = projector.project(
        _replay_request(AccountingJournal.from_entries((ordinary,)))
    )
    lineage = projector.project(
        _replay_request(AccountingJournal.from_entries((entries[1],)))
    )
    entry_context = projector.project(
        replace(
            _replay_request(AccountingJournal.from_entries((entries[0],))),
            contract=replace(
                contract(),
                contract_multiplier=Rate(
                    250, Scale(3), "base_quantity_per_contract"
                ),
            ),
        )
    )
    assert context.failure is not None
    assert duplicate.failure is not None
    assert unsupported.failure is not None
    assert lineage.failure is not None
    assert entry_context.failure is not None
    return {
        "context": context.failure,
        "duplicate": duplicate.failure,
        "ordinary_target": unsupported.failure,
        "entry_context": entry_context.failure,
        "lineage": lineage.failure,
    }


def _rounding_controls() -> tuple[dict[str, object], ...]:
    rows = []
    for numerator in (1, -1, 3, -3):
        for rounding in (RoundingPolicy.HALF_EVEN, RoundingPolicy.HALF_UP):
            rows.append(
                {
                    "numerator": numerator,
                    "denominator": 200,
                    "rounding": rounding.value,
                    "cents": round_ratio(numerator * 100, 200, rounding),
                }
            )
    expected = (0, 1, 0, -1, 2, 2, -2, -2)
    assert tuple(row["cents"] for row in rows) == expected
    return tuple(rows)


def _directional_controls(entries) -> dict[str, object]:
    accounting = LinearDerivativeAccounting()

    def control(*, long: bool, kind: str, gain: bool):
        open_side = OrderSide.BUY if long else OrderSide.SELL
        close_side = OrderSide.SELL if long else OrderSide.BUY
        open_units = 2_000 if kind == "reduce" else 1_000
        close_units = 1_000 if kind != "flip" else 2_000
        exit_units = 10_100 if long == gain else 9_900
        transition = _transition(
            fill("a", side=open_side, quantity_units=open_units, price_units=10_000, execution_nanoseconds=1),
            fill("b", side=close_side, quantity_units=close_units, price_units=exit_units, execution_nanoseconds=2),
        )
        result = accounting.translate_position_fact(
            _accounting_request(transition, journal_digit="f")
        ).result
        assert result is not None
        numerator = result.journal_entry.exact_realized_pnl.numerator
        assert (numerator > 0) == gain
        return result

    controls = {
        f"{direction}_{kind}_{economics}": control(
            long=direction == "long",
            kind=kind,
            gain=economics == "gain",
        )
        for direction in ("long", "short")
        for kind in ("reduce", "close", "flip")
        for economics in ("gain", "loss")
    }
    controls["prior_basis_long_reduce"] = entries[2]
    controls["prior_basis_short_reduce"] = entries[6]
    return controls


def _publication_controls(entries) -> dict[str, object]:
    forward = AccountingJournal.from_entries(entries)
    reverse = AccountingJournal.from_entries(tuple(reversed(entries)))
    assert forward == reverse
    assert forward.append(entries[-1]) is forward

    accounting = LinearDerivativeAccounting()
    tie = _transition(
        fill("a", side=OrderSide.BUY, quantity_units=1_000, price_units=10_000, execution_nanoseconds=1),
        fill("b", side=OrderSide.SELL, quantity_units=1_000, price_units=10_004, execution_nanoseconds=2),
    )
    even = accounting.translate_position_fact(
        _accounting_request(tie, rounding=RoundingPolicy.HALF_EVEN)
    ).result
    up = accounting.translate_position_fact(
        _accounting_request(tie, rounding=RoundingPolicy.HALF_UP)
    ).result
    assert even is not None and up is not None
    try:
        AccountingJournal.empty().append(even.journal_entry).append(up.journal_entry)
    except JournalEntryConflictError as error:
        conflict = type(error).__name__
    else:
        raise AssertionError("same Journal ID with different policy must conflict")

    direct, _ = _translated_entries()
    first = accounting.translate_position_fact(
        _accounting_request(
            direct.transitions[0], recorded_nanoseconds=10, journal_digit="e"
        )
    ).result
    second = accounting.translate_position_fact(
        _accounting_request(
            direct.transitions[1], recorded_nanoseconds=9, journal_digit="f"
        )
    ).result
    assert first is not None and second is not None
    misordered = LinearDerivativeLedgerProjector().project(
        _replay_request(
            AccountingJournal.from_entries(
                (first.journal_entry, second.journal_entry)
            )
        )
    )
    assert misordered.failure is not None
    return {
        "forward_hash": forward.journal_hash,
        "reverse_hash": reverse.journal_hash,
        "candidate_permutation_normalized": forward == reverse,
        "identical_append_idempotent": forward.append(entries[-1]) is forward,
        "conflict_type": conflict,
        "misordered_booking_failure": misordered.failure,
    }


def _mixed_and_native_controls(entries) -> dict[str, object]:
    accounting = LinearDerivativeAccounting()
    projection = LinearPositionProjector().project(
        request(
            fill("a", side=OrderSide.BUY, quantity_units=1_000, price_units=10_000, execution_nanoseconds=1),
            fill("b", side=OrderSide.SELL, quantity_units=1_000, price_units=10_004, execution_nanoseconds=2),
            fill("c", side=OrderSide.BUY, quantity_units=1_000, price_units=10_000, execution_nanoseconds=3),
            fill("d", side=OrderSide.SELL, quantity_units=1_000, price_units=10_004, execution_nanoseconds=4),
        )
    )
    assert projection.result is not None
    sentinel_entries = []
    for index, transition in enumerate(projection.result.transitions, start=1):
        result = accounting.translate_position_fact(
            _accounting_request(transition, journal_digit=str(index))
        ).result
        assert result is not None
        sentinel_entries.append(result.journal_entry)
    cash_key = CashBalanceKey(ACCOUNT_ID, VENUE_ID, QUOTE_CURRENCY)
    deposit = AccountingJournalEntry(
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "a"),
        entry_type=AccountingEntryType.CAPITAL_DEPOSITED,
        account_id=ACCOUNT_ID,
        venue_id=VENUE_ID,
        effective_time=UtcInstant(5),
        recorded_at=SimulationInstant(UtcInstant(5), TimelinePhase(10, "accounting"), SourceSequence(0)),
        source_ids=("mixed-cash-deposit",),
        balance_changes=(BalanceChange(cash_key, Money(10_000, Scale(2), "USDT")),),
        realized_pnl=(),
        fees=(),
        financing=(),
    )
    mixed_journal = AccountingJournal.from_entries((*sentinel_entries, deposit))
    mixed = LinearDerivativeLedgerProjector().project(_replay_request(mixed_journal))
    assert mixed.result is not None
    assert mixed.result.exact_realized_pnl.numerator == 1
    assert mixed.result.exact_realized_pnl.denominator == 100
    assert mixed.result.realized_pnl.units == 0

    usd_key = CashBalanceKey(ACCOUNT_ID, VENUE_ID, CurrencyId("USD"))
    unregistered = AccountingJournalEntry(
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "b"),
        entry_type=AccountingEntryType.CAPITAL_DEPOSITED,
        account_id=ACCOUNT_ID,
        venue_id=VENUE_ID,
        effective_time=UtcInstant(9),
        recorded_at=SimulationInstant(UtcInstant(9), TimelinePhase(10, "accounting"), SourceSequence(0)),
        source_ids=("unregistered-cash",),
        balance_changes=(BalanceChange(usd_key, Money(1, Scale(2), "USD")),),
        realized_pnl=(),
        fees=(),
        financing=(),
    )
    try:
        LinearDerivativeLedgerProjector().project(
            _replay_request(AccountingJournal.from_entries((*entries, unregistered)))
        )
    except UnregisteredBalanceKeyError as error:
        native_failure = {"type": type(error).__name__, "message": str(error)}
    else:
        raise AssertionError("native Generic Ledger failure must propagate")
    return {
        "per_transition_sentinel": mixed.result,
        "whole_cash": Money(10_000, Scale(2), "USDT"),
        "native_ledger_failure": native_failure,
    }


def _large_integer_control() -> object:
    huge = 10**40
    result = LinearDerivativeAccounting().translate_position_fact(
        _accounting_request(
            _transition(
                fill("a", side=OrderSide.BUY, quantity_units=huge, price_units=10_000, execution_nanoseconds=1),
                fill("b", side=OrderSide.SELL, quantity_units=huge, price_units=10_001, execution_nanoseconds=2),
            )
        )
    ).result
    assert result is not None
    assert result.journal_entry.exact_realized_pnl.numerator == 125 * 10**32
    assert result.journal_entry.exact_realized_pnl.denominator == 1
    return result


def build_actual() -> dict[str, object]:
    accounting = LinearDerivativeAccounting()
    direct, entries = _translated_entries()
    journal = AccountingJournal.from_entries(entries)
    replay_request = _replay_request(journal)
    replay = LinearDerivativeLedgerProjector().project(replay_request)
    assert replay.result is not None

    prefixes = []
    for count in range(len(entries) + 1):
        prefix_journal = AccountingJournal.from_entries(entries[:count])
        outcome = LinearDerivativeLedgerProjector().project(
            _replay_request(prefix_journal)
        )
        assert outcome.result is not None
        prefixes.append(
            {
                "count": count,
                "cursor": outcome.result.cursor,
                "position_state": outcome.result.position_state,
                "exact_realized_pnl": outcome.result.exact_realized_pnl,
                "realized_pnl": outcome.result.realized_pnl,
                "journal_entry_ids": outcome.result.journal_entry_ids,
                "ledger_state_hash": outcome.result.ledger_state_hash,
            }
        )

    close = accounting.translate_position_fact(_close_request())
    assert close.result is not None
    mutation_request = _close_request()
    mutation_replay_request = _replay_request(journal)
    before = {
        "request": canonical_sha256(mutation_request),
        "journal": canonical_sha256(journal),
        "replay_request": canonical_sha256(mutation_replay_request),
    }
    mutation_translation = accounting.translate_position_fact(mutation_request)
    mutation_replay = LinearDerivativeLedgerProjector().project(
        mutation_replay_request
    )
    assert mutation_translation.result is not None
    assert mutation_replay.result is not None
    after = {
        "request": canonical_sha256(mutation_request),
        "journal": canonical_sha256(journal),
        "replay_request": canonical_sha256(mutation_replay_request),
    }
    assert before == after
    assert replay.result.position_state == direct.final_state
    assert (
        replay.result.exact_realized_pnl.numerator,
        replay.result.exact_realized_pnl.denominator,
        replay.result.realized_pnl.units,
    ) == (1, 16, 6)

    tie_transition = _transition(
        fill(
            "a",
            side=OrderSide.BUY,
            quantity_units=1_000,
            price_units=10_000,
            execution_nanoseconds=1,
        ),
        fill(
            "b",
            side=OrderSide.SELL,
            quantity_units=1_000,
            price_units=10_004,
            execution_nanoseconds=2,
        ),
    )
    rounded_zero = accounting.translate_position_fact(
        _accounting_request(tie_transition, rounding=RoundingPolicy.HALF_EVEN)
    )
    negative_rounded_zero = accounting.translate_position_fact(
        _accounting_request(
            _transition(
                fill("c", side=OrderSide.SELL, quantity_units=1_000, price_units=10_000, execution_nanoseconds=1),
                fill("d", side=OrderSide.BUY, quantity_units=1_000, price_units=10_004, execution_nanoseconds=2),
            ),
            rounding=RoundingPolicy.HALF_EVEN,
        )
    )
    assert rounded_zero.result is not None
    assert negative_rounded_zero.result is not None
    assert not rounded_zero.result.journal_entry.realized_pnl
    assert not negative_rounded_zero.result.journal_entry.realized_pnl
    try:
        replace(
            replay.result,
            realized_pnl=replace(
                replay.result.realized_pnl,
                units=replay.result.realized_pnl.units + 1,
            ),
        )
    except ValueError as error:
        projection_forgery = {"type": type(error).__name__, "message": str(error)}
    else:
        raise AssertionError("forged replay projection must fail")

    payload = {
        "fixture_id": "synthetic-linear-derivative-accounting-v1",
        "component_ref": accounting.component_ref,
        "translation_failure_values": tuple(
            value.value for value in LinearDerivativeAccountingFailureCode
        ),
        "replay_failure_values": tuple(
            value.value for value in LinearDerivativeLedgerReplayFailureCode
        ),
        "close_control": close.result,
        "rounded_zero_control": rounded_zero.result,
        "negative_rounded_zero_control": negative_rounded_zero.result,
        "rounding_controls": _rounding_controls(),
        "directional_controls": _directional_controls(entries),
        "translated_entries": entries,
        "translation_failures": _translation_failures(),
        "replay_prefixes": tuple(prefixes),
        "replay_projection": replay.result,
        "replay_failures": _replay_failures(entries),
        "publication_controls": _publication_controls(entries),
        "mixed_and_native_controls": _mixed_and_native_controls(entries),
        "large_integer_control": _large_integer_control(),
        "projection_forgery": projection_forgery,
        "canonical_hashes": {
            "component_digest": accounting.component_ref.component_digest,
            "close_result_hash": close.result.result_hash,
            "close_entry_hash": close.result.journal_entry.derivative_entry_hash,
            "journal_hash": journal.journal_hash,
            "replay_request_hash": replay_request.request_hash,
            "replay_projection_hash": replay.result.projection_hash,
            "replay_outcome_hash": replay.outcome_hash,
            "schema_hash": _ledger_schema().schema_hash,
            "actual_hash": canonical_sha256(
                {
                    "entries": entries,
                    "replay": replay.result,
                }
            ),
        },
        "no_mutation": {"before": before, "after": after},
        "limitations": {
            "development_only": True,
            "deployment_authorized": False,
            "principal_notional_cash_effect": False,
            "fees_owned": False,
            "funding_owned": False,
            "unrealized_pnl_owned": False,
            "margin_owned": False,
            "liquidation_owned": False,
        },
    }
    try:
        decoded = json.loads(canonical_bytes(payload))
    except (TypeError, ValueError) as error:
        raise AssertionError("G09B golden payload must be canonical JSON") from error
    assert isinstance(decoded, dict)
    return decoded


def test_linear_derivative_accounting_matches_static_golden() -> None:
    assert build_actual() == _read_json(FIXTURE)
