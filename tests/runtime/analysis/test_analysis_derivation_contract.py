from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json
from pathlib import Path

import pytest

from crypto_quant_backtest import (
    BacktestMetricProfile,
    VerifiedCompletedPublication,
    derive_backtest_analysis,
)
from crypto_quant_backtest.analysis_derivation import _calculate_simple_period_return
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    Money,
    Scale,
    canonical_bytes,
    canonical_sha256,
)
from tests.runtime.integration._fixtures import completed_journey

_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE = _ROOT / "tests/fixtures/runtime/bt-gap05-completed-analysis-v1.json"
_FIXTURE_SHA256 = "1eec1c7a9bea2d90323bc775e48f52d770392c1cc237aa6d40b242f3faf1acce"


def _load_fixture() -> dict[str, object]:
    value = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert type(value) is dict
    return value


def _profile() -> tuple[ArtifactRef, BacktestMetricProfile]:
    profile = BacktestMetricProfile("simple_period_return.fill_count.v1", 1)
    ref = ArtifactRef.from_envelope(
        ArtifactEnvelope.create("backtest_metric_profile", 1, profile)
    )
    return ref, profile


def _money(value: str, currency: str = "USD") -> Money:
    sign = -1 if value.startswith("-") else 1
    unsigned = value.removeprefix("-")
    whole, dot, fraction = unsigned.partition(".")
    return Money(
        sign * int(whole + fraction),
        Scale(len(fraction) if dot else 0),
        currency,
    )


def test_completed_derivation_matches_frozen_artifact_and_is_idempotent(
    tmp_path: Path,
) -> None:
    fixture = _load_fixture()
    assert sha256(_FIXTURE.read_bytes()).hexdigest() == _FIXTURE_SHA256
    assert fixture["fixture_id"] == "bt-gap05-completed-analysis-v1"
    journey = completed_journey(tmp_path)
    finalized = journey.publication.finalized_result
    assert finalized is not None
    completed = VerifiedCompletedPublication(finalized, journey.case)
    profile_ref, profile = _profile()

    first = derive_backtest_analysis(completed, profile_ref, profile)
    second = derive_backtest_analysis(completed, profile_ref, profile)
    expected = fixture["derived"]
    assert type(expected) is dict
    assert first == second
    assert canonical_bytes(first.analysis) == canonical_bytes(expected["stored_payload"])
    assert canonical_bytes(first) == canonical_bytes(expected["loaded_view"])
    envelope = ArtifactEnvelope.create("backtest_analysis", 1, first.analysis)
    assert canonical_bytes(envelope).decode() == expected["expected_canonical_utf8"]
    assert envelope.to_canonical_dict() == expected["envelope"]
    assert canonical_bytes(first.analysis_ref) == canonical_bytes(expected["ref"])
    assert canonical_sha256(first.analysis) == expected["payload_canonical_sha256"]

    source = fixture["source"]
    assert type(source) is dict
    assert canonical_bytes(completed.source_publication_ref) == canonical_bytes(
        source["publication_ref"]
    )
    assert completed.source_execution_result_hash == source["execution_result_hash"]
    assert first.trade_count == source["authoritative_fill_count"]
    assert first.simple_period_return == "0.02392"


def test_return_formula_rounding_null_and_decimal_wire_match_frozen_examples() -> None:
    fixture = _load_fixture()
    examples = fixture["worked_examples"]
    assert type(examples) is list
    for example in examples:
        assert type(example) is dict
        actual = _calculate_simple_period_return(
            _money(example["starting_equity"]),
            _money(example["ending_equity"]),
            (_money(example["net_external_cash_flow"]),),
        )
        assert actual == example["expected_simple_period_return"]
        if actual is not None:
            assert "e" not in actual.lower()
            assert actual != "-0"
            assert "." not in actual or not actual.endswith("0")
            assert len(actual.partition(".")[2]) <= 18

    assert _calculate_simple_period_return(
        _money("100"), _money("110"), (_money("10", "EUR"),)
    ) is None
    assert _calculate_simple_period_return(
        _money("100"),
        _money("110"),
        (_money("10", "EUR"), _money("-10", "EUR")),
    ) == "0.1"


def test_derivation_rejects_terminals_profile_forgery_and_unverified_case(
    tmp_path: Path,
) -> None:
    journey = completed_journey(tmp_path)
    finalized = journey.publication.finalized_result
    assert finalized is not None
    completed = VerifiedCompletedPublication(finalized, journey.case)
    profile_ref, profile = _profile()

    terminal = ArtifactRef("evidence_manifest", 1, "sha256:" + "1" * 64)
    with pytest.raises(TypeError, match="VerifiedCompletedPublication"):
        derive_backtest_analysis(terminal, profile_ref, profile)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="does not bind"):
        derive_backtest_analysis(
            completed,
            ArtifactRef("backtest_metric_profile", 1, "sha256:" + "2" * 64),
            profile,
        )
    with pytest.raises(TypeError, match="exact BacktestMetricProfile"):
        derive_backtest_analysis(completed, profile_ref, object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="does not bind completed execution result"):
        VerifiedCompletedPublication(
            finalized,
            replace(journey.case, case_key="other.case.v1"),
        )


def test_verified_completed_publication_is_one_frozen_reference_view(
    tmp_path: Path,
) -> None:
    journey = completed_journey(tmp_path)
    finalized = journey.publication.finalized_result
    assert finalized is not None
    completed = VerifiedCompletedPublication(finalized, journey.case)
    assert not hasattr(completed, "__dict__")
    assert completed.publication is finalized
    assert completed.execution_case is journey.case
    assert completed.execution_summary is (
        finalized.result.context.attempts.canonical_attempt.summary
    )
    with pytest.raises(FrozenInstanceError):
        completed.publication = finalized  # type: ignore[misc]
