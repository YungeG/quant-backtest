from __future__ import annotations

import ast
from pathlib import Path

import crypto_quant_bundle_builder as builder


MODULE = (
    Path(__file__).parents[2]
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder"
    / "binance_usdm_aggtrades_archive.py"
)


def test_g12l_aggtrades_stays_off_frozen_root_and_out_of_runtime_kernel() -> None:
    assert not hasattr(builder, "capture_binance_usdm_aggregate_trades_archive")
    assert not hasattr(builder, "normalize_binance_usdm_aggregate_trades_archive")

    tree = ast.parse(MODULE.read_text())
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not any(
        name.startswith(("crypto_quant_trading", "crypto_quant_backtest"))
        for name in imports
    )
    assert not imports.intersection({"httpx", "requests", "socket", "urllib"})
