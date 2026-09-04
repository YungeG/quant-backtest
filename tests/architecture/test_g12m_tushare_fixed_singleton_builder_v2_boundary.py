from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]
PRODUCTION = (
    ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/"
    "g12m_tushare_fixed_singleton_execution_bundle_v2.py"
)
ALLOWED_FILES = {
    (
        "packages/market-bundle-builder/src/crypto_quant_bundle_builder/"
        "g12m_tushare_fixed_singleton_execution_bundle_v2.py"
    ),
    (
        "tests/bundle_builder/providers/tushare/"
        "test_g12m_tushare_fixed_singleton_execution_bundle_v2.py"
    ),
    ("tests/architecture/test_g12m_tushare_fixed_singleton_builder_v2_boundary.py"),
}
FIXTURE_PREFIX = (
    "tests/fixtures/market_data/providers/tushare/"
    "g12m-fixed-singleton-execution-bundle-v2/"
)


def test_production_boundary_has_no_runtime_kernel_io_or_root_export() -> None:
    source = PRODUCTION.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert not any(
        name.startswith(
            (
                "crypto_quant_backtest",
                "crypto_quant_trading",
                "pathlib",
                "os",
                "io",
                "socket",
                "httpx",
                "requests",
            )
        )
        for name in imports
    )
    assert "open(" not in source
    assert "LocalMarketBundleRepository" not in source
    assert "LocalMarketBundleReader" not in source
    assert "Runtime" not in source
    assert "Kernel" not in source

    root_export = (
        ROOT
        / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
    ).read_text(encoding="utf-8")
    assert "g12m_tushare_fixed_singleton_execution_bundle_v2" not in root_export
    assert "G12MTushare" not in root_export


def test_v2_02_worktree_write_set_is_exact() -> None:
    status = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    changed = tuple(line[3:] for line in status)
    if not changed:
        introduction = subprocess.run(
            [
                "git",
                "log",
                "--diff-filter=A",
                "--format=%H",
                "--",
                PRODUCTION.relative_to(ROOT).as_posix(),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        assert len(introduction) == 1
        changed = tuple(
            subprocess.run(
                [
                    "git",
                    "diff-tree",
                    "--no-commit-id",
                    "--name-only",
                    "-r",
                    introduction[0],
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.splitlines()
        )
    assert changed
    assert all(
        path in ALLOWED_FILES or path.startswith(FIXTURE_PREFIX) for path in changed
    )
