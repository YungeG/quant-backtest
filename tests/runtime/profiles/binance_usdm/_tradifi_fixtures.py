from __future__ import annotations

from crypto_quant_backtest import (
    BinanceUsdmAccountCapacityEvidence,
    BinanceUsdmTradifiProfileCompositionRequest,
    DeterministicBpsSlippageModel,
    SimulationComponentRef,
    SimulationPortType,
    SlippageApplicabilityEnvelope,
    SlippageCalibrationRef,
    SlippageModelKind,
    TimelineWindow,
)
from crypto_quant_domain import (
    ArtifactRef,
    CurrencyId,
    PricePurpose,
    Quantity,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import (
    FundingSlotId,
    LinearPerpetualContract,
    StaleMarkPolicy,
)
from crypto_quant_trading.funding_accounting import LinearFundingApplicationKey
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmAccountProfileModel,
    BinanceUsdmAccountProfileQuery,
    BinanceUsdmFundingSourceModel,
    BinanceUsdmFundingSourceQuery,
    BinanceUsdmHistoricalAccountProfileBook,
    BinanceUsdmHistoricalFundingBook,
    BinanceUsdmHistoricalPriceBook,
    BinanceUsdmInstrumentMetadataQuery,
    BinanceUsdmInstrumentModel,
    BinanceUsdmMarginTierModel,
    BinanceUsdmMarginTierQuery,
    BinanceUsdmMarginTierRuleBook,
    BinanceUsdmOrderRuleBook,
    BinanceUsdmOrderRuleModel,
    BinanceUsdmOrderRuleQuery,
    BinanceUsdmPricePurposeQuery,
    BinanceUsdmPriceStreamModel,
    BinanceUsdmTradifiInstrumentMetadataModel,
)

from tests.profiles.binance_usdm._account_profile_fixtures import account_band
from tests.profiles.binance_usdm._fixtures import revision
from tests.profiles.binance_usdm._funding_source_fixtures import (
    funding_coverage,
    funding_record,
)
from tests.profiles.binance_usdm._margin_tier_fixtures import band as margin_band
from tests.profiles.binance_usdm._order_rule_fixtures import SESSION_ID
from tests.profiles.binance_usdm._order_rule_fixtures import band as order_band
from tests.profiles.binance_usdm._price_stream_fixtures import (
    aggregate_trade,
    coverage,
    mark_bar,
)

HOUR = 3_600_000_000_000
MILLISECOND = 1_000_000
START = UtcInstant(1_784_160_000_000_000_000)
END = UtcInstant(START.epoch_nanoseconds + 2 * HOUR)
ONBOARD = UtcInstant(START.epoch_nanoseconds - 10 * HOUR)
BAND_END = UtcInstant(END.epoch_nanoseconds + 10 * HOUR)
COMPOSED_AT = SimulationInstant(
    UtcInstant(END.epoch_nanoseconds + HOUR),
    TimelinePhase(200, "tradifi_profile_composition"),
    SourceSequence(0),
)
STABLE_KEY = "koru-usdt-tradifi-perpetual"


def _sim(instant: UtcInstant, phase: int = 0) -> SimulationInstant:
    return SimulationInstant(instant, TimelinePhase(phase, "tradifi_fixture"), SourceSequence(0))


def _metadata_query(contract_type: str) -> BinanceUsdmInstrumentMetadataQuery:
    return BinanceUsdmInstrumentMetadataQuery(
        stable_instrument_key=STABLE_KEY,
        effective_at=START,
        captured_at=COMPOSED_AT.instant,
        revisions=(
            revision(
                "koru-v1",
                stable_instrument_key=STABLE_KEY,
                symbol="KORUUSDT",
                pair="KORUUSDT",
                contract_type=contract_type,
                onboard_at=ONBOARD,
                effective_from=ONBOARD,
                available_at=UtcInstant(ONBOARD.epoch_nanoseconds + 1),
                base_asset="KORU",
            ),
        ),
    )


def _instrument_authorities():
    ordinary = BinanceUsdmInstrumentModel().resolve_instrument(_metadata_query("PERPETUAL"))
    tradifi = BinanceUsdmTradifiInstrumentMetadataModel().resolve_instrument(
        _metadata_query("TRADIFI_PERPETUAL")
    )
    assert ordinary.result is not None
    assert tradifi.result is not None
    return ordinary.result, tradifi.result


def _order_rules(ordinary):
    instrument_id = ordinary.instrument.instrument_id
    active = order_band(
        "koru-rules-v1",
        effective_from=ONBOARD,
        effective_to_exclusive=BAND_END,
        available_at=UtcInstant(ONBOARD.epoch_nanoseconds + 2),
        tick_size="0.01",
        deferred_rule_keys=("MAX_NUM_ORDERS", "MAX_NUM_ALGO_ORDERS"),
        instrument_id=instrument_id,
    )
    book = BinanceUsdmOrderRuleBook(
        "binance-usdm-koru-order-rules-v1",
        1,
        instrument_id,
        ONBOARD,
        BAND_END,
        (active,),
    )
    outcome = BinanceUsdmOrderRuleModel().resolve_order_rules(
        BinanceUsdmOrderRuleQuery(ordinary, SESSION_ID, START, COMPOSED_AT.instant, book)
    )
    assert outcome.result is not None
    return outcome.result


def _margin_tiers(ordinary):
    instrument_id = ordinary.instrument.instrument_id
    active = margin_band(
        "koru-margin-v1",
        effective_from=ONBOARD,
        effective_to_exclusive=BAND_END,
        available_at=_sim(UtcInstant(ONBOARD.epoch_nanoseconds + 2), 60),
        instrument_id=instrument_id,
    )
    settlement = ordinary.instrument.settlement_currency
    assert settlement is not None
    book = BinanceUsdmMarginTierRuleBook(
        "binance-usdm-koru-margin-v1",
        1,
        instrument_id,
        settlement,
        ONBOARD,
        BAND_END,
        (active,),
    )
    outcome = BinanceUsdmMarginTierModel().resolve_margin_tiers(
        BinanceUsdmMarginTierQuery(ordinary, START, COMPOSED_AT, book)
    )
    assert outcome.result is not None
    return outcome.result


def _price_book(ordinary) -> BinanceUsdmHistoricalPriceBook:
    instrument_id = ordinary.instrument.instrument_id
    start_ms = START.epoch_nanoseconds // MILLISECOND
    end_ms = END.epoch_nanoseconds // MILLISECOND
    bars = (
        mark_bar(
            "koru-mark-0",
            open_time_ms=start_ms - 3_600_000,
            close_time_ms=start_ms - 1,
            open_price="10.00",
            high_price="10.10",
            low_price="9.90",
            close_price="10.00",
            instrument_id=instrument_id,
        ),
        mark_bar(
            "koru-mark-1",
            open_time_ms=start_ms,
            close_time_ms=start_ms + 3_600_000 - 1,
            open_price="10.00",
            high_price="10.20",
            low_price="9.80",
            close_price="10.10",
            instrument_id=instrument_id,
        ),
        mark_bar(
            "koru-mark-2",
            open_time_ms=start_ms + 3_600_000,
            close_time_ms=end_ms - 1,
            open_price="10.10",
            high_price="10.30",
            low_price="10.00",
            close_price="10.20",
            instrument_id=instrument_id,
        ),
    )
    coverages = tuple(
        coverage(
            purpose,
            coverage_from=(
                START
                if purpose is PricePurpose.LIQUIDATION
                else UtcInstant(START.epoch_nanoseconds - HOUR)
            ),
            coverage_to_exclusive=END,
        )
        for purpose in (
            PricePurpose.EXECUTION_REFERENCE,
            PricePurpose.VALUATION,
            PricePurpose.MARGIN,
            PricePurpose.LIQUIDATION,
        )
    )
    coverages = tuple(
        type(value)(
            value.coverage_id,
            instrument_id,
            value.price_purpose,
            value.source_kind,
            value.coverage_from,
            value.coverage_to_exclusive,
            value.stream_id,
            value.source_ref,
        )
        for value in coverages
    )
    trade = aggregate_trade(
        "koru-agg-1",
        aggregate_trade_id=1,
        price="10.00",
        trade_at=START,
        available_at=_sim(START),
        instrument_id=instrument_id,
    )
    return BinanceUsdmHistoricalPriceBook(
        "binance-usdm-koru-price-book-v1",
        1,
        instrument_id,
        CurrencyId("USDT"),
        coverages,
        (trade,),
        bars,
    )


def _prices(ordinary):
    book = _price_book(ordinary)
    values = []
    for purpose in (
        PricePurpose.EXECUTION_REFERENCE,
        PricePurpose.VALUATION,
        PricePurpose.MARGIN,
        PricePurpose.LIQUIDATION,
    ):
        query = BinanceUsdmPricePurposeQuery(
            ordinary,
            book,
            purpose,
            START,
            COMPOSED_AT,
            None
            if purpose is PricePurpose.LIQUIDATION
            else StaleMarkPolicy(
                f"koru-{purpose.value}-v1",
                1,
                purpose,
                HOUR,
                True,
            ),
            START if purpose is PricePurpose.LIQUIDATION else None,
            END if purpose is PricePurpose.LIQUIDATION else None,
        )
        outcome = BinanceUsdmPriceStreamModel().resolve_price_purpose(query)
        assert outcome.result is not None, outcome.failure
        values.append(outcome.result)
    return tuple(values)


def _funding(ordinary, order_rules):
    instrument_id = ordinary.instrument.instrument_id
    contract = LinearPerpetualContract(
        ordinary.instrument,
        order_rules.quantity_scale,
        order_rules.price_scale,
        ordinary.contract_metadata.contract_multiplier,
    )
    record = funding_record(
        funding_time_milliseconds=START.epoch_nanoseconds // MILLISECOND,
        mark_price="10.00",
        archive_available_at=_sim(UtcInstant(START.epoch_nanoseconds + 1)),
        event_id="funding:KORUUSDT:regular",
        instrument_id=instrument_id,
    )
    funding_span = funding_coverage(
        coverage_from=UtcInstant(START.epoch_nanoseconds - 1),
        coverage_to_exclusive=END,
        instrument_id=instrument_id,
    )
    book = BinanceUsdmHistoricalFundingBook(
        "binance-usdm-koru-funding-v1",
        1,
        instrument_id,
        (funding_span,),
        (record,),
    )
    key = LinearFundingApplicationKey.derive(
        "account-1", FundingSlotId.derive(instrument_id, START)
    )
    outcome = BinanceUsdmFundingSourceModel().resolve_funding_source(
        BinanceUsdmFundingSourceQuery(
            ordinary,
            contract,
            key,
            book,
            START,
            COMPOSED_AT,
        )
    )
    assert outcome.result is not None, outcome.failure
    return (outcome.result,)


def _account(ordinary):
    instrument_id = ordinary.instrument.instrument_id
    active = account_band(
        band_id="koru-account-v1",
        effective_from=ONBOARD,
        effective_to_exclusive=BAND_END,
        available_at=_sim(UtcInstant(ONBOARD.epoch_nanoseconds + 2)),
        leverage="1",
        instrument_id=instrument_id,
    )
    book = BinanceUsdmHistoricalAccountProfileBook(
        "binance-usdm-koru-account-v1",
        1,
        "account-1",
        instrument_id,
        ONBOARD,
        BAND_END,
        (active,),
    )
    outcome = BinanceUsdmAccountProfileModel().resolve_account_profile(
        BinanceUsdmAccountProfileQuery(
            ordinary,
            "account-1",
            book,
            START,
            COMPOSED_AT,
            CurrencyId("USDT"),
        )
    )
    assert outcome.result is not None, outcome.failure
    return outcome.result


def _capacity(order_rules, account) -> BinanceUsdmAccountCapacityEvidence:
    source = order_rules.active_band.source_ref
    return BinanceUsdmAccountCapacityEvidence(
        "binance-usdm-koru-capacity-v1",
        1,
        account.account_id,
        order_rules.active_band.instrument_id,
        ONBOARD,
        BAND_END,
        _sim(UtcInstant(ONBOARD.epoch_nanoseconds + 2)),
        200,
        10,
        source.source_key,
        source.source_hash,
        "koru-capacity-v1",
    )


def _slippage(instrument_id) -> DeterministicBpsSlippageModel:
    envelope = SlippageApplicabilityEnvelope.create(
        envelope_key="koruusdt-first-retained-trade-v1",
        envelope_version=1,
        instrument_id=instrument_id,
        valid_from=START,
        valid_to_exclusive=END,
        maximum_quantity=Quantity(1_000_000, Scale(3), str(instrument_id)),
        allowed_market_state_keys=("normal",),
    )
    return DeterministicBpsSlippageModel(
        SimulationComponentRef(
            SimulationPortType.SLIPPAGE_MODEL,
            SlippageModelKind.DETERMINISTIC_BPS_V1.value,
            1,
            canonical_sha256(
                {
                    "calibration": "koruusdt-first-retained-trade-v1",
                    "basis_points": 5,
                    "envelope": envelope.envelope_hash,
                }
            ),
        ),
        SlippageCalibrationRef(
            "koruusdt-first-retained-trade-v1",
            1,
            canonical_sha256({"basis_points": 5}),
        ),
        envelope,
        5,
        Scale(0),
        RoundingPolicy.HALF_UP,
        (),
    )


def composition_request(**overrides) -> BinanceUsdmTradifiProfileCompositionRequest:
    ordinary, tradifi = _instrument_authorities()
    order = _order_rules(ordinary)
    margin = _margin_tiers(ordinary)
    prices = _prices(ordinary)
    funding = _funding(ordinary, order)
    account = _account(ordinary)
    values = {
        "instrument_metadata": tradifi,
        "order_rules": order,
        "margin_tiers": margin,
        "price_purposes": prices,
        "funding_sources": funding,
        "account_profile": account,
        "account_capacity": _capacity(order, account),
        "timeline_window": TimelineWindow(START, START, END),
        "composed_at": COMPOSED_AT,
        "calendar_refs": (
            ArtifactRef("xkrx_regular_session_calendar", 1, "sha256:" + "11" * 32),
            ArtifactRef("arcx_koru_core_session_calendar", 1, "sha256:" + "22" * 32),
        ),
        "post_adjustment_unit_regime_ref": ArtifactRef(
            "binance_usdm_tradifi_post_adjustment_unit_regime",
            1,
            "sha256:" + "33" * 32,
        ),
        "slippage_model": _slippage(tradifi.instrument.instrument_id),
        "admitted_maximum_quantity": Quantity(
            1_000_000,
            Scale(3),
            str(tradifi.instrument.instrument_id),
        ),
        "required_market_state_keys": ("normal",),
    }
    values.update(overrides)
    return BinanceUsdmTradifiProfileCompositionRequest(**values)
