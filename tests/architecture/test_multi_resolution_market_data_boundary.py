from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/multi_resolution_market_data.py"
ROOT_MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/__init__.py"


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        *(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)),
        *(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names),
    }


def test_mrmd_core_is_off_root_and_uses_only_existing_runtime_authorities() -> None:
    assert MODULE.is_file()
    assert imports(MODULE) <= {
        "__future__", "dataclasses", "datetime", "enum", "time", "typing",
        "crypto_quant_domain", "crypto_quant_market_data", "decision_schedule",
        "observation_windows", "observations", "performance_observations",
    }
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "crypto_quant_bundle_builder", "crypto_quant_trading", "pandas", "numpy",
        "resample", "interpolate", "forward_fill", "Registry", "Factory", "Protocol",
        "Provider", "DSL", "global_frequency", "execution_input_bundle",
    ):
        assert forbidden not in source
    root_source = ROOT_MODULE.read_text(encoding="utf-8")
    assert "multi_resolution_market_data" not in root_source
    assert "MultiResolutionMarketDataBindings" not in root_source
