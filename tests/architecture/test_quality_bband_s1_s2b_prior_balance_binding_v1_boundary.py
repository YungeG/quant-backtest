from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "0c00c8266c2fe904e11f982979d804ff5d205700"
MODULE = ROOT / "tools/acquisition/cn_a_share_quality_bband_s1_s2b_prior_balance_binding_v1.py"
TEST_MODULE = ROOT / "tests/tools/acquisition/test_cn_a_share_quality_bband_s1_s2b_prior_balance_binding_v1.py"
ALLOWED = {
    "tools/acquisition/cn_a_share_quality_bband_s1_s2b_prior_balance_binding_v1.py",
    "tests/tools/acquisition/test_cn_a_share_quality_bband_s1_s2b_prior_balance_binding_v1.py",
    "tests/architecture/test_quality_bband_s1_s2b_prior_balance_binding_v1_boundary.py",
}


def test_tool_is_offline_and_does_not_import_predecessor_modules() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(name.startswith(("urllib", "requests", "http", "socket")) for name in imports)
    assert not any("quality_bband" in name for name in imports)
    assert "os.environ" not in source and "latest" not in source.lower()
    assert "RawSourceMember" in source and "freeze_source_snapshot" in source
    assert 'keep_bytes=name != "provider-rows.jsonl"' in source
    assert "O_NOFOLLOW" in source and "dir_fd=root_fd" in source
    assert "os.walk" not in source and "_enumerate_source_files(root_fd)" in source


def test_public_operation_and_cli_have_exact_five_paths() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    operation = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "build_quality_bband_s1_s2b_prior_balance_binding_v1"
    )
    assert operation.args.args == []
    assert [argument.arg for argument in operation.args.kwonlyargs] == [
        "stage_binding_root", "s2b_root", "s2a_root", "stage_a_root", "output_dir"
    ]
    source = MODULE.read_text(encoding="utf-8")
    assert source.count("parser.add_argument(") == 5
    assert all(
        value in source
        for value in (
            "--stage-binding-root", "--s2b-root", "--s2a-root", "--stage-a-root", "--output-dir"
        )
    )


def test_enum_output_surface_flags_and_base_are_frozen() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    enum_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "QualityBbandS1S2bPriorBalanceBindingFailure"
    )
    assert [
        node.targets[0].id
        for node in enum_node.body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
    ] == [
        "INPUT_TYPE_MISMATCH",
        "CATALOG_IDENTITY_MISMATCH",
        "SOURCE_MEMBER_CONFLICT",
        "FINANCIAL_REVISION_MISMATCH",
        "FINANCIAL_PAYLOAD_INCOMPLETE",
        "BUNDLE_EXACT_COVER_MISMATCH",
        "PUBLICATION_INTEGRITY_FAILURE",
    ]
    source = MODULE.read_text(encoding="utf-8")
    assert BASE in source
    for value in (
        "prior-balance-requirements.json",
        "prior-balance-provider-rows.jsonl",
        "prior-balance-binding-manifest.json",
        "226c7f1e5e678e1d8b35eca4a52a7427030b83605088199bbb14a297020e1a6e",
        "b51724cc10ce8fb2556ed59bb75e654a7dfff60f1a142ae0abf2bd7eede357cb",
        "1418102e92a50c28b379751fdc012af4f6751b90dc420f1b2711abf4f3fd63b3",
        "2b83d008ce3783f10e0a4e505e3cf165baa04baba885e6e1f4d9fe54345ae4bc",
        "1b34a72179420bd0da6ca336d0ee6a46c039177117c23993c79afed2e888d674",
        "f5c4c2f83352f68948e31a9cb049d8dfba20e6e12bcd9d6adc8e37152fdee124",
    ):
        assert value in source
    for name in (
        "formal_s2_qualified", "financial_payload_complete", "financial_scope_qualified",
        "decision_grade_eligible", "strategy_authorized", "strategy_target_authorized",
        "backtest_authorized", "validation_authorized", "deployment_authorized",
    ):
        assert f'"{name}": False' in source


def test_no_downstream_types_and_update_flag_is_never_a_selector() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"MarketBundle", "TargetSnapshot", "Strategy", "Runtime", "Trading", "ExecutionRequest"}
    assert not {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} & forbidden
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.IfExp, ast.comprehension)):
            expression = node.test if isinstance(node, (ast.If, ast.IfExp)) else node.iter
            assert "update_flag" not in ast.unparse(expression)
    assert '"update_flag": row[-1]' in source
    assert "row[:-1]" in source


def test_three_member_publication_is_pinned_no_delete_and_no_clobber() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert "renameat2" in source and "_rename_noreplace_at" in source
    assert "staging_identity" in source and "parent_identity" in source
    assert "identities[name]" in source and "published_fd" in source
    assert "set(os.listdir(staging_fd)) != set(_OUTPUT_FILES)" in source
    assert "set(os.listdir(published_fd)) != set(_OUTPUT_FILES)" in source
    assert "os.unlink" not in source and "os.rmdir" not in source and "shutil.rmtree" not in source
    assert "O_CREAT | os.O_EXCL" in source
    assert "for name in _OUTPUT_FILES" in source
    assert "_verify_visible_output_parent(output, parent_identity)" in source


def test_real_sentinel_and_synthetic_revision_and_race_coverage_are_present() -> None:
    source = TEST_MODULE.read_text(encoding="utf-8")
    for value in (
        "QB_S1_S2B_PRIOR_BALANCE_REAL_ARTIFACT_SENTINEL",
        "test_extract_retains_all_revisions_and_update_flag_never_selects_or_orders",
        "test_duplicate_profiles_distinguish_metadata_and_economic_revisions",
        "test_source_root_catalog_and_declared_member_conflicts_are_distinct",
        "test_global_failure_precedence_inspects_all_four_roots",
        "test_publication_race_never_deletes_racing_destination_or_quarantined_staging",
        "test_second_source_enumeration_rejects_racing_tree_change",
        "test_second_source_enumeration_rejects_same_size_in_place_mutation",
        "test_publication_rejects_extra_member_injected_during_rename_without_deletion",
        "test_publication_rejects_output_ancestor_replacement",
        "test_publication_rejects_staging_pathname_substitution_without_deleting_attacker",
        "required READY root is missing",
    ):
        assert value in source


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
        subprocess.check_output(["git", "diff", "--name-only", f"{BASE}..HEAD"], cwd=ROOT, text=True).splitlines()
    )
    assert changed <= ALLOWED
    assert committed <= ALLOWED
    assert changed | committed == ALLOWED
