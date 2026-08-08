from __future__ import annotations

import ast
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from crypto_quant_domain import (
    AccountingEntryType,
    BalanceChange,
    CashBalanceKey,
    CurrencyId,
    InstrumentId,
    Money,
    PositionBalanceKey,
    Price,
    Quantity,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    TradingDate,
    UtcInstant,
    VenueId,
    InstrumentType,
    OrderSide,
    canonical_sha256,
)
from crypto_quant_trading import (
    AvailabilityEvidenceError,
    AvailabilityProjection,
    CashReservationUse,
    LedgerBalanceRegistration,
    LedgerSchema,
    ReservationCommitment,
    ResourceReservationState,
    SettlementBook,
    SettlementEventType,
    SettlementLifecycleError,
    SettlementModel,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCalendarDayKind,
    CnAShareCashSettlementModel,
    CnAShareSettlementFailure,
    CnAShareSettlementFailureCode,
    CnAShareSettlementQuery,
    CnAShareSettlementResolution,
)
from tests.kernel.profiles.cn_a_share._fixtures import (
    settlement_journey,
    settlement_model,
    settlement_query,
    settlement_schema,
)


def test_public_settlement_contract_is_frozen() -> None:
    assert tuple(value.value for value in CnAShareSettlementFailureCode) == (
        "unsupported_venue",
        "unsupported_instrument",
        "unsupported_currency",
        "trade_time_not_open",
        "calendar_coverage_missing",
        "accounting_effect_mismatch",
        "settlement_identity_mismatch",
    )
    assert CnAShareSettlementQuery.__module__.endswith("cn_a_share.settlement")
    assert CnAShareSettlementResolution.__module__.endswith("cn_a_share.settlement")
    assert CnAShareSettlementFailure.__module__.endswith("cn_a_share.settlement")
    assert CnAShareCashSettlementModel.__module__.endswith("cn_a_share.settlement")


def test_buy_and_sell_resolve_fixed_t_plus_one_obligations() -> None:
    model = settlement_model()
    buy_query = settlement_query(OrderSide.BUY)
    sell_query = settlement_query(OrderSide.SELL)

    buy = model.resolve_settlement(buy_query)
    sell = model.resolve_settlement(sell_query)

    assert buy.failure is None
    assert sell.failure is None
    assert buy.result is not None
    assert sell.result is not None
    assert buy.result.trade_date.value.isoformat() == "2024-02-08"
    assert buy.result.next_trading_date.value.isoformat() == "2024-02-19"
    assert buy.result.position_availability_time.epoch_nanoseconds == 1_708_272_000_000_000_000
    assert buy.result.cash_withdrawal_time.epoch_nanoseconds == 1_708_329_600_000_000_000
    assert buy.result.fill_accounting_entry_hash == canonical_sha256(
        buy_query.fill_accounting_entry
    )
    assert tuple(value.units for value in buy.result.obligations) == (-100_000, 100)
    assert tuple(value.units for value in sell.result.obligations) == (120_000, -100)
    assert buy.result.obligations[0].obligation.settlement_time == buy_query.fill.execution_time
    assert (
        sell.result.obligations[1].obligation.settlement_time
        == sell_query.fill.execution_time
    )


def test_query_defers_domain_kind_validation_to_model() -> None:
    query = settlement_query(OrderSide.BUY)
    malformed = replace(query, cash_obligation_id=query.fill.fill_id)

    outcome = settlement_model().resolve_settlement(malformed)

    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is CnAShareSettlementFailureCode.SETTLEMENT_IDENTITY_MISMATCH
    )
    with pytest.raises(TypeError):
        replace(query, fill=object())  # type: ignore[arg-type]


def test_resolution_rejects_timing_or_binding_substitution() -> None:
    query = settlement_query(OrderSide.BUY)
    outcome = settlement_model().resolve_settlement(query)
    assert outcome.result is not None
    result = outcome.result

    with pytest.raises(ValueError):
        replace(result, obligations=tuple(reversed(result.obligations)))
    with pytest.raises(ValueError):
        replace(result, fill_accounting_entry_hash="not-a-hash")
    with pytest.raises(ValueError):
        replace(
            result,
            position_availability_time=query.fill.execution_time,
        )


def test_resolution_rejects_duplicate_cross_account_or_wrong_date_evidence() -> None:
    outcome = settlement_model().resolve_settlement(settlement_query(OrderSide.BUY))
    assert outcome.result is not None
    result = outcome.result
    cash, position = result.obligations
    assert isinstance(cash.balance_key, CashBalanceKey)
    assert isinstance(cash.value, Money)
    assert isinstance(position.balance_key, PositionBalanceKey)
    assert isinstance(position.value, Quantity)
    duplicate_position = replace(
        position,
        obligation=replace(
            position.obligation,
            settlement_obligation_id=cash.obligation.settlement_obligation_id,
        ),
    )
    cross_account_position = replace(
        position,
        balance_key=PositionBalanceKey(
            "account:other",
            position.balance_key.venue_id,
            position.balance_key.instrument_id,
        ),
    )
    wrong_venue_cash = replace(
        cash,
        balance_key=CashBalanceKey(
            cash.balance_key.account_id,
            VenueId("xshe"),
            cash.balance_key.currency_id,
        ),
    )
    wrong_next_date = TradingDate(
        result.next_trading_date.calendar_id,
        date(2024, 2, 20),
    )
    usd_cash = replace(
        cash,
        obligation=replace(
            cash.obligation,
            currency_id=CurrencyId("USD"),
            amount=Money(cash.units, cash.value.scale, "USD"),
        ),
        balance_key=CashBalanceKey(
            cash.balance_key.account_id,
            cash.balance_key.venue_id,
            CurrencyId("USD"),
        ),
    )
    negative_position = replace(
        position,
        obligation=replace(
            position.obligation,
            settlement_time=position.obligation.trade_time,
            quantity=Quantity(
                -abs(position.units),
                position.value.scale,
                position.value.instrument_id,
            ),
        ),
    )
    prior_trade = UtcInstant(
        cash.obligation.trade_time.epoch_nanoseconds - 86_400_000_000_000
    )
    prior_cash = replace(
        cash,
        obligation=replace(
            cash.obligation,
            trade_time=prior_trade,
            settlement_time=prior_trade,
        ),
    )
    prior_position = replace(
        position,
        obligation=replace(position.obligation, trade_time=prior_trade),
    )

    for changes in (
        {"obligations": (cash, duplicate_position)},
        {"obligations": (cash, cross_account_position)},
        {"obligations": (wrong_venue_cash, position)},
        {"next_trading_date": wrong_next_date},
        {"obligations": (usd_cash, position)},
        {"obligations": (cash, negative_position)},
        {"obligations": (prior_cash, prior_position)},
    ):
        with pytest.raises(ValueError):
            replace(result, **changes)


def test_failure_precedence_and_subject_keys_are_deterministic() -> None:
    model = settlement_model()
    unsupported_venue = settlement_query(OrderSide.BUY, venue="xshe")
    unsupported_instrument = settlement_query(OrderSide.BUY)
    unsupported_instrument = replace(
        unsupported_instrument,
        instrument=replace(
            unsupported_instrument.instrument,
            instrument_type=InstrumentType.SPOT,
        ),
    )
    unsupported_currency = settlement_query(OrderSide.BUY)
    unsupported_currency = replace(
        unsupported_currency,
        instrument=replace(
            unsupported_currency.instrument,
            quote_currency=CurrencyId("USD"),
            settlement_currency=CurrencyId("USD"),
        ),
    )
    identity_mismatch = settlement_query(OrderSide.BUY)
    identity_mismatch = replace(
        identity_mismatch,
        cash_obligation_id=identity_mismatch.fill.fill_id,
    )
    accounting_mismatch = settlement_query(OrderSide.BUY)
    accounting_mismatch = replace(
        accounting_mismatch,
        fill_accounting_entry=replace(
            accounting_mismatch.fill_accounting_entry,
            source_ids=("wrong-source",),
        ),
    )
    coverage_missing = settlement_query(
        OrderSide.BUY,
        local_date=date(2024, 2, 19),
    )
    trade_time_not_open = settlement_query(
        OrderSide.BUY,
        hour=12,
    )
    cases = (
        (
            unsupported_venue,
            CnAShareSettlementFailureCode.UNSUPPORTED_VENUE,
            "xshe",
        ),
        (
            unsupported_instrument,
            CnAShareSettlementFailureCode.UNSUPPORTED_INSTRUMENT,
            unsupported_instrument.fill.fill_id.value,
        ),
        (
            unsupported_currency,
            CnAShareSettlementFailureCode.UNSUPPORTED_CURRENCY,
            unsupported_currency.fill.fill_id.value,
        ),
        (
            identity_mismatch,
            CnAShareSettlementFailureCode.SETTLEMENT_IDENTITY_MISMATCH,
            identity_mismatch.fill.fill_id.value,
        ),
        (
            accounting_mismatch,
            CnAShareSettlementFailureCode.ACCOUNTING_EFFECT_MISMATCH,
            accounting_mismatch.fill_accounting_entry.journal_entry_id.value,
        ),
        (
            coverage_missing,
            CnAShareSettlementFailureCode.CALENDAR_COVERAGE_MISSING,
            coverage_missing.fill.fill_id.value,
        ),
        (
            trade_time_not_open,
            CnAShareSettlementFailureCode.TRADE_TIME_NOT_OPEN,
            trade_time_not_open.fill.fill_id.value,
        ),
    )

    for query, expected_code, expected_subject in cases:
        outcome = model.resolve_settlement(query)
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is expected_code
        assert outcome.failure.subject_key == expected_subject
        assert outcome.input_hash == canonical_sha256(query)


def test_adjacent_failure_precedence_is_not_masked() -> None:
    venue = settlement_query(OrderSide.BUY, venue="xshe")
    venue = replace(
        venue,
        instrument=replace(venue.instrument, instrument_type=InstrumentType.SPOT),
    )
    instrument = settlement_query(OrderSide.BUY)
    instrument = replace(
        instrument,
        instrument=replace(
            instrument.instrument,
            instrument_type=InstrumentType.SPOT,
            quote_currency=CurrencyId("USD"),
            settlement_currency=CurrencyId("USD"),
        ),
    )
    currency = settlement_query(OrderSide.BUY)
    currency = replace(
        currency,
        instrument=replace(
            currency.instrument,
            quote_currency=CurrencyId("USD"),
            settlement_currency=CurrencyId("USD"),
        ),
        cash_obligation_id=currency.fill.fill_id,
    )
    identity = settlement_query(OrderSide.BUY)
    identity = replace(
        identity,
        cash_obligation_id=identity.fill.fill_id,
        fill_accounting_entry=replace(
            identity.fill_accounting_entry,
            source_ids=("wrong-source",),
        ),
    )
    accounting = settlement_query(
        OrderSide.BUY,
        local_date=date(2024, 2, 19),
    )
    accounting = replace(
        accounting,
        fill_accounting_entry=replace(
            accounting.fill_accounting_entry,
            source_ids=("wrong-source",),
        ),
    )
    coverage = settlement_query(
        OrderSide.BUY,
        local_date=date(2024, 2, 19),
        hour=12,
    )
    cases = (
        (venue, CnAShareSettlementFailureCode.UNSUPPORTED_VENUE),
        (instrument, CnAShareSettlementFailureCode.UNSUPPORTED_INSTRUMENT),
        (currency, CnAShareSettlementFailureCode.UNSUPPORTED_CURRENCY),
        (identity, CnAShareSettlementFailureCode.SETTLEMENT_IDENTITY_MISMATCH),
        (accounting, CnAShareSettlementFailureCode.ACCOUNTING_EFFECT_MISMATCH),
        (coverage, CnAShareSettlementFailureCode.CALENDAR_COVERAGE_MISSING),
    )

    for query, expected in cases:
        outcome = settlement_model().resolve_settlement(query)
        assert outcome.failure is not None
        assert outcome.failure.code is expected


@pytest.mark.parametrize(
    ("side", "adjustment", "expected_units"),
    (
        (OrderSide.BUY, -1, -100_001),
        (OrderSide.SELL, 1, 120_001),
    ),
)
def test_settlement_preserves_authoritative_cash_effect_without_recomputing_notional(
    side: OrderSide,
    adjustment: int,
    expected_units: int,
) -> None:
    query = settlement_query(side)
    entry = query.fill_accounting_entry
    cash_change = next(
        value for value in entry.balance_changes if isinstance(value.key, CashBalanceKey)
    )
    assert isinstance(cash_change.value, Money)
    authoritative_cash = replace(
        cash_change,
        value=Money(
            cash_change.value.units + adjustment,
            cash_change.value.scale,
            cash_change.value.currency,
        ),
    )
    changed = replace(
        query,
        fill_accounting_entry=replace(
            entry,
            balance_changes=tuple(
                authoritative_cash if value is cash_change else value
                for value in entry.balance_changes
            ),
        ),
    )

    outcome = settlement_model().resolve_settlement(changed)

    assert outcome.result is not None
    assert outcome.result.obligations[0].units == expected_units


def test_accounting_entry_type_sign_quantity_and_fee_mismatches_fail() -> None:
    query = settlement_query(OrderSide.BUY)
    entry = query.fill_accounting_entry
    cash_change = next(
        value for value in entry.balance_changes if isinstance(value.key, CashBalanceKey)
    )
    position_change = next(
        value
        for value in entry.balance_changes
        if isinstance(value.key, PositionBalanceKey)
    )
    assert isinstance(cash_change.value, Money)
    assert isinstance(position_change.value, Quantity)
    malformed_entries = (
        replace(entry, entry_type=AccountingEntryType.CAPITAL_DEPOSITED),
        replace(
            entry,
            balance_changes=(
                replace(
                    cash_change,
                    value=Money(
                        -cash_change.value.units,
                        cash_change.value.scale,
                        cash_change.value.currency,
                    ),
                ),
                position_change,
            ),
        ),
        replace(
            entry,
            balance_changes=(
                cash_change,
                replace(
                    position_change,
                    value=Quantity(
                        position_change.value.units + 1,
                        position_change.value.scale,
                        position_change.value.instrument_id,
                    ),
                ),
            ),
        ),
        replace(
            entry,
            fees=(Money(1, cash_change.value.scale, cash_change.value.currency),),
        ),
    )

    for malformed in malformed_entries:
        outcome = settlement_model().resolve_settlement(
            replace(query, fill_accounting_entry=malformed)
        )
        assert outcome.failure is not None
        assert (
            outcome.failure.code
            is CnAShareSettlementFailureCode.ACCOUNTING_EFFECT_MISMATCH
        )


def test_fill_currency_instrument_and_settlement_id_predicates_are_isolated() -> None:
    query = settlement_query(OrderSide.BUY)
    other_instrument = InstrumentId(query.fill.venue_id, "600001")
    wrong_instrument = replace(
        query,
        instrument=replace(query.instrument, instrument_id=other_instrument),
    )
    usd_price = Price(
        query.fill.price.units,
        query.fill.price.scale,
        str(query.fill.instrument_id),
        "USD",
    )
    wrong_fill_currency = replace(
        query,
        fill=replace(
            query.fill,
            reference_price=usd_price,
            price=usd_price,
            slippage_amount=Money(0, usd_price.scale, "USD"),
        ),
    )
    wrong_position_kind = replace(
        query,
        position_obligation_id=query.fill.order_id,
    )
    duplicate_ids = replace(
        query,
        position_obligation_id=query.cash_obligation_id,
    )
    cases = (
        (wrong_instrument, CnAShareSettlementFailureCode.UNSUPPORTED_INSTRUMENT),
        (wrong_fill_currency, CnAShareSettlementFailureCode.UNSUPPORTED_CURRENCY),
        (
            wrong_position_kind,
            CnAShareSettlementFailureCode.SETTLEMENT_IDENTITY_MISMATCH,
        ),
        (duplicate_ids, CnAShareSettlementFailureCode.SETTLEMENT_IDENTITY_MISMATCH),
    )

    for malformed, expected in cases:
        outcome = settlement_model().resolve_settlement(malformed)
        assert outcome.failure is not None
        assert outcome.failure.code is expected


def test_quote_and_settlement_currency_fail_independently() -> None:
    query = settlement_query(OrderSide.BUY)
    quote_mismatch = replace(
        query,
        instrument=replace(
            query.instrument,
            quote_currency=CurrencyId("USD"),
        ),
    )
    settlement_mismatch = replace(
        query,
        instrument=replace(
            query.instrument,
            settlement_currency=CurrencyId("USD"),
        ),
    )

    for malformed in (quote_mismatch, settlement_mismatch):
        outcome = settlement_model().resolve_settlement(malformed)
        assert outcome.failure is not None
        assert (
            outcome.failure.code
            is CnAShareSettlementFailureCode.UNSUPPORTED_CURRENCY
        )


def test_source_identity_membership_is_exact_but_order_independent() -> None:
    query = settlement_query(OrderSide.BUY)
    entry = query.fill_accounting_entry
    reversed_source = replace(entry, source_ids=tuple(reversed(entry.source_ids)))
    accepted = settlement_model().resolve_settlement(
        replace(query, fill_accounting_entry=reversed_source)
    )
    assert accepted.result is not None
    malformed_sources = (
        (query.fill.fill_id.value,),
        (query.fill.fill_id.value, "wrong-source"),
        (*entry.source_ids, "extra-source"),
    )

    for source_ids in malformed_sources:
        outcome = settlement_model().resolve_settlement(
            replace(
                query,
                fill_accounting_entry=replace(entry, source_ids=source_ids),
            )
        )
        assert outcome.failure is not None
        assert (
            outcome.failure.code
            is CnAShareSettlementFailureCode.ACCOUNTING_EFFECT_MISMATCH
        )


def test_cash_position_cardinality_and_sell_sign_are_exact() -> None:
    buy = settlement_query(OrderSide.BUY)
    entry = buy.fill_accounting_entry
    cash_change = next(
        value for value in entry.balance_changes if isinstance(value.key, CashBalanceKey)
    )
    position_change = next(
        value
        for value in entry.balance_changes
        if isinstance(value.key, PositionBalanceKey)
    )
    assert isinstance(cash_change.value, Money)
    assert isinstance(position_change.value, Quantity)
    other_instrument = InstrumentId(buy.fill.venue_id, "600001")
    second_position = BalanceChange(
        PositionBalanceKey(
            buy.fill.account_id,
            buy.fill.venue_id,
            other_instrument,
        ),
        Quantity(1, Scale(0), str(other_instrument)),
    )
    second_cash = BalanceChange(
        CashBalanceKey(
            buy.fill.account_id,
            buy.fill.venue_id,
            CurrencyId("USD"),
        ),
        Money(-1, cash_change.value.scale, "USD"),
    )
    malformed_entries = (
        replace(entry, balance_changes=(cash_change,)),
        replace(entry, balance_changes=(position_change,)),
        replace(entry, balance_changes=(cash_change, second_cash)),
        replace(entry, balance_changes=(position_change, second_position)),
    )

    for malformed in malformed_entries:
        outcome = settlement_model().resolve_settlement(
            replace(buy, fill_accounting_entry=malformed)
        )
        assert outcome.failure is not None
        assert (
            outcome.failure.code
            is CnAShareSettlementFailureCode.ACCOUNTING_EFFECT_MISMATCH
        )

    sell = settlement_query(OrderSide.SELL)
    sell_position = next(
        value
        for value in sell.fill_accounting_entry.balance_changes
        if isinstance(value.key, PositionBalanceKey)
    )
    assert isinstance(sell_position.value, Quantity)
    positive_sell = replace(
        sell_position,
        value=Quantity(
            abs(sell_position.value.units),
            sell_position.value.scale,
            sell_position.value.instrument_id,
        ),
    )
    outcome = settlement_model().resolve_settlement(
        replace(
            sell,
            fill_accounting_entry=replace(
                sell.fill_accounting_entry,
                balance_changes=tuple(
                    positive_sell if value is sell_position else value
                    for value in sell.fill_accounting_entry.balance_changes
                ),
            ),
        )
    )
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is CnAShareSettlementFailureCode.ACCOUNTING_EFFECT_MISMATCH
    )


def test_accounting_context_timing_financing_and_shape_mismatches_fail() -> None:
    query = settlement_query(OrderSide.BUY)
    entry = query.fill_accounting_entry
    cash_change = next(
        value for value in entry.balance_changes if isinstance(value.key, CashBalanceKey)
    )
    position_change = next(
        value
        for value in entry.balance_changes
        if isinstance(value.key, PositionBalanceKey)
    )
    assert isinstance(cash_change.value, Money)
    assert isinstance(position_change.value, Quantity)
    other_account = "account:other"
    other_venue = VenueId("xshe")
    other_venue_instrument = InstrumentId(other_venue, "000001")
    other_instrument = InstrumentId(query.fill.venue_id, "600001")
    account_entry = replace(
        entry,
        account_id=other_account,
        balance_changes=(
            BalanceChange(
                CashBalanceKey(other_account, query.fill.venue_id, CurrencyId("CNY")),
                cash_change.value,
            ),
            BalanceChange(
                PositionBalanceKey(
                    other_account,
                    query.fill.venue_id,
                    query.fill.instrument_id,
                ),
                position_change.value,
            ),
        ),
    )
    venue_entry = replace(
        entry,
        venue_id=other_venue,
        balance_changes=(
            BalanceChange(
                CashBalanceKey(query.fill.account_id, other_venue, CurrencyId("CNY")),
                cash_change.value,
            ),
            BalanceChange(
                PositionBalanceKey(
                    query.fill.account_id,
                    other_venue,
                    other_venue_instrument,
                ),
                Quantity(
                    position_change.value.units,
                    position_change.value.scale,
                    str(other_venue_instrument),
                ),
            ),
        ),
    )
    currency_entry = replace(
        entry,
        balance_changes=(
            BalanceChange(
                CashBalanceKey(
                    query.fill.account_id,
                    query.fill.venue_id,
                    CurrencyId("USD"),
                ),
                Money(cash_change.value.units, cash_change.value.scale, "USD"),
            ),
            position_change,
        ),
    )
    instrument_entry = replace(
        entry,
        balance_changes=(
            cash_change,
            BalanceChange(
                PositionBalanceKey(
                    query.fill.account_id,
                    query.fill.venue_id,
                    other_instrument,
                ),
                Quantity(
                    position_change.value.units,
                    position_change.value.scale,
                    str(other_instrument),
                ),
            ),
        ),
    )
    scale_entry = replace(
        entry,
        balance_changes=(
            cash_change,
            replace(
                position_change,
                value=Quantity(
                    position_change.value.units,
                    Scale(1),
                    position_change.value.instrument_id,
                ),
            ),
        ),
    )
    extra_entry = replace(
        entry,
        balance_changes=(
            *entry.balance_changes,
            BalanceChange(
                PositionBalanceKey(
                    query.fill.account_id,
                    query.fill.venue_id,
                    other_instrument,
                ),
                Quantity(1, Scale(0), str(other_instrument)),
            ),
        ),
    )
    malformed_entries = (
        replace(
            entry,
            effective_time=UtcInstant(query.fill.execution_time.epoch_nanoseconds - 1),
        ),
        replace(
            entry,
            financing=(Money(1, cash_change.value.scale, "CNY"),),
        ),
        account_entry,
        venue_entry,
        currency_entry,
        instrument_entry,
        scale_entry,
        extra_entry,
    )

    for malformed in malformed_entries:
        outcome = settlement_model().resolve_settlement(
            replace(query, fill_accounting_entry=malformed)
        )
        assert outcome.failure is not None
        assert (
            outcome.failure.code
            is CnAShareSettlementFailureCode.ACCOUNTING_EFFECT_MISMATCH
        )


def test_availability_rules_are_fixed_and_venue_scoped() -> None:
    model = settlement_model()
    rules = model.availability_rules(settlement_schema())
    cash_rule = rules.cash_rules[0]
    position_rule = rules.position_rules[0]

    assert rules.policy_key == "equity.cn_a_share.cash.availability.v1"
    assert rules.policy_version == 1
    assert cash_rule.pending_receivable_tradable
    assert not cash_rule.pending_receivable_withdrawable
    assert not cash_rule.pending_receivable_margin_eligible
    assert cash_rule.tradable_reservation_uses == (
        CashReservationUse.CASH,
        CashReservationUse.FEE_RESERVE,
    )
    assert cash_rule.withdrawable_reservation_uses == (
        CashReservationUse.CASH,
        CashReservationUse.FEE_RESERVE,
    )
    assert cash_rule.available_margin_reservation_uses == ()
    assert not position_rule.pending_receivable_sellable
    assert (
        model.component_ref.component_digest
        != settlement_model("xshe").component_ref.component_digest
    )

    with pytest.raises(AvailabilityEvidenceError):
        model.availability_rules(settlement_schema("xshe"))
    with pytest.raises(TypeError):
        model.availability_rules(object())  # type: ignore[arg-type]


def test_availability_rules_reject_missing_or_cross_account_dimensions() -> None:
    model = settlement_model()
    schema = settlement_schema()
    cash_registration, position_registration = schema.registrations
    assert isinstance(cash_registration.key, CashBalanceKey)
    assert isinstance(position_registration.key, PositionBalanceKey)
    missing_position = LedgerSchema((cash_registration,))
    cross_account = LedgerSchema(
        (
            cash_registration,
            LedgerBalanceRegistration(
                PositionBalanceKey(
                    "account:other",
                    position_registration.key.venue_id,
                    position_registration.key.instrument_id,
                ),
                position_registration.scale,
            ),
        )
    )

    with pytest.raises(AvailabilityEvidenceError):
        model.availability_rules(missing_position)
    with pytest.raises(AvailabilityEvidenceError):
        model.availability_rules(cross_account)


def test_journal_settlement_and_availability_follow_t_plus_one_boundaries() -> None:
    journey = settlement_journey()
    before_cash = journey.before_availability.cash[0]
    before_position = journey.before_availability.positions[0]
    position_cash = journey.position_available.cash[0]
    position_position = journey.position_available.positions[0]
    mature_cash = journey.cash_available.cash[0]
    mature_position = journey.cash_available.positions[0]

    assert journey.journal.entry_count == 3
    assert journey.ledger.cursor == journey.journal.cursor_at(3)
    assert all(
        query.fill_accounting_entry in journey.journal.entries
        for query in journey.queries
    )
    fill_entries = [
        entry
        for entry in journey.journal.entries
        if entry.entry_type is AccountingEntryType.FILL_BOOKED
    ]
    assert [entry.recorded_at.source_sequence.value for entry in fill_entries] == [
        1,
        2,
    ]
    assert (
        fill_entries[0].journal_entry_id.value
        > fill_entries[1].journal_entry_id.value
    )
    assert (
        before_cash.total.units,
        before_cash.settled.units,
        before_cash.tradable.units,
        before_cash.withdrawable.units,
        before_cash.available_margin.units,
    ) == (1_020_000, 900_000, 999_000, 879_000, 900_000)
    assert (before_position.total.units, before_position.sellable.units) == (200, 80)
    assert position_cash == before_cash
    assert (position_position.total.units, position_position.sellable.units) == (
        200,
        180,
    )
    assert (
        mature_cash.total.units,
        mature_cash.settled.units,
        mature_cash.tradable.units,
        mature_cash.withdrawable.units,
        mature_cash.available_margin.units,
    ) == (1_020_000, 1_020_000, 999_000, 999_000, 1_020_000)
    assert mature_position == position_position
    assert journey.position_boundary_before.pending_obligations
    assert journey.position_boundary_after.pending_obligations
    assert journey.cash_boundary_before.pending_obligations
    assert not journey.cash_boundary_after.pending_obligations
    assert journey.full_state == journey.resumed_state
    assert journey.forward_book.book_hash == journey.reversed_book.book_hash


def test_book_rules_and_availability_are_input_order_invariant() -> None:
    journey = settlement_journey()
    reversed_schema = LedgerSchema(tuple(reversed(settlement_schema().registrations)))
    reversed_rules = settlement_model().availability_rules(reversed_schema)
    reversed_state = journey.reversed_book.project(
        stop=journey.reversed_book.cursor_at(
            journey.position_boundary_before.cursor.position
        )
    )
    reversed_availability = AvailabilityProjection().project(
        journey.ledger,
        reversed_state,
        journey.reservations,
        reversed_rules,
    )

    assert journey.forward_book.book_hash == journey.reversed_book.book_hash
    assert journey.rules.rules_hash == reversed_rules.rules_hash
    assert journey.before_availability.state_hash == reversed_availability.state_hash


def test_exact_nanosecond_boundaries_select_before_and_after_states() -> None:
    journey = settlement_journey()
    buy, sell = journey.resolutions

    def state_at(instant: UtcInstant):
        position = sum(
            event.occurred_at.instant <= instant
            for event in journey.forward_book.events
        )
        return journey.forward_book.project(
            stop=journey.forward_book.cursor_at(position)
        )

    position_before = UtcInstant(
        buy.position_availability_time.epoch_nanoseconds - 1
    )
    cash_before = UtcInstant(sell.cash_withdrawal_time.epoch_nanoseconds - 1)
    assert state_at(position_before) == journey.position_boundary_before
    assert state_at(buy.position_availability_time) == journey.position_boundary_after
    assert state_at(cash_before) == journey.cash_boundary_before
    assert state_at(sell.cash_withdrawal_time) == journey.cash_boundary_after


def test_component_identity_and_canonical_schemas_are_frozen() -> None:
    model: SettlementModel[
        CnAShareSettlementQuery,
        CnAShareSettlementResolution,
        CnAShareSettlementFailure,
    ] = settlement_model()
    query = settlement_query(OrderSide.BUY)
    outcome = model.resolve_settlement(query)
    assert outcome.result is not None

    assert model.component_ref.component_key == "equity.cn_a_share.cash.settlement.v1"
    assert model.component_ref.component_version == 1
    assert (
        model.component_ref.component_digest
        == "sha256:af93c4de6f0b17293bd72d6de27f8adfbd779864f0ae4d628ca76972895df1ea"
    )
    assert (
        settlement_model("xshe").component_ref.component_digest
        == "sha256:4739aafb8232502e92a567743baa78ce5ab5c129ae327d4dd474268a9dfe8134"
    )
    assert tuple(query.to_canonical_dict()) == (
        "type",
        "schema_version",
        "fill",
        "instrument",
        "fill_accounting_entry",
        "cash_obligation_id",
        "position_obligation_id",
    )
    assert tuple(outcome.result.to_canonical_dict()) == (
        "type",
        "schema_version",
        "venue_id",
        "fill_id",
        "trade_date",
        "next_trading_date",
        "position_availability_time",
        "cash_withdrawal_time",
        "fill_accounting_entry_hash",
        "obligations",
    )


def test_settlement_events_bind_resolution_and_exact_boundary_order() -> None:
    journey = settlement_journey()
    resolution_by_fill = {
        value.fill_id.value: value for value in journey.resolutions
    }
    obligation_by_id = {
        value.obligation.settlement_obligation_id: value
        for value in journey.forward_book.obligations
    }
    recorded = tuple(
        value
        for value in journey.forward_book.events
        if value.event_type is SettlementEventType.OBLIGATION_RECORDED
    )
    applied = tuple(
        value
        for value in journey.forward_book.events
        if value.event_type is SettlementEventType.SETTLEMENT_APPLIED
    )

    assert len(recorded) == 4
    assert len(applied) == 4
    assert all(
        value.occurred_at.phase.rank == 60
        and value.occurred_at.phase.code == "settlement_recorded"
        for value in recorded
    )
    assert all(
        value.occurred_at.phase.rank == 61
        and value.occurred_at.phase.code == "settlement_applied"
        for value in applied
    )
    recorded_ids = [value.event_id for value in recorded]
    recorded_sequences = [
        value.occurred_at.source_sequence.value for value in recorded
    ]
    assert recorded_ids == sorted(recorded_ids, reverse=True)
    assert recorded_sequences == [1, 2, 3, 4]
    for event in recorded:
        obligation = obligation_by_id[event.settlement_obligation_id]
        assert event.source_evidence_hash == canonical_sha256(
            resolution_by_fill[obligation.obligation.source_fill_id.value]
        )
    buy, sell = journey.resolutions
    position_event = next(
        value
        for value in applied
        if value.settlement_obligation_id
        == buy.obligations[1].obligation.settlement_obligation_id
    )
    cash_event = next(
        value
        for value in applied
        if value.settlement_obligation_id
        == sell.obligations[0].obligation.settlement_obligation_id
    )
    assert position_event.occurred_at.instant == buy.position_availability_time
    assert cash_event.occurred_at.instant == sell.cash_withdrawal_time
    assert all(
        entry.entry_type is not AccountingEntryType.SETTLEMENT_APPLIED
        for entry in journey.journal.entries
    )


def test_margin_reservation_has_no_owner_and_fails_closed() -> None:
    journey = settlement_journey()
    current = journey.reservations.active_reservations[0]
    margin_commitment = replace(
        current.commitment,
        margin=(Money(1, journey.ledger.cash_balances[0].amount.scale, "CNY"),),
    )
    reservations = ResourceReservationState(
        account_id=journey.reservations.account_id,
        cursors=journey.reservations.cursors,
        active_reservations=(
            replace(current, commitment=margin_commitment),
        ),
        totals=margin_commitment,
    )

    with pytest.raises(AvailabilityEvidenceError):
        AvailabilityProjection().project(
            journey.ledger,
            journey.position_boundary_before,
            reservations,
            journey.rules,
        )


def test_applied_before_recorded_fails_generic_lifecycle() -> None:
    journey = settlement_journey()
    obligation = journey.forward_book.obligations[0]
    recorded = next(
        value
        for value in journey.forward_book.events
        if value.event_type is SettlementEventType.OBLIGATION_RECORDED
        and value.settlement_obligation_id
        == obligation.obligation.settlement_obligation_id
    )
    applied = next(
        value
        for value in journey.forward_book.events
        if value.event_type is SettlementEventType.SETTLEMENT_APPLIED
        and value.settlement_obligation_id
        == obligation.obligation.settlement_obligation_id
    )
    early = replace(
        applied,
        occurred_at=SimulationInstant(
            obligation.obligation.trade_time,
            TimelinePhase(59, "settlement_applied_early"),
            SourceSequence(1),
        ),
    )

    with pytest.raises(SettlementLifecycleError):
        SettlementBook.from_events(
            obligation.account_id,
            (obligation,),
            (recorded, early),
        ).project()


def test_reservations_change_availability_without_mutating_settlement() -> None:
    journey = settlement_journey()
    empty = ResourceReservationState(
        account_id=journey.ledger.cash_balances[0].key.account_id,
        cursors=(),
        active_reservations=(),
        totals=ReservationCommitment.empty(),
    )

    without_reservations = AvailabilityProjection().project(
        journey.ledger,
        journey.position_boundary_before,
        empty,
        journey.rules,
    )

    assert (
        without_reservations.settlement_state_hash
        == journey.before_availability.settlement_state_hash
    )
    assert (
        without_reservations.reservation_state_hash
        != journey.before_availability.reservation_state_hash
    )
    assert without_reservations.cash[0].tradable.units == 1_020_000
    assert without_reservations.positions[0].sellable.units == 100
    assert journey.forward_book.project().state_hash == journey.full_state.state_hash


def test_settlement_component_digest_changes_with_frozen_calendar() -> None:
    model = settlement_model()
    calendar = model.calendar
    changed_day = replace(
        calendar.days[0],
        kind=CnAShareCalendarDayKind.WEEKEND,
    )
    changed_calendar = replace(
        calendar,
        days=(changed_day, *calendar.days[1:]),
    )

    assert (
        CnAShareCashSettlementModel(changed_calendar).component_ref.component_digest
        != model.component_ref.component_digest
    )


def test_xshg_and_xshe_share_economics_but_not_authoritative_identity() -> None:
    xshg = settlement_journey("xshg")
    xshe = settlement_journey("xshe")

    def economics(journey):
        cash = journey.before_availability.cash[0]
        position = journey.before_availability.positions[0]
        return (
            (
                cash.total.units,
                cash.settled.units,
                cash.tradable.units,
                cash.withdrawable.units,
                cash.available_margin.units,
            ),
            (position.total.units, position.sellable.units),
            tuple(
                obligation.units
                for resolution in journey.resolutions
                for obligation in resolution.obligations
            ),
        )

    assert economics(xshg) == economics(xshe)
    assert xshg.forward_book.book_hash != xshe.forward_book.book_hash
    assert xshg.rules.rules_hash != xshe.rules.rules_hash
    assert xshg.before_availability.state_hash != xshe.before_availability.state_hash


_ALLOWED_IMPORTS = {
    "__future__",
    "dataclasses",
    "datetime",
    "enum",
    "typing",
    "unicodedata",
    "zoneinfo",
    "crypto_quant_domain",
    "crypto_quant_trading.ledger",
    "crypto_quant_trading.market_rules",
    "crypto_quant_trading.ports",
    "crypto_quant_trading.settlement",
    "crypto_quant_trading.sizing",
}
_ALLOWED_RELATIVE_IMPORTS = {
    "calendar",
    "commission_tax",
    "order_rules",
    "quantity_lattice",
    "settlement",
}
_ALLOWED_IMPORTS_BY_FILE = {
    "__init__.py": set(),
    "calendar.py": {
        "__future__",
        "dataclasses",
        "datetime",
        "enum",
        "unicodedata",
        "zoneinfo",
        "crypto_quant_domain",
        "crypto_quant_trading.ports",
    },
    "commission_tax.py": {
        "__future__",
        "dataclasses",
        "enum",
        "typing",
        "unicodedata",
        "crypto_quant_domain",
        "crypto_quant_trading.fee_reservations",
        "crypto_quant_trading.fees",
        "crypto_quant_trading.ports",
    },
    "order_rules.py": {
        "__future__",
        "dataclasses",
        "datetime",
        "enum",
        "typing",
        "crypto_quant_domain",
        "crypto_quant_trading.market_rules",
        "crypto_quant_trading.ports",
        "crypto_quant_trading.sizing",
    },
    "quantity_lattice.py": {
        "__future__",
        "dataclasses",
        "enum",
        "unicodedata",
        "crypto_quant_domain",
        "crypto_quant_trading.ports",
        "crypto_quant_trading.sizing",
    },
    "settlement.py": {
        "__future__",
        "dataclasses",
        "datetime",
        "enum",
        "typing",
        "unicodedata",
        "zoneinfo",
        "crypto_quant_domain",
        "crypto_quant_trading.ledger",
        "crypto_quant_trading.ports",
        "crypto_quant_trading.settlement",
    },
}
_ALLOWED_RELATIVE_IMPORTS_BY_FILE = {
    "__init__.py": {
        "calendar",
        "commission_tax",
        "order_rules",
        "quantity_lattice",
        "settlement",
    },
    "calendar.py": set(),
    "commission_tax.py": set(),
    "order_rules.py": {"calendar", "quantity_lattice"},
    "quantity_lattice.py": set(),
    "settlement.py": {"calendar"},
}
_DYNAMIC_IMPORT_CALLS = {
    "__import__",
    "__builtins__.__import__",
    "builtins.__import__",
    "importlib.import_module",
}
_FORBIDDEN_MODULES = {
    "aiohttp",
    "boto3",
    "botocore",
    "builtins",
    "fsspec",
    "http",
    "httpx",
    "importlib.resources",
    "io",
    "os",
    "pathlib",
    "requests",
    "socket",
    "sqlite3",
    "subprocess",
    "tempfile",
    "time",
    "urllib",
    "websockets",
}
_WALL_CLOCK_CALLS = {
    "datetime.date.today",
    "datetime.datetime.now",
    "datetime.datetime.today",
    "datetime.datetime.utcnow",
    "time.time",
    "time.time_ns",
}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        pytest.fail(f"cannot read concrete profile source: {error}")


def _qualified_name(node: ast.expr, aliases: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        owner = _qualified_name(node.value, aliases)
        return f"{owner}.{node.attr}" if owner is not None else None
    return None


def _builtins_member(
    node: ast.expr,
    aliases: dict[str, str],
    member: str,
) -> bool:
    if isinstance(node, ast.Subscript):
        owner = _qualified_name(node.value, aliases)
        return (
            owner == "__builtins__"
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == member
        )
    if isinstance(node, ast.Call) and _qualified_name(node.func, aliases) == "getattr":
        return (
            len(node.args) >= 2
            and _qualified_name(node.args[0], aliases) == "__builtins__"
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == member
        )
    return False


def _dynamic_import_call(node: ast.expr, aliases: dict[str, str]) -> bool:
    if isinstance(node, ast.NamedExpr):
        return _dynamic_import_call(node.value, aliases)
    qualified = _qualified_name(node, aliases)
    if qualified in _DYNAMIC_IMPORT_CALLS:
        return True
    return _builtins_member(node, aliases, "__import__")


def _bind_purity_alias(
    target: ast.expr,
    value: ast.expr,
    aliases: dict[str, str],
) -> None:
    if (
        isinstance(target, (ast.Tuple, ast.List))
        and isinstance(value, (ast.Tuple, ast.List))
        and len(target.elts) == len(value.elts)
    ):
        for target_value, source_value in zip(
            target.elts,
            value.elts,
            strict=True,
        ):
            _bind_purity_alias(target_value, source_value, aliases)
        return
    if not isinstance(target, ast.Name):
        return
    qualified = _qualified_name(value, aliases)
    if _dynamic_import_call(value, aliases):
        aliases[target.id] = "__import__"
    elif _builtins_member(value, aliases, "open"):
        aliases[target.id] = "builtins.open"
    elif qualified is not None:
        aliases[target.id] = qualified
    else:
        aliases.pop(target.id, None)


def _purity_violations(
    source: str,
    *,
    allowed_imports: set[str] | None = None,
    allowed_relative_imports: set[str] | None = None,
) -> set[str]:
    tree = ast.parse(source)
    aliases: dict[str, str] = {}
    violations: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in {
            "__builtins__",
            "__import__",
            "open",
        }:
            violations.add(f"symbol:{node.id}")
        elif isinstance(node, ast.Attribute) and node.attr == "__import__":
            violations.add("symbol:__import__")
        elif isinstance(node, ast.Subscript) and isinstance(
            node.slice, ast.Constant
        ) and node.slice.value in {"__import__", "open"}:
            violations.add(f"symbol:{node.slice.value}")
        elif isinstance(node, ast.ImportFrom) and any(
            alias.name in {"__builtins__", "__import__"}
            for alias in node.names
        ):
            violations.add("import:dynamic_builtins")
    allowed = _ALLOWED_IMPORTS if allowed_imports is None else allowed_imports
    relative_allowed = (
        _ALLOWED_RELATIVE_IMPORTS
        if allowed_relative_imports is None
        else allowed_relative_imports
    )
    ordered_nodes = sorted(
        ast.walk(tree),
        key=lambda node: (
            getattr(node, "lineno", 0),
            getattr(node, "col_offset", 0),
        ),
    )
    for node in ordered_nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".", 1)[0]
                aliases[local] = alias.name
                if alias.name not in allowed:
                    violations.add(f"import:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            permitted = (
                node.level == 1 and module in relative_allowed
                if node.level
                else module in allowed
            )
            if not permitted:
                violations.add(f"import:{module}")
            for alias in node.names:
                aliases[alias.asname or alias.name] = (
                    f"{module}.{alias.name}" if module else alias.name
                )
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                _bind_purity_alias(target, node.value, aliases)
        elif isinstance(node, ast.AnnAssign):
            if node.value is None:
                if isinstance(node.target, ast.Name):
                    aliases.pop(node.target.id, None)
            else:
                _bind_purity_alias(node.target, node.value, aliases)
        elif isinstance(node, ast.NamedExpr):
            _bind_purity_alias(node.target, node.value, aliases)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.NamedExpr):
                _bind_purity_alias(node.func.target, node.func.value, aliases)
            qualified = _qualified_name(node.func, aliases)
            if _dynamic_import_call(node.func, aliases):
                violations.add("call:dynamic_import")
            if _builtins_member(node.func, aliases, "open"):
                violations.add("call:builtins.open")
            if qualified is None:
                continue
            if qualified in {"open", "builtins.open"}:
                violations.add(f"call:{qualified}")
            if qualified in _WALL_CLOCK_CALLS:
                violations.add(f"call:{qualified}")
            if any(
                qualified == module or qualified.startswith(f"{module}.")
                for module in _FORBIDDEN_MODULES
            ):
                violations.add(f"call:{qualified}")
    return violations


def test_concrete_profile_source_is_pure_and_not_root_reexported() -> None:
    root = Path(__file__).resolve().parents[4]
    profile_root = (
        root
        / "packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share"
    )
    for source_path in sorted(profile_root.rglob("*.py")):
        allowed = _ALLOWED_IMPORTS_BY_FILE[source_path.name]
        relative_allowed = _ALLOWED_RELATIVE_IMPORTS_BY_FILE[source_path.name]
        assert not _purity_violations(
            _read_text(source_path),
            allowed_imports=allowed,
            allowed_relative_imports=relative_allowed,
        ), source_path
    generic_root = root / "packages/trading-kernel/src/crypto_quant_trading"
    for source_path in generic_root.glob("*.py"):
        assert "profiles.cn_a_share" not in _read_text(source_path)
        assert "CnAShareCashSettlementModel" not in _read_text(source_path)
        assert "CnAShareCashQuantityLatticeModel" not in _read_text(source_path)
        assert "CnAShareCashMarketFeePolicy" not in _read_text(source_path)
        assert "CnAShareCashStampDutyTaxPolicy" not in _read_text(source_path)


@pytest.mark.parametrize(
    "source",
    (
        'open("x")',
        'import builtins as b\nb.open("x")',
        'import io as x\nx.open("x")',
        'import tempfile as x\nx.NamedTemporaryFile()',
        'import pathlib as x\nx.Path("x")',
        'import os as x\nx.listdir(".")',
        'import sqlite3 as x\nx.connect("x")',
        'import subprocess as x\nx.run(("x",))',
        'import importlib.resources as x\nx.files("x")',
        'import socket as x\nx.create_connection(("x", 1))',
        'import http.client as x\nx.HTTPConnection("x")',
        'import urllib.request as x\nx.urlopen("x")',
        'import requests as x\nx.get("x")',
        'import httpx as x\nx.get("x")',
        'import aiohttp as x\nx.ClientSession()',
        'import websockets as x\nx.connect("x")',
        'import fsspec as x\nx.open("x")',
        'import boto3 as x\nx.client("s3")',
        'import botocore as x\nx.session()',
        'import time as clock\nclock.time()',
        'from time import time_ns as now\nnow()',
        'from datetime import datetime as dt\ndt.now()',
        'from datetime import datetime as dt\ndt.utcnow()',
        'from datetime import date as d\nd.today()',
        '__import__("time")',
        'loader = __import__\nloader("urllib.request")',
        'import builtins as b\nb.__import__("time")',
        'import importlib\nimportlib.import_module("time")',
        '__builtins__["__import__"]("time")',
        'getattr(__builtins__, "__import__")("urllib.request")',
        'loader = __builtins__["__import__"]\nloader("time")',
        'loader = getattr(__builtins__, "__import__")\nloader("urllib.request")',
        'b = __builtins__\nloader = b["__import__"]\nloader("time")',
        'loader = __import__\nloader("time")\nloader = None',
        'loader = __import__\nloader = loader("time")',
        'loader = __import__\nloader: object\nloader("time")',
        'loader = __import__\nif False:\n    loader = None\nloader("time")',
        'loader: object = __import__\nloader("time")',
        '(loader := __import__)("time")',
        '(loader,) = (__import__,)\nloader("time")',
        'b = __builtins__\nloader = getattr(b, "__import__")\nloader("urllib.request")\nloader = object',
        '__builtins__["open"]("x")',
        '((b := __builtins__)["__import__"])("time")',
        'from .calendar import __builtins__ as b\nb["open"]("x")',
        'from calendar import timegm\ntimegm((1, 2, 3))',
        'from ...settlement import AvailabilityState\nAvailabilityState',
    ),
)
def test_purity_scanner_rejects_direct_and_aliased_forbidden_access(
    source: str,
) -> None:
    assert _purity_violations(source)
