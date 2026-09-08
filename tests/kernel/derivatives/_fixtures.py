from __future__ import annotations

from crypto_quant_domain import (
    CurrencyId,
    DomainId,
    DomainIdKind,
    Fill,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    Money,
    OrderSide,
    PositionBalanceKey,
    Price,
    PricePurpose,
    Quantity,
    Rate,
    Scale,
    UtcInstant,
    VenueId,
)
from crypto_quant_trading import (
    LinearPerpetualContract,
    LinearPositionProjectionRequest,
)

ACCOUNT_ID = "synthetic-linear-account"
VENUE_ID = VenueId("synthetic-perpetual")
INSTRUMENT_ID = InstrumentId(VENUE_ID, "btc-usdt-linear-perpetual")
BASE_CURRENCY = CurrencyId("BTC")
QUOTE_CURRENCY = CurrencyId("USDT")
QUANTITY_SCALE = Scale(3)
PRICE_SCALE = Scale(2)


def domain_id(kind: DomainIdKind, digit: str) -> DomainId:
    return DomainId(kind, f"{kind.prefix}_{digit * 64}")


def instrument() -> InstrumentDefinition:
    return InstrumentDefinition(
        instrument_id=INSTRUMENT_ID,
        instrument_type=InstrumentType.LINEAR_PERPETUAL,
        base_currency=BASE_CURRENCY,
        quote_currency=QUOTE_CURRENCY,
        settlement_currency=QUOTE_CURRENCY,
    )


def contract() -> LinearPerpetualContract:
    return LinearPerpetualContract(
        instrument=instrument(),
        quantity_scale=QUANTITY_SCALE,
        price_scale=PRICE_SCALE,
        contract_multiplier=Rate(
            125,
            Scale(3),
            "base_quantity_per_contract",
        ),
    )


def position_key() -> PositionBalanceKey:
    return PositionBalanceKey(ACCOUNT_ID, VENUE_ID, INSTRUMENT_ID)


def fill(
    digit: str,
    *,
    side: OrderSide,
    quantity_units: int,
    price_units: int,
    execution_nanoseconds: int,
) -> Fill:
    price = Price(
        price_units,
        PRICE_SCALE,
        str(INSTRUMENT_ID),
        str(QUOTE_CURRENCY),
    )
    return Fill(
        fill_id=domain_id(DomainIdKind.FILL, digit),
        order_id=domain_id(DomainIdKind.ORDER, digit),
        account_id=ACCOUNT_ID,
        venue_id=VENUE_ID,
        instrument_id=INSTRUMENT_ID,
        side=side,
        quantity=Quantity(quantity_units, QUANTITY_SCALE, str(INSTRUMENT_ID)),
        reference_price=price,
        reference_price_purpose=PricePurpose.EXECUTION_REFERENCE,
        price=price,
        slippage_amount=Money(0, PRICE_SCALE, str(QUOTE_CURRENCY)),
        slippage_decision_id=f"slippage-{digit}",
        slippage_model_key="synthetic.zero-slippage.v1",
        slippage_calibration_id=None,
        liquidity="taker",
        execution_time=UtcInstant(execution_nanoseconds),
    )


def request(*fills: Fill) -> LinearPositionProjectionRequest:
    return LinearPositionProjectionRequest(position_key(), contract(), tuple(fills))
