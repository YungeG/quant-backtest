from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_domain import canonical_sha256
from tests.bundle_builder.publication._fixtures import bundle_manifest
from tests.market_data.bundles._local_reader_fixtures import golden_payload


ROOT = Path(__file__).resolve().parents[3]
GOLDEN = (
    ROOT
    / "tests/fixtures/market_data/local-reader/local-market-bundle-reader-v1.expected.json"
)


def test_local_market_bundle_reader_matches_static_golden(tmp_path: Path) -> None:
    try:
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid G12E golden fixture: {error}") from error
    actual = golden_payload(tmp_path, bundle_manifest())

    assert actual == expected
    assert canonical_sha256(actual) == canonical_sha256(expected)
