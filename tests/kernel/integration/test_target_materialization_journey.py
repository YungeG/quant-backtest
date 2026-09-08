from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any, TypedDict, cast

import pytest

from crypto_quant_domain import (
    ActivePortfolioTarget,
    CurrencyId,
    DecisionBatch,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    Money,
    PricePurpose,
    Quantity,
    Scale,
    SimulationInstant,
    SourceSequence,
    StrategyDecisionCandidate,
    StrategyDecisionPayload,
    StrategySleeveId,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    AllocationConstraintCode,
    AtomicDecisionBatchCollector,
    DecisionBatchExpectation,
    DecisionBatchSubmission,
    ApprovedPortfolioTarget,
    InstrumentSizingInput,
    LatestSleeveDecisionState,
    NormalizedPortfolioTarget,
    PortfolioAllocation,
    PortfolioAllocator,
    PortfolioRiskEvaluator,
    PositionSizer,
    PositionSizingFailureCode,
    StrategyAllocation,
    StrategyOutputValidationContext,
    StrategyOutputValidator,
)
from tests.kernel.allocation._fixtures import (
    BTC,
    CARRY,
    ETH,
    MONEY_SCALE,
    NOTIONAL_SCALE,
    POLICY,
    TREND,
    USD,
    snapshot,
)
from tests.kernel.risk._fixtures import policy as risk_policy
from tests.kernel.sizing._fixtures import lattice, resolved_mark, sizing_policy


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/target-materialization-journey-v1.json"
SAME_UTC_FIXTURE = ROOT / "tests/fixtures/kernel/target-materialization-same-utc-v2.json"


class Journey(TypedDict):
    batch: DecisionBatch
    state: LatestSleeveDecisionState
    allocation: PortfolioAllocation
    approved: ApprovedPortfolioTarget
    normalized: NormalizedPortfolioTarget
    active: ActivePortfolioTarget


def catalog() -> InstrumentCatalog:
    btc = CurrencyId("BTC")
    eth = CurrencyId("ETH")
    return InstrumentCatalog(
        currencies=(btc, eth, USD),
        instruments=(
            InstrumentDefinition(BTC, InstrumentType.SPOT, btc, USD, USD),
            InstrumentDefinition(ETH, InstrumentType.SPOT, eth, USD, USD),
        ),
        symbol_timelines=(),
    )


def payload(
    strategy_id: str,
    sleeve_id: StrategySleeveId,
    targets: tuple[tuple[InstrumentId, str], ...],
    *,
    reverse_mapping: bool = False,
) -> StrategyDecisionCandidate:
    fields: dict[str, Any] = {
        "schema_version": 1,
        "strategy_id": strategy_id,
        "sleeve_id": sleeve_id.value,
        "decision_time": 100,
        "observed_through": 99,
        "effective_time": 100,
        "expires_at": 200,
        "targets": [
            {
                "instrument_id": {
                    "venue": instrument_id.venue.value,
                    "stable_key": instrument_id.stable_key,
                },
                "value": value,
            }
            for instrument_id, value in targets
        ],
        "confidence": None,
        "reason": "scheduled aggregate rebalance",
        "evidence": {"model_revision": f"{strategy_id}:v1"},
    }
    if reverse_mapping:
        fields = dict(reversed(tuple(fields.items())))
    return StrategyDecisionCandidate(StrategyDecisionPayload(fields))


def validate(
    expectation: DecisionBatchExpectation,
    targets: tuple[tuple[InstrumentId, str], ...],
    *,
    reverse_mapping: bool = False,
    decision_instant: SimulationInstant | None = None,
) -> DecisionBatchSubmission:
    result = StrategyOutputValidator().validate(
        payload(
            expectation.strategy_id,
            expectation.sleeve_id,
            targets,
            reverse_mapping=reverse_mapping,
        ),
        StrategyOutputValidationContext(
            expected_strategy_id=expectation.strategy_id,
            expected_sleeve_id=expectation.sleeve_id,
            decision_time=UtcInstant(100),
            instrument_catalog=catalog(),
            universe=(BTC, ETH),
            decision_instant=decision_instant,
        ),
    )
    return DecisionBatchSubmission(expectation=expectation, result=result)


def run_journey(*, reverse: bool = False) -> Journey:
    trend = DecisionBatchExpectation("trend-v1", TREND)
    carry = DecisionBatchExpectation("carry-v1", CARRY)
    trend_targets: tuple[tuple[InstrumentId, str], ...] = (
        (BTC, "0.5"),
        (ETH, "0.2"),
    )
    carry_targets: tuple[tuple[InstrumentId, str], ...] = (
        (BTC, "-0.25"),
        (ETH, "0.1"),
    )
    if reverse:
        trend_targets = tuple(reversed(trend_targets))
        carry_targets = tuple(reversed(carry_targets))
    submissions: tuple[DecisionBatchSubmission, ...] = (
        validate(trend, trend_targets, reverse_mapping=reverse),
        validate(carry, carry_targets, reverse_mapping=reverse),
    )
    expected: tuple[DecisionBatchExpectation, ...] = (trend, carry)
    if reverse:
        submissions = tuple(reversed(submissions))
        expected = tuple(reversed(expected))

    collected = AtomicDecisionBatchCollector().collect(
        decision_time=UtcInstant(100),
        expected=expected,
        submissions=submissions,
    )
    if collected.batch is None or collected.state is None:
        raise AssertionError(f"batch collection failed: {collected.failure!r}")

    portfolio_snapshot = snapshot()
    snapshot_hash = canonical_sha256(portfolio_snapshot)
    allocations: tuple[StrategyAllocation, ...] = (
        StrategyAllocation(
            strategy_id="trend-v1",
            sleeve_id=TREND,
            valuation_time=UtcInstant(100),
            valuation_currency=USD,
            allocation_nav=Money(60_000, MONEY_SCALE, "USD"),
            policy_ref=POLICY,
            source_portfolio_snapshot_hash=snapshot_hash,
        ),
        StrategyAllocation(
            strategy_id="carry-v1",
            sleeve_id=CARRY,
            valuation_time=UtcInstant(100),
            valuation_currency=USD,
            allocation_nav=Money(40_000, MONEY_SCALE, "USD"),
            policy_ref=POLICY,
            source_portfolio_snapshot_hash=snapshot_hash,
        ),
    )
    if reverse:
        allocations = tuple(reversed(allocations))
    allocated = PortfolioAllocator().allocate(
        sleeve_state=collected.state,
        portfolio_snapshot=portfolio_snapshot,
        allocations=allocations,
        target_notional_scale=NOTIONAL_SCALE,
    )
    if allocated.allocation is None:
        raise AssertionError(f"allocation failed: {allocated.failure!r}")

    assessed = PortfolioRiskEvaluator().evaluate(
        allocation=allocated.allocation,
        policy=risk_policy(reverse=reverse),
    )
    if assessed.approved_target is None:
        raise AssertionError(f"risk failed: {assessed.failure!r}")

    sizing_values: tuple[InstrumentSizingInput, ...] = (
        InstrumentSizingInput(
            instrument_id=BTC,
            mark=resolved_mark(BTC, price_units=2_000),
            current_quantity=Quantity(0, Scale(3), str(BTC)),
            lattice=lattice(BTC),
        ),
        InstrumentSizingInput(
            instrument_id=ETH,
            mark=resolved_mark(ETH, price_units=1_000),
            current_quantity=Quantity(0, Scale(3), str(ETH)),
            lattice=lattice(ETH),
        ),
    )
    if reverse:
        sizing_values = tuple(reversed(sizing_values))
    sized = PositionSizer().materialize(
        approved_target=assessed.approved_target,
        source_decision_batch_id=collected.batch.decision_batch_id,
        policy=sizing_policy(),
        inputs=sizing_values,
    )
    if sized.normalized_target is None:
        raise AssertionError(f"sizing failed: {sized.failure!r}")

    return {
        "batch": collected.batch,
        "state": collected.state,
        "allocation": allocated.allocation,
        "approved": assessed.approved_target,
        "normalized": sized.normalized_target,
        "active": sized.normalized_target.active_target,
    }


def load_fixture() -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid G04 fixture: {FIXTURE}") from error


def canonical_value(value: object) -> object:
    return json.loads(canonical_bytes(value))


def test_two_sleeves_materialize_one_stable_account_target() -> None:
    fixture = load_fixture()
    journey = run_journey()
    active = journey["active"]
    quantities = dict(active.quantities)

    assert quantities == {
        BTC: Quantity(10_000, Scale(3), str(BTC)),
        ETH: Quantity(16_000, Scale(3), str(ETH)),
    }
    assert canonical_value(active) == fixture["expected_active_target"]
    assert {
        key: canonical_sha256(journey[key])
        for key in ("batch", "state", "allocation", "approved", "normalized", "active")
    } == fixture["expected_stage_hashes"]


def test_registration_mapping_and_pipeline_input_order_are_irrelevant() -> None:
    first = run_journey()
    reordered = run_journey(reverse=True)

    for key in ("batch", "state", "allocation", "approved", "normalized", "active"):
        assert canonical_sha256(first[key]) == canonical_sha256(reordered[key])


def test_same_utc_second_state_flows_through_allocation_risk_and_sizing() -> None:
    try:
        fixture = cast(
            dict[str, Any],
            json.loads(SAME_UTC_FIXTURE.read_text(encoding="utf-8")),
        )
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid same-UTC fixture: {SAME_UTC_FIXTURE}") from error

    first_instant = SimulationInstant(
        UtcInstant(100), TimelinePhase(60, "decision"), SourceSequence(1)
    )
    later_instant = SimulationInstant(
        UtcInstant(100), TimelinePhase(60, "decision"), SourceSequence(2)
    )
    trend = DecisionBatchExpectation("trend-v1", TREND)
    carry = DecisionBatchExpectation("carry-v1", CARRY)
    collector = AtomicDecisionBatchCollector()
    first = collector.collect(
        decision_time=UtcInstant(100),
        decision_instant=first_instant,
        expected=(trend, carry),
        submissions=(
            validate(trend, ((BTC, "0.5"),), decision_instant=first_instant),
            validate(carry, ((ETH, "0.1"),), decision_instant=first_instant),
        ),
    )
    assert first.state is not None
    later = collector.collect(
        decision_time=UtcInstant(100),
        decision_instant=later_instant,
        expected=(trend,),
        submissions=(
            validate(trend, ((BTC, "0.75"),), decision_instant=later_instant),
        ),
        prior_state=first.state,
    )
    assert later.batch is not None and later.state is not None

    flattened_snapshot = snapshot()
    flattened_hash = canonical_sha256(flattened_snapshot)
    flattened = PortfolioAllocator().allocate(
        sleeve_state=later.state,
        portfolio_snapshot=flattened_snapshot,
        allocations=(
            StrategyAllocation(
                "trend-v1",
                TREND,
                UtcInstant(100),
                USD,
                Money(60_000, MONEY_SCALE, "USD"),
                POLICY,
                flattened_hash,
            ),
            StrategyAllocation(
                "carry-v1",
                CARRY,
                UtcInstant(100),
                USD,
                Money(40_000, MONEY_SCALE, "USD"),
                POLICY,
                flattened_hash,
            ),
        ),
        target_notional_scale=NOTIONAL_SCALE,
    )
    assert flattened.failure is not None
    assert {
        value.code for value in flattened.failure.decisions
    } == {AllocationConstraintCode.VALUATION_INSTANT_MISMATCH}

    portfolio_snapshot = replace(snapshot(), timestamp_instant=later_instant)
    snapshot_hash = canonical_sha256(portfolio_snapshot)
    allocated = PortfolioAllocator().allocate(
        sleeve_state=later.state,
        portfolio_snapshot=portfolio_snapshot,
        allocations=(
            StrategyAllocation(
                "trend-v1",
                TREND,
                UtcInstant(100),
                USD,
                Money(60_000, MONEY_SCALE, "USD"),
                POLICY,
                snapshot_hash,
                valuation_instant=later_instant,
            ),
            StrategyAllocation(
                "carry-v1",
                CARRY,
                UtcInstant(100),
                USD,
                Money(40_000, MONEY_SCALE, "USD"),
                POLICY,
                snapshot_hash,
                valuation_instant=later_instant,
            ),
        ),
        target_notional_scale=NOTIONAL_SCALE,
    )
    assert allocated.allocation is not None
    future_instant = SimulationInstant(
        UtcInstant(100), TimelinePhase(60, "decision"), SourceSequence(3)
    )
    future_snapshot = replace(portfolio_snapshot, timestamp_instant=future_instant)
    future_snapshot_hash = canonical_sha256(future_snapshot)
    future_allocation = PortfolioAllocator().allocate(
        sleeve_state=later.state,
        portfolio_snapshot=future_snapshot,
        allocations=tuple(
            replace(
                value,
                source_portfolio_snapshot_hash=future_snapshot_hash,
                valuation_instant=future_instant,
            )
            for value in allocated.allocation.allocations
        ),
        target_notional_scale=NOTIONAL_SCALE,
    )
    assert future_allocation.failure is not None
    assert {
        value.code for value in future_allocation.failure.decisions
    } == {AllocationConstraintCode.VALUATION_INSTANT_MISMATCH}

    assessed = PortfolioRiskEvaluator().evaluate(
        allocation=allocated.allocation,
        policy=risk_policy(),
    )
    assert assessed.approved_target is not None
    flattened_sizing = PositionSizer().materialize(
        approved_target=assessed.approved_target,
        source_decision_batch_id=later.batch.decision_batch_id,
        policy=sizing_policy(),
        inputs=(
            InstrumentSizingInput(
                BTC,
                resolved_mark(BTC, price_units=2_000),
                Quantity(0, Scale(3), str(BTC)),
                lattice(BTC),
            ),
            InstrumentSizingInput(
                ETH,
                resolved_mark(ETH, price_units=1_000),
                Quantity(0, Scale(3), str(ETH)),
                lattice(ETH),
            ),
        ),
    )
    assert flattened_sizing.failure is not None
    assert flattened_sizing.failure.code is PositionSizingFailureCode.MARK_TIME_MISMATCH

    exact_marks = (
        replace(
            resolved_mark(BTC, price_units=2_000),
            available_at_instant=later_instant,
            resolved_at_instant=later_instant,
        ),
        replace(
            resolved_mark(ETH, price_units=1_000),
            available_at_instant=later_instant,
            resolved_at_instant=later_instant,
        ),
    )
    future_sizing = PositionSizer().materialize(
        approved_target=assessed.approved_target,
        source_decision_batch_id=later.batch.decision_batch_id,
        policy=sizing_policy(),
        inputs=(
            InstrumentSizingInput(
                BTC,
                replace(
                    exact_marks[0],
                    available_at_instant=future_instant,
                    resolved_at_instant=future_instant,
                ),
                Quantity(0, Scale(3), str(BTC)),
                lattice(BTC),
            ),
            InstrumentSizingInput(
                ETH,
                exact_marks[1],
                Quantity(0, Scale(3), str(ETH)),
                lattice(ETH),
            ),
        ),
    )
    assert future_sizing.failure is not None
    assert future_sizing.failure.code is PositionSizingFailureCode.MARK_TIME_MISMATCH

    sized = PositionSizer().materialize(
        approved_target=assessed.approved_target,
        source_decision_batch_id=later.batch.decision_batch_id,
        policy=sizing_policy(),
        inputs=(
            InstrumentSizingInput(
                BTC,
                exact_marks[0],
                Quantity(0, Scale(3), str(BTC)),
                lattice(BTC),
            ),
            InstrumentSizingInput(
                ETH,
                exact_marks[1],
                Quantity(0, Scale(3), str(ETH)),
                lattice(ETH),
            ),
        ),
    )
    assert sized.normalized_target is not None

    by_sleeve = {
        value.target_snapshot.sleeve_id: value for value in later.state.decisions
    }
    actual = {
        "schema_version": 2,
        "fixture_id": "target-materialization-same-utc-v2",
        "first_batch_hash": first.batch_hash,
        "first_state_hash": first.state_hash,
        "later_batch_hash": later.batch_hash,
        "later_state_hash": later.state_hash,
        "allocation_hash": allocated.allocation.allocation_hash,
        "approved_target_hash": assessed.approved_target.approved_target_hash,
        "normalized_target_hash": sized.normalized_target.normalized_target_hash,
        "active_target": canonical_value(sized.normalized_target.active_target),
    }
    assert actual == fixture
    assert by_sleeve[TREND].decision_instant == later_instant
    assert by_sleeve[CARRY].decision_instant == first_instant
    assert allocated.allocation.source_sleeve_state_hash == later.state_hash
    assert allocated.allocation.valuation_instant == later_instant
    assert assessed.approved_target.approved_instant == later_instant
    assert sized.normalized_target.materialized_instant == later_instant
    assert sized.normalized_target.active_target.materialized_instant == later_instant
    assert (
        assessed.approved_target.source_allocation_hash
        == allocated.allocation.allocation_hash
    )
    assert (
        sized.normalized_target.source_approved_target_hash
        == assessed.approved_target.approved_target_hash
    )
    assert (
        sized.normalized_target.source_decision_batch_id
        == later.batch.decision_batch_id
    )


def test_later_marks_cannot_mutate_the_materialized_active_target() -> None:
    journey = run_journey()
    active = journey["active"]
    before = canonical_sha256(active)

    later_marks = (
        resolved_mark(BTC, price_units=4_000, resolved_at=UtcInstant(101), revision="v2"),
        resolved_mark(ETH, price_units=500, resolved_at=UtcInstant(101), revision="v2"),
    )

    assert all(mark.resolved_at == UtcInstant(101) for mark in later_marks)
    assert canonical_sha256(active) == before
    with pytest.raises(FrozenInstanceError):
        setattr(active, "materialized_at", UtcInstant(101))


def test_validation_failure_cannot_produce_a_partial_batch_or_target() -> None:
    trend = DecisionBatchExpectation("trend-v1", TREND)
    carry = DecisionBatchExpectation("carry-v1", CARRY)
    invalid_carry = validate(carry, ((BTC, "not-a-number"),))
    collected = AtomicDecisionBatchCollector().collect(
        decision_time=UtcInstant(100),
        expected=(trend, carry),
        submissions=(validate(trend, ((BTC, "0.5"),)), invalid_carry),
    )

    assert collected.batch is None
    assert collected.state is None
    assert collected.failure is not None
