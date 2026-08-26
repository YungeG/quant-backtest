from __future__ import annotations

import ast
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tools/acquisition/cn_a_share_tushare_s0_lightweight_catalog_source_bounded_v1.py"
PREDECESSOR = "5b99e50826a526cfd81ea8a28d2a1d1bf3daf52c"
ALLOWED = {
    "tools/acquisition/cn_a_share_tushare_s0_lightweight_catalog_source_bounded_v1.py",
    "tests/tools/acquisition/test_cn_a_share_tushare_s0_lightweight_catalog_source_bounded_v1.py",
    "tests/architecture/test_g12a_s0_lightweight_catalog_source_bounded_v1_boundary.py",
}


def test_s0_lightweight_catalog_sentinel_is_fixed_additive_acquisition_only() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    definitions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert definitions == {
        "TushareS0LightweightCatalogSourceBoundedRequestV1",
        "_timestamp",
        "_validate_rows",
        "acquire_tushare_s0_lightweight_catalog_source_bounded_v1",
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
        '"20260826-s0-candidate-01"',
        '_STATUSES = ("L", "D", "P")',
        '"ts_code"',
        '"act_ent_type"',
        '"L": 5550',
        '"D": 339',
        '"P": 0',
        '"source_bounded": True',
        '"absence_authority": False',
        '"decision_grade_eligible": False',
        '"deployment_authorized": False',
        "TUSHARE_PROXY_TOKEN",
        "_common.publish_directory",
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
        'parser.add_argument("--list-status"',
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


def test_s0_lightweight_catalog_sentinel_write_set_is_exact() -> None:
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
