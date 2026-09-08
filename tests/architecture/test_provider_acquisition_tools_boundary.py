from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[2]
TOOLS = ROOT / "tools/acquisition"
PACKAGES = ROOT / "packages"


def test_acquisition_tools_stay_out_of_runtime_packages_and_keep_secrets_external() -> None:
    sources = {
        path: path.read_text()
        for path in TOOLS.glob("*.py")
        if path.name != "__init__.py"
    }
    for path, source in sources.items():
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
        ), path
    tushare_source = sources[TOOLS / "cn_a_share_tushare.py"]
    assert "config/settings.json" not in tushare_source
    assert "TUSHARE_TOKEN" in tushare_source

    package_sources = "\n".join(
        path.read_text()
        for path in PACKAGES.glob("*/src/**/*.py")
        if path.is_file()
    )
    assert "tools.acquisition" not in package_sources
