from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]
FACADE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/facade.py"
DURABLE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/_durable_rebuild.py"
BASELINE_FILES = {
    "packages/backtest-runtime/src/crypto_quant_backtest/facade.py",
    "packages/backtest-runtime/src/crypto_quant_backtest/_durable_rebuild.py",
    "tests/runtime/test_durable_rebuild_facade_v4.py",
    "tests/architecture/test_execution_input_bundle_v4_boundary.py",
}
ALLOWED_FILES = {
    "packages/backtest-runtime/src/crypto_quant_backtest/_durable_rebuild.py",
    "packages/backtest-runtime/src/crypto_quant_backtest/composition.py",
    "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    "packages/backtest-runtime/src/crypto_quant_backtest/execution_inputs.py",
    "packages/backtest-runtime/src/crypto_quant_backtest/facade.py",
    "tests/architecture/test_bt_gap02a_composition_boundary.py",
    "tests/architecture/test_bt_gap02b_execution_input_boundary.py",
    "tests/architecture/test_bt_gap02c_execution_closure_boundary.py",
    "tests/architecture/test_execution_input_bundle_v4_boundary.py",
    "tests/runtime/durable_rebuild/test_schema6.py",
    "tests/runtime/durable_rebuild/test_verification.py",
    "tests/runtime/engine/test_execution_liquidity_role.py",
    "tests/runtime/execution_inputs/test_execution_liquidity_role_bundle_v6.py",
    "tests/runtime/execution_inputs/test_multi_resolution_bundle_v3.py",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }


def test_schema4_fanin_preserves_facade_and_provider_boundaries() -> None:
    facade = FACADE.read_text(encoding="utf-8")
    durable = DURABLE.read_text(encoding="utf-8")
    assert not any(
        value.startswith(("crypto_quant_bundle_builder", "crypto_quant_trading"))
        for value in _imports(FACADE) | _imports(DURABLE)
    )
    assert facade.count("    def run(") == 1
    assert "run_attested" not in facade
    assert "canonical-v4" not in facade + durable
    assert "_snapshot_execution_request_v4_from_validated_schema" in facade
    assert "request.schema_version not in {3, 4, 6}" in durable

    root_export = (
        ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/__init__.py"
    ).read_text(encoding="utf-8")
    assert "_materialize_execution_input_bundle_v4" not in root_export
    assert "_read_execution_inputs_v4" not in root_export


def test_c4_02_write_set_is_exact() -> None:
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
                "-S",
                "_snapshot_execution_request_v4_from_validated_schema",
                "--format=%H",
                "--",
                FACADE.relative_to(ROOT).as_posix(),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        assert introduction
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
        assert set(changed) == BASELINE_FILES
        return
    assert set(changed) == ALLOWED_FILES
