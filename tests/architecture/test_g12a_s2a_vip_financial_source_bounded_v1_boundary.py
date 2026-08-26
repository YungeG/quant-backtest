from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tools/acquisition/cn_a_share_tushare_s2a_vip_financial_source_bounded_v1.py"
PREDECESSOR = "1ba50ff69d1cdf37132e6e20ac1695bed0fbf685"
ALLOWED = {
    "tools/acquisition/cn_a_share_tushare_s2a_vip_financial_source_bounded_v1.py",
    "tests/tools/acquisition/test_cn_a_share_tushare_s2a_vip_financial_source_bounded_v1.py",
    "tests/architecture/test_g12a_s2a_vip_financial_source_bounded_v1_boundary.py",
}


def test_s2a_vip_financial_source_capture_is_additive_bounded_and_non_stage() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    } == {
        "TushareS2aVipFinancialSourceBoundedRequestV1",
        "_PageCaptureState",
        "_timestamp",
        "_midpoint",
        "_parse_page",
        "_validate_rows",
        "_capture_page_tree",
        "acquire_tushare_s2a_vip_financial_source_bounded_v1",
        "_parser",
        "main",
    }
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
    for required in (
        '"income_vip"',
        '"balancesheet_vip"',
        '"cashflow_vip"',
        '"s2a-vip-financial.2012-2024.20260826"',
        "MAX_SPLIT_DEPTH = 16",
        "MAX_TOTAL_REQUESTS = 4096",
        "MAX_TOTAL_RESPONSE_BYTES = 536_870_912",
        '"source_bounded": True',
        '"source_superset": True',
        '"expected_scope_extracted": False',
        '"decision_grade_eligible": False',
        '"deployment_authorized": False',
        "verify_source_snapshot",
        "_common.publish_directory",
        "TUSHARE_PROXY_TOKEN",
    ):
        assert required in source
    for forbidden in (
        "TUSHARE_TOKEN",
        "api.waditu.com",
        "import requests",
        "import httpx",
        "MarketBundle(",
        "BacktestRuntime(",
        "PromotionDecision(",
        'parser.add_argument("--capture-key"',
        'parser.add_argument("--period"',
        'parser.add_argument("--fields"',
        '"lease_liab",',
    ):
        assert forbidden not in source
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", PREDECESSOR, "HEAD"],
        cwd=ROOT,
        check=True,
    )
    for path in ALLOWED:
        assert subprocess.run(
            ["git", "cat-file", "-e", f"{PREDECESSOR}:{path}"],
            cwd=ROOT,
            check=False,
        ).returncode != 0


def test_s2a_vip_financial_source_capture_write_set_is_exact() -> None:
    committed = set(
        subprocess.check_output(
            ["git", "diff", "--name-only", f"{PREDECESSOR}..HEAD"],
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
    subprocess.run(
        [
            "git",
            "diff",
            "--exit-code",
            PREDECESSOR,
            "--",
            ".",
            *[f":(exclude){path}" for path in sorted(ALLOWED)],
        ],
        cwd=ROOT,
        check=True,
    )
