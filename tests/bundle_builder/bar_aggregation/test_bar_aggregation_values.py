from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import date

import pytest
from crypto_quant_bundle_builder import (
    BarAggregationFailure,
    BarAggregationFailureCode,
    BarAggregationManifest,
    BarAggregationOutcome,
    BarAggregationResult,
    BarBucket,
    BarBucketPlan,
    BarDefinition,
    aggregate_bars_v1,
)
from crypto_quant_domain import (
    PricePurpose,
    Scale,
    SessionId,
    TimelinePhase,
    TradingDate,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketBundleManifest,
    MarketBundleRef,
    MarketStreamManifest,
)
from tests.bundle_builder.bar_aggregation.test_bar_aggregation import (
    aggregate,
    event,
)

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64


def definition() -> BarDefinition:
    return BarDefinition(
        key="cn-equity-5m",
        version=1,
        output_stream_key="bars.cn-equity-5m",
        aggregation_kind="explicit_bucket_price_ohlc",
        source_stream_key="synthetic.prices",
        source_event_type="synthetic_price_point.v1",
        source_capability=MarketBundleCapability("synthetic_prices", 1),
        price_purpose=PricePurpose.VALUATION,
        price_scale=Scale(4),
        volume_semantics="none",
        empty_interval_policy="omit",
        output_phase=TimelinePhase(20, "bar.close"),
    )


def bucket() -> BarBucket:
    return BarBucket(
        session_id=SessionId("xshg", "2025-01-02.day"),
        trading_date=TradingDate("xshg", date(2025, 1, 2)),
        included_spans=((UtcInstant(100), UtcInstant(200)),),
        interval_start=UtcInstant(100),
        interval_end_exclusive=UtcInstant(200),
    )


def plan(value: BarDefinition | None = None) -> BarBucketPlan:
    selected = definition() if value is None else value
    return BarBucketPlan(
        plan_key="xshg-2025-01-02",
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(1_000),
        bar_definition_key=selected.key,
        bar_definition_version=selected.version,
        bar_definition_hash=selected.definition_hash,
        buckets=(bucket(),),
    )


def empty_result_values() -> tuple[BarAggregationManifest, MarketBundleManifest]:
    selected = definition()
    source_stream = MarketStreamManifest(
        stream_key=selected.source_stream_key,
        event_type=selected.source_event_type,
        capability=selected.source_capability,
        event_count=0,
        content_hash=HASH_A,
    )
    source_ref = MarketBundleRef("source", HASH_B)
    spec_hash = canonical_sha256(
        {
            "type": "bar_aggregation_spec",
            "schema_version": 1,
            "aggregation_id": "canonical_bar_aggregation@1",
        }
    )
    input_hash = canonical_sha256(
        {
            "type": "bar_aggregation_input",
            "schema_version": 1,
            "source_bundle_ref": source_ref.to_canonical_dict(),
            "source_stream_manifest": source_stream.to_canonical_dict(),
            "source_stream_hash": source_stream.content_hash,
            "definition_hash": selected.definition_hash,
            "bucket_plan_hash": HASH_B,
            "aggregation_spec_hash": spec_hash,
            "aggregation_code_hash": HASH_C,
        }
    )
    output = MarketBundleManifest.build(
        bundle_key="source.bar-aggregation-v1." + input_hash.removeprefix("sha256:"),
        schema_version=1,
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(1_000),
        instrument_catalog_hash=HASH_B,
        capabilities=(),
        streams=(),
    )
    manifest = BarAggregationManifest(
        source_bundle_ref=source_ref,
        source_stream_manifest=source_stream,
        source_stream_hash=source_stream.content_hash,
        bar_definition=selected,
        bucket_plan_key="empty-plan",
        bucket_plan_hash=HASH_B,
        aggregation_spec_hash=spec_hash,
        aggregation_code_hash=HASH_C,
        aggregation_input_hash=input_hash,
        input_event_count=0,
        source_stream_event_count=0,
        selected_source_revision_count=0,
        assigned_source_revision_count=0,
        out_of_plan_source_revision_count=0,
        nonselected_source_event_count=0,
        candidate_instrument_count=0,
        planned_bucket_count=0,
        empty_bucket_instrument_count=0,
        output_root_count=0,
        output_revision_count=0,
        output_stream_manifest=None,
        output_bundle_ref=MarketBundleRef.from_manifest(output),
        decision_grade_eligible=False,
        deployment_authorized=False,
    )
    return manifest, output


def test_public_root_exports_the_completed_milestone_one_values() -> None:
    assert all(
        value is not None
        for value in (
            BarBucket,
            BarBucketPlan,
            BarDefinition,
            BarAggregationManifest,
            BarAggregationResult,
            BarAggregationFailureCode,
            BarAggregationFailure,
            BarAggregationOutcome,
            aggregate_bars_v1,
        )
    )


def test_definition_hash_is_exact_nonrecursive_and_semantic() -> None:
    value = definition()
    expected_body = {
        "type": "bar_definition",
        "schema_version": 1,
        "key": value.key,
        "version": value.version,
        "output_stream_key": value.output_stream_key,
        "aggregation_kind": value.aggregation_kind,
        "source_stream_key": value.source_stream_key,
        "source_event_type": value.source_event_type,
        "source_capability": value.source_capability.to_canonical_dict(),
        "price_purpose": value.price_purpose.value,
        "price_scale": value.price_scale.places,
        "volume_semantics": value.volume_semantics,
        "empty_interval_policy": value.empty_interval_policy,
        "output_phase": value.output_phase.to_canonical_dict(),
    }

    assert value.definition_hash == canonical_sha256(expected_body)
    assert value.to_canonical_dict() == {
        **expected_body,
        "definition_hash": value.definition_hash,
    }
    assert replace(value, version=2).definition_hash != value.definition_hash
    assert replace(value, price_scale=Scale(5)).definition_hash != value.definition_hash


def test_definition_rejects_non_frozen_semantics_and_non_strict_scalars() -> None:
    value = definition()
    with pytest.raises(ValueError, match="stream keys"):
        replace(value, output_stream_key=value.source_stream_key)
    with pytest.raises(ValueError, match="aggregation_kind"):
        replace(value, aggregation_kind="vwap")
    with pytest.raises(ValueError, match="source_event_type"):
        replace(value, source_event_type="trade")
    with pytest.raises(ValueError, match="volume_semantics"):
        replace(value, volume_semantics="sum")
    with pytest.raises(ValueError, match="empty_interval_policy"):
        replace(value, empty_interval_policy="fill")
    with pytest.raises(ValueError, match="positive"):
        replace(value, version=True)
    with pytest.raises(FrozenInstanceError):
        value.key = "forged"  # type: ignore[misc]


def test_failure_codes_order_and_safe_value_shape_are_frozen() -> None:
    assert tuple(code.value for code in BarAggregationFailureCode) == (
        "invalid_input",
        "source_bundle_mismatch",
        "definition_bucket_plan_mismatch",
        "source_stream_mismatch",
        "source_coverage_unaligned",
        "source_event_invalid",
        "revision_chain_invalid",
        "output_causality_invalid",
        "output_validation_failed",
    )
    failure = BarAggregationFailure(
        code=BarAggregationFailureCode.SOURCE_EVENT_INVALID,
        stream_key="synthetic.prices",
        input_position=3,
        interval_hash=HASH_A,
    )
    assert failure.failure_hash == canonical_sha256(
        {
            "type": "bar_aggregation_failure",
            "schema_version": 1,
            "code": "source_event_invalid",
            "stream_key": "synthetic.prices",
            "input_position": 3,
            "interval_hash": HASH_A,
        }
    )
    with pytest.raises(ValueError, match="non-negative"):
        replace(failure, input_position=-1)
    with pytest.raises(ValueError, match="sha256"):
        replace(failure, interval_hash="unsafe")


def test_outcome_is_exactly_one_branch() -> None:
    failure = BarAggregationFailure(
        BarAggregationFailureCode.INVALID_INPUT, None, None, None
    )
    outcome = BarAggregationOutcome(result=None, failure=failure)

    assert outcome.failure == failure and outcome.result is None
    with pytest.raises(ValueError, match="exactly one"):
        BarAggregationOutcome(result=None, failure=None)
    with pytest.raises(ValueError, match="exactly one"):
        BarAggregationOutcome(  # type: ignore[arg-type]
            result="forged", failure=failure
        )


def test_manifest_result_counts_hash_and_false_flags_are_strict() -> None:
    manifest, output = empty_result_values()
    result = BarAggregationResult(
        generated_events=(),
        output_manifest=output,
        aggregation_manifest=manifest,
    )

    assert result.generated_events == ()
    assert manifest.manifest_hash == canonical_sha256(manifest._canonical_body())
    assert manifest.decision_grade_eligible is False
    assert manifest.deployment_authorized is False
    with pytest.raises(ValueError, match="counts do not reconcile"):
        replace(manifest, selected_source_revision_count=1)
    with pytest.raises(ValueError, match="counts do not reconcile"):
        replace(manifest, input_event_count=1, source_stream_event_count=1)
    with pytest.raises(ValueError, match="output roots cannot exceed"):
        replace(manifest, output_root_count=1)
    with pytest.raises(ValueError, match="non-empty output requires"):
        replace(manifest, output_revision_count=1)
    with pytest.raises(ValueError, match="qualification"):
        replace(manifest, deployment_authorized=True)
    with pytest.raises(ValueError, match="canonical_bar_aggregation"):
        replace(manifest, aggregation_spec_hash=HASH_A)

def test_result_forgery_is_rejected() -> None:
    manifest_val, output = empty_result_values()
    result = BarAggregationResult(
        generated_events=(),
        output_manifest=output,
        aggregation_manifest=manifest_val,
    )
    changed_manifest = MarketBundleManifest.build(
        bundle_key="forged",
        schema_version=1,
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(1_000),
        instrument_catalog_hash=output.instrument_catalog_hash,
        capabilities=(),
        streams=(),
    )
    with pytest.raises(ValueError, match="match aggregation output Bundle"):
        BarAggregationResult(
            generated_events=(),
            output_manifest=changed_manifest,
            aggregation_manifest=manifest_val,
        )


def test_nonempty_result_replace_forgery_is_rejected() -> None:
    outcome = aggregate((event(0, event_time=110, price_units=100),))
    assert outcome.result is not None
    result = outcome.result

    with pytest.raises(ValueError, match="Event count"):
        replace(result, generated_events=())
    with pytest.raises(ValueError, match="content hash"):
        replace(
            result,
            generated_events=(
                replace(result.generated_events[0], source_hash=HASH_A),
            ),
        )
    with pytest.raises(ValueError, match="root count"):
        replace(
            result,
            aggregation_manifest=replace(
                result.aggregation_manifest, output_root_count=0
            ),
        )


def test_all_public_values_require_explicit_constructor_arguments() -> None:
    for value_type in (
        BarBucket,
        BarBucketPlan,
        BarDefinition,
        BarAggregationManifest,
        BarAggregationResult,
        BarAggregationFailure,
        BarAggregationOutcome,
    ):
        with pytest.raises(TypeError):
            value_type()  # type: ignore[call-arg]
