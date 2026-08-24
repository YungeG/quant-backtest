from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).parents[2]
MODULE = (
    ROOT
    / "packages/backtest-runtime/src/crypto_quant_backtest/"
    "g12m_tushare_listing_presence_binding_v1.py"
)
ROOT_EXPORT = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/__init__.py"
PROTECTED_SHA256 = {
    ROOT
    / "packages/backtest-runtime/src/crypto_quant_backtest/"
    "g12m_tushare_fixed_singleton_assessment_v2.py": (
        "99a725d243d75e09a3bc66e06b3bf5d0ba91b5a1fd40f31a92b95005a7a337d0"
    ),
    ROOT
    / "packages/backtest-runtime/src/crypto_quant_backtest/"
    "g12m_tushare_fixed_singleton_route_v2.py": (
        "fae0993bce42d10dfaa38779a3098b74b1d86323e8cab78c18e6200306556295"
    ),
    ROOT
    / "tests/fixtures/market_data/providers/tushare/"
    "g12l-listing-source-bounded-v2/observation-report.expected.json": (
        "24122b0a68c87f7bdc5723640724733a2d1f25a7c1b62b0f02eb17bdad2d0205"
    ),
    ROOT
    / "tests/fixtures/runtime/g12m-tushare-fixed-singleton-assessment-v2/"
    "identity.expected.json": (
        "69d74c9c4b5572b91dd71c09c7570c1468b58e8dedec3f19971a799b23e31d02"
    ),
}


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }


def function_arguments(path: Path, function_name: str) -> tuple[list[str], list[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    )
    return [arg.arg for arg in function.args.args], [
        arg.arg for arg in function.args.kwonlyargs
    ]


def test_binding_is_pure_runtime_local_off_root_and_has_exact_signature() -> None:
    source = MODULE.read_text(encoding="utf-8")
    imported = imports(MODULE)

    assert function_arguments(MODULE, "bind_g12m_tushare_listing_presence_v1") == (
        [],
        [
            "base_assessment",
            "listing_report_bytes",
            "bound_at",
            "predecessor_binding",
        ],
    )
    assert not any(value.startswith("crypto_quant_bundle_builder") for value in imported)
    assert not imported.intersection(
        {"pathlib", "os", "subprocess", "socket", "urllib", "requests", "httpx"}
    )
    for forbidden in (
        "BacktestRuntime",
        "ArtifactReader",
        "ArtifactPublisher",
        "Repository",
        "open(",
        "Path(",
        "provider registry",
    ):
        assert forbidden not in source

    root_source = ROOT_EXPORT.read_text(encoding="utf-8")
    assert "g12m_tushare_listing_presence_binding_v1" not in root_source
    assert "G12MTushareListingPresenceBindingV1" not in root_source


def test_binding_preserves_accepted_route_assessment_and_listing_bytes() -> None:
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in PROTECTED_SHA256
    } == PROTECTED_SHA256
