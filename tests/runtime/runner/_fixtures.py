from __future__ import annotations

from dataclasses import dataclass, replace

from crypto_quant_backtest import (
    BacktestResolutionOutcome,
    EngineExecutionOutcome,
    ProfileResolver,
    ResolvedBacktestRequest,
)
from tests.runtime.engine._fixtures import execution_case
from tests.runtime.resolution._fixtures import (
    build_manifest,
    profile_registry,
    request,
)


def resolved_request() -> ResolvedBacktestRequest:
    manifest = build_manifest()
    case = execution_case()
    bundle = case.timeline.reader.manifest
    backtest_request = replace(
        request(manifest, bundle=bundle),
        execution_case_semantic_hash=case.case_hash,
        target_stream_digest=case.target_stream.target_stream_digest,
    )
    outcome: BacktestResolutionOutcome = ProfileResolver().resolve(
        request=backtest_request,
        registry=profile_registry(),
        market_bundle_manifest=bundle,
        build_artifact_manifest=manifest,
    )
    assert outcome.resolved is not None
    return outcome.resolved


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


__all__ = ["RecordingEngine", "execution_case", "resolved_request"]
