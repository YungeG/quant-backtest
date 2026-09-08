from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[2]
MODULE = ROOT / "tools/acquisition/cn_a_share_tushare_authority.py"
PACKAGES = ROOT / "packages"


def test_tushare_authority_acquisition_stays_additive_tool_only() -> None:
    assert MODULE.is_file(), "G12L authority acquisition RED: missing tool module"
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
    assert not imports.intersection({"httpx", "requests", "socket"})
    assert "TUSHARE_TOKEN" in source
    assert "config/settings.json" not in source
    for forbidden in ("Protocol", "Adapter", "Factory", "Registry", "Cache"):
        assert forbidden not in source

    package_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in PACKAGES.glob("*/src/**/*.py")
        if path.is_file()
    )
    assert "cn_a_share_tushare_authority" not in package_sources
