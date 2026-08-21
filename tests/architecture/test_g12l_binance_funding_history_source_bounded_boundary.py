from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]
MODULE = ROOT / "tools/acquisition/binance_usdm.py"
TOOLS = ROOT / "tools/acquisition"
PACKAGES = ROOT / "packages"


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }


def function_arguments(path: Path, function_name: str) -> tuple[list[str], list[str]]:
    tree = ast.parse(path.read_text())
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    )
    return [arg.arg for arg in function.args.args], [
        arg.arg for arg in function.args.kwonlyargs
    ]


def test_g12l_binance_funding_history_source_bounded_stays_additive_tool_only() -> None:
    source = MODULE.read_text()
    imported = imports(MODULE)

    assert not any(
        name.startswith(("crypto_quant_backtest", "crypto_quant_trading"))
        for name in imported
    )
    assert not imported.intersection({"httpx", "requests", "socket", "urllib"})
    assert "acquire_funding_history" in source

    package_sources = "\n".join(
        path.read_text() for path in PACKAGES.glob("*/src/**/*.py") if path.is_file()
    )
    assert "funding_history_source_bounded_v2" not in package_sources
    assert (
        "acquire_binance_usdm_funding_history_source_bounded_v2" not in package_sources
    )


def test_g12l_binance_funding_history_source_bounded_keeps_tool_contract() -> None:
    assert function_arguments(
        MODULE,
        "acquire_funding_history",
    ) == (["request"], ["output_dir", "acquired_at_epoch_nanoseconds", "get", "sleep"])
    assert function_arguments(MODULE, "main") == (["argv"], [])


def test_g12l_no_second_binance_funding_history_acquisition_module_added() -> None:
    assert MODULE.is_file()
    assert all(
        path.name != "binance_usdm_funding_history_source_bounded_v2.py"
        for path in TOOLS.glob("*.py")
    )
