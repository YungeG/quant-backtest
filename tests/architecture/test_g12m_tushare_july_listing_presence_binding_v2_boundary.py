from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/g12m_tushare_july_listing_presence_binding_v2.py"
ROOT_EXPORT = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/__init__.py"
PROTECTED_SHA256 = {
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/g12m_tushare_listing_presence_binding_v1.py": "1f6efe379f18eb85205db6f21f209d8d3cdf74fcf428c26f11830d592c401c1e",
    ROOT / "tests/fixtures/runtime/g12m-tushare-listing-presence-binding-v1/identity.expected.json": "c886434bad6c4acc4fcd4094593edcdda016c769715cf4ef8d234c28174e65ec",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/observation-report.expected.json": "36b38ec4367a4c9945c4ee8caee9b31eeb57bf73f6c10ed93526d0306d281e6c",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/g12m_tushare_fixed_singleton_assessment_v2.py": "99a725d243d75e09a3bc66e06b3bf5d0ba91b5a1fd40f31a92b95005a7a337d0",
}


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names} | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }


def function_arguments(path: Path, function_name: str) -> tuple[list[str], list[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function_name)
    return [arg.arg for arg in function.args.args], [arg.arg for arg in function.args.kwonlyargs]


def test_july_binding_is_pure_off_root_and_exact() -> None:
    source = MODULE.read_text(encoding="utf-8")
    imported = imports(MODULE)
    assert function_arguments(MODULE, "bind_g12m_tushare_july_listing_presence_v2") == (
        [], ["predecessor_binding", "july_report_bytes", "bound_at"]
    )
    assert not any(value.startswith("crypto_quant_bundle_builder") for value in imported)
    assert not imported.intersection({"pathlib", "os", "subprocess", "socket", "urllib", "requests", "httpx"})
    for forbidden in ("BacktestRuntime", "ArtifactReader", "ArtifactPublisher", "Repository", "open(", "Path("):
        assert forbidden not in source
    root_source = ROOT_EXPORT.read_text(encoding="utf-8")
    assert "g12m_tushare_july_listing_presence_binding_v2" not in root_source
    assert "G12MTushareJulyListingPresenceBindingV2" not in root_source


def test_july_binding_preserves_predecessor_assessment_and_report_bytes() -> None:
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in PROTECTED_SHA256} == PROTECTED_SHA256
