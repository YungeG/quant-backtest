from __future__ import annotations

import ast
from pathlib import Path

import crypto_quant_backtest

_ROOT = Path(__file__).resolve().parents[3]
_RUNTIME = _ROOT / "packages/backtest-runtime/src/crypto_quant_backtest"
_ANALYSIS = _RUNTIME / "analysis.py"
_PUBLIC_INIT = _RUNTIME / "__init__.py"
_PUBLIC_NAMES = {
    "AnalysisArtifactRef",
    "BacktestAnalysis",
    "BacktestMetricProfile",
    "VerifiedBacktestAnalysis",
}


def _tree(path: Path) -> ast.Module:
    assert path.exists(), f"BT-GAP-06 RED: missing {path.relative_to(_ROOT)}"
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_analysis_schema_has_one_exact_passive_public_surface() -> None:
    module = _tree(_ANALYSIS)
    public_classes = {
        node.name
        for node in module.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    }
    public_functions = {
        node.name
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert public_classes == _PUBLIC_NAMES
    assert public_functions == set()

    source = _ANALYSIS.read_text(encoding="utf-8")
    for forbidden in (
        "SchemaCatalog",
        "ArtifactEnvelopeReader",
        "Repository",
        "MetricRegistry",
        "MetricEngine",
        "derive(",
        "load_analysis",
        "from_canonical_dict",
        "object.__new__",
        "__getattr__",
        "EngineExecutionResult",
        "crypto_quant_platform",
        "crypto_quant_foundation",
        "tests.support",
        "pathlib",
        "urllib",
        "requests",
        "httpx",
    ):
        assert forbidden not in source


def test_analysis_contract_exports_only_values_not_runtime_or_storage() -> None:
    source = _PUBLIC_INIT.read_text(encoding="utf-8")
    for name in _PUBLIC_NAMES:
        assert name in source, f"BT-GAP-06 RED: {name} is not root-exported"
        assert name in crypto_quant_backtest.__all__
    for forbidden in (
        "BacktestAnalysisRepository",
        "BacktestAnalysisReader",
        "BacktestMetricRegistry",
    ):
        assert forbidden not in source


def test_analysis_module_imports_only_existing_public_authorities() -> None:
    module = _tree(_ANALYSIS)
    imports = {
        node.module or ""
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom)
    }
    imports.update(
        alias.name
        for node in ast.walk(module)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert imports <= {
        "__future__",
        "dataclasses",
        "re",
        "crypto_quant_domain",
        "integrity",
        "publication_refs",
    }
