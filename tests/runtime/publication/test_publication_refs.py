from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import tempfile
from pathlib import Path
from typing import Any, get_args

import pytest

import crypto_quant_backtest as backtest_runtime
from crypto_quant_backtest import (
    BacktestCanonicalPublicationRef,
    RunPublicationRef,
)
from crypto_quant_domain import ArtifactRef, canonical_bytes, canonical_sha256
from tests.runtime.integration._fixtures import completed_journey, mismatch_journey


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "tests/fixtures/runtime/bt-gap04-publication-ref-v1.json"
CONSUMER_FIXTURE = ROOT.parent / "tests/contracts/backtest-consumer-port-v1.json"
G07_FIXTURE = ROOT / "tests/fixtures/runtime/g07-auditable-synthetic-run-v1.json"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid fixture: {path}") from error
    if type(decoded) is not dict:
        raise AssertionError(f"fixture must be object: {path}")
    return decoded


def _artifact_ref(raw: dict[str, Any]) -> ArtifactRef:
    if raw.get("type") != "artifact_ref":
        raise AssertionError("expected artifact_ref object")
    return ArtifactRef(
        artifact_type=raw["artifact_type"],
        schema_version=raw["schema_version"],
        content_hash=raw["content_hash"],
    )


def _case(contract: dict[str, Any], case_id: str) -> dict[str, Any]:
    matches = [case for case in contract["cases"] if case["case_id"] == case_id]
    assert len(matches) == 1
    return matches[0]


def test_completed_publication_ref_matches_platform_wire_and_golden() -> None:
    fixture = _load_json(FIXTURE_PATH)["completed"]
    value = BacktestCanonicalPublicationRef.from_artifact_ref(
        _artifact_ref(fixture["ref"]["artifact_ref"])
    )

    assert value.to_artifact_ref() is value.artifact_ref
    assert json.loads(canonical_bytes(value).decode()) == fixture["ref"]
    assert canonical_bytes(value) == fixture["expected_canonical_utf8"].encode()
    assert canonical_sha256(value) == fixture["expected_canonical_sha256"]

    consumer = _case(_load_json(CONSUMER_FIXTURE), "adverse_completed")
    assert consumer["run"]["ref"] == fixture["ref"]
    assert consumer["completed"]["publication_ref"] == fixture["ref"]


def test_terminal_run_refs_remain_bare_artifact_refs() -> None:
    fixture = _load_json(FIXTURE_PATH)
    contract = _load_json(CONSUMER_FIXTURE)

    for entry in fixture["terminals"]:
        value = _artifact_ref(entry["ref"])
        consumer = _case(contract, f"terminal_{entry['status'].lower()}")

        assert value.to_canonical_dict() == entry["ref"]
        assert canonical_bytes(value) == entry["expected_canonical_utf8"].encode()
        assert canonical_sha256(value) == entry["expected_canonical_sha256"]
        assert consumer["run"]["ref"] == entry["ref"]
        assert consumer["terminal"] == {
            "status": entry["status"],
            "durable_evidence_ref": entry["ref"],
        }
        assert set(entry["ref"]) == {
            "type",
            "artifact_type",
            "schema_version",
            "content_hash",
        }


def test_run_publication_ref_is_exactly_one_direct_ref_union() -> None:
    assert get_args(RunPublicationRef) == (
        BacktestCanonicalPublicationRef,
        ArtifactRef,
    )
    assert "RunPublicationRef" in backtest_runtime.__all__
    assert "BacktestCanonicalPublicationRef" in backtest_runtime.__all__
    assert not hasattr(backtest_runtime, "TerminalPublicationRef")
    assert not hasattr(backtest_runtime, "RunPublicationOutcome")


def test_completed_publication_ref_rejects_forgery_and_is_frozen() -> None:
    fixture = _load_json(FIXTURE_PATH)["completed"]["ref"]["artifact_ref"]
    value = BacktestCanonicalPublicationRef(_artifact_ref(fixture))

    assert not hasattr(value, "__dict__")
    with pytest.raises(FrozenInstanceError):
        value.artifact_ref = _artifact_ref(fixture)  # type: ignore[misc]
    with pytest.raises(TypeError, match="ArtifactRef"):
        BacktestCanonicalPublicationRef("not-an-artifact-ref")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="canonical_publication_manifest"):
        BacktestCanonicalPublicationRef(
            ArtifactRef("evidence_manifest", 1, "sha256:" + "0" * 64)
        )
    with pytest.raises(ValueError, match="schema_version must be 1"):
        BacktestCanonicalPublicationRef(
            ArtifactRef("canonical_publication_manifest", 2, "sha256:" + "0" * 64)
        )


def test_g07_finalized_result_and_evaluation_wires_remain_frozen() -> None:
    fixture = _load_json(G07_FIXTURE)
    completed = completed_journey(Path(tempfile.mkdtemp(prefix="bt-gap04-completed-")))
    mismatch = mismatch_journey(Path(tempfile.mkdtemp(prefix="bt-gap04-mismatch-")))
    finalized_result = completed.publication.finalized_result
    finalized_evaluation = mismatch.publication.finalized_evaluation
    assert finalized_result is not None
    assert finalized_evaluation is not None

    assert finalized_result.to_canonical_dict() == fixture["completed"]["finalized_result"]
    assert (
        finalized_result.result.result_hash
        == fixture["completed"]["finalized_result"]["result_hash"]
    )
    assert canonical_sha256(finalized_result.to_canonical_dict()) == canonical_sha256(
        fixture["completed"]["finalized_result"]
    )
    assert finalized_evaluation.to_canonical_dict() == fixture["mismatch"][
        "finalized_evaluation"
    ]
    assert (
        finalized_evaluation.record.record_hash
        == fixture["mismatch"]["finalized_evaluation"]["evaluation_record_hash"]
    )
    assert canonical_sha256(
        finalized_evaluation.to_canonical_dict()
    ) == canonical_sha256(fixture["mismatch"]["finalized_evaluation"])
