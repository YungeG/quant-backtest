from __future__ import annotations

import json
from dataclasses import fields, replace
from functools import cache
from types import SimpleNamespace

import pytest
from crypto_quant_backtest import (
    ArtifactInstallMode,
    BinanceUsdmTradifiBarRequestIntent,
    BinanceUsdmTradifiProviderInputs,
    BuildArtifactRef,
    BuildArtifactRole,
    RequestedResultGrade,
    SourceTreeState,
    TimelineWindow,
)
from crypto_quant_backtest.binance_usdm_tradifi_preparation import (
    BinanceUsdmTradifiPreparationFailureCode,
    BinanceUsdmTradifiPreparationOutcome,
    BinanceUsdmTradifiPreparationResult,
    _trusted_result,
    resolve_binance_usdm_tradifi_preparation_authority_v1,
)
from crypto_quant_bundle_builder.binance_usdm_koru_closed_market_range_targets_v1 import (
    BinanceUsdmKoruClosedMarketRangeTargetsRequestV1,
    build_binance_usdm_koru_closed_market_range_targets_v1,
)
from crypto_quant_bundle_builder.binance_usdm_koru_tradifi_execution_bundle_v1 import (
    BinanceUsdmKoruTradifiExecutionBundleRequestV1,
    build_binance_usdm_koru_tradifi_execution_bundle_v1,
)
from crypto_quant_bundle_builder.binance_usdm_koru_tradifi_source_projection_v1 import (
    build_binance_usdm_koru_tradifi_source_projection_v1,
)
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactReadResult,
    ArtifactRef,
    CurrencyId,
    InstrumentId,
    Money,
    Scale,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    InMemoryMarketBundleReader,
    MarketBundleCapability,
    MarketBundleManifest,
    MarketStreamManifest,
)

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_aggtrades_source_bounded_v1 as aggregate_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_execution_bundle_v1 as execution_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_source_projection_v1 as source_fixture,
)
from tests.runtime.profiles.binance_usdm._tradifi_fixtures import (
    composition_request as ordinary_composition_request,
)
from tests.runtime.resolution._fixtures import build_manifest

_HOUR_NS = 3_600_000_000_000
_EQUITY = Money(1_000_000_000_000, Scale(8), "USDT")


class _Store:
    def __init__(self, envelopes: tuple[ArtifactEnvelope, ...]) -> None:
        self.values: dict[ArtifactRef, ArtifactReadResult] = {}
        for envelope in envelopes:
            ref = ArtifactRef.from_envelope(envelope)
            source = canonical_bytes(envelope)
            self.values[ref] = ArtifactReadResult(
                envelope, object(), source, canonical_sha256(envelope)
            )

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        return self.values[ref]


@cache
def _accepted_bundle():
    start = aggregate_fixture.DAY_START_NS
    end = start + 2 * _HOUR_NS
    trade = aggregate_fixture.DAY_START_MS + 90 * 60_000
    source_outcome = build_binance_usdm_koru_tradifi_source_projection_v1(
        source_fixture._request(((trade, "12.340"),), start_ns=start, end_ns=end)
    )
    assert source_outcome.failure is None and source_outcome.result is not None
    source = source_outcome.result
    target_outcome = build_binance_usdm_koru_closed_market_range_targets_v1(
        BinanceUsdmKoruClosedMarketRangeTargetsRequestV1(source)
    )
    assert target_outcome.failure is None and target_outcome.result is not None
    targets = target_outcome.result
    wire = execution_fixture._profile_wire(source)
    bundle_outcome = build_binance_usdm_koru_tradifi_execution_bundle_v1(
        BinanceUsdmKoruTradifiExecutionBundleRequestV1(
            source,
            targets,
            wire,
            canonical_sha256(wire),
            "account-1",
            _EQUITY,
            "1",
        )
    )
    assert bundle_outcome.failure is None and bundle_outcome.result is not None
    return bundle_outcome.result


def _store(bundle=None) -> _Store:
    value = bundle or _accepted_bundle()
    source = value.source_projection
    return _Store(
        (
            *value.target_result.artifacts,
            source.xkrx_calendar,
            source.arcx_calendar,
            source.post_adjustment_unit_regime,
        )
    )


def _intent(parameter_index: int = 0, *, bundle=None, **changes):
    value = bundle or _accepted_bundle()
    source = value.source_projection
    intent = BinanceUsdmTradifiBarRequestIntent(
        experiment_id="tradifi-preparation-test",
        timeline_window=TimelineWindow(
            source.request.timeline_window_start,
            source.request.timeline_window_start,
            source.request.timeline_window_end_exclusive,
        ),
        execution_account_id="account-1",
        reporting_currency=CurrencyId("USDT"),
        master_random_seed=0,
        market_bundle_ref=value.reader.bundle_ref,
        strategy_definition_ref=value.target_result.strategy.ref,
        strategy_parameter_set_ref=value.target_result.parameters[parameter_index].ref,
        result_grade_requested=RequestedResultGrade.DEVELOPMENT,
    )
    return replace(intent, **changes)


def _provider(**changes):
    return replace(
        BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY), **changes
    )


def _resolve(
    parameter_index: int = 0, *, bundle=None, store=None, intent=None, provider=None
):
    value = bundle or _accepted_bundle()
    return resolve_binance_usdm_tradifi_preparation_authority_v1(
        intent=intent or _intent(parameter_index, bundle=value),
        provider_inputs=provider or _provider(),
        artifact_reader=store or _store(value),
        market_reader=value.reader,
    )


def _mutated_events_bundle(*events):
    base = _accepted_bundle()
    streams = dict(base.streams)
    manifests = {value.stream_key: value for value in base.manifest.streams}
    for event in events:
        streams[event.stream_key] = (event,)
        manifests[event.stream_key] = MarketStreamManifest.from_events(
            event.stream_key, (event,)
        )
    manifest = MarketBundleManifest.build(
        bundle_key=base.manifest.bundle_key,
        schema_version=base.manifest.schema_version,
        coverage_start=base.manifest.coverage_start,
        coverage_end_exclusive=base.manifest.coverage_end_exclusive,
        instrument_catalog_hash=base.manifest.instrument_catalog_hash,
        capabilities=base.manifest.capabilities,
        streams=manifests.values(),
    )
    reader = InMemoryMarketBundleReader(
        bundle_ref=type(base.reader.bundle_ref).from_manifest(manifest),
        manifest=manifest,
        streams=streams,
    )
    return SimpleNamespace(
        reader=reader,
        manifest=manifest,
        streams=reader.streams,
        preparation_authority_event=streams[
            base.preparation_authority_event.stream_key
        ][0],
        price_purpose_authority_event=streams[
            base.price_purpose_authority_event.stream_key
        ][0],
        target_result=base.target_result,
        source_projection=base.source_projection,
    )


def _mutated_bundle(payload: dict[str, object]):
    return _mutated_events_bundle(
        replace(_accepted_bundle().preparation_authority_event, payload=payload)
    )


def _forged_result(
    result: BinanceUsdmTradifiPreparationResult, **changes: object
) -> BinanceUsdmTradifiPreparationResult:
    forged = object.__new__(BinanceUsdmTradifiPreparationResult)
    for value in fields(result):
        object.__setattr__(
            forged,
            value.name,
            changes.get(value.name, getattr(result, value.name)),
        )
    return forged


@pytest.mark.parametrize("parameter_index", range(8))
def test_all_eight_parameter_selections_resolve_including_empty_streams(
    parameter_index: int,
) -> None:
    outcome = _resolve(parameter_index)

    assert outcome.failure is None and outcome.result is not None
    result = outcome.result
    selected = _accepted_bundle().target_result.streams[parameter_index]
    assert selected.events == ()
    assert result.target_stream.events == ()
    assert result.target_stream_key == selected.stream_key
    assert result.target_stream_digest == selected.target_stream_digest
    assert result.strategy_parameter_set_ref == selected.parameter_ref
    assert result.market_reader is _accepted_bundle().reader
    assert len(result.verified_artifact_refs) == 12
    assert len(result.verified_target_bindings) == 8
    assert tuple(value.parameter_ref for value in result.verified_target_bindings) == (
        _accepted_bundle().parameter_refs
    )
    assert result.profile_registry == result.resolved_profile.profile_registry
    assert (
        result.financial_dispatcher_spec
        == result.resolved_profile.financial_dispatcher_spec
    )


def test_replay_is_exact_and_ordinary_profile_composition_is_unchanged() -> None:
    before = canonical_sha256(ordinary_composition_request())
    first = _resolve().result
    second = _resolve().result

    assert first is not None and second is not None
    assert canonical_bytes(first) == canonical_bytes(second)
    assert first.result_digest == second.result_digest
    assert canonical_sha256(ordinary_composition_request()) == before


def test_strategy_parameter_swap_unknown_duplicate_key_and_digest_fail_closed() -> None:
    base = _accepted_bundle()
    payload = json.loads(canonical_bytes(base.preparation_authority_event.payload))
    swapped = dict(payload)
    swapped["strategy_definition_ref"] = base.target_result.parameters[
        0
    ].ref.to_canonical_dict()
    swapped_bundle = _mutated_bundle(swapped)
    outcome = _resolve(bundle=swapped_bundle, intent=_intent(bundle=swapped_bundle))
    assert outcome.failure is not None

    for mutation in ("unknown", "duplicate", "key", "digest"):
        changed = json.loads(canonical_bytes(payload))
        bindings = changed["parameter_target_bindings"]
        if mutation == "unknown":
            bindings[0]["parameter_id"] = "p09"
        elif mutation == "duplicate":
            bindings[1] = bindings[0]
        elif mutation == "key":
            bindings[0]["target_stream_key"] += ".wrong"
        else:
            bindings[0]["target_stream_digest"] = "sha256:" + "0" * 64
        bundle = _mutated_bundle(changed)
        outcome = _resolve(bundle=bundle, intent=_intent(bundle=bundle))
        assert outcome.failure is not None
        expected = (
            BinanceUsdmTradifiPreparationFailureCode.TARGET_STREAM_INVALID
            if mutation == "digest"
            else BinanceUsdmTradifiPreparationFailureCode.PARAMETER_TARGET_BINDING_INVALID
        )
        assert outcome.failure.code is expected


def test_target_stream_tamper_and_authority_digest_mismatch_fail_closed() -> None:
    base = _accepted_bundle()
    payload = json.loads(canonical_bytes(base.preparation_authority_event.payload))
    payload["parameter_target_bindings"][0]["target_stream_digest"] = (
        "sha256:" + "0" * 64
    )
    bundle = _mutated_bundle(payload)

    outcome = _resolve(bundle=bundle, intent=_intent(bundle=bundle))

    assert outcome.failure is not None
    assert outcome.failure.code in {
        BinanceUsdmTradifiPreparationFailureCode.PARAMETER_TARGET_BINDING_INVALID,
        BinanceUsdmTradifiPreparationFailureCode.TARGET_STREAM_INVALID,
    }


def test_artifact_source_bytes_hash_and_arbitrary_decoded_object_handling() -> None:
    accepted = _resolve()
    assert accepted.failure is None

    for field in ("source_bytes", "source_hash", "envelope"):
        store = _store()
        ref = _accepted_bundle().target_result.strategy.ref
        original = store.values[ref]
        forged = object.__new__(ArtifactReadResult)
        object.__setattr__(forged, "artifact", {"not": "authority"})
        object.__setattr__(forged, "source_bytes", original.source_bytes)
        object.__setattr__(forged, "source_hash", original.source_hash)
        object.__setattr__(forged, "envelope", original.envelope)
        if field == "source_bytes":
            object.__setattr__(forged, field, original.source_bytes + b" ")
        elif field == "source_hash":
            object.__setattr__(forged, field, "sha256:" + "0" * 64)
        else:
            object.__setattr__(
                forged,
                field,
                ArtifactEnvelope.create("strategy_definition", 1, {"wrong": True}),
            )
        store.values[ref] = forged
        outcome = _resolve(store=store)
        assert outcome.failure is not None
        assert (
            outcome.failure.code
            is BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_READ_INVALID
        )


@pytest.mark.parametrize(
    ("artifact_index", "mutate"),
    (
        (0, lambda payload: payload["rules"].__setitem__("confidence", "0")),
        (8, lambda payload: payload.__setitem__("formation_hours", "999")),
        (
            9,
            lambda payload: payload["sessions"][0].__setitem__(
                "open_utc", "2026-07-15T00:00:00Z"
            ),
        ),
        (11, lambda payload: payload["adjustment"].__setitem__("ratio", "2")),
    ),
    ids=("strategy", "parameter", "calendar", "unit"),
)
def test_frozen_artifact_section_mutations_fail_hash_ref_binding(
    artifact_index: int, mutate
) -> None:
    store = _store()
    envelope = (
        _accepted_bundle().target_result.artifacts
        + _accepted_bundle().authority_artifacts
    )[artifact_index]
    ref = ArtifactRef.from_envelope(envelope)
    payload = json.loads(canonical_bytes(envelope.payload))
    mutate(payload)
    changed = ArtifactEnvelope.create(
        envelope.artifact_type, envelope.schema_version, payload
    )
    source = canonical_bytes(changed)
    original = store.values[ref]
    forged = object.__new__(ArtifactReadResult)
    object.__setattr__(forged, "artifact", original.artifact)
    object.__setattr__(forged, "source_bytes", source)
    object.__setattr__(forged, "source_hash", canonical_sha256(changed))
    object.__setattr__(forged, "envelope", changed)
    store.values[ref] = forged

    outcome = _resolve(store=store)

    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_READ_INVALID
    )


def test_unselected_parameter_stream_and_artifact_are_validated_before_selection() -> (
    None
):
    base = _accepted_bundle()
    payload = json.loads(canonical_bytes(base.preparation_authority_event.payload))
    payload["parameter_target_bindings"][7]["target_stream_digest"] = (
        "sha256:" + "0" * 64
    )
    bundle = _mutated_bundle(payload)
    outcome = _resolve(bundle=bundle, intent=_intent(0, bundle=bundle))
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is BinanceUsdmTradifiPreparationFailureCode.TARGET_STREAM_INVALID
    )

    store = _store()
    ref = base.parameter_refs[7]
    original = store.values[ref]
    forged = object.__new__(ArtifactReadResult)
    object.__setattr__(forged, "artifact", original.artifact)
    object.__setattr__(forged, "source_bytes", original.source_bytes + b" ")
    object.__setattr__(forged, "source_hash", original.source_hash)
    object.__setattr__(forged, "envelope", original.envelope)
    store.values[ref] = forged
    outcome = _resolve(0, store=store)
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is BinanceUsdmTradifiPreparationFailureCode.ARTIFACT_READ_INVALID
    )


class _MutatedStreamReader:
    def __init__(self, base, stream_key: str) -> None:
        self._base = base
        self._stream_key = stream_key

    @property
    def bundle_ref(self):
        return self._base.bundle_ref

    @property
    def manifest(self):
        return self._base.manifest

    def validate_requirements(self, **kwargs):
        return self._base.validate_requirements(**kwargs)

    def open_cursor(self, stream_key: str, *, batch_size: int):
        return self._base.open_cursor(stream_key, batch_size=batch_size)

    def resume_cursor(self, cursor, *, batch_size=None):
        return self._base.resume_cursor(cursor, batch_size=batch_size)

    def read_batch(self, cursor):
        events, next_cursor = self._base.read_batch(cursor)
        if cursor.stream_manifest.stream_key == self._stream_key and events:
            payload = json.loads(canonical_bytes(events[0].payload))
            payload["mutated"] = True
            events = (replace(events[0], payload=payload), *events[1:])
        return events, next_cursor


def test_price_purpose_source_manifest_fan_in_is_exact() -> None:
    base = _accepted_bundle()
    price_payload = json.loads(
        canonical_bytes(base.price_purpose_authority_event.payload)
    )
    price_payload["price_purpose_bindings"][3]["source_stream_manifest"][
        "event_count"
    ] += 1
    price_event = replace(base.price_purpose_authority_event, payload=price_payload)
    preparation_payload = json.loads(
        canonical_bytes(base.preparation_authority_event.payload)
    )
    preparation_payload["price_purpose_authority_binding"]["event_hash"] = (
        price_event.event_hash
    )
    preparation_event = replace(
        base.preparation_authority_event, payload=preparation_payload
    )
    bundle = _mutated_events_bundle(price_event, preparation_event)

    outcome = _resolve(bundle=bundle, intent=_intent(bundle=bundle))

    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID
    )


def test_price_purpose_event_instrument_is_exact() -> None:
    base = _accepted_bundle()
    price_event = replace(
        base.price_purpose_authority_event,
        instrument_id=InstrumentId(VenueId("other"), "other"),
    )
    preparation_payload = json.loads(
        canonical_bytes(base.preparation_authority_event.payload)
    )
    preparation_payload["price_purpose_authority_binding"]["event_hash"] = (
        price_event.event_hash
    )
    preparation_event = replace(
        base.preparation_authority_event, payload=preparation_payload
    )
    bundle = _mutated_events_bundle(price_event, preparation_event)

    outcome = _resolve(bundle=bundle, intent=_intent(bundle=bundle))

    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID
    )


def test_price_purpose_source_stream_is_read_not_only_manifest_bound() -> None:
    base = _accepted_bundle()
    binding = base.price_purpose_authority_event.payload["price_purpose_bindings"][0]
    stream_key = binding["source_stream_manifest"]["stream_key"]
    reader = _MutatedStreamReader(base.reader, stream_key)

    outcome = resolve_binance_usdm_tradifi_preparation_authority_v1(
        intent=_intent(bundle=base),
        provider_inputs=_provider(),
        artifact_reader=_store(base),
        market_reader=reader,
    )

    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH
    )


@pytest.mark.parametrize(
    "mutation",
    ("source_snapshot", "source_limitations", "source_fragment", "target_digest"),
)
def test_final_authority_fan_in_mutations_fail_closed(mutation: str) -> None:
    base = _accepted_bundle()
    payload = json.loads(canonical_bytes(base.preparation_authority_event.payload))
    if mutation == "source_snapshot":
        payload["source_snapshot_bindings"][0]["source_snapshot_hash"] = (
            "sha256:" + "0" * 64
        )
    elif mutation == "source_limitations":
        payload["source_limitations"][0] = "mutated"
    elif mutation == "source_fragment":
        payload["source_fragment_digest"] = "sha256:" + "0" * 64
    else:
        payload["target_result_digest"] = "not-a-hash"
    bundle = _mutated_bundle(payload)

    outcome = _resolve(bundle=bundle, intent=_intent(bundle=bundle))

    assert outcome.failure is not None


def test_profile_nested_mutation_fails_closed() -> None:
    base = _accepted_bundle()
    payload = json.loads(canonical_bytes(base.preparation_authority_event.payload))
    payload["profile_composition_request_wire"]["required_market_state_keys"] = [
        "mutated"
    ]
    payload["profile_composition_request_hash"] = canonical_sha256(
        payload["profile_composition_request_wire"]
    )
    bundle = _mutated_bundle(payload)

    outcome = _resolve(bundle=bundle, intent=_intent(bundle=bundle))

    assert outcome.failure is not None
    assert outcome.failure.code in {
        BinanceUsdmTradifiPreparationFailureCode.PREPARATION_AUTHORITY_INVALID,
        BinanceUsdmTradifiPreparationFailureCode.PROFILE_WIRE_INVALID,
        BinanceUsdmTradifiPreparationFailureCode.PROFILE_BINDING_INVALID,
        BinanceUsdmTradifiPreparationFailureCode.PROFILE_COMPOSITION_FAILED,
    }


def test_intent_provider_and_bundle_boundaries_are_exact() -> None:
    base = _intent()
    with pytest.raises(ValueError, match="USDT"):
        replace(base, reporting_currency=CurrencyId("USD"))
    with pytest.raises(ValueError, match="exact 0"):
        replace(base, master_random_seed=1)
    with pytest.raises(ValueError, match="DEVELOPMENT"):
        replace(base, result_grade_requested=RequestedResultGrade.DECISION_GRADE)
    with pytest.raises(ValueError, match="10000 USDT"):
        _provider(initial_equity=Money(999_999_999_999, Scale(8), "USDT"))

    other = _accepted_bundle()
    wrong_window = TimelineWindow(
        other.manifest.coverage_start,
        other.manifest.coverage_start,
        type(other.manifest.coverage_end_exclusive)(
            other.manifest.coverage_end_exclusive.epoch_nanoseconds - 1
        ),
    )
    outcome = _resolve(intent=replace(base, timeline_window=wrong_window))
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is BinanceUsdmTradifiPreparationFailureCode.MARKET_BUNDLE_MISMATCH
    )


def test_trusted_result_rejects_object_digest_and_reader_manifest_tampering() -> None:
    result = _resolve().result
    assert result is not None

    forged_object = _forged_result(
        result, target_stream_key=result.target_stream_key + ".tampered"
    )
    forged_digest = _forged_result(result, result_digest="sha256:" + "0" * 64)
    changed_manifest = MarketBundleManifest.build(
        bundle_key=result.market_bundle_manifest.bundle_key,
        schema_version=result.market_bundle_manifest.schema_version,
        coverage_start=result.market_bundle_manifest.coverage_start,
        coverage_end_exclusive=result.market_bundle_manifest.coverage_end_exclusive,
        instrument_catalog_hash="sha256:" + "0" * 64,
        capabilities=result.market_bundle_manifest.capabilities,
        streams=result.market_bundle_manifest.streams,
    )
    forged_reader = _forged_result(
        result,
        market_reader=SimpleNamespace(
            bundle_ref=result.market_bundle_ref,
            manifest=changed_manifest,
        ),
    )

    for forged in (forged_object, forged_digest, forged_reader):
        assert _trusted_result(forged) is None
        with pytest.raises(ValueError, match="trusted preparation result"):
            BinanceUsdmTradifiPreparationOutcome(result=forged)


def test_manifest_fan_in_preserves_unrelated_refs_and_rejects_conflicts() -> None:
    accepted = _resolve().result
    assert accepted is not None
    base = _provider().build_artifact_manifest
    profile_keys = {
        accepted.resolved_profile.market_registration.profile_key,
        accepted.resolved_profile.simulation_registration.profile_key,
        accepted.resolved_profile.execution_account_registration.profile_key,
    }
    assert tuple(
        value
        for value in accepted.build_artifact_manifest.artifacts
        if (value.role, value.artifact_key)
        not in {(BuildArtifactRole.PROFILE_COMPONENT, key) for key in profile_keys}
    ) == tuple(
        value
        for value in base.artifacts
        if (value.role, value.artifact_key)
        not in {(BuildArtifactRole.PROFILE_COMPONENT, key) for key in profile_keys}
    )

    registration = accepted.resolved_profile.market_registration
    unrelated_same_key = BuildArtifactRef(
        role=BuildArtifactRole.DECISION_SOURCE,
        artifact_key=registration.profile_key,
        artifact_version="1",
        install_mode=ArtifactInstallMode.WHEEL,
        source_tree_state=SourceTreeState.CLEAN,
        content_hash="sha256:" + "1" * 64,
        source_snapshot_hash=None,
    )
    with_unrelated = replace(base, artifacts=base.artifacts + (unrelated_same_key,))
    retained = _resolve(
        provider=_provider(build_artifact_manifest=with_unrelated)
    ).result
    assert retained is not None
    assert unrelated_same_key in retained.build_artifact_manifest.artifacts

    conflict = replace(
        accepted.build_artifact_manifest,
        artifacts=tuple(
            replace(value, content_hash="sha256:" + "0" * 64)
            if value.artifact_key == registration.profile_key
            else value
            for value in accepted.build_artifact_manifest.artifacts
        ),
    )
    outcome = _resolve(provider=_provider(build_artifact_manifest=conflict))
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is BinanceUsdmTradifiPreparationFailureCode.BUILD_MANIFEST_CONFLICT
    )


def test_profile_required_capabilities_are_present_in_final_bundle() -> None:
    result = _resolve().result
    assert result is not None
    required = {
        *result.resolved_profile.market_registration.required_bundle_capabilities,
        *result.resolved_profile.simulation_registration.required_bundle_capabilities,
    }
    assert MarketBundleCapability("bar_open", 1) in required
    assert (
        result.market_reader.validate_requirements(required_capabilities=required)
        is None
    )
    assert (
        result.market_reader.validate_requirements(
            required_capabilities=(
                MarketBundleCapability("precomputed_target_stream", 1),
            )
        )
        is None
    )
