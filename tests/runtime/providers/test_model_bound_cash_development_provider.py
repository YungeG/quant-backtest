from __future__ import annotations

from dataclasses import fields, replace
from inspect import Parameter, signature
from pathlib import Path

import pytest

import crypto_quant_backtest as backtest
from crypto_quant_domain import (
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
)
from crypto_quant_trading import OrderCapabilitySet
from tests.runtime.providers.test_cash_development_provider import (
    _Cas,
    _inputs,
    _intent,
    _reader,
)

_MODEL_KEY = "alpha.primary"
_MODEL_PHASE = TimelinePhase(70, "model_availability")


def _hash(marker: str) -> str:
    return "sha256:" + marker * 64


def _artifact(
    revision_id: str,
    *,
    model_key: str = _MODEL_KEY,
    available_at: int = 90,
    source_sequence: int = 1,
    supersedes_revision_id: str | None = None,
    marker: str = "a",
) -> backtest.ModelArtifactRef:
    return backtest.ModelArtifactRef(
        model_key=model_key,
        model_hash=_hash(marker),
        training_data_hash=_hash("b"),
        training_start=UtcInstant(0),
        training_end=UtcInstant(50),
        training_code_hash=_hash("c"),
        feature_schema_hash=_hash("d"),
        available_at=SimulationInstant(
            UtcInstant(available_at),
            _MODEL_PHASE,
            SourceSequence(source_sequence),
        ),
        revision_id=revision_id,
        supersedes_revision_id=supersedes_revision_id,
    )


def _timeline(
    decision_at: int = 100,
    artifacts: tuple[backtest.ModelArtifactRef, ...] | None = None,
) -> backtest.ModelRevisionTimeline:
    return backtest.ModelRevisionTimeline(
        model_key=_MODEL_KEY,
        decision_instant=SimulationInstant(
            UtcInstant(decision_at), _MODEL_PHASE, SourceSequence(9)
        ),
        artifacts=(_artifact("v1"),) if artifacts is None else artifacts,
    )


def _prepared(tmp_path, *, timeline=None, provider_inputs=None, store=None):
    selected_timeline = _timeline() if timeline is None else timeline
    selected = selected_timeline.select()
    assert selected is not None
    cas = _Cas() if store is None else store
    prepared = backtest.prepare_model_bound_cash_development_backtest(
        request_intent=_intent(),
        provider_inputs=_inputs() if provider_inputs is None else provider_inputs,
        model_timeline=selected_timeline,
        expected_model_key=selected.model_key,
        expected_artifact_ref_hash=selected.artifact_ref_hash,
        artifact_reader=cas,
        artifact_publisher=cas,
        market_reader=_reader(),
        publication_root=tmp_path,
    )
    return prepared, cas


def test_model_bound_public_preparation_is_narrow_and_additive(tmp_path) -> None:
    for name in (
        "ModelPreparationFailure",
        "ModelRequestBinding",
        "PreparedModelBoundBacktestExecution",
        "prepare_model_bound_cash_development_backtest",
    ):
        assert name in backtest.__all__

    assert tuple(field.name for field in fields(backtest.ModelRequestBinding)) == (
        "strategy_id",
        "input_name",
        "model_key",
        "timeline_hash",
        "artifact_ref_hash",
    )
    assert tuple(
        field.name for field in fields(backtest.PreparedModelBoundBacktestExecution)
    ) == (
        "request_ref",
        "semantic_run_id",
        "execution_request",
        "runtime",
        "model_binding",
    )
    parameters = tuple(
        signature(backtest.prepare_model_bound_cash_development_backtest).parameters.values()
    )
    assert tuple(parameter.name for parameter in parameters) == (
        "request_intent",
        "provider_inputs",
        "model_timeline",
        "expected_model_key",
        "expected_artifact_ref_hash",
        "artifact_reader",
        "artifact_publisher",
        "market_reader",
        "publication_root",
    )
    assert all(parameter.kind is Parameter.KEYWORD_ONLY for parameter in parameters)

    ordinary_store = _Cas()
    ordinary = backtest.prepare_cash_development_backtest(
        request_intent=_intent(),
        provider_inputs=_inputs(),
        artifact_reader=ordinary_store,
        artifact_publisher=ordinary_store,
        market_reader=_reader(),
        publication_root=tmp_path / "ordinary",
    )
    assert ordinary.execution_request.request.model_binding is None
    assert "model_binding" not in ordinary.execution_request.request.to_canonical_dict()


def test_completed_model_bound_run_persists_request_and_engine_binding(tmp_path) -> None:
    prepared, store = _prepared(tmp_path)

    publication_ref = prepared.runtime.run(prepared.execution_request)
    repeated = prepared.runtime.run(prepared.execution_request)
    verified = backtest.BacktestEvidenceRepository(reader=store).load_completed(
        publication_ref
    )
    request = prepared.execution_request.request
    request_envelope = store.by_ref[prepared.request_ref.artifact_ref]

    assert repeated == publication_ref
    assert request.model_binding == prepared.model_binding
    assert prepared.model_binding.input_name == "primary_model"
    assert prepared.model_binding.strategy_id == _inputs().strategy_id
    assert canonical_bytes(request_envelope.payload) == canonical_bytes(request)
    assert verified.semantic_run_id == prepared.semantic_run_id
    assert verified.engine_context.model_binding == prepared.model_binding
    assert (
        verified.engine_context.model_binding.artifact_ref_hash
        == prepared.model_binding.artifact_ref_hash
    )


def test_model_bound_public_module_exposes_no_loader_or_training_abi() -> None:
    source = (
        Path(backtest.__file__).parent / "cash_development_provider.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "Protocol",
        "Callable",
        "load_model",
        "model_bytes",
        "pickle",
        "joblib",
        "torch",
        "tensorflow",
        "sklearn",
        "fit(",
        "train(",
        "registry_handle",
    ):
        assert forbidden not in source


def test_blocked_model_bound_run_retains_the_same_request_binding(tmp_path) -> None:
    inputs = _inputs()
    original = inputs.order_capabilities
    no_market = OrderCapabilitySet.create(
        capability_set_key=original.capability_set_key,
        capability_set_version=original.capability_set_version,
        style_capabilities=(),
        supports_reduce_only=original.supports_reduce_only,
        supported_position_effects=original.supported_position_effects,
        declared_capability_keys=original.declared_capability_keys,
    )
    prepared, store = _prepared(
        tmp_path,
        provider_inputs=replace(inputs, order_capabilities=no_market),
    )

    terminal_ref = prepared.runtime.run(prepared.execution_request)
    terminal = backtest.BacktestEvidenceRepository(reader=store).load_terminal(
        terminal_ref
    )

    assert terminal.status.value == "BLOCKED"
    assert prepared.execution_request.request.model_binding == prepared.model_binding
    assert prepared.semantic_run_id.startswith("run_")


def test_revision_identity_changes_runs_but_hidden_future_revision_does_not(tmp_path) -> None:
    first = _artifact("v1")
    future = _artifact(
        "v2",
        available_at=150,
        source_sequence=2,
        supersedes_revision_id="v1",
        marker="e",
    )
    before = _timeline(100, (first,))
    before_with_future = _timeline(100, (first, future))
    after = _timeline(200, (first, future))

    prepared_before, _ = _prepared(tmp_path / "before", timeline=before)
    prepared_hidden, _ = _prepared(tmp_path / "hidden", timeline=before_with_future)
    prepared_after, _ = _prepared(tmp_path / "after", timeline=after)

    assert before.timeline_hash == before_with_future.timeline_hash
    assert prepared_before.request_ref == prepared_hidden.request_ref
    assert prepared_before.semantic_run_id == prepared_hidden.semantic_run_id
    assert prepared_before.request_ref != prepared_after.request_ref
    assert prepared_before.semantic_run_id != prepared_after.semantic_run_id
    assert (
        prepared_before.model_binding.artifact_ref_hash
        != prepared_after.model_binding.artifact_ref_hash
    )


@pytest.mark.parametrize(
    ("timeline", "model_key", "artifact_hash", "code"),
    (
        (
            backtest.ModelRevisionTimeline(
                model_key=_MODEL_KEY,
                decision_instant=SimulationInstant(
                    UtcInstant(100), _MODEL_PHASE, SourceSequence(9)
                ),
                artifacts=(),
            ),
            _MODEL_KEY,
            _hash("a"),
            "MODEL_ARTIFACT_UNAVAILABLE",
        ),
        (_timeline(), "wrong.key", _artifact("v1").artifact_ref_hash, "MODEL_BINDING_MISMATCH"),
        (_timeline(), _MODEL_KEY, _hash("f"), "MODEL_BINDING_MISMATCH"),
        (object(), _MODEL_KEY, _hash("a"), "MODEL_TIMELINE_INVALID"),
    ),
)
def test_invalid_or_substituted_model_fails_before_request_or_attempt(
    tmp_path,
    timeline,
    model_key: str,
    artifact_hash: str,
    code: str,
) -> None:
    store = _Cas()

    with pytest.raises(backtest.ModelPreparationFailure) as caught:
        backtest.prepare_model_bound_cash_development_backtest(
            request_intent=_intent(),
            provider_inputs=_inputs(),
            model_timeline=timeline,
            expected_model_key=model_key,
            expected_artifact_ref_hash=artifact_hash,
            artifact_reader=store,
            artifact_publisher=store,
            market_reader=_reader(),
            publication_root=tmp_path,
        )

    assert caught.value.code == code
    assert store.by_ref == {}
    assert not (tmp_path / "runs").exists()
