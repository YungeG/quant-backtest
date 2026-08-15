from __future__ import annotations

import ast
from pathlib import Path

from crypto_quant_bundle_builder import (
    BundleValidationFailure,
    BundleValidationFailureCode,
    BundleValidationOutcome,
    validate_market_bundle_v1,
)


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/bundle_validation.py"
ALLOWED_IMPORTS = {
    "__future__",
    "collections",
    "crypto_quant_domain",
    "crypto_quant_market_data",
    "dataclasses",
    "enum",
    "typing",
}
G12C_EXPORTS = {
    "BundleValidationFailure",
    "BundleValidationFailureCode",
    "BundleValidationOutcome",
    "validate_market_bundle_v1",
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


def test_bundle_validation_module_uses_only_public_validation_contracts() -> None:
    assert MODULE.is_file()
    assert _imports(MODULE) <= ALLOWED_IMPORTS
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "pathlib",
        "socket",
        "subprocess",
        "requests",
        "urllib",
        "datetime.now",
    ):
        assert forbidden not in source


def test_builder_root_exposes_the_g12c_seam() -> None:
    import crypto_quant_bundle_builder as builder

    assert G12C_EXPORTS <= set(builder.__all__)
    assert len(set(builder.__all__)) == 38
    assert builder.validate_market_bundle_v1 is validate_market_bundle_v1
    assert builder.BundleValidationFailure is BundleValidationFailure
    assert builder.BundleValidationFailureCode is BundleValidationFailureCode
    assert builder.BundleValidationOutcome is BundleValidationOutcome


def test_runtime_and_kernel_do_not_import_bundle_validator() -> None:
    for directory in (
        ROOT / "packages/backtest-runtime/src",
        ROOT / "packages/trading-kernel/src",
    ):
        for path in directory.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "validate_market_bundle_v1" not in source
            assert "BundleValidationFailure" not in source
            assert "BundleValidationOutcome" not in source
