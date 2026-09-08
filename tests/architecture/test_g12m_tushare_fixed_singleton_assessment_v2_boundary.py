from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]
PRODUCTION = (
    ROOT
    / "packages/backtest-runtime/src/crypto_quant_backtest/"
    "g12m_tushare_fixed_singleton_assessment_v2.py"
)
ALLOWED_FILES = {
    (
        "packages/backtest-runtime/src/crypto_quant_backtest/"
        "g12m_tushare_fixed_singleton_assessment_v2.py"
    ),
    "tests/runtime/g12m/test_tushare_fixed_singleton_assessment_v2.py",
    (
        "tests/architecture/"
        "test_g12m_tushare_fixed_singleton_assessment_v2_boundary.py"
    ),
}
FIXTURE_PREFIX = (
    "tests/fixtures/runtime/g12m-tushare-fixed-singleton-assessment-v2/"
)


def test_assessor_is_pure_runtime_local_and_not_root_exported() -> None:
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
    assert not any("builder" in value.lower() for value in imports)
    assert not any("repository" in value.lower() for value in imports)
    assert not any("reader" in value.lower() for value in imports)
    assert not any("publisher" in value.lower() for value in imports)
    assert "pathlib" not in imports
    assert "os" not in imports
    assert "subprocess" not in imports
    assert "open(" not in source
    assert "Path(" not in source
    assert "BacktestRuntime" not in source
    assert "ArtifactReader" not in source
    assert "ArtifactPublisher" not in source
    assert "tests." not in source

    allowed_project_imports = {
        "crypto_quant_domain",
        "crypto_quant_market_data",
        "g12m_tushare_fixed_singleton_route_v2",
        "verified_publications",
    }
    assert {
        value.rsplit(".", 1)[-1]
        for value in imports
        if value.startswith(("crypto_quant", "g12m_"))
        or value == "verified_publications"
    } <= allowed_project_imports

    root_export = (
        ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/__init__.py"
    ).read_text(encoding="utf-8")
    assert "g12m_tushare_fixed_singleton_assessment_v2" not in root_export
    assert "TushareFixedSingletonSourceBoundedAssessmentV2" not in root_export


def test_v2_04_assessment_write_set_is_exact() -> None:
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
