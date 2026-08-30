from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest
from crypto_quant_backtest import (
    ConservativeLinearLiquidationAuditModel,
    LinearLiquidationAccountWindowEvidence,
    LinearLiquidationAuditClassification,
    LinearLiquidationAuditFailure,
    LinearLiquidationAuditFailureCode,
    LinearLiquidationAuditRequest,
    LinearLiquidationAuditResult,
    LinearLiquidationMarkBarEvidence,
    LinearLiquidationPositionAudit,
    RequestedResultGrade,
)
from crypto_quant_domain import (
    CashBalance,
    InstrumentId,
    Money,
    Price,
    PricePurpose,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
)
from crypto_quant_trading import (
    LedgerState,
    LinearAccountMarginProjector,
    LinearInstrumentMarginModel,
    LinearMarginRuleBook,
)

from tests.kernel.derivatives._fixtures import (
    INSTRUMENT_ID,
    PRICE_SCALE,
    QUOTE_CURRENCY,
)
from tests.kernel.derivatives.test_linear_account_margin_projection import (
    CASH_KEY,
    _multi_instrument_projection,
)
from tests.kernel.derivatives.test_linear_account_margin_projection import (
    _request as account_margin_request,
)
from tests.kernel.derivatives.test_linear_margin_requirement import (
    _request as margin_request,
)

BAR_START = UtcInstant(10)
BAR_END = UtcInstant(20)
AUDIT_AT = SimulationInstant(
    UtcInstant(22), TimelinePhase(100, "liquidation_audit"), SourceSequence(0)
)


def _sim(nanoseconds: int, rank: int, code: str) -> SimulationInstant:
    return SimulationInstant(
        UtcInstant(nanoseconds), TimelinePhase(rank, code), SourceSequence(0)
    )


def _projection(wallet_units: int = 100_000, quantity_units: int = 1_000):
    request = account_margin_request(quantity_units)
    ledger_evidence = request.ledger_evidence
    assert ledger_evidence is not None
    ledger = ledger_evidence.ledger_state
    updated_ledger = LedgerState(
        ledger.schema,
        ledger.cursor,
        (CashBalance(CASH_KEY, replace(ledger.cash_balances[0].amount, units=wallet_units)),),
        ledger.position_balances,
        ledger.realized_pnl,
        ledger.fees,
        ledger.financing,
    )
    outcome = LinearAccountMarginProjector().project(
        replace(
            request,
            ledger_evidence=replace(ledger_evidence, ledger_state=updated_ledger),
        )
    )
    assert outcome.projection is not None
    return outcome.projection


def _window(
    wallet_units: int = 100_000, quantity_units: int = 1_000
) -> LinearLiquidationAccountWindowEvidence:
    return LinearLiquidationAccountWindowEvidence(
        account_projection=_projection(wallet_units, quantity_units),
        interval_start=BAR_START,
        interval_end_exclusive=BAR_END,
        available_at=_sim(21, 80, "account_window_available"),
        source_key="synthetic.liquidation-account-window.v1",
        source_hash="sha256:" + "1" * 64,
    )


def _bar(
    low_units: int = 8_000,
    high_units: int = 12_000,
    *,
    price_purpose: PricePurpose = PricePurpose.LIQUIDATION,
) -> LinearLiquidationMarkBarEvidence:
    return LinearLiquidationMarkBarEvidence(
        bar_id="synthetic-btc-liquidation-mark-bar-10-20",
        instrument_id=INSTRUMENT_ID,
        price_purpose=price_purpose,
        interval_start=BAR_START,
        interval_end_exclusive=BAR_END,
        low=Price(
            low_units,
            PRICE_SCALE,
            str(INSTRUMENT_ID),
            str(QUOTE_CURRENCY),
        ),
        high=Price(
            high_units,
            PRICE_SCALE,
            str(INSTRUMENT_ID),
            str(QUOTE_CURRENCY),
        ),
        closed_at=_sim(20, 50, "liquidation_bar_closed"),
        available_at=_sim(21, 60, "liquidation_bar_available"),
        stream_id="synthetic.liquidation-mark.1m.v1",
        event_id="synthetic-liquidation-mark-bar-event",
        revision_id="synthetic-liquidation-mark-bar-revision",
        supersedes_revision_id=None,
        source_key="synthetic.liquidation-mark-bars.v1",
        source_hash="sha256:" + "2" * 64,
    )


def _request(
    *,
    wallet_units: int = 100_000,
    low_units: int = 8_000,
    high_units: int = 12_000,
    requested_grade: RequestedResultGrade = RequestedResultGrade.DEVELOPMENT,
    quantity_units: int = 1_000,
) -> LinearLiquidationAuditRequest:
    return LinearLiquidationAuditRequest(
        account_window=_window(wallet_units, quantity_units),
        liquidation_bars=(_bar(low_units, high_units),),
        audit_at=AUDIT_AT,
        requested_grade=requested_grade,
    )


def test_long_low_safe_recomputes_adverse_equity_and_maintenance() -> None:
    outcome = ConservativeLinearLiquidationAuditModel().audit_liquidation(
        _request()
    )

    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert result.classification == LinearLiquidationAuditClassification.SAFE
    assert result.decision_grade_eligible is True
    assert result.position_audits[0].direction == "long"
    assert result.position_audits[0].adverse_price.units == 8_000
    assert result.position_audits[0].adverse_unrealized.units == -125
    assert result.position_audits[0].adverse_maintenance.units == 10
    assert result.adverse_equity.units == 99_875
    assert result.adverse_maintenance.units == 10


def test_short_uses_high_and_adverse_notional_can_cross_tier() -> None:
    outcome = ConservativeLinearLiquidationAuditModel().audit_liquidation(
        _request(quantity_units=-1_000, high_units=50_000)
    )

    assert outcome.result is not None
    audit = outcome.result.position_audits[0]
    assert audit.direction == "short"
    assert audit.adverse_price.units == 50_000
    assert audit.adverse_unrealized.units == -5_125
    assert audit.resolved_tier.tier_id == "synthetic-margin-tier-2"
    assert audit.adverse_maintenance.units == 75


def _mixed_long_short_request() -> LinearLiquidationAuditRequest:
    projection = _multi_instrument_projection(-1_000)
    first_bar = _bar()
    second_instrument = projection.request.position_valuations[1].position_state.contract.instrument.instrument_id
    second_bar = replace(
        first_bar,
        bar_id="synthetic-eth-liquidation-mark-bar-10-20",
        instrument_id=second_instrument,
        low=Price(
            8_000,
            PRICE_SCALE,
            str(second_instrument),
            str(QUOTE_CURRENCY),
        ),
        high=Price(
            12_000,
            PRICE_SCALE,
            str(second_instrument),
            str(QUOTE_CURRENCY),
        ),
        stream_id="synthetic.eth-liquidation-mark.1m.v1",
        event_id="synthetic-eth-liquidation-mark-bar-event",
        revision_id="synthetic-eth-liquidation-mark-bar-revision",
    )
    window = replace(_window(), account_projection=projection)
    return LinearLiquidationAuditRequest(
        window,
        (first_bar, second_bar),
        AUDIT_AT,
        RequestedResultGrade.DEVELOPMENT,
    )


def test_mixed_long_short_positions_use_simultaneous_directional_extremes() -> None:
    outcome = ConservativeLinearLiquidationAuditModel().audit_liquidation(
        _mixed_long_short_request()
    )

    assert outcome.result is not None
    directions = tuple(
        value.direction for value in outcome.result.position_audits
    )
    assert directions == ("long", "short")
    assert outcome.result.adverse_unrealized.units == -500
    assert outcome.result.adverse_equity.units == 99_500
    assert outcome.result.adverse_maintenance.units == 25


def test_adverse_equity_equal_to_maintenance_is_safe() -> None:
    outcome = ConservativeLinearLiquidationAuditModel().audit_liquidation(
        _request(wallet_units=135)
    )

    assert outcome.result is not None
    assert outcome.result.adverse_equity.units == 10
    assert outcome.result.adverse_maintenance.units == 10
    assert outcome.result.classification == LinearLiquidationAuditClassification.SAFE


def test_development_ambiguous_breach_preserves_audit_without_trigger() -> None:
    outcome = ConservativeLinearLiquidationAuditModel().audit_liquidation(
        _request(wallet_units=100, low_units=100)
    )

    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert (
        result.classification
        == LinearLiquidationAuditClassification.AMBIGUOUS_BREACH
    )
    assert result.decision_grade_eligible is False
    assert result.adverse_equity.units < result.adverse_maintenance.units
    assert result.limitation == (
        "bar-extremes-do-not-identify-intrabar-path-or-liquidation-time"
    )
    assert not hasattr(result, "liquidation_time")
    assert not hasattr(result, "liquidation_price")


def test_decision_grade_ambiguous_breach_fails_closed() -> None:
    outcome = ConservativeLinearLiquidationAuditModel().audit_liquidation(
        _request(
            wallet_units=100,
            low_units=100,
            requested_grade=RequestedResultGrade.DECISION_GRADE,
        )
    )

    assert outcome.result is None
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        == LinearLiquidationAuditFailureCode.AMBIGUOUS_BREACH_NOT_DECISION_GRADE
    )


def test_missing_window_precedes_missing_bars() -> None:
    request = _request()
    outcome = ConservativeLinearLiquidationAuditModel().audit_liquidation(
        replace(request, account_window=None, liquidation_bars=None)
    )

    assert len(LinearLiquidationAuditFailureCode) == 16
    assert outcome.result is None
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        == LinearLiquidationAuditFailureCode.MISSING_ACCOUNT_WINDOW
    )


def _negative_maintenance_request() -> LinearLiquidationAuditRequest:
    account_request = account_margin_request()
    base_margin_request = margin_request()
    rule_book = base_margin_request.rule_book
    assert rule_book is not None
    interval = rule_book.intervals[0]
    tiers = interval.tiers
    changed_interval = replace(
        interval,
        tiers=(
            replace(
                tiers[0],
                maintenance_margin_deduction=Money(
                    10, PRICE_SCALE, str(QUOTE_CURRENCY)
                ),
            ),
            tiers[1],
        ),
    )
    changed_rule_book = LinearMarginRuleBook.create(
        rule_book_key="synthetic.negative-adverse-maintenance.v1",
        rule_book_version=1,
        instrument_id=rule_book.instrument_id,
        settlement_currency_id=rule_book.settlement_currency_id,
        tier_scale=rule_book.tier_scale,
        intervals=(changed_interval,),
    )
    margin_outcome = LinearInstrumentMarginModel().evaluate_margin(
        replace(base_margin_request, rule_book=changed_rule_book)
    )
    assert margin_outcome.result is not None
    projection_outcome = LinearAccountMarginProjector().project(
        replace(account_request, margin_results=(margin_outcome.result,))
    )
    assert projection_outcome.projection is not None
    window = replace(
        _window(), account_projection=projection_outcome.projection
    )
    return LinearLiquidationAuditRequest(
        window,
        (_bar(low_units=100),),
        AUDIT_AT,
        RequestedResultGrade.DEVELOPMENT,
    )


def _failure_cases() -> list[
    tuple[LinearLiquidationAuditFailureCode, LinearLiquidationAuditRequest]
]:
    request = _request()
    window = request.account_window
    bars = request.liquidation_bars
    assert window is not None and bars is not None
    bar = bars[0]
    forged_projection = deepcopy(window.account_projection)
    object.__setattr__(forged_projection, "request_hash", "sha256:" + "0" * 64)
    later = SimulationInstant(
        AUDIT_AT.instant,
        TimelinePhase(110, "later_liquidation_evidence"),
        SourceSequence(0),
    )
    other_instrument = InstrumentId(
        INSTRUMENT_ID.venue, "eth-usdt-linear-perpetual"
    )
    return [
        (
            LinearLiquidationAuditFailureCode.MISSING_ACCOUNT_WINDOW,
            replace(request, account_window=None),
        ),
        (
            LinearLiquidationAuditFailureCode.MISSING_LIQUIDATION_BARS,
            replace(request, liquidation_bars=None),
        ),
        (
            LinearLiquidationAuditFailureCode.PROJECTION_CONTEXT_MISMATCH,
            replace(
                request,
                account_window=replace(
                    window, account_projection=forged_projection
                ),
            ),
        ),
        (
            LinearLiquidationAuditFailureCode.ACCOUNT_WINDOW_INTERVAL_MISMATCH,
            replace(
                request,
                account_window=replace(
                    window, interval_start=UtcInstant(11)
                ),
            ),
        ),
        (
            LinearLiquidationAuditFailureCode.ACCOUNT_WINDOW_NOT_AVAILABLE,
            replace(
                request,
                account_window=replace(window, available_at=later),
            ),
        ),
        (
            LinearLiquidationAuditFailureCode.DUPLICATE_LIQUIDATION_BAR,
            replace(request, liquidation_bars=(bar, bar)),
        ),
        (
            LinearLiquidationAuditFailureCode.LIQUIDATION_BAR_COVERAGE_MISMATCH,
            replace(request, liquidation_bars=()),
        ),
        (
            LinearLiquidationAuditFailureCode.LIQUIDATION_BAR_INTERVAL_MISMATCH,
            replace(
                request,
                liquidation_bars=(
                    replace(bar, interval_start=UtcInstant(11)),
                ),
            ),
        ),
        (
            LinearLiquidationAuditFailureCode.LIQUIDATION_BAR_NOT_CLOSED,
            replace(
                request,
                liquidation_bars=(
                    replace(
                        bar,
                        closed_at=_sim(19, 50, "liquidation_bar_not_closed"),
                    ),
                ),
            ),
        ),
        (
            LinearLiquidationAuditFailureCode.LIQUIDATION_BAR_NOT_AVAILABLE,
            replace(
                request,
                liquidation_bars=(replace(bar, available_at=later),),
            ),
        ),
        (
            LinearLiquidationAuditFailureCode.LIQUIDATION_BAR_PURPOSE_MISMATCH,
            replace(
                request,
                liquidation_bars=(
                    replace(bar, price_purpose=PricePurpose.MARGIN),
                ),
            ),
        ),
        (
            LinearLiquidationAuditFailureCode.LIQUIDATION_BAR_CONTEXT_MISMATCH,
            replace(
                request,
                liquidation_bars=(
                    replace(
                        bar,
                        low=Price(
                            bar.low.units,
                            PRICE_SCALE,
                            str(other_instrument),
                            str(QUOTE_CURRENCY),
                        ),
                        high=Price(
                            bar.high.units,
                            PRICE_SCALE,
                            str(other_instrument),
                            str(QUOTE_CURRENCY),
                        ),
                    ),
                ),
            ),
        ),
        (
            LinearLiquidationAuditFailureCode.LIQUIDATION_BAR_SCALE_MISMATCH,
            replace(
                request,
                liquidation_bars=(
                    replace(
                        bar,
                        low=Price(
                            80_000,
                            Scale(3),
                            str(INSTRUMENT_ID),
                            str(QUOTE_CURRENCY),
                        ),
                    ),
                ),
            ),
        ),
        (
            LinearLiquidationAuditFailureCode.INVALID_LIQUIDATION_BAR_EXTREMES,
            replace(
                request,
                liquidation_bars=(
                    replace(bar, low=replace(bar.low, units=0)),
                ),
            ),
        ),
        (
            LinearLiquidationAuditFailureCode.NEGATIVE_ADVERSE_MAINTENANCE,
            _negative_maintenance_request(),
        ),
        (
            LinearLiquidationAuditFailureCode.AMBIGUOUS_BREACH_NOT_DECISION_GRADE,
            _request(
                wallet_units=100,
                low_units=100,
                requested_grade=RequestedResultGrade.DECISION_GRADE,
            ),
        ),
    ]


def test_all_failures_follow_frozen_precedence() -> None:
    cases = _failure_cases()
    assert len(cases) == len(LinearLiquidationAuditFailureCode) == 16

    for expected, request in cases:
        outcome = ConservativeLinearLiquidationAuditModel().audit_liquidation(
            request
        )
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is expected
        assert outcome.failure.subject_ids[0] == expected.value


def test_result_position_and_failure_constructors_reject_forgery() -> None:
    request = _request()
    before = deepcopy(request)
    first = ConservativeLinearLiquidationAuditModel().audit_liquidation(request)
    second = ConservativeLinearLiquidationAuditModel().audit_liquidation(request)
    assert first == second
    assert request == before
    assert first.result is not None
    result = first.result
    with pytest.raises(ValueError, match="Result fields"):
        LinearLiquidationAuditResult(
            result.component_ref,
            result.request,
            result.input_hash,
            result.classification,
            result.position_audits,
            result.wallet_balance,
            result.adverse_unrealized,
            replace(result.adverse_equity, units=result.adverse_equity.units + 1),
            result.adverse_maintenance,
            result.decision_grade_eligible,
            result.limitation,
        )
    audit = result.position_audits[0]
    with pytest.raises(ValueError, match="Position Audit fields"):
        LinearLiquidationPositionAudit(
            audit.position_valuation,
            audit.margin_result,
            audit.position_key,
            audit.direction,
            audit.bar,
            replace(audit.adverse_price, units=audit.adverse_price.units + 1),
            audit.resolved_tier,
            audit.exact_adverse_unrealized,
            audit.adverse_unrealized,
            audit.exact_adverse_maintenance,
            audit.adverse_maintenance,
        )

    failed = ConservativeLinearLiquidationAuditModel().audit_liquidation(
        replace(request, account_window=None)
    )
    assert failed.failure is not None
    failure = failed.failure
    with pytest.raises(ValueError, match="subject_ids"):
        LinearLiquidationAuditFailure(
            failure.component_ref,
            failure.request,
            failure.input_hash,
            failure.code,
            ("forged",),
        )


def test_public_audit_values_are_frozen_contract_types() -> None:
    outcome = ConservativeLinearLiquidationAuditModel().audit_liquidation(_request())
    assert isinstance(outcome.result, LinearLiquidationAuditResult)
    assert not isinstance(outcome.failure, LinearLiquidationAuditFailure)
    assert isinstance(outcome.result.position_audits[0], LinearLiquidationPositionAudit)


def test_v2_accepts_raw_scale8_extremes_while_v1_rejects_them() -> None:
    from crypto_quant_backtest import ConservativeLinearLiquidationAuditModelV2

    raw = replace(
        _request(),
        liquidation_bars=(
            replace(
                _bar(),
                low=Price(80_000_001, Scale(8), str(INSTRUMENT_ID), str(QUOTE_CURRENCY)),
                high=Price(120_000_001, Scale(8), str(INSTRUMENT_ID), str(QUOTE_CURRENCY)),
            ),
        ),
    )
    assert ConservativeLinearLiquidationAuditModel().audit_liquidation(raw).failure.code is LinearLiquidationAuditFailureCode.LIQUIDATION_BAR_SCALE_MISMATCH
    result = ConservativeLinearLiquidationAuditModelV2().audit_liquidation(raw).result
    assert result is not None
    assert result.component_ref == ConservativeLinearLiquidationAuditModelV2().component_ref
    assert result.position_audits[0].adverse_price.scale == Scale(8)
