from __future__ import annotations

from crypto_quant_backtest import (
    BinanceUsdmAccountCapacityEvidence,
    BinanceUsdmProfileCompositionRequest,
    TimelineWindow,
)
from crypto_quant_domain import PricePurpose, Scale, SimulationInstant, SourceSequence, TimelinePhase, UtcInstant
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmAccountProfileModel,
    BinanceUsdmFundingSourceModel,
    BinanceUsdmInstrumentModel,
    BinanceUsdmMarginTierModel,
    BinanceUsdmOrderRuleModel,
    BinanceUsdmPriceStreamModel,
)
from tests.profiles.binance_usdm._account_profile_fixtures import account_query
from tests.profiles.binance_usdm._fixtures import RENAME_AT
from tests.profiles.binance_usdm._funding_source_fixtures import (
    application_key,
    funding_book,
    funding_query,
    funding_record,
    linear_contract,
)
from tests.profiles.binance_usdm._margin_tier_fixtures import (
    complete_bands as margin_bands,
    margin_tier_query,
)
from tests.profiles.binance_usdm._order_rule_fixtures import (
    complete_bands as order_bands,
    order_rule_query,
)
from tests.profiles.binance_usdm._price_stream_fixtures import BAR_START, price_query


WINDOW_END = UtcInstant(RENAME_AT.epoch_nanoseconds + 100)
COMPOSED_AT = SimulationInstant(
    UtcInstant(RENAME_AT.epoch_nanoseconds + 30_000_000),
    TimelinePhase(200, "profile_composition"),
    SourceSequence(0),
)


def successful_authorities():
    instrument = price_query(PricePurpose.VALUATION).instrument_metadata

    order_outcome = BinanceUsdmOrderRuleModel().resolve_order_rules(
        order_rule_query(
            *order_bands(
                second_deferred=("MAX_NUM_ORDERS", "MAX_NUM_ALGO_ORDERS")
            )
        )
    )
    assert order_outcome.result is not None

    margin_outcome = BinanceUsdmMarginTierModel().resolve_margin_tiers(
        margin_tier_query(*margin_bands())
    )
    assert margin_outcome.result is not None

    prices = []
    for purpose in (
        PricePurpose.EXECUTION_REFERENCE,
        PricePurpose.VALUATION,
        PricePurpose.MARGIN,
        PricePurpose.LIQUIDATION,
    ):
        outcome = BinanceUsdmPriceStreamModel().resolve_price_purpose(
            price_query(
                purpose,
                liquidation_interval_start=(
                    BAR_START
                    if purpose is PricePurpose.LIQUIDATION
                    else None
                ),
                liquidation_interval_end_exclusive=(
                    RENAME_AT
                    if purpose is PricePurpose.LIQUIDATION
                    else None
                ),
            )
        )
        assert outcome.result is not None
        prices.append(outcome.result)

    contract = linear_contract(price_scale=order_outcome.result.price_scale)
    funding_outcome = BinanceUsdmFundingSourceModel().resolve_funding_source(
        funding_query(
            book=funding_book(
                records=(
                    funding_record(mark_price="50000.10"),
                )
            ),
            contract=contract,
            key=application_key(),
        )
    )
    assert funding_outcome.result is not None

    account_outcome = BinanceUsdmAccountProfileModel().resolve_account_profile(
        account_query()
    )
    assert account_outcome.result is not None

    return (
        instrument,
        order_outcome.result,
        margin_outcome.result,
        tuple(prices),
        (funding_outcome.result,),
        account_outcome.result,
    )


def capacity_evidence(order_rules=None) -> BinanceUsdmAccountCapacityEvidence:
    if order_rules is None:
        _, order_rules, _, _, _, account = successful_authorities()
    else:
        account = successful_authorities()[-1]
    source = order_rules.active_band.source_ref
    return BinanceUsdmAccountCapacityEvidence(
        evidence_key="binance-usdm-order-capacity-v1",
        evidence_version=1,
        account_id=account.account_id,
        instrument_id=order_rules.active_band.instrument_id,
        effective_from=order_rules.active_band.effective_from,
        effective_to_exclusive=order_rules.active_band.effective_to_exclusive,
        available_at=SimulationInstant(
            order_rules.active_band.available_at,
            TimelinePhase(0, "capacity_source"),
            SourceSequence(0),
        ),
        max_num_orders=200,
        max_num_algo_orders=10,
        source_key=source.source_key,
        source_hash=source.source_hash,
        revision_id="exchange-info-capacity-v1",
    )


def composition_request(**overrides) -> BinanceUsdmProfileCompositionRequest:
    instrument, order, margin, prices, funding, account = successful_authorities()
    values = {
        "instrument_metadata": instrument,
        "order_rules": order,
        "margin_tiers": margin,
        "price_purposes": prices,
        "funding_sources": funding,
        "account_profile": account,
        "account_capacity": capacity_evidence(order),
        "timeline_window": TimelineWindow(RENAME_AT, RENAME_AT, WINDOW_END),
        "composed_at": COMPOSED_AT,
    }
    values.update(overrides)
    return BinanceUsdmProfileCompositionRequest(**values)
