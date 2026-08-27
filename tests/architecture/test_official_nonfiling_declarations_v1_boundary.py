from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "8d532da4a58eea22dd6e9f6ce7f5b13cfafbfbe0"
MODULE = ROOT / "tools/acquisition/cn_a_share_official_nonfiling_declarations_v1.py"
ALLOWED = {
    "tools/acquisition/cn_a_share_official_nonfiling_declarations_v1.py",
    "tests/tools/acquisition/test_cn_a_share_official_nonfiling_declarations_v1.py",
    "tests/architecture/test_official_nonfiling_declarations_v1_boundary.py",
}


def test_publication_is_source_only_and_has_no_network_or_strategy_authority() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(name.startswith(("urllib", "requests", "http", "socket")) for name in imports)
    assert "declare_official_annual_report_nonfiling_v1" in source
    assert "freeze_source_snapshot" in source and "verify_source_snapshot" in source
    assert "canonical_bytes" in source
    assert "os.rename(staging, output)" in source and "os.fsync" in source
    assert '"formal_s1_qualified": False' in source
    assert '"s2b_exact_cover_complete": False' in source
    assert '"strategy_target_authorized": False' in source
    assert '"deployment_authorized": False' in source
    assert "MarketBundle" not in source
    assert "TargetSnapshot" not in source
    assert "ExecutionRequest" not in source


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
