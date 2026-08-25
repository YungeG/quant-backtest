from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from functools import cache
from typing import Any, cast

import pytest
from crypto_quant_backtest import BinanceUsdmTradifiProfileComposer
from crypto_quant_bundle_builder.binance_usdm_koru_tradifi_execution_bundle_v1 import (
    BinanceUsdmKoruTradifiExecutionBundleOutcomeV1,
    BinanceUsdmKoruTradifiExecutionBundleRequestV1,
    _trusted_result,
    build_binance_usdm_koru_tradifi_execution_bundle_v1,
)
from crypto_quant_domain import Money, Scale, canonical_bytes, canonical_sha256
from crypto_quant_market_data import (
    EventCursor,
    MarketBundleCapability,
    MarketStreamManifest,
)
from crypto_quant_trading.profiles.binance_usdm.account_profile import (
    BinanceUsdmAccountProfileModel,
)

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_closed_market_range_targets_v1 as target_fixture,
)
from tests.runtime.profiles.binance_usdm._tradifi_fixtures import composition_request

_REQUIRED_EQUITY = Money(1_000_000_000_000, Scale(8), "USDT")


def _profile_wire(source, profile_request=None) -> dict[str, object]:
    wire = json.loads(canonical_bytes(profile_request or composition_request()))
    wire["calendar_refs"] = [
        source.xkrx_calendar_ref.to_canonical_dict(),
        source.arcx_calendar_ref.to_canonical_dict(),
    ]
    wire["post_adjustment_unit_regime_ref"] = (
        source.post_adjustment_unit_regime_ref.to_canonical_dict()
    )
    wire["timeline_window"] = {
        "type": "timeline_window",
        "data_start": source.request.timeline_window_start.to_canonical_dict(),
        "trading_start": source.request.timeline_window_start.to_canonical_dict(),
        "end_exclusive": source.request.timeline_window_end_exclusive.to_canonical_dict(),
    }
    start = source.request.timeline_window_start.epoch_nanoseconds
    end = source.request.timeline_window_end_exclusive.epoch_nanoseconds
    for resolution in cast(list[dict[str, Any]], wire["price_purposes"]):
        purpose = resolution["query"]["price_purpose"]
        book_coverages = resolution["query"]["price_book"]["coverages"]
        for coverages in (resolution["active_coverages"], book_coverages):
            coverage = next(
                value for value in coverages if value["price_purpose"] == purpose
            )
            coverage["coverage_from"]["epoch_nanoseconds"] = min(
                coverage["coverage_from"]["epoch_nanoseconds"], start
            )
            coverage["coverage_to_exclusive"]["epoch_nanoseconds"] = max(
                coverage["coverage_to_exclusive"]["epoch_nanoseconds"], end
            )
    return wire


def _request(source, target):
    wire = _profile_wire(source)
    return BinanceUsdmKoruTradifiExecutionBundleRequestV1(
        source_projection=source,
        target_result=target,
        profile_composition_request_wire=wire,
        profile_composition_request_hash=canonical_sha256(wire),
        execution_account_id="account-1",
        initial_equity=_REQUIRED_EQUITY,
        sleeve_allocation_fraction="1",
    )


def _build(source, target):
    outcome = build_binance_usdm_koru_tradifi_execution_bundle_v1(
        _request(source, target)
    )
    assert outcome.failure is None and outcome.result is not None
    return outcome.result


@cache
def _empty_result():
    return _build(target_fixture._base_fragment(), target_fixture._base_result())


@cache
def _nonempty_result():
    return _build(target_fixture._weekend_fragment(), target_fixture._weekend_result())


def test_final_bundle_exact_covers_source_targets_and_authority_streams() -> None:
    result = _empty_result()
    source = result.source_projection
    targets = result.target_result
    expected = {
        *(manifest.stream_key for manifest in source.stream_manifests),
        *(stream.stream_key for stream in targets.streams),
        "binance_usdm.funding_history.publications.koruusdt.v1",
        "binance_usdm.tradifi.preparation_authority.v1",
        "binance_usdm.tradifi.price_purpose.authority.koruusdt.v1",
        "binance_usdm.tradifi.account.authority.koruusdt.v1",
    }

    assert len(targets.streams) == 8
    assert set(result.streams) == expected
    assert {manifest.stream_key for manifest in result.manifest.streams} == expected
    assert set(result.manifest.capabilities) == {
        manifest.capability for manifest in result.manifest.streams
    }
    assert result.manifest.coverage_start == source.request.timeline_window_start
    assert (
        result.manifest.coverage_end_exclusive
        == source.request.timeline_window_end_exclusive
    )
    assert (
        result.manifest.instrument_catalog_hash
        == source.request.instrument_catalog_hash
    )
    profile_outcome = BinanceUsdmTradifiProfileComposer().compose(composition_request())
    assert profile_outcome.result is not None
    required_capabilities = (
        profile_outcome.result.market_registration.required_bundle_capabilities
    )
    assert required_capabilities == (
        MarketBundleCapability("account.financial-event", 1),
        MarketBundleCapability("bar_open", 1),
        MarketBundleCapability("binance_usdm.funding-publications", 1),
        MarketBundleCapability("binance_usdm.price-purpose-streams", 1),
    )
    assert (
        result.reader.validate_requirements(required_capabilities=required_capabilities)
        is None
    )


def test_price_purpose_authority_exact_binds_profile_and_source_manifests() -> None:
    result = _empty_result()
    event = result.price_purpose_authority_event
    payload = event.payload
    bindings = cast(tuple[Mapping[str, Any], ...], payload["price_purpose_bindings"])
    source_manifests = {
        manifest.stream_key: manifest
        for manifest in result.source_projection.stream_manifests
    }

    assert event.stream_key == (
        "binance_usdm.tradifi.price_purpose.authority.koruusdt.v1"
    )
    assert event.event_type == "binance_usdm_tradifi_price_purpose_binding_v1"
    assert event.capability == MarketBundleCapability(
        "binance_usdm.price-purpose-streams", 1
    )
    assert event.instrument_id is not None
    assert event.event_time == result.source_projection.request.timeline_window_start
    assert event.phase.rank == 0
    assert tuple(binding["price_purpose"] for binding in bindings) == (
        "execution_reference",
        "liquidation",
        "margin",
        "valuation",
    )
    keys = tuple(
        cast(Mapping[str, object], binding["source_stream_manifest"])["stream_key"]
        for binding in bindings
    )
    assert len(set(keys)) == 4
    profile_values = cast(
        tuple[Mapping[str, Any], ...],
        result.request.profile_composition_request_wire["price_purposes"],
    )
    profile_resolutions = {
        value["query"]["price_purpose"]: value for value in profile_values
    }
    for binding in bindings:
        purpose = cast(str, binding["price_purpose"])
        resolution = profile_resolutions[purpose]
        coverage = resolution["active_coverages"][0]
        assert binding["source_kind"] == coverage["source_kind"]
        assert binding["stream_id"] == coverage["stream_id"]
        assert binding["source_ref"] == coverage["source_ref"]
        assert binding["coverage_from"] == coverage["coverage_from"]
        assert binding["coverage_to_exclusive"] == coverage["coverage_to_exclusive"]
        assert binding["coverage_hash"] == canonical_sha256(coverage)
        assert binding["price_resolution_hash"] == canonical_sha256(resolution)
        manifest_wire = cast(Mapping[str, object], binding["source_stream_manifest"])
        manifest = source_manifests[cast(str, manifest_wire["stream_key"])]
        assert manifest_wire == {
            "stream_key": manifest.stream_key,
            "event_type": manifest.event_type,
            "original_capability": manifest.capability.to_canonical_dict(),
            "event_count": manifest.event_count,
            "content_hash": manifest.content_hash,
        }
    assert payload["source_fragment_digest"] == result.source_projection.fragment_digest
    assert (
        payload["profile_composition_request_hash"]
        == result.request.profile_composition_request_hash
    )
    assert result.preparation_authority_event.payload[
        "price_purpose_authority_binding"
    ] == {
        "stream_key": event.stream_key,
        "event_type": event.event_type,
        "event_id": event.event_id,
        "event_hash": canonical_sha256(event),
    }


def test_reader_retains_all_empty_target_streams_and_reads_nonempty_streams() -> None:
    empty = _empty_result()
    for target in empty.target_result.streams:
        cursor = empty.reader.open_cursor(target.stream_key, batch_size=2)
        assert isinstance(cursor, EventCursor) and cursor.exhausted
        assert target.events == ()
        assert target.manifest == MarketStreamManifest(
            target.stream_key,
            "strategy_decision_candidate",
            target.manifest.capability,
            0,
            canonical_sha256(()),
        )

    nonempty = _nonempty_result()
    target = next(stream for stream in nonempty.target_result.streams if stream.events)
    cursor = nonempty.reader.open_cursor(target.stream_key, batch_size=1)
    assert isinstance(cursor, EventCursor)
    batch, cursor = nonempty.reader.read_batch(cursor)
    assert batch == target.events[:1]
    assert cursor.position == 1


def test_source_and_target_event_bytes_are_unchanged() -> None:
    result = _nonempty_result()
    source = result.source_projection
    expected: dict[str, tuple[object, ...]] = {}
    for event in (*source.source_events, *source.projection_events):
        expected.setdefault(event.stream_key, ())
        expected[event.stream_key] = (*expected[event.stream_key], event)
    for stream in result.target_result.streams:
        expected[stream.stream_key] = stream.events

    assert {key: canonical_bytes(result.streams[key]) for key in expected} == {
        key: canonical_bytes(events) for key, events in expected.items()
    }


def test_preparation_authority_map_refs_and_source_bindings_are_exact() -> None:
    result = _empty_result()
    payload = result.preparation_authority_event.payload
    target = result.target_result
    bindings = cast(tuple[Mapping[str, Any], ...], payload["parameter_target_bindings"])

    assert result.preparation_authority_event.instrument_id is None
    assert result.preparation_authority_event.phase.rank == 0
    assert len(bindings) == 8
    assert tuple(row["parameter_id"] for row in bindings) == tuple(
        f"p{index:02d}" for index in range(1, 9)
    )
    assert {row["parameter_ref"]["content_hash"] for row in bindings} == {
        parameter.ref.content_hash for parameter in target.parameters
    }
    assert {row["target_stream_key"] for row in bindings} == {
        stream.stream_key for stream in target.streams
    }
    assert {row["target_stream_digest"] for row in bindings} == {
        stream.target_stream_digest for stream in target.streams
    }
    assert payload["xkrx_calendar_ref"] == result.authority_refs[0].to_canonical_dict()
    assert payload["arcx_calendar_ref"] == result.authority_refs[1].to_canonical_dict()
    assert (
        payload["post_adjustment_unit_regime_ref"]
        == result.authority_refs[2].to_canonical_dict()
    )
    source_bindings = cast(
        tuple[Mapping[str, Any], ...], payload["source_snapshot_bindings"]
    )
    assert source_bindings == tuple(
        sorted(
            source_bindings,
            key=lambda row: (
                row["source_kind"],
                row["source_snapshot_id"],
                row["source_normalization_hash"],
            ),
        )
    )
    assert {row["source_kind"] for row in source_bindings} == {
        "aggregate_trades",
        "mark_price",
        "index_price",
        "funding_history",
        "calendar_unit",
    }


def test_account_authority_is_exact_and_grants_no_operation_authority() -> None:
    result = _empty_result()
    event = result.account_authority_event
    payload = event.payload

    assert event.instrument_id is not None
    assert event.phase.rank == 110
    assert event.phase.code == "account_financial_dispatch"
    assert event.source_sequence.value == 0
    assert payload == {
        "schema_version": 1,
        "account_id": "account-1",
        "initial_equity": _REQUIRED_EQUITY.to_canonical_dict(),
        "sleeve_allocation_fraction": "1",
        "position_notional_usdt": "1000",
        "profile_composition_request_hash": result.request.profile_composition_request_hash,
        "strategy_definition_ref": result.strategy_ref.to_canonical_dict(),
        "strategy_definition_hash": result.strategy_ref.content_hash,
        "operation_authorized": False,
        "order_authorized": False,
        "deployment_authorized": False,
    }


def test_request_rejects_equity_allocation_account_profile_and_source_mismatches() -> (
    None
):
    source = target_fixture._base_fragment()
    target = target_fixture._base_result()
    request = _request(source, target)

    with pytest.raises(ValueError, match="10000 USDT"):
        replace(
            request,
            initial_equity=Money(999_900_000_000, Scale(8), "USDT"),
        )
    with pytest.raises(ValueError, match="full allocation"):
        replace(request, sleeve_allocation_fraction="0.5")
    with pytest.raises(ValueError, match="profile account"):
        replace(request, execution_account_id="account-2")
    with pytest.raises(ValueError, match="generated from"):
        _request(source, target_fixture._weekend_result())

    wire = _profile_wire(source)
    calendar_refs = cast(list[dict[str, object]], wire["calendar_refs"])
    calendar_refs[0]["content_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="authority refs"):
        BinanceUsdmKoruTradifiExecutionBundleRequestV1(
            source,
            target,
            wire,
            canonical_sha256(wire),
            "account-1",
            _REQUIRED_EQUITY,
            "1",
        )


def test_profile_wire_hash_and_json_boundary_fail_closed() -> None:
    source = target_fixture._base_fragment()
    target = target_fixture._base_result()
    wire = _profile_wire(source)
    with pytest.raises(ValueError, match="wire/hash"):
        BinanceUsdmKoruTradifiExecutionBundleRequestV1(
            source,
            target,
            wire,
            "sha256:" + "0" * 64,
            "account-1",
            _REQUIRED_EQUITY,
            "1",
        )
    wire["unexpected"] = None
    with pytest.raises(ValueError, match="wire/hash"):
        BinanceUsdmKoruTradifiExecutionBundleRequestV1(
            source,
            target,
            wire,
            canonical_sha256(wire),
            "account-1",
            _REQUIRED_EQUITY,
            "1",
        )
    wire = _profile_wire(source)
    valid_hash = canonical_sha256(wire)
    wire["required_market_state_keys"] = [1.0]
    with pytest.raises(TypeError, match="JSON values only"):
        BinanceUsdmKoruTradifiExecutionBundleRequestV1(
            source,
            target,
            wire,
            valid_hash,
            "account-1",
            _REQUIRED_EQUITY,
            "1",
        )


def _rehash_account_wire(wire: dict[str, object]) -> None:
    account = cast(dict[str, Any], wire["account_profile"])
    account["query_hash"] = canonical_sha256(account["query"])
    account["resolution_hash"] = canonical_sha256(
        {
            key: value
            for key, value in account.items()
            if key not in {"type", "schema_version", "resolution_hash"}
        }
    )


def _rehash_fee_config(rule_set: dict[str, Any], config_type: str) -> None:
    payload = {key: value for key, value in rule_set.items() if key != "config_hash"}
    payload["type"] = config_type
    rule_set["config_hash"] = canonical_sha256(payload)


def _assert_profile_wire_rejected(source, target, wire: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError), match=".+"):
        BinanceUsdmKoruTradifiExecutionBundleRequestV1(
            source,
            target,
            wire,
            canonical_sha256(wire),
            "account-1",
            _REQUIRED_EQUITY,
            "1",
        )


def test_profile_price_binding_reviewer_mutations_fail_closed() -> None:
    source = target_fixture._base_fragment()
    target = target_fixture._base_result()

    for mutation in ("stream_id", "source_ref", "bounds", "resolution", "query"):
        wire = _profile_wire(source)
        resolutions = cast(list[dict[str, Any]], wire["price_purposes"])
        resolution = next(
            value
            for value in resolutions
            if value["query"]["price_purpose"] == "margin"
        )
        coverage = resolution["active_coverages"][0]
        if mutation == "stream_id":
            coverage["stream_id"] = "mutated-margin-stream"
        elif mutation == "source_ref":
            coverage["source_ref"]["source_hash"] = "sha256:" + "0" * 64
        elif mutation == "bounds":
            coverage["coverage_from"]["epoch_nanoseconds"] += 1
        elif mutation == "resolution":
            resolution["model_key"] = "mutated-price-model"
        elif mutation == "query":
            resolution["query"]["requested_at"]["epoch_nanoseconds"] += 1

        with pytest.raises((TypeError, ValueError), match=".+"):
            BinanceUsdmKoruTradifiExecutionBundleRequestV1(
                source,
                target,
                wire,
                canonical_sha256(wire),
                "account-1",
                _REQUIRED_EQUITY,
                "1",
            )


def test_profile_account_wire_adversarial_mutations_fail_closed() -> None:
    source = target_fixture._base_fragment()
    target = target_fixture._base_result()

    for mutation in (
        "can_trade",
        "mode",
        "query",
        "book",
        "band",
        "account",
        "instrument",
        "resolution_hash",
        "query_hash",
        "config_hash",
        "taker",
        "capacity",
        "stale_source_refs",
        "stale_max_notional",
        "stale_book_band",
    ):
        wire = _profile_wire(source)
        account = cast(dict[str, Any], wire["account_profile"])
        query = cast(dict[str, Any], account["query"])
        book = cast(dict[str, Any], query["account_profile_book"])
        capacity = cast(dict[str, Any], wire["account_capacity"])
        rehash_account = True

        if mutation == "can_trade":
            account["can_trade"] = False
        elif mutation == "mode":
            account["position_mode"] = "hedge"
        elif mutation == "query":
            query["evaluated_at"]["epoch_nanoseconds"] = 0
        elif mutation == "book":
            book["coverage_to_exclusive"]["epoch_nanoseconds"] = 0
        elif mutation == "band":
            account["active_band"]["band_id"] = "foreign-band"
        elif mutation == "account":
            query["account_id"] = "account-2"
        elif mutation == "instrument":
            capacity["instrument_id"]["stable_key"] = "foreign"
        elif mutation == "resolution_hash":
            account["resolution_hash"] = "sha256:" + "0" * 64
            rehash_account = False
        elif mutation == "query_hash":
            account["query_hash"] = "sha256:" + "0" * 64
            rehash_account = False
        elif mutation == "config_hash":
            account["final_fee_rule_set"]["config_hash"] = "sha256:" + "0" * 64
        elif mutation == "taker":
            final = cast(dict[str, Any], account["final_fee_rule_set"])
            taker = next(
                rule
                for rule in final["charge_rules"]
                if rule["applicability"] == "taker_only"
            )
            taker["applicability"] = "maker_only"
            _rehash_fee_config(final, "final_fee_rule_set_config")
        elif mutation == "capacity":
            capacity["max_num_orders"] = 0
        elif mutation == "stale_source_refs":
            active = cast(dict[str, Any], account["active_band"])
            for band in (active, book["bands"][0]):
                ref = next(
                    value
                    for value in band["source_refs"]
                    if value["source_kind"] == "commission_rate"
                )
                ref["source_hash"] = "sha256:" + "1" * 64
        elif mutation == "stale_max_notional":
            account["active_band"]["max_notional_value"] = "2000000.00000000"
            book["bands"][0]["max_notional_value"] = "2000000.00000000"
        elif mutation == "stale_book_band":
            book["bands"][0]["max_notional_value"] = "2000000.00000000"

        if rehash_account:
            _rehash_account_wire(wire)
        with pytest.raises((TypeError, ValueError), match=".+"):
            BinanceUsdmKoruTradifiExecutionBundleRequestV1(
                source,
                target,
                wire,
                canonical_sha256(wire),
                "account-1",
                _REQUIRED_EQUITY,
                "1",
            )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("model_key", "crypto.binance_usdm.account-profile.v2"),
        ("model_digest", "sha256:" + "0" * 64),
        ("limitations", ["development_grade_account_history_completeness_unproven"]),
    ),
)
def test_account_model_identity_mutations_fail_with_outer_hashes_recomputed(
    field: str, value: object
) -> None:
    source = target_fixture._base_fragment()
    target = target_fixture._base_result()
    wire = _profile_wire(source)
    account = cast(dict[str, Any], wire["account_profile"])
    account[field] = value
    _rehash_account_wire(wire)
    _assert_profile_wire_rejected(source, target, wire)


def test_symbol_source_and_leverage_staleness_fail_with_outer_hashes_recomputed() -> (
    None
):
    source = target_fixture._base_fragment()
    target = target_fixture._base_result()
    for mutation in ("symbol_source", "leverage"):
        wire = _profile_wire(source)
        account = cast(dict[str, Any], wire["account_profile"])
        book = account["query"]["account_profile_book"]
        if mutation == "symbol_source":
            for band in (account["active_band"], book["bands"][0]):
                ref = next(
                    value
                    for value in band["source_refs"]
                    if value["source_kind"] == "symbol_config"
                )
                ref["source_hash"] = "sha256:" + "1" * 64
        else:
            account["leverage_evidence"]["selected_leverage"]["units"] = 2
        _rehash_account_wire(wire)
        _assert_profile_wire_rejected(source, target, wire)


@pytest.mark.parametrize(
    ("field", "value"),
    (("schedule_key", "stale"), ("schedule_digest", "sha256:" + "0" * 64)),
)
def test_account_fee_schedule_mutations_fail_with_outer_hashes_recomputed(
    field: str, value: str
) -> None:
    source = target_fixture._base_fragment()
    target = target_fixture._base_result()
    wire = _profile_wire(source)
    account = cast(dict[str, Any], wire["account_profile"])
    account["account_fee_schedule_ref"][field] = value
    _rehash_account_wire(wire)
    _assert_profile_wire_rejected(source, target, wire)


@pytest.mark.parametrize(
    ("rule_set_key", "rule_index", "field", "value"),
    (
        (
            "fee_reservation_rule_set",
            0,
            "rate",
            {"type": "rate", "units": 1, "scale": 8, "basis": "fee_fraction"},
        ),
        ("fee_reservation_rule_set", 1, "applicability", "applies"),
        ("fee_reservation_rule_set", 2, "rule_id", "mutated-account-rule"),
        (
            "fee_reservation_rule_set",
            2,
            "quantization",
            {
                "type": "quantization_policy",
                "version": "binance-usdm-fee-reservation-ceiling-v1",
                "target_scale": 8,
                "rounding": "floor",
            },
        ),
        (
            "final_fee_rule_set",
            0,
            "rate",
            {"type": "rate", "units": 1, "scale": 8, "basis": "fee_fraction"},
        ),
        ("final_fee_rule_set", 1, "applicability", "maker_only"),
        ("final_fee_rule_set", 2, "calculation_basis", "flat_amount"),
        (
            "final_fee_rule_set",
            3,
            "quantization",
            {
                "type": "quantization_policy",
                "version": "binance-usdm-final-fee-toward-zero-v1",
                "target_scale": 8,
                "rounding": "ceiling",
            },
        ),
    ),
)
def test_fee_tax_rule_and_quantization_mutations_fail_with_hashes_recomputed(
    rule_set_key: str, rule_index: int, field: str, value: object
) -> None:
    source = target_fixture._base_fragment()
    target = target_fixture._base_result()
    wire = _profile_wire(source)
    account = cast(dict[str, Any], wire["account_profile"])
    rule_set = cast(dict[str, Any], account[rule_set_key])
    rule_set["charge_rules"][rule_index][field] = value
    config_type = (
        "fee_reservation_rule_set_config"
        if rule_set_key == "fee_reservation_rule_set"
        else "final_fee_rule_set_config"
    )
    _rehash_fee_config(rule_set, config_type)
    _rehash_account_wire(wire)
    _assert_profile_wire_rejected(source, target, wire)


def test_capacity_and_order_source_mutations_fail_closed() -> None:
    source = target_fixture._base_fragment()
    target = target_fixture._base_result()
    for mutation in ("capacity_source", "order_schema", "order_hash"):
        wire = _profile_wire(source)
        capacity = cast(dict[str, Any], wire["account_capacity"])
        order_rules = cast(dict[str, Any], wire["order_rules"])
        order_source = cast(
            dict[str, Any], order_rules["active_band"]["source_ref"]
        )
        if mutation == "capacity_source":
            capacity["source_key"] = "foreign-source"
        elif mutation == "order_schema":
            order_source["schema_version"] = 2
        else:
            order_source["source_hash"] = "not-a-hash"
        _assert_profile_wire_rejected(source, target, wire)


def test_coherent_nonnegative_account_rates_are_reconstructed_from_lexemes() -> None:
    source = target_fixture._base_fragment()
    target = target_fixture._base_result()
    base = composition_request()
    account = base.account_profile
    assert account is not None
    band = replace(
        account.active_band,
        maker_commission_rate="0.001200000",
        taker_commission_rate="0.0003",
    )
    book = replace(account.query.account_profile_book, bands=(band,))
    query = replace(account.query, account_profile_book=book)
    outcome = BinanceUsdmAccountProfileModel().resolve_account_profile(query)
    assert outcome.result is not None, outcome.failure
    wire = _profile_wire(source, replace(base, account_profile=outcome.result))

    request = BinanceUsdmKoruTradifiExecutionBundleRequestV1(
        source,
        target,
        wire,
        canonical_sha256(wire),
        "account-1",
        _REQUIRED_EQUITY,
        "1",
    )

    assert request.execution_account_id == "account-1"


def test_constructor_bypass_request_mutations_fail_outcome_and_replay() -> None:
    source = target_fixture._base_fragment()
    target = target_fixture._base_result()
    mutations = (
        (
            "initial_equity",
            Money(999_900_000_000, Scale(8), "USDT"),
        ),
        ("sleeve_allocation_fraction", "0.5"),
        ("profile_composition_request_wire", {"type": "mutated"}),
        ("source_projection", target_fixture._weekend_fragment()),
        ("target_result", target_fixture._weekend_result()),
    )
    for field_name, value in mutations:
        result = _build(source, target)
        object.__setattr__(result.request, field_name, value)
        assert _trusted_result(result) is None
        with pytest.raises(ValueError, match="exact canonical"):
            BinanceUsdmKoruTradifiExecutionBundleOutcomeV1(result=result)


def test_manifest_result_and_digest_are_deterministic_and_tamper_evident() -> None:
    first = _empty_result()
    second = _build(target_fixture._base_fragment(), target_fixture._base_result())

    assert first.bundle_ref == second.bundle_ref
    assert canonical_bytes(first.manifest) == canonical_bytes(second.manifest)
    assert first.result_digest == second.result_digest
    assert _trusted_result(first) is not None
    assert BinanceUsdmKoruTradifiExecutionBundleOutcomeV1(result=first).result is first

    object.__setattr__(second, "result_digest", "sha256:" + "0" * 64)
    assert _trusted_result(second) is None
    with pytest.raises(ValueError, match="exact canonical"):
        BinanceUsdmKoruTradifiExecutionBundleOutcomeV1(result=second)
