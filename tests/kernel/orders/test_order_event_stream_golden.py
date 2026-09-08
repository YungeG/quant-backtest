from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_domain import canonical_sha256
from crypto_quant_trading import OrderEventStream

from ._fixtures import full_lifecycle_records, order


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "tests/fixtures/kernel/order-event-state-replay-v1.json"


def test_order_event_state_replay_matches_the_frozen_golden() -> None:
    try:
        expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid frozen Order Event fixture: {error}")

    subject = order()
    records = full_lifecycle_records(subject)
    stream = OrderEventStream.from_records(subject, tuple(reversed(records)))
    states = tuple(stream.state_at(position) for position in range(stream.event_count + 1))

    actual = {
        "fixture_id": "order-event-state-replay-v1",
        "ordered_event_types": [record.event.event_type.value for record in stream.records],
        "ordered_event_ids": [record.event.event_id for record in stream.records],
        "state_statuses": [None if state is None else state.status.value for state in states],
        "cumulative_fill_units": [
            None if state is None else state.cumulative_filled_quantity.units
            for state in states
        ],
        "remaining_units": [
            None if state is None else state.remaining_quantity.units for state in states
        ],
        "record_hashes": list(stream.record_hashes),
        "state_hashes": [
            stream.state_hash_at(position) for position in range(stream.event_count + 1)
        ],
        "stream_hash": stream.stream_hash,
        "final_state_hash": stream.state_hash,
        "canonical_stream_hash": canonical_sha256(stream),
    }

    assert actual == expected
