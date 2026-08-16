from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

import crypto_quant_backtest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/execution_inputs.py"
FORBIDDEN_IMPORT_ROOTS = {
    "foundation",
    "httpx",
    "os",
    "pathlib",
    "platform",
    "requests",
    "socket",
    "subprocess",
    "urllib",
}
FORBIDDEN_PUBLIC_SUFFIXES = (
    "Adapter",
    "Cache",
    "Factory",
    "Protocol",
    "Registry",
    "Repository",
    "Resolver",
)


def _module() -> ast.Module:
    assert MODULE.is_file(), "BT-GAP-02B RED: missing execution_inputs.py"
    return ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))


def test_execution_input_module_preserves_one_way_repository_boundary() -> None:
    module = _module()
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            roots = {node.module.split(".")[0]}
        else:
            continue
        assert roots.isdisjoint(FORBIDDEN_IMPORT_ROOTS)

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
    assert public_classes == {"BacktestExecutionRequest"}
    assert public_functions == {"materialize_execution_input_bundle"}
    assert not any(
        name.endswith(FORBIDDEN_PUBLIC_SUFFIXES)
        for name in public_classes | public_functions
    )


def test_execution_request_has_no_second_identity_or_storage_coordinate() -> None:
    execution_request = getattr(crypto_quant_backtest, "BacktestExecutionRequest", None)
    assert execution_request is not None, "BT-GAP-02B RED: missing public transport"
    field_names = tuple(field.name for field in fields(execution_request))
    expected_field_names = (
        "schema_version",
        "request",
        "execution_input_bundle_ref",
    )
    assert field_names == expected_field_names
    assert not {
        "content_hash",
        "created_at",
        "path",
        "reader",
        "repository",
        "request_hash",
        "status",
        "transport_ref",
    } & set(vars(execution_request))


def test_execution_input_module_does_not_copy_market_events_or_platform_types() -> None:
    _module()
    source = MODULE.read_text(encoding="utf-8")
    assert "MarketEvent" not in source
    assert "MarketBundleManifest" not in source
    assert "TrialDeclaration" not in source
    assert "ValidationCase" not in source
    assert "Foundation" not in source
