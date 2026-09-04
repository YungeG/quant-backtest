from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from crypto_quant_backtest import (
    ArtifactInstallMode,
    AttemptConsistencySet,
    AttemptEvidenceWriter,
    AttemptIdentity,
    AuditableBacktestRunner,
    BuildArtifactRef,
    BuildArtifactRole,
    CanonicalResultPublisher,
    DecisionSchedule,
    DecisionScheduleEntry,
    ExecutionResultHasher,
    InputOrigin,
    PortfolioStrategyInvocationContext,
    PortfolioStrategyRegistration,
    PrecomputedTargetStreamAdapter,
    ResolvedExecutionCase,
    SourceTreeState,
    StrategyCheckpoint,
    StrategyState,
    TimelineEvent,
    TimelineSegment,
    TimelineWindow,
    UniverseKind,
    UniverseQuery,
    UniverseSelection,
    invoke_portfolio_strategies,
)
from crypto_quant_domain import (
    CanonicalSchema,
    SimulationInstant,
    SourceSequence,
    StrategyDecisionCandidate,
    StrategyDecisionPayload,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import DecisionBatchExpectation
from tests.runtime.engine._fixtures import (
    BTC,
    SLEEVE,
    STRATEGY_ID,
    catalog,
    target_payload,
)
from tests.runtime.execution_hash._fixtures import ready_branch
from tests.runtime.integrity._fixtures import rebuild_evidence
from tests.runtime.runner._fixtures import resolved_request_and_case


FIXTURE_ID = "precomputed-vs-strategy-g11j-v1"
_ENTRY_ONLY_KEYS = {
    "precomputed": {
        "decision_batch_hash",
        "decision_batch_id",
        "injection_hash",
        "schedule_hash",
        "source_event_hashes",
        "source_event_ids",
        "target_stream_digest",
    },
    "strategy": {
        "checkpoint_hashes",
        "decision_batch_hash",
        "decision_batch_id",
        "context_hashes",
        "eligibility_hash",
        "handoff_hash",
        "invocation_hashes",
        "model_timeline_hashes",
        "observation_result_hashes",
        "output_hash",
        "random_stream_hashes",
        "schedule_hash",
        "state_transition_hashes",
        "strategy_artifact_hashes",
        "universe_selection_hashes",
        "window_result_hashes",
    },
}


def entry_only_keys() -> dict[str, set[str]]:
    return {name: set(values) for name, values in _ENTRY_ONLY_KEYS.items()}


@dataclass(frozen=True)
class _TargetStrategy:
    strategy_artifact: BuildArtifactRef

    def decide(
        self,
        *,
        context: PortfolioStrategyInvocationContext,
        previous_state: StrategyState,
    ) -> object:
        del context
        return (
            StrategyDecisionCandidate(StrategyDecisionPayload(target_payload())),
            previous_state,
            (),
        )


def _strategy_entry(decision_instant: SimulationInstant):
    entry = DecisionScheduleEntry(
        decision_instant,
        TimelineSegment.ACTIVE_TRADING,
    )
    schedule = DecisionSchedule(
        key="g11j.dual-entry.v1",
        version=1,
        window=TimelineWindow(UtcInstant(0), UtcInstant(90), UtcInstant(300)),
        entries=(entry,),
        requirements=(),
    )
    eligibility = schedule.eligibility(entry, ())
    expectation = DecisionBatchExpectation(STRATEGY_ID, SLEEVE)
    artifact = BuildArtifactRef(
        role=BuildArtifactRole.DECISION_SOURCE,
        artifact_key="g11j.source-neutral-target-strategy",
        artifact_version="1",
        install_mode=ArtifactInstallMode.WHEEL,
        source_tree_state=SourceTreeState.CLEAN,
        content_hash=canonical_sha256(
            {
                "type": "g11j_source_neutral_target_strategy",
                "schema_version": 1,
            }
        ),
        source_snapshot_hash=None,
    )
    genesis = SimulationInstant(
        UtcInstant(0),
        TimelinePhase(0, "genesis"),
        SourceSequence(0),
    )
    revision_hash = canonical_sha256(
        {
            "type": "g11j_static_universe_revision",
            "schema_version": 1,
            "instrument_id": BTC,
        }
    )
    universe = UniverseSelection(
        query=UniverseQuery(
            "g11j.synthetic.cash.v1",
            UniverseKind.STATIC,
            decision_instant,
        ),
        instruments=(BTC,),
        selected_revision_hashes=(revision_hash,),
        candidate_revision_hashes=(revision_hash,),
        max_selected_available_at=genesis,
        point_in_time=False,
        static_universe=True,
        survivorship_bias_safe=False,
        decision_grade_eligible=False,
        deployment_authorized=False,
    )
    checkpoint = StrategyCheckpoint(
        checkpoint_key="g11j-genesis",
        captured_at=genesis,
        state=StrategyState(
            strategy_id=SLEEVE,
            state_schema=CanonicalSchema("g11j.strategy.state", 1),
            values={"invocations": 0},
        ),
    )
    output = invoke_portfolio_strategies(
        eligibility=eligibility,
        instrument_catalog=catalog(),
        registrations=(
            PortfolioStrategyRegistration(
                expectation=expectation,
                strategy_artifact=artifact,
                strategy=_TargetStrategy(artifact),
                observation_results=(),
                universe=universe,
                windows=(),
                previous_checkpoint=checkpoint,
                random_streams=(),
                model_timelines=(),
            ),
        ),
    )
    result = output.batch_result
    if result is None or result.batch is None or result.state is None:
        raise AssertionError("expected successful G11J Strategy entry")
    invocations = output.invocations
    return (
        result.batch,
        result.state,
        {
            "checkpoint_hashes": [checkpoint.checkpoint_hash],
            "context_hashes": [value.context.context_hash for value in invocations],
            "decision_batch_hash": canonical_sha256(result.batch),
            "decision_batch_id": result.batch.decision_batch_id,
            "eligibility_hash": eligibility.eligibility_hash,
            "handoff_hash": output.handoff_hash,
            "invocation_hashes": [value.invocation_hash for value in invocations],
            "model_timeline_hashes": [],
            "observation_result_hashes": [],
            "output_hash": output.output_hash,
            "random_stream_hashes": [],
            "schedule_hash": schedule.schedule_hash,
            "state_transition_hashes": [
                canonical_sha256(value.state_transition)
                for value in invocations
                if value.state_transition is not None
            ],
            "strategy_artifact_hashes": [artifact.content_hash],
            "universe_selection_hashes": [universe.selection_hash],
            "window_result_hashes": [],
        },
    )


def _precomputed_entry(case: ResolvedExecutionCase):
    cycle = next(
        value
        for value in case.decision_cycles
        if value.schedule.segment is TimelineSegment.ACTIVE_TRADING
    )
    event_ids = {entry.event_id for entry in cycle.schedule.entries}
    events = tuple(
        event for event in case.target_stream.events if event.event_id in event_ids
    )
    decision_instant = events[-1].timeline_instant
    if decision_instant.instant != cycle.schedule.decision_time:
        raise AssertionError("G11J target event must bind the shared exact instant")
    outcome = PrecomputedTargetStreamAdapter().inject(
        stream=case.target_stream,
        timeline_events=tuple(
            TimelineEvent(cycle.schedule.segment, event) for event in events
        ),
        schedule=cycle.schedule,
    )
    injection = outcome.injection
    if injection is None:
        raise AssertionError("expected successful G11J precomputed entry")
    return (
        injection.batch,
        injection.state,
        decision_instant,
        {
            "decision_batch_hash": injection.batch_hash,
            "decision_batch_id": injection.batch.decision_batch_id,
            "injection_hash": injection.injection_hash,
            "schedule_hash": injection.schedule_hash,
            "source_event_hashes": list(injection.source_event_hashes),
            "source_event_ids": list(injection.source_event_ids),
            "target_stream_digest": injection.target_stream_digest,
        },
    )


def _normalized_decisions(batch, decision_instant: SimulationInstant):
    if batch.decision_time != decision_instant.instant:
        raise AssertionError("G11J source batch must match the exact decision instant")
    return tuple(
        replace(decision, decision_instant=decision_instant)
        for decision in batch.decisions
    )


def _projection(
    *,
    semantic_run_id: str,
    case: ResolvedExecutionCase,
    decision_instant: SimulationInstant,
    normalized_decisions,
    attempt_hash,
) -> dict[str, object]:
    result = attempt_hash.engine_result
    if result.case_hash != case.case_hash:
        raise AssertionError("G11J Engine Result must bind its composed case")
    if len(result.decision_batches) != 1 or _normalized_decisions(
        result.decision_batches[0], decision_instant
    ) != normalized_decisions:
        raise AssertionError("G11J normalized entry must bind the Engine source batch")
    payload = {
        "fixture_id": FIXTURE_ID,
        "layers": {
            "00_NORMALIZED_ENTRY": {
                "type": "normalized_entry_v1",
                "decision_instant": decision_instant,
                "execution_case_hash": case.case_hash,
                "semantic_run_id": semantic_run_id,
                "validated_decisions": normalized_decisions,
                "target_snapshots": tuple(
                    decision.target_snapshot for decision in normalized_decisions
                ),
            },
            "01_DECISION_BATCH": result.decision_batches,
            "02_ALLOCATION": result.allocations,
            "03_PORTFOLIO_RISK": result.approved_targets,
            "04_NORMALIZED_ACTIVE_TARGET": result.normalized_targets,
            "05_ORDER_PLAN_INTENT": result.order_plans,
            "06_ORDER_EVENT": result.order_streams,
            "07_FILL": result.fills,
            "08_SLIPPAGE": result.slippage_decisions,
            "09_FEE": result.fee_assessments,
            "10_FINANCIAL_ARTIFACT": result.financial_artifacts,
            "11_JOURNAL": result.final_journal.entries,
            "12_LEDGER": result.final_ledger_state,
            "13_FINAL_SNAPSHOT": result.final_portfolio_snapshot,
            "14_RUN_END": result.run_end_report,
            "15_TRACE": result.trace,
            "16_EXECUTION_RESULT_HASH": {
                "case_hash": result.case_hash,
                "engine_result_hash": result.result_hash,
                "execution_result_hash": attempt_hash.execution_result_hash,
                "journal_hash": result.final_journal.journal_hash,
                "ledger_state_hash": result.final_ledger_state.state_hash,
                "run_end_report_hash": result.run_end_report.report_hash,
                "semantic_run_id": semantic_run_id,
                "snapshot_hash": canonical_sha256(result.final_portfolio_snapshot),
                "trace_hash": result.trace.trace_hash,
            },
        },
        "qualification": {
            "decision_grade_eligible": False,
            "deployment_authorized": False,
        },
        "schema_version": 1,
    }
    decoded = json.loads(canonical_bytes(payload))
    if not isinstance(decoded, dict):
        raise AssertionError("G11J projection must be a JSON object")
    return decoded


def dual_entry_projections(
    root: Path,
) -> tuple[dict[str, object], dict[str, object], dict[str, Any]]:
    expected_request, expected_case = resolved_request_and_case()
    actual_request, actual_case = resolved_request_and_case()
    if expected_request != actual_request or expected_case != actual_case:
        raise AssertionError("G11J legs must resolve independently to equal values")

    precomputed_batch, _, entry_instant, precomputed_evidence = _precomputed_entry(
        expected_case
    )
    strategy_batch, _, strategy_evidence = _strategy_entry(entry_instant)
    actual_batch, _, actual_instant, _ = _precomputed_entry(actual_case)
    expected_decisions = _normalized_decisions(precomputed_batch, entry_instant)
    actual_decisions = _normalized_decisions(strategy_batch, entry_instant)
    if (
        expected_decisions != actual_decisions
        or expected_decisions
        != _normalized_decisions(actual_batch, actual_instant)
        or entry_instant != actual_instant
    ):
        raise AssertionError("G11J normalized validated Decisions must be exactly equal")
    if (
        precomputed_batch.decision_batch_id == strategy_batch.decision_batch_id
        or canonical_sha256(precomputed_batch) == canonical_sha256(strategy_batch)
    ):
        raise AssertionError("G11J source DecisionBatch identities must remain distinct")

    runner = AuditableBacktestRunner(publication_root=root)
    first = runner.execute(
        resolved_request=expected_request,
        execution_case=expected_case,
        attempt=AttemptIdentity.first(expected_request.semantic_run_id),
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )
    second = runner.retry_from_start(
        previous=first,
        resolved_request=actual_request,
        execution_case=actual_case,
        next_attempt_ordinal=2,
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )
    writer = AttemptEvidenceWriter(root=root)
    first_evidence = writer.publish(first).finalized
    second_evidence = writer.publish(second).finalized
    if first_evidence is None or second_evidence is None:
        raise AssertionError("expected finalized G11J Attempt evidence")
    first_hash = ExecutionResultHasher.bind(ready_branch(first), first_evidence)
    second_hash = ExecutionResultHasher.bind(ready_branch(second), second_evidence)
    attempts = AttemptConsistencySet(
        expected_request,
        (first_hash, second_hash),
        (first_evidence, second_evidence),
    )
    publication = CanonicalResultPublisher(root=root).publish(
        resolved_request=expected_request,
        attempt_hashes=attempts.attempt_hashes,
        finalized_attempts=attempts.finalized_attempts,
        rebuild_evidence=rebuild_evidence(attempts),
    )
    if publication.finalized_result is None:
        raise AssertionError("expected canonical G11J G07 Result")

    expected = _projection(
        semantic_run_id=expected_request.semantic_run_id,
        case=expected_case,
        decision_instant=entry_instant,
        normalized_decisions=expected_decisions,
        attempt_hash=first_hash,
    )
    actual = _projection(
        semantic_run_id=actual_request.semantic_run_id,
        case=actual_case,
        decision_instant=entry_instant,
        normalized_decisions=actual_decisions,
        attempt_hash=second_hash,
    )
    manifests = (expected_case.identity_manifest, actual_case.identity_manifest)
    if any(manifest is None for manifest in manifests):
        raise AssertionError("G11J cases require identity manifests")
    sidecar = {
        "entry_evidence": {
            "precomputed": precomputed_evidence,
            "strategy": strategy_evidence,
        },
        "g07": {
            "attempt_ids": [
                first_hash.attempt.attempt_id,
                second_hash.attempt.attempt_id,
            ],
            "canonical_result_hash": publication.finalized_result.result.result_hash,
            "evidence_directories": [
                first_evidence.relative_directory,
                second_evidence.relative_directory,
            ],
            "evidence_manifest_hashes": [
                first_evidence.manifest.manifest_hash,
                second_evidence.manifest.manifest_hash,
            ],
            "execution_case_hashes": [
                first_hash.engine_result.case_hash,
                second_hash.engine_result.case_hash,
            ],
            "execution_result_hashes": [
                first_hash.execution_result_hash,
                second_hash.execution_result_hash,
            ],
            "identity_manifest_hashes": [
                manifest.manifest_hash for manifest in manifests if manifest is not None
            ],
            "semantic_run_ids": [
                first_hash.attempt.semantic_run_id,
                second_hash.attempt.semantic_run_id,
            ],
        },
    }
    return expected, actual, sidecar
