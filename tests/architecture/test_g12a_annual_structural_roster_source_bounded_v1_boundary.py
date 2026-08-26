from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tools/acquisition/cn_a_share_tushare_annual_structural_roster_source_bounded_v1.py"
PREDECESSOR = "ea17ccf93f6242222800c298d6aab39177b8455d"
ALLOWED = {
    "tools/acquisition/cn_a_share_tushare_annual_structural_roster_source_bounded_v1.py",
    "tests/tools/acquisition/test_cn_a_share_tushare_annual_structural_roster_source_bounded_v1.py",
    "tests/architecture/test_g12a_annual_structural_roster_source_bounded_v1_boundary.py",
}


def test_annual_structural_roster_sentinel_is_fixed_additive_acquisition_only() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    definitions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert definitions == {
        "TushareAnnualStructuralRosterSourceBoundedRequestV1",
        "_timestamp",
        "_validate_trade_calendar_rows",
        "_validate_roster_rows",
        "acquire_tushare_annual_structural_roster_source_bounded_v1",
        "_parser",
        "main",
    }
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert {
        "ProxyPost",
        "_ALLOWED_ENDPOINTS",
        "_MINIMUM_DELAY_SECONDS",
        "_PROXY_KEY",
        "_headers",
        "_post_with_retries",
        "_request_body",
        "_stdlib_post",
        "_authority_rows",
        "_is_real_historical_date",
        "_validate_trade_calendar_range_v2",
        "RawSourceMember",
        "SourceSnapshotProvenance",
        "freeze_source_snapshot",
    } <= imported
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
    for frozen in (
        '"20260826-annual-structural-candidate-01"',
        '"start_date": "20160430"',
        '"end_date": "20250510"',
        '"20160503": 0',
        '"20170502": 3232',
        '"20250506": 5415',
        '"source_bounded": True',
        '"calendar_authority_qualified": False',
        '"historical_roster_qualified": False',
        '"listing_membership_qualified": False',
        '"absence_authority": False',
        '"decision_grade_eligible": False',
        '"deployment_authorized": False',
        "TUSHARE_PROXY_TOKEN",
        "_common.publish_directory",
        "_validate_trade_calendar_range_v2(rows, **_CALENDAR_PARAMS)",
    ):
        assert frozen in source
    for forbidden in (
        "TUSHARE_TOKEN",
        "api.waditu.com",
        "import requests",
        "import httpx",
        "MarketBundle(",
        "BacktestRuntime(",
        "PromotionDecision(",
        'parser.add_argument("--capture-key"',
        'parser.add_argument("--calendar-start"',
        'parser.add_argument("--roster-date"',
        'parser.add_argument("--fields"',
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


def test_annual_structural_roster_sentinel_write_set_is_exact() -> None:
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
