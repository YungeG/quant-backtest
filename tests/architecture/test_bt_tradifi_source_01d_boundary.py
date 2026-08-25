from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/koru_tradifi_calendar_unit_authority_v1.py"
)
BUILDER_ROOT = (
    ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
)
COMPOSER = (
    ROOT
    / "packages/backtest-runtime/src/crypto_quant_backtest/binance_usdm_tradifi_profile.py"
)
FIXTURE_ROOT = (
    ROOT / "tests/fixtures/market_data/providers/tradifi/koru-calendar-unit-v1"
)
FIXTURE_SHA256 = {
    "binance/acquisition-receipt.json": "e37c33eaf1b85c800f225b5d1f798069992772084b21ed91384af8f242173e59",
    "binance/adjustment-announcement.json": "0f06a75fa2b8291ee8ec1c749657576467a84092fa096ece181958069acae97e",
    "binance/completion-announcement.json": "c194651673fbd80c014c8e3931403f6a51d14cb8bf920fcf17c0c3e609c9a143",
    "krx/acquisition-receipt.json": "414c889f216f01be161110d4116bd4cd26509d4ec1079a32c043d62f9cee4f58",
    "krx/landing.html": "c181b15a7c08cc48a4fc390160cdf748c3680006155f1a0124465613f32b978e",
    "krx/market-closing-2026.json": "e60dc5a3d4f8a02afc842f34544f2edf162836bc124209b75dc7456030858dfe",
    "nyse/acquisition-receipt.json": "a393aaa8efe6e9747711695d0df2c49d98cd56ef9ad3ba83ed75d15f613a273c",
    "nyse/hours-calendars.html": "49ee8a651ec01ef2866e347842c0fb11309541f247d17aeaaf7ad9d6a513b1ed",
}
PROTECTED_SOURCE_SHA256 = {
    BUILDER_ROOT: "ce723694c39feeb0f70976065f8e513a1a2277d93cc35401bbaf046520acc40e",
    COMPOSER: "38de4c2bd0d95fe557e884320c76ba4c459e0ea88ce61fa31cbfdbe6273bbb76",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").lstrip(".")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }


def test_authority_is_package_internal_additive_and_off_runtime_boundaries() -> None:
    assert MODULE.is_file()
    assert _imports(MODULE) <= {
        "__future__",
        "hashlib",
        "json",
        "re",
        "dataclasses",
        "datetime",
        "enum",
        "html",
        "types",
        "typing",
        "crypto_quant_domain",
        "source_snapshots",
    }
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "MarketBundle",
        "Strategy",
        "Preparation",
        "crypto_quant_backtest",
        "crypto_quant_trading",
        "pathlib",
        "open(",
        "zoneinfo",
        "tzdata",
        "datetime.now",
        "date.today",
        "time.time",
        "socket",
        "requests",
        "urllib",
    ):
        assert forbidden not in source
    root_source = BUILDER_ROOT.read_text(encoding="utf-8")
    assert "koru_tradifi_calendar_unit_authority_v1" not in root_source
    assert "KoruTradifiCalendarUnitAuthority" not in root_source


def test_parent_captured_fixture_bytes_and_compatible_sources_are_pinned() -> None:
    assert {
        path: hashlib.sha256((FIXTURE_ROOT / path).read_bytes()).hexdigest()
        for path in FIXTURE_SHA256
    } == FIXTURE_SHA256
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in PROTECTED_SOURCE_SHA256
    } == PROTECTED_SOURCE_SHA256


def test_authority_has_one_build_and_one_verify_seam() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    public_functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]
    assert [node.name for node in public_functions] == [
        "build_koru_tradifi_calendar_unit_authority_v1",
        "verify_koru_tradifi_calendar_unit_authority_v1",
    ]
    assert [argument.arg for argument in public_functions[0].args.kwonlyargs] == [
        "members",
        "expected_hashes",
    ]
    assert [argument.arg for argument in public_functions[1].args.kwonlyargs] == [
        "result",
        "expected_hashes",
    ]
