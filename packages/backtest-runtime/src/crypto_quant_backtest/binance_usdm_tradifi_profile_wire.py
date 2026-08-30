"""Exact offline wire decoder for the Binance USD-M TradFi profile request."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping

from crypto_quant_domain import (
    ArtifactRef,
    CurrencyId,
    InstrumentId,
    PricePurpose,
    Quantity,
    Rate,
    RoundingPolicy,
    Scale,
    SessionId,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    FundingSlotId,
    LinearFundingApplicationKey,
    LinearPerpetualContract,
    StaleMarkPolicy,
)
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmAccountProfileBand,
    BinanceUsdmAccountProfileModel,
    BinanceUsdmAccountProfileQuery,
    BinanceUsdmAccountProfileScope,
    BinanceUsdmAccountProfileSourceRef,
    BinanceUsdmAccountSourceKind,
    BinanceUsdmAggregateTradePrice,
    BinanceUsdmFundingCoverage,
    BinanceUsdmFundingRateRecord,
    BinanceUsdmFundingSourceModel,
    BinanceUsdmFundingSourceModelV2,
    BinanceUsdmFundingSourceQuery,
    BinanceUsdmFundingSourceRef,
    BinanceUsdmHistoricalAccountProfileBook,
    BinanceUsdmHistoricalFundingBook,
    BinanceUsdmHistoricalPriceBook,
    BinanceUsdmInstrumentMetadataQuery,
    BinanceUsdmInstrumentMetadataResolution,
    BinanceUsdmInstrumentMetadataRevision,
    BinanceUsdmInstrumentMetadataSourceRef,
    BinanceUsdmInstrumentModel,
    BinanceUsdmMarginTierBand,
    BinanceUsdmMarginTierBracket,
    BinanceUsdmMarginTierModel,
    BinanceUsdmMarginTierQuery,
    BinanceUsdmMarginTierRuleBook,
    BinanceUsdmMarginTierScope,
    BinanceUsdmMarginTierSourceRef,
    BinanceUsdmMarkPriceKline,
    BinanceUsdmOrderAdmissionMode,
    BinanceUsdmOrderRuleBand,
    BinanceUsdmOrderRuleBook,
    BinanceUsdmOrderRuleModel,
    BinanceUsdmOrderRuleQuery,
    BinanceUsdmOrderRuleSourceRef,
    BinanceUsdmPricePurposeQuery,
    BinanceUsdmPriceSourceKind,
    BinanceUsdmPriceSourceRef,
    BinanceUsdmPriceStreamCoverage,
    BinanceUsdmPriceStreamModel,
    BinanceUsdmTradifiInstrumentMetadataModel,
    BinanceUsdmTradifiInstrumentMetadataResolution,
)

from .binance_usdm_profile import BinanceUsdmAccountCapacityEvidence
from .binance_usdm_tradifi_profile import BinanceUsdmTradifiProfileCompositionRequest
from .ports import SimulationComponentRef, SimulationPortType
from .slippage import (
    DeterministicBpsSlippageModel,
    SlippageApplicabilityEnvelope,
    SlippageCalibrationRef,
    SlippageLimitation,
)
from .timeline import TimelineWindow

_ERROR = "invalid Binance USD-M TradFi profile composition wire"
_UNSUPPORTED_AUTHORITY = "unsupported Stage1 authority"
_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,18})?")
_SIGNED_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,18})?")


def _normalize(value: object) -> object:
    if value is None or type(value) in (bool, int, str):
        if type(value) is str and unicodedata.normalize("NFC", value) != value:
            raise ValueError
        return value
    if isinstance(value, Mapping):
        keys = list(value.keys())
        if any(type(key) is not str for key in keys) or len(keys) != len(set(keys)):
            raise ValueError
        return {key: _normalize(value[key]) for key in keys}
    if type(value) is list:
        return [_normalize(item) for item in value]
    raise ValueError


def _object(
    value: object,
    wire_type: str,
    fields: tuple[str, ...],
    *,
    schema: bool = True,
) -> dict[str, object]:
    if type(value) is not dict:
        raise ValueError
    expected = {"type", *fields}
    if schema:
        expected.add("schema_version")
    if set(value) != expected or value.get("type") != wire_type:
        raise ValueError
    if schema and value.get("schema_version") != 1:
        raise ValueError
    return value


def _array(value: object) -> list[object]:
    if type(value) is not list:
        raise ValueError
    return value


def _text(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError
    return value


def _optional_text(value: object) -> str | None:
    return None if value is None else _text(value)


def _hash(value: object) -> str:
    result = _text(value)
    if _HASH.fullmatch(result) is None:
        raise ValueError
    return result


def _integer(value: object) -> int:
    if type(value) is not int:
        raise ValueError
    return value


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError
    return value


def _decimal(value: object, *, signed: bool = False) -> str:
    result = _text(value)
    pattern = _SIGNED_DECIMAL if signed else _DECIMAL
    if pattern.fullmatch(result) is None:
        raise ValueError
    return result


def _same(actual: object, wire: object) -> None:
    if canonical_bytes(actual) != canonical_bytes(wire):
        raise ValueError


def _utc(value: object) -> UtcInstant:
    payload = _object(value, "utc_instant", ("epoch_nanoseconds",), schema=False)
    result = UtcInstant(_integer(payload["epoch_nanoseconds"]))
    _same(result, payload)
    return result


def _simulation(value: object) -> SimulationInstant:
    payload = _object(
        value,
        "simulation_instant",
        ("instant", "phase", "source_sequence"),
        schema=False,
    )
    phase = _object(payload["phase"], "timeline_phase", ("code", "rank"), schema=False)
    sequence = _object(
        payload["source_sequence"], "source_sequence", ("value",), schema=False
    )
    result = SimulationInstant(
        _utc(payload["instant"]),
        TimelinePhase(_integer(phase["rank"]), _text(phase["code"])),
        SourceSequence(_integer(sequence["value"])),
    )
    _same(result, payload)
    return result


def _instrument_id(value: object) -> InstrumentId:
    payload = _object(value, "instrument_id", ("stable_key", "venue"), schema=False)
    result = InstrumentId(
        VenueId(_text(payload["venue"])), _text(payload["stable_key"])
    )
    _same(result, payload)
    return result


def _currency(value: object) -> CurrencyId:
    payload = _object(value, "currency_id", ("value",), schema=False)
    result = CurrencyId(_text(payload["value"]))
    _same(result, payload)
    return result


def _quantity(value: object) -> Quantity:
    payload = _object(
        value, "quantity", ("instrument_id", "scale", "units"), schema=False
    )
    result = Quantity(
        _integer(payload["units"]),
        Scale(_integer(payload["scale"])),
        _text(payload["instrument_id"]),
    )
    _same(result, payload)
    return result


def _artifact_ref(value: object) -> ArtifactRef:
    payload = _object(
        value,
        "artifact_ref",
        ("artifact_type", "content_hash", "schema_version"),
        schema=False,
    )
    result = ArtifactRef(
        _text(payload["artifact_type"]),
        _integer(payload["schema_version"]),
        _hash(payload["content_hash"]),
    )
    _same(result, payload)
    return result


def _rate(value: object) -> Rate:
    payload = _object(value, "rate", ("basis", "scale", "units"), schema=False)
    result = Rate(
        _integer(payload["units"]),
        Scale(_integer(payload["scale"])),
        _text(payload["basis"]),
    )
    _same(result, payload)
    return result


def _metadata_source(value: object) -> BinanceUsdmInstrumentMetadataSourceRef:
    payload = _object(
        value,
        "binance_usdm_instrument_metadata_source_ref",
        ("source_hash", "source_key"),
    )
    result = BinanceUsdmInstrumentMetadataSourceRef(
        _text(payload["source_key"]), _hash(payload["source_hash"])
    )
    _same(result, payload)
    return result


def _metadata_revision(value: object) -> BinanceUsdmInstrumentMetadataRevision:
    fields = (
        "available_at",
        "base_asset",
        "contract_type",
        "delivery_at",
        "effective_from",
        "margin_asset",
        "onboard_at",
        "pair",
        "quote_asset",
        "revision_id",
        "source_ref",
        "stable_instrument_key",
        "status",
        "supersedes_revision_id",
        "symbol",
    )
    payload = _object(value, "binance_usdm_instrument_metadata_revision", fields)
    result = BinanceUsdmInstrumentMetadataRevision(
        revision_id=_text(payload["revision_id"]),
        supersedes_revision_id=_optional_text(payload["supersedes_revision_id"]),
        stable_instrument_key=_text(payload["stable_instrument_key"]),
        symbol=_text(payload["symbol"]),
        pair=_text(payload["pair"]),
        contract_type=_text(payload["contract_type"]),
        status=_text(payload["status"]),
        onboard_at=_utc(payload["onboard_at"]),
        delivery_at=_utc(payload["delivery_at"]),
        base_asset=_text(payload["base_asset"]),
        quote_asset=_text(payload["quote_asset"]),
        margin_asset=_text(payload["margin_asset"]),
        effective_from=_utc(payload["effective_from"]),
        available_at=_utc(payload["available_at"]),
        source_ref=_metadata_source(payload["source_ref"]),
    )
    _same(result, payload)
    return result


def _instrument_resolution(
    value: object,
) -> (
    BinanceUsdmInstrumentMetadataResolution
    | BinanceUsdmTradifiInstrumentMetadataResolution
):
    if type(value) is not dict:
        raise ValueError
    wire_type = value.get("type")
    if wire_type not in (
        "binance_usdm_instrument_metadata_resolution",
        "binance_usdm_tradifi_instrument_metadata_resolution",
    ):
        raise ValueError
    payload = _object(
        value,
        wire_type,
        (
            "active_pair",
            "active_revision",
            "active_symbol",
            "contract_metadata",
            "instrument",
            "listing_interval",
            "query",
            "status",
            "symbol_timeline",
            "tradable",
            "visible_revisions",
        ),
    )
    revisions = tuple(
        _metadata_revision(item) for item in _array(payload["visible_revisions"])
    )
    query_wire = _object(
        payload["query"],
        "binance_usdm_instrument_metadata_query",
        ("captured_at", "effective_at", "revision_hashes", "stable_instrument_key"),
    )
    revision_hashes = tuple(
        _hash(item) for item in _array(query_wire["revision_hashes"])
    )
    if revision_hashes != tuple(item.revision_hash for item in revisions):
        raise ValueError(_UNSUPPORTED_AUTHORITY)
    query = BinanceUsdmInstrumentMetadataQuery(
        stable_instrument_key=_text(query_wire["stable_instrument_key"]),
        effective_at=_utc(query_wire["effective_at"]),
        captured_at=_utc(query_wire["captured_at"]),
        revisions=revisions,
    )
    _same(query, query_wire)
    outcome = (
        BinanceUsdmTradifiInstrumentMetadataModel().resolve_instrument(query)
        if wire_type == "binance_usdm_tradifi_instrument_metadata_resolution"
        else BinanceUsdmInstrumentModel().resolve_instrument(query)
    )
    if outcome.result is None:
        raise ValueError
    _same(outcome.result, payload)
    return outcome.result


def _order_source(value: object) -> BinanceUsdmOrderRuleSourceRef:
    payload = _object(
        value, "binance_usdm_order_rule_source_ref", ("source_hash", "source_key")
    )
    result = BinanceUsdmOrderRuleSourceRef(
        _text(payload["source_key"]), _hash(payload["source_hash"])
    )
    _same(result, payload)
    return result


def _order_band(value: object) -> BinanceUsdmOrderRuleBand:
    fields = (
        "admission_mode",
        "available_at",
        "band_id",
        "deferred_rule_keys",
        "effective_from",
        "effective_to_exclusive",
        "filter_keys",
        "instrument_id",
        "limit_max_qty",
        "limit_min_qty",
        "limit_step_size",
        "market_max_qty",
        "market_min_qty",
        "market_step_size",
        "max_price",
        "min_notional",
        "min_price",
        "order_types",
        "source_ref",
        "supports_reduce_only",
        "tick_size",
        "time_in_forces",
    )
    payload = _object(value, "binance_usdm_order_rule_band", fields)
    result = BinanceUsdmOrderRuleBand(
        band_id=_text(payload["band_id"]),
        instrument_id=_instrument_id(payload["instrument_id"]),
        effective_from=_utc(payload["effective_from"]),
        effective_to_exclusive=_utc(payload["effective_to_exclusive"]),
        available_at=_utc(payload["available_at"]),
        min_price=_decimal(payload["min_price"]),
        max_price=_decimal(payload["max_price"]),
        tick_size=_decimal(payload["tick_size"]),
        limit_min_qty=_decimal(payload["limit_min_qty"]),
        limit_max_qty=_decimal(payload["limit_max_qty"]),
        limit_step_size=_decimal(payload["limit_step_size"]),
        market_min_qty=_decimal(payload["market_min_qty"]),
        market_max_qty=_decimal(payload["market_max_qty"]),
        market_step_size=_decimal(payload["market_step_size"]),
        min_notional=_decimal(payload["min_notional"]),
        filter_keys=tuple(_text(item) for item in _array(payload["filter_keys"])),
        order_types=tuple(_text(item) for item in _array(payload["order_types"])),
        time_in_forces=tuple(_text(item) for item in _array(payload["time_in_forces"])),
        admission_mode=BinanceUsdmOrderAdmissionMode(_text(payload["admission_mode"])),
        supports_reduce_only=_boolean(payload["supports_reduce_only"]),
        deferred_rule_keys=tuple(
            _text(item) for item in _array(payload["deferred_rule_keys"])
        ),
        source_ref=_order_source(payload["source_ref"]),
    )
    _same(result, payload)
    return result


def _order_rules(value: object):
    payload = _object(
        value,
        "binance_usdm_order_rule_resolution",
        (
            "active_band",
            "active_deferred_rule_keys",
            "active_snapshot",
            "component_ref",
            "decision_grade_eligible",
            "deferred_rule_keys",
            "limit_quantity_lattice",
            "market_quantity_lattice",
            "order_capabilities",
            "price_scale",
            "quantity_scale",
            "query",
            "rule_timeline",
            "visible_bands",
        ),
    )
    query_wire = _object(
        payload["query"],
        "binance_usdm_order_rule_query",
        (
            "captured_at",
            "evaluated_at",
            "instrument_metadata",
            "rule_book",
            "session_id",
        ),
    )
    book_wire = _object(
        query_wire["rule_book"],
        "binance_usdm_order_rule_book",
        (
            "bands",
            "coverage_from",
            "coverage_to_exclusive",
            "instrument_id",
            "rule_book_key",
            "rule_book_version",
        ),
    )
    book = BinanceUsdmOrderRuleBook(
        _text(book_wire["rule_book_key"]),
        _integer(book_wire["rule_book_version"]),
        _instrument_id(book_wire["instrument_id"]),
        _utc(book_wire["coverage_from"]),
        _utc(book_wire["coverage_to_exclusive"]),
        tuple(_order_band(item) for item in _array(book_wire["bands"])),
    )
    _same(book, book_wire)
    session_wire = _object(
        query_wire["session_id"], "session_id", ("calendar_id", "value"), schema=False
    )
    session = SessionId(
        _text(session_wire["calendar_id"]), _text(session_wire["value"])
    )
    _same(session, session_wire)
    instrument = _instrument_resolution(query_wire["instrument_metadata"])
    if type(instrument) is not BinanceUsdmInstrumentMetadataResolution:
        raise ValueError
    query = BinanceUsdmOrderRuleQuery(
        instrument,
        session,
        _utc(query_wire["evaluated_at"]),
        _utc(query_wire["captured_at"]),
        book,
    )
    _same(query, query_wire)
    outcome = BinanceUsdmOrderRuleModel().resolve_order_rules(query)
    if outcome.result is None:
        raise ValueError
    _same(outcome.result, payload)
    return outcome.result


def _margin_source(value: object) -> BinanceUsdmMarginTierSourceRef:
    payload = _object(
        value,
        "binance_usdm_margin_tier_source_ref",
        ("source_hash", "source_key", "source_kind"),
    )
    result = BinanceUsdmMarginTierSourceRef(
        _text(payload["source_key"]),
        _hash(payload["source_hash"]),
        _text(payload["source_kind"]),
    )
    _same(result, payload)
    return result


def _margin_bracket(value: object) -> BinanceUsdmMarginTierBracket:
    fields = (
        "bracket_id",
        "maintenance_margin_deduction",
        "maintenance_margin_rate",
        "maximum_leverage",
        "minimum_leverage_range",
        "notional_cap",
        "notional_floor",
    )
    payload = _object(value, "binance_usdm_margin_tier_bracket", fields)
    result = BinanceUsdmMarginTierBracket(
        bracket_id=_decimal(payload["bracket_id"]),
        notional_floor=_decimal(payload["notional_floor"]),
        notional_cap=_decimal(payload["notional_cap"]),
        maintenance_margin_rate=_decimal(payload["maintenance_margin_rate"]),
        maintenance_margin_deduction=_decimal(payload["maintenance_margin_deduction"]),
        minimum_leverage_range=_decimal(payload["minimum_leverage_range"]),
        maximum_leverage=_decimal(payload["maximum_leverage"]),
    )
    _same(result, payload)
    return result


def _margin_band(value: object) -> BinanceUsdmMarginTierBand:
    payload = _object(
        value,
        "binance_usdm_margin_tier_band",
        (
            "available_at",
            "band_id",
            "brackets",
            "effective_from",
            "effective_to_exclusive",
            "instrument_id",
            "notional_coef",
            "scope",
            "source_ref",
        ),
    )
    coef = payload["notional_coef"]
    result = BinanceUsdmMarginTierBand(
        _text(payload["band_id"]),
        _instrument_id(payload["instrument_id"]),
        _utc(payload["effective_from"]),
        _utc(payload["effective_to_exclusive"]),
        _simulation(payload["available_at"]),
        BinanceUsdmMarginTierScope(_text(payload["scope"])),
        None if coef is None else _decimal(coef),
        tuple(_margin_bracket(item) for item in _array(payload["brackets"])),
        _margin_source(payload["source_ref"]),
    )
    _same(result, payload)
    return result


def _margin_tiers(value: object):
    payload = _object(
        value,
        "binance_usdm_margin_tier_resolution",
        (
            "active_band",
            "active_interval",
            "active_tiers",
            "component_ref",
            "coverage_from",
            "coverage_to_exclusive",
            "decision_grade_eligible",
            "finite_terminal_notional_cap",
            "margin_rule_book",
            "query",
            "tier_boundary_convention",
            "visible_bands",
        ),
    )
    query_wire = _object(
        payload["query"],
        "binance_usdm_margin_tier_query",
        ("captured_at", "evaluated_at", "instrument_metadata", "rule_book"),
    )
    book_wire = _object(
        query_wire["rule_book"],
        "binance_usdm_margin_tier_rule_book",
        (
            "bands",
            "coverage_from",
            "coverage_to_exclusive",
            "instrument_id",
            "rule_book_key",
            "rule_book_version",
            "settlement_currency_id",
        ),
    )
    book = BinanceUsdmMarginTierRuleBook(
        _text(book_wire["rule_book_key"]),
        _integer(book_wire["rule_book_version"]),
        _instrument_id(book_wire["instrument_id"]),
        _currency(book_wire["settlement_currency_id"]),
        _utc(book_wire["coverage_from"]),
        _utc(book_wire["coverage_to_exclusive"]),
        tuple(_margin_band(item) for item in _array(book_wire["bands"])),
    )
    _same(book, book_wire)
    instrument = _instrument_resolution(query_wire["instrument_metadata"])
    if type(instrument) is not BinanceUsdmInstrumentMetadataResolution:
        raise ValueError
    query = BinanceUsdmMarginTierQuery(
        instrument,
        _utc(query_wire["evaluated_at"]),
        _simulation(query_wire["captured_at"]),
        book,
    )
    _same(query, query_wire)
    outcome = BinanceUsdmMarginTierModel().resolve_margin_tiers(query)
    if outcome.result is None:
        raise ValueError
    _same(outcome.result, payload)
    return outcome.result


def _price_source(value: object) -> BinanceUsdmPriceSourceRef:
    payload = _object(
        value,
        "binance_usdm_price_source_ref",
        (
            "archive_key",
            "revision_id",
            "source_hash",
            "source_key",
            "supersedes_revision_id",
        ),
    )
    result = BinanceUsdmPriceSourceRef(
        _text(payload["source_key"]),
        _hash(payload["source_hash"]),
        _text(payload["archive_key"]),
        _text(payload["revision_id"]),
        _optional_text(payload["supersedes_revision_id"]),
    )
    _same(result, payload)
    return result


def _aggregate_trade(value: object) -> BinanceUsdmAggregateTradePrice:
    payload = _object(
        value,
        "binance_usdm_aggregate_trade_price",
        (
            "aggregate_trade_id",
            "available_at",
            "buyer_is_maker",
            "event_id",
            "first_trade_id",
            "instrument_id",
            "last_trade_id",
            "price",
            "quantity",
            "source_ref",
            "trade_at",
        ),
    )
    result = BinanceUsdmAggregateTradePrice(
        _text(payload["event_id"]),
        _instrument_id(payload["instrument_id"]),
        _integer(payload["aggregate_trade_id"]),
        _decimal(payload["price"]),
        _decimal(payload["quantity"]),
        _integer(payload["first_trade_id"]),
        _integer(payload["last_trade_id"]),
        _utc(payload["trade_at"]),
        _simulation(payload["available_at"]),
        _boolean(payload["buyer_is_maker"]),
        _price_source(payload["source_ref"]),
    )
    _same(result, payload)
    return result


def _mark_kline(value: object) -> BinanceUsdmMarkPriceKline:
    payload = _object(
        value,
        "binance_usdm_mark_price_kline",
        (
            "available_at",
            "close_price",
            "close_time_milliseconds",
            "closed_at",
            "closed_final",
            "event_id",
            "high_price",
            "instrument_id",
            "interval_key",
            "low_price",
            "open_price",
            "open_time_milliseconds",
            "source_ref",
        ),
    )
    result = BinanceUsdmMarkPriceKline(
        _text(payload["event_id"]),
        _instrument_id(payload["instrument_id"]),
        _text(payload["interval_key"]),
        _integer(payload["open_time_milliseconds"]),
        _integer(payload["close_time_milliseconds"]),
        _decimal(payload["open_price"]),
        _decimal(payload["high_price"]),
        _decimal(payload["low_price"]),
        _decimal(payload["close_price"]),
        _simulation(payload["closed_at"]),
        _simulation(payload["available_at"]),
        _boolean(payload["closed_final"]),
        _price_source(payload["source_ref"]),
    )
    _same(result, payload)
    return result


def _price_coverage(value: object) -> BinanceUsdmPriceStreamCoverage:
    payload = _object(
        value,
        "binance_usdm_price_stream_coverage",
        (
            "coverage_from",
            "coverage_id",
            "coverage_to_exclusive",
            "instrument_id",
            "price_purpose",
            "source_kind",
            "source_ref",
            "stream_id",
        ),
    )
    result = BinanceUsdmPriceStreamCoverage(
        _text(payload["coverage_id"]),
        _instrument_id(payload["instrument_id"]),
        PricePurpose(_text(payload["price_purpose"])),
        BinanceUsdmPriceSourceKind(_text(payload["source_kind"])),
        _utc(payload["coverage_from"]),
        _utc(payload["coverage_to_exclusive"]),
        _text(payload["stream_id"]),
        _price_source(payload["source_ref"]),
    )
    _same(result, payload)
    return result


def _price_book(value: object) -> BinanceUsdmHistoricalPriceBook:
    payload = _object(
        value,
        "binance_usdm_historical_price_book",
        (
            "aggregate_trades",
            "coverages",
            "instrument_id",
            "mark_price_klines",
            "price_book_key",
            "price_book_version",
            "quote_currency_id",
        ),
    )
    result = BinanceUsdmHistoricalPriceBook(
        _text(payload["price_book_key"]),
        _integer(payload["price_book_version"]),
        _instrument_id(payload["instrument_id"]),
        _currency(payload["quote_currency_id"]),
        tuple(_price_coverage(item) for item in _array(payload["coverages"])),
        tuple(_aggregate_trade(item) for item in _array(payload["aggregate_trades"])),
        tuple(_mark_kline(item) for item in _array(payload["mark_price_klines"])),
    )
    _same(result, payload)
    return result


def _stale_policy(value: object) -> StaleMarkPolicy | None:
    if value is None:
        return None
    payload = _object(
        value,
        "stale_mark_policy",
        (
            "allow_forward_fill",
            "max_age_nanoseconds",
            "policy_key",
            "policy_version",
            "price_purpose",
        ),
        schema=False,
    )
    result = StaleMarkPolicy(
        _text(payload["policy_key"]),
        _integer(payload["policy_version"]),
        PricePurpose(_text(payload["price_purpose"])),
        _integer(payload["max_age_nanoseconds"]),
        _boolean(payload["allow_forward_fill"]),
    )
    _same(result, payload)
    return result


def _price_purpose(value: object):
    payload = _object(
        value,
        "binance_usdm_price_purpose_resolution",
        (
            "active_coverages",
            "decision_grade_eligible",
            "limitations",
            "liquidation_bars",
            "model_digest",
            "model_key",
            "model_version",
            "observations",
            "query",
            "resolved_mark",
            "visible_source_records",
        ),
    )
    query_wire = _object(
        payload["query"],
        "binance_usdm_price_purpose_query",
        (
            "captured_at",
            "instrument_metadata",
            "liquidation_interval_end_exclusive",
            "liquidation_interval_start",
            "price_book",
            "price_purpose",
            "requested_at",
            "stale_policy",
        ),
    )
    instrument = _instrument_resolution(query_wire["instrument_metadata"])
    if type(instrument) is not BinanceUsdmInstrumentMetadataResolution:
        raise ValueError
    start = query_wire["liquidation_interval_start"]
    end = query_wire["liquidation_interval_end_exclusive"]
    query = BinanceUsdmPricePurposeQuery(
        instrument,
        _price_book(query_wire["price_book"]),
        PricePurpose(_text(query_wire["price_purpose"])),
        _utc(query_wire["requested_at"]),
        _simulation(query_wire["captured_at"]),
        _stale_policy(query_wire["stale_policy"]),
        None if start is None else _utc(start),
        None if end is None else _utc(end),
    )
    _same(query, query_wire)
    outcome = BinanceUsdmPriceStreamModel().resolve_price_purpose(query)
    if outcome.result is None:
        raise ValueError
    _same(outcome.result, payload)
    return outcome.result


def _funding_source(value: object) -> BinanceUsdmFundingSourceRef:
    payload = _object(
        value,
        "binance_usdm_funding_source_ref",
        (
            "archive_key",
            "revision_id",
            "source_hash",
            "source_key",
            "source_kind",
            "supersedes_revision_id",
        ),
    )
    result = BinanceUsdmFundingSourceRef(
        _text(payload["source_kind"]),
        _text(payload["source_key"]),
        _hash(payload["source_hash"]),
        _text(payload["archive_key"]),
        _text(payload["revision_id"]),
        _optional_text(payload["supersedes_revision_id"]),
    )
    _same(result, payload)
    return result


def _funding_record(value: object) -> BinanceUsdmFundingRateRecord:
    payload = _object(
        value,
        "binance_usdm_funding_rate_record",
        (
            "archive_available_at",
            "event_hash",
            "event_id",
            "funding_rate",
            "funding_time_milliseconds",
            "instrument_id",
            "mark_price",
            "rate_type",
            "revision_id",
            "source_ref",
        ),
    )
    funding_rate = payload["funding_rate"]
    mark_price = payload["mark_price"]
    result = BinanceUsdmFundingRateRecord(
        _instrument_id(payload["instrument_id"]),
        _integer(payload["funding_time_milliseconds"]),
        None if funding_rate is None else _decimal(funding_rate, signed=True),
        None if mark_price is None else _decimal(mark_price),
        _optional_text(payload["rate_type"]),
        _simulation(payload["archive_available_at"]),
        _text(payload["event_id"]),
        _text(payload["revision_id"]),
        _funding_source(payload["source_ref"]),
    )
    _same(result, payload)
    return result


def _funding_coverage(value: object) -> BinanceUsdmFundingCoverage:
    payload = _object(
        value,
        "binance_usdm_funding_coverage",
        (
            "coverage_from",
            "coverage_id",
            "coverage_to_exclusive",
            "instrument_id",
            "source_ref",
            "stream_key",
            "stream_version",
        ),
    )
    result = BinanceUsdmFundingCoverage(
        _text(payload["coverage_id"]),
        _instrument_id(payload["instrument_id"]),
        _utc(payload["coverage_from"]),
        _utc(payload["coverage_to_exclusive"]),
        _text(payload["stream_key"]),
        _integer(payload["stream_version"]),
        _funding_source(payload["source_ref"]),
    )
    _same(result, payload)
    return result


def _funding_book(value: object) -> BinanceUsdmHistoricalFundingBook:
    payload = _object(
        value,
        "binance_usdm_historical_funding_book",
        (
            "coverages",
            "funding_book_key",
            "funding_book_version",
            "instrument_id",
            "records",
        ),
    )
    result = BinanceUsdmHistoricalFundingBook(
        _text(payload["funding_book_key"]),
        _integer(payload["funding_book_version"]),
        _instrument_id(payload["instrument_id"]),
        tuple(_funding_coverage(item) for item in _array(payload["coverages"])),
        tuple(_funding_record(item) for item in _array(payload["records"])),
    )
    _same(result, payload)
    return result


def _application_key(value: object) -> LinearFundingApplicationKey:
    payload = _object(
        value,
        "linear_funding_application_key",
        ("account_id", "slot_id", "value"),
    )
    slot_wire = _object(
        payload["slot_id"],
        "funding_slot_id",
        ("instrument_id", "target_funding_time", "value"),
    )
    slot = FundingSlotId.derive(
        _instrument_id(slot_wire["instrument_id"]),
        _utc(slot_wire["target_funding_time"]),
    )
    _same(slot, slot_wire)
    result = LinearFundingApplicationKey.derive(_text(payload["account_id"]), slot)
    _same(result, payload)
    return result


def _contract(
    value: object, instrument: BinanceUsdmInstrumentMetadataResolution
) -> LinearPerpetualContract:
    payload = _object(
        value,
        "linear_perpetual_contract",
        ("contract_multiplier", "instrument", "price_scale", "quantity_scale"),
    )
    result = LinearPerpetualContract(
        instrument.instrument,
        Scale(_integer(payload["quantity_scale"])),
        Scale(_integer(payload["price_scale"])),
        _rate(payload["contract_multiplier"]),
    )
    _same(result, payload)
    return result


def _funding(value: object):
    payload = _object(
        value,
        "binance_usdm_funding_source_resolution",
        (
            "decision_grade_eligible",
            "funding_mark_evidence",
            "limitations",
            "mark_observation",
            "model_digest",
            "model_key",
            "model_version",
            "publication",
            "query",
            "query_hash",
            "resolution_hash",
            "selected_record",
            "settlement_evidence",
            "slot_id",
            "source_coverage",
        ),
    )
    query_wire = _object(
        payload["query"],
        "binance_usdm_funding_source_query",
        (
            "application_key",
            "captured_at",
            "contract",
            "funding_book",
            "instrument_resolution",
            "target_funding_time",
        ),
    )
    instrument = _instrument_resolution(query_wire["instrument_resolution"])
    if type(instrument) is not BinanceUsdmInstrumentMetadataResolution:
        raise ValueError
    query = BinanceUsdmFundingSourceQuery(
        instrument,
        _contract(query_wire["contract"], instrument),
        _application_key(query_wire["application_key"]),
        _funding_book(query_wire["funding_book"]),
        _utc(query_wire["target_funding_time"]),
        _simulation(query_wire["captured_at"]),
    )
    _same(query, query_wire)
    model_key = _text(payload["model_key"])
    model_version = _integer(payload["model_version"])
    if (model_key, model_version) == (
        "crypto.binance_usdm.funding-sources.v1",
        1,
    ):
        model = BinanceUsdmFundingSourceModel()
    elif (model_key, model_version) == (
        "crypto.binance_usdm.funding-sources.v2",
        2,
    ):
        model = BinanceUsdmFundingSourceModelV2()
    else:
        raise ValueError
    outcome = model.resolve_funding_source(query)
    if outcome.result is None:
        raise ValueError
    _same(outcome.result, payload)
    return outcome.result


def _account_source(value: object) -> BinanceUsdmAccountProfileSourceRef:
    payload = _object(
        value,
        "binance_usdm_account_profile_source_ref",
        (
            "evidence_key",
            "revision_id",
            "source_hash",
            "source_key",
            "source_kind",
            "supersedes_revision_id",
        ),
    )
    result = BinanceUsdmAccountProfileSourceRef(
        BinanceUsdmAccountSourceKind(_text(payload["source_kind"])),
        _text(payload["source_key"]),
        _hash(payload["source_hash"]),
        _text(payload["evidence_key"]),
        _text(payload["revision_id"]),
        _optional_text(payload["supersedes_revision_id"]),
    )
    _same(result, payload)
    return result


def _account_band(value: object) -> BinanceUsdmAccountProfileBand:
    payload = _object(
        value,
        "binance_usdm_account_profile_band",
        (
            "account_id",
            "available_at",
            "band_id",
            "can_trade",
            "dual_side_position",
            "effective_from",
            "effective_to_exclusive",
            "fee_burn",
            "fee_tier",
            "instrument_id",
            "is_auto_add_margin",
            "leverage",
            "maker_commission_rate",
            "margin_type",
            "max_notional_value",
            "multi_assets_margin",
            "scope",
            "source_refs",
            "taker_commission_rate",
            "trade_group_id",
        ),
    )
    result = BinanceUsdmAccountProfileBand(
        _text(payload["band_id"]),
        _text(payload["account_id"]),
        _instrument_id(payload["instrument_id"]),
        _utc(payload["effective_from"]),
        _utc(payload["effective_to_exclusive"]),
        _simulation(payload["available_at"]),
        BinanceUsdmAccountProfileScope(_text(payload["scope"])),
        _integer(payload["fee_tier"]),
        _boolean(payload["can_trade"]),
        _boolean(payload["dual_side_position"]),
        _boolean(payload["multi_assets_margin"]),
        _integer(payload["trade_group_id"]),
        _text(payload["margin_type"]),
        _boolean(payload["is_auto_add_margin"]),
        _decimal(payload["leverage"]),
        _decimal(payload["max_notional_value"]),
        _decimal(payload["maker_commission_rate"], signed=True),
        _decimal(payload["taker_commission_rate"], signed=True),
        _boolean(payload["fee_burn"]),
        tuple(_account_source(item) for item in _array(payload["source_refs"])),
    )
    _same(result, payload)
    return result


def _account_profile(value: object):
    payload = _object(
        value,
        "binance_usdm_account_profile_resolution",
        (
            "account_fee_schedule_ref",
            "account_id",
            "account_scope",
            "active_band",
            "asset_mode",
            "can_trade",
            "decision_grade_eligible",
            "fee_burn",
            "fee_currency_id",
            "fee_reservation_rule_set",
            "fee_reserve_funding_source",
            "fee_scale",
            "fee_tier",
            "final_fee_rule_set",
            "is_auto_add_margin",
            "leverage_evidence",
            "limitations",
            "margin_type",
            "model_digest",
            "model_key",
            "model_version",
            "position_mode",
            "query",
            "query_hash",
            "reporting_currency_id",
            "resolution_hash",
            "trade_group_id",
            "visible_bands",
        ),
    )
    query_wire = _object(
        payload["query"],
        "binance_usdm_account_profile_query",
        (
            "account_id",
            "account_profile_book",
            "captured_at",
            "evaluated_at",
            "instrument_resolution",
            "reporting_currency_id",
        ),
    )
    book_wire = _object(
        query_wire["account_profile_book"],
        "binance_usdm_historical_account_profile_book",
        (
            "account_id",
            "account_profile_book_key",
            "account_profile_book_version",
            "bands",
            "coverage_from",
            "coverage_to_exclusive",
            "instrument_id",
        ),
    )
    book = BinanceUsdmHistoricalAccountProfileBook(
        _text(book_wire["account_profile_book_key"]),
        _integer(book_wire["account_profile_book_version"]),
        _text(book_wire["account_id"]),
        _instrument_id(book_wire["instrument_id"]),
        _utc(book_wire["coverage_from"]),
        _utc(book_wire["coverage_to_exclusive"]),
        tuple(_account_band(item) for item in _array(book_wire["bands"])),
    )
    _same(book, book_wire)
    instrument = _instrument_resolution(query_wire["instrument_resolution"])
    if type(instrument) is not BinanceUsdmInstrumentMetadataResolution:
        raise ValueError
    query = BinanceUsdmAccountProfileQuery(
        instrument,
        _text(query_wire["account_id"]),
        book,
        _utc(query_wire["evaluated_at"]),
        _simulation(query_wire["captured_at"]),
        _currency(query_wire["reporting_currency_id"]),
    )
    _same(query, query_wire)
    outcome = BinanceUsdmAccountProfileModel().resolve_account_profile(query)
    if outcome.result is None:
        raise ValueError
    _same(outcome.result, payload)
    return outcome.result


def _account_capacity(value: object) -> BinanceUsdmAccountCapacityEvidence:
    payload = _object(
        value,
        "binance_usdm_account_capacity_evidence",
        (
            "account_id",
            "available_at",
            "effective_from",
            "effective_to_exclusive",
            "evidence_key",
            "evidence_version",
            "instrument_id",
            "max_num_algo_orders",
            "max_num_orders",
            "revision_id",
            "source_hash",
            "source_key",
        ),
    )
    result = BinanceUsdmAccountCapacityEvidence(
        _text(payload["evidence_key"]),
        _integer(payload["evidence_version"]),
        _text(payload["account_id"]),
        _instrument_id(payload["instrument_id"]),
        _utc(payload["effective_from"]),
        _utc(payload["effective_to_exclusive"]),
        _simulation(payload["available_at"]),
        _integer(payload["max_num_orders"]),
        _integer(payload["max_num_algo_orders"]),
        _text(payload["source_key"]),
        _hash(payload["source_hash"]),
        _text(payload["revision_id"]),
    )
    _same(result, payload)
    return result


def _slippage(value: object) -> DeterministicBpsSlippageModel:
    payload = _object(
        value,
        "deterministic_bps_slippage_model_binding",
        (
            "applicability_envelope",
            "basis_points_scale",
            "basis_points_units",
            "calibration_ref",
            "component_ref",
            "limitations",
            "rounding",
        ),
        schema=False,
    )
    component_wire = _object(
        payload["component_ref"],
        "simulation_component_ref",
        ("component_digest", "component_key", "component_version", "port_type"),
        schema=False,
    )
    component = SimulationComponentRef(
        SimulationPortType(_text(component_wire["port_type"])),
        _text(component_wire["component_key"]),
        _integer(component_wire["component_version"]),
        _hash(component_wire["component_digest"]),
    )
    _same(component, component_wire)
    calibration_wire = _object(
        payload["calibration_ref"],
        "slippage_calibration_ref",
        ("calibration_digest", "calibration_key", "calibration_version"),
        schema=False,
    )
    calibration = SlippageCalibrationRef(
        _text(calibration_wire["calibration_key"]),
        _integer(calibration_wire["calibration_version"]),
        _hash(calibration_wire["calibration_digest"]),
    )
    _same(calibration, calibration_wire)
    envelope_wire = _object(
        payload["applicability_envelope"],
        "slippage_applicability_envelope",
        (
            "allowed_market_state_keys",
            "config_hash",
            "envelope_key",
            "envelope_version",
            "instrument_id",
            "maximum_quantity",
            "valid_from",
            "valid_to_exclusive",
        ),
    )
    envelope = SlippageApplicabilityEnvelope(
        _text(envelope_wire["envelope_key"]),
        _integer(envelope_wire["envelope_version"]),
        _instrument_id(envelope_wire["instrument_id"]),
        _utc(envelope_wire["valid_from"]),
        _utc(envelope_wire["valid_to_exclusive"]),
        _quantity(envelope_wire["maximum_quantity"]),
        tuple(
            _text(item) for item in _array(envelope_wire["allowed_market_state_keys"])
        ),
        _hash(envelope_wire["config_hash"]),
    )
    _same(envelope, envelope_wire)
    return DeterministicBpsSlippageModel(
        component,
        calibration,
        envelope,
        _integer(payload["basis_points_units"]),
        Scale(_integer(payload["basis_points_scale"])),
        RoundingPolicy(_text(payload["rounding"])),
        tuple(
            SlippageLimitation(_text(item)) for item in _array(payload["limitations"])
        ),
    )


def _timeline(value: object) -> TimelineWindow:
    payload = _object(
        value,
        "timeline_window",
        ("data_start", "end_exclusive", "trading_start"),
        schema=False,
    )
    result = TimelineWindow(
        _utc(payload["data_start"]),
        _utc(payload["trading_start"]),
        _utc(payload["end_exclusive"]),
    )
    _same(result, payload)
    return result


def _decode(
    wire: dict[str, object], expected_hash: str
) -> BinanceUsdmTradifiProfileCompositionRequest:
    fields = (
        "account_capacity", "account_profile", "admitted_maximum_quantity",
        "calendar_refs", "composed_at", "funding_sources", "instrument_metadata",
        "margin_tiers", "order_rules", "post_adjustment_unit_regime_ref",
        "price_purposes", "required_market_state_keys", "slippage_model",
        "timeline_window",
    )
    raw_exact_valuation = wire.get("raw_exact_valuation") is True
    raw_exact_margin = wire.get("raw_exact_margin") is True
    raw_exact_strategy = wire.get("raw_exact_strategy") is True
    raw_exact_liquidation = wire.get("raw_exact_liquidation") is True
    payload = _object(
        wire,
        "binance_usdm_tradifi_profile_composition_request",
        fields
        + (("raw_exact_valuation",) if raw_exact_valuation else ())
        + (("raw_exact_margin",) if raw_exact_margin else ())
        + (("raw_exact_strategy",) if raw_exact_strategy else ())
        + (("raw_exact_liquidation",) if raw_exact_liquidation else ()),
    )
    instrument_wire = payload["instrument_metadata"]
    instrument = (
        None if instrument_wire is None else _instrument_resolution(instrument_wire)
    )
    calendar_refs = tuple(
        _artifact_ref(item) for item in _array(payload["calendar_refs"])
    )
    unit_wire = payload["post_adjustment_unit_regime_ref"]
    unit_ref = None if unit_wire is None else _artifact_ref(unit_wire)
    request = BinanceUsdmTradifiProfileCompositionRequest(
        instrument_metadata=instrument,
        order_rules=(
            None
            if payload["order_rules"] is None
            else _order_rules(payload["order_rules"])
        ),
        margin_tiers=(
            None
            if payload["margin_tiers"] is None
            else _margin_tiers(payload["margin_tiers"])
        ),
        price_purposes=tuple(
            _price_purpose(item) for item in _array(payload["price_purposes"])
        ),
        funding_sources=tuple(
            _funding(item) for item in _array(payload["funding_sources"])
        ),
        account_profile=(
            None
            if payload["account_profile"] is None
            else _account_profile(payload["account_profile"])
        ),
        account_capacity=(
            None
            if payload["account_capacity"] is None
            else _account_capacity(payload["account_capacity"])
        ),
        timeline_window=_timeline(payload["timeline_window"]),
        composed_at=_simulation(payload["composed_at"]),
        calendar_refs=calendar_refs,
        post_adjustment_unit_regime_ref=unit_ref,
        slippage_model=_slippage(payload["slippage_model"]),
        admitted_maximum_quantity=_quantity(payload["admitted_maximum_quantity"]),
        required_market_state_keys=tuple(
            _text(item) for item in _array(payload["required_market_state_keys"])
        ),
        raw_exact_valuation=raw_exact_valuation,
        raw_exact_margin=raw_exact_margin,
        raw_exact_strategy=raw_exact_strategy,
        raw_exact_liquidation=raw_exact_liquidation,
    )
    wire_hash = canonical_sha256(payload)
    if (
        _hash(expected_hash) != wire_hash
        or request.request_hash != wire_hash
        or canonical_bytes(request) != canonical_bytes(payload)
    ):
        raise ValueError
    return request


def decode_binance_usdm_tradifi_profile_composition_request_v1(
    wire: Mapping[str, object], expected_hash: str
) -> BinanceUsdmTradifiProfileCompositionRequest:
    """Decode accepted single-regime V1 authority wire.

    Instrument query revision hashes must exactly describe the visible revision
    bodies carried by the wire. Stage1 hidden metadata revisions are hash-only,
    non-invertible authorities and are rejected by this no-cross-regime codec.
    """

    try:
        normalized = _normalize(wire)
        if type(normalized) is not dict:
            raise ValueError
        return _decode(normalized, expected_hash)
    except Exception:  # noqa: BLE001 - Mapping implementations are untrusted
        raise ValueError(_ERROR) from None
