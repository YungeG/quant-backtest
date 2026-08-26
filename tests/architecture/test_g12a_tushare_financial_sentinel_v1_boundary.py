from __future__ import annotations

import ast
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tools/acquisition/cn_a_share_tushare_financial_sentinel_v1.py"


def test_financial_sentinel_is_acquisition_only_and_scope_frozen() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }

    assert not any(
        name.startswith(
            (
                "crypto_quant_backtest",
                "crypto_quant_market_data",
                "crypto_quant_trading",
            )
        )
        for name in imports
    )
    for forbidden in (
        "MarketBundle",
        "BacktestRuntime",
        "execute_experiment",
        "validate_candidate",
        "fina_indicator",
        "MarketEvent",
        "financial_statement_observations",
    ):
        assert forbidden not in source
    for frozen in (
        '"000651.SZ"',
        '"20231231"',
        '"20240430"',
        "1219928418.pdf",
        '"decision_grade_eligible": False',
        '"deployment_authorized": False',
    ):
        assert frozen in source
    acquisition_root = (ROOT / "tools/acquisition/__init__.py").read_text(
        encoding="utf-8"
    )
    assert "financial_sentinel" not in acquisition_root
    assert {
        "FinancialSentinelFailureCode",
        "FinancialSentinelAcquisitionError",
        "TushareCnAShareFinancialSourceSentinelRequestV1",
        "acquire_tushare_cn_a_share_financial_source_sentinel_v1",
    } <= {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }


def test_financial_sentinel_write_set_is_exact() -> None:
    allowed = {
        "tools/acquisition/cn_a_share_tushare_financial_sentinel_v1.py",
        "tests/tools/acquisition/test_cn_a_share_tushare_financial_sentinel_v1.py",
        "tests/architecture/test_g12a_tushare_financial_sentinel_v1_boundary.py",
    }
    changed = {
        line[3:]
        for line in subprocess.check_output(
            ["git", "status", "--short", "--untracked-files=all"],
            cwd=ROOT,
            text=True,
        ).splitlines()
    }
    if changed:
        assert changed == allowed
        return
    introduction = subprocess.check_output(
        [
            "git",
            "log",
            "--diff-filter=A",
            "--format=%H",
            "--",
            MODULE.relative_to(ROOT).as_posix(),
        ],
        cwd=ROOT,
        text=True,
    ).splitlines()
    assert len(introduction) == 1
    committed = set(
        subprocess.check_output(
            [
                "git",
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                introduction[0],
            ],
            cwd=ROOT,
            text=True,
        ).splitlines()
    )
    assert committed == allowed
