from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder"
    / "cn_a_share_current_selected_rule_coverage.py"
)
BUILDER_ROOT = (
    ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
)
SEAM = "analyze_cn_a_share_current_selected_rule_coverage_v1"
VALUE_TYPES = {
    "CnAShareCurrentSelectedRuleCoverageFailureCode",
    "CnAShareCurrentSelectedRuleCoverageFailure",
    "CnAShareCurrentSelectedRuleCoverageReport",
}
ALLOWED_IMPORTS = {
    "__future__",
    "collections.abc",
    "dataclasses",
    "datetime",
    "enum",
    "json",
    "typing",
    "zoneinfo",
    "crypto_quant_domain",
}


def test_coverage_analyzer_is_one_off_root_concrete_builder_seam() -> None:
    assert MODULE.is_file()
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    public_functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    ]
    assert [function.name for function in public_functions] == [SEAM]
    function = public_functions[0]
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

    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert classes == VALUE_TYPES
    dataclasses = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name != "CnAShareCurrentSelectedRuleCoverageFailureCode"
    ]
    assert all(
        any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Name)
            and decorator.func.id == "dataclass"
            and {keyword.arg: keyword.value.value for keyword in decorator.keywords}
            == {"frozen": True, "slots": True}
            for decorator in value.decorator_list
        )
        for value in dataclasses
    )

    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert imports <= ALLOWED_IMPORTS

    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "crypto_quant_trading",
        "crypto_quant_backtest",
        "crypto_quant_market_data",
        "Kernel",
        "Runtime",
        "Provider",
        "Repository",
        "Registry",
        "Resolver",
        "Protocol",
        "Adapter",
        "Factory",
        "DSL",
        "builtins.open(",
        "pathlib",
        "socket",
        "subprocess",
        "requests",
        "urllib",
        "datetime.now",
    ):
        assert forbidden not in source

    root_source = BUILDER_ROOT.read_text(encoding="utf-8")
    assert SEAM not in root_source
    assert "cn_a_share_current_selected_rule_coverage" not in root_source
