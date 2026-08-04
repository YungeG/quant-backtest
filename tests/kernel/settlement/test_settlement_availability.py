from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import Any, cast

import pytest

from crypto_quant_domain import (
    CashBalanceKey,
    CurrencyId,
    Money,
    PositionBalanceKey,
    Quantity,
    UtcInstant,
    VenueId,
)
from crypto_quant_trading import (
    AvailabilityEvidenceError,
    AvailabilityProjection,
    CashAvailabilityRule,
    CashReservationUse,
    MarketSettlementRules,
    PositionAvailabilityRule,
    SettlementBook,
    SettlementEventConflictError,
    SettlementLifecycleError,
    SettlementStateMismatchError,
)

from ._fixtures import (
    ACCOUNT,
    CASH_KEY,
    INSTRUMENT,
    MONEY_SCALE,
    POSITION_KEY,
    QUANTITY_SCALE,
    USD,
    applied_event,
    ledger_state,
    market_rules,
    reservation_state,
    settlement_book,
    settlement_evidence,
)


def test_settlement_lifecycle_tracks_exact_pending_and_applied_state() -> None:
    book = settlement_book()
    recorded = book.project(stop=book.cursor_at(3))
    position_applied = book.project(stop=book.cursor_at(4))
    fully_applied = book.project()

    assert len(recorded.pending_obligations) == 3
    assert not recorded.applied_obligations
    assert [
        item.obligation.settlement_obligation_id.value
        for item in position_applied.applied_obligations
    ] == [book.obligations[0].obligation.settlement_obligation_id.value]
    assert len(position_applied.pending_obligations) == 2
    assert not fully_applied.pending_obligations
    assert len(fully_applied.applied_obligations) == 3


def test_settlement_replay_is_order_independent_and_prefix_resumable() -> None:
    obligations, events = settlement_evidence()
    forward = SettlementBook.from_events(ACCOUNT, obligations, events)
    reverse = SettlementBook.from_events(
        ACCOUNT, tuple(reversed(obligations)), tuple(reversed(events))
    )
    prefix = forward.project(stop=forward.cursor_at(4))

    resumed = forward.resume(prefix)

    assert reverse.book_hash == forward.book_hash
    assert reverse.project().state_hash == forward.project().state_hash
    assert resumed == forward.project()
    assert resumed.state_hash == forward.project().state_hash


def test_identical_apply_is_idempotent_but_conflicts_and_second_apply_fail() -> None:
    obligations, events = settlement_evidence()
    prefix = SettlementBook.from_events(ACCOUNT, obligations, events[:4])
    identical = prefix.append(events=(events[3],))

    assert identical is prefix

    with pytest.raises(SettlementEventConflictError, match="conflicting"):
        prefix.append(
            events=(replace(events[3], source_evidence_hash="sha256:" + "f" * 64),)
        )

    second_apply = replace(
        events[4],
        event_id="settlement-event:applied:duplicate",
        settlement_obligation_id=events[3].settlement_obligation_id,
        causation_id=events[3].causation_id,
    )
    with pytest.raises(SettlementLifecycleError, match="already applied"):
        prefix.append(events=(second_apply,))


def test_settlement_time_causation_and_published_prefix_fail_closed() -> None:
    obligations, events = settlement_evidence()
    early_apply = replace(
        events[3],
        occurred_at=replace(events[3].occurred_at, instant=UtcInstant(19)),
    )
    with pytest.raises(SettlementLifecycleError, match="settlement_time"):
        SettlementBook.from_events(ACCOUNT, obligations, events[:3] + (early_apply,))

    wrong_cause = replace(events[3], causation_id="settlement-event:unknown")
    with pytest.raises(SettlementLifecycleError, match="causation"):
        SettlementBook.from_events(ACCOUNT, obligations, events[:3] + (wrong_cause,))

    prefix = SettlementBook.from_events(ACCOUNT, obligations[:1], events[:1])
    late_obligation = replace(
        obligations[1],
        obligation=replace(obligations[1].obligation, trade_time=UtcInstant(9)),
    )
    late_event = replace(
        events[1],
        occurred_at=replace(events[1].occurred_at, instant=UtcInstant(9)),
    )
    with pytest.raises(SettlementLifecycleError, match="published prefix"):
        prefix.append(obligations=(late_obligation,), events=(late_event,))


def test_resume_rejects_a_forged_prior_state() -> None:
    book = settlement_book()
    prefix = book.project(stop=book.cursor_at(4))
    forged = replace(
        prefix,
        pending_obligations=prefix.pending_obligations[1:],
    )

    with pytest.raises(SettlementStateMismatchError, match="prior state"):
        book.resume(forged)


def test_availability_separates_total_settled_and_reserved_resources() -> None:
    book = settlement_book()
    settlement = book.project(stop=book.cursor_at(4))

    state = AvailabilityProjection().project(
        ledger_state(), settlement, reservation_state(), market_rules()
    )

    cash = state.cash[0]
    position = state.positions[0]
    assert cash.total == Money(15_000, MONEY_SCALE, str(USD))
    assert cash.settled == Money(10_000, MONEY_SCALE, str(USD))
    assert cash.tradable == Money(12_900, MONEY_SCALE, str(USD))
    assert cash.withdrawable == Money(6_400, MONEY_SCALE, str(USD))
    assert cash.available_margin == Money(13_500, MONEY_SCALE, str(USD))
    assert position.total == Quantity(15, QUANTITY_SCALE, str(INSTRUMENT))
    assert position.sellable == Quantity(13, QUANTITY_SCALE, str(INSTRUMENT))

    cash_applied = book.project(stop=book.cursor_at(5))
    after = AvailabilityProjection().project(
        ledger_state(), cash_applied, reservation_state(), market_rules()
    )
    assert after.cash[0].settled.units == 15_000
    assert after.cash[0].withdrawable.units == 11_400
    assert after.cash[0].tradable.units == cash.tradable.units


def test_negative_pending_delivery_is_not_deducted_twice() -> None:
    book = settlement_book()
    all_recorded = book.project(stop=book.cursor_at(3))
    state = AvailabilityProjection().project(
        ledger_state(), all_recorded, reservation_state(), market_rules()
    )

    assert state.cash[0].settled.units == 10_000
    assert state.positions[0].sellable.units == 3


def test_rules_are_canonical_and_require_exact_coverage_and_reservation_ownership() -> None:
    book = settlement_book()
    settlement = book.project(stop=book.cursor_at(4))
    baseline = AvailabilityProjection().project(
        ledger_state(), settlement, reservation_state(), market_rules()
    )
    reverse = AvailabilityProjection().project(
        ledger_state(), settlement, reservation_state(), market_rules(reverse=True)
    )
    assert reverse == baseline
    assert reverse.state_hash == baseline.state_hash

    missing_position = MarketSettlementRules.create(
        policy_key="settlement.synthetic.explicit.v1",
        policy_version=1,
        account_id=ACCOUNT,
        cash_rules=market_rules().cash_rules,
        position_rules=(),
    )
    with pytest.raises(AvailabilityEvidenceError, match="coverage"):
        AvailabilityProjection().project(
            ledger_state(), settlement, reservation_state(), missing_position
        )

    other_key = CashBalanceKey(ACCOUNT, VenueId("other"), CurrencyId("USD"))
    duplicate_owner = CashAvailabilityRule(
        key=other_key,
        pending_receivable_tradable=True,
        pending_receivable_withdrawable=True,
        pending_receivable_margin_eligible=True,
        tradable_reservation_uses=(CashReservationUse.CASH,),
        withdrawable_reservation_uses=(),
        available_margin_reservation_uses=(),
    )
    rules = MarketSettlementRules.create(
        policy_key="settlement.synthetic.invalid.v1",
        policy_version=1,
        account_id=ACCOUNT,
        cash_rules=market_rules().cash_rules + (duplicate_owner,),
        position_rules=(PositionAvailabilityRule(POSITION_KEY, False),),
    )
    with pytest.raises(AvailabilityEvidenceError, match="coverage"):
        AvailabilityProjection().project(
            ledger_state(), settlement, reservation_state(), rules
        )


def test_contracts_are_frozen_and_reject_wrong_context() -> None:
    obligations, _ = settlement_evidence()
    with pytest.raises(FrozenInstanceError):
        cast(Any, obligations[0]).balance_key = CASH_KEY

    wrong_account_rules = MarketSettlementRules.create(
        policy_key="settlement.synthetic.wrong.v1",
        policy_version=1,
        account_id="account:other",
        cash_rules=(
            replace(market_rules().cash_rules[0], key=CashBalanceKey(
                "account:other", CASH_KEY.venue_id, CASH_KEY.currency_id
            )),
        ),
        position_rules=(
            replace(market_rules().position_rules[0], key=PositionBalanceKey(
                "account:other", POSITION_KEY.venue_id, POSITION_KEY.instrument_id
            )),
        ),
    )
    with pytest.raises(AvailabilityEvidenceError, match="account"):
        AvailabilityProjection().project(
            ledger_state(), settlement_book().project(), reservation_state(), wrong_account_rules
        )

    with pytest.raises(TypeError, match="CashReservationUse"):
        CashAvailabilityRule(
            CASH_KEY,
            True,
            True,
            True,
            cast(Any, ("cash",)),
            (),
            (),
        )
