from __future__ import annotations

from pathlib import Path

from crypto_quant_backtest import (
    AttemptIdentity,
    AuditableBacktestRunner,
    DeterministicBarEngine,
    InputOrigin,
)
from crypto_quant_domain import AccountingEntryType, canonical_sha256
from crypto_quant_trading import (
    GenericLedger,
    LinearDerivativeJournalEntry,
    LinearDerivativeLedgerProjector,
    LinearDerivativeLedgerReplayRequest,
    LinearFundingJournalEntry,
    LinearPositionTransitionKind,
)
from tests.support.synthetic_market import (
    SyntheticLinearPerpetualDevelopmentProfile,
    TestProfileRegistry,
    build_synthetic_linear_perpetual_execution_case,
    build_synthetic_linear_perpetual_resolved_request,
)
from tests.support.synthetic_market.linear_perpetual import (
    CONTRACT,
    PROFILE_KEY,
    SyntheticLinearFinancialDispatcher,
)
from tests.runtime.engine import _fixtures as cash


def _run(*, batch_size: int = 1):
    lookup = TestProfileRegistry(allow_development_profiles=True).lookup(PROFILE_KEY)
    profile = lookup.profile
    assert isinstance(profile, SyntheticLinearPerpetualDevelopmentProfile)
    resolved = build_synthetic_linear_perpetual_resolved_request(
        profile,
        timeline_batch_size=batch_size,
    )
    case = build_synthetic_linear_perpetual_execution_case(
        profile,
        timeline_batch_size=batch_size,
        resolved_request=resolved,
    )
    outcome = DeterministicBarEngine(SyntheticLinearFinancialDispatcher()).run(case)
    assert outcome.result is not None
    return resolved, case, outcome.result


def test_journey_is_long_open_partial_reduce_funding_then_flip_short() -> None:
    _, _, result = _run()
    derivative_entries = tuple(
        entry
        for entry in result.final_journal.entries
        if type(entry) is LinearDerivativeJournalEntry
    )
    transitions = tuple(entry.request.transition.kind for entry in derivative_entries)
    expected_transitions = (
        LinearPositionTransitionKind.OPEN,
        LinearPositionTransitionKind.REDUCE,
        LinearPositionTransitionKind.FLIP,
    )

    assert transitions == expected_transitions
    funding_entry_count = sum(
        type(entry) is LinearFundingJournalEntry
        for entry in result.final_journal.entries
    )
    assert funding_entry_count == 1
    assert result.final_ledger_state.position_balances[0].quantity.units == -1_000
    expected_lots: tuple[object, ...] = ()
    assert result.final_ledger_state.position_balances[0].lots == expected_lots
    assert result.final_ledger_state.realized_pnl[0].amount.units == -60
    assert result.final_ledger_state.financing[0].amount.units == -3
    assert result.final_ledger_state.fees[0].amount.units == 91


def test_financial_artifacts_cover_funding_margin_liquidation_and_final_snapshot() -> None:
    _, case, result = _run()
    roles = tuple(sorted(artifact.role for artifact in result.financial_artifacts))

    assert roles == case.financial_dispatch_plan.expected_artifact_roles
    artifacts = {artifact.role: artifact for artifact in result.financial_artifacts}
    assert type(artifacts["funding_eligibility"].payload).__name__ == "LinearFundingEligibility"
    assert type(artifacts["funding_accounting"].payload).__name__ == "LinearFundingSettlementResult"
    assert artifacts["liquidation_audit.long"].payload.classification.value == "safe"
    assert artifacts["liquidation_audit.short"].payload.classification.value == "safe"
    assert canonical_sha256(artifacts["final_snapshot"].payload) == canonical_sha256(
        result.final_portfolio_snapshot
    )


def test_final_journal_reconstructs_generic_ledger_and_linear_position() -> None:
    _, case, result = _run()
    ledger = GenericLedger(case.financial_state.ledger_schema).project(result.final_journal)
    replay = LinearDerivativeLedgerProjector().project(
        LinearDerivativeLedgerReplayRequest(
            result.final_journal,
            case.financial_state.ledger_schema,
            cash.POSITION_KEY,
            CONTRACT,
            cash.CASH_KEY,
        )
    )

    assert canonical_sha256(ledger) == canonical_sha256(result.final_ledger_state)
    if replay.result is None:
        raise AssertionError("final Linear Journal replay failed")
    projection = replay.result
    assert projection.position_state.quantity.units == -1_000
    assert projection.realized_pnl.units == -60
    assert projection.ledger_state_hash == result.final_ledger_state.state_hash
    entry_types = tuple(entry.entry_type for entry in result.final_journal.entries)
    assert entry_types.count(AccountingEntryType.FILL_BOOKED) == 3
    assert entry_types.count(AccountingEntryType.FUNDING_APPLIED) == 1


def test_auditable_runner_preserves_development_only_linear_result(
    tmp_path: Path,
) -> None:
    resolved, case, direct = _run()
    first = AttemptIdentity.first(resolved.semantic_run_id)
    second = AttemptIdentity.retry(first, next_ordinal=2)
    records = tuple(
        AuditableBacktestRunner(
            engine=DeterministicBarEngine(SyntheticLinearFinancialDispatcher()),
            publication_root=tmp_path / f"attempt-{index}",
        ).execute(
            resolved_request=resolved,
            execution_case=case,
            attempt=attempt,
            input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
        )
        for index, attempt in enumerate((first, second), start=1)
    )

    if next((record for record in records if record.ready_to_finalize is None), None):
        raise AssertionError("synthetic Linear Runner did not reach ready-to-finalize")
    result_hashes = tuple(
        record.ready_to_finalize.engine_result.result_hash
        for record in records
        if record.ready_to_finalize is not None
    )
    expected_hashes = (direct.result_hash, direct.result_hash)
    assert result_hashes == expected_hashes
    assert not resolved.environment.deployment_authorized


def test_timeline_batch_size_does_not_change_economic_or_artifact_identity() -> None:
    resolved_one, case_one, result_one = _run(batch_size=1)
    resolved_many, case_many, result_many = _run(batch_size=4)

    assert resolved_one.semantic_run_id == resolved_many.semantic_run_id
    assert case_one.case_hash == case_many.case_hash
    assert result_one.result_hash == result_many.result_hash
    artifact_hashes_one = tuple(
        value.artifact_hash for value in result_one.financial_artifacts
    )
    artifact_hashes_many = tuple(
        value.artifact_hash for value in result_many.financial_artifacts
    )
    assert artifact_hashes_one == artifact_hashes_many
