from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder"
    / "tushare_cn_a_share_daily.py"
)
BUILDER_ROOT = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
)


def test_tushare_daily_normalizer_stays_internal_and_off_runtime_kernel() -> None:
    assert MODULE.is_file(), "G12B Tushare RED: missing internal normalizer module"
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
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
    assert not any(name.startswith("crypto_quant_trading") for name in imports)
    assert not any(name.startswith("crypto_quant_backtest") for name in imports)
    assert not any(name.startswith(("requests", "httpx", "urllib")) for name in imports)

    source = MODULE.read_text(encoding="utf-8")
    for forbidden in ("Protocol", "Factory", "Registry", "Repository", "Cache"):
        assert forbidden not in source

    root_source = BUILDER_ROOT.read_text(encoding="utf-8")
    assert "TushareCnAShareDaily" not in root_source
    assert "normalize_tushare_cn_a_share_daily_v1" not in root_source
