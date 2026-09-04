from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    Money,
    PricePurpose,
    Quantity,
    RoundingPolicy,
    Scale,
    UtcInstant,
    VenueId,
)
from crypto_quant_trading import (
    InstrumentSizingInput,
    PositionSizer,
    PositionSizingAction,
    PositionSizingDecision,
    PositionSizingFailureCode,
    PositionSizingPolicy,
    QuantityLattice,
    ResidualPositionPolicy,
)

from ._fixtures import (
    BATCH_ID,
    BTC,
    ETH,
    QUANTITY_SCALE,
    approved_targets,
    expected_lattice_hash,
    expected_policy_hash,
    lattice,
    resolved_mark,
    sizing_inputs,
    sizing_policy,
    zero_approved_target,
)


def decisions_by_instrument(
    outcome: object,
) -> dict[InstrumentId, PositionSizingDecision]:
    normalized = getattr(outcome, "normalized_target")
    assert normalized is not None
    return {
        value.instrument_id: value.decision for value in normalized.targets
    }


def test_materializes_toward_zero_quantities_with_complete_provenance() -> None:
    approved = approved_targets()
    outcome = PositionSizer().materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(),
        inputs=sizing_inputs(),
    )

    assert outcome.failure is None
    assert outcome.normalized_target is not None
    normalized = outcome.normalized_target
    assert normalized.active_target.source_decision_batch_id == BATCH_ID
    assert normalized.active_target.materialized_at == approved.approved_at
    quantities = dict(normalized.active_target.quantities)
    assert quantities[BTC] == Quantity(10_300, QUANTITY_SCALE, str(BTC))
    assert quantities[ETH] == Quantity(-15_000, QUANTITY_SCALE, str(ETH))

    decisions = decisions_by_instrument(outcome)
    btc = decisions[BTC]
    assert btc.raw_quantity.units == 10_344
    assert btc.final_quantity.units == 10_300
    assert btc.residual_quantity.units == 44
    assert PositionSizingAction.ROUNDED_TOWARD_ZERO in btc.actions
    assert btc.mark_id == sizing_inputs()[0].mark.mark_id
    assert btc.lattice_hash == sizing_inputs()[0].lattice.lattice_hash
    assert normalized.source_approved_target_hash == approved.approved_target_hash


def test_minimum_quantity_and_notional_zero_the_target_with_decisions() -> None:
    approved = approved_targets()
    inputs = list(sizing_inputs())
    inputs[0] = replace(
        inputs[0],
        lattice=lattice(
            BTC,
            min_quantity_units=20_000,
            min_notional_units=40_000_000_000_000_000,
        ),
    )

    outcome = PositionSizer().materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(),
        inputs=tuple(inputs),
    )

    assert outcome.normalized_target is not None
    decision = decisions_by_instrument(outcome)[BTC]
    assert decision.final_quantity.units == 0
    assert PositionSizingAction.BELOW_MINIMUM_QUANTITY in decision.actions
    assert PositionSizingAction.BELOW_MINIMUM_NOTIONAL in decision.actions


def test_odd_lot_full_close_uses_explicit_capability_and_residual_policy() -> None:
    approved = zero_approved_target()
    odd_current = Quantity(1_050, QUANTITY_SCALE, str(BTC))
    base = InstrumentSizingInput(
        instrument_id=BTC,
        mark=resolved_mark(BTC, price_units=2_900),
        current_quantity=odd_current,
        lattice=lattice(BTC, odd_lot_close_permitted=False),
    )
    other = InstrumentSizingInput(
        instrument_id=ETH,
        mark=resolved_mark(ETH, price_units=2_000),
        current_quantity=Quantity(0, QUANTITY_SCALE, str(ETH)),
        lattice=lattice(ETH),
    )

    held = PositionSizer().materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(residual=ResidualPositionPolicy.HOLD_DUST),
        inputs=(base, other),
    )
    close_when_not_permitted = PositionSizer().materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(residual=ResidualPositionPolicy.CLOSE_IF_PERMITTED),
        inputs=(base, other),
    )
    failed = PositionSizer().materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(residual=ResidualPositionPolicy.FAIL),
        inputs=(base, other),
    )
    closed = PositionSizer().materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(residual=ResidualPositionPolicy.CLOSE_IF_PERMITTED),
        inputs=(replace(base, lattice=lattice(BTC, odd_lot_close_permitted=True)), other),
    )

    assert held.normalized_target is not None
    held_decision = decisions_by_instrument(held)[BTC]
    assert held_decision.final_quantity == odd_current
    assert held_decision.applied_lot_units == 100
    assert PositionSizingAction.RESIDUAL_HELD in held_decision.actions

    assert close_when_not_permitted.normalized_target is not None
    assert decisions_by_instrument(close_when_not_permitted)[BTC].final_quantity == odd_current

    assert failed.normalized_target is None
    assert failed.failure is not None
    assert failed.failure.code is PositionSizingFailureCode.RESIDUAL_NOT_PERMITTED

    assert closed.normalized_target is not None
    closed_decision = decisions_by_instrument(closed)[BTC]
    assert closed_decision.final_quantity.units == 0
    assert PositionSizingAction.ODD_LOT_CLOSE in closed_decision.actions


def test_residual_fail_is_atomic_for_target_quantization() -> None:
    outcome = PositionSizer().materialize(
        approved_target=approved_targets(),
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(residual=ResidualPositionPolicy.FAIL),
        inputs=sizing_inputs(),
    )

    assert outcome.normalized_target is None
    assert outcome.failure is not None
    assert outcome.failure.code is PositionSizingFailureCode.RESIDUAL_NOT_PERMITTED


def test_input_and_lattice_order_do_not_change_materialization_identity() -> None:
    approved = approved_targets()
    sizer = PositionSizer()
    first = sizer.materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(),
        inputs=sizing_inputs(),
    )
    reordered = sizer.materialize(
        approved_target=replace(approved, targets=tuple(reversed(approved.targets))),
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(),
        inputs=sizing_inputs(reverse=True),
    )

    assert first.normalized_target is not None
    assert reordered.normalized_target is not None
    assert first.normalized_target == reordered.normalized_target
    assert first.normalized_target.normalized_target_hash == reordered.normalized_target.normalized_target_hash


def test_missing_duplicate_unexpected_and_context_inputs_fail_without_partial_target() -> None:
    approved = approved_targets()
    values = sizing_inputs()
    missing = PositionSizer().materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(),
        inputs=values[:1],
    )
    duplicate = PositionSizer().materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(),
        inputs=(*values, values[0]),
    )
    extra = InstrumentId(VenueId("synthetic"), "cash:extra-usd")
    unexpected_input = InstrumentSizingInput(
        instrument_id=extra,
        mark=resolved_mark(extra, price_units=100),
        current_quantity=Quantity(0, QUANTITY_SCALE, str(extra)),
        lattice=lattice(extra),
    )
    unexpected = PositionSizer().materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(),
        inputs=(*values, unexpected_input),
    )
    wrong_time = PositionSizer().materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(),
        inputs=(
            replace(
                values[0],
                mark=resolved_mark(BTC, price_units=2_900, resolved_at=UtcInstant(101)),
            ),
            values[1],
        ),
    )

    assert missing.normalized_target is None
    assert missing.failure is not None
    assert missing.failure.code is PositionSizingFailureCode.MISSING_INPUT
    assert duplicate.failure is not None
    assert duplicate.failure.code is PositionSizingFailureCode.DUPLICATE_INPUT
    assert unexpected.failure is not None
    assert unexpected.failure.code is PositionSizingFailureCode.UNEXPECTED_INPUT
    assert wrong_time.failure is not None
    assert wrong_time.failure.code is PositionSizingFailureCode.MARK_TIME_MISMATCH


def test_missing_policy_wrong_purpose_and_implicit_fx_fail_closed() -> None:
    approved = approved_targets()
    values = sizing_inputs()
    missing = PositionSizer().materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=None,
        inputs=values,
    )
    wrong_purpose = PositionSizer().materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(price_purpose=PricePurpose.MARGIN),
        inputs=values,
    )
    eur = CurrencyId("EUR")
    invalid_price = PositionSizer().materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(),
        inputs=(
            replace(values[0], mark=resolved_mark(BTC, price_units=0)),
            values[1],
        ),
    )
    implicit_fx = PositionSizer().materialize(
        approved_target=approved,
        source_decision_batch_id=BATCH_ID,
        policy=sizing_policy(),
        inputs=(
            replace(
                values[0],
                mark=resolved_mark(BTC, price_units=2_900, currency=eur),
                lattice=lattice(BTC, currency=eur),
            ),
            values[1],
        ),
    )

    assert missing.failure is not None
    assert missing.failure.code is PositionSizingFailureCode.MISSING_POLICY
    assert wrong_purpose.failure is not None
    assert wrong_purpose.failure.code is PositionSizingFailureCode.PRICE_PURPOSE_MISMATCH
    assert invalid_price.failure is not None
    assert invalid_price.failure.code is PositionSizingFailureCode.INVALID_SIZING_PRICE
    assert implicit_fx.failure is not None
    assert implicit_fx.failure.code is PositionSizingFailureCode.CURRENCY_MISMATCH


def test_policy_and_lattice_definitions_verify_hashes_and_toward_zero_only() -> None:
    policy = sizing_policy()
    btc_lattice = lattice(BTC)
    assert policy.config_hash == expected_policy_hash(policy)
    assert btc_lattice.config_hash == expected_lattice_hash(btc_lattice)

    with pytest.raises(ValueError, match="config_hash"):
        replace(policy, config_hash="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="config_hash"):
        replace(btc_lattice, config_hash="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="toward_zero"):
        PositionSizingPolicy.create(
            policy_key="invalid.rounding.v1",
            policy_version=1,
            price_purpose=PricePurpose.VALUATION,
            rounding=RoundingPolicy.HALF_EVEN,
            residual_policy=ResidualPositionPolicy.HOLD_DUST,
        )
    with pytest.raises(ValueError, match="multiple"):
        QuantityLattice.create(
            instrument_id=BTC,
            lattice_key="invalid.lattice.v1",
            lattice_version=1,
            atomic_scale=Scale(3),
            step_units=10,
            buy_lot_units=15,
            sell_lot_units=100,
            min_quantity_units=100,
            min_notional=Money(100, Scale(2), "USD"),
            odd_lot_close_permitted=False,
        )
