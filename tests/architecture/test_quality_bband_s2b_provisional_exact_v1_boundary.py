from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "8d532da4a58eea22dd6e9f6ce7f5b13cfafbfbe0"
MODULE = ROOT / "tools/acquisition/cn_a_share_quality_bband_s2b_provisional_exact_v1.py"
ALLOWED = {
    "tools/acquisition/cn_a_share_quality_bband_s2b_provisional_exact_v1.py",
    "tests/tools/acquisition/test_cn_a_share_quality_bband_s2b_provisional_exact_v1.py",
    "tests/architecture/test_quality_bband_s2b_provisional_exact_v1_boundary.py",
}


def test_tool_is_offline_source_bounded_atomic_and_false_authority() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(name.startswith(("urllib", "requests", "http", "socket")) for name in imports)
    assert "freeze_source_snapshot" in source and "verify_source_snapshot" in source
    assert "build_pan_hai_2014_official_balance_backfill_v1" in source
    assert "declare_official_annual_report_nonfiling_v1" in source
    assert 'tree["terminal_leaf_member_keys"]' in source
    assert "_rename_noreplace(staging, output)" in source and "os.fsync" in source
    assert '"formal_s1_qualified": False' in source
    assert '"formal_s2_qualified": False' in source
    assert '"strategy_authorized": False' in source
    assert '"strategy_target_authorized": False' in source
    assert '"backtest_authorized": False' in source
    assert '"validation_authorized": False' in source
    assert '"deployment_authorized": False' in source
    assert "MarketBundle" not in source
    assert "TargetSnapshot" not in source
    assert "ExecutionRequest" not in source


def test_public_operation_and_cli_have_only_six_frozen_paths() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    operation = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "extract_quality_bband_s2b_provisional_exact_v1"
    )
    assert [argument.arg for argument in operation.args.kwonlyargs] == [
        "s0_root",
        "annual_roster_root",
        "s2a_root",
        "official_remediation_root",
        "nonfiling_publication_root",
        "output_dir",
    ]
    assert operation.args.args == []
    source = MODULE.read_text(encoding="utf-8")
    assert source.count("parser.add_argument(") == 6
    assert "--count" not in source and "--filter" not in source and "--authority" not in source


def test_candidate_write_set_is_exact_and_base_is_preserved() -> None:
    subprocess.run(["git", "merge-base", "--is-ancestor", BASE, "HEAD"], cwd=ROOT, check=True)
    changed = {
        line[3:]
        for line in subprocess.check_output(
            ["git", "status", "--short", "--untracked-files=all"], cwd=ROOT, text=True
        ).splitlines()
        if not line[3:].startswith(".pi-lens/")
    }
    committed = set(
        subprocess.check_output(
            ["git", "diff", "--name-only", f"{BASE}..HEAD"], cwd=ROOT, text=True
        ).splitlines()
    )
    assert changed <= ALLOWED
    assert committed <= ALLOWED
    assert changed | committed == ALLOWED
