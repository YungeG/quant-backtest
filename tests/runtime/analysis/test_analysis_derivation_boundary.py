from __future__ import annotations

import ast
from inspect import signature
from pathlib import Path

import crypto_quant_backtest
from crypto_quant_backtest import (
    BacktestAnalysisRuntime,
    VerifiedCompletedPublication,
    VerifiedCompletedPublicationV2,
)

_ROOT = Path(__file__).resolve().parents[3]
_RUNTIME = _ROOT / "packages/backtest-runtime/src/crypto_quant_backtest"
_DERIVATION = _RUNTIME / "analysis_derivation.py"
_VERIFIED = _RUNTIME / "verified_publications.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_derivation_has_one_exact_public_runtime_and_no_storage_framework() -> None:
    module = _tree(_DERIVATION)
    public_functions = {
        node.name
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    public_classes = {
        node.name
        for node in module.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    }
    assert public_functions == set()
    assert public_classes == {"BacktestAnalysisRuntime"}
    assert list(signature(BacktestAnalysisRuntime).parameters) == ["publisher"]
    assert list(signature(BacktestAnalysisRuntime.derive).parameters) == [
        "self",
        "completed",
        "metric_profile_ref",
    ]

    protocols = {
        node.name
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name.endswith("Publisher")
    }
    assert protocols == set()

    source = _DERIVATION.read_text(encoding="utf-8")
    assert "ArtifactEnvelopePublisher" in source
    for forbidden in (
        "crypto_quant_platform",
        "tests.support",
        "tests.",
        "Repository",
        "SchemaCatalog",
        "MetricRegistry",
        "MetricEngine",
        "ArtifactEnvelopeReader",
        "DeterministicBarEngine",
        "Path(",
        "pathlib",
        "cache",
        "simulator",
        "VerifiedBacktestAnalysis(",
        "def derive_backtest_analysis",
    ):
        assert forbidden not in source


def test_verified_publication_module_owns_one_minimal_completed_view() -> None:
    module = _tree(_VERIFIED)
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
    assert public_classes == {
        "VerifiedCompletedPublication",
        "VerifiedCompletedPublicationV2",
        "VerifiedExecutionSummary",
    }
    assert public_functions == set()
    assert list(signature(VerifiedCompletedPublication).parameters) == [
        "publication",
        "execution_case",
    ]
    assert list(signature(VerifiedCompletedPublicationV2).parameters) == [
        "source_publication_ref",
        "semantic_run_id",
        "source_execution_result_hash",
        "result_grade",
        "reporting_currency",
        "engine_context",
        "execution_summary",
    ]

    source = _VERIFIED.read_text(encoding="utf-8")
    for forbidden in (
        "crypto_quant_platform",
        "tests.support",
        "tests.",
        "Repository",
        "Protocol",
        "Factory",
        "Status",
        "Terminal",
        "Path(",
        "pathlib",
    ):
        assert forbidden not in source


def test_completed_view_and_runtime_are_root_exported_without_repository_api() -> None:
    assert crypto_quant_backtest.VerifiedCompletedPublication is (
        VerifiedCompletedPublication
    )
    assert crypto_quant_backtest.BacktestAnalysisRuntime is BacktestAnalysisRuntime
    assert not hasattr(crypto_quant_backtest, "derive_backtest_analysis")
    assert "VerifiedCompletedPublication" in crypto_quant_backtest.__all__
    assert "BacktestAnalysisRuntime" in crypto_quant_backtest.__all__
    assert "derive_backtest_analysis" not in crypto_quant_backtest.__all__
    for forbidden in (
        "BacktestAnalysisRepository",
        "BacktestAnalysisReader",
        "BacktestMetricRegistry",
    ):
        assert not hasattr(crypto_quant_backtest, forbidden)
