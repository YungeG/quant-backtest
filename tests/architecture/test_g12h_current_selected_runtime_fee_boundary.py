from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/"
    "cn_a_share_current_selected_fee_binding.py"
)
RUNTIME_ROOT = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/__init__.py"
EXISTING_V2 = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/"
    "cn_a_share_fee_v2_binding.py"
)


def test_current_selected_runtime_fee_fan_in_stays_off_root_and_io_free() -> None:
    source = MODULE.read_text()
    tree = ast.parse(source)
    imports = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert all(
        module.startswith(
            (
                "__future__",
                "collections",
                "dataclasses",
                "json",
                "typing",
                "crypto_quant_domain",
                "crypto_quant_market_data",
                "crypto_quant_trading",
                "cn_a_share_fee_v2_binding",
                "cn_a_share_profile",
                "engine",
                "resolution",
            )
        )
        for module in imports
    )
    for module in imports:
        lowered = module.lower()
        assert not any(
            forbidden in lowered
            for forbidden in ("provider", "network", "repository", "reader", "builder")
        )
    assert "crypto_quant_bundle_builder" not in source
    assert "cn_a_share_current_selected_fee_binding" not in RUNTIME_ROOT.read_text()
    assert "cn_a_share_current_selected_fee_binding" not in EXISTING_V2.read_text()
