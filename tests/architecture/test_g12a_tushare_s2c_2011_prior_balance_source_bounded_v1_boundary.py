from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tools/acquisition/cn_a_share_tushare_s2c_2011_prior_balance_source_bounded_v1.py"
BASE = "0c00c8266c2fe904e11f982979d804ff5d205700"
ALLOWED = {
    "tools/acquisition/cn_a_share_tushare_s2c_2011_prior_balance_source_bounded_v1.py",
    "tests/tools/acquisition/test_cn_a_share_tushare_s2c_2011_prior_balance_source_bounded_v1.py",
    "tests/architecture/test_g12a_tushare_s2c_2011_prior_balance_source_bounded_v1_boundary.py",
}


def test_s2c_2011_prior_balance_capture_is_additive_source_bounded_and_non_stage() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    definitions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert {
        "TushareS2c2011PriorBalanceSourceBoundedRequestV1",
        "_capture_page_tree",
        "_validate_tree",
        "_freeze",
        "_read_bounded",
        "_stdlib_post",
        "_preflight_output",
        "_rename_noreplace_at",
        "_publish",
        "acquire_tushare_s2c_2011_prior_balance_source_bounded_v1",
        "_read_token_file",
        "_parser",
        "main",
    } <= definitions
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
        '_API_NAME = "balancesheet_vip"',
        '_PERIOD = "20111231"',
        '_ROOT_START_DATE = "20111231"',
        '_ROOT_END_DATE = "20260826"',
        '_COMP_TYPE = "1"',
        '_REPORT_TYPE = "1"',
        "MAX_SPLIT_DEPTH = 16",
        "MAX_TOTAL_REQUESTS = 4096",
        "MAX_TOTAL_RESPONSE_BYTES = 536_870_912",
        "_MINIMUM_DELAY_SECONDS = 0.5",
        '"source_bounded": True',
        '"source_superset": True',
        '"logical_request_count": state.logical_request_count',
        '"provider_attempt_count": state.provider_attempt_count',
        "stat.S_IMODE(metadata.st_mode) != 0o600",
        "verify_source_snapshot",
        "snapshot.member_bytes",
        "urllib.request.ProxyHandler({})",
        "_NoRedirect()",
        "response.read(",
        "renameat2",
        "dir_fd=",
        'parser.add_argument("--token-file"',
        'parser.add_argument("--output-dir"',
        '"formal_s2_qualified"',
        '"strategy_authorized"',
        '"backtest_authorized"',
        '"validation_authorized"',
        '"deployment_authorized"',
        '"decision_grade_eligible"',
    ):
        assert required in source
    for forbidden in (
        '"income_vip"',
        '"cashflow_vip"',
        "TUSHARE_PROXY_TOKEN",
        "TUSHARE_TOKEN",
        "api.waditu.com",
        "import requests",
        "import httpx",
        "MarketBundle(",
        "BacktestRuntime(",
        "PromotionDecision(",
        'parser.add_argument("--capture-key"',
        'parser.add_argument("--period"',
        'parser.add_argument("--start-date"',
        'parser.add_argument("--end-date"',
        'parser.add_argument("--fields"',
        '"lease_liab",',
        "os.unlink(",
        "os.rmdir(",
    ):
        assert forbidden not in source
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE, "HEAD"],
        cwd=ROOT,
        check=True,
    )
    for path in ALLOWED:
        assert subprocess.run(
            ["git", "cat-file", "-e", f"{BASE}:{path}"],
            cwd=ROOT,
            check=False,
        ).returncode != 0


def test_s2c_2011_prior_balance_capture_write_set_is_exact() -> None:
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
    subprocess.run(
        [
            "git",
            "diff",
            "--exit-code",
            BASE,
            "--",
            ".",
            *[f":(exclude){path}" for path in sorted(ALLOWED)],
        ],
        cwd=ROOT,
        check=True,
    )
