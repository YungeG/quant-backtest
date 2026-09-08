from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Self

from crypto_quant_domain import (
    Order,
    OrderIntent,
    OrderTranslationReport,
    TranslationFieldMapping,
    TranslationStatus,
    UnsupportedCapability,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)

from .capabilities import OrderCapabilityApproval


_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_INTENT_FIELDS = (
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
_INTENT_FIELD_SET = frozenset(_INTENT_FIELDS)


class OrderTranslationError(ValueError):
    """Base error for invalid Order Translation evidence."""


class OrderTranslationEvidenceError(OrderTranslationError):
    """Raised when trusted translation inputs do not describe one Order."""


def _canonical_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value or value.strip() != value:
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 digest")


def _intent_values(intent: OrderIntent) -> dict[str, Any]:
    return {
        "instrument_id": intent.instrument_id,
        "side": intent.side.value,
        "quantity": intent.quantity,
        "execution_style": intent.execution_style.value,
        "price_constraint": intent.price_constraint,
        "time_in_force": intent.time_in_force.value,
        "reduce_only": intent.reduce_only,
        "position_effect": intent.position_effect.value,
        "urgency": intent.urgency,
        "reason": intent.reason,
        "parent_id": intent.parent_id,
    }


def _canonical_value(value: Any) -> str:
    return canonical_bytes(value).decode("utf-8")


@dataclass(frozen=True, slots=True)
class OrderTranslationFieldRule:
    canonical_field: str
    target_field: str

    def __post_init__(self) -> None:
        _canonical_text("canonical_field", self.canonical_field)
        _canonical_text("target_field", self.target_field)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_translation_field_rule",
            "canonical_field": self.canonical_field,
            "target_field": self.target_field,
        }


def _mapping_config_payload(
    *,
    translator_key: str,
    translator_version: int,
    target_profile_id: str,
    field_rules: tuple[OrderTranslationFieldRule, ...],
) -> dict[str, Any]:
    return {
        "type": "order_translation_mapping_config",
        "schema_version": 1,
        "translator_key": translator_key,
        "translator_version": translator_version,
        "target_profile_id": target_profile_id,
        "field_rules": field_rules,
    }


@dataclass(frozen=True, slots=True)
class OrderTranslationMapping:
    translator_key: str
    translator_version: int
    target_profile_id: str
    field_rules: tuple[OrderTranslationFieldRule, ...]
    config_hash: str

    def __post_init__(self) -> None:
        _canonical_text("translator_key", self.translator_key)
        if isinstance(self.translator_version, bool) or not isinstance(
            self.translator_version, int
        ):
            raise TypeError("translator_version must be int")
        if self.translator_version < 1:
            raise ValueError("translator_version must be positive")
        _canonical_text("target_profile_id", self.target_profile_id)
        if not isinstance(self.field_rules, tuple) or not all(
            isinstance(rule, OrderTranslationFieldRule) for rule in self.field_rules
        ):
            raise TypeError(
                "field_rules must be a tuple of OrderTranslationFieldRule"
            )
        canonical_fields = [rule.canonical_field for rule in self.field_rules]
        if len(set(canonical_fields)) != len(canonical_fields):
            raise ValueError("duplicate canonical field mapping")
        target_fields = [rule.target_field for rule in self.field_rules]
        if len(set(target_fields)) != len(target_fields):
            raise ValueError("duplicate target field mapping")
        ordered = tuple(
            sorted(
                self.field_rules,
                key=lambda rule: (rule.canonical_field, rule.target_field),
            )
        )
        object.__setattr__(self, "field_rules", ordered)
        _require_hash("config_hash", self.config_hash)
        expected_hash = canonical_sha256(self.config_payload())
        if self.config_hash != expected_hash:
            raise ValueError("config_hash does not match translation mapping")

    @classmethod
    def create(
        cls,
        *,
        translator_key: str,
        translator_version: int,
        target_profile_id: str,
        field_rules: tuple[OrderTranslationFieldRule, ...],
    ) -> Self:
        if not isinstance(field_rules, tuple) or not all(
            isinstance(rule, OrderTranslationFieldRule) for rule in field_rules
        ):
            raise TypeError(
                "field_rules must be a tuple of OrderTranslationFieldRule"
            )
        ordered = tuple(
            sorted(
                field_rules,
                key=lambda rule: (rule.canonical_field, rule.target_field),
            )
        )
        config_hash = canonical_sha256(
            _mapping_config_payload(
                translator_key=translator_key,
                translator_version=translator_version,
                target_profile_id=target_profile_id,
                field_rules=ordered,
            )
        )
        return cls(
            translator_key=translator_key,
            translator_version=translator_version,
            target_profile_id=target_profile_id,
            field_rules=ordered,
            config_hash=config_hash,
        )

    def config_payload(self) -> dict[str, Any]:
        return _mapping_config_payload(
            translator_key=self.translator_key,
            translator_version=self.translator_version,
            target_profile_id=self.target_profile_id,
            field_rules=self.field_rules,
        )

    @property
    def mapping_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_translation_mapping",
            "schema_version": 1,
            "translator_key": self.translator_key,
            "translator_version": self.translator_version,
            "target_profile_id": self.target_profile_id,
            "field_rules": self.field_rules,
            "config_hash": self.config_hash,
        }


def _validate_translation_context(
    *,
    source_order: Order,
    source_intent_hash: str,
    capability_approval: OrderCapabilityApproval,
    capability_decision_hash: str,
    translation_mapping: OrderTranslationMapping,
    translation_mapping_hash: str,
) -> None:
    if not isinstance(source_order, Order):
        raise TypeError("source_order must be Order")
    if not isinstance(capability_approval, OrderCapabilityApproval):
        raise TypeError("capability_approval must be OrderCapabilityApproval")
    if not isinstance(translation_mapping, OrderTranslationMapping):
        raise TypeError("translation_mapping must be OrderTranslationMapping")
    _require_hash("source_intent_hash", source_intent_hash)
    _require_hash("capability_decision_hash", capability_decision_hash)
    _require_hash("translation_mapping_hash", translation_mapping_hash)
    if canonical_sha256(source_order.intent) != source_intent_hash:
        raise OrderTranslationEvidenceError("source Intent hash mismatch")
    if capability_approval.intent_hash != source_intent_hash:
        raise OrderTranslationEvidenceError(
            "capability approval does not describe source intent"
        )
    if canonical_sha256(capability_approval) != capability_decision_hash:
        raise OrderTranslationEvidenceError("capability decision hash mismatch")
    if translation_mapping.mapping_hash != translation_mapping_hash:
        raise OrderTranslationEvidenceError("translation mapping hash mismatch")


def _spec_payload(
    *,
    source_order: Order,
    source_intent_hash: str,
    capability_approval: OrderCapabilityApproval,
    capability_decision_hash: str,
    translation_mapping: OrderTranslationMapping,
    translation_mapping_hash: str,
    field_mappings: tuple[TranslationFieldMapping, ...],
    translation_time: UtcInstant,
) -> dict[str, Any]:
    return {
        "type": "executable_order_spec_body",
        "schema_version": 1,
        "source_order": source_order,
        "source_intent_hash": source_intent_hash,
        "capability_approval": capability_approval,
        "capability_decision_hash": capability_decision_hash,
        "translation_mapping": translation_mapping,
        "translation_mapping_hash": translation_mapping_hash,
        "field_mappings": field_mappings,
        "translation_time": translation_time,
    }


def _tagged_id(prefix: str, payload: Any) -> str:
    return f"{prefix}:{canonical_sha256(payload)}"


@dataclass(frozen=True, slots=True)
class ExecutableOrderSpec:
    spec_id: str
    source_order: Order
    source_intent_hash: str
    capability_approval: OrderCapabilityApproval
    capability_decision_hash: str
    translation_mapping: OrderTranslationMapping
    translation_mapping_hash: str
    field_mappings: tuple[TranslationFieldMapping, ...]
    translation_time: UtcInstant

    def __post_init__(self) -> None:
        _validate_translation_context(
            source_order=self.source_order,
            source_intent_hash=self.source_intent_hash,
            capability_approval=self.capability_approval,
            capability_decision_hash=self.capability_decision_hash,
            translation_mapping=self.translation_mapping,
            translation_mapping_hash=self.translation_mapping_hash,
        )
        if not isinstance(self.translation_time, UtcInstant):
            raise TypeError("translation_time must be UtcInstant")
        if self.translation_time < self.source_order.created_at.instant:
            raise OrderTranslationEvidenceError("translation occurs before Order creation")
        _validate_complete_mappings(
            self.source_order.intent, self.translation_mapping, self.field_mappings
        )
        expected_id = _tagged_id(
            "executable-order-spec-v1", self._identity_payload()
        )
        if self.spec_id != expected_id:
            raise OrderTranslationEvidenceError("spec_id mismatch")

    @classmethod
    def create(
        cls,
        *,
        source_order: Order,
        capability_approval: OrderCapabilityApproval,
        translation_mapping: OrderTranslationMapping,
        field_mappings: tuple[TranslationFieldMapping, ...],
        translation_time: UtcInstant,
    ) -> Self:
        source_intent_hash = canonical_sha256(source_order.intent)
        capability_decision_hash = canonical_sha256(capability_approval)
        translation_mapping_hash = translation_mapping.mapping_hash
        payload = _spec_payload(
            source_order=source_order,
            source_intent_hash=source_intent_hash,
            capability_approval=capability_approval,
            capability_decision_hash=capability_decision_hash,
            translation_mapping=translation_mapping,
            translation_mapping_hash=translation_mapping_hash,
            field_mappings=field_mappings,
            translation_time=translation_time,
        )
        return cls(
            spec_id=_tagged_id("executable-order-spec-v1", payload),
            source_order=source_order,
            source_intent_hash=source_intent_hash,
            capability_approval=capability_approval,
            capability_decision_hash=capability_decision_hash,
            translation_mapping=translation_mapping,
            translation_mapping_hash=translation_mapping_hash,
            field_mappings=field_mappings,
            translation_time=translation_time,
        )

    @property
    def intent(self) -> OrderIntent:
        return self.source_order.intent

    @property
    def capability_decision_id(self) -> str:
        return self.capability_approval.decision_id

    def _identity_payload(self) -> dict[str, Any]:
        return _spec_payload(
            source_order=self.source_order,
            source_intent_hash=self.source_intent_hash,
            capability_approval=self.capability_approval,
            capability_decision_hash=self.capability_decision_hash,
            translation_mapping=self.translation_mapping,
            translation_mapping_hash=self.translation_mapping_hash,
            field_mappings=self.field_mappings,
            translation_time=self.translation_time,
        )

    @property
    def spec_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "executable_order_spec",
            "schema_version": 1,
            "spec_id": self.spec_id,
            **{
                key: value
                for key, value in self._identity_payload().items()
                if key not in {"type", "schema_version"}
            },
        }


def _validate_complete_mappings(
    intent: OrderIntent,
    mapping: OrderTranslationMapping,
    field_mappings: tuple[TranslationFieldMapping, ...],
) -> None:
    if not isinstance(field_mappings, tuple) or not all(
        isinstance(value, TranslationFieldMapping) for value in field_mappings
    ):
        raise TypeError("field_mappings must contain TranslationFieldMapping")
    rules = {rule.canonical_field: rule for rule in mapping.field_rules}
    if set(rules) != _INTENT_FIELD_SET:
        raise OrderTranslationEvidenceError("ExecutableOrderSpec requires complete mapping")
    values = _intent_values(intent)
    expected = tuple(
        sorted(
            (
                TranslationFieldMapping(
                    canonical_field=field,
                    canonical_value=_canonical_value(values[field]),
                    target_field=rules[field].target_field,
                    target_value=_canonical_value(values[field]),
                )
                for field in _INTENT_FIELDS
            ),
            key=lambda value: (value.canonical_field, value.target_field),
        )
    )
    if field_mappings != expected:
        raise OrderTranslationEvidenceError(
            "field mappings do not preserve source Intent semantics"
        )


def _mapping_evidence(
    intent: OrderIntent,
    mapping: OrderTranslationMapping,
) -> tuple[tuple[TranslationFieldMapping, ...], tuple[UnsupportedCapability, ...]]:
    values = _intent_values(intent)
    rules = {rule.canonical_field: rule for rule in mapping.field_rules}
    missing = sorted(_INTENT_FIELD_SET - set(rules))
    unknown = sorted(set(rules) - _INTENT_FIELD_SET)
    field_mappings = tuple(
        sorted(
            (
                TranslationFieldMapping(
                    canonical_field=field,
                    canonical_value=_canonical_value(values[field]),
                    target_field=rules[field].target_field,
                    target_value=_canonical_value(values[field]),
                )
                for field in _INTENT_FIELDS
                if field in rules
            ),
            key=lambda value: (value.canonical_field, value.target_field),
        )
    )
    unsupported = tuple(
        sorted(
            (
                *(
                    UnsupportedCapability(
                        capability=f"translation.{field}",
                        requested_value=_canonical_value(values[field]),
                        reason_code="missing_field_mapping",
                    )
                    for field in missing
                ),
                *(
                    UnsupportedCapability(
                        capability=f"translation.{field}",
                        requested_value=rules[field].target_field,
                        reason_code="unknown_field_mapping",
                    )
                    for field in unknown
                ),
            ),
            key=lambda value: (
                value.capability,
                value.requested_value,
                value.reason_code,
            ),
        )
    )
    return field_mappings, unsupported


@dataclass(frozen=True, slots=True)
class OrderTranslationResult:
    source_order: Order
    capability_approval: OrderCapabilityApproval
    translation_mapping: OrderTranslationMapping
    source_intent_hash: str
    capability_decision_hash: str
    translation_mapping_hash: str
    executable_spec: ExecutableOrderSpec | None
    report: OrderTranslationReport

    def __post_init__(self) -> None:
        _validate_translation_context(
            source_order=self.source_order,
            source_intent_hash=self.source_intent_hash,
            capability_approval=self.capability_approval,
            capability_decision_hash=self.capability_decision_hash,
            translation_mapping=self.translation_mapping,
            translation_mapping_hash=self.translation_mapping_hash,
        )
        if self.executable_spec is not None and not isinstance(
            self.executable_spec, ExecutableOrderSpec
        ):
            raise TypeError("executable_spec must be ExecutableOrderSpec or None")
        if not isinstance(self.report, OrderTranslationReport):
            raise TypeError("report must be OrderTranslationReport")
        if self.report.translation_time < self.source_order.created_at.instant:
            raise OrderTranslationEvidenceError("translation occurs before Order creation")
        field_mappings, unsupported = _mapping_evidence(
            self.source_order.intent, self.translation_mapping
        )
        translated = not unsupported
        expected_status = (
            TranslationStatus.TRANSLATED
            if translated
            else TranslationStatus.REJECTED
        )
        if self.report.status is not expected_status:
            raise OrderTranslationEvidenceError("report status mismatch")
        if translated != (self.executable_spec is not None):
            raise ValueError(
                "translated report requires spec and rejected report forbids spec"
            )
        if self.report.order_id != self.source_order.order_id:
            raise OrderTranslationEvidenceError("report Order identity mismatch")
        if self.report.translator_key != self.translation_mapping.translator_key:
            raise OrderTranslationEvidenceError("report translator key mismatch")
        if self.report.translator_version != str(
            self.translation_mapping.translator_version
        ):
            raise OrderTranslationEvidenceError("report translator version mismatch")
        if self.report.target_profile_id != self.translation_mapping.target_profile_id:
            raise OrderTranslationEvidenceError("report target Profile mismatch")
        if self.report.field_mappings != field_mappings:
            raise OrderTranslationEvidenceError("report field mappings mismatch")
        if self.report.unsupported_capabilities != unsupported:
            raise OrderTranslationEvidenceError("report rejection evidence mismatch")
        expected_report_id = _report_id(
            order=self.source_order,
            approval=self.capability_approval,
            mapping=self.translation_mapping,
            status=expected_status,
            unsupported=unsupported,
            field_mappings=field_mappings,
            translation_time=self.report.translation_time,
        )
        if self.report.report_id != expected_report_id:
            raise OrderTranslationEvidenceError("report_id mismatch")
        if self.executable_spec is not None:
            spec = self.executable_spec
            if spec.source_order != self.source_order:
                raise OrderTranslationEvidenceError("spec source Order mismatch")
            if spec.capability_approval != self.capability_approval:
                raise OrderTranslationEvidenceError("spec capability approval mismatch")
            if spec.translation_mapping != self.translation_mapping:
                raise OrderTranslationEvidenceError("spec translation mapping mismatch")
            if spec.field_mappings != field_mappings:
                raise OrderTranslationEvidenceError("spec field mappings mismatch")
            if spec.translation_time != self.report.translation_time:
                raise OrderTranslationEvidenceError("spec translation time mismatch")

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "order_translation_result",
            "schema_version": 1,
            "source_order": self.source_order,
            "capability_approval": self.capability_approval,
            "translation_mapping": self.translation_mapping,
            "source_intent_hash": self.source_intent_hash,
            "capability_decision_hash": self.capability_decision_hash,
            "translation_mapping_hash": self.translation_mapping_hash,
            "executable_spec": self.executable_spec,
            "report": self.report,
        }


def _report_id(
    *,
    order: Order,
    approval: OrderCapabilityApproval,
    mapping: OrderTranslationMapping,
    status: TranslationStatus,
    unsupported: tuple[UnsupportedCapability, ...],
    field_mappings: tuple[TranslationFieldMapping, ...],
    translation_time: UtcInstant,
) -> str:
    return _tagged_id(
        "order-translation-report-v1",
        {
            "type": "order_translation_report_identity",
            "schema_version": 1,
            "order_hash": canonical_sha256(order),
            "capability_decision_id": approval.decision_id,
            "capability_decision_hash": canonical_sha256(approval),
            "translation_mapping_hash": mapping.mapping_hash,
            "status": status.value,
            "unsupported_capabilities": unsupported,
            "field_mappings": field_mappings,
            "translation_time": translation_time,
        },
    )


class OrderTranslator:
    def translate(
        self,
        order: Order,
        approval: OrderCapabilityApproval,
        mapping: OrderTranslationMapping,
        translation_time: UtcInstant,
    ) -> OrderTranslationResult:
        if not isinstance(order, Order):
            raise TypeError("order must be Order")
        if not isinstance(approval, OrderCapabilityApproval):
            raise TypeError("approval must be OrderCapabilityApproval")
        if not isinstance(mapping, OrderTranslationMapping):
            raise TypeError("mapping must be OrderTranslationMapping")
        if not isinstance(translation_time, UtcInstant):
            raise TypeError("translation_time must be UtcInstant")
        intent_hash = canonical_sha256(order.intent)
        if (
            approval.source_intent != order.intent
            or approval.intent_hash != intent_hash
        ):
            raise OrderTranslationEvidenceError(
                "capability approval does not describe source intent"
            )
        if translation_time < order.created_at.instant:
            raise OrderTranslationEvidenceError("translation occurs before Order creation")

        field_mappings, unsupported = _mapping_evidence(order.intent, mapping)
        status = (
            TranslationStatus.REJECTED
            if unsupported
            else TranslationStatus.TRANSLATED
        )
        report = OrderTranslationReport(
            report_id=_report_id(
                order=order,
                approval=approval,
                mapping=mapping,
                status=status,
                unsupported=unsupported,
                field_mappings=field_mappings,
                translation_time=translation_time,
            ),
            order_id=order.order_id,
            translator_key=mapping.translator_key,
            translator_version=str(mapping.translator_version),
            target_profile_id=mapping.target_profile_id,
            status=status,
            unsupported_capabilities=unsupported,
            field_mappings=field_mappings,
            translation_time=translation_time,
        )
        spec = None
        if not unsupported:
            spec = ExecutableOrderSpec.create(
                source_order=order,
                capability_approval=approval,
                translation_mapping=mapping,
                field_mappings=field_mappings,
                translation_time=translation_time,
            )
        return OrderTranslationResult(
            source_order=order,
            capability_approval=approval,
            translation_mapping=mapping,
            source_intent_hash=intent_hash,
            capability_decision_hash=canonical_sha256(approval),
            translation_mapping_hash=mapping.mapping_hash,
            executable_spec=spec,
            report=report,
        )
