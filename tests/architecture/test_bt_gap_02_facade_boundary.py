from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME = _ROOT / "packages/backtest-runtime/src/crypto_quant_backtest"
_FACADE = _RUNTIME / "facade.py"
_PUBLIC_ROOT = _RUNTIME / "__init__.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_facade_is_one_public_root_run_boundary() -> None:
    tree = _tree(_FACADE)
    public_definitions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert public_definitions == {"BacktestRuntime"}
    facade = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "BacktestRuntime"
    )
    public_methods = {
        node.name
        for node in facade.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert public_methods == {"run"}
    run = next(
        node
        for node in facade.body
        if isinstance(node, ast.FunctionDef) and node.name == "run"
    )
    assert [argument.arg for argument in run.args.args] == ["self", "request"]
    assert not run.args.kwonlyargs
    assert "BacktestRuntime" in _PUBLIC_ROOT.read_text(encoding="utf-8")


def test_facade_reuses_existing_authorities_without_a_second_graph() -> None:
    source = _FACADE.read_text(encoding="utf-8")
    for forbidden in (
        "BacktestProfileRegistry(",
        "Protocol",
        "Builder",
        "Factory",
        "Dispatcher",
        "CnAShare",
        "BinanceUsdm",
        "tests.",
        "crypto_quant_platform",
        "crypto_quant_foundation",
        "requests",
        "httpx",
        "socket",
        "subprocess",
    ):
        assert forbidden not in source
    assert source.count("ProfileResolver().resolve(") == 1
    assert source.count("AuditableBacktestRunner.for_v2(") == 1
    assert source.count("AttemptEvidenceWriter(") == 1
    assert source.count("CanonicalResultPublisher(") == 1


def test_facade_exposes_no_internal_orchestration_values() -> None:
    tree = _tree(_FACADE)
    facade = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "BacktestRuntime"
    )
    assigned_attributes = {
        target.attr
        for node in ast.walk(facade)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            node.targets if isinstance(node, ast.Assign) else (node.target,)
        )
        if isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
    }
    assert assigned_attributes == {
        "_registry",
        "_artifact_reader",
        "_artifact_publisher",
        "_market_reader",
        "_publication_root",
    }
    assert not {
        "registry",
        "resolver",
        "composer",
        "runner",
        "builder",
        "resolved_request",
        "execution_case",
    } & assigned_attributes
