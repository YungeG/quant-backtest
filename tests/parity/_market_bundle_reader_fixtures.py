from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from crypto_quant_backtest import (
    AttemptEvidenceWriter,
    AttemptIdentity,
    AuditableBacktestRunner,
    BacktestResolutionOutcome,
    DeterministicBarEngine,
    DeterministicTimeline,
    ExecutionCaseComposer,
    ExecutionResultHasher,
    InputOrigin,
    ProfileResolver,
    ResolvedBacktestRequest,
    ResolvedExecutionCase,
)
from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
)
from crypto_quant_domain import canonical_bytes, canonical_sha256
from crypto_quant_market_data import (
    EventCursor,
    InMemoryMarketBundleReader,
    InputValidationFailure,
    LocalMarketBundleReader,
    MarketBundleReader,
)
from tests.bundle_builder.publication._fixtures import (
    PUBLICATION_RETENTION_POLICY_REF,
)
from tests.runtime.engine._fixtures import SyntheticExecutionCaseBuilder, reader
from tests.runtime.execution_hash._fixtures import ready_branch
from tests.runtime.resolution._fixtures import build_manifest, profile_registry, request


READER_BATCH_SIZES = (1, 2, 10)
TIMELINE_BATCH_SIZES = (1, 2, 10)


def publish_reader(root: Path) -> tuple[InMemoryMarketBundleReader, LocalMarketBundleReader]:
    in_memory = reader()
    outcome = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(root=root)
    ).publish_market_bundle_v1(
        manifest=in_memory.manifest,
        stream_payloads={
            stream_key: canonical_bytes(events)
            for stream_key, events in in_memory.streams.items()
        },
        retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF,
    )
    if outcome.result is None:
        raise AssertionError("expected G12D publication success")
    return (
        in_memory,
        LocalMarketBundleReader.open(
            repository_root=root,
            bundle_ref=outcome.result.bundle_ref,
        ),
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
    if outcome.resolved is None:
        raise AssertionError("expected resolved G12F request")
    case = ExecutionCaseComposer().compose(
        resolved_request=outcome.resolved,
        builder=builder,
    )
    return outcome.resolved, case


def case_for_reader(
    base: ResolvedExecutionCase,
    market_reader: MarketBundleReader,
    *,
    timeline_batch_size: int,
) -> ResolvedExecutionCase:
    timeline = DeterministicTimeline.open(
        reader=market_reader,
        stream_keys=base.timeline.stream_keys,
        window=base.timeline.window,
    )
    if isinstance(timeline, InputValidationFailure):
        raise AssertionError("expected valid G12F Timeline")
    return replace(
        base,
        timeline=timeline,
        timeline_batch_size=timeline_batch_size,
    )


def _stream_rows(market_reader: MarketBundleReader) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for stream in market_reader.manifest.streams:
        for batch_size in READER_BATCH_SIZES:
            cursor = market_reader.open_cursor(
                stream.stream_key,
                batch_size=batch_size,
            )
            if not isinstance(cursor, EventCursor):
                raise AssertionError("expected G12F stream cursor")
            event_ids: list[str] = []
            event_hashes: list[str] = []
            while not cursor.exhausted:
                batch, cursor = market_reader.read_batch(cursor)
                event_ids.extend(event.event_id for event in batch)
                event_hashes.extend(event.event_hash for event in batch)
            rows.append(
                {
                    "batch_size": batch_size,
                    "content_hash": stream.content_hash,
                    "event_count": stream.event_count,
                    "event_hashes": event_hashes,
                    "event_ids": event_ids,
                    "stream_key": stream.stream_key,
                    "terminal_cursor_hash": cursor.cursor_hash,
                }
            )
    return rows


def _timeline_rows(
    market_reader: MarketBundleReader,
    base: ResolvedExecutionCase,
) -> list[dict[str, object]]:
    timeline = DeterministicTimeline.open(
        reader=market_reader,
        stream_keys=base.timeline.stream_keys,
        window=base.timeline.window,
    )
    if isinstance(timeline, InputValidationFailure):
        raise AssertionError("expected G12F Timeline")

    rows: list[dict[str, object]] = []
    for batch_size in TIMELINE_BATCH_SIZES:
        cursor = timeline.open_cursor(batch_size=batch_size)
        event_ids: list[str] = []
        event_hashes: list[str] = []
        segments: list[str] = []
        while not cursor.window_complete:
            outcome = timeline.read_batch(cursor)
            if outcome.batch is None:
                raise AssertionError("expected G12F Timeline batch")
            event_ids.extend(item.event.event_id for item in outcome.batch.events)
            event_hashes.extend(item.event.event_hash for item in outcome.batch.events)
            segments.extend(item.segment.value for item in outcome.batch.events)
            cursor = outcome.batch.next_cursor
        rows.append(
            {
                "batch_size": batch_size,
                "event_hashes": event_hashes,
                "event_ids": event_ids,
                "segments": segments,
                "terminal_cursor_hash": cursor.cursor_hash,
                "timeline_id": timeline.timeline_id,
            }
        )
    return rows


def _execution_rows(
    market_reader: MarketBundleReader,
    base: ResolvedExecutionCase,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for batch_size in TIMELINE_BATCH_SIZES:
        case = case_for_reader(
            base,
            market_reader,
            timeline_batch_size=batch_size,
        )
        outcome = DeterministicBarEngine().run(case)
        if outcome.result is None:
            raise AssertionError("expected G12F Engine result")
        result = outcome.result
        rows.append(
            {
                "case_hash": case.case_hash,
                "engine_result_hash": result.result_hash,
                "ledger_state_hash": result.final_ledger_state.state_hash,
                "run_end_report_hash": result.run_end_report.report_hash,
                "snapshot_hash": canonical_sha256(result.final_portfolio_snapshot),
                "timeline_batch_size": batch_size,
                "trace_hash": result.trace.trace_hash,
            }
        )
    return rows


def _auditable_rows(
    root: Path,
    resolved_request: ResolvedBacktestRequest,
    market_reader: MarketBundleReader,
    base: ResolvedExecutionCase,
) -> list[dict[str, object]]:
    attempt_ids: list[str] = []
    evidence_hashes: list[str] = []
    execution_case_hashes: list[str] = []
    execution_result_hashes: list[str] = []
    previous: AttemptIdentity | None = None

    for index, batch_size in enumerate((1, 10), start=1):
        case = case_for_reader(
            base,
            market_reader,
            timeline_batch_size=batch_size,
        )
        attempt = (
            AttemptIdentity.first(resolved_request.semantic_run_id)
            if previous is None
            else AttemptIdentity.retry(previous, next_ordinal=index)
        )
        runner = AuditableBacktestRunner(publication_root=root)
        record = runner.execute(
            resolved_request=resolved_request,
            execution_case=case,
            attempt=attempt,
            input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
        )
        publication = AttemptEvidenceWriter(root=root).publish(record)
        if publication.finalized is None:
            raise AssertionError("expected finalized G12F Attempt evidence")
        execution_hash = ExecutionResultHasher.bind(
            ready_branch(record),
            publication.finalized,
        )
        attempt_ids.append(attempt.attempt_id)
        evidence_hashes.append(publication.finalized.manifest.manifest_hash)
        execution_case_hashes.append(record.execution_case_hash)
        execution_result_hashes.append(execution_hash.execution_result_hash)
        previous = attempt

    return [
        {
            "attempt_count": len(attempt_ids),
            "distinct_attempt_ids": len(set(attempt_ids)) == len(attempt_ids),
            "distinct_evidence_manifest_hashes": (
                len(set(evidence_hashes)) == len(evidence_hashes)
            ),
            "execution_case_hashes": execution_case_hashes,
            "execution_result_hashes": execution_result_hashes,
            "timeline_batch_sizes": [1, 10],
        }
    ]


def projection(root: Path, market_reader: MarketBundleReader) -> dict[str, object]:
    resolved_request, base = resolved_request_and_case()
    return json.loads(
        canonical_bytes(
            {
                "auditable_runs": _auditable_rows(
                    root / "auditable",
                    resolved_request,
                    market_reader,
                    base,
                ),
                "bundle": {
                    "bundle_ref": market_reader.bundle_ref.to_canonical_dict(),
                    "manifest_hash": market_reader.bundle_ref.manifest_hash,
                },
                "executions": _execution_rows(market_reader, base),
                "fixture_id": "market-bundle-reader-g12f-v1",
                "qualification": {
                    "decision_grade_eligible": False,
                    "deployment_authorized": False,
                },
                "schema_version": 1,
                "streams": _stream_rows(market_reader),
                "timelines": _timeline_rows(market_reader, base),
            }
        )
    )
