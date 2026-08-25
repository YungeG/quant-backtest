from __future__ import annotations

import ast
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = "5338d8046fa0f304d4a9590989c59ceffb51270b"
MODULE = ROOT / "tools/acquisition/cn_a_share_tushare_financial_history_sentinel_v3.py"
ALLOWED = {
    "tools/acquisition/cn_a_share_tushare_financial_history_sentinel_v3.py",
    "tests/tools/acquisition/test_cn_a_share_tushare_financial_history_sentinel_v3.py",
    "tests/architecture/test_g12a_tushare_financial_history_sentinel_v3_boundary.py",
}


def test_v3_is_fixed_additive_acquisition_only() -> None:
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
        "publish_directory",
        "MarketBundle",
        "BacktestRuntime",
        "execute_experiment",
        "validate_candidate",
        "available_at_utc",
        "FinancialStatementUnitDeclaration",
        '"is_calc"',
    ):
        assert forbidden not in source
    for frozen in (
        '"000651.SZ"',
        '"20181231"',
        '"20221231"',
        '"https://www.cninfo.com.cn/new/hisAnnouncement/query"',
        "1206125365.PDF",
        "1216702261.PDF",
        '"decision_grade_eligible": False',
        '"deployment_authorized": False',
    ):
        assert frozen in source
    assert {
        "FinancialHistorySentinelV3FailureCode",
        "FinancialHistorySentinelV3AcquisitionError",
        "TushareCnAShareFinancialHistorySentinelRequestV3",
        "acquire_tushare_cn_a_share_financial_history_sentinel_v3",
    } <= {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }
    assert "financial_history_sentinel_v3" not in (
        ROOT / "tools/acquisition/__init__.py"
    ).read_text(encoding="utf-8")


def test_v3_base_is_byte_identical_and_write_set_is_exact() -> None:
    tracked = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", BASE], cwd=ROOT, text=True
    ).splitlines()
    assert tracked
    for relative in tracked:
        current = ROOT / relative
        assert current.is_file(), relative
        assert current.read_bytes() == subprocess.check_output(
            ["git", "show", f"{BASE}:{relative}"], cwd=ROOT
        ), relative

    committed = set(
        subprocess.check_output(
            ["git", "diff", "--name-only", f"{BASE}..HEAD"],
            cwd=ROOT,
            text=True,
        ).splitlines()
    )
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    worktree = {line[3:] for line in status}
    assert committed | worktree == ALLOWED
    assert committed <= ALLOWED
    assert worktree <= ALLOWED
