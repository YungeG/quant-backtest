from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/gree_2023_financial_statement_normalization_v1.py"
)
PREDECESSOR = "b4124d5985a6f9cbd39221fd55286abf5608b6b8"
PROTECTED = {
    "tools/acquisition/cn_a_share_tushare_financial_sentinel_v1.py": "ffdf3d30fb64f0bbddb0c5d6a120af2f6acef04b39fcd196245121411d257a52",
    "tests/tools/acquisition/test_cn_a_share_tushare_financial_sentinel_v1.py": "e76ff828f7f78e8ef07eba255e56940d4526a10fff7e55c9e40c8a99130bc53d",
    "tests/architecture/test_g12a_tushare_financial_sentinel_v1_boundary.py": "819400e851a3e3dc3f3c2cdce583f1486ab6d5e65092ae9e0be3b41bef8a95c9",
    "tools/acquisition/cn_a_share_tushare_financial_sentinel_v2.py": "9d8164e6678352a4d74b6c03cba5c332640a9fe7d04edfda877ea0d59e2c3faa",
    "tests/tools/acquisition/test_cn_a_share_tushare_financial_sentinel_v2.py": "027787a87afca18c811cdd2ab6c40d08f7534840c34ca76ab74b9bd25428241d",
    "tests/architecture/test_g12a_tushare_financial_sentinel_v2_boundary.py": "c80ab43c42dcb5bf55318ea3cefd7c63879301b49f311fda559152fd5ab89e95",
    "packages/market-bundle-builder/src/crypto_quant_bundle_builder/gree_2023_financial_document_declarations_v1.py": "04fbdd2d6d9121503ead81dc81f7c1b5bfa11590a01a1d0f3248e575aed7b174",
    "tests/bundle_builder/providers/tushare/test_gree_2023_financial_document_declarations_v1.py": "4a14fd6d828b947a706315df29eb373f9fee86535e038e60ff097e0f2e20d776",
    "tests/architecture/test_gree_2023_financial_document_declarations_v1_boundary.py": "473ab4bdd5ae4965e2a6a49c58c7f203f1bb6956a1663dd56f2d8c3a453fd1b2",
    "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py": "ce723694c39feeb0f70976065f8e513a1a2277d93cc35401bbaf046520acc40e",
    "uv.lock": "a97b6708411bcec45f23504cc41b3a2b54c80d9272a6deb3f2800be891e9b41d",
}
ALLOWED = {
    "packages/market-bundle-builder/src/crypto_quant_bundle_builder/gree_2023_financial_statement_normalization_v1.py",
    "tests/bundle_builder/providers/tushare/test_gree_2023_financial_statement_normalization_v1.py",
    "tests/architecture/test_gree_2023_financial_statement_normalization_v1_boundary.py",
}


def test_normalization_is_pure_builder_only_and_predecessors_are_git_identical() -> None:
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
                "tools.acquisition",
            )
        )
        for name in imports
    )
    for forbidden in (
        "Path(",
        "open(",
        "urllib",
        "requests",
        "subprocess",
        "os.environ",
        "time.time",
        "datetime.now",
        "MarketEvent",
        "MarketBundle",
        "BacktestRuntime",
        "Strategy",
        "pypdf",
        "pdfplumber",
        "read_bytes",
        "write_bytes",
    ):
        assert forbidden not in source
    root_export = (
        ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
    ).read_text(encoding="utf-8")
    assert "gree_2023_financial_statement_normalization_v1" not in root_export
    assert "Gree2023FinancialStatementObservation" not in root_export

    subprocess.run(
        ["git", "merge-base", "--is-ancestor", PREDECESSOR, "HEAD"],
        cwd=ROOT,
        check=True,
    )
    for relative, expected_hash in PROTECTED.items():
        predecessor_bytes = subprocess.check_output(
            ["git", "show", f"{PREDECESSOR}:{relative}"], cwd=ROOT
        )
        current_bytes = (ROOT / relative).read_bytes()
        assert hashlib.sha256(predecessor_bytes).hexdigest() == expected_hash
        assert current_bytes == predecessor_bytes


def test_normalization_candidate_write_set_is_exact() -> None:
    changed = {
        line[3:]
        for line in subprocess.check_output(
            ["git", "status", "--short", "--untracked-files=all"],
            cwd=ROOT,
            text=True,
        ).splitlines()
    }
    committed = set(
        subprocess.check_output(
            ["git", "diff", "--name-only", f"{PREDECESSOR}..HEAD"],
            cwd=ROOT,
            text=True,
        ).splitlines()
    )
    assert changed <= ALLOWED
    assert committed <= ALLOWED
    assert changed | committed == ALLOWED
