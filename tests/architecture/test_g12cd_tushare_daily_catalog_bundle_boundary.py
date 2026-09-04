from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_daily_catalog_bundle.py"
BUILDER_ROOT = ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
SEAM = "project_tushare_cn_a_share_daily_catalog_bound_market_event_v2"
CLASSES = {
    "TushareCnAShareAcquisitionCatalogSource",
    "TushareCnAShareDailyCatalogPublicationFailureCode",
    "TushareCnAShareDailyCatalogPublicationFailure",
    "TushareCnAShareDailyCatalogPublicationResult",
    "TushareCnAShareDailyCatalogPublicationOutcome",
}


def test_catalog_bound_tushare_publication_stays_one_internal_compositional_module() -> None:
    assert MODULE.is_file(), "G12C/D Tushare catalog RED: missing internal v2 module"
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    public_functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    ]
    assert [function.name for function in public_functions] == [SEAM]
    function = public_functions[0]
    assert [argument.arg for argument in function.args.args] == ["result"]
    assert not (
        function.args.posonlyargs or function.args.kwonlyargs or function.args.vararg
        or function.args.kwarg or function.args.defaults or function.args.kw_defaults
    )
    assert function.returns is not None
    assert ast.unparse(function.returns) == "TushareCnAShareDailyCatalogPublicationOutcome"
    assert {node.name for node in tree.body if isinstance(node, ast.ClassDef)} == CLASSES

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
    assert not any(name.startswith(("crypto_quant_trading", "crypto_quant_backtest")) for name in imports)
    assert not imports.intersection({"httpx", "requests", "socket", "urllib", "pathlib", "tarfile"})
    assert not any(name.endswith(("bundle_validation", "local_market_bundle_repository")) for name in imports)

    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "Protocol", "Adapter", "Factory", "Registry", "Repository", "Reader",
        "price_bars", "SymbolTimeline", "listing_interval", "membership",
    ):
        assert forbidden not in source
    root_source = BUILDER_ROOT.read_text(encoding="utf-8")
    assert SEAM not in root_source
    assert "tushare_cn_a_share_daily_catalog_bundle" not in root_source


def test_v1_public_surface_and_production_bytes_are_locked() -> None:
    expected = {
        ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_daily.py": "019ec74e369f8bd747342e2be5e3da8b04dfeb226a2b18a5bc49160323bac77d",
        ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_daily_bundle.py": "561270a78ed856eb37e8e804fdde52fbcc9d52a0bac2fd1d3763e8623aa79ef9",
        BUILDER_ROOT: "ce723694c39feeb0f70976065f8e513a1a2277d93cc35401bbaf046520acc40e",
    }
    for path, digest in expected.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
