from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACQUISITION_MODULE = ROOT / "tools/acquisition/binance_usdm.py"
OBSERVATION_MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/binance_usdm_funding_history_source_bounded_v2.py"
)
BUILDER_ROOT = (
    ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
)
TOOLS = ROOT / "tools/acquisition"
PROTECTED_SHA256 = {
    ACQUISITION_MODULE: (
        "99f4cf3a4631cd4e69830674751b63e23f66537e96745439fba86a7d52b36617"
    ),
    ROOT
    / "tests/tools/acquisition/test_binance_usdm_funding_history_source_bounded_v2.py": (
        "4c9ead69234cd1ad50fba7ef895a4d13f45e789331291d24bc74f0416621cc1a"
    ),
    ROOT
    / "tests/fixtures/market_data/providers/binance_usdm/funding-history-source-bounded-v2/acquisition-receipt.json": (
        "a92989478047de7d744744aedeaf365f7d16240b536c1ccece749abe3b4efa36"
    ),
    ROOT
    / "tests/fixtures/market_data/providers/binance_usdm/funding-history-source-bounded-v2/response/funding-history.json": (
        "e9f73f9c845c28abb31037d8230df2d6f13d5d368c43436e891fcc757372c338"
    ),
    BUILDER_ROOT: ("ce723694c39feeb0f70976065f8e513a1a2277d93cc35401bbaf046520acc40e"),
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/binance_usdm_funding_rate_archive.py": (
        "2f42f796ed947dbe24f025e5e3612437c52704faaac5a12c60514685ceee0754"
    ),
    ROOT
    / "tests/bundle_builder/providers/binance_usdm/test_funding_history_response_evidence.py": (
        "bd2ad74940e3c49024bfea66be7b2f44735dba01823e980f39a2e0d93f754f7c"
    ),
    ROOT
    / "tests/fixtures/market_data/providers/binance_usdm/funding-history-v1/BTCUSDT-funding-history-2024-01-01.json": (
        "e9f73f9c845c28abb31037d8230df2d6f13d5d368c43436e891fcc757372c338"
    ),
    ROOT
    / "tests/fixtures/market_data/providers/binance_usdm/funding-history-v1/evidence.expected.json": (
        "56ae7e1ddf9ee0fbead02b96e44a76134f60e0add2451060a824106a0810efa4"
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


def test_g12l_binance_funding_history_source_bounded_preserves_protected_bytes() -> (
    None
):
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in PROTECTED_SHA256
    } == PROTECTED_SHA256


def test_g12l_binance_funding_history_source_bounded_keeps_tool_contract() -> None:
    imported = imports(ACQUISITION_MODULE)
    assert not any(
        name.startswith(("crypto_quant_backtest", "crypto_quant_trading"))
        for name in imported
    )
    assert not imported.intersection({"httpx", "requests", "socket", "urllib"})
    assert function_arguments(ACQUISITION_MODULE, "acquire_funding_history") == (
        ["request"],
        ["output_dir", "acquired_at_epoch_nanoseconds", "get", "sleep"],
    )
    assert function_arguments(ACQUISITION_MODULE, "main") == (["argv"], [])
    assert all(
        path.name != "binance_usdm_funding_history_source_bounded_v2.py"
        for path in TOOLS.glob("*.py")
    )


def test_g12l_observer_is_provider_specific_in_memory_and_architecture_isolated() -> (
    None
):
    source = OBSERVATION_MODULE.read_text(encoding="utf-8")
    imported = imports(OBSERVATION_MODULE)

    assert function_arguments(
        OBSERVATION_MODULE,
        "observe_binance_usdm_funding_history_source_bounded_v2",
    ) == (
        [],
        [
            "acquisition_receipt_bytes",
            "snapshot",
            "supersedes_report",
            "supersedes_acquisition_receipt_bytes",
            "supersedes_snapshot",
        ],
    )
    assert not any(
        name.startswith(("crypto_quant_backtest", "crypto_quant_trading"))
        for name in imported
    )
    assert not imported.intersection(
        {"httpx", "requests", "socket", "urllib", "pathlib", "os"}
    )
    for forbidden in (
        "LocalMarketBundleRepository",
        "Runtime",
        "Kernel",
        "open(",
        "provider registry",
        "repository head",
    ):
        assert forbidden not in source


def test_g12l_observer_has_no_builder_root_export_or_runtime_kernel_dependency() -> (
    None
):
    root_source = BUILDER_ROOT.read_text(encoding="utf-8")
    assert "BinanceUsdmFundingHistorySourceBoundedObservation" not in root_source
    assert "observe_binance_usdm_funding_history_source_bounded_v2" not in root_source

    runtime_kernel_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for package in ("backtest-runtime", "trading-kernel")
        for path in (ROOT / "packages" / package / "src").rglob("*.py")
    )
    assert (
        "binance_usdm_funding_history_source_bounded_v2" not in runtime_kernel_sources
    )
