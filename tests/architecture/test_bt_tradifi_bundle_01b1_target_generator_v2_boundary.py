from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/"
    "binance_usdm_koru_closed_market_range_targets_v2.py"
)


def test_v2_target_generator_reuses_frozen_rules_without_v1_source_materialization() -> (
    None
):
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "binance_usdm_koru_closed_market_range_targets_v1"
        for alias in node.names
    }

    assert "_stream_candidates" in imported
    assert "binance_usdm_koru_tradifi_source_projection_v1" not in source
    assert "build_binance_usdm_koru_tradifi_source_projection_v1" not in source
    for duplicated_rule in (
        "closed_market_range_long_entry",
        "closed_market_range_short_entry",
        "closed_market_range_max_hold_exit",
        "_PREMIUM_LIMIT",
        "_TARGET_EXPOSURE_FRACTION",
        "_PARAMETER_GRID",
    ):
        assert duplicated_rule not in source
