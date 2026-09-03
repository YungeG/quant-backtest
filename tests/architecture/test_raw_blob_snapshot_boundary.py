from __future__ import annotations

import ast
from pathlib import Path

import crypto_quant_bundle_builder as builder
from crypto_quant_bundle_builder import RawBlobSnapshotManifest


ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT
    / "packages"
    / "market-bundle-builder"
    / "src"
    / "crypto_quant_bundle_builder"
    / "raw_blob_snapshots.py"
)


def test_raw_blob_snapshot_builder_surface_has_no_foundation_dependency() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )

    assert not any(name.startswith("crypto_quant_foundation") for name in imported)
    assert builder.RawBlobSnapshotManifest is RawBlobSnapshotManifest
