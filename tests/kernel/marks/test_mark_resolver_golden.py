from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    Price,
    PricePurpose,
    Scale,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import MarkObservation, MarkResolver, StaleMarkPolicy


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "tests/fixtures/kernel/deterministic-mark-resolution-v1.json"
INSTRUMENT = InstrumentId(VenueId("synthetic"), "asset-1")
USD = CurrencyId("USD")
POLICY = StaleMarkPolicy(
    policy_key="marks.valuation.v1",
    policy_version=1,
    price_purpose=PricePurpose.VALUATION,
    max_age_nanoseconds=20,
    allow_forward_fill=True,
)


def observation(
    event: str,
    *,
    observed_at: int,
    available_at: int,
    units: int,
    revision: str,
) -> MarkObservation:
    return MarkObservation(
        instrument_id=INSTRUMENT,
        quote_currency_id=USD,
        price_purpose=PricePurpose.VALUATION,
        price=Price(units, Scale(2), str(INSTRUMENT), str(USD)),
        observed_at=UtcInstant(observed_at),
        available_at=UtcInstant(available_at),
        stream_id="stream:valuation",
        source_event_id=f"event:{event}",
        revision_id=revision,
    )


def test_mark_resolution_matches_frozen_golden() -> None:
    try:
        expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid frozen mark-resolution fixture: {error}")

    older = observation(
        "older", observed_at=80, available_at=85, units=12_000, revision="revision:1"
    )
    selected = observation(
        "selected",
        observed_at=100,
        available_at=105,
        units=12_500,
        revision="revision:3",
    )
    resolver = MarkResolver()
    success = resolver.resolve(
        (selected, older),
        instrument_id=INSTRUMENT,
        price_purpose=PricePurpose.VALUATION,
        requested_at=UtcInstant(110),
        stale_policy=POLICY,
    )
    stale = resolver.resolve(
        (selected,),
        instrument_id=INSTRUMENT,
        price_purpose=PricePurpose.VALUATION,
        requested_at=UtcInstant(121),
        stale_policy=POLICY,
    )
    ambiguous = resolver.resolve(
        (
            selected,
            observation(
                "selected",
                observed_at=100,
                available_at=106,
                units=12_600,
                revision="revision:4",
            ),
        ),
        instrument_id=INSTRUMENT,
        price_purpose=PricePurpose.VALUATION,
        requested_at=UtcInstant(110),
        stale_policy=POLICY,
    )

    actual = {
        "fixture_id": "deterministic-mark-resolution-v1",
        "policy_hash": POLICY.policy_hash,
        "observation_hashes": sorted(
            (older.observation_hash, selected.observation_hash)
        ),
        "success": json.loads(canonical_bytes(success)),
        "success_hash": canonical_sha256(success),
        "stale_failure": json.loads(canonical_bytes(stale)),
        "ambiguous_failure": json.loads(canonical_bytes(ambiguous)),
    }

    assert actual == expected
