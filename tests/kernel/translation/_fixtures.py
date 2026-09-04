from __future__ import annotations

from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    Order,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
)
from crypto_quant_trading import (
    OrderCapabilityApproval,
    OrderCapabilityValidator,
    OrderTranslationFieldRule,
    OrderTranslationMapping,
)
from tests.kernel.capabilities._fixtures import capability_set, intent


CANONICAL_FIELDS = (
    "instrument_id",
    "side",
    "quantity",
    "execution_style",
    "price_constraint",
    "time_in_force",
    "reduce_only",
    "position_effect",
    "urgency",
    "reason",
    "parent_id",
)
TARGET_FIELDS = (
    "instrument",
    "direction",
    "amount",
    "order_style",
    "price_terms",
    "tif",
    "reduce_only",
    "position_effect",
    "urgency",
    "reason",
    "parent_reference",
)


def simulation_instant(nanoseconds: int) -> SimulationInstant:
    return SimulationInstant(
        UtcInstant(nanoseconds),
        TimelinePhase(65, "translation"),
        SourceSequence(1),
    )


def order() -> Order:
    return Order(
        order_id=DomainId(DomainIdKind.ORDER, f"ord_{'6' * 64}"),
        account_id="account:primary",
        intent=intent(),
        created_at=simulation_instant(100),
    )


def approval(subject: Order | None = None) -> OrderCapabilityApproval:
    subject = order() if subject is None else subject
    decision = OrderCapabilityValidator().validate(subject.intent, capability_set())
    assert decision.approval is not None
    return decision.approval


def field_rules(*, reverse: bool = False) -> tuple[OrderTranslationFieldRule, ...]:
    rules = tuple(
        OrderTranslationFieldRule(canonical_field, target_field)
        for canonical_field, target_field in zip(
            CANONICAL_FIELDS, TARGET_FIELDS, strict=True
        )
    )
    return tuple(reversed(rules)) if reverse else rules


def mapping(
    *,
    rules: tuple[OrderTranslationFieldRule, ...] | None = None,
) -> OrderTranslationMapping:
    return OrderTranslationMapping.create(
        translator_key="synthetic.cash.order-translator.v1",
        translator_version=1,
        target_profile_id="synthetic.cash.development.v1",
        field_rules=field_rules() if rules is None else rules,
    )
