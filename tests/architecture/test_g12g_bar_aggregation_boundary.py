from __future__ import annotations

import ast
from pathlib import Path

from crypto_quant_bundle_builder import aggregate_bars_v1

ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/bar_aggregation.py"
)
ALLOWED_IMPORTS = {
    "__future__",
    "dataclasses",
    "enum",
    "typing",
    "crypto_quant_domain",
    "crypto_quant_market_data",
    "bundle_validation",
    ".bundle_validation",
}
G12G_EXPORTS = {
    "BarAggregationFailure",
    "BarAggregationFailureCode",
    "BarAggregationManifest",
    "BarAggregationOutcome",
    "BarAggregationResult",
    "BarBucket",
    "BarBucketPlan",
    "BarDefinition",
    "aggregate_bars_v1",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    return imports


def test_bar_aggregation_module_uses_only_public_offline_contracts() -> None:
    assert MODULE.is_file()
    assert _imports(MODULE) <= ALLOWED_IMPORTS
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "crypto_quant_domain.",
        "crypto_quant_market_data.",
        "crypto_quant_trading",
        "crypto_quant_backtest",
        "builtins.open(",
        "os.",
        "pathlib",
        "socket",
        "subprocess",
        "requests",
        "urllib",
        "datetime.now",
    ):
        assert forbidden not in source


def test_builder_root_exactly_adds_frozen_g12g_exports() -> None:
    import crypto_quant_bundle_builder as builder

    assert G12G_EXPORTS <= set(builder.__all__)
    assert len(set(builder.__all__)) == 38
    assert builder.aggregate_bars_v1 is aggregate_bars_v1


def test_runtime_and_kernel_do_not_import_builder_bar_aggregation() -> None:
    for directory in (
        ROOT / "packages/backtest-runtime/src",
        ROOT / "packages/trading-kernel/src",
    ):
        for path in directory.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "crypto_quant_bundle_builder.bar_aggregation" not in source
            assert "aggregate_bars_v1" not in source
