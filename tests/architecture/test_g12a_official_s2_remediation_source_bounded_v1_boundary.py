from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tools/acquisition/cn_a_share_official_s2_remediation_source_bounded_v1.py"
PREDECESSOR = "33f7320bd3f1e81c6a985f2fdeea39aedb7bc01e"
ALLOWED = {
    "tools/acquisition/cn_a_share_official_s2_remediation_source_bounded_v1.py",
    "tests/tools/acquisition/test_cn_a_share_official_s2_remediation_source_bounded_v1.py",
    "tests/architecture/test_g12a_official_s2_remediation_source_bounded_v1_boundary.py",
}
PREDECESSOR_HASHES = {
    "tools/acquisition/_common.py": "00f617fe88a7cd83212dac72756d4d9a9a8ef51092508614b8986c6f5b3a2ec6",
    "packages/market-bundle-builder/src/crypto_quant_bundle_builder/source_snapshots.py": "ec39d18d7eabb2d35d8d7eb7f237e39f77afb37440e843b7f9726dd2a4758361",
    "tools/acquisition/cn_a_share_tushare_s2a_vip_financial_source_bounded_v1.py": "d0f4fbd600b84fda3cd72abdf2ad8655166310c97fd2253921d09ab544ca634f",
    "tests/tools/acquisition/test_cn_a_share_tushare_s2a_vip_financial_source_bounded_v1.py": "78f16625067e39c6f1be281030eb1de259879341dcbb427fb428f5eea9ce9c3c",
    "tests/architecture/test_g12a_s2a_vip_financial_source_bounded_v1_boundary.py": "97e7d916db3146a1e2344081c3e74e665b617b8b166b22390fe3122f9d9b07f1",
}


def test_official_s2_remediation_capture_is_stdlib_source_only_and_non_authoritative() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_symbols = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert top_level_symbols == {
        "MetadataRequest", "PdfRequest", "_NoRedirect", "_require_safe_output",
        "_post_with_retries", "_get_with_retries", "_read_bounded", "_parse_metadata",
        "_validate_pdf", "acquire_official_s2_remediation_source_v1", "_build_output",
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
        "crypto_quant_bundle_builder", "dataclasses", "json", "os", "pathlib",
        "sys", "time", "typing", "urllib.error", "urllib.parse",
        "urllib.request",
    }
    for required in (
        "https://www.cninfo.com.cn/new/hisAnnouncement/query",
        "https://static.cninfo.com.cn/finalpage/2015-04-04/1200788303.PDF",
        "https://www.sse.com.cn/disclosure/credibility/supervision/inquiries/enquiry/c/10111560/files/a38770503b904cf88f85ebe52a75ad36.pdf",
        "MAX_LOGICAL_REQUESTS = 22", "MAX_METADATA_MEMBER_BYTES = 1 << 20",
        "MAX_PDF_MEMBER_BYTES = 8 << 20", "MAX_TOTAL_BYTES = 32 << 20",
        "freeze_source_snapshot", "verify_source_snapshot", "_common.publish_directory",
        'vendor_key="cninfo.com.cn-sse.com.cn"',
        'license_ref="official.public-disclosure"',
        '"deployment_authorized"',
    ):
        assert required in source
    for forbidden in (
        "os.environ", "getenv(", "TUSHARE", "api.waditu.com", "xiaodefa",
        "FinancialStatement", "NonfilingDeclaration", "Strategy(", "Stage(",
        "Target(", "Execution(", "Promotion(", "MarketBundle(", "BacktestRuntime(",
        "available_at_utc", "extract_text", "pdfplumber", "pypdf",
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
        "os.path.lexists",
        "urllib.request.build_opener",
        "urllib.request.ProxyHandler",
        "urllib.request.Request",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = dotted_name(node.func)
        if isinstance(node.func, ast.Name) and node.func.id in {
            "open", "exec", "eval", "compile", "__import__",
        }:
            forbidden_mutations.append(node)
        if call_name and call_name.startswith(("os.", "urllib.request.")):
            if call_name not in allowed_direct_calls:
                forbidden_mutations.append(node)
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in {
                "write", "write_bytes", "write_text", "mkdir", "unlink",
                "rename", "touch", "rmdir", "remove", "chmod", "symlink_to",
                "hardlink_to",
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


def test_predecessor_bytes_are_immutable_and_new_files_do_not_exist_at_base() -> None:
    subprocess.run(["git", "merge-base", "--is-ancestor", PREDECESSOR, "HEAD"], cwd=ROOT, check=True)
    for relative, expected_hash in PREDECESSOR_HASHES.items():
        predecessor_bytes = subprocess.check_output(["git", "show", f"{PREDECESSOR}:{relative}"], cwd=ROOT)
        assert hashlib.sha256(predecessor_bytes).hexdigest() == expected_hash
        assert (ROOT / relative).read_bytes() == predecessor_bytes
    for relative in ALLOWED:
        assert subprocess.run(["git", "cat-file", "-e", f"{PREDECESSOR}:{relative}"], cwd=ROOT, check=False).returncode != 0


def test_official_s2_remediation_write_set_is_exact() -> None:
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
