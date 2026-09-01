from __future__ import annotations

import json
import unicodedata
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import crypto_quant_domain as domain
from crypto_quant_market_data import MarketBundleReader

from .analysis import AnalysisArtifactRef, AnalysisArtifactRefV2
from .analysis_derivation import BacktestAnalysisRuntime
from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .binance_usdm_tradifi_preparation import (
    BinanceUsdmTradifiBarRequestIntent,
    BinanceUsdmTradifiProviderInputs,
)
from .binance_usdm_tradifi_provider import (
    BinanceUsdmTradifiBarBacktestFailure,
    prepare_binance_usdm_tradifi_bar_backtest,
)
from .cash_development_provider import PreparedBacktestExecution
from .evidence_repository import BacktestEvidenceRepository
from .publication_refs import (
    BacktestCanonicalPublicationRef,
    BacktestCanonicalPublicationRefV2,
)
from .verified_publications import (
    VerifiedCompletedPublicationV3,
    VerifiedResearchCompletedPublicationV1,
)


def _canonical_text(name: str, value: object) -> str:
    if (
        type(value) is not str
        or not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be canonical non-empty text")
    return value


def _plain(value: object) -> dict[str, object]:
    decoded = json.loads(domain.canonical_bytes(value))
    if type(decoded) is not dict:
        raise TypeError("canonical public value must encode as an object")
    return decoded


def _artifact_ref(
    value: object,
    *,
    artifact_type: str | None = None,
    schema_version: int | None = None,
) -> domain.ArtifactRef:
    if type(value) is not dict or set(value) != {
        "type",
        "artifact_type",
        "schema_version",
        "content_hash",
    }:
        raise TypeError("exact canonical ArtifactRef mapping required")
    if value["type"] != "artifact_ref":
        raise ValueError("artifact ref mapping type mismatch")
    ref = domain.ArtifactRef(
        value["artifact_type"], value["schema_version"], value["content_hash"]
    )
    if artifact_type is not None and ref.artifact_type != artifact_type:
        raise ValueError(f"artifact ref must target {artifact_type}")
    if schema_version is not None and ref.schema_version != schema_version:
        raise ValueError(f"artifact ref must target schema {schema_version}")
    return ref


def _nominal_ref(
    value: object,
    *,
    type_name: str,
    artifact_type: str,
    schema_version: int,
) -> domain.ArtifactRef:
    if type(value) is not dict or set(value) != {"type", "artifact_ref"}:
        raise TypeError(f"exact {type_name} mapping required")
    if value["type"] != type_name:
        raise ValueError(f"nominal ref must be {type_name}")
    return _artifact_ref(
        value["artifact_ref"],
        artifact_type=artifact_type,
        schema_version=schema_version,
    )


def _completed_view(
    completed: VerifiedResearchCompletedPublicationV1 | VerifiedCompletedPublicationV3,
) -> dict[str, object]:
    return _plain(
        {
            "publication_ref": completed.source_publication_ref,
            "semantic_run_id": completed.semantic_run_id,
            "execution_result_hash": completed.source_execution_result_hash,
            "result_grade": completed.result_grade.value,
        }
    )


class _PreparationFailed(RuntimeError):
    def __init__(self, failure: BinanceUsdmTradifiBarBacktestFailure) -> None:
        self.code = failure.code.value
        self.subject = failure.subject
        super().__init__(f"{self.code}:{self.subject}")


class PreparedTradifiTrial:
    """Opaque one-shot handle for a formally prepared TradFi Backtest trial."""

    __slots__ = ("_execution", "_operations", "_ran", "_request_ref")

    def __init__(
        self,
        execution: PreparedBacktestExecution,
        operations: BinanceUsdmTradifiBacktestOperations,
    ) -> None:
        if type(execution) is not PreparedBacktestExecution:
            raise TypeError("execution must be exact PreparedBacktestExecution")
        self._execution = execution
        self._operations = operations
        self._ran = False
        self._request_ref = _plain(execution.request_ref)

    @property
    def backtest_request_ref(self) -> dict[str, object]:
        return json.loads(json.dumps(self._request_ref))


class BinanceUsdmTradifiBacktestOperations:
    def __init__(
        self,
        *,
        intent_templates: Mapping[str, BinanceUsdmTradifiBarRequestIntent],
        provider_inputs: BinanceUsdmTradifiProviderInputs,
        artifact_reader: ArtifactEnvelopeReader,
        artifact_publisher: ArtifactEnvelopePublisher,
        market_reader: MarketBundleReader,
        publication_root: Path,
    ) -> None:
        if not isinstance(intent_templates, Mapping) or not intent_templates:
            raise TypeError("intent_templates must be a non-empty mapping")
        templates = dict(intent_templates)
        if any(
            _canonical_text("intent_key", key) != key
            or type(value) is not BinanceUsdmTradifiBarRequestIntent
            for key, value in templates.items()
        ):
            raise TypeError("intent_templates must contain exact public intents")
        if type(provider_inputs) is not BinanceUsdmTradifiProviderInputs:
            raise TypeError("provider_inputs must be exact BinanceUsdmTradifiProviderInputs")
        if not callable(getattr(artifact_reader, "read", None)) or not callable(
            getattr(artifact_publisher, "put", None)
        ):
            raise TypeError("artifact reader and publisher must satisfy structural ports")
        if not isinstance(publication_root, Path):
            raise TypeError("publication_root must be pathlib.Path")
        self._intent_templates = templates
        self._provider_inputs = provider_inputs
        self._artifact_reader = artifact_reader
        self._artifact_publisher = artifact_publisher
        self._market_reader = market_reader
        self._publication_root = publication_root
        self._repository = BacktestEvidenceRepository(artifact_reader)
        self._analysis_runtime = BacktestAnalysisRuntime(artifact_publisher)
        self._prepared_trials: set[PreparedTradifiTrial] = set()

    def prepare(
        self, request_spec: Mapping[str, object], experiment_id: str
    ) -> PreparedTradifiTrial:
        if type(request_spec) is not dict or set(request_spec) != {"intent_key"}:
            raise ValueError("request_spec must exact-cover intent_key")
        intent_key = _canonical_text("intent_key", request_spec["intent_key"])
        _canonical_text("experiment_id", experiment_id)
        try:
            template = self._intent_templates[intent_key]
        except KeyError as error:
            raise KeyError("unknown intent_key") from error
        prepared = prepare_binance_usdm_tradifi_bar_backtest(
            request_intent=replace(template, experiment_id=experiment_id),
            provider_inputs=self._provider_inputs,
            artifact_reader=self._artifact_reader,
            artifact_publisher=self._artifact_publisher,
            market_reader=self._market_reader,
            publication_root=self._publication_root,
        )
        if type(prepared) is BinanceUsdmTradifiBarBacktestFailure:
            raise _PreparationFailed(prepared)
        if type(prepared) is not PreparedBacktestExecution:
            raise TypeError("formal preparation returned an invalid result")
        trial = PreparedTradifiTrial(prepared, self)
        self._prepared_trials.add(trial)
        return trial

    def run_prepared(self, prepared: PreparedTradifiTrial) -> dict[str, object]:
        if type(prepared) is not PreparedTradifiTrial or prepared._operations is not self:
            raise TypeError("prepared must be an exact trial owned by these operations")
        if prepared._ran:
            raise RuntimeError("prepared trial has already run")
        if prepared not in self._prepared_trials:
            raise TypeError("prepared trial was not registered by these operations")
        self._prepared_trials.remove(prepared)
        prepared._ran = True
        return _plain(prepared._execution.runtime.run(prepared._execution.execution_request))

    def derive(
        self,
        completed_ref: Mapping[str, object],
        metric_profile_ref: Mapping[str, object],
    ) -> dict[str, object]:
        metric_ref = _artifact_ref(
            metric_profile_ref,
            artifact_type="backtest_metric_profile",
            schema_version=1,
        )
        published_metric_ref = self._analysis_runtime.publish_metric_profile()
        if metric_ref != published_metric_ref:
            raise ValueError("metric_profile_ref does not bind accepted metric profile")
        if type(completed_ref) is not dict:
            raise TypeError("completed_ref must be an exact nominal ref mapping")
        if completed_ref.get("type") == "backtest_canonical_publication_ref":
            completed = self._repository.load_completed_research_v1(
                BacktestCanonicalPublicationRef.from_artifact_ref(
                    _nominal_ref(
                        completed_ref,
                        type_name="backtest_canonical_publication_ref",
                        artifact_type="canonical_publication_manifest",
                        schema_version=1,
                    )
                )
            )
        elif completed_ref.get("type") == "backtest_canonical_publication_ref_v2":
            completed = self._repository.load_completed_v3(
                BacktestCanonicalPublicationRefV2.from_artifact_ref(
                    _nominal_ref(
                        completed_ref,
                        type_name="backtest_canonical_publication_ref_v2",
                        artifact_type="canonical_publication_manifest",
                        schema_version=2,
                    )
                )
            )
        else:
            raise ValueError("completed_ref has no accepted nominal version")
        return _plain(self._analysis_runtime.derive(completed, metric_ref))

    def load_completed(self, ref: Mapping[str, object]) -> dict[str, object]:
        nominal = BacktestCanonicalPublicationRef.from_artifact_ref(
            _nominal_ref(
                ref,
                type_name="backtest_canonical_publication_ref",
                artifact_type="canonical_publication_manifest",
                schema_version=1,
            )
        )
        return _completed_view(
            self._repository.load_completed_research_v1(nominal)
        )

    def load_completed_v3(self, ref: Mapping[str, object]) -> dict[str, object]:
        nominal = BacktestCanonicalPublicationRefV2.from_artifact_ref(
            _nominal_ref(
                ref,
                type_name="backtest_canonical_publication_ref_v2",
                artifact_type="canonical_publication_manifest",
                schema_version=2,
            )
        )
        completed = self._repository.load_completed_v3(nominal)
        return _plain(
            {
                **_completed_view(completed),
                "rebuild_verification_ref": completed.rebuild_verification_ref,
                "proof_publication_manifest_ref": (
                    completed.proof_publication_manifest_ref
                ),
            }
        )

    def load_terminal(self, ref: Mapping[str, object]) -> dict[str, object]:
        return _plain(self._repository.load_terminal(_artifact_ref(ref)))

    def load_analysis(self, ref: Mapping[str, object]) -> dict[str, object]:
        nominal = AnalysisArtifactRef(
            _nominal_ref(
                ref,
                type_name="analysis_artifact_ref",
                artifact_type="backtest_analysis",
                schema_version=1,
            )
        )
        return _plain(self._repository.load_analysis_research_v1(nominal))

    def load_analysis_v2(self, ref: Mapping[str, object]) -> dict[str, object]:
        nominal = AnalysisArtifactRefV2(
            _nominal_ref(
                ref,
                type_name="analysis_artifact_ref_v2",
                artifact_type="backtest_analysis",
                schema_version=2,
            )
        )
        return _plain(self._repository.load_analysis_v2(nominal))


__all__ = [
    "BinanceUsdmTradifiBacktestOperations",
    "PreparedTradifiTrial",
]
