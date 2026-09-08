from __future__ import annotations

from dataclasses import replace

from crypto_quant_bundle_builder import normalize_synthetic_jsonl_v1, validate_market_bundle_v1
from crypto_quant_domain import SourceSequence, UtcInstant
from crypto_quant_market_data import MarketEvent

from tests.bundle_builder.normalization._fixtures import config, snapshot


def bundle_header(**overrides: object) -> dict[str, object]:
    header: dict[str, object] = {
        "bundle_key": "synthetic-jsonl-bundle-validation-v1",
        "schema_version": 1,
        "coverage_start": UtcInstant(0),
        "coverage_end_exclusive": UtcInstant(1_000),
        "instrument_catalog_hash": "sha256:" + "b" * 64,
    }
    header.update(overrides)
    return header


def call(events: tuple[MarketEvent, ...], **overrides: object):
    return validate_market_bundle_v1(**bundle_header(**overrides), events=events)


def synthetic_events() -> tuple[MarketEvent, ...]:
    outcome = normalize_synthetic_jsonl_v1(snapshot(), config()).result
    assert outcome is not None
    return outcome.events


def replace_event_type(event: MarketEvent, value: str) -> MarketEvent:
    return replace(event, event_type=value)


def replace_event_key(event: MarketEvent, value: str) -> MarketEvent:
    return replace(event, event_id=value)


def replace_source_sequence(event: MarketEvent, value: int) -> MarketEvent:
    return replace(event, source_sequence=SourceSequence(value))


def replace_stream_key(event: MarketEvent, value: str) -> MarketEvent:
    return replace(event, stream_key=value)


def replace_source_hash(event: MarketEvent, value: str) -> MarketEvent:
    return replace(event, source_hash=value)


def replace_source_key(event: MarketEvent, value: str) -> MarketEvent:
    return replace(event, source_key=value)


def duplicate_event(event: MarketEvent, *, event_id: str | None = None) -> MarketEvent:
    return replace(event, event_id=event_id or event.event_id)
