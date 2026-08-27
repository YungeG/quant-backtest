"""Public V2-only preparation for Binance USD-M TradFi bar backtests."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import crypto_quant_domain as domain
from crypto_quant_market_data import MarketBundleReader

from .artifact_envelope_reader import ArtifactEnvelopeReader
from .binance_usdm_tradifi_case_planner import (
    BinanceUsdmTradifiCasePlanningResult,
    plan_binance_usdm_tradifi_case_v1,
)
from .binance_usdm_tradifi_case_planner import (
    _trusted_result as _trusted_case_planning_result,
)
from .binance_usdm_tradifi_preparation import (
    BinanceUsdmTradifiBarRequestIntent,
    BinanceUsdmTradifiPreparationResult,
    BinanceUsdmTradifiProviderInputs,
    resolve_binance_usdm_tradifi_preparation_authority_v2,
)
from .binance_usdm_tradifi_preparation import (
    _trusted_result as _trusted_preparation_result,
)
from .execution_inputs import _materialize_execution_input_bundle_v6

_SCHEMA_VERSION = 1


class BinanceUsdmTradifiBarBacktestFailureCode(str, Enum):
    INVALID_INTENT = "invalid_intent"
    INVALID_PROVIDER_INPUTS = "invalid_provider_inputs"
    MARKET_BUNDLE_MISMATCH = "market_bundle_mismatch"
    PREPARATION_AUTHORITY_INVALID = "preparation_authority_invalid"
    PARAMETER_TARGET_BINDING_INVALID = "parameter_target_binding_invalid"
    TARGET_STREAM_INVALID = "target_stream_invalid"
    ARTIFACT_READ_INVALID = "artifact_read_invalid"
    ARTIFACT_BINDING_INVALID = "artifact_binding_invalid"
    PROFILE_WIRE_INVALID = "profile_wire_invalid"
    PROFILE_BINDING_INVALID = "profile_binding_invalid"
    PROFILE_COMPOSITION_FAILED = "profile_composition_failed"
    BUILD_MANIFEST_CONFLICT = "build_manifest_conflict"
    CASE_PLANNING_FAILED = "case_planning_failed"
    RESULT_INVALID = "result_invalid"


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiBarBacktestIntent:
    request_intent: BinanceUsdmTradifiBarRequestIntent
    provider_inputs: BinanceUsdmTradifiProviderInputs

    def __post_init__(self) -> None:
        if type(self.request_intent) is not BinanceUsdmTradifiBarRequestIntent:
            raise TypeError(
                "request_intent must be exact BinanceUsdmTradifiBarRequestIntent"
            )
        if type(self.provider_inputs) is not BinanceUsdmTradifiProviderInputs:
            raise TypeError(
                "provider_inputs must be exact BinanceUsdmTradifiProviderInputs"
            )

    @property
    def intent_hash(self) -> str:
        return domain.canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_bar_backtest_intent",
            "schema_version": _SCHEMA_VERSION,
            "request_intent": self.request_intent,
            "provider_inputs": self.provider_inputs,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiBarBacktestFailure:
    code: BinanceUsdmTradifiBarBacktestFailureCode
    subject: str

    def __post_init__(self) -> None:
        if type(self.code) is not BinanceUsdmTradifiBarBacktestFailureCode:
            raise TypeError("code must be exact bar-backtest failure code")
        if (
            type(self.subject) is not str
            or not self.subject
            or self.subject.strip() != self.subject
        ):
            raise ValueError("subject must be canonical non-empty text")

    @property
    def failure_hash(self) -> str:
        return domain.canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_bar_backtest_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiBarBacktestResult:
    intent: BinanceUsdmTradifiBarBacktestIntent
    preparation_result: BinanceUsdmTradifiPreparationResult
    case_planning_result: BinanceUsdmTradifiCasePlanningResult
    execution_input_envelope: domain.ArtifactEnvelope
    execution_input_ref: domain.ArtifactRef
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.intent) is not BinanceUsdmTradifiBarBacktestIntent:
            raise TypeError("intent must be exact BinanceUsdmTradifiBarBacktestIntent")
        if _trusted_preparation_result(self.preparation_result) is None:
            raise ValueError("preparation_result must be exact trusted preparation result")
        if self.preparation_result.bundle_schema_version != 2:
            raise ValueError("preparation_result must be exact BundleV2")
        if (
            self.preparation_result.intent != self.intent.request_intent
            or self.preparation_result.provider_inputs != self.intent.provider_inputs
        ):
            raise ValueError("preparation result does not bind intent")
        if _trusted_case_planning_result(self.case_planning_result) is None:
            raise ValueError(
                "case_planning_result must be exact trusted planning result"
            )
        if (
            self.case_planning_result.preparation_result_digest
            != self.preparation_result.result_digest
        ):
            raise ValueError("case planning does not bind preparation result")
        expected_execution_input = _materialize_execution_input_bundle_v6(
            resolved_request=self.case_planning_result.resolved_request,
            hydrated_inputs=self.case_planning_result.hydrated_inputs,
            market_data_preparation=self.case_planning_result.market_data_preparation,
        )
        if (
            type(self.execution_input_envelope) is not domain.ArtifactEnvelope
            or self.execution_input_envelope.artifact_type
            != "backtest_execution_input_bundle"
            or self.execution_input_envelope.schema_version != 6
            or domain.canonical_bytes(self.execution_input_envelope)
            != domain.canonical_bytes(expected_execution_input)
            or type(self.execution_input_ref) is not domain.ArtifactRef
            or self.execution_input_ref
            != domain.ArtifactRef(
                self.execution_input_envelope.artifact_type,
                self.execution_input_envelope.schema_version,
                self.execution_input_envelope.content_hash,
            )
        ):
            raise ValueError("execution input must be exact schema 6 envelope/ref")
        object.__setattr__(self, "result_digest", domain.canonical_sha256(self._body()))

    @property
    def execution_case(self):
        return self.case_planning_result.execution_case

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_bar_backtest_result",
            "schema_version": _SCHEMA_VERSION,
            "intent": self.intent,
            "preparation_result": self.preparation_result,
            "case_planning_result": self.case_planning_result,
            "execution_input_envelope": self.execution_input_envelope,
            "execution_input_ref": self.execution_input_ref,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "result_digest": self.result_digest}


def _trusted_result(value: object) -> BinanceUsdmTradifiBarBacktestResult | None:
    if type(value) is not BinanceUsdmTradifiBarBacktestResult:
        return None
    try:
        rebuilt = BinanceUsdmTradifiBarBacktestResult(
            value.intent,
            value.preparation_result,
            value.case_planning_result,
            value.execution_input_envelope,
            value.execution_input_ref,
        )
        if domain.canonical_bytes(rebuilt) != domain.canonical_bytes(
            value
        ) or value.result_digest != domain.canonical_sha256(value._body()):
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt


@dataclass(frozen=True, slots=True)
class BinanceUsdmTradifiBarBacktestOutcome:
    result: BinanceUsdmTradifiBarBacktestResult | None = None
    failure: BinanceUsdmTradifiBarBacktestFailure | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one branch")
        if self.result is not None and _trusted_result(self.result) is None:
            raise ValueError("result must be exact trusted bar-backtest result")
        if (
            self.failure is not None
            and type(self.failure) is not BinanceUsdmTradifiBarBacktestFailure
        ):
            raise TypeError("failure must be exact bar-backtest failure")

    @property
    def outcome_hash(self) -> str:
        return domain.canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_tradifi_bar_backtest_outcome",
            "schema_version": _SCHEMA_VERSION,
            "result": self.result,
            "failure": self.failure,
        }


def _failure(
    code: BinanceUsdmTradifiBarBacktestFailureCode,
    subject: str,
) -> BinanceUsdmTradifiBarBacktestOutcome:
    return BinanceUsdmTradifiBarBacktestOutcome(
        failure=BinanceUsdmTradifiBarBacktestFailure(code, subject)
    )


def prepare_binance_usdm_tradifi_bar_backtest(
    intent: BinanceUsdmTradifiBarBacktestIntent,
    artifact_reader: ArtifactEnvelopeReader,
    bundle_reader: MarketBundleReader,
) -> BinanceUsdmTradifiBarBacktestOutcome:
    if type(intent) is not BinanceUsdmTradifiBarBacktestIntent:
        return _failure(
            BinanceUsdmTradifiBarBacktestFailureCode.INVALID_INTENT, "intent"
        )
    preparation = resolve_binance_usdm_tradifi_preparation_authority_v2(
        intent=intent.request_intent,
        provider_inputs=intent.provider_inputs,
        artifact_reader=artifact_reader,
        market_reader=bundle_reader,
    )
    if preparation.failure is not None:
        return _failure(
            BinanceUsdmTradifiBarBacktestFailureCode(preparation.failure.code.value),
            preparation.failure.subject,
        )
    try:
        if preparation.result is None:
            return _failure(
                BinanceUsdmTradifiBarBacktestFailureCode.RESULT_INVALID,
                "preparation_result",
            )
        planned = plan_binance_usdm_tradifi_case_v1(preparation.result)
        execution_input = _materialize_execution_input_bundle_v6(
            resolved_request=planned.resolved_request,
            hydrated_inputs=planned.hydrated_inputs,
            market_data_preparation=planned.market_data_preparation,
        )
        return BinanceUsdmTradifiBarBacktestOutcome(
            result=BinanceUsdmTradifiBarBacktestResult(
                intent,
                preparation.result,
                planned,
                execution_input,
                domain.ArtifactRef(
                    execution_input.artifact_type,
                    execution_input.schema_version,
                    execution_input.content_hash,
                ),
            )
        )
    except Exception:  # noqa: BLE001 - public preparation must fail closed
        return _failure(
            BinanceUsdmTradifiBarBacktestFailureCode.CASE_PLANNING_FAILED,
            "case_planning",
        )


__all__ = [
    "BinanceUsdmTradifiBarBacktestFailure",
    "BinanceUsdmTradifiBarBacktestFailureCode",
    "BinanceUsdmTradifiBarBacktestIntent",
    "BinanceUsdmTradifiBarBacktestOutcome",
    "BinanceUsdmTradifiBarBacktestResult",
    "prepare_binance_usdm_tradifi_bar_backtest",
]
