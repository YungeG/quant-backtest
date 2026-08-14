from __future__ import annotations

import hashlib
import re
import struct
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

from crypto_quant_domain import (
    CanonicalizationError,
    InstrumentCatalog,
    InstrumentId,
    Rate,
    Scale,
    SimulationInstant,
    StrategyDecision,
    StrategyDecisionCandidate,
    StrategySleeveId,
    TargetExposureFraction,
    TargetSnapshot,
    UtcInstant,
    VenueId,
    canonical_bytes,
)


_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DECIMAL_TEXT = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
_CANDIDATE_FINGERPRINT_V1 = b"strategy-decision-candidate-fingerprint-v1\0"
_SCALE = Scale(12)
_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "strategy_id",
        "sleeve_id",
        "decision_time",
        "observed_through",
        "effective_time",
        "expires_at",
        "targets",
        "confidence",
        "reason",
        "evidence",
    }
)
_TARGET_FIELDS = frozenset({"instrument_id", "value"})
_INSTRUMENT_FIELDS = frozenset({"venue", "stable_key"})


class StrategyValidationIssueCode(str, Enum):
    MISSING_FIELD = "missing_field"
    UNEXPECTED_FIELD = "unexpected_field"
    INVALID_TYPE = "invalid_type"
    INVALID_VALUE = "invalid_value"
    IDENTITY_MISMATCH = "identity_mismatch"
    TIME_CAUSALITY_VIOLATION = "time_causality_violation"
    UNKNOWN_INSTRUMENT = "unknown_instrument"
    INSTRUMENT_OUTSIDE_UNIVERSE = "instrument_outside_universe"
    DUPLICATE_TARGET = "duplicate_target"
    QUANTIZATION_FAILURE = "quantization_failure"
    CANONICAL_VALUE_FAILURE = "canonical_value_failure"


@dataclass(frozen=True, slots=True)
class StrategyValidationIssue:
    code: StrategyValidationIssueCode
    path: str
    subject_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, StrategyValidationIssueCode):
            raise TypeError("code must be StrategyValidationIssueCode")
        _require_canonical_text("path", self.path)
        _require_canonical_text("subject_key", self.subject_key)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "strategy_validation_issue",
            "code": self.code.value,
            "path": self.path,
            "subject_key": self.subject_key,
        }


@dataclass(frozen=True, slots=True)
class StrategyValidationFailure:
    candidate_payload_hash: str
    issues: tuple[StrategyValidationIssue, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_payload_hash, str) or _SHA256.fullmatch(
            self.candidate_payload_hash
        ) is None:
            raise ValueError("candidate_payload_hash must be canonical sha256")
        if not isinstance(self.issues, tuple) or not self.issues:
            raise ValueError("issues must be a non-empty tuple")
        if not all(isinstance(issue, StrategyValidationIssue) for issue in self.issues):
            raise TypeError("issues must contain StrategyValidationIssue")
        ordered = tuple(sorted(set(self.issues), key=_issue_key))
        object.__setattr__(self, "issues", ordered)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "strategy_validation_failure",
            "candidate_payload_hash": self.candidate_payload_hash,
            "issues": [issue.to_canonical_dict() for issue in self.issues],
        }


@dataclass(frozen=True, slots=True)
class StrategyValidationResult:
    decision: StrategyDecision | None
    failure: StrategyValidationFailure | None

    def __post_init__(self) -> None:
        if (self.decision is None) == (self.failure is None):
            raise ValueError("result requires exactly one decision or failure")
        if self.decision is not None and not isinstance(self.decision, StrategyDecision):
            raise TypeError("decision must be StrategyDecision or None")
        if self.failure is not None and not isinstance(
            self.failure, StrategyValidationFailure
        ):
            raise TypeError("failure must be StrategyValidationFailure or None")

    @classmethod
    def valid(cls, decision: StrategyDecision) -> StrategyValidationResult:
        return cls(decision=decision, failure=None)

    @classmethod
    def invalid(
        cls, failure: StrategyValidationFailure
    ) -> StrategyValidationResult:
        return cls(decision=None, failure=failure)


@dataclass(frozen=True, slots=True)
class StrategyOutputValidationContext:
    expected_strategy_id: str
    expected_sleeve_id: StrategySleeveId
    decision_time: UtcInstant
    instrument_catalog: InstrumentCatalog
    universe: tuple[InstrumentId, ...]
    decision_instant: SimulationInstant | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        _require_canonical_text("expected_strategy_id", self.expected_strategy_id)
        if not isinstance(self.expected_sleeve_id, StrategySleeveId):
            raise TypeError("expected_sleeve_id must be StrategySleeveId")
        if not isinstance(self.decision_time, UtcInstant):
            raise TypeError("decision_time must be UtcInstant")
        if self.decision_instant is not None:
            if not isinstance(self.decision_instant, SimulationInstant):
                raise TypeError("decision_instant must be SimulationInstant or None")
            if self.decision_instant.instant != self.decision_time:
                raise ValueError("decision_instant instant must equal decision_time")
        if not isinstance(self.instrument_catalog, InstrumentCatalog):
            raise TypeError("instrument_catalog must be InstrumentCatalog")
        if not isinstance(self.universe, tuple) or not all(
            isinstance(instrument_id, InstrumentId) for instrument_id in self.universe
        ):
            raise TypeError("universe must be a tuple of InstrumentId")
        if len(set(self.universe)) != len(self.universe):
            raise ValueError("duplicate InstrumentId in validation universe")
        known = {
            definition.instrument_id
            for definition in self.instrument_catalog.instruments
        }
        unknown = set(self.universe) - known
        if unknown:
            raise ValueError(
                "unknown InstrumentId in validation universe: "
                + ", ".join(sorted(map(str, unknown)))
            )
        object.__setattr__(self, "universe", tuple(sorted(self.universe)))


class StrategyOutputValidator:
    def validate(
        self,
        candidate: StrategyDecisionCandidate,
        context: StrategyOutputValidationContext,
    ) -> StrategyValidationResult:
        if not isinstance(candidate, StrategyDecisionCandidate):
            raise TypeError("candidate must be StrategyDecisionCandidate")
        if not isinstance(context, StrategyOutputValidationContext):
            raise TypeError("context must be StrategyOutputValidationContext")

        fields = candidate.payload.fields
        issues: list[StrategyValidationIssue] = []
        _validate_fields(fields, _REQUIRED_FIELDS, "$", issues)
        _validate_schema_version(fields, issues)

        strategy_id = _parse_text(fields, "strategy_id", issues)
        sleeve_id = _parse_sleeve(fields, issues)
        decision_time = _parse_instant(fields, "decision_time", issues)
        observed_through = _parse_instant(fields, "observed_through", issues)
        effective_time = _parse_instant(fields, "effective_time", issues)
        expires_at = _parse_optional_instant(fields, "expires_at", issues)
        targets = _parse_targets(fields, context, issues)
        confidence = _parse_confidence(fields, issues)
        reason = _parse_text(fields, "reason", issues, canonical_failure=True)
        evidence = _parse_evidence(fields, issues)

        _validate_identity(
            strategy_id,
            sleeve_id,
            decision_time,
            context,
            issues,
        )
        _validate_time_causality(
            decision_time,
            observed_through,
            effective_time,
            expires_at,
            issues,
        )

        if issues:
            return StrategyValidationResult.invalid(
                StrategyValidationFailure(
                    candidate_payload_hash=_candidate_payload_hash(fields),
                    issues=tuple(issues),
                )
            )

        if (
            strategy_id is None
            or sleeve_id is None
            or decision_time is None
            or observed_through is None
            or effective_time is None
            or targets is None
            or reason is None
            or evidence is None
        ):
            raise AssertionError("validated candidate has incomplete typed fields")

        decision = StrategyDecision(
            strategy_id=strategy_id,
            decision_time=decision_time,
            observed_through=observed_through,
            target_snapshot=TargetSnapshot(
                sleeve_id=sleeve_id,
                effective_time=effective_time,
                expires_at=expires_at,
                targets=targets,
            ),
            confidence=confidence,
            reason=reason,
            evidence=evidence,
            decision_instant=context.decision_instant,
        )
        return StrategyValidationResult.valid(decision)


def _require_canonical_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)


def _issue_key(issue: StrategyValidationIssue) -> tuple[str, str, str]:
    return issue.path, issue.code.value, issue.subject_key


def _add_issue(
    issues: list[StrategyValidationIssue],
    code: StrategyValidationIssueCode,
    path: str,
    subject_key: str,
) -> None:
    issues.append(StrategyValidationIssue(code, path, subject_key))


def _validate_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    path: str,
    issues: list[StrategyValidationIssue],
) -> None:
    for field in sorted(expected - set(value)):
        _add_issue(
            issues,
            StrategyValidationIssueCode.MISSING_FIELD,
            f"{path}.{field}",
            field,
        )
    for field in sorted(set(value) - expected):
        _add_issue(
            issues,
            StrategyValidationIssueCode.UNEXPECTED_FIELD,
            f"{path}.{field}",
            field,
        )


def _validate_schema_version(
    fields: Mapping[str, Any], issues: list[StrategyValidationIssue]
) -> None:
    if "schema_version" not in fields:
        return
    value = fields["schema_version"]
    if isinstance(value, bool) or not isinstance(value, int):
        code = StrategyValidationIssueCode.INVALID_TYPE
    elif value != 1:
        code = StrategyValidationIssueCode.INVALID_VALUE
    else:
        return
    _add_issue(issues, code, "$.schema_version", "schema_version")


def _parse_text(
    fields: Mapping[str, Any],
    field: str,
    issues: list[StrategyValidationIssue],
    *,
    canonical_failure: bool = False,
) -> str | None:
    if field not in fields:
        return None
    value = fields[field]
    if not isinstance(value, str):
        _add_issue(
            issues, StrategyValidationIssueCode.INVALID_TYPE, f"$.{field}", field
        )
        return None
    try:
        _require_canonical_text(field, value)
    except (ValueError, CanonicalizationError):
        _add_issue(
            issues,
            (
                StrategyValidationIssueCode.CANONICAL_VALUE_FAILURE
                if canonical_failure
                else StrategyValidationIssueCode.INVALID_VALUE
            ),
            f"$.{field}",
            field,
        )
        return None
    return value


def _parse_sleeve(
    fields: Mapping[str, Any], issues: list[StrategyValidationIssue]
) -> StrategySleeveId | None:
    value = _parse_text(fields, "sleeve_id", issues)
    if value is None:
        return None
    try:
        return StrategySleeveId(value)
    except (ValueError, CanonicalizationError):
        _add_issue(
            issues,
            StrategyValidationIssueCode.INVALID_VALUE,
            "$.sleeve_id",
            "sleeve_id",
        )
        return None


def _parse_instant(
    fields: Mapping[str, Any], field: str, issues: list[StrategyValidationIssue]
) -> UtcInstant | None:
    if field not in fields:
        return None
    value = fields[field]
    if isinstance(value, bool) or not isinstance(value, int):
        _add_issue(
            issues, StrategyValidationIssueCode.INVALID_TYPE, f"$.{field}", field
        )
        return None
    return UtcInstant(value)


def _parse_optional_instant(
    fields: Mapping[str, Any], field: str, issues: list[StrategyValidationIssue]
) -> UtcInstant | None:
    if field not in fields or fields[field] is None:
        return None
    return _parse_instant(fields, field, issues)


def _parse_targets(
    fields: Mapping[str, Any],
    context: StrategyOutputValidationContext,
    issues: list[StrategyValidationIssue],
) -> tuple[TargetExposureFraction, ...] | None:
    if "targets" not in fields:
        return None
    rows = fields["targets"]
    if not isinstance(rows, tuple):
        _add_issue(
            issues,
            StrategyValidationIssueCode.INVALID_TYPE,
            "$.targets",
            "targets",
        )
        return None

    targets: list[TargetExposureFraction] = []
    seen: set[InstrumentId] = set()
    known = {definition.instrument_id for definition in context.instrument_catalog.instruments}
    universe = set(context.universe)
    for index, row in enumerate(rows):
        path = f"$.targets[{index}]"
        target = _parse_target(row, path, known, universe, seen, issues)
        if target is not None:
            targets.append(target)
    return tuple(targets)


def _parse_target(
    row: Any,
    path: str,
    known: set[InstrumentId],
    universe: set[InstrumentId],
    seen: set[InstrumentId],
    issues: list[StrategyValidationIssue],
) -> TargetExposureFraction | None:
    if not isinstance(row, Mapping):
        _add_issue(issues, StrategyValidationIssueCode.INVALID_TYPE, path, "target")
        return None
    _validate_fields(row, _TARGET_FIELDS, path, issues)
    instrument_id = _parse_instrument_id(row, path, issues)
    units = _parse_target_units(row, path, issues)
    if instrument_id is not None:
        instrument_path = f"{path}.instrument_id"
        if instrument_id in seen:
            _add_issue(
                issues,
                StrategyValidationIssueCode.DUPLICATE_TARGET,
                instrument_path,
                str(instrument_id),
            )
        else:
            seen.add(instrument_id)
        if instrument_id not in known:
            _add_issue(
                issues,
                StrategyValidationIssueCode.UNKNOWN_INSTRUMENT,
                instrument_path,
                str(instrument_id),
            )
        elif instrument_id not in universe:
            _add_issue(
                issues,
                StrategyValidationIssueCode.INSTRUMENT_OUTSIDE_UNIVERSE,
                instrument_path,
                str(instrument_id),
            )
    if instrument_id is None or units is None:
        return None
    return TargetExposureFraction(instrument_id, units)


def _parse_instrument_id(
    row: Mapping[str, Any], path: str, issues: list[StrategyValidationIssue]
) -> InstrumentId | None:
    if "instrument_id" not in row:
        return None
    value = row["instrument_id"]
    instrument_path = f"{path}.instrument_id"
    if not isinstance(value, Mapping):
        _add_issue(
            issues,
            StrategyValidationIssueCode.INVALID_TYPE,
            instrument_path,
            "instrument_id",
        )
        return None
    _validate_fields(value, _INSTRUMENT_FIELDS, instrument_path, issues)
    venue = value.get("venue")
    stable_key = value.get("stable_key")
    if not isinstance(venue, str) or not isinstance(stable_key, str):
        _add_issue(
            issues,
            StrategyValidationIssueCode.INVALID_TYPE,
            instrument_path,
            "instrument_id",
        )
        return None
    try:
        return InstrumentId(VenueId(venue), stable_key)
    except (TypeError, ValueError):
        _add_issue(
            issues,
            StrategyValidationIssueCode.INVALID_VALUE,
            instrument_path,
            "instrument_id",
        )
        return None


def _parse_target_units(
    row: Mapping[str, Any], path: str, issues: list[StrategyValidationIssue]
) -> int | None:
    if "value" not in row:
        return None
    units = _exact_scaled_units(row["value"])
    if units is None:
        _add_issue(
            issues,
            StrategyValidationIssueCode.QUANTIZATION_FAILURE,
            f"{path}.value",
            "value",
        )
    return units


def _parse_confidence(
    fields: Mapping[str, Any], issues: list[StrategyValidationIssue]
) -> Rate | None:
    if "confidence" not in fields or fields["confidence"] is None:
        return None
    units = _exact_scaled_units(fields["confidence"])
    if units is None:
        _add_issue(
            issues,
            StrategyValidationIssueCode.QUANTIZATION_FAILURE,
            "$.confidence",
            "confidence",
        )
        return None
    if not 0 <= units <= _SCALE.factor:
        _add_issue(
            issues,
            StrategyValidationIssueCode.INVALID_VALUE,
            "$.confidence",
            "confidence",
        )
        return None
    return Rate(units, _SCALE, "confidence")


def _exact_scaled_units(value: Any) -> int | None:
    if isinstance(value, bool) or isinstance(value, float):
        return None
    if isinstance(value, int):
        decimal = Decimal(value)
    elif isinstance(value, Decimal):
        decimal = value
    elif isinstance(value, str):
        if not _is_canonical_decimal_text(value):
            return None
        try:
            decimal = Decimal(value)
        except InvalidOperation:
            return None
    else:
        return None
    units = _scale_decimal_exactly(decimal)
    if units is None:
        return None
    try:
        canonical_bytes(units)
    except CanonicalizationError:
        return None
    return units


def _is_canonical_decimal_text(value: str) -> bool:
    if _DECIMAL_TEXT.fullmatch(value) is None or value == "-0":
        return False
    return "." not in value or not value.endswith("0")


def _scale_decimal_exactly(value: Decimal) -> int | None:
    if not value.is_finite():
        return None
    parts = value.as_tuple()
    if not isinstance(parts.exponent, int):
        return None
    coefficient = 0
    for digit in parts.digits:
        coefficient = coefficient * 10 + digit
    if coefficient == 0:
        return 0
    power = parts.exponent + _SCALE.places
    if power >= 0:
        units = coefficient * (10**power)
    else:
        removed_places = -power
        if removed_places > len(parts.digits):
            return None
        units, remainder = divmod(coefficient, 10**removed_places)
        if remainder:
            return None
    return -units if parts.sign else units


def _parse_evidence(
    fields: Mapping[str, Any], issues: list[StrategyValidationIssue]
) -> Mapping[str, Any] | None:
    if "evidence" not in fields:
        return None
    value = fields["evidence"]
    if not isinstance(value, Mapping):
        _add_issue(
            issues,
            StrategyValidationIssueCode.INVALID_TYPE,
            "$.evidence",
            "evidence",
        )
        return None
    try:
        canonical_bytes(value)
    except CanonicalizationError:
        _add_issue(
            issues,
            StrategyValidationIssueCode.CANONICAL_VALUE_FAILURE,
            "$.evidence",
            "evidence",
        )
        return None
    return value


def _validate_identity(
    strategy_id: str | None,
    sleeve_id: StrategySleeveId | None,
    decision_time: UtcInstant | None,
    context: StrategyOutputValidationContext,
    issues: list[StrategyValidationIssue],
) -> None:
    if strategy_id is not None and strategy_id != context.expected_strategy_id:
        _add_issue(
            issues,
            StrategyValidationIssueCode.IDENTITY_MISMATCH,
            "$.strategy_id",
            "strategy_id",
        )
    if sleeve_id is not None and sleeve_id != context.expected_sleeve_id:
        _add_issue(
            issues,
            StrategyValidationIssueCode.IDENTITY_MISMATCH,
            "$.sleeve_id",
            "sleeve_id",
        )
    if decision_time is not None and decision_time != context.decision_time:
        _add_issue(
            issues,
            StrategyValidationIssueCode.IDENTITY_MISMATCH,
            "$.decision_time",
            "decision_time",
        )


def _validate_time_causality(
    decision_time: UtcInstant | None,
    observed_through: UtcInstant | None,
    effective_time: UtcInstant | None,
    expires_at: UtcInstant | None,
    issues: list[StrategyValidationIssue],
) -> None:
    if (
        decision_time is not None
        and observed_through is not None
        and observed_through > decision_time
    ):
        _add_issue(
            issues,
            StrategyValidationIssueCode.TIME_CAUSALITY_VIOLATION,
            "$.observed_through",
            "observed_through",
        )
    if (
        decision_time is not None
        and effective_time is not None
        and effective_time < decision_time
    ):
        _add_issue(
            issues,
            StrategyValidationIssueCode.TIME_CAUSALITY_VIOLATION,
            "$.effective_time",
            "effective_time",
        )
    if (
        effective_time is not None
        and expires_at is not None
        and expires_at <= effective_time
    ):
        _add_issue(
            issues,
            StrategyValidationIssueCode.TIME_CAUSALITY_VIOLATION,
            "$.expires_at",
            "expires_at",
        )


def _candidate_payload_hash(value: Any) -> str:
    digest = hashlib.sha256(_CANDIDATE_FINGERPRINT_V1 + _fingerprint(value))
    return f"sha256:{digest.hexdigest()}"


def _frame(tag: bytes, payload: bytes = b"") -> bytes:
    return tag + len(payload).to_bytes(8, "big") + payload


def _fingerprint(value: Any) -> bytes:
    if value is None:
        return _frame(b"n")
    if isinstance(value, bool):
        return _frame(b"b", b"1" if value else b"0")
    if isinstance(value, int):
        return _frame(b"i", str(value).encode("ascii"))
    if isinstance(value, float):
        return _frame(b"f", struct.pack(">d", value))
    if isinstance(value, Decimal):
        decimal_tuple = value.as_tuple()
        digits = bytes(decimal_tuple.digits)
        payload = (
            bytes((decimal_tuple.sign,))
            + _frame(b"d", digits)
            + _frame(b"e", str(decimal_tuple.exponent).encode("ascii"))
        )
        return _frame(b"q", payload)
    if isinstance(value, str):
        return _frame(b"s", value.encode("utf-8", errors="surrogatepass"))
    if isinstance(value, Mapping):
        rows = sorted(
            (_fingerprint(key), _fingerprint(child))
            for key, child in value.items()
        )
        encoded = b"".join(
            _frame(b"k", key) + _frame(b"v", child) for key, child in rows
        )
        return _frame(b"m", encoded)
    if isinstance(value, (list, tuple)):
        encoded = b"".join(
            _frame(b"v", _fingerprint(child)) for child in value
        )
        return _frame(b"l", encoded)
    raise TypeError(f"unsupported candidate payload type: {type(value).__name__}")
