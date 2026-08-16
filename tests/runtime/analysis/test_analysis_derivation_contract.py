from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json
from pathlib import Path

import pytest

from crypto_quant_backtest import (
    BacktestAnalysisRuntime,
    BacktestMetricProfile,
    VerifiedBacktestAnalysis,
    VerifiedCompletedPublication,
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
_FIXTURE_SHA256 = "f988ca0d779c68a0f05e5b06caf20c68b578a6c1ff7210307816f0e4835b4f2e"


class _RecordingPublisher:
    def __init__(self, returned_ref: ArtifactRef | None = None) -> None:
        self.returned_ref = returned_ref
        self.envelopes: list[ArtifactEnvelope] = []

    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        self.envelopes.append(envelope)
        return self.returned_ref or ArtifactRef.from_envelope(envelope)


class _FailingPublisher:
    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        raise RuntimeError("retention unavailable")


def _load_fixture() -> dict[str, object]:
    value = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert type(value) is dict
    return value


def _profile_ref() -> ArtifactRef:
    profile = BacktestMetricProfile("simple_period_return.fill_count.v1", 1)
    return ArtifactRef.from_envelope(
        ArtifactEnvelope.create("backtest_metric_profile", 1, profile)
    )


def _money(value: str, currency: str = "USD") -> Money:
    sign = -1 if value.startswith("-") else 1
    unsigned = value.removeprefix("-")
    whole, dot, fraction = unsigned.partition(".")
    return Money(
        sign * int(whole + fraction),
        Scale(len(fraction) if dot else 0),
        currency,
    )


def test_completed_derivation_publishes_frozen_artifact_and_returns_only_ref(
    tmp_path: Path,
) -> None:
    fixture = _load_fixture()
    assert sha256(_FIXTURE.read_bytes()).hexdigest() == _FIXTURE_SHA256
    assert fixture["fixture_id"] == "bt-gap05-completed-analysis-v1"
    journey = completed_journey(tmp_path)
    finalized = journey.publication.finalized_result
    assert finalized is not None
    completed = VerifiedCompletedPublication(finalized, journey.case)
    publisher = _RecordingPublisher()

    analysis_ref = BacktestAnalysisRuntime(publisher).derive(completed, _profile_ref())

    expected = fixture["derived"]
    assert type(expected) is dict
    assert not isinstance(analysis_ref, VerifiedBacktestAnalysis)
    assert not hasattr(analysis_ref, "analysis")
    assert expected["runtime_return"] == expected["ref"]
    assert canonical_bytes(analysis_ref) == canonical_bytes(expected["runtime_return"])
    assert len(publisher.envelopes) == 1
    envelope = publisher.envelopes[0]
    assert canonical_bytes(envelope).decode() == expected["expected_canonical_utf8"]
    assert envelope.to_canonical_dict() == expected["envelope"]
    assert envelope.payload == expected["stored_payload"]
    assert analysis_ref.artifact_ref == ArtifactRef.from_envelope(envelope)
    assert canonical_sha256(envelope.payload) == expected["payload_canonical_sha256"]

    source = fixture["source"]
    assert type(source) is dict
    assert canonical_bytes(completed.source_publication_ref) == canonical_bytes(
        source["publication_ref"]
    )
    assert completed.source_execution_result_hash == source["execution_result_hash"]
    assert envelope.payload["trade_count"] == source["authoritative_fill_count"]
    assert envelope.payload["simple_period_return"] == "0.02392"


def test_derivation_replay_performs_idempotent_put_and_returns_same_ref(
    tmp_path: Path,
) -> None:
    journey = completed_journey(tmp_path)
    finalized = journey.publication.finalized_result
    assert finalized is not None
    completed = VerifiedCompletedPublication(finalized, journey.case)
    publisher = _RecordingPublisher()
    runtime = BacktestAnalysisRuntime(publisher)
    profile_ref = _profile_ref()

    first = runtime.derive(completed, profile_ref)
    second = runtime.derive(completed, profile_ref)

    assert first == second
    assert len(publisher.envelopes) == 2
    assert publisher.envelopes[0] == publisher.envelopes[1]


def test_publisher_failures_and_wrong_returned_ref_are_not_fabricated(
    tmp_path: Path,
) -> None:
    journey = completed_journey(tmp_path)
    finalized = journey.publication.finalized_result
    assert finalized is not None
    completed = VerifiedCompletedPublication(finalized, journey.case)
    profile_ref = _profile_ref()

    with pytest.raises(RuntimeError, match="retention unavailable"):
        BacktestAnalysisRuntime(_FailingPublisher()).derive(completed, profile_ref)

    wrong = ArtifactRef("backtest_analysis", 1, "sha256:" + "3" * 64)
    with pytest.raises(ValueError, match="returned ref does not bind envelope"):
        BacktestAnalysisRuntime(_RecordingPublisher(wrong)).derive(
            completed, profile_ref
        )


@pytest.mark.parametrize("bad_ref", [
    ArtifactRef("backtest_metric_profile", 1, "sha256:" + "2" * 64),
    ArtifactRef("evidence_manifest", 1, "sha256:" + "1" * 64),
])
def test_derivation_rejects_profile_mismatch(bad_ref: ArtifactRef, tmp_path: Path) -> None:
    journey = completed_journey(tmp_path)
    finalized = journey.publication.finalized_result
    assert finalized is not None
    completed = VerifiedCompletedPublication(finalized, journey.case)

    with pytest.raises(ValueError, match="accepted metric profile"):
        BacktestAnalysisRuntime(_RecordingPublisher()).derive(completed, bad_ref)


def test_derivation_rejects_terminals_and_unverified_case(tmp_path: Path) -> None:
    journey = completed_journey(tmp_path)
    finalized = journey.publication.finalized_result
    assert finalized is not None
    completed = VerifiedCompletedPublication(finalized, journey.case)
    terminal = ArtifactRef("evidence_manifest", 1, "sha256:" + "1" * 64)

    with pytest.raises(TypeError, match="VerifiedCompletedPublication"):
        BacktestAnalysisRuntime(_RecordingPublisher()).derive(terminal, _profile_ref())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ArtifactRef"):
        BacktestAnalysisRuntime(_RecordingPublisher()).derive(completed, object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="does not bind completed execution result"):
        VerifiedCompletedPublication(
            finalized,
            replace(journey.case, case_key="other.case.v1"),
        )


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


def test_withdrawal_transfer_and_mixed_currency_cash_flow_behavior() -> None:
    assert _calculate_simple_period_return(
        _money("100"), _money("90"), (_money("-20"),)
    ) == "0.1"
    assert _calculate_simple_period_return(
        _money("100"), _money("110"), (_money("5"),)
    ) == "0.05"
    assert _calculate_simple_period_return(
        _money("100"), _money("110"), (_money("5", "EUR"),)
    ) is None
    assert _calculate_simple_period_return(
        _money("100"), _money("110"), (_money("5", "EUR"), _money("-5", "EUR"))
    ) == "0.1"


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
