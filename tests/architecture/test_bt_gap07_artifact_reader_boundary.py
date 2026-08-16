from __future__ import annotations

import ast
from pathlib import Path
from typing import get_type_hints

from crypto_quant_backtest import ArtifactEnvelopeReader
from crypto_quant_domain import ArtifactReadResult, ArtifactRef

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/artifact_envelope_reader.py"


def _module_body() -> ast.Module:
    assert MODULE.is_file()
    return ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))


def test_artifact_envelope_reader_module_has_exact_whitelisted_imports() -> None:
    body = _module_body()
    imports = {
        node.module: tuple(alias.name for alias in node.names)
        for node in ast.walk(body)
        if isinstance(node, ast.ImportFrom)
    }
    assert len(imports) == 3
    assert imports == {
        "__future__": ("annotations",),
        "typing": ("Protocol",),
        "crypto_quant_domain": ("ArtifactRef", "ArtifactReadResult"),
    }
    for node in ast.walk(body):
        if isinstance(node, (ast.Import, ast.Assign, ast.Call, ast.With, ast.For, ast.While)):
            raise AssertionError(f"forbidden implementation statement: {type(node).__name__}")


def test_artifact_envelope_reader_is_single_protocol_with_exact_signature() -> None:
    assert ArtifactEnvelopeReader.read is not None
    assert ArtifactEnvelopeReader.__name__ == "ArtifactEnvelopeReader"

    body = _module_body()
    top_level = [
        node
        for node in body.body
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    ]
    assert len(top_level) == 4
    class_nodes = [node for node in top_level if isinstance(node, ast.ClassDef)]
    assert len(class_nodes) == 1

    protocol = class_nodes[0]
    assert protocol.name == "ArtifactEnvelopeReader"
    assert len(protocol.bases) == 1
    assert isinstance(protocol.bases[0], ast.Name)
    assert protocol.bases[0].id == "Protocol"
    assert protocol.decorator_list == []

    methods = [node for node in protocol.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert len(methods) == 1
    read_method = methods[0]
    assert read_method.name == "read"
    assert read_method.args.posonlyargs == []
    assert len(read_method.args.args) == 1
    assert read_method.args.args[0].arg == "self"
    assert read_method.args.vararg is None
    assert [param.arg for param in read_method.args.kwonlyargs] == ["ref"]
    assert read_method.args.kw_defaults == [None]
    assert read_method.args.kwonlyargs[0].annotation.id == "ArtifactRef"
    assert read_method.returns is not None
    assert isinstance(read_method.returns, ast.Name)
    assert read_method.returns.id == "ArtifactReadResult"
    assert read_method.decorator_list == []
    assert len(read_method.body) == 1
    method_body = read_method.body[0]
    assert isinstance(method_body, ast.Expr)
    assert isinstance(method_body.value, ast.Constant)
    assert method_body.value.value is ...


def test_artifact_envelope_reader_type_hints_target_domain_contract() -> None:
    hints = get_type_hints(ArtifactEnvelopeReader.read, include_extras=True)
    assert hints["ref"] is ArtifactRef
    assert hints["return"] is ArtifactReadResult
