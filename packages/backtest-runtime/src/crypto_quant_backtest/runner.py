"""Auditable Attempt execution and pre-publication outcome mapping."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
import re
from typing import Protocol
import unicodedata

from crypto_quant_domain import canonical_sha256
from crypto_quant_market_data import InputValidationFailure

from .engine import (
    DeterministicBarEngine,
    EngineCancellation,
    EngineCancellationRequest,
    EngineExecutionOutcome,
    EngineExecutionResult,
    EngineFailure,
    EngineFailureCode,
    ResolvedExecutionCase,
)
from .resolution import ResolvedBacktestRequest, StrategyFamily


_HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
_RUN_PATTERN = re.compile(r"run_[0-9a-f]{64}")
_ATTEMPT_PATTERN = re.compile(r"attempt_[0-9a-f]{64}")


def _text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if (
        not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be nonempty canonical text")
    return value


def _hash(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if _HASH_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256 identity")
    return value


def _canonical_texts(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    if type(values) is not tuple:
        raise TypeError(f"{name} must be tuple")
    checked = tuple(sorted(_text(name, value) for value in values))
    if len(set(checked)) != len(checked):
        raise ValueError(f"{name} must be unique")
    return checked


def _canonical_hashes(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    if type(values) is not tuple:
        raise TypeError(f"{name} must be tuple")
    checked = tuple(sorted(_hash(name, value) for value in values))
    if len(set(checked)) != len(checked):
        raise ValueError(f"{name} must be unique")
    return checked


class InputOrigin(str, Enum):
    PRECOMPUTED_TARGET_STREAM = "precomputed_target_stream"
    RUNTIME_STRATEGY = "runtime_strategy"


class BacktestRunOutcome(str, Enum):
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AttemptExecutionStatus(str, Enum):
    READY_TO_FINALIZE = "READY_TO_FINALIZE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AttemptIssueSource(str, Enum):
    INPUT_VALIDATION = "input_validation"
    ENGINE_FAILURE = "engine_failure"
    RUNNER_CONTRACT = "runner_contract"
    ENGINE_EXCEPTION = "engine_exception"


@dataclass(frozen=True, slots=True)
class AttemptIdentity:
    semantic_run_id: str
    ordinal: int
    parent_attempt_id: str | None
    attempt_id: str

    def __post_init__(self) -> None:
        if type(self.semantic_run_id) is not str or _RUN_PATTERN.fullmatch(
            self.semantic_run_id
        ) is None:
            raise ValueError("semantic_run_id must use run_sha256 schema")
        if type(self.ordinal) is not int or self.ordinal <= 0:
            raise ValueError("ordinal must be positive integer")
        if self.ordinal == 1 and self.parent_attempt_id is not None:
            raise ValueError("first Attempt cannot have a parent")
        if self.ordinal > 1:
            if (
                type(self.parent_attempt_id) is not str
                or _ATTEMPT_PATTERN.fullmatch(self.parent_attempt_id) is None
            ):
                raise ValueError("retry Attempt requires canonical parent_attempt_id")
        expected = self._derive_id(
            self.semantic_run_id, self.ordinal, self.parent_attempt_id
        )
        if self.attempt_id != expected:
            raise ValueError(
                "attempt_id does not match semantic run, ordinal, and parent"
            )

    @classmethod
    def first(cls, semantic_run_id: str) -> AttemptIdentity:
        return cls(
            semantic_run_id=semantic_run_id,
            ordinal=1,
            parent_attempt_id=None,
            attempt_id=cls._derive_id(semantic_run_id, 1, None),
        )

    @classmethod
    def retry(
        cls, previous: AttemptIdentity, *, next_ordinal: int
    ) -> AttemptIdentity:
        if not isinstance(previous, AttemptIdentity):
            raise TypeError("previous must be AttemptIdentity")
        if type(next_ordinal) is not int or next_ordinal <= previous.ordinal:
            raise ValueError("next Attempt ordinal must be greater than previous")
        return cls(
            semantic_run_id=previous.semantic_run_id,
            ordinal=next_ordinal,
            parent_attempt_id=previous.attempt_id,
            attempt_id=cls._derive_id(
                previous.semantic_run_id, next_ordinal, previous.attempt_id
            ),
        )

    @staticmethod
    def _derive_id(
        semantic_run_id: str, ordinal: int, parent_attempt_id: str | None
    ) -> str:
        digest = canonical_sha256(
            {
                "type": "attempt_identity_v1",
                "semantic_run_id": semantic_run_id,
                "ordinal": ordinal,
                "parent_attempt_id": parent_attempt_id,
            }
        )
        return "attempt_" + digest.removeprefix("sha256:")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "attempt_identity",
            "schema_version": 1,
            "semantic_run_id": self.semantic_run_id,
            "ordinal": self.ordinal,
            "parent_attempt_id": self.parent_attempt_id,
            "attempt_id": self.attempt_id,
        }


@dataclass(frozen=True, slots=True)
class AttemptIssue:
    source: AttemptIssueSource
    code: str
    subject_keys: tuple[str, ...]
    evidence_hashes: tuple[str, ...]
    source_hash: str
    source_evidence: InputValidationFailure | EngineFailure | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, AttemptIssueSource):
            raise TypeError("source must be AttemptIssueSource")
        _text("code", self.code)
        subjects = _canonical_texts("subject_key", self.subject_keys)
        hashes = _canonical_hashes("evidence_hash", self.evidence_hashes)
        _hash("source_hash", self.source_hash)
        if self.source_evidence is not None:
            if not isinstance(
                self.source_evidence, (InputValidationFailure, EngineFailure)
            ):
                raise TypeError("source_evidence has unsupported type")
            if canonical_sha256(self.source_evidence) != self.source_hash:
                raise ValueError("source_hash does not match source_evidence")
        if self.source is AttemptIssueSource.INPUT_VALIDATION and not isinstance(
            self.source_evidence, InputValidationFailure
        ):
            raise ValueError("input-validation issue requires exact source evidence")
        if self.source is AttemptIssueSource.ENGINE_FAILURE and not isinstance(
            self.source_evidence, EngineFailure
        ):
            raise ValueError("engine-failure issue requires exact source evidence")
        if self.source in {
            AttemptIssueSource.RUNNER_CONTRACT,
            AttemptIssueSource.ENGINE_EXCEPTION,
        } and self.source_evidence is not None:
            raise ValueError("runner issue cannot carry engine/input source evidence")
        object.__setattr__(self, "subject_keys", subjects)
        object.__setattr__(self, "evidence_hashes", hashes)

    @property
    def issue_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "attempt_issue",
            "source": self.source.value,
            "code": self.code,
            "subject_keys": self.subject_keys,
            "evidence_hashes": self.evidence_hashes,
            "source_hash": self.source_hash,
            "source_evidence": self.source_evidence,
        }


def _validate_attempt_context(
    attempt: AttemptIdentity,
    resolved_request: ResolvedBacktestRequest,
    input_origin: InputOrigin,
    execution_case_hash: str,
) -> None:
    if not isinstance(attempt, AttemptIdentity):
        raise TypeError("attempt must be AttemptIdentity")
    if not isinstance(resolved_request, ResolvedBacktestRequest):
        raise TypeError("resolved_request must be ResolvedBacktestRequest")
    if attempt.semantic_run_id != resolved_request.semantic_run_id:
        raise ValueError("Attempt semantic run does not match resolved request")
    if not isinstance(input_origin, InputOrigin):
        raise TypeError("input_origin must be InputOrigin")
    _hash("execution_case_hash", execution_case_hash)


@dataclass(frozen=True, slots=True)
class _AttemptIssueReport:
    attempt: AttemptIdentity
    resolved_request: ResolvedBacktestRequest
    input_origin: InputOrigin
    execution_case_hash: str
    issue: AttemptIssue
    trace_hash: str | None = None

    def __post_init__(self) -> None:
        _validate_attempt_context(
            self.attempt,
            self.resolved_request,
            self.input_origin,
            self.execution_case_hash,
        )
        if not isinstance(self.issue, AttemptIssue):
            raise TypeError("issue must be AttemptIssue")
        if self.trace_hash is not None:
            _hash("trace_hash", self.trace_hash)

    @property
    def report_hash(self) -> str:
        return canonical_sha256(self)

    def _canonical_dict(self, report_type: str) -> dict[str, object]:
        return {
            "type": report_type,
            "attempt": self.attempt,
            "resolved_request": self.resolved_request,
            "input_origin": self.input_origin.value,
            "execution_case_hash": self.execution_case_hash,
            "issue": self.issue,
            "trace_hash": self.trace_hash,
        }


class BlockedAttemptReport(_AttemptIssueReport):
    __slots__ = ()

    def to_canonical_dict(self) -> dict[str, object]:
        return self._canonical_dict("blocked_attempt_report")


class FailedAttemptReport(_AttemptIssueReport):
    __slots__ = ()

    def to_canonical_dict(self) -> dict[str, object]:
        return self._canonical_dict("failed_attempt_report")


@dataclass(frozen=True, slots=True)
class CancelledAttemptReport:
    attempt: AttemptIdentity
    resolved_request: ResolvedBacktestRequest
    input_origin: InputOrigin
    execution_case_hash: str
    cancellation: EngineCancellation

    def __post_init__(self) -> None:
        _validate_attempt_context(
            self.attempt,
            self.resolved_request,
            self.input_origin,
            self.execution_case_hash,
        )
        if not isinstance(self.cancellation, EngineCancellation):
            raise TypeError("cancellation must be EngineCancellation")
        if self.cancellation.case_hash != self.execution_case_hash:
            raise ValueError("cancellation does not match execution case")

    @property
    def report_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cancelled_attempt_report",
            "attempt": self.attempt,
            "resolved_request": self.resolved_request,
            "input_origin": self.input_origin.value,
            "execution_case_hash": self.execution_case_hash,
            "cancellation": self.cancellation,
        }


@dataclass(frozen=True, slots=True)
class ReadyToFinalizeAttempt:
    attempt: AttemptIdentity
    resolved_request: ResolvedBacktestRequest
    input_origin: InputOrigin
    execution_case_hash: str
    engine_result: EngineExecutionResult

    def __post_init__(self) -> None:
        _validate_attempt_context(
            self.attempt,
            self.resolved_request,
            self.input_origin,
            self.execution_case_hash,
        )
        if not isinstance(self.engine_result, EngineExecutionResult):
            raise TypeError("engine_result must be EngineExecutionResult")
        if self.engine_result.case_hash != self.execution_case_hash:
            raise ValueError("Engine result does not match execution case")
        if (
            self.engine_result.target_stream_digest
            != self.resolved_request.request.target_stream_digest
        ):
            raise ValueError("Engine result target stream does not match request")

    @property
    def ready_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "ready_to_finalize_attempt",
            "attempt": self.attempt,
            "resolved_request": self.resolved_request,
            "input_origin": self.input_origin.value,
            "execution_case_hash": self.execution_case_hash,
            "engine_result": self.engine_result,
        }


@dataclass(frozen=True, slots=True)
class AttemptExecutionRecord:
    ready_to_finalize: ReadyToFinalizeAttempt | None = None
    blocked_report: BlockedAttemptReport | None = None
    failed_report: FailedAttemptReport | None = None
    cancelled_report: CancelledAttemptReport | None = None

    def __post_init__(self) -> None:
        branches = (
            self.ready_to_finalize is not None,
            self.blocked_report is not None,
            self.failed_report is not None,
            self.cancelled_report is not None,
        )
        if sum(branches) != 1:
            raise ValueError("Attempt execution requires exactly one branch")
        expected_types = (
            (self.ready_to_finalize, ReadyToFinalizeAttempt),
            (self.blocked_report, BlockedAttemptReport),
            (self.failed_report, FailedAttemptReport),
            (self.cancelled_report, CancelledAttemptReport),
        )
        for value, expected in expected_types:
            if value is not None and not isinstance(value, expected):
                raise TypeError("Attempt execution branch has invalid type")

    @property
    def status(self) -> AttemptExecutionStatus:
        if self.ready_to_finalize is not None:
            return AttemptExecutionStatus.READY_TO_FINALIZE
        if self.blocked_report is not None:
            return AttemptExecutionStatus.BLOCKED
        if self.failed_report is not None:
            return AttemptExecutionStatus.FAILED
        return AttemptExecutionStatus.CANCELLED

    @property
    def terminal_outcome(self) -> BacktestRunOutcome | None:
        if self.blocked_report is not None:
            return BacktestRunOutcome.BLOCKED
        if self.failed_report is not None:
            return BacktestRunOutcome.FAILED
        if self.cancelled_report is not None:
            return BacktestRunOutcome.CANCELLED
        return None

    @property
    def attempt(self) -> AttemptIdentity:
        for branch in (
            self.ready_to_finalize,
            self.blocked_report,
            self.failed_report,
            self.cancelled_report,
        ):
            if branch is not None:
                return branch.attempt
        raise RuntimeError("Attempt execution has no branch")

    @property
    def resolved_request(self) -> ResolvedBacktestRequest:
        for branch in (
            self.ready_to_finalize,
            self.blocked_report,
            self.failed_report,
            self.cancelled_report,
        ):
            if branch is not None:
                return branch.resolved_request
        raise RuntimeError("Attempt execution has no branch")

    @property
    def input_origin(self) -> InputOrigin:
        for branch in (
            self.ready_to_finalize,
            self.blocked_report,
            self.failed_report,
            self.cancelled_report,
        ):
            if branch is not None:
                return branch.input_origin
        raise RuntimeError("Attempt execution has no branch")

    @property
    def execution_case_hash(self) -> str:
        for branch in (
            self.ready_to_finalize,
            self.blocked_report,
            self.failed_report,
            self.cancelled_report,
        ):
            if branch is not None:
                return branch.execution_case_hash
        raise RuntimeError("Attempt execution has no branch")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "attempt_execution_record",
            "status": self.status.value,
            "terminal_outcome": (
                self.terminal_outcome.value
                if self.terminal_outcome is not None
                else None
            ),
            "ready_to_finalize": self.ready_to_finalize,
            "blocked_report": self.blocked_report,
            "failed_report": self.failed_report,
            "cancelled_report": self.cancelled_report,
        }


class _Engine(Protocol):
    @abstractmethod
    def run(
        self,
        case: ResolvedExecutionCase | InputValidationFailure,
        *,
        cancellation: EngineCancellationRequest | None = None,
    ) -> EngineExecutionOutcome:
        pass


_ORIGIN_SENSITIVE_CODES = frozenset(
    {
        EngineFailureCode.TARGET_INPUT_DECODE,
        EngineFailureCode.TARGET_VALIDATION,
        EngineFailureCode.DECISION_BATCH,
    }
)
_BLOCKED_ENGINE_CODES = frozenset(
    {
        EngineFailureCode.TIMELINE_FAILURE,
        EngineFailureCode.POSITION_SIZING,
        EngineFailureCode.CAPABILITY_REJECTED,
        EngineFailureCode.TRANSLATION_REJECTED,
        EngineFailureCode.MARKET_RULE_REJECTED,
        EngineFailureCode.MARKET_RULE_DATA_FAILURE,
        EngineFailureCode.FEE_RESERVATION,
        EngineFailureCode.PRETRADE_REJECTED,
        EngineFailureCode.EXECUTION_FAILURE,
        EngineFailureCode.SLIPPAGE_FAILURE,
        EngineFailureCode.FEE_ASSESSMENT_FAILURE,
        EngineFailureCode.SNAPSHOT_PROJECTION_FAILURE,
        EngineFailureCode.RUN_END_TERMINATED,
        EngineFailureCode.MISSING_SCHEDULED_EVENT,
    }
)
_FAILED_ENGINE_CODES = frozenset(
    {
        EngineFailureCode.ALLOCATION,
        EngineFailureCode.PORTFOLIO_RISK,
        EngineFailureCode.REBALANCE,
        EngineFailureCode.ORDER_PLAN_MISMATCH,
        EngineFailureCode.PRETRADE_CONTRACT_FAILURE,
        EngineFailureCode.FILL_CONSTRUCTION,
        EngineFailureCode.ACCOUNTING_FAILURE,
        EngineFailureCode.FEE_ACCOUNTING_FAILURE,
        EngineFailureCode.CASE_EVIDENCE_MISMATCH,
    }
)
if _ORIGIN_SENSITIVE_CODES | _BLOCKED_ENGINE_CODES | _FAILED_ENGINE_CODES != frozenset(
    EngineFailureCode
):
    raise RuntimeError("Engine failure outcome mapping is not exhaustive")


class AuditableBacktestRunner:
    def __init__(self, *, engine: _Engine | None = None) -> None:
        self._engine: _Engine = engine or DeterministicBarEngine()

    @staticmethod
    def classify_engine_failure(
        code: EngineFailureCode, input_origin: InputOrigin
    ) -> BacktestRunOutcome:
        if not isinstance(code, EngineFailureCode):
            raise TypeError("code must be EngineFailureCode")
        if not isinstance(input_origin, InputOrigin):
            raise TypeError("input_origin must be InputOrigin")
        if code in _ORIGIN_SENSITIVE_CODES:
            if input_origin is InputOrigin.PRECOMPUTED_TARGET_STREAM:
                return BacktestRunOutcome.BLOCKED
            return BacktestRunOutcome.FAILED
        if code in _BLOCKED_ENGINE_CODES:
            return BacktestRunOutcome.BLOCKED
        if code in _FAILED_ENGINE_CODES:
            return BacktestRunOutcome.FAILED
        raise RuntimeError(f"Engine failure code is not classified: {code.value}")

    def execute(
        self,
        *,
        resolved_request: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        attempt: AttemptIdentity,
        input_origin: InputOrigin,
        cancellation: EngineCancellationRequest | None = None,
    ) -> AttemptExecutionRecord:
        if not isinstance(resolved_request, ResolvedBacktestRequest):
            raise TypeError("resolved_request must be ResolvedBacktestRequest")
        if not isinstance(execution_case, ResolvedExecutionCase):
            raise TypeError("execution_case must be ResolvedExecutionCase")
        if not isinstance(attempt, AttemptIdentity):
            raise TypeError("attempt must be AttemptIdentity")
        if attempt.semantic_run_id != resolved_request.semantic_run_id:
            raise ValueError("Attempt semantic run does not match resolved request")
        if not isinstance(input_origin, InputOrigin):
            raise TypeError("input_origin must be InputOrigin")
        if cancellation is not None and not isinstance(
            cancellation, EngineCancellationRequest
        ):
            raise TypeError("cancellation must be EngineCancellationRequest or None")

        contract_issue = self._contract_issue(
            resolved_request, execution_case, input_origin
        )
        if contract_issue is not None:
            return self._failed_record(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                contract_issue,
            )
        try:
            outcome = self._engine.run(execution_case, cancellation=cancellation)
        except Exception as error:
            exception_type = f"{type(error).__module__}.{type(error).__qualname__}"
            source_hash = canonical_sha256(
                {
                    "type": "unhandled_engine_exception_v1",
                    "exception_type": exception_type,
                }
            )
            issue = AttemptIssue(
                source=AttemptIssueSource.ENGINE_EXCEPTION,
                code="unhandled_engine_exception",
                subject_keys=(exception_type,),
                evidence_hashes=(source_hash,),
                source_hash=source_hash,
            )
            return self._failed_record(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                issue,
            )
        if not isinstance(outcome, EngineExecutionOutcome):
            issue = self._runner_issue(
                "invalid_engine_outcome",
                (type(outcome).__qualname__,),
            )
            return self._failed_record(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                issue,
            )
        return self._map_outcome(
            resolved_request,
            execution_case,
            attempt,
            input_origin,
            cancellation,
            outcome,
        )

    def retry_from_start(
        self,
        *,
        previous: AttemptExecutionRecord,
        resolved_request: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        next_attempt_ordinal: int,
        input_origin: InputOrigin,
        cancellation: EngineCancellationRequest | None = None,
    ) -> AttemptExecutionRecord:
        if not isinstance(previous, AttemptExecutionRecord):
            raise TypeError("previous must be AttemptExecutionRecord")
        if previous.resolved_request.semantic_run_id != resolved_request.semantic_run_id:
            raise ValueError("retry must remain in the previous Semantic Run")
        if canonical_sha256(previous.resolved_request) != canonical_sha256(
            resolved_request
        ):
            raise ValueError("retry must reuse the same resolved request")
        if previous.execution_case_hash != execution_case.case_hash:
            raise ValueError("retry must reuse the same initial execution case")
        if previous.input_origin is not input_origin:
            raise ValueError("retry must preserve InputOrigin")
        attempt = AttemptIdentity.retry(
            previous.attempt, next_ordinal=next_attempt_ordinal
        )
        return self.execute(
            resolved_request=resolved_request,
            execution_case=execution_case,
            attempt=attempt,
            input_origin=input_origin,
            cancellation=cancellation,
        )

    def _map_outcome(
        self,
        resolved_request: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        attempt: AttemptIdentity,
        input_origin: InputOrigin,
        cancellation_request: EngineCancellationRequest | None,
        outcome: EngineExecutionOutcome,
    ) -> AttemptExecutionRecord:
        if outcome.result is not None:
            if outcome.result.case_hash != execution_case.case_hash:
                return self._failed_record(
                    attempt,
                    resolved_request,
                    input_origin,
                    execution_case.case_hash,
                    self._runner_issue(
                        "engine_result_case_mismatch",
                        (outcome.result.case_hash, execution_case.case_hash),
                    ),
                )
            return AttemptExecutionRecord(
                ready_to_finalize=ReadyToFinalizeAttempt(
                    attempt=attempt,
                    resolved_request=resolved_request,
                    input_origin=input_origin,
                    execution_case_hash=execution_case.case_hash,
                    engine_result=outcome.result,
                )
            )
        if outcome.input_validation_failure is not None:
            input_failure = outcome.input_validation_failure
            if input_failure.bundle_ref != resolved_request.request.market_bundle_ref:
                return self._failed_record(
                    attempt,
                    resolved_request,
                    input_origin,
                    execution_case.case_hash,
                    self._runner_issue(
                        "input_validation_bundle_mismatch",
                        (
                            input_failure.bundle_ref.manifest_hash,
                            resolved_request.request.market_bundle_ref.manifest_hash,
                        ),
                    ),
                )
            issue = AttemptIssue(
                source=AttemptIssueSource.INPUT_VALIDATION,
                code="market_bundle_input_validation",
                subject_keys=tuple(
                    f"{value.code.value}:{value.subject_key}"
                    for value in input_failure.issues
                ),
                evidence_hashes=(input_failure.failure_hash,),
                source_hash=input_failure.failure_hash,
                source_evidence=input_failure,
            )
            return AttemptExecutionRecord(
                blocked_report=BlockedAttemptReport(
                    attempt,
                    resolved_request,
                    input_origin,
                    execution_case.case_hash,
                    issue,
                )
            )
        if outcome.engine_failure is not None:
            engine_failure = outcome.engine_failure
            if engine_failure.case_hash != execution_case.case_hash:
                return self._failed_record(
                    attempt,
                    resolved_request,
                    input_origin,
                    execution_case.case_hash,
                    self._runner_issue(
                        "engine_failure_case_mismatch",
                        (engine_failure.case_hash, execution_case.case_hash),
                    ),
                )
            issue = AttemptIssue(
                source=AttemptIssueSource.ENGINE_FAILURE,
                code=engine_failure.code.value,
                subject_keys=engine_failure.subject_keys,
                evidence_hashes=engine_failure.evidence_hashes,
                source_hash=engine_failure.failure_hash,
                source_evidence=engine_failure,
            )
            mapped = self.classify_engine_failure(engine_failure.code, input_origin)
            if mapped is BacktestRunOutcome.BLOCKED:
                return AttemptExecutionRecord(
                    blocked_report=BlockedAttemptReport(
                        attempt,
                        resolved_request,
                        input_origin,
                        execution_case.case_hash,
                        issue,
                        engine_failure.trace_hash,
                    )
                )
            return self._failed_record(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                issue,
                engine_failure.trace_hash,
            )
        cancellation = outcome.cancellation
        if cancellation is None:
            raise RuntimeError("Engine outcome has no branch")
        if cancellation.case_hash != execution_case.case_hash:
            return self._failed_record(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                self._runner_issue(
                    "engine_cancellation_case_mismatch",
                    (cancellation.case_hash, execution_case.case_hash),
                ),
            )
        if cancellation_request is None or cancellation.request != cancellation_request:
            return self._failed_record(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                self._runner_issue(
                    "engine_cancellation_request_mismatch",
                    (cancellation.request.request_hash,),
                ),
                cancellation.trace_hash,
            )
        return AttemptExecutionRecord(
            cancelled_report=CancelledAttemptReport(
                attempt,
                resolved_request,
                input_origin,
                execution_case.case_hash,
                cancellation,
            )
        )

    @staticmethod
    def _contract_issue(
        resolved_request: ResolvedBacktestRequest,
        execution_case: ResolvedExecutionCase,
        input_origin: InputOrigin,
    ) -> AttemptIssue | None:
        request = resolved_request.request
        if request.execution_case_semantic_hash != execution_case.case_hash:
            return AuditableBacktestRunner._runner_issue(
                "execution_case_mismatch",
                (request.execution_case_semantic_hash, execution_case.case_hash),
            )
        if request.target_stream_digest != execution_case.target_stream.target_stream_digest:
            return AuditableBacktestRunner._runner_issue(
                "target_stream_digest_mismatch",
                (
                    request.target_stream_digest,
                    execution_case.target_stream.target_stream_digest,
                ),
            )
        expected_origin = (
            InputOrigin.PRECOMPUTED_TARGET_STREAM
            if request.strategy_family is StrategyFamily.PRECOMPUTED_TARGET
            else InputOrigin.RUNTIME_STRATEGY
        )
        if input_origin is not expected_origin:
            return AuditableBacktestRunner._runner_issue(
                "input_origin_mismatch",
                (request.strategy_family.value, input_origin.value),
            )
        return None

    @staticmethod
    def _runner_issue(code: str, subjects: tuple[str, ...]) -> AttemptIssue:
        payload = {
            "type": "auditable_runner_contract_issue_v1",
            "code": code,
            "subject_keys": tuple(sorted(subjects)),
        }
        source_hash = canonical_sha256(payload)
        return AttemptIssue(
            source=AttemptIssueSource.RUNNER_CONTRACT,
            code=code,
            subject_keys=subjects,
            evidence_hashes=(source_hash,),
            source_hash=source_hash,
        )

    @staticmethod
    def _failed_record(
        attempt: AttemptIdentity,
        resolved_request: ResolvedBacktestRequest,
        input_origin: InputOrigin,
        execution_case_hash: str,
        issue: AttemptIssue,
        trace_hash: str | None = None,
    ) -> AttemptExecutionRecord:
        return AttemptExecutionRecord(
            failed_report=FailedAttemptReport(
                attempt,
                resolved_request,
                input_origin,
                execution_case_hash,
                issue,
                trace_hash,
            )
        )


__all__ = [
    "AttemptExecutionRecord",
    "AttemptExecutionStatus",
    "AttemptIdentity",
    "AttemptIssue",
    "AttemptIssueSource",
    "AuditableBacktestRunner",
    "BacktestRunOutcome",
    "BlockedAttemptReport",
    "CancelledAttemptReport",
    "FailedAttemptReport",
    "InputOrigin",
    "ReadyToFinalizeAttempt",
]
