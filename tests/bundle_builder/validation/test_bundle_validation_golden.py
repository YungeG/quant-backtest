from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_bundle_builder import validate_market_bundle_v1
from crypto_quant_domain import UtcInstant, canonical_bytes, canonical_sha256
from crypto_quant_market_data import MarketBundleRef

from tests.bundle_builder.validation._fixtures import (
    call,
    replace_event_key,
    replace_event_type,
    replace_source_hash,
    replace_source_key,
    replace_source_sequence,
    replace_stream_key,
    synthetic_events,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests/fixtures/market_data/validation"
GOLDEN = FIXTURES / "synthetic-jsonl-bundle-validation-v1.expected.json"


def _payload() -> dict[str, object]:
    events = synthetic_events()
    coverage_end = UtcInstant(1_000)

    bundle = validate_market_bundle_v1(
        bundle_key="synthetic-jsonl-bundle-validation-v1",
        schema_version=1,
        coverage_start=events[0].event_time,
        coverage_end_exclusive=coverage_end,
        instrument_catalog_hash="sha256:" + "b" * 64,
        events=events,
    )
    assert bundle.manifest is not None

    outside = validate_market_bundle_v1(
        bundle_key="synthetic-jsonl-bundle-validation-v1",
        schema_version=1,
        coverage_start=events[0].event_time,
        coverage_end_exclusive=UtcInstant(200),
        instrument_catalog_hash="sha256:" + "b" * 64,
        events=(events[0], events[2]),
    )
    duplicate = validate_market_bundle_v1(
        bundle_key="synthetic-jsonl-bundle-validation-v1",
        schema_version=1,
        coverage_start=events[0].event_time,
        coverage_end_exclusive=coverage_end,
        instrument_catalog_hash="sha256:" + "b" * 64,
        events=(events[0], events[0]),
    )
    classification = validate_market_bundle_v1(
        bundle_key="synthetic-jsonl-bundle-validation-v1",
        schema_version=1,
        coverage_start=events[0].event_time,
        coverage_end_exclusive=coverage_end,
        instrument_catalog_hash="sha256:" + "b" * 64,
        events=(
            events[0],
            replace_event_type(events[1], "other"),
            events[2],
        ),
    )
    duplicate_order = validate_market_bundle_v1(
        bundle_key="synthetic-jsonl-bundle-validation-v1",
        schema_version=1,
        coverage_start=events[0].event_time,
        coverage_end_exclusive=coverage_end,
        instrument_catalog_hash="sha256:" + "b" * 64,
        events=(
            events[0],
            replace_event_key(events[1], "synthetic-jsonl-duplicate-ordering"),
            events[1],
        ),
    )
    handoff = validate_market_bundle_v1(
        bundle_key="synthetic-jsonl-bundle-validation-v1",
        schema_version=1,
        coverage_start=events[0].event_time,
        coverage_end_exclusive=coverage_end,
        instrument_catalog_hash="sha256:" + "b" * 64,
        events=(
            events[0],
            replace_stream_key(replace_event_key(events[0], "right"), "stream.other"),
        ),
    )
    noncontig = validate_market_bundle_v1(
        bundle_key="synthetic-jsonl-bundle-validation-v1",
        schema_version=1,
        coverage_start=events[0].event_time,
        coverage_end_exclusive=coverage_end,
        instrument_catalog_hash="sha256:" + "b" * 64,
        events=(
            replace_source_sequence(events[0], 1),
            replace_source_sequence(events[1], 99),
        ),
    )
    empty = validate_market_bundle_v1(
        bundle_key="synthetic-jsonl-bundle-validation-v1",
        schema_version=1,
        coverage_start=events[0].event_time,
        coverage_end_exclusive=coverage_end,
        instrument_catalog_hash="sha256:" + "b" * 64,
        events=(),
    )
    malformed = validate_market_bundle_v1(
        bundle_key="synthetic-jsonl-bundle-validation-v1",
        schema_version=1,
        coverage_start=events[0].event_time,
        coverage_end_exclusive=coverage_end,
        instrument_catalog_hash="sha256:" + "b" * 64,
        events=(
            {"event_id": "malformed"},
        ),
    )
    atomic = validate_market_bundle_v1(
        bundle_key="synthetic-jsonl-bundle-validation-v1",
        schema_version=1,
        coverage_start=events[0].event_time,
        coverage_end_exclusive=coverage_end,
        instrument_catalog_hash="sha256:" + "b" * 64,
        events=(events[0], events[0]),
    )

    source_hash_mutated = call(
        (
            replace_source_hash(events[0], "sha256:" + "c" * 64),
            *events[1:],
        )
    )
    source_key_mutated = call(
        (
            replace_source_key(events[0], "fixture.other.source"),
            *events[1:],
        )
    )
    ordering_left = replace_event_key(events[0], "a")
    ordering_right = replace_stream_key(replace_event_key(events[1], "b"), "other.stream")
    ordering = call((ordering_left, ordering_right))

    return {
        "schema_version": 1,
        "fixture_id": "synthetic-jsonl-bundle-validation-v1",
        "bundle_manifest": bundle.manifest.to_canonical_dict(),
        "bundle_ref": MarketBundleRef.from_manifest(bundle.manifest).to_canonical_dict(),
        "result_hash": canonical_sha256(bundle.manifest),
        "event_count": len(events),
        "stream_count": len(bundle.manifest.streams),
        "stream_keys": tuple(stream.stream_key for stream in bundle.manifest.streams),
        "stream_hashes": {
            stream.stream_key: stream.content_hash for stream in bundle.manifest.streams
        },
        "capabilities": [
            capability.to_canonical_dict() for capability in bundle.manifest.capabilities
        ],
        "source_sensitivity": {
            "base_hash": bundle.manifest.content_hash,
            "mutated_hash": source_hash_mutated.manifest.content_hash,
            "source_key_hash": source_key_mutated.manifest.content_hash,
        },
        "failure_precedence": {
            "event_outside_coverage": outside.failure.to_canonical_dict()
            if outside.failure
            else None,
            "duplicate_event_id": duplicate.failure.to_canonical_dict()
            if duplicate.failure
            else None,
            "stream_classification_mismatch": classification.failure.to_canonical_dict()
            if classification.failure
            else None,
            "duplicate_stream_ordering_key": duplicate_order.failure.to_canonical_dict()
            if duplicate_order.failure
            else None,
            "handoff_success": handoff.failure is None,
            "non_contiguous_success": noncontig.failure is None,
        },
        "invalid_input": {
            "empty": malformed.failure.to_canonical_dict()
            if malformed.failure
            else None,
        },
        "cross_stream_ordering": {
            "equal_order_allowed": handoff.failure is None,
            "left_order_key": handoff.manifest.streams[0].stream_key
            if handoff.manifest
            else None,
            "right_order_key": handoff.manifest.streams[1].stream_key
            if handoff.manifest
            else None,
        },
        "empty_result": {
            "failure": empty.failure.to_canonical_dict() if empty.failure else None,
            "manifest": empty.manifest.to_canonical_dict() if empty.manifest else None,
        },
        "atomic_no_manifest_failure": atomic.manifest is None,
    }


def test_bundle_validation_fixture_matches_static_golden() -> None:
    try:
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid G12C golden fixture: {error}") from error

    actual = json.loads(canonical_bytes(_payload()))
    assert actual == expected
