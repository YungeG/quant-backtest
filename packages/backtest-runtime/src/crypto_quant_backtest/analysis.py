from __future__ import annotations

import re
from dataclasses import dataclass

from crypto_quant_domain import ArtifactEnvelope, ArtifactRef

from .integrity import ResultGrade
from .publication_refs import (
    BacktestCanonicalPublicationRef,
    BacktestCanonicalPublicationRefV2,
)

__all__ = [
    "AnalysisArtifactRef",
    "AnalysisArtifactRefV2",
    "BacktestAnalysis",
    "BacktestAnalysisV2",
    "BacktestMetricProfile",
    "VerifiedBacktestAnalysis",
    "VerifiedBacktestAnalysisV2",
]

_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?\Z")
_PROFILE_KEY = "simple_period_return.fill_count.v1"


def _artifact_ref(
    value: object,
    *,
    artifact_type: str,
    name: str,
) -> ArtifactRef:
    if type(value) is not ArtifactRef:
        raise TypeError(f"{name} must be exact ArtifactRef")
    rebuilt = ArtifactRef(
        value.artifact_type,
        value.schema_version,
        value.content_hash,
    )
    if rebuilt != value or rebuilt.artifact_type != artifact_type or rebuilt.schema_version != 1:
        raise ValueError(f"{name} must target {artifact_type}@1")
    return rebuilt


def _publication_ref(value: object) -> BacktestCanonicalPublicationRef:
    if type(value) is not BacktestCanonicalPublicationRef:
        raise TypeError(
            "source_publication_ref must be exact BacktestCanonicalPublicationRef"
        )
    artifact_ref = _artifact_ref(
        value.artifact_ref,
        artifact_type="canonical_publication_manifest",
        name="source_publication_ref.artifact_ref",
    )
    rebuilt = BacktestCanonicalPublicationRef.from_artifact_ref(artifact_ref)
    if rebuilt != value:
        raise ValueError("source_publication_ref is invalid")
    return rebuilt


def _artifact_ref_v2(
    value: object,
    *,
    artifact_type: str,
    name: str,
) -> ArtifactRef:
    if type(value) is not ArtifactRef:
        raise TypeError(f"{name} must be exact ArtifactRef")
    rebuilt = ArtifactRef(
        value.artifact_type,
        value.schema_version,
        value.content_hash,
    )
    if (
        rebuilt != value
        or rebuilt.artifact_type != artifact_type
        or rebuilt.schema_version != 2
    ):
        raise ValueError(f"{name} must target {artifact_type}@2")
    return rebuilt


def _publication_ref_v2(value: object) -> BacktestCanonicalPublicationRefV2:
    if type(value) is not BacktestCanonicalPublicationRefV2:
        raise TypeError(
            "source_publication_ref must be exact BacktestCanonicalPublicationRefV2"
        )
    artifact_ref = _artifact_ref_v2(
        value.artifact_ref,
        artifact_type="canonical_publication_manifest",
        name="source_publication_ref.artifact_ref",
    )
    rebuilt = BacktestCanonicalPublicationRefV2.from_artifact_ref(artifact_ref)
    if rebuilt != value:
        raise ValueError("source_publication_ref is invalid")
    return rebuilt


def _execution_result_hash(value: object) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError("source_execution_result_hash must be canonical sha256")
    return value


def _period_return(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        raise TypeError("simple_period_return must be str or None")
    if _DECIMAL.fullmatch(value) is None or value == "-0":
        raise ValueError("simple_period_return must be canonical ordinary decimal")
    if "." in value and len(value.rsplit(".", 1)[1]) > 18:
        raise ValueError("simple_period_return supports at most 18 fractional digits")
    return value


@dataclass(frozen=True, slots=True)
class AnalysisArtifactRef:
    artifact_ref: ArtifactRef

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "artifact_ref",
            _artifact_ref(
                self.artifact_ref,
                artifact_type="backtest_analysis",
                name="artifact_ref",
            ),
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "analysis_artifact_ref",
            "artifact_ref": self.artifact_ref,
        }


@dataclass(frozen=True, slots=True)
class AnalysisArtifactRefV2:
    artifact_ref: ArtifactRef

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "artifact_ref",
            _artifact_ref_v2(
                self.artifact_ref,
                artifact_type="backtest_analysis",
                name="artifact_ref",
            ),
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "analysis_artifact_ref_v2",
            "artifact_ref": self.artifact_ref,
        }


@dataclass(frozen=True, slots=True)
class BacktestMetricProfile:
    profile_key: str
    profile_version: int

    def __post_init__(self) -> None:
        if type(self.profile_key) is not str or self.profile_key != _PROFILE_KEY:
            raise ValueError(f"profile_key must be {_PROFILE_KEY}")
        if type(self.profile_version) is not int or self.profile_version != 1:
            raise ValueError("profile_version must be 1")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "backtest_metric_profile",
            "schema_version": 1,
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
            "valuation_schedule": "run_boundary_snapshots",
            "return_method": "simple_period_return",
            "annualization_basis": "not_applicable",
            "risk_free_source": "not_applicable",
            "cash_flow_treatment": "subtract_net_external_cash_flow",
            "drawdown_sampling": "not_applicable",
            "reporting_currency_source": "source_execution_result",
            "benchmark": "not_applicable",
            "trade_count_method": "authoritative_fill_count",
            "decimal_policy": {
                "maximum_fractional_digits": 18,
                "rounding": "half_even",
                "notation": "ordinary",
                "strip_trailing_fractional_zeros": True,
                "normalize_negative_zero": True,
            },
            "missing_metric_encoding": "null",
        }


@dataclass(frozen=True, slots=True)
class BacktestAnalysis:
    metric_profile_ref: ArtifactRef
    source_publication_ref: BacktestCanonicalPublicationRef
    source_execution_result_hash: str
    simple_period_return: str | None
    trade_count: int
    result_grade: ResultGrade

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "metric_profile_ref",
            _artifact_ref(
                self.metric_profile_ref,
                artifact_type="backtest_metric_profile",
                name="metric_profile_ref",
            ),
        )
        object.__setattr__(
            self,
            "source_publication_ref",
            _publication_ref(self.source_publication_ref),
        )
        _execution_result_hash(self.source_execution_result_hash)
        object.__setattr__(
            self,
            "simple_period_return",
            _period_return(self.simple_period_return),
        )
        if type(self.trade_count) is not int or self.trade_count < 0:
            raise ValueError("trade_count must be a nonnegative integer")
        if type(self.result_grade) is not ResultGrade:
            raise TypeError("result_grade must be exact ResultGrade")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "backtest_analysis",
            "schema_version": 1,
            "metric_profile_ref": self.metric_profile_ref,
            "source_publication_ref": self.source_publication_ref,
            "source_execution_result_hash": self.source_execution_result_hash,
            "simple_period_return": self.simple_period_return,
            "trade_count": self.trade_count,
            "result_grade": self.result_grade.value,
        }


@dataclass(frozen=True, slots=True)
class BacktestAnalysisV2:
    metric_profile_ref: ArtifactRef
    source_publication_ref: BacktestCanonicalPublicationRefV2
    source_execution_result_hash: str
    simple_period_return: str | None
    trade_count: int
    result_grade: ResultGrade

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "metric_profile_ref",
            _artifact_ref(
                self.metric_profile_ref,
                artifact_type="backtest_metric_profile",
                name="metric_profile_ref",
            ),
        )
        object.__setattr__(
            self,
            "source_publication_ref",
            _publication_ref_v2(self.source_publication_ref),
        )
        _execution_result_hash(self.source_execution_result_hash)
        object.__setattr__(
            self,
            "simple_period_return",
            _period_return(self.simple_period_return),
        )
        if type(self.trade_count) is not int or self.trade_count < 0:
            raise ValueError("trade_count must be a nonnegative integer")
        if type(self.result_grade) is not ResultGrade:
            raise TypeError("result_grade must be exact ResultGrade")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "backtest_analysis",
            "schema_version": 2,
            "metric_profile_ref": self.metric_profile_ref,
            "source_publication_ref": self.source_publication_ref,
            "source_execution_result_hash": self.source_execution_result_hash,
            "simple_period_return": self.simple_period_return,
            "trade_count": self.trade_count,
            "result_grade": self.result_grade.value,
        }


@dataclass(frozen=True, slots=True)
class VerifiedBacktestAnalysis:
    analysis_ref: AnalysisArtifactRef
    analysis: BacktestAnalysis

    def __post_init__(self) -> None:
        if type(self.analysis_ref) is not AnalysisArtifactRef:
            raise TypeError("analysis_ref must be exact AnalysisArtifactRef")
        rebuilt_ref = AnalysisArtifactRef(self.analysis_ref.artifact_ref)
        if rebuilt_ref != self.analysis_ref:
            raise ValueError("analysis_ref is invalid")
        if type(self.analysis) is not BacktestAnalysis:
            raise TypeError("analysis must be exact BacktestAnalysis")
        rebuilt_analysis = BacktestAnalysis(
            self.analysis.metric_profile_ref,
            self.analysis.source_publication_ref,
            self.analysis.source_execution_result_hash,
            self.analysis.simple_period_return,
            self.analysis.trade_count,
            self.analysis.result_grade,
        )
        if rebuilt_analysis != self.analysis:
            raise ValueError("analysis is invalid")
        expected_ref = ArtifactRef.from_envelope(
            ArtifactEnvelope.create("backtest_analysis", 1, self.analysis)
        )
        if self.analysis_ref.artifact_ref != expected_ref:
            raise ValueError("analysis_ref does not bind the analysis payload")

    @property
    def metric_profile_ref(self) -> ArtifactRef:
        return self.analysis.metric_profile_ref

    @property
    def source_publication_ref(self) -> BacktestCanonicalPublicationRef:
        return self.analysis.source_publication_ref

    @property
    def source_execution_result_hash(self) -> str:
        return self.analysis.source_execution_result_hash

    @property
    def simple_period_return(self) -> str | None:
        return self.analysis.simple_period_return

    @property
    def trade_count(self) -> int:
        return self.analysis.trade_count

    @property
    def result_grade(self) -> ResultGrade:
        return self.analysis.result_grade

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "analysis_ref": self.analysis_ref,
            "metric_profile_ref": self.metric_profile_ref,
            "source_publication_ref": self.source_publication_ref,
            "source_execution_result_hash": self.source_execution_result_hash,
            "simple_period_return": self.simple_period_return,
            "trade_count": self.trade_count,
            "result_grade": self.result_grade.value,
        }


@dataclass(frozen=True, slots=True)
class VerifiedBacktestAnalysisV2:
    analysis_ref: AnalysisArtifactRefV2
    analysis: BacktestAnalysisV2

    def __post_init__(self) -> None:
        if type(self.analysis_ref) is not AnalysisArtifactRefV2:
            raise TypeError("analysis_ref must be exact AnalysisArtifactRefV2")
        rebuilt_ref = AnalysisArtifactRefV2(self.analysis_ref.artifact_ref)
        if rebuilt_ref != self.analysis_ref:
            raise ValueError("analysis_ref is invalid")
        if type(self.analysis) is not BacktestAnalysisV2:
            raise TypeError("analysis must be exact BacktestAnalysisV2")
        rebuilt_analysis = BacktestAnalysisV2(
            self.analysis.metric_profile_ref,
            self.analysis.source_publication_ref,
            self.analysis.source_execution_result_hash,
            self.analysis.simple_period_return,
            self.analysis.trade_count,
            self.analysis.result_grade,
        )
        if rebuilt_analysis != self.analysis:
            raise ValueError("analysis is invalid")
        expected_ref = ArtifactRef.from_envelope(
            ArtifactEnvelope.create("backtest_analysis", 2, self.analysis)
        )
        if self.analysis_ref.artifact_ref != expected_ref:
            raise ValueError("analysis_ref does not bind the analysis payload")

    @property
    def metric_profile_ref(self) -> ArtifactRef:
        return self.analysis.metric_profile_ref

    @property
    def source_publication_ref(self) -> BacktestCanonicalPublicationRefV2:
        return self.analysis.source_publication_ref

    @property
    def source_execution_result_hash(self) -> str:
        return self.analysis.source_execution_result_hash

    @property
    def simple_period_return(self) -> str | None:
        return self.analysis.simple_period_return

    @property
    def trade_count(self) -> int:
        return self.analysis.trade_count

    @property
    def result_grade(self) -> ResultGrade:
        return self.analysis.result_grade

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "analysis_ref": self.analysis_ref,
            "metric_profile_ref": self.metric_profile_ref,
            "source_publication_ref": self.source_publication_ref,
            "source_execution_result_hash": self.source_execution_result_hash,
            "simple_period_return": self.simple_period_return,
            "trade_count": self.trade_count,
            "result_grade": self.result_grade.value,
        }
