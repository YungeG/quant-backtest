from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from crypto_quant_backtest import (
    AttemptEvidenceWriter,
    AttemptExecutionRecord,
    AttemptIdentity,
    EngineExecutionResult,
    EvidencePublicationOutcome,
    ReadyToFinalizeAttempt,
)
from tests.runtime.evidence._fixtures import attempt_record


def ready_record(*, ordinal: int = 1, result: EngineExecutionResult | None = None) -> AttemptExecutionRecord:
    first = attempt_record("ready")
    assert first.ready_to_finalize is not None
    ready = first.ready_to_finalize
    if ordinal > 1:
        ready = replace(
            ready,
            attempt=AttemptIdentity.retry(first.attempt, next_ordinal=ordinal),
        )
    if result is not None:
        ready = replace(ready, engine_result=result)
    return AttemptExecutionRecord(ready_to_finalize=ready)


def publish_ready(
    root: Path,
    *,
    ordinal: int = 1,
    result: EngineExecutionResult | None = None,
) -> tuple[AttemptExecutionRecord, EvidencePublicationOutcome]:
    record = ready_record(ordinal=ordinal, result=result)
    publication = AttemptEvidenceWriter(root=root).publish(record)
    assert publication.finalized is not None
    assert publication.failure is None
    return record, publication


def ready_branch(record: AttemptExecutionRecord) -> ReadyToFinalizeAttempt:
    assert record.ready_to_finalize is not None
    return record.ready_to_finalize


__all__ = ["publish_ready", "ready_branch", "ready_record"]
