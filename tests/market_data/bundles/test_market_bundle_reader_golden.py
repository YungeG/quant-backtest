from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_domain import canonical_bytes, canonical_sha256
from crypto_quant_market_data import (
    EventCursor,
    InMemoryMarketBundleReader,
    InputValidationFailure,
    MarketBundleCapability,
)
from tests.market_data.bundles._fixtures import reader


ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests/fixtures/market_data/in-memory-market-bundle-reader-v1.json"


def collect_ids(
    bundle: InMemoryMarketBundleReader, cursor: EventCursor
) -> tuple[str, ...]:
    result: list[str] = []
    while not cursor.exhausted:
        batch, cursor = bundle.read_batch(cursor)
        result.extend(item.event_id for item in batch)
    return tuple(result)


def test_in_memory_market_bundle_reader_matches_canonical_golden() -> None:
    bundle = reader()
    missing = bundle.validate_requirements(
        required_capabilities=(
            MarketBundleCapability(key="funding_publications", version=1),
        )
    )
    assert isinstance(missing, InputValidationFailure)

    batch_orders: dict[str, list[str]] = {}
    for size in (1, 2, 10):
        cursor = bundle.open_cursor("bars.1m", batch_size=size)
        assert isinstance(cursor, EventCursor)
        batch_orders[str(size)] = list(collect_ids(bundle, cursor))

    actual = json.loads(
        canonical_bytes(
            {
                "schema_version": 1,
                "bundle_ref": bundle.bundle_ref.to_canonical_dict(),
                "manifest": bundle.manifest.to_canonical_dict(),
                "event_hashes": [
                    event.event_hash for event in bundle.streams["bars.1m"]
                ],
                "batch_orders": batch_orders,
                "missing_capability": missing.to_canonical_dict(),
            }
        )
    )
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))

    assert actual == expected
    assert canonical_sha256(actual) == canonical_sha256(expected)
