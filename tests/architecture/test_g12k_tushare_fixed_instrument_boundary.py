from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tools/acquisition/cn_a_share_tushare_g12k_fixed_instrument.py"
OBSERVATION_MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/g12k_tushare_fixed_instrument_source_bounded_v1.py"
)
BUILDER_ROOT = (
    ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
)
PACKAGES = ROOT / "packages"
PROTECTED_SHA256 = {
    ROOT / "tools/acquisition/cn_a_share_tushare.py": (
        "b7414ea5192338a43752e6b594670f180e016f69d4467a265ab2ad13d9e6f8ff"
    ),
    ROOT / "tools/acquisition/cn_a_share_tushare_authority.py": (
        "0e6ebf5db22721450874d9adf85e92777106bc2dc07b4784b332ea25aaddf9b1"
    ),
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_daily_source_bounded_v2.py": (
        "808f23ba7e2b0dd08fe08fcfa625489c3ca0d35a5ecbbcfa5e42e5d218d84e3a"
    ),
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_daily_catalog_bundle.py": (
        "0cbe6f744a7306f0f00e7fbbb77fb52dd2b01e16575cc3fb7cfb62edb66d9132"
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


def test_g12k_fixed_instrument_stays_additive_tool_only() -> None:
    source = MODULE.read_text(encoding="utf-8")
    imported = imports(MODULE)

    assert not any(
        name.startswith(("crypto_quant_backtest", "crypto_quant_trading"))
        for name in imported
    )
    assert not any(name in imported for name in ("httpx", "requests", "socket"))
    assert "TUSHARE_TOKEN" in source
    assert "--token" not in source
    assert "config/settings.json" not in source
    assert "_post_with_retries" in source
    assert "_provider_body" in source
    assert "_stdlib_post" in source
    assert "freeze_source_snapshot" in source
    assert "publish_directory" in source

    package_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in PACKAGES.glob("*/src/**/*.py")
        if path.is_file()
    )
    assert "cn_a_share_tushare_g12k_fixed_instrument" not in package_sources


def test_g12k_fixed_instrument_preserves_accepted_tushare_bytes() -> None:
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in PROTECTED_SHA256
    } == PROTECTED_SHA256


def test_g12k_fixed_instrument_acquisition_signature_is_stable() -> None:
    assert function_arguments(
        MODULE, "acquire_tushare_g12k_fixed_instrument_source_bounded_v1"
    ) == (
        ["request"],
        ["token", "output_dir", "post", "time_ns", "sleep"],
    )
    assert function_arguments(MODULE, "main") == (
        ["argv"],
        [],
    )


def test_g12k_fixed_instrument_observer_is_provider_specific_and_in_memory() -> None:
    source = OBSERVATION_MODULE.read_text(encoding="utf-8")
    imported = imports(OBSERVATION_MODULE)

    assert function_arguments(
        OBSERVATION_MODULE,
        "observe_g12k_tushare_fixed_instrument_source_bounded_v1",
    ) == (
        [],
        [
            "g12i_report_bytes",
            "acquisition_receipt_bytes",
            "snapshot",
            "instrument_catalog",
            "supersedes_report",
            "supersedes_acquisition_receipt_bytes",
            "supersedes_snapshot",
        ],
    )
    assert not any(
        name.startswith(("crypto_quant_backtest", "crypto_quant_trading"))
        for name in imported
    )
    assert not any(
        name in imported for name in ("httpx", "requests", "socket", "pathlib", "os")
    )
    for forbidden in (
        "MarketBundle",
        "MarketEvent",
        "Runtime",
        "Kernel",
        "LocalMarketBundleRepository",
        "open(",
        "repository head",
        "current report",
    ):
        assert forbidden not in source


def test_g12k_fixed_instrument_observer_has_no_root_export() -> None:
    root_source = BUILDER_ROOT.read_text(encoding="utf-8")
    assert "G12KFixedInstrumentSourceBoundedObservation" not in root_source
    assert "observe_g12k_tushare_fixed_instrument_source_bounded_v1" not in root_source
