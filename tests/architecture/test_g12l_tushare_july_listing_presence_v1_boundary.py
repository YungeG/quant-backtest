from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tools/acquisition/cn_a_share_tushare_july_listing_presence_v1.py"
PROTECTED_SHA256 = {
    ROOT / "tools/acquisition/cn_a_share_tushare_listing_source_bounded_v2.py": (
        "141d0901d74f3a8956c8006d5952b4c777a34184cd7f34d27bf8b42bebf07941"
    ),
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/"
    "tushare_cn_a_share_listing_source_bounded_v2.py": (
        "1a1cff72919707e4cab5fca3215fe031385aa9d15e68ce0cfc14304b9876aaa5"
    ),
    ROOT
    / "tests/fixtures/market_data/providers/tushare/"
    "g12l-listing-source-bounded-v2/observation-report.expected.json": (
        "24122b0a68c87f7bdc5723640724733a2d1f25a7c1b62b0f02eb17bdad2d0205"
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


def test_july_acquisition_is_fixed_additive_and_reuses_approved_transport() -> None:
    source = MODULE.read_text(encoding="utf-8")
    imported = imports(MODULE)

    assert function_arguments(MODULE, "acquire_tushare_july_listing_presence_v1") == (
        [],
        [
            "token",
            "endpoint",
            "output_dir",
            "acquired_at_epoch_nanoseconds",
            "post",
            "sleep",
        ],
    )
    assert not any(
        value.startswith(("crypto_quant_backtest", "crypto_quant_trading"))
        for value in imported
    )
    assert "_post_with_retries" in source
    assert "_stdlib_post" in source
    assert "_request_body" in source
    assert "_headers" in source
    assert "--token" not in source
    assert "stock_basic" not in source
    assert "namechange" not in source
    assert "https://api.tushare.pro" not in source
    assert "20260706" in source and "20260730" in source


def test_july_slice_preserves_accepted_listing_bytes() -> None:
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in PROTECTED_SHA256
    } == PROTECTED_SHA256
