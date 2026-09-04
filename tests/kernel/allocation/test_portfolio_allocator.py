from __future__ import annotations

from dataclasses import replace

from crypto_quant_domain import (
    CurrencyId,
    Money,
    Scale,
    StrategySleeveId,
    TargetExposureFraction,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import (
    AllocationConstraintCode,
    CapitalAllocationPolicyRef,
    LatestSleeveDecisionState,
    PortfolioAllocator,
    StrategyAllocation,
)

from ._fixtures import (
    BTC,
    CARRY,
    ETH,
    MONEY_SCALE,
    NOTIONAL_SCALE,
    POLICY,
    TREND,
    USD,
    allocations,
    decision,
    snapshot,
    state,
)


def failure_codes(outcome: object) -> set[AllocationConstraintCode]:
    failure = getattr(outcome, "failure")
    assert failure is not None
    return {decision.code for decision in failure.decisions}


def test_opposite_sleeves_net_to_explicit_zero_with_attribution() -> None:
    portfolio_snapshot = snapshot()
    outcome = PortfolioAllocator().allocate(
        sleeve_state=state(),
        portfolio_snapshot=portfolio_snapshot,
        allocations=allocations(portfolio_snapshot),
        target_notional_scale=NOTIONAL_SCALE,
    )

    assert outcome.failure is None
    assert outcome.allocation is not None
    assert portfolio_snapshot.equity == Money(100_000, MONEY_SCALE, "USD")
    assert outcome.allocation.total_allocation_nav == Money(
        100_000, MONEY_SCALE, "USD"
    )
    assert len(outcome.allocation.net_targets) == 1
    net = outcome.allocation.net_targets[0]
    assert net.instrument_id == BTC
    assert net.target_notional == Money(0, NOTIONAL_SCALE, "USD")
    assert [item.sleeve_id for item in net.sleeve_attributions] == [CARRY, TREND]
    assert [item.target_notional.units for item in net.sleeve_attributions] == [
        -30_000_000_000_000_000,
        30_000_000_000_000_000,
    ]


def test_state_allocation_and_registration_order_do_not_change_identity() -> None:
    portfolio_snapshot = snapshot()
    allocator = PortfolioAllocator()

    first = allocator.allocate(
        sleeve_state=state(),
        portfolio_snapshot=portfolio_snapshot,
        allocations=allocations(portfolio_snapshot),
        target_notional_scale=NOTIONAL_SCALE,
    )
    reordered = allocator.allocate(
        sleeve_state=state(reverse=True),
        portfolio_snapshot=portfolio_snapshot,
        allocations=allocations(portfolio_snapshot, reverse=True),
        target_notional_scale=NOTIONAL_SCALE,
    )

    assert first.allocation is not None
    assert reordered.allocation is not None
    assert first.allocation == reordered.allocation
    assert first.allocation.allocation_hash == reordered.allocation.allocation_hash
    assert first.allocation.allocation_id.startswith(
        "portfolio-allocation-v1:sha256:"
    )


def test_target_tuple_order_does_not_change_allocation_identity() -> None:
    portfolio_snapshot = snapshot()
    base = decision("trend-v1", TREND, 500_000_000_000)
    btc_target = base.target_snapshot.targets[0]
    eth_target = TargetExposureFraction(ETH, 250_000_000_000)
    forward = LatestSleeveDecisionState(
        as_of=UtcInstant(100),
        decisions=(
            replace(
                base,
                target_snapshot=replace(
                    base.target_snapshot,
                    targets=(btc_target, eth_target),
                ),
            ),
        ),
    )
    reverse = LatestSleeveDecisionState(
        as_of=UtcInstant(100),
        decisions=(
            replace(
                base,
                target_snapshot=replace(
                    base.target_snapshot,
                    targets=(eth_target, btc_target),
                ),
            ),
        ),
    )
    declared = (allocations(portfolio_snapshot)[0],)

    first = PortfolioAllocator().allocate(
        sleeve_state=forward,
        portfolio_snapshot=portfolio_snapshot,
        allocations=declared,
        target_notional_scale=NOTIONAL_SCALE,
    )
    reordered = PortfolioAllocator().allocate(
        sleeve_state=reverse,
        portfolio_snapshot=portfolio_snapshot,
        allocations=declared,
        target_notional_scale=NOTIONAL_SCALE,
    )

    assert first.allocation is not None
    assert reordered.allocation is not None
    assert first.allocation == reordered.allocation
    assert first.allocation.allocation_hash == reordered.allocation.allocation_hash


def test_missing_duplicate_and_unexpected_allocations_fail_atomically() -> None:
    portfolio_snapshot = snapshot()
    declared = allocations(portfolio_snapshot)
    unexpected = StrategyAllocation(
        strategy_id="other-v1",
        sleeve_id=StrategySleeveId("other.primary"),
        valuation_time=UtcInstant(100),
        valuation_currency=USD,
        allocation_nav=Money(0, MONEY_SCALE, "USD"),
        policy_ref=POLICY,
        source_portfolio_snapshot_hash=canonical_sha256(portfolio_snapshot),
    )
    outcome = PortfolioAllocator().allocate(
        sleeve_state=state(),
        portfolio_snapshot=portfolio_snapshot,
        allocations=(declared[0], declared[0], unexpected),
        target_notional_scale=NOTIONAL_SCALE,
    )

    assert outcome.allocation is None
    assert failure_codes(outcome) == {
        AllocationConstraintCode.DUPLICATE_ALLOCATION,
        AllocationConstraintCode.MISSING_ALLOCATION,
        AllocationConstraintCode.UNEXPECTED_ALLOCATION,
    }


def test_negative_and_over_budget_allocations_are_explicit_failures() -> None:
    portfolio_snapshot = snapshot()
    declared = allocations(portfolio_snapshot)

    negative = PortfolioAllocator().allocate(
        sleeve_state=state(),
        portfolio_snapshot=portfolio_snapshot,
        allocations=(
            replace(
                declared[0],
                allocation_nav=Money(-1, MONEY_SCALE, "USD"),
            ),
            declared[1],
        ),
        target_notional_scale=NOTIONAL_SCALE,
    )
    over_budget = PortfolioAllocator().allocate(
        sleeve_state=state(),
        portfolio_snapshot=portfolio_snapshot,
        allocations=(
            replace(
                declared[0],
                allocation_nav=Money(70_000, MONEY_SCALE, "USD"),
            ),
            declared[1],
        ),
        target_notional_scale=NOTIONAL_SCALE,
    )

    assert failure_codes(negative) == {
        AllocationConstraintCode.NEGATIVE_ALLOCATION_NAV
    }
    assert failure_codes(over_budget) == {
        AllocationConstraintCode.TOTAL_ALLOCATION_EXCEEDS_EQUITY
    }


def test_allocation_context_mismatches_fail_closed() -> None:
    portfolio_snapshot = snapshot()
    declared = allocations(portfolio_snapshot)
    other_policy = CapitalAllocationPolicyRef(
        "capital.fixed-initial.v1", 1, "sha256:" + "e" * 64
    )
    outcome = PortfolioAllocator().allocate(
        sleeve_state=state(),
        portfolio_snapshot=portfolio_snapshot,
        allocations=(
            replace(declared[0], strategy_id="wrong-v1"),
            replace(
                declared[1],
                valuation_time=UtcInstant(99),
                valuation_currency=CurrencyId("EUR"),
                allocation_nav=Money(40_000, Scale(3), "EUR"),
                policy_ref=other_policy,
                source_portfolio_snapshot_hash="sha256:" + "f" * 64,
            ),
        ),
        target_notional_scale=NOTIONAL_SCALE,
    )

    assert outcome.allocation is None
    assert failure_codes(outcome) == {
        AllocationConstraintCode.STRATEGY_ID_MISMATCH,
        AllocationConstraintCode.VALUATION_TIME_MISMATCH,
        AllocationConstraintCode.VALUATION_CURRENCY_MISMATCH,
        AllocationConstraintCode.ALLOCATION_SCALE_MISMATCH,
        AllocationConstraintCode.SNAPSHOT_HASH_MISMATCH,
        AllocationConstraintCode.POLICY_MISMATCH,
    }


def test_not_yet_effective_and_expired_targets_fail_closed() -> None:
    portfolio_snapshot = snapshot()
    declared = allocations(portfolio_snapshot)
    future_state = LatestSleeveDecisionState(
        as_of=UtcInstant(100),
        decisions=(
            decision(
                "trend-v1",
                TREND,
                500_000_000_000,
                effective_time=101,
                expires_at=200,
            ),
        ),
    )
    expired_state = LatestSleeveDecisionState(
        as_of=UtcInstant(100),
        decisions=(
            decision(
                "trend-v1",
                TREND,
                500_000_000_000,
                decision_time=80,
                effective_time=80,
                expires_at=100,
            ),
        ),
    )

    future = PortfolioAllocator().allocate(
        sleeve_state=future_state,
        portfolio_snapshot=portfolio_snapshot,
        allocations=(declared[0],),
        target_notional_scale=NOTIONAL_SCALE,
    )
    expired = PortfolioAllocator().allocate(
        sleeve_state=expired_state,
        portfolio_snapshot=portfolio_snapshot,
        allocations=(declared[0],),
        target_notional_scale=NOTIONAL_SCALE,
    )

    assert failure_codes(future) == {AllocationConstraintCode.TARGET_NOT_EFFECTIVE}
    assert failure_codes(expired) == {AllocationConstraintCode.TARGET_EXPIRED}


def test_target_notional_requires_exact_declared_scale() -> None:
    portfolio_snapshot = snapshot()
    declared = allocations(portfolio_snapshot)
    inexact_state = LatestSleeveDecisionState(
        as_of=UtcInstant(100),
        decisions=(
            decision("trend-v1", TREND, 333_333_333_333),
        ),
    )

    outcome = PortfolioAllocator().allocate(
        sleeve_state=inexact_state,
        portfolio_snapshot=portfolio_snapshot,
        allocations=(declared[0],),
        target_notional_scale=Scale(2),
    )

    assert outcome.allocation is None
    assert failure_codes(outcome) == {
        AllocationConstraintCode.TARGET_NOTIONAL_INEXACT
    }
