from __future__ import annotations

from dataclasses import replace

from crypto_quant_bundle_builder import (
    BundleValidationFailure,
    BundleValidationFailureCode,
    validate_market_bundle_v1,
)
from crypto_quant_domain import SourceSequence, UtcInstant, canonical_sha256
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketBundleRef,
    MarketEvent,
)

from tests.bundle_builder.validation._fixtures import (
    call,
    duplicate_event,
    replace_event_key,
    replace_event_type,
    replace_source_hash,
    replace_source_key,
    replace_source_sequence,
    replace_stream_key,
    synthetic_events,
)
from tests.market_data.bundles._fixtures import PRICE_BARS, event


def test_success_derives_manifest_and_ref_parity() -> None:
    events = synthetic_events()
    outcome = call(events)

    assert outcome.manifest is not None and outcome.failure is None
    assert tuple(item.stream_key for item in outcome.manifest.streams) == (
        "synthetic.prices",
    )
    stream = outcome.manifest.streams[0]
    assert stream.event_count == len(events)
    assert stream.event_type == events[0].event_type
    assert stream.capability == events[0].capability
    assert stream.content_hash == canonical_sha256(events)
    assert MarketBundleRef.from_manifest(outcome.manifest).manifest_hash == canonical_sha256(
        outcome.manifest
    )


def test_empty_events_structural_success() -> None:
    outcome = call(tuple())
    assert outcome.failure is None
    assert outcome.manifest is not None
    assert outcome.manifest.streams == ()
    assert outcome.manifest.capabilities == ()


def test_precedence_invalid_header_over_duplicate_event_id() -> None:
    event_a, event_b = synthetic_events()[:2]
    outcome = validate_market_bundle_v1(
        bundle_key="bad.v1",
        schema_version=1,
        coverage_start=UtcInstant(100),
        coverage_end_exclusive=UtcInstant(0),
        instrument_catalog_hash="sha256:" + "d" * 64,
        events=(event_a, event_b),
    )

    assert outcome.failure is not None
    assert outcome.failure.code is BundleValidationFailureCode.INVALID_INPUT


def test_non_tuple_and_non_event_inputs_are_invalid() -> None:
    non_tuple = validate_market_bundle_v1(
        bundle_key="bad.v1",
        schema_version=1,
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(1_000),
        instrument_catalog_hash="sha256:" + "c" * 64,
        events=[],  # type: ignore[arg-type]
    )
    outcome = validate_market_bundle_v1(
        bundle_key="bad.v1",
        schema_version=1,
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(1_000),
        instrument_catalog_hash="sha256:" + "c" * 64,
        events=(
            {"event_id": "not-an-event"},  # type: ignore[arg-type]
        ),
    )

    assert non_tuple.manifest is None
    assert non_tuple.failure is not None
    assert non_tuple.failure.code is BundleValidationFailureCode.INVALID_INPUT
    assert outcome.manifest is None
    assert outcome.failure is not None
    assert outcome.failure == BundleValidationFailure(
        code=BundleValidationFailureCode.INVALID_INPUT,
        stream_key=None,
        input_position=None,
    )


def test_forged_envelope_precedes_structural_checks() -> None:
    events = synthetic_events()
    malformed = duplicate_event(events[1], event_id=events[0].event_id)
    object.__setattr__(malformed, "source_hash", "sha256:not-a-hash")

    outcome = call((events[0], malformed))

    assert outcome.failure is not None
    assert outcome.failure.code is BundleValidationFailureCode.INVALID_INPUT
    assert outcome.failure.input_position is None


def test_duplicate_event_id_precedes_other_failures() -> None:
    events = synthetic_events()
    duplicate = duplicate_event(events[2], event_id=events[0].event_id)
    duplicate = replace(
        duplicate,
        event_time=UtcInstant(2_000),
        available_time=UtcInstant(2_000),
        event_type="other-type",
    )

    outcome = call((events[0], duplicate, events[1]))

    assert outcome.failure is not None
    assert outcome.failure.code is BundleValidationFailureCode.DUPLICATE_EVENT_ID
    assert outcome.failure.input_position == 1


def test_event_outside_coverage_precedes_stream_classification() -> None:
    events = synthetic_events()
    outside = replace(
        events[0],
        event_id="outside",
        event_time=UtcInstant(2_000),
        available_time=UtcInstant(2_000),
    )
    mismatch = replace_event_type(events[1], value="other-type")

    outcome = call((outside, mismatch, events[2]))

    assert outcome.failure is not None
    assert outcome.failure.code is BundleValidationFailureCode.EVENT_OUTSIDE_COVERAGE
    assert outcome.failure.input_position == 0


def test_stream_classification_mismatch_precedes_ordering_conflicts() -> None:
    first = event(
        "a",
        stream_key="s",
        event_type="bar",
        capability=PRICE_BARS,
        event_time=100,
        source_sequence=1,
        price_units=1,
    )
    second = replace(
        first,
        event_id="b",
        event_type="bar2",
    )
    third = replace(
        second,
        event_id="c",
        source_sequence=SourceSequence(3),
    )
    fourth = replace(
        first,
        event_id="d",
        source_sequence=SourceSequence(3),
        event_time=UtcInstant(130),
        available_time=UtcInstant(130),
    )

    outcome = call((first, second, third, fourth))
    assert outcome.failure is not None
    assert outcome.failure.code is BundleValidationFailureCode.STREAM_CLASSIFICATION_MISMATCH
    assert outcome.failure.input_position == 1
    assert outcome.failure.stream_key == "s"


def test_duplicate_ordering_precedes_regression_and_is_stream_local() -> None:
    first = event(
        "left",
        stream_key="left",
        event_type="bar",
        capability=PRICE_BARS,
        event_time=100,
        source_sequence=1,
        price_units=1,
    )
    regression = replace(
        first,
        event_id="reg",
        source_sequence=SourceSequence(4),
        event_time=UtcInstant(50),
        available_time=UtcInstant(50),
    )
    duplicate = replace(
        first,
        event_id="dup",
        event_time=UtcInstant(50),
        available_time=UtcInstant(50),
        source_sequence=SourceSequence(4),
    )
    other_stream = event(
        "other",
        stream_key="right",
        event_type="bar",
        capability=PRICE_BARS,
        event_time=100,
        source_sequence=1,
        price_units=2,
    )

    duplicate_outcome = call((first, regression, other_stream, duplicate))
    assert duplicate_outcome.failure is not None
    assert duplicate_outcome.failure.code is BundleValidationFailureCode.DUPLICATE_STREAM_ORDERING_KEY
    assert duplicate_outcome.failure.stream_key == "left"
    assert duplicate_outcome.failure.input_position == 3

    regression_outcome = call((first, other_stream, regression))
    assert regression_outcome.failure is not None
    assert regression_outcome.failure.code is BundleValidationFailureCode.STREAM_ORDER_REGRESSION
    assert regression_outcome.failure.stream_key == "left"
    assert regression_outcome.failure.input_position == 2


def test_cross_stream_equal_ordering_keys_are_allowed() -> None:
    left = event(
        "left",
        stream_key="stream.alpha",
        event_type="bar",
        capability=PRICE_BARS,
        event_time=100,
        source_sequence=1,
        price_units=1,
    )
    right = event(
        "right",
        stream_key="stream.beta",
        event_type="bar",
        capability=PRICE_BARS,
        event_time=100,
        source_sequence=1,
        price_units=2,
    )

    outcome = call((left, right))
    assert outcome.manifest is not None and outcome.failure is None
    assert tuple(stream.stream_key for stream in outcome.manifest.streams) == (
        "stream.alpha",
        "stream.beta",
    )
    assert outcome.manifest.capabilities == (MarketBundleCapability("price_bars", 1),)


def test_non_contiguous_source_sequence_is_structural_success() -> None:
    first = event(
        "first",
        event_time=100,
        source_sequence=1,
        price_units=10,
    )
    second = event(
        "second",
        event_time=200,
        source_sequence=99,
        price_units=20,
    )

    outcome = call((first, second))
    assert outcome.failure is None
    assert outcome.manifest is not None
    assert outcome.manifest.streams[0].event_count == 2


def test_source_sensitivity_affects_hashes() -> None:
    events = synthetic_events()
    mutated_hash = replace_source_hash(events[0], value="sha256:" + "c" * 64)
    mutated_key = replace_source_key(events[0], value="fixture.other.source")

    baseline = call(events)
    hash_mutated = call((mutated_hash, *events[1:]))
    key_mutated = call((mutated_key, *events[1:]))

    assert baseline.manifest is not None
    assert hash_mutated.manifest is not None
    assert key_mutated.manifest is not None

    assert baseline.manifest.content_hash != hash_mutated.manifest.content_hash
    assert baseline.manifest.content_hash != key_mutated.manifest.content_hash
    assert canonical_sha256(baseline.manifest.streams[0]) != canonical_sha256(
        hash_mutated.manifest.streams[0]
    )


def test_duplicate_event_id_precedes_stream_classification_and_ordering() -> None:
    first = event(
        "a",
        stream_key="s",
        event_type="bar",
        capability=PRICE_BARS,
        event_time=100,
        source_sequence=1,
        price_units=1,
    )
    duplicate = duplicate_event(first)
    duplicate = replace_source_key(duplicate, value="k2")
    mismatch = replace_event_type(first, value="other")

    outcome = call((first, duplicate, mismatch))
    assert outcome.failure is not None
    assert outcome.failure.code is BundleValidationFailureCode.DUPLICATE_EVENT_ID
    assert outcome.failure.input_position == 1


def test_manifest_construction_failure_returns_invalid_input(monkeypatch) -> None:
    import crypto_quant_bundle_builder.bundle_validation as module

    def fail_build(**_kwargs):
        raise ValueError("contract failure")

    monkeypatch.setattr(module.MarketBundleManifest, "build", fail_build)
    outcome = call(synthetic_events())

    assert outcome.failure is not None
    assert outcome.failure == BundleValidationFailure(
        code=BundleValidationFailureCode.INVALID_INPUT,
        stream_key=None,
        input_position=None,
    )
    assert outcome.manifest is None
