from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
import hashlib
from inspect import Parameter, signature
import json
from pathlib import Path
from typing import get_type_hints

import pytest

import crypto_quant_backtest
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)
from tests.runtime.resolution._fixtures import build_manifest
from tests.runtime.runner._fixtures import resolved_request_and_case

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/runtime/bt-gap02b-execution-input-bundle-v1.json"
)
FIXTURE_SHA256 = "09578ac47f997bc4bf55119d31e97dbcad3eb71e90d93a5ef7c8e6669bd66be2"


def _fixture() -> dict[str, object]:
    try:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid BT-GAP-02B fixture: {error}")


def _public() -> tuple[type, object]:
    execution_request = getattr(crypto_quant_backtest, "BacktestExecutionRequest", None)
    materializer = getattr(
        crypto_quant_backtest, "materialize_execution_input_bundle", None
    )
    assert execution_request is not None, "BT-GAP-02B RED: missing BacktestExecutionRequest"
    assert materializer is not None, (
        "BT-GAP-02B RED: missing materialize_execution_input_bundle"
    )
    return execution_request, materializer


def test_execution_input_fixture_is_independent_and_self_consistent() -> None:
    fixture = _fixture()
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256

    envelope = ArtifactEnvelope(**fixture["bundle"]["envelope"])
    ref_fields = dict(fixture["bundle"]["ref"])
    assert ref_fields.pop("type") == "artifact_ref"
    ref = ArtifactRef(**ref_fields)
    assert ArtifactRef.from_envelope(envelope) == ref
    assert canonical_bytes(envelope).decode() == fixture["bundle"]["expected_canonical_utf8"]
    assert canonical_sha256(envelope) == fixture["bundle"]["expected_canonical_sha256"]

    request = fixture["materializer_arguments"]["request"]
    assert canonical_bytes(request).decode() == fixture["request_identity"][
        "expected_canonical_utf8"
    ]
    assert canonical_sha256(request) == fixture["request_identity"][
        "expected_request_hash"
    ]

    transport = fixture["transport"]["value"]
    assert canonical_bytes(transport).decode() == fixture["transport"][
        "expected_canonical_utf8"
    ]
    assert canonical_sha256(transport) == fixture["transport"][
        "expected_canonical_sha256"
    ]


def test_execution_input_fixture_preserves_repository_independence() -> None:
    fixture = _fixture()
    transport = fixture["transport"]["value"]
    payload = fixture["bundle"]["envelope"]["payload"]
    template = payload["initial_financial_state_template"]

    assert set(transport) == {
        "type",
        "schema_version",
        "request",
        "execution_input_bundle_ref",
    }
    assert not set(fixture["forbidden_transport_fields"]) & set(transport)
    assert not set(fixture["forbidden_bundle_fields"]) & set(payload)
    assert "events" not in payload
    assert payload["target_stream_key"] in payload["timeline_stream_keys"]

    assert template["type"] == "backtest_initial_financial_state_template"
    assert "journal_state_hash" not in template["initial_snapshot_template"]
    assert "settlement_book_hash" not in template
    for entry in template["journal_entry_templates"]:
        assert entry["type"] == "accounting_journal_entry"
        assert "identity_binding_key" in entry
        assert "journal_entry_id" not in entry


def test_execution_input_public_surface_and_signatures_are_exact() -> None:
    execution_request, materializer = _public()
    assert execution_request is crypto_quant_backtest.BacktestExecutionRequest
    assert materializer is crypto_quant_backtest.materialize_execution_input_bundle
    assert "BacktestExecutionRequest" in crypto_quant_backtest.__all__
    assert "materialize_execution_input_bundle" in crypto_quant_backtest.__all__

    field_names = tuple(field.name for field in fields(execution_request))
    expected_field_names = (
        "schema_version",
        "request",
        "execution_input_bundle_ref",
    )
    assert field_names == expected_field_names

    parameters = tuple(signature(materializer).parameters.values())
    parameter_names = tuple(parameter.name for parameter in parameters)
    expected_parameter_names = (
        "request",
        "build_artifact_manifest",
        "execution_case_semantic_spec",
        "timeline_stream_keys",
        "target_stream_key",
        "timeline_batch_size",
        "initial_financial_state_template",
    )
    assert parameter_names == expected_parameter_names
    assert all(parameter.kind is Parameter.KEYWORD_ONLY for parameter in parameters)

    hints = get_type_hints(materializer)
    assert hints["request"] is crypto_quant_backtest.BacktestRequest
    assert hints["build_artifact_manifest"] is crypto_quant_backtest.BuildArtifactManifest
    assert hints["execution_case_semantic_spec"] is crypto_quant_backtest.ExecutionCaseSemanticSpec
    assert hints["timeline_stream_keys"] == tuple[str, ...]
    assert hints["target_stream_key"] is str
    assert hints["timeline_batch_size"] is int
    assert hints["return"] is ArtifactEnvelope


def test_materializer_reproduces_frozen_bundle_and_transport_without_changing_request_v1() -> None:
    execution_request, materializer = _public()
    fixture = _fixture()
    resolved, case = resolved_request_and_case()
    manifest = build_manifest()
    request_bytes = canonical_bytes(resolved.request)

    envelope = materializer(
        request=resolved.request,
        build_artifact_manifest=manifest,
        execution_case_semantic_spec=case.semantic_spec,
        timeline_stream_keys=case.timeline.stream_keys,
        target_stream_key=case.target_stream.stream_key,
        timeline_batch_size=case.timeline_batch_size,
        initial_financial_state_template=fixture["materializer_arguments"][
            "initial_financial_state_template"
        ],
    )
    assert canonical_bytes(envelope).decode() == fixture["bundle"][
        "expected_canonical_utf8"
    ]

    transport = execution_request(
        schema_version=1,
        request=resolved.request,
        execution_input_bundle_ref=ArtifactRef.from_envelope(envelope),
    )
    assert canonical_bytes(transport).decode() == fixture["transport"][
        "expected_canonical_utf8"
    ]
    assert canonical_bytes(resolved.request) == request_bytes
    assert resolved.request.request_hash == fixture["request_identity"][
        "expected_request_hash"
    ]


def test_materializer_rejects_non_base_initial_journal_entries() -> None:
    _, materializer = _public()
    fixture = _fixture()
    resolved, case = resolved_request_and_case()
    template = deepcopy(
        fixture["materializer_arguments"]["initial_financial_state_template"]
    )
    template["journal_entry_templates"][0]["type"] = "linear_funding_journal_entry"

    with pytest.raises(ValueError, match="base AccountingJournalEntry"):
        materializer(
            request=resolved.request,
            build_artifact_manifest=build_manifest(),
            execution_case_semantic_spec=case.semantic_spec,
            timeline_stream_keys=case.timeline.stream_keys,
            target_stream_key=case.target_stream.stream_key,
            timeline_batch_size=case.timeline_batch_size,
            initial_financial_state_template=template,
        )


def test_execution_request_rejects_wrong_bundle_ref_without_io() -> None:
    execution_request, _ = _public()
    resolved, _ = resolved_request_and_case()
    wrong_ref = ArtifactRef(
        artifact_type="evidence_manifest",
        schema_version=1,
        content_hash="sha256:" + "0" * 64,
    )

    with pytest.raises(ValueError, match="backtest_execution_input_bundle@1"):
        execution_request(
            schema_version=1,
            request=resolved.request,
            execution_input_bundle_ref=wrong_ref,
        )
