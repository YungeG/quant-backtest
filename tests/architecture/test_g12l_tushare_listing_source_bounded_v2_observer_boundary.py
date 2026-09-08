from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_listing_source_bounded_v2.py"
)
BUILDER_ROOT = (
    ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
)


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }


def function_arguments(path: Path, function_name: str) -> tuple[list[str], list[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    )
    return [arg.arg for arg in function.args.args], [
        arg.arg for arg in function.args.kwonlyargs
    ]


def test_listing_observer_is_pure_provider_specific_and_in_memory() -> None:
    source = MODULE.read_text(encoding="utf-8")
    imported = imports(MODULE)

    assert function_arguments(
        MODULE,
        "observe_tushare_cn_a_share_listing_source_bounded_v2",
    ) == (
        [],
        [
            "acquisition_receipt_bytes",
            "snapshot",
            "instrument_catalog",
            "supersedes_report",
            "supersedes_acquisition_receipt_bytes",
            "supersedes_snapshot",
        ],
    )
    assert not any(
        name.startswith(("crypto_quant_backtest", "crypto_quant_trading"))
        for name in imported
    )
    assert not imported.intersection(
        {"httpx", "requests", "socket", "urllib", "pathlib", "os"}
    )
    for forbidden in (
        "MarketBundle",
        "MarketEvent",
        "Runtime",
        "Kernel",
        "LocalMarketBundleRepository",
        "open(",
        "repository head",
        "provider registry",
    ):
        assert forbidden not in source


def test_listing_observer_is_not_exported_or_imported_by_runtime_kernel() -> None:
    root_source = BUILDER_ROOT.read_text(encoding="utf-8")
    assert "TushareCnAShareListingSourceBoundedObservation" not in root_source
    assert "observe_tushare_cn_a_share_listing_source_bounded_v2" not in root_source

    runtime_kernel_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for package in ("backtest-runtime", "trading-kernel")
        for path in (ROOT / "packages" / package / "src").rglob("*.py")
    )
    assert "tushare_cn_a_share_listing_source_bounded_v2" not in runtime_kernel_sources
