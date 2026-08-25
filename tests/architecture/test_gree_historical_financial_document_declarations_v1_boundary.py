from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = "64159f81fa6f831990690dd133587b96533a0362"
MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/gree_historical_financial_document_declarations_v1.py"
)
ALLOWED = {
    "packages/market-bundle-builder/src/crypto_quant_bundle_builder/gree_historical_financial_document_declarations_v1.py",
    "tests/bundle_builder/providers/tushare/test_gree_historical_financial_document_declarations_v1.py",
    "tests/architecture/test_gree_historical_financial_document_declarations_v1_boundary.py",
}


def test_historical_declarations_are_pure_builder_values() -> None:
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
        "read_bytes",
        "write_bytes",
        "urllib",
        "requests",
        "subprocess",
        "os.environ",
        "time.time",
        "datetime.now",
        "MarketEvent",
        "MarketBundle",
        "Strategy",
        "available_at",
    ):
        assert forbidden not in source
    root_export = (
        ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
    ).read_text(encoding="utf-8")
    assert "gree_historical_financial_document_declarations_v1" not in root_export
    assert "GreeHistoricalFinancialPeriodDocumentDeclarationsV1" not in root_export


def test_pr6_base_tree_is_byte_and_mode_identical() -> None:
    raw = subprocess.check_output(
        ["git", "ls-tree", "-r", "-z", BASE], cwd=ROOT
    )
    entries: list[tuple[str, str, str]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, encoded_path = record.split(b"\t", 1)
        mode, kind, blob = metadata.decode().split()
        assert kind == "blob"
        entries.append((mode, blob, encoded_path.decode()))

    index_raw = subprocess.check_output(["git", "ls-files", "-s", "-z"], cwd=ROOT)
    index_modes = {}
    for record in index_raw.split(b"\0"):
        if not record:
            continue
        metadata, encoded_path = record.split(b"\t", 1)
        mode, _blob, _stage = metadata.decode().split()
        index_modes[encoded_path.decode()] = mode

    regular = [(mode, blob, path) for mode, blob, path in entries if mode in {"100644", "100755"}]
    hashes = subprocess.check_output(
        ["git", "hash-object", "--stdin-paths"],
        cwd=ROOT,
        input="".join(path + "\n" for _mode, _blob, path in regular),
        text=True,
    ).splitlines()
    assert len(hashes) == len(regular)
    for (mode, blob, path), current_hash in zip(regular, hashes, strict=True):
        assert (ROOT / path).is_file()
        assert index_modes[path] == mode
        assert current_hash == blob

    for mode, blob, path in entries:
        if mode in {"100644", "100755"}:
            continue
        assert mode == "120000"
        assert (ROOT / path).is_symlink()
        target = os.readlink(ROOT / path).encode()
        current_hash = subprocess.check_output(
            ["git", "hash-object", "--stdin"], cwd=ROOT, input=target
        ).decode().strip()
        assert index_modes[path] == mode
        assert current_hash == blob


def test_historical_declaration_write_set_is_exact() -> None:
    subprocess.run(["git", "merge-base", "--is-ancestor", BASE, "HEAD"], cwd=ROOT, check=True)
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
            ["git", "diff", "--name-only", f"{BASE}..HEAD"],
            cwd=ROOT,
            text=True,
        ).splitlines()
    )
    assert changed <= ALLOWED
    assert committed <= ALLOWED
    assert changed | committed == ALLOWED
