from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]
PRODUCTION = (
    ROOT
    / "packages/backtest-runtime/src/crypto_quant_backtest/"
    "g12m_tushare_fixed_singleton_route_v2.py"
)
ALLOWED_FILES = {
    (
        "packages/backtest-runtime/src/crypto_quant_backtest/"
        "g12m_tushare_fixed_singleton_route_v2.py"
    ),
    "tests/runtime/g12m/test_tushare_fixed_singleton_route_v2.py",
    "tests/architecture/test_g12m_tushare_fixed_singleton_route_v2_boundary.py",
}
FIXTURE_PREFIX = (
    "tests/fixtures/runtime/g12m-tushare-fixed-singleton-production-run-v2/"
)


def test_route_uses_one_facade_without_builder_runner_or_engine_escape() -> None:
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
    assert not any(value.startswith("crypto_quant_bundle_builder") for value in imports)
    assert "tests." not in source
    assert "DeterministicBarEngine" not in source
    assert "AuditableBacktestRunner" not in source
    assert "run_with_cancellation" not in source
    assert source.count("runtime.run(execution_request)") == 1
    assert source.index("authority.validate_target_stream(target_stream)") < source.index(
        "prepare_multi_resolution_market_data_v1("
    )
    assert "_materialize_execution_input_bundle_v4" in source
    assert "BacktestExecutionRequest(4," in source
    assert "canonical-v4" not in source

    root_export = (
        ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/__init__.py"
    ).read_text(encoding="utf-8")
    assert "g12m_tushare_fixed_singleton_route_v2" not in root_export
    assert "G12MTushareFixedSingletonRouteResultV2" not in root_export


def test_v2_03_route_write_set_is_exact() -> None:
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
