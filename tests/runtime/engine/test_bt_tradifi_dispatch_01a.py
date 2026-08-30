from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest
from crypto_quant_backtest import (
    AuditableBacktestRunner,
    BinanceUsdmTradifiLinearFinancialDispatcher,
    ConservativeLinearLiquidationAuditModel,
    DefaultCashFinancialDispatcher,
    DeterministicBarEngine,
    FeeAccountingDispatchPlan,
    FillAccountingDispatchPlan,
    FinancialDispatcherSpec,
    FinancialDispatchFailureCode,
    FinancialStateView,
    default_cash_financial_dispatcher_spec,
    financial_dispatcher_for_spec,
    financial_dispatcher_owns_fee_accounting,
)
from crypto_quant_backtest.financial_dispatch import LinearDerivativeFillAccountingPlan
from crypto_quant_domain import (
    CashBalanceKey,
    CurrencyId,
    DomainIdKind,
    FeeBasisType,
    OrderSide,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal,
    FeeAssessmentBasisEvidence,
    FeeAssessmentEngine,
    FinalFeeRuleSet,
    GenericLedger,
    LedgerBalanceRegistration,
    LedgerSchema,
    LinearAccountMarginProjectorV2,
    LinearDerivativeAccounting,
    LinearDerivativeAccountingResult,
    LinearPositionTransitionKind,
    ProfileComponentRef,
    ProfilePortType,
    ReservationCommitment,
    ResourceReservationState,
)

from tests.kernel.derivatives._fixtures import (
    ACCOUNT_ID,
    QUOTE_CURRENCY,
    VENUE_ID,
    contract,
    domain_id,
    fill,
    position_key,
)
from tests.runtime.engine._financial_dispatch_fixtures import v2_cash_plan
from tests.runtime.engine._fixtures import execution_case, final_fee_rule_set


def _component(port_type: ProfilePortType, key: str) -> ProfileComponentRef:
    return ProfileComponentRef(
        port_type,
        key,
        1,
        canonical_sha256({"component_key": key, "component_version": 1}),
    )


def _tradifi_spec() -> FinancialDispatcherSpec:
    return FinancialDispatcherSpec(
        "crypto.binance_usdm.tradifi.linear-financial-dispatch.v1",
        1,
        canonical_sha256({"type": "accepted-tradifi-test-config"}),
        LinearDerivativeAccounting().component_ref,
        _component(
            ProfilePortType.FINANCING_MODEL,
            "crypto.binance_usdm.tradifi.linear-funding-composition.v1",
        ),
        _component(
            ProfilePortType.MARGIN_MODEL,
            "crypto.binance_usdm.tradifi.linear-margin-composition.v1",
        ),
        ConservativeLinearLiquidationAuditModel().component_ref,
        "crypto.binance_usdm.tradifi.linear-snapshot.v1",
        1,
    )


def _cash_registration() -> LedgerBalanceRegistration:
    return LedgerBalanceRegistration(
        CashBalanceKey(ACCOUNT_ID, VENUE_ID, QUOTE_CURRENCY),
        Scale(2),
    )


def _ledger() -> GenericLedger:
    return GenericLedger(
        LedgerSchema(
            (
                _cash_registration(),
                LedgerBalanceRegistration(position_key(), Scale(3)),
            )
        )
    )


def _state(journal: AccountingJournal) -> FinancialStateView:
    ledger_state = _ledger().project(journal)
    return FinancialStateView(
        journal,
        ledger_state,
        ResourceReservationState(
            ACCOUNT_ID,
            (),
            (),
            ReservationCommitment.empty(),
        ),
        (),
        (),
    )


def _fee_rule_set() -> FinalFeeRuleSet:
    base = final_fee_rule_set()
    return FinalFeeRuleSet.create(
        market_fee_policy_ref=base.market_fee_policy_ref,
        tax_policy_ref=base.tax_policy_ref,
        account_fee_schedule_ref=base.account_fee_schedule_ref,
        assessment_currency=QUOTE_CURRENCY,
        assessment_scale=Scale(2),
        charge_rules=tuple(
            rule for rule in base.charge_rules if rule.basis_type is FeeBasisType.FILL
        ),
        minimums=(),
    )


def _plan(fill_value, index: int) -> FillAccountingDispatchPlan:
    recorded_at = SimulationInstant(
        fill_value.execution_time,
        TimelinePhase(10, "accounting"),
        SourceSequence(index),
    )
    fee_time = UtcInstant(fill_value.execution_time.epoch_nanoseconds + 1)
    payload = LinearDerivativeFillAccountingPlan(
        position_key(),
        contract(),
        _cash_registration(),
        QuantizationPolicy("tradifi-test-pnl", Scale(2), RoundingPolicy.HALF_EVEN),
    )
    return FillAccountingDispatchPlan(
        f"tradifi-fill-{index}",
        fill_value.fill_id,
        _tradifi_spec().position_accounting_component,
        payload,
        payload,
        domain_id(DomainIdKind.JOURNAL, f"{index:x}"),
        recorded_at,
        FeeAccountingDispatchPlan(
            cast(CashBalanceKey, _cash_registration().key),
            _fee_rule_set(),
            domain_id(DomainIdKind.FEE, f"{index:x}"),
            fee_time,
            domain_id(DomainIdKind.JOURNAL, f"{index + 8:x}"),
            SimulationInstant(
                fee_time,
                TimelinePhase(10, "accounting"),
                SourceSequence(index + 10),
            ),
        ),
        (f"position_accounting.{index}",),
    )


def test_exact_financial_dispatcher_selector() -> None:
    spec = _tradifi_spec()
    cash = financial_dispatcher_for_spec(default_cash_financial_dispatcher_spec())
    tradifi = financial_dispatcher_for_spec(spec)

    assert type(cash) is DefaultCashFinancialDispatcher
    assert type(tradifi) is BinanceUsdmTradifiLinearFinancialDispatcher
    assert tradifi.spec is spec

    mixed = replace(
        _tradifi_spec(),
        position_accounting_component=(
            default_cash_financial_dispatcher_spec().position_accounting_component
        ),
    )
    unknown = replace(_tradifi_spec(), dispatcher_key="unknown.dispatcher.v1")
    with pytest.raises(ValueError, match="unsupported Binance USD-M TradFi"):
        financial_dispatcher_for_spec(mixed)
    with pytest.raises(ValueError, match="unsupported Binance USD-M TradFi"):
        financial_dispatcher_for_spec(unknown)


def test_tradifi_dispatcher_rejects_nonexact_v2_margin_component() -> None:
    v2 = LinearAccountMarginProjectorV2().component_ref
    forged = replace(v2, component_digest="sha256:" + "a1" * 32)

    with pytest.raises(ValueError, match="unsupported Binance USD-M TradFi margin component"):
        BinanceUsdmTradifiLinearFinancialDispatcher(
            replace(_tradifi_spec(), margin_component=forged)
        )


def test_fee_accounting_ownership_routing_is_generic_and_fail_closed() -> None:
    fill_value = fill(
        "1",
        side=OrderSide.BUY,
        quantity_units=1_000,
        price_units=10_000,
        execution_nanoseconds=1,
    )
    derivative_plan = _plan(fill_value, 1)
    tradifi = BinanceUsdmTradifiLinearFinancialDispatcher(_tradifi_spec())
    legacy_cash_plan = execution_case().bar_executions[0].accounting_plan

    assert financial_dispatcher_owns_fee_accounting(tradifi, derivative_plan)
    assert financial_dispatcher_owns_fee_accounting(
        DefaultCashFinancialDispatcher(), v2_cash_plan()
    )
    assert not financial_dispatcher_owns_fee_accounting(
        DefaultCashFinancialDispatcher(), legacy_cash_plan
    )
    assert not financial_dispatcher_owns_fee_accounting(object(), derivative_plan)
    assert not financial_dispatcher_owns_fee_accounting(
        tradifi,
        replace(derivative_plan, position_payload=execution_case().snapshot_plan),
    )


def test_default_engine_auto_selects_exact_tradifi_once_on_central_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    import crypto_quant_backtest._durable_rebuild as durable
    import crypto_quant_backtest.engine as engine_module

    spec = _tradifi_spec()
    base_case = execution_case()
    tradifi_case = replace(
        base_case,
        financial_dispatch_plan=replace(
            base_case.financial_dispatch_plan,
            dispatcher_spec=spec,
        ),
    )
    selections = []
    executions = []
    marker = object()

    def select(selected_spec):
        selections.append(selected_spec)
        return financial_dispatcher_for_spec(selected_spec)

    def execute(self, selected_case, cancellation):
        executions.append((self._financial_dispatcher, selected_case, cancellation))
        return marker

    monkeypatch.setattr(engine_module, "financial_dispatcher_for_spec", select)
    monkeypatch.setattr(DeterministicBarEngine, "_execute", execute)
    runner = AuditableBacktestRunner(publication_root=tmp_path)
    central_engine = runner._engine  # pyright: ignore[reportPrivateUsage]

    assert central_engine.run(tradifi_case) is marker
    assert selections == [spec]
    assert len(executions) == 1
    selected_dispatcher, selected_case, cancellation = executions[0]
    assert type(selected_dispatcher) is BinanceUsdmTradifiLinearFinancialDispatcher
    assert selected_dispatcher.spec is spec
    assert selected_case is tradifi_case
    assert cancellation is None
    assert type(selected_dispatcher) is not DefaultCashFinancialDispatcher
    assert durable.DeterministicBarEngine is DeterministicBarEngine  # pyright: ignore[reportPrivateImportUsage]

    fill_value = fill(
        "1",
        side=OrderSide.BUY,
        quantity_units=1_000,
        price_units=10_000,
        execution_nanoseconds=1,
    )
    rejected = DefaultCashFinancialDispatcher().book_fill(
        _plan(fill_value, 1),
        fill_value,
        _state(AccountingJournal.empty()),
    )
    assert rejected.result is None
    assert rejected.failure is not None


def test_tradifi_fill_dispatch_replays_open_add_reduce_close_and_reversal() -> None:
    dispatcher = BinanceUsdmTradifiLinearFinancialDispatcher(_tradifi_spec())
    fills = (
        fill(
            "1",
            side=OrderSide.BUY,
            quantity_units=1_000,
            price_units=10_000,
            execution_nanoseconds=1,
        ),
        fill(
            "2",
            side=OrderSide.BUY,
            quantity_units=500,
            price_units=11_000,
            execution_nanoseconds=2,
        ),
        fill(
            "3",
            side=OrderSide.SELL,
            quantity_units=600,
            price_units=12_000,
            execution_nanoseconds=3,
        ),
        fill(
            "4",
            side=OrderSide.SELL,
            quantity_units=900,
            price_units=12_500,
            execution_nanoseconds=4,
        ),
        fill(
            "5",
            side=OrderSide.BUY,
            quantity_units=500,
            price_units=13_000,
            execution_nanoseconds=5,
        ),
        fill(
            "6",
            side=OrderSide.SELL,
            quantity_units=1_000,
            price_units=12_000,
            execution_nanoseconds=6,
        ),
    )
    expected_kinds = (
        LinearPositionTransitionKind.OPEN,
        LinearPositionTransitionKind.ADD,
        LinearPositionTransitionKind.REDUCE,
        LinearPositionTransitionKind.CLOSE,
        LinearPositionTransitionKind.OPEN,
        LinearPositionTransitionKind.FLIP,
    )
    journal = AccountingJournal.empty()

    for index, (fill_value, expected_kind) in enumerate(
        zip(fills, expected_kinds, strict=True), start=1
    ):
        outcome = dispatcher.book_fill(
            _plan(fill_value, index), fill_value, _state(journal)
        )
        assert outcome.failure is None
        assert outcome.result is not None
        assert len(outcome.result.journal_entries) == 1
        assert len(outcome.result.artifacts) == 1
        artifact_payload = outcome.result.artifacts[0].payload
        assert type(artifact_payload) is LinearDerivativeAccountingResult
        assert artifact_payload.request.transition.kind is expected_kind
        assert artifact_payload.journal_entry is outcome.result.journal_entries[0]
        journal = journal.append(outcome.result.journal_entries[0])


def test_tradifi_fill_rejects_changed_contract_before_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatcher = BinanceUsdmTradifiLinearFinancialDispatcher(_tradifi_spec())
    first_fill = fill(
        "1",
        side=OrderSide.BUY,
        quantity_units=1_000,
        price_units=10_000,
        execution_nanoseconds=1,
    )
    first = dispatcher.book_fill(
        _plan(first_fill, 1), first_fill, _state(AccountingJournal.empty())
    )
    assert first.result is not None
    journal = AccountingJournal.from_entries(first.result.journal_entries)
    second_fill = fill(
        "2",
        side=OrderSide.BUY,
        quantity_units=500,
        price_units=11_000,
        execution_nanoseconds=2,
    )
    second_plan = _plan(second_fill, 2)
    payload = second_plan.position_payload
    assert type(payload) is LinearDerivativeFillAccountingPlan
    changed_payload = replace(
        payload,
        contract=replace(
            payload.contract,
            contract_multiplier=Rate(126, Scale(3), "base_quantity_per_contract"),
        ),
    )
    second_plan = replace(
        second_plan,
        position_payload=changed_payload,
        semantic_payload=changed_payload,
    )

    def unexpected_projection(*args, **kwargs):
        pytest.fail("changed contract reached position projection")

    monkeypatch.setattr(
        "crypto_quant_backtest.financial_dispatch.LinearPositionProjector.project",
        unexpected_projection,
    )
    outcome = dispatcher.book_fill(second_plan, second_fill, _state(journal))

    assert outcome.result is None
    assert outcome.failure is not None
    assert (
        outcome.failure.code is FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE
    )
    assert outcome.failure.subject_ids == ("contract_mismatch",)


def test_tradifi_fill_component_and_fee_mismatches_fail_closed() -> None:
    dispatcher = BinanceUsdmTradifiLinearFinancialDispatcher(_tradifi_spec())
    fill_value = fill(
        "7",
        side=OrderSide.BUY,
        quantity_units=1_000,
        price_units=10_000,
        execution_nanoseconds=7,
    )
    plan = _plan(fill_value, 7)
    mismatched = dispatcher.book_fill(
        replace(plan, expected_fill_id=domain_id(DomainIdKind.FILL, "8")),
        fill_value,
        _state(AccountingJournal.empty()),
    )
    assert mismatched.failure is not None
    assert mismatched.failure.code is FinancialDispatchFailureCode.FILL_PLAN_MISMATCH

    payload = plan.position_payload
    assert type(payload) is LinearDerivativeFillAccountingPlan
    wrong_registration = LedgerBalanceRegistration(
        CashBalanceKey(ACCOUNT_ID, VENUE_ID, CurrencyId("USD")),
        Scale(2),
    )
    component_failure = dispatcher.book_fill(
        replace(
            plan,
            position_payload=replace(
                payload,
                settlement_cash_registration=wrong_registration,
            ),
        ),
        fill_value,
        _state(AccountingJournal.empty()),
    )
    assert component_failure.failure is not None
    assert (
        component_failure.failure.code
        is FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE
    )

    assessed = FeeAssessmentEngine().assess(
        basis=FeeAssessmentBasisEvidence.for_fill(fill_value),
        rule_set=plan.fee_plan.final_fee_rule_set,
        fee_assessment_id=plan.fee_plan.fee_assessment_id,
        assessment_time=plan.fee_plan.fee_assessment_time,
    )
    assert assessed.result is not None
    fee_mismatch = dispatcher.book_fee(
        replace(
            plan,
            fee_plan=replace(
                plan.fee_plan,
                fee_assessment_id=domain_id(DomainIdKind.FEE, "8"),
            ),
        ),
        fill_value,
        assessed.result,
        _state(AccountingJournal.empty()),
    )
    assert fee_mismatch.failure is not None
    assert fee_mismatch.failure.code is FinancialDispatchFailureCode.FILL_PLAN_MISMATCH


def test_tradifi_taker_fee_dispatch_returns_projectable_journal_entry() -> None:
    dispatcher = BinanceUsdmTradifiLinearFinancialDispatcher(_tradifi_spec())
    fill_value = fill(
        "7",
        side=OrderSide.BUY,
        quantity_units=1_000,
        price_units=10_000,
        execution_nanoseconds=7,
    )
    plan = _plan(fill_value, 7)
    fill_outcome = dispatcher.book_fill(
        plan, fill_value, _state(AccountingJournal.empty())
    )
    assert fill_outcome.result is not None
    journal = AccountingJournal.from_entries(fill_outcome.result.journal_entries)
    assessed = FeeAssessmentEngine().assess(
        basis=FeeAssessmentBasisEvidence.for_fill(fill_value),
        rule_set=plan.fee_plan.final_fee_rule_set,
        fee_assessment_id=plan.fee_plan.fee_assessment_id,
        assessment_time=plan.fee_plan.fee_assessment_time,
    )
    assert assessed.result is not None
    assert assessed.result.assessment.amount.units > 0

    outcome = dispatcher.book_fee(plan, fill_value, assessed.result, _state(journal))

    assert outcome.failure is None
    assert outcome.result is not None
    assert outcome.result.artifacts == ()
    fee_entry = outcome.result.journal_entries[0]
    projected = _ledger().project(journal.append(fee_entry))
    assert (
        projected.cash_amount(cast(CashBalanceKey, _cash_registration().key)).units
        == -assessed.result.assessment.amount.units
    )
