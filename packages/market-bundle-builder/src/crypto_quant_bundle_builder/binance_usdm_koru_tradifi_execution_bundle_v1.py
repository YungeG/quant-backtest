"""Final immutable in-memory KORU TradFi execution bundle assembly."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    InstrumentId,
    Money,
    Scale,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    InMemoryMarketBundleReader,
    MarketBundleCapability,
    MarketBundleManifest,
    MarketBundleRef,
    MarketEvent,
    MarketStreamManifest,
)

from .binance_usdm_koru_closed_market_range_targets_v1 import (
    BinanceUsdmKoruClosedMarketRangeParameterArtifactBindingV1,
    BinanceUsdmKoruClosedMarketRangeStrategyArtifactBindingV1,
    BinanceUsdmKoruClosedMarketRangeTargetsResultV1,
)
from .binance_usdm_koru_closed_market_range_targets_v1 import (
    _trusted_result as _trusted_target_result,
)
from .binance_usdm_koru_tradifi_source_projection_v1 import (
    BinanceUsdmKoruTradifiSourceProjectionResultV1,
)
from .binance_usdm_koru_tradifi_source_projection_v1 import (
    _trusted_result as _trusted_source_result,
)

_SCHEMA_VERSION = 1
_PROFILE_REQUEST_TYPE = "binance_usdm_tradifi_profile_composition_request"
_PROFILE_REQUEST_KEYS = frozenset(
    {
        "type",
        "schema_version",
        "instrument_metadata",
        "order_rules",
        "margin_tiers",
        "price_purposes",
        "funding_sources",
        "account_profile",
        "account_capacity",
        "timeline_window",
        "composed_at",
        "calendar_refs",
        "post_adjustment_unit_regime_ref",
        "slippage_model",
        "admitted_maximum_quantity",
        "required_market_state_keys",
    }
)
_ACCOUNT_PROFILE_KEYS = frozenset(
    {
        "type",
        "schema_version",
        "model_key",
        "model_version",
        "model_digest",
        "query",
        "query_hash",
        "visible_bands",
        "active_band",
        "account_id",
        "account_scope",
        "can_trade",
        "position_mode",
        "asset_mode",
        "margin_type",
        "is_auto_add_margin",
        "fee_burn",
        "fee_tier",
        "trade_group_id",
        "leverage_evidence",
        "account_fee_schedule_ref",
        "fee_reservation_rule_set",
        "final_fee_rule_set",
        "reporting_currency_id",
        "fee_currency_id",
        "fee_scale",
        "fee_reserve_funding_source",
        "limitations",
        "decision_grade_eligible",
        "resolution_hash",
    }
)
_ACCOUNT_CAPACITY_KEYS = frozenset(
    {
        "type",
        "schema_version",
        "evidence_key",
        "evidence_version",
        "account_id",
        "instrument_id",
        "effective_from",
        "effective_to_exclusive",
        "available_at",
        "max_num_orders",
        "max_num_algo_orders",
        "source_key",
        "source_hash",
        "revision_id",
    }
)
_ACCOUNT_QUERY_KEYS = frozenset(
    {
        "type",
        "schema_version",
        "instrument_resolution",
        "account_id",
        "account_profile_book",
        "evaluated_at",
        "captured_at",
        "reporting_currency_id",
    }
)
_ACCOUNT_BOOK_KEYS = frozenset(
    {
        "type",
        "schema_version",
        "account_profile_book_key",
        "account_profile_book_version",
        "account_id",
        "instrument_id",
        "coverage_from",
        "coverage_to_exclusive",
        "bands",
    }
)
_ACCOUNT_BAND_KEYS = frozenset(
    {
        "type",
        "schema_version",
        "band_id",
        "account_id",
        "instrument_id",
        "effective_from",
        "effective_to_exclusive",
        "available_at",
        "scope",
        "fee_tier",
        "can_trade",
        "dual_side_position",
        "multi_assets_margin",
        "trade_group_id",
        "margin_type",
        "is_auto_add_margin",
        "leverage",
        "max_notional_value",
        "maker_commission_rate",
        "taker_commission_rate",
        "fee_burn",
        "source_refs",
    }
)
_ACCOUNT_SOURCE_REF_KEYS = frozenset(
    {
        "type",
        "schema_version",
        "source_kind",
        "source_key",
        "source_hash",
        "evidence_key",
        "revision_id",
        "supersedes_revision_id",
    }
)
_LEVERAGE_EVIDENCE_KEYS = frozenset(
    {
        "type",
        "schema_version",
        "account_id",
        "instrument_id",
        "selected_leverage",
        "effective_from",
        "effective_to_exclusive",
        "available_at",
        "source_key",
        "source_hash",
    }
)
_ORDER_SOURCE_REF_KEYS = frozenset(
    {"type", "schema_version", "source_key", "source_hash"}
)
_PRICE_RESOLUTION_KEYS = frozenset(
    {
        "type",
        "schema_version",
        "query",
        "model_key",
        "model_version",
        "model_digest",
        "visible_source_records",
        "active_coverages",
        "observations",
        "resolved_mark",
        "liquidation_bars",
        "limitations",
        "decision_grade_eligible",
    }
)
_PRICE_QUERY_KEYS = frozenset(
    {
        "type",
        "schema_version",
        "instrument_metadata",
        "price_book",
        "price_purpose",
        "requested_at",
        "captured_at",
        "stale_policy",
        "liquidation_interval_start",
        "liquidation_interval_end_exclusive",
    }
)
_PRICE_BOOK_KEYS = frozenset(
    {
        "type",
        "schema_version",
        "price_book_key",
        "price_book_version",
        "instrument_id",
        "quote_currency_id",
        "coverages",
        "aggregate_trades",
        "mark_price_klines",
    }
)
_PRICE_COVERAGE_KEYS = frozenset(
    {
        "type",
        "schema_version",
        "coverage_id",
        "instrument_id",
        "price_purpose",
        "source_kind",
        "coverage_from",
        "coverage_to_exclusive",
        "stream_id",
        "source_ref",
    }
)
_PRICE_SOURCE_REF_KEYS = frozenset(
    {
        "type",
        "schema_version",
        "source_key",
        "source_hash",
        "archive_key",
        "revision_id",
        "supersedes_revision_id",
    }
)
_INSTRUMENT = InstrumentId(VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual")
_INSTRUMENT_WIRE = _INSTRUMENT.to_canonical_dict()
_USDT_WIRE = {"type": "currency_id", "value": "USDT"}
_BOUND_PRICE_PURPOSES = (
    "execution_reference",
    "liquidation",
    "margin",
    "valuation",
)
_PRICE_PURPOSE_SOURCE_KINDS = {
    "execution_reference": "aggregate_trade",
    "liquidation": "mark_price_kline",
    "margin": "mark_price_kline",
    "valuation": "mark_price_kline",
}
_PRICE_PURPOSE_SOURCE_STREAMS = {
    "execution_reference": (
        "binance_usdm.aggregate_trades.execution_reference.koruusdt.tradifi.v1"
    ),
    "liquidation": "binance_usdm.mark_price.liquidation.koruusdt.1h.v1",
    "margin": "binance_usdm.mark_price.margin.koruusdt.1h.v1",
    "valuation": "binance_usdm.mark_price.valuation.koruusdt.1h.v1",
}
_ACCOUNT_SOURCE_KINDS = (
    "account_config",
    "commission_rate",
    "fee_burn",
    "symbol_config",
)
_ACCOUNT_MODEL_KEY = "crypto.binance_usdm.account-profile.v1"
_ACCOUNT_MODEL_DIGEST = (
    "sha256:ca590d72c3779164107ec960f7c557fdc3bc81bc9200d10790a937c3333b21b3"
)
_ACCOUNT_LIMITATIONS = (
    "development_grade_account_history_completeness_unproven",
    "fee_rounding_parity_unproven",
    "negative_rebates_unsupported",
    "bnb_fee_discount_unsupported",
    "account_risk_policy_composition_owned_by_g10g",
)
_REQUIRED_EQUITY = Money(1_000_000_000_000, Scale(8), "USDT")
_REQUIRED_ALLOCATION = "1"
_REQUIRED_POSITION_NOTIONAL = "1000"
_PREPARATION_STREAM = "binance_usdm.tradifi.preparation_authority.v1"
_PREPARATION_EVENT_TYPE = "binance_usdm_tradifi_preparation_authority_v1"
_PREPARATION_CAPABILITY = MarketBundleCapability(
    "binance_usdm.tradifi.preparation-authority", 1
)
_ACCOUNT_STREAM = "binance_usdm.tradifi.account.authority.koruusdt.v1"
_ACCOUNT_EVENT_TYPE = "account_financial_event"
_ACCOUNT_CAPABILITY = MarketBundleCapability("account.financial-event", 1)
_PRICE_PURPOSE_STREAM = "binance_usdm.tradifi.price_purpose.authority.koruusdt.v1"
_PRICE_PURPOSE_EVENT_TYPE = "binance_usdm_tradifi_price_purpose_binding_v1"
_PRICE_PURPOSE_CAPABILITY = MarketBundleCapability(
    "binance_usdm.price-purpose-streams", 1
)
_SOURCE_LIMITATIONS = (
    "aggregate_trade_event_represented_by_bar_open_v1",
    "development_only",
    "first_retained_trade_full_fill_only",
    "historical_account_and_market_archive_completeness_unproven",
    "post_adjustment_single_unit_regime_only",
    "source_fragment_decision_grade_ineligible",
    "source_fragment_deployment_unauthorized",
)


def _canonical_equal(left: object, right: object) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def _canonical_text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    return value


def _canonical_hash(name: str, value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _freeze_json(
    value: object, path: str = "profile_composition_request_wire"
) -> object:
    if value is None or type(value) in (bool, int, str):
        return value
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise TypeError(f"{path} object keys must be strings")
        return MappingProxyType(
            {key: _freeze_json(value[key], f"{path}.{key}") for key in sorted(value)}
        )
    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_json(item, f"{path}[{index}]") for index, item in enumerate(value)
        )
    raise TypeError(f"{path} must contain JSON values only")


def _mapping(value: object, subject: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        raise ValueError(f"{subject} must be a JSON object")
    return value


def _sequence(value: object, subject: str) -> tuple[object, ...]:
    if not isinstance(value, (tuple, list)):
        raise TypeError(f"{subject} must be a JSON array")
    return tuple(value)


def _wire_ref(ref: ArtifactRef) -> dict[str, object]:
    return ref.to_canonical_dict()


def _wire_instant(value: object, subject: str) -> int:
    instant = _mapping(value, subject)
    if (
        set(instant) != {"type", "epoch_nanoseconds"}
        or instant.get("type") != "utc_instant"
    ):
        raise ValueError(f"{subject} must be a canonical UTC instant")
    nanoseconds = instant.get("epoch_nanoseconds")
    if type(nanoseconds) is not int:
        raise ValueError(f"{subject} epoch must be an integer")
    return nanoseconds


def _simulation_key(value: object, subject: str) -> tuple[int, int, str, int]:
    instant = _mapping(value, subject)
    phase = _mapping(instant.get("phase"), f"{subject}.phase")
    sequence = _mapping(instant.get("source_sequence"), f"{subject}.source_sequence")
    rank = phase.get("rank")
    sequence_value = sequence.get("value")
    if (
        set(instant) != {"type", "instant", "phase", "source_sequence"}
        or instant.get("type") != "simulation_instant"
        or set(phase) != {"type", "rank", "code"}
        or phase.get("type") != "timeline_phase"
        or type(rank) is not int
        or rank < 0
        or set(sequence) != {"type", "value"}
        or sequence.get("type") != "source_sequence"
        or type(sequence_value) is not int
        or sequence_value < 0
    ):
        raise ValueError(f"{subject} must be a canonical simulation instant")
    return (
        _wire_instant(instant.get("instant"), f"{subject}.instant"),
        rank,
        _canonical_text(f"{subject}.phase.code", phase.get("code")),
        sequence_value,
    )


def _exact_wire_object(
    value: object,
    subject: str,
    keys: frozenset[str],
    wire_type: str,
) -> Mapping[str, object]:
    result = _mapping(value, subject)
    if (
        set(result) != keys
        or result.get("type") != wire_type
        or type(result.get("schema_version")) is not int
        or result.get("schema_version") != _SCHEMA_VERSION
    ):
        raise ValueError(f"{subject} schema/type mismatch")
    return result


def _currency_is_usdt(value: object) -> bool:
    return _canonical_equal(value, _USDT_WIRE)


def _validate_embedded_ids(value: object, account_id: str, path: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "account_id" and item != account_id:
                raise ValueError(f"profile account mismatch at {path}.account_id")
            if key == "instrument_id" and not _canonical_equal(item, _INSTRUMENT_WIRE):
                raise ValueError(f"{path} contains a foreign instrument_id")
            _validate_embedded_ids(item, account_id, f"{path}.{key}")
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            _validate_embedded_ids(item, account_id, f"{path}[{index}]")


def _config_hash(rule_set: Mapping[str, object], config_type: str) -> str:
    payload = dict(rule_set)
    payload.pop("config_hash", None)
    payload["type"] = config_type
    return canonical_sha256(payload)


def _exact_int(value: object, subject: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{subject} must be an exact integer")
    return value


def _decimal_parts(
    value: object, subject: str, *, maximum_scale: int = 18
) -> tuple[int, int]:
    if type(value) is not str or not value or value.count(".") > 1:
        raise ValueError(f"{subject} must be a canonical decimal")
    whole, separator, fraction = value.partition(".")
    if (
        not whole.isdigit()
        or (separator and (not fraction.isdigit() or len(fraction) > maximum_scale))
        or (len(whole) > 1 and whole.startswith("0"))
    ):
        raise ValueError(f"{subject} must be a canonical decimal")
    try:
        return int(whole + fraction), len(fraction)
    except ValueError as error:
        raise ValueError(f"{subject} must be a canonical decimal") from error


def _decimal_at_scale_8(value: object, subject: str) -> int:
    units, scale = _decimal_parts(value, subject, maximum_scale=8)
    return units * 10 ** (8 - scale)


def _decimal_rate(value: object, subject: str) -> dict[str, object]:
    units, scale = _decimal_parts(value, subject)
    return {"type": "rate", "units": units, "scale": scale, "basis": "fee_fraction"}


def _greater_or_equal_rate(
    left: Mapping[str, object], right: Mapping[str, object]
) -> bool:
    left_units = _exact_int(left.get("units"), "left rate units")
    right_units = _exact_int(right.get("units"), "right rate units")
    left_scale = _exact_int(left.get("scale"), "left rate scale")
    right_scale = _exact_int(right.get("scale"), "right rate scale")
    return left_units * 10**right_scale >= right_units * 10**left_scale


def _component_ref(port_type: str, key: str, policy: str) -> dict[str, object]:
    return {
        "type": "profile_component_ref",
        "port_type": port_type,
        "component_key": key,
        "component_version": 1,
        "component_digest": canonical_sha256(
            {
                "type": "binance_usdm_not_applicable_fee_component",
                "schema_version": _SCHEMA_VERSION,
                "port_type": port_type,
                "component_key": key,
                "policy": policy,
            }
        ),
    }


def _market_fee_ref() -> dict[str, object]:
    return _component_ref(
        "fee_assessment_policy",
        "crypto.binance_usdm.market-fee-not-applicable.v1",
        "account-specific commission owns exchange trading fee",
    )


def _tax_ref() -> dict[str, object]:
    return _component_ref(
        "tax_policy",
        "crypto.binance_usdm.tax-not-applicable.v1",
        "no separate transaction tax in frozen profile",
    )


def _whole_leverage(value: object, subject: str) -> int:
    units, scale = _decimal_parts(value, subject)
    if units % 10**scale or not 1 <= units // 10**scale <= 125:
        raise ValueError(f"{subject} must be an integer leverage from 1 through 125")
    return units // 10**scale


def _exact_bool(value: object, expected: bool) -> bool:
    return type(value) is bool and value == expected


def _validate_fee_authority(
    account: Mapping[str, object], active: Mapping[str, object]
) -> None:
    maker_rate = _decimal_rate(
        active.get("maker_commission_rate"), "active maker commission"
    )
    taker_rate = _decimal_rate(
        active.get("taker_commission_rate"), "active taker commission"
    )
    reservation_rate = (
        maker_rate if _greater_or_equal_rate(maker_rate, taker_rate) else taker_rate
    )
    reservation_quantization = {
        "type": "quantization_policy",
        "version": "binance-usdm-fee-reservation-ceiling-v1",
        "target_scale": 8,
        "rounding": "ceiling",
    }
    final_quantization = {
        "type": "quantization_policy",
        "version": "binance-usdm-final-fee-toward-zero-v1",
        "target_scale": 8,
        "rounding": "toward_zero",
    }
    zero_rate = {"type": "rate", "units": 0, "scale": 8, "basis": "fee_fraction"}
    expected_schedule = {
        "type": "account_fee_schedule_ref",
        "schedule_key": (
            f"binance.usdm.account-fee.{account['account_id']}.{_INSTRUMENT}"
        ),
        "schedule_version": 1,
        "schedule_digest": canonical_sha256(
            {
                "type": "binance_usdm_account_fee_schedule",
                "schema_version": _SCHEMA_VERSION,
                "account_id": account["account_id"],
                "instrument_id": _INSTRUMENT_WIRE,
                "band": active,
                "maker_rate": maker_rate,
                "taker_rate": taker_rate,
                "currency_id": _USDT_WIRE,
                "fee_scale": 8,
                "reservation_quantization": reservation_quantization,
                "final_quantization": final_quantization,
                "limitations": _ACCOUNT_LIMITATIONS,
            }
        ),
    }
    reservation = {
        "type": "fee_reservation_rule_set",
        "schema_version": _SCHEMA_VERSION,
        "market_fee_policy_ref": _market_fee_ref(),
        "tax_policy_ref": _tax_ref(),
        "account_fee_schedule_ref": expected_schedule,
        "reservation_currency": _USDT_WIRE,
        "reservation_scale": 8,
        "charge_rules": (
            {
                "type": "fee_reservation_charge_rule",
                "source": "market_fee",
                "rule_id": "binance-usdm-market-fee-not-applicable",
                "basis": "order_notional",
                "applicability": "not_applicable",
                "rate": zero_rate,
                "flat_amount": None,
                "quantization": reservation_quantization,
            },
            {
                "type": "fee_reservation_charge_rule",
                "source": "tax",
                "rule_id": "binance-usdm-tax-not-applicable",
                "basis": "order_notional",
                "applicability": "not_applicable",
                "rate": zero_rate,
                "flat_amount": None,
                "quantization": reservation_quantization,
            },
            {
                "type": "fee_reservation_charge_rule",
                "source": "account_schedule",
                "rule_id": "binance-usdm-account-worst-case-commission",
                "basis": "order_notional",
                "applicability": "applies",
                "rate": reservation_rate,
                "flat_amount": None,
                "quantization": reservation_quantization,
            },
        ),
        "minimums": (),
    }
    reservation["config_hash"] = _config_hash(
        reservation, "fee_reservation_rule_set_config"
    )
    final = {
        "type": "final_fee_rule_set",
        "schema_version": _SCHEMA_VERSION,
        "market_fee_policy_ref": _market_fee_ref(),
        "tax_policy_ref": _tax_ref(),
        "account_fee_schedule_ref": expected_schedule,
        "assessment_currency": _USDT_WIRE,
        "assessment_scale": 8,
        "charge_rules": (
            {
                "type": "final_fee_charge_rule",
                "source": "market_fee",
                "rule_id": "binance-usdm-market-fee-not-applicable",
                "basis_type": "fill",
                "calculation_basis": "notional_rate",
                "applicability": "not_applicable",
                "rate": zero_rate,
                "flat_amount": None,
                "quantization": final_quantization,
            },
            {
                "type": "final_fee_charge_rule",
                "source": "tax",
                "rule_id": "binance-usdm-tax-not-applicable",
                "basis_type": "fill",
                "calculation_basis": "notional_rate",
                "applicability": "not_applicable",
                "rate": zero_rate,
                "flat_amount": None,
                "quantization": final_quantization,
            },
            {
                "type": "final_fee_charge_rule",
                "source": "account_schedule",
                "rule_id": "binance-usdm-account-maker-commission",
                "basis_type": "fill",
                "calculation_basis": "notional_rate",
                "applicability": "maker_only",
                "rate": maker_rate,
                "flat_amount": None,
                "quantization": final_quantization,
            },
            {
                "type": "final_fee_charge_rule",
                "source": "account_schedule",
                "rule_id": "binance-usdm-account-taker-commission",
                "basis_type": "fill",
                "calculation_basis": "notional_rate",
                "applicability": "taker_only",
                "rate": taker_rate,
                "flat_amount": None,
                "quantization": final_quantization,
            },
        ),
        "minimums": (),
    }
    final["config_hash"] = _config_hash(final, "final_fee_rule_set_config")
    if (
        not _canonical_equal(account.get("account_fee_schedule_ref"), expected_schedule)
        or not _canonical_equal(account.get("fee_reservation_rule_set"), reservation)
        or not _canonical_equal(account.get("final_fee_rule_set"), final)
    ):
        raise ValueError("account fee authority binding mismatch")


def _validate_account_authority(
    profile: Mapping[str, object],
    account_id: str,
) -> None:
    account = _exact_wire_object(
        profile.get("account_profile"),
        "account_profile",
        _ACCOUNT_PROFILE_KEYS,
        "binance_usdm_account_profile_resolution",
    )
    capacity = _exact_wire_object(
        profile.get("account_capacity"),
        "account_capacity",
        _ACCOUNT_CAPACITY_KEYS,
        "binance_usdm_account_capacity_evidence",
    )
    _validate_embedded_ids(account, account_id, "account_profile")
    _validate_embedded_ids(capacity, account_id, "account_capacity")
    for key in ("account_id", "account_scope"):
        _canonical_text(f"account_profile.{key}", account.get(key))
    for key in ("query_hash", "resolution_hash"):
        _canonical_hash(f"account_profile.{key}", account.get(key))
    if (
        account.get("model_key") != _ACCOUNT_MODEL_KEY
        or account.get("model_version") != 1
        or account.get("model_digest") != _ACCOUNT_MODEL_DIGEST
        or not _canonical_equal(account.get("limitations"), _ACCOUNT_LIMITATIONS)
    ):
        raise ValueError("account profile model authority mismatch")

    query = _exact_wire_object(
        account.get("query"),
        "account_profile.query",
        _ACCOUNT_QUERY_KEYS,
        "binance_usdm_account_profile_query",
    )
    book = _exact_wire_object(
        query.get("account_profile_book"),
        "account_profile.query.account_profile_book",
        _ACCOUNT_BOOK_KEYS,
        "binance_usdm_historical_account_profile_book",
    )
    _canonical_text("account_profile_book.key", book.get("account_profile_book_key"))
    if (
        _exact_int(
            book.get("account_profile_book_version"),
            "account_profile_book.account_profile_book_version",
        )
        <= 0
        or query.get("account_id") != account_id
        or book.get("account_id") != account_id
        or not _canonical_equal(book.get("instrument_id"), _INSTRUMENT_WIRE)
        or not _currency_is_usdt(query.get("reporting_currency_id"))
    ):
        raise ValueError("account query/book identity mismatch")

    evaluated_at = _wire_instant(
        query.get("evaluated_at"), "account query evaluated_at"
    )
    captured_at = _simulation_key(query.get("captured_at"), "account query captured_at")
    composed_at = _simulation_key(profile.get("composed_at"), "profile composed_at")
    coverage_from = _wire_instant(
        book.get("coverage_from"), "account book coverage_from"
    )
    coverage_to = _wire_instant(
        book.get("coverage_to_exclusive"), "account book coverage_to_exclusive"
    )
    if coverage_from >= coverage_to or captured_at > composed_at:
        raise ValueError("account query/book timing mismatch")

    bands = tuple(
        _exact_wire_object(
            value,
            f"account_profile_book.bands[{index}]",
            _ACCOUNT_BAND_KEYS,
            "binance_usdm_account_profile_band",
        )
        for index, value in enumerate(
            _sequence(book.get("bands"), "account_profile_book.bands")
        )
    )
    if not bands:
        raise ValueError("account profile book must contain bands")
    band_rows: list[
        tuple[Mapping[str, object], int, int, tuple[int, int, str, int]]
    ] = []
    prior_sources: dict[str, Mapping[str, object]] = {}
    for index, band in enumerate(bands):
        start = _wire_instant(
            band.get("effective_from"), f"band[{index}].effective_from"
        )
        end = _wire_instant(
            band.get("effective_to_exclusive"),
            f"band[{index}].effective_to_exclusive",
        )
        available = _simulation_key(
            band.get("available_at"), f"band[{index}].available_at"
        )
        _canonical_text(f"band[{index}].band_id", band.get("band_id"))
        max_notional, _ = _decimal_parts(
            band.get("max_notional_value"), f"band[{index}].max_notional_value"
        )
        _whole_leverage(band.get("leverage"), f"band[{index}].leverage")
        _decimal_rate(
            band.get("maker_commission_rate"), f"band[{index}].maker_commission_rate"
        )
        _decimal_rate(
            band.get("taker_commission_rate"), f"band[{index}].taker_commission_rate"
        )
        fee_tier = band.get("fee_tier")
        if (
            start >= end
            or max_notional <= 0
            or band.get("account_id") != account_id
            or not _canonical_equal(band.get("instrument_id"), _INSTRUMENT_WIRE)
            or type(fee_tier) is not int
            or fee_tier < 0
            or type(band.get("trade_group_id")) is not int
        ):
            raise ValueError("account band identity/value mismatch")
        refs = tuple(
            _exact_wire_object(
                value,
                f"band[{index}].source_refs[{ref_index}]",
                _ACCOUNT_SOURCE_REF_KEYS,
                "binance_usdm_account_profile_source_ref",
            )
            for ref_index, value in enumerate(
                _sequence(band.get("source_refs"), f"band[{index}].source_refs")
            )
        )
        by_kind: dict[str, Mapping[str, object]] = {}
        for ref in refs:
            kind = ref.get("source_kind")
            if type(kind) is not str:
                raise ValueError("account band source kinds must be text")
            by_kind[kind] = ref
        if len(refs) != 4 or tuple(sorted(by_kind)) != _ACCOUNT_SOURCE_KINDS:
            raise ValueError("account band source refs must exact-cover four kinds")
        if not _canonical_equal(
            refs,
            tuple(
                sorted(
                    refs,
                    key=lambda ref: (
                        ref["source_kind"],
                        ref["source_key"],
                        ref["revision_id"],
                    ),
                )
            ),
        ):
            raise ValueError("account band source refs must be canonically sorted")
        for kind in _ACCOUNT_SOURCE_KINDS:
            ref = by_kind[kind]
            for key in ("source_key", "evidence_key", "revision_id"):
                _canonical_text(f"band[{index}].{kind}.{key}", ref.get(key))
            _canonical_hash(f"band[{index}].{kind}.source_hash", ref.get("source_hash"))
            supersedes = ref.get("supersedes_revision_id")
            prior = prior_sources.get(kind)
            if supersedes is not None:
                _canonical_text(f"band[{index}].{kind}.supersedes", supersedes)
            if (prior is None and supersedes is not None) or (
                prior is not None
                and not _canonical_equal(ref, prior)
                and (
                    ref.get("source_key") != prior.get("source_key")
                    or ref.get("revision_id") == prior.get("revision_id")
                    or supersedes != prior.get("revision_id")
                )
            ):
                raise ValueError("account band source revision chain mismatch")
            prior_sources[kind] = ref
        band_rows.append((band, start, end, available))

    expected_order = tuple(
        row[0]
        for row in sorted(
            band_rows,
            key=lambda row: (row[1], row[2], row[0]["band_id"]),
        )
    )
    if not _canonical_equal(bands, expected_order):
        raise ValueError("account profile bands must be canonically sorted")
    visible_rows = tuple(row for row in band_rows if row[3] <= captured_at)
    cursor = coverage_from
    for _, start, end, _ in visible_rows:
        if start != cursor:
            raise ValueError("account visible bands must exactly cover the book")
        cursor = end
    if cursor != coverage_to:
        raise ValueError("account visible bands must exactly cover the book")
    active_rows = tuple(row for row in visible_rows if row[1] <= evaluated_at < row[2])
    if len(active_rows) != 1:
        raise ValueError("account query must derive exactly one active band")
    active = active_rows[0][0]
    visible = _sequence(account.get("visible_bands"), "account_profile.visible_bands")
    if not _canonical_equal(
        visible, tuple(row[0] for row in visible_rows)
    ) or not _canonical_equal(account.get("active_band"), active):
        raise ValueError("account visible/active resolution is stale")

    instrument_resolution = _mapping(
        query.get("instrument_resolution"), "account query instrument resolution"
    )
    instrument_query = _mapping(
        instrument_resolution.get("query"), "account instrument resolution query"
    )
    listing = _mapping(
        instrument_resolution.get("listing_interval"), "account instrument listing"
    )
    listed_at = _wire_instant(listing.get("listed_at"), "account instrument listed_at")
    delisted = listing.get("delisted_at")
    if (
        _wire_instant(instrument_query.get("effective_at"), "instrument effective_at")
        != evaluated_at
        or _wire_instant(instrument_query.get("captured_at"), "instrument captured_at")
        > captured_at[0]
        or listed_at > evaluated_at
        or (
            delisted is not None
            and _wire_instant(delisted, "account instrument delisted_at")
            <= evaluated_at
        )
    ):
        raise ValueError("account instrument/query timing mismatch")

    expected_top = {
        "account_id": active["account_id"],
        "account_scope": active["scope"],
        "can_trade": active["can_trade"],
        "position_mode": "one_way",
        "asset_mode": "single_asset",
        "margin_type": active["margin_type"],
        "is_auto_add_margin": active["is_auto_add_margin"],
        "fee_burn": active["fee_burn"],
        "fee_tier": active["fee_tier"],
        "trade_group_id": active["trade_group_id"],
        "fee_scale": 8,
        "fee_reserve_funding_source": "available_margin",
        "limitations": _ACCOUNT_LIMITATIONS,
        "decision_grade_eligible": False,
    }
    if (
        any(
            not _canonical_equal(account.get(key), value)
            for key, value in expected_top.items()
        )
        or not _exact_bool(active.get("can_trade"), True)
        or not _exact_bool(active.get("dual_side_position"), False)
        or not _exact_bool(active.get("multi_assets_margin"), False)
        or active.get("margin_type") != "CROSSED"
        or not _exact_bool(active.get("is_auto_add_margin"), False)
        or not _exact_bool(active.get("fee_burn"), False)
        or active.get("scope") != "standard_um"
        or not _currency_is_usdt(account.get("reporting_currency_id"))
        or not _currency_is_usdt(account.get("fee_currency_id"))
    ):
        raise ValueError("account profile top fields do not derive from active band")

    leverage = _exact_wire_object(
        account.get("leverage_evidence"),
        "account_profile.leverage_evidence",
        _LEVERAGE_EVIDENCE_KEYS,
        "linear_margin_leverage_evidence",
    )
    symbol_ref = _mapping(
        next(
            ref
            for ref in _sequence(active.get("source_refs"), "active source refs")
            if _mapping(ref, "active source ref").get("source_kind") == "symbol_config"
        ),
        "active symbol source ref",
    )
    expected_leverage = {
        "type": "linear_margin_leverage_evidence",
        "schema_version": _SCHEMA_VERSION,
        "account_id": active["account_id"],
        "instrument_id": active["instrument_id"],
        "selected_leverage": {
            "type": "rate",
            "units": _whole_leverage(active.get("leverage"), "active leverage"),
            "scale": 0,
            "basis": "notional_per_initial_margin",
        },
        "effective_from": active["effective_from"],
        "effective_to_exclusive": active["effective_to_exclusive"],
        "available_at": active["available_at"],
        "source_key": symbol_ref["source_key"],
        "source_hash": symbol_ref["source_hash"],
    }
    if not _canonical_equal(leverage, expected_leverage):
        raise ValueError("account leverage evidence is stale")

    if account.get("query_hash") != canonical_sha256(query) or account.get(
        "resolution_hash"
    ) != canonical_sha256(
        {
            key: account[key]
            for key in account
            if key not in {"type", "schema_version", "resolution_hash"}
        }
    ):
        raise ValueError("account query/resolution hash mismatch")

    order_rules = _mapping(profile.get("order_rules"), "order_rules")
    order_band = _mapping(order_rules.get("active_band"), "order_rules.active_band")
    order_source = _exact_wire_object(
        order_band.get("source_ref"),
        "order_rules.active_band.source_ref",
        _ORDER_SOURCE_REF_KEYS,
        "binance_usdm_order_rule_source_ref",
    )
    for key in ("source_key",):
        _canonical_text(
            f"order_rules.active_band.source_ref.{key}", order_source.get(key)
        )
    _canonical_hash(
        "order_rules.active_band.source_ref.source_hash",
        order_source.get("source_hash"),
    )
    for key in ("evidence_key", "account_id", "source_key", "revision_id"):
        _canonical_text(f"account_capacity.{key}", capacity.get(key))
    _canonical_hash("account_capacity.source_hash", capacity.get("source_hash"))
    capacity_from = _wire_instant(
        capacity.get("effective_from"), "account_capacity.effective_from"
    )
    capacity_to = _wire_instant(
        capacity.get("effective_to_exclusive"),
        "account_capacity.effective_to_exclusive",
    )
    if (
        _exact_int(
            capacity.get("evidence_version"), "account_capacity.evidence_version"
        )
        <= 0
        or capacity_from >= capacity_to
        or _simulation_key(
            capacity.get("available_at"), "account_capacity.available_at"
        )
        > composed_at
        or capacity.get("account_id") != account_id
        or not _canonical_equal(capacity.get("instrument_id"), _INSTRUMENT_WIRE)
        or not _canonical_equal(order_band.get("instrument_id"), _INSTRUMENT_WIRE)
        or not _canonical_equal(
            capacity.get("effective_from"), active.get("effective_from")
        )
        or not _canonical_equal(
            capacity.get("effective_to_exclusive"), active.get("effective_to_exclusive")
        )
        or not _canonical_equal(
            capacity.get("effective_from"), order_band.get("effective_from")
        )
        or not _canonical_equal(
            capacity.get("effective_to_exclusive"),
            order_band.get("effective_to_exclusive"),
        )
        or capacity.get("source_key") != order_source.get("source_key")
        or capacity.get("source_hash") != order_source.get("source_hash")
        or any(
            _exact_int(capacity.get(key), f"account_capacity.{key}") <= 0
            for key in ("max_num_orders", "max_num_algo_orders")
        )
    ):
        raise ValueError("account capacity authority mismatch")
    _validate_fee_authority(account, active)


def _validate_price_authority(
    profile: Mapping[str, object], start: int, end: int
) -> tuple[Mapping[str, object], ...]:
    prices = tuple(
        _exact_wire_object(
            value,
            f"price_purposes[{index}]",
            _PRICE_RESOLUTION_KEYS,
            "binance_usdm_price_purpose_resolution",
        )
        for index, value in enumerate(
            _sequence(profile.get("price_purposes"), "price_purposes")
        )
    )
    by_purpose: dict[str, Mapping[str, object]] = {}
    for index, resolution in enumerate(prices):
        _canonical_text(
            f"price_purposes[{index}].model_key", resolution.get("model_key")
        )
        _canonical_hash(
            f"price_purposes[{index}].model_digest", resolution.get("model_digest")
        )
        if (
            _exact_int(
                resolution.get("model_version"),
                f"price_purposes[{index}].model_version",
            )
            <= 0
            or type(resolution.get("decision_grade_eligible")) is not bool
        ):
            raise ValueError("price purpose resolution field type mismatch")
        _sequence(resolution.get("limitations"), "price purpose limitations")
        query = _exact_wire_object(
            resolution.get("query"),
            f"price_purposes[{index}].query",
            _PRICE_QUERY_KEYS,
            "binance_usdm_price_purpose_query",
        )
        purpose = query.get("price_purpose")
        if type(purpose) is not str or purpose in by_purpose:
            raise ValueError("price purpose resolutions must have unique identities")
        by_purpose[purpose] = resolution

    if (
        tuple(sorted(by_purpose)) != tuple(sorted(_BOUND_PRICE_PURPOSES))
        or len(
            {
                (
                    resolution.get("model_key"),
                    resolution.get("model_version"),
                    resolution.get("model_digest"),
                    canonical_sha256(resolution.get("limitations")),
                    resolution.get("decision_grade_eligible"),
                )
                for resolution in prices
            }
        )
        != 1
    ):
        raise ValueError(
            "profile price purposes must exact-cover one model and four purposes"
        )

    bindings: list[Mapping[str, object]] = []
    for purpose in _BOUND_PRICE_PURPOSES:
        resolution = by_purpose[purpose]
        query = _exact_wire_object(
            resolution.get("query"),
            f"{purpose} query",
            _PRICE_QUERY_KEYS,
            "binance_usdm_price_purpose_query",
        )
        metadata = _mapping(query.get("instrument_metadata"), f"{purpose} metadata")
        instrument = _mapping(metadata.get("instrument"), f"{purpose} instrument")
        book = _exact_wire_object(
            query.get("price_book"),
            f"{purpose} price book",
            _PRICE_BOOK_KEYS,
            "binance_usdm_historical_price_book",
        )
        if (
            query.get("price_purpose") != purpose
            or not _canonical_equal(instrument.get("instrument_id"), _INSTRUMENT_WIRE)
            or not _canonical_equal(book.get("instrument_id"), _INSTRUMENT_WIRE)
            or not _currency_is_usdt(book.get("quote_currency_id"))
            or _exact_int(book.get("price_book_version"), f"{purpose} book version")
            <= 0
        ):
            raise ValueError("price purpose query identity mismatch")
        _canonical_text(f"{purpose} price_book_key", book.get("price_book_key"))
        _wire_instant(query.get("requested_at"), f"{purpose} requested_at")
        if _simulation_key(
            query.get("captured_at"), f"{purpose} captured_at"
        ) > _simulation_key(profile.get("composed_at"), "profile composed_at"):
            raise ValueError("price purpose query is unavailable at composition")
        for key in (
            "liquidation_interval_start",
            "liquidation_interval_end_exclusive",
        ):
            if query.get(key) is not None:
                _wire_instant(query.get(key), f"{purpose}.{key}")

        coverages = tuple(
            _exact_wire_object(
                value,
                f"{purpose} price book coverage[{coverage_index}]",
                _PRICE_COVERAGE_KEYS,
                "binance_usdm_price_stream_coverage",
            )
            for coverage_index, value in enumerate(
                _sequence(book.get("coverages"), f"{purpose} price book coverages")
            )
        )
        expected_kind = _PRICE_PURPOSE_SOURCE_KINDS[purpose]
        derived = tuple(
            coverage
            for coverage in coverages
            if coverage.get("price_purpose") == purpose
            and coverage.get("source_kind") == expected_kind
        )
        active = _sequence(
            resolution.get("active_coverages"), f"{purpose} active_coverages"
        )
        if len(derived) != 1 or not _canonical_equal(active, derived):
            raise ValueError("price purpose active coverage resolution is stale")
        coverage = derived[0]
        source_ref = _exact_wire_object(
            coverage.get("source_ref"),
            f"{purpose} coverage source_ref",
            _PRICE_SOURCE_REF_KEYS,
            "binance_usdm_price_source_ref",
        )
        for key in ("source_key", "archive_key", "revision_id"):
            _canonical_text(f"{purpose} source_ref.{key}", source_ref.get(key))
        _canonical_hash(
            f"{purpose} source_ref.source_hash", source_ref.get("source_hash")
        )
        supersedes = source_ref.get("supersedes_revision_id")
        if supersedes is not None:
            _canonical_text(f"{purpose} source_ref.supersedes", supersedes)
            if supersedes == source_ref.get("revision_id"):
                raise ValueError("price source revision cannot supersede itself")
        coverage_from = _wire_instant(
            coverage.get("coverage_from"), f"{purpose} coverage_from"
        )
        coverage_to = _wire_instant(
            coverage.get("coverage_to_exclusive"), f"{purpose} coverage_to_exclusive"
        )
        requested_at = _wire_instant(
            query.get("requested_at"), f"{purpose} requested_at"
        )
        records_key = (
            "aggregate_trades"
            if purpose == "execution_reference"
            else "mark_price_klines"
        )
        visible_records = tuple(
            record
            for record in _sequence(book.get(records_key), f"{purpose} source records")
            if _simulation_key(
                _mapping(record, f"{purpose} source record").get("available_at"),
                f"{purpose} source record available_at",
            )
            <= _simulation_key(query.get("captured_at"), f"{purpose} captured_at")
        )
        if not _canonical_equal(
            resolution.get("visible_source_records"), visible_records
        ):
            raise ValueError("price purpose visible source resolution is stale")
        if purpose == "liquidation":
            interval_start = _wire_instant(
                query.get("liquidation_interval_start"),
                "liquidation interval start",
            )
            interval_end = _wire_instant(
                query.get("liquidation_interval_end_exclusive"),
                "liquidation interval end",
            )
            bars = tuple(
                _mapping(value, "liquidation bar")
                for value in _sequence(
                    resolution.get("liquidation_bars"), "liquidation bars"
                )
            )
            if (
                not bars
                or interval_start >= interval_end
                or _wire_instant(bars[0].get("interval_start"), "first bar start")
                != interval_start
                or _wire_instant(bars[-1].get("interval_end_exclusive"), "last bar end")
                != interval_end
                or any(
                    bar.get("price_purpose") != purpose
                    or bar.get("stream_id") != coverage.get("stream_id")
                    for bar in bars
                )
            ):
                raise ValueError("liquidation resolution is stale")
        else:
            resolved = _mapping(
                resolution.get("resolved_mark"), f"{purpose} resolved mark"
            )
            if (
                _wire_instant(resolved.get("resolved_at"), f"{purpose} resolved_at")
                != requested_at
                or resolved.get("price_purpose") != purpose
                or resolved.get("stream_id") != coverage.get("stream_id")
                or resolved.get("revision_id") != source_ref.get("revision_id")
                or resolution.get("liquidation_bars") not in ((), [])
            ):
                raise ValueError("point price resolution is stale")
        if (
            coverage.get("price_purpose") != purpose
            or coverage.get("source_kind") != expected_kind
            or not _canonical_equal(coverage.get("instrument_id"), _INSTRUMENT_WIRE)
            or coverage_from > start
            or coverage_to < end
            or coverage_from >= coverage_to
            or not coverage_from <= requested_at < coverage_to
        ):
            raise ValueError("bound price purpose coverage mismatch")
        bindings.append(
            MappingProxyType(
                {
                    "price_purpose": purpose,
                    "source_kind": expected_kind,
                    "stream_id": _canonical_text(
                        f"{purpose} coverage stream_id", coverage.get("stream_id")
                    ),
                    "source_ref": source_ref,
                    "coverage_from": coverage["coverage_from"],
                    "coverage_to_exclusive": coverage["coverage_to_exclusive"],
                    "coverage_hash": canonical_sha256(coverage),
                    "price_resolution_hash": canonical_sha256(resolution),
                }
            )
        )
    return tuple(bindings)


def _validate_profile_wire(
    wire: object,
    request_hash: str,
    source: BinanceUsdmKoruTradifiSourceProjectionResultV1,
    account_id: str,
) -> tuple[Mapping[str, object], tuple[Mapping[str, object], ...]]:
    profile = _mapping(wire, "profile composition request wire")
    if (
        set(profile) != _PROFILE_REQUEST_KEYS
        or profile.get("type") != _PROFILE_REQUEST_TYPE
        or type(profile.get("schema_version")) is not int
        or profile.get("schema_version") != _SCHEMA_VERSION
        or not _canonical_equal(
            profile.get("required_market_state_keys"), ("normal",)
        )
        or canonical_sha256(profile) != request_hash
    ):
        raise ValueError("profile composition request wire/hash mismatch")

    expected_refs = (
        _wire_ref(source.xkrx_calendar_ref),
        _wire_ref(source.arcx_calendar_ref),
    )
    calendar_refs = _sequence(profile.get("calendar_refs"), "calendar_refs")
    if not _canonical_equal(calendar_refs, expected_refs) or not _canonical_equal(
        profile.get("post_adjustment_unit_regime_ref"),
        _wire_ref(source.post_adjustment_unit_regime_ref),
    ):
        raise ValueError(
            "profile authority refs do not match accepted source authority"
        )

    timeline = _mapping(profile.get("timeline_window"), "timeline_window")
    start = source.request.timeline_window_start.epoch_nanoseconds
    end = source.request.timeline_window_end_exclusive.epoch_nanoseconds
    if (
        set(timeline) != {"type", "data_start", "trading_start", "end_exclusive"}
        or timeline.get("type") != "timeline_window"
        or _wire_instant(timeline.get("data_start"), "timeline_window.data_start")
        != start
        or _wire_instant(timeline.get("trading_start"), "timeline_window.trading_start")
        != start
        or _wire_instant(timeline.get("end_exclusive"), "timeline_window.end_exclusive")
        != end
    ):
        raise ValueError("profile timeline does not match accepted source window")

    metadata = _mapping(profile.get("instrument_metadata"), "instrument_metadata")
    instrument = _mapping(metadata.get("instrument"), "instrument_metadata.instrument")
    if not _canonical_equal(instrument.get("instrument_id"), _INSTRUMENT_WIRE):
        raise ValueError("profile instrument does not match KORU authority")

    price_bindings = _validate_price_authority(profile, start, end)
    _validate_account_authority(profile, account_id)
    return profile, price_bindings


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiExecutionBundleRequestV1:
    source_projection: BinanceUsdmKoruTradifiSourceProjectionResultV1
    target_result: BinanceUsdmKoruClosedMarketRangeTargetsResultV1
    profile_composition_request_wire: Mapping[str, object]
    profile_composition_request_hash: str
    execution_account_id: str
    initial_equity: Money
    sleeve_allocation_fraction: str
    _price_purpose_bindings: tuple[Mapping[str, object], ...] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        source = _trusted_source_result(self.source_projection)
        target = _trusted_target_result(self.target_result)
        if source is None:
            raise ValueError("source_projection must be an exact accepted result")
        if target is None:
            raise ValueError("target_result must be an exact accepted result")
        if not _canonical_equal(target.request.source_projection, source):
            raise ValueError(
                "target result must be generated from the accepted source fragment"
            )
        request_hash = _canonical_hash(
            "profile_composition_request_hash", self.profile_composition_request_hash
        )
        account_id = _canonical_text("execution_account_id", self.execution_account_id)
        if (
            type(self.initial_equity) is not Money
            or self.initial_equity != _REQUIRED_EQUITY
        ):
            raise ValueError("initial_equity must be exact 10000 USDT at scale 8")
        if (
            type(self.sleeve_allocation_fraction) is not str
            or self.sleeve_allocation_fraction != _REQUIRED_ALLOCATION
        ):
            raise ValueError(
                "sleeve_allocation_fraction must be exact full allocation 1"
            )
        frozen_wire = _freeze_json(self.profile_composition_request_wire)
        profile, price_bindings = _validate_profile_wire(
            frozen_wire, request_hash, source, account_id
        )
        object.__setattr__(self, "source_projection", source)
        object.__setattr__(self, "target_result", target)
        object.__setattr__(self, "profile_composition_request_wire", profile)
        object.__setattr__(self, "_price_purpose_bindings", price_bindings)

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    @property
    def bundle_key(self) -> str:
        digest = canonical_sha256(
            {
                "type": "binance_usdm_koru_tradifi_execution_bundle_key_v1",
                "source_fragment_digest": self.source_projection.fragment_digest,
                "target_result_digest": self.target_result.result_digest,
                "profile_composition_request_hash": self.profile_composition_request_hash,
                "execution_account_id": self.execution_account_id,
                "initial_equity": self.initial_equity,
                "sleeve_allocation_fraction": self.sleeve_allocation_fraction,
            }
        )
        return "binance-usdm-koru-tradifi-execution-development-v1-" + digest[7:]

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_tradifi_execution_bundle_request_v1",
            "schema_version": _SCHEMA_VERSION,
            "source_projection": self.source_projection,
            "source_fragment_digest": self.source_projection.fragment_digest,
            "target_result": self.target_result,
            "target_result_digest": self.target_result.result_digest,
            "profile_composition_request_wire": self.profile_composition_request_wire,
            "profile_composition_request_hash": self.profile_composition_request_hash,
            "execution_account_id": self.execution_account_id,
            "initial_equity": self.initial_equity,
            "sleeve_allocation_fraction": self.sleeve_allocation_fraction,
            "bundle_key": self.bundle_key,
            "bundle_schema_version": _SCHEMA_VERSION,
            "development_only": True,
        }


class BinanceUsdmKoruTradifiExecutionBundleFailureCodeV1(str, Enum):
    INVALID_REQUEST = "invalid_request"
    SOURCE_FRAGMENT_INVALID = "source_fragment_invalid"
    TARGET_RESULT_INVALID = "target_result_invalid"
    PROFILE_REQUEST_INVALID = "profile_request_invalid"
    AUTHORITY_ASSEMBLY_INVALID = "authority_assembly_invalid"
    STREAM_ASSEMBLY_INVALID = "stream_assembly_invalid"
    RESULT_INVALID = "result_invalid"


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiExecutionBundleFailureV1:
    code: BinanceUsdmKoruTradifiExecutionBundleFailureCodeV1
    subject: str

    def __post_init__(self) -> None:
        if type(self.code) is not BinanceUsdmKoruTradifiExecutionBundleFailureCodeV1:
            raise TypeError("code must be exact execution-bundle failure code")
        _canonical_text("subject", self.subject)

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_tradifi_execution_bundle_failure_v1",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
        }


def _source_snapshot_bindings(
    source: BinanceUsdmKoruTradifiSourceProjectionResultV1,
) -> tuple[dict[str, object], ...]:
    bindings: list[dict[str, object]] = []
    groups = (
        ("aggregate_trades", source.request.aggregate_trade_results),
        ("mark_price", source.request.mark_price_results),
        ("index_price", source.request.index_price_results),
        ("funding_history", (source.request.funding_result,)),
    )
    for source_kind, results in groups:
        for result in results:
            bindings.append(
                {
                    "source_kind": source_kind,
                    "source_snapshot_id": result.source_snapshot_id,
                    "source_snapshot_hash": result.source_snapshot_hash,
                    "source_normalization_hash": result.normalization_hash,
                }
            )
    authority = source.request.authority_result
    snapshot = authority.source_snapshot
    bindings.append(
        {
            "source_kind": "calendar_unit",
            "source_snapshot_id": snapshot.snapshot_id,
            "source_snapshot_hash": canonical_sha256(snapshot.to_canonical_dict()),
            "source_normalization_hash": canonical_sha256(authority),
        }
    )
    return tuple(
        sorted(
            bindings,
            key=lambda value: (
                _canonical_text("source_kind", value["source_kind"]),
                _canonical_text("source_snapshot_id", value["source_snapshot_id"]),
                _canonical_text(
                    "source_normalization_hash", value["source_normalization_hash"]
                ),
            ),
        )
    )


def _parameter_target_bindings(
    target: BinanceUsdmKoruClosedMarketRangeTargetsResultV1,
) -> tuple[dict[str, object], ...]:
    if len(target.parameters) != 8 or len(target.streams) != 8:
        raise ValueError("target result must exact-cover eight parameters and streams")
    by_ref = {stream.parameter_ref: stream for stream in target.streams}
    if len(by_ref) != 8:
        raise ValueError("target parameter-to-stream binding is not bijective")
    bindings = []
    for parameter in target.parameters:
        stream = by_ref.get(parameter.ref)
        if stream is None:
            raise ValueError("target parameter has no exact stream")
        bindings.append(
            {
                "parameter_id": parameter.parameter_id,
                "parameter_ref": parameter.ref.to_canonical_dict(),
                "target_stream_key": stream.stream_key,
                "target_stream_digest": stream.target_stream_digest,
            }
        )
    return tuple(sorted(bindings, key=lambda value: value["parameter_id"]))


def _price_purpose_payload(
    request: BinanceUsdmKoruTradifiExecutionBundleRequestV1,
) -> dict[str, object]:
    manifests = {
        manifest.stream_key: manifest
        for manifest in request.source_projection.stream_manifests
    }
    if len(manifests) != len(request.source_projection.stream_manifests):
        raise ValueError("accepted source manifests must have disjoint stream keys")
    bindings = []
    bound_keys: set[str] = set()
    if (
        tuple(
            binding.get("price_purpose") for binding in request._price_purpose_bindings
        )
        != _BOUND_PRICE_PURPOSES
    ):
        raise ValueError("validated profile price bindings are incomplete")
    for profile_binding in request._price_purpose_bindings:
        purpose = profile_binding["price_purpose"]
        if type(purpose) is not str:
            raise ValueError("validated profile purpose must be text")
        stream_key = _PRICE_PURPOSE_SOURCE_STREAMS[purpose]
        manifest = manifests.get(stream_key)
        if manifest is None or stream_key in bound_keys:
            raise ValueError("price purpose source manifest binding is incomplete")
        bound_keys.add(stream_key)
        bindings.append(
            {
                **profile_binding,
                "source_stream_manifest": {
                    "stream_key": manifest.stream_key,
                    "event_type": manifest.event_type,
                    "original_capability": manifest.capability.to_canonical_dict(),
                    "event_count": manifest.event_count,
                    "content_hash": manifest.content_hash,
                },
            }
        )
    if (
        tuple(value["price_purpose"] for value in bindings) != _BOUND_PRICE_PURPOSES
        or len(bound_keys) != 4
    ):
        raise ValueError("price purpose authority must exact-cover four purposes")
    return {
        "schema_version": _SCHEMA_VERSION,
        "instrument_id": _INSTRUMENT_WIRE,
        "price_purpose_bindings": tuple(bindings),
        "source_fragment_digest": request.source_projection.fragment_digest,
        "profile_composition_request_hash": request.profile_composition_request_hash,
    }


def _price_purpose_authority_binding(event: MarketEvent) -> dict[str, object]:
    return {
        "stream_key": event.stream_key,
        "event_type": event.event_type,
        "event_id": event.event_id,
        "event_hash": canonical_sha256(event),
    }


def _preparation_payload(
    request: BinanceUsdmKoruTradifiExecutionBundleRequestV1,
    price_purpose: MarketEvent,
) -> dict[str, object]:
    source = request.source_projection
    target = request.target_result
    return {
        "schema_version": _SCHEMA_VERSION,
        "profile_composition_request_wire": request.profile_composition_request_wire,
        "profile_composition_request_hash": request.profile_composition_request_hash,
        "strategy_definition_ref": target.strategy.ref.to_canonical_dict(),
        "parameter_target_bindings": _parameter_target_bindings(target),
        "xkrx_calendar_ref": source.xkrx_calendar_ref.to_canonical_dict(),
        "arcx_calendar_ref": source.arcx_calendar_ref.to_canonical_dict(),
        "post_adjustment_unit_regime_ref": source.post_adjustment_unit_regime_ref.to_canonical_dict(),
        "source_snapshot_bindings": _source_snapshot_bindings(source),
        "source_fragment_digest": source.fragment_digest,
        "target_result_digest": target.result_digest,
        "price_purpose_authority_binding": _price_purpose_authority_binding(
            price_purpose
        ),
        "required_initial_equity": request.initial_equity.to_canonical_dict(),
        "required_sleeve_allocation_fraction": request.sleeve_allocation_fraction,
        "required_position_notional_usdt": _REQUIRED_POSITION_NOTIONAL,
        "source_limitations": _SOURCE_LIMITATIONS,
    }


def _event(
    *,
    stream_key: str,
    event_type: str,
    capability: MarketBundleCapability,
    instrument_id: InstrumentId | None,
    instant: UtcInstant,
    phase: TimelinePhase,
    payload: dict[str, object],
) -> MarketEvent:
    source_hash = canonical_sha256(
        {
            "type": event_type + "_source_v1",
            "stream_key": stream_key,
            "payload": payload,
        }
    )
    return MarketEvent(
        event_id=event_type + ":" + source_hash,
        stream_key=stream_key,
        event_type=event_type,
        capability=capability,
        instrument_id=instrument_id,
        event_time=instant,
        available_time=instant,
        phase=phase,
        source_sequence=SourceSequence(0),
        revision_id=canonical_sha256(
            {"type": event_type + "_revision_v1", "source_hash": source_hash}
        ),
        supersedes_revision_id=None,
        source_key=stream_key,
        source_hash=source_hash,
        payload=payload,
    )


def _authority_events(
    request: BinanceUsdmKoruTradifiExecutionBundleRequestV1,
) -> tuple[MarketEvent, MarketEvent, MarketEvent]:
    start = request.source_projection.request.timeline_window_start
    price_purpose = _event(
        stream_key=_PRICE_PURPOSE_STREAM,
        event_type=_PRICE_PURPOSE_EVENT_TYPE,
        capability=_PRICE_PURPOSE_CAPABILITY,
        instrument_id=_INSTRUMENT,
        instant=start,
        phase=TimelinePhase(0, "market_data"),
        payload=_price_purpose_payload(request),
    )
    preparation = _event(
        stream_key=_PREPARATION_STREAM,
        event_type=_PREPARATION_EVENT_TYPE,
        capability=_PREPARATION_CAPABILITY,
        instrument_id=None,
        instant=start,
        phase=TimelinePhase(0, "market_data"),
        payload=_preparation_payload(request, price_purpose),
    )
    strategy_ref = request.target_result.strategy.ref
    account = _event(
        stream_key=_ACCOUNT_STREAM,
        event_type=_ACCOUNT_EVENT_TYPE,
        capability=_ACCOUNT_CAPABILITY,
        instrument_id=_INSTRUMENT,
        instant=start,
        phase=TimelinePhase(110, "account_financial_dispatch"),
        payload={
            "schema_version": _SCHEMA_VERSION,
            "account_id": request.execution_account_id,
            "initial_equity": request.initial_equity.to_canonical_dict(),
            "sleeve_allocation_fraction": request.sleeve_allocation_fraction,
            "position_notional_usdt": _REQUIRED_POSITION_NOTIONAL,
            "profile_composition_request_hash": request.profile_composition_request_hash,
            "strategy_definition_ref": strategy_ref.to_canonical_dict(),
            "strategy_definition_hash": strategy_ref.content_hash,
            "operation_authorized": False,
            "order_authorized": False,
            "deployment_authorized": False,
        },
    )
    return preparation, price_purpose, account


def _accepted_streams(
    request: BinanceUsdmKoruTradifiExecutionBundleRequestV1,
    preparation: MarketEvent,
    price_purpose: MarketEvent,
    account: MarketEvent,
) -> tuple[dict[str, tuple[MarketEvent, ...]], tuple[MarketStreamManifest, ...]]:
    source = request.source_projection
    grouped: dict[str, list[MarketEvent]] = defaultdict(list)
    for event in (*source.source_events, *source.projection_events):
        grouped[event.stream_key].append(event)
    streams: dict[str, tuple[MarketEvent, ...]] = {
        manifest.stream_key: tuple(grouped.get(manifest.stream_key, ()))
        for manifest in source.stream_manifests
    }
    manifests = list(source.stream_manifests)
    funding_events = source.request.funding_result.events
    funding_identities = {
        (event.stream_key, event.event_type, event.capability)
        for event in funding_events
    }
    if len(funding_identities) != 1:
        raise ValueError("accepted funding authority must have one stream identity")
    funding_key, funding_type, funding_capability = next(iter(funding_identities))
    if funding_key not in streams:
        streams[funding_key] = ()
        manifests.append(
            MarketStreamManifest(
                funding_key,
                funding_type,
                funding_capability,
                0,
                canonical_sha256(()),
            )
        )
    for target_stream in request.target_result.streams:
        if target_stream.stream_key in streams:
            raise ValueError("target stream collides with accepted source stream")
        streams[target_stream.stream_key] = target_stream.events
        manifests.append(target_stream.manifest)
    for event in (preparation, price_purpose, account):
        if event.stream_key in streams:
            raise ValueError("authority stream collides with accepted stream")
        streams[event.stream_key] = (event,)
        manifests.append(MarketStreamManifest.from_events(event.stream_key, (event,)))

    if len({event.event_id for events in streams.values() for event in events}) != sum(
        len(events) for events in streams.values()
    ):
        raise ValueError("bundle event IDs must be globally unique")
    for manifest in manifests:
        events = streams[manifest.stream_key]
        if len({event.ordering_key for event in events}) != len(events):
            raise ValueError("stream ordering keys must be unique")
        expected = (
            MarketStreamManifest.from_events(manifest.stream_key, events)
            if events
            else MarketStreamManifest(
                manifest.stream_key,
                manifest.event_type,
                manifest.capability,
                0,
                canonical_sha256(()),
            )
        )
        if not _canonical_equal(manifest, expected):
            raise ValueError("accepted stream manifest does not match exact events")
    return streams, tuple(manifests)


@dataclass(frozen=True, slots=True)
class _Assembled:
    preparation_authority_event: MarketEvent
    price_purpose_authority_event: MarketEvent
    account_authority_event: MarketEvent
    streams: Mapping[str, tuple[MarketEvent, ...]]
    events: tuple[MarketEvent, ...]
    manifest: MarketBundleManifest
    bundle_ref: MarketBundleRef
    reader: InMemoryMarketBundleReader


def _assemble(request: BinanceUsdmKoruTradifiExecutionBundleRequestV1) -> _Assembled:
    preparation, price_purpose, account = _authority_events(request)
    streams, stream_manifests = _accepted_streams(
        request, preparation, price_purpose, account
    )
    capabilities = tuple(sorted({manifest.capability for manifest in stream_manifests}))
    source_request = request.source_projection.request
    manifest = MarketBundleManifest.build(
        bundle_key=request.bundle_key,
        schema_version=_SCHEMA_VERSION,
        coverage_start=source_request.timeline_window_start,
        coverage_end_exclusive=source_request.timeline_window_end_exclusive,
        instrument_catalog_hash=source_request.instrument_catalog_hash,
        capabilities=capabilities,
        streams=stream_manifests,
    )
    bundle_ref = MarketBundleRef.from_manifest(manifest)
    reader = InMemoryMarketBundleReader(bundle_ref, manifest, streams)
    events = tuple(
        event
        for stream_key in sorted(reader.streams)
        for event in reader.streams[stream_key]
    )
    return _Assembled(
        preparation,
        price_purpose,
        account,
        reader.streams,
        events,
        manifest,
        bundle_ref,
        reader,
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiExecutionBundleResultV1:
    request: BinanceUsdmKoruTradifiExecutionBundleRequestV1
    preparation_authority_event: MarketEvent
    price_purpose_authority_event: MarketEvent
    account_authority_event: MarketEvent
    manifest: MarketBundleManifest
    bundle_ref: MarketBundleRef
    reader: InMemoryMarketBundleReader
    events: tuple[MarketEvent, ...]
    development_only: bool = True
    deployment_authorized: bool = False
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        trusted_request = _trusted_request(self.request)
        if trusted_request is None:
            raise TypeError("request must be exact execution-bundle request")
        assembled = _assemble(trusted_request)
        if (
            type(self.preparation_authority_event) is not MarketEvent
            or not _canonical_equal(
                self.preparation_authority_event, assembled.preparation_authority_event
            )
            or type(self.price_purpose_authority_event) is not MarketEvent
            or not _canonical_equal(
                self.price_purpose_authority_event,
                assembled.price_purpose_authority_event,
            )
            or type(self.account_authority_event) is not MarketEvent
            or not _canonical_equal(
                self.account_authority_event, assembled.account_authority_event
            )
            or type(self.manifest) is not MarketBundleManifest
            or not _canonical_equal(self.manifest, assembled.manifest)
            or type(self.bundle_ref) is not MarketBundleRef
            or self.bundle_ref != assembled.bundle_ref
            or type(self.reader) is not InMemoryMarketBundleReader
            or self.reader.bundle_ref != assembled.reader.bundle_ref
            or not _canonical_equal(self.reader.manifest, assembled.reader.manifest)
            or not _canonical_equal(self.reader.streams, assembled.reader.streams)
            or type(self.events) is not tuple
            or not _canonical_equal(self.events, assembled.events)
            or type(self.development_only) is not bool
            or not self.development_only
            or type(self.deployment_authorized) is not bool
            or self.deployment_authorized
        ):
            raise ValueError("execution-bundle result binding mismatch")
        object.__setattr__(self, "request", trusted_request)
        object.__setattr__(self, "result_digest", canonical_sha256(self._body()))

    @property
    def source_projection(self) -> BinanceUsdmKoruTradifiSourceProjectionResultV1:
        return self.request.source_projection

    @property
    def target_result(self) -> BinanceUsdmKoruClosedMarketRangeTargetsResultV1:
        return self.request.target_result

    @property
    def authority_artifacts(self) -> tuple[ArtifactEnvelope, ...]:
        source = self.request.source_projection
        return (
            source.xkrx_calendar,
            source.arcx_calendar,
            source.post_adjustment_unit_regime,
        )

    @property
    def authority_refs(self) -> tuple[ArtifactRef, ...]:
        source = self.request.source_projection
        return (
            source.xkrx_calendar_ref,
            source.arcx_calendar_ref,
            source.post_adjustment_unit_regime_ref,
        )

    @property
    def strategy(self) -> BinanceUsdmKoruClosedMarketRangeStrategyArtifactBindingV1:
        return self.request.target_result.strategy

    @property
    def strategy_artifact(self) -> ArtifactEnvelope:
        return self.strategy.envelope

    @property
    def strategy_ref(self) -> ArtifactRef:
        return self.strategy.ref

    @property
    def parameters(
        self,
    ) -> tuple[BinanceUsdmKoruClosedMarketRangeParameterArtifactBindingV1, ...]:
        return self.request.target_result.parameters

    @property
    def parameter_artifacts(self) -> tuple[ArtifactEnvelope, ...]:
        return tuple(parameter.envelope for parameter in self.parameters)

    @property
    def parameter_refs(self) -> tuple[ArtifactRef, ...]:
        return tuple(parameter.ref for parameter in self.parameters)

    @property
    def preparation_authority_events(self) -> tuple[MarketEvent, ...]:
        return (self.preparation_authority_event,)

    @property
    def price_purpose_authority_events(self) -> tuple[MarketEvent, ...]:
        return (self.price_purpose_authority_event,)

    @property
    def account_events(self) -> tuple[MarketEvent, ...]:
        return (self.account_authority_event,)

    @property
    def streams(self) -> Mapping[str, tuple[MarketEvent, ...]]:
        return self.reader.streams

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_tradifi_execution_bundle_result_v1",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "authority_artifacts": self.authority_artifacts,
            "authority_refs": self.authority_refs,
            "strategy_artifact": self.strategy_artifact,
            "strategy_ref": self.strategy_ref,
            "parameter_artifacts": self.parameter_artifacts,
            "parameter_refs": self.parameter_refs,
            "preparation_authority_event": self.preparation_authority_event,
            "price_purpose_authority_event": self.price_purpose_authority_event,
            "account_authority_event": self.account_authority_event,
            "manifest": self.manifest,
            "bundle_ref": self.bundle_ref,
            "events": self.events,
            "development_only": self.development_only,
            "deployment_authorized": self.deployment_authorized,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "result_digest": self.result_digest}


def _trusted_result(
    value: object,
) -> BinanceUsdmKoruTradifiExecutionBundleResultV1 | None:
    if type(value) is not BinanceUsdmKoruTradifiExecutionBundleResultV1:
        return None
    try:
        rebuilt = BinanceUsdmKoruTradifiExecutionBundleResultV1(
            request=value.request,
            preparation_authority_event=value.preparation_authority_event,
            price_purpose_authority_event=value.price_purpose_authority_event,
            account_authority_event=value.account_authority_event,
            manifest=value.manifest,
            bundle_ref=value.bundle_ref,
            reader=value.reader,
            events=value.events,
            development_only=value.development_only,
            deployment_authorized=value.deployment_authorized,
        )
        if not _canonical_equal(
            rebuilt, value
        ) or value.result_digest != canonical_sha256(value._body()):
            return None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return rebuilt


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruTradifiExecutionBundleOutcomeV1:
    result: BinanceUsdmKoruTradifiExecutionBundleResultV1 | None = None
    failure: BinanceUsdmKoruTradifiExecutionBundleFailureV1 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")
        if self.result is not None and _trusted_result(self.result) is None:
            raise ValueError(
                "result must be an exact canonical execution-bundle result"
            )
        if (
            self.failure is not None
            and type(self.failure) is not BinanceUsdmKoruTradifiExecutionBundleFailureV1
        ):
            raise TypeError("failure must be exact execution-bundle failure")


def _failed(
    code: BinanceUsdmKoruTradifiExecutionBundleFailureCodeV1,
    subject: str,
) -> BinanceUsdmKoruTradifiExecutionBundleOutcomeV1:
    return BinanceUsdmKoruTradifiExecutionBundleOutcomeV1(
        failure=BinanceUsdmKoruTradifiExecutionBundleFailureV1(code, subject)
    )


def _trusted_request(
    value: object,
) -> BinanceUsdmKoruTradifiExecutionBundleRequestV1 | None:
    if type(value) is not BinanceUsdmKoruTradifiExecutionBundleRequestV1:
        return None
    try:
        rebuilt = BinanceUsdmKoruTradifiExecutionBundleRequestV1(
            source_projection=value.source_projection,
            target_result=value.target_result,
            profile_composition_request_wire=value.profile_composition_request_wire,
            profile_composition_request_hash=value.profile_composition_request_hash,
            execution_account_id=value.execution_account_id,
            initial_equity=value.initial_equity,
            sleeve_allocation_fraction=value.sleeve_allocation_fraction,
        )
        if not _canonical_equal(rebuilt, value):
            return None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return rebuilt


def build_binance_usdm_koru_tradifi_execution_bundle_v1(
    request: BinanceUsdmKoruTradifiExecutionBundleRequestV1,
) -> BinanceUsdmKoruTradifiExecutionBundleOutcomeV1:
    trusted = _trusted_request(request)
    if trusted is None:
        return _failed(
            BinanceUsdmKoruTradifiExecutionBundleFailureCodeV1.INVALID_REQUEST,
            "request",
        )
    try:
        assembled = _assemble(trusted)
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        return _failed(
            BinanceUsdmKoruTradifiExecutionBundleFailureCodeV1.STREAM_ASSEMBLY_INVALID,
            type(error).__name__,
        )
    try:
        result = BinanceUsdmKoruTradifiExecutionBundleResultV1(
            request=trusted,
            preparation_authority_event=assembled.preparation_authority_event,
            price_purpose_authority_event=assembled.price_purpose_authority_event,
            account_authority_event=assembled.account_authority_event,
            manifest=assembled.manifest,
            bundle_ref=assembled.bundle_ref,
            reader=assembled.reader,
            events=assembled.events,
        )
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        return _failed(
            BinanceUsdmKoruTradifiExecutionBundleFailureCodeV1.RESULT_INVALID,
            type(error).__name__,
        )
    return BinanceUsdmKoruTradifiExecutionBundleOutcomeV1(result=result)
