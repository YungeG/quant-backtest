from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_july_listing_presence_v1.py"
BUILDER_ROOT = ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
PROTECTED_SHA256 = {
    ROOT / "tools/acquisition/cn_a_share_tushare_july_listing_presence_v1.py": "311c47208d628ab70bfedcdc8e80e89441530226b4148fff34b5c2e3e698643a",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/acquisition-receipt.json": "b2160a51acc6a642fe471c87b946237bdb37b1087f56fc2e6262d86a834fb581",
    ROOT / "tests/fixtures/market_data/providers/tushare/cn-a-share-daily-source-bounded-v2/observation-report.expected.json": "9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-listing-source-bounded-v2/observation-report.expected.json": "24122b0a68c87f7bdc5723640724733a2d1f25a7c1b62b0f02eb17bdad2d0205",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260706.json": "26d269536446897c455f5d5b81a3c882b5e8867eaa133c8457a59423016b1d09",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260707.json": "7e89b7972ce7b7844ce780d4389d1db4339c5e86c3a2bb65a66a54fb91018a72",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260708.json": "ac2cc479dce38c94a01021e0c06176d60fc452cd57c4e3e8e203e891583ce26b",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260709.json": "c2dc6f6227d159105348314031951f1d364ccf179cb64aaa6a8a8d8ad4a86c79",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260710.json": "369e4c136bdf34ebc2a53e5a3443c6197c45c0e8bd8de410a3c1221f7defe972",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260713.json": "900b6402991d7a750e098b203baa137c7e13aa1fe75de77d20f7f340605a5e02",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260714.json": "211c27e56c773000c832f3b68620a7b1182aab2ad812e6bf89ad28b89d464705",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260715.json": "95676e397301d7d6e8482efb147a3d296c69d048d3fa3fc3335bc4b73dc76cc2",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260716.json": "77b9206efd21b308a8f6624aa0448a248a1f79779ecec31f786ad8726d21ec8f",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260717.json": "eacde103bfb43686b6018d04cbe000b5e91bea9102e6fa5fa564392c7193c7fc",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260720.json": "0bcfef83ba3c7433a5290921cd2d743964f2dce8c24bacda68d19e1955c0e66b",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260721.json": "70816209cf51fa43b6243ab02f86060821143388e92b14213154bebb28c32181",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260722.json": "f653e9b2c7188de46ca72ab1913206e775ab89e40cf0d5ec8eaa8c3a0a40efc1",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260723.json": "464a5c25394d57423a5148c4175728ac32dad38aac292b352e33c0954c1ececd",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260724.json": "06cfeb720e41612780d2bca3dfe16fecfe3700e90977d7a82bcc8033f62d9214",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260727.json": "e6b6c35b6c904eec03b30c22bc5401921a1301835883ef23cf902e7b4a44baa5",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260728.json": "c7dcb8bb8cadd5cd3265702e3c2df01d0fb8967b11036c4882ce2d0a55dc0765",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260729.json": "805e39206512d70d16a76289c9f544c6edec82ad03df16f22efdf9e102d4f11f",
    ROOT / "tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/20260730.json": "71653d16db4d60a909d502eb1638a0a71151d94d9ec019190ef82784e4f8a8d3",
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


def test_july_observer_is_pure_off_root_and_has_exact_signature() -> None:
    source = MODULE.read_text(encoding="utf-8")
    imported = imports(MODULE)
    assert function_arguments(MODULE, "observe_tushare_cn_a_share_july_listing_presence_v1") == (
        [],
        ["acquisition_receipt_bytes", "snapshot", "g12i_report_bytes", "listing_report_bytes", "instrument_catalog"],
    )
    assert not any(value.startswith(("crypto_quant_backtest", "crypto_quant_trading")) for value in imported)
    assert not imported.intersection({"pathlib", "os", "socket", "urllib", "requests", "httpx"})
    for forbidden in ("Runtime", "Kernel", "MarketEvent", "MarketBundle", "open(", "Path(", "repository"):
        assert forbidden not in source
    root_source = BUILDER_ROOT.read_text(encoding="utf-8")
    assert "TushareCnAShareJulyListingPresence" not in root_source
    assert "observe_tushare_cn_a_share_july_listing_presence_v1" not in root_source


def test_july_observer_preserves_accepted_upstream_and_acquisition_bytes() -> None:
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in PROTECTED_SHA256} == PROTECTED_SHA256
