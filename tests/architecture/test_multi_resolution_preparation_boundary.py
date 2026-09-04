from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from crypto_quant_backtest.multi_resolution_preparation import (
    MarketDataCaseAuthority,
    MarketDataPreparationFailure,
    MultiResolutionMarketDataPreparation,
    SignalObservationLineageBinding,
)

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/multi_resolution_preparation.py"
ROOT_MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/__init__.py"


def test_preparation_is_off_root_and_has_no_forbidden_architecture_dependencies() -> None:
    assert MODULE.is_file()
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = {
        *(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)),
        *(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names),
    }
    assert not any(
        value.startswith(("crypto_quant_bundle_builder", "crypto_quant_trading"))
        for value in imported
    )
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "Registry", "Factory", "Provider", "resample", "pandas", "numpy",
        "execution_inputs", "composition", "facade", "runner",
    ):
        assert forbidden not in source
    root = ROOT_MODULE.read_text(encoding="utf-8")
    assert "multi_resolution_preparation" not in root
    assert "MultiResolutionMarketDataPreparation" not in root


def test_preparation_does_not_reinstrument_f1_helpers() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    calls = {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id
        in {
            "construct_multi_resolution_market_data_bindings",
            "validate_schedule_signal_exact_cover",
            "verify_visible_signal_bars",
        }
    }
    construct = calls["construct_multi_resolution_market_data_bindings"]
    assert next(
        keyword.value
        for keyword in construct.keywords
        if keyword.arg == "recorder"
    ).value is None
    validate = calls["validate_schedule_signal_exact_cover"]
    verify = calls["verify_visible_signal_bars"]
    assert isinstance(validate.args[-1], ast.Constant) and validate.args[-1].value is None
    assert isinstance(verify.args[-1], ast.Constant) and verify.args[-1].value is None


def test_exact_value_field_surfaces_remain_minimal() -> None:
    assert tuple(field.name for field in fields(SignalObservationLineageBinding)) == (
        "requirement_hash", "event_id", "event_hash", "observation_key"
    )
    assert tuple(field.name for field in fields(MultiResolutionMarketDataPreparation)) == (
        "decision_schedule", "bindings", "signal_lineages"
    )
    assert tuple(field.name for field in fields(MarketDataCaseAuthority)) == (
        "decision_cycles", "bar_executions", "execution_model", "snapshot_plan", "target_stream"
    )
    assert tuple(field.name for field in fields(MarketDataPreparationFailure)) == (
        "code", "role_position", "schedule_entry_position", "requirement_position", "event_position"
    )
