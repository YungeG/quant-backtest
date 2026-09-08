from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_minute.py"
BUNDLE = ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_minute_bundle.py"
MONTH = ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_000703_january_2024_minute_authority.py"
ROOT_INIT = ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"


def test_tushare_minute_normalizer_and_publication_stay_private_builder_only() -> None:
    source = MODULE.read_text(encoding="utf-8")
    bundle_source = BUNDLE.read_text(encoding="utf-8")
    month_source = MONTH.read_text(encoding="utf-8")
    imports = {
        node.module or ""
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    } | {
        node.module or ""
        for source in (bundle_source, month_source)
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    }
    root_source = ROOT_INIT.read_text(encoding="utf-8")

    assert MODULE.is_file() and BUNDLE.is_file() and MONTH.is_file()
    assert not any(name.startswith(("crypto_quant_trading", "crypto_quant_backtest")) for name in imports)
    assert "from .bar_aggregation import BarBucket" in source
    assert "TushareCnAShareMinute" not in root_source
    assert "tushare_cn_a_share_minute_bundle" not in root_source
    assert "tushare_000703_january_2024_minute_authority" not in root_source
