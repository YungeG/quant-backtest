from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tools/acquisition/cn_a_share_official_s2_remediation_supplement_source_bounded_v1.py"
PREDECESSOR = "7276c696365ad644066393d4ee3bdb40053ef4b9"
ALLOWED = {
    "tools/acquisition/cn_a_share_official_s2_remediation_supplement_source_bounded_v1.py",
    "tests/tools/acquisition/test_cn_a_share_official_s2_remediation_supplement_source_bounded_v1.py",
    "tests/architecture/test_g12a_official_s2_remediation_supplement_source_bounded_v1_boundary.py",
}
PREDECESSOR_HASHES = {
    "tools/acquisition/cn_a_share_official_s2_remediation_source_bounded_v1.py": "ecd2f3ae89a993ed4cc8b491197ea20add28097177615929a135ae9ec2feac6a",
    "tests/tools/acquisition/test_cn_a_share_official_s2_remediation_source_bounded_v1.py": "5d806881cff2bacf6cf94945342e4b16951aa8f5145071b53b47fcc3ee69c7b2",
    "tests/architecture/test_g12a_official_s2_remediation_source_bounded_v1_boundary.py": "bb9241ce439a219763aaea898dcd7228ad0a58963bfaf48a16dec296e0dfa2d7",
    "tools/acquisition/_common.py": "00f617fe88a7cd83212dac72756d4d9a9a8ef51092508614b8986c6f5b3a2ec6",
    "packages/market-bundle-builder/src/crypto_quant_bundle_builder/source_snapshots.py": "ec39d18d7eabb2d35d8d7eb7f237e39f77afb37440e843b7f9726dd2a4758361",
}
APPROVED_PREDECESSOR_IMPORTS = {
    "_CNINFO_PDF_HEADERS", "_CNINFO_POST_HEADERS", "_FORM_KEYS",
    "_METADATA_ENDPOINT", "_NoRedirect", "_read_bounded",
    "_require_safe_output", "_RETRYABLE_STATUSES", "_RETRY_DELAYS",
}


def test_supplement_capture_is_stdlib_source_only_bounded_and_non_authoritative() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_symbols = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert top_level_symbols == {
        "MetadataRequest", "JsonGetRequest", "PdfRequest", "_post_with_retries",
        "_get_with_retries", "_parse_cninfo_metadata", "_parse_neeq_metadata",
        "acquire_official_s2_remediation_supplement_source_v1", "_build_output",
        "_parse_args", "main",
    }
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
    assert imports == {
        "", "__future__", "_common", "argparse", "collections.abc",
        "cn_a_share_official_s2_remediation_source_bounded_v1",
        "crypto_quant_bundle_builder", "dataclasses", "json", "pathlib", "sys",
        "time", "typing", "urllib.error", "urllib.parse", "urllib.request",
    }
    predecessor_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "cn_a_share_official_s2_remediation_source_bounded_v1"
    ]
    assert len(predecessor_imports) == 1
    assert {alias.name for alias in predecessor_imports[0].names} == APPROVED_PREDECESSOR_IMPORTS
    for required in (
        "https://neeq.cs.com.cn/xsb/v1/xsb_search/&gs=R%E9%91%AB%E5%8D%871&st=2026-04-01&ed=2026-05-10&1.json",
        "http://dataclouds.cninfo.com.cn/sjother2/neeqs/2026/20260429/5e69266176024a6dae6eb9392c5e22b5.pdf",
        "https://dataclouds.cninfo.com.cn/sjother2/neeqs/2026/20260429/5e69266176024a6dae6eb9392c5e22b5.pdf",
        "MAX_LOGICAL_REQUESTS = 6", "MAX_METADATA_MEMBER_BYTES = 1 << 20",
        "MAX_PDF_MEMBER_BYTES = 1 << 20", "MAX_TOTAL_BYTES = 4 << 20",
        "freeze_source_snapshot", "verify_source_snapshot", "_common.publish_directory",
        'vendor_key="cninfo.com.cn-neeq.cs.com.cn"',
        'source_key="official.s2-remediation.nonfiling-effective-boundary-supplement.v1"',
        'license_ref="official.public-disclosure"',
        '"official_evidence_reviewed"', '"deployment_authorized"',
        "urllib.request.ProxyHandler({})",
    ):
        assert required in source
    for forbidden in (
        "os.environ", "getenv(", "TUSHARE", "api.waditu.com", "xiaodefa",
        "FinancialStatement", "NonfilingDeclaration", "Strategy(", "Stage(",
        "Target(", "Execution(", "Promotion(", "MarketBundle(", "BacktestRuntime(",
        "available_at_utc", "extract_text", "pdfplumber", "pypdf",
        "Cookie", "Authorization", "Bearer", "classify",
    ):
        assert forbidden not in source

    def dotted_name(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = dotted_name(node.value)
            return None if parent is None else f"{parent}.{node.attr}"
        return None

    forbidden_mutations = []
    allowed_direct_calls = {
        "urllib.request.build_opener", "urllib.request.ProxyHandler", "urllib.request.Request",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = dotted_name(node.func)
        if isinstance(node.func, ast.Name) and node.func.id in {"open", "exec", "eval", "compile", "__import__"}:
            forbidden_mutations.append(node)
        if call_name and call_name.startswith("urllib.request.") and call_name not in allowed_direct_calls:
            forbidden_mutations.append(node)
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in {
                "write", "write_bytes", "write_text", "mkdir", "unlink", "rename",
                "touch", "rmdir", "remove", "chmod", "symlink_to", "hardlink_to",
            }:
                forbidden_mutations.append(node)
            if node.func.attr == "open" and dotted_name(node.func.value) != "opener":
                forbidden_mutations.append(node)
            if node.func.attr == "replace" and dotted_name(node.func.value) != "title":
                root = node.func.value
                while isinstance(root, ast.Call) and isinstance(root.func, ast.Attribute):
                    root = root.func.value
                if dotted_name(root) != "title":
                    forbidden_mutations.append(node)
    assert forbidden_mutations == []
    publication_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "_common"
        and node.func.attr == "publish_directory"
    ]
    assert len(publication_calls) == 1


def test_pr13_predecessor_bytes_are_immutable_and_supplement_files_are_new() -> None:
    assert subprocess.run(["git", "merge-base", "--is-ancestor", PREDECESSOR, "HEAD"], cwd=ROOT, check=False).returncode == 0
    for relative, expected_hash in PREDECESSOR_HASHES.items():
        predecessor_bytes = subprocess.check_output(["git", "show", f"{PREDECESSOR}:{relative}"], cwd=ROOT)
        assert hashlib.sha256(predecessor_bytes).hexdigest() == expected_hash
        assert (ROOT / relative).read_bytes() == predecessor_bytes
    for relative in ALLOWED:
        assert subprocess.run(["git", "cat-file", "-e", f"{PREDECESSOR}:{relative}"], cwd=ROOT, check=False).returncode != 0


def test_official_s2_remediation_supplement_write_set_is_exact() -> None:
    committed = set(subprocess.check_output(["git", "diff", "--name-only", f"{PREDECESSOR}..HEAD"], cwd=ROOT, text=True).splitlines())
    status = subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT, text=True).splitlines()
    worktree = {line[3:] for line in status}
    assert committed | worktree == ALLOWED
    assert committed <= ALLOWED
    assert worktree <= ALLOWED
    subprocess.run([
        "git", "diff", "--exit-code", PREDECESSOR, "--", ".",
        *[f":(exclude){path}" for path in sorted(ALLOWED)],
    ], cwd=ROOT, check=True)
