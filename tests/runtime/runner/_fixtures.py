from __future__ import annotations

from dataclasses import dataclass, replace

from crypto_quant_backtest import (
    BacktestResolutionOutcome,
    EngineExecutionOutcome,
    ExecutionCaseComposer,
    ProfileResolver,
    ResolvedBacktestRequest,
    ResolvedExecutionCase,
)
from tests.runtime.engine._fixtures import SyntheticExecutionCaseBuilder, reader
from tests.runtime.resolution._fixtures import (
    build_manifest,
    profile_registry,
    request,
)


def resolved_request_and_case() -> tuple[ResolvedBacktestRequest, ResolvedExecutionCase]:
    builder = SyntheticExecutionCaseBuilder()
    spec = builder.semantic_spec()
    manifest = build_manifest()
    bundle = reader().manifest
    backtest_request = replace(
        request(manifest, bundle=bundle),
        execution_case_semantic_hash=spec.semantic_spec_hash,
        target_stream_digest=spec.target_stream_digest,
    )
    outcome: BacktestResolutionOutcome = ProfileResolver().resolve(
        request=backtest_request,
        registry=profile_registry(),
        market_bundle_manifest=bundle,
        build_artifact_manifest=manifest,
    )
    assert outcome.resolved is not None
    case = ExecutionCaseComposer().compose(
        resolved_request=outcome.resolved,
        builder=builder,
    )
    return outcome.resolved, case


def resolved_request() -> ResolvedBacktestRequest:
    return resolved_request_and_case()[0]


def execution_case() -> ResolvedExecutionCase:
    return resolved_request_and_case()[1]


@dataclass
class RecordingEngine:
    outcome: EngineExecutionOutcome | None = None
    error: BaseException | None = None

    def __post_init__(self) -> None:
        self.calls: list[tuple[object, object]] = []

    def run(self, case, *, cancellation=None):
        self.calls.append((case, cancellation))
        if self.error is not None:
            raise self.error
        assert self.outcome is not None
        return self.outcome


__all__ = [
    "RecordingEngine",
    "execution_case",
    "resolved_request",
    "resolved_request_and_case",
]
