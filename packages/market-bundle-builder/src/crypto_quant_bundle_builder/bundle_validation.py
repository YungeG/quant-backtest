from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import cast

from crypto_quant_domain import UtcInstant, canonical_sha256
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketBundleIntegrityError,
    MarketBundleManifest,
    MarketEvent,
    MarketStreamManifest,
)

_SCHEMA_VERSION = 1


def _text(name: str, value: object) -> str:
    if type(value) is not str:
        raise ValueError(f"{name} must be text")
    if not value or value.strip() != value:
        raise ValueError(f"{name} must be nonempty canonical text")
    return value


def _hash(name: str, value: object) -> str:
    if type(value) is not str:
        raise ValueError(f"{name} must be canonical sha256")
    if not value.startswith("sha256:") or len(value) != 71:
        raise ValueError(f"{name} must be canonical sha256")
    for digit in value[7:]:
        if digit not in "0123456789abcdef":
            raise ValueError(f"{name} must be canonical sha256")
    return value


def _validate_tuple(name: str, value: tuple[object, ...], *, item_type: type[object]) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{name} must be tuple")
    if any(type(item) is not item_type for item in value):
        raise ValueError(f"{name} contains invalid item")
    return value


def _validate_events(events: tuple[object, ...]) -> tuple[MarketEvent, ...]:
    validated = cast(
        tuple[MarketEvent, ...],
        _validate_tuple("events", events, item_type=MarketEvent),
    )
    for event in validated:
        try:
            MarketEvent(
                event_id=event.event_id,
                stream_key=event.stream_key,
                event_type=event.event_type,
                capability=event.capability,
                instrument_id=event.instrument_id,
                event_time=event.event_time,
                available_time=event.available_time,
                phase=event.phase,
                source_sequence=event.source_sequence,
                revision_id=event.revision_id,
                supersedes_revision_id=event.supersedes_revision_id,
                source_key=event.source_key,
                source_hash=event.source_hash,
                payload=event.payload,
            )
        except MarketBundleIntegrityError as error:
            raise ValueError("event envelope is invalid") from error
    return validated


class BundleValidationFailureCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    DUPLICATE_EVENT_ID = "duplicate_event_id"
    EVENT_OUTSIDE_COVERAGE = "event_outside_coverage"
    STREAM_CLASSIFICATION_MISMATCH = "stream_classification_mismatch"
    DUPLICATE_STREAM_ORDERING_KEY = "duplicate_stream_ordering_key"
    STREAM_ORDER_REGRESSION = "stream_order_regression"


@dataclass(frozen=True, slots=True)
class BundleValidationFailure:
    code: BundleValidationFailureCode
    stream_key: str | None
    input_position: int | None

    def __post_init__(self) -> None:
        if type(self.code) is not BundleValidationFailureCode:
            raise TypeError("code must be BundleValidationFailureCode")
        if self.stream_key is not None:
            _text("stream_key", self.stream_key)
        if self.input_position is not None:
            if type(self.input_position) is not int or self.input_position < 0:
                raise ValueError("input_position must be a non-negative int")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "market_bundle_v1_validation_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "stream_key": self.stream_key,
            "input_position": self.input_position,
        }


@dataclass(frozen=True, slots=True)
class BundleValidationOutcome:
    manifest: MarketBundleManifest | None = None
    failure: BundleValidationFailure | None = None

    def __post_init__(self) -> None:
        if (self.manifest is None) == (self.failure is None):
            raise ValueError("outcome must have exactly one branch")
        if self.manifest is not None and not isinstance(self.manifest, MarketBundleManifest):
            raise TypeError("manifest must be MarketBundleManifest")
        if self.failure is not None and not isinstance(self.failure, BundleValidationFailure):
            raise TypeError("failure must be BundleValidationFailure")


def _invalid_input() -> BundleValidationOutcome:
    return BundleValidationOutcome(
        failure=BundleValidationFailure(
            code=BundleValidationFailureCode.INVALID_INPUT,
            stream_key=None,
            input_position=None,
        )
    )


def validate_market_bundle_v1(
    *,
    bundle_key: str,
    schema_version: int,
    coverage_start: UtcInstant,
    coverage_end_exclusive: UtcInstant,
    instrument_catalog_hash: str,
    events: tuple[MarketEvent, ...],
) -> BundleValidationOutcome:
    try:
        _text("bundle_key", bundle_key)
        if type(schema_version) is not int or schema_version <= 0:
            raise ValueError("schema_version must be positive integer")
        if not isinstance(coverage_start, UtcInstant) or not isinstance(
            coverage_end_exclusive, UtcInstant
        ):
            raise ValueError("coverage bounds must be UtcInstant")
        if (
            coverage_end_exclusive.epoch_nanoseconds
            <= coverage_start.epoch_nanoseconds
        ):
            raise ValueError("coverage interval must be non-empty")
        _hash("instrument_catalog_hash", instrument_catalog_hash)
        events = _validate_events(events)
    except (TypeError, ValueError):
        return _invalid_input()

    seen_event_ids: set[str] = set()
    for index, event in enumerate(events):
        if event.event_id in seen_event_ids:
            return BundleValidationOutcome(
                failure=BundleValidationFailure(
                    BundleValidationFailureCode.DUPLICATE_EVENT_ID,
                    event.stream_key,
                    index,
                )
            )
        seen_event_ids.add(event.event_id)

    for index, event in enumerate(events):
        if not (
            coverage_start.epoch_nanoseconds
            <= event.event_time.epoch_nanoseconds
            < coverage_end_exclusive.epoch_nanoseconds
        ):
            return BundleValidationOutcome(
                failure=BundleValidationFailure(
                    BundleValidationFailureCode.EVENT_OUTSIDE_COVERAGE,
                    event.stream_key,
                    index,
                )
            )

    stream_events: dict[str, list[tuple[int, MarketEvent]]] = defaultdict(list)
    for index, event in enumerate(events):
        stream_events[event.stream_key].append((index, event))

    for stream_key, indexed_events in stream_events.items():
        expected = (indexed_events[0][1].event_type, indexed_events[0][1].capability)
        mismatch = next(
            (
                index
                for index, event in indexed_events
                if (event.event_type, event.capability) != expected
            ),
            None,
        )
        if mismatch is not None:
            return BundleValidationOutcome(
                failure=BundleValidationFailure(
                    BundleValidationFailureCode.STREAM_CLASSIFICATION_MISMATCH,
                    stream_key,
                    mismatch,
                )
            )

    for stream_key, indexed_events in stream_events.items():
        ordering_keys: set[tuple[int, int, str, int]] = set()
        for index, event in indexed_events:
            if event.ordering_key in ordering_keys:
                return BundleValidationOutcome(
                    failure=BundleValidationFailure(
                        BundleValidationFailureCode.DUPLICATE_STREAM_ORDERING_KEY,
                        stream_key,
                        index,
                    )
                )
            ordering_keys.add(event.ordering_key)

    for stream_key, indexed_events in stream_events.items():
        previous: tuple[int, int, str, int] | None = None
        for index, event in indexed_events:
            if previous is not None and event.ordering_key < previous:
                return BundleValidationOutcome(
                    failure=BundleValidationFailure(
                        BundleValidationFailureCode.STREAM_ORDER_REGRESSION,
                        stream_key,
                        index,
                    )
                )
            previous = event.ordering_key

    try:
        stream_manifests = tuple(
            MarketStreamManifest.from_events(
                stream_key,
                tuple(event for _, event in indexed_events),
            )
            for stream_key, indexed_events in stream_events.items()
        )
        capabilities = tuple(
            sorted({stream.capability for stream in stream_manifests})
        )
        manifest = MarketBundleManifest.build(
            bundle_key=bundle_key,
            schema_version=schema_version,
            coverage_start=coverage_start,
            coverage_end_exclusive=coverage_end_exclusive,
            instrument_catalog_hash=instrument_catalog_hash,
            capabilities=capabilities,
            streams=stream_manifests,
        )
    except (TypeError, ValueError):
        return _invalid_input()

    return BundleValidationOutcome(manifest=manifest, failure=None)
