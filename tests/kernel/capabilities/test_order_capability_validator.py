from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import (
    ExecutionStyle,
    PositionEffect,
    TimeInForce,
    UnsupportedCapability,
    canonical_sha256,
)
from crypto_quant_trading import (
    CapabilityRejection,
    OrderCapabilityApproval,
    OrderCapabilityDecision,
    OrderCapabilityKey,
    OrderCapabilitySet,
    OrderCapabilityValidator,
    OrderStyleCapability,
    PriceConstraintShape,
)

from ._fixtures import (
    capability_set,
    intent,
    limit_constraint,
    stop_limit_constraint,
    style_capabilities,
    trigger_constraint,
)


def rejection_reasons(decision: OrderCapabilityDecision) -> set[str]:
    assert decision.rejection is not None
    return {item.reason_code for item in decision.rejection.unsupported_capabilities}


def test_supported_intent_is_approved_without_modification() -> None:
    source = intent()
    capabilities = capability_set()

    decision = OrderCapabilityValidator().validate(source, capabilities)

    assert isinstance(decision.approval, OrderCapabilityApproval)
    assert decision.rejection is None
    assert decision.approval.source_intent is source
    assert decision.approval.capability_set is capabilities
    assert decision.approval.intent_hash == canonical_sha256(source)
    assert decision.approval.capability_set_hash == canonical_sha256(capabilities)
    assert decision.decision_id.startswith("order-capability-decision-v1:sha256:")


def test_exact_price_constraint_shapes_are_style_specific() -> None:
    validator = OrderCapabilityValidator()
    capabilities = capability_set()

    cases = (
        intent(),
        intent(style=ExecutionStyle.LIMIT, constraint=limit_constraint()),
        intent(style=ExecutionStyle.STOP, constraint=trigger_constraint()),
        intent(
            style=ExecutionStyle.STOP_LIMIT,
            constraint=stop_limit_constraint(),
        ),
    )
    assert all(validator.validate(value, capabilities).approval for value in cases)

    wrong_shape = validator.validate(
        intent(style=ExecutionStyle.LIMIT, constraint=trigger_constraint()),
        capabilities,
    )
    assert rejection_reasons(wrong_shape) == {"unsupported_price_constraint"}


def test_style_specific_tif_reduce_only_and_position_effect_reject_structurally() -> None:
    limited = capability_set(
        styles=(
            OrderStyleCapability(
                ExecutionStyle.LIMIT,
                (PriceConstraintShape.LIMIT,),
                (TimeInForce.DAY,),
            ),
        ),
        supports_reduce_only=False,
        position_effects=(PositionEffect.AUTO,),
    )
    source = intent(
        style=ExecutionStyle.LIMIT,
        constraint=limit_constraint(),
        tif=TimeInForce.GTC,
        reduce_only=True,
        position_effect=PositionEffect.CLOSE,
    )

    decision = OrderCapabilityValidator().validate(source, limited)

    assert isinstance(decision.rejection, CapabilityRejection)
    assert decision.approval is None
    assert rejection_reasons(decision) == {
        "unsupported_time_in_force",
        "unsupported_reduce_only",
        "unsupported_position_effect",
    }
    assert decision.rejection.source_intent is source
    assert decision.rejection.capability_set is limited


def test_unsupported_execution_style_does_not_silently_downgrade() -> None:
    market_only = capability_set(styles=(style_capabilities()[0],))
    source = intent(style=ExecutionStyle.LIMIT, constraint=limit_constraint())

    decision = OrderCapabilityValidator().validate(source, market_only)

    assert decision.approval is None
    assert rejection_reasons(decision) == {"unsupported_execution_style"}
    assert decision.rejection is not None
    assert decision.rejection.source_intent.execution_style is ExecutionStyle.LIMIT
    assert decision.rejection.source_intent.price_constraint == limit_constraint()


def test_missing_and_unknown_declared_capability_keys_fail_closed() -> None:
    declared = tuple(
        key.value
        for key in OrderCapabilityKey
        if key is not OrderCapabilityKey.REDUCE_ONLY
    ) + ("iceberg",)
    capabilities = capability_set(declared_keys=declared)

    decision = OrderCapabilityValidator().validate(intent(), capabilities)

    assert decision.rejection is not None
    details = {
        (item.capability, item.requested_value, item.reason_code)
        for item in decision.rejection.unsupported_capabilities
    }
    missing_reduce_only = (
        "reduce_only",
        "false",
        "missing_capability_declaration",
    )
    unknown_iceberg = ("iceberg", "declared", "unknown_capability")
    assert missing_reduce_only in details
    assert unknown_iceberg in details


def test_capability_set_and_decision_identity_ignore_set_like_input_order() -> None:
    first = capability_set()
    second = capability_set(
        styles=tuple(
            replace(
                value,
                price_constraint_shapes=tuple(reversed(value.price_constraint_shapes)),
                time_in_forces=tuple(reversed(value.time_in_forces)),
            )
            for value in reversed(style_capabilities())
        ),
        position_effects=(
            PositionEffect.CLOSE,
            PositionEffect.OPEN,
            PositionEffect.AUTO,
        ),
        declared_keys=tuple(reversed(tuple(key.value for key in OrderCapabilityKey))),
    )

    assert first == second
    first_decision = OrderCapabilityValidator().validate(intent(), first)
    second_decision = OrderCapabilityValidator().validate(intent(), second)
    assert first_decision == second_decision
    assert first_decision.decision_hash == second_decision.decision_hash


def test_duplicate_style_and_forged_config_hash_fail_at_contract_boundary() -> None:
    market = style_capabilities()[0]
    with pytest.raises(ValueError, match="duplicate execution style"):
        capability_set(styles=(market, market))

    valid = capability_set()
    with pytest.raises(ValueError, match="config_hash"):
        replace(valid, config_hash="sha256:" + "0" * 64)


def test_contracts_reject_noncanonical_or_duplicate_capability_values() -> None:
    with pytest.raises(ValueError, match="duplicate PriceConstraintShape"):
        OrderStyleCapability(
            ExecutionStyle.MARKET,
            (PriceConstraintShape.NONE, PriceConstraintShape.NONE),
            (TimeInForce.DAY,),
        )
    with pytest.raises(ValueError, match="duplicate TimeInForce"):
        OrderStyleCapability(
            ExecutionStyle.MARKET,
            (PriceConstraintShape.NONE,),
            (TimeInForce.DAY, TimeInForce.DAY),
        )
    with pytest.raises(ValueError, match="duplicate declared capability"):
        capability_set(declared_keys=("execution_style", "execution_style"))
    with pytest.raises(ValueError, match="canonical"):
        capability_set(declared_keys=(" iceberg ",))
    with pytest.raises(TypeError, match="OrderIntent"):
        OrderCapabilityValidator().validate(object(), capability_set())  # type: ignore[arg-type]


def test_rejection_evidence_is_canonical_sorted_and_duplicate_free() -> None:
    limited = capability_set(
        styles=(
            OrderStyleCapability(
                ExecutionStyle.LIMIT,
                (PriceConstraintShape.NONE,),
                (TimeInForce.DAY,),
            ),
        ),
        supports_reduce_only=False,
        position_effects=(PositionEffect.AUTO,),
    )
    decision = OrderCapabilityValidator().validate(
        intent(
            style=ExecutionStyle.LIMIT,
            constraint=limit_constraint(),
            tif=TimeInForce.GTC,
            reduce_only=True,
            position_effect=PositionEffect.CLOSE,
        ),
        limited,
    )
    assert decision.rejection is not None
    assert all(
        isinstance(item, UnsupportedCapability)
        for item in decision.rejection.unsupported_capabilities
    )
    keys = [
        (item.capability, item.requested_value, item.reason_code)
        for item in decision.rejection.unsupported_capabilities
    ]
    assert keys == sorted(keys)
    assert len(keys) == len(set(keys))
