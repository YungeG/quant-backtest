from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder"
PAYLOADS = BUILDER / "g12b_universe_corporate_action_payloads.py"
ANALYZER = BUILDER / "g12k_july_2026_development_coverage.py"
BUILDER_ROOT = BUILDER / "__init__.py"
ALLOWED_IMPORTS = {
    "__future__",
    "collections.abc",
    "dataclasses",
    "datetime",
    "enum",
    "typing",
    "crypto_quant_domain",
    "crypto_quant_market_data",
    "bundle_validation",
    "coverage_declarations",
    "g12b_universe_corporate_action_payloads",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").lstrip(".")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }


def test_g12k_is_non_root_exported_pure_builder_code() -> None:
    assert PAYLOADS.is_file()
    assert ANALYZER.is_file()
    assert _imports(PAYLOADS) <= ALLOWED_IMPORTS
    assert _imports(ANALYZER) <= ALLOWED_IMPORTS

    source = PAYLOADS.read_text(encoding="utf-8") + ANALYZER.read_text(encoding="utf-8")
    for forbidden in (
        "crypto_quant_backtest",
        "crypto_quant_trading",
        "Runtime",
        "Kernel",
        "Repository",
        "Reader",
        "Registry",
        "Framework",
        "Provider",
        "Factory",
        "Protocol",
        "pathlib",
        "builtins.open(",
        "socket",
        "subprocess",
        "requests",
        "urllib",
    ):
        assert forbidden not in source

    root_source = BUILDER_ROOT.read_text(encoding="utf-8")
    assert "g12k_july_2026_development_coverage" not in root_source
    assert "g12b_universe_corporate_action_payloads" not in root_source
    assert "G12K" not in root_source
    assert "G12BListingMembershipRevisionPayloadV1" not in root_source


def test_g12k_has_one_exact_analyzer_seam_and_frozen_concrete_types() -> None:
    tree = ast.parse(ANALYZER.read_text(encoding="utf-8"))
    public_functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]
    assert [node.name for node in public_functions] == [
        "analyze_g12k_july_2026_development_coverage_v1"
    ]
    function = public_functions[0]
    assert not function.args.args
    assert [argument.arg for argument in function.args.kwonlyargs] == [
        "manifest",
        "instrument_catalog",
        "events",
        "universe_closure",
        "corporate_action_closure",
    ]
    assert function.args.kw_defaults == [None] * 5
    assert function.returns is not None

    dataclass_names = {
        "G12KRevisionClosureDeclarationV1",
        "UniverseCoverageReport",
        "CorporateActionCoverageReport",
        "G12KJuly2026DevelopmentCoverageFailure",
        "G12KJuly2026DevelopmentCoverageOutcome",
    }
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    assert dataclass_names <= set(classes)
    for name in dataclass_names:
        decorators = classes[name].decorator_list
        assert any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Name)
            and decorator.func.id == "dataclass"
            and {
                keyword.arg: getattr(keyword.value, "value", None)
                for keyword in decorator.keywords
            }
            == {"frozen": True, "slots": True}
            for decorator in decorators
        )


def test_g12k_does_not_add_framework_registry_or_cross_layer_references() -> None:
    for directory in (
        ROOT / "packages/backtest-runtime/src/crypto_quant_backtest",
        ROOT / "packages/trading-kernel/src/crypto_quant_trading",
    ):
        for path in directory.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "g12k_july_2026_development_coverage" not in source
            assert "G12KRevisionClosureDeclarationV1" not in source
