from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "packages/backtest-runtime/src"
DEPENDENCY_ROOTS = (
    ROOT / "packages/trading-domain/src",
    ROOT / "packages/market-data-contracts/src",
    ROOT / "packages/trading-kernel/src",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }


def test_runtime_v3_has_no_builder_import_and_imports_without_builder() -> None:
    runtime_package = RUNTIME / "crypto_quant_backtest"
    assert not any(
        value.startswith("crypto_quant_bundle_builder")
        for path in runtime_package.rglob("*.py")
        for value in _imports(path)
    )
    environment = os.environ | {
        "PYTHONPATH": os.pathsep.join(str(path) for path in (RUNTIME, *DEPENDENCY_ROOTS)),
    }
    result = subprocess.run(
        [sys.executable, "-S", "-c", "import crypto_quant_backtest"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
