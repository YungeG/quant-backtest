from __future__ import annotations

from dataclasses import fields, replace

import pytest

from crypto_quant_backtest import (
    DeterministicBpsSlippageModel,
    ExecutionReferencePrice,
    SlippageApplicabilityDimension,
    SlippageApplicabilityEnvelope,
    SlippageApplicabilityViolation,
    SlippageDecision,
    SlippageLimitation,
    SlippageMarketState,
    SlippageModel,
    SlippageModelKind,
    SimulationPortType,
)
from crypto_quant_domain import (
    InstrumentId,
    OrderSide,
    PricePurpose,
    Quantity,
    RoundingPolicy,
    Scale,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from tests.runtime.slippage._fixtures import (
    BTC,
    calibration_ref,
    component_ref,
    envelope,
    market_state,
    model,
    request,
    resolved_mark,
    zero_model,
)


def test_buy_and_sell_apply_exact_signed_bps_without_changing_reference() -> None:
    slippage = model()

    buy = slippage.decide_slippage(request(OrderSide.BUY))
    sell = slippage.decide_slippage(request(OrderSide.SELL))

    assert isinstance(slippage, SlippageModel)
    assert slippage.spec().component_ref == slippage.component_ref
    assert slippage.spec().applicability == envelope()
    assert buy.failure is None and isinstance(buy.result, SlippageDecision)
    assert sell.failure is None and isinstance(sell.result, SlippageDecision)
    assert buy.result.reference_price.mark.price.units == 10_000
    assert buy.result.slippage_amount.units == 25
    assert buy.result.execution_price.units == 10_025
    assert sell.result.slippage_amount.units == -25
    assert sell.result.execution_price.units == 9_975
    assert buy.result.execution_price.scale == buy.result.reference_price.mark.price.scale
    assert buy.result.applicability.applicable is True
    assert buy.result.component_ref.port_type is SimulationPortType.SLIPPAGE_MODEL


def test_bps_scale_and_rounding_are_explicit_integer_arithmetic() -> None:
    half_up = model(
        basis_points_units=125,
        basis_points_scale=Scale(1),
        rounding=RoundingPolicy.HALF_UP,
    ).decide_slippage(request(price_units=10_003))
    toward_zero = model(
        basis_points_units=125,
        basis_points_scale=Scale(1),
        rounding=RoundingPolicy.TOWARD_ZERO,
    ).decide_slippage(request(price_units=10_003))

    assert half_up.result is not None and toward_zero.result is not None
    assert half_up.result.slippage_amount.units == 13
    assert toward_zero.result.slippage_amount.units == 12
    assert half_up.result.basis_points_units == 125
    assert half_up.result.basis_points_scale == Scale(1)
    assert half_up.result.rounding is RoundingPolicy.HALF_UP


def test_out_of_envelope_returns_structured_violation() -> None:
    other = InstrumentId(VenueId("synthetic"), "cash:eth-usd")
    wrong_envelope = SlippageApplicabilityEnvelope.create(
        envelope_key="synthetic.cash.bps-envelope.v1",
        envelope_version=1,
        instrument_id=other,
        valid_from=UtcInstant(101),
        valid_to_exclusive=UtcInstant(150),
        maximum_quantity=Quantity(1_000, Scale(3), str(other)),
        allowed_market_state_keys=("auction_only",),
    )
    slippage = replace(model(), applicability_envelope=wrong_envelope)

    outcome = slippage.decide_slippage(
        request(quantity_units=2_000, state_key="normal")
    )

    assert outcome.result is None
    assert isinstance(outcome.failure, SlippageApplicabilityViolation)
    assert outcome.failure.failed_dimensions == (
        SlippageApplicabilityDimension.INSTRUMENT,
        SlippageApplicabilityDimension.TIME_WINDOW,
        SlippageApplicabilityDimension.QUANTITY,
        SlippageApplicabilityDimension.MARKET_STATE,
    )
    assert outcome.failure.request_hash == canonical_sha256(outcome.failure.request)
    assert outcome.failure.envelope_hash == wrong_envelope.envelope_hash


def test_decision_recomputes_amount_and_nonpositive_execution_fails_structured() -> None:
    decision = model().decide_slippage(request()).result
    assert decision is not None
    with pytest.raises(ValueError, match="configured BPS"):
        replace(
            decision,
            slippage_amount=replace(decision.slippage_amount, units=99),
            execution_price=replace(decision.execution_price, units=10_099),
        )

    nonpositive = model(basis_points_units=9_999).decide_slippage(
        request(OrderSide.SELL, price_units=1)
    )
    assert nonpositive.result is None
    assert nonpositive.failure is not None
    assert nonpositive.failure.failed_dimensions == (
        SlippageApplicabilityDimension.EXECUTION_PRICE_POSITIVE,
    )


def test_request_rejects_future_market_state_and_identity_mismatch() -> None:
    with pytest.raises(ValueError, match="future market state"):
        replace(request(), market_state=market_state(available_at=101))

    wrong_quantity = Quantity(
        1_000,
        Scale(3),
        str(InstrumentId(VenueId("synthetic"), "cash:eth-usd")),
    )
    with pytest.raises(ValueError, match="instrument"):
        replace(request(), quantity=wrong_quantity)

    wrong_purpose = replace(
        resolved_mark(), price_purpose=PricePurpose.VALUATION
    )
    with pytest.raises(ValueError, match="execution_reference"):
        ExecutionReferencePrice(wrong_purpose)


def test_zero_slippage_requires_explicit_development_component_and_limitation() -> None:
    with pytest.raises(ValueError, match="nonzero BPS"):
        model(basis_points_units=0)

    zero = zero_model()
    outcome = zero.decide_slippage(request())
    assert outcome.result is not None
    assert outcome.result.execution_price == outcome.result.reference_price.mark.price
    assert outcome.result.slippage_amount.units == 0
    assert outcome.result.limitations == (
        SlippageLimitation.ZERO_SLIPPAGE_DEVELOPMENT_ONLY,
    )

    with pytest.raises(ValueError, match="development limitation"):
        DeterministicBpsSlippageModel(
            component_ref=component_ref(
                SlippageModelKind.ZERO_SLIPPAGE_DEVELOPMENT_V1
            ),
            calibration_ref=calibration_ref(),
            applicability_envelope=envelope(),
            basis_points_units=0,
            basis_points_scale=Scale(0),
            rounding=RoundingPolicy.TOWARD_ZERO,
            limitations=(),
        )


def test_config_and_evidence_values_fail_closed() -> None:
    with pytest.raises(ValueError, match="config_hash"):
        replace(envelope(), config_hash="sha256:" + "00" * 32)
    with pytest.raises(ValueError, match="positive"):
        replace(envelope(), maximum_quantity=Quantity(0, Scale(3), str(BTC)))
    with pytest.raises(ValueError, match="canonical"):
        SlippageMarketState(
            state_key="e\u0301",
            observed_at=UtcInstant(90),
            available_at=UtcInstant(95),
            source_event_id="state-1",
            revision_id="rev-1",
            evidence_hash="sha256:" + "55" * 32,
        )


def test_request_and_model_shapes_cannot_read_future_bar_fields() -> None:
    request_fields = {field.name for field in fields(type(request()))}
    state_fields = {field.name for field in fields(SlippageMarketState)}
    forbidden = {"high", "low", "close", "volume", "bar"}

    assert request_fields.isdisjoint(forbidden)
    assert state_fields.isdisjoint(forbidden)
