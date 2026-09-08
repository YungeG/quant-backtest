from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotFailureCode,
    SyntheticJsonlV1NormalizationFailureCode,
    SyntheticJsonlV1RecordLocator,
    freeze_source_snapshot,
    normalize_synthetic_jsonl_v1,
)
from crypto_quant_domain import InstrumentId, PricePurpose, VenueId

from tests.bundle_builder.normalization._fixtures import (
    JSONL,
    ROOT_LINE,
    config,
    provenance,
    snapshot,
)


def test_synthetic_jsonl_normalizes_in_physical_order_with_exact_trace() -> None:
    outcome = normalize_synthetic_jsonl_v1(snapshot(), config())

    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert [event.revision_id for event in result.events] == ["v1", "v2", "f1"]
    assert [event.source_sequence.value for event in result.events] == [0, 1, 2]
    assert [event.payload["price_purpose"] for event in result.events] == [
        "valuation",
        "valuation",
        "funding",
    ]
    assert result.events[1].supersedes_revision_id == "v1"
    assert result.traces[1].event_hash == result.events[1].event_hash
    locator = SyntheticJsonlV1RecordLocator("prices.jsonl", 2)
    assert result.event_for_source_record(locator) == result.events[1]
    assert result.trace_for_event(result.events[1].event_id) == result.traces[1]
    assert result.event_for_source_record(
        SyntheticJsonlV1RecordLocator("prices.jsonl", 99)
    ) is None


def test_empty_member_is_success_without_coverage_claim() -> None:
    outcome = normalize_synthetic_jsonl_v1(snapshot(b""), config())

    assert outcome.result is not None
    assert outcome.result.events == ()
    assert outcome.result.traces == ()
    assert outcome.result.decision_grade_eligible is False
    assert outcome.result.deployment_authorized is False


def test_binding_order_is_identity_invariant() -> None:
    first = config()
    reversed_purposes = config(purposes=tuple(reversed(first.price_purpose_bindings)))

    assert first == reversed_purposes
    assert first.config_hash == reversed_purposes.config_hash


def test_provenance_source_and_content_identity_sensitivity() -> None:
    baseline = normalize_synthetic_jsonl_v1(snapshot(), config()).result
    provenance_only_snapshot = freeze_source_snapshot(
        members=(RawSourceMember("prices.jsonl", JSONL, "0644", 999, None),),
        provenance=replace(provenance(), license_ref="license.changed"),
    ).snapshot
    assert provenance_only_snapshot is not None
    provenance_only = normalize_synthetic_jsonl_v1(
        provenance_only_snapshot, config()
    ).result
    changed_source = normalize_synthetic_jsonl_v1(
        snapshot(source_key="fixture.other"), config()
    ).result
    changed_content = normalize_synthetic_jsonl_v1(
        snapshot(JSONL.replace(b"12345", b"12346", 1)), config()
    ).result
    assert all(
        value is not None
        for value in (baseline, provenance_only, changed_source, changed_content)
    )
    assert baseline is not None and provenance_only is not None
    assert changed_source is not None and changed_content is not None

    assert baseline.events[0].event_id == provenance_only.events[0].event_id
    assert baseline.normalization_hash != provenance_only.normalization_hash
    assert baseline.events[0].event_id != changed_source.events[0].event_id
    assert baseline.events[0].event_id != changed_content.events[0].event_id


@pytest.mark.parametrize(
    ("value", "code"),
    (
        (b"\xef\xbb\xbf" + ROOT_LINE + b"\n", SyntheticJsonlV1NormalizationFailureCode.MEMBER_ENCODING_INVALID),
        (ROOT_LINE, SyntheticJsonlV1NormalizationFailureCode.JSONL_LAYOUT_INVALID),
        (ROOT_LINE + b"\n\n", SyntheticJsonlV1NormalizationFailureCode.JSONL_LAYOUT_INVALID),
        (b"{bad}\n", SyntheticJsonlV1NormalizationFailureCode.JSON_INVALID),
        (ROOT_LINE.replace(b'"available_time_epoch_nanoseconds":110,"event_time_epoch_nanoseconds":100', b'"event_time_epoch_nanoseconds":100,"available_time_epoch_nanoseconds":110') + b"\n", SyntheticJsonlV1NormalizationFailureCode.NONCANONICAL_JSON),
        (ROOT_LINE.replace(b'"record_key":"btc-close",', b"") + b"\n", SyntheticJsonlV1NormalizationFailureCode.RECORD_SHAPE_INVALID),
        (ROOT_LINE.replace(b'"schema_version":1', b'"schema_version":2') + b"\n", SyntheticJsonlV1NormalizationFailureCode.UNSUPPORTED_RECORD_SCHEMA),
        (ROOT_LINE.replace(b'"price_units":12345', b'"price_units":0') + b"\n", SyntheticJsonlV1NormalizationFailureCode.RECORD_FIELD_INVALID),
    ),
)
def test_layout_and_record_failures_are_structured(
    value: bytes, code: SyntheticJsonlV1NormalizationFailureCode
) -> None:
    outcome = normalize_synthetic_jsonl_v1(snapshot(value), config())

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is code


def test_unmapped_aliases_fail_without_partial_output() -> None:
    unmapped_instrument = config(
        instruments=(("ETHUSDT", InstrumentId(VenueId("test"), "eth-usdt")),)
    )
    unmapped_purpose = config(purposes=(("funding", PricePurpose.FUNDING),))

    first = normalize_synthetic_jsonl_v1(snapshot(), unmapped_instrument)
    second = normalize_synthetic_jsonl_v1(snapshot(), unmapped_purpose)

    assert first.result is second.result is None
    assert first.failure is not None
    assert first.failure.code is SyntheticJsonlV1NormalizationFailureCode.INSTRUMENT_UNMAPPED
    assert second.failure is not None
    assert second.failure.code is SyntheticJsonlV1NormalizationFailureCode.PRICE_PURPOSE_UNMAPPED


def test_invalid_snapshot_and_missing_member_precede_parsing() -> None:
    current = snapshot()
    forged = replace(current, archive_bytes=b"bad")
    missing_config = replace(config(), member_key="missing.jsonl")

    invalid = normalize_synthetic_jsonl_v1(forged, config())
    missing = normalize_synthetic_jsonl_v1(current, missing_config)

    assert invalid.failure is not None
    assert invalid.failure.code is SyntheticJsonlV1NormalizationFailureCode.SOURCE_SNAPSHOT_INVALID
    assert missing.failure is not None
    assert missing.failure.code is SyntheticJsonlV1NormalizationFailureCode.SELECTED_MEMBER_MISSING


def test_config_and_result_reject_forged_relations() -> None:
    with pytest.raises(ValueError, match="unique"):
        config(
            purposes=(
                ("valuation", PricePurpose.VALUATION),
                ("valuation", PricePurpose.FUNDING),
            )
        )
    result = normalize_synthetic_jsonl_v1(snapshot(), config()).result
    assert result is not None
    with pytest.raises(ValueError, match="exact-cover"):
        replace(result, traces=result.traces[:-1])
    with pytest.raises(ValueError, match="qualification"):
        replace(result, deployment_authorized=True)
