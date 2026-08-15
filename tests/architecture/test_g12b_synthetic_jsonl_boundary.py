from __future__ import annotations

import ast
from pathlib import Path

from crypto_quant_bundle_builder import normalize_synthetic_jsonl_v1


ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/synthetic_jsonl.py"
)
ALLOWED_IMPORTS = {
    "__future__",
    "crypto_quant_domain",
    "crypto_quant_market_data",
    "dataclasses",
    "enum",
    "json",
    "re",
    "source_snapshots",
    "typing",
}
G12B_EXPORTS = {
    "SyntheticJsonlV1Config",
    "SyntheticJsonlV1NormalizationFailure",
    "SyntheticJsonlV1NormalizationFailureCode",
    "SyntheticJsonlV1NormalizationOutcome",
    "SyntheticJsonlV1NormalizationResult",
    "SyntheticJsonlV1RecordLocator",
    "SyntheticJsonlV1SourceTrace",
    "normalize_synthetic_jsonl_v1",
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


def test_synthetic_jsonl_uses_only_public_offline_normalization_contracts() -> None:
    assert MODULE.is_file()
    assert _imports(MODULE) <= ALLOWED_IMPORTS
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "crypto_quant_domain.",
        "crypto_quant_market_data.",
        "crypto_quant_trading",
        "crypto_quant_backtest",
        "archive_bytes",
        "tarfile",
        "gzip",
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


def test_builder_root_exactly_adds_frozen_g12b_exports() -> None:
    import crypto_quant_bundle_builder as builder

    assert G12B_EXPORTS <= set(builder.__all__)
    assert builder.normalize_synthetic_jsonl_v1 is normalize_synthetic_jsonl_v1
    assert len(set(builder.__all__)) == 45


def test_runtime_and_kernel_do_not_import_builder_normalizer() -> None:
    for directory in (
        ROOT / "packages/backtest-runtime/src/crypto_quant_backtest",
        ROOT / "packages/trading-kernel/src/crypto_quant_trading",
    ):
        for path in directory.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "crypto_quant_bundle_builder" not in source
            assert "SyntheticJsonlV1" not in source
