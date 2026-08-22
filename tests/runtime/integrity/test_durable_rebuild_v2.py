from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import crypto_quant_backtest._durable_rebuild as durable
import pytest
from crypto_quant_backtest import (
    AttemptConsistencySet,
    BacktestRunOutcome,
    ExecutionResultHasher,
)
from crypto_quant_backtest._durable_rebuild import (
    DurableRebuildPublisherV1,
    DurableRebuildVerifierV1,
)
from crypto_quant_backtest._publication import RunPublicationLock
from crypto_quant_backtest.integrity import (
    IntegrityEvaluationContextV2,
    IntegrityEvaluationRecordV2,
    IntegrityIssueCode,
    _evaluate_integrity_v2,
)
from crypto_quant_domain import canonical_sha256

from tests.runtime.test_durable_rebuild_facade import (
    _journey_values,
    _local_reader,
    _seed_attempt_graph,
    _Store,
)


def test_attempt_equal_rebuild_mismatch_is_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    values = _journey_values()
    prepared, resolved, case, _, request, registry = values
    store = _Store()
    records, finalized = _seed_attempt_graph(store, tmp_path / "publication", values)
    attempt_hashes = tuple(
        ExecutionResultHasher.bind(record.ready_to_finalize, evidence)
        for record, evidence in zip(records, finalized, strict=True)
        if record.ready_to_finalize is not None and evidence is not None
    )
    attempts = AttemptConsistencySet(resolved, attempt_hashes, finalized)
    local = _local_reader(tmp_path / "market", prepared.verified_reader)
    original_run = durable.DeterministicBarEngine.run

    def changed_run(self, *args, **kwargs):
        outcome = original_run(self, *args, **kwargs)
        assert outcome.result is not None
        changed = replace(
            outcome.result,
            trace=replace(
                outcome.result.trace,
                entries=(
                    replace(
                        outcome.result.trace.entries[0],
                        evidence_hash=canonical_sha256({"changed": True}),
                    ),
                    *outcome.result.trace.entries[1:],
                ),
            ),
        )
        return replace(outcome, result=changed)

    monkeypatch.setattr(durable.DeterministicBarEngine, "run", changed_run)
    verification = DurableRebuildVerifierV1(
        artifact_reader=store,
        market_reader=local,
        profile_registry=registry,
    ).verify(
        request=request,
        resolved_request=resolved,
        prepared_market_data=prepared,
        execution_case=case,
        attempts=attempts,
    )
    root = tmp_path / "publication"
    with RunPublicationLock(root=root, semantic_run_id=resolved.semantic_run_id) as lock:
        observation = DurableRebuildPublisherV1(
            root=root, artifact_reader=store
        ).publish(lock=lock, verification=verification)
    context = IntegrityEvaluationContextV2(
        resolved,
        attempts,
        ExecutionResultHasher.check_same_semantic_run(attempt_hashes),
        observation,
    )
    report = _evaluate_integrity_v2(context)
    assert [issue.code for issue in report.issues] == [
        IntegrityIssueCode.DETERMINISTIC_REBUILD_MISMATCH
    ]
    record = IntegrityEvaluationRecordV2(
        report,
        BacktestRunOutcome.FAILED,
    )
    assert record.outcome.value == "FAILED"
