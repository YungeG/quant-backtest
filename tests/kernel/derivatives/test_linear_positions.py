from __future__ import annotations

from dataclasses import replace
from typing import cast

from crypto_quant_domain import (
    CurrencyId,
    DomainId,
    Fill,
    InstrumentId,
    InstrumentType,
    Money,
    OrderSide,
    PositionBalanceKey,
    Price,
    Quantity,
    Rate,
    Scale,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
import pytest
import crypto_quant_trading
from crypto_quant_trading import (
    ExactAverageEntryBasis,
    LinearPerpetualContract,
    LinearPositionProjectionFailureCode,
    LinearPositionProjectionOutcome,
    LinearPositionProjectionRequest,
    LinearPositionProjector,
    LinearPositionState,
    LinearPositionTransition,
    LinearPositionTransitionKind,
)

from tests.kernel.derivatives._fixtures import (
    INSTRUMENT_ID,
    PRICE_SCALE,
    QUOTE_CURRENCY,
    VENUE_ID,
    contract,
    fill,
    position_key,
    request,
)


def test_buy_from_flat_opens_a_long_position_with_exact_fill_basis() -> None:
    projection_request = request(
        fill(
            "1",
            side=OrderSide.BUY,
            quantity_units=1_000,
            price_units=10_000,
            execution_nanoseconds=1,
        )
    )

    outcome = LinearPositionProjector().project(projection_request)

    assert outcome.failure is None
    assert outcome.result is not None
    assert len(outcome.result.transitions) == 1
    transition = outcome.result.transitions[0]
    assert transition.kind is LinearPositionTransitionKind.OPEN
    assert transition.closed_quantity == Quantity(
        0, Scale(3), str(INSTRUMENT_ID)
    )
    assert transition.after.quantity == Quantity(
        1_000, Scale(3), str(INSTRUMENT_ID)
    )
    assert transition.after.average_entry_basis == ExactAverageEntryBasis(
        INSTRUMENT_ID,
        QUOTE_CURRENCY,
        100,
        1,
    )
    assert outcome.result.final_state == transition.after


def test_ordered_fills_project_open_add_reduce_close_and_flip_exactly() -> None:
    projection_request = request(
        fill("1", side=OrderSide.BUY, quantity_units=1_000, price_units=10_000, execution_nanoseconds=1),
        fill("2", side=OrderSide.BUY, quantity_units=2_000, price_units=10_050, execution_nanoseconds=2),
        fill("3", side=OrderSide.SELL, quantity_units=1_000, price_units=9_900, execution_nanoseconds=3),
        fill("4", side=OrderSide.SELL, quantity_units=2_000, price_units=9_900, execution_nanoseconds=4),
        fill("5", side=OrderSide.SELL, quantity_units=1_000, price_units=10_100, execution_nanoseconds=5),
        fill("6", side=OrderSide.SELL, quantity_units=1_000, price_units=10_200, execution_nanoseconds=6),
        fill("7", side=OrderSide.BUY, quantity_units=500, price_units=10_000, execution_nanoseconds=7),
        fill("8", side=OrderSide.BUY, quantity_units=2_000, price_units=9_900, execution_nanoseconds=8),
    )

    outcome = LinearPositionProjector().project(projection_request)

    assert outcome.failure is None
    assert outcome.result is not None
    transitions = outcome.result.transitions
    kinds = tuple(value.kind for value in transitions)
    quantities = tuple(value.after.quantity.units for value in transitions)
    closed_quantities = tuple(value.closed_quantity.units for value in transitions)
    expected_kinds = (
        LinearPositionTransitionKind.OPEN,
        LinearPositionTransitionKind.ADD,
        LinearPositionTransitionKind.REDUCE,
        LinearPositionTransitionKind.CLOSE,
        LinearPositionTransitionKind.OPEN,
        LinearPositionTransitionKind.ADD,
        LinearPositionTransitionKind.REDUCE,
        LinearPositionTransitionKind.FLIP,
    )
    expected_quantities = (
        1_000,
        3_000,
        2_000,
        0,
        -1_000,
        -2_000,
        -1_500,
        500,
    )
    expected_closed_quantities = (
        0,
        0,
        1_000,
        2_000,
        0,
        0,
        500,
        1_500,
    )
    assert kinds == expected_kinds
    assert quantities == expected_quantities
    assert closed_quantities == expected_closed_quantities
    assert transitions[1].after.average_entry_basis == ExactAverageEntryBasis(
        INSTRUMENT_ID, QUOTE_CURRENCY, 301, 3
    )
    assert (
        transitions[2].after.average_entry_basis
        == transitions[1].after.average_entry_basis
    )
    assert transitions[3].after.average_entry_basis is None
    assert transitions[5].after.average_entry_basis == ExactAverageEntryBasis(
        INSTRUMENT_ID, QUOTE_CURRENCY, 203, 2
    )
    assert (
        transitions[6].after.average_entry_basis
        == transitions[5].after.average_entry_basis
    )
    assert transitions[7].after.average_entry_basis == ExactAverageEntryBasis(
        INSTRUMENT_ID, QUOTE_CURRENCY, 99, 1
    )
    assert outcome.result.final_state == transitions[-1].after


def test_empty_prefix_and_equal_time_order_are_canonical_business_semantics() -> None:
    projector = LinearPositionProjector()
    empty_request = request()
    empty = projector.project(empty_request)
    assert empty.failure is None
    assert empty.result is not None
    assert not empty.result.transitions
    assert empty.result.final_state.quantity.units == 0
    assert empty.result.final_state.average_entry_basis is None

    first = fill(
        "1",
        side=OrderSide.BUY,
        quantity_units=1_000,
        price_units=10_000,
        execution_nanoseconds=10,
    )
    second = fill(
        "2",
        side=OrderSide.BUY,
        quantity_units=2_000,
        price_units=10_050,
        execution_nanoseconds=10,
    )
    prefix = projector.project(request(first))
    forward = projector.project(request(first, second))
    reverse = projector.project(request(second, first))
    assert prefix.result is not None
    assert forward.result is not None
    assert reverse.result is not None
    assert prefix.result.transitions == forward.result.transitions[:1]
    assert forward.result.final_state == reverse.result.final_state
    assert forward.result.request_hash != reverse.result.request_hash
    assert forward.result.projection_hash != reverse.result.projection_hash
    assert (
        forward.result.transitions[0].transition_hash
        != reverse.result.transitions[0].transition_hash
    )


def test_projection_failures_are_atomic_and_follow_frozen_precedence() -> None:
    projector = LinearPositionProjector()
    valid = fill(
        "1",
        side=OrderSide.BUY,
        quantity_units=1_000,
        price_units=10_000,
        execution_nanoseconds=10,
    )

    other_instrument = InstrumentId(VENUE_ID, "other-linear-perpetual")
    position_mismatch = projector.project(
        type(request())(
            PositionBalanceKey("synthetic-linear-account", VENUE_ID, other_instrument),
            contract(),
            (valid,),
        )
    )
    assert position_mismatch.result is None
    assert position_mismatch.failure is not None
    assert (
        position_mismatch.failure.code
        is LinearPositionProjectionFailureCode.POSITION_CONTEXT_MISMATCH
    )
    assert position_mismatch.failure.fill_index is None
    assert position_mismatch.failure.fill_id is None

    duplicate = projector.project(request(valid, replace(valid, execution_time=type(valid.execution_time)(9))))
    assert duplicate.result is None
    assert duplicate.failure is not None
    assert duplicate.failure.code is LinearPositionProjectionFailureCode.DUPLICATE_FILL_ID
    assert duplicate.failure.fill_index == 1
    assert duplicate.failure.fill_id == valid.fill_id

    later = fill(
        "2",
        side=OrderSide.BUY,
        quantity_units=1_000,
        price_units=10_000,
        execution_nanoseconds=9,
    )
    regression = projector.project(request(valid, later))
    assert regression.failure is not None
    assert (
        regression.failure.code
        is LinearPositionProjectionFailureCode.NON_MONOTONIC_EXECUTION_TIME
    )
    assert regression.failure.fill_index == 1
    assert regression.failure.fill_id == later.fill_id

    account_mismatch_fill = replace(valid, account_id="other-account")
    account_mismatch = projector.project(request(account_mismatch_fill))
    assert account_mismatch.failure is not None
    assert (
        account_mismatch.failure.code
        is LinearPositionProjectionFailureCode.FILL_CONTEXT_MISMATCH
    )

    quantity_scale_fill = replace(
        valid,
        quantity=Quantity(100, Scale(2), str(INSTRUMENT_ID)),
    )
    quantity_scale = projector.project(request(quantity_scale_fill))
    assert quantity_scale.failure is not None
    assert (
        quantity_scale.failure.code
        is LinearPositionProjectionFailureCode.QUANTITY_SCALE_MISMATCH
    )

    usd = CurrencyId("USD")
    wrong_currency_price = Price(
        valid.price.units,
        PRICE_SCALE,
        str(INSTRUMENT_ID),
        str(usd),
    )
    price_context_fill = replace(
        valid,
        reference_price=wrong_currency_price,
        price=wrong_currency_price,
        slippage_amount=Money(0, PRICE_SCALE, str(usd)),
    )
    price_context = projector.project(request(price_context_fill))
    assert price_context.failure is not None
    assert (
        price_context.failure.code
        is LinearPositionProjectionFailureCode.PRICE_CONTEXT_MISMATCH
    )

    wrong_scale_price = Price(
        valid.price.units * 10,
        Scale(3),
        str(INSTRUMENT_ID),
        str(QUOTE_CURRENCY),
    )
    price_scale_fill = replace(
        valid,
        reference_price=wrong_scale_price,
        price=wrong_scale_price,
    )
    price_scale = projector.project(request(price_scale_fill))
    assert price_scale.failure is not None
    assert (
        price_scale.failure.code
        is LinearPositionProjectionFailureCode.PRICE_SCALE_MISMATCH
    )

    combined_fill_context = projector.project(
        request(
            replace(
                account_mismatch_fill,
                quantity=Quantity(100, Scale(2), str(INSTRUMENT_ID)),
            )
        )
    )
    assert combined_fill_context.failure is not None
    assert (
        combined_fill_context.failure.code
        is LinearPositionProjectionFailureCode.FILL_CONTEXT_MISMATCH
    )
    wrong_currency_scale_price = Price(
        valid.price.units * 10,
        Scale(3),
        str(INSTRUMENT_ID),
        str(usd),
    )
    combined_price_context = projector.project(
        request(
            replace(
                valid,
                reference_price=wrong_currency_scale_price,
                price=wrong_currency_scale_price,
                slippage_amount=Money(0, PRICE_SCALE, str(usd)),
            )
        )
    )
    assert combined_price_context.failure is not None
    assert (
        combined_price_context.failure.code
        is LinearPositionProjectionFailureCode.PRICE_CONTEXT_MISMATCH
    )
    position_precedence = projector.project(
        type(request())(
            PositionBalanceKey("synthetic-linear-account", VENUE_ID, other_instrument),
            contract(),
            (valid, valid),
        )
    )
    assert position_precedence.failure is not None
    assert (
        position_precedence.failure.code
        is LinearPositionProjectionFailureCode.POSITION_CONTEXT_MISMATCH
    )

    assert position_key() == request().position_key


def test_public_values_recompute_embedded_state_and_reject_forgery() -> None:
    valid_contract = contract()
    with pytest.raises(ValueError, match="LINEAR_PERPETUAL"):
        replace(
            valid_contract,
            instrument=replace(
                valid_contract.instrument,
                instrument_type=InstrumentType.SPOT,
            ),
        )
    with pytest.raises(ValueError, match="base currency"):
        replace(
            valid_contract,
            instrument=replace(valid_contract.instrument, base_currency=None),
        )
    with pytest.raises(ValueError, match="quote and settlement"):
        replace(
            valid_contract,
            instrument=replace(
                valid_contract.instrument,
                settlement_currency=CurrencyId("USD"),
            ),
        )
    with pytest.raises(ValueError, match="contract multiplier"):
        replace(
            valid_contract,
            contract_multiplier=Rate(1, Scale(0), "fraction"),
        )

    with pytest.raises(ValueError, match="GCD-reduced"):
        ExactAverageEntryBasis(INSTRUMENT_ID, QUOTE_CURRENCY, 200, 2)
    with pytest.raises(ValueError, match="positive"):
        ExactAverageEntryBasis(INSTRUMENT_ID, QUOTE_CURRENCY, 0, 1)

    flat = LinearPositionState(
        position_key(),
        valid_contract,
        Quantity(0, Scale(3), str(INSTRUMENT_ID)),
        None,
    )
    with pytest.raises(ValueError, match="flat state"):
        replace(
            flat,
            average_entry_basis=ExactAverageEntryBasis(
                INSTRUMENT_ID, QUOTE_CURRENCY, 100, 1
            ),
        )
    with pytest.raises(ValueError, match="non-flat state"):
        replace(
            flat,
            quantity=Quantity(1_000, Scale(3), str(INSTRUMENT_ID)),
        )

    class ForgedBasis:
        instrument_id = INSTRUMENT_ID
        quote_currency = QUOTE_CURRENCY
        numerator = 100
        denominator = 1

        def to_canonical_dict(self) -> dict[str, object]:
            return ExactAverageEntryBasis(
                INSTRUMENT_ID, QUOTE_CURRENCY, 100, 1
            ).to_canonical_dict()

    with pytest.raises(TypeError, match="ExactAverageEntryBasis"):
        LinearPositionState(
            position_key(),
            valid_contract,
            Quantity(1_000, Scale(3), str(INSTRUMENT_ID)),
            cast(ExactAverageEntryBasis, ForgedBasis()),
        )

    class ForgedTuple(tuple[object, ...]):
        pass

    with pytest.raises(TypeError, match="exact tuple of Fill"):
        LinearPositionProjectionRequest(
            position_key(),
            valid_contract,
            cast(tuple[Fill, ...], ForgedTuple()),
        )

    class ForgedDomainId(DomainId):
        pass

    valid_fill = fill(
        "f",
        side=OrderSide.BUY,
        quantity_units=1_000,
        price_units=10_000,
        execution_nanoseconds=1,
    )
    forged_fill = replace(
        valid_fill,
        fill_id=ForgedDomainId(valid_fill.fill_id.kind, valid_fill.fill_id.value),
    )
    with pytest.raises(TypeError, match="fill_id must be exact DomainId"):
        request(forged_fill)

    class ForgedStr(str):
        pass

    forged_venue = VenueId(ForgedStr(VENUE_ID.value))
    forged_venue_fill = replace(valid_fill, venue_id=forged_venue)
    with pytest.raises(TypeError, match="Venue identities must be exact"):
        request(forged_venue_fill)
    forged_key = PositionBalanceKey(
        "synthetic-linear-account",
        forged_venue,
        InstrumentId(forged_venue, INSTRUMENT_ID.stable_key),
    )
    with pytest.raises(TypeError, match="venue_id must be exact VenueId"):
        LinearPositionProjectionRequest(forged_key, valid_contract, ())

    projection_request = request(
        fill("1", side=OrderSide.BUY, quantity_units=1_000, price_units=10_000, execution_nanoseconds=1),
        fill("2", side=OrderSide.SELL, quantity_units=2_000, price_units=9_900, execution_nanoseconds=2),
    )
    outcome = LinearPositionProjector().project(projection_request)
    assert outcome.result is not None
    result = outcome.result
    first, second = result.transitions

    class ForgedState(LinearPositionState):
        def __eq__(self, other: object) -> bool:
            return True

    forged_after = ForgedState(
        first.after.position_key,
        first.after.contract,
        Quantity(2_000, Scale(3), str(INSTRUMENT_ID)),
        first.after.average_entry_basis,
    )
    with pytest.raises(TypeError, match="exact LinearPositionState"):
        replace(first, after=cast(LinearPositionState, forged_after))

    class ForgedTransition(LinearPositionTransition):
        def __eq__(self, other: object) -> bool:
            return True

    forged_transition = ForgedTransition(
        first.kind,
        first.fill,
        first.before,
        first.after,
        first.closed_quantity,
    )
    with pytest.raises(TypeError, match="tuple of LinearPositionTransition"):
        replace(
            result,
            transitions=(
                cast(LinearPositionTransition, forged_transition),
                second,
            ),
        )
    with pytest.raises(TypeError, match="tuple of LinearPositionTransition"):
        replace(
            result,
            transitions=cast(
                tuple[LinearPositionTransition, ...],
                ForgedTuple(result.transitions),
            ),
        )

    with pytest.raises(ValueError, match="transition"):
        replace(first, kind=LinearPositionTransitionKind.CLOSE)
    with pytest.raises(ValueError, match="transition"):
        replace(first, closed_quantity=replace(first.closed_quantity, units=1))
    with pytest.raises(ValueError, match="transition"):
        replace(second, after=second.before)
    with pytest.raises(ValueError, match="request_hash"):
        replace(result, request_hash="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="transition prefix"):
        replace(result, transitions=(second, first))
    with pytest.raises(ValueError, match="final_state"):
        replace(result, final_state=first.after)
    with pytest.raises(ValueError, match="request_hash"):
        replace(outcome, request_hash="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="exactly one"):
        LinearPositionProjectionOutcome(
            projection_request.request_hash,
            result,
            LinearPositionProjector()
            .project(request(projection_request.fills[0], projection_request.fills[0]))
            .failure,
        )

    duplicate = LinearPositionProjector().project(
        request(projection_request.fills[0], projection_request.fills[0])
    )
    assert duplicate.failure is not None
    with pytest.raises(ValueError, match="first Request failure"):
        replace(
            duplicate.failure,
            code=LinearPositionProjectionFailureCode.NON_MONOTONIC_EXECUTION_TIME,
        )
    with pytest.raises(ValueError, match="request_hash"):
        replace(duplicate.failure, request_hash="sha256:" + "0" * 64)

    assert valid_contract.contract_hash == canonical_sha256(valid_contract)
    assert flat.state_hash == canonical_sha256(flat)
    assert result.projection_hash == canonical_sha256(result)
    assert outcome.outcome_hash == canonical_sha256(outcome)


def test_metadata_multiplier_scale_and_inputs_remain_exactly_bound() -> None:
    projector = LinearPositionProjector()
    first = fill(
        "1",
        side=OrderSide.BUY,
        quantity_units=1_000,
        price_units=10_000,
        execution_nanoseconds=1,
    )
    request_a = request(first)
    before = canonical_bytes(request_a)
    outcome_a = projector.project(request_a)
    assert canonical_bytes(request_a) == before
    assert outcome_a.result is not None

    reference = Price(
        9_950,
        PRICE_SCALE,
        str(INSTRUMENT_ID),
        str(QUOTE_CURRENCY),
    )
    metadata_fill = replace(
        first,
        reference_price=reference,
        slippage_decision_id="different-slippage-decision",
        liquidity="maker",
    )
    outcome_b = projector.project(request(metadata_fill))
    assert outcome_b.result is not None
    assert outcome_a.result.final_state == outcome_b.result.final_state
    assert outcome_a.result.request_hash != outcome_b.result.request_hash
    assert outcome_a.result.projection_hash != outcome_b.result.projection_hash
    assert (
        outcome_a.result.transitions[0].transition_hash
        != outcome_b.result.transitions[0].transition_hash
    )

    alternate_contract = replace(
        contract(),
        contract_multiplier=Rate(250, Scale(3), "base_quantity_per_contract"),
    )
    alternate_request = type(request())(
        position_key(), alternate_contract, ()
    )
    alternate = projector.project(alternate_request)
    empty = projector.project(request())
    assert alternate.result is not None
    assert empty.result is not None
    assert alternate.result.final_state.quantity == empty.result.final_state.quantity
    assert alternate.result.final_state.state_hash != empty.result.final_state.state_hash
    assert alternate.result.projection_hash != empty.result.projection_hash

    wrong_quantity_contract = replace(contract(), quantity_scale=Scale(2))
    quantity_failure = projector.project(
        type(request())(position_key(), wrong_quantity_contract, (first,))
    )
    assert quantity_failure.failure is not None
    assert (
        quantity_failure.failure.code
        is LinearPositionProjectionFailureCode.QUANTITY_SCALE_MISMATCH
    )

    wrong_price_contract = replace(contract(), price_scale=Scale(3))
    price_failure = projector.project(
        type(request())(position_key(), wrong_price_contract, (first,))
    )
    assert price_failure.failure is not None
    assert (
        price_failure.failure.code
        is LinearPositionProjectionFailureCode.PRICE_SCALE_MISMATCH
    )


def test_public_interface_and_canonical_preimages_are_frozen() -> None:
    expected_exports = {
        "LinearPositionTransitionKind",
        "LinearPerpetualContract",
        "ExactAverageEntryBasis",
        "LinearPositionState",
        "LinearPositionProjectionRequest",
        "LinearPositionTransition",
        "LinearPositionProjection",
        "LinearPositionProjectionFailureCode",
        "LinearPositionProjectionFailure",
        "LinearPositionProjectionOutcome",
        "LinearPositionProjector",
    }
    assert expected_exports <= set(crypto_quant_trading.__all__)
    transition_values = tuple(value.value for value in LinearPositionTransitionKind)
    failure_values = tuple(
        value.value for value in LinearPositionProjectionFailureCode
    )
    expected_transition_values = ("open", "add", "reduce", "close", "flip")
    expected_failure_values = (
        "position_context_mismatch",
        "duplicate_fill_id",
        "non_monotonic_execution_time",
        "fill_context_mismatch",
        "quantity_scale_mismatch",
        "price_context_mismatch",
        "price_scale_mismatch",
    )
    assert transition_values == expected_transition_values
    assert failure_values == expected_failure_values

    projection_request = request(
        fill(
            "1",
            side=OrderSide.BUY,
            quantity_units=1_000,
            price_units=10_000,
            execution_nanoseconds=1,
        )
    )
    outcome = LinearPositionProjector().project(projection_request)
    assert outcome.result is not None
    transition = outcome.result.transitions[0]
    basis = transition.after.average_entry_basis
    assert basis is not None
    values = (
        contract().to_canonical_dict(),
        basis.to_canonical_dict(),
        transition.before.to_canonical_dict(),
        projection_request.to_canonical_dict(),
        transition.to_canonical_dict(),
        outcome.result.to_canonical_dict(),
        outcome.to_canonical_dict(),
    )
    expected_types = (
        "linear_perpetual_contract",
        "exact_average_entry_basis",
        "linear_position_state",
        "linear_position_projection_request",
        "linear_position_transition",
        "linear_position_projection",
        "linear_position_projection_outcome",
    )
    assert tuple(value["type"] for value in values) == expected_types
    assert all(value["schema_version"] == 1 for value in values)
    assert contract().to_canonical_dict()["quantity_scale"] == 3
    assert contract().to_canonical_dict()["price_scale"] == 2

    duplicate = LinearPositionProjector().project(
        request(projection_request.fills[0], projection_request.fills[0])
    )
    assert duplicate.failure is not None
    failure_value = duplicate.failure.to_canonical_dict()
    assert failure_value["type"] == "linear_position_projection_failure"
    assert failure_value["schema_version"] == 1
