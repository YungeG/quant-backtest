"""Architecture contract approved for opt-in reference delivery."""
import ast
from inspect import Parameter, signature
from pathlib import Path
from unittest.mock import Mock

import pytest

from crypto_quant_backtest import BacktestExecutionRequest, BacktestRuntime, facade

ROOT = Path(facade.__file__).parent

def calls(root, member):
    return {path.name for path in root.glob("*.py") if any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == member for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))))}

def test_referenced_pair_is_private_to_delivery_and_is_not_on_generic_runner_route():
    assert calls(ROOT, "_execute_referenced_pair_locked") == {"_referenced_delivery.py"}
    assert calls(ROOT, "_execute_referenced_locked") == {"runner.py"}
    runner = ast.parse((ROOT / "runner.py").read_text(encoding="utf-8"))
    owner, = (node for node in runner.body if isinstance(node, ast.ClassDef)
              and node.name == "AuditableBacktestRunner")
    pair, = (node for node in owner.body if isinstance(node, ast.FunctionDef)
             and node.name == "_execute_referenced_pair_locked")
    assert sum(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and node.func.attr == "_execute_referenced_locked" for node in ast.walk(pair)) == 2
    assert all(not any(isinstance(call, ast.Attribute) and call.attr in {
        "_execute_referenced_pair_locked", "_execute_referenced_locked"}
        for call in ast.walk(method)) for method in owner.body
        if isinstance(method, ast.FunctionDef) and method is not pair)

def test_resume_delivery_requires_an_explicit_layout_and_exact_input9(monkeypatch):
    layout = signature(BacktestRuntime).parameters["evidence_layout"]
    assert layout.kind is Parameter.KEYWORD_ONLY and layout.default == "legacy"
    assert list(signature(BacktestRuntime.resume_delivery).parameters) == ["self", "request"]

    runtime = object.__new__(BacktestRuntime)
    snapshot, recovered = object(), object()
    decode = Mock(return_value=(snapshot, None))
    original_economic_run = Mock(side_effect=AssertionError("resume entered the public engine"))
    recovered_run = Mock(return_value=recovered)
    monkeypatch.setattr(facade, "_snapshot_execution_request_v9_from_validated_schema", decode)
    monkeypatch.setattr(BacktestRuntime, "_run", original_economic_run)
    monkeypatch.setattr(BacktestRuntime, "_run_v6", recovered_run)
    request = object.__new__(BacktestExecutionRequest)
    object.__setattr__(request, "schema_version", 9)
    runtime._evidence_layout = "legacy"
    with pytest.raises(ValueError, match="requires referenced_v1"):
        runtime.resume_delivery(request)
    runtime._evidence_layout = "referenced_v1"
    with pytest.raises(ValueError, match="requires exact Input9"):
        runtime.resume_delivery(object())
    old = object.__new__(BacktestExecutionRequest)
    object.__setattr__(old, "schema_version", 8)
    with pytest.raises(ValueError, match="requires exact Input9"):
        runtime.resume_delivery(old)
    decode.assert_not_called()
    recovered_run.assert_not_called()
    assert runtime.resume_delivery(request) is recovered
    decode.assert_called_once_with(request)
    recovered_run.assert_called_once_with(snapshot, cancellation=None, resume=True)
    original_economic_run.assert_not_called()
