from __future__ import annotations

from crypto_quant_backtest import (
    DeterministicBpsSlippageModel,
    ExecutionReferencePrice,
    SlippageApplicabilityEnvelope,
    SlippageCalibrationRef,
    SlippageLimitation,
    SlippageMarketState,
    SlippageModelKind,
    SlippageRequest,
    SimulationComponentRef,
    SimulationPortType,
)
from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    OrderSide,
    Price,
    PricePurpose,
    Quantity,
    RoundingPolicy,
    Scale,
    UtcInstant,
    VenueId,
)
from crypto_quant_trading import ResolvedMark


VENUE = VenueId("synthetic")
BTC = InstrumentId(VENUE, "cash:btc-usd")
USD = CurrencyId("USD")


def resolved_mark(*, price_units: int = 10_000) -> ResolvedMark:
    return ResolvedMark(
        instrument_id=BTC,
        quote_currency_id=USD,
        price_purpose=PricePurpose.EXECUTION_REFERENCE,
        price=Price(price_units, Scale(2), str(BTC), str(USD)),
        observed_at=UtcInstant(90),
        available_at=UtcInstant(95),
        resolved_at=UtcInstant(100),
        age_nanoseconds=10,
        stream_id="bars.open",
        source_event_id="bar-1",
        revision_id="rev-1",
        stale_policy_key="execution.no_forward_fill.v1",
        stale_policy_version=1,
        stale_policy_hash="sha256:" + "11" * 32,
    )


def component_ref(
    kind: SlippageModelKind = SlippageModelKind.DETERMINISTIC_BPS_V1,
) -> SimulationComponentRef:
    digest_byte = "22" if kind is SlippageModelKind.DETERMINISTIC_BPS_V1 else "33"
    return SimulationComponentRef(
        port_type=SimulationPortType.SLIPPAGE_MODEL,
        component_key=kind.value,
        component_version=1,
        component_digest="sha256:" + digest_byte * 32,
    )


def calibration_ref() -> SlippageCalibrationRef:
    return SlippageCalibrationRef(
        calibration_key="synthetic.bps.calibration.v1",
        calibration_version=1,
        calibration_digest="sha256:" + "44" * 32,
    )


def envelope() -> SlippageApplicabilityEnvelope:
    return SlippageApplicabilityEnvelope.create(
        envelope_key="synthetic.cash.bps-envelope.v1",
        envelope_version=1,
        instrument_id=BTC,
        valid_from=UtcInstant(50),
        valid_to_exclusive=UtcInstant(150),
        maximum_quantity=Quantity(10_000, Scale(3), str(BTC)),
        allowed_market_state_keys=("normal", "opening_auction"),
    )


def market_state(*, state_key: str = "normal", available_at: int = 99) -> SlippageMarketState:
    return SlippageMarketState(
        state_key=state_key,
        observed_at=UtcInstant(98),
        available_at=UtcInstant(available_at),
        source_event_id="market-state-1",
        revision_id="rev-1",
        evidence_hash="sha256:" + "55" * 32,
    )


def request(
    side: OrderSide = OrderSide.BUY,
    *,
    quantity_units: int = 2_000,
    state_key: str = "normal",
    price_units: int = 10_000,
) -> SlippageRequest:
    return SlippageRequest(
        reference_price=ExecutionReferencePrice(resolved_mark(price_units=price_units)),
        side=side,
        quantity=Quantity(quantity_units, Scale(3), str(BTC)),
        market_state=market_state(state_key=state_key),
    )


def model(
    *,
    basis_points_units: int = 25,
    basis_points_scale: Scale = Scale(0),
    rounding: RoundingPolicy = RoundingPolicy.HALF_UP,
) -> DeterministicBpsSlippageModel:
    return DeterministicBpsSlippageModel(
        component_ref=component_ref(),
        calibration_ref=calibration_ref(),
        applicability_envelope=envelope(),
        basis_points_units=basis_points_units,
        basis_points_scale=basis_points_scale,
        rounding=rounding,
        limitations=(),
    )


def zero_model() -> DeterministicBpsSlippageModel:
    return DeterministicBpsSlippageModel(
        component_ref=component_ref(SlippageModelKind.ZERO_SLIPPAGE_DEVELOPMENT_V1),
        calibration_ref=calibration_ref(),
        applicability_envelope=envelope(),
        basis_points_units=0,
        basis_points_scale=Scale(0),
        rounding=RoundingPolicy.TOWARD_ZERO,
        limitations=(SlippageLimitation.ZERO_SLIPPAGE_DEVELOPMENT_ONLY,),
    )
