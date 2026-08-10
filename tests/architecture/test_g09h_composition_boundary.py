from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GENERIC_MODULES = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/runner.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/timeline.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/composition.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/ledger.py",
)
LINEAR_SUPPORT = ROOT / "tests/support/synthetic_market/linear_perpetual.py"
PRODUCTION_ROOTS = (
    ROOT / "packages/backtest-runtime/src",
    ROOT / "packages/trading-kernel/src",
    ROOT / "packages/trading-domain/src",
    ROOT / "packages/market-data-contracts/src",
)
FORBIDDEN_PREFIXES = (
    "Funding",
    "LinearDerivative",
    "LinearPerpetual",
    "Liquidation",
    "Margin",
)
FORBIDDEN_SUPPORT_IMPORTS = (
    "boto",
    "cloud",
    "database",
    "http",
    "requests",
    "socket",
    "sql",
    "subprocess",
    "urllib",
)


def _forbidden_prefix(value: str) -> bool:
    return next(
        (True for prefix in FORBIDDEN_PREFIXES if value.startswith(prefix)),
        False,
    )


def _forbidden_import(value: str) -> bool:
    lowered = value.lower()
    return next(
        (True for token in FORBIDDEN_SUPPORT_IMPORTS if token in lowered),
        False,
    )


def _generic_violations(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if _forbidden_prefix(alias.name):
                    violations.add(f"import:{alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if next(
                    (_forbidden_prefix(part) for part in alias.name.split(".")),
                    False,
                ):
                    violations.add(f"import:{alias.name}")
        elif isinstance(node, ast.Name) and _forbidden_prefix(node.id):
            violations.add(f"name:{node.id}")
        elif isinstance(node, ast.Attribute) and _forbidden_prefix(node.attr):
            violations.add(f"attribute:{node.attr}")
    return violations


def test_generic_runtime_has_no_derivative_financial_branches() -> None:
    for path in GENERIC_MODULES:
        assert not _generic_violations(path), path.relative_to(ROOT)


def test_synthetic_linear_support_has_no_external_side_effect_imports() -> None:
    tree = ast.parse(LINEAR_SUPPORT.read_text(encoding="utf-8"))
    imported = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imported.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    violations = {
        value
        for value in imported
        if _forbidden_import(value)
    }
    assert not violations


def test_production_packages_do_not_import_test_support() -> None:
    violations: list[str] = []
    for root in PRODUCTION_ROOTS:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if "tests.support.synthetic_market" in source:
                violations.append(str(path.relative_to(ROOT)))
    assert not violations
