from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable

import pytest

from crypto_quant_backtest import BacktestExecutionRequest
from crypto_quant_backtest.execution_inputs import (
    _ExecutionInputsHydrationFailureCode,
    _ExecutionInputsHydrationOutcome,
    _hydrate_execution_inputs,
)
from crypto_quant_domain import (
    ArtifactCatalogError,
    ArtifactEnvelope,
    ArtifactReadResult,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)
from tests.runtime.runner._fixtures import resolved_request_and_case

_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/runtime/bt-gap02b-execution-input-bundle-v1.json"
)


def _fixture() -> dict[str, object]:
    try:
        return json.loads(_FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid BT-GAP-02B fixture: {error}")


def _frozen_envelope() -> ArtifactEnvelope:
    return ArtifactEnvelope(**_fixture()["bundle"]["envelope"])


def _modified_envelope(modifier: Callable[[dict[str, object]], None]) -> ArtifactEnvelope:
    payload = deepcopy(_fixture()["bundle"]["envelope"]["payload"])
    modifier(payload)
    return ArtifactEnvelope.create("backtest_execution_input_bundle", 1, payload)


def _transport(envelope: ArtifactEnvelope) -> BacktestExecutionRequest:
    resolved, _ = resolved_request_and_case()
    return BacktestExecutionRequest(
        schema_version=1,
        request=resolved.request,
        execution_input_bundle_ref=ArtifactRef.from_envelope(envelope),
    )


def _hydrate(reader: object, request: object) -> _ExecutionInputsHydrationOutcome:
    _, case = resolved_request_and_case()
    return _hydrate_execution_inputs(
        reader,  # type: ignore[arg-type]
        request,  # type: ignore[arg-type]
        market_reader=case.timeline.reader,
    )


@dataclass(frozen=True, slots=True)
class _Reader:
    envelope: ArtifactEnvelope | None = None
    error: Exception | None = None

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        if self.error is not None:
            raise self.error
        if self.envelope is None:
            raise ArtifactCatalogError("missing")
        source_bytes = canonical_bytes(self.envelope)
        return ArtifactReadResult(
            envelope=self.envelope,
            artifact={"not": "semantic authority"},
            source_bytes=source_bytes,
            source_hash=canonical_sha256(self.envelope),
        )


def _assert_failure(
    outcome: _ExecutionInputsHydrationOutcome,
    code: _ExecutionInputsHydrationFailureCode,
) -> None:
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is code


def test_hydration_uses_source_bytes_not_structural_reader_artifact() -> None:
    envelope = _frozen_envelope()
    outcome = _hydrate(_Reader(envelope), _transport(envelope))

    assert outcome.failure is None
    assert outcome.result is not None
    assert outcome.result.build_artifact_manifest.manifest_hash == (
        _transport(envelope).request.build_artifact_manifest_hash
    )
    assert outcome.result.target_stream.stream_key == "targets"
    assert outcome.result.target_stream.target_stream_digest == (
        _transport(envelope).request.target_stream_digest
    )
    expected_stream_keys = ("bars.open", "targets")
    assert outcome.result.timeline_stream_keys == expected_stream_keys
    assert outcome.result.timeline_batch_size == 1


def test_malformed_transport_precedes_io() -> None:
    reader = _Reader(error=AssertionError("reader must not be called"))
    outcome = _hydrate(reader, object())
    _assert_failure(
        outcome,
        _ExecutionInputsHydrationFailureCode.MALFORMED_EXECUTION_REQUEST,
    )


def test_wrong_bundle_ref_precedes_io() -> None:
    resolved, _ = resolved_request_and_case()
    forged = object.__new__(BacktestExecutionRequest)
    object.__setattr__(forged, "schema_version", 1)
    object.__setattr__(forged, "request", resolved.request)
    object.__setattr__(
        forged,
        "execution_input_bundle_ref",
        ArtifactRef("evidence_manifest", 1, "sha256:" + "0" * 64),
    )
    reader = _Reader(error=AssertionError("reader must not be called"))
    outcome = _hydrate(reader, forged)
    _assert_failure(
        outcome,
        _ExecutionInputsHydrationFailureCode.WRONG_EXECUTION_INPUT_BUNDLE_REF,
    )


def test_unavailable_input_has_no_partial_value() -> None:
    envelope = _frozen_envelope()
    outcome = _hydrate(
        _Reader(error=ArtifactCatalogError("missing")),
        _transport(envelope),
    )
    _assert_failure(
        outcome,
        _ExecutionInputsHydrationFailureCode.EXECUTION_INPUT_UNAVAILABLE,
    )


def test_returned_envelope_ref_mismatch_is_tamper() -> None:
    requested = _frozen_envelope()
    returned = _modified_envelope(
        lambda payload: payload.__setitem__("timeline_batch_size", 2)
    )
    outcome = _hydrate(_Reader(returned), _transport(requested))
    _assert_failure(
        outcome,
        _ExecutionInputsHydrationFailureCode.EXECUTION_INPUT_TAMPERED,
    )


def test_forged_reader_source_is_tamper_before_payload_decode() -> None:
    envelope = _frozen_envelope()
    forged = object.__new__(ArtifactReadResult)
    object.__setattr__(forged, "envelope", envelope)
    object.__setattr__(forged, "artifact", {"forged": True})
    object.__setattr__(forged, "source_bytes", b"{}")
    object.__setattr__(forged, "source_hash", "sha256:" + "0" * 64)

    @dataclass(frozen=True, slots=True)
    class ForgedReader:
        def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
            return forged

    outcome = _hydrate(ForgedReader(), _transport(envelope))
    _assert_failure(
        outcome,
        _ExecutionInputsHydrationFailureCode.EXECUTION_INPUT_TAMPERED,
    )


def test_malformed_payload_is_decode_failure_after_ref_verification() -> None:
    envelope = _modified_envelope(lambda payload: payload.pop("build_artifact_manifest"))
    outcome = _hydrate(_Reader(envelope), _transport(envelope))
    _assert_failure(
        outcome,
        _ExecutionInputsHydrationFailureCode.EXECUTION_INPUT_DECODE_FAILED,
    )


def test_request_binding_mismatch_precedes_later_binding_defects() -> None:
    def mutate(payload: dict[str, object]) -> None:
        payload["request_hash"] = "sha256:" + "0" * 64
        payload["execution_case_semantic_spec"]["case_version"] = 2

    envelope = _modified_envelope(mutate)
    outcome = _hydrate(_Reader(envelope), _transport(envelope))
    _assert_failure(
        outcome,
        _ExecutionInputsHydrationFailureCode.REQUEST_BINDING_MISMATCH,
    )


def test_build_binding_mismatch() -> None:
    def mutate(payload: dict[str, object]) -> None:
        manifest = payload["build_artifact_manifest"]
        manifest["identity"]["build_key"] = "different.build.v1"
        manifest["manifest_hash"] = canonical_sha256(manifest["identity"])

    envelope = _modified_envelope(mutate)
    outcome = _hydrate(_Reader(envelope), _transport(envelope))
    _assert_failure(
        outcome,
        _ExecutionInputsHydrationFailureCode.BUILD_BINDING_MISMATCH,
    )


def test_target_binding_mismatch_precedes_semantic_hash_mismatch() -> None:
    def mutate(payload: dict[str, object]) -> None:
        payload["execution_case_semantic_spec"]["target_stream_digest"] = (
            "sha256:" + "0" * 64
        )

    envelope = _modified_envelope(mutate)
    outcome = _hydrate(_Reader(envelope), _transport(envelope))
    _assert_failure(
        outcome,
        _ExecutionInputsHydrationFailureCode.TARGET_BINDING_MISMATCH,
    )


def test_initial_state_binding_mismatch_precedes_semantic_hash_mismatch() -> None:
    def mutate(payload: dict[str, object]) -> None:
        snapshot = payload["initial_financial_state_template"][
            "initial_snapshot_template"
        ]
        snapshot["account_id"] = "account:other"

    envelope = _modified_envelope(mutate)
    outcome = _hydrate(_Reader(envelope), _transport(envelope))
    _assert_failure(
        outcome,
        _ExecutionInputsHydrationFailureCode.INITIAL_STATE_BINDING_MISMATCH,
    )


def test_execution_case_semantic_hash_mismatch_is_last() -> None:
    def mutate(payload: dict[str, object]) -> None:
        payload["execution_case_semantic_spec"]["case_version"] = 2

    envelope = _modified_envelope(mutate)
    outcome = _hydrate(_Reader(envelope), _transport(envelope))
    _assert_failure(
        outcome,
        _ExecutionInputsHydrationFailureCode.EXECUTION_CASE_SEMANTIC_HASH_MISMATCH,
    )
