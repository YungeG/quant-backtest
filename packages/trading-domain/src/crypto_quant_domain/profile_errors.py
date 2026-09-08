"""Shared canonical failures for profile components and resolution."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum


class ProfileComponentFailureCode(str, Enum):
    """Stable cross-runtime reason codes for profile component failures."""

    PROFILE_LOOKUP_FAILED = "profile_lookup_failed"
    COMPONENT_INCOMPATIBLE = "component_incompatible"
    CAPABILITY_MISSING = "capability_missing"
    APPLICABILITY_VIOLATION = "applicability_violation"
    UNSUPPORTED_SEMANTICS = "unsupported_semantics"


@dataclass(frozen=True, slots=True)
class ProfileComponentFailure:
    """Minimal structured failure shared by profile and simulation ports."""

    reason_code: ProfileComponentFailureCode
    subject_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.reason_code, ProfileComponentFailureCode):
            raise TypeError("reason_code must be ProfileComponentFailureCode")
        if type(self.subject_key) is not str:
            raise TypeError("subject_key must be str")
        if (
            not self.subject_key
            or self.subject_key.strip() != self.subject_key
            or unicodedata.normalize("NFC", self.subject_key) != self.subject_key
        ):
            raise ValueError("subject_key must be non-empty canonical text")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "profile_component_failure",
            "reason_code": self.reason_code.value,
            "subject_key": self.subject_key,
        }
