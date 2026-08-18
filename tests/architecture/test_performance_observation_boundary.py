from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/performance_observations.py"
ROOT_MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/__init__.py"


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        *(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)),
        *(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names),
    }


def test_performance_recorder_is_stdlib_only_private_and_has_no_platform_behavior() -> None:
    assert MODULE.is_file()
    assert imports(MODULE) <= {"__future__", "dataclasses", "enum"}
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in ("logging", "open(", "pathlib", "socket", "thread", "Lock", "Protocol", "registry", "export", "serialize"):
        assert forbidden not in source
    root_source = ROOT_MODULE.read_text(encoding="utf-8")
    assert "performance_observations" not in root_source
    assert "BoundedPerformanceRecorder" not in root_source
