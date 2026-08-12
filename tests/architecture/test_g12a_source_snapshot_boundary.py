from __future__ import annotations

import ast
from pathlib import Path

from crypto_quant_bundle_builder import SourceSnapshot, freeze_source_snapshot


ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/source_snapshots.py"
)
ALLOWED_IMPORTS = {
    "__future__",
    "dataclasses",
    "enum",
    "gzip",
    "hashlib",
    "io",
    "json",
    "re",
    "tarfile",
    "typing",
    "unicodedata",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    return imports


def test_source_snapshot_core_is_stdlib_only_and_offline() -> None:
    assert MODULE.is_file()
    assert _imports(MODULE) <= ALLOWED_IMPORTS
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "crypto_quant_domain",
        "crypto_quant_market_data",
        "crypto_quant_trading",
        "crypto_quant_backtest",
        "Path(",
        "builtins.open(",
        "socket",
        "requests",
        "urllib",
        "subprocess",
        "datetime.now",
        "time.time",
        "Callable",
        "Protocol",
    ):
        assert forbidden not in source


def test_builder_root_exposes_only_frozen_g12a_surface() -> None:
    import crypto_quant_bundle_builder as builder

    assert set(builder.__all__) == {
        "RawSourceMember",
        "SourceSnapshot",
        "SourceSnapshotFailure",
        "SourceSnapshotFailureCode",
        "SourceSnapshotMember",
        "SourceSnapshotOutcome",
        "SourceSnapshotProvenance",
        "freeze_source_snapshot",
        "verify_source_snapshot",
    }
    assert builder.freeze_source_snapshot is freeze_source_snapshot
    assert builder.SourceSnapshot is SourceSnapshot


def test_runtime_does_not_import_builder_source_snapshot_core() -> None:
    runtime = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest"
    for path in runtime.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "crypto_quant_bundle_builder" not in source
        assert "SourceSnapshot" not in source
