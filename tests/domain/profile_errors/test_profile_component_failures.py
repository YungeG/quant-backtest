from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from crypto_quant_backtest import (
    SimulationComponentRef,
    SimulationPortOutcome,
    SimulationPortType,
)
from crypto_quant_domain import (
    ProfileComponentFailure,
    ProfileComponentFailureCode,
)
from crypto_quant_trading import ProfileComponentRef, ProfilePortOutcome, ProfilePortType


class CanonicalRequest:
    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "profile_error_test_request", "request_id": "request:1"}


def test_reason_code_catalog_is_stable_and_complete() -> None:
    assert [code.value for code in ProfileComponentFailureCode] == [
        "profile_lookup_failed",
        "component_incompatible",
        "capability_missing",
        "applicability_violation",
        "unsupported_semantics",
    ]


def test_failure_is_an_immutable_minimal_canonical_value() -> None:
    failure = ProfileComponentFailure(
        ProfileComponentFailureCode.CAPABILITY_MISSING,
        "prices.execution_reference",
    )

    assert failure.to_canonical_dict() == {
        "type": "profile_component_failure",
        "reason_code": "capability_missing",
        "subject_key": "prices.execution_reference",
    }
    assert [field.name for field in fields(failure)] == ["reason_code", "subject_key"]
    with pytest.raises(FrozenInstanceError):
        failure.subject_key = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("reason_code", "expected_error"),
    [
        ("capability_missing", TypeError),
        (None, TypeError),
    ],
)
def test_failure_rejects_untyped_reason_codes(
    reason_code: object, expected_error: type[Exception]
) -> None:
    with pytest.raises(expected_error):
        ProfileComponentFailure(reason_code, "bars.ohlcv")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("subject_key", "expected_error"),
    [
        (None, TypeError),
        (1, TypeError),
        ("", ValueError),
        (" leading", ValueError),
        ("trailing ", ValueError),
        ("e\u0301", ValueError),
    ],
)
def test_failure_rejects_invalid_or_noncanonical_subject_keys(
    subject_key: object, expected_error: type[Exception]
) -> None:
    with pytest.raises(expected_error):
        ProfileComponentFailure(
            ProfileComponentFailureCode.PROFILE_LOOKUP_FAILED,
            subject_key,  # type: ignore[arg-type]
        )


def test_kernel_profile_outcome_accepts_the_shared_failure_contract() -> None:
    request = CanonicalRequest()
    failure = ProfileComponentFailure(
        ProfileComponentFailureCode.COMPONENT_INCOMPATIBLE,
        "position_accounting_model",
    )
    outcome = ProfilePortOutcome.for_failure(
        ProfileComponentRef(
            ProfilePortType.POSITION_ACCOUNTING_MODEL,
            "test.position-accounting.v1",
            1,
            f"sha256:{'ab' * 32}",
        ),
        request,
        failure,
    )

    assert outcome.failure is failure
    assert outcome.result is None


def test_simulation_outcome_accepts_the_shared_failure_contract() -> None:
    request = CanonicalRequest()
    failure = ProfileComponentFailure(
        ProfileComponentFailureCode.APPLICABILITY_VIOLATION,
        "bar.execution-model.applicability",
    )
    outcome = SimulationPortOutcome.for_failure(
        SimulationComponentRef(
            SimulationPortType.EXECUTION_MODEL,
            "test.execution-model.v1",
            1,
            f"sha256:{'cd' * 32}",
        ),
        request,
        failure,
    )

    assert outcome.failure is failure
    assert outcome.result is None
