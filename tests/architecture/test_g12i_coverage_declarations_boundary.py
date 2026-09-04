import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/coverage_declarations.py"
)
ALLOWED_IMPORTS = {
    "__future__",
    "dataclasses",
    "enum",
    "typing",
    "crypto_quant_domain",
    "crypto_quant_market_data",
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


def test_coverage_declarations_module_uses_only_public_offline_contracts() -> None:
    assert MODULE.is_file()
    assert _imports(MODULE) <= ALLOWED_IMPORTS
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
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


def test_builder_root_exports_coverage_declarations() -> None:
    import crypto_quant_bundle_builder as builder

    exports = {
        "BuilderStaleMarkPolicy",
        "PricePurposeRequirement",
        "MarketAvailabilityReason",
        "AvailabilitySpan",
        "AvailabilityClosureDeclaration",
        "RevisionTerminalLineage",
        "RevisionClosureDeclaration",
    }
    assert exports <= set(builder.__all__)
    for blocked in (
        "PriceStreamCoverageReport",
        "MarketAvailabilityReport",
        "RevisionProvenanceReport",
    ):
        assert blocked not in builder.__all__
