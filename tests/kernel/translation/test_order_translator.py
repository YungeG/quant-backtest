from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_domain import Order, TranslationStatus, UtcInstant, canonical_sha256
from crypto_quant_trading import (
    OrderCapabilityValidator,
    OrderTranslationEvidenceError,
    OrderTranslationFieldRule,
    OrderTranslationMapping,
    OrderTranslator,
)
from tests.kernel.capabilities._fixtures import capability_set, intent

from ._fixtures import CANONICAL_FIELDS, approval, field_rules, mapping, order


def test_translates_every_canonical_field_without_mutating_intent() -> None:
    subject = order()
    source_hash = canonical_sha256(subject.intent)

    result = OrderTranslator().translate(
        subject,
        approval(subject),
        mapping(),
        UtcInstant(110),
    )

    assert result.executable_spec is not None
    assert result.report.status is TranslationStatus.TRANSLATED
    assert result.report.unsupported_capabilities == ()
    expected_fields = tuple(sorted(CANONICAL_FIELDS))
    actual_fields = tuple(
        value.canonical_field for value in result.report.field_mappings
    )
    assert actual_fields == expected_fields
    assert result.executable_spec.source_order == subject
    assert result.executable_spec.intent is subject.intent
    assert result.executable_spec.intent.execution_style is subject.intent.execution_style
    assert result.executable_spec.intent.time_in_force is subject.intent.time_in_force
    assert result.executable_spec.intent.reduce_only is subject.intent.reduce_only
    assert result.executable_spec.intent.position_effect is subject.intent.position_effect
    assert canonical_sha256(subject.intent) == source_hash


def test_mapping_input_order_does_not_change_translation_identity() -> None:
    subject = order()
    first = OrderTranslator().translate(
        subject, approval(subject), mapping(), UtcInstant(110)
    )
    second = OrderTranslator().translate(
        subject,
        approval(subject),
        mapping(rules=field_rules(reverse=True)),
        UtcInstant(110),
    )

    assert first == second
    assert first.result_hash == second.result_hash
    assert first.executable_spec is not None
    assert second.executable_spec is not None
    assert first.executable_spec.spec_id == second.executable_spec.spec_id
    assert first.report.report_id == second.report.report_id


def test_missing_field_mapping_rejects_without_partial_executable_spec() -> None:
    subject = order()
    incomplete = mapping(rules=field_rules()[:-1])

    result = OrderTranslator().translate(
        subject, approval(subject), incomplete, UtcInstant(110)
    )

    assert result.executable_spec is None
    assert result.report.status is TranslationStatus.REJECTED
    assert result.source_order == subject
    assert result.capability_approval == approval(subject)
    assert result.translation_mapping == incomplete
    assert result.source_intent_hash == canonical_sha256(subject.intent)
    assert result.capability_decision_hash == canonical_sha256(approval(subject))
    assert result.translation_mapping_hash == incomplete.mapping_hash
    actual_unsupported = [
        (value.capability, value.reason_code)
        for value in result.report.unsupported_capabilities
    ]
    expected_unsupported = [("translation.parent_id", "missing_field_mapping")]
    assert actual_unsupported == expected_unsupported
    assert len(result.report.field_mappings) == len(CANONICAL_FIELDS) - 1


def test_unknown_field_mapping_rejects_with_structured_evidence() -> None:
    subject = order()
    rules = field_rules() + (
        OrderTranslationFieldRule("venue_extension", "vendor_extension"),
    )

    result = OrderTranslator().translate(
        subject, approval(subject), mapping(rules=rules), UtcInstant(110)
    )

    assert result.executable_spec is None
    assert result.report.status is TranslationStatus.REJECTED
    actual_unsupported = [
        (value.capability, value.requested_value, value.reason_code)
        for value in result.report.unsupported_capabilities
    ]
    expected_unsupported = [
        (
            "translation.venue_extension",
            "vendor_extension",
            "unknown_field_mapping",
        )
    ]
    assert actual_unsupported == expected_unsupported
    assert len(result.report.field_mappings) == len(CANONICAL_FIELDS)


def test_mapping_rejects_duplicate_fields_and_forged_config_hash() -> None:
    duplicate_canonical = field_rules() + (
        OrderTranslationFieldRule("side", "other_direction"),
    )
    with pytest.raises(ValueError, match="duplicate canonical field"):
        mapping(rules=duplicate_canonical)

    rules = field_rules()
    duplicate_target = rules[:-1] + (
        OrderTranslationFieldRule("parent_id", rules[0].target_field),
    )
    with pytest.raises(ValueError, match="duplicate target field"):
        mapping(rules=duplicate_target)

    valid = mapping()
    with pytest.raises(ValueError, match="config_hash"):
        replace(valid, config_hash="sha256:" + "0" * 64)


def test_rejects_capability_approval_for_a_different_intent() -> None:
    subject = order()
    other_intent = replace(intent(), reason="different reason")
    decision = OrderCapabilityValidator().validate(other_intent, capability_set())
    assert decision.approval is not None

    with pytest.raises(OrderTranslationEvidenceError, match="source intent"):
        OrderTranslator().translate(
            subject,
            decision.approval,
            mapping(),
            UtcInstant(110),
        )


def test_rejects_translation_before_order_creation() -> None:
    subject = order()
    with pytest.raises(OrderTranslationEvidenceError, match="before Order creation"):
        OrderTranslator().translate(
            subject,
            approval(subject),
            mapping(),
            UtcInstant(99),
        )


def test_requires_typed_inputs() -> None:
    translator = OrderTranslator()
    subject = order()
    approved = approval(subject)
    configuration = mapping()

    with pytest.raises(TypeError, match="order must be Order"):
        translator.translate(object(), approved, configuration, UtcInstant(110))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="approval must be OrderCapabilityApproval"):
        translator.translate(subject, object(), configuration, UtcInstant(110))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="mapping must be OrderTranslationMapping"):
        translator.translate(subject, approved, object(), UtcInstant(110))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="translation_time must be UtcInstant"):
        translator.translate(subject, approved, configuration, object())  # type: ignore[arg-type]

    translated = translator.translate(
        subject, approved, configuration, UtcInstant(110)
    )
    assert translated.executable_spec is not None
    with pytest.raises(TypeError, match="source_order must be Order"):
        replace(translated.executable_spec, source_order=object())  # type: ignore[arg-type]
