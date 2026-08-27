from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "8d532da4a58eea22dd6e9f6ce7f5b13cfafbfbe0"
MODULE = ROOT / "tools/acquisition/cn_a_share_quality_bband_2026_calendar_lineage_source_bounded_v1.py"
ALLOWED = {
    "tools/acquisition/cn_a_share_quality_bband_2026_calendar_lineage_source_bounded_v1.py",
    "tests/tools/acquisition/test_cn_a_share_quality_bband_2026_calendar_lineage_source_bounded_v1.py",
    "tests/architecture/test_quality_bband_2026_calendar_lineage_source_bounded_v1_boundary.py",
}


def test_source_candidate_has_exact_boundary_and_no_strategy_authority() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(name.startswith(("crypto_quant_backtest", "crypto_quant_trading")) for name in imports)
    assert "ProxyHandler({})" in source
    assert "_NoRedirect" in source
    assert "canonical_bytes" in source
    assert "os.rename(staging, output)" in source and "os.fsync" in source
    assert '"formal_s1_qualified"' in source
    assert '"s2b_exact_cover_complete"' in source
    assert '"strategy_authorized"' in source
    assert '"deployment_authorized"' in source
    assert "MarketBundle" not in source
    assert "TargetSnapshot" not in source
    assert "ExecutionRequest" not in source
    assert "TUSHARE_PROXY_TOKEN" in source
    assert "x-api-key-redacted" in source


def test_candidate_write_set_is_exact_and_predecessor_is_preserved() -> None:
    subprocess.run(["git", "merge-base", "--is-ancestor", BASE, "HEAD"], cwd=ROOT, check=True)
    changed = {
        line[3:]
        for line in subprocess.check_output(
            ["git", "status", "--short", "--untracked-files=all"], cwd=ROOT, text=True
        ).splitlines()
    }
    committed = set(
        subprocess.check_output(
            ["git", "diff", "--name-only", f"{BASE}..HEAD"], cwd=ROOT, text=True
        ).splitlines()
    )
    assert changed <= ALLOWED
    assert committed <= ALLOWED
    assert changed | committed == ALLOWED
