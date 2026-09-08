from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from crypto_quant_backtest import (
    DefaultCashFinancialDispatcher,
    DeterministicBarEngine,
    EngineFailureCode,
    FinancialDispatchFailureCode,
    FinancialStateView,
    default_cash_financial_dispatcher_spec,
)
from crypto_quant_domain import (
    DomainIdKind,
    Money,
    OrderSide,
    PositionBalanceKey,
    PositionLot,
    PositionLotChange,
    Price,
    Quantity,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal,
    CashInstrumentAccounting,
    FeeAssessmentBasisEvidence,
    FeeAssessmentEngine,
    GenericLedger,
    LedgerBalanceRegistration,
    LedgerSchema,
    ReservationCommitment,
    ResourceReservationState,
)

from tests.kernel.accounting._fixtures import (
    CASH_KEY,
    COST_BASIS_POLICY_V2,
    MONEY_SCALE,
    NOTIONAL_POLICY,
    POSITION_KEY,
    QUANTITY_SCALE,
    domain_id,
    fill,
    recorded_at,
)
from tests.kernel.accounting._fixtures import (
    COST_BASIS_POLICY as KERNEL_COST_BASIS_POLICY,
)
from tests.runtime.engine._financial_dispatch_fixtures import (
    lot_books_from_ledger,
    v2_cash_plan,
)
from tests.runtime.engine._fixtures import (
    MONEY_SCALE as RUNTIME_MONEY_SCALE,
)
from tests.runtime.engine._fixtures import (
    POSITION_KEY as RUNTIME_POSITION_KEY,
)
from tests.runtime.engine._fixtures import (
    QUANTITY_SCALE as RUNTIME_QUANTITY_SCALE,
)
from tests.runtime.engine._fixtures import SyntheticExecutionCaseBuilder, execution_case


def _kernel_ledger_schema() -> LedgerSchema:
    return LedgerSchema(
        (
            LedgerBalanceRegistration(CASH_KEY, MONEY_SCALE),
            LedgerBalanceRegistration(POSITION_KEY, QUANTITY_SCALE),
        )
    )


def _financial_state_view(
    journal: AccountingJournal,
    lot_books: tuple[tuple[PositionBalanceKey, tuple[PositionLot, ...]], ...],
) -> FinancialStateView:
    schema = _kernel_ledger_schema()
    ledger_state = GenericLedger(schema).project(journal)
    reservation_state = ResourceReservationState(
        CASH_KEY.account_id,
        (),
        (),
        ReservationCommitment.empty(),
    )
    return FinancialStateView(
        journal,
        ledger_state,
        reservation_state,
        lot_books,
        (),
    )


def test_engine_rejects_missing_or_invalid_financial_dispatcher() -> None:
    with pytest.raises(TypeError, match="FinancialEventDispatcher"):
        DeterministicBarEngine(None)
    with pytest.raises(TypeError, match="FinancialEventDispatcher"):
        DeterministicBarEngine(object())


def test_cash_execution_uses_canonical_financial_dispatch_plan() -> None:
    case = execution_case()

    outcome = DeterministicBarEngine().run(case)

    assert outcome.result is not None
    assert case.financial_dispatch_plan.dispatcher_spec == (
        default_cash_financial_dispatcher_spec()
    )
    roles = tuple(value.role for value in outcome.result.financial_artifacts)
    expected_roles = ("position_accounting", "final_snapshot")
    assert roles == expected_roles
    assert canonical_sha256(outcome.result.financial_artifacts[1].payload) == (
        canonical_sha256(outcome.result.final_portfolio_snapshot)
    )
    assert canonical_bytes(case) == canonical_bytes(execution_case())


def test_dispatcher_spec_mismatch_fails_before_fill_accounting() -> None:
    case = execution_case()
    wrong = replace(
        default_cash_financial_dispatcher_spec(),
        dispatcher_key="wrong.financial-dispatcher.v1",
    )
    dispatcher = DefaultCashFinancialDispatcher()
    object.__setattr__(dispatcher, "_spec", wrong)

    outcome = DeterministicBarEngine(dispatcher).run(case)

    assert outcome.result is None
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.code == EngineFailureCode.FINANCIAL_DISPATCH_FAILURE
    expected_subjects = (FinancialDispatchFailureCode.DISPATCHER_SPEC_MISMATCH.value,)
    assert outcome.engine_failure.subject_keys == expected_subjects


def test_financial_plan_changes_case_and_semantic_identity() -> None:
    case = execution_case()
    changed = replace(
        case.financial_dispatch_plan,
        expected_artifact_roles=("final_snapshot",),
    )

    changed_case = replace(case, financial_dispatch_plan=changed)

    assert changed_case.case_hash != case.case_hash
    assert canonical_sha256(changed) != canonical_sha256(case.financial_dispatch_plan)


def test_initial_lot_changes_alter_financial_semantics_without_changing_v1() -> None:
    from crypto_quant_backtest import ExecutionCaseComposer

    builder = SyntheticExecutionCaseBuilder()
    case = execution_case()
    expected_v1 = builder.semantic_spec()
    baseline = ExecutionCaseComposer.semantic_spec_from_case(
        case,
        spec_key=expected_v1.spec_key,
        spec_version=expected_v1.spec_version,
        identity_namespace=expected_v1.identity_namespace,
        identity_plan=expected_v1.identity_plan,
    )
    assert baseline == expected_v1

    initial_entry = case.financial_state.journal.entries[0]
    price = Price(
        10_000,
        RUNTIME_MONEY_SCALE,
        str(RUNTIME_POSITION_KEY.instrument_id),
        "USD",
    )
    lot = PositionLot(
        lot_id="lot:initial-v2",
        position_key=RUNTIME_POSITION_KEY,
        source_id="initial:v2",
        quantity=Quantity(
            1, RUNTIME_QUANTITY_SCALE, str(RUNTIME_POSITION_KEY.instrument_id)
        ),
        unit_cost=price,
        allocated_fees=(),
        opened_at=initial_entry.effective_time,
        total_cost_basis=Money(10_000, RUNTIME_MONEY_SCALE, "USD"),
    )
    altered_journal = AccountingJournal.from_entries(
        (
            replace(
                initial_entry,
                position_lot_changes=(PositionLotChange(None, lot),),
            ),
        )
    )
    altered_financial_state = replace(case.financial_state)
    object.__setattr__(altered_financial_state, "journal", altered_journal)
    altered_case = replace(case, financial_state=altered_financial_state)
    altered = ExecutionCaseComposer.semantic_spec_from_case(
        altered_case,
        spec_key=expected_v1.spec_key,
        spec_version=expected_v1.spec_version,
        identity_namespace=expected_v1.identity_namespace,
        identity_plan=expected_v1.identity_plan,
    )

    assert altered.financial_inputs_hash != baseline.financial_inputs_hash
    assert altered.semantic_spec_hash != baseline.semantic_spec_hash


def test_v2_book_fill_ignores_legacy_side_state_and_returns_exact_evidence() -> None:
    dispatcher = DefaultCashFinancialDispatcher()
    plan = v2_cash_plan()
    seed = fill(
        "1",
        side=OrderSide.BUY,
        quantity_units=10,
        price_units=10_000,
        execution_time=10,
    )
    seed_outcome = CashInstrumentAccounting().book_fill(
        fill=seed,
        cash_key=CASH_KEY,
        position_key=POSITION_KEY,
        open_lots=(),
        cost_basis_policy=COST_BASIS_POLICY_V2,
        notional_quantization=NOTIONAL_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "1"),
        recorded_at=recorded_at(10),
    )
    assert seed_outcome.result is not None
    initial_journal = AccountingJournal.from_entries(
        (seed_outcome.result.journal_entry,)
    )
    fill_fill = replace(
        fill(
            "2",
            side=OrderSide.SELL,
            quantity_units=2,
            price_units=11_000,
            execution_time=20,
        ),
        fill_id=plan.expected_fill_id,
    )
    state = _financial_state_view(initial_journal, ())
    outcome = dispatcher.book_fill(plan, fill_fill, state)
    assert outcome.input_hash == canonical_sha256(
        {
            "operation": "book_fill",
            "plan": plan,
            "fill": fill_fill,
            "journal_hash": initial_journal.journal_hash,
            "ledger_state_hash": state.ledger_state.state_hash,
        }
    )
    assert outcome.result is not None
    assert outcome.result.journal_entries

    result_lots = dict(outcome.result.position_lot_books)
    assert POSITION_KEY in result_lots
    remaining_lots = result_lots[POSITION_KEY]
    assert remaining_lots
    assert remaining_lots[0].lot_id == seed_outcome.result.open_lots[0].lot_id

    replay = GenericLedger(_kernel_ledger_schema()).project(
        AccountingJournal.from_entries(
            (
                seed_outcome.result.journal_entry,
                outcome.result.journal_entries[0],
            )
        )
    )
    assert lot_books_from_ledger(replay) == outcome.result.position_lot_books


def test_v2_fee_dispatch_uses_ledger_lots_and_returns_exact_evidence() -> None:
    dispatcher = DefaultCashFinancialDispatcher()
    plan = v2_cash_plan()
    target_fill = replace(
        fill(
            "2",
            side=OrderSide.BUY,
            quantity_units=10,
            price_units=10_000,
            execution_time=20,
        ),
        fill_id=plan.expected_fill_id,
    )
    initial_journal = AccountingJournal.from_entries(())
    fill_outcome = dispatcher.book_fill(
        plan,
        target_fill,
        _financial_state_view(initial_journal, ()),
    )
    assert fill_outcome.result is not None
    filled_journal = AccountingJournal.from_entries(fill_outcome.result.journal_entries)
    state = _financial_state_view(filled_journal, ())
    assessed = FeeAssessmentEngine().assess(
        basis=FeeAssessmentBasisEvidence.for_fill(target_fill),
        rule_set=plan.fee_plan.final_fee_rule_set,
        fee_assessment_id=plan.fee_plan.fee_assessment_id,
        assessment_time=plan.fee_plan.fee_assessment_time,
    )
    assert assessed.result is not None

    outcome = dispatcher.book_fee(plan, target_fill, assessed.result, state)

    assert outcome.input_hash == canonical_sha256(
        {
            "operation": "book_fee",
            "plan": plan,
            "fill": target_fill,
            "assessment": assessed.result,
            "journal_hash": filled_journal.journal_hash,
            "ledger_state_hash": state.ledger_state.state_hash,
        }
    )
    assert outcome.result is not None
    assert outcome.result.artifacts == ()
    replay = GenericLedger(_kernel_ledger_schema()).project(
        filled_journal.append_many(outcome.result.journal_entries)
    )
    assert lot_books_from_ledger(replay) == outcome.result.position_lot_books
    allocated_lot = dict(outcome.result.position_lot_books)[POSITION_KEY][0]
    assert allocated_lot.allocated_fees == (assessed.result.assessment.amount,)


def test_v2_fee_rejects_nonzero_position_with_empty_ledger_lot_books() -> None:
    dispatcher = DefaultCashFinancialDispatcher()
    plan = v2_cash_plan()
    seed = fill(
        "1",
        side=OrderSide.BUY,
        quantity_units=10,
        price_units=10_000,
        execution_time=10,
    )
    seed_outcome = CashInstrumentAccounting().book_fill(
        fill=seed,
        cash_key=CASH_KEY,
        position_key=POSITION_KEY,
        open_lots=(),
        cost_basis_policy=KERNEL_COST_BASIS_POLICY,
        notional_quantization=NOTIONAL_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "1"),
        recorded_at=recorded_at(10),
    )
    assert seed_outcome.result is not None
    initial_journal = AccountingJournal.from_entries(
        (seed_outcome.result.journal_entry,)
    )

    stale_lot = PositionLot(
        lot_id="lot:stale",
        position_key=POSITION_KEY,
        source_id="legacy",
        quantity=Quantity(10, QUANTITY_SCALE, str(POSITION_KEY.instrument_id)),
        unit_cost=seed.price,
        allocated_fees=(),
        opened_at=seed.execution_time,
        total_cost_basis=Money(0, MONEY_SCALE, str(seed.price.quote_currency)),
    )
    fill_fill = replace(
        fill(
            "2",
            side=OrderSide.SELL,
            quantity_units=2,
            price_units=11_000,
            execution_time=20,
        ),
        fill_id=plan.expected_fill_id,
    )
    state = _financial_state_view(
        initial_journal,
        ((POSITION_KEY, (stale_lot,)),),
    )
    assessed = FeeAssessmentEngine().assess(
        basis=FeeAssessmentBasisEvidence.for_fill(fill_fill),
        rule_set=plan.fee_plan.final_fee_rule_set,
        fee_assessment_id=plan.fee_plan.fee_assessment_id,
        assessment_time=plan.fee_plan.fee_assessment_time,
    )
    assert assessed.result is not None

    outcome = dispatcher.book_fee(plan, fill_fill, assessed.result, state)
    assert outcome.result is None
    assert outcome.failure is not None
    assert (
        outcome.failure.code.value
        == FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE.value
    )
    assert "position_lot_books" in outcome.failure.subject_ids


def test_v1_result_hash_parity_is_unchanged() -> None:
    fixture = json.loads(
        (
            Path(__file__).parents[3]
            / "tests/fixtures/runtime/deterministic-engine-orchestration-v1.json"
        ).read_text(encoding="utf-8")
    )

    outcome = DeterministicBarEngine().run(execution_case())
    assert outcome.result is not None
    assert outcome.result.result_hash == fixture["result_hash"]
