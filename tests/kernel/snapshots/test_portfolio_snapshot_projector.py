from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import Any, cast

import pytest

from crypto_quant_domain import (
    CashBalanceKey,
    CurrencyId,
    InstrumentId,
    Money,
    PortfolioSnapshot,
    PositionBalanceKey,
    PricePurpose,
    Scale,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading import (
    PortfolioSnapshotProjector,
    PortfolioValueKind,
    PortfolioValueRef,
    ReportingCurrencyValuation,
    ResolvedMark,
    SnapshotProjectionFailureCode,
    SnapshotProjectionOutcome,
)

from ._fixtures import (
    EUR_KEY,
    FX,
    MONEY_SCALE,
    STOCK_KEY,
    USD,
    USD_KEY,
    VALUATION_AT,
    ledger_state,
    resolved_mark,
    snapshot_inputs,
)


def project(**overrides: object) -> SnapshotProjectionOutcome:
    inputs = snapshot_inputs()
    inputs.update(overrides)
    return PortfolioSnapshotProjector().project(**inputs)  # type: ignore[arg-type]


def assert_failure(
    outcome: SnapshotProjectionOutcome, code: SnapshotProjectionFailureCode
) -> None:
    assert outcome.snapshot is None
    assert outcome.failure is not None
    assert outcome.failure.code is code


def test_value_refs_and_valuations_are_typed_immutable_evidence() -> None:
    cash_ref = PortfolioValueRef(PortfolioValueKind.CASH, USD_KEY)
    position_ref = PortfolioValueRef(
        PortfolioValueKind.POSITION_MARKET_VALUE, STOCK_KEY
    )
    valuation = cast(
        tuple[ReportingCurrencyValuation, ...], snapshot_inputs()["valuations"]
    )[2]

    assert cash_ref.ref_hash == canonical_sha256(cash_ref)
    assert position_ref.ref_hash == canonical_sha256(position_ref)
    assert valuation.valuation_hash == canonical_sha256(valuation)
    with pytest.raises(TypeError):
        PortfolioValueRef(PortfolioValueKind.CASH, STOCK_KEY)
    with pytest.raises(TypeError):
        PortfolioValueRef(PortfolioValueKind.UNREALIZED_PNL, EUR_KEY)
    with pytest.raises(ValueError, match="QuantizationPolicy"):
        replace(valuation, quantization_policy=None)
    with pytest.raises(FrozenInstanceError):
        cast(Any, cash_ref).kind = PortfolioValueKind.FEES


def test_projection_is_order_independent_and_exactly_rebuildable() -> None:
    forward = project()
    reverse = project(**snapshot_inputs(reverse=True))

    assert forward.failure is None
    assert isinstance(forward.snapshot, PortfolioSnapshot)
    snapshot = forward.snapshot
    assert reverse.snapshot == snapshot
    assert canonical_sha256(reverse.snapshot) == canonical_sha256(snapshot)
    assert snapshot.reporting_currency == USD
    assert snapshot.realized_pnl == Money(1_100, MONEY_SCALE, "USD")
    assert snapshot.unrealized_pnl == Money(3_300, MONEY_SCALE, "USD")
    assert snapshot.fees == Money(220, MONEY_SCALE, "USD")
    assert snapshot.financing == Money(-100, MONEY_SCALE, "USD")
    assert snapshot.equity == Money(138_500, MONEY_SCALE, "USD")
    assert snapshot.journal_state_hash == ledger_state().state_hash
    assert len(snapshot.valuation_marks) == 2


def test_valuation_coverage_must_be_exact_and_unique() -> None:
    inputs = snapshot_inputs()
    valuations = cast(tuple[ReportingCurrencyValuation, ...], inputs["valuations"])

    assert_failure(
        project(valuations=valuations[:-1]),
        SnapshotProjectionFailureCode.VALUATION_COVERAGE_MISMATCH,
    )
    assert_failure(
        project(valuations=valuations + (valuations[0],)),
        SnapshotProjectionFailureCode.VALUATION_COVERAGE_MISMATCH,
    )
    extra_ref = PortfolioValueRef(PortfolioValueKind.FEES, USD_KEY)
    assert_failure(
        project(valuations=valuations + (replace(valuations[0], value_ref=extra_ref),)),
        SnapshotProjectionFailureCode.VALUATION_COVERAGE_MISMATCH,
    )


def test_native_reporting_path_and_graph_context_fail_closed() -> None:
    valuations = cast(
        tuple[ReportingCurrencyValuation, ...], snapshot_inputs()["valuations"]
    )
    eur_cash = valuations[1]

    assert_failure(
        project(
            valuations=(
                valuations[0],
                replace(eur_cash, native_value=Money(19_999, MONEY_SCALE, "EUR")),
                *valuations[2:],
            )
        ),
        SnapshotProjectionFailureCode.NATIVE_VALUE_MISMATCH,
    )
    assert_failure(
        project(
            valuations=(
                valuations[0],
                replace(
                    eur_cash,
                    reporting_value=Money(22_000, Scale(3), "USD"),
                ),
                *valuations[2:],
            )
        ),
        SnapshotProjectionFailureCode.REPORTING_CONTEXT_MISMATCH,
    )
    assert_failure(
        project(
            valuations=(
                valuations[0],
                replace(
                    eur_cash,
                    currency_valuation_graph_hash="sha256:" + "f" * 64,
                ),
                *valuations[2:],
            )
        ),
        SnapshotProjectionFailureCode.CURRENCY_GRAPH_MISMATCH,
    )
    assert_failure(
        project(timestamp=UtcInstant(101)),
        SnapshotProjectionFailureCode.VALUATION_PATH_MISMATCH,
    )


def test_position_mark_and_exact_notional_are_required() -> None:
    valuations = cast(
        tuple[ReportingCurrencyValuation, ...], snapshot_inputs()["valuations"]
    )
    market_value = valuations[2]

    assert_failure(
        project(
            valuations=(
                *valuations[:2],
                replace(
                    market_value,
                    native_value=Money(14_999, MONEY_SCALE, "EUR"),
                ),
                *valuations[3:],
            )
        ),
        SnapshotProjectionFailureCode.POSITION_NOTIONAL_MISMATCH,
    )
    wrong_mark = resolved_mark(
        InstrumentId(VenueId("synthetic"), "other"),
        EUR_KEY.currency_id,
        5_000,
    )
    marks = cast(tuple[ResolvedMark, ...], snapshot_inputs()["resolved_marks"])
    assert_failure(
        project(resolved_marks=(wrong_mark, marks[1])),
        SnapshotProjectionFailureCode.POSITION_MARK_MISMATCH,
    )


def test_mark_set_must_exactly_cover_positions_and_currency_paths() -> None:
    marks = cast(tuple[ResolvedMark, ...], snapshot_inputs()["resolved_marks"])

    assert_failure(
        project(resolved_marks=marks[:1]),
        SnapshotProjectionFailureCode.MARK_COVERAGE_MISMATCH,
    )
    extra_mark = resolved_mark(
        InstrumentId(VenueId("synthetic"), "extra"), CurrencyId("USD"), 100
    )
    assert_failure(
        project(resolved_marks=marks + (extra_mark,)),
        SnapshotProjectionFailureCode.MARK_COVERAGE_MISMATCH,
    )
    future_fx = replace(
        marks[1], resolved_at=UtcInstant(101), age_nanoseconds=11
    )
    assert_failure(
        project(resolved_marks=(marks[0], future_fx)),
        SnapshotProjectionFailureCode.MARK_COVERAGE_MISMATCH,
    )


def test_v1_rejects_multiple_accounts_and_outcome_is_exclusive() -> None:
    assert_failure(
        project(ledger_state=ledger_state(second_account=True)),
        SnapshotProjectionFailureCode.MULTIPLE_ACCOUNTS,
    )
    successful = project()
    failed = project(ledger_state=ledger_state(second_account=True))
    assert successful.snapshot is not None
    assert failed.failure is not None
    with pytest.raises(ValueError, match="exactly one"):
        SnapshotProjectionOutcome(successful.snapshot, failed.failure)
    with pytest.raises(ValueError, match="exactly one"):
        SnapshotProjectionOutcome(None, None)
