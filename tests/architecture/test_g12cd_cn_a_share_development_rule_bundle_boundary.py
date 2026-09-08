from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder"
    / "cn_a_share_development_rule_bundle.py"
)
BUILDER_ROOT = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
)
SEAM = "project_cn_a_share_development_rule_authority_events_v1"


def test_rule_authority_projection_stays_internal_providerless_and_compositional() -> None:
    assert MODULE.is_file(), "G12H prerequisite RED: missing internal projection module"
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    assert [function.name for function in functions] == [SEAM]
    function = functions[0]
    assert [argument.arg for argument in function.args.posonlyargs] == ["declaration"]
    assert not (
        function.args.args
        or function.args.kwonlyargs
        or function.args.vararg
        or function.args.kwarg
        or function.args.defaults
        or function.args.kw_defaults
    )
    assert function.returns is not None
    assert ast.unparse(function.returns) == "tuple[MarketEvent, ...]"
    assert not any(isinstance(node, ast.ClassDef) for node in tree.body)

    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not any(
        name.startswith(("crypto_quant_trading", "crypto_quant_backtest"))
        for name in imports
    )
    assert not imports.intersection({"httpx", "requests", "socket", "urllib"})
    assert not any(
        name.endswith(("bundle_validation", "local_market_bundle_repository"))
        for name in imports
    )

    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "Protocol",
        "Adapter",
        "Factory",
        "Registry",
        "Repository",
        "Resolver",
    ):
        assert forbidden not in source

    root_source = BUILDER_ROOT.read_text(encoding="utf-8")
    assert SEAM not in root_source
    assert "cn_a_share_development_rule_bundle" not in root_source
