from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT_MODULE = (
    ROOT
    / "packages/backtest-runtime/src/crypto_quant_backtest/liquidation_audit.py"
)
GENERIC_MODULES = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/runner.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/timeline.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/ledger.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/margin.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/account_margin.py",
)
PREFIXES = (
    "ConservativeLinearLiquidation",
    "LinearLiquidation",
)


def _audit_purity_violations(source: str) -> set[str]:
    tree = ast.parse(source)
    allowed_imports = {
        "__future__",
        "dataclasses",
        "enum",
        "math",
        "typing",
        "crypto_quant_domain",
        "crypto_quant_trading",
        "ports",
        "resolution",
    }
    violations: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "") not in allowed_imports:
            violations.add(f"import:{node.module}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in allowed_imports:
                    violations.add(f"import:{alias.name}")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            violations.add(f"scope:{type(node).__name__}")
        elif isinstance(node, ast.Name) and node.id in {
            "Decimal",
            "Path",
            "__import__",
            "eval",
            "exec",
            "float",
            "open",
        }:
            violations.add(f"name:{node.id}")
        elif isinstance(node, ast.Call):
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else ""
            )
            if name in {
                "connect",
                "execute",
                "open",
                "run",
                "send",
                "system",
                "unlink",
                "urlopen",
                "write",
            }:
                violations.add(f"side_effect:{name}")
    for statement in tree.body:
        value = None
        if isinstance(statement, ast.Assign):
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            value = statement.value
        if isinstance(value, (ast.Dict, ast.List, ast.Set)):
            violations.add("module_state:mutable_literal")
    return violations


def _generic_reference_violations(source: str) -> set[str]:
    tree = ast.parse(source)
    violations: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and "liquidation_audit" in (
            node.module or ""
        ):
            violations.add(f"import:{node.module}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "liquidation_audit" in alias.name:
                    violations.add(f"import:{alias.name}")
        elif isinstance(node, ast.Name) and node.id.startswith(PREFIXES):
            violations.add(f"name:{node.id}")
        elif isinstance(node, ast.Attribute) and node.attr.startswith(PREFIXES):
            violations.add(f"attribute:{node.attr}")
    return violations


def test_liquidation_audit_module_is_pure_and_bounded() -> None:
    assert not _audit_purity_violations(AUDIT_MODULE.read_text(encoding="utf-8"))


def test_generic_modules_do_not_reference_linear_liquidation_audit() -> None:
    for path in GENERIC_MODULES:
        assert not _generic_reference_violations(
            path.read_text(encoding="utf-8")
        ), path.relative_to(ROOT)
