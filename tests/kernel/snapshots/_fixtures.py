from __future__ import annotations

from crypto_quant_domain import (
    CashBalance,
    CashBalanceKey,
    CurrencyId,
    InstrumentId,
    Money,
    PositionBalance,
    PositionBalanceKey,
    Price,
    PricePurpose,
    QuantizationPolicy,
    Quantity,
    RoundingPolicy,
    Scale,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal,
    CurrencyValuationEdge,
    CurrencyValuationGraph,
    LedgerBalanceRegistration,
    LedgerSchema,
    LedgerState,
    PortfolioValueKind,
    PortfolioValueRef,
    ReportingCurrencyValuation,
    ResolvedMark,
)


VENUE = VenueId("synthetic")
ACCOUNT = "account:primary"
USD = CurrencyId("USD")
EUR = CurrencyId("EUR")
STOCK = InstrumentId(VENUE, "stock-eur-1")
FX = InstrumentId(VENUE, "eur-usd")
USD_KEY = CashBalanceKey(ACCOUNT, VENUE, USD)
EUR_KEY = CashBalanceKey(ACCOUNT, VENUE, EUR)
STOCK_KEY = PositionBalanceKey(ACCOUNT, VENUE, STOCK)
MONEY_SCALE = Scale(2)
QUANTITY_SCALE = Scale(0)
VALUATION_AT = UtcInstant(100)
ROUNDING = QuantizationPolicy(
    version="position-notional.half-even.v1",
    target_scale=MONEY_SCALE,
    rounding=RoundingPolicy.HALF_EVEN,
)


def resolved_mark(
    instrument: InstrumentId,
    quote: CurrencyId,
    units: int,
    *,
    observed_at: int = 90,
) -> ResolvedMark:
    policy_hash = canonical_sha256(
        {
            "policy_key": "marks.valuation.v1",
            "policy_version": 1,
            "max_age_nanoseconds": 20,
        }
    )
    return ResolvedMark(
        instrument_id=instrument,
        quote_currency_id=quote,
        price_purpose=PricePurpose.VALUATION,
        price=Price(units, MONEY_SCALE, str(instrument), str(quote)),
        observed_at=UtcInstant(observed_at),
        available_at=UtcInstant(95),
        resolved_at=VALUATION_AT,
        age_nanoseconds=100 - observed_at,
        stream_id=f"stream:{instrument.stable_key}:valuation",
        source_event_id=f"event:{instrument.stable_key}:90",
        revision_id="revision:1",
        stale_policy_key="marks.valuation.v1",
        stale_policy_version=1,
        stale_policy_hash=policy_hash,
    )


def ledger_state(*, second_account: bool = False) -> LedgerState:
    usd_key = USD_KEY
    if second_account:
        usd_key = CashBalanceKey("account:secondary", VENUE, USD)
    schema = LedgerSchema(
        (
            LedgerBalanceRegistration(usd_key, MONEY_SCALE),
            LedgerBalanceRegistration(EUR_KEY, MONEY_SCALE),
            LedgerBalanceRegistration(STOCK_KEY, QUANTITY_SCALE),
        )
    )
    return LedgerState(
        schema=schema,
        cursor=AccountingJournal.empty().cursor_at(0),
        cash_balances=tuple(
            sorted(
                (
                    CashBalance(usd_key, Money(100_000, MONEY_SCALE, "USD")),
                    CashBalance(EUR_KEY, Money(20_000, MONEY_SCALE, "EUR")),
                ),
                key=lambda value: canonical_bytes(value.key),
            )
        ),
        position_balances=(
            PositionBalance(
                STOCK_KEY,
                Quantity(3, QUANTITY_SCALE, str(STOCK)),
                (),
            ),
        ),
        realized_pnl=(CashBalance(EUR_KEY, Money(1_000, MONEY_SCALE, "EUR")),),
        fees=(CashBalance(EUR_KEY, Money(200, MONEY_SCALE, "EUR")),),
        financing=(CashBalance(usd_key, Money(-100, MONEY_SCALE, "USD")),),
    )


def snapshot_inputs(*, reverse: bool = False) -> dict[str, object]:
    state = ledger_state()
    stock_mark = resolved_mark(STOCK, EUR, 5_000)
    fx_mark = resolved_mark(FX, USD, 110)
    graph = CurrencyValuationGraph(
        valuation_at=VALUATION_AT,
        price_purpose=PricePurpose.VALUATION,
        edges=(CurrencyValuationEdge(EUR, fx_mark),),
    )
    eur_resolution = graph.resolve(EUR, USD).resolution
    usd_resolution = graph.resolve(USD, USD).resolution
    assert eur_resolution is not None
    assert usd_resolution is not None

    valuations = (
        ReportingCurrencyValuation(
            PortfolioValueRef(PortfolioValueKind.CASH, USD_KEY),
            Money(100_000, MONEY_SCALE, "USD"),
            Money(100_000, MONEY_SCALE, "USD"),
            usd_resolution,
            graph.graph_hash,
        ),
        ReportingCurrencyValuation(
            PortfolioValueRef(PortfolioValueKind.CASH, EUR_KEY),
            Money(20_000, MONEY_SCALE, "EUR"),
            Money(22_000, MONEY_SCALE, "USD"),
            eur_resolution,
            graph.graph_hash,
        ),
        ReportingCurrencyValuation(
            PortfolioValueRef(PortfolioValueKind.POSITION_MARKET_VALUE, STOCK_KEY),
            Money(15_000, MONEY_SCALE, "EUR"),
            Money(16_500, MONEY_SCALE, "USD"),
            eur_resolution,
            graph.graph_hash,
            ROUNDING,
        ),
        ReportingCurrencyValuation(
            PortfolioValueRef(PortfolioValueKind.UNREALIZED_PNL, STOCK_KEY),
            Money(3_000, MONEY_SCALE, "EUR"),
            Money(3_300, MONEY_SCALE, "USD"),
            eur_resolution,
            graph.graph_hash,
        ),
        ReportingCurrencyValuation(
            PortfolioValueRef(PortfolioValueKind.REALIZED_PNL, EUR_KEY),
            Money(1_000, MONEY_SCALE, "EUR"),
            Money(1_100, MONEY_SCALE, "USD"),
            eur_resolution,
            graph.graph_hash,
        ),
        ReportingCurrencyValuation(
            PortfolioValueRef(PortfolioValueKind.FEES, EUR_KEY),
            Money(200, MONEY_SCALE, "EUR"),
            Money(220, MONEY_SCALE, "USD"),
            eur_resolution,
            graph.graph_hash,
        ),
        ReportingCurrencyValuation(
            PortfolioValueRef(PortfolioValueKind.FINANCING, USD_KEY),
            Money(-100, MONEY_SCALE, "USD"),
            Money(-100, MONEY_SCALE, "USD"),
            usd_resolution,
            graph.graph_hash,
        ),
    )
    marks = (stock_mark, fx_mark)
    return {
        "ledger_state": state,
        "resolved_marks": tuple(reversed(marks)) if reverse else marks,
        "valuations": tuple(reversed(valuations)) if reverse else valuations,
        "reporting_currency": USD,
        "reporting_scale": MONEY_SCALE,
        "timestamp": VALUATION_AT,
        "currency_valuation_graph_hash": graph.graph_hash,
    }
