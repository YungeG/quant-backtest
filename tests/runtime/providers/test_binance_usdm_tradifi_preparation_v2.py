from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from functools import cache
from types import SimpleNamespace

import pytest
from crypto_quant_backtest import (
    BinanceUsdmTradifiBarRequestIntent,
    BinanceUsdmTradifiProviderInputs,
    RequestedResultGrade,
    TimelineWindow,
)
from crypto_quant_backtest.binance_usdm_tradifi_preparation import (
    BinanceUsdmTradifiPreparationFailureCode,
    _trusted_result,
    resolve_binance_usdm_tradifi_preparation_authority_v2,
)
from crypto_quant_domain import (
    ArtifactReadResult,
    ArtifactRef,
    CurrencyId,
    Money,
    Scale,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    InMemoryMarketBundleReader,
    MarketBundleManifest,
    MarketStreamManifest,
)

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_closed_market_range_targets_v1 as target_v1_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_execution_bundle_v2 as bundle_v2_fixture,
)
from tests.runtime.providers import (
    test_binance_usdm_tradifi_preparation as v1_preparation_fixture,
)
from tests.runtime.resolution._fixtures import build_manifest

_EQUITY = Money(1_000_000_000_000, Scale(8), "USDT")


class _Store:
    def __init__(self, bundle) -> None:
        self.values = {}
        for envelope in (*bundle.target_result.artifacts, *bundle.authority_artifacts):
            ref = ArtifactRef.from_envelope(envelope)
            source = canonical_bytes(envelope)
            self.values[ref] = ArtifactReadResult(
                envelope,
                object(),
                source,
                "sha256:" + hashlib.sha256(source).hexdigest(),
            )

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        return self.values[ref]


@cache
def _nonempty_bundle():
    return bundle_v2_fixture._build()


@cache
def _empty_bundle():
    return bundle_v2_fixture._build(
        bundle_v2_fixture._source(target_v1_fixture._base_fragment())
    )


def _two_funding_bundle():
    source = target_v1_fixture._weekend_fragment()
    start = source.request.timeline_window_start.epoch_nanoseconds // 1_000_000
    return bundle_v2_fixture._build(
        bundle_v2_fixture._source(source, (start + 18_000_000, start + 21_600_000))
    )


@cache
def _raw_scale8_two_funding_bundle():
    return bundle_v2_fixture._raw_scale8_two_funding_bundle()


def _intent(bundle, parameter_index: int = 0):
    source = bundle.source_projection
    return BinanceUsdmTradifiBarRequestIntent(
        experiment_id="tradifi-preparation-v2-test",
        timeline_window=TimelineWindow(
            source.request.timeline_window_start,
            source.request.timeline_window_start,
            source.request.timeline_window_end_exclusive,
        ),
        execution_account_id="account-1",
        reporting_currency=CurrencyId("USDT"),
        master_random_seed=0,
        market_bundle_ref=bundle.reader.bundle_ref,
        strategy_definition_ref=bundle.target_result.strategy.ref,
        strategy_parameter_set_ref=bundle.target_result.parameters[
            parameter_index
        ].ref,
        result_grade_requested=RequestedResultGrade.DEVELOPMENT,
    )


def _resolve(bundle, parameter_index: int = 0, store=None):
    return resolve_binance_usdm_tradifi_preparation_authority_v2(
        intent=_intent(bundle, parameter_index),
        provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY),
        artifact_reader=store or _Store(bundle),
        market_reader=bundle.reader,
    )


def _with_events(bundle, *events):
    streams = dict(bundle.streams)
    manifests = {value.stream_key: value for value in bundle.manifest.streams}
    for event in events:
        streams[event.stream_key] = (event,)
        manifests[event.stream_key] = MarketStreamManifest.from_events(
            event.stream_key, (event,)
        )
    manifest = MarketBundleManifest.build(
        bundle_key=bundle.manifest.bundle_key,
        schema_version=bundle.manifest.schema_version,
        coverage_start=bundle.manifest.coverage_start,
        coverage_end_exclusive=bundle.manifest.coverage_end_exclusive,
        instrument_catalog_hash=bundle.manifest.instrument_catalog_hash,
        capabilities=tuple(sorted({value.capability for value in manifests.values()})),
        streams=manifests.values(),
    )
    reader = InMemoryMarketBundleReader(
        type(bundle.bundle_ref).from_manifest(manifest), manifest, streams
    )
    return SimpleNamespace(
        reader=reader,
        manifest=manifest,
        streams=reader.streams,
        source_projection=bundle.source_projection,
        target_result=bundle.target_result,
    )


@pytest.mark.parametrize("parameter_index", range(8))
def test_v2_all_eight_streams_are_verified_before_selection(
    parameter_index: int,
) -> None:
    bundle = _nonempty_bundle()
    outcome = _resolve(bundle, parameter_index)

    assert outcome.failure is None and outcome.result is not None
    result = outcome.result
    selected = bundle.target_result.streams[parameter_index]
    assert result.bundle_schema_version == 2
    assert result.target_stream_key == selected.stream_key
    assert result.target_stream_digest == selected.target_stream_digest
    assert result.target_stream.events == selected.events
    assert len(result.verified_target_bindings) == 8
    assert len(result.verified_artifacts) == 13
    assert result.source_profile_authority_ref == bundle.authority_refs[3]
    assert result.source_profile_authority_hash == bundle.authority_artifacts[3].content_hash
    assert result.source_profile_authority_envelope == bundle.authority_artifacts[3]


def test_v2_empty_streams_and_trusted_replay_are_canonical() -> None:
    outcome = _resolve(_empty_bundle(), 7)

    assert outcome.failure is None and outcome.result is not None
    result = outcome.result
    assert all(value.target_stream.events == () for value in result.verified_target_bindings)
    assert result.target_stream.events == ()
    assert _trusted_result(result) is not None
    assert canonical_sha256(result.to_canonical_dict()) == canonical_sha256(result)


def test_v2_manifest_exact_covers_source_projection_targets_and_authorities() -> None:
    bundle = _nonempty_bundle()
    source_payload = bundle.authority_artifacts[3].payload
    source_keys = {
        value["stream_key"] for value in source_payload["source_stream_manifests"]
    }
    expected = {
        *source_keys,
        source_payload["execution_projection_stream_manifest"]["stream_key"],
        *(value.stream_key for value in bundle.target_result.streams),
        "binance_usdm.tradifi.preparation_authority.v2",
        "binance_usdm.tradifi.price_purpose.authority.koruusdt.v2",
        "binance_usdm.tradifi.account.authority.koruusdt.v2",
    }

    assert len(source_keys) == 7
    assert len(expected) == 19
    assert {value.stream_key for value in bundle.manifest.streams} == expected


def test_v2_source_authority_is_required_from_cas_and_exactly_bound() -> None:
    bundle = _nonempty_bundle()
    source_ref = bundle.authority_refs[3]
    missing = _Store(bundle)
    del missing.values[source_ref]

    outcome = _resolve(bundle, store=missing)

    assert outcome.failure is not None
    assert outcome.failure.code is BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_READ_INVALID

    payload = json.loads(canonical_bytes(bundle.preparation_authority_event.payload))
    payload["source_profile_authority_envelope"]["content_hash"] = "sha256:" + "0" * 64
    changed = _with_events(
        bundle, replace(bundle.preparation_authority_event, payload=payload)
    )
    outcome = _resolve(changed, store=_Store(bundle))
    assert outcome.failure is not None
    assert outcome.failure.code is BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID


@pytest.mark.parametrize(
    "kind", ("preparation", "price", "account", "bar_open", "target")
)
def test_v2_rejects_every_mixed_v1_stream_identity(kind: str) -> None:
    bundle = _nonempty_bundle()
    if kind == "preparation":
        event = replace(
            bundle.preparation_authority_event,
            event_id=bundle.preparation_authority_event.event_id + ":mixed-v1",
            stream_key="binance_usdm.tradifi.preparation_authority.v1",
            event_type="binance_usdm_tradifi_preparation_authority_v1",
        )
    elif kind == "price":
        event = replace(
            bundle.price_purpose_authority_event,
            event_id=bundle.price_purpose_authority_event.event_id + ":mixed-v1",
            stream_key="binance_usdm.tradifi.price_purpose.authority.koruusdt.v1",
            event_type="binance_usdm_tradifi_price_purpose_binding_v1",
        )
    elif kind == "account":
        event = replace(
            bundle.account_authority_event,
            event_id=bundle.account_authority_event.event_id + ":mixed-v1",
            stream_key="binance_usdm.tradifi.account.authority.koruusdt.v1",
        )
    elif kind == "bar_open":
        event = replace(
            bundle.source_projection.projection_events[0],
            event_id=bundle.source_projection.projection_events[0].event_id
            + ":mixed-v1",
            stream_key=(
                "binance_usdm.tradifi.bar_open."
                "first_retained_aggregate_trade.koruusdt.1h.v1"
            ),
        )
    else:
        target_event = next(
            event
            for stream in bundle.target_result.streams
            for event in stream.events
        )
        event = replace(
            target_event,
            event_id=target_event.event_id + ":mixed-v1",
            stream_key="binance_usdm.tradifi.target.koruusdt.closed_market_range.p01.v1",
        )
    mixed = _with_events(bundle, event)

    outcome = _resolve(mixed, store=_Store(bundle))

    assert outcome.failure is not None
    assert outcome.failure.code is (
        BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH
    )


def test_v2_rejects_v1_bundle_without_fallback() -> None:
    v1_bundle = v1_preparation_fixture._accepted_bundle()
    fallback = resolve_binance_usdm_tradifi_preparation_authority_v2(
        intent=v1_preparation_fixture._intent(bundle=v1_bundle),
        provider_inputs=v1_preparation_fixture._provider(),
        artifact_reader=v1_preparation_fixture._store(v1_bundle),
        market_reader=v1_bundle.reader,
    )
    assert fallback.failure is not None
    assert fallback.failure.code is BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH


def test_v2_projection_and_account_stream_content_are_read_and_exactly_bound() -> None:
    bundle = _nonempty_bundle()
    projection = bundle.source_projection.projection_events[0]
    projection_payload = json.loads(canonical_bytes(projection.payload))
    projection_payload["open_price"]["units"] += 1
    changed_projection = _with_events(
        bundle, replace(projection, payload=projection_payload)
    )

    projection_outcome = _resolve(changed_projection, store=_Store(bundle))

    assert projection_outcome.failure is not None
    assert projection_outcome.failure.code in {
        BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_BINDING_INVALID,
        BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH,
    }

    account_payload = json.loads(canonical_bytes(bundle.account_authority_event.payload))
    account_payload["account_id"] = "other-account"
    changed_account = _with_events(
        bundle, replace(bundle.account_authority_event, payload=account_payload)
    )

    account_outcome = _resolve(changed_account, store=_Store(bundle))

    assert account_outcome.failure is not None
    assert account_outcome.failure.code is (
        BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID
    )


def test_v2_rejects_extra_manifest_stream() -> None:
    bundle = _nonempty_bundle()
    extra = replace(
        bundle.account_authority_event,
        event_id=bundle.account_authority_event.event_id + ":extra",
        stream_key="binance_usdm.tradifi.unexpected.v2",
    )
    changed = _with_events(bundle, extra)

    outcome = _resolve(changed, store=_Store(bundle))

    assert outcome.failure is not None
    assert outcome.failure.code is (
        BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH
    )


def test_v2_profile_wire_mismatch_fails_closed() -> None:
    bundle = _nonempty_bundle()
    preparation = json.loads(canonical_bytes(bundle.preparation_authority_event.payload))
    price = json.loads(canonical_bytes(bundle.price_purpose_authority_event.payload))
    account = json.loads(canonical_bytes(bundle.account_authority_event.payload))
    preparation["profile_composition_request_wire"]["required_market_state_keys"] = [
        "mutated"
    ]
    changed_hash = canonical_sha256(preparation["profile_composition_request_wire"])
    preparation["profile_composition_request_hash"] = changed_hash
    price["profile_composition_request_hash"] = changed_hash
    account["profile_composition_request_hash"] = changed_hash
    price_event = replace(bundle.price_purpose_authority_event, payload=price)
    account_event = replace(bundle.account_authority_event, payload=account)
    preparation["price_purpose_authority_binding"]["event_hash"] = price_event.event_hash
    preparation_event = replace(bundle.preparation_authority_event, payload=preparation)
    changed = _with_events(bundle, price_event, preparation_event, account_event)

    outcome = _resolve(changed, store=_Store(bundle))

    assert outcome.failure is not None
    assert outcome.failure.code in {
        BinanceUsdmTradifiPreparationFailureCode.PROFILE_BINDING_INVALID,
        BinanceUsdmTradifiPreparationFailureCode.PROFILE_COMPOSITION_FAILED,
    }


def test_v2_unselected_empty_stream_digest_is_still_verified() -> None:
    bundle = _empty_bundle()
    payload = json.loads(canonical_bytes(bundle.preparation_authority_event.payload))
    payload["parameter_target_bindings"][7]["target_stream_digest"] = (
        "sha256:" + "0" * 64
    )
    changed = _with_events(
        bundle, replace(bundle.preparation_authority_event, payload=payload)
    )

    outcome = _resolve(changed, 0, _Store(bundle))

    assert outcome.failure is not None
    assert outcome.failure.code is BinanceUsdmTradifiPreparationFailureCode.TARGET_STREAM_INVALID
