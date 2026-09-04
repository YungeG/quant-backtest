from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

import crypto_quant_backtest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/execution_inputs.py"
FORBIDDEN_IMPORT_ROOTS = {
    "_publication",
    "crypto_quant_foundation",
    "crypto_quant_promotion",
    "crypto_quant_research",
    "crypto_quant_validation",
    "evidence",
    "foundation",
    "httpx",
    "integrity",
    "os",
    "pathlib",
    "platform",
    "publication_refs",
    "requests",
    "runner",
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


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _literal_argument(call: ast.Call, *, keyword: str, position: int) -> object | None:
    for item in call.keywords:
        if item.arg == keyword and isinstance(item.value, ast.Constant):
            return item.value.value
    if len(call.args) > position and isinstance(call.args[position], ast.Constant):
        return call.args[position].value
    return None


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
    assert public_functions == {
        "materialize_execution_input_bundle",
        "materialize_execution_input_bundle_v2",
        "materialize_execution_input_bundle_v6",
    }
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


def test_only_the_bundle_has_one_private_versioned_schema_catalog() -> None:
    module = _module()
    registrations = [
        (
            _literal_argument(node, keyword="artifact_type", position=0),
            _literal_argument(node, keyword="schema_version", position=1),
        )
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and _call_name(node.func).endswith("ArtifactSchemaRegistration")
    ]
    catalogs = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Call) and _call_name(node.func).endswith("SchemaCatalog")
    ]
    preserved_registrations = [
        ("backtest_execution_input_bundle", 1),
        ("backtest_execution_input_bundle", 2),
        ("backtest_execution_input_bundle", 3),
        ("backtest_execution_input_bundle", 4),
        ("backtest_execution_input_bundle", 5),
    ]
    assert registrations[:5] == preserved_registrations
    assert registrations == preserved_registrations + [
        ("backtest_execution_input_bundle", 6)
    ]
    assert len(catalogs) == 1


def test_transport_defines_no_artifact_identity_behavior() -> None:
    module = _module()
    transport = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "BacktestExecutionRequest"
    )
    public_methods = {
        node.name
        for node in transport.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert public_methods == {"to_canonical_dict"}
    calls = {
        _call_name(node.func)
        for node in ast.walk(transport)
        if isinstance(node, ast.Call)
    }
    assert calls.isdisjoint(
        {
            "SchemaCatalog",
            "ArtifactEnvelope.create",
            "ArtifactRef.from_envelope",
            "canonical_sha256",
        }
    )
