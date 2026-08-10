from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from crypto_quant_domain import (
    CashBalanceKey,
    CurrencyId,
    InstrumentId,
    Money,
    Price,
    PricePurpose,
    QuantizationPolicy,
    Quantity,
    Rate,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
)
from crypto_quant_trading import (
    ExactLinearMarginAmount,
    LedgerBalanceRegistration,
    LinearInstrumentMarginFailure,
    LinearInstrumentMarginFailureCode,
    LinearInstrumentMarginModel,
    LinearInstrumentMarginRequest,
    LinearInstrumentMarginResult,
    LinearMarginLeverageEvidence,
    LinearMarginMarkEvidence,
    LinearMarginRuleBook,
    LinearMarginRuleInterval,
    LinearMarginTier,
    ProfilePortType,
    ResolvedMark,
    StaleMarkPolicy,
)

from tests.kernel.derivatives._fixtures import (
    ACCOUNT_ID,
    INSTRUMENT_ID,
    PRICE_SCALE,
    QUOTE_CURRENCY,
    QUANTITY_SCALE,
    VENUE_ID,
    contract,
    position_key,
)


TIER_SCALE = Scale(2)
EVALUATED_AT = SimulationInstant(
    UtcInstant(10),
    TimelinePhase(100, "margin_requirement"),
    SourceSequence(0),
)


def _instant(
    nanoseconds: int, rank: int = 50, code: str = "margin_evidence"
) -> SimulationInstant:
    return SimulationInstant(
        UtcInstant(nanoseconds), TimelinePhase(rank, code), SourceSequence(0)
    )


def _leverage(units: int = 10, basis: str = "notional_per_initial_margin") -> LinearMarginLeverageEvidence:
    return LinearMarginLeverageEvidence(
        account_id=ACCOUNT_ID,
        instrument_id=INSTRUMENT_ID,
        selected_leverage=Rate(units, Scale(0), basis),
        effective_from=UtcInstant(0),
        effective_to_exclusive=None,
        available_at=_instant(9),
        source_key="synthetic.margin.leverage.v1",
        source_hash="sha256:" + "1" * 64,
    )


def _tiers() -> tuple[LinearMarginTier, ...]:
    return (
        LinearMarginTier(
            tier_id="synthetic-margin-tier-1",
            notional_floor=Money(0, TIER_SCALE, str(QUOTE_CURRENCY)),
            notional_cap=Money(5_000, TIER_SCALE, str(QUOTE_CURRENCY)),
            maximum_leverage=Rate(
                20, Scale(0), "notional_per_initial_margin"
            ),
            maintenance_margin_rate=Rate(
                1, Scale(2), "maintenance_margin_fraction_of_notional"
            ),
            maintenance_margin_deduction=Money(
                0, TIER_SCALE, str(QUOTE_CURRENCY)
            ),
        ),
        LinearMarginTier(
            tier_id="synthetic-margin-tier-2",
            notional_floor=Money(5_000, TIER_SCALE, str(QUOTE_CURRENCY)),
            notional_cap=None,
            maximum_leverage=Rate(
                10, Scale(0), "notional_per_initial_margin"
            ),
            maintenance_margin_rate=Rate(
                2, Scale(2), "maintenance_margin_fraction_of_notional"
            ),
            maintenance_margin_deduction=Money(
                50, TIER_SCALE, str(QUOTE_CURRENCY)
            ),
        ),
    )


def _interval(
    *,
    interval_id: str = "synthetic-margin-interval-root",
    effective_from: UtcInstant = UtcInstant(0),
    effective_to_exclusive: UtcInstant | None = None,
    available_at: SimulationInstant = _instant(9),
    tiers: tuple[LinearMarginTier, ...] | None = None,
) -> LinearMarginRuleInterval:
    return LinearMarginRuleInterval(
        interval_id=interval_id,
        effective_from=effective_from,
        effective_to_exclusive=effective_to_exclusive,
        available_at=available_at,
        tiers=_tiers() if tiers is None else tiers,
        source_key="synthetic.margin.rules.v1",
        source_hash="sha256:" + "2" * 64,
    )


def _rule_book(
    intervals: tuple[LinearMarginRuleInterval, ...] | None = None,
    *,
    instrument_id: InstrumentId = INSTRUMENT_ID,
    settlement_currency_id: CurrencyId = QUOTE_CURRENCY,
    tier_scale: Scale = TIER_SCALE,
) -> LinearMarginRuleBook:
    return LinearMarginRuleBook.create(
        rule_book_key="synthetic.linear-margin-rules.v1",
        rule_book_version=1,
        instrument_id=instrument_id,
        settlement_currency_id=settlement_currency_id,
        tier_scale=tier_scale,
        intervals=(_interval(),) if intervals is None else intervals,
    )


def _mark_evidence() -> LinearMarginMarkEvidence:
    policy = StaleMarkPolicy(
        "synthetic.margin-mark.v1", 1, PricePurpose.MARGIN, 10, True
    )
    return LinearMarginMarkEvidence(
        ResolvedMark(
            instrument_id=INSTRUMENT_ID,
            quote_currency_id=QUOTE_CURRENCY,
            price_purpose=PricePurpose.MARGIN,
            price=Price(
                10_000,
                PRICE_SCALE,
                str(INSTRUMENT_ID),
                str(QUOTE_CURRENCY),
            ),
            observed_at=UtcInstant(8),
            available_at=UtcInstant(9),
            resolved_at=UtcInstant(10),
            age_nanoseconds=2,
            stream_id="synthetic.margin-mark.stream.v1",
            source_event_id="synthetic-margin-mark-event",
            revision_id="synthetic-margin-mark-revision",
            stale_policy_key=policy.policy_key,
            stale_policy_version=policy.policy_version,
            stale_policy_hash=policy.policy_hash,
        ),
        policy,
    )


def _request(
    quantity_units: int = 1_000,
    *,
    leverage_evidence: LinearMarginLeverageEvidence | None = None,
    rule_book: LinearMarginRuleBook | None = None,
    margin_mark_evidence: LinearMarginMarkEvidence | None = None,
    rounding: RoundingPolicy = RoundingPolicy.CEILING,
) -> LinearInstrumentMarginRequest:
    return LinearInstrumentMarginRequest(
        position_key=position_key(),
        contract=contract(),
        exposure_quantity=Quantity(
            quantity_units, QUANTITY_SCALE, str(INSTRUMENT_ID)
        ),
        evaluated_at=EVALUATED_AT,
        leverage_evidence=(
            _leverage() if leverage_evidence is None else leverage_evidence
        ),
        rule_book=_rule_book() if rule_book is None else rule_book,
        margin_mark_evidence=(
            _mark_evidence()
            if margin_mark_evidence is None
            else margin_mark_evidence
        ),
        settlement_cash_registration=LedgerBalanceRegistration(
            CashBalanceKey(ACCOUNT_ID, VENUE_ID, QUOTE_CURRENCY), Scale(2)
        ),
        requirement_quantization=QuantizationPolicy(
            "synthetic.margin-requirement.v1", Scale(2), rounding
        ),
    )


def test_exact_notional_initial_and_maintenance_requirements() -> None:
    request = _request()

    outcome = LinearInstrumentMarginModel().evaluate_margin(request)

    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert result.component_ref.port_type is ProfilePortType.MARGIN_MODEL
    assert result.resolved_tier.tier_id == "synthetic-margin-tier-1"
    assert result.exact_notional == ExactLinearMarginAmount(
        QUOTE_CURRENCY, 25, 2
    )
    assert result.exact_initial_margin == ExactLinearMarginAmount(
        QUOTE_CURRENCY, 5, 4
    )
    assert result.exact_maintenance_margin == ExactLinearMarginAmount(
        QUOTE_CURRENCY, 1, 8
    )
    assert result.initial_margin.units == 125
    assert result.maintenance_margin.units == 13
    assert result.request == request
    assert result.request_hash == request.request_hash


@pytest.mark.parametrize(
    ("quantity_units", "tier_id", "notional", "initial", "maintenance"),
    (
        (1_000, "synthetic-margin-tier-1", (25, 2), 125, 13),
        (-1_000, "synthetic-margin-tier-1", (25, 2), 125, 13),
        (0, "synthetic-margin-tier-1", (0, 1), 0, 0),
        (3_999, "synthetic-margin-tier-1", (3_999, 80), 500, 50),
        (4_000, "synthetic-margin-tier-2", (50, 1), 500, 50),
        (4_001, "synthetic-margin-tier-2", (4_001, 80), 501, 51),
    ),
)
def test_signed_quantity_tier_boundaries_and_ceiling_are_exact(
    quantity_units: int,
    tier_id: str,
    notional: tuple[int, int],
    initial: int,
    maintenance: int,
) -> None:
    outcome = LinearInstrumentMarginModel().evaluate_margin(
        _request(quantity_units)
    )

    assert outcome.result is not None
    result = outcome.result
    assert result.resolved_tier.tier_id == tier_id
    actual_notional = (
        result.exact_notional.numerator,
        result.exact_notional.denominator,
    )
    assert actual_notional == notional
    assert result.initial_margin.units == initial
    assert result.maintenance_margin.units == maintenance


def _with_mark(
    request: LinearInstrumentMarginRequest, mark: ResolvedMark
) -> LinearInstrumentMarginRequest:
    evidence = request.margin_mark_evidence
    assert evidence is not None
    return replace(
        request,
        margin_mark_evidence=replace(evidence, resolved_mark=mark),
    )


def _failure_cases() -> list[
    tuple[LinearInstrumentMarginFailureCode, LinearInstrumentMarginRequest]
]:
    request = _request()
    leverage = request.leverage_evidence
    rule_book = request.rule_book
    evidence = request.margin_mark_evidence
    assert leverage is not None and rule_book is not None and evidence is not None
    mark = evidence.resolved_mark
    tiers = _tiers()
    other_instrument = InstrumentId(VENUE_ID, "eth-usdt-linear-perpetual")
    late_mark = deepcopy(mark)
    object.__setattr__(late_mark, "available_at", UtcInstant(11))
    return [
        (
            LinearInstrumentMarginFailureCode.MISSING_LEVERAGE_EVIDENCE,
            replace(request, leverage_evidence=None),
        ),
        (
            LinearInstrumentMarginFailureCode.MISSING_MARGIN_RULE_BOOK,
            replace(request, rule_book=None),
        ),
        (
            LinearInstrumentMarginFailureCode.MISSING_MARGIN_MARK,
            replace(request, margin_mark_evidence=None),
        ),
        (
            LinearInstrumentMarginFailureCode.POSITION_CONTEXT_MISMATCH,
            replace(
                request,
                exposure_quantity=Quantity(
                    1_000, QUANTITY_SCALE, str(other_instrument)
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.LEVERAGE_CONTEXT_MISMATCH,
            replace(
                request,
                leverage_evidence=replace(leverage, account_id="other-account"),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.UNSUPPORTED_LEVERAGE_BASIS,
            replace(
                request,
                leverage_evidence=replace(
                    leverage,
                    selected_leverage=Rate(10, Scale(0), "other-basis"),
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.NON_POSITIVE_LEVERAGE,
            replace(
                request,
                leverage_evidence=replace(
                    leverage,
                    selected_leverage=Rate(
                        0, Scale(0), "notional_per_initial_margin"
                    ),
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.LEVERAGE_NOT_EFFECTIVE,
            replace(
                request,
                leverage_evidence=replace(
                    leverage, effective_from=UtcInstant(11)
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.LEVERAGE_NOT_AVAILABLE,
            replace(
                request,
                leverage_evidence=replace(leverage, available_at=_instant(11)),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.RULE_BOOK_CONTEXT_MISMATCH,
            replace(request, rule_book=_rule_book(instrument_id=other_instrument)),
        ),
        (
            LinearInstrumentMarginFailureCode.MISSING_HISTORICAL_RULE,
            replace(
                request,
                rule_book=_rule_book(
                    (
                        _interval(
                            effective_from=UtcInstant(11),
                            interval_id="future-current-margin-rule",
                        ),
                    )
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.OVERLAPPING_HISTORICAL_RULES,
            replace(
                request,
                rule_book=_rule_book(
                    (
                        _interval(interval_id="overlap-a"),
                        _interval(interval_id="overlap-b"),
                    )
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.HISTORICAL_RULE_NOT_AVAILABLE,
            replace(
                request,
                rule_book=_rule_book(
                    (_interval(available_at=_instant(11)),)
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.TIER_ORDER_MISMATCH,
            replace(
                request,
                rule_book=_rule_book((_interval(tiers=(tiers[1], tiers[0])),)),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.TIER_CONTEXT_MISMATCH,
            replace(
                request,
                rule_book=_rule_book(
                    (
                        _interval(
                            tiers=(
                                replace(
                                    tiers[0],
                                    notional_cap=Money(
                                        5_000, TIER_SCALE, "USD"
                                    ),
                                ),
                                tiers[1],
                            )
                        ),
                    )
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.TIER_GAP,
            replace(
                request,
                rule_book=_rule_book(
                    (
                        _interval(
                            tiers=(
                                tiers[0],
                                replace(
                                    tiers[1],
                                    notional_floor=Money(
                                        5_100, TIER_SCALE, str(QUOTE_CURRENCY)
                                    ),
                                ),
                            )
                        ),
                    )
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.TIER_OVERLAP,
            replace(
                request,
                rule_book=_rule_book(
                    (
                        _interval(
                            tiers=(
                                tiers[0],
                                replace(
                                    tiers[1],
                                    notional_floor=Money(
                                        4_900, TIER_SCALE, str(QUOTE_CURRENCY)
                                    ),
                                ),
                            )
                        ),
                    )
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.UNSUPPORTED_TIER_BASIS,
            replace(
                request,
                rule_book=_rule_book(
                    (
                        _interval(
                            tiers=(
                                replace(
                                    tiers[0],
                                    maximum_leverage=Rate(
                                        20, Scale(0), "other-basis"
                                    ),
                                ),
                                tiers[1],
                            )
                        ),
                    )
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.MARGIN_MARK_PURPOSE_MISMATCH,
            _with_mark(request, replace(mark, price_purpose=PricePurpose.FUNDING)),
        ),
        (
            LinearInstrumentMarginFailureCode.MARGIN_MARK_CONTEXT_MISMATCH,
            _with_mark(
                request,
                replace(
                    mark,
                    instrument_id=other_instrument,
                    price=Price(
                        mark.price.units,
                        mark.price.scale,
                        str(other_instrument),
                        str(QUOTE_CURRENCY),
                    ),
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.MARGIN_MARK_INSTANT_MISMATCH,
            _with_mark(
                request,
                replace(mark, resolved_at=UtcInstant(11), age_nanoseconds=3),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.MARGIN_MARK_SCALE_MISMATCH,
            _with_mark(
                request,
                replace(
                    mark,
                    price=Price(
                        100_000,
                        Scale(3),
                        str(INSTRUMENT_ID),
                        str(QUOTE_CURRENCY),
                    ),
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.NON_POSITIVE_MARGIN_MARK,
            _with_mark(request, replace(mark, price=replace(mark.price, units=0))),
        ),
        (
            LinearInstrumentMarginFailureCode.MARGIN_MARK_POLICY_MISMATCH,
            replace(
                request,
                margin_mark_evidence=replace(
                    evidence,
                    stale_policy=replace(
                        evidence.stale_policy, policy_key="other.margin-mark.v1"
                    ),
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.MARGIN_MARK_NOT_AVAILABLE,
            _with_mark(request, late_mark),
        ),
        (
            LinearInstrumentMarginFailureCode.LEVERAGE_EXCEEDS_TIER_MAXIMUM,
            replace(
                _request(4_000),
                leverage_evidence=_leverage(20),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.NEGATIVE_MAINTENANCE_REQUIREMENT,
            replace(
                request,
                rule_book=_rule_book(
                    (
                        _interval(
                            tiers=(
                                replace(
                                    tiers[0],
                                    maintenance_margin_deduction=Money(
                                        2_000, TIER_SCALE, str(QUOTE_CURRENCY)
                                    ),
                                ),
                                tiers[1],
                            )
                        ),
                    )
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.SETTLEMENT_CASH_CONTEXT_MISMATCH,
            replace(
                request,
                settlement_cash_registration=replace(
                    request.settlement_cash_registration,
                    key=CashBalanceKey("other-account", VENUE_ID, QUOTE_CURRENCY),
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.QUANTIZATION_SCALE_MISMATCH,
            replace(
                request,
                requirement_quantization=replace(
                    request.requirement_quantization, target_scale=Scale(3)
                ),
            ),
        ),
        (
            LinearInstrumentMarginFailureCode.UNSAFE_MARGIN_ROUNDING,
            replace(
                request,
                requirement_quantization=replace(
                    request.requirement_quantization,
                    rounding=RoundingPolicy.HALF_EVEN,
                ),
            ),
        ),
    ]


def test_all_failures_follow_frozen_precedence() -> None:
    assert len(LinearInstrumentMarginFailureCode) == 30

    for expected, request in _failure_cases():
        outcome = LinearInstrumentMarginModel().evaluate_margin(request)
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is expected
        assert len(outcome.failure.subject_ids) == 8
        assert outcome.failure.subject_ids[0] == expected.value
        assert outcome.failure.subject_ids[1] == ACCOUNT_ID
        assert outcome.failure.subject_ids[2] == str(INSTRUMENT_ID)


def test_history_large_integer_idempotency_and_input_authority() -> None:
    historical = _rule_book(
        (
            _interval(
                interval_id="closed-prior-margin-rule",
                effective_to_exclusive=UtcInstant(10),
            ),
            _interval(
                interval_id="active-boundary-margin-rule",
                effective_from=UtcInstant(10),
            ),
        )
    )
    request = _request(10**15 + 1, rule_book=historical)
    before = deepcopy(request)

    first = LinearInstrumentMarginModel().evaluate_margin(request)
    second = LinearInstrumentMarginModel().evaluate_margin(request)

    assert first == second
    assert request == before
    assert first.result is not None
    assert first.result.resolved_interval.interval_id == "active-boundary-margin-rule"
    assert first.result.resolved_tier.maximum_leverage == _leverage().selected_leverage
    assert first.result.exact_notional == ExactLinearMarginAmount(
        QUOTE_CURRENCY, 10**15 + 1, 80
    )

    leverage_boundary = LinearInstrumentMarginModel().evaluate_margin(
        _request(
            leverage_evidence=replace(
                _leverage(), effective_to_exclusive=UtcInstant(10)
            )
        )
    )
    assert leverage_boundary.failure is not None
    assert (
        leverage_boundary.failure.code
        is LinearInstrumentMarginFailureCode.LEVERAGE_NOT_EFFECTIVE
    )


def test_multi_defect_request_returns_only_first_failure() -> None:
    outcome = LinearInstrumentMarginModel().evaluate_margin(
        replace(
            _request(),
            leverage_evidence=None,
            rule_book=None,
            margin_mark_evidence=None,
        )
    )

    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is LinearInstrumentMarginFailureCode.MISSING_LEVERAGE_EVIDENCE
    )


def test_result_failure_and_exact_amount_constructors_reject_forgery() -> None:
    success = LinearInstrumentMarginModel().evaluate_margin(_request())
    assert success.result is not None
    result = success.result
    with pytest.raises(ValueError, match="Result fields"):
        LinearInstrumentMarginResult(
            result.component_ref,
            result.request,
            result.request_hash,
            result.resolved_interval,
            result.resolved_tier,
            result.exact_notional,
            result.exact_initial_margin,
            result.exact_maintenance_margin,
            replace(result.initial_margin, units=result.initial_margin.units + 1),
            result.maintenance_margin,
        )

    failed_request = replace(_request(), leverage_evidence=None)
    failure_outcome = LinearInstrumentMarginModel().evaluate_margin(failed_request)
    assert failure_outcome.failure is not None
    failure = failure_outcome.failure
    with pytest.raises(ValueError, match="subject_ids"):
        LinearInstrumentMarginFailure(
            failure.component_ref,
            failure.request,
            failure.request_hash,
            failure.code,
            ("forged",),
        )
    with pytest.raises(ValueError, match="GCD-reduced"):
        ExactLinearMarginAmount(QUOTE_CURRENCY, 2, 2)


def test_rule_book_identity_and_current_fallback_are_closed() -> None:
    rule_book = _rule_book()
    assert rule_book.config_hash.startswith("sha256:")
    assert rule_book.rule_book_hash.startswith("sha256:")
    with pytest.raises(ValueError, match="config_hash"):
        LinearMarginRuleBook(
            rule_book.rule_book_key,
            rule_book.rule_book_version,
            rule_book.instrument_id,
            rule_book.settlement_currency_id,
            rule_book.tier_scale,
            rule_book.intervals,
            "sha256:" + "0" * 64,
        )

    request = _request()
    later_current_only = _rule_book(
        (
            _interval(
                interval_id="later-current-only",
                effective_from=UtcInstant(11),
            ),
        )
    )
    outcome = LinearInstrumentMarginModel().evaluate_margin(
        replace(request, rule_book=later_current_only)
    )
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is LinearInstrumentMarginFailureCode.MISSING_HISTORICAL_RULE
    )
