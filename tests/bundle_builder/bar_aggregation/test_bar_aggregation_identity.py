from __future__ import annotations

from dataclasses import replace

from crypto_quant_bundle_builder import aggregate_bars_v1
from crypto_quant_domain import canonical_bytes, canonical_sha256

from crypto_quant_market_data import MarketBundleManifest
from tests.bundle_builder.bar_aggregation.test_bar_aggregation import (
    aggregate,
    bucket,
    definition,
    event,
    manifest,
    plan,
)


def test_repeat_output_is_exact_and_code_identity_changes_every_output_identity() -> (
    None
):
    events = (event(0, event_time=110, price_units=100),)
    bucket_plan = plan(bucket(100, 200))
    source_manifest = manifest(events)

    first = aggregate_bars_v1(
        source_manifest=source_manifest,
        source_events=events,
        bucket_plan=bucket_plan,
        definition=definition(),
        aggregation_code_hash=canonical_sha256("code-a"),
    )
    repeated = aggregate_bars_v1(
        source_manifest=source_manifest,
        source_events=events,
        bucket_plan=bucket_plan,
        definition=definition(),
        aggregation_code_hash=canonical_sha256("code-a"),
    )
    changed = aggregate_bars_v1(
        source_manifest=source_manifest,
        source_events=events,
        bucket_plan=bucket_plan,
        definition=definition(),
        aggregation_code_hash=canonical_sha256("code-b"),
    )

    assert first.result is not None
    assert repeated.result is not None
    assert changed.result is not None
    assert canonical_bytes(first.result) == canonical_bytes(repeated.result)
    assert (
        first.result.generated_events[0].revision_id
        != changed.result.generated_events[0].revision_id
    )
    assert (
        first.result.aggregation_manifest.output_bundle_ref
        != changed.result.aggregation_manifest.output_bundle_ref
    )


def test_source_event_identity_changes_bar_stream_and_output_bundle_identity() -> None:
    source = event(0, event_time=110, price_units=100)
    changed_source = replace(
        source,
        source_hash=canonical_sha256("changed-source-provenance"),
    )

    original = aggregate((source,))
    changed = aggregate((changed_source,))

    assert original.result is not None
    assert changed.result is not None
    original_bar = original.result.generated_events[0]
    changed_bar = changed.result.generated_events[0]
    assert original_bar.payload["close"] == changed_bar.payload["close"]
    assert original_bar.revision_id != changed_bar.revision_id
    assert (
        original.result.aggregation_manifest.source_stream_hash
        != changed.result.aggregation_manifest.source_stream_hash
    )
    assert (
        original.result.aggregation_manifest.output_stream_manifest
        != changed.result.aggregation_manifest.output_stream_manifest
    )
    assert (
        original.result.aggregation_manifest.output_bundle_ref
        != changed.result.aggregation_manifest.output_bundle_ref
    )


def test_empty_plan_and_out_of_plan_only_identities_are_distinct() -> None:
    events = (event(0, event_time=500, price_units=100),)
    empty_plan = aggregate(events, bucket_plan=plan())
    out_of_plan = aggregate(events, bucket_plan=plan(bucket(100, 200)))

    assert empty_plan.result is not None
    assert out_of_plan.result is not None
    assert len(empty_plan.result.generated_events) == 0
    assert len(out_of_plan.result.generated_events) == 0
    assert empty_plan.result.aggregation_manifest.input_event_count == 1
    assert out_of_plan.result.aggregation_manifest.input_event_count == 1
    assert (
        empty_plan.result.aggregation_manifest.output_bundle_ref
        != out_of_plan.result.aggregation_manifest.output_bundle_ref
    )

def test_source_bundle_ref_identity_changes_bar_and_bundle_identity() -> None:
    events = (event(0, event_time=110, price_units=100),)
    original = aggregate(events)
    original_manifest = manifest(events)
    changed_manifest = MarketBundleManifest.build(
        bundle_key="source.changed",
        schema_version=1,
        coverage_start=original_manifest.coverage_start,
        coverage_end_exclusive=original_manifest.coverage_end_exclusive,
        instrument_catalog_hash=original_manifest.instrument_catalog_hash,
        capabilities=original_manifest.capabilities,
        streams=original_manifest.streams,
    )
    changed = aggregate_bars_v1(
        source_manifest=changed_manifest,
        source_events=events,
        bucket_plan=plan(bucket(100, 200)),
        definition=definition(),
        aggregation_code_hash=canonical_sha256("aggregation-code"),
    )

    assert original.result is not None
    assert changed.result is not None
    assert (
        original.result.generated_events[0].revision_id
        != changed.result.generated_events[0].revision_id
    )
    assert (
        original.result.aggregation_manifest.output_bundle_ref
        != changed.result.aggregation_manifest.output_bundle_ref
    )
def test_bucket_plan_and_definition_identity_change_bar_and_bundle_identity() -> None:
    events = (event(0, event_time=110, price_units=100),)
    original = aggregate(events, bucket_plan=plan(bucket(100, 200)))
    changed_plan = aggregate(
        events,
        bucket_plan=replace(plan(bucket(100, 200)), plan_key="changed-plan"),
    )
    changed_definition = replace(
        definition(), key="changed-bars", output_stream_key="bars.changed"
    )
    changed_definition_outcome = aggregate_bars_v1(
        source_manifest=manifest(events),
        source_events=events,
        bucket_plan=plan(bucket(100, 200), value=changed_definition),
        definition=changed_definition,
        aggregation_code_hash=canonical_sha256("aggregation-code"),
    )

    assert original.result is not None
    assert changed_plan.result is not None
    assert changed_definition_outcome.result is not None
    original_bar = original.result.generated_events[0]
    assert (
        original_bar.revision_id != changed_plan.result.generated_events[0].revision_id
    )
    assert (
        original.result.aggregation_manifest.output_bundle_ref
        != changed_plan.result.aggregation_manifest.output_bundle_ref
    )
    assert (
        original_bar.revision_id
        != changed_definition_outcome.result.generated_events[0].revision_id
    )
    assert (
        original.result.aggregation_manifest.output_bundle_ref
        != changed_definition_outcome.result.aggregation_manifest.output_bundle_ref
    )
