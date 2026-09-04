from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[2]
MODULE = ROOT / "tools/acquisition/cn_a_share_tushare_listing_source_bounded_v2.py"
OFFICIAL = ROOT / "tools/acquisition/cn_a_share_tushare.py"


def test_approved_proxy_acquisition_is_exact_additive_and_tool_only() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
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
        name.startswith(("crypto_quant_backtest", "crypto_quant_trading"))
        for name in imports
    )
    assert not imports.intersection({"httpx", "requests", "socket", "tushare"})
    for required in (
        "TUSHARE_PROXY_TOKEN",
        '"x-api-key"',
        '"Accept-Encoding": "gzip"',
        '"https://fast.xiaodefa.cn"',
        '"https://tt.xiaodefa.cn"',
        'vendor_key="tushare.pro"',
        "xiaodefa.approved-tushare-proxy.v1",
        '"stock_basic"',
        '"bak_basic"',
        '"namechange"',
        '_FIXED_TS_CODE = "000001.SZ"',
        '_FIXED_TRADE_DATE = "20240102"',
        "_NoRedirect",
        '"absence_authority": False',
        "len(token) != 56",
    ):
        assert required in source
    for forbidden in (
        "TUSHARE_TOKEN",
        "Protocol",
        "Adapter",
        "Factory",
        "Registry",
        "Cache",
        "crypto_quant_platform",
    ):
        assert forbidden not in source

    assert 'parser.add_argument("--ts-code"' not in source
    assert 'parser.add_argument("--trade-date"' not in source

    official = OFFICIAL.read_text(encoding="utf-8")
    assert "xiaodefa" not in official
    assert "TUSHARE_PROXY_TOKEN" not in official
