from __future__ import annotations

import ast
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tools/acquisition/cn_a_share_tushare_gree_valuation_source_bounded_v1.py"
PREDECESSOR = "bac94d56272d3d3aa1172c052c855d4fb46a4356"
ALLOWED = {
    "tools/acquisition/cn_a_share_tushare_gree_valuation_source_bounded_v1.py",
    "tests/tools/acquisition/test_cn_a_share_tushare_gree_valuation_source_bounded_v1.py",
    "tests/architecture/test_g12a_gree_valuation_source_bounded_v1_boundary.py",
}


def test_valuation_sentinel_is_additive_fixed_acquisition_only() -> None:
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
                "crypto_quant_strategy",
                "crypto_quant_validation",
            )
        )
        for name in imports
    )
    for forbidden in (
        "MarketBundle(",
        "BacktestRuntime(",
        "execute_experiment(",
        "validate_candidate(",
        "PromotionDecision(",
        "Order(",
        "Account(",
        "LiveRequest(",
    ):
        assert forbidden not in source
    for frozen in (
        '"000651.SZ"',
        '"20190506"',
        '"20240506"',
        '"daily_basic"',
        '"total_mv"',
        '"pe_ttm"',
        '"source_bounded": True',
        '"decision_grade_eligible": False',
        '"deployment_authorized": False',
        "TUSHARE_PROXY_TOKEN",
    ):
        assert frozen in source
    assert "TUSHARE_TOKEN" not in source
    assert "api.waditu.com" not in source
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", PREDECESSOR, "HEAD"],
        cwd=ROOT,
        check=True,
    )


def test_valuation_sentinel_write_set_is_exact() -> None:
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", PREDECESSOR, "HEAD"],
        cwd=ROOT,
        check=True,
    )
    committed = set(
        subprocess.check_output(
            ["git", "diff", "--name-only", f"{PREDECESSOR}..HEAD"],
            cwd=ROOT,
            text=True,
        ).splitlines()
    )
    worktree = {
        line[3:]
        for line in subprocess.check_output(
            ["git", "status", "--short", "--untracked-files=all"],
            cwd=ROOT,
            text=True,
        ).splitlines()
    }
    assert committed | worktree == ALLOWED
    assert committed <= ALLOWED
    assert worktree <= ALLOWED
