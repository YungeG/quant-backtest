from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from crypto_quant_domain import (
    CashBalance,
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    InstrumentId,
    Money,
    OrderSide,
    PositionBalance,
    PositionBalanceKey,
    Price,
    PricePurpose,
    QuantizationPolicy,
    Quantity,
    RoundingPolicy,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
)
from crypto_quant_trading import (
    ActiveOrderReservation,
    ExactAverageEntryBasis,
    ExactLinearUnrealizedPnl,
    JournalReplayCursor,
    LedgerBalanceRegistration,
    LedgerSchema,
    LedgerState,
    LinearAccountMarginProjector,
    LinearAccountMarginProjection,
    LinearAccountMarginProjectionFailure,
    LinearAccountMarginProjectionFailureCode,
    LinearAccountMarginProjectionOutcome,
    LinearAccountMarginProjectionRequest,
    LinearInstrumentMarginModel,
    LinearMarginLedgerEvidence,
    LinearMarginReservationEvidence,
    LinearMarginRuleBook,
    LinearPositionProjector,
    LinearPositionState,
    LinearPositionUnrealizedPnl,
    LinearPositionValuationEvidence,
    OrderReservationCursor,
    ReservationCommitment,
    ResolvedMark,
    ResourceReservationState,
    StaleMarkPolicy,
)

from tests.kernel.derivatives._fixtures import (
    ACCOUNT_ID,
    INSTRUMENT_ID,
    PRICE_SCALE,
    QUOTE_CURRENCY,
    QUANTITY_SCALE,
    VENUE_ID,
    fill,
    position_key,
    request as position_request,
)
from tests.kernel.derivatives.test_linear_margin_requirement import (
    EVALUATED_AT,
    _request as margin_request,
)


CASH_KEY = CashBalanceKey(ACCOUNT_ID, VENUE_ID, QUOTE_CURRENCY)
CASH_REGISTRATION = LedgerBalanceRegistration(CASH_KEY, PRICE_SCALE)


def _available(
    nanoseconds: int = 10, rank: int = 90, code: str = "account_margin_evidence"
) -> SimulationInstant:
    return SimulationInstant(
        UtcInstant(nanoseconds), TimelinePhase(rank, code), SourceSequence(0)
    )


def _position(quantity_units: int = 1_000, entry_price_units: int = 9_000):
    side = OrderSide.BUY if quantity_units > 0 else OrderSide.SELL
    outcome = LinearPositionProjector().project(
        position_request(
            fill(
                "8",
                side=side,
                quantity_units=abs(quantity_units),
                price_units=entry_price_units,
                execution_nanoseconds=1,
            )
        )
    )
    assert outcome.result is not None
    return outcome.result.final_state


def _valuation(quantity_units: int = 1_000) -> LinearPositionValuationEvidence:
    state = _position(quantity_units)
    policy = StaleMarkPolicy(
        "synthetic.account-valuation.v1",
        1,
        PricePurpose.VALUATION,
        10,
        True,
    )
    mark = ResolvedMark(
        instrument_id=INSTRUMENT_ID,
        quote_currency_id=QUOTE_CURRENCY,
        price_purpose=PricePurpose.VALUATION,
        price=Price(
            10_000,
            PRICE_SCALE,
            str(INSTRUMENT_ID),
            str(QUOTE_CURRENCY),
        ),
        observed_at=UtcInstant(8),
        available_at=UtcInstant(9),
        resolved_at=UtcInstant(10),
        age_nanoseconds=2,
        stream_id="synthetic.account-valuation.stream.v1",
        source_event_id="synthetic-account-valuation-event",
        revision_id="synthetic-account-valuation-revision",
        stale_policy_key=policy.policy_key,
        stale_policy_version=policy.policy_version,
        stale_policy_hash=policy.policy_hash,
    )
    return LinearPositionValuationEvidence(state, mark, policy)


def _ledger(quantity_units: int = 1_000) -> LedgerState:
    schema = LedgerSchema(
        (
            CASH_REGISTRATION,
            LedgerBalanceRegistration(position_key(), QUANTITY_SCALE),
        )
    )
    return LedgerState(
        schema=schema,
        cursor=JournalReplayCursor(4, "sha256:" + "4" * 64),
        cash_balances=(CashBalance(CASH_KEY, Money(100_000, PRICE_SCALE, "USDT")),),
        position_balances=(
            PositionBalance(
                position_key(),
                Quantity(quantity_units, QUANTITY_SCALE, str(INSTRUMENT_ID)),
                (),
            ),
        ),
        realized_pnl=(CashBalance(CASH_KEY, Money(200, PRICE_SCALE, "USDT")),),
        fees=(CashBalance(CASH_KEY, Money(100, PRICE_SCALE, "USDT")),),
        financing=(CashBalance(CASH_KEY, Money(50, PRICE_SCALE, "USDT")),),
    )


def _ledger_evidence(quantity_units: int = 1_000) -> LinearMarginLedgerEvidence:
    return LinearMarginLedgerEvidence(
        ledger_state=_ledger(quantity_units),
        projected_through=EVALUATED_AT,
        available_at=_available(),
        source_key="synthetic.account-margin-ledger.v1",
        source_hash="sha256:" + "5" * 64,
    )


def _reservation(
    margin_units: int = 200, *, margin_currency: str = "USDT"
) -> ResourceReservationState:
    if margin_units == 0:
        return ResourceReservationState(
            ACCOUNT_ID, (), (), ReservationCommitment.empty()
        )
    order_id = DomainId(DomainIdKind.ORDER, "ord_" + "6" * 64)
    commitment = ReservationCommitment(
        cash=(Money(300, PRICE_SCALE, "USDT"),),
        margin=(Money(margin_units, PRICE_SCALE, margin_currency),),
        fee_reserve=(Money(25, PRICE_SCALE, "USDT"),),
        order_capacity_units=1,
        exposure_capacity=(Money(500, PRICE_SCALE, "USDT"),),
    )
    cursor = OrderReservationCursor(
        order_id,
        1,
        "sha256:" + "7" * 64,
        "sha256:" + "8" * 64,
    )
    active = ActiveOrderReservation(
        ACCOUNT_ID,
        order_id,
        "synthetic-order-accepted",
        Quantity(500, QUANTITY_SCALE, str(INSTRUMENT_ID)),
        commitment,
        "sha256:" + "9" * 64,
    )
    return ResourceReservationState(ACCOUNT_ID, (cursor,), (active,), commitment)


def _reservation_evidence(
    margin_units: int = 200,
) -> LinearMarginReservationEvidence:
    return LinearMarginReservationEvidence(
        reservation_state=_reservation(margin_units),
        projected_through=EVALUATED_AT,
        available_at=_available(),
        source_key="synthetic.account-margin-reservation.v1",
        source_hash="sha256:" + "a" * 64,
    )


def _margin_result(quantity_units: int = 1_000):
    from crypto_quant_trading import LinearInstrumentMarginModel

    outcome = LinearInstrumentMarginModel().evaluate_margin(
        margin_request(quantity_units)
    )
    assert outcome.result is not None
    return outcome.result


def _request(
    quantity_units: int = 1_000,
    *,
    ledger_evidence: LinearMarginLedgerEvidence | None = None,
    reservation_evidence: LinearMarginReservationEvidence | None = None,
) -> LinearAccountMarginProjectionRequest:
    return LinearAccountMarginProjectionRequest(
        account_id=ACCOUNT_ID,
        venue_id=VENUE_ID,
        evaluated_at=EVALUATED_AT,
        ledger_evidence=(
            _ledger_evidence(quantity_units)
            if ledger_evidence is None
            else ledger_evidence
        ),
        position_valuations=(_valuation(quantity_units),),
        margin_results=(_margin_result(quantity_units),),
        reservation_evidence=(
            _reservation_evidence()
            if reservation_evidence is None
            else reservation_evidence
        ),
        settlement_cash_registration=CASH_REGISTRATION,
        unrealized_pnl_quantization=QuantizationPolicy(
            "synthetic.account-unrealized-pnl.v1",
            PRICE_SCALE,
            RoundingPolicy.HALF_EVEN,
        ),
    )


def test_wallet_unrealized_equity_and_margin_aggregates_are_exact() -> None:
    outcome = LinearAccountMarginProjector().project(_request())

    assert outcome.failure is None
    assert outcome.projection is not None
    projection = outcome.projection
    assert projection.wallet_balance.units == 100_000
    assert projection.realized_pnl.units == 200
    assert projection.fees.units == 100
    assert projection.funding.units == 50
    expected_position_pnl = (
        LinearPositionUnrealizedPnl(
            projection.request.position_valuations[0],
            projection.request.position_valuations[0].valuation_evidence_hash,
            ExactLinearUnrealizedPnl(QUOTE_CURRENCY, 5, 4),
            Money(125, PRICE_SCALE, "USDT"),
        ),
    )
    assert projection.position_unrealized_pnl == expected_position_pnl
    assert projection.total_unrealized_pnl.units == 125
    assert projection.equity.units == 100_125
    assert projection.total_initial_margin.units == 125
    assert projection.total_maintenance_margin.units == 13
    assert projection.working_order_margin_reservation.units == 200
    assert projection.available_margin.units == 99_800


def test_short_direction_and_non_margin_reservation_dimensions_are_not_net_equity() -> None:
    outcome = LinearAccountMarginProjector().project(_request(-1_000))

    assert outcome.projection is not None
    projection = outcome.projection
    assert projection.position_unrealized_pnl[0].exact_unrealized_pnl == (
        ExactLinearUnrealizedPnl(QUOTE_CURRENCY, -5, 4)
    )
    assert projection.equity.units == 99_875
    assert projection.working_order_margin_reservation.units == 200
    assert projection.available_margin.units == 99_550


def test_missing_evidence_precedence_is_fail_closed() -> None:
    request = _request()
    outcome = LinearAccountMarginProjector().project(
        replace(request, ledger_evidence=None, reservation_evidence=None)
    )

    assert len(LinearAccountMarginProjectionFailureCode) == 25
    assert outcome.projection is None
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is LinearAccountMarginProjectionFailureCode.MISSING_LEDGER_EVIDENCE
    )
    assert outcome.failure.subject_ids[0] == "missing_ledger_evidence"


def _with_valuation(
    request: LinearAccountMarginProjectionRequest,
    evidence: LinearPositionValuationEvidence,
) -> LinearAccountMarginProjectionRequest:
    return replace(request, position_valuations=(evidence,))


def _failure_cases() -> list[
    tuple[
        LinearAccountMarginProjectionFailureCode,
        LinearAccountMarginProjectionRequest,
    ]
]:
    request = _request()
    ledger = request.ledger_evidence
    reservation = request.reservation_evidence
    valuation = request.position_valuations[0]
    mark = valuation.resolved_mark
    assert ledger is not None and reservation is not None
    later = SimulationInstant(
        EVALUATED_AT.instant,
        TimelinePhase(110, "later_account_margin_evidence"),
        SourceSequence(0),
    )
    late_mark = deepcopy(mark)
    object.__setattr__(late_mark, "available_at", UtcInstant(11))
    other_instrument = InstrumentId(VENUE_ID, "eth-usdt-linear-perpetual")
    other_price = Price(
        mark.price.units,
        mark.price.scale,
        str(other_instrument),
        str(QUOTE_CURRENCY),
    )
    wrong_reservation = LinearMarginReservationEvidence(
        ResourceReservationState(
            "other-account", (), (), ReservationCommitment.empty()
        ),
        EVALUATED_AT,
        _available(),
        "synthetic.other-reservation.v1",
        "sha256:" + "b" * 64,
    )
    wrong_margin_state = _reservation(margin_currency="USD")
    wrong_margin_reservation = replace(
        reservation, reservation_state=wrong_margin_state
    )
    return [
        (
            LinearAccountMarginProjectionFailureCode.MISSING_LEDGER_EVIDENCE,
            replace(request, ledger_evidence=None),
        ),
        (
            LinearAccountMarginProjectionFailureCode.MISSING_RESERVATION_EVIDENCE,
            replace(request, reservation_evidence=None),
        ),
        (
            LinearAccountMarginProjectionFailureCode.ACCOUNT_CONTEXT_MISMATCH,
            replace(request, account_id="other-account"),
        ),
        (
            LinearAccountMarginProjectionFailureCode.LEDGER_PROJECTION_INSTANT_MISMATCH,
            replace(
                request,
                ledger_evidence=replace(ledger, projected_through=_available(9)),
            ),
        ),
        (
            LinearAccountMarginProjectionFailureCode.LEDGER_NOT_AVAILABLE,
            replace(request, ledger_evidence=replace(ledger, available_at=later)),
        ),
        (
            LinearAccountMarginProjectionFailureCode.RESERVATION_PROJECTION_INSTANT_MISMATCH,
            replace(
                request,
                reservation_evidence=replace(
                    reservation, projected_through=_available(9)
                ),
            ),
        ),
        (
            LinearAccountMarginProjectionFailureCode.RESERVATION_NOT_AVAILABLE,
            replace(
                request,
                reservation_evidence=replace(reservation, available_at=later),
            ),
        ),
        (
            LinearAccountMarginProjectionFailureCode.SETTLEMENT_CASH_CONTEXT_MISMATCH,
            replace(
                request,
                settlement_cash_registration=LedgerBalanceRegistration(
                    CashBalanceKey("other-account", VENUE_ID, QUOTE_CURRENCY),
                    PRICE_SCALE,
                ),
            ),
        ),
        (
            LinearAccountMarginProjectionFailureCode.DUPLICATE_POSITION,
            replace(
                request,
                position_valuations=(valuation, valuation),
                margin_results=(request.margin_results[0], request.margin_results[0]),
            ),
        ),
        (
            LinearAccountMarginProjectionFailureCode.POSITION_CONTEXT_MISMATCH,
            replace(request, position_valuations=(_valuation(2_000),)),
        ),
        (
            LinearAccountMarginProjectionFailureCode.DUPLICATE_MARGIN_RESULT,
            replace(
                request,
                margin_results=(request.margin_results[0], request.margin_results[0]),
            ),
        ),
        (
            LinearAccountMarginProjectionFailureCode.MARGIN_COVERAGE_MISMATCH,
            replace(request, margin_results=()),
        ),
        (
            LinearAccountMarginProjectionFailureCode.MARGIN_CONTEXT_MISMATCH,
            replace(request, margin_results=(_margin_result(-1_000),)),
        ),
        (
            LinearAccountMarginProjectionFailureCode.VALUATION_COVERAGE_MISMATCH,
            replace(request, position_valuations=(), margin_results=()),
        ),
        (
            LinearAccountMarginProjectionFailureCode.VALUATION_MARK_PURPOSE_MISMATCH,
            _with_valuation(
                request,
                replace(
                    valuation,
                    resolved_mark=replace(
                        mark, price_purpose=PricePurpose.MARGIN
                    ),
                ),
            ),
        ),
        (
            LinearAccountMarginProjectionFailureCode.VALUATION_MARK_CONTEXT_MISMATCH,
            _with_valuation(
                request,
                replace(
                    valuation,
                    resolved_mark=replace(
                        mark,
                        instrument_id=other_instrument,
                        price=other_price,
                    ),
                ),
            ),
        ),
        (
            LinearAccountMarginProjectionFailureCode.VALUATION_MARK_INSTANT_MISMATCH,
            _with_valuation(
                request,
                replace(
                    valuation,
                    resolved_mark=replace(
                        mark, resolved_at=UtcInstant(11), age_nanoseconds=3
                    ),
                ),
            ),
        ),
        (
            LinearAccountMarginProjectionFailureCode.VALUATION_MARK_SCALE_MISMATCH,
            _with_valuation(
                request,
                replace(
                    valuation,
                    resolved_mark=replace(
                        mark,
                        price=Price(
                            100_000,
                            type(PRICE_SCALE)(3),
                            str(INSTRUMENT_ID),
                            str(QUOTE_CURRENCY),
                        ),
                    ),
                ),
            ),
        ),
        (
            LinearAccountMarginProjectionFailureCode.NON_POSITIVE_VALUATION_MARK,
            _with_valuation(
                request,
                replace(
                    valuation,
                    resolved_mark=replace(
                        mark, price=replace(mark.price, units=0)
                    ),
                ),
            ),
        ),
        (
            LinearAccountMarginProjectionFailureCode.VALUATION_MARK_POLICY_MISMATCH,
            _with_valuation(
                request,
                replace(
                    valuation,
                    stale_policy=replace(
                        valuation.stale_policy,
                        policy_key="other.account-valuation.v1",
                    ),
                ),
            ),
        ),
        (
            LinearAccountMarginProjectionFailureCode.VALUATION_MARK_NOT_AVAILABLE,
            _with_valuation(
                request, replace(valuation, resolved_mark=late_mark)
            ),
        ),
        (
            LinearAccountMarginProjectionFailureCode.QUANTIZATION_SCALE_MISMATCH,
            replace(
                request,
                unrealized_pnl_quantization=replace(
                    request.unrealized_pnl_quantization,
                    target_scale=type(PRICE_SCALE)(3),
                ),
            ),
        ),
        (
            LinearAccountMarginProjectionFailureCode.UNSAFE_UNREALIZED_PNL_ROUNDING,
            replace(
                request,
                unrealized_pnl_quantization=replace(
                    request.unrealized_pnl_quantization,
                    rounding=RoundingPolicy.CEILING,
                ),
            ),
        ),
        (
            LinearAccountMarginProjectionFailureCode.RESERVATION_CONTEXT_MISMATCH,
            replace(request, reservation_evidence=wrong_reservation),
        ),
        (
            LinearAccountMarginProjectionFailureCode.RESERVATION_MARGIN_CONTEXT_MISMATCH,
            replace(request, reservation_evidence=wrong_margin_reservation),
        ),
    ]


def test_all_failures_follow_frozen_precedence() -> None:
    cases = _failure_cases()
    assert len(cases) == len(LinearAccountMarginProjectionFailureCode) == 25

    for expected, request in cases:
        outcome = LinearAccountMarginProjector().project(request)
        assert outcome.projection is None
        assert outcome.failure is not None
        assert outcome.failure.code is expected
        assert len(outcome.failure.subject_ids) == 6
        assert outcome.failure.subject_ids[0] == expected.value


def test_multiple_instruments_aggregate_without_cross_account_or_currency_netting() -> None:
    request = _request()
    first_valuation = request.position_valuations[0]
    first_state = first_valuation.position_state
    second_instrument = InstrumentId(VENUE_ID, "eth-usdt-linear-perpetual")
    second_contract = replace(
        first_state.contract,
        instrument=replace(
            first_state.contract.instrument,
            instrument_id=second_instrument,
            base_currency=CurrencyId("ETH"),
        ),
    )
    second_key = PositionBalanceKey(ACCOUNT_ID, VENUE_ID, second_instrument)
    second_state = LinearPositionState(
        second_key,
        second_contract,
        Quantity(1_000, QUANTITY_SCALE, str(second_instrument)),
        ExactAverageEntryBasis(second_instrument, QUOTE_CURRENCY, 90, 1),
    )
    second_mark = replace(
        first_valuation.resolved_mark,
        instrument_id=second_instrument,
        price=Price(
            10_000,
            PRICE_SCALE,
            str(second_instrument),
            str(QUOTE_CURRENCY),
        ),
        stream_id="synthetic.eth-account-valuation.stream.v1",
        source_event_id="synthetic-eth-account-valuation-event",
        revision_id="synthetic-eth-account-valuation-revision",
    )
    second_valuation = LinearPositionValuationEvidence(
        second_state, second_mark, first_valuation.stale_policy
    )

    base_margin_request = margin_request()
    assert base_margin_request.rule_book is not None
    assert base_margin_request.margin_mark_evidence is not None
    assert base_margin_request.leverage_evidence is not None
    second_margin_request = replace(
        base_margin_request,
        position_key=second_key,
        contract=second_contract,
        exposure_quantity=Quantity(
            1_000, QUANTITY_SCALE, str(second_instrument)
        ),
        leverage_evidence=replace(
            base_margin_request.leverage_evidence,
            instrument_id=second_instrument,
        ),
        rule_book=LinearMarginRuleBook.create(
            rule_book_key="synthetic.eth-linear-margin-rules.v1",
            rule_book_version=1,
            instrument_id=second_instrument,
            settlement_currency_id=QUOTE_CURRENCY,
            tier_scale=PRICE_SCALE,
            intervals=base_margin_request.rule_book.intervals,
        ),
        margin_mark_evidence=replace(
            base_margin_request.margin_mark_evidence,
            resolved_mark=replace(
                base_margin_request.margin_mark_evidence.resolved_mark,
                instrument_id=second_instrument,
                price=Price(
                    10_000,
                    PRICE_SCALE,
                    str(second_instrument),
                    str(QUOTE_CURRENCY),
                ),
                stream_id="synthetic.eth-margin-mark.stream.v1",
                source_event_id="synthetic-eth-margin-mark-event",
                revision_id="synthetic-eth-margin-mark-revision",
            ),
        ),
    )
    second_margin = LinearInstrumentMarginModel().evaluate_margin(
        second_margin_request
    )
    assert second_margin.result is not None

    ledger = request.ledger_evidence
    assert ledger is not None
    second_registration = LedgerBalanceRegistration(second_key, QUANTITY_SCALE)
    position_balances = tuple(
        sorted(
            ledger.ledger_state.position_balances
            + (
                PositionBalance(
                    second_key,
                    second_state.quantity,
                    (),
                ),
            ),
            key=lambda value: canonical_bytes(value.key),
        )
    )
    multi_ledger = LedgerState(
        LedgerSchema(ledger.ledger_state.schema.registrations + (second_registration,)),
        ledger.ledger_state.cursor,
        ledger.ledger_state.cash_balances,
        position_balances,
        ledger.ledger_state.realized_pnl,
        ledger.ledger_state.fees,
        ledger.ledger_state.financing,
    )
    outcome = LinearAccountMarginProjector().project(
        replace(
            request,
            ledger_evidence=replace(ledger, ledger_state=multi_ledger),
            position_valuations=(first_valuation, second_valuation),
            margin_results=(request.margin_results[0], second_margin.result),
        )
    )

    assert outcome.projection is not None
    projection = outcome.projection
    assert len(projection.position_unrealized_pnl) == 2
    assert projection.total_unrealized_pnl.units == 250
    assert projection.equity.units == 100_250
    assert projection.total_initial_margin.units == 250
    assert projection.total_maintenance_margin.units == 26
    assert projection.available_margin.units == 99_800


def test_large_integer_unrealized_pnl_is_exact_without_pre_quantization() -> None:
    quantity_units = 10**15 + 1
    outcome = LinearAccountMarginProjector().project(
        _request(
            quantity_units,
            reservation_evidence=_reservation_evidence(0),
        )
    )

    assert outcome.projection is not None
    assert outcome.projection.position_unrealized_pnl[0].exact_unrealized_pnl == (
        ExactLinearUnrealizedPnl(QUOTE_CURRENCY, quantity_units, 800)
    )


def test_negative_available_margin_is_state_not_failure_and_is_idempotent() -> None:
    request = _request(
        reservation_evidence=_reservation_evidence(200_000)
    )
    before = deepcopy(request)

    first = LinearAccountMarginProjector().project(request)
    second = LinearAccountMarginProjector().project(request)

    assert first == second
    assert request == before
    assert first.failure is None
    assert first.projection is not None
    assert first.projection.equity.units == 100_125
    assert first.projection.available_margin.units == -100_000


def test_projection_and_pnl_constructors_reject_forgery() -> None:
    outcome = LinearAccountMarginProjector().project(_request())
    assert outcome.projection is not None
    projection = outcome.projection
    with pytest.raises(ValueError, match="Projection fields"):
        LinearAccountMarginProjection(
            projection.component_ref,
            projection.request,
            projection.request_hash,
            projection.wallet_balance,
            projection.realized_pnl,
            projection.fees,
            projection.funding,
            projection.position_unrealized_pnl,
            projection.total_unrealized_pnl,
            projection.equity,
            projection.total_initial_margin,
            projection.total_maintenance_margin,
            projection.working_order_margin_reservation,
            replace(
                projection.available_margin,
                units=projection.available_margin.units + 1,
            ),
        )
    position_pnl = projection.position_unrealized_pnl[0]
    with pytest.raises(ValueError, match="Unrealized PnL fields"):
        LinearPositionUnrealizedPnl(
            position_pnl.valuation_evidence,
            position_pnl.valuation_evidence_hash,
            ExactLinearUnrealizedPnl(QUOTE_CURRENCY, 3, 2),
            position_pnl.unrealized_pnl,
        )
    with pytest.raises(ValueError, match="GCD-reduced"):
        ExactLinearUnrealizedPnl(QUOTE_CURRENCY, 2, 2)


def test_public_projection_values_are_frozen_contract_types() -> None:
    outcome: LinearAccountMarginProjectionOutcome = (
        LinearAccountMarginProjector().project(_request())
    )
    assert isinstance(outcome.projection, LinearAccountMarginProjection)
    assert not isinstance(outcome.failure, LinearAccountMarginProjectionFailure)
