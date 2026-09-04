from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

import pytest

from crypto_quant_domain import (
    CanonicalizationError,
    InstrumentId,
    SimulationInstant,
    SourceSequence,
    StrategyDecisionCandidate,
    StrategyDecisionPayload,
    StrategySleeveId,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
)
from crypto_quant_trading import (
    StrategyOutputValidationContext,
    StrategyOutputValidator,
    StrategyValidationIssueCode,
)

from ._fixtures import BTC, ETH, candidate, catalog, context, valid_payload


def issue_codes(result: Any) -> set[StrategyValidationIssueCode]:
    assert result.failure is not None
    return {issue.code for issue in result.failure.issues}


def test_valid_candidate_becomes_the_only_authoritative_decision() -> None:
    result = StrategyOutputValidator().validate(candidate(), context())

    assert result.failure is None
    assert result.decision is not None
    assert result.decision.strategy_id == "trend-v1"
    assert result.decision.decision_time == UtcInstant(100)
    assert result.decision.observed_through == UtcInstant(90)
    assert result.decision.target_snapshot.sleeve_id == StrategySleeveId(
        "trend.primary"
    )
    assert result.decision.target_snapshot.targets[0].instrument_id == BTC
    assert result.decision.target_snapshot.targets[0].units == 500_000_000_000
    assert result.decision.confidence is not None
    assert result.decision.confidence.units == 875_000_000_000


def test_validation_context_binds_exact_instant_without_changing_candidate_schema() -> None:
    instant = SimulationInstant(
        UtcInstant(100), TimelinePhase(60, "decision"), SourceSequence(1)
    )
    result = StrategyOutputValidator().validate(
        candidate(), context(decision_instant=instant)
    )

    assert "decision_instant" not in candidate().payload.fields
    assert result.failure is None
    assert result.decision is not None
    assert result.decision.decision_instant == instant

    with pytest.raises(ValueError, match="decision_instant instant"):
        context(
            decision_instant=SimulationInstant(
                UtcInstant(101), instant.phase, instant.source_sequence
            )
        )


def test_schema_missing_and_unknown_fields_fail_without_partial_decision() -> None:
    payload = valid_payload()
    del payload["reason"]
    payload["unexpected"] = "preserved"

    result = StrategyOutputValidator().validate(candidate(payload), context())

    assert result.decision is None
    assert issue_codes(result) == {
        StrategyValidationIssueCode.MISSING_FIELD,
        StrategyValidationIssueCode.UNEXPECTED_FIELD,
    }
    assert result.failure is not None
    assert [issue.path for issue in result.failure.issues] == [
        "$.reason",
        "$.unexpected",
    ]


def test_identity_and_time_causality_are_checked_against_trusted_context() -> None:
    payload = valid_payload()
    payload.update(
        strategy_id="other-strategy",
        sleeve_id="other.sleeve",
        decision_time=101,
        observed_through=102,
        effective_time=99,
        expires_at=99,
    )

    result = StrategyOutputValidator().validate(candidate(payload), context())

    assert result.decision is None
    assert issue_codes(result) == {
        StrategyValidationIssueCode.IDENTITY_MISMATCH,
        StrategyValidationIssueCode.TIME_CAUSALITY_VIOLATION,
    }
    assert result.failure is not None
    assert {issue.path for issue in result.failure.issues} == {
        "$.strategy_id",
        "$.sleeve_id",
        "$.decision_time",
        "$.observed_through",
        "$.effective_time",
        "$.expires_at",
    }


def test_unknown_outside_universe_and_duplicate_targets_are_not_deleted() -> None:
    payload = valid_payload()
    payload["targets"] = [
        {
            "instrument_id": {
                "venue": "binance_usdm",
                "stable_key": "linear_perpetual:unknown-usdt",
            },
            "value": "0.1",
        },
        {
            "instrument_id": {
                "venue": ETH.venue.value,
                "stable_key": ETH.stable_key,
            },
            "value": "0.2",
        },
        {
            "instrument_id": {
                "venue": BTC.venue.value,
                "stable_key": BTC.stable_key,
            },
            "value": "0.3",
        },
        {
            "instrument_id": {
                "venue": BTC.venue.value,
                "stable_key": BTC.stable_key,
            },
            "value": "0.4",
        },
    ]

    result = StrategyOutputValidator().validate(candidate(payload), context())

    assert result.decision is None
    assert issue_codes(result) == {
        StrategyValidationIssueCode.UNKNOWN_INSTRUMENT,
        StrategyValidationIssueCode.INSTRUMENT_OUTSIDE_UNIVERSE,
        StrategyValidationIssueCode.DUPLICATE_TARGET,
    }


@pytest.mark.parametrize(
    ("value", "expected_units"),
    [
        (1, 1_000_000_000_000),
        (Decimal("-0.25"), -250_000_000_000),
        ("0.000000000001", 1),
        ("2", 2_000_000_000_000),
        (
            Decimal("12345678901234567890.123456789012"),
            12345678901234567890123456789012,
        ),
    ],
)
def test_target_decimal_values_quantize_exactly_without_rounding(
    value: object, expected_units: int
) -> None:
    payload = valid_payload()
    cast(list[dict[str, Any]], payload["targets"])[0]["value"] = value

    result = StrategyOutputValidator().validate(candidate(payload), context())

    assert result.failure is None
    assert result.decision is not None
    assert result.decision.target_snapshot.targets[0].units == expected_units


@pytest.mark.parametrize(
    "value",
    [True, 0.1, Decimal("0.0000000000001"), "0.500", "1e-1", "NaN"],
)
def test_float_noncanonical_and_inexact_target_values_fail_closed(value: object) -> None:
    payload = valid_payload()
    cast(list[dict[str, Any]], payload["targets"])[0]["value"] = value

    result = StrategyOutputValidator().validate(candidate(payload), context())

    assert result.decision is None
    assert issue_codes(result) == {
        StrategyValidationIssueCode.QUANTIZATION_FAILURE
    }


def test_confidence_range_and_canonical_evidence_are_contract_failures() -> None:
    payload = valid_payload()
    payload["confidence"] = "1.000000000001"
    payload["reason"] = " not canonical "
    payload["evidence"] = {"score": 0.5}

    result = StrategyOutputValidator().validate(candidate(payload), context())

    assert result.decision is None
    assert issue_codes(result) == {
        StrategyValidationIssueCode.INVALID_VALUE,
        StrategyValidationIssueCode.CANONICAL_VALUE_FAILURE,
    }
    assert result.failure is not None
    assert {issue.path for issue in result.failure.issues} == {
        "$.confidence",
        "$.reason",
        "$.evidence",
    }


def test_failure_hash_is_order_independent_but_preserves_scalar_types() -> None:
    first = {"unexpected_b": 1, "unexpected_a": Decimal("1")}
    second = {"unexpected_a": Decimal("1"), "unexpected_b": 1}
    integer = {"unexpected_b": 1, "unexpected_a": 1}

    first_result = StrategyOutputValidator().validate(candidate(first), context())
    second_result = StrategyOutputValidator().validate(candidate(second), context())
    integer_result = StrategyOutputValidator().validate(candidate(integer), context())

    assert first_result.failure is not None
    assert second_result.failure is not None
    assert integer_result.failure is not None
    assert (
        first_result.failure.candidate_payload_hash
        == second_result.failure.candidate_payload_hash
    )
    assert (
        first_result.failure.candidate_payload_hash
        != integer_result.failure.candidate_payload_hash
    )
    with pytest.raises(CanonicalizationError):
        canonical_bytes(StrategyDecisionCandidate(StrategyDecisionPayload(first)))


def test_validation_context_rejects_duplicate_or_unknown_universe_members() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        StrategyOutputValidationContext(
            expected_strategy_id="trend-v1",
            expected_sleeve_id=StrategySleeveId("trend.primary"),
            decision_time=UtcInstant(100),
            instrument_catalog=catalog(),
            universe=(BTC, BTC),
        )
    with pytest.raises(ValueError, match="unknown"):
        StrategyOutputValidationContext(
            expected_strategy_id="trend-v1",
            expected_sleeve_id=StrategySleeveId("trend.primary"),
            decision_time=UtcInstant(100),
            instrument_catalog=catalog(),
            universe=(InstrumentId(BTC.venue, "linear_perpetual:unknown-usdt"),),
        )
