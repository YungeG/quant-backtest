from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DAILY_MODULE = ROOT / "tools/acquisition/cn_a_share_tushare.py"
CALENDAR_MODULE = ROOT / "tools/acquisition/cn_a_share_tushare_trade_calendar.py"
PACKAGES = ROOT / "packages"


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
    return (
        [argument.arg for argument in function.args.args],
        [argument.arg for argument in function.args.kwonlyargs],
    )


def test_g12i_source_bounded_v2_stays_additive_tool_only() -> None:
    daily_source = DAILY_MODULE.read_text(encoding="utf-8")
    calendar_source = CALENDAR_MODULE.read_text(encoding="utf-8")
    imported = imports(DAILY_MODULE) | imports(CALENDAR_MODULE)

    assert not any(
        name.startswith(("crypto_quant_backtest", "crypto_quant_trading"))
        for name in imported
    )
    assert not imported.intersection({"httpx", "requests", "socket"})
    for forbidden in ("Protocol", "Adapter", "Factory", "Registry", "Cache"):
        assert forbidden not in daily_source
        assert forbidden not in calendar_source
    assert "TUSHARE_TOKEN" in daily_source
    assert "--token" not in daily_source
    assert "config/settings.json" not in daily_source
    assert "source-bounded-v2" in daily_source
    assert "_post_with_retries" in daily_source
    assert "_provider_body" in daily_source
    assert "_stdlib_post" in daily_source
    assert "freeze_source_snapshot" in daily_source
    assert "publish_directory" in daily_source

    package_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in PACKAGES.glob("*/src/**/*.py")
        if path.is_file()
    )
    assert "cn_a_share_tushare_source_bounded" not in package_sources
    assert "acquire_tushare_cn_a_share_daily_source_bounded_v2" not in package_sources


def test_g12i_v2_does_not_change_v1_acquisition_signatures() -> None:
    assert function_arguments(DAILY_MODULE, "acquire_daily_listing") == (
        ["request"],
        [
            "token",
            "output_dir",
            "acquired_at_epoch_nanoseconds",
            "post",
            "sleep",
        ],
    )
    assert function_arguments(CALENDAR_MODULE, "acquire_trade_calendar") == (
        ["request"],
        [
            "token",
            "output_dir",
            "acquired_at_epoch_nanoseconds",
            "post",
            "sleep",
        ],
    )
    assert function_arguments(
        DAILY_MODULE, "acquire_tushare_cn_a_share_daily_source_bounded_v2"
    ) == (
        ["request"],
        ["token", "output_dir", "post", "time_ns", "sleep"],
    )
