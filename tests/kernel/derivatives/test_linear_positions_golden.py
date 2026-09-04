from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Callable

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    Money,
    OrderSide,
    PositionBalanceKey,
    Price,
    Quantity,
    Rate,
    Scale,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    ExactAverageEntryBasis,
    LinearPositionProjectionFailureCode,
    LinearPositionProjector,
    LinearPositionTransitionKind,
)
from tests.kernel.derivatives._fixtures import (
    ACCOUNT_ID,
    INSTRUMENT_ID,
    PRICE_SCALE,
    QUOTE_CURRENCY,
    VENUE_ID,
    contract,
    fill,
    request,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/derivatives/linear-position-v1.json"


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot read canonical JSON: {path.name}") from error
    assert isinstance(value, dict)
    return value


def _error(call: Callable[[], object]) -> str:
    try:
        call()
    except (TypeError, ValueError) as error:
        return f"{type(error).__name__}: {error}"
    raise AssertionError("expected constructor rejection")


def build_actual() -> dict[str, object]:
    projector = LinearPositionProjector()
    long_fills = (
        fill("1", side=OrderSide.BUY, quantity_units=1_000, price_units=10_000, execution_nanoseconds=1),
        fill("2", side=OrderSide.BUY, quantity_units=2_000, price_units=10_050, execution_nanoseconds=2),
        fill("3", side=OrderSide.SELL, quantity_units=1_000, price_units=9_900, execution_nanoseconds=3),
        fill("4", side=OrderSide.SELL, quantity_units=2_000, price_units=9_900, execution_nanoseconds=4),
    )
    long_request = request(*long_fills)
    long_before = canonical_bytes(long_request)
    long_outcome = projector.project(long_request)
    assert long_outcome.result is not None
    long_projection = long_outcome.result
    assert canonical_bytes(long_request) == long_before

    short_request = request(
        fill("5", side=OrderSide.SELL, quantity_units=1_000, price_units=10_100, execution_nanoseconds=5),
        fill("6", side=OrderSide.SELL, quantity_units=1_000, price_units=10_200, execution_nanoseconds=6),
        fill("7", side=OrderSide.BUY, quantity_units=500, price_units=10_000, execution_nanoseconds=7),
        fill("8", side=OrderSide.BUY, quantity_units=2_000, price_units=9_900, execution_nanoseconds=8),
    )
    short_outcome = projector.project(short_request)
    assert short_outcome.result is not None

    equal_first = fill(
        "9",
        side=OrderSide.BUY,
        quantity_units=1_000,
        price_units=10_000,
        execution_nanoseconds=10,
    )
    equal_second = fill(
        "a",
        side=OrderSide.BUY,
        quantity_units=2_000,
        price_units=10_050,
        execution_nanoseconds=10,
    )
    equal_forward = projector.project(request(equal_first, equal_second))
    equal_reverse = projector.project(request(equal_second, equal_first))
    assert equal_forward.result is not None
    assert equal_reverse.result is not None
    assert equal_forward.result.final_state == equal_reverse.result.final_state

    cross_sell = fill(
        "b",
        side=OrderSide.SELL,
        quantity_units=2_000,
        price_units=9_900,
        execution_nanoseconds=11,
    )
    cross_buy = fill(
        "c",
        side=OrderSide.BUY,
        quantity_units=3_000,
        price_units=10_100,
        execution_nanoseconds=11,
    )
    cross_forward = projector.project(request(cross_sell, cross_buy))
    cross_reverse = projector.project(request(cross_buy, cross_sell))
    assert cross_forward.result is not None
    assert cross_reverse.result is not None
    assert cross_forward.result.final_state == cross_reverse.result.final_state
    long_to_short = projector.project(
        request(
            fill("d", side=OrderSide.BUY, quantity_units=1_000, price_units=10_000, execution_nanoseconds=12),
            fill("e", side=OrderSide.SELL, quantity_units=2_000, price_units=9_800, execution_nanoseconds=13),
        )
    )
    short_close = projector.project(
        request(
            fill("e", side=OrderSide.SELL, quantity_units=1_000, price_units=9_800, execution_nanoseconds=14),
            fill("f", side=OrderSide.BUY, quantity_units=1_000, price_units=9_900, execution_nanoseconds=15),
        )
    )
    assert long_to_short.result is not None
    assert short_close.result is not None
    assert long_to_short.result.transitions[-1].kind is LinearPositionTransitionKind.FLIP
    assert short_close.result.transitions[-1].kind is LinearPositionTransitionKind.CLOSE

    valid = equal_first
    duplicate = projector.project(
        request(
            valid,
            replace(
                valid,
                execution_time=type(valid.execution_time)(9),
            ),
        )
    )
    regression = projector.project(
        request(
            valid,
            fill(
                "f",
                side=OrderSide.BUY,
                quantity_units=1_000,
                price_units=10_000,
                execution_nanoseconds=9,
            ),
        )
    )
    account_mismatch = projector.project(request(replace(valid, account_id="other-account")))
    quantity_scale = projector.project(
        request(
            replace(
                valid,
                quantity=Quantity(100, Scale(2), str(INSTRUMENT_ID)),
            )
        )
    )
    usd = CurrencyId("USD")
    usd_price = Price(
        valid.price.units,
        PRICE_SCALE,
        str(INSTRUMENT_ID),
        str(usd),
    )
    price_context = projector.project(
        request(
            replace(
                valid,
                reference_price=usd_price,
                price=usd_price,
                slippage_amount=Money(0, PRICE_SCALE, str(usd)),
            )
        )
    )
    scale_three_price = Price(
        valid.price.units * 10,
        Scale(3),
        str(INSTRUMENT_ID),
        str(QUOTE_CURRENCY),
    )
    price_scale = projector.project(
        request(
            replace(
                valid,
                reference_price=scale_three_price,
                price=scale_three_price,
            )
        )
    )
    other_instrument = InstrumentId(VENUE_ID, "other-linear-perpetual")
    mismatch_request = type(request())(
        PositionBalanceKey(ACCOUNT_ID, VENUE_ID, other_instrument),
        contract(),
        (valid,),
    )
    position_context = projector.project(mismatch_request)

    regression_and_context = projector.project(
        request(
            valid,
            replace(
                fill(
                    "f",
                    side=OrderSide.BUY,
                    quantity_units=1_000,
                    price_units=10_000,
                    execution_nanoseconds=9,
                ),
                account_id="other-account",
            ),
        )
    )
    context_and_quantity = projector.project(
        request(
            replace(
                valid,
                account_id="other-account",
                quantity=Quantity(100, Scale(2), str(INSTRUMENT_ID)),
            )
        )
    )
    quantity_and_price = projector.project(
        request(
            replace(
                valid,
                quantity=Quantity(100, Scale(2), str(INSTRUMENT_ID)),
                reference_price=usd_price,
                price=usd_price,
                slippage_amount=Money(0, PRICE_SCALE, str(usd)),
            )
        )
    )
    usd_scale_three_price = Price(
        valid.price.units * 10,
        Scale(3),
        str(INSTRUMENT_ID),
        str(usd),
    )
    price_context_and_scale = projector.project(
        request(
            replace(
                valid,
                reference_price=usd_scale_three_price,
                price=usd_scale_three_price,
                slippage_amount=Money(0, PRICE_SCALE, str(usd)),
            )
        )
    )
    position_and_duplicate = projector.project(
        type(request())(
            PositionBalanceKey(ACCOUNT_ID, VENUE_ID, other_instrument),
            contract(),
            (valid, valid),
        )
    )

    failures = (
        position_context,
        duplicate,
        regression,
        account_mismatch,
        quantity_scale,
        price_context,
        price_scale,
        regression_and_context,
        context_and_quantity,
        quantity_and_price,
        price_context_and_scale,
        position_and_duplicate,
    )
    assert all(value.result is None and value.failure is not None for value in failures)
    actual_failure_codes = tuple(
        value.failure.code for value in failures if value.failure is not None
    )
    expected_failure_codes = (
        LinearPositionProjectionFailureCode.POSITION_CONTEXT_MISMATCH,
        LinearPositionProjectionFailureCode.DUPLICATE_FILL_ID,
        LinearPositionProjectionFailureCode.NON_MONOTONIC_EXECUTION_TIME,
        LinearPositionProjectionFailureCode.FILL_CONTEXT_MISMATCH,
        LinearPositionProjectionFailureCode.QUANTITY_SCALE_MISMATCH,
        LinearPositionProjectionFailureCode.PRICE_CONTEXT_MISMATCH,
        LinearPositionProjectionFailureCode.PRICE_SCALE_MISMATCH,
        LinearPositionProjectionFailureCode.NON_MONOTONIC_EXECUTION_TIME,
        LinearPositionProjectionFailureCode.FILL_CONTEXT_MISMATCH,
        LinearPositionProjectionFailureCode.QUANTITY_SCALE_MISMATCH,
        LinearPositionProjectionFailureCode.PRICE_CONTEXT_MISMATCH,
        LinearPositionProjectionFailureCode.POSITION_CONTEXT_MISMATCH,
    )
    assert actual_failure_codes == expected_failure_codes

    empty = projector.project(request())
    assert empty.result is not None
    prefix = projector.project(request(*long_fills[:2]))
    assert prefix.result is not None
    assert prefix.result.transitions == long_outcome.result.transitions[:2]

    alternate_contract = replace(
        contract(),
        contract_multiplier=Rate(250, Scale(3), "base_quantity_per_contract"),
    )
    alternate_multiplier = projector.project(
        type(request())(request().position_key, alternate_contract, ())
    )
    quantity_scale_contract = replace(contract(), quantity_scale=Scale(2))
    quantity_scale_mutation = projector.project(
        type(request())(request().position_key, quantity_scale_contract, (valid,))
    )
    price_scale_contract = replace(contract(), price_scale=Scale(3))
    price_scale_mutation = projector.project(
        type(request())(request().position_key, price_scale_contract, (valid,))
    )
    assert alternate_multiplier.result is not None
    assert quantity_scale_mutation.failure is not None
    assert price_scale_mutation.failure is not None

    first_transition = long_outcome.result.transitions[0]
    duplicate_failure = duplicate.failure
    assert duplicate_failure is not None
    constructor_rejections = {
        "unreduced_basis": _error(
            lambda: ExactAverageEntryBasis(
                INSTRUMENT_ID, QUOTE_CURRENCY, 200, 2
            )
        ),
        "forged_transition": _error(
            lambda: replace(
                first_transition,
                kind=LinearPositionTransitionKind.CLOSE,
            )
        ),
        "forged_projection": _error(
            lambda: replace(
                long_projection,
                final_state=first_transition.after,
            )
        ),
        "forged_failure": _error(
            lambda: replace(
                duplicate_failure,
                code=LinearPositionProjectionFailureCode.NON_MONOTONIC_EXECUTION_TIME,
            )
        ),
    }

    payload = {
        "fixture_id": "synthetic-linear-position-v1",
        "transition_enum": [value.value for value in LinearPositionTransitionKind],
        "failure_enum": [value.value for value in LinearPositionProjectionFailureCode],
        "contract": contract(),
        "contract_hash": contract().contract_hash,
        "long_projection": long_outcome,
        "short_projection": short_outcome,
        "empty_projection": empty,
        "prefix_projection": prefix,
        "equal_time": {
            "forward": equal_forward,
            "reverse": equal_reverse,
            "same_final_state_hash": equal_forward.result.final_state.state_hash,
        },
        "cross_zero": {
            "sell_then_buy": cross_forward,
            "buy_then_sell": cross_reverse,
            "long_to_short_flip": long_to_short,
            "short_close": short_close,
            "same_final_state_hash": cross_forward.result.final_state.state_hash,
        },
        "failures": [value.failure for value in failures],
        "mutations": {
            "alternate_multiplier": alternate_multiplier,
            "quantity_scale": quantity_scale_mutation,
            "price_scale": price_scale_mutation,
        },
        "constructor_rejections": constructor_rejections,
        "canonical": {
            "request_bytes": canonical_bytes(long_request).decode("utf-8"),
            "request_hash": canonical_sha256(long_request),
            "projection_hash": long_outcome.result.projection_hash,
            "outcome_hash": long_outcome.outcome_hash,
            "basis_hashes": [
                transition.after.average_entry_basis.basis_hash
                for transition in long_outcome.result.transitions
                if transition.after.average_entry_basis is not None
            ],
            "transition_hashes": [
                transition.transition_hash
                for transition in long_outcome.result.transitions
            ],
            "failure_hashes": [
                value.failure.failure_hash
                for value in failures
                if value.failure is not None
            ],
        },
        "no_mutation": {
            "request_before": long_before.decode("utf-8"),
            "request_after": canonical_bytes(long_request).decode("utf-8"),
            "contract_before": canonical_sha256(contract()),
            "contract_after": canonical_sha256(contract()),
        },
    }
    try:
        decoded = json.loads(canonical_bytes(payload))
    except (TypeError, ValueError) as error:
        raise AssertionError("G09A golden payload must be canonical JSON") from error
    assert isinstance(decoded, dict)
    return decoded


def test_linear_position_projection_matches_static_golden() -> None:
    assert build_actual() == _read_json(FIXTURE)
