from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "0d373b71b263a53b6b00e50b26ae1508dcfc986f"
MODULE = ROOT / "tools/acquisition/cn_a_share_quality_bband_tushare_s1_s2b_stage_binding_v1.py"
TEST_MODULE = ROOT / "tests/tools/acquisition/test_cn_a_share_quality_bband_tushare_s1_s2b_stage_binding_v1.py"
ALLOWED = {
    "tools/acquisition/cn_a_share_quality_bband_tushare_s1_s2b_stage_binding_v1.py",
    "tests/tools/acquisition/test_cn_a_share_quality_bband_tushare_s1_s2b_stage_binding_v1.py",
    "tests/architecture/test_quality_bband_tushare_s1_s2b_stage_binding_v1_boundary.py",
}


def test_tool_is_offline_self_contained_and_keeps_downstream_authority_false() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(name.startswith(("urllib", "requests", "http", "socket")) for name in imports)
    assert not any("quality_bband_s2b_provisional_exact" in name for name in imports)
    assert not any("tushare_s1_structural" in name for name in imports)
    assert 'keep_bytes=name != "provider-rows.jsonl"' in source
    assert "O_NOFOLLOW" in source and "dir_fd=root_fd" in source
    assert "_open_output_parent" in source and 'return ("/" if output.is_absolute() else ".")' in source
    assert "dir_fd=descriptor" in source and 'if ".." in components' in source
    assert "os.path.lexists" not in source and ".absolute()" not in source
    assert "renameat2" in source and "_rename_noreplace_at" in source
    assert "staging_identity" in source and "parent_identity" in source
    assert "member_identity" in source and "published_member_fd" in source
    assert "_verify_visible_output_parent(output, parent_identity)" in source
    assert '"formal_s2_qualified": False' in source
    assert '"strategy_authorized": False' in source
    assert '"strategy_target_authorized": False' in source
    assert '"backtest_authorized": False' in source
    assert '"validation_authorized": False' in source
    assert '"deployment_authorized": False' in source
    assert "MarketBundle" not in source
    assert "TargetSnapshot" not in source
    assert "ExecutionRequest" not in source


def test_public_operation_and_cli_have_only_three_explicit_paths() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    operation = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "build_quality_bband_tushare_s1_s2b_stage_binding_v1"
    )
    assert operation.args.args == []
    assert [argument.arg for argument in operation.args.kwonlyargs] == [
        "s1_root",
        "s2b_root",
        "output_dir",
    ]
    source = MODULE.read_text(encoding="utf-8")
    assert source.count("parser.add_argument(") == 3
    assert all(value in source for value in ("--s1-root", "--s2b-root", "--output-dir"))
    assert "os.environ" not in source and "latest" not in source.lower()


def test_ready_evidence_sentinel_covers_real_mutations_and_secure_publication_races() -> None:
    source = TEST_MODULE.read_text(encoding="utf-8")
    assert "v1-candidate-02" in source
    assert "required READY S2B root is missing" in source
    assert 'changed_s1["manifest_id"]' in source
    assert 'changed_expected["expected_set_id"]' in source
    assert 'changed_members["provider-rows.jsonl"]' in source
    assert '("o_member_keys", "n_member_keys")' in source
    assert "test_atomic_publication_rejects_ancestor_replacement" in source
    assert "test_atomic_publication_rejects_parent_replacement" in source
    assert "test_atomic_publication_rejects_member_substitution_without_deleting_attacker" in source


def test_failure_enum_and_frozen_output_surface_are_exact() -> None:
    module = ast.parse(MODULE.read_text(encoding="utf-8"))
    enum_node = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef)
        and node.name == "QualityBbandTushareS1S2bBindingFailure"
    )
    assert [
        node.targets[0].id
        for node in enum_node.body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
    ] == [
        "INPUT_TYPE_SCHEMA_OR_PATH",
        "ARTIFACT_IDENTITY_MISMATCH",
        "AUTHORITY_REBINDING_MISMATCH",
        "SHARED_SOURCE_BINDING_MISMATCH",
        "EXPECTED_SET_EQUIVALENCE_MISMATCH",
        "S2B_CLOSURE_OR_PAYLOAD_MISMATCH",
        "FROZEN_OUTPUT_MISMATCH",
        "PUBLICATION_INTEGRITY_FAILURE",
    ]
    source = MODULE.read_text(encoding="utf-8")
    assert '"stage-binding-manifest.json"' in source
    assert "7323" in source
    assert "c54bac9818a24688699aa585e49e91bde64ddbaf3efa90e0aa18491ff9b86f5c" in source
    assert "ba5abfc5fc592ceb88ce1cabc95ebbded24abe9a8b108e9f6a31c96a0cc0878c" in source


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
