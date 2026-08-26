from __future__ import annotations

from dataclasses import replace

import pytest
from crypto_quant_backtest import (
    BinanceUsdmTradifiLinearFinancialDispatcher,
    BinanceUsdmTradifiProfileComposer,
    DeterministicBarEngine,
    FinancialDispatchFailureCode,
    FinancialDispatchOutcome,
    FinancialDispatchResult,
    FinancialStateView,
    LinearFundingAccountEventPlan,
    LinearMarginProjectionPlan,
    RequestedResultGrade,
)
from crypto_quant_backtest.composition import (
    _execution_case_semantic_spec_v3,
    _validate_financial_component_bindings,
)
from crypto_quant_backtest.execution_inputs import (
    _materialize_execution_input_bundle_v5,
    _materialize_execution_input_bundle_v6,
    _read_execution_input_payload_v6,
)
from crypto_quant_backtest.liquidation_audit import LinearLiquidationMarkBarEvidence
from crypto_quant_domain import (
    PricePurpose,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    GenericLedger,
    LinearFundingMarkEvidence,
    LinearFundingPublicationStatus,
    LinearFundingRatePublicationCandidate,
    LinearFundingSettlementEvidence,
    LinearMarginLeverageEvidence,
    LinearMarginMarkEvidence,
    LinearMarginRuleBook,
    ReservationCommitment,
    ResourceReservationState,
    StaleMarkPolicy,
)

from tests.runtime.engine import _fixtures as cash
from tests.runtime.execution_inputs.test_multi_resolution_bundle_v3 import (
    _contract,
    _resolved_for_spec,
)
from tests.runtime.profiles.binance_usdm._tradifi_fixtures import composition_request
from tests.support.synthetic_market.linear_perpetual import (
    CONTRACT,
    PROFILE_KEY,
    SETTLEMENT_REGISTRATION,
    SyntheticLinearFinancialDispatcher,
    _margin_rule_book,
    _resolved_mark,
    build_execution_case,
)


def _sim(value: int, phase: TimelinePhase) -> SimulationInstant:
    return SimulationInstant(UtcInstant(value), phase, SourceSequence(0))


def _projection_plan(
    *,
    evaluated_at: SimulationInstant,
    valuation_price,
    margin_price,
    suffix: str,
    valuation_mark=None,
    valuation_policy=None,
) -> LinearMarginProjectionPlan:
    resolved_valuation, resolved_valuation_policy = _resolved_mark(
        PricePurpose.VALUATION,
        valuation_price,
        evaluated_at,
        f"{suffix}.valuation",
    )
    resolved_margin, resolved_margin_policy = _resolved_mark(
        PricePurpose.MARGIN,
        margin_price,
        evaluated_at,
        f"{suffix}.margin",
    )
    return LinearMarginProjectionPlan(
        cash.ACCOUNT,
        cash.VENUE,
        cash.POSITION_KEY,
        CONTRACT,
        cash.ledger_schema(),
        cash.CASH_KEY,
        evaluated_at,
        resolved_valuation if valuation_mark is None else valuation_mark,
        (resolved_valuation_policy if valuation_policy is None else valuation_policy),
        LinearMarginLeverageEvidence(
            cash.ACCOUNT,
            cash.BTC,
            Rate(10, Scale(0), "notional_per_initial_margin"),
            UtcInstant(0),
            None,
            _sim(1, TimelinePhase(10, "leverage")),
            f"{PROFILE_KEY}.leverage",
            "sha256:" + "b2" * 32,
        ),
        _margin_rule_book(),
        LinearMarginMarkEvidence(resolved_margin, resolved_margin_policy),
        SETTLEMENT_REGISTRATION,
        QuantizationPolicy(
            f"{PROFILE_KEY}.margin-ceiling",
            cash.MONEY_SCALE,
            RoundingPolicy.CEILING,
        ),
        QuantizationPolicy(
            f"{PROFILE_KEY}.unrealized-half-even",
            cash.MONEY_SCALE,
            RoundingPolicy.HALF_EVEN,
        ),
        f"{PROFILE_KEY}.ledger",
        f"{PROFILE_KEY}.reservations",
    )


def _window_states(case) -> dict[str, FinancialStateView]:
    class CapturingDispatcher:
        def __init__(self) -> None:
            self.delegate = SyntheticLinearFinancialDispatcher()
            self.states: dict[str, FinancialStateView] = {}

        @property
        def spec(self):
            return self.delegate.spec

        def book_fill(self, *args):
            return self.delegate.book_fill(*args)

        def book_fee(self, *args):
            return self.delegate.book_fee(*args)

        def dispatch_scheduled_event(self, event, state):
            self.states[event.event_id] = state
            return self.delegate.dispatch_scheduled_event(event, state)

        def project_final_snapshot(self, *args):
            return self.delegate.project_final_snapshot(*args)

    dispatcher = CapturingDispatcher()
    DeterministicBarEngine(dispatcher).run(case)
    assert set(dispatcher.states) == {
        "linear-funding-300",
        "linear-long-audit-350",
        "linear-short-audit-650",
    }
    return dispatcher.states


def _production_window_states(case) -> dict[str, FinancialStateView]:
    delegate = BinanceUsdmTradifiLinearFinancialDispatcher(
        case.financial_dispatch_plan.dispatcher_spec
    )

    class CapturingDispatcher:
        def __init__(self) -> None:
            self.states: dict[str, FinancialStateView] = {}

        @property
        def spec(self):
            return delegate.spec

        def book_fill(self, *args):
            return delegate.book_fill(*args)

        def book_fee(self, *args):
            return delegate.book_fee(*args)

        def dispatch_scheduled_event(self, event, state):
            if event.operation_key != "margin_liquidation_audit":
                return delegate.dispatch_scheduled_event(event, state)
            self.states[event.event_id] = state
            input_hash = canonical_sha256(
                {"event": event.event_id, "journal": state.journal.journal_hash}
            )
            return FinancialDispatchOutcome(
                self.spec,
                input_hash,
                result=FinancialDispatchResult(
                    self.spec,
                    event.event_id,
                    (),
                    state.position_lot_books,
                    (),
                ),
            )

        def project_final_snapshot(self, *args):
            return delegate.project_final_snapshot(*args)

    dispatcher = CapturingDispatcher()
    DeterministicBarEngine(dispatcher).run(case)
    assert set(dispatcher.states) == {
        "linear-long-audit-350",
        "linear-short-audit-650",
    }
    return dispatcher.states


def _production_case(*, final_sell_quantity_units: int = 3_000):
    case = build_execution_case(final_sell_quantity_units=final_sell_quantity_units)
    baseline_states = _window_states(case)
    composed = BinanceUsdmTradifiProfileComposer().compose(composition_request())
    assert composed.result is not None
    spec = composed.result.financial_dispatcher_spec
    scheduled = []
    production_funding_entry = None
    for event in case.financial_dispatch_plan.scheduled_account_events:
        payload = event.payload
        if event.operation_key == "funding":
            target = event.event_at.instant
            slot = payload.settlement_identity.application_key.funding_slot_id
            eligibility_at = _sim(
                target.epoch_nanoseconds,
                TimelinePhase(100, "funding_eligibility"),
            )
            publication = LinearFundingRatePublicationCandidate(
                slot,
                LinearFundingPublicationStatus.FINAL_RATE,
                event.semantic_payload.applied_rate,
                f"{event.event_id}.publication",
                "sha256:" + "c3" * 32,
                UtcInstant(target.epoch_nanoseconds - 1),
                _sim(
                    target.epoch_nanoseconds,
                    TimelinePhase(50, "funding_publication"),
                ),
                "revision-1",
                None,
                f"{PROFILE_KEY}.funding-publication",
                "sha256:" + "d4" * 32,
            )
            funding_mark, funding_policy = _resolved_mark(
                PricePurpose.FUNDING,
                event.semantic_payload.funding_price,
                event.event_at,
                "funding",
            )
            settlement = LinearFundingSettlementEvidence(
                payload.settlement_identity.application_key,
                target,
                event.event_at,
                publication.published_rate,
                f"{event.event_id}.settlement",
                "sha256:" + "e5" * 32,
                "revision-1",
                None,
                f"{PROFILE_KEY}.funding-settlement",
                "sha256:" + "f6" * 32,
            )
            production_payload = LinearFundingAccountEventPlan(
                payload.settlement_identity,
                payload.recorded_at,
                cash.ledger_schema(),
                cash.CASH_KEY,
                cash.POSITION_KEY,
                CONTRACT,
                eligibility_at,
                _sim(
                    target.epoch_nanoseconds,
                    TimelinePhase(105, "position_snapshot"),
                ),
                f"{event.event_id}.position-snapshot",
                f"{PROFILE_KEY}.position-series",
                "revision-1",
                None,
                (publication,),
                settlement,
                LinearFundingMarkEvidence(funding_mark, funding_policy),
                SETTLEMENT_REGISTRATION,
                QuantizationPolicy(
                    f"{PROFILE_KEY}.funding-half-even",
                    cash.MONEY_SCALE,
                    RoundingPolicy.HALF_EVEN,
                ),
            )
            production_event = replace(
                event,
                component_keys=(spec.financing_component.component_key,),
                payload=production_payload,
                semantic_payload=production_payload.production_semantic_authority(),
            )
            scheduled.append(production_event)
            funding_outcome = BinanceUsdmTradifiLinearFinancialDispatcher(
                spec
            ).dispatch_scheduled_event(
                production_event,
                baseline_states[event.event_id],
            )
            assert funding_outcome.result is not None
            production_funding_entry = funding_outcome.result.journal_entries[0]
            continue

        projection_plan = _projection_plan(
            evaluated_at=payload.evaluated_at,
            valuation_price=payload.valuation_price,
            margin_price=payload.margin_price,
            suffix=payload.role_suffix,
        )
        bar = LinearLiquidationMarkBarEvidence(
            f"liquidation-bar.{payload.role_suffix}",
            cash.BTC,
            PricePurpose.LIQUIDATION,
            payload.interval_start,
            payload.interval_end_exclusive,
            payload.liquidation_low,
            payload.liquidation_high,
            _sim(
                payload.interval_end_exclusive.epoch_nanoseconds,
                TimelinePhase(40, "bar_closed"),
            ),
            event.event_at,
            f"{PROFILE_KEY}.liquidation.stream",
            f"{event.event_id}.bar",
            "revision-1",
            None,
            f"{PROFILE_KEY}.liquidation-source",
            "sha256:" + "ab" * 32,
        )
        assert production_funding_entry is not None
        baseline_state = baseline_states[event.event_id]
        attested_journal = type(baseline_state.journal)(
            tuple(
                production_funding_entry
                if entry.journal_entry_id == production_funding_entry.journal_entry_id
                else entry
                for entry in baseline_state.journal.entries
            )
        )
        journal_hash = attested_journal.journal_hash
        reservation_hash = baseline_state.reservation_state.state_hash
        production_payload = replace(
            payload,
            projection_plan=projection_plan,
            liquidation_bars=(
                ()
                if final_sell_quantity_units == 2_000 and payload.role_suffix == "short"
                else (bar,)
            ),
            requested_grade=RequestedResultGrade.DEVELOPMENT,
            account_window_evidence_key=(
                f"{PROFILE_KEY}.account-window.{payload.role_suffix}"
            ),
            interval_start_journal_hash=journal_hash,
            interval_end_journal_hash=journal_hash,
            interval_start_reservation_hash=reservation_hash,
            interval_end_reservation_hash=reservation_hash,
        )
        scheduled.append(
            replace(
                event,
                component_keys=(
                    spec.liquidation_audit_component.component_key,
                    spec.margin_component.component_key,
                ),
                payload=production_payload,
                semantic_payload=production_payload.production_semantic_authority(),
            )
        )

    snapshot = case.snapshot_plan
    valuation_mark = snapshot.resolved_marks[0]
    valuation_policy = StaleMarkPolicy(
        valuation_mark.stale_policy_key,
        valuation_mark.stale_policy_version,
        valuation_mark.price_purpose,
        100,
        True,
    )
    final_projection = _projection_plan(
        evaluated_at=_sim(
            snapshot.timestamp.epoch_nanoseconds,
            TimelinePhase(90, "final_projection"),
        ),
        valuation_price=valuation_mark.price,
        margin_price=valuation_mark.price,
        suffix="final",
        valuation_mark=valuation_mark,
        valuation_policy=valuation_policy,
    )
    snapshot = replace(
        snapshot,
        resolved_marks=(valuation_mark,) if final_sell_quantity_units != 2_000 else (),
        linear_margin_projection_plan=final_projection,
        margin_projection_artifact_role="margin_projection.final",
        final_snapshot_artifact_role="final_snapshot",
    )
    dispatch_plan = replace(
        case.financial_dispatch_plan,
        dispatcher_spec=spec,
        scheduled_account_events=tuple(scheduled),
        final_snapshot_payload=snapshot,
    )
    bars = tuple(
        replace(
            bar,
            accounting_plan=replace(
                bar.accounting_plan,
                position_accounting_component=spec.position_accounting_component,
            ),
        )
        for bar in case.bar_executions
    )
    preliminary = replace(
        case,
        bar_executions=bars,
        financial_dispatch_plan=dispatch_plan,
        snapshot_plan=snapshot,
    )
    window_states = _production_window_states(preliminary)
    attested_events = []
    for event in preliminary.financial_dispatch_plan.scheduled_account_events:
        if event.operation_key != "margin_liquidation_audit":
            attested_events.append(event)
            continue
        state = window_states[event.event_id]
        payload = replace(
            event.payload,
            interval_start_journal_hash=state.journal.journal_hash,
            interval_end_journal_hash=state.journal.journal_hash,
            interval_start_reservation_hash=state.reservation_state.state_hash,
            interval_end_reservation_hash=state.reservation_state.state_hash,
        )
        attested_events.append(
            replace(
                event,
                payload=payload,
                semantic_payload=payload.production_semantic_authority(),
            )
        )
    return replace(
        preliminary,
        financial_dispatch_plan=replace(
            preliminary.financial_dispatch_plan,
            scheduled_account_events=tuple(attested_events),
        ),
    )


def _replace_event_payload(case, event_id: str, payload):
    events = tuple(
        replace(
            event,
            payload=payload,
            semantic_payload=payload.production_semantic_authority(),
        )
        if event.event_id == event_id
        else event
        for event in case.financial_dispatch_plan.scheduled_account_events
    )
    return replace(
        case,
        financial_dispatch_plan=replace(
            case.financial_dispatch_plan,
            scheduled_account_events=events,
        ),
    )


def _production_financial_hash(case) -> str:
    prepared, _, hydrated, _, _ = _contract()
    plan = replace(
        hydrated.execution_case_plan,
        financial_state=case.financial_state,
        financial_dispatch_plan=case.financial_dispatch_plan,
        snapshot_plan=case.snapshot_plan,
    )
    return _execution_case_semantic_spec_v3(
        base_spec=hydrated.execution_case_semantic_spec,
        execution_case_plan=plan,
        market_data_preparation=prepared.preparation,
    ).financial_inputs_hash


def test_production_dispatch_runs_full_linear_derivative_journey() -> None:
    case = _production_case()
    outcome = DeterministicBarEngine().run(case)

    assert outcome.engine_failure is None
    assert outcome.result is not None
    result = outcome.result
    roles = tuple(artifact.role for artifact in result.financial_artifacts)
    assert roles == (
        "position_accounting.1",
        "funding_eligibility",
        "funding_accounting",
        "liquidation_audit.long",
        "margin_projection.long",
        "position_accounting.2",
        "position_accounting.3",
        "liquidation_audit.short",
        "margin_projection.short",
        "final_snapshot",
        "margin_projection.final",
    )
    assert set(roles) == set(case.financial_dispatch_plan.expected_artifact_roles)
    assert result.final_portfolio_snapshot is not None
    assert result.final_portfolio_snapshot.unrealized_pnl.units == -10
    assert result.final_portfolio_snapshot.realized_pnl.units == -60
    assert result.final_portfolio_snapshot.fees.units == 91
    assert result.final_portfolio_snapshot.financing.units == -3
    snapshot = result.final_portfolio_snapshot
    assert {
        "cash": canonical_sha256(snapshot.cash),
        "positions": canonical_sha256(snapshot.positions),
        "realized": canonical_sha256(snapshot.realized_pnl),
        "unrealized": canonical_sha256(snapshot.unrealized_pnl),
        "fees": canonical_sha256(snapshot.fees),
        "funding": canonical_sha256(snapshot.financing),
        "equity": canonical_sha256(snapshot.equity),
        "marks": snapshot.valuation_mark_set_hash,
        "staleness": snapshot.valuation_staleness_report_hash,
    } == {
        "cash": (
            "sha256:12d2b9afaccb32a942f755c32b1f366510cde300e513e454dad0609553de0a89"
        ),
        "positions": (
            "sha256:d197178029795b9dcc69b37bdc2dc5ead968e8b824b3b190c141d2693e214818"
        ),
        "realized": (
            "sha256:5b67faab0beb8eade84d572e631d741f6d238a7006f553e560ed7c769d9abb3f"
        ),
        "unrealized": (
            "sha256:3fd7f94111cc8358b3e9ecc4cd07935ff43bd0c93b4336a12aeed73f70462315"
        ),
        "fees": (
            "sha256:5e878d085f661d6af3e90fe0acde6c7a22e580967d8434036ca3a742b6efe51e"
        ),
        "funding": (
            "sha256:df3ef29b862c282299d9979c3271eeda7559aa751a1bbf06668c7dc31184f26f"
        ),
        "equity": (
            "sha256:026e77fe1413ae12a6b3bf01adb3ffb66e2224d889f929c4d81cc140a418d9b7"
        ),
        "marks": (
            "sha256:86132479e1cbb420e9def44ea0f2bfa8fe2e6690386aa776ded84498b7594f88"
        ),
        "staleness": (
            "sha256:65c84673c0077bdbb274f2ed723f3982034650ab2864e95b6863087ddb61a7fc"
        ),
    }
    long_projection = next(
        artifact.payload
        for artifact in result.financial_artifacts
        if artifact.role == "margin_projection.long"
    )
    assert long_projection.request.reservation_evidence is not None
    assert (
        long_projection.request.reservation_evidence.reservation_state.active_reservations
    )


def test_empty_position_funding_and_thin_plan_fails_closed() -> None:
    case = _production_case()
    event = next(
        value
        for value in case.financial_dispatch_plan.scheduled_account_events
        if value.operation_key == "funding"
    )
    journal = case.financial_state.journal
    state = FinancialStateView(
        journal,
        GenericLedger(case.financial_state.ledger_schema).project(journal),
        ResourceReservationState(
            cash.ACCOUNT,
            (),
            (),
            ReservationCommitment.empty(),
        ),
        (),
        (),
    )
    dispatcher = BinanceUsdmTradifiLinearFinancialDispatcher(
        case.financial_dispatch_plan.dispatcher_spec
    )

    outcome = dispatcher.dispatch_scheduled_event(event, state)
    assert outcome.result is not None
    assert outcome.result.journal_entries[0].financing == ()

    thin = replace(
        event,
        payload=LinearFundingAccountEventPlan(
            event.payload.settlement_identity,
            event.payload.recorded_at,
        ),
    )
    rejected = dispatcher.dispatch_scheduled_event(thin, state)
    assert rejected.failure is not None
    assert rejected.failure.code is FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH


def test_execution_input_v6_round_trips_derivative_authority_and_v5_rejects_it() -> (
    None
):
    prepared, resolved, hydrated, _, _ = _contract()
    production = _production_case()
    plan = replace(
        hydrated.execution_case_plan,
        financial_state=production.financial_state,
        financial_dispatch_plan=production.financial_dispatch_plan,
        snapshot_plan=production.snapshot_plan,
    )
    spec = _execution_case_semantic_spec_v3(
        base_spec=hydrated.execution_case_semantic_spec,
        execution_case_plan=plan,
        market_data_preparation=prepared.preparation,
    )
    resolved = _resolved_for_spec(prepared, resolved, spec)
    hydrated = replace(
        hydrated,
        execution_case_semantic_spec=spec,
        execution_case_plan=plan,
    )

    envelope = _materialize_execution_input_bundle_v6(
        resolved_request=resolved,
        hydrated_inputs=hydrated,
        market_data_preparation=prepared.preparation,
    )
    decoded = _read_execution_input_payload_v6(envelope.payload)

    assert canonical_bytes(decoded.execution_case_plan.financial_dispatch_plan) == (
        canonical_bytes(production.financial_dispatch_plan)
    )
    assert canonical_bytes(
        decoded.execution_case_plan.snapshot_plan
    ) == canonical_bytes(production.snapshot_plan)
    try:
        _materialize_execution_input_bundle_v5(
            resolved_request=resolved,
            hydrated_inputs=hydrated,
            market_data_preparation=prepared.preparation,
        )
    except ValueError as error:
        assert "cannot persist derivative dispatch authority" in str(error)
    else:
        raise AssertionError("execution input v5 accepted derivative authority")


def test_legacy_plan_bytes_remain_unchanged_when_production_authority_is_omitted() -> (
    None
):
    case = build_execution_case()
    funding = next(
        event.payload
        for event in case.financial_dispatch_plan.scheduled_account_events
        if event.operation_key == "funding"
    )

    assert canonical_bytes(funding) == canonical_bytes(
        {
            "type": "synthetic_funding_dispatch_payload",
            "settlement_identity": funding.settlement_identity,
            "recorded_at": funding.recorded_at,
        }
    )
    assert "linear_margin_projection_plan" not in case.snapshot_plan.to_canonical_dict()


def test_production_authority_mutations_change_financial_hash() -> None:
    case = _production_case()
    baseline = _production_financial_hash(case)
    funding_event = next(
        event
        for event in case.financial_dispatch_plan.scheduled_account_events
        if event.operation_key == "funding"
    )
    funding = funding_event.payload
    margin_event = next(
        event
        for event in case.financial_dispatch_plan.scheduled_account_events
        if event.operation_key == "margin_liquidation_audit"
    )
    margin = margin_event.payload
    projection = margin.projection_plan
    interval = projection.margin_rule_book.intervals[0]
    changed_rule_book = LinearMarginRuleBook.create(
        rule_book_key=projection.margin_rule_book.rule_book_key,
        rule_book_version=projection.margin_rule_book.rule_book_version,
        instrument_id=projection.margin_rule_book.instrument_id,
        settlement_currency_id=projection.margin_rule_book.settlement_currency_id,
        tier_scale=projection.margin_rule_book.tier_scale,
        intervals=(replace(interval, source_hash="sha256:" + "12" * 32),),
    )
    mutations = (
        replace(
            funding,
            publication_candidates=(
                replace(
                    funding.publication_candidates[0],
                    source_hash="sha256:" + "13" * 32,
                ),
            ),
        ),
        replace(
            funding,
            settlement_evidence=replace(
                funding.settlement_evidence,
                source_hash="sha256:" + "14" * 32,
            ),
        ),
        replace(
            funding,
            funding_mark_evidence=replace(
                funding.funding_mark_evidence,
                resolved_mark=replace(
                    funding.funding_mark_evidence.resolved_mark,
                    revision_id="revision-2",
                ),
            ),
        ),
        replace(funding, position_revision_id="revision-2"),
        replace(
            funding,
            payment_quantization=replace(
                funding.payment_quantization,
                version=funding.payment_quantization.version + ".v2",
            ),
        ),
        replace(
            margin,
            projection_plan=replace(
                projection,
                leverage_evidence=replace(
                    projection.leverage_evidence,
                    source_hash="sha256:" + "15" * 32,
                ),
            ),
        ),
        replace(
            margin,
            projection_plan=replace(projection, margin_rule_book=changed_rule_book),
        ),
        replace(
            margin,
            projection_plan=replace(
                projection,
                margin_mark_evidence=replace(
                    projection.margin_mark_evidence,
                    resolved_mark=replace(
                        projection.margin_mark_evidence.resolved_mark,
                        revision_id="revision-2",
                    ),
                ),
            ),
        ),
        replace(
            margin,
            liquidation_bars=(
                replace(
                    margin.liquidation_bars[0],
                    source_hash="sha256:" + "16" * 32,
                ),
            ),
        ),
        replace(
            margin,
            interval_start_journal_hash="sha256:" + "17" * 32,
            interval_end_journal_hash="sha256:" + "17" * 32,
        ),
        replace(
            margin,
            interval_start_reservation_hash="sha256:" + "18" * 32,
            interval_end_reservation_hash="sha256:" + "18" * 32,
        ),
    )
    hashes = []
    for payload in mutations:
        event_id = (
            funding_event.event_id
            if type(payload) is LinearFundingAccountEventPlan
            else margin_event.event_id
        )
        hashes.append(
            _production_financial_hash(_replace_event_payload(case, event_id, payload))
        )
    assert all(value != baseline for value in hashes)

    identity_only = replace(
        funding,
        settlement_identity=type(funding.settlement_identity).derive(
            funding.settlement_identity.application_key,
            funding.settlement_identity.identity_namespace,
            "semantic-run-id-mutation",
        ),
    )
    assert (
        _production_financial_hash(
            _replace_event_payload(case, funding_event.event_id, identity_only)
        )
        == baseline
    )


def test_liquidation_window_journal_reservation_and_audit_time_mutations_fail() -> None:
    case = _production_case()
    event = next(
        event
        for event in case.financial_dispatch_plan.scheduled_account_events
        if event.event_id == "linear-long-audit-350"
    )
    state = _production_window_states(case)[event.event_id]
    dispatcher = BinanceUsdmTradifiLinearFinancialDispatcher(
        case.financial_dispatch_plan.dispatcher_spec
    )
    assert dispatcher.dispatch_scheduled_event(event, state).result is not None

    payloads = (
        replace(event.payload, interval_end_journal_hash="sha256:" + "21" * 32),
        replace(event.payload, interval_end_reservation_hash="sha256:" + "22" * 32),
        replace(
            event.payload,
            audit_at=_sim(
                event.event_at.instant.epoch_nanoseconds,
                TimelinePhase(999, "mutated_audit"),
            ),
        ),
    )
    for payload in payloads:
        mutated = replace(
            event,
            payload=payload,
            semantic_payload=payload.production_semantic_authority(),
        )
        outcome = dispatcher.dispatch_scheduled_event(mutated, state)
        assert outcome.failure is not None
        assert (
            outcome.failure.code
            is FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE
        )


def test_generic_composition_binds_all_financial_dispatcher_components() -> None:
    _, resolved, hydrated, _, _ = _contract()
    plan = hydrated.execution_case_plan
    _validate_financial_component_bindings(resolved, plan)
    spec = plan.financial_dispatch_plan.dispatcher_spec
    mutations = (
        replace(
            spec,
            position_accounting_component=replace(
                spec.position_accounting_component,
                component_digest="sha256:" + "31" * 32,
            ),
        ),
        replace(
            spec,
            financing_component=replace(
                spec.financing_component,
                component_digest="sha256:" + "32" * 32,
            ),
        ),
        replace(
            spec,
            margin_component=replace(
                spec.margin_component,
                component_digest="sha256:" + "33" * 32,
            ),
        ),
        replace(
            spec,
            liquidation_audit_component=replace(
                spec.liquidation_audit_component,
                component_digest="sha256:" + "34" * 32,
            ),
        ),
    )
    for mutated in mutations:
        changed_plan = replace(
            plan,
            financial_dispatch_plan=replace(
                plan.financial_dispatch_plan,
                dispatcher_spec=mutated,
            ),
        )
        with pytest.raises(ValueError, match="financial dispatcher"):
            _validate_financial_component_bindings(resolved, changed_plan)


def test_close_to_flat_full_engine_journey_uses_no_position_marks() -> None:
    outcome = DeterministicBarEngine().run(
        _production_case(final_sell_quantity_units=2_000)
    )

    assert outcome.engine_failure is None
    assert outcome.result is not None
    assert outcome.result.final_ledger_state.position_balances == ()
    assert outcome.result.final_portfolio_snapshot.positions == ()
    assert outcome.result.final_portfolio_snapshot.valuation_marks == ()
    final_projection = next(
        artifact.payload
        for artifact in outcome.result.financial_artifacts
        if artifact.role == "margin_projection.final"
    )
    assert final_projection.request.position_valuations == ()
    assert final_projection.request.margin_results == ()


def test_derivative_snapshot_reporting_scale_mismatch_fails_closed() -> None:
    case = _production_case()
    snapshot = replace(case.snapshot_plan, reporting_scale=Scale(3))
    changed = replace(
        case,
        snapshot_plan=snapshot,
        financial_dispatch_plan=replace(
            case.financial_dispatch_plan,
            final_snapshot_payload=snapshot,
        ),
    )

    outcome = DeterministicBarEngine().run(changed)
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.code.value == "financial_dispatch_failure"
