from __future__ import annotations

import ast
from pathlib import Path

import crypto_quant_backtest as runtime

ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/"
    "binance_usdm_tradifi_profile_wire.py"
)
FUNCTION = "decode_binance_usdm_tradifi_profile_composition_request_v1"


def test_tradifi_profile_wire_codec_is_public_offline_and_runtime_owned() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }

    assert getattr(runtime, FUNCTION).__module__ == (
        "crypto_quant_backtest.binance_usdm_tradifi_profile_wire"
    )
    assert FUNCTION in runtime.__all__
    assert all(
        "bundle_builder" not in name and not name.startswith("tests")
        for name in imports
    )
    for forbidden in (
        "pickle",
        "socket",
        "requests",
        "urllib",
        "datetime.now",
        "time.time",
        "open(",
    ):
        assert forbidden not in source


def test_tradifi_profile_wire_codec_has_one_public_function() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    functions = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]
    assert functions == [FUNCTION]
