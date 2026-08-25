from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tools/acquisition/cn_a_share_tushare_financial_sentinel_v2.py"
PREDECESSOR = "e7e874fc58e0911b7df1cd0463387526afcb845d"
V1_HASHES = {
    "tools/acquisition/cn_a_share_tushare_financial_sentinel_v1.py": "ffdf3d30fb64f0bbddb0c5d6a120af2f6acef04b39fcd196245121411d257a52",
    "tests/tools/acquisition/test_cn_a_share_tushare_financial_sentinel_v1.py": "e76ff828f7f78e8ef07eba255e56940d4526a10fff7e55c9e40c8a99130bc53d",
    "tests/architecture/test_g12a_tushare_financial_sentinel_v1_boundary.py": "819400e851a3e3dc3f3c2cdce583f1486ab6d5e65092ae9e0be3b41bef8a95c9",
}


def test_v2_is_additive_acquisition_only_and_v1_is_immutable() -> None:
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
        "FinancialStatementUnitDeclaration",
        "available_at_utc",
    ):
        assert forbidden not in source
    for frozen in (
        '"000651.SZ"',
        '"20231231"',
        '"20240430"',
        "1219928418.pdf",
        "1220300051.pdf",
        '"decision_grade_eligible": False',
        '"deployment_authorized": False',
    ):
        assert frozen in source
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", PREDECESSOR, "HEAD"],
        cwd=ROOT,
        check=True,
    )
    for relative, expected in V1_HASHES.items():
        predecessor_bytes = subprocess.check_output(
            ["git", "show", f"{PREDECESSOR}:{relative}"], cwd=ROOT
        )
        current_bytes = (ROOT / relative).read_bytes()
        assert hashlib.sha256(predecessor_bytes).hexdigest() == expected
        assert current_bytes == predecessor_bytes


def test_v2_write_set_is_exact() -> None:
    allowed = {
        "tools/acquisition/cn_a_share_tushare_financial_sentinel_v2.py",
        "tests/tools/acquisition/test_cn_a_share_tushare_financial_sentinel_v2.py",
        "tests/architecture/test_g12a_tushare_financial_sentinel_v2_boundary.py",
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
