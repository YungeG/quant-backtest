from __future__ import annotations

import json
from pathlib import Path


DECLARATION = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "fixtures/market_data/rule_authorities/cn-a-share-development-v1/declaration.json"
    ).read_text()
)


def test_current_five_dimension_authority_has_no_common_g12h_target() -> None:
    target = DECLARATION["target_coverage"]
    target_start = target["start_epoch_nanoseconds"]
    target_end = target["end_exclusive_epoch_nanoseconds"]
    authorities = DECLARATION["authorities"]

    calendar = authorities["calendar"]["body"]
    assert (calendar["coverage_start"], calendar["coverage_end_exclusive"]) == (
        "2026-07-06",
        "2026-07-31",
    )
    order_bands = [
        band
        for band in authorities["order_rules"]["body"]["bands"]
        if band["venue_id"]["value"] == "xshe" and band["board"] == "main"
    ]
    assert [
        (band["effective_from"], band["effective_to_exclusive"])
        for band in order_bands
    ] == [("2026-07-06", "2026-07-31")]
    corporate_action_bands = [
        band
        for band in authorities["corporate_action_entitlements"]["body"]["bands"]
        if band["venue_id"]["value"] == "xshe"
    ]
    assert [
        (
            band["effective_start"]["epoch_nanoseconds"],
            band["effective_end"]["epoch_nanoseconds"],
        )
        for band in corporate_action_bands
    ] == [(target_start, target_end)]

    gaps = []
    for dimension in ("market_fees", "stamp_duty"):
        bands = [
            band
            for band in authorities[dimension]["body"]["bands"]
            if band["venue_id"]["value"] == "xshe"
        ]
        assert [
            (
                band["effective_from"]["epoch_nanoseconds"],
                band["effective_to_exclusive"]["epoch_nanoseconds"],
            )
            for band in bands
        ] == [
            (1_692_892_800_000_000_000, 1_693_152_000_000_000_000),
            (1_693_152_000_000_000_000, 1_693_324_800_000_000_000),
        ]
        if max(band["effective_to_exclusive"]["epoch_nanoseconds"] for band in bands) <= target_start:
            gaps.append(dimension)

    assert gaps == ["market_fees", "stamp_duty"]
    assert gaps[0] == "market_fees"
