from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "0d373b71b263a53b6b00e50b26ae1508dcfc986f"
MODULE = ROOT / "tools/acquisition/cn_a_share_quality_bband_tushare_s1_structural_v1.py"
PACKET = ROOT.parent / "platform-qb-formal-s1-authority/implementation/plans/quality-bband-tushare-s1-authority-pivot-v1.md"
ALLOWED = {
    "tools/acquisition/cn_a_share_quality_bband_tushare_s1_structural_v1.py",
    "tests/tools/acquisition/test_cn_a_share_quality_bband_tushare_s1_structural_v1.py",
    "tests/architecture/test_quality_bband_tushare_s1_structural_v1_boundary.py",
}
PRIVATE_SYMBOLS = {
    "_FrozenSourceIdentity",
    "_LoadedSourceRoot",
    "_strict_json",
    "_read_root_member",
    "_load_source_root",
    "_canonical_instrument",
    "_fifth_anniversary",
    "_derive_catalog_and_extras",
    "_build_screen_dispositions",
    "_build_financial_requirements",
    "_validate_frozen_hashes",
    "_rename_noreplace_at",
    "_atomic_publish",
    "_parse_args",
    "main",
}


def test_tool_is_offline_source_bounded_atomic_and_has_exact_authority_flags() -> None:
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
    assert "dir_fd=staging_fd" in source and "dir_fd=parent_fd" in source
    assert "_rename_noreplace_at(parent_fd, staging_name, output.name)" in source and "os.fsync" in source
    assert '"owner_approved_tushare_authority": True' in source
    assert '"formal_s1_qualified": True' in source
    assert '"provider_scope_exact": True' in source
    for flag in (
        "official_exchange_authority",
        "official_csrc_industry_authority",
        "market_truth_completeness_claimed",
        "survivorship_bias_safe_beyond_tushare_scope",
        "formal_s2_qualified",
        "decision_grade_eligible",
        "strategy_authorized",
        "strategy_target_authorized",
        "backtest_authorized",
        "validation_authorized",
        "deployment_authorized",
    ):
        assert f'"{flag}": False' in source
    assert "MarketBundle" not in source
    assert "TargetSnapshot" not in source
    assert "ExecutionRequest" not in source


def test_public_operation_cli_schema_and_required_symbols_are_exact() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    operation = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "build_quality_bband_tushare_s1_structural_v1"
    )
    assert operation.args.args == []
    assert [argument.arg for argument in operation.args.kwonlyargs] == [
        "s0_root",
        "annual_roster_root",
        "output_dir",
    ]
    names = {node.name for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))}
    assert {"QualityBbandTushareS1Failure", "QualityBbandTushareS1Error"} <= names
    assert PRIVATE_SYMBOLS <= names
    source = MODULE.read_text(encoding="utf-8")
    assert source.count("parser.add_argument(") == 3
    assert "/srv/" not in source
    assert "--filter" not in source and "--authority" not in source and "--count" not in source


def test_packet_body_hash_is_self_excluding_and_frozen_in_tool() -> None:
    raw = PACKET.read_bytes()
    line = (
        b"- **Packet body hash:** `sha256:aeb8ac2b5aa8a97c5cf04140ff4a12a0c45854ee8ea34c19a8a89792676006bb` "
        b"(SHA-256 of this UTF-8 file with this entire line removed)\n"
    )
    assert raw.count(line) == 1
    digest = "sha256:" + hashlib.sha256(raw.replace(line, b"", 1)).hexdigest()
    assert digest == "sha256:aeb8ac2b5aa8a97c5cf04140ff4a12a0c45854ee8ea34c19a8a89792676006bb"
    assert digest in MODULE.read_text(encoding="utf-8")


def test_candidate_write_set_is_exact_base_is_preserved_and_nothing_is_staged() -> None:
    subprocess.run(["git", "merge-base", "--is-ancestor", BASE, "HEAD"], cwd=ROOT, check=True)
    status_lines = subprocess.check_output(
        ["git", "status", "--short", "--untracked-files=all"], cwd=ROOT, text=True
    ).splitlines()
    changed = {
        line[3:]
        for line in status_lines
        if not line[3:].startswith((".pi-lens/", ".venv/"))
    }
    staged = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True
    ).splitlines()
    committed = set(
        subprocess.check_output(
            ["git", "diff", "--name-only", f"{BASE}..HEAD"], cwd=ROOT, text=True
        ).splitlines()
    )
    assert staged == []
    assert changed <= ALLOWED
    assert committed <= ALLOWED
    assert changed | committed == ALLOWED
